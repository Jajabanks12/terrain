"""
Builds db/terrain.db from all processed CSV files.

Tables:
  counties    — one row per county, all data sources joined on FIPS
  legislation — one row per LegiScan bill, joined by state_abbr

Re-run this script any time you refresh a data source CSV.
"""

import pathlib, sqlite3
import pandas as pd

ROOT = pathlib.Path(__file__).parent.parent
PROC = ROOT / "data" / "processed"
DB   = ROOT / "db" / "terrain.db"

DB.parent.mkdir(parents=True, exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def load(filename: str, **kwargs) -> pd.DataFrame:
    path = PROC / filename
    if not path.exists():
        print(f"  WARN: {filename} not found — skipping")
        return pd.DataFrame()
    df = pd.read_csv(path, dtype=str, **kwargs)
    print(f"  {filename}: {len(df):,} rows, {len(df.columns)} cols")
    return df


def to_numeric_cols(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# ── load all sources ──────────────────────────────────────────────────────────

print("Loading CSVs...")
spine   = load("spine_with_fips.csv")
census  = load("census.csv")
nhtsa   = load("nhtsa.csv")
cdc     = load("cdc_alcohol.csv")
cbp     = load("cbp.csv")
legi    = load("legiscan.csv")

# FBI may not exist yet if the background job hasn't finished
fbi_path = PROC / "fbi_crime.csv"
fbi = load("fbi_crime.csv") if fbi_path.exists() else pd.DataFrame()


# ── build counties table ──────────────────────────────────────────────────────

print("\nJoining counties table...")

# Start from spine (authoritative list of counties)
counties = spine[["state_abbr", "county_name", "venue_rating", "fips"]].copy()

def dedup_fips(df: pd.DataFrame, prefer_col: str | None = None) -> pd.DataFrame:
    """Drop duplicate FIPS rows (CT judicial districts share county FIPS)."""
    if prefer_col and prefer_col in df.columns:
        df = df.copy()
        df[prefer_col] = pd.to_numeric(df[prefer_col], errors="coerce")
        df = df.sort_values(prefer_col, ascending=False)
    return df.drop_duplicates(subset="fips", keep="first")


# Census
if not census.empty:
    census_cols = [
        "fips", "population", "median_hh_income", "pct_bachelors_plus",
        "ALAND_SQMI", "pop_density_sqmi", "urban_class",
    ]
    census_cols = [c for c in census_cols if c in census.columns]
    counties = counties.merge(dedup_fips(census[census_cols]), on="fips", how="left")

# FBI crime
if not fbi.empty:
    fbi_cols = [c for c in fbi.columns
                if c in ("fips","violent_crime_rate","robbery_rate","data_flag")]
    if fbi_cols:
        counties = counties.merge(fbi[fbi_cols], on="fips", how="left")

# NHTSA — deduplicate on FIPS first (CT judicial districts share county FIPS)
if not nhtsa.empty:
    nhtsa_cols = [
        "fips", "total_crashes", "total_fatalities",
        "alcohol_crashes", "pct_alcohol", "fatality_rate_per_100k",
    ]
    nhtsa_cols = [c for c in nhtsa_cols if c in nhtsa.columns]
    nhtsa_dedup = (
        nhtsa[nhtsa_cols]
        .copy()
        .assign(total_crashes=lambda d: pd.to_numeric(d["total_crashes"], errors="coerce"))
        .sort_values("total_crashes", ascending=False)
        .drop_duplicates(subset="fips", keep="first")
    )
    counties = counties.merge(nhtsa_dedup, on="fips", how="left")

# CDC alcohol
if not cdc.empty:
    cdc_cols = ["fips", "binge_drinking_pct", "binge_drinking_ci_lo", "binge_drinking_ci_hi"]
    cdc_cols = [c for c in cdc_cols if c in cdc.columns]
    counties = counties.merge(dedup_fips(cdc[cdc_cols]), on="fips", how="left")

# CBP business counts
if not cbp.empty:
    cbp_cols = [
        "fips",
        "drinking_places_estab", "drinking_places_suppressed",
        "restaurants_fullsvc_estab", "restaurants_fullsvc_suppressed",
        "truck_transportation_estab", "truck_transportation_suppressed",
    ]
    cbp_cols = [c for c in cbp_cols if c in cbp.columns]
    counties = counties.merge(dedup_fips(cbp[cbp_cols]), on="fips", how="left")

# Coerce numeric columns
num_cols = [
    "population", "median_hh_income", "pct_bachelors_plus",
    "ALAND_SQMI", "pop_density_sqmi",
    "violent_crime_rate", "robbery_rate",
    "total_crashes", "total_fatalities", "alcohol_crashes",
    "pct_alcohol", "fatality_rate_per_100k",
    "binge_drinking_pct", "binge_drinking_ci_lo", "binge_drinking_ci_hi",
    "drinking_places_estab", "restaurants_fullsvc_estab", "truck_transportation_estab",
]
counties = to_numeric_cols(counties, num_cols)

print(f"  counties table: {len(counties):,} rows x {len(counties.columns)} cols")


# ── build legislation table ───────────────────────────────────────────────────

print("\nBuilding legislation table...")
if not legi.empty:
    legislation = legi[[
        "bill_id", "state_abbr", "bill_number", "title",
        "status", "last_action_date", "last_action", "url", "matched_term",
    ]].copy()
    print(f"  legislation table: {len(legislation):,} rows x {len(legislation.columns)} cols")
else:
    legislation = pd.DataFrame()
    print("  WARN: legiscan.csv not found — legislation table will be empty")


# ── write to SQLite ───────────────────────────────────────────────────────────

print(f"\nWriting {DB} ...")
con = sqlite3.connect(DB)

counties.to_sql("counties", con, if_exists="replace", index=False)
print(f"  counties: {len(counties):,} rows written")

if not legislation.empty:
    legislation.to_sql("legislation", con, if_exists="replace", index=False)
    print(f"  legislation: {len(legislation):,} rows written")

# Add indexes for fast lookups
con.execute("CREATE INDEX IF NOT EXISTS idx_counties_fips        ON counties(fips)")
con.execute("CREATE INDEX IF NOT EXISTS idx_counties_state       ON counties(state_abbr)")
con.execute("CREATE INDEX IF NOT EXISTS idx_counties_rating      ON counties(venue_rating)")
con.execute("CREATE INDEX IF NOT EXISTS idx_legislation_state    ON legislation(state_abbr)")
con.execute("CREATE INDEX IF NOT EXISTS idx_legislation_status   ON legislation(status)")
con.commit()
con.close()
print("  Indexes created.")


# ── spot-check ────────────────────────────────────────────────────────────────

print("\nSpot-check — Fulton County, GA:")
con = sqlite3.connect(DB)
cur = con.execute("""
    SELECT state_abbr, county_name, venue_rating, fips,
           population, median_hh_income, pct_bachelors_plus, urban_class,
           total_crashes, fatality_rate_per_100k, pct_alcohol,
           binge_drinking_pct, drinking_places_estab, restaurants_fullsvc_estab
    FROM counties
    WHERE county_name = 'Fulton' AND state_abbr = 'GA'
""")
row = cur.fetchone()
if row:
    cols = [d[0] for d in cur.description]
    for col, val in zip(cols, row):
        print(f"  {col:<35} {val}")
else:
    print("  NOT FOUND")

print("\nLegislation sample (first 5):")
cur2 = con.execute("""
    SELECT state_abbr, bill_number, status, last_action_date, substr(title,1,70)
    FROM legislation ORDER BY last_action_date DESC LIMIT 5
""")
for r in cur2.fetchall():
    print(" ", r)

con.close()
print(f"\nDone. Database: {DB}")
