"""Lead store (data/leads.jsonl): one row per person, with the evidence that they are real and right.

    python tools/leads.py add '{"name": "...", "profile_url": "...", ...}'   add one lead (JSON)
    python tools/leads.py import found.jsonl                                 add many (skips duplicates)
    python tools/leads.py exists <profile_url>                               exit 0 if already known
    python tools/leads.py list [--status drafted]                            table of leads
    python tools/leads.py show li-0007
    python tools/leads.py set li-0007 key=value [key=value ...]              (value may be JSON)
    python tools/leads.py status li-0007 approved                            move along the pipeline
    python tools/leads.py gate li-0007                                       verification gate (exit 1 if it fails)
    python tools/leads.py next invite|message|followup                       best lead ready for that action
    python tools/leads.py due                                                follow-ups and first messages due now
    python tools/leads.py dnc <profile_url> "reason"                         never contact this person

Pipeline:
  found -> verified -> drafted -> approved -> invited -> connected -> messaged -> replied
  side exits: skipped (failed gate / not a fit), declined, do_not_contact
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import (DATA, LEADS_FILE, iso, load_settings, normalize_profile_url, now, parse, read_jsonl,
                    write_jsonl)

STATUSES = ["found", "verified", "drafted", "approved", "invited", "connected", "messaged", "replied",
            "skipped", "declined", "do_not_contact"]
DNC_FILE = DATA / "do_not_contact.jsonl"
STAMP = {"verified": "verified_at", "approved": "approved_at", "invited": "invited_at",
         "connected": "connected_at", "messaged": "messaged_at", "replied": "replied_at"}


def load() -> list[dict]:
    return read_jsonl(LEADS_FILE)


def save(rows: list[dict]) -> None:
    write_jsonl(LEADS_FILE, rows)


def dnc_urls() -> set[str]:
    return {r["profile_url"] for r in read_jsonl(DNC_FILE)}


def find(rows: list[dict], lead_id: str) -> dict:
    for r in rows:
        if r["id"] == lead_id:
            return r
    sys.exit(f"no lead {lead_id}")


def next_id(rows: list[dict]) -> str:
    n = max([int(r["id"].split("-")[1]) for r in rows if r.get("id", "").startswith("li-")] or [0])
    return f"li-{n + 1:04d}"


def add_one(rows: list[dict], lead: dict) -> str:
    url = normalize_profile_url(lead.get("profile_url", ""))
    if not url:
        return f"SKIP not a linkedin.com/in/ URL: {lead.get('profile_url')!r}"
    if url in dnc_urls():
        return f"SKIP do-not-contact: {url}"
    for r in rows:
        if r["profile_url"] == url:
            return f"SKIP duplicate of {r['id']}: {url}"
    lead = dict(lead)
    lead["profile_url"] = url
    lead["id"] = next_id(rows)
    lead.setdefault("status", "found")
    lead.setdefault("evidence", [])
    lead.setdefault("followups_sent", 0)
    lead["found_at"] = iso(now())
    rows.append(lead)
    return f"ADDED {lead['id']} {lead.get('name', '?')} {url}"


def gate(lead: dict, s: dict) -> list[str]:
    """Return the list of failed checks. Empty list = verified."""
    v = s.get("verification", {})
    fails = []
    if not lead.get("name"):
        fails.append("no name")
    if not normalize_profile_url(lead.get("profile_url", "")):
        fails.append("no valid profile URL")
    if lead["profile_url"] in dnc_urls():
        fails.append("on do-not-contact list")
    chk = lead.get("checks", {})
    if v.get("require_profile_opened") and not chk.get("profile_opened_at"):
        fails.append("profile not opened in the browser (checks.profile_opened_at)")
    if v.get("require_current_role_on_profile") and not (lead.get("role") and lead.get("company")):
        fails.append("current role/company not recorded from the profile")
    ev = lead.get("evidence", [])
    if v.get("require_second_source") and not any(
            e.get("url") and "linkedin.com" not in e["url"] for e in ev):
        fails.append("no second, non-LinkedIn source (company site, press, etc.) in evidence")
    max_days = v.get("max_days_since_active")
    last = chk.get("last_active")
    if max_days:
        if not last:
            fails.append("no checks.last_active date (latest post, comment or job change)")
        elif (now() - parse(last if "T" in last else last + "T00:00:00")).days > max_days:
            fails.append(f"inactive: last activity {last} is over {max_days} days ago")
    if v.get("min_connections") and int(chk.get("connections", 0)) < v["min_connections"]:
        fails.append(f"fewer than {v['min_connections']} connections (checks.connections)")
    if v.get("require_photo") and not chk.get("has_photo"):
        fails.append("no real profile photo (checks.has_photo)")
    if v.get("require_hook_source") and not (lead.get("hook") and lead.get("hook_source")):
        fails.append("no personal hook with a source URL (hook, hook_source)")
    if chk.get("red_flags"):
        fails.append(f"red flags: {chk['red_flags']}")
    return fails


def ready_for(rows: list[dict], action: str, s: dict) -> list[dict]:
    t = now()
    seq = s.get("sequence", {})
    out = []
    for r in rows:
        st = r.get("status")
        if action == "invite" and st == "approved" and not r.get("already_connected"):
            out.append(r)
        elif action == "message":
            if st == "approved" and r.get("already_connected"):
                out.append(r)
            elif st == "connected" and r.get("connected_at"):
                lo = seq.get("first_message_after_accept_hours", [4, 48])[0]
                if t - parse(r["connected_at"]) >= timedelta(hours=lo):
                    out.append(r)
        elif action == "followup" and st == "messaged":
            lo = seq.get("followup_after_days", [4, 9])[0]
            last = r.get("last_followup_at") or r.get("messaged_at")
            if (last and t - parse(last) >= timedelta(days=lo)
                    and r.get("followups_sent", 0) < seq.get("max_followups", 1)):
                out.append(r)
    out.sort(key=lambda r: (-(r.get("score") or 0), r.get("found_at", "")))
    return out


def table(rows: list[dict]) -> None:
    for r in rows:
        print(f"{r['id']}  {r.get('status', ''):<14} {str(r.get('score', '')):>3}  {r.get('name', '')[:28]:<28} "
              f"{(r.get('role') or '')[:24]:<24} @ {(r.get('company') or '')[:22]:<22} {r['profile_url']}")
    print(f"({len(rows)} leads)")


def coerce(v: str):
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return v


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("add").add_argument("json")
    sub.add_parser("import").add_argument("file")
    sub.add_parser("exists").add_argument("url")
    ls = sub.add_parser("list"); ls.add_argument("--status")
    sub.add_parser("show").add_argument("id")
    st = sub.add_parser("set"); st.add_argument("id"); st.add_argument("pairs", nargs="+")
    ss = sub.add_parser("status"); ss.add_argument("id"); ss.add_argument("new", choices=STATUSES)
    ss.add_argument("--force", action="store_true", help="skip the gate when moving to verified/approved")
    sub.add_parser("gate").add_argument("id")
    sub.add_parser("next").add_argument("action", choices=["invite", "message", "followup"])
    sub.add_parser("due")
    d = sub.add_parser("dnc"); d.add_argument("url"); d.add_argument("reason", nargs="?", default="")
    a = p.parse_args()

    rows = load()
    s = load_settings()

    if a.cmd == "add":
        print(add_one(rows, json.loads(a.json)))
        save(rows)
    elif a.cmd == "import":
        with open(a.file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    print(add_one(rows, json.loads(line)))
        save(rows)
    elif a.cmd == "exists":
        url = normalize_profile_url(a.url)
        hit = [r for r in rows if r["profile_url"] == url] or ([{"id": "do-not-contact"}] if url in dnc_urls() else [])
        print(f"YES {hit[0]['id']}" if hit else "NO")
        sys.exit(0 if hit else 1)
    elif a.cmd == "list":
        table([r for r in rows if not a.status or r.get("status") == a.status])
    elif a.cmd == "show":
        print(json.dumps(find(rows, a.id), indent=2, ensure_ascii=False))
    elif a.cmd == "set":
        r = find(rows, a.id)
        for pair in a.pairs:
            k, _, v = pair.partition("=")
            node = r
            *path, last = k.split(".")
            for part in path:
                node = node.setdefault(part, {})
            node[last] = coerce(v)
        save(rows)
        print(f"updated {a.id}")
    elif a.cmd == "status":
        r = find(rows, a.id)
        if a.new in ("verified", "drafted", "approved") and not a.force:
            fails = gate(r, s)
            if fails:
                print(f"GATE FAILED for {a.id}; status unchanged:")
                for f_ in fails:
                    print(f"  - {f_}")
                sys.exit(1)
        if a.new == "approved" and not a.force and not (r.get("draft") or {}).get("approved_hash"):
            sys.exit(f"{a.id}: approve the draft text with `drafts.py approve {a.id}` (it records what was approved).")
        r["status"] = a.new
        if a.new in STAMP:
            r[STAMP[a.new]] = iso(now())
        if a.new == "do_not_contact":
            from common import append_jsonl
            append_jsonl(DNC_FILE, {"profile_url": r["profile_url"], "reason": "status set", "at": iso(now())})
        save(rows)
        print(f"{a.id} -> {a.new}")
    elif a.cmd == "gate":
        r = find(rows, a.id)
        fails = gate(r, s)
        if fails:
            print(f"FAIL {a.id} {r.get('name')}")
            for f_ in fails:
                print(f"  - {f_}")
            sys.exit(1)
        print(f"PASS {a.id} {r.get('name')}")
    elif a.cmd == "next":
        ready = ready_for(rows, a.action, s)
        if not ready:
            print("NONE")
            sys.exit(1)
        print(json.dumps(ready[0], indent=2, ensure_ascii=False))
    elif a.cmd == "due":
        for act in ("message", "followup", "invite"):
            ready = ready_for(rows, act, s)
            print(f"{act}: {len(ready)} ready" + (f" (next: {ready[0]['id']} {ready[0].get('name')})" if ready else ""))
    elif a.cmd == "dnc":
        from common import append_jsonl
        url = normalize_profile_url(a.url)
        if not url:
            sys.exit("not a LinkedIn profile URL")
        append_jsonl(DNC_FILE, {"profile_url": url, "reason": a.reason, "at": iso(now())})
        for r in rows:
            if r["profile_url"] == url:
                r["status"] = "do_not_contact"
        save(rows)
        print(f"do-not-contact: {url}")


if __name__ == "__main__":
    main()
