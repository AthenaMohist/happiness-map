# 评估算法校准机制 — 架构设计（子卡超时→预估偏差反馈→自适应，DPL-018）

> 发言人：高见远（架构师） | 日期：2026-08-13 | 版本：v1.0
> 输入：PRD v1.0（docs/prd/estimate-calibration-prd.md，commit 33bef7a）+ 现状代码核查（cmd_chain.py / discover.py / checkpoint.py / cmd_channel.sh / test_cmd_channel.sh / notify_check.py）+ 存量设计（estimate-split-cards / smart-skip-steps / DPL-020 arch-fix-standalone-dev-subsplit）
> 定位：6 步闭环 Step 2 架构落地 —— 把 PRD E-1..E-7 + 待裁决 D1..D2 细化为文件/函数/数据流级实现方案，工程师可直接照写代码
> 核心原则：**评估失准是系统的可学习信号，不是执行者的过错。** 子卡超时 → 系统自动采集「预估 vs 实际」→ 偏差落库 → 下次评估卡/子卡生成时注入校准上下文 → 评估口径一次比一次准，超时一次比一次少。
> 数据流红线（PRD C2/C3/C5）：采集**只读 kanban.db**、**只写 pipeline_state.db**；任何采集/注入失败 fail-open（不阻塞主流程、退出码 0）；子卡超时判定只依赖 task_runs（内核语义，消费不修改）。

---

## 0. 范围与裁决总表

### 0.1 本设计做什么（PRD E-1..E-7 全覆盖 + 待裁决 D1/D2 定稿）

| # | PRD 需求 / 待裁决 | 本设计章节 | 状态 |
|---|------------------|-----------|------|
| 1 | E-1 [SUB-SPLIT] 每子卡预估轮数（解析 + prompt 格式说明） | §3 | ✅ |
| 2 | E-2 est_deviation 表（pipeline_state.db，UNIQUE 幂等，fail-open） | §4 | ✅ |
| 3 | E-3 偏差采集（cmd_channel tick 段 + 匹配 + upsert） | §5 | ✅ |
| 4 | E-4 calc_calibration_factor 纯函数（中位数/clamp/连续超时 flag） | §6 | ✅ |
| 5 | E-5 评估 prompt 注入（cmd_chain + discover 双入口 + trigger 兜底） | §7 | ✅ |
| 6 | E-6 子卡 body 校准注入（_create_dev_sub_cards + _create_qa_sub_cards） | §8 | ✅ |
| 7 | E-7 测试（新增 T59+，≥15 断言，T1-T58 回归） | §9 | ✅ |
| 8 | D1 完成卡是否采集偏差（P1 E-8） | §10 | ✅ **定稿：P0 只做超时反馈** |
| 9 | D2 校准系数是否允许 <1（下偏校准） | §10 | ✅ **定稿：clamp 下限 0.5** |

### 0.2 架构裁决总表（本设计的核心决策）

| 决策点 | 裁决 | 说明 |
|--------|------|------|
| **A1 校准模块归属** | **新增 `pipeline/calibration.py`**（单一职责：偏差采集 + 系数计算 + 上下文构建 + 渲染 + backfill） | cmd_chain.py 已 1538 行、discover.py 已 919 行；校准是独立领域（反馈闭环），不塞进既有模块。模块内 `collect_est_deviations` 对 cmd_chain 做**函数内延迟导入**（`from pipeline.cmd_chain import _read_sub_split`）→ cmd_chain 可安全模块级 `from pipeline.calibration import ...`，**无循环导入** |
| **A2 采集游标（不追溯历史）** | project_config 存 `est_calib_last_run_id`（task_runs.id 游标）；首次运行（无游标）→ 初始化游标 = MAX(task_runs.id) 且**不采集**（PRD N6：不追溯历史超时） | task_runs.id 是 AUTOINCREMENT 单调递增、永不复用 → 游标天然幂等。每 tick 只处理 `id > 游标` 的新行，处理完推进游标 |
| **A3 retry_count 语义** | 同子卡第二次超时（新 task_runs 行）→ 不新增行，`UPDATE retry_count = retry_count + 1`（AC-4：1→2） | UNIQUE(sub_task_id) 幂等建行；游标保证每次超时事件恰好处理一次，retry_count 精确 = 超时次数 |
| **A4 触发路径校准注入缺口** | est_intercept_after_insert **触发器是纯 SQL，无法读 pipeline_state.db**（跨库，SQLite 触发器禁止 ATTACH）→ 独立卡 est 卡实际由触发器建 body，Python 入口注入不到 → **新增 `backfill_est_bodies`（tick 段内调用）**：扫描 `status='ready'` 且 body 无校准标记的 est 卡，补写校准段（幂等：标记防重） | 实测链路：OC 直建 dev 卡 → 触发器同事务建 est 卡（body=SQL 模板）→ dispatcher 60s 内 claim。backfill 在 autopilot tick（2min）内跑，对尚未被 claim 的 ready 卡补写。**已 claim 的卡跳过**（worker 已拿 body，补写无意义）。残留竞态窗口（trigger→claim <60s vs backfill 2min tick）接受：校准是 prompt 增强不是正确性门，fail-open（C3）；且子卡 body 校准（E-6，建卡时注入）不受此窗口影响 |
| **A5 E-5 全局 vs E-6 局部门控** | E-5 评估卡注入用**全局**偏差（所有 est_deviation 窗口）；E-6 子卡 body 注入门控「该 spec_hash **或** est_card_id 有记录」（链卡用 spec_hash，独立卡 discover-sub- 无 spec_hash → 用 est_card_id） | PRD E-5 明确「最近 5 条 + 累计偏差率 + K」= 全局口径；E-6 明确「该 spec_hash 已有 est_deviation」= 局部门控。独立卡无 spec_hash 是 DPL-020 幂等键 `discover-sub-<id>-<N>` 的必然结果，用 est_card_id 等价门控 |
| **A6 校准段位置** | ⚠️ 横幅 = body **首行**（编号行之前）；「历史偏差校准」段 = dev-est 任务说明块末尾。无数据 → 段与横幅都省略（AC-9 首次评估零噪音） | PRD E-5：「timeout_flag 时顶部加 ⚠️ 横幅」；「无记录 → 段省略」 |
| **A7 QA 子卡同享校准** | `_create_qa_sub_cards` 同步注入校准行（E-6 范围 PRD 只写 dev，但 QA 执行子卡超时同样进 est_deviation，对称注入零成本） | 采集（E-3）已按 PRD 覆盖 [DEV-QA-SUB-*]；注入不对称会造成 QA 子卡永远看不到校准。一行参数，进 P0 |
| **A8 时间口径** | created_at 用 UTC ISO（`%Y-%m-%dT%H:%M:%SZ`，与 checkpoint.py `_now_iso` 同款）；窗口排序用 `ORDER BY id DESC`（插入序 = 事件序，单调可靠），created_at 作审计 | PRD C8：UTC 口径；ISO 字符串字典序 = 时间序，双保险 |
| **A9 测试编号** | 新增 **T59-T69**（+T31 扩展断言） | 存量 T1-T58 已占用（T51 缺失历史遗留）；新编号从 59 起 |
| **A10 工时** | P0 = **9.5h**（PRD 9h + 0.5h：A4 backfill 覆盖 trigger 路径缺口） | 诚实增量：PRD 未计 trigger 路径，架构实测后补 |

