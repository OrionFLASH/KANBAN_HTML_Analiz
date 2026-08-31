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
| Excel-таблица | Имя в config (`excel_table_name`: `Base`); авто fallback на Sheet1 |
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

## Фаза 10 — HTML-дашборд (будущее)

| # | Задача | Статус |
|---|--------|--------|
| 10.1 | HTML-страница с загрузкой JSON | `[ ]` |
| 10.2 | Графики (стадии × сроки) с фильтрами ТБ/продукт | `[ ]` |
| 10.3 | Интеграция в основной pipeline | `[ ]` |

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

## Следующий шаг

- **9.2** — prod-прогон на 22 файлах в каталоге `IN/`
- **9.3** — профилирование на большом объёме
- **Фаза 10** — HTML-дашборд по JSON
