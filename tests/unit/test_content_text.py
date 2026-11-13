from app.content.text import english_tokens, fold_text, fts_query, lemma_key, slug, word_id


def test_lemma_key_normalizes_case_and_spaces():
    assert lemma_key("  Ice   Cream ") == "ice cream"
    assert lemma_key("I") == "i"


def test_word_id_is_stable_slug():
    assert word_id("ice cream") == "word.ice-cream"
    assert word_id("o'clock") == "word.o-clock"
    assert slug("Café") == "cafe"


def test_fold_text_handles_turkish_letters():
    assert fold_text("Öğrenci IŞIK İstanbul çay") == "ogrenci isik istanbul cay"


def test_english_tokens():
    assert english_tokens("She isn’t at home.") == ["she", "isn't", "at", "home"]


def test_fts_query_is_safe():
    assert fts_query('kitap" OR *') == '"kitap"* "or"*'
    assert fts_query("  ---  ") is None
    assert fts_query("ışık") == '"isik"*'
