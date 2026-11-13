// Kelime alıştırmaları: soru, kurallı değerlendirme ve açıklamalı geri bildirim.

import * as api from "../api.js";
import { add, h, pageHeader, toast } from "../dom.js";
import { EXERCISES } from "./study.js";

const INSTRUCTIONS = {
  mc_en_tr: "Kelimenin Türkçe anlamını seçin.",
  mc_tr_en: "Bu anlamın İngilizce karşılığını seçin.",
  typing: "Bu anlamın İngilizce karşılığını yazın.",
  cloze: "Boşluğa gelen kelimeyi (temel biçimiyle) seçin.",
  antonym: "Kelimenin zıt anlamlısını seçin.",
  matching: "Her İngilizce kelime için doğru Türkçe karşılığı seçin.",
};

function wordLink(word) {
  return h("a", { href: `#/kelime/${encodeURIComponent(word.id)}`, lang: "en" }, word.lemma);
}

function feedbackBox(feedback) {
  const box = h("div", { class: `feedback ${feedback.correct ? "ok" : "bad"}`, role: "status" });
  add(box, h("p", { class: "feedback-title" }, feedback.correct ? "Doğru!" : "Yanlış."));
  if (feedback.word) {
    add(box,
      h("p", {}, "Doğru cevap: ", h("strong", {}, feedback.correct_answer), " — ", wordLink(feedback.word), " = ", feedback.word.meaning_tr),
      feedback.note ? h("p", {}, feedback.note) : null,
      feedback.chosen
        ? h("p", {}, "Sizin cevabınız: ", wordLink(feedback.chosen), ` = ${feedback.chosen.meaning_tr}. Bu yüzden bu soruda doğru değil.`)
        : null,
      feedback.word.example
        ? h("div", { class: "example" }, h("p", { class: "ex-en", lang: "en" }, feedback.word.example.en), h("p", { class: "ex-tr" }, feedback.word.example.tr))
        : null,
      feedback.word.notes_tr ? h("p", { class: "ex-note" }, feedback.word.notes_tr) : null);
  } else {
    add(box, h("ul", {}, feedback.results.map((r) =>
      h("li", {}, h("span", { class: `mark ${r.correct ? "good" : "bad"}` }, r.correct ? "Doğru: " : "Yanlış: "),
        wordLink({ id: r.word_id, lemma: r.lemma }), ` = ${r.meaning_tr}`))));
  }
  return box;
}

