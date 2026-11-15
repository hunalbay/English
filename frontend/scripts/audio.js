// Ses bileşenleri: hazır kayıtları çalma, sistem sesine geçiş ve mikrofon kaydı.
// Mikrofon izni yalnızca kullanıcı "Kaydet" düğmesine bastığında istenir. Kayıtlar yalnızca
// tarayıcı belleğinde tutulur; sunucuya ya da başka bir yere gönderilmez, diske yazılmaz.

import { h, toast } from "./dom.js";

let current = null; // aynı anda tek ses çalsın

function play(url) {
  if (current) current.pause();
  current = new Audio(url);
  current.play().catch(() => toast("Ses çalınamadı.", { error: true }));
  return current;
}

function systemVoiceAvailable() {
  return typeof window.speechSynthesis !== "undefined" && typeof window.SpeechSynthesisUtterance !== "undefined";
}

function speakWithSystemVoice(text) {
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.9;
  window.speechSynthesis.speak(utterance);
}

// Kısa bir sözcük ya da cümle için "Dinle" düğmesi.
// Hazır kayıt yoksa bunu açıkça belirtir ve (varsa) bilgisayarın kendi sesini seçenek olarak sunar.
export function listenButton(audio, text, { label = "Dinle" } = {}) {
  if (audio && audio.url) {
    return h("button", { class: "btn small listen", type: "button", "aria-label": `${label}: ${text}`,
      onclick: () => play(audio.url) }, "▶ ", label);
  }
  if (systemVoiceAvailable()) {
    return h("button", { class: "btn small listen fallback", type: "button",
      title: "Bu içerik için hazır kayıt yok. Bilgisayarınızın kendi sesi kullanılır; kalite sisteminize göre değişir.",
      "aria-label": `Sistem sesiyle dinle: ${text}`,
      onclick: () => speakWithSystemVoice(text) }, "▶ Sistem sesiyle dinle");
  }
  return h("span", { class: "muted small audio-missing" }, "Bu içerik için ses dosyası yok.");
}

// Uzun kayıtlar için oynatıcı: hız seçimi vardır. Kayıt yoksa uyarı gösterir.
export function audioPlayer(audio, { fallbackText = "" } = {}) {
  if (!audio || !audio.url) {
    return h("div", { class: "notice audio-missing", role: "status" },
      h("strong", {}, "Bu içerik için ses dosyası bulunamadı. "),
      "Kayıt bu kurulumda yer almıyor. Metni okuyarak çalışabilirsiniz.",
      fallbackText && systemVoiceAvailable()
        ? h("p", {}, h("button", { class: "btn small", type: "button", onclick: () => speakWithSystemVoice(fallbackText) },
            "▶ Sistem sesiyle dinle"),
            h("span", { class: "muted small" }, " Bilgisayarınızın kendi sesi kullanılır; kalite değişebilir."))
        : null);
  }
  const element = h("audio", { controls: true, preload: "none", src: audio.url, class: "player" });
  const speed = h("select", { "aria-label": "Çalma hızı", class: "speed" },
    [["0.75", "Yavaş (0,75×)"], ["1", "Normal hız"], ["1.25", "Hızlı (1,25×)"]].map(([value, text]) =>
      h("option", { value, selected: value === "1" }, text)));
  speed.addEventListener("change", () => { element.playbackRate = Number(speed.value); });
  element.addEventListener("play", () => {
    if (current && current !== element) current.pause();
    current = element;
    element.playbackRate = Number(speed.value);
  });
  const seconds = Math.round((audio.duration_ms || 0) / 1000);
  return h("div", { class: "audio-box" }, element,
    h("div", { class: "row" }, speed,
      seconds ? h("span", { class: "muted small" }, `Süre: ${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`) : null));
}

const MIC_ERRORS = {
  NotAllowedError: "Mikrofon izni verilmedi. Kayıt yapmak için tarayıcının izin isteğini kabul etmelisiniz.",
  NotFoundError: "Mikrofon bulunamadı. Bir mikrofon bağlayıp yeniden deneyin.",
  NotReadableError: "Mikrofon başka bir uygulama tarafından kullanılıyor olabilir.",
};

// Kendi sesini kaydedip dinleme. Otomatik puanlama yoktur.
export function recorder(label) {
  const supported = Boolean(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  if (!supported) {
    return h("span", { class: "muted small" }, "Bu tarayıcı ses kaydını desteklemiyor.");
  }
  const button = h("button", { class: "btn small record", type: "button", "aria-label": `Sesimi kaydet: ${label}` }, "● Kaydet");
  const playback = h("button", { class: "btn small", type: "button", hidden: true }, "▶ Kaydımı dinle");
  const status = h("span", { class: "muted small", "aria-live": "polite" });
  let media = null;
  let stream = null;
  let url = null;
  let timer = null;

  const stop = () => {
    clearTimeout(timer);
    if (media && media.state !== "inactive") media.stop();
  };
  button.addEventListener("click", async () => {
    if (media && media.state === "recording") { stop(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      status.textContent = MIC_ERRORS[error.name] || "Mikrofona erişilemedi.";
      return;
    }
    const chunks = [];
    media = new MediaRecorder(stream);
    media.addEventListener("dataavailable", (event) => { if (event.data.size) chunks.push(event.data); });
    media.addEventListener("stop", () => {
      stream.getTracks().forEach((track) => track.stop()); // mikrofonu hemen bırak
      if (url) URL.revokeObjectURL(url);
      url = URL.createObjectURL(new Blob(chunks, { type: media.mimeType }));
      button.textContent = "● Yeniden kaydet";
      button.classList.remove("recording");
      playback.hidden = false;
      status.textContent = "Kayıt hazır. Örnek sesle karşılaştırın.";
    });
    media.start();
    button.textContent = "■ Durdur";
    button.classList.add("recording");
    status.textContent = "Kaydediliyor…";
    timer = setTimeout(stop, 15000); // en çok 15 saniye
  });
  playback.addEventListener("click", () => { if (url) play(url); });
  return h("span", { class: "row recorder" }, button, playback, status);
}
