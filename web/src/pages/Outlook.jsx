import { useState } from "react";
import { useData, fmt, INK, STATUS } from "../lib/data.js";
import DistrictMap from "../components/DistrictMap.jsx";
import { SampleBanner, Card, Loading } from "../components/ui.jsx";

export default function Outlook() {
  const [data, error] = useData(["/data/outlook.json", "/data/crops.json", "/geo/world.json"]);
  const [crop, setCrop] = useState("paddy");
  const [sel, setSel] = useState("LKA");
  if (!data) return <Loading error={error} />;
  const [out, { crops }, world] = data;
  const rows = out.rows.filter((r) => r.crop === crop).sort((a, b) => b.balance_t - a.balance_t);
  const values = Object.fromEntries(rows.map((r) => [r.iso3, r.balance_t]));
  const byIso = Object.fromEntries(rows.map((r) => [r.iso3, r]));
  return (
    <div className="page">
      <SampleBanner meta={out.meta} />
      <div className="page-head">
        <div><h1>Harvest outlook board</h1><p>Each country publishes what it expects to harvest and whether it will have a surplus or a shortfall, before the harvest. Buyers and importing countries can plan early; sudden price shocks get smaller.</p></div>
        <label className="field"><span>Crop</span><select value={crop} onChange={(e) => setCrop(e.target.value)}>{crops.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      </div>
      <div className="grid two-one">
        <Card title="Expected surplus and deficit" sub="Blue: surplus available to trade. Red: expected import need. Grey: country not yet publishing.">
          <DistrictMap geo={world} values={values} diverging selected={sel} onSelect={setSel} center={[14, 88]} zoom={4} height={440} overlayControls={false}
            legendTitle="Expected balance (tonnes)" format={fmt.t}
            tooltip={(iso, p) => (byIso[iso] ? `<b>${p.name}</b><br/>${byIso[iso].balance_t >= 0 ? "Surplus" : "Deficit"} ${fmt.t(Math.abs(byIso[iso].balance_t))}` : `${p.name}: not publishing`)} />
        </Card>
        <Card title="Published outlooks" sub="Sri Lanka's row comes from this system. The other rows are placeholders that show how the board would look with more countries.">
          <table className="tbl">
            <thead><tr><th>Country</th><th className="num">Production</th><th className="num">Balance</th><th>Harvest</th><th>Source</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.iso3} className={r.iso3 === sel ? "sel" : ""} onClick={() => setSel(r.iso3)}>
                <td>{r.country}</td><td className="num">{fmt.t(r.production_t)}</td>
                <td className="num" style={{ color: r.balance_t < 0 ? STATUS.critical : INK.secondary }}>{r.balance_t < 0 ? "−" : "+"}{fmt.t(Math.abs(r.balance_t))}</td>
                <td>{r.fromModel ? r.window : "—"}</td>
                <td>{r.fromModel ? `Field Shift model · confidence ${r.confidence}` : <span className="chip">placeholder</span>}</td>
              </tr>))}</tbody>
          </table>
          <p className="note">The pipeline is region-agnostic: a second country joins by supplying its own yield statistics, prices and fertilizer rates; the NASA inputs are already global.</p>
        </Card>
      </div>
    </div>
  );
}
