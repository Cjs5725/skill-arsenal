---
name: keyword-research
version: 1.0.0
display_name: "Keyword Research"
display_name_en: "Keyword Research"
description_zh: "将 keyword-research 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Keyword research from a seed topic — ideas, real Google volume/CPC, intent, difficulty, clustered into a plan."
category: productivity
author: "_staged-keyword-research"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Keyword research from a seed topic — ideas, real Google volume/CPC, intent, difficulty, clustered into a plan. Use when asked to "find keywords", "keyword research for X", "what should I rank for", or "build a keyword plan".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-keyword-research
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Keyword Research

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

Seed → ideas → metrics → clusters. Volumes come from Google Ads planner data (the source everyone else resells), enriched with DataForSEO intent/difficulty.

## Workflow

1. **Expand the seed.** `google_ads__generateKeywordIdeas` with the seed keyword(s) and/or the user's URL. Collect up to ~200 ideas.
2. **Metrics.** `google_ads__generateKeywordHistoricalMetrics` on the candidate list — monthly volume, competition, CPC range, 12-month trend.
3. **Intent + difficulty (optional enrich).** If the workspace exposes DataForSEO tools, call the Labs `keyword_overview` endpoint for the top ~50 (search intent, keyword difficulty, SERP features). Request shape: `native__get_provider_docs` provider `dataforseo`. Skip silently if unavailable — Google metrics alone are enough for a v1 plan.
4. **What they already rank for.** `google_search_console__runRawSearchAnalytics` (dimension `query`, filtered to the topic) — mark keywords the site already has positions for; those are optimize-not-create.
5. **Cluster.** Group by intent and topic into content clusters: pillar + supporting pages. For each cluster: target keyword, supporting keywords, total volume, intent, existing page (if any) or "new page".

## Output

One table per cluster (keyword, volume, CPC, intent, current position if any), then a ranked plan: which clusters to attack first and why (volume × winnability — favor clusters where the site already has striking-distance positions). Plain language, no filler.

## Rules

- Never invent volumes. If a metrics call fails, show the keyword without numbers and say why.
- CPC belongs in the output — it tells the user what the traffic is worth, and this doubles as an ads negative-keyword source.

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
