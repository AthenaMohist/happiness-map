# [B3] 指令卡通道 — 验证记录（cmd_channel.sh + task_control + 类型化建链）

> 任务: `t_e4d2f205` `[B3] 指令卡通道 — cmd_channel.sh + task_control + 排除集 + 类型化建链`
> 来源: B 类 Roundtable R2（product #842 / architect #845 / engineer #848）+ Frank 裁定（2026-08-11-r2-rulings-design.md）
> 日期: 2026-08-11
> 执行: game-engine（寇豆码）

## 1. 交付物清单

| 交付物 | 文件 | 状态 |
|---|---|---|
| 指令通道脚本 | `scripts/cmd_channel.sh`（353 行） | ✅ |
| 类型化建链薄路由 | `pipeline/cmd_chain.py`（400 行） | ✅ |
| 建链策略/棒次常量 | `pipeline/constants.py` `ROUNDTABLE_CHAIN_STRATEGY` + `DEVELOPMENT_CHAIN` | ✅ |
| 控制面检查 | `pipeline/state.py` `determine_next_action` 入口 ~27 行（paused/aborted → wait） | ✅ |
| v3 migration + 控制表 | `pipeline/checkpoint.py` `task_control` 表 + `migrate_v2_to_v3` + `get_active_tasks` LEFT JOIN 排除 + CRUD + `abort_cascade` | ✅ |
| 排除集补丁 | `pipeline/discover.py`（[ROUNDTABLE-/[DEV- 前缀）+ `scripts/dedup_check.sh`（[CMD] 分组前 skip）+ `scripts/stuck_check.sh`（assignee != 'autopilot'） | ✅ |
| 主循环挂载 | `scripts/autopilot.sh` cmd_channel 挂载（主 flock **之前**，fail-open `|| true`） | ✅ |
| 单测 | `scripts/test_cmd_channel.sh`（50 断言） | ✅ |
| 验证记录 | 本文档 | ✅ |

**B2 已做、本任务不重复**（commit 69093ec）: discover.py `SUB_TASK_TITLE_PREFIXES` 加 `[CMD]`、`PIPELINE_ASSIGNEES` 移除 autopilot、workspace_check 排除 [CMD]。

## 2. 测试用例（scripts/test_cmd_channel.sh — 50/50 PASS）

隔离环境: `/tmp/cmdchan-test`（复制真实 kanban schema 后清空 + 插入受控行；独立 pipeline_state.db；hermes CLI 通过 `HERMES_KANBAN_DB` 指向 temp 库，不触碰真实 board）。

### 2.1 消费 + 排除集（验收 1/2/5）

| # | 用例 | 断言 | 结果 |
|---|---|---|---|
| T1 | [CMD] roundtable B 测试 → 1 tick 消费并归档 | T1a: status=archived | ✅ |
| T2 | pipeline_state.db 零 dev 步骤记录（验收 b） | T2a/T2b: `pipeline_steps` 无 `t_cmd_%` / `t_cmd_rt` 记录 | ✅ |
| T3 | 三脚本都不报它（验收 c） | T3a/b/c: dedup/stuck/workspace_check 输出无 `t_cmd_rt` | ✅ |
| T4 | roundtable B all_at_once 一次建全链 + parents 门控 | T4a-f: 4 张链卡（director/architect/engineer/qa）+ 3 条 parent 依赖 | ✅ |
| T5 | 幂等（重复 tick 不重复建卡/消费） | T5a: 链卡数不变（idempotency-key 命中）；T5b: 二次运行"无待消费指令"；T5c: CAS 守卫 | ✅ |

### 2.2 类型化建链（验收 3）

| # | 用例 | 断言 | 结果 |
|---|---|---|---|
| T6 | roundtable D / create dev → sequential 只建 PRD | T6a/b: 指令卡已归档；T6c: 只建 2 张 [DEV-PRD]（两链各 1）；T6d: arch 未提前建 | ✅ |
| T7 | 逐棒推进（PRD done → 建 arch 产物注入 → done → 建 dev） | T7a-g: 推进日志、arch 卡 1 张、body 注入 `PRD/spec.md`、未 done 链不推进、dev 卡注入 `架构设计/arch.md`、assignee=game-engine | ✅ |

### 2.3 task_control（验收 4）

| # | 用例 | 断言 | 结果 |
|---|---|---|---|
| T8 | pause 断点 / resume 续跑 | T8a: 控制位 `paused|等 Frank 确认`；T8b/c: `determine_next_action` → wait（含"已暂停"）；T8d: paused 不在活跃集；T8e: resume 清控制位；T8f: 回到活跃集 | ✅ |
| T9 | abort 级联 + 归档 + 终态审计 | T9a: 控制位 `aborted|需求取消`；T9b: 步骤 cancelled + error_msg 审计；T9c: kanban 卡归档；T9d: 不在活跃集；T9e: 二次运行 exit 0 幂等；T9f: 终态行保留 | ✅ |

### 2.4 回执/容错/滞留（验收 2/6）

| # | 用例 | 断言 | 结果 |
|---|---|---|---|
| T10 | 未知指令 → 失败回执 + 归档（不静默） | T10a: 已归档；T10b: comment 含 [cmd-channel] + 失败 | ✅ |
| T11 | fail-open: kanban.db 不存在 exit 0 | T11a/b | ✅ |
| T12 | 滞留 3 tick 告警打日志（归 notify cron） | T12a-c: 告警日志点名 + 说明归 notify cron；T12d: 告警后仍正常消费归档 | ✅ |

### 2.5 回归（B2 discover 不误注册）

| # | 用例 | 断言 | 结果 |
|---|---|---|---|
| R1 | [ROUNDTABLE- 链卡不被 discover 注册 | ✅ |
| R2 | [DEV- 链卡不被 discover 注册 | ✅ |
| R3 | 普通管线卡 t_normal 仍被发现 | ✅ |

### 2.6 既有套件回归

| 套件 | 结果 |
|---|---|
| `scripts/test_notify_check.py`（B1 notify cron，33 断言） | ✅ 33/33 PASS |
| `scripts/test_workspace_check.sh`（B2，27 断言） | ✅ 27/27 PASS |
| `tests/slice3_smoke_test.py`（6 模块） | ✅ ALL 6 MODULES PASSED |
| `tests/slice2_smoke.py`（state/checkpoint/discover） | ✅ ALL SMOKE TESTS PASSED |
| `tests/slice2_integration.py` | ⚠️ 预存在失败（缺 `claim_report.md` fixture，HEAD 同样失败，非本任务引入） |

## 3. 真实看板手动验收（硬标准 engineer #848）

**方法**: 在真实 kanban.db 手动插入一张 `[CMD] roundtable B <时间戳> 手动验收` 卡（assignee=autopilot, status=ready, workspace_kind=scratch），跑 1 tick（`bash scripts/cmd_channel.sh`），验证 (a)(b)(c)，随后立即归档本次创建的 [ROUNDTABLE-B] 链卡（测试话题，不得真实派发）。

**证据**（2026-08-11T04:46:39Z）:

```
═══ [1/5] 手动造卡: [CMD] roundtable B B3 手动验收 20260811T044639Z ═══
inserted t_cmd_b3_manual
═══ [2/5] 跑 1 tick（cmd_channel.sh）═══
[cmd-channel] 消费 t_cmd_b3_manual: [CMD] roundtable B B3 手动验收 20260811T044639Z
[cmd-channel] t_cmd_b3_manual: roundtable B B3 手动验收 20260811T044639Z
              → all_at_once 建链成功: game-director=t_eba0dddd, game-architect=t_65eecbee,
                game-engine=t_b294c5d2, game-qa=t_29a1c74f
[cmd-channel] 无在途开发链需推进
═══ [3/5] 验证 (a)(b)(c) ═══
(a) [CMD] 卡状态: archived  (want: archived)          → PASS
(b) [CMD] 卡在 pipeline_steps 记录数: 0  (want: 0)    → PASS
(c) dedup_check hits=0  stuck_check hits=0  workspace_check hits=0  (want: 0 0 0) → PASS
═══ [4/5] 回执 comment 检查 ═══
最近 comment: [cmd-channel] roundtable B B3 手动验收 ... all_at_once 建链成功: game-director=t_eba0dddd, ...
═══ [5/5] 清理: 归档本次 [ROUNDTABLE-B] 链卡（测试话题不得派发）═══
archived t_eba0dddd | [ROUNDTABLE-B] B3 手动验收 ... | game-director | ready
archived t_65eecbee | [ROUNDTABLE-B] B3 手动验收 ... (2/4 架构) | game-architect | todo
archived t_b294c5d2 | [ROUNDTABLE-B] B3 手动验收 ... (3/4 研发) | game-engine | todo
archived t_29a1c74f | [ROUNDTABLE-B] B3 手动验收 ... (4/4 QA) | game-qa | todo
```

**派发核查**: 4 张链卡仅 `created` 事件、无 `spawned`/`claimed` 事件、无 task_runs 记录 → dispatcher（60s tick）未及派发即被归档，真实板无测试污染。

## 4. 验收标准对照

| # | 验收标准 | 证据 | 结果 |
|---|---|---|---|
| 1 | [CMD] 排除集完整（剩余 2 处）+ 硬验收 4 条全过 | dedup_check L80-85（[CMD] skip）+ stuck_check L90（assignee != 'autopilot'）；§2.1 T1-T3 + §3 真实板 | ✅ |
| 2 | cmd_channel.sh 五类指令可解析、单次消费幂等、1 tick 归档 | §2.1 T5 + §2.4 T10/T12 + §3 | ✅ |
| 3 | 类型化建链: B 一次建全链（parents 门控）；D sequential 逐棒（产物注入） | §2.1 T4 + §2.2 T6/T7 + §3（真实板 all_at_once） | ✅ |
| 4 | task_control: pause 断点 resume 续跑；abort 置 cancelled + 归档 + 终态审计 | §2.3 T8/T9 | ✅ |
| 5 | discover 误注册 bug 不再出现（指令卡不派发 game-engine） | §2.5 R1-R3 + §3（无 spawned 事件） | ✅ |
| 6 | autopilot 主循环 fail-open 不受影响 | `scripts/autopilot.sh` cmd_channel `|| true` + §2.6 slice smokes | ✅ |

## 5. 关键设计决策（记录）

1. **挂载点 = 主 flock 之前**（engineer #849）: 锁内挂载会导致每 tick flock 冲突 → 命令永不被消费。cmd_channel.sh 用独立 fd 201 flock 同一 LOCKFILE，与主循环互斥。
2. **单次消费三层幂等**: CAS（`UPDATE status='archived' WHERE 活跃` → rowcount==1 才执行）+ kernel idempotency-key + comment `[cmd-channel]` 标记守卫。
3. **滞留 3 tick 告警归 notify cron**: 未归档 [CMD] 卡使 notify 保持 ACTIVE 持续 heartbeat，本脚本只打日志不重复告警。
4. **abort reclaim 顺序**: running 卡先 reclaim 停 agent 再归档（若先归档，reclaim 会把卡翻回 ready 重新可派发）。
5. **abort 后 task_control 行保留为终态审计**（aborted + reason + updated_at），resume 时 DELETE；aborted 终态拒绝 resume。
6. **流程知识不复制**: cmd_chain.py 只引用 constants.py `ROUNDTABLE_*`/`DEVELOPMENT_CHAIN`，产物依赖语义由 constants 定义。

## 6. 环境备注

- 真实 `pipeline_state.db` 已完成 v3 迁移（user_version=3，task_control 表创建），由 `CheckpointDB.ensure_schema()` 幂等执行；本次提交不含二进制 db（与 B1/B2 先例一致，运行时自动迁移）。
- `config/notify.json` 含运行时注入的飞书真实凭据，**不纳入提交**（git 保持未暂存，避免泄露密钥）。
- 测试期间产生的 `t_target` 测试行已从真实 pipeline_state.db 清理（`DELETE FROM task_control WHERE task_id='t_target'`）。
