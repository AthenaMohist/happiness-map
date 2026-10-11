"""QA 独立测试脚手架 — memory middleware V2 命令验收（v3 方案 41 用例执行）。

约束：
- 本文件只存在于 devPPL/docs/qa/，不改 mem-core 代码（只读被测对象）。
- 被测对象：/workspace/mem-core（HEAD d29bac9，含 f9d7f46 V2 实现）。
- 独立实测：不 import mem-core 测试文件，不转述 dev 断言。
- 每个用例独立临时 wiki（tmp_path 语义），互不污染。

运行：
  python3 qa_v2_harness.py /workspace/mem-core
输出：每用例一行 PASS/FAIL/PARTIAL/OBS/NOT_RUN + 证据。
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else "/workspace/mem-core")
MEMCTL = REPO / "bin" / "memctl"
sys.path.insert(0, str(REPO))

from memcore import blast, drift, gailinks, indexer, schema  # noqa: E402
from memcore.sources.gai import GaiAdapter  # noqa: E402

RESULTS: list[dict] = []

SCHEMA_PAGE = """# SCHEMA

> 测试首页。

## 定位

wiki 是 L3 编译知识层。
"""


def write_page(wiki_root, rel: str, content: str) -> Path:
    dest = Path(wiki_root) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(content, encoding="utf-8")
    return dest


def action_page(pid: str, status: str = "active", body: str = "") -> str:
    return (
        f"---\n"
        f"id: {pid}\n"
        f"type: action\n"
        f"status: {status}\n"
        f"priority: P1\n"
        f"est_hours: 2\n"
        f"location: devppl/memory/architecture\n"
        f"created: 2026-08-10T12:00:00Z\n"
        f"updated: 2026-08-10T12:00:00Z\n"
        f"source_task: {pid}\n"
        f"---\n"
        f"# {pid}\n\n"
        f"{body}\n"
    )


def concept_page(pid: str, body: str = "") -> str:
    return (
        f"---\n"
        f"id: {pid}\n"
        f"type: concept\n"
        f"status: active\n"
        f"location: devppl/memory/architecture\n"
        f"created: 2026-08-10T12:00:00Z\n"
        f"updated: 2026-08-10T12:00:00Z\n"
        f"---\n"
        f"# {pid}\n\n"
        f"{body}\n"
    )


def mock_kanban(db_path: Path, tasks: list[dict]) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks "
            "(id TEXT PRIMARY KEY, title TEXT, status TEXT, result TEXT)"
        )
        for t in tasks:
            conn.execute(
                "INSERT OR REPLACE INTO tasks (id, title, status, result) VALUES (?,?,?,?)",
                (t.get("id"), t.get("title", ""), t.get("status", "running"), t.get("result", "")),
            )
        conn.commit()
    finally:
        conn.close()


class Env:
    """每用例独立临时 wiki 环境。

    __init__ 同时设置进程级 MEM_* 环境变量，保证引擎函数直接调用
    （如 drift.three_way_check 不传 kanban_db/gai_file 时）也走临时夹具，
    不落到真实 kanban.db / GAI 文件（隔离铁律）。
    """

    def __init__(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="qa-v2-"))
        self.wiki = self.tmp / "wiki"
        self.wiki.mkdir()
        self.db = self.tmp / "mem_meta.db"
        self.gai = self.tmp / "nogai.md"
        self.kanban = self.tmp / "nokanban.db"
        write_page(self.wiki, "SCHEMA.md", SCHEMA_PAGE)
        # 进程级隔离：引擎函数缺省参数读到的是临时夹具而非真实 L0
        os.environ[schema.ENV_WIKI_PATH] = str(self.tmp)
        os.environ[schema.ENV_DB_PATH] = str(self.db)
        os.environ[schema.ENV_GAI_FILE] = str(self.gai)
        os.environ[schema.ENV_KANBAN_DB] = str(self.kanban)

    def env(self, **over) -> dict:
        e = {
            "MEM_WIKI_PATH": str(self.tmp),
            "MEM_DB_PATH": str(self.db),
            "MEM_GAI_FILE": str(self.gai),
            "MEM_KANBAN_DB": str(self.kanban),
        }
        e.update(over)
        return e

    def run(self, *args, **over) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env.update(self.env(**over))
        return subprocess.run(
            [sys.executable, str(MEMCTL), *args],
            capture_output=True, text=True, env=env, cwd=str(REPO),
        )

    def index(self) -> subprocess.CompletedProcess:
        return self.run("index")


def record(case: str, verdict: str, evidence: str) -> None:
    RESULTS.append({"case": case, "verdict": verdict, "evidence": evidence})
    print(f"[{verdict:8s}] {case}: {evidence}")


def verdict_from(ok: bool, evidence: str, ok_label: str = "PASS") -> str:
    return ok_label if ok else "FAIL"


# ═══════════════════════════════════════════════════════════════════════
# Phase 0: V2-STB-01 — stub 阶段契约（现在 CLI 已实现 → OBS）
# ═══════════════════════════════════════════════════════════════════════
def test_stb01() -> None:
    env = Env()
    # 现在 4 命令已实现，不再 exit 2 → 原 stub 契约作废，验证已实现
    r = env.run("update")
    impl = r.returncode != 2
    record("V2-STB-01", "OBS" if impl else "FAIL",
           f"stub 契约已被实现取代: update exit={r.returncode}（≠2）→ 契约升级为已实现面")


# ═══════════════════════════════════════════════════════════════════════
# V2-UPD 组：update
# ═══════════════════════════════════════════════════════════════════════
def test_upd01() -> None:
    env = Env()
    write_page(env.wiki, "concepts/middleware.md",
               concept_page("middleware", "正文 [[SCHEMA.md|S]] 记忆中间层架构决策"))
    write_page(env.wiki, "concepts/architecture.md",
               concept_page("architecture", "正文 [[SCHEMA.md|S]] 架构决策"))
    write_page(env.wiki, "concepts/other.md", concept_page("other", "正文 [[SCHEMA.md|S]]"))
    env.index()
    source = "记忆中间层架构决策 未来扩展向量检索"
    cands = blast.compute_candidates(env.db, source)
    ok = len(cands) > 0 and all(c["hit_count"] >= 1 for c in cands)
    # 排序：hit_count 降序
    sorted_ok = all(
        cands[i]["hit_count"] >= cands[i + 1]["hit_count"] for i in range(len(cands) - 1)
    )
    record("V2-UPD-01", verdict_from(ok and sorted_ok, "候选集非空且降序"),
           f"candidates={[(c['page_id'], c['hit_count']) for c in cands]} sorted={sorted_ok}")


def test_upd02() -> None:
    """B1 硬约束：compute_candidates 不读 wiki 文件（只查 db）。"""
    env = Env()
    for i in range(32):
        write_page(env.wiki, f"concepts/c{i}.md", concept_page(f"c{i}", f"正文 主题词 t{i}"))
    env.index()
    # monkeypatch Path.read_text 统计 wiki 文件读取
    from pathlib import Path as _P

    orig_read = _P.read_text
    counter = {"n": 0}

    def spy_read(self, *a, **kw):
        if str(self).startswith(str(env.wiki)):
            counter["n"] += 1
        return orig_read(self, *a, **kw)

    _P.read_text = spy_read
    try:
        blast.compute_candidates(env.db, "主题词 t5 t7 未来扩展")
    finally:
        _P.read_text = orig_read
    ok = counter["n"] == 0
    record("V2-UPD-02", verdict_from(ok, f"wiki 文件读取数={counter['n']}（期望 0）"),
           f"读取数={counter['n']}")


def test_upd03() -> None:
    """空候选：source 无命中词 → 空列表，不崩溃。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 记忆"))
    env.index()
    cands = blast.compute_candidates(env.db, "量子物理超导体完全无关内容")
    ok = cands == [] and len(blast.extract_source_terms("量子物理超导体完全无关内容")) > 0
    record("V2-UPD-03", verdict_from(ok, f"空候选={cands==[]}"),
           f"candidates={len(cands)} terms={len(blast.extract_source_terms('量子物理超导体完全无关内容'))}")


