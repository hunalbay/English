import sqlite3

API = "/api/v1"
LESSON = "gram.a1.to-be-present"


def _start(client, auth, **body):
    response = client.post(f"{API}/tests/sessions", json={"seed": 7, **body}, headers=auth)
    assert response.status_code == 200, response.text
    return response.json()


def _key(content_db, question_id):
    conn = sqlite3.connect(content_db)
    try:
        correct = conn.execute("SELECT position FROM answer_options WHERE question_id = ? AND is_correct = 1", (question_id,)).fetchone()
        wrong = conn.execute("SELECT position FROM answer_options WHERE question_id = ? AND is_correct = 0", (question_id,)).fetchone()
        accepted = conn.execute("SELECT text FROM accepted_answers WHERE question_id = ? ORDER BY position", (question_id,)).fetchone()
        return (correct and correct[0], wrong and wrong[0], accepted and accepted[0])
    finally:
        conn.close()


def _answer(client, auth, test, question_id, answer):
    return client.post(f"{API}/tests/sessions/{test['session_id']}/answers",
                       json={"question_id": question_id, "answer": answer}, headers=auth)


def test_start_requires_token_and_existing_content(client, auth):
    assert client.post(f"{API}/tests/sessions", json={"lesson_id": LESSON}).status_code == 403
    assert client.post(f"{API}/tests/sessions", json={"lesson_id": "gram.a1.yok"}, headers=auth).status_code == 404
    response = client.post(f"{API}/tests/sessions", json={"level": "C2"}, headers=auth)
    assert response.status_code == 404 and "henüz soru yok" in response.json()["error"]["message"]
    assert client.post(f"{API}/tests/sessions", json={"level": "A1", "size": 500}, headers=auth).status_code == 422


def test_questions_are_sent_without_answer_key(client, auth):
    test = _start(client, auth, lesson_id=LESSON, size=12)
    assert len(test["questions"]) == 12 and test["kind"] == "lesson"
    dumped = str(test["questions"])
    assert "is_correct" not in dumped and "explanation" not in dumped and "accepted" not in dumped
    for question in test["questions"]:
        assert question["lesson"]["id"] == LESSON and question["instruction_tr"]
        if question["evaluator"] == "order":
            assert sorted(question["tokens"]) == sorted(["Are", "you", "a", "student", "?"])
        if question["evaluator"] == "choice":
            assert len(question["options"]) >= 2


def test_wrong_choice_explains_every_option_and_links_lesson(client, auth, content_db):
    test = _start(client, auth, lesson_id=LESSON, types=["multiple_choice"], size=1)
    question = test["questions"][0]
    correct, wrong, _ = _key(content_db, question["id"])
    feedback = _answer(client, auth, test, question["id"], wrong).json()
    assert feedback["result"] == "incorrect" and feedback["chosen"] == wrong
    assert len(feedback["options"]) == len(question["options"])
    assert all(option["explanation_tr"] for option in feedback["options"])
    assert sum(1 for option in feedback["options"] if option["is_correct"]) == 1
    assert feedback["explanation_tr"] and feedback["lessons"][0]["id"] == LESSON
    assert feedback["lesson_examples"] and feedback["lesson_examples"][0]["tr"]
    # bağlantılı ders gerçekten var
    assert client.get(f"{API}/lessons/{feedback['lessons'][0]['id']}").status_code == 200
    # aynı soru iki kez cevaplanamaz
    assert _answer(client, auth, test, question["id"], correct).status_code == 409


def test_text_question_normalization_and_strict_mode(client, auth):
    test = _start(client, auth, lesson_id="gram.a1.subject-pronouns", types=["error_correction"], size=1)
    question = test["questions"][0]
    assert question["strict"] is True
    feedback = _answer(client, auth, test, question["id"], "Tom and i are friends.").json()
    assert feedback["result"] == "incorrect" and "noktalama" in feedback["note_tr"]
    assert feedback["accepted_answers"] == ["Tom and I are friends."]

    test = _start(client, auth, lesson_id=LESSON, types=["fill_blank"], size=2)
    for question in test["questions"]:
        answer = "AM" if "twenty" in question["prompt"] else "aren't"
        assert _answer(client, auth, test, question["id"], answer).json()["result"] == "correct"


def test_translation_not_in_list_is_ungraded_then_self_rated(client, auth):
    test = _start(client, auth, lesson_id=LESSON, types=["translation"], size=1)
    question = test["questions"][0]
    feedback = _answer(client, auth, test, question["id"], "She is not in the house.").json()
    assert feedback["result"] == "ungraded" and "kesin olarak değerlendiremez" in feedback["note_tr"]
    url = f"{API}/tests/sessions/{test['session_id']}/self-rating"
    assert client.post(url, json={"question_id": question["id"], "rating": "partial"}).status_code == 403
    rated = client.post(url, json={"question_id": question["id"], "rating": "partial"}, headers=auth).json()
    assert rated["result"] == "self_partial"
    summary = client.post(f"{API}/tests/sessions/{test['session_id']}/finish", headers=auth).json()
    assert summary["partial"] == 1 and summary["self_assessed"] == 1 and summary["correct"] == 0


