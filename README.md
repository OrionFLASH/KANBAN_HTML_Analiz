# KANBAN HTML Analiz

Сервис анализа Excel-отчётов Kanban по лидам (ПрПр) и сделкам: сроки нахождения на стадиях, сводная статистика (min/max/перцентили) в разрезе продуктов и ТБ.

## Задача

- Загрузка 22 prod-файлов Kanban (остаток / К продаже и Отказ / ВСЕ / Реализация) из `IN/PROD` или test из `IN/TEST`
- Трекинг каждого `ID ПрПр` по стадиям «Текущий статус» (и опционально «Стадия сделки»)
- Агрегация сроков: min, max, эмпирические перцентили (целые дни; для каждого P — срок, число лидов, min/max нижней доли)
- Экспорт в Excel (форматирование) и JSON (для будущего HTML-дашборда)

## Требования

- Python 3.12 или Anaconda (pandas, openpyxl — без pip install)
- Входные файлы: лист `Sheet1`, первая строка — заголовок (именованные таблицы Excel не используются)

## Запуск

### HTML + JSON pipeline (основной)

```bash
cd /path/to/KANBAN_HTML_Analiz
python run.py
```

Или с явным config:

```bash
python -m src.v1.main config.json
```

| Режим | Каталог входа | Выход |
|-------|---------------|-------|
| `test` | `IN/TEST` | `OUT/kanban_report_*.xlsx` + JSON |
| `prod` | `IN/PROD` | то же |

### Excel-only pipeline v2

Отдельный отчёт по лидам: нормативы, уникальные ID, превышения (перцентиль из `exceedance.percentile`), своды менеджеров. **JSON не создаётся.**

```bash
python run_excel.py
```

Конфиг: `config_excel_v2.json` — обзор: [Docs/CONFIG_EXCEL_V2.md](Docs/CONFIG_EXCEL_V2.md); **каждый ключ:** [Docs/CONFIG_EXCEL_V2_PARAMS.md](Docs/CONFIG_EXCEL_V2_PARAMS.md)

Ключевые блоки v2: `filters` (универсальная схема), `exceedance.percentile` (порог превышения, по умолчанию 80), `outlier_clipping` (выбросы срока перед нормативами, `min_remaining`), `team_files`, `output.sheet_freeze`, `output.statistics`.

| Режим | Каталог входа | Выход |
|-------|---------------|-------|
| `test` | `IN/TEST` | `OUT/excel_v2/kanban_excel_v2_{analytics\|detail\|source}_*.xlsx` |
| `prod` | `IN/PROD` | то же |

В `IN/TEST` / `IN/PROD` — Kanban и файлы команд (`team_files` в config). Перед запуском проверяется наличие **всех** файлов для выбранного `mode`; при prod — **15 файлов** (11 Kanban ЕФС + 4 объединённых «команда лида и сделки»).

> Пути в config считаются **от корня проекта** (где `run.py` / `run_excel.py`), не от CWD IDE.

Готовый пакет Excel v2 (код, `config_excel_v2.json`, Docs): **`v2_program_files_20260911c.zip`** в корне репозитория. В архиве: `run_excel.py` / `run.py`, **весь `src/`** (общие модули + `v1` + `v2`, **без** `src/Tests/`), конфиги, Docs; старые `v2_*.zip` удалены. Справочник конфига: [Docs/CONFIG_EXCEL_V2.md](Docs/CONFIG_EXCEL_V2.md) v2.9.3; полный разбор **каждого** ключа: [Docs/CONFIG_EXCEL_V2_PARAMS.md](Docs/CONFIG_EXCEL_V2_PARAMS.md).

Отдельный архив документации (папка `Docs/` + `README.md` + `ROADMAP.md`): **`docs_20260911c.zip`**.

## Структура проекта

