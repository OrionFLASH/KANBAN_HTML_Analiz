"""Проверка наличия входных файлов Kanban и команд перед запуском pipeline."""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any

from src.config_loader import get_file_list, get_input_dir
from src.team_loader import is_team_files_enabled, team_filenames_for_mode

logger: logging.Logger = logging.getLogger("kanban.input_files_check")


class InputFilesMissingError(RuntimeError):
    """Отсутствуют файлы, указанные в config для текущего режима."""

    def __init__(
        self,
        mode: str,
        input_dir: Path,
        missing: list[tuple[str, str]],
    ) -> None:
        self.mode: str = mode
        self.input_dir: Path = input_dir
        self.missing: list[tuple[str, str]] = list(missing)
        lines: list[str] = [
            f"Ошибка: отсутствуют входные файлы (режим: {mode}, каталог: {input_dir}):"
        ]
        for category, name in missing:
            lines.append(f"  [{category}] {name}")
        lines.append("Обработка остановлена. Положите файлы в каталог и повторите запуск.")
        super().__init__("\n".join(lines))


def config_for_team_loader(config: dict[str, Any]) -> dict[str, Any]:
    """Адаптирует config для team_loader (v2: team_files в корне)."""
    if config.get("manager_analytics", {}).get("team_files"):
        return config
    team_files: dict[str, Any] = dict(config.get("team_files") or {})
    if not team_files:
        return config
    merged: dict[str, Any] = deepcopy(config)
    merged.setdefault("manager_analytics", {})["team_files"] = team_files
    return merged


def collect_required_input_files(config: dict[str, Any]) -> list[tuple[str, str]]:
    """
    Список (категория, имя файла) для текущего mode.
    Категории: Kanban, Команда лида, Команда сделки.
    """
    items: list[tuple[str, str]] = []
    for name in get_file_list(config):
        items.append(("Kanban", name))

    team_cfg: dict[str, Any] = config_for_team_loader(config)
    if not is_team_files_enabled(team_cfg):
        return items

    lead_names: list[str] = team_filenames_for_mode(team_cfg, "lead_team")
    deal_names: list[str] = team_filenames_for_mode(team_cfg, "deal_team")
    for name in lead_names:
        items.append(("Команда лида", name))
    for name in deal_names:
        items.append(("Команда сделки", name))
    return items


def find_missing_input_files(config: dict[str, Any]) -> list[tuple[str, str]]:
    """Возвращает отсутствующие файлы: (категория, имя)."""
    input_dir: Path = get_input_dir(config)
    missing: list[tuple[str, str]] = []
    for category, name in collect_required_input_files(config):
        path: Path = input_dir / name
        if not path.is_file():
            missing.append((category, name))
    return missing


def ensure_input_files_exist(config: dict[str, Any], log: logging.Logger | None = None) -> None:
    """
    Проверяет наличие всех входных файлов для mode test/prod.
    При отсутствии — лог и InputFilesMissingError.
    """
    mode: str = str(config.get("mode", "test"))
    input_dir: Path = get_input_dir(config)
    file_list: list[str] = get_file_list(config)

    if not file_list:
        raise ValueError(f"Для режима '{mode}' список файлов Kanban пуст (test_files / prod_files)")

    missing: list[tuple[str, str]] = find_missing_input_files(config)
    if not missing:
        active_log: logging.Logger = log or logger
        active_log.info(
            "Входные файлы найдены: режим=%s, каталог=%s, Kanban=%d",
            mode,
            input_dir,
            len(file_list),
        )
        return

    err: InputFilesMissingError = InputFilesMissingError(mode, input_dir, missing)
    active_log = log or logger
    for category, name in missing:
        active_log.error("Файл не найден [%s]: %s", category, input_dir / name)
    active_log.error(str(err))
    raise err
