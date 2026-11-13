"""content.db okuma sorguları. Tüm sorgular parametrelidir; veri tabanı salt okunur açılır."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from app.content.text import fts_query, lemma_key

Row = dict[str, Any]


def _rows(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> list[Row]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _one(conn: sqlite3.Connection, sql: str, params: tuple | list = ()) -> Row | None:
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _placeholders(values: list) -> str:
    return ",".join("?" * len(values))


# --- Seviyeler ve dersler ---------------------------------------------------

def levels(conn: sqlite3.Connection) -> list[Row]:
    return _rows(
        conn,
        """SELECT l.code, l.name_tr, l.description_tr,
                  (SELECT COUNT(*) FROM lessons x WHERE x.level = l.code) AS lesson_count,
                  (SELECT COUNT(*) FROM vocabulary v WHERE v.level = l.code) AS word_count
           FROM levels l ORDER BY l.position""",
    )


def lesson_ids_by_level(conn: sqlite3.Connection) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in conn.execute("SELECT level, id FROM lessons"):
        result.setdefault(row["level"], []).append(row["id"])
    return result


def units(conn: sqlite3.Connection, level: str) -> list[Row]:
    unit_rows = _rows(
        conn, "SELECT id, level, title_tr, title_en, description_tr FROM units WHERE level = ? ORDER BY position", (level,)
    )
    for unit in unit_rows:
        unit["lessons"] = _rows(
            conn,
            "SELECT id, kind, level, title_tr, title_en, objective_tr FROM lessons WHERE unit_id = ? ORDER BY position",
            (unit["id"],),
        )
    return unit_rows


def lesson_exists(conn: sqlite3.Connection, lesson_id: str) -> bool:
    return conn.execute("SELECT 1 FROM lessons WHERE id = ?", (lesson_id,)).fetchone() is not None


def lesson_briefs(conn: sqlite3.Connection, lesson_ids: list[str]) -> dict[str, Row]:
    if not lesson_ids:
        return {}
    rows = _rows(
        conn,
        f"SELECT id, kind, level, title_tr, title_en FROM lessons WHERE id IN ({_placeholders(lesson_ids)})",  # noqa: S608
        lesson_ids,
    )
    return {row["id"]: row for row in rows}


def ordered_lesson_ids(conn: sqlite3.Connection, level: str) -> list[str]:
    return [
        row["id"]
        for row in conn.execute(
            """SELECT ls.id FROM lessons ls JOIN units u ON u.id = ls.unit_id
               WHERE ls.level = ? ORDER BY u.position, ls.position""",
            (level,),
        )
    ]


def lesson(conn: sqlite3.Connection, lesson_id: str) -> Row | None:
    data = _one(
        conn,
        """SELECT ls.id, ls.kind, ls.level, ls.title_tr, ls.title_en, ls.objective_tr, ls.review_status,
                  u.id AS unit_id, u.title_tr AS unit_title_tr,
                  s.name AS source_name, s.license AS source_license
           FROM lessons ls JOIN units u ON u.id = ls.unit_id JOIN content_sources s ON s.id = ls.source_id
           WHERE ls.id = ?""",
        (lesson_id,),
    )
    if data is None:
        return None
    sections = _rows(
        conn,
        "SELECT id, kind, title_tr, text_tr, table_json FROM lesson_sections WHERE lesson_id = ? ORDER BY position",
        (lesson_id,),
    )
    for section in sections:
        table_json = section.pop("table_json")
        section["table"] = json.loads(table_json) if table_json else None
        section["examples"] = [
            {**example, "is_incorrect": bool(example["is_incorrect"])}
            for example in _rows(
                conn,
                """SELECT en, tr, note_tr, is_incorrect, correction_en FROM example_sentences
                   WHERE section_id = ? ORDER BY position""",
                (section.pop("id"),),
            )
        ]
    data["sections"] = sections
    relations = _rows(
        conn,
        """SELECT r.kind AS relation, ls.id, ls.kind, ls.level, ls.title_tr, ls.title_en
           FROM lesson_relations r JOIN lessons ls ON ls.id = r.related_lesson_id
           WHERE r.lesson_id = ? ORDER BY r.rowid""",
        (lesson_id,),
    )
    for name in ("prerequisite", "next", "related"):
        data[f"{name}_lessons"] = [
            {key: value for key, value in row.items() if key != "relation"} for row in relations if row["relation"] == name
        ]
    data["vocabulary"] = word_briefs(
        conn,
        [row["word_id"] for row in conn.execute(
            "SELECT lv.word_id FROM lesson_vocabulary lv JOIN vocabulary v ON v.id = lv.word_id "
            "WHERE lv.lesson_id = ? ORDER BY v.lemma_key", (lesson_id,))],
    )
    return data


# --- Sözlük -----------------------------------------------------------------

_WORD_BRIEF = """SELECT v.id, v.lemma, v.level, v.ipa,
                        (SELECT GROUP_CONCAT(pos, '|') FROM (SELECT DISTINCT pos FROM word_meanings m
                                                             WHERE m.word_id = v.id ORDER BY m.position)) AS pos,
                        (SELECT GROUP_CONCAT(meaning_tr, '; ') FROM (SELECT meaning_tr FROM word_meanings m
                                                                     WHERE m.word_id = v.id ORDER BY m.position)) AS meaning_tr
                 FROM vocabulary v"""


def _brief(row: Row) -> Row:
    row["pos"] = row["pos"].split("|") if row["pos"] else []
    return row


def word_exists(conn: sqlite3.Connection, word_id: str) -> bool:
    return conn.execute("SELECT 1 FROM vocabulary WHERE id = ?", (word_id,)).fetchone() is not None


def word_briefs(conn: sqlite3.Connection, word_ids: list[str]) -> list[Row]:
    """Verilen kimliklerin özetlerini, verilen sırayı koruyarak döndürür."""
    if not word_ids:
        return []
    rows = _rows(conn, f"{_WORD_BRIEF} WHERE v.id IN ({_placeholders(word_ids)})", word_ids)  # noqa: S608
    by_id = {row["id"]: _brief(row) for row in rows}
    return [by_id[word_id] for word_id in word_ids if word_id in by_id]


def words(conn: sqlite3.Connection, level: str | None, query: str | None, limit: int, offset: int) -> tuple[list[Row], int]:
    where, params = [], []
    if level:
        where.append("v.level = ?")
        params.append(level)
    order = "v.lemma_key"
    if query:
        match = fts_query(query)
        if match is None:
            return [], 0
        where.append("v.id IN (SELECT ref_id FROM search_index WHERE kind = 'word' AND search_index MATCH ?)")
        params.append(match)
        # tam eşleşme önce, sonra ön ek eşleşmesi, sonra diğerleri
        order = "(v.lemma_key = ?) DESC, (v.lemma_key LIKE ? ESCAPE '\\') DESC, v.lemma_key"
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    total = conn.execute(f"SELECT COUNT(*) FROM vocabulary v {clause}", params).fetchone()[0]  # noqa: S608
    order_params: list = []
    if query:
        key = lemma_key(query)
        escaped = key.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        order_params = [key, f"{escaped}%"]
    rows = _rows(
        conn, f"{_WORD_BRIEF} {clause} ORDER BY {order} LIMIT ? OFFSET ?", [*params, *order_params, limit, offset]  # noqa: S608
    )
    return [_brief(row) for row in rows], total


def word(conn: sqlite3.Connection, word_id: str) -> Row | None:
    data = _one(
        conn,
        """SELECT v.id, v.lemma, v.level, v.ipa, v.syllables, v.frequency_rank, v.notes_tr, v.review_status,
                  s.name AS source_name, s.license AS source_license
           FROM vocabulary v JOIN content_sources s ON s.id = v.source_id WHERE v.id = ?""",
        (word_id,),
    )
    if data is None:
        return None
    data["meanings"] = _rows(
        conn, "SELECT pos, meaning_tr, definition_en FROM word_meanings WHERE word_id = ? ORDER BY position", (word_id,)
    )
    data["forms"] = [row["form"] for row in conn.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY rowid", (word_id,))]
    data["examples"] = _rows(conn, "SELECT en, tr FROM example_sentences WHERE word_id = ? ORDER BY position", (word_id,))
    data["collocations"] = _rows(conn, "SELECT phrase, meaning_tr FROM collocations WHERE word_id = ? ORDER BY id", (word_id,))
    relations = _rows(
        conn,
        """SELECT kind, other FROM (
               SELECT kind, related_word_id AS other FROM word_relations WHERE word_id = ?
               UNION
               SELECT kind, word_id AS other FROM word_relations WHERE related_word_id = ?
           )""",
        (word_id, word_id),
    )  # ilişkiler çift yönlü gösterilir
    for kind, key in (("synonym", "synonyms"), ("antonym", "antonyms"), ("related", "related_words")):
        data[key] = word_briefs(conn, sorted(row["other"] for row in relations if row["kind"] == kind))
    data["lessons"] = _rows(
        conn,
        """SELECT ls.id, ls.kind, ls.level, ls.title_tr, ls.title_en
           FROM lesson_vocabulary lv JOIN lessons ls ON ls.id = lv.lesson_id
           WHERE lv.word_id = ? ORDER BY ls.level, ls.title_tr""",
        (word_id,),
    )
    return data


def lookup_form(conn: sqlite3.Connection, text: str) -> str | None:
    """Bir sözcüğün (temel ya da çekimli biçim) ait olduğu kelime kimliğini bulur."""
    key = lemma_key(text)
    row = conn.execute(
        "SELECT id FROM vocabulary WHERE lemma_key = ? UNION ALL SELECT word_id FROM word_forms WHERE form = ? LIMIT 1",
        (key, key),
    ).fetchone()
    return row[0] if row else None


# --- Arama ------------------------------------------------------------------

def search(conn: sqlite3.Connection, query: str, limit: int) -> dict[str, list[Row]]:
    match = fts_query(query)
    if match is None:
        return {"lessons": [], "words": []}
    hits = conn.execute(
        "SELECT kind, ref_id FROM search_index WHERE search_index MATCH ? ORDER BY bm25(search_index, 0, 0, 0, 10.0, 1.0) LIMIT ?",
        (match, limit * 4),
    ).fetchall()
    lesson_ids = [hit["ref_id"] for hit in hits if hit["kind"] == "lesson"][:limit]
    word_ids = [hit["ref_id"] for hit in hits if hit["kind"] == "word"][:limit]
    briefs = lesson_briefs(conn, lesson_ids)
    return {
        "lessons": [briefs[lesson_id] for lesson_id in lesson_ids if lesson_id in briefs],
        "words": word_briefs(conn, word_ids),
    }


def totals(conn: sqlite3.Connection) -> Row:
    return {
        "lessons": conn.execute("SELECT COUNT(*) FROM lessons").fetchone()[0],
        "words": conn.execute("SELECT COUNT(*) FROM vocabulary").fetchone()[0],
    }


# --- Kelime çalışması -------------------------------------------------------

def word_ids_for_level(conn: sqlite3.Connection, level: str) -> list[str]:
    """Bir seviyenin kelimeleri, çalışma sırasıyla.

    Sıklık bilgisi olan kelimeler önce gelir. Diğerleri alfabetik değil, kimliğe bağlı
    sabit bir karışık sırayla gelir; böylece öğrenci yalnızca "a" ile başlayan kelimelerle
    başlamaz ve sıra her açılışta aynı kalır.
    """
    rows = conn.execute("SELECT id, frequency_rank FROM vocabulary WHERE level = ?", (level,)).fetchall()
    return [
        row["id"]
        for row in sorted(
            rows,
            key=lambda row: (
                row["frequency_rank"] is None,
                row["frequency_rank"] or 0,
                hashlib.sha1(row["id"].encode("utf-8")).hexdigest(),  # noqa: S324 (güvenlik amaçlı değil)
            ),
        )
    ]


def existing_word_ids(conn: sqlite3.Connection, word_ids: list[str]) -> set[str]:
    found: set[str] = set()
    for start in range(0, len(word_ids), 500):
        chunk = word_ids[start : start + 500]
        found |= {row["id"] for row in conn.execute(
            f"SELECT id FROM vocabulary WHERE id IN ({_placeholders(chunk)})", chunk)}  # noqa: S608
    return found


def study_cards(conn: sqlite3.Connection, word_ids: list[str]) -> list[Row]:
    """Kart ve alıştırmalar için kelime verisi: özet + çekimler + ilk örnek cümle."""
    cards = word_briefs(conn, word_ids)
    for card in cards:
        example = conn.execute(
            "SELECT en, tr FROM example_sentences WHERE word_id = ? ORDER BY position LIMIT 1", (card["id"],)
        ).fetchone()
        card["example"] = dict(example) if example else None
        card["forms"] = [row["form"] for row in conn.execute("SELECT form FROM word_forms WHERE word_id = ?", (card["id"],))]
        notes = conn.execute("SELECT notes_tr FROM vocabulary WHERE id = ?", (card["id"],)).fetchone()
        card["notes_tr"] = notes["notes_tr"]
    return cards


def related_word_ids(conn: sqlite3.Connection, word_id: str, kind: str | None = None) -> set[str]:
    clause = "AND kind = ?" if kind else ""
    params = (word_id, kind, word_id, kind) if kind else (word_id, word_id)
    return {
        row[0]
        for row in conn.execute(
            f"""SELECT related_word_id FROM word_relations WHERE word_id = ? {clause}
                UNION SELECT word_id FROM word_relations WHERE related_word_id = ? {clause}""",  # noqa: S608
            params,
        )
    }


def distractor_pool(conn: sqlite3.Connection, level: str, pos: str, limit: int = 400) -> list[Row]:
    """Aynı türden, yakın seviyeden çeldirici adayları."""
    return _rows(
        conn,
        f"""{_WORD_BRIEF}
            WHERE v.id IN (SELECT word_id FROM word_meanings WHERE pos = ? AND position = 1)
            ORDER BY (v.level = ?) DESC, v.lemma_key LIMIT ?""",  # noqa: S608
        (pos, level, limit),
    )


def words_with_antonyms(conn: sqlite3.Connection, word_ids: list[str]) -> list[str]:
    candidates = set(word_ids)
    rows = conn.execute("SELECT word_id, related_word_id FROM word_relations WHERE kind = 'antonym'").fetchall()
    linked = {row[0] for row in rows} | {row[1] for row in rows}
    return [word_id for word_id in word_ids if word_id in candidates & linked]
