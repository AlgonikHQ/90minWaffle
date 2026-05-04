#!/usr/bin/env python3
"""
statiq_bridge.py — Cross-bot intelligence between 90minWaffle and StatiqFC.

When StatiqFC identifies an edge on a fixture, 90minWaffle should:
1. Know about it when generating F3 previews for that fixture
2. Frame the preview around the statistical evidence
3. Subtly prime the audience before StatiqFC fires the alert

This bridge reads StatiqFC's selections DB and exposes relevant edges
to 90minWaffle's script generation pipeline.

Also: when 90minWaffle publishes an F4 result, check if StatiqFC had
an edge on that game and post a combined "result + edge outcome" card.

Zero API cost — reads directly from StatiqFC's SQLite DB.
"""

import sqlite3
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

STATIQ_DB   = "/root/statiq/data/cache.db"
WAFFLE_DB   = "/root/90minwaffle/data/waffle.db"
LOG_PATH    = "/root/90minwaffle/logs/statiq_bridge.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [BRIDGE] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()]
)
log = logging.getLogger(__name__)


def get_todays_edges() -> list[dict]:
    """
    Return all StatiqFC edges from today that are still pending.
    Used by 90minWaffle to frame F3 previews around edge context.
    """
    if not Path(STATIQ_DB).exists():
        return []
    try:
        conn = sqlite3.connect(STATIQ_DB)
        conn.row_factory = sqlite3.Row
        today = datetime.utcnow().strftime("%Y-%m-%d")
        rows = conn.execute("""
            SELECT fixture_id, home, away, market, odds, score,
                   reasoning, layers_json, created_at, result, league
            FROM selections
            WHERE created_at LIKE ?
            ORDER BY created_at DESC
        """, (today + "%",)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"StatiqFC DB read failed: {e}")
        return []


def find_edge_for_fixture(home: str, away: str) -> dict | None:
    """
    Find a StatiqFC edge for a specific fixture.
    Used when generating F3 previews — if an edge exists, enrich the stats block.
    """
    edges = get_todays_edges()
    home_l = home.lower()
    away_l = away.lower()

    for edge in edges:
        h = (edge.get("home") or "").lower()
        a = (edge.get("away") or "").lower()
        if (home_l in h or h in home_l) and (away_l in a or a in away_l):
            return edge
        if (home_l in a or a in home_l) and (away_l in h or h in away_l):
            return edge
    return None


def build_edge_context_block(edge: dict) -> str:
    """
    Build a stat context string for script_gen.py to include in F3 previews.
    This primes the audience for the StatiqFC alert without revealing the pick.
    """
    if not edge:
        return ""

    market_labels = {
        "BTTS":     "Both Teams to Score",
        "OVER25":   "Over 2.5 Goals",
        "CS_HOME":  "Home Clean Sheet",
        "HOME_WIN": "Home Win",
        "AWAY_WIN": "Away Win",
    }

    market   = edge.get("market", "")
    label    = market_labels.get(market, market)
    reasoning = edge.get("reasoning", "")
    score    = edge.get("score", 0)
    home     = edge.get("home", "")
    away     = edge.get("away", "")

    block = (
        f"STATIQ_EDGE: Model has flagged {label} for {home} vs {away} "
        f"(confidence {score}/6). {reasoning} "
        f"Use this context to frame the preview around statistical evidence. "
        f"Do NOT mention StatiqFC or betting explicitly — frame as analytical insight."
    )
    return block


def get_pending_edge_results() -> list[dict]:
    """
    Find StatiqFC edges where result is now known but hasn't been
    cross-referenced with a 90minWaffle F4 story yet.
    Used to auto-generate "edge hit/miss" content.
    """
    if not Path(STATIQ_DB).exists():
        return []
    try:
        conn = sqlite3.connect(STATIQ_DB)
        conn.row_factory = sqlite3.Row
        # Edges settled in last 24h
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        rows = conn.execute("""
            SELECT fixture_id, home, away, market, odds, result,
                   profit, reasoning, league, settled_at
            FROM selections
            WHERE result IN ('WIN', 'LOSS')
            AND settled_at > ?
            ORDER BY settled_at DESC
        """, (cutoff,)).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"Edge results read failed: {e}")
        return []


