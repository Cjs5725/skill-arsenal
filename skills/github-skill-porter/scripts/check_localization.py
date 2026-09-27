#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文化门禁：检查 WorkBuddy 平台版技能的中文化完成度与技术锚点保留情况。

用法：
    单目录：
        python check_localization.py <平台版目录> [--src <源目录>] [--min-coverage 0.9] [--strict-refs]
    批量：
        python check_localization.py --batch <清单文件|父目录> [--out <报告.md>] [--json]

    --batch 的两种形态：
        - 清单文件：每行一个平台版目录路径，`#` 开头为注释；
        - 父目录：取其下**每个含 SKILL.md 的一级子目录**为一项。

检查项（纯标准库、零联网）：
    1. 中文字段：frontmatter 的 display_name / description_zh 是否含中文。
    2. 中文化覆盖率：逐行判定「疑似英文散文行」（连续英文词 >= N 的正文行，
       或含英文词的标题行），剔除代码块、行内代码、URL、hex 色值、字体名、
       文件路径等「不作为翻译对象」的 token 后统计是否已译为中文。
       SKILL.md 不达标 → 硬问题；references/ 下 .md 不达标 → 警告（--strict-refs 升为硬问题）。
       该分档正是为了拦住「正文译了、规格文件仍英文」这种最常见的假中文化。
    3. 技术锚点保留：与 --src 比对，源中出现的 hex 色值、字体名是否在产物中全部保留。
       （仅单目录模式支持：批量下无逐项源映射。）
    4. 引用完整性：正文引用的资源文件是否存在（悬空引用）；被搬迁但正文未引用的
       文件（覆盖盲区，能通过合规校验但语义断裂）。

退出码：存在硬问题（缺中文字段 / SKILL.md 覆盖率不足 / 锚点丢失 / 悬空引用）→ 1；否则 0。
        批量模式下，任一项存在硬问题即整体 1。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# —— token 级识别 ——
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\u3000-\u303f\uff00-\uffef]")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
FONT = re.compile(
    r"\b(?:DejaVu (?:Sans|Serif)(?: Bold)?|FreeSans(?: Bold)?|FreeSerif(?: Bold)?|"
    r"Arial(?: Black| Narrow)?|Helvetica(?: Neue)?|Roboto(?: Mono)?|Inter|Montserrat|"
    r"Noto Sans(?: SC| TC| JP)?|Source Han (?:Sans|Serif)|PingFang SC|Microsoft YaHei)\b")
URL = re.compile(r"https?://\S+")
INLINE = re.compile(r"`[^`]*`")
EMPH = re.compile(r"[*_>|]")
PATHISH = re.compile(r"(?<![\w/.-])[\w.-]+(?:/[\w.-]+)+\.[A-Za-z0-9]{1,8}\b")
# 裸文件名（无目录前缀）。必须单独识别：`PATHISH` 要求路径至少含一个 `/`，
# 故根目录下的同包文件（如 `THIRD-PARTY-NOTICES.md`）**永远匹配不上**，
# 会稳定误报「未被正文引用」且无从修好。负向后顾排除路径片段，避免与 PATHISH 重复。
BARE_FILE = re.compile(r"(?<![\w/.-])([\w.-]+\.[A-Za-z0-9]{1,8})(?![\w/])")
WORD = re.compile(r"[A-Za-z][A-Za-z'\-]*")
FENCE = re.compile(r"^\s*```")

RESOURCE_EXT = {".md", ".pdf", ".txt", ".py", ".json", ".csv", ".sh", ".yaml", ".yml"}


def strip_tech(s):
    """剔除不作为翻译对象的 token，只留下真正该翻译的自然语言。"""
    s = URL.sub(" ", s)
    s = INLINE.sub(" ", s)
    s = HEX.sub(" ", s)
    s = FONT.sub(" ", s)
    s = PATHISH.sub(" ", s)
    s = EMPH.sub(" ", s)
    return s


def split_frontmatter(raw):
    if raw.startswith("---"):
        parts = raw.split("---", 2)
        if len(parts) >= 3:
            return parts[1], parts[2]
    return "", raw


