"""Her sorunun cevap anahtarı, programın kendi değerlendiricisi tarafından doğru kabul edilmelidir.

Bu test, içerik yazarken yapılan hataları yakalar: yazım ya da noktalama yüzünden reddedilen kabul edilen
cevaplar, sıralama sorularında eşleşmeyen alternatifler, doğru seçeneği olmayan sorular vb.
"""

import re
import sqlite3

import pytest

from app.assessment import grading
from app.content import repository as repo


@pytest.fixture(scope="module")
def questions(content_db):
    conn = sqlite3.connect(content_db)
    conn.row_factory = sqlite3.Row
    ids = [row[0] for row in conn.execute("SELECT id FROM questions ORDER BY id")]
    yield [repo.question_for_grading(conn, qid) for qid in ids]
    conn.close()


def test_every_answer_key_is_graded_correct(questions):
    problems = []
    for q in questions:
        evaluator = q["evaluator"]
        if evaluator == "choice":
            right = [o for o in q["options"] if o["is_correct"]]
            if len(right) != 1 or grading.grade(q, right[0]["position"])["result"] != "correct":
                problems.append(q["id"])
            for wrong in (o for o in q["options"] if not o["is_correct"]):
                if grading.grade(q, wrong["position"])["result"] != "incorrect":
                    problems.append(q["id"] + " (yanlış seçenek doğru sayıldı)")
        elif evaluator == "text":
            for answer in q["accepted"]:
                if grading.grade(q, answer)["result"] != "correct":
                    problems.append(f"{q['id']}: {answer!r}")
        elif evaluator == "order":
            for tokens in [q["data"]["tokens"], *q["data"].get("also", [])]:
                if grading.grade(q, list(tokens))["result"] != "correct":
                    problems.append(f"{q['id']}: {tokens}")
        elif evaluator == "matching":
            pairs = dict(q["data"]["pairs"])
            if grading.grade(q, pairs)["result"] != "correct":
                problems.append(q["id"])
    assert problems == []


def test_obviously_wrong_text_answers_are_not_accepted(questions):
    """Anlamsız bir cevap hiçbir yazılı soruda doğru sayılmamalıdır."""
    accepted = [q["id"] for q in questions if q["evaluator"] == "text"
                and grading.grade(q, "qwerty asdf")["result"] == "correct"]
    assert accepted == []


# Kaçış karakteri kalıntısı, yer tutucu, çift boşluk, sekme, ayrıştırılmamış seçenek ayracı,
# noktalama öncesi boşluk (bilerek kullanılan " ..." üç noktası hariç).
ARTIFACTS = re.compile(r'\\"|TODO|XXX|(?<!\n)  (?!\n)|\t|::| ,| \.(?!\.)')


def test_question_texts_have_no_authoring_artifacts(questions):
    """Kaçış karakteri kalıntısı, yer tutucu ya da çift boşluk gibi yazım artıkları."""
    bad = []
    for q in questions:
        texts = [q["prompt"], q["explanation_tr"], q["context"] or "", *(o["text"] for o in q["options"]),
                 *(o["explanation_tr"] or "" for o in q["options"]), *q["accepted"]]
        for text in texts:
            if ARTIFACTS.search(text):
                bad.append(f"{q['id']}: {text[:60]!r}")
    assert bad == []