```
config.json          # HTML+JSON pipeline (см. Docs/CONFIG.md)
config_excel_v2.json # Excel-only v2 (см. Docs/CONFIG_EXCEL_V2.md)
run.py               # запуск HTML+JSON (v1)
run_excel.py         # запуск Excel v2
src/                 # общие модули + пакеты pipeline
  v1/                # HTML + JSON + Excel (run.py / config.json)
  v2/                # Excel-only (run_excel.py / config_excel_v2.json)
  Tests/             # pytest
Docs/CONFIG.md       # справочник config.json
Docs/CONFIG_EXCEL_V2.md  # обзорный справочник config_excel_v2.json
Docs/CONFIG_EXCEL_V2_PARAMS.md  # карточка на каждый ключ config
IN/TEST/             # test Kanban + команды (run.py и run_excel.py)
IN/PROD/             # prod Kanban + команды
OUT/                 # результаты run.py
OUT/excel_v2/        # результаты run_excel.py
log/                 # логи INFO/DEBUG
```

## config.json

**Полный справочник с вариантами и примерами:** [Docs/CONFIG.md](Docs/CONFIG.md)

### Краткая карта разделов

| Раздел | Назначение |
|--------|------------|
| `mode`, `paths`, `test_files`, `prod_files` | Режим и каталоги |
| `columns`, `required_column_keys` | Имена колонок Excel |
| `excel` | Лист Sheet1 (заголовок в первой строке), openpyxl `read_only` |
| `processing` | Дедупликация, аудит, fallback сроков |
| `performance` | Workers, память, оптимизация чтения |
| `progress` | Вывод статуса, тайминг этапов, сводка в конце |
| `dates` | Форматы дат, пустые значения |
| `duration_source`, `stage_analysis_mode`, `percentiles` | Логика анализа. `stage_analysis_mode: status` — только статусы; фильтр уровня в HTML скрыт (`analysis_level_locked`) |
| `aggregation` | Группировки и метрики |
| `output` | Имена файлов, листы Excel, оформление |
| `filters` | Фильтры: Excel (`enabled`), JSON (`filter_slices` для `html_slice: true`), HTML (ВКЛ/ВЫКЛ). Config-only (`html_slice: false`): ЕФС, терминальные `exclude_deal_*`, опционально `exclude_current_for_sale` (исключить текущий статус «К ПРОДАЖЕ» из анализа и колонок UI) |
| `dashboard` | Дашборд: `precompute_html_filter_slices`, `html_json` (split-bundle), метрики по умолчанию |
| `manager_analytics` | Превышения P80; TOP по участникам команды (`rank_by_team` + `team_files.files` + «Тип команды» 1/2); КМ+ВКС+лидеры; Excel/UI |
| `logging` | Файлы логов |

### Частые настройки

```json
{
  "mode": "prod",
  "duration_source": "columns",
  "stage_analysis_mode": "status",
  "percentiles": [20, 50, 80],
  "parallel_workers": 0,
  "performance": {
    "max_parallel_workers": 3,
    "reserve_cpu_cores": 1,
    "compact_distribution_series": true,
    "precompute_pivot_matrices": false
  },
  "dashboard": {
    "html_json": {
      "bundle_mode": "split",
      "max_distribution_points": 800,
      "write_monolith_archive": true
    }
  },
  "filters": {
    "efs_flag": { "enabled": false, "column_key": "efs_flag", "value": 1, "html_slice": false }
  },
  "manager_analytics": {
    "enabled": true,
    "top_managers_per_tb": 3,
    "use_latest_report_date": true,
    "rank_selection": {
      "product_groups": [],
      "products": [],
      "strategy_filter": "strategy_2026",
      "efs_flag": 1,
      "change_conditions": 0
    }
  }
}
```

## Выходные файлы

`OUT/kanban_report_YYYYMMDD_HHMMSS.xlsx` — листы:

- **Сводная** — все ТБ
- **Общий** — без разреза ТБ
- **{ТБ}** — отдельный лист на каждый ТБ
- **Менеджеры** — топ-N участников/КМ по ТБ (при `rank_by_team` — по команде), роли и команда, зоны превышения
- **Графики** — кривые «лиды × дни» (если лист ещё формируется в сборке; иначе — только HTML)

