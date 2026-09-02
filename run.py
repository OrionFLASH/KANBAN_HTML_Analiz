"""Запуск анализа из корня проекта."""

import sys
from pathlib import Path

# Корень проекта в sys.path при запуске run.py из IDE с любым CWD
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.v1.main import run

if __name__ == "__main__":
    run()
