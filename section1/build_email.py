print(">>> build_email.py loaded")

import json
import os
import re
from datetime import datetime

print(">>> imports done")

NARRATIVE_PATH = "section1/narrative.json"
CONSOLIDATED_PATH = "section1/consolidated.json"
MANIFEST_PATH = "archive/staging/section1/charts/manifest.json"
OUTPUT_DIR = "archive/staging/section1"
OUTPUT_PATH = os.path.join(OUTPUT_DIR, "email.html")
METADATA_PATH = os.path.join(OUTPUT_DIR, "metadata.json")

INDICATOR_DISPLAY_NAMES = {
    "gdp": "GDP", "cpi": "CPI", "core_cpi": "Core CPI", "pce": "PCE Price Index",
    "nonfarm_payrolls": "Nonfarm Payrolls", "unemployment_rate": "Unemployment Rate",
    "ism_manufacturing": "ISM Manufacturing", "manufacturing_employment": "Manufacturing Employment",
    "retail_sales": "Retail Sales", "consumer_sentiment": "Consumer Sentiment",
    "fed_balance_sheet": "Fed Balance Sheet", "reverse_repo": "Reverse Repo Facility",
    "fed_funds_rate": "Fed Funds Rate", "treasury_10y": "10Y Treasury Yield",
    "bis_cross_border_credit": "BIS Cross-Border Credit",
    "imf_world_gdp_growth": "IMF World GDP Growth",
    "ecb_deposit_rate": "ECB Deposit Rate",
}

SOURCES = (
    "Sources: U.S. Federal Reserve (FRED, ALFRED, H.4.1, NY Fed), "
    "U.S. Bureau of Labor Statistics, U.S. Bureau of Economic Analysis, "
    "Bank for International Settlements, OECD, IMF, ECB Data Portal."
)


def load_json(path):
    if not os.path.exists(path):
        print(">>> WARN: " + path + " not found.")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_narrative(raw):
    result = {"summary": "", "fresh": [], "recent": "", "watch": ""}
    pattern = r"(##[A-Z]+(?::[a-z_]+)?##)"
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


def build_chart_html(indicator_key):
    cid = "chart_" + indicator_key
    return (
        "<div style='margin:16px 0 8px 0;text-align:center;'>"
        "<img src='cid:" + cid + "' alt='chart' "
        "style='max-width:100%;width:600px;height:auto;border:1px solid #e5e7eb;border-radius:6px;'>"
        "</div>"
    )


def build_html(narrative, consolidated, manifest):
    today = datetime.now().strftime("%B %d, %Y")
    parsed = parse_narrative(narrative.get("narrative", ""))

    top3 = manifest.get("top_3", []) if manifest else []
    print(">>> charts to embed: " + str(top3))

    fresh_html = ""
    for item in parsed["fresh"]:
        key = item["key"]
        heading = display_name(key)
        ind = consolidated.get("indicators", {}).get(key, {})
        period_label = ind.get("period", "")
        country = ind.get("country", "")
        meta_line = ""
        if country and period_label:
            meta_line = "<div style='font-size:12px;color:#6b7280;margin:0 0 10px 0;'>" + country + " · " + period_label + "</div>"
        elif period_label:
            meta_line = "<div style='font-size:12px;color:#6b7280;margin:0 0 10px 0;'>" + period_label + "</div>"

        chart_html = build_chart_html(key) if key in top3 else ""

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
            "<h3 style='margin:0 0 6px 0;font-size:16px;color:#111827;font-weight:600;'>This Week's Other Releases</h3>"
            "<div style='font-size:12px;color:#6b7280;margin:0 0 10px 0;'>Not updated this week</div>"
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
            "<div style='background:#f9fafb;border-left:4px solid #2563eb;padding:16px 20px;margin:0 0 28px 0;'>"
            "<div style='font-size:12px;font-weight:600;color:#2563eb;text-transform:uppercase;letter-spacing:0.5px;margin:0 0 10px 0;'>Quick Summary</div>"
            + format_paragraph(parsed["summary"]) +
            "</div>"
        )

    html = """<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro and Policy</title>
</head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f3f4f6;">
<tr>
<td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;width:100%;background:#ffffff;border-radius:8px;overflow:hidden;">
<tr>
<td style="background:#1e3a8a;color:#ffffff;padding:24px 28px;">
<h1 style="margin:0;font-size:22px;font-weight:600;">MACRO AND POLICY</h1>
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
        return "[TEST] Macro Brief"
    first = summary.split(".")[0].strip()
    if len(first) > 70:
        first = first[:67].rstrip() + "..."
    return "[TEST] Macro Brief: " + first


def save_metadata(parsed, manifest):
    subject = build_subject_line(parsed)
    top3 = manifest.get("top_3", []) if manifest else []
    charts_to_attach = []
    for key in top3:
        chart_file = os.path.join("archive/staging/section1/charts", "chart_" + key + ".png")
        charts_to_attach.append({"indicator": key, "file": chart_file, "cid": "chart_" + key})

    metadata = {
        "section": 1,
        "section_name": "Macro & Policy",
        "generated_at": datetime.now().isoformat(),
        "subject": subject,
        "recipients": ["aderemi4festus@gmail.com"],
        "charts": charts_to_attach,
        "summary_stats": {
            "fresh_count": len(parsed.get("fresh", [])),
            "has_recent": bool(parsed.get("recent")),
            "has_watch": bool(parsed.get("watch")),
            "charts_embedded": len(charts_to_attach),
        },
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    print(">>> metadata saved to " + METADATA_PATH)
    print(">>> subject: " + subject)
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
        manifest = {"top_3": [], "generated": [], "scores": {}}

    parsed = parse_narrative(narrative.get("narrative", ""))
    fresh_keys = [item["key"] for item in parsed["fresh"]]
    print(">>> FRESH indicators in narrative: " + str(fresh_keys))

    manifest_top3 = manifest.get("top_3", [])
    filtered_top3 = [k for k in manifest_top3 if k in fresh_keys]

    if len(filtered_top3) < 3:
        scores = manifest.get("scores", {})
        generated = manifest.get("generated", [])
        ranked = sorted(
            [(k, scores.get(k, {}).get("total_score", 0)) for k in generated],
            key=lambda x: x[1],
            reverse=True,
        )
        for k, _ in ranked:
            if k in filtered_top3:
                continue
            if k in fresh_keys:
                filtered_top3.append(k)
            if len(filtered_top3) >= 3:
                break

    print(">>> charts to embed after filter: " + str(filtered_top3))

    manifest["top_3"] = filtered_top3
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(">>> manifest updated with filtered top_3")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    html = build_html(narrative, consolidated, manifest)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(">>> email HTML built (" + str(len(html)) + " characters)")
    print(">>> saved to " + OUTPUT_PATH)

    save_metadata(parsed, manifest)

    print(">>> DONE")


if __name__ == "__main__":
    main()
