from datetime import timedelta

from app.models.user import ReviewHistory, ReviewItem, utcnow
from app.services import study

API = "/api/v1"


def _level(client, auth, level="A1"):
    client.put(f"{API}/profile/level", json={"level": level}, headers=auth)


def test_session_requires_level_for_level_source(client):
    response = client.get(f"{API}/study/session", params={"direction": "en_tr"})
    assert response.status_code == 422 and "seviyenizi" in response.json()["error"]["message"]


def test_new_session_respects_new_limit(client, auth):
    _level(client, auth)
    data = client.get(f"{API}/study/session", params={"direction": "en_tr", "size": 20, "new_limit": 7}).json()
    assert len(data["cards"]) == 7 and data["due_count"] == 0
    assert data["pool_size"] == data["new_available"] >= 100
    card = data["cards"][0]
    assert card["review"]["status"] == "new" and card["example"]["en"] and card["meaning_tr"]


def test_review_flow_and_scheduling(client, auth, app):
    _level(client, auth)
    cards = client.get(f"{API}/study/session", params={"direction": "en_tr", "new_limit": 3}).json()["cards"]
    first, second, third = (card["id"] for card in cards)

    assert client.post(f"{API}/study/review", json={"word_id": first, "direction": "en_tr", "grade": 2}).status_code == 403
    good = client.post(f"{API}/study/review", json={"word_id": first, "direction": "en_tr", "grade": 2}, headers=auth).json()
    assert good["review"]["interval_days"] == 1 and good["review"]["is_due"] is False
    again = client.post(f"{API}/study/review", json={"word_id": second, "direction": "en_tr", "grade": 0}, headers=auth).json()
    assert again["review"]["interval_days"] == 0
    client.post(f"{API}/study/review", json={"word_id": third, "direction": "en_tr", "grade": 3}, headers=auth)

    # aynı oturumda cevaplanan kartlar yeniden gelmez; yeni kelimeler gelir
    next_cards = client.get(f"{API}/study/session", params={"direction": "en_tr", "new_limit": 3}).json()["cards"]
    assert not {first, second, third} & {card["id"] for card in next_cards}

    # yönler bağımsızdır: TR→EN yönünde aynı kelimeler hâlâ yenidir
    reverse = client.get(f"{API}/study/session", params={"direction": "tr_en", "new_limit": 3}).json()["cards"]
    assert {card["id"] for card in reverse} == {first, second, third}

    # zaman ilerleyince tekrar zamanı gelen kartlar önce gelir
    with app.state.user_sessions() as session:
        later = utcnow() + timedelta(days=2)
        data = study.build_session(session, _content(app), "en_tr", "level", "A1", 20, 0, now=later)
    assert [card["id"] for card in data["cards"]][:2] == [second, first]  # en eski vadeli önce
    assert data["due_count"] == 2 and third not in {card["id"] for card in data["cards"]}

    assert client.post(f"{API}/study/review", json={"word_id": "word.yok", "direction": "en_tr", "grade": 2}, headers=auth).status_code == 404
    assert client.post(f"{API}/study/review", json={"word_id": first, "direction": "en_tr", "grade": 9}, headers=auth).status_code == 422
    assert client.post(f"{API}/study/review", json={"word_id": first, "direction": "xx", "grade": 2}, headers=auth).status_code == 422


def _content(app):
    from app.database.content_db import connect_readonly

    return connect_readonly(app.state.settings.content_db_path)


def test_list_and_due_sources(client, auth):
    _level(client, auth)
    assert client.get(f"{API}/study/session", params={"direction": "en_tr", "source": "list"}).json()["cards"] == []
    client.put(f"{API}/word-list/word.book", headers=auth)
    client.put(f"{API}/word-list/word.tea", headers=auth)
    cards = client.get(f"{API}/study/session", params={"direction": "en_tr", "source": "list"}).json()["cards"]
    assert {card["id"] for card in cards} == {"word.book", "word.tea"}
    # "due" kaynağı yeni kelime getirmez
    assert client.get(f"{API}/study/session", params={"direction": "en_tr", "source": "due"}).json()["cards"] == []
    client.post(f"{API}/study/review", json={"word_id": "word.book", "direction": "en_tr", "grade": 0}, headers=auth)
    assert client.get(f"{API}/study/session", params={"direction": "en_tr", "source": "due"}).json()["cards"] == []  # 10 dk sonra


def test_exercises_endpoint_is_reproducible_with_seed(client, auth):
    _level(client, auth)
    params = {"type": "mc_en_tr", "size": 5, "seed": 42}
    first = client.get(f"{API}/study/exercises", params=params).json()
    assert first == client.get(f"{API}/study/exercises", params=params).json()
    assert len(first["questions"]) == 5
    assert "correct" not in str(first["questions"])  # cevap anahtarı soruyla birlikte gönderilmez
    assert client.get(f"{API}/study/exercises", params={"type": "yok"}).status_code == 422
    for kind in ("mc_tr_en", "typing", "cloze", "antonym", "matching"):
        data = client.get(f"{API}/study/exercises", params={"type": kind, "size": 3, "seed": 1}).json()
        assert data["questions"], kind