Листы с **> 900 000** строк выгружаются в CSV (`;`) вместо вкладки Excel (см. `output.csv_overflow`).

> Лист **«Матрица»** в Excel **не создаётся**. Сводная матрица — в HTML (дни + счётчики ≤ / > порога).

### Excel v2 (`run_excel.py`)

Два файла (управляется `output.report_parts`: `both` / `analytics` / `detail`):

| Файл | Листы |
|------|--------|
| `kanban_excel_v2_analytics_*.xlsx` | Нормативы, Статистика, все матрицы «Распределение сроков» |
| `kanban_excel_v2_detail_*.xlsx` | Уникальные ID, Свод по менеджеру, Свод ПрПр с отклонениями |

| Лист | Содержание |
|------|------------|
| **Нормативы** | Min/max, P20/P50/P80 по ТБ и «все тб»; по строке — до/после и отсечено по каждому вх. фильтру + выбросы; `green_red` для колонок «Мин…» / «Макс…» |
| **Статистика** | Воронка фильтров (до/после) + свод отсечений по группам |
| **Распределение сроков** | Матрица группа/продукт × дни; порядок `by_volume` (см. `variants`) |
| **Распределение сроков (группы)** | Тот же pivot: дни ↑; группы А→Я; внутри группы продукты по убыванию лидов |
| **Распределение сроков (статус)** | Как основной + колонка «Текущий статус» после продукта |
| **Распред. сроков (группы+статус)** | Раскладка по группам + статус после продукта |
| **Уникальные ID** | Снимок лидов, лидеры (+ почты Альфа/Сигма по ТН), колонки сроков по каждому статусу, норматив P{n}, превышение; лёгкое оформление (`light_format_sheets`) |
| **Свод по менеджеру** | ФИО/ТН/почты, число нарушений, разрез «Группа + Продукт» |
| **Свод ПрПр с отклонениями** | Детализация каждого превышения; лёгкое оформление (`light_format_sheets`) |

Ненужная часть не считается: `analytics` — без команд/почт/менеджеров; `detail` — без матриц сроков и воронки.

Если на листе **больше 900 000** строк, вкладка в xlsx не создаётся — данные сохраняются в отдельный CSV (`;`, UTF-8 BOM) рядом с отчётом. Настройки: `output.excel_max_rows_per_sheet`, `output.csv_overflow`.

`excel_theme: green_red` красит колонки с маркерами «Мин»/«Макс» на обычных листах; на `leads`/`violations` раскраска и поклеточное оформление отключены ради скорости ПРОД.

Подробнее: [Docs/CONFIG_EXCEL_V2.md](Docs/CONFIG_EXCEL_V2.md)

**JSON основной** (split-bundle, prod):

```
OUT/kanban_report_YYYYMMDD_HHMMSS.json          # slim-архив / указатель
OUT/kanban_report_YYYYMMDD_HHMMSS_html/
  kanban_report_YYYYMMDD_HHMMSS.manifest.json
  slices/none.json, slices/change_conditions.json, …
```

Содержит `visualizations.filter_slices` (комбинации HTML-фильтров), обе агрегации `group_product` / `group_only`. Копии `*_latest*` и `HTML/data/` **не создаются**.

`OUT/kanban_report_managers_YYYYMMDD_HHMMSS.json` — аналитика КМ:

| Блок | Содержание |
|------|------------|
| `meta.report_date_snapshot` | Дата актуальной выгрузки (max «Дата отчета») при `use_latest_report_date: true` |
| `records[]` | Лиды×стадии актуального среза: метка, exceeded, порог P80; `deal_id`/`inn`/`client` — только при exceeded |
| `exceedances[]` | Только отклонения P80: lead_id, deal_id, inn, client, overshoot |
| `top_by_tb[]` | TOP-N по `rank_selection` + `hotspots` + `stuck_items` |
| `top_by_tb_grouped[]` | Те же данные, сгруппированные по ТБ для UI |
| `dimensions` | Справочник групп и продуктов |
| `charts` | Bar-графики КМ (`by_tb`, `facts`) |
| `detail_by_product`, `manager_totals` | Агрегаты (полный набор) |

