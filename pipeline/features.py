"""Climate features from NASA POWER daily data (blueprint section 4).

Reads   data/raw/power/<district>.csv
Writes  data/processed/daily/<district>.csv      daily series with reference evapotranspiration (ET0)
        data/processed/season_features.csv       one row per district x crop year x season
        data/processed/climate_summary.json      monthly normals, rain-onset trend, 2021 anomalies

Seasons: Maha Y = 1 Oct (Y-1) to 31 Mar Y, labelled with the harvest year Y. Yala Y = 1 Apr to 30 Sep Y.
Usage:  python pipeline/features.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/power"
OUT = ROOT / "data/processed"
# Approximate elevation (m) for the pressure term in ET0; lowland districts default to 50 m.
ELEV = {"nuwara-eliya": 1500, "badulla": 700, "kandy": 500, "matale": 400, "kegalle": 200, "ratnapura": 150, "monaragala": 150}
NORMAL = (1991, 2020)


def et0_penman_monteith(df, lat_deg, elev):
    """FAO-56 Penman-Monteith reference evapotranspiration, mm/day (Allen et al. 1998, eq. 6)."""
    tmax, tmin, rh, u2, rs = (df[c].to_numpy(float) for c in ["tmax", "tmin", "rh", "wind", "solar"])
    doy = df["date"].dt.dayofyear.to_numpy()
    tmean = (tmax + tmin) / 2
    svp = lambda t: 0.6108 * np.exp(17.27 * t / (t + 237.3))
    es = (svp(tmax) + svp(tmin)) / 2
    ea = es * rh / 100
    delta = 4098 * svp(tmean) / (tmean + 237.3) ** 2
    gamma = 0.000665 * 101.3 * ((293 - 0.0065 * elev) / 293) ** 5.26
    lat = np.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    decl = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    ws = np.arccos(-np.tan(lat) * np.tan(decl))
    ra = 24 * 60 / np.pi * 0.0820 * dr * (ws * np.sin(lat) * np.sin(decl) + np.cos(lat) * np.cos(decl) * np.sin(ws))
    rso = (0.75 + 2e-5 * elev) * ra
    rns = 0.77 * rs
    rnl = 4.903e-9 * ((tmax + 273.16) ** 4 + (tmin + 273.16) ** 4) / 2 * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * np.minimum(rs / rso, 1) - 0.35)
    return np.maximum(0, (0.408 * delta * (rns - rnl) + gamma * 900 / (tmean + 273) * u2 * (es - ea)) / (delta + gamma * (1 + 0.34 * u2)))


def load(district):
    df = pd.read_csv(RAW / f"{district['id']}.csv", parse_dates=["date"])
    # POWER has no solar data before 1984: fill gaps with that calendar day's long-term mean
    for col in ["tmax", "tmin", "rain", "rh", "wind", "solar"]:
        if df[col].isna().any():
            df[col] = df[col].fillna(df.groupby(df["date"].dt.dayofyear)[col].transform("mean"))
    df["et0"] = et0_penman_monteith(df, district["lat"], ELEV.get(district["id"], 50)).round(2)
    return df


def longest_dry_spell(rain):
    best = run = 0
    for r in rain:
        run = run + 1 if r < 1 else 0
        best = max(best, run)
    return best


def maha_onset(rain_from_sep1):
    """Day (counted from 1 Sep) when 10-day rain first reaches 50 mm and the next 20 days bring at least 20 mm."""
    r = np.asarray(rain_from_sep1)
    for i in range(0, len(r) - 30):
        if r[i:i + 10].sum() >= 50 and r[i + 10:i + 30].sum() >= 20:
            return i
    return np.nan


def season_rows(did, df):
    rows = []
    s = df.set_index("date")
    for year in range(1982, 2022):
        for season, a, b in [("maha", f"{year - 1}-10-01", f"{year}-03-31"), ("yala", f"{year}-04-01", f"{year}-09-30")]:
            w = s.loc[a:b]
            if len(w) < 170:
                continue
            row = {
                "district": did, "year": year, "season": season,
                "rain_mm": w.rain.sum(), "rain_days": int((w.rain >= 1).sum()), "dry_spell_days": longest_dry_spell(w.rain),
                "extreme_rain_days": int((w.rain > 50).sum()), "et0_mm": w.et0.sum(), "water_balance_mm": w.rain.sum() - w.et0.sum(),
                "tmax_mean": w.tmax.mean(), "tmin_mean": w.tmin.mean(), "heat_days": int((w.tmax > 35).sum()),
                "gdd10": np.maximum(0, (w.tmax + w.tmin) / 2 - 10).sum(), "solar_mean": w.solar.mean(),
            }
            if season == "maha":
                row["onset_day"] = maha_onset(s.loc[f"{year - 1}-09-01":f"{year}-01-31"].rain)
            rows.append(row)
    return rows


SEASON_MONTHS = {"maha": [(-1, 10), (-1, 11), (-1, 12), (0, 1), (0, 2), (0, 3)], "yala": [(0, m) for m in range(4, 10)]}


def add_satellite(df):
    """Adds satellite features when their files exist (each is optional):
    imerg_rain_mm  GPM IMERG season rain (district mean, 0.1 deg)
    ndvi_early     MODIS NDVI anomaly in the first 3 months of the season (vs the district-season 2001-2020 mean)
    smap_anom      SMAP root-zone soil-moisture anomaly over the season (vs 2015-2020 mean), 2016 onwards only
    """
    def season_value(monthly, col, how, first_n=6):
        m = monthly.assign(y=pd.to_datetime(monthly.date).dt.year, mo=pd.to_datetime(monthly.date).dt.month).set_index(["district", "y", "mo"])[col]
        vals = []
        for r in df.itertuples():
            keys = [(r.district, r.year + dy, mo) for dy, mo in SEASON_MONTHS[r.season][:first_n]]
            got = [m.get(k) for k in keys]
            got = [g for g in got if g is not None and pd.notna(g)]
            vals.append((sum(got) if how == "sum" else sum(got) / len(got)) if len(got) == len(keys) else np.nan)
        return vals

    for name, path, col, how, n in (("imerg_rain_mm", "imerg_monthly.csv", "rain_mm", "sum", 6), ("ndvi_early", "ndvi_monthly.csv", "ndvi", "mean", 3),
                                   ("smap_anom", "smap_monthly.csv", "sm_rootzone", "mean", 6)):
        if not (OUT / path).exists():
            continue
        df[name] = season_value(pd.read_csv(OUT / path), col, how, n)
        if name != "imerg_rain_mm":  # anomaly against the district-season normal
            ref = df[df.year <= 2020].groupby(["district", "season"])[name].transform("mean")
            norm = df.assign(_r=ref).groupby(["district", "season"])._r.transform("max")
            df[name] = df[name] - norm
        print(f"added {name}: {df[name].notna().sum()} seasons", flush=True)
    return df


def main():
    (OUT / "daily").mkdir(parents=True, exist_ok=True)
    districts = [f["properties"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]]
    rows, summary = [], {}
    for d in districts:
        df = load(d)
        df.to_csv(OUT / "daily" / f"{d['id']}.csv", index=False)
        r = season_rows(d["id"], df)
        rows += r
        sf = pd.DataFrame(r)
        norm = df[(df.date.dt.year >= NORMAL[0]) & (df.date.dt.year <= NORMAL[1])]
        ym = norm.groupby([norm.date.dt.year, norm.date.dt.month])
        monthly = lambda col, how: getattr(ym[col], how)().groupby(level=1).mean()
        onset = sf[(sf.season == "maha") & sf.onset_day.notna() & (sf.year <= 2020)]
        slope = np.polyfit(onset.year, onset.onset_day, 1)[0] if len(onset) > 10 else 0.0
        base = sf[(sf.year >= NORMAL[0]) & (sf.year <= NORMAL[1])].groupby("season").mean(numeric_only=True)
        y21 = sf[sf.year == 2021].set_index("season")
        summary[d["id"]] = {
            "rain": monthly("rain", "sum").round(0).astype(int).tolist(),
            "et0": monthly("et0", "sum").round(0).astype(int).tolist(),
            "tmax": monthly("tmax", "mean").round(1).tolist(),
            "seasonRain": {s: int(round(base.loc[s, "rain_mm"])) for s in ["maha", "yala"]},
            "seasonRain2021": {s: int(round(y21.loc[s, "rain_mm"])) for s in ["maha", "yala"]},
            "rainAnom2021Pct": {s: round((y21.loc[s, "rain_mm"] / base.loc[s, "rain_mm"] - 1) * 100, 1) for s in ["maha", "yala"]},
            "heatDays": int(round(base["heat_days"].sum())),
            "heatDays2021": int(y21["heat_days"].sum()),
            # onset: day of year, counted from 1 Sep (day 244)
            "onset": {"years": onset.year.astype(int).tolist(), "doy": (onset.onset_day + 244).astype(int).tolist(), "shiftDays": round(float(slope) * (2020 - 1982), 1)},
        }
        print(f"{d['id']:14s} Maha {summary[d['id']]['seasonRain']['maha']:5d} mm  Yala {summary[d['id']]['seasonRain']['yala']:5d} mm  "
              f"onset shift {summary[d['id']]['onset']['shiftDays']:+5.1f} d  2021 anomaly Maha {summary[d['id']]['rainAnom2021Pct']['maha']:+.0f}% Yala {summary[d['id']]['rainAnom2021Pct']['yala']:+.0f}%")
    add_satellite(pd.DataFrame(rows)).round(4).to_csv(OUT / "season_features.csv", index=False)
    (OUT / "climate_summary.json").write_text(json.dumps({"source": "NASA POWER daily (AG community), one point per district", "normalPeriod": NORMAL, "districts": summary}))
    print(f"season_features.csv: {len(rows)} rows")


if __name__ == "__main__":
    main()
