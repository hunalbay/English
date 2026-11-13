# Mimari

## Genel bakış

```
EnglishMaster (başlatıcı: app/launcher.py)
 ├─ tek kopya kilidi  → ikinci açılışta çalışan kopyanın arayüzü açılır
 ├─ uvicorn, yalnızca 127.0.0.1
 ├─ arayüzü varsayılan tarayıcıda açar
 └─ kapatma: tepsi menüsü · arayüzdeki "Programı kapat" · Ctrl+C

FastAPI (/api/v1/…) + statik arayüz (frontend/)
 ├─ content.db  salt okunur eğitim içeriği, uygulamayla dağıtılır
 └─ user.db     kullanıcı verisi, kurulum klasöründen bağımsız
```

## İki veri tabanı

| | `content.db` | `user.db` |
|---|---|---|
| İçerik | Dersler, kelimeler, sorular, metinler, ses kayıt bilgileri | İlerleme, cevaplar, tekrar planı, ayarlar, yazma çalışmaları |
| Konum | Kurulum klasörü (`data/build/`) | Windows: `%LOCALAPPDATA%\EnglishMaster\` |
| Yazma | Uygulama asla yazmaz | Yalnızca uygulama yazar |
| Güncelleme | Her sürümde `scripts/build_content.py` ile yeniden üretilir | Alembic migration; öncesinde otomatik yedek |
| Sürüm | `content_meta.content_version` | `alembic_version` |

Kullanıcı kayıtları içeriğe sayısal kimlikle değil, **kararlı metin kimlikleriyle**
(ör. `gram.b1.present-perfect`, `word.although`) bağlanır. İçerik yeniden üretildiğinde
kullanıcı geçmişi bozulmaz. İki dosya arasında SQL yabancı anahtarı yoktur; tutarlılık
uygulama katmanında ve içerik doğrulayıcıda sağlanır.

### Şema güncellemesi (`app/services/migrations.py`)

1. `user.db` güncel değilse SQLite yedekleme API'siyle `backups/user-pre-migration-…db` alınır.
2. Alembic `upgrade head` çalışır.
3. Hata olursa yedek geri konur, program anlaşılır bir hata ile durur.

Yeni kurulumda (dosya yokken) yedek alınmaz.

## Güvenlik (`app/core/security.py`)

- Sunucu yalnızca `127.0.0.1`'e bağlanır.
- `Host` başlığı `127.0.0.1` / `localhost` değilse istek reddedilir (DNS rebinding).
- Veri değiştiren API istekleri `X-EM-Token` ister. Belirteç her açılışta yeniden üretilir;
  CORS kapalı olduğundan başka sitelerdeki sayfalar belirteci okuyamaz.
- İçerik güvenlik politikası arayüzün dış adreslere istek atmasını engeller.
- Hata ayrıntıları yalnızca `logs/app.log` dosyasına yazılır.
- FastAPI'nin yerleşik OpenTelemetry desteği kapalıdır; telemetri yoktur.

## Arayüz

Saf ES modülleri, hash tabanlı yönlendirme, derleme adımı yok. Menüde yalnızca gerçekten
çalışan sayfalar bulunur (`frontend/scripts/app.js` içindeki `ROUTES`). DOM, `dom.js`
içindeki `h()` yardımcısıyla kurulur; `innerHTML` kullanılmaz.

## İçerik hattı

```
data/*.yaml ──(Pydantic şemaları)──> doğrulama ──> data/build/content.db
```

`scripts/build_content.py` kaynak dosyaları okur (`app/content/source_models.py`), dosyalar arası
tutarlılığı denetler (`app/content/builder.py: validate`) ve veri tabanını üretir. Tek bir hata varsa
dosya üretilmez. Uygulama kodu değişmeden yeni ders ve kelime eklenebilir; bkz. [CONTENT.md](CONTENT.md).

content.db'ye erişim `app/content/repository.py` içindeki parametreli, salt okunur sorgularla yapılır.
Arama SQLite FTS5 ile çalışır; metinler `fold_text()` ile sadeleştirildiği için Türkçe karakter
yazmadan da arama yapılabilir (ogretmen → öğretmen).

## API

| Uç | Açıklama |
|---|---|
| `GET /api/v1/health` | Sürüm, içerik durumu, şema revizyonu |
| `GET /api/v1/session` | Yazma istekleri için oturum belirteci |
| `GET /api/v1/settings` · `PUT /api/v1/settings/{key}` | Ayarlar (`theme`, `daily_goal_minutes`) |
| `POST /api/v1/system/shutdown` | Programı kapat |
| `GET /api/v1/profile` · `PUT /api/v1/profile/level` | Yerel profil ve seviye |
| `GET /api/v1/dashboard` | Ana ekran özeti (gerçek kayıtlardan) |
| `GET /api/v1/levels` · `GET /api/v1/levels/{code}/units` | Seviyeler, üniteler, dersler ve durumları |
| `GET /api/v1/lessons/{id}` | Ders: bölümler, örnekler, bağlantılı dersler ve kelimeler |
| `POST /api/v1/lessons/{id}/open` · `PUT /api/v1/lessons/{id}/completion` | Ders ilerlemesi |
| `GET /api/v1/vocabulary` · `GET /api/v1/vocabulary/{id}` | Sözlük listesi/araması ve kelime ayrıntısı |
| `GET /api/v1/vocabulary/lookup?form=` | Çekimli biçimden temel kelimeye |
| `GET/PUT/DELETE /api/v1/word-list[/{id}]` | Kişisel kelime listesi |
| `GET /api/v1/search?q=` | Derslerde ve sözlükte arama |

| `GET /api/v1/study/session` | Kart oturumu: tekrar zamanı gelenler + sınırlı sayıda yeni kelime |
| `POST /api/v1/study/review` | Kart cevabı (0 bilemedim · 1 zor · 2 bildim · 3 kolay) |
| `GET /api/v1/study/exercises` · `POST /api/v1/study/answer` | Alıştırma soruları ve açıklamalı değerlendirme |
| `GET /api/v1/study/stats` | Kelime istatistikleri |
| `GET/DELETE /api/v1/study/words/{id}` | Kelimenin öğrenme geçmişi · tekrar planını sıfırlama |

| `GET /api/v1/tests/overview` | Seviye ve derslere göre soru sayıları, konu başarısı, test geçmişi |
| `POST /api/v1/tests/sessions` | Test başlat (derse ya da seviyeye göre); sorular cevap anahtarı olmadan döner |
| `POST /api/v1/tests/sessions/{id}/answers` | Cevabı değerlendir; açıklamalı geri bildirim döner |
| `POST /api/v1/tests/sessions/{id}/self-rating` · `/finish` | Öz değerlendirme · testi bitir |

Hata biçimi: `{"error": {"code": "...", "message": "Türkçe açıklama"}}`

## Test motoru

- Soru tipleri ve değerlendiriciler `app/content/source_models.py` içinde tanımlıdır (18 tip, 5 değerlendirici).
- Değerlendirme kuralları `app/assessment/grading.py` içindedir. Esnek kipte büyük/küçük harf, sondaki
  noktalama ve kısaltma biçimi (isn't / is not) önemsenmez; `strict` kipte yazım ve noktalama da ölçülür.
- Program kesin karar veremediği cevapları "yanlış" saymaz: sonuç `ungraded` olur, örnek cevap gösterilir
  ve kullanıcı kendini değerlendirir. Öz değerlendirmeye dayanan sonuçlar özetlerde ayrıca belirtilir.
- Cevap anahtarı istemciye yalnızca cevap verildikten sonra gönderilir.
- Yeni testte önce hiç çözülmemiş, sonra yanlış yapılmış sorular seçilir.
- `listening_comprehension` tipi tanımlıdır ancak ses dosyaları Aşama 5'te ekleneceği için henüz sorusu yoktur.

## Kelime öğrenme

- **Aralıklı tekrar** (`app/learning/srs.py`): SM-2 türevi, saf fonksiyonlar. Her kelime için iki
  bağımsız kart vardır (EN→TR ve TR→EN). Kurallar dosyanın başında açıklanmıştır.
- **Alıştırmalar** (`app/learning/exercises.py`): sözlükten otomatik üretilir. Çeldiriciler aynı
  türden seçilir; doğru cevapla ortak Türkçe karşılığı olan ya da ilişkili kelimeler çeldirici
  yapılmaz (tek doğru cevap güvencesi). Yazılı cevapta aynı karşılığı taşıyan başka bir kelime de
  doğru kabul edilir.
- Alıştırmalarda doğru cevap tekrar planını ilerletmez; yanlış cevap, kelime daha önce kartlarla
  çalışılmışsa kartı öne alır. Bütün cevaplar `review_history` tablosuna yazılır.
- Henüz yok: dinleyerek tanıma ve yazma (ses dosyaları Aşama 5'te), İngilizce tanımdan bulma,
  kelime ailesi, eşdizim, phrasal verb ve deyim alıştırmaları (ilgili veri Aşama 6'da).

## Testler

- `tests/unit` — yapılandırma, güvenlik, ayarlar, migration/yedek, başlatıcı, içerik doğrulayıcı
- `tests/integration` — API uçları (FastAPI TestClient)
- `tests/e2e` — gerçek süreç: başlatma, tek kopya, kalıcılık, kapanış; tarayıcı duman testi
  (Node + Playwright varsa çalışır, yoksa atlanır)

## Aşamalar

1. Proje altyapısı ✔
2. Temel eğitim sistemi (içerik veri modeli, ana ekran, seviye seçimi, sözlük, arama) ✔
3. Kelime öğrenme (≥ 5.000 temel kelime, kartlar, aralıklı tekrar) ✔
4. Dil bilgisi ve test motoru
5. Okuma, dinleme, yazma, telaffuz
6. Deyimler ve mesleki İngilizce
7. Seviye tespit ve gelişim raporları
8. Kalite kontrolü
9. Windows paketleme (PyInstaller + NSIS, GitHub Actions)
10. Teslimat
