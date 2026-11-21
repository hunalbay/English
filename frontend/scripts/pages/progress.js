// İlerleme raporu: seriler, günlük etkinlik, haftalık başarı, alanlara göre dersler,
// güçlü / zayıf konular ve öneriler. Bütün sayılar yerel kayıtlardan gelir.

import * as api from "../api.js";
import { barChart, meter } from "../charts.js";
import { add, h, pageHeader } from "../dom.js";

const TRACK_TR = {
  grammar: "Dil bilgisi", reading: "Okuma", listening: "Dinleme", writing: "Yazma",
  pronunciation: "Telaffuz", expressions: "Deyimler ve kalıplar", professional: "Mesleki İngilizce",
};
const TYPE_TR = {
  multiple_choice: "Çoktan seçmeli", true_false: "Doğru / yanlış", fill_blank: "Boşluk doldurma",
  sentence_building: "Cümle kurma", word_order: "Sözcük sıralama", matching: "Eşleştirme",
  translation: "Çeviri", written_answer: "Yazılı cevap", error_spotting: "Hata bulma",
  error_correction: "Hata düzeltme", sentence_completion: "Cümle tamamlama",
  dialogue_completion: "Diyalog tamamlama", reading_comprehension: "Okuduğunu anlama",
  listening_comprehension: "Dinlediğini anlama", word_in_context: "Bağlamda kelime",
  word_formation: "Kelime türetme", paragraph_completion: "Paragraf tamamlama", nuance: "Anlam nüansı",
};
const LEVEL_TR = { below_A1: "A1 altı" };

const percent = (rate) => (rate === null || rate === undefined ? "—" : `%${Math.round(rate * 100)}`);
const shortDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("tr-TR", { day: "numeric", month: "short" });

function tile(label, value, note) {
  return h("div", { class: "stat-tile" },
    h("p", { class: "stat-label" }, label),
    h("p", { class: "stat-value" }, value),
    note ? h("p", { class: "muted small" }, note) : null);
}

function topicRow(topic) {
  return h("li", {},
    h("a", { href: `#/ders/${encodeURIComponent(topic.id)}` }, topic.title_tr),
    h("span", { class: "muted small" }, `${topic.level} · ${TRACK_TR[topic.track] || ""} · ${topic.correct}/${topic.total} doğru (${percent(topic.rate)})`));
}

function rateTable(title, rows, nameOf) {
  if (!rows.length) return null;
  return h("div", {},
    h("h3", {}, title),
    h("div", { class: "table-wrap" },
      h("table", {},
        h("thead", {}, h("tr", {}, h("th", { scope: "col" }, ""), h("th", { scope: "col" }, "Doğru"), h("th", { scope: "col" }, "Toplam"), h("th", { scope: "col" }, "Başarı"))),
        h("tbody", {}, rows.map((row) =>
          h("tr", {}, h("td", {}, nameOf(row.key)), h("td", {}, String(row.correct)), h("td", {}, String(row.total)), h("td", {}, percent(row.rate))))))));
}

function recommendation(item) {
  if (item.kind === "review_lesson") {
    return h("li", {}, h("a", { href: `#/ders/${encodeURIComponent(item.lesson.id)}` }, `Tekrar edin: ${item.lesson.title_tr}`),
      " — ", item.reason_tr, " ",
      h("a", { href: `#/test/ders/${encodeURIComponent(item.lesson.id)}` }, "Konu testini çöz"));
  }
  if (item.kind === "review_words") return h("li", {}, h("a", { href: "#/calis" }, "Kelime tekrarı yapın"), " — ", item.reason_tr);
  return h("li", {}, h("a", { href: "#/seviye-tespiti" }, "Seviye tespit sınavına girin"), " — ", item.reason_tr);
}

