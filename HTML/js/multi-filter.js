/** Компактный мультивыбор с поиском, бейджем и сворачиванием. */

const KanbanMultiFilter = (() => {
  class Widget {
    /**
     * @param {object} opts
     * @param {HTMLElement} opts.listEl
     * @param {HTMLElement} opts.badgeEl
     * @param {HTMLElement|null} opts.searchEl
     * @param {HTMLElement|null} opts.panelEl
     * @param {HTMLElement|null} opts.toggleEl
     * @param {HTMLButtonElement|null} opts.allBtn
     * @param {HTMLButtonElement|null} opts.noneBtn
     * @param {() => void} opts.onChange
     * @param {(event: Event, widget: Widget) => void|null} opts.onItemChange
     * @param {boolean} opts.startCollapsed
     */
    constructor(opts) {
      this.listEl = opts.listEl;
      this.badgeEl = opts.badgeEl;
      this.searchEl = opts.searchEl || null;
      this.panelEl = opts.panelEl || null;
      this.toggleEl = opts.toggleEl || null;
      this.allBtn = opts.allBtn || null;
      this.noneBtn = opts.noneBtn || null;
      this.onChange = opts.onChange || (() => {});
      this.onItemChange = opts.onItemChange || null;
      this.emptyLabel = "Все";
      this.allItems = [];

      if (this.searchEl) {
        this.searchEl.addEventListener("input", () => this.renderList());
      }

      if (this.toggleEl && this.panelEl) {
        this.collapsed = Boolean(opts.startCollapsed);
        this.toggleEl.addEventListener("click", () => this.toggleCollapse());
        this.applyCollapseState();
      }

      this.listEl.addEventListener("change", (event) => {
        if (this.onItemChange) this.onItemChange(event, this);
        this.updateBadge();
        this.onChange();
      });

      this.allBtn?.addEventListener("click", () => {
        this.selectAll();
        this.onChange();
      });
      this.noneBtn?.addEventListener("click", () => {
        this.selectNone();
        this.onChange();
      });
    }

    toggleCollapse() {
      this.collapsed = !this.collapsed;
      this.applyCollapseState();
    }

    applyCollapseState() {
      if (!this.panelEl || !this.toggleEl) return;
      this.panelEl.classList.toggle("is-collapsed", this.collapsed);
      this.toggleEl.setAttribute("aria-expanded", String(!this.collapsed));
    }

    setItems(items, selectedValues) {
      this.allItems = items.map(({ value, label }) => ({
        value: String(value),
        label: String(label),
      }));
      const selected = new Set((selectedValues || []).map(String));
      if (this.searchEl) this.searchEl.value = "";
      this.renderList(selected);
      this.updateBadge();
    }

    getSelected() {
      return Array.from(this.listEl.querySelectorAll('input[type="checkbox"]:checked')).map((cb) => cb.value);
    }

    getSelectedSet() {
      return new Set(this.getSelected());
    }

    selectAll() {
      this.listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        cb.checked = true;
      });
      this.updateBadge();
    }

    selectNone() {
      this.listEl.querySelectorAll('input[type="checkbox"]').forEach((cb) => {
        cb.checked = false;
      });
      this.updateBadge();
    }

    updateBadge() {
      if (!this.badgeEl) return;
      const selected = this.getSelected();
      const total = this.allItems.length;
      if (!selected.length) {
        this.badgeEl.textContent = this.emptyLabel;
        this.badgeEl.dataset.state = "all";
      } else if (selected.length === total) {
        this.badgeEl.textContent = `Все (${total})`;
        this.badgeEl.dataset.state = "all-picked";
      } else {
        this.badgeEl.textContent = `${selected.length} / ${total}`;
        this.badgeEl.dataset.state = "partial";
      }
    }

    renderList(preselected) {
      const selected = preselected || this.getSelectedSet();
      const query = (this.searchEl?.value || "").trim().toLowerCase();
      const visible = this.allItems.filter(
        (item) => !query || item.label.toLowerCase().includes(query) || item.value.toLowerCase().includes(query)
      );

      this.listEl.innerHTML = "";
      if (!visible.length) {
        const empty = document.createElement("div");
        empty.className = "multi-filter__empty";
        empty.textContent = query ? "Ничего не найдено" : "Нет значений";
        this.listEl.appendChild(empty);
        return;
      }

      visible.forEach(({ value, label }) => {
        const row = document.createElement("label");
        row.className = "multi-filter__item";
        row.title = label;

        const cb = document.createElement("input");
        cb.type = "checkbox";
        cb.value = value;
        cb.checked = selected.has(value);

        const text = document.createElement("span");
        text.className = "multi-filter__item-label";
        text.textContent = label;

        row.appendChild(cb);
        row.appendChild(text);
        this.listEl.appendChild(row);
      });

      if (!(preselected instanceof Set)) {
        this.updateBadge();
      }
    }
  }

  return { Widget };
})();
