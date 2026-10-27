#!/usr/bin/env python3
"""风格确认：用这条片子自己的素材，在六套风格包里各渲 4 帧，拼成一张选择单，让人挑。

    python3 style_pick.py <工程目录> [--packs A,B,C,K1,K2,K3] [--theme 维港青]

为什么要用「自己的素材」而不是示范内容：`gallery.py` 用的是选题库的示范文案，人看到的是别人的话；
风格要贴着这条片子的脸、字、数字来选，所以这里直接拿本工程已 build 的时间线，只换风格包渲同一批帧。

前提：工程已经 build 过一次（有 timing.json、aroll_cut.mp4 与归一化好的 clips）。
产物：out/风格目录/<代号>.jpg（每套 4 帧）、out/风格目录/选择单.jpg、out/风格目录/选择单.md
注意：会临时改写 remotion/src/timeline.json，做完自动恢复原时间线（不用重跑 build）。

判断依据见 references/04 §〇「内容 → 风格包」；每套的分值来自 suggest_style.py。
"""
import argparse, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, load, save, die

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--packs", default="A,B,C,K1,K2,K3")
ap.add_argument("--theme", default="", help="给能换色的包套一个账号主题看效果（已经写在时间线里的主题会被覆盖）")
ap.add_argument("--reuse", action="store_true", help="已经渲过的风格帧直接复用，不重新渲染（只重拼选择单）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
R = P(proj, "remotion")
TL_P = P(R, "src", "timeline.json")
if not os.path.exists(TL_P) or not os.path.exists(P(proj, "timing.json")):
    die("先对这个工程跑一次 build.py（要借它已经归一化好的素材与时间线）")
base = load(TL_P)
ALIAS = {"A": "editorial", "B": "glass", "C": "kinetic", "K1": "evidence", "K2": "diagram", "K3": "brand"}
NAMES = {"A": "A 分带刊物", "B": "B 雾金玻璃", "C": "C 港刊大字", "K1": "K1 证据桌", "K2": "K2 图解", "K3": "K3 IFA 品牌刊"}
ONE = {
    "A": "上刊头、中画面窗、下字幕带，字永远不压画面",
    "B": "满幅实拍＋雾＋液态玻璃，字压在雾上",
    "C": "满幅＋书脊线＋宋体大字，字就是版面",
    "K1": "桌面纸纹、撕边剪报、荧光笔，原文当证据摆上来",
    "K2": "网格＋柱图从 0 起＋图号来源，数字拿走舞台",
    "K3": "和 IFA 小红书图文卡同一套渐变与 logo",
}
GOOD = {
    "A": "个人近况、生活、经历",
    "B": "活动、开业、品牌宣传",
    "C": "热点、观点、金句",
    "K1": "政策、新闻、报告原文",
    "K2": "数字、对比、清单",
    "K3": "平台、招募、团队",
}
COST = {
    "A": "画面窗只占 58% 高，脸会比满幅小",
    "B": "满幅会露出原片底部的桌面杂物；雾会压掉一点脸部细节",
    "C": "满幅＋大字，信息靠字幕，数字多时不好承载",
    "K1": "每张卡都要出处，没有原文就只能放泛指标签",
    "K2": "冷；没有数字的片子会显得在硬撑",
    "K3": "锁品牌色，账号之间分不开",
}
LAYOUT = load(P(R, "src", "packs", "layout.json"))

# ---------- 选帧：人脸＋名字条 / B-roll / 大字卡 / 信息卡（没有就退到照片卡、再退到人脸） ----------
cap0 = min((c["from"] for c in base.get("captions") or [base["durationInFrames"] // 3]), default=90)
other = [s for s in base["shots"] if s["type"] != "I"]
fB = next(((s["from"] + s["to"]) // 2 for s in other if s["type"] in ("B", "S")), cap0 + 90)
G = next((s for s in base["shots"] if s["type"] == "G"), None)
fG = ((G.get("figure") or {}).get("revealFrom", G["from"]) + 22) if G else fB + 90
I = next((s for s in base["shots"] if s["type"] == "I"), None) or next((s for s in base["shots"] if s["type"] == "P"), None)
fI = (I["from"] + I["to"]) // 2 if I else fG + 90
fA = max(cap0 + 20, 84)
stills = [fA, fB, fG, fI]
LABELS = ["人脸＋刊头＋字幕", "B-roll＋字幕", "大字／数字卡", "信息卡" if I and I["type"] == "I" else "照片卡／字幕"]

# ---------- 适配分：直接问 suggest_style ----------
score, why = {}, {}
try:
    out = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "suggest_style.py"), proj],
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        m = re.match(r"^\s{2}([A-Z0-9]{1,2})\s+\S.*?\s+([\d.]+)　(.*)$", line)
        if m and m.group(1) in NAMES:
            score[m.group(1)] = float(m.group(2))
            why[m.group(1)] = m.group(3)
except Exception:
    pass

# ---------- 渲：每套换 style 渲同一批帧 ----------
outdir = P(proj, "out", "风格目录")
os.makedirs(outdir, exist_ok=True)
codes = [c.strip() for c in a.packs.split(",") if c.strip()]
orig = open(TL_P, encoding="utf-8").read()
try:
    for code in codes:
        have = [P(outdir, "%s_%d%s.jpg" % (code, i + 1, n)) for i, n in enumerate(["人脸", "broll", "大字卡", "信息卡"])]
        if a.reuse and all(os.path.exists(x) for x in have):
            print("· %s 复用已有风格帧" % NAMES[code])
            continue
        style = ALIAS[code]
        tl = dict(base)
        tl["style"] = style
        tl["coverInWindow"] = bool(LAYOUT.get(style, {}).get("coverInWindow", True))
        if a.theme:
            th = load(P(R, "src", "packs", "themes.json")).get(a.theme)
            if th:
                tl["theme"] = dict(th, name=a.theme, custom=True)
        save(TL_P, tl)
        st = P(proj, "out", "stills")
        shutil.rmtree(st, ignore_errors=True)
        r = subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "render.py"), proj,
                            "--stills", ",".join(map(str, stills))], capture_output=True, text=True)
        if r.returncode != 0:
            die("渲 %s 失败：%s" % (code, (r.stderr or r.stdout)[-600:]))
        ims = [P(st, "f%05d.jpg" % f) for f in stills]
        if not all(os.path.exists(x) for x in ims):
            die("渲 %s 缺少风格帧：%s" % (code, ims))
        shutil.copy(ims[0], P(outdir, "%s_1人脸.jpg" % code))
        shutil.copy(ims[1], P(outdir, "%s_2broll.jpg" % code))
        shutil.copy(ims[2], P(outdir, "%s_3大字卡.jpg" % code))
        shutil.copy(ims[3], P(outdir, "%s_4信息卡.jpg" % code))
        print("✓ %s → out/风格目录/%s_*.jpg" % (NAMES[code], code))
finally:
    open(TL_P, "w", encoding="utf-8").write(orig)
    shutil.rmtree(P(proj, "out", "stills"), ignore_errors=True)

# ---------- 拼选择单 ----------
from PIL import Image, ImageDraw, ImageFont
fnt = ImageFont.truetype(os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-Heavy.otf"), 46)
fsm = ImageFont.truetype(os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-SemiBold.otf"), 28)
fmn = ImageFont.truetype(os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-SemiBold.otf"), 24)
CW, CH, PADX, TOP, GAPX, GAPY = 300, 533, 24, 132, 16, 26
rows = []
for code in codes:
    files = [P(outdir, "%s_%d%s.jpg" % (code, i + 1, n)) for i, n in enumerate(["人脸", "broll", "大字卡", "信息卡"])]
    row = Image.new("RGB", (PADX * 2 + CW * 4 + GAPX * 3, TOP + CH + GAPY), "#141414")
    d = ImageDraw.Draw(row)
    sc = ("　适配 %.1f" % score[code]) if code in score else ""
    d.text((PADX, 18), NAMES[code] + sc, fill="#F3EDE3", font=fnt)
    d.text((PADX, 74), ONE[code], fill="#C9A46A", font=fsm)
    for i, f_ in enumerate(files):
        if not os.path.exists(f_):
            continue
        im = Image.open(f_).convert("RGB").resize((CW, CH), Image.LANCZOS)
        row.paste(im, (PADX + i * (CW + GAPX), TOP))
    rows.append((code, row))
W = max(r.width for _, r in rows)
sheet = Image.new("RGB", (W, sum(r.height for _, r in rows) + 60), "#141414")
y = 0
for _, r in rows:
    sheet.paste(r, (0, y))
    y += r.height
ImageDraw.Draw(sheet).text((PADX, y + 12), "同一条片子、同一批帧，只换风格包。素材按 %s 的画面窗归一化，满幅包会放大一点，看版式与字，不看清晰度。" % "A",
                           fill="#8A8A8A", font=fmn)
sheet.save(P(outdir, "选择单.jpg"), quality=88)
print("✓ 选择单 → out/风格目录/选择单.jpg")

# ---------- 选择单.md：给人和 AI 都能用的一页 ----------
lines = ["# 风格选择单（这一条片子自己的素材）", "",
         "同一批帧（%s 秒）在六套风格包里各渲一次，只换风格包。判断依据：%s。" % (", ".join("%.1f" % (f / 30) for f in stills), "references/04 §〇"),
         "", "| 代号 | 风格包 | 一句话 | 适合 | 本片适配分 | 代价 |", "|---|---|---|---|---|---|"]
for code in codes:
    lines.append("| %s | %s | %s | %s | %s | %s |" % (code, NAMES[code], ONE[code], GOOD[code],
                                                     ("%.1f" % score[code]) if code in score else "—", COST[code]))
lines += ["", "图：`选择单.jpg`（整张）、`<代号>_1人脸.jpg` … `<代号>_4信息卡.jpg`（单帧原图，可放大看字）。", "",
          "**怎么回**：回一个代号即可（例：`K1`）；也可以补一句调整（例：`A，字幕再小一点`）。不回＝用推荐第一名。"]
open(P(outdir, "选择单.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")

best = max(codes, key=lambda c: score.get(c, 0)) if score else codes[0]
print("\n" + "=" * 56)
print("请挑一套风格（回一个代号就行）：")
for code in codes:
    star = "★ 推荐" if code == best else ""
    print("  %-3s %-12s %-6s %s" % (code, NAMES[code], ("%.1f" % score[code]) if code in score else "", star))
print("  不回的默认：%s（%s）" % (best, why.get(best, GOOD[best])))
print("=" * 56)
print("拿定主意后：把代号写进 decompose.json 的 style，再跑 build.py（或 make.py）。")
