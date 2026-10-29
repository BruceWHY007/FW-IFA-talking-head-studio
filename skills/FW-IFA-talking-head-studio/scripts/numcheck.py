#!/usr/bin/env python3
"""①-b 数字核对原声：把每句带数字的话从原声里再听一遍，和 transcript.json 的 text 对比，对不上的标出来让人听。

    python3 numcheck.py <工程目录> [--model ~/.cache/whisper-cpp/ggml-small.bin]

为什么要有这一步（2026-10-29 栽过）：whisper 默认会把口语数字「规范化」——
  「千分之一到千分之一点五」被写成「1-1.5%」，屏上就成了 1%–1.5%（错了 10 倍）；
  同一段换个提示又听成「千分之五」（把「一点五」吞成「五」）。数字一错就是事实错误，比错字严重得多。
做法：逐句截原声（前后各留 0.3s），用「数字按原话写汉字」的提示重新转写，把两边都换成 (数值, 百分号/千分号/万分号) 比：
  ① 单位类：text 写 % 而原声是「千分之／万分之」（或反过来）＝高危，必须改
  ② 数值类：两边数值集合不一样＝要人听（重听也可能听错，比如吞掉「点」）
人听过确认无误：在 transcript.json 那一句加 "num_verified": true（可写 "num_note" 记听到的原话），重跑本脚本即消。
产物：work/numcheck.json（build.py 会读它报警，qa.py 会把未解决的条目算不过线）
"""
import argparse, json, os, re, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, load, die, has

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", os.path.expanduser("~/.cache/whisper-cpp/ggml-small.bin")))
a = ap.parse_args()
proj = os.path.abspath(a.proj)
tr = load(P(proj, "transcript.json"))
wav = P(proj, "work", "voice.wav")
if not os.path.exists(wav):
    die("没有 work/voice.wav（先跑 ingest.py）")
if not has("whisper-cli") or not os.path.exists(a.model):
    die("没有 whisper-cli 或模型 %s：数字核对做不了，屏上所有数字请人逐条听原声" % a.model)

PROMPT = "以下是普通话口播，数字一律按原话写汉字：千分之一、千分之一点五、万分之五、百分之十、一点五倍、三千万、十二月一日。"
D = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
U = {"十": 10, "百": 100, "千": 1000}
CN = "零〇一二两三四五六七八九十百千万亿"


def cn2num(s):
    s = s.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", s):
        return float(s)
    if "点" in s or "." in s:
        x, y = re.split(r"[点.]", s, 1)
        frac = "".join(str(D[c]) if c in D else c for c in y if c in D or c.isdigit())
        return cn2num(x or "零") + (float("0." + frac) if frac else 0)
    total, sec, num = 0, 0, 0
    for c in s:
        if c.isdigit():
            num = num * 10 + int(c)
        elif c in D:
            num = D[c]
        elif c in U:
            sec += (num or 1) * U[c]
            num = 0
        elif c == "万":
            total += (sec + num) * 10000
            sec, num = 0, 0
        elif c == "亿":
            total = (total + sec + num) * 100000000
            sec, num = 0, 0
    return float(total + sec + num)


UNIT_AFTER = "年月日号个倍万亿天岁人家位成条类点%‰‱"
TOK = re.compile(r"(百分之|千分之|万分之)?([%s\d]+(?:[点.][%s\d]+)?)\s*(%%|‰|‱)?" % (CN, CN))


