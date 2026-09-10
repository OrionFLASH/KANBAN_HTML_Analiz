#!/usr/bin/env python3
"""Проверка: у каждого пути config_excel_v2.json есть карточка с вариантами значений."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT: Path = Path(__file__).resolve().parents[1]
CONFIG: Path = ROOT / "config_excel_v2.json"
PARAMS: Path = ROOT / "Docs" / "CONFIG_EXCEL_V2_PARAMS.md"


def walk(obj: Any, prefix: str = "") -> list[str]:
    rows: list[str] = []
    if isinstance(obj, dict):
        for key, val in obj.items():
            path: str = f"{prefix}.{key}" if prefix else key
            if isinstance(val, dict):
                rows.append(path)
                rows.extend(walk(val, path))
            elif isinstance(val, list):
                rows.append(path)
                if val and isinstance(val[0], dict):
                    for idx, item in enumerate(val):
                        ip: str = f"{path}[{idx}]"
                        rows.append(ip)
                        rows.extend(walk(item, ip))
            else:
                rows.append(path)
    return rows


def main() -> int:
    cfg: dict[str, Any] = json.loads(CONFIG.read_text(encoding="utf-8"))
    md: str = PARAMS.read_text(encoding="utf-8")
    paths: list[str] = walk(cfg)
    missing: list[str] = [p for p in paths if f"### `{p}`" not in md]
    cards: int = md.count("### `")
    variants: int = md.count("**Допустимые значения / варианты**")
    print(
        f"config_paths={len(paths)} cards_in_md={cards} "
        f"variant_rows={variants} missing={len(missing)}"
    )
    if missing:
        for path in missing[:50]:
            print(f"MISSING {path}")
        return 1
    if cards != variants:
        print("FAIL: не у всех карточек есть строка допустимых значений")
        return 1
    mode_card = re.search(r"### `mode`[\s\S]*?(?=### `|\Z)", md)
    if not mode_card or "`test`" not in mode_card.group(0) or "`prod`" not in mode_card.group(0):
        print("FAIL: карточка mode должна описывать варианты test/prod")
        return 1
    print("OK: 100% coverage + variants")
    return 0


if __name__ == "__main__":
    sys.exit(main())
