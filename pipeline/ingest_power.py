"""Download NASA POWER daily agro-climate data for every district (one point per district).

No key needed. Output: data/raw/power/<district>.csv with columns
date, tmax, tmin, rain, rh, wind, solar   (deg C, deg C, mm/day, %, m/s at 2 m, MJ/m2/day)

Usage:  python pipeline/ingest_power.py [start_year] [end_year]
Already-downloaded districts are skipped, so the script can be re-run after a failure.
"""
import csv
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "power"
PARAMS = {"T2M_MAX": "tmax", "T2M_MIN": "tmin", "PRECTOTCORR": "rain", "RH2M": "rh", "WS2M": "wind", "ALLSKY_SFC_SW_DWN": "solar"}
URL = ("https://power.larc.nasa.gov/api/temporal/daily/point?parameters={p}&community=AG"
       "&longitude={lon}&latitude={lat}&start={y0}0101&end={y1}1231&format=JSON")


def fetch(lat, lon, y0, y1):
    url = URL.format(p=",".join(PARAMS), lat=lat, lon=lon, y0=y0, y1=y1)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "crop-rotation-tool"}), timeout=180) as r:
                return json.load(r)["properties"]["parameter"]
        except Exception as e:  # network errors and rate limits: wait and retry
            print(f"  retry {attempt + 1}: {e}", flush=True)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("NASA POWER request failed 4 times")


def main():
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 1981
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2021
    OUT.mkdir(parents=True, exist_ok=True)
    districts = [f["properties"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]]
    for i, d in enumerate(districts, 1):
        path = OUT / f"{d['id']}.csv"
        if path.exists():
            print(f"[{i}/{len(districts)}] {d['id']}: already downloaded", flush=True)
            continue
        data = fetch(d["lat"], d["lon"], y0, y1)
        days = sorted(data["T2M_MAX"])
        missing = 0
        tmp = path.with_suffix(".tmp")
        with tmp.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["date", *PARAMS.values()])
            for day in days:
                row = [data[p].get(day, -999) for p in PARAMS]
                row = ["" if v is None or v <= -900 else v for v in row]  # POWER marks missing values as -999
                missing += row.count("")
                w.writerow([f"{day[:4]}-{day[4:6]}-{day[6:]}", *row])
        tmp.replace(path)
        print(f"[{i}/{len(districts)}] {d['id']}: {len(days)} days, {missing} missing values", flush=True)
        time.sleep(1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
