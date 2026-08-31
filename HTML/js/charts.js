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

  function renderBars(container, chartGroups, options) {
    destroyAll();
    container.innerHTML = "";

    if (!chartGroups.length) {
      container.innerHTML =
        `<div class="empty-state"><p>Нет данных по КМ для графика. Загрузите JSON менеджеров.</p></div>`;
      return;
    }

    chartGroups.forEach((group, groupIdx) => {
      const card = document.createElement("article");
      card.className = "chart-card chart-card--bar";

      const title = document.createElement("h3");
      title.textContent = group.title;
      card.appendChild(title);

      if (group.subtitle) {
        const intro = document.createElement("p");
        intro.className = "chart-card__intro";
        intro.textContent = group.subtitle;
        card.appendChild(intro);
      }

      const wrap = document.createElement("div");
      wrap.className = "chart-wrap chart-wrap--bar";
      const canvas = document.createElement("canvas");
      wrap.appendChild(canvas);
      card.appendChild(wrap);
      container.appendChild(card);

      const color = palette[groupIdx % palette.length];
    const horizontal = group.labels.length > 12;
      const chart = new Chart(canvas, {
        type: "bar",
        data: {
          labels: group.labels,
          datasets: [
            {
              label: "КМ с нарушениями",
              data: group.values,
              backgroundColor: color + "cc",
              borderColor: color,
              borderWidth: 1,
              borderRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          indexAxis: horizontal ? "y" : "x",
          plugins: {
            legend: {
              display: options.showLegend,
              labels: { color: "#5a6578", boxWidth: 12 },
            },
            tooltip: {
              callbacks: {
                label(ctx) {
                  const value = horizontal ? ctx.parsed.x : ctx.parsed.y;
                  const deals = group.deals?.[ctx.dataIndex];
                  const kmTotal = group.kmTotal?.[ctx.dataIndex];
                  const parts = [`КМ с нарушениями: ${value}`];
                  if (deals != null) parts.push(`сделок с превышением: ${deals}`);
                  if (kmTotal != null) parts.push(`всего КМ в ТБ: ${kmTotal}`);
                  return parts;
                },
              },
            },
          },
          scales: {
            x: {
              beginAtZero: horizontal,
              ticks: {
                color: "#5a6578",
                maxRotation: 45,
                autoSkip: true,
                stepSize: horizontal ? 1 : undefined,
                precision: horizontal ? 0 : undefined,
              },
              grid: { color: "rgba(90, 101, 120, 0.12)" },
              title: horizontal
                ? { display: true, text: "Число КМ", color: "#5a6578" }
                : undefined,
            },
            y: {
              beginAtZero: !horizontal,
              ticks: {
                color: "#5a6578",
                stepSize: horizontal ? undefined : 1,
                precision: horizontal ? undefined : 0,
              },
              grid: { color: "rgba(90, 101, 120, 0.12)" },
              title: horizontal
                ? undefined
                : { display: true, text: "Число КМ", color: "#5a6578" },
            },
          },
        },
      });
      instances.push(chart);
    });
  }

  return { render, renderBars, destroyAll };
})();
