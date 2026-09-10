# ROADMAP: KANBAN HTML Analiz

**Старт:** 2026-08-31  
**Статус проекта:** Разработка (MVP готов, test пройден)

---

## Согласованные решения (v1.1)

| Тема | Решение |
|------|---------|
| Расчёт сроков | Оба метода в коде; `duration_source`: `columns` / `dates` |
| Подстадии | `stage_analysis_mode`: `status` / `substages` / `both` |
| Фильтры | Каждый вкл/выкл в config; AND; только подходящие строки |
| Excel-лист | `Sheet1`, первая строка — заголовок; без именованных таблиц; openpyxl `read_only` |
| JSON | Только агрегаты |
| Категория файла | Объединять (не влияет на аналитику) |
| Дубли / срок лида | Max дней на стадии; при равенстве — max `Дата отчета` |
| Перцентили | Настраиваемый список, default `[20, 50, 80]` |
| Workers | `os.cpu_count()` (parallel_workers=0) |
| Excel | green_red + autofilter + freeze + ширина + формат чисел |

## Легенда статусов

| Статус | Значение |
|--------|----------|
| `[v]` | Сделано |
| `[w]` | В работе |
| `[ ]` | Не сделано |
| `[x]` | Отменено |

---

## Фаза 0 — Анализ и согласование

| # | Задача | Статус |
|---|--------|--------|
| 0.1 | Разбор `Docs/ToDo KANBAN.txt` | `[v]` |
| 0.2 | Формирование БТ `Docs/BT_KANBAN.md` | `[v]` |
| 0.3 | Создание ROADMAP | `[v]` |
| 0.4 | **Уточняющие вопросы — ответы пользователя** | `[v]` |
| 0.5 | Исследование test-файла `2ГОСБ1ТБ.xlsx` (колонки, объём, типы) | `[v]` |
| 0.6 | Фиксация решений по открытым вопросам в BT v1.1 | `[v]` |

---

## Фаза 1 — Инфраструктура проекта

| # | Задача | Модули / файлы | Статус |
|---|--------|----------------|--------|
| 1.1 | Структура каталогов: `src/`, `src/Tests/`, `log/`, `IN/`, `OUT/` | — | `[v]` |
| 1.2 | `config.json` + описание в README | `config.json` | `[v]` |
| 1.3 | `.env.example`, обновление `.gitignore` | `.gitignore` | `[v]` |
| 1.4 | `logger_setup.py` — INFO/DEBUG в `log/` | `src/logger_setup.py` | `[v]` |
| 1.5 | `config_loader.py` — загрузка и валидация config | `src/config_loader.py` | `[v]` |
| 1.6 | `main.py` — скелет pipeline | `src/main.py` | `[v]` |
| 1.7 | `README.md` — описание, запуск, config | `README.md` | `[v]` |
| 1.8 | Виртуальное окружение / проверка Anaconda-зависимостей | — | `[v]` |

---

## Фаза 2 — Загрузка данных

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 2.1 | Константа `REQUIRED_COLUMNS` — список колонок из BT | `src/excel_loader.py` | `[v]` |
| 2.2 | Функция `read_single_file(path) → DataFrame` | `src/excel_loader.py` | `[v]` |
| 2.3 | Параллельная загрузка `load_all_files(config) → DataFrame` | `src/excel_loader.py` | `[v]` |
| 2.4 | Валидация schema (наличие колонок, типы) | `src/excel_loader.py` | `[v]` |
| 2.5 | Служебные поля: `source_file`, `source_category` | `src/excel_loader.py` | `[v]` |
| 2.6 | Тест: загрузка `2ГОСБ1ТБ.xlsx` | `src/Tests/test_excel_loader.py` | `[v]` |

---

## Фаза 3 — Справочники

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 3.1 | `extract_tb_list(df) → list[str]` | `src/dictionaries.py` | `[v]` |
| 3.2 | `extract_stages(df) → dict[status, set[deal_stage]]` | `src/dictionaries.py` | `[v]` |
| 3.3 | `extract_products(df) → list[{group, product}]` | `src/dictionaries.py` | `[v]` |
| 3.4 | Логирование counts справочников | `src/dictionaries.py` | `[v]` |
| 3.5 | Тест справочников на test-файле | `src/Tests/test_dictionaries.py` | `[ ]` |

