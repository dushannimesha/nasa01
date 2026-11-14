"""GPM IMERG Final monthly precipitation (GPM_3IMERGM V07, 0.1 deg) over Sri Lanka, 2001-2021, via GES DISC OPeNDAP.

Each month: one small subset request for the Sri Lanka box (25 x 41 cells), decoded from the OPeNDAP binary
(.dods) response. District value = mean of the cells whose centres fall inside the district polygon
(nearest cell to the centre for very small districts). IMERG reports mm/hour; converted to mm per month.
Raw subsets are cached in data/raw/imerg/, so re-runs only fetch missing months.
Output: data/processed/imerg_monthly.csv   district, date, rain_mm
Usage:  python pipeline/ingest_imerg.py [start_year] [end_year]
"""
import calendar
import json
import struct
import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import earthdata as ed  # noqa: E402
from ingest_appeears import inside  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/imerg"
LON0, LON1, LAT0, LAT1 = 2595, 2619, 958, 998  # grid indices: lon = -179.95 + 0.1 i, lat = -89.95 + 0.1 j
URL = ("https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/GPM_3IMERGM.07/{y}/3B-MO.MS.MRG.3IMERG.{y}{m:02d}01-S000000-E235959.{m:02d}.V07B.HDF5.dods"
       f"?precipitation[0:0][{LON0}:{LON1}][{LAT0}:{LAT1}]")


def fetch(opener, y, m, tries=4):
    for k in range(tries):
        try:
            b = opener.open(URL.format(y=y, m=m), timeout=180).read()
            body = b.split(b"Data:\n", 1)[1]
            n = struct.unpack(">I", body[:4])[0]
            return list(struct.unpack(f">{n}f", body[8:8 + 4 * n]))  # order: [lon][lat]
        except Exception as e:
            print(f"   {y}-{m:02d} retry {k + 1}: {type(e).__name__}", flush=True)
            time.sleep(20 * (k + 1))
    raise RuntimeError(f"IMERG {y}-{m:02d} failed")


MANUAL = ROOT / "data/manual/imerg"


def from_files():
    """Read Harmony / GES DISC subset files (netCDF4) from data/manual/imerg/, if present."""
    import re
    import h5py
    files = sorted(MANUAL.glob("*.nc4")) if MANUAL.exists() else []
    if not files:
        return None
    feats = json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]
    rows, members = [], None
    for f in files:
        m = re.search(r"3IMERG\.(\d{4})(\d{2})01", f.name)
        y, mo = int(m.group(1)), int(m.group(2))
        with h5py.File(f, "r") as h:
            lon, lat = h["Grid/lon"][:], h["Grid/lat"][:]
            pr = h["Grid/precipitation"][0]  # [lon, lat], mm/hr
        if members is None:
            cells = [(float(lo), float(la), i, j) for i, lo in enumerate(lon) for j, la in enumerate(lat)]
            members = {}
            for ft in feats:
                idx = [(i, j) for lo, la, i, j in cells if inside(lo, la, ft["geometry"])]
                if not idx:
                    p = ft["properties"]
                    c = min(cells, key=lambda c: (c[0] - p["lon"]) ** 2 + (c[1] - p["lat"]) ** 2)
                    idx = [(c[2], c[3])]
                members[ft["properties"]["id"]] = idx
        hours = 24 * calendar.monthrange(y, mo)[1]
        for did, idx in members.items():
            v = [float(pr[i, j]) for i, j in idx if pr[i, j] >= 0]
            rows.append({"district": did, "date": f"{y}-{mo:02d}-01", "rain_mm": round(sum(v) / len(v) * hours, 1) if v else None})
    return pd.DataFrame(rows), members


def main():
    got = from_files()
    if got is not None:
        df, members = got
        df.to_csv(ROOT / "data/processed/imerg_monthly.csv", index=False)
        print(f"imerg_monthly.csv from {df.date.nunique()} monthly files: {len(df)} rows; cells per district (first 6):",
              {k: len(v) for k, v in list(members.items())[:6]})
        return
    y0 = int(sys.argv[1]) if len(sys.argv) > 1 else 2001
    y1 = int(sys.argv[2]) if len(sys.argv) > 2 else 2021
    RAW.mkdir(parents=True, exist_ok=True)
    opener = ed.earthdata_opener()
    nlat = LAT1 - LAT0 + 1
    cells = [(-179.95 + 0.1 * i, -89.95 + 0.1 * j) for i in range(LON0, LON1 + 1) for j in range(LAT0, LAT1 + 1)]
    feats = json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]
    members = {}
    for f in feats:
        idx = [k for k, (lo, la) in enumerate(cells) if inside(lo, la, f["geometry"])]
        if not idx:
            p = f["properties"]
            idx = [min(range(len(cells)), key=lambda k: (cells[k][0] - p["lon"]) ** 2 + (cells[k][1] - p["lat"]) ** 2)]
        members[f["properties"]["id"]] = idx
    rows = []
    for y in range(y0, y1 + 1):
        for m in range(1, 13):
            cache = RAW / f"{y}{m:02d}.json"
            if not cache.exists():
                cache.write_text(json.dumps(fetch(opener, y, m)))
                print(f"{y}-{m:02d} downloaded", flush=True)
            vals = json.loads(cache.read_text())
            hours = 24 * calendar.monthrange(y, m)[1]
            for did, idx in members.items():
                v = [vals[k] for k in idx if vals[k] >= 0]
                rows.append({"district": did, "date": f"{y}-{m:02d}-01", "rain_mm": round(sum(v) / len(v) * hours, 1) if v else None})
    df = pd.DataFrame(rows)
    df.to_csv(ROOT / "data/processed/imerg_monthly.csv", index=False)
    print("imerg_monthly.csv:", len(df), "rows; cells per district:", {k: len(v) for k, v in list(members.items())[:6]}, "...")


if __name__ == "__main__":
    main()
