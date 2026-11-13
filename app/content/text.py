"""Metin normalizasyonu: kimlik üretimi, benzersizlik anahtarı ve arama."""

from __future__ import annotations

import re
import unicodedata

_TR_FOLD = str.maketrans({"ı": "i", "İ": "i", "I": "i"})
_SLUG_INVALID = re.compile(r"[^a-z0-9]+")
_WORD = re.compile(r"[a-z0-9']+")


def lemma_key(lemma: str) -> str:
    """Benzersizlik anahtarı: baştaki/sondaki boşluklar atılır, iç boşluklar teke iner, küçük harf."""
    return " ".join(lemma.split()).lower()


def slug(text: str) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return _SLUG_INVALID.sub("-", ascii_text.lower()).strip("-")


def word_id(lemma: str) -> str:
    return f"word.{slug(lemma_key(lemma))}"


def fold_text(text: str) -> str:
    """Arama için sadeleştirme: Türkçe ı/İ dâhil harfleri küçültür, aksanları kaldırır."""
    folded = unicodedata.normalize("NFKD", text.translate(_TR_FOLD).lower())
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def english_tokens(text: str) -> list[str]:
    """İngilizce cümleyi küçük harfli sözcüklere ayırır (tipografik kesme işareti dâhil)."""
    return _WORD.findall(text.lower().replace("’", "'"))


def fts_query(user_query: str) -> str | None:
    """Kullanıcı girdisini güvenli bir FTS5 sorgusuna çevirir (her sözcük ön ek araması)."""
    tokens = re.findall(r"[^\W_]+", fold_text(user_query))
    if not tokens:
        return None
    return " ".join(f'"{token}"*' for token in tokens[:8])


_VOWELS = "aeiou"


def regular_inflections(lemma: str) -> set[str]:
    """Tek sözcüklü bir temel biçimin kurallı çekim adaylarını üretir.

    Yalnızca eşleştirme için kullanılır (örnek cümlede kelimenin geçip geçmediğini
    denetlemek, boşluk doldurma sorusunda kelimeyi bulmak). Üretilen biçimler
    sözlüğe YAZILMAZ; düzensiz biçimler kaynak dosyada `forms` ile verilir.
    """
    word = lemma_key(lemma)
    if " " in word or len(word) < 2:
        return set()
    forms = {f"{word}s", f"{word}'s", f"{word}ed", f"{word}ing", f"{word}er", f"{word}est", f"{word}ly"}
    if word.endswith(("s", "x", "z", "ch", "sh", "o")):
        forms.add(f"{word}es")
    if word.endswith("y") and len(word) > 2 and word[-2] not in _VOWELS:
        stem = word[:-1]
        forms |= {f"{stem}ies", f"{stem}ied", f"{stem}ier", f"{stem}iest", f"{stem}ily"}
    if word.endswith("e"):
        stem = word[:-1]
        forms |= {f"{word}d", f"{stem}ing", f"{word}r", f"{word}st"}
    if word.endswith("ie"):
        forms.add(f"{word[:-2]}ying")
    if len(word) >= 3 and word[-1] not in _VOWELS + "wxy" and word[-2] in _VOWELS and word[-3] not in _VOWELS:
        doubled = word + word[-1]
        forms |= {f"{doubled}ed", f"{doubled}ing", f"{doubled}er", f"{doubled}est"}
    return forms


def find_word_span(sentence: str, candidates: set[str]) -> tuple[int, int] | None:
    """Cümlede adaylardan birinin (tam sözcük olarak) ilk geçtiği yerin konumunu bulur."""
    normalized = sentence.replace("’", "'")
    best: tuple[int, int] | None = None
    for candidate in candidates:
        match = re.search(rf"(?<![A-Za-z']){re.escape(candidate)}(?![A-Za-z])", normalized, flags=re.IGNORECASE)
        if match and (best is None or match.start() < best[0] or
                      (match.start() == best[0] and match.end() > best[1])):
            best = (match.start(), match.end())
    return best
