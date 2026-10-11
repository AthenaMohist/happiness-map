# 开发管线脚本化可行性分析

> 作者：Hermes Orchestrator | 日期：2026-07-13 | 版本：v1.0
> 触发：Multica 架构对比 + 现有管线稳定性反思
> 状态：P4 预研，待后续深入

---

## 1. Multica 的启发

Multica（multica-ai/multica）是一个开源的 Managed Agents 平台，核心设计围绕"将编码 Agent 转化为团队协作者"。对照我们的 6 步开发管线，以下设计有直接借鉴意义：

### 1.1 结构化任务生命周期

| Multica | Hermes 当前 | 差距 |
|---|---|---|
| `queued → claimed → in_progress → review → done` | `todo → running → done` | 我们缺少 `review`（验收）和 `claimed`（认领）两个显式状态 |
| 每个状态转换有前置条件校验 | 状态切换无强制校验 | task 标了 done 但 GAI 没更新、manifest 没补——状态机不完整 |
| 状态变更触发事件（WebSocket 推送） | OC `sleep 30` → poll kanban | 被动轮询 vs 主动推送 |

**借鉴**：把 SOUL.md 中已有的闭环序列 6 步映射为显式 kanban 状态，done 必须通过所有校验。

### 1.2 Autopilot 统一模式

Multica 的 autopilot：`定时触发 → 创建 Issue → 路由给 agent → 追踪结果 → 回报`。我们四个 cron job（做梦、权限审计、VA 证伪、Watchdog v3.0）各自为政，存在三个盲区：
- 做梦/审计 deliver=local → Frank 看不到
- VA 证伪 bot-not-in-chat → 投递失败
- Watchdog v3.0 全部 paused → 无心跳

**借鉴**：统一 cron 入口模板，所有定时任务走同一套创建卡片→路由→结果回写→投递的管道。

### 1.3 进度事件替代轮询

Multica 用 WebSocket 推送状态变更。我们不需要 WebSocket 这么重，但"卡片 body 内追加时间戳事件日志"可以达到同样效果——OC 不用轮询，读最后一行就知道断在哪。

### 1.4 不做的事

Multica 的前端面板（Next.js + 看板视图）和 WebSocket 实时流不引入。飞书 DM + kanban 文字界面已满足当前需求。引入 Docker Compose + PostgreSQL 换一个面板性价比太低。

---

## 2. 脚本化：优缺分析

### 2.1 优点

| 优点 | 说明 |
|---|---|
| **流程固化** | "记得补 GAI、记得补 manifest"变成代码，不会遗忘 |
| **稳定性提升** | 每次执行路径一致，不依赖 OC 的"当时记得" |
| **可审计** | 每步执行留下结构化日志，出问题可追溯 |
| **跨会话续接** | 新 OC 读 `pipeline_state.db` 就知道断在哪，不靠 relay cron |
| **减少 OC 轮次消耗** | 当前 OC 手动 sleep-poll 每一轮耗费 token；脚本化后 OC 只处理需要人类判断的节点 |
| **可测试** | 每个 step 脚本可独立运行、模拟测试 |

### 2.2 风险和缓解

| 风险 | 严重度 | 缓解 |
|---|---|---|
| **过度自动化**——不该自动的决策被跳过 | 高 | 关键决策点设人工闸门（D 类 roundtable、merge 前确认），脚本到闸门即停，不穿越 |
| **脚本 bug 导致静默卡死** | 高 | 每步超时 + watchdog 播报；卡超 30 分钟 → 飞书告警 Frank |
| **与现有 kanban/dispatcher 冲突** | 中 | 脚本不做替代，只做"胶水"——读 kanban 状态、创建卡片、等 dispatcher 完成 |
| **维护成本**——多一套代码要管 | 低 | 脚本总量小（初始 < 500 行），pipeline scope 边界清晰 |
| **灵活性丧失**——脚本太死板 | 中 | 脚本提供默认路径 + `--skip-step` / `--manual` 覆盖参数 |

### 2.3 什么不该脚本化

