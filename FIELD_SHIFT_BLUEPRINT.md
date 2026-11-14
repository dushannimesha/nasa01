# Field Shift — Technical Blueprint
*NASA Space Apps 2026 · "Field Shift: Adapting Farms with NASA Data" · Focus region: Sri Lanka (demo district: Anuradhapura, dry zone)*

---

## 0. One-line pitch
**A farm-to-nation crop-rotation advisor:** a farmer gets data-backed rotation choices and growth-stage guidance for *their* field; the government sees what the whole country is planting, what it will produce, what fertilizer it needs, and where the surpluses and shortages will be, **before the season starts**.

## 0.1 The idea most teams will miss: the "everyone plants onion" problem
If an app tells every farmer "plant the most profitable crop", they all plant it, prices crash, and the advice turns out wrong (the cobweb effect: Ezekiel, 1938). Sri Lanka sees this every year with big onion, potato and vegetables.
**Our fix:** the farmer app and the government dashboard share one aggregate. Planned area feeds a supply forecast, the supply forecast feeds an expected price, and the expected price feeds back into the farmer's market score. No other team will close this loop.

---

## 1. Users & modes

| User | Mode | Input | Output |
|---|---|---|---|
| Farmer | **A. Plan**: what should I plant? | Location (map pin), field size, current/last crops, water source (rain / tank / well), budget, labour, priorities (income · water saving · soil health · low risk) | Top 3+ rotation strategies (including their existing rotation), each with *why*, evidence, benefits, risks, information gaps, and expected yield/profit **ranges** |
| Farmer | **B. Already planted**: how do I optimize? | Crop + sowing date | Current growth stage, water deficit, 14-day weather risk, actions (irrigate / fertilize / protect), yield outlook |
| Farmer | **C. My idea**: I want to grow X | Crop X + planned date | Feasibility, how-to calendar, simulated outcome versus the recommended options, risks |
| Government | **D. National dashboard** | Aggregated farmer plans + satellite crop maps | Production forecast by district, fertilizer demand (N/P/K), surplus/deficit versus consumption → store / export / import plan, nutrition coverage, price-pressure warnings |
| Government | **E. What-if simulator** | "Shift 20% of Yala paddy to green gram", "fertilizer supply −30%", "rainfall −25%" | Production, price, fertilizer, nutrition and soil-health impact over the next 3–6 seasons |

The tool **supports, not replaces**, farmer and extension-officer judgment. Every output shows confidence and the points that need local checking.

---

## 2. System architecture

```
 ┌──────────────── DATA LAYER (ingest + harmonize) ────────────────┐
 │ NASA: POWER · GPM IMERG · SMAP · MODIS/VIIRS · HLS(Landsat+S2) │
 │       ECOSTRESS · SRTM · GLDAS · GRACE-FO · NEX-GDDP-CMIP6      │
 │ Partner: Sentinel-1/2 · ERA5 · SEAS5 seasonal forecast           │
 │ Soil/Crop: SoilGrids · FAO GAEZ v4 · ECOCROP · ESA WorldCereal    │
 │ Sri Lanka: DCS paddy/OFC stats · HARTI prices · DoA fert. recs    │
 │            Food balance (FAOSTAT) · population (DCS)              │
 └────────────┬───────────────────────────────────────────────────┘
              ▼  common grid: 0.05° (≈5 km) + dekadal (10-day) time step
 ┌──────────────── FEATURE STORE (per pixel / district / season) ──┐
 │ climate · water balance · stress indices · soil · terrain · NDVI│
 └────────────┬───────────────────────────────────────────────────┘
              ▼
 ┌──────────────── MODEL LAYER ────────────────────────────────────┐
 │ M1 Suitability filter (GAEZ/ECOCROP + season window)            │
 │ M2 Crop-water simulation (FAO-56 / AquaCrop-OSPy)               │
 │ M3 ML yield model (LightGBM + conformal intervals + SHAP)       │
 │ M4 Soil-state model (N balance, SOC/ICBM, RUSLE erosion, pests) │
 │ M5 Climate scenarios (SEAS5 next season, CMIP6 2030-2050)       │
 │ M6 Market model (supply → price elasticity, aggregate feedback) │
 │ M7 Multi-criteria ranker (farmer weights, TOPSIS)               │
 └────────────┬───────────────────────────────────────────────────┘
              ▼
 ┌──── API (FastAPI) ────┐      ┌──── Frontends ────────────────────┐
 │ /plan /monitor /whatif│ ───► │ Farmer PWA (Sinhala/Tamil/English)│
 │ /gov/aggregate        │      │ Gov dashboard (map + scenarios)   │
 └───────────────────────┘      └───────────────────────────────────┘
```

