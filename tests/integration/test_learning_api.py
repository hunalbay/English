import sqlite3

from fastapi.testclient import TestClient

from app.core.config import load_settings
from app.main import create_app
from tests.conftest import BASE_URL

LESSON = "gram.a1.to-be-present"
API = "/api/v1"


def test_profile_starts_without_level(client):
    assert client.get(f"{API}/profile").json() == {"current_level": None, "level_source": None}
    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["level_progress"] is None and dashboard["continue_lesson"] is None


def test_set_level(client, auth):
    assert client.put(f"{API}/profile/level", json={"level": "B1"}).status_code == 403
    response = client.put(f"{API}/profile/level", json={"level": "A1"}, headers=auth)
    assert response.json() == {"current_level": "A1", "level_source": "self"}
    assert client.put(f"{API}/profile/level", json={"level": "Z9"}, headers=auth).status_code == 422


def test_levels_list_all_six_with_real_counts(client, content_db):
    levels = client.get(f"{API}/levels").json()["levels"]
    assert [level["code"] for level in levels] == ["A1", "A2", "B1", "B2", "C1", "C2"]
    conn = sqlite3.connect(content_db)
    expected = dict(conn.execute("SELECT level, COUNT(*) FROM lessons GROUP BY level"))
    conn.close()
    for level in levels:
        assert level["lesson_count"] == expected.get(level["code"], 0)
        assert level["completed_lessons"] == 0


def test_units_and_lesson_order(client):
    units = client.get(f"{API}/levels/A1/units").json()["units"]
    assert units[0]["id"] == "a1.u01"
    assert [lesson["id"] for lesson in units[0]["lessons"]][:2] == ["gram.a1.subject-pronouns", LESSON]
    assert all(lesson["status"] == "not_started" for lesson in units[0]["lessons"])
    assert client.get(f"{API}/levels/C2/units").json()["units"] == []
    assert client.get(f"{API}/levels/X1/units").status_code == 422


def test_lesson_detail_structure_and_links(client):
    lesson = client.get(f"{API}/lessons/{LESSON}").json()
    assert lesson["title_en"].startswith("The verb")
    kinds = [section["kind"] for section in lesson["sections"]]
    for required in ("explanation", "formula", "positive", "negative", "question", "correct_incorrect", "common_mistakes"):
        assert required in kinds
    wrong = [ex for section in lesson["sections"] for ex in section["examples"] if ex["is_incorrect"]]
    assert wrong and all(ex["correction_en"] for ex in wrong)
    assert all(ex["tr"] for section in lesson["sections"] for ex in section["examples"])
    assert lesson["sections"][kinds.index("formula")]["table"]["headers"][0] == "Özne"
    # her bağlantının gerçek bir hedefi var
    for other in lesson["prerequisite_lessons"] + lesson["next_lessons"]:
        assert client.get(f"{API}/lessons/{other['id']}").status_code == 200
    assert lesson["vocabulary"]
    for word in lesson["vocabulary"]:
        assert client.get(f"{API}/vocabulary/{word['id']}").status_code == 200


def test_unknown_lesson_404(client, auth):
    assert client.get(f"{API}/lessons/gram.a1.yok").status_code == 404
    assert client.post(f"{API}/lessons/gram.a1.yok/open", headers=auth).status_code == 404
    assert client.put(f"{API}/lessons/gram.a1.yok/completion", json={"completed": True}, headers=auth).status_code == 404


