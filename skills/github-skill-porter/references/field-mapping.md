# 字段映射与转换规则

> 用途：第 4 步规格转换的唯一依据。源标准 = Agent Skills（agentskills.io），目标标准 = WorkBuddy 开放平台。

## 零、源类型与获取（第 1 步）

`port_skill.py` 的输入 `<源>` 支持两类，由 `--source-type auto|local|github` 控制，默认 auto（本地目录优先，否则尝试 GitHub）：

| 源类型 | 输入形态 | 获取方式 |
|---|---|---|
| 本地目录 | 已下载的技能目录路径 | 直接读取，无需联网 |
| GitHub 地址 | `owner/repo`、`owner/repo/sub@branch`、完整 `github.com` URL | 内置经 GitHub API（`git trees` 取文件列表）+ jsDelivr CDN（逐个下载），拉取到输出根下的 `_src_cache/` |

- 网络限制：jsDelivr 树 API（`data.jsdelivr.com`）偶发 502，已改用 GitHub API 取列表；下载仍走 CDN。两者均带 3 次重试兜住临时网关错误。
- 拉取失败时（代理/网关持续不可用）：报错并引导改用本地目录输入，不阻塞转换流程。
- 指定子路径 `sub`（如 `skills/theme-factory`）只拉取该技能，避免大仓库整仓下载。

## 一、源与目标字段对照

| Agent Skills 源字段 | WorkBuddy 目标字段 | 转换规则 |
|---|---|---|
| `name` | `name` | slug 化后去保留词，≤64 字符，小写字母数字连字符，不以连字符起止 |
| `description` | `description` | 原文保留，改写为「何时使用 + 产出什么 + 不适用于」三段式，≤1024 字符 |
| — | `version` | 无源值时填 `1.0.0`；源有 `version` 则沿用并标注来源 |
| — | `display_name` | 源有中文名用之；否则由 slug 生成简洁中文名（≤12 字） |
| — | `display_name_en` | 由 slug 生成 Title Case 英文名，词间空格 |
| — | `description_zh` | 源 description 含中文则取其首句（≤60 字）；否则按「动词 + 对象 + 适用场景」生成中文短句 |
| — | `description_en` | 源 description 首句英文，≤200 字符，去掉未引号的「冒号+空格」 |
| `allowed-tools` | `allowed-tools` | 按工具名映射表转换，无法映射者删除并在报告标注 |
| `license` | `license` | 保留原值；源文件为 source-available 时标注风险 |
| `metadata.*` | — | 平台不识别，下沉为 `references/` 内的 `origin-metadata.md` |

## 二、slug 化与保留词处理

1. 取源 `name`，转小写，非 `[a-z0-9]` 字符统一替换为连字符，合并连续连字符，去除首尾连字符。
2. 保留词处理：若 token 命中 `claude`、`anthropic`、`claude-code`、`chatgpt`、`gpt`、`gemini`、`copilot`、`codex`，删除该 token。
   - 实证：Anthropic 曾将 `claude-academy-guide` 改名为 `academy-guide`，原因即技能名不得含保留词。
3. 删除保留词后若为空，回退为 `ported-skill` 并在报告中标注需人工命名。
4. 长度 >64 时按 token 边界截断，保留完整词。

## 三、YAML 硬约束（转换后必检）

| 约束 | 违规样例 | 修复 |
|---|---|---|
| 值内不得出现未引号的「半角冒号+空格」 | `description_en: port skill: need network` | 改用 `via`/`with`，或整值加英文双引号 |
| 禁止中文引号 | `description_zh: “搬运”` | 改为不加引号或使用英文引号 |
| 冒号后必须有空格 | `name:foo` | 写为 `name: foo` |
| 多行值用块标量 `|` 且内容行缩进 | 多行值直接换行 | 改为 `\|` + 缩进 |
| 值内不得出现尖括号 | `<skill-name>` | 改为 `SKILL 名` |