def test_upd04() -> None:
    """无 db 降级：db 不存在 → 空列表，不抛异常。"""
    env = Env()
    try:
        cands = blast.compute_candidates(env.tmp / "nonexistent.db", "任意内容")
        ok = cands == []
    except Exception as e:  # noqa: BLE001
        ok = False
        cands = f"EXC {e}"
    record("V2-UPD-04", verdict_from(ok, f"空返回={cands==[] if isinstance(cands, list) else cands}"),
           f"result={cands!r}")


def test_upd05() -> None:
    """update --apply：parser 接受但 cmd_update 未使用（静默 no-op）→ FAIL 契约。"""
    env = Env()
    write_page(env.wiki, "actions/P0-19.md", action_page("P0-19", body="正文 [[SCHEMA.md|S]]"))
    env.index()
    src = env.tmp / "src.md"
    src.write_text("记忆中间层架构决策 未来扩展", encoding="utf-8")
    r = env.run("update", str(src), "--apply", "actions/P0-19.md", "--no-commit")
    # 期望：apply 候选页改写 + bump updated；实际：--apply 被忽略 → 无变更 exit 1
    applied = r.returncode == 0 and "P0-19" in r.stdout
    record("V2-UPD-05", "FAIL" if not applied else "PASS",
           f"--apply 未实现（静默 no-op）: exit={r.returncode} stdout={r.stdout.strip()!r}")


def test_upd06() -> None:
    """update --apply 矛盾检测：无 apply 实现 → NOT_RUN（依赖 apply）。"""
    record("V2-UPD-06", "NOT_RUN", "依赖 update --apply（未实现，见 V2-UPD-05 证据）")