def test_lesson_progress_flow(client, auth):
    client.put(f"{API}/profile/level", json={"level": "A1"}, headers=auth)
    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["next_lesson"]["id"] == "gram.a1.subject-pronouns"

    assert client.post(f"{API}/lessons/{LESSON}/open", headers=auth).json()["status"] == "started"
    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["continue_lesson"]["id"] == LESSON
    assert dashboard["level_progress"]["completed"] == 0

    response = client.put(f"{API}/lessons/{LESSON}/completion", json={"completed": True}, headers=auth)
    assert response.json()["status"] == "completed"
    assert client.get(f"{API}/lessons/{LESSON}").json()["status"] == "completed"
    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["continue_lesson"] is None
    assert dashboard["completed_lessons"] == 1
    assert dashboard["level_progress"]["completed"] == 1
    assert next(l for l in client.get(f"{API}/levels").json()["levels"] if l["code"] == "A1")["completed_lessons"] == 1
    # tamamlanan ders yeniden açılınca tamamlanmış kalır
    assert client.post(f"{API}/lessons/{LESSON}/open", headers=auth).json()["status"] == "completed"

    client.put(f"{API}/lessons/{LESSON}/completion", json={"completed": False}, headers=auth)
    assert client.get(f"{API}/dashboard").json()["completed_lessons"] == 0


def test_changing_level_keeps_history(client, auth):
    client.put(f"{API}/profile/level", json={"level": "A1"}, headers=auth)
    client.put(f"{API}/lessons/{LESSON}/completion", json={"completed": True}, headers=auth)
    client.put(f"{API}/word-list/word.book", headers=auth)
    client.put(f"{API}/profile/level", json={"level": "B2"}, headers=auth)
    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["profile"]["current_level"] == "B2"
    assert dashboard["completed_lessons"] == 1 and dashboard["word_list_count"] == 1
    assert client.get(f"{API}/lessons/{LESSON}").json()["status"] == "completed"


def test_vocabulary_listing_and_pagination(client):
    first = client.get(f"{API}/vocabulary?page_size=10").json()
    assert first["total"] >= 100 and len(first["items"]) == 10
    lemmas = [item["lemma"].lower() for item in first["items"]]
    assert lemmas == sorted(lemmas)
    second = client.get(f"{API}/vocabulary?page_size=10&page=2").json()
    assert not {item["id"] for item in first["items"]} & {item["id"] for item in second["items"]}
    assert client.get(f"{API}/vocabulary?level=C2").json()["total"] == 0
    assert client.get(f"{API}/vocabulary?page_size=1000").status_code == 422


def test_vocabulary_search(client):
    def ids(query):
        return [item["id"] for item in client.get(f"{API}/vocabulary", params={"q": query}).json()["items"]]

    assert ids("book")[0] == "word.book"
    assert "word.teacher" in ids("öğretmen")
    assert "word.teacher" in ids("ogretmen")      # Türkçe karakter olmadan
    assert "word.child" in ids("children")        # çekimli biçimden temel kelimeye
    assert "word.be" in ids("were")
    assert ids("a")[0] == "word.a"                # tam eşleşme önce
    assert ids("zzzzqq") == []
    assert ids('" OR 1=1 --') == []               # zararlı girdi sorguyu bozmaz
    assert ids("%") == []


def test_word_detail(client):
    word = client.get(f"{API}/vocabulary/word.be").json()
    assert word["lemma"] == "be" and "were" in word["forms"]
    assert word["meanings"][0] == {"pos": "verb", "meaning_tr": "olmak", "definition_en": None}
    assert word["examples"][0]["tr"]
    assert LESSON in [lesson["id"] for lesson in word["lessons"]]
    assert client.get(f"{API}/vocabulary/word.yok").status_code == 404


def test_word_relations_are_bidirectional(client):
    # 'young' kaydında antonyms: [old]; 'old' kaydında [new, young]
    old = client.get(f"{API}/vocabulary/word.old").json()
    assert {w["lemma"] for w in old["antonyms"]} == {"new", "young"}
    assert "old" in {w["lemma"] for w in client.get(f"{API}/vocabulary/word.new").json()["antonyms"]}


def test_lookup_inflected_form(client):
    assert client.get(f"{API}/vocabulary/lookup", params={"form": "Children"}).json() == {"word_id": "word.child"}
    assert client.get(f"{API}/vocabulary/lookup", params={"form": "xyzzy"}).status_code == 404