### 0.3 约束合规确认

| 约束 | 本设计合规点 |
|------|-------------|
| C1 EST_SPLIT_THRESHOLD_ROUNDS=20 不改 | 零引用改动；constants.py L92 原样保留（AC-13 断言） |
| C2 采集只读 kanban.db、只写 pipeline_state.db | `collect_est_deviations` 对 kanban.db 仅 SELECT（task_runs/tasks/task_comments/task_links），对 pipeline_state.db 仅 INSERT/UPDATE（est_deviation/project_config） |
| C3 fail-open | 所有 DB 访问 try/except 包住；表缺失/库缺失 → 返回 0 不抛；cmd_channel 段调用失败仅日志 |
| C4 校准走 prompt 注入，不机械改预估 | E-5/E-6 全部是「注入上下文 + 建议」，拆卡决策仍由评估模型/阈值判定（E-9 机械自适应明确排 P1） |
| C5 子卡超时判定只依赖 task_runs | 只读 status/outcome/error/ended_at；不修改内核语义 |
| C6 兼容旧 [SUB-SPLIT] 格式 | 无轮数 → `estimates=None`，解析成功、行为与现有一致（AC-2，T27/T28/T31 不回归） |
| C7 dev-est 可被 --skip dev-est 跳过 | 跳过路径不建评估卡 → 无校准注入点，天然兼容（注入只在建卡函数内） |
| C8 时间基准 UTC | A8 定稿 ISO UTC |

---

## 1. 现状核查与数据流全景

### 1.1 现状核查（读码结论，非假设）

| # | 核查点 | 结论 | 证据 |
|---|--------|------|------|
| 1 | `_parse_sub_split` 只取 count/mode/titles | 确认：返回 dict 仅 4 键，轮数被丢弃 | cmd_chain.py L551-593 |
| 2 | `_read_sub_split` 读最新 [SUB-SPLIT] comment | 确认：`body LIKE '[<marker>]%' ORDER BY id DESC LIMIT 1` → `_parse_sub_split` 权威复验 marker | cmd_chain.py L596-611 |
| 3 | 子卡 body 含「评估卡 <id>」可解析 | 确认：`_sub_card_body` 写 `来源: [DEV-EST] 评估拆卡（评估卡 {parent_id}），子卡 {i}/{total}`（dev/qa 同款） | cmd_chain.py L630-662 |
| 4 | 子卡幂等键格式 | 链卡 dev：`dev-<hash>-dev-sub-<N>`；链卡 qa：`dev-<hash>-qa-exec-sub-<N>`；独立卡：`discover-sub-<源卡id>-<N>`（DPL-020） | cmd_chain.py L696-700 / L735-740 / discover.py L890 |
| 5 | task_runs 超时事实 | `status IN ('timed_out','gave_up')` + `error` 含 `Iteration budget exhausted (60/60)`；id 为 AUTOINCREMENT 单调 | 实测 schema（/root/.hermes/kanban.db）+ notify_check.py L1147-1157 先例 |
| 6 | est_deviation 无表 | pipeline_state.db 现 3 表（pipeline_steps/project_config/task_control） | checkpoint.py SCHEMA_SQL L13-51 |
| 7 | est 卡三入口 | ① cmd_chain `advance_sequential_chains` L1151-1159 建链卡 dev-est；② discover `_create_est_card` L199-250 建独立卡；③ **est_intercept_after_insert 触发器纯 SQL 建卡**（discover.py L335-370，body 模板 L341-355） | cmd_chain.py / discover.py / autopilot.sh L94-99 |
| 8 | 评估 prompt 格式说明三处 | cmd_chain `_dev_card_body` L483-487、discover `_create_est_card` L229、est trigger SQL body L353-354 | 三处都要加「每子卡带预估轮数」格式说明 |
| 9 | cmd_channel.sh 六段结构 | ①flock ②滞留告警 ③扫描 ④消费 ⑤链卡消费 ⑥advance；`PIPELINE_DB` 变量已在 L46 | cmd_channel.sh L465-730 |
| 10 | checkpoint ensure_schema 时机 | autopilot L116 每 tick `db.ensure_schema()` 在 cmd_channel.sh（L55 调用）**之后** → 采集段必须自带 `CREATE TABLE IF NOT EXISTS` 兜底 | autopilot.sh L55 / L116 |
| 11 | 测试编号尾部 | T58 为当前最后用例（T56-T58 链卡消费 FIX） | test_cmd_channel.sh L1719-1836 |
| 12 | 测试 harness | 隔离 temp kanban.db（复制真实 schema + DROP 触发器）+ temp pipeline_state.db + 隔离 flock；`q1` helper 已存在 | test_cmd_channel.sh L22-116 |

