"""
Generate sample data for the SQLite and file connectors.

  python seed.py            # create data/source.db + data/objects/*.{csv,jsonl}
  python seed.py --mutate   # bump some rows' updated_at to test incremental sync
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import random
import sqlite3
import sys

DATA = os.path.join(os.path.dirname(__file__), "data")
DB = os.path.join(DATA, "source.db")
OBJ = os.path.join(DATA, "objects")
BASE = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)


def _ts(i: int) -> str:
    return (BASE + dt.timedelta(hours=i)).isoformat()


def seed_db():
    conn = sqlite3.connect(DB)
    conn.executescript(
        """
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS orders;
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            is_active BOOLEAN,
            credit_limit NUMERIC(10,2),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            total NUMERIC(10,2),
            status TEXT,
            updated_at TIMESTAMP
        );
        """
    )
    for i in range(1, 41):
        conn.execute(
            "INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
            (i, f"Customer {i}", f"c{i}@example.com", i % 2,
             round(random.uniform(100, 9999), 2), _ts(i), _ts(i)),
        )
    for i in range(1, 81):
        conn.execute(
            "INSERT INTO orders VALUES (?,?,?,?,?)",
            (i, random.randint(1, 40), round(random.uniform(5, 2000), 2),
             random.choice(["new", "shipped", "delivered"]), _ts(i)),
        )
    conn.commit()
    conn.close()
    print(f"seeded {DB}: 40 customers, 80 orders")


def seed_objects():
    os.makedirs(OBJ, exist_ok=True)
    # CSV: stringly typed -> exercises schema-on-read inference + coercion
    with open(os.path.join(OBJ, "signups.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "email", "plan", "trial_days", "mrr", "verified", "joined_at"])
        for i in range(1, 26):
            w.writerow([i, f"u{i}@example.com", random.choice(["free", "team", "biz"]),
                        random.randint(0, 30), round(random.uniform(0, 299), 2),
                        random.choice(["true", "false"]), _ts(i)])
    # JSONL: real types incl. nested object -> IR JSON
    with open(os.path.join(OBJ, "pageviews.jsonl"), "w") as f:
        for i in range(1, 31):
            f.write(json.dumps({
                "id": i,
                "path": random.choice(["/", "/pricing", "/docs"]),
                "ms": random.randint(20, 900),
                "meta": {"bot": random.random() < 0.1, "ref": "google"},
            }) + "\n")
    print(f"seeded {OBJ}: signups.csv (25), pageviews.jsonl (30)")


def mutate():
    """Add new rows + touch some updated_at so an incremental run picks them up."""
    conn = sqlite3.connect(DB)
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    conn.execute("INSERT INTO customers VALUES (?,?,?,?,?,?,?)",
                 (41, "New Customer 41", "c41@example.com", 1, 500.0, now, now))
    conn.execute("UPDATE customers SET credit_limit=credit_limit+1, updated_at=? WHERE id IN (1,2,3)", (now,))
    conn.commit()
    conn.close()
    print("mutated source.db: +1 customer, touched ids 1,2,3 (run incremental to see the delta)")


if __name__ == "__main__":
    os.makedirs(DATA, exist_ok=True)
    if "--mutate" in sys.argv:
        mutate()
    else:
        seed_db()
        seed_objects()
