"""M3: paddy yield model (district x season), trained on seasons up to Yala 2020, tested on 2021.

Target   DCS average yield, t/ha (data/processed/dcs_paddy.csv)
Inputs   yield history (last year, 3-year mean, share of rain-fed land, trend, season, district);
         NASA POWER season climate + FAO-56 water balance (season_features.csv, water_balance.csv);
         GPM IMERG season rain and MODIS early-season NDVI anomaly, when those files have been downloaded.
Dataset comparison ("what each dataset adds")
         The same three models (ridge, random forest, LightGBM) are trained on 2002-2020 with
         1) history only  2) + NASA POWER  3) + GPM IMERG  4) + MODIS NDVI.
         Each is scored by expanding-window validation on 2011-2020 (every year predicted only from earlier years)
         and on the held-out 2021 seasons. The combination with the lowest 2011-2020 error is kept (2021 is never
         used to choose). Note: MODIS NDVI covers the first 3 months of a season, so set 4 is a mid-season forecast.
Outputs  data/processed/yield_model.json   comparison, metrics, 2021 predictions (80 % interval, top reasons),
                                           per-district rain and temperature sensitivities
         models/artifacts/paddy_best.joblib  the chosen model (used by the API)
Usage:   python models/yield_ml.py
"""
import json
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
ART = ROOT / "models/artifacts"
HISTORY = ["lag1", "mean3", "rainfed_share", "year", "is_maha"]
POWER = ["rain_mm", "rain_days", "dry_spell_days", "extreme_rain_days", "et0_mm", "water_balance_mm", "tmax_mean", "tmin_mean", "heat_days", "solar_mean",
         "wb_ratio", "wb_irrig_mm"]
IMERG = ["imerg_rain_mm"]
NDVI = ["ndvi_early"]
LABEL = {"rain_mm": "season rain (NASA POWER)", "rain_days": "rainy days", "dry_spell_days": "longest dry spell", "extreme_rain_days": "very heavy rain days",
         "et0_mm": "evaporation demand", "water_balance_mm": "rain minus evaporation", "tmax_mean": "daytime temperature", "tmin_mean": "night temperature",
         "heat_days": "days above 35 °C", "solar_mean": "sunshine", "wb_ratio": "crop water supply from rain", "wb_irrig_mm": "irrigation need",
         "lag1": "last year's yield", "mean3": "3-year average yield", "rainfed_share": "share of rain-fed fields", "year": "long-term trend",
         "is_maha": "season", "district": "district", "imerg_rain_mm": "season rain (GPM IMERG)", "ndvi_early": "early-season greenness (MODIS NDVI)"}
TEST_YEAR, CV_YEARS, START = 2021, range(2011, 2021), 2002


def build():
    y = pd.read_csv(P / "dcs_paddy.csv")
    y["rainfed_share"] = (y.harvested_ha_rainfed.fillna(0) / y.harvested_ha).clip(0, 1)
    y = y[["district", "season", "year", "yield_t_ha", "harvested_ha", "rainfed_share"]].dropna(subset=["yield_t_ha"]).sort_values("year")
    g = y.groupby(["district", "season"]).yield_t_ha
    y["lag1"] = g.shift(1)
    y["mean3"] = g.transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    f = pd.read_csv(P / "season_features.csv")
    wb = pd.read_csv(P / "water_balance.csv")
    wb = wb[wb.crop == "paddy"].rename(columns={"ratio_rain": "wb_ratio", "irrig_mm": "wb_irrig_mm"})[["district", "season", "year", "wb_ratio", "wb_irrig_mm"]]
    d = y.merge(f, on=["district", "season", "year"]).merge(wb, on=["district", "season", "year"])
    d["is_maha"] = (d.season == "maha").astype(int)
    d = d.dropna(subset=["lag1", "mean3"]).reset_index(drop=True)
    d["rainfed_share"] = d.rainfed_share.fillna(d.groupby(["district", "season"]).rainfed_share.transform("median")).fillna(0)
    base = HISTORY + POWER
    d[base] = d[base].fillna(d[base].median())
    for c in IMERG + NDVI:
        if c in d:  # a few gaps (cloudy months, missing files): use that district-season's median
            d[c] = d[c].fillna(d.groupby(["district", "season"])[c].transform("median"))
    return d


def models(num):
    onehot = lambda: OneHotEncoder(handle_unknown="ignore")
    return {
        "Ridge regression": lambda: make_pipeline(ColumnTransformer([("num", StandardScaler(), num), ("dist", onehot(), ["district"])]), Ridge(alpha=3.0)),
        "Random forest": lambda: make_pipeline(ColumnTransformer([("num", "passthrough", num), ("dist", onehot(), ["district"])]),
                                               RandomForestRegressor(n_estimators=300, min_samples_leaf=3, random_state=0, n_jobs=-1)),
        "LightGBM": lambda: LGBM(num),
    }


