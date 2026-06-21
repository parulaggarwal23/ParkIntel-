"""
Parking Intelligence Dashboard — Redesigned for Police Officers
Clean, bright, simple. One job: tell officers where to go.
"""

import streamlit as st
import pandas as pd
import pickle
import os
import folium
from folium.plugins import HeatMap
from streamlit.components.v1 import html as st_html
from dotenv import load_dotenv
from patrol_allocation import render_patrol_plan, get_patrol_css  # [PATROL_ALLOCATION]

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
MAPPLS_KEY = os.getenv("MAPPLS_API_KEY", "")
# Also check Streamlit secrets (for cloud deployment)
try:
    import streamlit as _st
    if "MAPPLS_API_KEY" in _st.secrets:
        MAPPLS_KEY = _st.secrets["MAPPLS_API_KEY"]
except Exception:
    pass
DATA_DIR = os.path.join(os.path.dirname(__file__), "../data/processed")

st.set_page_config(
    page_title="Parking Enforcement — Bengaluru",
    page_icon="🚦",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Global CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background: #f0f4ff;
}

/* Hide streamlit default chrome */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebar"] { display: none; }
.block-container { padding: 1.5rem 2rem 2rem 2rem !important; }

/* ── Top header bar ── */
.top-bar {
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%);
    color: white;
    border-radius: 16px;
    padding: 20px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 24px;
    box-shadow: 0 4px 20px rgba(26,35,126,0.25);
}
.top-bar-title { font-size: 1.5rem; font-weight: 800; letter-spacing: -0.3px; }
.top-bar-sub   { font-size: 0.85rem; opacity: 0.8; margin-top: 2px; }
.top-bar-badge {
    background: rgba(255,255,255,0.15);
    border-radius: 10px;
    padding: 8px 16px;
    text-align: center;
    font-size: 0.8rem;
}
.top-bar-badge b { font-size: 1.4rem; display: block; }

/* ── Summary strip ── */
.summary-strip {
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
}
.summary-card {
    flex: 1;
    border-radius: 14px;
    padding: 16px 20px;
    color: white;
    font-weight: 700;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    min-height: 90px;
}
.summary-card .num  { font-size: 2rem; font-weight: 800; line-height: 1; }
.summary-card .lbl  { font-size: 0.78rem; opacity: 0.9; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }

/* ── Section title ── */
.section-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #1a237e;
    margin: 8px 0 14px 0;
    display: flex;
    align-items: center;
    gap: 8px;
}

