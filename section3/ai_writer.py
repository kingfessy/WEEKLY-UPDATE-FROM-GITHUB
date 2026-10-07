print(">>> ai_writer.py loaded")

import json
import os
import re
import time
from datetime import datetime

from openai import OpenAI

print(">>> imports done")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CONSOLIDATED_PATH = "section3/consolidated.json"
OUTPUT_PATH = "section3/narrative.json"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "openai/gpt-oss-120b"

# Category weights for top-N selection
CATEGORY_WEIGHTS = {
    "sofr": 6, "effr": 6, "iorb": 6,
    "dvp_overnight_rate": 5, "triparty_overnight_rate": 5, "gcf_overnight_rate": 5,
    "bank_credit_total": 5, "commercial_loans": 5,
    "on_rrp_balance": 4, "tga_balance": 4, "m2_money_supply": 4,
    "large_bank_deposits": 4, "small_bank_deposits": 4,
    "bank_total_assets": 3,
}

MAX_FRESH = 6

SYSTEM_PROMPT = """You are a financial journalist writing a weekly briefing on US liquidity and credit conditions for an intelligent non-specialist reader.

VOICE AND TONE:
- Write like a real human reporter, not an AI assistant.
- Use specific names, numbers, and figures.
- Vary sentence length. Short sentences are fine.
- Be direct. Do not hedge unless the data itself is uncertain.
- Frame everything around one question: are funding conditions getting tighter or looser?

FORBIDDEN FORMATTING:
- No markdown. No asterisks, no bold, no italics, no headers, no bullets, no numbered lists.
- No em dashes. Use periods, commas, semicolons, or the word "and" instead.
- No quotation marks around section titles.
- No colons at the start of paragraphs.

FORBIDDEN PHRASES:
- Never start a sentence with "In conclusion", "It's worth noting", "Furthermore", "Moreover", "Delve", "Indeed", or "Ultimately".
- Never use "In a world where", "It is important to note", "Navigating the landscape", "the data suggest", or "could give the Fed room".
- Never write meta-commentary about being an AI.

FACT DISCIPLINE:
- You may ONLY state what is written in the "Note" field for each indicator.
- Do NOT add industry color, opinions, or invented detail.
- Do NOT infer causes not stated.
- If the Note is sparse, write less.

SPACING:
- Always put a single regular space between words.
- Write rate values as "3.89 percent" (with space).
- Write dollar values as "$948.7 billion" or "$23.34 trillion".
- Always put a space after commas.

LENGTH:
- Each fresh indicator paragraph must be exactly 3 lines (3 sentences).
- Be concise. State the value, the change, and the implication.

CONTEXT NOTES:
- TIC data (foreign holdings) is published with a 1.5-month lag. Label it as "latest available".
- Monthly figures (M2, commercial loans) represent the most recent month, not this week.

OUTPUT MARKERS (critical):
- Begin the Quick Summary paragraph with the exact marker ##SUMMARY## on its own line.
- Begin EACH fresh indicator paragraph with the exact marker ##FRESH:indicator_key## on its own line, using the exact key provided.
- Begin the recent indicators paragraph with the exact marker ##RECENT## on its own line.
- Begin the What to Watch paragraph with the exact marker ##WATCH## on its own line.
- Do NOT write the markers anywhere else.

OUTPUT FORMAT:
- Block 1: ##SUMMARY## followed by a 5 to 7 line Quick Summary.
- Then one block per fresh indicator: ##FRESH:indicator_key## followed by exactly 3 lines.
- Then one block for other updates: ##RECENT## followed by 3 to 4 lines listing the remaining indicators.
- Final block: ##WATCH## followed by 3 to 4 lines.
"""