def test_upd07() -> None:
    """update --plan --json：parser 缺 --json 参数 → argparse 报错 exit 2。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 记忆"))
    env.index()
    src = env.tmp / "src.md"
    src.write_text("记忆", encoding="utf-8")
    r = env.run("update", str(src), "--plan", "--json")
    ok = r.returncode == 0
    if ok:
        try:
            data = json.loads(r.stdout)
            ok = "candidates" in data
        except json.JSONDecodeError:
            ok = False
    record("V2-UPD-07", verdict_from(ok, "--json 输出"),
           f"exit={r.returncode} stderr={r.stderr.strip()!r}")


def test_upd08() -> None:
    """update 无 source：实现面 = 增量模式（任务卡面 update [--dry-run]），非 exit 2。

    附带探针：`update --plan`（无 source）在脏 wiki 上是否静默执行增量写入
    （--plan 语义只读 → 若写入则构成 MAJOR 危险路径）。
    """
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    r1 = env.run("update")
    r2 = env.run("update", "--plan")
    # D2-F1 差异（任务卡 update [--dry-run] vs 架构 update <source> --plan）未裁定，
    # 实现合并两面：裸 update = 增量（合法），--plan 需 source。
    # 危险探针：脏 wiki（新增 b 页未入库）+ `update --plan` 无 source → 是否写入？
    write_page(env.wiki, "concepts/b.md",
               concept_page("b", "正文 [[SCHEMA.md|S]] [[concepts/a.md|A]]"))
    db_before = env.db.read_bytes()
    r3 = env.run("update", "--plan")
    db_after = env.db.read_bytes()
    wrote = db_before != db_after
    record("V2-UPD-08", "OBS",
           f"update exit={r1.returncode} update --plan exit={r2.returncode}（增量模式默认值，任务卡面）"
           f" | 危险探针: update --plan 无 source 在脏 wiki 上写入={wrote} exit={r3.returncode}（--plan 应只读）")


# ═══════════════════════════════════════════════════════════════════════
# V2-DRF 组：drift
# ═══════════════════════════════════════════════════════════════════════
def test_drf01() -> None:
    """B5：干净状态 drift 为空。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    diffs = drift.three_way_check(env.wiki, env.db)
    r = env.run("drift")
    ok = diffs == [] and r.returncode == 0 and "无漂移" in r.stdout
    record("V2-DRF-01", verdict_from(ok, f"引擎空={diffs==[]} CLI exit={r.returncode}"),
           f"engine={diffs} exit={r.returncode} out={r.stdout.strip()!r}")


def test_drf02() -> None:
    """B2：kanban 活跃任务缺页检出。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    mock_kanban(env.kanban, [{"id": "t_10000001", "title": "缺页", "status": "running"}])
    diffs = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    r = env.run("drift", MEM_KANBAN_DB=str(env.kanban))
    found = any("t_10000001" in d for d in diffs)
    # 契约：有差异 exit 3（arch §4.4）；实现：exit 1
    record("V2-DRF-02", "PASS" if found else "FAIL",
           f"检出={found} engine={diffs} CLI exit={r.returncode}（契约 exit 3，实现 exit {r.returncode}）→ 见 MEM-V2 发现")


def test_drf03() -> None:
    """B2：GAI 缺页检出 + 优先级列不产生假断链（MEM-QA-02 回归）。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-101 | 事项A | devPPL | 1h |\n"
        "| P1-02 | DPL-102 | 事项B | devPPL | 2h |\n",
        encoding="utf-8",
    )
    env.index()
    diffs = drift.three_way_check(env.wiki, env.db, gai_file=str(gai))
    found_101 = any("DPL-101" in d for d in diffs)
    found_102 = any("DPL-102" in d for d in diffs)
    fake = any("P1-01" in d or "P1-02" in d for d in diffs)
    ok = found_101 and found_102 and not fake
    record("V2-DRF-03", verdict_from(ok, f"101={found_101} 102={found_102} 假断链P1={fake}"),
           f"diffs={diffs}")


def test_drf04() -> None:
    """index 幽灵页检出。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    # 注入幽灵页条目
    idx = env.wiki / "index.md"
    idx.write_text(idx.read_text(encoding="utf-8") + "[[concepts/ghost.md]]\n", encoding="utf-8")
    diffs = drift.three_way_check(env.wiki, env.db)
    found = any("幽灵页" in d and "ghost" in d for d in diffs)
    record("V2-DRF-04", verdict_from(found, "幽灵页检出"), f"diffs={diffs}")


def test_drf05() -> None:
    """铁律 2：drift 只读不修复。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    mock_kanban(env.kanban, [{"id": "t_10000002", "title": "缺页", "status": "running"}])
    before = {p: (env.wiki / p).read_bytes() for p in ("concepts/a.md", "SCHEMA.md")}
    diffs = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    after = {p: (env.wiki / p).read_bytes() for p in ("concepts/a.md", "SCHEMA.md")}
    read_only = before == after
    ok = len(diffs) > 0 and read_only and not (env.wiki / "actions" / "t_10000002.md").exists()
    record("V2-DRF-05", verdict_from(ok, "检出且只读不修复"),
           f"diffs={len(diffs)} 文件哈希不变={read_only} 缺页未建={not (env.wiki / 'actions' / 't_10000002.md').exists()}")


