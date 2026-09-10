#!/usr/bin/env python3
"""Генератор полного справочника Docs/CONFIG_EXCEL_V2_PARAMS.md.

Полная логика описаний встроена в историю репозитория / поддерживается вместе с
Docs/CONFIG_EXCEL_V2_PARAMS.md. Перед коммитом всегда запускайте:

    python3 scripts/check_config_excel_v2_params.py

Если check падает (новые ключи в config) — допишите карточки в
Docs/CONFIG_EXCEL_V2_PARAMS.md по шаблону соседних ключей того же блока
(Зачем / Как работает / Что даёт / От чего зависит / Значение в config).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

def main() -> int:
    print("Справочник: Docs/CONFIG_EXCEL_V2_PARAMS.md")
    print("Проверка покрытия ключей config…")
    from check_config_excel_v2_params import main as check_main
    return check_main()

if __name__ == "__main__":
    raise SystemExit(main())
