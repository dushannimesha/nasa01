import { useMemo, useState } from "react";
import { MapContainer, TileLayer, GeoJSON, Marker } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { ramp, SEQ, DIV } from "../lib/data.js";

// NASA GIBS layers (names, zoom sets and date coverage checked against the GIBS WMTS capabilities list).
export const GIBS = [
  { id: "none", name: "No NASA overlay" },
  { id: "IMERG_Precipitation_Rate", name: "Rainfall (GPM IMERG)", tms: "GoogleMapsCompatible_Level6", z: 6, ext: "png" },
  { id: "SMAP_L4_Analyzed_Root_Zone_Soil_Moisture", name: "Root-zone soil moisture (SMAP L4)", tms: "GoogleMapsCompatible_Level6", z: 6, ext: "png" },
  { id: "MODIS_Terra_L3_NDVI_16Day", name: "Vegetation greenness NDVI (MODIS)", tms: "GoogleMapsCompatible_Level9", z: 9, ext: "png" },
  { id: "MODIS_Terra_Land_Surface_Temp_Day", name: "Land surface temperature (MODIS)", tms: "GoogleMapsCompatible_Level7", z: 7, ext: "png" },
  { id: "MODIS_Terra_CorrectedReflectance_TrueColor", name: "True colour (MODIS Terra)", tms: "GoogleMapsCompatible_Level9", z: 9, ext: "jpg" },
];
const START = Date.UTC(2020, 9, 1); // 1 Oct 2020, start of Maha 2020/21
const DAYS = 364;
const isoDay = (i) => new Date(START + i * 86400000).toISOString().slice(0, 10);

const pin = L.divIcon({ className: "", html: '<div class="pin"></div>', iconSize: [18, 18], iconAnchor: [9, 9] });

export function Legend({ title, min, max, diverging, format = (v) => v }) {
  const stops = diverging ? DIV : SEQ;
  return (
    <div className="legend">
      <div className="legend-title">{title}</div>
      <div className="legend-bar" style={{ background: `linear-gradient(to right, ${stops.join(",")})` }} />
      <div className="legend-ends"><span>{format(min)}</span>{diverging && <span>0</span>}<span>{format(max)}</span></div>
    </div>
  );
}

/**
 * values: { districtId: number } to colour the districts (optional)
 * diverging: colour around zero (red below, blue above)
 */
export default function DistrictMap({ geo, values, diverging, selected, onSelect, marker, height = 460, center = [7.85, 80.7], zoom = 7, legendTitle, format, overlayControls = true, tooltip }) {
  const [layerId, setLayerId] = useState("none");
  const [day, setDay] = useState(45);
  const layer = GIBS.find((g) => g.id === layerId);

  const [min, max] = useMemo(() => {
    const v = Object.values(values || {}).filter(Number.isFinite);
    if (!v.length) return [0, 1];
    if (diverging) { const m = Math.max(...v.map(Math.abs)) || 1; return [-m, m]; }
    return [Math.min(...v), Math.max(...v)];
  }, [values, diverging]);

  const style = (f) => {
    const id = f.properties.id ?? f.properties.iso3;
    const v = values?.[id];
    const has = Number.isFinite(v);
    return {
      fillColor: has ? ramp(diverging ? DIV : SEQ, max === min ? 0.5 : (v - min) / (max - min)) : "#e1e0d9",
      fillOpacity: values ? (layerId === "none" ? (has ? 0.85 : 0.35) : 0.15) : 0.08,
      color: id === selected ? "#0b0b0b" : "#ffffff",
      weight: id === selected ? 2.5 : 1,
    };
  };
  const each = (f, lyr) => {
    const id = f.properties.id ?? f.properties.iso3;
    lyr.on("click", (e) => onSelect?.(id, e.latlng));
    lyr.bindTooltip(() => (tooltip ? tooltip(id, f.properties) : f.properties.name), { sticky: true });
  };
  // GeoJSON does not restyle on prop change, so the key forces a redraw when colours or selection change.
  const key = `${selected}|${layerId}|${diverging}|${JSON.stringify(values || {})}`.length + `${selected}${layerId}${min}${max}${Object.values(values || {}).reduce((s, v) => s + (v || 0), 0)}`;

  return (
    <div className="map-wrap">
      <MapContainer center={center} zoom={zoom} style={{ height }} scrollWheelZoom worldCopyJump>
        <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='&copy; OpenStreetMap contributors' />
        {layer?.tms && (
          <TileLayer
            key={layer.id + day}
            url={`https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/${layer.id}/default/${isoDay(day)}/${layer.tms}/{z}/{y}/{x}.${layer.ext}`}
            maxNativeZoom={layer.z} opacity={0.75} attribution="NASA GIBS / EOSDIS"
          />
        )}
        {geo && <GeoJSON key={key} data={geo} style={style} onEachFeature={each} />}
        {marker && <Marker position={marker} icon={pin} />}
      </MapContainer>
      {values && layerId === "none" && legendTitle && <Legend title={legendTitle} min={min} max={max} diverging={diverging} format={format} />}
      {overlayControls && (
        <div className="map-controls">
          <label>
            <span>NASA satellite layer</span>
            <select value={layerId} onChange={(e) => setLayerId(e.target.value)}>
              {GIBS.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
            </select>
          </label>
          {layer?.tms && (
            <label className="grow">
              <span>Date: {isoDay(day)} ({day < 182 ? "Maha 2020/21" : "Yala 2021"})</span>
              <input type="range" min="0" max={DAYS} step={layer.id.includes("16Day") ? 16 : 1} value={day} onChange={(e) => setDay(+e.target.value)} />
            </label>
          )}
        </div>
      )}
    </div>
  );
}
