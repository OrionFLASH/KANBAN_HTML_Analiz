/** Отрисовка графиков Chart.js: распределение лидов + bar КМ. */

const KanbanCharts = (() => {
  const instances = [];

  const palette = [
    "#007AFF", "#34C759", "#FF9500", "#5856D6", "#FF3B30",
    "#5AC8FA", "#AF52DE", "#FF2D55", "#64D2FF", "#30D158",
    "#0b6bcb", "#0f8a6a", "#c27a00",
  ];

  function destroyAll() {
    if (typeof KanbanChartExpand !== "undefined") KanbanChartExpand.collapseIfExpanded();
    instances.forEach((chart) => chart.destroy());
    instances.length = 0;
  }

  function axisStyle() {
    return {
      ticks: { color: "#5a6578" },
      grid: { color: "rgba(90, 101, 120, 0.12)" },
      title: { color: "#5a6578" },
    };
  }

  function percentileMarkerDatasets(percentiles, pStats, axisMax, orientation) {
    /** Вспомогательные линии перцентилей (вертикальные или горизонтальные). */
    const datasets = [];
    percentiles.forEach((p) => {
      const st = pStats[p];
      if (st?.days == null) return;
      const color = KanbanDistribution.pColor(p);
      const label = `П${p} = ${st.days} дн.`;
      if (orientation === "vertical") {
        datasets.push({
          type: "line",
          label,
          data: [
            { x: st.days, y: 0 },
            { x: st.days, y: axisMax },
          ],
          borderColor: color,
          borderWidth: 2,
          borderDash: p === 80 ? [] : [5, 4],
          pointRadius: 0,
          fill: false,
          order: 0,
          parsing: false,
        });
      } else if (orientation === "horizontal") {
        datasets.push({
          type: "line",
          label: `${p}% лидов`,
          data: [
            { x: 0, y: p },
            { x: st.days, y: p },
          ],
          borderColor: color + "99",
          borderWidth: 1,
          borderDash: [3, 3],
          pointRadius: 0,
          fill: false,
          order: 0,
          parsing: false,
        });
        datasets.push({
          type: "line",
          label,
          data: [
            { x: st.days, y: 0 },
            { x: st.days, y: p },
          ],
          borderColor: color,
          borderWidth: 2,
          borderDash: p === 80 ? [] : [5, 4],
          pointRadius: 0,
          fill: false,
          order: 0,
          parsing: false,
        });
      } else if (orientation === "rank-h") {
        datasets.push({
          type: "line",
          label,
          data: [
            { x: 1, y: st.days },
            { x: axisMax, y: st.days },
          ],
          borderColor: color,
          borderWidth: 1.5,
          borderDash: p === 80 ? [6, 3] : [4, 4],
          pointRadius: 0,
          fill: false,
          order: 0,
          parsing: false,
        });
      }
    });
    return datasets;
  }

  function createCanvas(wrap, className) {
    wrap.className = className;
    const canvas = document.createElement("canvas");
    wrap.appendChild(canvas);
    return canvas;
  }

  /** Вертикальные линии перцентилей на категориальной гистограмме (одна серия). */
  const histogramPercentilePlugin = {
    id: "histogramPercentileLines",
    afterDraw(chart) {
      const opts = chart.options.plugins?.histogramPercentileLines;
      if (!opts?.bucketDefs?.length) return;

      const { ctx, chartArea, scales } = chart;
      const xScale = scales.x;
      const { percentiles, pStats, bucketDefs } = opts;

      percentiles.forEach((p) => {
        const day = pStats[p]?.days;
        if (day == null) return;
        const idx = KanbanDistribution.bucketIndexForDay(bucketDefs, day);
        if (idx < 0) return;

        const x = xScale.getPixelForValue(idx);
        const color = KanbanDistribution.pColor(p);

        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = p === 80 ? 2 : 1.5;
        ctx.setLineDash(p === 80 ? [] : [5, 4]);
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.stroke();

        ctx.fillStyle = color;
        ctx.font = "600 10px system-ui, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(`П${p}=${day}`, x, chartArea.top + 12);
        ctx.restore();
      });
    },
  };

  function renderHistogram(canvas, seriesEntries, percentiles, showLegend) {
    const aligned = KanbanDistribution.buildAlignedHistogram(seriesEntries);

    if (!aligned.labels.length) {
      const wrap = canvas.parentElement;
      if (wrap) {
        wrap.innerHTML = `<p class="dist-panel__empty">Нет данных для гистограммы</p>`;
      }
      return;
    }

    const barDatasets = seriesEntries.map((entry, idx) => ({
      label: `${entry.label} (${entry.analysis.n} лид.)`,
      data: aligned.counts[idx],
      backgroundColor: palette[idx % palette.length] + "bb",
      borderColor: palette[idx % palette.length],
      borderWidth: 1,
      borderRadius: 3,
      maxBarThickness: seriesEntries.length > 1 ? 18 : 28,
    }));

    const chart = new Chart(canvas, {
      type: "bar",
      data: { labels: aligned.labels, datasets: barDatasets },
      plugins: [histogramPercentilePlugin],
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: showLegend,
            labels: { color: "#5a6578", boxWidth: 12 },
          },
          histogramPercentileLines:
            seriesEntries.length === 1
              ? {
                  percentiles,
                  pStats: seriesEntries[0].analysis.percentiles,
                  bucketDefs: aligned.bucketDefs,
                }
              : undefined,
          tooltip: {
            callbacks: {
              title(items) {
                return aligned.labels[items[0]?.dataIndex] || "";
              },
              label(ctx) {
                const n = ctx.parsed.y;
                if (!n) return null;
                return `${ctx.dataset.label}: ${n} лид.`;
              },
            },
            filter(item) {
              return (item.parsed?.y || 0) > 0;
            },
          },
        },
        scales: {
          x: {
            ...axisStyle(),
            title: { display: true, text: "Срок (дни)", color: "#5a6578" },
            ticks: {
              ...axisStyle().ticks,
              maxRotation: 45,
              minRotation: 0,
              autoSkip: true,
              maxTicksLimit: 16,
            },
          },
          y: {
            beginAtZero: true,
            suggestedMax: aligned.maxCount * 1.12,
            ...axisStyle(),
            title: { display: true, text: "Число лидов", color: "#5a6578" },
            ticks: { ...axisStyle().ticks, stepSize: 1, precision: 0 },
          },
        },
      },
    });
    instances.push(chart);
  }

  function renderEcdf(canvas, seriesEntries, percentiles, showLegend) {
    const lineDatasets = seriesEntries.map((entry, idx) => ({
      type: "line",
      label: `${entry.label} (${entry.analysis.n} лид.)`,
      data: entry.analysis.ecdf.map((pt) => ({ x: pt.x, y: pt.y })),
      borderColor: palette[idx % palette.length],
      backgroundColor: palette[idx % palette.length] + "33",
      borderWidth: 2,
      pointRadius: entry.analysis.ecdf.length > 40 ? 0 : 2,
      fill: false,
      stepped: "after",
      order: 2,
    }));

    const xMax = Math.max(
      ...seriesEntries.flatMap((e) => e.analysis.ecdf.map((pt) => pt.x)),
      1
    );

    const markerSets =
      seriesEntries.length === 1
        ? percentileMarkerDatasets(percentiles, seriesEntries[0].analysis.percentiles, 100, "horizontal")
        : percentiles.map((p) => ({
            type: "line",
            label: `${p}% лидов`,
            data: [
              { x: 0, y: p },
              { x: xMax * 1.05, y: p },
            ],
            borderColor: KanbanDistribution.pColor(p) + "66",
            borderWidth: 1,
            borderDash: [4, 4],
            pointRadius: 0,
            fill: false,
            order: 0,
            parsing: false,
          }));

    const chart = new Chart(canvas, {
      type: "line",
      data: { datasets: [...markerSets, ...lineDatasets] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        parsing: false,
        plugins: {
          legend: { display: showLegend, labels: { color: "#5a6578", boxWidth: 12 } },
          tooltip: {
            callbacks: {
              label(ctx) {
                if (ctx.dataset.label?.includes("% лидов") && !ctx.dataset.label.includes("=")) {
                  return ctx.dataset.label;
                }
                return `${ctx.dataset.label}: ≤ ${ctx.parsed.x} дн. → ${ctx.parsed.y}% лидов`;
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            min: 0,
            max: xMax * 1.05,
            ...axisStyle(),
            title: { display: true, text: "Срок (дни)", color: "#5a6578" },
          },
          y: {
            min: 0,
            max: 100,
            ...axisStyle(),
            title: { display: true, text: "Накоплено лидов, %", color: "#5a6578" },
            ticks: { ...axisStyle().ticks, callback: (v) => `${v}%` },
          },
        },
      },
    });
    instances.push(chart);
  }

  function renderRank(canvas, seriesEntries, percentiles, showLegend) {
    const nMax = Math.max(...seriesEntries.map((e) => e.analysis.n), 1);
    const yMax = Math.max(...seriesEntries.flatMap((e) => e.analysis.rank.map((pt) => pt.y)), 1);

    const lineDatasets = seriesEntries.map((entry, idx) => ({
      type: "line",
      label: `${entry.label} (${entry.analysis.n} лид.)`,
      data: entry.analysis.rank,
      borderColor: palette[idx % palette.length],
      backgroundColor: palette[idx % palette.length] + "44",
      borderWidth: 2,
      pointRadius: entry.analysis.n > 80 ? 0 : 2,
      fill: false,
      stepped: "after",
      order: 2,
    }));

    const markerSets =
      seriesEntries.length === 1
        ? percentileMarkerDatasets(percentiles, seriesEntries[0].analysis.percentiles, nMax, "rank-h")
        : [];

    const chart = new Chart(canvas, {
      type: "line",
      data: { datasets: [...markerSets, ...lineDatasets] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: showLegend, labels: { color: "#5a6578", boxWidth: 12 } },
          tooltip: {
            callbacks: {
              label(ctx) {
                if (ctx.dataset.order === 0) return ctx.dataset.label || "";
                const seriesIdx = ctx.datasetIndex - markerSets.length;
                const entry = seriesEntries[seriesIdx];
                const n = entry?.analysis?.n || nMax;
                const pct = n ? Math.round((ctx.parsed.x / n) * 100) : 0;
                return `${ctx.dataset.label}: лид №${ctx.parsed.x} (${pct}%) — ${ctx.parsed.y} дн.`;
              },
            },
          },
        },
        scales: {
          x: {
            type: "linear",
            min: 1,
            max: Math.max(nMax, 2),
            ...axisStyle(),
            title: { display: true, text: "Номер лида (от меньшего срока к большему)", color: "#5a6578" },
          },
          y: {
            beginAtZero: true,
            max: yMax * 1.08,
            ...axisStyle(),
            title: { display: true, text: "Срок (дни)", color: "#5a6578" },
            ticks: { ...axisStyle().ticks, stepSize: 1 },
          },
        },
      },
    });
    instances.push(chart);
  }

  function renderPercentileChips(container, seriesEntries, percentiles) {
    container.innerHTML = "";
    seriesEntries.forEach((entry, idx) => {
      const row = document.createElement("div");
      row.className = "dist-stats-row";
      const name = document.createElement("span");
      name.className = "dist-stats-row__name";
      name.style.borderLeftColor = palette[idx % palette.length];
      name.textContent = entry.label;
      row.appendChild(name);

      const chips = document.createElement("div");
      chips.className = "dist-stats-row__chips";
      if (!entry.analysis.n) {
        chips.textContent = "нет данных";
      } else {
        const meta = document.createElement("span");
        meta.className = "dist-chip dist-chip--meta";
        meta.textContent = `${entry.analysis.n} лид. · мин ${entry.analysis.min} · макс ${entry.analysis.max}`;
        chips.appendChild(meta);
        percentiles.forEach((p) => {
          const st = entry.analysis.percentiles[p];
          if (st?.days == null) return;
          const chip = document.createElement("span");
          chip.className = "dist-chip";
          chip.style.borderColor = KanbanDistribution.pColor(p);
          chip.style.color = KanbanDistribution.pColor(p);
          chip.title = `Нижние ${p}% лидов по счёту: срок ≤ ${st.days} дн. (${st.le_count} лид.), выше порога: ${st.gt_count}`;
          chip.textContent = `П${p}=${st.days} (≤${st.le_count} · >${st.gt_count})`;
          chips.appendChild(chip);
        });
      }
      row.appendChild(chips);
      container.appendChild(row);
    });
  }

  function renderDistribution(container, chartGroups, options) {
    destroyAll();
    container.innerHTML = "";

    if (!chartGroups.length) {
      container.innerHTML = `<div class="empty-state"><p>Нет данных для графика с текущими фильтрами.</p></div>`;
      return;
    }

    const percentiles = KanbanDistribution.percentilesList();
    const showLegend = Boolean(options.showLegend);

    chartGroups.forEach((group) => {
      const card = document.createElement("article");
      card.className =
        group.tier === "summary" ? "chart-card chart-card--summary chart-card--dist" : "chart-card chart-card--detail chart-card--dist";

      const title = document.createElement("h3");
      title.textContent = group.title;
      card.appendChild(title);

      const seriesEntries = group.seriesList.map((series) => ({
        series,
        label: KanbanDistribution.formatSeriesLabel(series, options.chartMode),
        analysis: KanbanDistribution.analyzeSeries(series),
      }));

      const stats = document.createElement("div");
      stats.className = "dist-stats";
      renderPercentileChips(stats, seriesEntries, percentiles);
      card.appendChild(stats);

      if (seriesEntries.length === 1) {
        const hint = document.createElement("p");
        hint.className = "chart-card__intro";
        hint.textContent = KanbanDistribution.summaryLine(seriesEntries[0].analysis, percentiles);
        card.appendChild(hint);
      }

      const stack = document.createElement("div");
      stack.className = "dist-stack";

      const row = document.createElement("div");
      row.className = "dist-row";

      const histBlock = document.createElement("div");
      histBlock.className = "dist-panel";
      const histTitle = document.createElement("div");
      histTitle.className = "dist-panel__title";
      histTitle.textContent = "Где толпа: число лидов на каждом сроке";
      histBlock.appendChild(histTitle);
      const histWrap = document.createElement("div");
      createCanvas(histWrap, "chart-wrap chart-wrap--dist");
      histBlock.appendChild(histWrap);
      row.appendChild(histBlock);

      const ecdfBlock = document.createElement("div");
      ecdfBlock.className = "dist-panel";
      const ecdfTitle = document.createElement("div");
      ecdfTitle.className = "dist-panel__title";
      ecdfTitle.textContent = "Накопление: какой % лидов уложился в срок";
      ecdfBlock.appendChild(ecdfTitle);
      const ecdfWrap = document.createElement("div");
      createCanvas(ecdfWrap, "chart-wrap chart-wrap--dist");
      ecdfBlock.appendChild(ecdfWrap);
      row.appendChild(ecdfBlock);

      stack.appendChild(row);

      const rankBlock = document.createElement("div");
      rankBlock.className = "dist-panel dist-panel--wide";
      const rankTitle = document.createElement("div");
      rankTitle.className = "dist-panel__title";
      rankTitle.textContent =
        seriesEntries.length > 1
          ? "Ранговая шкала (сравнение серий): лид №1 — самый быстрый"
          : "Ранговая шкала: лид №1 — самый быстрый, линии П20 / П50 / П80 — границы нижних долей";
      rankBlock.appendChild(rankTitle);
      const rankWrap = document.createElement("div");
      const rankCanvas = createCanvas(rankWrap, "chart-wrap chart-wrap--rank");
      rankBlock.appendChild(rankWrap);
      stack.appendChild(rankBlock);

      card.appendChild(stack);
      container.appendChild(card);

      renderHistogram(histWrap.querySelector("canvas"), seriesEntries, percentiles, showLegend);
      renderEcdf(ecdfWrap.querySelector("canvas"), seriesEntries, percentiles, showLegend);
      renderRank(rankCanvas, seriesEntries, percentiles, showLegend);
    });

    if (typeof KanbanChartExpand !== "undefined") KanbanChartExpand.bind(container);
  }

  function renderBars(container, chartGroups, options) {
    destroyAll();
    container.innerHTML = "";

    if (!chartGroups.length) {
      container.innerHTML =
        `<div class="empty-state"><p>Нет данных по КМ для графика. Нужен блок <code>managers</code> в основном JSON.</p></div>`;
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

    if (typeof KanbanChartExpand !== "undefined") KanbanChartExpand.bind(container);
  }

  return { render: renderDistribution, renderDistribution, renderBars, destroyAll };
})();
