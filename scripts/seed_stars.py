import sqlite3
from datetime import datetime, timezone

DB_PATH = "/root/90minwaffle/data/waffle.db"

# Current top 30 star players — updated manually until live detection is built
STAR_PLAYERS = [
    # PL elite
    "salah", "haaland", "palmer", "saka", "rice", "trent", "alexander-arnold",
    "isak", "eze", "mbeumo", "watkins", "rashford", "fernandes", "mainoo",
    "maddison", "son", "wilson", "havertz", "odegaard", "martinelli",
    # European stars
    "mbappe", "vinicius", "bellingham", "yamal", "dembele", "lewandowski",
    "kane", "wirtz", "musiala", "ter stegen",
]

def seed_stars():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()

    for i, player in enumerate(STAR_PLAYERS):
        score = 100 - (i * 2)  # Rank-weighted seed score
        c.execute('''
            INSERT INTO star_index
                (player_name, mention_count, total_score, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(player_name) DO UPDATE SET
                total_score = ?,
                last_updated = ?
        ''', (player, 10, score, now, score, now))

    conn.commit()
    conn.close()
    print(f"[OK] Seeded {len(STAR_PLAYERS)} star players into index")

if __name__ == "__main__":
    seed_stars()
