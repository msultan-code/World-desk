
import asyncio
import html
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
import feedparser
from bs4 import BeautifulSoup
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

VERSION = "1.0.1"

app = FastAPI(title=f"WORLD DESK v{VERSION}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("world-desk")

# Arabic sources only expanded in this release.
# Prefer verified RSS endpoints. Use HTML only when the publisher's RSS page
# itself reliably exposes current article headlines.
SOURCES = [
    {"name":"الجزيرة نت","cc":"QA","country":"قطر","lang":"ar","type":"rss",
     "url":"https://www.aljazeera.net/aljazeerarss/alarabic.xml","home":"https://www.aljazeera.net"},
    {"name":"الشرق الأوسط","cc":"SA","country":"السعودية","lang":"ar","type":"rss",
     "url":"https://aawsat.com/feed","home":"https://aawsat.com"},
    {"name":"الشروق","cc":"EG","country":"مصر","lang":"ar","type":"rss",
     "url":"https://www.shorouknews.com/rss/main","home":"https://www.shorouknews.com"},
    {"name":"مصراوي","cc":"EG","country":"مصر","lang":"ar","type":"rss",
     "url":"https://www.masrawy.com/rss/feed/25/%D8%A3%D8%AE%D8%A8%D8%A7%D8%B1","home":"https://www.masrawy.com"},
    {"name":"الخليج","cc":"AE","country":"الإمارات","lang":"ar","type":"rss",
     "url":"https://www.alkhaleej.ae/rssFeed/157","home":"https://www.alkhaleej.ae"},
    {"name":"الشرق القطرية","cc":"QA","country":"قطر","lang":"ar","type":"rss",
     "url":"https://al-sharq.com/rss/latestNews","home":"https://al-sharq.com"},
    {"name":"العرب القطرية","cc":"QA","country":"قطر","lang":"ar","type":"rss",
     "url":"https://alarab.qa/rss/latestNews","home":"https://alarab.qa"},
    {"name":"المدينة","cc":"SA","country":"السعودية","lang":"ar","type":"rss",
     "url":"https://www.al-madina.com/rssFeed/193","home":"https://www.al-madina.com"},
    {"name":"الأنباء الكويتية","cc":"KW","country":"الكويت","lang":"ar","type":"rss",
     "url":"https://www.alanba.com.kw/rss/kuwait-news","home":"https://www.alanba.com.kw"},
    {"name":"اليوم السابع","cc":"EG","country":"مصر","lang":"ar","type":"html",
     "url":"https://www.youm7.com/rss/rss","home":"https://www.youm7.com"},
    {"name":"الإمارات اليوم","cc":"AE","country":"الإمارات","lang":"ar","type":"html",
     "url":"https://www.emaratalyoum.com/rss-7.951867","home":"https://www.emaratalyoum.com"},
    # v1.0.1 repair: Sky News Arabia exposes a working public RSS endpoint
    # (the homepage is JS-rendered and returned no parseable headlines).
    {"name":"سكاي نيوز عربية","cc":"AE","country":"الإمارات","lang":"ar","type":"rss",
     "url":"https://www.skynewsarabia.com/rss","home":"https://www.skynewsarabia.com"},

    {"name":"المصري اليوم","cc":"EG","country":"مصر","lang":"ar","type":"html","url":"https://www.almasryalyoum.com/","home":"https://www.almasryalyoum.com"},
    # v1.0.1 repair: Veto exposes a working public RSS endpoint.
    {"name":"فيتو","cc":"EG","country":"مصر","lang":"ar","type":"rss",
     "url":"https://www.vetogate.com/rss","home":"https://www.vetogate.com"},
    {"name":"الوفد","cc":"EG","country":"مصر","lang":"ar","type":"html","url":"https://alwafd.news/","home":"https://alwafd.news"},
    {"name":"الراي الكويتية","cc":"KW","country":"الكويت","lang":"ar","type":"html","url":"https://www.alraimedia.com/","home":"https://www.alraimedia.com"},
    # v1.0.1 repair: Annahar exposes a working public RSS endpoint.
    {"name":"النهار","cc":"LB","country":"لبنان","lang":"ar","type":"rss",
     "url":"https://www.annahar.com/rss","home":"https://www.annahar.com"},
    {"name":"العربي الجديد","cc":"LB","country":"العالم العربي","lang":"ar","type":"html","url":"https://www.alaraby.co.uk/","home":"https://www.alaraby.co.uk"},
    {"name":"اندبندنت عربية","cc":"SA","country":"العالم العربي","lang":"ar","type":"html","url":"https://www.independentarabia.com/","home":"https://www.independentarabia.com"},
    {"name":"عمون","cc":"JO","country":"الأردن","lang":"ar","type":"html","url":"https://www.ammonnews.net/","home":"https://www.ammonnews.net"},
    {"name":"هسبريس","cc":"MA","country":"المغرب","lang":"ar","type":"html","url":"https://www.hespress.com/","home":"https://www.hespress.com"},
    {"name":"الخبر","cc":"DZ","country":"الجزائر","lang":"ar","type":"html","url":"https://www.elkhabar.com/","home":"https://www.elkhabar.com"},
    {"name":"تونس الرقمية","cc":"TN","country":"تونس","lang":"ar","type":"html","url":"https://ar.tunisienumerique.com/","home":"https://ar.tunisienumerique.com"},
    {"name":"شفق نيوز","cc":"IQ","country":"العراق","lang":"ar","type":"html","url":"https://shafaq.com/ar","home":"https://shafaq.com/ar"},
    {"name":"معا","cc":"PS","country":"فلسطين","lang":"ar","type":"html","url":"https://www.maannews.net/","home":"https://www.maannews.net"},
    {"name":"بوابة الوسط","cc":"LY","country":"ليبيا","lang":"ar","type":"html","url":"https://alwasat.ly/","home":"https://alwasat.ly"},

    # Existing international baseline, not expanded in this cycle.
    {"name":"BBC News","cc":"GB","country":"United Kingdom","lang":"en","type":"rss",
     "url":"https://feeds.bbci.co.uk/news/rss.xml","home":"https://www.bbc.com/news"},
    {"name":"The Guardian","cc":"GB","country":"United Kingdom","lang":"en","type":"rss",
     "url":"https://www.theguardian.com/world/rss","home":"https://www.theguardian.com"},
    {"name":"NPR","cc":"US","country":"United States","lang":"en","type":"rss",
     "url":"https://feeds.npr.org/1001/rss.xml","home":"https://www.npr.org"},
    {"name":"CBC News","cc":"CA","country":"Canada","lang":"en","type":"rss",
     "url":"https://www.cbc.ca/cmlink/rss-topstories","home":"https://www.cbc.ca/news"},
]
ARAB = {"EG","SA","AE","QA","KW","BH","OM","JO","LB","PS","IQ","SY","YE","MA","DZ","TN","LY","SD","MR"}
UA = f"Mozilla/5.0 (compatible; WORLD-DESK/{VERSION}; +news-reader)"

AR_RANGE = re.compile(r"[\u0600-\u06FF]")


def is_arabic(s: str) -> bool:
    """True if the string contains any Arabic-script character."""
    return bool(AR_RANGE.search(s or ""))


def clean(v) -> str:
    """Normalize text for storage and display.

    - remove literal '&nbsp;' text that sometimes survives parsing
    - decode all HTML/named/numeric entities (incl. &#8230;, &, ")
    - turn the non-breaking space (U+00A0) into a normal space
    - drop zero-width joiners/non-joiners that corrupt Arabic shaping
    - collapse runs of whitespace and trim

    Arabic letters and diacritics (tashkeel) are preserved untouched so valid
    Arabic is never damaged.
    """
    if not v:
        return ""
    s = html.unescape(str(v).replace("&nbsp;", " "))
    s = s.replace("\xa0", " ")                 # non-breaking space -> space
    s = s.replace("\u200b", "").replace("\u200c", "")  # zero-width spaces
    s = re.sub(r"\s+", " ", s).strip()
    return s


def norm_ar(s: str) -> set:
    """Tokenize an Arabic (or mixed) title for clustering/deduplication.

    Only used for similarity scoring, never for display, so the aggressive
    normalization here does not affect what the reader sees.
    """
    table = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه","ـ":""})
    s = clean(s).lower().translate(table)
    s = re.sub(r"[\u064B-\u065F\u0670]", "", s)   # strip diacritics for matching
    s = re.sub(r"[^\w\s]", " ", s)
    stop = {"في","من","على","الى","عن","مع","بعد","قبل","بين","هذا","هذه","ذلك",
            "التي","الذي","كان","كانت","حول","خلال","عاجل","اليوم"}
    return set(t for t in s.split() if len(t) > 2 and t not in stop)


def safe_article_url(src, href) -> str:
    if not href:
        return ""
    u = urljoin(src["home"], href)
    p = urlparse(u)
    if p.scheme not in ("http", "https"):
        return ""
    return u


# --- bilingual, correctly-pluralized cluster metadata ---------------------

def en_plural(n: int, one: str, many: str) -> str:
    return f"{n} {one}" if n == 1 else f"{n} {many}"


def ar_plural(n: int, one: str, two: str, few: str, many: str) -> str:
    """Arabic plural rules (singular / dual / few 3-10 / many 11+)."""
    if n == 1:
        return f"{n} {one}"
    if n == 2:
        return f"{n} {two}"
    if 3 <= n <= 10:
        return f"{n} {few}"
    return f"{n} {many}"


def cluster_meta(label: str, pubs: int, countries: int, headlines: int) -> str:
    """Natural bilingual metadata line for a story cluster.

    Arabic clusters get Arabic pluralized labels; everything else gets
    English pluralized labels. Counts are always accurate; nothing is
    duplicated or malformed (e.g. '...headlines 2').
    """
    if is_arabic(label):
        return " · ".join([
            ar_plural(pubs, "منشور", "منشوران", "منشورات", "منشورًا"),
            ar_plural(countries, "دولة", "دولتان", "دول", "دولة"),
            ar_plural(headlines, "عنوان", "عنوانان", "عناوين", "عنوانًا"),
        ])
    return " · ".join([
        en_plural(pubs, "publication", "publications"),
        en_plural(countries, "country", "countries"),
        en_plural(headlines, "headline", "headlines"),
    ])


def dedup_headlines(items: list) -> list:
    """Remove exact duplicate articles (same title + url), keeping the first.

    Within-source dedup happens during parsing; this dedups across sources so a
    story syndicated by two publishers does not appear twice in the wall.
    """
    seen = set()
    out = []
    for x in items:
        key = (x.get("title", ""), x.get("url", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def aggregate(gather_results) -> tuple:
    """Turn raw asyncio.gather(..., return_exceptions=True) results into
    (sources, headlines). Any result that is an Exception (a source that could
    not even be caught inside fetch_one) is converted to a failed source row so
    one broken publisher can never interrupt the ingestion cycle.
    """
    sources, items = [], []
    for r in gather_results:
        if isinstance(r, Exception):
            sources.append({"source": "unknown", "ok": False, "items": [],
                            "error": f"{type(r).__name__}: {r}"[:160]})
            log.error("source ingestion crashed: %s: %s", type(r).__name__, r)
            continue
        sources.append(r)
        items.extend(r.get("items", []))
    return sources, items


async def fetch_one(client, src):
    t0 = asyncio.get_event_loop().time()
    try:
        r = await client.get(src["url"], headers={"User-Agent": UA},
                             timeout=20, follow_redirects=True)
        r.raise_for_status()
        out = []

        if src["type"] == "rss":
            feed = feedparser.parse(r.content)
            seen = set()
            for e in feed.entries[:45]:
                title = clean(e.get("title"))
                link = safe_article_url(src, clean(e.get("link")))
                if not title or not link or (title, link) in seen:
                    continue
                seen.add((title, link))
                out.append({"title": title, "url": link})
        else:
            soup = BeautifulSoup(r.text, "html.parser")
            host = urlparse(src["home"]).netloc.replace("www.", "")
            seen = set()
            # Broadened selector set so publishers whose headlines live in
            # .title / .item / .card / .post containers are still captured.
            for selector in ["h1 a", "h2 a", "h3 a", "h4 a", "article a",
                             "a.title", ".title a", ".news-title a",
                             ".card a", ".item a", ".post a", ".article-card a"]:
                for a in soup.select(selector):
                    title = clean(a.get_text(" ", strip=True) or
                                  a.get("title") or a.get("aria-label") or "")
                    href = clean(a.get("href"))
                    if len(title) < 18 or len(title) > 220 or not href:
                        continue
                    u = safe_article_url(src, href)
                    if not u:
                        continue
                    uh = urlparse(u).netloc.replace("www.", "")
                    if host not in uh and uh not in host:
                        continue
                    if (title, u) in seen:
                        continue
                    seen.add((title, u))
                    out.append({"title": title, "url": u})
                    if len(out) >= 40:
                        break
                if len(out) >= 20:
                    break

        for x in out:
            x.update({
                "publication": src["name"],
                "country_code": src["cc"],
                "country": src["country"],
                "lang": src["lang"],
            })

        dur = round(asyncio.get_event_loop().time() - t0, 3)
        ok = len(out) > 0
        err = "" if ok else "No usable headlines returned"
        log.info("source=%s ok=%s items=%d duration=%ss status=%s error=%s",
                 src["name"], ok, len(out), dur, r.status_code,
                 err or src["url"])
        return {"source": src["name"], "ok": ok, "items": out,
                "duration": dur, "status": r.status_code, "error": err}

    except Exception as e:
        dur = round(asyncio.get_event_loop().time() - t0, 3)
        msg = str(e)[:160]
        log.warning("source=%s ok=False items=0 duration=%ss error=%s",
                    src["name"], dur, msg)
        return {"source": src["name"], "ok": False, "items": [],
                "duration": dur, "status": None, "error": msg}


def cluster(items, arab_only=False):
    work = [x for x in items
            if not arab_only or x["country_code"] in ARAB or x["lang"] == "ar"]
    groups = []
    for x in work:
        toks = norm_ar(x["title"])
        placed = False
        for g in groups:
            gt = g["tokens"]
            if not toks or not gt:
                continue
            score = len(toks & gt) / max(1, len(toks | gt))
            if score >= 0.27:
                g["items"].append(x)
                g["tokens"] |= toks
                placed = True
                break
        if not placed:
            groups.append({"tokens": set(toks), "items": [x]})

    result = []
    for g in groups:
        if len(g["items"]) < 2:
            continue
        pubs = len(set(i["publication"] for i in g["items"]))
        countries = len(set(i["country_code"] for i in g["items"]))
        label = sorted([i["title"] for i in g["items"]],
                      key=len)[len(g["items"]) // 2]
        result.append({
            "label": label,
            "headline_count": len(g["items"]),
            "publication_count": pubs,
            "country_count": countries,
            "meta": cluster_meta(label, pubs, countries, len(g["items"])),
            "items": g["items"][:15],
        })
    result.sort(key=lambda z: (z["country_count"] * 3 +
                               z["publication_count"] * 2 +
                               z["headline_count"]), reverse=True)
    return result[:20]


@app.get("/api/refresh")
async def refresh():
    async with httpx.AsyncClient() as client:
        raw = await asyncio.gather(
            *[fetch_one(client, s) for s in SOURCES],
            return_exceptions=True,
        )
    sources, items = aggregate(raw)
    items = dedup_headlines(items)
    ok = sum(1 for s in sources if s.get("ok"))
    log.info("ingestion complete: %d/%d sources ok, %d headlines",
             ok, len(sources), len(items))
    return {
        "version": VERSION,
        "sources": sources,
        "headlines": items[:700],
        "world": cluster(items, False),
        "arab": cluster(items, True),
    }


@app.get("/api/sources")
def sources():
    return {"version": VERSION, "sources": SOURCES}


@app.get("/healthz")
def healthz():
    """Liveness/health probe. Used by the Render web service health check.
    Returns 200 as long as the process is up; it does not depend on the
    database or any external source being reachable.
    """
    return JSONResponse({"status": "ok", "version": VERSION,
                          "sources": len(SOURCES)})


# Resolve publisher redirects server-side. This helps feeds whose raw link
# redirects through an intermediate URL or behaves poorly inside an installed PWA.
@app.get("/open")
async def open_original(url: str = Query(...)):
    p = urlparse(url)
    allowed = any(
        p.netloc.replace("www.", "").endswith(
            urlparse(s["home"]).netloc.replace("www.", ""))
        for s in SOURCES
    )
    if not allowed:
        return RedirectResponse(url="/", status_code=302)

    try:
        async with httpx.AsyncClient(headers={"User-Agent": UA}, timeout=10,
                                     follow_redirects=True) as client:
            r = await client.get(url)
            final = str(r.url)
            if final.startswith("http"):
                return RedirectResponse(url=final, status_code=302)
    except Exception:
        pass
    return RedirectResponse(url=url, status_code=302)


HTML = r"""<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#090909">
<title>WORLD DESK</title>
<style>
:root{--bg:#090909;--line:#242424;--fg:#f4f4f4;--muted:#777;--card:#131313}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
  padding-bottom:calc(60px + env(safe-area-inset-bottom));line-height:1.45}
header{position:sticky;top:0;z-index:8;background:#090909ee;backdrop-filter:blur(14px);
  padding:calc(15px + env(safe-area-inset-top)) 16px 12px;border-bottom:1px solid var(--line);
  display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:900;letter-spacing:.08em;font-size:20px}
.sub{font-size:9px;color:#777;letter-spacing:.13em;margin-top:3px}
button,select,input{font:inherit}
.refresh{width:44px;height:44px;border-radius:50%;background:#151515;color:#fff;
  border:1px solid #303030;font-size:21px;flex:none}
.tabs,.scopes{display:flex;background:#090909;border-bottom:1px solid var(--line);padding:0 10px}
.tabs button,.scopes button{flex:1;background:none;border:0;color:#777;padding:12px 7px;
  font-weight:800;font-size:12px;min-height:44px}
.tabs .active,.scopes .active{color:#fff;border-bottom:2px solid #fff}
.scopes{padding:10px 12px;border:0;gap:7px}
.scopes button{border:1px solid #292929;border-radius:10px}
.scopes .active{background:#eee;color:#111;border-color:#eee}
.section{padding:18px 16px 9px}
.eyebrow{font-size:10px;letter-spacing:.13em;color:#777;font-weight:800}
.section h1{font:28px Georgia,serif;margin:5px 0 0}
.meta{font-size:10px;color:#777;margin-top:6px;unicode-bidi:plaintext}
.hidden{display:none!important}
.empty{margin:20px 16px;padding:16px;border:1px dashed #2c2c2c;border-radius:12px;color:#777}
.back{background:none;border:0;color:#aaa;padding:0 0 12px;font-size:14px;min-height:44px}
.clusterHeader{padding:18px 16px 10px;border-bottom:1px solid var(--line)}
.clusterHeader h2{font:25px/1.4 Georgia,serif;margin:6px 0}
.clusterHeader[dir="rtl"] h2{font-family:"Geeza Pro","Noto Naskh Arabic",Tahoma,Arial,sans-serif}
.sourceok{color:#ccc}.sourcebad{color:#666}

/* Story cards (TOP STORIES) — styled so they read as cards on mobile. */
.storyCard{display:block;width:100%;background:var(--card);color:inherit;border:0;
  border-top:1px solid #202020;padding:14px 16px;text-align:left;text-decoration:none;cursor:pointer}
.storyCard.ar .storyRow{flex-direction:row-reverse}
.storyCard.ar{text-align:right}
.storyRow{display:flex;gap:12px;align-items:flex-start}
.storyNo{flex:none;font-size:12px;font-weight:800;color:#555;min-width:22px;
  padding-top:2px;unicode-bidi:isolate}
.storyBody{flex:1;min-width:0}
.storyTitle{font:clamp(17px,4.6vw,20px)/1.4 Georgia,"Times New Roman",serif;color:var(--fg)}
.storyCard.ar .storyTitle{font-family:"Geeza Pro","Noto Naskh Arabic",Tahoma,Arial,sans-serif;
  font-size:clamp(18px,4.8vw,21px);line-height:1.6}
.storyMeta{font-size:10px;color:#777;margin-top:7px;unicode-bidi:plaintext}
.storyCard.ar .storyMeta{text-align:right}
.chev{color:#555;font-size:14px;unicode-bidi:isolate}

/* Headline cards (HEADLINES wall + cluster items). */
.newsCard{display:block;width:100%;background:var(--card);color:inherit;
  border-top:1px solid #202020;padding:14px 16px;text-decoration:none}
.newsCard.ar{text-align:right}
.newsMeta{font-size:10px;color:#777;margin-bottom:7px;unicode-bidi:plaintext}
.newsMeta .sep{color:#444;margin:0 6px}
.newsTitle{font:clamp(16px,4.3vw,18px)/1.4 Georgia,"Times New Roman",serif;color:var(--fg)}
.newsCard.ar .newsTitle{font-family:"Geeza Pro","Noto Naskh Arabic",Tahoma,Arial,sans-serif;
  font-size:clamp(17px,4.6vw,19px);line-height:1.6}
.external{unicode-bidi:isolate}

/* Source health rows. */
.htitle{font-size:15px}
.headline .meta{unicode-bidi:plaintext}

.controls{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 12px}
.controls input,.controls select{background:#141414;color:#eee;border:1px solid #292929;
  border-radius:9px;padding:12px;min-height:44px}
.controls input{grid-column:1/-1}
.status{position:fixed;bottom:calc(8px + env(safe-area-inset-bottom));left:50%;
  transform:translateX(-50%);background:#1b1b1bef;border:1px solid #333;border-radius:99px;
  padding:6px 10px;color:#aaa;font-size:10px;z-index:20;white-space:nowrap;max-width:92vw;
  overflow:hidden;text-overflow:ellipsis}
</style>
</head>
<body>
<header>
  <div><div class="brand">WORLD DESK</div><div class="sub">GLOBAL NEWSPAPER INTELLIGENCE · v1.0.1</div></div>
  <button class="refresh" id="refresh" aria-label="Refresh">↻</button>
</header>

<div class="tabs">
  <button class="active" data-view="pulse">TOP STORIES</button>
  <button data-view="headlines">Headlines</button>
  <button data-view="sources">Sources</button>
</div>

<section id="pulse">
  <div class="section"><div class="eyebrow">TOP STORIES</div><h1>What the press is leading with</h1><div class="meta" id="freshness">LIVE</div></div>
  <div class="scopes"><button class="active" data-scope="world">🌍 WORLD</button><button data-scope="arab" dir="rtl">العالم العربي</button></div>
  <div id="stories"><div class="empty">Tap ↻ to load live headlines.</div></div>
</section>

<section id="headlines" class="hidden">
  <div class="controls">
    <select id="country"><option value="">All countries</option></select>
    <select id="pub"><option value="">All publications</option></select>
    <input id="q" placeholder="Search headlines">
  </div>
  <div id="wall"></div>
</section>

<section id="sources" class="hidden">
  <div class="section"><div class="eyebrow">SOURCE HEALTH</div><h1>Live sources</h1></div>
  <div id="sourceList"></div>
</section>

<section id="cluster" class="hidden">
  <div class="clusterHeader" id="clusterHeader">
    <button class="back" id="back">‹ Back to Pulse</button>
    <div class="eyebrow">STORY COVERAGE</div>
    <h2 id="clusterTitle"></h2>
    <div class="meta" id="clusterMeta"></div>
  </div>
  <div id="clusterItems"></div>
</section>

<div id="status" class="status" role="status" aria-live="polite">Ready</div>

<script>
let DATA={headlines:[],world:[],arab:[],sources:[]}, scope="world";
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const esc=s=>{let d=document.createElement("div");d.textContent=s||"";return d.innerHTML};
const isAr=s=>/[\u0600-\u06FF]/.test(s||"");
const dir=s=>isAr(s)?"rtl":"ltr";
const openUrl=u=>"/open?url="+encodeURIComponent(u);

function metaHTML(x){
  const ar = x.lang==="ar" || isAr(x.title) || isAr(x.publication);
  const seg=(t,cls)=>`<bdi class="${cls}">${esc(t)}</bdi>`;
  const sep=`<span class="sep" aria-hidden="true">·</span>`;
  const ext=`<bdi class="external" aria-hidden="true">↗</bdi>`;
  if(ar){
    return `${seg(x.country||x.country_code||"","seg")} ${sep} ${seg(x.publication||"","seg")} ${sep} ${seg("المصدر الأصلي","seg")} ${ext}`;
  }
  return `${seg(x.country_code||"","seg")} ${sep} ${seg(x.publication||"","seg")} ${sep} ${seg("Original","seg")} ${ext}`;
}
function headlineCard(x){
  const ar = x.lang==="ar" || isAr(x.title) || isAr(x.publication);
  return `<a class="newsCard ${ar?"ar":"en"}" href="${openUrl(x.url)}" target="_blank" rel="noopener"><div class="newsMeta">${metaHTML(x)}</div><div class="newsTitle">${esc(x.title)}</div></a>`;
}

function renderStories(){
  let a=DATA[scope]||[];
  $("#stories").innerHTML=a.length?a.map((x,i)=>{
    const ar=isAr(x.label);
    return `<button class="storyCard ${ar?"ar":"en"}" onclick="openCluster(${i})"><div class="storyRow"><div class="storyNo">${String(i+1).padStart(2,"0")}</div><div class="storyBody"><div class="storyTitle">${esc(x.label)}</div><div class="storyMeta" dir="${ar?"rtl":"ltr"}">${esc(x.meta||"")} <span class="chev">›</span></div></div></div></button>`;
  }).join(""):`<div class="empty">No multi-source story clusters yet.</div>`;
}
function openCluster(i){
  let x=(DATA[scope]||[])[i];
  if(!x)return;
  $("#pulse").classList.add("hidden");
  $("#cluster").classList.remove("hidden");
  const ar=isAr(x.label);
  $("#clusterHeader").setAttribute("dir",ar?"rtl":"ltr");
  $("#clusterTitle").textContent=x.label;
  const m=document.getElementById("clusterMeta");
  m.setAttribute("dir",ar?"rtl":"ltr");
  m.textContent=x.meta||"";
  $("#clusterItems").innerHTML=x.items.map(h=>headlineCard(h)).join("");
}
window.openCluster=openCluster;

function searchNorm(v){
  return (v||"").toLowerCase().normalize("NFKD")
    .replace(/[أإآ]/g,"ا").replace(/ى/g,"ي").replace(/ة/g,"ه").trim();
}

function renderWall(){
  let c=$("#country").value,p=$("#pub").value,q=searchNorm($("#q").value);
  let a=DATA.headlines.filter(x=>(!c||x.country_code===c)&&(!p||x.publication===p)&&(!q||searchNorm(x.title).includes(q)||searchNorm(x.publication).includes(q)));
  $("#wall").innerHTML=a.map(x=>headlineCard(x)).join("");
}
function renderSources(){
  let a=DATA.sources||[];
  $("#sourceList").innerHTML=a.map(x=>{
    const ar=isAr(x.source);
    return `<div class="newsCard ${ar?"ar":"en"}"><div class="newsMeta"><bdi class="seg">${x.ok?"●":"○"}</bdi> <bdi class="seg">${esc(x.source)}</bdi></div><div class="newsTitle" style="font-size:13px;color:#999">${x.ok?(x.items.length||x.count||0)+" headlines":esc(x.error||"failed")}</div></div>`;
  }).join("");
}

function filters(){
  let cs=[...new Set(DATA.headlines.map(x=>x.country_code))].sort();
  $("#country").innerHTML='<option value="">All countries</option>'+cs.map(c=>`<option>${c}</option>`).join("");
  let ps=[...new Set(DATA.headlines.map(x=>x.publication))].sort();
  $("#pub").innerHTML='<option value="">All publications</option>'+ps.map(p=>`<option>${esc(p)}</option>`).join("");
}

async function refresh(){
  $("#status").textContent="Loading live sources…";
  try{
    let r=await fetch("/api/refresh",{cache:"no-store"});
    if(!r.ok) throw new Error("HTTP "+r.status);
    DATA=await r.json();
    localStorage.setItem("wd101",JSON.stringify(DATA));
    filters();renderStories();renderWall();renderSources();
    let ok=(DATA.sources||[]).filter(x=>x.ok).length;
    $("#status").textContent=`${DATA.headlines.length} headlines · ${ok}/${DATA.sources.length} sources`;
    let f=document.getElementById("freshness"); if(f) f.textContent="LIVE · Updated just now";
  }catch(e){
    $("#status").textContent="Refresh failed";
  }
}

$("#refresh").onclick=refresh;
$("#back").onclick=()=>{$("#cluster").classList.add("hidden");$("#pulse").classList.remove("hidden");};

$$(".tabs button").forEach(b=>b.onclick=()=>{
  $$(".tabs button").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");
  ["pulse","headlines","sources","cluster"].forEach(v=>$("#"+v).classList.toggle("hidden",v!==b.dataset.view));
});

$$(".scopes button").forEach(b=>b.onclick=()=>{
  $$(".scopes button").forEach(x=>x.classList.remove("active"));
  b.classList.add("active");scope=b.dataset.scope;renderStories();
});

$("#country").onchange=renderWall;
$("#pub").onchange=renderWall;
$("#q").oninput=renderWall;

// Display refresh every 2 minutes; source refresh every 5 minutes while app is open.
setInterval(()=>{renderStories();renderWall();},120000);
setInterval(()=>{refresh();},300000);

try{
  let saved=localStorage.getItem("wd101");
  if(saved){DATA=JSON.parse(saved);filters();renderStories();renderWall();renderSources();
    $("#status").textContent="Cached headlines loaded";}
}catch(e){}

// First live fetch automatically.
refresh();
</script>
</body></html>"""


@app.get("/", response_class=HTMLResponse)
def home():
    return HTML


@app.get("/manifest.json")
def manifest():
    return JSONResponse({
        "name": "WORLD DESK",
        "short_name": "World Desk",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#090909",
        "theme_color": "#090909",
        "version": VERSION,
    })
