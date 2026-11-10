#!/usr/bin/env python3
"""安装与自检（macOS／Windows／Linux 通用，只需要先有 Python 3.9+）。可以反复跑，装过的会跳过。

    python setup.py                 装到能用：每一步有超时、先走国内镜像、大文件断点续传
    python setup.py --check         只检查不改（等于以前的 doctor）：最后一行是 [doctor] OK 才算好
    python setup.py --smoke         装完渲一帧，证明「打包→无头浏览器→出图」这条链是通的
    python setup.py --offline <目录> 大文件先从这个目录找（同事之间拷一份离线包，不用再下载）
    python setup.py --pack <目录> [--target win|mac|linux]   把某个系统要下载的大文件收进一个目录，做成离线包
    python setup.py --model small   转写模型要原版 small（487MB）；默认装量化版 small-q5_1（190MB，实测结果基本一致）

为什么要这个文件（2026-11-10）：原来只有 setup.sh——Windows 没有 bash；强制走 npmjs 官方源，国内很慢；
无头浏览器默认从 storage.googleapis.com 下、转写模型从 huggingface.co 下，国内都不通，Agent 会一直等到超时。
现在：npm 源、PyPI 源先测哪个通；浏览器、ffmpeg、Node 走 npmmirror；模型走 hf-mirror；每个下载有总时限和「卡住 40 秒就换源」。
"""
import argparse, gzip, json, os, platform, shutil, socket, subprocess, sys, time, urllib.request, zipfile, tarfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kb
from kb import SKILL, CACHE, BIN, WIN, MAC, PY, has

ap = argparse.ArgumentParser()
ap.add_argument("--check", action="store_true")
ap.add_argument("--smoke", action="store_true")
ap.add_argument("--offline", default="")
ap.add_argument("--pack", default="")
ap.add_argument("--target", default="", choices=["", "win", "mac", "linux"])
ap.add_argument("--model", default="small-q5_1", choices=["small-q5_1", "small"])
ap.add_argument("--skip", default="", help="跳过某几步，逗号分隔：pip,ffmpeg,node,npm,browser,whisper,model")
a = ap.parse_args()
SKIP = set(x.strip() for x in a.skip.split(",") if x.strip())
RT = os.path.join(SKILL, "runtime")
NM = os.path.join(RT, "node_modules")
ARCH = "arm64" if platform.machine().lower() in ("arm64", "aarch64") else "x64"
OSN = "win" if WIN else ("mac" if MAC else "linux")
ok_n, bad, warn = 0, [], []


def good(msg):
    global ok_n
    ok_n += 1
    print("  ✅ " + msg, flush=True)


def fail(msg, fix):
    bad.append((msg, fix))
    print("  ❌ %s\n     → %s" % (msg, fix), flush=True)


def note(msg, fix=""):
    warn.append(msg)
    print("  ⚠️  %s%s" % (msg, ("\n     → " + fix) if fix else ""), flush=True)


def sh(cmd, timeout=60, **kw):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, **kw)
    except (OSError, subprocess.TimeoutExpired) as e:
        return subprocess.CompletedProcess(cmd, 1, "", str(e))


def npm(args):
    """npm 在 Windows 上是 npm.cmd：经 cmd 调用。"""
    return (["cmd", "/c", "npm"] if WIN else ["npm"]) + args


# ---------- 下载：多个源依次试、断点续传、卡住就换、总时限 ----------
def reachable(url, t=6):
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "ifa-koubo-setup"})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=t) as r:
            return (time.time() - t0) if r.status < 400 else None
    except Exception:
        return None


