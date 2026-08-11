
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
import asyncio, re, hashlib
from urllib.parse import urljoin, urlparse
import httpx, feedparser
from bs4 import BeautifulSoup

app = FastAPI(title="WORLD DESK v0.4")

SOURCES = [
 {"name":"Al Jazeera Arabic","cc":"QA","country":"Qatar","lang":"ar","type":"rss","url":"https://www.aljazeera.net/aljazeerarss/alarabic.xml"},
 {"name":"Asharq Al-Awsat","cc":"SA","country":"Saudi Arabia","lang":"ar","type":"rss","url":"https://aawsat.com/feed"},
 {"name":"Youm7","cc":"EG","country":"Egypt","lang":"ar","type":"html","url":"https://www.youm7.com/"},
 {"name":"Al Shorouk","cc":"EG","country":"Egypt","lang":"ar","type":"html","url":"https://www.shorouknews.com/"},
 {"name":"Al Riyadh","cc":"SA","country":"Saudi Arabia","lang":"ar","type":"html","url":"https://www.alriyadh.com/"},
 {"name":"Al Khaleej","cc":"AE","country":"United Arab Emirates","lang":"ar","type":"html","url":"https://www.alkhaleej.ae/"},
 {"name":"Al Sharq Qatar","cc":"QA","country":"Qatar","lang":"ar","type":"html","url":"https://al-sharq.com/"},
 {"name":"Al Arab Qatar","cc":"QA","country":"Qatar","lang":"ar","type":"html","url":"https://alarab.qa/"},
 {"name":"Ammon News","cc":"JO","country":"Jordan","lang":"ar","type":"html","url":"https://www.ammonnews.net/"},
 {"name":"BBC News","cc":"GB","country":"United Kingdom","lang":"en","type":"rss","url":"https://feeds.bbci.co.uk/news/rss.xml"},
 {"name":"The Guardian","cc":"GB","country":"United Kingdom","lang":"en","type":"rss","url":"https://www.theguardian.com/world/rss"},
 {"name":"NPR","cc":"US","country":"United States","lang":"en","type":"rss","url":"https://feeds.npr.org/1001/rss.xml"},
 {"name":"CBC News","cc":"CA","country":"Canada","lang":"en","type":"rss","url":"https://www.cbc.ca/cmlink/rss-topstories"},
 {"name":"ABC News Australia","cc":"AU","country":"Australia","lang":"en","type":"rss","url":"https://www.abc.net.au/news/feed/51120/rss.xml"},
 {"name":"France 24 English","cc":"FR","country":"France","lang":"en","type":"rss","url":"https://www.france24.com/en/rss"},
 {"name":"Deutsche Welle","cc":"DE","country":"Germany","lang":"en","type":"rss","url":"https://rss.dw.com/rdf/rss-en-all"},
 {"name":"Times of India","cc":"IN","country":"India","lang":"en","type":"rss","url":"https://timesofindia.indiatimes.com/rssfeedstopstories.cms"},
 {"name":"The Hindu","cc":"IN","country":"India","lang":"en","type":"rss","url":"https://www.thehindu.com/news/feeder/default.rss"},
 {"name":"Japan Times","cc":"JP","country":"Japan","lang":"en","type":"rss","url":"https://www.japantimes.co.jp/feed/"},
]
ARAB={"EG","SA","AE","QA","KW","BH","OM","JO","LB","PS","IQ","SY","YE","MA","DZ","TN","LY","SD","MR"}
UA="WORLD-DESK/0.4"

def clean(s): return re.sub(r"\s+"," ",s or "").strip()
def norm_ar(s):
    table=str.maketrans({"أ":"ا","إ":"ا","آ":"ا","ى":"ي","ؤ":"و","ئ":"ي","ة":"ه","ـ":""})
    s=clean(s).lower().translate(table)
    s=re.sub(r"[\u064B-\u065F\u0670]","",s)
    s=re.sub(r"[^\w\s]"," ",s)
    stop={"في","من","على","الى","عن","مع","بعد","قبل","بين","هذا","هذه","ذلك","التي","الذي","كان","كانت","حول","خلال","عاجل","اليوم"}
    return set(t for t in s.split() if len(t)>2 and t not in stop)

