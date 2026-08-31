# KANBAN HTML Analiz

Сервис анализа Excel-отчётов Kanban по лидам (ПрПр) и сделкам: сроки нахождения на стадиях, сводная статистика (min/max/перцентили) в разрезе продуктов и ТБ.

## Задача

- Загрузка 22 prod-файлов (11 ТБ × «К ПРОДАЖЕ» / «В РАБОТЕ») или test-файлов из `Docs/FileIN`
- Трекинг каждого `ID ПрПр` по стадиям «Текущий статус» (и опционально «Стадия сделки»)
- Агрегация сроков: min, max, эмпирические перцентили (целые дни; для каждого P — срок, число лидов, min/max нижней доли)
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

> Пути в config и каталоги `log/`, `OUT/` считаются **от корня проекта** (где `run.py`), не от текущей папки IDE.

## Структура проекта

```
config.json          # параметры (см. Docs/CONFIG.md)
run.py               # точка запуска
src/                 # исходный код
Docs/CONFIG.md       # полный справочник config.json
Docs/FileIN/         # test-данные (в .gitignore)
IN/                  # prod-данные
OUT/                 # результаты с timestamp
log/                 # логи INFO/DEBUG
```

## config.json

**Полный справочник с вариантами и примерами:** [Docs/CONFIG.md](Docs/CONFIG.md)

### Краткая карта разделов

| Раздел | Назначение |
|--------|------------|
| `mode`, `paths`, `test_files`, `prod_files` | Режим и каталоги |
| `columns`, `required_column_keys` | Имена колонок Excel |
| `excel` | Лист, таблица Base, движок |
| `processing` | Дедупликация, аудит, fallback сроков |
| `performance` | Workers, память, оптимизация чтения |
| `progress` | Вывод статуса, тайминг этапов, сводка в конце |
| `dates` | Форматы дат, пустые значения |
| `duration_source`, `stage_analysis_mode`, `percentiles` | Логика анализа |
| `aggregation` | Группировки и метрики |
| `output` | Имена файлов, листы Excel, оформление |
| `filters` | Фильтры: Excel (`enabled`), JSON (`filter_slices` для `html_slice: true`), HTML (ВКЛ/ВЫКЛ). ЕФС — только config (`html_slice: false`) |
| `dashboard` | Дашборд: `precompute_html_filter_slices`, `html_json` (split-bundle), метрики по умолчанию |
| `manager_analytics` | Превышения P80 по КМ; отдельный JSON + bar-графики в HTML |
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
    "html_include_detail": false
  }
}
```

## Выходные файлы

`OUT/kanban_report_YYYYMMDD_HHMMSS.xlsx` — листы:

- **Сводная** — все ТБ
- **Общий** — без разреза ТБ
- **{ТБ}** — отдельный лист на каждый ТБ
- **Матрица** — продукт × стадия, фильтры ТБ / показатель / метрика
- **Менеджеры** — топ-N КМ по ТБ с превышениями P80 (если в Excel есть колонка КМ)
- **Графики** — кривые «лиды × дни» (Chart.js в Excel через openpyxl)

**JSON основной** (split-bundle, prod):

```
OUT/kanban_report_YYYYMMDD_HHMMSS.json          # slim-архив / указатель
OUT/kanban_report_YYYYMMDD_HHMMSS_html/
  kanban_report_YYYYMMDD_HHMMSS.manifest.json
  slices/none.json, slices/change_conditions.json, …
```

Содержит `visualizations.filter_slices` (комбинации HTML-фильтров), обе агрегации `group_product` / `group_only`. Копии `*_latest*` и `HTML/data/` **не создаются**.

`OUT/kanban_report_managers_YYYYMMDD_HHMMSS.json` — аналитика КМ: `top_by_tb`, блок `charts` для bar-графиков; при `html_include_detail: true` — также `detail_by_product`, `manager_totals`.

## HTML-дашборд

Каталог `HTML/` — локальная страница с загрузкой JSON. **UI** повторяет glass-layout из `SPOD_PROM/common/web-fill-full` и `RESURCE_PANEL_HTML_WORK` (боковые панели, edge-кнопки, filter-block).

```bash
cd HTML && python -m http.server 8080
# открыть http://localhost:8080 — загрузить JSON вручную (manifest + slices или monolith)
```

- Левая панель: загрузка JSON (manifest или monolith + JSON менеджеров), **pipeline-фильтры** (ВКЛ/ВЫКЛ), настройки графика
- Правая панель: **мультивыбор** ТБ, групп и продуктов (поиск, сворачивание, бейдж «N / всего»)
- Вкладки **Графики** и **Сводная матрица** (+ блок **BOTTOM менеджеры** на вкладке матрицы)
- **Графики линий:** «По продуктам/группам» и «По ТБ» — кривые «лиды × дни»
- **Графики КМ:** «КМ с нарушениями P80: по ТБ» / «… по группам/продуктам» — bar-chart (нужен JSON менеджеров)
- **Агрегация в HTML:** «По продуктам» / «По группам» + pipeline-фильтры — срез из `visualizations.filter_slices`
- **Pipeline-фильтры:** изменение условий, ввод данных, метки «Стратегия» / «Стратегия·2026». **ЕФС** — только `config.filters.efs_flag` (`enabled`, `value`, `html_slice: false`)
- **Менеджеры:** отдельный JSON в `OUT/`; загрузка вручную в дашборде
- `config.product_analysis_mode` — только для **Excel**; в JSON — обе агрегации и все срезы фильтров
- Режим «По ТБ»: графики **друг под другом** (одна колонка)

## Полнота данных

- Оптимизация **не отбрасывает строки** — только ускоряет чтение/обработку
- В JSON серии распределения хранятся как `days_sorted` (эквивалент `{lead_index, days}`)
- Блок `pivot_matrices` в JSON не генерируется по умолчанию — HTML строит матрицу из `pivot_flat`
- Исключение строк — **только включённые фильтры** в `filters` (`enabled: true`) для **Excel**; HTML переключает предрасчитанные срезы JSON
- Аудит в логе: `Аудит [лиды]: все N ID ПрПр учтены`

## Перенос на другой ПК (без Git)

Подробно: [Docs/DEPLOY.md](Docs/DEPLOY.md). Архив для почты: каталог `POST/KANBAN_HTML_Analiz.zip`.

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
| 1.0.2 | 2026-08-31 | Split-bundle JSON; ЕФС config-only (`html_slice`); без `*_latest*`; bar-графики КМ; `charts` в JSON менеджеров |
