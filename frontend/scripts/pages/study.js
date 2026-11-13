// Kelime çalışması: kaynak seçimi, çalışma türleri ve gerçek kayıtlardan istatistikler.

import * as api from "../api.js";
import { wordRow } from "../components.js";
import { LEVEL_NAMES, add, h, pageHeader } from "../dom.js";

export const EXERCISES = [
  ["mc_en_tr", "Anlamı seç", "İngilizce kelimenin Türkçe anlamını dört seçenekten seçin."],
  ["mc_tr_en", "Kelimeyi seç", "Türkçe anlamın İngilizce karşılığını seçin."],
  ["typing", "Kelimeyi yaz", "Türkçe anlamı verilen kelimeyi İngilizce yazın."],
  ["cloze", "Boşluk doldurma", "Cümledeki boşluğa gelen kelimeyi seçin."],
  ["matching", "Eşleştirme", "Beş kelimeyi anlamlarıyla eşleştirin."],
  ["antonym", "Zıt anlam", "Kelimenin zıt anlamlısını seçin."],
];

const SOURCE_KEY = "em.study.source";

function loadChoice(defaultLevel) {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(SOURCE_KEY) || "{}");
  } catch { /* yok say */ }
  return { source: saved.source || "level", level: saved.level || defaultLevel || "A1" };
}

function saveChoice(choice) {
  try {
    localStorage.setItem(SOURCE_KEY, JSON.stringify(choice));
  } catch { /* yok say */ }
}

function bars(daily) {
  const max = Math.max(1, ...daily.map((day) => day.answers));
  return h("div", { class: "bars", role: "img",
    "aria-label": "Son 7 günde verilen cevap sayıları: " + daily.map((d) => `${d.date}: ${d.answers}`).join(", ") },
    daily.map((day) => {
      const bar = h("div", { class: "bar" });
      bar.style.height = `${Math.round((day.answers / max) * 100)}%`;
      const label = new Date(`${day.date}T00:00:00Z`).toLocaleDateString("tr-TR", { weekday: "short", timeZone: "UTC" });
      return h("div", { class: "bar-col" }, h("span", { class: "bar-value" }, String(day.answers)),
        h("div", { class: "bar-track" }, bar), h("span", { class: "bar-label" }, label));
    }));
}