### 1.2 现状数据流（缺陷：超时无感知）

```
[DEV-EST] 评估卡 → [SUB-SPLIT] N serial|parallel（只解析 count/mode/titles，轮数丢弃）
  → autopilot 建 N 张 [DEV-SUB-*] 子卡（body 无预估信息）
  → 子卡执行 → 60/60 timed_out（error 落 task_runs）
  → ❌ 系统无感知：无人读 task_runs 超时、无预估可比对、下次评估照旧
实证: t_15a3982c（拆后仍 60/60 ×2，评估"预计 10-12 轮" vs 实际 60，偏差 +500%）
```

### 1.3 目标数据流（反馈闭环）

```
[DEV-EST] 评估卡（body 注入【历史偏差校准】段：最近 5 条 + 累计偏差率 + K + ⚠️横幅）
  ├─ prompt 要求每子卡带「预计 X-Y 轮」→ [SUB-SPLIT] comment
  ├─ _parse_sub_split 解析 estimates=[{min,max},...]（与 titles 序号对齐）
  ├─ autopilot 建子卡（body 注入「预估轮数（含校准）: N 轮」，N=round(mid×K)）
  ├─ 子卡执行 → 60/60 timed_out → task_runs 新行
  ├─ cmd_channel tick 段 collect_est_deviations（只读 kanban → upsert est_deviation）
  │     ├─ 游标推进（est_calib_last_run_id）
  │     └─ backfill_est_bodies（ready 态 est 卡补校准段，覆盖 trigger 路径）
  └─ 下次评估卡生成 → 读到 est_deviation → 校准上下文 → 闭环
```

---

## 2. 模块设计：`pipeline/calibration.py`（新增，A1）

### 2.1 模块边界与职责

```python
"""pipeline/calibration.py — DPL-018 评估算法校准（子卡超时→偏差反馈→自适应）。

职责（单一领域：评估口径反馈闭环）:
  - 偏差采集: collect_est_deviations（只读 kanban.db task_runs → upsert pipeline_state.db est_deviation）
  - 系数计算: calc_calibration_factor（纯函数，E-4）
  - 上下文构建: load_recent_records / build_calibration_context（E-5 输入）
  - 渲染: render_calibration_section / render_banner（E-5 输出）
  - 触发路径兜底: backfill_est_bodies（A4）
  - 子卡校准: calibrated_rounds（E-6）
依赖方向: calibration → cmd_chain（仅 collect_est_deviations 内延迟导入 _read_sub_split）
          cmd_chain → calibration（模块级，E-6 用）
          discover → calibration（模块级，E-5 用）
无循环导入。全部 DB 访问 try/except fail-open（C3）。
"""
```

### 2.2 关键 API 签名（工程师实现锚点）

| 函数 | 签名 | 归属需求 |
|------|------|---------|
| `collect_est_deviations` | `(kanban_db: str, pipeline_db: str) -> int` | E-3；返回本次处理行数（含跳过）；异常内吞返回 0 |
| `calc_calibration_factor` | `(records: list[dict], window: int = 10) -> tuple[float, float, bool]` | E-4；`(factor, cum_rate, timeout_flag)`；纯函数无 IO |
| `load_recent_records` | `(pipeline_db: str, limit: int = 10) -> list[dict]` | E-4/E-5；`SELECT ... ORDER BY id DESC LIMIT ?`；fail-open → [] |
| `build_calibration_context` | `(pipeline_db: str) -> Optional[dict]` | E-5；无记录 → None；有 → `{records_5, cum_rate, factor, timeout_flag}` |
| `render_calibration_section` | `(ctx: dict) -> str` | E-5；「历史偏差校准」段 markdown |
| `render_banner` | `(ctx: dict) -> Optional[str]` | E-5；timeout_flag → `⚠️ ...` 否则 None |
| `backfill_est_bodies` | `(kanban_db: str, pipeline_db: str) -> int` | E-5/A4；扫描 ready est 卡补写校准段；返回补写数 |
| `calibrated_rounds` | `(pipeline_db: str, spec_hash: str, est_card_id: str, estimate: dict) -> Optional[int]` | E-6；门控 spec_hash/est_card_id 有记录 → `round(mid×K)`；无 → None |

---

## 3. E-1 [SUB-SPLIT] 每子卡预估轮数

### 3.1 `_parse_sub_split` 扩展（cmd_chain.py L551-593）

**新增正则**（放在 SUB_ITEM_RE 之后）：

```python
# 每行尾部预估轮数: "预计 8-10 轮"（区间）/ "预计 8 轮"（单值，min=max）
EST_RANGE_RE = re.compile(r"预计\s*(\d+)\s*(?:-|~|至)\s*(\d+)\s*轮")
EST_SINGLE_RE = re.compile(r"预计\s*(\d+)\s*轮")
```

**解析逻辑**（titles 循环内，对每个 `t = im.group(1).strip()`）：

