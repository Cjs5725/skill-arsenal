#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""decompose_skills.py — 组合实验台·工序一：把技能拆解为可复用能力单元。

拆解对象：port-v2 平台版目录（22 技能，zh）。粒度 = SKILL.md 的二级标题段（## …）。
拆解规则（详见 references/combination-lab.md）：
  1. 单元自含：正文依赖「上一节/如上所述/见第 X 节」者标记 self_contained=false；
  2. 类型四分：capability（能力正文）/ workflow（执行流程）/ boundary（边界与降级）/ qa（质量自检）；
  3. 搬运说明不入库（出处信息，非能力）；frontmatter 不入库（字段层，非正文能力）；
  4. 每单元强制带来源（skill + 行号区间），组合时逐单元可溯。

用法： python decompose_skills.py [--base PORT_V2_DIR] [--out OUT.json]
输出： OUT.json（机读单元库）+ OUT 同目录 units-library.md（人读摘要）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ZH_RE = re.compile(r"[一-鿿]")
REF_PAT = re.compile(r"上一节|前一节|如上所述|见第[一二三四五六七八九十]+[节章]|（见上文）|如前述")
TEMPLATE_SKIP = ("搬运说明",)
TYPE_RULES = (
    ("执行流程", "workflow"),
    ("边界与降级", "boundary"),
    ("质量自检", "qa"),
)


def classify(title: str) -> str:
    for key, t in TYPE_RULES:
        if key in title:
            return t
    return "capability"


def split_sections(text: str):
    lines = text.splitlines()
    heads = [(i, ln) for i, ln in enumerate(lines) if re.match(r"^##\s+\S", ln)]
    if not heads:
        return []
    secs = []
    for k, (i, ln) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        secs.append({
            "title": re.sub(r"^##\s+", "", ln).strip(),
            "start": i + 1,            # 1-based
            "end": end,                # 1-based 闭区间
            "body": "\n".join(lines[i:end]).rstrip() + "\n",
        })
    return secs


def main() -> int:
    ap = argparse.ArgumentParser(description="拆解技能为能力单元库")
    ap.add_argument("--base", type=Path, default=None,
                    help="平台版技能根目录（含各技能子目录），如 <输出根>/port-v2")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()
    if a.base is None:
        ap.error("--base 必填：指定平台版技能根目录（避免硬编码本机路径）")
    out = a.out or (a.base / "units-library.json")

    skills = sorted(
        d for d in a.base.iterdir()
        if d.is_dir() and (d / "SKILL.md").is_file()
        and not d.name.endswith("-local") and d.name not in ("dist-zh", "listing")
    )
    lib, skipped, not_self = {"_meta": {
        "base": str(a.base), "generated_by": "decompose_skills.py",
        "rules": "granularity=##-section; 搬运说明不入库; 单元必须自含或显式标记不自含",
    }}, 0, 0
    for d in skills:
        text = (d / "SKILL.md").read_text(encoding="utf-8")
        units = []
        for sec in split_sections(text):
            if any(t in sec["title"] for t in TEMPLATE_SKIP):
                skipped += 1
                continue
            body = sec["body"]
            broken = bool(REF_PAT.search(body))
            not_self += broken
            units.append({
                "id": f"{d.name}::{sec['title']}",
                "skill": d.name,
                "type": classify(sec["title"]),
                "title": sec["title"],
                "lines": f"L{sec['start']}-L{sec['end']}",
                "zh_chars": len(ZH_RE.findall(body)),
                "self_contained": not broken,
                "inline_refs": len(re.findall(r"`[^`]*[\w.-]+/[\w.-]+", body)),
                "body": body,
            })
        lib[d.name] = units

    total = sum(len(v) for k, v in lib.items() if k != "_meta")
    lib["_meta"]["skills"] = len(skills)
    lib["_meta"]["units_total"] = total
    lib["_meta"]["template_skipped"] = skipped
    lib["_meta"]["not_self_contained"] = not_self
    out.write_text(json.dumps(lib, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    # 人读摘要
    md = ["# 能力单元库（人读摘要）", "",
          f"> 共 {len(skills)} 技能 / {total} 单元；搬运说明段 {skipped} 个已排除；不自含单元 {not_self} 个（组合时须补语境）。",
          "> 机读版：units-library.json。正文全文在 JSON 的 body 字段，本摘要只列索引。", ""]
    for d in skills:
        md.append(f"## {d.name}（{len(lib[d.name])} 单元）")
        for u in lib[d.name]:
            flag = "" if u["self_contained"] else " ⚠不自含"
            md.append(f"- [{u['type']}] `{u['id']}` {u['lines']} / {u['zh_chars']} 字{flag}")
        md.append("")
    (out.parent / "units-library.md").write_text("\n".join(md), encoding="utf-8", newline="\n")

    print(f"LIB_OK {out}")
    print(f"  技能 {len(skills)} / 单元 {total} / 排除搬运说明 {skipped} / 不自含 {not_self}")
    by_type = {}
    for k, v in lib.items():
        if k == "_meta":
            continue
        for u in v:
            by_type[u["type"]] = by_type.get(u["type"], 0) + 1
    print("  类型分布:", by_type)
    return 0


if __name__ == "__main__":
    sys.exit(main())