def test_word_list_flow(client, auth):
    assert client.get(f"{API}/word-list").json() == {"items": [], "total": 0}
    assert client.put(f"{API}/word-list/word.book").status_code == 403
    assert client.put(f"{API}/word-list/word.yok", headers=auth).status_code == 404
    client.put(f"{API}/word-list/word.book", headers=auth)
    client.put(f"{API}/word-list/word.book", headers=auth)  # yinelenen ekleme tek kayıt
    client.put(f"{API}/word-list/word.tea", headers=auth)
    listing = client.get(f"{API}/word-list").json()
    assert listing["total"] == 2 and {w["id"] for w in listing["items"]} == {"word.book", "word.tea"}
    assert client.get(f"{API}/vocabulary/word.book").json()["in_word_list"] is True
    assert client.get(f"{API}/vocabulary", params={"q": "book"}).json()["items"][0]["in_word_list"] is True
    assert client.delete(f"{API}/word-list/word.book", headers=auth).json()["in_word_list"] is False
    assert client.get(f"{API}/word-list").json()["total"] == 1


def test_search_finds_lessons_and_words(client):
    data = client.get(f"{API}/search", params={"q": "zamir"}).json()
    assert "gram.a1.subject-pronouns" in [lesson["id"] for lesson in data["lessons"]]
    data = client.get(f"{API}/search", params={"q": "pronouns"}).json()
    assert data["lessons"][0]["id"] == "gram.a1.subject-pronouns"
    data = client.get(f"{API}/search", params={"q": "kitap"}).json()
    assert "word.book" in [word["id"] for word in data["words"]]
    assert client.get(f"{API}/search", params={"q": "!!!"}).json() == {"query": "!!!", "lessons": [], "words": []}
    assert client.get(f"{API}/search").status_code == 422


def test_progress_survives_restart_and_content_rebuild(settings, tmp_path):
    with TestClient(create_app(settings), base_url=BASE_URL) as first:
        token = {"X-EM-Token": first.get(f"{API}/session").json()["token"]}
        first.put(f"{API}/profile/level", json={"level": "A1"}, headers=token)
        first.put(f"{API}/lessons/{LESSON}/completion", json={"completed": True}, headers=token)
        first.put(f"{API}/word-list/word.book", headers=token)

    # içerik yeniden üretilir (yeni dosya); kullanıcı verisi aynı klasörde kalır
    from app.content import builder
    from tests.conftest import ROOT

    rebuilt = tmp_path / "rebuilt.db"
    builder.build(ROOT / "data", rebuilt)
    again = load_settings(data_dir=settings.data_dir, content_db_path=rebuilt)
    with TestClient(create_app(again), base_url=BASE_URL) as second:
        dashboard = second.get(f"{API}/dashboard").json()
        assert dashboard["profile"]["current_level"] == "A1"
        assert dashboard["completed_lessons"] == 1 and dashboard["word_list_count"] == 1


def test_stale_progress_for_removed_content_is_ignored(client, auth, app):
    """İçerikten kaldırılmış bir derse ait kayıt sayılara ve bağlantılara sızmaz."""
    from app.models.user import LessonProgress, PersonalWord

    with app.state.user_sessions() as session:
        session.add(LessonProgress(lesson_id="gram.a1.silinmis", status="completed"))
        session.add(LessonProgress(lesson_id="gram.a1.silinmis2", status="started"))
        session.add(PersonalWord(word_id="word.silinmis"))
        session.commit()
    dashboard = client.get(f"{API}/dashboard").json()
    assert dashboard["completed_lessons"] == 0 and dashboard["continue_lesson"] is None
    assert client.get(f"{API}/word-list").json()["items"] == []


def test_missing_content_gives_clear_error(tmp_path):
    settings = load_settings(data_dir=tmp_path / "u", content_db_path=tmp_path / "yok.db")
    with TestClient(create_app(settings), base_url=BASE_URL) as client:
        response = client.get(f"{API}/levels")
        assert response.status_code == 503
        assert "Eğitim içeriği bulunamadı" in response.json()["error"]["message"]
        assert client.get(f"{API}/settings").status_code == 200  # kullanıcı verisi yine erişilebilir