```python
def _extract_estimate(line: str) -> Optional[dict]:
    """'预计 X-Y 轮' → {min:X, max:Y}；'预计 X 轮' → {min:X, max:X}；无 → None。
    X>Y → 交换（宽容，防异常文案负偏差）；mid==0 由调用方跳过。"""
    m = EST_RANGE_RE.search(line)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if lo > hi:
            lo, hi = hi, lo
        return {"min": lo, "max": hi}
    m = EST_SINGLE_RE.search(line)
    if m:
        v = int(m.group(1))
        return {"min": v, "max": v}
    return None
```

**返回 dict 增加 `"estimates"` 键**：

```python
estimates: list[Optional[dict]] = [_extract_estimate(t) for t in titles]  # 与 titles 序号对齐
return {
    "marker": marker, "count": count, "mode": mode or "serial",
    "titles": titles,
    "estimates": estimates if any(e is not None for e in estimates) else None,
    # None = 全部行无轮数（旧格式兼容，AC-2）；有任一 → 列表（缺省行 None 占位）
}
```

**边界用例（进 T59 单测）**：
- `[SUB-SPLIT] 2 serial\n1. [S1] 编号注入 预计 8-10 轮\n2. [S2] drift 扩展 预计 12-14 轮` → `estimates=[{8,10},{12,14}]`（AC-1）
- 无轮数 `1. 甲\n2. 乙` → `estimates=None`（AC-2，T31 现有断言不回归）
- 混杂 `1. 甲 预计 8-10 轮\n2. 乙` → `estimates=[{8,10},None]`
- 单值 `预计 8 轮` → `{min:8,max:8}`
- `预计 10-8 轮` → 交换 `{min:8,max:10}`
- `预计 ≤20 轮`（阈值描述，非预估）→ 不匹配（`预计` 后紧跟 `≤` 非数字）→ None
- titles 缺省（无列表行）→ `estimates=None`

### 3.2 评估 prompt 格式说明（三处同步）

| 位置 | 现状 | 改为 |
|------|------|------|
| cmd_chain.py `_dev_card_body` L483-487 | `[SUB-SPLIT] N serial|parallel\n1. 子任务描述\n2. 子任务描述` | 加一行说明：`每行格式: 序号. 子任务描述 预计 X-Y 轮（或 预计 X 轮；无轮数行不采集偏差）` |
| discover.py `_create_est_card` L229 | `6. 拆分建议写 [SUB-SPLIT] comment（N serial|parallel + 子任务列表）` | 加 `（每行带 预计 X-Y 轮）` |
| discover.py est trigger SQL body L353-354 | 同上（SQL 字符串模板） | 同 discover L229 文案（三处文案一致，防 worker 困惑） |

---

## 4. E-2 est_deviation 表（pipeline_state.db）

### 4.1 schema（checkpoint.py SCHEMA_SQL 追加 + migration v4）

```sql
-- DPL-018 评估偏差反馈（Frank 2026-08-13 裁定）: 每子卡首次超时一条，重复超时 retry_count+1
CREATE TABLE IF NOT EXISTS est_deviation (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sub_task_id     TEXT NOT NULL UNIQUE,      -- 幂等: 每子卡一条（AC-4）
    est_card_id     TEXT NOT NULL,             -- 来源评估卡（子卡 body「评估卡 <id>」解析）
    spec_hash       TEXT,                       -- 链标识（dev-<hash>-*-sub-N 解析；独立卡 NULL）
    sub_idx         INTEGER,                    -- 子卡序号 1..N（body「子卡 i/N」）
    estimate_min    INTEGER NOT NULL,          -- 该子卡预估区间（[SUB-SPLIT] 每子卡字段）
    estimate_max    INTEGER NOT NULL,
    actual_rounds   INTEGER NOT NULL,          -- 超时实际轮数（error 解析；失败取 60）
    deviation_rate  REAL NOT NULL,             -- (actual - mid) / mid；mid=(min+max)/2
    outcome         TEXT NOT NULL,             -- timed_out / gave_up
    retry_count     INTEGER NOT NULL DEFAULT 0, -- 同子卡重复超时次数（首次=1）
    created_at      TEXT NOT NULL              -- UTC ISO（A8）
);
CREATE INDEX IF NOT EXISTS idx_est_dev_created ON est_deviation(id DESC);
```

- `checkpoint.py`：SCHEMA_SQL 追加上述 DDL；新增 `migrate_v3_to_v4`（仅记账 `PRAGMA user_version = 4`，表由 CREATE IF NOT EXISTS 幂等创建，仿 migrate_v2_to_v3 模式）；`ensure_schema()` 调用链加 `migrate_v3_to_v4`。
- **重要**：cmd_channel 采集段在 autopilot `ensure_schema()` 之前执行（§1.1 #10）→ `collect_est_deviations` 内部先 `CREATE TABLE IF NOT EXISTS`（自带兜底，幂等，fail-open）。

### 4.2 幂等与 fail-open

- `UNIQUE(sub_task_id)`：INSERT OR IGNORE → 已存在则 `UPDATE retry_count=retry_count+1`（AC-4 1→2）
- 表缺失/库缺失 → 采集跳过返回 0，不抛异常（AC-14）
- 游标 `est_calib_last_run_id` 存 project_config（key/value），与 `_get_skip_steps` 同表不同 key，无冲突

---

## 5. E-3 偏差采集（cmd_channel tick 段）

### 5.1 挂载点（cmd_channel.sh 新段 7，位于段 6 advance 之后、flock 释放前）

