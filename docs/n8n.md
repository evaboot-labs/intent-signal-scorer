# Run it in n8n

[`n8n/intent-signal-scorer.json`](../n8n/intent-signal-scorer.json) is the same ranking for n8n. Every Monday at 8 it reads your Evaboot export of your Sales Navigator account search, reads your intent export from a CSV link, scores every account like `score.py`, and appends the list to a Google Sheet. No AI model and no AI key: the scoring is a Code node.

## What runs

1. **Your settings** (Edit Fields): the export's id, the CSV link, your topics, the sheet, the points.
2. **Get the accounts** (Evaboot MCP `get_export`): the accounts with their domain and headcount growth.
3. **Intent export** (HTTP Request) and **Read the CSV**: your provider's rows, from the CSV link.
4. **Score and tier** (Code): both matched by domain, scored with `points` and `settings`, one row per account, best score first.
5. **Add to Accounts** (Google Sheets): the rows, dated, in your Accounts tab.

## Set it up

1. **The account export:** ask your agent (Evaboot MCP) to export your Sales Navigator account search, and note its `extraction_id`. Export it again about once a month, so growth and new accounts stay current, and paste the new id.
2. **The intent CSV link:** put your provider's export in a Google Sheet tab, then *File > Share > Publish to web*, that tab, *Comma-separated values (.csv)*. Or use any link that returns the CSV. Replace the rows each week with the new export.
3. **The output sheet:** a tab named `Accounts` with this header row: `Date, Tier, Score, Company, Domain, Signals, Intent topics, Growth 1y %, Growth 6m %, Employees, LinkedIn, Action`.
4. **Import** the JSON in n8n: *Workflows > Import from file*.
5. **Add two credentials:**
   - **Bearer Auth** with your Evaboot API key ([dash.evaboot.com/dash/api/](https://dash.evaboot.com/dash/api/)), on Get the accounts.
   - **Google Sheets**, on Add to Accounts.
6. **Fill in Your settings:** `accounts_extraction_id`, `intent_csv_url`, `topics` (empty keeps every topic), `accounts_tab_url` (with its `gid`), and `search_has_hiring_filter` (`yes` when the search has the "Hiring on LinkedIn" filter). `points` and `settings` hold the same values as `SIGNALS.md`.
7. **Test:** click **Execute workflow**, then read the Accounts tab. Then **Publish** so it runs every Monday.

## Good to know

- The workflow reads an export that already ran: it spends no credits. Each monthly re-export spends 1 credit per account.
- Do not point it at a recurring export: each recurring run holds only the accounts new to the search, not the whole list.
- The buyers at the `now` accounts are one more export: ask your agent (step 4 of the skill), or add a people search with those company ids.
- Most intent providers refresh weekly. Run the workflow after your provider's refresh day.

Back to the [README](../README.md).
