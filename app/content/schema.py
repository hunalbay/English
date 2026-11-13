"""content.db şeması.

Bu veri tabanı her derlemede sıfırdan üretilir; migration uygulanmaz.
Kimlikler (lesson.id, vocabulary.id, unit.id) sürümler arasında kararlı metin
değerleridir, çünkü kullanıcı ilerlemesi (user.db) bu kimliklere bağlanır.
"""

SCHEMA_VERSION = "2"

DDL = """
CREATE TABLE content_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE content_sources (
    id      TEXT PRIMARY KEY,
    name    TEXT NOT NULL,
    license TEXT NOT NULL,
    url     TEXT,
    notes   TEXT
);

CREATE TABLE levels (
    code           TEXT PRIMARY KEY CHECK (code IN ('A1','A2','B1','B2','C1','C2')),
    position       INTEGER NOT NULL UNIQUE,
    name_tr        TEXT NOT NULL,
    description_tr TEXT NOT NULL
);

CREATE TABLE units (
    id             TEXT PRIMARY KEY,
    level          TEXT NOT NULL REFERENCES levels(code),
    position       INTEGER NOT NULL,
    title_tr       TEXT NOT NULL,
    title_en       TEXT,
    description_tr TEXT,
    UNIQUE (level, position)
);

CREATE TABLE lessons (
    id            TEXT PRIMARY KEY,
    unit_id       TEXT NOT NULL REFERENCES units(id),
    position      INTEGER NOT NULL,
    kind          TEXT NOT NULL CHECK (kind IN ('grammar','vocabulary','reading','listening',
                                               'writing','speaking','pronunciation','expressions')),
    level         TEXT NOT NULL REFERENCES levels(code),
    title_tr      TEXT NOT NULL,
    title_en      TEXT NOT NULL,
    objective_tr  TEXT NOT NULL,
    source_id     TEXT NOT NULL REFERENCES content_sources(id),
    review_status TEXT NOT NULL CHECK (review_status IN ('draft','auto_checked','human_reviewed')),
    UNIQUE (unit_id, position)
);
CREATE INDEX ix_lessons_level ON lessons(level);

CREATE TABLE lesson_sections (
    id         INTEGER PRIMARY KEY,
    lesson_id  TEXT NOT NULL REFERENCES lessons(id),
    position   INTEGER NOT NULL,
    kind       TEXT NOT NULL,
    title_tr   TEXT NOT NULL,
    text_tr    TEXT,
    table_json TEXT,
    UNIQUE (lesson_id, position)
);

CREATE TABLE lesson_relations (
    lesson_id         TEXT NOT NULL REFERENCES lessons(id),
    related_lesson_id TEXT NOT NULL REFERENCES lessons(id),
    kind              TEXT NOT NULL CHECK (kind IN ('prerequisite','next','related')),
    PRIMARY KEY (lesson_id, related_lesson_id, kind),
    CHECK (lesson_id <> related_lesson_id)
);

CREATE TABLE vocabulary (
    id             TEXT PRIMARY KEY,
    lemma          TEXT NOT NULL,
    lemma_key      TEXT NOT NULL UNIQUE,   -- küçük harfe çevrilmiş, boşlukları sadeleştirilmiş temel biçim
    level          TEXT NOT NULL REFERENCES levels(code),
    frequency_rank INTEGER,
    ipa            TEXT,
    syllables      TEXT,
    notes_tr       TEXT,
    source_id      TEXT NOT NULL REFERENCES content_sources(id),
    review_status  TEXT NOT NULL CHECK (review_status IN ('draft','auto_checked','human_reviewed'))
);
CREATE INDEX ix_vocabulary_level ON vocabulary(level, lemma_key);

CREATE TABLE word_meanings (
    id            INTEGER PRIMARY KEY,
    word_id       TEXT NOT NULL REFERENCES vocabulary(id),
    position      INTEGER NOT NULL,
    pos           TEXT NOT NULL,
    meaning_tr    TEXT NOT NULL,
    definition_en TEXT,
    UNIQUE (word_id, position)
);

CREATE TABLE word_forms (
    word_id TEXT NOT NULL REFERENCES vocabulary(id),
    form    TEXT NOT NULL,
    PRIMARY KEY (word_id, form)
);
CREATE INDEX ix_word_forms_form ON word_forms(form);

CREATE TABLE collocations (
    id         INTEGER PRIMARY KEY,
    word_id    TEXT NOT NULL REFERENCES vocabulary(id),
    phrase     TEXT NOT NULL,
    meaning_tr TEXT,
    UNIQUE (word_id, phrase)
);

CREATE TABLE word_relations (
    word_id         TEXT NOT NULL REFERENCES vocabulary(id),
    related_word_id TEXT NOT NULL REFERENCES vocabulary(id),
    kind            TEXT NOT NULL CHECK (kind IN ('synonym','antonym','related')),
    PRIMARY KEY (word_id, related_word_id, kind),
    CHECK (word_id <> related_word_id)
);

CREATE TABLE lesson_vocabulary (
    lesson_id TEXT NOT NULL REFERENCES lessons(id),
    word_id   TEXT NOT NULL REFERENCES vocabulary(id),
    PRIMARY KEY (lesson_id, word_id)
);
CREATE INDEX ix_lesson_vocabulary_word ON lesson_vocabulary(word_id);

-- Örnek cümleler bir ders bölümüne ya da bir kelimeye aittir (ikisinden tam biri).
CREATE TABLE example_sentences (
    id            INTEGER PRIMARY KEY,
    section_id    INTEGER REFERENCES lesson_sections(id),
    word_id       TEXT REFERENCES vocabulary(id),
    position      INTEGER NOT NULL,
    en            TEXT NOT NULL,
    tr            TEXT NOT NULL,
    note_tr       TEXT,
    is_incorrect  INTEGER NOT NULL DEFAULT 0 CHECK (is_incorrect IN (0,1)),
    correction_en TEXT,
    CHECK ((section_id IS NULL) <> (word_id IS NULL)),
    CHECK (is_incorrect = 0 OR correction_en IS NOT NULL)
);
CREATE INDEX ix_examples_section ON example_sentences(section_id);
CREATE INDEX ix_examples_word ON example_sentences(word_id);

-- Tam metin arama. Metinler fold_text() ile sadeleştirilerek yazılır (ı→i vb.).
CREATE VIRTUAL TABLE search_index USING fts5(
    kind UNINDEXED, ref_id UNINDEXED, level UNINDEXED, title, body,
    tokenize = 'unicode61 remove_diacritics 2', prefix = '2 3 4'
);
"""
