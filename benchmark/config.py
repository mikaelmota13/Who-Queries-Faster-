from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def _csv_env(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


def _int_csv_env(name: str, default: str) -> list[int]:
    return [int(x) for x in _csv_env(name, default)]


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    raw_dir: Path = ROOT / "data" / "tpch_raw"
    clean_dir: Path = ROOT / "data" / "tpch_clean"
    query_dir: Path = ROOT / "queries"
    results_dir: Path = ROOT / "results"

    sf: float = float(os.getenv("TPCH_SCALE_FACTOR", "1"))
    dbms: tuple[str, ...] = tuple(_csv_env("DBMS", "postgres,mysql,sqlserver,oracle"))
    concurrency_levels: tuple[int, ...] = tuple(_int_csv_env("CONCURRENCY_LEVELS", "1,5,10,25,50"))
    repetitions: int = int(os.getenv("REPETITIONS", "3"))
    warmup_runs: int = int(os.getenv("WARMUP_RUNS", "1"))
    query_timeout_seconds: int = int(os.getenv("QUERY_TIMEOUT_SECONDS", "0"))
    create_indexes: bool = os.getenv("CREATE_INDEXES", "true").lower() in {"1", "true", "yes", "y"}

    # Protocol requested for the paper
    sequential_iterations: int = int(os.getenv("SEQUENTIAL_ITERATIONS", "10"))
    speedup_iterations: int = int(os.getenv("SPEEDUP_ITERATIONS", "5"))
    speedup_threads: tuple[int, ...] = tuple(_int_csv_env("SPEEDUP_THREADS", "1,4,8,16"))
    throughput_query_id: int = int(os.getenv("THROUGHPUT_QUERY_ID", "1"))
    throughput_seconds: int = int(os.getenv("THROUGHPUT_SECONDS", "120"))
    throughput_threads: int = int(os.getenv("THROUGHPUT_THREADS", "1"))
    clear_cache_between_runs: bool = os.getenv("CLEAR_CACHE_BETWEEN_RUNS", "true").lower() in {"1", "true", "yes", "y"}

    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "tpch")
    postgres_user: str = os.getenv("POSTGRES_USER", "tpch")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "tpchpass")

    mysql_host: str = os.getenv("MYSQL_HOST", "mysql")
    mysql_port: int = int(os.getenv("MYSQL_PORT", "3306"))
    mysql_db: str = os.getenv("MYSQL_DATABASE", "tpch")
    mysql_user: str = os.getenv("MYSQL_USER", "tpch")
    mysql_password: str = os.getenv("MYSQL_PASSWORD", "tpchpass")
    mysql_root_password: str = os.getenv("MYSQL_ROOT_PASSWORD", "rootpass")

    mssql_host: str = os.getenv("MSSQL_HOST", "sqlserver")
    mssql_port: int = int(os.getenv("MSSQL_PORT", "1433"))
    mssql_db: str = os.getenv("MSSQL_DB", "tpch")
    mssql_user: str = os.getenv("MSSQL_USER", "sa")
    mssql_password: str = os.getenv("MSSQL_SA_PASSWORD", "StrongPassw0rd!")

    oracle_dsn: str = os.getenv("ORACLE_DSN", "oracle:1521/FREEPDB1")
    oracle_user: str = os.getenv("ORACLE_USER", "tpch")
    oracle_password: str = os.getenv("ORACLE_PASSWORD", "tpchpass")
    oracle_sys_password: str = os.getenv("ORACLE_SYS_PASSWORD", "StrongPassw0rd!")


settings = Settings()
settings.results_dir.mkdir(parents=True, exist_ok=True)
