"""Запуск Excel-only pipeline v2 (отдельно от run.py / HTML+JSON)."""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.v2.pipeline import run_excel_pipeline

if __name__ == "__main__":
    run_excel_pipeline()
