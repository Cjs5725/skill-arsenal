# 主流源仓库与典型技能搬运要点

> 用途：第 3 步处置决策的参考。star 数为公开检索所得，随 time 变动，仅用于判断仓库活跃度。

## 一、源仓库对照

| 仓库 | 定位 | star 量级 | 搬运要点 |
|---|---|---|---|
| anthropics/skills | Agent Skills 官方示范库，含 Creative & Design、Development & Technical、Enterprise & Communication、Document Skills 四类 | 30k+ | 结构最规范，多数可直接搬；注意 `skills/docx`、`pdf`、`pptx`、`xlsx` 为 source-available，仅可本地用；仓库级目录 `.claude-plugin`、`spec`、`template` 不搬运 |
| obra/superpowers | 工程工作流合集（TDD、debug、协作模式） | 20k+ | 技能间互相引用，搬运单个技能时需检查是否引用了同仓库其他技能；引用需改为自包含或一并搬运 |
| ComposioHQ/awesome-claude-skills | Awesome 列表聚合，60+ 场景 | 15k+ | 本身多为索引，真正可搬的是其链接到的子仓库技能；搬运前先跳转到具体源 |
| travisvn/awesome-claude-skills | Claude Code 工作流定制 | 5k+ | 同上，偏工作流；大量钩子与命令文件需转为平台可识别的目录结构 |
| huggingface/skills | AI/ML 方向（训练、评估、数据集） | 5k+ | 强依赖 transformers / datasets 等第三方包与 GPU，平台版多判为「不建议搬」，仅产本地版 |
| trailofbits/skills | 安全工程方向 | 4k+ | 多依赖专用 CLI 工具，平台版需删除 CLI 依赖或改为文字规则 |

## 二、典型技能处置方案

**文档处理类（pdf / docx / pptx / xlsx）**
- 风险：source-available 许可；脚本依赖 python-docx、openpyxl、pypdf 等第三方包；资源目录常嵌套。
- 处置：平台版删除第三方依赖脚本，改为「按规范步骤手工执行 + 文字规则」；本地版保留脚本；报告中显式标注不得公开发布。

**前端设计类（frontend-design / web-artifacts）**
- 风险：多为纯指令型技能，无脚本，依赖少。
- 处置：通常可直接搬；只需补七项字段与压缩 description。

**TDD / debug 类（superpowers）**
- 风险：正文强制要求运行测试命令；可能引用同仓库其他技能。
- 处置：保留流程判据（不依赖外部），删除跨技能引用或改为内联要点；测试命令改为「按项目既有测试命令执行」的通用表述。

**浏览器自动化类**
- 风险：依赖 Playwright / Puppeteer 与联网。
- 处置：平台版判为「不建议搬」，转为本地版；或改写为「给出操作步骤 + 选择器规则」的纯指令版。

**数据 / AI 训练类**
- 风险：依赖 GPU 与大型第三方库。
- 处置：仅产本地版，报告中标注运行环境要求。

## 三、已验证的格式事实

1. Agent Skills 标准的 frontmatter 仅要求 `name` 与 `description` 两项，因此 GitHub 技能普遍缺少 WorkBuddy 所需的另外五项字段。
2. Claude 平台对上传技能的 `description` 有 1024 字符校验；Anthropic 曾为通过校验把 `claude-academy-guide` 的描述从 1176 字符压到 992 字符。
3. 技能名不得含 `claude`、`anthropic` 等保留词，Anthropic 为此把技能目录、frontmatter name 与 marketplace 条目名统一改名。
4. WorkBuddy 压缩包唯一可用形态是 root 直铺；`skills/{name}/SKILL.md` 双层包裹会报「压缩包缺少 SKILL.md 文件」。
5. 平台沙箱评测不保证联网与外部依赖，强联网技能会在评测环节判为质量不达标。

## 四、选品建议

- 优先搬：纯指令型技能（设计、写作、流程规范、审查清单）——改造成本低、平台版通过率高。
- 谨慎搬：脚本辅助型技能（文档处理、代码分析）——需把脚本依赖改写成文字规则，工作量中等。
- 建议只做本地版：强环境依赖型技能（AI 训练、浏览器自动化、专用 CLI）——平台版无法保证执行。
