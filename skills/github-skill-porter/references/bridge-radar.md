# 采集雷达 → 转换引擎 联动 SOP

> 适用场景：另一套流程（GitHub 采集雷达，日更）产出一份候选仓库报告，
> 需要把其中有价值的部分接进转换引擎，产出可安装 / 可上传的技能包。
> 本文件是该联动的唯一权威说明，`scripts/bridge_trending.py` 是它的实现。

---

## 一、为什么需要桥

雷达与转换引擎的**筛选口径不同**，不能直接对接：

| | 采集雷达 | 转换引擎 |
|---|---|---|
| 输入 | 按 `created` 与 `stars` 抓取的候选仓库 | 单个**技能目录**（须含 `SKILL.md`） |
| 排序依据 | 增速 / 采用深度 / 窗口期 / 许可 / 活跃 / 本地化 / 商业空白 | 不排序，只做转换 |
| 产出 | 一份 markdown 榜单 + 变现建议 | 平台版 zip + 本地版目录 + 改动清单 |
| 粒度 | 仓库 | 仓库内的某个技能目录 |

把榜单里的 `owner/repo` 直接喂给 `port_skill.py --batch`，会因为**榜上绝大多数仓库
根本不是 Agent Skills** 而大面积失败。桥要做的，是先按「可搬运性」筛一遍。

---

## 二、桥的三分类口径

`bridge_trending.py` 对每个仓库取文件树，按以下规则归类：

| 类 | 判定条件 | 处置 |
|---|---|---|
| **A 可直接搬** | 树中存在 `SKILL.md`（可能多个） | 每个 `SKILL.md` 的父目录是一个独立可搬源，写入 `manifest.txt` |
| **B 需创作技能** | 无 `SKILL.md`，但有 `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` / `.cursorrules` / `.claude-plugin/` | 交给技能生成器**从零创作**，不要喂转换引擎 |
| **C 不可搬** | 其余（普通工程仓库、教程、模型权重） | 跳过，报告里留档说明 |
| **? 探测失败** | API 失败 / 仓库过大 trees 被截断 | 人工确认，可改用本地目录输入 |

判定必须是**文件树级**的，不能靠 README 措辞猜——实测同一榜单里
`kruzovic7/ai-data-extractor`（名字像技能）实为普通 Python 脚本仓库，
`anthropics/commerce-agents`（名字像应用）却含 **16 个 SKILL.md**。

---

## 三、许可风险必须单列（联动里最容易被忽略的一环）

雷达的许可维度是**扣分制**：MIT / Apache-2.0 记满 20 分，AGPL-3.0 记 8 分，
无 LICENSE 仅记 2 分。这会把 copyleft 与未声明许可的项目**结构性地挤出前 20 名**。

实测后果（2026-09-14 那份报告）：采集端榜前 20 里只有 **2** 个仓库含 `SKILL.md`；
而被扣分排到「许可风险专区」的候选里，仅前 15 个就有 **5** 个含 `SKILL.md`。
**转换引擎唯一的货源，恰好被雷达的排序规则推到了榜外。**

因此：

- 风险专区**不是垃圾区，而是技能富矿**，必须单独跑一遍；
- `bridge_trending.py` 默认把 A 类全部写入 `manifest.txt`，同时在报告里标注
  「AGPL 传染性条款 / 默认保留全部权利 / 许可未知」，让**人**决定是否踩线；
- 需要机器直接剔除时加 `--exclude-risk`，但默认不剔除——**搬运 ≠ 商用**，
  自用与本地版不受许可限制，只有对外分发与 SaaS 才需要。

---

## 四、两步执行

