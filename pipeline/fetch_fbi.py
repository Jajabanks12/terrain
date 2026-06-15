"""
Pulls FBI Crime Data Explorer (CDE) violent crime statistics at the county level.

Strategy:
  1. Per state, fetch all agencies (51 calls) — agencies carry county names.
  2. Per county, prioritize the County Sheriff's Office ORI; fall back to
     any reporting agency.
  3. Fetch violent-crime + robbery monthly rates for 2020-2022, average them
     to get a single annual rate per county.
  4. Flag stale/missing data so underwriters know coverage gaps.

Requires FBI_API_KEY in .env
Sign up free: https://api.data.gov/signup/
"""

import os, time, pathlib
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FBI_API_KEY")
if not API_KEY:
    raise SystemExit("ERROR: set FBI_API_KEY in your .env file")

BASE   = "https://api.usa.gov/crime/fbi/cde"
FROM_  = "01-2020"
TO_    = "12-2022"

SPINE  = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine_with_fips.csv"
OUT    = pathlib.Path(__file__).parent.parent / "data" / "processed" / "fbi_crime.csv"

STATE_ABBRS = [
    "AL","AK","AZ","AR","CA","CO","CT","DE","DC","FL","GA","HI","ID","IL","IN",
    "IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH",
    "NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT",
    "VT","VA","WA","WV","WI","WY",
]


def get_with_retry(url: str, params: dict, max_tries: int = 5) -> dict | list | None:
    """GET with exponential backoff for rate-limit (429) responses."""
    for attempt in range(max_tries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                wait = 2 ** attempt * 5
                print(f"      rate-limited, waiting {wait}s...", flush=True)
                time.sleep(wait)
                continue
            if not r.ok:
                return None
            if not r.text.strip():
                return None
            data = r.json()
            if isinstance(data, dict) and "error" in data:
                return None
            return data
        except Exception:
            time.sleep(2 ** attempt)
    return None


def fetch_agencies_by_state(state: str) -> dict[str, list[dict]]:
    """Returns {COUNTY_NAME_UPPER: [agency, ...]} for a state."""
    data = get_with_retry(
        f"{BASE}/agency/byStateAbbr/{state}",
        {"API_KEY": API_KEY},
    )
    if not data or not isinstance(data, dict):
        return {}
    return data


def pick_best_ori(agencies: list[dict]) -> str | None:
    """
    From a county's agency list, prefer (in order):
      1. County Sheriff's Office / County Police
      2. State Police / Highway Patrol
      3. Any agency
    """
    if not agencies:
        return None
    for preferred in ["County", "Sheriff"]:
        for a in agencies:
            if preferred.lower() in a.get("agency_type_name", "").lower() or \
               preferred.lower() in a.get("agency_name", "").lower():
                return a["ori"]
    # fall back to first agency
    return agencies[0]["ori"]


def fetch_crime_rate(ori: str, offense: str) -> float | None:
    """
    Fetch monthly offense rates for an ORI, return mean annual rate per 100k.
    """
    data = get_with_retry(
        f"{BASE}/summarized/agency/{ori}/{offense}",
        {"API_KEY": API_KEY, "from": FROM_, "to": TO_},
    )
    if not data:
        return None

    rates_dict = data.get("offenses", {}).get("rates", {})
    # Find the key ending in " Offenses" that matches this agency
    agency_key = next(
        (k for k in rates_dict if k.endswith("Offenses") and
         "United States" not in k and "Alabama" not in k and
         len(rates_dict[k]) > 0),
        None,
    )
    # Fallback: take the first non-national Offenses key
    if not agency_key:
        agency_key = next(
            (k for k in rates_dict if "Offenses" in k and "United States" not in k),
            None,
        )
    if not agency_key:
        return None

    monthly = rates_dict[agency_key]
    values = [v for v in monthly.values() if isinstance(v, (int, float)) and v >= 0]
    if not values:
        return None
    return round(sum(values) / len(values) * 12, 1)   # annualised rate per 100k


def process_state(state_abbr: str) -> list[dict]:
    county_map = fetch_agencies_by_state(state_abbr)
    time.sleep(0.3)

    rows = []
    for county_upper, agencies in county_map.items():
        ori = pick_best_ori(agencies)
        if not ori:
            rows.append({
                "state_abbr": state_abbr,
                "fbi_county": county_upper.title(),
                "violent_crime_rate": None,
                "robbery_rate": None,
                "data_years": f"{FROM_}-{TO_}",
                "data_flag": "no_agency",
            })
            continue

        vc_rate = fetch_crime_rate(ori, "violent-crime")
        time.sleep(0.25)
        rob_rate = fetch_crime_rate(ori, "robbery")
        time.sleep(0.25)

        flag = "ok" if vc_rate is not None else "no_data"

        rows.append({
            "state_abbr": state_abbr,
            "fbi_county": county_upper.title(),
            "violent_crime_rate": vc_rate,
            "robbery_rate": rob_rate,
            "data_years": f"{FROM_}-{TO_}",
            "data_flag": flag,
        })

    return rows


def normalize_county(name: str) -> str:
    return (name.strip().lower()
            .replace(" county", "")
            .replace(" parish", "")
            .replace(" borough", "")
            .replace(".", "")
            .replace("'", "")
            .replace("-", " "))


if __name__ == "__main__":
    print(f"Pulling FBI CDE data ({FROM_} to {TO_}) ...")
    all_rows = []

    for i, state in enumerate(STATE_ABBRS, 1):
        print(f"  [{i:02d}/{len(STATE_ABBRS)}] {state}", end=" ", flush=True)
        rows = process_state(state)
        all_rows.extend(rows)
        ok = sum(1 for r in rows if r["data_flag"] == "ok")
        print(f"-> {len(rows)} counties, {ok} with data")

    fbi = pd.DataFrame(all_rows)
    print(f"\nTotal FBI rows: {len(fbi)}")
    print(f"With data:      {(fbi['data_flag']=='ok').sum()}")
    print(f"No data:        {(fbi['data_flag']!='ok').sum()}")

    # ── join to spine ─────────────────────────────────────────────────────────
    spine = pd.read_csv(SPINE, dtype=str)

    # normalise both sides for fuzzy join
    spine["_key"] = spine["state_abbr"] + "|" + spine["county_name"].str.lower().apply(normalize_county)
    fbi["_key"]   = fbi["state_abbr"]   + "|" + fbi["fbi_county"].str.lower().apply(normalize_county)

    merged = spine.merge(
        fbi[["_key", "violent_crime_rate", "robbery_rate", "data_years", "data_flag"]],
        on="_key",
        how="left",
    ).drop(columns=["_key"])

    merged["data_flag"] = merged["data_flag"].fillna("not_matched")

    print(f"\nSpine rows:     {len(merged)}")
    print(f"Matched:        {(merged['data_flag']=='ok').sum()}")
    print(f"No data:        {(merged['data_flag']=='no_data').sum()}")
    print(f"Not matched:    {(merged['data_flag']=='not_matched').sum()}")

    merged.to_csv(OUT, index=False)
    print(f"\nSaved: {OUT}")

    # ── spot-check ────────────────────────────────────────────────────────────
    for state, county in [("GA","Fulton"), ("TX","Harris"), ("FL","Miami-Dade")]:
        row = merged[(merged["state_abbr"]==state) & (merged["county_name"]==county)]
        if not row.empty:
            r = row.iloc[0]
            print(f"\n{county}, {state}: violent={r['violent_crime_rate']} "
                  f"robbery={r['robbery_rate']} flag={r['data_flag']}")
