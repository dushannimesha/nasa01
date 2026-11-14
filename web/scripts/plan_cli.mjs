// Command-line bridge to the ranking engine, used by the Python API so the API, the web app and the bot share
// one implementation. Reads one JSON request on stdin, writes one JSON answer on stdout.
// Request: { "district": "anuradhapura", "water": "tank", "weights": {...} | "goal": "income",
//            "current": {"maha": "paddy", "yala": "fallow"}, "areaHa": 1, "market": true }
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { planRotations, explain, rotName } from "../src/lib/model.js";

const DATA = path.join(path.dirname(fileURLToPath(import.meta.url)), "../public/data");
const GOALS = {
  balanced: { profit: 7, risk: 5, water: 5, soil: 5, erosion: 2, pest: 3 },
  income: { profit: 9, risk: 4, water: 2, soil: 2, erosion: 1, pest: 2 },
  water: { profit: 4, risk: 4, water: 9, soil: 3, erosion: 2, pest: 2 },
  soil: { profit: 4, risk: 3, water: 3, soil: 9, erosion: 5, pest: 5 },
  safe: { profit: 4, risk: 9, water: 4, soil: 3, erosion: 2, pest: 3 },
};
try {
  const req = JSON.parse(fs.readFileSync(0, "utf8") || "{}");
  if (!/^[a-z-]+$/.test(req.district || "")) throw new Error("unknown district");
  const pack = JSON.parse(fs.readFileSync(path.join(DATA, "packs", `${req.district}.json`), "utf8"));
  const { crops } = JSON.parse(fs.readFileSync(path.join(DATA, "crops.json"), "utf8"));
  const water = ["rain", "tank", "well"].includes(req.water) ? req.water : "tank";
  const weights = req.weights || GOALS[req.goal] || GOALS.balanced;
  const current = req.current || pack.typicalRotation;
  const o = { waterSource: water, market: req.market !== false };
  const res = planRotations(pack, crops, current, weights, o);
  const area = Number(req.areaHa) || 1;
  const card = (s) => ({
    rotation: s.rot, name: rotName(s.rot, res.crops), suitability: s.suit, score: +s.score.toFixed(3), rank: s.rank,
    incomePerYear: s.annualProfit.map((v) => Math.round(v * area)), waterMm: Math.round(s.water_mm), soilNitrogenChange: Math.round(s.dN),
    explanation: explain(s, res.existing, pack, res.crops, o),
  });
  process.stdout.write(JSON.stringify({ district: pack.name, water, weights, top: res.top.map(card), current: card(res.existing), ruledOut: res.rejected.length, meta: pack.meta }));
} catch (e) {
  process.stdout.write(JSON.stringify({ error: e.message }));
  process.exitCode = 1;
}