def tokens(s):
    s = s.replace("～", "-").replace("~", "-").replace("—", "-").replace("–", "-")
    raw = []
    for m in TOK.finditer(s):
        pre, num, suf = m.group(1), m.group(2), m.group(3)
        has_digit = bool(re.search(r"\d", num))
        nxt = s[m.end():m.end() + 1]
        prv = s[max(m.start() - 1, 0):m.start()]
        is_range_head = nxt in ("-", "到", "至")
        listed = nxt == "、" or prv == "、"   # 只认顿号并列；逗号后面的「一份文件」不是数字
        # 纯汉字数字只在「后面跟单位／前面有百分之千分之／区间一端／并列项」时算数，免得把「一份文件」的「一」也当数字
        if not has_digit and not pre and not suf and nxt not in UNIT_AFTER and not is_range_head and not listed:
            continue
        unit = {"百分之": "%", "千分之": "‰", "万分之": "‱"}.get(pre) or suf or ""
        raw.append([cn2num(num), unit, m.start(), m.end(), is_range_head, prv])
    # 区间：1-1.5% ／ 一到三年 —— 前一端没有单位、后一端有，前一端沿用后一端的百分号类单位
    for i in range(len(raw) - 1):
        if raw[i][4] and not raw[i][1] and raw[i + 1][1]:
            raw[i][1] = raw[i + 1][1]
    # 并列：百分之十、二十、三十 —— 顿号后面的项沿用前一项的百分号类单位
    for i in range(1, len(raw)):
        if not raw[i][1] and raw[i][5] in "、，," and raw[i - 1][1] in ("%", "‰", "‱") and raw[i][2] - raw[i - 1][3] <= 1:
            raw[i][1] = raw[i - 1][1]
    return [(round(v, 4), u) for v, u, _, _, _, _ in raw]


def asr(path):
    r = subprocess.run(["whisper-cli", "-m", a.model, "-l", "zh", "-f", path, "-np", "-nt", "--prompt", PROMPT],
                       capture_output=True, text=True)
    return re.sub(r"\s+", "", r.stdout)


rows, flagged = [], 0
with tempfile.TemporaryDirectory() as td:
    for s in tr["sentences"]:
        text = s.get("text", "")
        if s.get("drop") or not re.search(r"[\d%‰]|百分之|千分之|万分之", text):
            continue
        seg = os.path.join(td, "%s.wav" % s["id"])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % max(0, s["start"] - 0.3), "-t", "%.2f" % (s["end"] - s["start"] + 0.6),
                        "-i", wav, "-ar", "16000", "-ac", "1", seg], check=True)
        heard = asr(seg)
        tt, th = tokens(text), tokens(heard)
        pct_t = {u for _, u in tt if u}
        pct_h = {u for _, u in th if u}
        flag = ""
        warn = ""
        if tt and not th:
            warn = "重听没听到数字（截段吞字或口音），不判；屏上用到这句的数字请人听一遍"
        elif pct_t != pct_h and (pct_t | pct_h) & {"%", "‰", "‱"}:
            flag = "单位：转写写 %s，原声听着是 %s（百分之／千分之／万分之）" % ("、".join(sorted(pct_t)) or "无", "、".join(sorted(pct_h)) or "无")
        elif sorted(v for v, _ in tt) != sorted(v for v, _ in th):
            flag = "数值：转写 %s，重听 %s" % ([v for v, _ in tt], [v for v, _ in th])
        if s.get("num_verified"):
            flag = ""
        flagged += bool(flag)
        rows.append({"id": s["id"], "text": text, "heard": heard, "text_nums": tt, "heard_nums": th, "flag": flag, "warn": warn,
                     "verified": bool(s.get("num_verified")), "note": s.get("num_note", "")})
        print("%s %-4s %s\n      重听：%s%s" % ("❌" if flag else ("✅" if s.get("num_verified") else "⚠️" if warn else "·"), s["id"], text, heard,
                                               ("\n      → " + (flag or warn)) if (flag or warn) else ""))

json.dump({"_说明": "numcheck.py 产物：flag 非空＝转写里的数字和原声对不上，要人听；听过无误在 transcript.json 那句加 num_verified: true。",
           "model": os.path.basename(a.model), "rows": rows, "unresolved": flagged},
          open(P(proj, "work", "numcheck.json"), "w"), ensure_ascii=False, indent=1)
print("\n带数字的句子 %d 句，对不上 %d 句 → work/numcheck.json" % (len(rows), flagged))
if flagged:
    print("处理：听原声 → 改 transcript.json 的 text（例「1-1.5%」→「千分之一到千分之一点五」）→ 加 \"num_verified\": true → 重跑本脚本、再跑 trim.py")
