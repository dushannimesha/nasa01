"""Climate outlook per district from Open-Meteo (free, no key; not NASA):
  - Seasonal forecast (ECMWF SEAS5 via Open-Meteo): rain for the coming months against the district's
    NASA POWER 1991-2020 normal -> below / near / above normal.
  - Climate projections (CMIP6 HighResMIP models via Open-Meteo Climate API): 2040-2049 against 1995-2014,
    change in Maha and Yala rain (%) and mean temperature (deg C), averaged over the models that answer.
Output: data/processed/climate_outlook.json        Usage: python pipeline/ingest_openmeteo.py
"""
import json
import time
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed/climate_outlook.json"
MODELS = ["EC_Earth3P_HR", "MRI_AGCM3_2_S", "CMCC_CM2_VHR4"]
MAHA, YALA = [10, 11, 12, 1, 2, 3], [4, 5, 6, 7, 8, 9]


def get(url, params, tries=3):
    q = url + "?" + urllib.parse.urlencode(params)
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(q, headers={"User-Agent": "crop-rotation-tool"}), timeout=180) as r:
                return json.load(r)
        except Exception as e:
            print("   retry:", type(e).__name__, flush=True)
            time.sleep(10 * (k + 1))
    raise RuntimeError("Open-Meteo request failed")


def main():
    climate = json.loads((ROOT / "data/processed/climate_summary.json").read_text())["districts"]
    districts = [f["properties"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]]
    out = json.loads(OUT.read_text()) if OUT.exists() else {}
    limited = [False]
    for d in districts:
        if d["id"] in out and out[d["id"]].get("future") and not out[d["id"]]["future"].get("borrowedFrom"):
            continue
        loc = {"latitude": d["lat"], "longitude": d["lon"]}
        # --- seasonal outlook: monthly rain totals from the ensemble mean ---
        s = get("https://seasonal-api.open-meteo.com/v1/seasonal", {**loc, "daily": "precipitation_sum", "forecast_days": 183})
        sd = pd.DataFrame({"t": pd.to_datetime(s["daily"]["time"])})
        members = [k for k in s["daily"] if k.startswith("precipitation_sum")]
        sd["rain"] = pd.DataFrame({k: s["daily"][k] for k in members}).mean(axis=1)
        sd = sd[sd.t.dt.day.groupby(sd.t.dt.to_period("M")).transform("count") >= 25]  # whole months only
        mon = sd.groupby(sd.t.dt.to_period("M")).rain.sum().head(3)
        normal = sum(climate[d["id"]]["rain"][p.month - 1] for p in mon.index)
        pct = (mon.sum() / normal - 1) * 100 if normal else 0
        seasonal = {"months": [str(p) for p in mon.index], "rain_mm": round(float(mon.sum())), "normal_mm": round(normal), "anomaly_pct": round(float(pct)),
                    "rainOutlook": "below normal" if pct < -15 else "above normal" if pct > 15 else "near normal",
                    "issued": date.today().isoformat(), "source": "Open-Meteo Seasonal Forecast API (ECMWF SEAS5 ensemble mean)"}
        # --- 2040s change, CMIP6 high-resolution models (heavy requests: stop after the first rate-limit refusal) ---
        deltas = []
        for m in ([] if limited[0] else MODELS):
            try:
                c = get("https://climate-api.open-meteo.com/v1/climate", {**loc, "start_date": "1995-01-01", "end_date": "2049-12-31", "models": m, "daily": "precipitation_sum,temperature_2m_mean"}, tries=1)
            except RuntimeError:
                limited[0] = True
                break
            cd = pd.DataFrame({"t": pd.to_datetime(c["daily"]["time"]), "p": c["daily"]["precipitation_sum"], "tm": c["daily"]["temperature_2m_mean"]}).dropna()
            base, fut = cd[cd.t.dt.year <= 2014], cd[cd.t.dt.year >= 2040]
            per = lambda df, months: df[df.t.dt.month.isin(months)].groupby(df.t.dt.year).p.sum().mean()
            deltas.append({"maha": per(fut, MAHA) / per(base, MAHA) - 1, "yala": per(fut, YALA) / per(base, YALA) - 1, "t": fut.tm.mean() - base.tm.mean()})
            time.sleep(1)
        future = None
        if deltas:
            dd = pd.DataFrame(deltas).mean()
            future = {"period": "2040-2049 vs 1995-2014", "rainPct": {"maha": round(dd.maha * 100), "yala": round(dd.yala * 100)}, "tempC": round(float(dd.t), 1),
                      "models": len(deltas), "source": "Open-Meteo Climate API (CMIP6 HighResMIP: " + ", ".join(MODELS[: len(deltas)]) + ")"}
        out[d["id"]] = {"seasonal": seasonal, "future": future}
        OUT.write_text(json.dumps(out, indent=1))
        print(f"{d['id']}: outlook {seasonal['rainOutlook']} ({seasonal['anomaly_pct']:+d} %), 2040s " +
              (f"Maha {future['rainPct']['maha']:+d} %, Yala {future['rainPct']['yala']:+d} %, {future['tempC']:+.1f} C" if future else "n/a"), flush=True)
        time.sleep(1)
    # districts without their own projection borrow the nearest computed one (labelled); re-run later to replace them
    own = {k: v["future"] for k, v in out.items() if v.get("future") and not v["future"].get("borrowedFrom")}
    pos = {d["id"]: (d["lat"], d["lon"]) for d in districts}
    for k, v in out.items():
        if (not v.get("future") or v["future"].get("borrowedFrom")) and own:
            near = min(own, key=lambda o: (pos[o][0] - pos[k][0]) ** 2 + (pos[o][1] - pos[k][1]) ** 2)
            v["future"] = {**own[near], "borrowedFrom": near}
    OUT.write_text(json.dumps(out, indent=1))
    print("climate_outlook.json:", len(out), "districts;", len(own), "with their own projection")


if __name__ == "__main__":
    main()