def load_consolidated():
    if not os.path.exists(CONSOLIDATED_PATH):
        print(">>> ERROR: " + CONSOLIDATED_PATH + " not found.")
        return None
    with open(CONSOLIDATED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def pick_top_fresh(consolidated, max_n=6):
    """Return the top N fresh indicators by category weight."""
    fresh = consolidated.get("fresh_indicators", [])
    scored = []
    for key in fresh:
        weight = CATEGORY_WEIGHTS.get(key, 1)
        scored.append((key, weight))
    scored.sort(key=lambda x: x[1], reverse=True)
    top = [k for k, _ in scored[:max_n]]
    rest = [k for k, _ in scored[max_n:]]
    return top, rest


def build_user_prompt(consolidated, top_fresh, rest_fresh):
    lines = []
    lines.append("Section: " + str(consolidated.get("section_name")))
    lines.append("Period covered: " + str(consolidated.get("period_covered")))
    lines.append("Total indicators: " + str(consolidated.get("total_indicators")))
    lines.append("")
    lines.append("FRESH INDICATORS - TOP " + str(len(top_fresh)) + " (write one ##FRESH:KEY## block per indicator, EXACTLY 3 lines each):")

    for key in top_fresh:
        ind = consolidated["indicators"][key]
        lines.append("")
        lines.append("[" + key + "]")
        lines.append("  Use marker: ##FRESH:" + key + "##")
        lines.append("  Display Name: " + str(ind.get("display_name")))
        lines.append("  Value: " + str(ind.get("value")) + " " + str(ind.get("unit", "")))
        lines.append("  Period: " + str(ind.get("period")))
        lines.append("  Prior: " + str(ind.get("prior")))
        lines.append("  Note: " + str(ind.get("note")))

    lines.append("")
    lines.append("REMAINING FRESH INDICATORS (mention briefly in the ##RECENT## block, 1 line each):")
    for key in rest_fresh:
        ind = consolidated["indicators"][key]
        lines.append("")
        lines.append("[" + key + "]")
        lines.append("  Display Name: " + str(ind.get("display_name")))
        lines.append("  Value: " + str(ind.get("value")) + " " + str(ind.get("unit", "")))
        lines.append("  Note: " + str(ind.get("note")))

    lines.append("")
    lines.append("RECENT INDICATORS (older data, combine with the remaining fresh into ONE ##RECENT## block, 3 to 4 lines):")
    for key in consolidated["recent_indicators"]:
        ind = consolidated["indicators"][key]
        lines.append("")
        lines.append("[" + key + "]")
        lines.append("  Display Name: " + str(ind.get("display_name")))
        lines.append("  Value: " + str(ind.get("value")) + " " + str(ind.get("unit", "")))
        lines.append("  Period: " + str(ind.get("period")))
        lines.append("  Note: " + str(ind.get("note")))

    return "\n".join(lines)


def normalize_unicode(text):
    for bad in ['\u202f', '\u00a0', '\u2009', '\u200a', '\u2002', '\u2003', '\u3000']:
        text = text.replace(bad, ' ')
    text = text.replace('\u2011', '-')
    text = text.replace('\u2013', '-')
    text = text.replace('\u2014', '--')
    text = text.replace('\u2018', "'")
    text = text.replace('\u2019', "'")
    text = text.replace('\u201c', '"')
    text = text.replace('\u201d', '"')
    return text


KNOWN_VOCABULARY = set([
    "gdp", "cpi", "pce", "ism", "fomc", "tic", "rrp", "fed", "boe", "ecb", "bis",
    "the", "and", "or", "but", "of", "to", "in", "on", "at", "for", "with", "from",
    "month", "year", "day", "week", "quarter", "index", "rate", "report", "data",
    "growth", "target", "point", "level", "below", "above", "under", "over",
    "sofr", "effr", "iorb", "repo", "triparty", "gcf", "dvp", "m2", "tga",
    "bank", "banks", "credit", "deposits", "loans", "assets", "treasury",
    "holdings", "foreign", "japan", "china", "united", "kingdom",
    "this", "that", "these", "those", "suggests", "means", "shows", "indicates",
    "mix", "combination", "overall", "same", "next", "last", "rise", "fall",
    "small", "large", "big", "major", "minor", "regional", "national", "central",
    "previous", "reading", "snapshot", "figure", "point", "mark",
])


def split_merged_token(token, vocabulary):
    lower = token.lower()
    if lower in vocabulary:
        return token
    if len(lower) < 6:
        return token
    best_split = None
    best_len = 0
    for i in range(3, len(lower) - 2):
        left = lower[:i]
        right = lower[i:]
        if left in vocabulary and right in vocabulary:
            if len(left) > best_len:
                best_len = len(left)
                best_split = (token[:i], token[i:])
    if best_split:
        return best_split[0] + " " + best_split[1]
    return token


def repair_tokens(text, vocabulary):
    tokens = text.split(" ")
    repaired = []
    for token in tokens:
        if token.startswith("##") and token.endswith("##"):
            repaired.append(token)
            continue
        match = re.match(r'^([^\w]*)([\w\.\-]+)([^\w]*)$', token)
        if match:
            lead, core, trail = match.groups()
            fixed = split_merged_token(core, vocabulary)
            repaired.append(lead + fixed + trail)
        else:
            repaired.append(token)
    return " ".join(repaired)


def clean_narrative(text):
    text = normalize_unicode(text)
    text = re.sub(r'  +', ' ', text)

    text = re.sub(r'\bover\s+over\s+reverse', 'overnight reverse', text)
    text = re.sub(r'\bover\s+reverse', 'overnight reverse', text)
    text = text.replace('under under', 'under')
    text = text.replace('priorweek', 'prior week')
    text = text.replace('cross-bordercredit', 'cross-border credit')

    text = re.sub(r"(\w+'s)(\d)", r"\1 \2", text)

    text = re.sub(r'percentin\b', 'percent in', text)
    text = re.sub(r'percentof\b', 'percent of', text)
    text = re.sub(r'percentto\b', 'percent to', text)

    text = re.sub(r',([a-z])', r', \1', text)

    text = re.sub(r'\b(The|the)(rise|fall|drop|decline|increase|change|result|move|shift|mix|combination|overall|same|next|last|figure|data|number|balance|total|level)\b', r'\1 \2', text)

    text = re.sub(r'\b(This|That|These|Those)(suggests|means|shows|indicates|adds|points|reflects|remains|leaves)\b', r'\1 \2', text)

    text = re.sub(r'\b(is|was|are|were|be)(the|a|an|not|no|more|less|up|down|now|a)\b', r'\1 \2', text)

    text = re.sub(r'\b(small|large|big|major|minor|regional|national|central)(bank|banks)\b', r'\1 \2', text)

    # previous + common nouns
    text = re.sub(r'\b(previous|prior|last|next)(reading|snapshot|figure|data|period|month|week|day|year|quarter)\b', r'\1 \2', text)

    # end-of-month
    text = re.sub(r'\b(end|start|mid)-of-(month|week|year|quarter)\b', r'\1-of-\2', text)

    text = re.sub(r'\b(for|from|in|by|since|until|during|through)(\d{4})\b', r'\1 \2', text)

    text = text.replace('overnightinterest-rate', 'overnight interest rate')
    text = text.replace('overnightinterest rate', 'overnight interest rate')

    text = re.sub(r'\b(while|when|where|since|before|after|until)(the|a|an)\b', r'\1 \2', text)

    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

    text = repair_tokens(text, KNOWN_VOCABULARY)

    text = re.sub(r'(\d),(\d{4})', r'\1, \2', text)
    text = re.sub(r'\b(\d{3})000\b', r'\1,000', text)

    text = re.sub(r'(\d+\.\d+)(percent|pct)', r'\1 \2', text)
    text = re.sub(r'(\d+)(percent|pct)', r'\1 \2', text)

    text = text.replace('annualised', 'annualized')
    text = text.replace('labour', 'labor')

    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    return text.strip()


def call_llm(system_prompt, user_prompt):
    if not GROQ_API_KEY:
        print(">>> ERROR: GROQ_API_KEY not set.")
        return None

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

    print(">>> calling Groq main model: " + MODEL)
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=5000,
        )
        content = response.choices[0].message.content
        if not content or len(content.strip()) < 100:
            print(">>> main model returned empty or invalid content.")
            return None
        return content
    except Exception as e:
        print(">>> Groq main model error: " + str(e))
        return None


