# 架构设计 — FIX notify heartbeat 统计范围限定到当前开发链

> 作者：高见远（架构师） | 日期：2026-08-11 | 版本：v1.0
> 议题：[DEV-ARCH] FIX notify heartbeat 统计范围限定到当前开发链（不统计全局历史）
> 上游：docs/prd/fix-notify-heartbeat-chain-scope-prd.md（v1.0，许清楚）
> 前置：B1 通知 cron（已交付）+ B1-F1（已交付）+ B3 指令卡通道（已交付）
> 本设计可直接落地：工程师按 §5 接口定义实现，按 §6 验收。

---

## 1. 结论（TL;DR）

**根因确认**：`notify_check.py` 的 heartbeat 数字统计源是 `pipeline_steps` 全表（全局历史），而当前开发链卡（`[DEV-*]` + `dev-<hash>-<step>` 幂等键）按 R2 四道闸设计**永不注册**进 pipeline_steps。两条信息源完全脱节 → 开发链在跑时 heartbeat 报 `活跃0 跑0 堵0`、甚至判 IDLE 静默。PRD 判定 MAJOR 成立，与真实数据核对一致（当前 pipeline_steps 仅 3 条 done 历史行，而 board 有 2 条 running 开发链）。

**方案一句话**：heartbeat 统计源从「pipeline_steps 全表」切换为「kanban 当前开发链卡」（`idempotency_key LIKE 'dev-%'`），保留 pipeline/[CMD] 作为 ACTIVE 判定来源与无开发链时的自动回退；配置 `heartbeat.stats_scope` 做逃生阀。

**改动面**：仅 `scripts/notify_check.py` + `config/notify.json` + `scripts/test_notify_check.py`。autopilot / cmd_channel / discover / cmd_chain / constants **零改动**（PRD 约束 N3 + R2 四道闸不回退）。

**工期**：P0 约 4.5h（含测试），P1 约 1.5h，合计 6h（与 PRD §8 的 6.5h 基本一致，见 §7）。

---

## 2. 现状梳理与缺陷确认（实测核对）

### 2.1 当前数据流

```
pipeline_state.db (ro)              kanban.db (ro)                notify_state.db (rw)
  pipeline_steps 全表                  tasks                          notify_events / pipeline_snapshot / kv_store
      │  read_pipeline_steps()            │ read_cmd_cards()               ▲
      ▼                                   ▼                               │
  ┌──────────────────────────── run_tick() ───────────────────────────────┘
  │ cleanup → load_snapshot → diff_states → save_snapshot
  │ is_active(steps, cmd_cards)        → work_state（work-gated）
  │ compute_counts(steps)              → 活跃N/跑N/堵N/今完N
  │ emit: exception / milestone(边界) / heartbeat(附注)
  └────────────────────────────────────────────────────────────────────
```

### 2.2 实测确认的缺陷（2026-08-11 现场数据）

| 项 | 实测 | 结论 |
|----|------|------|
| pipeline_steps 现状 | 仅 3 条，全部 `done`（全局历史，无活跃） | 数字源已与真实工作脱节 |
| board 开发链现状 | `t_f86c3398 [DEV-PRD]` done（今日 13:38）、`t_0c41ef06 [DEV-ARCH]` running、`t_daff6195 [DEV-ARCH]` running、`t_e1d81053 [DEV-PRD]` done（今日 13:21） | 当前应报 `活跃2 跑2 堵0 今完2` |
| 旧逻辑输出 | 活跃0 跑0 堵0 今完0（且若 [CMD] 卡已消费，ACTIVE 判定也会失效） | 信号失真确认 |

### 2.3 关键事实（设计依据，工程师勿偏离）

