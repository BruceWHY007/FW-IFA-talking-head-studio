#!/usr/bin/env python3
"""⑤ 组装：decompose.json（镜头计划）＋剪后句表＋素材 → timeline.json（全片唯一时间真源）＋素材归一化＋字体子集。

    python3 build.py <工程目录> [--no-conform]

decompose.json 的写法见 references/02 §四。核心：镜头用「原话锚点」定位，不写秒数——
  "cover": "从这句话的某几个字…到这几个字"   （省略号两边各取一段原话；只写一段＝只盖这一段）
没被任何镜头盖住的时间＝人脸镜头（A）。剪辑点自动吸附到字缝，再落到帧网格。
产物：timing.json、remotion/src/timeline.json、remotion/public/{aroll_cut.mp4, clips/, img/, fonts/, grain.png}、out/分镜表.md
"""
import argparse, glob, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
from kb import P, SKILL, FPS, run, load, save, die, probe, encoder_args, hms, clip_cuts, sid_span, as_list
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--no-conform", action="store_true", help="只重算时间线，不重新处理素材")
ap.add_argument("--decompose", default="decompose.json", help="换一份镜头计划（同一条原片出不同风格的版本）")
ap.add_argument("--style", default="", help="临时换风格包：A／B／C／K1／K2／K3")
ap.add_argument("--theme", default="", help="临时换账号主题：themes.json 里的名字")
ap.add_argument("--draft", action="store_true", help="草稿：完整版表达层检查、审片理由检查只提醒不停（只想先看结构／空片格时用）")
ap.add_argument("--sync-packs", action="store_true", help="把技能模板里的版式包同步进本工程（技能更新过、工程是旧的时用）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
pj = load(P(proj, "project.json"), {})
dec = load(P(proj, a.decompose) if not os.path.isabs(a.decompose) else a.decompose)
if a.style:
    dec["style"] = a.style
if a.theme:
    dec["theme"] = a.theme
tc = load(P(proj, "work", "transcript_cut.json"))
edl = load(P(proj, "work", "edl.json"))
lib = load(P(proj, "broll", "library.json"), {"clips": {}})
R = P(proj, "remotion")
PUB = P(R, "public")
# 风格包：A editorial 分带刊物／B glass 雾金玻璃／C kinetic 港刊大字／K1 evidence 证据桌／K2 diagram 图解／K3 brand IFA 品牌刊
ALIAS = {"A": "editorial", "B": "glass", "C": "kinetic", "K1": "evidence", "K2": "diagram", "K3": "brand", "F": "fullbleed",
         "满幅讲述": "fullbleed", "全屏口播": "fullbleed",
         "分带刊物": "editorial", "雾金玻璃": "glass", "港刊大字": "kinetic", "证据桌": "evidence", "图解": "diagram", "IFA品牌刊": "brand", "品牌刊": "brand"}
STYLE = ALIAS.get(str(dec.get("style", "fullbleed")).replace(" ", ""), dec.get("style", "fullbleed"))
# 工程里的版式包是建工程时从技能模板拷来的副本：技能更新了，旧工程不会跟着变（10-27「说修了其实没修」、10-29 第一轮验片看到旧样式）
_tpl = os.path.join(SKILL, "template", "remotion", "src", "packs")
_pk_diff = [f for f in sorted(os.listdir(_tpl)) if os.path.isfile(os.path.join(_tpl, f)) and
            (not os.path.exists(P(R, "src", "packs", f)) or open(os.path.join(_tpl, f), "rb").read() != open(P(R, "src", "packs", f), "rb").read())]
PACK_MSG = []
if _pk_diff and a.sync_packs:
    for f in _pk_diff:
        shutil.copy(os.path.join(_tpl, f), P(R, "src", "packs", f))
    print("✓ 版式包已和技能模板同步：%s" % "、".join(_pk_diff))
elif _pk_diff:
    PACK_MSG.append("工程的版式包和技能模板不一样（%s）：技能更新过就 build --sync-packs 同步；是本工程有意改的就别同步" % "、".join(_pk_diff))
LAYOUT = load(P(R, "src", "packs", "layout.json"))
if STYLE not in LAYOUT:
    die("没有这个风格包：%s（可选 %s）" % (STYLE, "、".join(k for k in LAYOUT if not k.startswith("_"))))
WX, WY, WW, WH = LAYOUT[STYLE]["window"]  # 画面窗：B-roll 按它的尺寸归一化
for d in ["clips", "img", "fonts"]:
    os.makedirs(P(PUB, d), exist_ok=True)
DUR = tc["duration"]

# ---------- 0.5 decompose 格式纠正与必填项（10-30：弱一点的模型最常写错的几处——能纠的自动纠，纠不了的直接停） ----------
FIXED = []
for s_ in dec.get("shots", []):
    if not s_.get("cover") and s_.get("at"):
        s_["cover"] = s_["at"]
    if not s_.get("cover"):
        die("镜头 %s 没写 cover（锚点）：写原话片段，或直接写句号 \"s17\"／\"s16–s19\"（句号见 work/beats.md）" % s_.get("id"))
    if isinstance(s_.get("q"), str):
        s_["q"] = as_list(s_["q"]); FIXED.append("%s 的 q 写成了字符串，已改成列表" % s_["id"])
    inf_ = s_.get("info")
    if isinstance(inf_, dict) and isinstance(inf_.get("items"), list):
        for j_, it_ in enumerate(inf_["items"]):
            if isinstance(it_, str):
                inf_["items"][j_] = {"t": it_}; FIXED.append("信息卡 %s 的条目「%s」写成了字符串，已改成 {\"t\": …}（不改会只有序号没有字）" % (s_["id"], it_[:8]))
for tx_ in dec.get("texts", []):
    tx_["lines"] = [{"t": x, "at": x} if isinstance(x, str) else x for x in tx_.get("lines", [])]
if isinstance(dec.get("tracker"), dict):
    dec["tracker"]["items"] = [{"t": x, "at": x} if isinstance(x, str) else x for x in dec["tracker"].get("items", [])]
if STYLE == "fullbleed":
    ttl_ = dec.get("title") or {}
    if not (ttl_.get("series") and ttl_.get("episode")):
        die("F 包没有封面，第一帧就是刊头＝这条片子的标题：decompose 必须写 \"title\": {\"series\": 系列名, \"episode\": 本期标题}（没给就按原话拟，交付时标「拟」）")
    ttl_.setdefault("lines", [ttl_["series"], ttl_["episode"]])
    dec["title"] = ttl_

# ---------- 0. 账号：主题（身份，固定）与形式登记（每支错开）----------
# 登记文件放在工程的上一级目录（同一批工程共用）；一个账号的主题一旦定下就沿用，封面形式与上一支错开
ACCOUNT = dec.get("account") or pj.get("account") or ""
REG_P = P(os.path.dirname(proj), "_口播形式登记.json")
REG = load(REG_P, {"entries": []}) if os.path.exists(REG_P) else {"entries": []}
PREV = [e for e in REG.get("entries", []) if ACCOUNT and e.get("account") == ACCOUNT and e.get("project") != os.path.basename(proj)]
LAST = PREV[-1] if PREV else None
THEMES = {k: v for k, v in load(P(R, "src", "packs", "themes.json")).items() if not k.startswith("_")}
th_name = dec.get("theme") or (LAST or {}).get("theme") or ""
if isinstance(th_name, dict):
    THEME = dict(th_name, name=th_name.get("name", "自定义"), custom=True)
elif th_name:
    if th_name not in THEMES:
        die("没有这个账号主题：%s（可选 %s；也可以在 decompose.theme 里直接写一组颜色）" % (th_name, "、".join(THEMES)))
    THEME = dict(THEMES[th_name], name=th_name, custom=True)
else:
    THEME = dict(THEMES["琥珀金"], name="琥珀金", custom=False)
NF = int(round(DUR * FPS))
def probe_img(p):
    from PIL import Image
    try:
        with Image.open(p) as im:
            return im.size
    except Exception:
        return (0, 0)


warn = list(PACK_MSG) + FIXED
HARD = []   # 不加 --draft 就停的项
# 自动素材审片（stock.py auto → review → redo）：自动取的素材没人挑过，审片没判完就报（10-29：6 条里 4 条是外国国旗与外国政府楼）
_rv_p = P(proj, "broll", "stock", "auto_review.json")
if os.path.exists(_rv_p):
    _rv = load(_rv_p).get("shots", {})
    _auto = [s_ for s_ in dec.get("shots", []) if str(s_.get("pick", "")).startswith("stock:st_%s" % s_["id"].lower())]
    _todo = [s_["id"] for s_ in _auto if _rv.get(s_["id"], {}).get("verdict") != "keep"]
    if _todo:
        warn.append("自动素材没审完：%s（看 broll/stock/auto_review.jpg，在 auto_review.json 填 verdict，replace 的跑 stock.py redo）" % "、".join(_todo))
    # 审片理由要说得出画面里是什么（10-30：DeepSeek 一次把 6 条全写成「复审通过」，其中两条刚换过、没看图）
    _GENERIC = {"", "通过", "复审通过", "ok", "keep", "可以", "可用", "没问题", "贴题", "保留", "合适", "符合"}
    _thin = [s_["id"] for s_ in _auto if _rv.get(s_["id"], {}).get("verdict") == "keep"
             and (str(_rv.get(s_["id"], {}).get("reason", "")).strip().lower() in _GENERIC or len(str(_rv.get(s_["id"], {}).get("reason", "")).strip()) < 8)]
    if _thin:
        HARD.append("审片理由太空：%s —— keep 也要写清画面主体是什么、为什么贴这句（≥8 字）；批量写「通过」等于没审，回去看 auto_review.jpg" % "、".join(_thin))
elif dec.get("lite"):
    warn.append("极简档还没出审片表：先跑 stock.py <工程> auto（或 review）再判")
# 数字核对原声（numcheck.py）：转写会把「千分之一」写成「1%」——没核对、或核对出对不上的，先报（10-29：屏上 1%–1.5% 实为千分之）
_nc_p = P(proj, "work", "numcheck.json")
NUM_VER = []
if not os.path.exists(_nc_p):
    warn.append("屏上数字还没核对原声：先跑 numcheck.py（转写常把千分之／万分之写成 %，或吞掉「点」）")
else:
    _nc = load(_nc_p)
    if os.path.getmtime(P(proj, "transcript.json")) > os.path.getmtime(_nc_p) + 1:
        warn.append("transcript.json 在数字核对之后又改过：重跑 numcheck.py")
    NUM_VER = [_r["id"] for _r in _nc.get("rows", []) if _r.get("verified")]
    for _r in _nc.get("rows", []):
        if _r.get("flag"):
            warn.append("数字对不上原声 %s「%s」：%s" % (_r["id"], _r["text"][:16], _r["flag"]))

# ---------- 1. 全片逐字表 ----------
chars = []
for s in tc["sentences"]:
    for c in s["chars"]:
        chars.append(dict(c, sid=s["id"]))
TEXT = "".join(c["c"] for c in chars)
PUNCT = "，。、！？；：,.!?;:“”\"' "
# ASR 偶尔把一串字记成 0 长度（第 5 轮评审：「点点赞」三个字起止相同），字幕和关键词时间都会跟着错——先报出来
# 剪完之后这类字会被映射成同一个起止（例 77.72–77.76），所以按「连续几个不同 token 的字起点相同」来认
_z, _run = [], []
for c in [c for c in chars if c["c"] not in PUNCT]:
    if _run and abs(c["s"] - _run[-1]["s"]) < 0.005 and c.get("w") != _run[-1].get("w"):  # 同一个 token 的几个字本来就同起点
        _run.append(c)
    else:
        if len(_run) >= 2:
            _z.append(_run)
        _run = [c]
if len(_run) >= 2:
    _z.append(_run)
for r in _z:
    warn.append("逐字时间里「%s」%d 个字起点相同（%.2fs，ASR 没对上）：同卡两行已改为一起出，关键词高亮可能早，必要时按能量谷手改 transcript.json" % ("".join(c["c"] for c in r), len(r), r[0]["s"]))

def find(anchor, after_idx):
    """在全文里从 after_idx 往后找锚点，返回 (起字下标, 止字下标)。锚点里的标点和空格不参与匹配。
    也可以直接写句号："s17"＝这一整句，"s16–s19"＝从 s16 第一个字到 s19 最后一个字（句号见 work/beats.md）。"""
    sp_ = sid_span(anchor)
    if sp_:
        ia_ = [i for i, c in enumerate(chars) if c["sid"] == sp_[0] and c["c"] not in PUNCT]
        ib_ = [i for i, c in enumerate(chars) if c["sid"] == sp_[1] and c["c"] not in PUNCT]
        return (ia_[0], ib_[-1]) if ia_ and ib_ and ib_[-1] >= ia_[0] else None
    def norm_find(needle, start):
        n = "".join(ch for ch in needle if ch not in PUNCT)
        idx = [i for i, ch in enumerate(TEXT) if ch not in PUNCT]
        stream = "".join(TEXT[i] for i in idx)
        k0 = next((k for k, i in enumerate(idx) if i >= start), len(idx))
        k = stream.find(n, k0)
        if k < 0:
            return None
        return idx[k], idx[k + len(n) - 1]
    if "…" in anchor:
        a0, a1 = [x for x in anchor.split("…") if x][:2]
        r0 = norm_find(a0, after_idx)
        if not r0:
            return None
        r1 = norm_find(a1, r0[0])
        return (r0[0], r1[1]) if r1 else None
    return norm_find(anchor, after_idx)

def gap_before(i):
    return chars[i]["s"] - chars[i - 1]["e"] if i > 0 else chars[0]["s"]

# ---------- 2. 镜头 → 时间 ----------
shots = []
cursor = 0
for sh in dec.get("shots", []):
    r = find(sh["cover"], cursor)
    if not r:
        r = find(sh["cover"], 0)
        if not r:
            die("镜头 %s 的锚点「%s」在剪后文字里找不到（删了？改字了？）→ 别凭印象抄原话，直接写句号 \"s17\" 或 \"s16–s19\"（句号见 work/beats.md）" % (sh["id"], sh["cover"]))
    i0, i1 = r
    cursor = i1
    # 剪辑点落在开口帧上：切进来＝这一段第一个字开口；切回去＝下一个字开口。字幕换卡与画面切换因此同帧
    t0 = chars[i0]["s"] if i0 > 0 else 0.0
    nx = next((j for j in range(i1 + 1, len(chars)) if chars[j]["c"] not in PUNCT), None)  # 标点不是开口
    if nx is not None and chars[nx]["s"] - chars[i1]["e"] < 0.6:
        t1 = chars[nx]["s"]
    elif nx is not None:
        t1 = chars[i1]["e"] + 0.2
    else:
        t1 = DUR
    shots.append(dict(sh, t0=t0, t1=t1, i0=i0, i1=i1))
shots.sort(key=lambda x: x["t0"])

# 规则：B 镜头 ≥1.6s；相邻非 A 镜头之间 <0.6s 的 A 缝合掉（防止一闪而过的脸）
MIN_B, MAX_B = 1.6, (9.0 if STYLE == "fullbleed" else 6.5)   # F 包：R0 单条 B 最长 9s（数据地球那段），见 references/11 §五
ONSETS = sorted(set(c["s"] for c in chars if c["c"] not in PUNCT))
for k, s in enumerate(shots):
    mn = 1.2 if s["type"] == "G" else 2.4 if s["type"] == "I" else MIN_B  # 大字卡最短 1.2s（引子越短越好）；信息卡 2.4s
    if s["t1"] - s["t0"] < mn:
        # 太短的镜头往前长（落在更早一个开口帧上），不往后长——往后长会让剪辑点落在句中、字幕先换位再跳
        lo_ = shots[k - 1]["t1"] if k > 0 else 0.0
        cand = [o for o in ONSETS if lo_ <= o <= s["t1"] - mn]
        if cand:
            s["t0"] = cand[-1]
        else:
            s["t1"] = min(s["t0"] + mn, shots[k + 1]["t0"] if k + 1 < len(shots) else DUR)
for k in range(len(shots) - 1):
    a_, b_ = shots[k], shots[k + 1]
    if b_["t0"] - a_["t1"] < 0.6:
        a_["t1"] = b_["t0"]
    if a_["t1"] > b_["t0"]:
        a_["t1"] = b_["t0"]
# 信息卡（I）：条目、数字、柱子按原话锚点揭开；没写锚点就按顺序每 0.4s 一条
def info_need(s):
    """返回（各条目揭开秒数列表, 卡片至少要停到的秒数）"""
    info = s.get("info") or {}
    kind = info.get("kind")
    items = info.get("items") or info.get("groups") or []
    t_base = s["t0"] - 0.07   # 没写锚点的条目：第一条在切点前 2 帧就在（第 6 轮：K2 切进来先露空卡）
    ts = []
    for n_, it in enumerate(items):
        r_ = find(it["at"], s["i0"]) if isinstance(it, dict) and it.get("at") else None
        ts.append(chars[r_[0]]["s"] if r_ else t_base + n_ * 0.4)
    last = max(ts) if ts else t_base
    if kind == "quote":
        n_ch = len(str(info.get("text", "")))
        return ts, s["t0"] + max(2.0, n_ch / 8 + 0.6)
    hold = {"list": 1.2, "timeline": 1.2, "compare": 1.4, "chart": 1.9}.get(kind, 1.3)
    return ts, last + hold

# 大字卡／信息卡：字落下后至少完整可读一段时间，出点延到那之后的第一个开口帧（10-22 评审第 3 轮：量在屏时长会骗人）
for k, s in enumerate(shots):
    fig = s.get("figure") or {}
    need_t = None
    if s["type"] == "G" and fig.get("at"):
        r_ = find(fig["at"], s["i0"])
        if r_:
            need_t = chars[r_[0]]["s"] + (6 + 39) / FPS
    if s["type"] == "I":
        need_t = info_need(s)[1]
    if need_t is not None and s["t1"] < need_t:
        nxt_t = shots[k + 1]["t0"] if k + 1 < len(shots) else DUR
        cand = [o for o in ONSETS if o >= need_t]
        want = cand[0] if cand else need_t
        if want > nxt_t and k + 1 < len(shots) and shots[k + 1]["type"] in ("B", "S", "PH") \
                and shots[k + 1]["t1"] - want >= MIN_B:
            shots[k + 1]["t0"] = want  # 后一镜够长：把它的入点往后推，让大字读完（仍落在开口帧上）
            nxt_t = want
        s["t1"] = min(want, nxt_t)
        if s["type"] == "I" and s["t1"] < need_t - 0.2:
            warn.append("信息卡 %s 只能停到 %.1fs，读完要到 %.1fs：把锚点往后写、条目减少，或让下一镜让位" % (s["id"], s["t1"], need_t))
# 跳切藏到镜头下面：镜头入点前 ≤8 帧有跳切，入点提前到跳切；出点后 ≤8 帧有跳切，出点延到跳切（不留几帧的人脸碎片）
_jc_s = edl.get("jump_cuts", [])
for k, s in enumerate(shots):
    for c in _jc_s:
        if 0 < s["t0"] - c <= 8 / FPS and (k == 0 or shots[k - 1]["t1"] <= c):
            s["t0"] = c
        if 0 < c - s["t1"] <= 8 / FPS and (k + 1 == len(shots) or shots[k + 1]["t0"] >= c):
            s["t1"] = c
for s in shots:
    s["from"], s["to"] = int(round(s["t0"] * FPS)), int(round(s["t1"] * FPS))
    fig = s.get("figure") or {}
    if s["type"] == "G" and fig.get("at"):
        r_ = find(fig["at"], s["i0"])
        if r_:
            rv_f = int(round(chars[r_[0]]["s"] * FPS))
            if s["from"] > rv_f - 4:
                s["from"] = max(rv_f - 4, 0)  # 数字要在开口那一帧已经落下：卡片至少提前 4 帧起（第 4 轮评审：晚 7–8 帧）
    if (s["t1"] - s["t0"]) > MAX_B and s["type"] in ("B", "S"):
        warn.append("%s 长 %.1fs：单条 B-roll 超过 %.1fs 会闷，拆成两条或缩短" % (s["id"], s["t1"] - s["t0"], MAX_B))
zero = [x for x in shots if x["to"] - x["from"] <= 0]
if zero:
    ids = "、".join(x["id"] for x in zero)
    die("有镜头长度算成 0 帧：%s（多半是两个镜头用了同一句原话做锚点，后一个被前一个吃掉了）。删掉一个，或把其中一个的 cover 改到别处" % ids)
from collections import Counter as _C
_picks = _C(s.get("pick") for s in shots if s.get("pick"))
for _p, _n in _picks.items():
    if _n > 2 and not dec.get("lite"):
        # 10-30：DeepSeek 先下 3–5 条通用香港素材再分给各句，一条天际线用了 5 次——完整版直接停
        HARD.append("同一段素材用了 %d 次：%s——一条素材最多 2 次；每条 B-roll 按自己那句的 see 去找，不许先下几条通用素材再分给各句" % (_n, _p))
    elif _n >= 3:
        warn.append("同一段素材用了 %d 次：%s（规则：一支片子里同一条素材最多 2 次，第三次起换素材或上图卡；本地没有就按 03 的规则去免费素材库找）" % (_n, _p))
_end = (dec.get("end") or {})
if _end:
    _full = "".join(x["text"] for x in tc["sentences"])
    if "下期" in str(_end.get("kicker", "")) and not any(k in _full for k in ("下期", "下一个视频", "下一条", "下次")):
        warn.append("落版写了「下期」，但口播里没提到下一期：不是每条片子都有下一期，改成总结／行动号召，或删掉 kicker")
covered = sorted((s["from"], s["to"]) for s in shots)

# 人脸段 = 补集
a_segs, cur = [], 0
for f0, f1 in covered:
    if f0 > cur:
        a_segs.append((cur, f0))
    cur = max(cur, f1)
if cur < NF:
    a_segs.append((cur, NF))
a_total = sum(b - a for a, b in a_segs) / FPS
for a0, a1 in (a_segs if STYLE != "fullbleed" else []):   # F 包的人脸段按「版面事件间隔」查，在后面
    # 景别变化不算「换了画面」（10-22 评审：一次推镜撑不住 12.5 秒的人脸）；连续人脸 >8.5s 就要插一条
    if (a1 - a0) / FPS > 8.5:
        warn.append("人脸镜头 %s–%s 连续 %.1fs（>8.5s）：中间找一句事实、名词或动作盖 B-roll"
                    % (hms(a0 / FPS), hms(a1 / FPS), (a1 - a0) / FPS))

# ---------- 3. 跳切处换景别（只处理露在人脸镜头里的跳切） ----------
face = pj.get("face", {"cx": 0.5, "cy": 0.42, "w": 0.35})
punch = dec.get("punch_scale", 1.06 if face.get("w", .35) < .45 else 1.0)  # 1.08 时人前倾就切到头顶（第 4 轮评审）
cuts = [int(round(t * FPS)) for t in edl.get("jump_cuts", [])]
# 标注签在场时不换景别（换了指引线就指偏，10-22 评审第 2 轮）
_tag_spans = []
for tg in dec.get("tags", []):
    r_ = find(tg["cover"], 0)
    if r_:
        _tag_spans.append((int(round(chars[r_[0]]["s"] * FPS)) - 2, int(round(chars[r_[1]]["e"] * FPS)) + 14))
cuts = [c for c in cuts if not any(a_ <= c <= b_ for a_, b_ in _tag_spans)]
zoom, state = [], 0
bounds = sorted(set([0, NF] + cuts + [x for seg in a_segs for x in seg]))
for z0, z1 in zip(bounds[:-1], bounds[1:]):
    in_a = any(a0 <= z0 < a1 for a0, a1 in a_segs)
    if in_a and z0 in cuts:
        state ^= 1
    zoom.append({"from": z0, "to": z1, "scale": punch if state else 1.0})
# 短于 12 帧的景别碎段沿用前一段的景别，再把相邻同景别的段合并（10-22 评审：单帧、4 帧、8 帧、11 帧的「先跳一下」）
for i_, z in enumerate(zoom):
    if z["to"] - z["from"] < 12:
        z["scale"] = zoom[i_ - 1]["scale"] if i_ > 0 else (zoom[1]["scale"] if len(zoom) > 1 else 1.0)
merged_z = []
for z in zoom:
    if merged_z and merged_z[-1]["scale"] == z["scale"] and merged_z[-1]["to"] == z["from"]:
        merged_z[-1]["to"] = z["to"]
    else:
        merged_z.append(dict(z))
zoom = merged_z

# ---------- 4. 素材归一化：统一调色、裁切、时长 ----------
GRADE = dec.get("grade", "eq=contrast=1.05:saturation=0.84:gamma=0.97,colorbalance=rs=0.02:gs=0.0:bs=-0.03:rh=0.03:bh=-0.04")

def src_path(pick):
    kind, _, ref = pick.partition(":")
    if kind == "lib":
        c = lib["clips"].get(ref)
        return c["path"] if c else None
    if kind == "stock":
        return P(proj, "broll", "stock", ref + ".mp4")
    if kind == "gen":
        return P(proj, "broll", "gen", ref + ".mp4")
    if kind == "file":
        return ref if os.path.isabs(ref) else P(proj, ref)
    return None

def conform_extra(pick, t_in, need_s, W, H, name, fx=0.5, fy=0.5, extra=""):
    """F 包的插条、分带第二三条：裁成 W×H、统一调色、24/25fps 逐帧铺进 30fps；不够长慢放到 0.85，再不够就报。返回 public 下的相对路径"""
    sp = src_path(pick) if ":" in str(pick)[:7] else (pick if os.path.isabs(pick) else P(proj, pick))
    if not sp or not os.path.exists(sp):
        warn.append("%s 的素材不存在：%s → 这一块先空着" % (name, pick))
        return None
    ext = os.path.splitext(sp)[1].lower()
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        dst = P(PUB, "img", name + ext)
        shutil.copy(sp, dst)
        w_, h_ = probe_img(sp)
        if w_ and W / min(w_, h_ * W / H) > 1.6:
            warn.append("%s 图片 %dx%d 放进 %dx%d 要放大 %.1f 倍，会糊：换大图" % (name, w_, h_, W, H, W / min(w_, h_ * W / H)))
        return "img/%s%s" % (name, ext)
    info = probe(sp)
    v = info["video"]
    sfps = v["fps"]
    fm = 23.5 < sfps < 25.5
    speed = 30.0 / sfps if fm else 1.0
    need_src = need_s * speed
    avail = info["duration"] - t_in
    if avail < need_src:
        if fm and avail >= need_s + 0.04:
            fm, speed, need_src = False, 1.0, need_s
        else:
            fm = False
            speed = max(avail / need_s, 0.85)
            need_src = need_s * speed
            if avail / need_s < 0.85:
                warn.append("%s 素材从 %.1fs 起只剩 %.1fs，不够 %.1fs：换素材或改入点" % (name, t_in, avail, need_s))
    look = GRADE + ("," + extra if extra else "")
    ar = "%d/%d" % (W, H)
    cw, chh = "min(iw\\,ih*%s)" % ar, "min(ih\\,iw/(%s))" % ar
    pts = "settb=1/30,setpts=N" if fm else "setpts=(PTS-STARTPTS)/%.4f" % speed
    fc = "[0:v]%s,fps=30,crop=%s:%s:(iw-%s)*%.3f:(ih-%s)*%.3f,scale=%d:%d,%s,format=yuv420p" % (pts, cw, chh, cw, fx, chh, fy, W, H, look)
    out = P(PUB, "clips", name + ".mp4")
    sig = json.dumps([sp, t_in, W, H, fx, fy, round(speed, 4), round(need_s, 3), look, fm])
    sig_p = out[:-4] + ".sig"
    if not os.path.exists(out) or not os.path.exists(sig_p) or open(sig_p).read() != sig or not a.no_conform:
        run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t_in, "-i", sp, "-t", "%.3f" % (need_src + 0.1), "-filter_complex", fc]
            + encoder_args("high") + ["-an", "-r", "30", "-t", "%.3f" % need_s, out])
        open(sig_p, "w").write(sig)
    up = W / min(v["w"], v["h"] * W / H)
    if up > 1.6:
        warn.append("%s 素材 %dx%d 裁进 %dx%d 要放大 %.1f 倍会糊：换更高清的，或改用 band 画框条" % (name, v["w"], v["h"], W, H, up))
    return "clips/%s.mp4" % name

