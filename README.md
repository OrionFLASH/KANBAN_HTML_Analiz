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

## config.json — структура настроек

Все параметры задаются в `config.json`. Отсутствующие ключи дополняются значениями по умолчанию из `src/settings.py`.

### Режим и пути (`paths`)

| Ключ | Описание |
|------|----------|
| `mode` | `test` или `prod` |
| `paths.input_test` | Каталог test-файлов |
| `paths.input_prod` | Каталог prod-файлов |
| `paths.output` | Каталог результатов |
| `paths.log` | Каталог логов |
| `test_files` / `prod_files` | Списки имён xlsx |

### Колонки Excel (`columns`)

Имена колонок в исходных файлах — **ключ → имя в Excel**:

| Ключ | По умолчанию |
|------|--------------|
| `report_date` | Дата отчета |
| `lead_id` | ID ПрПр |
| `product_group` | Группа продукта |
| `product` | Продукт |
| `work_start_date` | Дата начала работы |
| `current_status` | Текущий статус |
| `days_on_stage` | Количество дней на текущей стадии |
| `deal_created_date` | Дата создания сделки |
| `deal_stage` | Стадия сделки |
| `days_since_deal` | Количество дней с создания сделки |
| `tb` | ТБ |
| `label` | Метка |
| `change_conditions` | _Изменение условий |
| `data_entry` | _Ввод данных |
| `efs_flag` | ЕФС флаг |

`required_column_keys` — какие ключи обязательны при загрузке.

### Excel (`excel`)

| Ключ | Описание |
|------|----------|
| `sheet_name` | Лист |
| `table_name` | Именованная таблица (например `Base`) |
| `table_auto` | Сначала таблица, иначе весь лист |
| `engine` | Движок pandas (`openpyxl`) |
| `na_values` | Пустые значения |
| `category_markers` | Маркеры «К ПРОДАЖЕ» / «В РАБОТЕ» в имени файла |

### Обработка (`processing`)

| Ключ | Описание |
|------|----------|
| `empty_stage_values` | Значения пустой подстадии (`-`, `""`, …) |
| `dedup_same_date_agg` | Агрегация на одну дату (`max`) |
| `pick_across_dates` | Правило выбора между датами отчёта |

### Анализ

| Ключ | Описание |
|------|----------|
| `duration_source` | `columns` или `dates` |
| `stage_analysis_mode` | `status`, `substages`, `both` |
| `percentiles` | Список перцентилей, напр. `[20, 50, 80]` |
| `parallel_workers` | Процессы (`0` = число CPU) |
| `aggregation.group_keys` | Ключи группировки статистики |
| `aggregation.metrics` | Метрики: `days_on_stage`, `days_since_deal` |

### Выход (`output`)

| Ключ | Описание |
|------|----------|
| `report_prefix` | Префикс файлов (`kanban_report`) |
| `timestamp_format` | Формат timestamp в имени |
| `excel_sheets.summary` / `overall` | Имена листов Excel |
| `column_labels` | Заголовки колонок в Excel |
| `excel_format` | Freeze, ширина, цвета min/max |

### Фильтры (`filters`)

Каждый фильтр: `enabled`, `column_key` (ссылка на `columns`), `value` или `contains`:

- `change_conditions`, `data_entry`, `efs_flag`, `strategy_label`

### Логирование (`logging`)

| Ключ | Описание |
|------|----------|
| `logger_name` | Имя логгера |
| `info_file_prefix` / `debug_file_prefix` | Префиксы файлов логов |
| `hour_format` | Формат часа в имени лога |

### Прочее

| Ключ | Описание |
|------|----------|
| `excel_theme` | `green_red` или `minimal` |

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
| 0.2.0 | 2026-08-31 | Все пути, колонки и форматы вынесены в config.json |
