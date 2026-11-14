#!/usr/bin/env bash
# Run the Field Shift backend on a Linux server (e.g. ampere): API on port 8000 and the Telegram bot.
# First time:  git clone https://github.com/dushannimesha/nasa01.git && cd nasa01 && bash scripts/serve.sh setup
# Then:        bash scripts/serve.sh start | stop | status
# The bot needs TELEGRAM_BOT_TOKEN in the environment or in key.txt (keep that file readable only by you: chmod 600 key.txt).
# The data files under data/ are not in git: run "python scripts/build_all.py --no-web" once after setup
# (needs internet; NASA POWER and SoilGrids downloads take about 15 minutes), or copy data/ from a built machine.
set -euo pipefail
cd "$(dirname "$0")/.."
VENV=.venv
case "${1:-start}" in
  setup)
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r requirements.txt
    (cd web && npm ci --no-audit --no-fund)
    echo "setup done. Next: $VENV/bin/python scripts/build_all.py --no-web"
    ;;
  start)
    mkdir -p logs
    nohup "$VENV/bin/uvicorn" api.main:app --host 0.0.0.0 --port "${PORT:-8000}" > logs/api.log 2>&1 & echo $! > logs/api.pid
    nohup "$VENV/bin/python" channels/telegram_bot.py > logs/bot.log 2>&1 & echo $! > logs/bot.pid
    echo "api pid $(cat logs/api.pid), bot pid $(cat logs/bot.pid); logs in logs/"
    ;;
  stop)
    for p in api bot; do [ -f "logs/$p.pid" ] && kill "$(cat logs/$p.pid)" 2>/dev/null && rm "logs/$p.pid" && echo "stopped $p"; done
    ;;
  status)
    for p in api bot; do if [ -f "logs/$p.pid" ] && kill -0 "$(cat logs/$p.pid)" 2>/dev/null; then echo "$p running"; else echo "$p stopped"; fi; done
    curl -s "localhost:${PORT:-8000}/health" || true; echo
    ;;
  *) echo "usage: $0 setup|start|stop|status"; exit 1 ;;
esac
