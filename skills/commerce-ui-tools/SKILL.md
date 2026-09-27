---
name: commerce-ui-tools
version: 1.0.0
display_name: "呈现工具与前端契约"
display_name_en: "Commerce UI Tools"
description_zh: "参考实现的呈现工具契约：服务端补全、建议快捷选项、事件流、渐进式渲染、两个角色的内置组件，以及如何新增一个垂直领域组件。"
description_en: "The reference presentation-tool contract, covering server-side enrichment, suggestion chips, the event stream, progressive rendering, both roles' built-in components, and adding a vertical component."
category: productivity
author: "anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-ui-tools"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  参考实现的呈现工具契约：涵盖服务端补全、建议快捷选项、事件流、渐进式渲染、两个角色的内置组件，
  以及如何新增一个垂直领域组件。
  触发场景：构建或审查商务智能体的输出如何抵达前端。
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-ui-tools
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# 呈现工具

> **路径约定**：本文所有模块与文件均指**上游参考仓库**内的位置，**不随本包交付**，本包内不存在这些文件。
> 其中 `commerce_common` 对应上游 `commerce-common/commerce_common/`，`shopping_agent` 对应
> `shopping-agent/core/shopping_agent/`，`merchant_agent` 对应 `merchant-agent/core/merchant_agent/`。

## 一、契约

- **组件就是一个工具**。模型的参数携带它的判断：哪些 id、按什么顺序、每一项的理由或说明、按什么维度比较。
  服务端把每一个事实（标题、价格、图片、指标值、变更记录）都从**本会话工具返回过的记录**中对接上，
  因此**前端永远不会渲染由模型自撰的值**。
- **每个组件一份规格**：`commerce_common` 包 `presentation.py` 中的 `PresentationComponent` 给出工具名、
  宿主用于渲染的 `component` 字符串、校验参数的 `payload_model`（各角色 `tools` 目录下的 `presentation.py`），
  以及 `enrich` 钩子（各角色的 `enrichment.py`，汇总于 `PRESENTATION_COMPONENTS`）。
- `commerce_common` 包 `presentation.py` 中的 `run_presentation` 是**唯一的运行器**：校验、补全、发出 `ui` 事件。
  模型读到的是执行器的 `displayed_text` 加上钩子给出的说明；**补全后的载荷只发给宿主**。
- 补全钩子会丢弃没有来源的 id 并追加一条写明它们的说明；当什么都不剩时抛出 `PresentationRefused`——
  它在指明门禁时以"被拦下的调用"返回，否则以错误返回。
- 购物侧从 `ShoppingSessionState.seen_products`、购物车或一次订单读取中对接；商家侧从
  `MerchantSessionState.latest_snapshot`、`seen_series`、`seen_campaigns`、`seen_analyses`、`seen_listings`
  与 `seen_changes` 中对接。`enrich_change_preview` 还会**移除那些货币或星期与变更记录不符的模型文本**。
- **组合规则**（由哪个组件结束一轮、文本承载推理、卡片承载数据）属于静态提示词材料；
  每个组件的"何时使用"那一行就是它的工具描述（参见商务架构技能的分层表）。

## 二、建议快捷选项

- `present_suggestions` 是**唯一**携带本轮快捷选项的工具，至多四个；模型在本轮最后一个组件的**同一回合**调用它，
  若本轮没有组件，则在文本之后调用；被点选的快捷选项作为**下一条用户消息**发出。
  其他任何载荷——内置的或扩展的——都**不携带**快捷选项。
- `commerce_common` 包 `fencing.py` 中的 `sanitize_suggestion_chips` 作用于 `PresentSuggestionsPayload`：
  去掉不可见字符与控制字符、折叠空白、丢弃空项、每项 80 字符、至多四项。
  **净化后一个都不剩时，该载荷判定为失败。**
- 一轮**干净的**呈现调用若包含 `present_suggestions`，则**结束本轮**
  （`commerce_common` 包 `turn.py` 中的 `round_closes_turn`，配置项 `close_on_presentation`）：
  Messages API 循环在此停下，Agent SDK 运行时则通过 `PostToolBatch` 钩子停下
  （`close_on_presentation_hook`，`commerce_common` 包 `agent_sdk.py`）。
  在宿主审批开启时，商家侧提示词会说明**没有任何快捷选项会批准或应用变更**。

## 三、事件流

