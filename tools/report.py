"""Daily / weekly report: what went out, what came back, what's waiting on you.

    python tools/report.py            today + this week
    python tools/report.py --log      also append a one-line summary to data/log.md
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import timedelta

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import ACTIONS_FILE, DATA, LEADS_FILE, iso, load_settings, load_state, now, parse, read_jsonl, start_of_week
from pace import decide, invite_health, limits


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", action="store_true")
    a = p.parse_args()
    s = load_settings()
    lim = limits(s)
    t = now()
    day0 = t.replace(hour=0, minute=0, second=0)
    week0 = start_of_week(t)
    acts = read_jsonl(ACTIONS_FILE)
    leads = read_jsonl(LEADS_FILE)
    today = Counter(x["action"] for x in acts if parse(x["at"]) >= day0)
    week = Counter(x["action"] for x in acts if parse(x["at"]) >= week0)
    by_status = Counter(l.get("status") for l in leads)
    pending, rate = invite_health(lim)
    contacted = [l for l in leads if l.get("messaged_at")]
    replied = [l for l in contacted if l.get("replied_at")]
    st = load_state()

    print(f"== LinkedIn outreach report {iso(t)} ({s.get('aggressiveness')}, ramp {lim['_ramp']:.0%}) ==")
    print("today:     " + (", ".join(f"{k} {v}" for k, v in sorted(today.items())) or "nothing"))
    print("this week: " + (", ".join(f"{k} {v}" for k, v in sorted(week.items())) or "nothing"))
    print("pipeline:  " + ", ".join(f"{k} {by_status.get(k, 0)}" for k in
                                     ["found", "verified", "drafted", "approved", "invited", "connected",
                                      "messaged", "replied", "declined", "skipped", "do_not_contact"]))
    print(f"invites pending {pending}; acceptance (invites 14d+ old) {'n/a' if rate is None else f'{rate:.0%}'}; "
          f"reply rate {len(replied)}/{len(contacted)}" + (f" = {len(replied) / len(contacted):.0%}" if contacted else ""))
    waiting = by_status.get("drafted", 0)
    if waiting:
        print(f"WAITING ON YOU: {waiting} drafts to review (python tools/drafts.py review)")
    if st.get("warning") and not st["warning"].get("cleared"):
        print(f"STOPPED: LinkedIn warning {st['warning']['text']!r} at {st['warning']['at']}")
    v, secs, why = decide("invite")
    print(f"next invite: {v} {why}")
    if a.log:
        DATA.mkdir(parents=True, exist_ok=True)
        with open(DATA / "log.md", "a", encoding="utf-8") as f:
            f.write(f"- {iso(t)} today {dict(today)} | pipeline {dict(by_status)} | pending {pending} | "
                    f"acc {'n/a' if rate is None else f'{rate:.0%}'} | {v} {why}\n")


if __name__ == "__main__":
    main()
