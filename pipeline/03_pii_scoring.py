"""
Module 3: Parking Impact Index (PII) Scoring
Scores every hotspot zone and ranks them for enforcement priority.

PII Formula:
  PII = (violation_count_score * 0.35)
      + (avg_severity_score    * 0.25)
      + (junction_score        * 0.20)
      + (recurrence_score      * 0.10)
      + (vehicle_weight_score  * 0.10)

All components normalized 0-100 before combining.
Final PII is 0-100. Higher = needs patrol more urgently.
"""

import pandas as pd
import numpy as np
import pickle
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
ZONES_FILE  = os.path.join(os.path.dirname(__file__), "../data/processed/hotspot_zones.pkl")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "../data/processed/ranked_zones.pkl")

VEHICLE_WEIGHT = {
    "TANKER":        5,
    "PRIVATE BUS":   5,
    "LGV":           4,
    "MAXI-CAB":      4,
    "VAN":           3,
    "GOODS AUTO":    3,
    "CAR":           2,
    "PASSENGER AUTO":2,
    "MOTOR CYCLE":   1,
    "SCOOTER":       1,
    "MOPED":         1,
}


def normalize(series: pd.Series) -> pd.Series:
    """Min-max normalize a series to 0-100."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series([50.0] * len(series), index=series.index)
    return ((series - mn) / (mx - mn)) * 100


def compute_pii(zones: pd.DataFrame) -> pd.DataFrame:
    df = zones.copy()

    # ── Component 1: Violation count (volume) ────────────────────────────
    df["c_volume"] = normalize(df["total_violations"])

    # ── Component 2: Average severity ─────────────────────────────────────
    df["c_severity"] = normalize(df["avg_impact"])

    # ── Component 3: Junction proximity ───────────────────────────────────
    df["c_junction"] = normalize(df["junction_pct"])

    # ── Component 4: Recurrence (how consistently bad) ───────────────────
    df["c_recurrence"] = normalize(df["recurrence_score"])

    # ── Component 5: Dominant vehicle weight ─────────────────────────────
    df["dominant_vehicle_weight"] = df["dominant_vehicle"].apply(
        lambda v: VEHICLE_WEIGHT.get(str(v).strip().upper(), 1)
    )
    df["c_vehicle"] = normalize(df["dominant_vehicle_weight"])

    # ── Volume gate: junction score only counts if volume is meaningful ──
    # Zones with < 500 violations cannot score high on junction alone
    volume_gate = (df["total_violations"] >= 500).astype(float)
    df["c_junction_gated"] = df["c_junction"] * volume_gate

    # ── Final PII (weighted sum) ──────────────────────────────────────────
    df["PII"] = (
        df["c_volume"]          * 0.40 +
        df["c_severity"]        * 0.20 +
        df["c_junction_gated"]  * 0.20 +
        df["c_recurrence"]      * 0.10 +
        df["c_vehicle"]         * 0.10
    ).round(1)

    # ── Risk Level: percentile-based so distribution is meaningful ────────
    p75 = df["PII"].quantile(0.75)
    p50 = df["PII"].quantile(0.50)
    p25 = df["PII"].quantile(0.25)

    def risk_level(pii):
        if pii >= p75:
            return "🔴 CRITICAL"
        elif pii >= p50:
            return "🟡 HIGH"
        elif pii >= p25:
            return "🟠 MEDIUM"
        else:
            return "🟢 LOW"

    df["risk_level"] = df["PII"].apply(risk_level)

    # ── Enforcement Priority Rank ─────────────────────────────────────────
    df = df.sort_values("PII", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1

    # ── Human-readable recommendation ────────────────────────────────────
    def make_recommendation(row):
        return (
            f"Deploy patrol to {row['zone_name']}. "
            f"Peak violations at {row['peak_hour_str']} on {row['peak_day']}s. "
            f"Primary issue: {row['dominant_violation'].title()}."
        )

    df["recommendation"] = df.apply(make_recommendation, axis=1)

    return df


def main():
    print("Loading zone profiles...")
    with open(ZONES_FILE, "rb") as f:
        zones = pickle.load(f)
    print(f"  {len(zones)} zones loaded")

    print("Computing Parking Impact Index (PII)...")
    ranked = compute_pii(zones)

    # ── Fix unnamed/ambiguous zone names using known locality data ────────
    ZONE_NAME_FIXES = {
        "Unnamed Road": "Begur Chikkanahalli Road, Yelahanka",
    }
    ranked["zone_name"] = ranked["zone_name"].replace(ZONE_NAME_FIXES)

    # ── Cap unique_days_active to actual dataset span (150 days) ─────────
    ranked["unique_days_active"] = ranked["unique_days_active"].clip(upper=150)

    # Recompute recommendation with fixed names
    ranked["recommendation"] = ranked.apply(
        lambda r: (
            f"Deploy patrol to {r['zone_name']}. "
            f"Peak violations at {r['peak_hour_str']} on {r['peak_day']}s. "
            f"Primary issue: {r['dominant_violation'].title()}."
        ), axis=1
    )

    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(ranked, f)
    print(f"Saved ranked zones → {OUTPUT_FILE}")

    print("\n── TOP 15 ENFORCEMENT PRIORITY ZONES ───────────────────────")
    cols = ["rank", "zone_name", "PII", "risk_level", "total_violations",
            "peak_hour_str", "peak_day", "police_station"]
    print(ranked[cols].head(15).to_string(index=False))

    print("\n── Risk Distribution ────────────────────────────────────────")
    print(ranked["risk_level"].value_counts().to_string())


if __name__ == "__main__":
    main()
