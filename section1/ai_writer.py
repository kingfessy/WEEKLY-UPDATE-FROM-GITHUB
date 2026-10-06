print(">>> ai_writer.py loaded")

import json
import os
import re
from openai import OpenAI

print(">>> imports done")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
CONSOLIDATED_PATH = "section1/consolidated.json"
OUTPUT_PATH = "section1/narrative.json"

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MAIN_MODEL = "openai/gpt-oss-120b"

KNOWN_VOCABULARY = set([
    "gdp", "cpi", "pce", "ism", "fomc", "tic", "rrp", "fed", "boe", "ecb", "bis",
    "imf", "oecd", "uk", "us", "usa", "treasury", "yield", "yields", "curve",
    "unemployment", "payrolls", "nonfarm", "inflation", "deflation", "debt",
    "balance", "sheet", "repo", "reverse", "overnight", "facility", "runoff",
    "liquidity", "reserves", "credit", "spread", "spreads", "cross-border",
    "rose", "fell", "dropped", "climbed", "gained", "slowed", "eased", "added",
    "beat", "missed", "totaled", "reached", "surged", "plunged", "nudged",
    "increased", "decreased", "expanded", "contracted", "revised", "continued",
    "above", "below", "under", "over", "prior", "previous", "next", "last",
    "this", "that", "these", "those", "other", "another",
    "month", "months", "year", "years", "day", "days", "week", "weeks",
    "quarter", "quarters", "annualized", "annualised", "monthly", "yearly",
    "january", "february", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december",
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at",
    "for", "with", "from", "by", "as", "is", "was", "were", "are", "be",
    "been", "being", "has", "have", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "must", "can", "cannot",
    "into", "onto", "upon", "about", "between", "among", "through",
    "during", "before", "after", "since", "until", "while", "when", "where",
    "expansion", "contraction", "threshold", "target", "level", "rate",
    "rates", "index", "point", "points", "percent", "percentage", "pct",
    "billion", "trillion", "million", "thousand", "dollars", "dollar",
    "euro", "euros", "pound", "pounds", "yen",
    "higher", "lower", "rising", "falling", "stronger", "weaker",
    "modest", "modestly", "slightly", "sharply", "steady", "steadily",
    "report", "reports", "released", "showed", "shows", "indicated",
    "signals", "suggests", "reflecting", "indicating", "highlighting",
    "including", "excluding", "driven", "shaped", "weighed", "supported",
    "data", "figure", "figures", "number", "numbers", "value", "values",
    "central", "bank", "banks", "market", "markets", "economy", "economic",
    "growth", "output", "activity", "demand", "supply", "prices", "price",
    "core", "headline", "total", "aggregate",
    "labor", "labour", "jobs", "job", "workers", "employment", "wages",
    "earnings", "hiring", "layoffs",
    "federal", "reserve", "new", "york", "university", "michigan",
    "institute", "management", "census", "bureau", "england", "international",
    "settlements",
    "said", "reported", "noted", "stated", "added", "mentioned",
    "wrote", "published", "updated", "recorded", "registered",
])


SYSTEM_PROMPT = """You are a financial journalist writing a weekly macro briefing for an intelligent non-specialist reader.

VOICE AND TONE:
- Write like a real human reporter, not an AI assistant.
- Use specific names, numbers, and countries.
- Vary sentence length. Short sentences are fine. Some can be longer with context.
- Be direct. Do not hedge unless the data itself is uncertain.

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

SPACING AND FORMAT:
- Always put a single regular space between words.
- Write quarter labels as Q2, Q3, Q4 with no space.
- Write large numbers with commas: 142,000 and 185,000.
- Write the term as "overnight reverse repo" (never "over reverse repo").
- Use American spelling: "annualized" not "annualised", "labor" not "labour".

OUTPUT MARKERS (critical):
- Begin the Quick Summary paragraph with the exact marker ##SUMMARY## on its own line, then a newline, then the paragraph.
- Begin EACH fresh indicator paragraph with the exact marker ##FRESH:indicator_key## on its own line, where indicator_key is the exact key given in the input for that indicator.
- Begin the recent indicators paragraph with the exact marker ##RECENT## on its own line.
- Begin the What to Watch paragraph with the exact marker ##WATCH## on its own line.
- Do NOT write the markers anywhere else.

OUTPUT FORMAT:
- Block 1: ##SUMMARY## followed by a Quick Summary of 5 to 7 lines.
- Then one block per fresh indicator: ##FRESH:indicator_key## followed by 4 to 6 lines. Use the indicator key exactly as provided in the input.
- Then one block for recent indicators: ##RECENT## followed by 3 to 5 lines.
- Final block: ##WATCH## followed by 3 to 4 lines.
"""


