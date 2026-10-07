print(">>> aggregate.py loaded")

import json
import os
from datetime import datetime

print(">>> imports done")

DATA_DIR = "archive/data"
OUTPUT_PATH = os.path.join(DATA_DIR, "section3_aggregated.json")

INDICATOR_PRIORITY = {
    "m2_money_supply":          [("fred_liquidity.json", "m2_money_supply")],
    "tga_balance":              [("fred_liquidity.json", "tga_balance")],
    "on_rrp_balance":           [("fred_liquidity.json", "on_rrp_balance")],
    "sofr":                     [("fred_liquidity.json", "sofr")],
    "effr":                     [("fred_liquidity.json", "effr")],
    "iorb":                     [("fred_liquidity.json", "iorb")],
    "large_bank_deposits":      [("fred_banking.json", "large_bank_deposits")],
    "small_bank_deposits":      [("fred_banking.json", "small_bank_deposits")],
    "bank_credit_total":        [("fred_banking.json", "bank_credit_total")],
    "commercial_loans":         [("fred_banking.json", "commercial_loans")],
    "bank_total_assets":        [("fred_banking.json", "bank_total_assets")],
    "dvp_overnight_rate":       [("ofr.json", "dvp_overnight_rate")],
    "triparty_overnight_rate":  [("ofr.json", "triparty_overnight_rate")],
    "gcf_overnight_rate":       [("ofr.json", "gcf_overnight_rate")],
    "foreign_official":         [("tic.json", "foreign_official")],
    "japan_holdings":           [("tic.json", "japan")],
    "china_holdings":           [("tic.json", "china_mainland")],
    "uk_holdings":              [("tic.json", "united_kingdom")],
}

DISPLAY_NAMES = {
    "m2_money_supply":          "US M2 Money Supply",
    "tga_balance":              "Treasury General Account",
    "on_rrp_balance":           "Overnight Reverse Repo",
    "sofr":                     "SOFR",
    "effr":                     "EFFR",
    "iorb":                     "IORB",
    "large_bank_deposits":      "Large Bank Deposits",
    "small_bank_deposits":      "Small Bank Deposits",
    "bank_credit_total":        "Total Bank Credit",
    "commercial_loans":         "Commercial Loans",
    "bank_total_assets":        "Total Bank Assets",
    "dvp_overnight_rate":       "DVP Repo Rate",
    "triparty_overnight_rate":  "Tri-Party Repo Rate",
    "gcf_overnight_rate":       "GCF Repo Rate",
    "foreign_official":         "Foreign Official Treasury Holdings",
    "japan_holdings":           "Japan Treasury Holdings",
    "china_holdings":           "China Treasury Holdings",
    "uk_holdings":              "UK Treasury Holdings",
}

UNITS = {
    "m2_money_supply":          "billion_usd",
    "tga_balance":              "billion_usd",
    "on_rrp_balance":           "billion_usd",
    "sofr":                     "percent",
    "effr":                     "percent",
    "iorb":                     "percent",
    "large_bank_deposits":      "billion_usd",
    "small_bank_deposits":      "billion_usd",
    "bank_credit_total":        "billion_usd",
    "commercial_loans":         "billion_usd",
    "bank_total_assets":        "billion_usd",
    "dvp_overnight_rate":       "percent",
    "triparty_overnight_rate":  "percent",
    "gcf_overnight_rate":       "percent",
    "foreign_official":         "billion_usd",
    "japan_holdings":           "billion_usd",
    "china_holdings":           "billion_usd",
    "uk_holdings":              "billion_usd",
}


def load_source(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        print(">>> warning: " + filename + " not found")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_value(value, unit):
    """Format a raw numeric value for display. All *_usd values are in billions."""
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
    if unit == "percent":
        return str(round(v, 3)) + "%"
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
        amount = str(abs(round(diff, 3))) + " percentage points"
    elif unit == "billion_usd":
        amount = format_value(abs(diff), unit)
    else:
        amount = str(abs(round(diff, 2)))

    if diff > 0:
        return ("up", amount)
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
        series_container = source_data.get("series", source_data)
        series = series_container.get(series_key)
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
            "series_id": series.get("series_id") or series.get("mnemonic") or series.get("series_code"),
            "history": series.get("history", []),
        }
    return None


def main():
    print(">>> main block entered")

    sources = {
        "fred_liquidity.json": load_source("fred_liquidity.json"),
        "fred_banking.json": load_source("fred_banking.json"),
        "ofr.json": load_source("ofr.json"),
        "tic.json": load_source("tic.json"),
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
                "unit": UNITS[indicator],
                "value": picked["value"],
                "period": picked["period"],
                "prior": picked["prior"],
                "source_used": picked["source_used"],
                "series_id": picked["series_id"],
                "history": picked.get("history", []),
                "note": note,
            }
            print(">>> " + indicator + ": " + note + " [history: " + str(len(picked.get("history", []))) + "]")
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

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    print("")
    print(">>> saved " + str(len(results)) + "/" + str(len(INDICATOR_PRIORITY)) + " indicators to " + OUTPUT_PATH)
    if missing:
        print(">>> missing: " + str(missing))
    print(">>> DONE")


if __name__ == "__main__":
    main()
