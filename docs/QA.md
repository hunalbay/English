# Kalite güvencesi raporu (Aşama 8)

Tarih: 21 Kasım 2026 · Sürüm: 0.9.0 · Ortam: Linux (geliştirme), GitHub Actions (Linux + Windows)

Bu belge, yapılan denetimleri, kullanılan araçları, bulunan sorunları ve bilinen sınırları özetler.
Burada "geçti" denen her şey otomatik bir testle ya da kaydı tutulan bir ölçümle doğrulanmıştır.

## 1. Otomatik test takımı

| Grup | Kapsam |
|---|---|
| Birim | yapılandırma, güvenlik ara katmanı, ayarlar, migration'lar, başlatıcı, metin işleme, içerik doğrulayıcı, aralıklı tekrar, alıştırma üretimi, değerlendirme, ses eşleştirme, cevap anahtarları |
| Entegrasyon | bütün API uçları: öğrenme, sözlük, kelime çalışması, testler, beceriler, seviye tespiti, raporlar, güvenlik taraması |
| Uçtan uca | gerçek süreçte başlatma / tek örnek / kapanma; Chromium ile ~40 adımlı kullanıcı senaryosu |

Sonuç: **220 test, 220 geçti.** CI her gönderimde Linux ve Windows'ta çalışır (tarayıcı senaryosu yalnızca Linux'ta).

## 2. Güvenlik

| Denetim | Yöntem | Sonuç |
|---|---|---|
| Veri değiştiren uçlar belirteç ister | Bütün uçlar uygulamadan otomatik listelenip belirteçsiz çağrıldı (`test_security_routes.py`) | Geçti; yeni eklenen uçlar da kendiliğinden sınanır |
| GET istekleri durum değiştirmez | Bütün GET uçları çağrılıp önce / sonra karşılaştırıldı | Geçti |
| DNS rebinding / yabancı Host | 5 farklı Host başlığı | Hepsi 400 |
| Dosya yolu kaçışı | 8 farklı `..` / kodlanmış yol | Hepsi 404; veri tabanı ve kaynak kodu sunulmuyor |
| Güvenlik başlıkları | Sayfa, API, ses dosyası, 404 | CSP (`script-src 'self'`, satır içi betik yok), nosniff, no-referrer, CORP; API'de `no-store` |
| API belgeleri kapalı | `/docs`, `/redoc`, `/openapi.json` | 404 |
| Hata mesajı sızıntısı | Geçersiz veri, bozuk JSON | Genel Türkçe mesaj; iç ayrıntı yalnızca yerel log dosyasında |
| Arama girdisi | FTS sözdizimi, SQL parçası, NUL, çok uzun girdi | Hata yok; tablo bozulmadı |
| SQL enjeksiyonu | bandit + elle inceleme | Dinamik SQL'lerin hepsi yalnızca sabit parçalar ve `?` yer tutucuları kullanıyor; kullanıcı girdisi sorgu metnine girmiyor |
| Bağımlılık açıkları | pip-audit (requirements.txt + requirements-dev.txt) | Bilinen açık yok |
| Statik denetim | ruff (E, F, W, B, S, UP, SIM) | Gerçek hata yok; birkaç biçim önerisi uygulandı |
| Telemetri | Kod taraması; FastAPI OpenTelemetry kapalı | Dış ağa istek yok (tarayıcı senaryosu her dış isteği hata sayar) |

## 3. Erişilebilirlik

- **axe-core 4.10** ile 28 sayfa, açık ve koyu temada, WCAG 2.1 A / AA ve en iyi uygulama kurallarıyla tarandı.
  Bulunan tek ihlal (grafik çubuklarında rolü olmayan öğede `aria-label`) düzeltildi; son tarama **temiz**.
  Renk karşıtlığı denetimi de bu taramaya dâhildir.
- **Telefon genişliği (375 px):** 28 sayfanın hiçbirinde yatay taşma yok.
- **Klavye:** "İçeriğe geç" bağlantısı, görünür odak çerçevesi, sayfa geçişinde odağın içeriğe taşınması,
  grafik çubuklarına klavyeyle odaklanıp değer okuma.
- **Bulunan hata:** "İçeriğe geç" bağlantısı, adres çubuğundaki `#` yönlendirme için kullanıldığından
  "Sayfa bulunamadı" ekranını açıyordu. Düzeltildi ve tarayıcı testine eklendi.
- **Sınır:** Ekran okuyucuyla (NVDA, Narrator) elle deneme yapılmadı.

## 4. Performans

Kullanıcı veri tabanı, yıllarca yoğun kullanım gibi doldurularak ölçüldü: 3.000 test, 30.000 cevap,
8.000 kelime kartı, 120.000 kart tekrarı, 1.000 etkin gün (`user.db` ≈ 31 MB). Medyan yanıt süreleri:

