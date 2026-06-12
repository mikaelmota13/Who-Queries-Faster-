#!/usr/bin/env bash
set -euo pipefail

SF="${TPCH_SCALE_FACTOR:-1}"
DBGEN_REPO="${DBGEN_REPO:-https://github.com/electrum/tpch-dbgen.git}"
DBGEN_DIR="/work/tools/tpch-dbgen"
RAW_DIR="/work/data/tpch_raw"
QUERY_DIR="/work/queries"

mkdir -p /work/tools "$RAW_DIR" "$QUERY_DIR"

if [ ! -d "$DBGEN_DIR/.git" ]; then
  git clone "$DBGEN_REPO" "$DBGEN_DIR"
fi

cd "$DBGEN_DIR"
make clean >/dev/null 2>&1 || true
make MACHINE=LINUX DATABASE=ORACLE

# dbgen/qgen precisam enxergar ./dists.dss; por isso executam dentro de DBGEN_DIR.
rm -f ./*.tbl
./dbgen -vf -s "$SF"
cp ./*.tbl "$RAW_DIR"/

for i in $(seq 1 22); do
  DSS_QUERY="$DBGEN_DIR/queries" ./qgen -s "$SF" "$i" > "$QUERY_DIR/q${i}.sql"
done

echo "TPC-H SF=$SF gerado em data/tpch_raw e queries/."