def download(urls, dst, size=0, limit=900, label=""):
    """urls 依次试；dst.part 断点续传；40 秒没有新数据就换下一个源；limit 是总时限（秒）。成功返回 True。"""
    label = label or os.path.basename(dst)
    if os.path.exists(dst) and (not size or os.path.getsize(dst) == size):
        return True
    if a.offline:
        for root, _d, files in os.walk(a.offline):
            if os.path.basename(dst) in files:
                src = os.path.join(root, os.path.basename(dst))
                if not size or os.path.getsize(src) == size:
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy(src, dst)
                    print("     · %s 取自离线包" % label, flush=True)
                    return True
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    part, t_all = dst + ".part", time.time()
    for url in urls:
        host = url.split("/")[2]
        for opener in (urllib.request.build_opener(), urllib.request.build_opener(urllib.request.ProxyHandler({}))):   # 先按系统代理设置，再直连
            have = os.path.getsize(part) if os.path.exists(part) else 0
            req = urllib.request.Request(url, headers={"User-Agent": "ifa-koubo-setup", **({"Range": "bytes=%d-" % have} if have else {})})
            try:
                with opener.open(req, timeout=40) as r:
                    if have and r.status != 206:
                        have = 0
                    total = have + int(r.headers.get("Content-Length") or 0)
                    last = time.time()
                    with open(part, "ab" if have else "wb") as f:
                        while True:
                            buf = r.read(1 << 18)
                            if not buf:
                                break
                            f.write(buf)
                            have += len(buf)
                            if time.time() - last > 8:
                                last = time.time()
                                print("     · %s %d／%d MB（%s）" % (label, have >> 20, (size or total) >> 20, host), flush=True)
                            if time.time() - t_all > limit:
                                raise TimeoutError("超过总时限 %d 秒" % limit)
                want = size or total
                if want and os.path.getsize(part) != want:
                    raise IOError("大小不对：%d ≠ %d" % (os.path.getsize(part), want))
                os.replace(part, dst)
                return True
            except Exception as e:
                print("     · %s 从 %s 没下完（%s）%s" % (label, host, str(e)[:60], "，已下的部分留着续传" if os.path.exists(part) else ""), flush=True)
                if time.time() - t_all > limit:
                    return False
    return False


def unzip(zp, dst, strip_prefix=""):
    with zipfile.ZipFile(zp) as z:
        for m in z.infolist():
            name = m.filename
            if strip_prefix and name.startswith(strip_prefix):
                name = name[len(strip_prefix):]
            if not name or name.endswith("/"):
                continue
            out = os.path.join(dst, name)
            os.makedirs(os.path.dirname(out), exist_ok=True)
            with z.open(m) as src, open(out, "wb") as f:
                shutil.copyfileobj(src, f)
            mode = (m.external_attr >> 16) & 0o777
            if mode and not WIN:
                os.chmod(out, mode)


# ---------- 各个大文件从哪下（国内镜像在前） ----------
def chrome_version():
    js = os.path.join(NM, "@remotion", "renderer", "dist", "browser", "get-chrome-download-url.js")
    if os.path.exists(js):
        import re
        m = re.search(r"TESTED_VERSION = '([\d.]+)'", open(js, encoding="utf-8").read())
        if m:
            return m.group(1)
    return "149.0.7790.0"   # Remotion 4.0.484 钉的版本


