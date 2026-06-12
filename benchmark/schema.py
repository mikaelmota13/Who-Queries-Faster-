from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # int, decimal, date, char, varchar
    length: int | None = None


@dataclass(frozen=True)
class Table:
    name: str
    columns: tuple[Column, ...]
    pk: tuple[str, ...]


TABLES: tuple[Table, ...] = (
    Table("region", (
        Column("r_regionkey", "int"),
        Column("r_name", "char", 25),
        Column("r_comment", "varchar", 152),
    ), ("r_regionkey",)),
    Table("nation", (
        Column("n_nationkey", "int"),
        Column("n_name", "char", 25),
        Column("n_regionkey", "int"),
        Column("n_comment", "varchar", 152),
    ), ("n_nationkey",)),
    Table("supplier", (
        Column("s_suppkey", "int"),
        Column("s_name", "char", 25),
        Column("s_address", "varchar", 40),
        Column("s_nationkey", "int"),
        Column("s_phone", "char", 15),
        Column("s_acctbal", "decimal"),
        Column("s_comment", "varchar", 101),
    ), ("s_suppkey",)),
    Table("customer", (
        Column("c_custkey", "int"),
        Column("c_name", "varchar", 25),
        Column("c_address", "varchar", 40),
        Column("c_nationkey", "int"),
        Column("c_phone", "char", 15),
        Column("c_acctbal", "decimal"),
        Column("c_mktsegment", "char", 10),
        Column("c_comment", "varchar", 117),
    ), ("c_custkey",)),
    Table("part", (
        Column("p_partkey", "int"),
        Column("p_name", "varchar", 55),
        Column("p_mfgr", "char", 25),
        Column("p_brand", "char", 10),
        Column("p_type", "varchar", 25),
        Column("p_size", "int"),
        Column("p_container", "char", 10),
        Column("p_retailprice", "decimal"),
        Column("p_comment", "varchar", 23),
    ), ("p_partkey",)),
    Table("partsupp", (
        Column("ps_partkey", "int"),
        Column("ps_suppkey", "int"),
        Column("ps_availqty", "int"),
        Column("ps_supplycost", "decimal"),
        Column("ps_comment", "varchar", 199),
    ), ("ps_partkey", "ps_suppkey")),
    Table("orders", (
        Column("o_orderkey", "int"),
        Column("o_custkey", "int"),
        Column("o_orderstatus", "char", 1),
        Column("o_totalprice", "decimal"),
        Column("o_orderdate", "date"),
        Column("o_orderpriority", "char", 15),
        Column("o_clerk", "char", 15),
        Column("o_shippriority", "int"),
        Column("o_comment", "varchar", 79),
    ), ("o_orderkey",)),
    Table("lineitem", (
        Column("l_orderkey", "int"),
        Column("l_partkey", "int"),
        Column("l_suppkey", "int"),
        Column("l_linenumber", "int"),
        Column("l_quantity", "decimal"),
        Column("l_extendedprice", "decimal"),
        Column("l_discount", "decimal"),
        Column("l_tax", "decimal"),
        Column("l_returnflag", "char", 1),
        Column("l_linestatus", "char", 1),
        Column("l_shipdate", "date"),
        Column("l_commitdate", "date"),
        Column("l_receiptdate", "date"),
        Column("l_shipinstruct", "char", 25),
        Column("l_shipmode", "char", 10),
        Column("l_comment", "varchar", 44),
    ), ("l_orderkey", "l_linenumber")),
)

TABLE_BY_NAME = {t.name: t for t in TABLES}
LOAD_ORDER = [t.name for t in TABLES]
DROP_ORDER = list(reversed(LOAD_ORDER))


def type_sql(col: Column, dbms: str) -> str:
    if col.kind == "int":
        return "NUMBER(10)" if dbms == "oracle" else "INT"
    if col.kind == "decimal":
        return "NUMBER(15,2)" if dbms == "oracle" else "DECIMAL(15,2)"
    if col.kind == "date":
        return "DATE"
    if col.kind == "char":
        return f"CHAR({col.length})"
    if col.kind == "varchar":
        return f"VARCHAR2({col.length})" if dbms == "oracle" else f"VARCHAR({col.length})"
    raise ValueError(f"Tipo não suportado: {col.kind}")


def drop_table_sql(table: str, dbms: str) -> str:
    if dbms == "oracle":
        return f"BEGIN EXECUTE IMMEDIATE 'DROP TABLE {table} CASCADE CONSTRAINTS PURGE'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -942 THEN RAISE; END IF; END;"
    return f"DROP TABLE IF EXISTS {table}"


def create_table_sql(table: Table, dbms: str) -> str:
    pk_cols = set(table.pk)

    cols = ",\n  ".join(
        f"{c.name} {type_sql(c, dbms)} {'NOT NULL' if c.name in pk_cols else ''}".strip()
        for c in table.columns
    )

    return f"CREATE TABLE {table.name} (\n  {cols}\n)"


def pk_sql(table: Table, dbms: str) -> str:
    cols = ", ".join(table.pk)
    return f"ALTER TABLE {table.name} ADD CONSTRAINT pk_{table.name} PRIMARY KEY ({cols})"


EXTRA_INDEXES = {
    "nation": ["n_regionkey"],
    "supplier": ["s_nationkey"],
    "customer": ["c_nationkey"],
    "partsupp": ["ps_suppkey"],
    "orders": ["o_custkey", "o_orderdate"],
    "lineitem": ["l_partkey", "l_suppkey", "l_shipdate", "l_commitdate", "l_receiptdate"],
}


def index_sql(table: str, col: str, dbms: str) -> str:
    return f"CREATE INDEX idx_{table}_{col} ON {table} ({col})"
