/** Загрузка JSON менеджеров, панель BOTTOM и bar-графики «КМ с нарушениями P80». */

const KanbanManagers = (() => {
  let payload = null;

  function loadJson(text) {
    payload = JSON.parse(text);
    return payload;
  }

  function getPayload() {
    return payload;
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

  function filterDetail(filters) {
    const rows = payload?.detail_by_product || [];
    const tbSet = resolveTbFilter(filters);
    let result = rows;
    if (tbSet) result = result.filter((row) => tbSet.has(String(row.tb)));
    if (filters?.productGroups?.length) {
      result = result.filter((row) => filters.productGroups.includes(String(row.product_group)));
    }
    if (filters?.products?.length) {
      result = result.filter((row) => filters.products.includes(String(row.product)));
    }
    if (filters?.stage) {
      result = result.filter((row) => String(row.stage_key) === filters.stage);
    }
    return result;
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

  /** Уникальные КМ с нарушениями по ключу сегмента (группа или продукт). */
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

  /** Уникальные КМ с нарушениями внутри одного ТБ по сегменту. */
  function aggregateFactsByTbSegment(facts, tb, groupOnly) {
    const scoped = facts.filter((f) => String(f.tb) === String(tb));
    return aggregateFactsBySegment(scoped, groupOnly);
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
            "Число уникальных КМ, у которых есть сделки с превышением порога продукта×стадии",
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
            "Уникальные КМ с превышением порога (с учётом фильтров ТБ и стадии)",
            segments,
            "km_with_violations",
            "label"
          )
        );
      }

      const byTb = filterByTbRows(filters)
        .filter((row) => row.km_with_violations > 0)
        .slice()
        .sort((a, b) => b.km_with_violations - a.km_with_violations)
        .slice(0, limit);

      byTb.forEach((row) => {
        const tbSegments = aggregateFactsByTbSegment(facts, row.tb, groupOnly).slice(0, limit);
        if (!tbSegments.length) return;
        groups.push(
          toBarGroup(
            `${KanbanData.tbDisplay(row.tb)} · ${segmentDim}`,
            `${row.km_with_violations} КМ с нарушениями · ${row.violation_deals} сделок`,
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

  function render(container, filters) {
    if (!container) return;
    container.innerHTML = "";

    if (!hasData()) {
      container.innerHTML =
        `<div class="managers-empty">` +
        `<p class="managers-empty__title">Нет данных по менеджерам</p>` +
        `<p>Загрузите <code>kanban_managers_*.json</code> или выполните <code>run.py</code> с колонкой КМ.</p>` +
        `</div>`;
      return;
    }

    const head = document.createElement("div");
    head.className = "managers-panel__head";
    head.innerHTML =
      `<h3 class="managers-panel__title">BOTTOM: менеджеры с превышениями P80</h3>` +
      `<p class="managers-panel__intro">${metaLine()} · срок на стадии &gt; порога продукта×стадии</p>`;
    container.appendChild(head);

    const top = filterTop(filters);
    if (!top.length) {
      const empty = document.createElement("p");
      empty.className = "managers-panel__empty";
      empty.textContent = "Нет менеджеров для выбранных фильтров ТБ.";
      container.appendChild(empty);
      return;
    }

    const topWrap = document.createElement("div");
    topWrap.className = "managers-top-grid";
    top.forEach((row) => {
      const card = document.createElement("div");
      card.className = "manager-card";
      card.innerHTML =
        `<div class="manager-card__rank">${row.rank}</div>` +
        `<div class="manager-card__body">` +
        `<div class="manager-card__name">${escapeHtml(row.km)}</div>` +
        `<div class="manager-card__meta">${escapeHtml(row.tb)}</div>` +
        `<div class="manager-card__stat"><span>${row.exceedance_count}</span> превышений · ${row.total_leads} лидов</div>` +
        `</div>`;
      topWrap.appendChild(card);
    });
    container.appendChild(topWrap);

    const detail = filterDetail(filters);
    if (detail.length) {
      const tableWrap = document.createElement("div");
      tableWrap.className = "managers-detail-wrap";
      const table = document.createElement("table");
      table.className = "managers-detail-table";
      table.innerHTML =
        `<thead><tr>` +
        `<th>ТБ</th><th>КМ</th><th>Группа</th><th>Продукт</th><th>Стадия</th><th>P80</th><th>Превыш.</th>` +
        `</tr></thead><tbody></tbody>`;
      const tbody = table.querySelector("tbody");
      detail
        .sort((a, b) => b.exceedance_count - a.exceedance_count)
        .slice(0, 200)
        .forEach((row) => {
          const tr = document.createElement("tr");
          tr.innerHTML =
            `<td>${escapeHtml(row.tb)}</td>` +
            `<td>${escapeHtml(row.km)}</td>` +
            `<td>${escapeHtml(row.product_group)}</td>` +
            `<td>${escapeHtml(row.product || "—")}</td>` +
            `<td>${escapeHtml(row.stage_key)}</td>` +
            `<td>${row.threshold_days ?? "—"}</td>` +
            `<td><b>${row.exceedance_count}</b></td>`;
          tbody.appendChild(tr);
        });
      tableWrap.appendChild(table);
      container.appendChild(tableWrap);
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
