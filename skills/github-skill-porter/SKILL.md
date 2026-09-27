---
name: github-skill-porter
version: 2.4.0
display_name: GitHub技能搬运工
display_name_en: GitHub Skill Porter
description_zh: "支持清单文件与多 --source 叠加的批量搬运模式，可桥接外部「采集雷达」类候选榜单自动筛出可搬技能，自动体检并转换 Agent Skills 源技能，自动识别许可证 SPDX（含从仓库根目录兜底），双轨产出本地版与可上传平台版，在交付前运行引用完整性自检门禁，并提供平台版中文化改写 SOP 与中文化门禁；跨会话复用源码与文件树缓存，避免重复下载与 GitHub API 限流，运行时自动向共享层公示本会话能力；内置许可准入门禁（无许可拒收、copyleft 仅本地、宽松许可强制随附许可证全文与归属声明），以 SOURCE_INFO.json 契约接入 GitHub 之外的采集源（含把采集端的仓库级素材根自动展开为技能级源并继承来源与许可），产出平台上架物料，并在交付前执行去毒审计（凭据泄露 / 提示词注入 / 危险执行 / 敏感读取 / 路径遍历 / 供应链六类，硬问题阻断上架）；交付前调用平台官方校验器复核，并提供 N:1 合并引擎——按相似度准入闸把同能力多配置收敛为单一技能，共同部分逐行保留、差异逐项落表、零丢失验收。"
description_en: "Batch mode via manifest or multiple --source flags, plus a bridge that triages external discovery reports into portable skill sources. Audits and ports Agent Skills, auto-detects license SPDX (with repo-root fallback), produces dual-track output (local + uploadable), and runs a built-in reference-integrity gate before delivery. Reuses source and file-tree caches across sessions to avoid duplicate downloads and GitHub API rate limits, and announces its capabilities to the shared layer at runtime. Enforces a license admission gate (refuses unlicensed sources, keeps copyleft local-only, bundles license text and attribution for permissive sources), ingests non-GitHub collected material through a SOURCE_INFO.json contract (including expanding a collector's repo-level material roots into skill-level sources with inherited provenance), emits platform listing material, and runs a pre-delivery toxicity audit (credentials, prompt injection, dangerous execution, sensitive reads, path traversal, supply chain) that blocks delivery on hard findings. Cross-checks every artifact with the platform's official validator, and ships an N:1 merge engine that collapses variants of one capability into a single skill behind a similarity admission gate, preserving the common body line-by-line, tabulating every difference, and enforcing a zero-loss acceptance check."
category: productivity
author: WorkBuddy
allowed-tools: Read,Write,Edit,Bash,Glob,Grep,WebFetch
agent_created: true
description: |
  当用户想把 GitHub 或本地的 Agent Skills 技能（anthropics/skills、awesome-claude-skills、obra/superpowers 等）
  搬到 WorkBuddy 时使用，覆盖定位/抓取、体检、转换、合规加固、打包全流程。
  产出可迁移性体检报告、本地可安装版技能目录、以及可直接上传开放平台的 root 直铺 zip。
  触发词：搬运技能、迁移技能、转换技能、导入 GitHub 技能、port skill、把 GitHub 技能装进来。
  不适用于：从零创作新技能、生成专家或连接器、搬运非 Agent Skills 格式的提示词仓库。
---

# GitHub技能搬运工

把 GitHub 上遵循 Agent Skills 标准的技能，体检、转换、打包成 WorkBuddy 能装、能传、能跑的技能包。面向想在 WorkBuddy 中复用 GitHub 技能生态的技能作者与开发者。

## 一、职责与边界

- 做：解析源结构 → 体检风险 → 按映射表补字段 → 拉平目录 → 降级外部依赖 → 双轨产出（本地版 + 平台版 zip）→ 输出改动清单。
- 不做：从零创作新技能（交给技能生成器）；改写技能的领域方法论本身；生成专家或连接器。

## 二、核心能力

**能力 1 · 规格转换与双轨产出**
- 用户目标：一个源技能（GitHub 地址或本地目录），同时要能在本地装、能上传平台。
- 对标基准：手工逐字段补 frontmatter、手动拉平目录、手动压缩。
- 可验证差异：① 一次运行同时产出平台版与本地版两套目录；② 平台版 zip 为 root 直铺，解压即可上传；③ 输出逐条改动清单，标明改了什么、为什么改。
- 验收判据：平台版通过合规校验零 FAIL；zip 根目录含 SKILL.md；改动清单覆盖全部字段改动与文件搬迁。