def generate_receipt_message(edge: dict) -> str:
    """
    Generate a cross-platform receipt message when an edge settles.
    Used by receipt_poster.py (coming Monday with X API).
    Format suitable for Telegram, Discord, and X.
    """
    market_labels = {
        "BTTS": "Both Teams to Score", "OVER25": "Over 2.5 Goals",
        "CS_HOME": "Home Clean Sheet", "HOME_WIN": "Home Win", "AWAY_WIN": "Away Win",
    }

    result  = edge.get("result", "")
    home    = edge.get("home", "")
    away    = edge.get("away", "")
    market  = edge.get("market", "")
    odds    = edge.get("odds", 0)
    profit  = edge.get("profit", 0)
    label   = market_labels.get(market, market)
    league  = edge.get("league", "")

    if result == "WIN":
        emoji = "✅"
        outcome = f"+{abs(profit):.2f}u"
        tone = "Model correct."
    else:
        emoji = "❌"
        outcome = f"-{abs(profit):.2f}u"
        tone = "Model wrong — we post the misses too."

    msg = (
        f"{emoji} *STATIQFC RESULT*\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"*{home} vs {away}*\n"
        f"Market: {label}\n"
        f"Odds: {odds} | Result: *{result}* {outcome}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"_{tone}_\n"
        f"Track record → @StatiqFCpicks"
    )
    return msg


def post_edge_receipts_to_waffle():
    """
    Post settled edge receipts to 90minWaffle bets Telegram channel.
    Called from orchestrator on heavy cycles.
    Non-critical — failures logged but don't break anything.
    """
    edges = get_pending_edge_results()
    if not edges:
        return 0

    # Check which ones we've already posted
    waffle_conn = sqlite3.connect(WAFFLE_DB)
    posted = 0

    for edge in edges:
        fixture_id = edge.get("fixture_id", "")

        # Check if already posted
        existing = waffle_conn.execute(
            "SELECT id FROM stories WHERE guid LIKE ? AND status='published'",
            (f"bridge_{fixture_id}%",)
        ).fetchone()

        if existing:
            continue

        msg = generate_receipt_message(edge)

        # Post to 90minWaffle bets Telegram channel
        try:
            import sys
            sys.path.insert(0, "/root/90minwaffle/scripts")
            from telegram_poster import send_bets_card
            import asyncio
            asyncio.run(send_bets_card(msg))

            # Mark as posted in waffle DB
            waffle_conn.execute("""
                INSERT OR IGNORE INTO stories
                (guid, title, url, source, status, score, format, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (
                f"bridge_{fixture_id}_{edge['market']}",
                f"StatiqFC: {edge['home']} vs {edge['away']} [{edge['market']}] {edge['result']}",
                "", "StatiqFC Bridge", "published", 60, "F8",
                datetime.utcnow().isoformat()
            ))
            waffle_conn.commit()
            posted += 1
            log.info(f"Receipt posted: {edge['home']} vs {edge['away']} [{edge['result']}]")
        except Exception as e:
            log.error(f"Receipt post failed: {e}")

    waffle_conn.close()
    log.info(f"Bridge receipts posted: {posted}")
    return posted


if __name__ == "__main__":
    print("=== TODAY'S STATIQFC EDGES ===")
    for edge in get_todays_edges():
        print(f"  {edge['home']} vs {edge['away']} [{edge['market']}] score={edge['score']} result={edge['result']}")

    print("\n=== PENDING RECEIPTS ===")
    for edge in get_pending_edge_results():
        print(generate_receipt_message(edge))
        print()
