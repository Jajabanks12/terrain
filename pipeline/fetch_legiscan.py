"""
Pulls pending tort-reform-related legislation from LegiScan API.
State-level table only — does not join to county spine.

Search terms (run one query per term per state would be too many calls,
so we use LegiScan's built-in relevance search across all states with
'year=2' = current + prior session, then filter client-side):
  - "tort reform"
  - "damages cap"
  - "joint and several"
  - "dram shop"

Deduplicates by bill_id. Filters to bills with last_action in past 18 months.
Target: dozens to low hundreds of rows.

Requires LEGISCAN_API_KEY in .env
Sign up free: https://legiscan.com/legiscan-api/signup
"""

import os, time, pathlib
from datetime import datetime, timedelta
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LEGISCAN_API_KEY")
if not API_KEY:
    raise SystemExit("ERROR: set LEGISCAN_API_KEY in .env")

BASE = "https://api.legiscan.com/"
OUT  = pathlib.Path(__file__).parent.parent / "data" / "processed" / "legiscan.csv"

# Search terms — kept specific; broader terms filtered by relevance + title
SEARCH_TERMS = [
    "tort reform",
    "dram shop liability",
    "punitive damages cap",
    "joint and several liability reform",
]

# Minimum LegiScan relevance score (0-100) to accept a result
MIN_RELEVANCE = 70

# Only keep bills with last action within this window
CUTOFF = datetime.now() - timedelta(days=548)   # ~18 months

# Title must contain at least one of these keywords to be included
TITLE_KEYWORDS = [
    "tort", "liability", "damages", "negligence", "dram shop",
    "personal injury", "civil action", "cause of action", "wrongful",
    "joint and several", "punitive", "comparative fault",
]

# LegiScan bill status codes
STATUS_MAP = {
    1: "Introduced",
    2: "Engrossed",
    3: "Enrolled",
    4: "Passed",
    5: "Vetoed",
    6: "Failed/Dead",
}


def _derive_status(last_action: str) -> str:
    """Infer bill status from last action text (search results lack a status code)."""
    a = last_action.lower()
    if any(w in a for w in ["signed", "enacted", "chaptered", "effective"]):
        return "Enacted"
    if any(w in a for w in ["passed", "adopted", "approved"]):
        return "Passed"
    if any(w in a for w in ["vetoed"]):
        return "Vetoed"
    if any(w in a for w in ["failed", "died", "tabled", "withdrawn", "indefinitely postponed"]):
        return "Failed/Dead"
    if any(w in a for w in ["committee", "referred", "assigned", "introduced", "first read", "second read"]):
        return "In Committee"
    return "Active"


def search(query: str, page: int = 1) -> dict:
    params = {
        "key":   API_KEY,
        "op":    "search",
        "query": query,
        "year":  2,        # current + prior session
        "page":  page,
    }
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_bill(bill_id: int) -> dict | None:
    params = {"key": API_KEY, "op": "getBill", "id": bill_id}
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("status") == "OK":
        return data.get("bill", {})
    return None


def collect_search_results(query: str) -> list[dict]:
    """Page through all search results for a query, return summary rows."""
    results = []
    page = 1
    while True:
        data = search(query, page)
        if data.get("status") != "OK":
            print(f"    API error: {data.get('alert', {}).get('message', data)}")
            break

        sr = data.get("searchresult", {})
        summary = sr.get("summary", {})
        total_pages = int(summary.get("page_total", 1))
        hits = [v for k, v in sr.items() if k != "summary"]

        results.extend(hits)
        if page >= total_pages:
            break
        page += 1
        time.sleep(0.3)

    return results


if __name__ == "__main__":
    all_hits: dict[int, dict] = {}   # bill_id -> row

    for term in SEARCH_TERMS:
        print(f"\nSearching: '{term}' ...")
        hits = collect_search_results(term)
        print(f"  {len(hits)} raw results")

        new = 0
        for hit in hits:
            bill_id = hit.get("bill_id")
            if not bill_id or bill_id in all_hits:
                continue

            # Relevance filter
            if int(hit.get("relevance", 0)) < MIN_RELEVANCE:
                continue

            # Parse last action date
            last_action_date_str = hit.get("last_action_date", "")
            try:
                last_action_date = datetime.strptime(last_action_date_str, "%Y-%m-%d")
            except ValueError:
                continue

            if last_action_date < CUTOFF:
                continue

            # Title keyword filter — must mention a tort/liability concept
            title_lower = hit.get("title", "").lower()
            if not any(kw in title_lower for kw in TITLE_KEYWORDS):
                continue

            all_hits[bill_id] = {
                "bill_id":          bill_id,
                "state_abbr":       hit.get("state", ""),
                "bill_number":      hit.get("bill_number", ""),
                "title":            hit.get("title", ""),
                "status":           _derive_status(hit.get("last_action", "")),
                "last_action_date": last_action_date_str,
                "last_action":      hit.get("last_action", ""),
                "url":              hit.get("url", ""),
                "matched_term":     term,
            }
            new += 1

        print(f"  {new} new bills added (after dedup + date filter)")
        time.sleep(0.5)

    print(f"\nTotal unique bills: {len(all_hits)}")

    if not all_hits:
        print("No bills found — check API key and search terms.")
    else:
        df = pd.DataFrame(all_hits.values())
        df = df.sort_values(["state_abbr", "last_action_date"], ascending=[True, False])

        print(f"\nBy state (top 15):")
        print(df["state_abbr"].value_counts().head(15).to_string())

        print(f"\nBy status:")
        print(df["status"].value_counts().to_string())

        df.to_csv(OUT, index=False)
        print(f"\nSaved: {OUT}  ({len(df)} rows)")

        # Sample
        print("\nSample bills:")
        print(df[["state_abbr","bill_number","status","last_action_date","title"]]
              .head(10)
              .to_string(index=False))
