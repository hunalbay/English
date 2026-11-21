// Seviye tespit sınavı. Her seviyede 8 soru sorulur; cevaplar sınav bitene kadar gösterilmez.

import * as api from "../api.js";
import { LEVEL_NAMES, add, h, pageHeader, toast } from "../dom.js";

const LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"];
const LEVEL_TR = { below_A1: "A1 altı" };

function levelSelect() {
  return h("select", { id: "start-level", "aria-label": "Başlangıç seviyesi" },
    LEVELS.map((code) => h("option", { value: code, selected: code === "A1" }, `${code} — ${LEVEL_NAMES[code]}`)));
}

function renderIntro(root, overview) {
  const select = levelSelect();
  const start = h("button", { class: "btn primary", type: "button" }, "Sınava başla");
  start.addEventListener("click", async () => {
    start.disabled = true;
    try {
      const data = await api.post("/placement/sessions", { start_level: select.value });
      runTest(root, data);
    } catch (error) {
      toast(error.message, { error: true });
      start.disabled = false;
    }
  });
  add(root,
    pageHeader("Seviye tespit sınavı", "Hangi seviyeden başlamanız gerektiğini tahmin etmek için kısa bir sınav."),
    h("section", { class: "card" },
      h("h2", {}, "Nasıl işler?"),
      h("ul", {},
        h("li", {}, `Her seviye için ${overview.block_size} soru sorulur. ${overview.pass_mark} veya daha fazla doğru, o seviyeyi geçtiğiniz anlamına gelir.`),
        h("li", {}, "Geçtiğiniz seviyeden sonra bir üst seviye, kaldığınız seviyeden sonra (gerekirse) bir alt seviye sorulur."),
        h("li", {}, `Sınav en fazla ${overview.max_blocks} bölüm sürer; çoğu kişi için 2–4 bölüm (yaklaşık 10–20 dakika).`),
        h("li", {}, "Cevaplarınızın doğru olup olmadığı sınav bitene kadar gösterilmez."),
        h("li", {}, "Sayfadan çıkarsanız yarım kalan sınav kaydedilmez; yeniden başlamanız gerekir.")),
      h("p", { class: "notice" }, overview.limits_tr)),
    h("section", { class: "card" },
      h("h2", {}, "Başlangıç seviyesi"),
      h("p", { class: "muted" }, "Emin değilseniz A1'den başlayın. Seviyenizin daha yüksek olduğunu düşünüyorsanız oradan başlayabilirsiniz; kalırsanız sınav bir alt seviyeyi de sorar."),
      h("div", { class: "row" }, select, start)),
    overview.history.length
      ? h("section", { class: "card" },
          h("h2", {}, "Önceki sonuçlar"),
          h("ul", { id: "placement-history" }, overview.history.map((item) =>
            h("li", {}, `${new Date(item.finished_at).toLocaleDateString("tr-TR")}: tahmini seviye `,
              h("strong", {}, LEVEL_TR[item.result_level] || item.result_level),
              `, önerilen çalışma seviyesi ${item.recommended_level}`))))
      : null,
  );
}

function questionView(question, onAnswer) {
  const box = h("div", { class: "card", id: "placement-question" });
  add(box,
    question.context ? h("pre", { class: "context", lang: "en" }, question.context) : null,
    question.passage
      ? h("div", { class: "context passage", lang: "en" }, question.passage.lines.map((line) =>
          h("p", {}, line.speaker ? h("strong", {}, `${line.speaker}: `) : null, line.en)))
      : null,
    h("p", { class: "muted small" }, question.instruction_tr),
    h("p", { class: "question-prompt", lang: /[ğşıİçöü]/i.test(question.prompt) ? "tr" : "en" }, question.prompt));
  if (question.evaluator === "choice") {
    add(box, h("div", { class: "options" }, question.options.map((option) =>
      h("button", { class: "btn option", type: "button", lang: "en", onclick: () => onAnswer(option.position) }, option.text))));
  } else {
    const input = h("input", { id: "answer-input", type: "text", autocomplete: "off", spellcheck: "false", lang: "en",
      "aria-label": "Cevabınız", maxlength: "500" });
    const form = h("form", { class: "row", novalidate: true }, input, h("button", { class: "btn primary", type: "submit" }, "Cevapla"));
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!input.value.trim()) { toast("Lütfen bir cevap yazın.", { error: true }); return; }
      onAnswer(input.value.trim());
    });
    add(box, form);
    setTimeout(() => input.focus(), 0);
  }
  return box;
}

