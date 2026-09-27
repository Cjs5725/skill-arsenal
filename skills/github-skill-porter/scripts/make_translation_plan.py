#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_translation_plan.py — 中文化工序 A：自动抽取翻译作业计划。

对指定技能的 SKILL.md（及可选 references/*.md）做结构分析，生成 translation-plan.md：
  [决策]  frontmatter 字段逐项列出（display_name / description_zh 需人工定）
  [翻译]  标题与正文段，附行号区间与中文字符密度（密度高 = 可能已译/模板段）
  [保留]  围栏代码块、行内路径与命令（自动识别，列抽样供核对）
  [核对]  表格（译文需键名原样）
  [重写]  疑似骨架占位段：固定段标题 + 正文过短 / 命中通用套话

用法:
  python make_translation_plan.py <skill_dir> [--out PLAN.md] [--deep]
默认输出 <skill_dir>/../translation-plan__<slug>.md；--deep 额外分析 references/*.md。

设计约束（与 localization-zh.md / glossary.md 配合）：
  - 本脚本只做「分类与定位」，不做任何改写；判断活留给执行者。
  - 骨架段判定是启发式，宁多报不漏报，最终由人确认。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SKELETON_TITLES = ("执行流程", "边界与降级", "质量自检", "搬运说明")
GENERIC_PHRASES = ("依次执行", "按源技能定义", "核心动作", "参见上游")
FENCE_RE = re.compile(r"^(```|~~~)")
INLINE_PATH_RE = re.compile(
    r"`[^`\n]*[\w.-]+/[\w.-]+\.[A-Za-z0-9]{1,5}[^`\n]*`"   # `dir/file.ext`
    r"|`[^`\n]*(?:^|[\s/])(?:[a-z][\w-]*(?:\.py|\.sh|\.ts|\.js|\.md))[^`\n]*`"
)
ZH_RE = re.compile(r"[一-鿿]")
FRONTMATTER_KEYS_DECIDE = ("display_name", "description_zh", "description_en", "display_name_en")


def count_zh(s: str) -> int:
    return len(ZH_RE.findall(s))


def parse_blocks(text: str):
    """把 md 切成带行号的块：(start, end, kind, payload)  1-based，闭区间。"""
    lines = text.splitlines()
    blocks, i, n = [], 0, len(lines)
    in_front = False
    if n and lines[0].strip() == "---":
        in_front = True
        i = 1
        while i < n and lines[i].strip() != "---":
            i += 1
        blocks.append((1, min(i + 1, n), "frontmatter", lines[1:i]))
        i += 1
    while i < n:
        line = lines[i]
        m = FENCE_RE.match(line.strip())
        if m:
            fence = m.group(1)[:3]
            j = i + 1
            while j < n and not lines[j].strip().startswith(fence):
                j += 1
            blocks.append((i + 1, min(j + 1, n), "code", (lines[i + 1:j], line.strip()[3:] or "text")))
            i = j + 1
            continue
        hm = re.match(r"^(#{1,6})\s+(.*)$", line)
        if hm:
            blocks.append((i + 1, i + 1, "heading", (len(hm.group(1)), hm.group(2).strip())))
            i += 1
            continue
        if line.lstrip().startswith("|") and i + 1 < n and set(lines[i + 1].replace(" ", "").replace("|", "")) <= set("-:"):
            j = i + 1
            while j < n and lines[j].lstrip().startswith("|"):
                j += 1
            blocks.append((i + 1, j, "table", lines[i:j]))
            i = j
            continue
        blocks.append((i + 1, i + 1, "text", line))
        i += 1
    return lines, blocks


def heading_spans(blocks):
    """返回 [(level, title, start, end)]，end=下一个同级或更高级标题前一行。"""
    heads = [(t[0], t[1], s) for s, e, k, t in blocks if k == "heading"]
    spans = []
    for idx, (lv, title, start) in enumerate(heads):
        end = blocks[-1][1]
        for lv2, _t2, s2 in heads[idx + 1:]:
            if lv2 <= lv:
                end = s2 - 1
                break
        spans.append((lv, title, start, end))
    return spans


def analyze(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    lines, blocks = parse_blocks(text)
    total_lines = len(lines)
    zh_total = count_zh(text)
    out = [f"# 翻译作业计划 — {path.parent.name}/{path.name}\n"]
    out.append(f"- 体量：{total_lines} 行 / 中文字符 {zh_total}"
               f"{'（⚠ 译文候选但近乎全 EN，属正常：源为 EN 版）' if zh_total < total_lines * 0.05 and zh_total < 50 else ''}")
    codes = [b for b in blocks if b[2] == "code"]
    tables = [b for b in blocks if b[2] == "table"]
    out.append(f"- 代码块 {len(codes)} 个（保留原样）；表格 {len(tables)} 个（键名原样、表头译）；见下。\n")

    # frontmatter
    out.append("## 一、frontmatter [决策]\n")
    for s, e, k, payload in blocks:
        if k != "frontmatter":
            continue
        for off, ln in enumerate(payload):
            mm = re.match(r"^([A-Za-z_-]+)\s*:", ln)
            if mm:
                key = mm.group(1)
                mark = " ← 需人工定（中文名/中文描述，不得机翻味）" if key in FRONTMATTER_KEYS_DECIDE else ""
                out.append(f"- L{s + off + 1} `{key}`{mark}")
    out.append("")

    # 标题树 + 骨架段检测
    out.append("## 二、标题树与分段 [翻译] / [重写]\n")
    for lv, title, start, end in heading_spans(blocks):
        body = "\n".join(lines[start:end]) if end >= start else ""
        zh = count_zh(body)
        body_lines = max(end - start, 0)
        tag = "[翻译]"
        warn = ""
        if any(t in title for t in SKELETON_TITLES):
            if body_lines < 5 or any(p in body for p in GENERIC_PHRASES):
                tag, warn = "[重写]", " ⚠ 疑似骨架占位（正文过短或含通用套话）"
        out.append(f"- L{start}-L{end} {'  ' * (lv - 1)}{tag} `{title}` — 正文 {body_lines} 行 / 中文字符 {zh}{warn}")
    out.append("")

    # 代码块
    out.append("## 三、代码块 [保留]\n")
    if codes:
        for s, e, _k, (body, lang) in codes:
            first = body[0].strip() if body else ""
            out.append(f"- L{s}-L{e} ```{lang}`` ({len(body)} 行) 首行：`{first[:60]}`")
    else:
        out.append("- 无")
    out.append("")

    # 表格
    out.append("## 四、表格 [核对：键名原样，表头与说明文字译]\n")
    for s, e, _k, rows in tables:
        header = rows[0].strip()
        out.append(f"- L{s}-L{e} 表头：`{header[:70]}`（{len(rows) - 1} 数据行）")
    if not tables:
        out.append("- 无")
    out.append("")

    # 行内路径/命令
    out.append("## 五、行内路径与命令 [核对：`内`原样；`外`按 glossary 第四节]\n")
    hits = []
    for s, e, k, payload in blocks:
        if k in ("code", "frontmatter"):
            continue
        content = "\n".join(payload) if isinstance(payload, list) else str(payload)
        for m in INLINE_PATH_RE.finditer(content):
            hits.append((s, m.group(0)))
    for s, tok in hits[:12]:
        out.append(f"- 约 L{s}: {tok[:80]}")
    if len(hits) > 12:
        out.append(f"- …共 {len(hits)} 处（其余略）")
    if not hits:
        out.append("- 无")
    out.append("")

    out.append("## 六、作业顺序（与 references/translation-pipeline.md 对应）\n")
    out.append("1. 逐项落定「一、frontmatter [决策]」；")
    out.append("2. 过一遍「五」核对路径口径（包内 → 真实路径；上游 → 「上游 `<模块>` 包中的 `<文件名>`」）；")
    out.append("3. 按「二」自上而下翻译，术语查 references/glossary.md，[重写] 段按源内容落为具体步骤与判据；")
    out.append("4. 全部完成后跑双门禁（self_check + check_localization），复看本计划无 [重写] 遗留。")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="生成中文化翻译作业计划（只分类，不改写）")
    ap.add_argument("skill_dir", type=Path)
    ap.add_argument("--out", type=Path, default=None, help="输出 plan 路径（默认 <skill_dir>/../translation-plan__<slug>.md）")
    ap.add_argument("--deep", action="store_true", help="附带分析 references/*.md（仅标题树摘要）")
    a = ap.parse_args()

    skill_md = a.skill_dir / "SKILL.md"
    if not skill_md.is_file():
        print(f"FAIL: 未找到 {skill_md}", file=sys.stderr)
        return 2

    plan = analyze(skill_md)

    if a.deep:
        refs = sorted((a.skill_dir / "references").glob("*.md")) if (a.skill_dir / "references").is_dir() else []
        if refs:
            plan += "\n## 七、references 附查 [翻译]\n"
            for r in refs:
                t = r.read_text(encoding="utf-8")
                zh = count_zh(t)
                heads = re.findall(r"^#{1,3}\s+(.+)$", t, flags=re.M)
                plan += (f"- {r.name}: {len(t.splitlines())} 行 / 中文字符 {zh} / 标题 {len(heads)} 个"
                         f"（首个：{heads[0][:40] if heads else '—'}）\n")

    out_path = a.out or (a.skill_dir.parent / f"translation-plan__{a.skill_dir.name}.md")
    out_path.write_text(plan, encoding="utf-8", newline="\n")

    n_rewrite = plan.count("[重写]")
    n_decision = plan.count("需人工定")
    print(f"PLAN_OK {out_path}")
    print(f"  [重写] 疑似骨架段: {n_rewrite} 个；[决策] frontmatter 字段: {n_decision} 个")
    return 0


if __name__ == "__main__":
    sys.exit(main())