- **kanban `tasks` 表**：`idempotency_key TEXT`、`completed_at INTEGER`（unix epoch 秒，非 TEXT）、`status` 枚举含 `todo/ready/running/blocked/done/archived/cancelled/triage`。
- **链卡幂等键格式**：`dev-<spec_hash>-<step>`（恰好 3 段），step ∈ {prd, arch, dev}（`DEVELOPMENT_CHAIN`）。
- **链卡生命周期**：创建即无 parents → `ready` → `running` → `done`（终态保留，不自动归档）；`abort` 会直接置 `archived`。链卡正常完成**不会**被归档。
- **completed_at 语义**：kernel 在置 `done` 时写 unix epoch。今日完成判定必须用「本地时区今日零点」的 epoch 比较（PRD C6），不能用 TEXT 字符串比较。
- **现有 `read_cmd_cards` 已含 `[DEV-%`**（提交 7640aa8 的过渡补丁）：只返回数量、无状态明细、`NOT IN ('done','archived')` 会误计 cancelled/todo。本设计将其职责收窄回 `[CMD]` 专用，开发链改由 `read_dev_chain_cards` 精确读取。

---

## 3. 架构决策（ADR）

### ADR-1：链卡识别口径 = 幂等键 + 标题双过滤

```sql
SELECT id, title, status, completed_at, idempotency_key
FROM tasks
WHERE idempotency_key LIKE 'dev-%'
  AND title LIKE '[DEV-%'
  AND status != 'archived'
```

- 与 `cmd_chain.advance_sequential_chains` 的扫描口径一致（`dev-%` + `[DEV-%`），避免误纳入手工建的 `dev-*` 键卡。
- `status != 'archived'`：**归档即退出统计**（PRD §2.3）。归档卡从源消失后，diff 只遍历 cur（不遍历 prev），不会产生归档迁移噪音。
- **fail-open**：kanban.db 缺失 / tasks 表缺失 / 列缺失（如旧测试 fixture 无 `idempotency_key` 列）→ 捕获 `sqlite3.Error` 返回 `[]`（AC-7）。
- 明确**不做**：不把 `[ROUNDTABLE-*]` 计入统计数字（PRD N6 + §7 D1 待裁决，见 §8）。

### ADR-2：统计口径切换 + 无开发链自动回退（关键决策）

`stats_scope="chain"`（新默认）时，**不是**无条件用链卡数字，而是：

```
chain_relevant(dev_cards) =
    ∃ 卡 status ∈ (ready, running, blocked)          -- 在途
    ∨ ∃ 卡 status = done AND completed_at ≥ 本地今日零点  -- 今日完成
```

- `chain_relevant = True` → 数字来自链卡（`compute_chain_counts`）。
- `chain_relevant = False`（无开发链 / 链全部 done 且非今日 / 全部归档）→ **自动回退** legacy 数字（`compute_pipeline_counts`）。

理由：
1. **PRD AC-6 明确要求**：无 `dev-*` 链卡时保持原行为（数字来自 pipeline）。若不回退，纯 legacy 活跃时 heartbeat 会报 `活跃0` 但 ACTIVE=true——比现在更误导。
2. 链全部 done 但**非今日**（昨天完成）时，`今完0` 且无在途 → 回退 legacy，避免「活跃0」与真实工作（若 legacy 有活）矛盾。
3. 链全部 done **今日** → 不回退（`done_today` 卡满足 relevant 第二项），空闲边界消息能报出「今日完N」，符合 AC-5。

`stats_scope="legacy"`（逃生阀）→ 无条件走旧逻辑：数字来自 pipeline，ACTIVE 按旧口径（见 ADR-3）。

### ADR-3：ACTIVE 判定来源拆分（F-3）

```
is_active(steps, cmd_cards, dev_cards, scope):
    pipeline_active = ∃ step.status ∈ (pending, running, blocked)      -- 不变
    cmd_active      = read_cmd_cards(kanban_db) > 0                    -- [CMD] 未归档，不变
    dev_active      = scope=="chain"
                          ? ∃ card.status ∈ (ready, running, blocked)  -- 精确在途
                          : ∃ card.status NOT IN ('done','archived')   -- 旧口径（含 todo/cancelled）
    return pipeline_active or cmd_active or dev_active
```

