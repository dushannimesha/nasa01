"""M3: paddy yield model (district x season), trained on seasons up to Yala 2020, tested on 2021.

Target   DCS average yield, t/ha (data/processed/dcs_paddy.csv)
Features NASA POWER season climate (data/processed/season_features.csv), the FAO-56 water-balance stress for
         paddy (data/processed/water_balance.csv), the district's yield history (last year, 3-year mean),
         share of rain-fed land, season, year, district.
Models   baselines ("same as last year", "3-year mean"), ridge regression, random forest, LightGBM.
Checks   expanding-window validation on 2011-2020 (each year predicted only from earlier years),
         then the held-out test on 2021 (Maha 2020/21 and Yala 2021). (NASA POWER is only downloaded to the end of
         2021, so the fertilizer-ban season Maha 2021/22 is not tested.)
Outputs  data/processed/yield_model.json  metrics, 2021 predictions with 80 % intervals and top reasons,
                                          per-district rain and temperature sensitivities
         models/artifacts/paddy_lgbm.txt  the trained LightGBM model
Usage:   python models/yield_ml.py
"""
import json
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data/processed"
ART = ROOT / "models/artifacts"
CLIMATE = ["rain_mm", "rain_days", "dry_spell_days", "extreme_rain_days", "et0_mm", "water_balance_mm", "tmax_mean", "tmin_mean", "heat_days", "solar_mean"]
WATER = ["wb_ratio", "wb_irrig_mm"]
HISTORY = ["lag1", "mean3", "rainfed_share"]
NUM = CLIMATE + WATER + HISTORY + ["year", "is_maha"]
LABEL = {"rain_mm": "season rain", "rain_days": "rainy days", "dry_spell_days": "longest dry spell", "extreme_rain_days": "very heavy rain days",
         "et0_mm": "evaporation demand", "water_balance_mm": "rain minus evaporation", "tmax_mean": "daytime temperature", "tmin_mean": "night temperature",
         "heat_days": "days above 35 Â°C", "solar_mean": "sunshine", "wb_ratio": "crop water supply from rain", "wb_irrig_mm": "irrigation need",
         "lag1": "last year's yield", "mean3": "3-year average yield", "rainfed_share": "share of rain-fed fields", "year": "long-term trend",
         "is_maha": "season", "district": "district"}
TEST_YEAR, CV_YEARS = 2021, range(2011, 2021)


def build():
    y = pd.read_csv(P / "dcs_paddy.csv")
    y["rainfed_share"] = (y.harvested_ha_rainfed.fillna(0) / y.harvested_ha).clip(0, 1)
    y = y[["district", "season", "year", "yield_t_ha", "harvested_ha", "rainfed_share"]].dropna(subset=["yield_t_ha"])
    y = y.sort_values("year")
    g = y.groupby(["district", "season"]).yield_t_ha
    y["lag1"] = g.shift(1)
    y["mean3"] = g.transform(lambda s: s.shift(1).rolling(3, min_periods=2).mean())
    f = pd.read_csv(P / "season_features.csv")
    wb = pd.read_csv(P / "water_balance.csv")
    wb = wb[wb.crop == "paddy"].rename(columns={"ratio_rain": "wb_ratio", "irrig_mm": "wb_irrig_mm"})[["district", "season", "year", "wb_ratio", "wb_irrig_mm"]]
    d = y.merge(f, on=["district", "season", "year"]).merge(wb, on=["district", "season", "year"])
    d["is_maha"] = (d.season == "maha").astype(int)
    d = d.dropna(subset=["lag1", "mean3"]).reset_index(drop=True)
    # a few seasons lack the area split; use that district-season's median share
    d["rainfed_share"] = d.rainfed_share.fillna(d.groupby(["district", "season"]).rainfed_share.transform("median")).fillna(0)
    missing = d[NUM].isna().sum()
    if missing.any():
        print("filled missing values:", missing[missing > 0].to_dict())
        d[NUM] = d[NUM].fillna(d[NUM].median())
    return d


def models():
    pre = ColumnTransformer([("num", StandardScaler(), NUM), ("dist", OneHotEncoder(handle_unknown="ignore"), ["district"])])
    return {
        "Ridge regression": lambda: make_pipeline(pre, Ridge(alpha=3.0)),
        "Random forest": lambda: make_pipeline(ColumnTransformer([("num", "passthrough", NUM), ("dist", OneHotEncoder(handle_unknown="ignore"), ["district"])]),
                                               RandomForestRegressor(n_estimators=400, min_samples_leaf=3, random_state=0, n_jobs=-1)),
        "LightGBM": lambda: LGBM(),
    }


class LGBM:
    params = dict(n_estimators=500, learning_rate=0.03, num_leaves=15, min_child_samples=15, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=0, verbose=-1)

    def _x(self, df):
        x = df[NUM + ["district"]].copy()
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


