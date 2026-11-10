#!/usr/bin/env python3
"""向导：看工程现在做到哪一步，只告诉你下一步——命令、必须看的东西、过不去的条件。

    python next.py <工程目录>                 现在该做什么（每做完一步就再跑一次）
    python next.py <工程目录> --tier lite     这支片子定为极简档（默认完整版；只需说一次，记在 project.json）
    python next.py <工程目录> --all           所有步骤的状态一览

为什么要它（2026-11-10）：流程写在文档里，模型读一半就开工、跳步、凭记忆排顺序。现在顺序写在这个脚本里：
不知道下一步是什么就跑它，不用回去翻文档；每一步「做完没有」看的是文件，不是自己说做完了。
"""
import argparse, glob, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, PY, load, save, has_trad

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--tier", default="", choices=["", "lite", "full"])
ap.add_argument("--all", action="store_true")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
py = os.path.basename(PY)
S = lambda name: '%s "%s"' % (py, os.path.join(SKILL, "scripts", name))
Q = '"%s"' % proj
ex = lambda *p: os.path.exists(P(proj, *p))
mt = lambda *p: os.path.getmtime(P(proj, *p)) if ex(*p) else 0


def newer(a_, b_):
    """a_ 比 b_ 新（或 b_ 不存在）"""
    return mt(*a_) + 1 >= mt(*b_)


if not ex("project.json"):
    print("这个目录还不是口播工程。\n→ 第 1 步 建工程：%s <原片.mp4> %s\n  （工程放进对应项目的子目录，不放桌面根目录）" % (S("new_project.py"), Q))
    if not os.path.isdir(os.path.join(SKILL, "runtime", "node_modules", "remotion")):
        print("  在这之前先装环境（只装一次）：%s　——最后一行是 [setup] OK 才算好" % S("setup.py"))
    sys.exit(0)

pj = load(P(proj, "project.json"), {})
if a.tier:
    pj["tier"] = a.tier
    save(P(proj, "project.json"), pj)
LITE = pj.get("tier") == "lite" or (not pj.get("tier") and ex("decompose_lite.json") and not ex("decompose.json"))
DEC = "decompose_lite.json" if LITE else "decompose.json"
dec = load(P(proj, DEC), {}) if ex(DEC) else {}
tr = load(P(proj, "transcript.json"), {}) if ex("transcript.json") else {}
sents = tr.get("sentences", [])

steps = []   # (编号, 名称, 状态 done/todo/warn, 说明行, 详情行[])


def add(n, name, done, summary="", detail=None):
    steps.append((n, name, done, summary, detail or []))


# 1 建工程
add("1", "建工程", True, os.path.basename(proj))

# 2 转写
ok2 = ex("transcript.json") and ex("work", "aroll.mp4")
add("2", "导入转写", ok2, "%d 句" % len(sents) if ok2 else "", [
    "命令：%s %s --prompt \"这条片子里的专有名词，用顿号隔开\"" % (S("ingest.py"), Q),
    "产物：transcript.json、work/sheet_2s.jpg（每 2 秒一格的总览，看一眼人和画面）"])

# 3 校对
changed = sum(1 for s in sents if s.get("text") != s.get("raw_text"))
trad = [s["id"] for s in sents if has_trad(s.get("text", ""))]
ok3 = bool(tr.get("_corrected")) and not trad
why3 = []
if not tr.get("_corrected"):
    why3.append("还没加顶层 \"_corrected\": true")
if trad:
    why3.append("%d 句里还有繁体字（%s…）" % (len(trad), "、".join(trad[:6])))
add("3", "校对转写", ok3, ("改了 %d／%d 句" % (changed, len(sents))) if ok3 else "；".join(why3), [
    "动作：逐句改 transcript.json 的 text——错字、同音错词、人名、机构名、术语、数字口径；全部句子，不是前一半。",
    "　　　只改 text，不动 raw_text 和 chars；整句是重说的废稿写 \"drop\": true；改完在文件顶层加 \"_corrected\": true。",
    "数字：口播说「千分之一」就写「千分之一」，不要写成 1%。拿不准的字列进 facts.json 的 pending，交付时问用户。",
    "过不去：有一句没看就不算校完。规则细节：references/02 §一"])