## HTML-дашборд

Каталог `HTML/` — локальная страница с загрузкой JSON. **UI** повторяет glass-layout из `SPOD_PROM/common/web-fill-full` и `RESURCE_PANEL_HTML_WORK` (боковые панели, edge-кнопки, filter-block).

```bash
cd HTML && python -m http.server 8080
# открыть http://localhost:8080 — загрузить JSON вручную (manifest + slices или monolith)
```

- Левая панель: загрузка **одного** JSON (manifest или monolith), **pipeline-фильтры** (ВКЛ/ВЫКЛ), настройки графика
- Правая панель: **мультивыбор** ТБ, групп и продуктов (поиск, сворачивание, бейдж «N / всего»)
- Вкладки **Графики** и **Сводная матрица**; вкладка **Менеджеры** — только при `dashboard.show_managers_tab: true` (данные из блока `managers` в том же JSON)
- **Графики распределения** (режимы «По продуктам/группам» и «По ТБ»): на каждой карточке три вида — **гистограмма** (где толпа лидов по срокам), **ECDF** (накопленный % лидов), **ранговая шкала** (лид №1 = самый быстрый); линии П20/50/80 по эмпирическому алгоритму backend
- **Разворот графика:** клик по графику — увеличение между боковыми панелями; клик по заголовку/между графиками — вся карточка на весь экран; «Свернуть» или Esc
- **Графики КМ:** «КМ с нарушениями P80: по ТБ» / «… по группам/продуктам» — bar-chart (нужен вложенный блок `managers` / `charts`)
- **Агрегация в HTML:** «По продуктам» / «По группам» + pipeline-фильтры — срез из `visualizations.filter_slices`
- **Pipeline-фильтры:** изменение условий, ввод данных, метки «Стратегия» / «Стратегия·2026». **ЕФС** — только `config.filters.efs_flag` (`enabled`, `value`, `html_slice: false`)
- **Менеджеры:** при включённой вкладке — секции **по ТБ**, топ-3 нарушителя P80; hotspots с **ИНН / ID ПрПр / ID сделки**; отдельный файл менеджеров в UI **не загружается**
- `config.product_analysis_mode` — только для **Excel**; в JSON — обе агрегации и все срезы фильтров
- Режим «По ТБ»: графики **друг под другом** (одна колонка)

## Полнота данных

- Оптимизация **не отбрасывает строки** — только ускоряет чтение/обработку
- В JSON серии распределения хранятся как `days_sorted` (эквивалент `{lead_index, days}`)
- Блок `pivot_matrices` в JSON не генерируется по умолчанию — HTML строит матрицу из `pivot_flat`
- Исключение строк — **только включённые фильтры** в `filters` (`enabled: true`) для **Excel**; HTML переключает предрасчитанные срезы JSON
- Аудит в логе: `Аудит [лиды]: все N ID ПрПр учтены`

## Перенос на другой ПК (без Git)

Подробно: [Docs/DEPLOY.md](Docs/DEPLOY.md). UI: один файл `OUT/kanban_report_*.json` (monolith). Копия для пересылки: `POST/KANBAN_HTML_Analiz/` (код без тестов и HTML; в Docs — только CONFIG).

## История версий

