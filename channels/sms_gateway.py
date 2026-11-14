"""Where a message actually goes. Chosen by SMS_PROVIDER in key.txt (or the environment):

  telegram (default)  farmers who linked their phone in the Telegram bot (send JOIN 07XXXXXXXX to @agro01bot) get
                      the message there; everyone else is recorded as "demo" (generated, not sent)
  demo                nothing is sent; every message is only recorded in the outbox
  twilio              real SMS. Needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
  notifylk            real SMS through Notify.lk (Sri Lanka). Needs NOTIFYLK_USER_ID, NOTIFYLK_API_KEY, NOTIFYLK_SENDER_ID
                      (request format taken from Notify.lk's public API; test with one number first)

send(phone, text) -> (status, detail)   status: sent | demo | failed. Secrets are never printed or returned.
"""
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINKS = ROOT / "data/channels/telegram_links.json"


def setting(name, default=None):
    if os.environ.get(name):
        return os.environ[name]
    for fname in ("key.txt", "keys.txt"):
        p = ROOT / fname
        if p.exists():
            m = re.search(rf"^\s*{name}\s*[=:]\s*[\"']?([^\"'\r\n]+?)[\"']?\s*$", p.read_text(encoding="utf-8"), re.M)
            if m:
                return m.group(1).strip()
    return default


def normalize_phone(raw):
    """Sri Lankan mobile numbers in any common form -> +947XXXXXXXX, or None."""
    d = re.sub(r"\D", "", str(raw or ""))
    if d.startswith("0094"):
        d = d[2:]
    if d.startswith("94") and len(d) == 11:
        d = d[2:]
    if d.startswith("0") and len(d) == 10:
        d = d[1:]
    return f"+94{d}" if len(d) == 9 and d.startswith("7") else None


def mask(phone):
    return phone[:5] + "***" + phone[-4:] if phone and len(phone) > 9 else "***"


def links():
    try:
        return json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_link(phone, chat_id):
    data = links()
    if chat_id is None:
        data.pop(phone, None)
    else:
        data[phone] = chat_id
    LINKS.parent.mkdir(parents=True, exist_ok=True)
    LINKS.write_text(json.dumps(data, indent=1), encoding="utf-8")


def _telegram(phone, text):
    chat = links().get(phone)
    if not chat:
        return "demo", "no SMS gateway: generated only (phone not linked in Telegram)"
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from telegram_bot import call, token  # noqa: E402
    try:
        call(token(), "sendMessage", chat_id=chat, text=text)
        return "sent", "telegram"
    except Exception as e:  # noqa: BLE001
        return "failed", f"telegram: {type(e).__name__}"


def _twilio(phone, text):
    sid, tok, frm = setting("TWILIO_ACCOUNT_SID"), setting("TWILIO_AUTH_TOKEN"), setting("TWILIO_FROM")
    if not (sid and tok and frm):
        return "failed", "twilio settings missing in key.txt"
    req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
                                 data=urllib.parse.urlencode({"To": phone, "From": frm, "Body": text}).encode(),
                                 headers={"Authorization": "Basic " + base64.b64encode(f"{sid}:{tok}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return "sent", "twilio " + json.load(r).get("status", "")
    except Exception as e:  # noqa: BLE001
        return "failed", f"twilio: {getattr(e, 'code', type(e).__name__)}"


def _notifylk(phone, text):
    uid, key, sender = setting("NOTIFYLK_USER_ID"), setting("NOTIFYLK_API_KEY"), setting("NOTIFYLK_SENDER_ID", "NotifyDEMO")
    if not (uid and key):
        return "failed", "notify.lk settings missing in key.txt"
    q = {"user_id": uid, "api_key": key, "sender_id": sender, "to": phone.lstrip("+"), "message": text}
    if not text.isascii():
        q["type"] = "unicode"
    try:
        with urllib.request.urlopen("https://app.notify.lk/api/v1/send?" + urllib.parse.urlencode(q), timeout=30) as r:
            body = json.load(r)
        return ("sent", "notify.lk") if str(body.get("status")).lower() == "success" else ("failed", "notify.lk refused the message")
    except Exception as e:  # noqa: BLE001
        return "failed", f"notify.lk: {getattr(e, 'code', type(e).__name__)}"


def provider():
    return (setting("SMS_PROVIDER", "telegram") or "telegram").lower()


def send(phone, text):
    p = provider()
    if p == "demo":
        return "demo", "demo mode: generated only"
    return {"telegram": _telegram, "twilio": _twilio, "notifylk": _notifylk}.get(p, _telegram)(phone, text)
