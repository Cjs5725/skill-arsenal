# 搬运改动清单

- 源规格：`anthropics/skills@main/skills/discernment-nudge`
- 来源类型：github（命中用户级共享源码缓存（跨会话复用，零文件下载））
- 平台版：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-25/batch6/discernment-nudge`
- 本地版：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-25/batch6/discernment-nudge-local`

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

## 三、正文引用重写

- 正文未发现需要改写的资源引用

## 四、待人工确认

- 已补写段落骨架：执行流程、边界与降级、质量自检（含补写标注，须按源技能内容改写为具体步骤与判据）
- `display_name` 为自动推导，建议替换为更贴切的中文名
- 转换后请运行合规校验，确认零 FAIL 后再上传

## 五、交付物

- 平台版目录：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-25/batch6/discernment-nudge`
- 本地版目录：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-25/batch6/discernment-nudge-local`（复制到 `~/.workbuddy/skills/` 即可用）
- 许可随包文件：`LICENSE`、`THIRD-PARTY-NOTICES.md`
- 上传包：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-25/batch6/discernment-nudge.zip`（root 直铺）

## 六、交付前自检与去毒审计

- 必填字段、目录层级、引用完整性（双向）：**PASS**
- 去毒审计：**CLEAN** —— 未检出风险（硬 0）
- 平台校验（官方 validate_skill.py）：**通过** —— 通过 11 / 警告 0 / 失败 0