## 四、目录拉平规则

源技能常见嵌套（如 `scripts/helpers/`、`references/guides/`），平台只认两级。映射策略：

1. 相对路径第一段命中 `references` / `scripts` / `assets` → 目标目录取该段。
2. 未命中时按扩展名归类：`.py` `.sh` `.js` `.ps1` → `scripts/`；`.md` `.json` `.yaml` `.yml` `.txt` `.csv` → `references/`；其余 → `assets/`。
3. 被压平的中间路径用双下划线连接进文件名，例如 `scripts/helpers/make_doc.py` → `scripts/helpers__make_doc.py`。**例外：非标准一级代码目录（含 .py 的目录，如 `core/`）映射到 `scripts/` 时保留模块原名、不嵌入父目录名**——`core/gif_builder.py` → `scripts/gif_builder.py`，以避免破坏 `from core.gif_builder import` 这类导入。
4. 重名冲突追加序号后缀 `-2`、`-3`。
5. 转换后同步替换正文中的旧路径引用，保证 `references/xxx.md` 形式的引用全部真实存在。

## 五、正文资源引用重写

重写分三类，按 A → B → C 顺序执行，覆盖标准目录之外的引用：

| 类别 | 形态 | 样例 | 处理 |
|---|---|---|---|
| A 完整路径 | 带目录的文件路径 | `themes/arctic-frost.md` | 按搬迁映射表替换为 `references/themes__arctic-frost.md` |
| B 唯一文件名 | 不带目录的文件名 | `theme-showcase.pdf` | 该 basename 在映射中唯一时，替换为 `assets/theme-showcase.pdf`；不唯一则不动 |
| C 目录引用 | 目录名加斜杠 | `themes/` | 替换为搬迁后的目标目录 `references/`，并在改动清单提示「目录下文件已重命名为 `themes__<name>`」 |
| D 代码模块引用 | `包名.模块名` 形式 | `core.gif_builder` | 非标准代码目录迁移时，替换为搬迁后的裸模块名 `gif_builder`（如 `from core.gif_builder import` → `from gif_builder import`）；改写后请按平台执行模型核对 import 形式 |

执行规则：
1. 先按 A、B 替换文件级引用，再按 C 替换目录级引用。
2. 只替换命中搬迁映射表的字符串；含 `://` 的 URL 不处理。
3. C 类只改目录名，正文中的具体文件名表述需人工核对（机械替换无法表达「一批文件」的语义）。
4. 替换后逐一校验 `references|scripts|assets/` 形式的引用真实存在；不存在的列为待修项，不留悬空引用。

## 六、双轨差异对照

| 维度 | 本地版（装 ~/.workbuddy/skills/） | 平台版（上传开放平台） |
|---|---|---|
| 目录层级 | 保留原嵌套结构 | 强制两级，无嵌套 |
| 脚本依赖 | 保留原脚本，允许第三方包 | 仅标准库，第三方依赖改为文字规则或删除 |
| 联网 | 允许 | 禁止强依赖，联网降级为可选增强 |
| 工具名 | 保留原工具声明 | 仅保留平台工具集内工具 |
| frontmatter | 补齐七项（本地列表显示需要） | 补齐七项 + 合规加固 |
| 打包 | 目录直接复制 | root 直铺 zip，根目录可见 SKILL.md |

## 七、工具名映射表

| 源工具名 | WorkBuddy 对应 | 处置 |
|---|---|---|
| Read / Write / Edit | 同名 | 保留 |
| Bash / Glob / Grep | 同名 | 保留 |
| WebSearch / WebFetch | 同名 | 平台版保留但正文须声明为可选增强 |
| Task / TodoWrite / NotebookEdit | 无对应 | 删除，改为正文中的步骤与自检清单 |
| 其他 MCP 或 CLI 专属工具 | 无对应 | 删除，能力写入「不适用于」边界 |