---

## Фаза 4 — Трекинг лидов

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 4.1 | Алгоритм: группировка по `ID ПрПр` + стадия | `src/lead_tracker.py` | `[v]` |
| 4.2 | Правило выбора строки при нескольких `Дата отчета` (latest date) | `src/lead_tracker.py` | `[v]` |
| 4.3 | Извлечение `days_on_stage`, `days_since_deal` | `src/lead_tracker.py` | `[v]` |
| 4.4 | Опционально: расчёт дней по датам (`duration_source=dates`) | `src/lead_tracker.py` | `[v]` |
| 4.5 | DataFrame `lead_stage_records` — одна строка = лид × стадия | `src/lead_tracker.py` | `[v]` |
| 4.6 | Тест трекинга на синтетических + real data | `src/Tests/test_lead_tracker.py` | `[ ]` |

---

## Фаза 5 — Фильтрация

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 5.1 | `apply_filters(df, config) → df` | `src/filters.py` | `[v]` |
| 5.2 | Бинарные фильтры: `_Изменение условий`, `_Ввод данных`, `ЕФС флаг` | `src/filters.py` | `[v]` |
| 5.3 | Текстовый фильтр `Метка` contains «Стратегия» | `src/filters.py` | `[v]` |
| 5.4 | Тест фильтров | `src/Tests/test_filters.py` | `[ ]` |

---

## Фаза 6 — Агрегация статистики

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 6.1 | `aggregate_statistics(records, group_cols, percentiles)` | `src/aggregator.py` | `[v]` |
| 6.2 | Группировка: общая (без ТБ) | `src/aggregator.py` | `[v]` |
| 6.3 | Группировка: по ТБ | `src/aggregator.py` | `[v]` |
| 6.4 | Метрики: min, max, count + для каждого P: дней, лидов, min, max | `src/percentile_stats.py`, `src/aggregator.py` | `[v]` |
| 6.5 | Отдельная агрегация для `days_since_deal` | `src/aggregator.py` | `[v]` |
| 6.6 | Тест агрегации | `src/Tests/test_aggregator.py` | `[ ]` |

---

## Фаза 7 — Экспорт Excel

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 7.1 | `export_excel(stats, output_path, config)` | `src/excel_exporter.py` | `[v]` |
| 7.2 | Лист «Сводная» — все ТБ | `src/excel_exporter.py` | `[v]` |
| 7.3 | Лист «Общий» — без ТБ | `src/excel_exporter.py` | `[v]` |
| 7.4 | Листы `{ТБ}` — по одному на банк | `src/excel_exporter.py` | `[v]` |
| 7.5 | Условная раскраска min/max/percentiles | `src/excel_exporter.py` | `[v]` |
| 7.6 | Timestamp в имени файла | `src/excel_exporter.py` | `[v]` |

---

## Фаза 8 — Экспорт JSON

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 8.1 | `export_json(stats, dimensions, meta, output_path)` | `src/json_exporter.py` | `[v]` |
| 8.2 | Schema: dimensions + statistics (без lead_tracks) | `src/json_exporter.py` | `[v]` |
| 8.3 | Timestamp в имени файла | `src/json_exporter.py` | `[v]` |

---

## Фаза 9 — Интеграция и prod

| # | Задача | Статус |
|---|--------|--------|
| 9.1 | Полный pipeline test-режим end-to-end | `[v]` |
| 9.2 | Prod-режим: 22 файла, parallel workers | `[ ]` |
| 9.3 | Профилирование памяти / времени на test | `[ ]` |
| 9.4 | Документация CLI в `Docs/` | `[v]` |
| 9.5 | Финальный прогон и приёмка по критериям BT §10 | `[ ]` |

---

## Фаза 10 — HTML-дашборд