---

## 3. Datasets (what, why, how to get it)

### 3.1 NASA (core, must be visible in the demo)
| Dataset | Variables | Resolution | Role | Access |
|---|---|---|---|---|
| **NASA POWER** (Agroclimatology) | T2M max/min, precipitation, RH, wind, solar radiation | 0.5° daily, 1981→ | Long climate baseline, ET₀ (Penman-Monteith), GDD, heat-stress days | REST API, no login |
| **GPM IMERG Final/Late** | Precipitation | 0.1° daily, 2000→ | Season-onset shift, dry spells, extreme rain, erosivity (RUSLE R) | Earthdata (GES DISC), OPeNDAP |
| **SMAP L4 / L3** | Surface + root-zone soil moisture | 9 km, 2015→ | Current water status, soil-moisture anomaly | Earthdata (NSIDC), AppEEARS |
| **MODIS MOD13Q1 / VIIRS VNP13** | NDVI/EVI | 250–500 m, 16-day | Crop calendar, bare-field periods, stress, district yield features | AppEEARS |
| **HLS (Landsat + Sentinel-2)** | Surface reflectance → NDVI | 30 m, ~3-day | Field-level monitoring (Mode B) | Earthdata (LP DAAC) |
| **ECOSTRESS** | LST, ET, Evaporative Stress Index | 70 m, irregular | Heat/water-stress hotspots | AppEEARS |
| **SRTM** | Elevation | 30 m | Slope → RUSLE LS factor, runoff, tank cascade context | Earthdata / OpenTopography |
| **GLDAS Noah** | Soil moisture, ET, runoff | 0.25°, 3-hourly, 2000→ | Gap-free continuous water-balance series | Earthdata (GES DISC) |
| **GRACE-FO** | Terrestrial water storage anomaly | ~1° monthly | Long-term groundwater trend (well-dependent farms) | PO.DAAC |
| **NEX-GDDP-CMIP6** | Downscaled future T/P (SSP2-4.5, SSP5-8.5) | 0.25° daily to 2100 | "Future" rotation suitability 2030–2050 | NASA NCCS / AWS open data |

### 3.2 Partner / global
- **ERA5 / ERA5-Land** (ECMWF): gap-filling and validation for POWER/IMERG.
- **C3S SEAS5 seasonal forecast** (Copernicus CDS): rainfall/temperature anomaly for the *next* 1–6 months, used to drive next-season advice.
- **Open-Meteo forecast API** (free, no key): 14-day weather for Mode B actions.
- **Sentinel-1 SAR**: sees through clouds; paddy mapping in Maha season.
- **Sentinel-2 / ESA WorldCereal / Dynamic World**: crop and land-cover maps for the government layer.
- **ISRIC SoilGrids 250 m**: pH, SOC, N, texture, CEC, bulk density, giving available water capacity.
- **FAO GAEZ v4**: crop suitability and attainable yield. **FAO ECOCROP**: crop temperature/rain/pH limits.
- **FAOSTAT**: food balance sheets (per-capita consumption), national production and trade.

