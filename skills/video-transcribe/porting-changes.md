# 搬运改动清单

- 源规格：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-26/demo-video-transcribe/_staged-src`
- 来源类型：local（直接使用本地目录）
- 平台版：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-26/demo-video-transcribe/video-transcribe`
- 本地版：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-26/demo-video-transcribe/video-transcribe-local`

## 一、字段改动

- `version`：源缺失，已按映射表补全
- `display_name`：源缺失，已按映射表补全
- `display_name_en`：源缺失，已按映射表补全
- `description_zh`：源缺失，已按映射表补全
- `description_en`：源缺失，已按映射表补全
- `license`：源缺失或非标准，已根据 LICENSE 文本自动识别为 `Apache-2.0`
- 许可准入等级：`permissive` —— 宽松许可 → 可双轨分发（上架需随附 LICENSE 与归属声明）

## 二、文件搬迁

- `assets/LICENSE`（原 `LICENSE`）

## 三、正文引用重写

- 正文未发现需要改写的资源引用

## 四、待人工确认

- 已补写段落骨架：执行流程、边界与降级、质量自检（含补写标注，须按源技能内容改写为具体步骤与判据）
- 正文仍含联网或安装类语句：brew install、pip install，平台版须改为内置知识优先并保留离线路径
- `display_name` 为自动推导，建议替换为更贴切的中文名
- 转换后请运行合规校验，确认零 FAIL 后再上传

## 五、交付物

- 平台版目录：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-26/demo-video-transcribe/video-transcribe`
- 本地版目录：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-26/demo-video-transcribe/video-transcribe-local`（复制到 `~/.workbuddy/skills/` 即可用）
- 许可随包文件：`LICENSE`、`THIRD-PARTY-NOTICES.md`
- 上传包：`E:/workbuddy/2026-09-13-23-02-38/_release/2026-09-26/demo-video-transcribe/video-transcribe.zip`（root 直铺）

## 六、交付前自检与去毒审计

- 必填字段、目录层级、引用完整性（双向）：**PASS**
- 去毒审计：**REVIEW** —— 需人工确认（硬 0，待确认 1 项）
- 待人工确认（1 项）：
  - 去毒审计·供应链：未锁定版本的依赖安装（`SKILL.md:33`）锁定版本号或提供哈希
- 平台校验（官方 validate_skill.py）：**通过** —— 通过 11 / 警告 0 / 失败 0

## 七、中文化阶段改动（2026-09-26，四道工序）

1. 元数据修复：`author` 与 `搬运来源` 由暂存目录名（_staged-src）改为真实来源 `wendy7756/AI-Video-Transcriber/skills/video-transcribe`；`display_name` 由自动推导「转录」改为「视频转录」；`description_en` 补回被截断的原文（`.txt file. Use when...` 一段）。
2. 许可按路径核：技能子目录无 LICENSE，随源补入仓库根 `LICENSE`（Apache-2.0）原件后再过准入闸。
3. 正文逐段翻译：7 个 EN 标题段全译；术语按 `references/glossary.md` 口径（transcribe=转录、transcript=转录文本、summary=摘要、subtitle=字幕、pipeline=流水线、podcast=播客、fallback=降级；Whisper/ffmpeg/venv/JSON 键原样）。新术语 3 条已回填术语表。
4. 骨架段按源重写：`执行流程`（4 步：环境判据→带 --json 执行→解析 JSON 交付→中间结果可查）、`边界与降级`（无密钥→--no-llm；无字幕→Whisper 慢告知；缺环境→停步不交付）、`质量自检`（4 条源自源技能 no_speech/失败模式语义）、`搬运说明`（残留风险如实列）。
5. 悬空引用修复：`./install.sh` 为源仓库根脚本而非包内文件，措辞改为「AI Video Transcriber 仓库根目录的安装脚本」，本地化检查悬空 1→0。
6. 复跑门禁：官方 validate_skill.py 11/0/0 通过；check_localization.py PASS（覆盖率 100%，悬空 0）；pack_zh 交付包一级条目白名单（LICENSE/SKILL.md/THIRD-PARTY-NOTICES.md/assets）。
7. 残留风险（如实保留）：依赖安装未锁定版本号（上游原文如此，未替上游做决定）；运行依赖外部仓库环境（venv/ffmpeg），属源技能固有前置条件。
