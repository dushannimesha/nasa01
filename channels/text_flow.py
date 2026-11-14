"""Text conversation for farmers without a smartphone app. Channel-independent: the Telegram bot and an
SMS gateway both call reply(user_id, text) and send back the returned string.

Answers come from web/public/data/bot_table.json, which is produced by the same engine as the web app.
"""
import difflib
import json
from datetime import date, datetime
from pathlib import Path

TABLE_PATH = Path(__file__).resolve().parents[1] / "web/public/data/bot_table.json"
WATER = {"1": "rain", "2": "tank", "3": "well"}
PRIORITY = {"1": "income", "2": "water", "3": "soil", "4": "safe"}
HELP = ("Field Shift crop advice.\nSend PLAN to get crop choices for your district.\n"
        "Send SOWED <crop> <date>, e.g. SOWED paddy 2021-10-25, to get this week's field actions.\n"
        "Registered by your officer? Send JOIN <your mobile number> to get season advice and weather alerts here.")

_sessions = {}
_table = None


def table():
    global _table
    if _table is None:
        _table = json.loads(TABLE_PATH.read_text(encoding="utf-8"))
    return _table


def _district(text):
    names = {d["name"].lower(): did for did, d in table()["districts"].items()}
    hit = difflib.get_close_matches(text.strip().lower(), names, n=1, cutoff=0.6)
    return names[hit[0]] if hit else None


def _plan_answer(did, water, prio):
    t = table()
    a = t["districts"][did]["answers"][f"{water}|{prio}"]
    lines = [f"{t['districts'][did]['name']}: best rotations (Maha > Yala), income in LKR per hectare per year"]
    for i, r in enumerate(a["top"], 1):
        lines.append(f"{i}. {r['name'].replace(' → ', ' > ')}: {r['income']}, water {r['water_mm']} mm" + (" (needs care)" if r["suit"] != "pass" else ""))
    lines.append(f"Usual here: {a['current'].replace(' → ', ' > ')}: {a['currentIncome']}")
    lines.append("Why no.1: " + a["top"][0]["why"])
    if t["meta"].get("sample"):
        lines.append("TEST DATA: not for real decisions yet.")
    lines.append("Advice only. Check with your Agricultural Instructor.")
    return "\n".join(lines)


def _sowed(parts, today):
    crops = {c["id"]: c for c in table()["crops"]} | {c["name"].lower().replace(" ", ""): c for c in table()["crops"]}
    if len(parts) < 3:
        return "Send: SOWED <crop> <date>. Example: SOWED paddy 2021-10-25"
    crop = crops.get(parts[1].lower())
    if not crop:
        return "Crop not known. Use one of: " + ", ".join(c["id"] for c in table()["crops"])
    try:
        sow = datetime.strptime(parts[2], "%Y-%m-%d").date()
    except ValueError:
        return "Date must look like 2021-10-25 (year-month-day)."
    day = (today - sow).days
    if day < 0:
        return f"{crop['name']}: sowing is in {-day} days."
    if day >= crop["days"]:
        return f"{crop['name']}: day {day}. The crop has reached maturity; harvest in dry weather."
    start = 0
    for st in crop["stages"]:
        if day < start + st["days"]:
            break
        start += st["days"]
    out = [f"{crop['name']} day {day} of {crop['days']}: {st['name']} stage."]
    due = [f for f in crop["fert"] if -3 <= f["day"] - day <= 7]
    out += [f"Fertilizer about day {f['day']}: {f['text']}." for f in due] or ["No fertilizer due this week."]
    if st["kc"] >= 1:
        out.append("Peak water demand now: do not let the field dry out.")
    if crop["days"] - day <= 14:
        out.append(f"Harvest in about {crop['days'] - day} days.")
    return "\n".join(out)


def reply(user_id, text, today=None):
    """Returns the answer to one incoming message and remembers where the user is in the conversation."""
    text = (text or "").strip()
    cmd = text.lower().lstrip("/")
    if cmd in ("start", "help", "hi", "hello", ""):
        _sessions.pop(user_id, None)
        return HELP
    if cmd.startswith("sowed"):
        return _sowed(text.split(), today or date.today())
    s = _sessions.get(user_id)
    if cmd == "plan" or s is None:
        _sessions[user_id] = {"step": "district"}
        return "Which district is your field in? (type the name, e.g. Anuradhapura)"
    if s["step"] == "district":
        did = _district(text)
        if not did:
            return "District not found. Type the district name again, e.g. Kurunegala."
        s.update(district=did, step="water")
        return "Water for the field?\n1 Rain only\n2 Tank or canal\n3 Agro-well\nReply 1, 2 or 3."
    if s["step"] == "water":
        if text not in WATER:
            return "Reply 1 (rain), 2 (tank or canal) or 3 (well)."
        s.update(water=WATER[text], step="priority")
        return "What matters most?\n1 Income\n2 Saving water\n3 Soil health\n4 Low risk\nReply 1, 2, 3 or 4."
    if s["step"] == "priority":
        if text not in PRIORITY:
            return "Reply 1, 2, 3 or 4."
        _sessions.pop(user_id, None)
        return _plan_answer(s["district"], s["water"], PRIORITY[text])
    _sessions.pop(user_id, None)
    return HELP


if __name__ == "__main__":  # quick self-test of a full conversation
    for msg in ["/start", "PLAN", "anuradapura", "2", "1", "SOWED paddy 2021-10-25"]:
        print(f"> {msg}\n{reply('test', msg, today=date(2021, 11, 30))}\n")