async def fetch_one(client,src):
    try:
        r=await client.get(src["url"],headers={"User-Agent":UA},timeout=12,follow_redirects=True)
        r.raise_for_status()
        out=[]
        if src["type"]=="rss":
            feed=feedparser.parse(r.content)
            for e in feed.entries[:35]:
                t=clean(e.get("title")); u=clean(e.get("link"))
                if t and u: out.append({"title":t,"url":u})
        else:
            soup=BeautifulSoup(r.text,"html.parser")
            host=urlparse(src["url"]).netloc.replace("www.","")
            seen=set()
            for sel in ["h1 a","h2 a","h3 a","article a","a"]:
                for a in soup.select(sel):
                    t=clean(a.get_text(" ",strip=True)); href=clean(a.get("href"))
                    if len(t)<24 or len(t)>220 or not href: continue
                    u=urljoin(src["url"],href)
                    uh=urlparse(u).netloc.replace("www.","")
                    if host not in uh and uh not in host: continue
                    if (t,u) in seen: continue
                    seen.add((t,u)); out.append({"title":t,"url":u})
                    if len(out)>=35: break
                if len(out)>=20: break
        for x in out:
            x.update({"publication":src["name"],"country_code":src["cc"],"country":src["country"],"lang":src["lang"]})
        return {"source":src["name"],"ok":True,"items":out}
    except Exception as e:
        return {"source":src["name"],"ok":False,"error":str(e)[:160],"items":[]}