# F 包：每种画面处理里主素材实际占的框（主素材按这个尺寸裁，不按整窗裁——分带只有 650 高）
F_MAIN = {"bands3": (1080, 650), "glowband": (1080, 1200)}   # glowband 接缝 10-29 由 1150 下移到 1200（字幕不压接缝）
F_LAYOUTS = ("full", "band", "bands3", "pip", "glow", "glowband", "ring", "doc")

# 信息卡输出：锚点→帧号；quote 的重点词→字符区间；按卡型查字数（装不下就报，不缩字号、不截断）
LIMITS = {"quote": [("text", 44)], "compare": [("title", 16)], "list": [("title", 16)], "timeline": [("title", 16)], "chart": [("title", 18)]}
ITEM_LIM = {"compare": {"label": 6, "value": 7, "unit": 6, "note": 16}, "list": {"t": 9, "d": 16}, "timeline": {"when": 8, "what": 12},
            "chart": {"label": 8}}
def info_out(s):
    info = json.loads(json.dumps(s["info"]))
    kind = info.get("kind")
    if kind not in ("quote", "compare", "list", "timeline", "chart"):
        die("信息卡 %s 的 kind 只能是 quote／compare／list／timeline／chart，写的是 %s" % (s["id"], kind))
    ts, _ = info_need(s)
    for it, t in zip(info.get("items") or info.get("groups") or [], ts):
        if isinstance(it, dict):
            it["revealAt"] = int(round(t * FPS))
            it.pop("at", None)
    for key, lim in LIMITS.get(kind, []):
        if len(str(info.get(key, ""))) > lim:
            warn.append("信息卡 %s 的 %s 有 %d 字（上限 %d）：拆成两张卡或删字" % (s["id"], key, len(str(info.get(key, ""))), lim))
    for it in info.get("items") or info.get("groups") or []:
        for key, lim in ITEM_LIM.get(kind, {}).items():
            if info.get("surface") == "paper" and key == "t":
                lim = 13   # 皱纸单一行一条、居中排，13 字以内装得下
            if isinstance(it, dict) and len(str(it.get(key, ""))) > lim:
                warn.append("信息卡 %s 的条目「%s」%s 超过 %d 字" % (s["id"], str(it.get(key))[:8], key, lim))
    if kind == "quote" and info.get("hl"):
        a_ = str(info["text"]).find(info["hl"])
        info["hl"] = [a_, a_ + len(info["hl"])] if a_ >= 0 else None
        if info.get("hl_at"):
            r_ = find(info["hl_at"], s["i0"])
            if r_:
                info["hlAt"] = int(round(chars[r_[0]]["s"] * FPS))
    if kind in ("compare", "chart", "quote") and not info.get("source"):
        warn.append("信息卡 %s（%s）没有来源行：数据和原文必须写 source（她自己的话就写「口述」）" % (s["id"], kind))
    if kind == "chart":
        for g in info.get("groups", []):
            if len(g.get("values", [])) != len(info.get("series", [])):
                die("信息卡 %s 的柱图：每组 values 个数要等于 series 个数" % s["id"])
    return info