def save_narrative(narrative, consolidated, top_fresh, rest_fresh):
    output = {
        "section": 3,
        "section_name": "Liquidity & Credit",
        "period_covered": consolidated.get("period_covered"),
        "generated_at": datetime.now().isoformat(),
        "narrative": narrative,
        "top_fresh": top_fresh,
        "rest_fresh": rest_fresh,
        "fresh_count": len(consolidated.get("fresh_indicators", [])),
        "recent_count": len(consolidated.get("recent_indicators", [])),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(">>> saved narrative to " + OUTPUT_PATH)


def main():
    print(">>> main block entered")

    consolidated = load_consolidated()
    if not consolidated:
        raise SystemExit(1)

    top_fresh, rest_fresh = pick_top_fresh(consolidated, max_n=MAX_FRESH)
    print(">>> top fresh: " + str(top_fresh))
    print(">>> rest fresh: " + str(rest_fresh))

    user_prompt = build_user_prompt(consolidated, top_fresh, rest_fresh)
    print(">>> user prompt built (" + str(len(user_prompt)) + " characters)")

    narrative = call_llm(SYSTEM_PROMPT, user_prompt)
    if not narrative:
        raise SystemExit(1)

    narrative = clean_narrative(narrative)

    print("")
    print("=" * 60)
    print("LLM OUTPUT (cleaned)")
    print("=" * 60)
    print(narrative)
    print("=" * 60)
    print("")

    save_narrative(narrative, consolidated, top_fresh, rest_fresh)
    print(">>> DONE")


if __name__ == "__main__":
    main()
