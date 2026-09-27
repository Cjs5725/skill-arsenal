---
name: video-transcribe
version: 1.0.0
display_name: "转录"
display_name_en: "Video Transcribe"
description_zh: "将 video-transcribe 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Transcribe and summarize a video or podcast from a URL (YouTube, TikTok, Bilibili, Apple Podcasts, SoundCloud, 30+ platforms) or from a local media/."
category: productivity
author: "_staged-src"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  Transcribe and summarize a video or podcast from a URL (YouTube, TikTok, Bilibili, Apple Podcasts, SoundCloud, 30+ platforms) or from a local media/.txt file. Use when the user shares a video/podcast link or media file and wants a transcript, summary, translation, or the original video downloaded. Triggers on "transcribe", "summarize this video", "what does this video say", "get the transcript", "转录", "视频摘要".
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：_staged-src
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Video Transcribe

Runs this repo's pipeline headlessly: platform subtitles when available (seconds),
local Whisper as fallback, then optimize -> translate -> summarize.

## Before running

The command must be run from the AI Video Transcriber repository root and needs the
project virtualenv plus `ffmpeg`. Verify once per session:

```bash
ls venv/bin/python && command -v ffmpeg
```

- No venv: run `./install.sh`, or `python3 -m venv venv && venv/bin/pip install -r requirements.txt`.
- No ffmpeg: install it first with `brew install ffmpeg` on macOS or `sudo apt install ffmpeg` on Debian/Ubuntu. Do not proceed without it; audio extraction will fail.

## Run it

```bash
venv/bin/python transcribe.py "<URL or file path>" --json
```

Always pass `--json`: it puts machine-readable output on stdout and keeps progress
chatter on stderr. Parse the JSON rather than scraping log lines.

Useful flags:

| Flag | When to use |
|------|-------------|
| `-l, --summary-language <code>` | Summary language: `en`, `zh`, `es`, `fr`, `de`, `it`, `pt`, `ru`, `ja`, `ko`, `ar`. Default `en` |
| `--no-llm` | No API key is available, or the user only wants the raw transcript. Skips optimize/translate/summarize |
| `--no-video` | The user does not want the source video kept |
| `--whisper-model small` | Accuracy matters more than speed. `tiny` to `large`, default `base` |
| `-o <dir>` | Write the Markdown somewhere other than `./temp` |

The LLM steps need an OpenAI-compatible key via `OPENAI_API_KEY` and optionally
`OPENAI_BASE_URL`. Without one the pipeline still transcribes but falls back to
basic formatting; prefer `--no-llm` when the user only needs the transcript.

Provider settings:

```bash
export OPENAI_API_KEY="your_api_key_here"
export OPENAI_BASE_URL="https://openrouter.ai/api/v1"
export OPENAI_TRANSLATION_MODEL="gpt-4o"  # optional
```

For a one-off run, `transcribe.py` also accepts `--api-key`, `--base-url`, and
`--model`. Prefer environment variables when possible so API keys are not written
to shell history.

## Reading the result

```json
{
  "title": "...",
  "no_speech": false,
  "detected_language": "en",
  "files": { "raw": "...", "transcript": "...", "summary": "...", "translation": "..." },
  "media": { "path": "...", "kind": "video", "size_bytes": 2243691 }
}
```

Read the `transcript` and `summary` paths to get the content. `translation` is
present only when the source language differs from the summary language.

## Critical: `no_speech`

When `"no_speech": true` the source contains no speech. There is no transcript,
summary, or translation. The pipeline deliberately skips the LLM so that nothing
gets invented.

If you see this, tell the user the video has no speech. Do not guess at the
content, infer it from the title, or describe what the video probably says.

## Failure modes

- Exit `2`: bad input, such as a missing file, unsupported extension, or empty text file. Report the message and fix the argument.
- Exit `1`: download/transcode failure, usually an unreachable URL, region-blocked/private video, or missing ffmpeg. Report the actual error.
- First run downloads Whisper weights, so it can look stalled for a minute.
- Long videos are slow in Whisper mode. Warn the user before starting if no platform subtitles are available.

## 执行流程

<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写为具体步骤与判据 -->

1. 按源技能定义的核心动作依次执行，每步明确动作与判据。
2. 每步产出可检查的中间结果，未达标则回退重做。


## 边界与降级

<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写 -->

- 信息不足时：用默认值推进并标注假设，不阻塞交付。
- 环境受限（无网络、无脚本执行）时：改为人工按上述规则执行，交付完整性不下降。
- 无法处理的场景写入边界说明，不假装覆盖。


## 质量自检

<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写 -->

- [ ] 输出满足源技能定义的验收标准
- [ ] 引用的资源路径全部存在
- [ ] 无占位符残留

## 搬运说明

本技能由上游源技能（本地素材）转换而来，核心流程与判据保持原样。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
