from __future__ import annotations

import numpy as np
import pandas as pd

from .config import settings


def pct(series: pd.Series, q: float) -> float:
    if series.empty:
        return float("nan")
    return float(np.percentile(series.astype(float), q))


def latency_agg(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    ok = df[df["success"] == True].copy()  # noqa: E712
    if ok.empty:
        return pd.DataFrame()
    return (
        ok.groupby(group_cols, as_index=False)
        .agg(
            executions=("elapsed_seconds", "count"),
            mean_latency_s=("elapsed_seconds", "mean"),
            median_latency_s=("elapsed_seconds", "median"),
            p95_latency_s=("elapsed_seconds", lambda s: pct(s, 95)),
            p99_latency_s=("elapsed_seconds", lambda s: pct(s, 99)),
            std_latency_s=("elapsed_seconds", "std"),
            min_latency_s=("elapsed_seconds", "min"),
            max_latency_s=("elapsed_seconds", "max"),
            mean_rows=("row_count", "mean"),
        )
    )


def build_sequential_metrics() -> pd.DataFrame:
    path = settings.results_dir / "sequential_raw.csv"
    if not path.exists():
        return pd.DataFrame()
    raw = pd.read_csv(path)
    metrics = latency_agg(raw, ["dbms", "sf", "query_id"])
    if not metrics.empty:
        err = raw.groupby(["dbms", "sf", "query_id"], as_index=False).agg(
            attempts=("success", "count"),
            errors=("success", lambda s: int((s != True).sum())),  # noqa: E712
            cache_before_failures=("cache_before_ok", lambda s: int((s != True).sum())),  # noqa: E712
            cache_after_failures=("cache_after_ok", lambda s: int((s != True).sum())),  # noqa: E712
        )
        metrics = metrics.merge(err, on=["dbms", "sf", "query_id"], how="outer")
    return metrics


def build_speedup_metrics() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_path = settings.results_dir / "speedup_raw.csv"
    scenario_path = settings.results_dir / "speedup_scenario.csv"
    if not raw_path.exists() or not scenario_path.exists():
        return pd.DataFrame(), pd.DataFrame()

    raw = pd.read_csv(raw_path)
    scenario = pd.read_csv(scenario_path)

    latency = latency_agg(raw, ["dbms", "sf", "query_id", "threads"])

    scen = (
        scenario.groupby(["dbms", "sf", "query_id", "threads"], as_index=False)
        .agg(
            repetitions=("iteration", "count"),
            mean_wall_s=("wall_seconds", "mean"),
            median_wall_s=("wall_seconds", "median"),
            p95_wall_s=("wall_seconds", lambda s: pct(s, 95)),
            p99_wall_s=("wall_seconds", lambda s: pct(s, 99)),
            mean_throughput_qps=("throughput_qps", "mean"),
            median_throughput_qps=("throughput_qps", "median"),
            total_success=("queries_success", "sum"),
            total_errors=("queries_error", "sum"),
            cache_before_failures=("cache_before_ok", lambda s: int((s != True).sum())),  # noqa: E712
            cache_after_failures=("cache_after_ok", lambda s: int((s != True).sum())),  # noqa: E712
        )
    )

    rows: list[dict[str, object]] = []
    for (dbms, sf, query_id), group in scen.groupby(["dbms", "sf", "query_id"]):
        base = group[group["threads"] == 1]
        if base.empty:
            continue
        base_wall = float(base["mean_wall_s"].iloc[0])
        base_throughput = float(base["mean_throughput_qps"].iloc[0])
        for _, row in group.iterrows():
            threads = int(row["threads"])
            mean_wall = float(row["mean_wall_s"])
            mean_throughput = float(row["mean_throughput_qps"])
            throughput_speedup = mean_throughput / base_throughput if base_throughput > 0 else np.nan
            wall_speedup = base_wall / mean_wall if mean_wall > 0 else np.nan
            rows.append({
                "dbms": dbms,
                "sf": sf,
                "query_id": query_id,
                "threads": threads,
                "wall_speedup": wall_speedup,
                "throughput_speedup": throughput_speedup,
                "efficiency": throughput_speedup / threads if threads > 0 else np.nan,
            })
    speedup = pd.DataFrame(rows)
    if not speedup.empty:
        scen = scen.merge(speedup, on=["dbms", "sf", "query_id", "threads"], how="left")
    if not latency.empty:
        scen = scen.merge(latency, on=["dbms", "sf", "query_id", "threads"], how="left")
    return scen, latency


def build_fixed_time_throughput_metrics() -> pd.DataFrame:
    raw_path = settings.results_dir / "throughput_raw.csv"
    scenario_path = settings.results_dir / "throughput_scenario.csv"
    if not raw_path.exists() or not scenario_path.exists():
        return pd.DataFrame()

    raw = pd.read_csv(raw_path)
    scenario = pd.read_csv(scenario_path)
    latency = latency_agg(raw, ["dbms", "sf", "query_id"])

    scen = (
        scenario.groupby(["dbms", "sf", "query_id", "duration_seconds", "threads"], as_index=False)
        .agg(
            repetitions=("run_id", "count"),
            mean_wall_s=("wall_seconds", "mean"),
            total_executions=("executions", "sum"),
            total_success=("success", "sum"),
            total_errors=("errors", "sum"),
            mean_throughput_qps=("throughput_qps", "mean"),
            median_throughput_qps=("throughput_qps", "median"),
        )
    )
    if not latency.empty:
        scen = scen.merge(latency, on=["dbms", "sf", "query_id"], how="left")
    return scen


def build_dbms_summary(sequential: pd.DataFrame, speedup: pd.DataFrame, fixed_t: pd.DataFrame) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    if not sequential.empty:
        seq = sequential.groupby(["dbms", "sf"], as_index=False).agg(
            sequential_queries=("executions", "sum"),
            sequential_mean_latency_s=("mean_latency_s", "mean"),
            sequential_median_latency_s=("median_latency_s", "median"),
            sequential_p95_latency_s=("p95_latency_s", "mean"),
            sequential_errors=("errors", "sum"),
        )
        parts.append(seq)

    if not fixed_t.empty:
        thr = fixed_t.groupby(["dbms", "sf"], as_index=False).agg(
            q1_fixed_time_success=("total_success", "sum"),
            q1_fixed_time_mean_throughput_qps=("mean_throughput_qps", "mean"),
        )
        parts.append(thr)

    if not speedup.empty:
        sp = speedup.groupby(["dbms", "sf", "threads"], as_index=False).agg(
            mean_throughput_speedup=("throughput_speedup", "mean"),
            mean_efficiency=("efficiency", "mean"),
            mean_throughput_qps=("mean_throughput_qps", "mean"),
        )
        sp.to_csv(settings.results_dir / "dbms_speedup_summary_by_threads.csv", index=False)

    if not parts:
        return pd.DataFrame()
    summary = parts[0]
    for p in parts[1:]:
        summary = summary.merge(p, on=["dbms", "sf"], how="outer")
    return summary


def main() -> None:
    settings.results_dir.mkdir(parents=True, exist_ok=True)

    sequential = build_sequential_metrics()
    speedup, speedup_latency = build_speedup_metrics()
    fixed_t = build_fixed_time_throughput_metrics()
    summary = build_dbms_summary(sequential, speedup, fixed_t)

    if not sequential.empty:
        sequential.to_csv(settings.results_dir / "sequential_metrics.csv", index=False)
        print(f"- {settings.results_dir / 'sequential_metrics.csv'}")
    if not speedup.empty:
        speedup.to_csv(settings.results_dir / "speedup_metrics.csv", index=False)
        print(f"- {settings.results_dir / 'speedup_metrics.csv'}")
    if not speedup_latency.empty:
        speedup_latency.to_csv(settings.results_dir / "speedup_latency_metrics.csv", index=False)
        print(f"- {settings.results_dir / 'speedup_latency_metrics.csv'}")
    if not fixed_t.empty:
        fixed_t.to_csv(settings.results_dir / "throughput_fixed_time_metrics.csv", index=False)
        print(f"- {settings.results_dir / 'throughput_fixed_time_metrics.csv'}")
    if not summary.empty:
        summary.to_csv(settings.results_dir / "dbms_summary_metrics.csv", index=False)
        print(f"- {settings.results_dir / 'dbms_summary_metrics.csv'}")

    if sequential.empty and speedup.empty and fixed_t.empty:
        raise FileNotFoundError("Nenhum CSV bruto encontrado. Rode: make protocol-all ou make protocol-db DB=postgres")


if __name__ == "__main__":
    main()
