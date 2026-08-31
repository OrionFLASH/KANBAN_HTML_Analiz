/** Загрузка и фильтрация данных JSON. */

const KanbanData = (() => {
  let payload = null;
  /** Выбранная агрегация на HTML-странице (не путать с config → Excel). */
  let aggregationMode = "group_product";
  /** Активные pipeline-фильтры (имена из config.filters). */
  let activePipelineFilters = [];
  /** split-bundle: кэш загруженных срезов, базовый URL каталога slices/. */
  let bundleMode = "monolith";
  let slicesBase = "slices/";
  const sliceCache = {};

  function isSplitBundle() {
    return bundleMode === "split";
  }

  function getSlicesBase() {
    return slicesBase;
  }

  function defaultActivePipelineFilters() {
    const catalog = filterCatalog();
    const fromCatalog = catalog.filter((item) => item.default_active).map((item) => item.name);
    if (fromCatalog.length) return normalizeExclusivePipelineFilters(fromCatalog);
    const defaultSlice =
      payload?.visualizations?.default_view?.filter_slice || payload?.meta?.default_slice;
    if (defaultSlice && defaultSlice !== "none") {
      return normalizeExclusivePipelineFilters(defaultSlice.split("+"));
    }
    return [];
  }

  function _initFromPayload(data) {
    payload = data;
    const defaultAgg =
      payload?.visualizations?.default_view?.aggregation ||
      payload?.visualizations?.excel_product_analysis_mode ||
      "group_product";
    aggregationMode = availableAggregationModes().includes(defaultAgg) ? defaultAgg : "group_product";
    activePipelineFilters = defaultActivePipelineFilters();
  }

  function loadJson(text) {
    const data = JSON.parse(text);
    if (data?.meta?.json_bundle_mode === "split") {
      bundleMode = "split";
      slicesBase = data.meta.slices_base || "slices/";
      Object.keys(sliceCache).forEach((k) => delete sliceCache[k]);
      _initFromPayload(data);
      return payload;
    }
    bundleMode = "monolith";
    Object.keys(sliceCache).forEach((k) => delete sliceCache[k]);
    _initFromPayload(data);
    return payload;
  }

  function clearPayload() {
    payload = null;
    aggregationMode = "group_product";
    activePipelineFilters = [];
    bundleMode = "monolith";
    slicesBase = "slices/";
    Object.keys(sliceCache).forEach((k) => delete sliceCache[k]);
  }

  async function ensureSlice(key) {
    if (!isSplitBundle()) {
      return filterSliceData();
    }
    const sliceKey = key || resolveFilterSliceKey();
    if (sliceCache[sliceKey]) {
      if (!payload.visualizations.filter_slices) payload.visualizations.filter_slices = {};
      payload.visualizations.filter_slices[sliceKey] = sliceCache[sliceKey];
      return sliceCache[sliceKey];
    }
    const base = slicesBase.endsWith("/") ? slicesBase : `${slicesBase}/`;
    const url = `${base}${sliceKey}.json`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`Не удалось загрузить срез «${sliceKey}» (${response.status})`);
    }
    const data = await response.json();
    const slice = { ...data };
    delete slice.key;
    sliceCache[sliceKey] = slice;
    if (!payload.visualizations.filter_slices) payload.visualizations.filter_slices = {};
    payload.visualizations.filter_slices[sliceKey] = slice;
    return slice;
  }

  async function prepareActiveSlice() {
    return ensureSlice(resolveFilterSliceKey());
  }

  const AGGREGATION_LABELS = {
    group_product: "По продуктам",
    group_only: "По группам",
  };

  const METRIC_LABELS = {
    days_on_stage: "Дни на стадии",
    days_since_deal: "Дни с создания сделки",
  };

  const INDICATOR_LABELS = {
    min: "Мин",
    max: "Макс",
    p20: "П20",
    p50: "П50",
    p80: "П80",
  };

  function setAggregationMode(mode) {
    if (availableAggregationModes().includes(mode)) {
      aggregationMode = mode;
    }
  }

  function getAggregationMode() {
    return aggregationMode;
  }

  function availableAggregationModes() {
    const fromMeta = payload?.meta?.json_aggregation_modes;
    if (fromMeta?.length) return fromMeta;
    const locked = payload?.meta?.product_analysis_mode;
    if (locked) return [locked];
    const sliceAggs = filterSliceData()?.aggregations;
    if (sliceAggs && typeof sliceAggs === "object") {
      const keys = Object.keys(sliceAggs);
      if (keys.length) return keys;
    }
    return ["group_product"];
  }

  function aggregationLabel(mode) {
    return AGGREGATION_LABELS[mode] || mode;
  }

  function filterCatalog() {
    return viz().filter_catalog || payload?.meta?.filter_catalog || [];
  }

  function filterSliceKey(activeNames) {
    if (!activeNames || !activeNames.length) return "none";
    return [...activeNames].sort().join("+");
  }

  function setActivePipelineFilters(names) {
    activePipelineFilters = normalizeExclusivePipelineFilters(names || []);
  }

  /** В одной exclusive_group — не больше одного фильтра (метки Стратегия / 2026). */
  function normalizeExclusivePipelineFilters(names) {
    const catalog = filterCatalog();
    const result = [];
    const takenGroup = new Set();
    // Идём с конца: последний выбранный в группе побеждает
    for (const name of [...names].reverse()) {
      const item = catalog.find((c) => c.name === name);
      const group = item?.exclusive_group;
      if (group) {
        if (takenGroup.has(group)) continue;
        takenGroup.add(group);
      }
      result.push(name);
    }
    return result.reverse().sort();
  }

  function getActivePipelineFilters() {
    return [...activePipelineFilters];
  }

  function resolveFilterSliceKey() {
    const key = filterSliceKey(activePipelineFilters);
    const slices = viz().filter_slices || {};
    if (slices[key]) return key;
    const manifestKeys = payload?.meta?.slice_keys || payload?.meta?.filter_slice_keys || [];
    if (manifestKeys.includes(key)) return key;
    if (slices.none || manifestKeys.includes("none")) return "none";
    return key;
  }

  function filterSliceData() {
    const key = resolveFilterSliceKey();
    const slices = viz().filter_slices || {};
    if (slices[key]) return slices[key];
    return { aggregations: viz().aggregations, label: "Без pipeline-фильтров", active_filters: [] };
  }

  /** Срез visualizations для текущей HTML-агрегации и pipeline-фильтров. */
  function aggSlice() {
    const slice = filterSliceData();
    const aggs = slice.aggregations || viz().aggregations;
    if (aggs && aggs[aggregationMode]) return aggs[aggregationMode];
    if (aggs && aggs.group_product) return aggs.group_product;
    return viz();
  }

  function isGroupOnly() {
    return aggregationMode === "group_only";
  }

  function getPayload() {
    return payload;
  }

  function rowDimension() {
    return aggSlice().row_dimension || (isGroupOnly() ? "product_group" : "product");
  }

  function rowLabel(series) {
    return series.row_key || (isGroupOnly() ? series.product_group : series.product);
  }

  function viz() {
    return payload?.visualizations || {};
  }

  function allTbLabel() {
    return viz().all_tb_label || "__ALL__";
  }

  function allTbDisplay() {
    return payload?.meta?.all_tb_display || "ВСЕ ТБ";
  }

  const DEFAULT_STAGES_ORDER = [
    "К ПРОДАЖЕ",
    "ВЫЯВЛЕНИЕ ПОТРЕБНОСТИ",
    "ОБСУЖДЕНИЕ УСЛОВИЙ",
    "РЕАЛИЗАЦИЯ СДЕЛКИ",
    "АКТИВАЦИЯ ПРОДУКТА",
    "ПРОДАЖА ЗАВЕРШЕНА",
  ];

  function excludedStages() {
    const fromMeta = payload?.meta?.excluded_stages;
    if (Array.isArray(fromMeta) && fromMeta.length) {
      return fromMeta.map((s) => String(s));
    }
    return [];
  }

  function withoutExcludedStages(stages) {
    const excluded = new Set(excludedStages().map((s) => s.toLowerCase()));
    if (!excluded.size) return stages;
    return stages.filter((s) => !excluded.has(String(s).toLowerCase()));
  }

  function stageOrder() {
    const fromViz = viz().stage_order;
    let order;
    if (Array.isArray(fromViz) && fromViz.length && !(fromViz.length === 2 && fromViz[1] === "В РАБОТЕ")) {
      order = fromViz.map((s) => String(s));
    } else {
      const fromMeta = payload?.meta?.stages_order;
      order =
        Array.isArray(fromMeta) && fromMeta.length
          ? fromMeta.map((s) => String(s))
          : DEFAULT_STAGES_ORDER.slice();
    }
    return withoutExcludedStages(order);
  }

  /** Колонки матрицы: stages_order + стадии из pivot_flat, которых нет в списке. */
  function pivotStageColumns(rows) {
    const order = stageOrder();
    const present = [];
    const seen = new Set();
    const excluded = new Set(excludedStages().map((s) => s.toLowerCase()));
    (rows || pivotFlat()).forEach((row) => {
      const stage = String(row.stage_key || "");
      if (!stage || seen.has(stage)) return;
      if (excluded.has(stage.toLowerCase())) return;
      seen.add(stage);
      present.push(stage);
    });
    const ordered = order.filter((s) => seen.has(s));
    present.forEach((s) => {
      if (!ordered.includes(s)) ordered.push(s);
    });
    return ordered.length ? ordered : order;
  }

  function metrics() {
    return viz().metrics || ["days_on_stage", "days_since_deal"];
  }

  function indicators() {
    return viz().indicators || ["min", "max", "p20", "p50", "p80"];
  }

  function distributionSeries() {
    return aggSlice().distribution_series || [];
  }

  /** Точки графика: из points или компактного days_sorted. */
  function seriesPoints(series) {
    if (series.points?.length) {
      return series.points.map((p) => ({ lead_index: p.lead_index, days: p.days }));
    }
    const days = series.days_sorted || [];
    return days.map((day, idx) => ({ lead_index: idx + 1, days: day }));
  }

  function seriesPointCount(series) {
    if (series.points?.length) return series.points.length;
    return (series.days_sorted || []).length;
  }

  function pivotFlat() {
    return aggSlice().pivot_flat || [];
  }

  function realTbValues() {
    /** Реальные ТБ из данных (без псевдо-сводки __ALL__). */
    const allLabel = allTbLabel();
    const set = new Set();
    distributionSeries().forEach((s) => {
      const tb = String(s.tb);
      if (tb !== allLabel) set.add(tb);
    });
    pivotFlat().forEach((row) => {
      const tb = String(row.tb);
      if (tb !== allLabel) set.add(tb);
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, "ru"));
  }

  function tbOptions() {
    return realTbValues().map((value) => ({
      value,
      label: value,
      icon: "tb",
    }));
  }

  function isTbSelectionAll(selected) {
    const real = realTbValues();
    if (!real.length) return true;
    if (!selected || !selected.length) return true;
    const picked = new Set(selected.map(String).filter((tb) => tb !== allTbLabel()));
    return picked.size === 0 || picked.size >= real.length;
  }

  function uniqueValues(field) {
    const set = new Set();
    distributionSeries().forEach((row) => {
      if (row[field] != null && row[field] !== "") set.add(String(row[field]));
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, "ru"));
  }

  function productGroupMap() {
    /** Группа → множество продуктов (для каскадного фильтра). */
    const map = new Map();
    const placeholder = payload?.meta?.group_only_product_label || "—";

    const addPair = (groupRaw, productRaw) => {
      const group = String(groupRaw || "").trim();
      const product = String(productRaw || "").trim();
      if (!group || !product || product === placeholder) return;
      if (!map.has(group)) map.set(group, new Set());
      map.get(group).add(product);
    };

    // 1) Справочник dimensions.products — полный набор пар группа×продукт
    const dimProducts = payload?.dimensions?.products;
    if (Array.isArray(dimProducts)) {
      dimProducts.forEach((row) => {
        if (!row || typeof row !== "object") return;
        addPair(row.group ?? row.product_group, row.product);
      });
    }
    if (map.size) return map;

    // 2) Активный filter_slice → aggregations.group_product (top-level aggregations часто пуст)
    const sliceAggs = filterSliceData()?.aggregations || {};
    const productSeries =
      sliceAggs.group_product?.distribution_series ||
      viz().aggregations?.group_product?.distribution_series ||
      distributionSeries() ||
      [];
    productSeries.forEach((row) => {
      addPair(row.product_group, row.product);
    });
    return map;
  }

  function productOptionsForGroups(selectedGroups) {
    /** null/[] — все продукты; иначе только продукты выбранных групп. */
    if (!selectedGroups || !selectedGroups.length) {
      const fromMap = productGroupMap();
      if (fromMap.size) {
        const all = new Set();
        fromMap.forEach((set) => set.forEach((p) => all.add(p)));
        return Array.from(all).sort((a, b) => a.localeCompare(b, "ru"));
      }
      return uniqueValues("product");
    }
    const map = productGroupMap();
    const products = new Set();
    selectedGroups.forEach((group) => {
      const items = map.get(String(group));
      if (items) items.forEach((product) => products.add(product));
    });
    return Array.from(products).sort((a, b) => a.localeCompare(b, "ru"));
  }

  function matchesMulti(value, selected) {
    if (!selected || !selected.length) return true;
    return selected.includes(String(value));
  }

  function resolveTbSet(filters) {
    /** Пустой или полный выбор в UI = все ТБ (свод __ALL__ в JSON). */
    const allLabel = allTbLabel();
    let tbs = filters.tbs;
    if (!tbs || !tbs.length) {
      if (filters.tb) tbs = [String(filters.tb)];
      else return [allLabel];
    }
    tbs = tbs.map(String).filter((tb) => tb !== allLabel);
    if (isTbSelectionAll(tbs)) return [allLabel];
    return tbs;
  }

  function matchesTbFilter(seriesTb, filters) {
    const tbSet = resolveTbSet(filters);
    const allLabel = allTbLabel();
    if (tbSet.length === 1 && tbSet[0] === allLabel) return true;
    return tbSet.includes(String(seriesTb));
  }

  function filterSeries(filters) {
    return distributionSeries().filter((series) => {
      if (!matchesTbFilter(series.tb, filters)) return false;
      if (filters.metric && series.metric !== filters.metric) return false;
      if (!matchesMulti(series.product_group, filters.productGroups)) return false;
      if (!matchesMulti(series.product, filters.products)) return false;
      if (filters.stage && String(series.stage_key) !== filters.stage) return false;
      if (filters.level && String(series.analysis_level) !== filters.level) return false;
      return true;
    });
  }

  function tbDisplay(tb) {
    return String(tb) === allTbLabel() ? allTbDisplay() : String(tb);
  }

  function rowDimensionLabel() {
    return isGroupOnly() ? "Группы" : "Продукты";
  }

  function mergeSeriesList(seriesList, template) {
    /** Объединяет кривые лидов в одну отсортированную шкалу дней. */
    const days = [];
    seriesList.forEach((s) => {
      seriesPoints(s).forEach((p) => days.push(p.days));
    });
    days.sort((a, b) => a - b);
    return {
      ...template,
      days_sorted: days,
      total_leads: days.length,
      metric: seriesList[0]?.metric,
      analysis_level: seriesList[0]?.analysis_level,
      _merged: true,
    };
  }

  function uniqueStagesFromSeries(seriesList) {
    const order = stageOrder();
    const excluded = new Set(excludedStages().map((s) => s.toLowerCase()));
    const present = new Set(
      seriesList
        .map((s) => String(s.stage_key))
        .filter((stage) => stage && !excluded.has(stage.toLowerCase()))
    );
    const ordered = order.filter((s) => present.has(s));
    present.forEach((s) => {
      if (!ordered.includes(s)) ordered.push(s);
    });
    return ordered;
  }

  function resolveChartTbs(seriesList, filters) {
    /** ТБ для детальных графиков (без псевдо __ALL__). */
    const allLabel = allTbLabel();
    const fromFilters = resolveTbSet(filters).filter((tb) => tb !== allLabel);
    if (fromFilters.length) {
      return fromFilters.sort((a, b) => a.localeCompare(b, "ru"));
    }
    return [...new Set(seriesList.map((s) => String(s.tb)).filter((tb) => tb !== allLabel))].sort((a, b) =>
      a.localeCompare(b, "ru")
    );
  }

  function chartEligibleSeries(filtered, filters) {
    /** Исключает свод __ALL__, если есть конкретные ТБ. */
    const allLabel = allTbLabel();
    const tbs = resolveTbSet(filters);
    if (tbs.length === 1 && tbs[0] === allLabel) {
      return filtered;
    }
    return filtered.filter((s) => String(s.tb) !== allLabel);
  }

  function filtersApplied() {
    return payload?.meta?.filters_applied || [];
  }

  function configLockedFilters() {
    return payload?.meta?.config_locked_filters || [];
  }

  function filtersActive() {
    return Boolean(payload?.meta?.filters_active) || filtersApplied().length > 0;
  }

  function filtersSummaryLine() {
    const applied = filtersApplied();
    const locked = configLockedFilters();
    const slice = filterSliceData();
    const parts = [];
    if (activePipelineFilters.length) {
      const catalog = filterCatalog();
      const labels = activePipelineFilters.map((name) => {
        const item = catalog.find((c) => c.name === name);
        return item?.html_label || name;
      });
      parts.push(`HTML-фильтры: ${labels.join(" + ")}`);
    } else if (slice.label && viz().filter_slices) {
      parts.push(slice.label);
    }
    if (applied.length) {
      parts.push(
        `Excel (config): ${applied.map((f) => (f.contains ? `${f.name}: «${f.contains}»` : `${f.name}=${f.value}`)).join("; ")}`
      );
    }
    const lockedOn = locked.filter((f) => f.enabled);
    if (lockedOn.length) {
      parts.push(
        `Config-only: ${lockedOn.map((f) => `${f.name}=${f.value}`).join("; ")}`
      );
    }
    if (!parts.length) return "";
    return parts.join(" · ");
  }

  function selectedGroupsHint(filters) {
    if (!isGroupOnly() || !filters?.productGroups?.length) return "";
    return ` · ${filters.productGroups.length} групп`;
  }

  function groupSeriesForCharts(filtered, chartMode, maxSeries, filters) {
    const charts = [];
    const data = chartEligibleSeries(filtered, filters || {});
    if (!data.length) return charts;

    const stages = uniqueStagesFromSeries(data);
    const rowDim = rowDimensionLabel();
    const limit = Math.max(1, maxSeries);

    if (chartMode === "by_tb") {
      const tbs = resolveChartTbs(data, filters || {});

      stages.forEach((stage) => {
        const stageData = data.filter((s) => String(s.stage_key) === stage);

        const summarySeries = tbs
          .map((tb) => {
            const bucket = stageData.filter((s) => String(s.tb) === tb);
            if (!bucket.length) return null;
            return mergeSeriesList(bucket, {
              tb,
              stage_key: stage,
              _chartLabel: tbDisplay(tb),
            });
          })
          .filter(Boolean)
          .sort((a, b) => b.total_leads - a.total_leads)
          .slice(0, limit);

        if (summarySeries.length) {
          charts.push({
            title: `Свод: все ТБ${selectedGroupsHint(filters)} | ${stage}`,
            seriesList: summarySeries,
            tier: "summary",
            layout: "stacked",
          });
        }

        tbs.slice(0, limit).forEach((tb) => {
          const bucket = stageData.filter((s) => String(s.tb) === tb);
          const rowMap = new Map();
          bucket.forEach((s) => {
            const rk = rowLabel(s);
            if (!rowMap.has(rk)) rowMap.set(rk, []);
            rowMap.get(rk).push(s);
          });

          const seriesList = [...rowMap.entries()]
            .map(([rk, list]) =>
              mergeSeriesList(list, { tb, stage_key: stage, row_key: rk, _chartLabel: rk })
            )
            .sort((a, b) => b.total_leads - a.total_leads)
            .slice(0, limit);

          if (seriesList.length) {
            const rowDim = isGroupOnly() ? "группы" : rowDimensionLabel().toLowerCase();
            charts.push({
              title: `${tbDisplay(tb)} · ${rowDim}${selectedGroupsHint(filters)} | ${stage}`,
              seriesList,
              tier: "detail",
              layout: "stacked",
            });
          }
        });
      });
    } else {
      stages.forEach((stage) => {
        const stageData = data.filter((s) => String(s.stage_key) === stage);
        const rowMap = new Map();
        stageData.forEach((s) => {
          const rk = rowLabel(s);
          if (!rowMap.has(rk)) rowMap.set(rk, []);
          rowMap.get(rk).push(s);
        });

        const summarySeries = [...rowMap.entries()]
          .map(([rk, list]) =>
            mergeSeriesList(list, { stage_key: stage, row_key: rk, _chartLabel: rk })
          )
          .sort((a, b) => b.total_leads - a.total_leads)
          .slice(0, limit);

        if (summarySeries.length) {
          charts.push({
            title: `Свод: все ${rowDim}${selectedGroupsHint(filters)} | ${stage}`,
            seriesList: summarySeries,
            tier: "summary",
          });
        }

        [...rowMap.entries()]
          .sort(
            (a, b) =>
              b[1].reduce((sum, s) => sum + s.total_leads, 0) -
              a[1].reduce((sum, s) => sum + s.total_leads, 0)
          )
          .slice(0, limit)
          .forEach(([rk, list]) => {
            charts.push({
              title: `${rk}${selectedGroupsHint(filters)} | ${stage}`,
              seriesList: [
                mergeSeriesList(list, { stage_key: stage, row_key: rk, _chartLabel: rk }),
              ],
              tier: "detail",
            });
          });
      });
    }

    return charts;
  }

  function buildPivotMatrix(filters) {
    const tbs = resolveTbSet(filters);
    const metric = filters.metric || "days_on_stage";
    const indicator = filters.indicator || "p80";
    const allLabel = allTbLabel();

    const rows = pivotFlat().filter(
      (row) =>
        tbs.includes(String(row.tb)) &&
        row.metric === metric &&
        row.indicator === indicator &&
        matchesMulti(row.product_group, filters.productGroups) &&
        (isGroupOnly() || matchesMulti(row.product, filters.products)) &&
        (!filters.stage || String(row.stage_key) === filters.stage)
    );

    const stages = pivotStageColumns(rows);
    const rowKey = (r) => String(r.row_key || (isGroupOnly() ? r.product_group : r.product));
    const rowLabels = Array.from(new Set(rows.map(rowKey))).sort((a, b) => a.localeCompare(b, "ru"));

    const values = {};
    rowLabels.forEach((label) => {
      values[label] = {};
      stages.forEach((stage) => {
        values[label][stage] = null;
      });
    });

    rows.forEach((row) => {
      const label = rowKey(row);
      const stage = String(row.stage_key);
      if (!values[label] || !(stage in values[label])) return;
      const val = row.value;
      if (val == null) return;
      const cell = {
        value: Number(val),
        leads_le: row.leads_le != null ? Number(row.leads_le) : null,
        leads_gt: row.leads_gt != null ? Number(row.leads_gt) : null,
      };
      const prev = values[label][stage];
      // Несколько ТБ: берём ячейку с большим сроком (как раньше max по дням)
      if (prev == null || cell.value > prev.value) {
        values[label][stage] = cell;
      }
    });

    return {
      tb: tbs.length === 1 ? tbs[0] : allLabel,
      tbs,
      metric,
      indicator,
      stages,
      rows: rowLabels,
      products: rowLabels,
      values,
      row_dimension: rowDimension(),
    };
  }

  function stageAnalysisMode() {
    return payload?.meta?.stage_analysis_mode || "status";
  }

  function lockedAnalysisLevel() {
    if (payload?.meta?.analysis_level) return String(payload.meta.analysis_level);
    const mode = stageAnalysisMode();
    if (mode === "status") return "status";
    if (mode === "substages") return "substage";
    return null;
  }

  function isAnalysisLevelLocked() {
    if (typeof payload?.meta?.analysis_level_locked === "boolean") {
      return payload.meta.analysis_level_locked;
    }
    return stageAnalysisMode() !== "both";
  }

  function metaLine() {
    if (!payload?.meta) return "JSON не загружен";
    const m = payload.meta;
    const excelMode = m.excel_product_analysis_mode || m.product_analysis_mode || "group_product";
    const viewLabel = aggregationLabel(aggregationMode);
    const sliceKey = resolveFilterSliceKey();
    const filterNote = filtersActive() ? " | Excel-фильтры config: да" : "";
    const levelNote = isAnalysisLevelLocked()
      ? ` | уровень: ${lockedAnalysisLevel() || stageAnalysisMode()}`
      : "";
    return (
      `Сгенерировано: ${m.generated_at || "—"} | режим: ${m.mode || "—"} | ` +
      `Excel: ${aggregationLabel(excelMode)} | HTML: ${viewLabel} | срез: ${sliceKey}${filterNote}${levelNote} | ` +
      `перцентили: ${(m.percentiles || []).join(", ")}`
    );
  }

  return {
    loadJson,
    clearPayload,
    isSplitBundle,
    getSlicesBase,
    ensureSlice,
    prepareActiveSlice,
    getPayload,
    setAggregationMode,
    getAggregationMode,
    setActivePipelineFilters,
    getActivePipelineFilters,
    defaultActivePipelineFilters,
    filterCatalog,
    filterSliceKey,
    resolveFilterSliceKey,
    filterSliceData,
    availableAggregationModes,
    aggregationLabel,
    stageAnalysisMode,
    lockedAnalysisLevel,
    isAnalysisLevelLocked,
    METRIC_LABELS,
    INDICATOR_LABELS,
    allTbLabel,
    allTbDisplay,
    tbDisplay,
    stageOrder,
    metrics,
    indicators,
    distributionSeries,
    seriesPoints,
    seriesPointCount,
    pivotFlat,
    tbOptions,
    realTbValues,
    isTbSelectionAll,
    resolveTbSet,
    productOptionsForGroups,
    matchesMulti,
    uniqueValues,
    filterSeries,
    groupSeriesForCharts,
    buildPivotMatrix,
    isGroupOnly,
    rowDimension,
    rowDimensionLabel,
    rowLabel,
    filtersApplied,
    configLockedFilters,
    filtersActive,
    filtersSummaryLine,
    metaLine,
  };
})();
