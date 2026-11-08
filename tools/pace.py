"""Pace guard: decides whether one more LinkedIn action is allowed right now.

    python tools/pace.py check invite      -> OK | WAIT <seconds> <reason> | STOP <reason>
    python tools/pace.py log invite --lead li-0007
    python tools/pace.py warn "LinkedIn showed: 'You've reached the weekly invitation limit'"
    python tools/pace.py clear --i-checked-linkedin
    python tools/pace.py status
    python tools/pace.py next              -> seconds until the next send is allowed (for loop wakeups)

Exit codes for check: 0 = OK, 1 = WAIT, 2 = STOP. Run `check` right before every action and
`log` right after it, every time. The guard only works if every action is logged.
"""
from __future__ import annotations

import argparse
import random
import sys
from datetime import timedelta

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import (ACTIONS_FILE, ALL_ACTIONS, LEADS_FILE, SEND_ACTIONS, STOP_FILE, append_jsonl, iso, load_settings,
                    load_state, now, parse, read_jsonl, save_state, start_of_week)


def ramp_fraction(s: dict) -> float:
    r = s.get("ramp") or {}
    start = r.get("start_date")
    fr = r.get("week_fractions") or [1.0]
    if not start:
        return 1.0
    weeks = max(0, (now() - parse(start + "T00:00:00" if len(start) == 10 else start)).days // 7)
    return fr[min(weeks, len(fr) - 1)]


def limits(s: dict) -> dict:
    lim = dict(s["_limits"])
    f = ramp_fraction(s)
    for k in ("invites_per_day", "invites_per_week", "messages_per_day", "views_per_day", "sends_per_hour"):
        lim[k] = max(1, int(lim[k] * f))
    lim["_ramp"] = f
    return lim


def counts(actions: list[dict]) -> dict:
    t = now()
    day0 = t.replace(hour=0, minute=0, second=0)
    week0 = start_of_week(t)
    hour_ago = t - timedelta(hours=1)
    c = {"invite_today": 0, "invite_week": 0, "message_today": 0, "view_today": 0, "sends_last_hour": 0,
         "last_send": None}
    for a in actions:
        ts = parse(a["at"])
        kind = a["action"]
        if kind == "invite":
            if ts >= day0:
                c["invite_today"] += 1
            if ts >= week0:
                c["invite_week"] += 1
        if kind in ("message", "followup", "reply", "inmail") and ts >= day0:
            c["message_today"] += 1
        if kind == "view" and ts >= day0:
            c["view_today"] += 1
        if kind in SEND_ACTIONS:
            if ts >= hour_ago:
                c["sends_last_hour"] += 1
            if c["last_send"] is None or ts > c["last_send"]:
                c["last_send"] = ts
    return c


def invite_health(lim: dict) -> tuple[int, float | None]:
    """Pending invites and acceptance rate of invites sent 14+ days ago."""
    leads = read_jsonl(LEADS_FILE)
    pending = sum(1 for l in leads if l.get("status") == "invited")
    old = [l for l in leads if l.get("invited_at") and (now() - parse(l["invited_at"])).days >= 14]
    if len(old) < 20:
        return pending, None
    accepted = sum(1 for l in old if l.get("connected_at"))
    return pending, accepted / len(old)


def decide(action: str) -> tuple[str, int, str]:
    if action not in ALL_ACTIONS:
        return "STOP", 0, f"unknown action '{action}' (use one of {sorted(ALL_ACTIONS)})"
    s = load_settings()
    lim = limits(s)
    st = load_state()
    t = now()

    if STOP_FILE.exists():
        return "STOP", 0, f"kill switch: {STOP_FILE} exists. Delete it to resume."
    if st.get("warning"):
        w = st["warning"]
        until = parse(w["cooldown_until"])
        if not w.get("cleared"):
            return "STOP", 0, f"unresolved LinkedIn warning from {w['at']}: {w['text']!r}. A human must look at LinkedIn, then run `pace.py clear --i-checked-linkedin`."
        if t < until:
            return "WAIT", int((until - t).total_seconds()), f"cooling down after warning until {iso(until)}"

    if t.weekday() not in s.get("active_days", [0, 1, 2, 3, 4]):
        return "WAIT", seconds_to_next_window(s), "outside active days"
    h0, h1 = s.get("active_hours", [9, 18])
    lb = s.get("lunch_break") or [None, None]
    if not (h0 <= t.hour < h1) or (lb[0] is not None and lb[0] <= t.hour < lb[1]):
        return "WAIT", seconds_to_next_window(s), "outside active hours"

    c = counts(read_jsonl(ACTIONS_FILE))
    if action == "view":
        if c["view_today"] >= lim["views_per_day"]:
            return "WAIT", seconds_to_tomorrow(s), f"profile views today {c['view_today']}/{lim['views_per_day']}"
        return "OK", 0, "view allowed"

    if action == "invite":
        if c["invite_week"] >= lim["invites_per_week"]:
            return "WAIT", seconds_to_next_week(s), f"invites this week {c['invite_week']}/{lim['invites_per_week']}"
        if c["invite_today"] >= lim["invites_per_day"]:
            return "WAIT", seconds_to_tomorrow(s), f"invites today {c['invite_today']}/{lim['invites_per_day']}"
        pending, rate = invite_health(lim)
        if pending >= lim["pending_invites_max"]:
            return "STOP", 0, f"{pending} invites still pending (max {lim['pending_invites_max']}). Withdraw the oldest by hand before sending more."
        if rate is not None and rate < lim["min_acceptance_rate"]:
            return "STOP", 0, f"acceptance rate {rate:.0%} is under {lim['min_acceptance_rate']:.0%}. Fix targeting or the note before sending more invites."
    else:
        if c["message_today"] >= lim["messages_per_day"]:
            return "WAIT", seconds_to_tomorrow(s), f"messages today {c['message_today']}/{lim['messages_per_day']}"

    if c["sends_last_hour"] >= lim["sends_per_hour"]:
        return "WAIT", 15 * 60, f"{c['sends_last_hour']} sends in the last hour (max {lim['sends_per_hour']})"
    nxt = st.get("next_send_at")
    if nxt and t < parse(nxt):
        return "WAIT", int((parse(nxt) - t).total_seconds()), f"spacing: next send not before {nxt}"
    return "OK", 0, f"{action} allowed"


def seconds_to_next_window(s: dict) -> int:
    t = now()
    h0, h1 = s.get("active_hours", [9, 18])
    lb = s.get("lunch_break") or [None, None]
    days = s.get("active_days", [0, 1, 2, 3, 4])
    probe = t.replace(second=0) + timedelta(minutes=1)
    for _ in range(60 * 24 * 8):
        if probe.weekday() in days and h0 <= probe.hour < h1 and not (lb[0] is not None and lb[0] <= probe.hour < lb[1]):
            return max(60, int((probe - t).total_seconds()))
        probe += timedelta(minutes=15)
    return 3600


def seconds_to_tomorrow(s: dict) -> int:
    t = now()
    tomorrow = (t + timedelta(days=1)).replace(hour=0, minute=0, second=0)
    return int((tomorrow - t).total_seconds()) + 60


def seconds_to_next_week(s: dict) -> int:
    t = now()
    return int((start_of_week(t) + timedelta(days=7) - t).total_seconds()) + 60


def cmd_log(action: str, lead: str | None, note: str | None) -> None:
    if action not in ALL_ACTIONS:
        sys.exit(f"unknown action '{action}'")
    s = load_settings()
    lim = limits(s)
    t = now()
    append_jsonl(ACTIONS_FILE, {"at": iso(t), "action": action, "lead": lead, "note": note})
    if action in SEND_ACTIONS:
        st = load_state()
        gap = lim["min_gap_minutes"] + random.uniform(0, lim.get("jitter_minutes", 0))
        st["next_send_at"] = iso(t + timedelta(minutes=gap))
        save_state(st)
        print(f"logged {action} {lead or ''} at {iso(t)}; next send not before {st['next_send_at']}")
    else:
        print(f"logged {action} {lead or ''} at {iso(t)}")


def cmd_warn(text: str) -> None:
    s = load_settings()
    hours = s["_limits"]["cooldown_hours_after_warning"]
    st = load_state()
    t = now()
    st["warning"] = {"at": iso(t), "text": text, "cleared": False,
                     "cooldown_until": iso(t + timedelta(hours=hours))}
    st.setdefault("warning_history", []).append({"at": iso(t), "text": text})
    save_state(st)
    print(f"STOPPED. Warning recorded. Nothing is sent until a human checks LinkedIn and runs "
          f"`pace.py clear --i-checked-linkedin`; then a {hours}h cooldown applies.")


def cmd_clear(confirmed: bool) -> None:
    if not confirmed:
        sys.exit("Refusing: a human must open LinkedIn, confirm the account is fine, then pass --i-checked-linkedin.")
    st = load_state()
    if not st.get("warning"):
        print("no active warning")
        return
    st["warning"]["cleared"] = True
    save_state(st)
    print(f"warning cleared; cooldown still runs until {st['warning']['cooldown_until']}")


def cmd_status() -> None:
    s = load_settings()
    lim = limits(s)
    c = counts(read_jsonl(ACTIONS_FILE))
    pending, rate = invite_health(lim)
    st = load_state()
    print(f"tier: {s.get('aggressiveness')}  ramp: {lim['_ramp']:.0%}  send_mode: {s.get('send_mode')}")
    print(f"invites today {c['invite_today']}/{lim['invites_per_day']}  week {c['invite_week']}/{lim['invites_per_week']}")
    print(f"messages today {c['message_today']}/{lim['messages_per_day']}  views today {c['view_today']}/{lim['views_per_day']}")
    print(f"sends last hour {c['sends_last_hour']}/{lim['sends_per_hour']}  next send not before {st.get('next_send_at', 'now')}")
    print(f"pending invites {pending}/{lim['pending_invites_max']}  acceptance (14d+) {'n/a (<20 old invites)' if rate is None else f'{rate:.0%}'}")
    if STOP_FILE.exists():
        print("KILL SWITCH ON (data/STOP exists)")
    if st.get("warning"):
        print(f"WARNING: {st['warning']}")
    for a in ("invite", "message"):
        v, secs, why = decide(a)
        print(f"check {a}: {v} {secs if v == 'WAIT' else ''} {why}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("action")
    l = sub.add_parser("log"); l.add_argument("action"); l.add_argument("--lead"); l.add_argument("--note")
    w = sub.add_parser("warn"); w.add_argument("text")
    cl = sub.add_parser("clear"); cl.add_argument("--i-checked-linkedin", action="store_true")
    sub.add_parser("status")
    sub.add_parser("next")
    a = p.parse_args()
    if a.cmd == "check":
        v, secs, why = decide(a.action)
        print(f"{v} {secs} {why}" if v == "WAIT" else f"{v} {why}")
        sys.exit({"OK": 0, "WAIT": 1, "STOP": 2}[v])
    if a.cmd == "log":
        cmd_log(a.action, a.lead, a.note)
    elif a.cmd == "warn":
        cmd_warn(a.text)
    elif a.cmd == "clear":
        cmd_clear(a.i_checked_linkedin)
    elif a.cmd == "status":
        cmd_status()
    elif a.cmd == "next":
        best = None
        for act in ("message", "invite"):
            v, secs, _ = decide(act)
            if v == "OK":
                best = 0
                break
            if v == "WAIT":
                best = secs if best is None else min(best, secs)
        print(best if best is not None else -1)


if __name__ == "__main__":
    main()
