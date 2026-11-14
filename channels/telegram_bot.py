"""Telegram bot: the free stand-in for an SMS line. Long polling, so no public URL is needed.

Reads TELEGRAM_BOT_TOKEN from key.txt (or the environment). The token is never printed.
Usage:  python channels/telegram_bot.py          run the bot
        python channels/telegram_bot.py --check   only verify the token and print the bot's username
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from text_flow import reply  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def token():
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        return os.environ["TELEGRAM_BOT_TOKEN"]
    for name in ("key.txt", "keys.txt"):
        p = ROOT / name
        if p.exists():
            m = re.search(r"^\s*TELEGRAM_BOT_TOKEN\s*[=:]\s*[\"']?([^\"'\s]+)", p.read_text(encoding="utf-8"), re.M)
            if m:
                return m.group(1)
    sys.exit("TELEGRAM_BOT_TOKEN not found in key.txt or the environment")


def call(tok, method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/{method}", data=data, timeout=70) as r:
        return json.load(r)["result"]


def main():
    tok = token()
    me = call(tok, "getMe")
    print(f"bot ok: @{me['username']}", flush=True)
    if "--check" in sys.argv:
        return
    offset = 0
    while True:
        try:
            for u in call(tok, "getUpdates", offset=offset, timeout=50):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                if "text" in msg:
                    call(tok, "sendMessage", chat_id=msg["chat"]["id"], text=reply(msg["chat"]["id"], msg["text"]))
        except Exception as e:  # network hiccup: wait and carry on (the error text may contain the URL, so it is not printed)
            print("poll error:", type(e).__name__, flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
