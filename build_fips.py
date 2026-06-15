"""
build_fips.py  —  run from the project root
Downloads the Census county FIPS reference, merges it onto spine.csv,
and writes data/processed/spine_with_fips.csv.

Setup:
  1. Place spine.csv in data/processed/
  2. Add CENSUS_API_KEY=your_key to .env  (not needed for FIPS download,
     but kept here so the file is ready for ACS pulls)
  3. python build_fips.py
"""

import pathlib, io, zipfile, requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# ── paths ────────────────────────────────────────────────────────────────────
ROOT      = pathlib.Path(__file__).parent
RAW_DIR   = ROOT / "data" / "raw"
PROC_DIR  = ROOT / "data" / "processed"
FIPS_FILE = RAW_DIR  / "national_county.txt"
SPINE_IN  = PROC_DIR / "spine.csv"
OUT       = PROC_DIR / "spine_with_fips.csv"

# ── suffix pattern (do NOT strip standalone "city" — needed for independent
#    cities like Carson City NV and St. Louis city MO) ───────────────────────
SUFFIX_PAT = (
    r"\s+(county|parish|borough|census area|municipality"
    r"|city and borough|unified government|metropolitan government"
    r"|consolidated government)$"
)

# ── manual overrides: (STATE, spine_name_lower) -> census_key_lower ──────────
OVERRIDES = {
    # Connecticut judicial districts -> Census county
    ("CT", "bridgeport (fairfield judicial district)"):       "fairfield",
    ("CT", "danbury"):                                        "fairfield",
    ("CT", "hartford"):                                       "hartford",
    ("CT", "litchfield judicial district (torrington)"):      "litchfield",
    ("CT", "middlesex"):                                      "middlesex",
    ("CT", "new haven"):                                      "new haven",
    ("CT", "new london"):                                     "new london",
    ("CT", "norwalk (stamford/ norwalk judicial district)"):  "fairfield",
    ("CT", "tolland"):                                        "tolland",
    ("CT", "windham"):                                        "windham",
    ("CT", "new britain judicial district"):                  "hartford",
    ("CT", "waterbury judicial district"):                    "new haven",
    ("CT", "norwich ( new london judicial district)"):        "new london",
    ("CT", "meriden (middlesex judicial district"):           "middlesex",
    ("CT", "ansonia/milford judicial district"):              "new haven",
    # Alaska renamed/reshaped boroughs
    ("AK", "aleutians east"):                  "aleutians east",
    ("AK", "aleutians west"):                  "aleutians west",
    ("AK", "lake and peninsula"):              "lake and peninsula",
    ("AK", "prince of wales-outer ketchikan"): "prince of wales-hyder",
    ("AK", "skagway"):                         "skagway",
    ("AK", "wade hampton"):                    "wade hampton",
    ("AK", "wrangell"):                        "wrangell",
    ("AK", "yakutat"):                         "yakutat",
    # Hawaii districts -> Census county
    ("HI", "hilo"):     "hawaii",
    ("HI", "kahului"):  "maui",
    ("HI", "lana'i"):   "maui",
    ("HI", "lana'i"):   "maui",
    ("HI", "molokai"):  "maui",
    ("HI", "oahu"):     "honolulu",
    ("HI", "kaua'i"):   "kauai",   # straight apostrophe
    ("HI", "kaua’i"): "kauai",  # right single quotation mark (UTF-8 \xe2\x80\x99)
    # DC
    ("DC", "dc"):  "district of columbia",
    # Florida
    ("FL", "dade"):    "miami-dade",
    ("FL", "desoto"):  "desoto",
    # Illinois
    ("IL", "de witt"):  "de witt",
    ("IL", "la salle"): "lasalle",
    ("IL", "dekalb"):   "dekalb",
    # Indiana
    ("IN", "la porte"):  "laporte",
    ("IN", "de kalb"):   "dekalb",
    # Louisiana
    ("LA", "la salle"):  "la salle",
    # Maryland independent city
    ("MD", "baltimore city"):  "baltimore city",
    ("MD", "prince george's"): "prince george's",
    ("MD", "queen anne's"):    "queen anne's",
    # Minnesota
    ("MN", "lake of the wood"):  "lake of the woods",
    # Missouri independent city
    ("MO", "st. louis city"):  "st. louis city",
    ("MO", "de kalb"):         "dekalb",
    # Montana (not a real county; map to Yellowstone county)
    ("MT", "yellowstone national park"):  "yellowstone",
    # Nevada independent city
    ("NV", "carson city"):  "carson city",
    # New Mexico
    ("NM", "de baca"):  "de baca",
    # New York
    ("NY", "new york city"):  "new york",
    # Texas
    ("TX", "la salle"):  "la salle",
    ("TX", "de witt"):   "de witt",
    # Alabama / Georgia DeKalb
    ("AL", "de kalb"):  "dekalb",
    ("GA", "de kalb"):  "dekalb",
    # Mississippi
    ("MS", "de soto"):  "desoto",
    # Virginia independent cities
    ("VA", "chesapeake"):    "chesapeake city",
    ("VA", "hampton"):       "hampton city",
    ("VA", "newport news"):  "newport news city",
    ("VA", "suffolk"):       "suffolk city",
    ("VA", "virginia beach"): "virginia beach city",
    # Arkansas
    ("AR", "st. francis"):  "st. francis",
}


def download_fips():
    """Download national_county.txt from Census if not already present."""
    if FIPS_FILE.exists():
        print(f"FIPS file already present: {FIPS_FILE}")
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    url = "https://www2.census.gov/geo/docs/reference/codes/files/national_county.txt"
    print("Downloading Census FIPS reference...")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    FIPS_FILE.write_bytes(r.content)
    print(f"Saved: {FIPS_FILE}  ({len(r.content):,} bytes)")


def load_fips() -> pd.DataFrame:
    df = pd.read_csv(
        FIPS_FILE,
        header=None,
        names=["state_abbr", "state_fips", "county_fips", "county_name", "class"],
        dtype=str,
        encoding="latin-1",
    )
    df["fips"] = df["state_fips"] + df["county_fips"]
    df["county_key"] = (
        df["county_name"]
        .str.lower()
        .str.strip()
        .str.replace(SUFFIX_PAT, "", regex=True)
    )
    return df[["state_abbr", "county_key", "fips"]]


def merge(spine: pd.DataFrame, fips: pd.DataFrame) -> pd.DataFrame:
    lookup = {
        (r["state_abbr"].upper(), r["county_key"]): r["fips"]
        for _, r in fips.iterrows()
    }

    results, unmatched = [], []
    for _, row in spine.iterrows():
        state  = row["state_abbr"].strip().upper()
        county = row["county_name"].strip()
        key    = (state, county.lower())
        target = OVERRIDES.get(key, county.lower())
        code   = lookup.get((state, target))
        if code is None:
            unmatched.append((state, county))
        results.append({**row.to_dict(), "fips": code})

    if unmatched:
        print(f"\nWARN: {len(unmatched)} unmatched rows:")
        for s, c in sorted(unmatched):
            print(f"  ({s!r}, {c.lower()!r})")

    return pd.DataFrame(results)


if __name__ == "__main__":
    download_fips()

    spine  = pd.read_csv(SPINE_IN, dtype=str)
    fips   = load_fips()
    result = merge(spine, fips)

    missing = result["fips"].isna().sum()
    print(f"\nRows:         {len(result)}")
    print(f"With FIPS:    {(~result['fips'].isna()).sum()}")
    print(f"Missing FIPS: {missing}")

    PROC_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False)
    print(f"Saved: {OUT}")
