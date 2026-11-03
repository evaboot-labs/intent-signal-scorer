"""Builds n8n/intent-signal-scorer.json. Run: python3 n8n/build_workflow.py

Every Monday: read your Evaboot export of your Sales Navigator account search (by its extraction id, the whole
search, re-exported about once a month), read your intent provider's export from a CSV link, match both by domain, score every account like score.py and
append the ranked accounts to a Google Sheet. No AI model: the scoring is a Code node.
"""
import json
import uuid
from pathlib import Path

EVABOOT_MCP = "https://mcp.evaboot.com/mcp"
EVABOOT_CRED = {"httpBearerAuth": {"id": "", "name": "Evaboot MCP (Bearer)"}}
SHEETS_CRED = {"googleSheetsOAuth2Api": {"id": "", "name": "Google Sheets account"}}
# Keep in step with SIGNALS.md.
POINTS = {"intent_surge": 10, "intent_extra_topic": 3, "fast_growth": 6, "fit": 5, "recent_growth": 4, "hiring": 3}
SETTINGS = {"surge_threshold": 60, "max_extra_topics": 2, "fast_growth_pct": 30, "recent_growth_pct": 15,
            "tier_now": 20, "tier_next": 10}

nodes, connections = [], {}


def node(name, type_, version, params, pos, creds=None, **extra):
    n = {"parameters": params, "id": str(uuid.uuid4()), "name": name, "type": type_,
         "typeVersion": version, "position": pos, **extra}
    if creds:
        n["credentials"] = creds
    nodes.append(n)


def link(a, b):
    connections.setdefault(a, {}).setdefault("main", [[]])[0].append({"node": b, "type": "main", "index": 0})


def mcp_call(name, tool, json_expr, pos):
    node(name, "@n8n/n8n-nodes-langchain.mcpClient", 1.1, {
        "endpointUrl": EVABOOT_MCP, "authentication": "bearerAuth",
        "tool": {"__rl": True, "mode": "list", "value": tool, "cachedResultName": tool},
        "inputMode": "json", "jsonInput": json_expr, "options": {"timeout": 120000},
    }, pos, EVABOOT_CRED)


def code(name, js, pos, **extra):
    node(name, "n8n-nodes-base.code", 2, {"jsCode": js}, pos, **extra)


SCORE_JS = r"""
// Same as score.py: match the intent rows and the Sales Navigator accounts by domain, score, tier.
const s = $('Your settings').first().json;
const P = JSON.parse(s.points), S = JSON.parse(s.settings);
const topicsWanted = String(s.topics || '').split(',').map(t => t.trim().toLowerCase()).filter(Boolean);
const num = v => { const n = parseFloat(String(v ?? '').replace(/[,%]/g, '')); return isNaN(n) ? null : n; };
const NOT_A_DOMAIN = new Set(['linktr.ee', 'linkedin.com', 'bit.ly', 'facebook.com', 'google.com']);
const domainOf = v => {
  let x = String(v || '').trim().toLowerCase();
  if (!x) return '';
  x = x.replace(/^[a-z]+:\/\//, '').split(/[/?#:]/)[0].replace(/^(www\d?|get|go|app)\./, '');
  return NOT_A_DOMAIN.has(x) ? '' : x;
};
const pick = (row, names) => { const k = Object.keys(row).find(h => names.includes(h.toLowerCase().trim())); return k ? row[k] : ''; };

// Intent rows -> {domain: {company, topics}}
const intent = {};
for (const { json: r } of $('Read the CSV').all()) {
  const d = domainOf(pick(r, ['domain', 'company domain', 'website', 'company website', 'company_domain']));
  const score = num(pick(r, ['score', 'composite score', 'intent score', 'surge score', 'intent strength', 'signal score']));
  const topic = String(pick(r, ['topic', 'topic name', 'intent topic', 'keyword', 'category']) || 'intent').trim();
  if (!d || score === null || (topicsWanted.length && !topicsWanted.includes(topic.toLowerCase()))) continue;
  const a = intent[d] ??= { company: String(pick(r, ['company', 'company name', 'account', 'account name', 'company_name']) || ''), topics: {} };
  a.topics[topic] = Math.max(score, a.topics[topic] || 0);
}

// Sales Navigator accounts from the Evaboot export
const accounts = {};
for (const a of $('Get the accounts').first().json.structuredContent?.result?.prospects || []) {
  if (String(a['Matches Filters'] || 'match').toLowerCase() === 'no_match') continue;
  const d = domainOf(a['Company Domain']) || domainOf(a['Company Website URL']);
  accounts[d || 'name:' + String(a['Company Name']).toLowerCase()] ??= { raw: a, domain: d };
}

const TIERS = [[S.tier_now, 'now', 'export the buyers and reach out this week'],
               [S.tier_next, 'next', "add to next week's list"], [-Infinity, 'watch', 'wait for a stronger signal']];
const today = new Date().toISOString().slice(0, 10);
const keys = [...Object.keys(accounts), ...Object.keys(intent).filter(d => !accounts[d])];
return keys.map(key => {
  const acc = accounts[key], raw = acc ? acc.raw : {}, domain = acc ? acc.domain : key;
  const signals = []; let total = 0;
  const surging = Object.entries(intent[domain]?.topics || {}).filter(([, v]) => v >= S.surge_threshold).sort((a, b) => b[1] - a[1]);
  if (surging.length) {
    total += P.intent_surge + Math.min(surging.length - 1, S.max_extra_topics) * P.intent_extra_topic;
    signals.push(`intent surge on ${surging.length} topic${surging.length > 1 ? 's' : ''}`);
  }
  if (acc) {
    total += P.fit; signals.push('fits your account search');
    if (s.search_has_hiring_filter === 'yes') { total += P.hiring; signals.push('hiring on LinkedIn'); }
  }
  const g1 = num(raw['Company Employee Growth 1 Year (%)']), g6 = num(raw['Company Employee Growth 6 Months (%)']);
  if (g1 !== null && g1 >= S.fast_growth_pct) { total += P.fast_growth; signals.push(`headcount +${Math.round(g1)}% in a year`); }
  if (g6 !== null && g6 >= S.recent_growth_pct) { total += P.recent_growth; signals.push(`headcount +${Math.round(g6)}% in 6 months`); }
  let [, tier, action] = TIERS.find(t => total >= t[0]);
  if (!acc) { action = 'intent only: check the account fits'; signals.push('not in your account search: check fit'); }
  return { json: {
    'Date': today, 'Tier': tier, 'Score': total,
    'Company': raw['Company Name'] || intent[domain]?.company || domain, 'Domain': domain,
    'Signals': signals.join(', ') || 'none', 'Intent topics': surging.map(([t, v]) => `${t} ${v}`).join('; '),
    'Growth 1y %': g1 ?? '', 'Growth 6m %': g6 ?? '', 'Employees': raw['Company Employee Exact Count'] || '',
    'LinkedIn': raw['Company Linkedin URL Unique ID'] || '', 'Action': action,
  } };
}).sort((a, b) => b.json.Score - a.json.Score || String(a.json.Company).localeCompare(String(b.json.Company)));
"""

