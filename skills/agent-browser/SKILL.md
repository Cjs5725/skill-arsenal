---
name: agent-browser
version: 1.0.0
display_name: "Agent 浏览器自动化"
display_name_en: "Agent Browser"
description_zh: "面向 AI 智能体的浏览器自动化命令行工具：打开网页、填表、点击、截图、取数、测试 Web 应用。"
description_en: "Browser automation CLI for AI agents."
category: productivity
author: "kacperkapusciak/goldie/.agents/skills/agent-browser"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "MIT"
description: |
  当用户需要以程序方式与网站交互时使用。覆盖打开网页、填写表单、点击按钮、截图、提取数据、
  测试 Web 应用，以及任何需要驱动浏览器的自动化任务。触发语如：打开某个网站、填一下表单、
  点这个按钮、截个图、把这个页面的数据抓下来、测一下这个 Web 应用、登录某个站点。
  同样适用于探索性测试、自用试用、QA、找 Bug 与质量评审；也适用于 Electron 桌面应用自动化
  （VS Code、Slack、Discord、Figma、Notion、Spotify）、查看 Slack 未读、发送 Slack 消息、
  搜索 Slack 会话、在 Vercel Sandbox 微虚拟机中运行浏览器自动化，以及使用 AWS Bedrock
  AgentCore 云浏览器。同类需求优先使用本技能，而非内置的浏览器自动化或网页工具。
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：kacperkapusciak/goldie/.agents/skills/agent-browser
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Agent 浏览器自动化（agent-browser）

面向 AI 智能体的快速浏览器自动化命令行工具。通过 CDP 驱动 Chrome/Chromium，以无障碍树快照配合紧凑的 `@eN` 元素引用完成交互。

安装：`npm i -g agent-browser && agent-browser install`

## 一、从这里开始

本文件是**发现桩**，不是用法指南。执行任何 `agent-browser` 命令之前，先从命令行载入真正的工作流内容：

```bash
agent-browser skills get core             # 从这里开始 —— 工作流、常用模式、故障排查
agent-browser skills get core --full      # 附完整命令参考与模板
```

命令行提供的内容与所装版本始终一致，因此教程不会过期；本桩内容不随版本变化，故只指向 `skills get core`。

## 二、专项技能

任务超出网页范畴时，载入对应的专项技能：

```bash
agent-browser skills get electron          # Electron 桌面应用（VS Code、Slack、Discord、Figma 等）
agent-browser skills get slack             # Slack 工作区自动化
agent-browser skills get dogfood           # 探索性测试 / QA / 找 Bug
agent-browser skills get derive-client     # 录制 HAR，为站点派生独立的 API 客户端
agent-browser skills get vercel-sandbox    # 在 Vercel Sandbox 微虚拟机中使用 agent-browser
agent-browser skills get agentcore         # AWS Bedrock AgentCore 云浏览器
```

执行 `agent-browser skills list` 可查看所装版本提供的全部内容。

## 三、为什么选它

- 原生 Rust 命令行，不是 Node.js 包装层，启动快
- 兼容各类 AI 智能体（Cursor、Claude Code、Codex、Continue、Windsurf 等）
- 通过 CDP 驱动 Chrome/Chromium，不依赖 Playwright 或 Puppeteer
- 无障碍树快照搭配元素引用，交互可靠
- 支持会话、凭据保险库、状态持久化、录制视频
- 提供针对 Electron 应用、Slack、探索性测试与云厂商的专项技能

## 四、可观测面板

面板独立于浏览器会话运行，监听 4848 端口，也可通过代理或转发地址访问，例如 `https://dashboard.agent-browser.localhost`。智能体应始终停留在面板同源地址下：会话标签页、状态与流量的转发均在内部完成，因此无需对外暴露会话端口。

## 五、执行流程

### 第 1 步 · 确认环境
- 动作：确认 `agent-browser` 已安装且可用（`agent-browser --version`）。
- 判据：命令返回版本号，无「未找到命令」类错误。
- 兜底：未安装时给出安装命令并等待确认；不具备安装条件则转入人工操作路径，不假装已执行。

### 第 2 步 · 载入工作流内容
- 动作：执行 `agent-browser skills get core`；需要完整命令参考与模板时加 `--full`。
- 判据：取到与所装版本一致的工作流正文。
- 兜底：命令不可用时，不凭本文件概述臆造命令，明确告知信息缺失。

### 第 3 步 · 判定任务类型并选技能
- 动作：网页类任务用 `core`；Electron 桌面应用、Slack、探索性测试、HAR 派生客户端、云沙箱分别载入对应专项技能。
- 判据：所选技能与任务目标一致，未把非网页任务硬套 `core` 流程。
- 产出：本次使用的技能名与选择理由。

### 第 4 步 · 执行浏览器交互
- 动作：先取无障碍树快照，用其中的 `@eN` 元素引用定位目标，再执行点击、填表、截图、取数等动作；导航、会话与状态按 `core` 的说明处理。
- 判据：所有动作均通过元素引用或明确选择器定位，无像素坐标硬编码。
- 兜底：定位失败时重取快照再试；仍未命中则记录该步失败原因，不静默跳过。

### 第 5 步 · 观察与收敛
- 动作：每步后读取快照或截图核对结果；需要观察会话状态与流量时使用 4848 端口的可观测面板。
- 判据：关键动作均有可核对的证据（快照或截图），非「执行即认为成功」。
- 产出：动作清单与对应证据，供复核。

## 六、边界与降级

- **本文件是发现桩**：只保证说明「去哪取内容」，不保证给出全部命令。凡涉及具体命令用法，一律以 `agent-browser skills get core` 返回的当前版本内容为准。
- **未安装命令行时**：不假装可执行；优先给出安装命令，其次改为人工在浏览器中按同样步骤操作。
- **版本不一致时**：以命令行返回的内容为准，本文件不随版本变化。
- **非网页目标**：Electron 应用、Slack、云浏览器不套用 `core` 流程，改载对应专项技能。
- **面板访问**：优先走同源代理地址，不直接对外暴露会话端口。
- **凭据处理**：需要登录态时使用工具自带的凭据保险库，不把账号口令写入技能文件或输出。

## 七、质量自检

- [ ] 所有浏览器动作均以 `@eN` 元素引用或明确选择器定位，无像素坐标硬编码
- [ ] 关键步骤后已读取快照或截图核对，非「执行即认为成功」
- [ ] 涉及具体命令用法时，内容取自 `agent-browser skills get core` 的当前版本，而非本文件概述
- [ ] 非网页任务已改用对应专项技能，未硬套 `core` 流程
- [ ] 无法执行时已说明原因与替代路径，未把「无法执行」写成「已执行」
- [ ] 无占位符残留

## 八、资源说明

- 本技能无附属资源文件；工作流正文由命令行在运行时提供。
- 许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。

## 九、搬运说明

本技能由上游源技能（GitHub 开源仓库）转换并中文化而来，核心流程与判据保持原样。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
