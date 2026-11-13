# İçerik ekleme kılavuzu

Eğitim içeriği `data/` altındaki YAML dosyalarında durur. Uygulama kodu değiştirilmeden
ders ve kelime eklenebilir.

```bash
python scripts/build_content.py --check   # yalnızca doğrula
python scripts/build_content.py           # doğrula ve data/build/content.db üret
```

## Dosyalar

| Dosya | İçerik |
|---|---|
| `data/sources.yaml` | Kaynaklar ve lisansları. Her ders ve kelime dosyası bir kaynağa bağlanır. |
| `data/curriculum/curriculum.yaml` | Seviyeler, üniteler ve ünitelerdeki ders sırası |
| `data/lessons/<seviye>/*.yaml` | Her dosya bir ders |
| `data/vocabulary/*.yaml` | Kelime dosyaları (seviye başına bir ya da daha çok) |

## Sıkıştırılmış kelime dosyası (`.psv`)

Büyük kelime listeleri için satır başına bir kelime içeren biçim kullanılır:

```
#! level: B1
#! source: original-cefrj
#! review_status: auto_checked
temel biçim | tür | Türkçe anlam | Örnek cümle. | Çevirisi. | düzensiz çekimler (isteğe bağlı)
break | v / n | kırmak / mola, ara | Do not break the glass. | Bardağı kırma. | breaks, broke, broken, breaking
```

- Tür kısaltmaları: `n v adj adv pron prep conj det art int num modal aux phr`
- Birden çok anlam için tür ve anlam alanları ` / ` ile ayrılır ve sayıları eşit olmalıdır.
- **Kurallı çekimleri yazmayın** (`works`, `worked`, `working`): doğrulayıcı bunları kendisi tanır.
  Yalnızca düzensiz ya da yazımı değişen biçimleri listeleyin (`children`, `went`, `bigger`).
- Başka bir kelimenin çekimiyle aynı yazılan bağımsız kelimeler (`building`, `left`, `rose`)
  `data/vocabulary/homographs.txt` dosyasına eklenmelidir; aksi hâlde içerik derlenmez.
  Bu kural, çekimli biçimlerin yanlışlıkla ayrı temel kelime olarak sayılmasını engeller.

### Yardımcı araçlar

```bash
python scripts/vocab_tools.py stats               # seviyelere göre benzersiz temel kelime sayısı
python scripts/vocab_tools.py candidates B2 200   # CEFR-J'de olup sözlükte olmayan kelimeler
python scripts/vocab_tools.py check-levels        # sözlük seviyeleri ile CEFR-J farkları
python scripts/vocab_tools.py ipa cmudict.dict    # data/pronunciation/ipa.tsv dosyasını yeniden üretir
python scripts/relevel.py                         # C1/C2'ye yazılmış ama CEFR-J'de seviyesi olan kelimeleri taşır
```

### Seviyeler ve kaynaklar

- **A1–B2:** kelime seçimi ve seviye, CEFR-J Wordlist 1.5'e dayanır (`data/reference/README.md`).
- **C1–C2:** CEFR-J bu seviyeleri kapsamaz; seviyeler bu projede atanmıştır (`source: original`).
- **IPA:** CMU Pronouncing Dictionary'den otomatik dönüştürülür (Amerikan İngilizcesi).
  CMUdict'te bulunmayan kelimelerde IPA alanı boş bırakılır.
- Türkçe anlamlar, örnek cümleler ve çeviriler projeye özgüdür.

## Kimlikler kalıcıdır

Kullanıcı ilerlemesi ders ve kelime kimliklerine bağlıdır. Yayımlanmış bir kimliği
**değiştirmeyin**: `gram.a1.to-be-present`, `word.book` (kelime kimliği temel biçimden türetilir).

## Kelime kaydı

```yaml
- lemma: child            # temel biçim — benzersiz (büyük/küçük harf ve boşluk farkı sayılmaz)
  pos: noun               # kısa yazım: tek anlam
  tr: çocuk
  forms: [children]       # çekimli biçimler; ayrı kelime olarak SAYILMAZ
  en: "The children are in the garden."   # örnek cümle
  ex_tr: "Çocuklar bahçede."              # çevirisi
  antonyms: [adult]       # hedef kelime sözlükte bulunmalıdır
  notes_tr: "..."
```

Birden çok anlam/örnek için `meanings: [{pos, tr, definition_en}]` ve `examples: [{en, tr}]`
kullanılır. İsteğe bağlı alanlar: `ipa`, `syllables`, `frequency_rank`, `collocations`,
`synonyms`, `related`. Bilinmeyen bilgi boş bırakılır; uydurulmaz.

## Ders dosyası

Zorunlu alanlar: `id, kind, level, title_tr, title_en, objective_tr, source, review_status, sections`.
Bağlantılar: `prerequisites`, `next`, `related` (ders kimlikleri), `vocabulary` (temel biçimler).

Bölüm türleri: `explanation, usage, formula, positive, negative, question, examples,
correct_incorrect, common_mistakes, comparison, exceptions, daily_life, review_tips`.
Her bölümde `text_tr` (boş satırla ayrılmış paragraflar; `**kalın**` desteklenir), `table`
(`headers`, `rows`) ve `examples` (`en`, `tr`, `note_tr`; yanlış kullanım için `wrong: true` +
`correction`) bulunabilir.

## Doğrulayıcının denetledikleri

- Bilinmeyen alan, eksik zorunlu alan, geçersiz seviye / kelime türü
- Yinelenen ders kimliği ya da temel kelime; temel biçimin `forms` içinde tekrarı
- Her örnek cümlenin Türkçe çevirisinin bulunması
- Kelime örneğinde kelimenin kendisinin ya da tanımlı bir çekiminin geçmesi
- Tüm bağlantıların (ders→ders, ders→kelime, kelime→kelime) gerçek bir hedefinin olması
- Her dersin bir üniteye yerleşmiş ve ünite seviyesiyle uyumlu olması
- Dil bilgisi derslerinde `explanation` ve `common_mistakes` bölümleri ile en az bir örnek
- Yanlış kullanım örneklerinde düzeltmenin bulunması

## review_status

- `draft` — taslak
- `auto_checked` — otomatik denetimlerden geçti
- `human_reviewed` — bir uzman gözden geçirdi. **Gerçekten gözden geçirilmeden bu değeri kullanmayın.**
