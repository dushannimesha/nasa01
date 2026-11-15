"""Tell the website where the API is: writes the API's public HTTPS address to Firestore (config/api).
The farmer page shows "Log in with your mobile" only while this address is set.
Usage:  python api/publish_url.py https://api.example.org     (or --clear to hide the login again)
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    if len(sys.argv) < 2 or not (sys.argv[1] == "--clear" or sys.argv[1].startswith("https://")):
        sys.exit("Usage: python api/publish_url.py https://<public address> | --clear")
    firebase_admin.initialize_app(credentials.Certificate(str(ROOT / "firebase-service-account.json")))
    doc = firestore.client().collection("config").document("api")
    if sys.argv[1] == "--clear":
        doc.delete()
        print("API address cleared; phone login hidden on the site.")
    else:
        doc.set({"url": sys.argv[1].rstrip("/"), "updatedAt": datetime.now(timezone.utc).isoformat()})
        print("API address published; phone login shown on the site.")
