// Test çözme: soru tipine göre arayüz, açıklamalı geri bildirim, ilgili derse geçiş.

import * as api from "../api.js";
import { wordChip } from "../components.js";
import { add, h, levelBadge, pageHeader, toast } from "../dom.js";

const TYPE_TR = {
  multiple_choice: "Çoktan seçmeli", true_false: "Doğru / yanlış", fill_blank: "Boşluk doldurma",
  sentence_building: "Cümle kurma", word_order: "Kelime sıralama", matching: "Eşleştirme",
  translation: "Çeviri", written_answer: "Yazılı cevap", error_spotting: "Hata bulma",
  error_correction: "Hata düzeltme", sentence_completion: "Cümle tamamlama",
  dialogue_completion: "Diyalog tamamlama", reading_comprehension: "Okuduğunu anlama",
  listening_comprehension: "Dinlediğini anlama", word_in_context: "Bağlamda kelime",
  word_formation: "Kelime türetme", paragraph_completion: "Paragraf tamamlama", nuance: "Anlam nüansı",
};
const RESULT_TR = {
  correct: ["Doğru!", "ok"], incorrect: ["Yanlış.", "bad"],
  ungraded: ["Kendiniz değerlendirin", "neutral"],
};

function example(item) {
  return h("div", { class: "example" }, h("p", { class: "ex-en", lang: "en" }, item.en), h("p", { class: "ex-tr" }, item.tr));
}

function feedbackBox(feedback, question, { onSelfRate }) {
  const [title, kind] = RESULT_TR[feedback.result] || RESULT_TR.ungraded;
  const box = h("div", { class: `feedback ${kind}`, role: "status", id: "feedback" }, h("p", { class: "feedback-title" }, title));

  if (feedback.options) {
    add(box, h("ul", { class: "option-reasons" }, feedback.options.map((option) =>
      h("li", { class: option.is_correct ? "is-right" : option.position === feedback.chosen ? "is-chosen" : "" },
        h("span", { class: `mark ${option.is_correct ? "good" : "bad"}` }, option.is_correct ? "Doğru: " : "Yanlış: "),
        h("strong", { lang: "en" }, option.text),
        option.position === feedback.chosen ? h("span", { class: "muted" }, " (sizin cevabınız)") : null,
        " — ", option.explanation_tr))));
  }
  if (feedback.accepted_answers) {
    add(box, h("p", {}, feedback.result === "correct" ? "Kabul edilen cevaplar: " : "Doğru cevap: ",
      feedback.accepted_answers.flatMap((answer, index) => [index ? " / " : "", h("strong", { lang: "en" }, answer)])));
  }
  if (feedback.correct_order) {
    add(box, h("p", {}, "Doğru sıra: ", h("strong", { lang: "en" }, feedback.correct_order.join(" ").replace(/ ([?.!,])/g, "$1")),
      feedback.also.map((alt) => [" / ", h("strong", { lang: "en" }, alt.join(" ").replace(/ ([?.!,])/g, "$1"))])));
  }
  if (feedback.pairs) {
    add(box, h("ul", {}, feedback.pairs.map((pair) =>
      h("li", {}, h("span", { class: `mark ${pair.correct ? "good" : "bad"}` }, pair.correct ? "Doğru: " : "Yanlış: "),
        h("strong", { lang: "en" }, pair.left), " → ", pair.right,
        pair.correct ? null : h("span", { class: "muted" }, ` (sizin cevabınız: ${pair.chosen})`)))));
  }
  if (feedback.model_answers && feedback.model_answers.length) {
    add(box, h("p", {}, h("strong", {}, "Örnek cevap:")),
      feedback.model_answers.map((answer) => h("p", { class: "ex-en", lang: "en" }, answer)));
  }
  if (feedback.checklist && feedback.checklist.length) {
    add(box, h("p", {}, h("strong", {}, "Kontrol listesi:")), h("ul", {}, feedback.checklist.map((item) => h("li", {}, item))));
  }
  if (feedback.note_tr) add(box, h("p", { class: "notice" }, feedback.note_tr));
  add(box, h("p", {}, h("strong", {}, "Açıklama: "), feedback.explanation_tr));
  if (feedback.example) add(box, example(feedback.example));
  if (feedback.lesson_examples.length) {
    add(box, h("details", {}, h("summary", {}, "Dersten benzer örnekler"), feedback.lesson_examples.map(example)));
  }
  if (feedback.vocabulary.length) add(box, h("div", { class: "chips" }, feedback.vocabulary.map(wordChip)));

  if (feedback.result === "ungraded") {
    const rate = (rating, label, style) =>
      h("button", { class: `btn ${style}`, type: "button", onclick: () => onSelfRate(rating) }, label);
    add(box, h("div", { class: "row", id: "self-rating" }, h("span", {}, "Cevabınız örnek cevaba göre nasıl?"),
      rate("correct", "Doğruydu", ""), rate("partial", "Kısmen doğruydu", ""), rate("incorrect", "Yanlıştı", "")));
  }
  add(box, h("div", { class: "row feedback-links" },
    feedback.lessons.map((lesson) =>
      h("a", { class: "btn small", href: `#/ders/${encodeURIComponent(lesson.id)}` }, `İlgili ders: ${lesson.title_tr}`)),
    feedback.lessons.length
      ? h("a", { class: "btn small", href: `#/test/ders/${encodeURIComponent(feedback.lessons[0].id)}/${Date.now()}` }, "Aynı konudan yeni sorular")
      : null));
  return box;
}

