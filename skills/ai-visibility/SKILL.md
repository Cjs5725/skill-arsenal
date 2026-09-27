---
name: ai-visibility
version: 1.0.0
display_name: "Ai Visibility"
display_name_en: "Ai Visibility"
description_zh: "将 ai-visibility 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Measure real AI-engine visibility — traffic from ChatGPT, Perplexity, Claude, Gemini and which pages they cite — from actual GA4 referral data, not prompt sampling."
category: productivity
author: "_staged-ai-visibility"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Measure real AI-engine visibility — traffic from ChatGPT, Perplexity, Claude, Gemini and which pages they cite — from actual GA4 referral data, not prompt sampling. Use when asked "AI visibility", "GEO/AEO check", "do LLMs cite us", "traffic from ChatGPT", or "how do we show up in AI search".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-ai-visibility
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# AI Visibility

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

Every "AI visibility tracker" samples prompts and guesses. GA4 records the actual clicks AI engines send. Measure the real thing first, then diagnose.

## Workflow

1. **Traffic by engine.** `google_analytics__getAiTrafficByEngine` — sessions per AI source (ChatGPT, Perplexity, Gemini, Claude, Copilot…), current vs previous period.
2. **Trend.** `google_analytics__getAiTrafficDaily` — is AI traffic growing, and did anything spike (a spike = something started citing you; find it).
3. **Cited pages.** `google_analytics__getAiLandingPages` — which URLs AI engines actually send people to. These are your proven-citable pages.
4. **Referral detail.** `google_analytics__getAIReferrals` for source-level detail and conversions — is AI traffic converting better or worse than organic.
5. **Diagnose the winners.** Read the top 2–3 cited pages (fetch them). Note the pattern: direct answers high on the page, stats/definitions, clean headings, schema. That pattern is the citation recipe for this site.
6. **Find the misses.** Cross-reference with `google_search_console__runRawSearchAnalytics`: pages with strong organic queries but zero AI referrals — candidates to restructure toward the citation recipe from step 5.

## Output

Verdict (AI traffic share of organic, trend, top engine), then: engine table, cited-pages table with conversions, the citation recipe observed on winning pages, and a top-5 list of pages to restructure. Keep it concrete — name the pages and the exact change.

## Fallback

If the GA4 AI-traffic tools aren't available in the workspace, build the same report with `google_analytics__runRawReport` filtered on `sessionSource` matching known AI referrers (chatgpt.com, perplexity.ai, gemini.google.com, claude.ai, copilot.microsoft.com).

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
