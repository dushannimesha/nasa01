// 2021 test: what farmers actually did (DCS 2021) against what would have happened if part of the area had
// followed the app's advice. Uses the same ranking engine as the web app (src/lib/model.js).
//
// Rules
//  - Advice uses only pre-2021 information: climate normals 1991-2020, paddy yields 2018-2020, water-balance
//    normals. (Prices are the 2021 HARTI quotes: no earlier price series was supplied.)
//  - Advice is for a typical farm in each district: tank water, balanced priorities. A farmer switches only to a
//    rotation that earns at least as much as the current one; otherwise nothing changes.
//  - Adoption a (10/30/50 %): share a of Maha paddy moves to the advised Maha crop, share a of Yala paddy to the
//    advised Yala crop, and share a of land left bare in Yala gets the advised Yala crop.
//  - Market rule (the app's national plan): advice for a crop stops once planned national supply would move its
//    price by more than 15 % either way (5 % for rice, the staple). Districts are served in order of their income gain; a district can be
//    given a smaller share or its next-best rotation when the first choice no longer fits.
//  - Everything is valued under the ACTUAL 2021 weather (2021 water balance) and actual 2021 paddy yields, with
//    prices responding to national supply (assumed elasticities). A run without the market rule is kept to show
//    what happens when every adopter gets the same top advice.
// Output: public/data/backtest_2021.json      Usage: node scripts/run_backtest.mjs
import fs from "node:fs";
import { planRotations, byId, clamp } from "../src/lib/model.js";

const D = "public/data";
const { crops: cropList, meta } = JSON.parse(fs.readFileSync(`${D}/crops.json`, "utf8"));
const crops = byId(cropList);
const ids = cropList.map((c) => c.id);
const packs = fs.readdirSync(`${D}/packs`).map((f) => JSON.parse(fs.readFileSync(`${D}/packs/${f}`, "utf8")));
const ym = JSON.parse(fs.readFileSync("../data/processed/yield_model.json", "utf8"));
const WEIGHTS = { profit: 7, risk: 5, water: 5, soil: 5, erosion: 2, pest: 3 };
const S = ["maha", "yala"];
const BAND = 0.15;
const BAND_FOR = (c) => (c === "paddy" ? 0.05 : BAND); // rice is the staple: hold its price within 5 %
const r1 = (x) => Math.round(x * 10) / 10;

const actual = Object.fromEntries(packs.map((p) => [p.id, Object.fromEntries(S.map((s) => [s, Object.fromEntries(ids.map((c) => [c, p.crops[c][s].district_area_ha]))]))]));
const bare = (A) => Math.max(0, ids.reduce((t, c) => t + A.maha[c], 0) - ids.reduce((t, c) => t + A.yala[c], 0));

// ranked rotations a typical farmer in each district would accept (earn at least as much as the current rotation)
const options = Object.fromEntries(packs.map((p) => {
  const res = planRotations(p, cropList, p.typicalRotation, WEIGHTS, { waterSource: "tank", market: false });
  const ok = res.ranked.filter((r) => r !== res.existing && r.criteria.profit >= res.existing.criteria.profit);
  return [p.id, { list: ok.map((r) => r.rot), gain: ok.length ? ok[0].criteria.profit - res.existing.criteria.profit : 0, existing: res.existing.rot }];
}));

// move a share of one district's land to a rotation, starting from its actual 2021 areas
function adoptOne(id, rot, share) {
  const A0 = actual[id];
  const A = structuredClone(A0);
  if (rot.maha !== "paddy") { const m = share * A0.maha.paddy; A.maha.paddy -= m; A.maha[rot.maha] += m; }
  if (rot.yala !== "paddy") { const m = share * A0.yala.paddy; A.yala.paddy -= m; if (rot.yala !== "fallow") A.yala[rot.yala] += m; }
  if (rot.yala !== "fallow") A.yala[rot.yala] += share * bare(A0);
  return A;
}

