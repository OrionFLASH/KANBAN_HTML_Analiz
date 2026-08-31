# Справочник config.json

Полное описание параметров конфигурации сервиса KANBAN HTML Analiz.

Отсутствующие ключи автоматически дополняются значениями по умолчанию из `src/settings.py`.

---

## Быстрые примеры

### Test-режим (по умолчанию)

```json
{
  "mode": "test",
  "test_files": ["2ГОСБ1ТБ.xlsx"]
}
```

### Prod на 22 файла

```json
{
  "mode": "prod",
  "parallel_workers": 0,
  "performance": {
    "max_parallel_workers": 3,
    "reserve_cpu_cores": 2
  }
}
```

### Анализ по датам + подстадии

```json
{
  "duration_source": "dates",
  "stage_analysis_mode": "both",
  "processing": {
    "duration_fallback_to_columns": true
  }
}
```

### Фильтр «Стратегия» + ЕФС

```json
{
  "filters": {
    "efs_flag": { "enabled": true, "column_key": "efs_flag", "value": 1 },
    "strategy_label": {
      "enabled": true,
      "column_key": "label",
      "contains": "Стратегия",
      "case_sensitive": false
    }
  }
}
```

---

## 1. Режим работы

### `mode`

| Значение | Описание |
|----------|----------|
| `"test"` | Файлы из `paths.input_test` + список `test_files` |
| `"prod"` | Файлы из `paths.input_prod` + список `prod_files` |

**Пример:**

```json
"mode": "prod"
```

---

## 2. Пути (`paths`)

Все пути **относительно корня проекта** (где лежит `run.py`), не зависят от текущей папки IDE.

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `input_test` | `Docs/FileIN` | Test Excel |
| `input_prod` | `IN` | Prod Excel (22 файла) |
| `output` | `OUT` | Excel + JSON с timestamp |
| `log` | `log` | INFO/DEBUG логи |

**Пример (Windows-пути через прямой слэш допустимы):**

```json
"paths": {
  "input_test": "Docs/FileIN",
  "input_prod": "D:/Data/Kanban/IN",
  "output": "OUT",
  "log": "log"
}
```

---

## 3. Списки файлов

### `test_files`

Массив имён xlsx для режима `test`.

```json
"test_files": ["2ГОСБ1ТБ.xlsx"]
```

Несколько test-файлов:

```json
"test_files": ["2ГОСБ1ТБ.xlsx", "2ГОСБ1ТБ SHORT.xlsx"]
```

### `prod_files`

22 имени Kanban-файлов (11 ТБ × 2 категории). Полный список — в корневом `config.json`.

---

## 4. Колонки Excel (`columns`)

Сопоставление **внутреннего ключа** → **имя колонки в Excel**.

| Ключ | Имя по умолчанию | Назначение |
|------|------------------|------------|
| `report_date` | Дата отчета | Снимок отчёта |
| `lead_id` | ID ПрПр | Уникальный лид |
| `product_group` | Группа продукта | Группа |
| `product` | Продукт | Продукт |
| `work_start_date` | Дата начала работы | Старт лида |
| `current_status` | Текущий статус | Стадия Kanban |
| `days_on_stage` | Количество дней на текущей стадии | Срок на стадии |
| `deal_created_date` | Дата создания сделки | Старт сделки |
| `deal_stage` | Стадия сделки | Подстадия |
| `days_since_deal` | Количество дней с создания сделки | Срок сделки |
| `tb` | ТБ | Территориальный банк |
| `label` | Метка | Текстовая метка |
| `change_conditions` | _Изменение условий | Флаг 0/1 |
| `data_entry` | _Ввод данных | Флаг 0/1 |
| `efs_flag` | ЕФС флаг | Флаг 0/1 |

**Пример переименования колонки в другом источнике:**

```json
"columns": {
  "lead_id": "ID ПрПр",
  "days_on_stage": "Дней на стадии"
}
```

### `required_column_keys`

Какие ключи из `columns` **обязательны** при загрузке. Отсутствие → ошибка с указанием файла.

```json
"required_column_keys": ["report_date", "lead_id", "product_group", "product", "tb"]
```

> Оптимизация `read_only_required_columns` читает **только эти колонки**, но **все строки** листа сохраняются.

---

## 5. Excel (`excel`)

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `sheet_name` | string | `Sheet1` | Имя листа |
| `table_name` | string | `Base` | Именованная таблица Excel |
| `table_auto` | bool | `true` | Сначала таблица `table_name`, иначе весь лист |
| `engine` | string | `openpyxl` | Движок pandas |
| `na_values` | array | `[""]` | Что считать пустым |

### `category_markers`

Маркеры в **имени файла** (не влияют на аналитику, служебное поле):

