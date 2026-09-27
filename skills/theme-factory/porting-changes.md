# 搬运改动清单

- 源规格：`anthropics/skills@main/skills/theme-factory`
- 来源类型：github（上游仓库源码）
- 平台版：`skills/theme-factory`
- 本地版：`（本地版副本，未随包分发）`

## 一、字段改动

- `version`：源缺失，已按映射表补全
- `display_name`：源缺失，已按映射表补全
- `display_name_en`：源缺失，已按映射表补全
- `description_zh`：源缺失，已按映射表补全
- `description_en`：源缺失，已按映射表补全
- `license`：源缺失或非标准，已根据 LICENSE 文本自动识别为 `Apache-2.0`
- 许可准入等级：`permissive` —— 宽松许可 → 可双轨分发（上架需随附 LICENSE 与归属声明）

## 二、文件搬迁

- `references/LICENSE.txt`（原 `LICENSE.txt`）
- `assets/theme-showcase.pdf`（原 `theme-showcase.pdf`）
- `references/themes__arctic-frost.md`（原 `themes/arctic-frost.md`）
- `references/themes__botanical-garden.md`（原 `themes/botanical-garden.md`）
- `references/themes__desert-rose.md`（原 `themes/desert-rose.md`）
- `references/themes__forest-canopy.md`（原 `themes/forest-canopy.md`）
- `references/themes__golden-hour.md`（原 `themes/golden-hour.md`）
- `references/themes__midnight-galaxy.md`（原 `themes/midnight-galaxy.md`）
- `references/themes__modern-minimalist.md`（原 `themes/modern-minimalist.md`）
- `references/themes__ocean-depths.md`（原 `themes/ocean-depths.md`）
- `references/themes__sunset-boulevard.md`（原 `themes/sunset-boulevard.md`）
- `references/themes__tech-innovation.md`（原 `themes/tech-innovation.md`）

## 三、正文引用重写

- `theme-showcase.pdf` → `assets/theme-showcase.pdf`
- `theme-showcase.pdf` → `assets/theme-showcase.pdf`
- 目录引用 `themes/` → `references/`，目录下文件已重命名为 `themes__<name>`，建议人工核对表述

## 四、待人工确认

- 已补写段落骨架：执行流程、边界与降级、质量自检（含补写标注，须按源技能内容改写为具体步骤与判据）
- `display_name` 为自动推导，建议替换为更贴切的中文名
- 转换后请运行合规校验，确认零 FAIL 后再上传

## 五、交付物

- 平台版目录：`skills/theme-factory`
- 本地版目录：`（本地版副本，未随包分发）`（复制到 `~/.workbuddy/skills/` 即可用）
- 许可随包文件：`LICENSE`、`THIRD-PARTY-NOTICES.md`
- 上传包：`（打包产物，未随包分发）`（root 直铺）

## 六、交付前自检与去毒审计

- 必填字段、目录层级、引用完整性（双向）：**PASS**
- 去毒审计：**CLEAN** —— 未检出风险（硬 0）
- 待人工确认（10 项）：
  - 搬迁文件未被正文引用：references/themes__arctic-frost.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__botanical-garden.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__desert-rose.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__forest-canopy.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__golden-hour.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__midnight-galaxy.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__modern-minimalist.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__ocean-depths.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__sunset-boulevard.md（建议人工确认是否需在正文引用）
  - 搬迁文件未被正文引用：references/themes__tech-innovation.md（建议人工确认是否需在正文引用）
- 平台校验（官方 validate_skill.py）：**通过** —— 通过 12 / 警告 0 / 失败 0
