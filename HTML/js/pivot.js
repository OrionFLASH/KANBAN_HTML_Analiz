/** Сводная матрица продукт × стадия с сортировкой по колонкам. */

const KanbanPivot = (() => {
  let sortStage = null;
  let sortDir = "asc";
  let lastRenderArgs = null;

  function cellDays(cell) {
    if (cell == null) return null;
    if (typeof cell === "number") return cell;
    return cell.value != null ? Number(cell.value) : null;
  }

  function heatColor(value, min, max) {
    if (value == null || min == null || max == null || min === max) return "";
    const t = (value - min) / (max - min);
    const r = Math.round(99 + t * (248 - 99));
    const g = Math.round(190 - t * (190 - 105));
    const b = Math.round(123 - t * (123 - 107));
    return `rgb(${r},${g},${b})`;
  }

  function sortRowLabels(rowLabels, values, stage) {
    if (!stage) return rowLabels;
    const sorted = [...rowLabels];
    sorted.sort((a, b) => {
      const va = cellDays(values[a]?.[stage]);
      const vb = cellDays(values[b]?.[stage]);
      if (va == null && vb == null) return a.localeCompare(b, "ru");
      if (va == null) return 1;
      if (vb == null) return -1;
      const cmp = va - vb;
      return sortDir === "asc" ? cmp : -cmp;
    });
    return sorted;
  }

  function onHeaderClick(stage) {
    if (sortStage === stage) {
      sortDir = sortDir === "asc" ? "desc" : "asc";
    } else {
      sortStage = stage;
      sortDir = "asc";
    }
    if (lastRenderArgs) {
      render(...lastRenderArgs);
    }
  }

  function resetSort() {
    sortStage = null;
    sortDir = "asc";
  }

  function countBadge(kind, value) {
    const isGt = kind === "gt";
    const title = isGt
      ? "Лидов со сроком больше порога"
      : "Лидов со сроком не выше порога (≤)";
    const icon = isGt
      ? `<svg class="pivot-cell__icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 3.5 12.5 9H9.5v3.5h-3V9H3.5L8 3.5z"/></svg>`
      : `<svg class="pivot-cell__icon" viewBox="0 0 16 16" aria-hidden="true"><path d="M8 12.5 3.5 7H6.5V3.5h3V7H12.5L8 12.5z"/></svg>`;
    const shown = value != null ? String(value) : "—";
    const zeroClass = value === 0 ? " pivot-cell__count--zero" : "";
    return (
      `<span class="pivot-cell__count pivot-cell__count--${kind}${zeroClass}" title="${title}">` +
      icon +
      `<b>${shown}</b>` +
      `</span>`
    );
  }

  function renderCell(cell, days, min, max) {
    const td = document.createElement("td");
    td.className = "cell-heat pivot-cell";
    if (days == null) {
      td.textContent = "—";
      return td;
    }

    td.style.background = heatColor(days, min, max);
    td.style.color = days > (min + max) / 2 ? "#0f1419" : "#e2e8f0";

    const le = cell && typeof cell === "object" ? cell.leads_le : null;
    const gt = cell && typeof cell === "object" ? cell.leads_gt : null;
    const hasCounts = le != null || gt != null;

    if (!hasCounts) {
      td.textContent = String(days);
      td.title = `${days} дн.`;
      return td;
    }

    td.innerHTML =
      `<div class="pivot-cell__grid">` +
      `<span class="pivot-cell__days" title="Срок (дней)">${days}</span>` +
      `<div class="pivot-cell__counts">` +
      countBadge("gt", gt) +
      countBadge("le", le) +
      `</div>` +
      `</div>`;
    td.title = `${days} дн. · ↑ выше порога: ${gt ?? "—"} · ↓ не выше: ${le ?? "—"}`;
    return td;
  }

  function render(table, matrix, captionEl) {
    lastRenderArgs = [table, matrix, captionEl];
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    const { stages, rows, products, values, tbs, metric, indicator, row_dimension: rowDim } = matrix;
    let rowLabels = rows || products || [];
    if (!rowLabels.length) {
      captionEl.textContent = "Нет данных для матрицы с текущими фильтрами.";
      return;
    }

    if (sortStage && stages.includes(sortStage)) {
      rowLabels = sortRowLabels(rowLabels, values, sortStage);
    }

    const allLabel = KanbanData.allTbLabel();
    const tbNames = tbs && tbs.length ? tbs : [matrix.tb || allLabel];
    const tbLabel =
      tbNames.length > 1
        ? tbNames.map((tb) => (tb === allLabel ? KanbanData.allTbDisplay() : tb)).join(", ")
        : tbNames[0] === allLabel
          ? KanbanData.allTbDisplay()
          : tbNames[0];

    const rowHeader = rowDim === "product_group" || KanbanData.isGroupOnly() ? "Группа" : "Продукт";
    captionEl.textContent =
      `Свод: ${tbLabel} | ${KanbanData.METRIC_LABELS[metric] || metric} | ${KanbanData.INDICATOR_LABELS[indicator] || indicator}` +
      ` | ячейка: дни · ↑ красное >порога · ↓ бирюзовое ≤порога` +
      (tbNames.length > 1 ? " | при нескольких ТБ: max по дням" : "") +
      (sortStage ? ` | сортировка: ${sortStage} по дням (${sortDir === "asc" ? "↑" : "↓"})` : "");

    const headerRow = document.createElement("tr");
    const corner = document.createElement("th");
    corner.textContent = rowHeader;
    corner.className = "pivot-corner";
    corner.title = "Клик по заголовку стадии — сортировка строк по числу дней";
    headerRow.appendChild(corner);

    stages.forEach((stage) => {
      const th = document.createElement("th");
      th.className = "pivot-sortable";
      if (sortStage === stage) {
        th.classList.add(sortDir === "asc" ? "sort-asc" : "sort-desc");
      }
      const label = document.createElement("span");
      label.className = "pivot-sortable__label";
      label.textContent = stage;
      th.appendChild(label);
      if (sortStage === stage) {
        const icon = document.createElement("span");
        icon.className = "pivot-sortable__icon";
        icon.textContent = sortDir === "asc" ? "▲" : "▼";
        icon.setAttribute("aria-hidden", "true");
        th.appendChild(icon);
      }
      th.title = "Сортировка по дням в колонке «" + stage + "»";
      th.addEventListener("click", () => onHeaderClick(stage));
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    let min = Infinity;
    let max = -Infinity;
    rowLabels.forEach((rowLabel) => {
      stages.forEach((stage) => {
        const val = cellDays(values[rowLabel]?.[stage]);
        if (val != null) {
          min = Math.min(min, val);
          max = Math.max(max, val);
        }
      });
    });
    if (!Number.isFinite(min)) {
      min = 0;
      max = 0;
    }

    rowLabels.forEach((rowLabel) => {
      const tr = document.createElement("tr");
      const nameTd = document.createElement("td");
      nameTd.textContent = rowLabel;
      tr.appendChild(nameTd);

      stages.forEach((stage) => {
        const cell = values[rowLabel]?.[stage];
        tr.appendChild(renderCell(cell, cellDays(cell), min, max));
      });
      tbody.appendChild(tr);
    });
  }

  return { render, resetSort };
})();
