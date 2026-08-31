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

  function filterSeries(filters) {
    return distributionSeries().filter((series) => {
      if (filters.tb && String(series.tb) !== filters.tb) return false;
      if (filters.metric && series.metric !== filters.metric) return false;
      if (filters.productGroup && String(series.product_group) !== filters.productGroup) return false;
      if (filters.product && String(series.product) !== filters.product) return false;
      if (filters.stage && String(series.stage_key) !== filters.stage) return false;
      if (filters.level && String(series.analysis_level) !== filters.level) return false;
      return true;
    });
  }

  function groupSeriesForCharts(filtered, chartMode, maxSeries) {
    const charts = [];

    if (chartMode === "by_tb") {
      const byProductStage = new Map();
      filtered.forEach((series) => {
        const key = `${rowLabel(series)} | ${series.stage_key}`;
        if (!byProductStage.has(key)) byProductStage.set(key, []);
        byProductStage.get(key).push(series);
      });
      for (const [title, list] of byProductStage.entries()) {
        const sorted = [...list].sort((a, b) => b.total_leads - a.total_leads).slice(0, maxSeries);
        charts.push({ title: `ТБ → ${title}`, seriesList: sorted });
      }
    } else {
      const byStage = new Map();
      filtered.forEach((series) => {
        const key = String(series.stage_key);
        if (!byStage.has(key)) byStage.set(key, []);
        byStage.get(key).push(series);
      });
      for (const [stage, list] of byStage.entries()) {
        const sorted = [...list].sort((a, b) => b.total_leads - a.total_leads).slice(0, maxSeries);
        const prefix = isGroupOnly() ? "Группы" : "Продукты";
        charts.push({ title: `${prefix} | ${stage}`, seriesList: sorted });
      }
    }

    return charts.slice(0, maxSeries);
  }

  function buildPivotMatrix(filters) {
    const tb = filters.tb || allTbLabel();
    const metric = filters.metric || "days_on_stage";
    const indicator = filters.indicator || "p80";
    const stages = stageOrder();

    const rows = pivotFlat().filter(
      (row) =>
        String(row.tb) === tb &&
        row.metric === metric &&
        row.indicator === indicator &&
        (!filters.productGroup || String(row.product_group) === filters.productGroup) &&
        (!filters.product || isGroupOnly() || String(row.product) === filters.product) &&
        (!filters.stage || String(row.stage_key) === filters.stage)
    );

    const rowLabels = Array.from(
      new Set(rows.map((r) => String(r.row_key || (isGroupOnly() ? r.product_group : r.product))))
    ).sort((a, b) => a.localeCompare(b, "ru"));

    const values = {};
    rowLabels.forEach((rowLabel) => {
      values[rowLabel] = {};
      stages.forEach((stage) => {
        const match = rows.find(
          (r) =>
            String(r.row_key || (isGroupOnly() ? r.product_group : r.product)) === rowLabel &&
            String(r.stage_key) === stage
        );
        values[rowLabel][stage] = match ? match.value : null;
      });
    });

    return { tb, metric, indicator, stages, rows: rowLabels, products: rowLabels, values, row_dimension: rowDimension() };
  }

  function metaLine() {
    if (!payload?.meta) return "JSON не загружен";
    const m = payload.meta;
    return `Сгенерировано: ${m.generated_at || "—"} | режим: ${m.mode || "—"} | продукты: ${m.product_analysis_mode || "group_product"} | перцентили: ${(m.percentiles || []).join(", ")}`;
  }

  return {
    loadJson,
    getPayload,
    METRIC_LABELS,
    INDICATOR_LABELS,
    allTbLabel,
    allTbDisplay,
    stageOrder,
    metrics,
    indicators,
    distributionSeries,
    seriesPoints,
    seriesPointCount,
    pivotFlat,
    tbOptions,
    uniqueValues,
    filterSeries,
    groupSeriesForCharts,
    buildPivotMatrix,
    isGroupOnly,
    rowDimension,
    rowLabel,
    metaLine,
  };
})();
