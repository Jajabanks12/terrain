"""
Pulls ACS 5-year 2022 data for every county, merges land area from the
Census Gazetteer, and joins to spine_with_fips.csv on FIPS.

Variables pulled per county:
  B01003_001E  total population
  B19013_001E  median household income
  B15003_001E  population 25+          (education denominator)
  B15003_022E  bachelor's degree
  B15003_023E  master's degree
  B15003_024E  professional school degree
  B15003_025E  doctorate degree

Derived:
  pop_density_sqmi  = population / ALAND_SQMI
  pct_bachelors_plus = (bach + master + prof + doc) / pop_25plus * 100
  urban_class        = Urban / Suburban / Rural  (density thresholds)

Requires CENSUS_API_KEY in .env
"""

import os, time, pathlib
import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY  = os.getenv("CENSUS_API_KEY")
if not API_KEY:
    raise SystemExit("ERROR: set CENSUS_API_KEY in your .env file")

BASE = "https://api.census.gov/data/2022/acs/acs5"

ACS_VARS = [
    "NAME",
    "B01003_001E",   # population
    "B19013_001E",   # median HH income
    "B15003_001E",   # pop 25+ (edu denominator)
    "B15003_022E",   # bachelor's
    "B15003_023E",   # master's
    "B15003_024E",   # professional
    "B15003_025E",   # doctorate
]

RENAME = {
    "B01003_001E": "population",
    "B19013_001E": "median_hh_income",
    "B15003_001E": "edu_pop_25plus",
    "B15003_022E": "edu_bachelors",
    "B15003_023E": "edu_masters",
    "B15003_024E": "edu_professional",
    "B15003_025E": "edu_doctorate",
}

RAW_GAZ   = pathlib.Path(__file__).parent.parent / "data" / "raw"  / "2023_Gaz_counties_national.txt"
SPINE     = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine_with_fips.csv"
OUT       = pathlib.Path(__file__).parent.parent / "data" / "processed" / "census.csv"


# ── state FIPS codes (all 51 including DC) ───────────────────────────────────
STATE_FIPS = [
    "01","02","04","05","06","08","09","10","11","12","13","15","16","17","18",
    "19","20","21","22","23","24","25","26","27","28","29","30","31","32","33",
    "34","35","36","37","38","39","40","41","42","44","45","46","47","48","49",
    "50","51","53","54","55","56",
]


def fetch_state(state_fips: str) -> pd.DataFrame:
    params = {
        "get":  ",".join(ACS_VARS),
        "for":  "county:*",
        "in":   f"state:{state_fips}",
        "key":  API_KEY,
    }
    r = requests.get(BASE, params=params, timeout=30)
    r.raise_for_status()
    if r.text.strip().startswith("<"):
        raise ValueError(f"API returned HTML (key issue?): {r.text[:120].strip()}")
    data = r.json()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["fips"] = df["state"] + df["county"]
    return df


def fetch_all() -> pd.DataFrame:
    frames = []
    for i, sf in enumerate(STATE_FIPS, 1):
        print(f"  [{i:02d}/{len(STATE_FIPS)}] state {sf} ...", end=" ", flush=True)
        try:
            df = fetch_state(sf)
            frames.append(df)
            print(f"{len(df)} counties")
        except Exception as e:
            print(f"ERROR: {e}")
        time.sleep(0.15)   # stay well under Census rate limit
    return pd.concat(frames, ignore_index=True)


def load_gazetteer() -> pd.DataFrame:
    gaz = pd.read_csv(RAW_GAZ, sep="\t", dtype=str, encoding="latin-1")
    gaz = gaz[["GEOID", "ALAND_SQMI"]].rename(columns={"GEOID": "fips"})
    gaz["ALAND_SQMI"] = pd.to_numeric(gaz["ALAND_SQMI"], errors="coerce")
    return gaz


def derive_fields(df: pd.DataFrame) -> pd.DataFrame:
    num_cols = [
        "population", "median_hh_income", "edu_pop_25plus",
        "edu_bachelors", "edu_masters", "edu_professional", "edu_doctorate",
    ]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
        # Census uses -666666666 for suppressed / N/A values
        df[col] = df[col].where(df[col] >= 0, other=None)

    df["pct_bachelors_plus"] = (
        (df["edu_bachelors"] + df["edu_masters"] + df["edu_professional"] + df["edu_doctorate"])
        / df["edu_pop_25plus"] * 100
    ).round(1)

    df["pop_density_sqmi"] = (df["population"] / df["ALAND_SQMI"]).round(2)

    # Simple 3-tier urban classification based on density + population
    def classify(row):
        pop  = row["population"]  or 0
        dens = row["pop_density_sqmi"] or 0
        if dens >= 1000 or pop >= 250_000:
            return "Urban"
        elif dens >= 100 or pop >= 50_000:
            return "Suburban"
        else:
            return "Rural"

    df["urban_class"] = df.apply(classify, axis=1)
    return df


if __name__ == "__main__":
    print("Fetching ACS 5-year 2022 data ...")
    raw = fetch_all()
    raw = raw.rename(columns=RENAME)

    print(f"\nRaw ACS rows: {len(raw)}")

    # merge land area
    gaz = load_gazetteer()
    raw = raw.merge(gaz, on="fips", how="left")
    missing_area = raw["ALAND_SQMI"].isna().sum()
    if missing_area:
        print(f"  WARN: {missing_area} counties missing land area")

    raw = derive_fields(raw)

    # join to spine
    spine = pd.read_csv(SPINE, dtype=str)
    merged = spine.merge(
        raw[["fips", "population", "median_hh_income", "edu_pop_25plus",
             "edu_bachelors", "edu_masters", "edu_professional", "edu_doctorate",
             "pct_bachelors_plus", "ALAND_SQMI", "pop_density_sqmi", "urban_class"]],
        on="fips",
        how="left",
    )

    missing = merged["population"].isna().sum()
    print(f"Spine rows:   {len(merged)}")
    print(f"Matched:      {len(merged) - missing}")
    print(f"Missing data: {missing}")
    print(f"Urban classes:\n{merged['urban_class'].value_counts().to_string()}")

    merged.to_csv(OUT, index=False)
    print(f"\nSaved: {OUT}")

    # spot-check Fulton County GA
    fc = merged[(merged["state_abbr"] == "GA") & (merged["county_name"] == "Fulton")]
    if not fc.empty:
        print("\nSpot-check — Fulton County, GA:")
        print(fc[["county_name","venue_rating","fips","population",
                   "median_hh_income","pct_bachelors_plus","pop_density_sqmi","urban_class"]].to_string(index=False))