```bash
# ══════════════════════════════════════════════════════════════════════
# 7. 偏差采集（DPL-018 E-3）: task_runs 超时 → est_deviation（只读 kanban、只写 pipeline_state，fail-open）
# ══════════════════════════════════════════════════════════════════════
COLLECTED=$(python3 - "$KANBAN_DB" "$PIPELINE_DB" <<'PYEOF' 2>"$TMP_ERR"
import sys
sys.path.insert(0, "$REPO_ROOT")
from pipeline.calibration import collect_est_deviations, backfill_est_bodies
n = collect_est_deviations(sys.argv[1], sys.argv[2])
b = backfill_est_bodies(sys.argv[1], sys.argv[2])
print(f"collected={n} backfill={b}")
PYEOF
)
log_tmp_err "偏差采集"
[ -n "$COLLECTED" ] && log "偏差采集: $COLLECTED"
```

> 注：heredoc 内 `$REPO_ROOT` 由外层 shell 展开（与既有段 6 同款模式）。

### 5.2 `collect_est_deviations` 流程（伪代码）

```python
def collect_est_deviations(kanban_db: str, pipeline_db: str) -> int:
    try:
        _ensure_tables(pipeline_db)                      # CREATE IF NOT EXISTS est_deviation/project_config
        kconn = sqlite3.connect(f"file:{kanban_db}?mode=ro", uri=True)   # C2: 只读
        pconn = sqlite3.connect(pipeline_db)
        try:
            cursor = _read_cursor(pconn)                  # project_config['est_calib_last_run_id'] or None
            max_id = _max_run_id(kconn)                   # SELECT MAX(id) FROM task_runs
            if cursor is None:
                _write_cursor(pconn, max_id or 0)         # 首次: 初始化游标，不追溯历史（N6）
                return 0
            rows = kconn.execute(
                "SELECT id, task_id, status, outcome, error FROM task_runs "
                "WHERE id > ? AND status IN ('timed_out','gave_up') ORDER BY id",
                (cursor,),
            ).fetchall()
            processed = 0
            for r in rows:
                _collect_one(kconn, pconn, dict(r))       # 单行处理，内部跳过非子卡/无预估
                processed += 1
            _write_cursor(pconn, max(rows[-1]["id"], cursor) if rows else cursor)
            return processed
        finally:
            kconn.close(); pconn.close()
    except sqlite3.Error:
        return 0                                          # C3 fail-open
```

### 5.3 `_collect_one` 关键步骤

| 步骤 | 实现 | 失败处理 |
|------|------|---------|
| ① 读子卡 | `SELECT id,title,body,idempotency_key FROM tasks WHERE id=?` | 无 → skip |
| ② 子卡判定 | `idem LIKE 'dev-%-dev-sub-%' OR idem LIKE 'dev-%-qa-exec-sub-%' OR idem LIKE 'discover-sub-%' OR title LIKE '[DEV-SUB-%' OR title LIKE '[DEV-QA-SUB-%'` | 非子卡（[CMD] 等）→ skip（AC-5） |
| ③ spec_hash / sub_idx | idem `dev-<hash>-*-sub-<N>` → `_parse_dev_key` 取 hash + 尾段 N；`discover-sub-<src>-<N>` → spec_hash=None、N=尾段；body 正则 `子卡 (\d+)/(\d+)` 兜底 | 解析失败 → sub_idx=None → skip |
| ④ est_card_id | body 正则 `评估卡\s*([tT]_\w+)`（`_sub_card_body` 系统生成，可靠）；兜底 task_links 找 parent | 无 → skip（fail-open） |
| ⑤ 读预估 | `_read_sub_split(kanban_db_conn, est_card_id, 'SUB-SPLIT')`（qa 子卡用 'QA-SUB-SPLIT'，按 ② 判定）→ `split['estimates'][sub_idx-1]` | estimates 为 None 或该行 None（旧格式/无轮数）→ skip（E-1 语义：不采集不报错） |
| ⑥ 实际轮数 | error 正则 `Iteration budget exhausted\s*\((\d+)/` → X；失败取 60（max_turns） | — |
| ⑦ 偏差率 | `mid=(min+max)/2`；`rate=(actual-mid)/mid`；mid==0 → skip（防御） | — |
| ⑧ upsert | `INSERT OR IGNORE ... (retry_count=1)`；存在 → `UPDATE retry_count=retry_count+1`（AC-4） | — |

### 5.4 幂等与边界（AC-3/AC-4/AC-5/AC-14 全对齐）

- **重复 tick**：游标推进 → 已处理行不再扫描；未处理行（新超时）→ 幂等 upsert（AC-4）
- **同子卡再次超时**：新 task_runs 行（id > 游标）→ 命中 UNIQUE → retry_count+1（AC-4）
- **非子卡超时**（[CMD]/普通 dev 卡）：② 不匹配 → skip（AC-5）
- **无预估子卡超时**：⑤ estimates=None → skip（无基准不可比，E-1 fail-open）
- **表/库缺失**：外层 try → return 0（AC-14）
- **历史超时不追溯**：首次运行初始化游标（N6）

---

## 6. E-4 `calc_calibration_factor` 纯函数

```python
def calc_calibration_factor(records: list[dict], window: int = 10) -> tuple[float, float, bool]:
    """纯函数，无 IO，可单测。

    records: [{deviation_rate, outcome, sub_task_id}, ...]（按 id DESC 传入，即最新在前）
    window:  滚动窗口（默认 10，PRD §2.3）
    Returns: (factor, cum_rate, timeout_flag)
      - cum_rate: 窗口内 deviation_rate 中位数；样本 <3 → 均值；空 → 0
      - factor:   clamp(1 + cum_rate, 0.5, 3.0)（D2 定稿: 下限 0.5）
      - timeout_flag: 窗口内 outcome ∈ {timed_out,gave_up} 的**不同子卡** ≥ 2
    """
    recent = records[:window]
    if not recent:
        return (1.0, 0.0, False)
    rates = [r["deviation_rate"] for r in recent]
    if len(rates) < 3:
        cum = sum(rates) / len(rates)
    else:
        s = sorted(rates)
        mid = len(s) // 2
        cum = s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2
    factor = max(0.5, min(3.0, 1.0 + cum))
    timeout_subs = {r["sub_task_id"] for r in recent
                    if r.get("outcome") in ("timed_out", "gave_up")}
    timeout_flag = len(timeout_subs) >= 2
    return (round(factor, 4), round(cum, 4), timeout_flag)
```

