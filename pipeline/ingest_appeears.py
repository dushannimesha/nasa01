"""MODIS NDVI, SMAP root-zone soil moisture and SRTM elevation per district, via NASA AppEEARS point requests.

Points: 5 points spread inside each district polygon (no cropland mask is applied, so NDVI includes some
non-farm land; the model uses NDVI anomalies against each district's own normal, which reduces that bias).
Outputs
  data/processed/ndvi_monthly.csv   district, date, ndvi            (MOD13A3.061, 1 km, monthly, 2001-2021)
  data/processed/smap_monthly.csv   district, date, sm_rootzone     (SPL4SMGP.008, 9 km, 2015-2021, m3/m3)
  data/processed/terrain.csv        district, elev_m, slope_pct     (SRTMGL1_NC.003, 30 m)
Resumable: task ids are kept in data/raw/appeears/tasks.json; re-running only polls and downloads.
Usage:  python pipeline/ingest_appeears.py
"""
import json
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import earthdata as ed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/appeears"
OUT = ROOT / "data/processed"
MANUAL = ROOT / "data/manual/appeears"  # hand-downloaded result CSVs; point lists to upload are here too
STEP = 0.005  # ~550 m between the SRTM cross points


def inside(lon, lat, geom):
    def ring(r):
        c = False
        for i in range(len(r)):
            (x1, y1), (x2, y2) = r[i], r[i - 1]
            if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
                c = not c
        return c
    polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
    return any(ring(p[0]) and not any(ring(h) for h in p[1:]) for p in polys)


