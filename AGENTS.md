# Agent instructions

This repo ranks target accounts by merging two kinds of buying signals: the intent export of a third-party intent data provider (Bombora, 6sense, ZoomInfo, G2, Demandbase...) and first-party Sales Navigator account signals (headcount growth, hiring on LinkedIn), exported with Evaboot. It scores every account with the points in `SIGNALS.md`, sorts them into now, next and watch, then exports the buyers at the `now` accounts. The user does the outreach. When the user asks to score intent data, rank accounts by intent, or combine an intent export with Sales Navigator:

1. Follow the skill in `skills/intent-signal-scorer/SKILL.md` step by step.
2. Read `SIGNALS.md` for the account search, the intent topics, the points and the tiers. If it says `Status: EXAMPLE`, ask the user and update it.
3. Use `score.py` to merge, score and write the list. The Evaboot MCP server does the Sales Navigator work (`.mcp.json`).
4. If the user is not connected yet, follow `docs/connect-your-agent.md` with them.
5. If the user wants n8n instead, follow `docs/n8n.md` with them one step at a time: you cannot click inside n8n, so say exactly what to do and wait for their confirmation.

Exports cost 1 Evaboot credit per lead or account. Confirm with the user before every export. Never contact anyone yourself. Never ask for or handle an API key: the user writes it into `.env`. Never commit `.env`, `data/` or `lists/`: they hold real company and people data.
