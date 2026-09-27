#!/usr/bin/env python3
"""桥接器：把「GitHub 采集雷达」的日更报告接到转换引擎流水线上。

问题背景
    雷达（另一套流程）每天产出一份 markdown 报告，列出新上榜的高增速仓库；
    转换引擎只会处理 **Agent Skills 格式**（含 SKILL.md）的源。
    两者之间没有桥：报告里的 `owner/repo` 不能直接喂给 port_skill.py，
    而且榜上绝大多数仓库根本不是 Agent Skills —— 直接批量喂会大面积失败。

本脚本做的事
    1. 解析报告（markdown 表格 / 竖线表 / 被压平的一行一格的粘贴格式都能吃），
       提取去重后的 `owner/repo` 列表，并尽力从报告里带出 star 与许可证；
    2. 用 GitHub API 取每个仓库的文件树，判定它属于哪一类：
         A 可直接搬   —— 树中存在 SKILL.md（可能多个，每个父目录是一个独立可搬源）
         B 需创作技能 —— 无 SKILL.md，但具备方法论载体（AGENTS.md / CLAUDE.md /
                          .claude-plugin / skills 目录），适合交给技能生成器从零创作
         C 不可搬     —— 普通工程仓库、教程、模型权重等，转换引擎不适用
    3. 产出两件东西：
         manifest.txt      仅 A 类，每行一个源规格，可直接
                           `port_skill.py --batch manifest.txt`
         bridge-report.md  三分类明细 + 许可风险标注 + 下一步命令

许可风险
    AGPL-3.0 / GPL-3.0 / LGPL-3.0 / 无 LICENSE 视为商用风险，在报告中单列。
    默认仍写入 manifest（搬运 ≠ 商用），需要剔除时加 `--exclude-risk`。

用法
    python bridge_trending.py <报告.md | 源列表.txt> --out <输出根>
                              [--limit N] [--exclude-risk] [--probe-license]
                              [--sleep 0.3]

依赖：仅 Python 标准库。
"""

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

UA = {"User-Agent": "workbuddy-skill-bridge",
      "Accept": "application/vnd.github+json"}

REPO_RE = re.compile(r"^[A-Za-z0-9][\w.-]*/[A-Za-z0-9][\w.-]*$")
FILE_TAIL_RE = re.compile(r"\.(json|ya?ml|toml|md|txt|py|sh|js|ts|csv|log|ini|cfg|lock)$", re.I)
NUM_RE = re.compile(r"^\d+(\.\d+)?k?$", re.I)

# 首段是这些词的基本是仓库内的路径，不是 owner/repo
DIR_WORDS = {"data", "docs", "doc", "src", "lib", "test", "tests", "assets",
             "build", "dist", "out", "node_modules", "scripts", "config",
             "themes", "plugins", "examples", "template", "templates"}
# 文档里的占位写法，不是真仓库
PLACEHOLDERS = {"owner/repo", "user/repo", "owner/name", "foo/bar", "your/repo",
                "org/repo", "someone/repo", "username/repo", "<owner>/<repo>",
                "a/b", "x/y"}

KNOWN_LICENSES = {
    "MIT", "APACHE-2.0", "APACHE 2.0", "APACHE-2", "AGPL-3.0", "GPL-3.0",
    "GPL-2.0", "LGPL-3.0", "BSD-3-CLAUSE", "BSD-2-CLAUSE", "ISC", "MPL-2.0",
    "UNLICENSED", "NOASSERTION", "无 LICENSE", "无LICENSE", "未声明",
}
RISK_LICENSES = {"AGPL-3.0", "GPL-3.0", "GPL-2.0", "LGPL-3.0",
                 "UNLICENSED", "无 LICENSE", "无LICENSE", "未声明", ""}

METHOD_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules")


def tokenize(text):
    """把报告压成扁平 token 流：按换行与竖线切分，去掉空串。

    这样 markdown 表格（一行多格）与被压平的粘贴格式（一行一格）都能走同一条路径。
    """
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        for cell in line.split("|"):
            c = cell.strip().strip("`*").strip()
            if c:
                out.append(c)
    return out


