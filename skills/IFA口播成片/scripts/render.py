#!/usr/bin/env python3
"""⑦ 渲染：Remotion 逐帧渲画面（静音）→ 与 audio/mix.wav 合成 → out/成片_9x16.mp4

    python3 render.py <工程目录> --test            先渲 0–5 秒试片（正式开工前必做，查字体、素材路径、音画对位）
    python3 render.py <工程目录> --stills 3,520,1560  渲风格帧到 out/stills/（每个风格方向至少看三张：人脸＋字幕、B-roll、卡片）
    python3 render.py <工程目录>                   整片
"""
import argparse, os, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, load, die, probe

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--test", action="store_true")
ap.add_argument("--stills", default="")
ap.add_argument("--frames", default="", help="只渲一段，如 0-299（看方向用的小样）")
ap.add_argument("--out", default="", help="输出文件名（放 out/ 下）")
ap.add_argument("--concurrency", default="3", help="整片默认 3；报 compositor Request closed 时降到 2")
ap.add_argument("--chunk", type=int, default=600, help="分段渲染：每段多少帧起一个新进程（0＝不分段）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
R = P(proj, "remotion")
if not os.path.exists(P(R, "node_modules")):
    die("remotion/node_modules 不存在：软链到 skill 的 runtime/node_modules")
os.makedirs(P(proj, "out"), exist_ok=True)

def remotion(args):
    t = time.time()
    r = subprocess.run(["npx", "remotion"] + args + ["--log=error"], cwd=R, capture_output=True, text=True)
    err = (r.stderr or r.stdout) or ""
    for conc in ("2", "1"):
        if not (r.returncode != 0 and ("Request closed" in err or "Timeout" in err or "delayRender" in err) and any(x.startswith("--concurrency=") for x in args)):
            break
        # 偶发：compositor 抽帧请求被关、取素材或字体超时（10-22 K3 样片：第 2245 帧取 B09、字体 delayRender 118s）。逐级降并发重渲
        print("⚠ Remotion 偶发失败（%s），并发降到 %s 重渲" % ("Request closed" if "Request closed" in err else "超时", conc))
        args = [x if not x.startswith("--concurrency=") else "--concurrency=" + conc for x in args]
        r = subprocess.run(["npx", "remotion"] + args + ["--log=error"], cwd=R, capture_output=True, text=True)
        err = (r.stderr or r.stdout) or ""
    if r.returncode != 0:
        die("Remotion 失败：\n" + err[-2500:])
    return time.time() - t

if a.stills:
    os.makedirs(P(proj, "out", "stills"), exist_ok=True)
    for fr in [int(x) for x in a.stills.split(",") if x.strip()]:
        remotion(["still", "src/index.ts", "Film", P(proj, "out", "stills", "f%05d.jpg" % fr), "--frame=%d" % fr, "--jpeg-quality=92"])
    print("✓ 风格帧 → out/stills/")
    sys.exit(0)

tl = load(P(proj, "timing.json"))
silent = P(proj, "out", "_video_test.mp4" if a.test else "_video.mp4")
args = ["render", "src/index.ts", "Film", silent, "--muted", "--codec=h264", "--crf=16", "--pixel-format=yuv420p",
        "--timeout=120000", "--concurrency=%s" % a.concurrency]
if a.test:
    rng = (0, 149)
elif a.frames:
    rng = tuple(int(x) for x in a.frames.split("-"))
else:
    rng = (0, int(tl["durationInFrames"]) - 1)
# 分段渲染：一个 Remotion 进程连续跑太久，合成器会在中途断开（10-23 实测：样片在第 1280 帧左右「Request closed」后字体 delayRender 超时，
# 同一段单独渲完全正常）。每 600 帧一个新进程，再无损拼接（-c copy），不积累长跑状态
n_fr = rng[1] - rng[0] + 1
if a.chunk and n_fr > a.chunk * 1.5:
    parts, sec = [], 0.0
    for c0 in range(rng[0], rng[1] + 1, a.chunk):
        c1 = min(c0 + a.chunk - 1, rng[1])
        part = P(proj, "out", "_part_%05d.mp4" % c0)
        sec += remotion([x if x != silent else part for x in args] + ["--frames=%d-%d" % (c0, c1)])
        parts.append(part)
        print("  · 分段 %d–%d 完成" % (c0, c1))
    lst = P(proj, "out", "_parts.txt")
    open(lst, "w").write("".join("file '%s'\n" % x.replace("'", "'\\''") for x in parts))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    for x in parts + [lst]:
        os.remove(x)
    got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                              "-of", "csv=p=0", silent], capture_output=True, text=True).stdout.strip().strip(",") or 0)
    if got != n_fr:
        die("分段拼接后帧数 %d ≠ 应有 %d" % (got, n_fr))
else:
    sec = remotion(args + ["--frames=%d-%d" % rng])
mix = P(proj, "audio", "mix.wav")
final = P(proj, "out", a.out or ("试片_0-5s.mp4" if a.test else ("片段_%s.mp4" % a.frames if a.frames else "成片_9x16.mp4")))
if os.path.exists(mix):
    off = int(a.frames.split("-")[0]) / 30.0 if a.frames else 0.0
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", silent, "-ss", "%.3f" % off, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", "%.4f" % (probe(silent)["duration"]), "-movflags", "+faststart", final]  # 不用 -shortest：它会把画面截掉 2 帧（10-22 评审第 3 轮）
    run(cmd)
    os.remove(silent)
else:
    os.replace(silent, final)
    print("⚠ 还没有 audio/mix.wav，出的是无声版")
info = probe(final)
print("✓ %s  %.2fs  %s  渲染用时 %.0fs" % (os.path.basename(final), info["duration"], info["video"], sec))
