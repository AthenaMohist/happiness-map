# FIX PRD — notify heartbeat 统计范围限定到当前开发链（不统计全局历史）

> 作者：许清楚（产品负责人） | 日期：2026-08-11 | 版本：v1.0
> 来源：[CMD] 指令卡通道（Frank 2026-08-11 裁定 2 类型化建链）
> 议题：FIX notify heartbeat 统计范围限定到当前开发链（不统计全局历史）
> 定位：B1 通知 cron（notify_check.py）的 heartbeat 统计口径缺陷修复。前置：B1 通知 cron（t_b3e1c93e，已交付）+ B1-F1（t_c36bd9e4，已交付）+ B3 指令卡通道（t_e4d2f205，已交付）。
> 北极星对齐：heartbeat 是 Frank 判断"autopilot 是否活着 + 当前在做什么"的唯一信号。统计范围错 = 信号失真 = Frank 对系统状态产生错误认知。本 FIX 让 heartbeat 只报**当前开发链**，不掺全局历史噪音。

---

## 0. 本 PRD 在整体规划中的定位

```
B1 通知 cron（已交付）      — notify_state.db + 事件推断 + work-gated heartbeat + 飞书 token 缓存
B1-F1（已交付）             — milestone 聚合路径过滤 __boundary__ 合成行
B3 指令卡通道（已交付）     — cmd_channel.sh + task_control + 类型化建链（[CMD] create dev）
本 PRD（FIX）              — heartbeat 统计范围从「全局历史」改为「当前开发链」
```

**一句话定位**：heartbeat 数字（活跃N/跑N/堵N/今完N）目前从 `pipeline_steps` 全表统计——那是**全局历史**（所有跑过管线的任务，含旧链、已完成、已归档）；改成从**当前开发链**（kanban 中 `[DEV-*]` 链卡）统计，只反映现在正在进行的开发工作。

---

## 1. 背景与痛点

### 1.1 现状：heartbeat 统计源是全局历史

`notify_check.py` 的 heartbeat 统计链路：

```
read_pipeline_steps(state_db)  → pipeline_steps 全表（所有注册过管线的任务，永不清除）
compute_counts(steps)          → 活跃N/跑N/堵N/今完N（按 task 去重）
is_active(steps, cmd_cards)    → 有 pending/running/blocked 步骤 或 未归档 [CMD] 卡 → ACTIVE
```

### 1.2 缺陷：heartbeat 看不到当前开发链

B3 类型化建链（Frank 2026-08-11 裁定 2）上线后，开发任务走 `[CMD] create dev` → **sequential 链卡**：

| 链卡 | assignee | idempotency_key | 状态 |
|------|----------|-----------------|------|
| `[DEV-PRD] <议题>` | game-director | `dev-<spec_hash>-prd` | 第 1 棒 |
| `[DEV-ARCH] <议题>` | game-architect | `dev-<spec_hash>-arch` | 前棒 done 后建 |
| `[DEV-DEV] <议题>` | game-engine | `dev-<spec_hash>-dev` | 前棒 done 后建 |

**但这些链卡不会进入 pipeline_steps**——`discover.py` 的 `SUB_TASK_TITLE_PREFIXES` 明确排除 `[DEV-` / `[ROUNDTABLE-` / `[CMD] `（第 2 道闸，防误注册）。后果：

1. **统计口径错误**：heartbeat 数字统计的是 pipeline_steps 全表（全局历史），而**当前开发链的进度完全不在里面**。例：当前 board 有 2 条活跃开发链（t_f86c3398 `[DEV-PRD] FIX notify heartbeat` running、t_daff6195 `[DEV-ARCH] MEM-001` running），但 pipeline_steps 里只有旧 Slice2 任务（t_4a3caf99 / t_7d9c2145，均 done）→ heartbeat 显示 `活跃0 跑0 堵0`，与真实工作完全脱节。
2. **ACTIVE 判定失灵**：`is_active()` 只看 pipeline 活跃步骤 + 未归档 [CMD] 卡。开发链在跑时：[CMD] 卡已被消费归档、pipeline_steps 无活跃步骤 → **判定 IDLE → heartbeat 静默**。Frank 在开发链进行中收不到任何心跳，无法区分"没活干"和"系统死了"——这正是 B1 裁定要解决的核心问题（work-gated heartbeat 的开启/关闭条件）。
3. **今完N 被历史污染**：`今完N = COUNT(*) WHERE status='done' AND finished_at >= 今日零点`，统计的是**全部历史任务今天完成的步骤数**（含旧链补跑、误注册、已归档任务的残留），不是当前开发链今天完成的卡数。

