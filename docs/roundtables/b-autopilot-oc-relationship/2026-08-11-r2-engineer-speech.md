# B 类 Roundtable R2 — engineer 发言（第三棒）

**身份**：engineer（寇豆码）
**日期**：2026-08-11
**议题**：指令卡通道实现 + notify cron 工程评估
**立场**：从实现者角度，逐条验证代码、给出落地结构和工期判断。不追求与前置发言一致。

---

## 〇、先说结论（TL;DR）

1. **architect 的 discover bug 属实**（我读了 discover.py 逐行确认），但**dedup_check.sh 是比 discover 更危险的遗漏路径**——它会主动归档 `[CMD]` 卡，把命令静默吞掉。修复必须同时覆盖这两处 + stuck_check 防御。
2. **cmd_channel.sh 可行**，我给出具体结构（解析器/处理器/归档）、与 autopilot.sh 的挂载点（主锁之前）、三层幂等保证。**关键坑：cmd_channel 必须挂在 autopilot.sh 主 flock 之前执行**，否则"共享 flock"会变成死锁式跳过，命令永远不被消费。
3. **task_control 表可行**，与现有 schema 零冲突（CREATE TABLE IF NOT EXISTS 即可，VALID_STATUSES 已含 cancelled）。abort 级联要"reclaim + 归档 + 全步 cancelled"，且**幂等**；pause 是软断点。契约里"叫停=状态标记不 kill"必须细化：abort 不是不 kill，是不 SIGKILL、由 dispatcher 正常终止 agent。
4. **notify_state.db 独立库我同意**——撤销我 R1 的 pipeline_events 表主张。notify 需要自己的 emit/cooldown 审计状态，写进 pipeline_state.db 违反"单一写入者"契约。但**有一个 architect 没提的坑：upsert_step 用 INSERT OR REPLACE，snapshot diff 的 key 绝不能用 rowid**，必须用 (task_id, step_name)。
5. 工期估算：通知 cron ~0.5d + cmd_channel 通道（含 discover/dedup 修复，一个原子变更集）~0.5d + task_control ~0.25d + workspace_check ~0.25d，合计 **~1.5 人日**，串行实施 2~3 天。

---

## 一、议题 B：discover 误注册 bug — 确认属实 + 遗漏路径

### 1.1 代码验证（真 bug，非推测）

`pipeline/discover.py`：

- L25 `PIPELINE_ASSIGNEES` 已含 `"autopilot"` ✅
- L29-40 `SUB_TASK_TITLE_PREFIXES` 无 `"[CMD] "` 前缀 ✅
- 结论：OC 建一张 `[CMD] roundtable B` 卡（assignee=autopilot，status=ready/running，workspace_path=/workspace/devPPL）→ L107 `_is_sub_task` 返回 False → L111 assignee 命中集合 → L115 未注册 → 进入 discovered → L137-141 `register_discovered_task` **硬编码** `step_name="dev", assigned_agent="game-engine"` → 下一 tick autopilot 给 game-engine 建 `dev: <cmd卡id>` 卡。

**后果**：命令卡被当成一个普通 dev 任务派给研发，研发会去"实现"一条命令。而且这张 dev 卡 assignee=game-engine 是真 profile，dispatcher 真会派发。这比"卡滞留"严重——是命令被错误执行。

### 1.2 遗漏路径（architect 的修复方案不完整）

architect 说修复 = discover.py 加前缀 + cmd_channel 先消费（双闸）。**不够，还有两条**：

**① dedup_check.sh（危险，必须修）**。L65-118 按 assignee 分组 + title startswith 判定重复，命中的重复卡会被 **L163 直接归档**（`UPDATE tasks SET status='archived'`）。`[CMD]` 卡 assignee=autopilot 自成一组，但两条命令标题只要互相 startswith 就成组——例如 `[CMD] roundtable B` 与 `[CMD] roundtable B: 关于分级判定`——后一条被当重复卡**归档**，命令被静默吞掉，连告警都没有。**这是"命令丢失"路径，比 discover 误注册更隐蔽**。修复：dedup_check 的重复分组必须跳过 `[CMD]` 前缀（title 归一化时先剔除/跳过）。

**② stuck_check.sh（防御性，建议修）**。L74-143 只扫 status='running'。`[CMD]` 卡 assignee=autopilot 不是真实 profile（我验证了 `hermes profile list` 无 autopilot），dispatcher 永不派发，永远不会 running → 默认安全。但加一行排除是零成本的防御，建议顺手加。

