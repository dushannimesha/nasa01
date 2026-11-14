// Plan storage. Uses Firestore when the Firebase config is present (web/.env.local),
// otherwise the browser's local storage, so the app runs with no backend at all.
// Firestore offline persistence queues writes made without a connection.
import { useEffect, useState } from "react";

const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};
export const hasFirebase = Boolean(cfg.apiKey && cfg.projectId);

let fs = null;
async function firestore() {
  if (!hasFirebase) return null;
  if (!fs) {
    fs = (async () => {
      const { initializeApp } = await import("firebase/app");
      const m = await import("firebase/firestore");
      const app = initializeApp(cfg);
      const db = m.initializeFirestore(app, { localCache: m.persistentLocalCache({ tabManager: m.persistentMultipleTabManager() }) });
      return { db, m };
    })();
  }
  return fs;
}

const LS = "fieldshift.plans";
const readLocal = () => { try { return JSON.parse(localStorage.getItem(LS) || "[]"); } catch { return []; } };
const listeners = new Set();
let fsBroken = false; // set when the register cannot be read (rules, no database); plans then stay on the device

export async function savePlan(plan) {
  const doc = { ...plan, createdAt: new Date().toISOString() };
  const f = fsBroken ? null : await firestore().catch(() => null);
  if (f) {
    // not awaited on purpose: offline writes resolve only after sync, the local cache updates at once
    f.m.addDoc(f.m.collection(f.db, "plans"), doc).catch((e) => console.warn("plan not synced yet:", e.message));
    return { where: "firestore" };
  }
  try { localStorage.setItem(LS, JSON.stringify([doc, ...readLocal()])); } catch { /* storage blocked */ }
  listeners.forEach((fn) => fn());
  return { where: "local" };
}

// Live list of registered plans (all districts, newest first).
export function usePlans() {
  const [plans, setPlans] = useState(hasFirebase ? [] : readLocal());
  const [source, setSource] = useState(hasFirebase ? "firestore" : "local");
  useEffect(() => {
    let unsub = () => {};
    const local = () => setPlans(readLocal());
    firestore().then((f) => {
      if (!f) { listeners.add(local); return; }
      const q = f.m.query(f.m.collection(f.db, "plans"), f.m.orderBy("createdAt", "desc"), f.m.limit(500));
      unsub = f.m.onSnapshot(q, (snap) => setPlans(snap.docs.map((d) => ({ id: d.id, ...d.data() }))), (e) => {
        console.warn("Firestore unavailable, using local storage:", e.message);
        fsBroken = true; setSource("local"); local(); listeners.add(local);
      });
    }).catch(() => { setSource("local"); local(); listeners.add(local); });
    return () => { unsub(); listeners.delete(local); };
  }, []);
  return { plans, source };
}

// Sum of registered area per district, season and crop; feeds the market loop and the gov coverage figure.
export function aggregatePlans(plans) {
  const agg = {};
  for (const p of plans) {
    for (const season of ["maha", "yala"]) {
      const crop = p.rotation?.[season];
      if (!crop || crop === "fallow") continue;
      const k = `${p.districtId}|${season}|${crop}`;
      agg[k] = (agg[k] || 0) + (Number(p.areaHa) || 0);
    }
  }
  return agg;
}
