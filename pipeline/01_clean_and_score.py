"""
Module 1: Data Cleaning & Severity Scoring
Reads raw CSV, parses violation types, scores each record,
and outputs a clean enriched dataframe saved as processed_data.pkl
"""

import pandas as pd
import numpy as np
import json
import os
import pickle
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
RAW_DATA = os.path.join(
    os.path.dirname(__file__),
    "../dataset/jan to may police violation_anonymized791b166 (1).csv"
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "../data/processed")
os.makedirs(OUTPUT_DIR, exist_ok=True)
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "processed_data.pkl")

# ── Severity Weights ──────────────────────────────────────────────────────────
# Higher = more congestion impact
VIOLATION_SEVERITY = {
    "DOUBLE PARKING":                          10,
    "PARKING NEAR TRAFFIC LIGHT OR ZEBRA CROSS": 9,
    "PARKING NEAR ROAD CROSSING":              9,
    "PARKING IN A MAIN ROAD":                  8,
    "WRONG PARKING":                           7,
    "PARKING OPPOSITE TO ANOTHER PARKED VEHICLE": 7,
    "PARKING ON FOOTPATH":                     6,
    "PARKING NEAR BUSTOP/SCHOOL/HOSPITAL ETC": 6,
    "NO PARKING":                              5,
    "PARKING OTHER THAN BUS STOP":             4,
}

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

# Junction proximity bonus
JUNCTION_BONUS = 3


def parse_violation_types(raw: str) -> list:
    """Parse JSON array string into list of violation type strings."""
    if not raw or raw == "NULL":
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []


def compute_violation_severity(violations: list) -> float:
    """Return max severity score from list of violation types."""
    if not violations:
        return 1
    scores = [VIOLATION_SEVERITY.get(v, 1) for v in violations]
    return max(scores)


def compute_vehicle_weight(vehicle_type: str) -> int:
    """Return vehicle congestion weight."""
    return VEHICLE_WEIGHT.get(str(vehicle_type).strip().upper(), 1)


def is_near_junction(junction_name: str) -> bool:
    """True if record is tagged to a real junction."""
    return (
        junction_name is not None
        and junction_name not in ("No Junction", "NULL", "", "nan")
    )


def load_and_clean(path: str) -> pd.DataFrame:
    print("Loading dataset...")
    df = pd.read_csv(path, low_memory=False)
    print(f"  Loaded {len(df):,} records, {len(df.columns)} columns")

    # ── Drop rows without GPS ─────────────────────────────────────────────
    df = df.dropna(subset=["latitude", "longitude"])
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # ── Filter to Bengaluru bounding box ─────────────────────────────────
    df = df[
        (df["latitude"].between(12.7, 13.2)) &
        (df["longitude"].between(77.3, 77.9))
    ]
    print(f"  After GPS filter: {len(df):,} records")

    # ── Parse timestamps ──────────────────────────────────────────────────
    df["created_datetime"] = pd.to_datetime(
        df["created_datetime"], errors="coerce", utc=True
    )
    df = df.dropna(subset=["created_datetime"])
    df["created_datetime"] = df["created_datetime"].dt.tz_convert("Asia/Kolkata")

    df["hour"]    = df["created_datetime"].dt.hour
    df["day"]     = df["created_datetime"].dt.day
    df["month"]   = df["created_datetime"].dt.month
    df["weekday"] = df["created_datetime"].dt.day_name()
    df["date"]    = df["created_datetime"].dt.date
    df["week"]    = df["created_datetime"].dt.isocalendar().week.astype(int)

    # ── Parse violation types ─────────────────────────────────────────────
    print("  Parsing violation types...")
    df["violation_list"] = df["violation_type"].apply(parse_violation_types)

    # ── Severity score ────────────────────────────────────────────────────
    df["violation_severity"] = df["violation_list"].apply(compute_violation_severity)

    # ── Vehicle weight ────────────────────────────────────────────────────
    df["vehicle_weight"] = df["vehicle_type"].apply(compute_vehicle_weight)

    # ── Junction flag ─────────────────────────────────────────────────────
    df["near_junction"] = df["junction_name"].apply(is_near_junction)
    df["junction_bonus"] = df["near_junction"].apply(
        lambda x: JUNCTION_BONUS if x else 0
    )

    # ── Record-level Impact Score ─────────────────────────────────────────
    # Raw score per individual violation record
    df["record_impact"] = (
        df["violation_severity"] * df["vehicle_weight"] + df["junction_bonus"]
    )

    # ── Time of day bucket ────────────────────────────────────────────────
    def time_bucket(hour):
        if 0 <= hour < 6:
            return "Late Night (12AM-6AM)"
        elif 6 <= hour < 10:
            return "Morning Rush (6AM-10AM)"
        elif 10 <= hour < 16:
            return "Afternoon (10AM-4PM)"
        elif 16 <= hour < 20:
            return "Evening Rush (4PM-8PM)"
        else:
            return "Night (8PM-12AM)"

    df["time_bucket"] = df["hour"].apply(time_bucket)

    # ── Primary violation (first in list) ────────────────────────────────
    df["primary_violation"] = df["violation_list"].apply(
        lambda x: x[0] if x else "UNKNOWN"
    )

    print(f"  Final clean records: {len(df):,}")
    return df


def main():
    df = load_and_clean(RAW_DATA)

    # Save processed data
    with open(OUTPUT_FILE, "wb") as f:
        pickle.dump(df, f)
    print(f"\nSaved to {OUTPUT_FILE}")

    # Quick stats
    print("\n── Quick Stats ─────────────────────────────────────────────")
    print(f"Date range : {df['created_datetime'].min().date()} → {df['created_datetime'].max().date()}")
    print(f"Near junction: {df['near_junction'].sum():,} ({df['near_junction'].mean()*100:.1f}%)")
    print(f"Avg record impact score: {df['record_impact'].mean():.2f}")
    print(f"Max record impact score: {df['record_impact'].max()}")
    print(f"\nTop violation types:")
    from collections import Counter
    all_v = [v for lst in df["violation_list"] for v in lst]
    for k, c in Counter(all_v).most_common(8):
        print(f"  {k}: {c:,}")


if __name__ == "__main__":
    main()
