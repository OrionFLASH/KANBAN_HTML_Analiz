/** Загрузка JSON менеджеров, детальные карточки КМ и bar-графики нарушений P80. */

const KanbanManagers = (() => {
  let payload = null;
  let selectedKey = null;

  function loadJson(text) {
    payload = JSON.parse(text);
    selectedKey = null;
    return payload;
  }

  function getPayload() {
    return payload;
  }

  function managerKey(tb, km) {
    return `${String(tb)}|${String(km)}`;
  }

  function chartsData() {
    return payload?.charts || { by_tb: [], facts: [] };
  }

  function hasData() {
    return Boolean(payload?.top_by_tb?.length);
  }

  function hasChartData() {
    const charts = chartsData();
    return Boolean(charts.by_tb?.length || charts.facts?.length);
  }

  function metaLine() {
    if (!payload?.meta) return "";
    const m = payload.meta;
    return `P${m.percentile} · ${m.metric} · топ-${m.top_managers_per_tb} на ТБ`;
  }

  function percentileLabel() {
    const m = payload?.meta || {};
    return String(m.percentile_label || `p${m.percentile || 80}`).toUpperCase();
  }

  function resolveTbFilter(filters) {
    if (!filters?.tbs?.length) return null;
    const allLabel = KanbanData.allTbLabel();
    const picked = filters.tbs.map(String).filter((tb) => tb !== allLabel);
    if (!picked.length || KanbanData.isTbSelectionAll(filters.tbs)) return null;
    return new Set(picked);
  }

  function filterTop(filters) {
    const rows = payload?.top_by_tb || [];
    const tbSet = resolveTbFilter(filters);
    if (!tbSet) return rows;
    return rows.filter((row) => tbSet.has(String(row.tb)));
  }

  function filterFacts(filters) {
    let rows = chartsData().facts || [];
    const tbSet = resolveTbFilter(filters);
    if (tbSet) rows = rows.filter((row) => tbSet.has(String(row.tb)));
    if (filters?.productGroups?.length) {
      rows = rows.filter((row) => filters.productGroups.includes(String(row.product_group)));
    }
    if (filters?.products?.length) {
      rows = rows.filter((row) => filters.products.includes(String(row.product)));
    }
    if (filters?.stage) {
      rows = rows.filter((row) => String(row.stage_key) === filters.stage);
    }
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
      .sort((a, b) => b.km_with_violations - a.km_with_violations || b.violation_deals - a.violation_deals);
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
        .sort((a, b) => b.km_with_violations - a.km_with_violations || b.violation_deals - a.violation_deals);

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

  function renderDetailCard(row, filters) {
    const hotspots = (row.hotspots || []).filter((spot) => {
      if (filters?.stage && String(spot.stage_key) !== filters.stage) return false;
      if (filters?.productGroups?.length && !filters.productGroups.includes(String(spot.product_group))) {
        return false;
      }
      if (filters?.products?.length && !filters.products.includes(String(spot.product))) return false;
      return true;
    });

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
      `Почему в топе: наибольшие отклонения по продуктам и стадиям (срок &gt; порога ${pLabel}).` +
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

    const top = filterTop(filters);
    if (!top.length) {
      const empty = document.createElement("p");
      empty.className = "managers-panel__empty";
      empty.textContent = "Нет менеджеров для выбранных фильтров ТБ.";
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
      detailWrap.innerHTML = renderDetailCard(selected, filters);
      container.appendChild(detailWrap);
    }
  }

  return {
    loadJson,
    getPayload,
    hasData,
    hasChartData,
    metaLine,
    buildChartGroups,
    render,
  };
})();
