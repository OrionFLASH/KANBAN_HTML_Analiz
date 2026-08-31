/** Отрисовка графиков Chart.js. */

const KanbanCharts = (() => {
  const instances = [];

  const palette = [
    "#38bdf8", "#22c55e", "#f97316", "#a78bfa", "#f472b6",
    "#eab308", "#2dd4bf", "#fb7185", "#60a5fa", "#84cc16",
    "#c084fc", "#fbbf24",
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
      card.className = "chart-card";

      const title = document.createElement("h3");
      title.textContent = group.title;
      card.appendChild(title);

      const wrap = document.createElement("div");
      wrap.className = "chart-wrap";
      const canvas = document.createElement("canvas");
      wrap.appendChild(canvas);
      card.appendChild(wrap);
      container.appendChild(card);

      const datasets = group.seriesList.map((series, idx) => ({
        label: options.chartMode === "by_tb"
          ? `${series.tb} (${series.total_leads} лид.)`
          : `${series.product} (${series.total_leads} лид.)`,
        data: series.points.map((p) => ({ x: p.lead_index, y: p.days })),
        borderColor: palette[(groupIdx + idx) % palette.length],
        backgroundColor: palette[(groupIdx + idx) % palette.length] + "55",
        tension: options.smooth ? 0.25 : 0,
        pointRadius: series.points.length > 80 ? 0 : 2,
        borderWidth: 2,
        fill: false,
      }));

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
              labels: { color: "#cbd5e1", boxWidth: 12 },
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
              title: { display: true, text: "Число лидов", color: "#94a3b8" },
              ticks: { color: "#94a3b8" },
              grid: { color: "rgba(148,163,184,0.15)" },
            },
            y: {
              title: { display: true, text: "Дней", color: "#94a3b8" },
              ticks: { color: "#94a3b8", stepSize: 1 },
              grid: { color: "rgba(148,163,184,0.15)" },
            },
          },
        },
      });
      instances.push(chart);
    });
  }

  return { render, destroyAll };
})();
