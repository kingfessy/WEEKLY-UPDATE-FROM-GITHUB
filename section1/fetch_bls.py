print(">>> fetch_bls.py loaded")

import json
import os
import requests
from datetime import datetime, timedelta

print(">>> imports done")

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "bls.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

SERIES_MAP = {
    "unemployment_rate": "LNS14000000",
    "nonfarm_payrolls": "CES0000000001",
    "cpi": "CUUR0000SA0",
    "core_cpi": "CUUR0000SA0L1E",
}


def cache_is_fresh():
    if FORCE_REFRESH:
        print(">>> FORCE_REFRESH is true — bypassing cache.")
        return False
    if not os.path.exists(OUTPUT_PATH):
        return False
    mtime = datetime.fromtimestamp(os.path.getmtime(OUTPUT_PATH))
    age = datetime.now() - mtime
    if age < timedelta(hours=CACHE_HOURS):
        print(">>> cache is fresh (age: " + str(round(age.total_seconds() / 3600, 1)) + "h) — using cached data.")
        return True
    print(">>> cache is stale — fetching fresh data.")
    return False


def fetch_bls_series(series_ids):
    payload = {
        "seriesid": series_ids,
        "startyear": str(datetime.now().year - 1),
        "endyear": str(datetime.now().year),
    }
    try:
        r = requests.post(BLS_URL, json=payload, timeout=30)
        if r.status_code != 200:
            print("   BLS HTTP " + str(r.status_code))
            return None
        return r.json()
    except Exception as e:
        print("   BLS error: " + str(e))
        return None


def parse_bls_response(data):
    results = {}
    if not data or data.get("status") != "REQUEST_SUCCEEDED":
        print("   BLS status: " + str(data.get("status") if data else "no data"))
        if data and data.get("message"):
            for m in data.get("message", []):
                print("   msg: " + str(m))
        return results

    for series in data.get("Results", {}).get("series", []):
        series_id = series.get("seriesID")
        series_data = series.get("data", [])

        sorted_data = sorted(
            series_data,
            key=lambda x: (x.get("year", "0"), x.get("period", "M0")),
            reverse=True,
        )

        matched_key = None
        for key, sid in SERIES_MAP.items():
            if sid == series_id:
                matched_key = key
                break

        if not matched_key:
            continue

        if not sorted_data:
            results[matched_key] = {"status": "empty", "series_id": series_id}
            continue

        latest = sorted_data[0]
        prior = sorted_data[1] if len(sorted_data) > 1 else None

        year = latest.get("year", "")
        period_code = latest.get("period", "")
        month = period_code.replace("M", "")

        if month and month.isdigit() and month != "13":
            period_iso = year + "-" + month.zfill(2) + "-01"
        else:
            period_iso = year

        try:
            value = float(latest.get("value", "0"))
        except ValueError:
            value = None

        try:
            prior_value = float(prior.get("value", "0")) if prior else None
        except ValueError:
            prior_value = None

        results[matched_key] = {
            "status": "ok",
            "series_id": series_id,
            "value": value,
            "period": period_iso,
            "period_name": latest.get("periodName", ""),
            "prior": prior_value,
            "source": "BLS",
        }

    return results


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

    print(">>> requesting " + str(len(SERIES_MAP)) + " BLS series...")
    raw = fetch_bls_series(list(SERIES_MAP.values()))

    if not raw:
        print(">>> BLS fetch failed. Writing empty result.")
        results = {k: {"status": "error", "series_id": v} for k, v in SERIES_MAP.items()}
    else:
        results = parse_bls_response(raw)
        for key, sid in SERIES_MAP.items():
            if key not in results:
                results[key] = {"status": "empty", "series_id": sid}

    output = {
        "source": "BLS",
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