#!/bin/bash
# 共享 Remotion 运行时：只装一次，所有口播工程的 remotion/node_modules 软链到这里。
# npmmirror 在本机连不上，走 npmjs 官方源；无头浏览器优先从已有工程拷，避免下载。
set -e
SK="$(cd "$(dirname "$0")/.." && pwd)"
cd "$SK/runtime"
if [ ! -d node_modules/remotion ]; then
  npm install --registry=https://registry.npmjs.org/ --no-audit --no-fund
fi
if [ ! -d node_modules/.remotion/chrome-headless-shell ]; then
  SRC=$(find "$HOME/Desktop" -maxdepth 6 -type d -path "*node_modules/.remotion/chrome-headless-shell" 2>/dev/null | head -1)
  if [ -n "$SRC" ]; then
    mkdir -p node_modules/.remotion && cp -R "$SRC" node_modules/.remotion/
    echo "· 无头浏览器从 $SRC 拷入"
  else
    echo "· 没找到现成的无头浏览器，首次渲染时 Remotion 会自己下载（需要网络）"
  fi
fi
command -v whisper-cli >/dev/null || echo "⚠ 缺 whisper-cli：brew install whisper-cpp"
[ -f "$HOME/.cache/whisper-cpp/ggml-small.bin" ] || echo "⚠ 缺 whisper 模型 ~/.cache/whisper-cpp/ggml-small.bin（约 466MB，下载要限时）"
command -v firecrawl >/dev/null || echo "⚠ 缺 firecrawl CLI：免费素材那一路用不了"
python3 -c "import numpy, PIL, fontTools" 2>/dev/null || echo "⚠ Python 缺 numpy / Pillow / fonttools"
mkdir -p "$HOME/.cache/ifa-koubo"
[ -x "$HOME/.cache/ifa-koubo/face" ] || swiftc -O "$SK/scripts/face.swift" -o "$HOME/.cache/ifa-koubo/face" 2>/dev/null || echo "⚠ Vision 人脸检测编译失败（不影响主流程）"
[ -x "$HOME/.cache/ifa-koubo/text" ] || swiftc -O "$SK/scripts/text.swift" -o "$HOME/.cache/ifa-koubo/text" 2>/dev/null || echo "⚠ Vision 文字识别编译失败（qa 的「B-roll 可读文字」会跳过）"
echo "[runtime] OK"