def looks_like_repo(tok):
    if tok.lower() in PLACEHOLDERS or not REPO_RE.match(tok):
        return False
    head, tail = tok.split("/", 1)
    if head.lower() in DIR_WORDS:
        return False
    if FILE_TAIL_RE.search(tail):
        return False
    if tok.count("/") != 1:
        return False
    return True


def parse_report(text):
    """从报告文本提取 [{repo, stars, license}]，保持出现顺序，去重。"""
    toks = tokenize(text)
    found, seen = [], set()
    for i, t in enumerate(toks):
        if not looks_like_repo(t) or t in seen:
            continue
        seen.add(t)
        stars, lic = None, None
        for j in range(i + 1, min(i + 7, len(toks))):
            nxt = toks[j]
            if stars is None and NUM_RE.match(nxt):
                stars = nxt
                continue
            if lic is None and nxt.upper() in KNOWN_LICENSES:
                lic = nxt
                continue
            if nxt.upper() in KNOWN_LICENSES:
                break
        found.append({"repo": t, "stars": stars, "license": lic})
    return found


def gh_get(url, retries=3, timeout=40):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            last = e
        except Exception as e:
            last = e
        if i < retries - 1:
            time.sleep(1.5 * (i + 1))
    raise last


def probe_repo(repo, sleep=0.3):
    """取仓库文件树并分类。返回 dict。"""
    info = {"repo": repo, "branch": None, "files": 0, "skill_dirs": [],
            "method_files": [], "api_license": None, "probe_ok": False,
            "error": ""}
    owner, name = repo.split("/", 1)
    tree = None
    for branch in ("main", "master"):
        try:
            tree = gh_get("https://api.github.com/repos/%s/git/trees/%s?recursive=1"
                          % (repo, branch))
            info["branch"] = branch
            break
        except Exception:
            time.sleep(sleep)
    if tree is None:
        try:
            meta = gh_get("https://api.github.com/repos/%s" % repo)
            branch = meta.get("default_branch") or "main"
            info["branch"] = branch
            info["api_license"] = (meta.get("license") or {}).get("spdx_id")
            tree = gh_get("https://api.github.com/repos/%s/git/trees/%s?recursive=1"
                          % (repo, branch))
        except Exception as e:
            info["error"] = "%s" % e
            return info
    if tree.get("truncated"):
        info["error"] = "仓库过大，git trees 被截断，需人工指定子路径"
        return info
    blobs = [t["path"] for t in tree.get("tree", []) if t.get("type") == "blob"]
    info["files"] = len(blobs)
    info["probe_ok"] = True
    info["_paths"] = blobs
    for p in blobs:
        segs = p.split("/")
        if segs[-1] == "SKILL.md":
            d = "/".join(segs[:-1])
            if d and d not in info["skill_dirs"]:
                info["skill_dirs"].append(d)
        elif segs[-1] in METHOD_FILES or (len(segs) == 2 and segs[0] == ".claude-plugin"):
            info["method_files"].append(p)
    return info


def classify(info):
    if not info["probe_ok"]:
        return "?", "探测失败：%s" % (info["error"] or "未知原因")
    if info["skill_dirs"]:
        return "A", "含 %d 个 SKILL.md" % len(info["skill_dirs"])
    if info["method_files"]:
        return "B", "无 SKILL.md，但具备方法论载体（%s）" % "、".join(info["method_files"][:3])
    return "C", "普通工程仓库，无 Agent Skills 结构"


def risk_of(repo_info, probe):
    lic = repo_info.get("license") or probe.get("api_license") or ""
    lic = (lic or "").strip()
    if lic.upper() in {x.upper() for x in RISK_LICENSES}:
        if not lic:
            return lic, "许可未知：爬取时未读到 LICENSE，商用前必须核实"
        if "AGPL" in lic.upper() or "GPL" in lic.upper():
            return lic, "copyleft 传染性条款：私有部署 / SaaS 属明确踩线，可谈商业授权"
        return lic, "默认保留全部权利：商用前必须取得作者书面授权"
    return lic, ""


