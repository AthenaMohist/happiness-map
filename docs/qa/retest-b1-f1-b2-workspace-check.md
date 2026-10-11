# B1-F1 回归 + B2 workspace_check/内容注入 — QA 独立复测报告

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa
>
> 任务卡：t_d7e6bdd2 [B1-FIX+B2 QA] QA 复测 — B1-F1 回归 + B2 workspace_check/内容注入
> 被测提交：9263501（B1-F1 修复卡 t_c36bd9e4）+ 69093ec（B2 卡 t_aad6d422）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 执行摘要

| 项目 | 数值 |
|------|:---:|
| B1-F1 S1/S2 repro 独立复现（qa_boundary_repro.py） | **repro=False / repro=False**（exit 0） |
| 研发断言套件独立重跑（test_notify_check.py，T1-T10） | **33 PASS / 0 FAIL**（27 原有 + 6 新增 T9/T10） |
| QA 独立断言（qa_notify_retest.py，12 组） | **32 PASS / 0 FAIL** |
| QA 边界正常推送独立验证（新增 qa_boundary_normal.py，3 组） | **7 PASS / 0 FAIL** |
| B2 workspace_check 测试套件（test_workspace_check.sh） | **27 PASS / 0 FAIL** |
| B2 discover.py 静态核对 | 4/4 通过 |
| B2 实机核对（autopilot.log + kanban.db） | 4/4 通过 |
| 回归（crontab / notify_cron.sh / pytest / slice3_smoke） | 全过 |
| 缺陷 | **0（BLOCKER=0，MAJOR=0，MINOR=0）** |
| 结论 | **PASS** — B1-F1 修复有效且无回归；B2 功能与验收标准全部通过 |

发布门禁对照（§10）：BLOCKER=0，MAJOR=0（≤3），安全漏洞=0，无未裁定申诉 → **门禁通过**。

---

## 1. B1-F1 回归验证（修复提交 9263501）

### 1.1 修复代码核对（notify_check.py L595-600）

修复点：milestone 聚合路径过滤 `__boundary__` 合成行。

```python
milestone_rows = [r for r in pending
                  if r["event_type"] == "milestone" and r["task_id"] != "__boundary__"]
```

- ✅ 过滤条件在 pending 查询之后、格式化之前（L599-600）
- ✅ 边界消息优先路径（L590-593，boundary_msg 非空时直接消费合成行）不受影响
- ✅ 注释完整说明 B1-F1 根因（发送失败/dry-run 后 last_sent_at NULL → 进入 pending）

### 1.2 S1/S2 独立复现（复用 /tmp/qa_boundary_repro.py）

```
── S1: 边界消息发送失败 → 下 tick 补推 ──
  boundary rows after failed tick: [('2511f4...', 'milestone', '__boundary__', 'work_state', 'idle', None)]
  messages sent in retry tick: ['✅ t_a dev done']
  未复现（无 __boundary__ 垃圾文案）

── S2: 生产库 dry-run 触发边界 → 下 tick 真推 ──
  boundary rows after dry-run: [('__boundary__', 'work_state', 'idle', None)]
  messages sent in real tick: ['✅ t_a dev done']
  未复现

RESULT: S1 repro=False S2 repro=False
EXIT=0
```

- ✅ 边界合成行仍留在 notify_events（last_sent_at=NULL），但 milestone 聚合不再选中它 → 不推垃圾文案
- ✅ 真实 milestone（`✅ t_a dev done`）在重试 tick 正常补推（不误伤）

### 1.3 研发断言套件独立重跑

```
python3 scripts/test_notify_check.py
RESULTS: 33 PASS / 0 FAIL   (exit 0)
```

- ✅ T1-T8 原有 27 断言全绿（无回归）
- ✅ T9（S1 发送失败重试）/T10（S2 dry-run）新增 6 断言全绿

### 1.4 QA 独立断言（研发复跑 /tmp/qa_notify_retest.py，12 组 32 断言）

```
QA INDEPENDENT RESULTS: 32 PASS / 0 FAIL   (exit 0)
```

含 E12：IDLE→ACTIVE 开工边界推送 + 30min 去重。

### 1.5 正常边界消息仍推送（QA 新增独立验证 qa_boundary_normal.py，7 断言）

> 独立于研发脚本构造 fixture，验证修复不过滤正常边界消息：

```
── N1: IDLE→ACTIVE 开工边界仍推送 ──
  ✓ N1-1: 开工边界消息已推送
  ✓ N1-2: 开工消息无 __boundary__ 垃圾
── N2: ACTIVE→IDLE 空闲边界仍推送 ──
  ✓ N2-1: 空闲边界消息已推送
  ✓ N2-2: 空闲消息含今日完成数
  ✓ N2-3: 空闲消息无 __boundary__ 垃圾
── N3: 稳态 ACTIVE→ACTIVE 不推边界/无垃圾 ──
  ✓ N3-1: 无边界消息（稳态）
  ✓ N3-2: 无 __boundary__ 垃圾
BOUNDARY NORMAL RESULTS: 7 PASS / 0 FAIL   (exit 0)
```