def analyze(text, min_words):
    """返回 (需翻译行数, 已中文化行数, 未译行列表[(行号, 内容)])。"""
    need, done, untranslated = 0, 0, []
    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if FENCE.match(s):
            in_fence = not in_fence
            continue
        if in_fence or not s or s.startswith("<!--"):
            continue
        words = WORD.findall(strip_tech(s))
        # 标题行：出现任一英文词即视为需中文化；正文行：连续英文词达阈值
        needs = (len(words) >= 1) if s.startswith("#") else (len(words) >= min_words)
        if not needs:
            continue
        need += 1
        if CJK.search(s):
            done += 1
        else:
            untranslated.append((i, s))
    return need, done, untranslated


def check_frontmatter(fm):
    issues, warnings = [], []
    for k in ("display_name", "description_zh"):
        m = re.search(r"^%s:\s*(.+)$" % k, fm, re.M)
        val = (m.group(1).strip().strip('"\'') if m else "")
        if not val:
            issues.append("frontmatter 缺少 `%s`" % k)
        elif not CJK.search(val):
            issues.append("frontmatter `%s` 未含中文：%s" % (k, val[:40]))
    m = re.search(r"^description\s*:\s*\|?\s*\n?([\s\S]+?)(?=\n\w+:|\Z)", fm, re.M)
    if m and not CJK.search(m.group(1)):
        warnings.append("frontmatter `description` 未含中文（建议改为中文触发说明）")
    return issues, warnings


def collect_anchors(root):
    """收集目录下所有文本文件中的 hex 色值与字体名。"""
    hexes, fonts = set(), set()
    for p in Path(root).rglob("*"):
        if not p.is_file() or p.suffix.lower() not in RESOURCE_EXT:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        hexes |= {h.lower() for h in HEX.findall(text)}
        fonts |= set(FONT.findall(text))
    return hexes, fonts


def check_references(platform_dir, raw):
    """悬空引用（硬问题）与未引用搬迁文件（覆盖盲区，警告）。"""
    issues, warnings = [], []
    referenced = set()
    for m in PATHISH.finditer(raw):
        token = m.group(0)
        if Path(token).suffix.lower() not in RESOURCE_EXT:
            continue
        referenced.add(Path(token).name)
        if (platform_dir / token).exists():
            continue
        if not [q for q in platform_dir.rglob(Path(token).name) if q.is_file()]:
            issues.append("悬空引用：正文引用 `%s`，产物中不存在" % token)
    # 裸文件名只用于**消除误报**（登记为「已引用」），不参与悬空引用判定——
    # 少了目录前缀的信号太弱，据此判硬问题会误伤。
    for m in BARE_FILE.finditer(raw):
        name = m.group(1)
        if Path(name).suffix.lower() in RESOURCE_EXT:
            referenced.add(name)
    for p in sorted(platform_dir.rglob("*")):
        if not p.is_file() or p.name in ("SKILL.md", "porting-changes.md"):
            continue
        if "license" in p.name.lower():   # 许可证文件无需正文引用（与 port_skill.self_check 一致）
            continue
        if p.name not in referenced:
            warnings.append("搬迁文件未被正文引用：%s（建议在正文补索引，避免语义断裂）"
                            % p.relative_to(platform_dir).as_posix())
    return issues, warnings