def plan(osn, arch):
    """这个系统需要哪些大文件：{名字: (本地文件名, [源…], 字节数或 0)}"""
    cv = chrome_version()
    cplat = {"win": "win64", "mac": "mac-arm64" if arch == "arm64" else "mac-x64", "linux": "linux64"}[osn]
    fplat = {"win": "win32-x64", "mac": "darwin-" + arch, "linux": "linux-" + arch}[osn]
    hf = "ggerganov/whisper.cpp/resolve/main/"
    mname = "ggml-%s.bin" % a.model
    p = {
        "browser": ("chrome-headless-shell-%s.zip" % cplat,
                    ["https://cdn.npmmirror.com/binaries/chrome-for-testing/%s/%s/chrome-headless-shell-%s.zip" % (cv, cplat, cplat),
                     "https://storage.googleapis.com/chrome-for-testing-public/%s/%s/chrome-headless-shell-%s.zip" % (cv, cplat, cplat)], 0),
        "model": (mname, ["https://hf-mirror.com/" + hf + mname, "https://huggingface.co/" + hf + mname],
                  {"small-q5_1": 190085487, "small": 487601967}[a.model]),
        "ffmpeg": ("ffmpeg-%s.gz" % fplat, ["https://cdn.npmmirror.com/binaries/ffmpeg-static/b6.1.1/ffmpeg-%s.gz" % fplat,
                                           "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffmpeg-%s.gz" % fplat], 0),
        "ffprobe": ("ffprobe-%s.gz" % fplat, ["https://cdn.npmmirror.com/binaries/ffmpeg-static/b6.1.1/ffprobe-%s.gz" % fplat,
                                             "https://github.com/eugeneware/ffmpeg-static/releases/download/b6.1.1/ffprobe-%s.gz" % fplat], 0),
    }
    if osn == "win":
        gh = "https://github.com/ggml-org/whisper.cpp/releases/download/v1.8.2/whisper-bin-x64.zip"
        p["whisper"] = ("whisper-bin-x64.zip", [gh, "https://ghfast.top/" + gh, "https://gh-proxy.com/" + gh], 0)
        p["node"] = ("node-v22.21.1-win-x64.zip", ["https://cdn.npmmirror.com/binaries/node/v22.21.1/node-v22.21.1-win-x64.zip",
                                                    "https://nodejs.org/dist/v22.21.1/node-v22.21.1-win-x64.zip"], 0)
    return p, cplat


# ---------- 离线包 ----------
if a.pack:
    tgt = a.target or OSN
    p, _ = plan(tgt, "x64" if tgt == "win" else ARCH)
    os.makedirs(a.pack, exist_ok=True)
    print("── 做离线包（%s）→ %s" % (tgt, a.pack))
    for k, (fn, urls, size) in p.items():
        if tgt != "win" and k in ("ffmpeg", "ffprobe"):
            continue   # macOS／Linux 用系统包管理器装 ffmpeg
        got = download(urls, os.path.join(a.pack, fn), size, limit=1800, label=fn)
        print("  %s %s" % ("✅" if got else "❌", fn), flush=True)
    open(os.path.join(a.pack, "怎么用.txt"), "w", encoding="utf-8").write(
        "把这个文件夹整个拷给同事，然后在技能目录下跑：\n    python scripts/setup.py --offline <这个文件夹的路径>\n"
        "脚本会先从这里取大文件，取不到的才去下载。Remotion 的 npm 包不在离线包里（各系统不一样），安装时走国内 npm 镜像，一两分钟。\n")
    sys.exit(0)

CHECK = a.check
P_, CPLAT = plan(OSN, ARCH)
print("IFA口播成片 · %s（%s %s，Python %s）\n技能目录：%s" % ("环境自检" if CHECK else "安装", OSN, ARCH, platform.python_version(), SKILL), flush=True)

# ---------- 1. Python 库 ----------
print("── 1／7 Python 库", flush=True)
need = [("numpy", "numpy"), ("PIL", "pillow"), ("fontTools", "fonttools")]
opt = [] if MAC else [("cv2", "opencv-python-headless")]   # macOS 的人脸检测用系统自带的 Vision
if sys.version_info < (3, 9):
    fail("Python %s 太旧" % platform.python_version(), "装 Python 3.9 以上")


def missing(mods):
    return [pkg for mod, pkg in mods if sh([PY, "-c", "import " + mod], 60).returncode != 0]


miss = missing(need + opt)
if miss and not CHECK and "pip" not in SKIP:
    cn = reachable("https://pypi.tuna.tsinghua.edu.cn/simple/pip/")
    org = reachable("https://pypi.org/simple/pip/")
    idx = ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"] if cn is not None and (org is None or cn <= org * 1.5) else []
    print("     · pip 安装 %s（%s）" % (" ".join(miss), "清华镜像" if idx else "官方源"), flush=True)
    r = sh([PY, "-m", "pip", "install", "--disable-pip-version-check", "--timeout", "30"] + idx + miss, 900)
    if r.returncode != 0 and "externally-managed" in (r.stderr or ""):
        r = sh([PY, "-m", "pip", "install", "--user", "--break-system-packages", "--timeout", "30"] + idx + miss, 900)
    miss = missing(need + opt)