**B1-F1 结论：修复有效，repro=False，正常推送无回归。**

---

## 2. B2 独立验证（提交 69093ec）

### 2.1 workspace_check.sh 核心逻辑审查（137 行）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 2.1.1 | 判定规则：workspace_kind 非白名单 + 管线 assignee + 活跃(ready/running) | ✅ | L59-95：SQL 限定 status IN ('ready','running') AND workspace_kind IS NOT NULL；Python 过滤 assignee ∈ PIPELINE_ASSIGNEES 且 wkind ∉ 白名单 |
| 2.1.2 | 白名单 worktree/scratch（含工程裁定注释） | ✅ | L45 `WORKSPACE_KIND_WHITELIST="worktree scratch"`；L16-23 注释解释 scratch 白名单理由（autopilot 自建 qa/va 卡均 scratch，防自伤噪声） |
| 2.1.3 | [CMD] 卡排除（双层防御） | ✅ | L68-74 PIPELINE_ASSIGNEES 无 autopilot（第 1 层）；L91-94 标题 `[CMD]` 前缀（大小写不敏感，第 2 层防御手动误设 assignee） |
| 2.1.4 | 仅 comment 告警不阻塞（观察期） | ✅ | L13-14 注释 + L128-129 `hermes kanban comment`；无 block/reclaim/archive 调用 |
| 2.1.5 | fail-open | ✅ | L39 `set -uo pipefail`（无 -e）；L50-53 DB 不存在 exit 0；L130 `|| log "comment $VID 失败"` 单卡失败继续 |
| 2.1.6 | 幂等（已有标记不重复告警） | ✅ | L104-118 `comment_exists()` 查 `body LIKE '%[workspace-check]%'`；L127 已存在则跳过 |
| 2.1.7 | PIPELINE_ASSIGNEES 与 discover.py 同源 | ✅ | L66-74 注释声明同源；实际比对（见 2.3）两处集合一致且均无 autopilot |

### 2.2 test_workspace_check.sh 独立重跑

```
bash scripts/test_workspace_check.sh
PASS=27 FAIL=0
ALL TESTS PASSED   (exit 0)
```

覆盖：dir 卡 flag / [CMD] 卡不 flag（含小写 [cmd]）/ worktree、scratch 不 flag / done 不 flag / 未知 kind flag / 非管线 assignee 不 flag / comment 幂等 / 缺 DB fail-open exit 0 / discover 4 处修复（手动卡发现、[CMD] 卡不发现、running+有效 claim 跳过、running+失效 claim 可接管）/ HERMES_KANBAN_DB 路径 / 内容注入（claim/wiki/超轮次 + 幂等守卫）。

### 2.3 discover.py 静态核对

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 2.3.1 | PIPELINE_ASSIGNEES 无 autopilot | ✅ | L24-30：仅 game-engine/game-qa/verifier/game-director/game-architect 5 个（含移除注释） |
| 2.3.2 | SUB_TASK_TITLE_PREFIXES 含 [CMD] | ✅ | L36-48：11 个前缀，末项 `"[CMD] "` |
| 2.3.3 | HERMES_KANBAN_DB 路径优先 | ✅ | L76-82：`os.environ.get("HERMES_KANBAN_DB") or ~/.hermes/kanban.db` |
| 2.3.4 | running + 有效 claim 守卫 | ✅ | L104-122：running 且 claim_lock 非空且 claim_expires > now → 跳过；ready 与 stale running 仍接管 |

### 2.4 实机核对（autopilot.log + kanban.db）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 2.4.1 | [workspace-check] 告警真实发生 | ✅ | autopilot.log 04:10-04:19 连续 tick 告警 dir 卡：t_aad6d422 / t_c36bd9e4 / t_eb49e276 / t_d7e6bdd2（本卡），"违规卡 ... (workspace_kind=dir, assignee=game-engine, status=running)" |
| 2.4.2 | 幂等（已有标记跳过） | ✅ | 04:10/04:13 对 t_aad6d422/t_c36bd9e4 "已有 [workspace-check] 标记，跳过（幂等）" |
| 2.4.3 | 告警 comment 落库 | ✅ | kanban.db task_comments 查到 6 条 [workspace-check] comment（t_d7e6bdd2/t_aad6d422×2/t_eb49e276/t_c36bd9e4/t_96cf339b），文案含"不在白名单（worktree scratch）…观察期仅告警不阻塞；请 OC 处置" |
| 2.4.4 | autopilot 主循环 fail-open 连续 tick | ✅ | autopilot cron（orchestrator profile，id 4e52405060a3，every 2m，enabled）4437 次运行 last_status=ok；log 显示 04:07→04:22 每 3 分钟连续轮询，workspace_check 挂在 dedup/stuck 之后 `|| true`（autopilot.sh L735） |

