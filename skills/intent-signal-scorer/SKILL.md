---
name: intent-signal-scorer
description: Rank target accounts by merging a third-party intent data export (Bombora, 6sense, ZoomInfo, G2, Demandbase, Apollo...) with first-party Sales Navigator account signals exported through Evaboot (headcount growth, hiring on LinkedIn), score each account with the points in SIGNALS.md, sort them into now, next and watch, then export the buyers at the now accounts with verified emails. Use when the user asks to score or prioritise intent data, rank accounts by intent, combine an intent export with Sales Navigator, or decide which in-market accounts to work first.
---

# Intent signal scorer

This skill runs inside a clone of https://github.com/evaboot-labs/intent-signal-scorer: it uses the repo's `score.py`, `SIGNALS.md` and `docs/`. If `score.py` is not in the working directory, clone the repo and work from there.

You do the Sales Navigator and Evaboot work through the Evaboot MCP server (`https://mcp.evaboot.com/mcp`). Every tool named below is an Evaboot MCP tool. `score.py` merges, scores and writes the list, the same way every time.

## Rules

- **You never contact anyone.** The list tells the user which accounts to work and who the buyers are; they do the outreach.
- Confirm with the user before every `export_sn_search_or_list`. Show the search and the cost (1 Evaboot credit per exported account or lead), then wait for a yes.
- Never invent intent data. The intent scores come only from the file the user gives you. If they have none, say so and score on Sales Navigator signals only.
- Never ask for or paste an API key. The user writes `EVABOOT_API_KEY` into `.env` and exports it before starting the agent (`docs/connect-your-agent.md`).
- Print every Sales Navigator URL as a Markdown link with the URL in angle brackets: `[Open in Sales Navigator](<url>)`.

## Step 0: check the setup

1. If the Evaboot MCP tools are not in this session, walk the user through `docs/connect-your-agent.md`, then ask them to restart the agent from this folder.
2. Otherwise call `get_daily_export_quota`. If `has_valid_salesnav` is false, ask the user to sign in to Evaboot in Chrome, open any Sales Navigator search with the Evaboot extension, and click Export with Evaboot, then call it again.
3. Run `mkdir -p data lists`.
4. Read `SIGNALS.md`. If it says `Status: EXAMPLE`, ask the user who they sell to (the account search), who the buyers are at those accounts (titles), which intent provider they use and which topics to keep. Rewrite the file and set `Status: yours`.

## Step 1: the intent export

1. Ask the user to download their provider's intent export as CSV (one row per company and topic) and save it as `data/intent-<date>.csv`. `examples/intent-export.csv` shows the shape.
2. Read the header row. `score.py` needs a domain column and a score column; it also reads a topic and a company column. If a column has another name, rename it in the file (see `SIGNALS.md`).

## Step 2: the Sales Navigator account search

1. Build the account search with `build_sn_search_from_prompt`, **companies only**, from `SIGNALS.md`: industry, size, region, headcount growth, and "hiring on LinkedIn". Ask the user how many accounts they want and pass it as `max_results`. When it answers `building`, poll `get_search_build`.
2. Show the URL as a link. If a filter the user asked for is missing from `filters_used`, say so and add it to the URL before exporting.
3. On a yes, export it with `export_sn_search_or_list` and `max_results`, and poll `get_export` with `limit: 0` until it is done. Save it:

```bash
set -a; [ -n "$EVABOOT_API_KEY" ] || . ./.env; set +a
curl -s -H "Authorization: Bearer $EVABOOT_API_KEY" \
  https://api.evaboot.com/v1/extractions/<extraction_id>/ > data/accounts-$(date +%F).json
```

## Step 3: score

```bash
python3 score.py --accounts hiring=data/accounts-$(date +%F).json --intent data/intent-<date>.csv \
  --topics "<topics from SIGNALS.md>" --csv lists/$(date +%F).csv > lists/$(date +%F).md
```

Drop the `hiring=` prefix when the account search had no hiring filter. Show the list: `now` first, with the signals of each account. Point out accounts marked "not in your account search: check fit": the provider sees intent there, but the account is outside the user's search.

## Step 4: the buyers at the now accounts

1. Take the `linkedin` id of each `now` account from the CSV (the number at the end of `https://www.linkedin.com/company/<id>`).
2. Build a people search with `build_sn_search_from_prompt` for the titles in the "Your buyers" section of `SIGNALS.md`. Company names often do not resolve, so add the companies yourself: put this filter first in the URL's filter list, one `(id:...)` per account:
   `(type%3ACURRENT_COMPANY%2Cvalues%3AList((id%3Aurn%253Ali%253Aorganization%253A<id>%2CselectionType%3AINCLUDED)))%2C`
3. Show the link so the user can check the count, then on a yes export it with a small `max_results` (10 to start) and save it as `data/buyers-$(date +%F).json`.
4. List the buyers per account: name, title, verified (`safe`) email or LinkedIn. For each, suggest one opening line from the account's signals only, never from the intent topic itself (the buyer does not know you see their research).

## Every week

Most providers refresh intent weekly. Each week: a new intent export, scored against the same account export, then steps 3 and 4. Export the account search again about once a month, after the user agrees to the cost, so growth and new accounts stay current. Do not use a recurring export here: its runs hold only the accounts new to the search, not the whole list. Or set up the n8n version (`docs/n8n.md`), which writes the ranked accounts to a Google Sheet.
