/** Расчёт распределения лидов по срокам (эмпирические перцентили, как в backend). */

const KanbanDistribution = (() => {
  const P_COLORS = {
    20: "#34C759",
    50: "#FF9500",
    80: "#FF3B30",
  };

  function pColor(p) {
    return P_COLORS[p] || "#5856D6";
  }

  /** Сроки серии, отсортированные по возрастанию. */
  function sortedDays(series) {
    return KanbanData.seriesPoints(series)
      .map((pt) => Number(pt.days))
      .filter((d) => Number.isFinite(d))
      .sort((a, b) => a - b);
  }

  /**
   * Эмпирический перцентиль P — нижние p% лидов на отсортированной шкале.
   * Логика совпадает с src/percentile_stats.py.
   */
  function empiricalPercentileStats(days, p) {
    const n = days.length;
    if (!n) {
      return { days: null, count: 0, min: null, max: null, le_count: 0, gt_count: 0 };
    }
    const sorted = days;
    const count = Math.max(1, Math.ceil((p / 100) * n));
    const bottom = sorted.slice(0, count);
    const threshold = bottom[bottom.length - 1];
    let le_count = 0;
    sorted.forEach((d) => {
      if (d <= threshold) le_count += 1;
    });
    return {
      days: threshold,
      count,
      min: bottom[0],
      max: threshold,
      le_count,
      gt_count: n - le_count,
    };
  }

  /** Определения корзин для общей гистограммы (несколько серий на одной оси X). */
  function buildBucketDefs(allDays, maxBars = 24) {
    if (!allDays.length) return [];

    const sorted = [...allDays].sort((a, b) => a - b);
    const uniqueCount = new Set(sorted).size;

    if (uniqueCount <= maxBars) {
      return [...new Set(sorted)].sort((a, b) => a - b).map((day) => ({
        start: day,
        end: day,
        mid: day,
        label: `${day} дн.`,
      }));
    }

    const min = sorted[0];
    const max = sorted[sorted.length - 1];
    const span = max - min + 1;
    const bucketSize = Math.max(1, Math.ceil(span / maxBars));
    const bucketCount = Math.ceil(span / bucketSize);
    const defs = [];

    for (let i = 0; i < bucketCount; i += 1) {
      const start = min + i * bucketSize;
      const end = Math.min(start + bucketSize - 1, max);
      defs.push({
        start,
        end,
        mid: (start + end) / 2,
        label: bucketSize === 1 ? `${start} дн.` : `${start}–${end} дн.`,
      });
    }
    return defs;
  }

  /** Число лидов серии в каждой корзине. */
  function countInBuckets(days, bucketDefs) {
    return bucketDefs.map(({ start, end }) => days.filter((d) => d >= start && d <= end).length);
  }

  /**
   * Гистограмма с общими корзинами для сравнения серий (grouped bar, категориальная ось X).
   */
  function buildAlignedHistogram(seriesEntries, maxBars = 24) {
    const allDays = seriesEntries.flatMap((e) => e.analysis.days);
    const bucketDefs = buildBucketDefs(allDays, maxBars);
    const labels = bucketDefs.map((b) => b.label);
    const counts = seriesEntries.map((e) => countInBuckets(e.analysis.days, bucketDefs));
    const maxCount = Math.max(1, ...counts.flat());
    return { labels, bucketDefs, counts, maxCount };
  }

  /** Индекс корзины для значения перцентиля (для вертикальной линии). */
  function bucketIndexForDay(bucketDefs, day) {
    if (day == null || !bucketDefs.length) return -1;
    const idx = bucketDefs.findIndex((b) => day >= b.start && day <= b.end);
    if (idx >= 0) return idx;
    let best = 0;
    let bestDist = Infinity;
    bucketDefs.forEach((b, i) => {
      const dist = day < b.start ? b.start - day : day > b.end ? day - b.end : 0;
      if (dist < bestDist) {
        bestDist = dist;
        best = i;
      }
    });
    return best;
  }

  /** Гистограмма: X — дни (или корзины), Y — число лидов. */
  function buildHistogram(days, maxBars = 36) {
    if (!days.length) {
      return { points: [], bucketSize: 1, maxCount: 0 };
    }

    const uniqueCount = new Set(days).size;
    if (uniqueCount <= maxBars) {
      const map = new Map();
      days.forEach((d) => map.set(d, (map.get(d) || 0) + 1));
      const labels = [...map.keys()].sort((a, b) => a - b);
      const points = labels.map((day) => ({
        x: day,
        y: map.get(day),
        label: `${day} дн.`,
      }));
      const maxCount = Math.max(...points.map((pt) => pt.y), 1);
      return { points, bucketSize: 1, maxCount };
    }

    const min = days[0];
    const max = days[days.length - 1];
    const span = max - min + 1;
    const bucketSize = Math.max(1, Math.ceil(span / maxBars));
    const buckets = new Map();

    days.forEach((d) => {
      const idx = Math.floor((d - min) / bucketSize);
      const start = min + idx * bucketSize;
      buckets.set(start, (buckets.get(start) || 0) + 1);
    });

    const starts = [...buckets.keys()].sort((a, b) => a - b);
    const points = starts.map((start) => {
      const end = start + bucketSize - 1;
      return {
        x: start + bucketSize / 2 - 0.5,
        y: buckets.get(start),
        label: bucketSize === 1 ? `${start} дн.` : `${start}–${end} дн.`,
        bucketStart: start,
        bucketEnd: end,
      };
    });
    const maxCount = Math.max(...points.map((pt) => pt.y), 1);
    return { points, bucketSize, maxCount };
  }

  /** ECDF: X — дни, Y — накопленный % лидов (≤ X). */
  function buildEcdf(days) {
    if (!days.length) return [];
    const n = days.length;
    const points = [];
    let cum = 0;
    for (let i = 0; i < n; i += 1) {
      cum += 1;
      if (i === n - 1 || days[i + 1] !== days[i]) {
        points.push({
          x: days[i],
          y: Math.round((cum / n) * 1000) / 10,
        });
      }
    }
    return points;
  }

  /** Ранговая шкала: X — номер лида, Y — срок. */
  function buildRankPoints(days) {
    return days.map((y, idx) => ({ x: idx + 1, y }));
  }

  function percentilesList() {
    const fromMeta = KanbanData.getPayload()?.meta?.percentiles;
    if (Array.isArray(fromMeta) && fromMeta.length) {
      return fromMeta.map((p) => Number(p)).filter((p) => Number.isFinite(p));
    }
    return [20, 50, 80];
  }

  /** Полный анализ одной серии для графиков. */
  function analyzeSeries(series) {
    const days = sortedDays(series);
    const percentiles = percentilesList();
    const pStats = {};
    percentiles.forEach((p) => {
      pStats[p] = empiricalPercentileStats(days, p);
    });
    return {
      days,
      n: days.length,
      min: days.length ? days[0] : null,
      max: days.length ? days[days.length - 1] : null,
      percentiles: pStats,
      histogram: buildHistogram(days),
      ecdf: buildEcdf(days),
      rank: buildRankPoints(days),
    };
  }

  function formatSeriesLabel(series, chartMode) {
    if (series._chartLabel) return String(series._chartLabel);
    if (chartMode === "by_tb") return KanbanData.tbDisplay(series.tb);
    return KanbanData.rowLabel(series);
  }

  /** Краткая строка для подписи под заголовком. */
  function summaryLine(analysis, percentiles) {
    if (!analysis.n) return "Нет лидов в выборке";
    const parts = [`${analysis.n} лид.`];
    if (analysis.min != null) parts.push(`мин ${analysis.min}`);
    if (analysis.max != null) parts.push(`макс ${analysis.max}`);
    percentiles.forEach((p) => {
      const st = analysis.percentiles[p];
      if (st?.days == null) return;
      parts.push(`П${p}=${st.days} (≤${st.le_count}, >${st.gt_count})`);
    });
    return parts.join(" · ");
  }

  return {
    pColor,
    sortedDays,
    empiricalPercentileStats,
    buildHistogram,
    buildBucketDefs,
    buildAlignedHistogram,
    bucketIndexForDay,
    buildEcdf,
    buildRankPoints,
    percentilesList,
    analyzeSeries,
    formatSeriesLabel,
    summaryLine,
  };
})();
