import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/root/statiq/data/cache.db"

def log_bet_result(fixture_id, market, won, odds):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS bet_results (
        date TEXT, fixture_id TEXT, market TEXT, won INTEGER, odds REAL, profit REAL)""")
    profit = (odds - 1) if won else -1
    conn.execute("INSERT INTO bet_results VALUES (?,?,?,?,?,?)", 
                 (datetime.now().isoformat(), fixture_id, market, int(won), odds, profit))
    conn.commit()
    conn.close()

def get_performance(days=30):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT won, profit FROM bet_results WHERE date > ?", 
                       ((datetime.now() - timedelta(days=days)).isoformat(),)).fetchall()
    conn.close()
    if not rows:
        return "No betting data yet"
    wins = sum(r[0] for r in rows)
    total = len(rows)
    total_profit = sum(r[1] for r in rows)
    return f"Win Rate: {wins}/{total} ({wins/total*100:.1f}%) | Profit: {total_profit:.2f} units"
