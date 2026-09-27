---
name: seo-vs-ads
version: 1.0.0
display_name: "Seo Vs Ads"
display_name_en: "Seo Vs Ads"
description_zh: "将 seo-vs-ads 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Find money leaking between search ads and SEO — queries you pay for while already ranking organically, and paid queries with no organic coverage."
category: productivity
author: "_staged-seo-vs-ads"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  Find money leaking between search ads and SEO — queries you pay for while already ranking organically, and paid queries with no organic coverage. Use when asked "am I paying for clicks I'd get free", "brand bidding waste", "SEO vs ads overlap", or "cut wasted ad spend with SEO".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-seo-vs-ads
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# SEO vs Ads

## Requires

The free Ryze MCP connector (`https://connector.get-ryze.ai/mcp`). Claude Code: `claude mcp add ryze --transport http https://connector.get-ryze.ai/mcp`. claude.ai / Desktop / Cursor: add it as a custom connector with the same URL. Setup: https://www.get-ryze.ai/how-to-connect-claude-to-google-meta-ads-mcp

The report subscription tools can't do: it needs your ads account AND your Search Console together. Both are on the Ryze MCP.

## Workflow

1. **Paid search terms.** `google_ads__runRawGaql` on the default account — search terms report, last 90 days: term, impressions, clicks, cost, conversions. (GAQL shape via `native__get_provider_docs`, provider `google_ads`, if needed.)
2. **Organic positions.** `google_search_console__runRawSearchAnalytics`, dimension `["query"]`, same window.
3. **Join on query** and bucket:
   - **Double-paying** — organic position ≤ 3 AND paid spend on the same term. Especially brand terms with no competing advertisers (check top-of-page rate / competition). Sum the spend: that's the number for the headline.
   - **Defensible** — organic ≤ 3 but competitors bid on the term (paid presence may be justified; say so honestly)
   - **Paid-only winners** — terms converting in ads with no organic ranking → the SEO content roadmap, pre-validated by money
   - **Organic-only converters** — strong organic queries with no ad coverage → scale candidates if ads team wants volume
4. **Estimate savings.** For the double-paying bucket: spend × the organic click-capture you'd retain (be conservative, ~50–70% for position 1 brand terms; label it an estimate).

## Output

Headline first: "$X/quarter going to clicks you already rank #1 for." Then the four buckets as tables (term, cost, conversions, organic position), the savings estimate with its assumptions stated, and a short action list: exact negatives to add, exact pages to build.

## Fallback

If only one of the two accounts is connected, run what's possible, and name the missing connection instead of guessing at the other half.

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
