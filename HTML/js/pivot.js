/** Сводная матрица продукт × стадия. */

const KanbanPivot = (() => {
  function heatColor(value, min, max) {
    if (value == null || min == null || max == null || min === max) return "";
    const t = (value - min) / (max - min);
    const r = Math.round(99 + t * (248 - 99));
    const g = Math.round(190 - t * (190 - 105));
    const b = Math.round(123 - t * (123 - 107));
    return `rgb(${r},${g},${b})`;
  }

  function render(table, matrix, captionEl, filters) {
    const thead = table.querySelector("thead");
    const tbody = table.querySelector("tbody");
    thead.innerHTML = "";
    tbody.innerHTML = "";

    const { stages, rows, products, values, tb, metric, indicator, row_dimension: rowDim } = matrix;
    const rowLabels = rows || products || [];
    if (!rowLabels.length) {
      captionEl.textContent = "Нет данных для матрицы с текущими фильтрами.";
      return;
    }

    const tbLabel = tb === KanbanData.allTbLabel() ? KanbanData.allTbDisplay() : tb;
    const rowHeader = rowDim === "product_group" || KanbanData.isGroupOnly() ? "Группа" : "Продукт";
    captionEl.textContent =
      `Свод: ${tbLabel} | ${KanbanData.METRIC_LABELS[metric] || metric} | ${KanbanData.INDICATOR_LABELS[indicator] || indicator}`;

    const headerRow = document.createElement("tr");
    const corner = document.createElement("th");
    corner.textContent = rowHeader;
    headerRow.appendChild(corner);
    stages.forEach((stage) => {
      const th = document.createElement("th");
      th.textContent = stage;
      headerRow.appendChild(th);
    });
    thead.appendChild(headerRow);

    let min = Infinity;
    let max = -Infinity;
    rowLabels.forEach((rowLabel) => {
      stages.forEach((stage) => {
        const val = values[rowLabel]?.[stage];
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
        const td = document.createElement("td");
        const val = values[rowLabel]?.[stage];
        td.textContent = val == null ? "—" : String(val);
        td.className = "cell-heat";
        if (val != null) {
          td.style.background = heatColor(val, min, max);
          td.style.color = val > (min + max) / 2 ? "#0f1419" : "#e2e8f0";
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  return { render };
})();