def cluster(items, arab_only=False):
    work=[x for x in items if (not arab_only or x["country_code"] in ARAB or x["lang"]=="ar")]
    groups=[]
    for x in work:
        toks=norm_ar(x["title"])
        placed=False
        for g in groups:
            gt=g["tokens"]
            if not toks or not gt: continue
            score=len(toks&gt)/max(1,len(toks|gt))
            if score>=0.28:
                g["items"].append(x); g["tokens"] |= toks; placed=True; break
        if not placed:
            groups.append({"tokens":set(toks),"items":[x]})
    result=[]
    for g in groups:
        pubs=len(set(i["publication"] for i in g["items"]))
        countries=len(set(i["country_code"] for i in g["items"]))
        if len(g["items"])<2: continue
        label=sorted([i["title"] for i in g["items"]],key=len)[len(g["items"])//2]
        result.append({"label":label,"headline_count":len(g["items"]),"publication_count":pubs,"country_count":countries,"items":g["items"][:12]})
    result.sort(key=lambda z:(z["country_count"]*3+z["publication_count"]*2+z["headline_count"]),reverse=True)
    return result[:20]

@app.get("/api/refresh")
async def refresh():
    async with httpx.AsyncClient() as client:
        res=await asyncio.gather(*[fetch_one(client,s) for s in SOURCES])
    items=[i for r in res for i in r["items"]]
    return {"sources":res,"headlines":items[:500],"world":cluster(items,False),"arab":cluster(items,True)}

@app.get("/api/sources")
def sources(): return SOURCES

HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="theme-color" content="#090909"><title>WORLD DESK</title>
<style>
:root{--bg:#090909;--line:#242424;--fg:#f4f4f4;--muted:#777}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;padding-bottom:40px}
header{position:sticky;top:0;z-index:8;background:#090909ee;backdrop-filter:blur(14px);padding:calc(15px + env(safe-area-inset-top)) 16px 12px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between}.brand{font-weight:900;letter-spacing:.08em;font-size:20px}.sub{font-size:9px;color:#777;letter-spacing:.13em;margin-top:3px}
button,select,input{font:inherit}.refresh{width:40px;height:40px;border-radius:50%;background:#151515;color:#fff;border:1px solid #303030;font-size:21px}
.tabs,.scopes{display:flex;background:#090909;border-bottom:1px solid var(--line);padding:0 10px}.tabs button,.scopes button{flex:1;background:none;border:0;color:#777;padding:12px 7px;font-weight:800;font-size:12px}.tabs .active,.scopes .active{color:#fff;border-bottom:2px solid #fff}
.scopes{padding:10px 12px;border:0;gap:7px}.scopes button{border:1px solid #292929;border-radius:10px}.scopes .active{background:#eee;color:#111;border-color:#eee}
.section{padding:18px 16px 9px}.eyebrow{font-size:10px;letter-spacing:.13em;color:#777;font-weight:800}.section h1{font:28px Georgia,serif;margin:5px 0 0}
.story,.headline{display:block;width:100%;text-align:left;background:none;color:inherit;border:0;border-top:1px solid #202020;padding:14px 16px;text-decoration:none}.storytitle,.htitle{font:18px/1.25 Georgia,serif}.meta{font-size:10px;color:#777;margin-top:5px}.num{font-size:10px;color:#555;margin-right:7px}
.controls{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:10px 12px}.controls input,.controls select{background:#141414;color:#eee;border:1px solid #292929;border-radius:9px;padding:10px}.controls input{grid-column:1/-1}
.status{position:fixed;bottom:calc(8px + env(safe-area-inset-bottom));left:50%;transform:translateX(-50%);background:#1b1b1bef;border:1px solid #333;border-radius:99px;padding:6px 10px;color:#aaa;font-size:10px;z-index:20;white-space:nowrap}.hidden{display:none!important}.rtl{direction:rtl;text-align:right}.empty{margin:20px 16px;padding:16px;border:1px dashed #2c2c2c;border-radius:12px;color:#777}
</style></head><body>
<header><div><div class="brand">WORLD DESK</div><div class="sub">GLOBAL NEWSPAPER INTELLIGENCE · v0.4</div></div><button class="refresh" id="refresh">↻</button></header>
<div class="tabs"><button class="active" data-view="pulse">Pulse</button><button data-view="headlines">Headlines</button><button data-view="sources">Sources</button></div>
<section id="pulse"><div class="section"><div class="eyebrow">GLOBAL PULSE</div><h1>What the press is leading with</h1></div><div class="scopes"><button class="active" data-scope="world">🌍 WORLD</button><button data-scope="arab">العالم العربي</button></div><div id="stories"><div class="empty">Tap ↻ to load live headlines.</div></div></section>
<section id="headlines" class="hidden"><div class="controls"><select id="country"><option value="">All countries</option></select><select id="pub"><option value="">All publications</option></select><input id="q" placeholder="Search headlines"></div><div id="wall"></div></section>
<section id="sources" class="hidden"><div class="section"><div class="eyebrow">SOURCE HEALTH</div><h1>Live sources</h1></div><div id="sourceList"></div></section>
<div id="status" class="status">Ready</div>
<script>
let DATA={headlines:[],world:[],arab:[],sources:[]}, scope="world";
const $=s=>document.querySelector(s), $$=s=>document.querySelectorAll(s);
const esc=s=>{let d=document.createElement("div");d.textContent=s||"";return d.innerHTML};
function renderStories(){let a=DATA[scope]||[];$("#stories").innerHTML=a.length?a.map((x,i)=>`<div class="story ${/[\\u0600-\\u06FF]/.test(x.label)?"rtl":""}"><div class="storytitle"><span class="num">${String(i+1).padStart(2,"0")}</span>${esc(x.label)}</div><div class="meta">${x.publication_count} publications · ${x.country_count} countries · ${x.headline_count} headlines</div></div>`).join(""):`<div class="empty">No multi-source story clusters yet. Refresh again as coverage changes.</div>`}
function renderWall(){let c=$("#country").value,p=$("#pub").value,q=$("#q").value.toLowerCase();let a=DATA.headlines.filter(x=>(!c||x.country_code===c)&&(!p||x.publication===p)&&(!q||x.title.toLowerCase().includes(q)));$("#wall").innerHTML=a.map(x=>`<a class="headline ${x.lang==="ar"?"rtl":""}" href="${esc(x.url)}" target="_blank"><div class="meta">${esc(x.country_code)} · ${esc(x.publication)}</div><div class="htitle">${esc(x.title)}</div></a>`).join("")}
function renderSources(){let a=DATA.sources||[];$("#sourceList").innerHTML=a.map(x=>`<div class="headline"><div class="htitle">${x.ok?"●":"○"} ${esc(x.source)}</div><div class="meta">${x.ok?x.items.length+" headlines":esc(x.error||"failed")}</div></div>`).join("")}
function filters(){let cs=[...new Set(DATA.headlines.map(x=>x.country_code))].sort();$("#country").innerHTML='<option value="">All countries</option>'+cs.map(c=>`<option>${c}</option>`).join("");let ps=[...new Set(DATA.headlines.map(x=>x.publication))].sort();$("#pub").innerHTML='<option value="">All publications</option>'+ps.map(p=>`<option>${esc(p)}</option>`).join("")}
async function refresh(){ $("#status").textContent="Loading live sources…"; try{let r=await fetch("/api/refresh");DATA=await r.json();localStorage.setItem("wd04",JSON.stringify(DATA));filters();renderStories();renderWall();renderSources();let ok=DATA.sources.filter(x=>x.ok).length;$("#status").textContent=`${DATA.headlines.length} headlines · ${ok}/${DATA.sources.length} sources`; }catch(e){$("#status").textContent="Refresh failed";}}
$("#refresh").onclick=refresh; $$(".tabs button").forEach(b=>b.onclick=()=>{$$(".tabs button").forEach(x=>x.classList.remove("active"));b.classList.add("active");["pulse","headlines","sources"].forEach(v=>$("#"+v).classList.toggle("hidden",v!==b.dataset.view));}); $$(".scopes button").forEach(b=>b.onclick=()=>{$$(".scopes button").forEach(x=>x.classList.remove("active"));b.classList.add("active");scope=b.dataset.scope;renderStories()}); $("#country").onchange=renderWall;$("#pub").onchange=renderWall;$("#q").oninput=renderWall;
try{let saved=localStorage.getItem("wd04");if(saved){DATA=JSON.parse(saved);filters();renderStories();renderWall();renderSources();$("#status").textContent="Cached headlines loaded";}}catch(e){}
</script></body></html>"""

@app.get("/",response_class=HTMLResponse)
def home(): return HTML

@app.get("/manifest.json")
def manifest():
    return JSONResponse({"name":"WORLD DESK","short_name":"World Desk","start_url":"/","display":"standalone","background_color":"#090909","theme_color":"#090909"})