export async function render(root, params) {
  const info = EXERCISES.find(([type]) => type === params.type);
  if (!info) throw Object.assign(new Error("Böyle bir alıştırma türü yok."), { status: 404 });
  const [type, title] = info;
  const query = new URLSearchParams({ type, source: params.source, size: type === "matching" ? "3" : "10" });
  if (params.source === "level" && params.level !== "-") query.set("level", params.level);
  const data = await api.get(`/study/exercises?${query}`);
  const questions = data.questions;
  const stage = h("div", {});
  add(root, h("nav", { class: "breadcrumb", "aria-label": "Konum" }, h("a", { href: "#/calis" }, "Kelime çalışması"), " › Alıştırma"),
    pageHeader(title), stage);

  if (questions.length === 0) {
    stage.append(h("p", { class: "notice" },
      "Seçtiğiniz kelimelerle bu türde soru üretilemedi (yeterli kelime ya da gerekli veri yok). Başka bir kaynak ya da alıştırma türü deneyin."),
      h("p", {}, h("a", { href: "#/calis" }, "Kelime çalışmasına dön")));
    return title;
  }

  let index = 0;
  let correctCount = 0;
  const missed = [];

  function finish() {
    stage.replaceChildren(
      h("section", { class: "card" },
        h("h2", {}, "Alıştırma tamamlandı"),
        h("p", { id: "exercise-summary" }, `${questions.length} sorudan ${correctCount} tanesini doğru cevapladınız.`),
        missed.length
          ? [h("p", {}, "Tekrar etmeniz gereken kelimeler:"), h("div", { class: "chips" }, missed.map((word) =>
              h("a", { class: "chip", href: `#/kelime/${encodeURIComponent(word.id)}` }, h("span", { lang: "en" }, word.lemma), h("span", { class: "muted" }, ` — ${word.meaning_tr}`))))]
          : null,
        h("div", { class: "row" },
          h("button", { class: "btn primary", type: "button", onclick: () => { root.replaceChildren(); render(root, params); } }, "Yeni sorular"),
          h("a", { class: "btn", href: "#/calis" }, "Kelime çalışmasına dön"))));
  }

  function show() {
    const question = questions[index];
    const area = h("div", {});
    const after = h("div", {});
    let answered = false;

    async function submit(answer, controls) {
      if (answered) return;
      answered = true;
      controls.forEach((control) => { control.disabled = true; });
      let feedback;
      try {
        feedback = await api.post("/study/answer", { type, word_id: question.word_id, answer });
      } catch (error) {
        answered = false;
        controls.forEach((control) => { control.disabled = false; });
        toast(error.message, { error: true });
        return;
      }
      if (feedback.correct) correctCount += 1;
      else if (feedback.word) missed.push(feedback.word);
      else feedback.results.filter((r) => !r.correct).forEach((r) => missed.push({ id: r.word_id, lemma: r.lemma, meaning_tr: r.meaning_tr }));
      area.querySelectorAll("[data-option]").forEach((button) => {
        if (feedback.word && (button.dataset.option === feedback.word.id && type !== "antonym")) button.classList.add("right");
        if (button.dataset.option === answer && !feedback.correct) button.classList.add("wrong");
        if (button.dataset.option === answer && feedback.correct) button.classList.add("right");
      });
      const next = h("button", { class: "btn primary", type: "button", onclick: () => { index += 1; index < questions.length ? show() : finish(); } },
        index + 1 < questions.length ? "Sonraki soru" : "Sonucu gör");
      after.replaceChildren(feedbackBox(feedback), next);
      next.focus();
    }

    if (type === "matching") {
      const selects = question.left.map((item) => {
        const select = h("select", { id: `m-${item.id}`, "data-left": item.id },
          h("option", { value: "" }, "Seçin…"), question.right.map((r) => h("option", { value: r.id }, r.text)));
        return { item, select };
      });
      const check = h("button", { class: "btn primary", type: "submit" }, "Kontrol et");
      add(area, h("form", {
        onsubmit: (event) => {
          event.preventDefault();
          if (selects.some(({ select }) => !select.value)) { toast("Lütfen bütün kelimeleri eşleştirin.", { error: true }); return; }
          submit(Object.fromEntries(selects.map(({ item, select }) => [item.id, select.value])), [check, ...selects.map((s) => s.select)]);
        },
      },
        selects.map(({ item, select }) => h("div", { class: "match-row" }, h("label", { for: select.id, lang: "en" }, item.text), select)),
        check));
    } else if (type === "typing") {
      const input = h("input", { id: "typed", type: "text", autocomplete: "off", autocapitalize: "off", spellcheck: "false", maxlength: "60", lang: "en" });
      const check = h("button", { class: "btn primary", type: "submit" }, "Kontrol et");
      add(area,
        h("p", { class: "question-prompt" }, question.prompt),
        h("form", { class: "row", onsubmit: (event) => {
          event.preventDefault();
          if (!input.value.trim()) { toast("Lütfen bir cevap yazın.", { error: true }); return; }
          submit(input.value, [input, check]);
        } },
          h("label", { class: "visually-hidden", for: "typed" }, "İngilizce karşılığı"), input, check),
        h("p", { class: "muted small" }, `İpucu: "${question.first_letter}" harfiyle başlar, ${question.length} harflidir.`));
      setTimeout(() => input.focus(), 0);
    } else {
      const buttons = question.options.map((option) =>
        h("button", { class: "btn option", type: "button", "data-option": option.id, lang: type === "mc_en_tr" ? "tr" : "en",
          onclick: () => submit(option.id, buttons) }, option.text));
      add(area,
        h("p", { class: "question-prompt", lang: question.prompt_lang }, question.prompt),
        question.hint ? h("p", { class: "muted" }, type === "cloze" ? `Türkçesi: ${question.hint}` : `Anlamı: ${question.hint}`) : null,
        h("div", { class: "options" }, buttons));
    }

    stage.replaceChildren(
      h("p", { class: "muted", id: "question-progress" }, `Soru ${index + 1} / ${questions.length}`),
      h("section", { class: "card" }, h("p", { class: "muted" }, INSTRUCTIONS[type]), area, after));
  }

  show();
  return title;
}
