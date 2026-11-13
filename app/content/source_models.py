"""data/ altındaki içerik kaynak dosyalarının şemaları (Pydantic).

Bilinmeyen alanlar hata sayılır; böylece yazım hataları sessizce kaybolmaz.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Level = Literal["A1", "A2", "B1", "B2", "C1", "C2"]
ReviewStatus = Literal["draft", "auto_checked", "human_reviewed"]
LessonKind = Literal[
    "grammar", "vocabulary", "reading", "listening", "writing", "speaking", "pronunciation", "expressions"
]
SectionKind = Literal[
    "explanation", "usage", "formula", "positive", "negative", "question", "examples",
    "correct_incorrect", "common_mistakes", "comparison", "exceptions", "daily_life", "review_tips",
]
PartOfSpeech = Literal[
    "noun", "verb", "adjective", "adverb", "pronoun", "preposition", "conjunction", "determiner",
    "article", "interjection", "numeral", "modal verb", "auxiliary verb", "phrase",
]

ID_PATTERN = r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$"
NonEmpty = Field(min_length=1)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Source(Strict):
    id: str = Field(pattern=ID_PATTERN)
    name: str = NonEmpty
    license: str = NonEmpty
    url: str | None = None
    notes: str | None = None


class SourcesFile(Strict):
    sources: list[Source]


class LevelDef(Strict):
    code: Level
    name_tr: str = NonEmpty
    description_tr: str = NonEmpty


class UnitDef(Strict):
    id: str = Field(pattern=ID_PATTERN)
    level: Level
    title_tr: str = NonEmpty
    title_en: str | None = None
    description_tr: str | None = None
    lessons: list[str] = Field(default_factory=list, description="Sıralı ders kimlikleri")


class CurriculumFile(Strict):
    levels: list[LevelDef]
    units: list[UnitDef]


class Example(Strict):
    en: str = NonEmpty
    tr: str = NonEmpty
    note_tr: str | None = None
    wrong: bool = False
    correction: str | None = None

    @model_validator(mode="after")
    def _wrong_needs_correction(self) -> "Example":
        if self.wrong and not self.correction:
            raise ValueError("Yanlış kullanım örneğinde 'correction' zorunludur.")
        if not self.wrong and self.correction:
            raise ValueError("'correction' yalnızca wrong: true olan örneklerde kullanılır.")
        return self


class Table(Strict):
    headers: list[str] = Field(min_length=2)
    rows: list[list[str]] = Field(min_length=1)

    @model_validator(mode="after")
    def _row_width(self) -> "Table":
        if any(len(row) != len(self.headers) for row in self.rows):
            raise ValueError("Tablo satırlarının sütun sayısı başlıklarla aynı olmalıdır.")
        return self


class Section(Strict):
    kind: SectionKind
    title_tr: str = NonEmpty
    text_tr: str | None = None
    table: Table | None = None
    examples: list[Example] = Field(default_factory=list)

    @model_validator(mode="after")
    def _not_empty(self) -> "Section":
        if not (self.text_tr or self.table or self.examples):
            raise ValueError("Bölüm boş olamaz (metin, tablo veya örnek gerekli).")
        return self


class LessonFile(Strict):
    id: str = Field(pattern=ID_PATTERN)
    kind: LessonKind
    level: Level
    title_tr: str = NonEmpty
    title_en: str = NonEmpty
    objective_tr: str = NonEmpty
    source: str
    review_status: ReviewStatus
    prerequisites: list[str] = Field(default_factory=list)
    next: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    vocabulary: list[str] = Field(default_factory=list, description="İlgili kelimelerin temel biçimleri")
    sections: list[Section] = Field(min_length=1)


class Meaning(Strict):
    pos: PartOfSpeech
    tr: str = NonEmpty
    definition_en: str | None = None


class WordExample(Strict):
    en: str = NonEmpty
    tr: str = NonEmpty


class Collocation(Strict):
    phrase: str = NonEmpty
    tr: str | None = None


class WordEntry(Strict):
    """Kelime kaydı. Tek anlam/tek örnek için kısa yazım (pos, tr, en, ex_tr) kullanılabilir."""

    lemma: str = NonEmpty
    level: Level | None = None  # dosya düzeyindeki varsayılanı ezer
    pos: PartOfSpeech | None = None
    tr: str | None = None
    en: str | None = None
    ex_tr: str | None = None
    meanings: list[Meaning] = Field(default_factory=list)
    examples: list[WordExample] = Field(default_factory=list)
    forms: list[str] = Field(default_factory=list)
    ipa: str | None = None
    syllables: str | None = None
    frequency_rank: int | None = Field(default=None, ge=1)
    collocations: list[Collocation] = Field(default_factory=list)
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    notes_tr: str | None = None

    @model_validator(mode="after")
    def _expand_shorthand(self) -> "WordEntry":
        if (self.pos is None) != (self.tr is None):
            raise ValueError(f"{self.lemma}: 'pos' ve 'tr' birlikte verilmelidir.")
        if self.pos and self.tr:
            self.meanings.insert(0, Meaning(pos=self.pos, tr=self.tr))
        if (self.en is None) != (self.ex_tr is None):
            raise ValueError(f"{self.lemma}: 'en' ve 'ex_tr' birlikte verilmelidir.")
        if self.en and self.ex_tr:
            self.examples.insert(0, WordExample(en=self.en, tr=self.ex_tr))
        if not self.meanings:
            raise ValueError(f"{self.lemma}: en az bir anlam gereklidir.")
        return self


class VocabularyFile(Strict):
    level: Level
    source: str
    review_status: ReviewStatus
    words: list[WordEntry]
