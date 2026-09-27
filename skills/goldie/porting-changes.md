# 搬运改动清单

- 源规格：`kacperkapusciak/goldie@main/skills/goldie`
- 来源类型：github（上游仓库源码）
- 平台版：`skills/goldie`
- 本地版：`（本地版副本，未随包分发）`

## 一、字段改动

- `version`：源缺失，已按映射表补全
- `display_name`：源缺失，已按映射表补全
- `display_name_en`：源缺失，已按映射表补全
- `description_zh`：源缺失，已按映射表补全
- `description_en`：源缺失，已按映射表补全
- `license`：源缺失或非标准，已根据 LICENSE 文本自动识别为 `MIT`（该 LICENSE 取自仓库根目录——技能子目录内无 LICENSE，子路径搬运场景下的常见情况）
- 许可准入等级：`permissive` —— 宽松许可 → 可双轨分发（上架需随附 LICENSE 与归属声明）

## 二、文件搬迁

- `references/config.md`
- `references/flows.md`

## 三、正文引用重写

- 正文未发现需要改写的资源引用
- 目录引用 `references/` → `references/`，目录下文件已重命名为 `references__<name>`，建议人工核对表述

## 四、待人工确认

- 已补写段落骨架：执行流程、边界与降级、质量自检（含补写标注，须按源技能内容改写为具体步骤与判据）
- 正文仍含联网或安装类语句：brew install、install the，平台版须改为内置知识优先并保留离线路径
- `display_name` 为自动推导，建议替换为更贴切的中文名
- 转换后请运行合规校验，确认零 FAIL 后再上传

## 五、交付物

- 平台版目录：`skills/goldie`
- 本地版目录：`（本地版副本，未随包分发）`（复制到 `~/.workbuddy/skills/` 即可用）
- 许可随包文件：`LICENSE`、`THIRD-PARTY-NOTICES.md`
- 上传包：`（打包产物，未随包分发）`（root 直铺）

## 六、交付前自检与去毒审计

- 必填字段、目录层级、引用完整性（双向）：**PASS**
- 去毒审计：**REVIEW** —— 需人工确认（硬 0，待确认 1 项）
- 待人工确认（1 项）：
  - 去毒审计·供应链：npx 拉取远端包（供应链风险）（`SKILL.md:91`）确认包名与发布者可信
- 平台校验（官方 validate_skill.py）：**通过** —— 通过 12 / 警告 0 / 失败 0
