print(">>> fetch_fred_liquidity.py loaded")

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
OUTPUT_PATH = os.path.join(DATA_DIR, "fred_liquidity.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

# scale: multiply FRED's raw value to normalize to billions of USD
# WTREGEN reports in millions, so scale = 0.001 to convert to billions
SERIES_MAP = {
    "m2_money_supply":  {"id": "M2SL",       "history_months": 24, "frequency": "monthly", "scale": 1.0},
    "tga_balance":      {"id": "WTREGEN",    "history_months": 12, "frequency": "weekly",  "scale": 0.001},
    "on_rrp_balance":   {"id": "RRPONTSYD",  "history_months": 6,  "frequency": "daily",   "scale": 1.0},
    "sofr":             {"id": "SOFR",       "history_months": 6,  "frequency": "daily",   "scale": 1.0},
    "effr":             {"id": "EFFR",       "history_months": 6,  "frequency": "daily",   "scale": 1.0},
    "iorb":             {"id": "IORB",       "history_months": 6,  "frequency": "daily",   "scale": 1.0},
}


def log_api_call(series_id, status):
    log_path = os.path.join(DATA_DIR, "_api_log.json")
    entry = {"ts": datetime.now().isoformat(), "source": "FRED", "series": series_id, "status": status}
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
        print(">>> cache is fresh (age: " + str(round(age.total_seconds() / 3600, 1)) + "h) - using cached data.")
        return True
    print(">>> cache is stale - fetching fresh data.")
    return False


def downsample_daily(history):
    sampled = []
    last_date = None
    for point in history:
        try:
            d = datetime.strptime(point["date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            sampled.append(point)
            continue
        if last_date is None or (d - last_date).days >= 7:
            sampled.append(point)
            last_date = d
    return sampled


def fetch_series(indicator_key, meta):
    series_id = meta["id"]
    months = meta["history_months"]
    freq = meta["frequency"]
    scale = meta.get("scale", 1.0)

    print(">>> fetching " + indicator_key + " (" + series_id + ")...")
    max_retries = 3
    series = None
    for attempt in range(1, max_retries + 1):
        try:
            start = datetime.now() - timedelta(days=months * 31)
            series = fred.get_series(series_id, observation_start=start.strftime("%Y-%m-%d"))
            log_api_call(series_id, "ok")
            break
        except Exception as e:
            print("   attempt " + str(attempt) + " failed: " + str(e)[:120])
            log_api_call(series_id, "error")
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            return {"status": "error", "error": str(e)}

    if series is None or len(series) == 0:
        print("   no data for " + series_id)
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

    if freq == "daily":
        history = downsample_daily(history)

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
        "source": "FRED",
        "scale_applied": scale,
    }


def load_cache():
    with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    print(">>> main block entered")

    if cache_is_fresh():
        data = load_cache()
        print(">>> loaded " + str(data.get("count_ok", 0)) + "/" + str(data.get("count_total", 0)) + " from cache.")
        print(">>> DONE (cached)")
        return

    results = {}
    for key, meta in SERIES_MAP.items():
        results[key] = fetch_series(key, meta)

    output = {
        "source": "FRED",
        "category": "liquidity",
        "fetched_at": datetime.now().isoformat(),
        "units": "billions_usd_except_rates",
        "count_ok": sum(1 for r in results.values() if r.get("status") == "ok"),
        "count_total": len(results),
        "series": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved " + str(output["count_ok"]) + "/" + str(output["count_total"]) + " series to " + OUTPUT_PATH)
    for key, r in results.items():
        if r.get("status") == "ok":
            print("    " + key + ": " + str(r.get("history_points")) + " points, latest " + str(round(r.get("value"), 3)))
    print(">>> DONE")


if __name__ == "__main__":
    main()
