#!/usr/bin/env python3
"""风格目录：**人把原片递过来时，用他自己的画面渲一张七套风格的对比图**，让他挑。

    python3 catalog.py --video <原片.mp4> [--seconds 6] [--keep]   # 生成目录（约 2–4 分钟）
    python3 catalog.py                                             # 只打印菜单与用法（不渲）

为什么不预置一张目录图：目录里的人必须是**这位用户本人**。拿别支片子的人物去做样片，
既是拿别人的脸当模板，也会让用户认不出「这是我这支片子的样子」。所以每次都用他给的片子现做：
取正脸 → 六套风格里用同一份示范文案各渲 8 帧 → 拼成 总览.jpg。

产物：`~/.cache/ifa-koubo/catalog/总览.jpg`（路径会打印出来，直接发给用户）
"""
import argparse, json, os, subprocess, sys, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, run, probe, save, die

ap = argparse.ArgumentParser()
ap.add_argument("--video", default="", help="用户给的原片；给了才渲目录")
ap.add_argument("--seconds", type=float, default=6.0, help="从头取多少秒做样片（默认 6s）")
ap.add_argument("--keep", action="store_true", help="保留临时工程，方便排查")
a = ap.parse_args()

CACHE = os.path.expanduser("~/.cache/ifa-koubo/catalog")
PACKS = [("F", "F 满幅讲述（默认）", "她满幅在说＋小窗／分带／B-roll 轮换，数据上玻璃卡，重话金银字", "观点讲述、政策解读、财经科普"),
         ("A", "A 分带刊物", "上下纸带，字永远不压画面", "个人近况、生活、经历"),
         ("B", "B 雾金玻璃", "满幅实拍＋雾＋液态玻璃", "活动、开业、品牌宣传"),
         ("C", "C 港刊大字", "满幅＋书脊线＋宋体大字", "热点、观点、金句"),
         ("K1", "K1 证据桌", "桌面纸纹、撕边剪报、荧光笔", "政策、新闻、报告原文"),
         ("K2", "K2 图解", "网格＋柱图从 0 起＋图号来源", "数字、对比、清单"),
         ("K3", "K3 IFA 品牌刊", "IFA 图文卡同一套渐变与 logo", "平台、招募、团队")]


def menu():
    print("== 风格目录：先给用户看，再开工 ==")
    print("跑：python3 scripts/catalog.py --video <用户的原始口播.mp4>")
    print("它会用**用户自己的画面**渲一张七套风格的对比图（约 2–4 分钟），把那张图发给用户，等一个代号。")
    print("")
    for code, name, one, good in PACKS:
        print("  %-3s %-12s %s｜适合：%s" % (code, name, one, good))
    print("")
    print("底部分三种，默认 paper：paper＝整页纸、不留色块；fade＝100px 深底＋渐深；plate＝160px 深底。")
    print("  只有发抖音／视频号（白字描述压在画面上）才需要 fade 或 plate，写进 decompose.footer。")
    print("回法：`A` / `K1` 这样一行；要深底就补一个词，例如 `A fade`。不回、或回「默认」，就用 F 满幅讲述。")


if not a.video:
    menu()
    raise SystemExit(0)

raw = os.path.abspath(a.video)
if not os.path.exists(raw):
    die("原片不存在：" + raw)
info = probe(raw)
v = info["video"]
if not v:
    die("这个文件没有视频流")

# ---------- 1. 临时工程 ----------
shutil.rmtree(CACHE, ignore_errors=True)
proj = CACHE
R = P(proj, "remotion")
os.makedirs(P(proj, "out"), exist_ok=True)
os.makedirs(P(proj, "work"), exist_ok=True)
shutil.copytree(os.path.join(SKILL, "template", "remotion"), R, ignore=shutil.ignore_patterns("node_modules", "out"))
nm = os.path.join(SKILL, "runtime", "node_modules")
if not os.path.exists(nm):
    die("共享运行时还没装：bash scripts/setup.sh")
