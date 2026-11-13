"""İçerik kaynak dosyalarını yükler, doğrular ve content.db üretir.

Doğrulama iki aşamalıdır:
1. Her dosya kendi Pydantic şemasına göre denetlenir.
2. Dosyalar arası tutarlılık denetlenir (benzersizlik, bağlantı hedefleri vb.).

Tek bir hata bile varsa veri tabanı üretilmez.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from pydantic import ValidationError

from app.content.schema import DDL, SCHEMA_VERSION
from app.content.source_models import (
    DEFAULT_INSTRUCTIONS,
    EVALUATORS,
    CurriculumFile,
    LessonFile,
    SourcesFile,
    VocabularyFile,
    WordEntry,
)
from app.content.text import english_tokens, fold_text, lemma_key, regular_inflections, word_id

CONTENT_VERSION = "0.4.0"


class ContentError(Exception):
    def __init__(self, errors: list[str]) -> None:
        super().__init__(f"{len(errors)} içerik hatası")
        self.errors = errors


@dataclass
class LoadedWord:
    id: str
    key: str
    level: str
    source: str
    review_status: str
    entry: WordEntry
    origin: str


@dataclass
class Content:
    sources: SourcesFile
    curriculum: CurriculumFile
    lessons: dict[str, LessonFile] = field(default_factory=dict)
    words: dict[str, LoadedWord] = field(default_factory=dict)  # lemma_key -> kelime


def _read_yaml(path: Path, model, errors: list[str]):  # noqa: ANN001
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return model.model_validate(raw)
    except yaml.YAMLError as exc:
        errors.append(f"{path}: YAML okunamadı: {exc}")
    except ValidationError as exc:
        for issue in exc.errors():
            location = ".".join(str(part) for part in issue["loc"])
            errors.append(f"{path}: {location}: {issue['msg']}")
    return None


def load(data_dir: Path) -> Content:
    """Kaynak dosyaları okur ve doğrular. Hata varsa ContentError fırlatır."""
    errors: list[str] = []
    sources = _read_yaml(data_dir / "sources.yaml", SourcesFile, errors)
    curriculum = _read_yaml(data_dir / "curriculum" / "curriculum.yaml", CurriculumFile, errors)
    if sources is None or curriculum is None:
        raise ContentError(errors)
    content = Content(sources=sources, curriculum=curriculum)

    for path in sorted((data_dir / "lessons").rglob("*.yaml")):
        lesson = _read_yaml(path, LessonFile, errors)
        if lesson is None:
            continue
        if lesson.id in content.lessons:
            errors.append(f"{path}: ders kimliği yineleniyor: {lesson.id}")
        content.lessons[lesson.id] = lesson

    for path in sorted((data_dir / "vocabulary").rglob("*.yaml")):
        vocab = _read_yaml(path, VocabularyFile, errors)
        if vocab is None:
            continue
        _add_words(content, vocab, path, errors)

    for path in sorted((data_dir / "vocabulary").rglob("*.psv")):
        vocab = _read_psv(path, errors)
        if vocab is not None:
            _add_words(content, vocab, path, errors)

    ipa = _read_ipa(data_dir / "pronunciation" / "ipa.tsv", errors)
    for key, word in content.words.items():
        if word.entry.ipa is None and key in ipa:
            word.entry.ipa = ipa[key]

    homographs_file = data_dir / "vocabulary" / "homographs.txt"
    homographs = set()
    if homographs_file.is_file():
        homographs = {
            lemma_key(line) for line in homographs_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
    form_owner = {lemma_key(form): word for word in content.words.values() for form in word.entry.forms}
    for key, word in content.words.items():
        owner = form_owner.get(key)
        if owner is not None and key not in homographs:
            errors.append(
                f"kelime '{word.entry.lemma}' ({word.origin}): '{owner.entry.lemma}' kelimesinin çekimli biçimi olarak "
                "tanımlı. Bağımsız bir kelimeyse data/vocabulary/homographs.txt dosyasına ekleyin."
            )
    for key in sorted(homographs - {k for k in content.words if k in form_owner}):
        errors.append(f"homographs.txt: '{key}' artık gerekli değil (sözlükte yok ya da bir çekimle çakışmıyor)")

    errors.extend(validate(content))
    if errors:
        raise ContentError(errors)
    return content


POS_ABBREVIATIONS = {
    "n": "noun", "v": "verb", "adj": "adjective", "adv": "adverb", "pron": "pronoun", "prep": "preposition",
    "conj": "conjunction", "det": "determiner", "art": "article", "int": "interjection", "num": "numeral",
    "modal": "modal verb", "aux": "auxiliary verb", "phr": "phrase",
}


def _read_psv(path: Path, errors: list[str]) -> VocabularyFile | None:
    """Sıkıştırılmış kelime dosyası: `lemma | tür | Türkçe | örnek | çeviri | çekimler`.

    Başlık satırları `#! anahtar: değer` biçimindedir (level, source, review_status).
    Birden çok anlam için tür ve Türkçe alanları ` / ` ile ayrılır: `work | v / n | çalışmak / iş | ...`
    """
    header: dict[str, str] = {}
    words: list[dict] = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if line.startswith("#!"):
            key, _, value = line[2:].partition(":")
            header[key.strip()] = value.strip()
            continue
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) not in (5, 6):
            errors.append(f"{path}:{number}: 5 ya da 6 alan bekleniyor, {len(parts)} bulundu")
            continue
        lemma, pos_field, tr_field, en, ex_tr = parts[:5]
        pos_list = [item.strip() for item in pos_field.split("/")]
        tr_list = [item.strip() for item in tr_field.split(" / ")]
        if len(pos_list) != len(tr_list):
            errors.append(f"{path}:{number}: tür sayısı ({len(pos_list)}) ile anlam sayısı ({len(tr_list)}) uyuşmuyor")
            continue
        unknown = [item for item in pos_list if item not in POS_ABBREVIATIONS]
        if unknown:
            errors.append(f"{path}:{number}: bilinmeyen kelime türü: {', '.join(unknown)}")
            continue
        words.append({
            "lemma": lemma,
            "meanings": [{"pos": POS_ABBREVIATIONS[p], "tr": t} for p, t in zip(pos_list, tr_list)],
            "examples": [{"en": en, "tr": ex_tr}],
            "forms": [f.strip() for f in parts[5].split(",") if f.strip()] if len(parts) == 6 else [],
        })
    try:
        return VocabularyFile.model_validate({**header, "words": words})
    except ValidationError as exc:
        for issue in exc.errors():
            location = issue["loc"]
            lemma = words[location[1]]["lemma"] if len(location) > 1 and location[0] == "words" else ""
            errors.append(f"{path}: {lemma or '.'.join(str(part) for part in location)}: {issue['msg']}")
        return None


def _read_ipa(path: Path, errors: list[str]) -> dict[str, str]:
    """`temel biçim<TAB>IPA` satırlarından oluşan telaffuz dosyası (CMUdict'ten türetilir)."""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        key, tab, value = line.partition("\t")
        if not tab or not value.strip():
            errors.append(f"{path}:{number}: 'kelime<TAB>IPA' biçimi bekleniyor")
            continue
        result[lemma_key(key)] = value.strip()
    return result


def _add_words(content: Content, vocab: VocabularyFile, path: Path, errors: list[str]) -> None:
    for entry in vocab.words:
        key = lemma_key(entry.lemma)
        if key in content.words:
            errors.append(f"{path}: '{entry.lemma}' yineleniyor (ilk kayıt: {content.words[key].origin})")
            continue
        content.words[key] = LoadedWord(
            id=word_id(entry.lemma),
            key=key,
            level=entry.level or vocab.level,
            source=vocab.source,
            review_status=vocab.review_status,
            entry=entry,
            origin=path.name,
        )


def validate(content: Content) -> list[str]:
    """Dosyalar arası tutarlılık denetimleri."""
    errors: list[str] = []
    source_ids = {s.id for s in content.sources.sources}
    if len(source_ids) != len(content.sources.sources):
        errors.append("sources.yaml: kaynak kimlikleri benzersiz olmalıdır.")

    level_codes = [level.code for level in content.curriculum.levels]
    if level_codes != ["A1", "A2", "B1", "B2", "C1", "C2"]:
        errors.append("curriculum.yaml: seviyeler A1…C2 sırasıyla ve eksiksiz tanımlanmalıdır.")

    # Üniteler ve ders yerleşimi
    unit_ids: set[str] = set()
    placed: dict[str, str] = {}
    for unit in content.curriculum.units:
        if unit.id in unit_ids:
            errors.append(f"curriculum.yaml: ünite kimliği yineleniyor: {unit.id}")
        unit_ids.add(unit.id)
        for lesson_id in unit.lessons:
            lesson = content.lessons.get(lesson_id)
            if lesson is None:
                errors.append(f"curriculum.yaml: {unit.id} ünitesindeki ders bulunamadı: {lesson_id}")
                continue
            if lesson_id in placed:
                errors.append(f"curriculum.yaml: {lesson_id} birden fazla ünitede ({placed[lesson_id]}, {unit.id})")
            placed[lesson_id] = unit.id
            if lesson.level != unit.level:
                errors.append(f"{lesson_id}: ders seviyesi ({lesson.level}) ünite seviyesiyle ({unit.level}) uyuşmuyor")

    # Dersler
    for lesson in content.lessons.values():
        where = f"ders {lesson.id}"
        if lesson.id not in placed:
            errors.append(f"{where}: hiçbir üniteye yerleştirilmemiş")
        if lesson.source not in source_ids:
            errors.append(f"{where}: bilinmeyen kaynak '{lesson.source}'")
        for label, targets in (("prerequisites", lesson.prerequisites), ("next", lesson.next), ("related", lesson.related)):
            for target in targets:
                if target == lesson.id:
                    errors.append(f"{where}: {label} kendisine bağlanamaz")
                elif target not in content.lessons:
                    errors.append(f"{where}: {label} hedefi bulunamadı: {target}")
            if len(set(targets)) != len(targets):
                errors.append(f"{where}: {label} içinde yinelenen bağlantı var")
        for lemma in lesson.vocabulary:
            if lemma_key(lemma) not in content.words:
                errors.append(f"{where}: ilgili kelime sözlükte yok: '{lemma}'")
        kinds = {section.kind for section in lesson.sections}
        if lesson.kind == "grammar":
            for required in ("explanation", "common_mistakes"):
                if required not in kinds:
                    errors.append(f"{where}: dil bilgisi dersinde '{required}' bölümü zorunludur")
            if not any(section.examples for section in lesson.sections):
                errors.append(f"{where}: en az bir örnek cümle gereklidir")
        for section in lesson.sections:
            if section.kind == "correct_incorrect" and not any(example.wrong for example in section.examples):
                errors.append(f"{where}: '{section.title_tr}' bölümünde yanlış kullanım örneği yok")

    errors.extend(_validate_questions(content))

    # Kelimeler
    seen_ids: dict[str, str] = {}
    for word in content.words.values():
        entry = word.entry
        where = f"kelime '{entry.lemma}' ({word.origin})"
        if word.id in seen_ids:
            errors.append(f"{where}: kimlik çakışması ({word.id}) — '{seen_ids[word.id]}' ile")
        seen_ids[word.id] = entry.lemma
        if entry.lemma != " ".join(entry.lemma.split()):
            errors.append(f"{where}: gereksiz boşluk içeriyor")
        if word.source not in source_ids:
            errors.append(f"{where}: bilinmeyen kaynak '{word.source}'")
        if len({(m.pos, m.tr) for m in entry.meanings}) != len(entry.meanings):
            errors.append(f"{where}: yinelenen anlam kaydı")
        form_keys = [lemma_key(form) for form in entry.forms]
        if len(set(form_keys)) != len(form_keys) or word.key in form_keys:
            errors.append(f"{where}: çekimli biçimlerde yineleme var ya da temel biçim tekrar edilmiş")
        # Örnek cümlede kelimenin kendisi ya da tanımlı bir çekimi geçmelidir.
        accepted = [
            english_tokens(candidate)
            for candidate in (entry.lemma, *entry.forms, *sorted(regular_inflections(entry.lemma)))
        ]
        for example in entry.examples:
            tokens = english_tokens(example.en)
            if not any(_contains(tokens, candidate) for candidate in accepted if candidate):
                errors.append(f"{where}: örnek cümlede kelime ya da çekimi geçmiyor: \"{example.en}\"")
        for label, targets in (("synonyms", entry.synonyms), ("antonyms", entry.antonyms), ("related", entry.related)):
            for target in targets:
                target_key = lemma_key(target)
                if target_key == word.key:
                    errors.append(f"{where}: {label} kendisine bağlanamaz")
                elif target_key not in content.words:
                    errors.append(f"{where}: {label} hedefi sözlükte yok: '{target}'")
    return errors


def _validate_questions(content: Content) -> list[str]:
    errors: list[str] = []
    seen: dict[str, str] = {}
    for lesson in content.lessons.values():
        for question in lesson.questions:
            where = f"soru {question.id} ({lesson.id})"
            if question.id in seen:
                errors.append(f"{where}: soru kimliği yineleniyor (ilk kullanım: {seen[question.id]})")
            seen[question.id] = lesson.id
            evaluator = EVALUATORS[question.type]
            if evaluator == "choice":
                options = question.parsed_options()
                expected = 2 if question.type == "true_false" else 3
                if len(options) < expected or (question.type == "true_false" and len(options) != 2):
                    errors.append(f"{where}: seçenek sayısı yetersiz ya da hatalı ({len(options)})")
                if sum(1 for _, correct, _ in options if correct) != 1:
                    errors.append(f"{where}: tam olarak bir doğru seçenek (* ile) işaretlenmelidir")
                if any(not why for _, _, why in options):
                    errors.append(f"{where}: her seçeneğin açıklaması olmalıdır (metin :: açıklama)")
                texts = [text.lower() for text, _, _ in options]
                if len(set(texts)) != len(texts):
                    errors.append(f"{where}: yinelenen seçenek var")
            elif evaluator == "text":
                if not question.answers:
                    errors.append(f"{where}: en az bir kabul edilen cevap (answers) gereklidir")
                if question.type in ("fill_blank", "word_formation") and "___" not in question.prompt:
                    errors.append(f"{where}: soru metninde boşluk (___) bulunmalıdır")
            elif evaluator == "order":
                if len(question.tokens) < 3:
                    errors.append(f"{where}: en az üç sözcük (tokens) gereklidir")
                for alternative in question.also:
                    if sorted(alternative) != sorted(question.tokens):
                        errors.append(f"{where}: 'also' sırası aynı sözcüklerden oluşmalıdır")
            elif evaluator == "matching":
                lefts = [left for left, _ in question.pairs]
                rights = [right for _, right in question.pairs]
                if len(question.pairs) < 3 or len(set(lefts)) != len(lefts) or len(set(rights)) != len(rights):
                    errors.append(f"{where}: en az üç, birbirinden farklı eşleştirme çifti gereklidir")
            elif evaluator == "self" and not question.model_answers:
                errors.append(f"{where}: öz değerlendirme için örnek cevap (model_answers) gereklidir")
            if question.type in ("reading_comprehension", "dialogue_completion", "paragraph_completion") and not question.context:
                errors.append(f"{where}: bu soru tipi için metin (context) gereklidir")
            for target in question.lessons:
                if target not in content.lessons:
                    errors.append(f"{where}: ilgili ders bulunamadı: {target}")
            for lemma in question.vocabulary:
                if lemma_key(lemma) not in content.words:
                    errors.append(f"{where}: ilgili kelime sözlükte yok: '{lemma}'")
    return errors


def _contains(tokens: list[str], candidate: list[str]) -> bool:
    size = len(candidate)
    return any(tokens[i : i + size] == candidate for i in range(len(tokens) - size + 1))


def build(data_dir: Path, output: Path) -> dict[str, int]:
    """content.db dosyasını üretir ve kayıt sayılarını döndürür."""
    content = load(data_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    tmp = output.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    conn = sqlite3.connect(tmp)
    try:
        conn.executescript(DDL)
        _insert(conn, content)
        conn.execute("PRAGMA foreign_keys=ON")
        broken = conn.execute("PRAGMA foreign_key_check").fetchall()
        if broken:
            raise ContentError([f"yabancı anahtar ihlali: {row}" for row in broken[:20]])
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ContentError(["veri tabanı bütünlük denetimi başarısız"])
        conn.commit()
        counts = {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 (sabit tablo adları)
            for table in ("units", "lessons", "lesson_sections", "questions", "vocabulary", "word_meanings",
                          "example_sentences")
        }
        conn.execute("VACUUM")
    except Exception:
        conn.close()
        tmp.unlink(missing_ok=True)
        raise
    conn.close()
    tmp.replace(output)  # yarım kalmış bir dosya asla content.db olarak kalmaz
    return counts


def _insert(conn: sqlite3.Connection, content: Content) -> None:
    conn.executemany(
        "INSERT INTO content_meta VALUES (?, ?)",
        [
            ("content_version", CONTENT_VERSION),
            ("schema_version", SCHEMA_VERSION),
            ("built_at", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        ],
    )
    conn.executemany(
        "INSERT INTO content_sources VALUES (?, ?, ?, ?, ?)",
        [(s.id, s.name, s.license, s.url, s.notes) for s in content.sources.sources],
    )
    conn.executemany(
        "INSERT INTO levels VALUES (?, ?, ?, ?)",
        [(lv.code, i, lv.name_tr, lv.description_tr) for i, lv in enumerate(content.curriculum.levels, 1)],
    )

    unit_position: dict[str, int] = {}
    lesson_place: dict[str, tuple[str, int]] = {}
    for unit in content.curriculum.units:
        unit_position[unit.level] = unit_position.get(unit.level, 0) + 1
        conn.execute(
            "INSERT INTO units VALUES (?, ?, ?, ?, ?, ?)",
            (unit.id, unit.level, unit_position[unit.level], unit.title_tr, unit.title_en, unit.description_tr),
        )
        for position, lesson_id in enumerate(unit.lessons, 1):
            lesson_place[lesson_id] = (unit.id, position)

    for lesson in content.lessons.values():
        unit_id, position = lesson_place[lesson.id]
        conn.execute(
            "INSERT INTO lessons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lesson.id, unit_id, position, lesson.kind, lesson.level, lesson.title_tr, lesson.title_en,
             lesson.objective_tr, lesson.source, lesson.review_status),
        )
    for lesson in content.lessons.values():
        body_parts = [lesson.objective_tr]
        for position, section in enumerate(lesson.sections, 1):
            cursor = conn.execute(
                "INSERT INTO lesson_sections (lesson_id, position, kind, title_tr, text_tr, table_json) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (lesson.id, position, section.kind, section.title_tr, section.text_tr,
                 json.dumps(section.table.model_dump(), ensure_ascii=False) if section.table else None),
            )
            conn.executemany(
                "INSERT INTO example_sentences (section_id, position, en, tr, note_tr, is_incorrect, correction_en) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(cursor.lastrowid, i, ex.en, ex.tr, ex.note_tr, int(ex.wrong), ex.correction)
                 for i, ex in enumerate(section.examples, 1)],
            )
            body_parts += [section.title_tr, section.text_tr or ""]
            body_parts += [ex.en for ex in section.examples if not ex.wrong]
            if section.table:
                body_parts += [cell for row in section.table.rows for cell in row]
        for kind, targets in (("prerequisite", lesson.prerequisites), ("next", lesson.next), ("related", lesson.related)):
            conn.executemany(
                "INSERT INTO lesson_relations VALUES (?, ?, ?)", [(lesson.id, target, kind) for target in targets]
            )
        conn.execute(
            "INSERT INTO search_index (kind, ref_id, level, title, body) VALUES ('lesson', ?, ?, ?, ?)",
            (lesson.id, lesson.level, fold_text(f"{lesson.title_tr} {lesson.title_en}"), fold_text(" ".join(body_parts))),
        )

    for word in content.words.values():
        entry = word.entry
        conn.execute(
            "INSERT INTO vocabulary VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (word.id, entry.lemma, word.key, word.level, entry.frequency_rank, entry.ipa, entry.syllables,
             entry.notes_tr, word.source, word.review_status),
        )
        conn.executemany(
            "INSERT INTO word_meanings (word_id, position, pos, meaning_tr, definition_en) VALUES (?, ?, ?, ?, ?)",
            [(word.id, i, m.pos, m.tr, m.definition_en) for i, m in enumerate(entry.meanings, 1)],
        )
        conn.executemany(
            "INSERT INTO word_forms VALUES (?, ?)", [(word.id, lemma_key(form)) for form in entry.forms]
        )
        conn.executemany(
            "INSERT INTO example_sentences (word_id, position, en, tr) VALUES (?, ?, ?, ?)",
            [(word.id, i, ex.en, ex.tr) for i, ex in enumerate(entry.examples, 1)],
        )
        conn.executemany(
            "INSERT INTO collocations (word_id, phrase, meaning_tr) VALUES (?, ?, ?)",
            [(word.id, c.phrase, c.tr) for c in entry.collocations],
        )
        conn.execute(
            "INSERT INTO search_index (kind, ref_id, level, title, body) VALUES ('word', ?, ?, ?, ?)",
            (word.id, word.level, fold_text(" ".join([entry.lemma, *entry.forms])),
             fold_text(" ".join(m.tr for m in entry.meanings))),
        )
    for word in content.words.values():
        for kind, targets in (("synonym", word.entry.synonyms), ("antonym", word.entry.antonyms), ("related", word.entry.related)):
            conn.executemany(
                "INSERT OR IGNORE INTO word_relations VALUES (?, ?, ?)",
                [(word.id, content.words[lemma_key(target)].id, kind) for target in targets],
            )
    for lesson in content.lessons.values():
        conn.executemany(
            "INSERT OR IGNORE INTO lesson_vocabulary VALUES (?, ?)",
            [(lesson.id, content.words[lemma_key(lemma)].id) for lemma in lesson.vocabulary],
        )
    _insert_questions(conn, content)


