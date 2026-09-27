#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""去毒审计：扫描技能源码中的安全风险（上架前的强制工序）。

为什么需要它
------------
技能不是文档，是**可执行代码**，拥有与 Agent 相同的权限——可读文件系统、
读环境变量、执行 Shell。已公开的实测数据（二手，见 SOURCES_MAP.md）：

    ClawHub 341 个恶意技能分发 macOS 恶意软件（ClawHavoc）
    ClawHub 全量扫描 7.1% 技能在源码里硬编码 API Key
    1200+ 技能排查：36% 含提示词注入
    22,511 个技能审计出 140,963 个问题（平均 6.3 个/技能）
    MCP 生态 60 天 30 个 CVE，其中 82% 为路径遍历

**刮取谁都会，净化不是。** 本脚本是转换引擎「去毒＋合并＋中文化＋可安装」四合一
里"去毒"这一段的实现。

判定分级
--------
    hard    硬问题：必须修复或拒收，不得上架（凭据泄露 / 注入 / 反弹 shell 等）
    review  需人工确认：可能是误报，须逐条判定后才可上架

用法
----
    python scan_toxicity.py <技能目录> [<技能目录> ...]
    python scan_toxicity.py --batch <清单文件>       # 每行一个目录，# 注释
    python scan_toxicity.py <目录> --json           # 机器可读
    python scan_toxicity.py <目录> --quiet          # 只输出结论行

退出码：检出 hard 问题 → 1；仅 review 或干净 → 0。
（作为门禁时用退出码判断；作为报告时可读 markdown 全文。）

