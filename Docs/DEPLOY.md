# Перенос проекта на другой ПК (без Git)

**Версия копии POST:** 1.0.7 (2026-08-31)

Инструкция для работы после пересылки по почте или копированием каталога.

## Каталог POST (без zip)

Актуальная копия проекта: **`POST/KANBAN_HTML_Analiz/`** (обновляется при релизах).

Содержит **Python pipeline + HTML-дашборд** (каталог `HTML/`). Архив `.zip` **не** формируется — только зеркало структуры с файлами.

**Не входит в POST:** `src/Tests/` (тесты только в Git-репозитории).

## Минимальный набор файлов (код + конфиг)

```
KANBAN_HTML_Analiz/
├── config.json
├── run.py
├── README.md
├── ROADMAP.md
├── .env.example
├── src/                           # без каталога Tests/
│   ├── main.py
│   ├── excel_loader.py
│   ├── lead_tracker.py
│   ├── aggregator.py
│   ├── filter_slices.py
│   ├── manager_analytics.py
│   ├── visualization_data.py
│   ├── json_exporter.py
│   ├── excel_exporter.py
│   └── …
├── HTML/                          # ← дашборд (обязательно)
│   ├── index.html
│   ├── css/
│   │   └── dashboard.css
│   └── js/
│       ├── data.js
│       ├── icons.js
│       ├── multi-filter.js
│       ├── managers.js
│       ├── charts.js
│       ├── pivot.js
│       └── app.js
└── Docs/
    ├── CONFIG.md
    ├── DEPLOY.md
    └── BT_KANBAN.md
```

**Не включать:** `.git/`, `log/`, `OUT/`, `IN/`, `Docs/FileIN/`, `POST/`, `src/Tests/`, `__pycache__/`

## Данные Excel (отдельно)

| Режим | Каталог | Файлы |
|-------|---------|-------|
| test | `Docs/FileIN/` | `2ГОСБ1ТБ.xlsx` |
| prod | `IN/` | 22 файла из `config.json` → `prod_files` |

## Настройка на новом ПК

1. Python 3.12 + `pandas`, `openpyxl`
2. Распаковать архив
3. Создать пустые: `IN/`, `OUT/`, `log/`, `Docs/FileIN/`
4. Положить xlsx
5. Настроить `config.json` — см. [CONFIG.md](CONFIG.md)
6. `python run.py` → файлы в `OUT/`
7. Дашборд: открыть `HTML/index.html` в браузере (file://), загрузить `OUT/kanban_report_*.json`. Сервер не нужен.

## HTML-дашборд

| Раздел | Описание |
|--------|----------|
| Левая панель | Загрузка **одного** JSON (monolith), **pipeline-фильтры**, агрегация, режим графика |
| Правая панель | Мультивыбор ТБ, групп, продуктов (поиск, сворачивание) |
| Вкладки | **Графики** · **Сводная матрица** · **Менеджеры** (опционально, `show_managers_tab: true`) |
| Графики линий | «По продуктам/группам», «По ТБ» — кривые «лиды × дни» |
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
```

> `pytest src/Tests/` — только в Git-репозитории разработки; в копии POST каталог `src/Tests/` отсутствует.