**能力 2 · 可迁移性体检**
- 用户目标：动手前就知道这个技能能不能搬、卡在哪、值不值得搬。
- 对标基准：人肉通读 SKILL.md 与脚本判断。
- 可验证差异：① 结构化体检报告，逐项给风险等级与处置动作；② 覆盖五类风险（外部依赖、目录层级、保留词命名、许可证、工具名）；③ 结论强制三选一。
- 验收判据：报告必含五类风险逐项结论；每个阻断项有具体处置动作；结论为「可直接搬 / 需改造 / 不建议搬」之一。

**能力 3 · 依赖降级与本地化改写**
- 用户目标：让依赖联网、第三方包或专属工具的技能，在平台沙箱里也能跑通。
- 对标基准：原样搬运（沙箱评测因无网络或无依赖而失败）。
- 可验证差异：① 联网依赖改写为「内置知识优先、联网可选增强」；② 平台外工具名映射到 WorkBuddy 工具集，无对应者改为文字规则；③ 无法降级的依赖显式写入「不适用于」。
- 验收判据：平台版正文不含联网强依赖、不含第三方 import（标准库除外）、不含平台工具集之外的工具名。

**能力 4 · 许可证自动识别与交付前自检门禁**
- 用户目标：搬完不用再手工补 license、也不用肉眼核对引用是否漏改。
- 对标基准：手工读 LICENSE 文本判断 SPDX，再逐条 grep 正文查引用是否覆盖。
- 可验证差异：① 读取源根目录 LICENSE / COPYING 文本识别 SPDX（Apache-2.0 / MIT / BSD / GPL / MPL / ISC / CC 等）写入 `license`；源已含标准标识则沿用，非标准表述有识别结果则覆盖、无则标注待核；② 转换结束自动跑自检门禁，双向校验引用——既查悬空引用（正文引用不指向真实文件），也查覆盖盲区（被搬文件未被正文引用），并复验七项字段与目录层级；③ 硬问题（缺字段 / 层级超限 / 悬空引用）**非零退出阻断交付**，软问题列入待人工确认。
- 验收判据：改动清单含「`license`：已识别为 `<SPDX>`」；「六、交付前自检」节显示 **PASS** 或列出硬问题；硬问题时退出码非 0。

**能力 5 · 批量搬运与汇总**
- 用户目标：一次把多个源（本地目录、GitHub 地址任意混合）批量转换，并拿到总览报告。
- 对标基准：把同一命令手动跑 N 次再人工汇总。
- 可验证差异：① 两种形态归一——`--batch manifest.txt`（每行一个源，`#` 注释）或多次 `--source <源>` 叠加；② 每技能独立产出互不覆盖（各自 `<slug>/`、`<slug>.zip`、`<slug>-local/`，改动清单落各自目录）；③ 结束生成 `batch-report.md` 汇总表（源 / slug / 类型 / 许可证 / 平台版 zip / 自检 / 备注），失败源单列；④ 单源退化为原行为；多源时单源失败不阻塞其余，有硬问题或失败项则整体非零退出。
- 验收判据：`batch-report.md` 含全部成功与失败项；每个 `<slug>/` 内含 `porting-changes.md`；有硬问题或失败时退出码非 0，成功项不受影响。

