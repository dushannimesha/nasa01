// Reads key.txt (repo root) and writes web/.env.local with the Firebase web config.
// Values are never printed. Usage: node scripts/make_env.mjs
import fs from "node:fs";

const src = fs.existsSync("key.txt") ? "key.txt" : "keys.txt";
const map = {
  apiKey: "VITE_FIREBASE_API_KEY", authDomain: "VITE_FIREBASE_AUTH_DOMAIN", projectId: "VITE_FIREBASE_PROJECT_ID",
  storageBucket: "VITE_FIREBASE_STORAGE_BUCKET", messagingSenderId: "VITE_FIREBASE_MESSAGING_SENDER_ID", appId: "VITE_FIREBASE_APP_ID",
  FIREBASE_API_KEY: "VITE_FIREBASE_API_KEY", FIREBASE_AUTH_DOMAIN: "VITE_FIREBASE_AUTH_DOMAIN", FIREBASE_PROJECT_ID: "VITE_FIREBASE_PROJECT_ID", FIREBASE_APP_ID: "VITE_FIREBASE_APP_ID",
};
const out = [];
for (const line of fs.readFileSync(src, "utf8").split(/\r?\n/)) {
  const m = line.match(/^\s*([A-Za-z_]+)\s*[:=]\s*["']?([^"',\s]+)["']?\s*,?\s*$/);
  if (m && map[m[1]]) out.push(`${map[m[1]]}=${m[2]}`);
}
fs.writeFileSync("web/.env.local", out.join("\n") + "\n");
console.log("wrote web/.env.local with", out.map((l) => l.split("=")[0]).join(", "));
