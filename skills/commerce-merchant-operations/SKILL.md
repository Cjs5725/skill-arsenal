---
name: commerce-merchant-operations
version: 1.0.0
display_name: "商家侧运营智能体"
display_name_en: "Commerce Merchant Operations"
description_zh: "参考实现中的商家侧智能体：五条流程、待生效变更与宿主审批、指标接地、分析委派、店铺记忆、组件，以及多卖家市场的规则。"
description_en: "The reference merchant agent, covering its flows, staged changes and host approval, metrics grounding, the analysis delegate, store memory, components, and marketplace rules."
category: productivity
author: "anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-merchant-operations"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  参考实现中的商家侧智能体：涵盖五条流程、待生效变更与宿主审批、指标接地、分析委派、
  店铺记忆、内置组件与多卖家市场规则。
  触发场景：为店铺、房源、订阅用户群或场地的运营方构建或审查智能体。
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-merchant-operations
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# 商家侧智能体

> **路径约定**：本文所有模块与文件均指**上游参考仓库**内的位置，**不随本包交付**，本包内不存在这些文件。
> 其中 `merchant_agent` 对应上游 `merchant-agent/core/merchant_agent/`，
> `merchant_agent_runtime` 对应 `merchant-agent/runtime-messages-api/merchant_agent_runtime/`，
> `merchant_agent_sdk` 对应 `merchant-agent/runtime-agent-sdk/merchant_agent_sdk/`，
> `commerce_common` 对应 `commerce-common/commerce_common/`。

## 一、它做什么

商家侧智能体在运营方的后台内、经由**单一** `MerchantBackend` 与运营方协作（该后端的实现位于上游 `merchant_agent` 包的 `backend.py`）。
它的五条流程就是上游 `merchant-agent/skills/` 下的技能：经营洞察、商品页管理、库存运营、定价与促销、营销活动。
`commerce_common` 中的机制是共享的；提示词、工具、门禁与执行器是它自己的，
且**每个工具结果都在 `MERCHANT_FENCE` 内返回**（围栏定义在上游 `merchant_agent` 包的 `fencing.py`）。

## 二、待生效变更契约

1. **每一次写入都是一个 `stage_*` 工具**（`stage_listing_update`、`stage_price_update`、`stage_inventory_action`、
   `stage_promotion`、`stage_campaign`）。每个都返回待生效记录与一条说明，发出一个 `change_update` 事件；
   且在 `stage_shows_preview` 打开时（**默认打开**，见上游 `merchant_agent` 包的 `config.py`），
   经由 `present_change_preview` 所用的运行器（`MerchantToolExecutor`，位于上游 `merchant_agent` 包的 `executor.py`）
   发出 `change_preview` 卡片。MCP 服务器下该开关是关的，因为它的执行器事件到不了运营方，所以托管智能体自行调用
   `present_change_preview`；该工具也能把更早的一次变更再展示一遍。
   **在 `apply_change` 之前，线上状态不被触碰**——`apply_change` 才真正执行平台写入。
2. **暂存只接受本会话内由工具返回过的商品页 id 与活动 id**，且内容编辑还需要一次 `get_listing` 读取；
   `apply_change` 与 `discard_change` 只接受由暂存或 `get_pending_changes` 返回过的变更 id
   （门禁见上游 `merchant_agent` 包的 `gates.py`）。**展示预览卡片不等于任何东西被批准。**
3. 上游 `merchant_agent` 包 `changes.py` 中的 `check_guardrails` 在变更被暂存时运行（`ChangeLedger.stage`，或你的后端等价物），
   并在 `check_apply_change`（同包 `gates.py`）中按**生效时**所依据的配置再运行一次。
   限额为同包 `config.py` 中的 `max_items_per_change`、`max_price_delta_pct`、`max_promotion_discount_pct`、
   `max_restock_quantity`、`max_campaign_budget` 与 `max_listing_field_chars`；**其默认值是演示用的取值**。