out_shots = []
for k, s in enumerate(shots):
    o = {"id": s["id"], "type": s["type"], "from": s["from"], "to": s["to"], "push": 1 if k % 2 == 0 else -1,
         "move": s.get("move", "push" if k % 2 == 0 else "pull")}
    # 真实性标签（借自 talk-workbench）：示意画面要标出来，财经内容尤其不能让观众把示意当实拍证据
    kind_ = (s.get("pick") or "").partition(":")[0]
    if s["type"] == "B" or (s["type"] == "G" and s.get("pick")):
        # 角标挂在画面窗右上（页脚 19px 看不见，10-22 评审第 2 轮）；AI 画面写「AI 生成」，免费实拍写「示意画面」
        o["label"] = s.get("label") or {"stock": "示意画面", "gen": "AI 生成", "lib": dec.get("lib_label", "示意画面")}.get(kind_, "")
    if s["type"] == "I":
        o["info"] = info_out(s)
    for key in ("tag", "need", "credit", "figure", "text_ok"):   # text_ok：画面里的字是本意（qa 可读文字项豁免）
        if s.get(key):
            o[key] = dict(s[key]) if isinstance(s[key], dict) else s[key]
    # F 包的画面处理：layout（见 references/11 §四）＋方窗位置＋原文截图的高亮框
    if s.get("layout"):
        if s["layout"] not in F_LAYOUTS:
            die("%s 的 layout 只能是 %s，写的是 %s" % (s["id"], "／".join(F_LAYOUTS), s["layout"]))
        o["layout"] = s["layout"]
    for key in ("pip_pos", "hl"):
        if s.get(key) is not None:
            o[key] = s[key]
    if s.get("hl_at"):
        r_ = find(s["hl_at"], s["i0"])
        if r_:
            o["hlAt"] = int(round(chars[r_[0]]["s"] * FPS))
    if s.get("figure") and s["figure"].get("at"):
        # 大字在说到这个词的那一帧揭开（钉在拍上），之前是预备动作
        r_ = find(s["figure"]["at"], s["i0"])
        if r_:
            o["figure"]["revealFrom"] = int(round(chars[r_[0]]["s"] * FPS))
            lead = (o["figure"]["revealFrom"] - s["from"]) / FPS
            if lead > 1.2:
                warn.append("%s 大字卡揭开前空等 %.1fs（>1.2s 会读作冻住）：cover 只盖那个词＋前面 ≤1 秒的引子" % (s["id"], lead))
        o["figure"].pop("at", None)
    need_s = (s["to"] - s["from"]) / FPS + 0.15
    if s.get("image"):
        # 图片 B-roll：拷贝进 public/img，按窗口比例 cover + 运镜（推近／横移），和视频走同一条相机曲线
        src_img = s["image"] if os.path.isabs(s["image"]) else P(proj, s["image"].replace("file:", ""))
        if not os.path.exists(src_img):
            src_img = src_path("file:" + s["image"]) if not os.path.isabs(s["image"]) else src_img
        if not os.path.exists(src_img):
            warn.append("%s 图片不存在：%s → 先渲空片格" % (s["id"], s.get("image")))
        else:
            ext = os.path.splitext(src_img)[1].lower() or ".jpg"
            dst = P(PUB, "img", s["id"] + ext)
            shutil.copy(src_img, dst)
            o["img"] = "img/%s%s" % (s["id"], ext)
            o["move"] = s.get("move", "push")
            w_img, h_img = probe_img(src_img)
            o["iw"], o["ih"] = w_img, h_img
            if min(w_img, h_img) < 1080 and s.get("layout") != "doc":
                warn.append("%s 图片只有 %dx%d，推到 1080 宽会糊：换大图，或把运镜改成 hold" % (s["id"], w_img, h_img))
    elif s["type"] in ("B", "S") or (s["type"] == "G" and s.get("pick")):
        sp = src_path(s["pick"]) if s.get("pick") else None
        if sp and os.path.exists(sp):
            info = probe(sp)
            v = info["video"]
            t_in = float(s.get("in", 0))
            # 24/25fps 素材逐帧铺进 30fps（播放快 1.25/1.2 倍）：每帧只用一次，不出现「每 5 帧重复 1 帧」的抖
            sfps = v["fps"]
            frame_map = 23.5 < sfps < 25.5 and not s.get("no_frame_map")
            speed = 30.0 / sfps if frame_map else 1.0
            need_src = need_s * speed
            # 素材内部的剪辑点：截取段不能跨过它（否则成片里多一个闪镜）
            cps = [0.0] + [c for c in clip_cuts(sp) if 0.05 < c < info["duration"] - 0.05] + [info["duration"]]
            segs_ = list(zip(cps[:-1], cps[1:]))
            home = next(((x0, x1) for x0, x1 in segs_ if x0 <= t_in < x1), segs_[-1])
            if t_in + need_src > home[1] - 0.04:
                if frame_map and home[1] - home[0] >= need_s + 0.04 and home[1] - home[0] < need_src:
                    frame_map, speed, need_src = False, 1.0, need_s  # 逐帧铺不够长就退回原速
                if home[1] - home[0] >= need_src + 0.04:
                    t_in = max(home[0], home[1] - need_src - 0.04)
                else:
                    alt = [g for g in segs_ if g[1] - g[0] >= need_src + 0.04]
                    if alt:
                        g = min(alt, key=lambda g: abs(g[0] - t_in))
                        warn.append("%s 入点 %.1fs 所在镜头不够长，改用素材里 %.1f–%.1fs 那个镜头" % (s["id"], t_in, g[0], g[1]))
                        t_in = g[0] + 0.02
                    else:
                        warn.append("%s 素材里没有一个连续镜头够 %.1fs（跨内部剪辑点会闪）：换素材或缩短镜头" % (s["id"], need_src))
            avail = info["duration"] - t_in
            if avail < need_src:
                speed = max(avail / need_s, 0.85)
                frame_map = False
                if avail / need_s < 0.85:
                    warn.append("%s 素材从 %.1fs 起只剩 %.1fs，不够 %.1fs（慢放下限 0.85）：换素材或缩短镜头" % (s["id"], t_in, avail, need_s))
            fit = s.get("fit") or ("cover" if v["h"] >= v["w"] or s["type"] == "G" else "cover")
            TW, TH = WW, WH
            if STYLE == "fullbleed" and s["type"] in ("B", "S"):
                lay_ = s.get("layout")
                # 横版素材裁满幅要放大 >1.45 倍：没指定 layout 就自动走 band 画框条（R0 钟表镜、R1 新闻镜的做法），不硬裁
                if not lay_ and v["w"] > v["h"] and WW / min(v["w"], v["h"] * WW / WH) > 1.45:
                    lay_ = "band"
                    o["layout"] = "band"
                if lay_ == "band":
                    fit = "band"
                if lay_ in F_MAIN:
                    TW, TH = F_MAIN[lay_]
            # 单镜补光：在统一调色后面追加（例 "eq=gamma=1.15"），只给偏暗的素材用，整片色调仍是一套
            look = GRADE + ("," + s["grade_extra"] if s.get("grade_extra") else "")
            fx = float(s.get("focus", 0.5))
            fy = float(s.get("focus_y", 0.5))  # 竖向取景：0 顶、1 底（例：浪花在画面下部）
            out = P(PUB, "clips", s["id"] + ".mp4")
            BAND_Y = int(s.get("band_y", LAYOUT[STYLE].get("bandY", 560)))
            sig = json.dumps([sp, t_in, fit, fx, round(speed, 4), round(need_s, 3), look, frame_map, TW, TH, fy, BAND_Y])
            sig_p = out[:-4] + ".sig"
            stale = not os.path.exists(out) or not os.path.exists(sig_p) or open(sig_p).read() != sig
            if stale or not a.no_conform:
                # 先把时间基设成 1/30 再按帧号排时间戳：直接 setpts=N/(30*TB) 时时间基还是 1/25，时间戳被取整回 25fps 网格，
                # 后面的 fps=30 又补出「每 6 帧重复 1 帧」（10-22 评审第 4 轮实测，第 2 轮那次修复其实没生效）
                pts = "settb=1/30,setpts=N" if frame_map else "setpts=(PTS-STARTPTS)/%.4f" % speed
                if not frame_map and 23.5 < sfps < 25.5:
                    # 逐帧铺不够长：用运动补帧到 30fps（不再退回「每 5 帧重复 1 帧」，10-22 评审第 2 轮）
                    pts += ",minterpolate=fps=30:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
                if fit == "band":
                    band_y = BAND_Y
                    fc = ("[0:v]%s,fps=30,split[a][b];"
                          "[a]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=40:2,eq=brightness=-0.16:saturation=0.7[bg];"
                          "[b]scale=1080:-2,%s[fg];[bg][fg]overlay=0:%d,%s" % (pts, look, band_y, "format=yuv420p"))
                    o["band"] = {"y": band_y, "h": int(round(1080 * v["h"] / v["w"]))}
                else:
                    # 裁成画面窗的比例（分带刊物的窗接近方形，横版素材只需轻裁）
                    ar = "%d/%d" % (TW, TH)
                    cw, chh = "min(iw\\,ih*%s)" % ar, "min(ih\\,iw/(%s))" % ar
                    fc = ("[0:v]%s,fps=30,crop=%s:%s:(iw-%s)*%.3f:(ih-%s)*%.3f,scale=%d:%d,%s,format=yuv420p"
                          % (pts, cw, chh, cw, fx, chh, fy, TW, TH, look))
                run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t_in, "-i", sp, "-t", "%.3f" % (need_s * speed + 0.1),
                     "-filter_complex", fc] + encoder_args("high") + ["-an", "-r", "30", "-t", "%.3f" % need_s, out])
                open(sig_p, "w").write(sig)
            o["clip"] = "clips/%s.mp4" % s["id"]
            o["fit"] = fit
            if fit == "band":
                o["band"] = {"y": BAND_Y, "h": int(round(1080 * v["h"] / v["w"]))}
            # F 包分带／光晕圆＋下条：第二、三条素材（picks 里写，入点 ins）
            if s.get("picks"):
                lay_ = o.get("layout")
                sizes = {"bands3": [(1080, 640), (1080, 630)], "glowband": [(1080, 720)]}.get(lay_, [])
                if not sizes:
                    warn.append("%s 写了 picks，但 layout=%s 用不到第二条素材（只有 bands3／glowband 用）" % (s["id"], lay_))
                ins_ = s.get("ins") or []
                o["clips"] = [c for c in (conform_extra(pk, float(ins_[j]) if j < len(ins_) else 0.0, need_s, sizes[j][0], sizes[j][1], "%s_%d" % (s["id"], j + 2))
                              for j, pk in enumerate(s["picks"][:len(sizes)])) if c]
            if s["type"] == "G":
                o["bg"] = o.pop("clip")
            short = min(v["w"], v["h"])
            up = TW / min(v["w"], v["h"] * TW / TH)
            if fit == "cover" and up > 1.45 and s["type"] != "G":  # 大字卡的底压暗当背景，糊一点不碍事
                warn.append("%s 素材 %dx%d 裁进 %dx%d 画面窗要放大 %.1f 倍会糊：换更高清或竖版素材、或换风格包 A（窗接近方形）"
                            % (s["id"], v["w"], v["h"], WW, WH, up))
        elif s["type"] in ("B", "S"):
            hint = "（素材库里的文件挪了位置？跑 broll_index.py <工程> --relink <新目录>）" if s.get("pick", "").startswith("lib:") else ""
            warn.append("%s 还没有素材（pick 为空或文件不存在）→ 先渲空片格%s" % (s["id"], hint))
    if s.get("split"):
        # 分屏：说到 split.at 那个词时，画面窗一分为二，左边是本镜素材，右边是第二条素材
        sp2 = src_path(s["split"]["pick"])
        if not sp2 or not os.path.exists(sp2):
            die("%s 分屏的第二条素材不存在：%s（素材库文件挪了位置就跑 broll_index.py <工程> --relink <新目录>）" % (s["id"], s["split"]["pick"]))
        info2 = probe(sp2)
        t2 = float(s["split"].get("in", 0))
        out2 = P(PUB, "clips", s["id"] + "_b.mp4")
        sfps2 = info2["video"]["fps"]
        fm2 = 23.5 < sfps2 < 25.5
        need2 = need_s * (30.0 / sfps2 if fm2 else 1.0)
        ar = "%d/%d" % (WW // 2, WH)
        cw2, ch2 = "min(iw\\,ih*%s)" % ar, "min(ih\\,iw/(%s))" % ar
        fx2 = float(s["split"].get("focus", 0.5))
        fc2 = ("[0:v]%s,fps=30,crop=%s:%s:(iw-%s)*%.3f:(ih-%s)/2,scale=%d:%d,%s,format=yuv420p"
               % ("settb=1/30,setpts=N" if fm2 else "setpts=PTS-STARTPTS", cw2, ch2, cw2, fx2, ch2, WW // 2, WH, GRADE))
        run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t2, "-i", sp2, "-t", "%.3f" % (need2 + 0.1), "-filter_complex", fc2]
            + encoder_args("high") + ["-an", "-r", "30", "-t", "%.3f" % need_s, out2])
        r_ = find(s["split"]["at"], s["i0"])
        o["split"] = {"clip": "clips/%s_b.mp4" % s["id"], "at": int(round(chars[r_[0]]["s"] * FPS)) if r_ else s["from"] + 30,
                      "labels": s["split"].get("labels", []),
                      # 分屏后左半边取原画哪一段：0＝最左、0.5＝正中（默认）；写字的手在原画左缘就给 0.1（第 5 轮评审）
                      "lx": float(s["split"].get("left_focus", 0.5))}
        # 角标按两半里「更需要声明」的那一半定：任何一半是 AI，就标 AI（第 4 轮评审：只按左半边定，漏标）
        if s["split"]["pick"].partition(":")[0] in ("lib", "gen") and "AI" in (dec.get("lib_label", "") + "AI 生成"):
            o["label"] = dec.get("lib_label", "示意画面 · AI 生成") if s["split"]["pick"].startswith("lib:") else "AI 生成"
    if s["type"] == "P":
        img = P(proj, s["image"]) if not os.path.isabs(s["image"]) else s["image"]
        if not os.path.exists(img):
            die("%s 的图片不存在：%s" % (s["id"], img))
        dst = P(PUB, "img", s["id"] + os.path.splitext(img)[1].lower())
        shutil.copy(img, dst)
        from PIL import Image
        with Image.open(dst) as im:
            o["iw"], o["ih"] = im.size
        o["image"] = "img/" + os.path.basename(dst)
    out_shots.append(o)

# ---------- 5. 刊头、名字条、封面、下期预告（字幕要避让它们，所以先算） ----------
ttl = dec.get("title", {})
spk = dec.get("speaker")
cover = dec.get("cover")
tl_cover = None
if cover:
    # 封面停 1.2s（够读完标题，也是信息流里的第一眼），再用 12 帧推回正常景别；只停 8 帧会读作闪一下（10-22 评审）
    # 封面形式：title（标题）／number（一个数字）／versus（两边对比）／quote（一句原话）。写 "auto" 就在写了数据的几种里挑，
    # 和同一账号上一支错开（第二层「不重样」）；写死某一种就照写的来
    have = [f_ for f_ in ("title", "number", "versus", "quote") if (cover.get(f_) if f_ != "title" else cover.get("title"))]
    form = cover.get("form", "title")
    if form == "auto":
        cands = have or ["title"]
        last_form = (LAST or {}).get("cover_form")
        form = next((f_ for f_ in cands if f_ != last_form), cands[0])
    elif form not in have and form != "title":
        die("封面写了 form=%s，但没写对应的数据（cover.%s）" % (form, form))
    tl_cover = {"frames": int(cover.get("frames", 36)), "trans": 12, "kicker": cover.get("kicker", ""), "title": cover.get("title", []),
                "sub": cover.get("sub", ""), "scale": 1.12, "form": form,
                "number": cover.get("number"), "versus": cover.get("versus"), "quote": cover.get("quote")}
nametag = None
if spk:
    first_a = next(((a0, a1) for a0, a1 in a_segs if a1 - a0 > 45), (0, int(4.5 * FPS)))
    n0 = max(first_a[0], (tl_cover or {}).get("frames", 0) + (tl_cover or {}).get("trans", 0)) + 4
    n1 = min(first_a[1], n0 + int(spk.get("hold", 4.2) * FPS))
    nametag = {"from": n0, "to": n1, "name": spk.get("name", ""), "latin": spk.get("latin", ""), "lines": spk.get("lines", [])}
    if not str(spk.get("name", "")).strip():
        warn.append("名字条没有姓名（speaker.name 为空）：A 包会收成单行身份条，其他包会留一个空壳 → 有姓名就补上，没确认就在交付清单里列明")
end = None
if dec.get("end"):
    e = dec["end"]
    r = find(e["from"], 0)
    if not r:
        die("end.from 锚点找不到：" + e["from"])
    end = {"from": int(round(chars[r[0]]["s"] * FPS)), "to": NF, "kicker": e.get("kicker", "下期预告"), "line": e.get("line", ""), "cta": e.get("cta", "")}

# ---------- 6. 字幕：按标点切短语，一张卡最多两行，第二行在它开口时出现 ----------
HL = [h for h in dec.get("captions", {}).get("highlight", []) if h]
NUM = re.compile(r"(?:[0-9０-９]+|[二三四五六七八九十百千万亿两][一二三四五六七八九十百千万亿两]*)(?:个月|个人|人|年|万|亿|岁|%|倍|天|小时|家|位)")  # 「一个」是量词不是数字，不高亮
MAXC = dec.get("captions", {}).get("max_chars", LAYOUT[STYLE].get("maxChars", 12))  # 按风格包：右沿不压进右侧互动栏
AFTER = "的了着过吧呢啊"          # 可以断在它后面
BEFORE = "也都还就和把在是从让跟但而我你他她它"  # 可以断在它前面（主语起句处）
# 常用双字词：不在中间断（whisper 有时把一个词切成两个 token，词号挡不住）
KEEP2 = set("过去 这几 那几 个月 没有 一下 这个 那个 什么 已经 可以 时间 孩子 团队 香港 布局 事业 家庭 发展 业绩 视频 大家 关注 现在 自己 其实 开始 "
            "决定 学校 读书 入学 适应 放心 出镜 下一 主要 怎么 稀缺 成果 不错 半年 几个 月份 办公 背后 大厦 中环 复星 交代 两个 整个 "
            "后面 多多 一些 点赞 招呼 公司 客户 资产 配置 美国 中国 日本 全球 经济 危机 利息 利率 市场 收入 利润 时候 因为 所以 但是 "
            "如果 我们 你们 他们 她们 这些 那些 还是 只是 就是 不是 所有 今天 明天 去年 今年 明年 一个 一起 一直 一定 可能 应该 需要 "
            "知道 觉得 认为 希望 喜欢 工作 生活 身份 申请 移民 保险 基金 股票 理财 投资 收益 风险 合规 服务 专业 机会 问题 方法 "
            "控制 境外 境内 主体 备案 核准 管理 办法 保单 信托 融资 链条 申报 豁免 通道 罚款 个人 二级 结构 架构 监管 政策 外汇 银行 "
            "通过 条文 路径 资金 出境 返程 实施 系统 报告 合同 债权 持股 持有 代持 杠杆 成本 程序 义务 细则 目录 存量 配套 审批 全过程".split())
KEEPN = ("对外投资 管理办法 外汇购付汇 购付汇 跨境理财通 家族信托 保单持有人 保险合同 工作日 整数倍 二级市场 发改委 居住地 申报路径 "
         "两套 一套 线上 架子 返程投资 境外主体 实质控制 持牌 合规律师 联合惩戒 违法所得 投资额 管辖范围 金融服务 程序义务 全过程").split()
phr = []
for s in tc["sentences"]:
    cs = [c for c in chars if c["sid"] == s["id"]]
    buf = []
    def emit():
        cs_ = [c for k_, c in enumerate(buf) if c["c"] not in "，。、；：,;" and not (c["c"] in ".:" and not (0 < k_ < len(buf) - 1 and buf[k_ - 1]["c"].isdigit() and buf[k_ + 1]["c"].isdigit()))]
        t = "".join(c["c"] for c in cs_)
        if t.strip():
            phr.append({"sid": s["id"], "text": t, "s": buf[0]["s"], "e": buf[-1]["e"], "cs": cs_})
    for ci, c in enumerate(cs):
        # 数字中间的点和冒号不是断句（1-1.5%、9:30）：10-27／10-29 两次实测「再按中方投资额1-1」「5%罚款」被拆成两张卡
        if c["c"] in ".:" and 0 < ci < len(cs) - 1 and cs[ci - 1]["c"].isdigit() and cs[ci + 1]["c"].isdigit():
            buf.append(c)
            continue
        if c["c"] in "，。、；：,.;:！？!?":
            if c["c"] in "！？!?":
                buf.append(c)
            if buf:
                emit()
            buf = []
            continue
        buf.append(c)
    if buf:
        emit()
# 过长短语按意群拆：候选断点打分＝说话时的真实气口（字间停顿）＋软断字＋靠近中间；
# 不在 whisper 的同一个词（token）里断、不在英文词和数字中间断（10-22 评审：「没 / 有」「过 / 去」「一 / 下」「Al / l in」）
LATIN = re.compile(r"[A-Za-z0-9 .%\-]")  # 连字符也算拉丁：1-1.5% 不能被拆成「1-1」和「.5%」（10-27 实测）
def wlen(t):
    return sum(0.55 if LATIN.match(ch) else 1 for ch in t)  # 英文数字按半宽算
def split_long(p):
    t = p["text"]
    cs_ = p["cs"]
    if wlen(t) <= MAXC or len(cs_) != len(t):
        return [p]
    n = len(t)
    def score(i):
        if LATIN.match(t[i - 1]) and LATIN.match(t[i]):
            return -99
        w0, w1 = cs_[i - 1].get("w"), cs_[i].get("w")
        same_word = w0 is not None and w0 == w1
        gap = max(cs_[i]["s"] - cs_[i - 1]["e"], 0)
        soft = 1.0 if (t[i - 1] in AFTER or t[i] in BEFORE) else 0.0
        bal = abs(wlen(t[:i]) - wlen(t[i:])) / max(wlen(t), 1)
        word = t[i - 1:i + 1] in KEEP2
        # 多字术语不拆（对外｜投资、购付｜汇）；引号书名号不和它的字分家（「控制｜」）；不断在「的」前面（被盯上｜的是）——10-29 自查
        term = any(t.find(w_) >= 0 and t.find(w_) < i < t.find(w_) + len(w_) for w_ in KEEPN)
        quote = t[i] in "」”）》、" or t[i - 1] in "「“（《"
        return gap * 8 + soft - bal * 3 - (6 if same_word else 0) - (4 if word else 0) - (5 if term else 0) - (8 if quote else 0) \
            - (2 if t[i] == "的" else 0)
    cut = max(range(2, n - 1), key=score)
    tm = cs_[cut]["s"]  # 拆点用真实字头时间，不插值
    return split_long({"sid": p["sid"], "text": t[:cut], "s": p["s"], "e": cs_[cut - 1]["e"], "cs": cs_[:cut]}) + \
           split_long({"sid": p["sid"], "text": t[cut:], "s": tm, "e": p["e"], "cs": cs_[cut:]})
phr = [q for p in phr for q in split_long(p)]

def hl_ranges(t):
    rs = []
    for h in HL:
        i = t.find(h)
        if i >= 0:
            rs.append([i, i + len(h)])
    for m in NUM.finditer(t):
        if not any(a0 <= m.start() < a1 for a0, a1 in rs):
            rs.append([m.start(), m.end()])
    return rs

cards, i = [], 0
while i < len(phr):
    p = phr[i]
    lines = [p]
    if LAYOUT[STYLE].get("capLines", 2) > 1 and i + 1 < len(phr) and phr[i + 1]["sid"] == p["sid"] and wlen(p["text"]) + wlen(phr[i + 1]["text"]) <= MAXC * 2 \
            and phr[i + 1]["s"] - p["e"] < 0.5:
        lines.append(phr[i + 1])
        i += 1
    cards.append(lines)
    i += 1
# 字幕换卡与剪辑点相差 ≤4 帧时对齐到剪辑点：画面切、字一起换，不各跳各的
EDGES = sorted(set([x["from"] for x in out_shots] + [x["to"] for x in out_shots]))
def snap_edge(fr_):
    e = min(EDGES, key=lambda x: abs(x - fr_)) if EDGES else fr_
    return e if abs(e - fr_) <= 4 else fr_
for p_ in phr:
    p_["s"] = snap_edge(int(round(p_["s"] * FPS))) / FPS
# 字幕最短 0.7s：太短的卡（常见于「忙」这类一字收句）把下一张卡与贴着它的剪辑点一起往后推，最多 4 帧
MINF = int(0.7 * FPS)
for k in range(len(cards) - 1):
    f0 = int(round(cards[k][0]["s"] * FPS))
    nx = int(round(cards[k + 1][0]["s"] * FPS))
    lack = MINF - (nx - f0)
    if lack <= 0:
        continue
    # 先把这张卡往前提（字比嘴早 ≤6 帧算对位，前一张仍要 ≥0.7s，起点上有剪辑点就不提）；
    # 不够再把下一张往后推，但最多 1 帧——原来推 4 帧，下一张就晚 2–4 帧（10-29 qa：「性质上属于」晚 2 帧）
    pf0 = int(round(cards[k - 1][0]["s"] * FPS)) if k > 0 else 0
    cut_at = any(x["from"] == f0 or x["to"] == f0 for x in out_shots)
    take = 0 if cut_at else max(0, min(lack, 5, f0 - (pf0 + MINF)))
    if take:
        cards[k][0]["s"] = (f0 - take) / FPS
        lack -= take
    if 0 < lack <= 1:
        for x in out_shots:
            if x["from"] == nx:
                x["from"] += lack
            if x["to"] == nx:
                x["to"] += lack
        cards[k + 1][0]["s"] = (nx + lack) / FPS
cap_out = []
for k, lines in enumerate(cards):
    f0 = int(round(lines[0]["s"] * FPS))
    nxt = int(round(cards[k + 1][0]["s"] * FPS)) if k + 1 < len(cards) else NF
    end_t = lines[-1]["e"] + 0.35
    f1 = nxt if nxt - int(round(end_t * FPS)) < 15 else int(round(end_t * FPS))
    f1 = max(f1, f0 + int(0.7 * FPS))
    f1 = min(f1, nxt, NF)
    def hl_at(l):
        # 关键词开口那一帧：字幕里的关键词在说到它时才变金、画下划线（跟着嘴走）
        rs = hl_ranges(l["text"])
        cs_ = l.get("cs") or []
        return rs, [int(round(cs_[a]["s"] * FPS)) if len(cs_) == len(l["text"]) and a < len(cs_) else int(round(l["s"] * FPS)) for a, b in rs]
    ls_ = [dict(zip(("text", "from", "hl", "hlAt"), (l["text"], int(round(l["s"] * FPS)), *hl_at(l)))) for l in lines]
    # 同一张卡的第二行若只比第一行晚 ≤8 帧，两行一起出：第一行只露几帧就被顶上，看着像闪（第 5 轮评审：ASR 把「点点赞」记成 0 长度）
    for a_, b_ in zip(ls_, ls_[1:]):
        if b_["from"] - a_["from"] <= 8:
            b_["from"] = a_["from"]
    cap_out.append({"from": f0, "to": f1, "lines": ls_})

# 字幕全片一种字体、一条基线（10-22 评审：A/B 切换时字体和位置一起跳，13 次、340px，像拼凑）。
# 只有大字卡、照片卡把字幕让到更低一点；剪辑点落在一张卡中间时，在剪辑点拆开，后半张不重播入场
def variant_at(fr_):
    s = next((x for x in out_shots if x["from"] <= fr_ < x["to"]), None)
    if s and s["type"] in ("G", "P", "I") and not any(b and b["from"] <= fr_ < b["to"] for b in (nametag, end)):
        return {"P": "p", "G": "g", "I": "g"}[s["type"]], None
    return "a", None
edges = sorted(set([x["from"] for x in out_shots] + [x["to"] for x in out_shots]))
# 封面画在画面窗里的版式（A），字幕从第一句就走；封面占字幕带的版式（B/C），封面停留期间不上字幕
# 封面期间字幕要不要让位：默认 hold（字幕等封面收掉再出），避免「封面小标」和「第一句字幕」说同一件事
if tl_cover and str(cover.get("caption", "run")) == "hold":
    cover_end = tl_cover["frames"] + tl_cover["trans"] // 2
else:
    cover_end = 0 if (not tl_cover or LAYOUT[STYLE].get("coverInWindow")) else tl_cover["frames"] + tl_cover["trans"] // 2
final_caps = []
prev_to = -99
for c in cap_out:
    if c["to"] <= cover_end:
        continue  # 封面停留期间不上字幕（封面大标题就是这段的字）
    if c["from"] < cover_end:
        c["from"] = cover_end
    pieces, st = [], c["from"]
    for e in edges:
        if c["from"] < e < c["to"]:
            pieces.append((st, e))
            st = e
    pieces.append((st, c["to"]))
    pieces = [pc for pc in pieces if pc[1] - pc[0] >= 3] or pieces  # 不留 1–2 帧的碎片
    for j, (p0, p1) in enumerate(pieces):
        v, top = variant_at(p0)
        host = next((x for x in out_shots if x["from"] <= p0 < x["to"]), None)
        dup = str((host or {}).get("figure", {}).get("value", "")) if host and host["type"] == "G" else ""
        # 画面已经说了的字不再上字幕：大字卡上，字幕里与大字相同的那一行删掉
        lines_ = []
        for l in c["lines"]:
            if l["from"] >= p1 or (dup and l["text"].strip("，。！？ ") == dup):
                continue
            if l.get("hl"):
                # 大字卡在屏时字幕不高亮：卡就是这一刻唯一的重点（第 4、5 轮评审：「3 个月」同屏三遍、金「20 人」＋铜「布局」两个重点）
                keep = [(h, a) for h, a in zip(l["hl"], l.get("hlAt", [None] * len(l["hl"])))
                        if not any(g["type"] in ("G", "I") and g["from"] <= (a if a is not None else l["from"]) < g["to"] for g in out_shots)]
                l = dict(l, hl=[h for h, a in keep], hlAt=[a for h, a in keep])
            lines_.append(l)
        cc = {"from": p0, "to": p1, "variant": v, "cont": j > 0, "lines": lines_}
        # 入场动画只给「一段话的第一张」（前面空了 ≥8 帧）；同一段里换卡是硬切，字在开口那一帧就完整可读。
        # 有入场的卡提前 3 帧起，动画在开口帧做完（10-22 评审：每张都重播入场，开口后 4–6 帧才看得清，全片约 4.3 秒半截字）
        cc["animate"] = (j == 0) and (p0 - prev_to >= 8) and prev_to > 0   # 全片第一张不预滚：没有上一张，预滚会早于开口（10-30 qa 超线 2 帧）
        if cc["animate"]:
            cc["from"] = max(p0 - 3, prev_to if prev_to > 0 else 0, cover_end)
        if top:
            cc["top"] = top
        if cc["lines"]:
            final_caps.append(cc)
            prev_to = cc["to"]
# F 包：整行重话换金／银（captions.gold／captions.silver 写原话片段，字幕行包含它就整行换色放大）；第一张卡是开场钩子（放大一档）
_TONE = [(t, "gold") for t in dec.get("captions", {}).get("gold", [])] + [(t, "silver") for t in dec.get("captions", {}).get("silver", [])]
def _norm(t):
    return "".join(ch for ch in t if ch not in PUNCT)
if _TONE:
    _hit = set()
    for c in final_caps:
        for l in c["lines"]:
            for t_, tone_ in _TONE:
                if _norm(t_) and _norm(t_) in _norm(l["text"]):
                    l["tone"] = tone_
                    l["hl"], l["hlAt"] = [], []
                    _hit.add(t_)
    for t_, _ in _TONE:
        if t_ not in _hit:
            warn.append("captions 金／银重话「%s」在字幕里找不到（字幕按气口断行，重话要写成一行里连着的原话）" % t_)
if final_caps and dec.get("captions", {}).get("hook", True):
    final_caps[0]["hook"] = True

# F 包：插条（盖在她画面上的上／下条、角落小图）、屏上字（堆叠清单／步骤标题／散点关键词）、常驻进度坞
def _fr(anchor, after=0, end=False):
    r_ = find(anchor, after)
    if not r_:
        die("锚点找不到：「%s」" % anchor)
    return int(round((chars[r_[1]]["e"] if end else chars[r_[0]]["s"]) * FPS)), r_
def _until(item, f0, i_after, default_s):
    if item.get("until"):
        f1, _ = _fr(item["until"], i_after)
        return f1
    return min(NF, f0 + int(default_s * FPS))
inserts = []
INS_SIZE = {"top": (1080, 520), "bottom": (1080, 650), "corner": (360, 240)}
for n_, ins in enumerate(dec.get("inserts", [])):
    pos = ins.get("pos", "bottom")
    if pos not in INS_SIZE:
        die("inserts 的 pos 只能是 top／bottom／corner：%s" % pos)
    r_ = find(ins["cover"], 0)
    if not r_:
        die("inserts 锚点找不到：" + ins["cover"])
    f0 = int(round(chars[r_[0]]["s"] * FPS))
    nx = next((j for j in range(r_[1] + 1, len(chars)) if chars[j]["c"] not in PUNCT), None)
    f1 = int(round((chars[nx]["s"] if nx is not None else chars[r_[1]]["e"] + 0.3) * FPS))
    if any(x["from"] < f1 and x["to"] > f0 for x in out_shots):
        warn.append("插条「%s」和镜头重叠：插条只放在人脸段上（盖住 B-roll 就看不见了）" % ins["cover"][:12])
    W_, H_ = INS_SIZE[pos]
    rel = conform_extra(ins.get("pick") or ins.get("image"), float(ins.get("in", 0)), (f1 - f0) / FPS + 0.15, W_, H_, "ins%02d" % (n_ + 1),
                        float(ins.get("focus", 0.5)), float(ins.get("focus_y", 0.5)), ins.get("grade_extra", ""))
    item = {"from": f0, "to": f1, "pos": pos, "move": ins.get("move")}
    if rel:
        item["img" if rel.startswith("img/") else "clip"] = rel
    inserts.append(item)
texts_out = []
for tx in dec.get("texts", []):
    kind = tx.get("kind", "stack")
    if kind not in ("stack", "step", "scatter"):
        die("texts 的 kind 只能是 stack／step／scatter：%s" % kind)
    lines_ = []
    cur_ = 0
    for ln in tx.get("lines", []):
        f_, r_ = _fr(ln["at"], cur_)
        cur_ = r_[0]
        lines_.append({"t": ln["t"], "from": f_ - 2, "tone": ln.get("tone"), "xy": ln.get("xy"), "size": ln.get("size")})
    if not lines_:
        continue
    f0 = lines_[0]["from"]
    f1 = _until(tx, f0, cur_, {"step": 4.5, "stack": 3.0, "scatter": 2.6}[kind] + (lines_[-1]["from"] - f0) / FPS)
    if kind == "stack" and len(lines_) > 3:
        warn.append("堆叠清单「%s」有 %d 行：屏上最多同时 3 行（第 4 行起顶掉最早一行），超过 4 行改信息卡" % (lines_[0]["t"], len(lines_)))
    texts_out.append({"kind": kind, "from": f0, "to": f1, "lines": lines_, "align": tx.get("align"), "tone": tx.get("tone"), "top": tx.get("top"), "size": tx.get("size"), "num": bool(tx.get("num"))})
tracker = None
if dec.get("tracker"):
    T = dec["tracker"]
    f0, r0_ = _fr(T["from"])
    items_ = []
    cur_ = r0_[0]
    for it in T.get("items", []):
        f_, r_ = _fr(it["at"], cur_)
        cur_ = r_[0]
        items_.append({"t": it["t"], "from": f_, "n": it.get("n")})
    tracker = {"title": T.get("title", ""), "en": T.get("en", ""), "from": f0, "to": _until(T, f0, cur_, 600), "items": items_}
    if len(items_) > 5:
        warn.append("进度坞有 %d 格：最多 5 格，再多一格就读不清" % len(items_))

# F 包节奏（references/11 §五，R0 实测）：满幅人脸可以长，但连续 12 秒里必须有一次「版面事件」——
# 插条、堆叠清单、步骤标题、散点关键词、金／银整行、进度坞点亮；景别跳切不算（R0 的人脸段靠字的变化撑住，不靠剪碎）
if STYLE == "fullbleed":
    ev = sorted(set([x["from"] for x in inserts] + [x["from"] for x in texts_out] + [l["from"] for x in texts_out for l in x["lines"]]
                    + ([it["from"] for it in tracker["items"]] if tracker else [])
                    + [c["from"] for c in final_caps if any(l.get("tone") for l in c["lines"])]))
    for a0, a1 in a_segs:
        pts = [a0] + [e for e in ev if a0 < e < a1] + [a1]
        gap = max((b_ - a_) for a_, b_ in zip(pts, pts[1:]))
        if gap / FPS > 12:
            warn.append("满幅人脸 %s–%s 有 %.1fs 没有任何版面事件（>12s）：加一处插条／堆叠／金银整行，或盖一条 B-roll" % (hms(a0 / FPS), hms(a1 / FPS), gap / FPS))
    a_share = a_total / DUR
    if not 0.45 <= a_share <= 0.75 and not dec.get("lite"):   # 极简档（lite_plan.py）本来就只靠字和数字卡撑节奏，不查人脸占比
        warn.append("满幅人脸占 %.0f%%（F 包区间 45–75%%，R0 实测 61%%＋插条 7%%）：%s" % (a_share * 100, "B／卡片太多，人被挤掉了" if a_share < 0.45 else "画面处理太少，会读作一条没剪的口播"))
    elif dec.get("lite") and a_share > 0.80:
        warn.append("极简档满幅人脸占 %.0f%%（上限 80%%）：lite_plan.py 的 --broll 调大，或在最长的人脸段补 B-roll／清单卡" % (a_share * 100))
    lays = [x.get("layout", "full") for x in out_shots if x["type"] in ("B", "S")]
    for k_ in range(len(lays) - 2):
        if lays[k_] == lays[k_ + 1] == lays[k_ + 2] and lays[k_] != "full":
            warn.append("连续三条 B-roll 都用 %s：同一种小窗连用三次会读成模板，换一种处理（R0 相邻两次就换）" % lays[k_])
    cards_ = [x for x in out_shots if x["type"] in ("I", "G")]
    if cards_ and sum(x["to"] - x["from"] for x in cards_) / FPS / DUR > 0.25:
        warn.append("信息卡＋大字卡占 %.0f%%（F 包上限 25%%）：F 是「人在讲」的片子，卡多了就成了 K2 图解" % (sum(x["to"] - x["from"] for x in cards_) / FPS / DUR * 100))

# 标注签：挂在任何镜头上（人脸镜头在刊头下方，满幅 B-roll 在顶部）。来源＝decompose.tags ＋ 各镜头的 tag 字段
tags = []
for tg in dec.get("tags", []):
    r = find(tg["cover"], 0)
    if not r:
        die("tags 锚点找不到：" + tg["cover"])
    f0 = int(round(chars[r[0]]["s"] * FPS))
    f1 = int(round(chars[r[1]]["e"] * FPS)) + 12
    tags.append({"from": f0, "to": f1, "text": tg["text"], "point": tg.get("point")})
for s_ in out_shots:
    if s_.get("tag"):
        tags.append({"from": s_["from"], "to": s_["to"], "text": s_["tag"]})
for tg in tags:
    host = next((x for x in out_shots if x["from"] <= tg["from"] < x["to"]), None)
    tg["top"] = 200 if host and host["type"] in ("B", "S") else 420

# ---------- 7. 音效事件（只给画面里真发生的事；B-roll 硬切不配音效，人声是连续的） ----------
sfx = []
if nametag:
    sfx.append({"t": round(nametag["from"] / FPS, 3), "kind": "tick"})
for s in out_shots:
    if s["type"] == "G":
        sfx.append({"t": round(s["figure"].get("revealFrom", s["from"] + 6) / FPS, 3), "kind": "swell"})
    if s["type"] == "P":
        sfx.append({"t": round(s["from"] / FPS, 3), "kind": "air"})
if end:
    sfx.append({"t": round(end["from"] / FPS, 3), "kind": "tick"})

# 章节：刊头上的页签跟着走（看得见进度）；每章第一个 B-roll 从接缝处「升起」，其余硬切
chapters = []
for n, ch in enumerate(dec.get("chapters", [])):
    r = find(ch["from"], 0) if ch.get("from") else (0, 0)
    if not r:
        die("chapters 锚点找不到：" + ch["from"])
    chapters.append({"from": 0 if (n == 0 and not ch.get("from")) else int(round(chars[r[0]]["s"] * FPS)), "n": n + 1, "title": ch["title"]})
for i_, ch in enumerate(chapters):
    nxt_ = chapters[i_ + 1]["from"] if i_ + 1 < len(chapters) else NF
    first_b = next((x for x in out_shots if ch["from"] <= x["from"] < nxt_ and x["type"] in ("B", "S")), None)
    if first_b and i_ > 0 and dec.get("chapter_rise"):
        first_b["enter"] = "rise"  # 默认关：第 4 轮评审——接缝停在脸上 4 帧，拼出「她的头接在别人身上」，判为为动而动
# 重话快推：说到这个词时人脸镜头 4 帧推近，保持到这一段人脸结束
emph = []
for em in dec.get("emphasis", []):
    r = find(em["at"], 0)
    if not r:
        die("emphasis 锚点找不到：" + em["at"])
    f0 = int(round(chars[r[0]]["s"] * FPS))
    seg = next(((a0, a1) for a0, a1 in a_segs if a0 <= f0 < a1), None)
    if seg:
        sc = float(em.get("scale", 1.14))
        zc = next((z["scale"] for z in zoom if z["from"] <= f0 < z["to"]), 1.0)
        if sc < zc * 1.05:
            warn.append("emphasis「%s」推到 %.2f，但这时景别已是 %.2f，推近不到 5%%看不出来：加大或删掉" % (em["at"], sc, zc))
        emph.append({"from": f0, "to": seg[1], "scale": sc})
    else:
        warn.append("emphasis「%s」不在人脸镜头里，跳过" % em["at"])

# 落版：最后一个字说完后，画面停在她的最后一帧（压暗、缓推），字幕带打出行动号召，配乐收尾（冻结检查对这一段豁免）
OUT = int(round(float(dec.get("outro", 1.3)) * FPS))
outro = None
if OUT > 0:
    run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.05", "-i", P(proj, "work", "aroll_cut.mp4"), "-frames:v", "1", "-q:v", "2", P(PUB, "outro.jpg")])
    outro = {"from": NF, "frames": OUT, "cta": (dec.get("end") or {}).get("cta", "")}
    if end:
        end["to"] = NF + OUT

# F 包：皱纸单、堆叠清单、散点关键词在屏时字幕让位；口播里的「第一／第二」正好被步骤标题大字接住时，那张字幕卡也不出（同一处只出一种字）。
# 标 hidden：画面里不画，qa 也不拿它量停留、对位、对比度（10-29 qa：量的是看不见的字）
if STYLE == "fullbleed":
    hide_w = [(x["from"], x["to"]) for x in out_shots if x["type"] == "I" and (x.get("info") or {}).get("surface") == "paper"] + \
             [(x["from"], x["to"]) for x in texts_out if x["kind"] in ("stack", "scatter")]
    steps_ = [(x["from"], x["to"], x["lines"][0]["t"]) for x in texts_out if x["kind"] == "step"]
    for c in final_caps:
        txt_ = "".join(l["text"] for l in c["lines"]).strip("，。、 ")
        if any(a_ <= c["from"] < b_ for a_, b_ in hide_w) or any(a_ - 6 <= c["from"] < b_ and txt_ == t_ for a_, b_, t_ in steps_):
            c["hidden"] = True

# F 包：亮底 B-roll 上字幕托底按亮度加深。量的是字幕那一带（成片 y≈980–1260）在素材里对应的位置，取 3 帧平均亮度：
# Y≤80 用默认 0.20，往上线性加深，封顶 0.60（10-29 qa：白色建筑肋条、亮楼面上白字实测对比度 1.6）
if STYLE == "fullbleed":
    def _zone_y(path, y0, y1, H):
        try:
            dur_ = probe(path)["duration"]
        except Exception:
            return None
        vals = []
        for k_ in (0.25, 0.5, 0.75):
            r_ = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.2f" % (dur_ * k_), "-i", path, "-frames:v", "1",
                                 "-vf", "scale=1080:%d,crop=1080:%d:0:%d,signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-" % (H, max(y1 - y0, 2), y0),
                                 "-f", "null", "-"], capture_output=True, text=True)
            m_ = re.search(r"YAVG=([\d.]+)", r_.stdout + r_.stderr)
            if m_:
                vals.append(float(m_.group(1)))
        return sum(vals) / len(vals) if vals else None
    for s_ in out_shots:
        if s_["type"] not in ("B", "S") or not s_.get("clip"):
            continue
        lay_ = s_.get("layout", "full")
        if lay_ == "doc":
            continue
        if lay_ == "bands3":   # 字幕落在中间那条（650–1290），那条用的是 clips[0]
            src_ = (s_.get("clips") or [None])[0]
            y_ = _zone_y(P(PUB, src_), 330, 610, 640) if src_ else None
        elif lay_ == "glowband":
            y_ = _zone_y(P(PUB, s_["clip"]), 980, 1200, 1200)
        else:
            y_ = _zone_y(P(PUB, s_["clip"]), 980, 1260, 1920)
        if y_ is not None:
            s_["capScrim"] = round(min(0.60, max(0.20, 0.20 + (y_ - 80) / 140 * 0.40)), 2)