```bash
SCRIPTS=<github-skill-porter>/scripts
PY=<python>

# 第 1 步：建桥 —— 解析报告、探测分类、产出源清单与文件树缓存
"$PY" "$SCRIPTS/bridge_trending.py" radar-2026-09-14.md --out _radar/2026-09-14
#   产出：manifest.txt（A 类源）、bridge-report.md（三分类 + 许可风险）
#         trees.json（文件树缓存）、bridge-rows.json（机读明细）

# 第 2 步：搬运 —— 必须带 --tree-cache 复用上一步已探到的文件树
"$PY" "$SCRIPTS/port_skill.py" --batch _radar/2026-09-14/manifest.txt \
      --tree-cache _radar/2026-09-14/trees.json --out _radar/2026-09-14/port
```

---

## 五、两条硬性约束（都踩过）

### 1. `--tree-cache` 不是可选优化，是必需项

桥探一次文件树、搬运再探一次，同一个仓库会被打两次 GitHub API。
GitHub **未认证限流只有 60 次/小时**，20 个仓库就要 40 次，批量搬运必然撞墙。
带 `--tree-cache` 后搬运阶段**零 API 调用**，只下载文件内容。

### 2. 文件内容走 codeload tarball，不要走 CDN 逐文件

实测本机出口（经代理）：

| 链路 | 耗时 | 成功率 |
|---|---|---|
| `raw.githubusercontent.com` 单文件 | 10.5 s | 502 失败 |
| `cdn.jsdelivr.net` 单文件 | 12~13 s | 频繁 502 |
| `codeload.github.com` **整仓 tarball** | 0.8~1.4 s | 稳定 |

`resolve_github()` 已把 codeload tarball 设为首选、jsDelivr 为回退，
并对同一仓库做进程内缓存（多个子技能只下一次）。
实测 18 个源的完整批量：**3.2 秒**（改进前 3 个源就要 4.5 分钟）。

---

## 六、批量模式的三个已知坑（均已修，作为回归项保留）

1. **同名 slug 静默覆盖**：`profiles/plus/.../astra-orchestrator` 与
   `profiles/pro/.../astra-orchestrator` 会产出同一个 slug，后者覆盖前者且
   `porting-changes.md` 一并被覆盖——静默丢数据。现已在批量开工前**预扫描**
   同名技能并统一分配带前缀的消歧 slug（`plus-astra-orchestrator` /
   `pro-astra-orchestrator`），另保留运行中兜底检查。
2. **子路径源的许可证识别失效**：从大仓库搬子技能时，`LICENSE` 在**仓库根目录**，
   不在技能目录内，只扫技能目录会导致 `license` 字段整体为空。
   现已从 tarball 注入仓库根 LICENSE 文本作兜底，并在改动清单里标明来源。
3. **强依赖误报**：早期对全部文本做裸词匹配，正文里出现「requests」就被判成
   强第三方依赖，进而阻断平台版 zip 生成。现只在三种语境下判定——
   代码文件的 `import`/`require`、依赖清单文件、安装命令行。

---

## 七、交付判据

- [ ] `bridge-report.md` 三分类完整，C 类有逐条跳过理由
- [ ] 许可风险项已单列，且已就「是否商用」做出人工判断
- [ ] `manifest.txt` 只含 A 类源，每行形如 `owner/repo@branch/子路径`
- [ ] 搬运阶段带 `--tree-cache`，无 API 限流报错
- [ ] `batch-report.md` 里每个 `PASS` 项的 slug 唯一（无覆盖）
- [ ] `FAIL` 项已逐条定位：属本工具缺陷还是**上游技能自身缺陷**，自检报告里会区分
- [ ] B 类仓库已转交技能生成器，未混入搬运清单

---

## 八、联动之外的下一步（给雷达那一侧的建议）

桥只解决「搬得来」。要让联动真正产生价值，雷达侧建议加一个维度：

**技能可搬运性**——在评分里增加「仓库是否含 `SKILL.md` / `AGENTS.md`」的探测。
现在这一信息完全由搬运侧事后发现，等于每天都要用 60 次 API 额度去换一个
「能不能搬」的是非题。若雷达在采集候选池时就标注该字段，桥可以退化成纯解析器，
省掉全部探测调用。
