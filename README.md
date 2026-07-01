# mini-connector-framework

A small, runnable connector framework for learning the concepts in *Part 2 — Data
connectors*. The whole point: **cross-cutting concerns live once in the framework
and are inherited; each source adapter only describes what's unique.**


## Quickstart

```bash
python3 seed.py                 # generate sample SQLite db + CSV/JSONL files
python3 run.py list             # list connectors
python3 run.py discover sqlite  # show discovered schema (native type -> IR)
python3 run.py sync sqlite      # full extract -> normalize -> warehouse
python3 seed.py --mutate        # change a few rows
python3 run.py sync sqlite      # incremental: only the changed rows re-read
python3 run.py peek sqlite customers

# REST connector needs the mock API running in another terminal:
python3 -m mock.rest_server     # terminal 1
python3 run.py sync rest        # terminal 2 (watch retries fire on 429s)

python3 run.py sync files       # CSV + JSONL, schema-on-read
```

## Layout

```
framework/            the reusable primitives (inherited by every connector)
  ir.py               IRType / IRField / IRSchema / IRRecord  <-- the IR
  normalize.py        TypeMapper, coerce(), schema-on-read inference, drift widening
  base.py             Connector base class: the sync orchestration loop
  pagination.py       Keyset / Cursor / Offset paginators behind one interface
  retry.py            TokenBucket (proactive) + retry()/backoff (reactive, Retry-After)
  state.py            cursor/watermark persistence + overlapping-window lookback
  sink.py             idempotent UPSERT warehouse (keyed by dedupe_key)
  observability.py    structured logs + per-run RunMetrics
connectors/
  sqlite_connector.py relational: catalog discovery, keyset pages, watermark incremental
  rest_connector.py   cursor pagination, 429/Retry-After, since-filter + overlap
  file_connector.py   S3 stand-in: list objects, schema-on-read, mtime incremental
mock/rest_server.py   fake paginated, rate-limited /events API
run.py / seed.py      CLI + sample-data generator
```

## How the spec maps to the code

| Concept (from the brief)        | Where it lives                                        |
|---------------------------------|------------------------------------------------------|
| Anatomy of a connector          | `framework/base.py` (everything inherited)           |
| Auth / token refresh            | `Connector.auth()` overridden per adapter            |
| Discovery (schema)              | `*.discover()` -> `IRSchema`                          |
| Extraction: full snapshot       | `file_connector`, `sqlite` no-cursor path            |
| Extraction: incremental watermark | `sqlite_connector.read()` `WHERE updated_at > :cursor` |
| Pagination (one abstraction)    | `framework/pagination.py`                            |
| Keyset/seek (not OFFSET)        | `KeysetPaginator` + `sqlite_connector`               |
| Cursor/token pagination         | `CursorPaginator` + `rest_connector`                 |
| Rate-limit compliance           | `TokenBucket` + `RateLimitError(retry_after=...)`    |
| Retries / backoff + jitter      | `framework/retry.py`                                 |
| Incremental state / cursor      | `framework/state.py`                                 |
| Overlapping window + dedupe     | `state.read_window_start()` + sink upsert            |
| **Type normalization -> IR**    | `framework/normalize.py` + `framework/ir.py`         |
| Schema-on-read / drift          | `infer_ir_type()` + `merge_inferred()`               |
| Idempotency                     | `IRRecord.dedupe_key()` + `WarehouseSink.write_batch`|
| Observability                   | `framework/observability.py`                         |

## The IR layer (the centerpiece)

Downstream code never sees a `NUMERIC(10,2)`, a CSV's `"true"` string, or a REST
JSON blob. Each adapter declares a `TypeMapper` (native type -> `IRType`); the
framework coerces every value into the canonical Python form. Adding a new source
is then "declare a type map + implement `read()`" — everything else is free.

## Suggested exercises (deliberately left undone)

1. **Add a connector**: a JSON REST API of your choice. You only write `auth()`,
   `discover()`, `read()`, and a `TypeMapper`.
2. **CDC instead of watermark**: tail SQLite's `data_version` / a trigger-written
   audit table to capture deletes (watermark misses hard deletes — see the brief).
3. **Per-page checkpointing**: today `retry()` wraps the whole stream read; make it
   retry per page and persist the cursor incrementally so a crash resumes mid-stream.
4. **Decimal precision**: thread `precision`/`scale` from `NUMERIC(10,2)` into
   `IRField` and assert the sink preserves it.
5. **Parquet object**: extend `file_connector` to read a `.parquet` file (embedded
   schema -> no inference needed; predicate pushdown).
6. **GraphQL adapter**: use an introspection query to self-configure `discover()`.
```
