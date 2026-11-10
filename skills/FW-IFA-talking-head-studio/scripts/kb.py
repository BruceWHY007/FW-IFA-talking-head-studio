"""IFA口播成片 共享工具：路径、ffmpeg/ffprobe、json、时间换算。只依赖 Python 3.9 标准库 + numpy。
macOS／Windows／Linux 通用：所有脚本都先 import 这个文件，平台差异只在这里处理。"""
import json, os, subprocess, sys, shutil

WIN = os.name == "nt"
MAC = sys.platform == "darwin"
# Windows 中文系统的默认编码是 GBK：读 UTF-8 的 json 会报错，打印 ✓ ⚠ 会直接崩。
# 不是 UTF-8 模式就用 UTF-8 模式把当前脚本重启一次（只重启一次），之后 open()／print()／子进程输出都按 UTF-8。
if WIN and not sys.flags.utf8_mode and os.environ.get("IFA_KOUBO_UTF8") != "1" and sys.argv and os.path.isfile(sys.argv[0]):
    _env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", IFA_KOUBO_UTF8="1")
    sys.exit(subprocess.call([sys.executable, "-X", "utf8"] + sys.argv, env=_env))
os.environ.setdefault("PYTHONUTF8", "1")           # 子进程里的 Python 也用 UTF-8
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")           # 终端显示不了的字符换成 ?，不让脚本崩
    except Exception:
        pass

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "ifa-koubo")
# setup.py 把自己下载的工具（Windows 上的 ffmpeg／ffprobe／whisper-cli）放在这里；排在 PATH 最前，不用用户改系统环境变量
BIN = os.path.join(CACHE, "bin")
for _d in (os.path.join(CACHE, "node"), BIN):     # node：Windows 上没装 Node 时 setup.py 下的便携版
    if os.path.isdir(_d) and _d not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
PY = sys.executable                                 # 提示里的命令用它：Windows 上没有 python3 这个命令
FPS = 30
W, H = 1080, 1920


def die(msg):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(1)


