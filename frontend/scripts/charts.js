// Bağımlılıksız, tek serili SVG çubuk grafiği.
// Renk CSS değişkeninden gelir (açık / koyu tema). Her çubuğun üzerine gelince ya da odaklanınca
// değer ipucu gösterilir; grafiğin altında aynı verinin tablo görünümü bulunur.

import { h } from "./dom.js";

const SVG = "http://www.w3.org/2000/svg";

function svg(tag, attrs = {}) {
  const el = document.createElementNS(SVG, tag);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}

// Üstü 4px yuvarlatılmış, tabana oturan çubuk yolu.
function barPath(x, y, width, height, radius) {
  const r = Math.min(radius, width / 2, height);
  if (height <= 0) return "";
  return `M${x},${y + height} V${y + r} Q${x},${y} ${x + r},${y} H${x + width - r} ` +
    `Q${x + width},${y} ${x + width},${y + r} V${y + height} Z`;
}

/**
 * items: [{ label, value (sayı ya da null), tooltip, axisLabel? }]
 * options: { title, max, format(value), tableHeaders: [etiket, değer], emptyText }
 */
export function barChart(items, options) {
  const width = 640;
  const height = 180;
  const pad = { top: 12, right: 8, bottom: 26, left: 36 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const values = items.map((item) => item.value).filter((value) => value !== null);
  const max = options.max ?? Math.max(1, ...values);
  const format = options.format || String;
  const slot = plotW / items.length;
  const barW = Math.max(2, Math.min(28, slot - 2)); // çubuklar arasında en az 2px boşluk

  // Grafik bir grup; her çubuk klavyeyle odaklanabilen ve değerini okuyan ayrı bir görseldir.
  const root = svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "chart", role: "group", "aria-label": options.title });
  // Silik yatay çizgiler: 0, yarı, tam
  for (const fraction of [0, 0.5, 1]) {
    const y = pad.top + plotH - plotH * fraction;
    root.append(svg("line", { x1: pad.left, x2: width - pad.right, y1: y, y2: y, class: fraction === 0 ? "chart-base" : "chart-grid", "aria-hidden": "true" }));
    const tick = svg("text", { x: pad.left - 6, y: y + 4, class: "chart-tick", "text-anchor": "end", "aria-hidden": "true" });
    tick.textContent = format(max * fraction);
    root.append(tick);
  }
  const tooltip = h("div", { class: "chart-tooltip", role: "status", hidden: true });
  const show = (item, anchor) => {
    tooltip.textContent = item.tooltip;
    tooltip.hidden = false;
    const box = anchor.getBoundingClientRect();
    const host = tooltip.parentElement.getBoundingClientRect();
    tooltip.style.left = `${Math.min(Math.max(box.left - host.left + box.width / 2, 60), host.width - 60)}px`;
    tooltip.style.top = `${Math.max(box.top - host.top - 8, 0)}px`;
  };
  const hide = () => { tooltip.hidden = true; };

  items.forEach((item, index) => {
    const x = pad.left + slot * index + (slot - barW) / 2;
    const group = svg("g", { class: "chart-item", tabindex: 0, role: "img", "aria-label": item.tooltip });
    // Geniş görünmez isabet alanı (çubuktan büyük)
    group.append(svg("rect", { x: pad.left + slot * index, y: pad.top, width: slot, height: plotH, class: "chart-hit" }));
    if (item.value !== null && item.value > 0) {
      const barH = Math.max(2, (item.value / max) * plotH);
      group.append(svg("path", { d: barPath(x, pad.top + plotH - barH, barW, barH, 4), class: "chart-bar" }));
    } else if (item.value === null) {
      const dash = svg("text", { x: x + barW / 2, y: pad.top + plotH - 4, class: "chart-tick", "text-anchor": "middle" });
      dash.textContent = "—";
      group.append(dash);
    }
    if (item.axisLabel) {
      const label = svg("text", { x: x + barW / 2, y: height - 8, class: "chart-tick", "text-anchor": "middle" });
      label.textContent = item.axisLabel;
      group.append(label);
    }
    group.addEventListener("pointerenter", () => show(item, group));
    group.addEventListener("pointerleave", hide);
    group.addEventListener("focus", () => show(item, group));
    group.addEventListener("blur", hide);
    root.append(group);
  });

  const table = h("details", { class: "chart-table" },
    h("summary", {}, "Tablo olarak göster"),
    h("div", { class: "table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {}, options.tableHeaders.map((header) => h("th", { scope: "col" }, header)))),
        h("tbody", {}, items.map((item) =>
          h("tr", {}, h("td", {}, item.label), h("td", {}, item.value === null ? "—" : format(item.value))))))));

  return h("figure", { class: "chart-figure" },
    h("figcaption", { class: "chart-title" }, options.title),
    values.length ? null : h("p", { class: "muted small" }, options.emptyText || "Henüz veri yok."),
    h("div", { class: "chart-host" }, root, tooltip),
    table);
}

// Yatay ilerleme çubuğu (tamamlanan / toplam).
export function meter(completed, total, label) {
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const fill = h("div", { class: "progress-fill" });
  fill.style.width = `${percent}%`;
  return h("div", { class: "meter" },
    h("div", { class: "meter-head" }, h("span", {}, label), h("span", { class: "muted small" }, `${completed} / ${total}`)),
    h("div", { class: "progress", role: "img", "aria-label": `${label}: ${total} dersten ${completed} tanesi tamamlandı` }, fill));
}