for mod, pkg in need:
    good("python 库 " + pkg) if pkg not in miss else fail("缺 python 库 " + pkg, "%s -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple %s" % (os.path.basename(PY), pkg))
for mod, pkg in opt:
    good("python 库 %s（人脸检测）" % pkg) if pkg not in miss else note("没有 %s：人脸检测用不了，逐句的「人脸正不正」会记成未知" % pkg,
                                                                   "%s -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple %s" % (os.path.basename(PY), pkg))

# ---------- 2. ffmpeg／ffprobe ----------
print("── 2／7 ffmpeg／ffprobe", flush=True)
FILTERS = ["loudnorm", "sidechaincompress", "acompressor", "afftdn", "alimiter", "minterpolate", "colorspace", "ebur128", "boxblur"]


def ffmpeg_ok():
    if not (has("ffmpeg") and has("ffprobe")):
        return False, "没有 ffmpeg／ffprobe"
    f = sh(["ffmpeg", "-hide_banner", "-filters"], 30).stdout or ""
    lack = [x for x in FILTERS if (" %s " % x) not in f]
    e = sh(["ffmpeg", "-hide_banner", "-encoders"], 30).stdout or ""
    if "libx264" not in e and "h264_videotoolbox" not in e:
        lack.append("H.264 编码器")
    return (not lack), ("缺 " + "、".join(lack) if lack else "")


okf, why = ffmpeg_ok()
if not okf and not CHECK and "ffmpeg" not in SKIP:
    # 自己下一份静态版放进 ~/.cache/ifa-koubo/bin（kb.py 会把它排在 PATH 最前，不用改系统环境变量）
    os.makedirs(BIN, exist_ok=True)
    for k in ("ffmpeg", "ffprobe"):
        fn, urls, size = P_[k]
        gz = os.path.join(CACHE, "dl", fn)
        exe = os.path.join(BIN, k + (".exe" if WIN else ""))
        if download(urls, gz, size, limit=600, label=k):
            with gzip.open(gz, "rb") as src, open(exe, "wb") as f:
                shutil.copyfileobj(src, f)
            if not WIN:
                os.chmod(exe, 0o755)
    os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")
    okf, why = ffmpeg_ok()
if okf:
    good("ffmpeg／ffprobe（滤镜齐全）：%s" % shutil.which("ffmpeg"))
    e = sh(["ffmpeg", "-hide_banner", "-encoders"], 30).stdout or ""
    print("     · 中间文件编码：%s" % ("VideoToolbox 硬件编码" if "h264_videotoolbox" in e else "libx264 veryfast"), flush=True)
else:
    fail("ffmpeg 不可用（%s）" % why, {"mac": "brew install ffmpeg", "win": "重跑本脚本（会自动下一份），或 winget install Gyan.FFmpeg",
                                  "linux": "apt install ffmpeg，或重跑本脚本自动下静态版"}[OSN])

# ---------- 3. Node ----------
print("── 3／7 Node.js", flush=True)
NODE_DIR = os.path.join(CACHE, "node")
if os.path.isdir(NODE_DIR):
    os.environ["PATH"] = NODE_DIR + os.pathsep + os.environ.get("PATH", "")


def node_ver():
    r = sh(["node", "-v"], 20)
    try:
        return int((r.stdout or "").strip().lstrip("v").split(".")[0])
    except Exception:
        return 0


if node_ver() < 18 and WIN and not CHECK and "node" not in SKIP:
    fn, urls, size = P_["node"]
    zp = os.path.join(CACHE, "dl", fn)
    if download(urls, zp, size, limit=600, label="Node.js 便携版"):
        shutil.rmtree(NODE_DIR, ignore_errors=True)
        unzip(zp, NODE_DIR, strip_prefix=fn[:-4] + "/")
        os.environ["PATH"] = NODE_DIR + os.pathsep + os.environ.get("PATH", "")
