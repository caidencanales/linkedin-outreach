# Sounding like you

Messages work when they read like you wrote them to one person. The system learns your voice once, from your own last 100 sent LinkedIn messages, then checks every draft against it.

## 1. Collect your last 100 sent messages
- **Preferred: LinkedIn's data export.** Settings & Privacy > Data privacy > Get a copy of your data > select **Messages** > Request archive. LinkedIn emails you a link (usually within minutes to a day). Unzip it and run
  `python tools/voice.py csv path/to/messages.csv --me "Your Name"` (your name exactly as in the `FROM` column; the tool lists the most common senders if it doesn't match).
- **Or: Claude in Chrome, read-only.** Claude opens your conversations one at a time, newest first, and copies only the messages *you* wrote into `voice/collected.txt`, separated by lines of `---`, then runs `python tools/voice.py text voice/collected.txt`.

Either way, only your own messages are kept, and only inside `voice/`, which git never commits.

## 2. What the tool measures
`voice/voice_profile.json`: message length (10th percentile, median, 90th), sentences per message, emoji use, exclamation marks, question rate, em dashes, starting in lowercase, line breaks, common openers and closers, words and phrases you use a lot.

## 3. The style guide Claude writes
`voice/VOICE.md` is plain language: how you open and close, sentence length, punctuation and capitalization, phrases you use and phrases you'd never use, how you write to strangers vs. people you know, and five "sounds like me / doesn't" pairs. You correct it until it's right.

## 4. How it's used
- Every draft is written from `voice/VOICE.md` and `templates.md`.
- `python tools/drafts.py lint` flags drafts that don't match: emoji when you never use them, too many exclamation marks, em dashes you don't use, much longer than you usually write, capitalized when you usually start lowercase.
- Hard limits are errors: note length, unfilled placeholders, banned phrases, a missing first name.

## Defaults that help most people
One idea per message. A first line that's about them and could only be sent to them. One easy ask. No link in the connection note. No "hope this finds you well", "quick question", "pick your brain" or fake familiarity.
