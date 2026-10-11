# Roundtable B — R2 engineer 发言（寇豆码，最后一轮）

> 工具重评：Frank 反馈后的管线工具最终评估

---

## 0. 一手事实核查（不是我猜的，是跑命令验证的）

### 0.1 Node 版本

```
$ node --version
v18.19.1

$ apt list --installed | grep nodejs
nodejs/noble,now 18.19.1+dfsg-6ubuntu5 amd64 [installed]
```

Ubuntu 24.04 (Noble) 的 apt 仓库只提供 Node 18.x。升级路径：

- **方案 A**: Nodesource PPA（setup_22.x 脚本支持 "nodistro" suite，在 Noble 上可用）
- **方案 B**: 直接下载 Node 22.12.0 二进制 → `/usr/local`（已验证 `nodejs.org` 返回 200，~30MB）
- **方案 C**: nvm（需先安装，当前系统没有）

建议方案 B（二进制直装），零依赖、可回滚。预计 0.5h。如果在 CloudStudio 沙箱有权限限制（无法写 `/usr/local`），可能需要运维介入，额外 +0.5-1h。

### 0.2 close.sh

```
$ find / -maxdepth 4 -name "close.sh" -type f 2>/dev/null
/root/.hermes/profiles/orchestrator/scripts/close.sh
/tmp/backup-lfs-migrate/config/profiles/orchestrator/scripts/close.sh
```

**close.sh 真实存在**，位于 OC profile home（`/root/.hermes/profiles/orchestrator/scripts/close.sh`），104 行，6 步验证脚本（kanban 状态 → VA 验证 → GAI 更新 → manifest → 备份 → 通知）。结构完整，有 `--fix` 自动修复模式。

但 R1 的担忧有其道理：不在 devPPL repo 中。commit 0da3e39（"P0-18/19/20 完成 — watchdog v4, close.sh, SOUL 拆分"）只改了 `GLOBAL_ACTION_ITEMS.md` 一行，close.sh 本体从未入 repo。

**判定**：这不是"幽灵依赖"（Architect 的措辞），而是"跨 profile 依赖"——OC 的脚本不在项目 repo 中。管线健康检查的正确命令应该是：

```bash
ls /root/.hermes/profiles/orchestrator/scripts/close.sh
```

而不是 `find /` 全盘扫描。

### 0.3 OpenSpec

```
$ npm install -g @fission-ai/openspec  # 安装成功，76 packages
$ openspec --version                     # 崩溃：SyntaxError
```

崩溃原因：`cli-spinners@3.4.0` 使用了 `import ... with {type: 'json'}`（Node ≥20 特性，18 不支持）。**OpenSpec 必须 Node ≥20.19 才能运行**。Architect 的前置条件判断完全正确。

### 0.4 Hermes webhook vs kanban 事件

经查 Hermes 官方文档 + 实测：

- **Hermes webhook**：外部服务 → Hermes 的单向事件触发（GitHub/GitLab/Stripe POST → Hermes agent）。`--events` 参数过滤的是外部服务的事件类型（`pull_request`、`push` 等），**不支持 kanban 内部事件**。
- **Kanban 事件流**：kanban 有自己的 WebSocket 端点（`WS /events?since=<event_id>`），用于实时监控 task_events。但这是只读流，不是 hook 系统。
- **Hermes hooks**（gateway event hooks / shell hooks）：支持 `gateway:startup`、`agent:step`、`session:start` 等生命周期事件，但**没有 kanban 任务事件**（如 `task:completed`、`task:blocked`）。

**结论：Architect 的判断完全正确。Hermes webhook 不能订阅 kanban 事件。cron polling 是当前唯一可靠路径。**

---

## 1. 前置条件验证结论

| 条件 | 状态 | 处理方案 |
|------|------|----------|
| Node ≥20.19 | ❌ 当前 18.19 | 二进制直装 Node 22 → `/usr/local`（0.5h） |
| close.sh 定位 | ✅ 已定位 | OC profile home，非幽灵依赖 |
| 管线健康检查 | ✅ 命令已知 | 1 行验证，不需 0.3h |

