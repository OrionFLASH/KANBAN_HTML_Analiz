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
| `progress` | Вывод статуса в консоль |
| `dates` | Форматы дат, пустые значения |
| `duration_source`, `stage_analysis_mode`, `percentiles` | Логика анализа |
| `aggregation` | Группировки и метрики |
| `output` | Имена файлов, листы Excel, оформление |
| `filters` | Фильтры (AND, только если enabled) |
| `logging` | Файлы логов |

### Частые настройки

```json
{
  "mode": "prod",
  "duration_source": "columns",
  "stage_analysis_mode": "status",
  "percentiles": [20, 50, 80],
  "parallel_workers": 0,
  "performance": { "max_parallel_workers": 3, "reserve_cpu_cores": 1,
    "compact_distribution_series": true, "precompute_pivot_matrices": false }
}
```

## Выходные файлы

`OUT/kanban_report_YYYYMMDD_HHMMSS.xlsx` — листы:

- **Сводная** — все ТБ
- **Общий** — без разреза ТБ
- **Сводная** / **Общий** / **{ТБ}** — табличная статистика
- **Матрица** — продукт × стадия, фильтры ТБ / показатель / метрика (выпадающие списки)
- **Графики** — кривые «лиды × дни» (Chart.js в Excel через openpyxl)

`OUT/kanban_report_YYYYMMDD_HHMMSS.json` — агрегаты + блок `visualizations` для HTML.

## HTML-дашборд

Каталог `HTML/` — локальная страница с загрузкой JSON. **UI** повторяет glass-layout из `SPOD_PROM/common/web-fill-full` и `RESURCE_PANEL_HTML_WORK` (боковые панели, edge-кнопки, filter-block).

```bash
cd HTML && python -m http.server 8080
# открыть http://localhost:8080
```

- Левая панель: настройки (режим графика, метрика, показатель)
- Правая панель: фильтры (ТБ, группа, продукт, стадия)
- Вкладки **Графики** (линии по продуктам или ТБ) и **Сводная матрица**

## Полнота данных

- Оптимизация **не отбрасывает строки** — только ускоряет чтение/обработку
- В JSON серии распределения хранятся как `days_sorted` (эквивалент `{lead_index, days}`)
- Блок `pivot_matrices` в JSON не генерируется по умолчанию — HTML строит матрицу из `pivot_flat`
- Исключение строк — **только включённые фильтры** в `filters`
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
