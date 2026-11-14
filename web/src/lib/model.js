// Interactive engine used by every page. It combines the per-district numbers in the data
// packs (produced by the Python models) into rotation outcomes, rankings and national totals.
// Thin by design: each formula is a simplified version of the blueprint model named beside it.

export const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
export const SEASONS = ["maha", "yala"];
export const SEASON_LABEL = { maha: "Maha", yala: "Yala" };
export const byId = (list) => Object.fromEntries(list.map((x) => [x.id, x]));

export const CRITERIA = [
  { id: "profit", label: "Income", benefit: true },
  { id: "risk", label: "Low risk", benefit: true },
  { id: "water", label: "Water saving", benefit: false },
  { id: "soil", label: "Soil health", benefit: true },
  { id: "erosion", label: "Erosion control", benefit: false },
  { id: "pest", label: "Pest-cycle break", benefit: false },
];

// M6: more planned area than usual -> more supply -> lower expected price (and the reverse).
export function priceShiftPct(pack, crops, cropId, season, extraHa = 0) {
  const s = pack.crops[cropId]?.[season];
  if (!s || !s.district_area_ha) return 0;
  const supplyPct = ((s.planned_area_ha + extraHa) / s.district_area_ha - 1) * 100;
  return clamp(supplyPct / crops[cropId].elasticity, -45, 45);
}

// M2 (thin): one season of one crop on one field.
export function seasonOutcome(pack, crops, cropId, season, o) {
  const crop = crops[cropId];
  if (!crop || cropId === "fallow") return { cropId: "fallow", profit: [0, 0, 0], yield: [0, 0, 0], water_mm: 0, ratio: 1, priceShift: 0, suit: "pass", reasons: [] };
  const p = pack.crops[cropId];
  const s = p[season];
  const w = pack.water[season];
  const need = s.water_mm * (1 + 0.03 * (o.tempC || 0));
  // s.supply (from the water-balance model) = share of the crop's need met by each water source
  const avail = s.supply
    ? s.water_mm * s.supply[o.waterSource] * (1 + ((o.rainPct || 0) / 100) * (o.waterSource === "rain" ? 1 : 0.5))
    : w[o.waterSource] + w.rain * ((o.rainPct || 0) / 100);
  const ratio = clamp(avail / need, 0, 1);
  const waterMult = clamp(1 - crop.ky * (1 - ratio), 0.1, 1);       // FAO yield response to water
  const heatMult = 1 - 0.04 * (o.tempC || 0);
  const pestMult = 1 - 0.25 * (o.pest?.[crop.family] || 0);
  const nMult = crop.family === "legume" ? 1 : clamp(0.85 + 0.15 * ((o.soilN ?? pack.soil.n_kg_ha) / pack.soil.n_kg_ha), 0.8, 1.1);
  const mult = waterMult * heatMult * pestMult * nMult;
  const priceShift = o.market ? priceShiftPct(pack, crops, cropId, season, o.areaHa || 0) : 0;
  const price = p.price * (1 + priceShift / 100);
  const yld = s.yield.map((y) => y * mult);
  const profit = yld.map((y) => y * 1000 * price - p.cost);
  let suit = s.suit;
  const reasons = [...s.reasons];
  if (ratio < 0.5) { suit = "fail"; reasons.unshift(`With ${o.waterSource === "rain" ? "rain only" : o.waterSource + " water"} the season supplies about ${Math.round(ratio * 100)} % of the water this crop needs.`); }
  else if (ratio < 0.8 && suit === "pass") { suit = "warn"; reasons.unshift(`Water supply covers about ${Math.round(ratio * 100)} % of the crop's need; expect some stress.`); }
  return { cropId, profit, yield: yld, water_mm: Math.min(avail, need), ratio, priceShift, price, suit, reasons };
}