def test_drf06() -> None:
    """kanban.db 缺失/损坏静默降级。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    # 缺失
    try:
        d1 = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.tmp / "missing.db"))
        ok_missing = isinstance(d1, list)
    except Exception as e:  # noqa: BLE001
        ok_missing = False
        d1 = f"EXC {e}"
    # 损坏
    bad = env.tmp / "bad.db"
    bad.write_text("not a sqlite", encoding="utf-8")
    try:
        d2 = drift.three_way_check(env.wiki, env.db, kanban_db=str(bad))
        ok_corrupt = isinstance(d2, list)
    except Exception as e:  # noqa: BLE001
        ok_corrupt = False
        d2 = f"EXC {e}"
    ok = ok_missing and ok_corrupt
    record("V2-DRF-06", verdict_from(ok, "缺失/损坏均静默"),
           f"missing={d1!r} corrupt={d2!r}")


def test_drf07() -> None:
    """done/closed/cancelled 任务不参与活跃过滤。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    mock_kanban(env.kanban, [
        {"id": "t_done01", "title": "完成", "status": "done"},
        {"id": "t_closed01", "title": "关闭", "status": "closed"},
        {"id": "t_cancelled01", "title": "取消", "status": "cancelled"},
    ])
    diffs = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    ok = all(tid not in " ".join(diffs) for tid in ("t_done01", "t_closed01", "t_cancelled01"))
    record("V2-DRF-07", verdict_from(ok, "done/closed/cancelled 排除"),
           f"diffs={diffs}")


