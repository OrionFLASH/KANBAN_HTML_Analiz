# Справочник config.json

Полное описание параметров конфигурации сервиса KANBAN HTML Analiz (версия **1.0.7**).

Отсутствующие ключи автоматически дополняются значениями по умолчанию из `src/settings.py`.

---

## Оглавление

1. [Режим работы](#1-режим-работы) — `mode`
2. [Пути](#2-пути-paths) — `paths`
3. [Списки файлов](#3-списки-файлов) — `test_files`, `prod_files`
4. [Колонки Excel](#4-колонки-excel-columns) — `columns`, `required_column_keys`
5. [Excel](#5-excel-excel) — `excel`
6. [Обработка](#6-обработка-processing) — `processing`
7. [Анализ](#7-анализ-корневые-параметры) — `duration_source`, `stage_analysis_mode`, `product_analysis_mode`, `percentiles`, `stages_order`, `dashboard`, `parallel_workers`, `excel_theme`
8. [Производительность](#8-производительность-performance) — `performance`
9. [Прогресс](#9-прогресс-progress) — `progress`
10. [Даты](#10-даты-dates) — `dates`
11. [Агрегация](#11-агрегация-aggregation) — `aggregation`
12. [Выход](#12-выход-output) — `output`
13. [Фильтры](#13-фильтры-filters) — `filters` (Excel + JSON + HTML)
14. [Аналитика менеджеров](#14-аналитика-менеджеров-manager_analytics-колонка-km) — `manager_analytics`
15. [Логирование](#15-логирование-logging) — `logging`
16. [Аудит данных](#16-аудит-данных)
17. [Минимальный config](#17-минимальный-config)

---

## Карта корневых ключей

| Ключ | Тип | Назначение |
|------|-----|------------|
| `mode` | `"test"` \| `"prod"` | Откуда брать Excel |
| `paths` | object | Каталоги input/output/log |
| `columns` | object | Внутренний ключ → имя колонки Excel |
| `required_column_keys` | array | Обязательные колонки при загрузке (и список для `read_only_required_columns`) |
| `excel` | object | Лист, таблица Base, движок |
| `processing` | object | Дедупликация, аудит, fallback сроков |
| `performance` | object | Workers, память, compact JSON |
| `progress` | object | Консольный прогресс и тайминг |
| `dates` | object | Парсинг дат |
| `aggregation` | object | Ключи группировки и метрики |
| `output` | object | Имена файлов, листы Excel, оформление |
| `logging` | object | Файлы логов |
| `test_files` | array | Имена xlsx для test |
| `prod_files` | array | 22 prod-файла |
| `duration_source` | `"columns"` \| `"dates"` | Источник сроков |
| `stage_analysis_mode` | `"status"` \| `"substages"` \| `"both"` | Уровень стадий |
| `product_analysis_mode` | `"group_product"` \| `"group_only"` | **Только Excel** — детализация по продуктам |
| `percentiles` | array[int] | Список перцентилей (20, 50, 80…) |
| `stages_order` | array[str] | Порядок стадий в матрице |
| `dashboard` | object | Дашборд, матрица, предрасчёт filter_slices |
| `manager_analytics` | object | TOP по участникам команды / КМ; `team_files`, `rank_by_team`, `rank_selection` |
| `parallel_workers` | int | 0 = авто, 1 = последовательно |
| `excel_theme` | `"green_red"` \| `"minimal"` | Оформление Excel |
| `html_json` | object | По умолчанию monolith (один JSON для file://); split — опционально |
| `filters` | object | Pipeline-фильтры; см. §13 (`html_slice`, `enabled`) |

### Excel vs JSON vs HTML — три контекста одного `config.json`

| Контекст | Что управляет config | Где применяется |
|----------|----------------------|-----------------|
| **Excel** | `filters.*.enabled: true` — AND; `product_analysis_mode`; config-only фильтры (`html_slice: false`) | Листы сводки и **Менеджеры** (листы «Матрица» и «Графики» не создаются) |
| **JSON (основной)** | `dashboard.precompute_html_filter_slices`; фильтры с `html_slice: true` (не `enabled`) | `visualizations.filter_slices` — комбинации 2^N (N = число HTML-фильтров); база данных — после config-only фильтров |
| **JSON (менеджеры)** | `manager_analytics.*`, `rank_by_team`, `team_files`, `rank_selection`; колонки `km`, `vks`, `label`, `deal_id`, `inn`, `client` | Блок `managers` в monolith JSON: `records` (+`team`), `top_by_tb`, `charts` (отдельный файл — только при `write_separate_managers_json: true`, в UI не загружается) |
| **HTML** | Pipeline ВКЛ/ВЫКЛ; зафиксированные фильтры; матрица (дни + ↑/↓ порога); вкладка «Менеджеры» — опционально (`show_managers_tab`) | Локальный дашборд `HTML/` (file://), один JSON |

> **`enabled` в `filters` влияет на Excel и на config-only срез (`html_slice: false`).** HTML переключает готовые срезы JSON (`html_slice: true`) без пересчёта pipeline. Копии `*_latest*` и запись в `HTML/data/` **не создаются** — JSON загружается вручную.

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
    "efs_flag": { "enabled": true, "column_key": "efs_flag", "value": 1, "html_slice": false },
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
| `km` | КМ | ФИО менеджера (аналитика менеджеров / команда) |
| `vks` | ВКС | ФИО ВКС (опционально; `optional_column_keys`) |
| `deal_id` | ID сделки | Идентификатор сделки (зависшие сделки в карточке) |
| `inn` | ИНН | ИНН клиента |
| `client` | Клиент | Наименование клиента |

**Пример переименования колонки в другом источнике:**

```json
"columns": {
  "lead_id": "ID ПрПр",
  "days_on_stage": "Дней на стадии"
}
```

### `required_column_keys`

Какие ключи из `columns` **обязательны** при загрузке. Отсутствие → ошибка с указанием файла.

При `performance.read_only_required_columns: true` (по умолчанию) из Excel читаются **только** эти колонки — все строки листа сохраняются.

```json
"required_column_keys": [
  "report_date", "lead_id", "product_group", "product",
  "work_start_date", "current_status", "days_on_stage",
  "deal_created_date", "deal_stage", "days_since_deal",
  "tb", "change_conditions", "data_entry", "efs_flag", "label", "km",
  "deal_id", "inn", "client"
]
```

| Правило | Описание |
|---------|----------|
| Базовый набор | Все ключи аналитики + фильтры + `label` |
| **`km`** | Обязателен, если `manager_analytics.enabled: true` и в Excel есть колонка КМ. Без `km` в списке колонка **не загрузится** при `read_only_required_columns`, и аналитика менеджеров будет пропущена |
| **`label`** | Нужен для `rank_selection.strategy_filter` (отбор TOP по метке «Стратегия» / «2026»). Без `label` в списке фильтр метки не применяется |
| **`deal_id`**, **`inn`**, **`client`** | ID сделки, ИНН и наименование клиента — для `exceedances` и `hotspots[].stuck_items` (только при превышении P80) |
| **`vks`** | Колонка ВКС — через `optional_column_keys` (читается если есть в файле, без ошибки если нет) |
| **`client_display`** | Сокращение юрформ в имени клиента (ООО, АО, ИП…); список `abbreviations`: `{match, replace}`; применяется в JSON и UI |
| Отключить менеджеров | `manager_analytics.enabled: false` — `km` можно убрать из списка для экономии памяти |

### `optional_column_keys`

Колонки, которые **желательно** загрузить, но отсутствие в Excel **не ошибка**. При `read_only_required_columns: true` они добавляются к `usecols`, если есть в шапке файла.

```json
"optional_column_keys": ["vks"]
```

> Оптимизация **не отбрасывает строки** — только ограничивает набор колонок при чтении.

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
| `group_only_product_label` | string | `"—"` | Подпись в колонке «Продукт» при `product_analysis_mode: group_only` |
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
| `"status"` | Только «Текущий статус» (**рекомендуется**). В meta: `analysis_level_locked: true`, `analysis_level: "status"` — фильтр уровня в HTML **скрыт** |
| `"substages"` | Только «Стадия сделки» (не «-»). Уровень тоже зафиксирован (`analysis_level: "substage"`) |
| `"both"` | Оба уровня — в HTML доступен фильтр «Уровень анализа» |

```json
"stage_analysis_mode": "status"
```

При `status` / `substages` в UI вместо селекта показывается locked-чип (как у агрегации).
### `product_analysis_mode`

Режим детализации по продуктам:

| Значение | Описание |
|----------|----------|
| `"group_product"` | **По умолчанию.** Полный анализ: **ГРУППА + ПРОДУКТ** |
| `"group_only"` | Только **ГРУППА** — расчёт без разреза по продуктам |

```json
"product_analysis_mode": "group_product"
```

Только по группам:

```json
"product_analysis_mode": "group_only"
```

При `group_only` трекинг и агрегация идут по `лид × группа × ТБ × стадия`; в Excel/HTML строки матрицы — **группы**. Подпись в колонке «Продукт»: `processing.group_only_product_label` (по умолчанию `—`).

**Важно:** `product_analysis_mode` в `config.json` управляет только **Excel**. В JSON при каждом `run.py` экспортируются **оба** среза:

| Ключ JSON | Содержимое |
|-----------|------------|
| `statistics.group_product` / `statistics.group_only` | Агрегаты overall, by_tb, tb_sheets |
| `visualizations.aggregations.group_product` | `distribution_series`, `pivot_flat` по продуктам |
| `visualizations.aggregations.group_only` | То же по группам |
| `meta.excel_product_analysis_mode` | Режим Excel из config |
| `meta.json_aggregation_modes` | `["group_product", "group_only"]` |

HTML-дашборд: агрегация **зафиксирована** в config (`aggregation_locked`); переключатель в UI заменён locked-чипом «По продуктам» / «По группам».

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

**Только для P80 (Excel):** дополнительные колонки:

| Суффикс | Смысл |
|---------|--------|
| `km_count` | Число **уникальных КМ** со сроком **≥** П80 |
| `le_count` | Число лидов со сроком **≤** П80 |
| `gt_count` | Число лидов со сроком **>** П80 |

Шаблоны заголовков — в `output.percentile_column_labels`. В HTML-матрице `leads_le` / `leads_gt` показываются справа от дней (↑ красный / ↓ бирюзовый).

### `stages_order`

Порядок статусов в сводной матрице Excel/HTML (строки/колонки стадий):

```json
"stages_order": [
  "К ПРОДАЖЕ",
  "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ",
  "ОБСУЖДЕНИЕ УСЛОВИЙ",
  "РЕАЛИЗАЦИЯ СДЕЛКИ",
  "АКТИВАЦИЯ ПРОДУКТА",
  "ПРОДАЖА ЗАВЕРШЕНА"
]
```

### `dashboard`

Настройки дашборда и листа «Матрица»:

| Ключ | Описание |
|------|----------|
| `all_tb_label` | Внутренний ключ «все ТБ» в JSON (`__ALL__`) |
| `all_tb_display` | Подпись в UI и Excel (`ВСЕ ТБ`) |
| `default_tb` | ТБ по умолчанию |
| `default_metric` | `days_on_stage` или `days_since_deal` |
| `default_indicator` | `min`, `max`, `p20`, `p50`, `p80` |
| `excel_max_chart_series` | Число графиков на листе Excel |
| `max_chart_series` | Макс. линий на одном HTML-графике |
| `precompute_html_filter_slices` | `true` — все комбинации HTML-фильтров в JSON (пустые пропускаются) |
| `show_managers_tab` | `false` — вкладка «Менеджеры» в HTML **скрыта** (по умолчанию). `true` — показать; данные только из блока `managers` в том же monolith JSON (отдельная загрузка файла менеджеров в UI **не поддерживается**) |
| `html_json` | Экспорт для HTML: monolith/split, compact, прореживание серий |

### `dashboard.html_json` — оптимизация для prod

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `bundle_mode` | `"monolith"` | `"monolith"` — один JSON со срезами (+ managers); `"split"` — каталог `*_html/slices` (нужен HTTP) |
| `compact` | `true` | JSON без indent (меньше размер) |
| `include_statistics` | `false` | Блок `statistics` (тяжёлый; UI не требует) |
| `include_dimensions` | `true` | Справочники в JSON |
| `max_distribution_points` | `800` | Прореживание `days_sorted` в сериях |
| `slices_subdir` | `"slices"` | Только для `split` |
| `write_monolith_archive` | `false` | Для split — slim-указатель; для monolith не используется |
| `embed_managers` | `true` | Вложить блок `managers` в основной JSON |
| `write_separate_managers_json` | `false` | Дополнительно писать `kanban_report_managers_*.json` |

**Структура выхода после `run.py` (monolith, по умолчанию):**

```
OUT/
  kanban_report_YYYYMMDD_HHMMSS.xlsx      # Excel
  kanban_report_YYYYMMDD_HHMMSS.json      # ← ЭТОТ файл грузить в UI
```

**Split-bundle (опционально):** `bundle_mode: "split"` — каталог `*_html/` + lazy-load; **нужен HTTP к slices/** (на корпоративных ПК без серверов не использовать).

**Monolith (по умолчанию, file://):** один файл `OUT/kanban_report_{timestamp}.json` — внутри `filter_slices` и блок `managers`. Каталоги `*_html` **не** создаются. В UI выбираете **только этот файл**.

Запуск UI: открыть `HTML/index.html` в браузере (двойной клик / file://) — сервер не нужен.

**Менеджеры:** JSON содержит **полные** `records` (все лиды×стадии с меткой) **только по актуальной дате отчёта** (`use_latest_report_date`); `exceedances` — только отклонения; `top_by_tb` / `top_by_tb_grouped` — предрасчёт по `rank_selection`; в UI TOP пересчитывается по фильтрам.

JSON содержит блок `visualizations`:

| Ключ | Описание |
|------|----------|
| `distribution_series` | Кривые «лиды × дни» (`days_sorted` или `points`) |
| `distribution_format` | `days_sorted` или `points` |
| `pivot_flat` | Длинный формат для матрицы (HTML строит матрицу из него) |
| `pivot_matrices` | Предрасчёт (по умолчанию пусто, см. `performance.precompute_pivot_matrices`) |
| `default_pivot_matrix` | Срез по умолчанию |
| `default_view` | `{ tb, metric, indicator, aggregation, filter_slice }` для UI |
| `filter_catalog` | Описание фильтров из `config.filters` для HTML |
| `filter_slices` | Предрасчитанные срезы: ключ `none` или `name1+name2` → `{ aggregations, record_count, series_count }` |
| `aggregations` | Срез по умолчанию (`none`) — совместимость со старым HTML |

Структура `filter_slices` (без дублирования `stage_order` / `metrics`):

```json
"filter_slices": {
  "none": {
    "active_filters": [],
    "label": "Без pipeline-фильтров",
    "record_count": 13182,
    "series_count": 308,
    "aggregations": {
      "group_product": { "distribution_series": [], "pivot_flat": [] },
      "group_only": { "distribution_series": [], "pivot_flat": [] }
    }
  },
  "change_conditions+strategy_label": { "...": "..." }
}
```

Пустые комбинации в JSON не попадают. Число срезов: **2^N**, где N — фильтры с `html_slice: true` (по умолчанию 4: изменение условий, ввод данных, два варианта метки; `efs_flag` с `html_slice: false` **не входит**).

В `meta` JSON дополнительно:

| Ключ | Описание |
|------|----------|
| `filter_catalog` | Каталог HTML-фильтров (подписи, column_key, type) |
| `filter_slice_keys` | Список ключей срезов в JSON |
| `excel_product_analysis_mode` | Режим Excel из config |
| `json_aggregation_modes` | `["group_product", "group_only"]` |
| `filters_applied` | Фильтры с `enabled=true` в config (только Excel) |
| `filters_active` | `true`, если Excel-фильтры включены в config |
| `config_locked_filters` | Список фильтров с `html_slice: false` для блока «Зафиксированные фильтры» в UI |
| `analysis_level_locked` | `true` при `stage_analysis_mode` ∈ {status, substages} |
| `analysis_level` | `"status"` / `"substage"` / `null` |
| `excluded_stages` | Стадии, убранные из анализа (`exclude_equals`, напр. «К ПРОДАЖЕ») |
| `stages_order` | Эффективный порядок стадий (без `excluded_stages`) |
| `data_scope_note` | Excel vs JSON vs HTML |

В `dimensions.filter_dimensions` — фактические значения колонок фильтров в отфильтрованном срезе.

### HTML-дашборд (`HTML/`)

Запуск: `cd HTML && python -m http.server 8080` — загрузите manifest или monolith через левую панель.

| Возможность | Описание |
|-------------|----------|
| Загрузка JSON | Кнопка выбора файла; после загрузки — **Сбросить** (очистка данных) |
| Агрегация / уровень | Locked-чипы из config (`product_analysis_mode`, `stage_analysis_mode`) |
| Pipeline-фильтры | Кнопки ВКЛ/ВЫКЛ по `filter_catalog` (`html_slice: true`) |
| Зафиксированные фильтры | Чипы config-only (`html_slice: false`) — без переключателей |
| Мультивыбор | ТБ, группы, продукты — чекбоксы, поиск |
| Графики линий | «По продуктам/группам» и «По ТБ» |
| Графики КМ | Bar-chart нарушений P80 (из блока managers) |
| Матрица | ⅔ ячейки — дни; ⅓ — ↑ выше / ↓ ≤ порога; сортировка по клику на стадию |
| Менеджеры | TOP-3 по ТБ (участники команды при `rank_by_team`); роли + состав команды на карточке |

Файлы: `index.html`, `css/dashboard.css`, `js/data.js`, `js/icons.js`, `js/multi-filter.js`, `js/managers.js`, `js/charts.js`, `js/pivot.js`, `js/app.js`.

Split-bundle: manifest в `OUT/kanban_report_{timestamp}_html/`; срезы — в подкаталоге `slices/`. Для lazy-load срезов manifest и slices должны быть доступны по HTTP из одной базы URL (сервер из каталога `_html/`).

### Режимы графика (HTML, селект «Режим линий»)

| Значение | Тип | Источник данных |
|----------|-----|-----------------|
| `by_product` | line | Основной JSON — `distribution_series` |
| `by_tb` | line | Основной JSON — `distribution_series` |
| `km_by_tb` | bar | Блок `managers.charts.by_tb` + `charts.facts` в основном JSON |
| `km_by_segment` | bar | Блок `managers.charts.facts` (группы/продукты по «Агрегация строк») |

**Нарушение КМ:** уникальный КМ, у которого есть сделки со сроком **строго больше** P80 для той же группы × продукта × стадии. На bar-chart — **число таких КМ**; в tooltip — число сделок с превышением.

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
| `compact_distribution_series` | `true` | В JSON серии как `days_sorted` вместо `{lead_index, days}` — меньше размер, те же данные |
| `precompute_pivot_matrices` | `false` | Не дублировать матрицы в JSON (HTML строит из `pivot_flat`) |

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
| `show_timing_summary` | `true` | Сводная таблица времени по этапам в конце pipeline |

```json
"progress": {
  "enabled": true,
  "log_every_seconds": 5,
  "show_timing_summary": true
}
```

Пример вывода:

```
▶ Этап: Загрузка Excel — 22 файл(ов), workers=3
  … [5/22] Канбан ББ (...).xlsx: 52,341 строк за 45.2 сек
✓ Загрузка: 1,124,500 строк из 22 файлов — полный объём (48.3 сек)
⏱ Этап «Загрузка Excel»: 48.3 сек — Загрузка: 1,124,500 строк...

════════════════════════════════════════
Сводка времени обработки
────────────────────────────────────────
  Загрузка Excel              48.3 сек  ( 76%)
  Трекинг лидов по стадиям     6.1 сек  ( 10%)
  ...
────────────────────────────────────────
  ИТОГО                       63.4 сек
════════════════════════════════════════
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

- Колонки, уже прочитанные openpyxl как **datetime64** (не ломаются при повторном parse)
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
| `excel_sheets.managers` | Лист «Менеджеры» (топ КМ + зоны превышения; колонка «Топ зон» — перенос строк) |
| `excel_sheets.matrix` / `charts` | Устаревшие ключи; листы **не создаются** (графики и матрица — только в HTML) |
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

Каждый фильтр — объект в `config.filters`. Имена ключей (`change_conditions`, `strategy_label` …) используются как идентификаторы в `filter_catalog` и ключах `filter_slices` (только для `html_slice: true`).

### Общие поля фильтра

| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `enabled` | bool | `false` | Применять фильтр в Excel (AND с другими `enabled: true`) |
| `column_key` | string | — | Ключ из `columns` |
| `html_slice` | bool | `true` | `false` — только config (без UI и без комбинаций в JSON); база данных для срезов фильтруется до комбинаций |
| `value` | int | `1` | Для бинарных фильтров: ожидаемое значение колонки |
| `contains` | string | — | Подстрока в текстовой колонке |
| `contains_all` | array | — | Все подстроки обязательны |
| `case_sensitive` | bool | `false` | Учёт регистра для текстовых фильтров |
| `exclusive_group` | string | — | Группа взаимоисключения в HTML (варианты метки) |
| `filter_mode` | string | `"include"` | `"exclude"` — исключить строки |
| `exclude_contains` | string | — | Подстрока для исключения |
| `exclude_equals` | string | — | Точное равенство (напр. «К ПРОДАЖЕ» в текущем статусе) |
| `also_column_keys` | array | — | Доп. колонки для OR-проверки exclude |
| `default_active` | bool | `false` | В HTML включён по умолчанию |
| `ui_group` | string | — | Группа переключателей в левой панели |

### Роли поля `enabled`

| `enabled` | Excel | JSON `filter_slices` | HTML |
|-----------|-------|----------------------|------|
| `false` | Фильтр **не** применяется | Срез предрасчитывается (если `html_slice: true`) | Доступен переключателем ВКЛ/ВЫКЛ |
| `true` + `html_slice: true` | Строки фильтруются | Комбинации в JSON | Переключатель ВКЛ/ВЫКЛ |
| `true` + `html_slice: false` | Строки фильтруются | База всех срезов уже отфильтрована; отдельных ключей `efs_flag` в JSON **нет** | **Не показывается** в UI |

В `meta.filters_applied` JSON попадают **только** фильтры с `enabled: true` (отражение Excel-среза).

### Бинарные фильтры

`change_conditions`, `data_entry` — переключатели в HTML и комбинации в JSON.

`efs_flag` — **только config** (`html_slice: false`): в UI и `filter_slices` не участвует; при `enabled: true` отбирает строки с заданным `value` (обычно `1`) **до** построения JSON и Excel. При `enabled: false` (по умолчанию) строки с `0` и `1` не отсекаются.

| Поле | Описание |
|------|----------|
| `enabled` | `true` / `false` |
| `column_key` | Ключ из `columns` |
| `value` | Ожидаемое значение (обычно `1`) |
| `html_slice` | `false` — без UI и без комбинаций в JSON (`efs_flag`) |

```json
"efs_flag": {
  "enabled": true,
  "column_key": "efs_flag",
  "value": 1,
  "html_slice": false
}
```

### Фильтры по метке (взаимоисключающие в HTML)

Два варианта для колонки «Метка». В **Excel** включается один из них через `enabled: true`. В **JSON** предрасчитываются оба (+ комбинации с другими фильтрами). В **HTML** — кнопки ВКЛ/ВЫКЛ; одновременно активен не более одного варианта метки.

| Имя | Условие |
|-----|---------|
| `strategy_label` | Метка содержит «Стратегия» (без учёта регистра) |
| `strategy_label_2026` | Метка содержит **и** «Стратегия», **и** «2026» (без учёта регистра) |

| Поле | Описание |
|------|----------|
| `enabled` | `true` / `false` (Excel) |
| `column_key` | `"label"` |
| `contains` | Одна подстрока (`strategy_label`) |
| `contains_all` | Список подстрок, все обязательны (`strategy_label_2026`) |
| `case_sensitive` | `false` — без учёта регистра |
| `exclusive_group` | `"strategy_label"` — группа взаимоисключения в HTML |

```json
"strategy_label": {
  "enabled": false,
  "column_key": "label",
  "contains": "Стратегия",
  "case_sensitive": false,
  "exclusive_group": "strategy_label"
},
"strategy_label_2026": {
  "enabled": false,
  "column_key": "label",
  "contains_all": ["Стратегия", "2026"],
  "case_sensitive": false,
  "exclusive_group": "strategy_label"
}
```

> Без включённых фильтров (`enabled: false` у всех) в Excel анализируются **все** строки. HTML по умолчанию показывает срез `none`.

HTML переключает срезы из `visualizations.filter_slices` кнопками **ВКЛ/ВЫКЛ** по `filter_catalog`. Варианты метки с одним `exclusive_group` **взаимоисключающие** в UI.

### Исключение терминальных стадий (`deal_stage` / `current_status`)

Строки с терминальными подстроками **не участвуют** в расчёте дней на стадиях, min/max, перцентилей, JSON-срезах и аналитике КМ.

| Ключ фильтра | Колонки | Подстрока (`exclude_contains`) | По умолчанию Excel + HTML |
|--------------|---------|-------------------------------|---------------------------|
| `exclude_deal_otkaz` | `deal_stage` + `current_status` (`also_column_keys`) | `отказ` | **ВКЛ** |
| `exclude_deal_zakryta` | `deal_stage` | `закрыта` | **ВКЛ** |
| `exclude_deal_zaklyuchen` | `deal_stage` | `заключен` | **ВКЛ** |

Регистр не учитывается (`case_sensitive: false`). **Пустая стадия** (`-`, `""`, `nan`) **всегда остаётся** в расчёте — исключаются только строки с непустой стадией и совпадением подстроки.

```json
"exclude_deal_otkaz": {
  "enabled": true,
  "column_key": "deal_stage",
  "also_column_keys": ["current_status"],
  "filter_mode": "exclude",
  "exclude_contains": "отказ",
  "case_sensitive": false,
  "html_slice": true,
  "default_active": true,
  "ui_group": "terminal_deal_stages"
}
```

- **`also_column_keys`:** доп. колонки для OR-проверки той же подстроки (для «отказ» — ещё «Текущий статус»).
- **Excel:** `enabled: true` — исключение при `run.py` (статистика, менеджеры).
- **HTML:** три переключателя в группе «Исключить терминальные стадии»; **ВКЛ** = исключать; **ВЫКЛ** = вернуть такие строки в расчёт.
- **JSON менеджеров:** лиды/сделки с терминальными стадиями **не попадают** в `records` / `exceedances` (фильтр на этапе pipeline).

**Гранularity:** отсекается **только конкретная строка** (лид × дата отчёта). Тот же `ID ПрПр` на других датах отчёта или других стадиях **остаётся** в расчёте min/max/перцентилей и у менеджеров.

Срез по умолчанию в UI: все три исключения **ВКЛ** (ключ вида `exclude_deal_otkaz+exclude_deal_zakryta+exclude_deal_zaklyuchen`).

> В текущем `config.json` терминальные `exclude_deal_*` обычно с `html_slice: false` — они **зафиксированы** в config и показываются в блоке «Зафиксированные фильтры», без переключателей в pipeline.

### Исключение статуса «К ПРОДАЖЕ» (`exclude_current_for_sale`)

Опциональный config-only фильтр: из анализа убираются лиды с **текущим статусом** ровно «К ПРОДАЖЕ»; колонка/опция этой стадии исчезает из матрицы и UI.

```json
"exclude_current_for_sale": {
  "enabled": true,
  "column_key": "current_status",
  "filter_mode": "exclude",
  "exclude_equals": "К ПРОДАЖЕ",
  "case_sensitive": false,
  "html_slice": false
}
```

| Поле | Значение |
|------|----------|
| `enabled` | `true` — исключать; `false` — оставить стадию в анализе |
| `exclude_equals` | Точное совпадение (не substring) |
| `html_slice` | `false` — только config; в `meta.excluded_stages` и locked-чипах |

---

## 14. Аналитика менеджеров (`manager_analytics`, колонка `km`)

Менеджер / участник — **ФИО**. При `rank_by_team: true` TOP считается не только по колонке КМ, а по **уникальным участникам команды** зависшего лида.

| Поле | Описание |
|------|----------|
| `enabled` | `true` / `false` |
| `metric` | Метрика срока (обычно `days_on_stage`) |
| `percentile` | Порог перцентиля (обычно `80`) |
| `threshold_scope` | `overall` — порог из общей сводки без ТБ |
| `top_managers_per_tb` | Топ-N в каждом ТБ (по умолчанию `3`) |
| `top_hotspots_per_manager` | Топ зон превышения на карточке (по умолчанию `5`) |
| `top_stuck_items_per_hotspot` | Макс. зависших лидов в одной зоне (по умолчанию `15`) |
| `use_latest_report_date` | `true` — только `max(Дата отчета)` |
| `rank_by_team` | `true` — TOP по участникам команды (нужны `team_files`) |
| `team_files` | Файлы команды лида / сделки (см. ниже) |
| `rank_selection` | Пул отбора TOP (группы, продукты, метка, ЕФС…) |
| `html_include_detail` | Устарело: `records` / `exceedances` всегда в JSON |

### `team_files` — команда лида и сделки

Отдельные Excel (лежат рядом с kanban в `paths.input_*`):

| Ключ | Описание |
|------|----------|
| `enabled` | Включить подгрузку |
| `lead_team.test` / `.prod` | Файлы «Команда л …» — лидер лида (`Лидер = Да` по max дате отчёта на `ID ПрПр`) |
| `deal_team.test` / `.prod` | Файлы «Команда с …» — лидеры сделки (`Лидер = Да` по max дате на `ID сделки`) |
| `leader_values` | Значения «да» для колонки «Лидер» |
| `columns` | Имена колонок файла команды |

**Команда зависшего лида (уникальные ФИО):**

1. Лидер(ы) лида из `lead_team`
2. Лидер(ы) сделки из `deal_team`
3. **КМ** из канбан-файла
4. **ВКС** из канбан-файла (`optional_column_keys`)

Повторы схлопываются; у человека собираются роли: `КМ`, `ВКС`, `Команда лида · …`, `Команда сделки · …`.

**Алгоритм TOP:** перцентили по продукту×стадии → лиды с превышением P80 → разворот по участникам команды → TOP-N по ТБ → на карточке роли и состав команды.

```json
"team_files": {
  "enabled": true,
  "lead_team": { "test": ["тест Команда л ….xlsx"], "prod": [] },
  "deal_team": { "test": ["тест Команда с ….xlsx"], "prod": [] },
  "leader_values": ["Да", "да", "yes", "1"],
  "columns": {
    "report_date": "Дата отчета",
    "lead_id": "ID ПрПр",
    "deal_id": "ID сделки",
    "member": "Участник команды",
    "role": "Роль участника команды",
    "is_leader": "Лидер",
    "tb": "ТБ"
  }
}
```

### `rank_selection` — отбор TOP

Задаёт **пул** групп/продуктов и фильтр метки для расчёта `top_by_tb` (Excel + начальное состояние UI). Полные данные — в `records`; пользователь в UI может сузить выбор.

| Поле | Тип | По умолчанию | Описание |
|------|-----|--------------|----------|
| `product_groups` | string[] | `[]` | Группы в пуле отбора. Пустой массив = **все** группы |
| `products` | string[] | `[]` | Продукты в пуле. Пустой массив = **все** продукты |
| `strategy_filter` | string | `"strategy_2026"` | Фильтр метки (`columns.label`) |
| `efs_flag` | int \| null | `1` | Только лиды с указанным значением ЕФС; `null` — без фильтра |
| `change_conditions` | int \| null | `0` | Только лиды с указанным «Изменение условий»; `null` — без фильтра |

> Если ключ `products` **отсутствует** в config — подставляется дефолтный список из `src/settings.py` (`DEFAULT_RANK_PRODUCTS`, 14 продуктов). Пустой массив `products: []` = **все** продукты.

**`strategy_filter`:**

| Значение | Описание |
|----------|----------|
| `all` | Все метки |
| `strategy` | Метка содержит «Стратегия» (как `filters.strategy_label`) |
| `strategy_2026` | Метка содержит «Стратегия» **и** «2026» |
| `non_strategy` | Метка **без** «Стратегия» |

```json
"rank_selection": {
  "product_groups": [],
  "products": ["Факторинг", "Cash-management"],
  "strategy_filter": "strategy_2026",
  "efs_flag": 1,
  "change_conditions": 0
}
```

> TOP-N — по превышениям P80 в пуле (Excel). JSON: **`records`** — все лиды актуального среза; `client` / `inn` / `deal_id` — **только** у строк с `exceeded: true`; **`exceedances`** — только отклонения; ключ КМ: **`km_tb_key`** = ТБ+КМ. Пороги P80 — из **общей** сводки (все даты отчёта).

**Срез по дате отчёта (`use_latest_report_date: true`):**

- В исходных данных может быть несколько «Дата отчета» (несколько выгрузок в одном файле)
- Для аналитики менеджеров pipeline оставляет только строки с **максимальной** датой
- Общая статистика Excel/JSON **не** ограничивается этим срезом
- В логе: `Менеджеры: актуальная выгрузка YYYY-MM-DD — N → M строк`

**Логика:** для каждой группы × продукт × стадия берётся P80 из overall; лид менеджера **превышает** порог, если срок **строго больше** P80. Считаются превышения по КМ×ТБ (уникальный ключ ТБ+ФИО).

**Hotspots** — зоны превышения с вложенным **`stuck_items[]`**: `lead_id`, `deal_id`, `inn`, `client`, `days_int`, `overshoot`.

**Блок `charts` (в slim и полном JSON):**

| Ключ | Описание |
|------|----------|
| `by_tb[]` | `{ tb, km_with_violations, km_total, violation_deals }` — уникальные КМ с нарушениями по ТБ |
| `facts[]` | `{ tb, km, product_group, product?, stage_key, deals }` — детализация для bar-графиков и фильтров UI |

**Выход:**

| Артефакт | Путь |
|----------|------|
| Excel | Лист «Менеджеры»: место, участник/КМ, ТБ, превышения, **роли**, **команда**, зоны |
| JSON | Блок `managers` в monolith (или `…_managers_*.json`) |
| HTML | Секции по ТБ; карточка с ролями и командой по зависшим лидам |

**Структура JSON менеджеров (кратко):**

```json
{
  "meta": {
    "metric": "days_on_stage",
    "percentile": 80,
    "top_managers_per_tb": 3,
    "top_stuck_items_per_hotspot": 15,
    "use_latest_report_date": true,
    "report_date_snapshot": "2026-08-27",
    "manager_key": "km_tb_key",
    "km_column": "КМ",
    "rank_selection": {
      "product_groups": [],
      "products": ["Факторинг"],
      "strategy_filter": "strategy_2026",
      "efs_flag": 1,
      "change_conditions": 0
    }
  },
  "dimensions": { "product_groups": ["…"], "products": ["…"] },
  "records": [
    {
      "tb": "…", "km": "…", "product_group": "…", "product": "…",
      "stage_key": "В РАБОТЕ", "label": "Стратегия 2026", "lead_id": "…",
      "deal_id": "…", "inn": "7701234567", "client": "ООО Пример",
      "days_int": 45, "threshold_days": 30, "exceeded": true
    }
  ],
  "exceedances": [
    {
      "tb": "…", "km": "…", "lead_id": "…", "deal_id": "…", "inn": "7701234567", "client": "ООО Пример",
      "product_group": "…", "product": "…", "stage_key": "В РАБОТЕ",
      "days_int": 45, "threshold_days": 30, "overshoot": 15
    }
  ],
  "top_by_tb": [
    {
      "tb": "…",
      "rank": 1,
      "km": "…",
      "exceedance_count": 12,
      "total_leads": 340,
      "hotspots": [
        {
          "product_group": "…",
          "product": "…",
          "stage_key": "В РАБОТЕ",
          "exceedance_count": 5,
          "threshold_days": 30,
          "max_days": 45,
          "max_overshoot": 15,
          "avg_overshoot": 8.2,
          "stuck_items": [
            {
              "lead_id": "…", "deal_id": "…", "inn": "7701234567", "client": "ООО Пример",
              "days_int": 45, "overshoot": 15
            }
          ]
        }
      ]
    }
  ],
  "top_by_tb_grouped": [
    {
      "tb": "ЮЗБ",
      "managers": [ "… элементы как в top_by_tb[] …" ]
    }
  ],
  "charts": {
    "by_tb": [
      { "tb": "ЮЗБ", "km_with_violations": 12, "km_total": 80, "violation_deals": 45 }
    ],
    "facts": [
      { "tb": "ЮЗБ", "km": "Иванов И.И.", "product_group": "…", "product": "…", "stage_key": "В РАБОТЕ", "deals": 3 }
    ]
  },
  "thresholds_count": 156,
  "detail_by_product": [],
  "manager_totals": []
}
```

В JSON **всегда**: `records`, `exceedances`, `dimensions`, `top_by_tb`, `top_by_tb_grouped`, `charts`, `detail_by_product`, `manager_totals`.

> Этап пропускается **без ошибки**, если: `enabled: false`; колонки КМ нет в Excel; `km` не в `required_column_keys`; не удалось построить пороги P80.  
> При отсутствии `label` в данных `strategy_filter` работает как `all`.

```json
"columns": { "km": "КМ" },
"required_column_keys": [ "...", "km" ],
"manager_analytics": {
  "enabled": true,
  "metric": "days_on_stage",
  "percentile": 80,
  "threshold_scope": "overall",
  "top_managers_per_tb": 3,
  "top_hotspots_per_manager": 5,
  "top_stuck_items_per_hotspot": 15,
  "use_latest_report_date": true,
  "rank_by_team": true,
  "team_files": { "enabled": true, "lead_team": { "test": [] }, "deal_team": { "test": [] } },
  "rank_selection": {
    "product_groups": [],
    "products": [],
    "strategy_filter": "strategy_2026",
    "efs_flag": 1,
    "change_conditions": 0
  },
  "html_include_detail": false
}
```

---

## 15. Логирование (`logging`)

| Ключ | По умолчанию | Описание |
|------|--------------|----------|
| `logger_name` | `kanban` | Имя логгера |
| `info_file_prefix` | `INFO_kanban` | Файл INFO |
| `debug_file_prefix` | `DEBUG_kanban` | Файл DEBUG |
| `hour_format` | `%Y%m%d_%H` | Час в имени лога |

Файлы: `log/INFO_kanban_20260831_12.log`

---

## 16. Аудит данных

При `processing.audit_row_counts: true` в лог пишется:

- число строк на каждом этапе;
- **предупреждение**, если строки пропали без причины;
- проверка, что все `ID ПрПр` попали в `lead_stage_records`.

```
Аудит [фильтрация]: 43,776 строк (без изменений)
Аудит [лиды]: все 13,182 уникальных ID ПрПр учтены
```

---

## 17. Минимальный config

```json
{
  "mode": "test",
  "test_files": ["2ГОСБ1ТБ.xlsx"]
}
```

Остальное подставится из `src/settings.py`.

---

## 18. Связанные документы

- [README.md](../README.md) — обзор и запуск
- [DEPLOY.md](DEPLOY.md) — перенос на другой ПК
- [BT_KANBAN.md](BT_KANBAN.md) — бизнес-требования
