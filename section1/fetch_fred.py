print(">>> fetch_fred.py loaded")

import json
import os
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
OUTPUT_PATH = os.path.join(DATA_DIR, "fred.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

# Series metadata with sampling strategy
# "history_months": how many months to store
# "frequency": "daily", "monthly", "quarterly" (for sampling decisions)
SERIES_MAP = {
    "gdp":                    {"id": "GDPC1",    "history_months": 24, "frequency": "quarterly"},
    "cpi":                    {"id": "CPIAUCSL", "history_months": 24, "frequency": "monthly"},
    "core_cpi":               {"id": "CPILFESL", "history_months": 24, "frequency": "monthly"},
    "pce":                    {"id": "PCEPI",    "history_months": 24, "frequency": "monthly"},
    "nonfarm_payrolls":       {"id": "PAYEMS",   "history_months": 24, "frequency": "monthly"},
    "unemployment_rate":      {"id": "UNRATE",   "history_months": 24, "frequency": "monthly"},
    "fed_funds_rate":         {"id": "DFF",      "history_months": 12, "frequency": "daily"},
    "treasury_10y":           {"id": "DGS10",    "history_months": 12, "frequency": "daily"},
    "fed_balance_sheet":      {"id": "WALCL",    "history_months": 24, "frequency": "weekly"},
    "reverse_repo":           {"id": "RRPONTSYD","history_months": 6,  "frequency": "daily"},
    "ism_manufacturing":      {"id": "MANEMP",   "history_months": 24, "frequency": "monthly"},
}


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


def downsample_daily(history, frequency):
    """
    If frequency is daily, downsample to weekly to keep JSON manageable.
    Otherwise return history as-is.
    """
    if frequency != "daily":
        return history
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
    history_months = meta["history_months"]
    frequency = meta["frequency"]

    print(">>> fetching " + indicator_key + " (" + series_id + ")...")
    try:
        start_date = datetime.now() - timedelta(days=history_months * 31)
        series = fred.get_series(series_id, observation_start=start_date.strftime("%Y-%m-%d"))
    except Exception as e:
        print("   error on " + series_id + ": " + str(e))
        return {"status": "error", "error": str(e)}

    if series is None or len(series) == 0:
        print("   no data for " + series_id)
        return {"status": "empty"}

    # Build history list
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

    # Downsample daily data to weekly
    history = downsample_daily(history, frequency)

    if not history:
        print("   no valid history for " + series_id)
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
        ok = data.get("count_ok", 0)
        total = data.get("count_total", 0)
        print(">>> loaded " + str(ok) + "/" + str(total) + " series from cache.")
        print(">>> set FORCE_REFRESH=true to bypass cache.")
        print(">>> DONE (cached)")
        return

    results = {}
    for key, meta in SERIES_MAP.items():
        results[key] = fetch_series(key, meta)

    output = {
        "source": "FRED",
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
