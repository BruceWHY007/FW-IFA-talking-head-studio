#!/usr/bin/env python3
"""④-b 免费商用量素材库找 B-roll：三个源，按缩略图挑，不按标题猜。

    python3 stock.py <工程> sources                                  # 看有哪些源、许可、能不能用
    python3 stock.py <工程> search "英文画面词" ["词2" ...] [--source all|pexels|coverr|mixkit] [--landscape]
    python3 stock.py <工程> get <源>:<id> <存成的名字> [<源>:<id> <名字> ...]
    python3 stock.py <工程> get <pexels 纯数字 id> <名字>              # 老写法，默认当 Pexels

三个免 key 的源 + 一个 API 源（Pixabay，需要环境变量 PIXABAY_API_KEY），都是**免费可商用、无需署名**：
  pexels  搜索页走 firecrawl（直连会被拦），能拿到 1080–2160p；港景、亚洲面孔偏多，是最好的主力源
  coverr  CDN 直连，能拿到 1080p；片库小（几千条），欧美生活场景多
  mixkit  CDN 直连，最高 720p（1080 要登录）；片库偏「干净的办公／城市／自然空镜」
  pixabay 官方 API（免费 key，放环境变量 PIXABAY_API_KEY），能到 1080p／4K；片库最大，欧美场景多，竖版要自己筛
关键词用英文、写画面不写动作，一次 2–3 个词组：
  ✗ "success"  ✗ "signing document close up"（一屏全是手）  ✓ "hong kong street tram"  ✓ "modern office window city view"
挑片规则见 references/03：相邻两条 B-roll 不能同一类画面（人／手／建筑／文件／物件／空镜）。
"""
import glob, json, os, re, subprocess, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, die, has, font

if len(sys.argv) < 3:
    die(__doc__)
proj, cmd, args = os.path.abspath(sys.argv[1]), sys.argv[2], sys.argv[3:]
D = P(proj, "broll", "stock")
os.makedirs(os.path.join(D, "_thumbs"), exist_ok=True)
os.makedirs(os.path.join(D, "_html"), exist_ok=True)
landscape = "--landscape" in args
args = [x for x in args if x != "--landscape"]
SRC = "all"
if "--source" in args:
    i = args.index("--source")
    SRC = args[i + 1]
    del args[i:i + 2]

LIC = {
    "pexels": "Pexels License（免费可商用，无需署名；不得暗示画面里的人为本品牌背书）",
    "coverr": "Coverr License（免费可商用，无需署名；不得把素材本身当素材再分发）",
    "mixkit": "Mixkit Free License（免费可商用，无需署名；不得把素材本身当素材再分发，不得用于转售模板）",
    "pixabay": "Pixabay Content License（免费可商用，无需署名；不得把素材本身当素材再分发）",
    "ia": "Internet Archive 条目自带 CC／公有领域许可（详见 page 里的 license，署名要求按该许可走）",
    "wiki": "Wikimedia Commons：CC／公有领域，按条目注明署名（credit 会写进时间线）",
}
PAGE = {
    "pexels": "https://www.pexels.com/video/%s-%s/",
    "coverr": "https://coverr.co/videos/%s",
    "mixkit": "https://mixkit.co/free-stock-video/%s/",
    "pixabay": "%s",
    "ia": "%s",
    "wiki": "%s",
}


def scrape(url, out, minbytes=30000):
    if not os.path.exists(out) or os.path.getsize(out) < minbytes:
        if not has("firecrawl"):
            die("没有 firecrawl CLI，免费素材这一路走不了；改用用户素材或生成")
        subprocess.run(["perl", "-e", "alarm 150; exec @ARGV", "firecrawl", "scrape", url, "-f", "rawHtml", "-o", out],
                       capture_output=True)
    return open(out, errors="ignore").read() if os.path.exists(out) else ""


def slug(q):
    return re.sub(r"\W+", "_", q).strip("_")


def curl(url, out, t=60):
    subprocess.run(["curl", "-sL", "--max-time", str(t), "-o", out, url])


