print(">>> aggregate.py loaded")

import json
import os
from datetime import datetime

print(">>> imports done")

DATA_DIR = "archive/data"
OUTPUT_PATH = os.path.join(DATA_DIR, "aggregated.json")

INDICATOR_PRIORITY = {
    "gdp":                    [("fred.json", "gdp"), ("bea.json", "gdp")],
    "cpi":                    [("fred.json", "cpi"), ("bls.json", "cpi")],
    "core_cpi":               [("fred.json", "core_cpi"), ("bls.json", "core_cpi")],
    "pce":                    [("fred.json", "pce"), ("bea.json", "pce")],
    "nonfarm_payrolls":       [("fred.json", "nonfarm_payrolls"), ("bls.json", "nonfarm_payrolls")],
    "unemployment_rate":      [("fred.json", "unemployment_rate"), ("bls.json", "unemployment_rate")],
    "fed_funds_rate":         [("fred.json", "fed_funds_rate")],
    "treasury_10y":           [("fred.json", "treasury_10y")],
    "fed_balance_sheet":      [("fred.json", "fed_balance_sheet")],
    "reverse_repo":           [("fred.json", "reverse_repo")],
    "manufacturing_employment": [("fred.json", "ism_manufacturing")],
    "bis_cross_border_credit":[("global.json", "bis_cross_border_credit")],
    "imf_world_gdp_growth":   [("global.json", "imf_world_gdp_growth")],
    "ecb_deposit_rate":       [("global.json", "ecb_deposit_rate")],
}

DISPLAY_NAMES = {
    "gdp": "US Real GDP",
    "cpi": "US CPI",
    "core_cpi": "US Core CPI",
    "pce": "US PCE Price Index",
    "nonfarm_payrolls": "US Nonfarm Payrolls",
    "unemployment_rate": "US Unemployment Rate",
    "fed_funds_rate": "US Fed Funds Rate",
    "treasury_10y": "US 10Y Treasury Yield",
    "fed_balance_sheet": "Fed Balance Sheet",
    "reverse_repo": "Reverse Repo Facility",
    "manufacturing_employment": "US Manufacturing Employment",
    "bis_cross_border_credit": "BIS Cross-Border Credit",
    "imf_world_gdp_growth": "IMF World GDP Growth",
    "ecb_deposit_rate": "ECB Deposit Rate",
}

UNITS = {
    "gdp": "billion_usd",
    "cpi": "index",
    "core_cpi": "index",
    "pce": "index",
    "nonfarm_payrolls": "thousand_jobs",
    "unemployment_rate": "percent",
    "fed_funds_rate": "percent",
    "treasury_10y": "percent",
    "fed_balance_sheet": "million_usd",
    "reverse_repo": "billion_usd",
    "manufacturing_employment": "thousand_jobs",
    "bis_cross_border_credit": "billion_usd",
    "imf_world_gdp_growth": "percent",
    "ecb_deposit_rate": "percent",
}

COUNTRIES = {
    "gdp": "US", "cpi": "US", "core_cpi": "US", "pce": "US",
    "nonfarm_payrolls": "US", "unemployment_rate": "US",
    "fed_funds_rate": "US", "treasury_10y": "US",
    "fed_balance_sheet": "US", "reverse_repo": "US",
    "manufacturing_employment": "US",
    "bis_cross_border_credit": "Global",
    "imf_world_gdp_growth": "Global",
    "ecb_deposit_rate": "Euro Area",
}


def load_source(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(">>> warning: " + filename + " not found")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_value(value, unit):
    if value is None:
        return "N/A"
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)

    if unit == "billion_usd":
        if abs(v) >= 1000:
            return "$" + str(round(v / 1000, 2)) + "T"
        return "$" + str(round(v, 1)) + "B"
    if unit == "million_usd":
        if abs(v) >= 1_000_000:
            return "$" + str(round(v / 1_000_000, 2)) + "T"
        if abs(v) >= 1000:
            return "$" + str(round(v / 1000, 1)) + "B"
        return "$" + str(round(v, 1)) + "M"
    if unit == "thousand_jobs":
        if abs(v) >= 1000:
            return str(round(v / 1000, 1)) + "M jobs"
        return str(int(v)) + "K jobs"
    if unit == "percent":
        return str(round(v, 2)) + "%"
    if unit == "index":
        return str(round(v, 2))
    return str(v)


