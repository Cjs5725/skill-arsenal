---
name: seo-audit
version: 1.0.0
display_name: "Seo Audit"
display_name_en: "Seo Audit"
description_zh: "将 seo-audit 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Full SEO audit of a site from its real Search Console + GA4 data — indexation health, CTR anomalies, decaying pages, striking-distance keywords, quick wins."
category: productivity
author: "_staged-seo-audit"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Full SEO audit of a site from its real Search Console + GA4 data — indexation health, CTR anomalies, decaying pages, striking-distance keywords, quick wins. Use when asked to "audit my site", "SEO audit", "why is my organic traffic down", or "SEO health check".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-seo-audit
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# SEO Audit

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

Audit the user's site using their own data via the Ryze MCP. No estimates — everything below comes from their actual GSC/GA4.

## Workflow

1. **Pick the property.** `google_search_console__listSites`. If several, use the one matching the user's domain; confirm only when ambiguous.
2. **Indexation.** `google_search_console__getIndexationSummary` — indexed vs not-indexed counts and reasons. Flag anything unusual (large "Crawled — currently not indexed", spikes in excluded pages).
3. **Performance baseline.** `google_search_console__runRawSearchAnalytics`: last 90 days vs previous 90, dimensions `query` and `page` (two calls each period). Compute clicks/impressions/CTR/position deltas.
4. **Find the problems:**
   - **Decaying pages** — pages whose clicks dropped >30% period-over-period
   - **CTR anomalies** — queries with position ≤ 5 but CTR < 2% (title/meta problem)
   - **Striking distance** — queries at position 8–20 with high impressions (one push from page 1)
   - **Cannibalization** — same query, multiple ranking pages splitting clicks
5. **Spot-check pages.** For the 3–5 worst pages, `google_search_console__inspectUrl` — canonical, indexing state, last crawl.
6. **Cross-check traffic.** `google_analytics__runRawReport` — organic sessions + conversions by landing page, same periods. A page can hold rankings but lose revenue; call that out.
7. **AI traffic.** `google_analytics__getAIReferrals` for the same window — note whether AI engines are becoming a meaningful channel for this site.

## Output

A report with: verdict up top (one paragraph, is the site healthy or not and the #1 issue), then sections — Indexation, Losers, Quick wins (striking distance + CTR fixes, ranked by impressions), Cannibalization — each with a table and the specific fix. End with a prioritized 5-item action list.

## Fallbacks

If GSC isn't connected, say so and point to Ryze connector setup (https://help.get-ryze.ai/claude/connect) — do not substitute third-party estimates for the site's own data.

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
