# [B3] 指令卡通道 — QA 独立复测报告

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa（独立复测，非研发自测）
>
> 任务卡：t_bdc5e9e2 [B3-QA] QA 复测 — 指令卡通道独立验证
> 被测提交：7640aa8（B3 卡 t_e4d2f205，11 files +1448/-5）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 验证记录（研发）：`docs/qa/cmd-channel-verification.md`

---

## 0. 执行摘要

| 复测要求 | 结果 |
|---|:---:|
| 1. cmd_channel.sh 核心逻辑（读脚本） | ✅ PASS |
| 2. 单测复跑 `scripts/test_cmd_channel.sh` | ✅ 50/50 PASS |
| 3. 独立验证验收 (a)(b)(c) — 1 tick 消费归档 / 零 dev 步骤 / 三脚本不报 | ✅ PASS |
| 4. task_control 表 + determine_next_action + get_active_tasks 排除 | ✅ PASS |
| 5. 排除集（discover/dedup/stuck/workspace_check） | ✅ PASS |
| 6. 回归 B1 notify + B2 workspace_check | ⚠️ **部分 FAIL — 1 个 MAJOR** |

**缺陷汇总**：BLOCKER=0，**MAJOR=1**（B3-QA-01：notify cron 实机通道失效），MINOR=0，SUGGESTION=0。

**结论**：**有条件 PASS** — B3 提交（7640aa8）代码本身全部验收通过；但"B1 notify 不受影响"的实机回归不成立：notify cron 自 04:34Z 起每 tick 飞书发送 HTTP 400（invalid receive_id），根因是 B3 工作窗口内对未提交 `config/notify.json` 的运行时修改（chat_id oc_9…→oc_7… + 凭据显式化），非提交内代码缺陷。MAJOR 处置（恢复有效 chat_id / 确认新群已加 bot）后方可闭环。

---

## 1. cmd_channel.sh 核心逻辑审查（复测要求 1）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 1.1 | 扫描条件：`[CMD]% + assignee=autopilot + ready/blocked`，全 workspace | ✅ | L265-278：`WHERE title LIKE '[CMD] %' AND assignee='autopilot' AND status IN ('ready','blocked') ORDER BY created_at`——无 workspace_path 过滤（engineer #848 A4 全 workspace）；LIKE 大小写不敏感（SQLite ASCII，[cmd] 小写同样消费） |
| 1.2 | 五类指令解析 | ✅ | L308-324：`[CMD] verb args...` → case roundtable/create/pause/resume/abort；未知 verb → 失败回执 + 归档（不静默） |
| 1.3 | CAS 单次消费 | ✅ | L288-305：`UPDATE tasks SET status='archived' WHERE id=? AND status IN ('ready','blocked')` → rowcount==1 才执行；`${CAS:-0} != 1` → 跳过 |
| 1.4 | fail-open | ✅ | L36 `set -uo pipefail`（无 -e）；L49-52 kanban.db 不存在 exit 0；单卡异常仅日志继续 |
| 1.5 | 挂载点在主 flock 之前（独立 fd 201） | ✅ | autopilot.sh L54 `bash "$REPO_ROOT/scripts/cmd_channel.sh" "$REPO_ROOT" || true` 位于主 flock（L57-61）**之前**；cmd_channel.sh L225-229 独立 `exec 201>LOCKFILE` + `flock -n 201`（engineer #849：锁内挂载 = 每 tick flock 冲突 → 命令永不被消费） |
| 1.6 | 三层幂等 | ✅ | CAS（消费侧）+ kernel idempotency-key（建链 `_hermes_create` L91-103）+ comment `[cmd-channel]` 回执守卫 |
| 1.7 | 滞留 3 tick 告警归 notify cron | ✅ | L235-258 按 created_at 超 3×120s 打日志点名，不重复告警；notify_check.py L182-197 `read_cmd_cards` 未归档 [CMD] 卡使 notify 保持 ACTIVE |
| 1.8 | 类型化建链薄路由 | ✅ | cmd_channel.sh L99-153 仅调 `pipeline/cmd_chain.py`；cmd_chain.py L34-41 引用 constants.py `ROUNDTABLE_CHAIN_STRATEGY/ASSIGNEES/WORKFLOWS/DEVELOPMENT_CHAIN`（流程知识不复制） |

## 2. 单测复跑（复测要求 2）

```
bash scripts/test_cmd_channel.sh
PASS=50 FAIL=0
ALL TESTS PASSED
```

