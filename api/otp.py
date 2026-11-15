"""Phone login codes (OTP): a random 6-digit code texted through the MoceanAPI SMS service.

The Mocean API token is read from key.txt (line "otp = apit-...") or the MOCEAN_API_TOKEN environment variable,
and is never printed or returned. The code itself is never stored: only a hash of it, for 5 minutes.

Limits enforced here (in memory, per API process): 3 codes per number per hour, 5 wrong tries per code,
codes valid for 5 minutes.

Usage (tests)
  python api/otp.py probe                 check the token with a request that sends no SMS
  python api/otp.py send 0771234567       text a code to that number (uses one SMS of credit)
  python api/otp.py check <reqid> <code>  check a code
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://rest.moceanapi.com/rest/2/verify"
BRAND = os.environ.get("OTP_BRAND", "FieldShift")
VALID_S = 300
_sent = {}      # phone -> [timestamps]
_pending = {}   # reqid -> {"phone", "tries", "at"}


def token():
    if os.environ.get("MOCEAN_API_TOKEN"):
        return os.environ["MOCEAN_API_TOKEN"]
    for name in ("key.txt", "keys.txt"):
        p = ROOT / name
        if p.exists():
            m = re.search(r"^\s*(?:otp|MOCEAN_API_TOKEN)\s*[=:]\s*[\"']?([^\"'\s]+)", p.read_text(encoding="utf-8"), re.M | re.I)
            if m:
                return m.group(1)
    raise RuntimeError("Mocean API token not found (key.txt line 'otp = ...')")


def normalize_phone(raw):
    d = re.sub(r"\D", "", str(raw or ""))
    if d.startswith("0094"):
        d = d[2:]
    if d.startswith("94") and len(d) == 11:
        d = d[2:]
    if d.startswith("0") and len(d) == 10:
        d = d[1:]
    return f"+94{d}" if len(d) == 9 and d.startswith("7") else None


def _call(path, params):
    body = urllib.parse.urlencode({**params, "mocean-resp-format": "json"}).encode()
    req = urllib.request.Request(f"{BASE}/{path}", data=body, headers={"Authorization": f"Bearer {token()}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}


TEXT = {
    "en": "Field Shift login code: {code}. It works for 5 minutes. Do not share it.",
    "si": "Field Shift ඇතුළු වීමේ කේතය: {code}. මිනිත්තු 5ක් වලංගුයි. කිසිවෙකුට නොදෙන්න.",
    "ta": "Field Shift உள்நுழைவுக் குறியீடு: {code}. 5 நிமிடங்கள் செல்லுபடியாகும். யாருடனும் பகிர வேண்டாம்.",
}


def _sms(phone, text):
    """MoceanAPI SMS. Returns (ok, detail)."""
    body = urllib.parse.urlencode({"mocean-from": BRAND, "mocean-to": phone.lstrip("+"), "mocean-text": text,
                                   "mocean-resp-format": "json"}).encode()
    req = urllib.request.Request("https://rest.moceanapi.com/rest/2/sms", data=body, headers={"Authorization": f"Bearer {token()}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            out = json.loads(e.read().decode() or "{}")
        except ValueError:
            return False, f"HTTP {e.code}"
    msg = (out.get("messages") or [{}])[0]
    return str(msg.get("status")) == "0", msg.get("err_msg") or "sent"


def send_code(raw_phone, lang="en"):
    """Creates a 6-digit code, texts it, keeps only its hash. Returns {"ok", "reqid"} or {"ok": False, "error"}."""
    phone = normalize_phone(raw_phone)
    if not phone:
        return {"ok": False, "error": "Enter a Sri Lankan mobile number, for example 0771234567."}
    now = time.time()
    recent = [t for t in _sent.get(phone, []) if now - t < 3600]
    if len(recent) >= 3:
        return {"ok": False, "error": "Too many codes for this number. Try again in an hour."}
    code = f"{secrets.randbelow(10**6):06d}"
    ok, detail = _sms(phone, TEXT.get(lang, TEXT["en"]).format(code=code))
    if not ok:
        return {"ok": False, "error": "Could not send the code. Try again in a minute.", "detail": detail}
    _sent[phone] = recent + [now]
    reqid = secrets.token_urlsafe(16)
    _pending[reqid] = {"phone": phone, "tries": 0, "at": now, "hash": hashlib.sha256(f"{reqid}:{code}".encode()).hexdigest()}
    return {"ok": True, "reqid": reqid, "phone": phone}


def check_code(reqid, code):
    """Returns {"ok": True, "phone": ...} when the code is right."""
    p = _pending.get(reqid)
    if not p or time.time() - p["at"] > VALID_S:
        return {"ok": False, "error": "This code has expired. Ask for a new one."}
    if p["tries"] >= 5:
        return {"ok": False, "error": "Too many wrong codes. Ask for a new one."}
    p["tries"] += 1
    code = str(code or "").strip()
    if not re.fullmatch(r"\d{6}", code):
        return {"ok": False, "error": "The code is the 6 digits in the SMS."}
    if hmac.compare_digest(p["hash"], hashlib.sha256(f"{reqid}:{code}".encode()).hexdigest()):
        _pending.pop(reqid, None)
        return {"ok": True, "phone": p["phone"]}
    return {"ok": False, "error": "That code is not right. Check the SMS and try again."}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "probe"
    if cmd == "probe":
        status, body = _call("req", {"mocean-brand": BRAND})  # no number: Mocean refuses before sending anything
        print("HTTP", status, {k: v for k, v in body.items() if k in ("status", "err_msg")})
    elif cmd == "send":
        print(send_code(sys.argv[2]))
    elif cmd == "check":
        _pending[sys.argv[2]] = {"phone": "?", "tries": 0, "at": time.time()}
        print(check_code(sys.argv[2], sys.argv[3]))
