#!/usr/bin/env python3
"""② 拆 A-roll：逐句量「这一句的脸能不能直接用」，出一张逐句总览图给人（和 Claude）判。

    python3 analyze.py <工程目录>

每句量六样：时长与语速、口癖、疑似重说、人脸（在不在、正不正对镜头）、清晰度、手势能量。
结论只是建议标签，最终 A/B 判定写在 decompose.json 里（规则见 references/02）：
  A·宜留   有表情有手势、正对镜头、清楚——观点、转折、钩子、号召优先放这里
  A·可遮   画面能用但平淡——事实、数字、名词句优先拿 B-roll 盖
  需遮     失焦／侧脸／低头看稿／卡壳——必须盖 B-roll，或删
  删       整句是重说的废稿
产物：work/analysis.json、work/aroll_sheet.jpg（逐句一格，带标签），project.json 写入人脸中心（推镜用）。
"""
import argparse, difflib, glob, json, os, re, shutil, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, run, load, save, die, read_gray_frames, font, hms
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("proj")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
tr = load(P(proj, "transcript.json"))
src = P(proj, "work", "aroll.mp4")
S = tr["sentences"]

# 口癖词表：句首的「那么／然后／就是」、独立的「嗯／呃／额」。「啊／呢／吧」是句末语气，不算。
FILLER_HEAD = ["那么", "然后", "就是说", "就是", "那个", "这个", "其实"]
FILLER_ANY = ["嗯", "呃", "额"]

def fillers(t):
    hits = [w for w in FILLER_HEAD if t.startswith(w)]
    hits += [w for w in FILLER_ANY if w in t]
    return hits