| # | Задача | Модули | Статус |
|---|--------|--------|--------|
| 10.1 | HTML-страница с загрузкой JSON | `HTML/` | `[v]` |
| 10.2 | Графики распределения (гистограмма, ECDF, ранговая шкала, разворот) | `HTML/js/charts.js`, `distribution.js`, `chart-expand.js` | `[v]` |
| 10.3 | Сводная матрица продукт × стадия | `HTML/js/pivot.js` | `[v]` |
| 10.4 | Блок `visualizations` в JSON | `src/visualization_data.py` | `[v]` |
| 10.5 | Excel: лист «Графики» (без «Матрицы») | `src/pivot_excel.py` | `[v]` |
| 10.6 | Менеджеры: hotspots + детальная карточка КМ в HTML | `manager_analytics.py`, `managers.js` | `[v]` |
| 10.7 | Отбор TOP КМ: `rank_selection`, полные `records`, пересчёт в UI | `manager_analytics.py`, `managers.js`, config | `[v]` |
| 10.8 | Уменьшение JSON: config-only фильтры, убрать дубли viz, меню сжатия | `filter_slices`, `json_exporter`, UI | `[w]` |
| 10.9 | Опционально исключить стадию «К ПРОДАЖЕ» из анализа (config-only) | `filters`, `visualization_data`, UI | `[v]` |
| 10.10 | Команда лида/сделки: лидеры + КМ + ВКС → TOP-3 по ТБ, Excel/UI | `team_loader`, `manager_analytics`, UI | `[v]` |
| 10.11 | **Разворот графика:** после «Свернуть» — сброс inline-размеров Chart.js, reflow layout | `chart-expand.js`, `dashboard.css` | `[v]` |

---

## Декомпозиция модулей

```
src/
├── main.py                 # точка входа, оркестрация
├── config_loader.py        # config.json
├── logger_setup.py         # логирование
├── excel_loader.py         # параллельное чтение xlsx
├── dictionaries.py         # справочники
├── lead_tracker.py         # стадии по ID ПрПр
├── filters.py              # фильтры config
├── aggregator.py           # min/max/percentiles
├── excel_exporter.py       # форматированный xlsx
├── json_exporter.py        # JSON для HTML
└── Tests/
    ├── test_excel_loader.py
    ├── test_dictionaries.py
    ├── test_lead_tracker.py
    ├── test_filters.py
    └── test_aggregator.py
```

---

## Зависимости между фазами

```
Фаза 0 ──► Фаза 1 ──► Фаза 2 ──► Фаза 3
                              │
                              ▼
                         Фаза 4 ──► Фаза 5 ──► Фаза 6
                                              │
                                    ┌─────────┴─────────┐
                                    ▼                   ▼
                               Фаза 7              Фаза 8
                                    │                   │
                                    └─────────┬─────────┘
                                              ▼
                                         Фаза 9 ──► Фаза 10
```

---

## Уточняющие вопросы

**Закрыты 2026-08-31.** Решения зафиксированы в §«Согласованные решения (v1.1)» и `Docs/BT_KANBAN.md` §12.

---

## Фаза 11 — Excel-only pipeline v2 (`Docs/ToDo KANBAN v2.txt`)

