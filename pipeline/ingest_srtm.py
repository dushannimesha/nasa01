"""SRTM 30 m elevation and slope per district via the free OpenTopoData API (srtm30m dataset, no login).

Same sample points and slope method as pipeline/ingest_appeears.py (5 points per district, each with a cross of
points ~550 m apart). Use this when the AppEEARS SRTM request is still queued; AppEEARS output overwrites it later.
Output: data/processed/terrain.csv   district, elev_m, slope_pct
Usage:  python pipeline/ingest_srtm.py
"""
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ingest_appeears import STEP, sample_points  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.opentopodata.org/v1/srtm30m"


def elevations(points):
    out = []
    for k in range(0, len(points), 100):  # API limit: 100 locations per request, 1 request per second
        q = "|".join(f"{la},{lo}" for lo, la in points[k:k + 100])
        for t in range(4):
            try:
                req = urllib.request.Request(API, data=json.dumps({"locations": q}).encode(),
                                             headers={"Content-Type": "application/json", "User-Agent": "crop-rotation-tool"})
                res = json.load(urllib.request.urlopen(req, timeout=60))["results"]
                out += [r["elevation"] for r in res]
                break
            except Exception as e:
                print(f"  retry {t + 1}: {type(e).__name__}", flush=True)
                time.sleep(5 * (t + 1))
        else:
            raise RuntimeError("OpenTopoData request failed")
        time.sleep(1.1)
    return out


def main():
    rows = []
    for d, pts in sample_points().items():
        for i, (lo, la) in enumerate(pts):
            for tag, dx, dy in (("c", 0, 0), ("e", STEP, 0), ("w", -STEP, 0), ("n", 0, STEP), ("s", 0, -STEP)):
                rows.append({"district": d, "pt": f"{d}_{i}", "tag": tag, "lat": round(la + dy, 5), "lon": round(lo + dx, 5)})
    df = pd.DataFrame(rows)
    df["z"] = elevations(list(zip(df.lon, df.lat)))
    w = df.pivot_table(index=["district", "pt"], columns="tag", values="z", aggfunc="first").dropna().reset_index()
    lat = df.groupby("pt").lat.mean()
    dx = 2 * STEP * 111320 * w.pt.map(lat).apply(lambda v: math.cos(math.radians(v)))
    dy = 2 * STEP * 110570
    w["slope_pct"] = (((w.e - w.w) / dx) ** 2 + ((w.n - w.s) / dy) ** 2) ** 0.5 * 100
    terr = w.groupby("district").agg(elev_m=("c", "median"), slope_pct=("slope_pct", "median")).round(1).reset_index()
    terr.to_csv(ROOT / "data/processed/terrain.csv", index=False)
    print(f"terrain.csv: {len(terr)} districts from {len(df)} SRTM points")
    print(terr.sort_values("slope_pct", ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
