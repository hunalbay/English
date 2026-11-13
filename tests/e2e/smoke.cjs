// Tarayıcı duman testi. Kullanım: node smoke.cjs http://127.0.0.1:PORT/
const { chromium } = require("playwright");

const url = process.argv[2];
const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  const external = [];
  const consoleErrors = [];
  page.on("request", (request) => {
    const target = new URL(request.url());
    if (target.protocol.startsWith("http") && target.hostname !== "127.0.0.1") external.push(request.url());
  });
  page.on("console", (message) => { if (message.type() === "error") consoleErrors.push(message.text()); });
  page.on("pageerror", (error) => consoleErrors.push(String(error)));

  // 1) Başlangıç ekranı gerçek durum bilgisini gösterir
  await page.goto(url);
  await page.getByRole("heading", { level: 1, name: "English Master" }).waitFor();
  check(await page.getByText("Hazır", { exact: true }).isVisible(), "içerik durumu 'Hazır' görünmüyor");
  check(await page.locator("#content-built").isVisible(), "içerik derleme tarihi görünmüyor");

  // 2) Ayar değiştirilir ve sayfa yenilendiğinde korunur
  await page.getByRole("link", { name: "Ayarlar" }).click();
  await page.getByRole("heading", { level: 1, name: "Ayarlar" }).waitFor();
  await page.getByText("Koyu", { exact: true }).click();
  await page.getByText("Ayar kaydedildi.").waitFor();
  check((await page.evaluate(() => document.documentElement.dataset.theme)) === "dark", "koyu tema uygulanmadı");
  await page.getByLabel("Günlük çalışma hedefi (dakika)").fill("35");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await page.getByText("Ayar kaydedildi.").waitFor();
  await page.reload();
  await page.getByRole("heading", { level: 1, name: "Ayarlar" }).waitFor();
  check((await page.getByLabel("Günlük çalışma hedefi (dakika)").inputValue()) === "35", "günlük hedef korunmadı");
  check(await page.locator('input[name="theme"][value="dark"]').isChecked(), "tema seçimi korunmadı");

  // 3) Geçersiz değer anlaşılır hata verir
  await page.getByLabel("Günlük çalışma hedefi (dakika)").fill("1000");
  await page.getByRole("button", { name: "Kaydet" }).click();
  await page.getByText("5 ile 240 dakika arasında olmalıdır").waitFor();

  // 4) Bilinmeyen sayfa
  await page.goto(url + "#/yok");
  await page.getByRole("heading", { name: "Sayfa bulunamadı" }).waitFor();

  // 5) Küçük ekranda yatay taşma olmamalı
  await page.setViewportSize({ width: 375, height: 700 });
  await page.goto(url + "#/ayarlar");
  await page.getByRole("heading", { level: 1, name: "Ayarlar" }).waitFor();
  check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), "375px genişlikte yatay taşma var");

  if (process.argv[3]) await page.screenshot({ path: process.argv[3] + "-mobile.png" });
  await page.setViewportSize({ width: 1280, height: 800 });
  if (process.argv[3]) {
    await page.screenshot({ path: process.argv[3] + "-settings.png" });
    await page.goto(url + "#/");
    await page.getByText("Hazır", { exact: true }).waitFor();
    await page.screenshot({ path: process.argv[3] + "-home.png" });
    await page.goto(url + "#/ayarlar");
  }

  // 6) Arayüzden programı kapatma
  await page.getByRole("button", { name: "Programı kapat" }).click();
  await page.getByRole("heading", { name: "English Master kapatıldı" }).waitFor();

  check(external.length === 0, "dış adrese istek atıldı: " + external.join(", "));
  check(consoleErrors.length === 0, "konsol hatası: " + consoleErrors.join(" | "));
  await browser.close();

  if (failures.length) {
    console.error("BAŞARISIZ:\n- " + failures.join("\n- "));
    process.exit(1);
  }
  console.log("Duman testi başarılı");
})().catch((error) => { console.error(error); process.exit(1); });
