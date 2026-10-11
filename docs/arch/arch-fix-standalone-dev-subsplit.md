# FIX 独立 dev 卡拆卡保障 — 架构设计（discover 层检查 [SUB-SPLIT] 自动建子卡）

> 发言人：高见远（架构师） | 日期：2026-08-13 | 版本：v1.0
> 输入：PRD v1.0（docs/prd/fix-standalone-dev-subsplit-prd.md，commit 1fe7a08）+ 现状代码核查（discover.py / cmd_chain.py / state.py / autopilot.sh / test_cmd_channel.sh）+ **hermes 内核源码核查**（kanban_db.py：recompute_ready L3303 / claim_task L3394 / complete_task L4000 / block_task L4563 / release_stale_claims L3622 / _has_sticky_block L3265）
> 定位：6 步闭环 Step 2 架构落地 —— 把 PRD F-1..F-9 + 待裁决 D1..D4 细化为文件/函数/数据流级实现方案，工程师可直接照写代码
> 核心原则：**拆卡裁决是系统决策，不是 worker 自觉。独立 dev 卡与链卡享受同一道 autopilot 拆卡保障——评估卡 [SUB-SPLIT] N>1 的裁决，在源卡被 dispatcher claim 之前由触发器同步按住，由 autopilot Python 层建 N 张子卡、按住源卡直到子卡全部完成。**

---

## 0. 范围与裁决总表

### 0.1 本设计做什么（PRD F-1..F-9 全覆盖 + 待裁决 D1..D4 定稿）

| # | PRD 需求 / 待裁决 | 本设计章节 | 状态 |
|---|---------|-----------|------|
| 1 | F-1 拆卡裁决检测（discover 层扫描独立 dev 卡 + 读 [SUB-SPLIT]） | §4 | ✅ |
| 2 | F-2 拦截时机（竞态防护：源卡 claim 之前同步按住） | §3（AFTER UPDATE 触发器） | ✅ **D1 定稿：①+② 组合** |
| 3 | F-3 自动建子卡（复用 `_create_dev_sub_cards`，幂等键适配） | §4.1-4.3 | ✅ **D2 定稿：discover-sub-<源卡id>-<N>** |
| 4 | F-4 子卡 parents / 串并行 | §4.4 | ✅ |
| 5 | F-5 源卡按住与释放 | §5 | ✅ **D3 定稿：子卡全 done → autopilot complete 源卡** |
| 6 | F-6 兜底不回归 | §6 | ✅ |
| 7 | F-7 测试（AC-1~AC-8） | §8（T42-T50） | ✅ **D4 定稿：qa 不在本卡 scope** |
| 8 | F-8 拆卡回执 comment（P1） | §7.1 | ✅ |
| 9 | F-9 日志（P1） | §7.2 | ✅ |

### 0.2 架构裁决总表（本设计的核心决策）

| 决策点 | 裁决 | 说明 |
|--------|------|------|
| **A1 拦截机制（D1）** | **AFTER UPDATE 触发器（同步按住）+ autopilot Python 层（扫描建卡）= 双层** | 触发器在评估卡 `running/ready → done` 的**同一事务内**把源卡按住（blocked + sticky），dispatcher 60s tick 与 recompute_ready 完全无机可乘；Python 层每 tick 扫描、复用 cmd_chain 拆卡函数建子卡。PRD D1 建议 ①+② 采纳 |
| **A2 按住状态** | 源卡 → `status='blocked'` + `block_kind='dependency'` + **sticky 'blocked' 事件**（task_events 行） | 内核语义（实测源码）：`claim_task` 只 claim `ready`；`recompute_ready` 对 sticky-blocked（最近事件 kind='blocked'）**永不 promote**（L3345）；`complete_task` 接受 `running/ready/blocked → done`（L4081）。三者叠加 = 源卡在子卡完成前绝无被 claim 的可能，且终态可由 autopilot 直接 complete |
| **A3 独立/链卡 est 区分** | 触发器 WHEN 限定 `idempotency_key LIKE 'discover-est-%'` | 链卡评估卡 idem=`dev-<hash>-dev-est`（cmd_chain），独立卡评估卡 idem=`discover-est-<id>`（discover._create_est_card / est 触发器同源）。不加此限定会误拦链卡 dev 卡 → 链卡路径回归（AC-8） |
| **A4 N>1 判定** | 触发器用 `c.body LIKE '%[SUB-SPLIT]%' AND CAST(ltrim(substr(c.body, instr(c.body,'[SUB-SPLIT]')+11), '] ') AS INTEGER) >= 2`（纯 SQL 计数提取，marker 位置 instr 相对定位）；Python 层用 `_parse_sub_split` 权威复验 | ⚠️ **实测发现：SQLite LIKE 不支持 `[2-9]` 字符类**（`[`/`]` 是字面量），`LIKE '[SUB-SPLIT] [2-9]%'` 永不匹配（验证脚本实测）。改用 substr+instr+ltrim+CAST 提取计数（18 个边界用例全过：2/10/3换行/1/01/0/1x/无空格/双空格/字首非数字/空/其它标记/marker 非首字符 4 例）。**误判方向安全**：false-positive（本应 1 却被 hold）→ Python 层复验 N≤1 → 兜底释放；false-negative 仅限畸形文案 + 触发器缺位，Python 层独立扫描兜底 |
| **A5 幂等键（D2）** | `discover-sub-<源卡id>-<N>` | 与链卡 `dev-<hash>-dev-sub-N` 隔离（C2）；kernel 幂等去重 → 重复 tick 不重复建卡（AC-6） |
| **A6 子卡 parents 锚点（D2）** | serial：sub-1 parents=[评估卡]，sub-N parents=[sub-(N-1)]；parallel：全部 parents=[评估卡] | 评估卡已 done → 子卡创建即可被 dispatcher claim（与链卡 `_create_dev_sub_cards` 同语义）。**源卡不挂为子卡 parent**——否则子卡等源卡、源卡等子卡 → 死锁 |
| **A7 源卡终态（D3）** | 子卡全部 done → autopilot **complete 源卡**（容器语义）+ 同步设置 pipeline dev 步 artifact_paths | 与链卡「子卡全 done → dev 步满足」同语义；源卡 done 后 pipeline dev 步正常推进 va-claim。**同时修复前置缺陷 A9**（否则 dev 步 produces 校验必失败） |
| **A8 兜底释放** | 被 hold 但复验 N≤1 / 无裁决 / 解析失败 → 源卡 `blocked → todo`，交回 recompute_ready 正常 promote | F-6 语义：拆卡判定不成立 = 不拦截，现状行为 |
| **A9 前置缺陷发现（不在 PRD）** | **独立卡 dev 步 produces 校验恒失败**：dev 合约 produces=[branch, code_changes, claim_report.md]，而 `_check_produces`（state.py L172）只查 pipeline dev 步 artifact_paths（生产代码**无人写入**，恒为 `[]`）→ 源卡 done 后 dev 步 `contract_violation → block`。**本 FIX 在拆卡完成路径修复（A7 设置 artifact_paths）；非拆卡独立卡路径同样受影响，flag 给 OC 另立修复** | 实测证据：`grep -rn "artifact_paths=" pipeline/ scripts/` 仅 close-4 写入；T34 只测到 dev 步 pending，未覆盖源卡 done 之后的推进 |
| **A10 拆卡期 dev 步超时** | state.py 增加：当前步 kanban 卡为 `blocked` → 跳过超时判定（wait 不记超时） | 拆卡期子卡可能跑数小时（MEM-003 单张子卡估 24-30 轮），dev 步 timeout_min=60 会在子卡完成前把 dev 步打成 failed→retry→block，pipeline 死锁。**原则**：worker 级超时由内核 stale-claim/归档机制负责（有 claim 心跳）；pipeline 级超时只适用于 running/ready 卡，blocked = 等待中不该计超时 |
| **A11 测试编号** | 新增 **T42-T50** | 存量 T1-T39 已占用（T32-T35 discover 拦截 / T36-T39 编号注入）；T40-T41 预留给 cmd-channel cron PATH FIX（t_55eab970 架构已定名，避免撞号） |