def main():
    d = build()
    X = lambda q: d[q][NUM + ["district"]]
    builders = models()
    # 1) expanding-window validation: predict each year 2011-2020 from all earlier years only
    cv = {name: [] for name in builders}
    cv_rows = []
    for yr in CV_YEARS:
        tr, te = d.year < yr, d.year == yr
        for name, mk in builders.items():
            m = mk().fit(X(tr), d[tr].yield_t_ha)
            p = m.predict(X(te))
            cv[name].append(pd.DataFrame({"actual": d[te].yield_t_ha.values, "pred": p}))
    base_cv = d[d.year.isin(CV_YEARS)]
    results = {"Same as last year": {"cv_rmse": rmse(base_cv.yield_t_ha, base_cv.lag1)}, "3-year average": {"cv_rmse": rmse(base_cv.yield_t_ha, base_cv.mean3)}}
    for name, parts in cv.items():
        c = pd.concat(parts)
        results[name] = {"cv_rmse": rmse(c.actual, c.pred), "cv_r2": float(r2_score(c.actual, c.pred))}
    best = min(builders, key=lambda n: results[n]["cv_rmse"])
    resid = pd.concat(cv[best]).eval("actual - pred")
    q_lo, q_hi = float(resid.quantile(0.10)), float(resid.quantile(0.90))  # split-conformal style 80 % band

    # 2) final models trained on everything up to 2020; tested on 2021 and on Maha 2021/22 (fertilizer ban)
    train = d.year <= 2020
    fitted = {name: mk().fit(X(train), d[train].yield_t_ha) for name, mk in builders.items()}
    out_rows = []
    for label, mask in {"maha": (d.year == TEST_YEAR) & (d.season == "maha"), "yala": (d.year == TEST_YEAR) & (d.season == "yala")}.items():
        t = d[mask]
        for name in list(builders) + ["Same as last year", "3-year average"]:
            p = fitted[name].predict(X(mask)) if name in fitted else (t.lag1 if name == "Same as last year" else t.mean3)
            results[name][f"test_{label}_rmse"] = rmse(t.yield_t_ha, p)
            results[name][f"test_{label}_r2"] = float(r2_score(t.yield_t_ha, p))
    model = fitted[best]

    # 3) 2021 predictions with intervals and plain-language reasons (LightGBM SHAP contributions)
    t21 = d[d.year == TEST_YEAR].copy()
    t21["pred"] = model.predict(t21[NUM + ["district"]])
    cols = NUM + ["district"]
    if best == "Ridge regression":
        # linear model: contribution of each feature = coefficient x (value - training mean) / scale, i.e. effect versus an average season
        pre, ridge = model.steps[0][1], model.steps[1][1]
        sc = pre.named_transformers_["num"]
        coef = ridge.coef_
        num_c = (t21[NUM].to_numpy() - sc.mean_) / sc.scale_ * coef[: len(NUM)]
        oh = pre.named_transformers_["dist"]
        dist_coef = dict(zip(oh.categories_[0], coef[len(NUM):]))
        mean_dist = float(np.mean(list(dist_coef.values())))
        contrib = np.column_stack([num_c, [dist_coef.get(x, mean_dist) - mean_dist for x in t21.district]])
    else:
        contrib = fitted["LightGBM"].contrib(t21[cols])
    preds = []
    for i, r in enumerate(t21.itertuples()):
        c = sorted(((cols[k], contrib[i][k]) for k in range(len(cols))), key=lambda kv: -abs(kv[1]))
        reasons = [{"feature": LABEL[f], "effect_t_ha": round(float(v), 2)} for f, v in c if f not in ("year",)][:3]
        preds.append({"district": r.district, "season": r.season, "year": int(r.year), "actual": round(r.yield_t_ha, 2), "predicted": round(float(r.pred), 2),
                      "interval": [round(float(r.pred + q_lo), 2), round(float(r.pred + q_hi), 2)], "reasons": reasons})

    # 4) sensitivities for the what-if sliders: % yield change per +10 % rain and per +1 Â°C, from the model itself
    sens = {}
    base = d[d.year == 2020].copy()
    for (dist, season), row in base.groupby(["district", "season"]):
        x0 = row[NUM + ["district"]]
        p0 = float(model.predict(x0)[0])
        wet = x0.copy(); wet["rain_mm"] *= 1.1; wet["water_balance_mm"] += 0.1 * row.rain_mm.values; wet["wb_ratio"] = (wet.wb_ratio * 1.05).clip(upper=1)
        hot = x0.copy(); hot["tmax_mean"] += 1; hot["tmin_mean"] += 1; hot["et0_mm"] *= 1.04
        sens.setdefault(dist, {})[season] = {"rainPer10Pct": round((float(model.predict(wet)[0]) / p0 - 1) * 100, 2), "tempPerC": round((float(model.predict(hot)[0]) / p0 - 1) * 100, 2)}

    imp = pd.Series(fitted["LightGBM"].m.booster_.feature_importance("gain"), index=cols)
    ART.mkdir(parents=True, exist_ok=True)
    fitted["LightGBM"].m.booster_.save_model(str(ART / "paddy_lgbm.txt"))
    import joblib
    joblib.dump({"model": model, "name": best, "features": NUM + ["district"], "q10": q_lo, "q90": q_hi}, ART / "paddy_best.joblib")
    out = {
        "target": "DCS paddy average yield (t/ha), district x season", "trainedOn": "seasons 1983-2020", "rows": int(train.sum()), "bestModel": best,
        "interval": {"level": 0.8, "residual_q10": round(q_lo, 3), "residual_q90": round(q_hi, 3)},
        "results": {k: {m: round(v, 3) for m, v in r.items()} for k, r in results.items()},
        "importance": {LABEL[k]: round(float(v / imp.sum()), 3) for k, v in imp.sort_values(ascending=False).items()},
        "predictions": preds, "sensitivity": sens,
    }
    (P / "yield_model.json").write_text(json.dumps(out, indent=1))
    print(f"training rows {int(train.sum())}; best by 2011-2020 validation: {best}; 80 % band {q_lo:+.2f} / {q_hi:+.2f} t/ha")
    print(pd.DataFrame(results).T.round(3).to_string())
    print("top drivers:", ", ".join(f"{k} {v:.0%}" for k, v in list(out["importance"].items())[:6]))


if __name__ == "__main__":
    main()