4. `protected_fields` **永远不可被暂存**；`price_bearing_fields` 是价格上限所读的字段；
   `listing_update_blocked_fields` 不得随自由格式的商品页更新一起带出。
   以别的名义定价的垂直领域（房晚价、月费、阶梯价）应当**追加**到这些元组上，**绝不替换**它们。
5. `require_host_approval` 默认为 `True`：`apply_change` 只对出现在 `MerchantSessionState.approved_change_ids` 中的 id 成功，
   而该集合**只有宿主代码会写**。上游仓库中的三个入口是：门户的 `/changes/{change_id}/apply` 路由
   （上游 `examples/demo_common` 目录中的 `merchant.py`）、`MerchantToolset.host_approve`
   （上游 `merchant_agent_sdk` 包中的 `merchant_tools.py`，由上游 `merchant-agent/runtime-agent-sdk` 下的 `main.py` 逐变更提示）、
   以及托管清单中 `apply_change` 上的 `always_ask`；在托管形态下，MCP 服务器的配置把 `require_host_approval` 设为 `False`
   （其 `default_config` 即如此；你自带的配置也必须如此，否则每一次应用都会被挂住）。
   **在对话里打一句"批准"不设置任何标记。**
6. `require_host_approval` 与 `approval_surface` 会渲染进静态提示词与拒绝话术，因此它们是**按部署**设定的，
   改动其中任何一个都等于重新部署（参见提示词缓存技能）。`approval_surface` 里要写**真实的**审批入口。
7. 系统不支持的变更类型会抛出 `ChangeNotApplicable`（上游 `merchant_agent` 包 `changes.py`），由执行器转达；工具仍然保持注册。
   **已应用与已丢弃的变更都可继续查询，构成审计轨迹**，每条都盖上 `MerchantSessionContext.operator` 中的运营方标识，
   生产宿主从认证信息中推导出它。

## 三、接地与跟办

- 涉及业绩的问题会**强制** `get_business_snapshot`；一次带"应用"措辞、但本会话什么都没暂存的变更请求会**强制** `get_pending_changes`
  （接地规则在上游 `merchant_agent` 包 `grounding.py` 的 `GROUNDING_RULES`；词表与开关在同包 `config.py`，
  同样是**追加而不替换**）。
- 命中 `change_requested` 却以纯文本收尾、既没有尝试 `stage_*` 也没有以 `present_suggestions` 收口的那一轮，
  会收到一次 `STAGING_FOLLOWTHROUGH_REMINDER`，以用户消息形式注入
  （门禁在上游 `merchant_agent` 包 `gates.py`；在 `merchant_agent_runtime` 包的 `orchestrator.py` 与
  `merchant_agent_sdk` 包的 `agent.py` 中施加）；**该提醒文本不参与记忆抽取**。
- `present_metrics` 把快照、某条查询出的序列、某个活动或某次已记录分析中的每一项**对接上**，其余丢弃并附说明
  （见上游 `merchant_agent` 包 `enrichment.py` 的 `resolve_metrics`），因此**卡片永远不会携带模型自撰的数字**。

## 四、分析委派

- `enable_analysis`（**默认关闭**）会注册 `run_analysis`，这是一个由 `build_analysis_delegate` 构建的 `DelegateExtension`
  （位于上游 `merchant_agent_runtime` 包的 `analysis.py`）。该委派的工具包括一个提交工具、一个进度工具、
  `ANALYSIS_READ_TOOLS`（上游 `merchant_agent` 包 `analysis.py`），以及在后端实现 `MerchantBackend.execute_analysis_query`
  时追加的一个查询工具（此时 `analysis_sql_only` 会关掉逐序列读取）。它**不持有任何暂存类工具**；
  其结果记录进 `seen_analyses`，并渲染为它自己的指标卡片。
