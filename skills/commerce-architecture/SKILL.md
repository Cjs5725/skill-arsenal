---
name: commerce-architecture
version: 1.0.0
display_name: "Commerce 智能体架构"
display_name_en: "Commerce Architecture"
description_zh: "两种角色的参考 commerce 智能体是如何组织的：主循环、每条规则归属于哪一层、技能、后端接口、委托调用与模型字段。"
description_en: "How the reference commerce agents of either role are structured, covering the loop, where each rule lives, skills, the backend interface, delegates, and model fields."
category: productivity
author: "anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-architecture"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  说明两种角色的参考 commerce 智能体是如何组织的：主循环、每条规则归属于哪一层、技能（skills）、
  后端接口、委托调用（delegates）与模型字段。
  在**设计或评审**购物端／商家端智能体的结构时加载本技能。
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-architecture
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Commerce 智能体架构（Commerce agent architecture）

> **路径约定**：本文所有模块与文件均指**上游参考仓库**内的位置，**不随本包交付**，本包内不存在这些文件。
> 其中 `commerce_common` 对应上游 `commerce-common/commerce_common/`，`shopping_agent` 对应
> `shopping-agent/core/shopping_agent/`，`merchant_agent` 对应 `merchant-agent/core/merchant_agent/`；
> 两个运行时分别是 `shopping-agent/runtime-messages-api/shopping_agent_runtime/` 与
> `merchant-agent/runtime-messages-api/merchant_agent_runtime/`。
> 下文凡写作「X 包的 Y」者，均指上游仓库中该模块下的同名文件。

## 只有一条主循环

- **一个模型独占对话**。一个回合是 `ShoppingAgent.stream_turn` 或 `MerchantAgent.stream_turn`
  （分别位于两个运行时包中的 `orchestrator.py`）：
  模型读缓存的提示词、调用工具（同一回合内的调用**并发**执行），并以正文加呈现类调用收尾。
  **没有路由器、分类器，也没有交接（hand-off）。**
- 所有路径上的每一次调用都经由角色执行器（`shopping_agent` 包的 `executor.py` 中的 `ShoppingToolExecutor`、
  `merchant_agent` 包的 `executor.py` 中的 `MerchantToolExecutor`），它们基于 `commerce_common` 包
  `execution.py` 的 `BaseToolExecutor`。
  Messages API 运行时、Agent SDK 工具集与 MCP 服务器调用的是同一个 `execute`，而它**从不抛异常**；
  达到 `max_tool_iterations` 轮（`commerce_common` 包 `config.py`）后，运行时强制走一轮不带工具的回合。

## 一条规则该住在哪一层

| 适用的规则 | 归属于 | 参考实现 |
|---|---|---|
| 某次调用的参数正在被填写时适用 | 那个工具自身的 description | 各角色 `tools` 目录中 `registry.py` 的 `build_tools` |
| 大多数回合都适用：购物车与结算、暂存写入契约、呈现语法、工具顺序、信任规则 | **静态提示词** | 各角色 `prompt.py` 中的 `build_static_system` |
| 仅少数需要多步流程的请求适用 | **技能（skill）**，按需加载 | `shopping-agent/skills/`、`merchant-agent/skills/` |

核心旅程在**多数对话**中都要用到的规则，就往下沉一层。**本表是关于分层方式的唯一表述。**

## 技能（Skills）

- 一个技能就是一个含 `SKILL.md` 的目录：frontmatter 里的 `name` 与 `description`，然后是正文
  （`commerce_common` 包 `skills.py` 中的 `parse_skill_md`）。**description 只命名请求类别，不携带示例话术。**
- 静态提示词只携带索引（`SkillRegistry.index_block`，按名称排序），`load_skill` 返回某一个正文
  （`commerce_common` 包 `execution.py` 中的 `_load_skill`）。在 Agent SDK 上，`ensure_project_skills` 把同一批目录链接进
  `.claude/skills/`，并由 `SKILL_TOOL_ADAPTER` 把模型指向 SDK 的 `Skill` 工具（`commerce_common` 包 `agent_sdk.py`）；
  托管清单则在 `agent.yaml` 的 `skills[]` 下列出这些目录。