# ---------- 人脸检测（macOS Vision） ----------
face_bin = os.path.expanduser("~/.cache/ifa-koubo/face")
if not os.path.exists(face_bin):
    os.makedirs(os.path.dirname(face_bin), exist_ok=True)
    r = subprocess.run(["swiftc", "-O", os.path.join(SKILL, "scripts", "face.swift"), "-o", face_bin],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("⚠ Vision 人脸检测编译失败，跳过人脸项：", r.stderr[-300:])
fd = P(proj, "work", "_fa")
shutil.rmtree(fd, ignore_errors=True)
os.makedirs(fd)
for k, s in enumerate(S):
    for j, fr_ in enumerate((0.25, 0.5, 0.75)):
        t = s["start"] + (s["end"] - s["start"]) * fr_
        run(["ffmpeg", "-v", "error", "-y", "-ss", "%.3f" % t, "-i", src, "-frames:v", "1",
             "-vf", "scale=540:-2", P(fd, "%03d_%d.jpg" % (k, j))])
faces = {}
if os.path.exists(face_bin):
    faces = json.loads(subprocess.run([face_bin, fd], capture_output=True, text=True).stdout or "{}")

# ---------- 清晰度：人脸框（没有就画面中上部）的拉普拉斯方差 ----------
from PIL import Image
def sharp_luma(path, box):
    im = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
    h, w = im.shape
    if box:
        x0, y0 = int(box["x"] * w), int(box["y"] * h)
        x1, y1 = int((box["x"] + box["w"]) * w), int((box["y"] + box["h"]) * h)
    else:
        x0, y0, x1, y1 = int(w * .25), int(h * .15), int(w * .75), int(h * .5)
    c = im[max(y0, 0):y1, max(x0, 0):x1]
    if c.size < 100:
        return 0.0, 0.0
    lap = c[1:-1, 1:-1] * 4 - c[:-2, 1:-1] - c[2:, 1:-1] - c[1:-1, :-2] - c[1:-1, 2:]
    return float(lap.var()), float(c.mean())

# ---------- 手势能量：句内 6fps 帧差（脸以下区域） ----------
g = read_gray_frames(src, 180, 320, 6)
def gesture(s0, s1):
    i0, i1 = int(s0 * 6), max(int(s1 * 6), int(s0 * 6) + 2)
    seg = g[i0:i1, 140:, :]
    if len(seg) < 2:
        return 0.0
    return float(np.abs(np.diff(seg, axis=0)).mean())

rows = []
for k, s in enumerate(S):
    fs = [faces.get("%03d_%d.jpg" % (k, j), []) for j in range(3)]
    best = [max(f, key=lambda o: o["w"] * o["h"]) if f else None for f in fs]
    seen = [b for b in best if b]
    yaw = float(np.median([abs(b["yaw"]) for b in seen])) if seen else None
    sh = [sharp_luma(P(fd, "%03d_%d.jpg" % (k, j)), best[j]) for j in range(3)]
    dur = s["end"] - s["start"]
    nxt = S[k + 1]["text"] if k + 1 < len(S) else ""
    sim = difflib.SequenceMatcher(None, s["text"], nxt).ratio() if nxt else 0
    rows.append({
        "id": s["id"], "text": s["text"], "start": s["start"], "end": s["end"], "dur": round(dur, 2),
        "rate": round(len(s["text"]) / max(dur, .1), 2), "fillers": fillers(s["text"]),
        "retake_sim_next": round(sim, 2), "face_seen": len(seen), "yaw": None if yaw is None else round(yaw, 2),
        "face": seen[1] if len(seen) > 1 else (seen[0] if seen else None),
        "sharp": round(float(np.median([x[0] for x in sh])), 1), "luma": round(float(np.median([x[1] for x in sh])), 1),
        "gesture": round(gesture(s["start"], s["end"]), 2),
    })

sh_med = float(np.median([r["sharp"] for r in rows])) or 1
ge = [r["gesture"] for r in rows]
ge_hi = float(np.percentile(ge, 70)) if ge else 0
for r in rows:
    why = []
    if r["face_seen"] == 0:
        why.append("无脸")
    elif r["yaw"] is not None and r["yaw"] > 0.35:
        why.append("侧脸")
    if r["sharp"] < sh_med * 0.45:
        why.append("偏糊")
    if r["luma"] < 60 or r["luma"] > 220:
        why.append("曝光")
    if r["retake_sim_next"] > 0.55:
        why.append("疑似重说")
    if r["rate"] < 2.6 and r["dur"] > 1.5:
        why.append("卡壳/慢")
    if why:
        tag = "删" if why == ["疑似重说"] else "需遮"
    elif r["gesture"] >= ge_hi:
        tag = "A·宜留"
    else:
        tag = "A·可遮"
    r["tag"], r["why"] = tag, why

seen_faces = [r["face"] for r in rows if r["face"]]
if seen_faces:
    cx = float(np.median([f["x"] + f["w"] / 2 for f in seen_faces]))
    cy = float(np.median([f["y"] + f["h"] / 2 for f in seen_faces]))
    fw = float(np.median([f["w"] for f in seen_faces]))
    pj = load(P(proj, "project.json"), {})
    pj["face"] = {"cx": round(cx, 3), "cy": round(cy, 3), "w": round(fw, 3)}
    save(P(proj, "project.json"), pj)
save(P(proj, "work", "analysis.json"), {"sharp_median": sh_med, "gesture_p70": ge_hi, "sentences": rows})

# ---------- 逐句总览图 ----------
from PIL import ImageDraw
cw, ch = 216, 384
cols = 8
img = Image.new("RGB", (cols * cw, ((len(rows) + cols - 1) // cols) * (ch + 96)), (16, 16, 16))
dr = ImageDraw.Draw(img)
f1, f2 = font(17), font(15)
COL = {"A·宜留": (120, 220, 140), "A·可遮": (230, 230, 230), "需遮": (250, 170, 60), "删": (240, 90, 80)}
for k, r in enumerate(rows):
    im = Image.open(P(fd, "%03d_1.jpg" % k)).resize((cw, ch))
    x0, y0 = (k % cols) * cw, (k // cols) * (ch + 96)
    img.paste(im, (x0, y0))
    dr.rectangle([x0, y0, x0 + cw - 1, y0 + 24], fill=(0, 0, 0))
    dr.text((x0 + 4, y0 + 3), "%s %s %s" % (r["id"], hms(r["start"]), r["tag"]), fill=COL[r["tag"]], font=f1)
    t = r["text"]
    dr.text((x0 + 4, y0 + ch + 4), t[:12], fill="white", font=f1)
    dr.text((x0 + 4, y0 + ch + 26), t[12:24], fill="white", font=f1)
    dr.text((x0 + 4, y0 + ch + 50), "%.1fs %.1f字/s 手势%.1f" % (r["dur"], r["rate"], r["gesture"]), fill=(170, 170, 170), font=f2)
    dr.text((x0 + 4, y0 + ch + 70), " ".join(r["why"] + r["fillers"])[:16], fill=(250, 170, 60), font=f2)
img.save(P(proj, "work", "aroll_sheet.jpg"), quality=84)
shutil.rmtree(fd, ignore_errors=True)

cnt = {}
for r in rows:
    cnt[r["tag"]] = cnt.get(r["tag"], 0) + 1
print("✓ 逐句 %d：%s" % (len(rows), "  ".join("%s %d" % kv for kv in cnt.items())))
print("  看 work/aroll_sheet.jpg，再按 references/02 写 edits.json 与 decompose.json")
