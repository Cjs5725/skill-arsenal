#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_skills.py —— N:1 合并引擎（同能力多配置 → 单一技能）

本工具解决的是**产能问题**：采集端一次投喂可能带来成百上千个技能源，
逐个独立上架既无意义也不可行。合并的正确含义是「把同一能力的多个变体
收成一个」，而不是「把不同能力堆在一个目录里」。

--------------------------------------------------------------------------
范围声明（第一版只做 M1，刻意不做别的）
--------------------------------------------------------------------------
合并按判据分三类，本工具只实现第一类：

    M1 同能力多配置  正文高度重叠，差异仅为参数/配置
                     → 合并为一份，差异抽成「变体配置」表        ← 本工具
    M2 同能力多实现  能力描述相同但实现路径不同
                     → 应择优选一或做适配层，**不是本工具能自动定的**
    同产品不同能力   能力互不重叠（如 commerce 家族）
                     → 应保持各自独立，**合并即堆叠**

**没有相似度闸的合并就是堆叠。** 故本工具的第一道工序不是合并，是**拒绝**：
低于阈值的组合会被判为「不同能力」，直接拒绝并提示保持独立。

--------------------------------------------------------------------------
三条可选性判据（对应 COMBINATION_LAB 的铁律 1「没有判定方法的组合只叫混合」）
--------------------------------------------------------------------------
    目标性质  合并后**共同部分零丢失**且**各变体差异可指认**
    判定方法  ① 两两相似度 ≥ 阈值；② 每个成员正文逐行覆盖率 = 100%；
              ③ 交付前自检门禁 PASS；④ 去毒审计无硬问题
    试错带宽  单组合一次合并 + 一次验收，秒级；可批量试全库

注意：合并是**去重**，不是**造新性质**——故不属 COMBINATION_LAB 的
「新组合」登记范围（该台账铁律 3 管的正是「不得称为新组合」这件事）。

--------------------------------------------------------------------------
产出
--------------------------------------------------------------------------
    <输出根>/<name>/SKILL.md              合并稿（基线正文 + 变体配置表）
    <输出根>/<name>/LICENSE               源许可全文（随包，合规硬要求）
    <输出根>/<name>/THIRD-PARTY-NOTICES.md 归属声明（含全部成员来源）
    <输出根>/<name>/merge-report.md       合并报告：相似度矩阵、差异块、零丢失验收
    <输出根>/<name>.zip                   root 直铺上传包

用法
----
    python merge_skills.py <源1> <源2> [...] --name <合并slug> --out <输出根>
    python merge_skills.py --group groups.json --out <输出根>     # 多组合批处理
    python merge_skills.py <源...> --name X --out Y --dry-run      # 只判定不落盘
    python merge_skills.py <源...> --name X --out Y --no-zip
