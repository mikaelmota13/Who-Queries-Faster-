from __future__ import annotations

from .config import settings
from .db import connect, execute, fetch_scalar, wait_for
from .load_data import load_data
from .schema import DROP_ORDER, EXTRA_INDEXES, LOAD_ORDER, TABLES, create_table_sql, drop_table_sql, index_sql, pk_sql


def maybe_count(conn, dbms: str, table: str) -> int:
    if dbms == "oracle":
        return int(fetch_scalar(conn, f"SELECT COUNT(*) FROM {table}"))
    return int(fetch_scalar(conn, f"SELECT COUNT(*) FROM {table}"))


def init_db(dbms: str) -> None:
    print(f"\n=== Inicializando {dbms} ===")
    wait_for(dbms)
    conn = connect(dbms)
    try:
        for table in DROP_ORDER:
            print(f"drop {table}")
            execute(conn, drop_table_sql(table, dbms))

        for table in TABLES:
            print(f"create {table.name}")
            execute(conn, create_table_sql(table, dbms))

        load_data(conn, dbms)

        if settings.create_indexes:
            for table in TABLES:
                print(f"pk {table.name}")
                try:
                    execute(conn, pk_sql(table, dbms))
                except Exception as exc:  # noqa: BLE001
                    print(f"WARN pk {table.name}: {exc}")

            for table, cols in EXTRA_INDEXES.items():
                for col in cols:
                    print(f"idx {table}.{col}")
                    try:
                        execute(conn, index_sql(table, col, dbms))
                    except Exception as exc:  # noqa: BLE001
                        print(f"WARN idx {table}.{col}: {exc}")

        for table in LOAD_ORDER:
            print(f"{dbms}.{table}: {maybe_count(conn, dbms, table)}")
    finally:
        conn.close()


def main() -> None:
    if not settings.clean_dir.exists():
        raise RuntimeError("data/tpch_clean não existe. Rode: make tpch")
    for dbms in settings.dbms:
        init_db(dbms)


if __name__ == "__main__":
    main()
