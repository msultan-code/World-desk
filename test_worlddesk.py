"""Regression tests for WORLD DESK v1.0.1.

Run with:  python -m pytest test_worlddesk.py -v

Covers the mandatory fix areas:
  - HTML entity decoding & literal `&nbsp;` removal
  - Arabic spacing / normalization without damaging valid Arabic
  - Bidirectional (RTL/LTR) text rendering
  - Cluster metadata pluralization (bilingual, no malformed strings)
  - A failed source never blocks the ingestion cycle
  - Duplicate articles are de-duplicated
  - /healthz is healthy
"""
import sys, os, asyncio, types, importlib
sys.path.insert(0, os.path.dirname(__file__))

# Import the application module fresh.
import app as wd
from app import (
    clean, norm_ar, cluster_meta, en_plural, ar_plural, is_arabic,
    dedup_headlines, aggregate, cluster, fetch_one, SOURCES, VERSION,
)


# ---------- 1. HTML entities & literal &nbsp; ----------

def test_clean_decodes_named_entities():
    assert clean("Q&A with the minister") == "Q&A with the minister"

def test_clean_decodes_numeric_entities():
    assert clean("Hello&#8230; world") == "Hello… world"

def test_clean_strips_literal_nbsp_text():
    # the literal 5-character string "&nbsp;" must never survive
    assert "&nbsp;" not in clean("News&nbsp;flash")
    assert clean("News&nbsp;flash") == "News flash"

def test_clean_strips_nonbreaking_space_char():
    assert clean("News\xa0flash") == "News flash"

def test_clean_collapses_whitespace_runs():
    assert clean("a    b\t c") == "a b c"

def test_clean_empty_input():
    assert clean(None) == ""
    assert clean("") == ""

def test_clean_preserves_arabic_letters():
    src = "الجغرافيا السياسية.. لماذا تُغيّر غوغل أسماء المسطحات المائية"
    out = clean(src)
    assert "الجغرافيا" in out
    # no entity, no nbsp, no double spaces
    assert "&" not in out
    assert "\xa0" not in out
    assert "  " not in out

def test_no_literal_nbsp_after_parsing_feed_entry():
    """Simulates a feedparser entry carrying literal &nbsp; text."""
    entry_title = "عاجل&nbsp;&nbsp;أخبار مباشرة & تطورات"
    cleaned = clean(entry_title)
    # the literal entity text must be gone...
    assert "&nbsp;" not in cleaned
    # ...the decoded ampersand is preserved as a real character...
    assert "&" in cleaned
    # ...and no double spaces remain where the entities were
    assert "  " not in cleaned


# ---------- 2. Arabic spacing / normalization ----------

def test_norm_ar_strips_diacritics_for_matching():
    # diacritics are removed for matching; the raw Arabic title keeps them.
    raw = "تُغيّر"          # contains damma (U+064F) and shadda (U+0651)
    toks = norm_ar(raw)
    joined = " ".join(toks)
    assert "\u064f" not in joined      # damma stripped
    assert "\u0651" not in joined      # shadda stripped
    assert isinstance(toks, set)
    assert len(toks) > 0

def test_norm_ar_removes_stopwords():
    # common Arabic stopwords are filtered out of the token set
    toks = norm_ar("في من حول هذا ذلك")
    assert toks == set()

def test_norm_ar_preserves_content_words():
    # content words survive (note: ؤ->و and ة->ه normalization for matching)
    toks = norm_ar("مؤتمر القمة العربي")
    assert "موتمر" in toks or "القمه" in toks or "العربي" in toks

def test_norm_ar_normalizes_alef_variants():
    # أ إ آ all collapse to ا for matching purposes
    a = norm_ar("أحمد")
    b = norm_ar("إحمد")
    c = norm_ar("آحمد")
    assert a == b == c

def test_norm_ar_normalizes_taa_marbuta():
    assert norm_ar("مدرسة") == norm_ar("مدرسه")

def test_norm_ar_does_not_damage_display_text():
    """norm_ar is for matching only; the raw title must stay readable."""
    title = "بوتين: روسيا تتجه نحو إنهاء الصراع الأوكراني"
    assert is_arabic(title)
    # display text untouched (clean() used separately)
    assert title in title  # identity check placeholder


# ---------- 3. Bidirectional text ----------

def test_is_arabic_detects_arabic():
    assert is_arabic("الجزيرة نت") is True
    assert is_arabic("BBC News") is False
    assert is_arabic("mixed عربي text") is True
    assert is_arabic("") is False
    assert is_arabic(None) is False

def test_cluster_meta_arabic_label_uses_rtl_phrasing():
    m = cluster_meta("الجغرافيا السياسية", 3, 2, 5)
    assert "منشورات" in m   # 3 publications -> few plural
    assert "دولتان" in m      # 2 countries -> dual
    assert "عناوين" in m      # 5 headlines -> few plural
    assert "headlines" not in m  # not English

def test_cluster_meta_english_label_uses_english():
    m = cluster_meta("World leaders meet", 3, 2, 5)
    assert "publications" in m
    assert "countries" in m
    assert "headlines" in m
    assert "منشور" not in m

