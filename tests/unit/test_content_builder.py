"""İçerik doğrulayıcının hatalı içeriği reddettiğini ve gerçek içeriğin tutarlı olduğunu sınar."""

import shutil
import sqlite3
from pathlib import Path

import pytest
import yaml

from app.content import builder
from tests.conftest import ROOT

DATA = ROOT / "data"


@pytest.fixture()
def data_copy(tmp_path) -> Path:
    target = tmp_path / "data"
    shutil.copytree(DATA, target, ignore=shutil.ignore_patterns("build", "audio"))
    return target


def _edit(path: Path, change) -> None:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _errors(data_dir: Path) -> str:
    with pytest.raises(builder.ContentError) as info:
        builder.load(data_dir)
    return "\n".join(info.value.errors)


def test_real_content_is_valid():
    content = builder.load(DATA)
    assert len(content.lessons) >= 3
    assert len(content.words) >= 100


def test_duplicate_lemma_rejected_even_with_different_case(data_copy):
    _edit(data_copy / "vocabulary" / "a1-core.yaml",
          lambda d: d["words"].append({"lemma": "Book ", "pos": "noun", "tr": "kitap"}))
    assert "yineleniyor" in _errors(data_copy)


def test_inflected_form_cannot_repeat_lemma(data_copy):
    def change(doc):
        next(w for w in doc["words"] if w["lemma"] == "book")["forms"] = ["books", "book"]
    _edit(data_copy / "vocabulary" / "a1-core.yaml", change)
    assert "çekimli biçimlerde" in _errors(data_copy)


def test_example_must_contain_word(data_copy):
    def change(doc):
        next(w for w in doc["words"] if w["lemma"] == "book")["en"] = "This is a pen."
    _edit(data_copy / "vocabulary" / "a1-core.yaml", change)
    assert "örnek cümlede kelime ya da çekimi geçmiyor" in _errors(data_copy)


def test_example_requires_translation(data_copy):
    def change(doc):
        del next(w for w in doc["words"] if w["lemma"] == "book")["ex_tr"]
    _edit(data_copy / "vocabulary" / "a1-core.yaml", change)
    assert "birlikte verilmelidir" in _errors(data_copy)


def test_broken_word_relation_rejected(data_copy):
    def change(doc):
        next(w for w in doc["words"] if w["lemma"] == "good")["antonyms"] = ["nonexistentword"]
    _edit(data_copy / "vocabulary" / "a1-core.yaml", change)
    assert "hedefi sözlükte yok" in _errors(data_copy)


def test_broken_lesson_link_rejected(data_copy):
    _edit(data_copy / "lessons" / "a1" / "subject-pronouns.yaml", lambda d: d.update(next=["gram.a1.yok"]))
    assert "next hedefi bulunamadı" in _errors(data_copy)


def test_lesson_vocabulary_must_exist(data_copy):
    _edit(data_copy / "lessons" / "a1" / "subject-pronouns.yaml", lambda d: d["vocabulary"].append("zzzz"))
    assert "ilgili kelime sözlükte yok" in _errors(data_copy)


def test_unknown_field_rejected(data_copy):
    _edit(data_copy / "lessons" / "a1" / "subject-pronouns.yaml", lambda d: d.update(tittle_tr="x"))
    assert "tittle_tr" in _errors(data_copy)


def test_grammar_lesson_requires_core_sections(data_copy):
    def change(doc):
        doc["sections"] = [s for s in doc["sections"] if s["kind"] != "common_mistakes"]
    _edit(data_copy / "lessons" / "a1" / "subject-pronouns.yaml", change)
    assert "'common_mistakes' bölümü zorunludur" in _errors(data_copy)


def test_wrong_example_requires_correction(data_copy):
    def change(doc):
        section = next(s for s in doc["sections"] if s["kind"] == "correct_incorrect")
        del section["examples"][0]["correction"]
    _edit(data_copy / "lessons" / "a1" / "subject-pronouns.yaml", change)
    assert "correction" in _errors(data_copy)


def test_unplaced_lesson_rejected(data_copy):
    _edit(data_copy / "curriculum" / "curriculum.yaml", lambda d: d["units"][0]["lessons"].pop())
    assert "hiçbir üniteye yerleştirilmemiş" in _errors(data_copy)


def test_failed_build_leaves_no_database(data_copy, tmp_path):
    _edit(data_copy / "lessons" / "a1" / "subject-pronouns.yaml", lambda d: d.update(next=["gram.a1.yok"]))
    output = tmp_path / "out" / "content.db"
    with pytest.raises(builder.ContentError):
        builder.build(data_copy, output)
    assert not output.exists() and not output.with_suffix(".tmp").exists()


def test_built_database_integrity(content_db):
    conn = sqlite3.connect(content_db)
    try:
        total, unique = conn.execute("SELECT COUNT(*), COUNT(DISTINCT lemma_key) FROM vocabulary").fetchone()
        assert total == unique >= 100
        # çekimli biçimle aynı yazılan temel kelimeler yalnızca açıkça izin verilenlerdir (homographs.txt)
        overlaps = {row[0] for row in conn.execute(
            "SELECT f.form FROM word_forms f JOIN vocabulary v ON v.lemma_key = f.form")}
        allowed = {line.strip() for line in (DATA / "vocabulary" / "homographs.txt").read_text(encoding="utf-8").splitlines()
                   if line.strip() and not line.startswith("#")}
        assert overlaps == allowed
        # her kelimenin anlamı, her dersin bölümü ve örneği vardır
        assert conn.execute(
            "SELECT COUNT(*) FROM vocabulary v WHERE NOT EXISTS (SELECT 1 FROM word_meanings m WHERE m.word_id = v.id)"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM lessons l WHERE NOT EXISTS (SELECT 1 FROM lesson_sections s WHERE s.lesson_id = l.id)"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM example_sentences WHERE TRIM(tr) = ''").fetchone()[0] == 0
        conn.execute("PRAGMA foreign_keys=ON")
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        meta = dict(conn.execute("SELECT key, value FROM content_meta"))
        assert meta["content_version"] == builder.CONTENT_VERSION
    finally:
        conn.close()