/* ── Zone cards ── */
.zone-card {
    background: white;
    border-radius: 16px;
    padding: 18px 20px;
    margin-bottom: 12px;
    border-left: 6px solid #ccc;
    box-shadow: 0 2px 12px rgba(0,0,0,0.07);
    transition: box-shadow 0.2s;
}
.zone-card:hover { box-shadow: 0 4px 20px rgba(0,0,0,0.13); }
.zone-card.critical { border-left-color: #e53935; }
.zone-card.high     { border-left-color: #fb8c00; }
.zone-card.medium   { border-left-color: #fdd835; }
.zone-card.low      { border-left-color: #43a047; }

.zone-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.zone-rank {
    background: #1a237e;
    color: white;
    border-radius: 8px;
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 800;
    font-size: 1rem;
    flex-shrink: 0;
}
.zone-name { font-size: 1.05rem; font-weight: 700; color: #1a237e; margin-left: 12px; flex: 1; }
.zone-badge {
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.badge-critical { background: #ffebee; color: #c62828; }
.badge-high     { background: #fff3e0; color: #e65100; }
.badge-medium   { background: #fffde7; color: #f57f17; }
.badge-low      { background: #e8f5e9; color: #2e7d32; }

.zone-info {
    display: flex;
    gap: 20px;
    margin-top: 12px;
    flex-wrap: wrap;
}
.zone-info-item { display: flex; flex-direction: column; }
.zone-info-label { font-size: 0.7rem; color: #9e9e9e; text-transform: uppercase; letter-spacing: 0.5px; }
.zone-info-value { font-size: 0.95rem; font-weight: 600; color: #212121; margin-top: 2px; }

.go-btn {
    display: inline-block;
    background: #1a237e;
    color: white !important;
    border-radius: 10px;
    padding: 8px 18px;
    font-size: 0.82rem;
    font-weight: 600;
    text-decoration: none !important;
    margin-top: 14px;
}
.go-btn:hover { background: #283593; }

/* ── Filter bar ── */
.filter-bar {
    background: white;
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 20px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06);
}

/* ── Tab bar redesign ── */
div[data-testid="stTabs"] > div:first-child {
    background: white;
    border-radius: 14px;
    padding: 6px 8px;
    gap: 4px;
    box-shadow: 0 2px 10px rgba(0,0,0,0.07);
    margin-bottom: 20px;
    border-bottom: none !important;
    overflow-x: auto;
}

/* All tab buttons */
button[data-baseweb="tab"] {
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    color: #555 !important;
    background: transparent !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 16px !important;
    transition: background 0.18s, color 0.18s !important;
    white-space: nowrap !important;
    letter-spacing: 0.1px !important;
}

button[data-baseweb="tab"]:hover {
    background: #f0f4ff !important;
    color: #1a237e !important;
}

/* Active tab */
button[data-baseweb="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #1a237e 0%, #283593 100%) !important;
    color: white !important;
    box-shadow: 0 3px 10px rgba(26,35,126,0.3) !important;
}

/* Hide the default bottom border indicator line */
div[data-testid="stTabs"] > div:first-child > div[role="tablist"]::before,
div[data-testid="stTabs"] > div:first-child > div[role="tablist"]::after {
    display: none !important;
}
div[data-baseweb="tab-highlight"],
div[data-baseweb="tab-border"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)

st.markdown(get_patrol_css(), unsafe_allow_html=True)  # [PATROL_ALLOCATION] — no-op, kept for compat


# ── Load data ──────────────────────────────────────────────────────────────────
@st.cache_data
def load_all():
    ranked_path   = os.path.join(DATA_DIR, "ranked_zones.pkl")
    temporal_path = os.path.join(DATA_DIR, "temporal_data.pkl")
    cluster_path  = os.path.join(DATA_DIR, "processed_data_clustered_slim.pkl")
    missing = [p for p in [ranked_path, temporal_path, cluster_path] if not os.path.exists(p)]
    if missing:
        return None, None, None
    with open(ranked_path,   "rb") as f: ranked   = pickle.load(f)
    with open(temporal_path, "rb") as f: temporal = pickle.load(f)
    with open(cluster_path,  "rb") as f: df       = pickle.load(f)
    return ranked, temporal, df

ranked, temporal, df_full = load_all()

if ranked is None:
    st.error("⚠️ Run the pipeline first:  python3 run_pipeline.py")
    st.stop()

# ── Helpers ────────────────────────────────────────────────────────────────────
def risk_info(risk):
    if "CRITICAL" in risk:
        return ("critical", "CRITICAL", "🔴")
    elif "HIGH" in risk:
        return ("high",     "HIGH RISK", "🟠")
    elif "MEDIUM" in risk:
        return ("medium",   "MODERATE",  "🟡")
    else:
        return ("low",      "LOW RISK",  "🟢")

critical_count = (ranked["risk_level"] == "🔴 CRITICAL").sum()
high_count     = (ranked["risk_level"] == "🟡 HIGH").sum()
medium_count   = (ranked["risk_level"] == "🟠 MEDIUM").sum()
total_zones    = len(ranked)


# ── Enforcement Recommendations: cached vehicle aggregation ───────────────────
@st.cache_data
def build_enforcement_data(_df_full, _ranked):
    """Group df_full by vehicle_number and compute enforcement tiers."""
    # cluster → zone name lookup
    zone_map = dict(zip(_ranked["cluster_id"], _ranked["zone_name"]))

    def _top_zone(clusters):
        valid = [c for c in clusters if c != -1]
        if not valid:
            return "Unknown"
        top_c = pd.Series(valid).value_counts().index[0]
        return zone_map.get(top_c, "Unknown")

    veh = (
        _df_full.groupby("vehicle_number")
        .agg(
            total_violations=("id",               "count"),
            vehicle_type    =("vehicle_type",     lambda x: x.value_counts().index[0]),
            top_violation   =("primary_violation",lambda x: x.value_counts().index[0]),
            top_zone        =("cluster",          _top_zone),
            top_station     =("police_station",   lambda x: x.value_counts().index[0]),
            last_seen       =("created_datetime", "max"),
            first_seen      =("created_datetime", "min"),
        )
        .reset_index()
    )

    def _tier(n):
        if n >= 5:  return ("🔴 High Priority Enforcement", "critical", "#e53935", "#ffebee", "#c62828")
        if n >= 2:  return ("🟠 Repeat Offender Alert",     "high",     "#fb8c00", "#fff3e0", "#e65100")
        return          ("🟢 Violation Recorded",           "low",      "#43a047", "#e8f5e9", "#2e7d32")

    tiers = veh["total_violations"].apply(_tier)
    veh["tier_label"] = tiers.apply(lambda t: t[0])
    veh["tier_class"] = tiers.apply(lambda t: t[1])
    veh["tier_color"] = tiers.apply(lambda t: t[2])
    veh["tier_bg"]    = tiers.apply(lambda t: t[3])
    veh["tier_fg"]    = tiers.apply(lambda t: t[4])

    veh["last_seen_str"]  = veh["last_seen"].dt.strftime("%d %b %Y")
    veh["first_seen_str"] = veh["first_seen"].dt.strftime("%d %b %Y")
    veh["vehicle_type"]   = veh["vehicle_type"].str.title()
    veh["top_violation"]  = veh["top_violation"].str.title()

    veh = veh.sort_values("total_violations", ascending=False).reset_index(drop=True)
    veh["rank"] = veh.index + 1
    return veh

enf_data = build_enforcement_data(df_full, ranked)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="top-bar">
  <div>
    <div class="top-bar-title">🚦 Bengaluru Parking Enforcement</div>
    <div class="top-bar-sub">Powered by ASTraM Data · MapMyIndia · AI Hotspot Detection</div>
  </div>
  <div style="display:flex; gap:12px;">
    <div class="top-bar-badge">
      <b>{len(df_full):,}</b>
      Violations Analysed
    </div>
    <div class="top-bar-badge">
      <b>{total_zones}</b>
      Hotspot Zones Found
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Summary strip ──────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="summary-strip">
  <div class="summary-card" style="background:linear-gradient(135deg,#e53935,#b71c1c);">
    <div class="num">{critical_count}</div>
    <div class="lbl">🔴 Needs Patrol Now</div>
  </div>
  <div class="summary-card" style="background:linear-gradient(135deg,#fb8c00,#e65100);">
    <div class="num">{high_count}</div>
    <div class="lbl">🟠 High Risk Zones</div>
  </div>
  <div class="summary-card" style="background:linear-gradient(135deg,#fdd835,#f9a825);">
    <div class="num">{medium_count}</div>
    <div class="lbl" style="color:#333;">🟡 Moderate Zones</div>
  </div>
  <div class="summary-card" style="background:linear-gradient(135deg,#1e88e5,#1565c0);">
    <div class="num">{ranked.iloc[0]['zone_name'][:18]}</div>
    <div class="lbl">📍 Worst Zone Today</div>
  </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([    # [PATROL_ALLOCATION]
    "Where to Patrol",
    "Map View",
    "Repeat Offenders",
    "All Zones",
    "Patrol Planner",                   # [PATROL_ALLOCATION]
    "Enforcement Recommendations",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 ── WHERE TO PATROL (Main screen for officers)
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    # Filter row
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        all_stations = ["All Stations"] + sorted(ranked["police_station"].dropna().unique().tolist())
        station = st.selectbox("Filter by Police Station", all_stations, label_visibility="collapsed")
    with col_f2:
        risk_filter = st.selectbox(
            "Filter by Risk",
            ["Show All Zones", "🔴 Needs Patrol Now", "🟠 High Risk Only", "🟡 Moderate & Above"],
            label_visibility="collapsed"
        )
    with col_f3:
        top_n = st.selectbox("Show", [5, 10, 20, 30], index=1, label_visibility="collapsed")

    # Apply filters
    view = ranked.copy()
    if station != "All Stations":
        view = view[view["police_station"] == station]
    if risk_filter == "🔴 Needs Patrol Now":
        view = view[view["risk_level"] == "🔴 CRITICAL"]
    elif risk_filter == "🟠 High Risk Only":
        view = view[view["risk_level"].isin(["🔴 CRITICAL", "🟡 HIGH"])]
    elif risk_filter == "🟡 Moderate & Above":
        view = view[~view["risk_level"].isin(["🟢 LOW"])]
    view = view.head(top_n)

    if len(view) == 0:
        st.info("No zones match these filters. Try changing the filter above.")
    else:
        st.markdown(f"""
        <div class="section-title">
          📍 Top {len(view)} zones to patrol — sorted by urgency
        </div>
        """, unsafe_allow_html=True)

        for _, row in view.iterrows():
            cls, badge_text, emoji = risk_info(row["risk_level"])
            maps_link = (
                f"https://www.google.com/maps/dir/?api=1&destination="
                f"{row['centroid_lat']},{row['centroid_lon']}"
            )
            violation = row["dominant_violation"].replace("PARKING", "Parking").replace(
                "WRONG", "Wrong").replace("NO ", "No ").replace("IN A MAIN ROAD", "on Main Road").title()

            # Simple plain English recommendation
            action = f"Send patrol to {row['zone_name']}. Worst on {row['peak_day']}s around {row['peak_hour_str']}."

            st.markdown(f"""
<div class="zone-card {cls}">
  <div class="zone-header">
    <div class="zone-rank">#{int(row['rank'])}</div>
    <div class="zone-name">{row['zone_name']}</div>
    <span class="zone-badge badge-{cls}">{emoji} {badge_text}</span>
  </div>

  <div class="zone-info">
    <div class="zone-info-item">
      <span class="zone-info-label">📍 Police Station</span>
      <span class="zone-info-value">{row['police_station']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🚗 Violations Recorded</span>
      <span class="zone-info-value">{int(row['total_violations']):,}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">⏰ Peak Time</span>
      <span class="zone-info-value">{row['peak_hour_str']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">📅 Worst Day</span>
      <span class="zone-info-value">{row['peak_day']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">⚠️ Common Violation</span>
      <span class="zone-info-value">{violation}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🔁 Active For</span>
      <span class="zone-info-value">{int(row['unique_days_active'])} days</span>
    </div>
  </div>

  <div style="margin-top:10px; color:#555; font-size:0.88rem;">
    💬 <i>{action}</i>
  </div>

  <a class="go-btn" href="{maps_link}" target="_blank">
    🗺️ Open in Google Maps &rarr;
  </a>
</div>
""", unsafe_allow_html=True)

        # ── [PATROL_ALLOCATION] render call removed — moved to tab5 ─────────


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 ── MAP VIEW
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    st.markdown("""
    <div class="section-title">🗺️ Violation heatmap across Bengaluru</div>
    <p style="color:#555; font-size:0.9rem; margin-bottom:4px;">
      The <b style="color:#e53935;">red areas</b> show where most parking violations are concentrated.
      Use the <b>+ button</b> to zoom into any red area to see the exact zones.
    </p>
    """, unsafe_allow_html=True)

    m = folium.Map(location=[12.9716, 77.5946], zoom_start=14, tiles=None)

    # MapMyIndia tiles
    if MAPPLS_KEY:
        folium.TileLayer(
            tiles=f"https://apis.mappls.com/advancedmaps/v1/{MAPPLS_KEY}/still_map/{{z}}/{{x}}/{{y}}.png",
            attr="© MapMyIndia",
            name="MapMyIndia",
            max_zoom=18,
        ).add_to(m)
    else:
        folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
            attr="© CartoDB",
            name="Light Map",
        ).add_to(m)

    # Heatmap layer — reduced opacity so markers show through
    df_sample = df_full[df_full["cluster"] != -1].sample(min(25_000, len(df_full)), random_state=42)
    heat_data = df_sample[["latitude", "longitude", "record_impact"]].values.tolist()
    HeatMap(
        heat_data, radius=14, blur=18, max_zoom=15, min_opacity=0.3,
        gradient={"0.2": "#ffffcc", "0.5": "#fd8d3c", "0.8": "#e31a1c", "1.0": "#800026"},
    ).add_to(m)

    # Marker FeatureGroup — added AFTER heatmap, sits on top
    marker_group = folium.FeatureGroup(name="Hotspot Zones", overlay=True)
    dot_color = {"critical": "#e53935", "high": "#fb8c00", "medium": "#fdd835", "low": "#43a047"}
    border_color = {"critical": "#b71c1c", "high": "#e65100", "medium": "#f9a825", "low": "#2e7d32"}

    for _, row in ranked.head(80).iterrows():
        cls, badge_text, emoji = risk_info(row["risk_level"])
        maps_link = f"https://www.google.com/maps/dir/?api=1&destination={row['centroid_lat']},{row['centroid_lon']}"
        radius = 14 if cls == "critical" else 11 if cls == "high" else 8
        bg = dot_color.get(cls, "#1e88e5")
        bd = border_color.get(cls, "#0d47a1")

        popup_html = f"""
        <div style='font-family:Arial,sans-serif; padding:6px; min-width:230px;'>
          <div style='font-size:1rem; font-weight:700; color:#1a237e; margin-bottom:4px;'>
            #{int(row['rank'])} {row['zone_name']}
          </div>
          <div style='padding:3px 10px; border-radius:12px; display:inline-block;
               font-size:0.75rem; font-weight:700; margin-bottom:8px;
               background:{"#ffebee; color:#c62828" if cls=="critical" else "#fff3e0; color:#e65100" if cls=="high" else "#fffde7; color:#f57f17"};'>
            {emoji} {badge_text}
          </div>
          <table style='font-size:0.82rem; width:100%; border-collapse:collapse;'>
            <tr><td style='color:#888; padding:2px 0;'>📍 Station</td>
                <td style='font-weight:600; padding:2px 0;'>{row['police_station']}</td></tr>
            <tr><td style='color:#888; padding:2px 0;'>🚗 Violations</td>
                <td style='font-weight:600; padding:2px 0;'>{int(row['total_violations']):,}</td></tr>
            <tr><td style='color:#888; padding:2px 0;'>⏰ Peak Time</td>
                <td style='font-weight:600; padding:2px 0;'>{row['peak_hour_str']}</td></tr>
            <tr><td style='color:#888; padding:2px 0;'>📅 Worst Day</td>
                <td style='font-weight:600; padding:2px 0;'>{row['peak_day']}</td></tr>
            <tr><td style='color:#888; padding:2px 0;'>⚠️ Main Issue</td>
                <td style='font-weight:600; padding:2px 0;'>{row['dominant_violation'].title()}</td></tr>
          </table>
          <div style='margin-top:10px;'>
            <a href='{maps_link}' target='_blank'
               style='background:#1a237e; color:white !important; padding:7px 14px;
                      border-radius:8px; text-decoration:none; font-size:0.82rem;
                      font-weight:600; display:inline-block;'>
              🗺️ Open in Google Maps
            </a>
          </div>
        </div>
        """

        # DivIcon renders in DOM (not canvas) — always clickable above heatmap
        short_name = row['zone_name'] if len(row['zone_name']) <= 22 else row['zone_name'][:20] + "…"
        icon_html = f"""
        <div style="display:flex; align-items:center; gap:6px; cursor:pointer;">
          <div style="
              width:28px; height:28px; flex-shrink:0;
              background:{bg}; border:2.5px solid {bd};
              border-radius:50%;
              box-shadow: 0 2px 6px rgba(0,0,0,0.45);
              display:flex; align-items:center; justify-content:center;
              font-size:11px; font-weight:800; color:white;
          ">{int(row['rank'])}</div>
          <div style="
              background:rgba(255,255,255,0.92);
              border:1.5px solid {bd};
              border-radius:6px;
              padding:3px 7px;
              font-size:11px; font-weight:700;
              color:#1a237e;
              white-space:nowrap;
              box-shadow: 0 1px 4px rgba(0,0,0,0.2);
          ">{short_name}</div>
        </div>
        """
        folium.Marker(
            location=[row["centroid_lat"], row["centroid_lon"]],
            popup=folium.Popup(popup_html, max_width=270),
            tooltip=f"{emoji} #{int(row['rank'])} {row['zone_name']} — click for details",
            icon=folium.DivIcon(
                html=icon_html,
                icon_size=(220, 30),
                icon_anchor=(14, 14),
            ),
        ).add_to(marker_group)

    marker_group.add_to(m)

    st_html(m._repr_html_(), height=580)
    st.markdown("""
    <div style="background:white; border-radius:12px; padding:14px 20px;
         box-shadow:0 2px 10px rgba(0,0,0,0.07); margin-top:12px;">
      <div style="font-size:0.85rem; font-weight:700; color:#1a237e; margin-bottom:8px;">
        How to read this map
      </div>
      <div style="display:flex; gap:24px; flex-wrap:wrap; font-size:0.82rem; color:#444;">
        <div><b style="color:#e53935;">■</b> Red heatmap = lots of parking violations here</div>
        <div><b style="color:#fd8d3c;">■</b> Orange heatmap = moderate violations</div>
        <div>🔴 <b>Numbered circles</b> = enforcement hotspot zones (zoom in to see them)</div>
        <div>👆 <b>Click any numbered circle</b> for zone details + Google Maps directions</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 ── REPEAT OFFENDERS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    repeat_path = os.path.join(DATA_DIR, "repeat_offenders.pkl")
    if not os.path.exists(repeat_path):
        st.warning("Run python3 pipeline/05_repeat_offenders.py to generate this data.")
    else:
        with open(repeat_path, "rb") as f:
            repeat = pickle.load(f)

        chronic  = (repeat["total_violations"] >= 20).sum()
        frequent = ((repeat["total_violations"] >= 10) & (repeat["total_violations"] < 20)).sum()
        repeat5  = ((repeat["total_violations"] >= 5)  & (repeat["total_violations"] < 10)).sum()
        total_veh = repeat["vehicle_number"].nunique() if "vehicle_number" in repeat.columns else len(repeat)

        # ── Summary strip ──────────────────────────────────────────────
        st.markdown(f"""
        <div class="section-title">🔁 Repeat Offenders — Vehicles caught multiple times</div>
        <p style="color:#555; font-size:0.88rem; margin-bottom:16px;">
          These vehicles have been caught parking illegally multiple times and never actioned.
          Targeting them directly reduces violations faster than area patrols alone.
        </p>
        <div class="summary-strip">
          <div class="summary-card" style="background:linear-gradient(135deg,#e53935,#b71c1c);">
            <div class="num">{chronic}</div>
            <div class="lbl">🔴 Chronic (20+ times)</div>
          </div>
          <div class="summary-card" style="background:linear-gradient(135deg,#fb8c00,#e65100);">
            <div class="num">{frequent}</div>
            <div class="lbl">🟠 Frequent (10–19 times)</div>
          </div>
          <div class="summary-card" style="background:linear-gradient(135deg,#fdd835,#f9a825);">
            <div class="num">{repeat5}</div>
            <div class="lbl" style="color:#333;">🟡 Repeat (5–9 times)</div>
          </div>
          <div class="summary-card" style="background:linear-gradient(135deg,#1e88e5,#1565c0);">
            <div class="num">{int(repeat.iloc[0]['total_violations'])}</div>
            <div class="lbl">📍 Most violations by one vehicle</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Filter ────────────────────────────────────────────────────
        col_r1, col_r2 = st.columns([2, 2])
        with col_r1:
            tier_filter = st.selectbox(
                "Filter by tier",
                ["All Offenders", "🔴 Chronic (20+)", "🟠 Frequent (10–19)", "🟡 Repeat (5–9)"],
                label_visibility="collapsed"
            )
        with col_r2:
            vtype_filter = st.selectbox(
                "Vehicle type",
                ["All Types"] + sorted(repeat["vehicle_type"].unique().tolist()),
                label_visibility="collapsed"
            )

        view = repeat.copy()
        if tier_filter == "🔴 Chronic (20+)":
            view = view[view["total_violations"] >= 20]
        elif tier_filter == "🟠 Frequent (10–19)":
            view = view[(view["total_violations"] >= 10) & (view["total_violations"] < 20)]
        elif tier_filter == "🟡 Repeat (5–9)":
            view = view[(view["total_violations"] >= 5) & (view["total_violations"] < 10)]
        if vtype_filter != "All Types":
            view = view[view["vehicle_type"] == vtype_filter]
        view = view.head(50)

        # ── Offender cards ────────────────────────────────────────────
        st.markdown(f"<div class='section-title' style='font-size:0.95rem;'>Showing top {len(view)} offenders</div>",
                    unsafe_allow_html=True)

        tier_card = {"chronic": "critical", "frequent": "high", "repeat": "medium", "occasional": "low"}
        tier_color = {"chronic": "#e53935", "frequent": "#fb8c00", "repeat": "#fdd835", "occasional": "#43a047"}

        for _, row in view.iterrows():
            cls   = tier_card.get(row["tier_class"], "low")
            color = tier_color.get(row["tier_class"], "#43a047")

            maps_link = f"https://www.google.com/maps/search/?api=1&query={row['top_zone'].replace(' ', '+')},+Bengaluru"

            st.markdown(f"""
<div class="zone-card {cls}">
  <div class="zone-header">
    <div class="zone-rank" style="background:{color};">#{int(row['rank'])}</div>
    <div class="zone-name" style="font-family:monospace; font-size:1rem;">
      {row['vehicle_number']}
    </div>
    <span class="zone-badge badge-{cls}">{row['tier_label']}</span>
  </div>

  <div class="zone-info">
    <div class="zone-info-item">
      <span class="zone-info-label">🚗 Vehicle Type</span>
      <span class="zone-info-value">{row['vehicle_type']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">⚠️ Times Caught</span>
      <span class="zone-info-value" style="color:{color}; font-size:1.1rem;">{int(row['total_violations'])}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">📍 Operates In</span>
      <span class="zone-info-value">{row['top_zone']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🏛️ Police Station</span>
      <span class="zone-info-value">{row['top_stations']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">⚠️ Main Violation</span>
      <span class="zone-info-value">{row['top_violation']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">📅 Last Caught</span>
      <span class="zone-info-value">{row['last_seen_str']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🗓️ First Caught</span>
      <span class="zone-info-value">{row['first_seen_str']}</span>
    </div>
  </div>

  <div style="margin-top:10px; color:#555; font-size:0.85rem;">
    💬 <i>Caught {int(row['total_violations'])} times in {int(row['days_active'])} days
    — averaging {row['violations_per_day']} violations/day.
    Primarily operating near <b>{row['top_zone']}</b>.</i>
  </div>

  <a class="go-btn" href="{maps_link}" target="_blank">
    🗺️ View Operating Zone &rarr;
  </a>
</div>
""", unsafe_allow_html=True)

        st.divider()
        st.markdown("### Download repeat offender list")
        dl = view[["rank","vehicle_number","vehicle_type","total_violations",
                    "tier_label","top_zone","top_stations","top_violation",
                    "first_seen_str","last_seen_str","violations_per_day"]].copy()
        dl.columns = ["Rank","Vehicle No","Type","Times Caught","Tier",
                      "Main Zone","Stations","Main Violation","First Caught","Last Caught","Violations/Day"]
        csv = dl.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download as CSV", data=csv,
                           file_name="repeat_offenders.csv", mime="text/csv")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 ── ALL ZONES
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown("""
    <div class="section-title">📋 All enforcement zones — full list</div>
    """, unsafe_allow_html=True)

    # Station summary cards at top
    station_summary = (
        ranked.groupby("police_station")
        .agg(
            zones=("zone_name", "count"),
            critical=("risk_level", lambda x: (x == "🔴 CRITICAL").sum()),
            high=("risk_level", lambda x: (x == "🟡 HIGH").sum()),
            violations=("total_violations", "sum"),
        )
        .reset_index()
        .sort_values("violations", ascending=False)
        .head(8)
    )

    st.markdown("<div class='section-title' style='font-size:0.95rem;'>📊 Top 8 stations by violation count</div>",
                unsafe_allow_html=True)

    cols = st.columns(4)
    for i, (_, row) in enumerate(station_summary.iterrows()):
        with cols[i % 4]:
            critical_badge = f"<span style='color:#e53935; font-weight:700;'>{int(row['critical'])} critical</span>" if row['critical'] > 0 else ""
            st.markdown(f"""
<div style='background:white; border-radius:14px; padding:14px 16px;
     margin-bottom:12px; box-shadow:0 2px 10px rgba(0,0,0,0.07);'>
  <div style='font-size:0.95rem; font-weight:700; color:#1a237e;'>{row['police_station']}</div>
  <div style='font-size:1.5rem; font-weight:800; color:#212121; margin:4px 0;'>{int(row['violations']):,}</div>
  <div style='font-size:0.75rem; color:#888;'>violations · {int(row['zones'])} zones</div>
  <div style='font-size:0.78rem; margin-top:4px;'>{critical_badge}</div>
</div>
""", unsafe_allow_html=True)

    st.divider()

    # Clean table — no jargon
    display = ranked[[
        "rank", "zone_name", "risk_level", "police_station",
        "total_violations", "peak_hour_str", "peak_day", "dominant_violation"
    ]].copy()
    display.columns = ["#", "Zone Name", "Risk Level", "Police Station",
                       "Total Violations", "Peak Time", "Worst Day", "Main Violation"]
    display["Main Violation"] = display["Main Violation"].str.title()

    st.dataframe(display, use_container_width=True, height=500, hide_index=True)

    csv_data = display.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download as CSV",
        data=csv_data,
        file_name="enforcement_zones.csv",
        mime="text/csv",
    )


# ─────────────────────────────────────────────────────────────────────────────
# TAB 5 ── PATROL PLANNER  [PATROL_ALLOCATION]
# To remove: delete this entire block and dashboard/patrol_allocation.py
#            Also revert the tab definitions line above back to tab1..tab4
# ─────────────────────────────────────────────────────────────────────────────
with tab5:                                                                # [PATROL_ALLOCATION]
    st.markdown("""
    <div class="section-title" style="font-size:1.2rem; margin-bottom:4px;">
        🚔 Patrol Allocation Engine
    </div>
    """, unsafe_allow_html=True)

    # ── Controls ──────────────────────────────────────────────────────────
    col_p1, col_p2, col_p3 = st.columns([1, 2, 3])
    with col_p1:
        n_teams = st.number_input(
            "🚓 Available Patrol Teams",
            min_value=1,
            max_value=100,
            value=5,
            step=1,
            key="patrol_teams_tab5"
        )
    with col_p2:
        station_p = st.selectbox(
            "📍 Filter by Police Station (optional)",
            ["All Stations"] + sorted(ranked["police_station"].dropna().unique().tolist()),
            key="patrol_station_tab5"
        )

    # ── Filter ranked zones by station if selected ─────────────────────
    patrol_ranked = ranked.copy()
    if station_p != "All Stations":
        patrol_ranked = patrol_ranked[patrol_ranked["police_station"] == station_p]
        patrol_ranked = patrol_ranked.reset_index(drop=True)

    if len(patrol_ranked) == 0:
        st.info("No zones found for this station. Try 'All Stations'.")
    else:
        # ── Summary strip ──────────────────────────────────────────────
        actual_teams = min(n_teams, len(patrol_ranked))
        covered_violations = int(patrol_ranked.head(actual_teams)["total_violations"].sum())
        total_violations   = int(patrol_ranked["total_violations"].sum())
        coverage_pct       = round(covered_violations / total_violations * 100, 1) if total_violations else 0

        st.markdown(f"""
        <div class="summary-strip" style="margin-bottom:20px;">
          <div class="summary-card" style="background:linear-gradient(135deg,#1a237e,#283593);">
            <div class="num">{actual_teams}</div>
            <div class="lbl">Teams Deployed</div>
          </div>
          <div class="summary-card" style="background:linear-gradient(135deg,#e53935,#b71c1c);">
            <div class="num">{covered_violations:,}</div>
            <div class="lbl">Violations Covered</div>
          </div>
          <div class="summary-card" style="background:linear-gradient(135deg,#2e7d32,#1b5e20);">
            <div class="num">{coverage_pct}%</div>
            <div class="lbl">Of Total Violations Targeted</div>
          </div>
          <div class="summary-card" style="background:linear-gradient(135deg,#f57f17,#e65100);">
            <div class="num">{patrol_ranked.iloc[0]['zone_name'][:16]}</div>
            <div class="lbl">Top Priority Zone</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Deployment Plan ────────────────────────────────────────────
        st_html(render_patrol_plan(patrol_ranked, actual_teams), height=160 + actual_teams * 175, scrolling=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 6 ── ENFORCEMENT RECOMMENDATIONS
# To remove: delete this entire block, remove tab6 from st.tabs(), and
#            delete the build_enforcement_data() function + enf_data line above.
# ─────────────────────────────────────────────────────────────────────────────
with tab6:
    st.markdown("""
    <div class="section-title" style="font-size:1.2rem; margin-bottom:4px;">
        📌 Enforcement Recommendations
    </div>
    """, unsafe_allow_html=True)

    # ── Summary strip ──────────────────────────────────────────────────────
    n_high     = (enf_data["tier_class"] == "critical").sum()
    n_repeat   = (enf_data["tier_class"] == "high").sum()
    n_single   = (enf_data["tier_class"] == "low").sum()
    top_veh    = enf_data.iloc[0]["vehicle_number"] if len(enf_data) else "—"
    top_count  = int(enf_data.iloc[0]["total_violations"]) if len(enf_data) else 0

    st.markdown(f"""
    <div class="summary-strip" style="margin-bottom:20px;">
      <div class="summary-card" style="background:linear-gradient(135deg,#e53935,#b71c1c); display:flex; flex-direction:column; justify-content:flex-end;">
        <div class="num">{n_high:,}</div>
        <div class="lbl">High Priority (5+ violations)</div>
      </div>
      <div class="summary-card" style="background:linear-gradient(135deg,#fb8c00,#e65100); display:flex; flex-direction:column; justify-content:flex-end;">
        <div class="num">{n_repeat:,}</div>
        <div class="lbl">Repeat Offender (2–4 violations)</div>
      </div>
      <div class="summary-card" style="background:linear-gradient(135deg,#43a047,#2e7d32); display:flex; flex-direction:column; justify-content:flex-end;">
        <div class="num">{n_single:,}</div>
        <div class="lbl">Single Violation</div>
      </div>
      <div class="summary-card" style="background:linear-gradient(135deg,#1e88e5,#1565c0); display:flex; flex-direction:column; justify-content:flex-end;">
        <div class="num" style="font-size:1.3rem; line-height:1.2; word-break:break-all;">{top_veh}</div>
        <div class="lbl">⚠ Top Offender · {top_count} violations</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Filters ────────────────────────────────────────────────────────────
    col_e1, col_e2, col_e3, col_e4 = st.columns([2, 2, 2, 1])
    with col_e1:
        tier_f = st.selectbox(
            "Recommendation tier",
            ["All Vehicles",
             "🔴 High Priority Enforcement (5+)",
             "🟠 Repeat Offender Alert (2–4)",
             "🟢 Violation Recorded (1)"],
            label_visibility="collapsed",
            key="enf_tier_filter"
        )
    with col_e2:
        station_f = st.selectbox(
            "Police Station",
            ["All Stations"] + sorted(enf_data["top_station"].dropna().unique().tolist()),
            label_visibility="collapsed",
            key="enf_station_filter"
        )
    with col_e3:
        zone_f = st.selectbox(
            "Hotspot Zone",
            ["All Zones"] + sorted([z for z in enf_data["top_zone"].unique() if z != "Unknown"]),
            label_visibility="collapsed",
            key="enf_zone_filter"
        )
    with col_e4:
        top_enf = st.selectbox(
            "Show",
            [25, 50, 100],
            label_visibility="collapsed",
            key="enf_top_n"
        )

    # Optional vehicle number search
    search_q = st.text_input(
        "Search vehicle number",
        placeholder="e.g. KA01AB1234",
        label_visibility="collapsed",
        key="enf_search"
    )

    # ── Apply filters ──────────────────────────────────────────────────────
    view_e = enf_data.copy()
    if tier_f == "🔴 High Priority Enforcement (5+)":
        view_e = view_e[view_e["tier_class"] == "critical"]
    elif tier_f == "🟠 Repeat Offender Alert (2–4)":
        view_e = view_e[view_e["tier_class"] == "high"]
    elif tier_f == "🟢 Violation Recorded (1)":
        view_e = view_e[view_e["tier_class"] == "low"]
    if station_f != "All Stations":
        view_e = view_e[view_e["top_station"] == station_f]
    if zone_f != "All Zones":
        view_e = view_e[view_e["top_zone"] == zone_f]
    if search_q.strip():
        view_e = view_e[view_e["vehicle_number"].str.contains(search_q.strip(), case=False, na=False)]
    view_e = view_e.head(top_enf)

    st.markdown(
        f"<div class='section-title' style='font-size:0.95rem; margin-bottom:10px;'>"
        f"Showing {len(view_e):,} vehicles — ranked by violation count</div>",
        unsafe_allow_html=True
    )

    if len(view_e) == 0:
        st.info("No vehicles match these filters. Try adjusting above.")
    else:
        for _, row in view_e.iterrows():
            cls       = row["tier_class"]
            color     = row["tier_color"]
            tier_bg   = row["tier_bg"]
            tier_fg   = row["tier_fg"]
            tier_lbl  = row["tier_label"]
            n_viol    = int(row["total_violations"])
            maps_link = (
                f"https://www.google.com/maps/search/?api=1&query="
                f"{row['top_zone'].replace(' ', '+')},+Bengaluru"
            )

            # Action sentence
            if cls == "critical":
                action = (
                    f"Issue notice to vehicle <b>{row['vehicle_number']}</b>. "
                    f"Caught {n_viol} times — primarily at <b>{row['top_zone']}</b> "
                    f"under <b>{row['top_station']}</b> PS. Escalate to enforcement."
                )
            elif cls == "high":
                action = (
                    f"Flag vehicle <b>{row['vehicle_number']}</b> for repeat violations. "
                    f"Caught {n_viol} times near <b>{row['top_zone']}</b>. "
                    f"Monitor and issue formal warning."
                )
            else:
                action = (
                    f"Single violation recorded for <b>{row['vehicle_number']}</b> "
                    f"near <b>{row['top_zone']}</b>. Log and monitor."
                )

            st.markdown(f"""
<div class="zone-card {cls}">
  <div class="zone-header">
    <div class="zone-rank" style="background:{color}; min-width:40px; font-size:0.82rem;">
      #{int(row['rank'])}
    </div>
    <div class="zone-name" style="font-family:monospace; font-size:1rem; letter-spacing:1px;">
      {row['vehicle_number']}
    </div>
    <span class="zone-badge" style="background:{tier_bg}; color:{tier_fg};">{tier_lbl}</span>
  </div>

  <div class="zone-info">
    <div class="zone-info-item">
      <span class="zone-info-label">🚗 Vehicle Type</span>
      <span class="zone-info-value">{row['vehicle_type']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">⚠️ Total Violations</span>
      <span class="zone-info-value" style="color:{color}; font-size:1.15rem; font-weight:800;">{n_viol}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🔴 Main Violation</span>
      <span class="zone-info-value">{row['top_violation']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">📍 Primary Zone</span>
      <span class="zone-info-value">{row['top_zone']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🏛️ Police Station</span>
      <span class="zone-info-value">{row['top_station']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">🗓️ First Seen</span>
      <span class="zone-info-value">{row['first_seen_str']}</span>
    </div>
    <div class="zone-info-item">
      <span class="zone-info-label">📅 Last Seen</span>
      <span class="zone-info-value">{row['last_seen_str']}</span>
    </div>
  </div>

  <div style="margin-top:10px; color:#555; font-size:0.87rem; line-height:1.5;">
    💬 <i>{action}</i>
  </div>

  <a class="go-btn" href="{maps_link}" target="_blank">
    🗺️ View Operating Zone &rarr;
  </a>
</div>
""", unsafe_allow_html=True)

    # ── Download ───────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### ⬇️ Download enforcement list")
    dl_e = view_e[[
        "rank", "vehicle_number", "vehicle_type", "total_violations",
        "tier_label", "top_violation", "top_zone", "top_station",
        "first_seen_str", "last_seen_str"
    ]].copy()
    dl_e.columns = [
        "Rank", "Vehicle No", "Type", "Total Violations",
        "Recommendation", "Main Violation", "Primary Zone", "Police Station",
        "First Seen", "Last Seen"
    ]
    csv_enf = dl_e.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download as CSV",
        data=csv_enf,
        file_name="enforcement_recommendations.csv",
        mime="text/csv",
        key="enf_download"
    )
