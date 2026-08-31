/** Загрузка JSON менеджеров, отбор TOP КМ по фильтрам и детальные карточки. */

const KanbanManagers = (() => {
  let payload = null;
  let selectedKey = null;
  /** Текущий фильтр метки для отбора TOP (инициализируется из meta.rank_selection). */
  let strategyFilter = "all";

  const STRATEGY_LABELS = {
    all: "Все метки",
    strategy: "Стратегия",
    strategy_2026: "Стратегия · 2026",
    non_strategy: "Без стратегии",
  };

  function loadJson(text) {
    payload = JSON.parse(text);
    selectedKey = null;
    strategyFilter = payload?.meta?.rank_selection?.strategy_filter || "all";
    return payload;
  }

  /** Загрузка уже разобранного объекта (блок managers из monolith JSON). */
  function loadPayload(data) {
    payload = data || null;
    selectedKey = null;
    strategyFilter = payload?.meta?.rank_selection?.strategy_filter || "all";
    return payload;
  }

  function clearPayload() {
    payload = null;
    selectedKey = null;
    strategyFilter = "all";
  }

  function getPayload() {
    return payload;
  }

  function getStrategyFilter() {
    return strategyFilter;
  }

  function setStrategyFilter(mode) {
    strategyFilter = mode || "all";
    selectedKey = null;
  }

  function managerKey(tb, km) {
    return `${String(tb)}|${String(km)}`;
  }

  function chartsData() {
    return payload?.charts || { by_tb: [], facts: [] };
  }

  function hasData() {
    return Boolean(
      payload?.records?.length || payload?.top_by_tb?.length || payload?.detail_by_product?.length
    );
  }

  function hasChartData() {
    const charts = chartsData();
    return Boolean(charts.by_tb?.length || charts.facts?.length);
  }

  function metaLine() {
    if (!payload?.meta) return "";
    const m = payload.meta;
    const strat = STRATEGY_LABELS[strategyFilter] || strategyFilter;
    const snap = m.report_date_snapshot ? ` · срез ${m.report_date_snapshot}` : "";
    return `P${m.percentile} · ${m.metric} · топ-${m.top_managers_per_tb} нарушителей на ТБ · ${strat}${snap}`;
  }

  function percentileLabel() {
    const m = payload?.meta || {};
    return String(m.percentile_label || `p${m.percentile || 80}`).toUpperCase();
  }

  function topLimit() {
    return Math.max(1, Number(payload?.meta?.top_managers_per_tb) || 3);
  }

  function resolveTbFilter(filters) {
    if (!filters?.tbs?.length) return null;
    const allLabel = KanbanData.allTbLabel();
    const picked = filters.tbs.map(String).filter((tb) => tb !== allLabel);
    if (!picked.length || KanbanData.isTbSelectionAll(filters.tbs)) return null;
    return new Set(picked);
  }

  function matchesStrategy(label, mode) {
    const text = String(label ?? "");
    if (!mode || mode === "all") return true;
    if (mode === "strategy") return /стратегия/i.test(text);
    if (mode === "strategy_2026") return /стратегия/i.test(text) && /2026/.test(text);
    if (mode === "non_strategy") return !/стратегия/i.test(text);
    return true;
  }

  function matchesRankFlags(row) {
    const cfg = payload?.meta?.rank_selection || {};
    if (cfg.efs_flag != null && row.efs_flag != null && Number(row.efs_flag) !== Number(cfg.efs_flag)) {
      return false;
    }
    if (
      cfg.change_conditions != null &&
      row.change_conditions != null &&
      Number(row.change_conditions) !== Number(cfg.change_conditions)
    ) {
      return false;
    }
    return true;
  }

  function stuckLimit() {
    return Math.max(1, Number(payload?.meta?.top_stuck_items_per_hotspot) || 15);
  }

  function rankByTeam() {
    return Boolean(payload?.meta?.rank_by_team);
  }

  function normalizePersonName(value) {
    const text = String(value ?? "")
      .trim()
      .replace(/\s+/g, " ");
    if (!text || text === "-" || text === "—" || text.toLowerCase() === "nan") return "";
    return text;
  }

  function rolesForPersonOnLead(row, personName) {
    const target = normalizePersonName(personName).toLowerCase();
    if (!target) return [];
    const team = Array.isArray(row.team) ? row.team : [];
    const hit = team.find((m) => normalizePersonName(m?.name).toLowerCase() === target);
    if (hit?.roles?.length) return hit.roles.map(String);
    if (normalizePersonName(row.km).toLowerCase() === target) return ["КМ"];
    return [];
  }

  function teamMembersOfRow(row) {
    const team = Array.isArray(row.team) ? row.team : [];
    const names = [];
    const seen = new Set();
    team.forEach((member) => {
      const name = normalizePersonName(member?.name);
      if (!name) return;
      const key = name.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      names.push({ name, roles: (member.roles || []).map(String) });
    });
    if (!names.length) {
      const km = normalizePersonName(row.km);
      if (km) names.push({ name: km, roles: ["КМ"] });
    }
    return names;
  }

  /** Сокращение юрформ по meta.client_display (или встроенный список). */
  function clientAbbreviations() {
    const cfg = payload?.meta?.client_display;
    if (cfg && cfg.enabled === false) return [];
    const list = cfg?.abbreviations;
    if (Array.isArray(list) && list.length) {
      return [...list]
        .filter((x) => x && x.match && x.replace != null)
        .sort((a, b) => String(b.match).length - String(a.match).length);
    }
    return [
      { match: "публичное акционерное общество", replace: "ПАО" },
      { match: "непубличное акционерное общество", replace: "НАО" },
      { match: "закрытое акционерное общество", replace: "ЗАО" },
      { match: "открытое акционерное общество", replace: "ОАО" },
      { match: "общество с ограниченной ответственностью", replace: "ООО" },
      { match: "акционерное общество", replace: "АО" },
      { match: "индивидуальный предприниматель", replace: "ИП" },
      { match: "федеральное государственное бюджетное учреждение", replace: "ФГБУ" },
      { match: "федеральное государственное унитарное предприятие", replace: "ФГУП" },
      { match: "государственное унитарное предприятие", replace: "ГУП" },
      { match: "муниципальное унитарное предприятие", replace: "МУП" },
      { match: "автономная некоммерческая организация", replace: "АНО" },
      { match: "некоммерческая организация", replace: "НКО" },
      { match: "товарищество собственников жилья", replace: "ТСЖ" },
      { match: "товарищество собственников недвижимости", replace: "ТСН" },
      { match: "крестьянское (фермерское) хозяйство", replace: "КФХ" },
      { match: "крестьянское фермерское хозяйство", replace: "КФХ" },
      { match: "производственный кооператив", replace: "ПК" },
      { match: "сельскохозяйственный производственный кооператив", replace: "СПК" },
      { match: "полное товарищество", replace: "ПТ" },
      { match: "товарищество на вере", replace: "ТНВ" },
      { match: "коммандитное товарищество", replace: "КТ" },
    ];
  }

  function abbreviateClientName(name) {
    if (name == null) return null;
    let text = String(name).trim();
    if (!text) return null;
    const pairs = clientAbbreviations();
    const shorts = [];
    pairs.forEach((item) => {
      const full = String(item.match).trim();
      const short = String(item.replace).trim();
      if (!full || !short) return;
      shorts.push(short);
      const escaped = full.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const wrapped = new RegExp(`[«\"'(]\\s*${escaped}\\.?\\s*[»\"')]`, "gi");
      text = text.replace(wrapped, `${short} `);
      const bare = new RegExp(`${escaped}\\.?`, "gi");
      text = text.replace(bare, `${short} `);
    });
    text = text.replace(/\s{2,}/g, " ").replace(/^[,;\s]+|[,;\s]+$/g, "");
    if (shorts.length) {
      const alt = shorts
        .sort((a, b) => b.length - a.length)
        .map((s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("|");
      text = text.replace(new RegExp(`(${alt})(?=[A-Za-zА-Яа-яЁё0-9«\"'(])`, "g"), "$1 ");
      text = text.replace(/\s{2,}/g, " ").replace(/^[,;\s]+|[,;\s]+$/g, "");
    }
    return text || null;
  }

  function buildStuckItem(row, personName) {
    const days = Number(row.days_int) || 0;
    const thresh = Number(row.threshold_days) || 0;
    const team = (Array.isArray(row.team) ? row.team : [])
      .map((m) => ({
        name: normalizePersonName(m?.name),
        roles: (m?.roles || []).map(String),
      }))
      .filter((m) => m.name);
    return {
      lead_id: String(row.lead_id ?? ""),
      deal_id: row.deal_id != null && row.deal_id !== "" ? String(row.deal_id) : null,
      inn: row.inn != null && row.inn !== "" ? String(row.inn) : null,
      client: abbreviateClientName(
        row.client != null && String(row.client).trim() !== "" ? String(row.client).trim() : null
      ),
      stage_key: String(row.stage_key ?? ""),
      days_int: Math.round(days * 10) / 10,
      threshold_days: Math.round(thresh * 10) / 10,
      overshoot: Math.round(Math.max(0, days - thresh) * 10) / 10,
      member_roles: rolesForPersonOnLead(row, personName),
      team,
    };
  }

  /** Пул групп/продуктов из config.rank_selection + сужение UI-фильтрами. */
  function effectiveScope(filters) {
    const cfg = payload?.meta?.rank_selection || {};
    const poolGroups = (cfg.product_groups || []).filter(Boolean);
    const poolProducts = (cfg.products || []).filter(Boolean);

    let groups = null;
    if (filters?.productGroups?.length) {
      groups = new Set(filters.productGroups.map(String));
      if (poolGroups.length) {
        const pool = new Set(poolGroups.map(String));
        groups = new Set([...groups].filter((g) => pool.has(g)));
      }
    } else if (poolGroups.length) {
      groups = new Set(poolGroups.map(String));
    }

    let products = null;
    if (filters?.products?.length) {
      products = new Set(filters.products.map(String));
      if (poolProducts.length) {
        const pool = new Set(poolProducts.map(String));
        products = new Set([...products].filter((p) => pool.has(p)));
      }
    } else if (poolProducts.length) {
      products = new Set(poolProducts.map(String));
    }

    return { groups, products };
  }

  function filterLeadRecords(filters) {
    const rows = payload?.records || [];
    if (!rows.length) return [];

    const tbSet = resolveTbFilter(filters);
    const { groups, products } = effectiveScope(filters);

    return rows.filter((row) => {
      if (tbSet && !tbSet.has(String(row.tb))) return false;
      if (groups && !groups.has(String(row.product_group))) return false;
      if (products && !products.has(String(row.product))) return false;
      if (filters?.stage && String(row.stage_key) !== filters.stage) return false;
      if (!matchesStrategy(row.label, strategyFilter)) return false;
      if (!matchesRankFlags(row)) return false;
      return true;
    });
  }

  function aggregateHotspots(exceededRows, limit, personName) {
    const map = new Map();
    exceededRows.forEach((row) => {
      const person = personName || String(row.km);
      const key = [
        String(row.tb),
        String(person),
        String(row.product_group),
        String(row.product ?? "—"),
        String(row.stage_key),
      ].join("|");
      if (!map.has(key)) {
        map.set(key, {
          tb: String(row.tb),
          km: String(person),
          product_group: String(row.product_group),
          product: row.product != null ? String(row.product) : "—",
          stage_key: String(row.stage_key),
          exceedance_count: 0,
          threshold_days: Number(row.threshold_days) || 0,
          max_days: Number(row.days_int) || 0,
          max_overshoot: 0,
          avg_overshoot: 0,
          _days: [],
          _stuck: [],
        });
      }
      const spot = map.get(key);
      spot.exceedance_count += 1;
      const days = Number(row.days_int) || 0;
      spot._days.push(days);
      if (days > spot.max_days) spot.max_days = days;
      const thresh = Number(row.threshold_days) || 0;
      if (thresh > spot.threshold_days) spot.threshold_days = thresh;
      if (spot._stuck.length < stuckLimit()) {
        spot._stuck.push(buildStuckItem(row, person));
      }
    });

    const stuckCap = stuckLimit();
    const hotspots = [...map.values()].map((spot) => {
      const overs = Math.max(0, spot.max_days - spot.threshold_days);
      const avgDays = spot._days.length
        ? spot._days.reduce((a, b) => a + b, 0) / spot._days.length
        : 0;
      const stuckSorted = spot._stuck
        .slice()
        .sort(
          (a, b) =>
            (b.overshoot || 0) - (a.overshoot || 0) ||
            String(a.lead_id).localeCompare(String(b.lead_id), "ru")
        )
        .slice(0, stuckCap);
      return {
        tb: spot.tb,
        km: spot.km,
        product_group: spot.product_group,
        product: spot.product,
        stage_key: spot.stage_key,
        exceedance_count: spot.exceedance_count,
        threshold_days: Math.round(spot.threshold_days * 10) / 10,
        max_days: Math.round(spot.max_days * 10) / 10,
        max_overshoot: Math.round(overs * 10) / 10,
        avg_overshoot: Math.round(Math.max(0, avgDays - spot.threshold_days) * 10) / 10,
        stuck_items: stuckSorted,
      };
    });

    hotspots.sort(
      (a, b) =>
        b.exceedance_count - a.exceedance_count ||
        b.max_overshoot - a.max_overshoot ||
        String(a.stage_key).localeCompare(String(b.stage_key), "ru")
    );
    return hotspots.slice(0, limit);
  }

  function collectRolesFromHotspots(hotspots) {
    const roles = [];
    const seen = new Set();
    (hotspots || []).forEach((spot) => {
      (spot.stuck_items || []).forEach((item) => {
        (item.member_roles || []).forEach((role) => {
          const key = String(role).toLowerCase();
          if (!key || seen.has(key)) return;
          seen.add(key);
          roles.push(String(role));
        });
      });
    });
    return roles;
  }

  function recomputeTop(filters) {
    const records = filterLeadRecords(filters);
    if (records.length) {
      const topN = topLimit();
      const hotLimit = Number(payload?.meta?.top_hotspots_per_manager) || 5;
      const byManager = new Map();
      const useTeam = rankByTeam();

      records.forEach((row) => {
        const members = useTeam
          ? teamMembersOfRow(row)
          : [{ name: normalizePersonName(row.km), roles: ["КМ"] }].filter((m) => m.name);
        members.forEach((member) => {
          const key = managerKey(row.tb, member.name);
          if (!byManager.has(key)) {
            byManager.set(key, {
              tb: String(row.tb),
              km: member.name,
              exceedance_count: 0,
              total_leads: new Set(),
              exceeded_rows: [],
            });
          }
          const bucket = byManager.get(key);
          bucket.total_leads.add(String(row.lead_id));
          if (row.exceeded) {
            bucket.exceedance_count += 1;
            bucket.exceeded_rows.push(row);
          }
        });
      });

      const tbOrder = [...new Set(records.map((r) => String(r.tb)))].sort((a, b) =>
        a.localeCompare(b, "ru")
      );
      const result = [];

      tbOrder.forEach((tb) => {
        const bucketRows = [...byManager.values()]
          .filter((b) => b.tb === tb && b.exceedance_count > 0)
          .sort(
            (a, b) =>
              b.exceedance_count - a.exceedance_count ||
              b.total_leads.size - a.total_leads.size ||
              String(a.km).localeCompare(String(b.km), "ru")
          )
          .slice(0, topN);

        bucketRows.forEach((row, idx) => {
          const hotspots = aggregateHotspots(row.exceeded_rows, hotLimit, row.km);
          const memberRoles = collectRolesFromHotspots(hotspots);
          result.push({
            tb: row.tb,
            km: row.km,
            km_tb_key: managerKey(row.tb, row.km),
            rank: idx + 1,
            exceedance_count: row.exceedance_count,
            total_leads: row.total_leads.size,
            hotspots,
            member_roles: memberRoles,
            roles_summary: memberRoles.length ? memberRoles.join(", ") : "—",
          });
        });
      });

      return result;
    }

    return filterTopLegacy(filters);
  }

  function filterTopLegacy(filters) {
    const rows = payload?.top_by_tb || [];
    const tbSet = resolveTbFilter(filters);
    if (!tbSet) return rows;
    return rows.filter((row) => tbSet.has(String(row.tb)));
  }

  function filterFacts(filters) {
    let rows = chartsData().facts || [];
    const tbSet = resolveTbFilter(filters);
    if (tbSet) rows = rows.filter((row) => tbSet.has(String(row.tb)));
    const { groups, products } = effectiveScope(filters);
    if (groups) rows = rows.filter((row) => groups.has(String(row.product_group)));
    if (products) rows = rows.filter((row) => products.has(String(row.product)));
    if (filters?.stage) rows = rows.filter((row) => String(row.stage_key) === filters.stage);
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
      .sort(
        (a, b) =>
          b.km_with_violations - a.km_with_violations || b.violation_deals - a.violation_deals
      );
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
        .sort(
          (a, b) =>
            b.km_with_violations - a.km_with_violations || b.violation_deals - a.violation_deals
        );

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

  function groupTopByTb(rows) {
    const map = new Map();
    const order = [];
    (rows || []).forEach((row) => {
      const tb = String(row.tb);
      if (!map.has(tb)) {
        map.set(tb, []);
        order.push(tb);
      }
      map.get(tb).push(row);
    });
    return order.map((tb) => ({ tb, managers: map.get(tb) }));
  }

  function renderTeamChips(team) {
    if (!team?.length) return "";
    return (
      `<div class="manager-team">` +
      team
        .map((member) => {
          const roles = (member.roles || []).join(", ");
          return (
            `<span class="manager-team__chip" title="${escapeHtml(roles)}">` +
            `<b>${escapeHtml(member.name)}</b>` +
            (roles ? `<small>${escapeHtml(roles)}</small>` : "") +
            `</span>`
          );
        })
        .join("") +
      `</div>`
    );
  }

  function renderStuckItems(items) {
    if (!items?.length) {
      return `<p class="manager-stuck-empty">Нет зависших лидов/сделок в этой зоне.</p>`;
    }
    const showTeam = rankByTeam() || items.some((item) => item.team?.length || item.member_roles?.length);
    const head =
      `<thead><tr>` +
      `<th>Клиент</th><th>ИНН</th><th>ID ПрПр</th><th>ID сделки</th><th>Дней</th><th>+P80</th>` +
      (showTeam ? `<th>Роль</th><th>Команда</th>` : "") +
      `</tr></thead>`;
    const body = items
      .map((item) => {
        const roles = (item.member_roles || []).join(", ") || "—";
        return (
          `<tr>` +
          `<td class="manager-stuck-client" title="${escapeHtml(abbreviateClientName(item.client) || item.client || "")}">${escapeHtml(abbreviateClientName(item.client) || item.client || "—")}</td>` +
          `<td>${escapeHtml(item.inn || "—")}</td>` +
          `<td>${escapeHtml(item.lead_id || "—")}</td>` +
          `<td>${escapeHtml(item.deal_id || "—")}</td>` +
          `<td>${escapeHtml(item.days_int ?? "—")}</td>` +
          `<td class="manager-stuck-overshoot">+${escapeHtml(item.overshoot ?? "—")}</td>` +
          (showTeam
            ? `<td class="manager-stuck-roles">${escapeHtml(roles)}</td>` +
              `<td class="manager-stuck-team">${renderTeamChips(item.team)}</td>`
            : "") +
          `</tr>`
        );
      })
      .join("");
    return `<div class="manager-stuck-table-wrap"><table class="manager-stuck-table">${head}<tbody>${body}</tbody></table></div>`;
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
      `<div class="manager-hotspot__stuck">` +
      `<div class="manager-hotspot__stuck-title">Зависшие лиды / сделки</div>` +
      renderStuckItems(spot.stuck_items) +
      `</div>` +
      `</li>`
    );
  }

  function collectStuckItems(row) {
    const items = [];
    (row.hotspots || []).forEach((spot) => {
      (spot.stuck_items || []).forEach((item) => {
        items.push({
          ...item,
          product_group: spot.product_group,
          product: spot.product,
          stage_key: spot.stage_key || item.stage_key,
        });
      });
    });
    items.sort((a, b) => (Number(b.overshoot) || 0) - (Number(a.overshoot) || 0));
    return items;
  }

  function renderInfographics(row) {
    const hotspots = row.hotspots || [];
    const stuck = collectStuckItems(row);
    const maxHot = hotspots.reduce((m, s) => Math.max(m, Number(s.exceedance_count) || 0), 0) || 1;
    const maxOver = stuck.reduce((m, s) => Math.max(m, Number(s.overshoot) || 0), 0) || 1;
    const totalStuck = stuck.length;
    const avgOver =
      totalStuck > 0
        ? Math.round((stuck.reduce((s, x) => s + (Number(x.overshoot) || 0), 0) / totalStuck) * 10) / 10
        : 0;

    const hotspotBars = hotspots.length
      ? hotspots
          .map((spot) => {
            const count = Number(spot.exceedance_count) || 0;
            const pct = Math.round((count / maxHot) * 100);
            const severity = hotspotSeverity(spot);
            return (
              `<div class="mgr-infobar mgr-infobar--${severity}">` +
              `<div class="mgr-infobar__label">` +
              `<span>${escapeHtml(segmentLabel(spot))}</span>` +
              `<span class="mgr-infobar__meta">${escapeHtml(spot.stage_key)} · ${count} сд. · +${spot.max_overshoot ?? 0}</span>` +
              `</div>` +
              `<div class="mgr-infobar__track"><span class="mgr-infobar__fill" style="width:${pct}%"></span></div>` +
              `</div>`
            );
          })
          .join("")
      : `<p class="manager-detail__empty">Нет зон для диаграммы.</p>`;

    const topStuck = stuck.slice(0, 12);
    const stuckBars = topStuck.length
      ? topStuck
          .map((item) => {
            const over = Number(item.overshoot) || 0;
            const pct = Math.round((over / maxOver) * 100);
            const name = abbreviateClientName(item.client) || item.inn || item.lead_id || "—";
            return (
              `<div class="mgr-infobar mgr-infobar--stuck">` +
              `<div class="mgr-infobar__label">` +
              `<span title="${escapeHtml(name)}">${escapeHtml(name)}</span>` +
              `<span class="mgr-infobar__meta">${escapeHtml(item.stage_key || "")} · ${item.days_int ?? "—"} дн. · +${over}</span>` +
              `</div>` +
              `<div class="mgr-infobar__track"><span class="mgr-infobar__fill" style="width:${pct}%"></span></div>` +
              `</div>`
            );
          })
          .join("")
      : `<p class="manager-detail__empty">Нет зависших сделок в топ-зонах.</p>`;

    // Простая «полоса нагрузки»: доля превышений от лидов
    const loadPct = row.total_leads
      ? Math.min(100, Math.round((Number(row.exceedance_count) / Number(row.total_leads)) * 100))
      : 0;

    return (
      `<section class="mgr-info">` +
      `<div class="mgr-info__kpis">` +
      `<div class="mgr-kpi"><b>${row.exceedance_count}</b><span>превышений</span></div>` +
      `<div class="mgr-kpi"><b>${hotspots.length}</b><span>зон</span></div>` +
      `<div class="mgr-kpi"><b>${totalStuck}</b><span>зависших в топе</span></div>` +
      `<div class="mgr-kpi"><b>+${avgOver}</b><span>ср. +P80</span></div>` +
      `</div>` +
      `<div class="mgr-info__load">` +
      `<div class="mgr-info__load-head"><span>Доля превышений в портфеле</span><b>${loadPct}%</b></div>` +
      `<div class="mgr-infobar__track mgr-infobar__track--tall"><span class="mgr-infobar__fill mgr-infobar__fill--load" style="width:${loadPct}%"></span></div>` +
      `</div>` +
      `<div class="mgr-info__grid">` +
      `<div class="mgr-info__card">` +
      `<h5 class="mgr-info__title">Зоны превышения (число сделок)</h5>` +
      `<div class="mgr-info__bars">${hotspotBars}</div>` +
      `</div>` +
      `<div class="mgr-info__card">` +
      `<h5 class="mgr-info__title">Топ зависших по +P80</h5>` +
      `<div class="mgr-info__bars">${stuckBars}</div>` +
      `</div>` +
      `</div>` +
      `</section>`
    );
  }

  function renderDetailCard(row) {
    const hotspots = row.hotspots || [];
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
      `<article class="manager-detail manager-detail--fullscreen" id="managerDetailCard">` +
      `<div class="manager-detail__hero">` +
      `<div class="manager-detail__rank">${row.rank}</div>` +
      `<div class="manager-detail__identity">` +
      `<h4 class="manager-detail__name" id="managerOverlayTitle">${escapeHtml(row.km)}</h4>` +
      `<p class="manager-detail__tb">${escapeHtml(row.tb)}</p>` +
      (row.roles_summary && row.roles_summary !== "—"
        ? `<p class="manager-detail__roles">${escapeHtml(row.roles_summary)}</p>`
        : "") +
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
      (rankByTeam()
        ? "Участник команды зависших лидов: роли, команда сделки и превышения P80."
        : "Детализация нарушителя P80: клиенты, лиды и сделки с превышением срока.") +
      `</p>` +
      renderInfographics(row) +
      `<div class="manager-detail__legend">` +
      `<span class="manager-detail__legend-item manager-detail__legend-item--critical">сильное</span>` +
      `<span class="manager-detail__legend-item manager-detail__legend-item--warning">среднее</span>` +
      `<span class="manager-detail__legend-item manager-detail__legend-item--mild">умеренное</span>` +
      `</div>` +
      `<h5 class="mgr-info__title mgr-info__title--section">Зоны и зависшие сделки</h5>` +
      hotspotsHtml +
      `</article>`
    );
  }

  function getOverlayEls() {
    return {
      overlay: document.getElementById("managerDetailOverlay"),
      body: document.getElementById("managerOverlayBody"),
      closeBtn: document.getElementById("managerOverlayClose"),
    };
  }

  function closeDetailOverlay() {
    const { overlay, body } = getOverlayEls();
    if (!overlay) return;
    overlay.hidden = true;
    document.body.classList.remove("has-manager-overlay");
    if (body) body.innerHTML = "";
  }

  function openDetailOverlay(row) {
    const { overlay, body, closeBtn } = getOverlayEls();
    if (!overlay || !body) return;
    body.innerHTML = renderDetailCard(row);
    overlay.hidden = false;
    document.body.classList.add("has-manager-overlay");
    closeBtn?.focus();
  }

  function bindOverlayOnce() {
    const { overlay, closeBtn } = getOverlayEls();
    if (!overlay || overlay.dataset.bound === "1") return;
    overlay.dataset.bound = "1";
    closeBtn?.addEventListener("click", closeDetailOverlay);
    overlay.addEventListener("click", (event) => {
      if (event.target?.dataset?.overlayClose === "1") closeDetailOverlay();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && overlay && !overlay.hidden) closeDetailOverlay();
    });
  }

  function rankSelectionHint() {
    const cfg = payload?.meta?.rank_selection || {};
    const parts = [];
    if (cfg.product_groups?.length) parts.push(`группы: ${cfg.product_groups.length}`);
    if (cfg.products?.length) parts.push(`продукты: ${cfg.products.length}`);
    if (cfg.efs_flag != null) parts.push(`ЕФС=${cfg.efs_flag}`);
    if (cfg.change_conditions != null) parts.push(`изм.усл.=${cfg.change_conditions}`);
    if (parts.length) return `Пул config: ${parts.join(", ")}. Ключ КМ: ТБ+ФИО.`;
    return "Пул config: все группы и продукты. Ключ КМ: ТБ+ФИО.";
  }

  function renderStrategyControl(container, filters, onChange) {
    const wrap = document.createElement("div");
    wrap.className = "managers-rank-controls";
    wrap.innerHTML =
      `<label class="field field--inline">` +
      `<span class="field-label">Метка (отбор TOP)</span>` +
      `<select class="field-control" id="managerStrategyFilter"></select>` +
      `</label>` +
      `<p class="managers-rank-controls__hint">${escapeHtml(rankSelectionHint())} Группы/продукты — в панели фильтров справа.</p>`;

    const select = wrap.querySelector("#managerStrategyFilter");
    Object.entries(STRATEGY_LABELS).forEach(([value, label]) => {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = label;
      select.appendChild(opt);
    });
    select.value = strategyFilter;
    select.addEventListener("change", () => {
      setStrategyFilter(select.value);
      onChange();
    });
    container.appendChild(wrap);
  }

  function render(container, filters) {
    if (!container) return;
    bindOverlayOnce();
    container.innerHTML = "";

    if (!hasData()) {
      container.innerHTML =
        `<div class="managers-empty">` +
        `<p class="managers-empty__title">Нет данных по менеджерам</p>` +
        `<p>Загрузите monolith JSON с блоком <code>managers</code> или выполните <code>run.py</code> с колонкой КМ.</p>` +
        `</div>`;
      return;
    }

    const head = document.createElement("div");
    head.className = "managers-panel__head";
    head.innerHTML =
      `<h3 class="managers-panel__title">Топ нарушителей P80 по ТБ</h3>` +
      `<p class="managers-panel__intro">${metaLine()} · нажмите на КМ — полная карточка с инфографикой</p>`;
    container.appendChild(head);

    renderStrategyControl(container, filters, () => render(container, filters));

    const top = recomputeTop(filters);
    if (!top.length) {
      const empty = document.createElement("p");
      empty.className = "managers-panel__empty";
      empty.textContent = "Нет нарушителей P80 для выбранных фильтров отбора.";
      container.appendChild(empty);
      return;
    }

    const grouped = groupTopByTb(top);
    const tbSet = resolveTbFilter(filters);
    const sectionsWrap = document.createElement("div");
    sectionsWrap.className = "managers-tb-sections";

    grouped.forEach(({ tb, managers }) => {
      if (tbSet && !tbSet.has(String(tb))) return;
      const section = document.createElement("section");
      section.className = "managers-tb-section";
      section.innerHTML =
        `<header class="managers-tb-section__head">` +
        `<h4 class="managers-tb-section__title">${escapeHtml(KanbanData.tbDisplay ? KanbanData.tbDisplay(tb) : tb)}</h4>` +
        `<span class="managers-tb-section__badge">${managers.length} из ${topLimit()}</span>` +
        `</header>`;

      const cards = document.createElement("div");
      cards.className = "managers-top-grid managers-top-grid--tb managers-top-grid--screen";
      managers.forEach((row) => {
        const key = managerKey(row.tb, row.km);
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "manager-card" + (key === selectedKey ? " manager-card--active" : "");
        btn.dataset.managerKey = key;
        btn.innerHTML =
          `<div class="manager-card__rank">${row.rank}</div>` +
          `<div class="manager-card__body">` +
          `<div class="manager-card__name">${escapeHtml(row.km)}</div>` +
          (row.roles_summary && row.roles_summary !== "—"
            ? `<div class="manager-card__roles">${escapeHtml(row.roles_summary)}</div>`
            : "") +
          `<div class="manager-card__stat"><span>${row.exceedance_count}</span> превыш. · ${row.total_leads} лид.</div>` +
          (row.hotspots?.length
            ? `<div class="manager-card__hint">${escapeHtml(segmentLabel(row.hotspots[0]))} · ${escapeHtml(row.hotspots[0].stage_key)}</div>` +
              `<div class="manager-card__cta">Открыть карточку →</div>`
            : `<div class="manager-card__cta">Открыть карточку →</div>`) +
          `</div>`;
        btn.addEventListener("click", () => {
          selectedKey = key;
          openDetailOverlay(row);
          render(container, filters);
        });
        cards.appendChild(btn);
      });
      section.appendChild(cards);
      sectionsWrap.appendChild(section);
    });

    container.appendChild(sectionsWrap);
  }

  return {
    loadJson,
    loadPayload,
    clearPayload,
    getPayload,
    getStrategyFilter,
    setStrategyFilter,
    hasData,
    hasChartData,
    metaLine,
    buildChartGroups,
    render,
    closeDetailOverlay,
  };
})();
