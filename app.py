
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
import asyncio, re
from urllib.parse import urljoin, urlparse, quote
import httpx, feedparser
from bs4 import BeautifulSoup

app = FastAPI(title="WORLD DESK v0.6")

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
    {"name":"سكاي نيوز عربية","cc":"AE","country":"الإمارات","lang":"ar","type":"html",
     "url":"https://www.skynewsarabia.com/","home":"https://www.skynewsarabia.com"},

    {"name":"المصري اليوم","cc":"EG","country":"مصر","lang":"ar","type":"html","url":"https://www.almasryalyoum.com/","home":"https://www.almasryalyoum.com"},
    {"name":"فيتو","cc":"EG","country":"مصر","lang":"ar","type":"html","url":"https://www.vetogate.com/","home":"https://www.vetogate.com"},
    {"name":"الوفد","cc":"EG","country":"مصر","lang":"ar","type":"html","url":"https://alwafd.news/","home":"https://alwafd.news"},
    {"name":"الراي الكويتية","cc":"KW","country":"الكويت","lang":"ar","type":"html","url":"https://www.alraimedia.com/","home":"https://www.alraimedia.com"},
    {"name":"النهار","cc":"LB","country":"لبنان","lang":"ar","type":"html","url":"https://www.annahar.com/","home":"https://www.annahar.com"},
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
UA = "Mozilla/5.0 (compatible; WORLD-DESK/0.6; +news-reader)"

def clean(v):
    return re.sub(r"\s+"," ", v or "").strip()

def norm_ar(s):
    table = str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه","ـ":""})
    s = clean(s).lower().translate(table)
    s = re.sub(r"[\u064B-\u065F\u0670]","",s)
    s = re.sub(r"[^\w\s]"," ",s)
    stop={"في","من","على","الى","عن","مع","بعد","قبل","بين","هذا","هذه","ذلك","التي","الذي","كان","كانت","حول","خلال","عاجل","اليوم"}
    return set(t for t in s.split() if len(t)>2 and t not in stop)

def safe_article_url(src, href):
    if not href:
        return ""
    u = urljoin(src["home"], href)
    p = urlparse(u)
    if p.scheme not in ("http","https"):
        return ""
    return u

async def fetch_one(client, src):
    try:
        r = await client.get(src["url"], headers={"User-Agent":UA}, timeout=16, follow_redirects=True)
        r.raise_for_status()
        out=[]

        if src["type"] == "rss":
            feed=feedparser.parse(r.content)
            for e in feed.entries[:45]:
                title=clean(e.get("title"))
                link=safe_article_url(src, clean(e.get("link")))
                if title and link:
                    out.append({"title":title,"url":link})

        else:
            soup=BeautifulSoup(r.text,"html.parser")
            host=urlparse(src["home"]).netloc.replace("www.","")
            seen=set()

            # Prefer actual headline structures and avoid navigation links.
            for selector in ["h1 a","h2 a","h3 a","article a"]:
                for a in soup.select(selector):
                    title=clean(a.get_text(" ",strip=True))
                    href=clean(a.get("href"))
                    if len(title)<22 or len(title)>220 or not href:
                        continue
                    u=safe_article_url(src,href)
                    if not u:
                        continue
                    uh=urlparse(u).netloc.replace("www.","")
                    if host not in uh and uh not in host:
                        continue
                    if (title,u) in seen:
                        continue
                    seen.add((title,u))
                    out.append({"title":title,"url":u})
                    if len(out)>=40:
                        break
                if len(out)>=20:
                    break

        for x in out:
            x.update({
                "publication":src["name"],
                "country_code":src["cc"],
                "country":src["country"],
                "lang":src["lang"]
            })

        # A source with zero articles is NOT healthy.
        return {
            "source":src["name"],
            "ok":len(out)>0,
            "items":out,
            "error":"" if out else "No usable headlines returned"
        }

    except Exception as e:
        return {"source":src["name"],"ok":False,"items":[],"error":str(e)[:160]}

