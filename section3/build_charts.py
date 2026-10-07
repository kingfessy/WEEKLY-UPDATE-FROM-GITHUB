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
STAGING_DIR = "archive/staging/section3"
CHARTS_DIR = os.path.join(STAGING_DIR, "charts")

# Wipe charts folder at start of each run
if os.path.exists(CHARTS_DIR):
    for f in os.listdir(CHARTS_DIR):
        if f.endswith(".png"):
            try:
                os.remove(os.path.join(CHARTS_DIR, f))
            except Exception:
                pass
os.makedirs(CHARTS_DIR, exist_ok=True)

AGGREGATED_PATH = os.path.join(DATA_DIR, "section3_aggregated.json")

FRESHNESS_WINDOWS = {
    "daily": 10,
    "weekly": 20,
    "monthly": 70,
}

# Category weights - higher = more investor relevant
CATEGORY_WEIGHTS = {
    "rates": 10,
    "repo": 9,
    "bank_credit": 8,
    "liquidity": 6,
    "deposits": 4,
    "bank_assets": 3,
}

# Indicator -> category mapping
INDICATOR_CATEGORY = {
    "sofr": "rates",
    "effr": "rates",
    "iorb": "rates",
    "dvp_overnight_rate": "repo",
    "triparty_overnight_rate": "repo",
    "gcf_overnight_rate": "repo",
    "bank_credit_total": "bank_credit",
    "commercial_loans": "bank_credit",
    "on_rrp_balance": "liquidity",
    "tga_balance": "liquidity",
    "m2_money_supply": "liquidity",
    "large_bank_deposits": "deposits",
    "small_bank_deposits": "deposits",
    "bank_total_assets": "bank_assets",
}

# Indicator -> frequency for freshness checks
INDICATOR_FREQ = {
    "sofr": "daily",
    "effr": "daily",
    "iorb": "daily",
    "dvp_overnight_rate": "daily",
    "triparty_overnight_rate": "daily",
    "gcf_overnight_rate": "daily",
    "bank_credit_total": "weekly",
    "commercial_loans": "monthly",
    "on_rrp_balance": "daily",
    "tga_balance": "weekly",
    "m2_money_supply": "monthly",
    "large_bank_deposits": "weekly",
    "small_bank_deposits": "weekly",
    "bank_total_assets": "weekly",
}

# Chart definitions per category
CHART_CONFIG = {
    "rates": {
        "title": "Short-Term Rates (6 Months)",
        "type": "multi_line",
        "indicators": ["sofr", "effr", "iorb"],
        "labels": ["SOFR", "EFFR", "IORB"],
        "timeframe": 180,
        "ref_line": None,
        "ref_label": None,
    },
    "repo": {
        "title": "Repo Rates (6 Months)",
        "type": "multi_line",
        "indicators": ["dvp_overnight_rate", "triparty_overnight_rate", "gcf_overnight_rate"],
        "labels": ["DVP", "Tri-Party", "GCF"],
        "timeframe": 180,
        "ref_line": None,
        "ref_label": None,
    },
    "bank_credit": {
        "title": "Bank Credit and Commercial Loans (24 Months)",
        "type": "multi_line",
        "indicators": ["bank_credit_total", "commercial_loans"],
        "labels": ["Bank Credit", "Commercial Loans"],
        "timeframe": 24,
        "ref_line": None,
        "ref_label": None,
    },
    "liquidity": {
        "title": "M2 and Treasury General Account (24 Months)",
        "type": "multi_line",
        "indicators": ["m2_money_supply", "tga_balance"],
        "labels": ["M2 (Trillions)", "TGA (Billions)"],
        "timeframe": 24,
        "ref_line": None,
        "ref_label": None,
    },
    "deposits": {
        "title": "Bank Deposits (24 Weeks)",
        "type": "multi_line",
        "indicators": ["large_bank_deposits", "small_bank_deposits"],
        "labels": ["Large Bank", "Small Bank"],
        "timeframe": 24,
        "ref_line": None,
        "ref_label": None,
    },
    "bank_assets": {
        "title": "Total Bank Assets (24 Weeks)",
        "type": "area",
        "indicators": ["bank_total_assets"],
        "labels": ["Total Bank Assets"],
        "timeframe": 24,
        "ref_line": None,
        "ref_label": None,
    },
}

# Orange palette for Section 3
PRIMARY_COLOR = "#ea580c"
SECONDARY_COLOR = "#c2410c"
TERTIARY_COLOR = "#f59e0b"
HIGHLIGHT_COLOR = "#9a3412"
REF_LINE_COLOR = "#999999"
LINE_COLORS = [PRIMARY_COLOR, SECONDARY_COLOR, TERTIARY_COLOR]


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


def is_fresh_enough(indicator_key, ind):
    freq = INDICATOR_FREQ.get(indicator_key, "monthly")
    window = FRESHNESS_WINDOWS.get(freq, 70)
    period_date = parse_period_to_date(ind.get("period", ""))
    if period_date is None:
        return False
    age_days = (datetime.now() - period_date).days
    return age_days <= window