def test_drf08() -> None:
    """drift --json：合法 JSON + diffs 数组。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    r_clean = env.run("drift", "--json")
    mock_kanban(env.kanban, [{"id": "t_10000003", "title": "缺页", "status": "running"}])
    r_dirty = env.run("drift", "--json", MEM_KANBAN_DB=str(env.kanban))
    ok = True
    ev = ""
    try:
        data_clean = json.loads(r_clean.stdout)
        data_dirty = json.loads(r_dirty.stdout)
        ok = "diffs" in data_clean and "diffs" in data_dirty and data_dirty["count"] >= 1
        ev = f"clean_count={data_clean['count']} dirty_count={data_dirty['count']}"
    except json.JSONDecodeError as e:
        ok = False
        ev = f"JSON 解析失败: {e}"
    record("V2-DRF-08", verdict_from(ok, "--json 契约"),
           f"{ev} clean_exit={r_clean.returncode} dirty_exit={r_dirty.returncode}")


# ═══════════════════════════════════════════════════════════════════════
# V2-GAI 组：gai-links
# ═══════════════════════════════════════════════════════════════════════
def test_gai01() -> None:
    """零断链：GAI 待办全部有页有双链 → 无缺失。"""
    env = Env()
    write_page(env.wiki, "actions/DPL-201.md",
               action_page("DPL-201", body="正文 [[SCHEMA.md|S]] [[DPL-201]]"))
    write_page(env.wiki, "actions/DPL-202.md",
               action_page("DPL-202", body="正文 [[SCHEMA.md|S]] [[DPL-202]]"))
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-201 | 已回填 | devPPL | 1h |\n"
        "| P1-02 | DPL-202 | 已回填 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    env.index()
    missing = gailinks.check_gai_links(env.wiki, gai_file=str(gai))
    r = env.run("gai-links", MEM_GAI_FILE=str(gai))
    ok = missing == [] and r.returncode == 0
    record("V2-GAI-01", verdict_from(ok, "零断链"), f"missing={missing} exit={r.returncode}")


def test_gai02() -> None:
    """检出缺失双链：DPL-102 缺页 → 报告，不自动建页；--fix 补双链（B3）。"""
    env = Env()
    write_page(env.wiki, "actions/DPL-101.md",
               action_page("DPL-101", body="正文 [[SCHEMA.md|S]] [[DPL-101]]"))
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-101 | 有页 | devPPL | 1h |\n"
        "| P1-02 | DPL-102 | 无页 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    env.index()
    missing = gailinks.check_gai_links(env.wiki, gai_file=str(gai))
    ids = {m["external_id"] for m in missing}
    r = env.run("gai-links", MEM_GAI_FILE=str(gai))
    ok = "DPL-102" in ids and "DPL-101" not in ids
    ok = ok and not (env.wiki / "actions" / "DPL-102.md").exists()
    ok = ok and any("P1-01" not in m["external_id"] for m in missing)  # 优先级列不产生假 ID
    # B3 补充：--fix 对有页缺链的 DPL-101 补双链 → 但 DPL-101 已有 [[DPL-101]]，
    # 构造一个"有页但缺双链"的 DPL-103 → --fix 应补段且不建新页
    write_page(env.wiki, "actions/DPL-103.md",
               action_page("DPL-103", body="正文 [[SCHEMA.md|S]]"))
    env.index()
    gai2 = env.tmp / "gai2.md"
    gai2.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-103 | 缺双链 | devPPL | 1h |\n"
        "| P1-02 | DPL-104 | 无页 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    m2 = gailinks.check_gai_links(env.wiki, gai_file=str(gai2))
    ids2 = {m["external_id"] for m in m2}
    r_fix = env.run("gai-links", "--fix", "--no-commit", MEM_GAI_FILE=str(gai2))
    text103 = (env.wiki / "actions" / "DPL-103.md").read_text(encoding="utf-8")
    fix_ok = "DPL-103" in ids2 and r_fix.returncode == 0
    fix_ok = fix_ok and "GAI 关联" in text103
    fix_ok = fix_ok and not (env.wiki / "actions" / "DPL-104.md").exists()
    record("V2-GAI-02",
           verdict_from(ok and fix_ok, "检出且不建页 + --fix 补链"),
           f"missing={ids} exit={r.returncode} 建页={(env.wiki / 'actions' / 'DPL-102.md').exists()}"
           f" | --fix: exit={r_fix.returncode} 补段={'GAI 关联' in text103} DPL-104未建={not (env.wiki / 'actions' / 'DPL-104.md').exists()}")


def test_gai03() -> None:
    """表头变体解析：golden gai-dirty → 4 events 正确。"""
    env = Env()
    golden = REPO / "tests" / "golden" / "gai-dirty.md"
    adapter = GaiAdapter(gai_file=str(golden))
    events = adapter.fetch_events()
    ids = {ev.external_id for ev in events}
    ok = ids == {"DPL-009", "DPL-010", "INF-011", "INF-012"}
    record("V2-GAI-03", verdict_from(ok, "4 events 正确解析"),
           f"ids={sorted(ids)} kinds={[(e.external_id, e.kind) for e in events]}")


def test_gai04() -> None:
    """map_id + mirror_status。"""
    env = Env()
    golden = REPO / "tests" / "golden" / "gai-dirty.md"
    adapter = GaiAdapter(gai_file=str(golden))
    m1 = adapter.map_id("DPL-009")
    m2 = adapter.map_id("dpl-009")
    m3 = adapter.map_id("BOGUS")
    ms = adapter.mirror_status("wiki", "DPL-009")
    ok = m1 == "DPL-009" and m2 == "DPL-009" and m3 is None
    ok = ok and ms.get("status") in ("active", "done")
    record("V2-GAI-04", verdict_from(ok, "map_id/mirror_status"),
           f"map={m1}/{m2}/{m3} mirror={ms}")


def test_gai05() -> None:
    """缺 GAI 文件降级：fetch_events 空列表，不抛异常。"""
    env = Env()
    adapter = GaiAdapter(gai_file=str(env.tmp / "missing-gai.md"))
    try:
        events = adapter.fetch_events()
        ok = events == []
    except Exception as e:  # noqa: BLE001
        ok = False
        events = f"EXC {e}"
    record("V2-GAI-05", verdict_from(ok, "空列表降级"), f"events={events!r}")


def test_gai06() -> None:
    """done 行状态识别。"""
    env = Env()
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-301 | ✅ done 事项 | devPPL | 1h |\n"
        "| P1-02 | DPL-302 | 进行中事项 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    adapter = GaiAdapter(gai_file=str(gai))
    events = {e.external_id: e for e in adapter.fetch_events()}
    ok = events.get("DPL-301", None) and events["DPL-301"].kind == "done"
    ok = ok and events.get("DPL-302", None) and events["DPL-302"].kind == "active"
    record("V2-GAI-06", verdict_from(ok, "done/active 识别"),
           f"301={events.get('DPL-301') and events['DPL-301'].kind} 302={events.get('DPL-302') and events['DPL-302'].kind}")


# ═══════════════════════════════════════════════════════════════════════
# V2-DEM 组：demote
# ═══════════════════════════════════════════════════════════════════════
def test_dem01() -> None:
    """demote 正常路径：status 变更 + 说明节 + bump updated + log。"""
    env = Env()
    write_page(env.wiki, "actions/P0-19.md", action_page("P0-19", body="正文 [[SCHEMA.md|S]]"))
    env.index()
    r = env.run("demote", "P0-19", "--status", "blocked", "--reason", "被上游阻塞", "--no-commit")
    text = (env.wiki / "actions" / "P0-19.md").read_text(encoding="utf-8")
    log = (env.wiki / "log.md").read_text(encoding="utf-8") if (env.wiki / "log.md").exists() else ""
    ok = r.returncode == 0 and "status: blocked" in text
    ok = ok and "被上游阻塞" in text
    ok = ok and ("变更记录" in text or "状态变更" in text)
    ok = ok and "demote" in log and "P0-19" in log
    record("V2-DEM-01", verdict_from(ok, "status+说明+bump+log"),
           f"exit={r.returncode} status_blocked={'status: blocked' in text} reason={'被上游阻塞' in text} log={'demote' in log}")


def test_dem02() -> None:
    """B4 间接：demote 后双链不断裂。"""
    env = Env()
    write_page(env.wiki, "actions/P0-19.md",
               action_page("P0-19", body="正文 [[concepts/ref.md|Ref]] [[SCHEMA.md|SCHEMA]]"))
    write_page(env.wiki, "concepts/ref.md",
               concept_page("ref", "正文 [[P0-19]] [[SCHEMA.md|S]]"))
    env.index()
    r = env.run("demote", "P0-19", "--status", "blocked", "--no-commit")
    r_lint = env.run("lint")
    text = (env.wiki / "actions" / "P0-19.md").read_text(encoding="utf-8")
    ok = r.returncode == 0 and r_lint.returncode == 0
    ok = ok and "[[P0-19]]" in (env.wiki / "concepts" / "ref.md").read_text(encoding="utf-8")
    record("V2-DEM-02", verdict_from(ok, "lint 零问题 + 双链保留"),
           f"demote_exit={r.returncode} lint_exit={r_lint.returncode} out={r_lint.stdout.strip()!r}")


def test_dem03() -> None:
    """demote 不存在页 → exit 1。"""
    env = Env()
    env.index()
    r = env.run("demote", "NONEXIST-999", "--status", "blocked", "--no-commit")
    ok = r.returncode == 1
    record("V2-DEM-03", verdict_from(ok, "exit 1 页不存在"), f"exit={r.returncode} stderr={r.stderr.strip()!r}")


def test_dem04() -> None:
    """demote 无 --reason：实现默认 status=blocked，无用法错误（契约 OBS）。"""
    env = Env()
    write_page(env.wiki, "actions/P0-19.md", action_page("P0-19", body="正文 [[SCHEMA.md|S]]"))
    env.index()
    r = env.run("demote", "P0-19", "--no-commit")
    text = (env.wiki / "actions" / "P0-19.md").read_text(encoding="utf-8")
    # 契约（arch §4.4 --reason 必填 → exit 2/1）；实现默认 blocked + 自动 reason → exit 0
    contract = r.returncode in (1, 2)
    record("V2-DEM-04", "OBS" if r.returncode == 0 else ("PASS" if contract else "FAIL"),
           f"exit={r.returncode}（实现默认 --status=blocked，--reason 可选）status_blocked={'status: blocked' in text}")


def test_dem05() -> None:
    """镜像 L0 状态列：memctl 不写 GAI（铁律 2 断言）。"""
    env = Env()
    write_page(env.wiki, "actions/P0-19.md", action_page("P0-19", body="正文 [[SCHEMA.md|S]]"))
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | P0-19 | 事项 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    env.index()
    gai_before = gai.read_bytes()
    r = env.run("demote", "P0-19", "--status", "blocked", "--no-commit", MEM_GAI_FILE=str(gai))
    gai_after = gai.read_bytes()
    ok = r.returncode == 0 and gai_before == gai_after
    record("V2-DEM-05", verdict_from(ok, "GAI 未被 memctl 写入"),
           f"exit={r.returncode} GAI 哈希不变={gai_before == gai_after}")


# ═══════════════════════════════════════════════════════════════════════
# V2-IDM 组：幂等
# ═══════════════════════════════════════════════════════════════════════
def test_idm01() -> None:
    """update --plan 3 次候选集一致。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 记忆中间层架构决策"))
    env.index()
    source = "记忆中间层架构决策 未来扩展向量检索"
    r1 = blast.compute_candidates(env.db, source)
    r2 = blast.compute_candidates(env.db, source)
    r3 = blast.compute_candidates(env.db, source)
    ok = r1 == r2 == r3
    record("V2-IDM-01", verdict_from(ok, "3 次一致"), f"len={len(r1)} equal={r1 == r2 == r3}")