依赖：仅 Python 标准库（3.6+）。
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- 规则表
# 每条：(类别, 级别, 正则, 说明, 处置建议)
# 级别 hard = 不得上架；review = 需人工确认
RULES = [
    # ---------- 凭据泄露 ----------
    ("凭据泄露", "hard", r"sk-ant-[A-Za-z0-9_\-]{20,}",
     "Anthropic API Key 明文", "删除并改为环境变量引用"),
    ("凭据泄露", "hard", r"\bsk-[A-Za-z0-9]{32,}\b",
     "OpenAI 风格 API Key 明文", "删除并改为环境变量引用"),
    ("凭据泄露", "hard", r"\bghp_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{20,}\b",
     "GitHub Token 明文", "撤销该 token 并改为环境变量引用"),
    ("凭据泄露", "hard", r"\bAKIA[0-9A-Z]{16}\b",
     "AWS Access Key 明文", "撤销该密钥并改为环境变量引用"),
    ("凭据泄露", "hard", r"\bAIza[0-9A-Za-z_\-]{30,}\b",
     "Google API Key 明文", "删除并改为环境变量引用"),
    ("凭据泄露", "hard", r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b",
     "Slack Token 明文", "撤销并改为环境变量引用"),
    ("凭据泄露", "hard", r"\b(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{20,}\b",
     "Stripe 密钥明文", "撤销并改为环境变量引用"),
    ("凭据泄露", "hard", r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
     "私钥文件内容", "移除私钥，改为运行时注入"),
    ("凭据泄露", "review", r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b",
     "疑似 JWT（可能为示例值）", "确认非真实令牌后保留，否则移除"),
    ("凭据泄露", "review",
     r"(?i)\b(?:api[_-]?key|secret|password|passwd|access[_-]?token|auth[_-]?token)\b"
     r"\s*[:=]\s*[\"'][A-Za-z0-9\-_+/]{16,}[\"']",
     "疑似硬编码凭据（赋值形式）", "确认为占位符还是真实凭据；真实凭据必须移除"),

    # ---------- 提示词注入 / 隐蔽指令 ----------
    ("提示词注入", "hard",
     r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior|above|earlier|preceding)\s+"
     r"(?:instructions?|rules?|prompts?|directives?)",
     "英文越权指令（ignore previous instructions）", "删除该指令片段"),
    ("提示词注入", "hard",
     r"忽略(?:以上|之前|前面|上述)(?:的)?(?:所有)?(?:指令|规则|提示|要求)",
     "中文越权指令（忽略以上指令）", "删除该指令片段"),
    ("提示词注入", "hard",
     r"(?i)\bdo\s+not\s+(?:tell|inform|mention|reveal|disclose)\s+(?:the\s+)?"
     r"(?:user|human|operator)",
     "要求对用户隐瞒（do not tell the user）", "删除该指令片段"),
    ("提示词注入", "hard",
     r"(?i)\byou\s+are\s+now\s+(?:a|an|the)\b|从现在起你是|你现在(?:是|扮演)",
     "身份覆盖（越权重设角色）", "删除，或改为技能内的显式角色定义"),
    ("提示词注入", "hard", r"[\u202a-\u202e\u2066-\u2069]",
     "Unicode 双向控制字符（Trojan Source 载体）", "移除控制字符并在编辑器中复核差异"),
    ("提示词注入", "review",
     r"<!--(?:(?!-->)[\s\S]){0,400}?(?:忽略|ignore|system|指令|instruction)"
     r"(?:(?!-->)[\s\S]){0,400}?-->",
     "HTML 注释内的疑似隐蔽指令", "确认为说明性注释还是隐蔽指令"),
    ("提示词注入", "hard",
     r"(?i)\b(?:send|upload|post|exfiltrate|transmit|leak)\b[\s\S]{0,40}?"
     r"\b(?:env|environment|credential|token|api[_\s]?key|\.ssh|id_rsa)\b",
     "疑似凭据外传（读取敏感项后发送/上传）", "删除外传逻辑"),

    # ---------- 危险执行 ----------
    ("危险执行", "hard",
     r"rm\s+-[a-zA-Z]*[rR][a-zA-Z]*f[a-zA-Z]*\s+(?:/|~|\$HOME|\$\{HOME\})(?=[\"'\s;|&]|$)",
     "递归删除根/家目录", "删除该命令；如属说明性示例须改为非破坏性写法"),
    ("危险执行", "hard",
     r"(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|k)?sh\b",
     "管道执行远程脚本（curl | sh）", "改为先下载、校验哈希、再显式执行"),
    ("危险执行", "hard",
     r"base64\s+(?:-[dD]\b|-{1,2}decode\b)[^\n|]{0,120}\|\s*(?:ba|z|k)?sh\b",
     "base64 解码后管道执行（混淆载荷）", "拒绝：属典型混淆手法"),
    ("危险执行", "hard",
     r"(?:/dev/tcp/|(?:nc|ncat|netcat)\s+-[a-zA-Z]*e[a-zA-Z]*\s)",
     "反弹 shell 特征", "拒绝：属后门手法"),
    ("危险执行", "hard", r"subprocess\.(?:run|call|check_output|Popen)\s*\([^)]*shell\s*=\s*True",
     "shell=True 执行子进程（注入面）", "改为列表参数调用，禁用 shell=True"),
    ("危险执行", "review", r"(?:os\.system\s*\(|\beval\s*\(|\bexec\s*\()",
     "动态执行（eval / exec / os.system）", "确认入参不可由外部控制"),
    ("危险执行", "review", r"chmod\s+(?:-R\s+)?777\b",
     "过度宽松权限（chmod 777）", "改为最小必要权限"),

    # ---------- 敏感读取 / 外传 ----------
    ("敏感读取", "hard", r"(?:~|\$HOME)?/?\.ssh/(?:id_[a-z0-9]+|authorized_keys|config)\b",
     "读取 SSH 私钥 / 授权文件", "删除该读取逻辑"),
    ("敏感读取", "hard", r"\.aws/credentials\b|\.config/gcloud/|\.docker/config\.json\b",
     "读取云凭据文件", "删除该读取逻辑"),
    ("敏感读取", "review", r"(?i)(?:printenv\b|os\.environ\b|process\.env\b)[\s\S]{0,80}"
                        r"(?:requests\.post|urllib|http\.client|fetch\(|axios)",
     "环境变量与网络请求同时出现（疑似外传）", "确认环境变量未被发送到外部"),

    # ---------- 路径遍历 ----------
    ("路径遍历", "review", r"(?:\.\./){3,}",
     "多级上级目录引用（../../..）", "确认未越出技能目录"),
    ("路径遍历", "review", r"(?i)(?:open|read_text|readBytes|cat)\s*\([^)]*\.\./",
     "带上级路径的文件读取", "改用技能内相对路径"),

    # ---------- 供应链 ----------
    ("供应链", "hard", r"pip\s+install\b[^\n]{0,120}(?:--index-url|--extra-index-url|-i)\s+http://",
     "从非 HTTPS 源安装依赖", "改为 HTTPS 官方源或锁定哈希"),
    ("供应链", "review", r"pip\s+install\s+[A-Za-z0-9_.\-]+(?:\s|$)",
     "未锁定版本的依赖安装", "锁定版本号或提供哈希"),
    ("供应链", "review", r"npx\s+(?:-[a-zA-Z]+\s+)*[A-Za-z0-9@/_.\-]+(?:\s|$)",
     "npx 拉取远端包（供应链风险）", "确认包名与发布者可信"),
]