nv = node_ver()
if nv >= 18:
    good("node %s：%s" % (sh(["node", "-v"], 20).stdout.strip(), shutil.which("node")))
else:
    fail("没有 Node.js（要 18 以上）", {"mac": "brew install node", "win": "重跑本脚本（会自动下便携版），或 winget install OpenJS.NodeJS.LTS",
                                  "linux": "装 Node 18+：https://npmmirror.com/mirrors/node/"}[OSN])

# ---------- 4. Remotion 运行时 ----------
print("── 4／7 Remotion 运行时（runtime/，所有工程共用，只装一次）", flush=True)
if not os.path.isdir(os.path.join(NM, "remotion")) and nv >= 18 and not CHECK and "npm" not in SKIP:
    # 国内直连 npmjs 很慢、挂代理时 npmmirror 又可能不通：两个都测，用通的、快的那个
    cn, org = reachable("https://registry.npmmirror.com/remotion"), reachable("https://registry.npmjs.org/remotion")
    regs = sorted([(t, u) for t, u in ((cn, "https://registry.npmmirror.com/"), (org, "https://registry.npmjs.org/")) if t is not None])
    if not regs:
        regs = [(0, "https://registry.npmmirror.com/"), (0, "https://registry.npmjs.org/")]
    for _t, reg in regs:
        print("     · npm install（%s），约 350MB、几百个包，通常 1–3 分钟；15 分钟没装完会停" % reg.split("/")[2], flush=True)
        t0 = time.time()
        try:
            pr = subprocess.Popen(npm(["install", "--registry=" + reg, "--no-audit", "--no-fund", "--loglevel=error",
                                       "--fetch-retries=2", "--fetch-timeout=60000"]), cwd=RT)
            while pr.poll() is None:
                time.sleep(5)
                if int(time.time() - t0) % 30 < 5:
                    print("     · 还在装……%d 秒" % (time.time() - t0), flush=True)
                if time.time() - t0 > 900:
                    pr.kill()
                    break
        except OSError as e:
            print("     · npm 起不来：%s" % e, flush=True)
        if os.path.isdir(os.path.join(NM, "remotion")):
            break
if os.path.isdir(os.path.join(NM, "remotion")):
    try:
        ver = json.load(open(os.path.join(NM, "remotion", "package.json"), encoding="utf-8"))["version"]
    except Exception:
        ver = "?"
    comp = [d for d in os.listdir(os.path.join(NM, "@remotion")) if d.startswith("compositor-")]
    good("remotion %s（%s）" % (ver, "、".join(comp) or "⚠ 没有本机的 compositor 包"))
    if not comp:
        fail("runtime/node_modules 不是在这台机器上装的（缺本机的 compositor）", "删掉 runtime/node_modules 后重跑本脚本")
else:
    fail("Remotion 运行时没装上", "cd %s && npm install --registry=https://registry.npmmirror.com/" % RT)

# ---------- 5. 无头浏览器 ----------
print("── 5／7 无头浏览器（渲染用）", flush=True)
CV = chrome_version()
BR = os.path.join(NM, ".remotion", "chrome-headless-shell")
EXE = os.path.join(BR, CPLAT, "chrome-headless-shell-" + CPLAT, "chrome-headless-shell" + (".exe" if WIN else ""))


def browser_ok():
    try:
        return os.path.exists(EXE) and open(os.path.join(BR, "VERSION"), encoding="utf-8").read().strip() == CV
    except Exception:
        return False


if not browser_ok() and os.path.isdir(NM) and not CHECK and "browser" not in SKIP:
    # Remotion 自己会去 storage.googleapis.com 下（国内不通，会一直等到超时）：这里先从 npmmirror 下同一个版本、放到它找的位置
    fn, urls, size = P_["browser"]
    zp = os.path.join(CACHE, "dl", fn)
    if download(urls, zp, size, limit=900, label="无头浏览器 %s" % CV):
        shutil.rmtree(os.path.join(BR, CPLAT), ignore_errors=True)
        unzip(zp, os.path.join(BR, CPLAT))
        if os.path.exists(EXE):
            if not WIN:
                os.chmod(EXE, 0o755)
            open(os.path.join(BR, "VERSION"), "w", encoding="utf-8").write(CV)
