#!/bin/bash
# 环境自检：逐项报「有／没有／版本」，缺什么就告诉你怎么补。不改任何东西，可以随时跑。
#   bash scripts/doctor.sh
SK="$(cd "$(dirname "$0")/.." && pwd)"
ok=0; bad=0; warn=0
pass(){ echo "  ✅ $1"; ok=$((ok+1)); }
fail(){ echo "  ❌ $1"; echo "     → $2"; bad=$((bad+1)); }
note(){ echo "  ⚠️  $1"; [ -n "$2" ] && echo "     → $2"; warn=$((warn+1)); }

echo "── 必需：命令行工具"
if command -v ffmpeg >/dev/null; then
  pass "ffmpeg $(ffmpeg -version | head -1 | awk '{print $3}')"
  F=$(ffmpeg -hide_banner -filters 2>/dev/null)
  for flt in loudnorm sidechaincompress acompressor afftdn alimiter minterpolate colorspace ebur128 boxblur; do
    echo "$F" | grep -q " ${flt} " && pass "ffmpeg 滤镜 ${flt}" || fail "ffmpeg 缺滤镜 ${flt}" "装完整版 ffmpeg（macOS：brew install ffmpeg）"
  done
  E=$(ffmpeg -hide_banner -encoders 2>/dev/null)
  if echo "$E" | grep -q h264_videotoolbox; then pass "编码器 h264_videotoolbox（素材预处理走硬件编码）"
  elif echo "$E" | grep -q libx264; then note "没有 VideoToolbox，预处理退回 libx264（慢一些，结果一样）"
  else fail "没有 H.264 编码器" "装带 libx264 的 ffmpeg"; fi
else fail "没有 ffmpeg" "macOS：brew install ffmpeg；Linux：apt install ffmpeg"; fi
command -v ffprobe >/dev/null && pass "ffprobe" || fail "没有 ffprobe" "随 ffmpeg 一起装"
if command -v whisper-cli >/dev/null; then pass "whisper-cli（whisper.cpp）"
else fail "没有 whisper-cli" "macOS：brew install whisper-cpp；其他：编译 https://github.com/ggml-org/whisper.cpp"; fi
WM="${WHISPER_MODEL:-$HOME/.cache/whisper-cpp/ggml-small.bin}"
[ -f "${WM}" ] && pass "whisper 模型 ${WM}（$(du -h "${WM}" | cut -f1)）" || fail "缺 whisper 模型 ${WM}" "下载 ggml-small.bin（约 466MB）：https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin ；或设环境变量 WHISPER_MODEL 指向已有模型。下载要设超时"
command -v node >/dev/null && pass "node $(node -v)" || fail "没有 Node.js（≥18）" "https://nodejs.org 或 brew install node"
command -v npm >/dev/null && pass "npm $(npm -v)" || fail "没有 npm" "随 Node 一起装"

echo "── 必需：Python 3.9+ 与库"
if command -v python3 >/dev/null; then
  pass "python3 $(python3 -c 'import sys;print(sys.version.split()[0])')"
  for m in numpy PIL fontTools; do
    python3 -c "import ${m}" 2>/dev/null && pass "python 库 ${m}" || fail "缺 python 库 ${m}" "python3 -m pip install numpy pillow fonttools"
  done
else fail "没有 python3" "装 Python 3.9+"; fi

echo "── 必需：Remotion 共享运行时（skill 的 runtime/）"
[ -d "${SK}/runtime/node_modules/remotion" ] && pass "remotion $(node -p "require('${SK}/runtime/node_modules/remotion/package.json').version" 2>/dev/null)" \
  || fail "runtime 没装" "bash ${SK}/scripts/setup.sh"
[ -d "${SK}/runtime/node_modules/.remotion/chrome-headless-shell" ] && pass "无头浏览器 chrome-headless-shell" \
  || note "无头浏览器还没下" "第一次渲染时 Remotion 会自动下载（要网络），或跑 setup.sh 从已有工程拷"

echo "── 必需：字体（skill 自带）"
for f in SourceHanSerifSC-Heavy.otf SourceHanSerifSC-SemiBold.otf BodoniModa.ttf; do
  [ -f "${SK}/assets/fonts/${f}" ] && pass "字体 ${f}" || fail "缺字体 ${f}" "从 Adobe Source Han Serif / Google Fonts Bodoni Moda 下载（均为 OFL）放进 assets/fonts/"
done
if [ "$(uname)" = "Darwin" ]; then pass "苹方（PingFang SC，macOS 系统字体，字幕用）"
else note "非 macOS：没有苹方" "装思源黑体／Noto Sans SC，并把 template/remotion/src/theme.ts 里 F.sans 的第一个字体名换掉"; fi

echo "── 必需：六套风格包与账号主题（skill 自带）"
for f in editorial glass kinetic evidence diagram brand info parts; do
  [ -f "${SK}/template/remotion/src/packs/${f}.tsx" ] && pass "风格包文件 ${f}.tsx" || fail "缺 packs/${f}.tsx" "从正本恢复 template/remotion/src/packs/"
done
[ -f "${SK}/template/remotion/src/packs/themes.json" ] && pass "账号主题 themes.json" || fail "缺 themes.json" "从正本恢复"
[ -f "${SK}/template/remotion/public/brand/logo.png" ] && pass "K3 品牌 logo" || fail "缺 public/brand/logo.png" "从 IFA图文卡 的 assets/logo-简体.png 拷来"
if [ "$(uname)" = "Darwin" ]; then pass "Helvetica Neue／SF Mono（K2 图解的数字与图号，macOS 系统字体）"
else note "非 macOS：K2 的数字与图号字体" "改 packs/diagram.tsx 里的 HELV、MONO"; fi

echo "── 可选：免费素材、人脸检测、AI 生成"
command -v firecrawl >/dev/null && pass "firecrawl CLI（Pexels 免费素材检索）" || note "没有 firecrawl CLI：免费素材那一路用不了" "npm i -g firecrawl-cli 并登录（需要 Firecrawl 账号与额度）"
if [ "$(uname)" = "Darwin" ] && command -v swiftc >/dev/null; then pass "swiftc（macOS Vision 人脸检测，用于 A-roll 体检与人脸定位）"
else note "没有 Vision 人脸检测" "analyze.py 会跳过人脸项；人脸中心手动写进工程 project.json 的 face：{cx, cy, w}"; fi
for v in RUNNINGHUB_API_KEY ARK_API_KEY MINIMAX_API_KEY KLING_ACCESS_KEY FAL_KEY CUSTOM_VIDEO_API_KEY; do
  [ -n "${!v}" ] && echo "  ·  生成渠道密钥 ${v}：已设" || echo "  ·  生成渠道密钥 ${v}：未设（不需要 AI 生成就不用管）"
done

echo "── 结果：通过 ${ok}　缺失 ${bad}　提醒 ${warn}"
[ ${bad} -eq 0 ] && echo "[doctor] OK" || exit 1