class LGBM:
    params = dict(n_estimators=400, learning_rate=0.03, num_leaves=15, min_child_samples=15, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                  reg_lambda=1.0, random_state=0, verbose=-1)

    def __init__(self, num):
        self.num = num

    def _x(self, df):
        x = df[self.num + ["district"]].copy()
        x["district"] = pd.Categorical(x.district, categories=self.cats)
        return x

    def fit(self, df, y):
        self.cats = sorted(df.district.unique())
        self.m = lgb.LGBMRegressor(**self.params).fit(self._x(df), y)
        return self

    def predict(self, df):
        return self.m.predict(self._x(df))

    def contrib(self, df):
        return self.m.predict(self._x(df), pred_contrib=True)


def rmse(a, b):
    return float(np.sqrt(mean_squared_error(a, b)))


def evaluate(d, num):
    """CV 2011-2020 and 2021 test for the three models on one feature set."""
    cols = num + ["district"]
    res, cv_parts = {}, {}
    for name, mk in models(num).items():
        parts = []
        for yr in CV_YEARS:
            tr, te = d.year < yr, d.year == yr
            parts.append(pd.DataFrame({"actual": d[te].yield_t_ha.values, "pred": mk().fit(d[tr][cols], d[tr].yield_t_ha).predict(d[te][cols])}))
        c = pd.concat(parts)
        cv_parts[name] = c
        res[name] = {"cv_rmse": rmse(c.actual, c.pred), "cv_r2": float(r2_score(c.actual, c.pred))}
        train = d.year <= 2020
        assert d[train].year.max() <= 2020  # 2021 never enters training
        m = mk().fit(d[train][cols], d[train].yield_t_ha)
        for s in ("maha", "yala"):
            t = d[(d.year == TEST_YEAR) & (d.season == s)]
            p = m.predict(t[cols])
            res[name][f"test_{s}_rmse"], res[name][f"test_{s}_r2"] = rmse(t.yield_t_ha, p), float(r2_score(t.yield_t_ha, p))
    return res, cv_parts


def what_if(x, rain_pct, temp_c):
    """Same weather change applied to every rain and temperature input the model uses (also used by the API)."""
    x = x.copy()
    k = 1 + rain_pct / 100
    if "rain_mm" in x:
        x["water_balance_mm"] = x.water_balance_mm + (k - 1) * x.rain_mm
        x["rain_mm"] = x.rain_mm * k
        x["wb_ratio"] = np.clip(x.wb_ratio * (1 + rain_pct / 200), 0, 1)
        x["tmax_mean"] = x.tmax_mean + temp_c
        x["tmin_mean"] = x.tmin_mean + temp_c
        x["et0_mm"] = x.et0_mm * (1 + 0.04 * temp_c)
    if "imerg_rain_mm" in x:
        x["imerg_rain_mm"] = x.imerg_rain_mm * k
    return x