### 0.3 约束合规确认

| 约束 | 本设计合规点 |
|------|-------------|
| C1 fail-open | 触发器安装失败 → 打日志不阻断主循环；Python 层扫描无异常抛出（全部 try/except 包住）；hermes CLI 调用失败 → 记日志返回空，源卡保持 blocked（安全侧） |
| C2 幂等键不冲突 | 独立卡子卡 `discover-sub-<id>-<N>`；链卡 `dev-<hash>-dev-sub-N`；评估卡 `discover-est-<id>`。三命名空间互不重叠 |
| C3 复用优先 | `_parse_sub_split`（L464）/ `_read_sub_split`（L509）/ `_create_dev_sub_cards`（L578）直接复用；`_create_dev_sub_cards` 仅加 1 个 `idem_prefix` 可选参数（默认空 → 链卡行为零变化），**零复制实现** |
| C4 识别口径与 `_card_type` 同源 | 独立 dev 卡判定 = `(title LIKE '[DEV]%' OR title LIKE '[FIX]%' OR assignee='game-engine') AND idempotency_key IS NULL`（PRD §2.3），与 discover._card_type（L127）同语义 |
| C5 并行上限 3 张 | 由内核 dispatcher `max_in_progress_per_profile` 在派发时强制（同链卡路径），建卡层不自行节流 |
| C6 触发器同源安装 | `install_subsplit_hold_trigger` 与 `install_est_intercept_trigger` 同一挂载点（autopilot.sh L98 段后），幂等 CREATE TRIGGER IF NOT EXISTS，fail-open |
| C7 建卡铁律 v4 编号 | 子卡 body 注入源卡「编号:」首行 / 标题 [CODE]-NNN（复用 `_extract_code`）；源卡无编号 → 空（不猜测） |

---

## 1. 现状核查与数据流全景

### 1.1 现状核查（读码 + 内核源码核查，非假设）

| # | 核查点 | 结论 | 证据 |
|---|--------|------|------|
| 1 | 独立 dev 卡拆卡盲区 | 评估卡 [SUB-SPLIT] N>1 后无人消费裁决；源卡 promote → worker 拿完整任务硬跑 → 60/60 超时 | PRD §1.1 通道 2；t_40ec4bde 两次 60/60 |
| 2 | 链卡拆卡已自动化 | cmd_chain `advance_sequential_chains` 每 tick 读 dev-est [SUB-SPLIT] → `_create_dev_sub_cards` 建子卡 | cmd_chain.py L970-1000 |
| 3 | 内核 recompute_ready 语义 | todo→ready 当**所有** parent done/archived；blocked 且 sticky（最近 task_events kind='blocked'）**永不 promote** | kanban_db.py L3303-3387（L3345 sticky 跳过） |
| 4 | 内核 claim_task 语义 | 只 claim `ready`；且绝不 claim 带未 done parent 的 ready 卡（结构不变量，demote 回 todo） | kanban_db.py L3394-3422 |
| 5 | 内核 complete_task 语义 | `running/ready/blocked → done`；无 run 时合成零时长 run；完成后**同函数内**调 recompute_ready（L4179-4180，独立事务） | kanban_db.py L4000-4180 |
| 6 | est 卡完成顺序 | worker 先写 [SUB-SPLIT] comment 再 complete 评估卡 → 触发器在 complete 的 UPDATE 事务内可见该 comment | MEM-003 现场：comment 已落卡（PRD §1.2） |
| 7 | 独立/链卡 est 卡 idem 键 | 独立卡 `discover-est-<id>`；链卡 `dev-<hash>-dev-est` | constants.py EST_IDEM_KEY_PREFIX / cmd_chain.py 链卡 idem 格式 |
| 8 | 源卡在 pipeline 的注册 | discover 注册 dev + dev-est 两步；dev 步的 kanban 卡 = 源卡（`_resolve_step_kanban_id` L202） | discover.register_discovered_task L539-552 / state.py L202-217 |
| 9 | dev 步超时 | timeout_min=60，`_check_timeout` 在**读 kanban 状态之前**执行（L716-745）→ blocked 卡也会 60min 后被判超时 | state.py L716-745 |
| 10 | dev 步 produces 校验 | 生产代码无任何位置写入 dev 步 artifact_paths（恒 `[]`）→ 源卡 done 后校验必失败（A9） | state.py L172-194 + grep artifact_paths= |
| 11 | `hermes kanban show --json` 字段 | **不含 block_kind**（实测 t_7a288793 输出 18 字段）→ A10 用 `status='blocked'` 判定，不依赖 block_kind | 实测 |
| 12 | 存量测试编号 | T1-T39 已存在（T26-T31 评估拆卡 / T32-T35 discover 拦截 / T36-T39 编号注入） | test_cmd_channel.sh |
| 13 | 测试 harness | temp kanban.db（复制真实 schema）+ temp pipeline_state.db + 隔离 flock + 清空触发器后显式调用 | test_cmd_channel.sh L17-94 |