function evaluate(areas) {
  const per = Object.fromEntries(ids.map((c) => [c, { area_ha: 0, production_t: 0 }]));
  let water = 0, fertN = 0, bareHa = 0;
  const dist = {};
  for (const p of packs) {
    const A = areas[p.id];
    let w = 0;
    for (const s of S) for (const c of ids) {
      const cs = p.crops[c][s];
      per[c].area_ha += A[s][c]; per[c].production_t += A[s][c] * cs.yield2021;
      w += A[s][c] * cs.y2021.irrig_mm * 10; // m3
      fertN += (A[s][c] * crops[c].n) / 1000;
    }
    water += w; bareHa += bare(A);
    dist[p.id] = { A, water: w };
  }
  return { per, water, fertN, bareHa, dist };
}
const base = evaluate(actual);
const mult = (ev, c) => clamp(Math.pow(Math.max(1e-6, ev.per[c].production_t / base.per[c].production_t), 1 / crops[c].elasticity), 0.25, 2.5);
function priced(ev) {
  const m = Object.fromEntries(ids.map((c) => [c, mult(ev, c)]));
  const distIncome = Object.fromEntries(packs.map((p) => {
    const A = ev.dist[p.id].A;
    return [p.id, S.reduce((t, s) => t + ids.reduce((u, c) => u + A[s][c] * p.crops[c][s].yield2021 * 1000 * crops[c].price * m[c] - A[s][c] * crops[c].cost, 0), 0)];
  }));
  return { pct: Object.fromEntries(ids.map((c) => [c, (m[c] - 1) * 100])), income: Object.values(distIncome).reduce((a, b) => a + b, 0), distIncome };
}
const inBand = (ev) => ids.every((c) => Math.abs(mult(ev, c) - 1) <= BAND_FOR(c) + 1e-9);

function scenario(a, marketRule) {
  const areas = structuredClone(actual);
  const chosen = {};
  const order = [...packs].sort((x, y) => options[y.id].gain - options[x.id].gain);
  for (const p of order) {
    const list = options[p.id].list;
    let done = false;
    for (const rot of marketRule ? list : list.slice(0, 1)) {
      for (const f of marketRule ? [1, 0.5, 0.25, 0.1] : [1]) {
        const trial = { ...areas, [p.id]: adoptOne(p.id, rot, a * f) };
        if (!marketRule || inBand(evaluate(trial))) { areas[p.id] = trial[p.id]; chosen[p.id] = { rot, share: a * f }; done = true; break; }
      }
      if (done) break;
    }
    if (!done) chosen[p.id] = { rot: options[p.id].existing, share: 0 };
  }
  const ev = evaluate(areas);
  return { ev, pr: priced(ev), chosen };
}

