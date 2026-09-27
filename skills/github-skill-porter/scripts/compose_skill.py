#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compose_skill.py — 组合实验台·工序二：从单元库组合生成新技能草稿。

输入：组合规格 JSON（goal + units[(skill, section, role)] + 组合级边界/自检项）。
输出：<out>/<slug>/SKILL.md（组合草稿，带出处表与组合声明）。

组合三闸（硬校验，不过即退出码非 0）：
  ① 目标先行：goal 不得为空且 ≥ 20 字——先定义单一用户目标，禁止先拼后想；
  ② 单元存在：每个 (skill, section) 必须命中单元库，且 self_contained；
  ③ 判据完备：组合级边界 ≥ 2 条、组合级自检 ≥ 2 条（防止通用套话骨架）。

定位：本脚本产出**草稿**（出处可溯、过结构门禁），内容质量终审留给人工——
组合是造新性质，不是去重，与 merge_skills.py 的定位严格区分。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_FIELDS = ("slug", "display_name", "display_name_en", "description_zh",
                   "description_en", "goal", "units")


def fail(msg: str) -> int:
    print(f"COMPOSE_FAIL: {msg}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="从能力单元库组合生成新技能草稿")
    ap.add_argument("spec", type=Path, help="组合规格 JSON")
    ap.add_argument("--library", type=Path, default=None,
                    help="单元库 JSON（decompose_skills.py 的输出）；默认取 --out 同目录的 units-library.json")
    ap.add_argument("--out", type=Path, default=None, help="草稿输出根目录")
    a = ap.parse_args()
    if a.out is None:
        ap.error("--out 必填：指定草稿输出根目录（避免硬编码本机路径）")
    if a.library is None:
        a.library = a.out / "units-library.json"

    spec = json.loads(a.spec.read_text(encoding="utf-8"))
    for f in REQUIRED_FIELDS:
        if not spec.get(f):
            return fail(f"规格缺必填字段 {f}")
    slug, units = spec["slug"], spec["units"]
    if len(spec["goal"]) < 20:
        return fail("目标先行闸：goal 过短（<20 字），先定义单一用户目标再选单元")
    if len(spec.get("boundaries", [])) < 2 or len(spec.get("qa", [])) < 2:
        return fail("判据完备闸：组合级 boundaries 与 qa 各须 ≥2 条具体条目")

    lib = json.loads(a.library.read_text(encoding="utf-8"))
    index = {u["id"]: u for k, v in lib.items() if k != "_meta" for u in v}

    picked, skills_involved = [], []
    for e in units:
        uid = f"{e['skill']}::{e['section']}"
        u = index.get(uid)
        if not u:
            return fail(f"单元不存在：{uid}（先跑 decompose_skills.py 或检查节名）")
        if not u["self_contained"]:
            return fail(f"单元不自含，须先回源补语境：{uid}")
        if not e.get("role"):
            return fail(f"单元缺角色说明（在新目标下干什么）：{uid}")
        picked.append((e, u))
        if e["skill"] not in skills_involved:
            skills_involved.append(e["skill"])

    dst = a.out / slug
    dst.mkdir(parents=True, exist_ok=True)

    # 资源随迁闸：单元正文引用的包内资源（references|scripts|assets/...）从源技能一并搬迁，
    # 否则组合稿出现悬空引用（实测：goldie 单元引用其 references/config.md 与 flows.md）。
    import re as _re, shutil as _shutil
    base_dir = a.library.parent
    migrated = []
    for e, u in picked:
        for m in _re.finditer(r"`((?:references|scripts|assets)/[\w.-]+)`", u["body"]):
            rel = m.group(1)
            src_f = base_dir / e["skill"] / rel
            dst_f = dst / rel
            if src_f.is_file() and not dst_f.exists():
                dst_f.parent.mkdir(parents=True, exist_ok=True)
                _shutil.copy2(src_f, dst_f)
                migrated.append(f"{e['skill']}/{rel}")
    if migrated:
        print(f"  资源随迁 {len(migrated)} 个：{'、'.join(migrated)}")

    n = len(picked)
    zh_desc = spec["description_zh"]
    lines = []
    lines += [
        "---",
        f"name: {slug}",
        "version: 0.1.0",
        f"display_name: \"{spec['display_name']}\"",
        f"display_name_en: \"{spec['display_name_en']}\"",
        f"description_zh: \"{zh_desc}\"",
        f"description_en: \"{spec['description_en']}\"",
        f"category: {spec.get('category', 'productivity')}",
        "author: WorkBuddy 组合实验台",
        "allowed-tools: Read,Write,Edit,Bash,Glob,Grep",
        "agent_created: true",
        "license: \"Apache-2.0\"",
        "description: |",
        f"  {spec['goal']}",
        f"  本技能为组合稿：由 {'、'.join(skills_involved)} 的 {n} 个能力单元按上述目标装配，各节标注来源；",
        "  不适用于：与该目标无关的场景，以及需要单元原技能全部能力（超出组合范围）的场景。",
        "---",
        "",
        f"# {spec['display_name']}",
        "",
        "> **组合声明**：本文稿由组合实验台从已交付技能的能力单元装配而成，正文各节标注来源技能与单元；",
        "> 组合引入的新语境（目标衔接、执行顺序、组合级边界）为新增内容。整体定位为**草稿**，",
        "> 上架前须经人工终审并复跑双门禁。出处明细见文末「出处表」。",
        "",
        "## 一、目标与组合说明",
        "",
        f"- **用户目标**：{spec['goal']}",
        "- **单元角色**：",
        "",
        "| # | 单元 | 来源技能 | 在本组合中的角色 |",
        "|---|---|---|---|",
    ]
    for i, (e, u) in enumerate(picked, 1):
        lines.append(f"| {i} | {e['section']} | {e['skill']} | {e['role']} |")
    lines += ["", "## 执行流程", ""]
    for i, (e, u) in enumerate(picked, 1):
        lines.append(f"{i}. 执行「{num_head(i + 1)}、{e['section']}」（来源 {e['skill']}）：{e['role']}；")
    lines += [
        f"{n + 1}. 汇总各步产出，对照「{num_head(n + 2)}、边界与降级」「{num_head(n + 3)}、质量自检」复核后交付。",
        "",
    ]
    for i, (e, u) in enumerate(picked, 1):
        lines.append(f"## {num_head(i + 1)}、{e['section']}（来源：{e['skill']} {u['lines']}）")
        lines.append("")
        lines.append(u["body"].rstrip())
        lines.append("")
    lines += [
        f"## {num_head(n + 2)}、边界与降级（组合级）",
        "",
        "以下为本组合新增的组合级边界；各单元自身判据随单元正文保留，两层都须遵守。",
        "",
    ]
    lines += [f"- {b}" for b in spec["boundaries"]]
    lines += [
        "",
        f"## {num_head(n + 3)}、质量自检（组合级）",
        "",
    ]
    for b in spec["qa"]:
        lines.append(f"- [ ] {b}")
    lines += [
        "- [ ] 组合规格存档 `composition-spec.json`（目标、单元角色与验收判据的可复现定义）与本稿内容一致",
        "- [ ] 各单元正文判据已按其原技能 QA 口径复核（出处见下表）", "",
        f"## {num_head(n + 4)}、出处表", "",
        "| 单元 | 来源技能 | 源行号 | 类型 |", "|---|---|---|---|"]
    for e, u in picked:
        lines.append(f"| {e['section']} | {e['skill']} | {u['lines']} | {u['type']} |")
    lines.append("")

    (dst / "SKILL.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")

    # 组合规格存档（可复现）
    (dst / "composition-spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    print(f"COMPOSE_OK {dst / 'SKILL.md'}")
    print(f"  单元 {n} 个，来源技能 {len(skills_involved)} 个：{'、'.join(skills_involved)}")
    print(f"  下一步：人工终审 + 双门禁（self_check / check_localization）")
    return 0


def num_head(i: int) -> str:
    cn = "一二三四五六七八九十"
    return cn[i - 1] if 1 <= i <= 10 else str(i)


if __name__ == "__main__":
    sys.exit(main())