def portrait_ok(path):
    """缩略图能看出画幅：竖的才留（--landscape 时反过来）"""
    try:
        from PIL import Image
        im = Image.open(path)
        is_p = im.height >= im.width
        return is_p != landscape
    except Exception:
        return True


# ---------------- Pexels（走 firecrawl 抓搜索页） ----------------
def search_pexels(q):
    orient = "landscape" if landscape else "portrait"
    url = "https://www.pexels.com/search/videos/%s/?orientation=%s" % (urllib.parse.quote(q), orient)
    h = scrape(url, os.path.join(D, "_html", "s_%s_%s.html" % (slug(q), orient)))
    seen = {}
    for vid, name in re.findall(r'images\.pexels\.com/videos/(\d+)/([^"?\s/]+?)\.jpe?g', h):
        seen.setdefault(vid, name)
    slugs = {v: s for s, v in re.findall(r'/video/([a-z0-9-]+)-(\d+)/', h)}
    items = [dict(src="pexels", id=v, name=n, slug=slugs.get(v, ""),
                  thumb="https://images.pexels.com/videos/%s/%s.jpeg?auto=compress&w=360" % (v, n)) for v, n in seen.items()][:24]
    return items


def get_pexels(vid, name, it):
    page = PAGE["pexels"] % (it.get("slug") or "x", vid) if it.get("slug") else "https://www.pexels.com/video/%s/" % vid
    pat = r'video-files/%s/([0-9a-z-]+?)_(\d+)_(\d+)_(\d+)fps\.mp4' % vid
    h = "".join(open(f, errors="ignore").read() for f in glob.glob(os.path.join(D, "_html", "s_*.html")))
    files = re.findall(pat, h)
    if not files or max(max(int(f[1]), int(f[2])) for f in files) < 1920:
        h2 = scrape(page, os.path.join(D, "_html", "v_%s.html" % vid))
        files = files + re.findall(pat, h2)
    if not files:
        print("✗ 取不到直链", vid, page)
        return None
    fid, w, hh, fps = max(files, key=lambda f: (max(int(f[1]), int(f[2])) <= 2160, max(int(f[1]), int(f[2]))))
    src = "https://videos.pexels.com/video-files/%s/%s_%s_%s_%sfps.mp4" % (vid, fid, w, hh, fps)
    return src, page, (int(w), int(hh)), fps + "fps"


# ---------------- Coverr（CDN 直连，1080p 免费） ----------------
def search_coverr(q):
    url = "https://coverr.co/s?q=%s" % urllib.parse.quote(q)
    h = scrape(url, os.path.join(D, "_html", "c_%s.html" % slug(q)), 200000)
    slugs = []
    for s in re.findall(r'cdn\.coverr\.co/videos/([a-z0-9-]{6,})/', h):
        if s.startswith(("coverr-premium", "user-ai-")) or s in slugs:
            continue
        slugs.append(s)
    items = [dict(src="coverr", id=s, name=s.replace("coverr-", ""), slug=s,
                  thumb="https://cdn.coverr.co/videos/%s/thumbnail?width=385" % s) for s in slugs][:24]
    return items


def get_coverr(sl, name, it):
    # 注意：HEAD 对不存在的 2160p 也回 200，必须用 range GET 探一次真状态（10-27 实测）
    for q in ("1080p", "720p", "360p"):
        src = "https://cdn.coverr.co/videos/%s/%s.mp4" % (sl, q)
        st = subprocess.run(["curl", "-s", "-r", "0-2048", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "20", src],
                            capture_output=True, text=True).stdout.strip()
        if st == "206":
            return src, PAGE["coverr"] % sl, None, q
    print("✗ Coverr 没有可用直链", sl)
    return None


# ---------------- Mixkit（CDN 直连，最高 720p） ----------------
def search_mixkit(q):
    url = "https://mixkit.co/free-stock-video/%s/" % re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
    h = scrape(url, os.path.join(D, "_html", "m_%s.html" % slug(q)), 60000)
    ids = []
    for i in re.findall(r'assets\.mixkit\.co/videos/(\d+)/\1-thumb', h):
        if i not in ids:
            ids.append(i)
    items = [dict(src="mixkit", id=i, name=i, slug=i,
                  thumb="https://assets.mixkit.co/videos/%s/%s-thumb-720-0.jpg" % (i, i)) for i in ids][:24]
    return items


