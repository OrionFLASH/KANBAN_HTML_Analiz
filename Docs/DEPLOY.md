# Перенос проекта на другой ПК (без Git)

Инструкция для работы после пересылки по почте или архивом.

## Минимальный набор файлов (код + конфиг)

Передайте **архивом** (zip) следующую структуру:

```
KANBAN_HTML_Analiz/
├── config.json
├── run.py
├── README.md
├── ROADMAP.md
├── .env.example          # опционально
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config_loader.py
│   ├── logger_setup.py
│   ├── excel_loader.py
│   ├── dictionaries.py
│   ├── lead_tracker.py
│   ├── filters.py
│   ├── aggregator.py
│   ├── excel_exporter.py
│   ├── json_exporter.py
│   └── Tests/
│       └── test_excel_loader.py
└── Docs/
    ├── BT_KANBAN.md
    ├── ToDo KANBAN.txt
    └── DEPLOY.md         # этот файл
```

**Не включать в архив** (создаются локально или содержат данные):

| Каталог / файл | Причина |
|----------------|---------|
| `.git/` | Репозиторий не нужен |
| `log/` | Логи генерируются при запуске |
| `OUT/` | Результаты анализа |
| `IN/` | Prod Excel-файлы (большой объём) |
| `Docs/FileIN/` | Test Excel (~16 МБ, лучше отдельным вложением) |
| `__pycache__/`, `.venv/` | Кэш и окружение |

## Данные Excel (отдельно)

| Режим | Куда положить | Файлы |
|-------|---------------|-------|
| **test** | `Docs/FileIN/` | `2ГОСБ1ТБ.xlsx` (+ опционально `2ГОСБ1ТБ SHORT.xlsx`) |
| **prod** | `IN/` | 22 файла Kanban (имена — в `config.json` → `prod_files`) |

> Test-файлы большие (~10–16 МБ). Если почта не пропускает — облако / USB.

## Настройка на новом ПК

1. **Python 3.12** или **Anaconda** с пакетами `pandas`, `openpyxl` (без pip, если недоступен).
2. Распаковать архив в любую папку, например `C:\Projects\KANBAN_HTML_Analiz`.
3. Создать пустые каталоги (если их нет):
   ```
   IN/
   OUT/
   log/
   Docs/FileIN/
   ```
4. Скопировать Excel-файлы в `Docs/FileIN/` или `IN/` (см. выше).
5. При необходимости отредактировать `config.json` (`mode`, пути, фильтры).
6. Запуск из корня проекта:
   ```bash
   python run.py
   ```
7. Результаты появятся в `OUT/kanban_report_YYYYMMDD_HHMMSS.xlsx` и `.json`.

## Проверка окружения

```bash
python -c "import pandas, openpyxl; print('OK')"
python -m unittest src.Tests.test_excel_loader -v
```

## Prod-режим

В `config.json`:
```json
"mode": "prod"
```
Положить 22 xlsx в `IN/`, запустить `python run.py`.