const summarize = (ev, pr, a) => ({
  adoptionPct: a,
  perCrop: Object.fromEntries(ids.map((c) => [c, { area_ha: Math.round(ev.per[c].area_ha), production_t: Math.round(ev.per[c].production_t), priceChangePct: r1(pr.pct[c]) }])),
  income_lkr_bn: r1(pr.income / 1e9), water_mcm: Math.round(ev.water / 1e6), fertN_t: Math.round(ev.fertN), bareFallow_ha: Math.round(ev.bareHa),
});
const basePr = priced(base);
const levels = [10, 30, 50];
const runs = Object.fromEntries(levels.map((a) => [a, scenario(a / 100, true)]));
const naive = Object.fromEntries(levels.map((a) => [a, scenario(a / 100, false)]));
const best = ym.bestModel, R = ym.results;
const out = {
  meta: { ...meta, sample: false, note: "Simulation. The 'with app' side is not an observation." },
  method: [
    `Paddy yield model (${best}) trained on district seasons 1983-2020 only; tested on Maha 2020/21 and Yala 2021 against DCS statistics.`,
    "Without the app: DCS 2021 areas and yields (paddy) and DCS 2021 areas with typical yields under 2021 weather (other crops), valued at 2021 HARTI farmgate prices.",
    "With the app: advice from pre-2021 climate, water balance and yields for a typical tank-irrigated farm. A farmer switches only if the new rotation earns at least as much. 10, 30 or 50 % of area follows the advice; valued under the actual 2021 weather.",
    `Market rule: the app stops advising a crop once planned national supply would move its price more than ${BAND * 100} % either way, or the rice price more than 5 % (food security). Prices respond to supply with assumed elasticities.`,
  ],
  caveats: [
    "The 'with app' side is a simulation, not an observation. Its trust level is the model error shown here.",
    "Only paddy has district yield records; other crops use typical national yields reduced for 2021 water stress.",
    "Costs, fertilizer rates and price elasticities are assumed values; prices are one week of 2021 quotes.",
    "The chemical-fertilizer import ban began in May 2021, which affected Yala 2021 and especially Maha 2021/22 (not included).",
  ],
  modelError: Object.fromEntries(S.map((s) => [s, {
    rmse: Math.round(R[best][`test_${s}_rmse`] * 100) / 100, r2: Math.round(R[best][`test_${s}_r2`] * 100) / 100,
    baselineRmse: Math.round(R["Same as last year"][`test_${s}_rmse`] * 100) / 100, baseline3Rmse: Math.round(R["3-year average"][`test_${s}_rmse`] * 100) / 100,
    n: ym.predictions.filter((p) => p.season === s).length,
  }])),
  cvRmse: Object.fromEntries(Object.entries(R).map(([k, v]) => [k, Math.round(v.cv_rmse * 1000) / 1000])),
  bestModel: best,
  featureSet: ym.featureSet,
  ablation: ym.ablation || [],
  predVsActual: ym.predictions.map((p) => ({ id: p.district, name: packs.find((x) => x.id === p.district)?.name || p.district, season: p.season, actual: p.actual, predicted: p.predicted, interval: p.interval, reasons: p.reasons })),
  scenarios: [summarize(base, basePr, 0), ...levels.map((a) => summarize(runs[a].ev, runs[a].pr, a))],
  scenariosNoMarketRule: [summarize(base, basePr, 0), ...levels.map((a) => summarize(naive[a].ev, naive[a].pr, a))],
  advice: Object.fromEntries(packs.map((p) => [p.id, runs[30].chosen[p.id]])),
  districts: Object.fromEntries(packs.map((p) => [p.id, {
    income_lkr_bn: [basePr.distIncome[p.id], ...levels.map((a) => runs[a].pr.distIncome[p.id])].map((v) => Math.round(v / 1e7) / 100),
    waterSavedPct: [0, ...levels.map((a) => r1((1 - runs[a].ev.dist[p.id].water / Math.max(1, base.dist[p.id].water)) * 100))],
  }])),
};
fs.writeFileSync(`${D}/backtest_2021.json`, JSON.stringify(out));
const f = (s) => `income ${s.income_lkr_bn} bn, irrigation ${s.water_mcm} MCM, N ${s.fertN_t} t, bare Yala ${s.bareFallow_ha} ha | price % ${JSON.stringify(Object.fromEntries(ids.map((c) => [c, s.perCrop[c].priceChangePct])))}`;
console.log("without app:        ", f(out.scenarios[0]));
levels.forEach((a, i) => console.log(`app ${a}% + market:  `, f(out.scenarios[i + 1])));
levels.forEach((a, i) => console.log(`app ${a}% no rule:   `, f(out.scenariosNoMarketRule[i + 1])));
const tally = {};
for (const r of Object.values(out.advice)) { const k = `${r.rot.maha}>${r.rot.yala}@${Math.round(r.share * 100)}%`; tally[k] = (tally[k] || 0) + 1; }
console.log("advice at 30 %:", JSON.stringify(tally));