def _insert_questions(conn: sqlite3.Connection, content: Content) -> None:
    for lesson in content.lessons.values():
        for position, question in enumerate(lesson.questions, 1):
            evaluator = EVALUATORS[question.type]
            data: dict = {}
            if evaluator == "order":
                data = {"tokens": question.tokens, "also": question.also}
            elif evaluator == "matching":
                data = {"pairs": [list(pair) for pair in question.pairs]}
            if question.model_answers:
                data["model_answers"] = question.model_answers
            if question.checklist:
                data["checklist"] = question.checklist
            conn.execute(
                "INSERT INTO questions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (question.id, lesson.id, position, lesson.level, question.type, evaluator,
                 question.grading if evaluator == "text" else "none", question.difficulty, question.prompt,
                 question.context, question.instruction_tr or DEFAULT_INSTRUCTIONS[question.type],
                 question.explanation, question.example.en if question.example else None,
                 question.example.tr if question.example else None,
                 json.dumps(data, ensure_ascii=False) if data else None, lesson.source, lesson.review_status),
            )
            conn.executemany(
                "INSERT INTO answer_options VALUES (?, ?, ?, ?, ?)",
                [(question.id, i, text, int(correct), why)
                 for i, (text, correct, why) in enumerate(question.parsed_options(), 1)],
            )
            conn.executemany(
                "INSERT INTO accepted_answers VALUES (?, ?, ?)",
                [(question.id, i, answer) for i, answer in enumerate(question.answers, 1)],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO question_lessons VALUES (?, ?)",
                [(question.id, target) for target in question.lessons if target != lesson.id],
            )
            conn.executemany(
                "INSERT OR IGNORE INTO question_vocabulary VALUES (?, ?)",
                [(question.id, content.words[lemma_key(lemma)].id) for lemma in question.vocabulary],
            )
