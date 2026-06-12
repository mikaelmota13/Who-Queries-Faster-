from __future__ import annotations

import argparse
import csv
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cache import clear_database_cache
from .config import settings
from .db import connect, fetch_all_count, wait_for
from .sql_rewrite import load_query

SEQUENTIAL_FIELDS = [
    "run_id", "timestamp_utc", "experiment", "dbms", "sf", "query_id", "iteration",
    "success", "elapsed_seconds", "row_count", "cache_before_ok", "cache_before_error",
    "cache_after_ok", "cache_after_error", "error",
]

SPEEDUP_RAW_FIELDS = [
    "run_id", "timestamp_utc", "experiment", "dbms", "sf", "query_id", "threads", "iteration",
    "worker_id", "success", "elapsed_seconds", "row_count", "error",
]

SPEEDUP_SCENARIO_FIELDS = [
    "run_id", "timestamp_utc", "experiment", "dbms", "sf", "query_id", "threads", "iteration",
    "wall_seconds", "queries_submitted", "queries_success", "queries_error", "throughput_qps",
    "cache_before_ok", "cache_before_error", "cache_after_ok", "cache_after_error",
]

THROUGHPUT_RAW_FIELDS = [
    "run_id", "timestamp_utc", "experiment", "dbms", "sf", "query_id", "worker_id",
    "execution_index", "success", "elapsed_seconds", "row_count", "cache_after_ok", "cache_after_error", "error",
]

THROUGHPUT_SCENARIO_FIELDS = [
    "run_id", "timestamp_utc", "experiment", "dbms", "sf", "query_id", "duration_seconds", "threads",
    "wall_seconds", "executions", "success", "errors", "throughput_qps",
]

_write_lock = threading.Lock()
_stop_event = threading.Event()


def append_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with _write_lock, path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def clear_cache(dbms: str):
    if not settings.clear_cache_between_runs:
        return True, ""
    result = clear_database_cache(dbms)
    if not result.ok:
        print(f"WARN cache {dbms}: {result.error}")
    return result.ok, result.error


def execute_query(dbms: str, query_id: int) -> tuple[bool, float, int, str]:
    sql = load_query(query_id, dbms)
    conn = connect(dbms)
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
        conn.close()


def run_sequential(dbms: str, run_id: str, ts: str) -> None:
    print(f"\n=== SEQUENCIAL | {dbms} | 22 queries x {settings.sequential_iterations} iterações ===")
    path = settings.results_dir / "sequential_raw.csv"

    for iteration in range(1, settings.sequential_iterations + 1):
        for query_id in range(1, 23):
            before_ok, before_err = clear_cache(dbms)
            ok, elapsed, row_count, error = execute_query(dbms, query_id)
            after_ok, after_err = clear_cache(dbms)

            row = {
                "run_id": run_id,
                "timestamp_utc": ts,
                "experiment": "sequential_latency",
                "dbms": dbms,
                "sf": settings.sf,
                "query_id": query_id,
                "iteration": iteration,
                "success": ok,
                "elapsed_seconds": elapsed,
                "row_count": row_count,
                "cache_before_ok": before_ok,
                "cache_before_error": before_err,
                "cache_after_ok": after_ok,
                "cache_after_error": after_err,
                "error": error,
            }
            append_csv(path, SEQUENTIAL_FIELDS, [row])
            status = "ok" if ok else "erro"
            print(f"{dbms} Q{query_id:02d} iter={iteration:02d}: {elapsed:.3f}s {status}")


def _speedup_worker(dbms: str, query_id: int, worker_id: int) -> dict[str, Any]:
    ok, elapsed, row_count, error = execute_query(dbms, query_id)
    return {
        "worker_id": worker_id,
        "success": ok,
        "elapsed_seconds": elapsed,
        "row_count": row_count,
        "error": error,
    }


def run_speedup(dbms: str, run_id: str, ts: str) -> None:
    print(f"\n=== SPEEDUP | {dbms} | threads={settings.speedup_threads} | reps={settings.speedup_iterations} ===")
    raw_path = settings.results_dir / "speedup_raw.csv"
    scenario_path = settings.results_dir / "speedup_scenario.csv"

    for query_id in range(1, 23):
        for threads in settings.speedup_threads:
            for iteration in range(1, settings.speedup_iterations + 1):
                before_ok, before_err = clear_cache(dbms)
                wall_start = time.perf_counter()

                rows: list[dict[str, Any]] = []
                with ThreadPoolExecutor(max_workers=threads) as pool:
                    futures = [pool.submit(_speedup_worker, dbms, query_id, wid) for wid in range(1, threads + 1)]
                    for fut in as_completed(futures):
                        r = fut.result()
                        r.update({
                            "run_id": run_id,
                            "timestamp_utc": ts,
                            "experiment": "speedup_concurrency",
                            "dbms": dbms,
                            "sf": settings.sf,
                            "query_id": query_id,
                            "threads": threads,
                            "iteration": iteration,
                        })
                        rows.append(r)

                wall = time.perf_counter() - wall_start
                after_ok, after_err = clear_cache(dbms)
                success = sum(1 for r in rows if r["success"] is True)
                errors = len(rows) - success
                scenario = {
                    "run_id": run_id,
                    "timestamp_utc": ts,
                    "experiment": "speedup_concurrency",
                    "dbms": dbms,
                    "sf": settings.sf,
                    "query_id": query_id,
                    "threads": threads,
                    "iteration": iteration,
                    "wall_seconds": wall,
                    "queries_submitted": len(rows),
                    "queries_success": success,
                    "queries_error": errors,
                    "throughput_qps": success / wall if wall > 0 else 0,
                    "cache_before_ok": before_ok,
                    "cache_before_error": before_err,
                    "cache_after_ok": after_ok,
                    "cache_after_error": after_err,
                }
                append_csv(raw_path, SPEEDUP_RAW_FIELDS, rows)
                append_csv(scenario_path, SPEEDUP_SCENARIO_FIELDS, [scenario])
                print(f"{dbms} Q{query_id:02d} threads={threads:02d} iter={iteration}: wall={wall:.3f}s ok={success}/{len(rows)}")


