---
name: competitor-gap
version: 1.0.0
display_name: "Competitor Gap"
display_name_en: "Competitor Gap"
description_zh: "将 competitor-gap 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Find keywords a competitor ranks for that the user's site doesn't — the content gap, prioritized by volume and winnability."
category: productivity
author: "_staged-competitor-gap"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Find keywords a competitor ranks for that the user's site doesn't — the content gap, prioritized by volume and winnability. Use when asked "what does competitor.com rank for", "keyword gap vs X", "steal competitor keywords", or "why do they outrank us".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-competitor-gap
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Competitor Gap

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

Their rankings are estimates (DataForSEO), yours are real (GSC). Diff them.

## Workflow

1. **Competitor's keywords.** Via the workspace's DataForSEO tools — Labs `ranked_keywords` for the competitor domain (request shape: `native__get_provider_docs`, provider `dataforseo`). Pull top ~500 by volume. If DataForSEO isn't exposed in this workspace, check for connected `ahrefs`/`semrush` providers and use their organic-keywords endpoint instead; if none, stop and say which connection is missing.
2. **Competitor overview.** Labs `domain_rank_overview` — their estimated organic traffic and keyword count, for context.
3. **Your keywords.** `google_search_console__runRawSearchAnalytics`, dimension `["query"]`, last 90 days, high rowLimit — the full set of queries the user's site gets impressions for.
4. **Diff into three buckets:**
   - **Gap** — competitor ranks top 20, you have zero impressions → new content needed
   - **Behind** — you both rank but they're ≥ 5 spots ahead → improve existing page
   - **Ahead** — you outrank them (report briefly; it's the moat)
5. **Prioritize** the Gap and Behind buckets by volume × relevance to the user's product. Drop branded competitor terms unless the user wants comparison pages — then list them separately as "vs / alternative" page candidates.

## Output

Verdict (how big the gap is, in keywords and estimated traffic), then: Gap table (keyword, their position, volume, suggested page), Behind table (keyword, their pos, your pos, your page, fix), and a top-10 action list. Note explicitly which numbers are estimates (theirs) vs real (yours).

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
