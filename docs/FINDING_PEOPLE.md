# Finding the right people, and proving they're real

The plan prompt turns this into your own `docs/SOURCING_PLAN.md`. Everything here is read-only browsing, one page at a time, the way you'd do it yourself.

## Where good leads come from (warmest first)

1. **Seed audiences.** Seeds are the people, creators and companies whose world overlaps yours. Open a seed's recent posts (profile > Activity > Posts) and read who comments thoughtfully. Commenters are active, interested in the topic, and give you a natural hook ("your comment on X's post about Y"). Reactions are weaker than comments.
2. **Seed networks.** People the seeds work with, feature, invest in, hire or host: co-founders, podcast guests, portfolio companies, speakers at their events, people they tag.
3. **Lookalikes.** "People also viewed" and "More profiles for you" on a strong lead's or seed's profile, and the same roles at similar companies.
4. **Search.** LinkedIn people search with filters (title, location, industry, current company, school), or Sales Navigator if you have it. Read results page by page. Don't export or scrape them in bulk.
5. **Signals outside LinkedIn.** Funding announcements, accelerator batch pages, conference speaker lists, podcast guest lists, award lists, job posts ("hiring a first X"), GitHub or Product Hunt launches. Find the person there, then find their LinkedIn profile.
6. **Your own network.** 2nd-degree connections who share a mutual connection (ask the mutual for an intro instead of a cold invite when it matters), and 1st-degree connections who fit but you've never messaged.

Log how each lead was found in `source` (with the URL) and which seed in `seed`, so you can later see which sources reply best.

## Verification: every lead, before any draft

A lead must pass `python tools/leads.py gate <id>`. The default checks (turn them on or off in `settings.verification`):

| Check | How to verify | Field |
|---|---|---|
| Profile opened in the browser | Visit the profile (log a `view`) | `checks.profile_opened_at` |
| Current role and company | From the Experience section on the profile, not a stale search snippet | `role`, `company` |
| Second, non-LinkedIn source | Company team page, press, publication, conference page, personal site, Crunchbase-style page | `evidence[]` with `claim` + `url` |
| Active recently | Latest post or comment, or a recent job change, within `max_days_since_active` | `checks.last_active` |
| Real person | Real photo, connections over the minimum, a work history that makes sense, no signs of a fake or bot | `checks.has_photo`, `checks.connections`, `checks.red_flags` |
| Personal hook | Something real and specific they wrote, built, said or did, with its URL | `hook`, `hook_source` |
| Not already contacted | `leads.py exists <url>`, the do-not-contact list, and the message history on the profile | automatic |

Red flags (record them in `checks.red_flags` and skip): stock or AI-generated photo, a brand-new profile with few connections, a job history that contradicts the company site, "open to work" when you're selling to decision makers, recruiter or agency spam, students or minors when your ICP is executives, anyone who has asked people not to cold-message them.

## Scoring
Score each lead 0–100 with the rubric you agreed on in `ICP.md`. A typical split: fit with the ICP 40, timing or signal 20, hook quality 15, reachability (mutuals, shared seed, open DMs) 15, seniority or influence 10. Draft only above your bar. Record the reasons in `why`.

## Never
- Guess emails or phone numbers, or pull contact details that aren't publicly listed by the person.
- Collect sensitive data (health, religion, politics, home address, family).
- Contact minors, or anyone on the do-not-contact list.
- Use scripts against LinkedIn's internal APIs, or open many profiles in parallel.