if ok3 and changed == 0 and len(sents) > 8:
    steps[-1] = ("3", "校对转写", "warn", "标了已校对，但一句都没改——确认真的逐句看过（自动转写几乎不可能零错）", steps[-1][4])

# 4 数字核对
ncj = load(P(proj, "work", "numcheck.json"), {}) if ex("work", "numcheck.json") else {}
flagged = [r for r in ncj.get("rows", []) if r.get("flag")]
ok4 = ex("work", "numcheck.json") and newer(("work", "numcheck.json"), ("transcript.json",)) and not flagged
why4 = "" if ok4 else ("还没跑" if not ncj else ("transcript 改过，要重跑" if not newer(("work", "numcheck.json"), ("transcript.json",))
                                             else "%d 句数字对不上原声：%s" % (len(flagged), "、".join(r["id"] for r in flagged))))
add("4", "数字核对原声", ok4, why4, [
    "命令：%s %s" % (S("numcheck.py"), Q),
    "❌ 的每一句：停下来，把句号和两种读法发给用户听原声；用户确认后才在那一句写 \"num_verified\": true 和 \"num_note\"。",
    "过不去：不许自己听都没听就标 num_verified（你听不了声音）。没有带数字的句子，这一步直接过。"])

# 5 拆 A-roll
add("5", "逐句体检（人脸、清晰度、口癖、重说）", ex("work", "analysis.json"), "", [
    "命令：%s %s" % (S("analyze.py"), Q),
    "必须看：work/aroll_sheet.jpg（逐句一格带标签）。看不了图：读 work/analysis.json 里每句的 tag／why。"])

# 6 粗剪
ok6 = ex("work", "aroll_cut.mp4") and ex("work", "transcript_cut.json") and newer(("work", "transcript_cut.json"), ("transcript.json",)) \
    and (not ex("edits.json") or newer(("work", "transcript_cut.json"), ("edits.json",)))
add("6", "粗剪（剪口癖、压停顿）", ok6, "" if ok6 else ("transcript／edits 改过，要重跑 trim" if ex("work", "transcript_cut.json") else ""), [
    "动作：写 edits.json（没有要剪的就写 {}；字段见 references/02 §二）",
    "命令：%s %s --dry-run　看报告 → %s %s --verify" % (S("trim.py"), Q, S("trim.py"), Q),
    "过不去：--verify 的相似度 <0.97 就去看它列的差异；⚠ 的切点列进交付的「待人确认」。"])

# 7 节拍表
ok7 = ex("work", "beats.md") and newer(("work", "beats.md"), ("work", "transcript_cut.json"))
add("7", "逐句节拍表", ok7, "", [
    "命令：%s %s" % (S("beats.py"), Q),
    "必须读完：work/beats.md 全文（每句建议怎么处理＋这条片子的硬门槛＋形式候选）。没读完不许写分镜。"])

# 8 分镜
todo_key = "_待改" if LITE else "_待升级"
todo = dec.get(todo_key) or []
ok8 = bool(dec.get("shots") is not None and dec) and not todo
title = dec.get("title") or {}
why8 = "" if ok8 else ("还没有 %s" % DEC if not dec else "%s 里还有 %d 条没做" % (todo_key, len(todo)))
if LITE:
    d8 = ["命令：%s %s --series 系列名 --episode 本期标题" % (S("lite_plan.py"), Q),
          "动作：逐条改完 %s 里的 _待改，改完把这个键删掉。" % DEC]
else:
    d8 = ["命令：%s %s --full --series 系列名 --episode 本期标题　（出完整版底稿）" % (S("lite_plan.py"), Q),
          "动作：逐条做完 decompose.json 里的 _待升级（做法对照 references/00 的「完整版升级」表），做完把这个键删掉。只加不减。",
          "　　　锚点写句号（\"cover\": \"s17\" 或 \"s16–s19\"）；每一镜写 why；每条 B-roll 先写 see 再写 q，没有能拍的实物就不配 B-roll。",
          "禁止：从别的工程拷分镜；自创 layout 或画面类型；数字做递增计数动画。"]
