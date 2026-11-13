// Uygulama kabuğu: menü, sayfa yönlendirme, tema.
// Menüde yalnızca gerçekten çalışan sayfalar yer alır; yeni modüller
// geliştirildikçe ROUTES listesine eklenir.

import * as api from "./api.js";
import { add, applyTheme, h, pageHeader } from "./dom.js";
import * as home from "./pages/home.js";
import * as lessons from "./pages/lessons.js";
import * as lesson from "./pages/lesson.js";
import * as dictionary from "./pages/dictionary.js";
import * as word from "./pages/word.js";
import * as wordList from "./pages/word-list.js";
import * as search from "./pages/search.js";
import * as study from "./pages/study.js";
import * as flashcards from "./pages/flashcards.js";
import * as exercise from "./pages/exercise.js";
import * as settings from "./pages/settings.js";

// pattern: ":ad" parçaları parametre olarak sayfaya aktarılır. nav: menüde gösterilecek ad.
const ROUTES = [
  { pattern: "/", page: home, nav: "Ana Sayfa", section: "/" },
  { pattern: "/dersler", page: lessons, nav: "Dersler", section: "/dersler" },
  { pattern: "/dersler/:level", page: lessons, section: "/dersler" },
  { pattern: "/ders/:id", page: lesson, section: "/dersler" },
  { pattern: "/sozluk", page: dictionary, nav: "Sözlük", section: "/sozluk" },
  { pattern: "/kelime/:id", page: word, section: "/sozluk" },
  { pattern: "/calis", page: study, nav: "Kelime çalışması", section: "/calis" },
  { pattern: "/calis/kartlar/:direction/:source/:level", page: flashcards, section: "/calis" },
  { pattern: "/calis/alistirma/:type/:source/:level", page: exercise, section: "/calis" },
  { pattern: "/kelimelerim", page: wordList, nav: "Kelimelerim", section: "/kelimelerim" },
  { pattern: "/ara/:query", page: search, section: null },
  { pattern: "/ayarlar", page: settings, nav: "Ayarlar", section: "/ayarlar" },
];

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
    if (ok) return { route, params };
  }
  return null;
}

function renderNav(section) {
  nav.replaceChildren(
    ...ROUTES.filter((route) => route.nav).map((route) =>
      h("a", { href: `#${route.pattern}`, "aria-current": route.section === section ? "page" : null }, route.nav),
    ),
  );
}

async function render() {
  const token = ++renderToken;
  const path = location.hash.replace(/^#/, "") || "/";
  const found = match(path);
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
  main.replaceChildren(root);
  main.dataset.route = path; // sayfanın tamamen çizildiğini gösterir (testler bunu bekler)
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", () => {
  render().then(() => main.focus({ preventScroll: true }));
});

document.getElementById("search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.getElementById("search-input");
  const query = input.value.trim();
  if (query) location.hash = `#/ara/${encodeURIComponent(query)}`;
});

api.get("/settings").then((data) => applyTheme(data.settings.theme)).catch(() => {});
render();
