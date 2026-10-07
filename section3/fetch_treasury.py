print(">>> fetch_treasury.py loaded")

import json
import os
import time
from datetime import datetime, timedelta

import requests

print(">>> imports done")

DATA_DIR = "archive/data"
os.makedirs(DATA_DIR, exist_ok=True)
OUTPUT_PATH = os.path.join(DATA_DIR, "treasury.json")

CACHE_HOURS = 24
FORCE_REFRESH = os.environ.get("FORCE_REFRESH", "false").lower() == "true"

# Correct base URL and versioned endpoints
FISCAL_BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"


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


def fetch_debt_to_penny():
    print(">>> fetching Debt to the Penny...")
    url = FISCAL_BASE + "/v2/accounting/od/debt_to_penny"
    params = {
        "sort": "-record_date",
        "page[size]": "30",
    }
    data = fetch_with_retry(url, params)
    log_api_call("Treasury/DebtToThePenny", "ok" if data else "error")
    if not data or "data" not in data:
        return {"status": "empty"}

    records = data["data"]
    if not records:
        return {"status": "empty"}

    history = []
    for rec in records:
        date = rec.get("record_date")
        value = rec.get("tot_pub_debt_out_amt")
        if date and value:
            try:
                history.append({"date": date, "value": float(value)})
            except (ValueError, TypeError):
                continue

    if not history:
        return {"status": "empty"}

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
        "source": "Treasury FiscalData",
    }


def fetch_recent_auctions():
    print(">>> fetching recent Treasury auctions...")
    url = FISCAL_BASE + "/v1/accounting/od/auctions_query"
    params = {
        "sort": "-auction_date",
        "page[size]": "100",
    }
    data = fetch_with_retry(url, params)
    log_api_call("Treasury/Auctions", "ok" if data else "error")
    if not data or "data" not in data:
        return {"status": "empty"}

    records = data["data"]
    auctions = []
    for rec in records:
        auctions.append({
            "date": rec.get("auction_date"),
            "security_type": rec.get("security_type"),
            "security_term": rec.get("security_term"),
            "high_yield": rec.get("high_yield"),
            "bid_to_cover": rec.get("bid_to_cover_ratio"),
            "offering_amount": rec.get("offering_amt"),
            "total_accepted": rec.get("total_accepted"),
        })

    return {
        "status": "ok",
        "count": len(auctions),
        "auctions": auctions,
        "source": "Treasury FiscalData",
    }


def fetch_interest_expense():
    print(">>> fetching interest expense...")
    url = FISCAL_BASE + "/v2/accounting/od/interest_expense"
    params = {
        "sort": "-record_date",
        "page[size]": "12",
    }
    data = fetch_with_retry(url, params)
    log_api_call("Treasury/InterestExpense", "ok" if data else "error")
    if not data or "data" not in data:
        return {"status": "empty"}

    records = data["data"]
    history = []
    for rec in records:
        date = rec.get("record_date")
        value = rec.get("interest_expense_amt") or rec.get("month_expense_amt")
        if date and value:
            try:
                history.append({"date": date, "value": float(value)})
            except (ValueError, TypeError):
                continue

    if not history:
        return {"status": "empty"}

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
        "source": "Treasury FiscalData",
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

    debt = fetch_debt_to_penny()
    auctions = fetch_recent_auctions()
    interest = fetch_interest_expense()

    output = {
        "source": "Treasury FiscalData",
        "category": "treasury",
        "fetched_at": datetime.now().isoformat(),
        "debt_to_penny": debt,
        "recent_auctions": auctions,
        "interest_expense": interest,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved to " + OUTPUT_PATH)
    if debt.get("status") == "ok":
        print("    debt_to_penny: $" + str(round(debt["value"] / 1e12, 2)) + "T (" + str(debt["period"]) + ")")
    else:
        print("    debt_to_penny: " + str(debt.get("status")))
    if auctions.get("status") == "ok":
        print("    recent_auctions: " + str(auctions["count"]) + " auctions")
    else:
        print("    recent_auctions: " + str(auctions.get("status")))
    if interest.get("status") == "ok":
        print("    interest_expense: $" + str(round(interest["value"] / 1e9, 1)) + "B (" + str(interest["period"]) + ")")
    else:
        print("    interest_expense: " + str(interest.get("status")))
    print(">>> DONE")


if __name__ == "__main__":
    main()
