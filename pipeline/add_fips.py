"""
Merges FIPS codes onto spine.csv -> spine_with_fips.csv.
Join key: (state_abbr, county_key) where county_key = name lowercased, stripped,
with administrative suffixes removed (County, Parish, Borough, etc.) but NOT
standalone "City" — so "Carson City" and "St. Louis city" stay distinct.
Mismatches are resolved in OVERRIDES below.
"""

import pathlib
import pandas as pd

RAW_FIPS = pathlib.Path(__file__).parent.parent / "data" / "raw" / "national_county.txt"
SPINE    = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine.csv"
OUT      = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine_with_fips.csv"

# Suffix pattern — intentionally does NOT strip standalone "city" to keep
# independent cities (Carson City, St. Louis city) as distinct keys.
SUFFIX_PAT = (
    r"\s+(county|parish|borough|census area|municipality"
    r"|city and borough|unified government|metropolitan government"
    r"|consolidated government)$"
)

# Maps (state_abbr_upper, spine_county_lower) -> census_county_key_lower
# (i.e., Census name after lowercasing + suffix stripping).
OVERRIDES: dict[tuple[str, str], str] = {
    # ── Connecticut: uses judicial districts; map to Census county names ──
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

    # ── Alaska: older/renamed borough names ──
    ("AK", "aleutians east"):                   "aleutians east",
    ("AK", "aleutians west"):                   "aleutians west",
    ("AK", "lake and peninsula"):               "lake and peninsula",
    ("AK", "prince of wales-outer ketchikan"):  "prince of wales-hyder",
    ("AK", "skagway"):                          "skagway",
    ("AK", "wade hampton"):                     "wade hampton",   # still in Census 2020 file
    ("AK", "wrangell"):                         "wrangell",
    ("AK", "yakutat"):                          "yakutat",

    # ── Hawaii: Harmonie lists districts, not the 4 counties ──
    ("HI", "hilo"):      "hawaii",
    ("HI", "kahului"):   "maui",
    ("HI", "lana'i"):    "maui",
    ("HI", "molokai"):   "maui",
    ("HI", "oahu"):      "honolulu",
    ("HI", "kaua'i"):    "kauai",
    ("HI", "kaua’i"): "kauai",   # smart-quote variant

    # ── DC ──
    ("DC", "dc"):  "district of columbia",

    # ── Florida ──
    ("FL", "dade"):  "miami-dade",   # renamed 1997

    # ── Illinois ──
    ("IL", "de witt"):  "de witt",   # Census key after stripping "county"

    # ── Indiana ──
    ("IN", "la porte"):  "la porte",

    # ── Louisiana ──
    ("LA", "la salle"):  "la salle",   # Census key after stripping "parish"

    # ── Maryland: independent city ──
    ("MD", "baltimore city"):  "baltimore city",
    ("MD", "prince george's"): "prince george's",
    ("MD", "queen anne's"):    "queen anne's",

    # ── Minnesota ──
    ("MN", "lake of the wood"):  "lake of the woods",

    # ── Missouri: independent city ──
    ("MO", "st. louis city"):  "st. louis city",

    # ── Montana: not a real county; use Yellowstone county FIPS ──
    ("MT", "yellowstone national park"):  "yellowstone",

    # ── Nevada: independent city ──
    ("NV", "carson city"):  "carson city",

    # ── New Mexico ──
    ("NM", "de baca"):  "de baca",

    # ── New York: "New York City" rolled up -> New York (Manhattan) county ──
    ("NY", "new york city"):  "new york",

    # ── Texas ──
    ("TX", "la salle"):   "la salle",
    ("TX", "de witt"):    "de witt",

    # ── De Kalb spelling variants ──
    ("AL", "de kalb"):  "dekalb",
    ("GA", "de kalb"):  "dekalb",
    ("IL", "dekalb"):   "dekalb",
    ("IN", "de kalb"):  "dekalb",
    ("MO", "de kalb"):  "dekalb",

    # ── De Soto ──
    ("FL", "desoto"):   "desoto",
    ("MS", "de soto"):  "desoto",

    # ── La Salle (IL) ──
    ("IL", "la salle"):  "la salle",

    # ── Illinois ──
    ("IL", "la salle"):   "lasalle",

    # ── Indiana ──
    ("IN", "la porte"):   "laporte",

    # ── Virginia independent cities ──
    ("VA", "chesapeake"):    "chesapeake city",
    ("VA", "hampton"):       "hampton city",
    ("VA", "newport news"):  "newport news city",
    ("VA", "suffolk"):       "suffolk city",
    ("VA", "virginia beach"):"virginia beach city",

    # ── Misc St./Saint ──
    ("AR", "st. francis"):          "st. francis",
    ("MN", "st. louis"):            "st. louis",
    ("MO", "st. charles"):          "st. charles",
    ("MO", "st. clair"):            "st. clair",
    ("MO", "st. francois"):         "st. francois",
    ("MO", "st. louis"):            "st. louis",
    ("MO", "ste. genevieve"):       "ste. genevieve",
}


def load_fips() -> pd.DataFrame:
    df = pd.read_csv(
        RAW_FIPS,
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


def merge_fips(spine: pd.DataFrame, fips: pd.DataFrame) -> pd.DataFrame:
    fips_lookup: dict[tuple[str, str], str] = {
        (row["state_abbr"].upper(), row["county_key"]): row["fips"]
        for _, row in fips.iterrows()
    }

    results = []
    unmatched = []

    for _, row in spine.iterrows():
        state  = row["state_abbr"].strip().upper()
        county = row["county_name"].strip()
        key    = (state, county.lower())

        lookup_name = OVERRIDES.get(key, county.lower())
        fips_code   = fips_lookup.get((state, lookup_name))

        if fips_code is None:
            unmatched.append((state, county))

        results.append({**row.to_dict(), "fips": fips_code})

    if unmatched:
        print(f"\n  {len(unmatched)} UNMATCHED (need overrides):")
        for s, c in sorted(unmatched):
            print(f"    ({s!r}, {c.lower()!r})")

    return pd.DataFrame(results)


if __name__ == "__main__":
    spine  = pd.read_csv(SPINE, dtype=str)
    fips   = load_fips()
    merged = merge_fips(spine, fips)

    missing = merged["fips"].isna().sum()
    print(f"\nTotal rows:   {len(merged)}")
    print(f"With FIPS:    {(~merged['fips'].isna()).sum()}")
    print(f"Missing FIPS: {missing}")

    if missing == 0:
        merged.to_csv(OUT, index=False)
        print(f"Saved: {OUT}")
    else:
        print("Fix unmatched rows above, then re-run.")