### 1.3 与 Frank 需求映射

| Frank 裁定 | 现状 | 本 FIX |
|-----------|------|--------|
| "当前 x 卡在跑，x 卡已完成"（F1） | heartbeat 报的是全局历史，当前链卡不可见 | 统计范围 = 当前开发链卡 |
| "有明确的开启和关闭条件"（裁定 1） | 开发链在跑时判定 IDLE → 静默 | ACTIVE 判定纳入开发链在途卡 |
| "任务做完了自动停"（裁定 1） | 链卡 done 不影响 work_state | 链卡全部终态 → IDLE → 停 heartbeat |

---

## 2. 目标与范围

### 2.1 核心目标

1. **统计范围限定到当前开发链**：heartbeat 数字只统计 kanban 中在途/今日完成的 `[DEV-*]` 链卡，不统计 pipeline_steps 全局历史
2. **ACTIVE 判定纳入开发链**：有在途 `[DEV-*]` 链卡（ready/running/blocked）即 ACTIVE → 每 tick 推 heartbeat
3. **今完N 口径修正**：只统计当前开发链今天完成的卡数（按 kanban completed_at），不掺历史任务
4. **向后兼容**：旧逻辑（pipeline_steps 活跃步骤 + 未归档 [CMD] 卡）仍计入 ACTIVE 判定；无开发链时保持原行为

### 2.2 覆盖范围

| # | 范围 | 现状 | 改动 |
|---|------|------|------|
| 1 | heartbeat 数字统计（活跃N/跑N/堵N/今完N） | pipeline_steps 全表 | kanban 当前开发链卡 |
| 2 | ACTIVE 判定 | pipeline 活跃步骤 + [CMD] 卡 | + 在途 [DEV-*] 链卡 |
| 3 | 边界消息（开工/空闲） | 用旧 counts | 用新 counts |
| 4 | heartbeat 附注（annex） | 仅 pipeline 事件 | + 链卡状态迁移事件（可选，见 P1） |
| 5 | 测试 | test_notify_check.py（T1-T10） | 新增链卡口径用例 |

### 2.3 定义：什么是"当前开发链"

**当前开发链 = kanban 中 idempotency_key 以 `dev-` 开头的链卡集合**（cmd_channel 类型化建链产物），满足：

- `[DEV-*]` 标题 + `dev-<spec_hash>-<step>` 幂等键（DEVELOPMENT_CHAIN 三棒：prd/arch/dev）
- **在途卡**：status ∈ (ready, running, blocked) → 计入 活跃N/跑N/堵N，且使系统 ACTIVE
- **今日完成卡**：status=done 且 completed_at ≥ 今日零点（本地时区）→ 计入 今完N
- **排除**：archived（归档即退出统计）、done 但非今日（历史完成不报）

---

## 3. 非目标（明确不做）

| # | 不做 | 理由 |
|---|------|------|
| N1 | 不清理/不迁移 pipeline_steps 存量数据 | 存量是全局历史，本 FIX 只是**不再统计**它，不删数据（保留审计） |
| N2 | 不把 [DEV-*] 链卡重新注册进 pipeline_steps | discover 排除集是 R2 四道闸的安全设计（防误注册/重复执行），不能回退 |
| N3 | 不改 cmd_channel / discover / autopilot 主循环 | 本 FIX 只动 notify_check.py（通知 cron 独立脚本），autopilot 零改动约束不变 |
| N4 | 不新增通知渠道/不改变飞书消息格式 | 格式 `[AP HH:MM] 活跃N 跑N 堵N 今完N | 附注`（≤80 字）不变，只改数字来源 |
| N5 | 不为历史任务补报里程碑 | 已 done 的历史任务不追溯通知 |
| N6 | 不处理 [ROUNDTABLE-*] 链卡的统计 | roundtable 链卡是发言链（无物理产物），不属"开发链"；但**在途 roundtable 卡是否影响 ACTIVE** 需裁决（见 §7 待裁决） |

