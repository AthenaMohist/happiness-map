# Watchdog v3.0 产品评估

> 作者：许清楚（产品） | 日期：2026-07-10
> 任务：B 类 Roundtable — 对 Frank 提出的 Watchdog v3.0 四项需求进行产品评估

---

## 一、逐项需求评估

### 需求 1：每分钟心跳汇报，格式 `📋 安排N个 | ✅ 跑完N个 | 🔄 在跑N个 | ⏳ 未跑N个`

**当前实现**：
- 2min 间隔，输出逐条任务列表 + 汇总 `"N running, M blocked, K ready"`
- 没有 "安排/跑完/在跑/未跑" 的四维统计

**差距**：
- 间隔：2min → 1min（trivial，改 cron schedule 即可）
- 格式：逐条列表 → 四维计数汇总。这是输出逻辑的核心改动。
- 语义：Frank 要的是 "一屏看清全局" 的仪表盘，不要逐条滚动。当前格式适合日志，不适合飞书消息。

**产品判定**：格式重写，非 bug。`_print_active_report()` 需完全重写。工作量中等。

---

### 需求 2：与 OC 生命周期绑定 — OC 创建任务时自动创建 watchdog，OC 停止时 watchdog 最后提示 "无任务在跑，即将静默" 然后停

**当前实现**：
- watchdog 是一个独立 cron job，手动创建/删除，与 OC 无任何关联
- 状态机有 SILENT 概念，但 watchdog 本身永不停止，只是不输出

**差距**：
- 当前 watchdog 是常驻的，Frank 要的是 "随 OC 而生，随 OC 而死"
- 当前 watchdog 不知道 OC 是否存在、是否活跃
- 添加生命周期绑定 = watchdog 从常驻进程变成 OC 的子资源

**产品判定**：架构级变化。这不是在现有 watchdog 上改，而是重新定义 watchdog 的角色——从 "独立守护进程" 变成 "OC 的随从"。工作量高。

---

### 需求 3：汇报 OC 会话情况 — 当前会话何时结束、新 one-shot cron 何时启动，确保 Frank 知道 OC 没断

**当前实现**：
- 完全不感知 OC 会话
- watchdog 只看 kanban board 上的任务，不知道这些任务是谁创建的

**差距**：
- 需要新增一个数据源：OC 的活跃状态
- OC 的 "会话" 概念需要定义：什么算 "会话开始"？什么算 "会话结束"？
- 需要 OC 产出某种心跳信号，watchdog 消费

**产品判定**：全新功能。需要设计 OC 心跳协议。工作量中等。

---

### 需求 4：不要复杂的 SILENT 状态机

**当前实现**：
- 三态状态机：ACTIVE → QUIET → SILENT → ACTIVE（通过 `.kanban_resume` 信号）
- 4 个 tick（~8 分钟）才能进入真静默
- 有 `.kanban_watchdog_meta.json` 持久化静默计数

**差距**：
- Frank 说的是 "不要复杂的状态机"，当前恰有一个三态 FSM
- 简化方向：去掉 QUIET 过渡态和 SILENT 持久化，watchdog 只在有任务时汇报、无任务时就停（配合需求 2 的生命周期）

**产品判定**：简化，非重写。但简化方式取决于需求 2 的最终方案——如果 watchdog 随 OC 生命周期停止，SILENT 状态自然地不再需要。本质上，需求 2 解决了需求 4。

---

## 二、四个评估问题

### Q1：改动量多大？是修 bug 还是重写？

**判定：重写（rewrite），非 bug fix。**

对比矩阵：

| 模块 | 当前 v2.0 | Frank 要的 v3.0 | 改动性质 |
|------|----------|----------------|---------|
| 输出格式 | 逐条任务列表 | 四维计数 `📋/✅/🔄/⏳` | **重写** `_print_active_report()` |
| 运行方式 | 独立常驻 cron | 随 OC 生命周期创建/销毁 | **架构级变化** |
| 状态机 | ACTIVE/QUIET/SILENT 三态 | 无状态机（有任务就报，无任务就停） | **删除** |
| 数据源 | 仅 kanban board | kanban board + OC 会话状态 | **新增数据源** |
| 间隔 | 2min | 1min | 配置变更（trivial） |
| DB 读取层 | `get_all_boards()` / `get_board_tasks()` | 复用 | 不变 |

**结论**：6 个模块中 4 个需要重写或新增，1 个简化，1 个不变。总改动量约为当前代码的 60-70%。**不是修 bug，是新版设计。**

---

### Q2：会话感知如何实现？

"OC 会话" 需要先定义。经分析 OC 的 SOUL.md 和运行方式，OC 的 "会话" 本质是：

