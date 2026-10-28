#!/usr/bin/env python3
"""⑥ 声音：人声整理 → 代码合成音效（按 timing.json 的事件）→ 配乐自动避让 → 整片 −14 LUFS / 真峰值 ≤ −1.5 dBTP。

    python3 mix.py <工程目录> [--bgm 配乐文件 --bgm-in 起点秒 --bgm-db -22] [--no-sfx]

人声是这类片子的主角：配乐只做底，人声开口时自动压下去（sidechain），句间缓缓回来。
音效只给画面里真发生的事（名字条画线、大字揭开、照片卡落位、下期预告）；B-roll 硬切不配音效。
产物：audio/mix.wav（成片用）、audio/music_only.wav（配乐＋音效，不含人声）、audio/sfx.wav、qa/audio.json
"""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, run, load, save, die, probe
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--bgm", default="")
ap.add_argument("--bgm-in", type=float, default=0.0)
ap.add_argument("--bgm-db", type=float, default=-12.0, help="配乐基础电平（相对满刻度），人声开口时再自动压")
ap.add_argument("--no-sfx", action="store_true")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
tl = load(P(proj, "timing.json"))
SR = 48000
DUR = tl["durationInFrames"] / tl["fps"]
voice_in = P(proj, "audio", "voice_cut.wav")
if not os.path.exists(voice_in):
    die("没有 audio/voice_cut.wav，先跑 trim.py")

# ---------- 1. 人声：低切、轻降噪、温和压缩 ----------
voice = P(proj, "audio", "voice_proc.wav")
vdur = probe(voice_in)["duration"]
run(["ffmpeg", "-v", "error", "-y", "-i", voice_in, "-af",
     "highpass=f=75,afftdn=nr=6:nf=-48,acompressor=threshold=-22dB:ratio=2.5:attack=8:release=140:makeup=3,"
     "afade=t=out:st=%.3f:d=0.25,apad=whole_dur=%.3f" % (max(vdur - 0.25, 0), DUR), "-ar", str(SR), "-ac", "1", "-t", "%.3f" % DUR, voice])  # 人声尾巴淡出，落版段只剩配乐

# ---------- 2. 音效：全部代码合成（无版权问题），每种占自己的频段 ----------
rng = np.random.default_rng(11)

def shaped_noise(n, lo, hi):
    spec = np.fft.rfft(rng.normal(0, 1, n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-9)

def env(n, att, rel):
    t = np.arange(n) / SR
    e = np.minimum(t / max(att, 1e-4), 1.0) * np.exp(-np.maximum(t - att, 0) / rel)
    return e

def tick():   # 名字条画线／下期预告：一声很轻的高频「嗒」（2–6 kHz）
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * np.pi * 2650 * t) * 0.6 + np.sin(2 * np.pi * 3980 * t) * 0.3) * env(n, 0.001, 0.018)
    x += shaped_noise(n, 3000, 7000) * env(n, 0.0005, 0.006) * 0.4
    return x * 10 ** (-26 / 20) / (np.abs(x).max() + 1e-9)

def swell():  # 大字揭开：0.5s 气流上扬＋落点一记低频（60–90 Hz）
    n1, n2 = int(0.5 * SR), int(0.45 * SR)
    up = shaped_noise(n1, 400, 5000) * (np.linspace(0, 1, n1) ** 2) * 0.5
    t = np.arange(n2) / SR
    thump = np.sin(2 * np.pi * (78 - 18 * t / 0.45) * t) * env(n2, 0.004, 0.16)
    x = np.concatenate([up, thump])
    x[n1 - 2000:n1] *= np.linspace(1, 0.3, 2000)
    return x * 10 ** (-23 / 20) / (np.abs(x).max() + 1e-9)

def air():    # 照片卡落位：一口很短的气（800–3 kHz）
    n = int(0.42 * SR)
    x = shaped_noise(n, 800, 3000) * np.sin(np.linspace(0, np.pi, n)) ** 2
    return x * 10 ** (-30 / 20) / (np.abs(x).max() + 1e-9)

KIND = {"tick": tick, "swell": swell, "air": air}
sfx = np.zeros(int(DUR * SR) + SR)
if not a.no_sfx:
    for ev in tl.get("sfx", []):
        x = KIND.get(ev["kind"], tick)()
        lead = int(0.5 * SR) if ev["kind"] == "swell" else 0  # swell 的落点对准事件帧，上扬提前开始
        i0 = max(int(ev["t"] * SR) - lead, 0)
        sfx[i0:i0 + len(x)] += x[: len(sfx) - i0]
sfx = sfx[: int(DUR * SR)]
import wave
def write_wav(path, x, ch=1):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())
sfx_p = P(proj, "audio", "sfx.wav")
write_wav(sfx_p, sfx)