def select_top_categories(aggregated, max_n=2):
    """
    Rank categories by weight, considering only categories with at least
    one fresh indicator that has enough history.
    Returns list of category names (up to max_n), deduped by category.
    """
    indicators = aggregated.get("indicators", {})
    category_has_fresh = {}

    for key, ind in indicators.items():
        category = INDICATOR_CATEGORY.get(key)
        if not category:
            continue
        if not is_fresh_enough(key, ind):
            continue
        if len(ind.get("history", [])) < 6:
            continue
        category_has_fresh[category] = True

    scored = [(cat, CATEGORY_WEIGHTS.get(cat, 0)) for cat in category_has_fresh.keys()]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max_n]]


def shorten_label(date_str):
    s = str(date_str)
    if "-Q" in s or len(s) == 4:
        return s
    if len(s) == 7:
        return s
    if len(s) >= 10:
        return s[5:10]
    return s


def build_chart(category, config, aggregated):
    indicators = aggregated.get("indicators", {})

    fig, ax = plt.subplots(figsize=(6, 2.8), dpi=110)
    fig.patch.set_facecolor("#FFFFFF")
    ax.set_facecolor("#FFFFFF")

    try:
        # Gather data per indicator
        series_data = []
        for key in config["indicators"]:
            ind = indicators.get(key, {})
            history = ind.get("history", [])
            if not history:
                continue
            tf = config["timeframe"]
            data = history[-tf:] if len(history) > tf else history
            series_data.append({
                "key": key,
                "dates": [shorten_label(h["date"]) for h in data],
                "values": [h["value"] for h in data],
            })

        if not series_data:
            print("   no data for category " + category)
            return None

        # Plot
        if config["type"] == "area" and len(series_data) == 1:
            s = series_data[0]
            ax.fill_between(range(len(s["values"])), s["values"], color=PRIMARY_COLOR, alpha=0.3)
            ax.plot(range(len(s["values"])), s["values"], color=PRIMARY_COLOR, linewidth=1.5)
            ax.scatter([len(s["values"]) - 1], [s["values"][-1]], color=HIGHLIGHT_COLOR, s=60, zorder=5)
        else:
            for i, s in enumerate(series_data):
                color = LINE_COLORS[i % len(LINE_COLORS)]
                ax.plot(range(len(s["values"])), s["values"], color=color, linewidth=1.8,
                        marker="o", markersize=2.5, label=config["labels"][i] if i < len(config["labels"]) else s["key"])
                # Highlight latest point
                ax.scatter([len(s["values"]) - 1], [s["values"][-1]], color=HIGHLIGHT_COLOR, s=50, zorder=5)

            # Legend
            ax.legend(loc="best", fontsize=7, frameon=False)

        # Reference line
        if config.get("ref_line") is not None:
            ax.axhline(y=config["ref_line"], color=REF_LINE_COLOR, linestyle="--", linewidth=1, alpha=0.7)

        # Title
        ax.set_title(config["title"], fontsize=10, fontweight="bold", color="#111827", pad=8)

        # X axis labels
        max_len = max(len(s["dates"]) for s in series_data)
        dates_ref = series_data[0]["dates"]
        n_labels = min(6, max_len)
        step = max(1, max_len // n_labels)
        ax.set_xticks(range(0, max_len, step))
        ax.set_xticklabels([dates_ref[i] if i < len(dates_ref) else "" for i in range(0, max_len, step)],
                           fontsize=7, rotation=0)

        ax.tick_params(axis="y", labelsize=7, colors="#374151")
        ax.tick_params(axis="x", colors="#374151")
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#E5E7EB")
        ax.spines["bottom"].set_color("#E5E7EB")
        ax.grid(axis="y", linestyle=":", alpha=0.3)

        plt.tight_layout()

        output_path = os.path.join(CHARTS_DIR, "chart_" + category + ".png")
        fig.savefig(output_path, facecolor=fig.get_facecolor(), bbox_inches="tight")
        print("   >>> saved chart: " + output_path)
        return output_path
    finally:
        plt.close("all")


def main():
    print(">>> main block entered")

    aggregated = load_json(AGGREGATED_PATH)
    if not aggregated:
        print(">>> ERROR: section3_aggregated.json not found.")
        raise SystemExit(1)

    top_categories = select_top_categories(aggregated, max_n=2)
    print(">>> top categories selected: " + str(top_categories))

    generated = []
    for category in top_categories:
        config = CHART_CONFIG.get(category)
        if not config:
            continue
        print(">>> generating chart for " + category + "...")
        path = build_chart(category, config, aggregated)
        if path:
            generated.append(category)

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "generated": generated,
        "top_2": generated,
        "all_categories": list(CHART_CONFIG.keys()),
    }
    manifest_path = os.path.join(CHARTS_DIR, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("")
    print(">>> generated " + str(len(generated)) + " charts: " + str(generated))
    print(">>> manifest saved to " + manifest_path)
    print(">>> DONE")


if __name__ == "__main__":
    main()