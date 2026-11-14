"""Rebuild everything from raw data to the files the web app, bot and API serve.

Order: NASA POWER download -> climate features -> water balance -> DCS paddy parse -> supplied CSVs ->
SoilGrids -> yield model -> data packs -> 2021 test -> bot answers -> web build.
Steps whose inputs already exist are fast; downloads skip files already on disk.
Usage:  python scripts/build_all.py            (add --no-web to skip the website build)
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
PY = sys.executable
STEPS = [
    ([PY, "pipeline/ingest_power.py", "1981", "2021"], ROOT),
    ([PY, "pipeline/features.py"], ROOT),
    ([PY, "models/water_balance.py"], ROOT),
    ([PY, "pipeline/parse_dcs.py"], ROOT),
    ([PY, "pipeline/parse_csv.py"], ROOT),
    ([PY, "pipeline/ingest_soil.py"], ROOT),
    ([PY, "models/yield_ml.py"], ROOT),
    ([PY, "packs/build_packs.py"], ROOT),
    (["node", "scripts/run_backtest.mjs"], WEB),
    (["node", "scripts/make_bot_table.mjs"], WEB),
]

if __name__ == "__main__":
    steps = STEPS + ([] if "--no-web" in sys.argv else [(["npm", "run", "build"], WEB)])
    for cmd, cwd in steps:
        print(f"\n=== {' '.join(cmd[1:] if cmd[0] == PY else cmd)}", flush=True)
        r = subprocess.run(cmd, cwd=cwd, shell=sys.platform == "win32" and cmd[0] == "npm")
        if r.returncode:
            sys.exit(f"step failed: {' '.join(cmd)}")
    print("\nall steps done")
