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
    questions: list[Question] = Field(default_factory=list)


QuestionType = Literal[
    "multiple_choice", "true_false", "fill_blank", "sentence_building", "word_order", "matching",
    "translation", "written_answer", "error_spotting", "error_correction", "sentence_completion",
    "dialogue_completion", "reading_comprehension", "listening_comprehension", "word_in_context",
    "word_formation", "paragraph_completion", "nuance",
]

# Soru tipi -> değerlendirici. "choice": tek doğru seçenek; "text": kabul edilen cevap listesi;
# "order": sözcük sıralama; "matching": eşleştirme; "self": örnek cevapla öz değerlendirme.
EVALUATORS: dict[str, str] = {
    "multiple_choice": "choice", "true_false": "choice", "error_spotting": "choice",
    "sentence_completion": "choice", "dialogue_completion": "choice", "reading_comprehension": "choice",
    "listening_comprehension": "choice", "word_in_context": "choice", "paragraph_completion": "choice",
    "nuance": "choice",
    "fill_blank": "text", "sentence_building": "text", "error_correction": "text", "word_formation": "text",
    "translation": "text",
    "word_order": "order", "matching": "matching", "written_answer": "self",
}

DEFAULT_INSTRUCTIONS: dict[str, str] = {
    "multiple_choice": "Doğru seçeneği işaretleyin.",
    "true_false": "Cümle dil bilgisi açısından doğru mu, yanlış mı?",
    "fill_blank": "Boşluğu uygun biçimde doldurun.",
    "sentence_building": "Verilen sözcükleri kullanarak tam bir İngilizce cümle yazın.",
    "word_order": "Sözcükleri doğru sıraya dizin.",
    "matching": "Soldaki her öğeyi sağdaki uygun karşılığıyla eşleştirin.",
    "translation": "Cümleyi İngilizceye çevirin.",
    "written_answer": "Soruyu İngilizce tam cümlelerle cevaplayın.",
    "error_spotting": "Cümlede hatalı olan bölümü seçin.",
    "error_correction": "Cümledeki hatayı düzeltip cümleyi yeniden yazın.",
    "sentence_completion": "Cümleyi en uygun biçimde tamamlayan seçeneği işaretleyin.",
    "dialogue_completion": "Diyaloğu en uygun biçimde tamamlayan seçeneği işaretleyin.",
    "reading_comprehension": "Metni okuyun ve soruyu cevaplayın.",
    "listening_comprehension": "Kaydı dinleyin ve soruyu cevaplayın.",
    "word_in_context": "Cümleye en uygun kelimeyi seçin.",
    "word_formation": "Parantez içindeki kelimenin uygun biçimini yazın.",
    "paragraph_completion": "Paragraftaki boşluğa en uygun seçeneği işaretleyin.",
    "nuance": "Anlam farkına dikkat ederek doğru seçeneği işaretleyin.",
}


class QuestionExample(Strict):
    en: str = NonEmpty
    tr: str = NonEmpty


class Question(Strict):
    """Soru tanımı.

    Seçenekli tiplerde `options` satırları "metin :: açıklama" biçimindedir; doğru seçenek `*` ile başlar.
    Yazılı tiplerde `answers` kabul edilen cevapları listeler. `grading: strict` büyük/küçük harf ve
    noktalama farkını da değerlendirir.
    """

    id: str = Field(pattern=ID_PATTERN)
    type: QuestionType
    difficulty: int = Field(default=1, ge=1, le=5)
    prompt: str = NonEmpty
    context: str | None = None
    instruction_tr: str | None = None
    options: list[str] = Field(default_factory=list)
    answers: list[str] = Field(default_factory=list)
    grading: Literal["normalized", "strict"] = "normalized"
    tokens: list[str] = Field(default_factory=list, description="word_order: doğru sıradaki sözcükler")
    also: list[list[str]] = Field(default_factory=list, description="word_order: kabul edilen diğer sıralar")
    pairs: list[tuple[str, str]] = Field(default_factory=list, description="matching: [sol, sağ] çiftleri")
    model_answers: list[str] = Field(default_factory=list, description="öz değerlendirme için örnek cevaplar")
    checklist: list[str] = Field(default_factory=list)
    explanation: str = NonEmpty
    example: QuestionExample | None = None
    lessons: list[str] = Field(default_factory=list, description="ilgili diğer dersler")
    vocabulary: list[str] = Field(default_factory=list)

    def parsed_options(self) -> list[tuple[str, bool, str]]:
        """(metin, doğru mu, açıklama) üçlüleri."""
        parsed = []
        for raw in self.options:
            text, separator, why = raw.partition(" :: ")
            correct = text.startswith("*")
            parsed.append((text[1:].strip() if correct else text.strip(), correct, why.strip() if separator else ""))
        return parsed


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
