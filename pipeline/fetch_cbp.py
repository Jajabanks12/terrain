"""
Pulls Census County Business Patterns (CBP) 2021 establishment counts
for three NAICS codes per county:
  7224  — Drinking Places (Alcoholic Beverages)
  7221  — Full-Service Restaurants
  484   — Truck Transportation

One state-level call per NAICS code per state = 51 x 3 = 153 total API calls.

Suppressed values (Census withholds small counts for privacy) are stored as
None with a suppressed=True flag rather than zero.

Requires CENSUS_API_KEY in .env
"""

import os, time, pathlib
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("CENSUS_API_KEY")
if not API_KEY:
    raise SystemExit("ERROR: set CENSUS_API_KEY in .env")

BASE  = "https://api.census.gov/data/2021/cbp"
SPINE = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine_with_fips.csv"
OUT   = pathlib.Path(__file__).parent.parent / "data" / "processed" / "cbp.csv"

NAICS_TARGETS = {
    "7224":   "drinking_places",
    "722511": "restaurants_fullsvc",
    "484":    "truck_transportation",
}

STATE_FIPS = [
    "01","02","04","05","06","08","09","10","11","12","13","15","16","17","18",
    "19","20","21","22","23","24","25","26","27","28","29","30","31","32","33",
    "34","35","36","37","38","39","40","41","42","44","45","46","47","48","49",
    "50","51","53","54","55","56",
]


def fetch_naics(state_fips: str, naics: str) -> list[dict]:
    """
    Returns county-level establishment rows for one state + NAICS code.
    EMP_N is Census noise flag: 0 = real value, >0 = suppressed/noisy.
    """
    params = {
        "get":      "NAME,NAICS2017,ESTAB,EMP,EMP_N",
        "for":      "county:*",
        "in":       f"state:{state_fips}",
        "NAICS2017": naics,
        "key":      API_KEY,
    }
    try:
        r = requests.get(BASE, params=params, timeout=30)
        if not r.ok or not r.text.strip().startswith("["):
            return []
        data = r.json()
        headers = data[0]
        rows = []
        for record in data[1:]:
            d = dict(zip(headers, record))
            fips = d["state"].zfill(2) + d["county"].zfill(3)
            estab = None
            suppressed = False
            try:
                emp_n = int(d.get("EMP_N", 0))
                if emp_n > 0:
                    # Census suppressed this cell
                    suppressed = True
                else:
                    estab = int(d["ESTAB"])
            except (ValueError, TypeError):
                suppressed = True
            rows.append({
                "fips":       fips,
                "naics":      naics,
                "estab":      estab,
                "suppressed": suppressed,
            })
        return rows
    except Exception:
        return []


if __name__ == "__main__":
    all_rows = []

    for naics, label in NAICS_TARGETS.items():
        print(f"\nNAICS {naics} ({label}):")
        naics_rows = []
        for i, sf in enumerate(STATE_FIPS, 1):
            rows = fetch_naics(sf, naics)
            naics_rows.extend(rows)
            print(f"  [{i:02d}/51] state {sf} -> {len(rows)} counties", flush=True)
            time.sleep(0.15)

        real      = sum(1 for r in naics_rows if not r["suppressed"] and r["estab"] is not None)
        suppressed = sum(1 for r in naics_rows if r["suppressed"])
        print(f"  Total: {len(naics_rows)} counties | {real} with data | {suppressed} suppressed")
        all_rows.extend(naics_rows)

    # ── pivot: one row per county, one column per NAICS ──────────────────────
    df = pd.DataFrame(all_rows)

    # Build per-NAICS frames and merge together
    cbp = None
    for naics, label in NAICS_TARGETS.items():
        sub = df[df["naics"] == naics][["fips", "estab", "suppressed"]].copy()
        sub = sub.rename(columns={
            "estab":      f"{label}_estab",
            "suppressed": f"{label}_suppressed",
        })
        if cbp is None:
            cbp = sub
        else:
            cbp = cbp.merge(sub, on="fips", how="outer")

    if cbp is None:
        raise SystemExit("No data collected — check API key and NAICS codes")

    # ── join to spine ─────────────────────────────────────────────────────────
    spine  = pd.read_csv(SPINE, dtype=str)
    merged = spine.merge(cbp, on="fips", how="left")

    # Counties absent from CBP entirely = no establishments reported
    for label in NAICS_TARGETS.values():
        merged[f"{label}_suppressed"] = merged[f"{label}_suppressed"].fillna(False)

    print(f"\nSpine rows:  {len(merged)}")
    for label in NAICS_TARGETS.values():
        col = f"{label}_estab"
        has = merged[col].notna().sum()
        supp = merged[f"{label}_suppressed"].sum()
        print(f"  {label}: {has} with data, {int(supp)} suppressed, "
              f"{len(merged)-has-int(supp)} no establishments")

    merged.to_csv(OUT, index=False)
    print(f"\nSaved: {OUT}")

    # ── spot-checks ───────────────────────────────────────────────────────────
    print("\nSpot-checks:")
    for state, county in [("GA","Fulton"), ("TX","Harris"), ("FL","Dade"), ("NY","New York")]:
        row = merged[(merged["state_abbr"]==state) & (merged["county_name"]==county)]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {county}, {state}: "
                  f"bars={r.get('drinking_places_estab','?')} "
                  f"restaurants={r.get('restaurants_fullsvc_estab','?')} "
                  f"trucks={r.get('truck_transportation_estab','?')}")
