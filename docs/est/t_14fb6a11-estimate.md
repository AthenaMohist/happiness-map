# 评估报告 — [FIX] WIP 轮次进度检测 — running 卡超 N 轮无 checkpoint 自动提醒（行为层保证）

> 评估人：寇豆码（game-engine） | 日期：2026-08-14 | 评估卡：t_est_14fb6a11
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_14fb6a11（[FIX] WIP 轮次进度检测 — running 卡超 N 轮无 checkpoint 自动提醒）
> 上游：DPL-030 已落地（constants.py WIP_* 常量 + SOUL 注入 9 profile + 发现笔记协议）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后预计 39-57 轮 > 20 轮阈值）。**

任务本质是**机械型巡检脚本扩展**（复刻 stuck_check.sh 模板 + git log 检测 + comment 提醒），
改动面约 **5 个文件 + 386 断言回归**，无算法风险；但存在一个**已实锤的设计空白**
（R1：task_runs 无 iteration 列，"N 轮"计数的数据源不存在）和测试 fixture 需构造真实
git 仓库（比纯 DB 注入复杂）。按 DPL-018 校准系数 K=3.00 折算后总量远超 20 轮阈值，
必须拆卡。自然边界按「检测脚本 / 异常清单+测试收尾」拆成 2 张（S2 的 oc_wake 源 D
读 S1 打的 [wip-check] comment，串行依赖）。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **5 个文件**：scripts/wip_progress_check.sh（新，~120-160 行）、scripts/autopilot.sh（+1 挂载点）、scripts/oc_wake_check.sh（+源 D ~10-15 行）、pipeline/constants.py（复用 WIP_CHECKPOINT_MAX_ROUNDS，可能 +1 提醒窗口常量）、scripts/test_wip_progress_check.sh（新，~10-15 断言 + git fixture） | 需求「挂在 stuck_check.sh 或 oc_wake_check.sh」+「复用现有巡检节奏」；stuck_check.sh 205 行即模板 |
| ① wip_progress_check.sh | 复刻 stuck_check.sh 结构（python3 heredoc 扫 running 卡 + 幂等 comment 守卫），但检测体换成 **git log**：`git -C <workspace_path> log --oneline -N` 取最近 commit，判 `^\[WIP\]` 前缀 + WIP commit 距今秒数。**只 comment 不 block/reclaim**（与 stuck_check 的 reclaim 分支语义分离）。边界：scratch 卡/空 workspace_path/git 失败 → fail-open 跳过 | 实测 stuck_check.sh L74-145 扫描+判定、L152-168 幂等守卫、L183-190 comment；workspace_check.sh L104-118 同类守卫 |
| ② autopilot.sh 挂载 | stuck_check 调用（L773）后追加一行 `bash "$REPO_ROOT/scripts/wip_progress_check.sh" "$REPO_ROOT" || true` + 3 行注释 | 实测 L773 `bash ... stuck_check.sh ... \|\| true` |
| ③ oc_wake_check.sh 源 D | 仿源 A（L48-60 读 [stuck-check] comment）新增读 `[wip-check]` comment 的检测源 + seen 去重键 `wip-check:<tid>`，OC 唤醒时可见 | 实测 L48-60 源 A 结构完全同构 |
| ④ constants.py | **复用现有** WIP_CHECKPOINT_MAX_ROUNDS=15（L244）+ WIP_COMMIT_PREFIX="[WIP]"（L245）；可能追加 `WIP_CHECK_COMMENT_WINDOW_MIN`（提醒幂等窗口，默认 60min 对齐 oc_wake 节奏）。需求阈值 10-15 轮已与 DPL-030 常量对齐，无需新拆卡 | 实测 L243-247 三常量已存在；需求「阈值可配置，默认与 DPL-030 对齐」→ 直接引用 |
| ⑤ 测试 | 新 test_wip_progress_check.sh（模式同 test_idle_check.sh 隔离 DB + 真实 temp git 仓库 fixture）：has-[WIP] 不误报 / 无-[WIP] 提醒 / 阈值边界（N-1 不提醒 N 提醒）/ 只 comment 不改状态（AC-4）/ scratch 卡跳过；+ 全量回归 386+ | 实测 test_idle_check.sh L36-60 隔离 DB 注入模式；test_cmd_channel.sh L280/L465-476 有 stuck_check/oc_wake 既有断言（改动后必须回归） |
| ⑥ 收尾 | commit + 结构化 claim + 飞书推送 + kanban_complete | 团队惯例 |