def test_answer_records_history_and_wrong_answer_requeues_card(client, auth, app):
    _level(client, auth)
    for _ in range(2):  # kartı 6 günlük aralığa getir
        client.post(f"{API}/study/review", json={"word_id": "word.book", "direction": "en_tr", "grade": 2}, headers=auth)
    assert client.get(f"{API}/study/words/word.book").json()["directions"]["en_tr"]["interval_days"] == 6

    assert client.post(f"{API}/study/answer", json={"type": "mc_en_tr", "word_id": "word.book", "answer": "word.book"}).status_code == 403
    right = client.post(f"{API}/study/answer", json={"type": "mc_en_tr", "word_id": "word.book", "answer": "word.book"}, headers=auth).json()
    assert right["correct"] is True
    # doğru cevap planı değiştirmez
    assert client.get(f"{API}/study/words/word.book").json()["directions"]["en_tr"]["interval_days"] == 6

    wrong = client.post(f"{API}/study/answer", json={"type": "mc_en_tr", "word_id": "word.book", "answer": "word.pen"}, headers=auth).json()
    assert wrong["correct"] is False and wrong["chosen"]["lemma"] == "pen"
    progress = client.get(f"{API}/study/words/word.book").json()
    assert progress["directions"]["en_tr"]["interval_days"] == 0 and progress["directions"]["en_tr"]["lapses"] == 1
    assert progress["directions"]["tr_en"]["status"] == "new"
    assert [h["activity"] for h in progress["history"]] == ["mc_en_tr", "mc_en_tr", "flashcard", "flashcard"]

    # çalışılmamış kelimede yanlış cevap kart oluşturmaz, yalnızca geçmişe yazılır
    client.post(f"{API}/study/answer", json={"type": "typing", "word_id": "word.tea", "answer": "coffee"}, headers=auth)
    with app.state.user_sessions() as session:
        assert session.query(ReviewItem).filter_by(word_id="word.tea").count() == 0
        assert session.query(ReviewHistory).filter_by(word_id="word.tea").count() == 1

    assert client.post(f"{API}/study/answer", json={"type": "typing", "word_id": "word.tea", "answer": ""}, headers=auth).status_code == 422
    assert client.post(f"{API}/study/answer", json={"type": "typing", "word_id": "word.yok", "answer": "x"}, headers=auth).status_code == 404


def test_matching_answer(client, auth):
    _level(client, auth)
    body = {"type": "matching", "word_id": "word.book", "answer": {"word.book": "word.book", "word.tea": "word.pen", "word.pen": "word.tea"}}
    result = client.post(f"{API}/study/answer", json=body, headers=auth).json()
    assert result["correct"] is False and len(result["results"]) == 3
    assert len(client.get(f"{API}/study/words/word.tea").json()["history"]) == 1


def test_reset_word_keeps_history(client, auth):
    _level(client, auth)
    client.post(f"{API}/study/review", json={"word_id": "word.book", "direction": "en_tr", "grade": 2}, headers=auth)
    client.post(f"{API}/study/review", json={"word_id": "word.book", "direction": "tr_en", "grade": 3}, headers=auth)
    assert client.delete(f"{API}/study/words/word.book").status_code == 403
    assert client.delete(f"{API}/study/words/word.book", headers=auth).json() == {"word_id": "word.book", "reset": True}
    progress = client.get(f"{API}/study/words/word.book").json()
    assert progress["directions"]["en_tr"]["status"] == progress["directions"]["tr_en"]["status"] == "new"
    assert len(progress["history"]) == 2
    assert client.get(f"{API}/study/words/word.yok").status_code == 404


def test_stats_are_computed_from_real_records(client, auth, app):
    _level(client, auth)
    empty = client.get(f"{API}/study/stats").json()
    assert empty["studied_words"] == 0 and empty["total_answers"] == 0 and empty["most_missed"] == []
    assert len(empty["daily"]) == 7 and all(day["answers"] == 0 for day in empty["daily"])

    client.post(f"{API}/study/review", json={"word_id": "word.book", "direction": "en_tr", "grade": 2}, headers=auth)
    client.post(f"{API}/study/review", json={"word_id": "word.tea", "direction": "en_tr", "grade": 0}, headers=auth)
    client.post(f"{API}/study/answer", json={"type": "mc_en_tr", "word_id": "word.tea", "answer": "word.pen"}, headers=auth)
    with app.state.user_sessions() as session:  # içerikten silinmiş kelimeye ait kayıt sayılmaz
        now = utcnow()
        session.add(ReviewItem(word_id="word.silinmis", direction="en_tr", ease=2.5, interval_days=30,
                               repetitions=4, lapses=0, due_at=now, created_at=now, last_reviewed_at=now))
        session.commit()

    stats = client.get(f"{API}/study/stats").json()
    assert stats["studied_words"] == 2 and stats["started_this_week"] == 2
    assert stats["directions"]["en_tr"] == {"learning": 2, "learned": 0, "long_term": 0, "due": 0}
    assert stats["total_answers"] == 3 and stats["total_correct"] == 1
    assert stats["daily"][-1] == {"date": stats["daily"][-1]["date"], "answers": 3, "correct": 1}
    assert stats["most_missed"][0]["id"] == "word.tea" and stats["most_missed"][0]["wrong_count"] == 2
    assert stats["total_words"] >= 100
