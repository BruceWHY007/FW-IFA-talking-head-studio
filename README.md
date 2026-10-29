# FW-IFA 口播成片 · talking-head-studio

把一条**真人对着镜头说话**的原始视频，做成可以直发的竖版成片。

转写校对 → 逐句拆 A-roll → 剪口癖压停顿 → B-roll 三路来源 → 包装 → 混音 → 渲染 → 27 项验收 → 独立评审。

- 成片 1080×1920 / 30fps / −14 LUFS，自带刊头、字幕、名字条、标注、数字卡、信息卡、片尾
- 七套风格，默认 **F 满幅讲述**（另有分带刊物／雾金玻璃／港刊大字／证据桌／图解／IFA 品牌刊）；开工前给一个文字菜单选风格，预览图在 `references/assets/styles/`
- 两档：**完整版**（默认，效果最全）／**极简档**（自动规划＋自动取素材＋审片，同一套质感，省时间和 token）
- 屏上数字先**对过原声**（`numcheck.py`：转写会把「千分之」写成 %）
- 每个关键数字和题眼词单独成卡；屏上每个字都在 `facts.json` 里有出处
- 27 项量化验收（响度、字幕对位、冻结、安全区、对比度、素材重复、暗部亮度、画面里的可读文字……）
- 交付：成片、纯音乐版、抽帧图、分镜表、出处表、验收报告、评审报告、待人确认清单

## 安装

仓库公开，一条命令，不需要登录也不需要授权：

```bash
npx skills add BruceWHY007/FW-IFA-talking-head-studio -g --agent claude-code
```

装到 `~/.agents/skills/fw-ifa-talking-head-studio`（npx 会把名字转小写）。换 Agent 就把 `claude-code` 换成 `codex`／`cursor` 等。

装完先自检：

```bash
bash ~/.agents/skills/fw-ifa-talking-head-studio/scripts/setup.sh     # 装 Remotion 运行时（只装一次，约 500MB）
bash ~/.agents/skills/fw-ifa-talking-head-studio/scripts/doctor.sh    # 逐项报「有／没有／怎么补」，最后一行要是 [doctor] OK
```

## 最短用法

把它和一条原片交给 AI：

> 把这条视频做成口播成片。我是 XXX，做香港保险／理财，系列叫《XXX》，配乐轻一点。

它会先发一个文字菜单让你选风格（1–7，默认 F）和档位（完整版／极简档），不回就按默认做。想先用自己的画面看样子，再让它跑 `catalog.py --video <原片>`。

**任何 Agent 要从零复现，先读 `skills/FW-IFA-talking-head-studio/references/13_完整复现手册.md`**（数据流、文件契约、逐步命令、导演逻辑、包装设计逻辑、代码要点、验收口径、常见坑）。

命令行等价：

```bash
SK=~/.agents/skills/fw-ifa-talking-head-studio
# ⓪ 先问风格与档位（文字菜单）；要看自己的脸才跑：python3 $SK/scripts/catalog.py --video 原片.mp4
python3 $SK/scripts/new_project.py 原片.mp4 ~/片库/项目/这一期    # ① 建工程
python3 $SK/scripts/ingest.py ~/片库/项目/这一期 --prompt "专有名词"
# ③ 校对 transcript.json 的 text 后：
python3 $SK/scripts/numcheck.py ~/片库/项目/这一期              # ③.5 数字核对原声
python3 $SK/scripts/analyze.py ~/片库/项目/这一期                # ④ 逐句拆 A-roll
python3 $SK/scripts/trim.py ~/片库/项目/这一期 --verify          # ⑥ 剪
python3 $SK/scripts/make.py ~/片库/项目/这一期 --bgm 配乐.mp3    # ⑩ 一条龙：组装→混音→渲染→验收
```

极简档：

```bash
python3 $SK/scripts/lite_plan.py ~/片库/项目/这一期 --series 系列名 --episode 本期标题
python3 $SK/scripts/stock.py ~/片库/项目/这一期 auto --decompose decompose_lite.json   # 自动取素材＋审片表
# 看 broll/stock/auto_review.jpg，在 auto_review.json 填 keep/replace/drop；有 replace 就：
python3 $SK/scripts/stock.py ~/片库/项目/这一期 redo --decompose decompose_lite.json
python3 $SK/scripts/build.py ~/片库/项目/这一期 --decompose ~/片库/项目/这一期/decompose_lite.json
```

## 依赖

| 必需 | 说明 |
|---|---|
| ffmpeg / ffprobe | 需带 loudnorm、sidechaincompress、minterpolate、ebur128 等滤镜 |
| whisper-cli + ggml-small 模型 | 转写；`~/.cache/whisper-cpp/ggml-small.bin`（465MB） |
| Node ≥18 + npm | Remotion 运行时（`setup.sh` 用 `runtime/package.json` 装到 skill 目录内） |
| Python 3.9+ | numpy / Pillow / fonttools |
| macOS（推荐） | 人脸检测与文字识别用 Vision；Linux 上这两项会跳过 |

可选：`firecrawl` CLI（Pexels 检索）、`PIXABAY_API_KEY`（Pixabay 视频与图片 API）、Swift（Vision 编译）。

## 素材与许可

- 视频：Pexels（抓搜索页）、Coverr、Mixkit；图片：Pixabay、Wikimedia Commons（CC／公有领域，按条目署名）
- 一律下载后 `ffprobe` 复量真实分辨率，许可与来源页登记在 `broll/stock/stock_picks.json`、`broll/img/img_picks.json`
- 不抓他人的成片、影视片段和品牌广告

## 边界

- 不写稿、不做数字人、不做特效大片
- 理财／保险类内容发布前仍需过公司合规
- 原片太暗、太糊、太低价（如微信转码的 544×960）会直接反映在成片清晰度上

## 许可

MIT。其中 `assets/fonts` 为 SIL Open Font License 1.1（Source Han Serif、Bodoni Moda），随包分发，见 `assets/fonts/OFL-*.txt`。

## 校验

```bash
python3 <dbs-skill-maker>/scripts/validate_skill_project.py skills/fw-ifa-talking-head-studio
```