add("8", "分镜（%s）" % ("极简档" if LITE else "完整版"), ok8, why8, d8)
if ok8 and title.get("series") in ("", None, "口播笔记"):
    steps[-1] = ("8", steps[-1][1], "warn", "系列名还是默认的「口播笔记」：问用户，或按内容拟一个并在交付里标「拟」", d8)

# 9 素材
bshots = [s for s in dec.get("shots", []) if s.get("type") in ("B", "S") and s.get("layout") != "doc"]
nopick = [s["id"] for s in bshots if not s.get("pick") and not s.get("image")]
missing = []
for s in bshots:
    pk = str(s.get("pick", ""))
    if pk.startswith("stock:") and not ex("broll", "stock", pk[6:] + ".mp4"):
        missing.append(s["id"])
rv = load(P(proj, "broll", "stock", "auto_review.json"), {}).get("shots", {}) if ex("broll", "stock", "auto_review.json") else {}
unrev = [s["id"] for s in bshots if str(s.get("pick", "")) == "stock:st_%s" % s["id"].lower() and rv.get(s["id"], {}).get("verdict") != "keep"]
ok9 = ok8 and not nopick and not missing and not unrev
why9 = "；".join(x for x in ["没挑素材：%s" % "、".join(nopick) if nopick else "", "文件不在：%s" % "、".join(missing) if missing else "",
                           "审片没判完：%s" % "、".join(unrev) if unrev else ""] if x)
if LITE:
    d9 = ["命令：%s %s auto --decompose %s　（自动取素材＋出审片表）" % (S("stock.py"), Q, DEC),
          "必须看：broll/stock/auto_review.jpg 的每一行（前一个画面｜素材三帧｜后一个画面），对着「应该看到」判五问，在 auto_review.json 填 verdict 和 reason。",
          "　　　　有 replace：在那一镜写新的 q，再跑 %s %s redo --decompose %s，直到全部 keep。" % (S("stock.py"), Q, DEC),
          "你看不了图片（纯文本模型）：停下，把 auto_review.jpg 发给用户判，不许自己填 keep。"]
else:
    d9 = ["先读：references/03 §零（五步推导链）。",
          "命令：%s %s plan　→ 每镜一张候选图 broll/stock/plan/<镜号>.jpg（图上印着这镜的 see）" % (S("stock.py"), Q),
          "必须看：每张候选图，对着 see 挑，不收第一个；→ %s %s get <源:id> <名字>，再在该镜写 \"pick\": \"stock:<名字>\"。" % (S("stock.py"), Q),
          "　　　　用户自己的素材：%s %s <素材目录>，pick 写 lib:编号。政策原文：node scripts/webshot.mjs（见 references/00 第 8 步）。" % (S("broll_index.py"), Q),
          "过不去：一条素材最多用 2 次；build 会核对每条素材是不是出自这一镜自己的候选表（不是就要写 pick_note 说明来源）。",
          "你看不了图片（纯文本模型）：改走极简档（next.py --tier lite），审片表发给用户判。"]
add("9", "找素材、挑素材", ok9, why9 or ("" if ok8 else "先做完第 8 步"), d9)

# 10 组装
tlp = ("remotion", "src", "timeline.json")
ok10 = ok9 and ex("timing.json") and newer(("timing.json",), (DEC,)) and newer(("timing.json",), ("work", "transcript_cut.json"))
add("10", "组装时间线", ok10, "", [
    "命令：%s %s%s" % (S("build.py"), Q, (" --decompose %s" % DEC) if LITE else ""),
    "必须看：它打印的每一条 ✗ 和 ⚠。✗ 改到没有；⚠ 逐条处理，或在交付里写明为什么不改。",
    "过不去：不许用 --draft 出的时间线交付（--draft 只给自己看结构）。"])

# 11 出处
fj = load(P(proj, "facts.json"), {}) if ex("facts.json") else {}
ncard = sum(1 for s in dec.get("shots", []) if s.get("type") == "I")
ok11 = bool(fj.get("claims")) and len(fj.get("cards") or {}) >= ncard
add("11", "写出处 facts.json", ok11, "" if ok11 else ("claims 还是空的" if not fj.get("claims") else "信息卡 %d 张，cards 只登记了 %d 张" % (ncard, len(fj.get("cards") or {}))), [
    "动作：屏上每一句非口播文字（刊头、数字卡、词卡、屏上字）写进 claims：{text, kind, source}；每张信息卡在 cards 里一条。",
    "　　　source 写到「句号＋原话」，数字类注明「原声核对」。不确定的进 pending。按当前分镜写，不从别的工程拷。"])