---

## 4. 需求清单（按优先级）

### P0 — 统计范围修正（核心，MVP-FIX）

| ID | 需求 | 内容 | 验收要点 |
|----|------|------|---------|
| F-1 | 读取当前开发链卡 | notify_check.py 新增 `read_dev_chain_cards(kanban_db)`：查 tasks 表 `idempotency_key LIKE 'dev-%'`，返回 (task_id, title, status, completed_at)。kanban 缺失/异常 → 返回 []（fail-open） | 只读 kanban.db，绝不写；链卡识别准确 |
| F-2 | 统计口径切换 | `compute_counts()` 改为接收链卡列表：活跃N=在途(ready/running) 卡数、跑N=running 卡数、堵N=blocked 卡数、今完N=done 且 completed_at≥今日零点(本地时区) 卡数。pipeline_steps 不再作为数字统计源 | 数字与 board 实况一致（§5 AC-1~AC-4） |
| F-3 | ACTIVE 判定纳入开发链 | `is_active()` 增加：存在在途 [DEV-*] 链卡（ready/running/blocked）→ ACTIVE。原条件（pipeline 活跃步骤、未归档 [CMD] 卡）保留 | 开发链跑 → 每 tick 推 heartbeat；全 done/archived → IDLE 静默 |
| F-4 | 边界消息适配 | 开工消息 `🟢 autopilot 开工: 活跃N 跑N 堵N`、空闲消息 `⚪ autopilot 空闲: 全部任务完成（今日完N）` 使用新 counts | 数字与 heartbeat 口径一致 |
| F-5 | 配置项 | notify.json 增加 `heartbeat.stats_scope: "chain"`（默认，新口径）/ `"legacy"`（旧口径，回退开关） | 一键回退旧行为（逃生阀） |
| F-6 | 测试 | test_notify_check.py 新增 T11+：① 有在途链卡 → ACTIVE + heartbeat 数字正确 ② 链卡 done 今日 → 今完N+1 ③ 链卡 archived → 不计 ④ 无链卡（纯 legacy）→ 原行为不回归 ⑤ legacy 回退开关生效 | 新增用例 ≥5，存量 T1-T10 全绿 |

### P1 — 链卡状态迁移附注（增强，MVP-FIX 后）

| ID | 需求 | 内容 | 验收要点 |
|----|------|------|---------|
| F-7 | 链卡状态迁移事件 | pipeline_snapshot 纳入链卡状态（(task_id, step_name='card')），diff 出 ready→running→done/blocked 迁移 → 作为 heartbeat 附注（如 `t_f86c3398 prd running`），走 event_hash 30min 冷却 | 附注只显示当前链卡变化，不重复刷屏 |
| F-8 | 清理适配 | cleanup() 对链卡 snapshot 按 7 天滑动窗口 + 非活跃链卡清理 | 与现有清理语义一致 |

---

## 5. 验收标准

### 5.1 判定公式对照（QA 标准 §1.2）

- **缺陷性质**：统计口径错误（MAJOR，用户可见——Frank 依赖 heartbeat 判断系统状态，口径错误导致错误认知）
- **分级判定**：不涉及安全漏洞；属功能正确性缺陷，MAJOR 级（影响 Frank 对 autopilot 状态的判断）

### 5.2 验收用例

