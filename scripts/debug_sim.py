import sqlite3
from difflib import SequenceMatcher

DB_PATH = "/root/90minwaffle/data/waffle.db"

def similarity(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute("SELECT id, title, source FROM stories WHERE score > 0 LIMIT 100")
rows = c.fetchall()
conn.close()

stories = [{"id": r[0], "title": r[1], "source": r[2]} for r in rows]

print(f"Checking {len(stories)} stories...\n")
best_pairs = []
for i, s1 in enumerate(stories):
    for j, s2 in enumerate(stories):
        if i >= j: continue
        if s1["source"] == s2["source"]: continue
        sim = similarity(s1["title"], s2["title"])
        if sim > 0.25:
            best_pairs.append((sim, s1, s2))

best_pairs.sort(reverse=True)
print("Top 20 most similar cross-source pairs:")
for sim, s1, s2 in best_pairs[:20]:
    print(f"\n  Sim={sim:.2f}")
    print(f"  [{s1['source']}] {s1['title']}")
    print(f"  [{s2['source']}] {s2['title']}")
