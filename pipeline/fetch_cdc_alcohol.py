"""
Pulls CDC PLACES binge drinking prevalence at the county level.
Source: CDC PLACES 2023 release via Socrata API (no key required).
  Dataset: swc5-untb  (PLACES County Data)
  Measure: BINGE — crude prevalence % of adults who binge drink

Output columns:
  binge_drinking_pct       — crude prevalence %
  binge_drinking_pct_ci_lo — 95% CI lower bound
  binge_drinking_pct_ci_hi — 95% CI upper bound
  cdc_places_year          — data year (2023)
"""

import pathlib
import pandas as pd
import requests

URL   = "https://data.cdc.gov/resource/swc5-untb.json"
SPINE = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine_with_fips.csv"
OUT   = pathlib.Path(__file__).parent.parent / "data" / "processed" / "cdc_alcohol.csv"

PAGE  = 2000   # Socrata max per request


def fetch_binge() -> pd.DataFrame:
    """Fetch all county-level crude BINGE drinking prevalence records."""
    rows, offset = [], 0
    while True:
        params = {
            "measureid":       "BINGE",
            "datavaluetypeid": "CrdPrv",
            "$limit":          PAGE,
            "$offset":         offset,
            "$order":          "locationid",
        }
        r = requests.get(URL, params=params, timeout=30)
        r.raise_for_status()
        batch = r.json()
        rows.extend(batch)
        print(f"  fetched {len(rows):,} records...", flush=True)
        if len(batch) < PAGE:
            break
        offset += PAGE

    df = pd.DataFrame(rows)
    return df


if __name__ == "__main__":
    print("Pulling CDC PLACES binge drinking data...")
    raw = fetch_binge()
    print(f"Total records: {len(raw)}")

    # Keep only needed columns and rename
    raw = raw.rename(columns={
        "locationid":           "fips",
        "data_value":           "binge_drinking_pct",
        "low_confidence_limit": "binge_drinking_ci_lo",
        "high_confidence_limit":"binge_drinking_ci_hi",
        "year":                 "cdc_places_year",
    })

    # Ensure 5-digit FIPS (locationid is already numeric string)
    raw["fips"] = raw["fips"].astype(str).str.zfill(5)

    keep = ["fips", "binge_drinking_pct", "binge_drinking_ci_lo",
            "binge_drinking_ci_hi", "cdc_places_year"]
    raw = raw[keep].copy()

    for col in ["binge_drinking_pct", "binge_drinking_ci_lo", "binge_drinking_ci_hi"]:
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    # ── join to spine ─────────────────────────────────────────────────────────
    spine  = pd.read_csv(SPINE, dtype=str)
    merged = spine.merge(raw, on="fips", how="left")

    matched = merged["binge_drinking_pct"].notna().sum()
    missing = merged["binge_drinking_pct"].isna().sum()
    print(f"\nSpine rows: {len(merged)}")
    print(f"Matched:    {matched}")
    print(f"Missing:    {missing}")

    merged["cdc_places_year"] = merged["cdc_places_year"].fillna("no_data")

    merged.to_csv(OUT, index=False)
    print(f"\nSaved: {OUT}")

    # ── spot-checks ───────────────────────────────────────────────────────────
    print("\nSpot-checks:")
    for state, county in [("GA","Fulton"), ("TX","Harris"), ("FL","Dade"), ("CO","Denver")]:
        row = merged[(merged["state_abbr"]==state) & (merged["county_name"]==county)]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {county}, {state}: binge={r['binge_drinking_pct']}% "
                  f"(CI {r['binge_drinking_ci_lo']}–{r['binge_drinking_ci_hi']})")
        else:
            print(f"  {county}, {state}: NOT FOUND")