```json
"category_markers": {
  "for_sale": "К ПРОДАЖЕ",
  "in_work": "В РАБОТЕ",
  "unknown": "UNKNOWN"
}
```

**Пример без именованной таблицы:**

```json
"excel": {
  "sheet_name": "Sheet1",
  "table_auto": false
}
```

---

## 6. Обработка (`processing`)

| Ключ | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `empty_stage_values` | array | `["", "-", "nan", "None"]` | Пустая «Стадия сделки» |
| `dedup_same_date_agg` | string | `"max"` | На одну дату + стадию: `max` дней |
| `pick_across_dates` | string | `max_days_then_latest_report_date` | Между датами отчёта |
| `audit_row_counts` | bool | `true` | Аудит: не терять строки молча |
| `duration_fallback_to_columns` | bool | `true` | При `dates`: если дата пуста → колонка дней |

**Правило полноты данных:**

- Строки **не удаляются** при оптимизации
- Исключение — **включённые фильтры** в `filters`
- Записи без срока **остаются** в анализе (метрики могут быть пустыми)

---

## 7. Анализ (корневые параметры)

### `duration_source`

| Значение | Описание |
|----------|----------|
| `"columns"` | Сроки из колонок «Количество дней…» |
| `"dates"` | Расчёт по датам; при пустых датах — fallback на колонки (если включён) |

```json
"duration_source": "columns"
```

### `stage_analysis_mode`

| Значение | Описание |
|----------|----------|
| `"status"` | Только «Текущий статус» |
| `"substages"` | Только «Стадия сделки» (не «-») |
| `"both"` | Оба уровня — две группы записей |

```json
"stage_analysis_mode": "both"
```

### `percentiles`

Список перцентилей для сводки. Для каждого P и каждой метрики (`days_on_stage`, `days_since_deal`) считаются **четыре колонки**:

| Суффикс | Заголовок Excel (пример P=20) | Смысл |
|---------|-------------------------------|-------|
| `_days` | П20 дней | Срок на границе нижних p% лидов (целое) |
| `_count` | П20 лидов | Сколько лидов вошло в нижние p% |
| `_min` | П20 мин | Минимальный срок среди этих лидов |
| `_max` | П20 макс | Максимальный срок среди этих лидов |

**Метод расчёта (эмпирическая шкала):**

1. Все сроки лидов в группе округляются до **целых дней**.
2. Сроки сортируются по возрастанию (вертикаль — дни, горизонталь — накопленное число лидов).
3. Берутся нижние `ceil(p/100 × N)` лидов (минимум 1).
4. **Значение перцентиля** — срок последнего лида в этой доле (граница p% по шкале).
5. **min/max** — среди тех же лидов, что вошли в нижние p%.

Пример: 10 лидов со сроками 10…100 дней, P20 → 2 лида (10 и 20 дней) → П20 дней = 20, П20 лидов = 2, П20 мин = 10, П20 макс = 20.

```json
"percentiles": [20, 50, 80]
```

Квартили:

```json
"percentiles": [25, 50, 75]
```

Заголовки колонок перцентилей настраиваются в `output.percentile_column_labels` (шаблон `{p}` — число перцентиля).

### `parallel_workers`

| Значение | Поведение |
|----------|-----------|
| `0` | Авто: `CPU − reserve_cpu_cores`, но ≤ `max_parallel_workers` |
| `1` | Последовательно (щадящий режим) |
| `N` | Ровно N процессов |

```json
"parallel_workers": 2
```

### `excel_theme`

| Значение | Описание |
|----------|----------|
| `"green_red"` | Min зелёный, max красный, autofilter, freeze |
| `"minimal"` | Без цветовой раскраски |

---

## 8. Производительность (`performance`)

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `max_parallel_workers` | `4` | Потолок процессов (не вешать ПК) |
| `reserve_cpu_cores` | `1` | Ядра для ОС при авто-расчёте |
| `read_only_required_columns` | `true` | Читать только нужные **колонки** (все **строки** сохраняются) |
| `downcast_numeric` | `true` | Уменьшить типы **флагов** (сроки не трогаются) |
| `free_memory_between_stages` | `true` | `gc.collect()` между этапами |

**Слабый ПК / работа параллельно с другими задачами:**

```json
"performance": {
  "max_parallel_workers": 2,
  "reserve_cpu_cores": 2,
  "read_only_required_columns": true,
  "free_memory_between_stages": true
},
"parallel_workers": 1
```

**Мощный сервер:**

```json
"performance": {
  "max_parallel_workers": 8,
  "reserve_cpu_cores": 1
},
"parallel_workers": 0
```

---

## 9. Прогресс (`progress`)

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `enabled` | `true` | Вывод этапов в консоль + лог |
| `log_every_seconds` | `3` | Интервал heartbeat при долгих операциях |

