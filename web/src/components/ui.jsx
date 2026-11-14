import { CROP_COLORS } from "../lib/data.js";

export function SampleBanner({ meta }) {
  if (!meta?.sample) return meta?.dataAsOf ? <div className="asof">Data as of {meta.dataAsOf}</div> : null;
  if (meta.real?.length) return <div className="sample" role="note"><b>PARTLY SAMPLE DATA</b> Real so far: {meta.real.join("; ")}. Yields, areas, prices, costs and the 2021 test are still placeholders and must not be quoted.</div>;
  return <div className="sample" role="note"><b>SAMPLE DATA</b> These numbers are placeholders for building the interface. They are not model results and must not be quoted.</div>;
}

export function Tile({ label, value, sub, tone }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className={`tile-value ${tone || ""}`}>{value}</div>
      {sub && <div className="tile-sub">{sub}</div>}
    </div>
  );
}

export function Card({ title, sub, children, className = "" }) {
  return (
    <section className={`card ${className}`}>
      {title && <h3>{title}</h3>}
      {sub && <p className="card-sub">{sub}</p>}
      {children}
    </section>
  );
}

export const CropDot = ({ id }) => <span className="dot" style={{ background: CROP_COLORS[id] || "#898781" }} />;

export function Slider({ label, value, min, max, step = 1, unit = "", onChange, signed }) {
  return (
    <label className="slider">
      <span>{label}<b>{signed && value > 0 ? "+" : ""}{value}{unit}</b></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(+e.target.value)} />
    </label>
  );
}

export const Loading = ({ error }) => <div className="loading">{error ? `Could not load data: ${error.message}` : "Loading…"}</div>;

const SUIT = { pass: ["✓", "Suitable", "good"], warn: ["!", "Needs care", "warning"], fail: ["✕", "Not suitable", "critical"] };
export function Suit({ level }) {
  const [icon, text, cls] = SUIT[level] || SUIT.pass;
  return <span className={`status ${cls}`}><i>{icon}</i>{text}</span>;
}
