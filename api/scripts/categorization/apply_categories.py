"""Step 3: Apply URL-based categories to knowledge_base.

Reads:
  - url_clusters.json  — output of cluster_urls.py, contains {url, path, category}

Runs:
  ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS category VARCHAR(50);
  UPDATE knowledge_base SET category = X WHERE url = ANY(...);

Env:
  DATABASE_URL — postgres connection string
"""

import json
import os
from collections import defaultdict

import psycopg2
from dotenv import load_dotenv

load_dotenv()

OUTPUT_DIR = os.path.dirname(__file__)
CLUSTERS_FILE = os.path.join(OUTPUT_DIR, "url_clusters.json")


def main():
    with open(CLUSTERS_FILE) as f:
        clusters = json.load(f)

    by_cat: defaultdict[str, list[str]] = defaultdict(list)
    for item in clusters:
        cat = item.get("category")
        if cat and cat != "other":
            by_cat[cat].append(item["url"])

    total = sum(len(v) for v in by_cat.values())
    print(f"Mapped {total} URLs to categories:")
    for cat, cat_urls in sorted(by_cat.items(), key=lambda x: -len(x[1])):
        print(f"  {cat:<25s}: {len(cat_urls)} URLs")

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute("ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS category VARCHAR(50)")
    conn.commit()

    total_updated = 0
    for cat, cat_urls in by_cat.items():
        cur.execute(
            "UPDATE knowledge_base SET category = %s WHERE url = ANY(%s)",
            (cat, cat_urls)
        )
        total_updated += cur.rowcount

    conn.commit()
    cur.close()
    conn.close()
    print(f"Updated {total_updated} rows total.")


if __name__ == "__main__":
    main()