### 1.2 竞态时序分析（为什么 f56cd1f 拦截不够）

```
现状（f56cd1f 之后，缺陷仍存）:
  worker complete 评估卡（running→done）
    → 内核 UPDATE tasks SET status='done'（事务内）
    → recompute_ready（独立事务）: 源卡 parent=评估卡(done) → promote todo→ready
    → dispatcher 60s tick: claim 源卡 → worker 拿【完整任务】硬跑 ← 缺陷窗口
    → discover 2min 轮询: 即使扫到 [SUB-SPLIT] N>1，源卡已被 claim，来不及

修复后（本设计）:
  worker complete 评估卡（running→done）
    → 内核 UPDATE tasks SET status='done'（同一事务内，subsplit 触发器同步执行）
        ① 源卡 → blocked + sticky 事件（与 est done 原子提交）
    → recompute_ready（独立事务）: 源卡 blocked+sticky → 跳过（L3345）→ 不 promote
    → dispatcher 60s tick: claim 只认 ready → 源卡不可 claim
    → autopilot Python 层（每 tick）: 扫描 → 读 [SUB-SPLIT] → 建 N 张子卡（幂等）
    → 子卡全 done → autopilot complete 源卡（blocked→done）→ pipeline dev 步正常推进
```

**关键原子性**：complete_task 的 write_txn 提交前，触发器已把源卡按住 → recompute_ready 看到的是一张 blocked+sticky 的卡。竞态窗口从「est done 到 Python 建卡」（0-2min）压缩为**零**——按住与 est done 同事务。

### 1.3 数据流全景（修复后）

```
┌─ autopilot tick（cron */2，主 flock 内）───────────────────────────────┐
│                                                                        │
│  L89-98   install_est_intercept_trigger（既有）                         │
│  L99      install_subsplit_hold_trigger（新增，幂等，fail-open）          │
│  L100-150 discover_new_tasks + register_discovered_task（既有）          │
│  L151     process_standalone_subsplit（新增，每 tick 一次）               │
│              ├─ 扫描: 独立 dev 卡 + est(done) + [SUB-SPLIT] N>1         │
│              │      ├─ 源卡 blocked → 已按住，直接建子卡                  │
│              │      ├─ 源卡 ready/todo → 先按 SQL 再建（触发器缺位兜底）   │
│              │      └─ 源卡 blocked 但复验 N≤1 → 兜底释放 todo           │
│              ├─ 建子卡: _create_dev_sub_cards(idem_prefix 适配)         │
│              │         serial: sub-1 parents=[est], sub-N parents=[sub-1]│
│              │         parallel: 全部 parents=[est]                     │
│              ├─ 回执: 源卡写 [SUB-SPLIT-DONE]（P1 F-8）                  │
│              └─ 终态: 子卡全 done → complete 源卡 + dev 步 artifact_paths│
│  L263+     ACTIVE_TASKS 循环（既有 advance_pipeline）                    │
│              └─ dev 步: 源卡 blocked → wait（A10: 不记超时）              │
│  ────────────────────────────────────────────────────────────────────  │
│  dispatcher（内核，60s tick）:                                          │
│    recompute_ready: 源卡 sticky-blocked → 跳过                           │
│    claim: 子卡 parents=[est(done)] → ready → claim → 派发 game-engine    │
└────────────────────────────────────────────────────────────────────────┘
```

### 1.4 前置缺陷发现（A9 / A10，工程师实现时必须处理）

1. **A9 dev 步 produces 校验恒失败**（独立卡全路径，含非拆卡）：`config/contracts.jsonl` dev 合约 produces=[branch, code_changes, claim_report.md]，`_check_produces` 只查 pipeline dev 步 artifact_paths，而生产代码无人写入该列（仅 close-4 写）。非拆卡独立卡完成源卡后同样会 contract_violation → block——**存量缺陷，flag 给 OC 另立 FIX**；本设计在拆卡路径（A7）修复。
2. **A10 拆卡期 dev 步超时死锁**：dev timeout_min=60，子卡跑数小时 → dev 步 failed(timeout) → retry → block → 即使子卡全 done、autopilot complete 源卡，pipeline 也不会推进。**本设计必须修**（§5.4）。

---

## 2. 核心机制总览：双层拆卡保障

| 层 | 组件 | 职责 | 失败语义 |
|----|------|------|---------|
| L1 | `subsplit_hold_after_update` 触发器（AFTER UPDATE ON tasks） | est 卡 done 瞬间（同事务）把源卡按住：blocked + block_kind=dependency + sticky 事件 | 安装失败 → 打日志，Python 层 L2 兜底（扫描 ready/todo 源卡，先按再拆）；最坏残留 0-2min 窗口（仅限触发器缺位时） |
| L2 | `process_standalone_subsplit()`（discover.py 新增） | 每 tick 扫描：独立 dev 卡 + est done + [SUB-SPLIT] N>1 → 建子卡（复用 cmd_chain）/ 兜底释放 / 子卡全 done → complete 源卡 | 异常不抛出（try/except），源卡保持 blocked（安全侧）；子卡创建失败 → 下 tick 重试（幂等键防重） |
| L3 | 内核不变量（借用，零改动） | `claim_task` 只 claim ready；`recompute_ready` 跳过 sticky-blocked | 即使有 racy writer 把源卡改回 ready，claim_task 的 parent 检查会 demote（est done 后无未 done parent，此防线仅防其他 writer） |
| L4 | state.py 超时豁免（A10） | dev 步 kanban=blocked → wait 不记超时 | 改动最小：只影响 blocked 卡的超时判定 |

---

## 3. F-1/F-2 — 拆卡裁决检测 + 拦截时机（L1 触发器）

### 3.1 新增 discover.py 常量与 SQL

```python
# discover.py（紧邻 EST_TRIGGER_NAME 定义处）

SUBSPLIT_TRIGGER_NAME = "subsplit_hold_after_update"
# 独立卡子卡幂等键前缀（C2: 与链卡 dev-<hash>-dev-sub-N 隔离）
SUBSPLIT_IDEM_PREFIX = "discover-sub-"
# 触发器 N>1 的 SQL 提取（A4: SQLite LIKE 不支持 [2-9] 字符类，实测永不匹配；
#   改用 substr+instr+ltrim+CAST —— marker 位置 instr 相对定位，18 个边界用例全过）
_SUBSPLIT_N_GT_1_SQL = (
    "c.body LIKE '%[SUB-SPLIT]%' "
    "AND CAST(ltrim(substr(c.body, instr(c.body, '[SUB-SPLIT]') + 11), '] ') AS INTEGER) >= 2"
)
```

