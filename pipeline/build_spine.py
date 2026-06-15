"""
Reads Harmonie_VenueMap_Counties_2025.xlsx and produces data/processed/spine.csv.
Each state sheet: row 0 = state header (skipped), rows 1+ = county data.
Columns: state_abbr, county_name, venue_rating
"""

import pathlib
import pandas as pd

RAW = pathlib.Path(__file__).parent.parent / "data" / "raw" / "Harmonie_VenueMap_Counties_2025.xlsx"
OUT = pathlib.Path(__file__).parent.parent / "data" / "processed" / "spine.csv"

RATING_MAP = {
    "plaintiff oriented": "Plaintiff",
    "plaintiff":          "Plaintiff",
    "plantiff":           "Plaintiff",   # typo in source
    "defense oriented":   "Defense",
    "defense":            "Defense",
    "neutral":            "Neutral",
}

def normalize_rating(raw: str) -> str:
    if not isinstance(raw, str):
        return None
    return RATING_MAP.get(raw.strip().lower())


def build_spine() -> pd.DataFrame:
    xl = pd.ExcelFile(RAW)
    rows = []

    for sheet in xl.sheet_names:
        if sheet.strip().lower() == "master":
            continue

        df = xl.parse(sheet, header=None)
        # drop fully-empty rows
        df = df.dropna(how="all")
        if df.empty:
            continue

        state_abbr = sheet.strip()

        # row 0 is the state header row — skip it
        for _, row in df.iloc[1:].iterrows():
            county = row.iloc[0]
            rating_raw = row.iloc[1]

            if not isinstance(county, str) or not county.strip():
                continue

            county = county.strip()
            rating = normalize_rating(rating_raw)

            if rating is None:
                print(f"  WARN: unrecognized rating {rating_raw!r} for {state_abbr} / {county}")
                continue

            rows.append({"state_abbr": state_abbr, "county_name": county, "venue_rating": rating})

    return pd.DataFrame(rows)


if __name__ == "__main__":
    spine = build_spine()

    print(f"Total rows:      {len(spine)}")
    print(f"Unique ratings:  {sorted(spine['venue_rating'].unique())}")
    print(f"States:          {spine['state_abbr'].nunique()}")

    # sanity checks
    dupes = spine[spine.duplicated(subset=["state_abbr", "county_name"], keep=False)]
    if not dupes.empty:
        print(f"  WARN: {len(dupes)} duplicate (state, county) pairs")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    spine.to_csv(OUT, index=False)
    print(f"Saved: {OUT}")
