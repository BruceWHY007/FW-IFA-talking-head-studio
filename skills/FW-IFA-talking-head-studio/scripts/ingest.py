#!/usr/bin/env python3
"""① 导入：原片归一化 → 转写（逐字时间）→ 能量包络与停顿 → 2 秒一格的总览图。

    python3 ingest.py <工程目录> [--model ~/.cache/whisper-cpp/ggml-small.bin] [--prompt "术语提示"]

产物：
  work/aroll.mp4          30fps CFR、竖版、H.264（源≥1440 宽时保留 1440×2560，给推镜留余量）
  work/voice.wav          48k 单声道原声
  work/asr_full.json      whisper-cli 原始输出
  work/energy.json        10ms 能量包络（dBFS）与停顿表
  transcript.json         句表（text 待校对；raw_text/chars 是对齐用的原始转写，不要改）
  work/sheet_2s.jpg       每 2 秒一格的原片总览
"""
import argparse, glob, json, os, re, sys, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, probe, save, load, die, has, encoder_args, read_audio_mono, energy_db, hms, font

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", os.path.expanduser("~/.cache/whisper-cpp/ggml-small.bin")))
ap.add_argument("--prompt", default="")
ap.add_argument("--crop-x", type=float, default=None, help="横版源裁竖版时的主体水平中心（0–1），缺省按人脸")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
raws = glob.glob(P(proj, "source", "raw.*"))
if not raws:
    die("source/ 下没有 raw.*，先跑 new_project.py")
raw = raws[0]
info = probe(raw)
v = info["video"]
if not v:
    die("原片没有视频流")

# ---------- 1. 归一化 A-roll ----------
out_v = P(proj, "work", "aroll.mp4")
portrait = v["h"] >= v["w"]
tw, th = (1440, 2560) if min(v["w"], v["h"]) >= 1440 else (1080, 1920)
if not os.path.exists(out_v):
    ct = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
              "-of", "csv=p=0", raw]).stdout.strip()
    vf = []
    if ct in ("arib-std-b67", "smpte2084"):
        # HDR（iPhone HLG）→ SDR。没有 zscale 时用 colorspace 近似，色调交给后面统一调色。
        vf.append("colorspace=all=bt709:trc=bt709:format=yuv420p")
        print("· 源是 HDR（%s），已转 SDR；肤色请在总览图里看一眼" % ct)
    if portrait:
        vf.append("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d" % (tw, th, tw, th))
    else:
        cx = a.crop_x if a.crop_x is not None else 0.5
        cw = "ih*9/16"
        vf.append("crop=%s:ih:(iw-%s)*%.3f:0,scale=%d:%d" % (cw, cw, cx, tw, th))
        print("· 横版源裁成竖版，主体中心 x=%.2f（不对就用 --crop-x 重跑）" % cx)
    vf.append("fps=30")
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vf", ",".join(vf)] + encoder_args("high") +
        ["-an", "-movflags", "+faststart", out_v])
out_a = P(proj, "work", "voice.wav")
if not os.path.exists(out_a):
    run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-vn", "-ac", "1", "-ar", "48000", out_a])
dur = probe(out_v)["duration"]
print("✓ A-roll %dx%d 30fps %.2fs" % (tw, th, dur))

# ---------- 2. 转写（whisper-cli，逐 token 毫秒偏移） ----------
asr = P(proj, "work", "asr_full.json")
if not os.path.exists(asr):
    if not has("whisper-cli"):
        die("没有 whisper-cli（brew install whisper-cpp），或把逐字 SRT 放到 work/asr.srt 再改本脚本走 --srt")
    if not os.path.exists(a.model):
        die("缺 whisper 模型 %s（ggml-small 约 466MB，下载要限时并告知用户）" % a.model)
    wav16 = P(proj, "work", "a16.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", out_a, "-ac", "1", "-ar", "16000", wav16])
    prompt = "以下是普通话的句子，使用简体中文。" + a.prompt
    run(["whisper-cli", "-m", a.model, "-l", "zh", "-f", wav16, "-ojf", "-of", asr[:-5],
         "--prompt", prompt, "-t", "8", "-mc", "0"])
d = json.loads(open(asr, "rb").read().decode("utf-8", "replace"))

PUNCT = "，。！？、；：,.!?;:"
chars = []  # 每个字一条：c, s, e, seg（whisper 分段号，分段边界就是句边界）, w（whisper 词号：同一个 token 里的字不在中间断行）
wid = 0
for si, seg in enumerate(d.get("transcription", [])):
    for t in seg.get("tokens", []):
        wid += 1
        txt = t.get("text", "")
        if txt.startswith("[_") or not txt.strip():
            continue
        s, e = t["offsets"]["from"] / 1000.0, t["offsets"]["to"] / 1000.0
        cs = [c for c in txt if c.strip() and c != "�"]
        if not cs:
            continue
        step = (e - s) / max(len(cs), 1)
        for i, c in enumerate(cs):
            chars.append({"c": c, "s": round(s + i * step, 3), "e": round(s + (i + 1) * step, 3), "seg": si, "w": wid})

