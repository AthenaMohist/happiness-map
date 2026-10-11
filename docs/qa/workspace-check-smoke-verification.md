# B2 workspace_check 合规扫描 + 手动建卡内容注入 — 测试执行与 smoke 验证记录

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-engine
>
> 任务卡：t_aad6d422 [B2] workspace_check 合规扫描 + 手动建卡内容注入
>
> 验收基准：`docs/roundtables/b-autopilot-oc-relationship/2026-08-11-r2-rulings-design.md`（Frank 裁定 F3）
> + engineer #848（判定规则 / 第 4 处排除）+ engineer #849（发现 bug 验证）

---

## 0. 执行摘要

| 项目 | 数值 |
|------|:---:|
| **自动化测试用例** | 27（T0–T11，覆盖 5 条验收标准 + 线上 cron 路径回归） |
| **通过** | 27 |
| **失败** | 0 |
| **通过率** | 100% |
| **执行时间** | <15s（temp DB 隔离，零真实 board 污染） |
| **真实环境 smoke** | ✅ 已验证（live autopilot cron 04:07:08Z 自动触发 workspace_check 并 comment，不阻塞） |
| **发现缺陷** | 3（FIX-1 discover 线上路径 bug / FIX-2 `--workspace-kind` CLI 参数失效 / FIX-3 遗留测试契约过期），均已修复 |

交付物：
- `scripts/workspace_check.sh`（137 行，复刻 dedup_check.sh 模式）
- `scripts/test_workspace_check.sh`（27 用例）
- `pipeline/discover.py`（3 处修复：PIPELINE_ASSIGNEES 移除 autopilot + [CMD] 前缀 + 环境感知路径 + running 有效 claim 守卫）
- `scripts/autopilot.sh`（3 处改动：注入块 + workspace_check 挂载 + dev 卡 workspace 参数修复）
- `docs/user-guide/manual-card-creation.md`（SOP）

---

## 1. 验收标准对照

| # | 验收标准 | 测试覆盖 | 结果 |
|---|---------|---------|:---:|
| 1 | 手动造 `workspace_kind='dir'` + assignee=game-engine 的卡 → workspace_check 发现并 comment 告警（不阻塞） | T1 + 真实环境 smoke（live tick 对 t_aad6d422/t_96cf339b 告警，卡保持 running） | ✅ |
| 2 | `[CMD]` 卡（assignee=autopilot）不被 workspace_check 误报 | T2a/T2b + T9b（discover 侧同源排除） | ✅ |
| 3 | 手动建的卡被 discover 注册时自动注入 claim/wiki/超轮次 comment | T9a + T10a-d + T11a | ✅ |
| 4 | 不影响 autopilot 主循环（fail-open） | T0/T8 + 真实环境 smoke（live tick 正常完成） | ✅ |
| 5 | 单测覆盖上述场景 | T1–T11（27 用例） | ✅ |

---

## 2. 自动化测试执行结果

```
运行: cd /workspace/devPPL && bash scripts/test_workspace_check.sh

temp kanban.db ready

════════ T1-T7: workspace_check.sh 合规扫描（验收 1/2/4/5）════════
    2026-08-11T04:07:08Z [workspace-check] 违规卡 t_dir_ready (workspace_kind=dir, assignee=game-engine, status=ready): 手动 dir 卡
    2026-08-11T04:07:09Z [workspace-check] 违规卡 t_unknown (workspace_kind=weird, assignee=verifier, status=ready): 未知 kind 卡
    2026-08-11T04:07:10Z [workspace-check] 共告警 2 张违规卡

── 判定结果 ──
  ✓ T0: 脚本 exit 0（fail-open，验收 4）
  ✓ T1: dir 卡被 flag（验收 1）
  ✓ T2a: [CMD] 卡（assignee=autopilot）不误报（验收 2）
  ✓ T2b: [cmd] 小写前缀也不误报（防御）
  ✓ T3: worktree 卡不 flag
  ✓ T4: scratch 卡不 flag（qa 白名单）
  ✓ T5: done 状态不 flag（非活跃）
  ✓ T6: 未知 workspace_kind 卡 flag
  ✓ T7a: 非管线 assignee 不 flag
  ✓ T7b: dir 卡已有 [workspace-check] comment
  ✓ T7c: [CMD] 卡无 comment
  ✓ T7d: 未知 kind 卡已有 comment
  ✓ T7e: 二次运行不重复 comment（幂等）
  ✓ T8a: 缺 DB exit 0
  ✓ T8b: 日志说明跳过

════════ T9-T12: discover 修复 + 手动建卡内容注入（验收 3）════════
  ✓ T9a: 手动卡被 discover 发现（验收 3）
  ✓ T9b: [CMD] 卡不被 discover 发现（第 3 道闸 + [CMD] 前缀）
  ✓ T9c: autopilot 子任务卡不重复发现
  ✓ T9d: running + 有效 claim 卡不被发现（防重复执行）
  ✓ T9e: running + 失效 claim 卡被发现（可接管）
  ✓ T11a: 缺省路径走 HERMES_KANBAN_DB（线上发现恢复）
  ✓ T11b: running + 有效 claim 仍被跳过
  ✓ T11c: running + 失效 claim 仍被发现

── T10: 注册后内容注入（与 autopilot.sh 注入块同逻辑）──
registered
  ✓ T10a: 注入 comment 含 [claim 要求]（验收 3）
  ✓ T10b: 二次注入被幂等守卫拦截
  ✓ T10c: 注入含 wiki 链接
  ✓ T10d: 注入含超轮次提醒

════════ 结果汇总 ════════
PASS=27 FAIL=0
ALL TESTS PASSED
```