以下决策点**必须保留人工闸门**，脚本到此处停止并通知 OC/Frank：

- D 类 roundtable 发起和裁定（议题 1/2/3 需要多方评审）
- merge 回 main 的最终确认
- 产品方向变更（PRD 级别的需求调整）
- 安全敏感操作（token 变更、权限提升）

---

## 3. 可行性分析

### 3.1 已有基础设施

| 需要 | 已有 | 状态 |
|---|---|---|
| 任务状态持久化 | `pipeline_state.db` (SQLite)，infomanager 已用 | ✅ 生产级 |
| Kanban 操作 | `hermes kanban create/show/list/complete` CLI | ✅ 可用 |
| Agent 指派 | dispatcher 自动路由 | ✅ 可用 |
| Git 操作 | 所有 agent 可 `git` | ✅ 可用 |
| 消息通知 | 飞书 API 已封装（`send_feishu_msg`） | ✅ 可用 |
| 状态文件 | `.oc_relay.json` / `.oc_session.json` 模式已验证 | ✅ 可用 |
| Cron 调度 | `hermes cron create` 支持 script 模式 | ✅ 可用 |

### 3.2 需要新增的部分

| 新增 | 复杂度 | 说明 |
|---|---|---|
| `pipeline/state.py` — 状态机核心 | 中 | 读写 `pipeline_state.db`，定义状态和转换规则 |
| `pipeline/step_*.sh` — 步骤脚本（5-7 个） | 低 | 每个脚本：preflight → execute → handoff |
| `pipeline/autopilot.sh` — 自动推进 | 低 | 替代 OC sleep-poll，每 30s 检测状态变化 |
| `pipeline/resume.sh` — 跨会话续接 | 低 | 读 state → 跳到当前 step |
| `pipeline/close.sh` — 强制闭环 | 低 | GAI + manifest + 备份 + 通知，缺一不可 |

**总计预估：400-600 行 shell/python，不引入新依赖。**

### 3.3 与现有组件的关系

```
autopilot.sh (cron 30s)
    │
    ├── 读 kanban 状态 + pipeline_state.db
    ├── 检测到状态变化 → 执行对应 step_*.sh
    │       │
    │       ├── step_dev.sh   → 创建研发卡片 → 等待 done → 校验产物
    │       ├── step_qa.sh    → 创建 QA 卡片 → 等待报告 → D类闸门(停)
    │       ├── step_verify.sh → 创建 VA 卡片 → 等待 VERIFIED
    │       ├── step_merge.sh  → 合并 + S6 → 人工闸门(停)
    │       └── step_close.sh  → GAI + manifest + 备份 + 通知
    │
    └── 异常 → watchdog 播报
```

**不替代 kanban，不替代 dispatcher，不替代 agent——只替代 OC 的 sleep-poll 手工推进。**

---

## 4. 结合项目文档管理、工作空间制、上下文管理

### 4.1 项目文档管理

脚本化后，管线的每一步都会产生结构化元数据：

| 步骤 | 产出物 | 存储位置 |
|---|---|---|
| S1: 初始化 | PRD + 架构设计 + OC 评审记录 | `docs/prd-{P0-id}.md`, `docs/arch-{P0-id}.md` |
| S2: 研发 | 分支 + 代码 | `feat/{P0-id}`, kanban 卡片 body |
| S3: QA | 测试方案 + 测试报告 + D 类 roundtable 记录 | `docs/qa-test-plan-{P0-id}.md`, `docs/qa-test-report-{P0-id}.md`, `docs/roundtables/` |
| S4: VA | claims + verified/falsified | kanban 卡片结果 |
| S5: 合并 | merge commit + S6 检测 | git log |
| S6: 关闭 | GAI 更新 + manifest 更新 | `GLOBAL_ACTION_ITEMS.md`, `manifest.yaml` |

**价值**：脚本可以从这些产出物中自动汇总。比如 `autopilot.sh` 在 close 阶段自动检查 `docs/qa-test-report-{P0-id}.md` 是否存在、`manifest.yaml` 是否有新条目。

### 4.2 工作空间制

我们现有 workspace 按项目隔离：