// M4 (thin): carry soil nitrogen, organic carbon and pest pressure across 5 years (10 seasons).
export function simulateRotation(pack, crops, rot, o) {
  let n = pack.soil.n_kg_ha, soc = pack.soil.soc_pct;
  const pest = {};
  const traj = { labels: [], n: [], soc: [], pest: [], profit: [] };
  const tot = { profit: [0, 0, 0], water: 0, erosion: 0, pest: 0 };
  const seasons = [];
  let worst = "pass";
  for (let year = 1; year <= 5; year++) {
    for (const season of SEASONS) {
      const cropId = rot[season];
      const crop = crops[cropId];
      const out = seasonOutcome(pack, crops, cropId, season, { ...o, soilN: n, pest });
      if (year === 1) seasons.push({ season, ...out });
      if (out.suit === "fail") worst = "fail"; else if (out.suit === "warn" && worst !== "fail") worst = "warn";
      out.profit.forEach((v, i) => (tot.profit[i] += v));
      tot.water += out.water_mm;
      const family = crop?.family || "none";
      tot.pest += pest[family] || 0;
      // nitrogen index: legumes leave a credit, other crops draw the soil down slowly, bare soil leaches
      n = clamp(n + (cropId === "fallow" ? -3 : crop.nFix ? crop.nFix * 0.4 : -6), 15, 120);
      // organic carbon: residue adds, decomposition removes
      soc = soc + 0.02 * (crop?.residueC || 0.1) - 0.012 * soc;
      // erosion index: uncovered soil x slope x seasonal rain
      const cover = cropId === "fallow" ? 0.2 : crop.cover;
      tot.erosion += (1 - cover) * (1 + pack.slope_pct / 5) * (pack.climate.seasonRain[season] / 1000);
      for (const f of ["rice", "cereal", "legume", "allium", "solanaceae"]) pest[f] = f === family ? clamp((pest[f] || 0) + 0.3, 0, 1) : (pest[f] || 0) * 0.5;
      traj.labels.push(`Y${year} ${SEASON_LABEL[season]}`);
      traj.n.push(+n.toFixed(1)); traj.soc.push(+soc.toFixed(3)); traj.pest.push(+(pest[family] || 0).toFixed(2)); traj.profit.push(Math.round(out.profit[1]));
    }
  }
  const annualProfit = tot.profit.map((v) => v / 5);
  return {
    rot, seasons, suit: worst, traj, annualProfit,
    water_mm: tot.water / 5, erosion: tot.erosion / 5, pestAvg: tot.pest / 10,
    dN: n - pack.soil.n_kg_ha, dSoc: soc - pack.soil.soc_pct,
    criteria: {
      profit: annualProfit[1], risk: annualProfit[0], water: tot.water / 5,
      soil: (n - pack.soil.n_kg_ha) / pack.soil.n_kg_ha + (soc - pack.soil.soc_pct) / pack.soil.soc_pct,
      erosion: tot.erosion / 5, pest: tot.pest / 10,
    },
  };
}

// M7: TOPSIS (Hwang & Yoon 1981). Returns a closeness score 0..1 for each row.
export function topsis(rows, weights) {
  const wSum = CRITERIA.reduce((s, c) => s + (weights[c.id] || 0), 0) || 1;
  const cols = CRITERIA.map((c) => {
    const vals = rows.map((r) => r.criteria[c.id]);
    const norm = Math.sqrt(vals.reduce((s, v) => s + v * v, 0)) || 1;
    const v = vals.map((x) => (x / norm) * ((weights[c.id] || 0) / wSum));
    const best = c.benefit ? Math.max(...v) : Math.min(...v);
    const worst = c.benefit ? Math.min(...v) : Math.max(...v);
    return { v, best, worst };
  });
  return rows.map((_, i) => {
    const dBest = Math.sqrt(cols.reduce((s, c) => s + (c.v[i] - c.best) ** 2, 0));
    const dWorst = Math.sqrt(cols.reduce((s, c) => s + (c.v[i] - c.worst) ** 2, 0));
    return dBest + dWorst === 0 ? 0.5 : dWorst / (dBest + dWorst);
  });
}

export const rotKey = (r) => `${r.maha}>${r.yala}`;
export const rotName = (r, crops) => `${crops[r.maha]?.name || "Bare fallow"} → ${crops[r.yala]?.name || "Bare fallow"}`;

// Mode A: every Maha -> Yala pair that passes suitability, ranked by the farmer's priorities.
export function planRotations(pack, cropList, existing, weights, o) {
  const crops = byId(cropList);
  const all = [];
  for (const maha of cropList) for (const yala of [...cropList, { id: "fallow" }]) all.push({ maha: maha.id, yala: yala.id });
  if (!all.some((r) => rotKey(r) === rotKey(existing))) all.push(existing);
  const sims = all.map((r) => simulateRotation(pack, crops, r, o));
  // never recommend a rotation that fails on water or loses money in a normal year (the current rotation is always kept for comparison)
  const usable = sims.filter((s) => (s.suit !== "fail" && s.annualProfit[1] >= 0) || rotKey(s.rot) === rotKey(existing));
  const scores = topsis(usable, weights);
  usable.forEach((s, i) => (s.score = scores[i]));
  const ranked = [...usable].sort((a, b) => b.score - a.score);
  ranked.forEach((s, i) => (s.rank = i + 1));
  const existingSim = ranked.find((s) => rotKey(s.rot) === rotKey(existing));
  const top = ranked.filter((s) => s !== existingSim).slice(0, 3);
  return { top, existing: existingSim, ranked, rejected: sims.filter((s) => s.suit === "fail" && rotKey(s.rot) !== rotKey(existing)), crops };
}

