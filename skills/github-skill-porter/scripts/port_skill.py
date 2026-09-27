#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""规格转换：把 Agent Skills 源技能转为 WorkBuddy 双轨产物（支持批量）。

用法：
    # 单源（保持原行为）
    python port_skill.py <源> [--out <输出根>] [--display-name <中文名>]
                         [--no-zip] [--ensure-sections] [--source-type auto|local|github]

    # 批量：清单文件（每行一个源，# 开头为注释）
    python port_skill.py --batch manifest.txt [--out <输出根>] ...

    # 批量：多个 --source 叠加（可混用本地路径与 GitHub 地址）
    python port_skill.py --source <源A> --source <源B> ...

源（<源>）支持两种形态，自动识别：
    - 本地目录：直接传入路径（已下载的技能目录）
    - GitHub 地址：以下写法均支持，无需手动下载
        owner/repo                owner/repo@branch
        owner/repo/sub@branch     owner/repo@branch/sub
        https://github.com/owner/repo/tree/branch/sub
      文件树经 GitHub API 获取；文件内容优先走 codeload 整仓 tarball（1 次请求
      拿全部文件），失败时回退 jsDelivr 逐文件下载。
      可加 --tree-cache <json> 复用桥接器预取的文件树，彻底免掉二次 API 调用
      （GitHub 未认证限流 60 次/小时，批量搬运很容易撞墙）。

接入契约（非 GitHub 源同样适用，这是"多源采集 → 统一制造"的接口）：
    任何采集方（采集端、网页/知乎采集、其他数据平台）把素材交过来时，在素材根放一份
    可选的 SOURCE_INFO.json 声明来源与许可即可，字段（全部可选）：
        platform / source_url / author / license / license_text / collected_at
    新增采集平台无需改本工具代码——采集方只需按此契约投喂素材。

许可准入（两道具门，均固化为代码）：
    - 门一「能否搬运」：许可未识别/缺失 → **默认拒收**（无 LICENSE ≠ 可复制）；
      如已确认有权搬运，加 --allow-restricted 放行。
    - 门二「能否对外分发」：copyleft（GPL/AGPL/LGPL）或受限放行的产出 → 仅本地版，
      不生成上传包；宽松许可 → 双轨，且**强制随附 LICENSE 全文与归属声明**
      （Apache-2.0 第 4(a)/4(c) 条、MIT/BSD 同类义务）。

单源产出（落在 <输出根>/ 下）：
    <slug>/              平台版：两级目录、七项字段齐全、依赖已标注，内含 porting-changes.md、
                         LICENSE（源许可全文）、THIRD-PARTY-NOTICES.md（归属声明）
    <slug>.zip           root 直铺上传包，解压即可上传开放平台
    <slug>-local/        本地版：保留原结构与脚本，可复制到 ~/.workbuddy/skills/
    porting-changes.md   单源模式额外在输出根落一份（兼容旧调用）

批量产出（多个源归一处理）：
    <slug>/、<slug>.zip、<slug>-local/   每个源各自独立产出，互不覆盖
    batch-report.md                      汇总报告：成功/失败/许可等级/自检硬问题一览
    listing/                             上架物料（加 --listing 时生成）：<slug>.md + 上架清单.md