**基准轮数（未校准）：13-19 轮**（① 4-6 + ② 1 + ③ 1-2 + ④ 0.5-1 + ⑤ 4-6 + ⑥ 1-2）。
**DPL-018 校准：基准 × K=3.00 → 校准后 39-57 轮**（取中位 48）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **task_runs 无 iteration 列（"N 轮"数据源不存在，最高置信设计空白）** | **高** | 实测 kanban_db.py L1223-1243：task_runs 列 = id/task_id/profile/step_key/status/claim_lock/claim_expires/worker_pid/max_runtime_seconds/last_heartbeat_at/started_at/ended_at/outcome/summary/metadata/error，**无 iteration 计数**。迭代预算（60/60）是 run_agent.py 运行时概念（IterationBudget），不落库。需求约束 3 自己标注「需确认哪个可靠」→ 确认结论：**不可靠/不存在**。必须改用代理信号：(a) task_events 里 kind='heartbeat' 事件计数（实测 heartbeat_worker 每次写 event + run_id，L6125-6129）——近似轮数但非 1:1；(b) git log WIP commit 距今秒数（需求原文「或 WIP commit 距今过久」即此信号）；(c) run started_at → 经时秒数折算。**建议主信号 = WIP commit 距今（可靠、免猜），轮数作辅助**。此决策必须在 S1 卡内先定再写 |
| R2 测试需真实 git 仓库 fixture | 中 | 纯 DB 注入（test_idle_check 模式）不够——检测体是 git log，必须在 temp 目录 `git init` + 造 `[WIP]`/普通 commit + 设工作树路径，断言才真实。比既有单测多一层 fixture 搭建（~15-20 行） |
| R3 只提醒不打断的验收 | 中 | AC-4「验证不改变卡状态」：测试须断言 comment 后 status 仍 running + 无 reclaim。沿用 stuck_check 幂等窗口模式可满足；但需防 2min tick 刷屏 → 提醒窗口独立（WIP_CHECK_COMMENT_WINDOW_MIN，建议 60min） |
| R4 全量回归 | 低-中 | autopilot.sh / oc_wake_check.sh 改动会触发 test_cmd_channel.sh T3/T6/PRD-GATE-T6 既有断言（L280/L465-476）——加新检测源不破坏旧断言（源 A 只多不删），但必须跑 386+ 全量确认 |
| R5 scratch/无 git 卡误报 | 低 | workspace_path 为空或非 git 目录 → fail-open 跳过，与 workspace_check.sh 白名单语义对齐；测试覆盖 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 13-19 轮（中位 16） |
| DPL-018 校准后 | 39-57 轮（×K=3.00，中位 48）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（检测脚本）→ S2（oc_wake 读 [wip-check] + 测试）单向依赖；测试必须等脚本存在才可写断言；constants 复用不占独立卡 |
| 并行收益 | 低——S2 的 oc_wake 源 D 读 S1 打的 comment 串，测试断言 S1 的脚本行为，天然串行；并行会互相等 |
| 兜底 | 每张子卡有独立验收闭环：S1 交付脚本 + autopilot 挂载（AC-1/2/3 可验）；S2 交付 oc_wake 源 D + 全量测试（AC-4/5 可验）。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。** 量级参照：t_c8ad7805（DPL-030，7 文件 + 必破断言修正 → 拆 4 卡）；本卡 5 文件 + 无必破既有断言 + 一个设计空白（R1），拆 2 卡后每卡 10-21 校准轮，均在单会话可控区间（42 有效轮）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] WIP 轮次进度检测 S1 — scripts/wip_progress_check.sh 检测脚本 + autopilot.sh 挂载
   （复刻 stuck_check.sh 模板：扫 running 卡 → git -C <workspace_path> log 判最近 commit 是否
    [WIP] 前缀 + WIP commit 距今秒数；阈值引用 constants WIP_CHECKPOINT_MAX_ROUNDS=15 +
    可能 +WIP_CHECK_COMMENT_WINDOW_MIN 幂等窗口；只 comment [wip-check] 不 block/reclaim；
    scratch/空路径/git 失败 fail-open 跳过；S1 内先定 R1 代理信号方案（主 = WIP commit 距今，
    辅 = heartbeat 事件计数）再写检测体） 预计 10-15 轮
