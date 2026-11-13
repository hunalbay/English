"""Sözlükten otomatik üretilen kelime alıştırmaları ve kurallı değerlendirme.

Türler:
- mc_en_tr   İngilizce kelime → doğru Türkçe anlamı seç
- mc_tr_en   Türkçe anlam → doğru İngilizce kelimeyi seç
- typing     Türkçe anlam → İngilizce kelimeyi yaz
- cloze      Örnek cümlede boş bırakılan kelimeyi seç (çevirisi ipucu olarak verilir)
- antonym    Zıt anlamlı kelimeyi seç (yalnızca zıt anlamı tanımlı kelimeler için)
- matching   Beş İngilizce kelimeyi Türkçe karşılıklarıyla eşleştir

Çeldiriciler aynı türden kelimelerden seçilir. Doğru cevapla ortak bir Türkçe karşılığı
olan ya da ilişkili (eş/zıt anlamlı) kelimeler çeldirici yapılmaz; böylece bir soruda
birden fazla doğru seçenek oluşması engellenir.
"""

from __future__ import annotations

import random
import re
import sqlite3
from typing import Any

from app.content import repository as repo
from app.content.text import find_word_span, lemma_key, regular_inflections

EXERCISE_TYPES = ("mc_en_tr", "mc_tr_en", "typing", "cloze", "antonym", "matching")
OPTION_COUNT = 4
MATCHING_SIZE = 5
BLANK = "_____"

# Alıştırmanın ilgili olduğu kart yönü (yanlış cevapta o yöndeki kart yeniden sorulur).
DIRECTION = {
    "mc_en_tr": "en_tr", "matching": "en_tr", "antonym": "en_tr",
    "mc_tr_en": "tr_en", "typing": "tr_en", "cloze": "tr_en",
}


def _glosses(meaning_tr: str) -> set[str]:
    return {part.strip().lower() for part in re.split(r"[;,/]", meaning_tr) if part.strip()}


def _distractors(conn: sqlite3.Connection, card: dict, rng: random.Random, count: int, exclude: set[str]) -> list[dict]:
    """Doğru cevapla karışmayacak çeldiriciler seçer."""
    pos = card["pos"][0] if card["pos"] else "noun"
    target = _glosses(card["meaning_tr"])
    blocked = {card["id"], *exclude, *repo.related_word_ids(conn, card["id"])}
    pool = [
        other for other in repo.distractor_pool(conn, card["level"], pos)
        if other["id"] not in blocked and not (_glosses(other["meaning_tr"]) & target)
    ]
    same_level = [other for other in pool if other["level"] == card["level"]]
    source = same_level if len(same_level) >= count * 3 else pool
    chosen: list[dict] = []
    seen: set[str] = set()
    for other in rng.sample(source, len(source)):
        glosses = _glosses(other["meaning_tr"])
        if glosses & seen:
            continue  # çeldiriciler de birbirinden farklı anlamda olmalı
        seen |= glosses
        chosen.append(other)
        if len(chosen) == count:
            break
    return chosen


def _options(rng: random.Random, correct: dict, distractors: list[dict], text_key: str) -> list[dict]:
    options = [{"id": item["id"], "text": item[text_key]} for item in (correct, *distractors)]
    rng.shuffle(options)
    return options


def _cloze_sentence(card: dict) -> str | None:
    if not card["example"]:
        return None
    candidates = {lemma_key(card["lemma"]), *card["forms"], *regular_inflections(card["lemma"])}
    span = find_word_span(card["example"]["en"], candidates)
    if span is None:
        return None
    sentence = card["example"]["en"].replace("’", "'")
    return f"{sentence[: span[0]]}{BLANK}{sentence[span[1] :]}"


def build(conn: sqlite3.Connection, kind: str, word_ids: list[str], size: int, rng: random.Random) -> list[dict]:
    """İstenen türde en çok `size` soru üretir. Uygun veri yoksa daha az (ya da hiç) soru döner."""
    if kind not in EXERCISE_TYPES:
        raise ValueError(kind)
    if kind == "antonym":
        word_ids = repo.words_with_antonyms(conn, word_ids)
    wanted = size * MATCHING_SIZE * 2 if kind == "matching" else size * 3
    picked = rng.sample(word_ids, min(len(word_ids), wanted))
    cards = repo.study_cards(conn, picked)

    if kind == "matching":
        return _matching(cards, size, rng)

    questions: list[dict] = []
    for card in cards:
        if len(questions) == size:
            break
        question: dict[str, Any] = {"type": kind, "word_id": card["id"]}
        if kind == "typing":
            question.update(prompt=card["meaning_tr"], prompt_lang="tr", first_letter=card["lemma"][0],
                            length=len(card["lemma"]))
        elif kind == "antonym":
            antonyms = repo.word_briefs(conn, sorted(repo.related_word_ids(conn, card["id"], "antonym")))
            if not antonyms:
                continue
            correct = rng.choice(antonyms)
            distractors = _distractors(conn, card, rng, OPTION_COUNT - 1, exclude={a["id"] for a in antonyms})
            if len(distractors) < OPTION_COUNT - 1:
                continue
            question.update(prompt=card["lemma"], prompt_lang="en", hint=card["meaning_tr"],
                            options=_options(rng, correct, distractors, "lemma"))
        else:
            distractors = _distractors(conn, card, rng, OPTION_COUNT - 1, exclude=set())
            if len(distractors) < OPTION_COUNT - 1:
                continue
            if kind == "mc_en_tr":
                question.update(prompt=card["lemma"], prompt_lang="en",
                                options=_options(rng, card, distractors, "meaning_tr"))
            elif kind == "mc_tr_en":
                question.update(prompt=card["meaning_tr"], prompt_lang="tr",
                                options=_options(rng, card, distractors, "lemma"))
            else:  # cloze
                sentence = _cloze_sentence(card)
                if sentence is None:
                    continue
                question.update(prompt=sentence, prompt_lang="en", hint=card["example"]["tr"],
                                options=_options(rng, card, distractors, "lemma"))
        questions.append(question)
    return questions


