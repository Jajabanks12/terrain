"""
Pulls NHTSA FARS 2022 crash data and aggregates to county level.

Source: FARS2022NationalCSV.zip (no API key needed)
  accident.csv  — one row per fatal crash: STATE, COUNTY, FATALS
  vehicle.csv   — one row per vehicle: ST_CASE, DR_DRINK (alcohol flag)

Output columns per county:
  total_crashes        — fatal crashes in 2022
  total_fatalities     — sum of FATALS
  alcohol_crashes      — crashes where >= 1 driver had DR_DRINK=1
  pct_alcohol          — alcohol_crashes / total_crashes * 100
  fatality_rate_per_100k — fatalities / population * 100,000
  fars_year            — 2022
"""

import io, zipfile, pathlib
import pandas as pd
import requests

FARS_URL = "https://static.nhtsa.gov/nhtsa/downloads/FARS/2022/National/FARS2022NationalCSV.zip"
FARS_YEAR = 2022

SPINE   = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine_with_fips.csv"
CENSUS  = pathlib.Path(__file__).parent.parent / "data" / "processed" / "census.csv"
OUT     = pathlib.Path(__file__).parent.parent / "data" / "processed" / "nhtsa.csv"
RAW_DIR = pathlib.Path(__file__).parent.parent / "data" / "raw"
ZIP_CACHE = RAW_DIR / "FARS2022NationalCSV.zip"


def download_fars() -> zipfile.ZipFile:
    if ZIP_CACHE.exists():
        print(f"Using cached FARS zip: {ZIP_CACHE}")
        return zipfile.ZipFile(ZIP_CACHE)
    print("Downloading FARS 2022 (~35 MB)...")
    r = requests.get(FARS_URL, timeout=180)
    r.raise_for_status()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ZIP_CACHE.write_bytes(r.content)
    print(f"Saved: {ZIP_CACHE}")
    return zipfile.ZipFile(io.BytesIO(r.content))


def load_accident(z: zipfile.ZipFile) -> pd.DataFrame:
    with z.open("FARS2022NationalCSV/accident.csv") as f:
        df = pd.read_csv(f, encoding="utf-8-sig", low_memory=False)
    # Normalise column names (strip any remaining whitespace/quotes)
    df.columns = [c.strip().strip("'") for c in df.columns]
    df["fips"] = df["STATE"].astype(str).str.zfill(2) + df["COUNTY"].astype(str).str.zfill(3)
    return df[["ST_CASE", "fips", "FATALS"]]


def load_alcohol(z: zipfile.ZipFile) -> pd.DataFrame:
    """Returns set of ST_CASE values where at least one driver had DR_DRINK=1."""
    with z.open("FARS2022NationalCSV/vehicle.csv") as f:
        veh = pd.read_csv(f, encoding="latin-1", low_memory=False)
    # DR_DRINK: 0=No, 1=Yes, 8=Not reported, 9=Unknown
    alcohol = veh[veh["DR_DRINK"] == 1][["ST_CASE"]].drop_duplicates()
    return alcohol


def aggregate(acc: pd.DataFrame, alcohol_cases: pd.DataFrame) -> pd.DataFrame:
    # Flag alcohol involvement at crash level
    acc["alcohol"] = acc["ST_CASE"].isin(alcohol_cases["ST_CASE"]).astype(int)

    county = acc.groupby("fips").agg(
        total_crashes    =("ST_CASE",  "count"),
        total_fatalities =("FATALS",   "sum"),
        alcohol_crashes  =("alcohol",  "sum"),
    ).reset_index()

    county["pct_alcohol"] = (
        county["alcohol_crashes"] / county["total_crashes"] * 100
    ).round(1)
    county["fars_year"] = FARS_YEAR

    # Exclude county FIPS ending in 000 (state-level or unknown county)
    county = county[~county["fips"].str.endswith("000")]
    return county


if __name__ == "__main__":
    z   = download_fars()
    acc = load_accident(z)
    alc = load_alcohol(z)

    print(f"Total fatal crashes: {len(acc):,}")
    print(f"Alcohol-involved:    {len(alc):,} unique crashes")

    county_data = aggregate(acc, alc)
    print(f"Counties with crashes: {len(county_data)}")

    # ── join to spine + population from census ────────────────────────────────
    spine  = pd.read_csv(SPINE,  dtype=str)
    census = pd.read_csv(CENSUS, dtype=str)[["fips", "population"]]
    census["population"] = pd.to_numeric(census["population"], errors="coerce")

    merged = (
        spine
        .merge(census, on="fips", how="left")
        .merge(county_data, on="fips", how="left")
    )

    # Fatality rate per 100k (requires population from Census Phase 3)
    merged["fatality_rate_per_100k"] = (
        merged["total_fatalities"] / merged["population"] * 100_000
    ).round(2)

    # Fill counties with no reported crashes
    merged["total_crashes"]    = merged["total_crashes"].fillna(0).astype("Int64")
    merged["total_fatalities"] = merged["total_fatalities"].fillna(0).astype("Int64")
    merged["alcohol_crashes"]  = merged["alcohol_crashes"].fillna(0).astype("Int64")
    merged["fars_year"]        = merged["fars_year"].fillna(FARS_YEAR)
    merged["pct_alcohol"]      = merged["pct_alcohol"].fillna(0)

    merged.drop(columns=["population"], inplace=True)

    print(f"\nSpine rows:             {len(merged)}")
    print(f"Counties with crashes:  {(merged['total_crashes'] > 0).sum()}")
    print(f"Counties zero crashes:  {(merged['total_crashes'] == 0).sum()}")

    merged.to_csv(OUT, index=False)
    print(f"\nSaved: {OUT}")

    # ── spot-check ────────────────────────────────────────────────────────────
    checks = [("GA", "Fulton"), ("TX", "Harris"), ("FL", "Miami-Dade")]
    print("\nSpot-checks:")
    for state, county in checks:
        row = merged[(merged["state_abbr"] == state) & (merged["county_name"] == county)]
        if not row.empty:
            r = row.iloc[0]
            print(f"  {county}, {state}: crashes={r['total_crashes']}  "
                  f"fatalities={r['total_fatalities']}  "
                  f"alcohol={r['pct_alcohol']}%  "
                  f"rate={r['fatality_rate_per_100k']}/100k")
        else:
            print(f"  {county}, {state}: NOT FOUND in merged table")
