print(">>> build_charts.py loaded")

import json
import os
from datetime import datetime

print(">>> imports done")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

print(">>> matplotlib ready")

DATA_DIR = "archive/data"
STAGING_DIR = "archive/staging/section1"
CHARTS_DIR = os.path.join(STAGING_DIR, "charts")
os.makedirs(CHARTS_DIR, exist_ok=True)

AGGREGATED_PATH = os.path.join(DATA_DIR, "aggregated.json")

FRESHNESS_WINDOWS = {
    "daily": 10,
    "weekly": 14,
    "monthly": 70,
    "quarterly": 180,
    "annual": 400,
}

CATEGORY_WEIGHTS = {
    "gdp": 2, "cpi": 6, "core_cpi": 6, "pce": 6,
    "nonfarm_payrolls": 3, "unemployment_rate": 3, "manufacturing_employment": 3,
    "fed_funds_rate": 5, "treasury_10y": 5,
    "fed_balance_sheet": 4, "reverse_repo": 4,
    "bis_cross_border_credit": 1, "imf_world_gdp_growth": 1, "ecb_deposit_rate": 1,
}

CATEGORIES = {
    "cpi": "inflation", "core_cpi": "inflation", "pce": "inflation",
    "fed_funds_rate": "rates", "treasury_10y": "rates",
    "fed_balance_sheet": "liquidity", "reverse_repo": "liquidity",
    "nonfarm_payrolls": "labor", "unemployment_rate": "labor", "manufacturing_employment": "labor",
    "gdp": "growth",
    "bis_cross_border_credit": "global", "imf_world_gdp_growth": "global", "ecb_deposit_rate": "global",
}

CHANGE_THRESHOLDS = {
    "gdp": 0.1, "cpi": 0.1, "core_cpi": 0.1, "pce": 0.1,
    "nonfarm_payrolls": 20, "unemployment_rate": 0.1, "manufacturing_employment": 20,
    "fed_funds_rate": 0.10, "treasury_10y": 0.10,
    "fed_balance_sheet": 10000, "reverse_repo": 20,
    "bis_cross_border_credit": 50, "imf_world_gdp_growth": 0.1, "ecb_deposit_rate": 0.10,
}

CHART_CONFIG = {
    "gdp":                     {"type": "line", "timeframe": 8,   "freq": "quarterly", "title": "US Real GDP Growth (Quarterly)",       "ref_line": None, "ref_label": None},
    "cpi":                     {"type": "line", "timeframe": 24,  "freq": "monthly",   "title": "US CPI (Index, 24 Months)",              "ref_line": None, "ref_label": None},
    "core_cpi":                {"type": "line", "timeframe": 24,  "freq": "monthly",   "title": "US Core CPI (Index, 24 Months)",         "ref_line": None, "ref_label": None},
    "pce":                     {"type": "line", "timeframe": 24,  "freq": "monthly",   "title": "US PCE Price Index",                     "ref_line": None, "ref_label": None},
    "nonfarm_payrolls":        {"type": "bar",  "timeframe": 12,  "freq": "monthly",   "title": "US Nonfarm Payrolls (Monthly Change)",   "ref_line": 0,    "ref_label": None},
    "unemployment_rate":       {"type": "line", "timeframe": 24,  "freq": "monthly",   "title": "US Unemployment Rate",                   "ref_line": 4.0,  "ref_label": "4% threshold"},
    "fed_funds_rate":          {"type": "step", "timeframe": 24,  "freq": "daily",     "title": "US Fed Funds Rate",                      "ref_line": None, "ref_label": None},
    "treasury_10y":            {"type": "line", "timeframe": 52,  "freq": "daily",     "title": "US 10Y Treasury Yield",                  "ref_line": None, "ref_label": None},
    "fed_balance_sheet":       {"type": "area", "timeframe": 52,  "freq": "weekly",    "title": "Fed Balance Sheet (Trillions USD)",      "ref_line": None, "ref_label": None},
    "reverse_repo":            {"type": "bar",  "timeframe": 30,  "freq": "daily",     "title": "Reverse Repo Facility (Daily)",          "ref_line": None, "ref_label": None},
    "manufacturing_employment":{"type": "line", "timeframe": 24,  "freq": "monthly",   "title": "US Manufacturing Employment",            "ref_line": None, "ref_label": None},
    "bis_cross_border_credit": {"type": "line", "timeframe": 12,  "freq": "quarterly", "title": "BIS Cross-Border Credit",                "ref_line": None, "ref_label": None},
    "imf_world_gdp_growth":    {"type": "line", "timeframe": 12,  "freq": "annual",    "title": "IMF World GDP Growth",                   "ref_line": None, "ref_label": None},
    "ecb_deposit_rate":        {"type": "step", "timeframe": 24,  "freq": "annual",    "title": "ECB Deposit Rate",                       "ref_line": None, "ref_label": None},
}

