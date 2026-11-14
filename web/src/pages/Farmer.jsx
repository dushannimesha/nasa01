import { useEffect, useMemo, useState } from "react";
import { useData, fmt, INK } from "../lib/data.js";
import { planRotations, simulateRotation, explain, rotName, rotKey, CRITERIA, byId, SEASON_LABEL, growthStage, kcOnDay } from "../lib/model.js";
import { savePlan } from "../lib/store.js";
import DistrictMap from "../components/DistrictMap.jsx";
import LocationPicker from "../components/LocationPicker.jsx";
import EChart, { axis } from "../components/EChart.jsx";
import { SampleBanner, Card, Slider, Loading, Suit, CropDot, LevelIcon } from "../components/ui.jsx";
import { ArrowLeft } from "lucide-react";

const LINE = ["#2a78d6", "#eb6834", "#1baf7a", "#898781"];
const WATER = { rain: "Rain only", tank: "Tank / canal", well: "Agro-well" };
const addDays = (d, n) => new Date(new Date(d).getTime() + n * 86400000);
const dm = (d) => d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });

export default function Farmer() {
  const [base, error] = useData(["/data/crops.json", "/geo/districts.json"]);
  const [districtId, setDistrictId] = useState(() => new URLSearchParams(location.search).get("district") || "anuradhapura");
  const [marker, setMarker] = useState(null);
  const [packData] = useData([`/data/packs/${districtId}.json`]);
  const [tab, setTab] = useState(() => new URLSearchParams(location.search).get("tab") || "plan");
  const [f, setF] = useState({ areaHa: 1, waterSource: "tank", maha: "paddy", yala: "fallow", market: true });
  const [weights, setWeights] = useState({ profit: 7, risk: 5, water: 5, soil: 5, erosion: 2, pest: 3 });
  const [saved, setSaved] = useState(null);
  const pack = packData?.[0];
  useEffect(() => { if (pack) setF((s) => ({ ...s, ...pack.typicalRotation })); }, [pack?.id]);

  const result = useMemo(() => {
    if (!base || !pack) return null;
    return planRotations(pack, base[0].crops, { maha: f.maha, yala: f.yala }, weights, { waterSource: f.waterSource, market: f.market, areaHa: 0 });
  }, [base, pack, f, weights]);

  if (!base || !pack || !result) return <Loading error={error} />;
  const cropList = base[0].crops, crops = result.crops, geo = base[1];
  const o = { waterSource: f.waterSource, market: f.market };
  const options = [...result.top, result.existing];
  const upd = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const register = async (sim) => {
    const fert = { n: 0, p: 0, k: 0 };
    for (const s of ["maha", "yala"]) { const c = crops[sim.rot[s]]; if (c) { fert.n += c.n * f.areaHa; fert.p += c.p * f.areaHa; fert.k += c.k * f.areaHa; } }
    const res = await savePlan({ districtId, areaHa: Number(f.areaHa), waterSource: f.waterSource, rotation: sim.rot, by: "farmer", lat: marker?.lat ?? pack.lat, lon: marker?.lng ?? pack.lon });
    setSaved({ name: rotName(sim.rot, crops), fert, where: res.where });
  };

  return (
    <div className="page">
      <SampleBanner meta={pack.meta} />
      <div className="page-head"><div><h1>Plan my field: detailed view</h1><p>Find your field by GPS, by name or on the map, tell us what matters to you, and compare rotations for {pack.name}.</p></div><a className="btn ghost" href="/farm"><ArrowLeft size={16} aria-hidden="true" /> Simple view</a></div>

      <div className="grid one-two">
        <div className="stack">
          <Card title="1. Where is your field?" sub={`Selected: ${pack.name} (${pack.zone} zone)`}>
            <LocationPicker geo={geo} onPick={(id, pos) => { setDistrictId(id); setMarker(pos); setSaved(null); }} />
            <DistrictMap geo={geo} selected={districtId} marker={marker} height={300} overlayControls={false}
              onSelect={(id, latlng) => { setDistrictId(id); setMarker(latlng); setSaved(null); }} />
            <p className="note">Soil here: pH {pack.soil.ph}, organic carbon {pack.soil.soc_pct} %, {pack.soil.texture}. Rain: Maha {pack.climate.seasonRain.maha} mm, Yala {pack.climate.seasonRain.yala} mm.
              {pack.climate.seasonal?.issued && <> Next 3 months ({pack.climate.seasonal.months?.join(", ")}): rain {pack.climate.seasonal.rainOutlook} ({pack.climate.seasonal.anomaly_pct > 0 ? "+" : ""}{pack.climate.seasonal.anomaly_pct} %, seasonal forecast issued {pack.climate.seasonal.issued}).</>}</p>
          </Card>
          <Card title="2. Your field">
            <div className="row gap wrap">
              <label className="field"><span>Field size (ha)</span><input type="number" min="0.1" step="0.1" value={f.areaHa} onChange={upd("areaHa")} /></label>
              <label className="field"><span>Water source</span><select value={f.waterSource} onChange={upd("waterSource")}>{Object.entries(WATER).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            </div>
            <div className="row gap wrap">
              <label className="field"><span>What you grow in Maha</span><select value={f.maha} onChange={upd("maha")}>{cropList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label className="field"><span>What you grow in Yala</span><select value={f.yala} onChange={upd("yala")}><option value="fallow">Nothing (bare fallow)</option>{cropList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            </div>
            <label className="check"><input type="checkbox" checked={f.market} onChange={upd("market")} /> Adjust prices for what other farmers in the district have registered</label>
          </Card>
          <Card title="3. What matters most to you?">
            {CRITERIA.map((c) => <Slider key={c.id} label={c.label} value={weights[c.id]} min={0} max={10} onChange={(v) => setWeights((s) => ({ ...s, [c.id]: v }))} />)}
          </Card>
        </div>

        <div className="stack">
          <div className="tabs" role="tablist">
            {[["plan", "Recommended rotations"], ["idea", "My own idea"], ["monitor", "Already planted"]].map(([k, v]) => <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{v}</button>)}
          </div>
          {tab === "plan" && <Plan {...{ options, result, pack, crops, o, f, register, saved }} />}
          {tab === "idea" && <Idea {...{ result, pack, crops, cropList, o, f }} />}
          {tab === "monitor" && <Monitor {...{ pack, cropList, marker }} />}
        </div>
      </div>
    </div>
  );
}

function Plan({ options, result, pack, crops, o, f, register, saved }) {
  const ex = result.existing;
  const option = {
    xAxis: axis({ type: "category", data: ex.traj.labels, splitLine: { show: false }, axisLabel: { color: INK.muted, fontSize: 10, interval: 1 } }),
    yAxis: axis({ type: "value", name: "Soil nitrogen index (kg/ha)", scale: true }),
    tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: INK.axis } } },
    series: options.map((s, i) => ({
      name: (s === ex ? "Current: " : `${i + 1}. `) + rotName(s.rot, crops), type: "line", data: s.traj.n, symbol: "circle", symbolSize: 6, showSymbol: false,
      lineStyle: { width: 2, type: s === ex ? "dashed" : "solid" }, itemStyle: { color: s === ex ? LINE[3] : LINE[i] },
    })),
  };
  return (
    <>
      {saved && <div className="notice"><b>Plan registered: {saved.name}.</b> Fertilizer entitlement estimate for {f.areaHa} ha: {Math.round(saved.fert.n)} kg N, {Math.round(saved.fert.p)} kg P, {Math.round(saved.fert.k)} kg K (DoA rates). Saved {saved.where === "firestore" ? "to the national register; it syncs when you are online" : "on this device"}.</div>}
      {options.map((sim, i) => {
        const isEx = sim === ex;
        const x = explain(sim, ex, pack, crops, o);
        return (
          <section key={rotKey(sim.rot)} className={`card rot ${isEx ? "existing" : ""}`}>
            <div className="rot-head">
              <div><div className="eyebrow">{isEx ? `Your current rotation · ranked ${sim.rank} of ${result.ranked.length}` : `Option ${i + 1}`}</div>
                <h3><CropDot id={sim.rot.maha} />{rotName(sim.rot, crops)}</h3></div>
              <Suit level={sim.suit} />
            </div>
            <div className="meter" title="Match with your priorities"><div style={{ width: `${Math.round(sim.score * 100)}%` }} /></div>
            <div className="facts">
              <div><span>Match</span><b>{Math.round(sim.score * 100)} / 100</b></div>
              <div><span>Income per year, whole field</span><b>{fmt.lkrK(sim.annualProfit[0] * f.areaHa)} to {fmt.lkrK(sim.annualProfit[2] * f.areaHa)}</b></div>
              <div><span>Water per year</span><b>{Math.round(sim.water_mm)} mm</b></div>
              <div><span>Soil nitrogen after 5 years</span><b>{sim.dN >= 0 ? "+" : ""}{Math.round(sim.dN)} kg/ha</b></div>
            </div>
            <p className="why">{x.why[0]}</p>
            <details>
              <summary>Why, evidence, risks and gaps</summary>
              <div className="explain">
                <div><h4>Why suggested</h4><ul>{x.why.map((t, k) => <li key={k}>{t}</li>)}</ul></div>
                <div><h4>Evidence</h4><ul>{x.evidence.map((t, k) => <li key={k}>{t}</li>)}</ul></div>
                {x.benefits.length > 0 && <div><h4>Benefits</h4><ul>{x.benefits.map((t, k) => <li key={k}>{t}</li>)}</ul></div>}
                {x.risks.length > 0 && <div><h4>Risks to check locally</h4><ul>{x.risks.map((t, k) => <li key={k}>{t}</li>)}</ul></div>}
                <div><h4>What this tool does not know</h4><ul>{x.gaps.map((t, k) => <li key={k}>{t}</li>)}</ul></div>
              </div>
            </details>
            <button className="btn" onClick={() => register(sim)}>Register this plan</button>
          </section>
        );
      })}
      <Card title="Soil over five years" sub="Nitrogen left in the soil after each season, for the options above. Legumes add; bare seasons lose.">
        <EChart option={option} height={280} label="Soil nitrogen index over ten seasons by rotation" />
      </Card>
      <p className="note">{result.rejected.length} rotations were ruled out because a crop in them does not get enough water with your water source.</p>
    </>
  );
}

