# Справочник config_excel_v2.json

Отдельная конфигурация для **Excel-only pipeline v2** (`run_excel.py`).  
Не связана с `config.json` / `run.py` (HTML+JSON). Общие модули (`excel_loader`, `filters`, `lead_tracker`, `aggregator`) читают те же ключи, что описаны в [CONFIG.md](CONFIG.md), если они присутствуют в `config_excel_v2.json`.

> **Полный перечень без исключений:** на **каждый** ключ актуального `config_excel_v2.json` есть отдельная карточка (зачем / как / что даёт / от чего зависит / значение) в  
> **[CONFIG_EXCEL_V2_PARAMS.md](CONFIG_EXCEL_V2_PARAMS.md)** (656 путей, проверка: `python3 scripts/check_config_excel_v2_params.py`).  
> Этот файл — обзорный гайд по блокам и сценариям.

**Версия документа:** 2.8.0 (2026-09-10)

---

## Оглавление

0. [Полный справочник по каждому ключу](CONFIG_EXCEL_V2_PARAMS.md)
1. [Запуск и пути](#1-запуск-и-пути)
2. [Карта корневых ключей](#2-карта-корневых-ключей)
2.1. [columns](#21-columns--имена-колонок-kanban)
2.2. [excel](#22-excel--чтение-kanban)
2.3. [processing](#23-processing)
2.4. [dates](#24-dates)
2.5. [Анализ и агрегация](#25-анализ-и-агрегация)
2.6. [logging](#26-logging)
3. [Фильтры v2](#3-фильтры-v2)
3.1. [Отсечение выбросов](#31-отсечение-выбросов-outlier_clipping)
4. [team_files](#4-team_files)
4.1. [manager_emails](#manager_emails)
5. [output — листы и колонки](#5-output--листы-и-колонки)
5.1. [report_parts — файлы analytics/detail/source](#report_parts)
5.2. [source_export — третий Excel с исходными строками](#source_export)
5.2. [duration_matrix — матрицы сроков](#duration_matrix)
5.3. [status_duration_columns — сроки по статусам на «Уникальные ID»](#status_duration_columns)
5.4. [excel_format — даты, текст ID, light-листы](#excel_format)
5.5. [statistics — подробный разбор флагов](#55-statistics--подробный-разбор-флагов)
5.6. [column_labels / percentile_column_labels](#56-column_labels--percentile_column_labels)
6. [client_display](#6-client_display)
7. [Производительность](#7-производительность)
7.1. [progress](#71-progress)
8. [Минимальный config](#8-минимальный-config)
9. [Чек-лист ключей config_excel_v2.json](#9-чек-лист-ключей-config_excel_v2json)

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

**Выход — до трёх Excel-файлов** (см. [`report_parts`](#report_parts)): analytics, detail и опционально **source** (исходные строки + лидеры/почты).

| Часть | Имя файла | Листы |
|-------|-----------|--------|
| `analytics` | `{report_prefix}_analytics_{timestamp}.xlsx` | Нормативы, Статистика, все «Распределение сроков» |
| `detail` | `{report_prefix}_detail_{timestamp}.xlsx` | Уникальные ID, Свод по менеджеру, Свод ПрПр с отклонениями |

По умолчанию `report_prefix` = `kanban_excel_v2`, `timestamp_format` = `%Y%m%d_%H%M%S`. JSON **не** создаётся.

### Листы отчёта (`output.sheets`)

| Ключ config | Имя листа | Файл | Содержание |
|-------------|-----------|------|------------|
| `norms` | Нормативы | analytics | P20/P50/P80 по ТБ+группе+продукту+стадии; колонки отсечения выбросов **по каждой группе** |
| `statistics` | Статистика | analytics | Воронка фильтров + свод выбросов |
| `duration_matrix` | Распределение сроков | analytics | Матрица группа/продукт × дни; P20/P50/P80; «Всего»; порядок `by_volume` |
| `duration_matrix_by_group` | Распределение сроков (группы) | analytics | Дни ↑; группы А→Я; продукты по убыванию лидов |
| `duration_matrix_by_status` | Распределение сроков (статус) | analytics | Как основной + колонка «Текущий статус» после продукта |
| `duration_matrix_by_group_status` | Распред. сроков (группы+статус) | analytics | Раскладка по группам + статус |
| `leads` | Уникальные ID | detail | Снимок лидов, лидеры, **колонки сроков по каждому статусу**, норматив P80, превышение |
| `managers` | Свод по менеджеру | detail | Уникальные ФИО/ТН, число нарушений P80 |
| `violations` | Свод ПрПр с отклонениями | detail | Строка на каждое превышение |

---

## 2. Карта корневых ключей

| Ключ | Назначение |
|------|------------|
| `columns`, `required_column_keys`, `optional_column_keys` | Имена колонок Kanban — §2.1 |
| `excel` | Чтение xlsx Kanban — §2.2 |
| `processing` | Дедупликация, аудит, fallback сроков — §2.3 |
| `dates` | Парсинг дат — §2.4 |
| `duration_source` | `"columns"` (по умолчанию) или `"dates"` — §2.5 |
| `stage_analysis_mode` | `"status"` — только «Текущий статус» — §2.5 |
| `product_analysis_mode` | `"group_product"` — §2.5 |
| `percentiles` | `[20, 50, 80]` — §2.5 |
| `exceedance.percentile` | Порог превышения на лидах (в актуальном config часто `50`; должен входить в `percentiles`) |
| `aggregation` | `group_keys` + `metrics` — §2.5 |
| `filters` | См. §3 |
| `outlier_clipping` | Отсечение выбросов срока перед нормативами, см. §3.1 |
| `team_files` | Файлы команд лида/сделки, см. §4 |
| `manager_emails` | CSV почт Альфа/Сигма по ТН (`IN/` + filename), см. §4.1 |
| `client_display` | Сокращение юрформ в «Клиент», см. §6 |
| `output` | Префикс, **report_parts**, листы, подписи, оформление Excel — §5 |
| `performance` | Workers, память, параллель этапов, см. §7 |
| `progress` | Консольный прогресс — §7.1 |
| `logging` | Префиксы файлов логов — §2.6 |
| `parallel_workers` | `0` = авто (CPU − reserve) |
| `excel_theme` | `"green_red"` — заливка колонок «Мин»/«Макс» |

### 2.1. `columns` — имена колонок Kanban

Ключ → заголовок в Excel. Обязательные — в `required_column_keys`, остальные — в `optional_column_keys` (отсутствие optional не останавливает pipeline).

| Ключ | Типичный заголовок | Обязательный? | В снимке «Уникальные ID»? |
|------|--------------------|---------------|---------------------------|
| `report_date` | Дата отчета | да | служебный (не колонка снимка) |
| `lead_id` | ID ПрПр | да | ключ строки |
| `product_group` | Группа продукта | да | да |
| `product` | Продукт | да | да |
| `current_status` | Текущий статус | да | да (как «Стадия работы с лидом») |
| `days_on_stage` | Количество дней на текущей стадии | да | через exceedance / status_duration |
| `tb` | ТБ | да | да |
| `efs_flag` | ЕФС флаг | да | нет (фильтр) |
| `change_conditions` | _Изменение условий | да | нет (фильтр) |
| `label` | Метка | да | нет (фильтр) |
| `inn` | ИНН | нет | да |
| `client_id` | Идентификатор клиента | нет | да (**текст**) |
| `client` | Клиент | нет | да |
| `work_start_date` | Дата начала работы | нет | да |
| `deal_id` | ID сделки | нет | да |
| `source_deal_id` | ID сделки в исходной системе | нет | **нет** |
| `deal_created_date` | Дата создания сделки | нет | да |
| `deal_stage` | Стадия сделки | нет | да |
| `days_since_deal` | Количество дней с создания сделки | нет | нет |
| `tb_code` | Код ТБ | нет | **нет** |
| `gosb` | ГОСБ | нет | да |
| `km` | КМ | нет | да |
| `vks` | ВКС | нет | да |

Полный список актуальных заголовков — в `config_excel_v2.json` → `columns`. Подробнее про общие правила — [CONFIG.md §4](CONFIG.md#4-колонки-excel-columns).

### 2.2. `excel` — чтение Kanban

Параметры openpyxl/pandas при загрузке файлов из `test_files` / `prod_files`.

| Ключ | По умолчанию | Зачем | Как работает | Что влияет | Пример |
|------|--------------|-------|--------------|------------|--------|
| `sheet_name` | `"Sheet1"` | Какой лист читать | Имя вкладки в xlsx | Неверный лист → ошибка/пустые данные | `"Sheet1"` |
| `engine` | `"openpyxl"` | Движок pandas | Передаётся в `read_excel` | Смена на другой движок не поддерживается штатно | — |
| `read_only` | `true` | Экономия RAM | openpyxl `read_only=True` | Быстрее/легче на больших файлах; часть свойств книги недоступна | оставить `true` на prod |
| `data_only` | `true` | Брать **значения**, не формулы | Ячейки с формулами → вычисленный результат (как сохранён в файле) | `false` вернёт текст формулы — сломает числа/даты | всегда `true` для отчётов |
| `keep_links` | `false` | Не тянуть внешние ссылки | Ускоряет открытие | `true` может тормозить и требовать сеть | `false` |
| `na_values` | `[""]` | Что считать пустым | Пустая строка → NaN | Доп. маркеры пустоты при чтении | `["", "-"]` |
| `category_markers.for_sale` | `"К ПРОДАЖЕ"` | Служебный маркер категории | Сопоставление статуса/категории в загрузчике | Влияет на служебную разметку, не на фильтры `filters` | как в Excel |
| `category_markers.in_work` | `"В РАБОТЕ"` | То же для «в работе» | — | — | — |
| `category_markers.unknown` | `"UNKNOWN"` | Fallback неизвестной категории | — | — | — |

### 2.3. `processing`

Логика дедупа сроков и аудита после чтения Kanban.

| Ключ | По умолчанию | Зачем | Как работает | Что выходит / зависит |
|------|--------------|-------|--------------|------------------------|
| `empty_stage_values` | `["", "-", "nan", "None"]` | Какие стадии считать «пустыми» | Терминальный `exclude` **не** режет такие строки | Связан с фильтрами `exclude_*` |
| `dedup_same_date_agg` | `"max"` | Несколько строк лида на **одну** дату отчёта + стадию | Берётся `max` дней | Влияет на вход в трекинг/нормативы |
| `pick_across_dates` | `"max_days_then_latest_report_date"` | Выбор записи между **разными** датами отчёта | Сначала больший срок, при равенстве — более поздняя дата отчёта | Снимок / records |
| `group_only_product_label` | `"—"` | Подпись в колонке «Продукт», если режим только групп | Пишется эта строка вместо имени продукта | Только при `product_analysis_mode: group_only` |
| `audit_row_counts` | `true` | Не терять строки молча | В INFO/DEBUG — счётчики до/после этапов | Логи; на Excel-колонки не влияет |
| `duration_fallback_to_columns` | `true` | Запасной срок | При `duration_source: dates`, если дата пуста → колонка `days_on_stage` | Игнорируется при `duration_source: columns` |

### 2.4. `dates`

Парсинг дат из Excel/текста (`report_date`, `work_start_date`, …).

| Ключ | По умолчанию | Зачем | Как работает | Пример |
|------|--------------|-------|--------------|--------|
| `dayfirst` | `true` | Разрешить неоднозначность 01/02/2026 | Сначала день, потом месяц | `01.02.2026` → 1 февраля |
| `excel_origin` | `"1899-12-30"` | Числовые даты Excel → datetime | Epoch Windows Excel | `44927` → календарная дата |
| `formats` | `%d.%m.%Y`, `%Y-%m-%d`, … | Порядок проб `strptime` | Первый подошедший формат побеждает | Добавьте свой формат в конец/начало списка |
| `empty_values` | `""`, `-`, `nan`, … | Что считать «даты нет» | → NaT, дальше fallback/`duration_fallback` | Расширьте список под ваш выгруз |

### 2.5. Анализ и агрегация

| Ключ | По умолчанию | Зачем | Как / что зависит |
|------|--------------|-------|-------------------|
| `duration_source` | `"columns"` | Откуда брать срок | `columns` — поле `days_on_stage`; `dates` — разность дат (+ fallback) |
| `stage_analysis_mode` | `"status"` | Ось стадии | Разрез по «Текущий статус» (не по стадии сделки) |
| `product_analysis_mode` | `"group_product"` | Ось продукта | `group_product` — группа+продукт; `group_only` — только группа + `group_only_product_label` |
| `percentiles` | `[20, 50, 80]` | Какие перцентили считать глобально | Должны согласовываться с `output.statistics.percentiles[].p` и `exceedance.percentile` |
| `exceedance.percentile` | `50` (в v2-config) | Порог «превышение» на лидах | ∈ `percentiles`; влияет на колонки на «Уникальные ID» и рамку порога на матрице сроков |
| `aggregation.metrics` | `["days_on_stage"]` | Какие метрики агрегировать | Колонки нормативов строятся по этим ключам |
| `aggregation.group_keys` | product_group, product, current_status, stage_key | Ключи groupby | Менять осторожно — ломает смысл листов |

### 2.6. `logging`

| Ключ | По умолчанию | Зачем | Что получается |
|------|--------------|-------|----------------|
| `logger_name` | `"kanban_excel_v2"` | Имя логгера Python | Фильтр в коде/`logging.getLogger` |
| `info_file_prefix` | `"INFO_excel_v2"` | Префикс INFO-файла | `{prefix}_{hour}.log` в `paths.log` |
| `debug_file_prefix` | `"DEBUG_excel_v2"` | Префикс DEBUG | То же для DEBUG |
| `hour_format` | `"%Y%m%d_%H"` | Кусок имени с часом | Новый файл каждый час |

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

| Поле | Значения | Зачем | Как работает | Пример эффекта |
|------|----------|-------|--------------|----------------|
| `enabled` | bool | Вкл/выкл фильтра | `false` — фильтр не участвует в AND | Выключить стратегию на время |
| `column_key` | ключ из `columns` | Основная колонка | Берётся заголовок через `columns` | `"label"` → «Метка» |
| `column_keys` | массив ключей | Доп. колонки | Совпадение по **OR** с основной | искать метку ещё в другой колонке |
| `action` | `include` \| `exclude` | Оставить / убрать | `include` — оставить совпавшие; `exclude` — убрать | терминальные стадии — `exclude` |
| `match` | `equals` \| `contains` \| `starts_with` \| `ends_with` \| `gt` \| `gte` \| `lt` \| `lte` \| `max` \| `min` | Тип сравнения | Равенство / подстрока / префикс / суффикс / числовые и даты сравнения / экстремум по текущей выборке | `max` + `report_date`; `gt` + `[5]` |
| `values` | массив | Эталоны | Сравниваются с ячейкой | `[1]` для ЕФС |
| `values_mode` | `any` \| `all` | Логика по values | `any` — достаточно одного; `all` — все подстроки | «Стратегия» **и** «2026» |
| `value_type` | `string` \| `number` \| `date` \| `auto` | Приведение типа | Числа не сравниваются как текст | ЕФС = number |
| `case_sensitive` | bool | Регистр | `false` — «отказ» = «ОТКАЗ» | обычно `false` |

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

В актуальном `config_excel_v2.json` блок **включён**; активным примером может быть `unique_days_trim` (остальные правила — с `enabled: false`).

**Реализация:** маска отсечения строится по Series с **тем же индексом**, что у группы после `groupby` (не через `ndarray` без индекса). Иначе на больших выборках возможен `IndexingError: Unalignable boolean Series`.

---

## 4. team_files

Аналог `manager_analytics.team_files` в `config.json`, но в **корне** config v2.

Единый комплект `files` + колонка **«Тип команды»** (`1` — лид, `2` — сделка, `-`+ТН `-` — не взят в работу). Legacy `lead_team` / `deal_team` — только если `files` для mode пуст (например, test).

```json
"team_files": {
  "enabled": true,
  "pick_report_date": "latest",
  "files": {
    "test": ["Кбан К Л и С  (А 2Т2Г) __ 07-09-2026.xlsx"],
    "prod": [
      "Канбан ЕФС1 команда лида и сделки ЮЗБ (Активы-НКД-Пассивы-ФОТ) __08-09-2026.xlsx",
      "… файлы по ТБ (ЕФС0/ЕФС1) — полный список в config_excel_v2.json …",
      "Канбан ЕФС0 команда лида и сделки ЮЗБ __08-09-2026.xlsx"
    ]
  },
  "lead_team": { "test": ["тест Команда л 2Т2Г на 31-08-2026.xlsx"], "prod": [] },
  "deal_team": { "test": ["тест Команда с 2Т2Г на 31-08-2026.xlsx"], "prod": [] },
  "team_type_values": { "lead": [1, "1"], "deal": [2, "2"], "unassigned": ["-", "—", ""] },
  "leader_values": ["Да", "да", "yes", "YES", "true", "True", "1"],
  "keep_leaders_only": true,
  "columns": {
    "report_date": "Дата отчета",
    "team_added_date": "Дата добавления в команду",
    "lead_id": "ID ПрПр",
    "deal_id": "ID сделки",
    "member_tab_number": "Табельный номер участника команды",
    "member": "Участник команды",
    "role": "Роль участника команды",
    "is_leader": "Лидер",
    "tb": "ТБ",
    "team_type": "Тип команды"
  },
  "output_columns": {
    "lead": {
      "member_tab_number": "TN Лидера лида",
      "member": "ФИО Лидера лида",
      "role": "Роль Лидера лида",
      "tb": "ТБ Лидера лида"
    },
    "deal": {
      "member_tab_number": "TN Лидера сделки",
      "member": "ФИО Лидера сделки",
      "role": "Роль Лидера сделки",
      "tb": "ТБ Лидера сделки"
    }
  }
}
```

| Ключ | Описание |
|------|----------|
| `enabled` | Вкл/выкл подтягивание команд |
| `pick_report_date` | `"latest"` — брать лидеров на максимальной дате отчёта в файле |
| `files` / `lead_team` / `deal_team` | Списки xlsx по `mode`; приоритет у `files` |
| `team_type_values` | Значения колонки «Тип команды»: лид / сделка / не взят |
| `leader_values` | Значения колонки «Лидер», считающиеся истиной |
| `keep_leaders_only` | `true` — сразу после чтения оставить только строки-лидеры |
| `columns.*` | Имена колонок во входном xlsx команд |
| `output_columns.lead` / `.deal` | Заголовки колонок лидеров на листах detail |

- `keep_leaders_only: true` (по умолчанию) — участники без флага «Лидер» в Excel v2 **нигде не используются** (lookup → снимок/почты/своды); отсев снижает RAM до concat.
- После склейки `files` строки делятся по «Тип команды»; лидер — `is_leader` ∈ `leader_values` на max(`report_date`), затем max(`team_added_date`); если `Дата отчета` нет — весь файл считается одной датой отчёта; равные даты — все через `\n`.
- Отсутствие любого файла из списка — ошибка.
- Если нет лидеров (в т.ч. Тип/ТН = «-») — в своде менеджеров используются **КМ** (роль «ВКО») и **ВКС** из канбана.

### Проверка входных файлов

Перед обработкой — та же логика, что в [CONFIG.md](CONFIG.md) §3: все Kanban + team_files для `mode` должны лежать в `IN/TEST` или `IN/PROD`. Иначе pipeline останавливается.

### manager_emails

CSV со справочником почт (лежит в `IN/`, имя в config). По нормализованному ТН (8 знаков с ведущими нулями) подтягиваются **Почта Альфа** и **Почта Сигма** к лидеру лида и лидеру сделки. Несколько ТН в ячейке — почты в том же порядке через `\n`. Нет файла — предупреждение, колонки пустые.

```json
"manager_emails": {
  "enabled": true,
  "directory": "IN",
  "filename": "PROM_ALPHA_gamification-statistics.csv",
  "delimiter": ";",
  "encoding": "utf-8-sig",
  "columns": {
    "tab_number": "Табельный номер",
    "email_alpha": "Почта Альфа",
    "email_sigma": "Почта Сигма"
  },
  "output_columns": {
    "lead": {
      "email_alpha": "Почта Альфа Лидера лида",
      "email_sigma": "Почта Сигма Лидера лида"
    },
    "deal": {
      "email_alpha": "Почта Альфа Лидера сделки",
      "email_sigma": "Почта Сигма Лидера сделки"
    }
  }
}
```

На листах «Свод по менеджеру» почты вставляются сразу после «ФИО»; на «Уникальные ID» — сразу после «ФИО Лидера …»; на «Свод ПрПр…» — после «Табельный номер».

---

## 5. output — листы и колонки

### report_parts

Какие выходные файлы строить и какие тяжёлые этапы запускать.

```json
"output": {
  "report_parts": "both",
  "report_part_suffixes": {
    "analytics": "analytics",
    "detail": "detail",
    "source": "source"
  },
  "report_prefix": "kanban_excel_v2",
  "timestamp_format": "%Y%m%d_%H%M%S"
}
```

| Значение `report_parts` | Файлы | Что **считается** | Что **пропускается** |
|-------------------------|-------|-------------------|----------------------|
| `both` (default) | analytics + detail | полный pipeline без source | source_export |
| `analytics` | `*_analytics_*.xlsx` | фильтры, records, нормативы, воронка, матрицы сроков | команды, почты, detail, source |
| `detail` | `*_detail_*.xlsx` | фильтры, снимок, команды, почты, P80, exceedance, своды | матрицы / воронка на экспорт; source |
| `source` | `*_source_*.xlsx` | загрузка Kanban → фильтры `output.source_export` → лидеры/почты | analytics и detail целиком |
| `full` / `all` / `все` | все три | полный pipeline + source | — |

Допустимы список `["analytics","detail","source"]` и синонимы (`нормативы`, `лиды`, `исходные`, `1`/`2`/`3`, `оба`, `все`).

Имена файлов: `{report_prefix}_{suffix}_{timestamp}.xlsx`.

> **Зачем:** на prod матрицы и воронка тяжелее по CPU; команды/почты — по I/O. Source — отдельная выгрузка «как в файле» с своими фильтрами.

### source_export

Третий Excel: **все колонки как после загрузки** Kanban + колонки лидеров лида/сделки и их почт. Фильтры **не** из корневого `filters`, а из `output.source_export`.

```json
"output": {
  "source_export": {
    "filters_order": [
      "efs_equals_1",
      "max_report_date",
      "status_activation",
      "label_strategy_kvartal",
      "label_kvartal_2_or_3"
    ],
    "filters": {
      "efs_equals_1": {
        "enabled": true,
        "column_key": "efs_flag",
        "action": "include",
        "match": "equals",
        "values": [1],
        "values_mode": "any",
        "value_type": "number"
      },
      "max_report_date": {
        "enabled": true,
        "column_key": "report_date",
        "action": "include",
        "match": "max",
        "values": [],
        "value_type": "date"
      },
      "status_activation": {
        "enabled": true,
        "column_key": "current_status",
        "action": "include",
        "match": "contains",
        "values": ["Активация продукта"],
        "value_type": "string"
      },
      "label_strategy_kvartal": {
        "enabled": true,
        "column_key": "label",
        "action": "include",
        "match": "contains",
        "values": ["Стратегия", "квартал"],
        "values_mode": "all",
        "value_type": "string"
      },
      "label_kvartal_2_or_3": {
        "enabled": true,
        "column_key": "label",
        "action": "include",
        "match": "contains",
        "values": ["2", "3"],
        "values_mode": "any",
        "value_type": "string"
      }
    }
  }
}
```

| Поле блока | Смысл |
|------------|--------|
| `filters_order` | Порядок шагов: каждый следующий фильтр — на **остатке** предыдущего |
| `filters.<имя>.enabled` | Вкл/выкл шага без удаления из order |
| `filters.<имя>.*` | Та же универсальная схема, что в §3 (`action`, `match`, `values`, `values_mode`, `value_type`, …) |

`match=max` / `min` — оставить строки с экстремумом колонки **в текущей выборке** (после предыдущих шагов). Для даты отчёта задайте `value_type: "date"`.

Лист: `output.sheets.source` («Исходные строки»). Закрепление шапки и автофильтр — через `sheet_freeze.source` + `format_sheet`.

### sheets

```json
"sheets": {
  "norms": "Нормативы",
  "statistics": "Статистика",
  "duration_matrix": "Распределение сроков",
  "duration_matrix_by_group": "Распределение сроков (группы)",
  "duration_matrix_by_status": "Распределение сроков (статус)",
  "duration_matrix_by_group_status": "Распред. сроков (группы+статус)",
  "leads": "Уникальные ID",
  "managers": "Свод по менеджеру",
  "violations": "Свод ПрПр с отклонениями",
  "source": "Исходные строки"
}
```

| Ключ | Назначение |
|------|------------|
| `norms` | Таблица нормативов + колонки **входных фильтров** и **выбросов** по строке группы; закрепление через `sheet_freeze.norms` (колонка «Уровень анализа» не выводится) |
| `statistics` | Воронка фильтров и свод отсечений (отдельное оформление: два блока) |
| `duration_matrix` | Матрица числа лидов по сроку (дни); см. блок `output.duration_matrix` ниже |
| `duration_matrix_by_group` | Второй лист той же матрицы с раскладкой `group_alpha_product_volume` (через `variants`) |
| `duration_matrix_by_status` | Матрица с разрезом по «Текущий статус» (колонка после продукта) |
| `duration_matrix_by_group_status` | Группы А→Я + статус; имя листа ≤31 символа |
| `leads` / `managers` / `violations` | См. §1 |
| `source` | Третий файл: исходные колонки Kanban + лидеры/почты; см. [`source_export`](#source_export) |

### sheet_freeze

По каждому ключу листа из `sheets` задаётся **последняя закреплённая** строка и столбец.
Excel закрепляет всё слева и выше первой незакреплённой ячейки.

| Поле | Смысл |
|------|--------|
| `last_row` | Последняя зафиксированная строка (`1` = шапка) |
| `last_col` | Последний зафиксированный столбец (`0` = не фиксировать; `3` или `"C"` = A–C) |

```json
"sheet_freeze": {
  "default": { "last_row": 1, "last_col": 0 },
  "norms": { "last_row": 1, "last_col": 3 },
  "duration_matrix": { "last_row": 3, "last_col": 6 },
  "duration_matrix_by_group": { "last_row": 3, "last_col": 6 },
  "duration_matrix_by_status": { "last_row": 3, "last_col": 7 },
  "duration_matrix_by_group_status": { "last_row": 3, "last_col": 7 },
  "leads": { "last_row": 1, "last_col": 3 },
  "managers": { "last_row": 1, "last_col": 2 }
}
```

Примеры: `1` / `0` → freeze `A2`; `1` / `3` → шапка + A–C (после «Продукт»); `1` / `2` → шапка + A–B (после «ФИО»).
Листы со статусом: `last_col: 7` (группа + продукт + статус + P20/P50/P80 + Всего).

### duration_matrix

Лист строится по **снимку уникальных лидов** (после входных фильтров): текущий срок `_days_on_stage` (целые дни).
Агрегация кешируется отдельно для variants без статуса и со статусом (`include_status`).

| Ось | Содержание |
|-----|------------|
| Строки | «Группа продукта», «Продукт»[, «Текущий статус»] — по `sort_mode` |
| Колонки слева | После «Продукт» [и статуса]: **P20 / P50 / P80** (только значение в днях) → **«Всего»** → дни |
| Процентили | Пересчёт по лидам строки, **все стадии вместе**; те же `percentiles`, что в config |
| Строка 2 | Горизонталь «Всего» — сумма лидов по каждому дню + общий итог |
| Столбцы дней | Целые дни, где есть **хотя бы один** лид |
| Ячейка дней | Число лидов с этим сроком; **0 и пусто не пишутся** |
| Выделение | День = `exceedance.percentile` (сейчас P50) для строки — жирная сплошная граница (`threshold_border_color`) |
| Оформление | Тонкая светло-серая пунктирная граница ячеек; шапка/продукты — бледно-жёлтый; закрепление до «Всего» |

```json
"duration_matrix": {
  "enabled": true,
  "sort_mode": "by_volume",
  "variants": [
    { "sheet_key": "duration_matrix", "sort_mode": "by_volume", "include_status": false },
    {
      "sheet_key": "duration_matrix_by_group",
      "sort_mode": "group_alpha_product_volume",
      "include_status": false
    },
    {
      "sheet_key": "duration_matrix_by_status",
      "sort_mode": "by_volume",
      "include_status": true
    },
    {
      "sheet_key": "duration_matrix_by_group_status",
      "sort_mode": "group_alpha_product_volume",
      "include_status": true
    }
  ],
  "total_column_label": "Всего",
  "day_column_width": 4.5,
  "percentile_column_width": 8,
  "grid_border_color": "BFBFBF",
  "threshold_border_color": "C65911",
  "…"
}
```

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `enabled` | `true` | Выключить лист без удаления ключа из `sheets` |
| `sort_mode` | `by_volume` | Режим основного листа, если `variants` нет |
| `variants` | — | Список `{sheet_key, sort_mode, include_status?}`: несколько листов |
| `variants[].sheet_key` | — | Ключ имени листа из `output.sheets` |
| `include_status` | `false` | В variant: колонка текущего статуса после продукта |
| `total_column_label` | `"Всего"` | Подпись столбца итога |
| `day_column_width` | `4.5` | Ширина колонок дней |
| `percentile_column_width` | `8` | Ширина колонок P20/P50/P80 |
| `max_day_span` | `3000` | Лимит числа колонок дней |
| `row_height` | `28` | Высота строк продуктов |
| `header_row_height` | `22` | Высота строки заголовков |
| `filter_row_height` | `16` | Высота строки «Всего» / фильтра |
| `counts_font_size` | `14` | Размер шрифта чисел лидов (ячейки и «Всего») |
| `header_fill` | `FFF2CC` | Заливка шапки / подписей продуктов |
| `filter_row_font_color` | `D9D9D9` | Цвет шрифта служебной строки фильтра |
| `grid_border_color` | `BFBFBF` | Цвет пунктирной границы |
| `threshold_border_color` | `C65911` | Цвет жирной рамки ячейки порога превышения |
| `label_column_widths` | `A`…`D`, `total` | Ширины колонок подписей и «Всего» |
| `color_scale.start` / `.mid` / `.end` | зел./жёлт./красн. | Градиент заливки ячеек числа лидов |

**Режимы `sort_mode`:**

| Режим | Дни | Строки |
|-------|-----|--------|
| `alpha_days` | по возрастанию | группы и продукты А→Я |
| `by_volume` | по убыванию числа лидов (при равенстве — меньший день левее) | сверху максимум лидов |
| `group_alpha_product_volume` | по возрастанию | группы А→Я; внутри группы продукты по убыванию лидов |

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

Поля снимка уникальных `ID ПрПр` (fill-forward по max `Дата отчета`). Порядок колонок на листе = порядок ключей в блоке.

| Ключ config | Заголовок Excel (типичный) |
|-------------|----------------------------|
| `product_group` | Группа продукта |
| `product` | Продукт |
| `current_status` | Стадия работы с лидом |
| `inn` | ИНН |
| `client_id` | Идентификатор клиента (**текст**) |
| `client` | Клиент |
| `work_start_date` | Дата начала работы (`YYYY-MM-DD`) |
| `deal_id` | ID сделки |
| `deal_created_date` | Дата создания сделки (`YYYY-MM-DD`) |
| `deal_stage` | Текущая стадия сделки |
| `tb` | ТБ |
| `gosb` | ГОСБ |
| `km` | КМ |
| `vks` | ВКС |

**Не включать** в `snapshot_columns`: `source_deal_id`, `tb_code` — в отчёт не выводятся.

После «Стадия работы с лидом» автоматически вставляются колонки из [`status_duration_columns`](#status_duration_columns), затем колонки превышения и лидеров команд.

### status_duration_columns

На листе **«Уникальные ID»** (файл **detail**) после «Стадия работы с лидом» — колонки по вариантам «Текущий статус».

- **Заголовок колонки** = имя статуса  
- **Значение** = срок лида на этой стадии (целые дни)  
- **Пусто**, если лид на статусе не найден / срока нет  

```json
"status_duration_columns": {
  "enabled": true,
  "include_others": true,
  "others_sort": "alpha",
  "order": [
    "К продаже",
    "Выявление потребности",
    "Обсуждение условий",
    "Реализация сделки",
    "Активация продукта",
    "Продажа завершена"
  ]
}
```

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `enabled` | `true` | Выключить колонки без удаления блока |
| `order` | см. выше | Канонический порядок; колонки **всегда** в шапке (даже если в данных статуса не было) |
| `include_others` | `true` | После `order` — остальные статусы из данных |
| `others_sort` | `alpha` | Сортировка прочих: А→Я |

Источник: `lead_stage_records` (уровень `status`). Несколько продуктов/ТБ у одного лида на одной стадии → **max** дней. Имена статусов сопоставляются **без учёта регистра** (`К ПРОДАЖЕ` = `К продаже`).

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

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `freeze_panes` | `"A2"` | Fallback закрепления, если нет `sheet_freeze` для листа |
| `float_format` | `"0.00"` | Числовой формат float |
| `int_format` | `"0"` | Числовой формат целых |
| `date_format` | `"YYYY-MM-DD"` | Даты Excel (`Дата начала работы`, `Дата создания сделки`, …) |
| `thousands_format` | `"# ##0"` | Разделитель разрядов (пробел) на листе «Статистика» |
| `max_column_width` | `45` | Потолок автоширины |
| `min_column_width` | `12` | Минимум автоширины |
| `sample_rows_for_width` | `200` | Сколько строк смотреть при оценке ширины |
| `hotspots_column_width` | `55` | Ширина многострочных колонок (лидеры, «Клиент», …) |
| `light_format_sheets` | `["leads","violations"]` | Листы без полного поклеточного оформления |
| `colors.min` / `colors.max` | `C6EFCE` / `FFC7CE` | Заливка заголовков «Мин»/«Макс» при теме `green_red` |

#### Текстовые идентификаторы

«Идентификатор клиента» (и связанные ID) читаются и пишутся как **текст** (`number_format=@`), чтобы длинные значения не обрезались в Excel как числа.

В `snapshot_columns` **не выводятся** `source_deal_id` и `tb_code`.

#### `excel_theme` и `light_format_sheets`

Тема `green_red` **не отключена глобально**. В `format_sheet` заголовки с маркерами `column_labels.min_header_marker` / `max_header_marker` (по умолчанию «Мин» / «Макс») получают заливку из `excel_format.colors`.

| Лист (ключ) | `green_red` min/max | Полное поклеточное оформление |
|-------------|---------------------|-------------------------------|
| `norms`, `managers`, … | да | да |
| `leads`, `violations` (`light_format_sheets`) | **нет** | только даты/`@` для ID + freeze / автофильтр / шапка / ширина |
| `duration_matrix*` | своё оформление | не через `format_sheet` |
| `statistics` | своё оформление | не через `format_sheet` |

`light_format_sheets` ускоряет экспорт ПРОД на больших листах.

### 5.5. statistics — подробный разбор флагов

Блок `output.statistics` управляет **колонками метрик** на листе **«Нормативы»** (файл analytics).  
Реализация: `src/statistics_config.py`, расчёт — `src/percentile_stats.py` + `src/aggregator.py`.

#### Общая модель

1. Берётся группа (ТБ × группа продукта × продукт × стадия).
2. Сроки лидов (`days_on_stage`) сортируются по возрастанию.
3. Считаются min / max / число лидов и набор перцентилей из `percentiles[]` с `compute: true`.
4. Флаги `export*` решают, **какие** из посчитанных величин попадут в Excel (и в JSON у v1).  
   `compute: false` у перцентиля — величина **не считается** и не экспортируется.

Корневые ключи `output` рядом со statistics:

| Ключ | По умолчанию | Зачем | Эффект |
|------|--------------|-------|--------|
| `report_prefix` | `kanban_excel_v2` | Имя выходных файлов | `{prefix}_{analytics\|detail}_{timestamp}.xlsx` |
| `timestamp_format` | `%Y%m%d_%H%M%S` | Суффикс времени | Меняет только имя файла |
| `report_parts` / `report_part_suffixes` | §5.1 | Какие части отчёта строить | Пропуск расчётов |
| `source_export` | §5.2 | Фильтры третьего Excel | Исходные строки + лидеры |
| `all_tb_label` | `"все тб"` | Подпись агрегата без разреза по ТБ | Строка «все тб» в нормативах / воронке |
| `excel_max_sheet_name_length` | `31` | Лимит Excel на имя листа | Обрезка длинных имён (матрицы со статусом) |
| `excel_max_rows_per_sheet` / `csv_overflow` | § ниже | Overflow больших листов | CSV вместо вкладки |

#### `attach_counts_left`

| | |
|--|--|
| **Зачем** | Порядок колонок вокруг границы перцентиля: сначала «сколько лидов ≤», потом «порог в днях», потом «сколько >». |
| **Как** | `true` → суффиксы `le_count`, `days`, `gt_count`, …; `false` → сначала `days`, потом счётчики. |
| **Вывод** | Только порядок колонок на «Нормативах»; сами числа не меняются. |
| **Пример** | При `true` и P50 с le/gt: `П50 лидов ≤` \| `П50 дней` \| `П50 лидов >`. |
| **Зависит от** | Какие `export_*` включены у перцентиля. |

#### Блок `min` / `max` / `total_count`

Общий минимум / максимум срока и число лидов **в группе** (не внутри перцентильной доли).

| Ключ | Тип | Зачем | Что выводит на «Нормативах» | Зависит от |
|------|-----|-------|-----------------------------|------------|
| `min.compute` | bool | Считать минимум срока в группе | Без `true` колонки min пустые/не считаются | `aggregation.metrics` |
| `min.export` | bool | Показать колонку минимума | Заголовок из `column_labels.days_on_stage_min` («Мин срок дней») | `min.compute` |
| `min.export_le_count` | bool | Сколько лидов с сроком ≤ минимума | Обычно = числу лидов с этим мин. значением | `min.export` |
| `min.export_gt_count` | bool | Сколько лидов с сроком > минимума | `count − le` | `min.export` |
| `max.compute` / `max.export` / `export_le_count` / `export_gt_count` | bool | То же для максимума | «Макс срок дней»; `max_le_count` обычно = всем лидам группы | аналогично |
| `total_count.compute` | bool | Считать число лидов в группе | — | — |
| `total_count.export` | bool | Колонка «Число лидов» | Внутреннее имя `days_on_stage_count` | `column_labels.days_on_stage_count` |

**Пример** (как в актуальном `config_excel_v2.json`):

```json
"min": { "compute": true, "export": true, "export_le_count": false, "export_gt_count": false },
"max": { "compute": true, "export": true, "export_le_count": false, "export_gt_count": false },
"total_count": { "compute": true, "export": true }
```

→ на листе: **Мин срок дней** | **Макс срок дней** | **Число лидов**.

#### Блок `percentiles[]` — один профиль на каждый `p`

Каждый элемент — объект с числом перцентиля и флагами.  
Модель расчёта (эмпирическая по лидам): сортируем сроки; в «нижние p%» входит `ceil(p/100 × N)` лидов; **порог `days`** = срок последнего из них (макс среди нижней доли).

Числовой пример для **P50**, N = 10 лидов, сроки `10,20,…,100`:

| Поле | Значение | Смысл |
|------|----------|-------|
| `days` | 50 | граница: нижние 50% лидов заканчиваются на сроке 50 |
| `count` | 5 | сколько лидов вошло в «нижние 50%» по формуле (`ceil`) |
| `min` / `max` | 10 / 50 | мин и макс срока **внутри** этой нижней доли |
| `le_count` | ≥5 | сколько лидов во **всей** группе имеют срок ≤ `days` (может быть больше `count`, если есть равные сроки) |
| `gt_count` | N − le_count | лиды со сроком **строго больше** порога |

| Ключ | Зачем | Что появляется в Excel | Внутреннее имя | Типичный заголовок |
|------|-------|------------------------|----------------|--------------------|
| `p` | Какой перцентиль | — | — | — |
| `compute` | Считать этот перцентиль при агрегации | без `true` — нет данных | — | — |
| `export_days` | Показать **порог в днях** | колонка границы | `days_on_stage_p{p}_days` | `П{p} дней` |
| `export_count` | Показать размер нижней доли (`ceil`) | число лидов в доле | `…_p{p}_count` | `П{p} лидов` |
| `export_le_count` | Сколько лидов ≤ порога | счётчик слева/справа от days | `…_p{p}_le_count` | `П{p} лидов ≤` |
| `export_gt_count` | Сколько лидов > порога | счётчик | `…_p{p}_gt_count` | `П{p} лидов >` |
| `export_min` | Мин срок среди нижней доли | колонка | `…_p{p}_min` | `П{p} мин` |
| `export_max` | Макс срок среди нижней доли (= `days`) | колонка | `…_p{p}_max` | `П{p} макс` |
| **`export_km_count`** | Число **уникальных КМ**, у которых срок **≥ порога** этого перцентиля | колонка «П{p} КМ ≥» | `…_p{p}_km_count` | `П{p} КМ ≥` |

##### `export_km_count` — подробно

| | |
|--|--|
| **Зачем** | Понять, сколько разных менеджеров (КМ) «сидят» на сроках не ниже порога перцентиля — нагрузка/хвост, а не просто число лидов. |
| **Как считается** | В группе: лиды с `days_on_stage ≥ threshold`, где `threshold` = `…_p{p}_days`; по колонке КМ — `nunique` (пустые/`-` отбрасываются). Код: `count_unique_km_at_or_above_p80` в `percentile_stats.py`. |
| **Ограничение реализации** | Значение **заполняется только для P80** (`aggregator` смотрит на перцентиль 80). Для P20/P50 флаг `export_km_count: true` добавит колонку в список экспорта, но **ячейки будут пустыми**, если расчёт для этого `p` не сделан. Ставьте `export_km_count: true` на профиль `"p": 80`. |
| **Что выводит** | Целое число уникальных ФИО КМ. Заголовок из `percentile_column_labels.days_on_stage.km_count` (`"П{p} КМ ≥"` → «П80 КМ ≥»). |
| **От чего зависит** | `columns.km` / наличие колонки «КМ» в данных; `optional_column_keys` должен включать `km`; `compute: true` и `export_days` у того же `p` (нужен порог); `export_km_count: true` у **P80**. |
| **Не путать с** | `export_count` / `export_le_count` — это **лиды**, не менеджеры. |

Пример включения только порога P80 + КМ:

```json
{ "p": 80, "compute": true, "export_days": true, "export_km_count": true }
```

Актуальный `config_excel_v2.json` (схема колонок на «Нормативах» по метрике срока):

| Профиль | Включено | Колонки |
|---------|----------|---------|
| P20 | `export_days` | П20 дней |
| P50 | `export_days`, `export_le_count`, `export_gt_count` | П50 лидов ≤ \| П50 дней \| П50 лидов > |
| P80 | `export_days`, `export_km_count` | П80 дней \| П80 КМ ≥ |
| + min/max/count | `export: true` | Мин / Макс / Число лидов |

Полный пример блока:

```json
"statistics": {
  "attach_counts_left": true,
  "min": { "compute": true, "export": true },
  "max": { "compute": true, "export": true },
  "total_count": { "compute": true, "export": true },
  "percentiles": [
    { "p": 20, "compute": true, "export_days": true },
    {
      "p": 50,
      "compute": true,
      "export_days": true,
      "export_le_count": true,
      "export_gt_count": true
    },
    {
      "p": 80,
      "compute": true,
      "export_days": true,
      "export_km_count": true
    }
  ]
}
```

Не указанные `export_*` по умолчанию `false` (кроме `export_days` у дефолтных профилей в коде).

### 5.6. column_labels / percentile_column_labels

| Группа | Ключи | Зачем | Пример эффекта |
|--------|-------|-------|----------------|
| Оси | `product_group`, `product`, `tb`, `current_status` | Заголовки измерений на «Нормативах» | «Группа продукта», «Стадия работы с лидом» |
| Метрики | `days_on_stage_min`, `_max`, `_count` | Подписи min/max/числа лидов | «Мин срок дней» |
| Аудит | `filter_before`, `filter_after`, `outlier_*`, `outlier_rule_<name>` | Подписи колонок воронки/выбросов; `<name>` = `rules[].name` | «Отсечено: global_max_500» |
| Тема | `min_header_marker`, `max_header_marker` | Подстрока в заголовке → заливка green_red | «Мин» / «Макс» |
| Перцентили | `percentile_column_labels.<metric>.{days,count,min,max,le_count,gt_count,km_count}` | Шаблоны с `{p}` | `"km_count": "П{p} КМ ≥"` → «П80 КМ ≥» |

Без строки `km_count` в `percentile_column_labels` колонка `…_km_count` может уйти в Excel **без нормального заголовка** (или с внутренним именем).

#### `output.exceedance_columns`

Заголовки колонок превышения на «Уникальные ID» (см. § exceedance).

| Ключ | Зачем | Пример заголовка | Зависит от |
|------|-------|------------------|------------|
| `p80_norm` | Норматив порога для лида | `Норматив P{p}` → «Норматив P50» если `exceedance.percentile=50` | `exceedance.percentile` |
| `current_days` | Текущий срок лида | «Текущий срок» | снимок / `_days_on_stage` |
| `exceedance_flag` | Признак превышения | «превышение» = `ДА` или пусто | порог нормы |
| `exceedance_days` | На сколько дней выше нормы | «дней отклонения» | `current − norm` |

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

---

## 6. client_display

Сокращение полных юрформ в колонке «Клиент» (ООО, АО, **СЗ** и др.).  
Правила — от длинной формы к короткой; замена только префикса, остаток названия сохраняется.

| Ключ | Описание |
|------|----------|
| `enabled` | `false` — выводить исходный текст из Excel |
| `abbreviations[]` | Список `{ "match": "…", "replace": "…" }` (без учёта регистра при сопоставлении префикса) |

```json
{"match": "специализированный застройщик", "replace": "СЗ"}
```

Полный список сокращений — в `config_excel_v2.json` → `client_display.abbreviations`.

---

## 7. Производительность

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `parallel_workers` | `0` | Параллельная загрузка Kanban-файлов (`ProcessPoolExecutor`); `0` = авто |
| `performance.max_parallel_workers` | `8` | Потолок workers |
| `performance.reserve_cpu_cores` | `1` | Ядра, оставляемые системе |
| `performance.read_only_required_columns` | `true` | Читать только нужные колонки |
| `performance.downcast_numeric` | `true` | Сжатие типов флагов |
| `performance.free_memory_between_stages` | `true` | `gc.collect()` между этапами |
| `performance.parallel_pipeline_stages` | `true` | Параллельно: снимок + трекинг стадий + загрузка команд |
| `performance.parallel_stage_workers` | `0` | Workers для параллельных этапов (`0` = как `parallel_workers`) |
| `performance.parallel_team_files` | `true` | Параллельное чтение файлов команд |
| `performance.compact_distribution_series` | `true` | Legacy/совместимость с HTML+JSON: компактные серии в JSON |
| `performance.precompute_pivot_matrices` | `false` | Legacy: предрасчёт pivot для HTML; в Excel v2 обычно выкл. |

### `performance.adaptive_resources`

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `enabled` | `true` | Мониторинг RAM и автоснижение workers |
| `min_available_ram_gb` | `3.0` | Порог warn (ГБ свободной RAM) |
| `critical_available_ram_gb` | `1.5` | Порог critical по свободной RAM |
| `warn_used_ram_percent` | `80.0` | warn, если занято ≥ % RAM |
| `critical_used_ram_percent` | `92.0` | critical по % занятой RAM |
| `sequential_load_below_total_ram_gb` | `16.0` | При общей RAM &lt; порога — осторожный режим |
| `low_ram_max_workers` | `2` | Потолок workers в осторожном режиме |
| `low_ram_disable_parallel_stages` | `true` | Выкл. `parallel_pipeline_stages` в low-RAM |
| `low_ram_disable_parallel_teams` | `true` | Выкл. `parallel_team_files` в low-RAM |
| `warn_max_workers` | `2` | Потолок workers при warn |
| `warn_disable_parallel_stages` | `true` | Выкл. параллельные этапы при warn |
| `critical_max_workers` | `1` | Потолок workers при critical |
| `critical_disable_parallel_stages` | `true` | Выкл. параллельные этапы при critical |
| `critical_disable_parallel_teams` | `true` | Выкл. параллельную загрузку команд при critical |
| `input_size_per_worker_gb` | `1.2` | Оценка: размер входа на worker при выборе числа процессов |
| `gc_on_pressure` | `true` | `gc.collect()` между файлами при warn/critical |
| `override_explicit_workers_on_critical` | `true` | Ограничение явного `parallel_workers` при critical |
| `disable_html_slices_on_critical` | `true` | Legacy HTML: отключить срезы при critical (на Excel v2 не влияет) |

При `parallel_pipeline_stages: true` одновременно выполняются:

1. `build_lead_snapshot` (CPU)
2. `build_lead_stage_records` (CPU)
3. загрузка «Команда лида и сделки» (I/O, единый комплект + split по типу)

### 7.1. `progress`

| Ключ | По умолчанию | Зачем | Что выводит | Зависит от |
|------|--------------|-------|-------------|------------|
| `enabled` | `true` | Консольный прогресс этапов | Строки прогресса в stdout | — |
| `log_every_seconds` | `3` | Heartbeat при долгих операциях | Сообщение в лог не чаще раза в N сек | Долгие этапы загрузки/агрегации |
| `show_timing_summary` | `true` | Сводка времени в конце | Таблица «этап → секунды» в логе/консоли | — |
| `debug_detail` | `true` | Тайминги подэтапов | Доп. строки в DEBUG-логе | `logging.debug_file_prefix` |

---

## 8. Минимальный config

```json
{
  "mode": "test",
  "test_files": ["тест Канбан 2Т2Г (ALL) на 31-08-2026.xlsx"],
  "output": {
    "report_parts": "both"
  }
}
```

Остальное дополняется из `src/settings.py` (`normalize_config`).  

Типичные переключатели без правки кода:

| Задача | Ключ |
|--------|------|
| Только нормативы и матрицы | `"report_parts": "analytics"` |
| Только уникальные ID / менеджеры | `"report_parts": "detail"` |
| Только исходные строки + лидеры | `"report_parts": "source"` |
| Все три файла | `"report_parts": "full"` |
| Порог превышения = медиана | `"exceedance": { "percentile": 50 }` |
| Порядок статусов на «Уникальные ID» | `output.status_duration_columns.order` |
| Формат дат | `output.excel_format.date_format` (`YYYY-MM-DD`) |

Для листов менеджеров нужны файлы команд в `team_files` и колонки `km` / `vks` в Kanban.

---

## 9. Чек-лист ключей `config_excel_v2.json`

Сверка «есть в config → описано в этом документе (или явно отсылается к CONFIG.md)».

| Блок | Ключи (верхний уровень / важные вложенные) | Раздел |
|------|--------------------------------------------|--------|
| Пути / режим | `mode`, `paths.*`, `test_files`, `prod_files` | §1 |
| Колонки | `columns.*`, `required_column_keys`, `optional_column_keys` | §2.1 |
| Excel I/O | `excel.sheet_name`, `engine`, `read_only`, `data_only`, `keep_links`, `na_values`, `category_markers.*` | §2.2 |
| Processing | `empty_stage_values`, `dedup_same_date_agg`, `pick_across_dates`, `group_only_product_label`, `audit_row_counts`, `duration_fallback_to_columns` | §2.3 |
| Dates | `dayfirst`, `excel_origin`, `formats`, `empty_values` | §2.4 |
| Анализ | `duration_source`, `stage_analysis_mode`, `product_analysis_mode`, `percentiles`, `exceedance`, `aggregation.group_keys`, `aggregation.metrics` | §2.5 |
| Logging | `logger_name`, `info_file_prefix`, `debug_file_prefix`, `hour_format` | §2.6 |
| Filters | `filters.*` (универсальная схема) | §3 |
| Outliers | `outlier_clipping.*`, `rules[]` | §3.1 |
| Teams | `team_files.*` вкл. `pick_report_date`, `columns.*`, `output_columns.*` | §4 |
| Emails | `manager_emails.*` | §4.1 |
| Client | `client_display.enabled`, `abbreviations[]` | §6 |
| Output core | `report_prefix`, `timestamp_format`, `report_parts`, `report_part_suffixes`, `source_export`, `all_tb_label`, `excel_max_sheet_name_length`, `excel_max_rows_per_sheet`, `csv_overflow` | §5 / §5.5 |
| Sheets | `sheets.*`, `sheet_freeze.*` | §5 |
| Matrix | `duration_matrix.*` (variants, widths, heights, fills, `color_scale`) | §5.2 |
| Snapshot | `snapshot_columns`, `status_duration_columns.*`, `exceedance_columns` | §5 |
| Labels / stats | `column_labels.*`, `percentile_column_labels`, `statistics.*` | §5.5 |
| Excel format | `excel_format.*`, `excel_theme` | §5.4 |
| Perf | `parallel_workers`, `performance.*`, `adaptive_resources.*` | §7 |
| Progress | `progress.*` | §7.1 |

Если добавили новый ключ в `config_excel_v2.json` — допишите строку в этот чек-лист и таблицу соответствующего раздела.

---

## Связанные документы

- **[CONFIG_EXCEL_V2_PARAMS.md](CONFIG_EXCEL_V2_PARAMS.md)** — карточка на каждый ключ `config_excel_v2.json`
- [README.md](../README.md) — обзор, запуск `run_excel.py`
- [CONFIG.md](CONFIG.md) — справочник `config.json` (HTML+JSON pipeline)
- [DEPLOY.md](DEPLOY.md) — перенос на другой ПК
- [ROADMAP.md](../ROADMAP.md) — Фаза 11
- [Docs/ToDo KANBAN v2.txt](ToDo%20KANBAN%20v2.txt) — исходное ТЗ