| # | 场景 | 前置 | 期望结果 |
|---|------|------|---------|
| AC-1 | 当前有在途开发链 | kanban 有 `dev-<hash>-prd` 卡 status=running | ACTIVE；heartbeat `活跃1 跑1 堵0 今完N`（N=今日已完成链卡数） |
| AC-2 | 开发链有多棒在途 | prd done + arch running + dev ready | `活跃2 跑1 堵0 今完1`（prd 今日 done 计入今完） |
| AC-3 | 全局历史不统计 | pipeline_steps 有旧任务今日 done（如 t_4a3caf99 finished_at 今天） | 今完N **不包含**该历史任务（它不是 dev-* 链卡） |
| AC-4 | 链卡归档退出统计 | 链卡 status=archived | 不计活跃/跑/堵/今完；全部归档 → IDLE |
| AC-5 | 开发链完成自动停 | 链卡全部 done（今日） | 空闲边界消息 `今日完N` 含今日完成卡；后续静默 |
| AC-6 | 纯 legacy 不回归 | 无 dev-* 链卡，仅 pipeline 活跃步骤 | 原行为：ACTIVE 判定 + 数字来自 pipeline（stats_scope=legacy 或自动回退） |
| AC-7 | fail-open 不崩 | kanban.db 缺失 / 读异常 | 链卡=[]，不抛异常，不阻塞其他 emit 路径 |
| AC-8 | 格式不变 | 任意场景 | heartbeat ≤80 字，`[AP HH:MM]` 前缀不变 |

### 5.3 SLA 对照（QA 标准 §8）

- MAJOR 级：8h 定位 + 24h 方案（本 PRD 即方案，已完成）

---

## 6. 约束

| # | 约束 | 来源 |
|---|------|------|
| C1 | autopilot 主循环零改动（notify cron 独立运行） | B1 设计约束 |
| C2 | fail-open：任何失败不阻塞、不重试循环、退出码 0 | B1 设计约束 |
| C3 | 只读 pipeline_state.db / kanban.db，只写 notify_state.db | B1 设计约束 |
| C4 | 飞书 token 缓存（notify_state.db kv_store，过期才重换） | B1 验收 1 |
| C5 | discover 排除集（[DEV- 等）不回退 | R2 四道闸安全设计 |
| C6 | 时间基准：今完N 按**本地时区**（Asia/Shanghai）今日零点；现有 finished_at 比较为 UTC——需统一为配置 timezone（notify.json timezone 字段，默认 Asia/Shanghai） | 口径一致性 |

---

## 7. 待 Frank 裁决（1 项）

| # | 点 | 建议 |
|---|-----|------|
| D1 | **[ROUNDTABLE-*] 在途卡是否计入 ACTIVE？** 发言链（A/B/C roundtable）也在跑，但非"开发链"。若不计，roundtable 进行中心跳静默（与开发链同病）。若计，heartbeat 在 roundtable 期间也推，但统计数字只含 dev-* 链卡 | 建议**计入 ACTIVE**（有活干就报活），统计数字仍只含开发链（口径纯净）。P0 范围默认不含，D1 裁定后 0.5h 内可加 |

---

## 8. 工时估算

| 模块 | 工时 |
|------|:---:|
| F-1 读链卡 + F-2 统计口径 | 2h |
| F-3 ACTIVE + F-4 边界消息 | 1h |
| F-5 配置项 | 0.5h |
| F-6 测试（新增 ≥5 用例 + 回归） | 1.5h |
| F-7/F-8 附注增强（P1） | 1.5h |
| **合计** | **6.5h（P0 5h + P1 1.5h）** |

---

## 9. 交付物

| 交付物 | 路径 |
|--------|------|
| 本 PRD | `docs/prd/fix-notify-heartbeat-chain-scope-prd.md` |
| （后续）实现 | scripts/notify_check.py + config/notify.json + scripts/test_notify_check.py |

---

## 附：与本 FIX 相关的既有文档

- B1 通知 cron 验收：`docs/qa/notify-cron-smoke-verification.md`
- R2 裁定落地设计（heartbeat work-gated + 类型化建链）：`docs/roundtables/b-autopilot-oc-relationship/2026-08-11-r2-rulings-design.md`
- B3 指令卡通道验收：`docs/qa/retest-b3-cmd-channel.md`
- discover 排除集（SUB_TASK_TITLE_PREFIXES）：`pipeline/discover.py`