# ---------- 3. 配乐：截取、淡入淡出、按人声自动避让 ----------
inputs = ["-i", voice, "-i", sfx_p]
fc = []
if a.bgm:
    if not os.path.exists(a.bgm):
        die("配乐文件不存在：" + a.bgm)
    inputs += ["-ss", "%.3f" % a.bgm_in, "-t", "%.3f" % (DUR + 0.5), "-i", a.bgm]
    fc.append("[2:a]aformat=sample_rates=%d:channel_layouts=stereo,afade=t=in:d=1.2,afade=t=out:st=%.3f:d=2.8,volume=%.1fdB[bgm]"
              % (SR, max(DUR - 2.8, 0), a.bgm_db))
    # 避让的键＝人声＋延后 180／360ms 的两份：句间 0.3–0.6s 的小停顿里配乐不抬头，长停顿才慢慢回来
    # （第 5 轮评审：每个气口抬 8–13 dB，一下一下「呼」的起伏）
    fc.append("[0:a]asplit=4[v1][k0][k1][k2]")
    fc.append("[k1]adelay=180:all=1[k1d]")
    fc.append("[k2]adelay=360:all=1[k2d]")
    fc.append("[k0][k1d][k2d]amix=inputs=3:duration=first[vkey]")
    fc.append("[bgm][vkey]sidechaincompress=threshold=0.025:ratio=5:attack=40:release=900:makeup=1[bgmd]")
    fc.append("[bgmd]asplit=2[bgm1][bgm2]")
    fc.append("[v1]aformat=channel_layouts=stereo[vs]")
    fc.append("[1:a]aformat=channel_layouts=stereo,asplit=2[s1][s2]")
    fc.append("[vs][bgm1][s1]amix=inputs=3:normalize=0:duration=first[pre]")
    fc.append("[bgm2][s2]amix=inputs=2:normalize=0:duration=first[mo]")
else:
    fc.append("[0:a]aformat=channel_layouts=stereo[vs]")
    fc.append("[1:a]aformat=channel_layouts=stereo,asplit=2[s1][s2]")
    fc.append("[vs][s1]amix=inputs=2:normalize=0:duration=first[pre]")
    fc.append("[s2]anull[mo]")
pre = P(proj, "audio", "_pre.wav")
mo = P(proj, "audio", "music_only_raw.wav")
run(["ffmpeg", "-v", "error", "-y"] + inputs + ["-filter_complex", ";".join(fc),
     "-map", "[pre]", "-ar", str(SR), pre, "-map", "[mo]", "-ar", str(SR), mo])

# ---------- 4. 两遍 loudnorm 到 −14 LUFS ----------
def loudnorm(src, dst, I=-14.0, TP=-2.0):  # 峰值留 1 dB 给 AAC 编码（编码后真峰值会升，10-22 实测 −1.5→−0.5）
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", src, "-af", "loudnorm=I=%s:TP=%s:LRA=11:print_format=json" % (I, TP),
                        "-f", "null", "-"], capture_output=True, text=True).stderr
    m = json.loads(r[r.rindex("{"):r.rindex("}") + 1])
    af = ("loudnorm=I=%s:TP=%s:LRA=11:measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true"
          % (I, TP, m["input_i"], m["input_tp"], m["input_lra"], m["input_thresh"], m["target_offset"]))
    run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af", af + ",alimiter=limit=0.79:level=false", "-ar", str(SR), dst])

def measure(path):
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", path, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    tail = r[r.rfind("Summary:"):]
    import re
    I = float(re.search(r"I:\s+(-?[\d.]+) LUFS", tail).group(1))
    tp = float(re.search(r"Peak:\s+(-?[\d.]+) dBFS", tail).group(1))
    return I, tp

mix = P(proj, "audio", "mix.wav")
loudnorm(pre, mix)
I, TP = measure(mix)
# 纯音乐版与成片同一增益关系，方便后期替换人声
mo_out = P(proj, "audio", "music_only.wav")
if a.bgm:
    gain = I - measure(pre)[0]
    run(["ffmpeg", "-v", "error", "-y", "-i", mo, "-af", "volume=%.2fdB" % gain, mo_out])
os.remove(pre)

# 人声频带里人声比配乐高多少（说话时）：配乐糊不糊人声的判据
rep = {"integrated_lufs": I, "true_peak_dbtp": TP, "bgm": a.bgm or None, "bgm_in": a.bgm_in, "bgm_db": a.bgm_db,
       "sfx_events": len(tl.get("sfx", []))}
if a.bgm:
    def band_rms(path):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-af", "highpass=f=300,lowpass=f=3400", "-ac", "1", "-ar", "16000",
                              "-f", "s16le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
        n = len(x) // 1600
        return 20 * np.log10(np.sqrt((x[: n * 1600].reshape(n, 1600) ** 2).mean(1)) + 1e-9)
    v = band_rms(voice)
    m = band_rms(mo)
    k = min(len(v), len(m))
    speaking = v[:k] > np.percentile(v[:k], 40)
    d = (v[:k] - m[:k])[speaking]
    rep["voice_over_music_db_median"] = round(float(np.median(d)), 1)
    rep["voice_over_music_db_p10"] = round(float(np.percentile(d, 10)), 1)
save(P(proj, "qa", "audio.json"), rep)
print("✓ mix.wav  %.1f LUFS  真峰值 %.1f dBTP  音效 %d 处%s" % (I, TP, rep["sfx_events"],
      "  人声高出配乐 中位 %.1f dB / 低 10%% %.1f dB" % (rep["voice_over_music_db_median"], rep["voice_over_music_db_p10"]) if a.bgm else ""))