## 后端接口

一个部署为每种角色实现**一个抽象类**；除此之外没有任何东西能触达它的系统。

- `StorefrontBackend`（`shopping_agent` 包的 `backend.py`）：11 个抽象方法——商品目录 2、购物车 4、偏好 1、
  订单 2、条款 1、履约 1；`get_account_context`、`get_disclosure` 与 `checkout_handoff` 有默认实现。
  **没有任何方法会下单或动钱**；`checkout_handoff` 指明支付发生在何处（一个托管结算 URL，或每个卖家各一个），由宿主渲染。
- `MerchantBackend`（`merchant_agent` 包的 `backend.py`）：16 个抽象方法——读取类 8 个（业绩 3、目录 2、
  库存与订单健康 2、定价 1）与变更生命周期 8 个（五个 `stage_*`、`get_pending_changes`、
  `apply_change`、`discard_change`）；`execute_analysis_query`、`get_analysis_schema`、`get_merchant_context` 有默认实现。
- 按尺码、颜色或档位售卖的产品或商品是一个带 `options` 的**家族记录**，其各个变体分别是带
  `option_values` 与 `variant_of` 的记录；购物车与价格／补货写入接收**变体**的 id，
  而各道关卡持有的则是**家族**的 id。上游 `docs` 目录的 `backends.md` 给出常见目录模型的映射，
  以及平台无法提供的数字应当返回什么。
- **资格、定价、库存与数量规则在后端强制执行**；各道关卡只检查来源可信度与上限（见信任与安全技能）。
  后端返回的一切，在模型读到之前都会被围栏（fenced）处理。
- **尚未接通的系统**表现为一个会失败的方法（商家端方法从 `merchant_agent` 包 `changes.py` 抛 `ChangeNotApplicable`）；
  工具仍保持注册，因此提示词的字节数不变。**业务里根本不存在的系统**则表现为「缺席」：该角色配置上的某个
  `enable_*` 开关被关闭，于是三条路径上的对应工具（`absent_tools()`）、提示词行与接地规则一并移除，
  执行器也会拒绝这些名字；需要它的技能被停放在 `skills/_staged/` 下，该部署的字节数随之固定。
  `NotOffered`（`shopping_agent` 包 `backend.py`）是更窄的信号：系统本身开着，但某一件商品或某个卖家是这家店不服务的。
- `ShoppingAgent` / `MerchantAgent` 上的 `executor_class=`、SDK 工具集以及 MCP 服务器的 `build_server`，
  都接受该角色执行器的一个子类，供部署方定制自己的 `domain_error` 映射或结果措辞。

## 委托调用（Delegates）

第二次模型调用只有一种形态：`DelegateExtension`（`commerce_common` 包 `delegation.py`）。它收到一份简报
与 `DelegationContext` 中的句柄，**永远拿不到对话或执行器**；它返回一个按 `result_model` 校验过的结果；
它**不能**写入、呈现或再调用委托；`commerce_common` 包 `execution.py` 中的 `_run_delegate` 把它的每回合调用数
限制在 `max_delegate_calls_per_turn`。`MerchantAgent` 接受 `extra_delegates`，其内置实例是 `run_analysis`
（见商家侧运营技能）。`ShoppingAgent` 不注册任何委托。

## 模型字段

`model` 跑回合循环，`memory_model` 做回合后的抽取（`commerce_common` 包 `config.py` 中的 `BaseAgentConfig`）；
`analysis_model` 跑委托，`None` 表示沿用 `model`（`merchant_agent` 包 `config.py` 中的 `MerchantAgentConfig`）。
SDK 运行时把 `config.model` 复制进 options；清单里则设 `model:`。**这些取值请用你自己的评测来选。**

## 不要做

- 不要按请求改变 `tools[]` 或静态提示词（见提示词缓存技能）。
- 不要把「多数回合适用的规则」放进技能，也不要把「单一工具的规则」放进提示词。
- 不要只用提示词文字来执行上限或权限；它属于执行器或后端。
- 不要让模型**自己撰写**价格、数字或条款；组件由服务器记录拼接而成（见界面与工具技能）。
- 不要把领域工具加进核心包；某个垂类应通过 `PresentationExtension` 增加 UI，其余留在它自己的代码里。