# ---------- 3. 能量包络与停顿（与转写无关，直接量声音） ----------
x = read_audio_mono(out_a, 16000)
db = energy_db(x, 16000, 0.01)
import numpy as np
speech_lvl = float(np.percentile(db, 90))
floor_lvl = float(np.percentile(db, 3))
# 房间底噪常在 -55 dB 上下，用「底噪＋30% 动态」做门限，比「人声−30dB」稳
thr = floor_lvl + 0.3 * (speech_lvl - floor_lvl)
sil = db < thr
pauses, st = [], None
for i, s_ in enumerate(sil):
    if s_ and st is None:
        st = i
    elif not s_ and st is not None:
        if i - st >= 25:  # ≥250ms
            pauses.append([round(st / 100, 2), round(i / 100, 2)])
        st = None
if st is not None and len(sil) - st >= 25:
    pauses.append([round(st / 100, 2), round(len(sil) / 100, 2)])
save(P(proj, "work", "energy.json"), {"hop": 0.01, "speech_p90_db": speech_lvl, "floor_p3_db": floor_lvl, "silence_thr_db": thr,
                                      "pauses": pauses, "db": [round(float(v_), 1) for v_ in db]})

def in_pause(t):
    for p0, p1 in pauses:
        if p0 <= t < p1:
            return p0, p1
    return None

# ---------- 4. 句表：whisper 分段 / 句末标点 / 长停顿处切句 ----------
sents, cur = [], []
def flush():
    if cur:
        sents.append(cur[:])
        cur.clear()
for i, ch in enumerate(chars):
    cur.append(ch)
    nxt = chars[i + 1] if i + 1 < len(chars) else None
    gap = (nxt["s"] - ch["e"]) if nxt else 9
    if ch["c"] in "。！？!?" or gap > 0.6 or (nxt and nxt["seg"] != ch["seg"]):
        flush()
flush()
# 碎句并进前一句：<1.0s 或 ≤2 个字、且与前句间隔 <0.3s（whisper 常把「放心」「布局」单切一段）
merged = []
for cs in sents:
    d_ = cs[-1]["e"] - cs[0]["s"]
    if merged and (d_ < 1.0 or len(cs) <= 2) and cs[0]["s"] - merged[-1][-1]["e"] < 0.3:
        merged[-1].extend(cs)
    else:
        merged.append(cs)
sents = merged
# 句首尾吸附到真实停顿（whisper 的段界常落在整秒上，能量包络更可信），句内字时间按比例重排
for cs in sents:
    s0, e0 = cs[0]["s"], cs[-1]["e"]
    s1, e1 = s0, e0
    hit = in_pause(s0)
    if hit:
        s1 = hit[1]
    hit = in_pause(e0 - 0.01)
    if hit and hit[0] > s1 + 0.3:
        e1 = hit[0]
    if e1 - s1 < 0.3:
        s1, e1 = s0, e0
    k = (e1 - s1) / max(e0 - s0, 1e-3)
    for ch in cs:
        ch["s"] = round(s1 + (ch["s"] - s0) * k, 3)
        ch["e"] = round(s1 + (ch["e"] - s0) * k, 3)
        ch.pop("seg", None)
tr = {"_说明": "只改 text（校对错字、人名、术语、数字口径）；raw_text 和 chars 是对齐用的，别动。"
               "要删的整句（重说、废句）写 \"drop\": true；要剪掉的口癖在 edits.json 里写。",
      "sentences": []}
for k, cs in enumerate(sents):
    t = "".join(c["c"] for c in cs)
    tr["sentences"].append({"id": "s%02d" % (k + 1), "text": t, "raw_text": t,
                            "start": cs[0]["s"], "end": cs[-1]["e"], "chars": cs})
tp = P(proj, "transcript.json")
if os.path.exists(tp) and load(tp).get("_corrected"):
    print("· transcript.json 已校对过，不覆盖；新转写在 work/transcript_asr.json")
    save(P(proj, "work", "transcript_asr.json"), tr)
else:
    save(tp, tr)

# ---------- 5. 总览图：每 2 秒一格 ----------
from PIL import Image, ImageDraw
sheet = P(proj, "work", "sheet_2s.jpg")
tmpd = P(proj, "work", "_f2s")
os.makedirs(tmpd, exist_ok=True)
run(["ffmpeg", "-v", "error", "-y", "-i", out_v, "-vf", "fps=1/2,scale=180:320", P(tmpd, "f%04d.jpg")])
fs = sorted(glob.glob(P(tmpd, "f*.jpg")))
cols = 12
rows = (len(fs) + cols - 1) // cols
img = Image.new("RGB", (cols * 180, rows * 340), "black")
dr = ImageDraw.Draw(img)
fnt = font(18)
for i, f in enumerate(fs):
    im = Image.open(f)
    x0, y0 = (i % cols) * 180, (i // cols) * 340
    img.paste(im, (x0, y0))
    t = i * 2
    said = "".join(c["c"] for c in chars if t <= c["s"] < t + 2)[:9]
    dr.text((x0 + 4, y0 + 322), "%s %s" % (hms(t), said), fill="white", font=fnt)
img.save(sheet, quality=82)
for f in fs:
    os.remove(f)

n = len(tr["sentences"])
rate = len(chars) / max(sum(s["end"] - s["start"] for s in tr["sentences"]), 1)
print("✓ 转写 %d 句 %d 字，净语速 %.2f 字/秒；停顿≥0.25s 共 %d 处" % (n, len(chars), rate, len(pauses)))
print("  下一步：校对 transcript.json 的 text（改完加 \"_corrected\": true），再跑 analyze.py")