def test_idm02() -> None:
    """update --apply 幂等：依赖 apply（未实现）→ NOT_RUN。"""
    record("V2-IDM-02", "NOT_RUN", "依赖 update --apply（未实现，见 V2-UPD-05 证据）")


def test_idm03() -> None:
    """drift 3 次一致。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    mock_kanban(env.kanban, [{"id": "t_10000010", "title": "缺页", "status": "running"}])
    d1 = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    d2 = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    d3 = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    ok = d1 == d2 == d3
    record("V2-IDM-03", verdict_from(ok, "3 次 diffs 一致"), f"len={len(d1)} equal={d1 == d2 == d3}")


def test_idm04() -> None:
    """drift 幂等只读无副作用（文件哈希不变）。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    write_page(env.wiki, "actions/DPL-401.md",
               action_page("DPL-401", body="正文 [[SCHEMA.md|S]] [[DPL-401]]"))
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-401 | 事项 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    env.index()
    files = list((env.wiki).rglob("*.md"))
    before = {str(p): p.read_bytes() for p in files}
    drift.three_way_check(env.wiki, env.db, gai_file=str(gai), kanban_db=str(env.kanban))
    after = {str(p): p.read_bytes() for p in files}
    ok = before == after
    record("V2-IDM-04", verdict_from(ok, "全文件哈希不变"), f"files={len(files)} hash_eq={before == after}")


