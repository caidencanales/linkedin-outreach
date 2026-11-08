# Claude in Chrome: working notes

## Setup
- Install the Claude in Chrome extension, sign in, and connect it to Claude Code (in the desktop app, the Chrome connector; in the terminal, `claude --chrome` or `/chrome`).
- Sign in to LinkedIn yourself in that Chrome profile. Claude never types your password.
- Load the tools in one go at the start of a session (ToolSearch with `select:` and a comma-separated list): `tabs_context_mcp, tabs_create_mcp, navigate, computer, get_page_text, read_page, find`.

## Habits that keep sessions stable
- **Short steps.** Keep each browser call under about 40 seconds. Long chained batches can drop the connection mid-way. If one drops, don't repeat the action blindly: check the page (was the invite or message actually sent?) before doing anything else.
- **One LinkedIn tab.** Reuse it. Don't open profiles in parallel.
- **Read with text tools.** `get_page_text` for profiles and conversations, `read_page` or `find` to locate buttons. Screenshots only when a layout question can't be answered from text.
- **Wait for the page.** After `navigate`, wait 2–4 seconds before reading. LinkedIn loads sections lazily, so scroll the Experience or Activity section into view if it's missing.
- **Don't put personal data in URLs** you build yourself (search queries with emails, and so on).
- **No internal APIs.** Don't run JavaScript that calls LinkedIn's private endpoints or scrapes the DOM in bulk. Read what's on screen, like a person would.

## Sending in assisted mode
1. Open the profile URL from the lead row and confirm the name and headline on the page match.
2. Connect (it may sit under "More") > Add a note, or Message.
3. Paste the exact output of `python tools/drafts.py text <id> <field>`.
4. Read the text box back and compare it to the approved text. If anything differs, stop.
5. Click Send once. Then `pace.py log` right away.
If a "How do you know this person?" or email-required dialog appears, stop and mark the lead for human handling: some people only accept invites from people who know their email.

## When Claude is blocked
Claude Code's permission checks (especially in auto mode) may block sending messages on your behalf. That's expected. Don't look for a way around it: use `send_mode: human`, where Claude writes `review/to-send.md` and you paste and send, then tell Claude "sent 1–5" so it logs them.
