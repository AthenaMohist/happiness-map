# 2026-07-08 — 项目流程复盘：workspace、讨论记录串联、测试方案评审

## 议题来源

Frank 在 DM 中提出三个关键问题，涉及开发流程的完整性。

## 参与人

- Frank（发起 + 裁决）
- orchestrator（记录 + 分析）

## 议题一：Workspace 与辩论上下文传递

### 问题

Frank 发起辩论时，议题、参考资料能否顺利到达每个角色手上？

### 现状分析

| 维度 | 现状 |
|------|------|
| Hermes workspace 功能 | ✅ kanban 支持 `workspace_kind`: `scratch` / `dir:<path>` / `worktree:<path>` |
| roundtable 快速模式 (`hermes -z`) | ❌ 无 workspace 概念，每个 `--profile` 启动独立 session |
| 上下文传递方式 | 通过 prompt 字符串（`build_agent_context`）注入议题 + 前面角色发言 |
| 项目参考文档（PRD/架构文档） | ❌ 不会自动进入子角色 session |
| `hermes -z --workdir` | ⚠️ 待确认是否支持 |

### 风险

角色之间"鸡同鸭讲"——每个人基于不完整的上下文发言，遗漏关键约束。

### 方向

- 短期：`hermes -z` 加 `--workdir` 让项目 `.hermes.md` 自动注入
- 中期：审计模式用 `kanban_create(workspace_kind="dir")` 共享目录
- 备选：自研 context injector

## 议题二：讨论记录串联

### 问题

已有 session 记录和审计，是否需要额外工具把上下文、讨论内容、产出报告串起来？

### 现状分析

| 记录类型 | 位置 | 问题 |
|---------|------|------|
| 角色发言 | `hermes -z` stdout（非持久） | 只在 orchestrator 当前 session 可见 |
| Meeting record | 项目 `docs/meetings/` | ✅ 结构化，但手工写 |
| 辩论 session | `~/.hermes/state.db` 各角色独立 | 零散，不可跨 session 查询 |
| kanban 卡片 | `kanban.db` | 可追溯，但与 session 不互链 |
| VA 审计 | 独立 claims | 独立系统 |

### 风险

无法高效追溯"2026年7月关于某个技术选型的完整讨论链条"。

### 方向

- 确认 `hermes project` 功能是否能提供统一线索
- 自研 Project Thread 工具（链接 session → kanban → meeting record → VA）
- 短期：手工维护 meeting record 作为线索索引

## 议题三：测试方案评审（5 步闭环）

### Frank 提出的 5 步闭环

```
1. 初期讨论 → PRD + 架构设计 → orchestrator 评审（100% 符合 Frank 要求）
2. 切分支 → 研发推进 + QA 并行出测试方案 → 评审测试方案
3. QA 测试 → 测试报告 → 按风险等级判定通过/驳回/暂缓
4. QA 全绿 → VA 验证
5. VA 通过 → 合入主线
```

### 当前 Gap

| 步骤 | 现状 | Gap |
|:---:|------|-----|
| 1 | `orchestrator-review-protocol.md` 已有 | ✅ 缺执行频率约定 |
| 2 | QA 一个人定测试方案 | ❌ **最大风险：无评审环节** |
| 3 | `qa-finding-workflow.md` 有分级标准 | ⚠️ 论证流程不够自动化 |
| 4 | ✅ 已有 | — |
| 5 | ✅ 已有 | — |

### 决议

- **步骤 2**：在 roundtable-debate skill 新增"测试方案评审"议题类型（D 类：Test Plan Review）
  - 触发时机：研发切分支开始编码时，QA 并行提案
  - 参与者：QA（提案方）+ product + architect + engineer（评审方）
  - 核心目标：(a) 测试覆盖是否满足产品需求 (b) 测试是否覆盖架构风险点 (c) 验收标准是否可量化
  - 评审通过后 QA 才能进入正式测试
- **步骤 1**：orchestrator 审查 PRD/架构设计，现有协议可用，需纳入常规流程
- **步骤 3**：qa-finding-workflow.md 已覆盖分级，论证流程需并入 D 类评审

## 行动项

| # | 内容 | 负责人 | 类型 |
|---|------|--------|------|
| 1 | 修改 roundtable-debate skill — 新增 D 类"测试方案评审" | orchestrator（本次） | skill 改动 |
| 2 | 修改 SOUL.md — 更新 5 步闭环流程 | orchestrator（本次） | SOUL 改动 |
| 3 | 研究 Hermes workspace/context 能力 | game-architect（kanban） | 研究 |
| 4 | 研究上下文传递 + 讨论记录串联方案 | game-engine（kanban） | 研究 |
| 5 | 确认 devPPL 项目 workspace 结构 | orchestrator（本次） | 初始化 |

## Frank 裁决

- 测试方案评审：直接改 skill 和 SOUL，不走 roundtable（方向已明确）
- workspace + 记录串联：打包上下文发给架构和研发，由他们网上搜索 + 提案
- 讨论记录：orchestrator 手工记录到 devPPL 下
- **hermes -z 方案废弃**（2026-07-08 后续裁决）：scratch workspace 随任务完成被清理，上下文丢失，不可追溯审计。roundtable 全面切换为 kanban_create + dir workspace（v2.2）

## 创建时间

2026-07-08