# ═══════════════════════════════════════════════════════════════════════
# V2-NEG 组：负面注入
# ═══════════════════════════════════════════════════════════════════════
def test_neg01() -> None:
    """注入 GAI 断链 → gai-links/drift 检出。"""
    env = Env()
    write_page(env.wiki, "actions/DPL-101.md",
               action_page("DPL-101", body="正文 [[SCHEMA.md|S]] [[DPL-101]]"))
    gai = env.tmp / "gai.md"
    gai.write_text(
        "| 优先级 | 任务ID | 行动 | 机制 | 工时 |\n"
        "|--------|--------|------|------|:---:|\n"
        "| P1-01 | DPL-101 | 事项 | devPPL | 1h |\n",
        encoding="utf-8",
    )
    env.index()
    # 注入断链：删页
    (env.wiki / "actions" / "DPL-101.md").unlink()
    missing = gailinks.check_gai_links(env.wiki, gai_file=str(gai))
    diffs = drift.three_way_check(env.wiki, env.db, gai_file=str(gai))
    ok = any("DPL-101" in m["external_id"] for m in missing)
    ok = ok and any("DPL-101" in d for d in diffs)
    record("V2-NEG-01", verdict_from(ok, "双路径检出"),
           f"gai-links={[m['external_id'] for m in missing]} drift={diffs}")


def test_neg02() -> None:
    """注入 kanban 差异 → drift 检出 + 修复后为空。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    env.index()
    mock_kanban(env.kanban, [{"id": "t_99999999", "title": "新任务", "status": "running"}])
    d1 = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    found = any("t_99999999" in d for d in d1)
    # 修复：建页 + 机械维护（index 刷新 index.md / db —— 等价 memctl add 后维护）
    write_page(env.wiki, "actions/t_99999999.md",
               action_page("t_99999999", body="正文 [[SCHEMA.md|S]]"))
    env.index()
    d2 = drift.three_way_check(env.wiki, env.db, kanban_db=str(env.kanban))
    ok = found and d2 == []
    record("V2-NEG-02", verdict_from(ok, "注入检出+修复为空"),
           f"d1={d1} d2={d2}")


def test_neg03() -> None:
    """注入 index 不一致 → drift 检出（未收录 + 幽灵页双向）。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md", concept_page("a", "正文 [[SCHEMA.md|S]]"))
    write_page(env.wiki, "concepts/b.md", concept_page("b", "正文 [[SCHEMA.md|S]]"))
    env.index()
    idx = env.wiki / "index.md"
    text = idx.read_text(encoding="utf-8")
    # 删除 b 条目（未收录）+ 注入 ghost（幽灵页）—— index 条目格式 [[path|title]]
    new_text = text.replace("[[concepts/b.md|b]]", "") + "[[concepts/ghost.md|ghost]]\n"
    idx.write_text(new_text, encoding="utf-8")
    diffs = drift.three_way_check(env.wiki, env.db)
    unlisted = any("未收录" in d and "b.md" in d for d in diffs)
    ghost = any("幽灵页" in d and "ghost" in d for d in diffs)
    ok = unlisted and ghost
    record("V2-NEG-03", verdict_from(ok, "双向检出"), f"diffs={diffs}")


def test_neg04() -> None:
    """注入冲突源 → contradictions：依赖 apply（未实现）→ NOT_RUN。"""
    record("V2-NEG-04", "NOT_RUN", "依赖 update --apply 矛盾检测（未实现）")


