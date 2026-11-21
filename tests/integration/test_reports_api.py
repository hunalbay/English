"""Seviye tespit sınavı, analiz ve ilerleme raporu."""

import sqlite3

from app.content import repository as repo

API = "/api/v1"


def _content(content_db):
    conn = sqlite3.connect(content_db)
    conn.row_factory = sqlite3.Row
    return conn


def _answer_value(question: dict, right: bool):
    """Sorunun doğru (ya da bilerek yanlış) cevabı."""
    if question["evaluator"] == "choice":
        options = question["options"]
        option = next(o for o in options if o["is_correct"] == right)
        return option["position"]
    assert question["evaluator"] == "text"
    return question["accepted"][0] if right else "zzz wrong zzz"


def _answer_block(client, auth, content, session_id, questions, right_count):
    for index, item in enumerate(questions):
        full = repo.question_for_grading(content, item["id"])
        value = _answer_value(full, index < right_count)
        response = client.post(f"{API}/tests/sessions/{session_id}/answers",
                               json={"question_id": item["id"], "answer": value}, headers=auth)
        assert response.status_code == 200, response.text
        assert response.json()["result"] == ("correct" if index < right_count else "incorrect")


def test_placement_overview_states_limits(client):
    data = client.get(f"{API}/placement").json()
    assert data["block_size"] == 8 and data["pass_mark"] == 6 and data["history"] == []
    assert "konuşma, yazma ve dinleme" in data["limits_tr"].lower()


def test_placement_blocks_have_safe_types_and_mixed_tracks(client, auth, content_db):
    data = client.post(f"{API}/placement/sessions", json={"start_level": "B1", "seed": 3}, headers=auth).json()
    assert data["current_level"] == "B1" and data["block_number"] == 1 and len(data["questions"]) == 8
    content = _content(content_db)
    tracks = repo.lesson_tracks(content, [repo.question_for_grading(content, q["id"])["lesson_id"] for q in data["questions"]])
    assert set(tracks.values()) <= {"grammar", "reading", "expressions"}
    assert {"reading", "expressions"} <= set(tracks.values())
    assert all(q["evaluator"] in ("choice", "text") and q["type"] not in ("translation", "written_answer")
               for q in data["questions"])
    assert all(q["level"] == "B1" for q in data["questions"])
    assert len({q["id"] for q in data["questions"]}) == 8


def test_placement_requires_all_answers_before_next(client, auth):
    data = client.post(f"{API}/placement/sessions", json={"seed": 1}, headers=auth).json()
    response = client.post(f"{API}/placement/sessions/{data['session_id']}/next", json={}, headers=auth)
    assert response.status_code == 409 and "8 soru kaldı" in response.json()["error"]["message"]


def test_placement_climbs_until_failure(client, auth, content_db):
    content = _content(content_db)
    data = client.post(f"{API}/placement/sessions", json={"start_level": "A1", "seed": 5}, headers=auth).json()
    session_id = data["session_id"]
    for level, right in (("A1", 8), ("A2", 6), ("B1", 3)):
        assert data["current_level"] == level
        _answer_block(client, auth, content, session_id, data["questions"], right)
        data = client.post(f"{API}/placement/sessions/{session_id}/next", json={"seed": 9}, headers=auth).json()
    assert data["finished"] is True
    assert data["result_level"] == "A2" and data["recommended_level"] == "B1"
    assert [(b["level"], b["correct"], b["passed"]) for b in data["blocks"]] == [
        ("A1", 8, True), ("A2", 6, True), ("B1", 3, False)]
    assert data["answered"] == 24 and data["correct"] == 17
    levels = [item["level"] for item in data["review_lessons"]]
    assert levels and set(levels) <= {"A2", "B1"} and levels == sorted(levels)  # yanlış yapılan konular, seviye sırasıyla
    # Sonuç geçmişe yazılır; profil kendiliğinden değişmez
    assert client.get(f"{API}/placement").json()["history"][0]["result_level"] == "A2"
    assert client.get(f"{API}/profile").json()["current_level"] is None
    profile = client.put(f"{API}/profile/level", json={"level": "B1", "source": "placement"}, headers=auth).json()
    assert profile == {"current_level": "B1", "level_source": "placement"}


def test_placement_steps_down_after_failing_start_level(client, auth, content_db):
    content = _content(content_db)
    data = client.post(f"{API}/placement/sessions", json={"start_level": "B2", "seed": 2}, headers=auth).json()
    session_id = data["session_id"]
    _answer_block(client, auth, content, session_id, data["questions"], 2)
    data = client.post(f"{API}/placement/sessions/{session_id}/next", json={}, headers=auth).json()
    assert data["current_level"] == "B1" and not data["finished"]
    _answer_block(client, auth, content, session_id, data["questions"], 7)
    data = client.post(f"{API}/placement/sessions/{session_id}/next", json={}, headers=auth).json()
    assert data["finished"] and data["result_level"] == "B1" and data["recommended_level"] == "B2"


