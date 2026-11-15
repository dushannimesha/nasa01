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
  const owner = await currentUid();
  const doc = { ...plan, ...(owner ? { owner } : {}), createdAt: new Date().toISOString() };
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

// ---- Text messages for farmers without a smartphone ----
// "farmers" (phone numbers) can be added from the website but never read back; only the sender script reads it.
// "campaigns" are send requests the sender script picks up; "outbox" is what it sent, with numbers masked.
async function addTo(collection, doc) {
  const f = await firestore().catch(() => null);
  if (!f) throw new Error("The shared register is not configured on this site.");
  const write = f.m.addDoc(f.m.collection(f.db, collection), { ...doc, createdAt: new Date().toISOString() });
  // offline: the write waits in the local queue and syncs later
  const timeout = new Promise((ok) => setTimeout(() => ok("queued"), 8000));
  const r = await Promise.race([write.then(() => "saved"), timeout]);
  return r;
}
export const addFarmer = (farmer) => addTo("farmers", { ...farmer, consent: true });
export const requestCampaign = (type, district = "all") => addTo("campaigns", { type, district, status: "new" });

function useLive(collection, n) {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState(null);
  useEffect(() => {
    let unsub = () => {};
    firestore().then((f) => {
      if (!f) { setErr("not configured"); return; }
      const q = f.m.query(f.m.collection(f.db, collection), f.m.orderBy("createdAt", "desc"), f.m.limit(n));
      unsub = f.m.onSnapshot(q, (snap) => setRows(snap.docs.map((d) => ({ id: d.id, ...d.data() }))), (e) => setErr(e.code || e.message));
    });
    return () => unsub();
  }, [collection, n]);
  return [rows, err];
}
export const useOutbox = () => useLive("outbox", 60);
export const useCampaigns = () => useLive("campaigns", 5);

// ---- Farmer login by phone (OTP) ----
// The API's public address is kept in Firestore (config/api), written by the server when it starts, so the site
// needs no rebuild when the address changes. No address = login is hidden and the app works as before.
export function useApiUrl() {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let unsub = () => {};
    firestore().then((f) => {
      if (!f) return;
      unsub = f.m.onSnapshot(f.m.doc(f.db, "config", "api"), (d) => setUrl(d.exists() && d.data().url ? d.data().url.replace(/\/$/, "") : null), () => setUrl(null));
    });
    return () => unsub();
  }, []);
  return url;
}

let authMod = null;
async function fbAuth() {
  const f = await firestore();
  if (!f) return null;
  if (!authMod) authMod = (async () => { const m = await import("firebase/auth"); const { getApp } = await import("firebase/app"); return { m, auth: m.getAuth(getApp()) }; })();
  return authMod;
}

export function useUser() {
  const [user, setUser] = useState(null);
  useEffect(() => {
    let unsub = () => {};
    fbAuth().then((a) => { if (a) unsub = a.m.onAuthStateChanged(a.auth, (u) => setUser(u ? { uid: u.uid } : null)); });
    return () => unsub();
  }, []);
  return user;
}

async function post(api, path, body) {
  const r = await fetch(`${api}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.detail || "The login service did not answer. Try again in a minute.");
  return j;
}
export const sendLoginCode = (api, phone, lang = "en") => post(api, "/api/otp/send", { phone, lang });
export async function verifyLoginCode(api, reqid, code) {
  const { token } = await post(api, "/api/otp/verify", { reqid, code });
  const a = await fbAuth();
  await a.m.signInWithCustomToken(a.auth, token);
}
export async function logOut() { const a = await fbAuth(); if (a) await a.m.signOut(a.auth); }
export async function currentUid() { const a = await fbAuth().catch(() => null); return a?.auth.currentUser?.uid || null; }

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
