---
name: commerce-trust-safety
version: 1.0.0
display_name: "信任与安全规则（代码层）"
display_name_en: "Commerce Trust Safety"
description_zh: "参考实现在代码层强制执行的全部规则：第三方内容围栏、写入的来源与上限门禁、接地、身份、记忆边界，各条均给出所在模块，另附两条对抗性评测规则。"
description_en: "The rules the reference agents enforce in code for third-party content, writes, grounding, identity, and memory, each with its module, plus two adversarial-eval rules."
category: productivity
author: "anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-trust-safety"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  参考实现在代码层强制执行的全部规则：第三方内容围栏、写入的来源与上限门禁、接地、身份、
  记忆边界，各条均给出所在模块，另附两条对抗性评测规则。
  触发场景：处理不可信的工具结果；给写入类工具加门禁；限定智能体"记得住什么"。
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/commerce-agents/plugins/commerce-builder/skills/commerce-trust-safety
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# 信任与安全规则

> **路径约定**：本文所有模块与文件均指**上游参考仓库**内的位置，**不随本包交付**，本包内不存在这些文件。
> 其中 `commerce_common` 对应上游 `commerce-common/commerce_common/`，`shopping_agent` 对应
> `shopping-agent/core/shopping_agent/`，`merchant_agent` 对应 `merchant-agent/core/merchant_agent/`。
> 下文凡写作「X 包的 Y」者，均指上游仓库中该模块下的同名文件。

同样的规则也列在上游 `docs` 目录的 `safety.md` 中。
**落在工具调用内的规则在三条路径上同时成立**，因为它们共享同一个执行器（参见商务架构技能）；
第 10 条与第 15 条另行点明各自适用的路径。商家侧的暂存、护栏、审批与市场姿态见商家侧运营技能。

## 一、第三方内容一律加围栏

1. 来自商品目录、评论、政策、订单、指标、消息或网页内容的**每一个工具结果**都要经过
   `Fence.fence_payload`（`commerce_common` 包的 `fencing.py`）：NFKC 归一化，移除不可见字符与控制字符，
   替换围栏标记、伪造的轮次标记与特殊 token，套上角色的标签，并在 `max_fenced_chars` 处截断。
   执行器的 `_fenced` 会把这一处理施加到**每一个**处理器上。
2. 标签与提示是**按角色的常量**（`STOREFRONT_FENCE` 在 `shopping_agent` 包的 `fencing.py`，
   `MERCHANT_FENCE` 在 `merchant_agent` 包的 `fencing.py`）；提示在静态提示词中**只出现一次**，且其中不含任何不可信内容。
3. 每请求块（画像、购物车、记忆事实、页面、店铺上下文）位于**同一道围栏之内**、且在缓存断点之后
   （各角色 `prompt.py` 中的 `build_dynamic_context`）；后端上下文块另有自己的体量上限。
4. 模型给出的结果条数会被夹到 `max_search_results`（`clamp_limit`，`commerce_common` 包的 `execution.py`）。

## 二、写入按来源与上限加门禁

5. 购物车写入**只接受** `ShoppingSessionState.seen_products` 中的 id，该集合由本会话的商品目录读取与订单读取填充
   （`check_provenance` 与 `remember_order_items`，`shopping_agent` 包的 `gates.py`）；
   更新与移除还接受已在购物车中的行。商家侧暂存只接受 `seen_listings` 与 `read_listings` 中的 id，
   应用与丢弃只接受 `seen_changes` 中的 id（`merchant_agent` 包的 `gates.py`；另见商家侧运营技能）。
6. `max_quantity_per_item` 在写入后对行做上限约束，`max_cart_lines` 对整车做约束，且在**会话锁**之下执行
   （`gated_add_to_cart`，`shopping_agent` 包的 `gates.py`；上限在 `shopping_agent` 包的 `config.py`）。
   该锁是**按进程**的，因此 `StorefrontBackend` 的购物车方法也必须自行施加这些约束；
   资格、定价与库存**在两个角色中都属于后端**。
7. **两个接口都不会扣款或下单**：`checkout` 只渲染购物车（`enrich_checkout`，`shopping_agent` 包的 `enrichment.py`），
   由宿主完成交易；售后关怀是只读的，**没有取消或退款工具**。
8. 来源信息存放在会话状态上（`ShoppingSessionState`、`MerchantSessionState`），
   在请求或轮次结束时随会话一并保存（`SessionStore`，上游 `examples/demo_common` 目录的 `sessions.py`
   ——它是与转写并排的一份带版本的状态文档），因此另一个进程上的请求也能载入它。
   每个映射保留最新的 `PROVENANCE_CAP` 条记录（`remember`，`commerce_common` 包的 `types.py`）；
   **被挤掉的 id 需要重新读取一次**。
