/** Разворот графиков по клику: один panel или вся карточка (group). */

const KanbanChartExpand = (() => {
  const layer = document.getElementById("chartExpandLayer");
  const frame = document.getElementById("chartExpandFrame");
  const titleEl = document.getElementById("chartExpandTitle");
  const bodyEl = document.getElementById("chartExpandBody");
  const closeBtn = document.getElementById("chartExpandClose");
  const backdrop = layer?.querySelector("[data-expand-close]");

  /** @type {{ mode: 'panel'|'group'|null, node: HTMLElement|null, placeholder: Comment|null, cardTitle: string }} */
  let state = { mode: null, node: null, placeholder: null, cardTitle: "" };

  let boundRoot = null;

  function isExpanded() {
    return Boolean(state.mode);
  }

  function resizeChartsIn(root) {
    if (typeof Chart === "undefined" || !root) return;
    root.querySelectorAll("canvas").forEach((canvas) => {
      const chart = Chart.getChart(canvas);
      if (chart) chart.resize();
    });
  }

  function mainRect() {
    const main = document.querySelector(".main");
    if (!main) return { top: 56, left: 0, right: window.innerWidth, bottom: window.innerHeight - 8 };
    return main.getBoundingClientRect();
  }

  function positionPanelFrame() {
    if (!frame) return;
    const r = mainRect();
    frame.style.top = `${Math.max(0, r.top)}px`;
    frame.style.left = `${Math.max(0, r.left)}px`;
    frame.style.width = `${Math.max(320, r.width)}px`;
    frame.style.height = `${Math.max(240, r.height - 4)}px`;
  }

  function positionGroupFrame() {
    if (!frame) return;
    frame.style.top = "0";
    frame.style.left = "0";
    frame.style.width = "100%";
    frame.style.height = "100%";
  }

  function openLayer(mode, heading) {
    if (!layer || !bodyEl) return;
    layer.hidden = false;
    layer.setAttribute("aria-hidden", "false");
    layer.dataset.mode = mode;
    if (titleEl) titleEl.textContent = heading || "";
    document.body.classList.add("is-chart-expanded");
    document.body.classList.toggle("is-chart-expanded--group", mode === "group");
    document.body.classList.toggle("is-chart-expanded--panel", mode === "panel");
    if (mode === "group") positionGroupFrame();
    else positionPanelFrame();
  }

  function closeLayer() {
    if (!layer) return;
    layer.hidden = true;
    layer.setAttribute("aria-hidden", "true");
    delete layer.dataset.mode;
    document.body.classList.remove("is-chart-expanded", "is-chart-expanded--group", "is-chart-expanded--panel");
  }

  function collapse() {
    if (!state.mode || !state.node || !state.placeholder) {
      state = { mode: null, node: null, placeholder: null, cardTitle: "" };
      closeLayer();
      if (bodyEl) bodyEl.innerHTML = "";
      return;
    }

    const parent = state.placeholder.parentNode;
    if (parent) {
      parent.insertBefore(state.node, state.placeholder);
      state.placeholder.remove();
    }

    state.node.classList.remove("is-chart-expanded-node");
    state = { mode: null, node: null, placeholder: null, cardTitle: "" };
    closeLayer();
    if (bodyEl) bodyEl.innerHTML = "";

    if (boundRoot) resizeChartsIn(boundRoot);
  }

  function expandPanel(panelEl, card) {
    if (isExpanded()) collapse();

    const panelTitle = panelEl.querySelector(".dist-panel__title")?.textContent?.trim() || "";
    const cardTitle = card.querySelector("h3")?.textContent?.trim() || "";
    const heading = panelTitle ? `${cardTitle} — ${panelTitle}` : cardTitle;

    const placeholder = document.createComment("chart-expand");
    panelEl.parentNode.insertBefore(placeholder, panelEl);

    panelEl.classList.add("is-chart-expanded-node");
    bodyEl.appendChild(panelEl);

    state = { mode: "panel", node: panelEl, placeholder, cardTitle };
    openLayer("panel", heading);

    requestAnimationFrame(() => {
      positionPanelFrame();
      resizeChartsIn(panelEl);
    });
  }

  function expandGroup(card) {
    if (isExpanded()) collapse();

    const heading = card.querySelector("h3")?.textContent?.trim() || "Графики";
    const placeholder = document.createComment("chart-expand");
    card.parentNode.insertBefore(placeholder, card);

    card.classList.add("is-chart-expanded-node");
    bodyEl.appendChild(card);

    state = { mode: "group", node: card, placeholder, cardTitle: heading };
    openLayer("group", heading);

    requestAnimationFrame(() => {
      positionGroupFrame();
      resizeChartsIn(card);
    });
  }

  function onGridClick(event) {
    if (!boundRoot) return;
    if (event.target.closest("#chartExpandClose, [data-expand-close]")) {
      event.preventDefault();
      collapse();
      return;
    }
    if (isExpanded()) return;

    const card = event.target.closest(".chart-card");
    if (!card || !boundRoot.contains(card)) return;

    const panel = event.target.closest(".dist-panel");
    const barWrap = event.target.closest(".chart-card--bar .chart-wrap");

    if (panel && card.contains(panel)) {
      event.stopPropagation();
      expandPanel(panel, card);
      return;
    }

    if (barWrap && card.contains(barWrap)) {
      event.stopPropagation();
      expandPanel(barWrap, card);
      return;
    }

    if (card.contains(event.target)) {
      event.stopPropagation();
      expandGroup(card);
    }
  }

  function onKeyDown(event) {
    if (event.key === "Escape" && isExpanded()) {
      event.preventDefault();
      collapse();
    }
  }

  function onResize() {
    if (!isExpanded()) return;
    if (state.mode === "panel") positionPanelFrame();
    else positionGroupFrame();
    if (state.node) resizeChartsIn(state.node);
  }

  function bind(root) {
    if (!layer || !frame || !bodyEl) return;
    boundRoot = root;

    root.querySelectorAll(".chart-card").forEach((card) => {
      card.dataset.expandHint = "group";
    });
    root.querySelectorAll(".dist-panel, .chart-card--bar .chart-wrap").forEach((el) => {
      el.dataset.expandHint = "panel";
    });
  }

  function collapseIfExpanded() {
    if (isExpanded()) collapse();
  }

  if (closeBtn) closeBtn.addEventListener("click", collapse);
  if (backdrop) backdrop.addEventListener("click", collapse);
  document.addEventListener("keydown", onKeyDown);
  window.addEventListener("resize", onResize);
  ["btn-settings-hide", "btn-settings-show", "btn-filters-hide", "btn-filters-show"].forEach((id) => {
    document.getElementById(id)?.addEventListener("click", () => {
      window.setTimeout(onResize, 320);
    });
  });

  return {
    bind,
    collapse,
    collapseIfExpanded,
    isExpanded,
    onGridClick,
  };
})();
