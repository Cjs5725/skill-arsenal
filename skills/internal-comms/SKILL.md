---
name: internal-comms
version: 1.0.0
display_name: "Internal Comms"
display_name_en: "Internal Comms"
description_zh: "将 internal-comms 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use."
category: productivity
author: "anthropics/skills/skills/internal-comms"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  A set of resources to help me write all kinds of internal communications, using the formats that my company likes to use. Claude should use this skill whenever asked to write some sort of internal communications (status reports, leadership updates, 3P updates, company newsletters, FAQs, incident reports, project updates, etc.).
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/skills/skills/internal-comms
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


## When to use this skill
To write internal communications, use this skill for:
- 3P updates (Progress, Plans, Problems)
- Company newsletters
- FAQ responses
- Status reports
- Leadership updates
- Project updates
- Incident reports

## How to use this skill

To write any internal communication:

1. **Identify the communication type** from the request
2. **Load the appropriate guideline file** from the `references/` directory:
    - `references/examples__3p-updates.md` - For Progress/Plans/Problems team updates
    - `references/examples__company-newsletter.md` - For company-wide newsletters
    - `references/examples__faq-answers.md` - For answering frequently asked questions
    - `references/examples__general-comms.md` - For anything else that doesn't explicitly match one of the above
3. **Follow the specific instructions** in that file for formatting, tone, and content gathering

If the communication type doesn't match any existing guideline, ask for clarification or more context about the desired format.

## Keywords
3P updates, company newsletter, company comms, weekly update, faqs, common questions, updates, internal comms

## 执行流程

1. 从请求判定沟通类型：3P 更新（进展/计划/问题）、公司简报、FAQ 答复、或其它内部沟通。
2. 加载对应指南文件：`references/examples__3p-updates.md`（3P）、`references/examples__company-newsletter.md`（简报）、`references/examples__faq-answers.md`（FAQ）、`references/examples__general-comms.md`（其它）。
3. 按该指南的格式、语气与素材收集要求写作。
4. 类型与四份指南都不匹配时，先向用户澄清期望格式，不强行套用。


## 边界与降级

- 澄清后仍无匹配指南时：用 general-comms.md 兜底，并在交付开头注明所用假设。
- 写作所需的进度、数字等事实缺失时：向用户收集后再写，禁止编造进展或数据。
- references 指南文件缺失时：按本文件 Keywords 与正文场景描述执行，并声明已降级。


## 质量自检

- [ ] 所用指南文件与沟通类型对应且真实加载
- [ ] 格式与语气符合该指南的具体要求
- [ ] 无编造的事实性内容（进展/数字/事件）
- [ ] 四个 references 路径全部存在

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
