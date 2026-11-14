import { useState } from "react";
import { useData, fmt, INK, CROP_COLORS } from "../lib/data.js";
import { byId } from "../lib/model.js";
import DistrictMap from "../components/DistrictMap.jsx";
import EChart, { axis } from "../components/EChart.jsx";
import { SampleBanner, Tile, Card, Loading, CropDot } from "../components/ui.jsx";

export default function Backtest() {
  const [data, error] = useData(["/data/backtest_2021.json", "/data/crops.json", "/geo/districts.json"]);
  const [adopt, setAdopt] = useState(30);
  if (!data) return <Loading error={error} />;
  const [bt, { crops }, geo] = data;
  const base = bt.scenarios.find((s) => s.adoptionPct === 0);
  const sc = bt.scenarios.find((s) => s.adoptionPct === adopt);
  const idx = [0, 10, 30, 50].indexOf(adopt);
  const d = (a, b) => ((a / b - 1) * 100);
  const gain = Object.fromEntries(Object.entries(bt.districts).map(([id, v]) => [id, (v.income_lkr_bn[idx] - v.income_lkr_bn[0]) * 1000])); // LKR million
  const names = byId(geo.features.map((f) => f.properties));

  const scatter = {
    grid: { left: 8, right: 16, top: 52, bottom: 28, containLabel: true },
    xAxis: axis({ type: "value", name: "Actual yield 2021 (t/ha, DCS)", nameLocation: "middle", nameGap: 26, scale: true, nameTextStyle: { color: INK.muted, fontSize: 11 } }),
    yAxis: axis({ type: "value", name: "Predicted (t/ha)", scale: true }),
    tooltip: { trigger: "item", formatter: (p) => { const r = bt.predVsActual.find((x) => x.name === p.data[2] && x.season === (p.seriesIndex === 0 ? "maha" : "yala"));
      return `<b>${p.data[2]}</b> Â· ${p.seriesName}<br/>Actual ${p.data[0]} t/ha<br/>Predicted ${p.data[1]} t/ha${r?.interval ? ` (80 %: ${r.interval[0]}â€“${r.interval[1]})` : ""}${r?.reasons ? "<br/>" + r.reasons.map((x) => `${x.feature} ${x.effect_t_ha > 0 ? "+" : ""}${x.effect_t_ha}`).join("<br/>") : ""}`; } },
    series: [["maha", "Maha 2020/21", "#2a78d6", "circle"], ["yala", "Yala 2021", "#eb6834", "diamond"]].map(([s, name, color, symbol], i) => ({
      name, type: "scatter", symbol, symbolSize: 9, itemStyle: { color, borderColor: INK.surface, borderWidth: 1 },
      data: bt.predVsActual.filter((r) => r.season === s).map((r) => [r.actual, r.predicted, r.name]),
      ...(i === 0 ? { markLine: { silent: true, symbol: "none", lineStyle: { color: INK.axis, type: "dashed" }, label: { show: false }, data: [[{ coord: [2, 2] }, { coord: [6, 6] }]] } } : {}),
    })),
  };
  const prod = {
    xAxis: axis({ type: "category", data: crops.map((c) => c.name), splitLine: { show: false } }),
    yAxis: axis({ type: "value", name: "Change in production (%)" }),
    legend: { show: false },
    tooltip: { trigger: "axis", formatter: (p) => { const c = crops[p[0].dataIndex]; return `<b>${c.name}</b><br/>Without app ${fmt.t(base.perCrop[c.id].production_t)}<br/>With app ${fmt.t(sc.perCrop[c.id].production_t)}<br/>Price ${fmt.pct(sc.perCrop[c.id].priceChangePct, 0)}`; } },
    series: [{ type: "bar", barMaxWidth: 28, label: { show: true, position: "top", color: INK.secondary, fontSize: 11, formatter: (p) => fmt.pct(p.value, 0) },
      data: crops.map((c) => { const v = d(sc.perCrop[c.id].production_t, base.perCrop[c.id].production_t); return { value: +v.toFixed(1), itemStyle: { color: CROP_COLORS[c.id], borderRadius: v >= 0 ? [4, 4, 0, 0] : [0, 0, 4, 4] } }; }) }],
  };
  const Row = ({ label, a, b, unit, lowerBetter }) => { const ch = d(b, a); const good = lowerBetter ? ch < 0 : ch > 0; return (
    <tr><td>{label}</td><td className="num">{fmt.int(a)} {unit}</td><td className="num">{fmt.int(b)} {unit}</td><td className="num" style={{ color: Math.abs(ch) < 0.05 ? INK.muted : good ? "#006300" : "#d03b3b" }}>{fmt.pct(ch, 1)}</td></tr>); };

  return (
    <div className="page">
      <SampleBanner meta={bt.meta} />
      <div className="page-head"><div><h1>2021 test: with and without Field Shift</h1><p>The model learned from seasons up to 2020 only. 2021 is used to check it, and to ask what would have changed if farmers had followed its advice.</p></div></div>

      <div className="grid two">
        <Card title="Step 1: how good is the yield model?" sub="Paddy yield by district, predicted from 2021 weather against what DCS recorded. Points on the dashed line are perfect predictions.">
          <div className="tiles small">
            {["maha", "yala"].map((s) => { const e = bt.modelError[s]; return (
              <Tile key={s} label={`${s === "maha" ? "Maha 2020/21" : "Yala 2021"} error (RMSE)`} value={`${e.rmse} t/ha`}
                sub={`RÂ² ${e.r2} Â· simple guesses: last year ${e.baselineRmse}, 3-year average ${e.baseline3Rmse}`} tone={e.baseline3Rmse != null && e.rmse > e.baseline3Rmse ? "bad" : ""} />); })}
          </div>
          {bt.cvRmse && <p className="note">Model chosen: {bt.bestModel}. Error when each year 2011â€“2020 is predicted only from earlier years: {Object.entries(bt.cvRmse).sort((a, b) => a[1] - b[1]).map(([k, v]) => `${k} ${v}`).join(" Â· ")} t/ha.
            {bt.modelError.yala.rmse > bt.modelError.yala.baseline3Rmse && " In Yala 2021 the model did slightly worse than the 3-year average."}</p>}
          <EChart option={scatter} height={280} label="Predicted against actual paddy yield, 2021" />
        </Card>
        <Card title="How the test was run">
          <ol className="steps">{bt.method.map((m, i) => <li key={i}>{m}</li>)}</ol>
          <h4>Read this before quoting results</h4>
          <ul>{bt.caveats.map((m, i) => <li key={i}>{m}</li>)}</ul>
        </Card>
      </div>

      <Card title="Step 2: what would have changed?" sub="Choose the share of farm area that follows the app's top recommendation.">
        <div className="seg" role="group" aria-label="Adoption">{[10, 30, 50].map((a) => <button key={a} className={adopt === a ? "on" : ""} onClick={() => setAdopt(a)}>{a} % of area</button>)}</div>
        <div className="grid two">
          <div>
            <table className="tbl"><thead><tr><th>National, crop year 2021</th><th className="num">Without app (actual)</th><th className="num">With app (simulated)</th><th className="num">Change</th></tr></thead>
              <tbody>
                <Row label="Farm income, 6 crops" a={base.income_lkr_bn} b={sc.income_lkr_bn} unit="bn LKR" />
                <Row label="Irrigation water needed" a={base.water_mcm} b={sc.water_mcm} unit="M mÂ³" lowerBetter />
                <Row label="Nitrogen fertilizer need" a={base.fertN_t} b={sc.fertN_t} unit="t" lowerBetter />
                <Row label="Land left bare in Yala" a={base.bareFallow_ha} b={sc.bareFallow_ha} unit="ha" lowerBetter />
              </tbody></table>
            <table className="tbl"><thead><tr><th>Crop</th><th className="num">Area change</th><th className="num">Production change</th><th className="num">Price effect</th></tr></thead>
              <tbody>{crops.map((c) => { const a = base.perCrop[c.id], b = sc.perCrop[c.id]; return (
                <tr key={c.id}><td><CropDot id={c.id} />{c.name}</td><td className="num">{fmt.pct(d(b.area_ha, a.area_ha), 0)}</td><td className="num">{fmt.pct(d(b.production_t, a.production_t), 0)}</td><td className="num">{fmt.pct(b.priceChangePct, 0)}</td></tr>); })}</tbody></table>
          </div>
          <EChart option={prod} height={300} label="Change in production by crop with the app" />
        </div>
      </Card>

      {bt.scenariosNoMarketRule && (() => { const nr = bt.scenariosNoMarketRule.find((s) => s.adoptionPct === adopt); return (
        <Card title="Why the market rule matters" sub={`The same ${adopt} % adoption if every adopting farmer got the single best answer for their district, with no national market check.`}>
          <table className="tbl"><thead><tr><th>Crop</th><th className="num">Price with market rule</th><th className="num">Price without it</th></tr></thead>
            <tbody>{crops.map((c) => (
              <tr key={c.id}><td><CropDot id={c.id} />{c.name}</td><td className="num">{fmt.pct(sc.perCrop[c.id].priceChangePct, 0)}</td>
                <td className="num" style={{ color: Math.abs(nr.perCrop[c.id].priceChangePct) > 30 ? "#d03b3b" : INK.secondary }}>{fmt.pct(nr.perCrop[c.id].priceChangePct, 0)}</td></tr>))}</tbody></table>
          <p className="note">Without the check, rice supply falls and its price jumps while the advised crops flood their small markets. The app stops advising a crop once its national price would move more than 15 % (5 % for rice). Income figures include these price effects.</p>
        </Card>); })()}

      <Card title="Where the gain would be" sub={`Simulated change in district farm income at ${adopt} % adoption, including farmers who did not switch but sell at the changed prices.`}>
        <DistrictMap geo={geo} values={gain} legendTitle="Farm income change (LKR million)" format={(v) => `${v > 0 ? "+" : ""}${Math.round(v).toLocaleString()}`} height={420} overlayControls={false}
          tooltip={(id) => `<b>${names[id].name}</b><br/>Income ${gain[id] > 0 ? "+" : ""}${Math.round(gain[id]).toLocaleString()} million LKR<br/>Water saved ${bt.districts[id].waterSavedPct[idx]} %`} />
      </Card>
    </div>
  );
}