# 扫描时跳过的路径片段与扩展名
SKIP_PARTS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "_src_cache"}
SKIP_SUFFIX = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip",
               ".gz", ".tar", ".woff", ".woff2", ".ttf", ".otf", ".mp4", ".mp3",
               ".pyc", ".so", ".dll", ".dylib", ".bin", ".xlsx", ".docx", ".pptx"}
TEXT_SUFFIX = {".md", ".txt", ".py", ".sh", ".bash", ".js", ".mjs", ".cjs", ".ts",
               ".ps1", ".bat", ".cmd", ".json", ".yaml", ".yml", ".toml", ".ini",
               ".cfg", ".html", ".xml", ".rst", ".csv", ""}
MAX_BYTES = 2 * 1024 * 1024   # 单文件扫描上限，防大文件拖慢
SEV_ORDER = {"hard": 0, "review": 1}


def _iter_text_files(root):
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIX:
            continue
        if p.suffix.lower() not in TEXT_SUFFIX:
            continue
        try:
            if p.stat().st_size > MAX_BYTES:
                continue
        except OSError:
            continue
        yield p


def scan(root):
    """扫描单个技能目录，返回 findings 列表。

    每条 finding：{category, severity, rule_desc, action, file, line, evidence}
    evidence 为命中片段（截断至 120 字符），便于人工复核。
    """
    root = Path(root)
    findings = []
    seen = set()
    for p in _iter_text_files(root):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = p.relative_to(root).as_posix()
        for lineno, line in enumerate(text.splitlines(), 1):
            for cat, sev, pat, desc, action in RULES:
                m = re.search(pat, line)
                if not m:
                    continue
                ev = m.group(0).replace("\n", " ")
                if len(ev) > 120:
                    ev = ev[:120] + "…"
                key = (rel, lineno, desc)
                if key in seen:
                    continue          # 同一行同一规则只报一次；不同规则**全部**报出
                seen.add(key)
                findings.append({
                    "category": cat, "severity": sev, "rule_desc": desc,
                    "action": action, "file": rel, "line": lineno, "evidence": ev,
                })
    # review 级去噪：同一文件内「同一规则 + 同一证据」只报一条并附出现次数。
    # 实测：某技能的未固定版本包在正文出现 9 次即报 9 条，噪声淹没真信号。
    # hard 级不去噪——每一处都必须逐条修复。
    out, agg = [], {}
    for f in findings:
        if f["severity"] != "review":
            out.append(f)
            continue
        key = (f["file"], f["rule_desc"], f["evidence"])
        if key in agg:
            agg[key]["count"] += 1
            continue
        g = dict(f)
        g["count"] = 1
        agg[key] = g
        out.append(g)
    return out