def compute_change(value, prior, unit):
    if value is None or prior is None:
        return ("unknown", "")
    try:
        diff = float(value) - float(prior)
    except (TypeError, ValueError):
        return ("unknown", "")

    if abs(diff) < 1e-9:
        return ("unchanged", "unchanged")

    if unit == "percent":
        amount = str(abs(round(diff, 2))) + " percentage points"
    elif unit == "thousand_jobs":
        amount = str(abs(int(diff))) + "K jobs"
    elif unit in ("billion_usd", "million_usd"):
        amount = format_value(abs(diff), unit).lstrip("$")
        amount = "$" + amount
    else:
        amount = str(abs(round(diff, 2)))

    if diff > 0:
        return ("up", amount)
    else:
        return ("down", amount)


def build_note(display_name, value, prior, unit, period):
    formatted_value = format_value(value, unit)
    direction, amount = compute_change(value, prior, unit)

    if direction == "unchanged":
        return display_name + " held at " + formatted_value + " for " + str(period) + ", unchanged from the prior reading."
    elif direction == "up":
        return display_name + " rose to " + formatted_value + " for " + str(period) + ", up " + amount + " from the prior period."
    elif direction == "down":
        return display_name + " fell to " + formatted_value + " for " + str(period) + ", down " + amount + " from the prior period."
    else:
        return display_name + " stood at " + formatted_value + " for " + str(period) + "."


def pick_value(indicator, sources):
    for filename, series_key in INDICATOR_PRIORITY[indicator]:
        source_data = sources.get(filename)
        if not source_data:
            continue
        series = source_data.get("series", {}).get(series_key)
        if not series:
            continue
        if series.get("status") != "ok":
            continue
        if series.get("value") is None:
            continue
        return {
            "value": series.get("value"),
            "period": series.get("period"),
            "prior": series.get("prior"),
            "source_used": filename.replace(".json", "").upper(),
            "series_id": series.get("series_id") or series.get("series_code"),
            "history": series.get("history", []),
        }
    return None


def main():
    print(">>> main block entered")

    sources = {
        "fred.json": load_source("fred.json"),
        "bls.json": load_source("bls.json"),
        "bea.json": load_source("bea.json"),
        "global.json": load_source("global.json"),
    }

    results = {}
    missing = []

    for indicator in INDICATOR_PRIORITY.keys():
        picked = pick_value(indicator, sources)
        if picked:
            note = build_note(
                DISPLAY_NAMES[indicator],
                picked["value"],
                picked["prior"],
                UNITS[indicator],
                picked["period"],
            )
            results[indicator] = {
                "display_name": DISPLAY_NAMES[indicator],
                "country": COUNTRIES[indicator],
                "unit": UNITS[indicator],
                "value": picked["value"],
                "period": picked["period"],
                "prior": picked["prior"],
                "source_used": picked["source_used"],
                "series_id": picked["series_id"],
                "history": picked.get("history", []),
                "note": note,
            }
            print(">>> " + indicator + ": " + note + " [history: " + str(len(picked.get("history", []))) + " points]")
        else:
            missing.append(indicator)
            print(">>> " + indicator + ": NOT FOUND")

    output = {
        "aggregated_at": datetime.now().isoformat(),
        "total_indicators": len(INDICATOR_PRIORITY),
        "found_count": len(results),
        "missing_count": len(missing),
        "missing": missing,
        "indicators": results,
    }

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved " + str(len(results)) + "/" + str(len(INDICATOR_PRIORITY)) + " indicators to " + OUTPUT_PATH)
    print(">>> DONE")


if __name__ == "__main__":
    main()
