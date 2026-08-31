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
  const configLockedFiltersBlock = document.getElementById("configLockedFiltersBlock");
  const configLockedFiltersList = document.getElementById("configLockedFiltersList");
  const managersPanel = document.getElementById("managersPanel");

  const controls = {
    jsonFile: document.getElementById("jsonFile"),
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
      level: KanbanData.isAnalysisLevelLocked() ? "" : controls.levelFilter?.value || "",
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
    // Сужаем продукты только при частичном выборе групп (не «все» и не «пусто = все»)
    const selectedGroups = groupWidget.getSelected();
    const totalGroups = groupWidget.allItems?.length || 0;
    const restrictGroups =
      selectedGroups.length > 0 && selectedGroups.length < totalGroups ? selectedGroups : null;

    const prevSelected = new Set(productWidget.getSelected());
    const products = KanbanData.productOptionsForGroups(restrictGroups).map((value) => ({
      value,
      label: value,
      icon: "product",
    }));

    // Сохраняем пересечение прежнего выбора; если раньше было «все» — отмечаем весь новый список
    const prevWasAll =
      !prevSelected.size || prevSelected.size >= (productWidget.allItems?.length || 0);
    const stillValid = products.filter((p) => prevSelected.has(p.value)).map((p) => p.value);
    const nextSelected = prevWasAll ? products.map((p) => p.value) : stillValid;
    productWidget.setItems(products, nextSelected);

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

  function lockedFilterUi(item) {
    const labels = {
      change_conditions: { title: "Изм. условий", hint: "Изменение условий сделки" },
      data_entry: { title: "Ввод данных", hint: "Флаг ввода данных" },
      efs_flag: { title: "ЕФС", hint: "Единый фронт продаж" },
      exclude_deal_otkaz: { title: "Без отказа", hint: "Исключить стадии/статусы с «отказ»" },
      exclude_deal_zakryta: { title: "Без закрытых", hint: "Исключить стадии с «закрыта»" },
      exclude_deal_zaklyuchen: { title: "Без заключён.", hint: "Исключить стадии с «заключен»" },
      exclude_current_for_sale: {
        title: "Без «К ПРОДАЖЕ»",
        hint: "Только лиды с текущим статусом ≠ «К ПРОДАЖЕ»",
      },
    };
    const meta = labels[item.name] || {
      title: item.short_label || item.name,
      hint: item.column_label || item.name,
    };

    let stateText = "выкл";
    let stateKind = "off";
    if (item.filter_mode === "exclude") {
      if (item.enabled) {
        stateText = "искл.";
        stateKind = "on";
      } else {
        stateText = "выкл";
        stateKind = "off";
      }
    } else if (!item.enabled) {
      stateText = "все";
      stateKind = "off";
    } else if (Number(item.value) === 1) {
      stateText = "вкл";
      stateKind = "on";
    } else {
      stateText = "выкл";
      stateKind = "off";
    }

    return {
      title: meta.title,
      stateText,
      stateKind,
      tooltip: item.tooltip || `${meta.hint}. Сейчас: ${stateText}`,
    };
  }

  function populateConfigLockedFilters() {
    if (!configLockedFiltersBlock || !configLockedFiltersList) return;
    const locked = KanbanData.configLockedFilters();
    configLockedFiltersList.innerHTML = "";
    if (!locked.length) {
      configLockedFiltersBlock.hidden = true;
      return;
    }
    configLockedFiltersBlock.hidden = false;

    locked.forEach((item) => {
      const ui = lockedFilterUi(item);
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "locked-chip";
      chip.setAttribute("role", "listitem");
      chip.classList.toggle("is-on", ui.stateKind === "on");
      chip.classList.toggle("is-off", ui.stateKind === "off");
      chip.title = ui.tooltip;
      chip.setAttribute("aria-label", ui.tooltip);

      const iconWrap = document.createElement("span");
      iconWrap.className = "locked-chip__icon";
      iconWrap.appendChild(KanbanIcons.create(KanbanIcons.pipelineIcon(item.name), "icon icon--sm"));

      const body = document.createElement("span");
      body.className = "locked-chip__body";

      const text = document.createElement("span");
      text.className = "locked-chip__text";
      text.textContent = ui.title;

      const mark = document.createElement("span");
      mark.className = "locked-chip__mark";
      mark.textContent = ui.stateText;

      body.appendChild(text);
      body.appendChild(mark);
      chip.appendChild(iconWrap);
      chip.appendChild(body);
      configLockedFiltersList.appendChild(chip);
    });
  }

  function populatePipelineFilters() {
    if (!pipelineFilterList) return;
    const catalog = KanbanData.filterCatalog();
    pipelineFilterList.innerHTML = "";
    populateConfigLockedFilters();
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
      groupTitle.textContent = "Исключить терминальные стадии";
      group.appendChild(groupTitle);

      exclusion.forEach((item) => {
        group.appendChild(createPipelineToggle(item, active.has(item.name)));
      });
      pipelineFilterList.appendChild(group);
    }

    if (labelVariants.length) {
      const group = document.createElement("div");
      group.className = "pipeline-toggle-group pipeline-toggle-group--exclusive";
      group.dataset.exclusiveGroup = "strategy_label";

      const groupTitle = document.createElement("div");
      groupTitle.className = "pipeline-toggle-group__title";
      groupTitle.textContent = "Метка";
      group.appendChild(groupTitle);

      const hint = document.createElement("p");
      hint.className = "pipeline-toggle-group__hint";
      hint.textContent = "Одна или все выкл — не обе сразу";
      group.appendChild(hint);

      labelVariants.forEach((item) => {
        const toggle = createPipelineToggle(item, active.has(item.name));
        toggle.classList.add("pipeline-toggle--exclusive");
        group.appendChild(toggle);
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
    const exclusiveGroup = item?.exclusive_group || btn.dataset.exclusiveGroup || null;
    const active = new Set(KanbanData.getActivePipelineFilters());
    const turningOn = btn.getAttribute("aria-pressed") !== "true";

    if (turningOn) {
      // Метки: либо одна, либо ни одной — при включении второй гасим первую
      if (exclusiveGroup) {
        catalog
          .filter((c) => c.exclusive_group === exclusiveGroup && c.name !== name)
          .forEach((other) => active.delete(other.name));
        pipelineFilterList
          ?.querySelectorAll(`.pipeline-toggle[data-exclusive-group="${exclusiveGroup}"]`)
          .forEach((otherBtn) => {
            if (otherBtn.dataset.filter !== name) {
              active.delete(otherBtn.dataset.filter);
            }
          });
      }
      active.add(name);
    } else {
      active.delete(name);
    }

    KanbanData.setActivePipelineFilters(Array.from(active));
    syncPipelineToggleUi(KanbanData.getActivePipelineFilters());

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
    const lockedEl = document.getElementById("aggregationModeLocked");
    const mode = modes.includes(current) ? current : modes[0] || "group_product";
    KanbanData.setAggregationMode(mode);
    if (controls.aggregationMode) {
      controls.aggregationMode.value = mode;
      controls.aggregationMode.hidden = true;
    }
    if (lockedEl) {
      const label = KanbanData.aggregationLabel(mode);
      lockedEl.querySelector(".locked-chip__text").textContent = label;
      lockedEl.classList.toggle("is-on", true);
      lockedEl.title =
        `Фиксировано в config: product_analysis_mode = ${mode}. ` +
        "Смена только через config.json (пересчёт JSON).";
      lockedEl.setAttribute("aria-label", lockedEl.title);
    }
    updateAggregationUi();
  }

  function syncAnalysisLevelUi() {
    const block = document.getElementById("levelFilterBlock");
    const lockedEl = document.getElementById("levelModeLocked");
    const locked = KanbanData.isAnalysisLevelLocked();
    const level = KanbanData.lockedAnalysisLevel();

    if (controls.levelFilter) {
      controls.levelFilter.hidden = locked;
      if (locked) controls.levelFilter.value = "";
    }
    if (lockedEl) {
      lockedEl.hidden = !locked;
      if (locked) {
        const label =
          level === "status" ? "Статус" : level === "substage" ? "Подстадии" : level || "status";
        const text = lockedEl.querySelector(".locked-chip__text");
        if (text) text.textContent = label;
        lockedEl.classList.toggle("is-on", true);
        lockedEl.title =
          `Фиксировано в config: stage_analysis_mode = ${KanbanData.stageAnalysisMode() || level}. ` +
          "Фильтр уровня в UI отключён.";
        lockedEl.setAttribute("aria-label", lockedEl.title);
      }
    }
    if (block && !locked && !controls.levelFilter) {
      block.hidden = true;
    }
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

    syncAnalysisLevelUi();
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
          `<p>В JSON нет блока <code>managers.charts</code> — пересоберите отчёт с <code>html_json.embed_managers: true</code>.</p>` +
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

  function syncManagersTabVisibility() {
    const show = Boolean(KanbanData.getPayload()?.meta?.show_managers_tab);
    const btn = document.getElementById("managersTabBtn");
    const panel = document.getElementById("managersTab");
    if (btn) btn.hidden = !show;
    if (panel && !show) panel.classList.remove("active");
    if (!show && btn?.classList.contains("active")) {
      btn.classList.remove("active");
      btn.setAttribute("aria-selected", "false");
      const chartsBtn = document.querySelector('.mode-tabs .tab[data-tab="charts"]');
      const chartsPanel = document.getElementById("chartsTab");
      chartsBtn?.classList.add("active");
      chartsBtn?.setAttribute("aria-selected", "true");
      chartsPanel?.classList.add("active");
    }
  }

  const jsonLoadPanel = document.getElementById("jsonLoadPanel");
  const jsonLoadedPanel = document.getElementById("jsonLoadedPanel");
  const jsonLoadedName = document.getElementById("jsonLoadedName");
  const btnResetJson = document.getElementById("btnResetJson");
  let loadedJsonFileName = "";

  function setJsonLoadUi(loaded, fileName) {
    if (jsonLoadPanel) jsonLoadPanel.hidden = Boolean(loaded);
    if (jsonLoadedPanel) jsonLoadedPanel.hidden = !loaded;
    if (loaded && jsonLoadedName) {
      const name = fileName || loadedJsonFileName || "Файл загружен";
      jsonLoadedName.textContent = name;
      jsonLoadedName.title = name;
    }
    const loadLabel = document.getElementById("jsonLoadBlock")?.querySelector(".filter-block__label");
    if (loadLabel) loadLabel.textContent = loaded ? "Данные" : "Загрузка JSON";
  }

  function resetDashboardUi() {
    KanbanData.clearPayload();
    KanbanManagers.clearPayload();
    KanbanPivot.resetSort();
    loadedJsonFileName = "";
    if (controls.jsonFile) controls.jsonFile.value = "";

    setJsonLoadUi(false);
    syncManagersTabVisibility();

    if (pipelineFilterList) pipelineFilterList.innerHTML = "";
    if (pipelineFilterBlock) pipelineFilterBlock.hidden = true;
    if (configLockedFiltersBlock) configLockedFiltersBlock.hidden = true;
    if (configLockedFiltersList) configLockedFiltersList.innerHTML = "";

    chartsGrid.innerHTML =
      `<div class="empty-state panel"><p class="empty-state__title">Загрузите JSON-отчёт</p>` +
      `<p>Выберите файл <code>OUT/kanban_report_*.json</code>.</p></div>`;
    if (pivotTable) {
      const thead = pivotTable.querySelector("thead");
      const tbody = pivotTable.querySelector("tbody");
      if (thead) thead.innerHTML = "";
      if (tbody) tbody.innerHTML = "";
    }
    if (pivotCaption) pivotCaption.textContent = "";
    if (managersPanel) managersPanel.innerHTML = "";
    updateStats(0);
    metaInfo.textContent = "Выберите OUT/kanban_report_*.json (один файл). Сервер не нужен.";
  }

  async function onJsonLoaded(text, fileName) {
    try {
      KanbanData.loadJson(text);
      const data = KanbanData.getPayload();
      loadedJsonFileName = fileName || loadedJsonFileName || "kanban_report.json";
      setJsonLoadUi(true, loadedJsonFileName);
      syncManagersTabVisibility();

      if (data?.managers) {
        KanbanManagers.loadPayload(data.managers);
      } else {
        KanbanManagers.clearPayload();
      }

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
      metaInfo.textContent = `Ошибка загрузки: ${message}`;
      console.error("[KANBAN] loadJson failed:", err);
      setJsonLoadUi(false);
      const isFetch =
        /fetch|срез|Failed to fetch|NetworkError|не удалось загрузить срез/i.test(message);
      chartsGrid.innerHTML =
        `<div class="empty-state panel"><p class="empty-state__title">${
          isFetch
            ? "Не удалось подгрузить срез (режим split)"
            : "Не удалось загрузить JSON"
        }</p>` +
        `<p>${message}</p>` +
        `<p class="filter-block__hint">Нужен monolith: <code>OUT/kanban_report_*.json</code> после <code>run.py</code>.</p></div>`;
    }
  }

  controls.jsonFile.addEventListener("change", (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => onJsonLoaded(String(reader.result), file.name);
    reader.onerror = () => {
      metaInfo.textContent = "Не удалось прочитать выбранный файл.";
    };
    reader.readAsText(file, "UTF-8");
  });

  btnResetJson?.addEventListener("click", () => {
    resetDashboardUi();
  });

  pipelineFilterList?.addEventListener("click", onPipelineToggleClick);

  controls.aggregationMode?.addEventListener("change", () => {
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
    if (!KanbanData.isAnalysisLevelLocked() && controls.levelFilter) {
      controls.levelFilter.value = "";
    }
    KanbanData.setActivePipelineFilters(KanbanData.defaultActivePipelineFilters());
    populatePipelineFilters();
    populateTbFilter([]);
    populateGroupFilter();
    populateProductFilter();
    const defaultView = KanbanData.getPayload()?.visualizations?.default_view || {};
    controls.metricSelect.value = defaultView.metric || "days_on_stage";
    controls.indicatorSelect.value = defaultView.indicator || "p80";
    syncAnalysisLevelUi();
    refresh();
  });

  function bindSidebarToggle(hideId, showId, collapsedClass) {
    const hideBtn = document.getElementById(hideId);
    const showBtn = document.getElementById(showId);
    hideBtn?.addEventListener("click", () => {
      if (collapsedClass === "is-filters-collapsed") {
        const cur = parseInt(getComputedStyle(app).getPropertyValue("--filters-w"), 10);
        if (Number.isFinite(cur) && cur > 0) {
          app.dataset.filtersWidthBeforeCollapse = String(cur);
        }
        app.style.setProperty("--filters-w", "0px");
      }
      app.classList.add(collapsedClass);
      hideBtn.setAttribute("aria-expanded", "false");
      showBtn?.setAttribute("aria-expanded", "true");
    });
    showBtn?.addEventListener("click", () => {
      app.classList.remove(collapsedClass);
      if (collapsedClass === "is-filters-collapsed") {
        const saved = Number(app.dataset.filtersWidthBeforeCollapse || 0);
        const fallback = 360;
        const w = saved >= 280 ? saved : fallback;
        app.style.setProperty("--filters-w", `${w}px`);
      }
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
      const panel = document.getElementById(`${tab.dataset.tab}Tab`);
      panel?.classList.add("active");
      if (tab.dataset.tab === "pivot") {
        refreshKeepPivotSort();
      } else if (tab.dataset.tab === "managers") {
        renderManagers(getFilters());
      } else if (tab.dataset.tab === "charts") {
        refresh();
      }
    });
  });

  metaInfo.textContent =
    "Выберите OUT/kanban_report_*.json (один файл). Сервер не нужен.";
})();
