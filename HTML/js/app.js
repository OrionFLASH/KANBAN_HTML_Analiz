/** Главный контроллер дашборда (glass UI). */

(() => {
  const app = document.getElementById("app");
  const metaInfo = document.getElementById("metaInfo");
  const chartsGrid = document.getElementById("chartsGrid");
  const pivotTable = document.getElementById("pivotTable");
  const pivotCaption = document.getElementById("pivotCaption");
  const filterStats = document.getElementById("filterStats");
  const productFilterBlock = document.getElementById("productFilterBlock");

  const controls = {
    jsonFile: document.getElementById("jsonFile"),
    chartMode: document.getElementById("chartMode"),
    metricSelect: document.getElementById("metricSelect"),
    indicatorSelect: document.getElementById("indicatorSelect"),
    maxSeries: document.getElementById("maxSeries"),
    showLegend: document.getElementById("showLegend"),
    smoothLines: document.getElementById("smoothLines"),
    tbFilter: document.getElementById("tbFilter"),
    groupFilter: document.getElementById("groupFilter"),
    productFilter: document.getElementById("productFilter"),
    stageFilter: document.getElementById("stageFilter"),
    levelFilter: document.getElementById("levelFilter"),
    resetFilters: document.getElementById("resetFilters"),
  };

  function getFilters() {
    return {
      tb: controls.tbFilter.value,
      metric: controls.metricSelect.value,
      indicator: controls.indicatorSelect.value,
      productGroup: controls.groupFilter.value,
      product: controls.productFilter.value,
      stage: controls.stageFilter.value,
      level: controls.levelFilter.value,
    };
  }

  function fillSelect(select, items, keepFirst = false) {
    const first = keepFirst ? select.options[0]?.outerHTML : null;
    select.innerHTML = first || "";
    items.forEach(({ value, label }) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    });
  }

  function populateControlsFromPayload() {
    const defaultView = KanbanData.getPayload()?.visualizations?.default_view || {};

    fillSelect(
      controls.metricSelect,
      KanbanData.metrics().map((m) => ({ value: m, label: KanbanData.METRIC_LABELS[m] || m }))
    );
    fillSelect(
      controls.indicatorSelect,
      KanbanData.indicators().map((i) => ({ value: i, label: KanbanData.INDICATOR_LABELS[i] || i }))
    );
    fillSelect(controls.tbFilter, KanbanData.tbOptions());

    controls.metricSelect.value = defaultView.metric || "days_on_stage";
    controls.indicatorSelect.value = defaultView.indicator || "p80";
    controls.tbFilter.value = defaultView.tb || KanbanData.allTbLabel();

    fillSelect(
      controls.groupFilter,
      [{ value: "", label: "Все группы" }].concat(
        KanbanData.uniqueValues("product_group").map((v) => ({ value: v, label: v }))
      ),
      true
    );
    fillSelect(
      controls.productFilter,
      [{ value: "", label: "Все продукты" }].concat(
        KanbanData.uniqueValues("product").map((v) => ({ value: v, label: v }))
      ),
      true
    );
    fillSelect(
      controls.stageFilter,
      [{ value: "", label: "Все стадии" }].concat(
        KanbanData.stageOrder().map((v) => ({ value: v, label: v }))
      ),
      true
    );

    const groupOnly = KanbanData.isGroupOnly();
    if (productFilterBlock) {
      productFilterBlock.hidden = groupOnly;
    }
    if (groupOnly) {
      controls.productFilter.value = "";
      const opt = controls.chartMode.querySelector('option[value="by_product"]');
      if (opt) opt.textContent = "По группам (выбранное ТБ)";
    } else {
      const opt = controls.chartMode.querySelector('option[value="by_product"]');
      if (opt) opt.textContent = "По продуктам (выбранное ТБ)";
    }
  }

  function updateStats(filteredCount) {
    const total = KanbanData.distributionSeries().length;
    filterStats.innerHTML =
      `Серий в JSON: <b>${total}</b><br>` +
      `После фильтров: <b>${filteredCount}</b><br>` +
      `Точек: <b>${KanbanData.distributionSeries().reduce((s, x) => s + KanbanData.seriesPointCount(x), 0)}</b>`;
  }

  function refresh() {
    if (!KanbanData.getPayload()) return;

    const filters = getFilters();
    const maxSeries = Math.max(1, Number(controls.maxSeries.value) || 8);
    const chartMode = controls.chartMode.value;

    let filtered = KanbanData.filterSeries(filters);

    if (chartMode === "by_tb" && filters.product) {
      filtered = filtered.filter((s) => String(s.product) === filters.product);
    }

    updateStats(filtered.length);

    const chartGroups = KanbanData.groupSeriesForCharts(filtered, chartMode, maxSeries);
    KanbanCharts.render(chartsGrid, chartGroups, {
      chartMode,
      showLegend: controls.showLegend.checked,
      smooth: controls.smoothLines.checked,
    });

    const matrix = KanbanData.buildPivotMatrix(filters);
    KanbanPivot.render(pivotTable, matrix, pivotCaption, filters);
  }

  function onJsonLoaded(text) {
    KanbanData.loadJson(text);
    metaInfo.textContent = KanbanData.metaLine();
    populateControlsFromPayload();
    refresh();
  }

  controls.jsonFile.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onJsonLoaded(String(reader.result));
    reader.readAsText(file, "UTF-8");
  });

  [
    controls.chartMode,
    controls.metricSelect,
    controls.indicatorSelect,
    controls.maxSeries,
    controls.showLegend,
    controls.smoothLines,
    controls.tbFilter,
    controls.groupFilter,
    controls.productFilter,
    controls.stageFilter,
    controls.levelFilter,
  ].forEach((el) => el.addEventListener("change", refresh));

  controls.maxSeries.addEventListener("input", refresh);

  controls.resetFilters.addEventListener("click", () => {
    controls.groupFilter.value = "";
    controls.productFilter.value = "";
    controls.stageFilter.value = "";
    controls.levelFilter.value = "";
    const defaultView = KanbanData.getPayload()?.visualizations?.default_view || {};
    controls.tbFilter.value = defaultView.tb || KanbanData.allTbLabel();
    controls.metricSelect.value = defaultView.metric || "days_on_stage";
    controls.indicatorSelect.value = defaultView.indicator || "p80";
    refresh();
  });

  function bindSidebarToggle(hideId, showId, collapsedClass) {
    const hideBtn = document.getElementById(hideId);
    const showBtn = document.getElementById(showId);
    hideBtn?.addEventListener("click", () => {
      app.classList.add(collapsedClass);
      hideBtn.setAttribute("aria-expanded", "false");
      showBtn?.setAttribute("aria-expanded", "true");
    });
    showBtn?.addEventListener("click", () => {
      app.classList.remove(collapsedClass);
      showBtn.setAttribute("aria-expanded", "false");
      hideBtn?.setAttribute("aria-expanded", "true");
    });
  }

  bindSidebarToggle("btn-settings-hide", "btn-settings-show", "is-sidebar-collapsed");
  bindSidebarToggle("btn-filters-hide", "btn-filters-show", "is-filters-collapsed");

  document.querySelectorAll(".mode-tabs .tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document.querySelectorAll(".mode-tabs .tab").forEach((t) => {
        t.classList.remove("active");
        t.setAttribute("aria-selected", "false");
      });
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      document.getElementById(`${tab.dataset.tab}Tab`).classList.add("active");
    });
  });

  fetch("../OUT/kanban_report_latest.json")
    .then((r) => (r.ok ? r.text() : null))
    .then((text) => {
      if (text) onJsonLoaded(text);
    })
    .catch(() => {});
})();
