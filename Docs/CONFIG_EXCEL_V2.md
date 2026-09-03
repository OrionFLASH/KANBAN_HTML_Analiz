# Справочник config_excel_v2.json

Отдельная конфигурация для **Excel-only pipeline v2** (`run_excel.py`).  
Не связана с `config.json` / `run.py` (HTML+JSON). Общие модули (`excel_loader`, `filters`, `lead_tracker`, `aggregator`) читают те же ключи, что описаны в [CONFIG.md](CONFIG.md), если они присутствуют в `config_excel_v2.json`.

**Версия документа:** 2.2.2 (2026-09-02)

---

## Оглавление

1. [Запуск и пути](#1-запуск-и-пути)
2. [Карта корневых ключей](#2-карта-корневых-ключей)
3. [Фильтры v2](#3-фильтры-v2)
3.1. [Отсечение выбросов](#31-отсечение-выбросов-outlier_clipping)
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
python -m src.v2.pipeline
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
| `norms` | Нормативы | P20/P50/P80 по ТБ+группе+продукту+стадии; колонки отсечения выбросов **по каждой группе**; автофильтр и закрепление шапки |
| `statistics` | Статистика | Воронка фильтров (до/после/отсечено строк и лидов) + свод выбросов по всем группам |
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
| `exceedance.percentile` | Порог превышения на лидах (по умолчанию `80`; должен входить в `percentiles`) |
| `aggregation.metrics` | `["days_on_stage"]` — только срок на стадии |
| `filters` | См. §3 |
| `outlier_clipping` | Отсечение выбросов срока перед нормативами, см. §3.1 |
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

Все фильтры с `enabled: true` объединяются по **AND**.  
Формат — **универсальный** (см. ниже). Старые ключи (`value`, `contains*`, `exclude_*`) по-прежнему понимаются адаптером в `src/filters.py`.

> **Нет HTML/JSON:** в `config_excel_v2.json` **не используется** поле `html_slice` из `config.json`. В v2 действует только `enabled: true/false`.

### Универсальная схема

```json
"имя_фильтра": {
  "enabled": true,
  "column_key": "label",
  "column_keys": [],
  "action": "include",
  "match": "contains",
  "values": ["Стратегия 2 квартал 2026", "Стратегия 2 кватал 2026"],
  "values_mode": "any",
  "value_type": "string",
  "case_sensitive": false
}
```

| Поле | Значения | Смысл |
|------|----------|--------|
| `column_key` | ключ из `columns` | основная колонка |
| `column_keys` | массив ключей | доп. колонки; совпадение по **OR** |
| `action` | `include` \| `exclude` | оставить / убрать совпавшие строки |
| `match` | `equals` \| `contains` | целое поле / подстрока |
| `values` | массив | эталоны сравнения |
| `values_mode` | `any` \| `all` | достаточно одного / нужны все |
| `value_type` | `string` \| `number` \| `date` \| `auto` | приведение типа |
| `case_sensitive` | bool | для string |

Терминальные `action: exclude` применяются после inclusion (`filter_terminal_deal_stage_rows`).  
Пустые стадии (`processing.empty_stage_values`) **не** попадают под exclude.

### Текущий набор v2

| Имя | action | match | values | values_mode | value_type |
|-----|--------|-------|--------|-------------|------------|
| `efs_flag` | include | equals | `[1]` | any | number |
| `change_conditions` | include | equals | `[0]` | any | number |
| `strategy_label` | include | contains | `["Стратегия"]` | any | string (**вкл.**) |
| `strategy_label_2026` | include | contains | оба варианта «Стратегия 2 квар*тал* 2026» | any | string (`enabled: false`) |
| `strategy_label_and_2026` | include | contains | `["Стратегия", "2026"]` | **all** | string (`enabled: false`) |
| `current_status_activation` | include | contains | `["АКТИВАЦИЯ ПРОДУКТА"]` | any | string (`enabled: false`) |
| `exclude_current_otkaz` | exclude | contains | `["отказ"]` | any | string |
| `exclude_current_for_sale` | exclude | equals | `["К ПРОДАЖЕ"]` | any | string |
| `exclude_deal_otkaz` | exclude | contains | `["отказ"]` | any | string |
| `exclude_deal_zakryta` | exclude | contains | `["закрыта"]` | any | string |
| `exclude_deal_zaklyuchen` | exclude | contains | `["заключен"]` | any | string |
| `data_entry` | include | equals | `[0]` | any | number (`enabled: false`) |

По умолчанию из меток активен только `strategy_label` (подстрока «Стратегия»). Варианты `*_2026` и фильтр стадии «АКТИВАЦИЯ ПРОДУКТА» выключены — включаются в config при необходимости.

---

## 3.1. Отсечение выбросов (`outlier_clipping`)

Перед расчётом min/max/перцентилей в **каждой группе** агрегации (группа продукта + продукт + стадия [+ ТБ]) из выборки убираются нетипичные сроки. Снимок лидов и лист «Уникальные ID» **не** режутся — только нормативы / статистика.

```json
"outlier_clipping": {
  "enabled": true,
  "metric": "days_on_stage",
  "export_audit": true,
  "min_group_size": 5,
  "min_remaining": 3,
  "rules": [
    {
      "name": "global_max_500",
      "enabled": true,
      "scope": {},
      "mode": "range",
      "max_days": 500,
      "min_remaining": 3
    },
    {
      "name": "band_credits",
      "enabled": true,
      "scope": { "product_group": "Кредиты", "current_status": "В РАБОТЕ" },
      "mode": "range",
      "min_days": 2,
      "max_days": 500
    },
    {
      "name": "trim5",
      "enabled": true,
      "scope": {},
      "mode": "percentile_trim",
      "trim_lower_pct": 5,
      "trim_upper_pct": 5,
      "min_remaining": 5
    },
    {
      "name": "unique_days_10",
      "enabled": false,
      "scope": {},
      "mode": "unique_days_trim",
      "trim_lower_pct": 10,
      "trim_upper_pct": 10
    },
    {
      "name": "auto_iqr",
      "enabled": true,
      "scope": {},
      "mode": "iqr",
      "iqr_k": 1.5
    }
  ]
}
```

| Поле | Описание |
|------|----------|
| `enabled` | Вкл/выкл всего блока |
| `metric` | Колонка срока (`days_on_stage`) |
| `export_audit` | Колонки аудита на листе «Нормативы» |
| `min_group_size` | Минимум строк в группе для расчёта порогов `iqr` / `percentile_trim` |
| `min_remaining` | Минимум лидов после правила: если осталось бы меньше — правило **не применяется** (можно переопределить в `rules[].min_remaining`) |
| `rules[].name` | Имя для колонки «Отсечено: …» |
| `rules[].scope` | `{}` = все группы; иначе фильтр по `product_group` / `product` / `current_status` / `tb` (строка или массив) |
| `rules[].mode` | `range` \| `percentile_trim` \| `unique_days_trim` \| `iqr` |
| `rules[].min_remaining` | Опционально: порог «минимум лидов после» только для этого правила |
| `min_days` / `max_days` | Для `range`: отсечь срок `< min` или `> max` |
| `trim_lower_pct` / `trim_upper_pct` | Для `percentile_trim`: % квантилей снизу / сверху; для `unique_days_trim`: % от **числа уникальных сроков** слева / справа |
| `iqr_k` | Для `iqr`: множитель (обычно 1.5) |

#### `unique_days_trim` — отсечение по уникальным срокам

В группе берутся **разные значения дней**, по которым есть лиды (дни без лидов не считаются).  
Процент считается от **числа таких уникальных значений**, не от числа лидов.

Пример: 20 уникальных сроков `1, 20, 25, …, 80, 99`, `trim_lower_pct = trim_upper_pct = 10`  
→ `10% × 20 = 2` значения слева и 2 справа → отсекаются все лиды с днями `1`, `20` и `80`, `99`.  
Число уникальных значений после отсечения: `20 − 4 = 16`. Доля округляется **вниз** (`int`); если слева+справа ≥ всех уникальных — правило пропускается.

Правила применяются **по порядку**; на листе **«Статистика»**:

1. **Воронка фильтров**: по каждому активному фильтру / исключению — «До/После/Отсечено» для **строк** и **уникальных лидов**.
2. **Свод выбросов**: суммы колонок аудита по всем группам (и статус, если `outlier_clipping` выключен).

На листе **«Нормативы»** — обычная таблица по ТБ / группе / продукту / стадии (автофильтр, закрепление шапки) с колонками аудита по **каждой группе**: `До отсечения`, `После отсечения`, `Отсечено (всего)`, `Отсечено: <name>` (`export_audit: true`).

Чтобы колонки выбросов появились, нужно **`outlier_clipping.enabled: true`** и хотя бы одно правило с **`enabled: true`**.

По умолчанию в `config_excel_v2.json` блок **выключен** (`enabled: false`), примеры правил — с `enabled: false`.

---

## 4. team_files

Аналог `manager_analytics.team_files` в `config.json`, но в **корне** config v2.

```json
"team_files": {
  "enabled": true,
  "lead_team": {
    "test": ["тест Команда л 2Т2Г на 31-08-2026.xlsx"],
    "prod": [
      "Команда лида УБ на 01-09-2026.xlsx",
      "Команда лида ЮЗБ на 01-09-2026.xlsx",
      "Команда лида СРБ на 01-09-2026.xlsx",
      "Команда лида СИБ ЦЧБ на 01-09-2026.xlsx",
      "Команда лида СЗБ на 01-09-2026.xlsx",
      "Команда лида МБ на 01-09-2026.xlsx",
      "Команда лида ДВБ ПБ на 01-09-2026.xlsx",
      "Команда лида ББ ВВБ на 01-09-2026.xlsx"
    ]
  },
  "deal_team": {
    "test": ["тест Команда с 2Т2Г на 31-08-2026.xlsx"],
    "prod": [
      "Команда сделки УБ на 01-09-2026.xlsx",
      "Команда сделки ЮЗБ на 01-09-2026.xlsx",
      "Команда сделки СРБ на 01-09-2026.xlsx",
      "Команда сделки СИБ ЦЧБ на 01-09-2026.xlsx",
      "Команда сделки СЗБ на 01-09-2026.xlsx",
      "Команда сделки МБ на 01-09-2026.xlsx",
      "Команда сделки ДВБ ПБ на 01-09-2026.xlsx",
      "Команда сделки ББ ВВБ на 01-09-2026.xlsx"
    ]
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

- Лидер — строка с `Лидер` ∈ `leader_values` на max(Дата отчета) по `ID ПрПр` (lead) или `ID сделки` (deal).
- **Несколько prod-файлов** одного типа загружаются последовательно и **склеиваются** (`pd.concat`); отсутствие любого файла из списка — ошибка.
- Несколько лидеров — значения в одной ячейке через **перевод строки** (`\n`).
- Если нет лидеров — в своде менеджеров используются **КМ** (роль «ВКО») и **ВКС** (роль «ВКС»).

### Проверка входных файлов

Перед обработкой — та же логика, что в [CONFIG.md](CONFIG.md) §3: все Kanban + team_files для `mode` должны лежать в `IN/TEST` или `IN/PROD`. Иначе pipeline останавливается.

### output.statistics

Управление экспортом min/max/перцентилей (расчёт всегда полный). По умолчанию: число лидов — да; min/max — нет; P20/P50 — только граница; P80 — граница + le/gt/min/max. См. [CONFIG.md](CONFIG.md).

---

## 5. output — листы и колонки

### sheets

```json
"sheets": {
  "norms": "Нормативы",
  "statistics": "Статистика",
  "leads": "Уникальные ID",
  "managers": "Свод по менеджеру",
  "violations": "Свод ПрПр с отклонениями"
}
```

| Ключ | Назначение |
|------|------------|
| `norms` | Таблица нормативов + колонки **входных фильтров** и **выбросов** по строке группы; `freeze_panes` / автофильтр как у остальных табличных листов |
| `statistics` | Воронка фильтров и свод отсечений (отдельное оформление: два блока) |
| `leads` / `managers` / `violations` | См. §1 |

### Колонки отсечения на листе «Нормативы»

В конце каждой строки группы (после перцентилей):

| Внутренний ключ | Заголовок (по умолчанию) | Смысл |
|-----------------|--------------------------|--------|
| `filter_before` | До отсечения | Уник. лиды в группе **до** всех входных фильтров |
| `filter_dropped_<имя>` | Отсечено: `<имя>` | Уник. лиды, отсечённые этим фильтром (include/exclude) |
| `filter_after` | После фильтров | Уник. лиды в группе **после** всех входных фильтров |
| `outlier_before` | До выбросов | Записи группы до правил `outlier_clipping` |
| `outlier_rule_<имя>` | Отсечено: `<имя>` | Отсечено правилом выбросов |
| `outlier_after` | После отсечения | Записи группы после всех правил выбросов |
| `outlier_clipped_total` | Отсечено выбросами (всего) | Сумма отсечений выбросов в группе |

Суммы по всем группам дублируются на листе «Статистика».

### snapshot_columns

Поля снимка уникальных `ID ПрПр` (fill-forward по max `Дата отчета`):

| Ключ config | Заголовок Excel |
|-------------|-----------------|
| `current_status` | Стадия работы с лидом |
| `deal_stage` | Текущая стадия сделки |
| … | см. `config_excel_v2.json` |

### exceedance / exceedance_columns

Порог превышения задаётся в корневом блоке:

```json
"exceedance": { "percentile": 80 }
```

Значение должно входить в `percentiles`. Для медианы: `"percentile": 50`.

| Ключ | Заголовок | Описание |
|------|-----------|----------|
| `p80_norm` | `Норматив P{p}` | Порог по ТБ лида (fallback — «все тб»); `{p}` → число из `exceedance.percentile` |
| `current_days` | Текущий срок | Дни на стадии (актуальная дата отчёта) |
| `exceedance_flag` | превышение | `ДА` при превышении, иначе пусто |
| `exceedance_days` | дней отклонения | Текущий срок − норматив |

### excel_format

Те же правила, что в `config.json` → `output.excel_format`:

- `freeze_panes: A2`, автофильтр, ширина колонок
- `green_red` — зелёный min, красный max
- `hotspots_column_width: 55` — многострочные колонки (лидеры, «Группа + Продукт», «Клиент»)
- `thousands_format: "# ##0"` — разделитель разрядов (пробел) для чисел на листе **«Статистика»**

### Большие листы → CSV

Если на листе **больше** `excel_max_rows_per_sheet` строк данных (по умолчанию **900 000**), вкладка в xlsx **не создаётся** — данные пишутся в отдельный CSV рядом с отчётом:

`kanban_excel_v2_{timestamp}_{Имя листа}.csv`

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `excel_max_rows_per_sheet` | `900000` | Порог строк (лимит Excel ~1 048 576) |
| `csv_overflow.enabled` | `true` | Включить выгрузку в CSV |
| `csv_overflow.delimiter` | `";"` | Разделитель полей |
| `csv_overflow.encoding` | `utf-8-sig` | Кодировка (BOM для Excel в Windows) |

Если **все** листы ушли в CSV, в xlsx остаётся служебный лист «Экспорт CSV» со списком файлов.

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

### `performance.adaptive_resources`

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `enabled` | `true` | Мониторинг RAM и автоснижение workers (см. `CONFIG.md` §8) |
| `min_available_ram_gb` | `3.0` | Порог warn (ГБ свободной RAM) |
| `critical_available_ram_gb` | `1.5` | Порог critical |
| `sequential_load_below_total_ram_gb` | `16.0` | При общей RAM &lt; порога — осторожный режим |
| `low_ram_max_workers` | `2` | Потолок workers в осторожном режиме |
| `warn_max_workers` | `2` | Потолок workers при warn |
| `critical_max_workers` | `1` | Потолок workers при critical |
| `gc_on_pressure` | `true` | `gc.collect()` между файлами при warn/critical |
| `override_explicit_workers_on_critical` | `true` | Ограничение явного `parallel_workers` при critical |

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