def verdict(findings):
    """REJECT / REVIEW / CLEAN。"""
    if any(f["severity"] == "hard" for f in findings):
        return "REJECT"
    if findings:
        return "REVIEW"
    return "CLEAN"


def report_md(root, findings):
    v = verdict(findings)
    hard = [f for f in findings if f["severity"] == "hard"]
    review = [f for f in findings if f["severity"] == "review"]
    lines = [
        "# 去毒审计报告",
        "",
        "- 扫描目标：`%s`" % Path(root).as_posix(),
        "- 结论：**%s**" % {"REJECT": "拒绝上架（存在硬问题）",
                            "REVIEW": "需人工确认后才可上架",
                            "CLEAN": "未检出风险"}[v],
        "- 命中：硬问题 **%d** 项，需确认 **%d** 项" % (len(hard), len(review)),
        "",
    ]
    if not findings:
        lines += ["未命中任何规则。规则表覆盖：凭据泄露、提示词注入、危险执行、"
                  "敏感读取、路径遍历、供应链六类。", ""]
        return "\n".join(lines) + "\n"
    for sev, title in (("hard", "一、硬问题（不得上架）"),
                       ("review", "二、需人工确认")):
        group = [f for f in findings if f["severity"] == sev]
        if not group:
            continue
        lines += ["## %s" % title, "",
                  "| # | 类别 | 位置 | 证据 | 处置 |",
                  "|---|---|---|---|---|"]
        for i, f in enumerate(group, 1):
            ev = f["evidence"].replace("|", "\\|")
            n = f.get("count", 1)
            if n > 1:
                ev = "%s（同一文件共 %d 处）" % (ev, n)
            lines.append("| %d | %s · %s | `%s:%d` | `%s` | %s |"
                         % (i, f["category"], f["rule_desc"], f["file"], f["line"], ev, f["action"]))
        lines.append("")
    lines += ["> 本报告为**工程侧静态扫描**，不是安全认证：正则存在漏报（语义型后门、"
              "混淆载荷可能漏检）与误报（示例文本可能命中）。"
              "硬问题须修复或拒收，需确认项须逐条判定。", ""]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="去毒审计：技能源码安全扫描")
    ap.add_argument("targets", nargs="*", help="技能目录（可多个）")
    ap.add_argument("--batch", default="", help="清单文件：每行一个目录，# 注释")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--quiet", action="store_true", help="只输出结论行")
    ap.add_argument("--out", default="", help="报告落盘路径（markdown）")
    args = ap.parse_args()

    targets = list(args.targets)
    if args.batch:
        bp = Path(args.batch)
        if not bp.is_file():
            print("[error] 清单文件不存在：%s" % args.batch)
            sys.exit(2)
        for line in bp.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s and not s.startswith("#"):
                targets.append(s)
    if not targets:
        print("[error] 未指定扫描目标")
        sys.exit(2)

    all_res, blocked = {}, False
    for t in targets:
        p = Path(t)
        if not p.is_dir():
            print("[skip] 非目录：%s" % t)
            continue
        f = scan(p)
        all_res[p.as_posix()] = {"verdict": verdict(f), "findings": f}
        if verdict(f) == "REJECT":
            blocked = True

    if args.json:
        print(json.dumps(all_res, ensure_ascii=False, indent=2))
    else:
        chunks = []
        for t, r in all_res.items():
            if not args.quiet:
                chunks.append(report_md(t, r["findings"]))
            print("[%s] %s（硬 %d / 待确认 %d）"
                  % (r["verdict"], Path(t).name,
                     sum(1 for x in r["findings"] if x["severity"] == "hard"),
                     sum(1 for x in r["findings"] if x["severity"] == "review")))
        if chunks:
            body = "\n".join(chunks)
            if args.out:
                Path(args.out).write_text(body, encoding="utf-8")
                print("\n报告已写入：%s" % args.out)
            else:
                print("\n" + body)

    sys.exit(1 if blocked else 0)


if __name__ == "__main__":
    main()