def cluster(items, arab_only=False):
    work=[x for x in items if not arab_only or x["country_code"] in ARAB or x["lang"]=="ar"]
    groups=[]
    for x in work:
        toks=norm_ar(x["title"])
        placed=False
        for g in groups:
            gt=g["tokens"]
            if not toks or not gt:
                continue
            score=len(toks & gt)/max(1,len(toks | gt))
            if score>=0.27:
                g["items"].append(x)
                g["tokens"] |= toks
                placed=True
                break
        if not placed:
            groups.append({"tokens":set(toks),"items":[x]})

    result=[]
    for g in groups:
        if len(g["items"])<2:
            continue
        pubs=len(set(i["publication"] for i in g["items"]))
        countries=len(set(i["country_code"] for i in g["items"]))
        label=sorted([i["title"] for i in g["items"]],key=len)[len(g["items"])//2]
        result.append({
            "label":label,
            "headline_count":len(g["items"]),
            "publication_count":pubs,
            "country_count":countries,
            "items":g["items"][:15]
        })
    result.sort(key=lambda z:(z["country_count"]*3+z["publication_count"]*2+z["headline_count"]),reverse=True)
    return result[:20]

@app.get("/api/refresh")
async def refresh():
    async with httpx.AsyncClient() as client:
        res=await asyncio.gather(*[fetch_one(client,s) for s in SOURCES])
    items=[i for r in res for i in r["items"]]
    return {
        "sources":res,
        "headlines":items[:700],
        "world":cluster(items,False),
        "arab":cluster(items,True)
    }

@app.get("/api/sources")
def sources():
    return SOURCES

# Resolve publisher redirects server-side. This helps feeds whose raw link
# redirects through an intermediate URL or behaves poorly inside an installed PWA.
@app.get("/open")
async def open_original(url: str = Query(...)):
    p=urlparse(url)
    allowed = any(
        p.netloc.replace("www.","").endswith(urlparse(s["home"]).netloc.replace("www.",""))
        for s in SOURCES
    )
    if not allowed:
        return RedirectResponse(url="/",status_code=302)

    try:
        async with httpx.AsyncClient(headers={"User-Agent":UA},timeout=10,follow_redirects=True) as client:
            r=await client.get(url)
            final=str(r.url)
            if final.startswith("http"):
                return RedirectResponse(url=final,status_code=302)
    except Exception:
        pass
    return RedirectResponse(url=url,status_code=302)

HTML = r"""<!doctype html>
<html lang="en" dir="ltr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="theme-color" content="#090909">
<title>WORLD DESK</title>
<style>
:root{--bg:#090909;--line:#242424;--fg:#f4f4f4;--muted:#777}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;padding-bottom:50px}
header{position:sticky;top:0;z-index:8;background:#090909ee;backdrop-filter:blur(14px);padding:calc(15px + env(safe-area-inset-top)) 16px 12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
.brand{font-weight:900;letter-spacing:.08em;font-size:20px}.sub{font-size:9px;color:#777;letter-spacing:.13em;margin-top:3px}
button,select,input{font:inherit}.refresh{width:40px;height:40px;border-radius:50%;background:#151515;color:#fff;border:1px solid #303030;font-size:21px}
.tabs,.scopes{display:flex;background:#090909;border-bottom:1px solid var(--line);padding:0 10px}
.tabs button,.scopes button{flex:1;background:none;border:0;color:#777;padding:12px 7px;font-weight:800;font-size:12px}
.tabs .active,.scopes .active{color:#fff;border-bottom:2px solid #fff}
.scopes{padding:10px 12px;border:0;gap:7px}.scopes button{border:1px solid #292929;border-radius:10px}.scopes .active{background:#eee;color:#111;border-color:#eee}
.section{padding:18px 16px 9px}.eyebrow{font-size:10px;letter-spacing:.13em;color:#777;font-weight:800}.section h1{font:28px Georgia,serif;margin:5px 0 0}
.story,.headline{display:block;width:100%;background:none;color:inherit;border:0;border-top:1px solid #202020;padding:14px 16px;text-decoration:none}
.story{cursor:pointer}
.story[dir="rtl"],.headline[dir="rtl"]{direction:rtl!important;text-align:right!important;unicode-bidi:plaintext}
.story[dir="ltr"],.headline[dir="ltr"]{direction:ltr!important;text-align:left!important;unicode-bidi:plaintext}
.storytitle,.htitle{font:18px/1.35 Georgia,"Times New Roman",serif}
.story[dir="rtl"] .storytitle,.headline[dir="rtl"] .htitle{font-family:"Geeza Pro","Noto Naskh Arabic",Tahoma,Arial,sans-serif;font-size:19px;line-height:1.55}
.meta{font-size:10px;color:#777;margin-top:6px}.story[dir="rtl"] .meta,.headline[dir="rtl"] .meta{direction:rtl;text-align:right;unicode-bidi:isolate}.num{font-size:10px;color:#555;margin-inline-end:7px}
.controls{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 12px}.controls input,.controls select{background:#141414;color:#eee;border:1px solid #292929;border-radius:9px;padding:10px}.controls input{grid-column:1/-1}
.status{position:fixed;bottom:calc(8px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);background:#1b1b1bef;border:1px solid #333;border-radius:99px;padding:6px 10px;color:#aaa;font-size:10px;z-index:20;white-space:nowrap}
.hidden{display:none!important}.empty{margin:20px 16px;padding:16px;border:1px dashed #2c2c2c;border-radius:12px;color:#777}
.back{background:none;border:0;color:#aaa;padding:0 0 12px;font-size:14px}
.clusterHeader{padding:18px 16px 10px;border-bottom:1px solid var(--line)}
.clusterHeader[dir="rtl"]{direction:rtl;text-align:right}
.clusterHeader h2{font:25px/1.4 Georgia,serif;margin:6px 0}
.clusterHeader[dir="rtl"] h2{font-family:"Geeza Pro","Noto Naskh Arabic",Tahoma,Arial,sans-serif}
.sourceok{color:#ccc}.sourcebad{color:#666}
</style>
</head>
<body>
<header>
  <div><div class="brand">WORLD DESK</div><div class="sub">GLOBAL NEWSPAPER INTELLIGENCE · v0.7.1</div></div>
  <button class="refresh" id="refresh">↻</button>
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

<div id="status" class="status">Ready</div>

<script>
let DATA={headlines:[],world:[],arab:[],sources:[]}, scope="world";
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const esc=s=>{let d=document.createElement("div");d.textContent=s||"";return d.innerHTML};
const isAr=s=>/[\\u0600-\\u06FF]/.test(s||"");
const dir=s=>isAr(s)?"rtl":"ltr";
function metaLine(x){
  if((x.lang==="ar") || isAr(x.title) || isAr(x.publication)){
    return `${esc(x.country)} · ${esc(x.publication)} · المصدر الأصلي ↗`;
  }
  return `${esc(x.country_code)} · ${esc(x.publication)} · ↗ Original`;
}
const openUrl=u=>"/open?url="+encodeURIComponent(u);

function renderStories(){
  let a=DATA[scope]||[];
  $("#stories").innerHTML=a.length?a.map((x,i)=>`
    <button class="story" dir="${dir(x.label)}" onclick="openCluster(${i})">
      <div class="storytitle"><span class="num">${String(i+1).padStart(2,"0")}</span>${esc(x.label)}</div>
      <div class="meta">${x.publication_count} publications · ${x.country_count} countries · ${x.headline_count} headlines · ›</div>
    </button>`).join(""):`<div class="empty">No multi-source story clusters yet.</div>`;
}

function openCluster(i){
  let x=(DATA[scope]||[])[i];
  if(!x)return;
  $("#pulse").classList.add("hidden");
  $("#cluster").classList.remove("hidden");
  $("#clusterHeader").setAttribute("dir",dir(x.label));
  $("#clusterTitle").textContent=x.label;
  $("#clusterMeta").textContent=`${x.publication_count} publications · ${x.country_count} countries · ${x.headline_count} headlines`;
  $("#clusterItems").innerHTML=x.items.map(h=>`
    <a class="headline" dir="${dir(h.title)}" href="${openUrl(h.url)}" target="_blank" rel="noopener">
      <div class="meta ${dir(h.title)==="rtl"?"rtlMeta":""}">${metaLine(h)}</div>
      <div class="htitle">${esc(h.title)}</div>
    </a>`).join("");
}
window.openCluster=openCluster;

function searchNorm(v){
  return (v||"").toLowerCase().normalize("NFKD")
    .replace(/[أإآ]/g,"ا").replace(/ى/g,"ي").replace(/ة/g,"ه").trim();
}

function renderWall(){
  let c=$("#country").value,p=$("#pub").value,q=searchNorm($("#q").value);
  let a=DATA.headlines.filter(x=>
    (!c||x.country_code===c)&&
    (!p||x.publication===p)&&
    (!q||searchNorm(x.title).includes(q)||searchNorm(x.publication).includes(q))
  );
  $("#wall").innerHTML=a.map(x=>`
    <a class="headline" dir="${dir(x.title)}" href="${openUrl(x.url)}" target="_blank" rel="noopener">
      <div class="meta ${dir(x.title)==="rtl"?"rtlMeta":""}">${metaLine(x)}</div>
      <div class="htitle">${esc(x.title)}</div>
    </a>`).join("");
}

function renderSources(){
  let a=DATA.sources||[];
  $("#sourceList").innerHTML=a.map(x=>`
    <div class="headline" dir="${dir(x.source)}">
      <div class="htitle ${x.ok?"sourceok":"sourcebad"}">${x.ok?"●":"○"} ${esc(x.source)}</div>
      <div class="meta">${x.ok?x.items.length+" headlines":esc(x.error||"failed")}</div>
    </div>`).join("");
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
    localStorage.setItem("wd06",JSON.stringify(DATA));
    filters();renderStories();renderWall();renderSources();
    let ok=DATA.sources.filter(x=>x.ok).length;
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
  let saved=localStorage.getItem("wd06");
  if(saved){
    DATA=JSON.parse(saved);filters();renderStories();renderWall();renderSources();
    $("#status").textContent="Cached headlines loaded";
  }
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
        "name":"WORLD DESK",
        "short_name":"World Desk",
        "start_url":"/",
        "display":"standalone",
        "background_color":"#090909",
        "theme_color":"#090909"
    })
