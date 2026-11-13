// Sözlük: arama, seviye süzgeci, sayfalama.

import * as api from "../api.js";
import { wordRow } from "../components.js";
import { add, h, pageHeader } from "../dom.js";

const PAGE_SIZE = 30;

export async function render(root) {
  const state = { q: "", level: "", page: 1 };
  const results = h("div", { "aria-live": "polite" });
  let requestId = 0;

  async function load() {
    const id = ++requestId;
    const query = new URLSearchParams({ page: String(state.page), page_size: String(PAGE_SIZE) });
    if (state.q) query.set("q", state.q);
    if (state.level) query.set("level", state.level);
    let data;
    try {
      data = await api.get(`/vocabulary?${query}`);
    } catch (error) {
      if (id === requestId) results.replaceChildren(h("p", { class: "notice error", role: "alert" }, error.message));
      return;
    }
    if (id !== requestId) return; // daha yeni bir arama sonucu bekleniyor
    const pages = Math.max(1, Math.ceil(data.total / PAGE_SIZE));
    const go = (page) => () => { state.page = page; load(); };
    results.replaceChildren(
      h("p", { class: "muted", id: "word-count" }, data.total === 0 ? "Eşleşen kelime bulunamadı." : `${data.total} kelime`),
      h("ul", { class: "list" }, data.items.map((word) => wordRow(word))),
      pages > 1
        ? h("div", { class: "row pager" },
            h("button", { class: "btn", type: "button", disabled: state.page <= 1, onclick: go(state.page - 1) }, "Önceki"),
            h("span", { class: "muted" }, `Sayfa ${state.page} / ${pages}`),
            h("button", { class: "btn", type: "button", disabled: state.page >= pages, onclick: go(state.page + 1) }, "Sonraki"))
        : null,
    );
  }

  let timer = null;
  const input = h("input", {
    id: "dict-q", type: "search", maxlength: "80", autocomplete: "off", placeholder: "İngilizce ya da Türkçe yazın",
    oninput: () => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = input.value.trim(); state.page = 1; load(); }, 200);
    },
  });
  const select = h("select", { id: "dict-level", onchange: () => { state.level = select.value; state.page = 1; load(); } },
    h("option", { value: "" }, "Tüm seviyeler"),
    ["A1", "A2", "B1", "B2", "C1", "C2"].map((level) => h("option", { value: level }, level)));

  add(root, 
    pageHeader("Sözlük", "Kelimeleri İngilizce ya da Türkçe arayabilir, tekrar etmek istediklerinizi listenize ekleyebilirsiniz."),
    h("form", { class: "row filters", role: "search", onsubmit: (event) => event.preventDefault() },
      h("div", { class: "field-inline" }, h("label", { for: "dict-q" }, "Kelime ara"), input),
      h("div", { class: "field-inline" }, h("label", { for: "dict-level" }, "Seviye"), select)),
    results,
  );
  await load();
  return "Sözlük";
}