def evaluate(platform_dir, args):
    """对单个平台版目录跑全套检查，返回结果字典（不打印）。"""
    skill_md = platform_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    raw = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body = split_frontmatter(raw)
    sk_need, sk_done, sk_un = analyze(body, args.min_words)
    sk_cov = (sk_done / sk_need) if sk_need else 1.0
    # 体量守卫。覆盖率的**分母是当前文本**，不是源文本——因此「译完了」与
    # 「把正文删短了」在覆盖率上无法区分（删到没有英文行 → need=0 → 自动 100%）。
    # 这是「假中文化」最隐蔽的一种，故另记绝对体量并在过小时告警。
    vol_lines = sum(1 for l in body.splitlines()
                    if l.strip() and not l.strip().startswith("<!--")
                    and not l.strip().startswith("```"))
    vol_cjk = len(re.findall(r"[\u4e00-\u9fff]", body))

    ref_files = [p for p in sorted(platform_dir.rglob("*.md")) if p != skill_md]
    ref_need = ref_done = 0
    ref_un = []
    ref_bad = []
    for p in ref_files:
        t = p.read_text(encoding="utf-8", errors="replace")
        n, d, u = analyze(t, args.min_words)
        ref_need += n
        ref_done += d
        for ln, txt in u:
            ref_un.append((p.relative_to(platform_dir).as_posix(), ln, txt))
        if n and (d / n) < args.min_coverage:
            ref_bad.append("%s（%d/%d 行）" % (p.relative_to(platform_dir).as_posix(), d, n))
    ref_cov = (ref_done / ref_need) if ref_need else 1.0

    issues, warnings = check_frontmatter(fm)
    ref_issues, ref_warnings = check_references(platform_dir, raw)
    issues += ref_issues
    warnings += ref_warnings

    if sk_cov < args.min_coverage:
        issues.append("SKILL.md 中文化覆盖率不足：%.0f%% < %.0f%%" % (sk_cov * 100, args.min_coverage * 100))
    if ref_bad:
        msg = "references 下 %d 个文件中文化不足：%s" % (len(ref_bad), "；".join(ref_bad))
        (issues if args.strict_refs else warnings).append(msg)
    if vol_lines < 12:
        warnings.append("正文仅 %d 行、%d 个中文字，体量偏小——覆盖率会因分母随之变小而虚高，"
                        "无法区分「已译完」与「被压缩/截断」，请与源比对" % (vol_lines, vol_cjk))

    missing_hex, missing_font = set(), set()
    if args.src:
        s_hex, s_font = collect_anchors(args.src)
        t_hex, t_font = collect_anchors(platform_dir)
        missing_hex = {h for h in s_hex if h not in t_hex}
        missing_font = {f for f in s_font if f not in t_font}
        if missing_hex:
            issues.append("技术锚点丢失（hex 色值 %d 个）：%s"
                          % (len(missing_hex), "、".join(sorted(missing_hex))))
        if missing_font:
            issues.append("技术锚点丢失（字体名 %d 个）：%s"
                          % (len(missing_font), "、".join(sorted(missing_font))))

    return {
        "slug": platform_dir.name,
        "dir": platform_dir.as_posix(),
        "fm_issues": [i for i in issues if "frontmatter" in i],
        "fm_ok": not [i for i in issues if "frontmatter" in i],
        "sk_need": sk_need, "sk_done": sk_done, "sk_cov": sk_cov, "sk_un": sk_un,
        "vol_lines": vol_lines, "vol_cjk": vol_cjk,
        "ref_files": len(ref_files), "ref_need": ref_need, "ref_done": ref_done,
        "ref_cov": ref_cov, "ref_un": ref_un, "ref_bad": ref_bad,
        "missing_hex": sorted(missing_hex), "missing_font": sorted(missing_font),
        "ref_issues": ref_issues, "ref_warnings": ref_warnings,
        "issues": issues, "warnings": warnings,
        "verdict": "FAIL" if issues else "PASS",
    }


def render_single(r, args):
    """单目录模式输出（与历史格式保持一致）。"""
    print("中文化门禁：%s" % r["dir"])
    if args.src:
        print("锚点比对源：%s" % Path(args.src).resolve().as_posix())
    print()
    print("  [%s]  中文字段（display_name / description_zh）：%s"
          % ("FAIL" if not r["fm_ok"] else "ok", "存在缺失或未译" if not r["fm_ok"] else "均含中文"))
    print("  [%s]  SKILL.md 中文化覆盖率：%d / %d 行 = %.0f%%（下限 %.0f%%）"
          % ("ok" if r["sk_cov"] >= args.min_coverage else "FAIL",
             r["sk_done"], r["sk_need"], r["sk_cov"] * 100, args.min_coverage * 100))
    print("        正文体量：%d 行 / %d 个中文字%s"
          % (r["vol_lines"], r["vol_cjk"],
             "（偏小，覆盖率分母随之缩小，请与源比对）" if r["vol_lines"] < 12 else ""))
    print("  [%s]  references 中文化覆盖率：%d 个文件 %d / %d 行 = %.0f%%%s"
          % ("ok" if not r["ref_bad"] else ("FAIL" if args.strict_refs else "警告"),
             r["ref_files"], r["ref_done"], r["ref_need"], r["ref_cov"] * 100,
             "" if not r["ref_bad"] else "，未达标：%s" % "；".join(r["ref_bad"])))
    if args.src:
        print("  [%s]  技术锚点保留：缺失 hex %d 个 / 缺失字体名 %d 个"
              % ("ok" if not (r["missing_hex"] or r["missing_font"]) else "FAIL",
                 len(r["missing_hex"]), len(r["missing_font"])))
    print("  [%s]  引用完整性：悬空引用 %d 处 / 未引用文件 %d 个"
          % ("ok" if not r["ref_issues"] else "FAIL", len(r["ref_issues"]), len(r["ref_warnings"])))

    if r["sk_un"]:
        print()
        print("  SKILL.md 疑似未译行（共 %d 行，最多显示 12 行）：" % len(r["sk_un"]))
        for ln, txt in r["sk_un"][:12]:
            print("    第 %d 行：%s" % (ln, txt[:90]))
        if len(r["sk_un"]) > 12:
            print("    ……其余 %d 行略" % (len(r["sk_un"]) - 12))
    if r["ref_un"]:
        print()
        print("  references 疑似未译行（共 %d 行，最多显示 10 行）：" % len(r["ref_un"]))
        for fn, ln, txt in r["ref_un"][:10]:
            print("    %s 第 %d 行：%s" % (fn, ln, txt[:80]))
        if len(r["ref_un"]) > 10:
            print("    ……其余 %d 行略" % (len(r["ref_un"]) - 10))

    print()
    if r["issues"]:
        print("FAIL（%d 项硬问题，应修复后再次交付）：" % len(r["issues"]))
        for x in r["issues"]:
            print("  - %s" % x)
    if r["warnings"]:
        print("待人工确认（%d 项）：" % len(r["warnings"]))
        for x in r["warnings"]:
            print("  - %s" % x)
    if not r["issues"]:
        print("结论：PASS（中文化字段与覆盖率%s，锚点与引用%s）"
              % ("达标", "完整" if args.src else "未比对（未传 --src）"))
    else:
        print("结论：需修复")