function Idea({ result, pack, crops, cropList, o, f }) {
  const [crop, setCrop] = useState("bigonion");
  const [season, setSeason] = useState("yala");
  const [sow, setSow] = useState(season === "yala" ? "2021-05-01" : "2020-10-20");
  useEffect(() => setSow(season === "yala" ? "2021-05-01" : "2020-10-20"), [season]);
  const rot = { maha: f.maha, yala: f.yala, [season]: crop };
  const sim = simulateRotation(pack, crops, rot, o);
  const s = sim.seasons.find((x) => x.season === season);
  const c = crops[crop];
  const best = result.top[0], ex = result.existing;
  let day = 0;
  const row = (label, a) => <tr><td>{label}</td><td className="num">{fmt.lkrK(a.annualProfit[0] * f.areaHa)} to {fmt.lkrK(a.annualProfit[2] * f.areaHa)}</td><td className="num">{Math.round(a.water_mm)} mm</td><td className="num">{a.dN >= 0 ? "+" : ""}{Math.round(a.dN)}</td></tr>;
  return (
    <>
      <Card title="I want to grow…">
        <div className="row gap wrap">
          <label className="field"><span>Crop</span><select value={crop} onChange={(e) => setCrop(e.target.value)}>{cropList.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label className="field"><span>Season</span><select value={season} onChange={(e) => setSeason(e.target.value)}><option value="maha">Maha</option><option value="yala">Yala</option></select></label>
          <label className="field"><span>Planned sowing date</span><input type="date" value={sow} onChange={(e) => setSow(e.target.value)} /></label>
        </div>
      </Card>
      <Card title={`Can ${c.name} work here in ${SEASON_LABEL[season]}?`}>
        <div className="row gap"><Suit level={s.suit} /><span>Expected yield {s.yield[0].toFixed(1)} to {s.yield[2].toFixed(1)} t/ha · water supply covers {Math.round(s.ratio * 100)} % of need{o.market && Math.abs(s.priceShift) >= 3 ? ` · price expected ${fmt.pct(s.priceShift)} from other farmers' plans` : ""}</span></div>
        <ul>{s.reasons.map((r, k) => <li key={k}>{r}</li>)}</ul>
      </Card>
      <Card title="How it compares" sub={`Your idea as part of the rotation ${rotName(rot, crops)}.`}>
        <table className="tbl"><thead><tr><th>Rotation</th><th className="num">Income per year</th><th className="num">Water</th><th className="num">Soil N after 5 yr</th></tr></thead>
          <tbody>{row(`Your idea: ${rotName(rot, crops)}`, sim)}{row(`Top recommendation: ${rotName(best.rot, crops)}`, best)}{row(`Current: ${rotName(ex.rot, crops)}`, ex)}</tbody></table>
      </Card>
      <Card title="How to grow it: calendar" sub={`${c.days} days from sowing to harvest. Fertilizer timings follow Department of Agriculture practice; confirm rates locally.`}>
        <table className="tbl"><thead><tr><th>When</th><th>Stage</th><th>What to do</th></tr></thead>
          <tbody>
            {c.stages.map((st) => { const from = day; day += st.days; const jobs = c.fert.filter((x) => x.day >= from && x.day < day); return (
              <tr key={st.name}><td>{dm(addDays(sow, from))} to {dm(addDays(sow, day - 1))}</td><td>{st.name}</td>
                <td>{jobs.length ? jobs.map((j) => `${dm(addDays(sow, j.day))}: ${j.text}`).join("; ") : st.kc >= 1 ? "Peak water demand: do not let the field dry out" : "Weed and scout for pests"}</td></tr>); })}
            <tr><td>{dm(addDays(sow, c.days))}</td><td>Harvest</td><td>Harvest window opens</td></tr>
          </tbody></table>
      </Card>
    </>
  );
}

function Monitor({ pack, cropList, marker }) {
  const [crop, setCrop] = useState("paddy");
  const [sow, setSow] = useState(() => addDays(new Date(), -40).toISOString().slice(0, 10));
  const [wx, setWx] = useState(null);
  const [err, setErr] = useState(null);
  const lat = marker?.lat ?? pack.lat, lon = marker?.lng ?? pack.lon;
  useEffect(() => {
    setWx(null); setErr(null);
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${lat.toFixed(3)}&longitude=${lon.toFixed(3)}&daily=precipitation_sum,et0_fao_evapotranspiration,temperature_2m_max&past_days=14&forecast_days=14&timezone=auto`)
      .then((r) => r.json()).then((j) => (j.daily ? setWx(j.daily) : setErr("No forecast returned"))).catch(() => setErr("No connection and no saved forecast for this place yet."));
  }, [lat, lon]);
  const c = cropList.find((x) => x.id === crop);
  const g = growthStage(c, sow);
  const actions = [];
  let chart = null;
  if (wx) {
    const today = new Date().toISOString().slice(0, 10);
    const ti = Math.max(0, wx.time.indexOf(today));
    const etc = wx.time.map((t, i) => +(wx.et0_fao_evapotranspiration[i] * kcOnDay(c, g.day + (i - ti))).toFixed(1));
    const deficit = Math.max(0, etc.slice(0, ti).reduce((s, v) => s + v, 0) - wx.precipitation_sum.slice(0, ti).reduce((s, v) => s + (v || 0), 0));
    const rain3 = wx.precipitation_sum.slice(ti, ti + 3).reduce((s, v) => s + (v || 0), 0);
    const hot = Math.max(...wx.temperature_2m_max.slice(ti, ti + 7));
    const raw = 0.5 * pack.soil.awc_mm;
    if (g.day < 0) actions.push(["info", `Sowing is ${-g.day} days away.`]);
    else if (g.done) actions.push(["good", "The crop has reached maturity. Harvest when the weather is dry."]);
    else {
      if (deficit > raw && rain3 < 10) actions.push(["critical", `Irrigate: the crop used about ${Math.round(deficit)} mm more than it rained in the last ${ti} days, and under 10 mm is forecast in the next 3 days.`]);
      else if (deficit > raw) actions.push(["warning", `Water is short by about ${Math.round(deficit)} mm, but ${Math.round(rain3)} mm of rain is forecast in the next 3 days. Wait and check the field.`]);
      else actions.push(["good", `Water is adequate (shortfall ${Math.round(deficit)} mm over the last ${ti} days).`]);
      if (rain3 > 100) actions.push(["serious", `Heavy rain forecast (${Math.round(rain3)} mm in 3 days): open drains and delay fertilizer.`]);
      if (hot >= 35 && /flower|tassel|panicle/i.test(g.stage.name)) actions.push(["serious", `Heat alert: up to ${hot.toFixed(0)} °C forecast during ${g.stage.name.toLowerCase()}. Keep the soil moist.`]);
      c.fert.filter((x) => Math.abs(x.day - g.day) <= 5).forEach((x) => actions.push(["info", `Fertilizer due around day ${x.day} (${dm(addDays(sow, x.day))}): ${x.text}.`]));
      if (c.days - g.day <= 14) actions.push(["info", `Harvest in about ${c.days - g.day} days.`]);
    }
    chart = {
      xAxis: axis({ type: "category", data: wx.time.map((t) => dm(new Date(t))), splitLine: { show: false }, axisLabel: { color: INK.muted, fontSize: 10, interval: 3 } }),
      yAxis: axis({ type: "value", name: "mm per day" }),
      series: [
        { name: "Rain", type: "bar", barMaxWidth: 10, data: wx.precipitation_sum, itemStyle: { color: "#2a78d6", borderRadius: [3, 3, 0, 0] }, markLine: { symbol: "none", silent: true, lineStyle: { color: INK.muted, type: "dashed" }, label: { formatter: "today", color: INK.secondary }, data: [{ xAxis: ti }] } },
        { name: "Crop water use", type: "line", data: etc, showSymbol: false, lineStyle: { width: 2 }, itemStyle: { color: "#eb6834" } },
      ],
    };
  }
  return (
    <>
      <Card title="What I planted">
        <div className="row gap wrap">
          <label className="field"><span>Crop</span><select value={crop} onChange={(e) => setCrop(e.target.value)}>{cropList.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>
          <label className="field"><span>Sowing date</span><input type="date" value={sow} onChange={(e) => setSow(e.target.value)} /></label>
        </div>
      </Card>
      <Card title={g.day < 0 ? "Not sown yet" : g.done ? "Ready for harvest" : `Day ${g.day}: ${g.stage.name}`} sub={`${c.name} · ${c.days} days to harvest`}>
        <div className="stagebar">{c.stages.map((st) => <div key={st.name} style={{ flex: st.days }} className={st === g.stage && !g.done && g.day >= 0 ? "on" : ""}><span>{st.name}</span></div>)}</div>
        {err && <p className="note">{err}</p>}
        {!wx && !err && <p className="note">Loading the 14-day forecast…</p>}
        <ul className="actions">{actions.map(([lvl, text], k) => <li key={k} className={lvl}><LevelIcon level={lvl} size={20} />{text}</li>)}</ul>
      </Card>
      {chart && <Card title="Rain and crop water use" sub="Last 14 days and next 14 days. Weather: Open-Meteo forecast (not NASA). Crop water use = reference evapotranspiration × crop factor (FAO-56).">
        <EChart option={chart} height={240} label="Daily rain and crop water use" /></Card>}
    </>
  );
}
