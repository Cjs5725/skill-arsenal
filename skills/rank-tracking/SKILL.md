---
name: rank-tracking
version: 1.0.0
display_name: "Rank Tracking"
display_name_en: "Rank Tracking"
description_zh: "将 rank-tracking 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Rank tracking without a tracker subscription — position movers between any two periods from real Search Console data."
category: productivity
author: "_staged-rank-tracking"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Rank tracking without a tracker subscription — position movers between any two periods from real Search Console data. Use when asked "how are my rankings", "what moved this week/month", "track my keywords", or "did the update hit me".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-rank-tracking
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Rank Tracking

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

Rank trackers estimate your position by scraping SERPs daily. Search Console records the position Google actually served you at. Use the real number.

## Workflow

1. **Property.** `google_search_console__listSites` → pick the user's domain.
2. **Two windows.** Default: last 28 days vs previous 28. If the user names an event ("since the March update"), split around that date. GSC data lags ~2 days — never include today.
3. **Pull both periods.** `google_search_console__runRawSearchAnalytics`, dimensions `["query"]`, rowLimit high enough to cover the site (start 5000). Repeat with `["page"]` for page-level movement.
4. **Join and diff.** Match queries across periods, compute position delta, clicks delta, impressions delta.
5. **Classify:**
   - **Winners** — position improved ≥ 2 spots on queries with real impressions
   - **Losers** — dropped ≥ 2 spots (sort by clicks lost, not by delta — a 4→7 drop on a money query beats a 40→80 crash on a nothing query)
   - **New** — queries appearing only in the recent period
   - **Lost** — queries that vanished
6. **Spot-verify (optional).** For the 3–5 most important losers, if DataForSEO SERP tools are exposed in the workspace, pull the live SERP to see who took the spot. Skip if unavailable.

## Output

Verdict first (net up/down and the single biggest move), then four tables: Winners, Losers, New, Lost — query, positions before→after, clicks delta. If the user asked about a specific algorithm update, answer that question explicitly with the before/after evidence.

## Recurring

If the user wants this weekly, suggest scheduling it (Claude Code scheduled tasks / a routine) rather than re-running by hand.

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
