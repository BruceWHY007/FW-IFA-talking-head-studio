#!/usr/bin/env python3
"""④-b 免费商用量素材库找 B-roll：三个源，按缩略图挑，不按标题猜。

    python3 stock.py <工程> sources                                  # 看有哪些源、许可、能不能用
    python3 stock.py <工程> search "英文画面词" ["词2" ...] [--source all|pexels|coverr|mixkit] [--landscape]
    python3 stock.py <工程> get <源>:<id> <存成的名字> [<源>:<id> <名字> ...]
    python3 stock.py <工程> get <pexels 纯数字 id> <名字>              # 老写法，默认当 Pexels
    python3 stock.py <工程> plan [--decompose decompose_F.json]        # 按镜头批量检索：每个缺素材的 B 镜头一张候选图（带自动体检角标）
    python3 stock.py <工程> auto --decompose decompose_lite.json       # 极简档：每个缺素材的 B 镜头自动取第一条「干净」候选，写回 pick，并出审片表
    python3 stock.py <工程> review --decompose decompose_lite.json     # 只重出审片表 auto_review.jpg（前画面｜素材三帧｜后画面＋自动量的亮度／色调差）
    python3 stock.py <工程> redo --decompose decompose_lite.json       # 重取审片里判 replace 的镜头（排除被否过的），drop 的删掉，再出审片表
    python3 stock.py <工程> lexicon "原话"                             # 看这句话按概念词表会搜哪些画面词
    python3 stock.py <工程> search "画面词" --source ov                 # Openverse 图片（CC 可商用且可改编，免 key）

Pexels 有两条路：设了 PEXELS_API_KEY 就走官方 API（竖版在服务端筛、每条给 4 张预览帧、文件规格是真值）；没设就退回 firecrawl 抓搜索页。
自动体检角标（plan／search 的候选图上）：字＝缩略图里有可读文字　脸＝有大张陌生人正脸　暗＝平均亮度 <55　静＝几张预览帧几乎不动（只 API 有）。

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
from kb import P, die, has, font, sid_span, cover_text, as_list

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
    "ov": "Openverse（CC 聚合：只收可商用且允许改编的 by／by-sa／cc0／pdm，按条目署名）",
}
PAGE = {
    "pexels": "https://www.pexels.com/video/%s-%s/",
    "coverr": "https://coverr.co/videos/%s",
    "mixkit": "https://mixkit.co/free-stock-video/%s/",
    "pixabay": "%s",
    "ia": "%s",
    "wiki": "%s",
    "ov": "%s",
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
PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "")


def _json_get(url, headers=None, t=30):
    import urllib.request
    req = urllib.request.Request(url, headers=dict({"User-Agent": "Mozilla/5.0 (Macintosh) ifa-koubo/1.0", "Accept": "application/json"}, **(headers or {})))
    return json.loads(urllib.request.urlopen(req, timeout=t).read().decode("utf-8", "ignore"))


def search_pexels_api(q):
    """官方 API：orientation 在服务端筛；video_pictures 给每条 ~15 张预览帧（取 4 张做体检）；video_files 是真分辨率与帧率"""
    orient = "landscape" if landscape else "portrait"
    u = "https://api.pexels.com/videos/search?query=%s&orientation=%s&per_page=40&size=medium" % (urllib.parse.quote(q), orient)
    data = _json_get(u, {"Authorization": PEXELS_KEY})
    items = []
    for v in data.get("videos", []):
        pics = [x["picture"] for x in (v.get("video_pictures") or [])]
        pics = [pics[i] for i in sorted(set([0, len(pics) // 3, 2 * len(pics) // 3, len(pics) - 1])) if pics] if pics else []
        files = [dict(w=f.get("width") or 0, h=f.get("height") or 0, fps=f.get("fps"), link=f.get("link")) for f in v.get("video_files", []) if f.get("link")]
        slug_ = (v.get("url") or "").rstrip("/").split("/")[-1]
        items.append(dict(src="pexels", id=str(v["id"]), name=slug_[:40], slug=slug_.rsplit("-", 1)[0] if slug_ else "",
                          thumb=v.get("image") or (pics[0] if pics else ""), pics=pics, files=files, dur=v.get("duration"),
                          page=v.get("url", ""), author=(v.get("user") or {}).get("name", "")))
    return items


def search_pexels(q):
    if PEXELS_KEY:
        try:
            return search_pexels_api(q)
        except Exception as e:
            print("· pexels API 失败，退回抓页：", str(e)[:80])
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
    if it.get("files"):
        # API 给的文件表是真规格：挑长边 ≤2160 里最大的一档（4K 下下来几百兆，剪片用不上）
        fs = [f for f in it["files"] if max(f["w"], f["h"]) <= 2160] or it["files"]
        best = max(fs, key=lambda f: max(f["w"], f["h"]))
        return best["link"], it.get("page") or "https://www.pexels.com/video/%s/" % vid, (best["w"], best["h"]), "%sfps" % round(best["fps"] or 0)
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
                          page=h.get("pageURL", ""), mp4=big["url"], w=big.get("width"), h_=big.get("height"),
                          credit="%s / Pixabay" % (h.get("user") or "佚名")))
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
    reg_p = os.path.join(D2, "img_picks.json")
    reg = json.load(open(reg_p)) if os.path.exists(reg_p) else {}
    for i, h in enumerate(hits):
        name = "img_%s_%s" % (slug(q)[:18], h["id"])
        fp = os.path.join(D2, name + ".jpg")
        if not os.path.exists(fp):
            curl(h.get("largeImageURL") or h["webformatURL"], fp, 60)
        if os.path.exists(fp) and os.path.getsize(fp) > 20000:
            out.append((name, fp, h.get("pageURL", ""), h.get("tags", "")[:40]))
            reg[name] = dict(source="pixabay", page=h.get("pageURL", ""), file=name + ".jpg", licence=LIC["pixabay"],
                             credit="%s / Pixabay" % (h.get("user") or "佚名"))
    json.dump(reg, open(reg_p, "w"), indent=1, ensure_ascii=False)
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


def search_openverse(q, n=30):
    """Openverse（WordPress 维护的 CC 聚合，免 key）：只要「可商用＋允许改编」——我们会裁切调色，ND（禁止演绎）不能用"""
    asp = "wide" if landscape else "tall"
    u = ("https://api.openverse.org/v1/images/?q=%s&license_type=commercial,modification&page_size=%d&size=large&aspect_ratio=%s&mature=false"
         % (urllib.parse.quote(q), n, asp))
    try:
        data = _json_get(u, {"User-Agent": "ifa-koubo-skill/1.0 (stock image lookup)"})
    except Exception as e:
        print("· openverse 请求失败：", str(e)[:80])
        return []
    out = []
    for r in data.get("results", []):
        lic = (r.get("license") or "").lower()
        if lic not in ("by", "by-sa", "cc0", "pdm"):
            continue
        w, h = r.get("width") or 0, r.get("height") or 0
        if w and h and min(w, h) < 1000:
            continue
        credit = "%s / %s（CC %s %s）" % (r.get("creator") or "佚名", r.get("source") or "openverse", lic.upper(), r.get("license_version") or "")
        out.append(dict(src="ov", id=str(r["id"])[:8], full_id=r["id"], name=str(r.get("title", ""))[:50], slug=r["id"],
                        thumb=r.get("thumbnail") or r.get("url"), image=r.get("url"), page=r.get("foreign_landing_url", ""), w=w, h=h,
                        licence="CC %s %s · %s" % (lic.upper(), r.get("license_version") or "", r.get("license_url") or ""), credit=credit))
    return out


def get_openverse(i, name, it):
    return it.get("image"), it.get("page", ""), (it.get("w"), it.get("h")), "openverse"


SEARCH = {"pexels": search_pexels, "coverr": search_coverr, "mixkit": search_mixkit, "pixabay": search_pixabay,
          "ia": search_ia, "wiki": search_wiki, "ov": search_openverse}
GET = {"pexels": get_pexels, "coverr": get_coverr, "mixkit": get_mixkit, "pixabay": get_pixabay, "ia": get_ia, "wiki": get_wiki, "ov": get_openverse}


def pick_sources(one=None):
    s = one or SRC
    # all＝视频源（Pexels／Coverr／Mixkit／Pixabay）；图片源（wiki／ov）和 Archive 要点名才搜——混在一张候选图里分不清哪条是图
    return ["pexels", "coverr", "mixkit", "pixabay"] if s == "all" else s.split(",")


# ---------------- 自动体检：候选缩略图上打角标（字／脸／暗／静），挑片时一眼排除 ----------------
def _vision_bin(name):
    b = os.path.expanduser("~/.cache/ifa-koubo/%s" % name)
    if not os.path.exists(b) and has("swiftc"):
        os.makedirs(os.path.dirname(b), exist_ok=True)
        subprocess.run(["swiftc", "-O", os.path.join(os.path.dirname(os.path.abspath(__file__)), name + ".swift"), "-o", b], capture_output=True)
    return b if os.path.exists(b) else None


def vet(pairs):
    """pairs: [(item, 缩略图路径)] → {路径: [角标…]}。文字用 Vision OCR（≥4 字、置信 ≥0.5），人脸宽 ≥18% 画幅算「大张正脸」"""
    import shutil, tempfile
    from PIL import Image, ImageChops, ImageStat
    flags = {p: [] for _, p in pairs}
    tmp = tempfile.mkdtemp(prefix="vet_")
    extra = {}
    for k, (it, p) in enumerate(pairs):
        # 体检用 720 宽的预览（360 宽缩略图上 OCR 几乎看不到字：MAERSK 置信度只有 0.3——10-29 实测）
        big = p[:-4] + "_v720.jpg"
        u = it.get("thumb", "")
        if not os.path.exists(big) and it["src"] in ("pexels", "pixabay", "coverr", "ov", "wiki") and u:
            u2 = re.sub(r"([?&])w=\d+", r"\1w=720", u) if "w=" in u else u.replace("width=385", "width=720")
            curl(u2, big, 25)
        src_img = big if os.path.exists(big) and os.path.getsize(big) > 4000 else p
        shutil.copy(src_img, os.path.join(tmp, "%04d_0.jpg" % k))
        for j, u in enumerate((it.get("pics") or [])[1:4]):
            q = os.path.join(D, "_thumbs", "%s_%s_p%d.jpg" % (it["src"], it["id"], j + 1))
            if not os.path.exists(q):
                curl(u + ("&w=720" if "?" in u else "?w=720"), q, 20)
            if os.path.exists(q) and os.path.getsize(q) > 2000:
                shutil.copy(q, os.path.join(tmp, "%04d_%d.jpg" % (k, j + 1)))
                extra.setdefault(k, []).append(q)
    res = {}
    for nm in ("text", "face"):
        b = _vision_bin(nm)
        if b:
            try:
                env = dict(os.environ, OCR_MIN_CHARS="3", OCR_MIN_CONF="0.3")
                res[nm] = json.loads(subprocess.run([b, tmp], capture_output=True, text=True, timeout=300, env=env).stdout or "{}")
            except Exception:
                res[nm] = {}
    for k, (it, p) in enumerate(pairs):
        keys = [f for f in os.listdir(tmp) if f.startswith("%04d_" % k)]
        if any(res.get("text", {}).get(f) for f in keys):
            flags[p].append("字")
        if any(any(x.get("w", 0) >= 0.18 and x.get("conf", 0) > 0.6 for x in res.get("face", {}).get(f, [])) for f in keys):
            flags[p].append("脸")
        try:
            im = Image.open(p).convert("L")
            if ImageStat.Stat(im).mean[0] < 55:
                flags[p].append("暗")
            if extra.get(k):
                a_ = im.resize((64, 112))
                b_ = Image.open(extra[k][-1]).convert("L").resize((64, 112))
                if ImageStat.Stat(ImageChops.difference(a_, b_)).mean[0] < 4:
                    flags[p].append("静")
        except Exception:
            pass
    shutil.rmtree(tmp, ignore_errors=True)
    return flags


FLAGS = {}


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
    FLAGS.update(vet(ok))
    # 没有角标的排前面（挑片先看干净的），同档内保持源的相关度顺序
    ok.sort(key=lambda x: len(FLAGS.get(x[1], [])))
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
        fl = FLAGS.get(p, [])
        if fl:
            d.rectangle([x, y + ch - 30, x + 30 * len(fl) + 8, y + ch], fill=(190, 30, 30))
            d.text((x + 6, y + ch - 28), "".join(fl), fill="white", font=font(22))
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


ALIAS = {"pe": "pexels", "co": "coverr", "mi": "mixkit", "px": "pixabay", "ia": "ia", "wk": "wiki", "ov": "ov"}
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
    if s in ("wiki", "ov"):
        D2 = P(proj, "broll", "img"); os.makedirs(D2, exist_ok=True)
        out = os.path.join(D2, name + ".jpg")
        if not os.path.exists(out) or os.path.getsize(out) < 20000:
            curl(src, out, 120)
        reg_p = os.path.join(D2, "img_picks.json")
        reg = json.load(open(reg_p)) if os.path.exists(reg_p) else {}
        reg[name] = dict(source=s, page=page, file=name + ".jpg", licence=it.get("licence") or LIC[s],
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
    picks[name] = dict(source=s, id=vid, url=src, w=w, h=h, fps=fps, page=page, licence=LIC[s], credit=it.get("credit", ""))
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
elif cmd in ("plan", "lexicon", "auto", "review", "redo"):
    # 概念词表：抽象财经概念 → 看得见的画面（R0 的做法：「监管看得见」配数据地球，「长期」配钟表与公路）
    LEX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "template", "broll_lexicon.json")))
    def suggest(text):
        hit = []
        for c in LEX["concepts"]:
            if any(k in text for k in c["keys"]):
                hit.append(c)
        return hit
    if cmd == "lexicon":
        for t in args:
            for c in suggest(t):
                print("「%s」→ %s：%s  （避开：%s）" % (t, c["name"], " | ".join(c["queries"]), "、".join(c.get("avoid", [])) or "—"))
        sys.exit(0)
    if cmd in ("auto", "review", "redo"):
        # 极简档的素材流程：auto 自动取 → review 出审片表（一张图）→ Agent 看图逐条判 → redo 重取判「换」的 → 再 review
        # 审片标准与填写方法见 references/12 §审片
        DEFAULTS = [["hong kong city skyline", "modern office window city view"], ["hong kong street tram", "city traffic night"],
                    ["business meeting office", "documents desk close up"]]
        dec_p = P(proj, args[args.index("--decompose") + 1]) if "--decompose" in args else P(proj, "decompose.json")
        dec = json.load(open(dec_p))
        _tr_p = P(proj, "work", "transcript_cut.json") if os.path.exists(P(proj, "work", "transcript_cut.json")) else P(proj, "transcript.json")
        SENTS = json.load(open(_tr_p))["sentences"]
        ctext = lambda sh: cover_text(sh.get("cover", ""), SENTS)
        rv_p = os.path.join(D, "auto_review.json")
        rv = json.load(open(rv_p)) if os.path.exists(rv_p) else {"_说明": "", "shots": {}}
        picks_p = os.path.join(D, "stock_picks.json")

        def pick_key(sh):
            nm = str(sh.get("pick", ""))[6:]
            it = (json.load(open(picks_p)) if os.path.exists(picks_p) else {}).get(nm, {})
            return "%s:%s" % (it.get("source"), it.get("id")) if it else None

        def auto_pick(only=None):
            used = {pick_key(sh) for sh in dec.get("shots", []) if str(sh.get("pick", "")).startswith("stock:")} - {None}
            n_ok, k_def = 0, 0
            for sh in dec.get("shots", []):
                if sh.get("type") not in ("B", "S") or sh.get("image") or (only is None and sh.get("pick")) or (only is not None and sh["id"] not in only):
                    continue
                rej = set(rv["shots"].get(sh["id"], {}).get("rejected", []))
                qs = as_list(sh.get("q")) or [q for c in suggest(ctext(sh)) for q in c["queries"][:2]][:3]
                if not qs:
                    qs = DEFAULTS[k_def % len(DEFAULTS)]; k_def += 1
                best = None
                r_ = n_ok % len(qs) if only is None else 0   # 首轮轮换检索词（不让每一镜都搜同一个词）；redo 按审片时写的 q 顺序来
                for q in qs[r_:] + qs[:r_]:
                    _, r = do_search(q, pick_sources("pexels,pixabay"))
                    for it, pth in r:
                        key = "%s:%s" % (it["src"], it["id"])
                        if key not in used and key not in rej and not FLAGS.get(pth):
                            best = (key, it, q); break
                    if best:
                        break
                if not best:
                    print("· %s 没找到干净候选（字／脸／暗／静都有角标，或都被否过），留空——换 q 再 redo" % sh["id"]); continue
                used.add(best[0])
                name = "st_%s" % sh["id"].lower()
                fp_ = os.path.join(D, name + ".mp4")
                if os.path.exists(fp_):
                    os.remove(fp_)   # redo：同名文件先删，否则 do_get 会以为已经下好了
                do_get(best[0], name)
                if not (os.path.exists(fp_) and os.path.getsize(fp_) > 50000):
                    print("· %s 下载失败，留空" % sh["id"]); continue
                sh["pick"] = "stock:" + name
                sh.setdefault("in", 0.5)
                rv["shots"].setdefault(sh["id"], {}).update({"q_used": best[2], "verdict": "", "reason": ""})
                n_ok += 1
                print("✓ %s ← %s（q=%s）" % (sh["id"], best[0], best[2]))
            return n_ok

        def make_review():
            # 审片表：每条自动素材一行——[前一个画面][素材 3 帧][后一个画面]＋这句原话、检索词、自动量的亮度差／色调差／相邻同词
            from PIL import Image, ImageDraw
            import numpy as _np
            tr_ = json.load(open(P(proj, "transcript.json")))
            sents = tr_["sentences"]
            aroll = P(proj, "work", "aroll.mp4")
            strip_ = lambda t: re.sub(r"[，。、！？；：,.!?;: 「」“”…]", "", t or "")

            def sent_of(cover):
                sp_ = sid_span(cover)
                if sp_:
                    return next((x for x in sents if x.get("id") == sp_[0]), None)
                head = strip_(cover.split("…")[0])[:6]
                return next((x for x in sents if head and head in strip_(x.get("text", ""))), None)

            def grab(path, t, w=150, h=266):
                r_ = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.2f" % max(t, 0), "-i", path, "-frames:v", "1",
                                     "-vf", "scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (w, h, w, h), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                    capture_output=True)
                if len(r_.stdout) != w * h * 3:
                    return None
                return Image.frombytes("RGB", (w, h), r_.stdout)

            def stats(im):
                a_ = _np.asarray(im).astype(float)
                return float((0.2126 * a_[..., 0] + 0.7152 * a_[..., 1] + 0.0722 * a_[..., 2]).mean()), float((a_[..., 0] - a_[..., 2]).mean())

            bs = [sh for sh in dec.get("shots", []) if sh.get("type") in ("B", "S") and str(sh.get("pick", "")).startswith("stock:")]
            rows = []
            for sh in bs:
                st_ = sent_of(sh.get("cover", ""))
                t0, t1 = (st_["start"], st_["end"]) if st_ else (None, None)
                clip = os.path.join(D, str(sh["pick"])[6:] + ".mp4")
                cin = float(sh.get("in", 0.5))
                frames = [grab(clip, cin + k) for k in (0.3, 1.3, 2.3)]
                prev_ = grab(aroll, t0 - 0.4) if (st_ and os.path.exists(aroll)) else None
                next_ = grab(aroll, t1 + 0.4) if (st_ and os.path.exists(aroll)) else None
                rows.append((sh, st_, frames, prev_, next_))
            # 相邻关系：按原话出现的时间排序；两条 B-roll 之间不到 6 秒，前后画面就是另一条素材而不是她
            rows.sort(key=lambda r: r[1]["start"] if r[1] else 1e9)
            W_, H_ = 150, 266
            sheet = Image.new("RGB", (W_ * 5 + 60, (H_ + 110) * max(len(rows), 1) + 40), (18, 16, 14))
            d_ = ImageDraw.Draw(sheet)
            d_.text((10, 8), "审片表：左＝前画面　中＝素材三帧　右＝后画面", fill="white", font=font(20))
            hashes = {}
            for k, (sh, st_, frames, prev_, next_) in enumerate(rows):
                y0 = 40 + k * (H_ + 110)
                # 重复素材：中间帧做 8×8 均值指纹，和其他镜头几乎一样就标（10-29：文件和记录对不上，两镜成了同一条）
                if frames[1] is not None:
                    _h = _np.asarray(frames[1].convert("L").resize((8, 8))).astype(float)
                    hashes[sh["id"]] = (_h > _h.mean()).flatten()
                if k > 0 and rows[k - 1][1] and st_ and st_["start"] - rows[k - 1][1]["end"] < 6:
                    prev_ = rows[k - 1][2][-1] or prev_
                if k + 1 < len(rows) and rows[k + 1][1] and st_ and rows[k + 1][1]["start"] - st_["end"] < 6:
                    next_ = rows[k + 1][2][0] or next_
                flags = []
                ok_frames = [f for f in frames if f is not None]
                if ok_frames:
                    yb, cb = map(_np.mean, zip(*[stats(f) for f in ok_frames]))
                    for lab, nb in (("前", prev_), ("后", next_)):
                        if nb is not None:
                            yn, cn = stats(nb)
                            if abs(yb - yn) > 55:
                                flags.append("和%s画面亮度差 %d" % (lab, abs(yb - yn)))
                            if abs(cb - cn) > 45:   # 只是提醒：蓝天接暖色室内本来就会差 40 上下，判断看突不突兀
                                flags.append("和%s画面色调差 %d（冷暖跳）" % (lab, abs(cb - cn)))
                _qa, _qb = rv["shots"].get(rows[k - 1][0]["id"], {}).get("q_used") if k > 0 else None, rv["shots"].get(sh["id"], {}).get("q_used")
                if _qa and _qa == _qb:
                    flags.append("和上一条同一检索词（同类画面相邻）")
                if sh["id"] in hashes:
                    for oid, oh in hashes.items():
                        if oid != sh["id"] and int((oh != hashes[sh["id"]]).sum()) <= 6:
                            flags.append("和 %s 画面几乎一样（重复素材）" % oid)
                ent = rv["shots"].setdefault(sh["id"], {})
                ent.update({"cover": sh.get("cover", ""), "sentence": (st_ or {}).get("text", ""), "pick": sh["pick"], "auto_flags": flags})
                ent.setdefault("verdict", ""); ent.setdefault("reason", "")
                d_.text((10, y0 + 4), "%s　原话：%s" % (sh["id"], ((st_ or {}).get("text") or sh.get("cover", ""))[:34]), fill="yellow", font=font(22))
                d_.text((10, y0 + 32), "检索词：%s　｜　%s" % (ent.get("q_used", "—"), "；".join(flags) or "自动项无异常"), fill=(240, 180, 120) if flags else (170, 200, 170), font=font(18))
                for j, im in enumerate([prev_] + frames + [next_]):
                    x = 10 + j * (W_ + 10)
                    if im is not None:
                        sheet.paste(im, (x, y0 + 62))
                    d_.rectangle([x, y0 + 62, x + W_, y0 + 62 + H_], outline=(90, 90, 90) if j in (0, 4) else (230, 190, 90), width=2)
            out_ = os.path.join(D, "auto_review.jpg")
            sheet.save(out_, quality=85)
            rv["_说明"] = ("自动素材审片：看 auto_review.jpg，每条填 verdict（keep／replace／drop）和 reason；replace 可在 decompose 该镜写新的 q。"
                          "然后 stock.py <工程> redo --decompose <文件> 重取所有 replace 的镜头，再 review。build 会对没审完的报警。")
            json.dump(rv, open(rv_p, "w"), ensure_ascii=False, indent=1)
            print("审片表 → %s（%d 条）；判完写 %s" % (out_, len(rows), rv_p))

        if cmd == "auto":
            n = auto_pick()
            print("自动取素材 %d 条" % n)
        elif cmd == "redo":
            ids = [x for x, e in rv["shots"].items() if e.get("verdict") == "replace"]
            for sh in dec.get("shots", []):
                e_ = rv["shots"].get(sh["id"], {})
                qs_ = as_list(sh.get("q"))
                if sh["id"] not in ids and qs_ and e_.get("verdict") != "keep" and e_.get("q_used") and e_["q_used"] not in qs_:
                    ids.append(sh["id"]); print("· %s 的 q 改过（原来用的「%s」），一起重取" % (sh["id"], e_["q_used"]))
            if "--ids" in args:
                ids = args[args.index("--ids") + 1].split(",")
            for sh in dec.get("shots", []):
                if sh["id"] in ids:
                    k_ = pick_key(sh)
                    if k_:
                        rv["shots"].setdefault(sh["id"], {}).setdefault("rejected", []).append(k_)
                    sh.pop("pick", None)
            for sh in dec.get("shots", []):
                if sh["id"] in [x for x, e in rv["shots"].items() if e.get("verdict") == "drop"]:
                    sh["_dropped"] = True
            dec["shots"] = [sh for sh in dec["shots"] if not sh.pop("_dropped", False)]
            n = auto_pick(only=set(ids))
            print("重取 %d／%d 条" % (n, len(ids)))
        json.dump(dec, open(dec_p, "w"), ensure_ascii=False, indent=1)
        make_review()
        sys.exit(0)
    dec_p = P(proj, "decompose.json")
    if "--decompose" in args:
        dec_p = P(proj, args[args.index("--decompose") + 1])
    dec = json.load(open(dec_p))
    _trp = P(proj, "work", "transcript_cut.json") if os.path.exists(P(proj, "work", "transcript_cut.json")) else P(proj, "transcript.json")
    SENTS_P = json.load(open(_trp))["sentences"]
    PD = os.path.join(D, "plan")
    os.makedirs(PD, exist_ok=True)
    plan = {}
    from PIL import Image, ImageDraw
    for sh in dec.get("shots", []):
        if sh.get("type") not in ("B", "S") or sh.get("pick") or sh.get("image"):
            continue
        qs = as_list(sh.get("q")) or [q for c in suggest(cover_text(sh.get("cover", ""), SENTS_P) + sh.get("why", "")) for q in c["queries"][:2]][:3]
        if not qs:
            print("· %s 没写 q，词表也没命中：在 decompose 里给这镜写 2–3 个英文画面词（\"q\": [...]）" % sh["id"])
            continue
        landscape = sh.get("layout") == "band"
        got = []
        for q in qs:
            _, r = do_search(q, pick_sources(sh.get("source") or ("pexels,pixabay" if not PIXABAY_KEY else "pexels,pixabay")))
            got += r
        seen, uniq = set(), []
        for it, p in got:
            k = "%s:%s" % (it["src"], it["id"])
            if k not in seen:
                seen.add(k)
                uniq.append((it, p))
        uniq.sort(key=lambda x: len(FLAGS.get(x[1], [])))
        uniq = uniq[:16]
        cw, ch = 200, 356
        sheet = Image.new("RGB", (cw * 8, ch * max(1, (len(uniq) + 7) // 8) + 44), (16, 14, 12))
        d = ImageDraw.Draw(sheet)
        d.text((10, 8), "%s · %s · q=%s" % (sh["id"], sh.get("cover", "")[:24], " / ".join(qs))[:110], fill="white", font=font(22))
        for i, (it, p) in enumerate(uniq):
            im = Image.open(p).convert("RGB")
            im.thumbnail((cw, ch))
            x, y = (i % 8) * cw, 44 + (i // 8) * ch
            sheet.paste(im, (x + (cw - im.width) // 2, y + (ch - im.height) // 2))
            d.rectangle([x, y, x + 150, y + 26], fill="black")
            d.text((x + 4, y + 3), "%s:%s" % (it["src"][:2], it["id"]), fill="yellow", font=font(20))
            fl = FLAGS.get(p, [])
            if fl:
                d.rectangle([x, y + ch - 30, x + 30 * len(fl) + 8, y + ch], fill=(190, 30, 30))
                d.text((x + 6, y + ch - 28), "".join(fl), fill="white", font=font(22))
        sp = os.path.join(PD, "%s.jpg" % sh["id"])
        sheet.save(sp, quality=82)
        plan[sh["id"]] = {"cover": sh.get("cover"), "layout": sh.get("layout", "full"), "q": qs, "sheet": sp,
                          "candidates": [{"key": "%s:%s" % (it["src"][:2], it["id"]), "flags": FLAGS.get(p, [])} for it, p in uniq]}
        print("== %s %d 条候选 → %s" % (sh["id"], len(uniq), sp))
    json.dump(plan, open(os.path.join(PD, "plan.json"), "w"), ensure_ascii=False, indent=1)
    print("✓ 看 broll/stock/plan/*.jpg 挑片（先看没有红角标的）→ stock.py get <源:id> <名字> → decompose 写 pick")
elif cmd == "get":
    for i in range(0, len(args), 2):
        do_get(args[i], args[i + 1])
else:
    die(__doc__)
