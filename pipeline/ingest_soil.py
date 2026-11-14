"""Topsoil properties per district from ISRIC SoilGrids 2.0 (250 m), no key needed.

Queries a few points around each district centre (some centres fall on water or towns with no soil value)
and averages the 0-30 cm layers. Output: data/processed/soil.json
  ph, soc_pct (organic carbon), n_g_kg (total nitrogen), sand/silt/clay %, texture class, awc_mm (estimated)
Usage:  python pipeline/ingest_soil.py
"""
import json
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/soil.json"
PROPS = ["phh2o", "soc", "nitrogen", "sand", "silt", "clay"]
DEPTHS = ["0-5cm", "5-15cm", "15-30cm"]
WEIGHTS = [5, 10, 15]
URL = "https://rest.isric.org/soilgrids/v2.0/properties/query?lon={lon}&lat={lat}&" + "&".join(f"property={p}" for p in PROPS) + "&" + "&".join(f"depth={d}" for d in DEPTHS) + "&value=mean"
OFFSETS = [(0, 0), (0.08, 0), (-0.08, 0), (0, 0.08), (0, -0.08), (0.15, 0.15), (-0.15, -0.15)]


def query(lat, lon):
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL.format(lat=round(lat, 4), lon=round(lon, 4)), headers={"User-Agent": "crop-rotation-tool"})
            with urllib.request.urlopen(req, timeout=90) as r:
                layers = json.load(r)["properties"]["layers"]
            out = {}
            for L in layers:
                vals = [d["values"]["mean"] for d in L["depths"]]
                if any(v is None for v in vals):
                    return None
                out[L["name"]] = sum(v * w for v, w in zip(vals, WEIGHTS)) / sum(WEIGHTS) / L["unit_measure"]["d_factor"]
            return out
        except Exception as e:
            print("   retry:", type(e).__name__, flush=True)
            time.sleep(15 * (attempt + 1))
    return None


def texture(sand, clay):
    if clay >= 40: return "clay"
    if clay >= 27: return "clay loam" if sand < 45 else "sandy clay loam"
    if clay >= 20: return "sandy clay loam" if sand >= 45 else "loam"
    if sand >= 70: return "sandy loam" if clay >= 10 else "loamy sand"
    return "sandy loam" if sand >= 52 else "loam"


AWC_MM_PER_M = {"clay": 150, "clay loam": 170, "sandy clay loam": 140, "loam": 170, "sandy loam": 120, "loamy sand": 80}


def main():
    done = json.loads(OUT.read_text()) if OUT.exists() else {}
    districts = [f["properties"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]]
    for d in districts:
        if d["id"] in done:
            continue
        res = None
        for dy, dx in OFFSETS:
            res = query(d["lat"] + dy, d["lon"] + dx)
            time.sleep(12)  # SoilGrids asks for at most about 5 requests a minute
            if res:
                break
        if not res:
            print(f"{d['id']}: no soil value found", flush=True)
            continue
        tex = texture(res["sand"], res["clay"])
        done[d["id"]] = {"ph": round(res["phh2o"], 1), "soc_pct": round(res["soc"] / 10, 2), "n_g_kg": round(res["nitrogen"], 2),
                         "sand_pct": round(res["sand"], 1), "silt_pct": round(res["silt"], 1), "clay_pct": round(res["clay"], 1),
                         "texture": tex, "awc_mm": AWC_MM_PER_M[tex]}  # 1 m root zone, typical value for the texture class
        OUT.write_text(json.dumps(done, indent=1))
        print(f"{d['id']}: {done[d['id']]}", flush=True)
    print("soil.json:", len(done), "districts")


if __name__ == "__main__":
    main()
