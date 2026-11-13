// Dersler: seviye sekmeleri, üniteler ve ders listesi.

import * as api from "../api.js";
import { LESSON_KIND_TR, add, h, lessonLink, pageHeader } from "../dom.js";

export async function render(root, params) {
  const [{ levels }, profile] = await Promise.all([api.get("/levels"), api.get("/profile")]);
  const requested = (params.level || "").toUpperCase();
  const current = levels.find((level) => level.code === requested)
    || levels.find((level) => level.code === profile.current_level)
    || levels[0];
  const { units } = await api.get(`/levels/${current.code}/units`);

  add(root, 
    pageHeader("Dersler"),
    h("nav", { class: "tabs", "aria-label": "Seviyeler" },
      levels.map((level) =>
        h("a", { href: `#/dersler/${level.code}`, "aria-current": level.code === current.code ? "page" : null },
          level.code, h("span", { class: "tab-sub" }, ` ${level.completed_lessons}/${level.lesson_count}`)))),
    h("p", { class: "muted" }, h("strong", {}, `${current.code} — ${current.name_tr}. `), current.description_tr),
  );

  if (units.length === 0) {
    add(root, h("p", { class: "notice" }, `${current.code} seviyesi için dersler henüz eklenmedi.`));
    return `Dersler ${current.code}`;
  }
  for (const unit of units) {
    add(root, 
      h("section", { class: "card" },
        h("h2", {}, unit.title_tr),
        unit.description_tr ? h("p", { class: "muted" }, unit.description_tr) : null,
        h("div", { class: "list" },
          unit.lessons.map((lesson) => {
            const link = lessonLink(lesson);
            link.querySelector(".list-sub").prepend(`${LESSON_KIND_TR[lesson.kind] || lesson.kind} · `);
            return link;
          }))),
    );
  }
  return `Dersler ${current.code}`;
}
