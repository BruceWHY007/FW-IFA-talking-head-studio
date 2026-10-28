#!/usr/bin/env python3
"""④-c AI 生成补 B-roll。渠道不写死：读 gen_providers.json，默认不调用任何接口，只出提示词卡。

    python3 gen_video.py <工程目录> plan                       出 broll/gen/cards.md（每条：镜号、时长、要交代的信息、提示词）
    python3 gen_video.py <工程目录> run --yes [--only B07,B09]   按配置里 active 的渠道真调用，下载到 broll/gen/<镜号>.mp4
    python3 gen_video.py <工程目录> providers                  列出配置里的渠道、是否启用、密钥是否就位（只报有没有，不显示值）

配置查找顺序：<工程>/gen_providers.json → ~/.config/ifa-koubo/gen_providers.json → skill 自带模板（全部关闭）。
真调用要同时满足：active 指向一个 enabled 的渠道 ＋ 该渠道 key_env 的环境变量已设 ＋ 命令带 --yes。
跑之前先把 plan 的条数、总秒数报给用户、按该平台价格估费用，用户点头才加 --yes。
不需要生成的工程，这一步整个跳过。
"""
import argparse, base64, copy, hashlib, hmac, json, os, re, sys, time, urllib.request, urllib.error
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import P, SKILL, load, save, die

ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("cmd", choices=["plan", "run", "providers"])
ap.add_argument("--yes", action="store_true")
ap.add_argument("--only", default="")
ap.add_argument("--backup", action="store_true", help="plan 时把已有素材、但写了 gen_prompt 的镜头也出卡（备选）")
a = ap.parse_args()
proj = os.path.abspath(a.proj)

cfg_path = next(p for p in [P(proj, "gen_providers.json"),
                            os.path.expanduser("~/.config/ifa-koubo/gen_providers.json"),
                            os.path.join(SKILL, "template", "gen_providers.json")] if os.path.exists(p))
cfg = load(cfg_path)
provs = cfg.get("providers", {})

if a.cmd == "providers":
    print("配置：%s\nactive：%s" % (cfg_path, cfg.get("active")))
    for name, p in provs.items():
        ready = bool(os.environ.get(p.get("key_env", ""), ""))
        print("  %-11s %s  密钥%s  %s" % (name, "启用" if p.get("enabled") else "关闭", "已设" if ready else "未设",
                                          p.get("verified", "")[:40]))
    sys.exit(0)

# 统一尾巴：竖版、写实、无字、无 logo、生成的人只当背影/侧影/手（出镜人只能用实拍）
TAIL = ("竖屏 9:16 构图，主体在画面中央 60% 范围内。写实摄影质感，自然光，镜头缓慢推近或平移。"
        "画面里不要出现任何文字、字幕、水印、logo、可读的招牌字。人物只出现背影、侧影或手部，不要正脸特写。")

dec = load(P(proj, "decompose.json"))
shots = [s for s in dec.get("shots", []) if s.get("source") == "gen" or (a.backup and s.get("gen_prompt"))]
if a.only:
    shots = [s for s in shots if s["id"] in set(a.only.split(","))]
G = P(proj, "broll", "gen")
os.makedirs(G, exist_ok=True)
if not shots:
    print("· decompose.json 里没有 source=gen 的镜头，跳过")
    sys.exit(0)

active = cfg.get("active")
prov = provs.get(active) if active else None
lo, hi = (prov or {}).get("duration_range", [4, 10])
rows, total = [], 0
for s in shots:
    d = int(min(max(round(s.get("gen_dur", 5)), lo), hi))
    s["_d"] = d
    total += d
    s["_prompt"] = (s.get("gen_prompt") or s.get("need", "")).strip() + " " + TAIL
    if not s.get("gen_prompt") and not s.get("need"):
        die("%s 没写 gen_prompt / need" % s["id"])
    rows.append("| %s | %ds | %s | %s |" % (s["id"], d, s.get("need", ""), s["_prompt"].replace("|", "／")))
md = ["# 生成镜头卡", "", "渠道：%s（配置 %s）" % (active or "未接入：拿提示词去任意平台网页生成，文件命名为 <镜号>.mp4 放进 broll/gen/", cfg_path), "",
      "| 镜号 | 时长 | 这一镜要交代的信息 | 提示词 |", "|---|---|---|---|"] + rows + \
     ["", "合计 %d 条 / %d 秒。费用按所选平台当日价格估算，调用前报给用户。" % (len(shots), total)]