- 链卡 `blocked` 计入 ACTIVE（堵了也要让 Frank 知道系统还活着），但**不计入 活跃N**（活跃N=ready+running，与旧 pipeline 语义一致：堵是单独维度）。
- `read_cmd_cards` 收窄为只查 `[CMD] %`（原 `[DEV-%` 分支由 dev_cards 取代）。

### ADR-4：时间基准统一为本地时区（PRD C6）

- kanban `completed_at`（unix epoch）→ 与「配置 timezone 今日零点」的 epoch 比较。
- pipeline `finished_at`（TEXT，实测格式 `2026-08-11T04:31:10Z`，测试用 `2026-08-11T01:00:00Z`；SQLite `datetime('now')` 是 `YYYY-MM-DD HH:MM:SS`）→ 统一走 `_to_epoch()` 辅助函数转 epoch 再比较。
- 这同时修掉一个隐藏坑：混合格式下字符串比较会漏计（`'2026-08-11 01:00:00' < '2026-08-11T00:00:00Z'` 字典序错误）。
- legacy 的 `今完N` 也从 UTC 零点改为本地零点（口径一致，C6 要求；存量 T1/T2 不断言 done_today 数值，不回归）。

### ADR-5：P1 链卡迁移只进 heartbeat 附注（专用 diff，不污染 milestone）

- 链卡状态迁移**不作为 milestone 推送**（不推 `✅ t_x prd done`）。理由：(a) PRD F-7 明示走附注；(b) 避免与 heartbeat 数字（今完N）双重刷屏；(c) milestone 路径保持 pipeline-only，零回归。
- 实现：`diff_states()` 复用，但链卡事件统一 `event_type = "heartbeat_annex"`。
- 附注文案天然可读：`t_f86c3398 prd running` / `t_f86c3398 prd done`（step_name 取自幂等键第 3 段，而非字面 'card'）。
- 冷却沿用现有 `event_cooldown_min`（30min）；顺手启用已存在的死配置 `heartbeat.annex_cooldown_min`（见 §4 微修）。

### ADR-6：fail-open 与只读约束不放松

- 所有新增读函数走 `mode=ro` URI + `try/except sqlite3.Error` → 空结果。
- notify_state.db 是唯一写库；pipeline_state.db / kanban.db 只读（C2/C3）。
- 异常不阻塞、不重试循环、退出码 0（`main()` 已保证）。

### ADR-7：cleanup 保留集扩展（F-8）

```
keep = {s.task_id for s in steps}            -- 现状：pipeline_steps 出现的所有 task（含 done）
     ∪ {c.task_id for c in dev_cards}        -- 新增：非 archived 开发链卡
DELETE FROM pipeline_snapshot WHERE task_id NOT IN (keep)   -- 其余立即删
```

- 对 pipeline 语义**零改变**（现状即「不在 steps 的 task 快照立即删」）。
- 归档链卡的快照立即删（终态，无 diff 价值，卡也不会复活）——比 PRD F-8 的「7 天窗口」更简；若评审坚持字面 7 天，仅需加 `AND updated_at < datetime('now','-7 days')` 一行，标注为可选项。
- `notify_events` 7 天清理不变。

---

## 4. 模块划分与接口定义（工程师直接照此实现）

### 4.1 改动文件清单

| 文件 | 改动 |
|------|------|
| `scripts/notify_check.py` | 新增 4 函数 + 改 3 函数 + run_tick 接线 |
| `config/notify.json` | `heartbeat` 段加 `"stats_scope": "chain"` |
| `scripts/test_notify_check.py` | fixture 扩 schema + 新增 T11-T17 |

**零改动**：autopilot.sh / notify_cron.sh / cmd_channel.sh / discover.py / cmd_chain.py / constants.py。

