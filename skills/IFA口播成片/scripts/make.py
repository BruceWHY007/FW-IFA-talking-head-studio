#!/usr/bin/env python3
"""判定写完之后的一条龙：build → mix → render → qa。改了 decompose / edits / 配乐后重跑它就行。

    python3 make.py <工程目录> [--bgm 配乐 --bgm-in 秒 --bgm-db -12] [--test] [--skip-render]
                    [--decompose 另一份镜头计划 --style K2 --theme 维港青 --out 样片_K2.mp4]

成片渲完会写进账号登记（工程上一级的 _口播形式登记.json）：下一支同账号的片子据此错开封面形式、沿用主题。

--test 只渲 0–5 秒试片（正式开工前必做一次）。改了 edits.json 要先单独跑 trim.py。
"""
import argparse, os, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("proj")
ap.add_argument("--bgm", default="")
ap.add_argument("--bgm-in", default="0")
ap.add_argument("--bgm-db", default="-12")
ap.add_argument("--test", action="store_true")
ap.add_argument("--skip-render", action="store_true")
ap.add_argument("--decompose", default="")
ap.add_argument("--style", default="")
ap.add_argument("--theme", default="")
ap.add_argument("--out", default="", help="成片文件名（默认 成片_9x16.mp4）")
ap.add_argument("--no-register", action="store_true", help="样片、试片不写账号登记")
a = ap.parse_args()

def step(*args):
    print("\n▶ " + " ".join(os.path.basename(x) if i == 0 else x for i, x in enumerate(args)))
    r = subprocess.run([sys.executable, os.path.join(HERE, args[0])] + list(args[1:]))
    if r.returncode != 0:
        sys.exit(r.returncode)

bargs = ["build.py", a.proj] + (["--decompose", a.decompose] if a.decompose else []) + (["--style", a.style] if a.style else []) + \
    (["--theme", a.theme] if a.theme else [])
step(*bargs)
mix = ["mix.py", a.proj]
if a.bgm:
    mix += ["--bgm", a.bgm, "--bgm-in", a.bgm_in, "--bgm-db", a.bgm_db]
step(*mix)
if a.skip_render:
    sys.exit(0)
step("render.py", a.proj, *(["--test"] if a.test else []), *(["--out", a.out] if a.out else []))
if not a.test:
    step("qa.py", a.proj, *(["--video", os.path.join(os.path.abspath(a.proj), "out", a.out)] if a.out else []))
    # 账号登记：记下这一支用了什么（风格、主题、封面形式、卡型），下一支据此错开
    import json, time
    proj = os.path.abspath(a.proj)
    tl = json.load(open(os.path.join(proj, "remotion", "src", "timeline.json")))
    if tl.get("account") and not a.no_register:
        regp = os.path.join(os.path.dirname(proj), "_口播形式登记.json")
        reg = json.load(open(regp)) if os.path.exists(regp) else {"_说明": "口播成片的账号登记：每支一行。build.py 读它沿用账号主题、错开封面形式。", "entries": []}
        reg["entries"] = [e for e in reg["entries"] if not (e.get("project") == os.path.basename(proj) and e.get("out") == (a.out or "成片_9x16.mp4"))]
        reg["entries"].append({"time": time.strftime("%Y-%m-%d %H:%M"), "account": tl["account"], "project": os.path.basename(proj), "out": a.out or "成片_9x16.mp4",
                               "style": tl["style"], "theme": (tl.get("theme") or {}).get("name", ""), "cover_form": (tl.get("cover") or {}).get("form", "title"),
                               "cards": sorted(set((x.get("info") or {}).get("kind", "") for x in tl["shots"] if x["type"] == "I"))})
        json.dump(reg, open(regp, "w"), ensure_ascii=False, indent=1)
        print("✓ 账号登记 → " + regp)
    print("\n下一步：派一个没看过制作过程的评审子代理（references/06 §二 的提示词），按它的 P0/P1 修，记 ledger.md")
