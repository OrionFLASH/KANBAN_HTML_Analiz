"""Тесты загрузки Excel."""

from __future__ import annotations

import unittest
from pathlib import Path

from src.config_loader import load_config
from src.excel_loader import load_all_files, read_single_file


class TestExcelLoader(unittest.TestCase):
    """Проверка чтения test-файла."""

    def test_read_single_file(self) -> None:
        config = load_config("config.json")
        path = Path(config["paths"]["input_test"]) / config["test_files"][0]
        df = read_single_file((str(path), config))
        self.assertGreater(len(df), 0)
        self.assertIn("ID ПрПр", df.columns)
        self.assertIn("Текущий статус", df.columns)

    def test_load_all_test_files(self) -> None:
        config = load_config("config.json")
        input_dir = Path(config["paths"]["input_test"])
        files = list(config["test_files"])
        config["parallel_workers"] = 1
        df = load_all_files(config, input_dir, files)
        self.assertEqual(len(df["source_file"].unique()), 1)


if __name__ == "__main__":
    unittest.main()
