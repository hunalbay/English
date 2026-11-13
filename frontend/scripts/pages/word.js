// Kelime sayfası: anlamlar, biçimler, örnekler, ilişkili kelimeler ve dersler.

import * as api from "../api.js";
import { wordChip, wordListButton } from "../components.js";
import { POS_TR, add, h, lessonLink, levelBadge } from "../dom.js";

function chipSection(title, words) {
  if (!words.length) return null;
  return h("section", { class: "card" }, h("h2", {}, title), h("div", { class: "chips" }, words.map(wordChip)));
}

export async function render(root, params) {
  const word = await api.get(`/vocabulary/${encodeURIComponent(params.id)}`);

  add(root, 
    h("nav", { class: "breadcrumb", "aria-label": "Konum" }, h("a", { href: "#/sozluk" }, "Sözlük"), " › ", word.lemma),
    h("div", { class: "page-header" },
      h("div", { class: "row" }, h("h1", { lang: "en" }, word.lemma), levelBadge(word.level)),
      word.ipa ? h("p", { class: "muted", lang: "en" }, `/${word.ipa}/`) : null,
      wordListButton(word)),
    h("section", { class: "card" },
      h("h2", {}, "Anlamlar"),
      h("ol", { class: "meanings" },
        word.meanings.map((meaning) =>
          h("li", {},
            h("span", { class: "pos" }, POS_TR[meaning.pos] || meaning.pos), " ", h("strong", {}, meaning.meaning_tr),
            meaning.definition_en ? h("p", { class: "muted", lang: "en" }, meaning.definition_en) : null))),
      word.forms.length
        ? h("p", {}, h("span", { class: "muted" }, "Çekimli biçimler: "), h("span", { lang: "en" }, word.forms.join(", ")))
        : null,
      word.notes_tr ? h("p", { class: "notice" }, word.notes_tr) : null),
    word.examples.length
      ? h("section", { class: "card" }, h("h2", {}, "Örnek cümleler"),
          h("ul", { class: "examples" },
            word.examples.map((item) =>
              h("li", { class: "example" }, h("p", { class: "ex-en", lang: "en" }, item.en), h("p", { class: "ex-tr" }, item.tr)))))
      : null,
    word.collocations.length
      ? h("section", { class: "card" }, h("h2", {}, "Sık kullanılan birliktelikler"),
          h("ul", {}, word.collocations.map((item) =>
            h("li", {}, h("span", { lang: "en" }, item.phrase), item.meaning_tr ? ` — ${item.meaning_tr}` : null))))
      : null,
    chipSection("Eş anlamlılar", word.synonyms),
    chipSection("Zıt anlamlılar", word.antonyms),
    chipSection("İlgili kelimeler", word.related_words),
    word.lessons.length
      ? h("section", { class: "card" }, h("h2", {}, "Bu kelimenin geçtiği dersler"),
          h("div", { class: "list" }, word.lessons.map(lessonLink)))
      : null,
    h("p", { class: "muted small" },
      `Kaynak: ${word.source_name}. `,
      word.review_status === "human_reviewed"
        ? "Bu kayıt bir uzman tarafından gözden geçirilmiştir."
        : "Bu kayıt otomatik denetimlerden geçmiştir; henüz bir uzman tarafından gözden geçirilmemiştir."),
  );
  return word.lemma;
}