def run(cmd, quiet=True, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        die("命令失败：%s\n%s" % (" ".join(cmd[:6]), r.stderr[-1500:]))
    return r


def probe(path):
    r = run(["ffprobe", "-v", "error", "-show_entries",
             "stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,sample_rate,channels:"
             "stream_side_data=rotation:stream_tags=rotate:format=duration",
             "-of", "json", path])
    d = json.loads(r.stdout)
    v = next((s for s in d.get("streams", []) if s.get("codec_type") == "video"), None)
    a = next((s for s in d.get("streams", []) if s.get("codec_type") == "audio"), None)
    out = {"duration": float(d.get("format", {}).get("duration", 0) or 0), "video": None, "audio": None}
    if v:
        rot = 0
        for sd in v.get("side_data_list", []) or []:
            if "rotation" in sd:
                rot = int(float(sd["rotation"]))
        if "tags" in v and "rotate" in v["tags"]:
            rot = int(v["tags"]["rotate"])
        w, h = v["width"], v["height"]
        if abs(rot) in (90, 270):
            w, h = h, w
        num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
        fps = float(num) / float(den) if float(den) else 30.0
        out["video"] = {"w": w, "h": h, "fps": round(fps, 3), "codec": v.get("codec_name")}
    if a:
        out["audio"] = {"sr": int(a.get("sample_rate", 0)), "ch": a.get("channels")}
    return out


def load(path, default=None):
    if not os.path.exists(path):
        if default is not None:
            return default
        die("找不到 %s" % path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(path, obj):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def P(proj, *parts):
    return os.path.join(os.path.abspath(proj), *parts)


def fr(t):
    """秒 → 帧（四舍五入到帧网格）。"""
    return int(round(t * FPS))


def snap(t):
    return fr(t) / FPS


def hms(t):
    m, s = divmod(max(t, 0), 60)
    return "%d:%05.2f" % (m, s)


def has(cmd):
    return shutil.which(cmd) is not None


_ENC = []


def encoder_args(quality="high"):
    """中间文件的编码：macOS 用 VideoToolbox 硬件编码（风扇与速度）；其他系统用 libx264 的 veryfast 档
    （中间文件只给渲染读一遍，不追求体积；比 medium 档快 3 倍左右，画质由 crf 定、不变）。"""
    if not _ENC:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True, encoding="utf-8", errors="replace")
        _ENC.append("h264_videotoolbox" in (r.stdout or ""))
    if _ENC[0]:
        q = {"high": "85", "mid": "70"}[quality]
        return ["-c:v", "h264_videotoolbox", "-q:v", q, "-allow_sw", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "16" if quality == "high" else "20", "-pix_fmt", "yuv420p"]


def read_gray_frames(path, w, h, fps, t0=None, dur=None):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error"]
    if t0 is not None:
        cmd += ["-ss", "%.3f" % t0]
    cmd += ["-i", path]
    if dur is not None:
        cmd += ["-t", "%.3f" % dur]
    cmd += ["-vf", "fps=%s,scale=%d:%d,format=gray" % (fps, w, h), "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    n = len(raw) // (w * h)
    return np.frombuffer(raw[: n * w * h], dtype=np.uint8).reshape(n, h, w).astype(np.float32)


def read_audio_mono(path, sr=16000):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "s16le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def energy_db(x, sr=16000, hop_s=0.01):
    import numpy as np
    hop = int(sr * hop_s)
    n = len(x) // hop
    frames = x[: n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1) + 1e-12)
    return 20 * np.log10(rms)


_FONT_CANDS = [
    "/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",          # macOS
    "C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc", "C:/Windows/Fonts/simhei.ttf",       # Windows：微软雅黑／黑体
    "C:/Windows/Fonts/Deng.ttf", "C:/Windows/Fonts/simsun.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",   # Linux
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    os.path.join(SKILL, "assets", "fonts", "SourceHanSerifSC-SemiBold.otf"),                           # 都没有：用随包的思源宋体（保证总览图里的中文不是方框）
    "/System/Library/Fonts/Helvetica.ttc",
]
_FONT_PATH = []


def font(size, bold=False):
    """总览图、审片表上写字用的字体（要能显示中文）。按平台找系统黑体，找不到用随包的思源宋体。"""
    from PIL import ImageFont
    if not _FONT_PATH:
        _FONT_PATH.append(next((p for p in _FONT_CANDS if os.path.exists(p)), ""))
    if _FONT_PATH[0]:
        try:
            return ImageFont.truetype(_FONT_PATH[0], size)
        except Exception:
            pass
    return ImageFont.load_default()


# ---------- 跨平台：链接、外部工具、转写模型、人脸检测 ----------
def link_file(src, dst):
    """把大文件「放」到 dst 而不多占空间：软链 → 硬链 → 复制。Windows 没开开发者模式时软链会被拒绝，自动退到后两种。"""
    if os.path.lexists(dst):
        return "已存在"
    for how, fn in (("软链", os.symlink), ("硬链", os.link), ("复制", shutil.copy2)):
        try:
            fn(src, dst)
            return how
        except OSError:
            continue
    die("放不进去：%s → %s" % (src, dst))


def link_dir(src, dst):
    """目录链接：软链；Windows 上退到目录联接（junction，不需要管理员权限）。都不行就返回空串，由调用方决定怎么办。"""
    if os.path.lexists(dst):
        return "已存在"
    try:
        os.symlink(src, dst, target_is_directory=True)
        return "软链"
    except OSError:
        pass
    if WIN:
        r = subprocess.run(["cmd", "/c", "mklink", "/J", dst, src], capture_output=True)
        if r.returncode == 0:
            return "目录联接"
    return ""


def remotion_cmd(R):
    """Remotion 命令行：直接用 node 跑工程里的 cli（不走 npx——Windows 上 npx 是 .cmd，子进程直接叫会找不到；也省掉 npx 自己的启动时间）。"""
    cli = os.path.join(R, "node_modules", "@remotion", "cli", "remotion-cli.js")
    if not os.path.exists(cli):
        die("Remotion 运行时没装好（找不到 %s）：先跑 %s %s" % (cli, os.path.basename(PY), os.path.join(SKILL, "scripts", "setup.py")))
    return [shutil.which("node") or "node", cli]


def cpu_threads(cap=8):
    return max(1, min(cap, os.cpu_count() or 4))


def ram_gb():
    """物理内存（GB）；量不到返回 0。"""
    try:
        if WIN:
            import ctypes

            class _MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                           [(n, ctypes.c_ulonglong) for n in ("ullTotalPhys", "ullAvailPhys", "ullTotalPageFile", "ullAvailPageFile",
                                                              "ullTotalVirtual", "ullAvailVirtual", "ullAvailExtendedVirtual")]
            m = _MS(); m.dwLength = ctypes.sizeof(_MS)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 2 ** 30
        if MAC:
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout.strip() or 0) / 2 ** 30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    except Exception:
        return 0


