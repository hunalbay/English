// Ana sayfa: ilk açılışta seviye seçimi, sonrasında gerçek ilerleme özeti.

import * as api from "../api.js";
import { LEVEL_NAMES, add, h, lessonLink, levelBadge, pageHeader, toast } from "../dom.js";

function progressBar(completed, total) {
  const percent = total ? Math.round((completed / total) * 100) : 0;
  const fill = h("div", { class: "progress-fill" });
  fill.style.width = `${percent}%`; // CSSOM üzerinden; satır içi style özniteliği CSP tarafından engellenir
  return h("div", { class: "progress", role: "img", "aria-label": `${total} dersten ${completed} tanesi tamamlandı` }, fill);
}

function stat(label, value, link) {
  return h("div", { class: "card" },
    h("p", { class: "stat-label" }, label),
    h("p", { class: "stat-value" }, value),
    link || null);
}

async function renderOnboarding(root) {
  const { levels } = await api.get("/levels");
  add(root, 
    pageHeader("English Master'a hoş geldiniz",
      "Başlamak için seviyenizi seçin. Seviyenizi istediğiniz zaman Ayarlar'dan değiştirebilirsiniz; kayıtlarınız silinmez."),
    h("section", { "aria-labelledby": "seviye-baslik" },
      h("h2", { id: "seviye-baslik" }, "Seviyemi biliyorum"),
      h("div", { class: "grid" },
        levels.map((level) =>
          h("button", {
            class: "card level-card", type: "button",
            onclick: async () => {
              try {
                await api.put("/profile/level", { level: level.code });
                root.replaceChildren();
                await render(root);
              } catch (error) {
                toast(error.message, { error: true });
              }
            },
          },
            h("span", { class: "level-code" }, level.code),
            h("span", { class: "list-title" }, level.name_tr),
            h("span", { class: "list-sub" }, level.description_tr)))),
    ),
    h("section", { class: "card", "aria-labelledby": "tespit-baslik" },
      h("h2", { id: "tespit-baslik" }, "Seviyemi bilmiyorum"),
      h("p", { class: "muted" },
        "Seviye tespit sınavı henüz hazır değil; ilerleyen bir sürümde eklenecek. Şimdilik emin değilseniz " +
        "A1 ile başlayıp dersler kolay gelirse seviyenizi yükseltebilirsiniz.")),
  );
}

export async function render(root) {
  const [data, stats] = await Promise.all([api.get("/dashboard"), api.get("/study/stats")]);
  if (!data.profile.current_level) {
    await renderOnboarding(root);
    return "Hoş geldiniz";
  }

  const level = data.profile.current_level;
  const progress = data.level_progress;
  const resume = data.continue_lesson || data.next_lesson;

  add(root, 
    pageHeader("Ana Sayfa"),
    h("section", { class: "card", "aria-labelledby": "devam-baslik" },
      h("h2", { id: "devam-baslik" }, data.continue_lesson ? "Öğrenmeye devam et" : "Sıradaki ders"),
      resume
        ? h("div", { class: "list" }, lessonLink({ ...resume, status: data.continue_lesson ? "started" : null }))
        : h("p", { class: "muted" },
            progress.total === 0
              ? `${level} seviyesi için dersler henüz eklenmedi.`
              : `${level} seviyesindeki tüm dersleri açtınız. Dersler sayfasından tekrar edebilirsiniz.`)),
    h("div", { class: "grid" },
      h("div", { class: "card" },
        h("p", { class: "stat-label" }, "Seviyeniz"),
        h("p", { class: "stat-value" }, levelBadge(level), " ", LEVEL_NAMES[level]),
        progressBar(progress.completed, progress.total),
        h("p", { class: "muted small" }, `${progress.total} dersten ${progress.completed} tanesi tamamlandı`),
        h("a", { href: `#/dersler/${level}` }, "Dersleri gör")),
      stat("Tamamladığınız dersler", String(data.completed_lessons), h("a", { href: "#/dersler" }, "Tüm seviyeler")),
      stat("Tekrar zamanı gelen kart", String(stats.directions.en_tr.due + stats.directions.tr_en.due),
        h("a", { href: "#/calis" }, "Kelime çalışması")),
      stat("Kelime listeniz", `${data.word_list_count} kelime`, h("a", { href: "#/kelimelerim" }, "Kelimelerim")),
      stat("Sözlük", `${data.totals.words} kelime`, h("a", { href: "#/sozluk" }, "Sözlüğü aç")),
    ),
    h("section", { class: "card" },
      h("h2", {}, "Geliştirme sürümü"),
      h("p", { class: "muted" },
        `Bu sürümde ${data.totals.lessons} ders, ${data.totals.questions} soru ve ${data.totals.words} kelime bulunuyor. Okuma, ` +
        "dinleme, yazma ve diğer modüller henüz eklenmedi; hazır oldukça menüde görünecekler.")),
  );
  return "Ana Sayfa";
}
