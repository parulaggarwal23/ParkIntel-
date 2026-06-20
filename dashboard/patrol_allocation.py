"""
Patrol Allocation Engine
========================
Self-contained module. To remove this feature:
  1. Delete this file (dashboard/patrol_allocation.py)
  2. In app.py: remove the import line marked [PATROL_ALLOCATION]
  3. In app.py: revert tab definitions from tab1..tab5 back to tab1..tab4
  4. In app.py: delete the entire TAB 5 block marked [PATROL_ALLOCATION]

Rendering note:
  Uses st_html (streamlit.components.v1.html) which renders a fully
  self-contained HTML document — bypasses Streamlit's markdown sanitiser
  so styles and multi-item loops render correctly every time.
"""

from __future__ import annotations
import re
import html as _html_mod
import pandas as pd


# ── Time window helpers ────────────────────────────────────────────────────────

def _parse_peak_hour(peak_hour_str: str) -> int | None:
    if not isinstance(peak_hour_str, str):
        return None
    m = re.search(r"(\d{1,2})(?::\d{2})?\s*(AM|PM)", peak_hour_str, re.IGNORECASE)
    if m:
        h = int(m.group(1))
        ampm = m.group(2).upper()
        if ampm == "PM" and h != 12:
            h += 12
        if ampm == "AM" and h == 12:
            h = 0
        return h
    m = re.search(r"\b(\d{1,2})\b", peak_hour_str)
    if m:
        return int(m.group(1))
    return None


def _build_time_window(peak_hour_str: str) -> str:
    h = _parse_peak_hour(peak_hour_str)
    if h is None:
        return peak_hour_str

    start = max(0, h - 1)
    end   = min(23, h + 1)

    def fmt(hour: int) -> str:
        ampm = "AM" if hour < 12 else "PM"
        display = hour % 12 or 12
        return f"{display:02d}:00 {ampm}"

    return f"{fmt(start)} – {fmt(end)}"


# ── Reason builder ─────────────────────────────────────────────────────────────

def _build_reason(row: pd.Series, rank: int) -> str:
    pii   = float(row.get("PII", 0))
    viol  = int(row.get("total_violations", 0))
    risk  = str(row.get("risk_level", ""))
    vtype = str(row.get("dominant_violation", "")).title()
    day   = str(row.get("peak_day", ""))

    if rank == 1:
        return f"Immediate patrol deployment recommended. {viol:,} recorded violations — top enforcement priority."
    if "CRITICAL" in risk.upper():
        return f"Critical-risk zone. Worst violation: {vtype}. Peaks on {day}s. Dispatch patrol immediately."
    if "HIGH" in risk.upper():
        return f"High-risk zone with {viol:,} violations. Recurring {vtype.lower()} issue. Prioritise patrol."
    return f"Significant parking violations ({viol:,}) concentrated on {day}s. Schedule regular patrol."


# ── Colour maps ────────────────────────────────────────────────────────────────

BADGE_COLORS = {
    1: "#b71c1c",
    2: "#c62828",
    3: "#d32f2f",
}

RISK_LABELS = {
    "CRITICAL": ("🔴 CRITICAL", "#ffebee", "#c62828"),
    "HIGH":     ("🟠 HIGH",     "#fff3e0", "#e65100"),
    "MEDIUM":   ("🟡 MEDIUM",   "#fffde7", "#f57f17"),
    "LOW":      ("🟢 LOW",      "#e8f5e9", "#2e7d32"),
}

def _risk_label(risk: str):
    for key, val in RISK_LABELS.items():
        if key in risk.upper():
            return val
    return RISK_LABELS["LOW"]


# ── Main render ────────────────────────────────────────────────────────────────

def get_patrol_css() -> str:
    """Kept for backward compat — no longer needed when using st_html."""
    return ""


