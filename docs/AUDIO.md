# Ses içeriği

English Master'daki bütün İngilizce sesler **önceden üretilmiş sentetik seslerdir**. Program çalışırken
ses üretmez, internete bağlanmaz ve hiçbir çevrim içi konuşma hizmetini kullanmaz.

## Ne için ses var?

| İçerik | Anahtar | Açıklama |
|---|---|---|
| Sözlükteki her kelime | `w:<kelime>` | Kelime sayfasındaki "Dinle" düğmesi |
| Telaffuz çalışması öğeleri | `s:<metin özeti>` | Telaffuz derslerindeki örnek sesler |
| Dinleme dersleri | `l:<ders kimliği>` | Kaydın tamamı tek dosya; diyaloglarda her konuşmacı ayrı ses |

Okuma metinleri, dil bilgisi örnek cümleleri ve sorular için hazır ses **yoktur**.

Güncel sayılar `python scripts/build_audio.py --check` komutuyla ve Ayarlar sayfasındaki içerik
bilgisinden görülebilir.

## Kaynak ve lisanslar

| Bileşen | Kaynak | Lisans | Not |
|---|---|---|---|
| Ses modeli | Piper `en-us-libritts-high` (rhasspy/piper v0.0.2 sürüm dosyası) | Model kartına göre veri kümesi **CC BY 4.0** | LibriTTS veri kümesiyle (openslr.org/60) eğitilmiştir |
| Veri kümesi | LibriTTS (Zen ve ark., 2019), LibriVox kamu malı kayıtlarından türetilmiştir | CC BY 4.0 | Atıf gereklidir (aşağıda) |
| Üretim aracı | `piper-tts` (PyPI) | GPL-3.0 | Yalnızca **üretim sırasında** kullanılır; programla birlikte dağıtılmaz |
| Kodlama | ffmpeg + libmp3lame | LGPL/GPL | Yalnızca üretim sırasında kullanılır |
| Metinler | Bu projede yazılmış özgün içerik | Proje lisansı | |

**Atıf:** Sesler, LibriTTS veri kümesiyle (H. Zen ve ark., "LibriTTS: A Corpus Derived from LibriSpeech
for Text-to-Speech", 2019; CC BY 4.0) eğitilmiş Piper `en-us-libritts-high` modeli kullanılarak
üretilmiştir.

Piper ve ffmpeg programın içinde **yer almaz**; kurulum paketine yalnızca üretilmiş MP3 dosyaları girer.
Model dosyası depoya eklenmez.

## Kullanılan sesler

Model çok konuşmacılıdır (904 konuşmacı). Dört konuşmacı seçilmiştir:

| Ad | Konuşmacı no | Kullanım |
|---|---|---|
| `f1` | 45 | Varsayılan: kelimeler, telaffuz öğeleri, anlatıcı |
| `m1` | 330 | Diyaloglarda ikinci konuşmacı |
| `f2` | 840 | Üçüncü konuşmacı, bazı anlatımlar |
| `m2` | 375 | Dördüncü konuşmacı, bazı anlatımlar |

Seçim, örnek cümlelerin temel frekansı ölçülerek (kadın / erkek ses ayrımı ve dengeli konuşma hızı için)
yapılmıştır.

## Bilinen sınırlar

- **Sesler bir insan tarafından dinlenip denetlenmemiştir.** Üretildikleri ortamda ses dinleme olanağı
  yoktu; yalnızca dosyaların üretildiği, süreleri ve biçimleri otomatik olarak doğrulandı.
- Sentetik ses, tek başına söylenen kısa kelimelerde (ör. "a", "the") ve eş yazımlı kelimelerde
  (ör. "read", "live", "record") yanlış ya da doğal olmayan bir okunuş üretebilir.
- Aksan Amerikan İngilizcesidir. Derslerdeki telaffuz yazımları (IPA) yer yer İngiliz okunuşunu
  gösterir; küçük farklar olabilir.
- Vurgu, tonlama ve duygu doğal bir konuşmacınınki kadar zengin değildir. Dinleme kayıtları gerçek
  hayattaki konuşmalardan daha temiz ve daha yavaştır.
- Kayıtlar tek bir aksanı temsil eder; farklı aksanlara alışmak için başka kaynaklar da dinlenmelidir.

## Ses olmadığında

Bir içeriğin ses dosyası yoksa (dosya eksikse ya da metin değiştiği hâlde ses yeniden üretilmediyse):

- program hata vermez; ilgili yerde **"Bu içerik için ses dosyası bulunamadı"** uyarısı gösterilir,
- tarayıcı destekliyorsa **"Sistem sesiyle dinle"** seçeneği sunulur. Bu, bilgisayarın kendi
  (Windows) sesini kullanır; kalitesi sisteme göre değişir ve bu durum düğmede belirtilir,
- dinleme sorularında yazılı metin, cevap verilmeden önce gösterilmez.

Metni değişen bir içeriğin eski sesi **kullanılmaz**: manifestteki özet, güncel metnin özetiyle
aynı değilse klip yok sayılır. Böylece yanlış metni okuyan bir ses çalınmaz.

## Sesleri yeniden üretmek

Gereksinimler: `ffmpeg`, ayrı bir Python ortamında `piper-tts` ve model dosyaları.

```bash
python3 -m venv /tmp/tts
/tmp/tts/bin/pip install piper-tts
curl -L -o voice.tar.gz https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-libritts-high.tar.gz
tar xzf voice.tar.gz
python scripts/build_audio.py --check
python scripts/build_audio.py --piper-python /tmp/tts/bin/python --model en-us-libritts-high.onnx
python scripts/build_content.py
```

Betik yalnızca eksik ya da metni değişmiş klipleri üretir, artık gerekmeyen dosyaları siler ve
`data/audio/manifest.json` dosyasını günceller. Üretim bu modelle yaklaşık olarak gerçek sürenin
beşte biri kadar zaman alır.

## Mikrofon ve gizlilik

Telaffuz çalışmasındaki ses kaydı tümüyle tarayıcıda yapılır:

- mikrofon izni yalnızca kullanıcı **"Kaydet"** düğmesine bastığında istenir,
- kayıt yalnızca bellekte tutulur; sunucuya (yerel sunucu dâhil) gönderilmez, diske yazılmaz,
- sayfadan çıkıldığında ya da yeni kayıt yapıldığında silinir,
- kayıt en çok 15 saniye sürer ve bitince mikrofon hemen serbest bırakılır,
- **otomatik puanlama yoktur**; kullanıcı kendi kaydını örnek sesle karşılaştırır.