def get_mixkit(i, name, it):
    for q in ("720", "360"):
        src = "https://assets.mixkit.co/videos/%s/%s-%s.mp4" % (i, i, q)
        head = subprocess.run(["curl", "-sIL", "--max-time", "20", src], capture_output=True, text=True).stdout
        if " 200" in head:
            return src, PAGE["mixkit"] % i, None, q + "p"
    print("✗ Mixkit 没有可用直链", i)
    return None


# ---------------- Internet Archive（公有领域／CC，无 key） ----------------
def search_ia(q):
    import urllib.request
    u = ("https://archive.org/advancedsearch.php?q=%s&fl%%5B%%5D=identifier&fl%%5B%%5D=title&fl%%5B%%5D=licenseurl"
         "&rows=40&page=1&output=json&sort%%5B%%5D=downloads+desc" % urllib.parse.quote('(%s) AND mediatype:movies' % q))
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore"))
    except Exception as e:
        print("· archive.org 请求失败：", str(e)[:80])
        return []
    items = []
    for d in (data.get("response") or {}).get("docs", []):
        lic = (d.get("licenseurl") or "").lower()
        if "creativecommons.org" not in lic and "publicdomain" not in lic:
            continue  # 没标许可的一律不进候选
        items.append(dict(src="ia", id=d["identifier"], name=str(d.get("title", ""))[:40], slug=d["identifier"],
                          thumb="https://archive.org/services/img/%s" % d["identifier"],
                          page="https://archive.org/details/%s" % d["identifier"], lic_url=d.get("licenseurl", "")))
    return items


def get_ia(ident, name, it):
    import urllib.request
    try:
        req = urllib.request.Request("https://archive.org/metadata/%s" % ident, headers={"User-Agent": "Mozilla/5.0"})
        meta = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore"))
    except Exception as e:
        print("✗ archive.org 取元数据失败", ident, str(e)[:60])
        return None
    files = [f for f in meta.get("files", []) if str(f.get("name", "")).lower().endswith(".mp4")]
    if not files:
        print("✗ 这个条目里没有 mp4", ident)
        return None
    f = min(files, key=lambda x: abs(int(x.get("size") or 0) - 30 * 1024 * 1024))  # 挑一个 30MB 上下的，别下几百兆
    return ("https://archive.org/download/%s/%s" % (ident, urllib.parse.quote(f["name"])),
            it.get("page") or ("https://archive.org/details/%s" % ident), None, "archive")


# ---------------- Pixabay（官方 API，key 只从环境变量读） ----------------
PIXABAY_KEY = os.environ.get("PIXABAY_API_KEY", "")


def search_pixabay(q):
    if not PIXABAY_KEY:
        print("· pixabay 跳过：没设 PIXABAY_API_KEY")
        return []
    import urllib.request
    u = "https://pixabay.com/api/videos/?key=%s&q=%s&per_page=30&safesearch=true&video_type=film" % (
        urllib.parse.quote(PIXABAY_KEY), urllib.parse.quote(q))
    try:
        # urllib 默认的 Python-urllib UA 会被 Pixabay 判 403，必须换成普通浏览器 UA（10-27 实测）
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                                              "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                                                  "Accept": "application/json"})
        raw = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        data = json.loads(raw)
    except Exception as e:
        print("· pixabay 请求失败：", str(e)[:80])
        return []
    items = []
    for h in data.get("hits", []):
        v = h.get("videos") or {}
        # 选「不大于 1920 宽里最大的那一档」：large 常常是 4K，下下来一百多兆，剪片用不上（10-27 实测）
        cand = [x for x in (v.get("large"), v.get("medium"), v.get("small"), v.get("tiny")) if x and x.get("url")]
        if not cand:
            continue
        fit = [x for x in cand if (x.get("width") or 0) <= 1920]
        big = max(fit, key=lambda x: x.get("width") or 0) if fit else min(cand, key=lambda x: x.get("width") or 99999)
        items.append(dict(src="pixabay", id=str(h["id"]), name=str(h.get("tags", ""))[:40], slug=str(h["id"]),
                          thumb=big.get("thumbnail") or v.get("medium", {}).get("thumbnail", ""),
                          page=h.get("pageURL", ""), mp4=big["url"], w=big.get("width"), h_=big.get("height")))
    return items


