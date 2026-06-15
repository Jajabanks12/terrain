"""
Terrain — E&S Casualty County Risk Reference
Run: streamlit run app/streamlit_app.py
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

import streamlit as st
from streamlit_folium import st_folium
import pandas as pd

from app.db import (
    states, counties_for_state, county_detail,
    legislation_for_state, all_counties_ratings,
)
from app.map_utils import build_map
from app.news import fetch_state_news

# ── page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Terrain — County Risk",
    page_icon="🗺️",
    layout="wide",
)

st.markdown("""
<style>
/* ── Base ────────────────────────────────────────────────────────────────── */
.stApp { background-color: #ffffff; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #f8f9fb !important;
    border-right: 1px solid #e8edf2 !important;
}
[data-testid="stSidebar"] h1 {
    color: #165788 !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] small {
    color: #6b7a99 !important;
}

/* ── Dropdown selectors ──────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div {
    border-color: #e8edf2 !important;
    background-color: #ffffff !important;
    color: #1a1a2e !important;
}
[data-testid="stSelectbox"] > div > div:focus-within {
    border-color: #165788 !important;
    box-shadow: 0 0 0 2px rgba(22,87,136,0.15) !important;
}

/* ── Section expander headers ────────────────────────────────────────────── */
[data-testid="stExpander"] > details > summary {
    background-color: #f8f9fb !important;
    border-left: 3px solid #165788 !important;
    border-radius: 4px !important;
    padding: 8px 12px !important;
    color: #165788 !important;
    font-weight: 600 !important;
}
[data-testid="stExpander"] > details > summary:hover {
    background-color: #eef2f7 !important;
}
[data-testid="stExpander"] > details {
    border: 1px solid #e8edf2 !important;
    border-radius: 4px !important;
    box-shadow: 0 2px 8px rgba(22,87,136,0.06) !important;
}

/* ── Metric labels and values ────────────────────────────────────────────── */
[data-testid="stMetricLabel"] p {
    color: #6b7a99 !important;
    font-size: 0.8rem !important;
}
[data-testid="stMetricValue"] {
    color: #1a1a2e !important;
}

/* ── Headers ─────────────────────────────────────────────────────────────── */
h1, h2, h3 {
    color: #165788 !important;
}

