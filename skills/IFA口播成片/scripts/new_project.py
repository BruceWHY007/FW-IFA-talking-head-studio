#!/usr/bin/env python3
"""新建一支口播成片工程。

    python3 new_project.py <原始口播.mp4> <工程目录> [--title 系列名 --subtitle 本期标题]

做的事：建目录 → 原片软链进 source/ → 复制 Remotion 模板 → node_modules 软链到 skill 的共享运行时 →
写 brief.md / facts.json 空表。工程目录不要放桌面根目录。
"""
import argparse, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import SKILL, P, save, die, probe

ap = argparse.ArgumentParser()
ap.add_argument("raw")
ap.add_argument("proj")
ap.add_argument("--title", default="")
ap.add_argument("--subtitle", default="")
a = ap.parse_args()

raw = os.path.abspath(a.raw)
if not os.path.exists(raw):
    die("原片不存在：" + raw)
proj = os.path.abspath(a.proj)
if os.path.realpath(os.path.dirname(proj)) == os.path.realpath(os.path.expanduser("~/Desktop")):
    die("工程不要直接建在桌面根目录，放进对应项目的子目录")
for d in ["source", "work", "broll/lib", "broll/stock", "broll/gen", "audio", "out", "qa", "assets"]:
    os.makedirs(P(proj, d), exist_ok=True)

ext = os.path.splitext(raw)[1].lower()
link = P(proj, "source", "raw" + ext)
if not os.path.exists(link):
    os.symlink(raw, link)

tpl = os.path.join(SKILL, "template", "remotion")
dst = P(proj, "remotion")
if not os.path.exists(dst):
    shutil.copytree(tpl, dst, ignore=shutil.ignore_patterns("node_modules", "out"))
nm = os.path.join(SKILL, "runtime", "node_modules")
if not os.path.exists(nm):
    print("⚠ 共享运行时还没装：cd %s/runtime && npm install（只装一次）" % SKILL)
if not os.path.lexists(P(dst, "node_modules")):
    os.symlink(nm, P(dst, "node_modules"))

info = probe(raw)
brief = P(proj, "brief.md")
if not os.path.exists(brief):
    shutil.copy(os.path.join(SKILL, "template", "brief.md"), brief)
    with open(brief, "a", encoding="utf-8") as f:
        f.write("\n\n<!-- 原片探测：%s -->\n" % info)
if not os.path.exists(P(proj, "facts.json")):
    save(P(proj, "facts.json"), {"_说明": "屏上每个字、每个数都要在这里有出处。source 写原句或链接。",
                                 "claims": []})
if not os.path.exists(P(proj, "project.json")):
    save(P(proj, "project.json"), {"title": a.title, "subtitle": a.subtitle, "raw": raw, "probe": info})
if not os.path.exists(P(proj, "ledger.md")):
    with open(P(proj, "ledger.md"), "w", encoding="utf-8") as f:
        f.write("# ledger\n\n每一轮：改了什么 → 改前数字 → 改后数字 → 谁评的。\n\n")
print("✓ 工程已建：%s\n  原片 %s  %.1fs  %s" % (proj, os.path.basename(raw), info["duration"], info["video"]))
print("  下一步：python3 %s/scripts/ingest.py %s" % (SKILL, proj))
