#!/usr/bin/env python3
"""极简档：从剪后逐字稿**自动**写一份 F 满幅讲述的 decompose_lite.json（不调模型、不找素材、不渲样片）。

    python3 lite_plan.py <工程目录> [--series 系列名] [--episode 本期标题] [--account 账号] [--theme 琥珀金]
    python3 build.py <工程> --decompose <工程>/decompose_lite.json && python3 render.py <工程>

和完整版同一套 F 包（字体、金银字、刊头、字幕、玻璃卡、进度动效都一样），省的是**判定和素材**这两步：
  · 画面只用：她满幅 ＋ 数字卡／词卡（G）＋ 步骤标题（第一…第二…）＋ 关键词变金 ＋ 呼吸与重话快推
  · 不用：B-roll、AI 生成、免费素材检索、插条、分带、小窗、进度坞、原文截图、信息卡（I）
  · 要 B-roll 的地方，规划里只留 `tips`（建议在哪几句补一条），不阻塞出片
规则全文：references/12_极简档.md
"""
import argparse, json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, load

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--series", default="")
ap.add_argument("--episode", default="")
ap.add_argument("--account", default="")
ap.add_argument("--theme", default="")
ap.add_argument("--max-cards", type=int, default=6, help="数字卡／词卡最多几张（默认 6，和进度动效一起别超过 25% 时长）")
ap.add_argument("--broll", type=int, default=6, help="满幅 B-roll 最多几条（默认 6；0＝不要）")
ap.add_argument("--gap", type=float, default=14.0, help="两张卡之间至少隔几秒（默认 14）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)
tc_p = P(proj, "work", "transcript_cut.json")
tc = load(tc_p) if os.path.exists(tc_p) else load(P(proj, "transcript.json"))
sents = tc["sentences"]

NUM = re.compile(r"(\d+(?:\.\d+)?(?:[-–]\d+(?:\.\d+)?)?)\s*(%|个工作日|个月|万亿|万|亿|倍|年|天|人|家|位|岁|成)")
ORD = re.compile(r"^(第[一二三四五六七八九十]|[一二三四五六七八九十]是|首先|其次|最后)")
PUNCT = "，。、！？；：,.!?;: "


def strip(t):
    return "".join(c for c in t if c not in PUNCT)


# ---------- 1. 数字卡：每句取第一个「数字＋单位」，卡与卡隔 ≥gap 秒，最多 max-cards 张 ----------
cands = []
for s in sents:
    m = NUM.search(s["text"])
    if m:
        cands.append((s["start"], s, m))
picked, last = [], -999.0
# 先选数字最“硬”的（带单位的小数、百分号），再按时间回排
cands.sort(key=lambda x: -(2 if "%" in x[2].group(0) else 1) - (1 if "." in x[2].group(1) else 0))
for t0, s, m in cands:
    if len(picked) >= a.max_cards:
        break
    if all(abs(t0 - p[0]) >= a.gap for p in picked):
        picked.append((t0, s, m))
picked.sort(key=lambda x: x[0])

shots = []
for i, (t0, s, m) in enumerate(picked, 1):
    txt = s["text"]
    k = m.start()
    # 锚点：数字前最多 2 个字 ＋ 数字 ＋ 单位；G 卡只盖这几个字（build 对 >1.2s 报警）
    lead = strip(txt[max(0, k - 2):k])
    anchor = (lead + txt[k:m.end()]).strip(PUNCT)
    unit = m.group(2)
    shots.append({"id": "G%02d" % i, "type": "G", "cover": anchor,
                  "figure": {"kind": "number", "value": m.group(1).replace("-", "–"), "unit": unit, "label": "", "at": m.group(0)},
                  "why": "极简档：句中第一个数字落成数字卡"})

# ---------- 2. 步骤标题：口播里说「第一、第二…」的句子 ----------
texts = []
for s in sents:
    mm = ORD.match(s["text"])
    if mm:
        word = mm.group(1)
        word = {"首先": "首先", "其次": "其次", "最后": "最后"}.get(word, word.replace("是", ""))
        texts.append({"kind": "step", "lines": [{"t": word, "at": s["text"][:len(mm.group(1)) + 3].strip(PUNCT)}]})

# ---------- 3. 关键词变金：数字短语 ＋ 出现 ≥2 次的 2–4 字名词性词组（保守：只取数字短语与引号里的词） ----------
hl = []
for s in sents:
    for m in NUM.finditer(s["text"]):
        if m.group(0) not in hl:
            hl.append(m.group(0))
    for q in re.findall(r"[「“]([^」”]{2,8})[」”]", s["text"]):
        if q not in hl:
            hl.append(q)
hl = hl[:10]

# ---------- 4. 金／银整行：填满「连续人脸 >10s 没有版面事件」的空档（每个空档挑中间一个 5–12 字的短分句） ----------
STRONG = re.compile(r"不|别|必须|一定|千万|只|就是|才|第一|关键|重点|记住|注意|不是|没有|而是")
ev_t = sorted([p[0] for p in picked] + [s["start"] for s in sents if ORD.match(s["text"])])
dur = tc.get("duration", sents[-1]["end"] if sents else 0)
clauses = []
for s in sents:
    for c in re.split(r"[，。、！？；：,.!?; ]", s["text"]):
        c = c.strip()
        if 5 <= len(c) <= 12 and not NUM.search(c) and not ORD.match(c):
            # 子句起点按字符比例估（只用来分空档，不用来对位）
            i0 = s["text"].find(c)
            t_c = s["start"] + (s["end"] - s["start"]) * i0 / max(len(s["text"]), 1)
            clauses.append((t_c, c))
gold, silver = [], []
marks_ = sorted(set([0.0] + ev_t + [dur]))
def gaps(ms):
    return [(x, y) for x, y in zip(ms, ms[1:]) if y - x > 10]
guard = 0
while gaps(marks_) and guard < 30:
    guard += 1
    x, y = max(gaps(marks_), key=lambda g: g[1] - g[0])
    mid = (x + y) / 2
    pool = [(t_c, c) for t_c, c in clauses if x + 3 < t_c < y - 3 and c not in gold + silver]
    if not pool:
        marks_.append(mid); marks_.sort(); continue
    t_c, c = min(pool, key=lambda tc_: abs(tc_[0] - mid) - (4 if STRONG.search(tc_[1]) else 0))
    (gold if len(gold) <= len(silver) else silver).append(c)
    marks_.append(t_c); marks_.sort()

# ---------- 5. 满幅 B-roll（只用 full 版式，不做小窗／分带）：挑最长的人脸空档，每个空档取中间一句 ----------
brolls = []
if a.broll:
    ev_all = sorted(set([0.0, dur] + ev_t))
    slots = sorted([(y - x, x, y) for x, y in zip(ev_all, ev_all[1:]) if y - x > 8], reverse=True)[:a.broll]
    for _, x, y in sorted(slots, key=lambda t: t[1]):
        mid = (x + y) / 2
        s_mid = min([s for s in sents if x + 2 < s["start"] < y - 4] or sents, key=lambda s: abs((s["start"] + s["end"]) / 2 - mid))
        txt = s_mid["text"]
        brolls.append({"id": "B%02d" % (len(brolls) + 1), "type": "B", "layout": "full", "cover": txt[:14].strip(PUNCT) if len(strip(txt)) <= 16 else strip(txt)[:6] + "…" + strip(txt)[-6:],
                       "why": "极简档：连续人脸空档里补一条满幅 B-roll（stock.py auto 自动取素材）"})
shots = sorted(shots + brolls, key=lambda sh: 0)   # 顺序交给 build（按锚点定位）

first = strip(sents[0]["text"])[:14] if sents else "口播笔记"
dec = {
    "_说明": "极简档自动规划（lite_plan.py）：只用满幅人脸＋数字卡＋步骤标题＋关键词变金；要补 B-roll 的地方见 tips。",
    "style": "F",
    "account": a.account or "",
    "theme": a.theme or "琥珀金",
    "title": {"series": a.series or "口播笔记", "episode": a.episode or first,
              "lines": [a.series or "口播笔记", a.episode or first]},
    "disclaimer": "本内容仅作为科普，不构成任何投资建议",
    "outro": 0.8,
    "captions": {"highlight": hl, "gold": gold, "silver": silver},
    "texts": texts,
    "shots": shots,
    "lite": True,
}
# tips：最长的连续人脸段（>12s）里，挑中间一句建议补 B-roll——只提示，不阻塞
tips, face_from = [], 0.0
marks = sorted([(p[0], p[0] + 2.5) for p in picked] + [(s["start"], s["start"] + 2.0) for s in sents if ORD.match(s["text"])])
prev = 0.0
for t0, t1 in marks + [(tc.get("duration", 0), tc.get("duration", 0))]:
    if t0 - prev > 12:
        mid = prev + (t0 - prev) / 2
        s_mid = min(sents, key=lambda s: abs((s["start"] + s["end"]) / 2 - mid))
        tips.append("%d–%d 秒连续人脸 %.0f 秒，建议在「%s」补一条 B-roll（可选）" % (prev, t0, t0 - prev, s_mid["text"][:14]))
    prev = max(prev, t1)
dec["tips"] = tips
out = P(proj, "decompose_lite.json")
json.dump(dec, open(out, "w"), ensure_ascii=False, indent=1)
print("✓ %s：数字卡 %d 张、步骤标题 %d 处、金银整行 %d 句、关键词 %d 个" % (out, len(shots), len(texts), len(gold) + len(silver), len(hl)))
for t in tips:
    print("  · tips：" + t)
print("下一步：python3 stock.py %s auto --decompose %s ；python3 build.py %s --decompose %s ；python3 render.py %s" % (proj, out, proj, out, proj))