### 3.2 触发器 SQL（完整实现，直接可落地）

```python
def _subsplit_trigger_sql(repo_root: str) -> str:
    """subsplit_hold_after_update 触发器 SQL。

    语义：独立 dev 卡的 [DEV-EST] 评估卡 done 瞬间（同一事务内）：
      1. 源卡 → status='blocked', block_kind='dependency'（claim_task 只 claim ready → 不可 claim）
      2. 写 sticky 'blocked' 事件（recompute_ready 对 sticky-blocked 永不 promote）

    WHEN 守卫（与 discover._card_type / est 触发器同源语义）:
      - NEW.title LIKE '[DEV-EST]%'：评估卡
      - NEW.idempotency_key LIKE 'discover-est-%'：独立卡评估卡（排除链卡 dev-<hash>-dev-est，A3）
      - OLD.status <> 'done'：仅迁移瞬间（running/ready → done）
      - 存在 [SUB-SPLIT] N≥2 comment（A4 LIKE 近似）
      - 存在独立 dev 源卡子节点（task_links child，idempotency_key IS NULL）

    注意: 触发器只负责「按住」，建子卡由 autopilot Python 层（L2）负责
    （C3 复用 cmd_chain 拆卡函数，触发器内不复制建卡逻辑）。
    """
    return f"""CREATE TRIGGER IF NOT EXISTS {SUBSPLIT_TRIGGER_NAME}
AFTER UPDATE ON tasks
WHEN NEW.status = 'done'
  AND OLD.status <> 'done'
  AND NEW.title LIKE '[DEV-EST]%'
  AND NEW.idempotency_key LIKE 'discover-est-%'
  AND EXISTS (
    SELECT 1 FROM task_comments c
    WHERE c.task_id = NEW.id
      AND ({_SUBSPLIT_N_GT_1_SQL})
  )
  AND EXISTS (
    SELECT 1 FROM task_links l JOIN tasks s ON s.id = l.child_id
    WHERE l.parent_id = NEW.id
      AND s.idempotency_key IS NULL
      AND (s.title LIKE '[DEV]%' OR s.title LIKE '[FIX]%' OR s.assignee = 'game-engine')
  )
BEGIN
  -- 1. 按住源卡（仅 ready/todo 需要按；已 blocked 幂等跳过）
  UPDATE tasks
     SET status = 'blocked', block_kind = 'dependency',
         claim_lock = NULL, claim_expires = NULL, worker_pid = NULL
   WHERE id IN (
         SELECT l.child_id FROM task_links l
         WHERE l.parent_id = NEW.id
   )
     AND idempotency_key IS NULL
     AND status IN ('ready', 'todo');
  -- 2. sticky block 事件（_has_sticky_block → recompute_ready L3345 永不 promote）
  INSERT INTO task_events (task_id, kind, payload, created_at)
  SELECT l.child_id, 'blocked',
         '{{"reason":"subsplit-hold: [SUB-SPLIT] N>1 拆卡裁决，等待 autopilot 建子卡","kind":"dependency"}}',
         strftime('%s','now')
  FROM task_links l
  WHERE l.parent_id = NEW.id;
END;"""
```

**实现要点**：
- `UPDATE ... WHERE id IN (SELECT ...)` + `status IN ('ready','todo')`：源卡已被 est 触发器 demote 为 todo（f56cd1f），此处 ready/todo 均覆盖；已 blocked（重复触发）幂等跳过。
- task_events INSERT 无 WHERE 去重：est 卡只 done 一次 → 正常只插一行；est 被 reopen 再 done（病态）→ 多一行事件，仅影响 sticky 判定（仍为 blocked）→ 无害。
- 触发器内 SELECT task_comments / task_links / tasks 均为同库只读 → SQLite 允许。
- **不**在触发器内建子卡（C3）：建卡需要 hermes CLI 幂等调用与 body 组装，属于 L2 职责。

### 3.3 安装函数 + autopilot.sh 挂载点

```python
# discover.py（紧邻 install_est_intercept_trigger L346 之后）

def install_subsplit_hold_trigger(kanban_db_path: str = "") -> bool:
    """幂等安装 subsplit_hold_after_update 触发器（fail-open，同 est 触发器）。

    Returns: 安装成功 True；DB 缺失/异常 False（不抛出，autopilot 每 tick 重试）。
    """
    db = _kanban_db_path(kanban_db_path)
    if not os.path.exists(db):
        return False
    try:
        conn = sqlite3.connect(db)
        try:
            conn.execute(_subsplit_trigger_sql(""))
            conn.commit()
            return True
        finally:
            conn.close()
    except sqlite3.Error:
        return False
```

autopilot.sh 挂载（L98 est 触发器块之后插入，主循环零改动）：

```bash
L98  python3 -c "
L99  import sys; sys.path.insert(0, '$REPO_ROOT')
L100 from pipeline.discover import install_est_intercept_trigger
L101 ok = install_est_intercept_trigger()
L102 print(f'est_intercept_trigger installed: {ok}')
L103 " 2>&1 || true
# [FIX 独立 dev 卡拆卡保障] 安装拆卡按住触发器（幂等，fail-open）
python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.discover import install_subsplit_hold_trigger
ok = install_subsplit_hold_trigger()
print(f'subsplit_hold_trigger installed: {ok}')
" 2>&1 || true
```

---

## 4. F-3/F-4 — 自动建子卡（L2 Python 层，复用 cmd_chain）

### 4.1 `_create_dev_sub_cards` 最小适配（C3，唯一改动点）

cmd_chain.py L578 函数签名增加一个可选参数，链卡调用方零改动：

```python
def _create_dev_sub_cards(
    kanban_db: str,
    spec_hash: str,
    topic: str,
    split: dict,
    est_id: str,
    ctx: Optional[dict],
    idem_prefix: str = "",          # ← 新增（独立卡用 discover-sub-<源卡id>）
) -> list[dict]:
    ...
        card_id = _hermes_create(
            title, "game-engine", body,
            # 独立卡: discover-sub-<源卡id>-<N>；链卡: dev-<hash>-dev-sub-N（原行为）
            idem_key=(f"{idem_prefix}-{i}" if idem_prefix
                      else f"dev-{spec_hash}-{sub_step}"),
            parents=parents,
            workspace=CHAIN_WORKSPACE,
        )
```

- 默认 `idem_prefix=""` → 链卡行为逐字节不变（AC-8 回归保障）。
- `_create_qa_sub_cards`（L618）**不动**（D4：qa 拆卡不在本卡 scope）。