**能力 6 · 平台版中文化改写（LLM / 人工，按需）**
- 用户目标：英文源技能搬到中文环境时，平台版正文与字段读得通、术语不乱。
- 对标基准：逐句机翻（专有名词、路径、色值、字体名被误翻）。
- 可验证差异：① 提供《中文化改写 SOP》——明确「译什么 / 不译什么 / 并置规范 / 术语对照」四张清单；② 提供门禁 `scripts/check_localization.py`——逐行判定疑似英文散文行是否已译（SKILL.md 硬问题、references 警告），并比对技术锚点（hex 色值 / 字体名）与引用完整性；支持单目录与 `--batch`（清单文件或父目录，聚合出 md 报告与逐项待译行数）；③ 中文化在结构转换之后进行，**不改变引用语义**；④ 中文化后**必须复跑**门禁，交付用 `scripts/pack_zh.py` 重打纯技能内容 zip（不含内部文档，校验许可随包）。
- 验收判据：`check_localization.py` 返回 PASS（中文字段达标、SKILL.md 覆盖率 ≥ 下限、技术锚点无丢失、无悬空引用）；零 FAIL；正文无中英夹杂整句。**另看「正文体量」列**——覆盖率的分母是当前文本，删短正文会让分母缩小、覆盖率虚高，故体量过小会告警，须与源比对后再判定。样例见 `references/localization-zh.md` 第五节。
- 边界：语义翻译非脚本能力，门禁只做**判定**（覆盖率 / 锚点 / 引用），实际翻译由 LLM 或人工按 SOP 执行。**其引用检查口径比平台校验器与自检更宽**（任意 `a/b.ext` 而非仅三标准目录），因此会扫出后两者看不见的「跨目录路径引用」——那多为上游对**所在仓库布局**的叙述性引用（非本包文件、搬运未丢），须按语义判定：叙述可留（加语境声明）、指令必改，**不可一律当缺陷**。
- **翻译流水线（v2.3.0 起）**：中文化拆为四道工序、中间产物解耦，只组合入口不拆散技能——① `scripts/make_translation_plan.py` 自动生成 `translation-plan.md`（frontmatter 决策项 / 标题树与行号区间 / 代码块与表格定位 / 疑似骨架段 [重写] 标记 / 路径核对清单），消灭「通读」耗时；② 术语口径以 `references/glossary.md` 为唯一标准（实证词频回收，新词只追加），消灭「同词异译」；③ 逐段翻译按计划执行，术语查表、判断活不跨工序交接；④ 合成后照常双门禁。编排细节见 `references/translation-pipeline.md`。

**能力 7 · 外部候选榜单桥接（雷达类报告 → 可搬源清单）**
- 用户目标：另一套流程每天产出「新仓库候选榜单」，直接接进来把其中有价值的搬成技能。
- 对标基准：人工逐个打开仓库确认有没有 SKILL.md，再手写清单。
- 可验证差异：① `scripts/bridge_trending.py` 解析候选报告（markdown 表格、竖线表、被压平的一行一格粘贴格式），提取去重后的 `owner/repo`；② 用文件树探测把仓库归为 **A 可直接搬（含 SKILL.md）/ B 需创作技能（有 AGENTS.md、CLAUDE.md、.claude-plugin 等载体）/ C 不可搬**，A 类展开到每个 `SKILL.md` 父目录，产出可直接喂 `--batch` 的 `manifest.txt`；③ 许可风险（AGPL / GPL / 无 LICENSE / 未知）单列成区，默认仍写入清单供人工定夺，`--exclude-risk` 可机器剔除；④ 同时产出 `trees.json` 文件树缓存，供搬运阶段 `--tree-cache` 复用，**彻底免掉二次 API 调用**。
- 验收判据：`bridge-report.md` 三分类完整、C 类有逐条理由、许可风险单列；`manifest.txt` 每行形如 `owner/repo@branch/<子路径>`；搬运阶段带 `--tree-cache` 无 403 限流；`batch-report.md` 内 slug 唯一无覆盖。
- 联动要点（详见 `references/bridge-radar.md`）：雷达与转换引擎**筛选口径不同**——实测同一榜单前 20 名里只有 2 个仓库含 SKILL.md，而被许可扣分挤到榜外的候选里反而有 5 个。**风险专区是技能富矿，不是垃圾区。**

**能力 8 · 跨会话共享缓存与能力公示**
- 用户目标：多个会话并行干活时，不重复下载源码、不重复探测文件树、不重复搭管线。
- 对标基准：每个会话在各自目录各存一份 `_src_cache/`、各存一份本地 `trees.json`（实测同一份源码曾出现 4 份副本）。
- 可验证差异：① **共享复用**——`scripts/shared_cache.py` 把可跨会话复用的中间产物收敛到用户级共享层 `~/.workbuddy/shared/`（`src/` 源码、`trees/` 文件树、`licenses/` 许可证）；转换引擎默认接入，`resolve_github()` 首选共享命中（**零下载、零 API 调用**），`--no-shared-cache` 可关。② **能力公示**——启动时经 `_announce_self()` 向共享层 peers 目录写会话能力名片，并重渲染名册 `PEERS.md`；稳态退化为 `heartbeat()` 续期。③ **能力发现**——`peers` 看名册、`find <关键词>` 查能力；程序内 `shared.find_peer()` 取回对方 `root + entry + contract` 跨会话调用。④ **防重复建管线**——共享层索引 `INDEX.md` 登记主题级权威产物，收工用 `index --add` 追加。
- 验收判据：二次搬运同一技能出现「命中用户级共享源码缓存」提示且耗时显著下降；`stats` 命中计数增长而 `downloads` / `api_calls` 不增长；`PEERS.md` 含本会话条目。
- 边界（必读）：会话之间**没有实时消息总线**，名片是**异步公示**——对方下次运行时才读得到；已结束的历史会话不会自己报到，只能由他方核实后**代登记**（`registered_by` 字段标出）。协议见 `~/.workbuddy/shared/HOW-TO-CONNECT.md`。