def get_pixabay(i, name, it):
    src = it.get("mp4")
    if not src:
        print("✗ Pixabay 这条没有直链，重新搜一次再 get", i)
        return None
    return src, it.get("page") or PAGE["pixabay"] % i, (it.get("w"), it.get("h_")), "api"


def search_images(q, n=24):
    """免费商用图片（Pixabay 图片 API，同一把 key）。给「图片 B-roll」用：推近／横移，比视频更容易对题。"""
    if not PIXABAY_KEY:
        die("没设 PIXABAY_API_KEY。图片源现在走 Pixabay 图片 API")
    import urllib.request
    u = ("https://pixabay.com/api/?key=%s&q=%s&image_type=photo&per_page=%d&safesearch=true&orientation=%s"
         % (urllib.parse.quote(PIXABAY_KEY), urllib.parse.quote(q), n, "vertical" if not landscape else "horizontal"))
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore"))
    hits = data.get("hits", [])
    D2 = P(proj, "broll", "img")
    os.makedirs(D2, exist_ok=True)
    out = []
    for i, h in enumerate(hits):
        name = "img_%s_%s" % (slug(q)[:18], h["id"])
        fp = os.path.join(D2, name + ".jpg")
        if not os.path.exists(fp):
            curl(h.get("largeImageURL") or h["webformatURL"], fp, 60)
        if os.path.exists(fp) and os.path.getsize(fp) > 20000:
            out.append((name, fp, h.get("pageURL", ""), h.get("tags", "")[:40]))
    return out


def search_wiki(q, n=24):
    """Wikimedia Commons 图片（CC／公有领域，高清）。政策、机构、地标、文件这类「图库没有的东西」多半能在这里找到。"""
    import urllib.request
    u = ("https://commons.wikimedia.org/w/api.php?action=query&generator=search&gsrsearch=%s&gsrnamespace=6&gsrlimit=%d"
         "&prop=imageinfo&iiprop=%s&iiurlwidth=1600&format=json"
         % (urllib.parse.quote(q), n, urllib.parse.quote("url|size|extmetadata")))
    # Wikimedia 要求带说明的 UA，通用浏览器 UA 会被限流的空响应（10-27 实测）
    req = urllib.request.Request(u, headers={"User-Agent": "IFA-koubo-skill/1.0 (stock image lookup; local use)"})
    data = {}
    for _try in range(3):
        try:
            data = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore"))
            if data.get("query"):
                break
        except Exception:
            pass
        time.sleep(1.5)
    out = []
    for k, v in (data.get("query") or {}).get("pages", {}).items():
        ii = (v.get("imageinfo") or [{}])[0]
        w, h = ii.get("width") or 0, ii.get("height") or 0
        if not ii.get("thumburl") or min(w, h) < 900:
            continue
        _t = (ii.get("thumburl") or "").split("?")[0].split("#")[0]   # 现在会带 ?utm_content=… 查询串
        ext = _t.rsplit(".", 1)[-1][:4]
        if ext.lower() not in ("jpg", "jpeg", "png", "webp"):
            continue
        m = ii.get("extmetadata") or {}
        lic = (m.get("LicenseShortName", {}) or {}).get("value", "见来源页")
        artist = re.sub(r"<[^>]+>", "", (m.get("Artist", {}) or {}).get("value", "") or "")[:40]
        out.append(dict(src="wiki", id=str(k), name=str(v.get("title", ""))[5:][:60], slug=str(k),
                        thumb=ii.get("thumburl"), page=ii.get("descriptionurl", ""),
                        image=ii.get("thumburl"), w=w, h=h, licence="Wikimedia：%s（署名：%s）" % (lic, artist or "见来源页"),
                        credit="%s / Wikimedia（%s）" % (artist or "Wikimedia", lic)))
    return out


