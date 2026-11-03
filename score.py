"""Merge an intent data provider's export with Sales Navigator account signals and rank the accounts.

The agent exports your target accounts from Sales Navigator through the Evaboot MCP; you download the intent
export from your provider (Bombora, 6sense, ZoomInfo, G2, Demandbase...). This script matches both by domain,
scores every account with the points in SIGNALS.md, puts it in a tier and writes the list. No network.

    python3 score.py --accounts data/accounts.json --intent data/intent.csv \\
        [--signals SIGNALS.md] [--csv lists/2026-11-03.csv] > lists/2026-11-03.md
"""
import argparse
import csv
import json
import re
import sys
from urllib.parse import urlparse

# Fallback values, used when SIGNALS.md has no table row for them. Edit SIGNALS.md, not these.
DEFAULT_POINTS = {"intent_surge": 10, "intent_extra_topic": 3, "fit": 5, "fast_growth": 6, "recent_growth": 4,
                  "hiring": 3}
DEFAULT_SETTINGS = {"surge_threshold": 60, "max_extra_topics": 2, "fast_growth_pct": 30, "recent_growth_pct": 15,
                    "tier_now": 20, "tier_next": 10}
# (tier, what to do); the minimum scores come from SIGNALS.md (tier_now, tier_next)
TIER_ACTIONS = [("now", "export the buyers and reach out this week"),
                ("next", "add to next week's list; check again on the next intent export"),
                ("watch", "no outreach yet; wait for a stronger signal")]


def tiers(settings):
    mins = [settings["tier_now"], settings["tier_next"], float("-inf")]
    return [(m, t, a) for m, (t, a) in zip(mins, TIER_ACTIONS)]
COLUMN_ALIASES = {
    "domain": ["domain", "company domain", "website", "company website", "company_domain"],
    "company": ["company", "company name", "account", "account name", "company_name"],
    "topic": ["topic", "topic name", "intent topic", "keyword", "category"],
    "score": ["score", "composite score", "intent score", "surge score", "intent strength", "signal score"],
}
NOT_A_DOMAIN = {"linktr.ee", "linkedin.com", "bit.ly", "facebook.com", "google.com"}
CSV_FIELDS = ["tier", "score", "company", "domain", "signals", "intent_topics", "growth_1y", "growth_6m",
              "employees", "linkedin", "action"]


def num(v):
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def domain_of(value):
    """'https://www.Acme.com/li' -> 'acme.com'. Empty for link shorteners and blanks."""
    v = str(value or "").strip().lower()
    if not v:
        return ""
    host = urlparse(v if "://" in v else "http://" + v).hostname or ""
    host = re.sub(r"^(www\d?|get|go|app)\.", "", host)
    return "" if host in NOT_A_DOMAIN else host


def read_table(path):
    """Points and settings from the `| key | value |` rows of SIGNALS.md."""
    points, settings = dict(DEFAULT_POINTS), dict(DEFAULT_SETTINGS)
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return points, settings
    for key, value in re.findall(r"^\|\s*`([a-z_0-9]+)`\s*\|\s*(\d+(?:\.\d+)?)\s*\|", text, re.M):
        (points if key in points else settings)[key] = float(value) if "." in value else int(value)
    return points, settings


def read_intent(path, topics_filter):
    """Intent export -> {domain: {"company": str, "topics": {topic: best score}}}. No path: no intent."""
    if not path:
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        lower = {h.lower().strip(): h for h in reader.fieldnames or []}
        col = {k: next((lower[a] for a in aliases if a in lower), None) for k, aliases in COLUMN_ALIASES.items()}
        if not col["domain"] or not col["score"]:
            sys.exit(f"{path}: needs a domain column and a score column, found {reader.fieldnames}")
        out = {}
        for r in reader:
            d = domain_of(r.get(col["domain"]))
            s = num(r.get(col["score"]))
            topic = (r.get(col["topic"]) or "intent").strip() if col["topic"] else "intent"
            if not d or s is None or (topics_filter and topic.lower() not in topics_filter):
                continue
            acc = out.setdefault(d, {"company": (r.get(col["company"]) or "").strip() if col["company"] else "",
                                     "topics": {}})
            acc["topics"][topic] = max(s, acc["topics"].get(topic, 0))
    if topics_filter and not out:
        sys.exit(f"{path}: no row matches the topics {sorted(topics_filter)}; check their spelling in the file")
    return out


