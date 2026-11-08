"""Run every tool on fake data in a temp folder. Touches nothing real, opens no browser.

    python tools/selftest.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
failures = []


def run(args, now="2026-01-05T10:00:00", expect=0, home=None):
    env = dict(os.environ, LIO_HOME=str(home), LIO_NOW=now, PYTHONIOENCODING="utf-8")
    r = subprocess.run([sys.executable, str(TOOLS / args[0])] + args[1:], env=env, capture_output=True,
                       text=True, encoding="utf-8")
    ok = r.returncode == expect
    print(f"{'ok  ' if ok else 'FAIL'} {' '.join(args)} -> exit {r.returncode}: {(r.stdout or r.stderr).strip().splitlines()[:1]}")
    if not ok:
        failures.append((args, r.stdout, r.stderr))
    return r.stdout


def main():
    home = Path(tempfile.mkdtemp(prefix="lio-test-"))
    try:
        (home / "config").mkdir()
        s = json.loads((REPO / "config" / "settings.example.json").read_text(encoding="utf-8"))
        (home / "config" / "settings.json").write_text(json.dumps(s), encoding="utf-8")
        R = lambda *a, **k: run(list(a), home=home, **k)

        # leads: import, dedupe, gate
        R("leads.py", "import", str(REPO / "examples" / "leads.example.jsonl"))
        out = R("leads.py", "add", json.dumps({"name": "Dup", "profile_url": "https://linkedin.com/in/Jordan-Example-000?trk=x"}))
        assert "duplicate" in out, out
        R("leads.py", "gate", "li-0001")
        R("leads.py", "gate", "li-0002", expect=1)
        R("leads.py", "status", "li-0002", "drafted", expect=1)
        R("leads.py", "status", "li-0001", "drafted")

        # drafts: lint, approve, text guard
        R("drafts.py", "lint", "li-0001")
        R("drafts.py", "approve", "li-0001", "--by", "standing", expect=1)  # no standing approval by default
        R("drafts.py", "approve", "li-0001", "--by", "human")
        note = R("drafts.py", "text", "li-0001", "invite_note")
        assert note.startswith("Hi Jordan"), note
        R("leads.py", "set", "li-0001", "draft.invite_note=Hi Jordan, changed after approval")
        R("drafts.py", "text", "li-0001", "invite_note", expect=1)
        R("drafts.py", "review", "--status", "approved")

        # pace: hours, gap, caps, warnings, kill switch
        R("pace.py", "check", "invite")
        R("pace.py", "check", "invite", now="2026-01-05T07:00:00", expect=1)   # before hours
        R("pace.py", "check", "invite", now="2026-01-10T10:00:00", expect=1)   # Saturday
        R("pace.py", "log", "invite", "--lead", "li-0001")
        R("pace.py", "check", "message", now="2026-01-05T10:01:00", expect=1)  # gap
        R("pace.py", "check", "message", now="2026-01-05T10:20:00")
        for i in range(5):
            R("pace.py", "log", "invite", now=f"2026-01-05T10:{15 + i * 10}:00")
        out = R("pace.py", "check", "invite", now="2026-01-05T11:10:00", expect=1)  # careful: 5 sends/hour
        assert "last hour" in out, out
        for i in range(5):
            R("pace.py", "log", "invite", now=f"2026-01-05T14:{i * 10:02d}:00")
        out = R("pace.py", "check", "invite", now="2026-01-05T16:30:00", expect=1)  # 10/day careful cap
        assert "invites today" in out, out
        R("pace.py", "check", "invite", now="2026-01-06T10:00:00")
        R("pace.py", "warn", "Test: 'unusual activity' banner", now="2026-01-06T10:05:00")
        R("pace.py", "check", "message", now="2026-01-06T11:00:00", expect=2)
        R("pace.py", "clear", now="2026-01-06T11:00:00", expect=1)               # needs the flag
        R("pace.py", "clear", "--i-checked-linkedin", now="2026-01-06T11:00:00")
        R("pace.py", "check", "message", now="2026-01-07T11:00:00", expect=1)   # still cooling down (168h)
        R("pace.py", "check", "message", now="2026-01-14T11:00:00")
        (home / "data" / "STOP").write_text("stop")
        R("pace.py", "check", "message", now="2026-01-14T11:00:00", expect=2)
        (home / "data" / "STOP").unlink()

        # voice
        R("voice.py", "csv", str(REPO / "examples" / "messages.example.csv"), "--me", "Taylor Sample")
        prof = json.loads((home / "voice" / "voice_profile.json").read_text(encoding="utf-8"))
        assert prof["messages_analyzed"] == 4, prof
        R("drafts.py", "lint", "li-0001")

        R("report.py", "--log")
        R("leads.py", "set", "li-0001", "variant=A", "invited_at=\"2026-01-05T10:00:00\"")
        out = R("report.py", "--by", "variant")
        assert "A" in out and "invited" in out, out
        R("leads.py", "dnc", "https://www.linkedin.com/in/sam-placeholder", "asked not to be contacted")
        out = R("leads.py", "add", json.dumps({"name": "Sam", "profile_url": "https://www.linkedin.com/in/sam-placeholder"}))
        assert "do-not-contact" in out, out
    finally:
        shutil.rmtree(home, ignore_errors=True)
    if failures:
        print(f"\n{len(failures)} FAILED")
        for args, so, se in failures:
            print(" ".join(args), "\n", so, se)
        sys.exit(1)
    print("\nall checks passed")


if __name__ == "__main__":
    main()