**能力 9 · 许可准入门禁与许可随包**
- 对标基准：只填对 `license` 字段，产出内**不含任何许可文本**（实测某批次 36 个目录 / 18 个 zip 的 LICENSE 数为 **0**）；无许可仓库被照搬。
- 可验证差异：**两道具门**（「能否搬运」与「能否上架」分开）——`unknown` 默认**拒收**、`copyleft` 仅本地不出包、`permissive` 双轨且**强制随包** `LICENSE` 与 `THIRD-PARTY-NOTICES.md`；`AGPL-3.0` 匹配排在 `GPL-3.0` 之前，避免误判漏掉第 13 条部署义务。
- 验收判据：无许可源拒收且退出码非 0；GPL 源无 zip 且标注「不得对外分发」；宽松许可源的目录与 zip 均含两份许可文件。
- 边界（必读）：**工程侧形式合规，不是法律意见**；「是否侵权」是事实判断，票数与评分均不能覆盖。分级表与 AGPL 第 13 条见 `references/compliance-gates.md` 第一节。

**能力 10 · GitHub 之外的采集源接入与上架物料**
- 对标基准：只认 GitHub 地址与本地目录；产出说明写死「由 **GitHub** 源迁移而来」；上架标题 / 简介 / 标签全靠人工另整。
- 可验证差异：① **接入契约**——素材根放 `SOURCE_INFO.json`，新增采集平台**无需改工具代码**；该文件不进产出，信息进归属声明；② **两级粒度**——`--material-root` 可把采集端的**仓库级**素材根展开为技能级源并继承来源与许可；③ **上架物料**——`--listing` 出 `listing/<slug>.md` + `上架清单.md`。
- 验收判据：素材通过准入且归属声明含 `source_url` / 采集平台 / 采集日期；产出内不出现该文件；清单只收**平台校验通过**的产出。
- 边界（必读）：只做**结构化提取**，不写文案、不做中文化；模板化假简介会被识别并标注「待改写」，**不伪造成稿**。契约字段、两级粒度与实测规模见 `references/merge-and-material.md` 第七节。

**能力 11 · 去毒审计（上架前强制工序）**
- 对标基准：只搬不检；或只覆盖 3 种密钥格式（原 `audit_skill.py` 仅识 `sk-` / `ghp_` / `AKIA`）。
- 可验证差异：`scripts/scan_toxicity.py` 以 **35 条规则 / 6 类**静态扫描（凭据泄露、提示词注入含 Trojan Source、危险执行、敏感读取、路径遍历、供应链）；`hard` **阻断交付并撤下上传包**，`review` 列入待人工确认；默认执行。
- 验收判据：含 `rm -rf /`、`.ssh` 读取、`curl|sh`、越权指令、明文 API Key 的样本报 `REJECT` 且退出码 1；干净样本报 `CLEAN`；报告含「去毒」列。
- 边界（必读）：**静态正则扫描，不是安全认证**（有漏报与误报）；`review` 级去噪合并、`hard` 级不合并。规则明细见 `references/compliance-gates.md` 第二节。**这是「刮取谁都会、净化不是」里的净化那一段。**

**能力 12 · N:1 合并（同能力多配置收敛为单一技能）**
- 对标基准：把 N 个相似源一股脑塞进一个目录当「合并」——那是堆叠；或逐个独立交付，产能上不去。
- 可验证差异：`scripts/merge_skills.py` 四道闸——① **相似度准入闸**（低于阈值即判「不同能力」**拒绝合并**）；② **许可一致性闸**；③ **零丢失验收**（每成员正文逐行覆盖率须 100%）；④ **平台校验闸**。通过者共同部分逐行保留、差异抽成「变体配置」表，合并稿取**中性身份**。另有 `--scan` 只提议不产出。
- 验收判据：astra 双子（445 行中 437 行相同）→ 相似度 0.974、共同 441 行、差异 6 处、**两成员各 284 行校验丢失 0 行**、平台校验 11 ok / 0 FAIL；`--scan` 对 22 项报「1 组可合并 + 20 项独立」。
- 边界（必读）：只做「同能力多配置」（M1），不做 M2、不做跨能力堆叠；**合并是去重不是造新性质，故不记入 `COMBINATION_LAB` 台账**。细节见 `references/merge-and-material.md`。