- T1a/T2a-b/T3a-c：验收 (a)(b)(c) 硬标准（temp DB 隔离环境，`/tmp/cmdchan-test`，不触碰真实 board）
- T4a-f：roundtable B all_at_once 一次建 4 张链卡（director/architect/engineer/qa）+ 3 条 parents 依赖门控
- T5a-c：幂等（二次运行链卡数不变 / 无重复消费 / CAS 守卫保持 archived）
- T6a-d/T7a-g：sequential 逐棒（PRD→arch→dev，产物路径注入 `PRD/spec.md` / `架构设计/arch.md`，未 done 链不推进）
- T8a-f：pause 控制位 + determine_next_action→wait（"已暂停"）+ 不在活跃集；resume 清控制位回活跃集
- T9a-f：abort 级联 cancelled + 归档 + 终态审计保留 + 幂等 exit 0
- T10a-b/T11a-b/T12a-d：失败回执 / 缺 DB fail-open / 滞留告警点名归 notify
- R1-R3：discover 不注册 [ROUNDTABLE-/DEV- 链卡，普通卡仍被发现

## 3. 独立验证验收 (a)(b)(c)（复测要求 3）

QA 独立执行方式：隔离 temp DB 受控造卡（任务允许"用临时 DB"）——等价于真实板手动造卡，且不污染真实 board。

| 硬标准 | 断言 | 结果 |
|---|:---:|:---:|
| (a) 1 tick 消费并归档 | T1a `t_cmd_rt` status=archived（CAS 命中 rowcount=1） | ✅ |
| (b) pipeline_state.db 零 dev 步骤 | T2a `pipeline_steps` 无 `t_cmd_%` 记录（0）；T2b 自身零记录 | ✅ |
| (c) 三脚本不报 | T3a dedup_check / T3b stuck_check / T3c workspace_check 输出均无 `t_cmd_rt` | ✅ |

真实板证据（交叉核对研发验证记录 §3）：手动卡 `t_cmd_b3_manual` + 4 张 `[ROUNDTABLE-B]` 链卡均已 archived；仅有 `created` 事件、无 `spawned/claimed` 事件（未派发）；回执 comment `[cmd-channel] … all_at_once 建链成功` 落库。QA 残留核对：真实 kanban.db 无活跃 [CMD]/autopilot 卡；真实 pipeline_state.db `pipeline_steps`/`task_control` 均 0 残留（`t_cmd_%`/`t_target` 查无）。

## 4. task_control 控制面（复测要求 4）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 4.1 | task_control 表存在（真实库 v3） | ✅ | 真实 pipeline_state.db `PRAGMA user_version=3`；`sqlite_master` 含 task_control（CHECK control_state IN ('normal','paused','aborted')）；当前 0 行（干净） |
| 4.2 | 迁移幂等 | ✅ | checkpoint.py L91-105 `migrate_v2_to_v3`：表由 SCHEMA_SQL IF NOT EXISTS 创建，仅记账 user_version=3 |
| 4.3 | determine_next_action 入口检查 | ✅ | state.py L590-613：控制面检查在 `_complete` 判断**之前**（防 running 分支触碰步骤）；paused → wait（detail="已暂停: …"）；aborted → `_apply_abort_cascade` 兜底 + wait（"已中止"） |
| 4.4 | get_active_tasks 排除 | ✅ | checkpoint.py L251-268：`LEFT JOIN task_control … WHERE status IN ('pending','running') AND (tc.control_state IS NULL OR ='normal')` |
| 4.5 | pause/resume/abort 行为 | ✅ | T8a-f/T9a-f 全绿；abort_cascade（checkpoint.py L377-393）非 done 步骤置 cancelled + error_msg 审计；abort 终态拒绝 resume（cmd_chain.py L345-347） |

## 5. 排除集（复测要求 5）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 5.1 | discover.py 含 [ROUNDTABLE-/DEV- | ✅ | discover.py L36-53 `SUB_TASK_TITLE_PREFIXES` 含 `"[CMD] "`、`"[ROUNDTABLE-"`、`"[DEV-"` |
| 5.2 | dedup_check skip [CMD] | ✅ | dedup_check.sh L84：`(r[1] or "").upper().startswith("[CMD]")` 分组前跳过 |
| 5.3 | stuck_check 排除 autopilot | ✅ | stuck_check.sh L91：`AND assignee != 'autopilot'`（[CMD] 卡防御排除） |
| 5.4 | workspace_check [CMD] 双层防御 | ✅ | workspace_check.sh L67 白名单无 autopilot（PIPELINE_ASSIGNEES 同源）+ L91-93 标题 `[CMD]` 前缀（大小写不敏感）第二道 |
| 5.5 | 回归不误伤普通卡 | ✅ | R1-R3：普通管线卡 `t_normal` 仍被发现 |

## 6. 回归（复测要求 6）— ⚠️ 部分 FAIL

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 6.1 | crontab 行未变 | ✅ | root crontab：`*/2 * * * * bash /workspace/devPPL/scripts/notify_cron.sh >> …/notify_cron.log 2>&1`（与 B1/B2 记录一致）；autopilot cron 为 orchestrator profile hermes cron（id 4e52405060a3，every 2m，enabled，last_status=ok），B3 未改 |
| 6.2 | B2 workspace_check 不受影响 | ✅ | `test_workspace_check.sh` 27/27 PASS；实机 autopilot.log 04:49/04:52/04:55 tick `[workspace-check] 未发现 workspace_kind 违规卡`，主循环 fail-open 连续运行 |
| 6.3 | B1 notify 单测 | ✅ | `python3 scripts/test_notify_check.py` 33/33 PASS（含 B1-F1 回归断言） |
| 6.4 | **B1 notify 实机通道** | ❌ **FAIL** | 见 MAJOR B3-QA-01 |

## 7. 缺陷

### B3-QA-01（MAJOR）— notify cron 实机通道失效：飞书发送 HTTP 400 invalid receive_id

**现象**：`logs/notify_cron.log` 自 **2026-08-11T04:34:01Z** 起每个 tick（每 2min）输出 `[notify-check] 飞书发送异常: HTTP Error 400: Bad Request`，至复测时（04:54Z）持续未恢复（复测期间 04:56 仍复现）。

**复现步骤**：
1. `tail logs/notify_cron.log` → 04:34 起每 tick `飞书发送异常: HTTP Error 400`
2. `git diff config/notify.json` → 本地未提交修改 4 处：`chat_id` oc_9…（HEAD）→ oc_7…（本地）、`app_id`/`app_secret` 空→显式、`credential_source` verifier_env→orchestrator_env
3. 复现请求（带缓存 token 直调 `im/v1/messages`）→ `HTTPError 400`，Feishu `code=230001 msg=invalid receive_id`

**预期 vs 实际**：预期 notify cron 每 tick 正常推送（B1 验收 04:12-04:18 实测成功，notify_state.db 3 条事件 last_sent_at 均已设）；实际所有 send 路径（heartbeat/milestone/exception）自 04:34 起全部失败。

**影响**：飞书通知/告警通道整体不可达 20+ 分钟（用户收不到管线状态 heartbeat、里程碑、异常告警）；[CMD] 卡滞留提示（设计上归 notify cron）同步失效。管线主循环本身不受影响（notify fail-open 设计）。

**根因**：B3 工作窗口内（B3 验证记录 §6 明示"config/notify.json 含运行时注入的飞书真实凭据，不纳入提交"），工程师向未提交的 `config/notify.json` 注入凭据时将 `chat_id` 由 HEAD 的 oc_9… 改为 oc_7…，该群对当前 app 无权限/不存在 → Feishu 230001。**提交 7640aa8 未触碰 notify 代码/配置**（`git show --stat`：11 文件不含 notify_check.py/notify_cron.sh/config/notify.json）。

**修复建议（交 OC 建 FIX 卡 → 研发处置）**：
- 方案 A（最快）：恢复 HEAD 版 `chat_id`（oc_9…）并清空本地 app_id/app_secret 走 verifier_env 回退（B1 验证期间工作组合）
- 方案 B：若 oc_7… 为新目标群，需确认该 bot/app 已加入该群且具备发送权限
- 处置后需回归验证：notify_cron.log 连续 2 tick 无 400，且一条真实消息可达

**分级判定（§1.2 五步）**：
| 步骤 | 判定 |
|------|------|
| 用户可感知？ | ✅ 用户收不到任何飞书通知（heartbeat/milestone/exception 全失败） |
| 功能阻断？ | ✅ notify 功能整体失效（所有 send 路径 400，每 tick 重试） |
| 无 workaround？ | ❌ 有——恢复有效 chat_id/凭据（配置修复，非代码改动） |
| 安全漏洞？ | 无 |
| 结论 | 非 BLOCKER（有 workaround）→ **MAJOR**（严重影响体验，报警/通知不可达；发版需标注 known issue 或先修复） |

**论证流程（§6）**：本报告即 QA 发现 → 交研发评估 → 通过/驳回/暂缓；驳回须带新证据，产品裁定为最终。

## 8. SLA 对照（§8）

本次发现 1 个 MAJOR（非 BLOCKER），**不触发** BLOCKER 4h 响应 + 8h 定位 + 24h 方案 SLA。MAJOR 处置按常规 FIX 流程（OC 建卡 → 研发 → QA 复测）。

## 9. 分级示例对照（§1.1）

- B3-QA-01 对应"MAJOR：严重影响体验，发版需标注 known issue"——通知通道失效 20+ 分钟且持续，用户可感知、功能阻断，但有配置级 workaround。
- 未发现 BLOCKER/安全漏洞。

## 10. 结论

**有条件 PASS（B3 代码 PASS + 环境侧 1 个 MAJOR 待处置）**

- ✅ B3 提交 7640aa8 全部复测要求通过：核心逻辑审查（挂载点/CAS/fail-open/全 workspace 扫描/五类指令/三层幂等）、单测 50/50、验收 (a)(b)(c)、task_control 控制面、排除集、B2 workspace_check 回归
- ⚠️ 复测要求 6（B1 notify 不受影响）**不成立**：notify 实机通道自 04:34Z 起失效（B3-QA-01 MAJOR，根因为 B3 工作窗口内未提交 config 修改 chat_id 无效，非提交内代码缺陷）
- 处置建议：OC 建 FIX 卡恢复 notify 配置（恢复 oc_9… chat_id / 确认 oc_7… 群权限），QA 复测 notify_cron.log 连续 tick 无 400 后闭环

## 11. 交付物

- 本报告：`docs/qa/retest-b3-cmd-channel.md`
- 复测辅助脚本（/tmp，不入库）：`qa_b3_check.py` / `qa_b3_notify.py` / `qa_b3_cfg.py` / `qa_b3_repro400.py` / `qa_b3_residue.py` / `qa_b3_final.py`
