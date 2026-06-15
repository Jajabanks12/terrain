"""Database query helpers for the Terrain app."""

import pathlib, sqlite3
import pandas as pd

DB = pathlib.Path(__file__).parent.parent / "db" / "terrain.db"


def _con() -> sqlite3.Connection:
    return sqlite3.connect(DB)


def counties_summary() -> pd.DataFrame:
    """All counties with just the columns needed for the map / dropdowns."""
    return pd.read_sql(
        "SELECT fips, state_abbr, county_name, venue_rating FROM counties ORDER BY state_abbr, county_name",
        _con(),
    )


def states() -> list[str]:
    con = _con()
    rows = con.execute("SELECT DISTINCT state_abbr FROM counties ORDER BY state_abbr").fetchall()
    return [r[0] for r in rows]


def counties_for_state(state: str) -> list[str]:
    con = _con()
    rows = con.execute(
        "SELECT county_name FROM counties WHERE state_abbr = ? ORDER BY county_name",
        (state,),
    ).fetchall()
    return [r[0] for r in rows]


def county_detail(state: str, county: str) -> dict | None:
    con = _con()
    cur = con.execute(
        "SELECT * FROM counties WHERE state_abbr = ? AND county_name = ?",
        (state, county),
    )
    row = cur.fetchone()
    if not row:
        return None
    return dict(zip([d[0] for d in cur.description], row))


def legislation_for_state(state: str) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT bill_number, title, status, last_action_date, last_action, url, matched_term "
        "FROM legislation WHERE state_abbr = ? ORDER BY last_action_date DESC",
        _con(),
        params=(state,),
    )


def all_counties_ratings() -> pd.DataFrame:
    """FIPS + state_abbr + venue_rating for the choropleth and state breakdowns."""
    return pd.read_sql(
        "SELECT fips, state_abbr, venue_rating FROM counties",
        _con(),
    )
