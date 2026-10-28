#!/usr/bin/env python3
"""闸① 近空画面扫描（边缘密度）。复制自 IFA-AI人物视频/references/scripts/qa_edge.py（2026-10-22），本 skill 单独移植时不再依赖父 skill。

    python3 qa_edge.py 成片.mp4 [--abs 0.016]

整片降到 768×432 / 10fps，逐帧算相邻像素差 > 0.02 的占比。
它只认字与图形，不认渐变——纯渐变的空画面在这个指标上接近 0，而 std / 肉眼都会放过。

阈值：
  · 纯图形片      不传 --abs，用「全片中位 × 30%」
  · 混合素材片    传 --abs（照片的边缘密度远高于线条图形，相对阈值会误判图形段）
判据：连续 0.2 秒低于阈值即记一处，必须为零。
"""
import subprocess, sys, numpy as np

V = sys.argv[1]
ABS = None
if "--abs" in sys.argv:
    ABS = float(sys.argv[sys.argv.index("--abs") + 1])

W, H, FPS = 768, 432, 10
raw = subprocess.run(
    ["ffmpeg", "-v", "error", "-i", V, "-vf", f"fps={FPS},scale={W}:{H},format=gray",
     "-f", "rawvideo", "-"], capture_output=True).stdout
n = len(raw) // (W * H)
a = np.frombuffer(raw[:n * W * H], dtype=np.uint8).reshape(n, H, W).astype(np.float32) / 255.0

dx = np.abs(np.diff(a, axis=2))
dy = np.abs(np.diff(a, axis=1))
d = np.maximum(dx[:, :-1, :], dy[:, :, :-1])
dens = (d > 0.02).mean(axis=(1, 2))

med = float(np.median(dens))
thr = ABS if ABS is not None else med * 0.30
kind = "绝对" if ABS is not None else "相对（中位×30%）"
print(f"帧数 {n}   中位 {med:.4f}   阈值 {thr:.4f}（{kind}）")

runs, st = [], None
for i, v in enumerate(dens):
    if v < thr and st is None:
        st = i
    elif v >= thr and st is not None:
        if (i - st) / FPS >= 0.2:
            runs.append((st / FPS, (i - st) / FPS, float(dens[st:i].min())))
        st = None
if st is not None and (n - st) / FPS >= 0.2:
    runs.append((st / FPS, (n - st) / FPS, float(dens[st:].min())))

print(f"近空画面（连续 ≥0.2s）：{len(runs)} 处")
for s, dur, m in runs:
    print(f"  {s:7.2f}s   时长 {dur:.2f}s   最低 {m:.4f}")
idx = np.argsort(dens)[:10]
print("最低十帧：", ", ".join(f"{i/FPS:.1f}s={dens[i]:.4f}" for i in sorted(idx)))
