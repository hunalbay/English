// Kelime sayfası: anlamlar, biçimler, örnekler, ilişkili kelimeler ve dersler.

import * as api from "../api.js";
import { wordChip, wordListButton } from "../components.js";
import { POS_TR, add, h, lessonLink, levelBadge, toast } from "../dom.js";

function chipSection(title, words) {
  if (!words.length) return null;
  return h("section", { class: "card" }, h("h2", {}, title), h("div", { class: "chips" }, words.map(wordChip)));
}

const STATUS_TR = { new: "Henüz çalışılmadı", learning: "Öğreniliyor", learned: "İyi öğrenildi", long_term: "Uzun süredir biliniyor" };
const ACTIVITY_TR = {
  flashcard: "Kart", mc_en_tr: "Anlamı seç", mc_tr_en: "Kelimeyi seç", typing: "Kelimeyi yaz",
  cloze: "Boşluk doldurma", antonym: "Zıt anlam", matching: "Eşleştirme",
};
const GRADE_TR = ["Bilemedim", "Zor", "Bildim", "Kolay"];

function directionStatus(label, review) {
  const detail = review.status === "new" ? ""
    : review.is_due ? " · tekrar zamanı geldi"
    : ` · sonraki tekrar: ${new Date(review.due_at).toLocaleDateString("tr-TR")}`;
  return h("li", {}, h("strong", {}, `${label}: `), STATUS_TR[review.status], detail,
    review.lapses ? ` · ${review.lapses} kez unutuldu` : "");
}

function progressSection(word, progress) {
  const section = h("section", { class: "card", id: "word-progress" });
  const paint = (data) => {
    const studied = data.history.length > 0 || Object.values(data.directions).some((d) => d.status !== "new");
    section.replaceChildren(
      h("h2", {}, "Öğrenme durumunuz"),
      h("ul", {}, directionStatus("İngilizce → Türkçe", data.directions.en_tr), directionStatus("Türkçe → İngilizce", data.directions.tr_en)),
      data.history.length
        ? h("details", {}, h("summary", {}, `Cevap geçmişi (son ${data.history.length})`),
            h("ul", { class: "history" }, data.history.map((item) =>
              h("li", {}, new Date(item.reviewed_at).toLocaleString("tr-TR"), " · ", ACTIVITY_TR[item.activity] || item.activity, " · ",
                h("span", { class: `mark ${item.correct ? "good" : "bad"}` },
                  item.grade === null ? (item.correct ? "Doğru" : "Yanlış") : GRADE_TR[item.grade])))))
        : null,
      studied && Object.values(data.directions).some((d) => d.status !== "new")
        ? h("button", { class: "btn small", type: "button", onclick: async () => {
            if (!window.confirm(`"${word.lemma}" için tekrar planı sıfırlansın mı? Cevap geçmişiniz silinmez.`)) return;
            try {
              await api.del(`/study/words/${encodeURIComponent(word.id)}`);
              paint(await api.get(`/study/words/${encodeURIComponent(word.id)}`));
              toast("Tekrar planı sıfırlandı.");
            } catch (error) {
              toast(error.message, { error: true });
            }
          } }, "Tekrar planını sıfırla")
        : null);
  };
  paint(progress);
  return section;
}

export async function render(root, params) {
  const [word, progress] = await Promise.all([
    api.get(`/vocabulary/${encodeURIComponent(params.id)}`),
    api.get(`/study/words/${encodeURIComponent(params.id)}`),
  ]);

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
    progressSection(word, progress),
    h("p", { class: "muted small" },
      `Kaynak: ${word.source_name}. `,
      word.review_status === "human_reviewed"
        ? "Bu kayıt bir uzman tarafından gözden geçirilmiştir."
        : "Bu kayıt otomatik denetimlerden geçmiştir; henüz bir uzman tarafından gözden geçirilmemiştir."),
  );
  return word.lemma;
}
