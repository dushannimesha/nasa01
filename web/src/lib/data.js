import { useEffect, useState } from "react";

const cache = new Map();
export function loadJson(path) {
  if (!cache.has(path)) cache.set(path, fetch(path).then((r) => { if (!r.ok) throw new Error(`${path}: ${r.status}`); return r.json(); }));
  return cache.get(path);
}

// Loads several JSON files; returns [data, error]. data is null until all have arrived.
export function useData(paths) {
  const key = paths.join("|");
  const [state, setState] = useState([null, null]);
  useEffect(() => {
    let live = true;
    setState([null, null]);
    Promise.all(paths.map(loadJson)).then((d) => live && setState([d, null])).catch((e) => live && setState([null, e]));
    return () => { live = false; };
  }, [key]);
  return state;
}

export const CROP_COLORS = { paddy: "#2a78d6", maize: "#eb6834", greengram: "#1baf7a", cowpea: "#eda100", bigonion: "#e87ba4", chilli: "#008300", fallow: "#898781" };
export const INK = { primary: "#0b0b0b", secondary: "#52514e", muted: "#898781", grid: "#e1e0d9", axis: "#c3c2b7", surface: "#fcfcfb" };
export const SEQ = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
export const DIV = ["#d03b3b", "#e88f8f", "#f0efec", "#86b6ef", "#2a78d6"]; // red (deficit) .. gray .. blue (surplus)
export const STATUS = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" };

const hex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
export function ramp(stops, t) {
  if (!Number.isFinite(t)) return "#e1e0d9";
  const x = Math.max(0, Math.min(1, t)) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(x)), f = x - i;
  const a = hex(stops[i]), b = hex(stops[i + 1]);
  return `rgb(${a.map((v, k) => Math.round(v + (b[k] - v) * f)).join(",")})`;
}

export const fmt = {
  int: (v) => Math.round(v).toLocaleString(),
  t: (v) => (Math.abs(v) >= 1e6 ? `${(v / 1e6).toFixed(2)} M t` : Math.abs(v) >= 1e3 ? `${(v / 1e3).toFixed(0)}k t` : `${Math.round(v)} t`),
  pct: (v, d = 0) => `${v > 0 ? "+" : ""}${v.toFixed(d)} %`,
  lkrK: (v) => `LKR ${Math.round(v / 1000).toLocaleString()}k`,
};
