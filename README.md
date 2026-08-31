# KANBAN HTML Analiz

Сервис анализа Excel-отчётов Kanban по лидам (ПрПр) и сделкам: сроки нахождения на стадиях, сводная статистика (min/max/перцентили) в разрезе продуктов и ТБ.

## Задача

- Загрузка 22 prod-файлов (11 ТБ × «К ПРОДАЖЕ» / «В РАБОТЕ») или test-файлов из `Docs/FileIN`
- Трекинг каждого `ID ПрПр` по стадиям «Текущий статус» (и опционально «Стадия сделки»)
- Агрегация сроков: min, max, перцентили
- Экспорт в Excel (форматирование) и JSON (для будущего HTML-дашборда)

## Требования

- Python 3.12 или Anaconda (pandas, openpyxl — без pip install)
- Входные файлы: лист `Sheet1`, опционально именованная таблица `Base`

## Запуск

```bash
cd /path/to/KANBAN_HTML_Analiz
python run.py
```

Или с явным config:

```bash
python -m src.main config.json
```

## Структура проекта

```
config.json          # параметры
run.py               # точка запуска
src/                 # исходный код
  main.py            # pipeline
  excel_loader.py    # параллельная загрузка
  lead_tracker.py    # трекинг стадий лидов
  aggregator.py      # min/max/percentiles
  excel_exporter.py  # Excel с форматированием
  json_exporter.py   # JSON для HTML
Docs/FileIN/         # test-данные (в .gitignore)
IN/                  # prod-данные
OUT/                 # результаты с timestamp
log/                 # логи INFO/DEBUG
```

## config.json — основные параметры

| Параметр | Описание | По умолчанию |
|----------|----------|--------------|
| `mode` | `test` или `prod` | `test` |
| `paths.input_test` | Каталог test-файлов | `Docs/FileIN` |
| `paths.input_prod` | Каталог prod-файлов | `IN` |
| `paths.output` | Каталог результатов | `OUT` |
| `test_files` | Список test-файлов | `["2ГОСБ1ТБ.xlsx"]` |
| `prod_files` | Список prod-файлов | 22 имени из ТЗ |
| `sheet_name` | Лист Excel | `Sheet1` |
| `excel_table_name` | Имя таблицы Excel | `Base` |
| `excel_table_auto` | Таблица или весь лист | `true` |
| `duration_source` | `columns` или `dates` | `columns` |
| `stage_analysis_mode` | `status`, `substages`, `both` | `status` |
| `percentiles` | Список перцентилей | `[20, 50, 80]` |
| `parallel_workers` | Число процессов (`0` = CPU count) | `0` |
| `excel_theme` | `green_red` или `minimal` | `green_red` |
| `filters.*.enabled` | Включить фильтр | `false` |

### Фильтры

Каждый фильтр в `filters` имеет `enabled: true/false`. Если включён — в анализ попадают только подходящие строки (AND между включёнными):

- `change_conditions` → `_Изменение условий` = 1
- `data_entry` → `_Ввод данных` = 1
- `efs_flag` → `ЕФС флаг` = 1
- `strategy_label` → `Метка` содержит «Стратегия»

## Выходные файлы

`OUT/kanban_report_YYYYMMDD_HHMMSS.xlsx` — листы:

- **Сводная** — все ТБ
- **Общий** — без разреза ТБ
- **{ТБ}** — отдельный лист на каждый банк

`OUT/kanban_report_YYYYMMDD_HHMMSS.json` — агрегаты + справочники для HTML.

## Перенос на другой ПК (без Git)

Подробно: [Docs/DEPLOY.md](Docs/DEPLOY.md).

**Минимальный архив для почты:** `config.json`, `run.py`, `README.md`, `ROADMAP.md`, каталог `src/`, каталог `Docs/` (без `FileIN/`).

**Отдельно:** Excel-файлы в `Docs/FileIN/` (test) или `IN/` (prod) — не в репозитории.

**На новом ПК:** создать пустые `IN/`, `OUT/`, `log/`, `Docs/FileIN/`, положить xlsx, запустить `python run.py`.

## История версий

| Версия | Дата | Изменения |
|--------|------|-----------|
| 0.1.0 | 2026-08-31 | MVP pipeline: загрузка, трекинг, агрегация, Excel/JSON; test пройден |
