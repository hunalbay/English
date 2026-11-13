// Ana sayfa. Aşama 1'de yalnızca gerçek sistem durumunu gösterir;
// öğrenme modülleri geliştirildikçe buraya eklenecektir.

import * as api from "../api.js";
import { h } from "../dom.js";

function stat(label, value, badge) {
  return h(
    "div",
    { class: "card" },
    h("p", { class: "stat-label" }, label),
    h("p", { class: "stat-value" }, value, badge ? " " : null, badge || null),
  );
}

function formatDate(iso) {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString("tr-TR");
}

export async function render(root) {
  const health = await api.get("/health");
  const content = health.content;

  root.append(
    h(
      "div",
      { class: "page-header" },
      h("h1", {}, "English Master"),
      h("p", {}, "A1'den C2'ye İngilizce öğrenmek için ücretsiz ve çevrimdışı çalışan eğitim programı."),
    ),
    h(
      "section",
      { "aria-labelledby": "durum-baslik" },
      h("h2", { id: "durum-baslik" }, "Program durumu"),
      h(
        "div",
        { class: "grid" },
        stat("Program sürümü", health.version),
        stat(
          "Eğitim içeriği",
          content.available ? `Sürüm ${content.version}` : "Bulunamadı",
          h("span", { class: `badge ${content.available ? "ok" : "err"}` }, content.available ? "Hazır" : "Eksik"),
        ),
        stat(
          "Kişisel verileriniz",
          "Bu bilgisayarda saklanıyor",
          h("span", { class: "badge ok" }, `Şema ${health.user_db.schema_revision}`),
        ),
      ),
      content.available
        ? h("p", { class: "muted", id: "content-built" }, `İçerik derleme tarihi: ${formatDate(content.built_at)}`)
        : h(
            "p",
            { class: "notice error", role: "alert" },
            "Eğitim içeriği dosyası (content.db) bulunamadı. Programı yeniden kurmayı deneyin.",
          ),
    ),
    h(
      "section",
      { class: "card", "aria-labelledby": "gelistirme-baslik" },
      h("h2", { id: "gelistirme-baslik" }, "Geliştirme sürümü"),
      h(
        "p",
        {},
        "Bu sürüm programın altyapısını içerir. Dersler, kelime kartları, testler ve diğer öğrenme " +
          "modülleri henüz eklenmedi; hazır oldukça menüde görünecekler.",
      ),
    ),
  );
}
