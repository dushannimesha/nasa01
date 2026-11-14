"""Sends Field Shift advice to registered farmers who have no smartphone.

Farmers are registered on the Officer desk (Firestore collection "farmers": phone, district, water source, goal,
language, optional crop + sowing date). That collection cannot be read from the website; only this script reads it,
with the Firebase service account. Each message goes out through sms_gateway.send() and is recorded in "outbox"
with the phone number masked, which the Officer desk shows.

Usage
  python channels/sms_sender.py                     keep running: handle "Send" requests from the Officer desk
  python channels/sms_sender.py --once              handle pending requests once and stop
  python channels/sms_sender.py --season [district] send season advice now (all districts, or one)
  python channels/sms_sender.py --alerts            send weather alerts now (for a daily schedule)
  python channels/sms_sender.py --csv FILE ...      farmers from a CSV instead of Firestore (phone,district,water,goal,lang,crop,sowDate)
  add --dry-run to generate and print without sending or writing anything
"""
import csv
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sms_gateway as gw  # noqa: E402
from sms_messages import alert_messages, season_message, segments  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALERT_LOG = ROOT / "data/channels/alert_log.json"
DISTRICTS = {f["properties"]["id"]: f["properties"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"]}
DRY = "--dry-run" in sys.argv
_db = None


def db():
    global _db
    if _db is None:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(str(ROOT / "firebase-service-account.json")))
        _db = firestore.client()
    return _db


def farmers_from_firestore():
    out = []
    for d in db().collection("farmers").stream():
        f = d.to_dict()
        f["phone"] = gw.normalize_phone(f.get("phone"))
        if f["phone"] and f.get("district") in DISTRICTS and f.get("consent") is True and not f.get("optedOut"):
            out.append(f)
    return out


def farmers_from_csv(path):
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            r = {k.strip(): (v or "").strip() for k, v in r.items() if k}
            r["phone"] = gw.normalize_phone(r.get("phone"))
            if r["phone"] and r.get("district") in DISTRICTS:
                out.append({**r, "consent": True})
    return out


def forecast(did, cache={}):
    if did not in cache:
        p = DISTRICTS[did]
        url = (f"https://api.open-meteo.com/v1/forecast?latitude={p['lat']}&longitude={p['lon']}"
               "&daily=precipitation_sum,temperature_2m_max&forecast_days=7&timezone=Asia%2FColombo")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "crop-rotation-tool"}), timeout=60) as r:
            cache[did] = json.load(r)["daily"]
        time.sleep(0.5)
    return cache[did]


def deliver(campaign_id, f, kind, text):
    status, detail = ("demo", "dry run") if DRY else gw.send(f["phone"], text)
    rec = {"campaign": campaign_id, "kind": kind, "createdAt": datetime.now(timezone.utc).isoformat(), "district": f["district"],
           "lang": f.get("lang", "en"), "to": gw.mask(f["phone"]), "text": text, "segments": segments(text),
           "status": status, "detail": detail, "via": gw.provider()}
    print(f"  {rec['to']} {rec['district']:<13} {kind:<6} {status:<6} {rec['segments']} part(s)  {text[:70]}...", flush=True)
    if not DRY and campaign_id != "csv":
        db().collection("outbox").add(rec)
    return status


def run(campaign_id, kind, farmers, district=None):
    targets = [f for f in farmers if not district or district == "all" or f["district"] == district]
    counts = {"sent": 0, "demo": 0, "failed": 0}
    log = {} if DRY else (json.loads(ALERT_LOG.read_text()) if ALERT_LOG.exists() else {})
    today = date.today().isoformat()
    for f in targets:
        if kind == "season":
            counts[deliver(campaign_id, f, "season", season_message(f))] += 1
            continue
        try:
            alerts = alert_messages(f, forecast(f["district"]))
        except Exception as e:  # noqa: BLE001
            print(f"  forecast failed for {f['district']}: {type(e).__name__}")
            continue
        for a_kind, text in alerts:
            key = f"{f['phone']}|{a_kind}"
            if log.get(key, "") > today:  # same alert at most once every 5 days (log holds the next allowed date)
                continue
            counts[deliver(campaign_id, f, a_kind, text)] += 1
            log[key] = (date.fromordinal(date.today().toordinal() + 5)).isoformat()
    if not DRY and kind == "alerts":
        ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
        ALERT_LOG.write_text(json.dumps(log, indent=1))
    print(f"{kind}: {len(targets)} farmers -> {counts}", flush=True)
    return {"farmers": len(targets), **counts}


def pending_campaigns():
    for doc in db().collection("campaigns").where("status", "==", "new").stream():
        c = doc.to_dict()
        doc.reference.update({"status": "running", "startedAt": datetime.now(timezone.utc).isoformat()})
        try:
            res = run(doc.id, "alerts" if c.get("type") == "alerts" else "season", farmers_from_firestore(), c.get("district"))
            doc.reference.update({"status": "done", "finishedAt": datetime.now(timezone.utc).isoformat(), **res})
        except Exception as e:  # noqa: BLE001
            doc.reference.update({"status": "failed", "error": type(e).__name__})
            print("campaign failed:", type(e).__name__, flush=True)


def main():
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    farmers = None
    if "--csv" in args:
        i = args.index("--csv")
        farmers = farmers_from_csv(args[i + 1])
        del args[i:i + 2]
    print(f"provider: {gw.provider()}{' (dry run)' if DRY else ''}", flush=True)
    if "--season" in args or "--alerts" in args:
        kind = "season" if "--season" in args else "alerts"
        rest = [a for a in args if not a.startswith("--")]
        run("csv" if farmers is not None else f"manual-{kind}-{date.today()}", kind, farmers if farmers is not None else farmers_from_firestore(), rest[0] if rest else None)
        return
    while True:
        try:
            pending_campaigns()
        except Exception as e:  # noqa: BLE001
            print("poll error:", type(e).__name__, flush=True)
        if "--once" in args:
            return
        time.sleep(20)


if __name__ == "__main__":
    main()