"""

import argparse
import difflib
import json
import re
import sys
import time
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import port_skill as ps  # noqa: E402
try:
    import scan_toxicity as toxmod  # noqa: E402  去毒审计（同目录；缺失时降级为不扫描）
except Exception:
    toxmod = None

DEFAULT_MIN_SIMILARITY = 0.80
SEP = "=" * 76


# --------------------------------------------------------------- 读取与相似度

def read_source(d):
    """读入一个成员源，返回 dict。只取 SKILL.md（最稳定的共同载体）。"""
    d = Path(d)
    skill = d / "SKILL.md"
    if not skill.is_file():
        raise FileNotFoundError("源目录内无 SKILL.md：%s" % d)
    text = skill.read_text(encoding="utf-8", errors="replace")
    fm, body = ps.parse_frontmatter(text)
    return {
        "path": d,
        "dir_name": d.name,
        "fm": fm,
        "body": body,
        "lines": body.splitlines(),
        "license": (fm.get("license") or "").strip(),
    }


def similarity(a_lines, b_lines):
    """正文相似度：difflib 序列相似度（对行序列，顺序敏感）。"""
    if not a_lines and not b_lines:
        return 1.0
    return difflib.SequenceMatcher(None, a_lines, b_lines).ratio()


def similarity_matrix(members):
    """返回 (最小相似度, 最小对, 全矩阵行文本)。"""
    rows, worst, worst_pair = [], 1.0, None
    n = len(members)
    for i in range(n):
        cells = []
        for j in range(n):
            r = similarity(members[i]["lines"], members[j]["lines"])
            cells.append("%.3f" % r)
            if i < j and r < worst:
                worst, worst_pair = r, (members[i]["dir_name"], members[j]["dir_name"])
        rows.append((members[i]["dir_name"], cells))
    return worst, worst_pair, rows


# --------------------------------------------------------------- 差异抽取

def extract_variants(baseline, others):
    """把各成员相对基线的差异抽成结构化的变体记录（保真，不丢行）。

    对每个非基线成员跑行级 diff，产出：
      replace: [(基线行列表, 该变体行列表)]   —— 同一位置取值不同
      insert : [行列表]                        —— 该变体独有的新增
      delete : [行列表]                        —— 基线有而该变体没有
    三类记录合起来覆盖了两侧的全部差异行，这是零丢失验收成立的前提。
    """
    out = []
    for m in others:
        rec = {"name": m["dir_name"], "replace": [], "insert": [], "delete": []}
        sm = difflib.SequenceMatcher(None, baseline["lines"], m["lines"])
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "replace":
                rec["replace"].append((baseline["lines"][i1:i2], m["lines"][j1:j2]))
            elif tag == "insert":
                rec["insert"].append(m["lines"][j1:j2])
            elif tag == "delete":
                rec["delete"].append(baseline["lines"][i1:i2])
        out.append(rec)
    return out


def common_lines(baseline, variants):
    """基线的共同部分：在任一成员的差异中被改动过的行剔除后剩余的行。

    实现方式：把变体记录里出现过的基线侧行（replace 左值 + delete 值）收集起来，
    按出现次数从基线中扣除——同一文本多次出现时只扣实际被改动的次数，
    避免"重复行被一次性全删"这种误伤。
    """
    touched = {}
    for v in variants:
        for left, _ in v["replace"]:
            for l in left:
                touched[l] = touched.get(l, 0) + 1
        for blk in v["delete"]:
            for l in blk:
                touched[l] = touched.get(l, 0) + 1
    quota = dict(touched)
    kept = []
    for l in baseline["lines"]:
        if quota.get(l, 0) > 0:
            quota[l] -= 1
            continue
        kept.append(l)
    return kept


# --------------------------------------------------------------- 合并稿合成

def build_merged_body(name, common, baseline, variants, sources_desc, display=""):
    """合成合并稿正文：基线共同部分 + 变体配置表（差异全部落纸，不丢）。

    注意两处易错点，都已在实现中处理：
    ① 基线的标题行若属于被替换行，会从共同部分中剔除，故这里**补一个中性标题**，
       否则合并稿正文会以半句话开头；
    ② 变体表中「基线取值」一列**不等于**「共同部分取值」——被替换的行已不在共同
       正文里，属基线变体独有取值。标错会让读者以为正文里有两种写法。
    """
    title = display or name
    lines = ["# %s" % title, "", "（本技能为 %d 个同能力变体的合并版）" % (len(variants) + 1), ""]
    lines += list(common)
    if lines and lines[-1].strip():
        lines.append("")
    lines += [
        "",
        "## 变体配置",
        "",
        "本技能由 **%d 个同能力变体**合并而来（原为 %d 个独立技能）。" % (len(variants) + 1, len(variants) + 1),
        "上方正文为**各变体共同部分**；下方表格列出每个变体与共同部分的差异。",
        "**使用前请先确认本环境属于哪个变体，并按该变体一列取值。**",
        "",
        "| 变体 | 来源 | 差异项 |",
        "| --- | --- | --- |",
    ]
    for v in variants:
        n_diff = len(v["replace"]) + len(v["insert"]) + len(v["delete"])
        lines.append("| `%s` | `%s` | %d 处 |" % (v["name"], sources_desc[v["name"]], n_diff))
    lines += [
        "",
        "基线变体为 `%s`。下表「基线取值」一列是**该基线变体**的取值——被替换的行已不在上方共同正文中，"
        "上面正文写的是两侧都一致的部分。" % baseline["dir_name"],
        "",
    ]

    for v in variants:
        lines += ["### 变体：`%s`" % v["name"], ""]
        if not (v["replace"] or v["insert"] or v["delete"]):
            lines += ["- 与共同部分**完全一致**（零差异）。", ""]
            continue
        if v["replace"]:
            lines += ["**取值替换**", "",
                      "| # | 基线（`%s`）取值 | `%s` 取值 |" % (baseline["dir_name"], v["name"]),
                      "| --- | --- | --- |"]
            for k, (left, right) in enumerate(v["replace"], 1):
                lv = " / ".join(x.strip() for x in left) if len(left) > 1 else left[0].strip()
                rv = " / ".join(x.strip() for x in right) if len(right) > 1 else right[0].strip()
                lines.append("| %d | %s | %s |" % (k, _cell(lv), _cell(rv)))
            lines.append("")
        if v["insert"]:
            lines += ["**该变体独有的新增行**", ""]
            for blk in v["insert"]:
                for l in blk:
                    lines.append("- %s" % _cell(l.strip() or "（空行）"))
            lines.append("")
        if v["delete"]:
            lines += ["**该变体不含的行**（基线有、本变体没有；这些行已从上方共同正文中剔除）", ""]
            for blk in v["delete"]:
                for l in blk:
                    lines.append("- %s" % _cell(l.strip() or "（空行）"))
            lines.append("")
    lines += [
        "---",
        "",
        "> 由 `merge_skills.py` 机械合并：共同部分逐行保留，差异逐项落表，",
        "> 合并前后各成员正文**零丢失**（见 `merge-report.md` 的验收表）。",
        "> 本文件只做结构合并，不做改写与润色。",
        "",
    ]
    return "\n".join(lines)


def _cell(s):
    """表格单元格安全化：转义竖线；反引号不成对时替换掉，避免破坏代码跨段。"""
    s = s.replace("|", "\\|")
    if s.count("`") % 2:
        s = s.replace("`", "'")
    return s


def _inline(s, limit=90):
    """报告里的内联片段：截断并中性化反引号（内容自身常含反引号，再包一层会渲染坏）。"""
    s = s.strip()
    if len(s) > limit:
        s = s[:limit].rstrip() + "…"
    return s.replace("`", "'").replace("|", "\\|")


# --------------------------------------------------------------- 零丢失验收

def verify_no_loss(members, merged_text):
    """零丢失验收：每个成员正文的每一非空行都必须出现在合并产物中。

    这是合并的硬验收项——只要有一个成员的行丢失，合并即判失败。
    返回 (是否全部通过, 每成员的明细)。
    """
    rows, ok = [], True
    for m in members:
        total = 0
        missing = []
        for l in m["lines"]:
            s = l.strip()
            if not s:
                continue
            total += 1
            if s not in merged_text:
                missing.append(s)
        passed = not missing
        ok = ok and passed
        rows.append({"name": m["dir_name"], "checked": total,
                     "missing": missing, "passed": passed})
    return ok, rows


# --------------------------------------------------------------- 单组合处理

def merge_group(sources, name, out_root, min_similarity=DEFAULT_MIN_SIMILARITY,
                no_zip=False, dry_run=False, allow_mixed_license=False,
                ensure_sections=False):
    """处理一个合并组合。返回结果 dict（供批量报告汇总）。"""
    out_root = Path(out_root)
    members = [read_source(s) for s in sources]
    if len(members) < 2:
        raise ValueError("合并至少需要 2 个源，当前只有 %d 个" % len(members))

    # ---- 闸 1：相似度准入（这是防堆叠的核心）
    worst, worst_pair, matrix_rows = similarity_matrix(members)
    if worst < min_similarity:
        return {
            "name": name, "ok": False, "gate": "相似度不足",
            "reason": ("最低相似度 %.3f < 阈值 %.3f（%s ↔ %s）——判为**不同能力**，"
                       "不得合并。此类应保持各自独立；是否以「技能集/合集」形式组织，"
                       "取决于平台侧是否存在该承载形式，**本工具不假设它存在**。"
                       % (worst, min_similarity, worst_pair[0], worst_pair[1])),
            "worst": worst, "matrix": matrix_rows,
        }

    # ---- 闸 2：许可一致性（混合许可的合并会污染归属声明，需显式放行）
    lics = {m["license"] for m in members if m["license"]}
    if len(lics) > 1 and not allow_mixed_license:
        return {
            "name": name, "ok": False, "gate": "许可混合",
            "reason": "成员许可不一致：%s。合并会污染归属声明，需 --allow-mixed-license 显式放行。"
                      % "、".join(sorted(lics)),
            "worst": worst, "matrix": matrix_rows,
        }

    baseline, others = members[0], members[1:]
    variants = extract_variants(baseline, others)
    common = common_lines(baseline, variants)
    sources_desc = {m["dir_name"]: _src_label(m) for m in members}

    body = build_merged_body(name, common, baseline, variants, sources_desc,
                             display=ps.title_case(name))
    # 平台结构段落：合并稿同样是上架交付物，须满足平台校验器的结构要求。
    # 实测：英文源技能必然缺「边界与降级／质量自检」（平台正则只认中文词），
    # 不补则合并稿会被判 FAIL。
    added_sections = []
    if ensure_sections:
        body, added_sections = ps.fill_structural_sections(body)
    merged_text = body

    # ---- 闸 3：零丢失验收
    ok_loss, loss_rows = verify_no_loss(members, merged_text)
    if not ok_loss:
        return {
            "name": name, "ok": False, "gate": "零丢失验收失败",
            "reason": "合并后存在行丢失：%s" % "; ".join(
                "%s 缺 %d 行" % (r["name"], len(r["missing"])) for r in loss_rows if not r["passed"]),
            "worst": worst, "matrix": matrix_rows, "loss": loss_rows,
        }

    diff_blocks = sum(len(v["replace"]) + len(v["insert"]) + len(v["delete"]) for v in variants)
    if dry_run:
        return {"name": name, "ok": True, "gate": "通过（dry-run，未落盘）",
                "worst": worst, "matrix": matrix_rows, "loss": loss_rows,
                "variants": len(variants), "diff_blocks": diff_blocks,
                "common_lines": len(common), "dry_run": True}

    # ---- 组装 frontmatter（只组装、不落盘；过完下面所有闸才写盘）
    # 合并稿必须有**中性身份**，不得继承单一变体的身份。
    # 反面示例（本工具初版踩过）：display_name 仍是 "Plus Astra Orchestrator"、
    # description_en 仍写 "the Plus profile" —— 拿到合并稿的人会以为它只支持 Plus。
    platform_dir = out_root / name
    fm = dict(baseline["fm"])
    # 1) 先清掉继承来的变体限定身份，再显式给中性名称
    #    （不能留给 build_frontmatter 派生：它按正则从描述里抓中文名，会抓到
    #     「不适用于…」这类中文片段，实测产出过 display_name: "不适用于"）
    fm.pop("display_name", None)
    fm.pop("display_name_en", None)
    neutral = ps.title_case(name)
    fm["display_name"] = neutral
    fm["display_name_en"] = neutral
    # 2) 清掉继承描述里已固化的「搬运来源」（build_frontmatter 会统一追加一次；
    #    且继承的那一行指向单一变体，留着会误导）。用正则而非整行匹配——实测该
    #    片段常与正文挤在同一行，整行匹配删不掉。
    base_desc = (baseline["fm"].get("description") or "").strip()
    base_desc = re.sub(r"搬运来源：[^\n]*", "", base_desc)
    base_desc = re.sub(r"\n{3,}", "\n\n", base_desc).strip()
    member_names = "、".join(m["dir_name"] for m in members)
    base_zh = (baseline["fm"].get("description_zh") or "").strip()
    base_en = (baseline["fm"].get("description_en") or "").strip()
    fm["description"] = (
        "This is a MERGED skill covering %d variants of the same capability (%s). "
        % (len(members), member_names)
        + base_desc
        + "\n本技能由 %d 个同能力变体合并而成（%s）；上方正文为共同部分，"
          "各变体的模型与配置差异见「变体配置」章节。" % (len(members), member_names))
    fm["description_zh"] = (
        "合并自 %d 个同能力变体（%s）；正文为共同部分，变体差异见「变体配置」章节。"
        "基线变体简介：%s" % (len(members), member_names, base_zh or "（源未提供）"))
    fm["description_en"] = (
        "Merged from %d variants of the same capability (%s); the body above is the common "
        "part and per-variant differences are listed in the 「变体配置」 section. "
        "Baseline variant description: %s" % (len(members), member_names, base_en or "(not provided)"))
    fm["author"] = _merged_source_label(members)
    args = argparse.Namespace(display_name="")
    head, dropped, lic_value, lic_auto = ps.build_frontmatter(
        fm, name, args, _merged_source_label(members), lic_value_of(members))
    full_text = head + body.lstrip("\n")

    # ---- 闸 4：frontmatter 必须真能被 YAML 解析（写盘前拦，避免产出半成品）
    ok_yaml, yaml_problems = verify_frontmatter_yaml(full_text, name)
    if not ok_yaml:
        return {"name": name, "ok": False, "gate": "frontmatter 校验失败",
                "reason": "；".join(yaml_problems), "worst": worst,
                "matrix": matrix_rows, "loss": loss_rows}

    platform_dir.mkdir(parents=True, exist_ok=True)
    (platform_dir / "SKILL.md").write_text(full_text, encoding="utf-8")

    # 许可随包（合并稿沿承成员的许可；文本取自各成员的 LICENSE）
    lic_text, lic_origin = "", "未获取"
    for m in members:
        for c in ps.LICENSE_CANDS:
            p = m["path"] / c
            if p.is_file():
                lic_text = p.read_text(encoding="utf-8", errors="ignore")
                lic_origin = "%s 的 %s" % (m["dir_name"], c)
                break
        if lic_text:
            break
    lic_spdx = lic_value or (sorted(lics)[0] if lics else "")
    ps.write_license_bundle(platform_dir, lic_spdx, lic_text,
                            _merged_source_label(members), "本地（合并）",
                            " + ".join(m["dir_name"] for m in members), lic_origin)

    # 去毒审计 + 自检门禁
    tox_findings, tox_verdict = [], "SKIPPED"
    if toxmod is not None:
        tox_findings = toxmod.scan(platform_dir)
        tox_verdict = toxmod.verdict(tox_findings)
    tox = {"verdict": tox_verdict,
           "hard": sum(1 for f in tox_findings if f["severity"] == "hard"),
           "review": sum(1 for f in tox_findings if f["severity"] != "hard")}
    issues, warnings = ps.self_check(platform_dir, name, {})
    # 平台侧复核：合并稿是上架交付物，自检不能替代平台门禁
    plat_verdict, plat_detail = ps.run_platform_validation(platform_dir)

    zip_path, zip_made = out_root / ("%s.zip" % name), False
    blocked = bool(issues) or tox["hard"] > 0 or plat_verdict == "不通过"
    if not no_zip and not blocked:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(platform_dir.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(platform_dir).as_posix())
        zip_made = True

    report = build_merge_report(name, members, worst, worst_pair, matrix_rows,
                               variants, common, loss_rows, lic_spdx, lic_origin,
                               issues, warnings, tox, zip_made, added_sections,
                               plat_verdict, plat_detail)
    (platform_dir / "merge-report.md").write_text(report, encoding="utf-8")

    return {"name": name, "ok": True, "gate": "通过", "worst": worst,
            "matrix": matrix_rows, "loss": loss_rows, "variants": len(variants),
            "diff_blocks": diff_blocks, "common_lines": len(common),
            "added_sections": added_sections,
            "platform_dir": platform_dir.as_posix(),
            "zip_made": zip_made, "zip_path": zip_path.as_posix() if zip_made else None,
            "issues": issues, "warnings": warnings, "license": lic_spdx,
            "tox_hard": (tox or {}).get("hard", 0), "tox_review": (tox or {}).get("review", 0),
            "dropped_tools": dropped, "report": report}


def _dq_scalar_ok(v):
    """校验一行 `key: "…"` 的取值是不是**完整的**双引号标量。

    必要性：值里若含未转义的直引号（如 `... the "X" section ...`），标量会提前闭合，
    YAML 解析必然失败。这类错误用"引号总数是否为偶数"判断不出来（内层成对时是偶数，
    实测正是这样蒙混过关的），必须按字符扫描找**真正的闭合位置**。
    """
    v = v.strip()
    if not v.startswith('"'):
        return True                      # 非双引号标量（含 block scalar）不在此检查范围
    i = 1
    while i < len(v):
        ch = v[i]
        if ch == "\\":
            i += 2
            continue
        if ch == '"':
            return v[i + 1:].strip() == ""   # 闭合后不应再有内容
        i += 1
    return False                          # 引号未闭合


def verify_frontmatter_yaml(text, name):
    """门禁：合并稿的 YAML frontmatter 必须能被真正解析出来，且必填字段齐全。

    为什么单列一道闸：`self_check()` 用的是宽松字段探测，**YAML 语法错误查不出来**
    （实测踩过——英文描述里嵌了直引号，标量提前闭合，字段看似齐全但解析必然失败）。
    这类错误如果放过，会在上传平台时才炸，代价最高。

    优先用 yaml 库做真解析；本机可能没有 yaml（实测该环境无 PyYAML），
    此时退化为逐字段的标量扫描——**不是"跳过检查"，而是换成能真正抓到该缺陷的检查**。
    """
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        return False, ["frontmatter 分隔符不完整（缺 --- 配对）"]
    fm_block = m.group(1)

    try:
        import yaml
    except ImportError:
        yaml = None

    if yaml is not None:
        try:
            data = yaml.safe_load(fm_block)
        except Exception as e:
            return False, ["YAML 解析失败：%s" % e]
        if not isinstance(data, dict):
            return False, ["frontmatter 解析结果不是映射"]
    else:
        # 兜底：顶层行逐行做标量扫描（缩进的 block scalar 内容不参与）
        data = {}
        for line in fm_block.splitlines():
            if not line.strip() or line[0].isspace():
                continue
            k, sep, v = line.partition(":")
            if not sep:
                return False, ["顶层行缺冒号，疑似 YAML 语法错误：%s" % line[:70]]
            if not _dq_scalar_ok(v):
                return False, ["字段 %s 的双引号标量提前闭合（YAML 解析必然失败）：%s"
                               % (k.strip(), v.strip()[:70])]
            data[k.strip()] = v.strip()
        data = {k: v for k, v in data.items() if v}   # block scalar 的空值留给下一段

    missing = [f for f in ("name", "version", "display_name", "display_name_en",
                           "description_zh", "description_en", "description")
               if not data.get(f)]
    if missing:
        return False, ["解析后缺字段：%s" % "、".join(missing)]
    if data.get("name") != name:
        return False, ["name 与目录名不一致：%s ≠ %s" % (data.get("name"), name)]
    if str(data.get("display_name")).strip() in ("不适用于", ""):
        return False, ["display_name 派生错误：%r（疑似从描述里误抓中文片段）"
                       % data.get("display_name")]
    return True, []


def _src_label(m):
    author = (m["fm"].get("author") or "").strip()
    return author or m["dir_name"]


def _merged_source_label(members):
    return "合并自 %d 个源：%s" % (len(members), "、".join(_src_label(m) for m in members))


def lic_value_of(members):
    for m in members:
        if m["license"]:
            return m["license"]
    return None


# --------------------------------------------------------------- 报告

def build_merge_report(name, members, worst, worst_pair, matrix_rows, variants,
                       common, loss_rows, lic_spdx, lic_origin, issues, warnings,
                       tox, zip_made, added_sections=(), plat_verdict="—", plat_detail="—"):
    L = ["# 合并报告 · %s" % name, "",
         "- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M"),
         "- 成员数：**%d**（基线 `%s`，变体 %d 个）" % (len(members), members[0]["dir_name"], len(variants)),
         "- 共同部分：**%d 行**；差异块：**%d 处**" % (len(common),
                                                    sum(len(v["replace"]) + len(v["insert"]) + len(v["delete"]) for v in variants)),
         "",
         "## 一、相似度矩阵（准入闸）", "",
         "| 成员 | " + " | ".join(m["dir_name"] for m in members) + " |",
         "| --- | " + " | ".join("---" for _ in members) + " |"]
    for nm, cells in matrix_rows:
        L.append("| `%s` | %s |" % (nm, " | ".join(cells)))
    L += ["",
          "- 最低相似度：**%.3f**（%s ↔ %s）" % (worst, worst_pair[0], worst_pair[1]),
          "- 阈值：%.2f —— **通过**（低于阈值会被拒绝，判为「不同能力」，应保持独立）" % DEFAULT_MIN_SIMILARITY,
          ""]

    L += ["## 二、零丢失验收（合并的硬验收项）", "",
          "| 成员 | 校验行数 | 丢失行数 | 结论 |", "| --- | --- | --- | --- |"]
    for r in loss_rows:
        L.append("| `%s` | %d | %d | %s |"
                 % (r["name"], r["checked"], len(r["missing"]), "**PASS**" if r["passed"] else "**FAIL**"))
    L += ["", "> 判据：成员正文每一非空行都必须出现在合并产物中。任一行丢失即判合并失败。", ""]

    L += ["## 三、差异清单（各变体与共同部分的差别）", ""]
    for v in variants:
        n = len(v["replace"]) + len(v["insert"]) + len(v["delete"])
        L.append("- `%s`：**%d 处**（替换 %d / 新增块 %d / 缺失块 %d）"
                 % (v["name"], n, len(v["replace"]), len(v["insert"]), len(v["delete"])))
        for left, right in v["replace"][:8]:
            more = "（+%d 行）" % (len(left) - 1) if len(left) > 1 else ""
            L.append("  - 替换：`%s`%s → `%s`" % (_inline(left[0]), more, _inline(right[0])))
    L.append("")

    L += ["## 四、合规与门禁", "",
          "| 项 | 结果 |", "| --- | --- |",
          "| 许可（SPDX） | `%s` |" % (lic_spdx or "未识别"),
          "| 许可文本随包 | %s |" % (lic_origin if lic_spdx else "—"),
          "| 去毒审计 | %s |" % ("未执行" if tox.get("verdict") == "SKIPPED"
                                else "%s（硬 %d / 待确认 %d）" % (tox.get("verdict"),
                                                               tox.get("hard", 0), tox.get("review", 0))),
          "| 平台结构段落 | %s |" % ("已补骨架：%s（须按源内容改写）" % "、".join(added_sections)
                                     if added_sections else "三段落齐全，无需补写"),
          "| 平台校验（官方校验器） | %s（%s） |" % (plat_verdict, plat_detail),
          "| 交付前自检 | %s |" % ("**FAIL（%d）**" % len(issues) if issues else "PASS"),
          "| 上传包 | %s |" % ("已生成" if zip_made else "未生成"),
          ""]
    if warn_ := [w for w in warnings if "许可" in w]:
        L += ["> 待人工确认："] + ["> - %s" % w for w in warn_] + [""]

    L += ["## 五、范围声明（必读）", "",
          "- 本工具只做 **M1 同能力多配置** 的合并：正文高度重叠、差异为参数/配置。",
          "- **不做 M2（同能力多实现）**：那需要判断哪个实现更好，本工具不能自动定。",
          "- **不做跨能力堆叠**：不同能力应各自独立，塞进一个 SKILL.md 即堆叠。",
          "- 合并是**去重**，不是**造新性质**——不构成 COMBINATION_LAB 意义上的「新组合」。",
          ""]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------- 批量

def build_summary(results, out_root):
    L = ["# 合并批量汇总", "",
         "- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M"),
         "- 组合数：**%d**；通过 **%d**；拒绝 **%d**"
         % (len(results), sum(1 for r in results if r["ok"]), sum(1 for r in results if not r["ok"])),
         "",
         "| # | 组合 | 最低相似度 | 结果 | 说明 |",
         "| --- | --- | --- | --- | --- |"]
    for i, r in enumerate(results, 1):
        if r["ok"]:
            note = "共同 %d 行 / 差异 %d 处；丢行 0" % (r.get("common_lines", 0),
                                                  r.get("diff_blocks", 0))
            res = "通过" + ("（dry-run）" if r.get("dry_run") else "")
        else:
            note = r.get("reason", "")
            res = "**拒绝**（%s）" % r.get("gate", "-")
        L.append("| %d | `%s` | %.3f | %s | %s |"
                 % (i, r["name"], r.get("worst", 0), res, note.replace("|", "\\|")))
    L += ["", "> 被拒绝的组合不是失败——**拒绝正是这道闸的价值**：",
          "> 相似度不足即说明成员是不同能力，应保持各自独立，而不是塞进一个技能。", ""]
    return "\n".join(L)


def scan_groups(sources, min_similarity=DEFAULT_MIN_SIMILARITY):
    """扫描一批源，按相似度自动提议「可合并组」。

    这是 N:1 合并的**发现环节**：先看不出来哪些该合并，就没法谈产能。
    用并查集按阈值聚类——相似度 ≥ 阈值即并组，因此组内两两可达（传递闭包）。

    注意复杂度是 O(n²)。实测一个采集批次可含数千个技能源（单仓 3596 个），
    直接全量两两比对不现实；应先用关键词或来源分组缩小候选集，再对组内扫描。

    返回 (groups, singletons, pairs)：groups 为 size>=2 的组（含组内相似度中位数）。
    """
    members, skipped = [], []
    for s in sources:
        try:
            members.append(read_source(s))
        except Exception as e:
            skipped.append((str(s), str(e)))
    n = len(members)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    pairs = []
    for i in range(n):
        for j in range(i + 1, n):
            r = similarity(members[i]["lines"], members[j]["lines"])
            if r >= min_similarity:
                union(i, j)
                pairs.append((r, members[i]["dir_name"], members[j]["dir_name"]))
    buckets = {}
    for i in range(n):
        buckets.setdefault(find(i), []).append(i)

    groups, singletons = [], []
    for _, idxs in sorted(buckets.items()):
        names = [members[i]["dir_name"] for i in idxs]
        if len(idxs) < 2:
            singletons.append(names[0])
            continue
        rs = [r for r, a, b in pairs if a in names and b in names]
        groups.append({"names": names, "paths": [members[i]["path"].as_posix() for i in idxs],
                       "median": (sorted(rs)[len(rs) // 2] if rs else 0.0),
                       "min": (min(rs) if rs else 0.0), "max": (max(rs) if rs else 0.0)})
    groups.sort(key=lambda g: -len(g["names"]))
    return groups, singletons, pairs, skipped


def build_scan_report(sources, min_similarity, groups, singletons, pairs, skipped):
    L = ["# 合并候选扫描报告", "",
         "- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M"),
         "- 扫描源数：**%d**｜相似度阈值：**%.2f**" % (len(sources), min_similarity),
         "- 可合并组：**%d** 组（覆盖 %d 个源）｜独立源：**%d** 个"
         % (len(groups), sum(len(g["names"]) for g in groups), len(singletons)),
         "",
         "## 一、建议合并的组（同能力多配置）", ""]
    if not groups:
        L += ["无。**这本身就是结论**：本批源里没有发现同能力多实现，",
              "强行合并会制造堆叠，正确做法是保持各自独立。", ""]
    for k, g in enumerate(groups, 1):
        L += ["### 组 %d · %d 个源　相似度 %.3f（%.3f–%.3f）"
              % (k, len(g["names"]), g["median"], g["min"], g["max"]), ""]
        for nm in g["names"]:
            L.append("- `%s`" % nm)
        L += ["", "```bash",
              "python merge_skills.py \\"]
        for p in g["paths"]:
            L.append("  \"%s\" \\" % p)
        L += ["  --name <合并slug> --out <输出根> --ensure-sections", "```", ""]

    L += ["## 二、保持独立的源", "",
          "| # | 源 |", "| --- | --- |"]
    for i, nm in enumerate(singletons, 1):
        L.append("| %d | `%s` |" % (i, nm))
    L += ["",
          "> 独立源之间**不构成合并关系**。若它们服务于同一产品/角色，可考虑组织为",
          "> 一个技能集——但**平台侧是否存在「技能集」这种承载形式尚未验证**，",
          "> 本工具不假设它存在；在那之前它们应各自独立上架。", ""]

    if pairs:
        L += ["## 三、命中阈值的源对（原始证据）", "",
              "| 相似度 | A | B |", "| --- | --- | --- |"]
        for r, a, b in sorted(pairs, reverse=True)[:40]:
            L.append("| %.3f | `%s` | `%s` |" % (r, a, b))
        L.append("")
    if skipped:
        L += ["## 四、无法读取的源（跳过）", ""]
        for s, e in skipped:
            L += ["- `%s`：%s" % (s, e)]
        L.append("")
    L += ["## 五、方法说明", "",
          "- 相似度 = 正文行序列的 difflib 比值（顺序敏感，重复行亦计入）。",
          "- 聚类 = 并查集，阈值内传递闭包，故组内两两可达。",
          "- 复杂度 O(n²)：数千源不可全量扫，须先按来源/关键词缩小候选集。",
          "- **本报告只提议，不合并**；每组的合并都需单独跑一次并过零丢失验收。",
          ""]
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description="N:1 合并引擎（同能力多配置 → 单一技能）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="范围：本工具只做 M1（同能力多配置）；M2 与跨能力堆叠会被拒绝。")
    ap.add_argument("sources", nargs="*", help="成员源目录（至少 2 个）")
    ap.add_argument("--group", help="多组合批处理：JSON 文件 [{\"name\":..., \"sources\":[...]}, ...]")
    ap.add_argument("--name", help="合并后的 slug（单组合必填）")
    ap.add_argument("--out", required=True, help="输出根目录")
    ap.add_argument("--min-similarity", type=float, default=DEFAULT_MIN_SIMILARITY,
                    help="准入闸：两两最小正文相似度（默认 %.2f），低于则拒绝合并" % DEFAULT_MIN_SIMILARITY)
    ap.add_argument("--allow-mixed-license", action="store_true",
                    help="放行成员许可不一致的组合（默认拒绝，因会污染归属声明）")
    ap.add_argument("--scan", action="store_true",
                    help="扫描模式：对给定目录下的一组源做相似度聚类，只提议可合并组、不产出")
    ap.add_argument("--dry-run", action="store_true", help="只判定不落盘")
    ap.add_argument("--ensure-sections", action="store_true",
                    help="缺失平台结构段落（执行流程/边界与降级/质量自检）时补写骨架。"
                         "不补则合并稿会被平台校验器判 FAIL（英文源技能几乎必然缺失）")
    ap.add_argument("--no-zip", action="store_true", help="不生成上传包")
    args = ap.parse_args()

    out_root = Path(args.out)
    if not args.dry_run:
        out_root.mkdir(parents=True, exist_ok=True)

    # 扫描模式：展开目录（或直接用给定目录）→ 聚类 → 出报告，不产出任何技能
    if args.scan:
        cands = []
        for s in args.sources:
            p = Path(s)
            if p.is_dir() and list(p.glob("*/SKILL.md")):
                cands.extend(sorted(str(d) for d in p.iterdir()
                                    if d.is_dir() and (d / "SKILL.md").is_file()
                                    and not d.name.endswith("-local")))
            else:
                cands.append(s)
        groups, singletons, pairs, skipped = scan_groups(cands, args.min_similarity)
        report = build_scan_report(cands, args.min_similarity, groups, singletons, pairs, skipped)
        dest = out_root / "merge-scan-report.md"
        dest.write_text(report, encoding="utf-8")
        print(report)
        print("报告：%s" % dest.as_posix())
        sys.exit(0)

    groups = []
    if args.group:
        for g in json.loads(Path(args.group).read_text(encoding="utf-8")):
            groups.append((g["name"], g["sources"]))
    else:
        if not args.sources or not args.name:
            ap.error("单组合模式需同时给出 <源...> 与 --name；或多组合模式用 --group")
        groups.append((args.name, args.sources))

    results = []
    for name, srcs in groups:
        print(SEP)
        print("[组合] %s  ←  %d 个源" % (name, len(srcs)))
        try:
            r = merge_group(srcs, name, out_root, args.min_similarity,
                            no_zip=args.no_zip, dry_run=args.dry_run,
                            allow_mixed_license=args.allow_mixed_license,
                            ensure_sections=args.ensure_sections)
        except Exception as e:
            r = {"name": name, "ok": False, "gate": "异常", "reason": str(e), "worst": 0.0}
        results.append(r)
        if r["ok"]:
            print("[ok] 相似度 %.3f ≥ %.2f → 通过；共同 %d 行 / 差异 %d 处 / 成员 %d 个；丢行 0"
                  % (r["worst"], args.min_similarity, r.get("common_lines", 0),
                     r.get("diff_blocks", 0), r.get("variants", 0) + 1))
            if not r.get("dry_run"):
                print("     产出：%s" % r["platform_dir"])
                print("     zip ：%s" % (r["zip_path"] or "未生成"))
        else:
            print("[拒绝] 闸门=%s" % r.get("gate"))
            print("       %s" % r.get("reason", ""))

    summary = build_summary(results, out_root.as_posix())
    if not args.dry_run:
        (out_root / "merge-summary.md").write_text(summary, encoding="utf-8")
    print(SEP)
    print(summary)

    # 只要有一个组合「通过」即算成功；全部被拒（说明判据正确工作）不算错误
    sys.exit(0 if all(r["ok"] or r.get("gate") in ("相似度不足", "许可混合") for r in results) else 1)


if __name__ == "__main__":
    main()