def _throughput_worker(dbms: str, query_id: int, worker_id: int, deadline: float, run_id: str, ts: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    local_i = 0
    while time.perf_counter() < deadline and not _stop_event.is_set():
        local_i += 1
        ok, elapsed, row_count, error = execute_query(dbms, query_id)
        after_ok, after_err = clear_cache(dbms)
        rows.append({
            "run_id": run_id,
            "timestamp_utc": ts,
            "experiment": "throughput_all_queries_fixed_time",
            "dbms": dbms,
            "sf": settings.sf,
            "query_id": query_id,
            "worker_id": worker_id,
            "execution_index": local_i,
            "success": ok,
            "elapsed_seconds": elapsed,
            "row_count": row_count,
            "cache_after_ok": after_ok,
            "cache_after_error": after_err,
            "error": error,
        })
    return rows


def run_throughput_all_queries(dbms: str, run_id: str, ts: str) -> None:
    duration = settings.throughput_seconds
    threads = settings.throughput_threads

    raw_path = settings.results_dir / "throughput_raw.csv"
    scenario_path = settings.results_dir / "throughput_scenario.csv"

    for query_id in range(1, 23):
        print(f"\n=== VAZÃO | {dbms} | Q{query_id:02d} por {duration}s | threads={threads} ===")

        before_ok, before_err = clear_cache(dbms)

        _stop_event.clear()
        start = time.perf_counter()
        deadline = start + duration
        all_rows: list[dict[str, Any]] = []

        with ThreadPoolExecutor(max_workers=threads) as pool:
            futures = [
                pool.submit(
                    _throughput_worker,
                    dbms,
                    query_id,
                    wid,
                    deadline,
                    run_id,
                    ts,
                )
                for wid in range(1, threads + 1)
            ]

            for fut in as_completed(futures):
                rows = fut.result()
                append_csv(raw_path, THROUGHPUT_RAW_FIELDS, rows)
                all_rows.extend(rows)

        wall = time.perf_counter() - start
        success = sum(1 for r in all_rows if r["success"] is True)
        errors = len(all_rows) - success

        after_ok, after_err = clear_cache(dbms)

        scenario = {
            "run_id": run_id,
            "timestamp_utc": ts,
            "experiment": "throughput_all_queries_fixed_time",
            "dbms": dbms,
            "sf": settings.sf,
            "query_id": query_id,
            "duration_seconds": duration,
            "threads": threads,
            "wall_seconds": wall,
            "executions": len(all_rows),
            "success": success,
            "errors": errors,
            "throughput_qps": success / wall if wall > 0 else 0,
        }

        append_csv(scenario_path, THROUGHPUT_SCENARIO_FIELDS, [scenario])

        print(
            f"{dbms} throughput Q{query_id:02d}: "
            f"{success} execuções em {wall:.3f}s = "
            f"{scenario['throughput_qps']:.4f} q/s"
        )


def run_dbms(dbms: str, run_id: str, ts: str) -> None:
    wait_for(dbms)
    clear_cache(dbms)
    run_sequential(dbms, run_id, ts)
    run_speedup(dbms, run_id, ts)
    run_throughput_all_queries(dbms, run_id, ts)
    clear_cache(dbms)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run requested TPC-H benchmark protocol.")
    parser.add_argument("--dbms", nargs="*", default=None, help="DBMS list: postgres mysql sqlserver oracle")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dbms_list = args.dbms or list(settings.dbms)
    run_id = str(uuid.uuid4())
    ts = datetime.now(timezone.utc).isoformat()
    meta = {
        "run_id": run_id,
        "timestamp_utc": ts,
        "sf": settings.sf,
        "dbms": dbms_list,
        "sequential_iterations": settings.sequential_iterations,
        "speedup_iterations": settings.speedup_iterations,
        "speedup_threads": list(settings.speedup_threads),
        "throughput_query_id": settings.throughput_query_id,
        "throughput_seconds": settings.throughput_seconds,
        "throughput_threads": settings.throughput_threads,
        "clear_cache_between_runs": settings.clear_cache_between_runs,
    }
    settings.results_dir.mkdir(parents=True, exist_ok=True)
    (settings.results_dir / f"protocol_run_{run_id}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    for dbms in dbms_list:
        run_dbms(dbms, run_id, ts)

    print("\nFinalizado. Rode: make metrics")


if __name__ == "__main__":
    main()
