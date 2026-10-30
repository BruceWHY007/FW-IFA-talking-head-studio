#!/usr/bin/env python3
"""自动底稿：从剪后逐字稿写一份 F 满幅讲述的分镜（不调模型、不找素材、不渲样片）。极简档直接用它，完整版在它上面升级。

    python3 lite_plan.py <工程目录> [--series 系列名] [--episode 本期标题] [--account 账号] [--theme 琥珀金]
        → decompose_lite.json（极简档）
    python3 lite_plan.py <工程目录> --full [--series …] [--episode …]
        → decompose.json（完整版底稿：同样的自动内容＋小窗轮换占位＋「_待升级」清单；Agent 逐条升级，build 硬检查兜底）

10-30 起的规则（references/12）：
  · 两档的区别是「谁来判断、谁挑素材、谁来审」，不是镜头多少、也不是信息少一截——**完整版 ≥ 极简档**。
  · 两档都有：数字卡（G）、步骤标题＋进度坞、堆叠清单、清单卡（I list）、金银整行、关键词变金、满幅 B-roll（按片长铺够）。
  · 只有完整版有：小窗／光晕圆／细环／分带／画框条、插条、对比卡和原话卡的人工判断、政策原文页、评审子代理。
  · 列举、序号、问题清单由 beats.py 认出来（不只认「第一／第二」字面，「三件事」「几件必须问清」「一串问句」都算）。
  · 锚点一律写句号（"s17"／"s16–s19"），build 直接认，不会「锚点找不到」。
"""
import argparse, json, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, load
import beats as BT

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--series", default="")
ap.add_argument("--episode", default="")
ap.add_argument("--account", default="")
ap.add_argument("--theme", default="")
ap.add_argument("--full", action="store_true", help="完整版底稿：写 decompose.json，带小窗轮换占位和「_待升级」清单")
ap.add_argument("--out", default="", help="输出文件名（默认：极简档 decompose_lite.json，--full 时 decompose.json）")
ap.add_argument("--max-cards", type=int, default=0, help="数字卡最多几张（默认按片长：每 45 秒 1 张，至少 2、至多 6）")
ap.add_argument("--broll", type=int, default=-1, help="满幅 B-roll 条数（默认按片长：每 14 秒 1 条；0＝不要）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
res = BT.analyze(proj)
rows, groups, DUR = res["rows"], res["groups"], res["duration"]
BT.write(proj, res)
PUNCT = BT.PUNCT
strip = BT.strip
TODO = []


def label(text, n=9):
    """条目文字：取第一个分句，去掉口头的「你／就是／还有／或者」，最长 n 字（太长的交给 Agent 改，记进待办）"""
    cs = BT.clauses(text)
    c = cs[0] if cs else text
    c = re.sub(r"^(你|就是|还有|或者是|或者|另外|再|以及|那|而)", "", c)
    c = strip(c)
    return c[:n], len(c) > n


busy = set()      # 已经有卡／屏上字的句子，B-roll 和金银整行不再落在上面
events = []       # 版面事件的时间（秒）：用来找连续人脸的空档
shots, texts, tracker = [], [], None

# ---------- 1. 成组段落 → 步骤标题（＋进度坞）／堆叠清单／清单卡 ----------
n_list = 0
for g in groups:
    its = g["items"]
    if g["kind"] == "序号串":
        for i in its:
            m = BT.ORD.match(rows[i]["text"])
            word = m.group(1).replace("是", "") if m else "第%d" % (its.index(i) + 1)
            texts.append({"kind": "step", "lines": [{"t": word, "at": rows[i]["id"]}]})
            busy.add(i); events.append(rows[i]["start"])
        if len(its) >= 3 and tracker is None:
            labs = []
            for i in its:
                body = BT.ORD.sub("", rows[i]["text"]).strip("，, ")
                t_, _ = label(body, 4)
                labs.append({"t": t_, "at": rows[i]["id"]})
            head = rows[g["head"]] if "head" in g else None
            n_ = BT.head_count(head["text"]) if head else 0
            title = ("%s个%s" % ("零一二三四五六七八九十"[len(its)], "要点")) if not head else re.sub(r"[，。].*", "", head["text"])[:8]
            tracker = {"title": title, "from": (head or rows[its[0]])["id"], "until": rows[min(its[-1] + 3, len(rows) - 1)]["id"], "items": labs}
            TODO.append("进度坞的标题和每格文字是自动摘的（%s／%s）：改成 2–4 字的名词短语" % (title, "／".join(x["t"] for x in labs)))
    else:
        n_it = len(its)
        if n_it <= 3:
            lines = []
            for i in its:
                t_, _ = label(rows[i]["text"], 8)
                lines.append({"t": t_, "at": rows[i]["id"]})
                busy.add(i)
            texts.append({"kind": "stack", "num": True, "lines": lines, "until": rows[min(its[-1] + 1, len(rows) - 1)]["id"]})
            events.append(rows[its[0]]["start"])
            TODO.append("堆叠清单「%s」是自动摘的：改成通顺的短语（≤8 字）" % "／".join(x["t"] for x in lines))
        else:
            half = math.ceil(n_it / 2)
            chunks = [its[:half], its[half:]] if n_it > 5 else [its]
            head = rows[g["head"]] if "head" in g else None
            ids_ = []
            for c_, chunk in enumerate(chunks):
                n_list += 1
                items = []
                for i in chunk:
                    t_, _ = label(rows[i]["text"], 9)
                    items.append({"t": t_, "at": strip(rows[i]["text"])[:4]})
                    busy.add(i)
                title = (re.sub(r"[，。].*", "", head["text"])[:12] if head else "%d 个问题" % n_it) + ("（%d/%d）" % (c_ + 1, len(chunks)) if len(chunks) > 1 else "")
                info = {"kind": "list", "title": title[:16], "items": items, "source": "口述"}
                if g["kind"] == "问句串":
                    info["surface"] = "paper"
                cov = "%s–%s" % (rows[chunk[0]]["id"], rows[chunk[-1]]["id"]) if len(chunk) > 1 else rows[chunk[0]]["id"]
                shots.append({"id": "I%02d" % n_list, "type": "I", "cover": cov, "info": info,
                              "why": "口播在列举（%s）：做成清单卡逐条亮，观众能对着数" % ("问题清单" if g["kind"] == "问句串" else "%d 条" % len(chunk))})
                ids_.append("I%02d" % n_list)
                events.append(rows[chunk[0]]["start"])
            TODO.append("清单卡 %s 的标题和条目是自动摘的：每条 ≤9 字、读起来是完整的意思" % "、".join(ids_))

# ---------- 2. 数字卡：句中第一个「数字＋单位」，按片长定张数，相隔 ≥14 秒 ----------
max_cards = a.max_cards or max(2, min(6, round(DUR / 45)))
cands = [(r["start"], k, r["nums"][0]) for k, r in enumerate(rows) if r["nums"] and k not in busy]
cands.sort(key=lambda x: -(2 if re.search(r"[%‰]|分之", x[2]) else 1) - (1 if "." in x[2] else 0))
picked = []
for t0, k, num in cands:
    if len(picked) >= max_cards:
        break
    if all(abs(t0 - p[0]) >= 14 for p in picked) and all(abs(t0 - e) >= 4 for e in events):
        picked.append((t0, k, num))
for i, (t0, k, num) in enumerate(sorted(picked), 1):
    m = re.match(r"(.*?)(%|‰|个工作日|个月|万亿|万|亿|倍|年|天|人|家|位|岁|成|元|港元|块)?$", num.replace(" ", ""))
    val, unit = (m.group(1), m.group(2) or "") if m else (num, "")
    txt = rows[k]["text"]
    pos = txt.find(num)
    lead = strip(txt[max(0, pos - 2):pos])
    shots.append({"id": "G%02d" % i, "type": "G", "cover": (lead + num).strip(PUNCT),
                  "figure": {"kind": "number", "value": val.replace("-", "–"), "unit": unit, "label": "", "at": num},
                  "why": "这句的硬数字落成数字卡（只盖数字＋≤1 秒引子）"})
    busy.add(k); events.append(t0)
    TODO.append("数字卡 G%02d「%s」：补一行 label（这个数是什么，≤12 字）；数字必须过 numcheck" % (i, num))

# ---------- 3. 满幅 B-roll：只配在「有东西可拍」的句子上（beats 标了实物／地点），按片长铺，相邻两条不同题材 ----------
# 10-30：上一版按「人脸空档的时间中点」挑句子，挑中的多是抽象句（「不在管辖范围里」「信托有没有实质控制」），
# 自动检索只能配出护照、街舞、金属环、递钥匙。Claude 定稿的 12 条 B-roll 每一条都先认出「这句指的是什么」再搜。
# 空档里没有能拍的句子就不配 B-roll——那一段靠清单卡、金银整行、插条扛，宁缺毋滥。
n_b = a.broll if a.broll >= 0 else math.ceil(DUR / 14)
brolls, skipped = [], []
if n_b:
    ev = sorted(set([0.0, DUR] + events))
    gaps = [(x, y) for x, y in zip(ev, ev[1:]) if y - x > 9]
    want = {g: max(1, int((g[1] - g[0]) // 14)) for g in gaps}
    for g in sorted(gaps, key=lambda g: g[1] - g[0]):   # 条数超了：从短空档开始减
        while sum(want.values()) > n_b and want[g] > 0:
            want[g] -= 1
    last_concept = None
    for (x, y), nn in sorted(want.items()):
        span = (y - x) / (nn + 1)
        for j in range(nn):
            mid = x + span * (j + 1)
            pool = [k for k, r in enumerate(rows) if x + 1.5 < r["start"] < y - 2.5 and k not in busy and 1 < k < len(rows) - 2
                    and r["kind"] in ("地点", "实物") and r["concept"] != last_concept]
            if not pool:
                skipped.append("%d–%d 秒" % (x, y)); continue
            k = min(pool, key=lambda k: abs(rows[k]["start"] - mid))
            k2 = k
            if k + 1 < len(rows) and k + 1 not in busy and rows[k]["end"] - rows[k]["start"] < 3 and rows[k + 1]["end"] - rows[k]["start"] <= 6.5:
                k2 = k + 1
            r = rows[k]
            brolls.append({"id": "B%02d" % (len(brolls) + 1), "type": "B", "layout": "full",
                           "cover": r["id"] if k2 == k else "%s–%s" % (r["id"], rows[k2]["id"]),
                           "see": r["see"], "q": list(r["queries"]),
                           "why": "「%s」→ %s" % (strip(r["text"])[:14], r["see"])})
            busy.update({k, k2}); events.append(r["start"]); last_concept = r["concept"]
    if brolls:
        TODO.append("B-roll 的 see（观众应该看到什么）是按词表套的：逐条对着原话改具体（「香港实景」→「中环中银大厦白天外立面」），再按 see 改 q")
    if skipped:
        TODO.append("这些空档里没有能拍的句子，没配 B-roll（宁缺毋滥）：%s——靠清单卡／金银整行／插条撑，别硬配泛化画面" % "、".join(sorted(set(skipped))))
shots += brolls

# ---------- 4. 金银整行：用 beats 的候选，先填「连续人脸 >10 秒没有版面事件」的空档，再凑够门槛 ----------
gold, silver = [], []
cands_g = [(rows[k]["start"], rows[k]["gold"][0]) for k in range(len(rows)) if rows[k]["gold"] and k not in busy]
marks = sorted(set([0.0, DUR] + events))
for _ in range(40):
    gp = [(x, y) for x, y in zip(marks, marks[1:]) if y - x > 10]
    if not gp:
        break
    x, y = max(gp, key=lambda g: g[1] - g[0])
    pool = [(t, c) for t, c in cands_g if x + 2 < t < y - 2 and c not in gold + silver]
    mid = (x + y) / 2
    if not pool:
        marks.append(mid); marks.sort(); continue
    t, c = min(pool, key=lambda tc: abs(tc[0] - mid))
    (gold if len(gold) <= len(silver) else silver).append(c)
    marks.append(t); marks.sort()
for t, c in cands_g:   # 片子短、空档少时也至少凑够门槛（完整版 build 要查）
    if len(gold) + len(silver) >= res["need"]["gold"]:
        break
    if c not in gold + silver:
        gold.append(c)

# ---------- 5. 关键词变金：数字短语＋引号里的词 ----------
hl = []
for r in rows:
    for n in r["nums"]:
        n = n.replace(" ", "")
        if n not in hl:
            hl.append(n)
    for q in re.findall(r"[「“]([^」”]{2,8})[」”]", r["text"]):
        if q not in hl:
            hl.append(q)
hl = hl[:10]

first = strip(rows[0]["text"])[:14] if rows else "口播笔记"
dec = {
    "_说明": ("完整版底稿（lite_plan.py --full）：自动内容＋小窗轮换占位。按「_待升级」逐条做完再 build；build 按片长查表达层，不够就停。"
              if a.full else "极简档自动规划（lite_plan.py）：数字卡＋屏上字＋清单卡＋金银整行＋满幅 B-roll；素材走 stock.py auto → 审片。"),
    "style": "F",
    "account": a.account or "",
    "theme": a.theme or "琥珀金",
    "title": {"series": a.series or "口播笔记", "episode": a.episode or first, "lines": [a.series or "口播笔记", a.episode or first]},
    "disclaimer": "本内容仅作为科普，不构成任何投资建议",
    "outro": 0.8,
    "captions": {"highlight": hl, "gold": gold, "silver": silver},
    "texts": texts,
    "shots": shots,
}
if tracker:
    dec["tracker"] = tracker
if not (a.series and a.episode):
    TODO.insert(0, "系列名／本期标题没给：title 按原话拟了一个，交付时标「拟」，或问用户")
if a.full:
    # 小窗轮换占位：同一种不连用三次；素材到了再按 references/11 换（白底别用 glow、横版素材用 band、三条同题材素材才用 bands3）
    ROT = ["full", "pip", "glow", "full", "ring", "pip", "glowband", "full"]
    for j, sh in enumerate(brolls):
        sh["layout"] = ROT[j % len(ROT)]
    TODO += [
        "B-roll 的小窗版式（pip／glow／ring／glowband）是轮换占位：看了素材再定——白底不用 glow、横版用 band、有三条同题材素材可用 bands3",
        "每条 B-roll 的 why 写清「这条画面在这句里指什么」；写不出就别配，改成留脸或信息卡",
        "插条 inserts：在最长的几段满幅人脸里放 1–2 条（盖住她一部分、她还在），写法见 references/13 §3",
        "对比：beats.md 里标「对比」或一句两个数的地方，挑最关键的一处做 I compare（两边各一个标签＋值）",
        "金银整行只留最硬的判断；自动挑的不对就换（必须是字幕里连着的一段原话）",
    ]
    pol = [r for r in rows if "政策" in r["tags"]]
    if pol:
        TODO.insert(0, "口播提到政策／办法（%s「%s」）：用 webshot.mjs 截官方原文做 layout:\"doc\" 原文页（荧光带扫那一句），出处进 facts.json" % (pol[0]["id"], pol[0]["text"][:16]))
    dec["_待升级"] = TODO
else:
    dec["lite"] = True
    dec["_待改"] = TODO
out = P(proj, a.out or ("decompose.json" if a.full else "decompose_lite.json"))
if a.full and os.path.exists(out) and not a.out:
    os.replace(out, out + ".bak")
    print("· 旧的 decompose.json 备份成 decompose.json.bak")
json.dump(dec, open(out, "w"), ensure_ascii=False, indent=1)
ns = {k: sum(1 for s in shots if s["type"] == k) for k in "GIB"}
print("✓ %s：数字卡 %d、清单卡 %d、B-roll %d、屏上字 %d 组%s、金银整行 %d、关键词 %d" % (
    os.path.basename(out), ns["G"], ns["I"], ns["B"], len(texts), "＋进度坞" if tracker else "", len(gold) + len(silver), len(hl)))
for t in TODO:
    print("  · %s：%s" % ("待升级" if a.full else "待改", t))
if not os.path.exists(P(proj, "work", "numcheck.json")):
    print("⚠ 还没跑 numcheck.py：数字卡来自转写，转写常把千分之写成 %——先核对原声")
print("下一步：python3 stock.py %s auto --decompose %s → 看 broll/stock/auto_review.jpg 逐条判（理由写画面主体）→ build.py %s%s" % (
    proj, os.path.basename(out), proj, "" if a.full else " --decompose " + os.path.basename(out)))
