# Перенос проекта на другой ПК (без Git)

**Версия копии POST:** 2.2.7 (2026-09-03)

Инструкция для работы после пересылки по почте или копированием каталога.

## Каталог POST (без zip)

Актуальная копия проекта: **`POST/KANBAN_HTML_Analiz/`** (обновляется при релизах).

Содержит **Python pipeline + HTML-дашборд** (`HTML/`) и **Excel-only pipeline v2** (`run_excel.py`). Архив `.zip` **не** формируется — только зеркало структуры с файлами.

**Не входит в POST:** `src/Tests/` (тесты только в Git-репозитории).

## Минимальный набор файлов (код + конфиг)

```
KANBAN_HTML_Analiz/
├── config.json
├── config_excel_v2.json          # Excel-only v2 (см. Docs/CONFIG_EXCEL_V2.md)
├── run.py                        # HTML + JSON
├── run_excel.py                  # Excel v2 (без JSON)
├── README.md
├── ROADMAP.md
├── .env.example
├── src/                           # без каталога Tests/
│   ├── v1/                        # HTML + JSON + Excel (run.py)
│   ├── v2/                        # Excel-only pipeline (run_excel.py)
│   ├── filters.py                 # общие модули
│   ├── outlier_clipping.py        # выбросы срока (v2 нормативы)
│   ├── filter_funnel.py           # воронка фильтров → лист «Статистика»
│   ├── manager_emails.py          # почты Альфа/Сигма по ТН из CSV в IN/
│   ├── excel_loader.py
│   ├── lead_tracker.py
│   ├── aggregator.py
│   └── …                          # + duration_matrix в src/v2/
├── HTML/                          # ← дашборд (обязательно)
│   ├── index.html
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       ├── data.js
│       ├── distribution.js
│       ├── icons.js
│       ├── multi-filter.js
│       ├── managers.js
│       ├── charts.js
│       ├── chart-expand.js
│       ├── pivot.js
│       └── app.js
└── Docs/
    ├── CONFIG.md
    ├── CONFIG_EXCEL_V2.md
    ├── DEPLOY.md
    └── BT_KANBAN.md
```

**Не включать:** `.git/`, `log/`, `OUT/`, `IN/`, `Docs/FileIN/`, `POST/`, `src/Tests/`, `__pycache__/`

## Данные Excel (отдельно)

| Режим | Каталог | Файлы |
|-------|---------|-------|
| test (run.py / run_excel.py) | `IN/TEST/` | Kanban + команды из config |
| prod (run.py / run_excel.py) | `IN/PROD/` | 22 Kanban + 8 «Команда лида» + 8 «Команда сделки» (см. config) |

Перед запуском pipeline проверяет наличие всех файлов для `mode`; при отсутствии — остановка с перечнем недостающих.

## Настройка на новом ПК

1. Python 3.12 + `pandas`, `openpyxl`
2. Распаковать архив
3. Создать пустые: `IN/`, `IN/TEST/`, `IN/PROD/`, `OUT/`, `OUT/excel_v2/`, `log/`, `Docs/FileIN/`
4. Положить xlsx
5. Настроить `config.json` / `config_excel_v2.json` — см. [CONFIG.md](CONFIG.md), [CONFIG_EXCEL_V2.md](CONFIG_EXCEL_V2.md)
6. `python run.py` → `OUT/`; `python run_excel.py` → `OUT/excel_v2/`
7. Дашборд: открыть `HTML/index.html` в браузере (file://), загрузить `OUT/kanban_report_*.json`. Сервер не нужен.

## HTML-дашборд

| Раздел | Описание |
|--------|----------|
| Левая панель | Загрузка **одного** JSON (monolith), **pipeline-фильтры**, агрегация, режим графика |
| Правая панель | Мультивыбор ТБ, групп, продуктов (поиск, сворачивание) |
| Вкладки | **Графики** · **Сводная матрица** · **Менеджеры** (опционально, `show_managers_tab: true`) |
| Графики распределения | «По продуктам/группам», «По ТБ» — гистограмма, ECDF, ранговая шкала; линии П20/50/80 |
| Разворот графика | Клик по графику — между панелями; по карточке — на весь экран; Esc / «Свернуть» |
| Графики КМ | «КМ с нарушениями P80…» — bar-chart (блок `managers` в том же JSON) |
| Матрица | Группа/продукт × стадия; дни + счётчики ↑/↓ порога P80 |
| Менеджеры | Только при включённой вкладке; топ-N по ТБ; клик по КМ — **полноэкранная карточка**; отдельный файл менеджеров в UI **не загружается** |
| Pipeline-фильтры | ВКЛ/ВЫКЛ: изменение условий, ввод данных, метки, **терминальные стадии сделки** (отказ / закрыта / заключен). **ЕФС** — только в `config.json` |

### Отбор TOP КМ (`manager_analytics.rank_selection`)

| Поле config | Назначение |
|-------------|------------|
| `product_groups` | Пул групп для TOP-N. `[]` = все |
| `products` | Пул продуктов. `[]` = все |
| `strategy_filter` | `all` · `strategy` · `strategy_2026` · `non_strategy` |

Excel и начальный TOP в UI — по этим настройкам. В JSON всегда попадают **все** лиды (`records[]`); пользователь в дашборде может сузить выбор фильтрами справа и выпадающим списком «Метка (отбор TOP)» в блоке менеджеров.

Подробнее: [CONFIG.md §14](CONFIG.md#14-аналитика-менеджеров-manager_analytics-колонка-km).

После `run.py` в `OUT/` для UI нужен **один** файл: `kanban_report_{timestamp}.json` (monolith: срезы + менеджеры). Excel — отдельно. Каталоги `*_html` при `bundle_mode: monolith` не создаются.

Открыть: `HTML/index.html` (file://), загрузить этот JSON. Сервер не нужен.

Режим Excel — `config.product_analysis_mode`. В JSON — обе агрегации; pipeline-фильтры с `html_slice: true` — комбинации 2^N. ЕФС (`efs_flag`, `html_slice: false`) задаётся только через `enabled` в config.

## Prod-режим

```json
"mode": "prod"
```

22 xlsx в `IN/`, при необходимости снизить нагрузку:

```json
"parallel_workers": 1,
"performance": { "max_parallel_workers": 2, "reserve_cpu_cores": 2 }
```

## Проверка

```bash
python -c "import pandas, openpyxl; print('OK')"
python run.py
python run_excel.py
```

> `pytest src/Tests/` — только в Git-репозитории разработки; в копии POST каталог `src/Tests/` отсутствует.
