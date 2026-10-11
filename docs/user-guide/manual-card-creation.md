# 手动建卡让 autopilot 接管 — 操作手册（SOP）

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-engine
>
> 适用对象：Frank / OC / 任何需要绕过 CLI 之外手动建卡的成员
>
> 任务卡：[B2] workspace_check 合规扫描 + 手动建卡内容注入（t_aad6d422）
>
> 一句话：`hermes kanban create` 一张卡，autopilot 在 2~3 分钟内发现并接管（自动注册管线 + 注入 claim/wiki/超轮次 comment + 建 dev 卡执行）。

---

## 1. 背景

autopilot（`/workspace/devPPL/scripts/autopilot.sh`）每 2~3 分钟 tick 一次（orchestrator profile 的
`devppl_autopilot.sh` 定时任务）。它通过 `pipeline/discover.py` 扫描 kanban.db，发现"未注册的手动卡"后：

1. 自动注册到 `pipeline_state.db`（dev 步骤 pending）
2. **自动注入标准 comment**（[B2] 新增）：claim 要求 + wiki 链接 + 超轮次提醒
3. 走管线推进：创建 `dev: <task_id>` 卡（worktree）→ game-engine 执行 → qa → va → merge → close

手动建的卡如果没有这些注入，worker 拿卡缺上下文（不知道要输出 claim report、不知道 wiki、不知道超轮次要拆卡）——这就是本 SOP 存在的意义。

---

## 2. 建卡命令

### 2.1 推荐（开发任务）

```bash
hermes kanban create "任务标题" \
  --assignee game-engine \
  --body "需求描述 / spec 路径" \
  --workspace worktree:/workspace/devPPL \
  --priority 50
```

- `--workspace worktree:/workspace/devPPL`：**合规且可被发现**（见 §3.1/§4）。
- 也可以用 `--branch wt/<名字>` 指定分支，不指定则自动生成。

### 2.2 禁止（会导致合规告警）

```bash
# ❌ dir 卡：worker 直接写共享目录 = main 直改风险
hermes kanban create "..." --assignee game-engine --workspace dir:/workspace/devPPL

# ❌ 默认 scratch（不带 --workspace）：不会进管线（workspace_path 不匹配），
#   但也不会被合规告警（scratch 隔离安全）——只是不会被接管
hermes kanban create "..." --assignee game-engine
```

dir 卡会被 workspace_check 打 `[workspace-check]` 告警 comment（观察期不阻塞，由 OC 处置）。

### 2.3 指令卡（[CMD]，批 3 前）

```bash
hermes kanban create "[CMD] roundtable B <议题>" --assignee autopilot --body "..."
```

- 指令卡走批 3 的 cmd_channel.sh 消费，**当前尚未上线**，建了会被忽略（不注册、不告警、不误报）。
- `assignee=autopilot` 已从管线白名单移除——不会被误注册为 dev 任务。

---

## 3. 接管条件（discover 判定，全部满足才接管）

| # | 条件 | 说明 |
|---|------|------|
| 1 | `workspace_path = /workspace/devPPL` | 用 `--workspace worktree:/workspace/devPPL`（或 dir: 同路径）才会写入该值 |
| 2 | `assignee` ∈ 管线 5 角色 | game-engine / game-qa / verifier / game-director / game-architect（**不含 autopilot**，[B-RT R2] 已移除） |
| 3 | `status` = ready（或 running 且 claim 已失效） | 正在被 worker 执行（有效 claim）的卡**不会被重复接管**（[B2] 守卫，防重复执行） |
| 4 | 标题不以子任务前缀开头 | 不能是 `dev:` / `qa-d1:` / `qa-exec:` / `qa-d2:` / `va:` / `dev [ROLLBACK]:` / `dev [RETRY` / `qa-d1 [RETRY` / `close:` / `merge:` / `[CMD] ` |

---

## 4. 接管后的 2~3 分钟会发生什么

