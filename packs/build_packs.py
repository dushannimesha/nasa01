"""Writes model output and source data into the web app's data files (web/public/data).

Real inputs
  NASA POWER climate (pipeline/features.py), FAO-56 water balance (models/water_balance.py)
  DCS paddy yield and area by district and season (pipeline/parse_dcs.py)
  Paddy yield model trained to 2020 (models/yield_ml.py)
  DCS highland-crop areas 2020-2021, HARTI farmgate prices 2021, DCS population 2025 (pipeline/parse_csv.py)
  SoilGrids topsoil (pipeline/ingest_soil.py), if downloaded
Stated assumptions (listed in meta.assumptions and shown in the app)
  yields of non-paddy crops, costs of cultivation, fertilizer rates, per-capita consumption, price elasticities,
  irrigation cover by water source.
Usage:  python packs/build_packs.py   (then: cd web && node scripts/run_backtest.mjs && node scripts/make_bot_table.mjs)
"""
import json
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web/public/data"
PROC = ROOT / "data/processed"
GAP_COVER = {"tank": {"maha": 0.9, "yala": 0.6}, "well": {"maha": 0.5, "yala": 0.5}}
SEASON = {"maha": "Maha", "yala": "Yala"}
# DCS paddy yields are per NET hectare; harvested areas are GROSS. Net/gross = 0.896 (Yala 2021), 0.894 (Maha 2021/22).
NET_SHARE = 0.895

# Crop parameters. ASSUMED values are typical published figures for Sri Lanka, not yet checked against DoA tables.
CROP_UPDATE = {
    "paddy": {"refYield": None, "cost": 150000},
    "maize": {"refYield": 4.0, "cost": 140000},
    "greengram": {"refYield": 1.1, "cost": 110000},
    "cowpea": {"refYield": 1.1, "cost": 100000},
    "bigonion": {"refYield": 15.0, "cost": 600000},
    "chilli": {"name": "Green chilli", "refYield": 8.0, "cost": 450000, "kcalPerKg": 400, "proteinPerKg": 20, "perCapKg": 4.0, "elasticity": -0.5},
}
ASSUMPTIONS = [
    "Tank or canal water is assumed to cover 90 % of the rain shortfall in Maha and 60 % in Yala; an agro-well 50 %.",
    "Yields of maize, green gram, cowpea, big onion and green chilli are typical national averages (no district yield records were supplied), reduced for water stress by the FAO-56 model.",
    "Costs of cultivation, fertilizer rates, per-person consumption and price elasticities are typical published values, not yet checked against DoA tables.",
    "Prices are one week of HARTI farmgate quotes (27 Aug - 2 Sep 2021); big onion uses 80 % of the wholesale price.",
    "Population is the 2025 mid-year estimate; 2021 figures were not supplied.",
    "NASA POWER rain is on a grid of about 50 km, so neighbouring districts can share one value.",
]
REAL = ["NASA POWER climate 1981-2021", "FAO-56 crop water balance", "DCS paddy yield and area 1979-2021", "paddy yield model (trained to 2020)",
        "DCS crop areas 2020-2021", "HARTI farmgate prices 2021", "DCS population 2025"]


