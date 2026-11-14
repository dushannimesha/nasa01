// Shrinks the downloaded boundary files into small GeoJSON for the web app.
// Usage: node scripts/prep_geo.mjs
import fs from "node:fs";

const round = (d) => (c) => (typeof c[0] === "number" ? [+c[0].toFixed(d), +c[1].toFixed(d)] : c.map(round(d)));
const slug = (s) => s.toLowerCase().replace(/ district$/, "").replace(/[^a-z]+/g, "-").replace(/^-|-$/g, "");

function bbox(coords, b = [180, 90, -180, -90]) {
  if (typeof coords[0] === "number") {
    b[0] = Math.min(b[0], coords[0]); b[1] = Math.min(b[1], coords[1]);
    b[2] = Math.max(b[2], coords[0]); b[3] = Math.max(b[3], coords[1]);
  } else coords.forEach((c) => bbox(c, b));
  return b;
}

fs.mkdirSync("web/public/geo", { recursive: true });

const lka = JSON.parse(fs.readFileSync("data/raw/geo_lka/lka_adm2_simplified.geojson", "utf8"));
const districts = {
  type: "FeatureCollection",
  features: lka.features.map((f) => {
    const name = f.properties.shapeName.replace(/ District$/i, "");
    const b = bbox(f.geometry.coordinates);
    return {
      type: "Feature",
      properties: { id: slug(name), name, lat: +((b[1] + b[3]) / 2).toFixed(3), lon: +((b[0] + b[2]) / 2).toFixed(3) },
      geometry: { type: f.geometry.type, coordinates: round(3)(f.geometry.coordinates) },
    };
  }),
};
fs.writeFileSync("web/public/geo/districts.json", JSON.stringify(districts));
console.log(districts.features.map((f) => `${f.properties.id} (${f.properties.lat},${f.properties.lon})`).join("\n"));

const world = JSON.parse(fs.readFileSync("data/raw/geo_world/ne_110m_countries.geojson", "utf8"));
const out = {
  type: "FeatureCollection",
  features: world.features.map((f) => ({
    type: "Feature",
    properties: { iso3: f.properties.ADM0_A3, name: f.properties.NAME },
    geometry: { type: f.geometry.type, coordinates: round(1)(f.geometry.coordinates) },
  })),
};
fs.writeFileSync("web/public/geo/world.json", JSON.stringify(out));
for (const f of ["districts.json", "world.json"]) console.log(f, fs.statSync("web/public/geo/" + f).size, "bytes");