node("Every Monday at 8", "n8n-nodes-base.scheduleTrigger", 1.2, {"rule": {"interval": [
    {"field": "cronExpression", "expression": "0 8 * * 1"}]}}, [0, 0])
node("Your settings", "n8n-nodes-base.set", 3.4, {"assignments": {"assignments": [
    {"id": str(uuid.uuid4()), "name": k, "type": "string", "value": v} for k, v in [
        ("accounts_extraction_id", "PASTE_THE_EXTRACTION_ID_OF_YOUR_ACCOUNT_EXPORT"),
        ("search_has_hiring_filter", "yes"),
        ("intent_csv_url", "PASTE_THE_CSV_LINK_OF_YOUR_INTENT_EXPORT"),
        ("topics", "Sales Intelligence, Lead Generation, Sales Prospecting"),
        ("accounts_tab_url", "PASTE_THE_ACCOUNTS_TAB_URL_WITH_GID"),
        ("points", json.dumps(POINTS)),
        ("settings", json.dumps(SETTINGS)),
    ]]}, "options": {}}, [220, 0])
mcp_call("Get the accounts", "get_export",
         "={{ JSON.stringify({ extraction_id: $('Your settings').first().json.accounts_extraction_id }) }}", [440, 0])
node("Intent export", "n8n-nodes-base.httpRequest", 4.2, {
    "url": "={{ $('Your settings').first().json.intent_csv_url }}",
    "options": {"response": {"response": {"responseFormat": "file"}}},
}, [660, 0])
# An empty intent file still scores the accounts, like score.py.
node("Read the CSV", "n8n-nodes-base.extractFromFile", 1, {"operation": "csv", "options": {}}, [880, 0],
     alwaysOutputData=True)
code("Score and tier", SCORE_JS, [1100, 0], executeOnce=True)
node("Add to Accounts", "n8n-nodes-base.googleSheets", 4.7, {
    "operation": "append",
    "documentId": {"__rl": True, "mode": "url", "value": "={{ $('Your settings').first().json.accounts_tab_url }}"},
    "sheetName": {"__rl": True, "mode": "url", "value": "={{ $('Your settings').first().json.accounts_tab_url }}"},
    "columns": {"mappingMode": "autoMapInputData", "value": {}, "matchingColumns": [], "schema": []},
    "options": {"useAppend": True},
}, [1320, 0], SHEETS_CRED)

for a, b in [("Every Monday at 8", "Your settings"), ("Your settings", "Get the accounts"),
             ("Get the accounts", "Intent export"), ("Intent export", "Read the CSV"),
             ("Read the CSV", "Score and tier"), ("Score and tier", "Add to Accounts")]:
    link(a, b)

workflow = {"name": "Intent signal scorer (Evaboot)", "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}, "pinData": {}}
out = Path(__file__).with_name("intent-signal-scorer.json")
out.write_text(json.dumps(workflow, indent=2, ensure_ascii=False) + "\n")
print(out, len(nodes), "nodes")
