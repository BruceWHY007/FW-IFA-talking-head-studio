#!/usr/bin/env python3
"""风格目录：同一份示范内容，在六套风格包里各渲一组关键帧，拼成一张对比图，给人挑风格用。

    python3 gallery.py <工程目录> [--packs A,B,C,K1,K2,K3] [--sample 示范内容.json] [--theme 维港青]

需要一个已经 build 过的工程（借它剪好的人脸原片）。示范内容默认是 template/gallery_sample.json（选题库 05）。
产物：out/风格目录/<代号>.jpg（每套 8 帧）与 out/风格目录/总览.jpg。
注意：会改写工程里的 timeline.json 与字体子集，做完目录后重跑 build.py（或 make.py）恢复成片的时间线。
"""
import argparse, base64, json, os, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, run, load, save, die

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--packs", default="A,B,C,K1,K2,K3")
ap.add_argument("--sample", default=os.path.join(SKILL, "template", "gallery_sample.json"))
ap.add_argument("--theme", default="", help="给能换色的包（A／B／C／K2）套一个账号主题看效果")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
R = P(proj, "remotion")
if not os.path.exists(P(R, "public", "aroll_cut.mp4")):
    die("先对这个工程跑一次 build.py（目录要借剪好的人脸原片）")
ALIAS = {"A": "editorial", "B": "glass", "C": "kinetic", "K1": "evidence", "K2": "diagram", "K3": "brand"}
NAMES = {"A": "A 分带刊物", "B": "B 雾金玻璃", "C": "C 港刊大字", "K1": "K1 证据桌", "K2": "K2 图解", "K3": "K3 IFA 品牌刊"}
sm = load(a.sample)
base_tl = load(P(R, "src", "timeline.json"))
THEMES = {k: v for k, v in load(P(R, "src", "packs", "themes.json")).items() if not k.startswith("_")}
theme = dict(THEMES[a.theme], name=a.theme, custom=True) if a.theme else dict(THEMES["琥珀金"], name="琥珀金", custom=False)

# ---- 时间表：封面 0–72，人脸＋名字条 72–200，然后每张信息卡 110 帧，最后一张大字卡 ----
SEG = 110
shots, caps, stills = [], [], [30, 150]
def cap(f0, f1, text, hl=None):
    ln = {"text": text, "from": f0, "hl": [], "hlAt": []}
    if hl and hl in text:
        k = text.index(hl)
        ln["hl"], ln["hlAt"] = [[k, k + len(hl)]], [f0 + 8]
    caps.append({"from": f0, "to": f1, "variant": "a", "cont": False, "animate": True, "lines": [ln]})
cap(0, 100, sm["captions"][0])
cap(100, 200, sm["captions"][1], "BCG")
t = 200
for n, c in enumerate(sm["cards"]):
    info = {k: v for k, v in c.items() if k != "caption"}
    for i, it in enumerate(info.get("items") or info.get("groups") or []):
        it["revealAt"] = t + 8 + i * 14
    if info.get("kind") == "quote" and info.get("hl"):
        k = info["text"].find(info["hl"])
        info["hl"] = [k, k + len(info["hl"])] if k >= 0 else None
        info["hlAt"] = t + 18
    shots.append({"id": "I%d" % (n + 1), "type": "I", "from": t, "to": t + SEG, "push": 1, "move": "push", "info": info})
    cap(t, t + SEG, c.get("caption", ""))
    stills.append(t + SEG - 6)
    t += SEG
fig = dict(sm["figure"], revealFrom=t + 6)
shots.append({"id": "G1", "type": "G", "from": t, "to": t + 80, "push": 1, "move": "push", "figure": fig})
cap(t, t + 80, sm.get("figure_caption", ""))
stills.append(t + 70)
DUR = t + 80

texts = [sm["masthead"]["series"], sm["masthead"]["episode"], sm["speaker"]["name"]] + sm["speaker"]["lines"] + \
    [json.dumps(sm, ensure_ascii=False)] + ["来源 · 下期预告 vs “”示意画面"]