- `check_analysis_sql` 只放行**一条不带注释的 SELECT**，其余一律拒绝，随后才交给后端执行；
  只读角色与商家范围划分由后端负责；`analysis_query_timeout_s` 与 `cap_analysis_table`
  （`max_analysis_rows`、`max_analysis_table_chars`）约束单次查询，
  `analysis_timeout_s`、`max_analysis_iterations` 与 `max_delegate_calls_per_turn` 约束整次运行。
- `analysis_use_code_execution` 会挂载托管沙箱，且**仅在 Anthropic API 上可用**（包括托管在 Anthropic 上的 Foundry 部署）；
  查询方式到处可用（上游 `docs` 目录中的 `deployment.md`）。在 Agent SDK 上，同一契约体现为一个子智能体，
  其工具恰好就是那批只读工具（`build_analysis_agent`，上游 `merchant_agent_sdk` 包 `agent.py`）。
- **定时摘要**是同一个智能体的一次无头轮次（`run_morning_digest.py`，位于上游
  `merchant-agent/managed-agents/scheduled-digest/` 目录）。

## 五、记忆与组件

- 记忆以 `merchant_id` 为键（`memory_subject`，上游 `merchant_agent` 包 `executor.py`）；
  同包 `memory.py` 中的抽取提示词**只接纳运营方关于"如何经营"的陈述**，排除商品页、评论、买家消息与指标中的任何内容，
  以及与可识别顾客有关的任何内容。写入过滤器、保留期、删除、清空与 `enable_memory` 属共享规则（参见信任与安全技能）。
- 内置组件（上游 `merchant_agent` 包 `enrichment.py`）为 `present_metrics`、`present_digest`、`present_change_preview`
  与 `present_suggestions`；在宿主审批开启时，提示词会说明**没有任何快捷选项会批准或应用变更**。
  垂直领域可经扩展机制自行追加（示例中的 `present_occupancy_calendar`、`present_plan_mix`、`present_event_pacing`）
  （参见界面与工具技能）。

## 六、多卖家市场

- 多个卖家的内容走**同一道围栏**；**没有按卖家分标签这回事**，也没有哪个卖家的文本能逃出围栏。
  在购物侧部署中，卖家是搜索的一个维度（`SearchFilters.attributes`）并由组件展示；
  当平台条款与卖家条款不同时，`search_policies` 的结果要**写明所依据的是谁家的条款**。
- **来源与上限都是按会话的**，所以一个会话只能针对它自己的工具返回过的商品页暂存，别的不行。
- 买家与卖家的消息以**围栏材料**形式到达模型；**一条声称"变更已获批准"的消息不设置任何标记**。
- 记忆主体是运营方自己的生意，以其 `merchant_id` 为键；购物者的事实则以购物者为键。

## 执行流程

1. **确认部署形态与审批入口**。先判定当前是门户、MCP 服务器还是 Agent SDK 形态，并据此确认 `require_host_approval` 与
   `approval_surface` 的取值。判据：能指出真实的审批入口；若为 MCP 形态，确认配置中已把 `require_host_approval` 设为 `False`
   （否则每一次应用都会被挂住）。
2. **确认五条流程齐备**。核对经营洞察、商品页管理、库存运营、定价与促销、营销活动这五条流程是否都在。
   判据：任意一条运营方诉求都能被路由到其中一条流程，且该流程有对应的 `stage_*` 工具。
3. **核对暂存—应用链路**。沿 `stage_*` → `change_update` → `present_change_preview` → `apply_change` 走一遍。
   判据：① 暂存只接受本会话工具返回过的 id；② 内容编辑额外要求一次 `get_listing` 读取；
   ③ **在 `apply_change` 之前线上状态不被触碰**；④ 展示预览卡片不产生任何批准标记。
4. **核对护栏与保护字段**。确认 `check_guardrails` 在暂存时与按生效配置应用时**各运行一次**；
   核对六个限额字段与 `protected_fields`／`price_bearing_fields`／`listing_update_blocked_fields` 的取值。
   判据：越限的变更被拦下；垂直领域的定价字段是**追加**进元组而非替换。
