// Kelimelerim: kullanıcının tekrar etmek için seçtiği kelimeler.

import * as api from "../api.js";
import { wordRow } from "../components.js";
import { add, h, pageHeader } from "../dom.js";

export async function render(root) {
  const data = await api.get("/word-list");
  const count = h("p", { class: "muted", id: "word-list-count" });
  const list = h("ul", { class: "list" });
  const empty = h("p", { class: "notice" },
    "Listeniz boş. ", h("a", { href: "#/sozluk" }, "Sözlükten"), " ya da ders sayfalarından kelime ekleyebilirsiniz.");

  const paint = () => {
    const total = list.children.length;
    count.textContent = total ? `${total} kelime` : "";
    empty.hidden = total > 0;
  };
  for (const word of data.items) {
    const row = wordRow(word, { onChange: (changed) => { if (!changed.in_word_list) { row.remove(); paint(); } } });
    list.append(row);
  }
  paint();

  add(root, 
    pageHeader("Kelimelerim", "Tekrar etmek için seçtiğiniz kelimeler. Kelime kartları eklendiğinde bu listeyle çalışabileceksiniz."),
    count, list, empty,
  );
  return "Kelimelerim";
}