1. autopilot tick → discover 发现未注册卡
2. `register_discovered_task` 注册 dev 步骤 pending
3. **自动注入 comment**（内容与 autopilot 建 dev 卡时相同）：

   > [建卡要求·超轮次] 领到卡先评估工作量：若实现点多/场景复杂/预计超 60 轮，在完成报告建议拆分（职责内子卡由你建，assignee=game-engine；跨角色由 OC 建）。[claim 要求] 完成必须输出结构化 claim report（changed_files/tests_run/verification），供 VA 验证。[VA 验证点] 你的所有声明（代码完成、测试通过、verification）都会由 VA 检查——声明不实 = FALSIFIED + 返工。wiki 上下文: /workspace/mem-core/wiki/index.md

4. 下一 tick：advance_pipeline → `start_step dev` → 创建 `dev: <task_id>` 卡（worktree，隔离分支）→ game-engine 执行

---

## 5. workspace_check 告警的含义（看到 [workspace-check] comment 时）

- 触发条件：`workspace_kind` 非白名单（worktree/scratch）+ assignee 属管线 + 活跃（ready/running）
- 典型场景：手动建了 `dir:/workspace/devPPL` 卡
- 处置：**观察期不阻塞**（不自动 block/归档），由 OC 决定：
  - 确认豁免（例如 QA 复测需要共享目录），在卡上 comment 说明；或
  - 重建为 worktree 卡：归档旧卡 + 用 §2.1 命令重建

---

## 6. 时序说明与已知边界

1. **dispatcher 直接派发**：手动卡默认 status=ready，hermes dispatcher 会在 ~16s 内直接派发 worker 执行。
   若 autopilot tick 恰好错过 ready 窗口（卡已被派发且 claim 有效），discover 不会重复接管——卡由
   dispatcher 直接执行，不走管线跟踪。这是 [B2] 的有意守卫（防同一张卡被两个 worker 重复执行）。
   **如果你希望卡必须走管线**：建卡后 1 分钟内留意卡上是否出现注入 comment；若没有（说明已被直接派发），
   直接在卡上正常执行即可，管线跟踪为尽力而为。
2. **批 3（cmd_channel + 类型化建链）上线后**：手动建卡流程将规范化（[CMD] create 指令、D 类开发链
   逐棒建卡、body 产物注入），本 SOP 会被替代/更新。
3. **B 系列 infra 卡**（如 [B1]/[B2]/[FIX]）：若带 `--workspace dir:/workspace/devPPL` 创建，会被
   workspace_check 告警（属预期）；同时因有有效 claim 不会被 discover 重复接管（防双跑）。

---

## 7. Troubleshooting

| 现象 | 原因 | 处理 |
|------|------|------|
| 卡上出现 `[workspace-check]` comment | workspace_kind 非白名单（dir/未知） | §5：OC 确认豁免或重建 worktree |
| 卡上出现 `[claim 要求]` comment | discover 已注册 + 注入（正常！） | 按 comment 要求执行（输出结构化 claim） |
| 2~3 分钟没被接管 | 条件不满足：workspace_path 不匹配 / assignee 非管线 / 标题带子任务前缀 / 已被 dispatcher 直接派发 | 检查 §3 四条；用 §2.1 命令重建 |
| 卡被 dispatch 但没注入 comment | 卡已 running + 有效 claim（dispatcher 先手） | 正常，直接执行；管线跟踪尽力而为 |
| 建了 [CMD] 卡没反应 | cmd_channel（批 3）未上线 | 当前会被忽略；批 3 上线后自动消费 |

---

## 8. 相关文件

- 检测脚本：`scripts/workspace_check.sh`
- 注入逻辑：`scripts/autopilot.sh`（发现循环内 [B2 Gap2+5] 块）
- 发现逻辑：`pipeline/discover.py`（PIPELINE_ASSIGNEES 移除 autopilot / [CMD] 前缀 / HERMES_KANBAN_DB 路径 / running+claim 守卫）
- 验收与测试记录：`docs/qa/workspace-check-smoke-verification.md`