---

## 3. 真实环境 smoke 验证（live autopilot cron 自动触发）

### 3.1 发现：live autopilot 每 2~3 分钟 tick（orchestrator profile 的 devppl_autopilot.sh 定时任务）

改完代码后未做任何手动触发——**下一个 live tick 自动执行了新挂载的 workspace_check**：

```
# logs/autopilot.log @ 2026-08-11T04:07:08Z
2026-08-11T04:07:10Z [workspace-check] 违规卡 t_aad6d422 (workspace_kind=dir, assignee=game-engine, status=running): [B2] workspace_check 合规扫描 + 手动建卡内容注入
2026-08-11T04:07:10Z [workspace-check] 违规卡 t_96cf339b (workspace_kind=dir, assignee=game-qa, status=running): [B1-QA] QA 复测 — 通知 cron 独立验证
2026-08-11T04:07:10Z [workspace-check] 共告警 2 张违规卡
```

对应 kanban.db task_comments（真实 board）：
- comment#871（t_aad6d422，author=orchestrator，04:07:10Z）：`[workspace-check] 本卡 workspace_kind='dir' 不在白名单（worktree scratch）…观察期仅告警不阻塞…`
- comment#872（t_96cf339b，author=orchestrator，04:07:10Z）：同上

### 3.2 验证点

| # | 证据 | 结果 |
|---|------|:---:|
| 1 | live tick 自动跑 workspace_check（无需手动） | ✅ |
| 2 | dir 卡被发现并 comment 告警（验收 1 实机版） | ✅ |
| 3 | **不阻塞**：两张卡 status 仍为 running（未 block/未 reclaim/未归档） | ✅ |
| 4 | 主循环正常结束（`=== 轮询结束 ===` 后 exit 0，dedup/stuck/workspace 三子脚本全部 fail-open） | ✅ |
| 5 | 手动重跑幂等：`HERMES_KANBAN_DB=/root/.hermes/kanban.db bash scripts/workspace_check.sh` → 打 `已有 [workspace-check] 标记，跳过`，exit=0 | ✅ |

### 3.3 手动实机重跑（验收 1 直接证据）

```
$ cd /workspace/devPPL && HERMES_KANBAN_DB=/root/.hermes/kanban.db bash scripts/workspace_check.sh /workspace/devPPL; echo "exit=$?"
2026-08-11T04:07:19Z [workspace-check] 违规卡 t_aad6d422 (workspace_kind=dir, assignee=game-engine, status=running): [B2] ...
2026-08-11T04:07:19Z [workspace-check] t_aad6d422: 已有 [workspace-check] 标记，跳过（幂等）
2026-08-11T04:07:19Z [workspace-check] 共告警 2 张违规卡
exit=0
```

### 3.4 discover 线上路径验证（修复后）

```
$ python3 .tmp_probe_discover.py（对真实 board 跑 discover_new_tasks）
FOUND: []   ← 两张 running 卡均有有效 claim → 守卫生效，不被重复接管（防双跑）
```

---

## 4. 修复记录（本任务内发现的缺陷）

### FIX-1: discover.py 线上永不发现新卡（MAJOR，阻塞验收 3 生产生效）

- **现象**：live autopilot 每 tick 都跑 discover，但日志从无「发现新任务」；对真实 board 手动调
  `discover_new_tasks(db)` 返回空，而显式传 `kanban_db_path=/root/.hermes/kanban.db` 能发现。