open(os.path.join(G, "cards.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("✓ 提示词卡 broll/gen/cards.md：%d 条 / %d 秒" % (len(shots), total))
if a.cmd == "plan":
    sys.exit(0)

if not prov:
    print("· 没有接入任何生成渠道（active 为空）→ 只出卡")
    sys.exit(0)
if not prov.get("enabled"):
    die("渠道 %s 没有启用（enabled: false）" % active)
key = os.environ.get(prov.get("key_env", ""), "")
if not key:
    die("环境变量 %s 没设，渠道 %s 调不了" % (prov.get("key_env"), active))
if not a.yes:
    print("· 没带 --yes → 只出卡。先把条数、总秒数、预估费用报给用户，确认后再加 --yes")
    sys.exit(0)


def kling_jwt():
    sk = os.environ.get(prov.get("secret_env", ""), "")
    if not sk:
        die("可灵还要 %s" % prov.get("secret_env"))
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=")
    now = int(time.time())
    h = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    p = b64(json.dumps({"iss": key, "exp": now + 1800, "nbf": now - 5}).encode())
    sig = b64(hmac.new(sk.encode(), h + b"." + p, hashlib.sha256).digest())
    return (h + b"." + p + b"." + sig).decode()


def fill(obj, vars_):
    if isinstance(obj, dict):
        return {k: fill(v, vars_) for k, v in obj.items()}
    if isinstance(obj, list):
        return [fill(v, vars_) for v in obj]
    if isinstance(obj, str):
        m = re.fullmatch(r"\{(\w+)\}", obj)
        if m and m.group(1) in vars_:
            return vars_[m.group(1)]
        return re.sub(r"\{(\w+)\}", lambda m_: str(vars_.get(m_.group(1), m_.group(0))), obj)
    return obj


def pick(d, path):
    if not path:
        return None
    for part in path.split("."):
        if isinstance(d, list):
            try:
                d = d[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(d, dict):
            d = d.get(part)
        else:
            return None
    return d


def http(step, vars_):
    st = fill(step, vars_)
    body = st.get("body")
    req = urllib.request.Request(st["url"], method=st.get("method", "POST"),
                                 data=json.dumps(body, ensure_ascii=False).encode() if body is not None else None,
                                 headers=st.get("headers", {}))
    last = None
    for k in range(4):  # 网络抖动（SSL EOF、连接中断）重试；HTTP 错误码不重试
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode() or "{}")
        except urllib.error.HTTPError as e:
            return {"_http_error": e.code, "_detail": e.read().decode()[:600]}
        except Exception as e:
            last = e
            time.sleep(3 * (k + 1))
    return {"_http_error": -1, "_detail": str(last)[:300]}


ledger_p = os.path.join(G, "ledger.json")
ledger = load(ledger_p, {"runs": []})
jobs = []
for s in shots:
    vars_ = {"key": key, "model": prov.get("model", ""), "prompt": s["_prompt"], "duration": s["_d"],
             "duration_str": str(s["_d"]), "ratio": "9:16", "workflow_id": prov.get("workflow_id", ""),
             "webapp_id": prov.get("webapp_id", "")}
    if prov.get("auth") == "kling_jwt":
        vars_["jwt"] = kling_jwt()
    res = http(prov["submit"], vars_)
    for k, path in (prov.get("capture") or {}).items():
        vars_[k] = pick(res, path)
    direct = pick(res, prov["submit"].get("video_url", ""))
    if not vars_.get("task_id") and not direct:
        print("✗ %s 建任务失败：%s" % (s["id"], json.dumps(res, ensure_ascii=False)[:400]))
        continue
    ledger["runs"].append({"shot": s["id"], "provider": active, "model": prov.get("model"), "task": vars_.get("task_id"),
                           "created": time.strftime("%F %T"), "prompt": s["_prompt"], "duration": s["_d"]})
    save(ledger_p, ledger)
    jobs.append({"shot": s["id"], "vars": vars_, "url": direct})
    print("· %s → %s" % (s["id"], vars_.get("task_id") or "同步返回"))


def finish(job, url, status):
    out = os.path.join(G, job["shot"] + ".mp4")
    # 大文件不走本地代理（代理会掐长连接）
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(url, timeout=600) as r, open(out, "wb") as fo:
        fo.write(r.read())
    for row in ledger["runs"]:
        if row["shot"] == job["shot"] and row.get("task") == job["vars"].get("task_id"):
            row.update({"status": status, "file": out})
    save(ledger_p, ledger)
    print("✓ %s → %s" % (job["shot"], out))


deadline = time.time() + 40 * 60
pending = []
for j in jobs:
    if j["url"]:
        finish(j, j["url"], "sync")
    else:
        pending.append(j)
poll = prov.get("poll", {})
while pending and time.time() < deadline:
    time.sleep(15)
    for j in list(pending):
        if prov.get("auth") == "kling_jwt":
            j["vars"]["jwt"] = kling_jwt()
        res = http(poll, j["vars"])
        for k, path in (poll.get("capture") or {}).items():
            v = pick(res, path)
            if v:
                j["vars"][k] = v
        st = pick(res, poll.get("status", ""))
        if st in poll.get("ok", []):
            url = pick(res, poll.get("video_url", ""))
            if not url and prov.get("result"):
                url = pick(http(prov["result"], j["vars"]), prov["result"].get("video_url", ""))
            if url:
                finish(j, url, st)
            else:
                print("✗ %s 成功但取不到视频地址，查 ledger 与渠道配置的 video_url 路径" % j["shot"])
            pending.remove(j)
        elif st in poll.get("fail", []):
            print("✗ %s %s：%s" % (j["shot"], st, json.dumps(res, ensure_ascii=False)[:300]))
            pending.remove(j)
if pending:
    print("⚠ 40 分钟没跑完：%s（任务号在 broll/gen/ledger.json，别重复提交）" % [j["shot"] for j in pending])