def test_written_answer_shows_model_and_checklist(client, auth):
    test = _start(client, auth, lesson_id=LESSON, types=["written_answer"], size=1)
    question = test["questions"][0]
    assert question["checklist"]
    feedback = _answer(client, auth, test, question["id"], "I am Ali. I am 20 years old.").json()
    assert feedback["result"] == "ungraded" and feedback["model_answers"] and feedback["checklist"]
    assert "değerlendirilmez" in feedback["note_tr"]


def test_self_rating_not_allowed_for_machine_graded_answers(client, auth, content_db):
    test = _start(client, auth, lesson_id=LESSON, types=["multiple_choice"], size=1)
    question = test["questions"][0]
    _answer(client, auth, test, question["id"], _key(content_db, question["id"])[0])
    response = client.post(f"{API}/tests/sessions/{test['session_id']}/self-rating",
                           json={"question_id": question["id"], "rating": "incorrect"}, headers=auth)
    assert response.status_code == 409


def test_order_and_matching_questions(client, auth):
    test = _start(client, auth, lesson_id=LESSON, types=["word_order"], size=1)
    question = test["questions"][0]
    assert question["tokens"] != ["Are", "you", "a", "student", "?"]  # karıştırılmış gelir
    feedback = _answer(client, auth, test, question["id"], ["Are", "you", "a", "student", "?"]).json()
    assert feedback["result"] == "correct" and feedback["correct_order"][0] == "Are"

    test = _start(client, auth, lesson_id="gram.a1.subject-pronouns", types=["matching"], size=1)
    question = test["questions"][0]
    swapped = dict(zip(question["left"], reversed(question["right"]), strict=True))
    feedback = _answer(client, auth, test, question["id"], swapped).json()
    assert feedback["result"] in ("incorrect", "correct") and len(feedback["pairs"]) == 4
    assert _answer(client, auth, _start(client, auth, lesson_id="gram.a1.subject-pronouns", types=["matching"], size=1),
                   question["id"], {"I": "ben"}).status_code == 422


def test_invalid_answers_rejected(client, auth):
    test = _start(client, auth, lesson_id=LESSON, types=["multiple_choice"], size=1)
    question = test["questions"][0]
    assert _answer(client, auth, test, question["id"], 99).status_code == 422
    assert _answer(client, auth, test, question["id"], "is").status_code == 422
    assert _answer(client, auth, test, "q.a1.a-an.01", 1).status_code == 404   # bu teste ait olmayan soru
    assert client.post(f"{API}/tests/sessions/9999/answers", json={"question_id": question["id"], "answer": 1},
                       headers=auth).status_code == 404


def test_history_topic_stats_and_question_selection(client, auth, content_db):
    assert client.get(f"{API}/tests/overview").json()["history"] == []
    test = _start(client, auth, lesson_id=LESSON, types=["multiple_choice"], size=2)
    first, second = test["questions"]
    _answer(client, auth, test, first["id"], _key(content_db, first["id"])[0])
    _answer(client, auth, test, second["id"], _key(content_db, second["id"])[1])
    summary = client.post(f"{API}/tests/sessions/{test['session_id']}/finish", headers=auth).json()
    assert (summary["total"], summary["correct"], summary["incorrect"], summary["finished"]) == (2, 1, 1, True)

    overview = client.get(f"{API}/tests/overview").json()
    assert overview["history"][0]["lesson"]["id"] == LESSON and overview["history"][0]["correct"] == 1
    a1 = next(level for level in overview["levels"] if level["code"] == "A1")
    lesson = next(item for item in a1["lessons"] if item["id"] == LESSON)
    assert lesson["stats"]["accuracy"] == 50 and lesson["question_count"] == 12
    assert overview["weak_topics"][0]["id"] == LESSON
    assert all(level["question_count"] == sum(l["question_count"] for l in level["lessons"]) for level in overview["levels"])

    # yeni testte önce hiç çözülmemiş sorular gelir; daha önce doğru yapılan en sona kalır
    again = _start(client, auth, lesson_id=LESSON, size=10)
    ids = [question["id"] for question in again["questions"]]
    assert first["id"] not in ids and second["id"] not in ids

    # hiç cevaplanmayan oturum geçmişte görünmez
    assert len(client.get(f"{API}/tests/overview").json()["history"]) == 1


def test_level_test_and_lesson_question_count(client, auth):
    test = _start(client, auth, level="A1", size=10)
    assert test["kind"] == "level" and len(test["questions"]) == 10
    assert len({question["lesson"]["id"] for question in test["questions"]}) >= 2
    assert client.get(f"{API}/lessons/{LESSON}").json()["question_count"] == 12
    assert client.get(f"{API}/dashboard").json()["totals"]["questions"] >= 30
