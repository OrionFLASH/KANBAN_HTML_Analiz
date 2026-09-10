#!/usr/bin/env python3
"""Добавляет во все карточки CONFIG_EXCEL_V2_PARAMS.md блок допустимых значений."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARAMS = ROOT / "Docs" / "CONFIG_EXCEL_V2_PARAMS.md"

# path → многострочное описание вариантов (markdown внутри ячейки таблицы — через <br>)
VARIANTS: dict[str, str] = {}


def V(path: str, text: str) -> None:
    VARIANTS[path] = text.replace("\n", "<br>")


def seed() -> None:
    V(
        "mode",
        "**Обязательный enum.** "
        "`test` — читать `paths.input_test` + `test_files` (+ team test); "
        "`prod` — читать `paths.input_prod` + `prod_files` (+ team prod). "
        "Другие строки → ошибка валидации (`mode должен быть 'test' или 'prod'`).",
    )
    V("paths", "Объект-контейнер. Значение — словарь ключей `input_test` / `input_prod` / `output` / `log` (строки-пути).")
    V("paths.input_test", "Строка: относительный или абсолютный путь к каталогу. Обычно `IN/TEST`.")
    V("paths.input_prod", "Строка-путь. Обычно `IN/PROD`.")
    V("paths.output", "Строка-путь каталога отчётов. Обычно `OUT/excel_v2`.")
    V("paths.log", "Строка-путь каталога логов. Обычно `log`.")

    V("logging", "Объект: `logger_name`, `info_file_prefix`, `debug_file_prefix`, `hour_format`.")
    V("logging.logger_name", "Любая непустая строка — имя Python-логгера.")
    V("logging.info_file_prefix", "Строка-префикс имени INFO-файла (без расширения).")
    V("logging.debug_file_prefix", "Строка-префикс имени DEBUG-файла.")
    V("logging.hour_format", "Строка `strftime` для суффикса часа, напр. `%Y%m%d_%H`.")

    V("test_files", "Массив строк — имён xlsx. Пустой массив при mode=test недопустим на практике (нечего читать).")
    V("prod_files", "Массив строк — имён xlsx для prod.")

    V("columns", "Объект: ключ внутреннего поля → строка заголовка Excel. Значения — точные имена колонок во входном файле.")
    V(
        "required_column_keys",
        "Массив строк — ключей из `columns`. Каждый должен существовать в `columns` и в шапке файла, иначе ошибка.",
    )
    V(
        "optional_column_keys",
        "Массив строк — ключей из `columns`. Отсутствие колонки в файле не ошибка; наличие — колонка читается.",
    )

    V("excel", "Объект параметров чтения xlsx.")
    V("excel.sheet_name", "Строка — имя вкладки книги (напр. `Sheet1`).")
    V("excel.engine", "Строка движка pandas; штатно только `openpyxl`.")
    V(
        "excel.read_only",
        "**bool.** `true` — openpyxl read_only (меньше RAM); `false` — обычное открытие (больше возможностей API, больше памяти).",
    )
    V(
        "excel.data_only",
        "**bool.** `true` — значения ячеек (как сохранены); `false` — могут попасть формулы как текст (ломает числа/даты). Для отчётов нужен `true`.",
    )
    V(
        "excel.keep_links",
        "**bool.** `false` — не грузить внешние ссылки (быстрее); `true` — пытаться сохранить links (медленнее, может трогать сеть).",
    )
    V("excel.na_values", "Массив строк/значений, которые pandas считает пустыми (NaN), напр. `[\"\"]`.")
    V("excel.category_markers", "Объект маркеров категорий статуса.")
    V("excel.category_markers.for_sale", "Строка-маркер, обычно `К ПРОДАЖЕ`.")
    V("excel.category_markers.in_work", "Строка-маркер, обычно `В РАБОТЕ`.")
    V("excel.category_markers.unknown", "Строка-маркер fallback, обычно `UNKNOWN`.")

    V("processing", "Объект логики дедупа/аудита.")
    V("processing.empty_stage_values", "Массив строк — что считать пустой стадией (не режется terminal exclude).")
    V(
        "processing.dedup_same_date_agg",
        "**Строка агрегата.** Штатно `max` — на одну дату отчёта + стадию берётся максимальный срок. Другие значения не документированы как поддерживаемые в v2.",
    )
    V(
        "processing.pick_across_dates",
        "**Строка правила.** Штатно `max_days_then_latest_report_date`: сначала больший срок, при равенстве — более поздняя дата отчёта.",
    )
    V("processing.group_only_product_label", "Любая строка-подпись колонки «Продукт» при `product_analysis_mode=group_only` (часто `—`).")
    V(
        "processing.audit_row_counts",
        "**bool.** `true` — писать счётчики строк в лог; `false` — не писать аудит числа строк.",
    )
    V(
        "processing.duration_fallback_to_columns",
        "**bool.** Имеет смысл при `duration_source=dates`: `true` — пустая дата → колонка дней; `false` — без fallback (дыры в сроках).",
    )

    V("dates", "Объект парсинга дат.")
    V(
        "dates.dayfirst",
        "**bool.** `true` — неоднозначные даты как ДД.ММ; `false` — ММ.ДД (US-стиль).",
    )
    V("dates.excel_origin", "Строка даты-эпохи для serial Excel, обычно `1899-12-30`.")
    V("dates.formats", "Массив строк `strptime` по приоритету, напр. `%d.%m.%Y`, `%Y-%m-%d`.")
    V("dates.empty_values", "Массив маркеров пустой даты (`\"\"`, `-`, `nan`, …).")

    V(
        "duration_source",
        "**Enum:** `columns` — срок из колонки `days_on_stage`; "
        "`dates` — считать из дат (с возможным fallback). "
        "Иное → ошибка валидации.",
    )
    V(
        "stage_analysis_mode",
        "**Enum:** `status` — только Текущий статус (типично для Excel v2); "
        "`substages` — подстадии сделки; "
        "`both` — оба разреза. "
        "Иное → ошибка.",
    )
    V(
        "product_analysis_mode",
        "**Enum:** `group_product` — группа + продукт; "
        "`group_only` — только группа (продукт = `group_only_product_label`). "
        "Иное → ошибка.",
    )
    V(
        "percentiles",
        "Массив чисел 0–100 (обычно `[20, 50, 80]`). Каждый элемент должен согласовываться с `output.statistics.percentiles[].p` и может использоваться в `exceedance.percentile`.",
    )
    V("exceedance", "Объект с ключом `percentile`.")
    V(
        "exceedance.percentile",
        "Число из списка `percentiles` (напр. `50` или `80`). Задаёт норму превышения на лидах и день-порог на матрице сроков. Значение вне `percentiles` — логическая ошибка конфигурации.",
    )

    V("aggregation", "Объект: `group_keys`, `metrics`.")
    V("aggregation.group_keys", "Массив ключей группировки (строки-имена полей records), напр. product_group, product, current_status, stage_key.")
    V("aggregation.metrics", "Массив имён метрик; в v2 обычно только `[\"days_on_stage\"]`.")

    V("outlier_clipping", "Объект настроек выбросов.")
    V("outlier_clipping.enabled", "**bool.** `true` — применять rules; `false` — блок выключен.")
    V("outlier_clipping.metric", "Строка — имя колонки срока (обычно `days_on_stage`).")
    V("outlier_clipping.export_audit", "**bool.** `true` — колонки аудита на Нормативах; `false` — без аудита.")
    V("outlier_clipping.min_group_size", "Целое ≥1: минимум строк группы для iqr/trim.")
    V("outlier_clipping.min_remaining", "Целое ≥0: минимум лидов после правила (глобально).")
    V("outlier_clipping.rules", "Массив объектов-правил (см. элементы `rules[i]`).")

    # rule fields via pattern handled in resolve

    V("filters", "Объект: имя_фильтра → объект полей фильтра.")
    # filter fields via pattern

    V("team_files", "Объект настроек команд.")
    V("team_files.enabled", "**bool.** `true` — грузить team-файлы; `false` — без лидеров из файлов.")
    V(
        "team_files.pick_report_date",
        "**Строка.** Штатно поддерживается `latest` (max дата отчёта). Другие значения сейчас не поддерживаются (warning → latest).",
    )
    V("team_files.lead_team", "Объект `{test: [...], prod: [...]}` — legacy списки файлов.")
    V("team_files.lead_team.test", "Массив имён xlsx.")
    V("team_files.lead_team.prod", "Массив имён xlsx (часто `[]`).")
    V("team_files.deal_team", "Как lead_team для сделки.")
    V("team_files.deal_team.test", "Массив имён xlsx.")
    V("team_files.deal_team.prod", "Массив имён xlsx.")
    V("team_files.files", "Объект `{test, prod}` — единый комплект лид+сделка.")
    V("team_files.files.test", "Массив имён xlsx.")
    V("team_files.files.prod", "Массив имён xlsx.")
    V("team_files.leader_values", "Массив значений «истина» для колонки Лидер (`Да`, `1`, `true`, …).")
    V(
        "team_files.keep_leaders_only",
        "**bool.** `true` — сразу отбросить не-лидеров; `false` — читать всех (в v2 участники всё равно не используются в отчёте).",
    )
    V("team_files.columns", "Объект ключ→заголовок входного team xlsx.")
    V("team_files.output_columns", "Объект lead/deal → заголовки в отчёте.")
    V("team_files.output_columns.lead", "Объект подписей лидера лида.")
    V("team_files.output_columns.deal", "Объект подписей лидера сделки.")
    V("team_files.team_type_values", "Объект lead/deal/unassigned → массивы маркеров.")
    V("team_files.team_type_values.lead", "Массив маркеров типа лид, обычно `[1, \"1\"]`.")
    V("team_files.team_type_values.deal", "Массив маркеров типа сделка, обычно `[2, \"2\"]`.")
    V("team_files.team_type_values.unassigned", "Массив маркеров «не взят», обычно `[\"-\", \"—\", \"\"]`.")

    V("manager_emails", "Объект CSV-почт.")
    V("manager_emails.enabled", "**bool.** `true` — подтягивать почты; `false` — колонки пустые.")
    V("manager_emails.directory", "Строка-каталог (часто `IN`).")
    V("manager_emails.filename", "Строка — имя CSV.")
    V("manager_emails.delimiter", "Строка-разделитель CSV (часто `;`).")
    V("manager_emails.encoding", "Строка кодировки (часто `utf-8-sig`).")
    V("manager_emails.columns", "Объект имён колонок CSV.")
    V("manager_emails.columns.tab_number", "Строка — заголовок ТН.")
    V("manager_emails.columns.email_alpha", "Строка — заголовок почты Альфа.")
    V("manager_emails.columns.email_sigma", "Строка — заголовок почты Сигма.")
    V("manager_emails.output_columns", "Объект lead/deal → заголовки почт в xlsx.")
    V("manager_emails.output_columns.lead", "Объект email_alpha/email_sigma.")
    V("manager_emails.output_columns.deal", "Объект email_alpha/email_sigma.")

    V("client_display", "Объект сокращений юрформ.")
    V("client_display.enabled", "**bool.** `true` — сокращать; `false` — сырой текст Клиент.")
    V("client_display.abbreviations", "Массив `{match, replace}`; порядок важен (длинные формы выше).")

    V("output", "Объект настроек отчёта.")
    V("output.report_prefix", "Строка-префикс имени файла.")
    V("output.timestamp_format", "Строка `strftime` для метки времени в имени.")
    V(
        "output.report_parts",
        "**Enum / список / синонимы.** "
        "`both` (также `all`, `оба`, `все`, `analytics+detail`) — оба файла; "
        "`analytics` (также `norms`, `нормативы`, `1`, …) — только analytics (нормативы/статистика/матрицы), без команд/detail; "
        "`detail` (также `leads`, `лиды`, `2`, …) — только detail (ID/менеджеры/нарушения), без матриц/воронки на экспорт; "
        "или список `['analytics','detail']`. Пусто/неизвестно → ошибка.",
    )
    V("output.report_part_suffixes", "Объект суффиксов имён файлов.")
    V("output.report_part_suffixes.analytics", "Строка суффикса (обычно `analytics`).")
    V("output.report_part_suffixes.detail", "Строка суффикса (обычно `detail`).")
    V("output.all_tb_label", "Строка подписи агрегата «все ТБ».")
    V("output.excel_max_sheet_name_length", "Целое, обычно `31` (лимит Excel).")
    V("output.excel_max_rows_per_sheet", "Целое ≥1: порог строк → CSV overflow (часто `900000`).")
    V("output.csv_overflow", "Объект overflow CSV.")
    V("output.csv_overflow.enabled", "**bool.** `true` — писать CSV при превышении; `false` — риск ошибки Excel.")
    V("output.csv_overflow.delimiter", "Строка-разделитель CSV.")
    V("output.csv_overflow.encoding", "Строка кодировки CSV.")
    V("output.sheets", "Объект ключ_листа → строка имени вкладки.")
    V("output.sheet_freeze", "Объект ключ_листа → `{last_row, last_col}` (+ `default`).")
    V("output.sheet_freeze.default", "Объект freeze по умолчанию.")
    V("output.sheet_freeze.default.last_row", "Целое ≥0: последняя закреплённая строка (`1` = шапка).")
    V("output.sheet_freeze.default.last_col", "Целое ≥0 или буква столбца; `0` = не фиксировать столбцы.")

    V("output.duration_matrix", "Объект настроек матриц сроков.")
    V("output.duration_matrix.enabled", "**bool.** `true` — строить матрицы; `false` — не строить.")
    V(
        "output.duration_matrix.sort_mode",
        "**Enum:** `by_volume` — дни по убыванию числа лидов, строки сверху с максимумом лидов; "
        "`alpha_days` — дни по возрастанию, группы/продукты А→Я; "
        "`group_alpha_product_volume` — дни ↑, группы А→Я, внутри продукты по убыванию лидов. "
        "Неизвестный → fallback `by_volume` + warning.",
    )
    V("output.duration_matrix.variants", "Массив объектов `{sheet_key, sort_mode, include_status}`.")
    V("output.duration_matrix.total_column_label", "Строка подписи столбца итога.")
    V("output.duration_matrix.day_column_width", "Число — ширина колонок дней.")
    V("output.duration_matrix.percentile_column_width", "Число — ширина колонок P*.")
    V("output.duration_matrix.row_height", "Число — высота строк.")
    V("output.duration_matrix.header_row_height", "Число — высота шапки.")
    V("output.duration_matrix.filter_row_height", "Число — высота служебной строки.")
    V("output.duration_matrix.counts_font_size", "Число — кегль чисел.")
    V("output.duration_matrix.header_fill", "HEX-цвет заливки шапки без `#`, напр. `FFF2CC`.")
    V("output.duration_matrix.filter_row_font_color", "HEX цвет шрифта служебной строки.")
    V("output.duration_matrix.grid_border_color", "HEX цвет сетки.")
    V("output.duration_matrix.threshold_border_color", "HEX цвет рамки дня-порога exceedance.")
    V("output.duration_matrix.max_day_span", "Целое — макс. число колонок дней.")
    V("output.duration_matrix.label_column_widths", "Объект A/B/C/D/total → числа ширин.")
    for colk in ("A", "B", "C", "D", "total"):
        V(f"output.duration_matrix.label_column_widths.{colk}", "Число — ширина колонки openpyxl.")
    V("output.duration_matrix.color_scale", "Объект start/mid/end HEX.")
    V("output.duration_matrix.color_scale.start", "HEX малых значений.")
    V("output.duration_matrix.color_scale.mid", "HEX середины.")
    V("output.duration_matrix.color_scale.end", "HEX больших значений.")

    V("output.column_labels", "Объект внутренних ключей → строки заголовков.")
    V("output.percentile_column_labels", "Объект метрик → шаблоны с `{p}`.")
    V("output.percentile_column_labels.days_on_stage", "Объект suffix → шаблон строки.")
    for suf in ("days", "count", "min", "max", "le_count", "gt_count", "km_count"):
        V(
            f"output.percentile_column_labels.days_on_stage.{suf}",
            "Строка-шаблон с плейсхолдером `{p}` (подставится 20/50/80).",
        )

    V("output.statistics", "Объект флагов расчёта/экспорта метрик.")
    V(
        "output.statistics.attach_counts_left",
        "**bool.** `true` — порядок колонок `le_count | days | gt_count`; `false` — сначала `days`, потом счётчики.",
    )
    V("output.statistics.min", "Объект флагов минимума.")
    V("output.statistics.max", "Объект флагов максимума.")
    V("output.statistics.total_count", "Объект флагов числа лидов.")
    for block in ("min", "max"):
        V(f"output.statistics.{block}.compute", "**bool.** `true` — считать; `false` — не считать.")
        V(f"output.statistics.{block}.export", "**bool.** `true` — колонка в Excel; `false` — скрыть (даже если посчитано).")
        V(f"output.statistics.{block}.export_le_count", "**bool.** `true` — доп. колонка счётчика ≤; `false` — нет.")
        V(f"output.statistics.{block}.export_gt_count", "**bool.** `true` — доп. колонка счётчика >; `false` — нет.")
    V("output.statistics.total_count.compute", "**bool.** `true`/`false` — считать число лидов.")
    V("output.statistics.total_count.export", "**bool.** `true`/`false` — показать «Число лидов».")
    V("output.statistics.percentiles", "Массив профилей `{p, compute, export_*}`.")

    V("output.excel_format", "Объект форматов Excel.")
    V("output.excel_format.freeze_panes", "Строка ячейки freeze fallback, напр. `A2`.")
    V("output.excel_format.float_format", "Строка формата float, напр. `0.00`.")
    V("output.excel_format.int_format", "Строка формата int, напр. `0`.")
    V("output.excel_format.date_format", "Строка формата дат Excel, напр. `YYYY-MM-DD`.")
    V("output.excel_format.thousands_format", "Строка формата тысяч, напр. `# ##0`.")
    V("output.excel_format.max_column_width", "Число — потолок автоширины.")
    V("output.excel_format.min_column_width", "Число — минимум автоширины.")
    V("output.excel_format.sample_rows_for_width", "Целое — сколько строк смотреть для ширины.")
    V("output.excel_format.hotspots_column_width", "Число — ширина многострочных колонок.")
    V("output.excel_format.light_format_sheets", "Массив ключей листов без полного оформления, напр. `[\"leads\",\"violations\"]`.")
    V("output.excel_format.colors", "Объект min/max HEX.")
    V("output.excel_format.colors.min", "HEX заливки заголовка Мин.")
    V("output.excel_format.colors.max", "HEX заливки заголовка Макс.")

    V("output.snapshot_columns", "Объект ключ→заголовок; порядок ключей = порядок колонок снимка.")
    V("output.status_duration_columns", "Объект колонок сроков по статусам.")
    V("output.status_duration_columns.enabled", "**bool.** `true` — вставлять колонки; `false` — нет.")
    V("output.status_duration_columns.include_others", "**bool.** `true` — статусы вне order; `false` — только order.")
    V(
        "output.status_duration_columns.others_sort",
        "**Строка.** `alpha` (также `az`, `a-z`, `ая`, `а→я`) — прочие статусы А→Я. Иное — без спец. сортировки alpha.",
    )
    V("output.status_duration_columns.order", "Массив строк — канонические имена статусов-колонок.")
    V("output.exceedance_columns", "Объект заголовков превышения.")
    V("output.exceedance_columns.p80_norm", "Строка с `{p}` — заголовок норматива.")
    V("output.exceedance_columns.current_days", "Строка заголовка текущего срока.")
    V("output.exceedance_columns.exceedance_flag", "Строка заголовка флага.")
    V("output.exceedance_columns.exceedance_days", "Строка заголовка дней отклонения.")

    V(
        "excel_theme",
        "**Enum:** `green_red` — заливка заголовков Мин/Макс цветами из `excel_format.colors`; "
        "`minimal` — без этой тематической заливки. Иное → ошибка валидации.",
    )
    V(
        "parallel_workers",
        "Целое ≥0. `0` — авто (примерно CPU − `reserve_cpu_cores`, с учётом adaptive); "
        "`≥1` — явное число процессов загрузки Kanban (может быть урезано adaptive при critical).",
    )

    V("performance", "Объект производительности.")
    V("performance.max_parallel_workers", "Целое ≥1 — потолок процессов.")
    V("performance.reserve_cpu_cores", "Целое ≥0 — ядра ОС при авто.")
    V("performance.read_only_required_columns", "**bool.** `true` — usecols только нужные; `false` — читать шире.")
    V("performance.downcast_numeric", "**bool.** `true` — сжимать dtype; `false` — нет.")
    V("performance.free_memory_between_stages", "**bool.** `true` — gc между этапами; `false` — нет.")
    V("performance.compact_distribution_series", "**bool.** Legacy HTML/JSON; на Excel v2 почти не влияет.")
    V("performance.precompute_pivot_matrices", "**bool.** Legacy HTML; в v2 обычно `false`.")
    V("performance.parallel_pipeline_stages", "**bool.** `true` — параллельно снимок+records+teams; `false` — последовательно.")
    V("performance.parallel_stage_workers", "Целое ≥0; `0` = как `parallel_workers`.")
    V("performance.parallel_team_files", "**bool.** `true` — параллельно читать team-файлы; `false` — по одному.")
    V("performance.adaptive_resources", "Объект автолимитов RAM.")

    for key, text in {
        "enabled": "**bool.** `true` — мониторинг RAM и автолимиты; `false` — не вмешиваться.",
        "min_available_ram_gb": "Число ГБ: свободная RAM ниже → warn.",
        "critical_available_ram_gb": "Число ГБ: свободная RAM ниже → critical.",
        "warn_used_ram_percent": "Число 0–100: занято ≥% → warn.",
        "critical_used_ram_percent": "Число 0–100: занято ≥% → critical.",
        "sequential_load_below_total_ram_gb": "Число ГБ: если всего RAM меньше — low-RAM режим.",
        "low_ram_max_workers": "Целое — потолок workers в low-RAM.",
        "low_ram_disable_parallel_stages": "**bool.** выкл stages в low-RAM.",
        "low_ram_disable_parallel_teams": "**bool.** выкл parallel teams в low-RAM.",
        "warn_max_workers": "Целое — потолок workers при warn.",
        "warn_disable_parallel_stages": "**bool.** выкл stages при warn.",
        "critical_max_workers": "Целое — потолок workers при critical (часто 1).",
        "critical_disable_parallel_stages": "**bool.** выкл stages при critical.",
        "critical_disable_parallel_teams": "**bool.** выкл teams при critical.",
        "input_size_per_worker_gb": "Число ГБ — эвристика размера входа на worker.",
        "gc_on_pressure": "**bool.** gc при warn/critical.",
        "override_explicit_workers_on_critical": "**bool.** резать явный parallel_workers при critical.",
        "disable_html_slices_on_critical": "**bool.** Legacy HTML; на v2 не влияет.",
    }.items():
        V(f"performance.adaptive_resources.{key}", text)

    V("progress", "Объект прогресса.")
    V("progress.enabled", "**bool.** `true` — прогресс в консоли; `false` — тише.")
    V("progress.log_every_seconds", "Число секунд ≥0 — интервал heartbeat.")
    V("progress.show_timing_summary", "**bool.** `true` — сводка времени в конце; `false` — нет.")
    V("progress.debug_detail", "**bool.** `true` — тайминги подэтапов в DEBUG; `false` — нет.")


def resolve_variants(path: str) -> str:
    if path in VARIANTS:
        return VARIANTS[path]

    # columns.*
    if re.fullmatch(r"columns\.[^.]+", path):
        return "Строка — точный заголовок колонки во входном Kanban Excel."

    # filters.<name>
    if re.fullmatch(r"filters\.[^.]+", path):
        return "Объект полей фильтра (`enabled`, `column_key`, `action`, `match`, `values`, …). См. вложенные ключи."

    m = re.fullmatch(r"filters\.[^.]+\.([^.]+)", path)
    if m:
        field = m.group(1)
        return {
            "enabled": "**bool.** `true` — фильтр в AND; `false` — полностью выключен.",
            "column_key": "Строка — ключ из `columns` (основная колонка).",
            "column_keys": "Массив ключей из `columns` (OR с основной); может быть `[]`.",
            "action": "**Enum:** `include` — оставить совпавшие строки; `exclude` — убрать совпавшие (терминальные — после include).",
            "match": "**Enum:** `equals` — целое поле равно эталону; `contains` — подстрока.",
            "values": "Массив эталонов (числа/строки/даты согласно `value_type`).",
            "values_mode": "**Enum:** `any` — достаточно одного value; `all` — нужны все (для contains — все подстроки).",
            "value_type": "**Enum:** `string` | `number` | `date` | `auto` (вывести тип по values).",
            "case_sensitive": "**bool.** `true` — учитывать регистр; `false` — сравнивать без регистра.",
        }.get(field, "См. схему универсального фильтра.")

    # outlier rules
    if re.fullmatch(r"outlier_clipping\.rules\[\d+\]", path):
        return "Объект правила: `name`, `enabled`, `scope`, `mode`, параметры режима (`min_days`/`max_days`/`trim_*`/`iqr_k`)."
    m = re.fullmatch(r"outlier_clipping\.rules\[\d+\]\.([^.]+)", path)
    if m:
        field = m.group(1)
        return {
            "name": "Строка — уникальное имя для аудита/колонки.",
            "enabled": "**bool.** `true`/`false` — применять правило.",
            "scope": "Объект `{}` = все группы; иначе ключи product_group/product/current_status/tb → строка или массив.",
            "mode": "**Enum:** `range` — отсечь вне [min_days, max_days]; "
            "`percentile_trim` — отрезать % хвостов по лидам; "
            "`unique_days_trim` — отрезать % уникальных сроков; "
            "`iqr` — fence Q1−k·IQR … Q3+k·IQR.",
            "min_days": "Число / null — нижняя граница для `range` (можно не задавать).",
            "max_days": "Число / null — верхняя граница для `range`.",
            "min_remaining": "Целое — локальный мин. остаток лидов (опционально).",
            "trim_lower_pct": "Число % снизу для trim-режимов.",
            "trim_upper_pct": "Число % сверху для trim-режимов.",
            "iqr_k": "Число — множитель IQR (обычно `1.5`).",
        }.get(field, "Параметр правила выбросов.")
    if re.match(r"outlier_clipping\.rules\[\d+\]\.scope(\.|$)", path):
        if path.endswith(".scope"):
            return "Объект: пустой `{}` или поля-ограничения (строка/массив значений)."
        return "Строка или массив строк — допустимые значения поля группы для срабатывания правила."

    # abbreviations
    if re.fullmatch(r"client_display\.abbreviations\[\d+\]", path):
        return "Объект `{match: строка полной формы, replace: строка аббревиатуры}`."
    if re.fullmatch(r"client_display\.abbreviations\[\d+\]\.match", path):
        return "Строка полной юрформы (сравнение префикса без регистра)."
    if re.fullmatch(r"client_display\.abbreviations\[\d+\]\.replace", path):
        return "Строка краткой формы (ООО, АО, СЗ, …)."

    # variants
    if re.fullmatch(r"output\.duration_matrix\.variants\[\d+\]", path):
        return "Объект `{sheet_key: ключ из sheets, sort_mode: enum сортировки, include_status: bool}`."
    m = re.fullmatch(r"output\.duration_matrix\.variants\[\d+\]\.([^.]+)", path)
    if m:
        field = m.group(1)
        return {
            "sheet_key": "Строка — ключ из `output.sheets` (имя вкладки берётся оттуда).",
            "sort_mode": "Как у `duration_matrix.sort_mode`: `by_volume` | `alpha_days` | `group_alpha_product_volume`.",
            "include_status": "**bool.** `true` — колонка статуса после продукта (+ freeze last_col 7); `false` — без статуса.",
        }.get(field, "Поле variant матрицы.")

    # statistics percentiles
    if re.fullmatch(r"output\.statistics\.percentiles\[\d+\]", path):
        return "Объект профиля: `p` (число) + флаги `compute` / `export_*` (bool)."
    m = re.fullmatch(r"output\.statistics\.percentiles\[\d+\]\.([^.]+)", path)
    if m:
        field = m.group(1)
        return {
            "p": "Число перцентиля 0–100 (обычно 20, 50 или 80); должно быть согласовано с корневым `percentiles`.",
            "compute": "**bool.** `true` — считать перцентиль; `false` — пропуск в агрегации.",
            "export_days": "**bool.** `true` — колонка порога в днях; `false` — не выводить.",
            "export_count": "**bool.** `true` — колонка размера нижней доли; `false` — нет.",
            "export_le_count": "**bool.** `true` — колонка «лидов ≤»; `false` — нет.",
            "export_gt_count": "**bool.** `true` — колонка «лидов >»; `false` — нет.",
            "export_min": "**bool.** `true` — мин в нижней доле; `false` — нет.",
            "export_max": "**bool.** `true` — макс в нижней доле; `false` — нет.",
            "export_km_count": "**bool.** `true` — колонка уник. КМ ≥ порога (значение заполняется для **P80**); `false` — нет колонки.",
        }.get(field, "Флаг/поле профиля перцентиля.")

    # sheets
    if re.fullmatch(r"output\.sheets\.[^.]+", path):
        return "Строка — имя вкладки Excel (длина ≤ `excel_max_sheet_name_length`, обычно 31)."

    # sheet_freeze
    if re.fullmatch(r"output\.sheet_freeze\.[^.]+", path):
        return "Объект `{last_row: int, last_col: int|буква}`."
    if re.fullmatch(r"output\.sheet_freeze\.[^.]+\.last_row", path):
        return "Целое ≥0: последняя закреплённая строка (`1` = шапка)."
    if re.fullmatch(r"output\.sheet_freeze\.[^.]+\.last_col", path):
        return "Целое ≥0 или буква столбца (`0` = не фиксировать; `3`/`C` = A–C; `7` при статусе на матрице)."

    # snapshot / column_labels / team columns / emails output
    if re.fullmatch(r"output\.snapshot_columns\.[^.]+", path):
        return "Строка — заголовок колонки на листе «Уникальные ID»."
    if re.fullmatch(r"output\.column_labels\.[^.]+", path):
        return "Строка — подпись колонки/маркера на «Нормативах» (или маркер темы Мин/Макс)."
    if re.fullmatch(r"team_files\.columns\.[^.]+", path):
        return "Строка — заголовок колонки во входном team-файле."
    if re.fullmatch(r"team_files\.output_columns\.(lead|deal)\.[^.]+", path):
        return "Строка — заголовок колонки лидера в отчёте detail."
    if re.fullmatch(r"manager_emails\.output_columns\.(lead|deal)\.[^.]+", path):
        return "Строка — заголовок колонки почты в отчёте."

    # generic fallbacks by suffix/type hints
    leaf = path.split(".")[-1]
    if leaf in {"enabled", "compute", "export", "export_audit", "keep_leaders_only", "include_status", "include_others", "case_sensitive", "attach_counts_left", "data_only", "read_only", "keep_links", "dayfirst", "audit_row_counts", "duration_fallback_to_columns", "show_timing_summary", "debug_detail", "gc_on_pressure"} or leaf.startswith("export_") or leaf.startswith("low_ram_disable_") or leaf.startswith("warn_disable_") or leaf.startswith("critical_disable_") or leaf in {"override_explicit_workers_on_critical", "disable_html_slices_on_critical", "parallel_pipeline_stages", "parallel_team_files", "downcast_numeric", "free_memory_between_stages", "compact_distribution_series", "precompute_pivot_matrices", "read_only_required_columns"}:
        return "**bool.** `true` / `false` — см. «Зачем»/«Как работает» карточки: включает или выключает соответствующее поведение."

    return (
        "См. тип значения в актуальном config (строка / число / bool / массив / объект). "
        "Допустимый диапазон — по смыслу поля; неверные enum обычно дают ошибку валидации или warning+fallback (см. «Как работает»)."
    )


def inject() -> None:
    seed()
    text = PARAMS.read_text(encoding="utf-8")
    # bump version
    text = text.replace("**Версия документа:** 3.0.0", "**Версия документа:** 3.1.0")
    if "Допустимые значения" not in text.split("## Оглавление", 1)[0]:
        text = text.replace(
            "Карточка на **каждый** ключ актуального конфига:",
            "Карточка на **каждый** ключ актуального конфига (включая **допустимые значения / варианты** и эффект каждого):",
        )

    parts = re.split(r"(?=^### `)", text, flags=re.M)
    header, cards = parts[0], parts[1:]
    out_cards: list[str] = []
    missing = 0
    for card in cards:
        m = re.search(r"^### `([^`]+)`", card, re.M)
        if not m:
            out_cards.append(card)
            continue
        path = m.group(1)
        variants = resolve_variants(path)
        if "универсальн" in variants or variants.startswith("См. тип значения"):
            # still counts as filled
            pass
        row = f"| **Допустимые значения / варианты** | {variants} |"
        if "**Допустимые значения / варианты**" in card:
            card = re.sub(
                r"\| \*\*Допустимые значения / варианты\*\* \|.*?\|",
                row,
                card,
                count=1,
                flags=re.S,
            )
        else:
            # insert before Значение в актуальном config
            if "| **Значение в актуальном config** |" in card:
                card = card.replace(
                    "| **Значение в актуальном config** |",
                    row + "\n| **Значение в актуальном config** |",
                    1,
                )
            else:
                missing += 1
                card = card.rstrip() + "\n" + row + "\n\n"
        out_cards.append(card)

    # ensure mode example is rich (already in VARIANTS)
    new_text = header + "".join(out_cards)
    # update completeness section note
    if "Допустимые значения" not in new_text[-800:]:
        new_text += "\n\nКаждая карточка содержит строку **Допустимые значения / варианты**.\n"

    PARAMS.write_text(new_text, encoding="utf-8")
    # verify
    md = PARAMS.read_text(encoding="utf-8")
    cards_n = md.count("### `")
    var_n = md.count("**Допустимые значения / варианты**")
    print(f"cards={cards_n} variant_rows={var_n} inject_missing_slot={missing}")
    if cards_n != var_n:
        raise SystemExit("Не у всех карточек есть строка вариантов")


if __name__ == "__main__":
    inject()