### 4.2 新增函数

```python
def read_dev_chain_cards(kanban_db: str) -> list[dict]:
    """F-1 读取当前开发链卡（fail-open）。

    SQL: SELECT id, title, status, completed_at, idempotency_key
         FROM tasks
         WHERE idempotency_key LIKE 'dev-%' AND title LIKE '[DEV-%'
           AND status != 'archived' ORDER BY created_at
    返回 [{task_id, title, status, step_name, completed_at}]
      - step_name: 幂等键第 3 段（key.split('-') 长度 != 3 的卡跳过）
      - completed_at: int epoch 或 None
    异常（缺库/缺表/缺列）→ []
    """

def compute_chain_counts(dev_cards: list[dict]) -> dict:
    """F-2 链卡口径数字。
    活跃N = COUNT(status in (ready, running))
    跑N   = COUNT(status == running)
    堵N   = COUNT(status == blocked)
    今完N = COUNT(status == done AND completed_at >= local_today_start_epoch)
    """

def chain_relevant(dev_cards: list[dict]) -> bool:
    """ADR-2 自动回退判定。
    在途卡(ready/running/blocked) 或 今日完成卡(done & completed_at >= 本地今日零点)。
    """

def _to_epoch(value) -> int | None:
    """ADR-4 时间归一化：int epoch 原样返回；ISO '...Z' → epoch；
    'YYYY-MM-DD HH:MM:SS'（SQLite now 格式）→ 按 UTC 解析 → epoch。
    解析失败 → None。"""
```

### 4.3 修改函数

```python
def read_cmd_cards(kanban_db: str) -> int:
    """收窄：只统计未归档 [CMD] 卡（原 [DEV-% 分支删除，由 read_dev_chain_cards 取代）。"""

def is_active(steps: list[dict], cmd_cards: int, dev_cards: list[dict],
              scope: str = "chain") -> bool:
    """F-3 见 ADR-3。scope=="chain" 用精确在途集；scope=="legacy" 用 NOT IN (done,archived)。"""

def compute_counts(steps: list[dict], dev_cards: list[dict] | None = None,
                   scope: str = "chain") -> dict:
    """F-2 总入口：scope=="chain" and chain_relevant(dev_cards) → compute_chain_counts
    否则 → 旧逻辑（compute_pipeline_counts，今完N 改用 _to_epoch + 本地零点比较）。"""

def cleanup(conn, retention_days: int, steps: list[dict],
            dev_cards: list[dict] | None = None) -> None:
    """F-8 保留集 = steps task_ids ∪ 非 archived 链卡 ids（ADR-7）。"""

def diff_states(prev: dict, cur_steps: list[dict]) -> list[dict]:
    """不改签名。链卡伪步骤喂入后，调用方负责把返回事件的 event_type 统一覆写为
    'heartbeat_annex'（ADR-5）。"""

def run_tick(cfg, state_db, notify_db, kanban_db, dry_run=False) -> None:
    """接线（见 4.4 数据流）。scope = (cfg.get("heartbeat") or {}).get("stats_scope", "chain")。"""
```

### 4.4 修改后 run_tick 数据流（P0 + P1 合并）

```
1. steps      = read_pipeline_steps(state_db)          # 不变
2. cmd_cards  = read_cmd_cards(kanban_db)              # 收窄为 [CMD]
3. dev_cards  = read_dev_chain_cards(kanban_db)        # 新增（F-1）
4. cleanup(conn, retention, steps, dev_cards)          # F-8
5. prev       = load_snapshot(conn)
   first_run  = kv_get('initialized') is None
6. chain_steps = [{task_id, step_name=step_name, status, error_msg:''} for c in dev_cards]   # P1
7. events     = diff_states(prev, steps) if not first_run else []
   chain_evs  = diff_states(prev, chain_steps) if not first_run else []
   for ev in chain_evs: ev["event_type"] = "heartbeat_annex"       # ADR-5
   events    += chain_evs
8. save_snapshot(conn, steps + chain_steps)
9. scope      = heartbeat.stats_scope or "chain"
   active     = is_active(steps, cmd_cards, dev_cards, scope)      # F-3
10. counts    = compute_counts(steps, dev_cards, scope)            # F-2（含自动回退）
11. 原 emit 三路径（exception / milestone+边界 / heartbeat+附注）不变，直接用新 counts
```