const lkr = (v) => `LKR ${Math.round(v / 1000).toLocaleString()}k`;

// Explanation card: why, evidence, benefits, risks, gaps. Built from the numbers, not canned text.
export function explain(sim, existing, pack, crops, o) {
  const why = [], evidence = [], benefits = [], risks = [], gaps = [];
  const c = sim.criteria, e = existing?.criteria;
  const legume = SEASONS.some((s) => crops[sim.rot[s]]?.family === "legume");
  const same = sim.rot.maha === sim.rot.yala;
  if (e && sim !== existing) {
    if (c.profit > e.profit * 1.05) why.push(`Expected yearly income is about ${lkr(c.profit - e.profit)} per hectare higher than your current rotation.`);
    if (c.water < e.water * 0.92) why.push(`Uses about ${Math.round((1 - c.water / e.water) * 100)} % less water per year than your current rotation.`);
    if (c.soil > e.soil + 0.03) why.push("Leaves the soil with more nitrogen and organic matter after five years.");
    if (c.pest < e.pest - 0.05) why.push("Changing crop family between seasons breaks pest and disease build-up.");
    if (c.erosion < e.erosion * 0.9) why.push("Keeps the field covered for more of the year, which reduces erosion.");
    if (c.risk > e.risk * 1.05 && c.risk > 0) why.push("Income in a poor year (low end of the range) is still above your current rotation.");
  }
  if (!why.length) why.push(sim === existing ? "This is the rotation you entered; it is the reference the others are compared with." : "Balanced result across your priorities; no single criterion dominates.");
  for (const s of sim.seasons) {
    if (s.cropId === "fallow") { evidence.push(`${SEASON_LABEL[s.season]}: field left bare. Rain in this season is about ${pack.climate.seasonRain[s.season]} mm (NASA POWER).`); continue; }
    evidence.push(`${SEASON_LABEL[s.season]} ${crops[s.cropId].name}: water supply covers ${Math.round(s.ratio * 100)} % of the ${pack.crops[s.cropId][s.season].water_mm} mm need (season rain ${pack.climate.seasonRain[s.season]} mm, NASA POWER); expected yield ${s.yield[0].toFixed(1)}–${s.yield[2].toFixed(1)} t/ha.`);
    if (o.market && Math.abs(s.priceShift) >= 3) evidence.push(`${crops[s.cropId].name} price is expected ${s.priceShift < 0 ? "lower" : "higher"} by about ${Math.abs(Math.round(s.priceShift))} % because farmers in this district have registered ${s.priceShift < 0 ? "more" : "less"} area than usual.`);
    s.reasons.filter((r) => !r.startsWith("Temperature, season")).forEach((r) => risks.push(`${SEASON_LABEL[s.season]} ${crops[s.cropId].name}: ${r}`));
  }
  evidence.push(`Soil: pH ${pack.soil.ph}, organic carbon ${pack.soil.soc_pct} %, ${pack.soil.texture} (SoilGrids). Slope about ${pack.slope_pct} %.`);
  if (legume) benefits.push("The legume fixes nitrogen from the air, so the next crop needs less urea.");
  if (sim.dN > 2) benefits.push(`Soil nitrogen index rises by about ${Math.round(sim.dN)} kg/ha over five years.`);
  if (sim.rot.yala !== "fallow") benefits.push("A crop in Yala gives a second income and keeps the soil covered.");
  if (!same && sim.rot.yala !== "fallow") benefits.push("Two different crops spread the weather and price risk.");
  for (const id of new Set(SEASONS.map((s) => sim.rot[s]))) {
    const c = crops[id];
    if (c?.marketRoomHa != null && id !== "paddy" && c.marketRoomHa < 0.25 * (c.nationalArea2021Ha || Infinity))
      risks.push(`${c.name} has a small national market: about ${Math.round(c.marketRoomHa).toLocaleString()} more hectares across the country would push its price down 15 %. If many farmers switch, expect lower prices.`);
  }
  if (same) risks.push("The same crop in both seasons lets pests and diseases of that crop build up.");
  if (sim.rot.yala === "fallow") risks.push("Bare soil in Yala loses nitrogen and organic matter and is open to erosion.");
  if (sim.annualProfit[0] < 0) risks.push(`In a poor year this rotation could lose money (low end ${lkr(sim.annualProfit[0])} per hectare per year).`);
  const shift = pack.climate.onset.shiftDays;
  if (Math.abs(shift) >= 7) risks.push(`Maha rains now start about ${Math.round(Math.abs(shift))} days ${shift > 0 ? "later" : "earlier"} than in the early 1980s (NASA POWER trend); plan sowing dates with that in mind.`);
  (pack.meta.assumptions || []).slice(0, 1).forEach((a) => gaps.push(a));
  gaps.push("Weather data is on a grid of about 50 km; your field can differ from the grid average.");
  gaps.push("Yield figures are district averages adjusted for water and soil, not measurements from your field.");
  gaps.push("Prices and costs are season averages; your buyer and input prices may differ.");
  gaps.push("Check variety choice, pest history and drainage with your Agricultural Instructor before deciding.");
  return { why, evidence, benefits, risks, gaps };
}

