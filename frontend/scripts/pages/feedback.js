// Geri bildirim: program hiçbir şeyi kendisi göndermez. Metin kullanıcının e-posta
// programında açılır ya da panoya kopyalanır; ne gönderileceğini kullanıcı görür.

import * as api from "../api.js";
import { copyText } from "../license.js";
import { add, h, pageHeader, toast } from "../dom.js";

const TOPICS = ["Hata bildirimi", "Öneri", "İçerik hatası (yanlış cevap, çeviri, ses)", "Diğer"];
const MAILTO_LIMIT = 1800; // e-posta programlarının bağlantı uzunluğu sınırı için

export async function render(root) {
  const info = await api.get("/feedback");
  const topic = h("select", { id: "fb-topic" }, TOPICS.map((name) => h("option", { value: name }, name)));
  const message = h("textarea", { id: "fb-message", rows: "8", maxlength: "4000", "aria-describedby": "fb-message-hint" });
  const include = h("input", { type: "checkbox", id: "fb-include", checked: true });
  const preview = h("pre", { class: "diagnostics", id: "fb-diagnostics" },
    Object.entries(info.diagnostics).map(([key, value]) => `${key}: ${value}`).join("\n"));

  const body = () => {
    let text = message.value.trim();
    if (include.checked) text += `\n\n--- Program bilgileri ---\n${preview.textContent}`;
    return text;
  };
  const subject = () => `English Master geri bildirim: ${topic.value}`;
  const ready = () => {
    if (message.value.trim()) return true;
    toast("Lütfen önce mesajınızı yazın.", { error: true });
    message.focus();
    return false;
  };

  const mailButton = h("button", {
    class: "btn primary", type: "button",
    onclick: () => {
      if (!ready()) return;
      let text = body();
      if (text.length > MAILTO_LIMIT) {
        text = text.slice(0, MAILTO_LIMIT) + "\n[Metin uzun olduğu için kısaltıldı; tamamını 'Metni kopyala' ile yapıştırın.]";
      }
      location.href = `mailto:${info.email}?subject=${encodeURIComponent(subject())}&body=${encodeURIComponent(text)}`;
    },
  }, "E-posta programında aç");
  const copyButton = h("button", {
    class: "btn", type: "button",
    onclick: async () => {
      if (!ready()) return;
      const ok = await copyText(`Kime: ${info.email}\nKonu: ${subject()}\n\n${body()}`);
      toast(ok ? `Metin kopyalandı. ${info.email} adresine e-postayla gönderebilirsiniz.` : "Kopyalanamadı; metni seçip Ctrl+C ile kopyalayın.",
        { error: !ok });
    },
  }, "Metni kopyala");
  include.addEventListener("change", () => { preview.hidden = !include.checked; });

  add(root,
    pageHeader("Geri bildirim", "Deneme sürümünü geliştirmemize yardım ettiğiniz için teşekkürler."),
    h("form", { class: "card", onsubmit: (event) => event.preventDefault() },
      h("div", { class: "field" }, h("label", { for: "fb-topic" }, "Konu"), topic),
      h("div", { class: "field wide" },
        h("label", { for: "fb-message" }, "Mesajınız"), message,
        h("p", { class: "hint", id: "fb-message-hint" }, "Hata bildiriyorsanız hangi sayfada ne yaptığınızı ve ne olduğunu yazın.")),
      h("div", { class: "field wide" },
        h("label", { class: "checkbox" }, include, " Program bilgilerini ekle"),
        preview,
        h("p", { class: "hint" }, "Eklenecek bilgilerin tamamı yukarıda görünüyor. Cevaplarınız, notlarınız veya ses kayıtlarınız eklenmez.")),
      h("div", { class: "row" }, mailButton, copyButton)),
    h("p", { class: "hint" },
      "Program hiçbir şeyi kendiliğinden göndermez. \"E-posta programında aç\" bilgisayarınızdaki e-posta uygulamasını açar; ",
      "e-posta uygulamanız yoksa metni kopyalayıp ", h("strong", {}, info.email), " adresine kendiniz gönderebilirsiniz."));
  return "Geri bildirim";
}