# ---------- 7.9 完整版表达层硬检查（10-30）----------
# 完整版不能比极简档少东西。DeepSeek 复现时写的「完整版」只有满幅＋自创动效：金银整行、屏上字、插条、进度坞、小窗一样没用，
# 观感还不如极简档。门槛按片长折算，Claude 定稿（49 号令 204s）每项都在门槛的 1.5–3 倍。
# 某一项这条片子确实用不上：decompose 写 "waive": {"项名": "为什么（≥8 字）"}；只想先看结构：build --draft（只提醒不停）。
GATE = []
if STYLE == "fullbleed" and not dec.get("lite"):
    mins_ = DUR / 60.0
    n_tone = len({l["text"] for c in final_caps for l in c["lines"] if l.get("tone")})
    lay_set = {x.get("layout", "full") for x in out_shots if x["type"] in ("B", "S")}
    n_I = sum(1 for x in out_shots if x["type"] == "I")
    n_G = sum(1 for x in out_shots if x["type"] == "G")
    _all = "".join(s_["text"] for s_ in tc["sentences"])
    _ORD = re.compile(r"^(第[一二三四五六七八九十](?![条款章节号])|[一二三四五六七八九十]是|首先|其次|最后)")
    n_ord = sum(1 for s_ in tc["sentences"] if _ORD.match(s_["text"].strip()))
    has_policy = bool(re.search(r"办法|条例|规定|号令|细则|指引|新规|法规|征求意见", _all))
    n_why = sum(1 for s_ in dec.get("shots", []) if len(str(s_.get("why", "")).strip()) >= 6)
    _bshots = [s_ for s_ in dec.get("shots", []) if s_["type"] in ("B", "S") and s_.get("layout") != "doc" and not str(s_.get("pick", "")).startswith("lib:")]
    n_see = sum(1 for s_ in _bshots if len(str(s_.get("see", "")).strip()) >= 4)
    need = [
        ("gold", "金银整行 captions.gold／silver（最硬的判断整行换金银，要写成字幕里连着的一段原话）", n_tone, max(3, round(mins_ * 1.5))),
        ("texts", "屏上字 texts（step 步骤标题／stack 堆叠清单／scatter 散点关键词）", len(texts_out), max(2, round(mins_ * 1.2))),
        ("layouts", "B-roll 画面处理种类（full／pip 方窗／glow 光晕圆／ring 细环／band 画框条／bands3 三条分带／glowband／doc 原文页）", len(lay_set), 4 if DUR >= 90 else 3),
        ("inserts", "插条 inserts（top／bottom／corner，盖在人脸段上、她还在）", len(inserts), 1 if DUR >= 60 else 0),
        ("info", "信息卡 I（compare／list／timeline／chart／quote；没有能拍的实物时，代码画面就是它）", n_I, 1),
        ("why", "镜头的 why（每一镜一句话：这条画面在这句里指什么）", n_why, len(dec.get("shots", []))),
        ("see", "B-roll 的 see（观众应该看到什么，具体到地点／物件，例「中环中银大厦白天外立面」；先写 see 再按它搜素材）", n_see, len(_bshots)),
    ]
    if n_ord >= 3:
        need.append(("tracker", "进度坞 tracker（口播里有 %d 句以「第一／第二／首先…」开头，逐格点亮）" % n_ord, 1 if tracker else 0, 1))
    if has_policy:
        need.append(("doc", "政策原文页（提到办法／规定／条例：node scripts/webshot.mjs 截官方原文，layout:\"doc\"）", 1 if "doc" in lay_set else 0, 1))
    _waive = dec.get("waive") or {}
    for key, label, got, want in need:
        if got >= want:
            continue
        why_ = str(_waive.get(key, "")).strip()
        if len(why_) >= 8:
            warn.append("完整版检查「%s」%d／%d，已豁免：%s" % (key, got, want, why_))
        else:
            GATE.append("· %s：现在 %d，至少 %d" % (label, got, want))
    if not 0.40 <= a_share <= 0.78:
        GATE.append("· 满幅人脸占 %.0f%%，完整版要在 40–78%%：%s" % (a_share * 100, "卡和 B-roll 太多，人被挤掉了" if a_share < 0.40 else "画面处理太少，加 B-roll／小窗／信息卡"))
    if n_I + n_G > max(5, round(DUR / 25)):
        warn.append("信息卡 %d＋大字卡 %d 张偏多（这条片长建议 ≤%d）：多了像 PPT" % (n_I, n_G, max(5, round(DUR / 25))))
