# 术语表（EN → zh 映射，跨批唯一口径）

> 定位：`localization-zh.md` 管「译什么 / 不译什么 / 怎么写」，本表管「**同一个英文词永远译成同一个中文词**」。
> 维护规则：**只追加，不改旧条目**；新词条目须注明出处批次；两个候选译名打架时，以**已交付 22 包中的实际用词**为准（下表「采用」列即实证结果，N=出现文件数，2026-09-21 扫描）。

## 一、通用术语

| 英文 | 采用译法 | 实证 |
|---|---|---|
| skill | 技能 | 全部 22 包 |
| upstream / source repo | 上游（仓库） | 全部 22 包 |
| workflow | 工作流 | 3 包（goldie、astra×2） |
| template | 模板 | 3 包 |
| orchestrator | 编排器 | 3 包 |
| subagent | 子代理 | 2 包 |
| checklist | 检查清单 | 1 包 |
| fallback / degradation | 降级 | 22 包（「边界与降级」） |
| transcribe / transcription | 转录 | 1 包新例（video-transcribe，2026-09-26；先例检索 0 命中后新造） |
| transcript | 转录文本 | 1 包新例（同上；区别于动作「转录」） |
| podcast | 播客 | 1 包新例（同上） |
| typed judgment | 类型化判断 | 1 包新例（jev-skill，2026-09-27；决策域核心词） |
| decision layer / control plane | 决策层 / 控制面 | 1 包新例（同上） |
| confidence | 置信度 | 1 包新例（同上；区别于 correctness「正确性」） |
| golden set | 黄金评测集 | 1 包新例（同上；评测基准集） |
| calibration | 校准 | 1 包新例（同上） |
| fail closed | 失败即拒绝 | 1 包新例（同上；安全默认行为） |
| canary | 金丝雀（版本） | 1 包新例（同上；浮动版本指针） |
| allowlist | 允许清单 | 1 包新例（同上） |
| verifier | 验证器 | 1 包新例（同上；区别于 validate「校验」） |
| routing / threshold | 路由 / 阈值 | 1 包新例（同上） |
| holographic foil | 全息镭射 | 1 包新例（holo-card-studio，2026-09-27） |
| lenticular | 光栅 | 1 包新例（同上） |
| ukiyo-e / sumi-e | 浮世绘 / 墨绘 | 1 包新例（同上） |
| registration | 套准 | 1 包新例（同上；图层对齐） |
| identity lock | 形象锁定 | 1 包新例（同上；A/B 形象一致性） |
| keyword | 关键词 | 先例 2 包，N9 批沿用 |
| ranking / rank tracking | 排名（追踪排名） | N9 批新例（SEO 域，先例 0 命中） |
| competitor (gap) | 竞品（竞品差距） | N9 批新例（SEO 域） |
| backlink | 反链 | N9 批新例（SEO 域；「引用域」= referring domain） |
| organic (traffic) | 自然（流量） | N9 批新例（SEO 域，与付费/paid 对举） |
| SERP | SERP（搜索结果页） | N9 批新例：缩写保留，首现可括注 |
| Search Console / GA4 / Google Ads | 保留英文 | Google 产品名不译 |
| striking distance | 近距离（排位） | N9 批新例（排位 8–20 的约定译法，包内首现括注英文） |
| cannibalization | 同类相食 | N9 批新例（SEO 术语，多页瓜分同词） |
| anchor (text) | 锚文本 | N9 批新例 |
| referring domains | 引用域 | N9 批新例 |
| gate / gate check | 门禁（内部用语，不出现在交付包正文） | — |
| port / porting | 搬运 / 移植（正文语境用「移植」，内部叙述用「搬运」） | — |

## 二、角色与拓扑（astra 批专有）

| 英文 | 采用译法 | 实证 |
|---|---|---|
| root agent | 根代理 | 2 包 |
| explorer | 探索者 | 2 包 |
| worker | 执行者 | 2 包 |
| tester | 测试者 | 2 包 |
| reviewer | 评审者 | 2 包 |
| researcher | 调研者 | 2 包 |
| reasoning effort | 推理档（high/medium/low → 最高/中等/低推理档） | 2 包 |
| delegation contract | 委派契约 | 2 包 |
| dispatch gate | 委派闸门 | 2 包 |
| model name（`gpt-5.6-luna` 等） | 原样保留，不译 | 2 包 |
| profile（Plus / Pro） | 原样保留，不译 | 3 包 |

## 三、固定段标题（我们的移植模板词，全部 22 包统一）

这四个标题是**平台结构判据的锚点**（判据只认中文词），拼写必须逐字一致：

| 段 | 固定标题 |
|---|---|
| 执行段 | `执行流程` |
| 边界段 | `边界与降级` |
| 自检段 | `质量自检` |
| 移植段 | `搬运说明` |

源技能标题的常见对应（依据 SOP 第五节样例）：`Purpose → 用途`、`Usage Instructions → 使用步骤`、`Available Themes → 可用主题`。同义源标题优先套用已用词，不自造。

## 四、并置与残留规则（回收自各批实做）

1. 专有概念**首次出现**：「中文（English）」并置，如 `主题工厂（Theme Factory）`；之后可只用中文。
2. 专有名词/产品名（`WorkBuddy`、`Slack`）：原样或并置，不硬译。
3. **目标状态：无中英夹杂整句**。允许残留 EN 的是 localization-zh.md 第二节所列类别＋本表标注「原样」的条目。
4. 正文引用的流程名/配置键（如 `flow: "store-01-home"`）：代码形态原样；**行文提到它时**可写「流程 `store-01-home`」——反引号内不译，反引号外用中文。
5. ⚠ 新术语拿不准时：先 grep 已交付 22 包；仍无先例才允许新造，并立即回填本表。

## 五、已知残留（下一批顺手项）

- `goldie` 及相关包有 3 处 EN 段标题（`Where each fact comes from`、`Stage and preview`）未译——按第四节规则应译为「各事实的来源」「暂存与预览」，已在 batch5 终验中记录，属低风险残留。
