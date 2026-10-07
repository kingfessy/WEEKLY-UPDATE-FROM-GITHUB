print(">>> fetch_fred_banking.py loaded")

import json
import os
import time
from datetime import datetime, timedelta
from fredapi import Fred

print(">>> imports done")

FRED_API_KEY = os.environ.get("FRED_API_KEY")

if not FRED_API_KEY:
    print(">>> ERROR: FRED_API_KEY not set.")
    raise SystemExit(1)

fred = Fred(api_key=FRED_API_KEY)

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "fred_banking.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

SERIES_MAP = {
    "large_bank_deposits":   {"id": "DPSACBW027SBOG", "history_months": 24, "frequency": "weekly"},
    "small_bank_deposits":   {"id": "DPSSCBW027SBOG", "history_months": 24, "frequency": "weekly"},
    "bank_credit_total":     {"id": "TOTBKCR",        "history_months": 24, "frequency": "weekly"},
    "commercial_loans":      {"id": "BUSLOANS",       "history_months": 24, "frequency": "monthly"},
    "bank_total_assets":     {"id": "TLAACBW027SBOG", "history_months": 24, "frequency": "weekly"},
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


def fetch_series(indicator_key, meta):
    series_id = meta["id"]
    months = meta["history_months"]

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
            v = float(value)
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
        "source": "FRED",
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
        "category": "banking",
        "fetched_at": datetime.now().isoformat(),
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
            print("    " + key + ": " + str(r.get("history_points")) + " points, latest " + str(r.get("value")))
    print(">>> DONE")


if __name__ == "__main__":
    main()