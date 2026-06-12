from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from tqdm import tqdm

from .config import settings
from .db import execute
from .schema import TABLE_BY_NAME, LOAD_ORDER, Column


def _cols(table: str) -> list[str]:
    return [c.name for c in TABLE_BY_NAME[table].columns]


def load_postgres(conn) -> None:
    for table in tqdm(LOAD_ORDER, desc="LOAD postgres"):
        path = settings.clean_dir / f"{table}.tbl"
        columns = ", ".join(_cols(table))
        sql = f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, DELIMITER '|', NULL '')"
        with path.open("r", encoding="utf-8") as f:
            cur = conn.cursor()
            cur.copy_expert(sql, f)
            cur.close()


def load_mysql(conn) -> None:
    for table in tqdm(LOAD_ORDER, desc="LOAD mysql"):
        path = settings.clean_dir / f"{table}.tbl"
        columns = ", ".join(_cols(table))
        sql = f"""
        LOAD DATA LOCAL INFILE '{path.as_posix()}'
        INTO TABLE {table}
        FIELDS TERMINATED BY '|'
        LINES TERMINATED BY '\n'
        ({columns})
        """
        cur = conn.cursor()
        cur.execute(sql)
        cur.close()


def load_sqlserver(conn) -> None:
    for table in tqdm(LOAD_ORDER, desc="LOAD sqlserver"):
        sql = f"""
        BULK INSERT dbo.{table}
        FROM '/tpch-data/{table}.tbl'
        WITH (
            FIELDTERMINATOR = '|',
            ROWTERMINATOR = '0x0a',
            TABLOCK,
            KEEPNULLS
        )
        """
        execute(conn, sql)


def _convert_row(row: list[str], cols: Iterable[Column]) -> list[object]:
    values: list[object] = []
    for value, col in zip(row, cols):
        if value == "":
            values.append(None)
        elif col.kind == "int":
            values.append(int(value))
        elif col.kind == "decimal":
            values.append(float(value))
        else:
            values.append(value)
    return values


def load_oracle(conn, chunk_size: int = 20000) -> None:
    for table in tqdm(LOAD_ORDER, desc="LOAD oracle"):
        t = TABLE_BY_NAME[table]
        path = settings.clean_dir / f"{table}.tbl"
        names = [c.name for c in t.columns]
        placeholders: list[str] = []
        bind_idx = 1
        for c in t.columns:
            if c.kind == "date":
                placeholders.append(f"TO_DATE(:{bind_idx}, 'YYYY-MM-DD')")
            else:
                placeholders.append(f":{bind_idx}")
            bind_idx += 1
        sql = f"INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join(placeholders)})"

        cur = conn.cursor()
        batch: list[list[object]] = []
        with path.open("r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter="|")
            for row in reader:
                batch.append(_convert_row(row, t.columns))
                if len(batch) >= chunk_size:
                    cur.executemany(sql, batch)
                    batch.clear()
            if batch:
                cur.executemany(sql, batch)
        cur.close()


def load_data(conn, dbms: str) -> None:
    if dbms == "postgres":
        load_postgres(conn)
    elif dbms == "mysql":
        load_mysql(conn)
    elif dbms == "sqlserver":
        load_sqlserver(conn)
    elif dbms == "oracle":
        load_oracle(conn)
    else:
        raise ValueError(dbms)
