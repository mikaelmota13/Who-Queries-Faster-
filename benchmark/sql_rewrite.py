from __future__ import annotations

import re
from pathlib import Path

from .config import settings

_COMMENT_RE = re.compile(r"--.*?$", re.MULTILINE)


def _strip(sql: str) -> str:
    sql = _COMMENT_RE.sub("", sql)
    sql = re.sub(r"\s+", " ", sql).strip()
    sql = sql.rstrip(";").strip()
    sql = re.sub(r"\blimit\s+-1\b", "", sql, flags=re.I).strip()
    sql = re.sub(r"\bday\s*\(\s*\d+\s*\)", "day", sql, flags=re.I)
    return sql


def _rewrite_limit(sql: str, dbms: str) -> str:
    m = re.search(r"\blimit\s+(\d+)\s*$", sql, flags=re.I)
    if not m:
        return sql
    n = m.group(1)
    body = sql[: m.start()].strip()
    if dbms in {"postgres", "mysql"}:
        return f"{body} LIMIT {n}"
    if dbms in {"oracle", "sqlserver"}:
        return f"{body} OFFSET 0 ROWS FETCH NEXT {n} ROWS ONLY"
    return sql


def _rewrite_common(sql: str) -> str:
    # Q22 appears in TPC-H with either SUBSTRING or substring syntax.
    sql = re.sub(
        r"substring\s*\(\s*([^()]+?)\s+from\s+(\d+)\s+for\s+(\d+)\s*\)",
        r"SUBSTRING(\1, \2, \3)",
        sql,
        flags=re.I,
    )
    return sql


def _rewrite_mysql(sql: str) -> str:
    sql = _rewrite_common(sql)

    def repl_interval(m: re.Match[str]) -> str:
        date, op, days = m.group(1), m.group(2), m.group(3)
        fn = "DATE_ADD" if op == "+" else "DATE_SUB"
        return f"{fn}(DATE '{date}', INTERVAL {days} DAY)"

    sql = re.sub(r"date\s+'([^']+)'\s*([+-])\s*interval\s+'(\d+)'\s+day", repl_interval, sql, flags=re.I)
    return _rewrite_limit(sql, "mysql")


def _rewrite_sqlserver(sql: str) -> str:
    sql = _rewrite_common(sql)

    def repl_interval(m: re.Match[str]) -> str:
        date, op, days = m.group(1), m.group(2), int(m.group(3))
        if op == "-":
            days = -days
        return f"DATEADD(day, {days}, CAST('{date}' AS DATE))"

    sql = re.sub(r"date\s+'([^']+)'\s*([+-])\s*interval\s+'(\d+)'\s+day", repl_interval, sql, flags=re.I)
    sql = re.sub(r"date\s+'([^']+)'", r"CAST('\1' AS DATE)", sql, flags=re.I)
    sql = re.sub(r"extract\s*\(\s*year\s+from\s+([^)]+?)\s*\)", r"YEAR(\1)", sql, flags=re.I)
    return _rewrite_limit(sql, "sqlserver")


def _rewrite_oracle(sql: str) -> str:
    sql = _rewrite_common(sql)
    sql = re.sub(r"SUBSTRING\s*\(", "SUBSTR(", sql, flags=re.I)
    return _rewrite_limit(sql, "oracle")


def rewrite_sql(sql: str, dbms: str) -> str:
    sql = _strip(sql)
    if dbms == "postgres":
        return _rewrite_limit(sql, dbms)
    if dbms == "mysql":
        return _rewrite_mysql(sql)
    if dbms == "sqlserver":
        return _rewrite_sqlserver(sql)
    if dbms == "oracle":
        return _rewrite_oracle(sql)
    raise ValueError(f"DBMS inválido: {dbms}")


def load_query(query_id: int, dbms: str) -> str:
    path = settings.query_dir / f"q{query_id}.sql"
    if not path.exists():
        raise FileNotFoundError(f"Consulta ausente: {path}. Rode: make tpch")

    sql = path.read_text(encoding="utf-8", errors="replace")

    # Remove lixo gerado pelo qgen em modo ORACLE: "; where rownum <= -1"
    sql = re.sub(
        r";\s*where\s+rownum\s*<=\s*-?\d+\s*;?",
        ";",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"\bwhere\s+rownum\s*<=\s*-?\d+\s*;?",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    sql = re.sub(
        r"\blimit\s+-1\s*;?",
        "",
        sql,
        flags=re.IGNORECASE,
    )

    sql = sql.strip()

    return rewrite_sql(sql, dbms)
    