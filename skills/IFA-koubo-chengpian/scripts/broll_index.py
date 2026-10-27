#!/usr/bin/env python3
"""④-a 用户给的 B-roll 素材库：逐条量时长画幅，出带编号的缩略总览图，给人和 Claude 按镜头挑。

    python3 broll_index.py <工程目录> <素材目录或文件> [...]
    python3 broll_index.py <工程目录> --relink <素材挪去的新目录> [...]   素材换了位置时找回，编号不变

每条素材抽 4 帧（10%/37%/63%/90%）拼成一行，标编号、时长、画幅、运动量。
挑片不靠文件名猜——文件名常常写的是当初的用途，不是画面里实际有什么。看图挑。
产物：broll/library.json（编号 → 路径与参数）、broll/lib_sheet_NN.jpg（每张 12 条）
"""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, probe, load, save, read_gray_frames, font, clip_cuts
from PIL import Image, ImageDraw
import numpy as np

proj = os.path.abspath(sys.argv[1])
args = sys.argv[2:]
relink = "--relink" in args
args = [x for x in args if x != "--relink"]
paths = []
for arg in args:
    if os.path.isdir(arg):
        for ext in ("mp4", "mov", "MP4", "MOV", "m4v", "webm"):
            paths += glob.glob(os.path.join(arg, "**", "*." + ext), recursive=True)
    else:
        paths.append(arg)
paths = sorted(set(os.path.abspath(p) for p in paths))
lib = load(P(proj, "broll", "library.json"), {"clips": {}})
if relink:
    # 素材挪了目录（整理桌面、归档进项目）：按文件名＋时长在新目录里找回，编号不变，decompose 不用改
    by_name = {}
    for p_ in paths:
        by_name.setdefault(os.path.basename(p_), []).append(p_)
    fixed, lost = 0, []
    for cid, c in lib["clips"].items():
        if os.path.exists(c["path"]):
            continue
        cands = [x for x in by_name.get(c["name"], []) if abs(probe(x)["duration"] - c["dur"]) < 0.15]
        if cands:
            c["path"] = cands[0]
            fixed += 1
        else:
            lost.append(cid + " " + c["name"])
    save(P(proj, "broll", "library.json"), lib)
    print("✓ 重新关联 %d 条%s" % (fixed, "；仍找不到：" + "、".join(lost) if lost else ""))
    sys.exit(0)
known = {c["path"]: k for k, c in lib["clips"].items()}
n0 = len(lib["clips"])
for p in paths:
    if p in known:
        continue
    info = probe(p)
    v = info["video"]
    if not v:
        continue
    cid = "L%03d" % (len(lib["clips"]) + 1)
    g = read_gray_frames(p, 96, 54 if v["w"] >= v["h"] else 170, 4)
    mot = float(np.abs(np.diff(g, axis=0)).mean()) if len(g) > 1 else 0.0
    lib["clips"][cid] = {"path": p, "name": os.path.basename(p), "dur": round(info["duration"], 2),
                         "w": v["w"], "h": v["h"], "fps": v["fps"],
                         "orient": "竖" if v["h"] > v["w"] else ("方" if v["h"] == v["w"] else "横"),
                         "motion": round(mot, 2), "cuts": clip_cuts(p)}
save(P(proj, "broll", "library.json"), lib)

# 总览图：每条一行 4 帧（统一高度 240）
tmp = P(proj, "broll", "_t")
os.makedirs(tmp, exist_ok=True)
items = sorted(lib["clips"].items())
per = 12
f1 = font(20)
for page in range((len(items) + per - 1) // per):
    chunk = items[page * per:(page + 1) * per]
    rows = []
    for cid, c in chunk:
        frames = []
        for k, fr_ in enumerate((0.1, 0.37, 0.63, 0.9)):
            out = os.path.join(tmp, "%s_%d.jpg" % (cid, k))
            if not os.path.exists(out):
                run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % (c["dur"] * fr_), "-i", c["path"],
                     "-frames:v", "1", "-vf", "scale=-2:240", out], check=False)
            if os.path.exists(out):
                frames.append(Image.open(out))
        wsum = sum(f.width for f in frames) + 8 * len(frames)
        row = Image.new("RGB", (max(wsum, 900) + 260, 252), (18, 18, 18))
        d = ImageDraw.Draw(row)
        d.text((8, 8), cid, fill=(240, 200, 120), font=font(30))
        d.text((8, 52), c["name"][:14], fill="white", font=f1)
        d.text((8, 82), "%.1fs %s %dx%d" % (c["dur"], c["orient"], c["w"], c["h"]), fill=(190, 190, 190), font=f1)
        d.text((8, 112), "运动 %.1f" % c["motion"], fill=(190, 190, 190), font=f1)
        if c.get("cuts"):
            d.text((8, 142), "内含 %d 个镜头" % (len(c["cuts"]) + 1), fill=(250, 170, 60), font=f1)
        x = 260
        for f in frames:
            row.paste(f, (x, 6))
            x += f.width + 8
        rows.append(row)
    W = max(r.width for r in rows)
    sheet = Image.new("RGB", (W, 252 * len(rows)), (10, 10, 10))
    for i, r in enumerate(rows):
        sheet.paste(r, (0, 252 * i))
    sheet.save(P(proj, "broll", "lib_sheet_%02d.jpg" % (page + 1)), quality=80)
print("✓ 素材库 %d 条（新增 %d），总览 broll/lib_sheet_*.jpg" % (len(lib["clips"]), len(lib["clips"]) - n0))