export async function render(root, params) {
  const body = params.lessonId ? { lesson_id: params.lessonId, size: 10 } : { level: params.level.toUpperCase(), size: 10 };
  const test = await api.post("/tests/sessions", body);
  const questions = test.questions;
  const title = params.lessonId ? `Konu testi: ${questions[0].lesson.title_tr}` : `${body.level} karışık test`;
  const stage = h("div", {});
  add(root, h("nav", { class: "breadcrumb", "aria-label": "Konum" }, h("a", { href: "#/testler" }, "Testler"), " › Test"),
    pageHeader(title), stage);

  let index = 0;
  const results = [];

  async function finish() {
    let summary;
    try {
      summary = await api.post(`/tests/sessions/${test.session_id}/finish`);
    } catch (error) {
      toast(error.message, { error: true });
      return;
    }
    const missedLessons = new Map();
    results.filter((r) => r.result === "incorrect" || r.result === "self_incorrect")
      .forEach((r) => { if (r.lesson) missedLessons.set(r.lesson.id, r.lesson); });
    stage.replaceChildren(
      h("section", { class: "card" },
        h("h2", {}, "Test tamamlandı"),
        h("p", { id: "test-summary" }, `${summary.total} sorudan ${summary.correct} doğru, ${summary.incorrect} yanlış.`,
          summary.partial ? ` ${summary.partial} cevabı kısmen doğru olarak işaretlediniz.` : "",
          summary.ungraded ? ` ${summary.ungraded} cevap değerlendirilmedi.` : ""),
        summary.self_assessed
          ? h("p", { class: "muted small" }, `${summary.self_assessed} cevabın sonucu sizin öz değerlendirmenize dayanıyor.`)
          : null,
        missedLessons.size
          ? [h("p", {}, "Tekrar etmeniz önerilen dersler:"),
             h("div", { class: "row" }, [...missedLessons.values()].map((lesson) =>
               h("a", { class: "btn small", href: `#/ders/${encodeURIComponent(lesson.id)}` }, lesson.title_tr)))]
          : null,
        h("div", { class: "row" },
          h("button", { class: "btn primary", type: "button", onclick: () => { root.replaceChildren(); render(root, params); } }, "Yeni test"),
          h("a", { class: "btn", href: "#/testler" }, "Testlere dön"))));
  }

  function show() {
    const question = questions[index];
    const area = h("div", { class: "question-area" });
    const after = h("div", {});
    let answered = false;

    function nextButton() {
      const button = h("button", { class: "btn primary", type: "button", id: "next-question",
        onclick: () => { index += 1; if (index < questions.length) show(); else finish(); } },
        index + 1 < questions.length ? "Sonraki soru" : "Sonucu gör");
      return button;
    }

    async function submit(answer, controls, mark) {
      if (answered) return;
      answered = true;
      controls.forEach((control) => { control.disabled = true; });
      let feedback;
      try {
        feedback = await api.post(`/tests/sessions/${test.session_id}/answers`, { question_id: question.id, answer });
      } catch (error) {
        answered = false;
        controls.forEach((control) => { control.disabled = false; });
        toast(error.message, { error: true });
        return;
      }
      const record = { result: feedback.result, lesson: question.lesson };
      results.push(record);
      if (mark) mark(feedback);
      const paint = () => {
        const next = nextButton();
        after.replaceChildren(feedbackBox(feedback, question, {
          onSelfRate: async (rating) => {
            try {
              const rated = await api.post(`/tests/sessions/${test.session_id}/self-rating`, { question_id: question.id, rating });
              record.result = rated.result;
              document.getElementById("self-rating").replaceChildren(
                h("span", { class: "muted" }, "Değerlendirmeniz kaydedildi."));
            } catch (error) {
              toast(error.message, { error: true });
            }
          },
        }), next);
        next.focus();
      };
      paint();
    }

    add(area,
      question.context ? h("pre", { class: "context", lang: "en" }, question.context) : null,
      h("p", { class: "question-prompt", lang: /[ğşıİçöü]/i.test(question.prompt) ? "tr" : "en" }, question.prompt));

    if (question.evaluator === "choice") {
      const buttons = question.options.map((option) =>
        h("button", { class: "btn option", type: "button", "data-position": String(option.position),
          onclick: () => submit(option.position, buttons, (feedback) => {
            buttons.forEach((button) => {
              const info = feedback.options.find((o) => String(o.position) === button.dataset.position);
              if (info.is_correct) button.classList.add("right");
              else if (info.position === feedback.chosen) button.classList.add("wrong");
            });
          }) }, option.text));
      add(area, h("div", { class: "options" }, buttons));
    } else if (question.evaluator === "text") {
      const input = h("input", { id: "answer-input", type: "text", class: "wide", autocomplete: "off", autocapitalize: "off",
        spellcheck: "false", maxlength: "300", lang: "en" });
      const check = h("button", { class: "btn primary", type: "submit" }, "Kontrol et");
      add(area,
        h("form", { class: "row", onsubmit: (event) => {
          event.preventDefault();
          if (!input.value.trim()) { toast("Lütfen bir cevap yazın.", { error: true }); return; }
          submit(input.value, [input, check]);
        } }, h("label", { class: "visually-hidden", for: "answer-input" }, "Cevabınız"), input, check),
        question.strict ? h("p", { class: "muted small" }, "Bu soruda büyük/küçük harf ve noktalama da değerlendirilir.") : null);
      setTimeout(() => input.focus(), 0);
    } else if (question.evaluator === "order") {
      const chosen = [];
      const pool = question.tokens.map((token, i) => ({ token, i, used: false }));
      const answerLine = h("p", { class: "order-answer", id: "order-answer", "aria-live": "polite", lang: "en" });
      const bank = h("div", { class: "chips", id: "token-bank" });
      const check = h("button", { class: "btn primary", type: "button" }, "Kontrol et");
      const undo = h("button", { class: "btn", type: "button" }, "Geri al");
      const paint = () => {
        answerLine.textContent = chosen.length ? chosen.map((item) => item.token).join(" ") : "Sözcüklere sırayla tıklayın.";
        bank.replaceChildren(...pool.map((item) =>
          h("button", { class: "btn token", type: "button", disabled: item.used || answered, lang: "en",
            onclick: () => { item.used = true; chosen.push(item); paint(); } }, item.token)));
        check.disabled = chosen.length !== pool.length || answered;
        undo.disabled = chosen.length === 0 || answered;
      };
      undo.addEventListener("click", () => { const item = chosen.pop(); if (item) item.used = false; paint(); });
      check.addEventListener("click", () => submit(chosen.map((item) => item.token), [check, undo], () => paint()));
      add(area, answerLine, bank, h("div", { class: "row" }, check, undo));
      paint();
    } else if (question.evaluator === "matching") {
      const selects = question.left.map((left, i) => ({
        left,
        select: h("select", { id: `match-${i}` }, h("option", { value: "" }, "Seçin…"),
          question.right.map((right) => h("option", { value: right }, right))),
      }));
      const check = h("button", { class: "btn primary", type: "submit" }, "Kontrol et");
      add(area, h("form", { onsubmit: (event) => {
        event.preventDefault();
        if (selects.some(({ select }) => !select.value)) { toast("Lütfen bütün öğeleri eşleştirin.", { error: true }); return; }
        submit(Object.fromEntries(selects.map(({ left, select }) => [left, select.value])), [check, ...selects.map((s) => s.select)]);
      } }, selects.map(({ left, select }) => h("div", { class: "match-row" }, h("label", { for: select.id, lang: "en" }, left), select)), check));
    } else {
      const textarea = h("textarea", { id: "answer-input", rows: "5", maxlength: "4000", lang: "en", spellcheck: "false" });
      const check = h("button", { class: "btn primary", type: "submit" }, "Cevabımı kaydet ve örnek cevabı göster");
      add(area, h("form", { onsubmit: (event) => {
        event.preventDefault();
        if (!textarea.value.trim()) { toast("Lütfen bir cevap yazın.", { error: true }); return; }
        submit(textarea.value, [textarea, check]);
      } }, h("label", { class: "visually-hidden", for: "answer-input" }, "Cevabınız"), textarea, check),
        h("p", { class: "muted small" }, "Serbest yazılı cevapları program değerlendirmez; örnek cevapla karşılaştırıp kendiniz değerlendirirsiniz."));
    }

    stage.replaceChildren(
      h("p", { class: "muted row", id: "question-progress" }, `Soru ${index + 1} / ${questions.length}`,
        levelBadge(question.level), h("span", {}, TYPE_TR[question.type] || question.type)),
      h("section", { class: "card" }, h("p", { class: "muted" }, question.instruction_tr), area, after));
  }

  show();
  return title;
}
