"""IFA口播成片 共享工具：路径、ffmpeg/ffprobe、json、时间换算。只依赖 Python 3.9 标准库 + numpy。"""
import json, os, subprocess, sys, shutil

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 30
W, H = 1080, 1920


def die(msg):
    print("✗ " + msg, file=sys.stderr)
    sys.exit(1)


def run(cmd, quiet=True, check=True):
    r = subprocess.run(cmd, capture_output=True, text=True)
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


def encoder_args(quality="high"):
    """预处理统一用 VideoToolbox（风扇与速度，见父 skill references/04 §十）；没有就退回 libx264。"""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-encoders"], capture_output=True, text=True)
    if "h264_videotoolbox" in r.stdout:
        q = {"high": "85", "mid": "70"}[quality]
        return ["-c:v", "h264_videotoolbox", "-q:v", q, "-allow_sw", "1", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "16" if quality == "high" else "20", "-pix_fmt", "yuv420p"]


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


def font(size, bold=False):
    from PIL import ImageFont
    for p in ["/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/System/Library/Fonts/Helvetica.ttc"]:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


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
    cache_p = os.path.expanduser("~/.cache/ifa-koubo/cuts.json")
    try:
        cache = _j.load(open(cache_p))
    except Exception:
        cache = {}
    key = "%s|%d" % (path, int(os.path.getmtime(path)))
    if key in cache:
        return cache[key]
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-vf", "scale=160:-2,select='gt(scene,%s)',showinfo" % thr,
                        "-an", "-f", "null", "-"], capture_output=True, text=True).stderr
    cuts = [round(float(x), 3) for x in _re.findall(r"pts_time:([\d.]+)", r)]
    cache[key] = cuts
    os.makedirs(os.path.dirname(cache_p), exist_ok=True)
    _j.dump(cache, open(cache_p, "w"))
    return cuts
