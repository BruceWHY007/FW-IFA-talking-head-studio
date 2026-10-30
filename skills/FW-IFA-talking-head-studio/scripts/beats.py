#!/usr/bin/env python3
"""⑤ 之前：逐句打标签，给每句「建议用什么处理」，并预告完整版硬检查会要什么（10-30 新增）。

    python3 beats.py <工程目录>        → work/beats.md（人看）＋ work/beats.json（lite_plan 读）

为什么有它：13 号手册 §4.2 写了「她在说什么 → 用什么」，但弱一点的模型读不到那一节，就会自创画面（10-30 DeepSeek 自写 motion 动效、
完整版连金银整行都没有）。这张表把 §4.2 落到这一条片子的每一句上：Agent 写分镜时只做「选、改、写 why」，不用从零想。
标签全靠规则，**只是候选**——内容决定最后用什么（SKILL.md §3.5），表里没提示的地方也可以按内容设计。
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, load

PUNCT = "，。、！？；：,.!?;:“”\"'「」 "
CN = "零〇一二两三四五六七八九十百千万亿"
NUM = re.compile(r"(\d+\s*万\s*\d+(?:\s*千\s*\d+)?|\d+(?:\.\d+)?(?:\s*[-–到至]\s*\d+(?:\.\d+)?)?\s*(?:%%|‰|个工作日|个月|万亿|万|亿|倍|年|天|人|家|位|岁|成|元|港元|块)"
                 r"|[%s]{2,}(?:万亿|万|亿|倍|成|年|个工作日)|[一二三四五六七八九两]成|(?:百|千|万)分之[%s点]+)" % (CN, CN))
ORD = re.compile(r"^(第[一二三四五六七八九十](?![条款章节号])|[一二三四五六七八九十]是|首先|其次|再者|另外|最后)")
ENUM_HEAD = re.compile(r"(几|[一二三四五六七八九十两\d])\s*(件事|件|个问题|个变化|个原因|个误区|个坑|条|类|点|种|样|步|层|方面|个)(?=[，。：:！？]|$|就|是|要|我|你|必须|值得)")
QUESTION = re.compile(r"[？?]$|吗[？?。]?$|^(谁|怎么|多少|哪|有没有|能不能|是不是|要不要|会不会)|有没有|能不能|是不是|要不要|怎么[算分办]|归谁|谁掏|多少")
POLICY = re.compile(r"办法|条例|规定|号令|细则|指引|新规|法规|通知|公告|征求意见|第\s*\d+\s*条|第[一二三四五六七八九十百]+条")
COMPARE = re.compile(r"不是.{1,14}(而是|是)|而是|相比|高出|低于|比.{1,6}(高|低|多|少)|两套|两条|另一面|反面|不是一回事|不一样|vs|VS|一边.{1,10}一边")
STRONG = re.compile(r"不|别|必须|一定|千万|只|就是|才|关键|重点|记住|注意|不是|没有|而是|从来")
CTA = re.compile(r"关注|评论|私信|留言|点赞|收藏|转发|给你一个动作|最后一句|记住这|拿问题去问")
FIRST = re.compile(r"我(在|们|做|见|去|当|刚|来|自己|的客户|入行|第一次)")


CNN = {"一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def head_count(t):
    """「不是办公室气派，是三件事」→ 3；「七个变化，我只讲…四个」→ 4（取最后一个）；「几件」→ 0（不定）"""
    ms = list(ENUM_HEAD.finditer(t))
    if not ms:
        return None
    x = ms[-1].group(1)
    return 0 if x == "几" else int(x) if x.isdigit() else CNN.get(x, 0)


def strip(t):
    return "".join(c for c in t if c not in PUNCT)


def load_sents(proj):
    tc_p = P(proj, "work", "transcript_cut.json")
    tc = load(tc_p) if os.path.exists(tc_p) else load(P(proj, "transcript.json"))
    return [s for s in tc["sentences"] if not s.get("drop")], tc.get("duration") or (tc["sentences"][-1]["end"] if tc["sentences"] else 0)


def clauses(text):
    return [c.strip() for c in re.split(r"[，。、！？；：,.!?;: ]", text) if c.strip()]


def analyze(proj):
    sents, dur = load_sents(proj)
    lex = load(os.path.join(SKILL, "template", "broll_lexicon.json"))["concepts"]
    rows = []
    for k, s in enumerate(sents):
        t = s["text"].strip()
        tags, obj = [], None
        if k < 2 or s["start"] < 6:
            tags.append("钩子")
        if POLICY.search(t):
            tags.append("政策")
        nums = [m.group(0) for m in NUM.finditer(t) if not re.fullmatch(r"(19|20)\d\d\s*年|\d+\s*[月日号]", m.group(0).strip())]
        if nums:
            tags.append("数字")
        if ORD.match(t):
            tags.append("序号")
        if ENUM_HEAD.search(t) and not re.search(r"\d+\s*个工作日|\d+\s*个月", t):
            tags.append("列举头")
        if QUESTION.search(t):
            tags.append("问句")
        if COMPARE.search(t):
            tags.append("对比")
        if CTA.search(t) or k >= len(sents) - 2:
            tags.append("收尾")
        if FIRST.search(t):
            tags.append("第一人称")
        for c in lex:
            if any(key in t for key in c["keys"]):
                obj = c
                break
        if obj:
            tags.append("实物")
        gold = [c for c in clauses(t) if 4 <= len(strip(c)) <= 12 and STRONG.search(c) and not NUM.search(c)]
        rows.append({"id": s["id"], "start": round(s["start"], 2), "end": round(s["end"], 2), "text": t, "tags": tags,
                     "nums": nums, "concept": obj["name"] if obj else "", "queries": obj["queries"][:3] if obj else [],
                     "prefer": obj.get("prefer", "") if obj else "", "gold": gold[:1]})

    # ---- 成组：序号串（第一…第二…）、列举头＋后面的短句、连续问句 ----
    groups, used = [], set()
    ords = [i for i, r in enumerate(rows) if "序号" in r["tags"]]
    run = []
    for i in ords:
        if run and rows[i]["start"] - rows[run[-1]]["start"] > 45:
            if len(run) >= 2:
                groups.append({"kind": "序号串", "items": run})
            run = []
        run.append(i)
    if len(run) >= 2:
        groups.append({"kind": "序号串", "items": run})
    # 只有两项、又夹着「最后／首先」或隔得远的，多半是「第三类…最后一句」这种碰巧，不算序号串
    groups = [g for g in groups if len(g["items"]) >= 3 or (all(rows[i]["text"].startswith("第") for i in g["items"])
              and rows[g["items"][1]]["start"] - rows[g["items"][0]]["start"] < 30)]
    for g in groups:
        used.update(g["items"])
    for i, r in enumerate(rows):
        if "列举头" not in r["tags"] or i in used or re.search(r"(这|那|完)[几一二两三四五六七八九十]", r["text"]):
            continue
        n_ = head_count(r["text"])
        og = next((g for g in groups if g["kind"] == "序号串" and "head" not in g and 0 < rows[g["items"][0]]["start"] - r["start"] < 20), None)
        if og:
            og["head"] = i; used.add(i); continue
        items = []
        for j in range(i + 1, min(i + 12, len(rows))):
            if j in used:
                break
            rj = rows[j]
            short = len(strip(rj["text"])) <= (24 if n_ else 14)
            if n_ and len(items) >= n_:
                break
            if short or "问句" in rj["tags"]:
                items.append(j)
            elif items or n_ == 0:
                break
        if len(items) >= 2:
            groups.append({"kind": "列举", "head": i, "items": items, "n": n_})
            used.update(items + [i])
    qrun = []
    for i, r in enumerate(rows + [{"tags": []}]):
        if i < len(rows) and "问句" in r["tags"] and i not in used:
            qrun.append(i)
        else:
            if len(qrun) >= 3:
                groups.append({"kind": "问句串", "items": qrun})
                used.update(qrun)
            qrun = []

    # ---- 每句的建议处理（13 号 §4.2）----
    gid = {}
    for n, g in enumerate(groups):
        for i in g["items"] + ([g["head"]] if "head" in g else []):
            gid[i] = n
    last_c = {}
    for i, r in enumerate(rows):
        tg, sug = r["tags"], []
        if i in gid:
            g = groups[gid[i]]
            n_it = len(g["items"])
            if g["kind"] == "序号串":
                sug.append("texts.step 步骤标题" + ("＋tracker 进度坞（%d 格）" % n_it if n_it >= 3 else ""))
            elif n_it <= 3:
                sug.append("texts.stack 堆叠清单（%d 行，num:true）" % n_it)
            else:
                sug.append("I list 清单卡（%d 条%s；问题清单可用 surface:\"paper\" 皱纸单）" % (n_it, "，超过 5 条拆成两张" if n_it > 5 else ""))
        if "政策" in tg:
            sug.append("doc 官方原文页（webshot.mjs 截原文，说到那句荧光带扫过）")
        if "数字" in tg:
            two = len(r["nums"]) >= 2 or (i + 1 < len(rows) and rows[i + 1]["nums"])
            sug.append("I compare 对比卡（两个数并排）" if two else "G 数字卡（只盖「%s」＋≤1 秒引子）" % r["nums"][0])
        if "对比" in tg and "数字" not in tg:
            sug.append("I compare 对比卡，或把「是」那半句做金银整行")
        if r["concept"] and not sug and r["concept"] != last_c.get("c") or (r["concept"] and not sug and r["start"] - last_c.get("t", -99) > 15):
            last_c.update(c=r["concept"], t=r["start"])
            sug.append("B-roll：%s（q 例：%s）" % (r["concept"], " / ".join(r["queries"][:2])))
        if r["gold"] and not sug:
            sug.append("金银整行候选「%s」" % r["gold"][0])
        if "钩子" in tg and not sug:
            sug.append("留脸（开场钩子 84px）")
        if "收尾" in tg and not sug:
            sug.append("留脸（号召回到脸）")
        if "第一人称" in tg and not sug:
            sug.append("留脸，或 S 本人素材（她自己的办公室／见客户）")
        if not sug:
            sug.append("留脸；连续人脸 >12 秒时这里可放插条 inserts／金银整行")
        r["suggest"] = sug
    # ---- 完整版硬检查预告（和 build.py 7.9 同一套门槛）----
    mins = dur / 60.0
    n_ord = sum(1 for r in rows if "序号" in r["tags"])
    need = {"gold": max(3, round(mins * 1.5)), "texts": max(2, round(mins * 1.2)), "layouts": 4 if dur >= 90 else 3,
            "inserts": 1 if dur >= 60 else 0, "info": 1, "tracker": 1 if n_ord >= 3 else 0,
            "doc": 1 if any("政策" in r["tags"] for r in rows) else 0, "face": "40–78%"}
    return {"duration": round(dur, 2), "rows": rows, "groups": groups, "need": need}


def write(proj, res):
    out = P(proj, "work", "beats.json")
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    rows, groups, need = res["rows"], res["groups"], res["need"]
    L = ["# 逐句节拍表（beats.py 自动生成：只是候选，内容决定最后用什么）", "",
         "锚点直接写句号：`\"cover\": \"s17\"` 或 `\"s16–s19\"`；`texts`／`tracker` 的 `at` 也可以写句号。", "",
         "## 完整版硬检查会要（build 不达标就停；确实用不上写 `waive`）", "",
         "| 项 | 这条片子至少 |", "|---|---|"]
    for k, lab in [("gold", "金银整行 captions.gold／silver"), ("texts", "屏上字 texts"), ("layouts", "B-roll 画面处理种类"),
                   ("inserts", "插条 inserts"), ("info", "信息卡 I"), ("tracker", "进度坞 tracker"), ("doc", "政策原文页 doc"), ("face", "满幅人脸占比")]:
        L.append("| %s | %s |" % (lab, need[k]))
    gc = [(r["id"], r["gold"][0]) for r in rows if r["gold"]]
    L += ["", "## 金银整行候选（captions.gold／silver 写成字幕里连着的原话片段；最硬的判断才用，挑 %s 句以上、隔开分布）" % need["gold"], ""]
    L.append("、".join("%s「%s」" % x for x in gc[:24]) or "（没挑出：自己从观点句里挑 4–12 字的短分句）")
    L += ["", "## 成组的段落（列举、序号、问题清单——最该做成屏上字或卡片的地方）", ""]
    if not groups:
        L.append("（没认出成组的段落：口播里没有「第一／第二」「三件事」「一串问题」这类结构）")
    for g in groups:
        ids = [rows[i]["id"] for i in g["items"]]
        head = ("头句 %s「%s」，" % (rows[g["head"]]["id"], rows[g["head"]]["text"][:20])) if "head" in g else ""
        L.append("- **%s** %s条目 %s：%s" % (g["kind"], head, "、".join(ids), "／".join(strip(rows[i]["text"])[:10] for i in g["items"])))
    L += ["", "## 逐句", "", "| 句号 | 时间 | 原话 | 标签 | 建议处理 |", "|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %d:%04.1f | %s | %s | %s |" % (r["id"], r["start"] // 60, r["start"] % 60, r["text"].replace("|", "｜"),
                                                    "、".join(r["tags"]) or "—", "；".join(r["suggest"])))
    open(P(proj, "work", "beats.md"), "w").write("\n".join(L) + "\n")
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    proj = os.path.abspath(sys.argv[1])
    res = analyze(proj)
    write(proj, res)
    tagc = {}
    for r in res["rows"]:
        for t in r["tags"]:
            tagc[t] = tagc.get(t, 0) + 1
    print("✓ work/beats.md：%d 句，%s" % (len(res["rows"]), "、".join("%s %d" % kv for kv in tagc.items())))
    for g in res["groups"]:
        print("  · %s：%s" % (g["kind"], "、".join(res["rows"][i]["id"] for i in g["items"])))
    print("  完整版至少：金银整行 %(gold)s、屏上字 %(texts)s、画面处理 %(layouts)s 种、插条 %(inserts)s、信息卡 %(info)s、进度坞 %(tracker)s、原文页 %(doc)s，人脸 %(face)s" % res["need"])