used = "".join(sorted(set("".join(texts)))) + "0123456789，。、！？：；“”（）·—…%+-ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz "
open(P(proj, "work", "used_chars_gallery.txt"), "w", encoding="utf-8").write(used)
for wt in ("Heavy", "SemiBold"):
    run([sys.executable, "-m", "fontTools.subset", os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-%s.otf" % wt),
         "--text-file=" + P(proj, "work", "used_chars_gallery.txt"), "--output-file=" + P(R, "public", "fonts", "SHSerif-%s.otf" % wt),
         "--layout-features=*", "--no-hinting"])
fd = {k: base64.b64encode(open(P(R, "public", "fonts", f), "rb").read()).decode()
      for k, f in [("SHSerif-Heavy", "SHSerif-Heavy.otf"), ("SHSerif-SemiBold", "SHSerif-SemiBold.otf"), ("BodoniModa", "BodoniModa.ttf")]}
open(P(R, "src", "fontdata.ts"), "w").write("export const FONT_DATA: Record<string, string> = " + json.dumps(fd) + ";\n")

outdir = P(proj, "out", "风格目录")
os.makedirs(outdir, exist_ok=True)
codes = [c.strip() for c in a.packs.split(",") if c.strip()]
from PIL import Image, ImageDraw, ImageFont
fnt = ImageFont.truetype(os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-Heavy.otf"), 44)
fsm = ImageFont.truetype(os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-SemiBold.otf"), 26)
LABELS = ["封面", "人脸＋名字条", "原文要点", "两边对比", "柱图", "几件事", "时间线", "大字卡"]
rows = []
for code in codes:
    style = ALIAS[code]
    cv = dict(sm["cover"], frames=60, trans=12, sub="", scale=1.12, form=sm.get("cover_forms", {}).get(code, "title"))
    tl = {"fps": 30, "width": 1080, "height": 1920, "durationInFrames": DUR, "style": style, "outro": None,
          "coverInWindow": style not in ("glass", "kinetic"), "theme": theme, "account": "",
          "aroll": base_tl["aroll"], "shots": shots, "arollZoom": [], "captions": caps, "masthead": sm["masthead"],
          "nametag": {"from": 80, "to": 200, "name": sm["speaker"]["name"], "latin": "", "lines": sm["speaker"]["lines"]},
          "cover": cv, "end": None, "tags": [], "sfx": [], "chapters": [], "emph": []}
    save(P(R, "src", "timeline.json"), tl)
    st = P(proj, "out", "stills")
    shutil.rmtree(st, ignore_errors=True)
    run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "render.py"), proj, "--stills", ",".join(map(str, stills))])
    ims = [Image.open(P(st, "f%05d.jpg" % fr)).convert("RGB").resize((270, 480), Image.LANCZOS) for fr in stills]
    row = Image.new("RGB", (len(ims) * 286 + 16, 480 + 120), "#161616")
    d = ImageDraw.Draw(row)
    d.text((16, 14), NAMES[code], fill="#F3EDE3", font=fnt)
    for i, im in enumerate(ims):
        row.paste(im, (16 + i * 286, 80))
        d.text((16 + i * 286, 568), LABELS[i] if i < len(LABELS) else "", fill="#C9A46A", font=fsm)
    row.save(P(outdir, "%s.jpg" % code), quality=90)
    rows.append(row)
    print("✓ %s → out/风格目录/%s.jpg" % (NAMES[code], code))
# 总览按 A→K3 的顺序拼目录里已有的每一套（只补渲几套时，其余沿用上次的图）
rows = [Image.open(P(outdir, "%s.jpg" % c)) for c in ["A", "B", "C", "K1", "K2", "K3"] if os.path.exists(P(outdir, "%s.jpg" % c))]
W = max(r.width for r in rows)
sheet = Image.new("RGB", (W, sum(r.height for r in rows)), "#161616")
y = 0
for r in rows:
    sheet.paste(r, (0, y)); y += r.height
sheet.save(P(outdir, "总览.jpg"), quality=88)
print("✓ 总览 → out/风格目录/总览.jpg　（目录做完了：重跑 build.py 恢复成片的时间线）")
