print(">>> fetch_global.py loaded")

import json
import os
import time
import requests
from datetime import datetime, timedelta

print(">>> imports done")

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "global.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

DB_NOMICS_API = "https://api.db.nomics.world/v22"

SERIES_MAP = {
    "bis_cross_border_credit": {"provider": "BIS", "dataset": "WS_TC", "series": "Q.US.N.A.M.XDC.A"},
    "imf_world_gdp_growth":    {"provider": "IMF", "dataset": "WEO:2024-10", "series": "USA.NGDP_RPCH"},
    "ecb_deposit_rate":        {"provider": "NBB", "dataset": "IRESCB", "series": "DPF.A"},
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
        print(">>> cache is fresh - using cached data.")
        return True
    print(">>> cache is stale - fetching fresh data.")
    return False


def fetch_series_via_http(provider, dataset, series_code):
    url = DB_NOMICS_API + "/series/" + provider + "/" + dataset + "/" + series_code
    params = {"observations": "1", "offset": "0"}
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            r = requests.get(url, params=params, timeout=60)
            if r.status_code != 200:
                return {"status": "error", "http": r.status_code}
            return r.json()
        except requests.exceptions.ConnectionError as e:
            print("   attempt " + str(attempt) + " failed (connection): " + str(e)[:120])
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            return {"status": "error", "error": str(e)}
        except Exception as e:
            print("   attempt " + str(attempt) + " failed: " + str(e)[:120])
            if attempt < max_retries:
                time.sleep(2 * attempt)
                continue
            return {"status": "error", "error": str(e)}
    return {"status": "error", "error": "max retries exceeded"}


def parse_series_json(data, current_year):
    try:
        series = data["series"]["docs"][0]
    except (KeyError, IndexError, TypeError):
        return None

    periods = series.get("period", [])
    values = series.get("value", [])

    history = []
    for p, v in zip(periods, values):
        if v is None or v == "NA":
            continue
        p_str = str(p)
        year_str = ""
        for ch in p_str:
            if ch.isdigit():
                year_str += ch
            else:
                break
        if year_str:
            try:
                if int(year_str) > current_year:
                    continue
            except ValueError:
                pass
        try:
            v_float = float(v)
        except (ValueError, TypeError):
            continue
        history.append({"date": p_str, "value": v_float})

    if not history:
        return None

    history.sort(key=lambda x: x["date"])

    latest = history[-1]
    prior = history[-2] if len(history) > 1 else None

    return {
        "status": "ok",
        "value": latest["value"],
        "period": latest["date"],
        "prior": prior["value"] if prior else None,
        "prior_period": prior["date"] if prior else None,
        "history": history,
        "history_points": len(history),
    }


def fetch_indicator(indicator_key, meta):
    provider = meta["provider"]
    dataset = meta["dataset"]
    series_code = meta["series"]
    print(">>> fetching " + indicator_key + " (" + provider + "/" + dataset + "/" + series_code + ")...")

    raw = fetch_series_via_http(provider, dataset, series_code)
    if raw.get("status") == "error":
        print("   error: " + str(raw))
        return raw

    current_year = datetime.now().year
    parsed = parse_series_json(raw, current_year)
    if not parsed:
        print("   no valid data in response")
        return {"status": "empty"}

    parsed["provider"] = provider
    parsed["dataset"] = dataset
    parsed["series_code"] = series_code
    parsed["source"] = "DBnomics (" + provider + ")"
    print("   value = " + str(parsed["value"]) + " (period " + str(parsed["period"]) + ", " + str(parsed["history_points"]) + " points)")
    return parsed


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
    for key, meta in SERIES_MAP.items():
        results[key] = fetch_indicator(key, meta)

    output = {
        "source": "DBnomics",
        "fetched_at": datetime.now().isoformat(),
        "count_ok": sum(1 for r in results.values() if r.get("status") == "ok"),
        "count_total": len(results),
        "series": results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved " + str(output["count_ok"]) + "/" + str(output["count_total"]) + " series to " + OUTPUT_PATH)
    print(">>> DONE")


if __name__ == "__main__":
    main()
