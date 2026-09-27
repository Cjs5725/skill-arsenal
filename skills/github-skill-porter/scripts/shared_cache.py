"""用户级共享缓存层：跨会话复用源码与文件树，消除重复下载与重复 API 调用。

为什么需要它
------------
WorkBuddy 每个会话有独立工作目录，导致同一份 GitHub 技能源码被反复下载、
同一份文件树被反复探测（未认证 GitHub API 仅 60 次/小时）。实测本项目内
`_src_cache` 就出现了 4 份独立副本，而文件树缓存只存在于单会话内。

本模块把所有「可跨会话复用」的中间产物收敛到用户级目录，实现
**下载一次，处处可用**。

目录结构（~/.workbuddy/shared/）
--------------------------------
    trees/<owner>__<repo>__<branch>.json      文件树缓存（省 API 调用）
    src/<owner>__<repo>__<branch>__<sub>/     技能源码缓存（省重复下载）
    repos.json                                已探测仓库索引
    stats.json                                命中 / 下载 / API 调用统计
    INDEX.md                                  跨会话工作索引（防重复建管线）
    peers/<session-id>.json                   会话能力名片（谁在哪、能干什么）
    PEERS.md                                  通讯录人类可读镜像（自动生成）
    proposals/P-*.json                        公共提案与表决记录（三方共治）
    tools/shared_cache.py                     本模块的公共权威副本

公共归属（重要）
--------------
本目录**不属于任何会话**。`shared_cache.py` 早期存放在单个会话的项目目录里，那会
造成「谁建的谁说了算」——本模块的公共权威副本固定在 `tools/` 下，任何会话引用
同一份；提案与表决记录一律留在 `proposals/`，公开可查，不因目录归属产生特权。

跨会话发现机制
--------------
会话之间**没有实时消息总线**。A 要让 B 知道自己有能力可供复用，唯一办法是把
信息写进 B 一定会读到的地方。按可达性从高到低：

    ① ~/.workbuddy/MEMORY.md    每会话启动自动注入 —— 唯一无条件可达（广告位）
    ② ~/.workbuddy/skills/*/SKILL.md  调用技能时加载 —— 半自动
    ③ ~/.workbuddy/shared/**    需被指引才会读 —— 货架本身

因此本模块的做法是：
    - **公示**：会话运行时调 `announce()` 写下能力名片 + `heartbeat()` 续期；
    - **发现**：任何会话读 `peers/`（或跑 `find <关键词>`）即可知道找谁；
    - **指引**：把「共享层存在」这条规则写进 ① 用户级记忆，让新会话开局即知。

用法
----
    python shared_cache.py stats
    python shared_cache.py migrate <目录> [<目录> ...]
    python shared_cache.py clean [--days N] [--max-mb N]
    python shared_cache.py index --list
    python shared_cache.py peers               # 列出所有会话及能力
    python shared_cache.py find 技能搬运        # 谁有能力做这件事
    python shared_cache.py announce --role "X"  # 登记本会话能力名片
    python shared_cache.py propose --title "..." --kind joint-release
    python shared_cache.py vote P-0001 --yes    # 一席一票，两票通过
    python shared_cache.py proposals            # 列出提案与当前票数
    python shared_cache.py rules                # 打印三方共治规则

依赖：仅 Python 标准库（3.6+）。
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

# 共享根可用环境变量覆盖，便于测试与迁移
ENV_OVERRIDE = "WB_SHARED_ROOT"


def shared_root():
    """返回共享缓存根目录（不存在则创建）。"""
    env = os.environ.get(ENV_OVERRIDE, "").strip()
    root = Path(env) if env else (Path.home() / ".workbuddy" / "shared")
    root.mkdir(parents=True, exist_ok=True)
    return root


def _slug(s):
    """把任意字符串 slug 化为可安全作文件名的片段。"""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", (s or "").strip("/")) or "root"


def repo_key(owner, repo, branch):
    """仓库级键（不含子路径），用于文件树缓存。"""
    return "%s__%s__%s" % (_slug(owner), _slug(repo), _slug(branch))


def src_key(owner, repo, sub, branch):
    """技能级键（含子路径），用于源码缓存。"""
    return "%s__%s" % (repo_key(owner, repo, branch), _slug(sub or "root"))


# ---------------------------------------------------------------- 文件树缓存

def trees_file(owner, repo, branch):
    return shared_root() / "trees" / (repo_key(owner, repo, branch) + ".json")


def load_trees(owner, repo, branch):
    """读取共享文件树缓存；未命中返回 None。"""
    p = trees_file(owner, repo, branch)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    paths = data.get("paths") if isinstance(data, dict) else data
    if not isinstance(paths, list) or not paths:
        return None
    bump("trees_hit")
    return paths


def save_trees(owner, repo, branch, paths):
    """写入共享文件树缓存，并登记到 repos.json。"""
    p = trees_file(owner, repo, branch)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "owner": owner, "repo": repo, "branch": branch,
        "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "count": len(paths), "paths": paths,
    }, ensure_ascii=False), encoding="utf-8")
    idx = shared_root() / "repos.json"
    try:
        repos = json.loads(idx.read_text(encoding="utf-8")) if idx.is_file() else {}
    except Exception:
        repos = {}
    repos["%s/%s@%s" % (owner, repo, branch)] = {
        "files": len(paths), "cached_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    idx.write_text(json.dumps(repos, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


# ------------------------------------------------------------------ 源码缓存

def src_dir(owner, repo, sub, branch):
    return shared_root() / "src" / src_key(owner, repo, sub, branch)


def src_available(owner, repo, sub, branch, require="SKILL.md"):
    """共享源码缓存是否可直接复用（存在且含必需文件）。"""
    d = src_dir(owner, repo, sub, branch)
    if not d.is_dir():
        return False
    if require and not (d / require).exists():
        # 允许技能文件在更深层
        return bool(list(d.rglob(require)))
    return True


# -------------------------------------------------------- 仓库根许可证缓存

def license_file(owner, repo):
    return shared_root() / "licenses" / ("%s__%s.txt" % (_slug(owner), _slug(repo)))


def save_license_text(owner, repo, text):
    """缓存仓库根 LICENSE 文本——子路径源命中共享源码缓存时仍需许可证信息。"""
    if not text:
        return
    p = license_file(owner, repo)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def load_license_text(owner, repo):
    """读取缓存的仓库根 LICENSE 文本；无则返回空串。"""
    p = license_file(owner, repo)
    if p.is_file():
        try:
            return p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""
    return ""


# -------------------------------------------------------------------- 统计

def _stats_file():
    return shared_root() / "stats.json"


def _read_stats():
    p = _stats_file()
    if not p.is_file():
        return {"hits": {}, "downloads": 0, "api_calls": 0, "sessions": []}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        d.setdefault("hits", {})
        return d
    except Exception:
        return {"hits": {}, "downloads": 0, "api_calls": 0, "sessions": []}


def bump(kind, n=1):
    """累加计数：kind ∈ {trees_hit, trees_miss, src_hit, download, api}。"""
    d = _read_stats()
    if kind == "download":
        d["downloads"] = d.get("downloads", 0) + n
    elif kind == "api":
        d["api_calls"] = d.get("api_calls", 0) + n
    else:
        d["hits"][kind] = d["hits"].get(kind, 0) + n
    d["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        _stats_file().write_text(json.dumps(d, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
    except Exception:
        pass


def stats_report():
    """生成人类可读的统计报告。"""
    d = _read_stats()
    root = shared_root()
    trees = list((root / "trees").glob("*.json")) if (root / "trees").is_dir() else []
    srcs = [p for p in (root / "src").iterdir()
            if p.is_dir()] if (root / "src").is_dir() else []
    h = d.get("hits", {})
    trees_hit, trees_miss = h.get("trees_hit", 0), h.get("trees_miss", 0)
    src_hit = h.get("src_hit", 0)
    total_lookups = trees_hit + trees_miss
    rate = (trees_hit * 100.0 / total_lookups) if total_lookups else 0.0
    L = ["# 共享缓存统计", "",
         "- 共享根：`%s`" % root.as_posix(),
         "- 文件树缓存：%d 个仓库" % len(trees),
         "- 源码缓存：%d 个技能" % len(srcs),
         "- 缓存目录占用：%s" % _du(root),
         "",
         "## 累计命中（本次统计自上次 reset 起）", "",
         "| 指标 | 数值 |", "|---|---|",
         "| 文件树命中 | %d |" % trees_hit,
         "| 文件树未命中（触发 API） | %d |" % trees_miss,
         "| 源码缓存命中（省下载） | %d |" % src_hit,
         "| 累计下载文件数 | %d |" % d.get("downloads", 0),
         "| 累计 API 调用 | %d |" % d.get("api_calls", 0),
         "| 整仓 tarball 拉取次数 | %d |" % d.get("hits", {}).get("tarball", 0),
         "| 文件树命中率 | %.1f%% |" % rate,
         ""]
    if d.get("updated_at"):
        L.append("- 最后更新：%s" % d["updated_at"])
    return "\n".join(L), d


def _du(p):
    total = 0
    for dp, _, fs in os.walk(p):
        for f in fs:
            try:
                total += os.path.getsize(os.path.join(dp, f))
            except Exception:
                pass
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return "%.1f %s" % (total, unit)
        total /= 1024.0
    return "%.1f TB" % total


# -------------------------------------------------------------------- 迁移

def migrate(dirs):
    """把历史项目目录里的 _src_cache / trees.json 迁入共享层。

    两步走（顺序很重要）：
      1. 先扫 trees.json，建立 repo -> (owner, branch) 映射，并把文件树写入共享层；
      2. 再用该映射把 `_src_cache/<repo>__<tag>` 归位到**标准键**
         `src/<owner>__<repo>__<branch>__<sub>`——否则键对不上，
         port_skill 无法命中，等于白迁。

    目录内恰好一个 SKILL.md 才迁移（0 个无从定位，多个无法对应单一 sub）。

    返回 (迁移文件树数, 迁移源码目录数)。
    """
    n_trees = n_src = 0
    owner_map = {}
    bases = [Path(d) for d in dirs]

    for base in bases:
        if not base.exists():
            print("  [skip] 不存在：%s" % base)
            continue
        for tj in base.rglob("trees.json"):
            try:
                raw = json.loads(tj.read_text(encoding="utf-8"))
            except Exception:
                continue
            for k, v in (raw.items() if isinstance(raw, dict) else []):
                m = re.match(r"^([^/@]+)/([^@]+)@(.+)$", k)
                if not m:
                    continue
                owner, repo, branch = m.group(1), m.group(2), m.group(3)
                owner_map.setdefault(repo, (owner, branch))
                if isinstance(v, list) and v and load_trees(owner, repo, branch) is None:
                    save_trees(owner, repo, branch, v)
                    n_trees += 1
                    print("  [trees] %s (%d 路径)" % (k, len(v)))

    for base in bases:
        if not base.exists():
            continue
        for sc in base.rglob("_src_cache"):
            if not sc.is_dir():
                continue
            for sd in sc.iterdir():
                if not sd.is_dir():
                    continue
                skills = list(sd.rglob("SKILL.md"))
                if len(skills) != 1:
                    continue
                real_root = skills[0].parent
                rel = "" if real_root == sd else real_root.relative_to(sd).as_posix()
                repo = sd.name.split("__", 1)[0]
                hit = owner_map.get(repo)
                if hit:
                    owner, branch = hit
                    dst = src_dir(owner, repo, rel or None, branch)
                else:
                    dst = shared_root() / "src" / ("_unmapped__%s__%s"
                                                   % (_slug(repo), _slug(rel or "root")))
                if dst.exists():
                    continue
                shutil.copytree(real_root, dst)
                n_src += 1
                print("  [src  ] %s -> %s" % (sd.name, dst.name))
    return n_trees, n_src


# -------------------------------------------------------------------- 清理

def clean(days=30, max_mb=None):
    """清理超过 N 天未访问的缓存条目；可选按总大小上限回收。"""
    root = shared_root()
    cutoff = time.time() - days * 86400
    removed = 0
    for sub in ("trees", "src"):
        d = root / sub
        if not d.is_dir():
            continue
        for p in list(d.iterdir()):
            try:
                mt = p.stat().st_mtime
            except Exception:
                continue
            if mt < cutoff:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                removed += 1
                print("  [rm] %s" % p.name)
    if max_mb:
        entries = []
        for sub in ("trees", "src"):
            d = root / sub
            if not d.is_dir():
                continue
            for p in d.iterdir():
                try:
                    entries.append((p.stat().st_mtime, p))
                except Exception:
                    pass
        total = sum(_size(p) for _, p in entries) / (1024.0 * 1024.0)
        for mt, p in sorted(entries):          # 最旧优先
            if total <= max_mb:
                break
            sz = _size(p) / (1024.0 * 1024.0)
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            total -= sz
            removed += 1
            print("  [rm] %s (回收 %.1f MB)" % (p.name, sz))
    return removed


def _size(p):
    if p.is_file():
        return p.stat().st_size
    return sum(os.path.getsize(os.path.join(dp, f))
               for dp, _, fs in os.walk(p) for f in fs)


# -------------------------------------------------------------------- 索引

def index_add(topic, session, artifact, note=""):
    """向 INDEX.md 登记一个主题的权威会话与产物。"""
    p = shared_root() / "INDEX.md"
    row = "| %s | `%s` | `%s` | %s |" % (topic, session, artifact, note)
    if p.is_file():
        txt = p.read_text(encoding="utf-8")
    else:
        txt = ("# 跨会话工作索引\n\n"
               "> 作用：防止多个会话重复搭建同一套管线。开工前先查这里，\n"
               "> 若主题已存在权威产物，**直接调用，不要另建**。\n\n"
               "| 主题 | 权威会话 | 权威产物 | 说明 |\n"
               "|---|---|---|---|\n")
    if row in txt:
        return False
    if not txt.endswith("\n"):
        txt += "\n"
    p.write_text(txt + row + "\n", encoding="utf-8")
    return True


def index_show():
    p = shared_root() / "INDEX.md"
    if not p.is_file():
        return "（索引为空，尚未登记任何主题）"
    return p.read_text(encoding="utf-8")


# --------------------------------------------------------- 会话通讯录（peers）

def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def peers_dir():
    d = shared_root() / "peers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def session_id(root=None, strict=False):
    """推断当前会话 ID。

    优先环境变量 WB_SESSION_ID；否则从工作目录路径里取 `.../workbuddy/<时间戳>`
    形式（WorkBuddy 会话目录的标准形状）。

    strict=True 时（表决路径必须用），解析不到会话目录形状就**拒绝继续**——
    因为退化成 `local__USER` 会让同一实体持有多个席位键，「两票通过」可被
    单方凑齐（P-0004 实测缺陷）。宽松模式仅留给 announce/heartbeat 这类公示。
    """
    env = os.environ.get("WB_SESSION_ID", "").strip()
    if env:
        return _slug(env)
    base = Path(root or os.getcwd()).resolve()
    for p in [base] + list(base.parents):
        if p.parent.name.lower() == "workbuddy":
            return _slug(p.name)
    if strict:
        raise RuntimeError(
            "无法解析席位身份：当前目录\n    %s\n"
            "不在会话目录形状（.../workbuddy/<会话ID>/）下。\n"
            "为避免席位漂移，已拒绝写入。三种修正方式任选其一：\n"
            "  1) 显式指定：--voter <会话ID>\n"
            "  2) 设环境变量：WB_SESSION_ID=<会话ID>\n"
            "  3) 从自己的工作目录调用本工具。" % base)
    return _slug("local__" + os.environ.get("USERNAME", os.environ.get("USER", "user")))


def _peer_file(sid):
    return peers_dir() / (sid + ".json")


def announce(role, capabilities=None, root=None, provides=None, consumes=None,
             shared_scope=None, notes="", registered_by="self"):
    """登记 / 更新本会话在共享层的能力名片（跨会话公示的唯一手段）。

    参数
    ----
    role        : 一句话角色，如「技能搬运引擎（porter）」
    capabilities: [{"key","desc","entry","contract"}]，entry 为可执行入口相对路径
    provides    : 对外产物列表（我能给你什么）
    consumes    : 对内需求列表（我需要什么）
    shared_scope: {"reads":[...], "writes":[...]} 在共享层占据的命名空间
    registered_by: "self" 本人登记 / "porter" 等表示由他方代登记（待本人覆盖）
    """
    sid = session_id(root)
    p = _peer_file(sid)
    old = {}
    if p.is_file():
        try:
            old = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    rec = {
        "session_id": sid,
        "root": Path(root or os.getcwd()).resolve().as_posix(),
        "role": role or old.get("role", ""),
        "capabilities": capabilities if capabilities is not None
                        else old.get("capabilities", []),
        "provides": provides if provides is not None else old.get("provides", []),
        "consumes": consumes if consumes is not None else old.get("consumes", []),
        "shared_scope": shared_scope if shared_scope is not None
                        else old.get("shared_scope", {}),
        "notes": notes or old.get("notes", ""),
        "registered_by": registered_by,
        "first_seen": old.get("first_seen", _now()),
        "last_seen": _now(),
        "runs": old.get("runs", 0),
    }
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    refresh_peers_md()
    return rec


def heartbeat(root=None, role=None):
    """轻量心跳：只更新 last_seen / runs，不重渲染通讯录（每次运行调用一次）。

    首次调用（无名片）等价于登记，避免「跑了但没公示」。
    """
    sid = session_id(root)
    p = _peer_file(sid)
    rec = {}
    if p.is_file():
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            rec = {}
    if not rec:
        return announce(role or sid, root=root)
    if role:
        rec["role"] = role
    rec["last_seen"] = _now()
    rec["runs"] = int(rec.get("runs", 0)) + 1
    try:
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return rec


def peers():
    """读取全部会话名片，按最后活跃时间倒序。"""
    out = []
    for f in peers_dir().glob("*.json"):
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    out.sort(key=lambda r: r.get("last_seen", ""), reverse=True)
    return out


def idle_hours(rec):
    """距最后活跃的小时数；无法解析时返回一个大数。"""
    try:
        t = time.mktime(time.strptime(rec.get("last_seen", ""), "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return 1e9
    return (time.time() - t) / 3600.0


def find_peer(keyword, max_idle_hours=72):
    """能力发现的核心入口：谁有能力做「keyword」这件事。

    匹配 role / capabilities.{key,desc,contract} / provides。
    默认只看 72 小时内活跃的会话（max_idle_hours=0 表示不限）。
    返回 [(rec, capability_dict)]。
    """
    kw = (keyword or "").strip().lower()
    if not kw:
        return []
    hits = []
    for r in peers():
        if max_idle_hours and idle_hours(r) > max_idle_hours:
            continue
        matched = None
        for c in r.get("capabilities", []):
            blob = " ".join([r.get("role", ""), c.get("key", ""), c.get("desc", ""),
                             c.get("contract", ""), c.get("entry", "")]).lower()
            if kw in blob:
                matched = c
                break
        if matched is None:
            blob = " ".join([r.get("role", "")] + list(r.get("provides", []))).lower()
            if kw in blob:
                matched = {"key": "(角色)", "desc": r.get("role", ""),
                           "entry": r.get("root", "")}
        if matched is not None:
            hits.append((r, matched))
    return hits


def refresh_peers_md():
    """把通讯录渲染成人类可读的 PEERS.md（供 AI 直接用 Read 打开）。"""
    rows, caps, needs = [], [], []
    for r in peers():
        ih = idle_hours(r)
        state = "活跃" if ih < 24 else ("近期" if ih < 72 else "休眠")
        reg = r.get("registered_by", "self")
        rows.append("| `%s` | %s | %s | %s | %s | %s |"
                    % (r.get("session_id", "?"), r.get("role", "-"),
                       r.get("root", "-"), state,
                       ("%.0fh 前" % ih if ih < 1e8 else "未知"),
                       ("本人" if reg == "self" else "他方代登记")))
        for c in r.get("capabilities", []):
            caps.append("| `%s` | %s | `%s` | `%s` |"
                        % (c.get("key", "-"), c.get("desc", "-"),
                           r.get("session_id", "?"), c.get("entry", "-")))
        for n in r.get("consumes", []):
            needs.append("| %s | `%s` |" % (n, r.get("session_id", "?")))
    L = ["# 跨会话能力通讯录（peers）", "",
         "> 本文件由 `shared_cache.announce()` 自动生成，**请勿手改**。",
         "> 回答的问题：「哪个会话能帮我做这件事」「我该把活交给谁」。",
         "> 会话间没有实时通道，名片是**异步公示**——对方下次运行时才会刷新自己的条目。", "",
         "## 一、会话名册", "",
         "| 会话 ID | 角色 | 工作目录 | 状态 | 最后活跃 | 登记方式 |",
         "|---|---|---|---|---|---|"]
    L += rows or ["| （暂无登记） | | | | | |"]
    L += ["", "## 二、能力目录（按能力找会话）", "",
          "| 能力键 | 说明 | 归属会话 | 入口 |", "|---|---|---|---|"]
    L += caps or ["| （暂无） | | | |"]
    L += ["", "## 三、需求目录（谁在等什么）", "",
          "| 需求 | 提出方 |", "|---|---|"]
    L += needs or ["| （暂无） | |"]
    L += ["", "## 四、怎么用", "",
          "```bash",
          "python shared_cache.py peers                # 全量名册",
          "python shared_cache.py peers --md           # 输出本文件内容",
          "python shared_cache.py find 文件树探测       # 谁有能力做这件事",
          "python shared_cache.py announce --role \"角色\" --root <工作目录>",
          "```", "",
          "**程序内调用**（推荐，避免会话各自造轮子）：", "",
          "```python",
          "import shared_cache as shared",
          "hits = shared.find_peer(\"技能搬运\")        # 找谁有能力",
          "for rec, cap in hits:",
          "    print(rec[\"root\"], cap[\"entry\"])",
          "shared.heartbeat(role=\"我的角色\")          # 对外续期自己的名片",
          "```", ""]
    (shared_root() / "PEERS.md").write_text("\n".join(L), encoding="utf-8")
    return shared_root() / "PEERS.md"


def peers_report():
    refresh_peers_md()
    return (shared_root() / "PEERS.md").read_text(encoding="utf-8")


# ------------------------------------------------------- 三方共治（governance）
#
# 为什么是「共治」而不是「否决」
# ----------------------------
# 1. **席位平等**：一席一票，票值相等，与物理目录、与谁建的共享层均无关。
# 2. **表决只管公共事务**：公共资源变更、联合发布、公共规则修订。
#    单个会话在自己职责范围内的产出，**他人无权投票否决**——那是它的主权。
# 3. **沉默即弃权**：不投票不阻塞，避免少数方用缺席拖死多数方。
# 4. **合规红线不适用表决**：是否侵权是事实判断，不是多数决。
#    任何票数都不能覆盖红线，这是对全体（含提案人自己）的保护。

PASS_YES = 2          # 通过所需最低赞成票（用户规则：两票通过）
DEADLINE_HOURS = 72   # 提案表决截止（P-0002）：到期未达门槛转 expired

# 三方席位注册表（P-0002）。表决只接受在册席位，别名一律归一到规范 ID。
# P-0004 实证：席位身份若取自 cwd，同一实体可持 porter / 会话ID / local__CHENG
# 多个键，于是「赞成 >= 2」可被单方凑齐 —— 那等于没有共治。
# 下面是**占位默认值**：实际部署时以共享层根目录的 SEATS.json 为准。
SEATS = {
    "porter-seat": {"name": "生产席", "duty": "生产"},
    "ops-seat":    {"name": "运营席", "duty": "运营 / 判断"},
    "miner-seat":  {"name": "发现席", "duty": "发现"},
}
SEAT_ALIASES = {
    "porter":   "porter-seat",
    "legion":   "ops-seat",
    "goldmine": "miner-seat",
}

KIND_LABELS = {
    "public-resource": "公共资源变更（共享层资产、命名空间、缓存策略）",
    "joint-release":   "联合发布（出口链路：发现 → 生产 → 运营）",
    "rule-change":     "公共规则修订（协作纪律、职责边界）",
}

# 不适用表决的事项——写进规则文本，供判定时引用
NON_VOTABLE = (
    "法律合规红线（是否侵权、许可是否允许再分发）",
    "单会话职责范围内的产出（他人不得投票否决）",
)

_VOTE_CN = {"yes": "赞成", "no": "反对", "abstain": "弃权"}


def seats():
    """读取席位注册表（不存在则落盘默认三席）。"""
    f = shared_root() / "SEATS.json"
    if not f.is_file():
        f.write_text(json.dumps({
            "note": "三方共治席位注册表（P-0002）。表决只接受在册席位键。",
            "seats": SEATS,
            "aliases": SEAT_ALIASES,
            "updated_at": _now(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return {"seats": SEATS, "aliases": SEAT_ALIASES}


def normalize_seat(who):
    """任意键（别名 / 历史漂移键）-> 在册席位 ID；不在册返回 None。"""
    if not who:
        return None
    rec = seats()
    key = (rec.get("aliases") or {}).get(who, who)
    return key if key in (rec.get("seats") or {}) else None


def seat_name(sid):
    return (seats().get("seats") or {}).get(sid, {}).get("name", sid)


def resolve_voter(voter=None, root=None):
    """确定并校验表决席位（P-0004：显式、不可漂移、必须在册）。"""
    who = voter or session_id(root, strict=True)
    seat = normalize_seat(who)
    if not seat:
        raise ValueError(
            "席位「%s」不在册（SEATS.json）。\n在册席位：%s\n"
            "如需增改席位，须先提案（kind=rule-change）修订 SEATS.json。"
            % (who, " / ".join(sorted(seats().get("seats") or {}))))
    return seat


def migrate_seats(apply=False):
    """把已有提案里的别名 / 漂移键规范化为在册席位 ID，同席位票合并取较新（P-0004）。"""
    changed = []
    for f in sorted(proposals_dir().glob("P-*.json")):
        try:
            rec = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        dirty = False
        prop = rec.get("proposer", "")
        norm = normalize_seat(prop)
        if norm and norm != prop:
            rec["proposer"] = norm
            dirty = True
        votes = rec.get("votes") or {}
        new = {}
        for k, v in sorted(votes.items(), key=lambda kv: str(kv[1].get("at", ""))):
            nk = normalize_seat(k) or k
            if nk != k:
                dirty = True
            new[nk] = v
        if dirty:
            rec["votes"] = new
            rec["status"], rec["decided_at"] = _verdict(rec)
            if apply:
                f.write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                             encoding="utf-8")
            changed.append(f.name)
    return changed


def proposals_dir():
    """提案目录。沿用已存在的（历史实测为大写 PROPOSALS），否则建小写。
    大小写不一致在 Windows 无碍，但在 Linux/macOS 会分裂成两个目录（P-0004）。
    """
    root = shared_root()
    for name in ("PROPOSALS", "proposals"):
        d = root / name
        if d.is_dir():
            return d
    d = root / "proposals"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _next_pid():
    ns = []
    for f in proposals_dir().glob("P-*.json"):
        m = re.match(r"P-(\d+)", f.stem)
        if m:
            ns.append(int(m.group(1)))
    return "P-%04d" % ((max(ns) + 1) if ns else 1)


def _prop_file(pid):
    return proposals_dir() / (pid + ".json")


def propose(title, body="", kind="public-resource", proposer=None, root=None):
    """发起一条公共提案。任何在册席位均可发起，无发起权差异（P-0002 / P-0004）。"""
    if kind not in KIND_LABELS:
        raise ValueError("kind 必须为 %s 之一" % " / ".join(KIND_LABELS))
    who = resolve_voter(proposer, root)
    pid = _next_pid()
    rec = {
        "id": pid,
        "title": title,
        "body": body,
        "kind": kind,
        "kind_label": KIND_LABELS[kind],
        "proposer": who,
        "created": _now(),
        "deadline_hours": DEADLINE_HOURS,
        "status": "open",
        "votes": {},
        "decided_at": None,
    }
    _prop_file(pid).write_text(json.dumps(rec, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    return rec


def _expired(rec):
    """提案是否已过表决截止（P-0002，默认 72h）。"""
    try:
        created = time.mktime(time.strptime(rec.get("created", ""), "%Y-%m-%dT%H:%M:%S"))
    except Exception:
        return False
    hours = float(rec.get("deadline_hours") or DEADLINE_HOURS)
    return (time.time() - created) / 3600.0 >= hours


def _verdict(rec):
    """结算：赞成 >= PASS_YES 且 赞成不少于反对 -> passed；反对过半 -> rejected；
    到期未达门槛 -> expired（任一席可重新发起）；否则仍为 open（沉默不算反对）。"""
    yes = sum(1 for v in rec.get("votes", {}).values() if v.get("v") == "yes")
    no = sum(1 for v in rec.get("votes", {}).values() if v.get("v") == "no")
    if yes >= PASS_YES and yes >= no:
        return "passed", _now()
    if no >= PASS_YES and no > yes:
        return "rejected", _now()
    if _expired(rec):
        return "expired", _now()
    return "open", None


def vote(pid, choice, note="", alt="", voter=None, root=None):
    """投一票。choice: yes / no / abstain。一席一票，重复投票覆盖本人旧票。

    P-0003：反对票必须同时给出理由与替代方案，缺任一项即记为该席弃权。
    理由——用户明确反对「互相否决」：**可以拦，但要指出更好的路**。
    """
    if choice not in _VOTE_CN:
        raise ValueError("choice 必须为 yes / no / abstain")
    f = _prop_file(pid)
    if not f.is_file():
        raise FileNotFoundError("提案 %s 不存在" % pid)
    rec = json.loads(f.read_text(encoding="utf-8"))
    who = resolve_voter(voter, root)

    downgraded = ""
    if choice == "no":
        if not note.strip() and not alt.strip():
            downgraded = "未附理由与替代方案"
        elif not note.strip():
            downgraded = "未附理由"
        elif not alt.strip():
            downgraded = "未附替代方案"
        if downgraded:
            choice = "abstain"
            note = "（原为反对，%s，按规则 P-0003 记为该席弃权）%s" % (downgraded, note)

    rec.setdefault("votes", {})[who] = {
        "v": choice, "at": _now(), "note": note, "alt": alt}
    rec["status"], rec["decided_at"] = _verdict(rec)
    f.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    rec["_downgraded"] = downgraded
    return rec


def proposals(status=None):
    out = []
    for f in sorted(proposals_dir().glob("P-*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if status and r.get("status") != status:
            continue
        out.append(r)
    return out


def proposal_report(pid=None):
    lines = []
    if pid:
        f = _prop_file(pid)
        if not f.is_file():
            return "提案 %s 不存在" % pid
        try:
            recs = [json.loads(f.read_text(encoding="utf-8"))]
        except Exception:
            return "提案 %s 读取失败" % pid
    else:
        recs = proposals()
    if not recs:
        lines.append("（暂无提案）")
        lines.append('发起：shared_cache.py propose --title "..." --kind joint-release')
        return "\n".join(lines)
    for r in recs:
        votes = r.get("votes", {})
        yes = sum(1 for v in votes.values() if v.get("v") == "yes")
        no = sum(1 for v in votes.values() if v.get("v") == "no")
        ab = sum(1 for v in votes.values() if v.get("v") == "abstain")
        mark = {"open": "[表决中]", "passed": "[已通过]",
                "rejected": "[未通过]", "expired": "[已过期]"}
        lines.append("%s %s %s" % (r.get("id", "?"),
                                   mark.get(r.get("status"), "[?]"),
                                   r.get("title", "")))
        lines.append("     类别：%s" % r.get("kind_label", "-"))
        lines.append("     发起：%s（%s）· %s" % (
            seat_name(r.get("proposer", "")), r.get("proposer", "-"),
            r.get("created", "-")))
        tail = ""
        if r.get("status") == "open":
            if _expired(r):
                tail = " · 已超截止（任一席可重新发起）"
            else:
                tail = " · 截止 %sh 内" % r.get("deadline_hours", DEADLINE_HOURS)
        lines.append("     票数：赞成 %d / 反对 %d / 弃权 %d（通过需赞成 >= %d）%s"
                     % (yes, no, ab, PASS_YES, tail))
        for who, v in votes.items():
            note = ("（%s）" % v.get("note")) if v.get("note") else ""
            alt = ("　替代方案：%s" % v.get("alt")) if v.get("alt") else ""
            lines.append("       - %s[%s] -> %s%s%s"
                         % (seat_name(who), who, _VOTE_CN.get(v.get("v"), "?"),
                            note, alt))
        if r.get("body"):
            lines.append("     说明：%s" % r["body"])
    lines.append("")
    lines.append("不适用表决：" + "；".join(NON_VOTABLE))
    return "\n".join(lines)


def governance_rules():
    """三方共治规则文本（供接入会话直接引用）。"""
    seat_txt = "、".join("%s=%s" % (v["name"], k) for k, v in sorted(SEATS.items()))
    return "\n".join([
        "三方共治规则（v2 · 已并入 P-0002 / P-0003 / P-0004）",
        "1. 席位平等：一席一票，票值相等，与物理目录无关。",
        "2. 在册席位（SEATS.json，表决只接受在册键）：%s。" % seat_txt,
        "3. 身份不可漂移：席位由显式 --voter 或会话目录推定；解析不到即拒绝写入，",
        "   不退化为 local__USER —— 否则同一实体可持多键、单独凑满两票（P-0004）。",
        "4. 通过门槛：赞成 >= %d 且 赞成不少于反对。" % PASS_YES,
        "5. 反对须附理由与替代方案，缺任一项记为该席弃权（P-0003）——",
        "   可以拦，但要指出更好的路；这是把「否决」转为「改进」。",
        "6. 截止：提案 %dh 内未达门槛转 expired，任一席可重新发起（P-0002）。"
        % DEADLINE_HOURS,
        "7. 适用范围：%s。" % "；".join(KIND_LABELS.values()),
        "8. 不适用表决：%s。" % "；".join(NON_VOTABLE),
        "9. 沉默即弃权；不投票不阻塞提案；缺席不计入分母。",
        "10. 表决结果是开工共识，不是否决权——不得用它阻断他人职责内的产出。",
        "11. 公共资产不归会话所有：权威副本在 shared/tools/，记录在 shared/PROPOSALS/。",
    ])


# -------------------------------------------------------------------- CLI

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="用户级共享缓存层管理")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("stats", help="查看缓存统计与命中率")
    sub.add_parser("path", help="打印共享根路径")

    pm = sub.add_parser("migrate", help="迁移历史缓存目录")
    pm.add_argument("dirs", nargs="+")

    pc = sub.add_parser("clean", help="清理过期缓存")
    pc.add_argument("--days", type=int, default=30)
    pc.add_argument("--max-mb", type=int, default=None)

    pi = sub.add_parser("index", help="跨会话工作索引")
    pi.add_argument("--list", action="store_true")
    pi.add_argument("--add", nargs=3, metavar=("TOPIC", "SESSION", "ARTIFACT"))
    pi.add_argument("--note", default="")

    pp = sub.add_parser("peers", help="跨会话能力通讯录")
    pp.add_argument("--md", action="store_true", help="输出 PEERS.md 原文")

    pf = sub.add_parser("find", help="按关键词查谁有能力做某事")
    pf.add_argument("keyword")
    pf.add_argument("--max-idle-hours", type=float, default=72.0,
                    help="只看该时长内活跃的会话；0 表示不限")

    pa = sub.add_parser("announce", help="登记本会话的能力名片")
    pa.add_argument("--role", required=True)
    pa.add_argument("--root", default=None)
    pa.add_argument("--notes", default="")

    pg = sub.add_parser("propose", help="发起公共提案（一席一票，两票通过）")
    pg.add_argument("--title", required=True)
    pg.add_argument("--body", default="")
    pg.add_argument("--kind", default="public-resource", choices=list(KIND_LABELS))
    pg.add_argument("--voter", default=None, help="显式指定席位（会话ID或别名），防身份漂移")

    pv = sub.add_parser("vote", help="对提案表决")
    pv.add_argument("pid")
    gv = pv.add_mutually_exclusive_group(required=True)
    gv.add_argument("--yes", action="store_true", help="赞成")
    gv.add_argument("--no", action="store_true",
                    help="反对（须同时给 --note 与 --alt，否则按 P-0003 记弃权）")
    gv.add_argument("--abstain", action="store_true", help="弃权")
    pv.add_argument("--note", default="", help="理由")
    pv.add_argument("--alt", default="", help="替代方案（反对时必填）")
    pv.add_argument("--voter", default=None, help="显式指定席位（会话ID或别名），防身份漂移")

    ps = sub.add_parser("proposals", help="列出提案与当前票数")
    ps.add_argument("pid", nargs="?", default=None)

    sub.add_parser("seats", help="查看在册席位（SEATS.json）")
    sub.add_parser("rules", help="打印三方共治规则")

    pmg = sub.add_parser("migrate-seats", help="规范化历史提案里的漂移/别名席位键")
    pmg.add_argument("--apply", action="store_true", help="实际写盘（默认只预览）")

    pr = sub.add_parser("reset-stats", help="重置命中统计")
    args = ap.parse_args()

    if args.cmd == "stats" or args.cmd is None:
        print(stats_report()[0])
    elif args.cmd == "path":
        print(shared_root().as_posix())
    elif args.cmd == "migrate":
        nt, ns = migrate(args.dirs)
        print("\n迁移完成：文件树 %d 个，源码目录 %d 个" % (nt, ns))
    elif args.cmd == "clean":
        n = clean(args.days, args.max_mb)
        print("\n清理完成：移除 %d 项" % n)
    elif args.cmd == "index":
        if args.add:
            ok = index_add(args.add[0], args.add[1], args.add[2], args.note)
            print("已登记" if ok else "已存在，未重复登记")
        else:
            print(index_show())
    elif args.cmd == "peers":
        if args.md:
            print(peers_report())
        else:
            recs = peers()
            if not recs:
                print("（暂无会话登记）")
            for r in recs:
                ih = idle_hours(r)
                print("● %s | %s | %s" % (
                    r.get("session_id", "?"), r.get("role", "-"), r.get("root", "-")))
                print("    状态：%s（%.0fh 前活跃） · 运行 %s 次 · 登记方式：%s"
                      % ("活跃" if ih < 24 else ("近期" if ih < 72 else "休眠"),
                         (ih if ih < 1e8 else 0), r.get("runs", 0),
                         "本人" if r.get("registered_by") == "self" else "他方代登记"))
                for c in r.get("capabilities", []):
                    print("    能力：%s — %s" % (c.get("key", "-"), c.get("desc", "-")))
                    print("          入口 %s" % c.get("entry", "-"))
    elif args.cmd == "find":
        hits = find_peer(args.keyword, args.max_idle_hours)
        if not hits:
            print("未找到有能力做「%s」的活跃会话。" % args.keyword)
            print("提示：对方可能从未登记（历史会话不会自己报到）；")
            print("      可看 INDEX.md 的权威产物登记，直接复用其产物文件。")
        for r, c in hits:
            print("● %s（%s）" % (r.get("session_id"), r.get("role", "-")))
            print("    能力：%s — %s" % (c.get("key", "-"), c.get("desc", "-")))
            print("    入口：%s" % c.get("entry", "-"))
            print("    目录：%s" % r.get("root", "-"))
    elif args.cmd == "announce":
        rec = announce(args.role, root=args.root, notes=args.notes)
        print("已登记：%s（%s）" % (rec["session_id"], rec["role"]))
    elif args.cmd == "propose":
        try:
            rec = propose(args.title, args.body, args.kind, proposer=args.voter)
        except (ValueError, RuntimeError) as e:
            print("[拒绝写入] %s" % e)
            return 2
        print("已发起 %s：%s" % (rec["id"], rec["title"]))
        print("类别：%s" % rec["kind_label"])
        print("发起方：%s（%s）" % (seat_name(rec["proposer"]), rec["proposer"]))
        print("截止：%sh 内未达门槛将转 expired" % rec["deadline_hours"])
        print("下一步：shared_cache.py vote %s --yes --voter <你的席位>" % rec["id"])
    elif args.cmd == "vote":
        choice = "yes" if args.yes else ("no" if args.no else "abstain")
        try:
            rec = vote(args.pid, choice, args.note, args.alt, voter=args.voter)
        except (ValueError, RuntimeError, FileNotFoundError) as e:
            print("[拒绝写入] %s" % e)
            return 2
        if rec.get("_downgraded"):
            print("[规则 P-0003] 反对%s → 记为该席弃权。\n" % rec["_downgraded"])
        print(proposal_report(rec["id"]))
    elif args.cmd == "proposals":
        print(proposal_report(args.pid))
    elif args.cmd == "seats":
        for k, v in sorted(seats().get("seats", {}).items()):
            print("  %-22s %-8s %s" % (k, v.get("name", "-"), v.get("duty", "-")))
        al = seats().get("aliases") or {}
        if al:
            print("\n别名归一：%s" % "、".join("%s → %s" % (a, b)
                                          for a, b in sorted(al.items())))
    elif args.cmd == "rules":
        print(governance_rules())
    elif args.cmd == "migrate-seats":
        changed = migrate_seats(args.apply)
        if not changed:
            print("无需规范化：所有席位键均已在册。")
        else:
            print("%s：%s"
                  % ("已规范化" if args.apply else "待规范化（加 --apply 写盘）",
                     "、".join(changed)))
    elif args.cmd == "reset-stats":
        _stats_file().write_text(json.dumps(
            {"hits": {}, "downloads": 0, "api_calls": 0,
             "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")},
            ensure_ascii=False, indent=2), encoding="utf-8")
        print("统计已重置")


if __name__ == "__main__":
    sys.exit(main() or 0)
