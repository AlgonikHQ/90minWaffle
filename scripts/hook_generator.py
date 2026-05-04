"""
hook_generator.py — Dedicated hook generation via Claude API
Drop this into /root/90minwaffle/scripts/

Usage:
    from hook_generator import generate_hook, is_tiktok_worthy
    hook = generate_hook(headline, summary)
    if is_tiktok_worthy(headline, tier1_names):
        queue_for_tiktok(story)
"""

import os
import re
import json
import httpx

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_URL           = "https://api.anthropic.com/v1/messages"

# ── Tier-1 filter for TikTok queue ─────────────────────────────────────────
TIER1_PLAYERS = {
    "haaland", "salah", "palmer", "saka", "bellingham", "vinicius", "mbappe",
    "kane", "son", "rashford", "de bruyne", "rodri", "odegaard", "martinelli",
    "trent", "virgil", "alisson", "ederson", "rice", "mainoo", "gordon",
    "isak", "watkins", "ollie", "mbuemo", "pedro neto", "yamal", "gavi",
    "pedri", "lewandowski", "osimhen", "osimhen", "lukaku", "dembele",
}

TIER1_CLUBS = {
    "arsenal", "chelsea", "manchester city", "man city", "liverpool",
    "manchester united", "man united", "man utd", "tottenham", "spurs",
    "newcastle", "aston villa",
}

DRAMA_SIGNALS = {
    "sacked", "fired", "crisis", "exposed", "bottled", "disaster",
    "row", "fury", "slams", "blasts", "rift", "meltdown", "outrage",
    "demand", "transfer", "exit", "snubbed", "dropped", "benched",
    "flop", "bust-up", "feud", "shock", "sensational", "exclusive",
    "revealed", "admits", "confesses", "slated", "hammered",
}


def is_tiktok_worthy(headline: str, summary: str = "") -> bool:
    """
    Returns True if story passes the TikTok filter:
    - Mentions a tier-1 player or club AND
    - Has a drama/opinion signal
    Pure match reports without drama fail the filter.
    """
    text = (headline + " " + summary).lower()

    has_tier1 = (
        any(p in text for p in TIER1_PLAYERS) or
        any(c in text for c in TIER1_CLUBS)
    )
    has_drama = any(d in text for d in DRAMA_SIGNALS)

    return has_tier1 and has_drama


def generate_hook(headline: str, summary: str = "", retries: int = 2) -> str:
    """
    Calls Claude API to generate a 6-word stop-the-scroll TikTok hook.
    Falls back to a truncated headline if API fails.

    Args:
        headline: story headline
        summary:  optional story summary for more context
        retries:  number of retry attempts on failure

    Returns:
        str: 6-word hook string
    """
    if not ANTHROPIC_API_KEY:
        print("[hook] No API key — using headline fallback")
        return _fallback_hook(headline)

    prompt = f"""You are a football pundit writing TikTok hooks. Your job is to write ONE hook — exactly 6 words — that stops someone mid-scroll.

Rules:
- Exactly 6 words (count them)
- Strong opinion or bold claim
- Football fan voice — direct, punchy, a bit provocative
- No question marks — statements hit harder
- No hashtags, no emojis
- Do not repeat the headline word for word

Story headline: {headline}
{f'Context: {summary}' if summary else ''}

Respond with ONLY the 6-word hook. Nothing else."""

    headers = {
        "content-type":      "application/json",
        "x-api-key":         ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
    }

    payload = {
        "model":      "claude-sonnet-4-5",
        "max_tokens": 50,
        "messages":   [{"role": "user", "content": prompt}],
    }

    for attempt in range(retries + 1):
        try:
            r = httpx.post(API_URL, headers=headers, json=payload, timeout=15)
            r.raise_for_status()
            data = r.json()
            hook = data["content"][0]["text"].strip().strip('"').strip("'")
            # Validate roughly 6 words
            if 4 <= len(hook.split()) <= 8:
                print(f"[hook] Generated: {hook!r}")
                return hook
            else:
                print(f"[hook] Bad word count ({len(hook.split())}), retrying...")
        except Exception as e:
            print(f"[hook] API error (attempt {attempt+1}): {e}")

    return _fallback_hook(headline)


def _fallback_hook(headline: str) -> str:
    """Simple fallback — first 6 words of headline."""
    words = re.sub(r"[^\w\s]", "", headline).split()
    return " ".join(words[:6]) + "."


# ── Series router ───────────────────────────────────────────────────────────
SERIES_MAP = {
    "flop":      "Flops We Aren't Talking About",
    "disaster":  "Flops We Aren't Talking About",
    "worst":     "Flops We Aren't Talking About",
    "sacked":    "Managers On The Brink",
    "fired":     "Managers On The Brink",
    "crisis":    "Managers On The Brink",
    "transfer":  "Transfer Chaos Index",
    "exit":      "Transfer Chaos Index",
    "signing":   "Transfer Chaos Index",
    "goal":      "Weekend Chaos Index",
    "hat-trick": "Weekend Chaos Index",
    "comeback":  "Weekend Chaos Index",
}


def detect_series(headline: str, summary: str = "") -> str | None:
    """
    Returns the series name if the story matches a known series template,
    or None if it's a standalone story.
    """
    text = (headline + " " + summary).lower()
    for keyword, series in SERIES_MAP.items():
        if keyword in text:
            return series
    return None


if __name__ == "__main__":
    # Quick test
    test_headline = "Arteta slams referee after Arsenal's fourth consecutive defeat"
    print("TikTok worthy:", is_tiktok_worthy(test_headline))
    print("Series:", detect_series(test_headline))
    print("Hook:", generate_hook(test_headline))