边界消息（F-4）无需新代码：`🟢 开工` / `⚪ 空闲` 已引用 `counts`，换源即生效。

### 4.5 配置变更（F-5）

```json
{
  "heartbeat": {
    "enabled": true,
    "silent_window": null,
    "annex_cooldown_min": 30,
    "stats_scope": "chain"
  }
}
```

- `stats_scope` 缺省 → `"chain"`（新口径）；显式 `"legacy"` 一键回退。
- 微修：heartbeat 附注冷却从 `event_cooldown_min` 改为 `annex_cooldown_min`（该配置键当前是死配置，未读；改动一行，语义对齐）。

### 4.6 输出格式（AC-8）

`format_heartbeat` / `format_annex_item` **不改**。`[AP HH:MM] 活跃N 跑N 堵N 今完N | t_x prd running, ...`，≤80 字。

---

## 5. 测试方案（F-6，T11+）

### 5.1 fixture 改造

`Fixture.seed_kanban_cmd` 的 CREATE TABLE 升级为含 `idempotency_key TEXT`、`completed_at INTEGER`、`started_at INTEGER` 的完整 tasks 表（CREATE TABLE IF NOT EXISTS 首建即全 schema）。新增：

```python
def seed_kanban_dev_chain(self, cards: list[dict]):
    """cards: [{id, step, status, completed_at_epoch?}] → 写 [DEV-<STEP>] t_xxx + dev-<hash>-<step> 键"""
def today_start_epoch(self) -> int:
    """本地时区（cfg timezone）今日零点 epoch，构造"今日完成"fixture 用"""
```

### 5.2 新增用例

| # | 场景 | 断言 |
|---|------|------|
| T11 | 1 张 running 链卡（无 pipeline 活跃） | ACTIVE + heartbeat `活跃1 跑1 堵0 今完0` |
| T12 | prd done(今日) + arch running + dev ready | `活跃2 跑1 堵0 今完1`（AC-2） |
| T13 | 链卡 archived | 不计活跃/跑/堵/今完；全归档 → IDLE（AC-4） |
| T14 | 无 dev 卡，仅 pipeline 活跃步骤 | 回退 legacy：数字来自 pipeline（AC-6） |
| T15 | 有 dev 卡 + `stats_scope=legacy` | 数字仍来自 pipeline（逃生阀） |
| T16 | dev 卡 running→done 迁移（P1） | 附注含 `t_x prd done`，不推 `✅` milestone；30min 冷却生效 |
| T17 | 链全 done 且非今日 + pipeline 无活跃 | `chain_relevant=False` → IDLE 静默（边界正确） |
| T18 | 旧 fixture 无 `idempotency_key` 列（fail-open 回归） | 不抛异常，视为无链卡（AC-7） |

### 5.3 存量回归

T1-T10 不 seed dev 卡 → `dev_cards=[]` → `chain_relevant=False` → 自动回退 legacy → 行为不变。T7（[CMD] 卡 ACTIVE）依赖 `read_cmd_cards` 收窄后仍只查 `[CMD]` → 绿。T5-2（缺 kanban.db）→ `read_dev_chain_cards` 返回 `[]` → 绿。

---

## 6. 验收对照（PRD §5.2）