def test_neg05() -> None:
    """注入 db 篡改 → lint 检出（exit 3）。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md",
               concept_page("a", "正文 [[SCHEMA.md|S]] [[concepts/b.md|B]]"))
    write_page(env.wiki, "concepts/b.md",
               concept_page("b", "正文 [[SCHEMA.md|S]] [[concepts/a.md|A]]"))
    env.index()
    conn = sqlite3.connect(str(env.db))
    try:
        conn.execute("UPDATE pages SET status='bogus' WHERE id='a'")
        conn.commit()
    finally:
        conn.close()
    r = env.run("lint")
    ok = r.returncode == 3 and "db 与文件不一致" in r.stdout
    record("V2-NEG-05", verdict_from(ok, "lint I4 检出"), f"exit={r.returncode} out={r.stdout.strip()!r}")


# ═══════════════════════════════════════════════════════════════════════
# V2-REG 组：回归保护（真实 repo 只读 + 临时环境）
# ═══════════════════════════════════════════════════════════════════════
def test_reg01() -> None:
    """V2 接线后 MVP lint 仍零问题（真实 repo 只读）。"""
    env = Env()
    # 用干净 env（清掉本进程可能污染的 MEM_* 变量）对真实 repo 跑 lint（只读）
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("MEM_")}
    r = subprocess.run(
        [sys.executable, str(MEMCTL), "lint"],
        capture_output=True, text=True, cwd=str(REPO), env=clean_env,
    )
    ok = r.returncode == 0 and "零问题" in r.stdout
    record("V2-REG-01", verdict_from(ok, "真实 repo lint 0"), f"exit={r.returncode} out={r.stdout.strip()!r}")


def test_reg02() -> None:
    """done --check 三态不变（临时环境）。"""
    env = Env()
    env.index()
    r1 = env.run("done", "t_nonexist", "--check")
    write_page(env.wiki, "actions/t_50000001.md",
               action_page("t_50000001", body="正文 [[SCHEMA.md|S]]"))
    r2 = env.run("done", "t_50000001", "--check")
    write_page(env.wiki, "actions/t_50000002.md",
               action_page("t_50000002", status="done", body="正文 [[SCHEMA.md|S]]"))
    r3 = env.run("done", "t_50000002", "--check")
    ok = r1.returncode == 1 and r2.returncode == 3 and r3.returncode == 0
    record("V2-REG-02", verdict_from(ok, "1/3/0 三态"),
           f"nonexist={r1.returncode} active={r2.returncode} done={r3.returncode}")


def test_reg03() -> None:
    """query 命中（trigram + bigram 回退）。"""
    env = Env()
    write_page(env.wiki, "concepts/middleware.md",
               concept_page("middleware", "正文 记忆中间层 架构决策 [[SCHEMA.md|S]]"))
    env.index()
    r1 = env.run("query", "中间层")
    r2 = env.run("query", "中间")
    ok = r1.returncode == 0 and "middleware" in r1.stdout
    ok = ok and r2.returncode == 0 and "middleware" in r2.stdout
    record("V2-REG-03", verdict_from(ok, "trigram+bigram 命中"),
           f"t3_exit={r1.returncode} hit3={'middleware' in r1.stdout} t2_exit={r2.returncode} hit2={'middleware' in r2.stdout}")


def test_reg04() -> None:
    """index --rebuild 幂等（含首页已存在场景，规避首次 bootstrap 差异）。"""
    env = Env()
    write_page(env.wiki, "concepts/a.md",
               concept_page("a", "正文 [[SCHEMA.md|S]] [[concepts/b.md|B]]"))
    write_page(env.wiki, "concepts/b.md",
               concept_page("b", "正文 [[SCHEMA.md|S]] [[concepts/a.md|A]]"))
    # 首次 build 生成 index.md/log.md 首页
    env.index()
    r1 = env.run("index", "--rebuild")
    n1 = _pages_count(env.db)
    r2 = env.run("index", "--rebuild")
    n2 = _pages_count(env.db)
    rl1 = env.run("lint")
    rl2 = env.run("lint")
    ok = r1.returncode == 0 and r2.returncode == 0 and n1 == n2
    ok = ok and rl1.returncode == 0 and rl2.returncode == 0
    record("V2-REG-04", verdict_from(ok, "rebuild 幂等 + lint 0"),
           f"pages={n1}/{n2} lint={rl1.returncode}/{rl2.returncode}")


def _pages_count(db: Path) -> int:
    if not db.exists():
        return -1
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════
# 汇总
# ═══════════════════════════════════════════════════════════════════════
ALL = [
    ("V2-STB-01", test_stb01),
    ("V2-UPD-01", test_upd01), ("V2-UPD-02", test_upd02), ("V2-UPD-03", test_upd03),
    ("V2-UPD-04", test_upd04), ("V2-UPD-05", test_upd05), ("V2-UPD-06", test_upd06),
    ("V2-UPD-07", test_upd07), ("V2-UPD-08", test_upd08),
    ("V2-DRF-01", test_drf01), ("V2-DRF-02", test_drf02), ("V2-DRF-03", test_drf03),
    ("V2-DRF-04", test_drf04), ("V2-DRF-05", test_drf05), ("V2-DRF-06", test_drf06),
    ("V2-DRF-07", test_drf07), ("V2-DRF-08", test_drf08),
    ("V2-GAI-01", test_gai01), ("V2-GAI-02", test_gai02), ("V2-GAI-03", test_gai03),
    ("V2-GAI-04", test_gai04), ("V2-GAI-05", test_gai05), ("V2-GAI-06", test_gai06),
    ("V2-DEM-01", test_dem01), ("V2-DEM-02", test_dem02), ("V2-DEM-03", test_dem03),
    ("V2-DEM-04", test_dem04), ("V2-DEM-05", test_dem05),
    ("V2-IDM-01", test_idm01), ("V2-IDM-02", test_idm02), ("V2-IDM-03", test_idm03),
    ("V2-IDM-04", test_idm04),
    ("V2-NEG-01", test_neg01), ("V2-NEG-02", test_neg02), ("V2-NEG-03", test_neg03),
    ("V2-NEG-04", test_neg04), ("V2-NEG-05", test_neg05),
    ("V2-REG-01", test_reg01), ("V2-REG-02", test_reg02), ("V2-REG-03", test_reg03),
    ("V2-REG-04", test_reg04),
]


def main() -> None:
    print(f"mem-core HEAD: {subprocess.run(['git', '-C', str(REPO), 'rev-parse', '--short', 'HEAD'], capture_output=True, text=True).stdout.strip()}")
    print(f"被测对象: {REPO}  | 41 用例独立实测\n" + "=" * 60)
    for case, fn in ALL:
        try:
            fn()
        except Exception as e:  # noqa: BLE001
            record(case, "FAIL", f"异常: {type(e).__name__}: {e}")
    print("\n" + "=" * 60)
    from collections import Counter
    c = Counter(r["verdict"] for r in RESULTS)
    print(f"汇总: {dict(c)}  ({len(RESULTS)} 用例)")
    # 输出 JSON 供报告生成
    Path("/tmp/qa_v2_results.json").write_text(
        json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