9. 组件要经过校验，其商品、订单、指标或变更从上述记录中对接，**没有来源的 id 被丢弃并上报**
   （`run_presentation`，`commerce_common` 包的 `presentation.py`；各角色的 `enrichment.py`；另见界面与工具技能）。

## 三、涉及数字或条款的回答必须接地

10. 条款类问题、订单类问题、或未出现过的商品 id（`GROUNDING_RULES`，`shopping_agent` 包的 `grounding.py`），
    以及业绩类问题或"什么都没暂存却要求应用"的请求（`merchant_agent` 包的 `grounding.py`），
    都要从**对应的读取**开始：由 `commerce_common` 包 `grounding.py` 中的 `first_forced_tool` 选出该读取；
    Messages API 运行时用 `tool_choice` 强制它；SDK 运行时在该规则有预取形态时预取它
    （`ground`，`commerce_common` 包的 `agent_sdk.py`；**条款类规则没有预取形态**）；托管路径只有提示词这一道。
11. 词表是配置元组（`policy_intent_terms`、`order_intent_terms`、`product_id_patterns`、`metrics_intent_terms`
    及其线索词）；部署方**追加**自己的词，门禁开关可以关掉某条规则，**两者都不改变提示词字节**。

## 四、身份由服务端持有

12. 会话开始时把已认证主体绑定到一个**不可猜的**会话 id；此后的请求只携带该 id，
    路由从记录中读取主体（`SessionStore.start` 与 `session_dependency`，上游 `examples/demo_common` 目录的 `sessions.py`）。
    **没有任何请求字段或工具参数会指名用户、商家或运营方**；MCP 服务器从自己的环境中取主体，生产服务器从请求中取。
13. 主体是否拥有某条记录（订单、工单、商品页），以及某次调用所依赖的前序步骤是否已发生，
    都**由后端对照自己的存储来判断**；**一个 id 有来源，并不意味着它属于该主体、或已经就绪**。

## 五、限定"记得住什么"

14. 两条写入路径（`save_memory` 与轮次后抽取）上的**每一条事实**都要通过 `commerce_common` 包 `memory.py` 中的 `validate_fact`：
    键最长 64 字符，值最长 200，属于三个 `MemoryCategory` 取值之一，并通过 `MemoryWriteFilter`——该过滤器**默认拒绝形如标识符的值**；
    `memory_blocked_patterns` 用于追加模式，带 `checks` 的过滤器则**替换**它（`MemoryRuntime.build`）。
15. 抽取只读**最后一次往来的用户与助手文本**（`transcript_text`，`commerce_common` 包的 `turn.py`），
    且当主体在此期间已被清除时，`extract_and_store` 会**丢弃**这一批；Messages API 运行时执行它（`update_memory`），
    SDK 宿主调用该运行时，托管路径则只经 `save_memory` 写入。
16. `memory_retention_days`（`with_retention`）、`MemoryStore.delete_fact`、`MemoryStore.clear` 与 `enable_memory`
    在**所有路径**上成立，且**不改变提示词或工具字节**；示例中暴露了读取与删除路由
    （`install_memory_routes`，上游 `examples/demo_common` 目录的 `memory.py`），
    而 `clear` 属于**账号删除**流程的一部分。
17. 记忆主体是购物者的 `user_id` 或生意的 `merchant_id`（各角色 `executor.py` 中的 `memory_subject`）。

## 六、拒绝走返回值，且暴露面保持固定

18. 被拦下的调用返回一个**正常结果**并点明是哪道门禁（`ToolOutcome.held`，`commerce_common` 包的 `streaming.py`；
    宿主的 `tool_result` 事件携带 `status: blocked`）；失败返回错误结果；而 `execute` **永不抛异常**。
19. 工具清单是配置的函数：`enable_web_search`（默认关闭）会加上该工具，SDK 运行时对已注册名称做白名单，
    清单则逐个启用工具。
20. 参考实现的 MCP 服务器**默认只绑定回环地址**，除非有环境变量声明前方存在一道认证网关
    （`enforce_local_only_bind`，`commerce_common` 包的 `mcp_server.py`）。

## 七、对抗性评测的两条规则

- 带毒的商品页、评论与消息存放在**供某次评测运行时合入**的夹具中，位于演示数据与目录数据之外。
- **每一条拒绝类用例在同一细分场景下都要有"本应服务"的对照**，这样一套评测才能也抓住**过度拒绝**（参见行为评测技能）。

## 执行流程

1. **判定规则适用路径**。先明确当前要处理的是购物侧、商家侧还是两者共享的执行器路径。判据：能将每条规则落到具体路径，
   并指出第 10 条与第 15 条各自适用的路径。
