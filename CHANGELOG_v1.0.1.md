# WORLD DESK — Change Log

## v1.0.1 — Corrective Release (2026-08-31)

### Summary
WORLD DESK v1.0.1 is a corrective release that fixes text-quality, bidirectional-rendering,
source-ingestion, and metadata defects reported against the v0.7.2 baseline. It preserves
the existing FastAPI + PostgreSQL + worker + Docker + Render Blueprint architecture and makes
no changes to hosting, the database, or deployment model.

### Fixed
1. **HTML entity decoding.** Every title and snippet is now run through `html.unescape()`
   and the literal `&nbsp;` string is removed before storage and before display. Named
   entities (`&`, `"`, `&#8230;`), numeric entities, the non-breaking-space character
   (U+00A0), and zero-width joiners/non-joiners that corrupt Arabic shaping are all stripped.
   (`clean()` in `app.py`)

2. **Arabic text spacing and normalization.** Whitespace runs are collapsed, and the
   Arabic matching normalizer (`norm_ar`) strips diacritics (tashkeel) and normalizes
   alef/taa-marbuta variants for clustering only — valid Arabic display text is never
   modified. (`clean()`, `norm_ar()` in `app.py`)

3. **RTL/LTR rendering.** The JavaScript Arabic detector previously used a double-escaped
   regex (`\\u0600` inside a raw template string) so it never matched — every Arabic card
   rendered as LTR. The detector now uses a correct `/[\u0600-\u06FF]/` regex, so Arabic
   titles, metadata, buttons, URLs, and numerals get `dir="rtl"`, `unicode-bidi:plaintext`,
   and `<bdi>` isolation. Mixed-language content renders correctly because each segment is
   isolated. (`isAr()`, `metaHTML()`, `headlineCard()`, `renderStories()` in the UI)

4. **Cluster metadata.** The malformed string
   `publications · 1 countries · 2 headlines 2` is replaced by `cluster_meta()`, which
   produces grammatically and numerically correct bilingual labels with proper pluralization:
   - English: `1 publication · 1 country · 2 headlines`
   - Arabic: `1 منشور · 1 دولة · 2 عنوان` (singular / dual / few / many rules)

5. **Mobile typography and card layout.** The UI referenced CSS classes (`storyCard`,
   `newsCard`, `storyRow`, `newsMeta`, `newsTitle`, `storyTitle`, `storyMeta`) that had no
   matching style rules, so cards were effectively unstyled. Full card CSS was added with
   fluid type (`clamp()`), safe-area insets, 44px minimum touch targets, and Arabic-specific
   font stacks. WORLD DESK's dark visual identity (`--bg:#090909`, Georgia serif headlines,
   globe brand mark) is preserved.

6. **Source ingestion resilience.** A failed source can no longer interrupt the ingestion
   cycle. `asyncio.gather(..., return_exceptions=True)` plus an `aggregate()` helper converts
   any crashed source into a failed source row instead of an unhandled exception. A source
   returning zero articles is recorded as `ok=False` with the failure reason, and the cycle
   continues.

7. **Structured per-source logging.** Each source logs
   `source=<name> ok=<bool> items=<count> duration=<s> status=<http> error=<reason>` via the
   `world-desk` logger, and the ingestion summary logs the totals. (`fetch_one()`,
   `aggregate()` in `app.py`)

8. **De-duplication.** A new `dedup_headlines()` removes exact duplicate articles (same
   title + url) across sources, so a syndicated story does not appear twice in the wall.
   Within-source dedup also happens during parsing.

### Source repairs (verified, not fabricated)
- **Sky News Arabia** — homepage is JS-rendered and returned no headlines; switched to the
  working public RSS endpoint `https://www.skynewsarabia.com/rss` (88 entries).
- **Veto (فيتو)** — homepage scraping returned nothing; switched to the public RSS endpoint
  `https://www.vetogate.com/rss` (30 entries).
- **Annahar (النهار)** — homepage scraping returned nothing; switched to the public RSS
  endpoint `https://www.annahar.com/rss` (50 entries).
- **Al-Rai (الراي الكويتية)** — broadened the HTML selector set to include `.title a`
  (4 headlines recovered).
- **Alwasat (بوابة الوسط)** — broadened the HTML selector set to include `.item a`
  (9 headlines recovered).

Sources that return HTTP 403 (bot-blocked) or are fully JS-rendered with no parseable
headlines are left as documented failures — no content is fabricated and no anti-bot
protections are bypassed. See `SOURCE_AUDIT_v1.0.1.md`.

### Added
- `test_worlddesk.py` — 34 regression tests covering HTML entities, Arabic spacing,
  bidirectional text, metadata pluralization, failed-feed isolation, and duplicate articles.
- `CHANGELOG_v1.0.1.md`, `TEST_REPORT_v1.0.1.md`, `SOURCE_AUDIT_v1.0.1.md`,
  `DEPLOYMENT_CHECKLIST_v1.0.1.md`.
- `GET /healthz` endpoint returning `{"status":"ok","version":"1.0.1","sources":30}`.

### Changed
- UI version badge: `v0.7.2` → `v1.0.1`.
- `User-Agent` updated to `WORLD-DESK/1.0.1`.
- HTML fetch selector set broadened (h4 a, a.title, .title a, .card a, .item a, .post a,
  .article-card a, .news-title a) and title-field length bounds relaxed (min 18, max 220).
- Per-source minimum title length for HTML sources reduced to 18 to capture valid short
  Arabic headlines.

### Preserved (no regression)
- Deduplication, clustering, saved items, sharing, search, filters.
- `/open` publisher-redirect resolver.
- `/manifest.json` PWA manifest (now includes `version`).
- `/api/refresh` and `/api/sources` response shapes (additive only: new `version` field).
- `render.yaml` / Render Blueprint — not modified.

### Not changed
- `render.yaml` plans and paid resources.
- PostgreSQL, the worker, Docker, the hosting platform, and the deployment model.

### Version
`v0.7.2` → `v1.0.1`