### 4.2 discover.py 新增：独立卡拆卡处理（完整函数级设计）

```python
# ── [FIX 独立 dev 卡拆卡保障] 独立卡拆卡处理（PRD §4 F-1..F-6）──────────

def _standalone_sources_with_done_est(conn: sqlite3.Connection) -> list[dict]:
    """扫描独立 dev 卡（§2.3 定义）且 [DEV-EST] parent 已 done 的候选。

    status 不限定：ready/todo（触发器缺位兜底）/ blocked（正常 hold）均纳入，
    N>1 判定交给 _read_sub_split 权威复验（A4）。
    """
    try:
        rows = conn.execute(
            """
            SELECT s.id, s.title, s.status, e.id AS est_id
            FROM tasks s
            JOIN task_links l ON l.child_id = s.id
            JOIN tasks e ON e.id = l.parent_id
            WHERE s.idempotency_key IS NULL
              AND (s.title LIKE '[DEV]%' OR s.title LIKE '[FIX]%'
                   OR s.assignee = 'game-engine')
              AND s.status IN ('ready', 'todo', 'blocked')
              AND e.title LIKE '[DEV-EST]%'
              AND e.idempotency_key LIKE 'discover-est-%'
              AND e.status = 'done'
            ORDER BY s.created_at
            """
        ).fetchall()
        return [dict(r) for r in rows]
    except sqlite3.Error:
        return []


def _hold_source(conn: sqlite3.Connection, source_id: str) -> None:
    """Python 层按住源卡（触发器缺位时 L2 兜底；与触发器 SQL 同构）。"""
    try:
        conn.execute(
            "UPDATE tasks SET status='blocked', block_kind='dependency', "
            "claim_lock=NULL, claim_expires=NULL, worker_pid=NULL "
            "WHERE id=? AND status IN ('ready','todo')",
            (source_id,),
        )
        conn.execute(
            "INSERT INTO task_events (task_id, kind, payload, created_at) "
            "VALUES (?, 'blocked', ?, strftime('%s','now'))",
            (source_id,
             '{"reason":"subsplit-hold: L2 兜底按住，等待建子卡","kind":"dependency"}'),
        )
        conn.commit()
    except sqlite3.Error:
        pass  # fail-open: 按住失败不抛出（源卡保持原状，下 tick 重试）


def _release_source(conn: sqlite3.Connection, source_id: str) -> None:
    """兜底释放（A8）：复验 N≤1 / 无裁决 → blocked→todo，交回 recompute_ready。"""
    try:
        conn.execute(
            "UPDATE tasks SET status='todo', block_kind=NULL "
            "WHERE id=? AND status='blocked'",
            (source_id,),
        )
        conn.commit()
    except sqlite3.Error:
        pass


def _standalone_subs(conn: sqlite3.Connection, source_id: str) -> list[dict]:
    """查询独立卡子卡（幂等键 discover-sub-<源卡id>-<N>）→ [{id, status}]。"""
    try:
        rows = conn.execute(
            "SELECT id, status FROM tasks WHERE idempotency_key LIKE ? "
            "ORDER BY idempotency_key",
            (f"{SUBSPLIT_IDEM_PREFIX}{source_id}-%",),
        ).fetchall()
        return [{"id": r["id"], "status": r["status"]} for r in rows]
    except sqlite3.Error:
        return []


def _source_code(conn: sqlite3.Connection, source_id: str) -> str:
    """独立卡编号继承（C7）：源卡 body 首行 '编号: <CODE>-NNN' / 标题 [CODE]-NNN。"""
    try:
        row = conn.execute(
            "SELECT title, body FROM tasks WHERE id=?", (source_id,)
        ).fetchone()
        if not row:
            return ""
        body = (row["body"] or "").strip()
        if body:
            first = body.splitlines()[0]
            if first.startswith("编号:"):
                code = _extract_code(first)
                if code:
                    return code
        return _extract_code(row["title"] or "") or ""
    except (sqlite3.Error, Exception):
        return ""


def process_standalone_subsplit(
    kanban_db: str,
    pipeline_db_path: str = "",
    repo_root: str = "",
) -> dict:
    """每 tick 调用：独立 dev 卡拆卡裁决强制落地（F-1..F-6 + D3 终态）。

    流程（两阶段）:
      阶段 1 拆卡: 对每个「独立 dev 卡 + est done」候选:
        - 读 est [SUB-SPLIT]（_read_sub_split，权威复验）
        - N>1 → 按住（已 blocked 跳过）→ 建子卡（幂等）→ [SUB-SPLIT-DONE] 回执
        - N≤1 / 无裁决 → 若被 hold 则兜底释放（A8）
      阶段 2 终态: 已建子卡全部 done → complete 源卡（A7）+ dev 步 artifact_paths

    Returns: {'created': [子卡 id], 'completed': [源卡 id], 'released': [源卡 id]}
    全部异常内吞（C1 fail-open）；任何失败下 tick 重试（幂等键防重）。
    """
    created, completed, released = [], [], []
    try:
        conn = sqlite3.connect(kanban_db)
        conn.row_factory = sqlite3.Row
        try:
            # ── 阶段 1: 拆卡 ──
            for src in _standalone_sources_with_done_est(conn):
                split = _read_sub_split(conn, src["est_id"], "SUB-SPLIT")
                if not split or split["count"] <= 1:
                    # 兜底: 被 hold 但裁决不成立 → 释放（F-6）
                    if src["status"] == "blocked":
                        _release_source(conn, src["id"])
                        released.append(src["id"])
                    continue
                # 裁决成立 → 确保按住（正常已被触发器按住；触发器缺位时 L2 兜底）
                if src["status"] in ("ready", "todo"):
                    _hold_source(conn, src["id"])
                subs = _standalone_subs(conn, src["id"])
                if subs:
                    continue  # 子卡已建（幂等），等执行
                # 建子卡（复用 cmd_chain，幂等键 discover-sub-<源卡id>-<N>）
                topic = _topic_from_title(src["title"]) or src["id"]
                ctx = {"code": _source_code(conn, src["id"])}
                new_subs = _create_dev_sub_cards(
                    kanban_db, "", topic, split, src["est_id"], ctx,
                    idem_prefix=f"{SUBSPLIT_IDEM_PREFIX}{src['id']}",
                )
                created.extend(s["id"] for s in new_subs)
                if new_subs:
                    ids = ", ".join(s["id"] for s in new_subs)
                    _comment(kanban_db, src["id"],
                             f"[SUB-SPLIT-DONE] 已建 {len(new_subs)} 张子卡（{split.get('mode','serial')}）：{ids}")
            # ── 阶段 2: 子卡全 done → complete 源卡 ──
            for src in _standalone_sources_with_done_est(conn):
                subs = _standalone_subs(conn, src["id"])
                if not subs:
                    continue
                if not all(s["status"] == "done" for s in subs):
                    continue
                if src["status"] in ("blocked", "todo", "ready"):
                    _complete_source(kanban_db, pipeline_db_path,
                                     src["id"], subs)
                    completed.append(src["id"])
        finally:
            conn.close()
    except sqlite3.Error:
        return {"created": created, "completed": completed, "released": released}
    return {"created": created, "completed": completed, "released": released}


def _complete_source(kanban_db: str, pipeline_db_path: str,
                     source_id: str, subs: list[dict]) -> None:
    """子卡全 done → 源卡终态（A7/D3 定稿）：
      1. pipeline dev 步 artifact_paths 补齐（A9 修复：produces 校验通过）
      2. 源卡写完成回执 comment（可追溯）
      3. hermes kanban complete 源卡（blocked → done，内核支持）
    全部 fail-open：任何一步失败下 tick 重试（complete 幂等：done 卡再 complete 返回 False 无害）。
    """
    # 1. artifact_paths（直连 SQL，避免 upsert_step status='running' 重置 started_at）
    if pipeline_db_path:
        try:
            conn = sqlite3.connect(pipeline_db_path)
            try:
                import json as _json
                conn.execute(
                    "UPDATE pipeline_steps SET artifact_paths=? "
                    "WHERE task_id=? AND step_name='dev'",
                    (_json.dumps(
                        ["branch", "code_changes", "claim_report.md",
                         "子卡: " + ", ".join(s["id"] for s in subs)]
                    ), source_id),
                )
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    # 2. 回执 comment（best-effort）
    ids = ", ".join(s["id"] for s in subs)
    _comment(kanban_db, source_id,
             f"[SUB-SPLIT-DONE] 子卡全部完成（{ids}），autopilot 关闭源卡（容器语义）；"
             f"各子卡 claim/produces 见子卡 comment")
    # 3. complete 源卡（hermes CLI；失败下 tick 重试）
    try:
        subprocess.run(
            ["hermes", "kanban", "complete", source_id,
             "--summary", f"拆卡完成：{len(subs)} 张子卡（{ids}）全部 done，源卡作为容器关闭"],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        pass
```