def get_wiki(i, name, it):
    return it.get("image"), it.get("page") or ("https://commons.wikimedia.org/?curid=%s" % i), (it.get("w"), it.get("h")), "wiki"


SEARCH = {"pexels": search_pexels, "coverr": search_coverr, "mixkit": search_mixkit, "pixabay": search_pixabay,
          "ia": search_ia, "wiki": search_wiki}
GET = {"pexels": get_pexels, "coverr": get_coverr, "mixkit": get_mixkit, "pixabay": get_pixabay, "ia": get_ia, "wiki": get_wiki}


def pick_sources(one=None):
    s = one or SRC
    return list(SEARCH) if s == "all" else [s]


def do_search(q, srcs):
    items = []
    for s in srcs:
        try:
            got = SEARCH[s](q)
            print("·", s, len(got), "条")
            items += got
        except Exception as e:
            print("·", s, "搜索失败：", str(e)[:80])
    if not items:
        return q, []
    # 缩略图 + 画幅过滤
    def th(it):
        p = os.path.join(D, "_thumbs", "%s_%s.jpg" % (it["src"], it["id"]))
        if not os.path.exists(p):
            curl(it["thumb"], p, 30)
        if not os.path.exists(p) or os.path.getsize(p) < 2000:
            return None
        if it["src"] == "wiki":
            return p
        return p if portrait_ok(p) else None
    with ThreadPoolExecutor(8) as ex:
        paths = list(ex.map(th, items))
    from PIL import Image, ImageDraw
    ok = [(it, p) for it, p in zip(items, paths) if p][:32]
    if not ok:
        return q, []
    cw, ch = 200, (200 if landscape else 356)
    sheet = Image.new("RGB", (cw * 8, ch * ((len(ok) + 7) // 8)), "black")
    f = font(20)
    for i, (it, p) in enumerate(ok):
        try:
            im = Image.open(p).convert("RGB")
        except Exception:
            continue
        im.thumbnail((cw, ch))
        x, y = (i % 8) * cw, (i // 8) * ch
        sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
        d = ImageDraw.Draw(sheet)
        tag = "%s:%s" % (it["src"][:2], it["id"] if it["src"] in ("pexels", "pixabay") else it["id"][-10:])
        d.rectangle([x, y, x + 150, y + 26], fill="black")
        d.text((x + 4, y + 3), tag, fill="yellow", font=f)
    sheet.save(os.path.join(D, "_thumbs", "sheet_%s.jpg" % slug(q)), quality=82)
    idx_p = os.path.join(D, "_thumbs", "index.json")
    idx = json.load(open(idx_p)) if os.path.exists(idx_p) else {}
    for it, _p in ok:
        idx["%s:%s" % (it["src"], it["id"])] = it
        idx.setdefault(it["id"], it)
        if it["src"] not in ("pexels", "pixabay"):   # coverr 的 slug 很长：用尾部 10 位当短名
            idx.setdefault("%s:%s" % (it["src"], it["id"][-10:]), it)
    json.dump(idx, open(idx_p, "w"), indent=1, ensure_ascii=False)
    return q, ok


ALIAS = {"pe": "pexels", "co": "coverr", "mi": "mixkit", "px": "pixabay", "ia": "ia", "wk": "wiki"}
def do_get(key, name):
    if ":" in key:
        head, vid = key.split(":", 1)
        s = ALIAS.get(head, head)
        if s not in GET:
            print("✗ 不认识的源：", head)
            return
    else:
        s, vid = "pexels", key
    idx_p = os.path.join(D, "_thumbs", "index.json")
    idx = json.load(open(idx_p)) if os.path.exists(idx_p) else {}
    it = idx.get("%s:%s" % (s, vid)) or idx.get(vid) or {"src": s, "id": vid, "slug": ""}
    vid = it.get("id") or vid
    res = GET[s](vid, name, it)
    if not res:
        return
    src, page, wh, note = res
    if s == "wiki":
        D2 = P(proj, "broll", "img"); os.makedirs(D2, exist_ok=True)
        out = os.path.join(D2, name + ".jpg")
        if not os.path.exists(out) or os.path.getsize(out) < 20000:
            curl(src, out, 120)
        reg_p = os.path.join(D2, "img_picks.json")
        reg = json.load(open(reg_p)) if os.path.exists(reg_p) else {}
        reg[name] = dict(source="wiki", page=page, file=name + ".jpg", licence=it.get("licence") or LIC["wiki"],
                         credit=it.get("credit", ""))
        json.dump(reg, open(reg_p, "w"), indent=1, ensure_ascii=False)
        print("✓ %s（图片）%s" % (name, it.get("licence", "")[:40]))
        return
    out = os.path.join(D, name + ".mp4")
    if not os.path.exists(out) or os.path.getsize(out) < 50000:
        curl(src, out, 300)
    # 下载后再量一次真实画幅与帧率（搜索页写的分辨率常常不是真的，07 #32）
    info = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,r_frame_rate",
                           "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip()
    parts = info.split(",")
    w, h = (int(parts[0]), int(parts[1])) if len(parts) >= 2 and parts[0].isdigit() else (0, 0)
    fps = parts[2] if len(parts) >= 3 else note
    picks_p = os.path.join(D, "stock_picks.json")
    picks = json.load(open(picks_p)) if os.path.exists(picks_p) else {}
    picks[name] = dict(source=s, id=vid, url=src, w=w, h=h, fps=fps, page=page, licence=LIC[s])
    json.dump(picks, open(picks_p, "w"), indent=1, ensure_ascii=False)
    kb = os.path.getsize(out) // 1024 if os.path.exists(out) else 0
    print("✓ %s %s:%s %sx%s %s %dKB" % (name, s, vid, w, h, fps, kb))


if cmd == "sources":
    print("免费商用素材源（都无需署名）：")
    for k in ("pexels", "coverr", "mixkit", "pixabay", "ia", "wiki"):
        if k == "pexels":
            st = "可用" if has("firecrawl") else "需要 firecrawl"
        elif k == "pixabay":
            st = "可用（API）" if PIXABAY_KEY else "没设 PIXABAY_API_KEY"
        elif k == "ia":
            st = "可用（只收标了 CC／公有领域的条目）"
        elif k == "wiki":
            st = "可用（CC／公有领域，高清；下载的是图片，用作图片 B-roll）"
        else:
            st = "可用"
        print("  %-7s %-58s %s" % (k, LIC[k][:56], st))
    print("\n调用：stock.py <工程> search \"hong kong street tram\" --source all")
    print("      stock.py <工程> get coverr:coverr-xxx st_name / get 8297900 st_name（Pexels 老写法）")
elif cmd == "images":
    if not args:
        die("用法：stock.py <工程> images \"英文画面词\" [--landscape]")
    D2 = P(proj, "broll", "img")
    os.makedirs(D2, exist_ok=True)
    lic_p = P(proj, "broll", "img", "img_picks.json")
    reg = json.load(open(lic_p)) if os.path.exists(lic_p) else {}
    for q in args:
        got = search_images(q)
        for name, fp, page, tags in got:
            reg[name] = dict(source="pixabay", page=page, tags=tags, file=os.path.basename(fp),
                             licence=LIC["pixabay"])
        print("== %s %d 张 → %s" % (q, len(got), D2))
    json.dump(reg, open(lic_p, "w"), indent=1, ensure_ascii=False)
elif cmd == "search":
    with ThreadPoolExecutor(3) as ex:
        for q, r in ex.map(lambda q: do_search(q, pick_sources()), args):
            print("==", q, len(r), "条 →", os.path.join(D, "_thumbs", "sheet_%s.jpg" % slug(q)))
elif cmd == "get":
    for i in range(0, len(args), 2):
        do_get(args[i], args[i + 1])
else:
    die(__doc__)
