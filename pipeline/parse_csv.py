"""Parse the CSV files supplied in pdf/csv/ (converted from DCS and HARTI publications).

Uses only what the models need:
  Highland_Crops_*.csv                                  -> data/processed/highland_area.csv   (district, season, year, crop, area_ha)
  HARTI_2021_W35_Table16_Farmgate_Producer_Prices.csv   -> data/processed/prices_2021.json    (Rs/kg at the farm gate)
  HARTI_2021_W35_Table04_Wholesale_Subsidiary_Food_Price.csv  (big onion has no farmgate quote that week)
  Mid_Year_Population_2025.csv                          -> data/processed/population.json
Usage:  python pipeline/parse_csv.py
"""
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "pdf/csv"
OUT = ROOT / "data/processed"
CROPS = {"Maize_Ha": "maize", "Green_Gram_Ha": "greengram", "Cowpea_Ha": "cowpea", "Big_Onion_Ha": "bigonion", "Chillies_Green_Ha": "chilli"}
FIX = {"moneragala": "monaragala", "mullaitivu": "mullaitivu", "killinochchi": "kilinochchi"}
# Big onion: farmgate is assumed to be 80 % of the wholesale price (no farmgate quote that week).
FARMGATE_SHARE_OF_WHOLESALE = 0.8


def did(name):
    s = re.sub(r"[^a-z]+", "-", str(name).strip().lower()).strip("-")
    return FIX.get(s, s)


def highland():
    known = {p.stem for p in (ROOT / "data/raw/power").glob("*.csv")}
    rows = []
    for f in sorted(SRC.glob("Highland_Crops_*.csv")):
        m = re.search(r"(\d{4})(?:_(\d{4}))?_(Maha|Yala)", f.stem)
        season = m.group(3).lower()
        year = int(m.group(2) or m.group(1))  # Maha 2020/2021 -> 2021 (harvest year)
        df = pd.read_csv(f)
        for _, r in df.iterrows():
            d = did(r["District"])
            if d not in known:
                continue
            for col, crop in CROPS.items():
                v = pd.to_numeric(r.get(col), errors="coerce")
                rows.append({"district": d, "season": season, "year": year, "crop": crop, "area_ha": 0.0 if pd.isna(v) else float(v)})
    out = pd.DataFrame(rows)
    out.to_csv(OUT / "highland_area.csv", index=False)
    print("highland_area.csv:", len(out), "rows;", out.groupby(["season", "year"]).area_ha.sum().round(0).to_dict())


def prices():
    fg = pd.read_csv(SRC / "HARTI_2021_W35_Table16_Farmgate_Producer_Prices.csv")
    fg["Average_Price"] = pd.to_numeric(fg["Average_Price"], errors="coerce")
    fg = fg.dropna(subset=["Average_Price"])
    pick = lambda pat: fg[fg.Commodity.str.contains(pat, case=False, regex=True)]
    out = {}
    for crop, pat in {"paddy": r"short grain|long grain \(white\)|paddy", "maize": r"^maize", "greengram": r"green gram", "cowpea": r"cowpea", "chilli": r"green chill"}.items():
        g = pick(pat)
        if len(g):
            out[crop] = {"rs_per_kg": round(float(g.Average_Price.mean()), 1), "range": [float(g.Range_Min.min()), float(g.Range_Max.max())],
                         "n_markets": int(len(g)), "source": "HARTI farmgate prices, week 35 (27 Aug - 2 Sep 2021)"}
    ws = pd.read_csv(SRC / "HARTI_2021_W35_Table04_Wholesale_Subsidiary_Food_Price.csv")
    bo = pd.concat([ws.Big_Onion_Min, ws.Big_Onion_Max]).dropna() / 50  # Rs per 50 kg bag -> Rs/kg
    out["bigonion"] = {"rs_per_kg": round(float(bo.mean()) * FARMGATE_SHARE_OF_WHOLESALE, 1), "range": [round(float(bo.min()), 1), round(float(bo.max()), 1)],
                       "n_markets": int(len(bo) // 2), "source": f"HARTI wholesale big onion, week 35 2021, x {FARMGATE_SHARE_OF_WHOLESALE} (assumed farmgate share)"}
    missing = sorted((set(CROPS.values()) | {"paddy"}) - set(out))
    if missing:
        print("no price found for:", missing)
    (OUT / "prices_2021.json").write_text(json.dumps(out, indent=1))
    print("prices_2021.json:", {k: v["rs_per_kg"] for k, v in out.items()})


def population():
    df = pd.read_csv(SRC / "Mid_Year_Population_2025.csv")
    pop = {did(r.District): int(r.Total_Thousands * 1000) for r in df.itertuples() if did(r.District) != "sri-lanka"}
    (OUT / "population.json").write_text(json.dumps({"year": 2025, "source": "DCS mid-year population 2025", "districts": pop}))
    print("population.json:", len(pop), "districts, total", sum(pop.values()))


if __name__ == "__main__":
    highland()
    prices()
    population()