if GATE or HARD:
    msg_ = ""
    if GATE:
        msg_ += "完整版表达层没达标（完整版不能比极简档少；对照 references/13 §4.2「她在说什么→用什么」，每句的建议处理见 work/beats.md）：\n  " + "\n  ".join(GATE) + \
                "\n  某项这条片子确实用不上：decompose 写 \"waive\": {\"项名\": \"理由≥8字\"}（项名：gold／texts／layouts／inserts／info／why／tracker／doc）\n"
    if HARD:
        msg_ += "\n".join("· " + h for h in HARD) + "\n"
    if a.draft:
        warn.extend(("[草稿放行] " + m) for m in msg_.strip().split("\n"))
    else:
        die(msg_ + "  （还在搭结构、只想先看空片格：build --draft，但 --draft 出的片子不能交付）")

# ---------- 8. 写时间线 ----------
shutil.copy(P(proj, "work", "aroll_cut.mp4"), P(PUB, "aroll_cut.mp4"))
tl = {"fps": FPS, "width": 1080, "height": 1920, "durationInFrames": NF + (OUT if outro else 0), "style": STYLE, "outro": outro, "coverInWindow": bool(LAYOUT[STYLE].get("coverInWindow")),
      "theme": THEME, "account": ACCOUNT,
      "aroll": {"src": "aroll_cut.mp4", "face": {"cx": face["cx"], "cy": face["cy"], "w": face.get("w", 0.3)}, "frame": dec.get("frame", {})},
      "shots": out_shots, "arollZoom": zoom, "captions": final_caps,
      "masthead": {"series": ttl.get("series", ""), "episode": ttl.get("episode", ""), "lines": ttl.get("lines", [])} if ttl else None,
      "inserts": inserts, "texts": texts_out, "tracker": tracker, "disclaimer": dec.get("disclaimer", ""),
      "nametag": nametag, "cover": tl_cover, "end": end, "tags": tags, "sfx": sfx, "chapters": chapters, "emph": emph,
      # 底部：plate＝给平台白字压深底（默认，160px）；paper＝整页纸、报尾落到最底（交付给不用底部叠字的平台，或要极简时用）
      "footer": dec.get("footer", "paper"),
      # 报尾两行小字：品牌固定，右边默认当天日期（可被 decompose.footer_text 覆盖）
      "footer_left": (dec.get("footer_text") or {}).get("left") or "复星财富IFA",
      "footer_right": (dec.get("footer_text") or {}).get("right") or __import__("time").strftime("%Y.%m.%d")}