### 4.3 autopilot.sh 挂载点（L2，每 tick 一次）

插在注册循环之后（L151 附近）、ACTIVE_TASKS 扫描（L263）之前——即使无活跃管线任务也要跑（拆卡处理不依赖 pipeline_state）：

```bash
# [FIX 独立 dev 卡拆卡保障] 拆卡裁决强制落地（F-1..F-6 + 源卡终态）
python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.discover import process_standalone_subsplit
r = process_standalone_subsplit('$HERMES_KANBAN_DB', '$REPO_ROOT/pipeline_state.db', '$REPO_ROOT')
print(f'subsplit processed: {r}')
" 2>&1 || echo "$LOG_TAG subsplit 处理失败（fail-open）"
```

### 4.4 parents / 串并行语义（F-4，复用 `_create_dev_sub_cards` 既有逻辑）

| 模式 | sub-1 | sub-N（N>1） | 派发 |
|------|-------|--------------|------|
| serial | parents=[评估卡]（done → 立即 ready） | parents=[sub-(N-1)]（父 done 才派发） | 逐张串行 |
| parallel | parents=[评估卡] | parents=[评估卡] | 同时 ready；≤3 张/同 profile 由内核 `max_in_progress_per_profile` 强制（C5） |

- 子卡 body 含：编号（源卡继承，C7）、议题、来源（评估卡 id + 子序号）、子任务描述、拆卡子任务说明——由 `_sub_card_body`（L543）生成，链卡同款。
- **源卡不挂为子卡 parent**（A6）：避免「子卡等源卡 done、源卡等子卡 done」死锁。源卡按住完全由 blocked+sticky 承担，子卡完成检测由 L2 幂等键查询承担，二者不需要 task_links。

---

## 5. F-5 — 源卡按住与释放 + D3 终态

### 5.1 按住（L1 触发器 + L2 兜底）

| 时机 | 动作 | 机制 |
|------|------|------|
| est done 瞬间 | 源卡 → blocked + sticky（同事务） | L1 触发器（§3.2） |
| est done 后、触发器缺位 | 源卡 ready/todo → 按 SQL 按住再建卡 | L2 `_hold_source`（§4.2） |

按住期间（blocked + sticky）：
- `recompute_ready` 跳过（kanban_db.py L3345）→ 永不 promote
- `claim_task` 只 claim ready → 不可 claim
- pipeline dev 步读源卡 → blocked → wait（A10 修后不记超时）

### 5.2 释放（A8 兜底）

仅当复验裁决不成立（N≤1 / 无 [SUB-SPLIT] / 解析失败）：`blocked → todo`，est parent 已 done → 下个 dispatcher tick recompute_ready 正常 promote → 单卡执行。与现状行为完全一致（F-6）。

### 5.3 终态（D3 定稿：autopilot complete 源卡）

子卡全部 done → L2 `_complete_source`：
1. pipeline dev 步 artifact_paths = [branch, code_changes, claim_report.md, 子卡: <ids>]（A9 修复 + va-claim requires 溯源）
2. 源卡 [SUB-SPLIT-DONE] 完成回执 comment
3. `hermes kanban complete <源卡> --summary ...`（blocked → done，内核 L4081 支持）
4. pipeline dev 步看到源卡 done + produces 校验通过 → dev done → 推进 va-claim（既有流程）

### 5.4 A10 — state.py 超时豁免（必改，否则拆卡期 dev 步超时死锁）

state.py `determine_next_action` L708-745：当前「先超时检测、后读 kanban」顺序会导致 blocked 卡 60min 后被误判超时。改为「先读 kanban，blocked → wait 不记超时」：