def render_concurrency():
    """渲染并发：环境变量 IFA_RENDER_CONCURRENCY 优先；否则按核数与内存定，最多 3（实测再高不更快、长片更容易断）。
    每个并发约占 1.5–2GB 内存：8GB 的机器 1 个，16GB 2–3 个。"""
    env = os.environ.get("IFA_RENDER_CONCURRENCY", "").strip()
    if env.isdigit() and int(env) >= 1:
        return int(env)
    cores, ram = os.cpu_count() or 4, ram_gb()
    by_ram = 3 if not ram else max(1, int(ram // 5))
    return max(1, min(3, cores // 3 or 1, by_ram))


def whisper_model():
    """转写模型：环境变量 WHISPER_MODEL → ~/.cache/whisper-cpp/ 下的 small → small 量化版 → 其他 ggml 模型。"""
    env = os.environ.get("WHISPER_MODEL")
    if env:
        return os.path.expanduser(env)
    d = os.path.join(os.path.expanduser("~"), ".cache", "whisper-cpp")
    for n in ("ggml-small.bin", "ggml-small-q5_1.bin", "ggml-medium-q5_0.bin", "ggml-medium.bin", "ggml-base.bin"):
        if os.path.exists(os.path.join(d, n)):
            return os.path.join(d, n)
    return os.path.join(d, "ggml-small.bin")


_T2S = {}
_T2S_FIX = (("着名", "著名"), ("显着", "显著"), ("着作", "著作"), ("着称", "著称"), ("土着", "土著"), ("卓着", "卓著"), ("编着", "编著"))


def t2s(text):
    """繁体转简体（逐字，一对一，不改字数，所以逐字时间不受影响）。转写经常整段出繁体：在脚本里统一转掉，不靠人逐句改。
    字表 scripts/t2s.txt 由系统的 Hant-Hans 转换生成（3048 对）；「著／着」这类一对多的按常见词修正。"""
    if not _T2S:
        try:
            for p in open(os.path.join(SKILL, "scripts", "t2s.txt"), encoding="utf-8").read().split():
                if len(p) == 2:
                    _T2S[p[0]] = p[1]
        except OSError:
            _T2S["\0"] = "\0"
    out = "".join(_T2S.get(c, c) for c in text)
    for a_, b_ in _T2S_FIX:
        out = out.replace(a_, b_)
    return out


def has_trad(text):
    """这段字里还有没有繁体字（字表里的键）"""
    t2s("")
    return [c for c in text if c in _T2S]


def vision_bin(name):
    """macOS Vision 小工具（face／text）：首次用时编译到缓存目录；不是 macOS 或没有 swiftc 就返回空。"""
    if not MAC:
        return ""
    b = os.path.join(CACHE, name)
    if not os.path.exists(b) and has("swiftc"):
        os.makedirs(CACHE, exist_ok=True)
        subprocess.run(["swiftc", "-O", os.path.join(SKILL, "scripts", name + ".swift"), "-o", b], capture_output=True)
    return b if os.path.exists(b) else ""


def detect_faces(fd):
    """给一个目录里的 jpg 做人脸检测 → ({文件名: [{x,y,w,h,yaw,roll,conf}]}, 用的方法)。坐标 0–1、原点左上。
    macOS 用 Vision；其他系统用 OpenCV（装了 opencv-python-headless 就有，模型随包 232KB）；都没有 → (None, "")。
    返回 None 表示「没法检测」，不是「没有脸」——调用方不能把它当成无脸处理。"""
    b = vision_bin("face")
    if b:
        try:
            return json.loads(subprocess.run([b, fd], capture_output=True, text=True).stdout or "{}"), "vision"
        except Exception:
            pass
    try:
        import cv2, math
    except Exception:
        return None, ""
    files = sorted(f for f in os.listdir(fd) if f.lower().endswith(".jpg"))
    out = {}
    model = os.path.join(SKILL, "assets", "models", "face_detection_yunet_2023mar.onnx")
    if os.path.exists(model) and hasattr(cv2, "FaceDetectorYN"):
        det = None
        for f in files:
            im = cv2.imread(os.path.join(fd, f))
            if im is None:
                continue
            h, w = im.shape[:2]
            if det is None:
                det = cv2.FaceDetectorYN.create(model, "", (w, h), 0.6, 0.3, 50)
            det.setInputSize((w, h))
            _, res = det.detect(im)
            faces = []
            for r in (res if res is not None else []):
                x, y, fw, fh = [float(v) for v in r[:4]]
                rex, rey, lex, ley, nx, ny = [float(v) for v in r[4:10]]
                eye = max(math.hypot(lex - rex, ley - rey), 1.0)
                # 鼻尖偏离两眼中点的程度 → 偏航角（弧度）。按 Vision 的读数校准过：系数 0.7；框放大 1.22 倍（Vision 的框含额头与下巴）
                yaw = 0.7 * math.atan(2.0 * (nx - (rex + lex) / 2.0) / eye)
                roll = math.atan2(ley - rey, lex - rex)
                k = 1.22
                x, y, fw, fh = x - fw * (k - 1) / 2, y - fh * (k - 1) / 2, fw * k, fh * k
                faces.append({"x": x / w, "y": y / h, "w": fw / w, "h": fh / h, "yaw": yaw, "roll": roll, "conf": float(r[14])})
            out[f] = faces
        return out, "opencv-yunet"
    casc = cv2.CascadeClassifier(os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml"))
    for f in files:
        im = cv2.imread(os.path.join(fd, f), cv2.IMREAD_GRAYSCALE)
        if im is None:
            continue
        h, w = im.shape[:2]
        out[f] = [{"x": float(x) / w, "y": float(y) / h, "w": float(fw) / w, "h": float(fh) / h, "yaw": 0.0, "roll": 0.0, "conf": 0.7}
                  for (x, y, fw, fh) in casc.detectMultiScale(im, 1.1, 5, minSize=(int(w * 0.08), int(w * 0.08)))]
    return out, "opencv-haar"


def align_text(raw_chars, new_text):
    """把校对后的文字对齐到原始转写的逐字时间上。
    raw_chars: [{"c","s","e"}...]；new_text: 校对后的整句。返回 [{"c","s","e"}...]（与 new_text 等长，空白除外）。
    相同或替换的字直接继承时间，新增的字在前后两个有时间的字之间插值。"""
    import difflib, re
    raw = "".join(c["c"] for c in raw_chars)
    new = list(re.sub(r"\s+", " ", new_text.strip()))  # 保留英文词间空格（All in、Band 1）
    out = [None] * len(new)
    sm = difflib.SequenceMatcher(None, raw, "".join(new), autojunk=False)
    for tag, i0, i1, j0, j1 in sm.get_opcodes():
        if tag == "equal":
            for k in range(j1 - j0):
                r = raw_chars[i0 + k]
                out[j0 + k] = {"c": new[j0 + k], "s": r["s"], "e": r["e"], "w": r.get("w")}
        elif tag == "replace":
            s, e = raw_chars[i0]["s"], raw_chars[i1 - 1]["e"]
            n = j1 - j0
            for k in range(n):
                out[j0 + k] = {"c": new[j0 + k], "s": round(s + (e - s) * k / n, 3), "e": round(s + (e - s) * (k + 1) / n, 3),
                               "w": raw_chars[i0].get("w")}  # 改过的字算一个词（中午→中五）
    # 插值补齐 insert
    known = [i for i, o in enumerate(out) if o]
    if not known:
        s, e = raw_chars[0]["s"], raw_chars[-1]["e"]
        n = len(new)
        return [{"c": new[k], "s": s + (e - s) * k / n, "e": s + (e - s) * (k + 1) / n} for k in range(n)]
    i = 0
    while i < len(out):
        if out[i] is None:
            j = i
            while j < len(out) and out[j] is None:
                j += 1
            left = out[i - 1]["e"] if i > 0 else out[j]["s"]
            right = out[j]["s"] if j < len(out) else out[i - 1]["e"]
            n = j - i
            for k in range(n):
                out[i + k] = {"c": new[i + k], "s": round(left + (right - left) * k / n, 3),
                              "e": round(left + (right - left) * (k + 1) / n, 3)}
            i = j
        else:
            i += 1
    return out


def sentence_chars(sent):
    """句子的逐字时间（按校对后的 text 对齐）。"""
    if sent.get("text") == sent.get("raw_text"):
        return [dict(c) for c in sent["chars"]]
    return align_text(sent["chars"], sent["text"])


def clip_cuts(path, thr=0.32):
    """素材内部的剪辑点（秒）。很多成品素材（AI 片段、免费素材）一条里有好几个镜头，
    截取时跨过内部剪辑点＝成片里多出一个 0.3–0.5s 的闪镜。结果按路径＋修改时间缓存。"""
    import json as _j, re as _re
    cache_p = os.path.join(CACHE, "cuts.json")
    try:
        cache = _j.load(open(cache_p, encoding="utf-8"))
    except Exception:
        cache = {}
    key = "%s|%d" % (path, int(os.path.getmtime(path)))
    if key in cache:
        return cache[key]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "scale=160:-2,select='gt(scene,%s)',showinfo" % thr,
                        "-an", "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    cuts = [round(float(x), 3) for x in _re.findall(r"pts_time:([\d.]+)", r)]
    cache[key] = cuts
    os.makedirs(os.path.dirname(cache_p), exist_ok=True)
    _j.dump(cache, open(cache_p, "w", encoding="utf-8"))
    return cuts


# ---------- 句号锚点（10-30）：decompose 里可以直接写 "s17" 或 "s16–s19"，不用一字不差抄原话 ----------
# 弱一点的模型凭印象抄原话，十有八九差一两个字，build 就报「锚点找不到」；句号是 transcript 里现成的，抄不错。
import re as _re
SID_RE = _re.compile(r"^\s*(s\d+)\s*(?:[–—\-~～到至]\s*(s\d+))?\s*$")


def sid_span(anchor):
    """'s17' → ('s17','s17')；'s16–s19' → ('s16','s19')；不是句号写法 → None"""
    m = SID_RE.match(str(anchor or ""))
    return (m.group(1), m.group(2) or m.group(1)) if m else None


def cover_text(anchor, sentences):
    """把锚点换成可读的原话（给素材检索、审片表、提示用）。句号写法 → 那几句原话连起来；原话写法 → 原样返回。"""
    sp = sid_span(anchor)
    if not sp:
        return str(anchor or "")
    ids = [s["id"] for s in sentences]
    if sp[0] not in ids or sp[1] not in ids:
        return str(anchor)
    i0, i1 = ids.index(sp[0]), ids.index(sp[1])
    return "".join(s.get("text", "") for s in sentences[i0:i1 + 1])


def as_list(x):
    """检索词 q 等字段：写成字符串也当一条（10-30：q 写成字符串被逐字搜，取回「金属环」「街舞」）"""
    if x is None:
        return []
    return [x] if isinstance(x, str) else list(x)
