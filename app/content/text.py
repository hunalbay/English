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
