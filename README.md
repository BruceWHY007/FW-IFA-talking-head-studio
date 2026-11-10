# FW-IFA 口播成片 · talking-head-studio

把一条**真人对着镜头说话**的原始视频，做成可以直发的竖版成片。

> **当前版本 v5.5.0（2026-11-10）**：macOS／Windows／Linux 通用的一条命令安装（国内镜像、限时、断点续传、可离线）；流程向导 `next.py`；渲染只打包一次、并发自动定；完整版增加过程证据检查。更新记录见页面底部。

转写校对 → 逐句拆 A-roll → 剪口癖压停顿 → B-roll 三路来源 → 包装 → 混音 → 渲染 → 27 项验收 → 独立评审。

- 成片 1080×1920 / 30fps / −14 LUFS，自带刊头、字幕、名字条、标注、数字卡、信息卡、片尾
- 七套风格，默认 **F 满幅讲述**（另有分带刊物／雾金玻璃／港刊大字／证据桌／图解／IFA 品牌刊）；开工前给一个文字菜单选风格，预览图在 `references/assets/styles/`
- 两档：**完整版**（默认，效果最全）／**极简档**（自动规划＋自动取素材＋审片，同一套质感，省时间和 token）
- 信息卡按内容结构换形式：原文／对比／清单／时间线／柱图，加六种新形式（数轴／点阵／前后拉杆／链条／汇聚／航线）。风格按账号锁，每支片子靠信息的呈现方式区分；同一账号连着两支会提醒错开，规则在 `references/14_内容到形式.md`
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

装完跑安装脚本（macOS／Windows／Linux 同一条，只需要先有 Python 3.9+；Windows 上写 `python`）：

```bash
python3 ~/.agents/skills/fw-ifa-talking-head-studio/scripts/setup.py            # 装到能用，最后一行是 [setup] OK
python3 ~/.agents/skills/fw-ifa-talking-head-studio/scripts/setup.py --check --smoke   # 自检＋渲一帧验证
```

- **国内网络直连就能装**：npm、pip 先测哪个源通；无头浏览器、ffmpeg、Node 走 npmmirror；转写模型走 hf-mirror。每个下载有总时限、断点续传，不会无限等。
- **Windows 原生可用，不需要 WSL、不需要管理员权限**：缺 ffmpeg／Node／whisper 时脚本自动下到 `~/.cache/ifa-koubo/`，不改系统 PATH。（11-10：Windows 路径已核对下载源与脚本逻辑，真机整条流程待验证，装的时候请留下 `setup.py` 的输出。）
- **GitHub 拉不动**：让同事把技能文件夹打包发来（不要带 `runtime/node_modules`），放进 Agent 的技能目录后跑 `setup.py`。
- **还是下不动**：有网的人跑 `setup.py --pack <目录> --target win` 做离线包（约 400MB），装的人跑 `setup.py --offline <目录>`。

装好以后不用记流程：每做完一步跑 `python3 scripts/next.py <工程目录>`，它只告诉你下一步。

## 最短用法

把它和一条原片交给 AI：

> 把这条视频做成口播成片。我是 XXX，做香港保险／理财，系列叫《XXX》，配乐轻一点。

它会先发一个文字菜单让你选风格（1–7，默认 F）和档位（完整版／极简档），不回就按默认做。想先用自己的画面看样子，再让它跑 `catalog.py --video <原片>`。

**任何模型执行前先读 `skills/FW-IFA-talking-head-studio/references/00_执行卡.md`**（一页：每步命令、过不去的条件、禁止事项）。

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
python3 $SK/scripts/beats.py ~/片库/项目/这一期                  # ⑤ 逐句节拍表 work/beats.md（每句建议处理＋硬门槛）
python3 $SK/scripts/lite_plan.py ~/片库/项目/这一期 --full --series 系列名 --episode 本期标题   # ⑤ 完整版底稿 → 逐条做完 _待升级
python3 $SK/scripts/make.py ~/片库/项目/这一期 --bgm 配乐.mp3    # ⑩ 一条龙：组装→混音→渲染→验收
```

极简档：

```bash
python3 $SK/scripts/beats.py ~/片库/项目/这一期
python3 $SK/scripts/lite_plan.py ~/片库/项目/这一期 --series 系列名 --episode 本期标题   # 改 _待改 里的每一条
python3 $SK/scripts/stock.py ~/片库/项目/这一期 auto --decompose decompose_lite.json   # 自动取素材＋审片表
# 看 broll/stock/auto_review.jpg，在 auto_review.json 填 keep/replace/drop；有 replace 就：
python3 $SK/scripts/stock.py ~/片库/项目/这一期 redo --decompose decompose_lite.json
python3 $SK/scripts/build.py ~/片库/项目/这一期 --decompose ~/片库/项目/这一期/decompose_lite.json
```

## 依赖

| 必需 | 说明 |
|---|---|
| Python 3.9+ | numpy／Pillow／fonttools；非 macOS 另加 opencv-python-headless（`setup.py` 用 pip 装） |
| ffmpeg／ffprobe | 需带 loudnorm、sidechaincompress、minterpolate、ebur128 等滤镜；Windows 上 `setup.py` 自动下静态版 |
| Node ≥18 | Remotion 运行时（`setup.py` 装到 skill 目录内的 `runtime/`，约 330MB）；Windows 没有 Node 时自动下便携版 |
| 无头浏览器 | chrome-headless-shell，`setup.py` 从 npmmirror 装（约 110MB） |
| whisper-cli＋模型 | 转写；新装默认量化版 `ggml-small-q5_1`（190MB），已有 `ggml-small.bin` 就用它 |

macOS 有系统自带的人脸检测与画面文字识别；Windows／Linux 人脸检测走 OpenCV，画面文字识别没有（要人看抽帧图）。

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

## 更新记录

| 版本 | 日期 | 内容 |
|---|---|---|
| v5.5.0 | 2026-11-10 | 跨平台安装 `setup.py`（Windows 原生可用，npm／pip／无头浏览器／ffmpeg／Node／转写模型走国内镜像，限时、断点续传、`--offline` 离线包、`--smoke` 渲一帧验证）；流程向导 `next.py`；渲染只打包一次（单帧 4.7s→0.9s）、并发按核数与内存自动定、`--draft` 半尺寸草稿；非 macOS 用 OpenCV 做人脸检测；转写繁体自动转简体；新装默认量化版转写模型（190MB）；完整版 build 查过程证据（素材复用面、候选表出处、工程指纹）。Windows 真机整条流程待验证 |
| v5.4.0 | 2026-10-31（11-10 打标签） | 七套风格（默认 F 满幅讲述）、完整版／极简档两档、numcheck 数字核对、选素材推导链、六种新形式 |
| v5.3.0 | 2026-10-28 | 名称加 FW-IFA 前缀，仓库转为公开，安装无需授权 |

## 校验

```bash
python3 <dbs-skill-maker>/scripts/validate_skill_project.py skills/fw-ifa-talking-head-studio
```