> **OC 的 gateway 进程存活 + 有活跃的 kanban 任务分配**

具体可通过以下信号组合感知：

**方案 A：OC 主动心跳（推荐）**

OC 在每次完成任务循环后（创建/完成 kanban 任务后），touch 一个信号文件 `.oc_heartbeat`，记录时间戳。

Watchdog 读取此文件：
- 如果心跳时间在 5 分钟内 → OC 活跃，正常汇报
- 如果心跳时间超过 10 分钟 → 汇报 "⚠️ OC 最后活动: 10 分钟前"
- 如果文件不存在 → 汇报 "⚠️ OC 会话状态未知"

**方案 B：读 OC 的 cron job 列表（备选）**

Watchdog 通过 `hermes --profile orchestrator cronjob list` 查询 OC 是否有一 shot cron 在运行。如果有 → OC 活跃；如果没有 → OC 可能已静默。

方案 B 的缺点：cron 列表可能包含非 OC 创建的 job，存在误判。且 cronjob list 只能在 LLM agent 模式下调用（不是 no_agent 脚本的能力）。

**方案 C：读 kanban task history（备选）**

通过检查 kanban task 的 `created_at` 时间戳，判断最近是否有 OC 分派的任务。如果最近 N 分钟内有新任务创建 → OC 活跃。

缺点：不能区分 OC 创建的任务 vs Frank 手动创建的任务。

**产品推荐**：**方案 A（OC 主动心跳）+ 方案 C（任务时间戳）双重判断。** OC 主动 touch 心跳是最准确的信号，任务时间戳作为 fallback（以防 OC crash 后心跳文件未更新）。

---

### Q3：与 OC 生命周期绑定的触发机制？

Frank 的要求很清楚：**OC 启动时自动创建 watchdog，OC 停止时 watchdog 发送告别消息然后停。**

实现路径：

**阶段 1：OC 主动管理 watchdog 生命周期**

OC 的 SOUL.md 增加规则（或通过 `kanban-event-hooks` skill）：

```
规则 1 — 会话启动:
  当 OC 开始创建/分派 kanban 任务时（即 "开始工作"），
  检查是否已有 watchdog cron job：
    - 如果没有 → 创建 watchdog cron job（schedule: "1m", no_agent, deliver: feishu）
    - 如果有 → 跳过（幂等）

规则 2 — 会话结束:
  当 OC 判断当前无更多工作（所有任务 done/archived，无待处理 roundtable）：
    1. 调用 watchdog 脚本的特殊模式：输出 "无任务在跑，即将静默" 后 exit 0
    2. 删除 watchdog cron job
    3. 删除 .kanban_resume 和 .kanban_watchdog_meta.json（清理状态）

规则 3 — 异常恢复:
  如果 OC 被 restart（gateway 重启），新 OC 实例检测到残留的 watchdog cron：
    1. 删除旧的 watchdog cron
    2. 重新创建（fresh start）
```

**阶段 2：Watchdog 脚本的修改**

Watchdog 不再有 SILENT 状态机。改为极简逻辑：

```python
def main():
    # 1. 读 OC 心跳（会话感知）
    oc_alive = check_oc_heartbeat()

    # 2. 扫描 kanban
    tasks = scan_all_boards()
    running = count_by_status(tasks, "running")
    blocked = count_by_status(tasks, "blocked")
    ready = count_by_status(tasks, "ready")
    done_recent = count_by_status(tasks, "done", since_last_tick=True)

    # 3. 总是输出（不再静默——静默由 OC 删除 cron 实现）
    print(f"📋 安排{ready}个 | ✅ 跑完{done_recent}个 | 🔄 在跑{running}个 | ⏳ 未跑{blocked}个")
    if not oc_alive:
        print("⚠️ OC 心跳超时，可能已静默")
```

关键变化：watchdog **自己不决定是否静默**。它总是输出心跳。静默由 OC 决定（规则 2 中删除 cron job）。

**阶段 3：优雅退出**

OC 停止时，不直接删除 cron——先让 watchdog 发一条 "告别消息" 再删：

```bash
# OC 执行：
python3 kanban_watchdog.py --farewell   # → 输出 "👋 无任务在跑，即将静默"
hermes --profile orchestrator cronjob remove <watchdog_job_id>
```

**产品判定**：触发机制清晰可行。复杂度从 watchdog 脚本（状态机）转移到 OC 的行为规则（SOUL.md / skill）。符合 Frank 的 "不要复杂状态机" 要求。

---

### Q4：有什么风险或架构限制？

#### 风险清单

| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|------|:---:|:---:|---------|
| **R1** | OC gateway 意外崩溃 → watchdog cron 残留 → 持续发送心跳（但没有新任务）→ Frank 误以为一切正常 | 中 | 高 | watchdog 加入 OC 心跳检测：如果 OC 心跳超时，watchdog 在消息中显式报告 "⚠️ OC 无响应"。不能只沉默——沉默 = Frank 不知道出事了。 |
| **R2** | OC restart 后旧 watchdog cron 未清理 → 同时存在两个 watchdog → 重复消息 | 中 | 中 | OC 启动时先 `cronjob list` + 清理所有 watchdog cron，再创建新的。幂等设计。 |
| **R3** | 1min cron 粒度不可靠（架构文档 §1.2 R3 已指出的问题）→ 心跳可能延迟或跳过 | 低 | 中 | 架构已有 Plan B（独立 daemon 30s 循环）。如果 1min cron 表现不佳，回退到 daemon 方案。 |
| **R4** | kanban board 多的情况下，每次 tick 全量扫描 → 1min 间隔可能来不及 | 低 | 低 | 当前 devPPL 只有 1 个 board，几十个任务。SQLite 查询毫秒级，瓶颈不在此。 |
| **R5** | OC 和 watchdog 并发读写 kanban.db → SQLite 锁冲突 | 低 | 低 | 当前代码已有 `try/except sqlite3.Error`，遇到锁时跳过该 tick。1min 后重试即可。 |
| **R6** | 依赖 OC 主动管理 lifecycle → OC 的行为可能不可靠（LLM agent 可能忘记执行规则 2/3） | 中 | 中 | 在 SOUL.md 中写成显式规则，配合 kanban-event-hooks skill 的强制加载。同时 watchdog 自检：如果运行超过 N 分钟且 OC 无心跳 → 自动降级输出 "OC 超时"（但不自停——留给 Frank 手动处理）。 |

#### 架构限制

| # | 限制 | 影响 | 是否可绕过 |
|---|------|------|:---:|
| **L1** | Hermes cron 系统不支持 "parent-death 自动清理子 cron" | OC crash 后 watchdog 残留在系统中 | 否。必须靠 watchdog 自检 OC 心跳 + OC restart 时主动清理。 |
| **L2** | `no_agent` cron job 无法调用 `hermes cronjob list`（需要 LLM agent 模式） | 方案 B（读 cron 列表）在 no_agent 模式下不可行 | 是。改用方案 A（OC 主动写心跳文件）。 |
| **L3** | Watchdog 必须在 orchestrator profile 下运行（Feishu 凭证仅在此 profile） | 不能跨 profile 部署 | 否。这是硬约束，按架构文档 §2.1 的设计原则处理。 |
| **L4** | OC 的 "会话结束" 判断依赖 LLM agent 的判断（何时算 "无更多工作"） | 可能存在误判——过早停止 watchdog 或过晚不停止 | 部分。可以加保守策略：至少等 2 个心跳周期确认无新任务后再停止。 |

---

## 三、产品裁决

### 结论：同意 Frank 的方向，v3.0 需要重写

**理由**：

1. v2.0 的核心假设（独立常驻 watchdog）与 Frank 的要求（随 OC 生命周期）根本冲突。不是修修补补能解决的。
2. 输出格式从 "运维日志" 变为 "高管仪表盘"，语义完全不同。
3. 去掉 SILENT 状态机本质上是把复杂度从 watchdog 脚本移到了 OC 的行为规则——**整体复杂度不降，但责任边界更清晰：watchdog 只管汇报，OC 管生命周期。**

### 建议方案（最小可行版）

考虑到改动量大，建议分 **MVP** 和 **完整版** 两步走：

**MVP（1.0 人天）**：
- 改输出格式：`📋 安排N个 | ✅ 跑完N个 | 🔄 在跑N个 | ⏳ 未跑N个`
- 改 1min 间隔
- 去掉 SILENT 状态机 → watchdog 始终输出（无任务时输出全 0）
- **不做生命周期绑定、不做会话感知**
- 由 Frank 手动管理 watchdog cron 的创建/删除

**完整版（追加 0.7 人天）**：
- OC 生命周期绑定（OC 创建/删除 watchdog cron）
- OC 心跳检测（会话感知）
- 异常恢复逻辑（OC restart → 清理旧 watchdog + 重建）

### 风险提示

最大的风险不是技术实现，而是 **OC 行为可靠性**。OC 是 LLM agent，可能出现 "忘记清理 watchdog cron" 的情况。建议：

1. watchdog 加自检超时：运行 > 30 分钟且 OC 无心跳 → 消息中显式标注 "⚠️ OC 无响应（已运行 X 分钟）"
2. 如果 MVP 阶段手动管理表现稳定，完整版可以考虑用独立 daemon 替代 cron（架构 Plan B），用 while+sleep 循环实现更可靠的 1min 心跳
