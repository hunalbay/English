"""Sözlük hazırlama yardımcıları (geliştirme aracı; uygulama çalışırken kullanılmaz).

    python scripts/vocab_tools.py stats
        Sözlükteki benzersiz temel kelime sayısını seviyelere göre gösterir.

    python scripts/vocab_tools.py candidates A2 150
        CEFR-J listesinde bulunan ama sözlükte henüz olmayan A2 kelimelerini listeler.

    python scripts/vocab_tools.py check-levels
        Sözlükteki seviyeleri CEFR-J ile karşılaştırır ve farkları listeler.

    python scripts/vocab_tools.py ipa /yol/cmudict.dict
        Sözlükteki kelimeler için data/pronunciation/ipa.tsv dosyasını CMUdict'ten üretir.
"""

from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.content import builder  # noqa: E402
from app.content.text import lemma_key  # noqa: E402

CEFRJ = ROOT / "data" / "reference" / "cefrj-vocabulary-profile-1.5.csv"
IPA_FILE = ROOT / "data" / "pronunciation" / "ipa.tsv"
LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]
POS_SHORT = {
    "noun": "n", "verb": "v", "adjective": "adj", "adverb": "adv", "pronoun": "pron", "preposition": "prep",
    "determiner": "det", "conjunction": "conj", "number": "num", "modal auxiliary": "modal", "be-verb": "v",
    "do-verb": "v", "have-verb": "v", "interjection": "int", "infinitive-to": "prep",
}


def cefrj() -> dict[str, tuple[str, list[str]]]:
    """temel biçim -> (en düşük seviye, türler)"""
    levels: dict[str, str] = {}
    pos: dict[str, list[str]] = defaultdict(list)
    with CEFRJ.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = lemma_key(row["headword"].split("/")[0])
            if key not in levels or LEVELS.index(row["CEFR"]) < LEVELS.index(levels[key]):
                levels[key] = row["CEFR"]
            short = POS_SHORT.get(row["pos"], row["pos"])
            if short not in pos[key]:
                pos[key].append(short)
    return {key: (levels[key], pos[key]) for key in levels}


def dictionary() -> dict[str, builder.LoadedWord]:
    return builder.load(ROOT / "data").words


def cmd_stats() -> None:
    words = dictionary()
    counts = Counter(word.level for word in words.values())
    for level in LEVELS:
        print(f"{level}: {counts.get(level, 0)}")
    print(f"Toplam benzersiz temel kelime: {len(words)}")


def cmd_candidates(level: str, limit: int) -> None:
    words = dictionary()
    known = set(words)
    for word in words.values():  # çekimli biçimi sözlükte olanlar da aday değildir
        known |= {lemma_key(form) for form in word.entry.forms}
    rows = [
        f"{key}({','.join(pos)})"
        for key, (word_level, pos) in sorted(cefrj().items())
        if word_level == level and key not in known and re.fullmatch(r"[a-z][a-z' -]*", key)
    ]
    print(f"# {level}: {len(rows)} aday kaldı; ilk {min(limit, len(rows))}:")
    print("  ".join(rows[:limit]))


def cmd_check_levels() -> None:
    reference = cefrj()
    differences = [
        f"{word.entry.lemma}: sözlük {word.level}, CEFR-J {reference[key][0]}"
        for key, word in sorted(dictionary().items())
        if key in reference and reference[key][0] != word.level
    ]
    print("\n".join(differences) or "Fark yok.")
    print(f"# {len(differences)} fark")