5. **核对接地与跟办**。确认业绩问题强制 `get_business_snapshot`、带应用措辞的请求强制 `get_pending_changes`；
   确认"未暂存却以纯文本收尾"的那一轮会收到一次跟办提醒，且该提醒不进入记忆。
   判据：能逐个指出触发条件与对应规则名。
6. **核对指标与分析的接地**。确认 `present_metrics` 的每一项都对接自快照／序列／活动／已记录分析，模型自撰的数字会被丢弃；
   若启用分析，确认 `check_analysis_sql` 只放行单条无注释 SELECT，且超时与体量上限均已生效。
   判据：抽一张卡片，能逐一说明每个数字的来源。
7. **核对记忆边界**。确认记忆以 `merchant_id` 为键，且抽取提示词排除了商品页、评论、买家消息、指标与可识别顾客的内容；
   写入过滤、保留、删除与清空按共享规则执行。
   判据：构造一条"记忆里出现买家信息"的情形，应被拒写且不对运营方报错。
8. **登记审计与来源**。确认已应用与已丢弃的变更都可查询，且每条都带运营方标识。
   判据：能按运营方回溯任一变更的完整轨迹。

## 边界与降级

- **依赖真实后端**：本技能描述的是上游参考仓库的智能体行为与配置；**本包不含这些文件，也不含可运行环境或真实后台**。
  实际部署与改动请回到上游仓库操作。此时本技能降级为**实现与审查清单**，逐条核对即可，交付完整性不下降。
- **认证缺失时的审批降级**：无法从认证信息推导运营方时，**不得**放宽 `require_host_approval` 或收窄 `approval_surface` 来"让流程走通"；
  应如实标注该部署不具备可用的审批入口，并阻塞应用动作。
- **无沙箱环境时**：`analysis_use_code_execution` 不可用，改用查询方式；若两者都不可用，明确标注"分析能力未启用"，
  不得用模型推测的数字冒充分析结果。
- **护栏默认值是演示值**：直接沿用默认限额交付属**未完成**配置，须按真实业务量核定后再上线，并在交付说明中写明核定依据。
- **不支持的变更类型**：由 `ChangeNotApplicable` 转达，工具保持注册，不算崩溃；**不得**为绕开它而放开暂存门禁。
- **禁止**：跳过 `apply_change` 直接写线上状态；把"对话里说批准"当作审批；让工具结果逃出围栏；
  让模型自撰的数字进入指标卡片。
- **信息不足时**：明确指出缺哪一项（无后端、无认证、无沙箱），只对可判定部分下结论，不臆测数值。

## 质量自检

- [ ] 部署形态与 `require_host_approval`／`approval_surface` 已核对，且 `approval_surface` 写的是真实审批入口。
- [ ] 五条流程齐备，每条流程都有对应的 `stage_*` 工具。
- [ ] 暂存—应用链路完整：来源校验、内容编辑的额读取、`apply_change` 前线上状态不变、预览卡片不产生批准标记。
- [ ] `check_guardrails` 在暂存时与应用时各运行一次；六个限额字段均已按真实业务核定（不再是演示默认值）。
- [ ] `protected_fields`、`price_bearing_fields`、`listing_update_blocked_fields` 已核对，垂直领域字段为追加而非替换。
- [ ] 接地规则与跟办提醒均已确认，且跟办提醒文本不参与记忆抽取。
- [ ] `present_metrics` 每一项都可回溯到来源；`run_analysis` 不持有暂存类工具；SQL 门禁只放行单条无注释 SELECT。
- [ ] 记忆以 `merchant_id` 为键，抽取提示词已排除第三方内容与可识别顾客信息。
- [ ] 每个工具结果都在 `MERCHANT_FENCE` 内返回；已应用与已丢弃变更均可按运营方回溯。
- [ ] 无占位符、无待填项；所有模块与文件引用均指向上游仓库且已被开头的路径约定覆盖。

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样，正文已中文化。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
