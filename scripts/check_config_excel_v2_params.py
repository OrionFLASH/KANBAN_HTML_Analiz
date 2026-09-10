#!/usr/bin/env python3
"""Проверка: у каждого пути config_excel_v2.json есть карточка в CONFIG_EXCEL_V2_PARAMS.md."""

from __future__ import annotations

import json
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
    print(f"config_paths={len(paths)} cards_in_md={md.count('### `')} missing={len(missing)}")
    if missing:
        for path in missing[:50]:
            print(f"MISSING {path}")
        return 1
    print("OK: 100% coverage")
    return 0


if __name__ == "__main__":
    sys.exit(main())