**能力 13 · 组合实验台（跨能力拆解与重组，产出新技能草稿）**
- 用户目标：把已交付技能的方法论拆成可复用单元，按一个新的用户目标组合成前所未有的新技能。
- 对标基准：整技能堆叠（几个 SKILL.md 拼一目录，判据冲突、引用悬空、目标涣散）。
- 可验证差异：① `scripts/decompose_skills.py` 按**二级标题段**拆解为四类单元（能力/执行流程/边界/自检），排除搬运说明，自含性校验，逐单元溯源到源行号；② `scripts/compose_skill.py` 按组合规格生成新技能草稿，**三道硬闸**（目标先行 ≥20 字 / 单元存在且自含并写明角色 / 组合级边界与自检各 ≥2 条）加**资源随迁闸**（单元引用的包内文件自动搬迁，实测拦截 goldie 的 2 处悬空引用）；③ 组合稿整体定位**草稿**：双门禁通过 ≠ 可上架，语义冲突由人工终审。
- 验收判据：实测 22 技能拆出 **212 单元**；三例组合（上架素材工坊 / 运营晨报 / 客服接地答复，均跨 3 技能）双门禁全绿；产物与规格存档可复现。规则与分工见 `references/combination-lab.md`。
- 边界（必读）：**与合并引擎准入闸相反**——合并收同、组合收异；脚本级功能不可组合（组合稿不承诺跨技能代码互通）。

## 三、执行流程

### 第 1 步 · 定位源技能
- 动作：`scripts/port_skill.py` 自动识别两类源：
  - **GitHub 地址**：`owner/repo`、`owner/repo@branch`、`owner/repo/sub@branch`、`owner/repo@branch/sub` 或完整 `github.com` URL——无需手动下载。**分支位置两种写法都支持**（早期版本只前者可用却写了后者，会误解析为 `sub@branch` 并报「GitHub 源无文件」）。
  - **本地目录**：已下载的技能目录直接读取。
  - `--source-type auto|local|github` 显式指定，默认 auto（本地优先，否则尝试 GitHub）。
- **下载机制**：文件树经 GitHub API；文件内容**首选 `codeload.github.com` 整仓 tarball**（1 次请求拿全部文件），失败或超 300 MB 回退 jsDelivr 逐文件。实测本机经代理时 tarball 约 1 秒稳定成功，而 raw / jsDelivr 单文件各需 10~13 秒且频繁 502——**这是批量耗时的决定性差异**。
- **批量形态**：单源用位置参数；多源用 `--batch manifest.txt`（每行一个源，`#` 注释）或多次 `--source`。GitHub 与本地源可混用。
- **外部榜单接入**：源来自外部候选榜单时，先用 `scripts/bridge_trending.py` 建桥筛出 A 类源，详见 `references/bridge-radar.md`。
- 判据：解析后得到含 SKILL.md 的源目录。GitHub 源**优先命中共享源码缓存** `~/.workbuddy/shared/src/`（零下载零 API）；未命中才拉取，落点亦为该目录；`--no-shared-cache` 时回退输出根下 `_src_cache/`。
- 兜底：GitHub 拉取失败时报错并引导改用本地目录；批量模式下单源失败不阻塞其余。

### 第 2 步 · 体检扫描
- 动作：`scripts/audit_skill.py <源目录>`，生成五类风险报告。
- 判据：覆盖外部依赖、目录层级、命名保留词、许可证、工具名五类，每项有「阻断 / 降级 / 通过」判定。
- 产出：`<输出根>/<slug>-audit.md`。
- 兜底：脚本不可执行时，按 `references/migration-checklist.md` 清单人工核对并标注「手工体检」。

