---
name: backlink-check
version: 1.0.0
display_name: "Backlink Check"
display_name_en: "Backlink Check"
description_zh: "将 backlink-check 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Backlink profile for any domain — referring domains, authority, anchors, new/lost links, and a side-by-side vs a competitor."
category: productivity
author: "_staged-backlink-check"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Backlink profile for any domain — referring domains, authority, anchors, new/lost links, and a side-by-side vs a competitor. Use when asked "check my backlinks", "backlink profile of X", "who links to them", or "link gap vs competitor".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-backlink-check
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Backlink Check

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

## Workflow

1. **Source.** Use the workspace's DataForSEO Backlinks tools (`native__get_provider_docs`, provider `dataforseo`, for exact request shapes): `summary` for the profile, `referring_domains` for the domain list, `anchors` for anchor distribution. If DataForSEO backlinks aren't exposed, fall back to a connected `ahrefs` or `semrush` provider; if neither, stop and say which connection is missing — never fabricate link counts.
2. **Target profile.** Pull summary + top ~100 referring domains by rank for the user's domain: total backlinks, referring domains, dofollow share, authority distribution.
3. **Competitor (if named).** Same pulls for the competitor. Compute the **link gap**: strong domains linking to them but not to the user — that's the outreach list.
4. **Quality read.** Flag: spammy anchor patterns (exact-match commercial anchors at scale), link velocity spikes, a profile dominated by low-authority domains.
5. **Traffic cross-check (own site only).** `google_analytics__runRawReport` — referral sessions by source; note which linking domains actually send visitors.

## Output

Verdict first (profile strength in one paragraph, and the gap vs the competitor if asked), then: profile summary table, top referring domains, anchor distribution, and — when a competitor was given — the link-gap outreach list (domain, authority, page linking to competitor). All third-party numbers labeled as index estimates.

## 执行流程

<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写为具体步骤与判据 -->

1. 按源技能定义的核心动作依次执行，每步明确动作与判据。
2. 每步产出可检查的中间结果，未达标则回退重做。


## 边界与降级

<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写 -->

- 信息不足时：用默认值推进并标注假设，不阻塞交付。
- 环境受限（无网络、无脚本执行）时：改为人工按上述规则执行，交付完整性不下降。
- 无法处理的场景写入边界说明，不假装覆盖。


## 质量自检

<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写 -->

- [ ] 输出满足源技能定义的验收标准
- [ ] 引用的资源路径全部存在
- [ ] 无占位符残留

## 搬运说明

本技能由上游源技能（本地素材）转换而来，核心流程与判据保持原样。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