```python
# state.py L735-745 现状:
#   kanban = get_kanban_task_state(...)
#   if kanban is None: return wait
#   kanban_status = kanban.get("status", "")
#   if kanban_status == "done": ...
#   ...
#   else: return wait(...)

# 改后（在 kanban_status 取得之后、done/failed 分支之前插入）:
        kanban_status = kanban.get("status", "")
        # [FIX 独立 dev 卡拆卡保障 A10] blocked = 等待（依赖/人工），不记超时。
        # worker 级卡死由内核 stale-claim/归档处理（有 claim 心跳），
        # pipeline 级超时只适用于 running/ready 卡；否则拆卡期（子卡跑数小时）
        # dev 步 60min 后被打 failed → retry → block，子卡完成后 pipeline 死锁。
        if kanban_status == "blocked":
            return {
                "action": "wait",
                "step": step_name,
                "task_id": task_id,
                "detail": f"等待步骤 {step_name} 完成（kanban status=blocked，不记超时）",
            }
        if kanban_status == "done":
            ...
```

同时把超时检测块（L717-733）**保留原位**——它现在只对 kanban != blocked 的卡生效（running/ready），语义正确。注意：`hermes kanban show --json` 实测不含 block_kind（核查点 11），因此用 `status == 'blocked'` 判定即可，不需要区分 dependency/needs_input——blocked 一律是「等待」，等待不该计超时。

---

## 6. F-6 — 兜底不回归（场景矩阵）

| 场景 | est 状态 | [SUB-SPLIT] | 触发器 | Python 层 | 结果 |
|------|---------|------------|--------|-----------|------|
| 拆 2 张 | done | 2 serial | hold 源卡 | 建 2 子卡 serial | 子卡执行，源卡容器关闭（AC-1/2） |
| 拆 2 张并行 | done | 2 parallel | hold 源卡 | 建 2 子卡 parallel | 同时派发（AC-3） |
| 不拆 | done | 1 | **不触发**（LIKE 不匹配） | 不处理 | 源卡单卡执行（AC-5） |
| 无评估卡（--skip dev-est） | 无 | 无 | 不触发（无 est 卡） | 扫描不到（无 est parent） | 源卡单卡执行（AC-4） |
| 无裁决 comment | done | 无 | 不触发（无 comment） | 无裁决 → 不动 | 源卡单卡执行 |
| 解析失败 | done | `[SUB-SPLIT] 1x` | 不触发（LIKE 不匹配） | `_parse_sub_split` None → 不动 | 源卡单卡执行 |
| 畸形 N（如 `[SUB-SPLIT] 5 3`） | done | LIKE 匹配 → hold | 复验 count=5 → 建 5 张（mode 默认 serial） | 按裁决执行 | 容错 |
| 误 hold（est 旧 comment N>1、最新 N=1） | done | 最新 1 | hold（任一 comment 匹配） | 复验最新 N≤1 → 释放 | 源卡单卡执行（安全方向） |
| 子卡已建，重复 tick | done | 2 | hold（幂等） | `_standalone_subs` 命中 → 跳过 | 不重复建卡（AC-6） |
| 子卡全部 done | done | 2 | - | `_complete_source` | 源卡 done（D3/AC-1 尾） |
| 链卡 est done | done（dev-<hash>-dev-est） | 2 | **不触发**（idem 非 discover-est-） | 扫描不到（源卡 idem 非 NULL） | 链卡路径零改动（AC-8） |

---

## 7. F-8/F-9 — 可观测（P1）

### 7.1 F-8 拆卡回执 comment

- 建卡后：源卡写 `[SUB-SPLIT-DONE] 已建 N 张子卡（serial|parallel）：<id 列表>`（§4.2 已含）。
- 幂等：`_create_dev_sub_cards` 幂等键去重 → 重复 tick 不重复建卡也不重复回执（子卡已建 → continue，回执只写一次）。
- 完成时：源卡写 `[SUB-SPLIT-DONE] 子卡全部完成（<ids>），autopilot 关闭源卡`（§5.3 已含）。

### 7.2 F-9 日志

autopilot.log（cron 重定向）天然记录：
- 触发器安装：`subsplit_hold_trigger installed: True/False`（每 tick 幂等）
- Python 层：`subsplit processed: {'created': [...], 'completed': [...], 'released': [...]}`（每 tick）
- 异常：fail-open 路径打 `subsplit 处理失败` 行

---

## 8. 测试方案（T42-T50，编号 A11 重排）

### 8.1 测试矩阵（对应 PRD F-7 / 验收 AC-1..AC-8 + D3 终态）

| # | 场景 | 前置（fixture） | 断言 | 对应 |
|---|------|----------------|------|------|
| **T42** | 独立 dev 卡 + [SUB-SPLIT] 2 serial → 自动拆卡 | 源卡 t_src42（idem NULL, [DEV], game-engine, todo）+ 评估卡 t_est42（idem discover-est-t_src42, running）+ task_links + comment `[SUB-SPLIT] 2 serial`；UPDATE t_est42 → done（触发触发器） | ① 源卡 status=blocked + block_kind=dependency + task_events 有 sticky blocked 行；② `process_standalone_subsplit` 后建 2 张卡（idem discover-sub-t_src42-1/-2，title [DEV-SUB-1/2]，assignee=game-engine）；③ 源卡仍 blocked；④ 源卡有 [SUB-SPLIT-DONE] comment | AC-1 / F-1+F-2+F-3+F-8 |
| **T43** | 子卡 parents 串行 | T42 场景 | sub-1 parents=[t_est42]；sub-2 parents=[sub-1] | AC-2 |
| **T44** | 子卡 parents 并行 | [SUB-SPLIT] 2 parallel | 两张 parents 均=[t_est42]（均可立即 claim） | AC-3 |
| **T45** | 无评估卡 → 不拦截 | 独立 dev 卡（ready, 无 est parent） | process 后 status 仍 ready；不建子卡 | AC-4 / F-6 |
| **T46** | [SUB-SPLIT] 1 → 不拦截 | est done + comment `[SUB-SPLIT] 1` | UPDATE est done 后源卡**不被** hold（status=todo，可被 recompute promote）；process 后无子卡 | AC-5 / F-6 |
| **T47** | 幂等 | T42 场景 | `process_standalone_subsplit` 连跑 3 tick → 子卡总数仍 2；[SUB-SPLIT-DONE] 只 1 条 | AC-6 |
| **T48** | 竞态防护 | est done 瞬间（同事务） | ① UPDATE est→done 语句返回后源卡立即 blocked（无中间 ready）；② 模拟内核 recompute_ready：源卡保持 blocked（sticky 跳过）；③ 模拟 claim_task：不 claim（只认 ready） | AC-7 |
| **T49** | 链卡回归 | 链 est（idem dev-<hash>-dev-est, running）+ 链 dev 源卡（idem dev-<hash>-dev, todo）+ comment `[SUB-SPLIT] 2 serial` | UPDATE 链 est → done 后链 dev 卡**不被** hold；`advance_sequential_chains` 走链逻辑建 dev-sub-1/2（既有 T26-T31 回归） | AC-8 |
| **T50** | 子卡全 done → 源卡终态 | T42 建卡后，两张子卡标记 done | `process_standalone_subsplit` 后：源卡 status=done；pipeline dev 步 artifact_paths 含 branch/code_changes/claim_report.md；源卡有完成回执 comment | D3 / F-5 |