### 第 3 步 · 处置决策
- 动作：按结论决策。阻断项必改（改名、拉平、补字段）；降级项改写（联网改内置、第三方包改标准库或文字规则）；通过项原样保留。
- 判据：无未处置的阻断项；每个降级项在改动清单有对应记录行。
- 兜底：无法降级的依赖写入技能「不适用于」边界并说明原因。
- 强依赖特例：pillow / numpy / imageio 等**无法用标准库重写的强第三方依赖**属不可降级项——**仅产本地版、不生成平台版 zip**，并在改动清单与报告中标注「平台版不可交付」。

### 第 4 步 · 规格转换
- 动作：`scripts/port_skill.py <源> --out <输出根> [--source-type auto|local|github]`（单源），或 `--batch manifest.txt` / `--source A --source B`（批量），按 `references/field-mapping.md` 补全七项必填字段（`license` 缺失或非标准时自动读根目录 LICENSE / COPYING 识别 SPDX）、拉平目录、重写正文中的资源路径引用（完整路径、唯一文件名、目录引用三类）。
- 说明：非标准代码目录（含 .py）映射到 scripts 时**保留模块原名**（如上游 `core` 目录中的 `gif_builder.py` 落为 `gif_builder.py`），并同步改写 `from core.xxx import` 引用；检测到强第三方依赖时跳过平台版 zip。
- 判据：平台版仅含 `references/` `scripts/` `assets/` 三个一级目录且无嵌套；目录名与 `name` 一致。
- 产出：平台版目录、本地版目录、zip、改动清单 `porting-changes.md`。
- 兜底：源正文缺「执行流程 / 边界与降级 / 质量自检」段落时，加 `--ensure-sections` 补骨架（带补写标注），或人工补写；脚本不可执行时按映射表与目录规则手工完成，产物形态一致。

### 第 5 步 · 合规校验、去毒审计与平台复核
- 动作：`port_skill.py` 转换结束时已**自动运行三道门禁**——① 交付前自检门禁（七项字段、目录层级、引用完整性双向校验、**平台结构段落**）；② **去毒审计**（`scan_toxicity.py`，35 规则 / 6 类）；③ **平台官方校验器复核**（自动定位 `validate_skill.py` 独立跑一遍）。改动清单同时给出三项结论；任一门禁报硬问题即非零退出，去毒 `REJECT` 还会**撤下上传包**。
- 判据：自检 PASS（或已修复全部硬问题）；去毒为 `CLEAN` 或 `REVIEW` 且 `review` 项逐条判定完毕；**平台校验判「通过」**；零 FAIL；警告项逐条确认或修复。
- 兜底：报「缺少某类段落」时用 `--ensure-sections` 补骨架后按源内容改写——**这只是结构合规，内容是通用骨架，必须改成具体条目才能上架**；提示联网或安装语句残留时，改为内置知识优先并保留离线路径后复检；去毒报硬问题时按报告「处置」列修复（凭据改环境变量、管道执行改为先校验后执行、越权指令删除），无法修复即拒收；无校验脚本时按 `references/migration-checklist.md` 交付前检查表手工核对。
- **为什么必须跑平台校验器**：自检只覆盖「我认为平台会查的项」，**不能替代平台门禁**。实测——自检 PASS 的 21 个产出被平台校验器**全部判 FAIL**。**自检比平台松，就会漏放。**

### 第 6 步 · 交付
- 动作：按 `assets/migration-report.template.md` 出迁移报告，按 `assets/README.port.template.md` 出安装与上传说明。
- 判据：三件产物齐全（平台版 zip、本地版目录、迁移报告），报告含体检结论与改动摘要。
- 兜底：打包失败时交付技能目录，并说明手工压缩要求（zip 根目录直接放 SKILL.md）。

## 四、输出规范