def main():
    climate = json.loads((PROC / "climate_summary.json").read_text())["districts"]
    wb = json.loads((PROC / "water_balance_summary.json").read_text())
    ym = json.loads((PROC / "yield_model.json").read_text())
    prices = json.loads((PROC / "prices_2021.json").read_text())
    pop = json.loads((PROC / "population.json").read_text())["districts"]
    soil = json.loads((PROC / "soil.json").read_text()) if (PROC / "soil.json").exists() else {}
    paddy = pd.read_csv(PROC / "dcs_paddy.csv")
    high = pd.read_csv(PROC / "highland_area.csv")
    real = REAL + (["SoilGrids topsoil"] if len(soil) >= 20 else [])

    cj = json.loads((WEB / "crops.json").read_text(encoding="utf-8"))
    for c in cj["crops"]:
        c.update({k: v for k, v in CROP_UPDATE[c["id"]].items() if v is not None})
        c["price"] = prices[c["id"]]["rs_per_kg"]
        c["priceSource"] = prices[c["id"]]["source"]
    crops = {c["id"]: c for c in cj["crops"]}
    meta = {"sample": False, "cropYear": "2021", "seasons": {"maha": "Maha 2020/21 (Oct-Mar)", "yala": "Yala 2021 (Apr-Sep)"},
            "dataAsOf": date.today().isoformat(), "real": real, "assumptions": ASSUMPTIONS}
    cj["meta"] = meta
    (WEB / "crops.json").write_text(json.dumps(cj), encoding="utf-8")

    q10, q90 = ym["interval"]["residual_q10"], ym["interval"]["residual_q90"]
    pred21 = {(p["district"], p["season"]): p for p in ym["predictions"]}
    national = json.loads((WEB / "national.json").read_text(encoding="utf-8"))
    national["meta"] = meta
    for d in national["districts"]:
        did, c = d["id"], climate[d["id"]]
        path = WEB / "packs" / f"{did}.json"
        pack = json.loads(path.read_text(encoding="utf-8"))
        pack["meta"] = meta
        if did in soil:
            s = soil[did]
            pack["soil"] = {"ph": s["ph"], "soc_pct": s["soc_pct"], "texture": s["texture"], "awc_mm": s["awc_mm"],
                            "n_kg_ha": int(max(30, min(90, round(25 + 20 * s["n_g_kg"])))), "source": "SoilGrids 2.0, 0-30 cm"}
        pack["climate"].update({"rain": c["rain"], "et0": c["et0"], "tmax": c["tmax"], "seasonRain": c["seasonRain"], "heatDays": c["heatDays"],
                                "seasonRain2021": c["seasonRain2021"], "rainAnom2021Pct": c["rainAnom2021Pct"], "onset": c["onset"]})
        pd_ = paddy[paddy.district == did]
        hd = high[high.district == did]
        nat_crops = {}
        yala_ratios = []
        for cid, crop in crops.items():
            pc = pack["crops"][cid]
            pc["price"], pc["cost"] = crop["price"], crop["cost"]
            area_tot = prod_tot = 0.0
            for s in ("maha", "yala"):
                r = wb[did][cid][s]
                lo, med, hi = r["ratio_rain"]
                supply = {"rain": med, **{src: round(med + (1 - med) * GAP_COVER[src][s], 3) for src in ("tank", "well")}}
                cs = pc[s]
                # ---- yield shown to farmers: potential yield before the app's own water-stress cut ----
                if cid == "paddy":
                    hist = pd_[(pd_.season == s) & (pd_.year.between(2018, 2020))].yield_t_ha.dropna()
                    base = float(hist.mean()) if len(hist) else 3.5
                    cs["yield"] = [round(max(0.5, base + q10), 2), round(base, 2), round(base + q90, 2)]
                    cs["yieldSource"] = "DCS district average 2018-2020, band from the yield model's error"
                else:
                    ref = crop["refYield"]
                    cs["yield"] = [round(ref * 0.75, 2), ref, round(ref * 1.2, 2)]
                    cs["yieldSource"] = "typical national average (assumed)"
                # ---- areas actually planted in the 2021 crop year ----
                if cid == "paddy":
                    row = pd_[(pd_.season == s) & (pd_.year == 2021)]
                    area = NET_SHARE * float(row.harvested_ha.iloc[0]) if len(row) and pd.notna(row.harvested_ha.iloc[0]) else 0.0
                    y21 = float(row.yield_t_ha.iloc[0]) if len(row) and pd.notna(row.yield_t_ha.iloc[0]) else base
                else:
                    row = hd[(hd.season == s) & (hd.year == 2021) & (hd.crop == cid)]
                    area = float(row.area_ha.sum())
                    rel = wb[did][cid][s]["y2021"]["ratio_rain"]
                    sup21 = rel + (1 - rel) * GAP_COVER["tank"][s]
                    y21 = crop["refYield"] * max(0.1, 1 - crop["ky"] * (1 - sup21))
                cs["district_area_ha"] = round(area)
                cs["planned_area_ha"] = round(area)  # neutral until farmers register plans
                cs["yield2021"] = round(y21, 2)
                area_tot += area
                prod_tot += area * y21
                cs.update({"water_mm": r["need_mm"], "etc_mm": r["etc_mm"], "irrig_mm": r["irrig_mm"], "supply": supply, "supplyRainRange": [lo, hi],
                           "y2021": r["y2021"]})
                if s == "yala":
                    yala_ratios.append(med)
                reasons, suit = [], "pass"
                if med < 0.8:
                    suit = "warn"
                    reasons.append(f"Rain alone meets about {round(med * 100)} % of this crop's water need in {SEASON[s]} in a normal year "
                                   f"({round(lo * 100)} % in a dry year); it needs about {r['irrig_mm']} mm of irrigation.")
                if supply["tank"] < 0.5:
                    suit = "fail"
                    reasons.append("Even with tank water the supply is under half of the requirement.")
                t_season = sum(c["tmax"][m] for m in ([9, 10, 11, 0, 1, 2] if s == "maha" else [3, 4, 5, 6, 7, 8])) / 6
                if cid not in ("paddy", "chilli") and t_season > 33:
                    reasons.append(f"Mean daily maximum is near {t_season:.1f} Â°C; heat at flowering can cut pod or grain set.")
                if cid == "bigonion" and c["seasonRain"][s] > 900:
                    suit = "warn" if suit == "pass" else suit
                    reasons.append("Heavy seasonal rain raises bulb-rot risk; needs well-drained land.")
                if pack["soil"]["ph"] < 5.6 and (crop["family"] == "legume" or cid == "bigonion"):
                    suit = "warn" if suit == "pass" else suit
                    reasons.append(f"Soil pH {pack['soil']['ph']} is on the acid side for this crop; check with a soil test.")
                cs["suit"], cs["reasons"] = suit, reasons or ["Temperature, season length, water supply and soil pH are all inside this crop's limits."]
            y = prod_tot / area_tot if area_tot else (pc["maha"]["yield"][1])
            if cid == "paddy":
                sv = ym["sensitivity"].get(did, {})
                rain = sum(v["rainPer10Pct"] for v in sv.values()) / max(1, len(sv)) / 10
                temp = sum(v["tempPerC"] for v in sv.values()) / max(1, len(sv))
                sens = {"rainPerPct": round(rain, 3), "tempPerC": round(temp, 2), "fertPerPct": 0.4, "source": "rain and temperature from the yield model; fertilizer assumed"}
            else:
                sens = {"rainPerPct": round(0.8 * (1 - (wb[did][cid]["maha"]["ratio_rain"][1] + wb[did][cid]["yala"]["ratio_rain"][1]) / 2) + 0.1, 3),
                        "tempPerC": -3.0, "fertPerPct": 0.1 if crop["family"] == "legume" else 0.4, "source": "assumed"}
            nat_crops[cid] = {"area_ha": round(area_tot), "yield": [round(y * 0.85, 2), round(y, 2), round(y * 1.13, 2)], "production_t": round(prod_tot), "sens": sens}
        # typical rotation in the district: Maha paddy; Yala paddy if at least half the Maha paddy land is cropped again
        pm, py = pack["crops"]["paddy"]["maha"]["district_area_ha"], pack["crops"]["paddy"]["yala"]["district_area_ha"]
        pack["typicalRotation"] = {"maha": "paddy", "yala": "paddy" if pm and py / pm >= 0.5 else "fallow"}
        path.write_text(json.dumps(pack), encoding="utf-8")

        total = c["seasonRain"]["maha"] + c["seasonRain"]["yala"]
        total21 = c["seasonRain2021"]["maha"] + c["seasonRain2021"]["yala"]
        d.update({"population": pop.get(did, d["population"]), "registered_pct": None, "crops": nat_crops,
                  "climate": {"rain_maha_mm": c["seasonRain"]["maha"], "rain_yala_mm": c["seasonRain"]["yala"], "rain_anom_pct": round((total21 / total - 1) * 100),
                              "heat_days": c["heatDays"], "onset_shift_days": c["onset"]["shiftDays"], "water_stress": round(1 - sum(yala_ratios) / len(yala_ratios), 2)}})
    (WEB / "national.json").write_text(json.dumps(national), encoding="utf-8")

    # harvest outlook board: Sri Lanka rows from this system; other countries stay labelled placeholders
    outlook = json.loads((WEB / "outlook.json").read_text(encoding="utf-8"))
    people = sum(d["population"] for d in national["districts"])
    for row in outlook["rows"]:
        if row["iso3"] != "LKA":
            continue
        cid = row["crop"]
        prod = sum(d["crops"][cid]["production_t"] for d in national["districts"])
        row.update({"production_t": round(prod), "balance_t": round(prod - people * crops[cid]["perCapKg"] / 1000), "sample": False, "fromModel": True,
                    "confidence": "medium (DCS 2021 data)" if cid == "paddy" else "low (typical yields)"})
    outlook["meta"] = {**meta, "assumptions": ASSUMPTIONS + ["Rows for countries other than Sri Lanka are placeholders that show the layout."]}
    (WEB / "outlook.json").write_text(json.dumps(outlook), encoding="utf-8")
    tot = {cid: sum(d["crops"][cid]["production_t"] for d in national["districts"]) for cid in crops}
    # market room: extra national area (ha) before the price falls 15 % (constant elasticity: Q/Q0 = 0.85 ** e)
    for cid, crop in crops.items():
        area = sum(d["crops"][cid]["area_ha"] for d in national["districts"])
        crop["marketRoomHa"] = round(area * (0.85 ** crop["elasticity"] - 1))
        crop["nationalArea2021Ha"] = round(area)
    (WEB / "crops.json").write_text(json.dumps(cj), encoding="utf-8")
    print("market room before a 15 % price fall (ha):", {k: c["marketRoomHa"] for k, c in crops.items()})
    print("packs and national.json rebuilt; soil for", len(soil), "districts; 2021 production (t):", {k: round(v) for k, v in tot.items()})


if __name__ == "__main__":
    main()
