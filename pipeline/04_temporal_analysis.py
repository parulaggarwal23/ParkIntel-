"""
Module 4: Temporal Pattern Analysis
Produces time-based pattern data per zone and overall.
Outputs temporal_data.pkl for use in the dashboard.
"""

import pandas as pd
import numpy as np
import pickle
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
CLUSTERED   = os.path.join(os.path.dirname(__file__), "../data/processed/processed_data_clustered.pkl")
RANKED      = os.path.join(os.path.dirname(__file__), "../data/processed/ranked_zones.pkl")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "../data/processed/temporal_data.pkl")

MONTH_NAMES = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr",
    5: "May", 6: "Jun", 7: "Jul", 8: "Aug",
    9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"
}

WEEKDAY_ORDER = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]


def main():
    print("Loading data...")
    with open(CLUSTERED, "rb") as f:
        df = pickle.load(f)
    with open(RANKED, "rb") as f:
        ranked = pickle.load(f)

    # Only include clustered points (exclude noise)
    df_valid = df[df["cluster"] != -1].copy()

    # ── 1. Overall hourly distribution ───────────────────────────────────
    hourly_overall = (
        df_valid.groupby("hour").size()
        .reset_index(name="violations")
        .sort_values("hour")
    )

    # ── 2. Overall day-of-week distribution ──────────────────────────────
    daily_overall = (
        df_valid.groupby("weekday").size()
        .reset_index(name="violations")
    )
    daily_overall["weekday"] = pd.Categorical(
        daily_overall["weekday"], categories=WEEKDAY_ORDER, ordered=True
    )
    daily_overall = daily_overall.sort_values("weekday")

    # ── 3. Monthly trend ─────────────────────────────────────────────────
    monthly_overall = (
        df_valid.groupby("month").size()
        .reset_index(name="violations")
    )
    monthly_overall["month_name"] = monthly_overall["month"].map(MONTH_NAMES)

    # ── 4. Hour × Weekday heatmap ─────────────────────────────────────────
    heatmap_data = (
        df_valid.groupby(["hour", "weekday"]).size()
        .reset_index(name="violations")
    )
    heatmap_pivot = heatmap_data.pivot(
        index="weekday", columns="hour", values="violations"
    ).fillna(0)
    heatmap_pivot = heatmap_pivot.reindex(
        [d for d in WEEKDAY_ORDER if d in heatmap_pivot.index]
    )

    # ── 5. Per-zone peak patterns (top 20 zones) ─────────────────────────
    top20_ids = ranked.head(20)["cluster_id"].tolist()
    zone_temporal = {}

    for cluster_id in top20_ids:
        zone_df = df_valid[df_valid["cluster"] == cluster_id]
        zone_name = ranked[ranked["cluster_id"] == cluster_id]["zone_name"].values[0]

        hourly = zone_df.groupby("hour").size().reset_index(name="count")
        daily  = zone_df.groupby("weekday").size().reset_index(name="count")
        daily["weekday"] = pd.Categorical(
            daily["weekday"], categories=WEEKDAY_ORDER, ordered=True
        )
        daily = daily.sort_values("weekday")

        zone_temporal[cluster_id] = {
            "zone_name": zone_name,
            "hourly":    hourly,
            "daily":     daily,
        }

    # ── 6. Violation type trend over months ───────────────────────────────
    from collections import Counter
    monthly_vtype = {}
    for month in sorted(df_valid["month"].unique()):
        mdf = df_valid[df_valid["month"] == month]
        all_v = [v for lst in mdf["violation_list"] for v in lst]
        top5 = Counter(all_v).most_common(5)
        monthly_vtype[MONTH_NAMES.get(month, str(month))] = dict(top5)

    # ── 7. Time bucket distribution ───────────────────────────────────────
    bucket_dist = (
        df_valid.groupby("time_bucket").size()
        .reset_index(name="violations")
        .sort_values("violations", ascending=False)
    )

    output = {
        "hourly_overall":   hourly_overall,
        "daily_overall":    daily_overall,
        "monthly_overall":  monthly_overall,
        "heatmap_pivot":    heatmap_pivot,
        "zone_temporal":    zone_temporal,
        "monthly_vtype":    monthly_vtype,
        "bucket_dist":      bucket_dist,
    }

    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(output, f)
    print(f"Saved temporal analysis → {OUTPUT_FILE}")

    # Quick print
    print("\n── Violations by Time Bucket ────────────────────────────────")
    print(bucket_dist.to_string(index=False))
    print("\n── Monthly Trend ────────────────────────────────────────────")
    print(monthly_overall[["month_name","violations"]].to_string(index=False))


if __name__ == "__main__":
    main()
