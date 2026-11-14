"""Shared NASA Earthdata helpers: credentials from key.txt (never printed), AppEEARS login and task handling,
and an authenticated session for GES DISC downloads.
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APPEEARS = "https://appeears.earthdatacloud.nasa.gov/api"


def credentials():
    user, pwd = os.environ.get("EARTHDATA_USERNAME"), os.environ.get("EARTHDATA_PASSWORD")
    if not (user and pwd):
        text = (ROOT / "key.txt").read_text(encoding="utf-8")
        get = lambda k: (re.search(rf"^\s*{k}\s*[=:]\s*[\"']?([^\"'\s]+)", text, re.M) or [None, None])[1]
        user, pwd = get("EARTHDATA_USERNAME"), get("EARTHDATA_PASSWORD")
    if not (user and pwd):
        raise SystemExit("EARTHDATA_USERNAME / EARTHDATA_PASSWORD not found in key.txt")
    return user, pwd


def _req(url, data=None, headers=None, method=None, timeout=120):
    body = json.dumps(data).encode() if isinstance(data, (dict, list)) else data
    h = {"User-Agent": "crop-rotation-tool", **(headers or {})}
    if isinstance(data, (dict, list)):
        h["Content-Type"] = "application/json"
    with urllib.request.urlopen(urllib.request.Request(url, data=body, headers=h, method=method), timeout=timeout) as r:
        return r.read()


def appeears_token():
    user, pwd = credentials()
    auth = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    out = json.loads(_req(f"{APPEEARS}/login", data=b"", headers={"Authorization": f"Basic {auth}"}, method="POST"))
    return out["token"]


def appeears(path, token, data=None, method=None, raw=False, timeout=300):
    b = _req(f"{APPEEARS}/{path}", data=data, headers={"Authorization": f"Bearer {token}"}, method=method, timeout=timeout)
    return b if raw else json.loads(b)


def wait_task(token, task_id, every=60, limit_s=6 * 3600):
    t0 = time.time()
    while True:
        st = appeears(f"task/{task_id}", token)
        print(f"  task {st.get('task_name')}: {st['status']} ({int(time.time() - t0)} s)", flush=True)
        if st["status"] == "done":
            return st
        if st["status"] in ("error", "expired") or time.time() - t0 > limit_s:
            raise RuntimeError(f"AppEEARS task {task_id} ended with status {st['status']}")
        time.sleep(every)


def download_task_csvs(token, task_id, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    files = appeears(f"bundle/{task_id}", token)["files"]
    got = []
    for f in files:
        if not f["file_name"].endswith(".csv"):
            continue
        dest = out_dir / Path(f["file_name"]).name
        dest.write_bytes(appeears(f"bundle/{task_id}/{f['file_id']}", token, raw=True, timeout=900))
        got.append(dest)
    return got


def earthdata_opener():
    """urllib opener that follows the Earthdata login redirect (for GES DISC OPeNDAP / data URLs)."""
    user, pwd = credentials()
    pm = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    pm.add_password(None, "https://urs.earthdata.nasa.gov", user, pwd)
    return urllib.request.build_opener(urllib.request.HTTPBasicAuthHandler(pm), urllib.request.HTTPCookieProcessor(CookieJar()))