```json
"progress": {
  "enabled": true,
  "log_every_seconds": 5
}
```

Пример вывода:

```
▶ Этап: Загрузка Excel — 22 файл(ов), workers=3
  … [5/22] Канбан ББ (...).xlsx: 52,341 строк за 45.2 сек
✓ Загрузка: 1,124,500 строк из 22 файлов — полный объём
```

---

## 10. Даты (`dates`)

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `dayfirst` | `true` | dd.mm.yyyy при неоднозначности |
| `excel_origin` | `1899-12-30` | Origin для Excel serial number |
| `formats` | см. config | Доп. strptime-форматы |
| `empty_values` | см. config | «Нет даты» → NaT |

**Пример для US-формата:**

```json
"dates": {
  "dayfirst": false,
  "formats": ["%m/%d/%Y", "%Y-%m-%d"],
  "empty_values": ["", "-", "N/A", "null"]
}
```

Поддерживается:

- Excel-числа (serial date)
- `27.08.2026`, `2026-08-27`
- Пустые / `-` / `N/A` → NaT (строка не удаляется)

---

## 11. Агрегация (`aggregation`)

### `group_keys`

Ключи группировки статистики. Значения `product_group`, `product`, `tb` маппятся на `columns`.

```json
"group_keys": [
  "product_group",
  "product",
  "analysis_level",
  "current_status",
  "deal_stage",
  "stage_key"
]
```

### `metrics`

```json
"metrics": ["days_on_stage", "days_since_deal"]
```

---

## 12. Выход (`output`)

| Ключ | Описание |
|------|----------|
| `report_prefix` | Префикс: `{prefix}_{timestamp}.xlsx` |
| `timestamp_format` | strftime, напр. `%Y%m%d_%H%M%S` |
| `excel_sheets.summary` | Лист «Сводная» (все ТБ) |
| `excel_sheets.overall` | Лист «Общий» |
| `excel_max_sheet_name_length` | Лимит Excel 31 символ |
| `column_labels` | Заголовки колонок в Excel |
| `excel_format` | freeze, ширина, форматы чисел, цвета |

**Пример другого префикса:**

```json
"output": {
  "report_prefix": "kanban_prod",
  "timestamp_format": "%Y%m%d"
}
```

### `excel_format.colors`

HEX без `#`: min — зелёный, max — красный.

```json
"colors": { "min": "C6EFCE", "max": "FFC7CE" }
```

---

## 13. Фильтры (`filters`)

Каждый фильтр — объект. Включённые фильтры объединяются через **AND**.

### Бинарные фильтры

`change_conditions`, `data_entry`, `efs_flag`:

| Поле | Описание |
|------|----------|
| `enabled` | `true` / `false` |
| `column_key` | Ключ из `columns` |
| `value` | Ожидаемое значение (обычно `1`) |

```json
"efs_flag": {
  "enabled": true,
  "column_key": "efs_flag",
  "value": 1
}
```

### Текстовый фильтр

`strategy_label`:

| Поле | Описание |
|------|----------|
| `enabled` | `true` / `false` |
| `column_key` | `"label"` |
| `contains` | Подстрока в «Метка» |
| `case_sensitive` | `false` — без учёта регистра |

```json
"strategy_label": {
  "enabled": true,
  "column_key": "label",
  "contains": "Стратегия",
  "case_sensitive": false
}
```

> Без включённых фильтров анализируются **все** строки.

---

## 14. Логирование (`logging`)

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `logger_name` | `kanban` | Имя логгера |
| `info_file_prefix` | `INFO_kanban` | Файл INFO |
| `debug_file_prefix` | `DEBUG_kanban` | Файл DEBUG |
| `hour_format` | `%Y%m%d_%H` | Час в имени лога |

Файлы: `log/INFO_kanban_20260831_12.log`

---

## 15. Аудит данных

При `processing.audit_row_counts: true` в лог пишется:

- число строк на каждом этапе;
- **предупреждение**, если строки пропали без причины;
- проверка, что все `ID ПрПр` попали в `lead_stage_records`.

```
Аудит [фильтрация]: 43,776 строк (без изменений)
Аудит [лиды]: все 13,182 уникальных ID ПрПр учтены
```

---

## 16. Минимальный config

```json
{
  "mode": "test",
  "test_files": ["2ГОСБ1ТБ.xlsx"]
}
```

Остальное подставится из `src/settings.py`.

---

## 17. Связанные документы

- [README.md](../README.md) — обзор и запуск
- [DEPLOY.md](DEPLOY.md) — перенос на другой ПК
- [BT_KANBAN.md](BT_KANBAN.md) — бизнес-требования
