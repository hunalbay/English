"""Kurallı cevap değerlendirme.

Sonuç değerleri:
- "correct" / "incorrect": kesin değerlendirme (seçenekli, sıralama, eşleştirme, kabul listesiyle eşleşen metin)
- "ungraded": program kesin karar veremez; kullanıcı örnek cevapla karşılaştırıp kendini değerlendirir.

Çeviri ve serbest yazı gibi birden çok doğru biçimi olabilen cevaplarda, kabul listesiyle eşleşmeyen
bir cevap "yanlış" sayılmaz; "ungraded" döner ve sınırlılık kullanıcıya açıkça bildirilir.
"""

from __future__ import annotations

import re
from typing import Any

# Yalnızca tek anlamlı kısaltmalar açılır ("'s" ve "'d" belirsiz olduğu için açılmaz).
_CONTRACTIONS = {
    "i'm": "i am", "you're": "you are", "we're": "we are", "they're": "they are",
    "isn't": "is not", "aren't": "are not", "wasn't": "was not", "weren't": "were not",
    "don't": "do not", "doesn't": "does not", "didn't": "did not",
    "can't": "cannot", "can not": "cannot", "couldn't": "could not", "won't": "will not",
    "wouldn't": "would not", "shouldn't": "should not", "mustn't": "must not",
    "haven't": "have not", "hasn't": "has not", "hadn't": "had not",
    "i've": "i have", "you've": "you have", "we've": "we have", "they've": "they have",
    "i'll": "i will", "you'll": "you will", "he'll": "he will", "she'll": "she will",
    "it'll": "it will", "we'll": "we will", "they'll": "they will",
    "there's": "there is", "that's": "that is", "what's": "what is", "where's": "where is",
    "who's": "who is", "how's": "how is", "it's": "it is", "he's": "he is", "she's": "she is",
    "let's": "let us",
}
_CONTRACTION_RE = re.compile(
    r"(?<![a-z'])(" + "|".join(sorted((re.escape(k) for k in _CONTRACTIONS), key=len, reverse=True)) + r")(?![a-z'])"
)

# Birden çok doğru biçimi olabilen tipler: kabul listesiyle eşleşmeyen cevap kesin yanlış sayılmaz.
OPEN_ENDED_TYPES = frozenset({"translation", "sentence_building"})


OPEN_ENDED_MIN_OVERLAP = 0.34


def _best_overlap(answer: str, accepted: list[str]) -> float:
    """Cevabın, kabul edilen cevaplardan en çok benzediğiyle ortak sözcük oranı (Jaccard)."""
    words = set(normalize(answer).split())
    best = 0.0
    for item in accepted:
        other = set(normalize(item).split())
        if words | other:
            best = max(best, len(words & other) / len(words | other))
    return best


def clean(text: str) -> str:
    """Her kipte uygulanan temel temizlik: tırnak işareti biçimi ve fazla boşluklar."""
    return " ".join(text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').split())


def normalize(text: str) -> str:
    """Esnek karşılaştırma: büyük/küçük harf, sondaki noktalama, virgüller ve kısaltma biçimi önemsenmez."""
    value = clean(text).lower()
    value = _CONTRACTION_RE.sub(lambda match: _CONTRACTIONS[match.group(1)], value)
    value = re.sub(r"[.!?]+$", "", value).replace(",", "")
    return " ".join(value.split())


def text_matches(answer: str, accepted: list[str], grading: str) -> bool:
    if grading == "strict":  # yazım ve noktalama ölçülen sorular
        return clean(answer) in {clean(item) for item in accepted}
    return normalize(answer) in {normalize(item) for item in accepted}


def grade(question: dict, answer: Any) -> dict:
    """Soruyu değerlendirir. `question`, repository.question_for_grading() çıktısıdır."""
    evaluator = question["evaluator"]

    if evaluator == "choice":
        if not isinstance(answer, int) or isinstance(answer, bool):
            raise ValueError("Bir seçenek işaretleyin.")
        option = next((o for o in question["options"] if o["position"] == answer), None)
        if option is None:
            raise ValueError("Geçersiz seçenek.")
        return {"result": "correct" if option["is_correct"] else "incorrect"}

    if evaluator == "text":
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("Cevap boş olamaz.")
        if len(answer) > 500:
            raise ValueError("Cevap çok uzun.")
        if text_matches(answer, question["accepted"], question["grading"]):
            return {"result": "correct"}
        if question["type"] in OPEN_ENDED_TYPES:
            # Kabul edilen cevaplarla yeterince ortak sözcüğü olan cevap başka bir doğru biçim olabilir;
            # program bunu kesin değerlendiremez. Hiç benzemeyen cevap ise yanlıştır.
            if _best_overlap(answer, question["accepted"]) >= OPEN_ENDED_MIN_OVERLAP:
                return {"result": "ungraded"}
            return {"result": "incorrect", "near_miss": False}
        # Yazım/noktalama ölçülen soruda cevap yalnızca bu yönden farklıysa kullanıcıya bildirilir.
        near = question["grading"] == "strict" and text_matches(answer, question["accepted"], "normalized")
        return {"result": "incorrect", "near_miss": near}

    if evaluator == "order":
        if not isinstance(answer, list) or not all(isinstance(token, str) for token in answer):
            raise ValueError("Sözcük sırası bekleniyor.")
        tokens = question["data"]["tokens"]
        if sorted(answer) != sorted(tokens):
            raise ValueError("Bütün sözcükleri kullanın.")
        accepted = [tokens, *question["data"].get("also", [])]
        return {"result": "correct" if answer in accepted else "incorrect"}

    if evaluator == "matching":
        pairs = dict(question["data"]["pairs"])
        if not isinstance(answer, dict) or set(answer) != set(pairs):
            raise ValueError("Bütün öğeleri eşleştirin.")
        details = [{"left": left, "chosen": answer[left], "right": right, "correct": answer[left] == right}
                   for left, right in pairs.items()]
        return {"result": "correct" if all(d["correct"] for d in details) else "incorrect", "pairs": details}

    # self: serbest yazı — program değerlendirmez
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Cevap boş olamaz.")
    if len(answer) > 4000:
        raise ValueError("Cevap çok uzun.")
    return {"result": "ungraded"}
