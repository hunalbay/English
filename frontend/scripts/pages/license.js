// Lisans sayfası: bilgisayar kodu, anahtar girişi, lisans bilgisi.
// Doğrulama tamamen bu bilgisayarda yapılır; internet bağlantısı gerekmez.

import * as api from "../api.js";
import * as license from "../license.js";
import { add, h, pageHeader, toast } from "../dom.js";

function codeBox(code) {
  const value = h("code", { class: "machine-code", id: "machine-code" }, code);
  const button = h("button", {
    class: "btn",
    type: "button",
    onclick: async () => {
      if (await license.copyText(code)) toast("Bilgisayar kodu kopyalandı.");
      else {
        const range = document.createRange();
        range.selectNodeContents(value);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
        toast("Kod seçildi; Ctrl+C ile kopyalayın.");
      }
    },
  }, "Kodu kopyala");
  return h("div", { class: "row" }, value, button);
}

function statusCard(status) {
  if (status.licensed) {
    const days = status.days_left === 0 ? "bugün son gün" : `${status.days_left} gün kaldı`;
    return h("section", { class: "card", "aria-labelledby": "license-state" },
      h("h2", { id: "license-state" }, "Lisans geçerli"),
      h("dl", { class: "facts" },
        h("dt", {}, "Lisans sahibi"), h("dd", {}, status.name),
        h("dt", {}, "Bitiş tarihi"), h("dd", {}, `${license.formatDate(status.expires)} (${days})`)),
      status.warn ? h("p", { class: "notice" },
        "Lisansınızın süresi yakında doluyor. Yenilemek için aşağıdaki bilgisayar kodunu ",
        h("strong", {}, status.contact_email), " adresine gönderin.") : null);
  }
  return h("p", { class: "notice error", role: "alert", id: "license-message" }, status.message);
}

export async function render(root) {
  const status = await license.refresh();
  const input = h("textarea", {
    id: "license-key", rows: "4", maxlength: "2200", spellcheck: "false", autocomplete: "off",
    "aria-describedby": "license-key-hint",
  });
  const submit = h("button", { class: "btn primary", type: "submit" }, status.licensed ? "Yeni anahtarı kaydet" : "Lisansı etkinleştir");
  const form = h("form", {
    class: "card",
    onsubmit: async (event) => {
      event.preventDefault();
      const key = input.value.trim();
      if (!key) { toast("Lütfen lisans anahtarını yapıştırın.", { error: true }); input.focus(); return; }
      submit.disabled = true;
      try {
        const result = await api.post("/license", { key });
        license.set(result);
        toast(`Lisans etkinleştirildi. ${license.formatDate(result.expires)} tarihine kadar geçerli.`);
        location.hash = "#/";
        window.dispatchEvent(new Event("hashchange"));
      } catch (error) {
        toast(error.message, { error: true });
        input.focus();
      } finally {
        submit.disabled = false;
      }
    },
  },
    h("h2", {}, status.licensed ? "Lisansı yenile" : "Lisans anahtarını girin"),
    h("div", { class: "field wide" },
      h("label", { for: "license-key" }, "Lisans anahtarı"),
      input,
      h("p", { class: "hint", id: "license-key-hint" }, "Size gönderilen ve EM1. ile başlayan anahtarın tamamını yapıştırın.")),
    submit);

  add(root,
    pageHeader("Lisans", "English Master şu an davetle verilen ücretsiz deneme sürümüdür."),
    statusCard(status),
    h("section", { class: "card", "aria-labelledby": "machine-heading" },
      h("h2", { id: "machine-heading" }, "Bu bilgisayarın kodu"),
      codeBox(status.machine_code),
      h("p", {}, status.licensed ? "Lisansı yenilemek için" : "Lisans anahtarı almak için",
        " bu kodu ", h("strong", {}, status.contact_email), " adresine gönderin. ",
        "Size yalnızca bu bilgisayarda çalışan bir anahtar gönderilir."),
      h("p", { class: "hint" },
        "Kod, bilgisayarınızın kimliğinden türetilir ve geri çevrilemez. Program bu kodu ya da başka bir bilgiyi ",
        "hiçbir yere göndermez; lisans denetimi internet bağlantısı olmadan bu bilgisayarda yapılır.")),
    form,
    h("p", {}, h("a", { href: "#/geri-bildirim" }, "Sorun mu yaşıyorsunuz? Geri bildirim gönderin")));
  return "Lisans";
}
