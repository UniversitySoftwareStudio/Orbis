"""
Step 4: Add parent_category column to knowledge_base and populate from hierarchy.

Env:
  DATABASE_URL — postgres connection string
"""

import os

import psycopg2
from dotenv import load_dotenv

from category_hierarchy import PARENT

load_dotenv()


def main():
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    cur = conn.cursor()

    cur.execute(
        "ALTER TABLE knowledge_base ADD COLUMN IF NOT EXISTS parent_category VARCHAR(50)"
    )
    conn.commit()

    # Group categories by parent for bulk updates
    from collections import defaultdict
    by_parent: defaultdict[str, list[str]] = defaultdict(list)
    for child, parent in PARENT.items():
        by_parent[parent].append(child)

    total = 0
    for parent, children in sorted(by_parent.items()):
        cur.execute(
            "UPDATE knowledge_base SET parent_category = %s WHERE category = ANY(%s)",
            (parent, children),
        )
        updated = cur.rowcount
        total += updated
        print(f"  {parent:<20s}: {updated} rows")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nTotal: {total} rows updated.")


if __name__ == "__main__":
    main()