def sample_points(n=5):
    pts = {}
    for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]:
        g, did = f["geometry"], f["properties"]["id"]
        coords = [c for poly in ([g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]) for c in poly[0]]
        xs, ys = [c[0] for c in coords], [c[1] for c in coords]
        grid = [(round(x, 4), round(y, 4)) for y in frange(min(ys), max(ys), 0.03) for x in frange(min(xs), max(xs), 0.03) if inside(x, y, g)]
        if not grid:
            grid = [(f["properties"]["lon"], f["properties"]["lat"])]
        k = max(1, len(grid) // n)
        pts[did] = grid[k // 2::k][:n]
    return pts


def frange(a, b, s):
    v = a + s / 2
    while v < b:
        yield v
        v += s


def submit(token, name, layers, coords, start, end):
    body = {"task_type": "point", "task_name": name,
            "params": {"dates": [{"startDate": start, "endDate": end}], "layers": layers, "coordinates": coords}}
    return ed.appeears("task", token, data=body, method="POST")["task_id"]


def col(df, part):
    return next(c for c in df.columns if part in c)


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    tasks_file = RAW / "tasks.json"
    tasks = json.loads(tasks_file.read_text()) if tasks_file.exists() else {}
    pts = sample_points()
    token = ed.appeears_token()
    coords_ndvi = [{"id": f"{d}_{i}", "category": d, "latitude": la, "longitude": lo} for d, p in pts.items() for i, (lo, la) in enumerate(p)]
    coords_smap = [{"id": f"{d}_c", "category": d, "latitude": p[len(p) // 2][1], "longitude": p[len(p) // 2][0]} for d, p in pts.items()]
    coords_dem = [{"id": f"{d}_{i}_{tag}", "category": d, "latitude": round(la + dy, 5), "longitude": round(lo + dx, 5)}
                  for d, p in pts.items() for i, (lo, la) in enumerate(p)
                  for tag, dx, dy in (("c", 0, 0), ("e", STEP, 0), ("w", -STEP, 0), ("n", 0, STEP), ("s", 0, -STEP))]
    spec = {
        "ndvi": ([{"product": "MOD13A3.061", "layer": "_1_km_monthly_NDVI"}], coords_ndvi, "01-01-2001", "12-31-2021"),
        "smap": ([{"product": "SPL4SMGP.008", "layer": "Geophysical_Data_sm_rootzone"}], coords_smap, "04-01-2015", "12-31-2021"),
        "dem": ([{"product": "SRTMGL1_NC.003", "layer": "SRTMGL1_DEM"}], coords_dem, "02-11-2000", "02-21-2000"),
    }
    for key, (layers, coords, a, b) in spec.items():
        if key not in tasks:
            tasks[key] = submit(token, f"fieldshift-{key}", layers, coords, a, b)
            tasks_file.write_text(json.dumps(tasks, indent=1))
            print(f"submitted {key}: {len(coords)} points", flush=True)
    files = manual_files()
    for key in sorted(tasks, key=["smap", "dem", "ndvi"].index):  # smallest first; each output is written as soon as it arrives
        if key in files:
            print(f"using your downloaded {key} files: {[f.name for f in files[key]]}", flush=True)
        elif key == "dem" and (OUT / "terrain.csv").exists():
            continue  # slope already made by pipeline/ingest_srtm.py
        else:
            ed.wait_task(token, tasks[key])
            files[key] = ed.download_task_csvs(token, tasks[key], RAW / key)
            print(f"downloaded {key}: {[f.name for f in files[key]]}", flush=True)
        write_outputs({key: files[key]})


def manual_files():
    """Result CSVs downloaded by hand from the AppEEARS website into data/manual/appeears/ (any file name)."""
    found = {}
    for f in sorted(MANUAL.glob("*.csv")) if MANUAL.exists() else []:
        head = f.open(encoding="utf-8", errors="ignore").readline()
        key = "ndvi" if "MOD13A3" in head else "smap" if "SPL4SMGP" in head else "dem" if "SRTMGL1" in head else None
        if key:
            found.setdefault(key, []).append(f)
    return found


def write_outputs(files):
    if "ndvi" in files:
        write_ndvi(files["ndvi"])
    if "smap" in files:
        write_smap(files["smap"])
    if "dem" in files:
        write_dem(files["dem"])


def write_ndvi(paths):
    nd = pd.concat(pd.read_csv(f) for f in paths)
    nd = nd.rename(columns={col(nd, "monthly_NDVI"): "ndvi"})
    nd = nd[(nd.ndvi > -0.2) & (nd.ndvi <= 1)]
    nd["district"], nd["date"] = nd.Category, pd.to_datetime(nd.Date).dt.strftime("%Y-%m-01")
    nd.groupby(["district", "date"]).ndvi.mean().round(4).reset_index().to_csv(OUT / "ndvi_monthly.csv", index=False)
    print(f"ndvi_monthly.csv: {len(nd)} values, {nd.district.nunique()} districts, {nd.date.min()} to {nd.date.max()}")


def write_smap(paths):
    sm = pd.concat(pd.read_csv(f) for f in paths)
    sm = sm.rename(columns={col(sm, "sm_rootzone"): "sm"})
    sm = sm[(sm.sm > 0) & (sm.sm < 1)]
    sm["district"], sm["date"] = sm.Category, pd.to_datetime(sm.Date).dt.strftime("%Y-%m-01")
    sm.groupby(["district", "date"]).sm.mean().round(4).rename("sm_rootzone").reset_index().to_csv(OUT / "smap_monthly.csv", index=False)
    print(f"smap_monthly.csv: {len(sm)} values, {sm.district.nunique()} districts, {sm.date.min()} to {sm.date.max()}")


def write_dem(paths):
    dm = pd.concat(pd.read_csv(f) for f in paths)
    dm = dm.rename(columns={col(dm, "SRTMGL1_DEM"): "z"})
    dm["pt"] = dm.ID.str.rsplit("_", n=1).str[0]
    dm["tag"] = dm.ID.str.rsplit("_", n=1).str[1]
    w = dm.pivot_table(index=["Category", "pt"], columns="tag", values="z", aggfunc="first").dropna().reset_index()
    lat = dm.groupby("pt").Latitude.mean()
    dx = 2 * STEP * 111320 * w.pt.map(lat).apply(lambda v: math.cos(math.radians(v)))
    dy = 2 * STEP * 110570
    w["slope_pct"] = (((w.e - w.w) / dx) ** 2 + ((w.n - w.s) / dy) ** 2) ** 0.5 * 100
    terr = w.groupby("Category").agg(elev_m=("c", "median"), slope_pct=("slope_pct", "median")).round(1).reset_index().rename(columns={"Category": "district"})
    terr.to_csv(OUT / "terrain.csv", index=False)
    print("terrain:", terr.set_index("district").slope_pct.to_dict())


if __name__ == "__main__":
    main()
