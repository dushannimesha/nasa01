"""Writes model output into the web app's data files (web/public/data).

Current state: climate and crop-water numbers are real (NASA POWER + water-balance model).
Yields, areas, prices, costs and the 2021 test are still sample values until the DCS / HARTI / DoA
files are parsed, so meta.sample stays true and meta.real lists what is already real.

Run after:  python pipeline/features.py  and  python models/water_balance.py
Usage:      python packs/build_packs.py
"""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web/public/data"
PROC = ROOT / "data/processed"
# Share of the rain shortfall that each water source is assumed to cover. No irrigation records are used yet.
GAP_COVER = {"tank": {"maha": 0.9, "yala": 0.6}, "well": {"maha": 0.5, "yala": 0.5}}
SEASON = {"maha": "Maha", "yala": "Yala"}
REAL = ["climate (NASA POWER 1981-2021)", "crop water requirement and rain-fed water supply (FAO-56 water balance)"]
ASSUMPTIONS = [
    "Tank or canal water is assumed to cover 90 % of the rain shortfall in Maha and 60 % in Yala; an agro-well 50 %.",
    "Sowing on 25 October (Maha) and 25 April (Yala); root-zone available water 120 mm.",
    "NASA POWER rain is on a grid of about 50 km, so neighbouring districts can share one value and wet-zone rain is underestimated.",
]


def main():
    climate = json.loads((PROC / "climate_summary.json").read_text())["districts"]
    wb = json.loads((PROC / "water_balance_summary.json").read_text())
    crops = {c["id"]: c for c in json.loads((WEB / "crops.json").read_text(encoding="utf-8"))["crops"]}
    national = json.loads((WEB / "national.json").read_text(encoding="utf-8"))
    stamp = {"real": REAL, "assumptions": ASSUMPTIONS, "dataAsOf": date.today().isoformat()}
    national["meta"].update(stamp)

    for d in national["districts"]:
        did, c = d["id"], climate[d["id"]]
        path = WEB / "packs" / f"{did}.json"
        pack = json.loads(path.read_text(encoding="utf-8"))
        pack["meta"].update(stamp)
        onset = pack["climate"]["onset"] = c["onset"]
        pack["climate"].update({"rain": c["rain"], "et0": c["et0"], "tmax": c["tmax"], "seasonRain": c["seasonRain"], "heatDays": c["heatDays"],
                                "seasonRain2021": c["seasonRain2021"], "rainAnom2021Pct": c["rainAnom2021Pct"]})
        yala_ratios = []
        for cid, crop in crops.items():
            for s in ("maha", "yala"):
                r = wb[did][cid][s]
                lo, med, hi = r["ratio_rain"]
                supply = {"rain": med, **{src: round(med + (1 - med) * GAP_COVER[src][s], 3) for src in ("tank", "well")}}
                cs = pack["crops"][cid][s]
                cs.update({"water_mm": r["need_mm"], "etc_mm": r["etc_mm"], "irrig_mm": r["irrig_mm"], "supply": supply, "supplyRainRange": [lo, hi]})
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
                    reasons.append(f"Mean daily maximum is near {t_season:.1f} °C; heat at flowering can cut pod or grain set.")
                if cid == "bigonion" and c["seasonRain"][s] > 900:
                    suit = "warn" if suit == "pass" else suit
                    reasons.append("Heavy seasonal rain raises bulb-rot risk; needs well-drained land.")
                if pack["soil"]["ph"] < 5.6 and (crop["family"] == "legume" or cid == "bigonion"):
                    suit = "warn" if suit == "pass" else suit
                    reasons.append(f"Soil pH {pack['soil']['ph']} is on the acid side for this crop; check with a soil test.")
                cs["suit"], cs["reasons"] = suit, reasons or ["Temperature, season length, water supply and soil pH are all inside this crop's limits."]
        path.write_text(json.dumps(pack), encoding="utf-8")

        total = c["seasonRain"]["maha"] + c["seasonRain"]["yala"]
        total21 = c["seasonRain2021"]["maha"] + c["seasonRain2021"]["yala"]
        d["climate"] = {"rain_maha_mm": c["seasonRain"]["maha"], "rain_yala_mm": c["seasonRain"]["yala"], "rain_anom_pct": round((total21 / total - 1) * 100),
                        "heat_days": c["heatDays"], "onset_shift_days": onset["shiftDays"], "water_stress": round(1 - sum(yala_ratios) / len(yala_ratios), 2)}
    (WEB / "national.json").write_text(json.dumps(national), encoding="utf-8")
    print("updated national.json and", len(national["districts"]), "district packs; real:", "; ".join(REAL))


if __name__ == "__main__":
    main()
