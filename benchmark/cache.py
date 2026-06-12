from __future__ import annotations

from dataclasses import dataclass

import oracledb

from .config import settings
from .db import connect, execute


@dataclass(frozen=True)
class CacheClearResult:
    ok: bool
    error: str = ""


def _try_exec(conn, sql: str, errors: list[str]) -> None:
    try:
        execute(conn, sql)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{sql}: {str(exc).replace(chr(10), ' ')[:300]}")


def clear_database_cache(dbms: str) -> CacheClearResult:
    """Clear DB-level data/plan caches as far as each engine allows.

    Notes:
    - PostgreSQL and MySQL do not expose a full portable command equivalent to
      SQL Server DBCC DROPCLEANBUFFERS. For strict cold-cache experiments, restart
      the DB container between runs. This function still clears planner/session/table
      caches where supported.
    - SQL Server and Oracle expose explicit buffer/plan cache flush commands.
    """
    errors: list[str] = []

    try:
        if dbms == "postgres":
            conn = connect("postgres")
            try:
                conn.autocommit = True
                _try_exec(conn, "CHECKPOINT", errors)
                _try_exec(conn, "DISCARD ALL", errors)
            finally:
                conn.close()

            return CacheClearResult(not errors, " | ".join(errors))

        if dbms == "mysql":
            # Needs root privileges for FLUSH TABLES/STATUS.
            conn = connect("mysql", admin=True)
            try:
                _try_exec(conn, "FLUSH TABLES", errors)
                _try_exec(conn, "FLUSH STATUS", errors)
                _try_exec(conn, "FLUSH OPTIMIZER_COSTS", errors)
            finally:
                conn.close()
            return CacheClearResult(not errors, " | ".join(errors))

        if dbms == "sqlserver":
            with connect("sqlserver") as conn:
                _try_exec(conn, "CHECKPOINT", errors)
                _try_exec(conn, "DBCC DROPCLEANBUFFERS WITH NO_INFOMSGS", errors)
                _try_exec(conn, "DBCC FREEPROCCACHE WITH NO_INFOMSGS", errors)
                _try_exec(conn, "DBCC FREESYSTEMCACHE('ALL') WITH NO_INFOMSGS", errors)
            return CacheClearResult(not errors, " | ".join(errors))

        if dbms == "oracle":
            conn = oracledb.connect(
                user="sys",
                password=settings.oracle_sys_password,
                dsn=settings.oracle_dsn,
                mode=oracledb.AUTH_MODE_SYSDBA,
            )
            try:
                conn.autocommit = True
                _try_exec(conn, "ALTER SYSTEM CHECKPOINT", errors)
                _try_exec(conn, "ALTER SYSTEM FLUSH BUFFER_CACHE", errors)
                _try_exec(conn, "ALTER SYSTEM FLUSH SHARED_POOL", errors)
            finally:
                conn.close()
            return CacheClearResult(not errors, " | ".join(errors))

        return CacheClearResult(False, f"DBMS inválido: {dbms}")
    except Exception as exc:  # noqa: BLE001
        return CacheClearResult(False, str(exc).replace("\n", " ")[:1000])