/* ── Dividers ────────────────────────────────────────────────────────────── */
hr {
    border-color: #e8edf2 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Munich Re brand palette ───────────────────────────────────────────────────
MR_BLUE       = "#165788"
MR_BLUE2      = "#00538a"
MR_PANEL      = "#ffffff"
MR_LABEL      = "#6b7a99"
MR_TEXT       = "#1a1a2e"
MR_BORDER     = "#e8edf2"
MR_BG_LIGHT   = "#f8f9fb"
MR_GREEN      = "#2ecc71"
MR_AMBER      = "#f39c12"
MR_RED        = "#e74c3c"

RATING_COLORS = {"Plaintiff": MR_RED, "Neutral": "#a8b8cc", "Defense": MR_BLUE}
RATING_EMOJI  = {"Plaintiff": "🔴", "Neutral": "⚪", "Defense": "🔵"}

STATE_NAMES = {
    "AL":"Alabama","AK":"Alaska","AZ":"Arizona","AR":"Arkansas","CA":"California",
    "CO":"Colorado","CT":"Connecticut","DE":"Delaware","DC":"District of Columbia",
    "FL":"Florida","GA":"Georgia","HI":"Hawaii","ID":"Idaho","IL":"Illinois",
    "IN":"Indiana","IA":"Iowa","KS":"Kansas","KY":"Kentucky","LA":"Louisiana",
    "ME":"Maine","MD":"Maryland","MA":"Massachusetts","MI":"Michigan","MN":"Minnesota",
    "MS":"Mississippi","MO":"Missouri","MT":"Montana","NE":"Nebraska","NV":"Nevada",
    "NH":"New Hampshire","NJ":"New Jersey","NM":"New Mexico","NY":"New York",
    "NC":"North Carolina","ND":"North Dakota","OH":"Ohio","OK":"Oklahoma",
    "OR":"Oregon","PA":"Pennsylvania","RI":"Rhode Island","SC":"South Carolina",
    "SD":"South Dakota","TN":"Tennessee","TX":"Texas","UT":"Utah","VT":"Vermont",
    "VA":"Virginia","WA":"Washington","WV":"West Virginia","WI":"Wisconsin","WY":"Wyoming",
}


GLOSSARY = {
    "demographics": [
        ("Population", "Total number of residents in the county based on Census estimates."),
        ("Urban Class", "Whether the county is classified as Urban, Suburban, or Rural based on population density. Urban counties tend to produce larger jury awards than rural ones."),
        ("Median HH Income", "The midpoint household income in the county. Higher income areas can correlate with larger damages awards, particularly for lost wages and pain and suffering."),
        ("Pop. Density /mi²", "How many people live per square mile. Denser counties typically have higher claim frequency and larger jury pools drawn from more litigious urban environments."),
        ("Bachelor's Degree+", "Percentage of residents with at least a bachelor's degree. Education level is a factor in jury composition and how complex liability arguments are received."),
        ("Land Area (mi²)", "Total geographic size of the county in square miles."),
    ],
    "traffic": [
        ("Fatal Crashes", "Total number of crashes resulting in at least one fatality in the most recent available year."),
        ("Fatalities", "Total number of people killed in traffic crashes. A single crash can involve multiple fatalities."),
        ("Fatality Rate/100k", "Fatalities per 100,000 residents, normalizing for county population size. This is the most useful comparison metric across counties of different sizes."),
        ("Alcohol-Involved", "Percentage of fatal crashes where alcohol impairment was identified as a contributing factor. Key indicator for both Auto Liability and Liquor Liability exposure."),
    ],
    "alcohol": [
        ("Binge Drinking %", "Estimated percentage of adults who report binge drinking (4+ drinks per occasion for women, 5+ for men) in the past 30 days. Higher rates suggest greater behavioral risk for alcohol-related incidents and dram shop exposure."),
        ("95% CI (Confidence Interval)", "The range within which the true binge drinking percentage likely falls with 95% certainty. A wider range means less precise data for that county, typically due to smaller sample sizes in rural areas."),
    ],
    "business": [
        ("Bars / Drinking Places", "Number of licensed drinking establishments (NAICS 7224) operating in the county. Higher counts increase Liquor Liability exposure frequency."),
        ("Full-Svc Restaurants", "Number of full-service restaurants (NAICS 722511) in the county, many of which hold liquor licenses and carry dram shop exposure."),
        ("Trucking Firms", "Number of trucking and freight operations (NAICS 484) in the county. Directly relevant to Commercial Auto Liability frequency."),
        ("Suppressed", "Census suppresses business counts in counties where reporting the number would identify a specific business, typically very small counties. This is a data privacy measure, not a data error."),
    ],
    "venue": [
        ("Defense Oriented", "Local courts and juries have historically favored defendants. Claims in these counties tend to settle lower and produce smaller verdicts."),
        ("Neutral", "Mixed track record with no strong lean toward plaintiffs or defendants. Outcomes depend more heavily on case-specific facts."),
        ("Plaintiff Oriented", "Local courts and juries have historically favored plaintiffs. These counties carry higher risk of large verdicts, nuclear outcomes, and aggressive litigation tactics."),
        ("FIPS Code", "Federal Information Processing Standards code — a unique 5-digit government identifier for every US county (first 2 digits = state, last 3 = county). Used to join data across government sources."),
    ],
}


def glossary_expander(section_key: str) -> None:
    """Renders a compact ℹ️ glossary expander for the given section."""
    terms = GLOSSARY.get(section_key, [])
    if not terms:
        return
    with st.expander("ℹ️ What do these mean?"):
        for term, definition in terms:
            st.markdown(
                f"<span style='color:#1a1a2e;font-weight:600'>{term}</span>"
                f"<span style='color:#6b7a99'> — {definition}</span>",
                unsafe_allow_html=True,
            )


def fmt(val, prefix="", suffix="", decimals=1, fallback="—"):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return fallback
    if isinstance(val, float):
        return f"{prefix}{val:,.{decimals}f}{suffix}"
    return f"{prefix}{val:,}{suffix}"


def _risk_level(val, low: float, high: float):
    """Returns (color, label) tuple for a numeric value against thresholds."""
    if val < low:
        return MR_GREEN, "Below Avg"
    elif val <= high:
        return MR_AMBER, "Avg"
    else:
        return MR_RED, "Elevated"


def _badge(color: str, label: str) -> str:
    return (
        f"<span style='background:{color};color:#fff;font-size:0.68rem;"
        f"padding:2px 8px;border-radius:10px;font-weight:700;"
        f"vertical-align:middle;margin-left:6px;'>{label}</span>"
    )


def risk_metric(col, label: str, val, low: float, high: float, suffix: str = "") -> None:
    """Renders a branded metric card with inline risk badge into the given column."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        val_html = "<span style='color:#6b7a99'>—</span>"
    else:
        color, tag_label = _risk_level(val, low, high)
        val_html = f"<span style='color:#1a1a2e;font-size:1.35rem;font-weight:600'>{val:,.1f}{suffix}</span>{_badge(color, tag_label)}"
    col.markdown(
        f"<div style='padding:4px 0 8px 0'>"
        f"<div style='color:#6b7a99;font-size:0.78rem;font-weight:500;margin-bottom:3px'>{label}</div>"
        f"<div>{val_html}</div></div>",
        unsafe_allow_html=True,
    )


def risk_tag(val, low: float, high: float, fallback="—") -> str:
    """Plain-text fallback used for business density compound strings."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return fallback
    color, label = _risk_level(val, low, high)
    return f"{val:,.1f} {_badge(color, label)}"


# ── load data (cached) ────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def load_ratings():
    return all_counties_ratings()

@st.cache_data(show_spinner=False)
def load_states():
    return states()

@st.cache_data(ttl=300, show_spinner=False)   # cache 5 minutes per state
def load_news(state_name: str) -> list[dict]:
    return fetch_state_news(state_name)


# ── sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🗺️ Terrain")
    st.caption("E&S Casualty County Risk Reference")
    st.divider()

    state_list  = ["All States"] + load_states()
    sel_state   = st.selectbox("State", state_list, index=state_list.index("GA") if "GA" in state_list else 0)

    if sel_state == "All States":
        sel_county = None
    else:
        county_list = counties_for_state(sel_state)
        sel_county  = st.selectbox("County", county_list, index=county_list.index("Fulton") if "Fulton" in county_list else 0)

    st.divider()
    st.caption("Data sources: Harmonie • Census ACS • NHTSA FARS • CDC PLACES • CBP • LegiScan")
    st.markdown(
        "<p style='color:#6b7a99;font-size:0.72rem;margin-top:8px;'>Powered by Munich Re Specialty</p>",
        unsafe_allow_html=True,
    )


# ── main layout ───────────────────────────────────────────────────────────────
detail  = county_detail(sel_state, sel_county) if sel_county and sel_state != "All States" else None
ratings = load_ratings()

col_map, col_card = st.columns([3, 2], gap="large")

# ── MAP ───────────────────────────────────────────────────────────────────────
with col_map:
    st.subheader("Venue Rating Map")
    selected_fips = detail["fips"] if detail else None
    map_state = sel_state if sel_state != "All States" else None
    m = build_map(ratings, selected_fips=selected_fips, selected_state=map_state)
    st_folium(m, width=None, height=520, returned_objects=[])

# ── COUNTY CARD ───────────────────────────────────────────────────────────────
_show_card = sel_state != "All States" and detail is not None

with col_card:
    if sel_state == "All States":
        st.info("Select a state to view county details.")
    elif not detail:
        st.warning("County not found in database.")
    else:
        rating = detail.get("venue_rating", "Unknown")
        color  = RATING_COLORS.get(rating, "#888")
        emoji  = RATING_EMOJI.get(rating, "⚪")

        # ── state venue breakdown ─────────────────────────────────────────────
        state_ratings = ratings[ratings["state_abbr"] == sel_state]["venue_rating"]
        state_total   = len(state_ratings)
        state_counts  = state_ratings.value_counts()

        def pct(r):
            return round(state_counts.get(r, 0) / state_total * 100) if state_total else 0

        pct_d = pct("Defense")
        pct_n = pct("Neutral")
        pct_p = pct("Plaintiff")

        state_name = STATE_NAMES.get(sel_state, sel_state)
        breakdown_line = (
            f"{state_name}: {pct_d}% Defense&nbsp;/&nbsp;{pct_n}% Neutral&nbsp;/&nbsp;{pct_p}% Plaintiff"
        )

        # ── risk context badge ────────────────────────────────────────────────
        if rating == "Plaintiff":
            if pct_p < 20:
                badge_bg, badge_color, badge_text = MR_RED,   "white", "High Risk Venue — uncommon rating for this state"
            else:
                badge_bg, badge_color, badge_text = MR_AMBER, "white", "Plaintiff Oriented — common in this state's legal environment"
        else:
            badge_bg, badge_color, badge_text = MR_GREEN, "white", "Favorable Venue"

        st.markdown(
            f"""
            <div style="background:#ffffff;border-left:5px solid {color};
                        border:1px solid #e8edf2;border-left:5px solid {color};
                        padding:14px 18px;border-radius:6px;margin-bottom:8px;
                        box-shadow:0 2px 8px rgba(22,87,136,0.08);">
              <div style="font-size:1.35rem;font-weight:700;color:#1a1a2e;">
                {sel_county} County, {sel_state}
              </div>
              <div style="margin-top:4px;">
                <span style="display:inline-block;background:{color};color:#fff;
                             font-size:0.8rem;font-weight:700;padding:3px 10px;
                             border-radius:12px;">{rating} Venue</span>
                &nbsp;<span style="color:#6b7a99;font-size:.85rem;">FIPS {detail.get('fips','')}</span>
              </div>
              <div style="color:#6b7a99;font-size:.8rem;margin-top:6px;">{breakdown_line}</div>
            </div>
            <div style="display:inline-block;background:{badge_bg};color:{badge_color};
                        padding:4px 12px;border-radius:12px;font-size:.82rem;
                        font-weight:600;margin-bottom:12px;">
              {badge_text}
            </div>
            """,
            unsafe_allow_html=True,
        )
        glossary_expander("venue")

        # Demographics
        with st.expander("📊 Demographics", expanded=True):
            c1, c2 = st.columns(2)
            c1.metric("Population",        fmt(detail.get("population"), decimals=0))
            c2.metric("Urban Class",        detail.get("urban_class") or "—")
            c1.metric("Median HH Income",   fmt(detail.get("median_hh_income"), prefix="$", decimals=0))
            c2.metric("Pop. Density /mi²",  fmt(detail.get("pop_density_sqmi"), suffix=" ppl"))
            c1.metric("Bachelor's Degree+", fmt(detail.get("pct_bachelors_plus"), suffix="%"))
            c2.metric("Land Area (mi²)",    fmt(detail.get("ALAND_SQMI"), decimals=0))
        glossary_expander("demographics")

        # Traffic & Safety
        with st.expander("🚗 Traffic & Crash Stats (FARS 2022)", expanded=True):
            c1, c2 = st.columns(2)
            c1.metric("Fatal Crashes",  fmt(detail.get("total_crashes"), decimals=0))
            c2.metric("Fatalities",     fmt(detail.get("total_fatalities"), decimals=0))
            risk_metric(c1, "Fatality Rate/100k", detail.get("fatality_rate_per_100k"), low=10, high=18)
            risk_metric(c2, "Alcohol-Involved %", detail.get("pct_alcohol"), low=25, high=35)
        glossary_expander("traffic")

        # Alcohol
        with st.expander("🍺 Alcohol Prevalence (CDC PLACES 2023)", expanded=True):
            c1, c2 = st.columns(2)
            risk_metric(c1, "Binge Drinking %", detail.get("binge_drinking_pct"), low=14, high=20)
            ci_lo = detail.get("binge_drinking_ci_lo")
            ci_hi = detail.get("binge_drinking_ci_hi")
            if ci_lo and ci_hi:
                c2.metric("95% CI", f"{fmt(ci_lo)}% – {fmt(ci_hi)}%")
        glossary_expander("alcohol")

        # Crime (only show if FBI data loaded)
        vc = detail.get("violent_crime_rate")
        rob = detail.get("robbery_rate")
        if vc or rob:
            with st.expander("🚨 Crime Rates (FBI CDE, per 100k)", expanded=True):
                c1, c2 = st.columns(2)
                c1.metric("Violent Crime Rate", fmt(vc, suffix="/100k"))
                c2.metric("Robbery Rate",       fmt(rob, suffix="/100k"))
                flag = detail.get("data_flag")
                if flag and flag != "ok":
                    st.caption(f"⚠️ Data flag: {flag}")

        # Business density
        with st.expander("🏢 Business Density (CBP 2021)", expanded=True):
            c1, c2, c3 = st.columns(3)
            bars     = detail.get("drinking_places_estab")
            rests    = detail.get("restaurants_fullsvc_estab")
            trucks   = detail.get("truck_transportation_estab")
            bar_sup  = detail.get("drinking_places_suppressed")
            pop      = detail.get("population")

            def per10k(count):
                if count is None or pop is None or pd.isna(count) or pd.isna(pop) or pop == 0:
                    return None
                return float(count) / float(pop) * 10_000

            bars_rate   = per10k(bars)
            trucks_rate = per10k(trucks)

            if bar_sup:
                c1.markdown(
                    "<div style='padding:4px 0 8px 0'>"
                    "<div style='color:#6b7a99;font-size:0.78rem;font-weight:500;margin-bottom:3px'>Bars / Drinking Places</div>"
                    "<div style='color:#6b7a99;font-size:1rem;font-style:italic'>suppressed</div></div>",
                    unsafe_allow_html=True,
                )
            elif bars_rate is not None:
                bc, bl = _risk_level(bars_rate, 8, 15)
                c1.markdown(
                    f"<div style='padding:4px 0 8px 0'>"
                    f"<div style='color:#6b7a99;font-size:0.78rem;font-weight:500;margin-bottom:3px'>Bars / Drinking Places</div>"
                    f"<div style='color:#1a1a2e;font-size:1.35rem;font-weight:600'>{fmt(bars, decimals=0)}"
                    f"<span style='color:#6b7a99;font-size:0.8rem;font-weight:400'> estab</span>"
                    f"{_badge(bc, f'{bars_rate:.1f}/10k · {bl}')}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                c1.metric("Bars / Drinking Places", fmt(bars, decimals=0))

            c2.metric("Full-Svc Restaurants", fmt(rests, decimals=0))

            if trucks_rate is not None:
                tc, tl = _risk_level(trucks_rate, 3, 8)
                c3.markdown(
                    f"<div style='padding:4px 0 8px 0'>"
                    f"<div style='color:#6b7a99;font-size:0.78rem;font-weight:500;margin-bottom:3px'>Trucking Firms</div>"
                    f"<div style='color:#1a1a2e;font-size:1.35rem;font-weight:600'>{fmt(trucks, decimals=0)}"
                    f"<span style='color:#6b7a99;font-size:0.8rem;font-weight:400'> firms</span>"
                    f"{_badge(tc, f'{trucks_rate:.1f}/10k · {tl}')}</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                c3.metric("Trucking Firms", fmt(trucks, decimals=0))
        glossary_expander("business")


# ── NEWS FEED ─────────────────────────────────────────────────────────────────
if sel_state == "All States":
    st.stop()

st.divider()
news_col, legi_col = st.columns([1, 1], gap="large")

with news_col:
    state_name_full = STATE_NAMES.get(sel_state, sel_state)
    st.subheader(f"📰 Recent News — {state_name_full}")
    st.caption(
        f'Google News headlines for "{state_name_full}" filtered by insurance and litigation keywords: '
        "nuclear verdict, liability lawsuit, tort reform, dram shop, jury award, premises liability, wrongful death."
    )
    with st.spinner("Fetching headlines…"):
        headlines = load_news(state_name_full)

    if not headlines:
        st.caption("No recent headlines found. Try selecting a different state.")
    else:
        for item in headlines:
            source_str = f" &nbsp;·&nbsp; <span style='color:#6b7a99'>{item['source']}</span>" if item["source"] else ""
            date_str   = f" &nbsp;·&nbsp; <span style='color:#6b7a99;font-size:.8rem'>{item['date']}</span>" if item["date"] else ""
            st.markdown(
                f"<div style='padding:8px 0 8px 12px;border-left:3px solid #165788;"
                f"border-bottom:1px solid #e8edf2;margin-bottom:4px;'>"
                f"<a href='{item['link']}' target='_blank' "
                f"style='color:#1a1a2e;font-size:.9rem;font-weight:500;text-decoration:none;'>"
                f"{item['title']}</a><br>"
                f"<span style='font-size:.78rem'>{source_str}{date_str}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.markdown(
            "<p style='color:#6b7a99;font-size:.72rem;margin-top:8px;'>"
            "Results from Google News RSS. Keyword-based — expect occasional irrelevant articles. "
            "Cached for 5 minutes.</p>",
            unsafe_allow_html=True,
        )

# ── LEGISLATION ───────────────────────────────────────────────────────────────
with legi_col:
    st.subheader(f"⚖️ Tort Reform Legislation — {sel_state}")

    legi = legislation_for_state(sel_state)
    if legi.empty:
        st.info(f"No tracked tort reform legislation found for {sel_state} in the past 18 months.")
    else:
        STATUS_BADGE = {
            "Enacted":      "🟢",
            "Passed":       "🔵",
            "In Committee": "🟡",
            "Active":       "🟠",
            "Failed/Dead":  "⚫",
        }
        for _, row in legi.iterrows():
            badge = STATUS_BADGE.get(row["status"], "⚪")
            with st.container():
                st.markdown(
                    f"{badge} **{row['bill_number']}** &nbsp;·&nbsp; "
                    f"<span style='color:#6b7a99'>{row['status']}</span> &nbsp;·&nbsp; "
                    f"<span style='color:#6b7a99;font-size:.85rem'>{row['last_action_date']}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(row["title"])
                if row.get("last_action"):
                    st.caption(f"Last action: {row['last_action']}")
                if row.get("url"):
                    st.markdown(f"[View bill →]({row['url']})", unsafe_allow_html=False)
                st.markdown("---")
