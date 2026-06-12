from __future__ import annotations

import csv
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import settings
from .db import connect, fetch_all_count, wait_for
from .sql_rewrite import load_query

RAW_FIELDS = [
    "run_id", "timestamp_utc", "dbms", "sf", "concurrency", "repetition", "user_id",
    "query_id", "success", "elapsed_seconds", "row_count", "error",
]
SCENARIO_FIELDS = [
    "run_id", "timestamp_utc", "dbms", "sf", "concurrency", "repetition",
    "wall_seconds", "queries_submitted", "queries_success", "queries_error", "throughput_qps",
]

_write_lock = threading.Lock()


def append_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with _write_lock, path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def run_one_query(conn, dbms: str, query_id: int) -> tuple[bool, float, int, str]:
    sql = load_query(query_id, dbms)
    cur = conn.cursor()
    started = time.perf_counter()
    try:
        cur.execute(sql)
        row_count = fetch_all_count(cur)
        elapsed = time.perf_counter() - started
        return True, elapsed, row_count, ""
    except Exception as exc:  # noqa: BLE001
        elapsed = time.perf_counter() - started
        return False, elapsed, 0, str(exc).replace("\n", " ")[:1000]
    finally:
        try:
            cur.close()
        except Exception:
            pass


def worker(dbms: str, sf: float, concurrency: int, repetition: int, user_id: int, run_id: str, ts: str) -> list[dict[str, Any]]:
    conn = connect(dbms)
    rows: list[dict[str, Any]] = []
    try:
        for query_id in range(1, 23):
            ok, elapsed, nrows, error = run_one_query(conn, dbms, query_id)
            rows.append({
                "run_id": run_id,
                "timestamp_utc": ts,
                "dbms": dbms,
                "sf": sf,
                "concurrency": concurrency,
                "repetition": repetition,
                "user_id": user_id,
                "query_id": query_id,
                "success": ok,
                "elapsed_seconds": elapsed,
                "row_count": nrows,
                "error": error,
            })
    finally:
        conn.close()
    return rows


def warmup(dbms: str) -> None:
    if settings.warmup_runs <= 0:
        return
    print(f"warmup {dbms}: {settings.warmup_runs} execução(ões)")
    conn = connect(dbms)
    try:
        for _ in range(settings.warmup_runs):
            for q in range(1, 23):
                ok, elapsed, _, error = run_one_query(conn, dbms, q)
                if not ok:
                    print(f"WARN warmup {dbms} Q{q}: {error}")
                else:
                    print(f"warmup {dbms} Q{q}: {elapsed:.3f}s")
    finally:
        conn.close()


def run_scenario(dbms: str, concurrency: int, repetition: int, run_id: str, ts: str) -> None:
    print(f"\n--- {dbms} | U={concurrency} | rep={repetition} ---")
    raw_path = settings.results_dir / "raw_results.csv"
    scenario_path = settings.results_dir / "scenario_results.csv"

    wall_start = time.perf_counter()
    all_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(worker, dbms, settings.sf, concurrency, repetition, u, run_id, ts) for u in range(1, concurrency + 1)]
        for fut in as_completed(futures):
            rows = fut.result()
            append_csv(raw_path, RAW_FIELDS, rows)
            all_rows.extend(rows)
    wall = time.perf_counter() - wall_start

    success = sum(1 for r in all_rows if r["success"] is True)
    errors = len(all_rows) - success
    scenario = [{
        "run_id": run_id,
        "timestamp_utc": ts,
        "dbms": dbms,
        "sf": settings.sf,
        "concurrency": concurrency,
        "repetition": repetition,
        "wall_seconds": wall,
        "queries_submitted": len(all_rows),
        "queries_success": success,
        "queries_error": errors,
        "throughput_qps": success / wall if wall > 0 else 0,
    }]
    append_csv(scenario_path, SCENARIO_FIELDS, scenario)
    print(f"wall={wall:.3f}s success={success} errors={errors} throughput={scenario[0]['throughput_qps']:.4f} q/s")


def main() -> None:
    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    meta = {
        "run_id": run_id,
        "timestamp_utc": ts,
        "sf": settings.sf,
        "dbms": list(settings.dbms),
        "concurrency_levels": list(settings.concurrency_levels),
        "repetitions": settings.repetitions,
        "warmup_runs": settings.warmup_runs,
        "query_timeout_seconds": settings.query_timeout_seconds,
        "create_indexes": settings.create_indexes,
    }
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    (settings.results_dir / f"run_{run_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    for dbms in settings.dbms:
        wait_for(dbms)
        warmup(dbms)
        for concurrency in settings.concurrency_levels:
            for repetition in range(1, settings.repetitions + 1):
                run_scenario(dbms, concurrency, repetition, run_id, ts)

    print("\nFinalizado. Rode: make metrics")


if __name__ == "__main__":
    main()