```
/workspace/devPPL/     ← 管线本身的 workspace
/workspace/InfoManager/ ← Infomanager workspace
/workspace/游戏/       ← 游戏项目 workspace（待定）
```

脚本化后，每个项目 workspace 有独立的 `pipeline_state.db`，管线脚本通过 `--workspace` 参数指定作用域：

```bash
pipeline/autopilot.sh --workspace /workspace/devPPL
pipeline/autopilot.sh --workspace /workspace/InfoManager
```

这保持了工作空间隔离，不会互相污染。

### 4.3 上下文管理

当前上下文管理的问题：
- OC 换会话后丢失之前的状态认知
- relay cron 跨会话传递的信息太粗糙（只传 phase + detail）
- 新 OC 不知道"上一步发生了什么"

脚本化后，上下文通过结构化方式传递：

| 传递方式 | 内容 | 接收方 |
|---|---|---|
| `pipeline_state.db` | 当前 step、状态、超时、任务 ID | 新 OC / autopilot |
| kanban 卡片 body 事件日志 | 每步的时间戳 + 角色 + 结果 | 所有人 |
| `GLOBAL_ACTION_ITEMS.md` | 全局待办状态 | OC / Frank |
| `docs/` 下的 PRD/QA/VA 文档 | 完整的决策和验证链 | 所有人 |

**新 OC 启动时**：读 `pipeline_state.db` → 知道当前所有活跃任务在哪一步 → 读对应 kanban 卡片 body → 知道具体发生了什么 → 继续推进。不需要任何 relay cron。

---

## 5. 实施建议

### 5.1 三阶段推进

| 阶段 | 范围 | 预期效果 |
|---|---|---|
| **Phase 1: 最小可行** | `close.sh` + `autopilot.sh` + `resume.sh` | 解决最痛的三个问题：闭环遗漏、OC 轮询消耗、跨会话断裂 |
| **Phase 2: 全流程** | 所有 step 脚本 + D 类闸门集成 | 完整 6 步管线自动化，人工决策点保留 |
| **Phase 3: 生态** | 多 workspace 支持 + 指标面板 + 自适应 SLA | 跨项目统一管线，运维可观测 |

### 5.2 Phase 1 具体清单

| 脚本 | 行数估计 | 职责 |
|---|---|---|
| `pipeline/state.py` | ~80 | 状态机定义 + pipeline_state.db 读写 |
| `pipeline/close.sh` | ~50 | 强制闭环：GAI → manifest → 备份 → 通知 |
| `pipeline/autopilot.sh` | ~60 | 30s cron 入口：读 kanban → 检测变化 → 推下一步 |
| `pipeline/resume.sh` | ~30 | 读 state → 恢复上下文 → 打印当前状态 |

### 5.3 铁律

1. **脚本不替代 kanban**——脚本只读 kanban 状态、创建卡片、等结果。实际工作由 agent 通过 dispatcher 执行
2. **关键决策点设人工闸门**——脚本到 D 类 roundtable / merge 前停止
3. **失败不回退**——脚本失败时保留现场（日志 + state + kanban 状态），由 OC 或 Frank 人工介入
4. **先验证再上线**——Phase 1 在 InfoManager 项目试点，跑通后推广到 devPPL

---

## 6. 附录：与 Multica 的功能对照

| 维度 | Multica | Hermes（脚本化后） |
|---|---|---|
| 任务生命周期 | queued→claimed→running→done | queued→claimed→dev→qa→verify→merge→closed |
| 状态推送 | WebSocket | kanban 卡片 body 事件日志 + watchdog 播报 |
| 技能复用 | 内置 Skill 系统 | Hermes skill 系统 + pipeline script 模板 |
| Autopilot | 创建 Issue → 路由 → 追踪 | cron → 检测 kanban → 执行 step 脚本 |
| 多 workspace | 有 | 通过 `--workspace` 参数 |
| 前端面板 | Next.js 看板 | 飞书 DM + kanban CLI |
| 部署 | Docker Compose + PostgreSQL | 纯 shell/python，零新依赖 |
