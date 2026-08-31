# Перенос проекта на другой ПК (без Git)

**Версия архива:** 1.0.4 (2026-08-31)

Инструкция для работы после пересылки по почте или архивом.

## Архив для почты

Готовый zip: **`POST/KANBAN_HTML_Analiz.zip`** (обновляется при релизах).

Содержит **Python pipeline + HTML-дашборд** (каталог `HTML/`).

## Минимальный набор файлов (код + конфиг)

```
KANBAN_HTML_Analiz/
├── config.json
├── run.py
├── README.md
├── ROADMAP.md
├── .env.example
├── src/
│   ├── main.py
│   ├── excel_loader.py
│   ├── lead_tracker.py
│   ├── aggregator.py
│   ├── filter_slices.py
│   ├── manager_analytics.py
│   ├── visualization_data.py
│   ├── json_exporter.py
│   ├── excel_exporter.py
│   ├── pivot_excel.py
│   ├── progress.py
│   └── Tests/
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

**Не включать:** `.git/`, `log/`, `OUT/`, `IN/`, `Docs/FileIN/`, `POST/`, `__pycache__/`

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
7. Дашборд:

```bash
cd HTML && python -m http.server 8080
# http://localhost:8080 — загрузка JSON через левую панель
```

## HTML-дашборд

| Раздел | Описание |
|--------|----------|
| Левая панель | Загрузка JSON (manifest + managers), **pipeline-фильтры**, агрегация, режим графика |
| Правая панель | Мультивыбор ТБ, групп, продуктов (поиск, сворачивание) |
| Графики линий | «По продуктам/группам», «По ТБ» — кривые «лиды × дни» |
| Графики КМ | «КМ с нарушениями P80: по ТБ» / «… по группам/продуктам» — bar-chart |
| Матрица | Группа/продукт × стадия; сортировка по клику |
| BOTTOM менеджеры | Топ-N КМ по `rank_selection` (config); полные `records` в JSON; в UI — группы/продукты + метка стратегии; клик → детальная карточка (hotspots) |
| Pipeline-фильтры | ВКЛ/ВЫКЛ: изменение условий, ввод данных, метки. **ЕФС** — только в `config.json` |

### Отбор TOP КМ (`manager_analytics.rank_selection`)

| Поле config | Назначение |
|-------------|------------|
| `product_groups` | Пул групп для TOP-N. `[]` = все |
| `products` | Пул продуктов. `[]` = все |
| `strategy_filter` | `all` · `strategy` · `strategy_2026` · `non_strategy` |

Excel и начальный TOP в UI — по этим настройкам. В JSON всегда попадают **все** лиды (`records[]`); пользователь в дашборде может сузить выбор фильтрами справа и выпадающим списком «Метка (отбор TOP)» в блоке менеджеров.

Подробнее: [CONFIG.md §14](CONFIG.md#14-аналитика-менеджеров-manager_analytics-колонка-km).

После `run.py` JSON только в `OUT/` (с timestamp). Split-bundle: `OUT/kanban_report_{timestamp}_html/` (manifest + `slices/`). Копии `*_latest*` не создаются.

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
python -m pytest src/Tests/ -q
python run.py
```