- 落盘位置：`<工作目录>/skill-build/` 下分 `port/<slug>/`（平台版）、`port/<slug>-local/`（本地版）、`dist/`（zip 与报告）。
- 命名规则：slug 为小写字母与连字符，长度 ≤64，不含保留词；zip 名为 `<slug>.zip`。
- 报告结构：源信息 → 体检结论 → 改动清单 → 残留风险 → 安装与上传步骤。
- 双轨差异：平台版零联网零外部依赖、两级目录、root 直铺；本地版保留原始脚本与嵌套结构，允许联网与第三方依赖。强第三方依赖的技能只产本地版（沙箱无网无包）。
- 许可随包：平台版与 zip 内均含 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`；本地版在原目录无许可文件时补写 `LICENSE`。
- 上架物料（`--listing`）：`<输出根>/listing/<slug>.md` + `上架清单.md`，只收录可上架产出（排除 copyleft / unknown / 自检 FAIL / 强依赖 / **平台校验不通过**），每项标明平台校验结论与结构段落是否已改写。
- 合并（`--scan` / 合并模式）：`merge/<slug>/`（`SKILL.md` 含「变体配置」表 + `LICENSE` + `THIRD-PARTY-NOTICES.md` + `merge-report.md`），扫描报告落输出根的 `merge-scan-report.md`。
- 去毒审计：结论写入各 `<slug>/porting-changes.md`「六」节与 `batch-report.md`「去毒」列；独立报告用 `scan_toxicity.py <目录> --out <路径>`。

## 五、边界与降级

- 信息不足（只给仓库名不给具体技能）：取默认分支的技能列表让用户选；未选则取 README 主推的第一个并标注「假设」。
- 环境受限（无网络）：跳过在线抓取，改走本地目录输入；转换与校验均离线完成，交付完整性不下降。
- 环境受限（无脚本执行）：按 `references/field-mapping.md` 与 `references/migration-checklist.md` 手工执行同样规则，产物形态一致。
- 源技能非 Agent Skills 格式（无 frontmatter）：先按模板补最小 frontmatter，再走流程，并标注「源格式非标准」。
- 许可未识别或缺失：**默认拒收**（不产任何版本）。作品自创作完成即受《伯尔尼公约》与中国《著作权法》保护，**无 LICENSE ≠ 可自由复制**，复制加重分发本身即构成侵权，民事上不以营利为前提。已确认有权搬运时用 `--allow-restricted` 放行，产出仅本地版、不生成上传包、强制标注风险。
- 许可为 copyleft（GPL / AGPL / LGPL）：仅产本地自用版，不生成上传包。AGPL 第 13 条触发条件是「**修改** + 通过网络对外提供交互服务」，原样部署不触发，但商业差异化几乎必然要改，且「未修改过」极难自证——按最保守口径处理。
- 许可为 source-available（如 anthropics 的 docx / pdf / pptx / xlsx）：提示不得公开发布，仅产本地自用版，平台上传需自行取得授权。
- 上架物料中的一句话简介：若自动补全的模板句被识别，会回落到源技能真实描述并标注「待运营层改写」，**不把模板句当成品简介交付**。

## 六、质量自检

- [ ] 体检报告覆盖五类风险且结论明确
- [ ] frontmatter 七项必填齐全；YAML 无冒号 / 直引号风险；目录层级 ≤2；目录名与 `name` 一致；无占位符残留
- [ ] zip 为 root 直铺，根目录可见 SKILL.md；本地版保留原脚本与原结构
- [ ] 平台版无联网强依赖、无第三方 import、无平台外工具名；强依赖技能已仅产本地版、未生成平台 zip；强依赖判定未误报（`requests` 等普通词不应触发）
- [ ] `license` 已落标准 SPDX（源含 LICENSE 时自动识别；子路径源已从仓库根兜底）
- [ ] 改动清单为 PASS 或硬问题已修复：无悬空引用、无未引用搬迁文件（或已列待确认）；逐条可追溯
- [ ] 批量模式：根目录出 `batch-report.md`；每 `<slug>/` 含 `porting-changes.md`；**无同名 slug 覆盖**；有硬问题或失败源时整体退出码非 0，成功项不受影响
- [ ] 外部榜单接入带 `--tree-cache` 复用文件树，无 API 限流报错
- [ ] 中文化（如执行）：按 `references/localization-zh.md` 保留不译项，复跑门禁零 FAIL，交付 zip 不含内部文档；批量产出用 `--batch` 一次过，达标数 = 待上架数
- [ ] 门禁报出的「跨目录路径引用」（非 `references|scripts|assets`）已逐条按**语义**判定：叙述性 → 保留或加语境声明，指令性 → 改写或拒收；**未把「平台校验 PASS」当作内容完整性通过**
- [ ] 跨会话复用已生效：二次搬运同一技能报「命中共享源码缓存」且无新增下载 / API；工作目录内**未遗留**自建 `_src_cache/` 或本地 `trees.json`
- [ ] 本会话能力已公示：`shared_cache.py peers` 可查到本会话条目；代登记条目的 `registered_by` 非 `self`
- [ ] 许可准入门禁已生效：无许可 / 未识别源被**拒收**（退出码非 0）；copyleft 源无 zip 且标注「不得对外分发」；宽松许可源未被误拒
- [ ] 许可随包：抽查 zip 内清单，每个可分发产出均含 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`
- [ ] 采集源接入：`SOURCE_INFO.json` 的来源与许可已进归属声明，且该文件**未**出现在产出目录内
- [ ] 上架物料（如用 `--listing`）：清单条目数 = 可上架源数；模板化简介已标注「待运营层改写」，未冒充成品
- [ ] 去毒审计结论明确：改动清单含 `CLEAN / REVIEW / REJECT` 行；`REJECT` **未产出 zip**；`review` 项已逐条人工判定（未把「待确认」当「已通过」）
- [ ] **平台校验已跑通**：官方校验器对每个待上架产出判「通过」，报告含该列与统计；**未用自检结论替代平台结论**
- [ ] **结构段落已改写**：补过骨架的产出，三段落已按源技能内容换成具体条目
- [ ] 合并（如执行）：最低相似度 ≥ 阈值；**每成员逐行覆盖率 100%**；差异已逐项落表；合并稿为**中性身份**；平台校验通过；**未把不同能力塞进一处**
- [ ] 仓库级素材根接入（如用 `--material-root`）：技能级产出继承仓库级来源与许可且见于归属声明；无 SKILL.md 的仓标注为「需创作技能」而非报错