## 执行流程

1. **确认评审对象**。明确当前是「设计」还是「评审」，以及角色是购物端还是商家端。判据：对象角色与阶段明确。
2. **核对主循环假设**。确认仍是「一个模型独占对话、单回合内工具并发、无路由与交接」。判据：设计中不存在路由器、分类器或交接环节；存在则视为偏离并指出。
3. **为每条规则定位分层**。逐条对照「一条规则该住在哪一层」表：多数回合适用 → 静态提示词；单次调用的参数 → 该工具 description；少数请求的多步流程 → 技能。判据：每条规则都落到三层之一；落在技能里的「多数回合规则」与落在提示词里的「单工具规则」均已挑出。
4. **核对技能契约**。检查每个 `SKILL.md` 的 frontmatter（`name`、`description`）与正文，且 description **只命名请求类别、不含示例话术**。判据：静态提示词只携带索引，正文按需加载。
5. **核对后端接口边界**。逐项确认：每种角色仅一个抽象类；无方法下单或动钱；资格／定价／库存／数量在后端强制；未接通系统用「会失败的方法 + 工具保持注册」，完全不存在的系统用 `enable_* 关闭 → absent_tools()` 三路径一并移除，需它的技能停放在 `skills/_staged/`。判据：无绕过后端的直连路径。
6. **核对委托约束**。确认委托收不到对话与执行器、不能写入／呈现／再委托，且每回合调用数受 `max_delegate_calls_per_turn` 限制。判据：四条约束全部满足。
7. **核对模型字段**。确认 `model` ／ `memory_model` ／ `analysis_model` 的取值为评测所选，且 `analysis_model=None` 时回退到 `model`。判据：取值有评测依据，未凭默认值拍板。
8. **过「不要做」清单**。逐条检查五项禁令。判据：五项均无违反；有违反则写明具体位置与改法。

## 边界与降级

- **参考仓库不可访问**：仅依据本技能描述的表与约束做评审，并在结论中标注「未做代码级核对」；不臆造代码细节。
- **角色未指明**：先确认是购物端还是商家端；两者抽象方法数（11 / 16）与执行器类名均不同，不得混用。
- **系统尚未接通 vs 根本不存在**：二者处置不同——前者保留工具注册并让方法抛错，后者经 `enable_*` 三路径一并移除并把相关技能停放；不得互相套用。
- **规则归属存疑**：以「核心旅程在多数对话中是否用到」为判据；仍不决时说明理由并给出两种落位的影响，不静默择一。
- **后端能否提供某数字不明**：查上游 `docs` 目录 `backends.md` 的映射；仍不明确时要求后端返回「无法提供」而非编造数值。
- **发现绕过后端的实现**（资格／定价／库存／数量在前端或提示词中强制）：直接判为硬问题并指出应移入后端或执行器。
- **无网络或无法读取仓库**：输出分层核对表与逐条结论，标注未做的代码级验证，交付完整性以核对表为准。

## 质量自检

- [ ] 已确认评审对象（设计／评审）与角色（购物端／商家端）。
- [ ] 主循环无路由器、分类器、交接环节。
- [ ] 每条规则都落在三层之一，且无「多数回合规则放进技能」或「单工具规则放进提示词」。
- [ ] 技能 description 只命名请求类别，不含示例话术；静态提示词只携带索引。
- [ ] 每种角色仅一个抽象类；无方法下单或动钱。
- [ ] 资格、定价、库存、数量在后端强制，未在提示词文字中强制。
- [ ] 「未接通」与「不存在」两种系统状态按各自规则处置，未互相套用。
- [ ] 委托满足四条约束（收不到对话／执行器、不写入／不呈现／不再委托、调用数受限）。
- [ ] 模型字段取值有评测依据；`analysis_model=None` 时回退 `model`。
- [ ] 「不要做」五项禁令均无违反，或已写明具体位置与改法。
- [ ] 无占位符、无待填项；所有模块与文件引用均指向上游仓库且已被开头的路径约定覆盖。

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样，正文已中文化。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