**③ 大小写旁路（低成本，建议修）**。`_is_sub_task` 用 `startswith` 大小写敏感。OC 手滑写 `[cmd]` 或全角 `［CMD］` 直接旁路双闸。建议：`title.upper().startswith("[CMD] ")` + 建卡规范文档强制大写。

### 1.3 双闸是否足够？

足够，但顺序重要：**cmd_channel 消费必须在 discover 之前**（同 tick 内）。双闸的意义是：即使某 tick 时序错乱，前缀排除也能兜底；即使前缀漏了，已归档的卡 discover 也扫不到。两个独立故障点同时失效才出事，可接受。但注意：**双闸是"消费侧"的修复，注册侧还有一个存量 bug**——`register_discovered_task` 硬编码 dev/game-engine（R1 我提过），OC 手动建 assignee=game-qa 的普通卡仍会被注册成 dev 步。本次不动，记 backlog。

---

## 二、议题 A：cmd_channel.sh 工程实现

### 2.1 实现结构（建议 ~180 行，复刻 dedup_check.sh 模式）

```
scripts/cmd_channel.sh
├─ 1. flock（与主循环同一 LOCKFILE /tmp/autopilot.lock，独立 fd，fail-open）
├─ 2. Parser：SELECT id, title, body FROM tasks
│        WHERE title LIKE '[CMD] %' AND status IN ('ready','running','blocked','todo')
│        ORDER BY created_at
│        （过滤建议：workspace_path = REPO_ROOT OR IS NULL，防多项目共享库误食）
├─ 3. 对每张卡（按 created_at 顺序）：
│     a. CAS 消费：UPDATE tasks SET status='archived'
│        WHERE id=? AND status IN (活跃) → rowcount==1 才继续（单次消费核心）
│     b. 解析命令：title 第二段 + body
│        roundtable / create / pause / resume / abort / custom(v2)
│     c. 处理器：每类一个函数（薄路由，流程知识引用 constants.py + contracts.jsonl，
│        不复制——用 python3 -c import，同 autopilot.sh 现有模式）
│     d. 回执：hermes kanban comment "[cmd-channel] 成功/失败: ..."（comment_exists 幂等）
│     e. 失败：comment 原因 + status='blocked'（人工介入，v1 不做自动重试）
└─ 4. 滞留告警：created_at < now-6min(3 tick) 且仍活跃的 [CMD] → 告警（走 notify 通道）
```

### 2.2 与 autopilot.sh 的集成点 — 这里有个致命坑

architect 说"与主循环共享 flock"。**如果理解为"在 autopilot.sh 主锁内调用 cmd_channel.sh"，实现就死了**：

- autopilot.sh L46 `exec 200>"$LOCKFILE"; flock -n 200` 已持锁。
- 子进程 cmd_channel.sh 若再 `exec 200>...; flock -n 200`，是**新的 open file description**，flock 与父进程锁冲突 → 必然失败 → fail-open 跳过 → 命令永远不被消费（每 tick 都如此）。

**正确挂载点**：cmd_channel.sh 放在 autopilot.sh **主 flock 获取之前**（L46 之前），自己用独立 fd（如 201）`flock -n` 同一 LOCKFILE，fail-open：

```
exec 201>"$LOCKFILE"; flock -n 201 || exit 0   # 上一个 autopilot 实例超时未退 → 本轮跳过
... 消费 [CMD] ...
flock -u 201
# 然后 autopilot.sh 正常走 L46 主锁 → L76 discover
```

效果：单 cron 入口（不改 cron 配置）、时序天然保证（consume → discover）、与主循环互斥（同 LOCKFILE）。若上一个 autopilot 实例还在跑（tick 超时），cmd_channel fail-open 跳过，命令最多延迟 1 个 tick（2 分钟），可接受。

### 2.3 幂等 / 单次消费在代码层怎么保证（三层）

1. **flock 串行**：任意时刻只有一个消费者。
2. **CAS 消费**：`UPDATE ... WHERE id=? AND status IN (活跃)` 查 rowcount。即使有人手动并发跑，只有一个拿到 rowcount=1。
3. **副作用幂等**：建卡一律走 `kanban_ensure_card`（lib_kanban_dedup.sh 已有 idempotency-key）；comment 用 `comment_exists` 守卫（dedup_check.sh L127-140 已有同款）。重复消费 → 卡不重复建、comment 不重复留。

**消费顺序决策**：先归档（CAS）→ 再执行 → 最后回执。理由：副作用有幂等键，重跑安全；若执行中崩溃，命令"丢失"但 OC 可补发（卡还活着就是没消费，卡归档了就是已消费）。反过来先执行后归档，崩溃在中间 = 副作用已发 + 卡未归档 → 下 tick 重跑 → 重复副作用。归档先行的失败模式可恢复性更好。

