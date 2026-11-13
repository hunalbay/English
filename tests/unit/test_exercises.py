import random
import sqlite3

import pytest

from app.content import repository as repo
from app.content.text import find_word_span, regular_inflections
from app.database.content_db import connect_readonly
from app.learning import exercises


@pytest.fixture()
def conn(content_db):
    connection = connect_readonly(content_db)
    yield connection
    connection.close()


@pytest.fixture()
def a1_ids(conn):
    return repo.word_ids_for_level(conn, "A1")


def test_regular_inflections():
    assert {"stops", "stopped", "stopping"} <= regular_inflections("stop")
    assert {"studies", "studied", "studying"} <= regular_inflections("study")
    assert {"lives", "lived", "living"} <= regular_inflections("live")
    assert {"watches", "bigger", "biggest"} <= regular_inflections("watch") | regular_inflections("big")
    assert regular_inflections("ice cream") == set()


def test_find_word_span_whole_words_only():
    assert find_word_span("The cat is in the category.", {"cat"}) == (4, 7)
    assert find_word_span("A category.", {"cat"}) is None
    assert find_word_span("She isn’t here.", {"isn't"}) == (4, 9)


@pytest.mark.parametrize("kind", ["mc_en_tr", "mc_tr_en", "cloze"])
def test_multiple_choice_has_exactly_one_correct_option(conn, a1_ids, kind):
    for seed in range(5):
        questions = exercises.build(conn, kind, a1_ids, 10, random.Random(seed))
        assert len(questions) == 10
        for question in questions:
            ids = [option["id"] for option in question["options"]]
            assert len(ids) == len(set(ids)) == 4 and question["word_id"] in ids
            texts = [option["text"] for option in question["options"]]
            assert len(set(texts)) == 4
            # seçeneklerin Türkçe karşılıkları çakışmaz → tek doğru cevap
            briefs = repo.word_briefs(conn, ids)
            glosses = [exercises._glosses(b["meaning_tr"]) for b in briefs]
            for i in range(4):
                for j in range(i + 1, 4):
                    assert not glosses[i] & glosses[j], (question, briefs[i]["lemma"], briefs[j]["lemma"])


def test_house_and_home_never_compete(conn, a1_ids):
    """'home' ve 'house' ortak karşılık (ev) taşır; aynı soruda seçenek olamazlar."""
    for seed in range(40):
        for question in exercises.build(conn, "mc_tr_en", a1_ids, 20, random.Random(seed)):
            ids = {option["id"] for option in question["options"]}
            assert not {"word.home", "word.house"} <= ids


def test_cloze_blanks_the_word_and_gives_translation(conn, a1_ids):
    questions = exercises.build(conn, "cloze", a1_ids, 20, random.Random(1))
    for question in questions:
        assert question["prompt"].count(exercises.BLANK) == 1
        assert question["hint"]
        lemma = repo.word_briefs(conn, [question["word_id"]])[0]["lemma"]
        assert lemma in [option["text"] for option in question["options"]]


def test_antonym_questions_only_for_words_with_antonyms(conn, a1_ids):
    questions = exercises.build(conn, "antonym", a1_ids, 10, random.Random(3))
    assert questions
    for question in questions:
        antonyms = repo.related_word_ids(conn, question["word_id"], "antonym")
        option_ids = {option["id"] for option in question["options"]}
        assert len(option_ids & antonyms) == 1  # tam bir doğru seçenek
        assert exercises.grade(conn, "antonym", question["word_id"], next(iter(option_ids & antonyms)))["correct"]


def test_matching_groups(conn, a1_ids):
    questions = exercises.build(conn, "matching", a1_ids, 3, random.Random(2))
    assert len(questions) == 3
    for question in questions:
        assert len(question["left"]) == len(question["right"]) == 5
        assert {item["id"] for item in question["left"]} == {item["id"] for item in question["right"]}
        assert len({item["text"] for item in question["right"]}) == 5


def test_small_pool_returns_fewer_questions(conn):
    assert exercises.build(conn, "matching", ["word.book", "word.tea"], 5, random.Random(0)) == []
    assert exercises.build(conn, "mc_en_tr", [], 5, random.Random(0)) == []


def test_grade_multiple_choice_explains_wrong_choice(conn):
    right = exercises.grade(conn, "mc_en_tr", "word.book", "word.book")
    assert right["correct"] and right["correct_answer"] == "kitap" and right["word"]["example"]["tr"]
    wrong = exercises.grade(conn, "mc_en_tr", "word.book", "word.pen")
    assert not wrong["correct"]
    assert wrong["chosen"]["lemma"] == "pen" and wrong["chosen"]["meaning_tr"]


def test_grade_typing_normalization_and_alternatives(conn):
    assert exercises.grade(conn, "typing", "word.book", "  BOOK ")["correct"]
    assert exercises.grade(conn, "typing", "word.eat", "to eat")["correct"]
    inflected = exercises.grade(conn, "typing", "word.book", "books")
    assert not inflected["correct"] and "çekimli" in inflected["note"]
    other = exercises.grade(conn, "typing", "word.book", "pen")
    assert not other["correct"] and other["chosen"]["lemma"] == "pen"
    # aynı Türkçe karşılığı taşıyan başka kelime de kabul edilir
    alternative = exercises.grade(conn, "typing", "word.house", "home")
    assert alternative["correct"] and "house" in alternative["note"]
    assert not exercises.grade(conn, "typing", "word.book", "bok")["correct"]


def test_grade_rejects_bad_input(conn):
    with pytest.raises(ValueError):
        exercises.grade(conn, "typing", "word.book", "   ")
    with pytest.raises(LookupError):
        exercises.grade(conn, "mc_en_tr", "word.yok", "word.book")
    with pytest.raises(ValueError):
        exercises.grade(conn, "matching", "word.book", "x")


def test_grade_matching(conn):
    result = exercises.grade(conn, "matching", "word.book", {"word.book": "word.book", "word.pen": "word.tea", "word.tea": "word.pen"})
    assert not result["correct"]
    assert [r["correct"] for r in result["results"]] == [True, False, False]