def test_placement_failing_a1_recommends_a1(client, auth, content_db):
    content = _content(content_db)
    data = client.post(f"{API}/placement/sessions", json={"seed": 4}, headers=auth).json()
    _answer_block(client, auth, content, data["session_id"], data["questions"], 1)
    data = client.post(f"{API}/placement/sessions/{data['session_id']}/next", json={}, headers=auth).json()
    assert data["finished"] and data["result_level"] == "below_A1" and data["recommended_level"] == "A1"


def test_placement_does_not_repeat_questions(client, auth, content_db):
    content = _content(content_db)
    data = client.post(f"{API}/placement/sessions", json={"seed": 8}, headers=auth).json()
    first = {q["id"] for q in data["questions"]}
    _answer_block(client, auth, content, data["session_id"], data["questions"], 8)
    data = client.post(f"{API}/placement/sessions/{data['session_id']}/next", json={}, headers=auth).json()
    assert first.isdisjoint({q["id"] for q in data["questions"]})


def test_unknown_placement_session(client, auth):
    assert client.get(f"{API}/placement/sessions/999").status_code == 404
    assert client.post(f"{API}/placement/sessions/999/next", json={}, headers=auth).status_code == 404
    assert client.post(f"{API}/placement/sessions", json={"start_level": "D1"}, headers=auth).status_code == 422


def test_empty_reports_have_no_invented_numbers(client):
    analysis = client.get(f"{API}/reports/analysis").json()
    assert analysis["graded_answers"] == 0 and analysis["strengths"] == [] and analysis["weaknesses"] == []
    assert any(item["kind"] == "placement" for item in analysis["recommendations"])
    progress = client.get(f"{API}/reports/progress").json()
    assert progress["streak"] == {"current": 0, "longest": 0, "active_days": 0}
    assert len(progress["daily"]) == 30 and all(d["questions"] == d["reviews"] == d["lessons"] == 0 for d in progress["daily"])
    assert len(progress["weekly_accuracy"]) == 8 and all(w["rate"] is None for w in progress["weekly_accuracy"])
    assert progress["totals"]["accuracy"] is None
    grammar = next(t for t in progress["tracks"] if t["track"] == "grammar")
    assert grammar["completed"] == 0 and grammar["total"] >= 100


def test_reports_reflect_real_activity(client, auth, content_db):
    content = _content(content_db)
    lesson = "gram.a1.to-be-present"
    test = client.post(f"{API}/tests/sessions", json={"lesson_id": lesson, "size": 6, "seed": 1}, headers=auth).json()
    gradable = [q for q in test["questions"] if q["evaluator"] in ("choice",)][:4]
    assert len(gradable) >= 3
    for item in gradable:  # hepsi yanlış: zayıf konu olmalı
        full = repo.question_for_grading(content, item["id"])
        client.post(f"{API}/tests/sessions/{test['session_id']}/answers",
                    json={"question_id": item["id"], "answer": _answer_value(full, False)}, headers=auth)
    client.put(f"{API}/lessons/{lesson}/completion", json={"completed": True}, headers=auth)
    client.post(f"{API}/study/review", json={"word_id": "word.book", "direction": "en_tr", "grade": 2}, headers=auth)

    analysis = client.get(f"{API}/reports/analysis").json()
    assert analysis["graded_answers"] == len(gradable)
    weak = analysis["weaknesses"][0]
    assert weak["id"] == lesson and weak["rate"] == 0 and weak["total"] == len(gradable)
    assert analysis["recommendations"][0]["kind"] == "review_lesson"
    assert analysis["by_track"][0]["key"] == "grammar" and analysis["by_level"][0]["key"] == "A1"

    progress = client.get(f"{API}/reports/progress").json()
    today = progress["daily"][-1]
    assert today["date"] == progress["today"]
    assert today["questions"] == len(gradable) and today["lessons"] == 1 and today["reviews"] == 1
    assert progress["streak"]["current"] == 1 and progress["streak"]["active_days"] == 1
    assert progress["weekly_accuracy"][-1] == {**progress["weekly_accuracy"][-1], "correct": 0, "total": len(gradable), "rate": 0}
    grammar = next(t for t in progress["tracks"] if t["track"] == "grammar")
    assert grammar["completed"] == 1 and grammar["levels"][0] == {**grammar["levels"][0], "level": "A1", "completed": 1}
    assert progress["vocabulary"]["studied_words"] == 1


def test_streak_calculation():
    from datetime import date, timedelta

    from app.services.reports import _streaks

    today = date(2026, 5, 10)
    days = {today - timedelta(days=i) for i in (1, 2, 3)} | {today - timedelta(days=i) for i in (10, 11, 12, 13, 14)}
    assert _streaks(days, today) == (3, 5)           # bugün henüz çalışılmadı: dünden geriye sayılır
    assert _streaks(days | {today}, today) == (4, 5)
    assert _streaks({today - timedelta(days=2)}, today) == (0, 1)
    assert _streaks(set(), today) == (0, 0)
