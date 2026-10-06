print(">>> consolidate.py loaded")

import json
import os
from datetime import datetime, timezone

print(">>> imports done")

AGGREGATED_PATH = "archive/data/aggregated.json"
OUTPUT_PATH = "section1/consolidated.json"


def load_aggregated():
    if not os.path.exists(AGGREGATED_PATH):
        print(">>> ERROR: " + AGGREGATED_PATH + " not found.")
        return None
    with open(AGGREGATED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_period(period_str):
    """
    Try to parse a period string into a datetime.
    Handles: YYYY-MM-DD, YYYY-MM, YYYY, YYYY-QN
    Returns None if unparseable.
    """
    if not period_str:
        return None
    s = str(period_str).strip()

    # YYYY-MM-DD
    try:
        return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # YYYY-MM
    try:
        return datetime.strptime(s, "%Y-%m").replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # YYYY
    try:
        return datetime.strptime(s, "%Y").replace(tzinfo=timezone.utc)
    except ValueError:
        pass

    # YYYY-QN (e.g., 2024-Q4)
    if "-Q" in s:
        try:
            year, q = s.split("-Q")
            month = (int(q) - 1) * 3 + 1
            return datetime(int(year), month, 1, tzinfo=timezone.utc)
        except (ValueError, IndexError):
            pass

    return None


def tag_freshness(indicator):
    """
    Determine freshness based on period.
    fresh   = released in last 7 days
    recent  = released in last 30 days
    stale   = older than 30 days
    unknown = unparseable period
    """
    period_str = indicator.get("period")
    dt = parse_period(period_str)
    if dt is None:
        return "unknown"

    now = datetime.now(timezone.utc)
    age_days = (now - dt).days

    if age_days <= 7:
        return "fresh"
    elif age_days <= 30:
        return "recent"
    else:
        return "stale"


def build_consolidated(aggregated):
    if not aggregated:
        return None

    indicators = aggregated.get("indicators", {})
    enriched = {}

    fresh_list = []
    recent_list = []
    stale_list = []
    unknown_list = []

    for key, ind in indicators.items():
        freshness = tag_freshness(ind)
        ind_with_freshness = dict(ind)
        ind_with_freshness["freshness"] = freshness
        ind_with_freshness["indicator_key"] = key
        enriched[key] = ind_with_freshness

        if freshness == "fresh":
            fresh_list.append(key)
        elif freshness == "recent":
            recent_list.append(key)
        elif freshness == "stale":
            stale_list.append(key)
        else:
            unknown_list.append(key)

    consolidated = {
        "section": 1,
        "section_name": "Macro & Policy",
        "period_covered": "Week ending " + datetime.now().strftime("%B %d, %Y"),
        "generated_at": datetime.now().isoformat(),
        "total_indicators": len(enriched),
        "fresh_indicators": fresh_list,
        "recent_indicators": recent_list,
        "stale_indicators": stale_list,
        "unknown_indicators": unknown_list,
        "indicators": enriched,
    }

    return consolidated


def print_summary(consolidated):
    if not consolidated:
        return
    print("")
    print("=" * 60)
    print("CONSOLIDATED DATA SUMMARY")
    print("=" * 60)
    print("Section: " + str(consolidated["section"]) + " - " + consolidated["section_name"])
    print("Period: " + consolidated["period_covered"])
    print("Total indicators: " + str(consolidated["total_indicators"]))
    print("  Fresh (last 7 days):   " + str(len(consolidated["fresh_indicators"])))
    print("  Recent (last 30 days): " + str(len(consolidated["recent_indicators"])))
    print("  Stale (30+ days):      " + str(len(consolidated["stale_indicators"])))
    print("  Unknown:               " + str(len(consolidated["unknown_indicators"])))
    print("")
    print("Fresh indicators:")
    for key in consolidated["fresh_indicators"]:
        ind = consolidated["indicators"][key]
        print("  - " + key + ": " + str(ind.get("value")) + " " + str(ind.get("unit", "")) + " (" + str(ind.get("period")) + ")")
    print("")
    print("Recent indicators:")
    for key in consolidated["recent_indicators"]:
        ind = consolidated["indicators"][key]
        print("  - " + key + ": " + str(ind.get("value")) + " " + str(ind.get("unit", "")) + " (" + str(ind.get("period")) + ")")
    print("")
    print("Stale indicators:")
    for key in consolidated["stale_indicators"]:
        ind = consolidated["indicators"][key]
        print("  - " + key + ": " + str(ind.get("value")) + " " + str(ind.get("unit", "")) + " (" + str(ind.get("period")) + ")")
    print("=" * 60)
    print("")


def main():
    print(">>> main block entered")

    aggregated = load_aggregated()
    if not aggregated:
        raise SystemExit(1)

    consolidated = build_consolidated(aggregated)
    print_summary(consolidated)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(consolidated, f, indent=2)
    print(">>> saved consolidated data to " + OUTPUT_PATH)
    print(">>> DONE")


if __name__ == "__main__":
    main()
