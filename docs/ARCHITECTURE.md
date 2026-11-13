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

## API (Aşama 1)

| Uç | Açıklama |
|---|---|
| `GET /api/v1/health` | Sürüm, içerik durumu, şema revizyonu |
| `GET /api/v1/session` | Yazma istekleri için oturum belirteci |
| `GET /api/v1/settings` | Ayarlar |
| `PUT /api/v1/settings/{key}` | Ayar güncelle (`theme`, `daily_goal_minutes`) |
| `POST /api/v1/system/shutdown` | Programı kapat |

Hata biçimi: `{"error": {"code": "...", "message": "Türkçe açıklama"}}`

## Testler

- `tests/unit` — yapılandırma, güvenlik, ayarlar, migration/yedek, başlatıcı
- `tests/integration` — API uçları (FastAPI TestClient)
- `tests/e2e` — gerçek süreç: başlatma, tek kopya, kalıcılık, kapanış; tarayıcı duman testi
  (Node + Playwright varsa çalışır, yoksa atlanır)

## Aşamalar

1. Proje altyapısı ← **şu an**
2. Temel eğitim sistemi (içerik veri modeli, ana ekran, seviye seçimi, sözlük, arama)
3. Kelime öğrenme (≥ 5.000 temel kelime, kartlar, aralıklı tekrar)
4. Dil bilgisi ve test motoru
5. Okuma, dinleme, yazma, telaffuz
6. Deyimler ve mesleki İngilizce
7. Seviye tespit ve gelişim raporları
8. Kalite kontrolü
9. Windows paketleme (PyInstaller + NSIS, GitHub Actions)
10. Teslimat
