/** Главный контроллер дашборда (glass UI). */

(() => {
  const app = document.getElementById("app");
  const metaInfo = document.getElementById("metaInfo");
  const chartsGrid = document.getElementById("chartsGrid");
  const pivotTable = document.getElementById("pivotTable");
  const pivotCaption = document.getElementById("pivotCaption");
  const filterStats = document.getElementById("filterStats");
  const filterScopeBanner = document.getElementById("filterScopeBanner");
  const productFilterBlock = document.getElementById("productFilterBlock");

  const controls = {
    jsonFile: document.getElementById("jsonFile"),
    chartMode: document.getElementById("chartMode"),
    metricSelect: document.getElementById("metricSelect"),
    indicatorSelect: document.getElementById("indicatorSelect"),
    maxSeries: document.getElementById("maxSeries"),
    showLegend: document.getElementById("showLegend"),
    smoothLines: document.getElementById("smoothLines"),
    stageFilter: document.getElementById("stageFilter"),
    levelFilter: document.getElementById("levelFilter"),
    resetFilters: document.getElementById("resetFilters"),
  };

  let tbWidget;
  let groupWidget;
  let productWidget;

  function onTbItemChange(event, widget) {
    const allLabel = KanbanData.allTbLabel();
    const target = event.target;
    const allCb = widget.listEl.querySelector(`input[value="${CSS.escape(allLabel)}"]`);

    if (target instanceof HTMLInputElement && target.type === "checkbox") {
      if (target.value === allLabel && target.checked) {
        widget.listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
          if (cb !== target) cb.checked = false;
        });
      } else if (target.value !== allLabel && target.checked && allCb) {
        allCb.checked = false;
      }
    }

    if (!widget.getSelected().length && allCb) {
      allCb.checked = true;
    }
  }

  function initFilterWidgets() {
    tbWidget = new KanbanMultiFilter.Widget({
      listEl: document.getElementById("tbFilterList"),
      badgeEl: document.getElementById("tbFilterBadge"),
      panelEl: document.getElementById("tbFilterPanel"),
      toggleEl: document.getElementById("tbFilterToggle"),
      allBtn: document.getElementById("tbSelectAll"),
      noneBtn: null,
      onChange: () => refreshKeepPivotSort(),
      onItemChange: onTbItemChange,
      startCollapsed: false,
    });

    document.getElementById("tbSelectNone").addEventListener("click", () => {
      const allLabel = KanbanData.allTbLabel();
      tbWidget.selectNone();
      const allCb = tbWidget.listEl.querySelector(`input[value="${CSS.escape(allLabel)}"]`);
      if (allCb) allCb.checked = true;
      tbWidget.updateBadge();
      refreshKeepPivotSort();
    });

    groupWidget = new KanbanMultiFilter.Widget({
      listEl: document.getElementById("groupFilterList"),
      badgeEl: document.getElementById("groupFilterBadge"),
      searchEl: document.getElementById("groupFilterSearch"),
      panelEl: document.getElementById("groupFilterPanel"),
      toggleEl: document.getElementById("groupFilterToggle"),
      allBtn: document.getElementById("groupSelectAll"),
      noneBtn: document.getElementById("groupSelectNone"),
      onChange: () => {
        syncProductListFromGroups();
        refreshKeepPivotSort();
      },
      startCollapsed: false,
    });

    productWidget = new KanbanMultiFilter.Widget({
      listEl: document.getElementById("productFilterList"),
      badgeEl: document.getElementById("productFilterBadge"),
      searchEl: document.getElementById("productFilterSearch"),
      panelEl: document.getElementById("productFilterPanel"),
      toggleEl: document.getElementById("productFilterToggle"),
      allBtn: document.getElementById("productSelectAll"),
      noneBtn: document.getElementById("productSelectNone"),
      onChange: () => refreshKeepPivotSort(),
      startCollapsed: true,
    });
  }

  initFilterWidgets();

  function getFilters() {
    const productGroups = groupWidget.getSelected();
    const products = productWidget.getSelected();
    return {
      tbs: tbWidget.getSelected(),
      productGroups: productGroups.length ? productGroups : undefined,
      products: products.length ? products : undefined,
      metric: controls.metricSelect.value,
      indicator: controls.indicatorSelect.value,
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

  function populateTbFilter(preferredTbs) {
    const options = KanbanData.tbOptions();
    const preferred = new Set(
      (preferredTbs && preferredTbs.length ? preferredTbs : [KanbanData.allTbLabel()]).map(String)
    );
    tbWidget.setItems(options, Array.from(preferred));

    if (!tbWidget.getSelected().length) {
      const fallback = options.find((o) => o.value === KanbanData.allTbLabel()) || options[0];
      if (fallback) tbWidget.setItems(options, [fallback.value]);
    }
  }

  function populateGroupFilter() {
    const groups = KanbanData.uniqueValues("product_group").map((value) => ({ value, label: value }));
    groupWidget.setItems(groups, []);
  }

  function syncProductListFromGroups() {
    if (KanbanData.isGroupOnly()) return;
    const selectedGroups = groupWidget.getSelected();
    const prevSelected = new Set(productWidget.getSelected());
    const products = KanbanData.productOptionsForGroups(selectedGroups).map((value) => ({
      value,
      label: value,
    }));
    const stillValid = products.filter((p) => prevSelected.has(p.value)).map((p) => p.value);
    productWidget.setItems(products, stillValid);

    const toggle = document.getElementById("productFilterToggle");
    if (products.length > 14 && toggle?.getAttribute("aria-expanded") !== "true") {
      productWidget.collapsed = true;
      productWidget.applyCollapseState();
    }
  }

  function populateProductFilter() {
    syncProductListFromGroups();
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

    populateTbFilter([defaultView.tb || KanbanData.allTbLabel()]);
    populateGroupFilter();
    populateProductFilter();

    controls.metricSelect.value = defaultView.metric || "days_on_stage";
    controls.indicatorSelect.value = defaultView.indicator || "p80";

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
    const optProduct = controls.chartMode.querySelector('option[value="by_product"]');
    const optTb = controls.chartMode.querySelector('option[value="by_tb"]');
    if (groupOnly) {
      productWidget.selectNone();
      if (optProduct) optProduct.textContent = "По группам: свод + каждая";
      if (optTb) optTb.textContent = "По ТБ: свод + каждый ТБ";
    } else {
      if (optProduct) optProduct.textContent = "По продуктам: свод + каждый";
      if (optTb) optTb.textContent = "По ТБ: свод + каждый ТБ";
    }

    updateFilterScopeBanner();
  }

  function updateFilterScopeBanner() {
    if (!filterScopeBanner) return;
    const line = KanbanData.filtersSummaryLine();
    if (line) {
      filterScopeBanner.hidden = false;
      filterScopeBanner.textContent = line;
    } else {
      filterScopeBanner.hidden = true;
      filterScopeBanner.textContent = "";
    }
  }

  function renderCharts(filters, maxSeries, chartMode) {
    const filtered = KanbanData.filterSeries(filters);
    const chartGroups = KanbanData.groupSeriesForCharts(filtered, chartMode, maxSeries, filters);
    chartsGrid.classList.toggle("charts-grid--by-tb", chartMode === "by_tb");
    KanbanCharts.render(chartsGrid, chartGroups, {
      chartMode,
      showLegend: controls.showLegend.checked,
      smooth: controls.smoothLines.checked,
    });
  }

  function updateStats(filteredCount) {
    const total = KanbanData.distributionSeries().length;
    const groupCount = groupWidget.getSelected().length;
    const productCount = productWidget.getSelected().length;
    const groupOnly = KanbanData.isGroupOnly();
    const productLine = groupOnly
      ? ""
      : ` · Продукты: <b>${productCount || "все"}</b>`;
    filterStats.innerHTML =
      `Серий в JSON: <b>${total}</b><br>` +
      `После фильтров: <b>${filteredCount}</b><br>` +
      `ТБ: <b>${tbWidget.getSelected().length || "все"}</b> · ` +
      `${groupOnly ? "Группы (выбранные)" : "Группы"}: <b>${groupCount || "все"}</b>${productLine}<br>` +
      `Точек: <b>${KanbanData.distributionSeries().reduce((s, x) => s + KanbanData.seriesPointCount(x), 0)}</b>`;
  }

  function refresh() {
    if (!KanbanData.getPayload()) return;

    const filters = getFilters();
    const maxSeries = Math.max(1, Number(controls.maxSeries.value) || 8);
    const chartMode = controls.chartMode.value;

    const filtered = KanbanData.filterSeries(filters);
    updateStats(filtered.length);

    renderCharts(filters, maxSeries, chartMode);

    KanbanPivot.resetSort();

    const matrix = KanbanData.buildPivotMatrix(filters);
    KanbanPivot.render(pivotTable, matrix, pivotCaption);
  }

  function refreshKeepPivotSort() {
    if (!KanbanData.getPayload()) return;

    const filters = getFilters();
    const maxSeries = Math.max(1, Number(controls.maxSeries.value) || 8);
    const chartMode = controls.chartMode.value;

    const filtered = KanbanData.filterSeries(filters);
    updateStats(filtered.length);

    renderCharts(filters, maxSeries, chartMode);

    const matrix = KanbanData.buildPivotMatrix(filters);
    KanbanPivot.render(pivotTable, matrix, pivotCaption);
  }

  function onJsonLoaded(text) {
    try {
      KanbanData.loadJson(text);
      metaInfo.textContent = KanbanData.metaLine();
      KanbanPivot.resetSort();
      populateControlsFromPayload();
      refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      metaInfo.textContent = `Ошибка загрузки JSON: ${message}`;
      console.error("[KANBAN] loadJson failed:", err);
      chartsGrid.innerHTML =
        `<div class="empty-state panel"><p class="empty-state__title">Не удалось разобрать JSON</p>` +
        `<p>${message}</p></div>`;
    }
  }

  controls.jsonFile.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onJsonLoaded(String(reader.result));
    reader.onerror = () => {
      metaInfo.textContent = "Не удалось прочитать выбранный файл.";
    };
    reader.readAsText(file, "UTF-8");
  });

  [
    controls.chartMode,
    controls.metricSelect,
    controls.indicatorSelect,
    controls.maxSeries,
    controls.showLegend,
    controls.smoothLines,
    controls.stageFilter,
    controls.levelFilter,
  ].forEach((el) => el.addEventListener("change", refresh));

  controls.maxSeries.addEventListener("input", refresh);

  controls.resetFilters.addEventListener("click", () => {
    controls.stageFilter.value = "";
    controls.levelFilter.value = "";
    const defaultView = KanbanData.getPayload()?.visualizations?.default_view || {};
    populateTbFilter([defaultView.tb || KanbanData.allTbLabel()]);
    populateGroupFilter();
    populateProductFilter();
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
      if (tab.dataset.tab === "pivot") {
        refreshKeepPivotSort();
      }
    });
  });

  /** Кандидаты автозагрузки: data/ — при сервере из HTML/; ../OUT и /OUT — из корня проекта. */
  const JSON_AUTOLOAD_URLS = [
    "data/kanban_report_latest.json",
    "../OUT/kanban_report_latest.json",
    "/OUT/kanban_report_latest.json",
  ];

  async function autoloadJson() {
    if (window.location.protocol === "file:") {
      metaInfo.textContent =
        "Автозагрузка недоступна (file://). Запустите HTTP-сервер или выберите JSON вручную.";
      return;
    }

    for (const url of JSON_AUTOLOAD_URLS) {
      try {
        const response = await fetch(url);
        if (!response.ok) continue;
        onJsonLoaded(await response.text());
        if (KanbanData.getPayload()) return;
      } catch (err) {
        console.warn("[KANBAN] autoload failed for", url, err);
      }
    }

    metaInfo.textContent =
      "JSON не найден. Выполните run.py или выберите kanban_report_*.json вручную.";
  }

  autoloadJson();
})();