| # | Задача | Модули / файлы | Статус |
|---|--------|----------------|--------|
| 11.1 | ROADMAP и `config_excel_v2.json` | `config_excel_v2.json` | `[v]` |
| 11.2 | Отдельный launcher `run_excel.py` (без JSON/HTML) | `run_excel.py` | `[v]` |
| 11.3 | Каталоги `IN/TEST`, `IN/PROD` | `IN/` | `[v]` |
| 11.4 | Пакет `src/v2/` (ранее `excel_report/`) | `config_loader`, `snapshot`, `team_enrich`, `norms`, `exceedance`, `manager_summary`, `exporter`, `pipeline` | `[v]` |
| 11.5 | Фильтры v2 (ЕФС, стратегия, терминальные стадии) | `config_excel_v2.json`, `filters.py` (reuse) | `[v]` |
| 11.6 | Снимок уникальных ID + fill-forward по дате | `snapshot.py` | `[v]` |
| 11.7 | Лидеры команд (TN, многострочные ячейки) | `team_enrich.py` | `[v]` |
| 11.8 | Нормативы P20/P50/P80 по ТБ и «все тб» | `norms.py` | `[v]` |
| 11.9 | Превышение P80 на строку лида | `exceedance.py` | `[v]` |
| 11.10 | Листы: нормативы, уникальные ID, свод менеджер, свод ПрПр | `exporter.py` | `[v]` |
| 11.11 | Сокращение «Клиент» (+ СЗ в config) | `client_names.py` (reuse) | `[v]` |
| 11.12 | Тесты snapshot / pipeline | `src/Tests/test_excel_report.py` | `[v]` |
| 11.13 | Разделение `src` на `v1/` / `v2/` / общие модули | `src/v1/`, `src/v2/` | `[v]` |
| 11.14 | Универсальные фильтры (action/match/values/value_type) | `filters.py`, `config_excel_v2.json` | `[v]` |
| 11.15 | Отсечение выбросов срока дней перед нормативами | `outlier_clipping.py`, `aggregator.py`, config | `[v]` |
| 11.16 | На листе «Нормативы»: воронка фильтров + свод/колонки выбросов | `filter_funnel.py`, `exporter.py`, `pipeline.py` | `[v]` |
| 11.17 | Порог превышения v2 из config (`exceedance.percentile`) | `norms.py`, `exceedance.py`, `config_excel_v2.json` | `[v]` |
| 11.18 | На «Нормативы»: до/после и отсечено по каждому вх. фильтру (по строке группы) | `filter_funnel.py`, `pipeline.py`, `statistics_config.py` | `[v]` |
| 11.19 | Режим отсечения `unique_days_trim` (процент уникальных сроков слева/справа) | `outlier_clipping.py`, `config_excel_v2.json` | `[v]` |
| 11.20 | Adaptive resources: лимиты workers/флаги из config; low-RAM 16 ГБ → 2 workers | `resource_guard.py`, configs | `[v]` |
| 11.21 | Лист матрицы: группа/продукт × дни (число лидов), градиент, freeze D2 | `duration_matrix.py`, `exporter.py` | `[v]` |
| 11.22 | Почты Альфа/Сигма по ТН лидеров из CSV в `IN/` | `manager_emails.py`, config | `[v]` |
| 11.23 | Закрепление областей по листам: `sheet_freeze.last_row/last_col` | `excel_format.py`, config | `[v]` |
| 11.24 | Fix `clip_group_frame`: маска выбросов с индексом группы (IndexingError) | `outlier_clipping.py` | `[v]` |
| 11.25 | Fix подливки лидера сделки: join по ключу снимка `deal_id` (+ все лидеры на max дате) | `team_enrich.py` | `[v]` |
| 11.26 | Отбор лидера: max дата отчёта → max «Дата добавления в команду»; равные → `\n` | `team_enrich.py`, `team_loader.py` | `[v]` |
| 11.27 | Снимок: единообразные ключи config (`lead_id` как `deal_id`) | `snapshot.py`, `manager_summary.py` | `[v]` |
| 11.28 | Даты в Excel как дата, формат `DD.MM.YYYY` | `excel_format.py`, `excel_sanitize.py` | `[v]` |
| 11.29 | Матрица сроков: P20/P50/P80 по группе+продукту (все стадии), выделение порога, пунктир | `duration_matrix.py`, `exporter.py` | `[v]` |
| 11.30 | Чтение Excel: убрать Base/table_auto, openpyxl `read_only=true` | `excel_loader.py`, `team_loader.py` | `[v]` |
| 11.31 | Архив программы v2: `v2_program_files_20260904.zip` (код+config+docs, read_only) | корень репо | `[v]` |
| 11.32 | Единые файлы «команда лида и сделки» + колонка «Тип команды» (1/2/-) | `team_loader`, configs, docs | `[v]` |
| 11.33 | Архив программы v2: `v2_program_files_20260907.zip` (без тестов, + единые команды) | корень репо | `[v]` |
| 11.34 | Fix: лидеры пустые после unified — логи, strip заголовков, «Тип команды», ID | `team_loader`, `logger_setup`, `team_enrich` | `[v]` |
| 11.35 | DEBUG-лог: стадии/подстадии/процедуры + тайминги (без данных из файлов) | `progress`, `debug_trace`, pipeline v2 | `[v]` |
| 11.36 | Архив `v2_program_files_20260908.zip`; удалены старые `v2_*.zip` | корень репо | `[v]` |
| 11.37 | Понятная ошибка при битом JSON в config (контекст строки) | `json_config.py` | `[v]` |
| 11.38 | Архив `v2_program_files_20260908b.zip` с корректным `team_files.files` | корень репо | `[v]` |
| 11.39 | Fix: `TypeError: DurationMatrixResult has no len()` в DEBUG после матрицы сроков | `pipeline.py` | `[v]` |
| 11.40 | Архив `v2_program_files_20260908c.zip` (fix len матрицы) | корень репо | `[v]` |
| 11.41 | Fix: нет «Дата отчета» в файле команды — весь файл = одна дата, не падаем | `team_enrich`, `team_loader` | `[v]` |
| 11.42 | Архив `v2_program_files_20260908d.zip` (fix лидеров без даты отчёта) | корень репо | `[v]` |
| 11.43 | Fix FutureWarning `fillna` downcasting в snapshot/filters + warnings→лог | `snapshot.py`, `filters.py`, `logger_setup.py` | `[v]` |
| 11.44 | Обновить `team_files.files.prod` (файлы по ТБ на 08-09-2026) | `config_excel_v2.json` | `[v]` |
| 11.45 | Архив `v2_program_files_20260908e.zip` | корень репо | `[v]` |
| 11.46 | Лёгкое оформление больших листов (`light_format_sheets`) | `excel_format.py`, config | `[v]` |
| 11.47 | `keep_leaders_only`: фильтр лидеров сразу при чтении team-файлов | `team_loader.py`, config | `[v]` |
| 11.48 | Второй лист матрицы сроков: группы А→Я, продукты по объёму (`variants`) | `duration_matrix.py`, exporter, config | `[v]` |
| 11.49 | Листы матрицы сроков с разрезом по статусу; client_id текстом; даты YYYY-MM-DD; без source_deal_id/tb_code | `duration_matrix`, exporter, excel_format, loader, config | `[v]` |
| 11.50 | Два выходных Excel + `report_parts` (analytics/detail/both) с пропуском лишних расчётов | `pipeline`, config, docs | `[v]` |
| 11.51 | На «Уникальные ID»: колонки сроков по каждому «Текущий статус» (порядок из config) | `status_durations`, snapshot, pipeline, config | `[v]` |
| 11.52 | Обновить Docs (CONFIG_EXCEL_V2 v2.5.0) + архив `v2_program_files_20260910.zip` | Docs, README, zip | `[v]` |
| 11.53 | Закрыть пробелы документации: все ключи `config_excel_v2.json` в CONFIG_EXCEL_V2 | Docs, README | `[v]` |
| 11.54 | Архив документации `docs_20260910.zip` | корень репо | `[v]` |
| 11.55 | Подробные описания параметров config (statistics/`export_km_count` и др.) | Docs, config | `[v]` |
| 11.56 | Архив документации `docs_20260910b.zip`; удалить `docs_20260910.zip` | корень репо | `[v]` |
| 11.57 | Полный справочник: подробное описание **каждого** ключа `config_excel_v2.json` | Docs | `[v]` |
| 11.59 | Третий Excel: исходные строки + лидеры/почты; отдельные фильтры; report_parts source | `source_export`, filters, pipeline, docs, zip | `[v]` |
| 11.60 | Проверка: `filters` и `source_export` независимы (не режут друг друга) | test, docs, pipeline comments | `[v]` |
| 11.61 | Актуальный `config_excel_v2.json` (prod, report_parts=all, новые exclude/source) | config, PARAMS, Docs | `[v]` |
| 11.62 | Архив `v2_program_files_20260910g.zip` + `docs_20260910g.zip` | корень репо | `[v]` |

