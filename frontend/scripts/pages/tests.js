// Testler: seviyeye ve derse göre test başlatma, zayıf konular, test geçmişi.

import * as api from "../api.js";
import { LEVEL_NAMES, add, h, pageHeader } from "../dom.js";

function accuracyBadge(stats) {
  if (!stats) return h("span", { class: "muted small" }, "henüz çözülmedi");
  const kind = stats.accuracy >= 70 ? "ok" : stats.accuracy >= 40 ? "warn" : "err";
  return h("span", { class: `badge ${kind}` }, `%${stats.accuracy} doğru`);
}

function historyRow(item) {
  const title = item.lesson ? item.lesson.title_tr : item.level ? `${item.level} karışık test` : "Karışık test";
  const date = new Date(item.started_at).toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
  const extra = [
    item.partial ? `${item.partial} kısmen` : null,
    item.ungraded ? `${item.ungraded} değerlendirilmedi` : null,
    item.finished ? null : "yarıda bırakıldı",
  ].filter(Boolean).join(" · ");
  return h("li", { class: "list-item" },
    h("span", { class: "list-main" }, h("span", { class: "list-title" }, title),
      h("span", { class: "list-sub" }, date, extra ? ` · ${extra}` : "")),
    h("span", { class: "list-meta" }, h("span", { class: "badge ok" }, `${item.correct} doğru`),
      h("span", { class: "badge err" }, `${item.incorrect} yanlış`), h("span", { class: "muted small" }, `/ ${item.total}`)));
}

export async function render(root, params) {
  const [data, profile] = await Promise.all([api.get("/tests/overview"), api.get("/profile")]);
  const requested = (params.level || "").toUpperCase();
  const current = data.levels.find((level) => level.code === requested)
    || data.levels.find((level) => level.code === profile.current_level)
    || data.levels[0];

  add(root,
    pageHeader("Testler", "Her soruda cevabınızın neden doğru ya da yanlış olduğu açıklanır ve ilgili derse geçebilirsiniz."),
    data.weak_topics.length
      ? h("section", { class: "card", id: "weak-topics" },
          h("h2", {}, "En çok hata yaptığınız konular"),
          h("ul", { class: "list" }, data.weak_topics.map((topic) =>
            h("li", { class: "list-item" },
              h("a", { class: "list-main", href: `#/ders/${encodeURIComponent(topic.id)}` },
                h("span", { class: "list-title" }, topic.title_tr),
                h("span", { class: "list-sub" }, `${topic.correct} doğru · ${topic.incorrect} yanlış`)),
              h("span", { class: "list-meta" }, accuracyBadge(topic),
                h("a", { class: "btn small", href: `#/test/ders/${encodeURIComponent(topic.id)}` }, "Tekrar çöz"))))))
      : null,
    h("nav", { class: "tabs", "aria-label": "Seviyeler" },
      data.levels.map((level) =>
        h("a", { href: `#/testler/${level.code}`, "aria-current": level.code === current.code ? "page" : null },
          level.code, h("span", { class: "tab-sub" }, ` ${level.question_count} soru`)))),
  );

  if (current.question_count === 0) {
    add(root, h("p", { class: "notice" }, `${current.code} seviyesi için sorular henüz eklenmedi.`));
  } else {
    add(root,
      h("section", { class: "card" },
        h("div", { class: "row spread" },
          h("div", {}, h("h2", {}, `${current.code} — ${LEVEL_NAMES[current.code]}`),
            h("p", { class: "muted" }, `${current.lessons.length} konuda ${current.question_count} soru`)),
          h("a", { class: "btn primary", href: `#/test/seviye/${current.code}` }, `${current.code} karışık test (10 soru)`)),
        h("ul", { class: "list" }, current.lessons.map((lesson) =>
          h("li", { class: "list-item" },
            h("a", { class: "list-main", href: `#/ders/${encodeURIComponent(lesson.id)}` },
              h("span", { class: "list-title" }, lesson.title_tr),
              h("span", { class: "list-sub" }, h("span", { lang: "en" }, lesson.title_en), ` · ${lesson.question_count} soru`)),
            h("span", { class: "list-meta" }, accuracyBadge(lesson.stats),
              h("a", { class: "btn small", href: `#/test/ders/${encodeURIComponent(lesson.id)}`,
                "aria-label": `${lesson.title_tr}: konu testi` }, "Konu testi")))))));
  }

  add(root,
    h("section", { class: "card", id: "test-history" },
      h("h2", {}, "Son testleriniz"),
      data.history.length
        ? h("ul", { class: "list" }, data.history.map(historyRow))
        : h("p", { class: "muted" }, "Henüz test çözmediniz.")));
  return "Testler";
}
