// Tarayıcı ile uçtan uca senaryo. Kullanım: node smoke.cjs http://127.0.0.1:PORT/ [ekran-görüntüsü-ön-eki]
const { chromium } = require("playwright");

const url = process.argv[2];
const shots = process.argv[3];
const failures = [];
const check = (condition, message) => { if (!condition) failures.push(message); };

(async () => {
  // Sahte mikrofon: telaffuz kaydı gerçek bir aygıt olmadan sınanır.
  const browser = await chromium.launch({
    args: ["--use-fake-device-for-media-stream", "--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"],
  });
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
  check(await page.getByText(/^\d+ dersten 0 tanesi tamamlandı$/).isVisible(), "seviye ilerlemesi görünmüyor");

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

  // 4b) Konu testi: her soru tipinde cevap ver, açıklamaları ve ders bağlantısını doğrula
  await page.getByRole("link", { name: "Konu testini çöz" }).click();
  await page.getByRole("heading", { level: 1, name: /Konu testi/ }).waitFor();
  const seenTypes = new Set();
  for (let i = 0; i < 10; i += 1) {
    await page.getByText(`Soru ${i + 1} / 10`).waitFor();
    if (await page.locator(".options .btn").count()) {
      seenTypes.add("choice");
      const optionCount = await page.locator(".options .btn").count();
      await page.locator(".options .btn").first().click();
      await page.locator("#feedback").waitFor();
      check((await page.locator(".option-reasons li").count()) === optionCount, "her seçenek için açıklama gösterilmedi");
      check((await page.locator(".option-reasons li.is-right").count()) === 1, "doğru seçenek açıklamada işaretlenmedi");
    } else if (await page.locator("#token-bank").count()) {
      seenTypes.add("order");
      check(await page.getByRole("button", { name: "Kontrol et" }).isDisabled(), "sıralama eksikken kontrol edilebiliyor");
      const tokens = page.locator("#token-bank .btn");
      const count = await tokens.count();
      for (let t = 0; t < count; t += 1) await tokens.nth(t).click();
      await page.getByRole("button", { name: "Kontrol et" }).click();
      await page.locator("#feedback").waitFor();
      check(await page.getByText("Doğru sıra:").isVisible(), "doğru sıra gösterilmedi");
    } else if (await page.locator(".match-row").count()) {
      seenTypes.add("matching");
      for (const select of await page.locator(".match-row select").all()) await select.selectOption({ index: 1 });
      await page.getByRole("button", { name: "Kontrol et" }).click();
      await page.locator("#feedback").waitFor();
    } else if (await page.locator("textarea#answer-input").count()) {
      seenTypes.add("self");
      await page.locator("textarea#answer-input").fill("I am Deniz. I am thirty years old. I am from Izmir.");
      await page.getByRole("button", { name: /Cevabımı kaydet/ }).click();
      await page.locator("#feedback").waitFor();
      check(await page.getByText("Örnek cevap:").isVisible(), "örnek cevap gösterilmedi");
      check(await page.getByText("Kontrol listesi:").isVisible(), "kontrol listesi gösterilmedi");
      await page.getByRole("button", { name: "Doğruydu", exact: true }).click();
      await page.getByText("Değerlendirmeniz kaydedildi.").waitFor();
    } else {
      seenTypes.add("text");
      await page.locator("input#answer-input").fill("She is xyz");
      await page.getByRole("button", { name: "Kontrol et" }).click();
      await page.locator("#feedback").waitFor();
      if (await page.locator("#self-rating").count()) {
        check(await page.getByText("kesin olarak değerlendiremez").isVisible(), "değerlendirme sınırı açıklanmadı");
        await page.getByRole("button", { name: "Yanlıştı", exact: true }).click();
        await page.getByText("Değerlendirmeniz kaydedildi.").waitFor();
      }
    }
    check(await page.getByText("Açıklama:").isVisible(), `soru ${i + 1}: açıklama gösterilmedi`);
    check(await page.locator(".feedback-links a", { hasText: "İlgili ders:" }).first().isVisible(), `soru ${i + 1}: ders bağlantısı yok`);
    check(await page.locator(".feedback-links a", { hasText: "Aynı konudan yeni sorular" }).isVisible(), "aynı konudan soru bağlantısı yok");
    if (i === 0 && shots) await shot("test-feedback");
    await page.locator("#next-question").click();
  }
  await page.locator("#test-summary").waitFor();
  check(/10 sorudan \d+ doğru, \d+ yanlış\./.test(await page.locator("#test-summary").innerText()), "test özeti hatalı");
  // Sorular rastgele seçilir (13 sorudan 10'u); yalnızca her seçimde mutlaka çıkan tipler zorunlu tutulur.
  // Sıralama, eşleştirme ve öz değerlendirme tipleri çıktıklarında yukarıda ayrıca doğrulanır;
  // tümü tests/integration/test_tests_api.py içinde kesin olarak sınanır.
  check(seenTypes.has("choice") && seenTypes.has("text"),
    "testte seçmeli ve yazmalı sorular birlikte görülmedi: " + [...seenTypes].join(","));
  await menu.getByRole("link", { name: "Testler", exact: true }).click();
  await heading("Testler").waitFor();
  check((await page.locator("#test-history .list-item").count()) === 1, "test geçmişi görünmüyor");
  check(await page.getByRole("link", { name: /karışık test/ }).isVisible(), "seviye testi bağlantısı yok");
  await shot("tests");
  await page.goto(url + "#/testler/C2");
  await page.getByRole("link", { name: "C2 karışık test (10 soru)" }).waitFor();
  await page.goto(url + "#/ders/gram.a1.to-be-present");
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
  const total = await page.evaluate(async () => (await (await fetch("/api/v1/vocabulary?page_size=1")).json()).total);
  check(total >= 800, "sözlükte beklenenden az kelime var: " + total);
  await page.getByText(`${total} kelime`, { exact: true }).waitFor();
  await page.getByLabel("Kelime ara").fill("ogretmen");
  await page.getByRole("button", { name: /^teacher: Listemden çıkar/ }).waitFor();
  check((await page.locator("main .list .list-item").count()) < 30, "arama sonuçları süzülmedi");
  await page.getByLabel("Kelime ara").fill("qqqq");
  await page.getByText("Eşleşen kelime bulunamadı.").waitFor();
  await page.getByLabel("Kelime ara").fill("");
  await page.getByText(`${total} kelime`, { exact: true }).waitFor();
  await page.getByRole("button", { name: "Sonraki" }).click();
  await page.getByText(`Sayfa 2 / ${Math.ceil(total / 30)}`).waitFor();
  await shot("dictionary");

  // 6b) Kelime kartları: EN→TR oturumu (liste kaynağı: teacher)
  await menu.getByRole("link", { name: "Kelime çalışması", exact: true }).click();
  await heading("Kelime çalışması").waitFor();
  check(await page.getByText("Henüz çalışma kaydınız yok.").isVisible(), "boş istatistik mesajı görünmüyor");
  await page.getByLabel("Hangi kelimeler?").selectOption("list");
  await page.getByRole("link", { name: /İngilizce → Türkçe/ }).click();
  await heading("Kartlar: İngilizce → Türkçe").waitFor();
  check((await page.locator(".card-front").innerText()) === "teacher", "kartın ön yüzü yanlış");
  check(await page.locator(".card-back").isHidden(), "cevap baştan görünüyor");
  await page.keyboard.press("Space");
  check((await page.locator(".card-answer").innerText()) === "öğretmen", "kartın arka yüzü yanlış");
  await page.keyboard.press("1"); // Bilemedim → oturum sonunda bir kez daha sorulur
  await page.getByText("· tekrar").waitFor();
  await page.getByRole("button", { name: /Cevabı göster/ }).click();
  await page.getByRole("button", { name: /Bildim/ }).click();
  await page.getByText('2 cevap verdiniz; 1 kez "Bilemedim" dediniz.').waitFor();

  // 6c) TR→EN yönü bağımsızdır
  await page.goto(url + "#/calis/kartlar/tr_en/list/-");
  await heading("Kartlar: Türkçe → İngilizce").waitFor();
  check((await page.locator(".card-front").innerText()) === "öğretmen", "TR→EN kartının ön yüzü yanlış");
  await page.getByRole("button", { name: /Cevabı göster/ }).click();
  check((await page.locator(".card-answer").innerText()) === "teacher", "TR→EN kartının arka yüzü yanlış");
  await page.getByRole("button", { name: /Kolay/ }).click();
  await page.getByText("Oturum tamamlandı").waitFor();
  await shot("flashcard-done");

  // 6d) Alıştırma: anlamı seç — bilerek bir yanlış, sonra doğrular
  await page.goto(url + "#/calis/alistirma/mc_en_tr/level/A1");
  await heading("Anlamı seç").waitFor();
  await page.getByText("Soru 1 / 10").waitFor();
  for (let i = 0; i < 10; i += 1) {
    await page.getByText(`Soru ${i + 1} / 10`).waitFor();
    const word = await page.locator(".question-prompt").innerText();
    const meaning = await page.evaluate(async (lemma) => {
      const response = await fetch(`/api/v1/vocabulary?q=${encodeURIComponent(lemma)}`);
      return (await response.json()).items.find((item) => item.lemma === lemma).meaning_tr;
    }, word);
    const options = page.locator(".options .btn");
    if (i === 0) {
      const texts = await options.allInnerTexts();
      await options.nth(texts.findIndex((text) => text !== meaning)).click();
      await page.getByText("Yanlış.").waitFor();
      check(await page.getByText("Sizin cevabınız:").isVisible(), "yanlış seçeneğin açıklaması yok");
      check((await page.locator(".btn.option.right").count()) === 1, "doğru seçenek işaretlenmedi");
      if (shots) await shot("exercise-wrong");
    } else {
      await options.getByText(meaning, { exact: true }).click();
      await page.getByText("Doğru!").waitFor();
    }
    check(await page.locator(".feedback .ex-en").isVisible(), "geri bildirimde örnek cümle yok");
    await page.locator(".feedback + .btn").click();
  }
  await page.getByText("10 sorudan 9 tanesini doğru cevapladınız.").waitFor();
  check((await page.locator(".chips .chip").count()) === 1, "tekrar edilecek kelime listesi yanlış");

  // 6e) Yazma alıştırması: boş cevap uyarısı ve doğru cevap
  await page.goto(url + "#/calis/alistirma/typing/list/-");
  await heading("Kelimeyi yaz").waitFor();
  await page.getByRole("button", { name: "Kontrol et" }).click();
  await page.getByText("Lütfen bir cevap yazın.").waitFor();
  await page.getByLabel("İngilizce karşılığı").fill("  Teacher ");
  await page.getByRole("button", { name: "Kontrol et" }).click();
  await page.getByText("Doğru!").waitFor();
  await page.getByRole("button", { name: "Sonucu gör" }).click();
  await page.getByText("1 sorudan 1 tanesini doğru cevapladınız.").waitFor();

  // 6f) Eşleştirme, boşluk doldurma ve zıt anlam sayfaları soru üretir
  for (const [type, name] of [["matching", "Eşleştirme"], ["cloze", "Boşluk doldurma"], ["antonym", "Zıt anlam"], ["mc_tr_en", "Kelimeyi seç"]]) {
    await page.goto(url + `#/calis/alistirma/${type}/level/A1`);
    await heading(name).waitFor();
    await page.locator("#question-progress").waitFor();
  }
  await page.goto(url + "#/calis/alistirma/matching/list/-");
  await page.getByText("soru üretilemedi").waitFor(); // tek kelimelik listeyle eşleştirme yapılamaz

  // 6g) İstatistikler ve kelime sayfasındaki öğrenme durumu gerçek kayıtları yansıtır
  await menu.getByRole("link", { name: "Kelime çalışması", exact: true }).click();
  await page.locator("#stat-studied").waitFor();
  check((await page.locator("#stat-studied").innerText()).startsWith("1 /"), "çalışılan kelime sayısı yanlış");
  check((await page.locator(".bar-value").last().innerText()) === "14", "bugünkü cevap sayısı yanlış");
  await shot("study");
  await page.goto(url + "#/kelime/word.teacher");
  await page.locator("#word-progress").waitFor();
  check((await page.locator("#word-progress").innerText()).includes("Öğreniliyor"), "kelime öğrenme durumu görünmüyor");
  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Tekrar planını sıfırla" }).click();
  await page.getByText("Tekrar planı sıfırlandı.").waitFor();
  check(((await page.locator("#word-progress").innerText()).match(/Henüz çalışılmadı/g) || []).length === 2, "tekrar planı sıfırlanmadı");

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
  check(await page.getByText(/^\d+ dersten 1 tanesi tamamlandı$/).isVisible(), "tamamlanan ders sayısı korunmadı");
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
  await page.reload();
  await heading("Ayarlar").waitFor();
  check((await page.getByText("Günlük çalışma hedefi").count()) === 0, "işlevsiz günlük hedef ayarı hâlâ görünüyor");
  check(await page.locator('input[name="theme"][value="dark"]').isChecked(), "tema seçimi korunmadı");
  check((await page.locator("#about").innerText()).includes("İçerik sürümü"), "program bilgisi görünmüyor");

  // 11) Bilinmeyen sayfa ve bilinmeyen ders
  await page.goto(url + "#/yok");
  await heading("Sayfa bulunamadı").waitFor();
  await page.goto(url + "#/ders/gram.a1.yok");
  await page.getByText("Ders bulunamadı.").waitFor();

  // 11b) Okuma: metin, çeviri düğmesi, sözlükçe ve sorular
  await menu.getByRole("link", { name: "Okuma", exact: true }).click();
  await heading("Okuma").waitFor();
  check((await page.locator(".tabs a").count()) === 6, "okuma sayfasında seviye sekmeleri eksik");
  await page.goto(url + "#/okuma/A1");
  await page.getByRole("link", { name: /Ailem/ }).click();
  await heading("Ailem").waitFor();
  check((await page.locator("#passage .passage-line").count()) >= 5, "okuma metni satırları görünmüyor");
  check(!(await page.locator("#passage .passage-tr").first().isVisible()), "çeviri baştan görünür olmamalı");
  await page.getByRole("button", { name: "Türkçe çevirileri göster" }).click();
  check(await page.locator("#passage .passage-tr").first().isVisible(), "çeviri gösterilmedi");
  check(await page.getByText("Metindeki kelimeler").isVisible(), "sözlükçe yok");
  await shot("reading");
  await page.getByRole("link", { name: "Soruları çöz" }).click();
  await page.getByText("Soru 1 /").waitFor();
  check(await page.locator(".question-prompt").isVisible(), "okuma sorusu yüklenmedi");
  if (await page.locator(".context.passage").count()) {
    check((await page.locator(".context.passage p").count()) >= 5, "okuma sorusunda metin eksik");
    check((await page.locator(".context.passage [lang=tr]").count()) === 0, "soruda Türkçe çeviri gösterilmemeli");
  }

  // 11c) Dinleme: oynatıcı, hız seçimi, gizli yazılı metin, ses dosyasının gerçekten yüklenmesi
  await menu.getByRole("link", { name: "Dinleme", exact: true }).click();
  await heading("Dinleme").waitFor();
  await page.goto(url + "#/dinleme/A1");
  await page.getByRole("link", { name: /Kafede sipariş/ }).click();
  await heading("Kafede sipariş").waitFor();
  check(!(await page.locator("#transcript").isVisible()), "yazılı metin baştan gizli olmalı");
  check((await menu.locator('a[aria-current="page"]').innerText()) === "Dinleme", "menüde Dinleme işaretli değil");
  const audioInfo = await page.evaluate(async () => {
    const audio = document.querySelector("audio.player");
    if (!audio) return null;
    audio.preload = "auto";
    audio.load();
    await new Promise((resolve) => {
      audio.addEventListener("loadedmetadata", resolve, { once: true });
      audio.addEventListener("error", resolve, { once: true });
      setTimeout(resolve, 8000);
    });
    return { src: audio.getAttribute("src"), duration: audio.duration, error: audio.error ? audio.error.code : 0 };
  });
  check(audioInfo && audioInfo.src.startsWith("/media/clips/"), "dinleme kaydı oynatıcısı yok");
  check(audioInfo && audioInfo.error === 0 && audioInfo.duration > 10, "dinleme kaydı yüklenemedi: " + JSON.stringify(audioInfo));
  check((await page.locator("select.speed option").count()) === 3, "çalma hızı seçenekleri yok");
  await page.getByRole("button", { name: "Yazılı metni göster" }).click();
  check(await page.locator("#transcript .speaker").first().isVisible(), "yazılı metinde konuşmacı adları yok");
  await shot("listening");
  await page.getByRole("link", { name: "Soruları çöz" }).click();
  await page.getByText("Soru 1 /").waitFor();
  check((await page.locator("audio.player").count()) === 1 || (await page.locator(".options .btn").count()) >= 2,
    "dinleme testi yüklenmedi");

  // 11d) Telaffuz: örnek ses düğmeleri ve mikrofon kaydı (sahte aygıtla)
  await menu.getByRole("link", { name: "Telaffuz", exact: true }).click();
  await heading("Telaffuz").waitFor();
  await page.goto(url + "#/telaffuz/A1");
  await page.getByRole("link", { name: /th sesleri/ }).click();
  await heading(/th sesleri/).waitFor();
  check((await page.locator("#practice .practice-item").count()) >= 8, "telaffuz öğeleri görünmüyor");
  check((await page.locator(".section-usage ol li").count()) === 4, "numaralı adımlar liste olarak gösterilmedi");
  check((await page.locator("#practice .btn.listen").count()) >= 8, "örnek ses düğmeleri yok");
  check((await page.locator("#practice .btn.listen.fallback").count()) === 0, "hazır kayıt yerine sistem sesi öneriliyor");
  check(await page.getByText("otomatik olarak").first().isVisible(), "puanlama olmadığı açıklanmadı");
  const firstItem = page.locator("#practice .practice-item").first();
  await firstItem.locator(".btn.record").click();
  await firstItem.getByText("Kaydediliyor…").waitFor();
  await page.waitForTimeout(700);
  await firstItem.locator(".btn.record").click();
  await firstItem.getByRole("button", { name: "▶ Kaydımı dinle" }).waitFor();
  check(await firstItem.getByText("Kayıt hazır.").isVisible(), "kayıt tamamlanmadı");
  await shot("pronunciation");

  // 11e) Yazma: açıklama, örnek ve öz değerlendirmeli çalışma
  await menu.getByRole("link", { name: "Yazma", exact: true }).click();
  await heading("Yazma").waitFor();
  await page.goto(url + "#/yazma/A1");
  await page.getByRole("link", { name: /Kendini tanıtan/ }).click();
  await heading(/Kendini tanıtan/).waitFor();
  check(await page.getByRole("heading", { name: "Yazma çalışması" }).isVisible(), "yazma çalışması kartı yok");
  check(await page.getByText("otomatik olarak puanlamaz").isVisible(), "yazma için puanlama sınırı açıklanmadı");
  await shot("writing");

  // 11e2) Deyimler ve mesleki İngilizce: ifade listesi, rozetler, sesler
  await menu.getByRole("link", { name: "Deyimler ve kalıplar", exact: true }).click();
  await heading("Deyimler ve kalıplar").waitFor();
  await page.goto(url + "#/deyimler/B1");
  await page.getByRole("link", { name: /Sık kullanılan deyimler/ }).click();
  await heading(/Sık kullanılan deyimler/).waitFor();
  check((await page.locator("#expressions .expression").count()) >= 10, "deyim listesi görünmüyor");
  check(await page.locator("#expressions").getByText("gündelik").first().isVisible(), "üslup rozeti yok");
  check((await page.locator("#expressions .btn.listen.fallback").count()) === 0, "deyimler için hazır ses yok");
  check((await menu.locator('a[aria-current="page"]').innerText()) === "Deyimler ve kalıplar", "menüde Deyimler işaretli değil");
  await shot("expressions");
  await menu.getByRole("link", { name: "Mesleki İngilizce", exact: true }).click();
  await heading("Mesleki İngilizce").waitFor();
  check(await page.getByText("SAP SE ile bağlantılı değildir").isVisible(), "SAP açıklaması görünmüyor");
  await page.goto(url + "#/mesleki/C1");
  await page.getByRole("link", { name: /SAP projelerinde/ }).click();
  await heading(/SAP projelerinde/).waitFor();
  check(await page.locator("#expressions").getByText("masraf yeri", { exact: true }).isVisible(), "SAP terimleri görünmüyor");
  check((await page.locator("ol li").count()) >= 5, "satınalma adımları liste olarak görünmüyor");

  // 11f) Kelime sayfasında hazır ses
  await page.goto(url + "#/kelime/word.teacher");
  await heading("teacher").waitFor();
  check((await page.locator(".page-header .btn.listen").count()) === 1, "kelime sayfasında dinle düğmesi yok");
  check((await page.locator(".page-header .btn.listen.fallback").count()) === 0, "kelime için hazır ses bulunamadı");

  // 11g) İlerleme raporu: gerçek etkinlik, iki grafik, tablo görünümü, analiz
  await menu.getByRole("link", { name: "İlerleme", exact: true }).click();
  await heading("İlerleme").waitFor();
  check((await page.locator("svg.chart").count()) === 2, "ilerleme grafikleri çizilmedi");
  check((await page.locator("svg.chart .chart-bar").count()) >= 1, "bugünkü etkinlik grafikte görünmüyor");
  const answered = Number((await page.locator(".stat-tile", { hasText: "Cevaplanan soru" }).locator(".stat-value").innerText()).trim());
  check(answered >= 10, "cevaplanan soru sayısı etkinliği yansıtmıyor: " + answered);
  check((await page.locator(".stat-tile", { hasText: "Güncel seri" }).locator(".stat-value").innerText()).startsWith("1"), "seri 1 gün olmalı");
  const firstChart = page.locator(".chart-figure").first();
  await firstChart.locator(".chart-item").last().focus();
  check(await firstChart.locator(".chart-tooltip").isVisible(), "grafik ipucu görünmüyor");
  check((await firstChart.locator(".chart-tooltip").innerText()).includes("soru"), "grafik ipucu değeri göstermiyor");
  await page.locator(".chart-table summary").first().click();
  check((await page.locator(".chart-table").first().locator("tbody tr").count()) === 30, "etkinlik tablosu 30 gün değil");
  check(await page.locator("#analysis").isVisible(), "güçlü / zayıf yön bölümü yok");
  check((await page.locator(".meter").count()) >= 5, "alan ilerleme çubukları eksik");
  await shot("progress");

  // 11h) Seviye tespit sınavı: başlat, bütün bölümleri cevapla, sonucu uygula
  await menu.getByRole("link", { name: "Seviye tespiti", exact: true }).click();
  await heading("Seviye tespit sınavı").waitFor();
  check(await page.getByText("Konuşma, yazma ve dinleme").isVisible(), "sınavın sınırları açıklanmadı");
  await page.getByRole("button", { name: "Sınava başla" }).click();
  await page.locator("#placement-status").getByText("Bölüm 1 · A1").waitFor();
  for (let step = 0; step < 48; step += 1) {
    if (await page.locator("#placement-result").count()) break;
    await page.locator("#placement-question").waitFor();
    const before = await page.locator("#placement-status").innerText();
    if (await page.locator("#placement-question .options .btn").count()) {
      check((await page.locator("#feedback").count()) === 0, "seviye tespitinde geri bildirim gösterilmemeli");
      await page.locator("#placement-question .options .btn").first().click();
    } else {
      await page.locator("#answer-input").fill("is");
      await page.getByRole("button", { name: "Cevapla" }).click();
    }
    await page.waitForFunction((text) => {
      if (document.getElementById("placement-result")) return true;
      const status = document.getElementById("placement-status");
      return status && /Soru \d/.test(status.textContent) && status.textContent !== text;
    }, before);
  }
  await page.locator("#placement-result").waitFor();
  check(await page.getByText("Tahmini seviyeniz").isVisible(), "tahmini seviye yok");
  check((await page.getByRole("heading", { name: "Bölümler" }).locator("xpath=..").locator("tbody tr").count()) >= 1, "bölüm tablosu yok");
  await shot("placement-result");
  const applyButton = page.getByRole("button", { name: /seviyesiyle devam et/ }).first();
  const appliedLevel = (await applyButton.innerText()).slice(0, 2);
  await applyButton.click();
  await heading("Ana Sayfa").waitFor();
  check(await page.locator(".stat-value", { hasText: appliedLevel }).first().isVisible(), "sonuç profile uygulanmadı");
  await page.goto(url + "#/seviye-tespiti");
  await page.locator("#placement-history li").first().waitFor();
  await page.goto(url + "#/testler");
  await page.getByText("Seviye tespit sınavı").first().waitFor();

  // 11i) Klavye: ilk Tab "İçeriğe geç" bağlantısına gider; Enter sayfayı değiştirmeden odağı içeriğe taşır
  await page.goto(url + "#/sozluk");
  await page.reload();  // sayfa ilk kez açılmış gibi: odak belgenin başında
  await heading("Sözlük").waitFor();
  await page.keyboard.press("Tab");
  check(await page.evaluate(() => document.activeElement.classList.contains("skip-link")), "ilk Tab içeriğe geç bağlantısına gitmiyor");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(200);
  check(await page.evaluate(() => document.activeElement.id === "main"), "içeriğe geç odağı taşımadı");
  check(page.url().endsWith("#/sozluk") && await heading("Sözlük").isVisible(), "içeriğe geç sayfayı değiştirdi");

  // 12) Küçük ekranda yatay taşma olmamalı
  await page.setViewportSize({ width: 375, height: 700 });
  for (const hash of ["#/", "#/ders/gram.a1.to-be-present", "#/sozluk", "#/kelime/word.be", "#/ayarlar", "#/calis", "#/calis/kartlar/en_tr/level/A1", "#/calis/alistirma/matching/level/A1", "#/testler", "#/test/ders/gram.a1.articles-a-an"]) {
    await page.goto(url + hash);
    await page.locator(`main[data-route="${hash.slice(1)}"]`).waitFor();
    check(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), `375px genişlikte taşma: ${hash}`);
  }
  if (shots) {
    await page.goto(url + "#/ders/gram.a1.to-be-present");
    await page.locator('main[data-route="/ders/gram.a1.to-be-present"]').waitFor();
    await page.screenshot({ path: `${shots}-mobile.png` });
  }
  await page.goto(url + "#/ayarlar");
  await heading("Ayarlar").waitFor();

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