save(P(R, "src", "timeline.json"), tl)
tl["draft"] = bool(a.draft)
save(P(proj, "timing.json"), dict(tl, _说明="全片唯一时间真源（帧，30fps）。字幕与镜头都由原话锚点算出，音效时间写秒。"))

# ---------- 9. 字体子集（宋体按本片用字切，几十 KB）与质感贴图 ----------
texts = [ttl.get("series", ""), ttl.get("episode", "")] + [l["text"] for c in final_caps for l in c["lines"]]
if spk:
    texts += [spk.get("name", "")] + spk.get("lines", [])
if tl_cover:
    texts += tl_cover["title"] + [tl_cover["kicker"], tl_cover["sub"]] + [json.dumps(tl_cover.get(k_), ensure_ascii=False) for k_ in ("number", "versus", "quote")]
if end:
    texts += [end["kicker"], end["line"], end["cta"]]
texts += [t["text"] for t in tags]
texts += ttl.get("lines", []) + [dec.get("disclaimer", "") or "本内容仅作为科普，不构成任何投资建议"]
texts += [l["t"] for x in texts_out for l in x["lines"]]
if tracker:
    texts += [tracker["title"], tracker["en"]] + [it["t"] for it in tracker["items"]]
for s in out_shots:
    texts += [s.get("need", "")] + ([str(v) for v in s["figure"].values()] if s.get("figure") else [])
    if s.get("info"):
        texts.append(json.dumps(s["info"], ensure_ascii=False))