依赖：仅 Python 标准库（3.6+）。
"""
import argparse
import io
import json
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path

# 同目录模块：用户级共享缓存层（跨会话复用下载与文件树，消除重复消耗）
_HERE = Path(__file__).resolve().parent
# 共享层公共权威副本优先，本地随包副本兜底（保证技能包离线独立可用）。
# 这样所有会话用的是同一份逻辑，谁也不能靠改自己目录里的副本获得特权。
_SHARED_TOOLS = Path.home() / ".workbuddy" / "shared" / "tools"
for _p in (str(_HERE), str(_SHARED_TOOLS)):
    if Path(_p).is_dir() and _p not in sys.path:
        sys.path.insert(0, _p)
import shared_cache as shared  # noqa: E402
try:
    import scan_toxicity as tox  # noqa: E402  去毒审计（同目录；缺失时降级为不扫描）
except Exception:              # pragma: no cover
    tox = None

# 全局开关：是否使用用户级共享缓存（由 --no-shared-cache 关闭）
_USE_SHARED = True

STD_DIRS = {"references", "scripts", "assets"}
PLATFORM_TOOLS = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"}
RESERVED = {"claude", "anthropic", "claude-code", "chatgpt", "gpt", "gemini", "copilot", "codex"}
SCRIPT_EXT = {".py", ".sh", ".js", ".ps1", ".ts"}
DOC_EXT = {".md", ".json", ".yaml", ".yml", ".txt", ".csv", ".rst"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PATH_REF_RE = re.compile(r"(?<![\w/])(references|scripts|assets)/([A-Za-z0-9._/-]+\.[A-Za-z0-9]+)")
BODY_DEP_HINTS = ("pip install", "npm install", "yarn add", "apt-get install", "brew install",
                  "必须先联网", "需要联网", "务必联网", "在线获取", "联网查询",
                  "requires an internet", "requires internet", "fetch the latest",
                  "requires the", "install the")
SECTION_HINTS = {
    "执行流程": (r"第\s*\d+\s*步|步骤|流程|工作流",),
    "边界与降级": (r"边界|降级|兜底|异常|不适用|禁止",),
    "质量自检": (r"自检|检查清单|质量|验收",),
}
SECTION_SKELETON = {
    "执行流程": "## 执行流程\n\n<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写为具体步骤与判据 -->\n\n"
                "1. 按源技能定义的核心动作依次执行，每步明确动作与判据。\n"
                "2. 每步产出可检查的中间结果，未达标则回退重做。\n",
    "边界与降级": "## 边界与降级\n\n<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写 -->\n\n"
                  "- 信息不足时：用默认值推进并标注假设，不阻塞交付。\n"
                  "- 环境受限（无网络、无脚本执行）时：改为人工按上述规则执行，交付完整性不下降。\n"
                  "- 无法处理的场景写入边界说明，不假装覆盖。\n",
    "质量自检": "## 质量自检\n\n<!-- 以下段落由搬运工补写以保证平台合规，请按源技能内容改写 -->\n\n"
                "- [ ] 输出满足源技能定义的验收标准\n- [ ] 引用的资源路径全部存在\n- [ ] 无占位符残留\n",
}


def platform_validator():
    """定位平台官方校验器 `validate_skill.py`；找不到返回 None。

    为什么需要它：本工具的自检只能覆盖"我认为平台会查的项"，**不能替代平台的门禁**。
    实测教训——自检显示"PASS"的 21 个产出，被平台校验器全部判 FAIL（缺结构段落），
    因为平台的三条结构正则是纯中文词，英文源技能必然不命中。自检比平台松，就会漏放。
    """
    cands = [Path.home() / ".workbuddy" / "skills" / "workbuddy-skill-generator"
             / "scripts" / "validate_skill.py"]
    root = Path.home() / ".workbuddy" / "skills"
    if root.is_dir():
        cands += sorted(root.glob("*/scripts/validate_skill.py"))
        cands += sorted(root.glob("*/**/validate_skill.py"))
    for c in cands:
        if c.is_file():
            return c
    return None


def run_platform_validation(platform_dir):
    """调用平台校验器。返回 (结论, 明细)；校验器不可用时返回 ("SKIPPED", 说明)。

    结论取值：通过 / 不通过 / SKIPPED。明细为 "通过 N / 警告 N / 失败 N" 之类的摘要行。
    """
    v = platform_validator()
    if v is None:
        return "SKIPPED", "未找到平台校验器 validate_skill.py，本次未做平台侧复核"
    try:
        r = subprocess.run([sys.executable, str(v), str(platform_dir)],
                           capture_output=True, text=True, encoding="utf-8", timeout=120)
    except Exception as e:
        return "SKIPPED", "平台校验器执行异常：%s" % e
    out = (r.stdout or "") + (r.stderr or "")
    summary = ""
    verdict = "不通过"
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("通过 ") and "警告" in s:
            summary = s
        if s.startswith("结论：通过"):
            verdict = "通过"
    if not summary:
        summary = "校验器未给出可解析摘要"
    return verdict, summary


def missing_structural_sections(body):
    """平台结构性要求：三段落必须命中。返回缺失的段落名列表。

    这三个正则与平台校验器 `validate_skill.py` 的 STRUCTURE_HINTS **完全一致**，
    且都是中文词。实测后果：**英文源技能必然全部缺失**——因为英文正文里不会出现
    「边界」「兜底」「自检」等中文词。这就是为什么必须补段，而不是"看起来没事"。
    转换引擎的自检门禁此前不含此项，比平台门禁更松，导致 21 个产出被误列入上架清单。
    """
    return [k for k, pats in SECTION_HINTS.items()
            if not any(re.search(p, body) for p in pats)]


def fill_structural_sections(body):
    """补写缺失段落骨架。返回 (新正文, 已补段落名列表)。

    补的是**骨架 + 明确的待改写标记**，不是凭空编造内容——骨架里带 HTML 注释说明
    须按源技能内容改写。因此补段后的产出属于"结构合规、内容待人工夯实"，
    不能当成已完成品交付。
    """
    missing = missing_structural_sections(body)
    if not missing:
        return body, []
    return body + "\n\n" + "\n\n".join(SECTION_SKELETON[k] for k in missing), missing


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    fm = {}
    i = 1
    while i < end:
        ln = lines[i]
        if not ln.strip() or ln[:1] in (" ", "\t", "#"):
            i += 1
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", ln)
        if not m:
            i += 1
            continue
        key, val = m.group(1), m.group(2).strip()
        if val in ("|", ">", "|-", ">-"):
            block = []
            i += 1
            while i < end and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                block.append(lines[i].strip())
                i += 1
            fm[key] = " ".join(x for x in block if x)
            continue
        fm[key] = val.strip('"').strip("'")
        i += 1
    return fm, "\n".join(lines[end + 1:])


def slugify(raw):
    s = re.sub(r"[^a-z0-9]+", "-", (raw or "").lower()).strip("-")
    s = re.sub(r"-{2,}", "-", s)
    tokens = [t for t in s.split("-") if t and t not in RESERVED]
    s = "-".join(tokens) or "ported-skill"
    if len(s) > 64:
        s = s[:64].rstrip("-")
    return s


def sanitize_value(v):
    """YAML 双引号标量安全化。

    必须处理直引号：`description_en: "%s"` 这类写法下，值里若含 `"` 会直接截断标量，
    产出 YAML 解析失败（本函数此前只清理尖括号与弯引号，漏了直引号——实测可达：
    源技能英文描述里出现 `"..."` 即可触发）。统一替换为单引号，语义无损且安全。
    """
    v = (v or "").replace("\n", " ").replace('"', "'")
    return re.sub(r"<|>|\u201c|\u201d", "", v).strip()


def first_sentence(text, limit):
    t = sanitize_value(text)
    m = re.split(r"(?<=[。.!?！？])\s*", t)
    head = (m[0] or t).strip()
    if len(head) > limit:
        # 按**词边界**切，不要断在词中：源描述常写成单条长句（逗号分隔的并列），
        # 直接 [:limit] 会得到 `incomp…` 这种残词（21 项中 10 项中招）。优先退到
        # 最近的空格；若退得太远（不足 60% 限长），说明该段无可切处，才硬切。
        cut = head.rfind(" ", 0, limit)
        if cut < int(limit * 0.6):
            cut = limit
        head = head[:cut].rstrip(" ,，;；、") + "…"
    return head or "Ported skill"


def title_case(slug):
    return " ".join(w.capitalize() for w in slug.split("-") if w)


THIRD_PARTY_MARKERS = ("PIL", "numpy", "imageio", "pandas", "torch", "tensorflow",
                       "cv2", "requests", "scipy", "matplotlib", "sklearn", "openpyxl",
                       "docx", "pptx", "PyPDF2", "fitz", "anthropic", "openai",
                       "selenium", "playwright", "gradio", "streamlit")


CODE_EXT = {".py", ".js", ".ts", ".sh", ".ps1"}
DEP_MANIFEST_NAMES = {"requirements.txt", "requirements-dev.txt", "pyproject.toml",
                      "pipfile", "setup.py", "setup.cfg", "environment.yml",
                      "package.json", "gemfile", "cargo.toml"}
INSTALL_LINE_RE = re.compile(
    r"(?:pip3?\s+install|python\s+-m\s+pip\s+install|npm\s+i(?:nstall)?|"
    r"yarn\s+add|pnpm\s+add|poetry\s+add|conda\s+install|uv\s+(?:pip\s+)?add)\s+[^\n]*",
    re.I)


def detect_hard_dep(src):
    """扫描源技能的**代码与依赖声明**，识别无法在平台沙箱解析的强第三方依赖。

    判定只在三种语境下成立：
      ① 代码文件里的 import / require 语句；
      ② 依赖清单文件（requirements.txt / pyproject.toml / package.json …）；
      ③ 任意文件里 pip / npm / yarn 等安装命令所在行。

    早期版本对全部文本做裸词匹配，把正文里出现的普通词（如「requests」）也判成
    强依赖，导致正常技能被整体阻断、平台版 zip 不生成——这是真实的误报源。
    """
    found = set()

    def hit(text):
        for m in THIRD_PARTY_MARKERS:
            if re.search(r"(?<![\w.-])" + re.escape(m) + r"(?![\w.-])", text):
                found.add(m)

    for p in sorted(src.rglob("*")):
        if not p.is_file():
            continue
        ext, low = p.suffix.lower(), p.name.lower()
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if ext in CODE_EXT:
            for m in THIRD_PARTY_MARKERS:
                esc = re.escape(m)
                if re.search(r"(?m)^\s*(?:import|from)\s+%s(?:\s|\.|,|$)" % esc, text) \
                        or re.search(r"require\(\s*['\"]%s(?:/|['\"])" % esc, text):
                    found.add(m)
        if low in DEP_MANIFEST_NAMES:
            hit(text)
        else:
            for line in INSTALL_LINE_RE.findall(text):
                hit(line)
    return sorted(found)


KNOWN_SPDX = {
    "Apache-2.0", "MIT", "BSD-2-Clause", "BSD-3-Clause", "GPL-2.0", "GPL-3.0",
    "LGPL-2.1", "LGPL-3.0", "MPL-2.0", "ISC", "Unlicense", "CC0-1.0",
    "CC-BY-4.0", "AGPL-3.0", "MulanPSL-2.0", "0BSD", "Python-2.0",
}
_LICENSE_PATTERNS = [
    # AGPL 必须排在 GPL 之前：AGPL 全文是 "GNU AFFERO General Public License"，
    # 若先匹配 GPL 的 "GNU General Public License.*Version 3" 存在误判风险，
    # 而 AGPL 第 13 条（网络服务须开源）比 GPL 重得多，误判会直接踩线。
    ("AGPL-3.0", re.compile(r"GNU Affero General Public License", re.I)),
    ("Apache-2.0", re.compile(r"Apache License", re.I)),
    ("MIT", re.compile(r"MIT License|Permission is hereby granted, free of charge", re.I)),
    ("BSD-3-Clause", re.compile(r"Redistribution and use in source and binary forms.*?3\. Neither", re.S | re.I)),
    ("BSD-2-Clause", re.compile(r"Redistribution and use in source and binary forms", re.S | re.I)),
    ("GPL-3.0", re.compile(r"GNU General Public License.*?Version 3", re.S | re.I)),
    ("GPL-2.0", re.compile(r"GNU General Public License.*?Version 2", re.S | re.I)),
    ("MPL-2.0", re.compile(r"Mozilla Public License", re.I)),
    ("ISC", re.compile(r"ISC License", re.I)),
    ("Unlicense", re.compile(r"This is free and unencumbered software", re.I)),
    ("CC0-1.0", re.compile(r"Creative Commons CC0|CC0 1\.0", re.I)),
    ("CC-BY-4.0", re.compile(r"Creative Commons Attribution 4\.0", re.I)),
]

# ------------------------------------------------- 许可准入策略（两道具门）
# 依据：作品自创作完成即受《伯尔尼公约》与中国《著作权法》保护，无 LICENSE ≠ 可自由复制。
# 「能否搬运」与「能否对外分发（上架）」是两道具门，此处把二者固化为代码，
# 避免"筛选评分宽容"被误用到"准入硬红线"。
PERMISSIVE_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD",
    "Unlicense", "CC0-1.0", "Python-2.0", "MulanPSL-2.0", "MPL-2.0", "CC-BY-4.0",
}
COPYLEFT_LICENSES = {"GPL-2.0", "GPL-3.0", "AGPL-3.0", "LGPL-2.1", "LGPL-3.0"}
MATERIAL_INFO_NAME = "SOURCE_INFO.json"


def classify_license(spdx):
    """把 SPDX 标识归入准入等级：permissive / copyleft / unknown。"""
    if not spdx:
        return "unknown"
    if spdx in PERMISSIVE_LICENSES:
        return "permissive"
    if spdx in COPYLEFT_LICENSES:
        return "copyleft"
    return "unknown"


def load_source_info(src):
    """读取（可选）素材元信息 SOURCE_INFO.json —— 供 GitHub 之外的采集源接入。

    任何采集方（采集端、网页/知乎采集、其他数据平台）把素材交过来时，在素材根放一份
    SOURCE_INFO.json 即可声明来源与许可，转换引擎据此完成归属与合规判定——
    新增平台接入不需要改代码，只需按此契约投喂素材。
    字段（全部可选）：platform / source_url / author / license / license_text / collected_at
    """
    p = src / MATERIAL_INFO_NAME
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def collect_license_text(src, repo_root_lic="", src_info=None):
    """收集源许可全文，返回 (spdx, text, origin)。

    优先级：源目录内 LICENSE 文件 > 仓库根 LICENSE 文本 > SOURCE_INFO.json 声明。
    绝不编造许可文本——拿不到就返回空串，交由准入策略决定是否放行。
    """
    for cand in LICENSE_CANDS:
        p = src / cand
        if p.is_file():
            try:
                return (detect_license(src), p.read_text(encoding="utf-8", errors="ignore"),
                        "源目录 LICENSE 文件")
            except Exception:
                pass
    if repo_root_lic:
        return detect_license(src, repo_root_lic), repo_root_lic, "仓库根 LICENSE"
    src_info = src_info or {}
    if src_info.get("license_text"):
        return (src_info.get("license") or detect_license(src, src_info["license_text"]),
                src_info["license_text"], "SOURCE_INFO.json 声明")
    return detect_license(src), "", "none"


def write_license_bundle(platform_dir, spdx, lic_text, source_label, src_type, spec, origin):
    """把源许可全文与归属声明随产出分发。

    这是 Apache-2.0 第 4(a)/4(c) 条、MIT/BSD 同类条款的硬要求：向接收副本者提供
    许可副本并保留归属声明。缺这一步，即使 SPDX 识别正确，分发形式上也不合规。
    返回 (已写文件名列表, 说明行列表)。
    """
    written, notes = [], []
    if (lic_text or "").strip():
        (platform_dir / "LICENSE").write_text(lic_text.rstrip() + "\n", encoding="utf-8")
        written.append("LICENSE")
        notes.append("LICENSE：源许可全文（取自 %s）" % origin)
    else:
        notes.append("LICENSE：**未附带**（源未提供许可文本，已按准入策略处理）")
    lines = [
        "# 第三方许可与归属声明",
        "",
        "本技能由上游来源转换而来，按上游许可条款分发。使用、修改、再分发前请阅读 `LICENSE` 全文。",
        "",
        "| 项 | 内容 |",
        "| --- | --- |",
        "| 来源 | %s |" % source_label,
        "| 来源类型 | %s |" % src_type,
        "| 源规格 | `%s` |" % spec,
        "| 许可（SPDX） | %s |" % (spdx or "未识别"),
        "| 许可文本 | %s |" % ("随包分发，见 `LICENSE`" if (lic_text or "").strip() else "源未提供"),
        "| 生成时间 | %s |" % time.strftime("%Y-%m-%d"),
        "",
        "> 由 `port_skill.py`（github-skill-porter）自动转换生成；版权归原作者所有，",
        "> 本声明不改变上游许可条款。",
    ]
    (platform_dir / "THIRD-PARTY-NOTICES.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    written.append("THIRD-PARTY-NOTICES.md")
    notes.append("THIRD-PARTY-NOTICES.md：归属与许可声明")
    return written, notes


LICENSE_CANDS = ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE.rst",
                 "COPYING", "COPYING.txt", "LICENSE-APACHE", "LICENSE-MIT")
_LICENSE_FALLBACK = {}


def detect_license(src, extra_text=""):
    """读取源技能根目录的 LICENSE / COPYING 文件，正则识别 SPDX 标识。

    返回标准 SPDX 字符串；无法识别返回 None。脚本不在 LICENSE 上凭空编造标识。

    extra_text：源为仓库子路径时的兜底文本。从大仓库里搬子技能时，技能目录内
    并不含 LICENSE（它在仓库根目录），只扫技能目录会导致许可证识别整体失效——
    而许可证恰恰是「能否商用」的判断依据。调用方可从仓库根 LICENSE 注入此文本。
    """
    for cand in LICENSE_CANDS:
        p = src / cand
        if not p.is_file():
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for spdx, pat in _LICENSE_PATTERNS:
            if pat.search(txt):
                return spdx
    if extra_text:
        for spdx, pat in _LICENSE_PATTERNS:
            if pat.search(extra_text):
                return spdx
    return None


def has_local_license(src):
    return any((src / c).is_file() for c in LICENSE_CANDS)


def _gh_owner_repo(spec):
    """解析源规格为 (owner, repo, branch, sub)。

    支持四种写法（分支位置不再挑剔）：
        1. owner/repo
        2. owner/repo@branch
        3. owner/repo@branch/sub/dir
        4. owner/repo/sub/dir@branch
        5. https://github.com/owner/repo/tree/branch/sub/dir
    早期版本只支持第 3 种，却把第 4 种写进了文档，导致
    `owner/repo/sub@branch` 被误解析成 sub="sub@branch"、branch 静默回退 main，
    最终以「GitHub 源无文件」报错（误导性错误信息）。此处在解析层兼容两种写法。
    """
    s = spec.strip()
    m = re.match(r"^https?://github\.com/([^/\s]+)/([^/\s]+?)(?:\.git)?"
                 r"(?:/(?:tree|blob)/([^/\s]+)(?:/(.*))?)?/?$", s)
    if m:
        owner, repo, branch, sub = m.group(1), m.group(2), m.group(3), m.group(4)
    else:
        branch = None
        body = s
        if "@" in body:
            head, tail = body.split("@", 1)
            if "/" in tail:                    # owner/repo@branch/sub/dir
                branch, _, rest = tail.partition("/")
                body = head + "/" + rest
            else:                              # owner/repo[/sub/dir]@branch
                branch, body = tail, head
        parts = [p for p in body.strip("/").split("/") if p]
        if len(parts) < 2:
            return None
        owner, repo = parts[0], parts[1]
        sub = "/".join(parts[2:]) or None
        if repo.endswith(".git"):
            repo = repo[:-4]
    if not re.match(r"^[\w.-]+$", owner or "") or not re.match(r"^[\w.-]+$", repo or ""):
        return None
    sub = (sub or "").strip("/")
    if sub.endswith("SKILL.md"):
        sub = sub.rsplit("/", 1)[0]
    return owner, repo, (branch or "main"), (sub or None)


def _http_get(url, timeout=40, retries=3):
    """带重试的 GET，兜住代理/网关临时 502（jsDelivr 树 API 偶发）。"""
    last = None
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return r.read()
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise last


_TREE_CACHE = {}


def load_tree_cache(path):
    """载入由 bridge_trending.py 预取的 git trees 缓存：{"owner/repo@branch": [路径...]}。

    动机：桥接器探测阶段已经拉过一次文件树，搬运阶段若再拉一次，
    在 GitHub 未认证限流（60 次/小时）下会直接撞墙。
    命中缓存的源**完全不发起 API 调用**，只走 jsDelivr 下载文件内容。
    """
    global _TREE_CACHE
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        print("[warn] 文件树缓存载入失败（忽略，回退在线拉取）：%s" % e)
        return 0
    n = 0
    for k, v in obj.items():
        if isinstance(v, list) and v:
            _TREE_CACHE[k] = v
            n += 1
    return n


def _http_get_capped(url, timeout=180, retries=2, max_bytes=300 * 1024 * 1024):
    """流式 GET，带大小上限——避免误拉模型权重类超大仓库把内存/磁盘打满。"""
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "workbuddy-skill-porter"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                buf = bytearray()
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    buf += chunk
                    if len(buf) > max_bytes:
                        raise ValueError("下载超过 %d MB 上限" % (max_bytes >> 20))
                return bytes(buf)
        except Exception as e:
            last = e
            if i < retries - 1:
                time.sleep(1.5 * (i + 1))
    raise last


_TARBALL_CACHE = {}
TARBALL_CACHE_MAX = 8 * 1024 * 1024


def _repo_blobs(owner, repo, branch):
    """取整仓 {相对路径: bytes}，进程内缓存——同一仓库的多个子技能只下载一次。"""
    key = "%s/%s@%s" % (owner, repo, branch)
    if key in _TARBALL_CACHE:
        return _TARBALL_CACHE[key]
    url = "https://codeload.github.com/%s/%s/tar.gz/refs/heads/%s" % (owner, repo, branch)
    shared.bump("tarball")          # 统计真实网络拉取次数（进程内每仓库至多 1 次）
    raw = _http_get_capped(url)
    blobs = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        for m in tf.getmembers():
            if not m.isfile():
                continue
            rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
            f = tf.extractfile(m)
            if f is None:
                continue
            blobs[rel] = f.read()
    if len(raw) <= TARBALL_CACHE_MAX:
        _TARBALL_CACHE[key] = blobs
    return blobs


def _fetch_via_tarball(owner, repo, branch, want, cache):
    """经 codeload 一次拉整仓 tar.gz，按需落盘指定路径。返回落盘文件数。

    为什么不用 jsDelivr 逐文件：实测本机出口经代理访问 raw.githubusercontent 与
    cdn.jsdelivr.net 单次请求需 10~13 秒且频繁 502，而 codeload.github.com 的整仓
    tarball 仅 1 秒左右且稳定。1 次请求替代 N 次请求，是批量搬运耗时的决定性差异。
    """
    blobs = _repo_blobs(owner, repo, branch)
    n = 0
    for rel in want:
        if rel not in blobs:
            continue
        tgt = cache / rel
        tgt.parent.mkdir(parents=True, exist_ok=True)
        tgt.write_bytes(blobs[rel])
        n += 1
    return n


def _gh_tree(owner, repo, branch):
    """取 git trees（recursive），返回 blob 路径列表。

    三级命中，逐级回退：
      1. 进程内 `_TREE_CACHE`（同一次运行内多次复用）；
      2. **用户级共享缓存**（跨会话复用，命中即零 API 调用）；
      3. GitHub API（拿到后回写共享层，供后续所有会话复用）。
    """
    key = "%s/%s@%s" % (owner, repo, branch)
    if key in _TREE_CACHE:
        return list(_TREE_CACHE[key])
    if _USE_SHARED:
        paths = shared.load_trees(owner, repo, branch)
        if paths:
            _TREE_CACHE[key] = paths
            return list(paths)
        shared.bump("trees_miss")
    url = "https://api.github.com/repos/%s/%s/git/trees/%s?recursive=1" % (owner, repo, branch)
    shared.bump("api")
    obj = json.loads(_http_get(url, timeout=60).decode("utf-8"))
    if obj.get("truncated"):
        raise ValueError("仓库过大，git trees 被截断：请改用本地目录或指定子路径 sub")
    paths = [t["path"] for t in obj.get("tree", []) if t.get("type") == "blob"]
    _TREE_CACHE[key] = paths
    if _USE_SHARED:
        shared.save_trees(owner, repo, branch, paths)
    return paths


def expand_material_root(root, per_repo_limit=0):
    """把「仓库级素材根」展开为「技能级源规格」。

    契约粒度（P-0005 契约里被漏掉的一层，这里是补齐）：
      采集端产出的是**仓库级**素材根 —— 每个候选仓一个目录，内含 SOURCE_INFO.json，
      但**不含 SKILL.md、也不含许可全文**（采集端只写契约文件、不下载素材）。
      生产端负责「仓库级 → 技能级」的展开、文件树探测与下载，这正是分工表里
      「下载与转换属生产端工序」的落点。

    这样采集端**一行都不用改**即可被消费；两侧都不越界。

    返回 (specs, info_map, notes)：
      specs    —— 技能级规格列表（`owner/repo@branch/<skill_dir>`）
      info_map —— spec -> 仓库级契约内容，供 process_one 继承
      notes    —— 每仓一行说明（含被跳过的原因）
    """
    root = Path(root)
    specs, info_map, notes = [], {}, []
    if not root.is_dir():
        return specs, info_map, ["素材根不存在：%s" % root]
    for d in sorted(root.iterdir()):
        info_p = d / "SOURCE_INFO.json"
        if not d.is_dir() or not info_p.is_file():
            continue
        try:
            info = json.loads(info_p.read_text(encoding="utf-8"))
        except Exception as e:
            notes.append("- `%s`：**跳过** —— SOURCE_INFO.json 解析失败（%s）" % (d.name, e))
            continue
        owner = repo = None
        if "__" in d.name:
            owner, _, repo = d.name.partition("__")
        if not owner:
            m = re.search(r"github\.com/([^/\s]+)/([^/\s#?]+)", info.get("source_url") or "")
            if m:
                owner, repo = m.group(1), m.group(2)
        if repo and repo.endswith(".git"):
            repo = repo[:-4]
        if not owner or not repo:
            notes.append("- `%s`：**跳过** —— 无法从目录名或 source_url 确定 owner/repo" % d.name)
            continue
        try:
            _, _, branch, _ = _gh_owner_repo("%s/%s" % (owner, repo))
            paths = _gh_tree(owner, repo, branch)
        except Exception as e:
            notes.append("- `%s/%s`：**跳过** —— 文件树探测失败（%s）" % (owner, repo, e))
            continue
        dirs = sorted({p.rsplit("/", 1)[0] for p in paths if p.endswith("SKILL.md")})
        total_dirs = len(dirs)
        if per_repo_limit > 0:
            dirs = dirs[:per_repo_limit]
        if not dirs:
            notes.append("- `%s/%s`：无 SKILL.md —— 属「需创作技能」，不归转换引擎（按 "
                         "`references/bridge-radar.md` 交给技能生成器）" % (owner, repo))
            continue
        for sub in dirs:
            spec = "%s/%s@%s/%s" % (owner, repo, branch, sub)
            specs.append(spec)
            info_map[spec] = info
        lic = info.get("license") or "未声明"
        cap = ("（每仓上限 %d，实际展开 %d/%d）" % (per_repo_limit, len(dirs), total_dirs)
               if per_repo_limit and total_dirs > per_repo_limit else "")
        notes.append("- `%s/%s`（%s，许可 `%s`）：展开出 **%d** 个技能源%s"
                     % (owner, repo, info.get("platform") or "未知平台", lic,
                        len(dirs), cap))
    return specs, info_map, notes


def resolve_github(spec, cache_root):
    """把 GitHub 地址拉取到本地，返回 (local_dir, label, fetch_note)。

    命中顺序（越靠前越省）：
      0. **用户级共享源码缓存**（跨会话复用）—— 零下载、零 API 调用；
      1. codeload 整仓 tarball —— 1 次请求拿到全部文件（实测约 1 秒）；
      2. jsDelivr 逐文件下载（tarball 失败或超限时的回退，实测单次 10~13 秒）。

    未命中的下载结果会写入共享层，供此后所有会话直接复用。
    """
    parsed = _gh_owner_repo(spec)
    if not parsed:
        raise ValueError("无法解析 GitHub 源：%s" % spec)
    owner, repo, branch, sub = parsed
    label = "%s/%s%s" % (owner, repo, ("/" + sub) if sub else "")

    # ① 共享源码缓存命中：复用已下载文件，不重复下载
    if _USE_SHARED and shared.src_available(owner, repo, sub, branch):
        cache = shared.src_dir(owner, repo, sub, branch)
        shared.bump("src_hit")
        note = "命中用户级共享源码缓存（跨会话复用，零文件下载）"
        if sub and not has_local_license(cache):
            lic = shared.load_license_text(owner, repo)
            if not lic:
                # 共享层尚无该仓库许可证文本：一次性补齐并缓存，此后同仓库所有技能零成本
                try:
                    blobs = _repo_blobs(owner, repo, branch)
                    for rn in LICENSE_CANDS:
                        if rn in blobs:
                            lic = blobs[rn].decode("utf-8", "ignore")
                            shared.save_license_text(owner, repo, lic)
                            note += "；许可证已就地补齐并缓存"
                            break
                except Exception:
                    pass
            if lic:
                _LICENSE_FALLBACK[cache.name] = lic
        return cache, label, note

    paths = _gh_tree(owner, repo, branch)
    if sub:
        paths = [p for p in paths if p == sub or p.startswith(sub + "/")]
    if not paths:
        raise ValueError("GitHub 源无文件：%s" % spec)
    tag = sub.replace("/", "_") if sub else "root"
    cache = Path(cache_root) / ("_src_cache/%s__%s" % (repo, tag))
    if cache.exists():
        shutil.rmtree(cache)
    cache.mkdir(parents=True, exist_ok=True)

    note = ""
    try:
        n = _fetch_via_tarball(owner, repo, branch, set(paths), cache)
        if n < len(paths):
            raise ValueError("tarball 仅覆盖 %d/%d 个文件" % (n, len(paths)))
        note = "codeload 整仓 tarball 一次拉取（%d 个文件）" % n
        shared.bump("download", n)
    except Exception as e:
        if cache.exists():
            shutil.rmtree(cache)
        cache.mkdir(parents=True, exist_ok=True)
        base = "https://cdn.jsdelivr.net/gh/%s/%s@%s/" % (owner, repo, branch)
        for p in paths:
            tgt = cache / p
            tgt.parent.mkdir(parents=True, exist_ok=True)
            tgt.write_bytes(_http_get(base + p, timeout=60))
        shared.bump("download", len(paths))
        note = "jsDelivr 逐文件下载（tarball 回退，原因：%s）" % str(e)[:90]

    # 仓库子路径源：技能目录内通常不含 LICENSE，从仓库根取一份文本作为许可证兜底
    lic_text = ""
    if sub:
        try:
            blobs = _repo_blobs(owner, repo, branch)
            for rn in LICENSE_CANDS:
                if rn in blobs:
                    lic_text = blobs[rn].decode("utf-8", "ignore")
                    _LICENSE_FALLBACK[cache.name] = lic_text
                    break
        except Exception:
            pass

    # 回写共享层：此后任何会话遇到同一源都零下载
    if _USE_SHARED:
        try:
            dst = shared.src_dir(owner, repo, sub, branch)
            if dst.exists():
                shutil.rmtree(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(cache, dst)
            if lic_text:
                shared.save_license_text(owner, repo, lic_text)
            note += "；已写入用户级共享缓存"
        except Exception as e:
            note += "（共享缓存写入失败，不影响本次产出：%s）" % str(e)[:60]
    return cache, label, note


def resolve_source(spec, source_type, cache_root):
    """返回 (local_dir, source_label, source_type, fetch_note)。"""
    p = Path(spec)
    if source_type in ("auto", "local") and p.is_dir():
        return p.resolve(), p.name, "local", "直接使用本地目录"
    if source_type == "local":
        raise ValueError("本地源目录不存在：%s" % spec)
    if source_type in ("auto", "github"):
        try:
            d, label, note = resolve_github(spec, cache_root)
            return d, label, "github", note
        except Exception as e:
            if source_type == "github":
                raise
    raise ValueError("无法识别源：%s（请传入本地目录，或 owner/repo 形式的 GitHub 地址）" % spec)


def plan_files(root):
    """返回 [(源文件, 目标一级目录, 目标文件名)]。

    规则：
    - 标准目录（references/scripts/assets）内部的子目录名嵌入文件名（helpers__extract.py）。
    - 非标准一级代码目录（含 .py 等脚本）映射至 scripts/ 时**保留模块原名**
      （core/gif_builder.py -> scripts/gif_builder.py），不嵌入父目录名，避免破坏 import。
    - 非标准一级文档/资源目录正常嵌入父目录名（themes__arctic-frost.md）。
    """
    plan, used = [], set()
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts[0].startswith("."):
            continue
        if len(rel.parts) == 1 and rel.name == "SKILL.md":
            continue
        if len(rel.parts) == 1 and rel.name == MATERIAL_INFO_NAME:
            # 采集契约文件（SOURCE_INFO.json）是投喂元信息，不是技能内容——
            # 其信息已进 THIRD-PARTY-NOTICES.md，不应作为资源搬进产出。
            continue
        suffix = p.suffix.lower()
        top = rel.parts[0] if len(rel.parts) > 1 else ""
        is_std = top in STD_DIRS
        if is_std:
            tdir = top
            stem_parts = rel.parts[1:-1]
            base = p.stem
            if stem_parts:
                base = "__".join(list(stem_parts) + [base])
        elif suffix in SCRIPT_EXT:
            tdir = "scripts"
            base = p.stem                      # 代码：保留模块原名
        elif suffix in DOC_EXT:
            tdir = "references"
            stem_parts = rel.parts[:-1]
            base = p.stem
            if stem_parts:
                base = "__".join(list(stem_parts) + [base])
        else:
            tdir = "assets"
            stem_parts = rel.parts[:-1]
            base = p.stem
            if stem_parts:
                base = "__".join(list(stem_parts) + [base])
        name = base + p.suffix
        cand, n = name, 2
        while (tdir, cand) in used:
            cand = "%s-%d%s" % (base, n, p.suffix)
            n += 1
        used.add((tdir, cand))
        plan.append((p, tdir, cand))
    return plan


def build_frontmatter(fm, name, args, source_label, detected_license=None):
    src_desc = (fm.get("description") or "").strip()
    body_desc = src_desc if src_desc else "迁移自 %s 的技能。" % source_label
    # 描述保真：平台规格对 `description` **无长度上限**（只对 `name` 限 64 字符），
    # 而描述里「触发时机」那半段恰是技能被发现的关键。此前按 700 字符硬切会**断在词中**
    # （实测 `...sending Slack messages` → `sen …`，21 项中 11 项中招），既丢信息又违反
    # 本项目「零丢失」原则。故不再截断；仅保留一个病态输入的安全阀，且**切在句界**。
    if len(body_desc) > 4000:
        cut = max(body_desc.rfind(m, 0, 4000) for m in "。！？.!?")
        body_desc = (body_desc[:cut + 1] if cut > 0 else body_desc[:4000]).rstrip() + " …"
    # 描述可能本身是多行（源技能用 `description: |` 块标量写成多段）。必须**逐行**
    # 拆成独立元素再加缩进——否则内嵌换行会落在缩进之外，YAML 块标量在此提前结束，
    # 产出解析失败。实测可达：上游描述含「不适用于：…／搬运来源：…」多段即触发。
    desc_lines = [seg.strip() for seg in body_desc.splitlines() if seg.strip()]
    if not desc_lines:
        desc_lines = ["迁移自 %s 的技能。" % source_label]
    if "不适用于" not in body_desc and "不适用" not in body_desc:
        desc_lines.append("不适用于：从零创作新技能，以及需强环境依赖方可执行的场景。")
    desc_lines.append("搬运来源：%s" % source_label)
    desc_block = "\n".join("  " + l for l in desc_lines)

    zh = fm.get("description_zh") or ""
    if not zh:
        cjk = re.findall(r"[\u4e00-\u9fff，。、；：！？]{6,}", src_desc)
        zh = first_sentence(cjk[0], 60) if cjk else "将 %s 技能迁移至 WorkBuddy，保留其流程与判据。" % name
    en = fm.get("description_en") or first_sentence(src_desc, 200)
    disp = args.display_name or fm.get("display_name") or ""
    if not disp:
        cjk_name = re.findall(r"[\u4e00-\u9fff]{2,12}", src_desc)
        disp = cjk_name[0] if cjk_name else title_case(name)

    tools = [t.strip() for t in (fm.get("allowed-tools") or "").split(",") if t.strip()]
    kept = [t for t in tools if t in PLATFORM_TOOLS] or ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
    dropped = [t for t in tools if t not in PLATFORM_TOOLS]

    lines = [
        "---",
        "name: %s" % name,
        "version: %s" % sanitize_value(fm.get("version") or "1.0.0"),
        'display_name: "%s"' % sanitize_value(disp),
        'display_name_en: "%s"' % sanitize_value(fm.get("display_name_en") or title_case(name)),
        'description_zh: "%s"' % sanitize_value(first_sentence(zh, 60)),
        'description_en: "%s"' % sanitize_value(en),
        "category: %s" % sanitize_value(fm.get("category") or "productivity"),
        'author: "%s"' % sanitize_value(fm.get("author") or source_label),
        "allowed-tools: %s" % ",".join(kept),
        "agent_created: true",
    ]
    # license 决策：源已是标准 SPDX → 沿用；否则用 LICENSE 文本自动识别；
    # 源为非标准表述（如 "Complete terms in LICENSE.txt"）→ 有识别结果则用，无则保留并标注待核
    raw_lic = (fm.get("license") or "").strip()
    lic_auto = False
    if raw_lic in KNOWN_SPDX:
        lic = raw_lic
    elif detected_license:
        lic = detected_license
        lic_auto = True
    elif raw_lic:
        lic = raw_lic
    else:
        lic = None
    if lic:
        lines.append('license: "%s"' % sanitize_value(lic))
    lines += ["description: |", desc_block, "---", ""]
    return "\n".join(lines), dropped, lic, lic_auto


def self_check(platform_dir, name, rename_map, allow_missing_sections=False):
    """交付前自检门禁：必填字段、目录层级、悬空引用、引用覆盖（双向）、平台结构段落。

    返回 (issues, warnings)：
    - issues 为硬问题（缺字段 / 层级超限 / 悬空引用 / 缺平台结构段落），应阻断上传；
    - warnings 为待人工确认的软问题（搬迁文件未被正文引用等）。
    本检查直接回应「合规校验通过 ≠ 引用完整」的盲区：既查引用指向的文件是否存在，
    也查被搬迁的文件是否都被正文引用到。

    `allow_missing_sections`：仅本地自用的产出可放宽结构段落要求；**面向平台上传的
    产出必须保留该检查**——平台校验器会独立跑同一套正则，这里放过等于把 FAIL 推迟到上传时。
    """
    issues, warnings = [], []
    skill = platform_dir / "SKILL.md"
    text = skill.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    required = ["name", "version", "display_name", "display_name_en",
                "description_zh", "description_en", "description"]
    for f in required:
        if f not in fm:
            issues.append("缺少必填字段：%s" % f)
    if fm.get("name") != name:
        issues.append("name 与目录名不一致：%s ≠ %s" % (fm.get("name"), name))
    # 平台结构段落（与 validate_skill.py 的 STRUCTURE_HINTS 同口径）
    if not allow_missing_sections:
        for k in missing_structural_sections(body):
            issues.append("缺少「%s」相关内容（平台校验器会判 FAIL；"
                          "用 --ensure-sections 补骨架后按源技能内容改写，"
                          "或手工补写）" % k)
    for p in platform_dir.rglob("*"):
        if p.is_file():
            depth = len(p.relative_to(platform_dir).parts)
            if depth > 2:
                issues.append("目录层级超限（>2 级）：%s" % p.relative_to(platform_dir).as_posix())
    moved_targets = set(rename_map.values())
    for m in PATH_REF_RE.finditer(body):
        if (platform_dir / m.group(1) / m.group(2)).exists():
            continue
        rel = "%s/%s" % (m.group(1), m.group(2))
        if rel in moved_targets:
            issues.append("悬空引用：%s（搬迁后未落盘，属本工具缺陷）" % rel)
        else:
            issues.append("悬空引用：%s（平台版无此文件，且源技能内亦无——"
                          "疑似上游技能自身缺陷，非搬运引入；如需交付请改正文或补文件）" % rel)
    # 引用覆盖：搬迁后的资源文件应至少被正文引用一次（LICENSE / SKILL.md 除外）
    for old_ref, new_ref in rename_map.items():
        if new_ref.endswith("SKILL.md"):
            continue
        if "license" in new_ref.lower():
            continue
        if new_ref not in body:
            warnings.append("搬迁文件未被正文引用：%s（建议人工确认是否需在正文引用）" % new_ref)
    # 许可随包：宽松许可分发时应附许可全文（Apache-2.0 第 4(a) 条等）
    if not any((platform_dir / c).is_file() for c in LICENSE_CANDS):
        warnings.append("平台版未附带源许可文本（LICENSE）——若源为宽松许可，分发时应随附"
                        "许可全文与归属声明（见 THIRD-PARTY-NOTICES.md）")
    return issues, warnings


GENERIC_SEGS = {"skills", "skill", "agents", "agent", "plugins", "plugin", "src",
                "lib", "source", "sources", "references", "scripts", "assets",
                "docs", "doc", "dist", "build", "tests", "test", "examples"}


def _alt_slug(slug, spec):
    """slug 冲突时的消歧名：取源路径中最靠后的一个有区分度的目录段做前缀。

    例：anthropics/commerce-agents@main/profiles/plus/agents/skills/astra-orchestrator
        → plus-astra-orchestrator
        .../profiles/pro/agents/skills/astra-orchestrator
        → pro-astra-orchestrator
    """
    p = Path(spec)
    if p.exists():
        segs = [s for s in p.parts if s and s != p.anchor]
        tail = [segs[-2]] if len(segs) >= 2 else []
    else:
        parsed = _gh_owner_repo(spec)
        sub = (parsed[3] if parsed else None) or ""
        tail = [s for s in sub.split("/") if s][:-1]
    cands = [s for s in tail if s.lower() not in GENERIC_SEGS]
    if not cands:
        cands = tail
    if cands:
        return slugify("%s-%s" % (cands[-1], slug))
    return ""


def _spec_tail(spec):
    """源规格的末段标识（子目录名 / 本地目录名），用于预判同名技能冲突。"""
    p = Path(spec)
    if p.exists():
        return p.name
    parsed = _gh_owner_repo(spec)
    sub = (parsed[3] if parsed else None) or ""
    segs = [s for s in sub.split("/") if s]
    if segs:
        return segs[-1]
    return parsed[1] if parsed else ""


def process_one(spec, source_type, out_root, display_name="", ensure_sections=False,
                no_zip=False, taken_slugs=None, slug_override="", allow_restricted=False,
                no_security_scan=False, inherited_info=None):
    """处理单个源技能，产出双轨（平台版 + 本地版）结果。

    taken_slugs：批量模式传入的已占用 slug 集合。同名 slug 会让后处理的技能
    直接覆盖先处理的产出（porting-changes.md 也被覆盖），是静默数据丢失，
    因此批量模式下必须消歧。单源模式传 None，保持原行为。
    返回结果字典；源解析或处理异常向上抛出，由调用方决定批量时是否继续。
    """
    try:
        src, source_label, stype, fetch_note = resolve_source(spec, source_type, out_root)
    except Exception as e:
        raise RuntimeError("源解析失败：%s" % e)
    # 必须在 src 被重指到技能子目录之前取键：GitHub 子路径源的缓存根名 != 技能目录名
    repo_root_lic = _LICENSE_FALLBACK.get(src.name, "")
    skill_md = src / "SKILL.md"
    if not skill_md.exists():
        cands = list(src.rglob("SKILL.md"))
        if not cands:
            raise RuntimeError("未找到 SKILL.md（源：%s）" % source_label)
        skill_md = cands[0]
        src = skill_md.parent
    hard_dep = detect_hard_dep(src)
    raw = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(raw)

    name = slugify(slug_override or fm.get("name") or src.name)
    slug_note = ""
    if slug_override:
        slug_note = "批量内存在同名技能，已预分配 slug `%s` 以避免产出互相覆盖" % name
    if taken_slugs is not None:
        if name in taken_slugs and not slug_override:
            alt = _alt_slug(name, spec)
            if alt:
                slug_note = ("批量内已有同名技能，slug `%s` → `%s`（避免产出互相覆盖）"
                             % (name, alt))
                name = alt
        taken_slugs.add(name)
    platform_dir = out_root / name
    local_dir = out_root / ("%s-local" % name)
    if platform_dir.exists():
        shutil.rmtree(platform_dir)
    if local_dir.exists():
        shutil.rmtree(local_dir)
    platform_dir.mkdir(parents=True, exist_ok=True)

    source_label = fm.get("author") or source_label
    # 素材元信息：技能级契约文件优先于继承来的仓库级契约。
    # 仓库级信息来自采集端（如 `--material-root` 展开的 SOURCE_INFO.json）——
    # 此前只在 stype=="local" 时读取契约，导致采集端投喂 GitHub 仓时其来源与许可
    # 声明被**完全忽略**，归属声明里只剩 owner/repo，采集端的贡献不可追溯。
    src_info = dict(inherited_info or {})
    _local_info = load_source_info(src)
    if _local_info:
        src_info.update(_local_info)
    declared_raw = (fm.get("license") or "").strip()
    spdx_from_text, lic_text, lic_origin = collect_license_text(src, repo_root_lic, src_info)
    detected_license = spdx_from_text or (declared_raw if declared_raw in KNOWN_SPDX else None)
    lic_class = classify_license(detected_license)
    # 归属可追溯：把采集端声明的平台 / 来源 URL / 采集时间并入来源标签。
    # 没有这一步，采集端投喂的信息虽然进了流程，却在交付物里**看不见**——
    # 出了许可问题无从回溯"这条素材是哪次采集、从哪个平台来的"。
    if src_info:
        bits = []
        if src_info.get("platform"):
            bits.append("采集平台 %s" % src_info["platform"])
        if src_info.get("source_url"):
            bits.append(str(src_info["source_url"]))
        if src_info.get("collected_at"):
            bits.append("采集于 %s" % str(src_info["collected_at"])[:10])
        if bits and not all(b in source_label for b in bits):
            source_label = "%s（%s）" % (source_label, "；".join(bits))

    # 准入门禁：许可未识别/缺失 → 默认拒收（无 LICENSE ≠ 可复制）
    if lic_class == "unknown" and not allow_restricted:
        raise RuntimeError(
            "许可未识别或缺失，按准入策略拒收（源：%s）。作品自创作完成即受《伯尔尼公约》"
            "与中国《著作权法》保护，无 LICENSE ≠ 可自由复制；复制+分发本身即构成侵权，"
            "民事上不以营利为前提。如已确认有权搬运，请加 --allow-restricted 放行"
            "（产出仅本地版、不生成上传包、强制标注风险）。" % source_label)

    # 分发门槛：copyleft 或（显式放行的）未知许可 → 仅本地版，不出上传包
    local_only = (lic_class == "copyleft") or (lic_class == "unknown" and allow_restricted)
    lic_from_root = bool(repo_root_lic) and not has_local_license(src) and bool(detected_license)
    ns = argparse.Namespace(display_name=display_name)
    head, dropped, lic_value, lic_auto = build_frontmatter(fm, name, ns, source_label, detected_license)

    changes = ["# 搬运改动清单", "", "- 源规格：`%s`" % spec,
               "- 来源类型：%s（%s）" % (stype, fetch_note),
               "- 平台版：`%s`" % platform_dir.as_posix(),
               "- 本地版：`%s`" % local_dir.as_posix(), "", "## 一、字段改动", ""]
    if slug_note:
        changes.append("- `name`：%s" % slug_note)
    for fld in ("version", "display_name", "display_name_en", "description_zh", "description_en"):
        changes.append("- `%s`：源缺失，已按映射表补全" % fld)
    raw_lic = (fm.get("license") or "").strip()
    if lic_auto:
        changes.append("- `license`：源缺失或非标准，已根据 LICENSE 文本自动识别为 `%s`%s"
                       % (lic_value,
                          "（该 LICENSE 取自仓库根目录——技能子目录内无 LICENSE，"
                          "子路径搬运场景下的常见情况）" if lic_from_root else ""))
    elif raw_lic in KNOWN_SPDX:
        changes.append("- `license`：源已含标准 SPDX `%s`，沿用" % lic_value)
    elif raw_lic:
        changes.append("- `license`：源值为 `%s`（非标准 SPDX），已原样保留，建议人工核对" % raw_lic)
    else:
        changes.append("- `license`：源无 license 字段且无 LICENSE 文件，未写入，建议人工补充")
    _CLASS_CN = {"permissive": "宽松许可 → 可双轨分发（上架需随附 LICENSE 与归属声明）",
                 "copyleft": "传染性许可 → 仅本地自用，不上架、不对外提供服务",
                 "unknown": "许可未识别 → 受限放行，仅本地自用"}
    changes.append("- 许可准入等级：`%s` —— %s" % (lic_class, _CLASS_CN[lic_class]))
    if slugify(fm.get("name") or "") != name and (fm.get("name") or ""):
        changes.append("- `name`：`%s` → `%s`（保留词或非法字符处理）" % (fm.get("name"), name))
    if dropped:
        changes.append("- `allowed-tools`：移除平台外工具 %s，改为正文步骤或边界说明" % ", ".join(dropped))

    # 平台版：拉平目录
    plan = plan_files(src)
    rename_map = {}
    changes += ["", "## 二、文件搬迁", ""]
    if not plan:
        changes.append("- 源技能无附属资源文件，仅转换 SKILL.md")
    for p, tdir, tname in plan:
        (platform_dir / tdir).mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, platform_dir / tdir / tname)
        old_ref = p.relative_to(src).as_posix()
        new_ref = "%s/%s" % (tdir, tname)
        rename_map[old_ref] = new_ref
        note = "" if old_ref == new_ref else "（原 `%s`）" % old_ref
        changes.append("- `%s/%s`%s" % (tdir, tname, note))

    # 正文引用重写，覆盖三类：
    #   A 完整路径引用（含非标准目录，如 themes/a.md）
    #   B 唯一文件名引用（根级文件，如 theme-showcase.pdf）
    #   C 目录引用（如 `themes/`），替换为搬迁后的目标目录，并列入待人工确认
    any_path_re = re.compile(r"(?<![\w/:.])([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\.[A-Za-z0-9]{1,8})(?![\w/.])")
    base_map, dir_target = {}, {}
    for old_ref, new_ref in rename_map.items():
        if old_ref != new_ref:
            base_map.setdefault(Path(old_ref).name, []).append(new_ref)
        parts = old_ref.split("/")
        if len(parts) > 1:
            dir_target.setdefault(parts[0], new_ref.split("/")[0])
    rewritten, dir_rewritten = [], []

    def rewrite_any(m):
        old = m.group(1)
        if "://" in old:
            return old
        if old in rename_map and rename_map[old] != old:                     # A
            rewritten.append((old, rename_map[old]))
            return rename_map[old]
        cands = base_map.get(Path(old).name, [])                             # B
        if len(cands) == 1 and cands[0] != old:
            rewritten.append((old, cands[0]))
            return cands[0]
        return old

    new_body = any_path_re.sub(rewrite_any, body)

    # 代码模块重命名：core.gif_builder -> gif_builder（仅作用于非标准代码目录迁移）
    module_map = {}
    for old_ref, new_ref in rename_map.items():
        if not new_ref.startswith("scripts/"):
            continue
        if Path(old_ref).suffix.lower() not in SCRIPT_EXT:
            continue
        old_dot = Path(old_ref).with_suffix("").as_posix().replace("/", ".")
        new_mod = Path(new_ref).stem
        if "." in old_dot and old_dot != new_mod:
            module_map[old_dot] = new_mod
    rewritten_modules = []
    for old_dot, new_mod in sorted(module_map.items()):
        pat = re.compile(r"(?<![\w.])" + re.escape(old_dot) + r"(?![\w.])")
        if pat.search(new_body):
            new_body = pat.sub(new_mod, new_body)
            rewritten_modules.append((old_dot, new_mod))

    for d, tgt in sorted(dir_target.items()):                                # C
        pat = r"(?<![\w/])%s/" % re.escape(d)
        if re.search(pat, new_body):
            new_body = re.sub(pat, "%s/" % tgt, new_body)
            dir_rewritten.append((d, tgt))
    missing_sections = missing_structural_sections(new_body)
    added_sections = []
    if ensure_sections and missing_sections:
        new_body, added_sections = fill_structural_sections(new_body)
    dep_hits = sorted({h for h in BODY_DEP_HINTS if h.lower() in new_body.lower()})
    src_kind = {"github": "GitHub 开源仓库", "local": "本地素材"}.get(stype, stype)
    note = ["", "## 搬运说明", "",
            "本技能由上游源技能（%s）转换而来，核心流程与判据保持原样。" % src_kind,
            "许可与归属见同目录 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`。",
            "依赖外部环境的部分已在迁移时标注或移除，执行前请阅读迁移报告中的残留风险。", ""]
    (platform_dir / "SKILL.md").write_text(head + new_body.rstrip() + "\n" + "\n".join(note),
                                           encoding="utf-8")

    # 许可与归属随包分发（Apache-2.0 4(a)/4(c)、MIT/BSD 同类义务）
    lic_written, lic_notes = write_license_bundle(
        platform_dir, detected_license, lic_text, source_label, stype, spec, lic_origin)

    # 本地版：保留原结构
    shutil.copytree(src, local_dir)
    (local_dir / "SKILL.md").write_text(head + body.lstrip("\n"), encoding="utf-8")
    if (lic_text or "").strip() and not has_local_license(src):
        # 本地版原本没有许可文件（技能子目录场景）：补上，避免本地版成为无许可副本
        (local_dir / "LICENSE").write_text(lic_text.rstrip() + "\n", encoding="utf-8")

    # zip（root 直铺）—— 强第三方依赖或 copyleft/受限许可时不出上传包
    zip_path = out_root / ("%s.zip" % name)
    zip_made = False
    if not no_zip and not hard_dep and not local_only:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(platform_dir.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(platform_dir).as_posix())
        zip_made = True
    elif (hard_dep or local_only) and not no_zip and zip_path.exists():
        zip_path.unlink()

    changes += ["", "## 三、正文引用重写", ""]
    if rewritten:
        for old, new in rewritten:
            changes.append("- `%s` → `%s`" % (old, new))
    else:
        changes.append("- 正文未发现需要改写的资源引用")
    for d, tgt in dir_rewritten:
        changes.append("- 目录引用 `%s/` → `%s/`，目录下文件已重命名为 `%s__<name>`，建议人工核对表述"
                       % (d, tgt, d))
    if rewritten_modules:
        for old_dot, new_mod in rewritten_modules:
            changes.append("- 代码模块引用 `%s` → `%s`（脚本已落在 `scripts/`，请按平台执行模型核对 import 形式）"
                           % (old_dot, new_mod))
    changes += ["", "## 四、待人工确认", ""]
    if hard_dep:
        changes.append("- **平台版不可交付**：检测到强第三方依赖（%s），平台沙箱无网无包无法运行，请仅使用本地版。"
                       % "、".join(hard_dep))
    if local_only:
        if lic_class == "copyleft":
            changes.append("- **不得对外分发**：源为传染性许可（`%s`），仅可本地自用。"
                           "对外提供网络服务或分发衍生作品会触发开源义务（AGPL 第 13 条等），"
                           "已不生成上传包。" % (detected_license or "未识别"))
        else:
            changes.append("- **风险放行**：许可未识别且使用了 `--allow-restricted`。"
                           "本产出**仅限本地自用**，不得上架、分发或商用；请尽快向上游确认许可。")
    if added_sections:
        changes.append("- 已补写段落骨架：%s（含补写标注，须按源技能内容改写为具体步骤与判据）"
                       % "、".join(added_sections))
    elif missing_sections:
        changes.append("- 源正文缺少常见段落：%s，建议人工补写或用 --ensure-sections 补骨架"
                       % "、".join(missing_sections))
    if dep_hits:
        changes.append("- 正文仍含联网或安装类语句：%s，平台版须改为内置知识优先并保留离线路径"
                       % "、".join(dep_hits))
    if not display_name:
        changes.append("- `display_name` 为自动推导，建议替换为更贴切的中文名")
    changes.append("- 转换后请运行合规校验，确认零 FAIL 后再上传")
    changes += ["", "## 五、交付物", ""]
    changes.append("- 平台版目录：`%s`" % platform_dir.as_posix())
    changes.append("- 本地版目录：`%s`（复制到 `~/.workbuddy/skills/` 即可用）" % local_dir.as_posix())
    if lic_written:
        changes.append("- 许可随包文件：%s" % "、".join("`%s`" % f for f in lic_written))
    if zip_made:
        changes.append("- 上传包：`%s`（root 直铺）" % zip_path.as_posix())
    elif hard_dep:
        changes.append("- 上传包：**未生成**（强第三方依赖：%s），平台版不可交付，仅本地版可用。"
                       % "、".join(hard_dep))
    elif local_only:
        changes.append("- 上传包：**未生成**（许可为 `%s`，按准入策略不出上架包），仅本地版可用。"
                       % (detected_license or "未识别"))

    # 交付前自检门禁 + 去毒审计（上架前强制工序）
    # 结构段落门禁：仅本地自用产出放宽（平台上传会独立跑同一套校验）
    issues, warnings = self_check(platform_dir, name, rename_map,
                                  allow_missing_sections=local_only)
    tox_verdict, tox_findings = "SKIPPED", []
    if tox is not None and not no_security_scan:
        tox_findings = tox.scan(platform_dir)
        tox_verdict = tox.verdict(tox_findings)
        for f in tox_findings:
            line = "去毒审计·%s：%s（`%s:%d`）%s" % (
                f["category"], f["rule_desc"], f["file"], f["line"], f["action"])
            if f["severity"] == "hard":
                issues.append(line)          # 硬问题与结构硬问题同等待遇：阻断交付
            else:
                warnings.append(line)
    changes += ["", "## 六、交付前自检与去毒审计", ""]
    if issues:
        changes.append("- **FAIL（%d 项硬问题，应修复后再上传）**：" % len(issues))
        for x in issues:
            changes.append("  - %s" % x)
    elif hard_dep:
        changes.append("- 平台版仅作结构校验（不生成上传包）；结构自检通过，未发现硬问题")
    else:
        changes.append("- 必填字段、目录层级、引用完整性（双向）：**PASS**")
    _TOX_CN = {"CLEAN": "未检出风险（硬 0）",
               "REVIEW": "需人工确认（硬 0，待确认 %d 项）" % len(tox_findings),
               "REJECT": "拒绝上架（硬 %d 项）" % len(tox_findings),
               "SKIPPED": "未执行（--no-security-scan 或扫描器不可用）"}
    changes.append("- 去毒审计：**%s** —— %s" % (tox_verdict, _TOX_CN[tox_verdict]))
    if warnings:
        changes.append("- 待人工确认（%d 项）：" % len(warnings))
        for x in warnings:
            changes.append("  - %s" % x)
    # 去毒审计 REJECT → 撤下上传包，避免受污染产物被误传上架
    # 平台侧复核：用平台官方校验器独立跑一遍（自检不能替代平台门禁——实测自检 PASS
    # 的产出会被平台判 FAIL）。仅本地自用产出不做此项：它不上传，不适用平台结构要求。
    if local_only:
        plat_verdict, plat_detail = "SKIPPED", "仅本地自用产出，不做平台侧复核"
    else:
        plat_verdict, plat_detail = run_platform_validation(platform_dir)
    changes.append("- 平台校验（官方 validate_skill.py）：**%s** —— %s"
                   % (plat_verdict, plat_detail))

    if tox_verdict == "REJECT" and zip_made:
        zip_path.unlink()
        zip_made = False
        changes.append("- 上传包：**已撤下**（去毒审计 REJECT，硬问题修复前不得分发）")

    # 每技能改动清单落到各自目录，避免批量时相互覆盖
    (platform_dir / "porting-changes.md").write_text("\n".join(changes) + "\n", encoding="utf-8")

    return {
        "spec": spec, "slug": name, "source_label": source_label, "source_type": stype,
        "license": lic_value, "license_auto": lic_auto, "hard_dep": hard_dep,
        "license_class": lic_class, "local_only": local_only, "license_files": lic_written,
        "tox_verdict": tox_verdict,
        "tox_hard": sum(1 for f in tox_findings if f["severity"] == "hard"),
        "tox_review": sum(1 for f in tox_findings if f["severity"] != "hard"),
        "plat_verdict": plat_verdict, "plat_detail": plat_detail,
        "zip_made": zip_made, "zip_path": (zip_path.as_posix() if zip_made else None),
        "platform_dir": platform_dir.as_posix(), "local_dir": local_dir.as_posix(),
        "issues": issues, "warnings": warnings,
        "added_sections": added_sections, "dep_hits": dep_hits,
    }


def build_batch_report(results, failures, out_root):
    """汇总批量结果，生成 batch-report.md。"""
    total = len(results) + len(failures)
    ok = len(results)
    fail = len(failures)
    hard = sum(1 for r in results if r["issues"])
    lines = ["# 批量搬运报告", "",
             "- 输出根目录：`%s`" % out_root,
             "- 总计：**%d** 个源｜成功 **%d**｜失败 **%d**｜自检硬问题 **%d**" % (total, ok, fail, hard),
             "- 平台校验（官方 validate_skill.py）：通过 **%d**｜不通过 **%d**｜未做 **%d**"
             % (sum(1 for r in results if r.get("plat_verdict") == "通过"),
                sum(1 for r in results if r.get("plat_verdict") == "不通过"),
                sum(1 for r in results if r.get("plat_verdict", "SKIPPED") == "SKIPPED")),
             ""]
    if results:
        lines += ["## 成功清单", "",
                  "| # | 源 | slug | 类型 | 许可证 | 许可等级 | 平台版(zip) | 自检 | 去毒 | 平台校验 | 备注 |",
                  "|---|---|---|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(results, 1):
            if r["issues"]:
                gate = "FAIL(%d)" % len(r["issues"])
            elif r["hard_dep"] or r.get("local_only"):
                gate = "PASS(仅本地版)"
            else:
                gate = "PASS"
            if r["zip_made"]:
                deliver = "✓ 已生成"
            elif r.get("local_only"):
                deliver = "✗ 许可受限"
            elif r["hard_dep"]:
                deliver = "✗ 强依赖阻断"
            else:
                deliver = "—"
            notes = []
            if r["added_sections"]:
                notes.append("补段落骨架")
            if r["dep_hits"]:
                notes.append("含联网语句")
            if r.get("license_files"):
                notes.append("许可随包 %d 件" % len(r["license_files"]))
            if r["warnings"]:
                notes.append("%d 项待确认" % len(r["warnings"]))
            lic = r["license"] or "—"
            tv = r.get("tox_verdict", "SKIPPED")
            tox_cell = {"CLEAN": "✓ 干净", "REVIEW": "⚠ 待确认 %d" % r.get("tox_review", 0),
                        "REJECT": "✗ 硬 %d" % r.get("tox_hard", 0),
                        "SKIPPED": "—"}.get(tv, tv)
            lines.append("| %d | `%s` | `%s` | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                i, r["spec"], r["slug"], r["source_type"], lic,
                r.get("license_class", "—"), deliver, gate, tox_cell,
                r.get("plat_verdict", "—"),
                "、".join(notes) or "—"))
        lines.append("")
    if failures:
        lines += ["## 失败清单", ""]
        for spec, err in failures:
            lines.append("- `%s` → **失败**：%s" % (spec, err))
        lines.append("")
    lines += ["## 产物位置", "",
              "- 每个技能：`<slug>/`（平台版，含 `porting-changes.md`）、`<slug>-local/`（本地版）、`<slug>.zip`（上传包）",
              "- 单个技能的完整改动清单见对应 `<slug>/porting-changes.md`", ""]
    return "\n".join(lines) + "\n"


def _extract_examples(body, limit=5):
    """从正文抽取『何时使用』类句子，作为上架示例问法的原材料。不编造内容。"""
    out = []
    for m in re.finditer(r"(?:当用户|当对方|何时使用|适用于|适用场景|触发(?:词|条件))[：:]?\s*([^\n]{4,80})", body):
        seg = m.group(1).strip(" -·、*>`")
        if seg and seg not in out:
            out.append(seg)
        if len(out) >= limit:
            break
    return out


def _first_paragraph(body, limit=300):
    """取正文第一段实质散文（跳过标题/列表/表格/注释），供运营层写简介时参考。"""
    for chunk in re.split(r"\n\s*\n", body):
        s = chunk.strip()
        if not s or s[0] in "#-*|>" or s.startswith("<!--"):
            continue
        s = re.sub(r"\s+", " ", s)
        if len(s) >= 40:
            return s[:limit].rstrip() + ("…" if len(s) > limit else "")
    return ""


def build_listing_material(results, out_root):
    """生成「上架物料」：平台上架所需的标题/简介/分类/标签/示例问法/检查清单。

    边界：本函数只做**结构化提取**（字段取自 SKILL.md frontmatter 与正文），
    不编造卖点、不做改写成稿——润色与最终定稿属运营层职责。
    许可为 copyleft / unknown 的产出会被排除，不进上架物料。
    返回可上架技能数。
    """
    listing_dir = out_root / "listing"
    listing_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    _BOILER = re.compile(r"^将\s*\S+\s*技能迁移至\s*WorkBuddy")
    for r in results:
        # 排除"不可上架"的产出：受限许可、自检 FAIL、强依赖阻断、平台校验不通过。
        # 注意不按 zip_made 判断——--no-zip 只是暂不打包，不影响可上架性。
        # 平台校验不通过者必须排除：这份清单的"可上架"是要拿去执行上架的，
        # 一旦混入会被平台打回，等于清单说谎。
        if r.get("local_only") or r["issues"] or r["hard_dep"]:
            continue
        if r.get("plat_verdict") == "不通过":
            continue
        pd = Path(r["platform_dir"])
        skill = pd / "SKILL.md"
        if not skill.is_file():
            continue
        fm, body = parse_frontmatter(skill.read_text(encoding="utf-8", errors="replace"))
        title = fm.get("display_name") or fm.get("name") or r["slug"]
        zh = (fm.get("description_zh") or "").strip()
        en = (fm.get("description_en") or "").strip()
        # 自动补的模板句（"将 X 技能迁移至 WorkBuddy…"）不是真简介，必须回落，
        # 否则上架物料全是一句空话，等于没有。
        if zh and not _BOILER.match(zh):
            brief, brief_src, ready = zh, "SKILL.md `description_zh`", True
        elif en:
            brief, brief_src, ready = (first_sentence(en, 140),
                                       "源技能 `description`（英文原文，待运营层改写为中文）", False)
        else:
            brief, brief_src, ready = "", "（源无简介，待运营层据正文补写）", False
        digest = _first_paragraph(body)
        tags = fm.get("tags") or ""
        if isinstance(tags, list):
            tags = "、".join(str(t) for t in tags)
        examples = _extract_examples(body)
        lic = r.get("license") or "未识别"
        card = [
            "# 上架物料 · %s" % title,
            "",
            "| 项 | 内容 |",
            "| --- | --- |",
            "| 技能标识（slug） | `%s` |" % r["slug"],
            "| 上传包 | `%s` |" % (r.get("zip_path") or "—"),
            "| 许可（SPDX） | `%s`（%s） |" % (lic, r.get("license_class", "—")),
            "| 来源 | %s |" % r.get("source_label", "—"),
            "| 许可随包 | %s |" % ("、".join(r.get("license_files") or []) or "无"),
            "| 平台校验（官方校验器） | %s（%s） |" % (r.get("plat_verdict", "—"),
                                                  r.get("plat_detail", "—")),
            "| 结构段落 | %s |" % ("已补骨架：%s —— **须按源技能内容改写成具体条目后再上架**"
                                  % "、".join(r["added_sections"])
                                  if r.get("added_sections") else "源技能自带，无需补写"),
            "",
            "## 一、标题与简介",
            "",
            "- **标题**（建议 ≤ 20 字）：%s" % title,
            "- **一句话简介**：%s" % (brief or "（待补写）"),
            "- 简介取自：%s" % brief_src,
            "",
        ]
        if digest:
            card += ["## 二、原文摘要（改写素材，非成稿）",
                     "",
                     "> %s" % digest,
                     ""]
        card += [
            "## 三、分类与标签",
            "",
            "- **建议分类**：%s" % fm.get("category", "（待运营层确定）"),
            "- **标签**：%s" % (tags or "（待运营层确定）"),
            "",
            "## 四、适用场景（示例问法）",
            "",
        ]
        card += (["- %s" % e for e in examples] if examples
                 else ["- （源正文未提供明确问法，待运营层据正文补写 3 条）"])
        card += [
            "",
            "## 五、上架前检查清单",
            "",
            "- [ ] 一句话简介经运营层改写为中文口语化表述（当前%s）" % ("已可用" if ready else "**仍是英文原文，未改写**"),
            "- [ ] 平台结构段落已按源技能内容改写成具体条目（本项%s）"
            % ("**为通用骨架，未改写**" if r.get("added_sections") else "源技能自带，无需改写"),
            "- [ ] 上传包已随附 `LICENSE` 与 `THIRD-PARTY-NOTICES.md`（合规硬要求）",
            "- [ ] 许可等级为 `permissive`（copyleft / unknown 不得上架）",
            "- [ ] 标题与简介经运营层润色，无夸大与绝对化表述",
            "- [ ] 上架后登记到台账，避免重复上架同一能力",
            "",
            "> 由 `port_skill.py --listing` 机械生成：字段取自 SKILL.md，未编造卖点；",
            "> 最终文案由运营层定稿。",
        ]
        (listing_dir / ("%s.md" % r["slug"])).write_text("\n".join(card) + "\n", encoding="utf-8")
        rows.append((r["slug"], title, lic, r.get("license_class", "—"), brief, ready))

    lines = ["# 上架清单", "",
             "- 可上架技能：**%d** 个" % len(rows),
             "- 收录门槛：许可为 `permissive` ＋ 自检无硬问题 ＋ **平台校验器判定「通过」**"
             "（排除 copyleft / unknown / 强依赖 / 平台校验不通过者）",
             "- 一句话简介可直接用：**%d** 个；待运营层改写：**%d** 个"
             % (sum(1 for x in rows if x[5]), sum(1 for x in rows if not x[5])),
             "- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M"),
             "",
             "| # | slug | 标题 | 许可 | 等级 | 简介状态 | 一句话简介 |",
             "|---|---|---|---|---|---|---|"]
    for i, (slug, title, lic, cls, brief, ready) in enumerate(rows, 1):
        lines.append("| %d | `%s` | %s | %s | %s | %s | %s |"
                     % (i, slug, title, lic, cls, "可直接用" if ready else "待改写",
                        (brief or "—")[:70]))
    lines += ["", "> 每项详情见 `listing/<slug>.md`。许可为 copyleft / unknown 的产出已排除，"
              "不会出现在本清单中。"]
    (listing_dir / "上架清单.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


# ------------------------------------------------- 跨会话公示（能力名片）

_PEER_VER = "porter@v1.9.0"
_PEER_ROLE = "技能搬运引擎（GitHub → 平台技能包）"


def _session_root():
    """推断本会话工作目录，供共享层通讯录取 session_id。"""
    for p in [_HERE] + list(_HERE.parents):
        if p.parent.name.lower() == "workbuddy":
            return str(p)
    return None


def _capabilities():
    """对外公示的能力清单——别的会话据此决定「要不要来找我」。"""
    base = "skill-build/github-skill-porter/scripts"
    return [
        {"key": "skill-port",
         "desc": "把 GitHub 仓库/子目录或本地素材搬成合规平台技能包（SKILL.md 补全 + 自检 + zip）",
         "entry": "%s/port_skill.py" % base,
         "contract": "输入 owner/repo[@branch][/sub] 或本地路径；输出 <slug>/、<slug>-local/、<slug>.zip"},
        {"key": "license-gate",
         "desc": "许可准入门禁与许可随包：无许可/未识别拒收、copyleft 仅本地、宽松许可强制附 LICENSE 全文与归属声明",
         "entry": "%s/port_skill.py" % base,
         "contract": "无需额外参数即生效；确已获授权时 --allow-restricted 放行（仅本地版、强制标风险）。"
                     "产出内必含 LICENSE + THIRD-PARTY-NOTICES.md"},
        {"key": "source-intake",
         "desc": "GitHub 之外的采集源接入契约：素材根放 SOURCE_INFO.json 即可，新增平台无需改代码",
         "entry": "%s/port_skill.py" % base,
         "contract": "SOURCE_INFO.json 字段：platform/source_url/author/license/license_text/collected_at；"
                     "该文件不进产出，信息进归属声明"},
        {"key": "listing-material",
         "desc": "生成平台上架物料（标题/简介/原文摘要/分类标签/示例问法/上架检查清单），自动排除受限产出",
         "entry": "%s/port_skill.py --listing" % base,
         "contract": "输入已产出技能包；输出 <out>/listing/<slug>.md + 上架清单.md（不写文案，待运营层定稿）"},
        {"key": "repo-tree-probe",
         "desc": "探测 GitHub 仓库文件结构并落共享缓存（免重复 API 调用）",
         "entry": "%s/bridge_trending.py" % base,
         "contract": "输入 owner/repo 列表；输出 trees.json + manifest.txt"},
        {"key": "trending-bridge",
         "desc": "解析《采集雷达》日更报告 → 可搬运性三分类 → 批量清单",
         "entry": "%s/bridge_trending.py" % base,
         "contract": "输入雷达 markdown；输出 bridge-report.md + manifest.txt（可直接喂 port_skill --batch）"},
        {"key": "skill-localize-zh",
         "desc": "技能中文化改写与合规门禁（覆盖率检查）",
         "entry": "%s/check_localization.py" % base,
         "contract": "输入技能目录；输出译覆盖率报告 + 未译行清单"},
    ]


def _announce_self():
    """把自己登记进共享层通讯录；已登记则只续期（低开销）。

    跨会话没有实时通道——名片是**异步公示**，别的会话下次运行时才会看到。
    版本号变化时才重写完整名片（能力清单可能已更新）。
    """
    try:
        root = _session_root()
        sid = shared.session_id(root)
        cur = next((r for r in shared.peers() if r.get("session_id") == sid), None)
        if cur is not None and cur.get("notes") == _PEER_VER:
            shared.heartbeat(root=root, role=_PEER_ROLE)
            return
        shared.announce(
            _PEER_ROLE,
            capabilities=_capabilities(),
            provides=["平台技能 zip 包（含 LICENSE 与归属声明）", "本地技能目录",
                      "文件树缓存", "许可证识别与准入判定", "上架物料（listing/）"],
            consumes=["GitHub 采集雷达报告（markdown）",
                      "任何采集源的素材目录（按 SOURCE_INFO.json 契约投喂，不限 GitHub）"],
            shared_scope={
                "reads": ["trees/", "src/", "licenses/", "peers/"],
                "writes": ["src/", "licenses/", "trees/", "repos.json",
                           "stats.json", "peers/", "PEERS.md", "INDEX.md"],
            },
            notes=_PEER_VER,
            root=root,
        )
    except Exception:
        pass          # 公示失败绝不影响搬运主流程


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?")
    ap.add_argument("--source", action="append", default=[], help="额外源（可多次）：本地路径或 GitHub 地址")
    ap.add_argument("--batch", default="", help="清单文件：每行一个源（# 开头为注释）")
    ap.add_argument("--out", default=".")
    ap.add_argument("--display-name", default="")
    ap.add_argument("--ensure-sections", action="store_true",
                    help="缺失平台结构段落（执行流程/边界与降级/质量自检）时补写骨架。"
                         "**英文源技能几乎必然缺失**（平台正则只认中文词），"
                         "不补则该产出会被平台校验器判 FAIL，无法上架——"
                         "除非只做本地自用（本地版放宽此检查）")
    ap.add_argument("--no-zip", action="store_true")
    ap.add_argument("--source-type", default="auto", choices=["auto", "local", "github"])
    ap.add_argument("--allow-restricted", action="store_true",
                    help="放行许可未识别的源（产出仅本地版、不出上传包、强制标注风险）")
    ap.add_argument("--listing", action="store_true",
                    help="额外生成上架物料（<输出根>/listing/），供运营层定稿上架")
    ap.add_argument("--no-security-scan", action="store_true",
                    help="跳过去毒审计（默认执行；硬问题按交付门禁阻断）")
    ap.add_argument("--tree-cache", default="",
                    help="git trees 缓存 json（bridge_trending.py 产出），命中则不调用 GitHub API")
    ap.add_argument("--material-root", default="",
                    help="仓库级素材根目录（采集端产出：`<owner>__<repo>/SOURCE_INFO.json`）。"
                         "自动展开为技能级源、探测文件树并继承其来源与许可声明；"
                         "采集端无需改一行即可接入（补 P-0005 契约的仓库级粒度）")
    ap.add_argument("--material-limit", type=int, default=0,
                    help="配合 --material-root：每个仓库最多展开多少个技能源（0=不限）。"
                         "实测单仓可含数千个 SKILL.md（如某技能合集 3596 个），"
                         "先用小样本验证链路再放量")
    ap.add_argument("--no-shared-cache", action="store_true",
                    help="关闭用户级共享缓存（默认开启）：不复用跨会话的源码与文件树缓存")
    args = ap.parse_args()

    global _USE_SHARED
    if args.no_shared_cache:
        _USE_SHARED = False
        print("[cache] 用户级共享缓存：已关闭（--no-shared-cache）")
    else:
        print("[cache] 用户级共享缓存：%s" % shared.shared_root().as_posix())
        _announce_self()

    if args.tree_cache:
        n = load_tree_cache(args.tree_cache)
        print("[cache] 已载入 %d 个仓库的文件树缓存（不含 SKILL.md 内容的下载）" % n)

    specs = []
    if args.batch:
        bp = Path(args.batch)
        if not bp.is_file():
            print("[error] 清单文件不存在：%s" % args.batch)
            sys.exit(2)
        for line in bp.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            specs.append(s)
    if args.source:
        specs.extend(args.source)
    if args.src:
        specs.append(args.src)
    specs = [s for s in specs if s]

    # 仓库级素材根：展开为技能级源，并让每个技能继承仓库级的来源与许可声明
    mat_inherit = {}
    if args.material_root:
        m_specs, mat_inherit, mat_notes = expand_material_root(args.material_root,
                                                               args.material_limit)
        specs.extend(m_specs)
        print("\n[素材根] %s" % args.material_root)
        for n in mat_notes:
            print("  %s" % n)

    if not specs:
        print("[error] 未指定任何源：请用 <src> 位置参数、--source、--batch 或 --material-root 指定至少一个源")
        sys.exit(2)

    out_root = Path(args.out).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    # 单源：保持原行为（改动清单同时落到 out_root，便于向下兼容）
    if len(specs) == 1:
        try:
            res = process_one(specs[0], args.source_type, out_root,
                              args.display_name, args.ensure_sections, args.no_zip,
                              allow_restricted=args.allow_restricted,
                              no_security_scan=args.no_security_scan,
                              inherited_info=mat_inherit.get(specs[0]))
        except Exception as e:
            print("[error] %s" % e)
            sys.exit(1)
        ch = Path(res["platform_dir"]) / "porting-changes.md"
        (out_root / "porting-changes.md").write_text(ch.read_text(encoding="utf-8"), encoding="utf-8")
        print(ch.read_text(encoding="utf-8"))
        if args.listing:
            n = build_listing_material([res], out_root)
            print("\n上架物料：%d 项 -> %s" % (n, (out_root / "listing").as_posix()))
        print("\n完成：%s" % res["slug"])
        if res["issues"]:
            print("[gate] 交付前自检 FAIL：%d 项硬问题，已阻断（非零退出），请修复后重跑" % len(res["issues"]))
            sys.exit(1)
        sys.exit(0)

    # 多源：批量模式
    # 预扫描同名技能：如 profiles/plus 与 profiles/pro 下各有一个 astra-orchestrator，
    # 两者 slug 相同会互相覆盖产出。先统一分配消歧 slug，让两份都拿到带前缀的名字。
    tails = {}
    for s in specs:
        tails.setdefault(_spec_tail(s), []).append(s)
    overrides = {}
    for tail, group in tails.items():
        if tail and len(group) > 1:
            for s in group:
                alt = _alt_slug(slugify(tail), s)
                if alt:
                    overrides[s] = alt
    if overrides:
        print("[slug] 检测到 %d 个同名技能，已预分配消歧 slug" % len(overrides))

    results, failures = [], []
    taken_slugs = set()
    for spec in specs:
        try:
            res = process_one(spec, args.source_type, out_root,
                              args.display_name, args.ensure_sections, args.no_zip,
                              taken_slugs=taken_slugs,
                              slug_override=overrides.get(spec, ""),
                              allow_restricted=args.allow_restricted,
                              no_security_scan=args.no_security_scan,
                              inherited_info=mat_inherit.get(spec))
            results.append(res)
            print("[ok] %s -> %s（%s）" % (spec, res["slug"],
                  "FAIL" if res["issues"] else
                  ("仅本地版" if (res["hard_dep"] or res.get("local_only")) else "PASS")))
        except Exception as e:
            failures.append((spec, str(e)))
            print("[fail] %s -> %s" % (spec, e))
    report = build_batch_report(results, failures, out_root.as_posix())
    (out_root / "batch-report.md").write_text(report, encoding="utf-8")
    print("\n" + report)
    if args.listing:
        n = build_listing_material(results, out_root)
        print("上架物料：%d 项可上架 -> %s" % (n, (out_root / "listing").as_posix()))
    if any(r["issues"] for r in results) or failures:
        print("[gate] 批量存在硬问题或失败项，非零退出")
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
