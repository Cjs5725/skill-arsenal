# -*- coding: utf-8 -*-
"""生成技能库全量台账 skill-registry.md：扫 _production/port-v2 与 _release 批次目录，按方案字段出册。"""
import json, re
from pathlib import Path

ROOT = Path(r"E:/workbuddy/2026-09-13-23-02-38")
PROD = ROOT / "_release/2026-09-15/port-v2"
B6 = ROOT / "_release/2026-09-25/batch6"
ZH_DONE = set()
if (PROD / "_zh_done.txt").is_file():
    ZH_DONE = {l.strip() for l in (PROD / "_zh_done.txt").read_text(encoding="utf-8").splitlines() if l.strip()}

# 标签判定：按 slug 关键词（主标签在前）
TAGS = [
    (r"catalog|listing|pricing|inventory|marketing|purchase|search-discovery|customer-care|commerce|merchant", "电商运营"),
    (r"internal-comms", "文档办公"),
    (r"canvas-design|algorithmic-art|theme-factory|frontend-design|goldie|slack-gif", "设计创作"),
    (r"mcp-builder|webapp-testing|web-artifacts|claude-api|agent-browser|pdf$|docx$|pptx$|xlsx$", "开发工具"),
    (r"astra|skill-creator|porter", "编排方法"),
    (r"discernment|memory|planning|performance|trust-safety", "辅助增强"),
]

def tags_for(slug):
    hits = [t for pat, t in TAGS if re.search(pat, slug)]
    return "/".join(hits[:2]) if hits else "辅助增强"

LICENSE = {"zh-pass": "Apache-2.0/MIT（随包，见包内 LICENSE）"}

# 第 6/7 批 slug（须在 port-v2 扫描前可用，用于排除重复出册）
B6_SLUGS = {"algorithmic-art", "brand-guidelines", "internal-comms", "discernment-nudge", "slack-gif-creator"}
B7_SLUGS = {"ai-visibility", "backlink-check", "competitor-gap", "content-brief",
            "keyword-research", "rank-tracking", "seo-audit", "seo-vs-ads", "video-transcribe"}
B8_SLUGS = {"jev-skill", "holo-card-studio"}

rows = []
# 批次 1–5：port-v2 正本（第 6 批已并入的 4 个技能在此跳过，避免按「第1–5批」重复出册）
for d in sorted(PROD.iterdir()):
    if d.is_dir() and not d.name.endswith("-local") and d.name not in B6_SLUGS and d.name not in B7_SLUGS and d.name not in B8_SLUGS and (d / "SKILL.md").is_file():
        slug = d.name
        zh = "zh-pass" if slug in ZH_DONE else "en-pass"
        rows.append((slug, tags_for(slug), "各上游（见 porting-changes.md）", "随包 LICENSE", zh, "第1–5批", f"_release/2026-09-15/port-v2/{slug}/"))
# 第 6 批（2026-09-25 并入正本：4 个 zh-pass 的正本路径指向 port-v2；
# slack-gif-creator 未过平台强依赖闸，仍留批次目录 local-only）
B6_ROWS = {
    "algorithmic-art": ("设计创作", "anthropics/skills", "Apache-2.0", "zh-pass", "第6批", "_release/2026-09-15/port-v2/algorithmic-art/"),
    "brand-guidelines": ("设计创作", "anthropics/skills", "Apache-2.0", "zh-pass", "第6批", "_release/2026-09-15/port-v2/brand-guidelines/"),
    "internal-comms": ("文档办公", "anthropics/skills", "Apache-2.0", "zh-pass", "第6批", "_release/2026-09-15/port-v2/internal-comms/"),
    "discernment-nudge": ("辅助增强", "anthropics/skills", "Apache-2.0", "zh-pass", "第6批", "_release/2026-09-15/port-v2/discernment-nudge/"),
    "slack-gif-creator": ("设计创作", "anthropics/skills", "Apache-2.0", "local-only", "第6批", "_release/2026-09-25/batch6/slack-gif-creator/"),
}
for slug, (tag, src, lic, st, batch, path) in B6_ROWS.items():
    rows.append((slug, tag, src, lic, st, batch, path))
# 第 7 批（2026-09-26：N9 open-seo-mcp-skills 八技能 + 示范案例 video-transcribe，
# 09-27 并入正本，正本路径指向 port-v2）
B7_ROWS = {
    slug: ("营销运营", "Ryze-AI-Adgent/open-seo-mcp-skills", "MIT", "zh-pass", "第7批", f"_release/2026-09-15/port-v2/{slug}/")
    for slug in ("ai-visibility", "backlink-check", "competitor-gap", "content-brief",
                 "keyword-research", "rank-tracking", "seo-audit", "seo-vs-ads")
}
B7_ROWS["video-transcribe"] = ("开发工具", "wendy7756/AI-Video-Transcriber", "Apache-2.0", "zh-pass", "示范案例", "_release/2026-09-15/port-v2/video-transcribe/")
for slug, (tag, src, lic, st, batch, path) in B7_ROWS.items():
    rows.append((slug, tag, src, lic, st, batch, path))
# 第 8 批（2026-09-27：jev 线甲档 Jev-Skill + 技能榜 M3 holo-card-studio）
# jev-skill＝zh-pass 可上架；holo-card-studio＝强依赖（Pillow/Blender/npm）判 local-only，
# 本批产物在批次目录（未并入 port-v2，并入时 path 改指正本）
B8_ROWS = {
    "jev-skill": ("开发工具", "aiwithenoch/Jev-Skill", "MIT-0", "zh-pass", "第8批", "_release/2026-09-27/batch8/jev-skill/"),
    "holo-card-studio": ("设计创作", "EverettFish/holo-card-studio", "MIT", "local-only", "第8批", "_release/2026-09-27/batch8/holo-card-studio/"),
}
for slug, (tag, src, lic, st, batch, path) in B8_ROWS.items():
    rows.append((slug, tag, src, lic, st, batch, path))
# 自研引擎
rows.append(("github-skill-porter", "编排方法", "自研", "Apache-2.0", "zh-pass", "第5批", "skill-build/github-skill-porter/"))

out = ["# 技能库台账（skill-registry）", "",
       "> 自动生成于 2026-09-25 · 维护规则：状态六态 inbox/en-pass/zh-pass/listed/local-only/frozen；新技能先登记 inbox。",
       "", "| slug | 标签 | 来源 | 许可 | 状态 | 批次 | 正本路径 |", "|---|---|---|---|---|---|---|"]
for r in rows:
    out.append("| " + " | ".join(r) + " |")
out += ["", f"合计：**{len(rows)}** 个技能（zh-pass {sum(1 for r in rows if r[4]=='zh-pass')} / en-pass {sum(1 for r in rows if r[4]=='en-pass')} / local-only {sum(1 for r in rows if r[4]=='local-only')}）"]
p = ROOT / "skill-registry.md"
p.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
print(f"REGISTRY_OK {len(rows)} 条 -> {p}")