def load_batch_targets(batch_arg):
    """--batch 支持「清单文件」或「父目录」两种形态，返回有序去重目录列表。"""
    p = Path(batch_arg)
    targets = []
    if p.is_dir():
        for d in sorted(p.iterdir()):
            if d.is_dir() and (d / "SKILL.md").exists():
                targets.append(d.resolve())
    else:
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            d = Path(s)
            if not d.is_absolute():
                d = (p.parent / d)
            targets.append(d.resolve())
    seen, out = set(), []
    for t in targets:
        if t.as_posix() not in seen:
            seen.add(t.as_posix())
            out.append(t)
    return out


def render_batch(results, min_coverage, out_path=None):
    """批量聚合：控制台表 + （可选）markdown 报告。"""
    ok = [r for r in results if r["verdict"] == "PASS"]
    bad = [r for r in results if r["verdict"] == "FAIL"]
    lines = []
    lines.append("中文化门禁（批量）：%d 项 —— 达标 %d / 需修复 %d" % (len(results), len(ok), len(bad)))
    lines.append("")
    lines.append("| # | slug | 中文字段 | SKILL.md 覆盖率 | references 覆盖率 | 悬空引用 | 正文体量 | 结论 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for i, r in enumerate(results, 1):
        lines.append("| %d | `%s` | %s | %d/%d = %.0f%% | %d/%d = %.0f%% | %d | %d 行 / %d 字%s | %s |"
                     % (i, r["slug"],
                        "ok" if r["fm_ok"] else "FAIL",
                        r["sk_done"], r["sk_need"], r["sk_cov"] * 100,
                        r["ref_done"], r["ref_need"], r["ref_cov"] * 100,
                        len(r["ref_issues"]),
                        r["vol_lines"], r["vol_cjk"],
                        "⚠" if r["vol_lines"] < 12 else "",
                        "PASS" if r["verdict"] == "PASS" else "需修复"))
    text = "\n".join(lines)
    print(text)

    # 共同缺口归纳（比逐项更可行动）
    fm_bad = [r["slug"] for r in results if not r["fm_ok"]]
    sk_bad = [r["slug"] for r in results if r["sk_cov"] < min_coverage]
    ref_bad = [r["slug"] for r in results if r["ref_bad"]]
    print()
    print("共同缺口：")
    print("  - 中文字段未达标：%d / %d 项" % (len(fm_bad), len(results)))
    print("  - SKILL.md 覆盖率未达标：%d / %d 项" % (len(sk_bad), len(results)))
    print("  - references 覆盖率未达标：%d / %d 项（软判为警告）" % (len(ref_bad), len(results)))

    if out_path:
        md = ["# 中文化门禁报告（批量）", "",
              "> 生成时间：%s" % __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"),
              "> 口径：`check_localization.py --batch`，覆盖率下限 %.0f%%；" % (min_coverage * 100) +
              "SKILL.md 不达标为**硬问题**，references 不达标为**警告**（`--strict-refs` 可升硬）。", "",
              "## 一、总览", "",
              "- 受检技能：**%d** 个" % len(results),
              "- 判定 **PASS**：**%d** 个；判定 **需修复**：**%d** 个" % (len(ok), len(bad)),
              "- 中文字段未达标：**%d** 个" % len(fm_bad),
              "- SKILL.md 覆盖率未达标：**%d** 个" % len(sk_bad),
              "- references 覆盖率未达标（警告）：**%d** 个" % len(ref_bad),
              "", "## 二、逐项结果", "", "| # | slug | 中文字段 | SKILL.md 覆盖率 | references 覆盖率 | 悬空引用 | 正文体量 | 结论 |",
              "|---|---|---|---|---|---|---|---|"]
        for i, r in enumerate(results, 1):
            md.append("| %d | `%s` | %s | %d/%d = %.0f%% | %d/%d = %.0f%% | %d | %d 行 / %d 字%s | %s |"
                      % (i, r["slug"],
                         "ok" if r["fm_ok"] else "FAIL",
                         r["sk_done"], r["sk_need"], r["sk_cov"] * 100,
                         r["ref_done"], r["ref_need"], r["ref_cov"] * 100,
                         len(r["ref_issues"]),
                         r["vol_lines"], r["vol_cjk"],
                         "⚠" if r["vol_lines"] < 12 else "",
                         "PASS" if r["verdict"] == "PASS" else "需修复"))
        md += ["", "## 三、待译工作量（按 SKILL.md 未译行计）", "",
               "| slug | SKILL.md 未译行 | references 未译行 |", "|---|---|---|"]
        for r in results:
            md.append("| `%s` | %d | %d |" % (r["slug"], len(r["sk_un"]), len(r["ref_un"])))
        md += ["", "> 语义翻译不是脚本能力——本报告只做**判定**（覆盖率 / 锚点 / 引用）。",
               "> 实际改写由 LLM 或人工按 `references/localization-zh.md` 的 SOP 执行，改后须**复跑本门禁**。",
               "> 另注：覆盖率的分母是**当前文本**，把正文删短会让分母缩小、覆盖率虚高——门禁因此无法区分",
               "> 「已译完」与「被压缩/截断」。故表中另列**正文体量**，标 ⚠ 者行数偏小，须与源比对后再判定。"]
        Path(out_path).write_text("\n".join(md) + "\n", encoding="utf-8")
        print()
        print("报告已写入：%s" % Path(out_path).resolve().as_posix())

    return 1 if bad else 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="平台版技能目录（单目录模式）")
    ap.add_argument("--src", default="", help="源技能目录（用于技术锚点比对，可选；仅单目录模式）")
    ap.add_argument("--batch", default="", help="批量：清单文件（每行一个目录，# 注释）或父目录（取含 SKILL.md 的一级子目录）")
    ap.add_argument("--out", default="", help="批量报告输出路径（markdown）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON（批量）")
    ap.add_argument("--min-words", type=int, default=3, help="正文行判定阈值（默认 3）")
    ap.add_argument("--min-coverage", type=float, default=0.9, help="中文化覆盖率下限（默认 0.9）")
    ap.add_argument("--strict-refs", action="store_true", help="references 下 .md 覆盖率不达标也判为硬问题")
    args = ap.parse_args()

    if args.batch:
        targets = load_batch_targets(args.batch)
        if not targets:
            print("[error] --batch 未解析到任何含 SKILL.md 的目录：%s" % args.batch)
            sys.exit(1)
        results, missing = [], []
        for t in targets:
            r = evaluate(t, args)
            if r is None:
                missing.append(t.as_posix())
                continue
            results.append(r)
        if missing:
            print("[warn] 以下目录无 SKILL.md，已跳过：%s" % "、".join(missing))
            print()
        code = render_batch(results, args.min_coverage, args.out or None)
        if args.json:
            print()
            print(json.dumps(results, ensure_ascii=False, indent=2))
        sys.exit(code)

    if not args.target:
        ap.error("需要提供 <平台版目录>，或使用 --batch")
    platform_dir = Path(args.target).resolve()
    if not (platform_dir / "SKILL.md").exists():
        print("[error] 未找到 %s" % (platform_dir / "SKILL.md"))
        sys.exit(1)
    r = evaluate(platform_dir, args)
    render_single(r, args)
    sys.exit(1 if r["issues"] else 0)


if __name__ == "__main__":
    main()
