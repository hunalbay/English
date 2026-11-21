// Uygulama kabuğu: menü, sayfa yönlendirme, tema.
// Menüde yalnızca gerçekten çalışan sayfalar yer alır; yeni modüller
// geliştirildikçe ROUTES listesine eklenir.

import * as api from "./api.js";
import * as license from "./license.js";
import { add, applyTheme, h, pageHeader } from "./dom.js";
import * as home from "./pages/home.js";
import * as lessons from "./pages/lessons.js";
import * as lesson from "./pages/lesson.js";
import * as skill from "./pages/skill.js";
import * as dictionary from "./pages/dictionary.js";
import * as word from "./pages/word.js";
import * as wordList from "./pages/word-list.js";
import * as search from "./pages/search.js";
import * as study from "./pages/study.js";
import * as flashcards from "./pages/flashcards.js";
import * as exercise from "./pages/exercise.js";
import * as tests from "./pages/tests.js";
import * as test from "./pages/test.js";
import * as settings from "./pages/settings.js";
import * as placement from "./pages/placement.js";
import * as progressPage from "./pages/progress.js";
import * as licensePage from "./pages/license.js";
import * as feedback from "./pages/feedback.js";

// pattern: ":ad" parçaları parametre olarak sayfaya aktarılır. nav: menüde gösterilecek ad.
const ROUTES = [
  { pattern: "/", page: home, nav: "Ana Sayfa", section: "/" },
  { pattern: "/dersler", page: lessons, nav: "Dersler", section: "/dersler" },
  { pattern: "/dersler/:level", page: lessons, section: "/dersler" },
  { pattern: "/ders/:id", page: lesson, section: "/dersler" },
  { pattern: "/okuma", page: skill, nav: "Okuma", section: "/okuma", extra: { track: "reading" } },
  { pattern: "/okuma/:level", page: skill, section: "/okuma", extra: { track: "reading" } },
  { pattern: "/dinleme", page: skill, nav: "Dinleme", section: "/dinleme", extra: { track: "listening" } },
  { pattern: "/dinleme/:level", page: skill, section: "/dinleme", extra: { track: "listening" } },
  { pattern: "/yazma", page: skill, nav: "Yazma", section: "/yazma", extra: { track: "writing" } },
  { pattern: "/yazma/:level", page: skill, section: "/yazma", extra: { track: "writing" } },
  { pattern: "/telaffuz", page: skill, nav: "Telaffuz", section: "/telaffuz", extra: { track: "pronunciation" } },
  { pattern: "/telaffuz/:level", page: skill, section: "/telaffuz", extra: { track: "pronunciation" } },
  { pattern: "/deyimler", page: skill, nav: "Deyimler ve kalıplar", section: "/deyimler", extra: { track: "expressions" } },
  { pattern: "/deyimler/:level", page: skill, section: "/deyimler", extra: { track: "expressions" } },
  { pattern: "/mesleki", page: skill, nav: "Mesleki İngilizce", section: "/mesleki", extra: { track: "professional" } },
  { pattern: "/mesleki/:level", page: skill, section: "/mesleki", extra: { track: "professional" } },
  { pattern: "/sozluk", page: dictionary, nav: "Sözlük", section: "/sozluk" },
  { pattern: "/kelime/:id", page: word, section: "/sozluk" },
  { pattern: "/calis", page: study, nav: "Kelime çalışması", section: "/calis" },
  { pattern: "/calis/kartlar/:direction/:source/:level", page: flashcards, section: "/calis" },
  { pattern: "/calis/alistirma/:type/:source/:level", page: exercise, section: "/calis" },
  { pattern: "/testler", page: tests, nav: "Testler", section: "/testler" },
  { pattern: "/testler/:level", page: tests, section: "/testler" },
  { pattern: "/test/ders/:lessonId", page: test, section: "/testler" },
  { pattern: "/test/ders/:lessonId/:run", page: test, section: "/testler" },
  { pattern: "/test/seviye/:level", page: test, section: "/testler" },
  { pattern: "/kelimelerim", page: wordList, nav: "Kelimelerim", section: "/kelimelerim" },
  { pattern: "/ilerleme", page: progressPage, nav: "İlerleme", section: "/ilerleme" },
  { pattern: "/seviye-tespiti", page: placement, nav: "Seviye tespiti", section: "/seviye-tespiti" },
  { pattern: "/ara/:query", page: search, section: null },
  { pattern: "/ayarlar", page: settings, nav: "Ayarlar", section: "/ayarlar" },
  { pattern: "/geri-bildirim", page: feedback, nav: "Geri bildirim", section: "/geri-bildirim", open: true },
  // Lisans sayfası menüde yalnızca lisans yokken görünür; lisans varken Ayarlar'dan açılır.
  { pattern: "/lisans", page: licensePage, navLocked: "Lisans", section: "/lisans", open: true },
];
const LICENSE_ROUTE = ROUTES.find((route) => route.pattern === "/lisans");

