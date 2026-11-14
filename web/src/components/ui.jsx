import { CircleAlert, CircleCheck, CircleX, Info, TriangleAlert } from "lucide-react";
import { CROP_COLORS } from "../lib/data.js";

export function SampleBanner({ meta }) {
  if (!meta?.sample) {
    if (!meta?.real) return meta?.dataAsOf ? <div className="asof">Data as of {meta.dataAsOf}</div> : null;
    return (
      <details className="sources">
        <summary>Data sources and assumptions · updated {meta.dataAsOf}</summary>
        <p><b>From data:</b> {meta.real.join("; ")}.</p>
        <p><b>Assumed (check locally):</b></p>
        <ul>{meta.assumptions.map((a, i) => <li key={i}>{a}</li>)}</ul>
      </details>
    );
  }
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

// Severity icons (Lucide line icons), shared by status badges and advice lists
export const LEVEL_ICON = { good: CircleCheck, info: Info, warning: TriangleAlert, serious: CircleAlert, critical: CircleX };
export const LevelIcon = ({ level, size = 18 }) => { const I = LEVEL_ICON[level] || Info; return <I className="lvl-icon" size={size} strokeWidth={2} aria-hidden="true" />; };

const SUIT = { pass: ["Suitable", "good"], warn: ["Needs care", "warning"], fail: ["Not suitable", "critical"] };
export function Suit({ level }) {
  const [text, cls] = SUIT[level] || SUIT.pass;
  return <span className={`status ${cls}`}><LevelIcon level={cls} size={16} />{text}</span>;
}