export async function render(root) {
  const [report, analysis] = await Promise.all([api.get("/reports/progress"), api.get("/reports/analysis")]);
  const totals = report.totals;

  add(root,
    pageHeader("İlerleme", "Çalışmalarınızın özeti. Bütün sayılar yalnızca bu bilgisayardaki kayıtlarınızdan hesaplanır."),
    h("section", { class: "card", "aria-labelledby": "ozet-baslik" },
      h("h2", { id: "ozet-baslik" }, "Özet"),
      h("div", { class: "stat-tiles" },
        tile("Güncel seri", `${report.streak.current} gün`, `En uzun seri: ${report.streak.longest} gün`),
        tile("Etkin gün", String(report.streak.active_days)),
        tile("Cevaplanan soru", String(totals.questions_answered),
          totals.graded_answers ? `Başarı: ${percent(totals.accuracy)} (${totals.graded_answers} değerlendirilmiş cevap)` : "Henüz değerlendirilmiş cevap yok"),
        tile("Tamamlanan ders", String(totals.lessons_completed)),
        tile("Kelime tekrarı", String(totals.word_reviews)),
        tile("Çalışılan kelime", `${report.vocabulary.studied_words} / ${report.vocabulary.total_words}`)),
      h("p", { class: "muted small" }, report.measures_note_tr, " ", report.timezone_note_tr)),
  );

  const daily = report.daily.map((day, index) => {
    const total = day.questions + day.reviews + day.lessons;
    return {
      label: shortDate(day.date), value: total,
      axisLabel: index % 5 === 4 || index === report.daily.length - 1 ? shortDate(day.date) : "",
      tooltip: `${shortDate(day.date)}: ${day.questions} soru, ${day.reviews} kelime tekrarı, ${day.lessons} ders`,
    };
  });
  const weekly = report.weekly_accuracy.map((week) => ({
    label: `${shortDate(week.week_start)} haftası`, value: week.rate === null ? null : Math.round(week.rate * 100),
    axisLabel: shortDate(week.week_start),
    tooltip: week.total ? `${shortDate(week.week_start)} haftası: ${week.correct}/${week.total} doğru (%${Math.round(week.rate * 100)})`
      : `${shortDate(week.week_start)} haftası: değerlendirilmiş cevap yok`,
  }));
  add(root,
    h("section", { class: "card" },
      barChart(daily, {
        title: "Son 30 gündeki etkinlik (cevaplanan soru + kelime tekrarı + tamamlanan ders)",
        tableHeaders: ["Gün", "Etkinlik"], emptyText: "Son 30 günde kayıtlı etkinlik yok.",
        format: (value) => String(Math.round(value)),
      })),
    h("section", { class: "card" },
      barChart(weekly, {
        title: "Haftalık test başarısı (doğru cevap yüzdesi)", max: 100,
        tableHeaders: ["Hafta", "Başarı (%)"], emptyText: "Son 8 haftada değerlendirilmiş test cevabı yok.",
        format: (value) => `%${Math.round(value)}`,
      }),
      h("p", { class: "muted small" }, "Serbest yazı gibi program tarafından değerlendirilemeyen cevaplar yalnızca öz değerlendirme yaptıysanız hesaba katılır.")),
  );

  add(root,
    h("section", { class: "card", "aria-labelledby": "alan-baslik" },
      h("h2", { id: "alan-baslik" }, "Alanlara göre tamamlanan dersler"),
      report.tracks.filter((track) => track.total).map((track) => meter(track.completed, track.total, TRACK_TR[track.track]))),
  );

  const vocab = report.vocabulary;
  add(root,
    h("section", { class: "card", "aria-labelledby": "kelime-baslik" },
      h("h2", { id: "kelime-baslik" }, "Kelimeler (İngilizce → Türkçe kartları)"),
      h("div", { class: "stat-tiles" },
        tile("Öğreniliyor", String(vocab.buckets_en_tr.learning), "Tekrar aralığı 21 günden kısa"),
        tile("İyi öğrenildi", String(vocab.buckets_en_tr.learned), "Tekrar aralığı en az 21 gün"),
        tile("Uzun süredir biliniyor", String(vocab.buckets_en_tr.long_term), "Tekrar aralığı en az 60 gün"),
        tile("Tekrar zamanı gelen", String(vocab.due), "İki yön toplamı")),
      analysis.difficult_words.length
        ? h("div", {}, h("h3", {}, "En çok yanılınan kelimeler"),
            h("div", { class: "chips" }, analysis.difficult_words.map((word) =>
              h("a", { class: "chip", href: `#/kelime/${encodeURIComponent(word.id)}` },
                h("span", { lang: "en" }, word.lemma), h("span", { class: "muted" }, ` — ${word.wrong_count} kez`)))))
        : null),
  );

  const judgedNote = `Bir konu hakkında yargıya varmak için en az ${analysis.min_answers} değerlendirilmiş cevap gerekir. ` +
    `Güçlü: %${Math.round(analysis.thresholds.strong_from * 100)} ve üzeri; geliştirilmeli: %${Math.round(analysis.thresholds.weak_below * 100)} altı.`;
  add(root,
    h("section", { class: "card", "aria-labelledby": "analiz-baslik", id: "analysis" },
      h("h2", { id: "analiz-baslik" }, "Güçlü ve zayıf yönler"),
      analysis.graded_answers === 0
        ? h("p", { class: "notice" }, "Henüz test cevabınız yok. Birkaç konu testi çözdükten sonra burada güçlü ve zayıf konularınız görünecek.")
        : h("div", { class: "grid" },
            h("div", {}, h("h3", {}, "Geliştirilmesi gereken konular"),
              analysis.weaknesses.length ? h("ul", { class: "rate-list", id: "weaknesses" }, analysis.weaknesses.map(topicRow))
                : h("p", { class: "muted" }, "Yeterli cevap olan konular arasında zayıf konu yok.")),
            h("div", {}, h("h3", {}, "Güçlü konular"),
              analysis.strengths.length ? h("ul", { class: "rate-list", id: "strengths" }, analysis.strengths.map(topicRow))
                : h("p", { class: "muted" }, "Henüz güçlü konu belirlenmedi."))),
      h("p", { class: "muted small" }, judgedNote,
        analysis.untested_topics ? ` ${analysis.untested_topics} konuda henüz yeterli cevap yok.` : ""),
      analysis.graded_answers
        ? h("details", {}, h("summary", {}, "Alan, seviye ve soru tipine göre başarı"),
            rateTable("Alanlara göre", analysis.by_track, (key) => TRACK_TR[key] || key),
            rateTable("Seviyelere göre", analysis.by_level, (key) => key),
            rateTable("Soru tiplerine göre", analysis.by_type, (key) => TYPE_TR[key] || key))
        : null),
    h("section", { class: "card", "aria-labelledby": "oneri-baslik" },
      h("h2", { id: "oneri-baslik" }, "Öneriler"),
      analysis.recommendations.length
        ? h("ul", { id: "recommendations" }, analysis.recommendations.map(recommendation))
        : h("p", { class: "muted" }, "Şu an için özel bir öneri yok. Kaldığınız yerden devam edin.")),
  );

  const latest = analysis.latest_placement;
  add(root,
    h("section", { class: "card" },
      h("h2", {}, "Seviye tespiti"),
      latest
        ? h("p", {}, `Son sınav (${new Date(latest.finished_at).toLocaleDateString("tr-TR")}): tahmini seviye `,
            h("strong", {}, LEVEL_TR[latest.result_level] || latest.result_level), ", önerilen çalışma seviyesi ",
            h("strong", {}, latest.recommended_level), ".")
        : h("p", { class: "muted" }, "Henüz seviye tespit sınavına girmediniz."),
      h("a", { class: "btn", href: "#/seviye-tespiti" }, latest ? "Sınavı yeniden çöz" : "Seviye tespit sınavına gir")),
  );
  return "İlerleme";
}