PRIMARY_COLOR = "#0072B2"
HIGHLIGHT_COLOR = "#D55E00"
REF_LINE_COLOR = "#999999"


def load_json(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_period_to_date(period_str):
    s = str(period_str).strip()
    try:
        if "-Q" in s:
            year = int(s.split("-Q")[0])
            return datetime(year, 1, 1)
        if len(s) == 4:
            return datetime(int(s), 1, 1)
        if len(s) == 7:
            return datetime.strptime(s, "%Y-%m")
        if len(s) >= 10:
            return datetime.strptime(s[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        pass
    return None


def compute_magnitude_score(value, prior, threshold):
    if value is None or prior is None:
        return 0.0
    try:
        diff = abs(float(value) - float(prior))
    except (TypeError, ValueError):
        return 0.0
    if threshold <= 0:
        return 0.5
    ratio = diff / threshold
    if ratio >= 1.0:
        return 1.0
    return round(ratio, 2)


def compute_freshness_score(age_days, window_days):
    if window_days <= 0:
        return 0.2
    ratio = age_days / window_days
    if ratio <= 0.2:
        return 1.0
    if ratio <= 0.5:
        return 0.7
    if ratio <= 0.8:
        return 0.5
    return 0.2


def should_generate(indicator_key, aggregated):
    indicators = aggregated.get("indicators", {})
    ind = indicators.get(indicator_key)
    if not ind:
        return (False, "not in aggregated", None)

    config = CHART_CONFIG.get(indicator_key, {})
    freq = config.get("freq", "monthly")
    window_days = FRESHNESS_WINDOWS.get(freq, 70)

    history = ind.get("history", [])
    if len(history) < 6:
        return (False, "less than 6 history points", None)

    period_date = parse_period_to_date(ind.get("period", ""))
    if period_date is None:
        return (False, "unparseable period", None)
    age_days = (datetime.now() - period_date).days
    if age_days > window_days:
        return (False, "period " + str(age_days) + "d old, exceeds window " + str(window_days) + "d", None)

    values = [h["value"] for h in history[-12:]]
    if len(set(round(v, 3) for v in values)) <= 1:
        return (False, "flat values", None)

    category_weight = CATEGORY_WEIGHTS.get(indicator_key, 1)
    threshold = CHANGE_THRESHOLDS.get(indicator_key, 0.1)
    magnitude_score = compute_magnitude_score(ind.get("value"), ind.get("prior"), threshold)
    freshness_score = compute_freshness_score(age_days, window_days)
    total_score = round(category_weight * 3 + magnitude_score * 2 + freshness_score * 1, 2)

    scores = {
        "category_weight": category_weight,
        "magnitude_score": magnitude_score,
        "freshness_score": freshness_score,
        "total_score": total_score,
        "age_days": age_days,
    }

    return (True, "qualifies (period " + str(age_days) + "d old, score " + str(total_score) + ")", scores)


def shorten_label(date_str):
    s = str(date_str)
    if "-Q" in s or len(s) == 4:
        return s
    if len(s) == 7:
        return s
    if len(s) >= 10:
        return s[5:10]
    return s


def build_chart(indicator_key, config, indicator_data):
    history = indicator_data["history"]
    timeframe = config["timeframe"]
    data = history[-timeframe:] if len(history) > timeframe else history

    dates = [shorten_label(h["date"]) for h in data]
    values = [h["value"] for h in data]

    fig, ax = plt.subplots(figsize=(6, 2.5), dpi=110)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    try:
        if config["type"] == "bar":
            ax.bar(range(len(values)), values, color=PRIMARY_COLOR, width=0.7)
        elif config["type"] == "step":
            ax.step(range(len(values)), values, where="post", color=PRIMARY_COLOR, linewidth=2)
        elif config["type"] == "area":
            ax.fill_between(range(len(values)), values, color=PRIMARY_COLOR, alpha=0.3)
            ax.plot(range(len(values)), values, color=PRIMARY_COLOR, linewidth=1.5)
        else:
            ax.plot(range(len(values)), values, color=PRIMARY_COLOR, linewidth=2, marker="o", markersize=3)

        if len(values) > 0:
            ax.scatter([len(values) - 1], [values[-1]], color=HIGHLIGHT_COLOR, s=60, zorder=5)

        if config["ref_line"] is not None:
            ax.axhline(y=config["ref_line"], color=REF_LINE_COLOR, linestyle="--", linewidth=1, alpha=0.7)

        ax.set_title(config["title"], fontsize=10, fontweight="bold", color="#111827", pad=8)

        n_labels = min(6, len(dates))
        step = max(1, len(dates) // n_labels)
        ax.set_xticks(range(0, len(dates), step))
        ax.set_xticklabels([dates[i] for i in range(0, len(dates), step)], fontsize=7, rotation=0)

        ax.tick_params(axis="y", labelsize=7, colors="#374151")
        ax.tick_params(axis="x", colors="#374151")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#E5E7EB")
        ax.spines["bottom"].set_color("#E5E7EB")
        ax.grid(axis="y", linestyle=":", alpha=0.3)

        plt.tight_layout()

        output_path = os.path.join(CHARTS_DIR, "chart_" + indicator_key + ".png")
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        print("   >>> saved chart: " + output_path)
        return output_path
    finally:
        plt.close("all")


def main():
    print(">>> main block entered")

    aggregated = load_json(AGGREGATED_PATH)
    if not aggregated:
        print(">>> ERROR: aggregated.json not found.")
        raise SystemExit(1)

    generated = []
    skipped = []
    scores_map = {}

    for indicator_key, config in CHART_CONFIG.items():
        qualifies, reason, scores = should_generate(indicator_key, aggregated)
        if not qualifies:
            print(">>> " + indicator_key + ": skipped (" + reason + ")")
            skipped.append((indicator_key, reason))
            continue

        indicator_data = aggregated["indicators"][indicator_key]
        print(">>> " + indicator_key + ": generating chart (" + reason + ")")
        path = build_chart(indicator_key, config, indicator_data)
        generated.append(indicator_key)
        scores_map[indicator_key] = scores

    ranked = sorted(scores_map.items(), key=lambda x: x[1]["total_score"], reverse=True)

    top3 = []
    seen_categories = set()
    for key, scores in ranked:
        cat = CATEGORIES.get(key, "other")
        if cat in seen_categories:
            continue
        top3.append(key)
        seen_categories.add(cat)
        if len(top3) >= 3:
            break

    print("")
    print(">>> Top 3 by importance score (deduplicated by category):")
    for k in top3:
        cat = CATEGORIES.get(k, "other")
        s = scores_map[k]
        print("    " + k + " [" + cat + "]: " + str(s["total_score"]))

    print("")
    print(">>> Other generated charts:")
    for k, s in ranked:
        if k not in top3:
            cat = CATEGORIES.get(k, "other")
            print("    " + k + " [" + cat + "]: " + str(s["total_score"]))

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "generated": generated,
        "top_3": top3,
        "scores": scores_map,
        "categories": {k: CATEGORIES.get(k, "other") for k in generated},
        "skipped": [{"indicator": k, "reason": r} for k, r in skipped],
    }
    manifest_path = os.path.join(CHARTS_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("")
    print(">>> generated " + str(len(generated)) + " charts, skipped " + str(len(skipped)))
    print(">>> manifest saved to " + manifest_path)
    print(">>> DONE")


if __name__ == "__main__":
    main()
