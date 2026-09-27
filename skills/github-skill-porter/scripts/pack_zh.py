#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""中文化交付打包：把平台版技能打成**纯技能内容**的 <slug>-zh.zip。

用法：
    单目录：python pack_zh.py <平台版目录> [--out <输出目录>]
    批量：  python pack_zh.py --batch <清单文件|父目录> [--out <输出目录>]

为什么单独一个脚本：
    `port_skill.py` 的 zip 是**搬运时**产的，里面含 `porting-changes.md` 等内部文档；
    中文化是搬运**之后**在平台版目录上原地改写的，改完必须重打交付包——且交付包
    **不得含内部文档**（平台只认技能内容）。本脚本即这一步，避免每次手搓 zip 造成
    两次交付物口径不一致。

打包规则（与平台规格一致）：
    - 收：SKILL.md、LICENSE*、THIRD-PARTY-NOTICES.md、references/**、scripts/**、assets/**
    - 排：porting-changes.md 及任何清单文件（内部文档）、`-local` 目录、缓存与临时文件
    - 形态：**root 直铺**（zip 内不再套一层目录）——平台只认这一种
    - 交付包**必须**含 LICENSE 与 THIRD-PARTY-NOTICES.md（宽松许可的随包义务）

退出码：0 全部成功；1 有目录缺 SKILL.md 或缺许可随包文件。
"""

import argparse
import sys
import zipfile
from pathlib import Path

# 随包必收的根级文件（存在即收）
ROOT_KEEP = {"SKILL.md", "LICENSE", "LICENSE.txt", "LICENSE.md", "THIRD-PARTY-NOTICES.md"}
# 一律排除的内部文档与噪声
EXCLUDE_NAMES = {"porting-changes.md", "batch-report.md", "manifest.txt"}
EXCLUDE_SUFFIX = (".zip", ".pyc", ".tmp", ".log")
EXCLUDE_DIRS = {"__pycache__", ".git", "dist"}
RESOURCE_DIRS = ("references", "scripts", "assets")


def collect(platform_dir):
    """返回 (待打包相对路径列表, 缺失项列表)。"""
    files, missing = [], []
    if not (platform_dir / "SKILL.md").exists():
        return [], ["SKILL.md"]
    for name in ROOT_KEEP:
        if (platform_dir / name).is_file():
            files.append(name)
    # 宽松许可的随包义务：LICENSE 与归属声明必须随包
    if not any(f.startswith("LICENSE") for f in files):
        missing.append("LICENSE")
    if "THIRD-PARTY-NOTICES.md" not in files:
        missing.append("THIRD-PARTY-NOTICES.md")
    for d in RESOURCE_DIRS:
        base = platform_dir / d
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file() or p.suffix.lower() in EXCLUDE_SUFFIX:
                continue
            if any(part in EXCLUDE_DIRS for part in p.parts):
                continue
            if p.name in EXCLUDE_NAMES:
                continue
            files.append(p.relative_to(platform_dir).as_posix())
    return files, missing


def pack_one(platform_dir, out_dir):
    files, missing = collect(platform_dir)
    if missing:
        print("[%s] 缺随包文件，未打包：%s" % (platform_dir.name, "、".join(missing)))
        return False
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("%s-zh.zip" % platform_dir.name)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in files:
            z.write(platform_dir / rel, rel)          # root 直铺：arcname 即相对路径
    size = out.stat().st_size / 1024
    print("[%s] %d 个文件 / %.1f KB -> %s" % (platform_dir.name, len(files), size, out.as_posix()))
    for rel in files:
        print("    %s" % rel)
    return True


def load_targets(spec):
    p = Path(spec)
    if p.is_dir():
        return sorted(d for d in p.iterdir()
                      if d.is_dir() and (d / "SKILL.md").exists()
                      and not d.name.endswith("-local"))
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        out.append((p.parent / s) if not Path(s).is_absolute() else Path(s))
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="平台版技能目录（单目录模式）")
    ap.add_argument("--batch", default="", help="清单文件（每行一个目录，# 注释）或父目录")
    ap.add_argument("--out", default="", help="输出目录（默认写到各技能目录的同级 dist-zh/）")
    args = ap.parse_args()

    if args.batch:
        targets = load_targets(args.batch)
        if not targets:
            print("[error] --batch 未解析到任何含 SKILL.md 的目录")
            return 1
        out_dir = Path(args.out) if args.out else targets[0].parent / "dist-zh"
        ok = all([pack_one(t, out_dir) for t in targets]) and True
        print("\n合计：%d 项，成功 %d" % (len(targets), sum(
            1 for t in targets if (out_dir / ("%s-zh.zip" % t.name)).exists())))
        return 0 if ok else 1

    if not args.target:
        print("[error] 需要 <平台版目录> 或 --batch")
        return 1
    d = Path(args.target)
    out_dir = Path(args.out) if args.out else d.parent / "dist-zh"
    return 0 if pack_one(d, out_dir) else 1


if __name__ == "__main__":
    sys.exit(main())
