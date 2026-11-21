# Windows paketini üretmek

English Master, Windows için iki biçimde dağıtılır:

| Çıktı | Açıklama |
|---|---|
| `dist/EnglishMaster-Setup-<sürüm>.exe` | Kurulum sihirbazı (NSIS). Yönetici izni gerekmez. |
| `dist/EnglishMaster/` | Taşınabilir klasör (PyInstaller). `EnglishMaster.exe` doğrudan çalıştırılabilir. |

Her ikisinde de kişisel veriler `%LOCALAPPDATA%\EnglishMaster` klasöründe tutulur; program klasöründen bağımsızdır.

## 1. GitHub Actions ile (önerilen)

`.github/workflows/build-windows.yml` iş akışı yalnızca şu durumlarda çalışır:

- `v` ile başlayan bir sürüm etiketi gönderildiğinde (`git tag v0.9.0 && git push origin v0.9.0`),
- ya da GitHub'da **Actions → Windows paketi → Run workflow** ile elle başlatıldığında.

İş akışı sırasıyla şunları yapar:

1. İçerik veri tabanını üretir ve üçüncü taraf lisanslarını toplar.
2. PyInstaller ile paketler.
3. Paket içeriğini denetler: veri tabanı, ses klipleri, arayüz, migration'lar, lisanslar.
4. **Paketlenmiş programı gerçekten çalıştırır** (`packaging/smoke_test.py`).
5. NSIS ile kurulum dosyasını üretir, SHA-256 özetini yazar.
6. Kurulum dosyasını sessizce kurar, kurulu programı çalıştırır, aynı sürümü yeniden kurar
   (güncelleme senaryosu), sessizce kaldırır ve **kişisel verinin korunduğunu** doğrular.
7. Kurulum dosyasını ve özetini 30 gün saklanan "artifact" olarak yükler (Actions sayfasındaki çalışmanın altında).

İş akışı gizli bilgi (secret) kullanmaz ve kullanıcı verisi içermez.

## 2. Kendi Windows bilgisayarınızda

Gereksinimler: Python 3.13 (`py` başlatıcısıyla), NSIS 3 (`winget install NSIS.NSIS`).

```powershell
.\scripts\build_windows.ps1
```

Betik ayrı bir sanal ortam (`.venv-build`) kurar ve iş akışındaki 1–5. adımları uygular. NSIS kurulu
değilse yalnızca taşınabilir klasörü üretir.

## 3. Elle (adım adım)

```powershell
py -3.13 -m venv .venv-build
.\.venv-build\Scripts\python.exe -m pip install -r requirements.txt -r packaging\requirements-build.txt
.\.venv-build\Scripts\python.exe scripts\build_content.py
.\.venv-build\Scripts\python.exe packaging\collect_licenses.py
.\.venv-build\Scripts\python.exe -m PyInstaller packaging\english_master.spec --noconfirm --distpath dist --workpath build\pyi
.\.venv-build\Scripts\python.exe packaging\smoke_test.py dist\EnglishMaster\EnglishMaster.exe
makensis /DVERSION=0.9.0 packaging\installer.nsi
```

## Dosyalar

| Dosya | Görevi |
|---|---|
| `packaging/entry.py` | `EnglishMaster.exe` giriş noktası |
| `packaging/english_master.spec` | PyInstaller tanımı: pakete girecek veri, simge, sürüm bilgisi |
| `packaging/installer.nsi` | Kurulum / kaldırma sihirbazı |
| `packaging/collect_licenses.py` | Pakete giren bileşenlerin lisans metinlerini toplar |
| `packaging/THIRD_PARTY_NOTICES.txt` | İçerik kaynakları ve bileşenlerin atıf metni |
| `packaging/smoke_test.py` | Paketlenmiş ya da kurulu programı çalıştırıp dener |
| `packaging/requirements-build.txt` | Yalnızca paketleme için gereken araçlar (sabit sürümler) |

## Notlar

- **Kod imzalama yok.** Kurulum dosyası dijital olarak imzalanmadığı için Windows SmartScreen
  "Windows bilgisayarınızı korudu" uyarısı gösterebilir. İmzalama için bir kod imzalama sertifikası
  gerekir (ücretlidir); sertifika edinilirse iş akışına `signtool` adımı eklenebilir.
- **Ses dosyaları** derleme sırasında üretilmez; depoda hazır bulunur (`data/audio/`). İçerik metni
  değişmişse paketlemeden önce `scripts/build_audio.py` ile yeniden üretilmelidir (bkz. `docs/AUDIO.md`).
  `build_windows.ps1` eksik ses sayısını gösterir.
- **pystray (LGPL-3.0)** pakete değiştirilebilir kaynak dosyaları olarak konur
  (`_internal\pystray\`); lisans metni `_internal\licenses\` altındadır.
- **UPX kullanılmaz;** sıkıştırılmış çalıştırılabilir dosyalar bazı virüs tarayıcılarında yanlış alarma yol açar.
- Paket boyutu: program klasörü yaklaşık 120 MB (bunun ~40 MB'ı ses), kurulum dosyası yaklaşık 55–60 MB.
