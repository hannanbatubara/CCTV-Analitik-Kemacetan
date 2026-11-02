"""
Kalibrasi batas density (LOW/MEDIUM/HIGH) dari log worker.

  python tools/calibrate_density.py logs/traffic_20261102.jsonl --start 13:00 --end 19:00

Batas usulan = persentil ke-33 (LOW_THRESHOLD) dan ke-80 (MEDIUM_THRESHOLD) dari
avg_vehicles_in_frame, jadi ±1/3 waktu tercatat LOW dan ±1/5 waktu HIGH.
"""
import argparse
import json
from collections import defaultdict

import numpy as np


def load(path, start, end):
    rows = []
    for line in open(path, encoding="utf-8"):
        if line.strip():
            d = json.loads(line)
            hhmm = d["timestamp"][11:16]
            if start <= hhmm < end:
                rows.append((hhmm, d["traffic"]["avg_vehicles_in_frame"]))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("logs", nargs="+")
    ap.add_argument("--start", default="00:00")
    ap.add_argument("--end", default="24:00")
    ap.add_argument("--low", type=float, default=33)
    ap.add_argument("--high", type=float, default=80)
    a = ap.parse_args()

    rows = [r for p in a.logs for r in load(p, a.start, a.end)]
    if not rows:
        raise SystemExit("Tidak ada data di rentang waktu itu")
    v = np.array([x for _, x in rows])
    low, med = np.percentile(v, [a.low, a.high])
    print(f"{len(v)} snapshot ({len(v) * 10 / 3600:.1f} jam), {a.start}-{a.end}")
    print("avg kendaraan di frame: min %.1f | P10 %.1f | median %.1f | P90 %.1f | maks %.1f"
          % (v.min(), *np.percentile(v, [10, 50, 90]), v.max()))
    print(f"\nUSULAN config.py:\n  LOW_THRESHOLD = {low:.0f}\n  MEDIUM_THRESHOLD = {med:.0f}")

    hours = defaultdict(list)
    for hhmm, x in rows:
        hours[hhmm[:2]].append(x)
    print("\nJam   rata2  LOW%  MED%  HIGH%")
    for h in sorted(hours):
        x = np.array(hours[h])
        print(f"{h}:00 {x.mean():6.1f} {np.mean(x < low)*100:5.0f} "
              f"{np.mean((x >= low) & (x < med))*100:5.0f} {np.mean(x >= med)*100:5.0f}")
