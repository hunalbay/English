// Küçük DOM yardımcıları. İçerik her zaman metin düğümü olarak eklenir (innerHTML kullanılmaz).

export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") el.className = value;
    else if (key.startsWith("on") && typeof value === "function") el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, "");
    else el.setAttribute(key, value);
  }
  add(el, children);
  return el;
}

// Çocukları ekler: iç içe diziler açılır, null/undefined/false atlanır, metin her zaman metin düğümü olur.
export function add(parent, ...children) {
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    parent.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return parent;
}

let toastTimer = null;

export function toast(message, { error = false } = {}) {
  const el = document.getElementById("toast");
  el.textContent = message;
  el.classList.toggle("error", error);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, error ? 6000 : 2500);
}

export function applyTheme(theme) {
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  else delete document.documentElement.dataset.theme;
}

// "**kalın**" işaretlerini <strong> öğesine çevirir; başka hiçbir biçimlendirme yorumlanmaz.
function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).filter(Boolean).map((part) =>
    part.startsWith("**") && part.endsWith("**") && part.length > 4 ? h("strong", {}, part.slice(2, -2)) : part,
  );
}

// Boş satırla ayrılmış paragrafları <p> öğelerine çevirir.
export function richText(text) {
  return (text || "").split(/\n\s*\n/).map((paragraph) => h("p", {}, inline(paragraph.trim())));
}

export const LEVEL_NAMES = {
  A1: "Başlangıç", A2: "Temel", B1: "Orta", B2: "Orta üstü", C1: "İleri", C2: "Ustalık düzeyi",
};

export const POS_TR = {
  noun: "isim", verb: "fiil", adjective: "sıfat", adverb: "zarf", pronoun: "zamir",
  preposition: "edat", conjunction: "bağlaç", determiner: "belirleyici", article: "tanımlık",
  interjection: "ünlem", numeral: "sayı", "modal verb": "kip fiili", "auxiliary verb": "yardımcı fiil",
  phrase: "kalıp",
};

export const LESSON_KIND_TR = {
  grammar: "Dil bilgisi", vocabulary: "Kelime", reading: "Okuma", listening: "Dinleme", writing: "Yazma",
  speaking: "Konuşma", pronunciation: "Telaffuz", expressions: "Kalıplar",
};

export function levelBadge(level) {
  return h("span", { class: "level", title: LEVEL_NAMES[level] || "" }, level);
}

export function statusBadge(status) {
  if (status === "completed") return h("span", { class: "badge ok" }, "Tamamlandı");
  if (status === "started") return h("span", { class: "badge warn" }, "Devam ediyor");
  return null;
}

export function pageHeader(title, subtitle) {
  return h("div", { class: "page-header" }, h("h1", {}, title), subtitle ? h("p", {}, subtitle) : null);
}

export function lessonLink(lesson) {
  return h(
    "a",
    { class: "list-item", href: `#/ders/${encodeURIComponent(lesson.id)}` },
    h("span", { class: "list-main" },
      h("span", { class: "list-title" }, lesson.title_tr),
      h("span", { class: "list-sub", lang: "en" }, lesson.title_en)),
    h("span", { class: "list-meta" }, statusBadge(lesson.status), levelBadge(lesson.level)),
  );
}
