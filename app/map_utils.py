"""Builds the Folium choropleth map."""

import json, pathlib
import folium
import pandas as pd

GEOJSON = pathlib.Path(__file__).parent.parent / "data" / "raw" / "counties_geojson.json"

COLORS = {
    "Plaintiff": "#e74c3c",   # risk red
    "Neutral":   "#a8b8cc",   # light blue-grey (readable on white basemap)
    "Defense":   "#165788",   # Munich Re primary blue
}
COLOR_FALLBACK = "#c8d4e0"
COLOR_GRAY     = "#dde4ec"   # out-of-state counties (light, unobtrusive on white)

# state_abbr -> (center_lat, center_lon, zoom_level, 2-digit fips prefix)
STATE_INFO: dict[str, tuple[float, float, int, str]] = {
    "AL": (32.8, -86.8, 6, "01"), "AK": (64.2, -153.4, 4, "02"),
    "AZ": (34.3, -111.1, 6, "04"), "AR": (34.8, -92.4, 6, "05"),
    "CA": (37.2, -119.5, 5, "06"), "CO": (39.0, -105.5, 6, "08"),
    "CT": (41.6, -72.7, 8, "09"), "DE": (39.0, -75.5, 8, "10"),
    "DC": (38.9, -77.0, 10, "11"), "FL": (27.8, -83.7, 6, "12"),
    "GA": (32.7, -83.4, 6, "13"), "HI": (20.3, -156.4, 7, "15"),
    "ID": (44.4, -114.6, 5, "16"), "IL": (40.0, -89.2, 6, "17"),
    "IN": (40.0, -86.1, 6, "18"), "IA": (42.1, -93.5, 6, "19"),
    "KS": (38.5, -98.4, 6, "20"), "KY": (37.5, -85.3, 6, "21"),
    "LA": (31.2, -91.8, 6, "22"), "ME": (45.4, -69.0, 6, "23"),
    "MD": (39.1, -76.8, 7, "24"), "MA": (42.3, -71.8, 7, "25"),
    "MI": (44.3, -85.4, 6, "26"), "MN": (46.4, -93.1, 5, "27"),
    "MS": (32.7, -89.7, 6, "28"), "MO": (38.5, -92.5, 6, "29"),
    "MT": (47.0, -110.0, 5, "30"), "NE": (41.5, -99.9, 6, "31"),
    "NV": (39.3, -116.6, 6, "32"), "NH": (43.7, -71.6, 7, "33"),
    "NJ": (40.1, -74.5, 7, "34"), "NM": (34.5, -106.1, 6, "35"),
    "NY": (42.9, -75.5, 6, "36"), "NC": (35.6, -79.4, 6, "37"),
    "ND": (47.5, -100.5, 6, "38"), "OH": (40.4, -82.8, 6, "39"),
    "OK": (35.6, -97.5, 6, "40"), "OR": (43.9, -120.6, 6, "41"),
    "PA": (40.9, -77.8, 6, "42"), "RI": (41.7, -71.6, 9, "44"),
    "SC": (33.9, -80.9, 6, "45"), "SD": (44.4, -100.2, 6, "46"),
    "TN": (35.9, -86.4, 6, "47"), "TX": (31.5, -99.3, 5, "48"),
    "UT": (39.3, -111.1, 6, "49"), "VT": (44.0, -72.7, 7, "50"),
    "VA": (37.5, -78.5, 6, "51"), "WA": (47.4, -120.5, 6, "53"),
    "WV": (38.6, -80.6, 6, "54"), "WI": (44.5, -89.8, 6, "55"),
    "WY": (43.0, -107.6, 6, "56"),
}


def build_map(
    ratings: pd.DataFrame,
    selected_fips: str | None = None,
    selected_state: str | None = None,
) -> folium.Map:
    """
    ratings: DataFrame with columns [fips, venue_rating]
    selected_fips:  highlights the selected county border
    selected_state: zooms to state and grays out all other counties
    """
    fips_color = {
        str(row["fips"]).zfill(5): COLORS.get(row["venue_rating"], COLOR_FALLBACK)
        for _, row in ratings.iterrows()
    }

    with open(GEOJSON) as f:
        geo = json.load(f)

    if selected_state and selected_state in STATE_INFO:
        lat, lon, zoom, state_prefix = STATE_INFO[selected_state]
    else:
        lat, lon, zoom, state_prefix = 38.5, -96.0, 4, None

    m = folium.Map(
        location=[lat, lon],
        zoom_start=zoom,
        tiles="CartoDB positron",
        prefer_canvas=True,
    )

    sel_fips_str = str(selected_fips).zfill(5) if selected_fips else None

    def style_fn(feature):
        fips = feature["id"]
        is_selected = sel_fips_str and fips == sel_fips_str

        if state_prefix and not fips.startswith(state_prefix):
            return {
                "fillColor":   COLOR_GRAY,
                "color":       "#bbbbbb",
                "weight":      0.2,
                "fillOpacity": 0.4,
            }

        color = fips_color.get(fips, COLOR_FALLBACK)
        return {
            "fillColor":   color,
            "color":       "#333333" if is_selected else "#555555",
            "weight":      2.5 if is_selected else 0.3,
            "fillOpacity": 0.85 if is_selected else 0.7,
        }

    folium.GeoJson(
        geo,
        style_function=style_fn,
        tooltip=folium.GeoJsonTooltip(
            fields=["NAME"],
            aliases=["County:"],
            localize=True,
        ),
    ).add_to(m)

    # Legend
    legend_html = """
    <div style="position:fixed;bottom:30px;left:30px;z-index:1000;
                background:#ffffff;border:1px solid #e8edf2;
                padding:10px 14px;border-radius:6px;
                box-shadow:0 2px 8px rgba(22,87,136,0.12);
                font-family:sans-serif;font-size:13px;color:#1a1a2e;">
      <b style="color:#165788">Venue Rating</b><br>
      <span style="color:#e74c3c">&#9632;</span> Plaintiff<br>
      <span style="color:#a8b8cc">&#9632;</span> Neutral<br>
      <span style="color:#165788">&#9632;</span> Defense
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    return m
