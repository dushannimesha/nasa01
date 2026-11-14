"""M2: daily crop water balance (FAO-56 single crop coefficient with a root-zone bucket).

For every district x season x crop x year it runs the crop from a fixed sowing date and reports
  etc_mm        crop water requirement (Kc x ET0)
  ratio_rain    share of that requirement met by rain alone (actual / potential crop evapotranspiration)
  rel_yield     FAO-33 yield response: 1 - Ky x (1 - ratio_rain)
  irrig_mm      extra water needed to remove the stress

Reads   data/processed/daily/<district>.csv, web/public/data/crops.json (crop stages, Kc, Ky)
Writes  data/processed/water_balance.csv           one row per district, season, crop, year
        data/processed/water_balance_summary.json  1991-2020 statistics and the 2021 values

Assumptions (stated in the app): sowing on 25 Oct (Maha) and 25 Apr (Yala); root-zone available water
120 mm unless soil data says otherwise; depletion fraction 0.5; rain above 1 mm/day counts in full until
the root zone is full, the rest drains. Paddy also needs water for land preparation and percolation.
Usage:  python models/water_balance.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data/processed"
SOW = {"maha": (10, 25), "yala": (4, 25)}
TAW_DEFAULT, P_DEPLETION = 120.0, 0.5
PADDY_EXTRA = {"land_prep_mm": 150.0, "percolation_mm_day": 3.0}


def kc_series(crop):
    return np.concatenate([np.full(s["days"], s["kc"]) for s in crop["stages"]])


def run_season(rain, et0, kc, ky, taw=TAW_DEFAULT, start_depletion=0.5):
    """Daily bucket. Returns (ETc, actual ET under rain only)."""
    raw = P_DEPLETION * taw
    dr = start_depletion * taw
    etc_sum = eta_sum = 0.0
    for p, e, k in zip(rain, et0, kc):
        etc = k * e
        ks = 1.0 if dr <= raw else max(0.0, (taw - dr) / (taw - raw))
        eta = ks * etc
        dr = min(taw, max(0.0, dr - (p if p >= 1 else 0.0) + eta))
        etc_sum += etc
        eta_sum += eta
    return etc_sum, eta_sum


def main():
    crops = json.loads((ROOT / "web/public/data/crops.json").read_text(encoding="utf-8"))["crops"]
    districts = [f["properties"]["id"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]]
    rows = []
    for did in districts:
        df = pd.read_csv(OUT / "daily" / f"{did}.csv", parse_dates=["date"]).set_index("date")
        for crop in crops:
            kc = kc_series(crop)
            for season, (m, d) in SOW.items():
                for year in range(1982, 2022):
                    start = pd.Timestamp(year - 1 if season == "maha" else year, m, d)
                    w = df.loc[start:start + pd.Timedelta(days=len(kc) - 1)]
                    if len(w) < len(kc):
                        continue
                    etc, eta = run_season(w.rain.to_numpy(), w.et0.to_numpy(), kc, crop["ky"])
                    need = etc + (PADDY_EXTRA["land_prep_mm"] + PADDY_EXTRA["percolation_mm_day"] * len(kc) if crop["id"] == "paddy" else 0)
                    ratio = eta / etc
                    rows.append({"district": did, "season": season, "crop": crop["id"], "year": year, "etc_mm": etc, "need_mm": need,
                                 "season_rain_mm": w.rain.sum(), "ratio_rain": ratio, "rel_yield": max(0.0, 1 - crop["ky"] * (1 - ratio)),
                                 "irrig_mm": need - eta if crop["id"] == "paddy" else etc - eta})
    wb = pd.DataFrame(rows)
    wb.round(3).to_csv(OUT / "water_balance.csv", index=False)

    base = wb[(wb.year >= 1991) & (wb.year <= 2020)]
    summary = {}
    for (did, season, crop), g in base.groupby(["district", "season", "crop"]):
        y21 = wb[(wb.district == did) & (wb.season == season) & (wb.crop == crop) & (wb.year == 2021)].iloc[0]
        summary.setdefault(did, {}).setdefault(crop, {})[season] = {
            "need_mm": round(float(g.need_mm.mean())), "etc_mm": round(float(g.etc_mm.mean())),
            "ratio_rain": [round(float(g.ratio_rain.quantile(q)), 3) for q in (0.1, 0.5, 0.9)],
            "rel_yield_rain": [round(float(g.rel_yield.quantile(q)), 3) for q in (0.1, 0.5, 0.9)],
            "irrig_mm": round(float(g.irrig_mm.mean())),
            "y2021": {"ratio_rain": round(float(y21.ratio_rain), 3), "rel_yield_rain": round(float(y21.rel_yield), 3), "irrig_mm": round(float(y21.irrig_mm))},
        }
    (OUT / "water_balance_summary.json").write_text(json.dumps(summary))
    print(f"water_balance.csv: {len(wb)} rows")
    show = base[base.district.isin(["anuradhapura", "kalutara", "jaffna"])].groupby(["district", "season", "crop"])[["etc_mm", "ratio_rain", "rel_yield", "irrig_mm"]].mean().round(2)
    print(show.to_string())


if __name__ == "__main__":
    main()