### 11.59 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.59.1 | Расширить match: starts_with, gt/gte/lt/lte, max/min | `[v]` |
| 11.59.2 | `output.source_export` + ordered filters; report_parts source/full | `[v]` |
| 11.59.3 | Экспорт xlsx (freeze+autofilter), тесты, docs, полный zip | `[v]` |

### 11.57 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.57.1 | Извлечь все пути ключей из config | `[v]` |
| 11.57.2 | Docs/CONFIG_EXCEL_V2_PARAMS.md — карточка на каждый ключ (603) | `[v]` |
| 11.57.3 | check-скрипт 100% покрытия; ссылки из CONFIG_EXCEL_V2 / README | `[v]` |
| 11.57.4 | Архив docs_20260910c.zip + PR | `[v]` |

### 11.56 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.56.1 | Собрать zip Docs+README+ROADMAP | `[v]` |
| 11.56.2 | Обновить ссылки README/DEPLOY; удалить старый zip | `[v]` |

### 11.55 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.55.1 | Разбор `output.statistics` + `export_km_count` (зачем/как/пример/зависимости) | `[v]` |
| 11.55.2 | Углубить excel/processing/dates/filters/progress | `[v]` |
| 11.55.3 | Починить config: km_count на P80 + label; обновить zip docs | `[v]` |

