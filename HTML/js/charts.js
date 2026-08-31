/** Отрисовка графиков Chart.js. */

const KanbanCharts = (() => {
  const instances = [];

  const palette = [
    "#007AFF", "#34C759", "#FF9500", "#5856D6", "#FF3B30",
    "#5AC8FA", "#AF52DE", "#FF2D55", "#64D2FF", "#30D158",
    "#0b6bcb", "#0f8a6a", "#c27a00",
  ];

  function destroyAll() {
    instances.forEach((chart) => chart.destroy());
    instances.length = 0;
  }

  function render(container, chartGroups, options) {
    destroyAll();
    container.innerHTML = "";

    if (!chartGroups.length) {
      container.innerHTML = `<div class="empty-state"><p>Нет данных для графика с текущими фильтрами.</p></div>`;
      return;
    }

    chartGroups.forEach((group, groupIdx) => {
      const card = document.createElement("article");
      card.className = group.tier === "summary" ? "chart-card chart-card--summary" : "chart-card chart-card--detail";

      const title = document.createElement("h3");
      title.textContent = group.title;
      card.appendChild(title);

      const wrap = document.createElement("div");
      wrap.className = "chart-wrap";
      const canvas = document.createElement("canvas");
      wrap.appendChild(canvas);
      card.appendChild(wrap);
      container.appendChild(card);

      const datasets = group.seriesList.map((series, idx) => {
        const points = KanbanData.seriesPoints(series);
        let label = series._chartLabel;
        if (!label) {
          label =
            options.chartMode === "by_tb"
              ? `${KanbanData.tbDisplay(series.tb)} (${series.total_leads} лид.)`
              : `${KanbanData.rowLabel(series)} (${series.total_leads} лид.)`;
        } else {
          label = `${label} (${series.total_leads} лид.)`;
        }
        return {
        label,
        data: points.map((p) => ({ x: p.lead_index, y: p.days })),
        borderColor: palette[(groupIdx + idx) % palette.length],
        backgroundColor: palette[(groupIdx + idx) % palette.length] + "55",
        tension: options.smooth ? 0.25 : 0,
        pointRadius: points.length > 80 ? 0 : 2,
        borderWidth: 2,
        fill: false,
      };
      });

      const chart = new Chart(canvas, {
        type: "line",
        data: { datasets },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          parsing: false,
          plugins: {
            legend: {
              display: options.showLegend,
              labels: { color: "#5a6578", boxWidth: 12 },
            },
            tooltip: {
              callbacks: {
                label(ctx) {
                  return `${ctx.dataset.label}: лид ${ctx.parsed.x}, ${ctx.parsed.y} дн.`;
                },
              },
            },
          },
          scales: {
            x: {
              type: "linear",
              title: { display: true, text: "Число лидов", color: "#5a6578" },
              ticks: { color: "#5a6578" },
              grid: { color: "rgba(90, 101, 120, 0.12)" },
            },
            y: {
              title: { display: true, text: "Дней", color: "#5a6578" },
              ticks: { color: "#5a6578", stepSize: 1 },
              grid: { color: "rgba(90, 101, 120, 0.12)" },
            },
          },
        },
      });
      instances.push(chart);
    });
  }

  return { render, destroyAll };
})();
