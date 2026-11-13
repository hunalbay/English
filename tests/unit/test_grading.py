import pytest

from app.assessment import grading


def q(evaluator, **extra):
    base = {"evaluator": evaluator, "type": "fill_blank", "grading": "normalized", "accepted": [], "options": [], "data": {}}
    return {**base, **extra}


def test_normalize_ignores_case_spacing_final_punctuation_and_contraction_form():
    assert grading.normalize("  She   ISN’T at home. ") == "she is not at home"
    assert grading.normalize("I'm fine, thanks!") == "i am fine thanks"
    assert grading.normalize("I can't swim") == grading.normalize("I cannot swim")
    # belirsiz kısaltmalar açılmaz
    assert grading.normalize("Tom's here") == "tom's here"


def test_text_normalized_accepts_variants():
    question = q("text", accepted=["She is not at home.", "She's not at home."])
    for answer in ("she isn't at home", "She is not at home", "SHE'S NOT AT HOME!"):
        assert grading.grade(question, answer) == {"result": "correct"}
    assert grading.grade(question, "She not at home")["result"] == "incorrect"


def test_text_strict_checks_case_and_punctuation():
    question = q("text", grading="strict", accepted=["Tom and I are friends."])
    assert grading.grade(question, "Tom and I are friends.")["result"] == "correct"
    assert grading.grade(question, " Tom  and I are friends. ")["result"] == "correct"  # yalnızca boşluk farkı
    lowercase = grading.grade(question, "Tom and i are friends.")
    assert lowercase == {"result": "incorrect", "near_miss": True}
    assert grading.grade(question, "Tom and I are friends")["near_miss"] is True       # nokta eksik
    assert grading.grade(question, "Tom and me are friends.")["near_miss"] is False


def test_open_ended_text_is_never_marked_wrong_automatically():
    question = q("text", type="translation", accepted=["They are happy."])
    assert grading.grade(question, "they're happy")["result"] == "correct"
    assert grading.grade(question, "They are glad.") == {"result": "ungraded"}
    # kabul edilen cevapla hiç ilgisi olmayan cevap ise yanlıştır
    assert grading.grade(question, "xyz")["result"] == "incorrect"
    assert grading.grade(question, "I like tea")["result"] == "incorrect"


def test_choice():
    question = q("choice", options=[{"position": 1, "is_correct": False}, {"position": 2, "is_correct": True}])
    assert grading.grade(question, 2)["result"] == "correct"
    assert grading.grade(question, 1)["result"] == "incorrect"
    for bad in (9, "2", True, None):
        with pytest.raises(ValueError):
            grading.grade(question, bad)


def test_word_order_with_alternatives():
    question = q("order", data={"tokens": ["I", "usually", "walk"], "also": [["usually", "I", "walk"]]})
    assert grading.grade(question, ["I", "usually", "walk"])["result"] == "correct"
    assert grading.grade(question, ["usually", "I", "walk"])["result"] == "correct"
    assert grading.grade(question, ["walk", "I", "usually"])["result"] == "incorrect"
    with pytest.raises(ValueError):
        grading.grade(question, ["I", "walk"])


def test_matching_reports_each_pair():
    question = q("matching", data={"pairs": [["I", "ben"], ["we", "biz"], ["they", "onlar"]]})
    right = grading.grade(question, {"I": "ben", "we": "biz", "they": "onlar"})
    assert right["result"] == "correct"
    wrong = grading.grade(question, {"I": "ben", "we": "onlar", "they": "biz"})
    assert wrong["result"] == "incorrect" and [p["correct"] for p in wrong["pairs"]] == [True, False, False]
    with pytest.raises(ValueError):
        grading.grade(question, {"I": "ben"})


def test_free_writing_is_ungraded():
    assert grading.grade(q("self"), "I am Deniz.") == {"result": "ungraded"}
    for bad in ("   ", 5, "x" * 5000):
        with pytest.raises(ValueError):
            grading.grade(q("self"), bad)


def test_empty_or_oversized_text_rejected():
    for bad in ("", "  ", None, "x" * 600):
        with pytest.raises(ValueError):
            grading.grade(q("text", accepted=["a"]), bad)
