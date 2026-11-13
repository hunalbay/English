// Birden çok sayfada kullanılan bileşenler.

import * as api from "./api.js";
import { POS_TR, h, levelBadge, toast } from "./dom.js";

// Kelimeyi kişisel listeye ekleyen / listeden çıkaran düğme.
export function wordListButton(word, { onChange } = {}) {
  const button = h("button", { class: "btn small", type: "button" });
  const paint = () => {
    button.textContent = word.in_word_list ? "Listemden çıkar" : "Listeme ekle";
    button.setAttribute("aria-pressed", String(Boolean(word.in_word_list)));
    button.setAttribute("aria-label", `${word.lemma}: ${button.textContent}`);
  };
  paint();
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    button.disabled = true;
    try {
      const path = `/word-list/${encodeURIComponent(word.id)}`;
      const result = word.in_word_list ? await api.del(path) : await api.put(path);
      word.in_word_list = result.in_word_list;
      paint();
      toast(word.in_word_list ? "Kelime listenize eklendi." : "Kelime listenizden çıkarıldı.");
      if (onChange) onChange(word);
    } catch (error) {
      toast(error.message, { error: true });
    } finally {
      button.disabled = false;
    }
  });
  return button;
}

export function wordRow(word, options) {
  return h(
    "li",
    { class: "list-item" },
    h("a", { class: "list-main", href: `#/kelime/${encodeURIComponent(word.id)}` },
      h("span", { class: "list-title", lang: "en" }, word.lemma),
      h("span", { class: "list-sub" },
        word.pos.map((pos) => POS_TR[pos] || pos).join(", "), " · ", word.meaning_tr)),
    h("span", { class: "list-meta" }, levelBadge(word.level), wordListButton(word, options)),
  );
}

export function wordChip(word) {
  return h("a", { class: "chip", href: `#/kelime/${encodeURIComponent(word.id)}` },
    h("span", { lang: "en" }, word.lemma), h("span", { class: "muted" }, ` — ${word.meaning_tr}`));
}
