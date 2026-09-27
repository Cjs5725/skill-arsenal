---
name: commerce-prompt-caching
version: 1.0.0
display_name: "提示词缓存架构（商务智能体参考实现）"
display_name_en: "Commerce Prompt Caching"
description_zh: "参考实现中「缓存稳定的请求组装」做法：静态系统块与每请求上下文的切分、固定工具清单、滚动会话断点，以及哪些配置字段属于提示词字节、如何验证缓存命中。"
description_en: "The reference agents' cache-stable request assembly, covering the static system and per-request context split, the fixed tool list, the rolling conversation breakpoint, which config fields are prompt bytes, and verification."
category: productivity
author: "anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-prompt-caching"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  参考实现中「缓存稳定的请求组装」做法：拆解静态系统块与每请求上下文，固定工具清单与顺序，
  布置滚动会话断点，并说明哪些配置字段属于提示词字节、以及如何验证缓存命中。
  触发场景：编写或审查商务智能体的请求组装；第二轮起缓存读取为 0；需要判断某一轮的时延或成本归因。
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-prompt-caching
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# 缓存稳定的请求组装

> **路径约定**：本文所有形如「模块目录／文件」的路径，均指**上游参考仓库**内的位置，**不随本包交付**，本包内不存在这些文件。
> 其中 `commerce_common` 对应上游 `commerce-common/commerce_common/`，`shopping_agent` 对应
> `shopping-agent/core/shopping_agent/`，`merchant_agent` 对应 `merchant-agent/core/merchant_agent/`。
> 读到本文提到的 `.py` 文件时，请回到上游仓库查阅。

## 一、三处断点

一次请求可缓存的前缀依次是 `tools`、`system`，然后是消息；一个断点结束一段跨度，下一次调用即从该处读回。
参考实现共放三处断点，全部出自上游 `commerce_common` 包中的 `prompt_assembly.py`：

1. **最后一个工具**：`with_tool_cache_control(tools)`。
2. **静态系统文本**：`build_system_blocks(static, context)` 为它打标记，并**不打标记地**追加上下文块。
3. **最新一条已持久化的消息**：`build_request_messages(messages, rolling_breakpoint=...)` **仅在本次出站请求上**
   标记最后一个已持久化的块；下一次调用即可从缓存读回此前的轮次（含检索载荷）。

每个请求各自变化的内容一律放进**上下文块**，由该角色的 `build_dynamic_context(...)` 每轮渲染一次。
若把它们放进静态块或工具清单，这些字节会在**每一次请求**上打断系统跨度或工具跨度；
放进上下文块，代价仅是「购物车／页面／事实发生变化的那一轮」重读一次会话，而滚动标记从该轮的下一轮起继续生效。
时钟按**小时**渲染（`context_clock`），所以分钟级变化不移动任何字节。

## 二、切分的落地方式

- 各角色 `prompt.py` 中的 `build_static_system(config, skills)` 渲染身份、最大轮数规则、围栏提示与技能索引，
  在**一次部署的整个生命周期内字节不变**。
- 同一模块中的 `build_dynamic_context(...)` 在角色的数据围栏内渲染每请求内容：购物侧取偏好、记忆事实、
  购物车、页面、账户块与时间；商家侧取店铺上下文、记忆事实与时间。后端上下文块另有自己的体量上限。
- `ShoppingAgent.__init__` 与 `MerchantAgent.__init__`（各自角色 `runtime-messages-api` 下的 `orchestrator.py`）
  **每进程只构建一次** `_static_system` 与 `_tools`；`stream_turn` 每轮渲染一次上下文块，
  每次模型调用各调一次 `build_request_messages`。
- 各角色 `tools` 目录下 `registry.py` 中的 `build_tools` 按**固定顺序**输出内置工具
  （商家构建器在启用时随后追加 `run_analysis`），`load_skill` 的枚举**排序后**输出，
  再接按给定顺序的扩展，最后是启用时的 `web_search`；**每个已注册工具都在每次请求上随行**，
  由执行器在到达时判定该调用能否被服务。
- Agent SDK 运行时传入同一份静态文本（外加 `SKILL_TOOL_ADAPTER`）与同一批契约，由 SDK 负责缓存；
  托管清单把该文本作为 `system.md` 交付，由上游仓库 `scripts` 目录中的 `check.py` 与构建器输出比对。

## 三、滚动标记被跳过的两种情形

有两轮不带标记：

