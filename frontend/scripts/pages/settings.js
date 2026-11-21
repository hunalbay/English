// Ayarlar sayfası: seviye, tema, programı kapatma.
// Not: "günlük hedef (dakika)" ayarı program çalışma süresini ölçmediği için arayüzden kaldırıldı;
// kayıtlı değer korunur ve süre ölçümü eklenirse yeniden gösterilebilir.

import * as api from "../api.js";
import { LEVEL_NAMES, add, applyTheme, h, toast } from "../dom.js";

const THEMES = [
  ["system", "Sistem"],
  ["light", "Açık"],
  ["dark", "Koyu"],
];

async function save(key, value) {
  try {
    const result = await api.put(`/settings/${key}`, { value });
    toast("Ayar kaydedildi.");
    return result.value;
  } catch (error) {
    toast(error.message, { error: true });
    return null;
  }
}

export async function render(root) {
  const [{ settings }, profile, health] = await Promise.all([
    api.get("/settings"), api.get("/profile"), api.get("/health"),
  ]);

  const levelSelect = h("select", {
    id: "level",
    onchange: async () => {
      if (!levelSelect.value) return;
      try {
        await api.put("/profile/level", { level: levelSelect.value });
        toast("Seviyeniz güncellendi. Önceki kayıtlarınız korunuyor.");
      } catch (error) {
        toast(error.message, { error: true });
      }
    },
  },
    profile.current_level ? null : h("option", { value: "" }, "Seçilmedi"),
    Object.entries(LEVEL_NAMES).map(([code, name]) =>
      h("option", { value: code, selected: profile.current_level === code }, `${code} — ${name}`)));
  const levelField = h("div", { class: "field" },
    h("label", { for: "level" }, "Seviyeniz"), levelSelect,
    h("p", { class: "hint" }, "Seviyenizi değiştirdiğinizde ders ve kelime kayıtlarınız silinmez."));

  const themeField = h(
    "fieldset",
    { class: "field" },
    h("legend", {}, "Görünüm"),
    h(
      "div",
      { class: "segmented" },
      THEMES.map(([value, label]) =>
        h(
          "label",
          {},
          h("input", {
            type: "radio",
            name: "theme",
            value,
            checked: settings.theme === value,
            onchange: async () => {
              const saved = await save("theme", value);
              if (saved) applyTheme(saved);
            },
          }),
          h("span", {}, label),
        ),
      ),
    ),
  );

  const quitButton = h(
    "button",
    {
      class: "btn danger",
      type: "button",
      onclick: async () => {
        quitButton.disabled = true;
        try {
          await api.post("/system/shutdown");
          root.replaceChildren(
            h("div", { class: "page-header" }, h("h1", {}, "English Master kapatıldı")),
            h("p", {}, "İlerlemeniz kaydedildi. Bu sekmeyi kapatabilirsiniz."),
          );
        } catch (error) {
          quitButton.disabled = false;
          toast(error.message, { error: true });
        }
      },
    },
    "Programı kapat",
  );

  add(root, 
    h("div", { class: "page-header" }, h("h1", {}, "Ayarlar")),
    h("section", { class: "card" }, levelField, themeField),
    h(
      "section",
      { class: "card" },
      h("h2", {}, "Programı kapat"),
      h("p", { class: "muted" }, "Tarayıcı sekmesini kapatmak programı kapatmaz. Programı tamamen kapatmak için bu düğmeyi kullanın."),
      quitButton,
    ),
    h(
      "section",
      { class: "card" },
      h("h2", {}, "Program hakkında"),
      h("p", { class: "muted", id: "about" },
        `Program sürümü ${health.version} · `,
        health.content.available ? `İçerik sürümü ${health.content.version}` : "Eğitim içeriği bulunamadı",
        ` · Veri şeması ${health.user_db.schema_revision}`),
      h("p", { class: "muted" }, "Verileriniz yalnızca bu bilgisayarda saklanır. Program hiçbir kullanım verisi toplamaz veya göndermez."),
    ),
  );
  return "Ayarlar";
}
