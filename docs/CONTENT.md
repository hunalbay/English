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
