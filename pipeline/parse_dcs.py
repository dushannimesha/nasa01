"""Parse DCS paddy statistics (district x season, 1979-2025) into one tidy table.

Inputs (downloaded from statistics.gov.lk -> Agriculture -> Paddy Statistics):
  data/raw/dcs/Average_Yeild-{Maha,Yala}_Season-1979-2025.xlsx       kg per net hectare
  data/raw/dcs/Harvested_Extent-{Maha,Yala}_Seasons-1979-2025.xlsx   hectares
Each sheet: one row per district; every season is a block of 4 columns (Major, Minor, Rainfed, Total).

Output: data/processed/dcs_paddy.csv
  district, year, season, yield_t_ha (+ major/minor/rainfed), harvested_ha (+ by scheme)
Year convention matches the climate features: Maha 2020/2021 -> year 2021 (harvest year), Yala 2021 -> 2021.
Usage:  python pipeline/parse_dcs.py
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/dcs"
NAMES = {  # DCS spelling -> district id used everywhere else
    "MULATIVU": "mullaitivu", "MULLAITIVU": "mullaitivu", "MULLATIVU": "mullaitivu", "KILLINOCHCHI": "kilinochchi", "KILINOCHCHI": "kilinochchi",
    "NUWARAELIYA": "nuwara-eliya", "NUWARA ELIYA": "nuwara-eliya", "MONERAGALA": "monaragala", "MONARAGALA": "monaragala",
    "AMPARAI": "ampara", "TRINCOMALIE": "trincomalee", "VAVUNIA": "vavuniya",
}
SCHEMES = ["major", "minor", "rainfed", "total"]


def did(name):
    n = re.sub(r"\s+", " ", str(name).strip().upper())
    return NAMES.get(n, n.lower().replace(" ", "-"))


def parse(path, value):
    df = pd.read_excel(path, header=None)
    head = df.iloc[2]
    starts = [(c, str(v).strip().replace(".0", "")) for c, v in head.items() if pd.notna(v) and re.search(r"\d{4}", str(v))]
    rows = []
    for r in range(4, len(df)):
        name = df.iat[r, 1]
        if not isinstance(name, str) or not name.strip() or "SRI LANKA" in name.upper() or "TOTAL" in name.upper():
            continue
        for c, label in starts:
            years = re.findall(r"\d{4}", label)
            year = int(years[-1])  # Maha 1978/1979 -> 1979 ; Yala 1979 -> 1979
            rec = {"district": did(name), "year": year}
            for k, s in enumerate(SCHEMES):
                v = pd.to_numeric(df.iat[r, c + k], errors="coerce")
                rec[f"{value}_{s}"] = v
            rows.append(rec)
    return pd.DataFrame(rows)


def main():
    known = {p.stem for p in (ROOT / "data/raw/power").glob("*.csv")}
    out = []
    for season, cap in (("maha", "Maha"), ("yala", "Yala")):
        y = parse(RAW / f"Average_Yeild-{cap}_Season-1979-2025.xlsx", "yield")
        a = parse(RAW / f"Harvested_Extent-{cap}_Seasons-1979-2025.xlsx", "harvested")
        m = y.merge(a, on=["district", "year"], how="outer")
        m["season"] = season
        out.append(m)
    df = pd.concat(out, ignore_index=True)
    # Udawalawe and Mahaweli 'H' were reported separately in early years; later they are inside their districts.
    unknown = sorted(set(df.district) - known)
    if unknown:
        print("rows not matched to a district (dropped):", unknown)
    df = df[df.district.isin(known)].copy()
    for s in SCHEMES:
        df[f"yield_t_ha_{s}"] = (df.pop(f"yield_{s}") / 1000).round(3)
        df[f"harvested_ha_{s}"] = df.pop(f"harvested_{s}")
    df = df.rename(columns={"yield_t_ha_total": "yield_t_ha", "harvested_ha_total": "harvested_ha"})
    df = df.sort_values(["district", "season", "year"])
    df.to_csv(ROOT / "data/processed/dcs_paddy.csv", index=False)
    ok = df.dropna(subset=["yield_t_ha"])
    print(f"dcs_paddy.csv: {len(df)} rows, {len(ok)} with a yield; years {ok.year.min()}-{ok.year.max()}; districts {ok.district.nunique()}")
    nat = ok.assign(prod=ok.yield_t_ha * ok.harvested_ha).groupby(["season", "year"]).agg(prod=("prod", "sum"), area=("harvested_ha", "sum"))
    nat["yield"] = (nat["prod"] / nat["area"]).round(2)
    print("national yield t/ha, recent seasons:")
    print(nat["yield"].unstack(0).loc[2015:].to_string())


if __name__ == "__main__":
    main()