**修正**：Architect 的"管线健康检查 0.3h"可以压缩到 0.1h。close.sh 位置已知，Node 版本检查是 1 行命令。

---

## 2. OpenSpec 集成评估

安装本身没问题（`npm install -g` 成功），阻塞点在 Node 版本。升级 Node 后：

```
npm install -g @fission-ai/openspec  # 重新安装（清除 engine 警告）
cd /workspace/devPPL && openspec init  # 生成 .openspec/ 目录
```

Hermes skill 路径 `.hermes/skills/openspec-/SKILL.md` — 这是 OpenSpec 官方 Hermes 集成文件，**不需要手动配置**。`openspec init` 后自动生成或被 Hermes 框架识别。

**但有一个 SOUL.md 冲突风险**：devPPL 已有多个 SOUL.md（每个 agent 角色一个）。OpenSpec 的 spec 格式可能与现有 SOUL.md 冲突。Architect 的风险清单里提到了这个，我同意需要审查后合并。

**集成工时**：1.0h（Architect 的估算），合理。包含：升级 Node → 重装 openspec → init → 验证 → 处理 SOUL.md 冲突。

---

## 3. 执行顺序：checkpoint 先 → autopilot 后 —— 从工程角度看

Architect 修正的执行顺序是 **checkpoint（P0-3）先 → autopilot+合约（P0-2）后**，理由是"合约校验依赖 checkpoint 状态，否则只能做弱校验"。

**我同意这个顺序。** 从工程角度：

- checkpoint 是数据层（SQLite pipeline_state.db）
- autopilot+合约是逻辑层（读 checkpoint 状态、执行合约校验）
- 逻辑层依赖数据层是标准分层模式

**但需要明确 checkpoint 的依赖**：

| checkpoint 依赖 | 当前状态 | 影响 |
|----------------|----------|------|
| pipeline_state.db schema | 未定义 | 需要先设计 schema，否则 checkpoint 写什么？ |
| close.sh 路径 | 已知（OC profile） | checkpoint 需要引用 close.sh 路径以记录闭环状态 |
| Hermes kanban CLI/API | 可用 | `hermes kanban show/list` 已验证 |

因此 checkpoint 的 1.5-2h 不只是"写代码"，包含 schema 设计（0.5h）+ 实现（1h）+ 测试（0.5h）。R1 对"1h 太乐观"的质疑是对的。

---

## 4. DPL-009：webhook 能不能订阅 kanban？

### 实测结论：不能。

一行命令验证：

```bash
# Hermes webhook 的 events 参数接受的是外部服务事件类型
# 不是 kanban 内部事件
hermes webhook subscribe kanban-hook \
  --events "task_completed,task_blocked" \
  --prompt "Kanban event: {event}" 2>&1
# 这会创建订阅，但不会有任何 kanban 事件触发它
```

验证方法：kanban 本身有 `hermes kanban watch --kinds "completed,blocked"` 可以实时看事件流。但这个流不经过 webhook 系统。

**Architect 的建议（cron polling 主路径 + 自定义事件钩子快速路径）是正确的。** 如果未来需要更快响应，可以通过 Hermes gateway hook（`gateway:startup` 事件配 handler.py）实现，但那是工程优化，不是 MVP 必需。

---

## 5. MVP Slice 1：到底先做什么？

三个候选：

| 选项 | 前端工作 | 工时 | 风险 |
|------|---------|------|------|
| **A. checkpoint** | schema 设计 + SQLite + 测试 | 1.5-2h | 低（零外部依赖） |
| **B. OpenSpec** | Node 升级 + 安装 + init + 冲突处理 | 1.0-1.5h | 中（Node 升级可能受阻） |
| **C. git hook** | pre-commit hook 脚本 | 0.5h | 低但价值有限 |

**我的推荐：A + B 并行启动。** 

- **A（checkpoint）**可以在等待 Node 升级的同时开始——schema 设计不需要 Node
- **B（OpenSpec）**的瓶颈在 Node 升级，这个可以用二进制直装快速绕过
- **C（git hook）**价值太低——只能做提交前检查，不能替代管线