const main = document.getElementById("main");
const nav = document.getElementById("nav");
let renderToken = 0;

function match(path) {
  const parts = path.split("/").filter(Boolean);
  for (const route of ROUTES) {
    const expected = route.pattern.split("/").filter(Boolean);
    if (expected.length !== parts.length) continue;
    const params = {};
    let ok = true;
    expected.forEach((segment, index) => {
      if (segment.startsWith(":")) {
        try {
          params[segment.slice(1)] = decodeURIComponent(parts[index]);
        } catch {
          ok = false;
        }
      } else if (segment !== parts[index]) ok = false;
    });
    if (ok) return { route, params: { ...params, ...(route.extra || {}) } };
  }
  return null;
}

function isLocked() {
  const status = license.status();
  return Boolean(status && !status.licensed);
}

function renderNav(section) {
  const locked = isLocked();
  const items = ROUTES.map((route) => ({ route, label: locked ? (route.open && (route.navLocked || route.nav)) : route.nav }))
    .filter((item) => item.label);
  nav.replaceChildren(
    ...items.map(({ route, label }) =>
      h("a", { href: `#${route.pattern}`, "aria-current": route.section === section ? "page" : null }, label),
    ),
  );
  document.getElementById("search-form").hidden = locked;
}

function expiryBanner() {
  const status = license.status();
  if (!status || !status.licensed || !status.warn) return null;
  const when = status.days_left === 0 ? "bugün sona eriyor" : `${license.formatDate(status.expires)} tarihinde sona eriyor (${status.days_left} gün kaldı)`;
  return h("p", { class: "notice license-banner", role: "status" },
    `Lisansınız ${when}. `, h("a", { href: "#/lisans" }, "Lisansı yenile"));
}

async function render() {
  const token = ++renderToken;
  const path = location.hash.replace(/^#/, "") || "/";
  let found = match(path);
  // Lisans yoksa yalnızca lisans ve geri bildirim sayfaları açılır.
  if (isLocked() && !(found && found.route.open)) found = { route: LICENSE_ROUTE, params: {} };
  renderNav(found ? found.route.section : null);
  const root = document.createElement("div");
  if (!found) {
    document.title = "Sayfa bulunamadı · English Master";
    add(root, pageHeader("Sayfa bulunamadı"), h("p", {}, "Aradığınız sayfa yok. ", h("a", { href: "#/" }, "Ana sayfaya dön")));
  } else {
    try {
      const title = await found.route.page.render(root, found.params);
      document.title = `${title || found.route.nav || "English Master"} · English Master`;
    } catch (error) {
      root.replaceChildren(
        pageHeader(error.status === 404 ? "Bulunamadı" : "Sayfa yüklenemedi"),
        h("p", { class: "notice error", role: "alert" }, error.message || "Beklenmeyen bir hata oluştu."),
        h("p", {}, h("a", { href: "#/" }, "Ana sayfaya dön")),
      );
    }
  }
  if (token !== renderToken) return; // bu arada başka bir sayfaya geçildi
  if (found && found.route !== LICENSE_ROUTE) {
    const banner = expiryBanner();
    if (banner) root.prepend(banner);
  }
  if (root.dataset.section) renderNav(root.dataset.section);
  main.replaceChildren(root);
  main.dataset.route = path; // sayfanın tamamen çizildiğini gösterir (testler bunu bekler)
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", () => {
  render().then(() => main.focus({ preventScroll: true }));
});

// "İçeriğe geç": adres çubuğundaki # yönlendirme için kullanıldığından bağlantı adresi değiştirmez,
// yalnızca odağı sayfa içeriğine taşır.
document.querySelector(".skip-link").addEventListener("click", (event) => {
  event.preventDefault();
  main.focus();
});

document.getElementById("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("search-input");
  const query = input.value.trim();
  if (query) location.hash = `#/ara/${encodeURIComponent(query)}`;
});

// Program açıkken lisans süresi dolarsa (ya da kilitli bir uca istek giderse) lisans ekranına dönülür.
let relocking = false;
window.addEventListener("em:license-required", async () => {
  if (relocking) return;
  relocking = true;
  try {
    await license.refresh();
  } catch {
    /* durum alınamadı; mevcut sayfa hatayı gösterir */
  }
  relocking = false;
  render();
});

api.get("/settings").then((data) => applyTheme(data.settings.theme)).catch(() => {});
license.refresh().catch(() => {}).finally(render);
