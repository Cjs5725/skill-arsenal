# 搬运改动清单

- 源规格：`anthropics/commerce-agents@main/shopping-agent/skills/customer-care`
- 来源类型：github（上游仓库源码）
- 平台版：`skills/customer-care`
- 本地版：`（本地版副本，未随包分发）`

## 一、字段改动

- `version`：源缺失，已按映射表补全
- `display_name`：源缺失，已按映射表补全
- `display_name_en`：源缺失，已按映射表补全
- `description_zh`：源缺失，已按映射表补全
- `description_en`：源缺失，已按映射表补全
- `license`：源缺失或非标准，已根据 LICENSE 文本自动识别为 `Apache-2.0`（该 LICENSE 取自仓库根目录——技能子目录内无 LICENSE，子路径搬运场景下的常见情况）
- 许可准入等级：`permissive` —— 宽松许可 → 可双轨分发（上架需随附 LICENSE 与归属声明）

## 二、文件搬迁

- 源技能无附属资源文件，仅转换 SKILL.md

## 三、正文引用重写

- 正文未发现需要改写的资源引用

## 四、待人工确认

- 已补写段落骨架：执行流程、边界与降级、质量自检（含补写标注，须按源技能内容改写为具体步骤与判据）
- `display_name` 为自动推导，建议替换为更贴切的中文名
- 转换后请运行合规校验，确认零 FAIL 后再上传

## 五、交付物

- 平台版目录：`skills/customer-care`
- 本地版目录：`（本地版副本，未随包分发）`（复制到 `~/.workbuddy/skills/` 即可用）
- 许可随包文件：`LICENSE`、`THIRD-PARTY-NOTICES.md`
- 上传包：`（打包产物，未随包分发）`（root 直铺）

## 六、交付前自检与去毒审计

- 必填字段、目录层级、引用完整性（双向）：**PASS**
- 去毒审计：**CLEAN** —— 未检出风险（硬 0）
- 平台校验（官方 validate_skill.py）：**通过** —— 通过 11 / 警告 0 / 失败 0
