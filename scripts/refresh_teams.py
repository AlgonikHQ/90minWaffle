#!/usr/bin/env python3
"""refresh_teams — weekly cron / systemd timer entry point.

Pulls every team from every league configured in leagues_config.LEAGUES
into the local cache at /root/90minwaffle/data/teams.json.

Usage:
    /root/90minwaffle/venv/bin/python3 /root/90minwaffle/scripts/refresh_teams.py
    /root/90minwaffle/venv/bin/python3 /root/90minwaffle/scripts/refresh_teams.py --verbose
"""

import sys
import time

from sportsdb_registry import refresh_teams


def main() -> int:
    verbose = "--verbose" in sys.argv or "-v" in sys.argv
    started = time.time()
    try:
        count = refresh_teams(verbose=verbose)
    except Exception as e:
        print(f"[refresh_teams] FATAL: {e}", file=sys.stderr)
        return 1
    elapsed = time.time() - started
    print(f"[refresh_teams] cached {count} teams in {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