### 2.4 补充风险（architect 未提）

- **dispatcher 竞态**：`[CMD]` 卡 assignee=autopilot 不是真实 profile，dispatcher 静默丢弃（已验证 profile list 无 autopilot）→ 卡安全躺在 ready 等 cmd_channel。**但这是隐式依赖**：未来若有人注册 autopilot profile，dispatcher 会把它当任务派发。防御建议：OC 建 [CMD] 卡时用 `initial_status='blocked'`（dispatcher 不拾取），cmd_channel 消费时翻 archived。一行防御，写进契约。
- **命令卡生命周期**：消费后 status=archived，dedup/discover/stuck 三处排除后永不复活。滞留告警依赖 created_at，注意 cron 宕机恢复后要能识别 3 tick 前的滞留卡（按 created_at 算，不按"连续 tick 数"，天然免疫宕机）。

---

## 三、议题 C：task_control 表

### 3.1 与现有 schema 兼容性 — 零冲突

- checkpoint.py `SCHEMA_SQL`（L12-39）加 `CREATE TABLE IF NOT EXISTS task_control (...)`，幂等，存量库无迁移（可选 bump user_version=3 做记账）。
- `VALID_STATUSES`（L41）已含 `cancelled` ✅ → abort 级联直接 `upsert_step(status='cancelled')`，无需扩枚举。
- `get_active_tasks`（L223-234）只取 pending/running → 全步 cancelled 后任务自然退出主循环 ✅。
- 唯一注意：`upsert_step` 是 INSERT OR REPLACE（L162），cancelled 会覆盖原行——error_msg 要带 `aborted: <reason>` 保留审计信息。

### 3.2 determine_next_action 入口检查的具体实现

放在 `determine_next_action`（state.py L550）**最顶部、_complete 判断之前**（约 12 行）：

```python
def determine_next_action(task_id, current_step, contracts, db):
    # ── [CMD] 控制面检查：pause = 软断点；abort = 级联兜底 ──
    ctrl = db.get_task_control(task_id)
    if ctrl:
        if ctrl["control_state"] == "paused":
            return {"action": "wait", "step": current_step and current_step.get("step_name"),
                    "task_id": task_id, "detail": f"已暂停: {ctrl.get('reason','')}"}
        if ctrl["control_state"] == "aborted":
            _apply_abort_cascade(task_id, db)   # 幂等：已 cancelled 则 no-op
            return {"action": "wait", "step": None, "task_id": task_id,
                    "detail": f"已中止: {ctrl.get('reason','')}"}
```

- **必须放最顶部**：L644-650 的 running/pending 分支会 `upsert_step(status='running')` 触碰步骤，pause 时绝不能走到那。
- pause 返回 wait：autopilot.sh 的 wait 分支本来就是 no-op（L489-491），零新增 shell 代码 ✅。

### 3.3 abort 级联逻辑（幂等，主路径在 cmd_channel，state.py 只做兜底）

主路径：cmd_channel.sh 消费 abort 命令时直接执行；state.py 的检查是第二道保险（防 cmd_channel 与主循环交错时漏网）。级联：

```python
def _apply_abort_cascade(task_id, db):
    # 1. 所有非 done 步骤置 cancelled（done 保留历史；不满足"全部完成"判定 → 不会误报 complete）
    for s in db.get_all_steps(task_id):
        if s["status"] not in ("done", "cancelled"):
            db.upsert_step(task_id, s["step_name"], "cancelled", error_msg="aborted by command")
    # 2. kanban 卡：running 先 reclaim（best-effort）→ 归档（active-status 守卫，同 dedup_check L163）
    # 3. comment 通知 [autopilot: ABORTED] <reason>
```

关键点：
- **幂等**：二次执行时所有步骤已 cancelled → 循环 no-op；归档带活跃状态守卫 → rowcount=0 跳过。
- **与"叫停=状态标记不 kill"契约的关系，必须向 Frank 说清楚**：abort 不是不 kill，是**不 SIGKILL**。reclaim 让 dispatcher 正常终止 agent 会话；在途 worker 最多跑完当前会话（分钟级~小时级），之后不再有新卡、不再推进。pause 才是不动 worker 的纯软断点。两者语义不同，v1 文档必须写清。
- **edge**：abort 一张已在 close 阶段的卡 — 级联把 close 步置 cancelled，归档 kanban 卡。close 子步骤（close-1 kanban complete 等）不会执行，因为该 task 已不在活跃集。可接受，记录为已知行为。

### 3.4 resume 语义

