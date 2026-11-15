"""Field Shift API.

The web app works without this server (it ships precomputed district packs and ranks in the browser, also offline).
The API adds: the trained paddy yield model with what-if weather, server-side ranking for other clients
(SMS gateways, partner systems), and a text endpoint any SMS provider can call.

Endpoints
  GET  /health
  GET  /api/districts                         id, name, centre
  GET  /api/pack/{district}                   everything the farmer page uses for one district
  GET  /api/national                          national dashboard data
  GET  /api/backtest                          2021 with/without-app results
  GET  /api/yield/{district}/{season}         paddy yield model: 2021 prediction, 80 % interval, reasons;
                                              ?rain_pct=-20&temp_c=1 runs a what-if on the 2021 weather
  POST /api/plan                              ranked rotations (same engine as the web app)
  POST /api/text                              {"user": "...", "text": "PLAN"} -> {"reply": "..."}  (SMS / chat bridge)
  POST /api/otp/send                          {"phone": "07..."} -> {"reqid"}   texts a login code (MoceanAPI)
  POST /api/otp/verify                        {"reqid", "code"} -> {"token"}    Firebase custom token for that phone
Run:  uvicorn api.main:app --host 0.0.0.0 --port 8000      (from the repository root)
"""
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "web/public/data"
sys.path[:0] = [str(ROOT / "channels"), str(ROOT / "models"), str(ROOT / "api")]
from text_flow import reply as text_reply  # noqa: E402

app = FastAPI(title="Field Shift API", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET", "POST"], allow_headers=["*"])


@lru_cache
def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@lru_cache
def districts():
    return {d["id"]: d for d in (f["properties"] for f in json.loads((ROOT / "web/public/geo/districts.json").read_text(encoding="utf-8"))["features"])}


def check(district):
    if district not in districts():
        raise HTTPException(404, f"unknown district '{district}'")


@lru_cache
def yield_model():
    import yield_ml  # builds the same feature table the model was trained on
    art = joblib.load(ROOT / "models/artifacts/paddy_best.joblib")
    table = yield_ml.build()
    return art, table


@app.get("/health")
def health():
    return {"ok": True, "districts": len(districts()), "model": (ROOT / "models/artifacts/paddy_best.joblib").exists()}


@app.get("/api/districts")
def list_districts():
    return [{"id": k, "name": v["name"], "lat": v["lat"], "lon": v["lon"]} for k, v in sorted(districts().items())]


@app.get("/api/pack/{district}")
def pack(district: str):
    check(district)
    return load(f"packs/{district}.json")


@app.get("/api/national")
def national():
    return load("national.json")


@app.get("/api/backtest")
def backtest():
    return load("backtest_2021.json")


@app.get("/api/yield/{district}/{season}")
def paddy_yield(district: str, season: str, year: int = 2021, rain_pct: float = 0, temp_c: float = 0):
    check(district)
    if season not in ("maha", "yala"):
        raise HTTPException(400, "season must be maha or yala")
    art, table = yield_model()
    row = table[(table.district == district) & (table.season == season) & (table.year == year)]
    if row.empty:
        raise HTTPException(404, f"no data for {district} {season} {year} (available up to 2021)")
    x = row[art["features"]].copy()
    p0 = float(art["model"].predict(x)[0])
    if rain_pct or temp_c:  # what-if: same adjustments as the model's sensitivity check
        import yield_ml
        x = yield_ml.what_if(x, rain_pct, temp_c)
    p = float(art["model"].predict(x)[0])
    actual = row.yield_t_ha.iloc[0]
    return {"district": district, "season": season, "year": year, "model": art["name"], "inputs": art.get("set"), "predicted_t_ha": round(p, 2),
            "interval80_t_ha": [round(p + art["q10"], 2), round(p + art["q90"], 2)], "baseline_t_ha": round(p0, 2),
            "whatIf": {"rain_pct": rain_pct, "temp_c": temp_c}, "actual_t_ha": None if np.isnan(actual) else round(float(actual), 2)}


class PlanRequest(BaseModel):
    district: str
    water: str = Field("tank", pattern="^(rain|tank|well)$")
    goal: str | None = Field(None, pattern="^(balanced|income|water|soil|safe)$")
    weights: dict[str, float] | None = None
    current: dict[str, str] | None = None
    areaHa: float = Field(1.0, gt=0, lt=1000)
    market: bool = True


@app.post("/api/plan")
def plan(req: PlanRequest):
    check(req.district)
    r = subprocess.run(["node", str(ROOT / "web/scripts/plan_cli.mjs")], input=req.model_dump_json(exclude_none=True), capture_output=True, text=True, timeout=30)
    out = json.loads(r.stdout or '{"error": "no output"}')
    if "error" in out:
        raise HTTPException(400, out["error"])
    return out


class TextIn(BaseModel):
    user: str = Field(..., max_length=64)
    text: str = Field(..., max_length=500)


@app.post("/api/text")
def text(msg: TextIn):
    return {"reply": text_reply(f"api:{msg.user}", msg.text)}


# ---- Phone login (OTP by SMS through MoceanAPI) ----
# The website asks for a code, the farmer types it, and on success gets a Firebase custom token for their number.
import time  # noqa: E402

import otp  # noqa: E402

_ip_hits = {}


def _ip_ok(request, limit=10):
    ip = request.client.host if request.client else "?"
    now = time.time()
    hits = [t for t in _ip_hits.get(ip, []) if now - t < 3600]
    _ip_hits[ip] = hits + [now]
    return len(hits) < limit


class OtpSend(BaseModel):
    phone: str = Field(..., max_length=20)
    lang: str = Field("en", pattern="^(en|si|ta)$")


class OtpCheck(BaseModel):
    reqid: str = Field(..., max_length=64)
    code: str = Field(..., max_length=8)


@app.post("/api/otp/send")
def otp_send(body: OtpSend, request: Request):
    if not _ip_ok(request):
        raise HTTPException(429, "Too many requests from this network. Try again later.")
    r = otp.send_code(body.phone, body.lang)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    return {"reqid": r["reqid"], "phone": r["phone"][:5] + "***" + r["phone"][-4:]}


@app.post("/api/otp/verify")
def otp_verify(body: OtpCheck):
    r = otp.check_code(body.reqid, body.code)
    if not r["ok"]:
        raise HTTPException(400, r["error"])
    import firebase_admin
    from firebase_admin import auth, credentials
    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.Certificate(str(ROOT / "firebase-service-account.json")))
    token = auth.create_custom_token(r["phone"], {"role": "farmer"}).decode()
    return {"token": token, "phone": r["phone"]}