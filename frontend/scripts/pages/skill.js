// Beceri sayfaları (okuma, dinleme, yazma, telaffuz): seviye sekmeleri ve ders listesi.

import * as api from "../api.js";
import { add, h, lessonLink, pageHeader } from "../dom.js";

const TRACKS = {
  reading: {
    path: "okuma", title: "Okuma",
    intro: "Seviyenize uygun metinleri okuyun, takıldığınız yerde Türkçe çeviriyi açın ve okuduğunu anlama sorularını çözün.",
  },
  listening: {
    path: "dinleme", title: "Dinleme",
    intro: "Kayıtları dinleyin, soruları cevaplayın, ardından yazılı metinle karşılaştırın. Kayıtlar bilgisayar tarafından üretilmiş (sentetik) seslerdir; internet gerekmez.",
  },
  writing: {
    path: "yazma", title: "Yazma",
    intro: "Metin türlerini örnekleriyle öğrenin ve kendi metninizi yazın. Program yazınızı otomatik olarak puanlamaz; örnek metin ve kontrol listesiyle kendiniz değerlendirirsiniz.",
  },
  pronunciation: {
    path: "telaffuz", title: "Telaffuz",
    intro: "Türkçe konuşanları zorlayan sesleri örnek kayıtlarla çalışın: dinleyin, kendi sesinizi kaydedin ve karşılaştırın. Otomatik puanlama yoktur; kayıtlarınız saklanmaz ve hiçbir yere gönderilmez.",
  },
};

export async function render(root, params) {
  const track = TRACKS[params.track];
  const [{ levels }, profile] = await Promise.all([api.get(`/tracks/${params.track}`), api.get("/profile")]);
  const requested = (params.level || "").toUpperCase();
  const current = levels.find((level) => level.code === requested)
    || levels.find((level) => level.code === profile.current_level && level.lesson_count > 0)
    || levels.find((level) => level.lesson_count > 0)
    || levels[0];
  const { units } = await api.get(`/levels/${current.code}/units?track=${params.track}`);

  add(root,
    pageHeader(track.title, track.intro),
    h("nav", { class: "tabs", "aria-label": "Seviyeler" },
      levels.map((level) =>
        h("a", { href: `#/${track.path}/${level.code}`, "aria-current": level.code === current.code ? "page" : null },
          level.code, h("span", { class: "tab-sub" }, ` ${level.completed_lessons}/${level.lesson_count}`)))),
  );
  if (units.length === 0) {
    add(root, h("p", { class: "notice" }, `${current.code} seviyesi için ${track.title.toLocaleLowerCase("tr-TR")} içeriği henüz eklenmedi.`));
    return `${track.title} ${current.code}`;
  }
  for (const unit of units) {
    add(root,
      h("section", { class: "card" },
        h("h2", {}, unit.title_tr),
        unit.description_tr ? h("p", { class: "muted" }, unit.description_tr) : null,
        h("div", { class: "list" }, unit.lessons.map((lesson) => {
          const link = lessonLink(lesson);
          if (lesson.has_audio === false) link.querySelector(".list-sub").append(" · ses dosyası yok");
          return link;
        }))));
  }
  return `${track.title} ${current.code}`;
}