if browser_ok():
    good("chrome-headless-shell %s" % CV)
else:
    fail("无头浏览器没装好（版本要 %s）" % CV, "重跑本脚本；或手动下载 %s 解压到 %s，并在 %s 里写一行 %s" % (
        P_["browser"][1][0], os.path.join(BR, CPLAT), os.path.join(BR, "VERSION"), CV))

# ---------- 6. 转写：whisper-cli＋模型 ----------
print("── 6／7 转写（whisper.cpp）", flush=True)
if not has("whisper-cli") and WIN and not CHECK and "whisper" not in SKIP:
    fn, urls, size = P_["whisper"]
    zp = os.path.join(CACHE, "dl", fn)
    if download(urls, zp, size, limit=300, label="whisper-cli"):
        os.makedirs(BIN, exist_ok=True)
        unzip(zp, BIN, strip_prefix="Release/")
        os.environ["PATH"] = BIN + os.pathsep + os.environ.get("PATH", "")
if has("whisper-cli"):
    good("whisper-cli：%s" % shutil.which("whisper-cli"))
else:
    fail("没有 whisper-cli", {"mac": "brew install whisper-cpp", "win": "重跑本脚本；或手动下 whisper-bin-x64.zip（whisper.cpp 的 GitHub 发布页），把 Release 里的文件放进 %s" % BIN,
                           "linux": "编译 https://github.com/ggml-org/whisper.cpp ，把 whisper-cli 放进 PATH 或 %s" % BIN}[OSN])
MODEL = kb.whisper_model()
if not os.path.exists(MODEL) and not CHECK and "model" not in SKIP:
    fn, urls, size = P_["model"]
    MODEL = os.path.join(os.path.dirname(MODEL), fn)
    download(urls, MODEL, size, limit=1500, label="转写模型 %s" % fn)
    MODEL = kb.whisper_model()
if os.path.exists(MODEL):
    good("转写模型 %s（%d MB）" % (MODEL, os.path.getsize(MODEL) >> 20))
else:
    fail("缺转写模型", "重跑本脚本（断点续传）；或手动下 %s 放到 %s；已有别的 ggml 模型就设环境变量 WHISPER_MODEL" % (
        P_["model"][1][0], os.path.dirname(MODEL)))

# ---------- 7. 随包文件与可选项 ----------
print("── 7／7 随包文件与可选项", flush=True)
for f in ("SourceHanSerifSC-Heavy.otf", "SourceHanSerifSC-SemiBold.otf", "BodoniModa.ttf"):
    good("字体 " + f) if os.path.exists(os.path.join(SKILL, "assets", "fonts", f)) else fail("缺字体 " + f, "从仓库重新取 assets/fonts/")
packs = ["fullbleed", "editorial", "glass", "kinetic", "evidence", "diagram", "brand", "info", "forms", "parts"]
lack = [f for f in packs if not os.path.exists(os.path.join(SKILL, "template", "remotion", "src", "packs", f + ".tsx"))]
good("七套风格包与信息卡") if not lack else fail("缺版式文件：" + "、".join(lack), "从仓库重新取 template/remotion/src/packs/")
if MAC:
    for nm_ in ("face", "text"):
        good("macOS Vision：%s" % nm_) if kb.vision_bin(nm_) else note("Vision %s 没编译出来（要 Xcode 命令行工具）" % nm_, "xcode-select --install")
else:
    _f, how = (None, "")
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            _f, how = kb.detect_faces(td)
    except Exception:
        pass
    good("人脸检测：%s" % how) if how else note("没有人脸检测", "pip 装 opencv-python-headless")
    note("这个系统没有画面文字识别（只有 macOS 有）：候选素材不会自动标「字」，B-roll 里的可读文字要人看抽帧图")
    note("字幕正文用系统黑体（Windows＝微软雅黑，Linux＝Noto Sans CJK）；和 macOS 的苹方字形略有差别，版式不变")
