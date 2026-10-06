print(">>> fetch_bea.py loaded")

import json
import os
import requests
from datetime import datetime, timedelta

print(">>> imports done")

BEA_API_KEY = os.environ.get("BEA_API_KEY")

if not BEA_API_KEY:
    print(">>> ERROR: BEA_API_KEY not set.")
    raise SystemExit(1)

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "bea.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

BEA_BASE = "https://apps.bea.gov/api/data"

# BEA NIPA table mapping
# T10101 = Real GDP (quarterly)
# T20804 = PCE Price Index (monthly)
BEA_QUERIES = {
    "gdp": {
        "datasetname": "NIPA",
        "tablename": "T10101",
        "frequency": "Q",
        "year": "X",
    },
    "pce": {
        "datasetname": "NIPA",
        "tablename": "T20804",
        "frequency": "M",
        "year": "X",
    },
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


def fetch_bea(indicator_key, params):
    query = {
        "UserID": BEA_API_KEY,
        "method": "GetData",
        "ResultFormat": "JSON",
        "datasetname": params["datasetname"],
        "TableName": params["tablename"],
        "Frequency": params["frequency"],
        "Year": params["year"],
    }

    print(">>> fetching " + indicator_key + " from BEA (" + params["tablename"] + ")...")
    try:
        r = requests.get(BEA_BASE, params=query, timeout=30)
        if r.status_code != 200:
            print("   BEA HTTP " + str(r.status_code))
            return {"status": "error", "http": r.status_code}
        data = r.json()
    except Exception as e:
        print("   BEA error: " + str(e))
        return {"status": "error", "error": str(e)}

    # Check for API-level errors
    bea_api = data.get("BEAAPI", {})
    results = bea_api.get("Results", {})

    # Some BEA responses nest Error inside Results
    if isinstance(results, dict) and results.get("Error"):
        err = results["Error"]
        print("   BEA API error: " + str(err))
        return {"status": "error", "error": str(err)}

    # Extract rows
    rows = None
    if isinstance(results, dict):
        rows = results.get("Data")
    elif isinstance(results, list):
        # Sometimes Results is a list
        for item in results:
            if isinstance(item, dict) and "Data" in item:
                rows = item["Data"]
                break

    if not rows:
        # Proactive diagnostic: dump the top-level keys we received
        print("   BEA response has no Data field. Top-level keys: " + str(list(bea_api.keys())))
        if isinstance(results, dict):
            print("   Results keys: " + str(list(results.keys())))
        return {"status": "empty", "raw_keys": list(bea_api.keys())}

    # Sort by TimePeriod
    sorted_rows = sorted(rows, key=lambda row: row.get("TimePeriod", ""))

    latest = sorted_rows[-1]
    prior = sorted_rows[-2] if len(sorted_rows) > 1 else None

    try:
        value = float(str(latest.get("DataValue", "0")).replace(",", ""))
    except (ValueError, AttributeError):
        value = None

    try:
        prior_value = float(str(prior.get("DataValue", "0")).replace(",", "")) if prior else None
    except (ValueError, AttributeError):
        prior_value = None

    return {
        "status": "ok",
        "value": value,
        "period": latest.get("TimePeriod", ""),
        "period_name": latest.get("TimePeriod", ""),
        "prior": prior_value,
        "source": "BEA",
        "table": params["tablename"],
        "line_description": latest.get("LineDescription", ""),
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
    for key, params in BEA_QUERIES.items():
        results[key] = fetch_bea(key, params)

    output = {
        "source": "BEA",
        "fetched_at": datetime.now().isoformat(),
        "count_ok": sum(1 for r in results.values() if r.get("status") == "ok"),
        "count_total": len(results),
        "series": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print(">>> saved " + str(output["count_ok"]) + "/" + str(output["count_total"]) + " series to " + OUTPUT_PATH)
    print(">>> DONE")


if __name__ == "__main__":
    main()