注：当前无活跃 [CMD] 卡（kanban.db 查询 `title LIKE '%[CMD]%' AND status IN ('ready','running')` = 空），[CMD] 不误报由测试套件 T1/T2b/T7c 覆盖。

### 2.5 autopilot.sh 挂载核对

- ✅ L735 `bash "$REPO_ROOT/scripts/workspace_check.sh" "$REPO_ROOT" || true`（dedup/stuck 之后）
- ✅ 手动建卡内容注入块（L104-121 区段）：注册后注入 [claim 要求] comment，幂等守卫（`body LIKE '%[claim 要求]%'`）——T10a-d 覆盖

**B2 结论：验收标准全部通过。**

---

## 3. 回归验证（B1 notify cron 不受 B2 影响）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 3.1 | crontab 行未变 | ✅ | root crontab：`*/2 * * * * bash /workspace/devPPL/scripts/notify_cron.sh >> .../notify_cron.log 2>&1` |
| 3.2 | notify_cron.sh 未被 B2 触碰 | ✅ | `git log -1 -- scripts/notify_cron.sh` → 40f6aaf（B1 原始提交），B2 提交 69093ec 不含此文件 |
| 3.3 | notify cron 实机存活 | ✅ | notify_state.db notify_events 显示 04:12/04:14/04:18 UTC 每 2 分钟 tick 并推送 t_4a3caf99 close-2 的 heartbeat_annex + milestone（last_sent_at 已更新）；token 缓存生效（kv_store feishu_token 03:54 缓存） |
| 3.4 | notify cron 日志不增长属正常 | ✅ | 成功 tick 无 stderr 输出（log 仅失败/边界/首跑时打），crontab `>>` 不产生写入 → 文件 mtime 停留在最后一次有输出（03:54 首跑）。实机数据证明 cron 每 2 分钟在跑 |
| 3.5 | legacy pytest 55 passed | ✅ | `python3 -m pytest tests/test_slice3_d1_qa.py -q` → **55 passed in 21.52s** |
| 3.6 | slice3_smoke 6 模块 | ✅ | `python3 tests/slice3_smoke_test.py` → ALL 6 MODULES PASSED（含 discover.py PIPELINE_ASSIGNEES=5 无 autopilot、SUB_TASK_TITLE_PREFIXES=11 含 [CMD]） |
| 3.7 | legacy 独立脚本 | ✅ | `python3 tests/scripts/test_staleness_guard.py` → G-T1 4/4 PASS（该脚本为独立断言脚本，模块级 exit 非 pytest 收集目标；pytest 全量收集会报 INTERNALERROR 属其自身设计，非本次改动引入） |

---

## 4. 分级判定对照（标准 §1.2 五步）

| 步骤 | 判定 |
|------|------|
| 用户可感知？ | 本次复测 0 缺陷，无待判项 |
| 功能阻断？ | — |
| 无 workaround？ | — |
| 安全漏洞？ | 无 |
| 结论 | 无发现 |

分级示例对照（§1.1）：B1-F1（原 MAJOR）经修复后复测 repro=False → 缺陷关闭；本次未发现新 BLOCKER/MAJOR/MINOR。

---

## 5. SLA 对照（§8）

本次为复测任务，无新 BLOCKER，不触发 4h/8h/24h SLA。

---

## 6. 结论

**PASS（无条件通过）**

- B1-F1：S1/S2 repro=False（exit 0），33 研发断言 + 32 QA 独立断言全绿，正常边界消息（开工/空闲）仍推送（QA 新增 7 断言全绿）→ 修复有效无回归
- B2：27/27 测试用例 PASS，workspace_check.sh 判定规则/[CMD] 排除/fail-open/幂等审查通过，discover.py 4 处修复静态核对通过，实机 autopilot log 与 kanban.db comment 证实告警落库且主循环 fail-open 连续 tick
- 回归：crontab 行、notify_cron.sh 未变，notify cron 实机每 2 分钟运行推送正常，pytest 55 passed + slice3_smoke 6 模块全过
- 发布门禁：BLOCKER=0，MAJOR=0，安全漏洞=0，无未裁定申诉 → **门禁通过**

## 7. 交付物

- 本报告：`docs/qa/retest-b1-f1-b2-workspace-check.md`
- 复测脚本（/tmp，不入库）：
  - `/tmp/qa_boundary_repro.py`（复用前次，S1/S2 repro 验证）
  - `/tmp/qa_notify_retest.py`（复用前次，32 断言）
  - `/tmp/qa_boundary_normal.py`（本次新增，正常边界 7 断言）
  - `/tmp/qa_bnd_dbg.py` / `/tmp/qa_db_check.py` / `/tmp/qa_cron_check.py` / `/tmp/qa_auto_cron.py`（本次辅助核对）