function runTest(root, data) {
  let state = data;
  let index = 0;
  const status = h("p", { class: "muted", "aria-live": "polite", id: "placement-status" });
  const area = h("div");
  root.replaceChildren(pageHeader("Seviye tespit sınavı"), status, area);

  const paint = () => {
    const question = state.questions[index];
    status.textContent = `Bölüm ${state.block_number} · ${state.current_level} seviyesi · Soru ${index + 1} / ${state.questions.length}`;
    area.replaceChildren(questionView(question, submit));
  };
  const submit = async (answer) => {
    area.querySelectorAll("button, input").forEach((el) => { el.disabled = true; });
    try {
      await api.post(`/tests/sessions/${state.session_id}/answers`, { question_id: state.questions[index].id, answer });
    } catch (error) {
      toast(error.message, { error: true });
      area.querySelectorAll("button, input").forEach((el) => { el.disabled = false; });
      return;
    }
    index += 1;
    if (index < state.questions.length) { paint(); return; }
    status.textContent = "Bölüm değerlendiriliyor…";
    try {
      const next = await api.post(`/placement/sessions/${state.session_id}/next`, {});
      if (next.finished) { renderResult(root, next); return; }
      state = next;
      index = 0;
      paint();
    } catch (error) {
      toast(error.message, { error: true });
    }
  };
  paint();
}

async function applyLevel(level) {
  try {
    await api.put("/profile/level", { level, source: "placement" });
    toast(`Çalışma seviyeniz ${level} olarak ayarlandı.`);
    location.hash = "#/";
  } catch (error) {
    toast(error.message, { error: true });
  }
}

function renderResult(root, result) {
  const estimated = LEVEL_TR[result.result_level] || result.result_level;
  const recommended = result.recommended_level;
  root.replaceChildren();
  add(root,
    pageHeader("Seviye tespit sonucu"),
    h("section", { class: "card", id: "placement-result" },
      h("div", { class: "grid" },
        h("div", {}, h("p", { class: "stat-label" }, "Tahmini seviyeniz"), h("p", { class: "big-level" }, estimated),
          LEVEL_NAMES[result.result_level] ? h("p", { class: "muted" }, LEVEL_NAMES[result.result_level]) : null),
        h("div", {}, h("p", { class: "stat-label" }, "Önerilen çalışma seviyesi"), h("p", { class: "big-level" }, recommended),
          h("p", { class: "muted" }, LEVEL_NAMES[recommended]))),
      h("p", {}, result.result_level === "below_A1"
        ? "A1 bölümünü geçmek için gereken doğru sayısına ulaşmadınız. En baştan, A1 derslerinden başlamanızı öneririz."
        : result.result_level === recommended
          ? `${recommended} seviyesini de geçtiniz. ${recommended} derslerindeki ince konularla devam edebilirsiniz.`
          : `${estimated} seviyesindeki soruların çoğunu doğru cevapladınız. ${recommended} derslerine başlayabilirsiniz; aşağıdaki konuları da tekrar etmeniz yararlı olur.`),
      h("div", { class: "row" },
        h("button", { class: "btn primary", type: "button", onclick: () => applyLevel(recommended) }, `${recommended} seviyesiyle devam et`),
        LEVELS.includes(result.result_level) && result.result_level !== recommended
          ? h("button", { class: "btn", type: "button", onclick: () => applyLevel(result.result_level) }, `${result.result_level} seviyesiyle devam et`)
          : null)),
    h("section", { class: "card" },
      h("h2", {}, "Bölümler"),
      h("div", { class: "table-wrap" },
        h("table", {},
          h("thead", {}, h("tr", {}, h("th", { scope: "col" }, "Seviye"), h("th", { scope: "col" }, "Doğru"), h("th", { scope: "col" }, "Sonuç"))),
          h("tbody", {}, result.blocks.map((block) =>
            h("tr", {}, h("td", {}, block.level), h("td", {}, `${block.correct} / ${block.total}`),
              h("td", {}, h("span", { class: `badge ${block.passed ? "ok" : "warn"}` }, block.passed ? "Geçti" : "Kaldı"))))))),
      h("p", { class: "muted small" }, `Toplam ${result.answered} sorudan ${result.correct} tanesi doğru. Bir bölümü geçmek için ${result.pass_mark} / ${result.block_size} doğru gerekir.`)),
    result.review_lessons.length
      ? h("section", { class: "card" },
          h("h2", {}, "Tekrar etmeniz önerilen konular"),
          h("p", { class: "muted" }, "Sınavda yanlış cevapladığınız soruların ait olduğu dersler:"),
          h("ul", { id: "review-lessons" }, result.review_lessons.map((lesson) =>
            h("li", {}, h("a", { href: `#/ders/${encodeURIComponent(lesson.id)}` }, lesson.title_tr), ` (${lesson.level})`))))
      : null,
    h("p", { class: "notice" }, result.limits_tr),
    h("p", {}, h("a", { href: "#/ilerleme" }, "İlerleme raporunu aç"), " · ", h("a", { href: "#/seviye-tespiti" }, "Sınav sayfasına dön")),
  );
}

export async function render(root) {
  const overview = await api.get("/placement");
  renderIntro(root, overview);
  return "Seviye tespiti";
}