### 3.3 Sri Lanka ground truth (this is what makes it "locally valid")
- **Dept. of Census & Statistics (DCS)**: paddy extent, yield and production by **district × season (Yala/Maha)**, plus OFC (maize, green gram, cowpea, big onion, chilli…) statistics. **These are the labels for the ML yield model.**
- **HARTI** (Hector Kobbekaduwa Agrarian Research & Training Institute): weekly wholesale/retail prices, used by the market model.
- **Dept. of Agriculture (DoA)**: crop recommendations, fertilizer recommendations (N-P-K kg/ha by crop and agro-ecological zone), variety maturity days, crop calendars.
- **Agro-ecological zone map (DL1–DL5, IL, WL…)**.
- **Dept. of Meteorology**: station data (validation) and the seasonal outlook.
- **Mahaweli / Irrigation Dept.**: tank water issue schedules (optional).

> The challenge's US resources (SSURGO, CDL, NASS, AMS, PRISM, OpenET) are the US equivalents of the list above. Mention in the deck that the pipeline is **region-agnostic**: swap SoilGrids→SSURGO, DCS→NASS, HARTI→AMS and it runs in Iowa.

---

## 4. Data processing (the "data clear" steps)
1. **Define the spatio-temporal frame:** 25 districts plus a 0.05° grid; dekadal steps (36 per year); seasons Maha (Oct–Mar) and Yala (Apr–Sep).
2. **Ingest** via APIs. Cache everything as Parquet/NetCDF (the demo must run offline).
3. **Clean:** QA masks (MODIS VI quality, cloud masks); remove outliers (>4σ); fill short gaps by linear interpolation and long gaps from ERA5/GLDAS. Smooth NDVI with Savitzky–Golay.
4. **Harmonize resolution** (as the challenge suggests): aggregate fine data (HLS, ECOSTRESS, SoilGrids) by mean or zonal statistics, and bilinearly resample coarse data (POWER, GLDAS) to the 0.05° grid. Districts use area-weighted zonal means over a **cropland mask** (WorldCereal), not over forest.
5. **Bias-correct** IMERG and POWER against Met Dept stations with quantile mapping, where stations are available.
6. **Derive features** for each season and growth stage:
   - Rain total, rain-day count, longest dry spell, onset date (first 10-day window ≥ 50 mm followed by no 10-day dry spell), extreme-rain days (>50 mm).
   - ET₀ (FAO-56 Penman-Monteith from POWER) and the water deficit P − ETc.
   - GDD, heat-stress days (Tmax > 35 °C at flowering), night temperature.
   - SMAP anomaly (z-score against 2015→ climatology); ESI from ECOSTRESS.
   - NDVI peak, timing, integral, and bare-soil fraction between seasons.
   - Soil: available water capacity (AWC), pH, SOC, texture class. Terrain: slope, RUSLE LS.
7. **Version** each processed dataset with its date and source; this goes on the "Evidence" panel in the UI.

---

## 5. Models

### M1. Suitability filter (rules, explainable)
For each candidate crop *c* and season *s*, keep *c* only if:
- The temperature range fits ECOCROP/GAEZ limits.
- Season length ≥ crop maturity days.
- Expected water supply (rain + irrigation source) ≥ 70 % of the crop's water requirement (ETc).
- Soil pH and drainage are within the crop's tolerance.

The output gives each crop a pass, warn or fail, **with the reason** (this becomes the "why" text).

