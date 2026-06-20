"""
CLI entry point. Runs a connector end-to-end: auth -> discover -> extract
(incremental) -> normalize -> idempotent write -> persist cursor -> print metrics.

Examples:
  python run.py list
  python run.py discover sqlite
  python run.py sync sqlite
  python run.py sync rest
  python run.py sync files
  python run.py peek sqlite customers
"""
from __future__ import annotations

import os
import sys

from connectors import REGISTRY
from framework import StateStore, WarehouseSink

DATA = os.path.join(os.path.dirname(__file__), "data")
STATE_PATH = os.path.join(os.path.dirname(__file__), "state", "state.json")
WAREHOUSE = os.path.join(DATA, "warehouse.db")

CONFIGS = {
    "sqlite": {
        "db_path": os.path.join(DATA, "source.db"),
        "cursor_fields": {"customers": "updated_at", "orders": "updated_at"},
    },
    "rest": {},
    "files": {"base_dir": os.path.join(DATA, "objects")},
}


def _connector(name: str):
    if name not in REGISTRY:
        sys.exit(f"unknown connector '{name}'. known: {', '.join(REGISTRY)}")
    return REGISTRY[name](CONFIGS.get(name, {}))


def cmd_list():
    print("connectors:", ", ".join(REGISTRY))


def cmd_discover(name: str):
    c = _connector(name)
    c.auth()
    for schema in c.discover():
        print(schema.pretty())
        print()


def cmd_sync(name: str):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    c = _connector(name)
    sink = WarehouseSink(WAREHOUSE)
    state = StateStore(STATE_PATH)
    for metrics in c.run(sink, state):
        print(metrics.summary())
    sink.close()


def cmd_peek(name: str, stream: str):
    sink = WarehouseSink(WAREHOUSE)
    print(f"{stream}: {sink.count(stream)} rows in warehouse")
    for row in sink.sample(stream):
        print(" ", row)
    sink.close()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd, *rest = sys.argv[1:]
    if cmd == "list":
        cmd_list()
    elif cmd == "discover" and rest:
        cmd_discover(rest[0])
    elif cmd == "sync" and rest:
        cmd_sync(rest[0])
    elif cmd == "peek" and len(rest) == 2:
        cmd_peek(rest[0], rest[1])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
