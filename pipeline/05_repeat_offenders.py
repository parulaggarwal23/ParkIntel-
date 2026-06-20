"""
Module 5: Repeat Offender Analysis
Identifies vehicles with multiple violations — chronic offenders
who are being repeatedly caught but never actioned.
"""

import pandas as pd
import pickle
import os

CLUSTERED   = os.path.join(os.path.dirname(__file__), "../data/processed/processed_data_clustered.pkl")
RANKED      = os.path.join(os.path.dirname(__file__), "../data/processed/ranked_zones.pkl")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "../data/processed/repeat_offenders.pkl")


def main():
    print("Loading data...")
    with open(CLUSTERED, "rb") as f:
        df = pickle.load(f)
    with open(RANKED, "rb") as f:
        ranked = pickle.load(f)

    # ── Build cluster_id → zone_name map ──────────────────────────────────
    zone_map = dict(zip(ranked["cluster_id"], ranked["zone_name"]))

    # ── Per-vehicle aggregation ───────────────────────────────────────────
    def top_zone(clusters):
        valid = [c for c in clusters if c != -1]
        if not valid:
            return "Unknown"
        top_cluster = pd.Series(valid).value_counts().index[0]
        return zone_map.get(top_cluster, "Unknown")

    def top2_stations(stations):
        top = pd.Series(list(stations)).value_counts().head(2).index.tolist()
        return ", ".join(top)

    def days_active(dates):
        return (max(dates) - min(dates)).days + 1

    print("Computing repeat offender profiles...")
    repeat = df.groupby("vehicle_number").agg(
        total_violations  = ("id",                "count"),
        vehicle_type      = ("vehicle_type",      lambda x: x.value_counts().index[0]),
        first_seen        = ("created_datetime",  "min"),
        last_seen         = ("created_datetime",  "max"),
        unique_zones      = ("cluster",           lambda x: x[x != -1].nunique()),
        top_zone          = ("cluster",           top_zone),
        top_stations      = ("police_station",    top2_stations),
        top_violation     = ("primary_violation", lambda x: x.value_counts().index[0]),
        avg_severity      = ("violation_severity","mean"),
    ).reset_index()

    repeat["days_active"] = repeat.apply(
        lambda r: (r["last_seen"] - r["first_seen"]).days + 1, axis=1
    )
    repeat["violations_per_day"] = (
        repeat["total_violations"] / repeat["days_active"]
    ).round(2)

    # ── Offender tier ─────────────────────────────────────────────────────
    def offender_tier(n):
        if n >= 20:  return ("🔴 Chronic",  "chronic")
        if n >= 10:  return ("🟠 Frequent", "frequent")
        if n >= 5:   return ("🟡 Repeat",   "repeat")
        return           ("🟢 Occasional","occasional")

    repeat["tier_label"] = repeat["total_violations"].apply(lambda n: offender_tier(n)[0])
    repeat["tier_class"] = repeat["total_violations"].apply(lambda n: offender_tier(n)[1])

    # ── Format dates for display ──────────────────────────────────────────
    repeat["first_seen_str"] = repeat["first_seen"].dt.strftime("%d %b %Y")
    repeat["last_seen_str"]  = repeat["last_seen"].dt.strftime("%d %b %Y")

    # ── Clean vehicle type ────────────────────────────────────────────────
    repeat["vehicle_type"] = repeat["vehicle_type"].str.title()
    repeat["top_violation"] = repeat["top_violation"].str.replace(
        "WRONG PARKING", "Wrong Parking").str.replace(
        "NO PARKING", "No Parking").str.title()

    repeat = repeat.sort_values("total_violations", ascending=False).reset_index(drop=True)
    repeat["rank"] = repeat.index + 1

    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(repeat, f)
    print(f"Saved → {OUTPUT_FILE}")

    # Stats
    print(f"\n── Repeat Offender Summary ──────────────────────────────────")
    print(f"  Total unique vehicles:          {len(df['vehicle_number'].unique()):,}")
    print(f"  🔴 Chronic  (20+ violations):   {(repeat['total_violations'] >= 20).sum()}")
    print(f"  🟠 Frequent (10–19 violations): {((repeat['total_violations'] >= 10) & (repeat['total_violations'] < 20)).sum()}")
    print(f"  🟡 Repeat   (5–9 violations):   {((repeat['total_violations'] >= 5) & (repeat['total_violations'] < 10)).sum()}")
    print(f"\n  Top offender: {repeat.iloc[0]['vehicle_number']} — {int(repeat.iloc[0]['total_violations'])} violations ({repeat.iloc[0]['vehicle_type']})")
    print(f"  Operating zone: {repeat.iloc[0]['top_zone']}")


if __name__ == "__main__":
    main()