- **裸的首次调用**（对话中仅一条消息）：一次性会话会「只付写、不获读」，而第二次调用的标记本就覆盖首条消息。
- **`tool_choice` 非 `auto` 的轮次**（强制接地的首轮迭代、强制文本的末轮）：`tool_choice` 参与消息跨度的键，
  因此在强制轮下写入的条目，无法被其后的自动轮读回；系统跨度与工具跨度仍然命中。

两处逻辑都在 `build_request_messages` 与各循环的 `rolling_breakpoint=` 参数中；
`rolling_conversation_cache` 可为调试关闭该标记。

## 四、会话被压缩时

当某一轮最后一次调用的用量达到或超过 `compact_history_above_tokens`（默认取平台自身的工具结果清理阈值，
即窗口的十分之一），该轮以 `compact_history` 收尾——它位于上游 `commerce_common` 包的 `turn.py`，
把已存会话中最旧的工具结果替换成一行标记，直到会话缩减为原先体量的一半。
下一轮的首个回合会重写一次消息跨度，其后回合读取更短的那一份；
`turn_complete.results_cleared` 用于告知「会把转写追加进自身存储」的宿主去重写。
系统跨度、工具跨度、消息与写入门禁均不受影响；来源信息保存在会话状态上。

## 五、属于提示词字节的配置字段

各配置中标注 `(prompt)` 的字段，加上商家工具构建器会读取的 `enable_analysis` 与 `max_items_per_change`，
都会渲染进静态文本或工具清单；**改动其中之一即等于重新部署，并在下一次请求上造成未命中**：

| 配置类 | 属于提示词字节的字段 |
|---|---|
| `BaseAgentConfig`（基础配置模块） | `brand_name`、`assistant_name`、`brand_voice`、`enable_web_search` |
| `ShoppingAgentConfig`（购物侧配置模块） | `domain_search_notes`、`enable_disclosures`，以及系统开关 `enable_cart`、`enable_orders`、`enable_policies`、`enable_fulfillment` |
| `MerchantAgentConfig`（商家侧配置模块） | `enable_analysis`、`require_host_approval`、`approval_surface`、`stage_shows_preview`，以及系统开关 `enable_listing_edits`、`enable_inventory`、`enable_pricing`、`enable_campaigns`；`max_items_per_change` 与 `max_search_results` 决定工具 schema 上的 `maxItems` 与 `maximum` |

技能、呈现扩展与委派对象同样是提示词字节。
门禁词表、护栏限额、记忆设置、时延旋钮（`eager_tool_dispatch`、`rolling_conversation_cache`、
`eager_partial_frames`、`close_on_presentation`）、购物车上限与 `compact_history_above_tokens` **则不是**；
上游 `tests` 目录下的 `test_role_registries.py` 对每个角色逐一断言了这一点。

## 六、什么会打破缓存命中

- 静态块或工具清单里出现**任何每请求变化**的内容：一个名称、购物车数量、页面、时钟、请求 id。
  其中前四项由上下文块承接；请求 id **哪里都不该放**。
- 把集合或字典**未排序**地迭代进提示词文本或 schema。
- **每请求**决定 `tools[]` 的成员（每请求读一次开关，而不是在构造时读一次）。
- 在轮次**内部**重建静态文本或工具清单，而不是在构造函数里做。
- 把滚动标记**持久化**进已存会话——那样会话会每轮多出一个标记。
- 在运行中的部署上切换某个 `(prompt)` 字段、技能或扩展；每一种都等于重新部署。
- **每请求**选择提示词变体，而不是每部署选择。
- 前缀短于模型的最小可缓存长度——那什么都不会写入。
- 强制 `tool_choice`（首轮接地气、末轮 `none`）只影响消息跨度；循环在这两处已跳过标记。

## 七、如何验证

- `turn_complete` 携带 `usage`（上游 `commerce_common` 包 `turn.py` 中的 `usage_totals`，为该轮各次调用之和）
  与 `elapsed_ms`；每次调用另各记一行日志，带同样计数器与自身耗时（`log_model_call`，
  位于购物侧与商家侧 runtime 的 `orchestrator`）。
  **一场对话的第二轮缓存读取为 0，即意味着前缀发生了变化。**
  值得按配置版本逐版记录的计数：缓存读取占输入的比例、`elapsed_ms`、每轮回合数、以及按门禁分组的
  被拦 `tool_result` 事件。
- 上游 `tests` 目录下的 `test_role_registries.py` 会把每个角色的提示词与工具各构建两次并逐字节比对，
  检查缓存标记，并验证非提示词设置改不动任何字节；`commerce-common` 的测试目录覆盖块构建器、上下文时钟、
  滚动标记与跳过情形；另一份轮次循环测试把两个循环钉在同一套块、标记与干净历史上。一次部署的测试要带同样这三项检查。
