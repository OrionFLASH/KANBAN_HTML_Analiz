#!/usr/bin/env python3
"""Сборка архивов Excel v2: программа (полный src без Tests) и docs."""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _skip(path: Path) -> bool:
    """Исключить Tests и кэш байткода."""
    parts = set(path.parts)
    return "__pycache__" in parts or path.suffix == ".pyc" or "Tests" in parts


def _add_tree(zf: zipfile.ZipFile, item: Path) -> None:
    """Добавить файл или дерево в zip с путями от корня репо."""
    if item.is_dir():
        for f in sorted(item.rglob("*")):
            if f.is_file() and not _skip(f):
                zf.write(f, f.relative_to(ROOT).as_posix())
    elif item.is_file():
        zf.write(item, item.relative_to(ROOT).as_posix())
    else:
        raise FileNotFoundError(item)


def pack_program(out: Path) -> int:
    """Архив программы: run_*, config*, весь src/ (без Tests), Docs, README, ROADMAP."""
    roots = [
        ROOT / "src",
        ROOT / "config.json",
        ROOT / "config_excel_v2.json",
        ROOT / "Docs",
        ROOT / "README.md",
        ROOT / "ROADMAP.md",
        ROOT / "run.py",
        ROOT / "run_excel.py",
    ]
    req = ROOT / "requirements.txt"
    if req.is_file():
        roots.append(req)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in roots:
            _add_tree(zf, item)
    names = zipfile.ZipFile(out).namelist()
    if not any(n.endswith("src/filter_funnel.py") for n in names):
        raise RuntimeError("в архиве нет src/filter_funnel.py — нужен весь src/, не только v2")
    if not any(n.startswith("src/v2/") for n in names):
        raise RuntimeError("в архиве нет src/v2/")
    if any("Tests" in n or "__pycache__" in n for n in names):
        raise RuntimeError("в архиве Tests или __pycache__")
    return len(names)


def pack_docs(out: Path) -> int:
    """Архив документации: Docs + README + ROADMAP."""
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in (ROOT / "Docs", ROOT / "README.md", ROOT / "ROADMAP.md"):
            _add_tree(zf, item)
    return len(zipfile.ZipFile(out).namelist())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tag",
        default="20260911b",
        help="суффикс имён zip (например 20260911b)",
    )
    parser.add_argument(
        "--keep-old",
        action="store_true",
        help="не удалять прежние v2_program_files_*.zip / docs_*.zip",
    )
    args = parser.parse_args()
    program = ROOT / f"v2_program_files_{args.tag}.zip"
    docs = ROOT / f"docs_{args.tag}.zip"

    if not args.keep_old:
        for p in ROOT.glob("v2_program_files_*.zip"):
            if p.resolve() != program.resolve():
                p.unlink()
                print("removed", p.name)
        for p in ROOT.glob("docs_*.zip"):
            if p.resolve() != docs.resolve():
                p.unlink()
                print("removed", p.name)

    n_prog = pack_program(program)
    n_docs = pack_docs(docs)
    print(f"wrote {program.name} ({n_prog} files, {program.stat().st_size} bytes)")
    print(f"wrote {docs.name} ({n_docs} files, {docs.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
