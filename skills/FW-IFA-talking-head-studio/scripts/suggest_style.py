#!/usr/bin/env python3
"""④-0 按内容推荐风格包、封面形式和信息卡（只给建议和理由，最后由人或 agent 定，写进 decompose.json）。

    python3 suggest_style.py <工程目录>

读剪后逐字稿（没剪就读 transcript.json）。判断依据见 references/04 §〇「内容 → 风格包」。
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, load

proj = os.path.abspath(sys.argv[1])
tc = load(P(proj, "work", "transcript_cut.json")) if os.path.exists(P(proj, "work", "transcript_cut.json")) else load(P(proj, "transcript.json"))
sents = [s["text"] for s in tc["sentences"]]
full = "".join(sents)
mins = max(tc.get("duration", 60) / 60, 0.5)
reg_p = P(os.path.dirname(proj), "_口播形式登记.json")
dec = load(P(proj, "decompose.json"), {})
acct = dec.get("account", "")

NUM = re.compile(r"\d+(?:\.\d+)?\s*(?:%|万|亿|倍|宗|家|个|年|月|岁|人)|[一二三四五六七八九十百千两]+(?:万|亿|个人|倍|成)")
def count(words):
    return sum(full.count(w) for w in words)
sig = {
    "数字": len(NUM.findall(full)) / mins,
    "出处": count(["报告", "指引", "政策", "规定", "条例", "官方", "统计", "数据显示", "公布", "发布", "保监局", "证监会", "政府", "研究", "调查"]) / mins,
    "个人": count(["我", "孩子", "家", "最近", "这几个月", "朋友", "我们家", "老公", "太太"]) / mins,
    "品牌": count(["复星", "平台", "加入", "招募", "IFA", "理财师", "我们公司", "团队"]) / mins,
    "热点": count(["热搜", "新闻", "最近都在", "很多人说", "刷屏", "争议", "火了", "爆了"]) / mins,
    "活动": count(["开业", "活动", "发布会", "典礼", "邀请", "欢迎", "现场"]) / mins,
}
score = {
    "F 满幅讲述（默认）": 4.0 + sig["数字"] * 0.2 + sig["出处"] * 0.3,   # 默认包：没有明确理由选别的，就是它
    "A 分带刊物": sig["个人"] * 1.0 + 2,
    "B 雾金玻璃": sig["活动"] * 3 + sig["品牌"] * 0.6,
    "C 港刊大字": sig["热点"] * 3 + (2 if sig["数字"] < 2 and sig["个人"] < 6 else 0),
    "K1 证据桌": sig["出处"] * 3 + sig["数字"] * 0.3,
    "K2 图解": sig["数字"] * 1.0 + sig["出处"] * 0.5,
    "K3 IFA 品牌刊": sig["品牌"] * 1.2 + sig["数字"] * 0.2,
}
why = {
    "F 满幅讲述（默认）": "默认：观点讲述、政策解读、财经科普；除非下面某一项明显更高",
    "A 分带刊物": "个人近况、生活、经历（第一人称每分钟 %.1f 次）" % sig["个人"],
    "B 雾金玻璃": "活动、开业、品牌宣传（活动词 %.1f／分）" % sig["活动"],
    "C 港刊大字": "热点、观点、金句（热点词 %.1f／分）" % sig["热点"],
    "K1 证据桌": "引用报告、政策、原话（出处词 %.1f／分）" % sig["出处"],
    "K2 图解": "数字、对比、走势（数字 %.1f 个／分）" % sig["数字"],
    "K3 IFA 品牌刊": "平台、招募、团队（品牌词 %.1f／分），要和小红书图文卡一个样" % sig["品牌"],
}
print("信号（每分钟）：" + "　".join("%s %.1f" % (k, v) for k, v in sig.items()))
print("\n风格包推荐（高→低）：")
for k, v in sorted(score.items(), key=lambda x: -x[1]):
    print("  %-10s %5.1f　%s" % (k, v, why[k]))

# 封面形式：开头 15 秒里有没有一个能当钩子的数字／一组对比／一句判断
head = "".join(s["text"] for s in tc["sentences"] if s["chars"][0]["s"] < 15)
forms = []
if NUM.search(head):
    forms.append("number（开头有数字：%s）" % NUM.search(head).group(0))
if re.search(r"超过|对比|比起|相比|vs|打平|差在", full):
    forms.append("versus（有两边对比的说法）")
if re.search(r"一个字|一句话|我觉得|说白了|其实", head):
    forms.append("quote／title（开头是一句判断或设问）")
forms.append("title（任何内容都可用）")
print("\n封面形式候选（cover.form 写 auto 时按账号登记错开）：\n  " + "\n  ".join(forms))

# 信息卡候选：一句里两个以上数字→compare/chart；第一第二第三→list；年月时间点→timeline；报告/指引原文→quote
print("\n信息卡候选：")
for s in tc["sentences"]:
    t = s["text"]
    n = len(NUM.findall(t))
    kind = None
    if n >= 2:
        kind = "compare 或 chart（%d 个数字）" % n
    elif re.match(r"^(第[一二三四五]|首先|其次|最后)", t):
        kind = "list（第几件事）"
    elif re.search(r"\d{4} ?年|\d+ ?月|去年|今年|明年", t) and re.search(r"开始|生效|之后|以后|到了", t):
        kind = "timeline（时间点）"
    elif re.search(r"报告|指引|规定|条例|官方|原话|说过", t):
        kind = "quote（原文／出处）"
    if kind:
        print("  %s %5.1fs  %-22s %s" % (s["id"], s["chars"][0]["s"], kind, t[:30]))

if acct and os.path.exists(reg_p):
    prev = [e for e in load(reg_p).get("entries", []) if e.get("account") == acct]
    if prev:
        e = prev[-1]
        print("\n账号「%s」上一支：%s／主题 %s／封面 %s／卡 %s——这一支主题沿用，封面形式和卡型尽量换" % (
            acct, e.get("style"), e.get("theme"), e.get("cover_form"), "、".join(e.get("cards", [])) or "无"))
