import { useEffect, useRef, useState } from "react";

// Which district polygon contains a point (ray casting; handles Polygon and MultiPolygon).
function inRing(lon, lat, ring) {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const [xi, yi] = ring[i], [xj, yj] = ring[j];
    if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
  }
  return inside;
}
export function districtAt(geo, lat, lon) {
  for (const f of geo.features) {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    if (polys.some((p) => inRing(lon, lat, p[0]) && !p.slice(1).some((hole) => inRing(lon, lat, hole)))) return f.properties;
  }
  return null;
}

const EN = {
  gps: "📍 Use my location", finding: "Finding you…", or: "or", search: "Type your district, town or village", district: "district",
  myLoc: (d) => `My location (${d})`,
  noGps: "This phone or browser cannot give a location. Type your district instead.",
  outside: "Your location is outside Sri Lanka. Type your district instead.",
  refused: "Location permission was refused. Allow it, or type your district.",
  gpsFail: "Could not get a location. Type your district instead.",
};
const NATIVE = /[඀-෿஀-௿]/; // Sinhala or Tamil letters typed

/**
 * Pick a place by GPS or by typing a district, town or village name.
 * onPick(districtId, { lat, lng }, label, { dname, town?, gps? })
 * Optional t (text) and district(id, englishName) translate the labels; district names can be typed in any of them.
 */
export default function LocationPicker({ geo, onPick, big = false, t = EN, district = (id, en) => en }) {
  const [q, setQ] = useState("");
  const [places, setPlaces] = useState([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const timer = useRef();
  const districts = geo.features.map((f) => f.properties);
  const term = q.trim().toLowerCase();
  const dHits = term.length >= 2 ? districts.filter((d) => d.name.toLowerCase().includes(term) || district(d.id, d.name).includes(q.trim())).slice(0, 5) : [];

  // town / village names: Open-Meteo geocoding (free, no key); needs a connection. Skipped for Sinhala/Tamil input.
  useEffect(() => {
    clearTimeout(timer.current);
    if (term.length < 3 || NATIVE.test(term)) { setPlaces([]); return; }
    timer.current = setTimeout(() => {
      fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(term)}&count=8&language=en&countryCode=LK`)
        .then((r) => r.json())
        .then((j) => setPlaces((j.results || []).filter((p) => p.country_code === "LK").map((p) => ({ ...p, district: districtAt(geo, p.latitude, p.longitude) })).filter((p) => p.district).slice(0, 6)))
        .catch(() => setPlaces([]));
    }, 350);
    return () => clearTimeout(timer.current);
  }, [term]);

  const choose = (d, pos, label, info) => { setQ(""); setPlaces([]); setMsg(""); onPick(d.id, pos, label, { dname: d.name, ...info }); };
  const gps = () => {
    if (!navigator.geolocation) { setMsg(t.noGps); return; }
    setBusy(true); setMsg("");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setBusy(false);
        const d = districtAt(geo, p.coords.latitude, p.coords.longitude);
        if (d) choose(d, { lat: p.coords.latitude, lng: p.coords.longitude }, `My location (${d.name})`, { gps: true });
        else setMsg(t.outside);
      },
      (e) => { setBusy(false); setMsg(e.code === 1 ? t.refused : t.gpsFail); },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 },
    );
  };

  return (
    <div className={`locpick ${big ? "big" : ""}`}>
      <button type="button" className="btn gps" onClick={gps} disabled={busy}>{busy ? t.finding : t.gps}</button>
      <div className="or">{t.or}</div>
      <div className="search">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={t.search} aria-label={t.search} autoComplete="off" />
        {(dHits.length > 0 || places.length > 0) && (
          <ul className="suggest">
            {dHits.map((d) => <li key={d.id}><button type="button" onClick={() => choose(d, { lat: d.lat, lng: d.lon }, d.name)}><b>{district(d.id, d.name)}</b> {t.district}</button></li>)}
            {places.map((p) => <li key={p.id}><button type="button" onClick={() => choose(p.district, { lat: p.latitude, lng: p.longitude }, `${p.name} (${p.district.name})`, { town: p.name })}><b>{p.name}</b> · {district(p.district.id, p.district.name)} {t.district}</button></li>)}
          </ul>
        )}
      </div>
      {msg && <p className="locmsg">{msg}</p>}
    </div>
  );
}