`task_control` 行：pause 写入 (paused, reason, updated_at)；resume 置 `normal`（或删行）。determine_next_action 只认 paused/aborted，normal = 不拦截。abort 后无 resume（v1 语义：abort 是终态，OC 需重建任务）。

---

## 四、议题 D：notify_state.db 工程评估

### 4.1 先表态：撤销我 R1 的 pipeline_events 主张，同意独立 notify_state.db

理由（R2 想清楚了的）：notify 需要**自己的审计状态**——已 emit 记录、cooldown 时间戳、snapshot 基线。这些写进 pipeline_state.db 会让"只有 autopilot 写"的契约破功，而且 notify 的保留策略（7 天清理）与 pipeline 的长期状态语义冲突。独立库让 fail-open 隔离彻底：notify cron 坏了/卡了，pipeline_state.db 完全无感。**承认 R1 判断错了**，architect 的契约洁癖在这里是正确成本。

### 4.2 WAL 只读短事务 — 可行

- pipeline_state.db 已是 WAL（checkpoint.py L89）。SQLite WAL 下 1 writer + N reader 并发，读者不阻塞写者。
- 实现：`sqlite3.connect("file:<path>?mode=ro")` + `PRAGMA query_only=ON` → 物理只读，写坏库的风险为零。
- 短事务：connect → 几条 SELECT → close。不要跨 tick 持连接。

### 4.3 snapshot diff 算法 — 有一个 architect 没提的坑

**坑：`upsert_step` 用 INSERT OR REPLACE（checkpoint.py L162）→ 每次更新都是删行重建 → rowid 变化。snapshot 的 key 绝不能用 rowid，必须用 (task_id, step_name)。**

算法（纯 Python，可单测）：
1. 读全表 pipeline_steps → `{(task_id, step_name): (status, finished_at)}`。
2. 与 pipeline_snapshot 对比：
   - 新 key → "步骤开始"
   - 同 key 状态变化 → "状态迁移"（running→done=完成里程碑；→failed=异常事件）
   - 全 task 所有步 done → "管线完成"
3. 写回新 snapshot。

两个必踩的 edge：
- **首跑基线**：第一次运行只写 snapshot 不 emit——否则全表每一行都像"新事件"，首跑瞬间刷屏。这个必须写进实现。
- **瞬态漏报**：跨 tick 的瞬态（一个 2min tick 内 failed→done）diff 看不到。管线步耗时分钟级，漏报概率低；异常主信号走 `[AUTOPILOT:` comment 扫描兜底（architect 的"辅助信号源"设计正好补这个洞）。接受，文档写明。

### 4.4 event_hash 冷却

- `md5(task_id|step|status|event_type)`，不含 detail ✅（detail 变化不重复推，正确）。
- dedup_cooldown 表存 (hash, last_emitted_at)，30min 内跳过。
- **发送失败不写 cooldown**（否则失败后 30min 静默）。webhook 失败 → 日志 + 下 tick 重试。
- 7 天清理：DELETE FROM notify_events WHERE created_at < now-7d，cron 每 tick 顺带跑（或每天一次）。

### 4.5 三条 emit 路径

- **exception**：pipeline_steps →failed 迁移 + kanban comment 含 `[AUTOPILOT: ERROR/BLOCK/ROLLBACK/GATE/AWAIT` 或 `[stuck-check]` 标记 → 实时推。
- **milestone**：步骤 done / 新任务注册 / 管线完成，聚合 ≤1 条/tick。
- **heartbeat**：`[AP 时间] 活跃N 跑N 堵N 今完N | 变化附注`（≤80 字）——本体纯数字**每 tick 必推不去重**；`| 变化附注` 部分走 event_hash 30min 冷却（architect 的语义二分法正确，heartbeat 去重会把 Frank 要的"每 tick 心跳"去没了）。
- 三条共用同一 webhook（feishu），webhook 配置在 config/notify.json（webhook url + heartbeat_enabled + silent_window + tz）。

### 4.6 与 autopilot 的 fail-open 隔离

- 独立 cron entry（deliver=local，no_agent 脚本或 script cron 调用 notify_check.py）。
- 只读 pipeline_state.db + kanban.db；只写自己的 notify_state.db。
- 自身崩溃/网络失败 → 静默 + 下 tick 重试，绝不影响主循环。
- 实现形态建议 **Python**（~200 行 scripts/notify_check.py）：双库 sqlite + md5 + diff 逻辑用 bash 写会很痛苦且易错。这不算"新增脚本模式"违背——dedup/stuck 是纯 SQL 逻辑所以 bash 合适，notify 有 diff/聚合算法所以 Python 合适，按复杂度选型。

### 4.7 与"不骚扰"红线的张力（产品已提，我补充工程面）

