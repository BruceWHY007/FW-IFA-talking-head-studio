#!/usr/bin/env python3
"""参考片／成片量化拆解：同一把尺子量参考片和我们的成片，拿数字对比，不靠「看着像」。

    python3 ref_measure.py <视频> <输出目录> [--asr] [--fps 2]
    python3 ref_measure.py <参考片> <目录A> && python3 ref_measure.py <我们的成片> <目录B>
    python3 ref_measure.py --compare <目录A> <目录B>                # 两份报告并排，出差值表

量什么（references/10 §一 的方法，2026-10-29 拆三支参考片时定下）：
  ① 每 0.5 秒一帧：Vision 人脸（大脸＝满屏讲述，小脸＝画中画，无脸＝B-roll／卡片）→ 三类占比与每段时长分布
  ② Vision OCR：屏上文字的行位置与字高 → 字幕中心线、字号（按 1080 宽折算）、刊头与声明的位置
  ③ 亮度：满屏讲述帧与非人脸帧各自的平均亮度（参考片暗书房 vs 我们的窗边，差多少）
  ④ 切点：ffmpeg 场景分数 >0.18 的帧 → 切点数、中位段长
  ⑤ 响度：EBU R128 积分响度、LRA、峰值
  ⑥ （--asr）whisper 转写 → 字数、语速（字/秒）、开场 10 秒原话
产物：<输出目录>/measure.json、report.md、sheet_1fps_NN.jpg（逐秒联系表，人工看结构用）
"""
import argparse, json, os, re, statistics as st, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import die

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("video", nargs="?")
ap.add_argument("out", nargs="?")
ap.add_argument("--fps", type=float, default=2.0)
ap.add_argument("--asr", action="store_true")
ap.add_argument("--compare", nargs=2, metavar=("A", "B"))
a = ap.parse_args()


def vision(name):
    b = os.path.expanduser("~/.cache/ifa-koubo/%s" % name)
    if not os.path.exists(b):
        os.makedirs(os.path.dirname(b), exist_ok=True)
        subprocess.run(["swiftc", "-O", os.path.join(HERE, name + ".swift"), "-o", b], capture_output=True)
    return b if os.path.exists(b) else None


if a.compare:
    A, B = [json.load(open(os.path.join(d, "measure.json"))) for d in a.compare]
    rows = [("时长 s", "duration"), ("满屏讲述占比", "share_A"), ("画中画占比", "share_PIP"), ("无人脸占比", "share_BG"),
            ("满屏讲述段中位 s", "A_run_median"), ("无人脸段中位 s", "BG_run_median"), ("切点数", "cuts"), ("中位段长 s", "cut_median"),
            ("字幕中心线 y（1920 高）", "cap_cy"), ("字幕字号 px（1080 宽）", "cap_px"), ("人脸宽占画幅", "face_w"),
            ("讲述帧亮度", "luma_A"), ("非人脸帧亮度", "luma_BG"), ("响度 LUFS", "lufs"), ("语速 字/秒", "cps")]
    print("| 指标 | %s | %s | 差 |\n|---|---|---|---|" % (os.path.basename(a.compare[0].rstrip("/")), os.path.basename(a.compare[1].rstrip("/"))))
    for n, k in rows:
        x, y = A.get(k), B.get(k)
        d = (y - x) if isinstance(x, (int, float)) and isinstance(y, (int, float)) else ""
        fmt = (lambda v: "%.0f%%" % (v * 100)) if k.startswith("share") else (lambda v: ("%.2f" % v) if isinstance(v, float) else str(v))
        print("| %s | %s | %s | %s |" % (n, fmt(x) if x is not None else "—", fmt(y) if y is not None else "—",
                                          (fmt(d) if not k.startswith("share") else "%+.0f 点" % (d * 100)) if d != "" else ""))
    sys.exit(0)

if not a.video or not a.out:
    die(__doc__)
V, O = os.path.abspath(a.video), os.path.abspath(a.out)
os.makedirs(O, exist_ok=True)
pr = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,codec_type", "-of", "json", V],
                               capture_output=True, text=True).stdout)
