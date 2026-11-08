"""Draft checks, approval and the review sheet.

A lead's drafts live on the lead row:  "draft": {"invite_note": "...", "message": "...", "followup": "..."}

    python tools/drafts.py lint li-0007            hard errors (exit 1) + voice warnings
    python tools/drafts.py lint --status drafted   lint every drafted lead
    python tools/drafts.py review                  write review/review-<date>.md for the human
    python tools/drafts.py approve li-0007 --by human|standing
    python tools/drafts.py text li-0007 invite_note    print the exact approved text to send
                                                   (exit 1 if it changed after approval)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import ROOT, VOICE, iso, load_settings, now, read_jsonl, write_jsonl, LEADS_FILE
from leads import gate

FIELDS = ("invite_note", "message", "followup")
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
PLACEHOLDER = re.compile(r"\{[^}]*\}|\[[A-Z _]+\]|<[A-Z _]+>|XX+|TODO|TKTK", re.I)


def voice_profile() -> dict:
    p = VOICE / "voice_profile.json"
    if p.exists():
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    return {}


def draft_hash(d: dict) -> str:
    blob = json.dumps({k: d.get(k, "") for k in FIELDS}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def lint(lead: dict, s: dict) -> tuple[list[str], list[str]]:
    errors, warns = [], []
    d = lead.get("draft") or {}
    seq, dr = s.get("sequence", {}), s.get("drafts", {})
    vp = voice_profile()
    first = (lead.get("name") or "").split(" ")[0]
    if not any(d.get(k) for k in FIELDS):
        return ["no draft text (draft.invite_note / draft.message / draft.followup)"], []
    if lead.get("already_connected") and d.get("invite_note"):
        warns.append("already connected: the invite note will not be used")
    if not lead.get("already_connected") and seq.get("connect_with_note") and not d.get("invite_note"):
        errors.append("sequence.connect_with_note is on but draft.invite_note is empty")
    for k in FIELDS:
        text = d.get(k) or ""
        if not text:
            continue
        limit = seq.get("note_char_limit", 200) if k == "invite_note" else dr.get("message_char_limit", 600)
        if len(text) > limit:
            errors.append(f"{k}: {len(text)} chars, limit {limit}")
        if PLACEHOLDER.search(text):
            errors.append(f"{k}: unfilled placeholder {PLACEHOLDER.search(text).group(0)!r}")
        low = text.lower()
        for b in dr.get("banned_phrases", []):
            if b.lower() in low:
                errors.append(f"{k}: banned phrase {b!r}")
        if k != "followup" and dr.get("require_first_name") and first and first.lower() not in low:
            errors.append(f"{k}: doesn't use their first name ({first})")
        if "http" in low and k == "invite_note":
            warns.append(f"{k}: links in connection notes lower acceptance")
        # voice checks: warnings only, the human decides
        if vp:
            if vp.get("emoji_rate", 0) < 0.05 and EMOJI.search(text):
                warns.append(f"{k}: uses an emoji; your messages almost never do")
            if vp.get("exclaim_per_msg", 0) < 0.2 and text.count("!") >= 2:
                warns.append(f"{k}: {text.count('!')} exclamation marks; you rarely use them")
            if not vp.get("uses_em_dash") and "—" in text:
                warns.append(f"{k}: em dash; you don't use them")
            p90 = (vp.get("length_chars") or {}).get("p90")
            if p90 and k != "invite_note" and len(text) > p90 * 1.6:
                warns.append(f"{k}: {len(text)} chars, much longer than you usually write (p90 {p90})")
            if vp.get("lowercase_start_rate", 0) > 0.6 and text[:1].isupper():
                warns.append(f"{k}: you usually start messages in lowercase")
    hook = lead.get("hook")
    if hook and not any(w.lower() in (d.get("invite_note", "") + d.get("message", "")).lower()
                        for w in re.findall(r"[A-Za-z]{5,}", hook)[:6]):
        warns.append("the personal hook doesn't seem to appear in the note or first message")
    return errors, warns


def load_rows():
    return read_jsonl(LEADS_FILE)


def find(rows, lead_id):
    for r in rows:
        if r["id"] == lead_id:
            return r
    sys.exit(f"no lead {lead_id}")


def review(rows: list[dict], s: dict, status: str) -> Path:
    out = ROOT / "review" / f"review-{now().date().isoformat()}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    picked = [r for r in rows if r.get("status") == status]
    lines = [f"# Review: {len(picked)} leads ({status})", "",
             "Reply in chat like: `approve 1,2,4` · `fix 3: shorter, mention their podcast` · `skip 5: not senior enough`", ""]
    for i, r in enumerate(picked, 1):
        e, w = lint(r, s)
        g = gate(r, s)
        lines += [f"## {i}. {r.get('name')} ({r['id']}), score {r.get('score', '?')}",
                  f"{r.get('role', '?')} @ {r.get('company', '?')} · {r.get('location', '')} · [profile]({r['profile_url']})",
                  f"- Why them: {r.get('why', '')}",
                  f"- Found via: {r.get('source', '')}",
                  f"- Hook: {r.get('hook', '')} ([source]({r.get('hook_source', '')}))"]
        for ev in r.get("evidence", []):
            lines.append(f"- Evidence: {ev.get('claim', '')} ([link]({ev.get('url', '')}))")
        lines.append(f"- Gate: {'PASS' if not g else 'FAIL: ' + '; '.join(g)}")
        d = r.get("draft") or {}
        for k in FIELDS:
            if d.get(k):
                lines += [f"\n**{k}** ({len(d[k])} chars)", "", "> " + d[k].replace("\n", "\n> ")]
        if e:
            lines.append(f"\n- LINT ERRORS: {'; '.join(e)}")
        if w:
            lines.append(f"- Voice notes: {'; '.join(w)}")
        lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("lint"); l.add_argument("id", nargs="?"); l.add_argument("--status")
    rv = sub.add_parser("review"); rv.add_argument("--status", default="drafted")
    ap = sub.add_parser("approve"); ap.add_argument("id"); ap.add_argument("--by", choices=["human", "standing"], required=True)
    tx = sub.add_parser("text"); tx.add_argument("id"); tx.add_argument("field", choices=FIELDS)
    a = p.parse_args()
    s = load_settings()
    rows = load_rows()

    if a.cmd == "lint":
        targets = [find(rows, a.id)] if a.id else [r for r in rows if r.get("status") == (a.status or "drafted")]
        bad = 0
        for r in targets:
            e, w = lint(r, s)
            print(f"{'FAIL' if e else 'OK  '} {r['id']} {r.get('name')}")
            for x in e:
                print(f"   error: {x}")
            for x in w:
                print(f"   voice: {x}")
            bad += bool(e)
        sys.exit(1 if bad else 0)
    if a.cmd == "review":
        print(f"wrote {review(rows, s, a.status)}")
    if a.cmd == "approve":
        r = find(rows, a.id)
        e, _ = lint(r, s)
        g = gate(r, s)
        if e or g:
            sys.exit(f"cannot approve {a.id}: " + "; ".join(e + g))
        if a.by == "standing":
            kind = "invites" if not r.get("already_connected") else "first_messages"
            if not (s.get("standing_approval") or {}).get(kind):
                sys.exit(f"no standing approval for {kind} in settings; the human must approve {a.id}")
        d = r.setdefault("draft", {})
        d["approved_hash"] = draft_hash(d)
        d["approved_by"] = a.by
        d["approved_at"] = iso(now())
        r["status"] = "approved"
        r["approved_at"] = d["approved_at"]
        write_jsonl(LEADS_FILE, rows)
        print(f"approved {a.id} ({a.by}) hash {d['approved_hash']}")
    if a.cmd == "text":
        r = find(rows, a.id)
        d = r.get("draft") or {}
        if not d.get("approved_hash"):
            sys.exit(f"{a.id} is not approved")
        if d["approved_hash"] != draft_hash(d):
            sys.exit(f"{a.id}: the draft changed after approval; get it approved again")
        if not d.get(a.field):
            sys.exit(f"{a.id} has no {a.field}")
        print(d[a.field])


if __name__ == "__main__":
    main()
