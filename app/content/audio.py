"""Ses klipleri: hangi içerik için hangi klibin gerektiği ve manifest okuma.

Sesler derleme sırasında üretilmez; `scripts/build_audio.py` ile önceden üretilip
`data/audio/` altına kaydedilir. Burada yalnızca gereken kliplerin tanımı (metin + ses)
hesaplanır. Manifestteki bir klip, tanımının özeti güncel içerikle aynıysa kullanılır;
metin değiştiyse eski ses kullanılmaz (yanlış ses çalmaktansa ses yok uyarısı gösterilir).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.content.text import lemma_key

if TYPE_CHECKING:
    from app.content.builder import Content

# Ses adı -> LibriTTS modelindeki konuşmacı numarası (bkz. docs/AUDIO.md).
VOICES: dict[str, int] = {"f1": 45, "f2": 840, "m1": 330, "m2": 375}
DEFAULT_VOICE = "f1"
DIALOGUE_ORDER = ("f1", "m1", "f2", "m2")  # diyalogda konuşmacılara sırayla atanır
MODEL_ID = "piper/en-us-libritts-high"
LINE_GAP_MS = 450  # metin/diyalog satırları arasındaki sessizlik


@dataclass(frozen=True)
class ClipSpec:
    key: str
    lines: tuple[tuple[str, str], ...]  # (ses adı, İngilizce metin)

    @property
    def digest(self) -> str:
        payload = json.dumps(
            {"model": MODEL_ID, "gap": LINE_GAP_MS, "lines": [[VOICES[voice], text] for voice, text in self.lines]},
            ensure_ascii=False, separators=(",", ":"),
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()  # noqa: S324 (güvenlik amaçlı değil)

    @property
    def filename(self) -> str:
        digest = self.digest
        return f"clips/{digest[:2]}/{digest}.mp3"


def word_key(lemma: str) -> str:
    return f"w:{lemma_key(lemma)}"


def phrase_key(text: str) -> str:
    return "s:" + hashlib.sha1(" ".join(text.split()).encode("utf-8")).hexdigest()[:20]  # noqa: S324


def lesson_key(lesson_id: str) -> str:
    return f"l:{lesson_id}"


def passage_voices(lines: list, declared: dict[str, str]) -> list[str]:
    """Her satır için kullanılacak ses adı."""
    assigned = dict(declared)
    result = []
    for line in lines:
        if not line.speaker:
            result.append(assigned.get("", DEFAULT_VOICE))
            continue
        if line.speaker not in assigned:
            used = set(assigned.values())
            assigned[line.speaker] = next((v for v in DIALOGUE_ORDER if v not in used), DEFAULT_VOICE)
        result.append(assigned[line.speaker])
    return result


def required_clips(content: "Content") -> dict[str, ClipSpec]:
    """İçeriğin tamamı için gereken klipler (anahtar -> tanım)."""
    clips: dict[str, ClipSpec] = {}
    for word in content.words.values():
        key = word_key(word.entry.lemma)
        clips[key] = ClipSpec(key, ((DEFAULT_VOICE, word.entry.lemma),))
    for lesson in content.lessons.values():
        if lesson.passage is not None and lesson.kind == "listening":
            voices = passage_voices(lesson.passage.lines, lesson.passage.voices)
            key = lesson_key(lesson.id)
            clips[key] = ClipSpec(key, tuple((voice, line.en) for voice, line in zip(voices, lesson.passage.lines)))
        for item in (*lesson.practice, *lesson.expressions):
            key = phrase_key(item.en)
            clips[key] = ClipSpec(key, ((DEFAULT_VOICE, item.en),))
    return clips


def read_manifest(audio_dir: Path) -> dict[str, dict]:
    path = audio_dir / "manifest.json"
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("clips", {}) if isinstance(data, dict) else {}


def available_clips(content: "Content", audio_dir: Path) -> dict[str, tuple[str, int]]:
    """Güncel ve dosyası yerinde olan klipler: anahtar -> (göreli yol, süre ms)."""
    manifest = read_manifest(audio_dir)
    result: dict[str, tuple[str, int]] = {}
    for key, spec in required_clips(content).items():
        entry = manifest.get(key)
        if not entry or entry.get("digest") != spec.digest:
            continue
        relative = str(entry.get("file", ""))
        if relative != spec.filename or not (audio_dir / relative).is_file():
            continue
        result[key] = (relative, int(entry.get("ms", 0)))
    return result
