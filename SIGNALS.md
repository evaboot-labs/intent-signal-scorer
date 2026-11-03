# Your accounts, your intent topics, and the points

Status: EXAMPLE. Your agent asks you and replaces this line with "Status: yours" once the file is yours.

## Who you sell to (the account search)

Software companies in the United Kingdom, 51 to 200 employees, headcount growth of 10% or more, hiring on LinkedIn.

**Not a fit:** agencies, consultancies and outsourcing firms.

## Your buyers (the people search at the `now` accounts)

CRO, Chief Revenue Officer, founders and co-founders, Head of Growth, and VPs, heads and directors of Sales, Revenue or Business Development. Not: assistants, analysts, interns and freelancers.

## Your intent export

| Field | Value |
|---|---|
| Provider | Bombora Company Surge (any provider works: 6sense, ZoomInfo, G2, Demandbase...) |
| Topics to keep | Sales Intelligence, Lead Generation, Sales Prospecting |
| File | `data/intent-<date>.csv`, one row per company and topic |

`score.py` reads the columns by name. It finds the domain in `Domain`, `Company Domain` or `Website`, the topic in `Topic`, `Topic Name` or `Intent Topic`, and the score in `Score`, `Composite Score`, `Intent Score` or `Intent Strength`. Rename a column if your provider uses another name.

## Points

Start here, then check your closed deals: raise what shows up in wins, lower what shows up in losses.

| Signal | Points |
|---|---|
| `intent_surge` | 10 |
| `intent_extra_topic` | 3 |
| `fast_growth` | 6 |
| `fit` | 5 |
| `recent_growth` | 4 |
| `hiring` | 3 |

- `intent_surge`: at least one of your topics at or above `surge_threshold` in the intent export.
- `intent_extra_topic`: each more surging topic, up to `max_extra_topics`.
- `fit`: the account is in your Sales Navigator account search.
- `hiring`: the search had the "Hiring on LinkedIn" filter (pass the export as `hiring=<file>`).
- `fast_growth` and `recent_growth`: headcount growth in a year and in 6 months, from the Evaboot export.

## Settings

| Setting | Value |
|---|---|
| `surge_threshold` | 60 |
| `max_extra_topics` | 2 |
| `fast_growth_pct` | 30 |
| `recent_growth_pct` | 15 |
| `tier_now` | 20 |
| `tier_next` | 10 |

## Tiers

| Score | Tier | Do |
|---|---|---|
| `tier_now` (20) or more | `now` | export the buyers at the account and reach out this week |
| `tier_next` (10) or more | `next` | add to next week's list; check again on the next intent export |
| below | `watch` | no outreach yet; wait for a stronger signal |

An account found only in the intent export gets no `fit` points and is marked "check the account fits".