# 12 声音
ok12 = ex("audio", "mix.wav") and newer(("audio", "mix.wav"), ("timing.json",))
add("12", "混音", ok12, "", ["命令：%s %s --bgm <配乐文件>　（没有配乐就不带 --bgm，交付时说明）" % (S("mix.py"), Q)])

# 13 关键帧
stills = glob.glob(P(proj, "out", "stills", "*.jpg"))
ok13 = bool(stills) and max(os.path.getmtime(x) for x in stills) + 1 >= mt("timing.json")
add("13", "关键帧验收", ok13, "%d 张" % len(stills) if ok13 else "", [
    "命令：%s %s --stills <帧号,帧号,…>　（帧号看 out/分镜表.md；每种画面至少一张：人脸＋字幕、每种 B-roll 版式、数字卡、每种信息卡、结尾）" % (S("render.py"), Q),
    "必须看：out/stills/ 里每一张。字压没压脸、卡有没有出界、素材贴不贴这句话。不为验收渲整片。",
    "你看不了图片：把这些图发给用户看，交付里写明「画面未经模型目检」。"])

# 14 整片与验收
okv = ex("out", "成片_9x16.mp4") and newer(("out", "成片_9x16.mp4"), ("timing.json",))
okq = okv and ex("qa", "qa_report.md") and newer(("qa", "qa_report.md"), ("out", "成片_9x16.mp4"))
add("14", "整片渲染＋验收", okq, "" if okq else ("整片渲过了，还没跑 qa" if okv else "用户要整片时才做"), [
    "命令：%s %s　→ %s %s　→ %s %s" % (S("render.py"), Q, S("seams.py"), Q, S("qa.py"), Q),
    "必须看：qa/qa_report.md 的每个红项、qa/接缝检查.jpg。红项先判是真问题还是量法问题，真问题改，量法问题附帧说明。",
    "省资源：只想看节奏用 render.py --draft（半尺寸，不能交付）。"])

# 15 评审（完整版）
if not LITE:
    okr = bool(glob.glob(P(proj, "qa", "评审_第*轮.md")))
    add("15", "独立评审", okr, "", [
        "动作：派一个没看过制作过程的评审子代理（提示词在 references/06 §二），意见存 qa/评审_第1轮.md；有 P0 不交付。",
        "你派不了子代理：把成片和 qa 报告交给用户审，交付里写明「未做独立评审」。"])

add("16", "交付", False, "", [
    "交付回复里写：成片路径、qa 结果（不全绿就不说「全部通过」）、待人确认清单——",
    "　拟的标题与系列名、numcheck 报过的数字、剪口癖的切点、示意画面会不会误导、没修完的红项、waive 掉的项和理由。",
    "细则：references/06 §三"])

# ---------- 输出 ----------
mark = {True: "✓", False: "·", "warn": "!"}
first = next((i for i, s in enumerate(steps) if s[2] is not True), len(steps) - 1)
print("工程：%s　｜　档位：%s%s" % (proj, "极简档" if LITE else "完整版", "" if pj.get("tier") else "（默认；要改跑 next.py <工程> --tier lite）"))
for i, (n, name, done, summ, detail) in enumerate(steps):
    cur = i == first
    if not a.all and not cur and done is not True and i > first:
        continue
    print("%s %s %s%s" % ("→" if cur else mark[done], n.rjust(2), name, ("　——　" + summ) if summ else ""))
    if cur or (a.all and done is not True):
        for line in detail:
            print("      " + line)
rest = [s for s in steps[first + 1:] if s[2] is not True]
if rest and not a.all:
    print("  后面还有：%s" % " → ".join("%s %s" % (s[0], s[1]) for s in rest))
print("做完这一步再跑一次本命令。规矩总表：references/00_执行卡.md")
