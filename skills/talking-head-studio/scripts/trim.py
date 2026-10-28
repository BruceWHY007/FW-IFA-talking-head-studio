#!/usr/bin/env python3
"""③ 粗剪：删重说、剪口癖、压长停顿。画面和声音用同一张 EDL 剪，逐帧同长。

    python3 trim.py <工程目录> [--dry-run]

读 transcript.json（校对后的 text、drop）与 edits.json：
  {
    "max_pause": 0.40,   停顿超过它就压
    "keep_pause": 0.20,  压到这么长（句间气口，别压到 0，人会像被掐住）
    "head": 0.12, "tail": 0.50,
    "cut": ["s03:那么", "s08:那么"],   句号:要剪的原话（按校对后文字找第一处）
    "keep": ["s25:那么"]               显式保留（覆盖自动口癖）
  }
切点先吸附到 ±60ms 内能量最低处，再落到 30fps 帧网格。
产物：work/aroll_cut.mp4、audio/voice_cut.wav、work/edl.json、work/transcript_cut.json（逐字时间已换算到剪后时间轴）
--dry-run 只打印要剪的地方和剪后时长，不出文件。剪完要听一遍切点（报告里标 ⚠ 的优先听）。
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, load, save, die, sentence_chars, FPS, hms, encoder_args, probe
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--dry-run", action="store_true")
ap.add_argument("--verify", action="store_true", help="剪完把人声再转写一遍，和预期文字逐字比对")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
tr = load(P(proj, "transcript.json"))
ed = load(P(proj, "edits.json"), {})
en = load(P(proj, "work", "energy.json"))
db = np.array(en["db"])
dur_src = probe(P(proj, "work", "aroll.mp4"))["duration"]

MAXP = ed.get("max_pause", 0.40)
KEEPP = ed.get("keep_pause", 0.20)
HEAD, TAIL = ed.get("head", 0.12), ed.get("tail", 0.25)  # 说完留 0.25s 就收：后面的停留交给落版（第 4 轮评审：留长了会剪进她伸手点停止键和「咔」一声）
BREATH = set(ed.get("breath", []))  # 这些句子后面留气口（重点词、段落转换），停顿最多压到 0.5s

S = [s for s in tr["sentences"]]
for s in S:
    s["_chars"] = sentence_chars(s)

removes = []  # (t0, t1, 原因)
# 1. 整句删除
for s in S:
    if s.get("drop"):
        removes.append((s["start"] - 0.05, s["end"] + 0.05, "删句 %s「%s」" % (s["id"], s["text"][:10]), 0.15))
# 2. 口癖与指定片段
by_id = {s["id"]: s for s in S}
for item in ed.get("cut", []):
    sid, frag = item.split(":", 1)
    s = by_id.get(sid)
    if not s:
        die("edits.cut 里的句号不存在：" + item)
    txt = "".join(c["c"] for c in s["_chars"])
    i = txt.find(frag)
    if i < 0:
        die("在 %s 里找不到「%s」（按校对后的文字找）：%s" % (sid, frag, txt))
    cs = s["_chars"][i:i + len(frag)]
    t0, t1 = cs[0]["s"], cs[-1]["e"]
    # 句首口癖：从句子起点剪到下一个字的字头
    nxt = s["_chars"][i + len(frag)] if i + len(frag) < len(s["_chars"]) else None
    if nxt:
        t1 = max(t1, nxt["s"] - 0.03)
    removes.append((t0, t1, "剪 %s「%s」" % (sid, frag), 0.15))
    for c in cs:
        c["cut"] = True
# 3. 长停顿（按能量量出来的，不靠转写）
def after_breath(p0):
    for s in S:
        if s["id"] in BREATH and -0.3 < p0 - s["end"] < 0.7:  # 句尾时间是估的，窗口放宽（10-22 评审第 3 轮：0.6 没生效）
            return True
    return False
_last_end = max(s["end"] for s in S if not s.get("drop"))
for p0, p1 in en["pauses"]:
    if p0 >= _last_end - 0.2:
        continue  # 最后一个字之后不压停顿：压了会在片尾剪出一段几帧的跳切碎片（10-22 评审第 3 轮）
    keep = ed.get("breath_keep", 0.5) if after_breath(p0) else KEEPP
    if p1 - p0 > max(MAXP, keep + 0.05) and p0 > 0.3:
        removes.append((p0 + keep / 2, p1 - keep / 2, "压停顿 %.2fs→%.2fs%s" % (p1 - p0, keep, "（留气口）" if keep > KEEPP else ""), 0.06))

# 片头片尾
first = min(s["start"] for s in S if not s.get("drop"))
last = max(s["end"] for s in S if not s.get("drop"))
lo, hi = max(first - HEAD, 0), min(last + TAIL, dur_src)

def valley(t, w=0.06):
    i0, i1 = int((t - w) * 100), int((t + w) * 100) + 1
    i0, i1 = max(i0, 0), min(i1, len(db) - 1)
    if i1 <= i0:
        return t
    return (i0 + int(np.argmin(db[i0:i1]))) / 100.0

def grid(t):
    return round(t * FPS) / FPS

segs = []
removes.sort()
merged = []
for r in removes:
    r0, r1 = max(r[0], lo), min(r[1], hi)
    if r1 - r0 < 0.04:
        continue
    if merged and r0 <= merged[-1][1] + 0.12:  # 两刀之间剩不到 0.12s 就并成一刀，不留碎片
        merged[-1] = (merged[-1][0], max(merged[-1][1], r1), merged[-1][2] + "＋" + r[2], max(merged[-1][3], r[3]))
    else:
        merged.append((r0, r1, r[2], r[3]))
cur = lo
report = []
for r0, r1, why, win in merged:
    c0, c1 = grid(valley(r0, win)), grid(valley(r1, win))
    if c0 - cur >= 2 / FPS:
        segs.append([grid(cur), c0])
    warn = db[int(c0 * 100)] > en["silence_thr_db"] + 6 or db[min(int(c1 * 100), len(db) - 1)] > en["silence_thr_db"] + 6
    report.append((c0, c1, why, warn))
    cur = c1
if hi - cur >= 2 / FPS:
    segs.append([grid(cur), grid(hi)])

edl, t = [], 0.0
for s0, s1 in segs:
    edl.append({"src0": round(s0, 4), "src1": round(s1, 4), "dst0": round(t, 4), "dst1": round(t + s1 - s0, 4)})
    t += s1 - s0
out_dur = t
print("剪掉 %d 处，%.2fs → %.2fs（%.0f%%）" % (len(report), hi - lo, out_dur, out_dur / (hi - lo) * 100))
for c0, c1, why, warn in report:
    print("  %s %s–%s  %.2fs  %s" % ("⚠" if warn else " ", hms(c0), hms(c1), c1 - c0, why))
if a.dry_run:
    sys.exit(0)

def to_dst(ts):
    """源时间 → 剪后时间。落在被剪区间里的（转写时间不准的字常落进停顿），吸附到最近的保留点，不丢字。"""
    best, bd = None, 1e9
    for e in edl:
        if e["src0"] - 1e-3 <= ts <= e["src1"] + 1e-3:
            return e["dst0"] + (ts - e["src0"])
        for src, dst in ((e["src0"], e["dst0"]), (e["src1"], e["dst1"])):
            if abs(src - ts) < bd:
                best, bd = dst, abs(src - ts)
    return best

# 剪后句表
out_s = []
for s in S:
    if s.get("drop"):
        continue
    cs = []
    for c in s["_chars"]:
        if c.get("cut"):
            continue
        d0, d1 = to_dst(c["s"]), to_dst(max(c["e"] - 0.01, c["s"]))
        if d0 is None or d1 is None:
            continue
        cs.append({"c": c["c"], "s": round(d0, 3), "e": round(max(d1, d0 + 0.04), 3), "w": c.get("w")})
    if cs:
        out_s.append({"id": s["id"], "text": "".join(c["c"] for c in cs), "start": cs[0]["s"], "end": cs[-1]["e"], "chars": cs})
save(P(proj, "work", "transcript_cut.json"), {"duration": round(out_dur, 4), "sentences": out_s})
save(P(proj, "work", "edl.json"), {"segments": edl, "jump_cuts": [e["dst0"] for e in edl[1:]]})

# 出片：画面与声音同一张 EDL；每段声音首尾 8ms 淡入淡出防爆音
src_v, src_a = P(proj, "work", "aroll.mp4"), P(proj, "work", "voice.wav")
fc, vl, al = [], "", ""
for i, e in enumerate(edl):
    d = e["src1"] - e["src0"]
    # 按帧号与采样号剪（48k/30fps＝每帧 1600 个采样），画面和声音逐段同长，整片不漂
    f0, f1 = int(round(e["src0"] * FPS)), int(round(e["src1"] * FPS))
    fc.append("[0:v]trim=start_frame=%d:end_frame=%d,setpts=PTS-STARTPTS[v%d]" % (f0, f1, i))
    fc.append("[1:a]atrim=start_sample=%d:end_sample=%d,asetpts=PTS-STARTPTS,afade=t=in:d=0.008,afade=t=out:st=%.4f:d=0.008[a%d]"
              % (f0 * 1600, f1 * 1600, max(d - 0.008, 0), i))
    vl += "[v%d]" % i
    al += "[a%d]" % i
fc.append("%sconcat=n=%d:v=1:a=0[vo]" % (vl, len(edl)))
fc.append("%sconcat=n=%d:v=0:a=1[ao]" % (al, len(edl)))
fcs = P(proj, "work", "trim_filter.txt")
open(fcs, "w").write(";\n".join(fc))
run(["ffmpeg", "-v", "error", "-y", "-i", src_v, "-i", src_a, "-filter_complex_script", fcs,
     "-map", "[vo]"] + encoder_args("high") + ["-r", "30", "-an", P(proj, "work", "aroll_cut.mp4"),
     "-map", "[ao]", "-ar", "48000", "-ac", "1", P(proj, "audio", "voice_cut.wav")])
vd = probe(P(proj, "work", "aroll_cut.mp4"))["duration"]
ad = probe(P(proj, "audio", "voice_cut.wav"))["duration"]
print("✓ aroll_cut.mp4 %.3fs ｜ voice_cut.wav %.3fs ｜ 差 %.0fms" % (vd, ad, abs(vd - ad) * 1000))

if a.verify:
    import difflib, json as _j
    exp = "".join(c["c"] for s in out_s for c in s["chars"])
    w16 = P(proj, "work", "cut16.wav")
    run(["ffmpeg", "-v", "error", "-y", "-i", P(proj, "audio", "voice_cut.wav"), "-ar", "16000", w16])
    model = os.environ.get("WHISPER_MODEL", os.path.expanduser("~/.cache/whisper-cpp/ggml-small.bin"))
    run(["whisper-cli", "-m", model, "-l", "zh", "-f", w16, "-otxt", "-of", w16[:-4], "-t", "8",
         "--prompt", "以下是普通话的句子，使用简体中文。"])
    got = open(w16[:-4] + ".txt", encoding="utf-8").read()
    strip = lambda t: "".join(ch for ch in t if ch.isalnum())
    e_, g_ = strip(exp), strip(got)
    r = difflib.SequenceMatcher(None, e_, g_).ratio()
    print("剪后复核：预期与重转写相似度 %.3f" % r)
    for tag, i0, i1, j0, j1 in difflib.SequenceMatcher(None, e_, g_).get_opcodes():
        if tag != "equal" and (i1 - i0 > 1 or j1 - j0 > 1):
            print("   %s 预期「%s」 听到「%s」" % (tag, e_[max(i0-4,0):i1+4], g_[max(j0-4,0):j1+4]))
