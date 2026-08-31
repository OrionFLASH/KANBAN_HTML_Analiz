/** Загрузка и фильтрация данных JSON. */

const KanbanData = (() => {
  let payload = null;

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

  function loadJson(text) {
    payload = JSON.parse(text);
    return payload;
  }

  function getPayload() {
    return payload;
  }

  function isGroupOnly() {
    const mode = payload?.meta?.product_analysis_mode || payload?.visualizations?.product_analysis_mode;
    return mode === "group_only";
  }

  function rowDimension() {
    return viz().row_dimension || (isGroupOnly() ? "product_group" : "product");
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

  function stageOrder() {
    return viz().stage_order || [];
  }

  function metrics() {
    return viz().metrics || ["days_on_stage", "days_since_deal"];
  }

  function indicators() {
    return viz().indicators || ["min", "max", "p20", "p50", "p80"];
  }

  function distributionSeries() {
    return viz().distribution_series || [];
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
    return viz().pivot_flat || [];
  }

  function tbOptions() {
    const set = new Set();
    distributionSeries().forEach((s) => set.add(String(s.tb)));
    pivotFlat().forEach((row) => set.add(String(row.tb)));
    const label = allTbLabel();
    const items = Array.from(set).sort((a, b) => {
      if (a === label) return -1;
      if (b === label) return 1;
      return a.localeCompare(b, "ru");
    });
    return items.map((value) => ({
      value,
      label: value === label ? allTbDisplay() : value,
    }));
  }

  function uniqueValues(field) {
    const set = new Set();
    distributionSeries().forEach((row) => {
      if (row[field] != null && row[field] !== "") set.add(String(row[field]));
    });
    return Array.from(set).sort((a, b) => a.localeCompare(b, "ru"));
  }

  function productGroupMap() {
    /** Группа → множество продуктов (из серий распределения). */
    const map = new Map();
    distributionSeries().forEach((row) => {
      const group = String(row.product_group || "");
      const product = String(row.product || "");
      if (!group || !product) return;
      if (!map.has(group)) map.set(group, new Set());
      map.get(group).add(product);
    });
    return map;
  }

  function productOptionsForGroups(selectedGroups) {
    if (!selectedGroups || !selectedGroups.length) {
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
    /** Нормализует список выбранных ТБ для фильтрации. */
    const allLabel = allTbLabel();
    let tbs = filters.tbs;
    if (!tbs || !tbs.length) {
      if (filters.tb) tbs = [String(filters.tb)];
      else tbs = [allLabel];
    }
    tbs = tbs.map(String);
    const specific = tbs.filter((tb) => tb !== allLabel);
    if (specific.length === 0) return [allLabel];
    return specific;
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
    /** Объединяет кривые лидов в одну отсортированную шкалу дней."""
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
    const present = new Set(seriesList.map((s) => String(s.stage_key)));
    const ordered = order.filter((s) => present.has(s));
    present.forEach((s) => {
      if (!ordered.includes(s)) ordered.push(s);
    });
    return ordered;
  }

  function resolveChartTbs(seriesList, filters) {
    /** ТБ для детальных графиков (без псевдо __ALL__)."""
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
    /** Исключает свод __ALL__, если есть конкретные ТБ."""
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

  function filtersActive() {
    return Boolean(payload?.meta?.filters_active) || filtersApplied().length > 0;
  }

  function filtersSummaryLine() {
    const applied = filtersApplied();
    if (!applied.length) return "";
    const parts = applied.map((f) => {
      if (f.contains) return `${f.name}: «${f.contains}»`;
      return `${f.name}=${f.value}`;
    });
    return `Pipeline-фильтры (данные уже срезаны): ${parts.join("; ")}`;
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
            title: `Свод: все ТБ | ${stage}`,
            seriesList: summarySeries,
            tier: "summary",
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
            charts.push({
              title: `${tbDisplay(tb)} | ${stage}`,
              seriesList,
              tier: "detail",
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
            title: `Свод: все ${rowDim} | ${stage}`,
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
              title: `${rk} | ${stage}`,
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
    const stages = stageOrder();
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
      const prev = values[label][stage];
      if (prev == null || val > prev) {
        values[label][stage] = val;
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

  function metaLine() {
    if (!payload?.meta) return "JSON не загружен";
    const m = payload.meta;
    const modeLabel = isGroupOnly() ? "только группы" : "группа+продукт";
    const filterNote = filtersActive() ? " | фильтры pipeline: да" : "";
    return (
      `Сгенерировано: ${m.generated_at || "—"} | режим: ${m.mode || "—"} | ` +
      `анализ: ${modeLabel}${filterNote} | перцентили: ${(m.percentiles || []).join(", ")}`
    );
  }

  return {
    loadJson,
    getPayload,
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
    filtersActive,
    filtersSummaryLine,
    metaLine,
  };
})();
