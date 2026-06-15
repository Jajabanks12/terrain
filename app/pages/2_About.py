"""
Terrain — About & Methodology
Explains data sources, refresh cadence, and known limitations.
"""

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(
    page_title="About — Terrain",
    page_icon="📋",
    layout="wide",
)

# ── Munich Re brand CSS (mirrors streamlit_app.py) ───────────────────────────
st.markdown("""
<style>
[data-testid="stSidebar"] {
    background-color: #0e1117 !important;
    border-right: 2px solid #165788;
}
[data-testid="stSidebar"] h1 { color: #165788 !important; }
[data-testid="stSidebar"] .stCaption, [data-testid="stSidebar"] small {
    color: #8b9ab0 !important;
}
h1, h2, h3 { color: #165788 !important; }
.about-card {
    background: #1c2333;
    border-left: 3px solid #165788;
    border-radius: 4px;
    padding: 16px 20px;
    margin-bottom: 16px;
}
.about-card h4 { color: #165788; margin: 0 0 6px 0; font-size: 1rem; }
.about-card p, .about-card li { color: #c8d0db; font-size: 0.9rem; line-height: 1.6; }
.about-card ul { margin: 6px 0 0 0; padding-left: 18px; }
.limit-card {
    background: #1c2333;
    border-left: 3px solid #e74c3c;
    border-radius: 4px;
    padding: 16px 20px;
    margin-bottom: 12px;
}
.limit-card h4 { color: #e74c3c; margin: 0 0 6px 0; font-size: 0.95rem; }
.limit-card p, .limit-card li { color: #c8d0db; font-size: 0.88rem; line-height: 1.6; }
.limit-card ul { margin: 6px 0 0 0; padding-left: 18px; }
.label { color: #8b9ab0; font-size: 0.78rem; font-weight: 600;
         text-transform: uppercase; letter-spacing: 0.05em; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📋 About Terrain")
st.markdown(
    "<p style='color:#8b9ab0;font-size:1rem;margin-top:-8px;'>"
    "Methodology, data sources, refresh cadence, and known limitations.</p>",
    unsafe_allow_html=True,
)
st.divider()

# ── Purpose ──────────────────────────────────────────────────────────────────
st.subheader("Purpose")
st.markdown("""
Terrain is a county-level risk reference tool built for **E&S casualty underwriting**.
It aggregates public data across five dimensions — venue rating, demographics, traffic safety,
alcohol prevalence, and business density — to give underwriters a single, structured view of
the litigation environment and behavioral risk factors in any US county.

It is designed to supplement, not replace, underwriter judgment. The data describes historical
conditions and statistical averages; individual accounts may differ materially based on
operations, coverage structure, and case-specific facts.
""")

st.divider()

# ── Data Sources ─────────────────────────────────────────────────────────────
st.subheader("Data Sources & Methodology")

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("""
    <div class="about-card">
      <h4>⚖️ Venue Rating — Harmonie Group VenueMap</h4>
      <p><span class="label">Coverage</span><br>
      3,117 US counties rated Defense, Neutral, or Plaintiff Oriented based on
      Harmonie member law firm assessments of local court and jury behavior.</p>
      <p><span class="label">Methodology</span><br>
      Ratings reflect the consensus view of defense counsel practicing in each jurisdiction.
      A Plaintiff rating indicates a court environment historically favorable to claimants —
      higher settlement values, more plaintiff-friendly juries, and greater nuclear verdict risk.
      Defense counties produce lower verdicts and more favorable claim resolution patterns.</p>
      <p><span class="label">Refresh</span><br>
      Harmonie publishes updates periodically. The current dataset reflects the 2025 VenueMap release.
      Re-run <code>pipeline/build_spine.py</code> with a new export to update.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
      <h4>👥 Demographics — US Census Bureau ACS 5-Year Estimates</h4>
      <p><span class="label">Coverage</span><br>
      All 3,117 counties. Variables: total population, median household income,
      educational attainment (bachelor's degree or higher), land area, and population density.</p>
      <p><span class="label">Methodology</span><br>
      American Community Survey 5-year estimates (2022 vintage) via the Census API.
      5-year estimates pool survey responses to improve reliability for small counties.
      Urban/Suburban/Rural classification is derived from population density thresholds:
      Urban ≥ 1,000/mi², Suburban ≥ 100/mi², Rural below 100/mi².</p>
      <p><span class="label">Refresh</span><br>
      Census releases new ACS 5-year estimates annually (December).
      Re-run <code>pipeline/fetch_census.py</code> to update.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
      <h4>🚗 Traffic Safety — NHTSA FARS 2022</h4>
      <p><span class="label">Coverage</span><br>
      All counties with at least one fatal crash in 2022. Counties with zero recorded
      fatal crashes show no data (not zero — the distinction matters for rural counties
      with small populations).</p>
      <p><span class="label">Methodology</span><br>
      Fatality Analysis Reporting System (FARS) annual bulk download.
      Fatal crashes are aggregated by county FIPS. Alcohol involvement is flagged at
      the vehicle level (DR_DRINK = 1) and rolled up to the crash level.
      Fatality rate per 100k is computed against ACS population estimates.</p>
      <p><span class="label">Refresh</span><br>
      NHTSA releases FARS annually with approximately an 18-month lag.
      Re-run <code>pipeline/fetch_nhtsa.py</code> when a new annual file is available.</p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div class="about-card">
      <h4>🍺 Alcohol Prevalence — CDC PLACES 2023</h4>
      <p><span class="label">Coverage</span><br>
      All 3,142 US counties (including some not in the Harmonie spine).
      Joined to Terrain by FIPS code.</p>
      <p><span class="label">Methodology</span><br>
      CDC PLACES modeled estimates of binge drinking prevalence among adults, derived from
      Behavioral Risk Factor Surveillance System (BRFSS) survey data combined with
      census-level small area estimation. Binge drinking is defined as 4+ drinks
      per occasion for women, 5+ for men, in the past 30 days.
      Confidence intervals reflect model precision — wider CI in rural counties
      due to smaller effective sample sizes.</p>
      <p><span class="label">Refresh</span><br>
      CDC PLACES releases updated estimates annually.
      Re-run <code>pipeline/fetch_cdc_alcohol.py</code> to update.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
      <h4>🏢 Business Density — Census County Business Patterns 2021</h4>
      <p><span class="label">Coverage</span><br>
      All counties. Three NAICS codes tracked:</p>
      <ul>
        <li><b>7224</b> — Drinking Places (Alcoholic Beverages)</li>
        <li><b>722511</b> — Full-Service Restaurants</li>
        <li><b>484</b> — Truck Transportation</li>
      </ul>
      <p><span class="label">Methodology</span><br>
      Annual establishment counts from the Census Bureau's County Business Patterns survey.
      Per-10k-resident rates are computed for bars and trucking firms to normalize across
      county population sizes. Census suppresses counts in counties where disclosure
      would identify a specific business (typically fewer than 3 establishments).</p>
      <p><span class="label">Refresh</span><br>
      CBP releases with roughly a 2-year lag. Current data is 2021.
      Re-run <code>pipeline/fetch_cbp.py</code> to update.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="about-card">
      <h4>⚖️ Tort Reform Legislation — LegiScan API</h4>
      <p><span class="label">Coverage</span><br>
      State-level legislation tracked across all 50 states + DC.
      Filtered to bills with LegiScan relevance score ≥ 70 and last action within 18 months.</p>
      <p><span class="label">Methodology</span><br>
      LegiScan full-text search across four tort reform search terms:
      "tort reform," "dram shop liability," "punitive damages cap," and
      "joint and several liability reform." Bills are further filtered by title keywords
      to exclude false positives. Status (Enacted, Passed, In Committee, Active, Failed/Dead)
      is derived from the last action text since LegiScan search results do not return
      status codes directly.</p>
      <p><span class="label">Refresh</span><br>
      Re-run <code>pipeline/fetch_legiscan.py</code> at any time to pull current legislative activity.
      The 18-month cutoff ensures only recent bills appear.</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ── National Benchmarks ───────────────────────────────────────────────────────
st.subheader("National Benchmark Thresholds")
st.markdown(
    "<p style='color:#8b9ab0'>Risk indicators on the county profile page use these thresholds, "
    "derived from national averages in the underlying data sources.</p>",
    unsafe_allow_html=True,
)

b1, b2, b3, b4, b5 = st.columns(5)
for col, label, green, yellow, red in [
    (b1, "Binge Drinking %",         "< 14%",   "14–20%",  "> 20%"),
    (b2, "Alcohol-Involved Crashes %","< 25%",   "25–35%",  "> 35%"),
    (b3, "Fatality Rate / 100k",      "< 10",    "10–18",   "> 18"),
    (b4, "Bars per 10k Residents",    "< 8",     "8–15",    "> 15"),
    (b5, "Trucking Firms per 10k",    "< 3",     "3–8",     "> 8"),
]:
    col.markdown(
        f"<div style='background:#1c2333;border-radius:4px;padding:12px;'>"
        f"<div style='color:#8b9ab0;font-size:0.75rem;font-weight:600;margin-bottom:8px'>{label}</div>"
        f"<div style='color:#2ecc71;font-size:0.82rem;margin-bottom:3px'>🟢 Below Avg: {green}</div>"
        f"<div style='color:#f39c12;font-size:0.82rem;margin-bottom:3px'>🟡 Avg: {yellow}</div>"
        f"<div style='color:#e74c3c;font-size:0.82rem'>🔴 Elevated: {red}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Known Limitations ─────────────────────────────────────────────────────────
st.subheader("Known Limitations & Data Gaps")

lim1, lim2 = st.columns(2, gap="large")

with lim1:
    st.markdown("""
    <div class="limit-card">
      <h4>FBI Crime Data — Partial or Missing</h4>
      <p>The FBI Crime Data Explorer (CDE) API provides violent crime and robbery rates at the
      county level, but coverage is incomplete. Not all agencies report to the FBI's UCR program,
      and reporting formats changed significantly with the NIBRS transition in 2021.
      Many counties — particularly in states like California, Florida, and New York —
      have gaps or suppressed values. Where FBI data is unavailable, the Crime Rates
      section is hidden rather than showing zero, which would be misleading.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="limit-card">
      <h4>Liquor Licensing Data — Not Included</h4>
      <p>State liquor licensing databases would provide a more precise count of
      dram shop exposure than CBP establishment counts, which capture industry type
      but not license status. Georgia's GDOR liquor license database, for example,
      is publicly available but requires county-level parsing and is not yet integrated.
      CBP bar counts should be treated as a directional proxy, not a precise exposure count.
      Licensed establishments with liquor liability exposure in full-service restaurants
      and private clubs are partially captured under NAICS 722511 but not fully enumerated.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="limit-card">
      <h4>CBP Suppression in Rural Counties</h4>
      <p>Census suppresses business establishment counts when the count is small enough
      to identify a specific business. This disproportionately affects rural counties
      with few bars or trucking firms. Suppressed values are flagged as "suppressed"
      rather than shown as zero — zero would imply no establishments exist, which is
      not what suppression means. In practice, suppression thresholds are typically
      triggered at 1–3 establishments per NAICS code per county.</p>
    </div>
    """, unsafe_allow_html=True)

with lim2:
    st.markdown("""
    <div class="limit-card">
      <h4>Venue Ratings — Subjective and Lagging</h4>
      <p>Harmonie venue ratings reflect member law firm consensus at a point in time.
      Jurisdictions can shift meaningfully between rating cycles — a county rated
      Neutral may have trended Plaintiff in recent years as jury composition, judicial
      appointments, or local economic conditions change. Ratings should be cross-referenced
      against recent verdict research for large or complex accounts.
      Additionally, some counties with limited defense firm presence may have fewer
      data points underlying their rating than high-activity metro counties.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="limit-card">
      <h4>FARS Data Lag and Zero-Crash Counties</h4>
      <p>NHTSA FARS data carries an approximately 18-month publication lag — the 2022
      dataset was the most recent available at build time. Counties with no recorded
      fatal crashes in 2022 show no traffic data rather than zero, which could
      understate risk in counties where fatal crashes occur sporadically. Very small,
      rural counties may have years with zero FARS entries followed by years with
      outsized rates due to a single multi-fatality event.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="limit-card">
      <h4>LegiScan Coverage and False Positives</h4>
      <p>LegiScan tracks state legislation but does not cover federal bills, local ordinances,
      or regulatory changes that can affect tort exposure (e.g., dram shop liability
      thresholds set by state alcohol control boards rather than the legislature).
      The relevance filter (≥ 70) and title keyword filter reduce but do not eliminate
      false positives — some tracked bills may address tangential legal topics.
      Bills that died in committee in prior sessions are excluded via the 18-month
      recency cutoff but may still be relevant as precedent for future legislative sessions.</p>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown(
    "<p style='color:#8b9ab0;font-size:0.8rem;'>"
    "Terrain is an internal underwriting reference tool. Data is provided as-is from public sources. "
    "It does not constitute legal advice or a binding risk assessment. "
    "All underwriting decisions remain with the underwriter of record.<br><br>"
    "<b style='color:#165788'>Powered by Munich Re Specialty</b> &nbsp;·&nbsp; "
    "Built with Python, Streamlit, and SQLite."
    "</p>",
    unsafe_allow_html=True,
)