texts += ["来源 · 下期预告 vs “”", end["kicker"] if end else ""]
used = "".join(sorted(set("".join(texts)))) + "0123456789０１２３４５６７８９，。、！？：；“”（）·—…%+-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
open(P(proj, "work", "used_chars.txt"), "w", encoding="utf-8").write(used)
for wt in ("Heavy", "SemiBold"):
    srcf = os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-%s.otf" % wt)
    run([sys.executable, "-m", "fontTools.subset", srcf, "--text-file=" + P(proj, "work", "used_chars.txt"), "--output-file=" + P(PUB, "fonts", "SHSerif-%s.otf" % wt),
         "--layout-features=*", "--no-hinting"])
shutil.copy(os.path.join(SKILL, "assets", "fonts", "BodoniModa.ttf"), P(PUB, "fonts", "BodoniModa.ttf"))
# 字体编进代码包，渲染时不走网络（见 fonts.ts 注释）
import base64
fd = {k: base64.b64encode(open(P(PUB, "fonts", f), "rb").read()).decode()
      for k, f in [("SHSerif-Heavy", "SHSerif-Heavy.otf"), ("SHSerif-SemiBold", "SHSerif-SemiBold.otf"), ("BodoniModa", "BodoniModa.ttf")]}
open(P(R, "src", "fontdata.ts"), "w").write("export const FONT_DATA: Record<string, string> = " + json.dumps(fd) + ";\n")
grain = P(PUB, "grain.png")
if not os.path.exists(grain):
    from PIL import Image
    rng = np.random.default_rng(7)
    g = (128 + rng.normal(0, 38, (960, 540))).clip(0, 255).astype(np.uint8)
    Image.fromarray(g).resize((1080, 1920), Image.NEAREST).save(grain)

