# 搬运改动清单

- 源规格：`https://github.com/aiwithenoch/Jev-Skill@HEAD`
- 来源类型：local（直接使用本地目录）
- 平台版：`skills/jev-skill（本仓）`
- 本地版：`本地分发件（不入本仓）`

## 一、字段改动

- `version`：源缺失，已按映射表补全
- `display_name`：源缺失，已按映射表补全
- `display_name_en`：源缺失，已按映射表补全
- `description_zh`：源缺失，已按映射表补全
- `description_en`：源缺失，已按映射表补全
- `license`：源缺失或非标准，已根据 LICENSE 文本自动识别为 `MIT`
- 许可准入等级：`permissive` —— 宽松许可 → 可双轨分发（上架需随附 LICENSE 与归属声明）

## 二、文件搬迁

- `references/agents__openai.yaml`（原 `agents/openai.yaml`）
- `assets/LICENSE`（原 `LICENSE`）
- `references/ecosystem.md`
- `references/harness.md`
- `references/langchain.md`
- `references/research-notes.md`
- `scripts/compare_reports.py`
- `scripts/fit_calibration.py`
- `scripts/jev_calibration.py`
- `scripts/jev_control.py`
- `scripts/jev_harness.py`

## 三、正文引用重写

- 正文未发现需要改写的资源引用
- 目录引用 `references/` → `references/`，目录下文件已重命名为 `references__<name>`，建议人工核对表述
- 目录引用 `scripts/` → `scripts/`，目录下文件已重命名为 `scripts__<name>`，建议人工核对表述

## 四、待人工确认

- 已补写段落骨架：执行流程、边界与降级、质量自检（含补写标注，须按源技能内容改写为具体步骤与判据）
- `display_name` 为自动推导，建议替换为更贴切的中文名
- 转换后请运行合规校验，确认零 FAIL 后再上传

## 五、交付物

- 平台版目录：`skills/jev-skill（本仓）`
- 本地版目录：`本地分发件（不入本仓）`（复制到 `~/.workbuddy/skills/` 即可用）
- 许可随包文件：`LICENSE`、`THIRD-PARTY-NOTICES.md`
- 上传包：`平台上传包（root 直铺）`（root 直铺）

## 六、交付前自检与去毒审计

- 必填字段、目录层级、引用完整性（双向）：**PASS**
- 去毒审计：**CLEAN** —— 未检出风险（硬 0）
- 待人工确认（2 项）：
  - 搬迁文件未被正文引用：references/agents__openai.yaml（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：scripts/jev_calibration.py（建议人工确认是否需在正文引用）
- 平台校验（官方 validate_skill.py）：**通过** —— 通过 12 / 警告 0 / 失败 0

## 八、本机痕迹修复（2026-09-27 晚，转公开预检发现）

- **发现**：SKILL.md `author`/`搬运来源` 与 THIRD-PARTY-NOTICES `来源`/`源规格` 共 4 处携带内部暂存目录名 `_staged-jev-skill`；`源规格` 为本机绝对路径。zh 包 NOTICES 同源 2 处。
- **修正**：author/来源/搬运来源 → `aiwithenoch/Jev-Skill`（与 zh 包既有写法对齐）；`源规格` → `https://github.com/aiwithenoch/Jev-Skill@HEAD`；产物位置改仓库语境表述。EN zip、zh zip、平台版、本地版四处同步修复。
- **验证**：包内与源目录扫描 `E:/workbuddy`、`_staged` 均为 0 命中；zip 条目清单不变、testzip 通过。
- **根因**：打包时 author 从暂存目录名推导；NOTICES 的源规格记录了本机落盘路径而非上游地址——属「本机痕迹」门禁盲区（痕迹扫描此前只在仓库重建层做，未进 porter/pack 层）。已提请将痕迹扫描下沉进打包管线（见批次报告）。
