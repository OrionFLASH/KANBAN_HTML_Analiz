/** Загрузка JSON менеджеров, отбор TOP КМ по фильтрам и детальные карточки. */

const KanbanManagers = (() => {
  let payload = null;
  let selectedKey = null;
  /** Текущий фильтр метки для отбора TOP (инициализируется из meta.rank_selection). */
  let strategyFilter = "all";

  const STRATEGY_LABELS = {
    all: "Все метки",
    strategy: "Стратегия",
    strategy_2026: "Стратегия · 2026",
    non_strategy: "Без стратегии",
  };

  function loadJson(text) {
    payload = JSON.parse(text);
    selectedKey = null;
    strategyFilter = payload?.meta?.rank_selection?.strategy_filter || "all";
    return payload;
  }

  function getPayload() {
    return payload;
  }

  function getStrategyFilter() {
    return strategyFilter;
  }

  function setStrategyFilter(mode) {
    strategyFilter = mode || "all";
    selectedKey = null;
  }

  function managerKey(tb, km) {
    return `${String(tb)}|${String(km)}`;
  }

  function chartsData() {
    return payload?.charts || { by_tb: [], facts: [] };
  }

  function hasData() {
    return Boolean(
      payload?.records?.length || payload?.top_by_tb?.length || payload?.detail_by_product?.length
    );
  }

  function hasChartData() {
    const charts = chartsData();
    return Boolean(charts.by_tb?.length || charts.facts?.length);
  }

  function metaLine() {
    if (!payload?.meta) return "";
    const m = payload.meta;
    const strat = STRATEGY_LABELS[strategyFilter] || strategyFilter;
    return `P${m.percentile} · ${m.metric} · топ-${m.top_managers_per_tb} на ТБ · ${strat}`;
  }

  function percentileLabel() {
    const m = payload?.meta || {};
    return String(m.percentile_label || `p${m.percentile || 80}`).toUpperCase();
  }

  function topLimit() {
    return Math.max(1, Number(payload?.meta?.top_managers_per_tb) || 3);
  }

  function resolveTbFilter(filters) {
    if (!filters?.tbs?.length) return null;
    const allLabel = KanbanData.allTbLabel();
    const picked = filters.tbs.map(String).filter((tb) => tb !== allLabel);
    if (!picked.length || KanbanData.isTbSelectionAll(filters.tbs)) return null;
    return new Set(picked);
  }

  function matchesStrategy(label, mode) {
    const text = String(label ?? "");
    if (!mode || mode === "all") return true;
    if (mode === "strategy") return /стратегия/i.test(text);
    if (mode === "strategy_2026") return /стратегия/i.test(text) && /2026/.test(text);
    if (mode === "non_strategy") return !/стратегия/i.test(text);
    return true;
  }

  /** Пул групп/продуктов из config.rank_selection + сужение UI-фильтрами. */
  function effectiveScope(filters) {
    const cfg = payload?.meta?.rank_selection || {};
    const poolGroups = (cfg.product_groups || []).filter(Boolean);
    const poolProducts = (cfg.products || []).filter(Boolean);

    let groups = null;
    if (filters?.productGroups?.length) {
      groups = new Set(filters.productGroups.map(String));
      if (poolGroups.length) {
        const pool = new Set(poolGroups.map(String));
        groups = new Set([...groups].filter((g) => pool.has(g)));
      }
    } else if (poolGroups.length) {
      groups = new Set(poolGroups.map(String));
    }

    let products = null;
    if (filters?.products?.length) {
      products = new Set(filters.products.map(String));
      if (poolProducts.length) {
        const pool = new Set(poolProducts.map(String));
        products = new Set([...products].filter((p) => pool.has(p)));
      }
    } else if (poolProducts.length) {
      products = new Set(poolProducts.map(String));
    }

    return { groups, products };
  }

  function filterLeadRecords(filters) {
    const rows = payload?.records || [];
    if (!rows.length) return [];

    const tbSet = resolveTbFilter(filters);
    const { groups, products } = effectiveScope(filters);

    return rows.filter((row) => {
      if (tbSet && !tbSet.has(String(row.tb))) return false;
      if (groups && !groups.has(String(row.product_group))) return false;
      if (products && !products.has(String(row.product))) return false;
      if (filters?.stage && String(row.stage_key) !== filters.stage) return false;
      if (!matchesStrategy(row.label, strategyFilter)) return false;
      return true;
    });
  }

  function aggregateHotspots(exceededRows, limit) {
    const map = new Map();
    exceededRows.forEach((row) => {
      const key = [
        String(row.tb),
        String(row.km),
        String(row.product_group),
        String(row.product ?? "—"),
        String(row.stage_key),
      ].join("|");
      if (!map.has(key)) {
        map.set(key, {
          tb: String(row.tb),
          km: String(row.km),
          product_group: String(row.product_group),
          product: row.product != null ? String(row.product) : "—",
          stage_key: String(row.stage_key),
          exceedance_count: 0,
          threshold_days: Number(row.threshold_days) || 0,
          max_days: Number(row.days_int) || 0,
          max_overshoot: 0,
          avg_overshoot: 0,
          _days: [],
        });
      }
      const spot = map.get(key);
      spot.exceedance_count += 1;
      const days = Number(row.days_int) || 0;
      spot._days.push(days);
      if (days > spot.max_days) spot.max_days = days;
      const thresh = Number(row.threshold_days) || 0;
      if (thresh > spot.threshold_days) spot.threshold_days = thresh;
    });

    const hotspots = [...map.values()].map((spot) => {
      const overs = Math.max(0, spot.max_days - spot.threshold_days);
      const avgDays = spot._days.length
        ? spot._days.reduce((a, b) => a + b, 0) / spot._days.length
        : 0;
      return {
        tb: spot.tb,
        km: spot.km,
        product_group: spot.product_group,
        product: spot.product,
        stage_key: spot.stage_key,
        exceedance_count: spot.exceedance_count,
        threshold_days: Math.round(spot.threshold_days * 10) / 10,
        max_days: Math.round(spot.max_days * 10) / 10,
        max_overshoot: Math.round(overs * 10) / 10,
        avg_overshoot: Math.round(Math.max(0, avgDays - spot.threshold_days) * 10) / 10,
      };
    });

    hotspots.sort(
      (a, b) =>
        b.exceedance_count - a.exceedance_count ||
        b.max_overshoot - a.max_overshoot ||
        String(a.stage_key).localeCompare(String(b.stage_key), "ru")
    );
    return hotspots.slice(0, limit);
  }

  function recomputeTop(filters) {
    const records = filterLeadRecords(filters);
    if (records.length) {
      const topN = topLimit();
      const hotLimit = Number(payload?.meta?.top_hotspots_per_manager) || 5;
      const byManager = new Map();

      records.forEach((row) => {
        const key = managerKey(row.tb, row.km);
        if (!byManager.has(key)) {
          byManager.set(key, {
            tb: String(row.tb),
            km: String(row.km),
            exceedance_count: 0,
            total_leads: new Set(),
            exceeded_rows: [],
          });
        }
        const bucket = byManager.get(key);
        bucket.total_leads.add(String(row.lead_id));
        if (row.exceeded) {
          bucket.exceedance_count += 1;
          bucket.exceeded_rows.push(row);
        }
      });

      const tbOrder = [...new Set(records.map((r) => String(r.tb)))].sort((a, b) =>
        a.localeCompare(b, "ru")
      );
      const result = [];

      tbOrder.forEach((tb) => {
        const bucketRows = [...byManager.values()]
          .filter((b) => b.tb === tb)
          .sort(
            (a, b) =>
              b.exceedance_count - a.exceedance_count ||
              b.total_leads.size - a.total_leads.size ||
              String(a.km).localeCompare(String(b.km), "ru")
          )
          .slice(0, topN);

        bucketRows.forEach((row, idx) => {
          result.push({
            tb: row.tb,
            km: row.km,
            rank: idx + 1,
            exceedance_count: row.exceedance_count,
            total_leads: row.total_leads.size,
            hotspots: aggregateHotspots(row.exceeded_rows, hotLimit),
          });
        });
      });

      return result;
    }

    return filterTopLegacy(filters);
  }

  function filterTopLegacy(filters) {
    const rows = payload?.top_by_tb || [];
    const tbSet = resolveTbFilter(filters);
    if (!tbSet) return rows;
    return rows.filter((row) => tbSet.has(String(row.tb)));
  }

  function filterFacts(filters) {
    let rows = chartsData().facts || [];
    const tbSet = resolveTbFilter(filters);
    if (tbSet) rows = rows.filter((row) => tbSet.has(String(row.tb)));
    const { groups, products } = effectiveScope(filters);
    if (groups) rows = rows.filter((row) => groups.has(String(row.product_group)));
    if (products) rows = rows.filter((row) => products.has(String(row.product)));
    if (filters?.stage) rows = rows.filter((row) => String(row.stage_key) === filters.stage);
    return rows;
  }

  function filterByTbRows(filters) {
    let rows = chartsData().by_tb || [];
    const tbSet = resolveTbFilter(filters);
    if (tbSet) rows = rows.filter((row) => tbSet.has(String(row.tb)));
    return rows;
  }

  function aggregateFactsBySegment(facts, groupOnly) {
    const map = new Map();
    facts.forEach((fact) => {
      const label = groupOnly
        ? String(fact.product_group)
        : `${fact.product_group} · ${fact.product || "—"}`;
      if (!map.has(label)) map.set(label, { kms: new Set(), deals: 0 });
      const bucket = map.get(label);
      bucket.kms.add(String(fact.km));
      bucket.deals += Number(fact.deals) || 0;
    });
    return [...map.entries()]
      .map(([label, v]) => ({
        label,
        km_with_violations: v.kms.size,
        violation_deals: v.deals,
      }))
      .sort(
        (a, b) =>
          b.km_with_violations - a.km_with_violations || b.violation_deals - a.violation_deals
      );
  }

  function aggregateFactsByTbSegment(facts, tb, groupOnly) {
    return aggregateFactsBySegment(
      facts.filter((f) => String(f.tb) === String(tb)),
      groupOnly
    );
  }

  function toBarGroup(title, subtitle, rows, valueKey, labelKey) {
    return {
      title,
      subtitle,
      labels: rows.map((r) => r[labelKey]),
      values: rows.map((r) => Number(r[valueKey]) || 0),
      deals: rows.map((r) => Number(r.violation_deals) || 0),
      kmTotal: rows.map((r) => (r.km_total != null ? Number(r.km_total) : null)),
      tier: "summary",
      chartKind: "bar",
    };
  }

  function buildChartGroups(filters, chartMode, maxSeries) {
    const limit = Math.max(1, Number(maxSeries) || 8);
    const pLabel = percentileLabel();
    const groupOnly = KanbanData.isGroupOnly();
    const segmentDim = groupOnly ? "группам" : "продуктам";
    const groups = [];

    if (chartMode === "km_by_tb") {
      const byTb = filterByTbRows(filters)
        .slice()
        .sort(
          (a, b) =>
            b.km_with_violations - a.km_with_violations || b.violation_deals - a.violation_deals
        );

      if (byTb.length) {
        groups.push(
          toBarGroup(
            `КМ с нарушениями ${pLabel} · по ТБ`,
            "Число уникальных КМ с превышением порога продукта×стадии",
            byTb.map((row) => ({
              label: KanbanData.tbDisplay(row.tb),
              km_with_violations: row.km_with_violations,
              violation_deals: row.violation_deals,
              km_total: row.km_total,
            })),
            "km_with_violations",
            "label"
          )
        );
      }

      const facts = filterFacts(filters);
      byTb.slice(0, limit).forEach((row) => {
        const segments = aggregateFactsByTbSegment(facts, row.tb, groupOnly).slice(0, limit);
        if (!segments.length) return;
        groups.push(
          toBarGroup(
            `${KanbanData.tbDisplay(row.tb)} · по ${segmentDim}`,
            `КМ с нарушениями ${pLabel} внутри ТБ`,
            segments.map((s) => ({ ...s, label: s.label })),
            "km_with_violations",
            "label"
          )
        );
      });
      return groups;
    }

    if (chartMode === "km_by_segment") {
      const facts = filterFacts(filters);
      const segments = aggregateFactsBySegment(facts, groupOnly).slice(0, limit);

      if (segments.length) {
        groups.push(
          toBarGroup(
            `КМ с нарушениями ${pLabel} · по ${segmentDim}`,
            "Уникальные КМ с превышением порога",
            segments,
            "km_with_violations",
            "label"
          )
        );
      }

      filterByTbRows(filters)
        .filter((row) => row.km_with_violations > 0)
        .sort((a, b) => b.km_with_violations - a.km_with_violations)
        .slice(0, limit)
        .forEach((row) => {
          const tbSegments = aggregateFactsByTbSegment(facts, row.tb, groupOnly).slice(0, limit);
          if (!tbSegments.length) return;
          groups.push(
            toBarGroup(
              `${KanbanData.tbDisplay(row.tb)} · ${segmentDim}`,
              `${row.km_with_violations} КМ · ${row.violation_deals} сделок`,
              tbSegments,
              "km_with_violations",
              "label"
            )
          );
        });
    }

    return groups;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function hotspotSeverity(spot) {
    const overshoot = Number(spot.max_overshoot) || 0;
    const count = Number(spot.exceedance_count) || 0;
    if (overshoot >= 20 || count >= 6) return "critical";
    if (overshoot >= 10 || count >= 3) return "warning";
    return "mild";
  }

  function segmentLabel(spot) {
    if (KanbanData.isGroupOnly()) return String(spot.product_group || "—");
    return `${spot.product_group || "—"} · ${spot.product || "—"}`;
  }

  function renderHotspotRow(spot, maxCount) {
    const severity = hotspotSeverity(spot);
    const count = Number(spot.exceedance_count) || 0;
    const barPct = maxCount > 0 ? Math.round((count / maxCount) * 100) : 0;
    const threshold = spot.threshold_days ?? "—";
    const maxDays = spot.max_days ?? "—";
    const overshoot = spot.max_overshoot ?? "—";

    return (
      `<li class="manager-hotspot manager-hotspot--${severity}">` +
      `<div class="manager-hotspot__head">` +
      `<span class="manager-hotspot__segment">${escapeHtml(segmentLabel(spot))}</span>` +
      `<span class="manager-hotspot__stage">${escapeHtml(spot.stage_key)}</span>` +
      `</div>` +
      `<div class="manager-hotspot__metrics">` +
      `<span><b>${count}</b> сделок</span>` +
      `<span>макс <b>${maxDays}</b> дн.</span>` +
      `<span>P80=${threshold}</span>` +
      `<span class="manager-hotspot__delta">+${overshoot} дн.</span>` +
      `</div>` +
      `<div class="manager-hotspot__bar" aria-hidden="true">` +
      `<span class="manager-hotspot__bar-fill" style="width:${barPct}%"></span>` +
      `</div>` +
      `</li>`
    );
  }

  function renderDetailCard(row) {
    const hotspots = row.hotspots || [];
    const maxCount = hotspots.reduce((m, s) => Math.max(m, Number(s.exceedance_count) || 0), 0);
    const pLabel = percentileLabel();

    let hotspotsHtml = "";
    if (hotspots.length) {
      hotspotsHtml =
        `<ul class="manager-hotspot-list">` +
        hotspots.map((spot) => renderHotspotRow(spot, maxCount)).join("") +
        `</ul>`;
    } else {
      hotspotsHtml = `<p class="manager-detail__empty">Нет зон превышения для текущих фильтров.</p>`;
    }

    return (
      `<article class="manager-detail" id="managerDetailCard">` +
      `<div class="manager-detail__hero">` +
      `<div class="manager-detail__rank">${row.rank}</div>` +
      `<div class="manager-detail__identity">` +
      `<h4 class="manager-detail__name">${escapeHtml(row.km)}</h4>` +
      `<p class="manager-detail__tb">${escapeHtml(row.tb)}</p>` +
      `</div>` +
      `<div class="manager-detail__totals">` +
      `<div class="manager-detail__stat">` +
      `<span class="manager-detail__stat-value">${row.exceedance_count}</span>` +
      `<span class="manager-detail__stat-label">превышений ${pLabel}</span>` +
      `</div>` +
      `<div class="manager-detail__stat">` +
      `<span class="manager-detail__stat-value">${row.total_leads}</span>` +
      `<span class="manager-detail__stat-label">лидов</span>` +
      `</div>` +
      `</div>` +
      `</div>` +
      `<p class="manager-detail__intro">` +
      `Почему в топе: наибольшие отклонения по выбранным продуктам и меткам (срок &gt; порога ${pLabel}).` +
      `</p>` +
      `<div class="manager-detail__legend">` +
      `<span class="manager-detail__legend-item manager-detail__legend-item--critical">сильное</span>` +
      `<span class="manager-detail__legend-item manager-detail__legend-item--warning">среднее</span>` +
      `<span class="manager-detail__legend-item manager-detail__legend-item--mild">умеренное</span>` +
      `</div>` +
      hotspotsHtml +
      `</article>`
    );
  }

  function rankSelectionHint() {
    const cfg = payload?.meta?.rank_selection || {};
    const parts = [];
    if (cfg.product_groups?.length) parts.push(`группы: ${cfg.product_groups.length}`);
    if (cfg.products?.length) parts.push(`продукты: ${cfg.products.length}`);
    if (parts.length) return `Пул config: ${parts.join(", ")}.`;
    return "Пул config: все группы и продукты.";
  }

  function renderStrategyControl(container, filters, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "managers-rank-controls";
    wrap.innerHTML =
      `<label class="field field--inline">` +
      `<span class="field-label">Метка (отбор TOP)</span>` +
      `<select class="field-control" id="managerStrategyFilter"></select>` +
      `</label>` +
      `<p class="managers-rank-controls__hint">${escapeHtml(rankSelectionHint())} Группы/продукты — в панели фильтров справа.</p>`;

    const select = wrap.querySelector("#managerStrategyFilter");
    Object.entries(STRATEGY_LABELS).forEach(([value, label]) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    });
    select.value = strategyFilter;
    select.addEventListener("change", () => {
      setStrategyFilter(select.value);
      onChange();
    });
    container.appendChild(wrap);
  }

  function render(container, filters) {
    if (!container) return;
    container.innerHTML = "";

    if (!hasData()) {
      container.innerHTML =
        `<div class="managers-empty">` +
        `<p class="managers-empty__title">Нет данных по менеджерам</p>` +
        `<p>Загрузите <code>kanban_report_managers_*.json</code> или выполните <code>run.py</code> с колонкой КМ.</p>` +
        `</div>`;
      return;
    }

    const head = document.createElement("div");
    head.className = "managers-panel__head";
    head.innerHTML =
      `<h3 class="managers-panel__title">Менеджеры: превышения P80</h3>` +
      `<p class="managers-panel__intro">${metaLine()} · выберите КМ для детализации</p>`;
    container.appendChild(head);

    renderStrategyControl(container, filters, () => render(container, filters));

    const top = recomputeTop(filters);
    if (!top.length) {
      const empty = document.createElement("p");
      empty.className = "managers-panel__empty";
      empty.textContent = "Нет менеджеров для выбранных фильтров отбора.";
      container.appendChild(empty);
      return;
    }

    const validKeys = new Set(top.map((row) => managerKey(row.tb, row.km)));
    if (!selectedKey || !validKeys.has(selectedKey)) {
      const first = top.find((row) => row.exceedance_count > 0) || top[0];
      selectedKey = managerKey(first.tb, first.km);
    }

    const topWrap = document.createElement("div");
    topWrap.className = "managers-top-grid";
    top.forEach((row) => {
      const key = managerKey(row.tb, row.km);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "manager-card" + (key === selectedKey ? " manager-card--active" : "");
      btn.dataset.managerKey = key;
      btn.innerHTML =
        `<div class="manager-card__rank">${row.rank}</div>` +
        `<div class="manager-card__body">` +
        `<div class="manager-card__name">${escapeHtml(row.km)}</div>` +
        `<div class="manager-card__meta">${escapeHtml(row.tb)}</div>` +
        `<div class="manager-card__stat"><span>${row.exceedance_count}</span> превыш. · ${row.total_leads} лид.</div>` +
        (row.hotspots?.length
          ? `<div class="manager-card__hint">${escapeHtml(segmentLabel(row.hotspots[0]))} · ${escapeHtml(row.hotspots[0].stage_key)}</div>`
          : "") +
        `</div>`;
      btn.addEventListener("click", () => {
        selectedKey = key;
        render(container, filters);
      });
      topWrap.appendChild(btn);
    });
    container.appendChild(topWrap);

    const selected = top.find((row) => managerKey(row.tb, row.km) === selectedKey);
    if (selected) {
      const detailWrap = document.createElement("div");
      detailWrap.className = "manager-detail-wrap";
      detailWrap.innerHTML = renderDetailCard(selected);
      container.appendChild(detailWrap);
    }
  }

  return {
    loadJson,
    getPayload,
    getStrategyFilter,
    setStrategyFilter,
    hasData,
    hasChartData,
    metaLine,
    buildChartGroups,
    render,
  };
})();
