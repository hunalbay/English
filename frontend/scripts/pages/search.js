// Genel arama: dersler ve kelimeler.

import * as api from "../api.js";
import { wordRow } from "../components.js";
import { add, h, lessonLink, pageHeader } from "../dom.js";

export async function render(root, params) {
  const query = params.query.trim().slice(0, 80);
  const data = await api.get(`/search?q=${encodeURIComponent(query)}`);
  const input = document.getElementById("search-input");
  if (input && document.activeElement !== input) input.value = query;

  add(root, pageHeader(`"${query}" için arama sonuçları`));
  if (!data.lessons.length && !data.words.length) {
    add(root, h("p", { class: "notice" }, "Eşleşen ders ya da kelime bulunamadı."));
    return "Arama";
  }
  if (data.lessons.length) {
    add(root, h("section", { class: "card" }, h("h2", {}, `Dersler (${data.lessons.length})`),
      h("div", { class: "list" }, data.lessons.map(lessonLink))));
  }
  if (data.words.length) {
    add(root, h("section", { class: "card" }, h("h2", {}, `Kelimeler (${data.words.length})`),
      h("ul", { class: "list" }, data.words.map((word) => wordRow(word)))));
  }
  return "Arama";
}