dur = float(pr["format"]["duration"])
vs = [s for s in pr["streams"] if s.get("codec_type") == "video"][0]
W, H = vs["width"], vs["height"]
k1080 = 1080 / W
m = {"video": V, "duration": round(dur, 2), "w": W, "h": H}

# ① ② ③ 抽帧＋人脸＋OCR＋亮度
fd = tempfile.mkdtemp(prefix="refm_")
subprocess.run(["ffmpeg", "-v", "error", "-i", V, "-vf", "fps=%g,scale=720:-2" % a.fps, "-q:v", "3", os.path.join(fd, "%05d.jpg")])
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", V, "-vf", "fps=1,scale=180:-2,tile=10x6", "-q:v", "3", os.path.join(O, "sheet_1fps_%02d.jpg")])
faces = json.loads(subprocess.run([vision("face"), fd], capture_output=True, text=True).stdout or "{}") if vision("face") else {}
env = dict(os.environ, OCR_MIN_CHARS="1", OCR_MIN_CONF="0.3")
ocr = json.loads(subprocess.run([vision("text"), fd], capture_output=True, text=True, env=env).stdout or "{}") if vision("text") else {}
from PIL import Image, ImageStat
rows = []
for i, f in enumerate(sorted(x for x in os.listdir(fd) if x.endswith(".jpg"))):
    fs = [x for x in faces.get(f, []) if x.get("conf", 0) > 0.5]
    big = [x for x in fs if x["w"] >= 0.16]
    small = [x for x in fs if 0.035 <= x["w"] < 0.16]
    cls = "A" if big else "PIP" if small else "BG"
    lum = ImageStat.Stat(Image.open(os.path.join(fd, f)).convert("L")).mean[0]
    rows.append({"t": i / a.fps, "cls": cls, "face": (big or small or [None])[0], "luma": lum, "ocr": ocr.get(f, [])})
n = len(rows) or 1
for c in ("A", "PIP", "BG"):
    m["share_" + c] = round(sum(1 for r in rows if r["cls"] == c) / n, 3)
runs, cur = [], None
for r in rows:
    if cur and cur[0] == r["cls"]:
        cur[2] = r["t"]
    else:
        if cur:
            runs.append(cur)
        cur = [r["cls"], r["t"], r["t"]]
if cur:
    runs.append(cur)
for c in ("A", "PIP", "BG"):
    L = [e - s + 1 / a.fps for c_, s, e in runs if c_ == c]
    if L:
        m[c + "_run_median"] = round(st.median(L), 2)
        m[c + "_run_max"] = round(max(L), 2)
        m[c + "_runs"] = len(L)
Af = [r["face"] for r in rows if r["cls"] == "A"]
if Af:
    m["face_w"] = round(st.median(f_["w"] for f_ in Af), 3)
    m["face_cy"] = round(st.median(f_["y"] + f_["h"] / 2 for f_ in Af), 3)
m["luma_A"] = round(st.mean([r["luma"] for r in rows if r["cls"] == "A"] or [0]), 1)
m["luma_BG"] = round(st.mean([r["luma"] for r in rows if r["cls"] == "BG"] or [0]), 1)
# 字幕：中下部（0.40–0.90）、字高 1.2%–6% 的文字行；按行中心 y 取众数 → 中心线；字号 ≈ 行宽 / 字数（中文）
caps = []
for r in rows:
    for o in r["ocr"]:
        cy = o["y"] + o["h"] / 2
        t = re.sub(r"\s", "", o["t"])
        han = len(re.findall(r"[\u4e00-\u9fff]", t))
        if 0.40 < cy < 0.90 and 0.012 < o["h"] < 0.06 and han >= 3 and o.get("c", 0) >= 0.3:
            caps.append((round(cy * 1920 / 20) * 20, o["w"] * W * k1080 / max(han + 0.55 * (len(t) - han), 1)))
