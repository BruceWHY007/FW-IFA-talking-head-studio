#!/usr/bin/env python3
"""⑦ 渲染：Remotion 逐帧渲画面（静音）→ 与 audio/mix.wav 合成 → out/成片_9x16.mp4

    python render.py <工程目录> --stills 3,520,1560   渲关键帧到 out/stills/（验收首选：每种画面看一张，一秒左右一张）
    python render.py <工程目录> --test               先渲 0–5 秒试片（查字体、素材路径、音画对位）
    python render.py <工程目录> --draft              半尺寸草稿 540×960（只看节奏和结构，省四成算力；不能交付）
    python render.py <工程目录>                      整片（用户要时才渲）

省资源的三件事（2026-11-10）：
  · 代码包只打一次，所有关键帧和分段共用（以前每张关键帧、每一段都重新打包，并把 public/ 里几百 MB 素材再复制一遍）
  · 并发按这台机器的核数和内存定（最多 3；8GB 内存的机器 1 个），可用 --concurrency 或环境变量 IFA_RENDER_CONCURRENCY 改
  · 验收先看关键帧，不为验收渲整片
"""
import argparse, atexit, os, shutil, subprocess, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, load, die, probe, remotion_cmd, render_concurrency

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--test", action="store_true")
ap.add_argument("--stills", default="")
ap.add_argument("--frames", default="", help="只渲一段，如 0-299（看方向用的小样）")
ap.add_argument("--out", default="", help="输出文件名（放 out/ 下）")
ap.add_argument("--draft", action="store_true", help="半尺寸草稿（540×960）：只看节奏结构，不能交付")
ap.add_argument("--concurrency", default="", help="不写＝按这台机器自动定（最多 3）；报 compositor Request closed 时会自动逐级降")
ap.add_argument("--chunk", type=int, default=600, help="分段渲染：每段多少帧起一个新进程（0＝不分段）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
R = P(proj, "remotion")
if not os.path.exists(P(R, "node_modules")):
    die("remotion/node_modules 不存在：先跑 scripts/setup.py，再重建工程或把它链到技能的 runtime/node_modules")
os.makedirs(P(proj, "out"), exist_ok=True)
RC = remotion_cmd(R)
CONC = a.concurrency or str(render_concurrency())
UTF = dict(capture_output=True, text=True, encoding="utf-8", errors="replace")

# ---------- 代码包只打一次 ----------
BUNDLE = P(proj, "out", "_bundle")


def _clean():
    shutil.rmtree(BUNDLE, ignore_errors=True)


def bundle():
    """打包一次（含 public/ 的一份拷贝），后面所有 still／render 都指向它；渲完删掉，不留在磁盘上。"""
    _clean()
    atexit.register(_clean)
    t = time.time()
    r = subprocess.run(RC + ["bundle", "src/index.ts", "--out-dir=" + BUNDLE, "--log=error"], cwd=R, **UTF)
    if r.returncode != 0 or not os.path.exists(os.path.join(BUNDLE, "index.html")):
        die("Remotion 打包失败：\n" + ((r.stderr or r.stdout) or "")[-2500:])
    return time.time() - t


def remotion(args):
    t = time.time()
    r = subprocess.run(RC + args + ["--log=error"], cwd=R, **UTF)
    err = (r.stderr or r.stdout) or ""
    for conc in ("2", "1"):
        if not (r.returncode != 0 and ("Request closed" in err or "Timeout" in err or "delayRender" in err) and any(x.startswith("--concurrency=") for x in args)):
            break
        # 偶发：compositor 抽帧请求被关、取素材或字体超时（10-22 K3 样片：第 2245 帧取 B09、字体 delayRender 118s）。逐级降并发重渲
        print("⚠ Remotion 偶发失败（%s），并发降到 %s 重渲" % ("Request closed" if "Request closed" in err else "超时", conc))
        args = [x if not x.startswith("--concurrency=") else "--concurrency=" + conc for x in args]
        r = subprocess.run(RC + args + ["--log=error"], cwd=R, **UTF)
        err = (r.stderr or r.stdout) or ""
    if r.returncode != 0:
        hint = ""
        if "storage.googleapis.com" in err or "Downloading" in err or "chrome-headless-shell" in err:
            hint = "\n→ 看起来是无头浏览器没装好（默认下载源在国内不通）：跑 scripts/setup.py，它会走国内镜像装"
        die("Remotion 失败：\n" + err[-2500:] + hint)
    return time.time() - t


if a.stills:
    frames = [int(x) for x in a.stills.split(",") if x.strip()]
    os.makedirs(P(proj, "out", "stills"), exist_ok=True)
    tb = bundle()
    t0 = time.time()
    for fr in frames:
        remotion(["still", BUNDLE, "Film", P(proj, "out", "stills", "f%05d.jpg" % fr), "--frame=%d" % fr, "--jpeg-quality=92"])
    print("✓ 关键帧 %d 张 → out/stills/（打包 %.0fs＋渲染 %.0fs）" % (len(frames), tb, time.time() - t0))
    sys.exit(0)

tl = load(P(proj, "timing.json"))
silent = P(proj, "out", "_video_test.mp4" if a.test else "_video.mp4")
args = ["render", BUNDLE, "Film", silent, "--muted", "--codec=h264", "--pixel-format=yuv420p",
        "--timeout=120000", "--concurrency=%s" % CONC]
args += ["--scale=0.5", "--jpeg-quality=70", "--crf=24"] if a.draft else ["--crf=16"]
if a.test:
    rng = (0, 149)
elif a.frames:
    rng = tuple(int(x) for x in a.frames.split("-"))
else:
    rng = (0, int(tl["durationInFrames"]) - 1)
sec = bundle()
# 分段渲染：一个 Remotion 进程连续跑太久，合成器会在中途断开（10-23 实测：样片在第 1280 帧左右「Request closed」后字体 delayRender 超时，
# 同一段单独渲完全正常）。每 600 帧一个新进程，再无损拼接（-c copy），不积累长跑状态
n_fr = rng[1] - rng[0] + 1
if a.chunk and n_fr > a.chunk * 1.5:
    parts = []
    for c0 in range(rng[0], rng[1] + 1, a.chunk):
        c1 = min(c0 + a.chunk - 1, rng[1])
        part = P(proj, "out", "_part_%05d.mp4" % c0)
        sec += remotion([x if x != silent else part for x in args] + ["--frames=%d-%d" % (c0, c1)])
        parts.append(part)
        print("  · 分段 %d–%d 完成" % (c0, c1), flush=True)
    lst = P(proj, "out", "_parts.txt")
    # concat 清单里的路径一律用正斜杠（Windows 的反斜杠在清单里是转义符）
    open(lst, "w", encoding="utf-8").write("".join("file '%s'\n" % x.replace("\\", "/").replace("'", "'\\''") for x in parts))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    for x in parts + [lst]:
        os.remove(x)
    got = int(subprocess.run(["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries", "stream=nb_read_frames",
                              "-of", "csv=p=0", silent], capture_output=True, text=True).stdout.strip().strip(",") or 0)
    if got != n_fr:
        die("分段拼接后帧数 %d ≠ 应有 %d" % (got, n_fr))
else:
    sec += remotion(args + ["--frames=%d-%d" % rng])
_clean()
mix = P(proj, "audio", "mix.wav")
name = a.out or ("试片_0-5s.mp4" if a.test else ("片段_%s.mp4" % a.frames if a.frames else "成片_9x16.mp4"))
if a.draft and not a.out:
    name = "草稿_540p_" + name.replace("成片_9x16", "整片")
final = P(proj, "out", name)
if os.path.exists(mix):
    off = int(a.frames.split("-")[0]) / 30.0 if a.frames else 0.0
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", silent, "-ss", "%.3f" % off, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
           "-c:a", "aac", "-b:a", "256k", "-ar", "48000", "-t", "%.4f" % (probe(silent)["duration"]), "-movflags", "+faststart", final]  # 不用 -shortest：它会把画面截掉 2 帧（10-22 评审第 3 轮）
    run(cmd)
    os.remove(silent)
else:
    os.replace(silent, final)
    print("⚠ 还没有 audio/mix.wav，出的是无声版")
# qa 读的是 out/成片_9x16.mp4：用 --out 起了别的名字时，同一个文件再挂一个这个名字（硬链接，不多占空间；10-30 DeepSeek 每次都要手动 cp）
main_ = P(proj, "out", "成片_9x16.mp4")
if a.out and not a.test and not a.frames and not a.draft and os.path.abspath(final) != os.path.abspath(main_):
    if os.path.lexists(main_):
        os.remove(main_)
    try:
        os.link(final, main_)
    except OSError:
        shutil.copy(final, main_)
    print("  · 同一个文件也挂在 out/成片_9x16.mp4（qa 读它）")
info = probe(final)
print("✓ %s  %.2fs  %s  用时 %.0fs（并发 %s）%s" % (os.path.basename(final), info["duration"], info["video"], sec, CONC,
                                              "　※ 草稿，不能交付" if a.draft else ""))