## 七、资源说明

- `references/field-mapping.md` —— 字段映射、补全规则、YAML 硬约束、双轨差异
- `references/migration-checklist.md` —— 五类风险体检清单与交付前检查表
- `references/porting-cases.md` —— 典型源仓库搬运要点与已验证处置
- `references/localization-zh.md` —— 中文化改写 SOP 与样例
- `references/glossary.md` —— 术语表（EN → zh 唯一口径，实证词频，新词只追加）
- `references/translation-pipeline.md` —— 翻译流水线编排：四道工序、中间产物、验收判据
- `references/combination-lab.md` —— 组合实验台：拆解与重组规则、可行性边界、与合并引擎的分工
- `scripts/make_translation_plan.py` —— 工序 A：自动抽取翻译作业计划（只分类不改写）
- `scripts/decompose_skills.py` —— 组合实验台·拆：技能 → 四类能力单元库（JSON + 人读摘要）
- `scripts/compose_skill.py` —— 组合实验台·合：按规格从单元库生成新技能草稿（三闸一资源随迁）
- `references/bridge-radar.md` —— 榜单桥接 SOP：三分类口径、许可风险单列、两条硬约束、批量三坑
- `references/compliance-gates.md` —— 许可准入分级与 AGPL 第 13 条、许可随包依据、去毒六类规则、采集契约与上架字段
- `references/merge-and-material.md` —— 合并四道闸实测锚点、中性身份失效模式、合并≠组合、契约两级粒度、自检≠平台门禁
- `scripts/audit_skill.py` —— 可迁移性体检，输出五类风险报告
- `scripts/bridge_trending.py` —— 榜单桥接：解析报告 → 三分类 → `manifest.txt` / `bridge-report.md` / `trees.json`
- `scripts/check_localization.py` —— 中文化门禁：字段、覆盖率、技术锚点、引用完整性；支持 `--batch`（清单文件 / 父目录）批量与 md 报告
- `scripts/pack_zh.py` —— 中文化交付打包：重打**纯技能内容**的 `<slug>-zh.zip`（root 直铺、排除 `porting-changes.md` 等内部文档、校验许可随包）
- `scripts/scan_toxicity.py` —— 去毒审计：35 规则 / 6 类静态扫描，`hard` 阻断上架
- `scripts/merge_skills.py` —— N:1 合并引擎：相似度准入 → 差异保真 → 零丢失验收 → 平台校验；`--scan` 只提议
- `scripts/shared_cache.py` —— 跨会话共享缓存与通讯录：复用（`stats` / `migrate` / `clean`）、能力（`announce` / `heartbeat` / `peers` / `find`）、索引（`index`）
- `~/.workbuddy/shared/HOW-TO-CONNECT.md`（运行时位置，非随包分发）—— 跨会话接入协议
- `scripts/port_skill.py` —— 规格转换与双轨产出
- `assets/migration-report.template.md` —— 迁移报告模板
- `assets/README.port.template.md` —— 安装与上传说明模板