def _matching(cards: list[dict], size: int, rng: random.Random) -> list[dict]:
    """Her soru, anlamları birbirinden farklı MATCHING_SIZE kelimelik bir eşleştirme kümesidir."""
    questions: list[dict] = []
    remaining = list(cards)
    while len(questions) < size and len(remaining) >= MATCHING_SIZE:
        group: list[dict] = []
        seen: set[str] = set()
        rest: list[dict] = []
        for card in remaining:
            glosses = _glosses(card["meaning_tr"])
            if len(group) < MATCHING_SIZE and not (glosses & seen):
                group.append(card)
                seen |= glosses
            else:
                rest.append(card)
        remaining = rest
        if len(group) < MATCHING_SIZE:
            break
        right = [{"id": card["id"], "text": card["meaning_tr"]} for card in group]
        rng.shuffle(right)
        questions.append({
            "type": "matching",
            "word_id": group[0]["id"],
            "left": [{"id": card["id"], "text": card["lemma"]} for card in group],
            "right": right,
        })
    return questions


def normalize_typed(text: str) -> str:
    """Yazılı cevap karşılaştırması: büyük/küçük harf, baş/son boşluk ve baştaki 'to ' önemsenmez."""
    value = " ".join(text.replace("’", "'").split()).lower()
    return value[3:] if value.startswith("to ") else value


def grade(conn: sqlite3.Connection, kind: str, word_id: str, answer: Any) -> dict:
    """Cevabı değerlendirir. Dönen sözlük: correct, results (kelime bazında) ve açıklama verisi."""
    card = repo.study_cards(conn, [word_id])
    if not card:
        raise LookupError(word_id)
    target = card[0]

    if kind == "matching":
        if not isinstance(answer, dict) or not answer:
            raise ValueError("Eşleştirme cevabı bekleniyor.")
        cards = {c["id"]: c for c in repo.study_cards(conn, list(answer.keys()))}
        if len(cards) != len(answer):
            raise LookupError("Bilinmeyen kelime.")
        results = [
            {"word_id": left, "correct": left == chosen, "lemma": cards[left]["lemma"], "meaning_tr": cards[left]["meaning_tr"]}
            for left, chosen in answer.items()
        ]
        return {"correct": all(r["correct"] for r in results), "results": results}

    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("Cevap boş olamaz.")

    chosen = None
    if kind == "typing":
        typed = normalize_typed(answer)
        correct = typed == lemma_key(target["lemma"])
        correct_text = target["lemma"]
    elif kind == "antonym":
        antonym_ids = repo.related_word_ids(conn, word_id, "antonym")
        correct = answer in antonym_ids
        correct_text = ", ".join(w["lemma"] for w in repo.word_briefs(conn, sorted(antonym_ids)))
        chosen = answer
    else:
        correct = answer == word_id
        correct_text = target["meaning_tr"] if kind == "mc_en_tr" else target["lemma"]
        chosen = answer

    feedback: dict[str, Any] = {
        "correct": correct,
        "correct_answer": correct_text,
        "word": {key: target[key] for key in ("id", "lemma", "meaning_tr", "level", "example", "notes_tr")},
        "results": [{"word_id": word_id, "correct": correct}],
        "chosen": None,
    }
    if chosen and not correct:
        other = repo.word_briefs(conn, [chosen])
        if other:  # yanlış seçilen seçeneğin gerçekte ne anlama geldiği
            feedback["chosen"] = {key: other[0][key] for key in ("id", "lemma", "meaning_tr")}
    if kind == "typing" and not correct:
        hit = repo.lookup_form(conn, normalize_typed(answer))
        if hit == word_id:
            feedback["note"] = "Kelimenin çekimli bir biçimini yazdınız; temel biçimi bekleniyordu."
        elif hit:
            other = repo.word_briefs(conn, [hit])[0]
            if _glosses(other["meaning_tr"]) & _glosses(target["meaning_tr"]):
                # Aynı Türkçe karşılığı taşıyan başka bir kelime de doğru kabul edilir.
                feedback["correct"] = True
                feedback["results"] = [{"word_id": word_id, "correct": True}]
                feedback["note"] = f"\"{other['lemma']}\" de doğru bir karşılıktır. Bu soruda beklenen kelime: {target['lemma']}."
            else:
                feedback["chosen"] = {key: other[key] for key in ("id", "lemma", "meaning_tr")}
    return feedback
