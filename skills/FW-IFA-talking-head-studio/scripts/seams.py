#!/usr/bin/env python3
"""接缝检查图：每个剪辑点前后的连续帧排成一行，看交接顺不顺（思路借自 talk-workbench 的 seam_sheet，自己实现）。

    python3 seams.py <工程目录> [--video out/成片_9x16.mp4]   → qa/接缝检查.jpg

每行 8 帧：切点前 0.3、0.1 秒，切点本帧，切点后 0.03、0.1、0.2、0.3、0.5 秒。重点看切点后 0.1–0.3 秒：
一闪而过的镜头、两镜叠在一起、字幕先换位再跳、画面窗空着、升起转场卡住。首尾两张静帧查不出这些。
"""
import io, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, load, hms, font
from PIL import Image, ImageDraw

proj = os.path.abspath(sys.argv[1])
V = sys.argv[sys.argv.index("--video") + 1] if "--video" in sys.argv else P(proj, "out", "成片_9x16.mp4")
tl = load(P(proj, "timing.json"))
FPS = tl["fps"]
cuts = sorted(set([s["from"] for s in tl["shots"]] + [s["to"] for s in tl["shots"]] + [c["from"] for c in tl.get("chapters", [])][1:]))
cuts = [c for c in cuts if 10 < c < tl["durationInFrames"] - 15]
OFFS = (-0.3, -0.1, 0.0, 0.033, 0.1, 0.2, 0.3, 0.5)  # 0.0＝切点本帧（第 2 轮评审：漏了它就漏了闪白）
TW, TH, LAB = 180, 320, 120
sheet = Image.new("RGB", (LAB + TW * len(OFFS), (TH + 26) * len(cuts)), (18, 18, 18))
d = ImageDraw.Draw(sheet)
f1, f2 = font(18), font(15)
name = {}
for s in tl["shots"]:
    name[s["from"]] = name.get(s["from"], "") + "→" + s["id"]
    name[s["to"]] = s["id"] + "→" + name.get(s["to"], "")
for r, c in enumerate(cuts):
    y = r * (TH + 26)
    d.text((6, y + 30), "%s\n%s" % (hms(c / FPS), name.get(c, "章节")), fill=(232, 194, 127), font=f1)
    for k, o in enumerate(OFFS):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", "%.4f" % max(c / FPS + o + 0.001, 0), "-i", V, "-frames:v", "1",
                              "-vf", "scale=%d:%d" % (TW, TH), "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
        if raw:
            sheet.paste(Image.open(io.BytesIO(raw)).convert("RGB"), (LAB + k * TW, y + 22))
        d.text((LAB + k * TW + 4, y + 2), "%+.2fs" % o, fill=(240, 90, 80) if 0 < o <= 0.3 else (170, 170, 170), font=f2)
out = P(proj, "qa", "接缝检查.jpg")
sheet.save(out, quality=84)
print("✓ %s（%d 个接缝）" % (out, len(cuts)))