事件清单就是 `commerce_common` 包 `streaming.py` 的文档字符串；`to_sse` 把每个事件装帧，宿主忽略自己不认识的类型。
`ui` 携带一个补全后的组件；`ui_partial` 在其调用仍在流式进行时携带同样的内容；
`cart_update` 在购物车写入之后携带整车；`change_update` 在变更记录发生移动之后携带它。
`commerce_common` 包 `turn.py` 中的 `outcome_events` 为每个 `ui` 事件盖上其调用 id 作为 `stream_id`，
并紧随其后发出 `tool_result`，其 `status` 为 `ok`、`error` 或 `blocked`。
**每一个非呈现类工具都可以先接受一个 `status` 参数**（`with_status`，`commerce_common` 包 `execution.py`）：
给等待者看的几个字，执行器在调用真正执行前把它丢掉，运行时把它作为 `tool_call` 事件的 `label` 发出；
Web 层把它显示为活动行。**MCP 服务器构建工具时不带它。**
Agent SDK 运行时执行同一个执行器，但在该轮结束后把载荷一并放在 `result.ui` 中返回。

## 四、渐进式渲染

带 `enrich_partial` 钩子的规格会在**参数陆续到达的过程中**就被渲染：请求把它的工具标记为 `eager_input_streaming`
（`with_eager_input`，`commerce_common` 包 `prompt_assembly.py`），编排器用 `parse_partial_json` 解析缓冲区
（**仍在写入中的字符串连同其键一起略去**），调用 `enrich_partial`（`commerce_common` 包 `presentation.py`），
并在 `partial_signature` 变化时产出 `ui_partial`（`StreamedRound.frame`，`commerce_common` 包 `turn.py`；
开启配置项 `eager_partial_frames` 时**每一次可见变化**都产出）；最终的 `ui` 事件携带**相同的** `stream_id` 并将它替换掉。
若流式输入不是 JSON 而是文本，会以**错误结果**回到模型，该回合继续进行（`StreamedRound`）。
部分补全钩子是**同步**的，且**只从会话状态**对接
（`partial_products`、`partial_comparison`、`partial_plan`、`partial_guide` 在 `shopping_agent` 包的 `enrichment.py`；
`partial_metrics`、`partial_digest`、`partial_change_preview` 在 `merchant_agent` 包的 `enrichment.py`）。

## 五、内置组件

- **购物侧**（`shopping_agent` 包 `enrichment.py`）：`present_products`、`present_comparison`、`present_plan`、
  `present_guide`、`present_order_status`、`checkout`（渲染购物车；**不扣任何款**）、`present_suggestions`，
  以及 `present_disclosure`——后者**仅在 `enable_disclosures` 下注册**，由 `StorefrontBackend.get_disclosure` 填充。
- **商家侧**（`merchant_agent` 包 `enrichment.py`）：`present_metrics`、`present_digest`、`present_change_preview`、
  `present_suggestions`。

## 六、新增一个垂直领域组件

- 构建一个 `PresentationExtension`（`commerce_common` 包 `presentation.py`）：模型看到的工具描述与 `input_schema`、
  校验同一形状的 `payload_model`、`component` 名称，以及补全钩子。
- 把它作为 `extra_presentation_tools` 传给 `ShoppingAgent` 或 `MerchantAgent`
  （示例见上游 `examples/travel/api` 目录的 `main.py`）；在 Agent SDK 与 MCP 路径上，
  改为继承工具集或传 `executor_class=`，使执行器以 `extensions` 收到它。
  `build_tools` **拒绝**与内置组件重名的名称，且扩展的字节会计入**已缓存的工具清单**（参见提示词缓存技能）。
- 上游仓库中的七个实例分别位于：`examples/travel/api` 目录的 `itinerary.py` 与 `occupancy.py`、
  `examples/telecom/api` 目录的 `plan_matrix.py` 与 `plan_mix.py`、
  `examples/entertainment/api` 目录的 `venue_map.py`、`hold_view.py` 与 `event_pacing.py`。
  每个都把自己的类型与卡片留在垂直领域内，**核心包里不加任何东西**。

## 执行流程

1. **确认组件形态**。先判定要处理的是内置组件、垂直领域扩展还是新建组件，并按开头的路径约定映射到上游模块。
   判据：能指出该组件的 `PresentationComponent` 规格与 `enrich` 钩子各自的落点。
2. **核对「组件即工具」的边界**。确认模型的参数只承载**判断**（哪些 id、顺序、理由、比较维度），
   而每个事实都由服务端从本会话工具返回过的记录中对接。判据：逐一抽查卡片字段，都能回溯到某条会话内记录，
   **找不到任何模型自撰的值**。
3. **核对来源过滤与说明**。确认补全钩子会丢弃无来源的 id 并在说明中点名它们；什么都不剩时抛 `PresentationRefused`，
   且该异常在指明门禁时以"被拦下的调用"返回。判据：塞一个无来源 id，应被丢弃并出现在说明里。
