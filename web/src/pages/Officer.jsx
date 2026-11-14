import { useState } from "react";
import { useData, fmt } from "../lib/data.js";
import { byId, rotName } from "../lib/model.js";
import { savePlan, usePlans, hasFirebase } from "../lib/store.js";
import { Card, Loading, Tile } from "../components/ui.jsx";

export default function Officer() {
  const [data, error] = useData(["/data/crops.json", "/geo/districts.json"]);
  const { plans, source } = usePlans();
  const [f, setF] = useState({ farmer: "", districtId: "anuradhapura", areaHa: 1, waterSource: "tank", maha: "paddy", yala: "greengram" });
  const [msg, setMsg] = useState("");
  if (!data) return <Loading error={error} />;
  const cropList = data[0].crops, crops = byId(cropList);
  const districts = data[1].features.map((x) => x.properties).sort((a, b) => a.name.localeCompare(b.name));
  const dName = byId(districts);
  const upd = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.value }));
  const submit = async (e) => {
    e.preventDefault();
    await savePlan({ farmerRef: f.farmer.trim() || "unnamed", districtId: f.districtId, areaHa: Number(f.areaHa), waterSource: f.waterSource, rotation: { maha: f.maha, yala: f.yala }, by: "officer" });
    const n = crops[f.maha].n * f.areaHa + (crops[f.yala]?.n || 0) * f.areaHa;
    setMsg(`Registered ${f.farmer || "farmer"}: ${rotName({ maha: f.maha, yala: f.yala }, crops)}, ${f.areaHa} ha. Nitrogen entitlement estimate ${Math.round(n)} kg.`);
    setF((s) => ({ ...s, farmer: "" }));
  };
  const area = plans.reduce((s, p) => s + (Number(p.areaHa) || 0), 0);
  return (
    <div className="page">
      <div className="page-head"><div><h1>Officer desk</h1><p>Register plans for farmers who have no phone. Each entry counts toward the district totals and the farmer's fertilizer entitlement.</p></div></div>
      <div className="tiles">
        <Tile label="Plans on the register" value={fmt.int(plans.length)} sub={source === "firestore" ? "Shared national register (Firestore)" : hasFirebase ? "Register unreachable: showing this device" : "Stored on this device only"} />
        <Tile label="Area registered" value={`${fmt.int(area)} ha`} />
        <Tile label="Entered by officers" value={fmt.int(plans.filter((p) => p.by === "officer").length)} />
      </div>
      <div className="grid one-two">
        <Card title="New registration">
          <form onSubmit={submit} className="stack">
            <label className="field"><span>Farmer reference number (do not enter names; the register is readable by anyone)</span><input value={f.farmer} onChange={upd("farmer")} placeholder="e.g. Farmer 0412" /></label>
            <label className="field"><span>District</span><select value={f.districtId} onChange={upd("districtId")}>{districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
            <div className="row gap wrap">
              <label className="field"><span>Field size (ha)</span><input type="number" min="0.1" step="0.1" value={f.areaHa} onChange={upd("areaHa")} /></label>
              <label className="field"><span>Water source</span><select value={f.waterSource} onChange={upd("waterSource")}><option value="rain">Rain only</option><option value="tank">Tank / canal</option><option value="well">Agro-well</option></select></label>
            </div>
            <div className="row gap wrap">
              <label className="field"><span>Maha crop</span><select value={f.maha} onChange={upd("maha")}>{cropList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label className="field"><span>Yala crop</span><select value={f.yala} onChange={upd("yala")}><option value="fallow">Bare fallow</option>{cropList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
            </div>
            <button className="btn">Register plan</button>
            {msg && <div className="notice">{msg}</div>}
          </form>
        </Card>
        <Card title="Register" sub="Newest first.">
          {plans.length === 0 ? <p className="note">No plans yet. Register one here or on the Farmer page.</p> : (
            <table className="tbl"><thead><tr><th>When</th><th>Farmer</th><th>District</th><th>Rotation</th><th className="num">ha</th><th>By</th></tr></thead>
              <tbody>{plans.slice(0, 50).map((p, i) => (
                <tr key={p.id || i}><td>{(p.createdAt || "").slice(0, 10)}</td><td>{p.farmerRef || "self"}</td><td>{dName[p.districtId]?.name || p.districtId}</td><td>{p.rotation ? rotName(p.rotation, crops) : ""}</td><td className="num">{p.areaHa}</td><td>{p.by}</td></tr>))}</tbody></table>)}
        </Card>
      </div>
    </div>
  );
}
