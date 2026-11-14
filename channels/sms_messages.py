"""Short SMS texts for farmers without a smartphone, in English, Sinhala and Tamil.

season_message(farmer)  the best Maha and Yala crops for the farmer's district, water source and goal
                        (same answers as the web app and the Telegram bot: web/public/data/bot_table.json)
alert_messages(farmer, forecast)  weather alerts for a crop already sown: dry spell, heavy rain, heat
segments(text)          SMS parts the text needs (Sinhala and Tamil use UCS-2: 70 characters, 67 per part when split)

A farmer is a dict: phone, district, water (rain|tank|well), goal (income|water|soil|safe), lang (en|si|ta),
and optionally crop + sowDate (YYYY-MM-DD) for alerts.
"""
import json
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = json.loads((ROOT / "web/src/lib/names.json").read_text(encoding="utf-8"))
_table = None
_crops = None

GSM7 = set("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà")

T = {
    "en": {
        "season": "Field Shift {d}: Maha {m}, Yala {y}. About Rs {inc} per ha a year (now Rs {cur}). {care}Reply PLAN for more. Check with your Agri Instructor.",
        "care": "Water may run short. ",
        "dry": "Field Shift {d}: {crop} day {day}, {stage}. Almost no rain next 7 days ({mm} mm). Keep the field watered.",
        "heavy": "Field Shift {d}: heavy rain {when} ({mm} mm). Clear drains; do not apply fertilizer before it.",
        "heat": "Field Shift {d}: {crop} at {stage}, hot days ahead ({t} C). Water in the evening; keep soil moist.",
    },
    "si": {
        "season": "Field Shift {d}: මහ {m}, යල {y}. හෙක්. වසරකට රු. {inc} (දැන් රු. {cur}). {care}වැඩි විස්තරට PLAN යවන්න.",
        "care": "වතුර මදි විය හැක. ",
        "dry": "Field Shift {d}: {crop} දින {day}. ඉදිරි දින 7 වැසි නැති තරම් ({mm} mm). කුඹුරට වතුර දෙන්න.",
        "heavy": "Field Shift {d}: {when} තද වැසි ({mm} mm). කාණු පිරිසිදු කරන්න; ඊට පෙර පොහොර නොදමන්න.",
        "heat": "Field Shift {d}: {crop}, ඉදිරියට උණුසුම් දින ({t} C). සවස වතුර දෙන්න.",
    },
    "ta": {
        "season": "Field Shift {d}: பெரும்போகம் {m}, சிறுபோகம் {y}. ஹெக். ஆண்டுக்கு ரூ. {inc} (இப்போது ரூ. {cur}). {care}மேலும் அறிய PLAN அனுப்பவும்.",
        "care": "நீர் பற்றாக்குறை ஏற்படலாம். ",
        "dry": "Field Shift {d}: {crop} நாள் {day}. அடுத்த 7 நாட்கள் மழை இல்லை ({mm} mm). வயலுக்கு நீர் பாய்ச்சவும்.",
        "heavy": "Field Shift {d}: {when} கனமழை ({mm} mm). வடிகால்களைச் சுத்தம் செய்யவும்; அதற்கு முன் உரம் இடவேண்டாம்.",
        "heat": "Field Shift {d}: {crop}, வெப்பமான நாட்கள் ({t} C). மாலையில் நீர் பாய்ச்சவும்.",
    },
}


def table():
    global _table
    if _table is None:
        _table = json.loads((ROOT / "web/public/data/bot_table.json").read_text(encoding="utf-8"))
    return _table


def crops():
    global _crops
    if _crops is None:
        _crops = {c["id"]: c for c in json.loads((ROOT / "web/public/data/crops.json").read_text(encoding="utf-8"))["crops"]}
    return _crops


def district_name(did, lang):
    return NAMES["districts"].get(lang, {}).get(did) or table()["districts"][did]["name"]


def crop_name(cid, lang):
    if cid == "fallow" or cid not in crops():
        return NAMES["crops"].get(lang, {}).get("fallow") or "rest the field"
    return NAMES["crops"].get(lang, {}).get(cid) or crops()[cid]["name"]


def segments(text):
    gsm = all(ch in GSM7 for ch in text)
    n = len(text)
    single, multi = (160, 153) if gsm else (70, 67)
    return 1 if n <= single else -(-n // multi)


def season_message(f):
    lang = f.get("lang", "en") if f.get("lang") in T else "en"
    a = table()["districts"][f["district"]]["answers"][f"{f.get('water', 'tank')}|{f.get('goal', 'income')}"]
    best = a["top"][0]
    return T[lang]["season"].format(
        d=district_name(f["district"], lang), m=crop_name(best["rot"]["maha"], lang), y=crop_name(best["rot"]["yala"], lang),
        inc=best["income"], cur=a["currentIncome"], care=T[lang]["care"] if best["suit"] != "pass" else "")


def stage_of(crop, day):
    start = 0
    for st in crop["stages"]:
        if day < start + st["days"]:
            return st
        start += st["days"]
    return None


def alert_messages(f, forecast, today=None):
    """forecast: {"time": [...], "precipitation_sum": [...], "temperature_2m_max": [...]} for the next days.
    Returns a list of (kind, text). Only for a crop that is in the field now."""
    lang = f.get("lang", "en") if f.get("lang") in T else "en"
    crop = crops().get(f.get("crop") or "")
    if not crop or not f.get("sowDate"):
        return []
    today = today or date.today()
    day = (today - datetime.strptime(f["sowDate"], "%Y-%m-%d").date()).days
    st = stage_of(crop, day) if day >= 0 else None
    if not st:
        return []
    d, cn = district_name(f["district"], lang), crop_name(crop["id"], lang)
    rain = [r or 0 for r in forecast["precipitation_sum"][:7]]
    tmax = [t or 0 for t in forecast["temperature_2m_max"][:7]]
    out = []
    if sum(rain) <= 5 and st["kc"] >= 1 and f.get("water") != "tank":
        out.append(("dry", T[lang]["dry"].format(d=d, crop=cn, day=day, stage=st["name"].lower(), mm=round(sum(rain)))))
    big = max(range(len(rain)), key=lambda i: rain[i]) if rain else None
    if big is not None and rain[big] >= 50:
        out.append(("heavy", T[lang]["heavy"].format(d=d, when=f"{forecast['time'][big][8:10]}/{forecast['time'][big][5:7]}", mm=round(rain[big]))))
    if max(tmax, default=0) >= 35 and st["kc"] >= 1:
        out.append(("heat", T[lang]["heat"].format(d=d, crop=cn, stage=st["name"].lower(), t=round(max(tmax)))))
    return out


if __name__ == "__main__":
    for lang in ("en", "si", "ta"):
        f = {"phone": "+94770000000", "district": "anuradhapura", "water": "tank", "goal": "income", "lang": lang,
             "crop": "paddy", "sowDate": "2026-10-10"}
        s = season_message(f)
        print(f"[{lang}] {segments(s)} part(s), {len(s)} chars\n{s}")
        fc = {"time": [f"2026-11-{15 + i}" for i in range(7)], "precipitation_sum": [0, 0, 1, 0, 0, 62, 3], "temperature_2m_max": [33, 34, 36, 35, 33, 31, 32]}
        for kind, text in alert_messages(f, fc, today=date(2026, 11, 15)):
            print(f"  alert {kind}: {segments(text)} part(s): {text}")
