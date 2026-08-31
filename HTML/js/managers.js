/** Загрузка и отображение JSON аналитики менеджеров (отдельный файл). */

const KanbanManagers = (() => {
  let payload = null;

  function loadJson(text) {
    payload = JSON.parse(text);
    return payload;
  }

  function getPayload() {
    return payload;
  }

  function hasData() {
    return Boolean(payload?.top_by_tb?.length);
  }

  function metaLine() {
    if (!payload?.meta) return "";
    const m = payload.meta;
    return `P${m.percentile} · ${m.metric} · топ-${m.top_managers_per_tb} на ТБ`;
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

  return { loadJson, getPayload, hasData, metaLine, render };
})();