| Uç | Önce | Sonra |
|---|---|---|
| Ana sayfa, dersler, sözlük, arama, kelime | 3–6 ms | değişmedi |
| Test başlatma / seviye tespiti başlatma | 75 / 93 ms | değişmedi |
| Kelime istatistikleri | 206 ms | **53 ms** |
| Güçlü / zayıf yön analizi | 302 ms | **173 ms** |
| İlerleme raporu | 480 ms | **310 ms** |

İyileştirmeler: günlük sayımlar Python yerine SQLite'ta yapılıyor; kelime istatistikleri yalnızca gereken
sütunları okuyor; `user.db`'ye iki dizin eklendi (migration 0006, yalnızca dizin).
Bu büyüklükteki veri tabanında migration'ın önce otomatik yedek aldığı da doğrulandı.

## 5. İçerik tutarlılığı

| Denetim | Sonuç |
|---|---|
| İçerik doğrulayıcı (bağlantılar, zorunlu bölümler, soru biçimleri, kelime örnekleri, yinelenenler) | Her derlemede çalışır; hatasız |
| **1.200 sorunun cevap anahtarı programın kendi değerlendiricisinde** | Hepsi doğru kabul ediliyor; yanlış seçeneklerin hiçbiri doğru sayılmıyor (`test_content_answer_keys.py`) |
| Anlamsız bir cevap herhangi bir yazılı soruda doğru sayılıyor mu? | Hayır |
| Yazım artıkları (kaçış karakteri, çift boşluk, ayrıştırılmamış ayraç, noktalama öncesi boşluk) | Yok |
| İngilizce yazım taraması (13.980 metin, CMU sözlüğü + programın sözlüğü) | Tanınmayan 154 sözcüğün tamamı gözden geçirildi: Türkçe metin, özel ad, hata düzeltme sorularındaki **bilerek yanlış** biçimler, İngiliz yazımı (maths, pyjamas) ya da seyrek ama doğru sözcükler. Gerçek yazım hatası bulunmadı |
| Telaffuz yazımı (IPA) | 5.048 kelimenin 4.998'inde var; eksik 50 kelime CMU sözlüğünde bulunmayan seyrek kelimeler (uydurulmadı) |
| Ses klipleri | Gereken 5.417 klibin tamamı mevcut ve metinleriyle eşleşiyor |

**Sınır:** İçeriğin anlamca doğruluğu (açıklamalar, çeviriler, örnekler) bir uzman tarafından gözden
geçirilmedi. Otomatik denetimler biçimsel tutarlılığı garanti eder, dilsel doğruluğu değil.

## 6. Dayanıklılık

| Durum | Önce | Sonra |
|---|---|---|
| İçerik veri tabanı yok | Açık mesaj (503) | değişmedi |
| İçerik veri tabanı bozuk | Genel "beklenmeyen hata" | Açık mesaj: dosya bozuk, yeniden kurun (503) |
| Kullanıcı veri tabanı bozuk | Açılışta ham veri tabanı hatasıyla çöküş | Program dosyaya dokunmadan durur; dosyanın ve yedek klasörünün yerini, kurtarma adımını anlatan mesaj |
| Ses dosyaları yok | Uyarı ve sistem sesi seçeneği | değişmedi |
| Migration hatası | Yedekten geri yükleme | değişmedi (test edildi) |
| Açılış hataları Windows'ta | Yalnızca konsola yazılıyordu (paketlenmiş sürümde görünmez) | Ayrıca bir uyarı penceresinde gösteriliyor |

## 7. İşlevsiz öğe kaldırıldı

Ayarlar'daki "günlük çalışma hedefi (dakika)" hiçbir yerde kullanılmıyordu, çünkü program çalışma süresini
ölçmüyor. İşlevsiz bir ayar göstermemek için arayüzden kaldırıldı. Kayıtlı değer korunur; süre ölçümü
eklenirse yeniden gösterilebilir.

## 8. Bilinen sınırlar ve açık riskler

- **Windows'ta elle deneme yok.** Windows'ta yalnızca otomatik testler (CI) çalıştı. Sistem tepsisi, sistem
  sesi geri dönüşü ve uyarı penceresi hiç çalıştırılmadı (Aşama 9'da kurulum paketiyle denenecek).
- **Ses ve mikrofon:** Sesler bir insan tarafından dinlenmedi; mikrofon kaydı yalnızca sahte aygıtla sınandı.
- **Ekran okuyucu:** Elle denenmedi.
- **İçerik:** Uzman denetimi yok; seviye tespit eşikleri gerçek öğrencilerle sınanmadı.
- **Rapor süresi:** Çok büyük geçmişte (yüz binlerce kayıt) ilerleme raporu yaklaşık 0,3 saniye sürüyor;
  kabul edilebilir, ama kayıt sayısıyla doğrusal artar.
