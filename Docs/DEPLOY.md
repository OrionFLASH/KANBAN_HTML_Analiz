# Перенос проекта на другой ПК (без Git)

**Версия копии POST:** 2.7.0 (2026-09-10)

Инструкция для работы после пересылки по почте или копированием каталога.

## Каталог POST (без zip)

Актуальная копия: **`POST/KANBAN_HTML_Analiz/`**.

**Обновление POST — только по явному запросу** («синхронизируй POST», «обнови POST» и т.п.). При обычных коммитах, пушах и правках кода зеркало **не** пересобирается автоматически.

Содержит **код pipeline** (`run.py`, `run_excel.py`, `src/`) и **документацию только по конфигам**. Архив `.zip` **не** формируется здесь — для Excel v2 см. пакет `v2_program_files_YYYYMMDD.zip` в корне репозитория.

**Не входит в POST:**

- `src/Tests/` — тесты только в Git
- `HTML/` — дашборд не включается
- `ROADMAP.md`, BT/ToDo и прочие не-config Docs
- `.git/`, `log/`, `OUT/`, `IN/`, `Docs/FileIN/`, `POST/`, `__pycache__/`

## Минимальный набор файлов (код + конфиг)

```
KANBAN_HTML_Analiz/
├── config.json
├── config_excel_v2.json          # Excel-only v2
├── run.py                        # HTML+JSON pipeline (без UI в этой копии)
├── run_excel.py                  # Excel v2
├── README.md                     # краткий запуск
├── .env.example
├── .gitignore
├── src/                          # без каталога Tests/
│   ├── v1/
│   ├── v2/
│   ├── filters.py
│   ├── outlier_clipping.py
│   ├── manager_emails.py
│   ├── team_loader.py
│   └── …
└── Docs/
    ├── CONFIG.md                 # справочник config.json
    └── CONFIG_EXCEL_V2.md        # справочник config_excel_v2.json
```

В копиях `config.json` / `config_excel_v2.json` внутри POST стоит **`mode: prod`**.

## Пакет Excel v2 (zip)

В корне репозитория: **`v2_program_files_20260910f.zip`** — код Excel v2, `config_excel_v2.json`, README/ROADMAP, Docs (без `src/Tests/`, без HTML/IN/OUT).

Только документация: **`docs_20260910f.zip`** — папка `Docs/` (включая **CONFIG_EXCEL_V2_PARAMS.md** — каждый ключ config) + `README.md` + `ROADMAP.md`.

Выход `run_excel.py` — **до трёх файлов** (см. `output.report_parts`):

| Файл | Листы |
|------|--------|
| `*_analytics_*.xlsx` | Нормативы, Статистика, матрицы сроков |
| `*_detail_*.xlsx` | Уникальные ID (сроки по статусам), менеджеры, нарушения |
| `*_source_*.xlsx` | Исходные строки Kanban + лидеры/почты (фильтры `output.source_export`) |

`report_parts`: `both` | `analytics` | `detail` | `source` | `full` — см. [CONFIG_EXCEL_V2.md](CONFIG_EXCEL_V2.md).

## Данные Excel (отдельно)

| Режим | Каталог | Файлы |
|-------|---------|-------|
| test | `IN/TEST/` | Kanban + команды из config |
| prod | `IN/PROD/` | 11 Kanban ЕФС + файлы «команда лида и сделки» (`team_files`) + CSV почт (если включён `manager_emails`) |

Перед запуском pipeline проверяет наличие всех файлов для `mode`; при отсутствии — остановка с перечнем недостающих.

## Настройка на новом ПК

1. Python 3.12 + `pandas`, `openpyxl`
2. Скопировать каталог `POST/KANBAN_HTML_Analiz/`
3. Создать пустые: `IN/`, `IN/TEST/`, `IN/PROD/`, `OUT/`, `OUT/excel_v2/`, `log/`
4. Положить xlsx (и CSV почт при необходимости)
5. При необходимости поправить `config.json` / `config_excel_v2.json` — см. [CONFIG.md](CONFIG.md), [CONFIG_EXCEL_V2.md](CONFIG_EXCEL_V2.md)
6. `python run.py` → `OUT/`; `python run_excel.py` → `OUT/excel_v2/`

## Prod-режим

```json
"mode": "prod"
```

При высокой нагрузке:

```json
"parallel_workers": 1,
"performance": { "max_parallel_workers": 2, "reserve_cpu_cores": 2 }
```

## Проверка

```bash
python -c "import pandas, openpyxl; print('OK')"
python run.py
python run_excel.py
```

> `pytest src/Tests/` — только в Git-репозитории разработки; в копии POST каталог `src/Tests/` отсутствует.