### 11.54 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.54.1 | Zip: `Docs/` + README + ROADMAP | `[v]` |
| 11.54.2 | Упомянуть в README | `[v]` |

### 11.53 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.53.1 | Сверка config ↔ docs, список GAP | `[v]` |
| 11.53.2 | Секции columns/excel/processing/dates/logging/perf/progress + чек-лист | `[v]` |
| 11.53.3 | README / DEPLOY / ROADMAP | `[v]` |

### 11.52 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.52.1 | Актуализация CONFIG_EXCEL_V2 / DEPLOY / README | `[v]` |
| 11.52.2 | Сборка zip (код+config+docs, без Tests) | `[v]` |
| 11.52.3 | Удалить старый `v2_program_files_20260908e.zip` | `[v]` |

### 11.51 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.51.1 | Pivot lead×статус → колонки дней; порядок + «прочие» | `[v]` |
| 11.51.2 | Вставка в экспорт снимка detail | `[v]` |
| 11.51.3 | Config / тесты / docs | `[v]` |

### 11.50 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.50.1 | Config `output.report_parts` + суффиксы имён файлов | `[v]` |
| 11.50.2 | Файл analytics: нормативы, статистика, матрицы сроков | `[v]` |
| 11.50.3 | Файл detail: уникальные ID, менеджеры, нарушения | `[v]` |
| 11.50.4 | Условный расчёт (teams/emails/managers/matrix/funnel) | `[v]` |
| 11.50.5 | Тесты и документация | `[v]` |

### 11.49 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.49.1 | Variants матрицы со статусом после продукта + смещение freeze | `[v]` |
| 11.49.2 | Идентификатор клиента — текст (чтение/запись без обрезки) | `[v]` |
| 11.49.3 | Формат дат Excel `YYYY-MM-DD` (в т.ч. light-листы) | `[v]` |
| 11.49.4 | Убрать из снимка `source_deal_id` и `tb_code` | `[v]` |
| 11.49.5 | Тесты и документация | `[v]` |

### 11.32 — Декомпозиция

| # | Подзадача | Статус |
|---|-----------|--------|
| 11.32.1 | Config: `team_files.files` (prod объединённые), `prod_files` Канбан ЕФС | `[v]` |
| 11.32.2 | Загрузка одного комплекта + split по «Тип команды» (1=лид, 2=сделка) | `[v]` |
| 11.32.3 | Прочерк тип+ТН → не лидер; КМ/ВКС из канбана (уже fallback без лидера) | `[v]` |
| 11.32.4 | input_files_check / parallel_utils / settings / docs / тесты | `[v]` |

---

## Следующий шаг

- **9.2** — prod-прогон Excel v2 на файлах в `IN/PROD` (проверить лидеров и DEBUG-детали в логе)