| AC | 实现落点 |
|----|---------|
| AC-1 在途链卡 → ACTIVE + 数字正确 | ADR-3 + compute_chain_counts + T11 |
| AC-2 多棒在途 | compute_chain_counts（今完N 含今日 done） + T12 |
| AC-3 全局历史不统计 | 数字源切换（chain_relevant 时） + T12/T14 |
| AC-4 归档退出统计 | read_dev_chain_cards `status != 'archived'` + T13 |
| AC-5 完成自动停 | chain_relevant 无在途+无今日 done → 空闲边界 + T17 |
| AC-6 纯 legacy 不回归 | 自动回退 + stats_scope=legacy + T14/T15 |
| AC-7 fail-open | 全部读函数 except sqlite3.Error → [] + T18 |
| AC-8 格式不变 | format_heartbeat 不改 + T7-2 已覆盖 |

---

## 7. 工期影响

| 模块 | 估算 | 说明 |
|------|:---:|------|
| F-1/F-2 读链卡 + 口径切换 + 自动回退 | 1.5h | 核心，含 `_to_epoch` |
| F-3/F-4 ACTIVE + 边界 | 0.5h | is_active 拆分支 + run_tick 接线 |
| F-5 配置 + 微修 | 0.5h | stats_scope + annex_cooldown |
| F-6 测试（fixture + T11-T18） | 2h | fixture 升级占大头 |
| P0 小计 | **4.5h** | |
| F-7/F-8 P1 附注 | 1.5h | diff 复用，改动小 |
| **合计** | **6h** | PRD §8 估 6.5h，差值在 fixture 复用 |

无架构性风险点；唯一外部依赖是 §8 D1 裁决（不阻塞 P0）。

---

## 8. 待 Frank 裁决（1 项，不阻塞 P0）

**D1：[ROUNDTABLE-*] 在途卡是否计入 ACTIVE？**

- PRD §7 建议计入（roundtable 进行中心跳不应静默）。架构上已留好扩展点：`is_active` 的 dev_active 分支是独立来源，加 roundtable 只需新增 `read_roundtable_cards`（`title LIKE '[ROUNDTABLE-%' AND status IN ('ready','running','blocked')`）+ 一行 or 分支，约 0.5h。
- **统计数字仍只含 dev-* 链卡**（口径纯净，PRD 明确）。
- P0 默认不含；Frank 裁定后 0.5h 内可加，不改本设计主体。

---

## 9. 风险登记

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 旧环境 tasks 表缺 idempotency_key 列 | fail-open → []（ADR-1 + T18） |
| R2 | 自动回退边界（链 done 非今日）语义争议 | ADR-2 明确 chain_relevant 规则 + T17 |
| R3 | 链卡 done 误入 milestone 刷屏 | ADR-5 强制 annex-only + T16 断言无 `✅` |
| R4 | 时区/epoch 换算错误 | ADR-4 `_to_epoch` 单点 + 今日零点 epoch 测试构造 |
| R5 | read_cmd_cards 收窄破坏 [DEV-] ACTIVE | 由 read_dev_chain_cards 精确接管，T7/T11 双覆盖 |

---

## 10. 交付物

| 交付物 | 路径 |
|--------|------|
| 本架构设计 | `docs/arch-fix-notify-heartbeat-chain-scope.md` |
| （下一棒）实现 | `scripts/notify_check.py` + `config/notify.json` + `scripts/test_notify_check.py` |

## 附：引用文档

- PRD：`docs/prd/fix-notify-heartbeat-chain-scope-prd.md`
- B1 验收：`docs/qa/notify-cron-smoke-verification.md`
- R2 裁定落地：`docs/roundtables/b-autopilot-oc-relationship/2026-08-11-r2-rulings-design.md`
- discover 排除集：`pipeline/discover.py`（SUB_TASK_TITLE_PREFIXES L40-54）
- 建链：`pipeline/cmd_chain.py`（advance_sequential_chains L254-321）、`pipeline/constants.py`（DEVELOPMENT_CHAIN L68-72）