**单测锚点（T60）**：
- 空记录 → `(1.0, 0.0, False)`（AC-7）
- 10 条全部 deviation_rate=+5 → cum=5（中位数）→ factor=6.0→clamp **3.0**；timeout_flag=True（AC-6）
- 10 条全部 −0.8 → cum=−0.8 → factor=0.2→clamp **0.5**（D2：允许温和下偏）
- 样本 2 条 [0.5, 1.5] → cum=1.0（均值退化）
- 样本 4 条 [0.5, 1.5, 2.0, 3.0] → cum=1.75（偶数中位数取中间两数均值）
- 窗口内 2 条超时但来自同一子卡（retry）→ timeout_flag=False（不同子卡 ≥2 才触发）
- 窗口内 2 条不同子卡超时 + 1 条下偏完成 → timeout_flag=True（混合窗口统计正确）

---

## 7. E-5 评估 prompt 注入

### 7.1 上下文构建（`build_calibration_context`）

```python
def build_calibration_context(pipeline_db: str) -> Optional[dict]:
    records = load_recent_records(pipeline_db, limit=10)   # 全局窗口（A5）
    if not records:
        return None                                        # AC-9: 无记录 → 段省略
    factor, cum_rate, timeout_flag = calc_calibration_factor(records)
    return {
        "records_5": records[:5],                          # 最近 5 条摘要
        "cum_rate": cum_rate,
        "factor": factor,
        "timeout_flag": timeout_flag,
        "window": 10,
    }
```

### 7.2 渲染（A6：横幅=body 首行；段=dev-est 块末尾）

```python
MARKER = "【历史偏差校准】"

def render_banner(ctx: dict) -> Optional[str]:
    if ctx.get("timeout_flag"):
        return "⚠️ 连续超时，必须校准（最近 10 条偏差中 ≥2 张不同子卡超时，DPL-018 自动检测）"
    return None

def render_calibration_section(ctx: dict) -> str:
    lines = [MARKER + "（DPL-018 自动注入）", "最近 5 条偏差记录:"]
    for r in ctx["records_5"]:
        lines.append(
            f"- 子卡 {r['sub_task_id']}: 预估 {r['estimate_min']}-{r['estimate_max']} 轮"
            f" / 实际 {r['actual_rounds']} 轮 / 偏差率 {r['deviation_rate']:+.2f}"
            f"（{r['outcome']}）"
        )
    lines += [
        f"累计偏差率: {ctx['cum_rate']:+.2f}（最近 {ctx['window']} 条中位数）",
        f"校准系数 K: {ctx['factor']:.2f}（clamp 0.5-3.0）",
        "校准建议: 预估轮数 = 基准 × (1 + 累计偏差率) = 基准 × K；"
        "例: 基准 10 轮 × K=1.5 → 校准 15 轮。请按校准后口径重新评估。",
    ]
    return "\n".join(lines)
```

### 7.3 三入口注入

| 入口 | 改动 | 说明 |
|------|------|------|
| ① cmd_chain `advance_sequential_chains` L1151-1159 | 建 dev-est 卡前：`calib = build_calibration_context(pipeline_db)`（仅 `step == "dev-est"` 时）；`_dev_card_body(..., calibration=calib)` | 链卡 dev-est 主入口；`_dev_card_body` 增可选参数 `calibration: Optional[dict] = None`，body 首行插 banner、dev-est 块末尾追加 section（A6） |
| ② discover `_create_est_card` L199-250 | 函数内 `calib = build_calibration_context(...)`（pipeline_db 用 `os.environ.get("PIPELINE_STATE_DB") or REPO_ROOT/pipeline_state.db`，与 cmd_chain `_pipeline_db_path` 同源）；est_body 首行插 banner、末尾追加 section | 独立卡 Python 入口（register_discovered_task L637 调用）；fail-open：build 失败 → calib=None → body 不含段 |
| ③ est trigger SQL（纯 SQL，无法跨库） | **不改触发器**；由 tick 段 `backfill_est_bodies` 兜底（A4） | SQL 触发器禁止 ATTACH pipeline_state.db；backfill 扫 ready est 卡补写 |

**`backfill_est_bodies` 实现锚点**：

```python
def backfill_est_bodies(kanban_db: str, pipeline_db: str) -> int:
    """扫描 ready 态 est 卡（discover-est-*/discover-qa-est-*/dev-%-dev-est），
    body 无 MARKER 且 est_deviation 有数据 → 补 banner + section（UPDATE tasks SET body）。
    幂等: MARKER 存在即跳过。fail-open: 任何异常返回 0。"""
    try:
        ctx = build_calibration_context(pipeline_db)
        if not ctx:
            return 0                                        # 无数据 → 无段可补
        conn = sqlite3.connect(kanban_db)
        try:
            rows = conn.execute(
                "SELECT id, body FROM tasks WHERE status='ready' AND ("
                " idempotency_key LIKE 'discover-est-%' OR idempotency_key LIKE 'discover-qa-est-%'"
                " OR idempotency_key LIKE 'dev-%-dev-est')"
            ).fetchall()
            n = 0
            for tid, body in rows:
                if MARKER in (body or ""):
                    continue
                new_body = body or ""
                if render_banner(ctx):
                    new_body = render_banner(ctx) + "\n" + new_body     # 横幅首行（A6）
                new_body += "\n" + render_calibration_section(ctx)
                conn.execute("UPDATE tasks SET body=? WHERE id=?", (new_body, tid))
                n += 1
            conn.commit()
            return n
        finally:
            conn.close()
    except sqlite3.Error:
        return 0
```