| Версия | Дата | Изменения |
|--------|------|-----------|
| 0.1.0 | 2026-08-31 | MVP pipeline |
| 0.2.0 | 2026-08-31 | Все настройки в config.json |
| 0.3.0 | 2026-08-31 | Ускорение, прогресс, разбор дат |
| 0.4.0 | 2026-08-31 | Аудит полноты данных, Docs/CONFIG.md |
| 0.5.0 | 2026-08-31 | HTML-дашборд, Excel Матрица/Графики, visualizations в JSON |
| 0.6.0 | 2026-08-31 | Оптимизация: один проход viz, compact JSON, tb_sheets из by_tb, itertuples |
| 0.6.1 | 2026-08-31 | Серии __ALL__ для графиков, тайминг этапов pipeline, kanban_report_latest.json |
| 0.7.0 | 2026-08-31 | HTML: мультивыбор, графики свод+деталь, сортировка матрицы, filters_applied в JSON |
| 0.8.0 | 2026-08-31 | JSON: обе агрегации; HTML — выбор среза; ТБ вертикально; Excel по config |
| 0.9.0 | 2026-08-31 | JSON filter_slices (комбинации config.filters); HTML pipeline-фильтры |
| 1.0.0 | 2026-08-31 | UI: иконки, ресайз, переключатели ВКЛ/ВЫКЛ; метка Стратегия/2026; аналитика КМ (Excel+JSON+HTML) |
| 1.0.1 | 2026-08-31 | Документация config; `km` в `required_column_keys`; синхронизация POST |
| 1.0.2 | 2026-08-31 | Split-bundle JSON; ЕФС config-only; bar-графики КМ; без `*_latest*` |
| 1.0.3 | 2026-08-31 | Excel без «Матрицы»; hotspots по КМ (Excel + JSON + UI); `top_hotspots_per_manager` |
| 1.0.4 | 2026-08-31 | `rank_selection` для отбора TOP КМ; полные `records` в JSON; пересчёт TOP в UI |
| 1.0.5 | 2026-08-31 | Топ-3 нарушителя по ТБ в UI; `exceedances`, `stuck_items`, `deal_id`/`inn`; срез `use_latest_report_date`; fix parse datetime64 |
| 1.0.6 | 2026-08-31 | Исключение терминальных стадий сделки (построчно, UI + JSON); Excel: колонки «П80 КМ ≥» — число уникальных КМ с сроком ≥ P80 |
| 1.0.7 | 2026-08-31 | Config-only «К ПРОДАЖЕ»; команда лида/сделки + ВКС → TOP; матрица ↑/↓ порога; locked уровень `status`; сброс JSON; вкладка «Менеджеры» опциональна, без отдельной загрузки JSON |
| 1.0.8 | 2026-08-31 | HTML: гистограмма + ECDF + ранговая шкала; перцентили на графиках; разворот по клику (график / карточка) |
| 2.0.0 | 2026-09-01 | **Excel v2:** `run_excel.py`, `config_excel_v2.json`, `src/v2/` (ранее `excel_report/`); 4 листа; [Docs/CONFIG_EXCEL_V2.md](Docs/CONFIG_EXCEL_V2.md) |
| 2.1.0 | 2026-09-02 | Универсальные `filters` (`action`/`match`/`values`); разделение `src/v1` и `src/v2`; POST 2.1.0 |
| 2.2.0 | 2026-09-02 | `outlier_clipping` в config v2; лист «Статистика» (воронка фильтров); на «Нормативах» — отсечение по группе |
| 2.2.1 | 2026-09-02 | Воронка фильтров перенесена на лист «Статистика»; «Нормативы» — снова таблица с автофильтром |
| 2.2.2 | 2026-09-02 | Фильтры метки (`strategy_label` вкл.; `*_2026` / активация выкл.); формат чисел `# ##0` на «Статистике» |
| 2.2.3 | 2026-09-03 | v2: `exceedance.percentile`; на «Нормативах» — до/после и отсечено по каждому вх. фильтру (по строке группы) |
| 2.2.4 | 2026-09-03 | `unique_days_trim`: отсечение % уникальных сроков слева/справа (example в config, выкл.) |
| 2.2.5 | 2026-09-03 | Adaptive: лимиты workers из config; осторожный режим при RAM &lt; 16 ГБ → 2 workers |
| 2.2.6 | 2026-09-03 | Лист «Распределение сроков»: матрица группа/продукт × дни (число лидов), градиент, freeze D2 |
| 2.2.7 | 2026-09-03 | Матрица: `sort_mode` by_volume, строка «Всего»/автофильтр, крупный шрифт; `manager_emails` (CSV почт по ТН) |
| 2.2.8 | 2026-09-03 | `output.sheet_freeze`: last_row/last_col — закрепление по каждому листу Excel v2 |
| 2.2.9 | 2026-09-03 | Fix `outlier_clipping` на больших группах (выравнивание индекса); почты на своде после ФИО; `group_keys` без `analysis_level` |
| 2.3.0 | 2026-09-07 | Единые файлы «команда лида и сделки» + колонка «Тип команды» (1/2/-); prod Kanban ЕФС 07-09-2026 |
| 2.3.1 | 2026-09-07 | Архив программы v2: `v2_program_files_20260907.zip` (без тестов) |
| 2.3.2 | 2026-09-08 | Fix лидеров + подробный DEBUG; архив `v2_program_files_20260908.zip` |
| 2.3.3 | 2026-09-08 | Архив `v2_program_files_20260908b.zip`: `team_files.files` + json_config |
| 2.3.4 | 2026-09-08 | Fix `len(DurationMatrixResult)` после матрицы сроков; архив `20260908c` |
| 2.3.5 | 2026-09-08 | Fix: нет «Дата отчета» в команде → весь файл = одна дата; архив `20260908d` |
| 2.3.6 | 2026-09-08 | Fix FutureWarning fillna; warnings→лог; team_files по ТБ 08-09; архив `20260908e` |
| 2.3.7 | 2026-09-08 | POST: код без тестов/HTML; Docs только CONFIG; синхронизация с main |
| 2.3.8 | 2026-09-08 | Лёгкое оформление leads/violations (`light_format_sheets`; `green_red` на Нормативах остаётся); `keep_leaders_only` |
| 2.3.9 | 2026-09-08 | Второй лист матрицы сроков: группы А→Я, внутри — продукты по объёму (`variants`) |
| 2.4.0 | 2026-09-10 | Матрица сроков со статусом; client_id текстом; даты `YYYY-MM-DD`; без source_deal_id/tb_code в снимке |
| 2.4.1 | 2026-09-10 | Два Excel-файла (`analytics` / `detail`) + `output.report_parts` с пропуском ненужных расчётов |
| 2.4.2 | 2026-09-10 | «Уникальные ID»: колонки сроков по каждому «Текущий статус» (`status_duration_columns`) |
| 2.5.0 | 2026-09-10 | Docs CONFIG_EXCEL_V2 v2.5.0; архив `v2_program_files_20260910.zip` |
| 2.5.1 | 2026-09-10 | Docs: полный разбор ключей config_excel_v2 (logging/excel/processing/dates/perf/checklist) |
| 2.5.2 | 2026-09-10 | Архив документации `docs_20260910.zip` (Docs + README + ROADMAP) |
| 2.6.0 | 2026-09-10 | Подробные описания statistics/`export_km_count` и др.; km_count на P80 |
| 2.6.1 | 2026-09-10 | Архив документации `docs_20260910b.zip` (v2.6.0 docs) |
| 2.7.0 | 2026-09-10 | CONFIG_EXCEL_V2_PARAMS: карточка на каждый ключ config (603); архив `docs_20260910c.zip` |
| 2.8.0 | 2026-09-10 | Третий Excel `source` + `output.source_export` (ordered filters, max/min/gt/…); архив `v2_program_files_20260910f.zip` |
| 2.8.1 | 2026-09-10 | Актуальный prod-config + независимость filters/source_export; архив `v2_program_files_20260910g.zip` |
| 2.9.0 | 2026-09-11 | ToDo v3: Метод продаж, percentiles Excel, filters_order, Статистика-каталог, heartbeat снимка; архив `v2_program_files_20260911.zip` |
| 2.9.1 | 2026-09-11 | Docs v2.9.0: CONFIG/PARAMS/DEPLOY; архивы `v2_program_files_20260911.zip` + `docs_20260911.zip` |
| 2.9.2 | 2026-09-11 | Fix архива: полный `src/` (не только `v2`); `v2_program_files_20260911b.zip` + `docs_20260911b.zip` |
| 2.9.3 | 2026-09-11 | Percentiles: `split_mode=files` — отдельный xlsx на ТБ; архивы `20260911c` |