def render_patrol_plan(ranked: pd.DataFrame, n_teams: int) -> str:
    """
    Returns a fully self-contained HTML document (including <style>)
    suitable for st_html(..., height=...).

    Parameters
    ----------
    ranked  : ranked_zones DataFrame sorted by PII descending
    n_teams : number of patrol teams

    Returns
    -------
    str : complete HTML document string
    """
    if ranked is None or len(ranked) == 0 or n_teams < 1:
        return "<html><body></body></html>"

    selected = ranked.head(n_teams).copy().reset_index(drop=True)

    rows_html = ""
    for i, row in selected.iterrows():
        team_num   = i + 1
        zone       = _html_mod.escape(str(row.get("zone_name", f"Zone {team_num}")))
        station    = _html_mod.escape(str(row.get("police_station", "—")))
        pii        = float(row.get("PII", 0))
        risk       = str(row.get("risk_level", ""))
        peak_raw   = str(row.get("peak_hour_str", ""))
        peak_day   = _html_mod.escape(str(row.get("peak_day", "")))
        violations = int(row.get("total_violations", 0))

        window       = _html_mod.escape(_build_time_window(peak_raw))
        reason       = _html_mod.escape(_build_reason(row, team_num))
        badge_color  = BADGE_COLORS.get(team_num, "#1565c0")
        risk_text, risk_bg, risk_fg = _risk_label(risk)

        row_html = (
            '<div class="patrol-row">'
            '<div class="patrol-badge" style="background:' + badge_color + ';">'
            "🚓<br>Team<br><strong>" + str(team_num) + "</strong>"
            "</div>"
            '<div class="patrol-body">'
            '<div class="patrol-zone">' + zone + "</div>"
            '<div class="patrol-time">⏰ Deploy: ' + window + " &nbsp;·&nbsp; 📅 Worst day: " + peak_day + "s</div>"
            '<div class="patrol-reason">💬 ' + reason + "</div>"
            '<div class="patrol-meta">'
            '<span class="patrol-tag" style="background:' + risk_bg + "; color:" + risk_fg + ';">' + risk_text + "</span>"
            '<span class="patrol-tag">' + f"{violations:,}" + " violations</span>"
            '<span class="patrol-tag">📍 ' + station + "</span>"
            "</div>"
            "</div>"
            "</div>"
        )
        rows_html += row_html

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: transparent;
    padding: 4px 2px 8px 2px;
  }}
  .patrol-panel {{
    background: linear-gradient(135deg, #0d1b3e 0%, #1a2f6e 100%);
    border-radius: 18px;
    padding: 22px 26px;
    box-shadow: 0 6px 30px rgba(13,27,62,0.4);
  }}
  .patrol-panel-title {{
    font-size: 1.1rem;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 4px;
    letter-spacing: 0.3px;
  }}
  .patrol-panel-subtitle {{
    font-size: 0.8rem;
    color: rgba(255,255,255,0.55);
    margin-bottom: 18px;
  }}
  .patrol-grid {{
    display: flex;
    flex-direction: column;
    gap: 11px;
  }}
  .patrol-row {{
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 13px;
    padding: 14px 16px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
  }}
  .patrol-row:hover {{
    background: rgba(255,255,255,0.11);
  }}
  .patrol-badge {{
    color: white;
    border-radius: 10px;
    min-width: 54px;
    text-align: center;
    padding: 8px 10px;
    font-size: 0.72rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    flex-shrink: 0;
    line-height: 1.5;
  }}
  .patrol-body {{ flex: 1; min-width: 0; }}
  .patrol-zone {{
    font-size: 0.98rem;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 4px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }}
  .patrol-time {{
    font-size: 0.8rem;
    color: #64b5f6;
    font-weight: 600;
    margin-bottom: 5px;
  }}
  .patrol-reason {{
    font-size: 0.77rem;
    color: rgba(255,255,255,0.65);
    line-height: 1.5;
    margin-bottom: 8px;
  }}
  .patrol-meta {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }}
  .patrol-tag {{
    background: rgba(255,255,255,0.1);
    color: rgba(255,255,255,0.8);
    border-radius: 6px;
    padding: 3px 9px;
    font-size: 0.71rem;
    font-weight: 600;
    white-space: nowrap;
  }}
  .patrol-footer {{
    margin-top: 16px;
    font-size: 0.74rem;
    color: rgba(255,255,255,0.35);
    border-top: 1px solid rgba(255,255,255,0.1);
    padding-top: 12px;
  }}
</style>
</head>
<body>
<div class="patrol-panel">
  <div class="patrol-panel-title">🚔 Patrol Deployment Plan</div>
  <div class="patrol-panel-subtitle">
    AI-generated deployment schedule for {n_teams} patrol team{"s" if n_teams > 1 else ""}
    &nbsp;·&nbsp; Ranked by Enforcement Priority &nbsp;·&nbsp; Updates automatically
  </div>
  <div class="patrol-grid">
    {rows_html}
  </div>
  <div class="patrol-footer">
    ⚙️ Generated from {len(ranked)} hotspot zones using AI scoring, peak-hour analysis
    and violation frequency data &nbsp;·&nbsp; Bengaluru Traffic Police — ASTraM System
  </div>
</div>
</body>
</html>"""