os.symlink(nm, P(R, "node_modules"))
os.makedirs(P(R, "public", "clips"), exist_ok=True)
# 字体：gallery.py 要用 public/fonts 里的三支字体做子集（模板里只有 brand/logo.png）
os.makedirs(P(R, "public", "fonts"), exist_ok=True)
for _f in ("SourceHanSerifSC-Heavy.otf", "SourceHanSerifSC-SemiBold.otf", "BodoniModa.ttf"):
    shutil.copy(os.path.join(SKILL, "assets", "fonts", _f), P(R, "public", "fonts", _f))

# ---------- 2. 归一化 + 截一段 ----------
aout = P(R, "public", "aroll_cut.mp4")
vf = []
ct = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                     "-of", "csv=p=0", raw], capture_output=True, text=True).stdout.strip()
if ct in ("arib-std-b67", "smpte2084"):
    vf.append("colorspace=all=bt709:trc=bt709:format=yuv420p")
if v["h"] >= v["w"]:
    vf += ["scale=1080:1920:force_original_aspect_ratio=increase", "crop=1080:1920"]
else:
    vf += ["crop=ih*9/16:ih:(iw-ih*9/16)*0.5:0", "scale=1080:1920"]
vf.append("fps=30")
run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-t", "%.2f" % min(a.seconds, info["duration"]), "-vf", ",".join(vf),
     "-c:v", "h264_videotoolbox", "-b:v", "12M", "-an", "-movflags", "+faststart", aout])
dur = probe(aout)["duration"]
print("· 样片 A-roll %.1fs 1080×1920" % dur)

# ---------- 3. 人脸位置（Vision；拿不到就居中）----------
face = {"cx": 0.507, "cy": 0.45}
fd = P(proj, "work", "_face")
os.makedirs(fd, exist_ok=True)
for i in range(6):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % (dur * (i + 0.5) / 6), "-i", aout, "-frames:v", "1",
                    os.path.join(fd, "f%02d.jpg" % i)], capture_output=True)
face_bin = os.path.expanduser("~/.cache/ifa-koubo/face")
if not os.path.exists(face_bin):
    subprocess.run(["swiftc", "-O", os.path.join(SKILL, "scripts", "face.swift"), "-o", face_bin], capture_output=True)
if os.path.exists(face_bin):
    try:
        got = json.loads(subprocess.run([face_bin, fd], capture_output=True, text=True).stdout or "{}")
        faces = [f for v_ in got.values() for f in v_ if f.get("conf", 0) > 0.5 and f.get("w", 0) > 0.12]
        if faces:
            big = max(faces, key=lambda f: f["w"])
            face = {"cx": round(big["x"] + big["w"] / 2, 3), "cy": round(big["y"] + big["h"] / 2, 3)}
            print("· 人脸中心 %.2f / %.2f（脸宽 %.0f%%）" % (face["cx"], face["cy"], big["w"] * 100))
    except Exception:
        pass

# ---------- 4. 最小时间线（gallery.py 只要 aroll）----------
save(P(R, "src", "timeline.json"), {"fps": 30, "width": 1080, "height": 1920, "durationInFrames": max(int(dur * 30), 240),
                                    "style": "editorial", "aroll": {"src": "aroll_cut.mp4", "face": face}})

# ---------- 5. 六套风格：同一批帧 ----------
r = subprocess.run([sys.executable, os.path.join(SKILL, "scripts", "gallery.py"), proj], capture_output=True, text=True)
if r.returncode != 0:
    die("渲目录失败：\n%s" % (r.stderr or r.stdout)[-1200:])
over = P(proj, "out", "风格目录", "总览.jpg")
if not os.path.exists(over):
    die("没有生成总览.jpg")
stable = P(CACHE, "总览.jpg")
shutil.copy(over, stable)
print("")
print("✓ 风格目录（用这位用户自己的画面）→ %s" % stable)
print("  把这张图发给用户，等一个代号：F（默认）/ A / B / C / K1 / K2 / K3；不回就是 F")
if not a.keep:
    shutil.rmtree(P(proj, "work", "_face"), ignore_errors=True)
