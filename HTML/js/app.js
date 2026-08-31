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
  const pipelineFilterList = document.getElementById("pipelineFilterList");
  const pipelineFilterBlock = document.getElementById("pipelineFilterBlock");
  const managersPanel = document.getElementById("managersPanel");

  const controls = {
    jsonFile: document.getElementById("jsonFile"),
    managersJsonFile: document.getElementById("managersJsonFile"),
    aggregationMode: document.getElementById("aggregationMode"),
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

  function initFilterWidgets() {
    tbWidget = new KanbanMultiFilter.Widget({
      listEl: document.getElementById("tbFilterList"),
      badgeEl: document.getElementById("tbFilterBadge"),
      panelEl: document.getElementById("tbFilterPanel"),
      toggleEl: document.getElementById("tbFilterToggle"),
      allBtn: document.getElementById("tbSelectAll"),
      noneBtn: document.getElementById("tbSelectNone"),
      onChange: () => refreshKeepPivotSort(),
      defaultIcon: "tb",
      startCollapsed: false,
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
      defaultIcon: "group",
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
      defaultIcon: "product",
      startCollapsed: true,
    });
  }

  initFilterWidgets();

  KanbanIcons.setIcon(document.getElementById("tbToggleIcon"), "tb");
  KanbanIcons.setIcon(document.getElementById("groupToggleIcon"), "group");
  KanbanIcons.setIcon(document.getElementById("productToggleIcon"), "product");
  KanbanIcons.setIcon(document.getElementById("pipelineBlockIcon"), "pipeline");
  KanbanIcons.setIcon(document.getElementById("stageBlockIcon"), "stage");
  KanbanIcons.setIcon(document.getElementById("levelBlockIcon"), "level");
  KanbanIcons.setIcon(document.getElementById("resetFilters"), "reset");

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

  function selectionSummaryLabel(widget) {
    if (widget.isAllSelected()) return "все";
    const n = widget.getSelected().length;
    return String(n);
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
    const allLabel = KanbanData.allTbLabel();
    const real = options.map((o) => o.value);
    let selected = [];

    if (preferredTbs?.length) {
      const pref = preferredTbs.map(String).filter((tb) => tb !== allLabel);
      if (pref.length && pref.length < real.length) {
        selected = pref.filter((tb) => real.includes(tb));
      }
    }

    tbWidget.setItems(options, selected);
  }

  function populateGroupFilter() {
    const groups = KanbanData.uniqueValues("product_group").map((value) => ({
      value,
      label: value,
      icon: "group",
    }));
    groupWidget.setItems(groups, []);
  }

  function syncProductListFromGroups() {
    if (KanbanData.isGroupOnly()) return;
    const selectedGroups = groupWidget.getSelected();
    const prevSelected = new Set(productWidget.getSelected());
    const products = KanbanData.productOptionsForGroups(selectedGroups).map((value) => ({
      value,
      label: value,
      icon: "product",
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

  function createPipelineToggle(item, isActive) {
    const { name, toggle_label: toggleLabel, html_label: htmlLabel, exclusive_group: exclusiveGroup } = item;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "pipeline-toggle";
    btn.dataset.filter = name;
    if (exclusiveGroup) btn.dataset.exclusiveGroup = exclusiveGroup;
    btn.title = htmlLabel || toggleLabel;
    btn.setAttribute("aria-pressed", isActive ? "true" : "false");

    const iconEl = document.createElement("span");
    iconEl.className = "pipeline-toggle__icon";
    iconEl.appendChild(KanbanIcons.create(KanbanIcons.pipelineIcon(name), "icon icon--sm"));

    const text = document.createElement("span");
    text.className = "pipeline-toggle__label";
    text.textContent = toggleLabel || htmlLabel;

    const state = document.createElement("span");
    state.className = "pipeline-toggle__state";
    state.textContent = isActive ? "ВКЛ" : "ВЫКЛ";

    btn.appendChild(iconEl);
    btn.appendChild(text);
    btn.appendChild(state);
    return btn;
  }

  function syncPipelineToggleUi(activeNames) {
    if (!pipelineFilterList) return;
    const active = new Set(activeNames || []);
    pipelineFilterList.querySelectorAll(".pipeline-toggle").forEach((btn) => {
      const on = active.has(btn.dataset.filter);
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      const state = btn.querySelector(".pipeline-toggle__state");
      if (state) state.textContent = on ? "ВКЛ" : "ВЫКЛ";
    });
  }

  function populatePipelineFilters() {
    if (!pipelineFilterList) return;
    const catalog = KanbanData.filterCatalog();
    pipelineFilterList.innerHTML = "";
    if (!catalog.length) {
      if (pipelineFilterBlock) pipelineFilterBlock.hidden = true;
      return;
    }
    if (pipelineFilterBlock) pipelineFilterBlock.hidden = false;
    const active = new Set(KanbanData.getActivePipelineFilters());

    const inclusion = catalog.filter((item) => item.filter_mode !== "exclude" && !item.exclusive_group);
    const exclusion = catalog.filter((item) => item.filter_mode === "exclude");
    const labelVariants = catalog.filter((item) => item.exclusive_group === "strategy_label");

    inclusion.forEach((item) => {
      pipelineFilterList.appendChild(createPipelineToggle(item, active.has(item.name)));
    });

    if (exclusion.length) {
      const group = document.createElement("div");
      group.className = "pipeline-toggle-group";
      group.dataset.uiGroup = "terminal_deal_stages";

      const groupTitle = document.createElement("div");
      groupTitle.className = "pipeline-toggle-group__title";
      groupTitle.textContent = "Исключить терминальные стадии сделки";
      group.appendChild(groupTitle);

      exclusion.forEach((item) => {
        group.appendChild(createPipelineToggle(item, active.has(item.name)));
      });
      pipelineFilterList.appendChild(group);
    }

    if (labelVariants.length) {
      const group = document.createElement("div");
      group.className = "pipeline-toggle-group";
      group.dataset.exclusiveGroup = "strategy_label";

      const groupTitle = document.createElement("div");
      groupTitle.className = "pipeline-toggle-group__title";
      groupTitle.textContent = "Метка";
      group.appendChild(groupTitle);

      labelVariants.forEach((item) => {
        group.appendChild(createPipelineToggle(item, active.has(item.name)));
      });
      pipelineFilterList.appendChild(group);
    }
  }

  function readPipelineFiltersFromUi() {
    if (!pipelineFilterList) return [];
    return Array.from(pipelineFilterList.querySelectorAll('.pipeline-toggle[aria-pressed="true"]')).map(
      (btn) => btn.dataset.filter
    );
  }

  async function onPipelineToggleClick(event) {
    const btn = event.target.closest(".pipeline-toggle");
    if (!btn) return;

    const name = btn.dataset.filter;
    const catalog = KanbanData.filterCatalog();
    const item = catalog.find((c) => c.name === name);
    const active = new Set(KanbanData.getActivePipelineFilters());
    const turningOn = btn.getAttribute("aria-pressed") !== "true";

    if (turningOn) {
      if (item?.exclusive_group) {
        catalog
          .filter((c) => c.exclusive_group === item.exclusive_group && c.name !== name)
          .forEach((other) => active.delete(other.name));
      }
      active.add(name);
    } else {
      active.delete(name);
    }

    KanbanData.setActivePipelineFilters(Array.from(active));
    syncPipelineToggleUi(Array.from(active));

    if (KanbanData.isSplitBundle()) {
      metaInfo.textContent = "Загрузка среза pipeline…";
      try {
        await KanbanData.ensureSlice(KanbanData.resolveFilterSliceKey());
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        metaInfo.textContent = `Ошибка среза: ${message}`;
        return;
      }
    }

    metaInfo.textContent = KanbanData.metaLine();
    updateFilterScopeBanner();
    populateGroupFilter();
    populateProductFilter();
    KanbanPivot.resetSort();
    refresh();
  }

  function updateAggregationUi() {
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
  }

  function populateAggregationControl() {
    const modes = KanbanData.availableAggregationModes();
    const current = KanbanData.getAggregationMode();
    controls.aggregationMode.innerHTML = "";
    modes.forEach((mode) => {
      const opt = document.createElement("option");
      opt.value = mode;
      opt.textContent = KanbanData.aggregationLabel(mode);
      controls.aggregationMode.appendChild(opt);
    });
    controls.aggregationMode.value = modes.includes(current) ? current : modes[0];
    KanbanData.setAggregationMode(controls.aggregationMode.value);
    updateAggregationUi();
  }

  function populateControlsFromPayload() {
    const defaultView = KanbanData.getPayload()?.visualizations?.default_view || {};

    populateAggregationControl();
    populatePipelineFilters();

    fillSelect(
      controls.metricSelect,
      KanbanData.metrics().map((m) => ({ value: m, label: KanbanData.METRIC_LABELS[m] || m }))
    );
    fillSelect(
      controls.indicatorSelect,
      KanbanData.indicators().map((i) => ({ value: i, label: KanbanData.INDICATOR_LABELS[i] || i }))
    );

    populateTbFilter(defaultView.tb ? [defaultView.tb] : []);
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

    updateFilterScopeBanner();
  }

  function updateFilterScopeBanner() {
    if (!filterScopeBanner) return;
    const line = KanbanData.filtersSummaryLine();
    const missing =
      KanbanData.getActivePipelineFilters().length &&
      KanbanData.resolveFilterSliceKey() !== KanbanData.filterSliceKey(KanbanData.getActivePipelineFilters())
        ? " (срез не найден в JSON — выберите другую комбинацию)"
        : "";
    if (line || missing) {
      filterScopeBanner.hidden = false;
      filterScopeBanner.textContent = (line || "") + missing;
    } else {
      filterScopeBanner.hidden = true;
      filterScopeBanner.textContent = "";
    }
  }

  function isKmChartMode(chartMode) {
    return String(chartMode || "").startsWith("km_");
  }

  function updateChartModeUi(chartMode) {
    const kmMode = isKmChartMode(chartMode);
    controls.metricSelect.closest(".field")?.classList.toggle("field--hidden", kmMode);
    controls.indicatorSelect.closest(".field")?.classList.toggle("field--hidden", kmMode);
    controls.smoothLines.closest(".field--check")?.classList.toggle("field--hidden", kmMode);
  }

  function renderCharts(filters, maxSeries, chartMode) {
    updateChartModeUi(chartMode);
    chartsGrid.classList.toggle("charts-grid--by-tb", chartMode === "by_tb");
    chartsGrid.classList.toggle("charts-grid--km", isKmChartMode(chartMode));

    if (isKmChartMode(chartMode)) {
      if (!KanbanManagers.hasChartData()) {
        KanbanCharts.destroyAll();
        chartsGrid.innerHTML =
          `<div class="empty-state panel">` +
          `<p class="empty-state__title">Нет данных по КМ</p>` +
          `<p>Загрузите <code>kanban_report_managers_*.json</code> — в нём блок <code>charts</code> для bar-графиков.</p>` +
          `</div>`;
        return;
      }
      const chartGroups = KanbanManagers.buildChartGroups(filters, chartMode, maxSeries);
      KanbanCharts.renderBars(chartsGrid, chartGroups, {
        showLegend: controls.showLegend.checked,
      });
      return;
    }

    const filtered = KanbanData.filterSeries(filters);
    const chartGroups = KanbanData.groupSeriesForCharts(filtered, chartMode, maxSeries, filters);
    KanbanCharts.render(chartsGrid, chartGroups, {
      chartMode,
      showLegend: controls.showLegend.checked,
      smooth: controls.smoothLines.checked,
    });
  }

  function updateStats(filteredCount) {
    const total = KanbanData.distributionSeries().length;
    const groupOnly = KanbanData.isGroupOnly();
    const productLine = groupOnly ? "" : ` · Продукты: <b>${selectionSummaryLabel(productWidget)}</b>`;
    const slice = KanbanData.filterSliceData();
    const pipelineLine = KanbanData.getActivePipelineFilters().length
      ? KanbanData.getActivePipelineFilters().join(" + ")
      : "нет";
    filterStats.innerHTML =
      `Срез JSON: <b>${KanbanData.resolveFilterSliceKey()}</b> (${slice.record_count ?? "—"} записей)<br>` +
      `Pipeline: <b>${pipelineLine}</b><br>` +
      `Серий в срезе: <b>${total}</b><br>` +
      `После UI-фильтров: <b>${filteredCount}</b><br>` +
      `ТБ: <b>${selectionSummaryLabel(tbWidget)}</b> · ` +
      `${groupOnly ? "Группы (выбранные)" : "Группы"}: <b>${selectionSummaryLabel(groupWidget)}</b>${productLine}<br>` +
      `Точек: <b>${KanbanData.distributionSeries().reduce((s, x) => s + KanbanData.seriesPointCount(x), 0)}</b>`;
  }

  function renderManagers(filters) {
    if (managersPanel) {
      KanbanManagers.render(managersPanel, filters);
    }
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
    renderManagers(filters);
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
    renderManagers(filters);
  }

  async function onJsonLoaded(text) {
    try {
      KanbanData.loadJson(text);
      if (KanbanData.isSplitBundle()) {
        metaInfo.textContent = "Загрузка среза данных…";
        await KanbanData.prepareActiveSlice();
      }
      metaInfo.textContent = KanbanData.metaLine();
      KanbanPivot.resetSort();
    populateControlsFromPayload();
    updateChartModeUi(controls.chartMode.value);
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

  controls.managersJsonFile?.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        KanbanManagers.loadJson(String(reader.result));
        refreshKeepPivotSort();
      } catch (err) {
        console.error("[KANBAN] managers JSON failed:", err);
      }
    };
    reader.readAsText(file, "UTF-8");
  });

  pipelineFilterList?.addEventListener("click", onPipelineToggleClick);

  controls.aggregationMode.addEventListener("change", () => {
    KanbanData.setAggregationMode(controls.aggregationMode.value);
    updateAggregationUi();
    populateGroupFilter();
    populateProductFilter();
    KanbanPivot.resetSort();
    refresh();
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
    KanbanData.setActivePipelineFilters(KanbanData.defaultActivePipelineFilters());
    populatePipelineFilters();
    populateTbFilter([]);
    populateGroupFilter();
    populateProductFilter();
    const defaultView = KanbanData.getPayload()?.visualizations?.default_view || {};
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

  initFiltersPanelResize();

  function initFiltersPanelResize() {
    const handle = document.getElementById("filtersResizeHandle");
    if (!handle || !app) return;

    const STORAGE_KEY = "kanban_filters_panel_width";
    const MIN = 280;
    const MAX = 560;
    const STEP = 12;

    function readCssFiltersWidth() {
      const raw = getComputedStyle(app).getPropertyValue("--filters-w").trim();
      const n = parseInt(raw, 10);
      return Number.isFinite(n) ? n : 360;
    }

    function clampWidth(px) {
      return Math.min(MAX, Math.max(MIN, Math.round(px)));
    }

    function applyWidth(px, persist) {
      const w = clampWidth(px);
      app.style.setProperty("--filters-w", `${w}px`);
      handle.setAttribute("aria-valuenow", String(w));
      if (persist) {
        try {
          localStorage.setItem(STORAGE_KEY, String(w));
        } catch (_) {
          /* localStorage недоступен */
        }
      }
      return w;
    }

    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) applyWidth(Number(saved), false);
      else applyWidth(readCssFiltersWidth(), false);
    } catch (_) {
      applyWidth(readCssFiltersWidth(), false);
    }

    let dragging = false;
    let startX = 0;
    let startW = 0;

    function onPointerMove(clientX) {
      const delta = startX - clientX;
      applyWidth(startW + delta, false);
    }

    function stopDrag() {
      if (!dragging) return;
      dragging = false;
      app.classList.remove("is-resizing-filters");
      applyWidth(readCssFiltersWidth(), true);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", stopDrag);
      window.removeEventListener("touchmove", onTouchMove);
      window.removeEventListener("touchend", stopDrag);
    }

    function onMouseMove(event) {
      if (!dragging) return;
      event.preventDefault();
      onPointerMove(event.clientX);
    }

    function onTouchMove(event) {
      if (!dragging || !event.touches.length) return;
      event.preventDefault();
      onPointerMove(event.touches[0].clientX);
    }

    function startDrag(clientX) {
      if (app.classList.contains("is-filters-collapsed")) return;
      dragging = true;
      startX = clientX;
      startW = readCssFiltersWidth();
      app.classList.add("is-resizing-filters");
      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", stopDrag);
      window.addEventListener("touchmove", onTouchMove, { passive: false });
      window.addEventListener("touchend", stopDrag);
    }

    handle.addEventListener("mousedown", (event) => {
      event.preventDefault();
      startDrag(event.clientX);
    });

    handle.addEventListener("touchstart", (event) => {
      if (!event.touches.length) return;
      startDrag(event.touches[0].clientX);
    }, { passive: true });

    handle.addEventListener("keydown", (event) => {
      if (app.classList.contains("is-filters-collapsed")) return;
      let next = readCssFiltersWidth();
      if (event.key === "ArrowLeft") next += STEP;
      else if (event.key === "ArrowRight") next -= STEP;
      else if (event.key === "Home") next = MAX;
      else if (event.key === "End") next = MIN;
      else return;
      event.preventDefault();
      applyWidth(next, true);
    });

    handle.addEventListener("dblclick", () => {
      applyWidth(360, true);
    });
  }

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

  metaInfo.textContent = "Выберите JSON отчёта (manifest или monolith) и при необходимости JSON менеджеров.";
})();
