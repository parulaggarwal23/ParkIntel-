"""
Module 2: Hotspot Detection using DBSCAN
Clusters GPS violation points into named hotspot zones.
Outputs hotspot_zones.pkl — a dataframe of all detected zones with stats.
"""

import pandas as pd
import numpy as np
import pickle
import os
from sklearn.cluster import DBSCAN
from collections import Counter

# ── Paths ─────────────────────────────────────────────────────────────────────
PROCESSED  = os.path.join(os.path.dirname(__file__), "../data/processed/processed_data.pkl")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../data/processed")
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "hotspot_zones.pkl")

# ── DBSCAN Parameters ─────────────────────────────────────────────────────────
# eps: ~150 metres in radians (150m / 6371000m)
EPS_METERS   = 150
EPS_RADIANS  = EPS_METERS / 6_371_000
MIN_SAMPLES  = 30   # minimum violations to form a hotspot zone


def load_data() -> pd.DataFrame:
    with open(PROCESSED, "rb") as f:
        return pickle.load(f)


def run_dbscan(df: pd.DataFrame):
    """Run DBSCAN on lat/long in radians for haversine metric."""
    coords = np.radians(df[["latitude", "longitude"]].values)
    db = DBSCAN(
        eps=EPS_RADIANS,
        min_samples=MIN_SAMPLES,
        algorithm="ball_tree",
        metric="haversine",
        n_jobs=-1
    )
    labels = db.fit_predict(coords)
    return labels


def build_zone_profiles(df: pd.DataFrame) -> pd.DataFrame:
    """
    For each cluster, compute:
    - centroid lat/long
    - total violations
    - dominant violation type
    - dominant vehicle type
    - average record impact
    - junction coverage %
    - peak hour & peak day
    - recurrence (unique days active)
    - zone name (from junction_name if available, else nearest address snippet)
    """
    zones = []

    for cluster_id in sorted(df["cluster"].unique()):
        if cluster_id == -1:
            continue  # noise points

        zone = df[df["cluster"] == cluster_id]

        # ── Core stats ────────────────────────────────────────────────
        total_violations = len(zone)
        centroid_lat     = zone["latitude"].mean()
        centroid_lon     = zone["longitude"].mean()
        avg_impact       = zone["record_impact"].mean()
        total_impact     = zone["record_impact"].sum()
        junction_pct     = zone["near_junction"].mean() * 100
        unique_days      = zone["date"].nunique()

        # ── Dominant violation ────────────────────────────────────────
        all_violations = [v for lst in zone["violation_list"] for v in lst]
        violation_counts = Counter(all_violations)
        dominant_violation = violation_counts.most_common(1)[0][0] if violation_counts else "UNKNOWN"
        top3_violations = [v for v, _ in violation_counts.most_common(3)]

        # ── Dominant vehicle ─────────────────────────────────────────
        dominant_vehicle = zone["vehicle_type"].value_counts().index[0] if len(zone) > 0 else "UNKNOWN"

        # ── Peak hour ────────────────────────────────────────────────
        peak_hour = zone["hour"].value_counts().index[0]
        peak_hour_str = f"{peak_hour:02d}:00 - {(peak_hour+1)%24:02d}:00"

        # ── Peak day ─────────────────────────────────────────────────
        peak_day = zone["weekday"].value_counts().index[0]

        # ── Peak time bucket ─────────────────────────────────────────
        peak_bucket = zone["time_bucket"].value_counts().index[0]

        # ── Zone name: prefer named junction ─────────────────────────
        junction_names = zone[zone["near_junction"]]["junction_name"]
        if len(junction_names) > 0:
            # Pick the most common junction name in this cluster
            zone_name = junction_names.value_counts().index[0]
            # Clean BTP prefix for display: "BTP051 - Safina Plaza Junction" → "Safina Plaza Junction"
            if " - " in zone_name:
                zone_name = zone_name.split(" - ", 1)[1]
        else:
            # Fallback: use location snippet
            locs = zone["location"].dropna()
            if len(locs) > 0:
                zone_name = locs.iloc[0].split(",")[0].strip()
            else:
                zone_name = f"Zone {cluster_id}"

        # ── Police station ────────────────────────────────────────────
        police_station = zone["police_station"].value_counts().index[0] if len(zone) > 0 else "Unknown"

        # ── Month trend ───────────────────────────────────────────────
        monthly = zone.groupby("month").size().to_dict()

        # ── Recurrence score (0-10): how many unique days out of total span ──
        date_range = (zone["date"].max() - zone["date"].min()).days + 1
        recurrence_score = min(10, round((unique_days / max(date_range, 1)) * 10, 1))

        zones.append({
            "cluster_id":         cluster_id,
            "zone_name":          zone_name,
            "centroid_lat":       round(centroid_lat, 6),
            "centroid_lon":       round(centroid_lon, 6),
            "total_violations":   total_violations,
            "avg_impact":         round(avg_impact, 2),
            "total_impact":       round(total_impact, 2),
            "junction_pct":       round(junction_pct, 1),
            "dominant_violation": dominant_violation,
            "top3_violations":    top3_violations,
            "dominant_vehicle":   dominant_vehicle,
            "peak_hour":          peak_hour,
            "peak_hour_str":      peak_hour_str,
            "peak_day":           peak_day,
            "peak_bucket":        peak_bucket,
            "unique_days_active": unique_days,
            "recurrence_score":   recurrence_score,
            "police_station":     police_station,
            "monthly_trend":      monthly,
        })

    return pd.DataFrame(zones)


def main():
    print("Loading processed data...")
    df = load_data()

    print(f"Running DBSCAN on {len(df):,} records...")
    print(f"  eps = {EPS_METERS}m, min_samples = {MIN_SAMPLES}")
    df["cluster"] = run_dbscan(df)

    n_clusters = df["cluster"].nunique() - (1 if -1 in df["cluster"].values else 0)
    n_noise    = (df["cluster"] == -1).sum()
    print(f"  Found {n_clusters} hotspot zones")
    print(f"  Noise points (not in any zone): {n_noise:,}")

    print("\nBuilding zone profiles...")
    zones_df = build_zone_profiles(df)
    print(f"  Built profiles for {len(zones_df)} zones")

    # Save cluster labels back to main df
    df_out_path = os.path.join(OUTPUT_DIR, "processed_data_clustered.pkl")
    with open(df_out_path, "wb") as f:
        pickle.dump(df, f)

    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(zones_df, f)

    print(f"\nSaved zone profiles → {OUTPUT_FILE}")
    print(f"Saved clustered data → {df_out_path}")

    print("\n── Top 10 Zones by Total Violations ────────────────────────")
    top10 = zones_df.nlargest(10, "total_violations")[
        ["zone_name", "total_violations", "dominant_violation", "peak_hour_str", "police_station"]
    ]
    print(top10.to_string(index=False))


if __name__ == "__main__":
    main()