4. **核对快捷选项的唯一来源**。确认只有 `present_suggestions` 携带快捷选项，至多四个，且经过 `sanitize_suggestion_chips`。
   判据：净化后为空时该载荷判定为失败；其他任何载荷都不携带快捷选项。
5. **核对收轮条件**。确认"含 `present_suggestions` 的一轮干净呈现调用"会结束本轮，且 Messages API 与 Agent SDK 两条路径各有对应机制。
   判据：能分别指出 `round_closes_turn` 与 `close_on_presentation_hook` 的生效位置。
6. **核对事件流字段**。对 `ui`、`ui_partial`、`cart_update`、`change_update`、`tool_result` 逐个确认载荷内容与
   `stream_id`／`status` 的取值域。判据：非呈现类工具的 `status` 参数在调用执行前被丢弃、并以 `tool_call` 的 `label` 发出。
7. **核对渐进式渲染**。确认请求把工具标记为 `eager_input_streaming`、用 `parse_partial_json` 解析缓冲区、
   在 `partial_signature` 变化时产出 `ui_partial`，且最终 `ui` 用**同一** `stream_id` 替换它。
   判据：非 JSON 的流式输入以错误结果回到模型且该回合继续；部分钩子是同步的且只读会话状态。
8. **核对新增扩展的接入方式**。按部署形态分别确认 `extra_presentation_tools`、继承工具集或 `executor_class=` 三条路径；
   确认重名会被 `build_tools` 拒绝、扩展字节计入已缓存工具清单、且类型与卡片留在垂直领域内。
   判据：核心包中不出现垂直领域专有类型。

## 边界与降级

- **依赖上游代码与前端**：本技能描述的是上游参考仓库的呈现契约；**本包不含这些文件，也不含可运行环境或前端**。
  实际改动请回到上游仓库。此时本技能降级为**契约审查清单**，逐条核对即可，交付完整性不下降。
- **无前端可验时**：无法确认卡片渲染效果，应改为**协议层核对**（载荷形状、`stream_id` 配对、事件类型覆盖），
  并明确标注"未做端到端验证"，不得据此断言前端表现。
- **两条硬红线（不得降级）**：① 前端渲染的每一个值都必须来自服务端对接的会话内记录，**不得**渲染模型自撰的值；
  ② 快捷选项只能由 `present_suggestions` 携带且必须经过净化。这两条属事实性约束，不适用"用默认值推进"。
- **部分渲染不可用时**：省略 `enrich_partial` 钩子即可退化为一次性渲染，契约其余部分不受影响；
  此时应标注"未启用渐进式渲染"，而**不得**伪造 `ui_partial` 事件序列。
- **扩展与内置重名时**：由 `build_tools` 拒绝，**不得**改内置名称来绕开；改名后需同步提示词与工具清单缓存版本。
- **无沙箱或无网络时**：只做静态核对，逐条标注"已核对／未核对"，不得把未核对项读作通过。
- **信息不足时**：明确列出缺失项（前端、事件消费端、宿主），只对可判定部分下结论。

## 质量自检

- [ ] 每个组件的规格四要素齐备：工具名、`component` 名、`payload_model`、`enrich` 钩子。
- [ ] 卡片中每个值都可回溯到本会话工具返回过的记录，**无任何模型自撰的值**。
- [ ] 补全钩子会丢弃无来源 id 并在说明中点名；空结果时抛 `PresentationRefused` 且能区分"被拦下"与"出错"。
- [ ] 快捷选项仅由 `present_suggestions` 携带，至多四个，且经 `sanitize_suggestion_chips` 净化；空结果判定为失败。
- [ ] 收轮条件已确认，Messages API 与 Agent SDK 两条路径的机制均已核对。
- [ ] 事件类型与字段已核对：`ui`／`ui_partial` 的 `stream_id` 配对、`tool_result` 的三种 `status`、非呈现工具的 `status` 只作 `label`。
- [ ] 渐进式渲染链路完整：`eager_input_streaming`、`parse_partial_json`、`partial_signature` 变更触发、最终 `ui` 替换；
  非 JSON 输入不中断回合。
- [ ] 新增扩展的接入路径按部署形态已确认；重名被拒；类型与卡片留在垂直领域内。
- [ ] `present_disclosure` 仅在 `enable_disclosures` 下注册；`checkout` 不扣款。
- [ ] 无占位符、无待填项；所有模块与文件引用均指向上游仓库且已被开头的路径约定覆盖。

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样，正文已中文化。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
