#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可迁移性体检：扫描 Agent Skills 源技能，输出五类风险报告。

用法：
    python audit_skill.py <源目录> [--out <报告文件>]

检查五类：外部依赖 / 目录层级 / 命名保留词 / 许可证 / 工具名。
每类逐项给出 阻断 / 降级 / 通过，并给出处置动作。
结论三选一：可直接搬 / 需改造 / 不建议搬。

退出码：0 = 可搬运（无未处置阻断），2 = 存在阻断。
依赖：仅 Python 标准库（3.6+）。
"""
import re
import sys
from pathlib import Path

try:
    STDLIB = set(sys.stdlib_module_names)
except AttributeError:
    STDLIB = set("""
os sys re json csv math io time datetime pathlib shutil subprocess argparse
collections itertools functools typing textwrap unittest logging tempfile
zipfile tarfile hashlib base64 urllib http socket ssl glob fnmatch random
string struct pickle copy enum dataclasses abc contextlib warnings traceback
""".split()) | {"__future__"}

STDLIB |= {"setuptools", "pip", "pkg_resources"}

STD_DIRS = {"references", "scripts", "assets"}
PLATFORM_TOOLS = {"Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"}
RESERVED = {"claude", "anthropic", "claude-code", "chatgpt", "gpt", "gemini", "copilot", "codex"}
SOURCE_AVAILABLE_HINTS = {"docx", "pdf", "pptx", "xlsx", "document-skills"}
NET_HINTS = ("curl ", "wget ", "pip install", "npm install", "requests.", "urllib.request",
             "httpx", "fetch(", "fetch (", "联网", "在线查询", "WebFetch", "WebSearch")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
IMPORT_RE = re.compile(r"^\s*(?:import|from)\s+([A-Za-z_][A-Za-z0-9_]*)", re.M)


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, "无 frontmatter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text, "frontmatter 未闭合"
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
    return fm, "\n".join(lines[end + 1:]), None


class Findings:
    def __init__(self):
        self.rows = []

    def add(self, category, item, level, action):
        self.rows.append((category, item, level, action))

    def blocking(self):
        return [r for r in self.rows if r[2] == "阻断"]


def scan(root: Path):
    f = Findings()
    skill_md = root / "SKILL.md"
    if not skill_md.exists():
        cands = list(root.rglob("SKILL.md"))
        if not cands:
            f.add("结构", "未找到 SKILL.md", "阻断", "确认输入目录是否为技能根目录")
            return f
        skill_md = cands[0]
        f.add("结构", "SKILL.md 位于子目录", "降级", "以该子目录为技能根重新体检")
        root = skill_md.parent

    text = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body, fm_err = parse_frontmatter(text)
    if fm_err:
        f.add("命名", fm_err, "阻断", "按模板补最小 frontmatter（name + description）")

    # A 外部依赖
    third_party, net_hits = set(), set()
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in (".py", ".sh", ".js", ".ps1", ".ts"):
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        for mod in IMPORT_RE.findall(src):
            if mod not in STDLIB:
                third_party.add(mod)
        for hint in NET_HINTS:
            if hint in src:
                net_hits.add(hint.strip())
    if third_party:
        f.add("外部依赖", "第三方包：" + ", ".join(sorted(third_party)[:12]), "阻断",
              "平台版改用标准库实现或改为文字规则；本地版可保留")
    else:
        f.add("外部依赖", "未发现第三方包", "通过", "无需处理")
    if net_hits:
        f.add("外部依赖", "联网/安装行为：" + ", ".join(sorted(net_hits)[:8]), "阻断",
              "删除安装类命令；联网改为可选增强并保留离线路径")
    else:
        f.add("外部依赖", "无联网或安装行为", "通过", "无需处理")

    # B 目录层级
    deep = [p.relative_to(root).as_posix() for p in root.rglob("*")
            if p.is_file() and len(p.relative_to(root).parts) > 2]
    if deep:
        f.add("目录层级", "超过两级：" + deep[0] + (" 等 %d 项" % len(deep) if len(deep) > 1 else ""),
              "阻断", "拉平为两级，中间路径用双下划线并入文件名")
    else:
        f.add("目录层级", "层级合规", "通过", "无需处理")
    extra = sorted({p.name for p in root.iterdir()
                    if p.is_dir() and p.name not in STD_DIRS and not p.name.startswith(".")})
    if extra:
        f.add("目录层级", "非标准一级目录：" + ", ".join(extra), "降级",
              "重命名或迁移到 references / scripts / assets")

    # C 命名
    name = (fm.get("name") or "").strip()
    if not name:
        f.add("命名", "name 缺失", "阻断", "按目录名 slug 化生成")
    else:
        if not NAME_RE.match(name):
            f.add("命名", "name 不合规范：" + name, "阻断", "小写化、下划线与空格转连字符")
        if len(name) > 64:
            f.add("命名", "name 超过 64 字符", "阻断", "按 token 边界截断")
        hit = sorted({t for t in name.split("-") if t in RESERVED})
        if hit:
            f.add("命名", "name 含保留词：" + ", ".join(hit), "阻断", "删除保留词 token 后重新 slug 化")
        if root.name != name:
            f.add("命名", "目录名与 name 不一致（%s / %s）" % (root.name, name), "阻断", "统一为 name")
    desc = fm.get("description") or ""
    if len(desc) > 1024:
        f.add("命名", "description 超过 1024 字符（当前 %d）" % len(desc), "阻断",
              "压缩为「何时使用 + 产出 + 不适用于」三段式")
    for fld in ("version", "display_name", "display_name_en", "description_zh", "description_en"):
        if not fm.get(fld):
            f.add("命名", "缺少平台必填字段：" + fld, "阻断", "按字段映射表补全")

    # D 许可证
    license_files = [p.name for p in root.iterdir() if p.is_file() and p.name.upper().startswith("LICENSE")]
    if not license_files and not (root.parent / "LICENSE").exists():
        f.add("许可证", "未声明许可证", "降级", "标注「许可未声明」，仅本地自用")
    else:
        f.add("许可证", "许可证文件：" + (license_files[0] if license_files else "仓库根 LICENSE"), "通过", "保留署名")
    root_posix = root.as_posix().lower()
    sa_hit = sorted({h for h in SOURCE_AVAILABLE_HINTS if h in root_posix})
    if sa_hit:
        f.add("许可证", "疑似 source-available 内容：" + ", ".join(sa_hit), "阻断",
              "仅产本地版，公开上传需自行取得授权")
    secret_pat = re.compile(r"(sk-[A-Za-z0-9]{16,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16})")
    secrets = set()
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in (".py", ".sh", ".js", ".md", ".json", ".yaml", ".yml", ".env"):
            try:
                m = secret_pat.search(p.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue
            if m:
                secrets.add(p.name)
    if secrets:
        f.add("许可证", "疑似密钥：" + ", ".join(sorted(secrets)), "阻断", "清除并改为环境变量说明")
    else:
        f.add("许可证", "未发现密钥", "通过", "无需处理")

    # E 工具名与运行时
    tools = [t.strip() for t in (fm.get("allowed-tools") or "").split(",") if t.strip()]
    if tools:
        outside = [t for t in tools if t not in PLATFORM_TOOLS]
        if outside:
            f.add("工具名", "平台工具集外工具：" + ", ".join(outside), "阻断",
                  "删除并改为正文步骤，或写入「不适用于」")
        else:
            f.add("工具名", "工具声明全部可映射", "通过", "无需处理")
    else:
        f.add("工具名", "未声明 allowed-tools", "通过", "按平台工具集补充声明")
    return f


def render(root: Path, f: Findings):
    blocking = f.blocking()
    if blocking:
        conclusion = "需改造（%d 项阻断，按处置动作完成后可搬）" % len(blocking)
    elif any(r[2] == "降级" for r in f.rows):
        conclusion = "需改造"
    else:
        conclusion = "可直接搬"
    lines = ["# 可迁移性体检报告", "", "- 源目录：`%s`" % root.as_posix(),
             "- 结论：**%s**" % conclusion, "",
             "| 类别 | 检查项 | 判定 | 处置动作 |", "|---|---|---|---|"]
    for c, i, lv, a in f.rows:
        lines.append("| %s | %s | %s | %s |" % (c, i, lv, a))
    lines += ["", "## 判定规则", "",
              "- 存在阻断项但均已按处置动作完成改造 → 可搬；",
              "- 阻断项无法处置（如强环境依赖） → 不建议搬，仅产本地版；",
              "- source-available 内容不得公开发布，仅产本地自用版。", ""]
    return "\n".join(lines), conclusion


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = [a for a in sys.argv[1:]]
    out = None
    if "--out" in args:
        idx = args.index("--out")
        out = Path(args[idx + 1])
        del args[idx:idx + 2]
    if not args:
        print(__doc__)
        sys.exit(1)
    root = Path(args[0]).resolve()
    if not root.is_dir():
        print("[error] 目录不存在：%s" % root)
        sys.exit(1)
    report, conclusion = render(root, scan(root))
    print(report)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print("\n报告已写入：%s" % out.as_posix())
    sys.exit(2 if conclusion.startswith("需改造") and "阻断" in conclusion else 0)


if __name__ == "__main__":
    main()
