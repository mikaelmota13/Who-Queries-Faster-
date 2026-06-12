from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any

import mysql.connector
import oracledb
import psycopg2
import pymssql

from .config import settings


def connect(dbms: str, database: str | None = None, admin: bool = False):
    if dbms == "postgres":
        conn = psycopg2.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            dbname=database or settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )
        conn.autocommit = True
        return conn

    if dbms == "mysql":
        conn = mysql.connector.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            database=database or settings.mysql_db,
            user="root" if admin else settings.mysql_user,
            password=settings.mysql_root_password if admin else settings.mysql_password,
            allow_local_infile=True,
            connection_timeout=15,
        )
        conn.autocommit = True
        return conn

    if dbms == "sqlserver":
        return pymssql.connect(
            server=settings.mssql_host,
            port=settings.mssql_port,
            user=settings.mssql_user,
            password=settings.mssql_password,
            database=database or settings.mssql_db,
            autocommit=True,
            login_timeout=20,
            timeout=settings.query_timeout_seconds,
        )

    if dbms == "oracle":
        conn = oracledb.connect(
            user=settings.oracle_user,
            password=settings.oracle_password,
            dsn=settings.oracle_dsn,
        )
        conn.autocommit = True
        return conn

    raise ValueError(f"DBMS inválido: {dbms}")


def execute(conn, sql: str, params: Any | None = None) -> None:
    cur = conn.cursor()
    try:
        cur.execute(sql, params or None)
    finally:
        cur.close()


def fetch_scalar(conn, sql: str):
    cur = conn.cursor()
    try:
        cur.execute(sql)
        row = cur.fetchone()
        return None if row is None else row[0]
    finally:
        cur.close()


def fetch_all_count(cursor) -> int:
    if cursor.description is None:
        return 0
    total = 0
    while True:
        rows = cursor.fetchmany(10000)
        if not rows:
            return total
        total += len(rows)


def wait_for(dbms: str, timeout: int = 900) -> None:
    start = time.time()
    last_err = None
    while time.time() - start < timeout:
        try:
            if dbms == "sqlserver":
                ensure_sqlserver_database()
            with connect(dbms) as conn:
                if dbms == "oracle":
                    fetch_scalar(conn, "SELECT 1 FROM dual")
                else:
                    fetch_scalar(conn, "SELECT 1")
            print(f"{dbms}: pronto")
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(5)
    raise RuntimeError(f"Timeout aguardando {dbms}: {last_err}")


def ensure_sqlserver_database() -> None:
    conn = pymssql.connect(
        server=settings.mssql_host,
        port=settings.mssql_port,
        user=settings.mssql_user,
        password=settings.mssql_password,
        database="master",
        autocommit=True,
        login_timeout=20,
        timeout=30,
    )
    try:
        cur = conn.cursor()
        cur.execute(f"IF DB_ID('{settings.mssql_db}') IS NULL CREATE DATABASE {settings.mssql_db}")
        cur.close()
    finally:
        conn.close()
