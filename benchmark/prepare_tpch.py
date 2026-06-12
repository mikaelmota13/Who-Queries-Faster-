from __future__ import annotations

import csv
from pathlib import Path

from tqdm import tqdm

from .config import settings
from .schema import LOAD_ORDER


def clean_tbl(src: Path, dst: Path) -> int:
    n = 0
    with src.open("r", encoding="utf-8", errors="replace") as fin, dst.open("w", encoding="utf-8", newline="") as fout:
        for line in fin:
            line = line.rstrip("\n")
            if line.endswith("|"):
                line = line[:-1]
            fout.write(line + "\n")
            n += 1
    return n


def main() -> None:
    settings.clean_dir.mkdir(parents=True, exist_ok=True)
    counts: list[tuple[str, int]] = []

    for table in tqdm(LOAD_ORDER, desc="Limpando .tbl"):
        src = settings.raw_dir / f"{table}.tbl"
        dst = settings.clean_dir / f"{table}.tbl"
        if not src.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {src}. Rode: make tpch")
        counts.append((table, clean_tbl(src, dst)))

    with (settings.clean_dir / "row_counts.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["table", "rows"])
        writer.writerows(counts)

    print("Arquivos limpos gerados em data/tpch_clean/")
    for table, rows in counts:
        print(f"{table}: {rows}")


if __name__ == "__main__":
    main()
