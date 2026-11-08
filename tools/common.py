"""Shared paths, settings and small helpers. Standard library only.

Every tool reads its working folder from the LIO_HOME environment variable
(default: the repo root). Your real data lives in LIO_HOME/data and
LIO_HOME/voice, which .gitignore keeps out of git.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(os.environ.get("LIO_HOME") or Path(__file__).resolve().parent.parent)
DATA = ROOT / "data"
VOICE = ROOT / "voice"
CONFIG = ROOT / "config"
SETTINGS_FILE = CONFIG / "settings.json"
SETTINGS_EXAMPLE = CONFIG / "settings.example.json"
LEADS_FILE = DATA / "leads.jsonl"
ACTIONS_FILE = DATA / "actions.jsonl"
STATE_FILE = DATA / "state.json"
STOP_FILE = DATA / "STOP"

# Actions that put something in front of another person. They share the hourly cap and the gap.
SEND_ACTIONS = {"invite", "message", "followup", "reply", "inmail"}
ALL_ACTIONS = SEND_ACTIONS | {"view"}


def now() -> datetime:
    """Local time, naive. Override with LIO_NOW=2026-01-05T10:00:00 for tests."""
    fake = os.environ.get("LIO_NOW")
    return datetime.fromisoformat(fake) if fake else datetime.now().replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def load_settings() -> dict:
    path = SETTINGS_FILE if SETTINGS_FILE.exists() else SETTINGS_EXAMPLE
    if not path.exists():
        sys.exit(f"No settings found. Copy {SETTINGS_EXAMPLE} to {SETTINGS_FILE} and fill it in.")
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    tier = s.get("aggressiveness", "careful")
    tiers = s.get("tiers", {})
    if tier not in tiers:
        sys.exit(f"settings.aggressiveness is '{tier}' but tiers has no such entry: {list(tiers)}")
    s["_limits"] = dict(tiers[tier])
    s["_limits"].update(s.get("limit_overrides") or {})
    s["_path"] = str(path)
    return s


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"{path}:{n} is not valid JSON ({e}). Fix that line first.")
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_state() -> dict:
    if STATE_FILE.exists():
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


_SLUG = re.compile(r"linkedin\.com/(in|company|school)/([^/?#\s]+)", re.I)


def normalize_profile_url(url: str) -> str | None:
    """https://www.linkedin.com/in/Jane-Doe-123/?trk=x -> https://www.linkedin.com/in/jane-doe-123"""
    if not url:
        return None
    m = _SLUG.search(url)
    if not m:
        return None
    return f"https://www.linkedin.com/{m.group(1).lower()}/{m.group(2).lower().rstrip('/')}"


def start_of_week(dt: datetime) -> datetime:
    d = dt - timedelta(days=dt.weekday())
    return d.replace(hour=0, minute=0, second=0, microsecond=0)
