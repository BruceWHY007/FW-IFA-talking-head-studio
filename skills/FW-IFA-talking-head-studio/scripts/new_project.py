#!/usr/bin/env python3
"""新建一支口播成片工程。

    python3 new_project.py <原始口播.mp4> <工程目录> [--title 系列名 --subtitle 本期标题]

做的事：建目录 → 原片软链进 source/ → 复制 Remotion 模板 → node_modules 软链到 skill 的共享运行时 →
写 brief.md / facts.json 空表。工程目录不要放桌面根目录。
"""
import argparse, os, shutil, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from kb import SKILL, P, PY, save, load, die, probe, link_file, link_dir

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
if not os.path.lexists(link):
    how = link_file(raw, link)   # 软链；Windows 没开开发者模式时退到硬链或复制
    if how == "复制":
        print("· 原片已复制进工程 source/（这台机器建不了链接）")

tpl = os.path.join(SKILL, "template", "remotion")
dst = P(proj, "remotion")
if not os.path.exists(dst):
    shutil.copytree(tpl, dst, ignore=shutil.ignore_patterns("node_modules", "out"))
nm = os.path.join(SKILL, "runtime", "node_modules")
if not os.path.exists(nm):
    die("共享运行时还没装：先跑 %s %s（只装一次）" % (os.path.basename(PY), os.path.join(SKILL, "scripts", "setup.py")))
if not os.path.lexists(P(dst, "node_modules")):
    if not link_dir(nm, P(dst, "node_modules")):
        die("建不了 remotion/node_modules 的链接（%s → %s）：Windows 请确认工程和技能在同一类磁盘（NTFS），或打开「开发者模式」" % (P(dst, "node_modules"), nm))

info = probe(raw)
brief = P(proj, "brief.md")
if not os.path.exists(brief):
    shutil.copy(os.path.join(SKILL, "template", "brief.md"), brief)
    with open(brief, "a", encoding="utf-8") as f:
        f.write("\n\n<!-- 原片探测：%s -->\n" % info)
import uuid
pid = load(P(proj, "project.json"), {}).get("pid") or uuid.uuid4().hex[:10]   # 工程指纹：脚本生成的文件都带上它，从别的工程拷来的文件 build 会认出来
if not os.path.exists(P(proj, "facts.json")):
    save(P(proj, "facts.json"), {"_说明": "屏上每个字、每个数都要在这里有出处。source 写原句或链接。", "_pid": pid,
                                 "claims": []})
if not os.path.exists(P(proj, "project.json")):
    save(P(proj, "project.json"), {"title": a.title, "subtitle": a.subtitle, "raw": raw, "probe": info, "pid": pid})
if not os.path.exists(P(proj, "ledger.md")):
    with open(P(proj, "ledger.md"), "w", encoding="utf-8") as f:
        f.write("# ledger\n\n每一轮：改了什么 → 改前数字 → 改后数字 → 谁评的。\n\n")
print("✓ 工程已建：%s\n  原片 %s  %.1fs  %s" % (proj, os.path.basename(raw), info["duration"], info["video"]))
print("  下一步：%s %s %s" % (os.path.basename(PY), os.path.join(SKILL, "scripts", "next.py"), proj))
