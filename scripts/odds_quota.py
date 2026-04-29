#!/usr/bin/env python3
"""Odds API quota manager — tracks usage and enforces daily budget."""
import os, json, sqlite3
from datetime import datetime, timezone
from pathlib import Path

QUOTA_FILE = Path("/root/90minwaffle/data/odds_quota.json")
MONTHLY_LIMIT = 500
DATA_DIR = Path("/root/90minwaffle/data")

def _load():
    if not QUOTA_FILE.exists():
        return {"month": datetime.now(timezone.utc).strftime("%Y-%m"), "used": 0, "last_reset": ""}
    try:
        return json.loads(QUOTA_FILE.read_text())
    except:
        return {"month": datetime.now(timezone.utc).strftime("%Y-%m"), "used": 0, "last_reset": ""}

def _save(data):
    QUOTA_FILE.write_text(json.dumps(data, indent=2))

def get_remaining():
    d = _load()
    # Reset if new month
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if d.get("month") != current_month:
        d = {"month": current_month, "used": 0, "last_reset": datetime.now(timezone.utc).isoformat()}
        _save(d)
    return MONTHLY_LIMIT - d.get("used", 0)

def get_daily_budget():
    """How many requests can we spend today."""
    remaining = get_remaining()
    if remaining <= 0:
        return 0
    # Days left in month
    now = datetime.now(timezone.utc)
    import calendar
    days_in_month = calendar.monthrange(now.year, now.month)[1]
    days_left = max(1, days_in_month - now.day + 1)
    # Budget = remaining / days_left, minimum 1 if we have any left
    budget = max(1, remaining // days_left)
    return budget

def can_spend(n=1):
    """Check if we can afford n requests today."""
    remaining = get_remaining()
    budget = get_daily_budget()
    d = _load()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_used = d.get("today_used", 0) if d.get("today_date") == today else 0
    return remaining >= n and today_used + n <= budget

def spend(n=1):
    """Record n requests spent."""
    d = _load()
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if d.get("month") != current_month:
        d = {"month": current_month, "used": 0}
    d["used"] = d.get("used", 0) + n
    if d.get("today_date") != today:
        d["today_date"] = today
        d["today_used"] = n
    else:
        d["today_used"] = d.get("today_used", 0) + n
    _save(d)

def sync_from_headers(remaining_header):
    """Sync actual remaining from API response headers."""
    try:
        actual_remaining = int(remaining_header)
        actual_used = MONTHLY_LIMIT - actual_remaining
        d = _load()
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        d["month"] = current_month
        d["used"] = actual_used
        _save(d)
    except:
        pass

def status():
    remaining = get_remaining()
    budget = get_daily_budget()
    d = _load()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_used = d.get("today_used", 0) if d.get("today_date") == today else 0
    return {
        "monthly_limit": MONTHLY_LIMIT,
        "used": d.get("used", 0),
        "remaining": remaining,
        "daily_budget": budget,
        "today_used": today_used,
        "month": d.get("month", ""),
    }

if __name__ == "__main__":
    s = status()
    print("Odds API Quota Status:")
    print("  Month:", s["month"])
    print("  Used:", s["used"], "/", s["monthly_limit"])
    print("  Remaining:", s["remaining"])
    print("  Daily budget:", s["daily_budget"])
    print("  Today used:", s["today_used"])
