"""Чтение JSON-конфигов с понятным контекстом при синтаксической ошибке."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json_file(path: Path) -> dict[str, Any]:
    """
    Читает JSON-объект из файла UTF-8.
    При JSONDecodeError показывает фрагмент вокруг проблемной строки.
    """
    text: str = path.read_text(encoding="utf-8-sig")
    try:
        raw: Any = json.loads(text)
    except json.JSONDecodeError as err:
        raise json.JSONDecodeError(
            _format_json_error(path, text, err),
            err.doc,
            err.pos,
        ) from None
    if not isinstance(raw, dict):
        raise ValueError(f"Корень JSON должен быть объектом {{...}}: {path}")
    return raw


def _format_json_error(path: Path, text: str, err: json.JSONDecodeError) -> str:
    """Сообщение с номером строки и соседним контекстом."""
    lines: list[str] = text.splitlines()
    lineno: int = max(1, int(err.lineno))
    col: int = max(1, int(err.colno))
    start: int = max(0, lineno - 4)
    end: int = min(len(lines), lineno + 3)
    context_lines: list[str] = []
    for idx in range(start, end):
        mark: str = ">>" if idx + 1 == lineno else "  "
        context_lines.append(f"{mark} {idx + 1}: {lines[idx]}")
    pointer: str = " " * (col + 5) + "^"
    context_lines.append(pointer)
    hint: str = (
        "Частые причины: пропущена запятая «,» между элементами, "
        "лишняя запятая перед } или ], незакрытая кавычка."
    )
    return (
        f"Ошибка JSON в {path} (строка {lineno}, колонка {col}): {err.msg}\n"
        + "\n".join(context_lines)
        + f"\n{hint}"
    )