def build_manifest(rows, exclude_risk):
    lines = []
    for r in rows:
        if r["class"] != "A":
            continue
        if exclude_risk and r["risk_note"]:
            continue
        for d in r["skill_dirs"]:
            lines.append("%s@%s/%s" % (r["repo"], r["branch"], d))
    return lines


def build_report(rows, manifest, out_root, exclude_risk):
    A = [r for r in rows if r["class"] == "A"]
    B = [r for r in rows if r["class"] == "B"]
    C = [r for r in rows if r["class"] == "C"]
    U = [r for r in rows if r["class"] == "?"]
    L = ["# 采集雷达 → 转换引擎 桥接报告", "",
         "- 输入项：%d 个仓库" % len(rows),
         "- 分类结果：**A 可直接搬 %d** ｜ B 需创作技能 %d ｜ C 不可搬 %d ｜ ? 探测失败 %d"
         % (len(A), len(B), len(C), len(U)),
         "- 生成清单：`%d` 条源（%s）" % (
             len(manifest),
             "已剔除许可风险项" if exclude_risk else "含许可风险项，仅作标记"),
         ""]
    if A:
        L += ["## A 类 · 可直接搬（已写入 manifest.txt）", "",
              "| 仓库 | 分支 | SKILL.md 源数 | 许可证 | 风险 |", "|---|---|---|---|---|"]
        for r in A:
            L.append("| `%s` | %s | %d | %s | %s |" % (
                r["repo"], r["branch"], len(r["skill_dirs"]),
                r["license"] or "—", "⚠ %s" % r["risk_note"] if r["risk_note"] else "—"))
        L.append("")
        L += ["**源级明细**（每个 SKILL.md 目录都是一个独立可搬源）：", ""]
        for r in A:
            for d in r["skill_dirs"]:
                L.append("- `%s@%s/%s`" % (r["repo"], r["branch"], d))
        L.append("")
    if B:
        L += ["## B 类 · 需创作技能（转换引擎不适用，交给技能生成器）", "",
              "| 仓库 | 文件数 | 方法论载体 | 许可证 |", "|---|---|---|---|"]
        for r in B:
            L.append("| `%s` | %d | %s | %s |" % (
                r["repo"], r["files"], "、".join(r["method_files"][:3]) or "—",
                r["license"] or "—"))
        L += ["",
              "处置：这类仓库不是 Agent Skills，但它把一套方法固化成了可读流程——",
              "用技能生成器把它的方法抽出来写成 SKILL.md，才是正确的转化方式。", ""]
    if C:
        L += ["## C 类 · 不可搬", "",
              "| 仓库 | 文件数 | 许可证 | 说明 |", "|---|---|---|---|"]
        for r in C:
            L.append("| `%s` | %d | %s | %s |" % (
                r["repo"], r["files"], r["license"] or "—", r["reason"]))
        L.append("")
    if U:
        L += ["## 探测失败（需人工确认）", ""]
        for r in U:
            L.append("- `%s` → %s" % (r["repo"], r["reason"]))
        L.append("")
    risky = [r for r in rows if r["risk_note"]]
    if risky:
        L += ["## 许可风险专区", "",
              "| 仓库 | 许可证 | 风险性质 | 是否已写入清单 |", "|---|---|---|---|"]
        for r in risky:
            inman = "是" if (r["class"] == "A" and not exclude_risk) else "否"
            L.append("| `%s` | %s | %s | %s |" % (
                r["repo"], r["license"] or "未知", r["risk_note"], inman))
        L.append("")
    L += ["## 下一步", "",
          "```bash",
          "# 1. 只跑 A 类，一次批量搬完。必须带 --tree-cache 复用本报告已探到的文件树，",
          "#    否则每个源都会再打一次 GitHub API —— 未认证限流 60 次/小时，会撞墙。",
          "python port_skill.py --batch \"%s\" --tree-cache \"%s\" --out \"%s/port\""
          % ((out_root / "manifest.txt").as_posix(),
             (out_root / "trees.json").as_posix(),
             out_root.as_posix()),
          "",
          "# 2. 看批量结果与每个技能的改动清单",
          "#    <out>/port/batch-report.md 与 <out>/port/<slug>/porting-changes.md",
          "",
          "# 3. B 类（无 SKILL.md 但有方法论载体）交给技能生成器从零创作，不要喂转换引擎",
          "```", ""]
    return "\n".join(L) + "\n"


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="雷达报告 .md，或纯 owner/repo 列表 .txt")
    ap.add_argument("--out", required=True, help="输出根目录")
    ap.add_argument("--limit", type=int, default=0, help="只探测前 N 个仓库（0=全部）")
    ap.add_argument("--exclude-risk", action="store_true",
                    help="把许可风险项（AGPL/GPL/无 LICENSE）排除出 manifest")
    ap.add_argument("--probe-license", action="store_true",
                    help="报告未给出许可证时，额外调用仓库 API 补 license 字段")
    ap.add_argument("--sleep", type=float, default=0.3, help="API 调用间隔秒数")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print("[error] 输入文件不存在：%s" % args.input)
        sys.exit(2)
    text = src.read_text(encoding="utf-8", errors="replace")
    items = parse_report(text)
    if not items:
        print("[error] 未能从输入解析出任何 owner/repo，请检查报告格式")
        sys.exit(2)
    if args.limit:
        items = items[:args.limit]
    print("解析到 %d 个仓库，开始探测…" % len(items))

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    rows = []
    for k, it in enumerate(items, 1):
        p = probe_repo(it["repo"], sleep=args.sleep)
        cls, reason = classify(p)
        lic, risk_note = risk_of(it, p)
        if not args.probe_license:
            lic = it.get("license") or p.get("api_license") or lic
            _, risk_note = risk_of({"license": lic}, {})
        p.update({"class": cls, "reason": reason, "license": lic,
                  "risk_note": risk_note, "stars": it.get("stars")})
        rows.append(p)
        print("  [%2d/%2d] %-45s %s  %s" % (k, len(items), it["repo"], cls, reason[:46]))
        time.sleep(args.sleep)

    manifest = build_manifest(rows, args.exclude_risk)
    mpath = out_root / "manifest.txt"
    head = ["# 由 bridge_trending.py 生成：采集雷达 A 类（含 SKILL.md）源清单",
            "# 用法：python port_skill.py --batch \"%s\" --out <输出根>" % mpath.as_posix(),
            "# 输入：%s" % src.as_posix(), ""]
    mpath.write_text("\n".join(head + manifest) + "\n", encoding="utf-8")

    rpath = out_root / "bridge-report.md"
    rpath.write_text(build_report(rows, manifest, out_root, args.exclude_risk),
                     encoding="utf-8")
    clean = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    (out_root / "bridge-rows.json").write_text(
        json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")

    trees = {}
    for r in rows:
        if r.get("_paths") and r.get("branch"):
            trees["%s@%s" % (r["repo"], r["branch"])] = r["_paths"]
    tpath = out_root / "trees.json"
    tpath.write_text(json.dumps(trees, ensure_ascii=False), encoding="utf-8")

    print("\nmanifest 源数：%d" % len(manifest))
    print("产物：")
    print("  %s" % mpath.as_posix())
    print("  %s" % rpath.as_posix())
    print("  %s" % tpath.as_posix())
    print("  %s" % (out_root / "bridge-rows.json").as_posix())
    if not manifest:
        print("\n[note] 本次没有 A 类源——榜上无 Agent Skills 结构仓库，转换引擎无源可搬。")
        print("       这不是脚本故障，而是信号：该批仓库需要走「技能生成器」从零创作。")
        sys.exit(0)


if __name__ == "__main__":
    main()
