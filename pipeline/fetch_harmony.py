"""Download the results of a NASA Harmony subset job (e.g. the GPM IMERG subset made on the GES DISC website)
using the Earthdata login in key.txt. Same job the website's download script fetches, without its prompts.
Usage:  python pipeline/fetch_harmony.py <job_id> [out_dir]      (default out_dir: data/manual/imerg)
"""
import base64
import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import earthdata as ed  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main():
    job = sys.argv[1]
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data/manual/imerg"
    out.mkdir(parents=True, exist_ok=True)
    user, pwd = ed.credentials()
    basic = {"Authorization": "Basic " + base64.b64encode(f"{user}:{pwd}".encode()).decode(), "User-Agent": "crop-rotation-tool"}
    # Earthdata user token (reuses an existing one or creates one); never printed
    toks = json.load(urllib.request.urlopen(urllib.request.Request("https://urs.earthdata.nasa.gov/api/users/tokens", headers=basic), timeout=120))
    if not toks:
        toks = [json.load(urllib.request.urlopen(urllib.request.Request("https://urs.earthdata.nasa.gov/api/users/token", data=b"", headers=basic, method="POST"), timeout=120))]
    auth = {"Authorization": f"Bearer {toks[0]['access_token']}", "User-Agent": "crop-rotation-tool"}
    url = f"https://harmony.earthdata.nasa.gov/jobs/{job}"
    while True:
        st = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=auth), timeout=120))
        print(f"job status: {st['status']} ({st.get('progress')} %)", flush=True)
        if st["status"] in ("successful", "complete_with_errors", "failed", "canceled"):
            break
        time.sleep(30)
    links = []
    page = url
    while page:  # results can be paged
        st = json.load(urllib.request.urlopen(urllib.request.Request(page, headers=auth), timeout=120))
        links += [l["href"] for l in st.get("links", []) if l.get("rel") == "data"]
        page = next((l["href"] for l in st.get("links", []) if l.get("rel") == "next"), None)
    print(f"{len(links)} result files", flush=True)
    for i, href in enumerate(links, 1):
        dest = out / href.split("?")[0].rsplit("/", 1)[-1]
        if dest.exists() and dest.stat().st_size > 0:
            continue
        for k in range(3):
            try:
                dest.write_bytes(urllib.request.urlopen(urllib.request.Request(href, headers=auth), timeout=300).read())
                break
            except Exception as e:
                print(f"  retry {dest.name}: {type(e).__name__}", flush=True)
                time.sleep(10 * (k + 1))
        if i % 25 == 0 or i == len(links):
            print(f"  {i}/{len(links)} downloaded", flush=True)
    print("files in", out, ":", len(list(out.iterdir())))


if __name__ == "__main__":
    main()