// Mode B: growth stage from days since sowing.
export function growthStage(crop, sowDate, today = new Date()) {
  const day = Math.floor((today - new Date(sowDate)) / 86400000);
  let start = 0;
  for (const st of crop.stages) {
    if (day < start + st.days) return { day, stage: st, stageDay: day - start, start, done: false };
    start += st.days;
  }
  return { day, stage: crop.stages[crop.stages.length - 1], stageDay: 0, start, done: day >= crop.days };
}
export function kcOnDay(crop, day) {
  let start = 0;
  for (const st of crop.stages) { if (day < start + st.days) return st.kc; start += st.days; }
  return 0;
}

// Mode D / E: national totals with what-if adjustments.
export function computeNational(national, cropList, w = {}) {
  const { rainPct = 0, tempC = 0, fertPct = 0, shiftFrom, shiftTo, shiftPct = 0 } = w;
  const tot = Object.fromEntries(cropList.map((c) => [c.id, { area_ha: 0, production_t: 0, base_t: 0, need_t: 0 }]));
  const fert = { n: 0, p: 0, k: 0 };
  let pop = 0;
  const districts = national.districts.map((d) => {
    pop += d.population;
    const out = { id: d.id, name: d.name, crops: {}, fertN_t: 0, production_t: 0 };
    const moved = shiftFrom && shiftTo && shiftFrom !== shiftTo ? d.crops[shiftFrom].area_ha * (shiftPct / 100) : 0;
    for (const c of cropList) {
      const dc = d.crops[c.id];
      const area = dc.area_ha + (c.id === shiftTo ? moved : c.id === shiftFrom ? -moved : 0);
      const mult = clamp(1 + (dc.sens.rainPerPct * rainPct + dc.sens.tempPerC * tempC + dc.sens.fertPerPct * fertPct) / 100, 0.2, 1.4);
      const production = area * dc.yield[1] * mult;
      const need = (d.population * c.perCapKg) / 1000;
      out.crops[c.id] = { area_ha: area, yield: dc.yield[1] * mult, production_t: production, balance_t: production - need };
      out.fertN_t += (area * c.n) / 1000;
      out.production_t += production;
      tot[c.id].area_ha += area; tot[c.id].production_t += production; tot[c.id].base_t += dc.production_t; tot[c.id].need_t += need;
      fert.n += (area * c.n) / 1000; fert.p += (area * c.p) / 1000; fert.k += (area * c.k) / 1000;
    }
    return out;
  });
  let kcal = 0, protein = 0;
  for (const c of cropList) {
    const t = tot[c.id];
    t.balance_t = t.production_t - t.need_t;
    t.priceChangePct = clamp(((t.production_t / t.base_t - 1) * 100) / c.elasticity, -60, 60);
    kcal += t.production_t * 1000 * c.kcalPerKg; protein += t.production_t * 1000 * c.proteinPerKg;
  }
  return {
    districts, byDistrict: byId(districts), crops: tot, fert, fertSupplied: { n: fert.n * (1 + fertPct / 100) }, population: pop,
    kcalCoverage: kcal / (pop * 365 * national.kcalNeedPerDay), proteinCoverage: protein / (pop * 365 * national.proteinNeedPerDay),
  };
}
