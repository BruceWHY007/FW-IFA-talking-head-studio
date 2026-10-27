#!/usr/bin/env python3
"""⑧ 验收：能量化的全量化，出 qa/qa_report.md ＋ 两张抽帧图（给静音解读和导演审片用）。

    python3 qa.py <工程目录> [--video out/成片_9x16.mp4]

量的项（对应 references/06 的质量线）：
  规格（时长/尺寸/帧率）· 第一帧是完成画面 · 冻结段 · 响度与真峰值 · 字幕与语音对位 · 音画同长
  文字对比度（按底板最坏情况算）· 安全区（右侧互动栏、底部描述区）· 屏上文字出处（facts.json）
  节奏（人脸连续时长、B-roll 长度、占比）· 近空画面（复用父 skill 的 qa_edge）
需要人判断的（版式像不像一支片子、拼凑感、拖沓）交给评审子代理看抽帧图，见 references/06 §三。
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, load, save, probe, read_gray_frames, hms, font
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--video", default="")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
V = a.video or P(proj, "out", "成片_9x16.mp4")
tl = load(P(proj, "timing.json"))
FPS = tl["fps"]
STYLE = tl.get("style", "editorial")
rows = []  # (项, 结果, 实测, 线)

def add(item, ok, got, line):
    ok = None if ok is None else bool(ok)
    rows.append((item, "✅" if ok is True else ("⚠️" if ok is None else "❌"), got, line))

# 1 规格
info = probe(V)
v = info["video"]
exp = tl["durationInFrames"] / FPS
nb = subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                     "-of", "csv=p=0", V], capture_output=True, text=True).stdout.strip()
m_nb = re.search(r"\d+", nb)
nb = int(m_nb.group(0)) if m_nb else -1
add("时长（视频流帧数）", nb == tl["durationInFrames"], "%d 帧（时间线 %d 帧，容器 %.3fs）" % (nb, tl["durationInFrames"], info["duration"]),
    "视频流帧数＝时间线帧数（第 3 轮评审：容器时长被音轨撑长，少 2 帧没查出来）")
add("尺寸帧率", v["w"] == 1080 and v["h"] == 1920 and abs(v["fps"] - FPS) < 0.01, "%dx%d %.2ffps" % (v["w"], v["h"], v["fps"]), "1080×1920 30fps")

# 2 第一帧
g = read_gray_frames(V, 270, 480, FPS)
f0 = g[0] / 255
edge = float((np.abs(np.diff(f0, axis=1)) > 0.04).mean())
add("第一帧是完成画面", f0.mean() > 0.12 and edge > 0.03, "均亮 %.2f 边缘密度 %.3f" % (f0.mean(), edge), "非黑、有字有图")

# 3 冻结：只量画面窗（分带刊物的纸面本来就不动，字幕换字也不算画面在动——思路借自 talk-workbench 的 motion_audit）
LAY = load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "template", "remotion", "src", "packs", "layout.json"))
wx, wy, ww, wh = LAY.get(STYLE, LAY["editorial"])["window"]
y0_, y1_ = int(wy / 1920 * 480), int(min(wy + wh, 1250) / 1920 * 480)  # 满幅版式也排除下部字幕区
g_win = g[:, y0_:y1_, :]
d = np.abs(np.diff(g_win, axis=0)).mean(axis=(1, 2))
# 卡片镜头：卡面本身是给人读的（按设计静止），量「该动的地方」——K 包量讲解人框，A／B／C 量卡片以外的画面窗；
# 有实底卡面的大字卡（K 包）也扣掉卡面（第 6 轮样片：整窗平均把讲解人的动作摊薄成「冻结」）
GEO_ = LAY.get(STYLE, {})
def _mask(rect_win):
    m = np.zeros(g.shape[1:3], bool)
    x, y, w_, h_ = rect_win
    X0, Y0 = int((wx + x) / 1080 * g.shape[2]), int((wy + y) / 1920 * g.shape[1])
    X1, Y1 = int((wx + x + w_) / 1080 * g.shape[2]), int((wy + y + h_) / 1920 * g.shape[1])
    m[max(Y0, 0):Y1, max(X0, 0):X1] = True
    return m
win_m = np.zeros(g.shape[1:3], bool); win_m[y0_:y1_, int(wx / 1080 * g.shape[2]):int((wx + ww) / 1080 * g.shape[2])] = True
for sh in tl["shots"]:
    if sh["type"] == "I":
        m = _mask(GEO_["presenter"]) if GEO_.get("presenter") else (win_m & ~_mask(GEO_["infoCard"]) if GEO_.get("infoCard") else win_m)
    elif sh["type"] == "G" and GEO_.get("figureCard"):
        m = win_m & ~_mask(GEO_["figureCard"])
    else:
        continue
    if m.sum() < 50:
        continue
    a_, b_ = max(sh["from"] - 1, 0), min(sh["to"] - 1, len(d))
    for i_ in range(a_, b_):
        d[i_] = float(np.abs(g[i_ + 1][m] - g[i_][m]).mean())
OUT0 = tl["outro"]["from"] if tl.get("outro") else 10 ** 9  # 落版段按设计是停帧缓推，冻结检查豁免
d = d[:max(OUT0 - 1, 1)]
frz, st = [], None
for i, x in enumerate(d):
    if x < 0.35 and st is None:
        st = i
    elif x >= 0.35 and st is not None:
        if (i - st) / FPS > 0.5:
            frz.append((st / FPS, (i - st) / FPS))
        st = None
if st is not None and (len(d) - st) / FPS > 0.5:
    frz.append((st / FPS, (len(d) - st) / FPS))
tot = sum(x[1] for x in frz)
add("冻结段（只量画面窗）", len(frz) == 0, "%d 处，共 %.1fs %s" % (len(frz), tot, " ".join("%s(%.1fs)" % (hms(s), l) for s, l in frz[:6])),
    "任何静止 ≤0.5s；每 30s 冻结 ≤1s")

# 3b 画面窗空白帧：画面窗里 ≥85% 的行是平的亮纸色＝闪白（第 2 轮评审：升起转场切点帧整窗空白，接缝图跳过了这一帧）
gw = read_gray_frames(V, 135, 240, FPS)
wy0, wy1 = int(wy / 1920 * 240), int(min(wy + wh, 1920) / 1920 * 240)
win_ = gw[:, wy0:wy1, :]
flat = ((win_.mean(axis=2) > 225) & (win_.std(axis=2) < 6)).mean(axis=1)
blank = [i for i, v_ in enumerate(flat) if v_ >= 0.85]
add("画面窗空白帧", not blank, "%d 帧 %s" % (len(blank), " ".join(hms(i / FPS) for i in blank[:6])), "0 帧")

# 4 响度
r = subprocess.run(["ffmpeg", "-hide_banner", "-i", V, "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
tail = r[r.rfind("Summary:"):]
I = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
TP = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1))
add("响度", abs(I + 14) <= 1.0, "%.1f LUFS" % I, "−14 ±1")
add("真峰值", TP <= -1.0, "%.1f dBTP" % TP, "≤ −1 dBTP")
aj = load(P(proj, "qa", "audio.json"), {})
if aj.get("voice_over_music_db_p10") is not None:
    add("配乐不糊人声", aj["voice_over_music_db_p10"] >= 12, "人声频带高出配乐 中位 %.1f / 低10%% %.1f dB" %
        (aj["voice_over_music_db_median"], aj["voice_over_music_db_p10"]), "低 10% ≥12 dB")

# 5 对位
tc = load(P(proj, "work", "transcript_cut.json"))
starts = sorted(int(round(c["s"] * FPS)) for s in tc["sentences"] for c in s["chars"])
edges = sorted(set([s["from"] for s in tl["shots"]] + [s["to"] for s in tl["shots"]]))
# 量的是「字完整可读」的那一帧，不是动画起点（10-22 评审：原来量动画起点，等于假通过）。
# 有入场的卡：遮罩 4 帧揭完；同段换卡与第二行：出现即完整。可读帧比开口早 ≤6 帧、晚 ≤1 帧才算对位
cover_end = 0 if (not tl.get("cover") or tl.get("coverInWindow")) else tl["cover"]["frames"] + tl["cover"]["trans"]
off = []
late_total = 0
for c in tl["captions"]:
    for j, l in enumerate(c["lines"]):
        if c.get("cont") and l["from"] < c["from"]:
            continue
        onset = min(starts, key=lambda x: abs(x - l["from"]))
        if onset < cover_end:
            continue  # 封面停留期间那句不上字幕，按设计豁免
        readable = (c["from"] + 4) if (c.get("animate") and j == 0) else max(l["from"], c["from"])
        dv = readable - onset
        late_total += max(dv, 0)
        if dv > 1 or dv < -6:
            if not any(abs(e - readable) <= 4 for e in edges):
                off.append((readable, l["text"], dv))
add("字幕与语音对位（可读帧）", not off, "%d 行超线 %s；全片字晚于声音合计 %.2fs" % (len(off), " ".join("%s「%s」%+d帧" % (hms(f / FPS), t[:6], dv) for f, t, dv in off[:4]), late_total / FPS),
    "字完整可读的那一帧：比开口早 ≤6 帧、晚 ≤1 帧")
vd = probe(P(proj, "work", "aroll_cut.mp4"))["duration"]
ad = probe(P(proj, "audio", "voice_cut.wav"))["duration"]
add("音画同长（口型）", abs(vd - ad) <= 1 / FPS, "画面 %.3fs 人声 %.3fs" % (vd, ad), "差 ≤1 帧")
# 一张字幕被剪辑点切成几段（后段 cont）时，按整句连续显示多久算
caps_ = tl["captions"]
short = []
for i_, c in enumerate(caps_):
    if c.get("cont"):
        continue
    to_ = c["to"]
    j_ = i_ + 1
    while j_ < len(caps_) and caps_[j_].get("cont") and caps_[j_]["from"] == to_:
        to_ = caps_[j_]["to"]
        j_ += 1
    if (to_ - c["from"]) / FPS < 0.7:
        short.append(c)
add("字幕停留", not short, "%d 张不足 0.7s" % len(short), "每张 ≥0.7s")

# 6 对比度：底板 α 下最坏情况（底下是纯白）
def lum(rgb):
    def ch(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r_, g_, b_ = [ch(x) for x in rgb]
    return 0.2126 * r_ + 0.7152 * g_ + 0.0722 * b_
def contrast(fg, bg):
    l1, l2 = sorted([lum(fg), lum(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)
ink, paper, gold = (13, 18, 22), (245, 240, 230), (232, 194, 127)
worst = {}
for name, alpha in [("字幕底板", 0.72), ("名字条/下期预告", 0.72), ("刊头", 0.72), ("标注签", 0.72)]:
    bg = tuple(alpha * i + (1 - alpha) * 255 for i in ink)
    worst[name] = (contrast(paper, bg), contrast(gold, bg))
_cg = LAY.get(STYLE, {}).get("caption", {})
if _cg.get("mode", "band") == "band":
    _thp = tl.get("theme") or {}
    _paper = tuple(int(_thp.get("paper", "#F3EDE3")[k:k + 2], 16) for k in (1, 3, 5)) if STYLE == "editorial" else (243, 237, 227)
    _acc = tuple(int(_thp.get("accent", "#7F5631")[k:k + 2], 16) for k in (1, 3, 5)) if STYLE == "editorial" else (127, 86, 49)
    worst = {"文字带（墨字／实底）": (contrast((25, 22, 18), _paper), contrast(_acc, _paper))}
low = {k: v for k, v in worst.items() if min(v) < 4.5}
add("文字对比度（理论最坏底）", None if low else True,
    "；".join("%s 白 %.1f 金 %.1f" % (k, v[0], v[1]) for k, v in worst.items()), "底板下面是纯白时的下限，≥4.5:1")

# 实测：在成片帧上取底板内边距里的像素（只有底板、没有字），取 95 分位亮度当「这一帧的最坏底」
def frame_rgb(t):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % t, "-i", V, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(1920, 1080, 3).astype(np.float32) if len(raw) == 1920 * 1080 * 3 else None
def lum_arr(px):
    c = px / 255
    c = np.where(c <= 0.03928, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * c[..., 0] + 0.7152 * c[..., 1] + 0.0722 * c[..., 2]
def cr(fg, lbg):
    lf = lum(fg)
    return (max(lf, lbg) + 0.05) / (min(lf, lbg) + 0.05)
CG = LAY.get(STYLE, {}).get("caption", {"mode": "band", "band": [1420, 1600], "x": 72, "size": 58, "ink": "#191612"})
hx = lambda h: tuple(int(h[k:k + 2], 16) for k in (1, 3, 5))
TH_ = tl.get("theme") or {}
meas = []
if CG["mode"] == "band":
    # 字印在实底的字幕带上（A、K1、K2、K3）：量字幕带里最亮的底与墨字、强调字的对比
    ink_c = hx(CG["ink"])
    acc_c = hx({"editorial": TH_.get("accent", "#7F5631"), "diagram": TH_.get("accent", "#2F5EA7") if TH_.get("custom") else "#2F5EA7",
                "brand": "#B5481A"}.get(STYLE, CG["ink"]))
    b0, b1 = CG["band"]
    for c in tl["captions"]:
        if c.get("cont"):
            continue
        fr_ = frame_rgb(min(c["from"] + 6, c["to"] - 1) / FPS)
        if fr_ is None:
            continue
        px = fr_[b0 + 20:b1 - 10, 72:900].reshape(-1, 3)
        lb = float(np.percentile(lum_arr(px), 99))
        meas.append((c["from"], c["lines"][0]["text"], cr(ink_c, lb), cr(acc_c, lb) if any(l["hl"] for l in c["lines"]) else 99))
else:
    # 字直接落在画面上（B 雾、C 渐隐）：量字行范围里「不是字」的像素（去掉接近字色的亮像素），取 95 分位当最坏底
    fg_c = hx(CG["fg"])
    lfg = lum(fg_c)
    gold_c = hx(TH_.get("dark", "#D8A863"))
    for c in tl["captions"]:
        if c.get("cont"):
            continue
        top = CG["topLow"] if c["variant"] in ("g", "p") else CG["top"]
        y = top
        for l in c["lines"]:
            fr_ = frame_rgb(min(max(c["from"], l["from"]) + 14, c["to"] - 1) / FPS)
            if fr_ is None:
                continue
            n = sum(0.55 if re.match(r"[A-Za-z0-9 ]", ch) else 1 for ch in l["text"])
            w = n * CG["size"]
            x0 = int(540 - w / 2) if CG["align"] == "center" else CG["x"]
            # 字行正上方、正下方各一条 6px 的窄带（没有字形），量底的亮度
            xa, xb = max(x0, 0), min(int(x0 + w), 1080)
            lh = CG["size"] * 1.38
            # 只取第一行上方、最后一行下方（两行之间那条会碰到下一行的字）；离开行框 12px，C 的关键词放大 1.22 倍会伸出行框
            li_ = c["lines"].index(l)
            strips = ([fr_[max(int(y) - 18, 0):max(int(y) - 12, 0), xa:xb]] if li_ == 0 else []) + \
                     ([fr_[int(y + lh) + 12:int(y + lh) + 18, xa:xb]] if li_ == len(c["lines"]) - 1 else [])
            px = np.concatenate([st_.reshape(-1, 3) for st_ in strips if st_.size])
            if px.size < 150:
                continue
            lb = float(np.percentile(lum_arr(px), 95))
            meas.append((c["from"], l["text"], cr(fg_c, lb), cr(gold_c, lb) if l["hl"] else 99))
            y += CG["size"] * 1.38
mh = []
for s_ in ([x for x in range(15, tl["durationInFrames"], 60)] if STYLE == "glass" else []):
    host = next((x for x in tl["shots"] if x["from"] <= s_ < x["to"]), None)
    if (host and (host["type"] in ("B", "S") or (host["type"] == "G" and host.get("bg")))) or \
            (tl.get("cover") and s_ < tl["cover"]["frames"]):
        continue
    fr_ = frame_rgb(s_ / FPS + 0.01)
    if fr_ is None or not tl.get("masthead"):
        continue
    hair = max((fr_[y, 520:560].mean(0) for y in range(354, 364)), key=lambda v: v[0])
    if not (hair[0] > 150 and hair[0] > hair[2] + 40):  # 刊头底部金线不在＝这一帧没有刊头
        continue
    px = np.concatenate([fr_[160:376, 8:52].reshape(-1, 3), fr_[160:376, 1028:1072].reshape(-1, 3)])
    mh.append(float(np.percentile(lum_arr(px), 95)))
mins = []
if meas:
    mw = min(meas, key=lambda x: x[2])
    mg = min(meas, key=lambda x: x[3])
    mins += [mw[2], mg[3]]
    got = "字幕 白字最低 %.1f（%s「%s」）金字最低 %.1f" % (mw[2], hms(mw[0] / FPS), mw[1][:6], mg[3] if mg[3] < 99 else float("nan"))
else:
    got = "无字幕"
if mh:
    lb = max(mh)
    mins += [cr(paper, lb), cr(gold, lb)]
    got += "；刊头 白 %.1f 金 %.1f" % (cr(paper, lb), cr(gold, lb))
add("文字对比度（成片实测）", min(mins) >= 4.5 if mins else None, got, "≥4.5:1")

# 7 安全区：按字数估宽
over = []
SIZE = {"a": 56, "p": 54, "g": 52, "b": 58, "band": 56}  # 与 Caption.tsx 的 STYLE 同步
for c in tl["captions"]:
    for l in c["lines"]:
        n = sum(0.55 if re.match(r"[A-Za-z0-9 ]", ch) else 1 for ch in l["text"])
        cg_ = LAY.get(STYLE, {}).get("caption", {})
        if cg_.get("mode", "band") == "band":
            right = cg_.get("x", 72) + n * cg_.get("size", 58)
        elif cg_.get("align") == "left":
            right = cg_.get("x", 98) + n * cg_.get("size", 58) * 1.08   # C 的关键词放大 1.22 倍，整行按 1.08 估
        else:
            right = 540 + n * cg_.get("size", 52) / 2
        if right > 940:
            over.append((c["from"], l["text"], int(right)))
add("安全区（右侧互动栏 x≤940）", not over, "%d 行越界 %s" % (len(over), " ".join("「%s」→%d" % (t[:6], x) for _, t, x in over[:4])), "字幕右沿 ≤940")

# 8 屏上文字出处
facts = load(P(proj, "facts.json"), {"claims": []})
known = set()
for cl in facts.get("claims", []):
    known.add(cl.get("text", ""))
design = set(facts.get("design_labels", []))
screen = []
if tl.get("masthead"):
    screen += [tl["masthead"]["series"], tl["masthead"]["episode"]]
if tl.get("cover"):
    screen += tl["cover"]["title"] + [tl["cover"]["kicker"], tl["cover"]["sub"]]
if tl.get("nametag"):
    screen += [tl["nametag"]["name"]] + tl["nametag"]["lines"]
if tl.get("end"):
    screen += [tl["end"]["kicker"], tl["end"]["line"], tl["end"]["cta"]]
screen += [t["text"] for t in tl.get("tags", [])]
for s in tl["shots"]:
    if s.get("figure"):
        screen += [str(s["figure"].get("value", "")) + str(s["figure"].get("unit", "")), s["figure"].get("label", "")]
cv = tl.get("cover") or {}
if cv.get("form") == "number" and cv.get("number"):
    screen.append(str(cv["number"].get("value", "")) + str(cv["number"].get("unit", "")))
if cv.get("form") == "versus" and cv.get("versus"):
    screen += ["%s %s" % (cv["versus"][k].get("label", ""), cv["versus"][k].get("value", "")) for k in ("left", "right") if cv["versus"].get(k)]
if cv.get("form") == "quote" and cv.get("quote"):
    screen.append(cv["quote"].get("text", ""))
miss = [t for t in screen if t and t not in known and t not in design]
# 信息卡：一张卡在 facts.cards 里登记一次（来源、原话还是转述、数字从哪来），不逐字登记
cards = facts.get("cards", {})
miss += ["信息卡 %s" % s["id"] for s in tl["shots"] if s["type"] == "I" and s["id"] not in cards]
add("屏上文字有出处", not miss, "%d 条没登记：%s" % (len(miss), "、".join(miss[:8])), "facts.json 里逐条有原句或链接；字幕＝口播原话")

# 8a 账号主题对比度：纸上强调字对纸 ≥4.5:1；页脚对平台白字 ≥12:1
def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
def _cr(a, b):
    la, lb = sorted([_lum(a), _lum(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)
th = tl.get("theme") or {}
if th.get("paper") and th.get("accent") and th.get("foot"):
    c1, c2 = _cr(th["accent"], th["paper"]), _cr("#FFFFFF", th["foot"])
    add("账号主题对比度（%s）" % th.get("name", ""), c1 >= 4.5 and c2 >= 12, "强调字对纸 %.1f:1｜页脚对白字 %.1f:1" % (c1, c2), "≥4.5:1｜≥12:1")

# 8b 大字卡完整可读时长：字落下（开口帧＋6 帧扫开）到下一镜，≥1.3s（第 3 轮评审：量在屏时长会骗人）
fig_short = []
for s_ in tl["shots"]:
    if s_["type"] == "G" and s_.get("figure", {}).get("revealFrom") is not None:
        rd = s_["to"] - (s_["figure"]["revealFrom"] + 6)
        if rd < 39:
            fig_short.append("%s %.2fs" % (s_["id"], rd / FPS))
add("大字卡完整可读", not fig_short, "；".join(fig_short) or "全部 ≥1.3s", "≥1.3s")
# 8c 人脸碎片：两个镜头之间、或跳切后只剩 ≤6 帧的人脸
cov_ = sorted((x["from"], x["to"]) for x in tl["shots"])
gaps_, cur_ = [], 0
for a0, a1 in cov_:
    if a0 > cur_:
        gaps_.append((cur_, a0))
    cur_ = max(cur_, a1)
edges_jc = [int(round(t * FPS)) for t in load(P(proj, "work", "edl.json")).get("jump_cuts", [])]
frag = []
for g0, g1 in gaps_:
    pts = [g0] + [c for c in edges_jc if g0 < c < g1] + [g1]
    for b0, b1 in zip(pts[:-1], pts[1:]):
        if 0 < b1 - b0 <= 6 and b0 > 0:
            frag.append("%s(%d帧)" % (hms(b0 / FPS), b1 - b0))
add("人脸碎片（≤6 帧）", not frag, "%d 处 %s" % (len(frag), " ".join(frag[:6])), "0 处")

# 8d B-roll 归一化片段的重复帧（第 4 轮评审：25fps 素材每 6 帧重复 1 帧，成片验收没抓到）
dup_bad, pop_bad = [], []
for s_ in tl["shots"]:
    for clip_ in [s_.get("clip"), s_.get("bg"), (s_.get("split") or {}).get("clip")]:
        if not clip_:
            continue
        cp = P(proj, "remotion", "public", clip_)
        if not os.path.exists(cp):
            continue
        raw_ = subprocess.run(["ffmpeg", "-v", "error", "-i", cp, "-vf", "scale=96:96,format=gray", "-f", "rawvideo", "-"], capture_output=True).stdout
        a_ = np.frombuffer(raw_, np.uint8).reshape(-1, 96, 96).astype(np.float32)
        if len(a_) < 10:
            continue
        dd = np.abs(np.diff(a_, axis=0)).mean(axis=(1, 2))
        med = float(np.median(dd))
        n_dup = int(((dd < 0.08) & (med > 0.4)).sum())  # 画面本身在动、却有帧完全没变＝重复帧
        if n_dup >= 3:
            dup_bad.append("%s %d帧" % (os.path.basename(clip_), n_dup))
        # 镜头内部亮度一帧跳 ≥5 级（素材自带的自动曝光跳变，第 5 轮评审：走廊「闪了两下」）
        dm = np.diff(a_.mean(axis=(1, 2)))
        jumps = [i + 1 for i in range(len(dm)) if abs(dm[i]) >= 5 and np.median(np.abs(dm[max(0, i - 6):i + 7])) < 1.5]
        if jumps:
            pop_bad.append("%s 第%s帧" % (os.path.basename(clip_), "、".join(map(str, jumps[:4]))))
add("B-roll 重复帧", not dup_bad, "；".join(dup_bad) or "0", "0（24/25fps 必须逐帧铺进 30fps）")
add("B-roll 内部亮度跳变", not pop_bad, "；".join(pop_bad) or "0", "0（一帧亮度跳 ≥5 级＝素材自带曝光跳，换段或换素材）")

# 8d-1 B-roll 亮度下限（10-27：星轨镜头 YAVG 27.8、近黑 4.97s，25 项全部通过没拦住）
# 判据：每条 B／S 片段在画面窗里的平均亮度 ≥55，且不低于本片人脸镜平均亮度的 0.5 —— 低于这条就是暗部没信息
face_lum = None
_av = P(proj, "work", "aroll_cut.mp4")
if os.path.exists(_av):
    raw_ar = subprocess.run(["ffmpeg", "-v", "error", "-i", _av, "-vf", "fps=2,scale=96:96,format=gray", "-f", "rawvideo", "-"],
                            capture_output=True).stdout
    if raw_ar:
        face_lum = float(np.frombuffer(raw_ar, np.uint8).mean())
dark_bad = []
if face_lum:
    for s_ in tl["shots"]:
        if s_["type"] not in ("B", "S"):
            continue
        for clip_ in [s_.get("clip"), (s_.get("split") or {}).get("clip")]:
            if not clip_:
                continue
            cp = P(proj, "remotion", "public", clip_)
            if not os.path.exists(cp):
                continue
            raw_ = subprocess.run(["ffmpeg", "-v", "error", "-i", cp, "-vf", "scale=96:96,format=gray", "-f", "rawvideo", "-"],
                                  capture_output=True).stdout
            if not raw_:
                continue
            m = float(np.frombuffer(raw_, np.uint8).mean())
            if m < max(55.0, face_lum * 0.50):
                dark_bad.append("%s %.0f（人脸 %.0f）" % (os.path.basename(clip_), m, face_lum))
add("B-roll 亮度下限", not dark_bad, "；".join(dark_bad) or "0", "每条 ≥55 且 ≥ 人脸镜平均亮度 ×0.5（暗部还要有信息）")

# 8d-2 B-roll 里有没有可读文字（10-27：1941 年华盛顿首日封「WASHINGTON JUN 25 1941」满屏可读，自动验收全过）
# macOS Vision OCR，只报 ≥4 个字且置信度 ≥0.5 的块；镜头写 text_ok: true 可豁免（例如招牌本来就要露）
txt_bad, txt_skip = [], []
text_bin = os.path.expanduser("~/.cache/ifa-koubo/text")
if not os.path.exists(text_bin):
    # 首次跑 qa 时顺手编译（setup.sh 也会编；非 macOS 没有 swiftc，编译失败就跳过这一项）
    os.makedirs(os.path.dirname(text_bin), exist_ok=True)
    _sk = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run(["swiftc", "-O", os.path.join(_sk, "scripts", "text.swift"), "-o", text_bin], capture_output=True)
if os.path.exists(text_bin):
    import tempfile
    tmpd = tempfile.mkdtemp(prefix="qa_ocr_")
    jobs = []
    for s_ in tl["shots"]:
        if s_["type"] not in ("B", "S") or s_.get("text_ok"):
            if s_["type"] in ("B", "S") and s_.get("text_ok"):
                txt_skip.append(s_["id"])
            continue
        for clip_ in [s_.get("clip"), (s_.get("split") or {}).get("clip")]:
            if not clip_:
                continue
            cp = P(proj, "remotion", "public", clip_)
            if not os.path.exists(cp):
                continue
            dur_ = max(probe(cp)["duration"], 0.2)
            for pct in (0.15, 0.5, 0.85):
                nm = "%s@%02d.jpg" % (s_["id"], int(pct * 100))
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % (dur_ * pct), "-i", cp, "-frames:v", "1",
                                "-vf", "scale=540:-2", os.path.join(tmpd, nm)], capture_output=True)
                jobs.append((s_["id"], nm))
    if jobs:
        r_ = subprocess.run([text_bin, tmpd], capture_output=True, text=True)
        try:
            ocr = json.loads(r_.stdout or "{}")
        except Exception:
            ocr = {}
        per = {}
        for sid, nm in jobs:
            for h in ocr.get(nm, []) or []:
                per.setdefault(sid, [])
                t = str(h.get("t", ""))[:14]
                if t and t not in per[sid]:
                    per[sid].append(t)
        for sid, ts_ in per.items():
            if ts_:
                txt_bad.append("%s「%s」" % (sid, "/".join(ts_[:3])))
    add("B-roll 可读文字", None if txt_bad else True, "；".join(txt_bad) or ("0" + ("（豁免 %s）" % "、".join(txt_skip) if txt_skip else "")),
        "画面里的字要和屏上的事实一致：报了就去核，确认是本意就在 decompose 该镜写 text_ok: true")
else:
    add("B-roll 可读文字", None, "跳过：没有 Vision OCR（非 macOS 或编译失败）", "macOS 上跑 setup.sh 会编译 scripts/text.swift")


# 8e 片尾杂音：最后一个字之后人声轨不应再有瞬态（第 3、4 轮评审：她伸手点停止键的「咔」）
last_end_ = max(c["e"] for s__ in tc["sentences"] for c in s__["chars"])
va = read_gray_frames  # 占位，避免未用导入告警
raw_a = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.3f" % (last_end_ + 0.15), "-i", P(proj, "audio", "voice_cut.wav"), "-ac", "1", "-ar", "16000",
                        "-f", "s16le", "-"], capture_output=True).stdout
if raw_a:
    xa = np.frombuffer(raw_a, np.int16).astype(np.float32) / 32768
    pk = 20 * np.log10(np.abs(xa).max() + 1e-9)
    add("片尾杂音", pk <= -30, "最后一个字后人声轨峰值 %.1f dBFS" % pk, "≤ −30 dBFS")

# 9 节奏与占比
NF = tl["durationInFrames"]
cov = np.zeros(NF, bool)
for s in tl["shots"]:
    cov[s["from"]:s["to"]] = True
zoom_cuts = set(z["from"] for z in tl.get("arollZoom", []))
runs, cur = [], 0
for i in range(NF):
    if not cov[i] and i not in zoom_cuts:
        cur += 1
    else:
        if cur:
            runs.append(cur)
        cur = 0 if cov[i] else 1
if cur:
    runs.append(cur)
mx = max(runs) / FPS if runs else 0
bl = [(s["to"] - s["from"]) / FPS for s in tl["shots"] if s["type"] in ("B", "S")]
share_a = 1 - cov.mean()
add("人脸同一景别最长", mx <= 8.5, "%.1fs" % mx, "≤8.5s")
add("B-roll 单条长度", all(1.5 <= x <= 6.5 for x in bl) if bl else None, "%.1f–%.1fs" % (min(bl), max(bl)) if bl else "无", "1.6–6.5s")
add("人脸占比", 0.35 <= share_a <= 0.6, "%.0f%%" % (share_a * 100), "35–60%（参考片 44%）")

# 10 近空画面（父 skill 的 qa_edge，混合素材用绝对阈值）
qe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qa_edge.py")  # 本 skill 自带一份，移植时不依赖父 skill
if os.path.exists(qe):
    out = subprocess.run([sys.executable, qe, V, "--abs", "0.016"], capture_output=True, text=True).stdout
    m_ = re.search(r"近空画面（连续 ≥0.2s）：(\d+) 处", out)
    n_ = int(m_.group(1)) if m_ else -1
    add("近空画面（qa_edge）", n_ == 0, "%d 处" % n_, "0 处")

# 抽帧图：静音解读（每秒 2 帧）与 16 帧总览
from PIL import Image, ImageDraw
def sheet(fps_, w, cols, path, label=True):
    tmp = P(proj, "qa", "_sheet")
    os.makedirs(tmp, exist_ok=True)
    for f in os.listdir(tmp):
        os.remove(os.path.join(tmp, f))
    run(["ffmpeg", "-v", "error", "-y", "-i", V, "-vf", "fps=%s,scale=%d:-2" % (fps_, w), os.path.join(tmp, "f%04d.jpg")])
    fs = sorted(os.listdir(tmp))
    h = Image.open(os.path.join(tmp, fs[0])).height
    img = Image.new("RGB", (cols * w, ((len(fs) + cols - 1) // cols) * (h + 22)), (12, 12, 12))
    dr = ImageDraw.Draw(img)
    for i, f in enumerate(fs):
        x0, y0 = (i % cols) * w, (i // cols) * (h + 22)
        img.paste(Image.open(os.path.join(tmp, f)), (x0, y0))
        if label:
            dr.text((x0 + 4, y0 + h + 3), hms(i / float(eval(str(fps_)))), fill=(200, 200, 200), font=font(15))
    img.save(path, quality=80)
sheet(2, 120, 20, P(proj, "out", "抽帧_每秒2帧.jpg"))
sheet("16/%.3f" % info["duration"], 270, 8, P(proj, "out", "抽帧_16帧.jpg"))

bad = [r_ for r_ in rows if r_[1] == "❌"]
md = ["# 验收报告", "", "成片：`%s`" % os.path.relpath(V, proj), "", "| 项 | 结果 | 实测 | 线 |", "|---|---|---|---|"]
md += ["| %s | %s | %s | %s |" % r_ for r_ in rows]
md += ["", "不过线 %d 项。需要人亲眼看、亲耳听的见 references/06 §四。" % len(bad),
       "抽帧图：`out/抽帧_每秒2帧.jpg`（静音解读用）、`out/抽帧_16帧.jpg`（交付缩略图）"]
REP = "qa_report.md" if not a.video else "qa_report_%s.md" % os.path.splitext(os.path.basename(V))[0]
open(P(proj, "qa", REP), "w", encoding="utf-8").write("\n".join(md) + "\n")
for r_ in rows:
    print("%s %s：%s" % (r_[1], r_[0], r_[2]))
print("→ qa/" + REP)
