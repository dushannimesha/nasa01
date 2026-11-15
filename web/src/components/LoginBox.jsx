import { useState } from "react";
import { KeyRound, LogOut, Smartphone } from "lucide-react";
import { logOut, sendLoginCode, useApiUrl, useUser, verifyLoginCode } from "../lib/store.js";

const masked = (p) => (p ? `${p.slice(0, 5)}***${p.slice(-4)}` : "");

// Optional phone login on the farmer page. Hidden until the login service has a public address (config/api).
export default function LoginBox({ t, lang = "en" }) {
  const api = useApiUrl();
  const user = useUser();
  const [open, setOpen] = useState(false);
  const [phone, setPhone] = useState("");
  const [req, setReq] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!api && !user) return null;

  if (user) return (
    <div className="s-login done"><Smartphone size={18} aria-hidden="true" /><span>{t.loggedAs(masked(user.uid))}</span>
      <button className="link" onClick={() => logOut()}><LogOut size={16} aria-hidden="true" /> {t.logout}</button></div>
  );
  if (!open) return <button className="s-login-open" onClick={() => setOpen(true)}><Smartphone size={18} aria-hidden="true" /> {t.login}</button>;

  const run = (fn) => async (e) => {
    e.preventDefault(); setBusy(true); setErr("");
    try { await fn(); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <section className="s-step s-login">
      <h2><KeyRound size={20} aria-hidden="true" /> {t.login}</h2>
      <p className="s-why">{t.loginWhy}</p>
      {!req ? (
        <form onSubmit={run(async () => setReq(await sendLoginCode(api, phone, lang)))} className="s-login-row">
          <label htmlFor="login-phone" className="sr">{t.phone}</label>
          <input id="login-phone" value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" autoComplete="tel" placeholder="07X XXX XXXX" />
          <button className="s-pick" disabled={busy || phone.replace(/\D/g, "").length < 9}>{t.sendCode}</button>
        </form>
      ) : (
        <form onSubmit={run(() => verifyLoginCode(api, req.reqid, code))} className="s-login-row">
          <p className="s-now">{t.sentTo(req.phone)}</p>
          <label htmlFor="login-code" className="sr">{t.code}</label>
          <input id="login-code" value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} inputMode="numeric" autoComplete="one-time-code" placeholder={t.code} />
          <button className="s-pick" disabled={busy || code.length < 4}>{t.verify}</button>
        </form>
      )}
      {err && <p className="s-care" role="alert">{err}</p>}
    </section>
  );
}
