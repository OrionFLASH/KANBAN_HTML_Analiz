"""Корень проекта и разрешение относительных путей (не зависит от CWD)."""

from __future__ import annotations

from pathlib import Path


def get_project_root() -> Path:
    """Корень проекта: каталог, где лежат run.py и config.json."""
    return Path(__file__).resolve().parent.parent


def resolve_path(path: str | Path) -> Path:
    """Превращает относительный путь в абсолютный от корня проекта."""
    candidate: Path = Path(path)
    if candidate.is_absolute():
        return candidate
    return get_project_root() / candidate
