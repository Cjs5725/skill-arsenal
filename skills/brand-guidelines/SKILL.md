---
name: brand-guidelines
version: 1.0.0
display_name: "Brand Guidelines"
display_name_en: "Brand Guidelines"
description_zh: "将 brand-guidelines 技能迁移至 WorkBuddy，保留其流程与判据。"
description_en: "Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel."
category: productivity
author: "anthropics/skills/skills/brand-guidelines"
allowed-tools: Read,Write,Edit,Bash,Glob,Grep
agent_created: true
license: "Apache-2.0"
description: |
  Applies Anthropic's official brand colors and typography to any sort of artifact that may benefit from having Anthropic's look-and-feel. Use it when brand colors or style guidelines, visual formatting, or company design standards apply.
  不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。
  搬运来源：anthropics/skills/skills/brand-guidelines
---

> **改动声明**：本文档基于上游原作**修改后**分发——已补全 YAML 字段、按平台要求改写正文表述并补写结构段落，与上游原文不完全一致，请以上游仓库版本为权威。来源与许可见同目录 `THIRD-PARTY-NOTICES.md` 与 `LICENSE`；版权归原作者所有，本声明不改变上游许可条款。


# Anthropic Brand Styling

## Overview

To access Anthropic's official brand identity and style resources, use this skill.

**Keywords**: branding, corporate identity, visual identity, post-processing, styling, brand colors, typography, Anthropic brand, visual formatting, visual design

## Brand Guidelines

### Colors

**Main Colors:**

- Dark: `#141413` - Primary text and dark backgrounds
- Light: `#faf9f5` - Light backgrounds and text on dark
- Mid Gray: `#b0aea5` - Secondary elements
- Light Gray: `#e8e6dc` - Subtle backgrounds

**Accent Colors:**

- Orange: `#d97757` - Primary accent
- Blue: `#6a9bcc` - Secondary accent
- Green: `#788c5d` - Tertiary accent

### Typography

- **Headings**: Poppins (with Arial fallback)
- **Body Text**: Lora (with Georgia fallback)
- **Note**: Fonts should be pre-installed in your environment for best results

## Features

### Smart Font Application

- Applies Poppins font to headings (24pt and larger)
- Applies Lora font to body text
- Automatically falls back to Arial/Georgia if custom fonts unavailable
- Preserves readability across all systems

### Text Styling

- Headings (24pt+): Poppins font
- Body text: Lora font
- Smart color selection based on background
- Preserves text hierarchy and formatting

### Shape and Accent Colors

- Non-text shapes use accent colors
- Cycles through orange, blue, and green accents
- Maintains visual interest while staying on-brand

## Technical Details

### Font Management

- Uses system-installed Poppins and Lora fonts when available
- Provides automatic fallback to Arial (headings) and Georgia (body)
- No font installation required - works with existing system fonts
- For best results, pre-install Poppins and Lora fonts in your environment

### Color Application

- Uses RGB color values for precise brand matching
- Applied via python-pptx's RGBColor class
- Maintains color fidelity across different systems

## 执行流程

1. 识别要套用品牌的文档或物料类型，明确将影响的色板与字体范围。
2. 按规范套用色板：深色 #141413（主文字/深底）、浅色 #faf9f5（浅底）、中灰 #b0aea5、浅灰 #e8e6dc、橙 #d97757（主强调）、蓝 #6a9bcc（次强调）、绿 #788c5d（三强调）。
3. 字体：标题（≥24pt）用 Poppins，正文用 Lora；目标环境缺失时按规范回退 Arial / Georgia。
4. 交付前逐项对照色值与字体表核对，不近似取色。


## 边界与降级

- 本技能只覆盖 Anthropic 官方品牌；其它品牌需求可参照其结构自建规范，但不得把 Anthropic 色值冒充为该品牌规范。
- 目标环境无 Poppins/Lora 时：走规范内回退字体（Arial/Georgia），不引入规范外字体。
- 品牌装饰与可读性冲突时：以可读性优先，并在交付说明中注明取舍。


## 质量自检

- [ ] 全部色值与规范十六进制逐一相等，无近似取色
- [ ] 标题 ≥24pt 用 Poppins、正文用 Lora，或已走规范回退并在说明中注明
- [ ] 深浅底色与文字组合满足可读性
- [ ] 未把 Anthropic 色值用于非 Anthropic 品牌宣称

## 搬运说明

本技能由上游源技能（GitHub 开源仓库）转换而来，核心流程与判据保持原样。
许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。
依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。
