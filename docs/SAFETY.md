# Safety: pace, limits, warnings

## Be honest about the risk first
LinkedIn's User Agreement prohibits bots and other automated ways of using the site, and that includes a browser agent clicking for you. LinkedIn can warn, limit or restrict accounts that act in automated-looking ways. This kit lowers the risk; it doesn't remove it:
- a human approves what goes out (and, in `human` mode, clicks Send),
- actions are spread out at a pace a busy person could plausibly keep,
- every warning stops the system until a human looks.

If your LinkedIn account matters a lot to you, use `careful` and `human` mode, and treat everything here as a drafting and research assistant.

LinkedIn doesn't publish exact limits, and they change. The numbers below are conservative choices, not LinkedIn's official figures. Check LinkedIn's Help Center for your own account.

## What LinkedIn roughly allows (as reported in 2026)
- **Invitations:** a weekly cap, commonly reported at about 100–200 a week depending on the account. The cap can't be bypassed, and many pending invites plus low acceptance draws scrutiny.
- **Personalized notes on free accounts:** only a few per month (reports range from 3 to about 10; 5 is most common), up to about 200 characters. Premium removes the monthly note cap but **not** the weekly invite cap.
- **Messages to 1st-degree connections:** no fixed published cap, but bursts of near-identical messages are what get flagged.

## The three tiers (`aggressiveness` in settings)

| | careful | standard | aggressive |
|---|---|---|---|
| Invites per day / week | 10 / 50 | 20 / 80 | 25 / 120 |
| Messages per day | 15 | 30 | 50 |
| Profile views per day | 40 | 80 | 150 |
| Sends per rolling hour | 5 | 8 | 12 |
| Minimum gap between sends | 8 min (+0–6) | 4 min (+0–4) | 2.5 min (+0–3) |
| Actions per loop tick | 1 | 2 | 3 |
| Max pending invites | 300 | 400 | 500 |
| Pause invites if acceptance falls below | 25% | 20% | 15% |
| Cooldown after a warning (once a human clears it) | 7 days | 3 days | 2 days |

Plus, for every tier:
- **Ramp:** from `ramp.start_date`, weeks 1, 2 and 3+ run at 50%, 75% and 100% of the tier's caps. Use it for new accounts, quiet accounts, and anyone moving up a tier.
- **Active hours and days only** (default weekdays 9:00–18:00, local time, with a lunch pause).
- **Kill switch:** if the file `data/STOP` exists, every check says STOP.

`limit_overrides` in settings can change single numbers. The plan prompt never sets them above the aggressive tier.

## Warnings: what always happens
At **any** tier, if LinkedIn shows a CAPTCHA, "verify it's you", "unusual activity", a restriction notice, the invitation limit, "sending too fast", or a security prompt:
1. Claude stops at once and runs `python tools/pace.py warn "<what it said>"`.
2. Every check returns STOP until **you** look at LinkedIn yourself and run `python tools/pace.py clear --i-checked-linkedin`.
3. Then the tier's cooldown runs before anything is sent again.
4. Consider moving down a tier, and withdraw old pending invites by hand (My Network > Manage > Sent).

Claude never solves CAPTCHAs or clicks through security prompts.

## What else keeps an account healthy
- Personal, specific messages. Templates are patterns, not copy-paste.
- High acceptance: target people who have a reason to say yes (shared seed, shared topic, a real hook).
- Few pending invites: withdraw any that are older than about 3 weeks.
- A complete profile, and some normal activity of your own (posting, commenting) alongside outreach.
- One browser, one tab, normal hours. No parallel sessions, no running from several machines.