if has("firecrawl"):
    good("firecrawl CLI（Pexels 搜索页）")
else:
    print("  ·  没有 firecrawl：Pexels 走搜索页那条路用不了。设了 PEXELS_API_KEY（免费）就走官方 API，或只用 Coverr／Mixkit／Pixabay", flush=True)
for v in ("PEXELS_API_KEY", "PIXABAY_API_KEY"):
    print("  ·  %s：%s" % (v, "已设" if os.environ.get(v) else "未设（免费申请，素材多一条路）"), flush=True)

# ---------- 冒烟：渲一帧 ----------
if a.smoke and not bad:
    print("── 冒烟：用模板渲一帧", flush=True)
    import tempfile
    td = tempfile.mkdtemp(prefix="ifa_smoke_")
    R = os.path.join(td, "remotion")
    shutil.copytree(os.path.join(SKILL, "template", "remotion"), R, ignore=shutil.ignore_patterns("node_modules", "out"))
    # 一秒测试图案当原片＋一行字幕：这一帧同时过了打包、无头浏览器、视频解码（合成器）、文字渲染
    sh(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=1", "-pix_fmt", "yuv420p",
        os.path.join(R, "public", "aroll_cut.mp4")], 120)
    json.dump({"fps": 30, "width": 1080, "height": 1920, "durationInFrames": 30, "style": "fullbleed", "outro": 0, "theme": {"name": "琥珀金"}, "account": "",
               "aroll": {"src": "aroll_cut.mp4", "face": {"cx": 0.5, "cy": 0.42, "w": 0.3}, "frame": {}}, "shots": [],
               "captions": [{"from": 0, "to": 30, "lines": [{"text": "安装自检：这一帧渲出来就是通的", "from": 0}]}],
               "arollZoom": [], "masthead": None, "nametag": None, "cover": None, "end": None, "sfx": []},
              open(os.path.join(R, "src", "timeline.json"), "w", encoding="utf-8"), ensure_ascii=False)
    if kb.link_dir(NM, os.path.join(R, "node_modules")):
        t0 = time.time()
        out = os.path.join(CACHE, "smoke.jpg")
        if os.path.exists(out):
            os.remove(out)
        r = sh(kb.remotion_cmd(R) + ["still", "src/index.ts", "Film", out, "--frame=10", "--log=error"], 300, cwd=R)
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 20000:
            good("渲出一帧（%.0f 秒）：打包、无头浏览器、视频解码、文字都通 → %s" % (time.time() - t0, out))
        else:
            fail("冒烟渲染失败", ((r.stderr or r.stdout) or "")[-600:])
    else:
        fail("建不了 node_modules 的链接", "Windows：打开「开发者模式」，或确认技能目录在 NTFS 盘上")
    try:   # 先解开链接再删，别顺着链接把共享运行时删了
        lk = os.path.join(R, "node_modules")
        os.rmdir(lk) if WIN and not os.path.islink(lk) else os.unlink(lk)
    except OSError:
        pass
    if not os.path.lexists(os.path.join(R, "node_modules")):
        shutil.rmtree(td, ignore_errors=True)

print("── 结果：通过 %d　缺失 %d　提醒 %d" % (ok_n, len(bad), len(warn)), flush=True)
if bad:
    print("还缺这些（照箭头后面的做；%s）：" % ("本次只检查、没有改任何东西，要安装就去掉 --check 重跑" if CHECK else "多数重跑一次本脚本就能续上"))
    for m, fx in bad:
        print("  · %s → %s" % (m, fx))
    sys.exit(1)
print("[doctor] OK" if CHECK else "[setup] OK　下一步：%s %s <原片> <工程目录>" % (os.path.basename(PY), os.path.join(SKILL, "scripts", "new_project.py")))