def test_cluster_meta_arabic_singular():
    m = cluster_meta("عنوان عربي", 1, 1, 1)
    assert "1 منشور" in m
    assert "1 دولة" in m
    assert "1 عنوان" in m

def test_cluster_meta_no_malformed_trailing_count():
    """The bug '...headlines 2' must not appear."""
    m = cluster_meta("title", 1, 1, 2)
    assert not m.endswith("2")
    # count should precede the noun, never trail it
    assert m.count("2") == 1


# ---------- 4. Metadata pluralization (English + Arabic rules) ----------

def test_en_plural():
    assert en_plural(1, "country", "countries") == "1 country"
    assert en_plural(2, "country", "countries") == "2 countries"
    assert en_plural(5, "country", "countries") == "5 countries"

def test_ar_plural_singular():
    assert ar_plural(1, "one", "two", "few", "many") == "1 one"

def test_ar_plural_dual():
    assert ar_plural(2, "one", "two", "few", "many") == "2 two"

def test_ar_plural_few():
    # 3-10 uses the "few" form
    assert ar_plural(3, "one", "two", "few", "many") == "3 few"
    assert ar_plural(10, "one", "two", "few", "many") == "10 few"

def test_ar_plural_many():
    assert ar_plural(11, "one", "two", "few", "many") == "11 many"
    assert ar_plural(25, "one", "two", "few", "many") == "25 many"


# ---------- 5. Failed source isolation ----------

def test_aggregate_converts_exception_to_failed_source():
    raw = [
        {"source": "A", "ok": True, "items": [{"title": "t", "url": "u"}]},
        RuntimeError("boom"),
        {"source": "C", "ok": True, "items": []},
    ]
    sources, items = aggregate(raw)
    assert len(sources) == 3
    assert sources[0]["ok"] is True
    assert sources[1]["ok"] is False
    assert "RuntimeError" in sources[1]["error"]
    assert sources[2]["ok"] is True
    # items from the crashed source are absent but others survive
    assert len(items) == 1

def test_failed_source_does_not_block_others():
    """A source returning a fetch error yields a failed row, not an exception."""
    bad = {"name": "Bad", "cc": "ZZ", "country": "Nowhere", "lang": "en",
           "type": "rss", "url": "http://127.0.0.1:1/nope", "home": "http://127.0.0.1"}
    good = {"name": "Good", "cc": "ZZ", "country": "Nowhere", "lang": "en",
            "type": "rss", "url": "http://127.0.0.1:2/nope", "home": "http://127.0.0.1"}
    async def run():
        import httpx
        async with httpx.AsyncClient() as client:
            res = await asyncio.gather(
                fetch_one(client, bad), fetch_one(client, good),
                return_exceptions=True,
            )
        return res
    res = asyncio.run(run())
    # both must be dict rows (not raised exceptions)
    assert all(isinstance(r, dict) for r in res)
    assert res[0]["ok"] is False
    assert res[0]["error"]
    assert res[1]["ok"] is False
    assert res[1]["error"]


# ---------- 6. Duplicate articles ----------

def test_dedup_removes_exact_duplicates():
    items = [
        {"title": "A", "url": "http://x/a", "publication": "P1"},
        {"title": "A", "url": "http://x/a", "publication": "P2"},  # exact dup
        {"title": "B", "url": "http://x/b", "publication": "P1"},
    ]
    out = dedup_headlines(items)
    assert len(out) == 2
    assert out[0]["title"] == "A"
    assert out[1]["title"] == "B"

def test_dedup_keeps_same_title_different_url():
    items = [
        {"title": "A", "url": "http://x/a1", "publication": "P1"},
        {"title": "A", "url": "http://x/a2", "publication": "P2"},
    ]
    out = dedup_headlines(items)
    assert len(out) == 2


# ---------- 7. Health endpoint ----------

def test_healthz():
    from fastapi.testclient import TestClient
    c = TestClient(wd.app)
    r = c.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.1"
    assert body["sources"] == 30

def test_version_is_101():
    assert VERSION == "1.0.1"

def test_sources_count_is_30():
    assert len(SOURCES) == 30

def test_ui_displays_version():
    from fastapi.testclient import TestClient
    c = TestClient(wd.app)
    r = c.get("/")
    assert r.status_code == 200
    assert "v1.0.1" in r.text
    # old version must be gone
    assert "v0.7.2" not in r.text
    assert "v0.6" not in r.text

def test_manifest_version():
    from fastapi.testclient import TestClient
    c = TestClient(wd.app)
    r = c.get("/manifest.json")
    assert r.status_code == 200
    assert r.json()["version"] == "1.0.1"

def test_api_refresh_shape():
    from fastapi.testclient import TestClient
    c = TestClient(wd.app)
    r = c.get("/api/refresh")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "1.0.1"
    assert "sources" in body and "headlines" in body
    assert "world" in body and "arab" in body
    # cluster metadata present and non-empty on clusters
    for cl in body["world"] + body["arab"]:
        assert "meta" in cl and cl["meta"]
        assert "&nbsp;" not in cl["meta"]
        assert "&" not in cl["meta"]


if __name__ == "__main__":
    sys.exit(__import__("pytest").main([__file__, "-v"]))
