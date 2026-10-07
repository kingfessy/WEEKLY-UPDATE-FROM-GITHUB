print(">>> build_email.py loaded")

import json
import os
import re
from datetime import datetime

print(">>> imports done")

NARRATIVE_PATH = "section3/narrative.json"
CONSOLIDATED_PATH = "section3/consolidated.json"
MANIFEST_PATH = "archive/staging/section3/charts/manifest.json"
OUTPUT_DIR = "archive/staging/section3"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "email.html")
METADATA_PATH = os.path.join(OUTPUT_DIR, "metadata.json")

INDICATOR_DISPLAY_NAMES = {
    "m2_money_supply": "US M2 Money Supply",
    "tga_balance": "Treasury General Account",
    "on_rrp_balance": "Overnight Reverse Repo",
    "sofr": "SOFR",
    "effr": "EFFR",
    "iorb": "IORB",
    "large_bank_deposits": "Large Bank Deposits",
    "small_bank_deposits": "Small Bank Deposits",
    "bank_credit_total": "Total Bank Credit",
    "commercial_loans": "Commercial Loans",
    "bank_total_assets": "Total Bank Assets",
    "dvp_overnight_rate": "DVP Repo Rate",
    "triparty_overnight_rate": "Tri-Party Repo Rate",
    "gcf_overnight_rate": "GCF Repo Rate",
    "foreign_official": "Foreign Official Treasury Holdings",
    "japan_holdings": "Japan Treasury Holdings",
    "china_holdings": "China Treasury Holdings",
    "uk_holdings": "UK Treasury Holdings",
}

ORANGE_DARK = "#c2410c"
ORANGE_MAIN = "#ea580c"
ORANGE_LIGHT = "#fff7ed"

SOURCES = (
    "Sources: U.S. Federal Reserve (FRED, H.4.1, NY Fed), "
    "U.S. Department of the Treasury (Fiscal Data, TIC), "
    "Office of Financial Research (OFR), FDIC."
)


def load_json(path):
    if not os.path.exists(path):
        print(">>> WARN: " + path + " not found.")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_narrative(raw):
    result = {"summary": "", "fresh": [], "recent": "", "watch": ""}
    pattern = r"(##[A-Z]+(?::[a-z0-9_]+)?##)"
    parts = re.split(pattern, raw)
    i = 1
    while i < len(parts):
        marker = parts[i]
        body = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if marker == "##SUMMARY##":
            result["summary"] = body
        elif marker == "##RECENT##":
            result["recent"] = body
        elif marker == "##WATCH##":
            result["watch"] = body
        elif marker.startswith("##FRESH:"):
            key = marker[8:-2]
            result["fresh"].append({"key": key, "body": body})
        i += 2
    return result


def display_name(key):
    if key in INDICATOR_DISPLAY_NAMES:
        return INDICATOR_DISPLAY_NAMES[key]
    return key.replace("_", " ").title()