def test_inflected_form_cannot_be_added_as_separate_word(data_copy):
    """'worked' gibi bir çekim, ayrı temel kelime olarak eklenemez."""
    path = data_copy / "vocabulary" / "a1-01.psv"
    path.write_text(path.read_text(encoding="utf-8") + "brought | v | getirdi | He brought a cake. | Bir pasta getirdi.\n", encoding="utf-8")
    assert "çekimli biçimi olarak tanımlı" in _errors(data_copy)


def test_psv_format_errors_are_reported(data_copy):
    path = data_copy / "vocabulary" / "a1-01.psv"
    path.write_text(path.read_text(encoding="utf-8") + "zzz | n | deneme\nyyy | xx | deneme | A yyy. | Bir yyy.\n", encoding="utf-8")
    errors = _errors(data_copy)
    assert "5 ya da 6 alan bekleniyor" in errors and "bilinmeyen kelime türü: xx" in errors


def test_dictionary_has_at_least_5000_unique_base_words(content_db):
    """Hedef, gerçek veri tabanı üzerinden ölçülür; çekimli biçimler sayılmaz."""
    conn = sqlite3.connect(content_db)
    try:
        total, unique = conn.execute("SELECT COUNT(*), COUNT(DISTINCT lemma_key) FROM vocabulary").fetchone()
        assert total == unique >= 5000
        levels = dict(conn.execute("SELECT level, COUNT(*) FROM vocabulary GROUP BY level"))
        assert set(levels) == {"A1", "A2", "B1", "B2", "C1", "C2"} and min(levels.values()) >= 400
        # her kelimenin en az bir anlamı ve çevirili bir örnek cümlesi vardır
        assert conn.execute(
            "SELECT COUNT(*) FROM vocabulary v WHERE NOT EXISTS (SELECT 1 FROM example_sentences e WHERE e.word_id = v.id)"
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM vocabulary WHERE ipa IS NOT NULL").fetchone()[0] >= 4500
    finally:
        conn.close()


LESSON_FILE = ("lessons", "a1", "to-be-present.yaml")


def _edit_question(data_copy, index, change):
    _edit(data_copy.joinpath(*LESSON_FILE), lambda doc: change(doc["questions"][index]))


def test_question_needs_exactly_one_correct_option(data_copy):
    _edit_question(data_copy, 0, lambda q: q.update(options=[o.lstrip("*") for o in q["options"]]))
    assert "tam olarak bir doğru seçenek" in _errors(data_copy)


def test_two_correct_options_rejected(data_copy):
    _edit_question(data_copy, 0, lambda q: q.update(options=["*" + o.lstrip("*") for o in q["options"]]))
    assert "tam olarak bir doğru seçenek" in _errors(data_copy)


def test_every_option_needs_explanation(data_copy):
    _edit_question(data_copy, 0, lambda q: q["options"].__setitem__(1, "am"))
    assert "her seçeneğin açıklaması olmalıdır" in _errors(data_copy)


def test_fill_blank_needs_blank_and_answer(data_copy):
    _edit_question(data_copy, 2, lambda q: q.update(prompt="I twenty years old.", answers=[]))
    errors = _errors(data_copy)
    assert "en az bir kabul edilen cevap" in errors and "boşluk (___)" in errors


def test_duplicate_question_id_rejected(data_copy):
    _edit_question(data_copy, 1, lambda q: q.update(id="q.a1.to-be.01"))
    assert "soru kimliği yineleniyor" in _errors(data_copy)


def test_question_explanation_is_required(data_copy):
    _edit_question(data_copy, 0, lambda q: q.pop("explanation"))
    assert "explanation" in _errors(data_copy)


def test_question_links_must_exist(data_copy):
    _edit_question(data_copy, 0, lambda q: q.update(lessons=["gram.a1.yok"], vocabulary=["zzzzz"]))
    errors = _errors(data_copy)
    assert "ilgili ders bulunamadı" in errors and "ilgili kelime sözlükte yok" in errors


def test_every_real_question_is_linked_and_explained(content_db):
    conn = sqlite3.connect(content_db)
    try:
        total = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        assert total >= 30
        assert conn.execute("SELECT COUNT(*) FROM questions WHERE TRIM(explanation_tr) = ''").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM questions q WHERE NOT EXISTS (SELECT 1 FROM lessons l WHERE l.id = q.lesson_id)"
        ).fetchone()[0] == 0
        # seçenekli her soruda tam bir doğru seçenek ve her seçenekte açıklama
        assert conn.execute(
            """SELECT COUNT(*) FROM questions q WHERE q.evaluator = 'choice' AND
               (SELECT COUNT(*) FROM answer_options o WHERE o.question_id = q.id AND o.is_correct = 1) <> 1"""
        ).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM answer_options WHERE TRIM(explanation_tr) = ''").fetchone()[0] == 0
        assert conn.execute(
            """SELECT COUNT(*) FROM questions q WHERE q.evaluator = 'text'
               AND NOT EXISTS (SELECT 1 FROM accepted_answers a WHERE a.question_id = q.id)"""
        ).fetchone()[0] == 0
    finally:
        conn.close()