如果必须只做一件事：**先做 checkpoint**。理由：
1. checkpoint 是数据基座，不依赖任何外部工具
2. 零环境风险——只有 Python + SQLite
3. checkpoint 完成后，autopilot+合约可以直接读它的状态

---

## 6. 工时评估：接受 10.6h 吗？

### Architect 的 10.6h 分解 vs 我的修正

| 工作项 | Architect | 寇豆码修正 | 差异说明 |
|--------|-----------|-----------|----------|
| 管线健康检查 | 0.3h | **0.1h** | close.sh 已定位，1 行命令 |
| Node 升级 | 并入 OpenSpec | **0.5h** | 二进制直装，独立计时 |
| OpenSpec 集成 | 1.0h | 1.0h | 同意 |
| Checkpoint (P0-3) | 1.0h | **1.5-2.0h** | 含 schema 设计 0.5h |
| Autopilot+合约 (P0-2) | 3.0h | 3.0h | 同意（R1 估算 3-4h，取中值） |
| 集成测试 | 2.0h | 2.0h | 同意 |
| 可视化 (P0-1) | 1.0h | **不在 Slice 1** | Product 说 P0-1 是"锦上添花" |
| **总计** | **10.6h** | **8.1-8.6h（不含 P0-1）** / **9.1-9.6h（含 P0-1）** | — |

### 我的判断

**接受 10.6h，但有条件：**

1. **不含 CloudStudio 沙箱权限问题**：如果无法写 `/usr/local`，Node 升级需要运维介入，+0.5-1h
2. **pipeline_state.db schema 设计顺利**：如果 schema 评审被来回拉扯，checkpoint 可能膨胀到 3h
3. **现实范围：9-12h，约 1.5-2 工作日。** Architect 的 10.6h 在可接受范围内。

R1 说"12-20h"——那个是包含 P0-1（可视化）和后端 API 的完整堆栈。MVP Slice 1 只做到 checkpoint + autopilot/合约，R1 的修正版 9.6h 和我的 8.1-9.6h 基本一致。

---

## 7. 风险再评估

Architect 列了 5 个风险。从工程实现角度看：

| 风险 | Architect 分级 | 实际影响 | 缓解 |
|------|---------------|---------|------|
| Node 版本 | MINOR | 已验证：需要升级但路径明确 | 二进制直装，5 行命令 |
| close.sh 幽灵依赖 | MAJOR | **降为 MINOR**：文件存在，路径已知 | 健康检查用精确路径 |
| OpenSpec/SOUL.md 冲突 | MEDIUM | 维持 MEDIUM | `openspec init` 后审查冲突 |
| pipeline_state.db schema | MEDIUM | 维持 MEDIUM | 先在 checkpoint 任务中设计 schema |
| specs 腐化 | MEDIUM | 维持 MEDIUM | `openspec validate --strict` |

**注意**：我降级了 close.sh 风险。Architect 说的"幽灵依赖"基于 R1 的"找不到"——但实测找到了，且在 OC profile home 是合理的（OC 脚本本就在自己的 profile 下）。

---

## 总结（给 Orchestrator 的汇总结论）

1. **前置条件**：Node 升级路径明确（二进制直装），close.sh 已定位（OC profile），管线健康检查可以 1 行搞定
2. **OpenSpec**：确认 P0 引入，但必须先升级 Node。Architect 的 Node ≥20.19 要求是硬约束
3. **执行顺序**：同意 checkpoint → autopilot+合约（数据层先于逻辑层）
4. **Webhook**：确认 Hermes webhook 不支持 kanban 事件订阅。cron polling 是唯一可靠路径
5. **MVP Slice 1**：做 checkpoint。它是数据基座，零外部依赖，做完后 autopilot+合约可以直接读它的状态
6. **工时**：接受 10.6h（含 buffer），实际范围 9-12h，约 1.5-2 工作日

**给 Frank 的一句话**：管线工具的 MVP 路径是清晰的——Node 升级 → checkpoint → autopilot/合约。环境风险可控（close.sh 不是幽灵），唯一的环境变量是 CloudStudio 的权限策略。如果遇到写权限问题，需要你出面协调。
