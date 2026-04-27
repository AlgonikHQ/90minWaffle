#!/usr/bin/env python3
"""90minWaffle Data Fetcher - football-data.org free tier"""
import os, json, time, logging, requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv("/root/90minwaffle/.env")

API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "").strip()
BASE_URL = "https://api.football-data.org/v4"
CACHE_DIR = Path("/root/90minwaffle/data/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = "/root/90minwaffle/logs/data_fetcher.log"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_PATH), logging.StreamHandler()])
log = logging.getLogger(__name__)

COMPS = {
    "PL": "Premier League",
    "ELC": "Championship",
    "CL": "Champions League",
    "PD": "La Liga",
    "BL1": "Bundesliga",
    "SA": "Serie A",
    "FL1": "Ligue 1"
}

CACHE_TTL = {"standings": 3600, "matches": 1800, "scorers": 7200, "competitions": 86400}

def _cache_path(name): return CACHE_DIR / f"{name}.json"

def _is_fresh(name, ttl):
    p = _cache_path(name)
    if not p.exists(): return False
    age = time.time() - p.stat().st_mtime
    return age < ttl

def _read_cache(name):
    try: return json.loads(_cache_path(name).read_text())
    except Exception: return None

def _write_cache(name, data):
    _cache_path(name).write_text(json.dumps(data, indent=2))

def _api_get(endpoint):
    if not API_KEY:
        log.error("FOOTBALL_DATA_API_KEY missing"); return None
    url = f"{BASE_URL}{endpoint}"
    try:
        r = requests.get(url, headers={"X-Auth-Token": API_KEY}, timeout=15)
        if r.status_code == 200: return r.json()
        if r.status_code == 429:
            log.warning("Rate limited, sleeping 65s"); time.sleep(65)
            return _api_get(endpoint)
        log.error(f"API {r.status_code}: {endpoint}"); return None
    except Exception as e:
        log.error(f"API fail {endpoint}: {e}"); return None

def fetch_standings(comp="PL", force=False):
    name = f"standings_{comp}"
    if not force and _is_fresh(name, CACHE_TTL["standings"]): return _read_cache(name)
    data = _api_get(f"/competitions/{comp}/standings")
    if data: _write_cache(name, data); log.info(f"Cached standings: {comp}")
    return data or _read_cache(name)

def fetch_matches(comp="PL", days_ahead=14, days_back=7, force=False):
    name = f"matches_{comp}"
    if not force and _is_fresh(name, CACHE_TTL["matches"]): return _read_cache(name)
    today = datetime.now(timezone.utc).date()
    date_from = (today - timedelta(days=days_back)).isoformat()
    date_to = (today + timedelta(days=days_ahead)).isoformat()
    data = _api_get(f"/competitions/{comp}/matches?dateFrom={date_from}&dateTo={date_to}")
    if data: _write_cache(name, data); log.info(f"Cached matches: {comp}")
    return data or _read_cache(name)

def fetch_scorers(comp="PL", limit=20, force=False):
    name = f"scorers_{comp}"
    if not force and _is_fresh(name, CACHE_TTL["scorers"]): return _read_cache(name)
    data = _api_get(f"/competitions/{comp}/scorers?limit={limit}")
    if data: _write_cache(name, data); log.info(f"Cached scorers: {comp}")
    return data or _read_cache(name)

def refresh_all():
    log.info("=== Data refresh starting ===")
    success = 0; total = 0
    for code in ["PL", "ELC", "CL"]:
        total += 3
        if fetch_standings(code): success += 1
        time.sleep(7)
        if fetch_matches(code): success += 1
        time.sleep(7)
        if fetch_scorers(code): success += 1
        time.sleep(7)
    log.info(f"=== Data refresh complete — {success}/{total} ===")
    return success

if __name__ == "__main__":
    refresh_all()
