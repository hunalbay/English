// Kelime kartları: çift yönlü, aralıklı tekrarlı çalışma oturumu.

import * as api from "../api.js";
import { POS_TR, add, h, levelBadge, pageHeader, toast } from "../dom.js";

const GRADES = [
  [0, "Bilemedim", "10 dk sonra tekrar", "danger"],
  [1, "Zor", "kısa aralık", ""],
  [2, "Bildim", "normal aralık", "primary"],
  [3, "Kolay", "uzun aralık", ""],
];

function nextDueText(review) {
  if (review.interval_days === 0) return "Bu kart yaklaşık 10 dakika sonra yeniden sorulacak.";
  return `Sonraki tekrar: ${review.interval_days} gün sonra.`;
}

export async function render(root, params) {
  const direction = params.direction === "tr_en" ? "tr_en" : "en_tr";
  const query = new URLSearchParams({ direction, source: params.source });
  if (params.source === "level" && params.level !== "-") query.set("level", params.level);
  const data = await api.get(`/study/session?${query}`);
  const title = direction === "en_tr" ? "Kartlar: İngilizce → Türkçe" : "Kartlar: Türkçe → İngilizce";

  const queue = data.cards.map((card) => ({ card, repeated: false }));
  const total = queue.length;
  const summary = { answered: 0, again: 0 };
  const stage = h("div", {});
  add(root, h("nav", { class: "breadcrumb", "aria-label": "Konum" }, h("a", { href: "#/calis" }, "Kelime çalışması"), " › Kartlar"),
    pageHeader(title), stage);

  if (total === 0) {
    stage.append(h("p", { class: "notice" },
      data.pool_size === 0
        ? "Bu kaynakta çalışılacak kelime yok."
        : "Şu an tekrar zamanı gelen ya da yeni kart yok. Daha sonra yeniden deneyin ya da başka bir kaynak seçin."),
      h("p", {}, h("a", { href: "#/calis" }, "Kelime çalışmasına dön")));
    return title;
  }

  let onKey = null;
  const cleanup = () => { if (onKey) document.removeEventListener("keydown", onKey); onKey = null; };
  window.addEventListener("hashchange", cleanup, { once: true });

  function finish() {
    cleanup();
    stage.replaceChildren(
      h("section", { class: "card" },
        h("h2", {}, "Oturum tamamlandı"),
        h("p", { id: "session-summary" }, `${summary.answered} cevap verdiniz; ${summary.again} kez "Bilemedim" dediniz.`),
        h("div", { class: "row" },
          h("button", { class: "btn primary", type: "button", onclick: () => { root.replaceChildren(); render(root, params); } }, "Yeni oturum"),
          h("a", { class: "btn", href: "#/calis" }, "Kelime çalışmasına dön"))));
  }

  function show() {
    cleanup();
    const entry = queue.shift();
    if (!entry) { finish(); return; }
    const { card } = entry;
    const frontText = direction === "en_tr" ? card.lemma : card.meaning_tr;
    const pos = card.pos.map((p) => POS_TR[p] || p).join(", ");
    const back = h("div", { class: "card-back", hidden: true });
    const buttons = h("div", { class: "row grade-row", hidden: true });
    const flip = h("button", { class: "btn primary", type: "button" }, "Cevabı göster (Boşluk)");
    const result = h("p", { class: "muted", "aria-live": "polite" });

    add(back,
      h("p", { class: "card-answer", lang: direction === "en_tr" ? "tr" : "en" }, direction === "en_tr" ? card.meaning_tr : card.lemma),
      card.ipa ? h("p", { class: "muted", lang: "en" }, `/${card.ipa}/`) : null,
      card.example ? h("div", { class: "example" }, h("p", { class: "ex-en", lang: "en" }, card.example.en), h("p", { class: "ex-tr" }, card.example.tr)) : null,
      card.notes_tr ? h("p", { class: "ex-note" }, card.notes_tr) : null,
      h("p", {}, h("a", { href: `#/kelime/${encodeURIComponent(card.id)}` }, "Kelime sayfası")));

    let busy = false;
    async function gradeCard(grade) {
      if (busy || back.hidden) return;
      busy = true;
      try {
        const response = await api.post("/study/review", { word_id: card.id, direction, grade });
        summary.answered += 1;
        if (grade === 0) {
          summary.again += 1;
          // Bilinemeyen kart oturum sonunda bir kez daha sorulur; aynı kart art arda yorulmaz.
          if (!entry.repeated) queue.push({ card, repeated: true });
        }
        result.textContent = nextDueText(response.review);
        show();
      } catch (error) {
        busy = false;
        toast(error.message, { error: true });
      }
    }
    add(buttons, GRADES.map(([grade, label, hint, style], index) =>
      h("button", { class: `btn ${style}`, type: "button", onclick: () => gradeCard(grade) },
        `${index + 1}. ${label}`, h("span", { class: "btn-hint" }, hint))));

    const reveal = () => { back.hidden = false; buttons.hidden = false; flip.hidden = true; buttons.querySelector("button:nth-child(3)").focus(); };
    flip.addEventListener("click", reveal);
    onKey = (event) => {
      if (event.target.closest("input, textarea, select")) return;
      if (back.hidden && (event.key === " " || event.key === "Enter")) { event.preventDefault(); reveal(); }
      else if (!back.hidden && ["1", "2", "3", "4"].includes(event.key)) gradeCard(Number(event.key) - 1);
    };
    document.addEventListener("keydown", onKey);

    stage.replaceChildren(
      h("p", { class: "muted", id: "card-progress" }, `Kalan kart: ${queue.length + 1}`,
        entry.repeated ? " · tekrar" : card.review.status === "new" ? " · yeni kelime" : ""),
      h("section", { class: "card flashcard" },
        h("div", { class: "row" }, levelBadge(card.level), h("span", { class: "muted" }, pos)),
        h("p", { class: "card-front", lang: direction === "en_tr" ? "en" : "tr" }, frontText),
        back, flip, buttons),
      result);
    flip.focus();
  }

  show();
  return title;
}