- **根因**：discover.py 缺省 `~/.hermes/kanban.db`；autopilot cron（orchestrator profile）的 HOME 是
  `/root/.hermes/profiles/orchestrator/home` → `~` 解析到不存在路径 → `os.path.exists` 直接返回 []。
  其余 autopilot 家族（dedup/stuck/workspace_check）都走 `HERMES_KANBAN_DB`，唯独 discover 不感知。
- **修复**：discover.py 缺省路径优先 `os.environ.get("HERMES_KANBAN_DB")`，回退 `~/.hermes/kanban.db`。
- **回归**：T11a-c（fake HOME + HERMES_KANBAN_DB 指向 temp → 发现恢复 + claim 守卫仍生效）。

### FIX-2: `--workspace-kind worktree` 参数在 CLI v0.19.0 已失效（MAJOR，阻塞 dev 卡创建）

- **现象**：autopilot.sh L270 传 `--workspace-kind worktree`，实测 `hermes kanban create ... --workspace-kind worktree`
  直接 argparse usage 报错 → dev 卡创建会失败（CARD_ID 空）。
- **根因**：当前 CLI（v0.19.0）参数为 `--workspace scratch|worktree|worktree:<path>|dir:<path>`，无 `--workspace-kind`。
- **修复**：改为 `--workspace "worktree:$REPO_ROOT"`（实测创建成功：workspace_kind=worktree, workspace_path=/workspace/devPPL）。
- **回归**：无直接单测（建卡 CLI 行为），由真实 CLI 探测验证（见 §5 边界 3）。

### FIX-3: 遗留测试契约过期（PIPELINE_ASSIGNEES=6 断言）

- **现象**：`tests/slice3_smoke_test.py` 与 `tests/test_slice3_d1_qa.py` TC-27 断言 PIPELINE_ASSIGNEES 含 6 角色（含 autopilot）。
- **根因**：[B-RT R2] 已裁定移除 autopilot（第 3 道闸根治），测试仍编码旧契约。
- **修复**：更新为 5 角色 + `autopilot not in`；TC-28/smoke 增补 `[CMD] ` 前缀断言。
- **回归**：`python3 tests/slice3_smoke_test.py` 全过；`python3 -m pytest tests/test_slice3_d1_qa.py -q` → 55 passed。

---

## 5. 已知边界与说明

1. **scratch 白名单（工程裁定）**：任务字面为 `workspace_kind != 'worktree'` 违规，但 autopilot 自建的
   qa/va 卡全部是默认 scratch；若只白名单 worktree，autopilot 自己的卡每 tick 被误报 → 合规告警自伤。
   实际白名单 = `worktree scratch`（scratch 派发时是全新 tmp 目录，天然隔离，不触碰 main），违规 = dir/未知值。
   可用 `WORKSPACE_KIND_WHITELIST` 环境变量覆盖。若 Frank 认为 qa/va 也须 worktree，改白名单即可（1 处）。
2. **running + 有效 claim 守卫**：discover 不接管正在被 dispatcher 直接派发的卡（防同一张卡双跑）。
   代价：手动卡若被 dispatcher 在 ready 窗口内先手派发（~16s），管线接管为尽力而为（SOP §6.1 已说明）。
3. **`--workspace-kind` 兼容**：本任务仅修 autopilot.sh dev 卡路径；rollback/retry/fanout 等分支未传
   workspace 参数（scratch）。批 3（cmd_channel）上线时若需统一 worktree，逐一补参数即可。
4. **discover 不区分任务类型**：任何管线 assignee + 路径匹配的 ready/stale-running 卡都会注册为 dev 步骤
   （infra 卡如 [B1]/[B2] 若在 ready 窗口被扫到也会被接管）。这是批 3「类型化建链」的解决范围；当前
   running+claim 守卫已挡住最常见的双跑场景。
5. **B1 notify cron 不受影响**：本任务零改动 notify_cron.sh / notify_check.py / notify_state.db；crontab
   条目与实跑日志（04:07 前后正常 tick）均未变。

---

## 6. 结论

5 条验收标准全部通过（27/27 自动化断言 + 真实环境 smoke，其中验收 1 由 live autopilot 自动触发验证），
交付物齐备：

- `scripts/workspace_check.sh`（合规扫描，comment 告警不阻塞，fail-open，幂等）
- `scripts/test_workspace_check.sh`（27 用例，temp DB 隔离）
- `pipeline/discover.py`（[CMD] 排除集 + 环境感知路径 + running claim 守卫）
- `scripts/autopilot.sh`（注入块 + workspace_check 挂载 + dev 卡 workspace 参数修复）
- `docs/user-guide/manual-card-creation.md`（Frank/OC 手动建卡 SOP）
- 顺带修复 3 个阻塞性缺陷（见 §4），legacy 测试 55/55 通过，B1 notify cron 无回归。