# ---------- 10. 分镜表与占比 ----------
TYPES = {"A": "人脸", "B": "B-roll", "S": "本人素材", "P": "照片卡", "G": "数字/大字卡", "PH": "手机里的她", "I": "信息卡"}
share = {"A": a_total}
for s in out_shots:
    share[s["type"]] = share.get(s["type"], 0) + (s["to"] - s["from"]) / FPS
rows = ["# 分镜表（自动生成，改 decompose.json 后重跑 build.py）", "",
        "总长 %s（%d 帧，含落版 %d 帧）。占比：%s" % (hms((NF + (OUT if outro else 0)) / FPS), NF + (OUT if outro else 0), OUT if outro else 0, "，".join("%s %.0f%%" % (TYPES[k], v / DUR * 100) for k, v in share.items())), "",
        "| 镜号 | 时间 | 类型 | 画面 | 这一镜交代什么（原话） | 声音 | 退场 | 延续到下一镜 |", "|---|---|---|---|---|---|---|---|"]
segs = [(a0, a1, "A") for a0, a1 in a_segs] + [(s["from"], s["to"], s["id"]) for s in out_shots]
segs.sort()
byid = {s["id"]: s for s in out_shots}
for a0, a1, sid in segs:
    said = "".join(c["c"] for c in chars if a0 / FPS <= c["s"] < a1 / FPS)
    if sid == "A":
        # 一段人脸里可能有几次跳切换景别：每一小段都列出来（第 5 轮评审：只写第一小段，4 处写错）
        zs = [(max(z["from"], a0), min(z["to"], a1), z["scale"]) for z in zoom if z["from"] < a1 and z["to"] > a0] or [(a0, a1, 1.0)]
        zs_txt = "→".join("%.2f" % z[2] for z in zs) + ("（%s 换）" % "、".join(hms(z[0] / FPS) for z in zs[1:]) if len(zs) > 1 else "")
        rows.append("| A | %s–%s | 人脸 | 原片（景别 %s） | %s | 人声 | 硬切 | 刊头、字幕带 |" % (hms(a0 / FPS), hms(a1 / FPS), zs_txt, said[:28]))
    else:
        s = byid[sid]
        pic = s.get("need", "") or (s.get("figure") or {}).get("value", "") or \
            ("%s · %s" % ((s.get("info") or {}).get("kind", ""), (s.get("info") or {}).get("title") or (s.get("info") or {}).get("text", "")[:12]) if s.get("info") else "")
        rows.append("| %s | %s–%s | %s | %s%s | %s | 人声%s | 硬切 | 金色细线 |" % (sid, hms(a0 / FPS), hms(a1 / FPS), TYPES[s["type"]], pic,
                    "（缺素材）" if s["type"] in ("B", "S") and not s.get("clip") else "", said[:28],
                    "＋" + next((x["kind"] for x in sfx if abs(x["t"] * FPS - a0) < 10), "") if any(abs(x["t"] * FPS - a0) < 10 for x in sfx) else ""))
open(P(proj, "out", "分镜表.md"), "w", encoding="utf-8").write("\n".join(rows) + "\n")

print("✓ timeline：%s，%d 个镜头，%d 张字幕卡" % (hms(DUR), len(out_shots), len(final_caps)))
print("  占比：" + "  ".join("%s %.0f%%" % (TYPES[k], v / DUR * 100) for k, v in share.items()))
for w in warn:
    print("  ⚠ " + w)
if NUM_VER:
    print("  · 数字标过「已核对」的句子：%s —— 交付时列进「待人确认清单」，请人听一遍原声（Agent 自己标的不算定论）" % "、".join(NUM_VER))
if a.draft:
    print("  · 这是 --draft 草稿：表达层／审片检查只提醒没拦，交付前去掉 --draft 重跑")