### M2. Crop-water simulation (process-based)
- Use **FAO-56** dual crop coefficient (Kc per stage × ET₀) and a daily soil water balance (AWC from SoilGrids) to estimate water stress Ks per stage.
- Optional upgrade: **AquaCrop-OSPy** (FAO's AquaCrop in Python), which simulates biomass and yield under water stress and needs weather, soil, crop and management inputs.
- Runs on **historical years** (2001–2025 IMERG/POWER), giving a *distribution* of outcomes rather than a single number. It also runs on **SEAS5** (next season) and **CMIP6** (future) forcings.

### M3. ML yield model (the "specifically trained model")
- **Target:** district × season yield (t/ha) from DCS, about 25 districts × 2 seasons × 20 years ≈ 1,000 rows for paddy, with fewer rows for OFCs.
- **Features:** the §4 features aggregated over the cropping season, plus the M2 water-stress index, previous-season crop, and fertilizer-availability flag (2021–22 ban years).
- **Model:** **LightGBM** (gradient boosting). Baselines: linear regression and random forest. Report all three and keep the best; judges like seeing the comparison, and the challenge asks for it.
- **Validation:** **leave-one-year-out** cross-validation, so the model never trains on the year it predicts. Report RMSE and R².
- **Uncertainty:** **conformal prediction** (MAPIE library) gives 80 % intervals ("3.1–4.2 t/ha").
- **Explainability:** **SHAP** values give the "why" in plain words ("late rain onset −0.4 t/ha").
- **Field scaling:** field yield = district prediction × field NDVI-ratio adjustment (field peak NDVI ÷ district peak NDVI), clipped to 0.7–1.3. Show it as an estimate, not a fact.
- Optional stretch: MODIS histogram + CNN/LSTM (You et al., 2017).

### M4. Soil-state model (rotation memory over seasons)
State per field: `{N_soil, SOC, pest_pressure[family], erosion_loss, moisture_carryover}`. Each season updates it:
- **Nitrogen:** N_next = N + fertilizer + fixation (legumes 20–80 kg/ha) + residue N − crop removal − losses (≈ 30 % of surplus).
- **Soil organic carbon:** **ICBM two-pool model** (Andrén & Kätterer, 1997) with residue inputs by crop.
- **Erosion:** **RUSLE**, A = R·K·LS·C·P. R comes from IMERG intensity, K from SoilGrids texture/SOC, LS from SRTM, and C from crop cover by stage (with a bare-fallow penalty).
- **Pests/disease:** pressure rises if the same crop family repeats and decays when it is broken (rules from DoA and the literature).
- Output: a **5-year (10-season) trajectory** per rotation, shown on the timeline visual.

### M5. Climate scenarios
- **Next season:** SEAS5 tercile probabilities (below/normal/above rain), which reweight historical years in M2 (analog-year method).
- **Long-term:** NEX-GDDP-CMIP6 2030–2050 versus 1995–2014 deltas, showing which crops get riskier ("onset already shifted N days since 2001; projected +M days by 2040").
- **What-if sliders** (rain ±%, temperature +°C) apply deltas to the historical forcing and rerun M2/M3.

### M6. Market & aggregate model (closes the cobweb loop)
- Baseline price P₀ and volatility come from HARTI history (seasonal median and interquartile range).
- Expected supply S = Σ (planned area from app users scaled to district total + satellite-mapped area) × predicted yield (M3).
- Price response: %ΔP ≈ (1/ε) · %ΔS, with demand elasticity ε from the literature (about −0.3 to −0.8 for vegetables; state this as an assumption).
- Farmer profit = yield × expected P − cost (DoA cost-of-cultivation tables), reported as a range.
- The government layer computes production − consumption (population × FAOSTAT per-capita consumption) → **surplus (store/export) or deficit (import)**. It also computes fertilizer demand = Σ area × DoA N-P-K rate, and nutrition = production × FAO food composition (kcal, protein, micronutrients) ÷ population needs.

### M7. Ranking / decision (farmer priorities)
1. **Generate candidates:** existing rotation + all M1-passing two-season sequences (Maha → Yala), plus one cover/green-manure option. That's roughly 20–60 candidates.
2. **Score each** on 6 criteria, normalized 0–1:
   - Expected profit (M2+M3+M6)
   - Downside risk (10th-percentile profit)
   - Water use (ETc ÷ available water)
   - Soil-health Δ (M4: N, SOC)
   - Erosion (M4)
   - Pest-cycle break (M4)
3. **Weights** come from the farmer's priority sliders.
4. **Rank with TOPSIS.** Show the **top 3 + the existing rotation** (the challenge asks for ≥3 including the existing one).
5. **Explain each strategy** with an auto-generated card: Why suggested (top SHAP and rule reasons) · Evidence (datasets + numbers) · Benefits · Risks · Information gaps (low data density, coarse resolution) · "Check with your Agricultural Instructor (KVK officer)".

---

## 6. The answering algorithm (end-to-end)

```
function PLAN(farmer):
    loc  = farmer.location;  F = load_features(loc)          # §4, cached
    hist = climate_history(loc, 2001..2025)                   # POWER + IMERG
    fc   = seasonal_forecast(loc)                             # SEAS5 terciles
    soil = soilgrids(loc) ⊕ farmer_overrides                  # farmer-known soil wins
    C    = [c for c in CROPS if suitability(c, F, soil, farmer.water).pass]
    R    = rotations(C, seasons=[next_Maha, next_Yala]) ∪ {farmer.current_rotation}
    for r in R:
        sims   = [simulate_water(r, year, soil) for year in analog_years(hist, fc)]
        yld    = ml_yield(r, F, sims) → (median, p10, p90, shap)
        soil_t = soil_state(r, soil, seasons=10)
        price  = market(r.crops, aggregate_plans(district))
        r.scores = criteria(yld, price, sims, soil_t)
    ranked = TOPSIS(R, weights = farmer.priorities)
    return top3(ranked) + existing, each with explain_card(r)

function MONITOR(farmer, crop, sow_date):                     # Mode B
    stage = growth_stage(crop, GDD since sow_date)            # FAO-56 stages
    wb    = water_balance(today, soil, IMERG+SMAP)            # deficit mm
    ndvi  = field_ndvi(HLS) vs expected_curve(crop, stage)    # anomaly
    wx    = forecast_14d(loc)
    actions = rules(stage, wb, ndvi, wx):                     # DoA guidance
        irrigate X mm if deficit > RAW · fertilizer split N at stage ·
        heat/flood alert · pest risk if humid & warm
    yield_outlook = ml_yield(updated features)  → range
    return calendar + actions + outlook

function MY_IDEA(farmer, crop_x):                             # Mode C
    run PLAN scoring for rotation containing crop_x
    return feasibility, how-to calendar, outcome vs top-3, risks

function GOV(district|nation, scenario):
    area   = Σ farmer_plans ⊕ satellite_crop_map(S1/S2)
    prod   = area × ml_yield ; fert = area × DoA_rates
    gap    = prod − demand ; nutrition = prod × composition / needs
    price  = market(prod) ; soil_trend = Σ soil_state
    apply scenario deltas → re-run → compare vs baseline
```

---

## 7. Growth-stage guidance (Mode B detail)
- **Stages:** FAO-56 initial, development, mid, late; plus crop-specific stages (paddy: tillering, panicle initiation, flowering, grain fill).
- **Triggers:**
  - Root-zone depletion > readily available water (RAW) → irrigate.
  - Fertilizer split due (DoA schedule, e.g. paddy urea top-dressings at fixed days after sowing).
  - Tmax > 35 °C forecast at flowering → heat alert.
  - > 100 mm/3 days forecast → drainage and erosion alert.
  - NDVI more than 15 % below the expected curve → "check field": possible pest, nutrient or water problem.
- **Delivery:** a simple calendar card per week, in Sinhala/Tamil, with an icon for each action. Optional SMS text.

---

## 8. Evaluation & honesty (Validity score)
- Yield model: leave-one-year-out RMSE/R² versus a "last year's yield" baseline.
- IMERG versus Met Dept stations: correlation and bias table.
- M2 check against DoA crop water requirements.
- A **"Data confidence" badge** on every output, based on resolution, record length and model error.
- **Limitations slide:** POWER is ~50 km, SMAP starts in 2015, district yields are not field yields, price elasticities are assumed, the model is not a substitute for extension officers.

---

## 9. 48-hour build plan

| Time | Data/ML (2 people) | Backend | Frontend/Design | Story |
|---|---|---|---|---|
| H0–4 | Pull and cache POWER + IMERG + MODIS NDVI + SoilGrids for Anuradhapura; DCS yields | FastAPI skeleton, data contract | Wireframes: farmer flow + gov dashboard | Pitch, farmer persona, find a farmer to interview |
| H4–14 | Features §4; M1 rules; M2 FAO-56 water balance | /plan endpoint with M1+M2 | Map pin, priority sliders, rotation cards | Script |
| H14–26 | M3 LightGBM + LOYO CV + SHAP + conformal | M4 soil state, M7 TOPSIS | 5-year soil/water timeline chart | Visual assets |
| H26–36 | M5 SEAS5/CMIP6 deltas; M6 market | /monitor, /gov | Mode B calendar; gov map + scenario sliders | Record demo |
| H36–44 | Validation tables | Offline cache, bug fixes | Sinhala/Tamil labels, polish | Edit video, ≤7 slides |
| H44–48 | **Freeze. Submit early.** | | | |

**MVP (must ship):** Mode A for 1 district, 6 crops (paddy, maize, green gram, cowpea, big onion, chilli), M1+M2+M3+M4+M7, 3 rotations + existing, with explanation cards.
**Stretch:** Mode B, gov dashboard, M5 CMIP6, M6 market loop, Sentinel-1 paddy map.

---

## 10. Tech stack
- **Python:** `requests`, `pandas`, `xarray`, `rioxarray`, `earthaccess`, `pyproj`, `scikit-learn`, `lightgbm`, `shap`, `mapie`, `aquacrop` (AquaCrop-OSPy), `pyet` (ET₀), `fastapi`, `uvicorn`.
- **Frontend:** React/Vite or plain HTML + **Leaflet** (map) + **Chart.js/ECharts**; i18n JSON for Sinhala/Tamil. NASA **GIBS/Worldview** tiles as map overlays.
- **Storage:** Parquet + a small SQLite store for farmer plans (gov aggregate).

---

## 11. Key references
- Allen, R.G. et al. (1998). *Crop Evapotranspiration*. FAO Irrigation & Drainage Paper 56.
- Steduto, P. et al. (2009). AquaCrop: the FAO crop model. *Agronomy Journal* 101(3).
- Kelly, T.D. & Foster, T. (2021). AquaCrop-OSPy. *Agricultural Water Management* 254.
- You, J. et al. (2017). Deep Gaussian Process for crop yield prediction based on remote sensing data. *AAAI*.
- van Klompenburg, T. et al. (2020). Crop yield prediction using machine learning: a systematic review. *Computers and Electronics in Agriculture* 177.
- Lundberg, S. & Lee, S.-I. (2017). A unified approach to interpreting model predictions (SHAP). *NeurIPS*.
- Angelopoulos, A. & Bates, S. (2021). A gentle introduction to conformal prediction. *arXiv:2107.07511*.
- Renard, K.G. et al. (1997). *RUSLE*. USDA Agriculture Handbook 703.
- Andrén, O. & Kätterer, T. (1997). ICBM: the introductory carbon balance model. *Ecological Applications* 7(4).
- Huffman, G.J. et al. GPM IMERG Algorithm Theoretical Basis Document (NASA).
- Thrasher, B. et al. (2022). NASA Global Daily Downscaled Projections, CMIP6. *Scientific Data* 9.
- Hwang, C.L. & Yoon, K. (1981). *Multiple Attribute Decision Making* (TOPSIS). Springer.
- Ezekiel, M. (1938). The cobweb theorem. *Quarterly Journal of Economics* 52(2).
- Sri Lanka DoA crop and fertilizer recommendations; DCS paddy statistics; HARTI price bulletins.

*(Verify each citation's details before putting them on slides.)*

---

## 12. Judging-criteria map
- **Impact:** farmer + nation loop; fertilizer planning (lesson of the 2021 fertilizer crisis); food security.
- **Creativity:** cobweb-aware recommendations; "the season moved" onset analysis; 5-year soil timeline.
- **Validity:** 10 NASA datasets, LOYO-validated model, conformal uncertainty, limitations slide.
- **Relevance:** hits every objective (≥3 rotations including existing, why/evidence/benefit/gap/risk, priorities, support-not-replace).
- **Presentation:** a farmer's story first, data second; Sinhala/Tamil UI; one real farmer voice.