if caps:
    from collections import Counter
    mode_y = Counter(c[0] for c in caps).most_common(1)[0][0]
    near = [c[1] for c in caps if abs(c[0] - mode_y) <= 40]
    m["cap_cy"] = mode_y
    m["cap_px"] = round(st.median(near), 1)
    m["cap_y_modes"] = Counter(c[0] for c in caps).most_common(4)
top = [o for r in rows for o in r["ocr"] if o["y"] < 0.12 and len(o["t"]) >= 4]
bot = [o for r in rows for o in r["ocr"] if o["y"] > 0.88 and len(o["t"]) >= 4]
if top:
    m["top_text_y"] = round(st.median(o["y"] for o in top) * 1920)   # 顶部文字行（刊头两行）的中位上沿
    m["kicker_share"] = round(sum(1 for r in rows if any(o["y"] < 0.12 and len(o["t"]) >= 4 for o in r["ocr"])) / n, 2)   # 有刊头的帧占比
if bot:
    m["footer_cy"] = round(st.median(o["y"] + o["h"] / 2 for o in bot) * 1920)
    m["footer_text"] = Counter(re.sub(r"\s", "", o["t"]) for o in bot).most_common(1)[0][0] if bot else ""
# ④ 切点
sc = subprocess.run(["ffmpeg", "-hide_banner", "-i", V, "-an", "-vf", "scale=180:-2,select='gt(scene,0.18)',metadata=print", "-f", "null", "-"],
                    capture_output=True, text=True).stderr
cuts = [float(x) for x in re.findall(r"pts_time:([0-9.]+)", sc)]
m["cuts"] = len(cuts)
segs = [b - a_ for a_, b in zip([0] + cuts, cuts + [dur])]
m["cut_median"] = round(st.median(segs), 2) if segs else None
# ⑤ 响度
lo = subprocess.run(["ffmpeg", "-hide_banner", "-i", V, "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
g = lambda pat: (re.findall(pat, lo) or [None])[-1]
m["lufs"], m["lra"], m["peak"] = [float(x) if x else None for x in (g(r"I:\s+(-?[0-9.]+) LUFS"), g(r"LRA:\s+([0-9.]+) LU"), g(r"Peak:\s+(-?[0-9.]+) dBFS"))]
# ⑥ 转写
if a.asr:
    wav = os.path.join(fd, "a.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", V, "-ar", "16000", "-ac", "1", wav])
    model = os.environ.get("WHISPER_MODEL", os.path.expanduser("~/.cache/whisper-cpp/ggml-small.bin"))
    subprocess.run(["whisper-cli", "-m", model, "-l", "zh", "-oj", "-of", os.path.join(O, "asr"), wav], capture_output=True)
    try:
        segs_ = json.load(open(os.path.join(O, "asr.json")))["transcription"]
        txt = "".join(s["text"] for s in segs_)
        han = len(re.findall(r"[\u4e00-\u9fff]", txt))
        m["chars"], m["cps"] = han, round(han / dur, 2)
        m["open10"] = "".join(s["text"] for s in segs_ if s["offsets"]["from"] < 10000)
    except Exception:
        pass
json.dump(m, open(os.path.join(O, "measure.json"), "w"), ensure_ascii=False, indent=1)
rep = ["# 量化拆解：%s" % os.path.basename(V), "", "| 指标 | 值 |", "|---|---|"]
for k, v in m.items():
    if k != "video":
        rep.append("| %s | %s |" % (k, v))
rep += ["", "联系表：sheet_1fps_*.jpg（每格 1 秒，10 列 × 6 行＝1 分钟一张）"]
open(os.path.join(O, "report.md"), "w").write("\n".join(rep) + "\n")
print("✓ %s  A %.0f%% / PIP %.0f%% / BG %.0f%%  字幕 y≈%s %spx  切点 %s  %s LUFS" % (os.path.basename(V), m["share_A"] * 100, m["share_PIP"] * 100,
      m["share_BG"] * 100, m.get("cap_cy"), m.get("cap_px"), m["cuts"], m["lufs"]))