def load_consolidated():
    if not os.path.exists(CONSOLIDATED_PATH):
        print(">>> ERROR: consolidated file not found.")
        return None
    with open(CONSOLIDATED_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_user_prompt(consolidated):
    lines = []
    lines.append("Section: " + str(consolidated.get("section_name")))
    lines.append("Period covered: " + str(consolidated.get("period_covered")))
    lines.append("Total indicators: " + str(consolidated.get("total_indicators")))
    lines.append("")
    lines.append("FRESH INDICATORS (updated this week). For each, write a ##FRESH:KEY## block where KEY is the exact indicator key shown in brackets below. Write 4 to 6 lines per block.")

    for key in consolidated["fresh_indicators"]:
        ind = consolidated["indicators"][key]
        lines.append("")
        lines.append("[" + key + "]")
        lines.append("  Use marker: ##FRESH:" + key + "##")
        lines.append("  Source: " + str(ind.get("source")))
        lines.append("  Country: " + str(ind.get("country")))
        lines.append("  Value: " + str(ind.get("value")) + " " + str(ind.get("unit", "")))
        lines.append("  Period: " + str(ind.get("period")))
        lines.append("  Prior: " + str(ind.get("prior")))
        lines.append("  Change: " + str(ind.get("change")))
        lines.append("  Release date: " + str(ind.get("release_date")))
        lines.append("  Note: " + str(ind.get("note")))

    lines.append("")
    lines.append("RECENT INDICATORS (not updated this week, combine into ONE ##RECENT## paragraph, 3 to 5 lines):")

    for key in consolidated["recent_indicators"]:
        ind = consolidated["indicators"][key]
        lines.append("")
        lines.append("[" + key + "]")
        lines.append("  Country: " + str(ind.get("country")))
        lines.append("  Value: " + str(ind.get("value")) + " " + str(ind.get("unit", "")))
        lines.append("  Period: " + str(ind.get("period")))
        lines.append("  Release date: " + str(ind.get("release_date")))
        lines.append("  Note: " + str(ind.get("note")))

    if consolidated.get("stale_indicators"):
        lines.append("")
        lines.append("STALE INDICATORS (no update in 30+ days):")
        for key in consolidated["stale_indicators"]:
            ind = consolidated["indicators"][key]
            lines.append("  - " + key + ": " + str(ind.get("value")) + " " + str(ind.get("unit", "")))

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
    """Walk through every token and repair merged words using the vocabulary.
    Markers (##XXX##) are preserved as-is and not processed."""
    tokens = text.split(" ")
    repaired = []
    for token in tokens:
        # Preserve markers
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

    # Targeted phrase fixes
    text = re.sub(r'\bover\s+over\s+reverse', 'overnight reverse', text)
    text = re.sub(r'\bover\s+reverse\s+repo', 'overnight reverse repo', text)
    text = re.sub(r'\bover\s+reverse', 'overnight reverse', text)
    text = re.sub(r'\bunder\s+under', 'under', text)

    # Targeted compound fixes
    text = text.replace('priorweek', 'prior week')
    text = text.replace('cross-bordercredit', 'cross-border credit')
    text = text.replace('short-termfunding', 'short-term funding')

    # Possessive + digit merges
    text = re.sub(r"(\w+'s)(\d)", r"\1 \2", text)

    # Percent merged with following common words
    text = re.sub(r'percentin\b', 'percent in', text)
    text = re.sub(r'percentof\b', 'percent of', text)
    text = re.sub(r'percentto\b', 'percent to', text)

    # while/the, when/the, etc.
    text = re.sub(r'\b(while|when|where|since|before|after|until)(the|a|an)\b', r'\1 \2', text)

    # Doubled words
    text = re.sub(r'\b(\w+)\s+\1\b', r'\1', text, flags=re.IGNORECASE)

    # Vocabulary-based repair (preserves markers)
    text = repair_tokens(text, KNOWN_VOCABULARY)

    # Comma/digit fixes
    text = re.sub(r'(\d),(\d{4})', r'\1, \2', text)
    text = re.sub(r'\b(\d{3})000\b', r'\1,000', text)

    # Percent merged
    text = re.sub(r'(\d+\.\d+)(percent|pct)', r'\1 \2', text)
    text = re.sub(r'(\d+)(percent|pct)', r'\1 \2', text)

    # US spelling
    text = text.replace('annualised', 'annualized')
    text = text.replace('Annualised', 'Annualized')
    text = text.replace('labour', 'labor')
    text = text.replace('Labour', 'Labor')

    # Strip trailing whitespace per line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)

    return text.strip()


def call_main_model(system_prompt, user_prompt):
    if not GROQ_API_KEY:
        print(">>> ERROR: GROQ_API_KEY not set.")
        return None

    client = OpenAI(api_key=GROQ_API_KEY, base_url=GROQ_BASE_URL)

    print(">>> calling main model: " + MAIN_MODEL)
    try:
        response = client.chat.completions.create(
            model=MAIN_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=3000,
        )
        content = response.choices[0].message.content
        if not content or len(content.strip()) < 100:
            print(">>> main model returned empty or invalid content.")
            return None
        return content
    except Exception as e:
        print(">>> main model error: " + str(e))
        return None


def save_narrative(narrative, consolidated):
    output = {
        "section": consolidated.get("section"),
        "section_name": consolidated.get("section_name"),
        "period_covered": consolidated.get("period_covered"),
        "generated_at": consolidated.get("generated_at"),
        "narrative": narrative,
        "fresh_count": len(consolidated.get("fresh_indicators", [])),
        "recent_count": len(consolidated.get("recent_indicators", [])),
        "stale_count": len(consolidated.get("stale_indicators", [])),
    }
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    print(">>> saved narrative to " + OUTPUT_PATH)


def main():
    print(">>> main block entered")

    consolidated = load_consolidated()
    if not consolidated:
        raise SystemExit(1)

    user_prompt = build_user_prompt(consolidated)
    print(">>> user prompt built (" + str(len(user_prompt)) + " characters)")

    narrative = call_main_model(SYSTEM_PROMPT, user_prompt)
    if not narrative:
        raise SystemExit(1)

    narrative = clean_narrative(narrative)
    print(">>> deterministic cleanup applied")

    print("")
    print("=" * 60)
    print("LLM OUTPUT (cleaned)")
    print("=" * 60)
    print(narrative)
    print("=" * 60)
    print("")

    save_narrative(narrative, consolidated)
    print(">>> DONE")


if __name__ == "__main__":
    main()