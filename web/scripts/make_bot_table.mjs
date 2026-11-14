// Pre-computes the answers the text channel (Telegram / SMS) gives, using the same engine as the web app,
// so both channels always agree. Output: public/data/bot_table.json
// Usage: node scripts/make_bot_table.mjs   (run after the data packs change)
import fs from "node:fs";
import { planRotations, explain, rotName } from "../src/lib/model.js";

const D = "public/data";
const { crops } = JSON.parse(fs.readFileSync(`${D}/crops.json`, "utf8"));
export const PRIORITIES = {
  income: { profit: 9, risk: 4, water: 2, soil: 2, erosion: 1, pest: 2 },
  water: { profit: 4, risk: 4, water: 9, soil: 3, erosion: 2, pest: 2 },
  soil: { profit: 4, risk: 3, water: 3, soil: 9, erosion: 5, pest: 5 },
  safe: { profit: 4, risk: 9, water: 4, soil: 3, erosion: 2, pest: 3 },
};
const k = (v) => `${Math.round(v / 1000)}k`;
const table = {};
let meta;
for (const file of fs.readdirSync(`${D}/packs`)) {
  const pack = JSON.parse(fs.readFileSync(`${D}/packs/${file}`, "utf8"));
  meta = pack.meta;
  const entry = (table[pack.id] = { name: pack.name, answers: {} });
  for (const water of ["rain", "tank", "well"]) {
    for (const [prio, weights] of Object.entries(PRIORITIES)) {
      const o = { waterSource: water, market: true };
      const res = planRotations(pack, crops, pack.typicalRotation, weights, o);
      entry.answers[`${water}|${prio}`] = {
        current: rotName(res.existing.rot, res.crops),
        currentIncome: `${k(res.existing.annualProfit[0])}-${k(res.existing.annualProfit[2])}`,
        top: res.top.map((s) => ({
          name: rotName(s.rot, res.crops), rot: s.rot, suit: s.suit,
          income: `${k(s.annualProfit[0])}-${k(s.annualProfit[2])}`, water_mm: Math.round(s.water_mm),
          why: explain(s, res.existing, pack, res.crops, o).why[0],
        })),
      };
    }
  }
}
fs.writeFileSync(`${D}/bot_table.json`, JSON.stringify({ meta, crops: crops.map(({ id, name, days, stages, fert }) => ({ id, name, days, stages, fert })), districts: table }));
console.log("bot_table.json:", Object.keys(table).length, "districts x 12 answers");
