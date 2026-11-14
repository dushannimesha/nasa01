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

/**
 * Pick a place by GPS or by typing a district, town or village name.
 * onPick(districtId, { lat, lng }, label)
 */
export default function LocationPicker({ geo, onPick, big = false }) {
  const [q, setQ] = useState("");
  const [places, setPlaces] = useState([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const timer = useRef();
  const districts = geo.features.map((f) => f.properties);
  const term = q.trim().toLowerCase();
  const dHits = term.length >= 2 ? districts.filter((d) => d.name.toLowerCase().includes(term)).slice(0, 5) : [];

  // town / village names: Open-Meteo geocoding (free, no key); needs a connection
  useEffect(() => {
    clearTimeout(timer.current);
    if (term.length < 3) { setPlaces([]); return; }
    timer.current = setTimeout(() => {
      fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(term)}&count=8&language=en&countryCode=LK`)
        .then((r) => r.json())
        .then((j) => setPlaces((j.results || []).filter((p) => p.country_code === "LK").map((p) => ({ ...p, district: districtAt(geo, p.latitude, p.longitude) })).filter((p) => p.district).slice(0, 6)))
        .catch(() => setPlaces([]));
    }, 350);
    return () => clearTimeout(timer.current);
  }, [term]);

  const choose = (d, pos, label) => { setQ(""); setPlaces([]); setMsg(""); onPick(d.id, pos, label); };
  const gps = () => {
    if (!navigator.geolocation) { setMsg("This phone or browser cannot give a location. Type your district instead."); return; }
    setBusy(true); setMsg("");
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setBusy(false);
        const d = districtAt(geo, p.coords.latitude, p.coords.longitude);
        if (d) choose(d, { lat: p.coords.latitude, lng: p.coords.longitude }, `My location (${d.name})`);
        else setMsg("Your location is outside Sri Lanka. Type your district instead.");
      },
      (e) => { setBusy(false); setMsg(e.code === 1 ? "Location permission was refused. Allow it, or type your district." : "Could not get a location. Type your district instead."); },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 },
    );
  };

  return (
    <div className={`locpick ${big ? "big" : ""}`}>
      <button type="button" className="btn gps" onClick={gps} disabled={busy}>{busy ? "Finding you…" : "📍 Use my location"}</button>
      <div className="or">or</div>
      <div className="search">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Type your district, town or village" aria-label="Search for a place" autoComplete="off" />
        {(dHits.length > 0 || places.length > 0) && (
          <ul className="suggest">
            {dHits.map((d) => <li key={d.id}><button type="button" onClick={() => choose(d, { lat: d.lat, lng: d.lon }, d.name)}><b>{d.name}</b> district</button></li>)}
            {places.map((p) => <li key={p.id}><button type="button" onClick={() => choose(p.district, { lat: p.latitude, lng: p.longitude }, `${p.name} (${p.district.name})`)}><b>{p.name}</b> · {p.district.name} district</button></li>)}
          </ul>
        )}
      </div>
      {msg && <p className="locmsg">{msg}</p>}
    </div>
  );
}
