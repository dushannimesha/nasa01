import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useData, CROP_COLORS } from "../lib/data.js";
import { planRotations, explain } from "../lib/model.js";
import { savePlan } from "../lib/store.js";
import LocationPicker from "../components/LocationPicker.jsx";
import { Loading } from "../components/ui.jsx";

// Same presets as the text channel, so the phone app and the SMS-style bot give the same answer.
const GOALS = {
  income: { label: "More income", icon: "💰", w: { profit: 9, risk: 4, water: 2, soil: 2, erosion: 1, pest: 2 } },
  water: { label: "Save water", icon: "💧", w: { profit: 4, risk: 4, water: 9, soil: 3, erosion: 2, pest: 2 } },
  soil: { label: "Better soil", icon: "🌱", w: { profit: 4, risk: 3, water: 3, soil: 9, erosion: 5, pest: 5 } },
  safe: { label: "Low risk", icon: "🛡️", w: { profit: 4, risk: 9, water: 4, soil: 3, erosion: 2, pest: 3 } },
};
const WATER = { rain: ["🌧️", "Rain only"], tank: ["🚰", "Tank or canal"], well: ["⛲", "Well"] };
const money = (v) => `Rs ${Math.round(v / 1000).toLocaleString()},000`;

export default function Simple() {
  const params = new URLSearchParams(location.search);
  const [base, error] = useData(["/data/crops.json", "/geo/districts.json"]);
  const [place, setPlace] = useState(params.get("district") ? { id: params.get("district"), label: params.get("district") } : null);
  const [water, setWater] = useState("tank");
  const [goal, setGoal] = useState("income");
  const [shown, setShown] = useState(params.get("show") === "1");
  const [saved, setSaved] = useState(null);
  const [packData] = useData(place ? [`/data/packs/${place.id}.json`] : []);
  const pack = place && packData?.[0]?.id === place.id ? packData[0] : null;

  const res = useMemo(() => (shown && pack && base ? planRotations(pack, base[0].crops, pack.typicalRotation, GOALS[goal].w, { waterSource: water, market: true }) : null), [shown, pack, base, water, goal]);
  if (!base) return <Loading error={error} />;
  const geo = base[1];
  const cropName = (id) => res.crops[id]?.name || "Rest the field";

  const choose = async (sim) => {
    await savePlan({ districtId: place.id, areaHa: 1, waterSource: water, rotation: sim.rot, by: "farmer-simple", lat: place.pos?.lat ?? pack.lat, lon: place.pos?.lng ?? pack.lon });
    setSaved(sim);
  };

  return (
    <div className="simple">
      <h1>What should I plant?</h1>

      <section className="s-step">
        <h2><span>1</span> Where is your field?</h2>
        {place ? (
          <div className="s-picked"><b>📍 {pack?.name || place.label}</b><button className="link" onClick={() => { setPlace(null); setShown(false); setSaved(null); }}>Change</button></div>
        ) : (
          <LocationPicker geo={geo} big onPick={(id, pos, label) => { setPlace({ id, pos, label }); setSaved(null); }} />
        )}
      </section>

      <section className="s-step">
        <h2><span>2</span> Where does your water come from?</h2>
        <div className="s-choices three">{Object.entries(WATER).map(([k, [icon, label]]) => (
          <button key={k} className={water === k ? "on" : ""} aria-pressed={water === k} onClick={() => { setWater(k); setSaved(null); }}><i>{icon}</i>{label}</button>))}</div>
      </section>

      <section className="s-step">
        <h2><span>3</span> What do you want most?</h2>
        <div className="s-choices four">{Object.entries(GOALS).map(([k, g]) => (
          <button key={k} className={goal === k ? "on" : ""} aria-pressed={goal === k} onClick={() => { setGoal(k); setSaved(null); }}><i>{g.icon}</i>{g.label}</button>))}</div>
      </section>

      {!shown && <button className="s-go" disabled={!place} onClick={() => setShown(true)}>{place ? "Show my best crops" : "Choose your place first"}</button>}

      {shown && place && !res && <Loading />}
      {res && (
        <section className="s-results">
          {pack.meta.sample
            ? <p className="s-test">Test version: money figures are examples, not real yet.</p>
            : <p className="s-now">Money figures use 2021 farm-gate prices and typical costs. Your own prices and costs may differ.</p>}
          <h2>Best choices for {pack.name}</h2>
          {res.top.map((sim, i) => {
            const more = sim.annualProfit[1] - res.existing.annualProfit[1];
            const legume = ["maha", "yala"].some((s) => res.crops[sim.rot[s]]?.family === "legume");
            const why = goal === "water" && sim.water_mm < res.existing.water_mm ? `Uses about ${Math.round((1 - sim.water_mm / res.existing.water_mm) * 100)} % less water than what most farmers here grow.`
              : goal === "soil" && legume ? "The bean crop feeds the soil, so the next crop needs less urea."
              : more > 5000 ? `About ${money(more)} more per hectare a year than what most farmers here grow.`
              : explain(sim, res.existing, pack, res.crops, { waterSource: water, market: true }).why[0];
            return (
              <article key={i} className={`s-card ${i === 0 ? "best" : ""}`}>
                {i === 0 && <div className="s-badge">Best match</div>}
                <div className="s-seasons">
                  <div><small>Maha (Oct to Mar)</small><b><span className="dot" style={{ background: CROP_COLORS[sim.rot.maha] }} />{cropName(sim.rot.maha)}</b></div>
                  <div className="s-arrow">→</div>
                  <div><small>Yala (Apr to Sep)</small><b><span className="dot" style={{ background: CROP_COLORS[sim.rot.yala] }} />{cropName(sim.rot.yala)}</b></div>
                </div>
                <p className="s-money">{money(sim.annualProfit[0])} to {money(sim.annualProfit[2])} <small>per hectare a year</small></p>
                <p className="s-why">{why}</p>
                {sim.suit !== "pass" && <p className="s-care">⚠️ Needs care: water may run short in some years.</p>}
                {saved === sim
                  ? <p className="s-saved">✓ Saved. Your agriculture officer can now see your plan.</p>
                  : <button className="s-pick" onClick={() => choose(sim)}>I will grow this</button>}
              </article>
            );
          })}
          <p className="s-now">What most farmers here grow now: <b>{cropName(res.existing.rot.maha)} → {cropName(res.existing.rot.yala)}</b>, {money(res.existing.annualProfit[0])} to {money(res.existing.annualProfit[2])} a year.</p>
          <p className="s-foot">This is advice from weather and soil data. Ask your Agricultural Instructor before you decide.</p>
          <Link className="s-adv" to={`/farmer?district=${place.id}`}>More detail and more options →</Link>
        </section>
      )}
    </div>
  );
}