2. **围栏先行**。核对来自目录、评论、政策、订单、指标、消息与网页内容的每一类工具结果是否都经过 `Fence.fence_payload`，
   并逐项确认 NFKC 归一化、不可见字符清除、标记替换与 `max_fenced_chars` 截断均已生效。
   判据：执行器的 `_fenced` 覆盖到每一个处理器；不可信内容不出现在静态提示词中。
3. **核对写入来源门禁**。对购物车与商家暂存分别列出「只接受哪些 id 集合」的清单，并确认更新、移除、应用、丢弃各自的额外条件。
   判据：用未出现过的 id 构造一次写入，应被拒绝。
4. **核对上限与会话锁**。检查 `max_quantity_per_item`、`max_cart_lines` 与后端的二次施加。
   判据：直接绕过门禁调用后端方法时，上限仍应生效。
5. **核对交易边界**。确认没有任何接口会扣款或下单，售后为只读。判据：全量检索是否有取消、退款、下单类工具，应为零。
6. **核对来源存储与容量**。确认来源存放在会话状态上并随会话保存，且每个映射保留 `PROVENANCE_CAP` 条。
   判据：构造一次"id 被挤掉"的情形，再次使用该 id 时应被要求重新读取。
7. **核对接地规则**。逐条确认条款、订单、未见过的商品 id、业绩与"未暂存却要求应用"这几种触发条件，
   以及对应读取被选中的方式（强制、预取或仅靠提示词）。判据：能指出哪条规则没有预取形态。
8. **核对身份绑定**。确认会话开始时绑定不可猜的会话 id，且请求字段与工具参数中**不含**任何主体标识。
   判据：抽查全部工具签名与请求模型，应无用户、商家、运营方字段。
9. **核对记忆边界**。逐项确认 `validate_fact` 的四条约束、写入过滤器默认拒绝标识符形态、
   抽取只读最后一次往来、主体被清除时丢弃本批。判据：构造一条标识符形态的值，应被拒写。
10. **登记暴露面**。确认工具清单随配置变化而固定，且 MCP 服务器默认只绑回环。判据：能给出该部署的完整工具白名单与绑定地址。

## 边界与降级

- **依赖上游代码**：本技能描述的是上游参考仓库在代码层强制的规则；**本包不含这些文件，也不含可运行环境**。
  实际改动请回到上游仓库。此时本技能降级为**实现与审查清单**，逐条核对即可，交付完整性不下降。
- **无后端可验时**：无法验证"id 是否属于该主体""前序步骤是否已发生"（这两项由后端负责）时，
  应明确标注**未验证**，不得据此断言安全；也不要自己在前端补一层替代判定。
- **四条硬红线（不得以任何降级方式放宽）**：① 第三方内容必须过围栏；② 写入必须过来源与上限门禁；
  ③ 身份必须由服务端持有、请求字段不得携带主体；④ 记忆抽取不得写入标识符形态的值或可识别顾客信息。
  这四条属**事实性约束，不适用"用默认值推进"**。
- **无沙箱或无网络时**：只做静态核对（清单式审查），逐条给出"已核对／未核对"，不得把未核对项读作通过。
- **词表与门禁开关**：追加词表或关闭某条规则**不改变提示词字节**；但关闭规则属**部署决策**，
  必须在交付说明中列明关了哪一条、为什么。
- **过时来源的处理**：id 被 `PROVENANCE_CAP` 挤掉后**必须重新读取**；
  **禁止**为"让流程走通"而放宽来源校验或直接把 id 塞进状态。
- **信息不足时**：明确列出缺失项（后端、认证、沙箱、夹具），只对可判定部分下结论。

## 质量自检

- [ ] 每类工具结果都经围栏处理，且静态提示词中不含不可信内容。
- [ ] 写入的来源门禁已逐条核对（购物车与商家暂存各自的允许 id 集合，以及更新／移除／应用／丢弃的额外条件）。
- [ ] 上限（单行数量、整车行数）在门禁与后端**两处**都生效，且处于会话锁之下。
- [ ] 全库无扣款、下单、取消、退款类工具；售后为只读。
- [ ] 来源保存在会话状态上，且 `PROVENANCE_CAP` 挤出后的 id 会被要求重新读取。
- [ ] 接地规则逐条可指出触发条件与选中读取的方式；已注明条款类规则无预取形态。
- [ ] 全量工具签名与请求模型中没有用户、商家、运营方标识字段。
- [ ] 记忆校验四条约束均生效，写入过滤器默认拒绝标识符形态；主体被清除时本批抽取被丢弃。
- [ ] `enable_memory` 与保留期、删除、清空在各路径一致，且不改变提示词与工具字节；`clear` 已纳入账号删除流程。
- [ ] MCP 服务器默认只绑回环，除非已声明前方存在认证网关。
- [ ] 无占位符、无待填项；所有模块与文件引用均指向上游仓库且已被开头的路径约定覆盖。

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样，正文已中文化。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