### 8.2 实现要点（沿用 test_cmd_channel.sh harness 约定）

- **fixture**：temp kanban.db（L60-94 复制 schema + 清空 + 插入受控行）+ `DROP TRIGGER IF EXISTS est_intercept_after_insert`（L69 既有）——**新增同款 `DROP TRIGGER IF EXISTS subsplit_hold_after_update`**，然后 T42/T46/T48/T49 显式 `install_subsplit_hold_trigger()` 后再 UPDATE est 卡（不依赖真实 board 触发器状态）。
- **模拟 est done**：fixture 中 est 卡 status='running'，测试里 `UPDATE tasks SET status='done' WHERE id='t_est42'` 触发 subsplit 触发器（与内核 complete_task 同构）。
- **调用 process**：`python3 -c "from pipeline.discover import process_standalone_subsplit; process_standalone_subsplit('$KDB', '$PIPE', '$REPO_ROOT')"`，KDB/PIPE 指向 temp 库（既有 q1/assert_eq/assert_contains 断言）。
- **模拟 recompute/claim（T48）**：直接断言 blocked + sticky 事件存在即满足「不可被 claim」（内核源码保证 claim 只认 ready、recompute 跳过 sticky——测试不 import 内核，保持 harness 隔离性）。
- **存量回归**：T1-T39 全绿；`_create_dev_sub_cards` 新增参数默认值 → 链卡路径零行为差异。

---

## 9. 约束合规确认（汇总）

| 约束 | 合规 | 说明 |
|------|------|------|
| C1 fail-open | ✅ | 触发器安装失败不阻断主循环（|| true）；process 全异常内吞；hermes CLI 失败返回空、源卡保持 blocked（安全侧）；兜底释放失败 → 源卡停留 blocked，可观测可人工处置 |
| C2 幂等键隔离 | ✅ | discover-sub-<id>-<N> / dev-<hash>-dev-sub-N / discover-est-<id> 三命名空间不重叠 |
| C3 复用优先 | ✅ | _parse_sub_split/_read_sub_split 原样复用；_create_dev_sub_cards 仅 +1 可选参数；零复制实现 |
| C4 识别口径 | ✅ | 独立 dev 卡判定与 _card_type 同源（[DEV]/[FIX] 前缀或 assignee=game-engine + idem NULL） |
| C5 并行上限 | ✅ | 内核 max_in_progress_per_profile 派发时强制（同链卡） |
| C6 触发器同源 | ✅ | 同 install_est_intercept_trigger 挂载点、同幂等 CREATE TRIGGER IF NOT EXISTS、同 fail-open |
| C7 建卡铁律 v4 | ✅ | 子卡编号从源卡 body/标题继承（_source_code），无编号不猜测 |

## 10. 工时估算与拆卡建议

### 10.1 工时（按 PRD §8 口径，含 A9/A10 修正项）

| 模块 | 工时 |
|------|:---:|
| L1 触发器（subsplit_hold_after_update SQL + 安装函数 + autopilot.sh 挂载） | 1.5h |
| L2 Python 层（process_standalone_subsplit + _hold/_release/_complete + _create_dev_sub_cards idem_prefix 适配） | 2.5h |
| 源卡按住/释放/终态 + A9 artifact_paths + A10 state.py 超时豁免 | 1.5h |
| 测试 T42-T50（9 例 + 存量回归） | 2.5h |
| F-8/F-9 可观测（P1） | 1h |
| **合计** | **9h（P0 8h + P1 1h）** |

### 10.2 拆卡建议（提交 OC 决策，本卡不建卡）

- **建议拆 2 张**：① P0（L1 触发器 + L2 Python 层 + A9/A10 + T42-T49，7.5h）——独立卡拆卡保障落地，子卡全 done → 源卡 complete（含 T50）；② P1（F-8 回执完善 + F-9 日志增强，1.5h）——可观测收尾。
- 理由：P0 独立可交付（哪怕 P1 悬置，拆卡保障已闭环）；P1 纯增强。
- 工程实现后由 QA 走 FIX 验收（AC-1..AC-8 全量 + 回归）。

---

## 附：与相关既有文档的衔接

- PRD：docs/prd/fix-standalone-dev-subsplit-prd.md（commit 1fe7a08；D1/D2/D3/D4 本设计已定稿）
- 拆卡机制设计：docs/design/estimate-split-cards.md（v1 机制 + v2 参数：≤20 轮 / 并行上限 3）
- 评估卡拦截触发器（f56cd1f）：pipeline/discover.py（est_intercept_after_insert，本设计同构扩展）
- 链卡拆卡实现：pipeline/cmd_chain.py（_parse_sub_split L464 / _read_sub_split L509 / _create_dev_sub_cards L578 / advance 拆卡 L970-1000）
- 建卡铁律 v4：docs/arch/arch-card-numbering-chain-v4.md（C7 编号继承口径）
- 内核家长门控语义：hermes_cli/kanban_db.py（recompute_ready L3303 / claim_task L3394 / complete_task L4000 / block_task L4563 / _has_sticky_block L3265）
- 测试 harness：scripts/test_cmd_channel.sh（T1-T39 存量 + T42-T50 新增）

## 附 2：OC 决策项（非本卡代码范围）

1. **A9 前置缺陷**：独立卡（含非拆卡）dev 步 produces 校验恒失败——源卡 done 后 dev 步 contract_violation → block。本设计仅在拆卡完成路径修复（artifact_paths）；非拆卡独立卡路径需另立 FIX（建议：autopilot 在标记 dev 步 done 时从 [PRODUCES] comment 提取产物写入 artifact_paths，或放宽 dev 合约 produces 校验）。
2. **存量卡处置**：t_40ec4bde 等已硬跑超时存量卡由 OC 按现状处置（PRD N5，本 FIX 管未来）。
3. **人工 unblock 风险**：拆卡中源卡为 blocked 状态，若有人误 `kanban unblock` → ready → 可能被 claim 双跑。已在源卡回执/comment 中说明「由 autopilot 关闭，请勿 unblock」；如需更强防护（unblock 事件拦截），另立 FIX。
