print(">>> fetch_fdic.py loaded")

import json
import os
import time
from datetime import datetime, timedelta

import requests

print(">>> imports done")

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "fdic.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

# FDIC BankFind API (free, no key required)
FDIC_BASE = "https://banks.data.fdic.gov/api"


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


def fetch_recent_failures():
    """Fetch banks that failed in the last 2 years."""
    print(">>> fetching recent bank failures...")
    url = FDIC_BASE + "/failures"
    params = {
        "filters": "FAILDATE:[2024-01-01 TO 2026-12-31]",
        "fields": "NAME,CITY,STALP,FAILDATE,SAVR,COST,RESTYPE,CERT",
        "sort_by": "FAILDATE",
        "sort_order": "DESC",
        "limit": "50",
        "format": "json",
    }
    data = fetch_with_retry(url, params)
    log_api_call("FDIC/Failures", "ok" if data else "error")
    if not data or "data" not in data:
        return {"status": "empty", "failures": []}

    records = data["data"]
    failures = []
    for rec in records:
        d = rec.get("data", {})
        failures.append({
            "name": d.get("NAME"),
            "city": d.get("CITY"),
            "state": d.get("STALP"),
            "fail_date": d.get("FAILDATE"),
            "resolution": d.get("RESTYPE"),
            "cost_estimate": d.get("COST"),
        })

    return {
        "status": "ok",
        "count": len(failures),
        "failures": failures,
        "source": "FDIC",
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

    failures = fetch_recent_failures()

    output = {
        "source": "FDIC",
        "category": "bank_failures",
        "fetched_at": datetime.now().isoformat(),
        "recent_failures": failures,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved to " + OUTPUT_PATH)
    if failures.get("status") == "ok":
        print("    recent_failures: " + str(failures["count"]) + " banks")
        for f in failures.get("failures", [])[:3]:
            print("      " + str(f.get("fail_date")) + " - " + str(f.get("name")) + " (" + str(f.get("state")) + ")")
    else:
        print("    recent_failures: " + str(failures.get("status")))
    print(">>> DONE")


if __name__ == "__main__":
    main()