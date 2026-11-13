// Uygulama kabuğu: menü, sayfa yönlendirme, tema.
// Menüde yalnızca gerçekten çalışan sayfalar yer alır; yeni modüller
// geliştirildikçe ROUTES listesine eklenir.

import * as api from "./api.js";
import { applyTheme, h } from "./dom.js";
import * as home from "./pages/home.js";
import * as settings from "./pages/settings.js";

const ROUTES = [
  { path: "/", label: "Ana Sayfa", page: home },
  { path: "/ayarlar", label: "Ayarlar", page: settings },
];

const main = document.getElementById("main");
const nav = document.getElementById("nav");

function currentPath() {
  const path = location.hash.replace(/^#/, "") || "/";
  return path.length > 1 ? path.replace(/\/$/, "") : path;
}

function renderNav(active) {
  nav.replaceChildren(
    ...ROUTES.map((route) =>
      h("a", { href: `#${route.path}`, "aria-current": route.path === active ? "page" : null }, route.label),
    ),
  );
}

async function render() {
  const path = currentPath();
  const route = ROUTES.find((r) => r.path === path);
  renderNav(route ? route.path : null);
  main.replaceChildren();
  if (!route) {
    main.append(
      h("div", { class: "page-header" }, h("h1", {}, "Sayfa bulunamadı")),
      h("p", {}, "Aradığınız sayfa yok. ", h("a", { href: "#/" }, "Ana sayfaya dön")),
    );
    return;
  }
  document.title = `${route.label} · English Master`;
  try {
    await route.page.render(main);
  } catch (error) {
    main.replaceChildren(
      h("div", { class: "page-header" }, h("h1", {}, route.label)),
      h("p", { class: "notice error", role: "alert" }, error.message || "Sayfa yüklenemedi."),
    );
  }
}

window.addEventListener("hashchange", () => {
  render().then(() => main.focus());
});

api.get("/settings").then((data) => applyTheme(data.settings.theme)).catch(() => {});
render();