def format_paragraph(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return "".join("<p style='margin:0 0 12px 0;line-height:1.55;color:#1f2937;'>" + line + "</p>" for line in lines)


def build_chart_html(chart_name):
    cid = "chart_" + chart_name
    return (
        "<div style='margin:16px 0 8px 0;text-align:center;'>"
        "<img src='cid:" + cid + "' alt='chart' "
        "style='max-width:100%;width:600px;height:auto;border:1px solid #e5e7eb;border-radius:6px;'>"
        "</div>"
    )


def build_html(narrative, consolidated, manifest, chart_categories):
    today = datetime.now().strftime("%B %d, %Y")
    parsed = parse_narrative(narrative.get("narrative", ""))

    indicator_to_category = {
        "sofr": "rates", "effr": "rates", "iorb": "rates",
        "dvp_overnight_rate": "repo", "triparty_overnight_rate": "repo", "gcf_overnight_rate": "repo",
        "bank_credit_total": "bank_credit", "commercial_loans": "bank_credit",
        "on_rrp_balance": "liquidity", "tga_balance": "liquidity", "m2_money_supply": "liquidity",
        "large_bank_deposits": "deposits", "small_bank_deposits": "deposits",
        "bank_total_assets": "bank_assets",
    }

    placed_categories = set()

    fresh_html = ""
    for item in parsed["fresh"]:
        key = item["key"]
        heading = display_name(key)
        ind = consolidated.get("indicators", {}).get(key, {})
        period_label = ind.get("period", "")
        meta_line = ""
        if period_label:
            meta_line = "<div style='font-size:12px;color:#6b7280;margin:0 0 10px 0;'>" + period_label + "</div>"

        chart_html = ""
        category = indicator_to_category.get(key)
        if category and category in chart_categories and category not in placed_categories:
            chart_html = build_chart_html(category)
            placed_categories.add(category)

        fresh_html += (
            "<div style='margin:0 0 28px 0;'>"
            "<h3 style='margin:0 0 6px 0;font-size:16px;color:#111827;font-weight:600;'>" + heading + "</h3>"
            + meta_line +
            format_paragraph(item["body"]) +
            chart_html +
            "</div>"
        )

    recent_html = ""
    if parsed["recent"]:
        recent_html = (
            "<div style='margin:0 0 28px 0;'>"
            "<h3 style='margin:0 0 6px 0;font-size:16px;color:#111827;font-weight:600;'>Other Updates</h3>"
            + format_paragraph(parsed["recent"]) +
            "</div>"
        )

    watch_html = ""
    if parsed["watch"]:
        watch_html = (
            "<div style='margin:0 0 28px 0;'>"
            "<h3 style='margin:0 0 6px 0;font-size:16px;color:#111827;font-weight:600;'>What to Watch</h3>"
            + format_paragraph(parsed["watch"]) +
            "</div>"
        )

    summary_html = ""
    if parsed["summary"]:
        summary_html = (
            "<div style='background:" + ORANGE_LIGHT + ";border-left:4px solid " + ORANGE_MAIN + ";padding:16px 20px;margin:0 0 28px 0;'>"
            "<div style='font-size:12px;font-weight:600;color:" + ORANGE_MAIN + ";text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px 0;'>Quick Summary</div>"
            + format_paragraph(parsed["summary"]) +
            "</div>"
        )

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Liquidity and Credit</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;">
<tr>
<td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;">
<tr>
<td style="background:""" + ORANGE_DARK + """;color:#ffffff;padding:24px 28px;">
<h1 style="margin:0;font-size:22px;font-weight:600;">LIQUIDITY AND CREDIT</h1>
<div style="font-size:13px;opacity:0.85;margin-top:6px;">Week ending """ + today + """</div>
</td>
</tr>
<tr>
<td style="padding:28px;">
""" + summary_html + fresh_html + recent_html + watch_html + """
<div style="border-top:1px solid #e5e7eb;padding-top:16px;margin-top:8px;">
<div style="font-size:11px;color:#6b7280;font-style:italic;line-height:1.5;">""" + SOURCES + """</div>
</div>
</td>
</tr>
</table>
</td>
</tr>
</table>
</body>
</html>"""

    return html


def build_subject_line(parsed):
    summary = parsed.get("summary", "").strip()
    if not summary:
        return "Liquidity Brief"
    first = summary.split(".")[0].strip()
    if len(first) > 70:
        first = first[:67].rstrip() + "..."
    return "Liquidity Brief: " + first


def save_metadata(parsed, chart_categories):
    subject = build_subject_line(parsed)
    charts_to_attach = []
    for cat in chart_categories:
        chart_file = os.path.join("archive/staging/section3/charts", "chart_" + cat + ".png")
        charts_to_attach.append({"indicator": cat, "file": chart_file, "cid": "chart_" + cat})

    metadata = {
        "section": 3,
        "section_name": "Liquidity & Credit",
        "generated_at": datetime.now().isoformat(),
        "subject": subject,
        "recipients": ["aderemi4festus@gmail.com", "Rab492@gmail.com"],
        "charts": charts_to_attach,
        "summary_stats": {
            "fresh_count": len(parsed.get("fresh", [])),
            "charts_embedded": len(charts_to_attach),
        },
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(">>> metadata saved to " + METADATA_PATH)
    print(">>> subject: " + subject)
    print(">>> recipients: " + str(metadata["recipients"]))
    print(">>> charts to attach: " + str(len(charts_to_attach)))
    return metadata


def main():
    print(">>> main block entered")

    narrative = load_json(NARRATIVE_PATH)
    if not narrative:
        raise SystemExit(1)

    consolidated = load_json(CONSOLIDATED_PATH)
    if not consolidated:
        raise SystemExit(1)

    manifest = load_json(MANIFEST_PATH)
    if not manifest:
        print(">>> WARN: no chart manifest - proceeding with text only")
        manifest = {"top_2": [], "generated": []}

    chart_categories = manifest.get("top_2", manifest.get("generated", []))
    print(">>> chart categories: " + str(chart_categories))

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    html = build_html(narrative, consolidated, manifest, chart_categories)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(">>> email HTML built (" + str(len(html)) + " characters)")
    print(">>> saved to " + OUTPUT_PATH)

    parsed = parse_narrative(narrative.get("narrative", ""))
    save_metadata(parsed, chart_categories)

    print(">>> DONE")


if __name__ == "__main__":
    main()