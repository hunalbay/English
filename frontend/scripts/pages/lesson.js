// Ders sayfası: bölümler, örnekler, bağlantılı dersler ve kelimeler, tamamlama durumu.

import * as api from "../api.js";
import { wordChip } from "../components.js";
import { LESSON_KIND_TR, add, h, lessonLink, levelBadge, richText, toast } from "../dom.js";

function example(item) {
  if (item.is_incorrect) {
    return h("li", { class: "example wrong" },
      h("p", { class: "ex-en", lang: "en" }, h("span", { class: "mark bad" }, "Yanlış: "), h("s", {}, item.en)),
      h("p", { class: "ex-en", lang: "en" }, h("span", { class: "mark good" }, "Doğru: "), item.correction_en),
      h("p", { class: "ex-tr" }, item.tr),
      item.note_tr ? h("p", { class: "ex-note" }, item.note_tr) : null);
  }
  return h("li", { class: "example" },
    h("p", { class: "ex-en", lang: "en" }, item.en),
    h("p", { class: "ex-tr" }, item.tr),
    item.note_tr ? h("p", { class: "ex-note" }, item.note_tr) : null);
}

function table(data) {
  return h("div", { class: "table-wrap" },
    h("table", {},
      h("thead", {}, h("tr", {}, data.headers.map((cell) => h("th", { scope: "col" }, cell)))),
      h("tbody", {}, data.rows.map((row) => h("tr", {}, row.map((cell) => h("td", {}, cell)))))));
}

function linked(title, lessons) {
  if (!lessons.length) return null;
  return h("section", { class: "card" }, h("h2", {}, title), h("div", { class: "list" }, lessons.map(lessonLink)));
}

export async function render(root, params) {
  const lesson = await api.get(`/lessons/${encodeURIComponent(params.id)}`);
  // Dersin açıldığını kaydet ("kaldığın yerden devam et" için). Başarısız olursa ders yine okunabilir.
  api.post(`/lessons/${encodeURIComponent(lesson.id)}/open`).catch(() => {});

  const completeButton = h("button", { class: "btn primary", type: "button" });
  const statusText = h("p", { class: "muted", id: "lesson-status", "aria-live": "polite" });
  const paint = () => {
    const done = lesson.status === "completed";
    completeButton.textContent = done ? "Tamamlandı işaretini kaldır" : "Dersi tamamladım";
    completeButton.classList.toggle("primary", !done);
    statusText.textContent = done ? "Bu dersi tamamladınız." : "";
  };
  paint();
  completeButton.addEventListener("click", async () => {
    completeButton.disabled = true;
    try {
      const result = await api.put(`/lessons/${encodeURIComponent(lesson.id)}/completion`, {
        completed: lesson.status !== "completed",
      });
      lesson.status = result.status;
      paint();
      toast(lesson.status === "completed" ? "Ders tamamlandı olarak işaretlendi." : "Tamamlandı işareti kaldırıldı.");
    } catch (error) {
      toast(error.message, { error: true });
    } finally {
      completeButton.disabled = false;
    }
  });

  add(root, 
    h("nav", { class: "breadcrumb", "aria-label": "Konum" },
      h("a", { href: `#/dersler/${lesson.level}` }, `Dersler ${lesson.level}`), " › ", lesson.unit_title_tr),
    h("div", { class: "page-header" },
      h("p", { class: "row" }, levelBadge(lesson.level), h("span", { class: "muted" }, LESSON_KIND_TR[lesson.kind] || lesson.kind)),
      h("h1", {}, lesson.title_tr),
      h("p", { class: "muted", lang: "en" }, lesson.title_en),
      h("p", {}, h("strong", {}, "Hedef: "), lesson.objective_tr)),
    lesson.prerequisite_lessons.length
      ? h("section", { class: "notice" }, h("strong", {}, "Önce şunları bilmelisiniz: "),
          lesson.prerequisite_lessons.flatMap((item, index) => [
            index ? ", " : "", h("a", { href: `#/ders/${encodeURIComponent(item.id)}` }, item.title_tr)]))
      : null,
    lesson.sections.map((section) =>
      h("section", { class: `card section-${section.kind}` },
        h("h2", {}, section.title_tr),
        richText(section.text_tr),
        section.table ? table(section.table) : null,
        section.examples.length ? h("ul", { class: "examples" }, section.examples.map(example)) : null)),
    lesson.vocabulary.length
      ? h("section", { class: "card" }, h("h2", {}, "İlgili kelimeler"),
          h("div", { class: "chips" }, lesson.vocabulary.map(wordChip)))
      : null,
    linked("Sonraki dersler", lesson.next_lessons),
    linked("İlgili dersler", lesson.related_lessons),
    lesson.question_count
      ? h("section", { class: "card", id: "lesson-test" },
          h("h2", {}, "Konu testi"),
          h("p", { class: "muted" }, `Bu konuda ${lesson.question_count} soru var. Her cevabın açıklaması gösterilir.`),
          h("a", { class: "btn primary", href: `#/test/ders/${encodeURIComponent(lesson.id)}` }, "Konu testini çöz"))
      : null,
    h("section", { class: "card" }, h("div", { class: "row" }, completeButton, statusText)),
    h("p", { class: "muted small" },
      `Kaynak: ${lesson.source_name}. `,
      lesson.review_status === "human_reviewed"
        ? "Bu içerik bir uzman tarafından gözden geçirilmiştir."
        : "Bu içerik otomatik denetimlerden geçmiştir; henüz bir uzman tarafından gözden geçirilmemiştir."),
  );
  return lesson.title_tr;
}