---

## 8. E-6 子卡 body 校准注入

### 8.1 `_sub_card_body` 扩展（cmd_chain.py L630-662）

```python
def _sub_card_body(topic, i, total, desc, parent_id, kind, ctx=None,
                   calibrated_rounds: Optional[int] = None) -> str:
    ...
    if calibrated_rounds is not None:
        lines.append(f"预估轮数（含校准）: {calibrated_rounds} 轮")   # 追加在链上下文之后
    return "\n".join(lines)
```

### 8.2 `_create_dev_sub_cards` / `_create_qa_sub_cards` 注入（A5/A7）

```python
# 模块级导入（A1 无循环）:
from pipeline.calibration import calibrated_rounds

# 建卡循环内（_create_dev_sub_cards L687-706 / _create_qa_sub_cards L726-744 同款）:
calib_n = None
estimates = split.get("estimates")
if estimates and i - 1 < len(estimates) and estimates[i - 1] is not None:
    calib_n = calibrated_rounds(_pipeline_db_path(), spec_hash, est_id, estimates[i - 1])
body = _sub_card_body(topic, i, count, desc, parent_id, kind, ctx,
                      calibrated_rounds=calib_n)
```

**`calibrated_rounds` 实现锚点**：

```python
def calibrated_rounds(pipeline_db, spec_hash, est_card_id, estimate) -> Optional[int]:
    """E-6: 该 spec_hash（链卡）或 est_card_id（独立卡）有 est_deviation 记录 →
    校准后预估 = round(mid × K)；无记录 → None（不加行，T27/T28 不回归）。"""
    try:
        conn = sqlite3.connect(f"file:{pipeline_db}?mode=ro", uri=True)
        try:
            if spec_hash:
                rows = conn.execute(
                    "SELECT deviation_rate, outcome, sub_task_id FROM est_deviation "
                    "WHERE spec_hash=? ORDER BY id DESC LIMIT 10", (spec_hash,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT deviation_rate, outcome, sub_task_id FROM est_deviation "
                    "WHERE est_card_id=? ORDER BY id DESC LIMIT 10", (est_card_id,)).fetchall()
            if not rows:
                return None
            factor, _, _ = calc_calibration_factor([dict(r) for r in rows])
            mid = (estimate["min"] + estimate["max"]) / 2
            return int(round(mid * factor))          # AC-11: mid=9 × K=1.5 → round(13.5)=14
        finally:
            conn.close()
    except sqlite3.Error:
        return None
```

**AC-11 验算**：est_deviation 有记录（中位数 +50% → K=1.5）；[SUB-SPLIT] 预估 8-10（mid=9）→ `round(9×1.5)=round(13.5)=14` → body 含 `预估轮数（含校准）: 14 轮` ✓
**AC-12**：est_deviation 空 → calibrated_rounds=None → 子卡 body 无校准行（与现有一致，T27/T28 回归）✓

---

## 9. E-7 测试计划（test_cmd_channel.sh，新增 T59-T69）

> 编号从 T59 起（存量到 T58，A9）。沿用既有 harness：隔离 temp kanban.db + temp pipe.db + 隔离 flock。

| # | 用例 | 断言要点 |
|---|------|---------|
| T59 | `_parse_sub_split` estimates 解析扩展 | 区间/单值/缺省/混杂/X>Y 交换/`预计 ≤20 轮` 不匹配/titles 对齐（AC-1/AC-2）→ 6-8 断言 |
| T60 | `calc_calibration_factor` 纯函数 | 空→(1.0,0,False)；全+5→3.0+flag；全−0.8→0.5；样本2 均值退化；偶数中位数；同子卡不触发 flag（AC-6/AC-7/D2）→ 6 断言 |
| T61 | `collect_est_deviations` 落库 | 构造 task_runs timed_out 行（error 含 Iteration budget exhausted (60/60)）+ 子卡 body（评估卡 id + 子卡 i/N）+ est [SUB-SPLIT] 预估 8-10 → est_deviation 行 est=8-10/actual=60/rate≈5.67/outcome=timed_out（AC-3）→ 5 断言 |
| T62 | 采集幂等 | 同 tick 重复调用不重复建行；同子卡二次超时（新 task_runs 行）→ retry_count 1→2（AC-4）→ 3 断言 |
| T63 | 非子卡超时忽略 | [CMD] 卡 timed_out → 无 est_deviation 行（AC-5）→ 1 断言 |
| T64 | 链卡 prompt 注入 | est_deviation 3 条 → `advance_sequential_chains` 建 dev-est 卡 body 含「历史偏差校准」/累计偏差率/K/建议公式；空 → body 不含段（AC-8/AC-9）→ 4 断言 |
| T65 | 独立卡 prompt 注入 + backfill | `_create_est_card`（PIPELINE_STATE_DB 指向 temp pipe）body 含校准段；模拟 trigger 建的 ready est 卡无段 → `backfill_est_bodies` 补写且幂等（A4）→ 4 断言 |
| T66 | ⚠️ 横幅 | timeout_flag=True 构造 → body 首行含「⚠️ 连续超时」；False → 无横幅（AC-10）→ 2 断言 |
| T67 | 子卡 body 校准注入 | est_deviation 中位数 +50% → `_create_dev_sub_cards` 子卡 body 含「预估轮数（含校准）: 14 轮」（AC-11）→ 2 断言 |
| T68 | 子卡无数据不注入 + 阈值不变 | est_deviation 空 → 子卡 body 无校准行（AC-12）；`EST_SPLIT_THRESHOLD_ROUNDS==20` 断言（AC-13）；pipe.db 缺失 → collect 返回 0 不抛（AC-14）→ 4 断言 |
| T69 | 回归 | T1-T58 全绿 + T31 扩展断言不破坏（AC-15）→ 全量 |

