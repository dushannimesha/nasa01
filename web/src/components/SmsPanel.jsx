import { useState } from "react";
import { MessageSquareText, Send, CloudSunRain, CircleCheck, Clock, CircleX } from "lucide-react";
import { addFarmer, requestCampaign, useCampaigns, useOutbox } from "../lib/store.js";
import { Card } from "./ui.jsx";

const LANG = { en: "English", si: "Sinhala", ta: "Tamil" };
const GOAL = { income: "More income", water: "Save water", soil: "Better soil", safe: "Low risk" };
const STATUS = { sent: ["Sent", CircleCheck, "good"], demo: ["Generated (no SMS gateway)", Clock, "info"], failed: ["Failed", CircleX, "critical"] };

// Sri Lankan mobile number in any common form -> +947XXXXXXXX (same rule as channels/sms_gateway.py)
export function normalizePhone(raw) {
  let d = String(raw || "").replace(/\D/g, "");
  if (d.startsWith("0094")) d = d.slice(2);
  if (d.startsWith("94") && d.length === 11) d = d.slice(2);
  if (d.startsWith("0") && d.length === 10) d = d.slice(1);
  return d.length === 9 && d.startsWith("7") ? `+94${d}` : null;
}

export default function SmsPanel({ districts, cropList }) {
  const blank = { phone: "", district: "anuradhapura", water: "tank", goal: "income", lang: "si", crop: "", sowDate: "", agreed: false };
  const [f, setF] = useState(blank);
  const [msg, setMsg] = useState(null);
  const [target, setTarget] = useState("all");
  const [sendMsg, setSendMsg] = useState(null);
  const [outbox, outErr] = useOutbox();
  const [campaigns] = useCampaigns();
  const dName = Object.fromEntries(districts.map((d) => [d.id, d.name]));
  const upd = (k) => (e) => setF((s) => ({ ...s, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value }));

  const register = async (e) => {
    e.preventDefault();
    const phone = normalizePhone(f.phone);
    if (!phone) return setMsg(["critical", "Enter a Sri Lankan mobile number, for example 0771234567."]);
    if (!f.agreed) return setMsg(["critical", "Tick the box only after the farmer has agreed to receive messages."]);
    const doc = { phone, district: f.district, water: f.water, goal: f.goal, lang: f.lang, ...(f.crop && f.sowDate ? { crop: f.crop, sowDate: f.sowDate } : {}) };
    try {
      const r = await addFarmer(doc);
      setMsg(["good", `${r === "queued" ? "Saved on this device; it will sync when online." : "Registered."} ${phone.slice(0, 5)}***${phone.slice(-4)} will get advice in ${LANG[f.lang]}. The number cannot be read back from this page.`]);
      setF({ ...blank, district: f.district, lang: f.lang });
    } catch (err) {
      setMsg(["critical", /permission/i.test(err.code || err.message) ? "The register refused the entry: the database rules for text messages are not published yet." : `Could not save: ${err.message}`]);
    }
  };
  const send = async (type) => {
    try {
      await requestCampaign(type, type === "season" ? target : "all");
      setSendMsg(["good", type === "season" ? `Season advice requested for ${target === "all" ? "all districts" : dName[target]}. Messages appear in the outbox below as they go out.` : "Weather check requested. Alerts go only to farmers with a crop in the field and a risk this week."]);
    } catch (err) {
      setSendMsg(["critical", /permission/i.test(err.code || err.message) ? "The send request was refused: the database rules for text messages are not published yet." : `Could not request: ${err.message}`]);
    }
  };
  const last = campaigns[0];

  return (
    <>
      <h2 className="section"><MessageSquareText size={20} aria-hidden="true" /> Text messages for farmers without a smartphone</h2>
      <div className="grid one-two">
        <Card title="Register a farmer for text messages" sub="Advice arrives by SMS in the farmer's language. With no SMS gateway connected, it goes to the Telegram bot for farmers who send JOIN and their number there.">
          <form onSubmit={register} className="stack">
            <label className="field"><span>Mobile number</span><input value={f.phone} onChange={upd("phone")} inputMode="tel" placeholder="07X XXX XXXX" autoComplete="off" /></label>
            <div className="row gap wrap">
              <label className="field"><span>District</span><select value={f.district} onChange={upd("district")}>{districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
              <label className="field"><span>Language</span><select value={f.lang} onChange={upd("lang")}>{Object.entries(LANG).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            </div>
            <div className="row gap wrap">
              <label className="field"><span>Water source</span><select value={f.water} onChange={upd("water")}><option value="rain">Rain only</option><option value="tank">Tank / canal</option><option value="well">Agro-well</option></select></label>
              <label className="field"><span>Goal</span><select value={f.goal} onChange={upd("goal")}>{Object.entries(GOAL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            </div>
            <div className="row gap wrap">
              <label className="field"><span>Crop in the field now (for weather alerts)</span><select value={f.crop} onChange={upd("crop")}><option value="">None yet</option>{cropList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
              <label className="field"><span>Sowing date</span><input type="date" value={f.sowDate} onChange={upd("sowDate")} disabled={!f.crop} /></label>
            </div>
            <label className="check"><input type="checkbox" checked={f.agreed} onChange={upd("agreed")} /> The farmer agreed to receive Field Shift messages on this number</label>
            <button className="btn">Register for messages</button>
            {msg && <div className={`notice ${msg[0]}`}>{msg[1]}</div>}
          </form>
        </Card>
        <Card title="Send" sub="The Field Shift sender writes one message per farmer from the same advice as the app and the bot, then sends it.">
          <div className="row gap wrap end">
            <label className="field"><span>Season advice for</span><select value={target} onChange={(e) => setTarget(e.target.value)}><option value="all">All districts</option>{districts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
            <button className="btn" onClick={() => send("season")}><Send size={16} aria-hidden="true" /> Send season advice</button>
            <button className="btn ghost" onClick={() => send("alerts")}><CloudSunRain size={16} aria-hidden="true" /> Check weather and send alerts</button>
          </div>
          {sendMsg && <div className={`notice ${sendMsg[0]}`}>{sendMsg[1]}</div>}
          {last && <p className="note">Last request: {last.type === "alerts" ? "weather alerts" : "season advice"}, {last.status}{last.status === "done" ? `: ${last.farmers} farmers, ${last.sent} sent, ${last.demo} generated only, ${last.failed} failed` : last.status === "new" ? " (waiting for the sender)" : ""}.</p>}
          <h4>Outbox</h4>
          {outErr ? <p className="note">Outbox not available yet ({outErr}).</p> : outbox.length === 0 ? <p className="note">No messages yet.</p> : (
            <div className="outbox">{outbox.map((o) => { const [label, Icon, tone] = STATUS[o.status] || STATUS.demo; return (
              <article key={o.id} className="sms">
                <header><b>{o.to}</b><span>{dName[o.district] || o.district} · {LANG[o.lang] || o.lang} · {o.kind} · {o.segments} part{o.segments > 1 ? "s" : ""}</span></header>
                <p lang={o.lang}>{o.text}</p>
                <footer className={`lvl ${tone}`}><Icon size={14} aria-hidden="true" /> {label}{o.status === "sent" && o.detail ? ` via ${o.detail}` : ""} · {(o.createdAt || "").slice(0, 16).replace("T", " ")}</footer>
              </article>); })}</div>)}
        </Card>
      </div>
    </>
  );
}
