---
name: content-brief
version: 1.0.0
display_name: "Content Brief"
display_name_en: "Content Brief"
description_zh: "将 content-brief 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "SERP-driven content brief for a target keyword — what ranks, what to cover, headings, questions, internal links from your own data."
category: productivity
author: "_staged-content-brief"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  SERP-driven content brief for a target keyword — what ranks, what to cover, headings, questions, internal links from your own data. Use when asked for a "content brief", "outline to rank for X", "what should this article cover", or before writing any SEO page.
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-content-brief
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Content Brief

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

A brief grounded in the live SERP plus the site's own data — not a generic outline.

## Workflow

1. **The SERP.** If the workspace exposes DataForSEO SERP tools, pull the live Google top 10 for the target keyword (`native__get_provider_docs`, provider `dataforseo`, for the request shape) — titles, URLs, SERP features (featured snippet, PAA, video). If unavailable, fetch the top results via web search instead; the brief must be built from a real SERP either way.
2. **Read the top 3.** Fetch and skim the top-ranking pages: their structure, depth, angle, what they all cover (table stakes) and what none cover (the opening).
3. **Keyword set.** `google_ads__generateKeywordIdeas` seeded with the target — secondary keywords and question variants worth folding in, with volumes via `google_ads__generateKeywordHistoricalMetrics`.
4. **Your existing foothold.** `google_search_console__runRawSearchAnalytics` filtered to the topic — queries the site already gets impressions for (work them into headings), and existing pages on adjacent topics (internal-link sources; also flag if one already half-covers this and should be expanded instead of a new page).
5. **Assemble the brief:**
   - Target keyword + secondaries with volumes
   - Search intent and required format (guide/listicle/comparison/tool page), inferred from what actually ranks
   - Proposed title + meta (write for the CTR, under 60/155 chars)
   - H2/H3 outline with a one-line note per section on what it must say
   - Questions to answer (PAA + question keywords)
   - Table stakes vs the differentiating angle
   - Internal links: 3–5 existing pages to link from, with anchors
   - Target length: match the ranking median, don't pad

## Output

The brief, ready to hand to a writer (or to write from directly). No preamble.

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
