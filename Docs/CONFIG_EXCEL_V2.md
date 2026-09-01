# Справочник config_excel_v2.json

Отдельная конфигурация для **Excel-only pipeline v2** (`run_excel.py`).  
Не связана с `config.json` / `run.py` (HTML+JSON). Общие модули (`excel_loader`, `filters`, `lead_tracker`, `aggregator`) читают те же ключи, что описаны в [CONFIG.md](CONFIG.md), если они присутствуют в `config_excel_v2.json`.

**Версия документа:** 2.0.0 (2026-09-01)

---

## Оглавление

1. [Запуск и пути](#1-запуск-и-пути)
2. [Карта корневых ключей](#2-карта-корневых-ключей)
3. [Фильтры v2](#3-фильтры-v2)
4. [team_files](#4-team_files)
5. [output — листы и колонки](#5-output--листы-и-колонки)
6. [client_display](#6-client_display)
7. [Производительность](#7-производительность)
8. [Минимальный config](#8-минимальный-config)

---

## 1. Запуск и пути

```bash
python run_excel.py
# или
python -m src.excel_report.pipeline
```

| Ключ | Значение по умолчанию | Описание |
|------|----------------------|----------|
| `mode` | `"test"` | `"test"` → `paths.input_test`, `"prod"` → `paths.input_prod` |
| `paths.input_test` | `IN/TEST` | Тестовые Kanban + команды |
| `paths.input_prod` | `IN/PROD` | Prod-файлы |
| `paths.output` | `OUT/excel_v2` | Каталог отчётов |
| `paths.log` | `log` | Логи (`INFO_excel_v2_*`, `DEBUG_excel_v2_*`) |
| `test_files` | массив имён xlsx | Файлы Kanban для test |
| `prod_files` | массив имён xlsx | Файлы Kanban для prod |

**Выход:** `OUT/excel_v2/kanban_excel_v2_YYYYMMDD_HHMMSS.xlsx` — **только Excel**, JSON не создаётся.

### Листы отчёта (`output.sheets`)

| Ключ config | Имя листа | Содержание |
|-------------|-----------|------------|
| `norms` | Нормативы | P20/P50/P80 по группе+продукт+стадия; колонка ТБ + строки «все тб» |
| `leads` | Уникальные ID | Снимок лидов, лидеры, норматив P80, превышение |
| `managers` | Свод по менеджеру | Уникальные ФИО/ТН, число нарушений P80, разрез «Группа + Продукт» |
| `violations` | Свод ПрПр с отклонениями | Строка на каждое превышение с деталями лида |

---

## 2. Карта корневых ключей

| Ключ | Назначение |
|------|------------|
| `columns`, `required_column_keys`, `optional_column_keys` | Имена колонок Kanban (см. [CONFIG.md §4](CONFIG.md#4-колонки-excel-columns)) |
| `excel` | Лист Sheet1, таблица Base, движок openpyxl |
| `processing` | Дедупликация, аудит, fallback сроков |
| `dates` | Парсинг дат |
| `duration_source` | `"columns"` (по умолчанию) или `"dates"` |
| `stage_analysis_mode` | `"status"` — только «Текущий статус» |
| `product_analysis_mode` | `"group_product"` |
| `percentiles` | `[20, 50, 80]` |
| `aggregation.metrics` | `["days_on_stage"]` — только срок на стадии |
| `filters` | См. §3 |
| `team_files` | Файлы команд лида/сделки, см. §4 |
| `client_display` | Сокращение юрформ в «Клиент», см. §6 |
| `output` | Префикс, листы, подписи колонок, оформление Excel |
| `performance` | Workers, память, параллель этапов, см. §7 |
| `progress` | Консольный прогресс и сводка времени |
| `logging` | `logger_name: kanban_excel_v2` |
| `parallel_workers` | `0` = авто (CPU − reserve) |
| `excel_theme` | `"green_red"` — раскраска min/max |

Дополнительные колонки v2 (в `columns`):

| Ключ | Колонка Excel |
|------|---------------|
| `client_id` | Идентификатор клиента |
| `source_deal_id` | ID сделки в исходной системе |
| `tb_code` | Код ТБ |
| `gosb` | ГОСБ |

---

## 3. Фильтры v2

Все фильтры с `enabled: true` объединяются по **AND**. Текстовые сравнения — **без учёта регистра** (`case_sensitive: false`).

| Имя фильтра | Тип | Действие |
|-------------|-----|----------|
| `efs_flag` | value | Оставить `ЕФС флаг` = 1 |
| `change_conditions` | value | Оставить `_Изменение условий` = 0 |
| `strategy_label_2026` | contains_all | Метка содержит «Стратегия» и «2026» |
| `exclude_current_otkaz` | exclude | Убрать «Текущий статус» с «отказ» |
| `exclude_deal_otkaz` | exclude | Убрать «Стадия сделки» с «отказ» |
| `exclude_deal_zakryta` | exclude | Убрать стадию с «закрыта» |
| `exclude_deal_zaklyuchen` | exclude | Убрать стадию с «заключен» |
| `data_entry` | value | **Выключен** (`enabled: false`) — не фильтрует v2 |

Терминальные exclude применяются после inclusion-фильтров (`filter_terminal_deal_stage_rows`).

---

## 4. team_files

Аналог `manager_analytics.team_files` в `config.json`, но в **корне** config v2.

```json
"team_files": {
  "enabled": true,
  "lead_team": {
    "test": ["тест Команда л 2Т2Г на 31-08-2026.xlsx"],
    "prod": ["Команда лида на 31-08-2026.xlsx"]
  },
  "deal_team": {
    "test": ["тест Команда с 2Т2Г на 31-08-2026.xlsx"],
    "prod": ["Команда сделки на 31-08-2026.xlsx"]
  },
  "leader_values": ["Да", "да", "yes", "YES", "true", "True", "1"],
  "columns": { ... },
  "output_columns": {
    "lead": {
      "member_tab_number": "TN Лидера лида",
      "member": "ФИО Лидера лида",
      "role": "Роль Лидера лида",
      "tb": "ТБ Лидера лида"
    },
    "deal": { ... }
  }
}
```

- Лидер — строка с `Лидер` ∈ `leader_values` на max(Дата отчета) по `ID ПрПр`.
- Несколько лидеров — значения в одной ячейке через **перевод строки** (`\n`).
- Если нет лидеров — в своде менеджеров используются **КМ** (роль «ВКО») и **ВКС** (роль «ВКС»).

---

## 5. output — листы и колонки

### snapshot_columns

Поля снимка уникальных `ID ПрПр` (fill-forward по max `Дата отчета`):

| Ключ config | Заголовок Excel |
|-------------|-----------------|
| `current_status` | Стадия работы с лидом |
| `deal_stage` | Текущая стадия сделки |
| … | см. `config_excel_v2.json` |

### exceedance_columns

| Ключ | Заголовок | Описание |
|------|-----------|----------|
| `p80_norm` | Норматив P80 | Порог по ТБ лида (fallback — «все тб») |
| `current_days` | Текущий срок | Дни на стадии (актуальная дата отчёта) |
| `exceedance_flag` | превышение | `ДА` при превышении, иначе пусто |
| `exceedance_days` | дней отклонения | Текущий срок − P80 |

### excel_format

Те же правила, что в `config.json` → `output.excel_format`:

- `freeze_panes: A2`, автофильтр, ширина колонок
- `green_red` — зелёный min, красный max
- `hotspots_column_width: 55` — многострочные колонки (лидеры, «Группа + Продукт», «Клиент»)

### percentile_column_labels

Подписи перцентилей на листе «Нормативы» (`П20 дней`, `П20 лидов ≤`, …).

---

## 6. client_display

Сокращение полных юрформ в колонке «Клиент» (ООО, АО, **СЗ** и др.).  
Правила — от длинной формы к короткой; замена только префикса, остаток названия сохраняется.

```json
{"match": "специализированный застройщик", "replace": "СЗ"}
```

`enabled: false` — выводить исходный текст из Excel.

---

## 7. Производительность

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `parallel_workers` | `0` | Параллельная загрузка Kanban-файлов (`ProcessPoolExecutor`) |
| `performance.max_parallel_workers` | `4` | Потолок workers |
| `performance.reserve_cpu_cores` | `1` | Ядра, оставляемые системе |
| `performance.read_only_required_columns` | `true` | Читать только нужные колонки |
| `performance.downcast_numeric` | `true` | Сжатие типов флагов |
| `performance.free_memory_between_stages` | `true` | `gc.collect()` между этапами |
| `performance.parallel_pipeline_stages` | `true` | Параллельно: снимок + трекинг стадий + загрузка команд |
| `performance.parallel_stage_workers` | `0` | Workers для параллельных этапов (`0` = как `parallel_workers`) |

При `parallel_pipeline_stages: true` одновременно выполняются:

1. `build_lead_snapshot` (CPU)
2. `build_lead_stage_records` (CPU)
3. загрузка «Команда лида» (I/O)
4. загрузка «Команда сделки» (I/O)

---

## 8. Минимальный config

```json
{
  "mode": "test",
  "test_files": ["тест Канбан 2Т2Г (ALL) на 31-08-2026.xlsx"]
}
```

Остальное дополняется из `src/settings.py` (`normalize_config`).  
Для работы листов менеджеров нужны файлы команд в `team_files` и колонки `km` / `vks` в Kanban.

---

## Связанные документы

- [README.md](../README.md) — обзор, запуск `run_excel.py`
- [CONFIG.md](CONFIG.md) — справочник `config.json` (HTML+JSON pipeline)
- [ROADMAP.md](../ROADMAP.md) — Фаза 11
- [Docs/ToDo KANBAN v2.txt](ToDo%20KANBAN%20v2.txt) — исходное ТЗ
