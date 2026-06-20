"""
Master pipeline runner.
Run this once before launching the dashboard.
  python3 run_pipeline.py
"""

import subprocess
import sys
import os
import time

STEPS = [
    ("01 — Clean & Score",       "pipeline/01_clean_and_score.py"),
    ("02 — Cluster Hotspots",    "pipeline/02_cluster_hotspots.py"),
    ("03 — PII Scoring",         "pipeline/03_pii_scoring.py"),
    ("04 — Temporal Analysis",   "pipeline/04_temporal_analysis.py"),
    ("05 — Repeat Offenders",    "pipeline/05_repeat_offenders.py"),
]

BASE = os.path.dirname(os.path.abspath(__file__))

def run_step(name, script):
    path = os.path.join(BASE, script)
    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    t0 = time.time()
    result = subprocess.run([sys.executable, path], cwd=BASE)
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"\n✗ FAILED: {name}")
        sys.exit(1)
    print(f"\n✓ Done in {elapsed:.1f}s")

if __name__ == "__main__":
    print("\n🚦 Parking Intelligence Pipeline Starting...\n")
    total_start = time.time()
    for name, script in STEPS:
        run_step(name, script)
    total = time.time() - total_start
    print(f"\n{'='*60}")
    print(f"  ✅ All pipeline steps complete in {total:.1f}s")
    print(f"  Run the dashboard with:")
    print(f"  streamlit run dashboard/app.py")
    print(f"{'='*60}\n")