- heartbeat 720 条/天是 Frank 亲口要的，红线为他让路；但 silent_window 必须默认开（建议 22:00-08:00）+ heartbeat_enabled 逃生阀。
- 80 字硬约束：`[AP 08:00] 活跃3 跑2 堵1 今完5 | 无` 才 ~30 字，有空间。时区建议配置化默认 Asia/Shanghai（现有日志全 UTC，但飞书给人看，CST 直观）。

---

## 五、工程风险总评 + 测试计划

### 5.1 竞态 / 幂等清单（按风险排序）

| 风险 | 防线 |
|------|------|
| [CMD] 卡被双消费 | flock + CAS rowcount + 副作用幂等键（三层） |
| [CMD] 卡被 discover 误注册 | discover 前缀排除（第一闸）+ consume-first 顺序（第二闸） |
| [CMD] 卡被 dedup 误归档 | dedup_check 排除 [CMD]（**必须修，最高危遗漏**） |
| notify 双发 | event_hash + cooldown；失败不写 cooldown |
| notify 首跑刷屏 | 首跑只建基线不 emit |
| pause/abort 同 tick 到达 | 单消费者 flock 串行 + created_at 排序，天然有序 |

### 5.2 迁移

全部 `CREATE TABLE IF NOT EXISTS` → 存量库零迁移零停机。notify_state.db 是全新库，自建 schema。task_control 无存量数据要迁。

### 5.3 测试计划（每个模块 3 条核心用例）

- **cmd_channel.sh**：HERMES_KANBAN_DB 指向 fixture 库（现有测试模式）+ PATH shim mock hermes CLI。断言：①同一 [CMD] 卡跑两次只消费一次；②roundtable 命令重复执行不重复建卡（幂等键命中）；③消费顺序 = created_at 升序。
- **task_control**：pytest 直调 determine_next_action（temp sqlite + 假 contracts，tests/ 已有 harness）。断言：①paused → 永远 wait 不推进；②abort → 全非 done 步 cancelled + 二次调用幂等；③resume → 恢复正常推进。
- **notify diff**：纯函数测试 (snapshot_A, snapshot_B) → 期望事件列表；首跑基线测试；INSERT OR REPLACE rowid 变化后 diff 仍正确（key 用 task_id+step_name 的回归用例，专门防这个坑）。

### 5.4 实施顺序微调

产品定的顺序：通知 cron → Gap3 + Gap2+5 → 指令卡通道。**我要求一个原子性约束**：指令卡通道（cmd_channel.sh + discover 前缀 + dedup 排除）必须**同一个变更集落地**，不能分 PR——否则中间态（通道先上/修复后上）存在 [CMD] 卡被误注册/误归档的窗口期。workspace_check 是纯新增扫描脚本、与 [CMD] 无耦合，可插队任何位置。

---

## 六、独立判断（不追求一致）

1. **确认 architect 的 bug 发现**，但修复清单不完整：dedup_check 排除比 discover 前缀更紧急（一个是"误执行"、一个是"静默吞命令"，都得出）。
2. **同意 notify_state.db 独立**，明确撤销 R1 主张。这是 R2 我改判的唯一一项，理由见 4.1。
3. **反对"cmd_channel 挂在主锁内"的实现理解**——必须挂在主 flock 之前（2.2 的 flock 陷阱），否则命令通道形同虚设。这是 architect 方案里唯一会在实现时踩死的坑。
4. **abort 语义要细化**：状态标记 + reclaim + 归档，不是"不 kill"。Frank 的"能叫停"需求，用 pause（软）和 abort（硬）两级满足，v1 就够。
5. **工期**：~1.5 人日（通知 cron 0.5d、[CMD] 通道原子集 0.5d、task_control 0.25d、workspace_check 0.25d），串行 2~3 天。若开工后 diff 算法和首跑基线的坑消耗超预期，最多 +0.25d，不会失控。

## 附：验证过的代码事实（本发言依据）

- `hermes profile list`：**无 autopilot profile** → [CMD] 卡 assignee=autopilot 不会被 dispatcher 派发（隐式安全，也是隐式依赖）。
- discover.py L25/L29-40/L107/L111/L137-141：bug 确认。
- dedup_check.sh L65-118/L163：归档路径确认 → 必须排除 [CMD]。
- checkpoint.py L41/L89/L162/L223-234：cancelled 已支持、WAL 已开、INSERT OR REPLACE rowid 坑确认。
- state.py L550/L644-650/L765：task_control 检查点位置确认。
- config/contracts.jsonl：10 步 dev→close 全量存在，薄路由引用来源确认。
