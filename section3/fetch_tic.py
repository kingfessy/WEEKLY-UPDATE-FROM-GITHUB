print(">>> fetch_tic.py loaded")

import json
import os
import time
import urllib.request
from datetime import datetime, timedelta

from fredapi import Fred

print(">>> imports done")

FRED_API_KEY = os.environ.get("FRED_API_KEY")

if not FRED_API_KEY:
    print(">>> ERROR: FRED_API_KEY not set.")
    raise SystemExit(1)

# Patch urlopen with a 30s timeout to prevent hangs
_original_urlopen = urllib.request.urlopen

def _urlopen_with_timeout(url, *args, **kwargs):
    kwargs.setdefault("timeout", 30)
    return _original_urlopen(url, *args, **kwargs)

urllib.request.urlopen = _urlopen_with_timeout

fred = Fred(api_key=FRED_API_KEY)

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "tic.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

# FRED TIC series report in MILLIONS of USD — scale to billions
SERIES_MAP = {
    "foreign_official":       {"id": "FORTREASPOS99990", "scale": 0.001},
    "japan":                  {"id": "FORTREASPOS42609", "scale": 0.001},
    "china_mainland":         {"id": "FORTREASPOS41408", "scale": 0.001},
    "united_kingdom":         {"id": "FORTREASPOS13005", "scale": 0.001},
}


def log_api_call(series_id, status):
    log_path = os.path.join(DATA_DIR, "_api_log.json")
    entry = {"ts": datetime.now().isoformat(), "source": "FRED/TIC", "series": series_id, "status": status}
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


def fetch_series(label, series_id, scale=1.0):
    print(">>> fetching " + label + " (" + series_id + ")...")
    max_retries = 2
    series = None
    for attempt in range(1, max_retries + 1):
        try:
            start = datetime.now() - timedelta(days=730)
            series = fred.get_series(series_id, observation_start=start.strftime("%Y-%m-%d"))
            log_api_call(series_id, "ok")
            break
        except Exception as e:
            print("   attempt " + str(attempt) + " failed: " + str(e)[:120])
            log_api_call(series_id, "error")
            if attempt < max_retries:
                time.sleep(3)
                continue
            return {"status": "error", "error": str(e)}

    if series is None or len(series) == 0:
        return {"status": "empty"}

    history = []
    for date, value in series.items():
        if value is None:
            continue
        try:
            v = float(value) * scale
        except (ValueError, TypeError):
            continue
        history.append({
            "date": date.strftime("%Y-%m-%d") if hasattr(date, "strftime") else str(date),
            "value": v,
        })

    if not history:
        return {"status": "empty"}

    latest = history[-1]
    prior = history[-2] if len(history) > 1 else None

    return {
        "status": "ok",
        "series_id": series_id,
        "value": latest["value"],
        "period": latest["date"],
        "prior": prior["value"] if prior else None,
        "prior_period": prior["date"] if prior else None,
        "history": history,
        "history_points": len(history),
        "source": "FRED (mirror of Treasury TIC)",
        "scale_applied": scale,
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
    for label, meta in SERIES_MAP.items():
        results[label] = fetch_series(label, meta["id"], meta.get("scale", 1.0))

    output = {
        "source": "FRED (Treasury TIC data)",
        "category": "tic",
        "fetched_at": datetime.now().isoformat(),
        "lag_note": "TIC data published with ~1.5-month lag. Values reflect latest available.",
        "units": "billions_usd",
        "series": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved to " + OUTPUT_PATH)
    for key, r in results.items():
        if r.get("status") == "ok":
            print("    " + key + ": " + str(r["history_points"]) + " points, latest " + str(round(r["value"], 2)))
        else:
            print("    " + key + ": " + str(r.get("status")))
    print(">>> DONE")


if __name__ == "__main__":
    main()
