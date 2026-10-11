# PRD: Watchdog v3.0

> 作者：许清楚（产品） | 日期：2026-07-10 | 版本：v3.1
> 依据：B 类 Roundtable 三票一致（产品 t_2eede1f0 + 架构 t_badfe4eb + 研发 t_ffabe17e）
> 替代：PRD v1.0（`docs/prd-p0-18-watchdog.md`）— v2.0 已实现上述 PRD，v3.0 在此基础上重写
>
> **v3.1 变更**：D1 冲突裁定——四维计数统一为架构 §3.3 定义（排除 blocked + project_boards 过滤，支持跨 board 汇总）

## 1. 需求概述

v3.0 是**重写**（非 bug fix），核心变化：watchdog 从"独立常驻守护进程"变为"OC 的随从"。4 项需求：

| # | 需求 | 优先级 |
|---|------|:---:|
| 1 | 每分钟心跳汇报，四维计数格式 `📋 安排N个 \| ✅ 跑完N个 \| 🔄 在跑N个 \| ⏳ 未跑N个` | P0 |
| 2 | 与 OC 生命周期绑定：OC 启动时自动激活 watchdog，OC 停止时 watchdog 发送告别消息后静默 | P0 |
| 3 | 汇报 OC 会话情况：当前会话何时结束（预估/实际）、下一轮 cron 何时启动 | P1 |
| 4 | 去掉三态 SILENT 状态机：有任务→报摘要，无任务→报最后一句→停 | P0 |

## 2. 架构方案

### 两层架构（Roundtable 共识）

```
Layer 1: Collector (no_agent script, 30s cron)
  → 读 kanban.db + .oc_session.json → 输出纯文本统计
  → 无 session file 时 stdout 为空（不输出）

Layer 2: Reporter (LLM cron, 1min, context_from collector)
  → collector 输出非空 → 原文转发
  → collector 输出为空 → 回复"无任务在跑，即将静默"→ 停止播报
```

理由：Layer 1 零 token、可独立测试；Layer 2 保证送达可靠性（走 agent 消息通道），LLM 仅做转发判断不做格式化。

### 会话感知

OC 启动时原子写 `.oc_session.json`（`write .tmp → mv`），结束时删除。Collector 读此文件判断是否播报。文件格式：

```json
{
  "session_id": "abc123",
  "started_at": "2026-07-10T14:30:00",
  "updated_at": "2026-07-10T14:35:00",
  "expected_children": 4,
  "completed_children": 2,
  "next_one_shot_at": "2026-07-10T15:00:00"
}
```

防崩溃残留：`updated_at` 超过 10 分钟（TTL）→ collector 视为无效，删除文件。

### 四维计数定义（产品最终裁定，2026-07-10 v3.1）

| 维度 | 定义 | 范围 |
|------|------|------|
| 📋 安排 | `ready + running`（**排除 blocked**，僵尸卡片不纳入工作量计数） | 当前项目所有关联 board（通过 `project_boards` 过滤，支持跨 board 汇总） |
| ✅ 跑完 | 本次会话 `started_at` 后 `completed_at >= started_at` 的 `done` 任务 | 当前项目所有关联 board |
| 🔄 在跑 | `status = running` | 当前项目所有关联 board |
| ⏳ 未跑 | `status = ready` | 当前项目所有关联 board |

> **裁定依据**：架构师提出的「排除 blocked 僵尸卡片」论点成立——blocked 不可执行，虚增安排计数会误导。四维统一范围为「当前项目关联所有 board + project_boards 过滤」，消除 v3.0 初版中「安排/跑完限 OC 任务，在跑/未跑为全局」的不一致性。

### 状态机简化

```
v2.0: ACTIVE → QUIET → SILENT → ACTIVE (三态 + 信号文件)
v3.0: 有 session file → 播报 | 无 session file → 不播报 (二元)
```

OC 负责管理 session file（创建/更新/删除），watchdog 只管读。复杂度从 watchdog 脚本移至 OC 行为规则，责任边界清晰。

## 3. OC 生命周期绑定

OC 的行为规则（写入 SOUL.md / skill）：

1. **会话启动**：开始分派 kanban 任务前，创建 `.oc_session.json`
2. **会话运行中**：每完成一个子任务，更新 `completed_children` 和 `updated_at`
3. **会话结束**：所有任务 done → 更新 `completed_children == expected_children` → collector 检测到 0 活跃任务 → reporter 输出告别消息 → OC 删除 `.oc_session.json`

Watchdog 不自己创建/删除 cron job——它是一个**持久 cron job**，通过 session file 的存在性决定是否播报。OC 无需管理 cron 生命周期，避免"忘记清理僵尸 cron"的风险。

## 4. 风险与缓解

| # | 风险 | 缓解 |
|---|------|------|
| R1 | OC crash → session file 残留 → watchdog 误报 | 文件 TTL 10min，collector 自检 `now - updated_at > TTL` → 删除 |
| R2 | OC 行为不可靠（LLM agent 可能忘记写 session file） | collector 无 session file 时静默 + reporter 最终兜底告警 |
| R3 | Kanban DB 锁竞争（1min 高频读） | 加 `PRAGMA journal_mode=WAL` |
| R4 | 多 OC 会话并存（未来扩展） | session file 用 `session_id` 命名，预留目录遍历能力 |

## 5. 发布计划

| 阶段 | 内容 | 工作量 |
|------|------|:---:|
| MVP | 格式改四维计数 + 1min 间隔 + 去三态状态机（无生命周期绑定） | 1.0 人天 |
| 完整版 | 两层架构 + session file 生命周期 + OC 会话感知 | +0.7 人天 |

MVP 不绑定 OC 生命周期——Frank 手动管理 watchdog cron。完整版补齐自动化。

## 6. 产出物

- `~/.hermes/profiles/orchestrator/scripts/kanban_collector.py` — Layer 1 采集脚本（新建）
- `~/.hermes/profiles/orchestrator/scripts/.oc_session.json` — 运行时状态文件
- `~/.hermes/profiles/orchestrator/scripts/kanban_watchdog.py` — v2.0 脚本（废弃）
- cron job（collector, 30s, no_agent）— 新建
- cron job（reporter, 1min, LLM, context_from collector）— 修改现有
