# Перенос проекта на другой ПК (без Git)

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
│       ├── multi-filter.js
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
| test | `Docs/FileIN/` | `2ГОСБ1TБ.xlsx` |
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
# Рекомендуется: сервер из HTML/ (после run.py JSON уже в HTML/data/)
cd HTML && python -m http.server 8080
# http://localhost:8080 — автозагрузка data/kanban_report_latest.json

# Или из корня проекта:
python -m http.server 8080
# http://localhost:8080/HTML/ — автозагрузка из OUT/ или HTML/data/
```

## HTML-дашборд

| Раздел | Описание |
|--------|----------|
| Левая панель | Загрузка JSON, режим графика, метрика, показатель матрицы |
| Правая панель | Мультивыбор ТБ, групп, продуктов (поиск, сворачивание) |
| Графики | Режим «свод + каждый»: сверху все выбранные сущности, ниже — по одной карточке |
| Режим «По ТБ» | Графики в **одну колонку** (друг под другом) |
| Матрица | Группа/продукт × стадия; сортировка по клику на заголовок колонки |
| Pipeline-фильтры | Если при `run.py` были `filters.enabled=true` — баннер вверху вкладки «Графики» |

Режим `product_analysis_mode: group_only` — агрегация и графики по **группам**, фильтр продуктов скрыт.

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
