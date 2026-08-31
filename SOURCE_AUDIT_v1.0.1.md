# WORLD DESK v1.0.1 — Source Audit

**Date:** 2026-08-31 (live verification, ~17:04 UTC)
**Method:** Each of the 30 configured sources was fetched individually using the v1.0.1
ingestion code (`fetch_one` in `app.py`) with `User-Agent: Mozilla/5.0 (compatible;
WORLD-DESK/1.0.1; +news-reader)`, a 20s timeout, and redirect following. No source was
claimed working without a verified HTTP 200 and at least one parseable headline from a
public RSS endpoint or the publisher's own HTML.

**Totals:** 22/30 sources OK · 617 deduped headlines (up from 17/30 · 531 in the v0.7.2 baseline).

---

## Status legend
- ✅ **OK** — returns parseable headlines from a public endpoint.
- 🔧 **REPAIRED in v1.0.1** — was failing in v0.7.2, now working.
- ❌ **FAILED** — documented failure; not repaired (see reason). No content fabricated,
  no anti-bot protection bypassed.

## Repairs applied
| # | Source | Change | Verified result |
|---|---|---|---|
| 12 | سكاي نيوز عربية | `html`→`rss`, url `https://www.skynewsarabia.com/rss` | 45 items, 200 OK |
| 14 | فيتو | `html`→`rss`, url `https://www.vetogate.com/rss` | 30 items, 200 OK |
| 16 | الراي الكويتية | broadened HTML selectors (`.title a`) | 4 items, 200 OK |
| 17 | النهار | `html`→`rss`, url `https://www.annahar.com/rss` | 45 items, 200 OK |
| 26 | بوابة الوسط | broadened HTML selectors (`.item a`) | 9 items, 200 OK |

---

## Per-source audit (all 30)

| # | Source | CC | Type | Status | Items | Dur(s) | HTTP | Failure reason / note |
|---|---|---|---|---|---|---|---|---|
| 1 | الجزيرة نت | QA | rss | ✅ | 25 | 1.64 | 200 | — |
| 2 | الشرق الأوسط | SA | rss | ✅ | 45 | 0.52 | 200 | — |
| 3 | الشروق | EG | rss | ✅ | 9 | 1.84 | 200 | — |
| 4 | مصراوي | EG | rss | ❌ | 0 | 0.19 | 403 | Bot-blocked (403 Forbidden) on all `/rss` paths. Public RSS endpoint exists but rejects automated fetchers. Not bypassed. |
| 5 | الخليج | AE | rss | ✅ | 45 | 0.25 | 200 | — |
| 6 | الشرق القطرية | QA | rss | ✅ | 30 | 1.13 | 200 | — |
| 7 | العرب القطرية | QA | rss | ✅ | 30 | 0.73 | 200 | — |
| 8 | المدينة | SA | rss | ✅ | 45 | 0.78 | 200 | — |
| 9 | الأنباء الكويتية | KW | rss | ✅ | 42 | 0.34 | 200 | — |
| 10 | اليوم السابع | EG | html | ✅ | 10 | 0.59 | 200 | Parses its RSS-shaped HTML page. |
| 11 | الإمارات اليوم | AE | html | ✅ | 10 | 0.11 | 200 | — |
| 12 | سكاي نيوز عربية | AE | rss | 🔧 | 45 | 0.76 | 200 | Repaired: public RSS `https://www.skynewsarabia.com/rss`. |
| 13 | المصري اليوم | EG | html | ❌ | 0 | 1.10 | 200 | Homepage returns 200 but headlines are JS-rendered; no public RSS found. No usable headlines. |
| 14 | فيتو | EG | rss | 🔧 | 30 | 1.36 | 200 | Repaired: public RSS `https://www.vetogate.com/rss`. |
| 15 | الوفد | EG | html | ❌ | 0 | 0.87 | 403 | Bot-blocked (403 Forbidden). No public RSS found. Not bypassed. |
| 16 | الراي الكويتية | KW | html | 🔧 | 4 | 0.87 | 200 | Repaired via `.title a` selector. Low yield; site is largely JS-driven. |
| 17 | النهار | LB | rss | 🔧 | 45 | 1.25 | 200 | Repaired: public RSS `https://www.annahar.com/rss`. |
| 18 | العربي الجديد | LB | html | ❌ | 0 | 1.37 | 403 | Bot-blocked (403 Forbidden). No public RSS found. Not bypassed. |
| 19 | اندبندنت عربية | SA | html | ❌ | 0 | 0.87 | 403 | Bot-blocked (403 Forbidden). No public RSS found. Not bypassed. |
| 20 | عمون | JO | html | ✅ | 40 | 0.70 | 200 | — |
| 21 | هسبريس | MA | html | ❌ | 0 | 0.87 | 403 | Bot-blocked (403 Forbidden) on homepage and `/rss`. Not bypassed. |
| 22 | الخبر | DZ | html | ✅ | 40 | 1.33 | 200 | — |
| 23 | تونس الرقمية | TN | html | ❌ | 0 | 1.61 | 200 | Homepage returns 200 but headlines are JS-rendered; `/feed`/`/rss` return 404. No usable headlines. |
| 24 | شفق نيوز | IQ | html | ✅ | 6 | 2.15 | 200 | Low yield but valid. |
| 25 | معا | PS | html | ❌ | 0 | 1.34 | 403 | Bot-blocked (403 Forbidden). No public RSS found. Not bypassed. |
| 26 | بوابة الوسط | LY | html | 🔧 | 9 | 4.92 | 200 | Repaired via `.item a` selector. Slow response (~5s). |
| 27 | BBC News | GB | rss | ✅ | 32 | 1.35 | 200 | — |
| 28 | The Guardian | GB | rss | ✅ | 45 | 1.69 | 200 | — |
| 29 | NPR | US | rss | ✅ | 10 | 1.69 | 200 | — |
| 30 | CBC News | CA | rss | ✅ | 20 | 1.64 | 200 | — |

---

## Unresolved source failures (8)

These sources fail and are **intentionally left failing** in v1.0.1. Per the release
requirements, no content is fabricated and no source that prohibits automated access is
scraped. Each failure is recorded with its reason in the structured per-source log and in
the `/api/refresh` response, and none blocks the ingestion cycle.

| # | Source | Root cause | Recommended next step (out of scope for v1.0.1) |
|---|---|---|---|
| 4 | مصراوي | 403 on RSS | Contact publisher for an allowlisted feed URL, or add a server-side caching proxy with publisher consent. |
| 13 | المصري اليوم | JS-rendered, no RSS | Build a headless-browser parser with publisher consent, or request an RSS feed. |
| 15 | الوفد | 403 | Request an allowlisted feed URL. |
| 18 | العربي الجديد | 403 | Request an allowlisted feed URL. |
| 19 | اندبندنت عربية | 403 | Request an allowlisted feed URL. |
| 21 | هسبريس | 403 | Request an allowlisted feed URL. |
| 23 | تونس الرقمية | JS-rendered, no RSS | Build a headless-browser parser with publisher consent. |
| 25 | معا | 403 | Request an allowlisted feed URL. |

## Resilience guarantee
A 9th hypothetical failure — a source whose `fetch_one` raises an unhandled exception — is
caught by `asyncio.gather(..., return_exceptions=True)` and converted by `aggregate()` into
a `ok=False` source row, so one broken publisher can never interrupt the ingestion cycle.
This is covered by `test_aggregate_converts_exception_to_failed_source` and
`test_failed_source_does_not_block_others`.
