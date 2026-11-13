// Tarayıcı ile uçtan uca senaryo. Kullanım: node smoke.cjs http://127.0.0.1:PORT/ [ekran-görüntüsü-ön-eki]
const { chromium } = require("playwright");

const url = process.argv[2];
const shots = process.argv[3];
const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
  page.setDefaultTimeout(10000);
  const external = [];
  const consoleErrors = [];
  page.on("request", (request) => {
    const target = new URL(request.url());
    if (target.protocol.startsWith("http") && target.hostname !== "127.0.0.1") external.push(request.url());
  });
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));
  const menu = page.getByRole("navigation", { name: "Ana menü" });
  const heading = (name) => page.getByRole("heading", { level: 1, name });
  const shot = async (name) => { if (shots) await page.screenshot({ path: `${shots}-${name}.png`, fullPage: true }); };

  // 1) İlk açılış: seviye seçimi
  await page.goto(url);
  await heading("English Master'a hoş geldiniz").waitFor();
  check((await page.locator(".level-card").count()) === 6, "altı seviye kartı görünmüyor");
  await shot("onboarding");
  await page.locator(".level-card", { hasText: "A1" }).click();
  await heading("Ana Sayfa").waitFor();
  await page.getByRole("heading", { name: "Sıradaki ders" }).waitFor();
  check(await page.getByText("3 dersten 0 tanesi tamamlandı").isVisible(), "seviye ilerlemesi görünmüyor");

  // 2) Dersler → ders sayfası
  await menu.getByRole("link", { name: "Dersler", exact: true }).click();
  await heading("Dersler").waitFor();
  check((await page.locator(".tabs a").count()) === 6, "seviye sekmeleri eksik");
  await page.getByRole("link", { name: /am, is, are/ }).click();
  await page.getByRole("heading", { level: 1, name: /To be/ }).waitFor();
  check(await page.getByText("She is a teacher.", { exact: true }).first().isVisible(), "örnek cümle görünmüyor");
  check(await page.getByText("O bir öğretmen.", { exact: true }).first().isVisible(), "örnek çevirisi görünmüyor");
  check(await page.getByText("I am 25 years old.").isVisible(), "yanlış kullanımın düzeltmesi görünmüyor");
  check((await page.locator("table").count()) >= 1, "tablo görünmüyor");
  check((await page.locator("main strong").count()) > 5, "kalın vurgu işlenmedi");
  check(!(await page.locator("main").innerText()).includes("**"), "biçimlendirme işaretleri ham görünüyor");
  await shot("lesson");

  // 3) Dersi tamamla
  await page.getByRole("button", { name: "Dersi tamamladım" }).click();
  await page.getByText("Bu dersi tamamladınız.").waitFor();

  // 4) Ön koşul bağlantısı ve geri dönüş
  await page.getByRole("link", { name: "Kişi zamirleri (özne)" }).first().click();
  await heading("Kişi zamirleri (özne)").waitFor();
  await page.goBack();
  await page.getByText("Bu dersi tamamladınız.").waitFor();

  // 5) Dersten kelimeye, kelimeyi listeye ekle
  await page.locator(".chip", { hasText: "teacher" }).click();
  await heading("teacher").waitFor();
  check(await page.getByText("öğretmen", { exact: true }).isVisible(), "kelime anlamı görünmüyor");
  check(await page.getByRole("link", { name: /am, is, are/ }).isVisible(), "kelimeden derse bağlantı yok");
  await page.getByRole("button", { name: /Listeme ekle/ }).click();
  await page.getByText("Kelime listenize eklendi.").waitFor();
  await shot("word");

  // 6) Sözlükte Türkçe karaktersiz arama
  await menu.getByRole("link", { name: "Sözlük", exact: true }).click();
  await heading("Sözlük").waitFor();
  await page.getByText("120 kelime", { exact: true }).waitFor();
  await page.getByLabel("Kelime ara").fill("ogretmen");
  await page.getByText("1 kelime", { exact: true }).waitFor();
  check(await page.getByRole("button", { name: /teacher: Listemden çıkar/ }).isVisible(), "liste durumu sözlükte görünmüyor");
  await page.getByLabel("Kelime ara").fill("qqqq");
  await page.getByText("Eşleşen kelime bulunamadı.").waitFor();
  await page.getByLabel("Kelime ara").fill("");
  await page.getByText("120 kelime", { exact: true }).waitFor();
  await page.getByRole("button", { name: "Sonraki" }).click();
  await page.getByText("Sayfa 2 / 4").waitFor();
  await shot("dictionary");

  // 7) Kelimelerim
  await menu.getByRole("link", { name: "Kelimelerim", exact: true }).click();
  await heading("Kelimelerim").waitFor();
  check((await page.locator("#word-list-count").innerText()) === "1 kelime", "kelime listesi sayısı yanlış");

  // 8) Genel arama
  await page.getByLabel("Derslerde ve sözlükte ara").fill("zamir");
  await page.getByLabel("Derslerde ve sözlükte ara").press("Enter");
  await page.getByRole("heading", { name: /Dersler \(\d+\)/ }).waitFor();
  check(await page.getByRole("link", { name: /Kişi zamirleri/ }).isVisible(), "arama dersi bulmadı");

  // 9) Sayfa yenilenince ilerleme korunur; "devam et" son açılan yarım dersi gösterir
  await page.goto(url);
  await page.reload();
  await heading("Ana Sayfa").waitFor();
  await page.getByRole("heading", { name: "Öğrenmeye devam et" }).waitFor();
  check(await page.getByText("3 dersten 1 tanesi tamamlandı").isVisible(), "tamamlanan ders sayısı korunmadı");
  check(await page.getByText("1 kelime", { exact: true }).isVisible(), "kelime listesi sayısı ana sayfada yanlış");
  check(await page.locator("#devam-baslik + .list").getByText("Kişi zamirleri (özne)").isVisible(), "devam edilecek ders yanlış");
  check((await page.locator(".progress-fill").evaluate((el) => el.getBoundingClientRect().width)) > 0, "ilerleme çubuğu boş");
  await shot("home");

  // 10) Ayarlar
  await menu.getByRole("link", { name: "Ayarlar", exact: true }).click();
  await heading("Ayarlar").waitFor();
  check((await page.getByLabel("Seviyeniz").inputValue()) === "A1", "seviye ayarlarda görünmüyor");
  await page.getByText("Koyu", { exact: true }).click();
  await page.getByText("Ayar kaydedildi.").waitFor();
  check((await page.evaluate(() => document.documentElement.dataset.theme)) === "dark", "koyu tema uygulanmadı");
  await page.getByLabel("Günlük çalışma hedefi (dakika)").fill("35");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await page.getByText("Ayar kaydedildi.").waitFor();
  await page.reload();
  await heading("Ayarlar").waitFor();
  check((await page.getByLabel("Günlük çalışma hedefi (dakika)").inputValue()) === "35", "günlük hedef korunmadı");
  check(await page.locator('input[name="theme"][value="dark"]').isChecked(), "tema seçimi korunmadı");
  await page.getByLabel("Günlük çalışma hedefi (dakika)").fill("1000");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await page.getByText("5 ile 240 dakika arasında olmalıdır").waitFor();
  check((await page.locator("#about").innerText()).includes("İçerik sürümü"), "program bilgisi görünmüyor");

  // 11) Bilinmeyen sayfa ve bilinmeyen ders
  await page.goto(url + "#/yok");
  await heading("Sayfa bulunamadı").waitFor();
  await page.goto(url + "#/ders/gram.a1.yok");
  await page.getByText("Ders bulunamadı.").waitFor();

  // 12) Küçük ekranda yatay taşma olmamalı
  await page.setViewportSize({ width: 375, height: 700 });
  for (const hash of ["#/", "#/ders/gram.a1.to-be-present", "#/sozluk", "#/kelime/word.be", "#/ayarlar"]) {
    await page.goto(url + hash);
    await page.locator(`main[data-route="${hash.slice(1)}"]`).waitFor();
    check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `375px genişlikte taşma: ${hash}`);
  }
  if (shots) {
    await page.goto(url + "#/ders/gram.a1.to-be-present");
    await page.locator('main[data-route="/ders/gram.a1.to-be-present"]').waitFor();
    await page.screenshot({ path: `${shots}-mobile.png` });
    await page.goto(url + "#/ayarlar");
    await heading("Ayarlar").waitFor();
  }

  // 13) Arayüzden programı kapatma
  await page.getByRole("button", { name: "Programı kapat" }).click();
  await page.getByRole("heading", { name: "English Master kapatıldı" }).waitFor();

  check(external.length === 0, "dış adrese istek atıldı: " + external.join(", "));
  // bilinçli olarak istenen 404 yanıtı dışındaki konsol hataları
  const unexpected = consoleErrors.filter((text) => !text.includes("404"));
  check(unexpected.length === 0, "konsol hatası: " + unexpected.join(" | "));
  await browser.close();

  if (failures.length) {
    console.error("BAŞARISIZ:\n- " + failures.join("\n- "));
    process.exit(1);
  }
  console.log("Uçtan uca senaryo başarılı");
})().catch((error) => { console.error(error); process.exit(1); });