2. [DEV-SUB-2] WIP 轮次进度检测 S2 — oc_wake_check.sh 异常清单源 D + test_wip_progress_check.sh
   + 全量回归 + 收尾
   （oc_wake_check.sh 仿源 A 新增读 [wip-check] comment 的源 D + seen 键 wip-check:<tid>；
    test_wip_progress_check.sh 隔离 DB + temp git 仓库 fixture：has-[WIP] 不误报 / 无-[WIP]
    提醒 / 阈值边界 N-1 vs N / comment 后状态不变（AC-4）/ scratch 跳过；全量 386+ 回归；
    结构化 claim + 飞书推送 + kanban_complete） 预计 12-15 轮
```

- SPLIT: yes（count=2，校准后 39-57 轮远超 20）
- MODE: serial（S1 脚本 → S2 清单+测试单向依赖）
- ROUNDS_EST（校准后）: 48（基准 16 × K=3.00）
- FILES: scripts/wip_progress_check.sh（新）, scripts/autopilot.sh, scripts/oc_wake_check.sh, pipeline/constants.py, scripts/test_wip_progress_check.sh（新）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡）
- TESTS: 新 test_wip_progress_check.sh ~10-15 断言；全量回归 386+ PASS
- RISK: R1 task_runs 无 iteration 列（设计空白，S1 先定代理信号）；R2 测试需 git fixture；R3 幂等窗口防刷屏；R4 全量回归
- ACTION: build_two_dev_cards（assignee=game-engine，serial parents 链）

## 6. 备注

- **R1 是关键约束的实证结论**：需求约束 3 原文「iteration 计数来源：task_runs 表或 dispatcher 状态（需确认哪个可靠）」——已确认 task_runs **无** iteration 列，dispatcher 状态亦不落库（IterationBudget 是 run_agent.py 内存对象）。因此「超 N 轮」必须用代理信号实现，**不能按字面读表**。需求验收 1「X 轮未 checkpoint」输出文案可保留，但轮数来源在 S1 卡内决策并注释互链 DPL-030。
- **只提醒不打断的机制**：与 stuck_check（告警+条件 reclaim）不同，本检测**永不 reclaim/block**——comment + 异常清单（oc_wake 源 D）是仅有的两个输出通道，语义上比 stuck_check 更轻，避免在 worker 实现深水区插入灾难性中断（需求关键约束 1）。
- **与 DPL-030 的关系**：WIP_SOUL_PARAGRAPH（constants.py L248-271）是「提示层」；本卡是「检测+纠偏层」，二者注释互链（S1 检测脚本头注释引用 DPL-030 协议）。阈值常量直接复用 WIP_CHECKPOINT_MAX_ROUNDS，保持单一来源。
- **本评估卡不写代码**；autopilot 读取 [SUB-SPLIT] comment 后建 2 张 [DEV-SUB-*] 卡（parents 链按 serial 挂接）。