- 在已部署环境中，跑一场**三轮**对话并读第二、三轮的 `usage`；代理层或重试层若重写请求，只会在这一处暴露、别处看不出来。

## 执行流程

1. **确认路径映射与角色**。先看清当前是购物侧还是商家侧智能体，并按本文开头的路径约定把模块目录对应到上游位置。
   判据：能说清要改的入口是哪个角色的 `prompt.py` 与 `orchestrator.py`。
2. **定位三处断点**。在上游 `commerce_common` 包的 `prompt_assembly.py` 中确认三处断点是否齐备：
   最后一个工具、静态系统文本、最新一条已持久化消息。判据：缺任何一处，缓存跨度都会在错误的位置断开。
3. **核静态前缀的稳定性**。检查 `_static_system` 与 `_tools` 是否**只在构造函数里构建一次**，
   且不掺入任何每请求内容。判据：把同一部署的静态文本与工具清单各构建两次，应逐字节相同。
4. **核每请求内容的归属**。把偏好、记忆事实、购物车、页面、账户块、时间等逐项核对，确认**全部落在上下文块内**。
   判据：静态块与工具清单中找不到随请求变化的字段。
5. **核对配置字段清单**。对照第五节表格，逐个确认哪些字段属于提示词字节。判据：凡属提示词字节的字段，
   一旦改动即按「重新部署」处理，不按热更新处理。
6. **跑验证**。执行一场三轮对话，读第二、三轮的 `usage`。判据：第二轮缓存读取应大于 0；
   若为 0，回到第六节逐条比对是哪种情形打破了前缀。
7. **记录基线**。把缓存读取占输入的比例、`elapsed_ms`、每轮回合数与按门禁分组的被拦事件，按配置版本登记。
   判据：下一次改动前后有可比对的同口径基线。

## 边界与降级

- **不可执行的场景**：本文涉及的是上游参考仓库的代码结构与部署行为，**本包不含这些文件、也不含可运行环境**。
  若需要实际改代码，请回到上游仓库操作；此时本文降级为**审查清单**使用，按执行流程逐条核对与判定，交付完整性不下降。
- **无部署环境的验证降级**：拿不到运行中的智能体时，改为**静态核对**——把静态文本与工具清单各构建两次比对字节，
  并逐项核对每请求内容是否越界。判据：字节一致且无越界字段，可判定前缀稳定；无法取得 `usage` 时应标注为「未实测」。
- **缓存读取为 0 时的排查顺序**：先看是否每请求在读 `tools[]` 成员开关，再看是否有集合／字典未排序迭代进文本或 schema，
  然后看是否在轮内重建了静态文本，最后看是否切换过某个 `(prompt)` 字段。
- **强制 `tool_choice` 下的预期行为**：消息跨度不命中属**设计内行为**，不计为缺陷；系统跨度与工具跨度仍应命中。
- **前缀过短的情形**：低于模型最小可缓存长度时写入为空，属模型侧限制，不应作为实现缺陷上报。
- **禁止**：把每请求内容放进静态块或工具清单以「顺手取到」；把滚动标记持久化进已存会话；
  在运行中的部署上切换提示词字段、技能或扩展。以上三种都会静默地持续破坏缓存命中。
- **信息不足时**：明确指出缺哪一项（如拿不到 `usage`、读不到上游某个文件），按已有信息给出可判定部分，不臆测数值。

## 质量自检

- [ ] 三处断点齐备，且各自的位置与作用能一一说明（最后一个工具／静态系统文本／最新一条已持久化消息）。
- [ ] 静态前缀稳定：静态文本与工具清单各构建两次，逐字节一致；且仅在构造函数中构建。
- [ ] 无越界：偏好、记忆事实、购物车、页面、账户块、时间等每请求内容全部位于上下文块内。
- [ ] 提示词字节清单已核对：`(prompt)` 字段、`enable_analysis`、`max_items_per_change` 均已识别，
  且改动按「重新部署」处理。
- [ ] 非提示词项未被误当作提示词字节：门禁词表、护栏限额、记忆设置、时延旋钮、购物车上限、
  `compact_history_above_tokens` 均不在静态文本与工具清单中。
- [ ] 验证已执行或有明确降级说明：给出第二、三轮的缓存读取情况，或标注「未实测」及原因。
- [ ] 无占位符、无待填项；文中的模块与文件引用均指向上游仓库，且已按开头路径约定声明。

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样，正文已中文化。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
