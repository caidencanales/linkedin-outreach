# linkedin-outreach

A kit for running your own LinkedIn outreach with **Claude Code + Claude in Chrome**: it finds the right people, proves they're real, writes to each one in *your* voice, and sends at a pace that keeps your account safe, with you approving what goes out.

It works in two steps:

1. **[PLAN_PROMPT.md](PLAN_PROMPT.md): the interview.** Claude asks you a long series of questions: what you're really trying to achieve, who you want to reach, whose audience overlaps yours, what you offer, how much account risk you'll accept, what should happen when LinkedIn warns you, how the sequence runs, and who clicks Send. It reads your last 100 sent LinkedIn messages to learn how you write. Then it writes your settings, ideal-lead profile, sourcing plan, voice guide and templates, and does a dry run of 10 leads.
2. **[LOOP_PROMPT.md](LOOP_PROMPT.md): the loop.** Run with `/loop`, it checks replies and accepts, keeps a pipeline of verified leads, drafts messages, sends approved ones one at a time inside the pace limits, reports, and schedules its own next wakeup.

```
interview ─> voice ─> plan ─> dry run ─> loop: [safety check → read replies → find + verify → draft → you approve → paced send → report] ↺
```

## Before you start: read [docs/SAFETY.md](docs/SAFETY.md)
LinkedIn's User Agreement prohibits bots and automated activity, and accounts that look automated can be restricted. This kit is built to keep a human in charge (approval on everything by default, a `human` send mode where you click Send), to move slowly (hourly, daily and weekly caps, minimum gaps, a ramp, active hours only), and to **stop completely on any LinkedIn warning** until you check. You choose how careful to be, and you carry the risk for your account.

## What's in the box

| Path | What it does |
|---|---|
| `PLAN_PROMPT.md` | Paste into Claude Code in plan mode: interview, voice, setup, dry run |
| `LOOP_PROMPT.md` | Paste after `/loop`: the recurring outreach loop |
| `CLAUDE.md` | Hard rules Claude follows in this folder |
| `tools/pace.py` | Pace guard: per-hour, day and week caps, spacing with jitter, active hours, ramp, acceptance-rate and pending-invite brakes, warning cooldowns, kill switch |
| `tools/leads.py` | Lead store: dedupe by profile URL, verification gate, pipeline status, do-not-contact list, what's due next |
| `tools/drafts.py` | Draft lint (note length, placeholders, banned phrases, voice match), review sheet, approval locked to the exact text |
| `tools/voice.py` | Builds your voice profile from your last 100 sent messages (LinkedIn data export or read in Chrome) |
| `tools/report.py` | Today and this week: sends, accepts, replies, what's waiting on you |
| `tools/selftest.py` | Runs every tool on fake data |
| `docs/` | `SAFETY` · `FINDING_PEOPLE` (sourcing + verification) · `VOICE` · `CHROME` (browser habits) |
| `config/settings.example.json` | Every setting, with the three tiers |
| `examples/` | Fake leads and a fake messages export in the real formats |

Python 3.9+ with only the standard library. Nothing to install besides Claude Code and the Claude in Chrome extension.

## Quick start
```bash
git clone https://github.com/<owner>/linkedin-outreach.git
cd linkedin-outreach
python tools/selftest.py
```
Then open Claude Code in this folder, switch to plan mode, and paste [PLAN_PROMPT.md](PLAN_PROMPT.md).

Handy commands:
```bash
python tools/pace.py status          # caps used, next allowed send, warnings
python tools/leads.py list --status drafted
python tools/drafts.py review        # writes review/review-<date>.md
python tools/report.py
```
Emergency stop: create a file named `data/STOP`.

## Your data stays local
`config/settings.json`, `data/`, `voice/` and `review/` are in `.gitignore`. They hold your leads, your messages and your voice samples. Don't commit them, and don't push a fork that includes them.

## License
MIT
