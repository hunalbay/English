"""Okuma, dinleme, yazma ve telaffuz uçları."""

import sqlite3

import pytest

API = "/api/v1"
TRACKS = ("reading", "listening", "writing", "pronunciation")


@pytest.mark.parametrize("track", TRACKS)
def test_track_summary_and_units(client, track):
    data = client.get(f"{API}/tracks/{track}").json()
    assert data["track"] == track
    assert [level["code"] for level in data["levels"]] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    assert data["levels"][0]["lesson_count"] >= 1 and data["levels"][0]["completed_lessons"] == 0
    units = client.get(f"{API}/levels/A1/units?track={track}").json()
    assert units["track"] == track and units["units"]
    assert all(lesson["kind"] == track for unit in units["units"] for lesson in unit["lessons"])


def test_unknown_track_rejected(client):
    assert client.get(f"{API}/tracks/speaking").status_code == 422
    assert client.get(f"{API}/levels/A1/units?track=nope").status_code == 422


def test_lessons_page_lists_only_grammar(client):
    units = client.get(f"{API}/levels/A1/units").json()["units"]
    kinds = {lesson["kind"] for unit in units for lesson in unit["lessons"]}
    assert kinds == {"grammar"}
    totals = client.get(f"{API}/dashboard").json()["totals"]
    assert totals["tracks"]["reading"] >= 10 and totals["lessons"] == totals["tracks"]["grammar"]


def test_reading_lesson_has_passage_with_translations(client):
    lesson = client.get(f"{API}/lessons/read.a1.my-family").json()
    assert lesson["track"] == "reading" and lesson["kind"] == "reading"
    passage = lesson["passage"]
    assert passage["mode"] == "text" and "audio" not in passage
    assert all(line["en"] and line["tr"] and line["speaker"] is None for line in passage["lines"])
    assert {"en": "garden", "tr": "bahçe"} in passage["glossary"]
    assert lesson["practice"] == [] and lesson["question_count"] >= 4


def test_listening_lesson_has_dialogue_and_audio(client):
    lesson = client.get(f"{API}/lessons/listen.a1.at-the-cafe").json()
    passage = lesson["passage"]
    assert passage["mode"] == "dialogue"
    assert {line["speaker"] for line in passage["lines"]} == {"Waiter", "Customer"}
    audio = passage["audio"]
    assert audio and audio["url"].startswith("/media/clips/") and audio["duration_ms"] > 5000
    response = client.get(audio["url"])
    assert response.status_code == 200 and response.headers["content-type"] == "audio/mpeg"
    assert len(response.content) > 10_000
    units = client.get(f"{API}/levels/A1/units?track=listening").json()["units"]
    assert all(item["has_audio"] for unit in units for item in unit["lessons"])


def test_pronunciation_lesson_has_practice_items_with_audio(client):
    lesson = client.get(f"{API}/lessons/pron.a1.th-sounds").json()
    assert lesson["passage"] is None and len(lesson["practice"]) >= 8
    first = lesson["practice"][0]
    assert first["en"] == "think" and first["ipa"] and first["tr"]
    assert all(item["audio"] and item["audio"]["url"].endswith(".mp3") for item in lesson["practice"])


def test_word_has_audio(client):
    word = client.get(f"{API}/vocabulary/word.teacher").json()
    assert word["audio"]["url"].startswith("/media/clips/")
    assert client.get(word["audio"]["url"]).status_code == 200


def test_media_path_cannot_escape_audio_folder(client):
    assert client.get("/media/clips/../manifest.json").status_code == 404
    assert client.get("/media/clips/%2e%2e/%2e%2e/build/content.db").status_code == 404


def test_listening_question_gets_audio_but_not_the_transcript(client, auth):
    test = client.post(f"{API}/tests/sessions", json={"lesson_id": "listen.a1.at-the-cafe"}, headers=auth).json()
    listening = [q for q in test["questions"] if q["type"] == "listening_comprehension"]
    assert len(listening) >= 3
    for question in listening:
        assert question["audio"]["url"].startswith("/media/clips/") and question["audio_missing"] is False
        assert "passage" not in question and question["context"] is None
    payload = str(test)
    assert "we don't have cheese sandwiches" not in payload  # yazılı metin cevaptan önce gönderilmez


def test_reading_question_gets_passage_without_translation(client, auth):
    test = client.post(f"{API}/tests/sessions", json={"lesson_id": "read.a1.my-family"}, headers=auth).json()
    reading = [q for q in test["questions"] if q["type"] == "reading_comprehension"]
    assert reading
    for question in reading:
        assert question["passage"]["lines"][0]["en"].startswith("Hello! My name is Elif.")
        assert all("tr" not in line for line in question["passage"]["lines"])
        assert "audio" not in question


def test_writing_lesson_tasks_are_self_assessed(client, auth):
    test = client.post(f"{API}/tests/sessions", json={"lesson_id": "write.a1.introducing-yourself"}, headers=auth).json()
    task = next(q for q in test["questions"] if q["type"] == "written_answer")
    assert task["evaluator"] == "self" and len(task["checklist"]) >= 3
    feedback = client.post(
        f"{API}/tests/sessions/{test['session_id']}/answers",
        json={"question_id": task["id"], "answer": "My name is Deniz. I am from Antalya."}, headers=auth,
    ).json()
    assert feedback["result"] == "ungraded" and feedback["model_answers"]


def test_skill_lesson_progress_is_recorded(client, auth):
    lesson_id = "read.a1.my-family"
    client.put(f"{API}/lessons/{lesson_id}/completion", json={"completed": True}, headers=auth)
    levels = client.get(f"{API}/tracks/reading").json()["levels"]
    assert levels[0]["completed_lessons"] == 1
    # dil bilgisi ilerlemesi etkilenmez
    grammar = client.get(f"{API}/levels").json()["levels"][0]
    assert grammar["completed_lessons"] == 0


def test_audio_missing_is_reported_not_an_error(client, auth, settings, monkeypatch, tmp_path):
    """Ses kaydı olmayan bir içerikte uçlar hata vermez; ses alanı boş döner."""
    copy = tmp_path / "silent.db"
    copy.write_bytes(settings.content_db_path.read_bytes())
    conn = sqlite3.connect(copy)
    conn.execute("DELETE FROM audio_clips")
    conn.commit()
    conn.close()

    from app.core.config import load_settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    silent = create_app(load_settings(data_dir=tmp_path / "u2", content_db_path=copy))
    with TestClient(silent, base_url="http://127.0.0.1:8765") as quiet:
        token = {"X-EM-Token": quiet.get(f"{API}/session").json()["token"]}
        lesson = quiet.get(f"{API}/lessons/listen.a1.at-the-cafe").json()
        assert lesson["passage"]["audio"] is None and lesson["passage"]["lines"]
        assert quiet.get(f"{API}/vocabulary/word.teacher").json()["audio"] is None
        practice = quiet.get(f"{API}/lessons/pron.a1.th-sounds").json()["practice"]
        assert all(item["audio"] is None for item in practice)
        test = quiet.post(f"{API}/tests/sessions", json={"lesson_id": "listen.a1.at-the-cafe"}, headers=token).json()
        question = next(q for q in test["questions"] if q["type"] == "listening_comprehension")
        assert question["audio"] is None and question["audio_missing"] is True
        units = quiet.get(f"{API}/levels/A1/units?track=listening").json()["units"]
        assert not any(item["has_audio"] for unit in units for item in unit["lessons"])
