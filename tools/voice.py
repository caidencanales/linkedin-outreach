"""Learn how you write from your own last 100 sent LinkedIn messages.

Two ways to get them (PLAN_PROMPT.md asks which you prefer):

  A. LinkedIn's own data export (safest, no browsing): Settings > Data privacy >
     Get a copy of your data > Messages. Unzip it and pass messages.csv:
        python tools/voice.py csv path/to/messages.csv --me "Your Name"
  B. Claude in Chrome reads your sent messages on linkedin.com/messaging (read-only)
     and saves each one you wrote into voice/collected.txt, separated by lines of ---:
        python tools/voice.py text voice/collected.txt

Writes (all git-ignored):
  voice/samples.md         your last N messages, newest first, for Claude to study
  voice/voice_profile.json the numbers drafts.py checks against (length, emoji, !, greetings, sign-offs)
Claude then writes voice/VOICE.md, a plain-language style guide, from both.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter

sys.path.insert(0, __import__("os").path.dirname(__file__))
from common import VOICE, normalize_profile_url

EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")
WORD = re.compile(r"[a-z']+")


def col(row: dict, *names: str) -> str:
    low = {k.strip().lower(): v for k, v in row.items() if k}
    for n in names:
        if n in low and low[n] is not None:
            return low[n]
    return ""


def from_csv(path: str, me: str | None, me_url: str | None, limit: int) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    me_l = (me or "").strip().lower()
    me_u = normalize_profile_url(me_url) if me_url else None
    mine = []
    for r in rows:
        sender = col(r, "from", "sender").strip().lower()
        surl = normalize_profile_url(col(r, "sender profile url"))
        text = col(r, "content", "body", "message").strip()
        if not text:
            continue
        if (me_u and surl == me_u) or (me_l and sender == me_l):
            mine.append({"date": col(r, "date"), "to": col(r, "to"), "text": text})
    if not mine:
        senders = Counter(col(r, "from") for r in rows).most_common(5)
        sys.exit(f"No messages matched you. Most common senders: {senders}. Pass --me exactly as one of those.")
    mine.sort(key=lambda m: m["date"], reverse=True)
    return mine[:limit]


def from_text(path: str, limit: int) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        blocks = [b.strip() for b in re.split(r"^\s*---\s*$", f.read(), flags=re.M)]
    return [{"date": "", "to": "", "text": b} for b in blocks if b][:limit]


def first_line_opener(t: str) -> str:
    w = WORD.findall(t.lower()[:40])
    return " ".join(w[:2]) if w else ""


def closer(t: str) -> str:
    last = t.strip().splitlines()[-1].strip().lower() if t.strip() else ""
    return last if len(last) <= 30 else ""


def profile(msgs: list[dict]) -> dict:
    texts = [m["text"] for m in msgs]
    lens = sorted(len(t) for t in texts)
    q = lambda p: lens[min(len(lens) - 1, int(p * len(lens)))]
    words = Counter(w for t in texts for w in WORD.findall(t.lower()))
    bigrams = Counter()
    for t in texts:
        ws = WORD.findall(t.lower())
        bigrams.update(" ".join(ws[i:i + 2]) for i in range(len(ws) - 1))
    return {
        "messages_analyzed": len(texts),
        "length_chars": {"p10": q(0.1), "median": int(statistics.median(lens)), "p90": q(0.9)},
        "sentences_per_msg": round(statistics.mean(max(1, len(re.findall(r"[.!?]+", t))) for t in texts), 1),
        "emoji_rate": round(sum(bool(EMOJI.search(t)) for t in texts) / len(texts), 2),
        "exclaim_per_msg": round(sum(t.count("!") for t in texts) / len(texts), 2),
        "question_rate": round(sum("?" in t for t in texts) / len(texts), 2),
        "uses_em_dash": sum("—" in t for t in texts) / len(texts) > 0.1,
        "lowercase_start_rate": round(sum(t[:1].islower() for t in texts) / len(texts), 2),
        "line_breaks_per_msg": round(sum(t.count("\n") for t in texts) / len(texts), 1),
        "top_openers": Counter(first_line_opener(t) for t in texts).most_common(8),
        "top_closers": [c for c in Counter(closer(t) for t in texts).most_common(8) if c[0]],
        "top_words": [w for w, _ in words.most_common(60) if len(w) > 3][:30],
        "top_phrases": [b for b, n in bigrams.most_common(40) if n >= 3][:20],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("csv"); c.add_argument("file"); c.add_argument("--me"); c.add_argument("--me-url")
    c.add_argument("--limit", type=int, default=100)
    t = sub.add_parser("text"); t.add_argument("file"); t.add_argument("--limit", type=int, default=100)
    a = p.parse_args()
    if a.cmd == "csv":
        if not (a.me or a.me_url):
            sys.exit("pass --me \"Your Name\" (as it appears in the FROM column) or --me-url")
        msgs = from_csv(a.file, a.me, a.me_url, a.limit)
    else:
        msgs = from_text(a.file, a.limit)
    VOICE.mkdir(parents=True, exist_ok=True)
    prof = profile(msgs)
    with open(VOICE / "voice_profile.json", "w", encoding="utf-8") as f:
        json.dump(prof, f, indent=2, ensure_ascii=False)
    with open(VOICE / "samples.md", "w", encoding="utf-8") as f:
        f.write(f"# Your last {len(msgs)} sent LinkedIn messages (private; git-ignored)\n\n")
        for m in msgs:
            f.write(f"---\n{m['date']}\n\n{m['text']}\n\n")
    print(json.dumps(prof, indent=2, ensure_ascii=False))
    print(f"\nwrote {VOICE / 'voice_profile.json'} and {VOICE / 'samples.md'} from {len(msgs)} messages")


if __name__ == "__main__":
    main()