**新增断言合计 ≥28**（PRD E-7 要求 ≥15，超配）。跑测时间：单次全量 test_cmd_channel.sh 现有 2-5 min，新增用例全部内存/临时库操作，预计 <6 min（PRD 约束）。

---

## 10. 待 Frank 裁决 D1/D2 定稿（架构建议）

| # | 点 | PRD 建议 | 架构定稿建议 | 理由 |
|---|-----|---------|-------------|------|
| D1 | 完成卡是否采集偏差（P1 E-8） | P0 只做超时反馈，E-8 排 P1 | **采纳 P0 只做超时反馈** | 超时 error 是唯一可靠轮数信号（内核写死）；完成卡精确轮数需 [CLAIM] 加 `轮数: N` 字段（跨 SOUL.md/worker 行为约定），且 E-8 上线前超时率趋势未知——先验证 P0 闭环是否把超时率压下来，再决定是否值得为完成卡加采集成本。**P0 架构已为 E-8 预留**：est_deviation.actual_rounds 字段通用，E-8 只是「额外数据源 + 去除 outcome 过滤」，无 schema 变更 |
| D2 | 校准系数是否允许 <1（下偏） | clamp 下限 0.5 | **采纳 clamp [0.5, 3.0]** | 允许温和下偏（评估高估时 K<1 让拆卡更不积极 → 更多单卡硬跑 → 反而不拆 = 更少子卡 = 更低超时面；这是期望方向）；但 0.5 封底防「系数无限放宽 → 拆卡阈值形同虚设」。激进下偏（实际 < 预估一半）是评估模型重大失准，应由评估卡重新审视，不由系数机械兜底（C4：校准不机械改拆法） |

---

## 11. 工时估算

| 模块 | 文件 | 工时 |
|------|------|:---:|
| E-1 [SUB-SPLIT] 解析扩展 + prompt 格式说明（3 处） | cmd_chain.py + discover.py（含 trigger SQL 文案） | 1.5h |
| E-2 est_deviation 表 + migration v4 + 采集段表兜底 | checkpoint.py + calibration.py | 0.5h |
| E-3 偏差采集（游标 + 匹配 + upsert + 段挂载） | calibration.py + cmd_channel.sh | 2h |
| E-4 calc_calibration_factor 纯函数 | calibration.py | 1h |
| E-5 prompt 注入（双入口 + backfill，A4 增量） | calibration.py + cmd_chain.py + discover.py | 2h（PRD 1.5h + 0.5h backfill） |
| E-6 子卡 body 校准注入（dev + qa） | cmd_chain.py + calibration.py | 1h |
| E-7 测试（T59-T69 + T31 扩展 + 回归） | test_cmd_channel.sh | 1.5h |
| **P0 合计** | | **9.5h**（PRD 9h + 0.5h A4 增量，已向 OC 说明） |
| P1 E-8 完成卡轮数采集 | calibration.py + worker claim 约定 | 2h |
| P1 E-9 机械自适应提示 | cmd_chain.py | 1h |
| P1 E-10 偏差看板 | notify_check.py | 1.5h |
| **P0+P1 合计** | | **14h** |

---

## 12. 交付物与 commit 计划

| 交付物 | 路径 | 状态 |
|--------|------|------|
| 本架构设计 | `docs/arch/arch-estimate-calibration.md` | ✅ 本文档 |
| 实现（后续 OC 派发） | `pipeline/calibration.py`（新）+ `pipeline/cmd_chain.py` + `pipeline/discover.py` + `pipeline/checkpoint.py` + `pipeline/constants.py`（零改动，仅回归验证）+ `scripts/cmd_channel.sh` + `scripts/test_cmd_channel.sh` | 待派发 |
| 数据（运行时） | `pipeline_state.db` 新表 est_deviation + project_config 游标 | 待实现 |

**commit**：`docs(arch): 评估算法校准机制 DPL-018 — 子卡超时→预估偏差反馈→自适应（[SUB-SPLIT] 结构化预估/est_deviation 偏差采集/校准系数 K/prompt 双入口注入+trigger backfill/子卡 body 校准注入，验收 AC-1~AC-15）`

**拆卡建议（报 OC，不自建卡——建卡铁律）**：
- P0 实现卡：assignee=game-engine，body 指向本架构 §2-§9 + PRD t_8db323af，工时 9.5h
- P1 增强卡（E-8/E-9/E-10）：assignee=game-engine，可拆 2 张（E-8 独立卡 + E-9/E-10 合并卡），待 P0 上线后按超时率趋势排期

---

## 附：与本设计相关的既有文档

- PRD：`docs/prd/estimate-calibration-prd.md`（t_8db323af，commit 33bef7a，245 行）
- 拆卡机制设计：`docs/design/estimate-split-cards.md`（Frank 2026-08-12 提出）
- 智能跳步设计：`docs/design/smart-skip-steps.md`（t_7b2781ec）
- 独立 dev 卡拆卡保障：`docs/arch/arch-fix-standalone-dev-subsplit.md`（DPL-020）
- 编号链 v4：`docs/arch/arch-card-numbering-chain-v4.md`（t_84884feb）
- 超时实证：t_15a3982c（拆后仍 60/60 ×2）、t_40ec4bde（未拆硬跑 60/60 ×2）
- task_runs 超时消费先例：`scripts/notify_check.py` L1147-1157（ever_timed_out）
- 早期 PRD 草案（v4，供参考）：`docs/prd/est-calibration-loop-prd.md`（commit 68f29e7，未合 main，本 PRD 为准）