def main():
    d_all = build()
    d = d_all[d_all.year >= START].reset_index(drop=True)
    sets = [("Yield history only", HISTORY, []), ("+ NASA POWER climate & water balance", HISTORY + POWER, ["NASA POWER"])]
    if "imerg_rain_mm" in d and d.imerg_rain_mm.notna().all():
        sets.append(("+ GPM IMERG rain", sets[-1][1] + IMERG, sets[-1][2] + ["GPM IMERG"]))
    if "ndvi_early" in d and d.ndvi_early.notna().all():
        sets.append(("+ MODIS NDVI (mid-season)", sets[-1][1] + NDVI, sets[-1][2] + ["MODIS NDVI"]))

    ablation, by_set = [], {}
    for label, num, ds in sets:
        res, cvp = evaluate(d, num)
        best_m = min(res, key=lambda n: res[n]["cv_rmse"])
        by_set[label] = (num, res, cvp, best_m)
        ablation.append({"set": label, "datasets": ds, "features": len(num), "model": best_m, **{k: round(v, 3) for k, v in res[best_m].items()}})
        print(f"{label:40s} best {best_m:17s} cv {res[best_m]['cv_rmse']:.3f}  test maha {res[best_m]['test_maha_rmse']:.3f}  yala {res[best_m]['test_yala_rmse']:.3f}", flush=True)
    chosen = min(ablation, key=lambda a: a["cv_rmse"])
    num, results, cvp, best = by_set[chosen["set"]]
    cols = num + ["district"]
    resid = cvp[best].eval("actual - pred")
    q_lo, q_hi = float(resid.quantile(0.10)), float(resid.quantile(0.90))  # split-conformal style 80 % band
    cvb = d[d.year.isin(CV_YEARS)]
    results["Same as last year"] = {"cv_rmse": rmse(cvb.yield_t_ha, cvb.lag1)}
    results["3-year average"] = {"cv_rmse": rmse(cvb.yield_t_ha, cvb.mean3)}
    for s in ("maha", "yala"):
        t = d[(d.year == TEST_YEAR) & (d.season == s)]
        for k, col in (("Same as last year", "lag1"), ("3-year average", "mean3")):
            results[k][f"test_{s}_rmse"], results[k][f"test_{s}_r2"] = rmse(t.yield_t_ha, t[col]), float(r2_score(t.yield_t_ha, t[col]))

    train = d.year <= 2020
    model = models(num)[best]().fit(d[train][cols], d[train].yield_t_ha)
    t21 = d[d.year == TEST_YEAR].copy()
    t21["pred"] = model.predict(t21[cols])
    if best == "Ridge regression":  # contribution = coefficient x standardised deviation from an average season
        pre, ridge = model.steps[0][1], model.steps[1][1]
        sc, coef = pre.named_transformers_["num"], ridge.coef_
        num_c = (t21[num].to_numpy() - sc.mean_) / sc.scale_ * coef[: len(num)]
        dist_coef = dict(zip(pre.named_transformers_["dist"].categories_[0], coef[len(num):]))
        mean_dist = float(np.mean(list(dist_coef.values())))
        contrib = np.column_stack([num_c, [dist_coef.get(x, mean_dist) - mean_dist for x in t21.district]])
    elif best == "LightGBM":
        contrib = model.contrib(t21[cols])
    else:
        contrib = models(num)["LightGBM"]().fit(d[train][cols], d[train].yield_t_ha).contrib(t21[cols])
    preds = []
    for i, r in enumerate(t21.itertuples()):
        c = sorted(((cols[k], contrib[i][k]) for k in range(len(cols))), key=lambda kv: -abs(kv[1]))
        preds.append({"district": r.district, "season": r.season, "year": int(r.year), "actual": round(r.yield_t_ha, 2), "predicted": round(float(r.pred), 2),
                      "interval": [round(float(r.pred + q_lo), 2), round(float(r.pred + q_hi), 2)],
                      "reasons": [{"feature": LABEL[f], "effect_t_ha": round(float(v), 2)} for f, v in c if f != "year"][:3]})

    sens = {}
    for (dist, season), row in d[d.year == 2020].groupby(["district", "season"]):
        x0 = row[cols]
        p0 = float(model.predict(x0)[0])
        sens.setdefault(dist, {})[season] = {"rainPer10Pct": round((float(model.predict(what_if(x0, 10, 0))[0]) / p0 - 1) * 100, 2),
                                             "tempPerC": round((float(model.predict(what_if(x0, 0, 1))[0]) / p0 - 1) * 100, 2)}

    imp_model = models(num)["LightGBM"]().fit(d[train][cols], d[train].yield_t_ha)
    imp = pd.Series(imp_model.m.booster_.feature_importance("gain"), index=cols)
    ART.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "name": best, "features": cols, "q10": q_lo, "q90": q_hi, "set": chosen["set"]}, ART / "paddy_best.joblib")
    out = {
        "target": "DCS paddy average yield (t/ha), district x season", "trainedOn": f"seasons {START}-2020", "rows": int(train.sum()),
        "bestModel": best, "featureSet": chosen["set"], "datasetsUsed": chosen["datasets"], "ablation": ablation,
        "interval": {"level": 0.8, "residual_q10": round(q_lo, 3), "residual_q90": round(q_hi, 3)},
        "results": {k: {m: round(v, 3) for m, v in r.items()} for k, r in results.items()},
        "importance": {LABEL[k]: round(float(v / imp.sum()), 3) for k, v in imp.sort_values(ascending=False).items()},
        "predictions": preds, "sensitivity": sens,
    }
    (P / "yield_model.json").write_text(json.dumps(out, indent=1))
    print(f"\nchosen: {chosen['set']} with {best}; training rows {int(train.sum())}; 80 % band {q_lo:+.2f} / {q_hi:+.2f} t/ha")
    print("top drivers:", ", ".join(f"{k} {v:.0%}" for k, v in list(out["importance"].items())[:6]))


if __name__ == "__main__":
    main()