def read_accounts(paths):
    """Evaboot account exports -> {domain or name: account}. `hiring=path` marks a search with the hiring filter."""
    accounts = {}
    for spec in paths:
        tag, _, path = spec.rpartition("=")
        data = json.load(open(path, encoding="utf-8"))
        for a in data.get("prospects") or data.get("results") or []:
            if str(a.get("Matches Filters", "match")).lower() == "no_match":
                continue
            d = domain_of(a.get("Company Domain")) or domain_of(a.get("Company Website URL"))
            key = d or "name:" + str(a.get("Company Name", "")).lower()
            acc = accounts.setdefault(key, {"raw": a, "domain": d, "tags": set()})
            if tag:
                acc["tags"].add(tag)
    return accounts


def score_all(accounts, intent, points, settings):
    rows, seen, tier_list = [], set(), tiers(settings)
    keys = list(accounts) + [d for d in intent if d not in accounts]
    for key in keys:
        if key in seen:
            continue
        seen.add(key)
        acc = accounts.get(key)
        raw = acc["raw"] if acc else {}
        domain = acc["domain"] if acc else key
        signals, total = [], 0

        surging = sorted(((t, s) for t, s in (intent.get(domain, {}).get("topics") or {}).items()
                          if s >= settings["surge_threshold"]), key=lambda x: -x[1])
        if surging:
            total += points["intent_surge"]
            extra = min(len(surging) - 1, settings["max_extra_topics"])
            total += extra * points["intent_extra_topic"]
            signals.append(f"intent surge on {len(surging)} topic{'s' if len(surging) > 1 else ''}")
        if acc:
            total += points["fit"]
            signals.append("fits your account search")
            if "hiring" in acc["tags"]:
                total += points["hiring"]
                signals.append("hiring on LinkedIn")
        g1, g6 = num(raw.get("Company Employee Growth 1 Year (%)")), num(raw.get("Company Employee Growth 6 Months (%)"))
        if g1 is not None and g1 >= settings["fast_growth_pct"]:
            total += points["fast_growth"]
            signals.append(f"headcount +{g1:.0f}% in a year")
        if g6 is not None and g6 >= settings["recent_growth_pct"]:
            total += points["recent_growth"]
            signals.append(f"headcount +{g6:.0f}% in 6 months")

        _, tier, action = next(t for t in tier_list if total >= t[0])
        if not acc:
            action = "intent only: check the account fits before any outreach"
            signals.append("not in your account search: check fit")
        rows.append({
            "tier": tier, "score": total,
            "company": raw.get("Company Name") or intent.get(domain, {}).get("company") or domain,
            "domain": domain, "signals": ", ".join(signals) or "none",
            "intent_topics": "; ".join(f"{t} {s:.0f}" for t, s in surging),
            "growth_1y": "" if g1 is None else f"{g1:.0f}", "growth_6m": "" if g6 is None else f"{g6:.0f}",
            "employees": raw.get("Company Employee Exact Count", ""),
            "linkedin": raw.get("Company Linkedin URL Unique ID", ""), "action": action,
        })
    return sorted(rows, key=lambda r: (-r["score"], r["company"].lower()))


def markdown(rows):
    out = ["# Accounts to work, best first", ""]
    for tier, action in TIER_ACTIONS:
        group = [r for r in rows if r["tier"] == tier]
        out += [f"## {tier} ({len(group)}): {action}", ""]
        if not group:
            out += ["None.", ""]
            continue
        out += ["| Score | Company | Signals | Intent topics |", "|---|---|---|---|"]
        out += [f"| {r['score']} | {r['company']} | {r['signals']} | {r['intent_topics'] or '-'} |" for r in group]
        out.append("")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--accounts", action="append", required=True,
                    help="Evaboot account export JSON; prefix with hiring= when the search had the hiring filter")
    ap.add_argument("--intent", default="", help="intent export CSV from your provider (optional)")
    ap.add_argument("--topics", default="", help="comma-separated topics to keep (default: all)")
    ap.add_argument("--signals", default="SIGNALS.md")
    ap.add_argument("--csv", help="also write the list as CSV")
    a = ap.parse_args()
    points, settings = read_table(a.signals)
    topics = {t.strip().lower() for t in a.topics.split(",") if t.strip()}
    rows = score_all(read_accounts(a.accounts), read_intent(a.intent, topics), points, settings)
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            w.writeheader()
            w.writerows(rows)
    print(markdown(rows))


if __name__ == "__main__":
    main()
