print(">>> fetch_ofr.py loaded")

import json
import os
import time
from datetime import datetime, timedelta

import requests

print(">>> imports done")

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "ofr.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

# OFR API base — free, no key
OFR_BASE = "https://data.financialresearch.gov/v1"

# Correct OFR mnemonics (from OFR STFM catalog)
# REPO-DVP_AR_OO-P = DVP Service Average Rate: Overnight/Open (Preliminary)
# REPO-TRI_AR_OO-P = Tri-Party Average Rate: Overnight/Open (Preliminary)
# REPO-GCF_AR_OO-P = GCF Repo Average Rate: Overnight/Open (Preliminary)
SERIES_MAP = {
    "dvp_overnight_rate": "REPO-DVP_AR_OO-P",
    "triparty_overnight_rate": "REPO-TRI_AR_OO-P",
    "gcf_overnight_rate": "REPO-GCF_AR_OO-P",
}


def log_api_call(source, status):
    log_path = os.path.join(DATA_DIR, "_api_log.json")
    entry = {"ts": datetime.now().isoformat(), "source": source, "status": status}
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                log = json.load(f)
        else:
            log = []
    except Exception:
        log = []
    log.append(entry)
    log = log[-500:]
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2)


def cache_is_fresh():
    if FORCE_REFRESH:
        print(">>> FORCE_REFRESH is true - bypassing cache.")
        return False
    if not os.path.exists(OUTPUT_PATH):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(OUTPUT_PATH))
    age = datetime.now() - mtime
    if age < timedelta(hours=CACHE_HOURS):
        print(">>> cache is fresh - using cached data.")
        return True
    print(">>> cache is stale - fetching fresh data.")
    return False


def fetch_with_retry(url, params=None):
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            print("   HTTP " + str(r.status_code) + " attempt " + str(attempt))
        except Exception as e:
            print("   attempt " + str(attempt) + " failed: " + str(e)[:120])
        if attempt < max_retries:
            time.sleep(2 * attempt)
    return None


def fetch_series(label, mnemonic):
    """Fetch a single OFR time series via /v1/series/timeseries."""
    print(">>> fetching " + label + " (" + mnemonic + ")...")
    url = OFR_BASE + "/series/timeseries"
    params = {
        "mnemonic": mnemonic,
        "start_date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
    }
    data = fetch_with_retry(url, params)
    log_api_call("OFR/" + mnemonic, "ok" if data else "error")

    if not data:
        return {"status": "empty"}

    # Response is [[date, value], ...] directly
    points = data if isinstance(data, list) else data.get("data", [])
    if not points:
        return {"status": "empty"}

    history = []
    for point in points:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        ts, val = point[0], point[1]
        if val is None:
            continue
        try:
            v = float(val)
        except (ValueError, TypeError):
            continue
        history.append({"date": str(ts)[:10], "value": v})

    if not history:
        return {"status": "empty"}

    history.sort(key=lambda x: x["date"])
    latest = history[-1]
    prior = history[-2] if len(history) > 1 else None

    return {
        "status": "ok",
        "mnemonic": mnemonic,
        "value": latest["value"],
        "period": latest["date"],
        "prior": prior["value"] if prior else None,
        "prior_period": prior["date"] if prior else None,
        "history": history,
        "history_points": len(history),
        "source": "OFR",
    }


def load_cache():
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print(">>> main block entered")

    if cache_is_fresh():
        data = load_cache()
        print(">>> loaded from cache.")
        print(">>> DONE (cached)")
        return

    results = {}
    for label, mnemonic in SERIES_MAP.items():
        results[label] = fetch_series(label, mnemonic)

    output = {
        "source": "OFR",
        "category": "repo_market",
        "fetched_at": datetime.now().isoformat(),
        "series": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved to " + OUTPUT_PATH)
    for key, r in results.items():
        if r.get("status") == "ok":
            print("    " + key + ": " + str(r.get("history_points")) + " points, latest " + str(r.get("value")))
        else:
            print("    " + key + ": " + str(r.get("status")))
    print(">>> DONE")


if __name__ == "__main__":
    main()
