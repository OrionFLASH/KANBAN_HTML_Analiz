# Перенос проекта на другой ПК (без Git)

Инструкция для работы после пересылки по почте или архивом.

## Архив для почты

Готовый zip: **`POST/KANBAN_HTML_Analiz.zip`** (обновляется при релизах).

## Минимальный набор файлов (код + конфиг)

```
KANBAN_HTML_Analiz/
├── config.json
├── run.py
├── README.md
├── ROADMAP.md
├── .env.example
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config_loader.py
│   ├── settings.py
│   ├── project_paths.py
│   ├── logger_setup.py
│   ├── excel_loader.py
│   ├── dictionaries.py
│   ├── lead_tracker.py
│   ├── filters.py
│   ├── aggregator.py
│   ├── excel_exporter.py
│   ├── json_exporter.py
│   ├── data_audit.py
│   ├── date_utils.py
│   ├── performance.py
│   ├── progress.py
│   └── Tests/
│       └── test_excel_loader.py
└── Docs/
    ├── CONFIG.md         # справочник config.json
    ├── BT_KANBAN.md
    ├── DEPLOY.md
    └── ToDo KANBAN.txt
```

**Не включать:** `.git/`, `log/`, `OUT/`, `IN/`, `Docs/FileIN/`, `POST/`, `__pycache__/`

## Данные Excel (отдельно)

| Режим | Каталог | Файлы |
|-------|---------|-------|
| test | `Docs/FileIN/` | `2ГОСБ1ТБ.xlsx` |
| prod | `IN/` | 22 файла из `config.json` → `prod_files` |

## Настройка на новом ПК

1. Python 3.12 / Anaconda + `pandas`, `openpyxl`
2. Распаковать архив
3. Создать пустые: `IN/`, `OUT/`, `log/`, `Docs/FileIN/`
4. Положить xlsx
5. Настроить `config.json` — см. [CONFIG.md](CONFIG.md)
6. `python run.py`

## Prod-режим

```json
"mode": "prod"
```

22 xlsx в `IN/`, при необходимости снизить нагрузку:

```json
"parallel_workers": 1,
"performance": { "max_parallel_workers": 2, "reserve_cpu_cores": 2 }
```

## Проверка

```bash
python -c "import pandas, openpyxl; print('OK')"
python -m unittest src.Tests.test_excel_loader -v
python run.py
```
