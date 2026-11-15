// Ders sayfası: bölümler, örnekler, bağlantılı dersler ve kelimeler, tamamlama durumu.

import * as api from "../api.js";
import { audioPlayer, listenButton, recorder } from "../audio.js";
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

const TRACK_PATH = { grammar: "dersler", reading: "okuma", listening: "dinleme", writing: "yazma", pronunciation: "telaffuz" };
const TRACK_NAME = { grammar: "Dersler", reading: "Okuma", listening: "Dinleme", writing: "Yazma", pronunciation: "Telaffuz" };
const TEST_CARD = {
  grammar: ["Konu testi", "Konu testini çöz", "Bu konuda"],
  reading: ["Okuduğunu anlama soruları", "Soruları çöz", "Bu metinle ilgili"],
  listening: ["Dinlediğini anlama soruları", "Soruları çöz", "Bu kayıtla ilgili"],
  writing: ["Yazma çalışması", "Yazmaya başla", "Bu derste"],
  pronunciation: ["Konu testi", "Konu testini çöz", "Bu konuda"],
};

function passageLines(passage) {
  return h("div", { class: "passage", lang: "en" },
    passage.lines.map((line) =>
      h("div", { class: "passage-line" },
        h("p", { class: "passage-en" }, line.speaker ? h("strong", { class: "speaker" }, `${line.speaker}: `) : null, line.en),
        h("p", { class: "passage-tr", lang: "tr", hidden: true }, line.tr))));
}

function translationToggle(container) {
  const button = h("button", { class: "btn small", type: "button", "aria-pressed": "false" }, "Türkçe çevirileri göster");
  button.addEventListener("click", () => {
    const show = button.getAttribute("aria-pressed") !== "true";
    container.querySelectorAll(".passage-tr").forEach((el) => { el.hidden = !show; });
    button.setAttribute("aria-pressed", String(show));
    button.textContent = show ? "Türkçe çevirileri gizle" : "Türkçe çevirileri göster";
  });
  return button;
}

function glossary(passage) {
  if (!passage.glossary.length) return null;
  return h("details", { class: "glossary" }, h("summary", {}, `Metindeki kelimeler (${passage.glossary.length})`),
    h("ul", {}, passage.glossary.map((item) => h("li", {}, h("strong", { lang: "en" }, item.en), ` — ${item.tr}`))));
}

function readingSection(passage) {
  const lines = passageLines(passage);
  return h("section", { class: "card", id: "passage" },
    h("h2", {}, "Metin"),
    h("p", { class: "muted" }, "Önce metni çevirilere bakmadan okuyun. Takıldığınız yerde çevirileri açabilirsiniz."),
    lines, h("div", { class: "row" }, translationToggle(lines)), glossary(passage));
}

function listeningSection(passage) {
  const lines = passageLines(passage);
  const transcript = h("div", { id: "transcript", hidden: true }, lines, h("div", { class: "row" }, translationToggle(lines)), glossary(passage));
  const reveal = h("button", { class: "btn", type: "button", "aria-expanded": "false", "aria-controls": "transcript" }, "Yazılı metni göster");
  reveal.addEventListener("click", () => {
    transcript.hidden = !transcript.hidden;
    reveal.setAttribute("aria-expanded", String(!transcript.hidden));
    reveal.textContent = transcript.hidden ? "Yazılı metni göster" : "Yazılı metni gizle";
  });
  return h("section", { class: "card", id: "passage" },
    h("h2", {}, "Kayıt"),
    h("p", { class: "muted" },
      "Kaydı önce yazılı metne bakmadan en az iki kez dinleyin, sonra soruları çözün. " +
      "Kayıtlar bilgisayar tarafından üretilmiş (sentetik) seslerdir."),
    audioPlayer(passage.audio, { fallbackText: passage.lines.map((line) => line.en).join(" ") }),
    h("div", { class: "row" }, reveal), transcript);
}

function practiceSection(items) {
  return h("section", { class: "card", id: "practice" },
    h("h2", {}, "Dinle, tekrar et, karşılaştır"),
    h("p", { class: "muted" },
      "Örnek sesi dinleyin, kendi sesinizi kaydedin ve ikisini karşılaştırın. Program telaffuzunuzu otomatik olarak " +
      "puanlamaz; değerlendirmeyi siz yaparsınız. Kayıtlarınız hiçbir yere gönderilmez ve saklanmaz; " +
      "sayfadan çıktığınızda silinir. Mikrofon izni yalnızca “Kaydet” düğmesine bastığınızda istenir."),
    h("ul", { class: "practice" }, items.map((item) =>
      h("li", { class: "practice-item" },
        h("p", { class: "practice-en", lang: "en" }, item.en, item.ipa ? h("span", { class: "muted ipa" }, ` /${item.ipa}/`) : null),
        h("p", { class: "ex-tr" }, item.tr),
        item.note_tr ? h("p", { class: "ex-note" }, item.note_tr) : null,
        h("div", { class: "row" }, listenButton(item.audio, item.en, { label: "Örneği dinle" }), recorder(item.en))))));
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
      h("a", { href: `#/${TRACK_PATH[lesson.track]}/${lesson.level}` }, `${TRACK_NAME[lesson.track]} ${lesson.level}`),
      " › ", lesson.unit_title_tr),
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
    lesson.passage && lesson.kind === "listening" ? listeningSection(lesson.passage) : null,
    lesson.passage && lesson.kind !== "listening" ? readingSection(lesson.passage) : null,
    lesson.sections.map((section) =>
      h("section", { class: `card section-${section.kind}` },
        h("h2", {}, section.title_tr),
        richText(section.text_tr),
        section.table ? table(section.table) : null,
        section.examples.length ? h("ul", { class: "examples" }, section.examples.map(example)) : null)),
    lesson.practice.length ? practiceSection(lesson.practice) : null,
    lesson.vocabulary.length
      ? h("section", { class: "card" }, h("h2", {}, "İlgili kelimeler"),
          h("div", { class: "chips" }, lesson.vocabulary.map(wordChip)))
      : null,
    linked("Sonraki dersler", lesson.next_lessons),
    linked("İlgili dersler", lesson.related_lessons),
    lesson.question_count
      ? h("section", { class: "card", id: "lesson-test" },
          h("h2", {}, TEST_CARD[lesson.track][0]),
          h("p", { class: "muted" }, lesson.track === "writing"
            ? `${TEST_CARD.writing[2]} ${lesson.question_count} çalışma var. Yazdıklarınızı örnek metin ve kontrol listesiyle kendiniz değerlendirirsiniz; program yazınızı otomatik olarak puanlamaz.`
            : `${TEST_CARD[lesson.track][2]} ${lesson.question_count} soru var. Her cevabın açıklaması gösterilir.`),
          h("a", { class: "btn primary", href: `#/test/ders/${encodeURIComponent(lesson.id)}` }, TEST_CARD[lesson.track][1]))
      : null,
    h("section", { class: "card" }, h("div", { class: "row" }, completeButton, statusText)),
    h("p", { class: "muted small" },
      `Kaynak: ${lesson.source_name}. `,
      lesson.review_status === "human_reviewed"
        ? "Bu içerik bir uzman tarafından gözden geçirilmiştir."
        : "Bu içerik otomatik denetimlerden geçmiştir; henüz bir uzman tarafından gözden geçirilmemiştir."),
  );
  root.dataset.section = `/${TRACK_PATH[lesson.track]}`; // menüde dersin ait olduğu alan işaretlenir
  return lesson.title_tr;
}