export async function render(root) {
  const [profile, stats] = await Promise.all([api.get("/profile"), api.get("/study/stats")]);
  const choice = loadChoice(profile.current_level);
  const links = h("div", {});

  const target = () => `${choice.source}/${choice.source === "level" ? choice.level : "-"}`;
  const paintLinks = () => {
    saveChoice(choice);
    links.replaceChildren(
      h("section", { class: "card" },
        h("h2", {}, "Kelime kartları"),
        h("p", { class: "muted" }, "Kartlar aralıklı tekrar yöntemiyle çalışır: bildiğiniz kelimeler giderek daha seyrek, zorlandıklarınız daha sık sorulur."),
        h("div", { class: "grid" },
          h("a", { class: "card tile", href: `#/calis/kartlar/en_tr/${target()}` },
            h("span", { class: "list-title" }, "İngilizce → Türkçe"),
            h("span", { class: "list-sub" }, "Kelimeyi görünce anlamını hatırlayın.")),
          h("a", { class: "card tile", href: `#/calis/kartlar/tr_en/${target()}` },
            h("span", { class: "list-title" }, "Türkçe → İngilizce"),
            h("span", { class: "list-sub" }, "Anlamı görünce İngilizcesini hatırlayın.")))),
      h("section", { class: "card" },
        h("h2", {}, "Alıştırmalar"),
        h("div", { class: "grid" },
          EXERCISES.map(([type, title, description]) =>
            h("a", { class: "card tile", href: `#/calis/alistirma/${type}/${target()}` },
              h("span", { class: "list-title" }, title), h("span", { class: "list-sub" }, description))))),
    );
  };

  const levelSelect = h("select", { id: "study-level", onchange: () => { choice.level = levelSelect.value; paintLinks(); } },
    Object.keys(LEVEL_NAMES).map((code) => h("option", { value: code, selected: code === choice.level }, code)));
  const sourceSelect = h("select", {
    id: "study-source",
    onchange: () => { choice.source = sourceSelect.value; levelSelect.disabled = choice.source !== "level"; paintLinks(); },
  },
    [["level", "Bir seviyenin kelimeleri"], ["list", "Kelime listem"], ["due", "Daha önce çalıştıklarım"]].map(([value, label]) =>
      h("option", { value, selected: value === choice.source }, label)));
  levelSelect.disabled = choice.source !== "level";

  const en = stats.directions.en_tr;
  const tr = stats.directions.tr_en;
  const accuracy = stats.total_answers ? `%${Math.round((stats.total_correct / stats.total_answers) * 100)}` : "—";

  add(root,
    pageHeader("Kelime çalışması"),
    h("form", { class: "row filters", onsubmit: (event) => event.preventDefault() },
      h("div", { class: "field-inline" }, h("label", { for: "study-source" }, "Hangi kelimeler?"), sourceSelect),
      h("div", { class: "field-inline" }, h("label", { for: "study-level" }, "Seviye"), levelSelect)),
    links,
    h("section", { class: "card", "aria-labelledby": "istatistik-baslik" },
      h("h2", { id: "istatistik-baslik" }, "Kelime istatistikleriniz"),
      stats.studied_words === 0 && stats.total_answers === 0
        ? h("p", { class: "muted" }, "Henüz çalışma kaydınız yok. İlk kart oturumunuzdan sonra istatistikler burada görünecek.")
        : [
            h("div", { class: "grid" },
              h("div", {}, h("p", { class: "stat-label" }, "Çalışılan kelime"), h("p", { class: "stat-value", id: "stat-studied" }, `${stats.studied_words} / ${stats.total_words}`)),
              h("div", {}, h("p", { class: "stat-label" }, "Bu hafta başlanan"), h("p", { class: "stat-value" }, String(stats.started_this_week))),
              h("div", {}, h("p", { class: "stat-label" }, "Tekrar zamanı gelen kart"), h("p", { class: "stat-value", id: "stat-due" }, String(en.due + tr.due))),
              h("div", {}, h("p", { class: "stat-label" }, "Doğru cevap oranı"), h("p", { class: "stat-value" }, accuracy, h("span", { class: "muted small" }, ` (${stats.total_answers} cevap)`)))),
            h("div", { class: "table-wrap" },
              h("table", {},
                h("thead", {}, h("tr", {}, ["Yön", "Öğreniliyor", "İyi öğrenildi", "Uzun süredir biliniyor", "Tekrar zamanı geldi"].map((t) => h("th", { scope: "col" }, t)))),
                h("tbody", {},
                  [["İngilizce → Türkçe", en], ["Türkçe → İngilizce", tr]].map(([label, d]) =>
                    h("tr", {}, h("th", { scope: "row" }, label), [d.learning, d.learned, d.long_term, d.due].map((n) => h("td", {}, String(n)))))))),
            h("p", { class: "muted small" }, `Sık unutulan kart: ${stats.difficult_cards}. "İyi öğrenildi": tekrar aralığı 21 gün ve üzeri; "uzun süredir biliniyor": 60 gün ve üzeri.`),
            h("h3", {}, "Son 7 gün"),
            bars(stats.daily),
            stats.most_missed.length
              ? [h("h3", {}, "En çok yanlış yaptığınız kelimeler"),
                 h("ul", { class: "list" }, stats.most_missed.map((word) => {
                   const row = wordRow({ ...word, in_word_list: undefined });
                   row.querySelector(".list-meta").replaceChildren(h("span", { class: "badge err" }, `${word.wrong_count} yanlış`));
                   return row;
                 }))]
              : null,
          ]),
  );
  paintLinks();
  return "Kelime çalışması";
}