ARPABET = {
    "AA": "ɑ", "AE": "æ", "AO": "ɔ", "AW": "aʊ", "AY": "aɪ", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð",
    "EH": "ɛ", "EY": "eɪ", "F": "f", "G": "ɡ", "HH": "h", "IH": "ɪ", "IY": "i", "JH": "dʒ", "K": "k", "L": "l",
    "M": "m", "N": "n", "NG": "ŋ", "OW": "oʊ", "OY": "ɔɪ", "P": "p", "R": "r", "S": "s", "SH": "ʃ", "T": "t",
    "TH": "θ", "UH": "ʊ", "UW": "u", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ",
}
ONSETS = {
    "", "b", "d", "f", "ɡ", "h", "dʒ", "k", "l", "m", "n", "p", "r", "s", "ʃ", "t", "tʃ", "θ", "ð", "v", "w", "j", "z", "ʒ",
    "bl", "br", "dr", "dw", "fl", "fr", "ɡl", "ɡr", "kl", "kr", "kw", "pl", "pr", "sk", "sl", "sm", "sn", "sp", "st",
    "sw", "tr", "tw", "θr", "ʃr", "skr", "spl", "spr", "str", "skw", "bj", "fj", "hj", "kj", "mj", "pj", "vj", "nj",
}


def arpabet_to_ipa(phones: list[str]) -> str:
    """ARPAbet dizisini IPA'ya çevirir; vurgu işareti hece başına konur (en büyük başlangıç kuralı)."""
    symbols: list[str] = []
    stresses: list[str | None] = []
    for phone in phones:
        stress = phone[-1] if phone[-1].isdigit() else None
        base = phone.rstrip("012")
        if base == "AH":
            symbol = "ə" if stress == "0" else "ʌ"
        elif base == "ER":
            symbol = "ər" if stress == "0" else "ɜr"
        else:
            symbol = ARPABET[base]
        symbols.append(symbol)
        stresses.append(stress)
    if sum(1 for stress in stresses if stress is not None) < 2:
        return "".join(symbols)  # tek heceli sözcükte vurgu işareti gerekmez
    marks: dict[int, str] = {}
    for index, stress in enumerate(stresses):
        if stress not in ("1", "2"):
            continue
        start = index
        while start > 0 and stresses[start - 1] is None:
            start -= 1
        # Ünlüden önceki ünsüzlerden, geçerli bir hece başlangıcı oluşturan en uzun bölüm heceye aittir.
        while "".join(symbols[start:index]) not in ONSETS:
            start += 1
        marks[start] = "ˈ" if stress == "1" else "ˌ"
    return "".join(marks.get(index, "") + symbol for index, symbol in enumerate(symbols))


def cmd_ipa(cmudict_path: Path) -> None:
    pronunciations: dict[str, list[str]] = {}
    for line in cmudict_path.read_text(encoding="latin-1").splitlines():
        line = line.split(" #")[0].strip()
        if not line:
            continue
        word, *phones = line.split()
        if "(" not in word:  # yalnızca ilk (en yaygın) telaffuz
            pronunciations.setdefault(word, phones)
    lines = [
        "# Telaffuz (IPA, Amerikan İngilizcesi). Bu dosya scripts/vocab_tools.py ipa komutuyla",
        "# CMU Pronouncing Dictionary'den (Copyright (C) 1993-2015 Carnegie Mellon University, BSD lisansı)",
        "# otomatik dönüştürülerek üretilmiştir. Elle düzenlemeyin.",
    ]
    words = dictionary()
    found = 0
    for key in sorted(words):
        parts = key.split(" ")
        if all(part in pronunciations for part in parts):
            lines.append(f"{key}\t{' '.join(arpabet_to_ipa(pronunciations[part]) for part in parts)}")
            found += 1
    IPA_FILE.parent.mkdir(parents=True, exist_ok=True)
    IPA_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{found} / {len(words)} kelime için IPA yazıldı: {IPA_FILE}")


def main(argv: list[str]) -> int:
    if len(argv) >= 1 and argv[0] == "stats":
        cmd_stats()
    elif len(argv) == 3 and argv[0] == "candidates":
        cmd_candidates(argv[1].upper(), int(argv[2]))
    elif len(argv) == 1 and argv[0] == "check-levels":
        cmd_check_levels()
    elif len(argv) == 2 and argv[0] == "ipa":
        cmd_ipa(Path(argv[1]))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except builder.ContentError as exc:
        print("\n".join(exc.errors), file=sys.stderr)
        sys.exit(1)
