# English Master

Türkçe konuşanlar için A1'den C2'ye **ücretsiz, çevrimdışı** İngilizce eğitim programı.
Hesap, üyelik veya internet bağlantısı gerektirmez; ilerlemeniz yalnızca kendi bilgisayarınızda saklanır.

> **Durum: Aşama 2 (temel eğitim sistemi).** Seviye seçimi, ders sayfaları, sözlük, arama ve yerel
> ilerleme kaydı çalışıyor. İçerik henüz başlangıç düzeyinde (3 ders, 120 kelime); kelime kartları,
> testler, okuma/dinleme ve Windows kurulum paketi sonraki aşamalarda eklenecek.

## Geliştirme ortamı

Gereksinim: Python 3.13.

**Windows (PowerShell):**

```powershell
.\scripts\setup_dev.ps1
.\.venv\Scripts\python.exe -m app
```

**Linux / macOS:**

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/build_content.py
.venv/bin/python -m pytest -rs
.venv/bin/python -m app
```

`python -m app` yerel sunucuyu yalnızca `127.0.0.1` üzerinde başlatır ve arayüzü tarayıcıda açar.
Seçenekler: `--port N`, `--no-browser`, `--no-tray`.

## Yapı

| Klasör | İçerik |
|---|---|
| `app/` | Backend (FastAPI): `core/` yapılandırma-güvenlik-log, `database/`, `models/`, `schemas/`, `api/`, `services/`, `launcher.py` |
| `frontend/` | Arayüz (saf HTML/CSS/JS, derleme adımı yok) |
| `data/` | Eğitim içeriği kaynak dosyaları; `data/build/content.db` bunlardan üretilir |
| `migrations/` | Kullanıcı veri tabanı (`user.db`) şema sürümleri (Alembic) |
| `scripts/` | İçerik derleme ve geliştirme betikleri |
| `tests/` | `unit/`, `integration/`, `e2e/` |
| `packaging/` | PyInstaller + NSIS dosyaları (Aşama 9) |
| `docs/` | Mimari ve geliştirici belgeleri |

Ayrıntılar: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · İçerik ekleme: [docs/CONTENT.md](docs/CONTENT.md)

## Gizlilik

Program hiçbir kullanım verisi toplamaz ve dışarı göndermez. Telemetri yoktur.
