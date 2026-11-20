"""Ses klibi eşleştirmesi: yalnızca güncel ve dosyası yerinde olan klipler kullanılır."""

import json

from app.content import audio, builder
from tests.conftest import ROOT


def _content():
    return builder.load(ROOT / "data")


def test_every_word_practice_item_and_listening_lesson_needs_a_clip():
    content = _content()
    clips = audio.required_clips(content)
    assert audio.word_key("book") in clips
    listening = [lesson for lesson in content.lessons.values() if lesson.kind == "listening"]
    assert listening and all(audio.lesson_key(lesson.id) in clips for lesson in listening)
    reading = [lesson for lesson in content.lessons.values() if lesson.kind == "reading"]
    assert reading and not any(audio.lesson_key(lesson.id) in clips for lesson in reading)
    practice = [item for lesson in content.lessons.values() for item in lesson.practice]
    assert practice and all(audio.phrase_key(item.en) in clips for item in practice)
    expressions = [item for lesson in content.lessons.values() for item in lesson.expressions]
    assert expressions and all(audio.phrase_key(item.en) in clips for item in expressions)


def test_dialogue_speakers_get_different_voices():
    content = _content()
    lesson = content.lessons["listen.a1.at-the-cafe"]
    voices = audio.passage_voices(lesson.passage.lines, lesson.passage.voices)
    assert len(voices) == len(lesson.passage.lines)
    assert len(set(voices)) == 2 and set(voices) <= set(audio.VOICES)


def test_undeclared_speakers_are_assigned_distinct_voices():
    class Line:
        def __init__(self, speaker):
            self.speaker = speaker
    lines = [Line("A"), Line("B"), Line("A"), Line("C")]
    assert audio.passage_voices(lines, {}) == ["f1", "m1", "f1", "f2"]


def test_clip_digest_changes_with_text_and_voice():
    base = audio.ClipSpec("k", (("f1", "Hello."),))
    assert base.digest == audio.ClipSpec("other", (("f1", "Hello."),)).digest
    assert base.digest != audio.ClipSpec("k", (("f1", "Hello!"),)).digest
    assert base.digest != audio.ClipSpec("k", (("m1", "Hello."),)).digest


def test_only_current_clips_with_files_are_available(tmp_path):
    content = _content()
    needed = audio.required_clips(content)
    good, stale, missing = (needed[audio.word_key(w)] for w in ("book", "teacher", "water"))
    for spec in (good, stale):
        target = tmp_path / spec.filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"x")
    manifest = {
        good.key: {"file": good.filename, "digest": good.digest, "ms": 500},
        stale.key: {"file": stale.filename, "digest": "0" * 40, "ms": 500},      # metin değişmiş
        missing.key: {"file": missing.filename, "digest": missing.digest, "ms": 500},  # dosya yok
    }
    (tmp_path / "manifest.json").write_text(json.dumps({"clips": manifest}), encoding="utf-8")
    available = audio.available_clips(content, tmp_path)
    assert available == {good.key: (good.filename, 500)}


def test_no_manifest_means_no_audio(tmp_path):
    assert audio.available_clips(_content(), tmp_path) == {}
