# Roundtable B 产品发言：接力 cron 与 Watchdog v3.0 合并方案

> 角色：许清楚（产品负责人） | 日期：2026-07-10
> 议题：B 类头脑风暴 — 接力 cron 播报 + watchdog v3.0 合并
> 标准依据：`docs/prd-p0-18b-watchdog-v3.md` v3.1

---

## 一、问题诊断：Frank 到底痛在哪里？

从产品视角拆解，当前有三层问题：

| # | 问题 | 用户影响 |
|---|------|---------|
| **P1** | 接力 cron（OC one-shot）中间 tick 全部 [SILENT]，Frank 看不到过程 | **黑盒体验**：OC 在做事但 Frank 不知道做到哪了。一个 4 轮派发的 OC session，Frank 只看到第 1 条「派发开始」和第 4 条「全部完成」，中间 2-3 个 tick 完全消失 |
| **P2** | 接力 cron 和 watchdog 都在扫 kanban | **资源浪费**：两次 SQLite 查询同一批数据，且各自产出一份播报。Frank 收到两份格式不同、语义重叠的消息，增加认知负担 |
| **P3** | 接力 cron 通过 LLM agent 判断「该做什么」，但判断过程对 Frank 不透明 | **信任问题**：Frank 不知道 OC 是「已识别任务，正在派发」还是「没扫到新任务，准备休眠」。两种状态外部看起来一模一样 |

**Frank 要的不是两个系统，是一个统一的「进度条」：从哪里开始、做到哪了、还剩多少。**

---

## 二、方案评估

### 方案 A：Watchdog 脱离 OC 生命周期，变为全局 kanban 心跳

**判定：❌ 不推荐**

理由：
1. **直接违反 Frank 需求 #4**：「OC 流程跑完 → 心跳停止」。全局心跳意味着 OC 静默后 Frank 还会收到「安排0 | 跑完0 | 在跑0 | 未跑0」，这是 Frank 明确不想看到的噪音。
2. **与 v3.0 PRD 冲突**：Watchdog v3.0 的核心设计原则是「会话驱动」，PRD §3 明确 watchdog 不自己决定播报——由 session file 的存在性决定。方案 A 等于推翻 v3.0 的设计基础。
3. **产品代价过高**：v3.0 刚完成 D1/D2 审定、62 项测试通过，推翻核心原则意味着重新设计、重新测试、重新 review。用户感知收益（全局心跳）远低于重做成本。

### 方案 B：接力 cron 降级为 no_agent 纯状态机脚本 → 状态写入共享文件 → collector 统一播报

**判定：⚠️ 方向正确但执行有误**

理由：
1. 「接力 cron 降级为 no_agent」不可行——接力 cron 的核心价值是 **LLM 决策**（判断该派发什么任务、是否该停止）。no_agent 脚本只能做确定性逻辑，无法替代 LLM 的判断能力。如果把 OC 的判断逻辑也写死，等于废掉 OC 的智能分派能力。
2. 但「状态写入共享文件 → collector 统一播报」是对的——这正是 v3.0 已有架构的自然延伸。

### 方案 C（产品推荐）：接力状态透传 + watchdog 统一播报

**判定：✅ 推荐**

核心思路：**不降级接力 cron 的 LLM 能力，只让它在做决策的同时把「我做到哪了」写出来。**

---

## 三、推荐方案设计

### 3.1 架构：扩展 session file 协议

当前 `.oc_session.json` 已有 `status`（active/draining/stopped）和 `role`（orchestrating/executing）字段。只需增加一个 `phase` 字段：

```json
{
  "session_id": "oc_20260710_143000",
  "started_at": 1750600200,
  "updated_at": 1750600260,
  "status": "active",
  "role": "orchestrating",
  "phase": "dispatching",          // 新增
  "phase_detail": "P0-15 D2 修复", // 新增：当前在做的事
  "expected_children": 4,
  "completed_children": 2,
  "project_boards": ["devPPL"]
}
```

`phase` 枚举值：

| 值 | 含义 | OC 在做什么 | Frank 看到的 |
|----|------|------------|-------------|
| `polling` | 轮询 kanban | 扫描 ready 任务，判断是否需介入 | 「🔗 接力：轮询中 — 扫描任务队列」 |
| `dispatching` | 派发任务 | 创建下游 kanban 任务 | 「🔗 接力：派发中 — P0-15 D2 修复 (3/5)」 |
| `waiting` | 等待结果 | 子任务在跑，OC 等待完成 | 「🔗 接力：等待中 — 3 个子任务在跑」 |
| `completed` | 本轮完成 | 所有子任务 done，准备停止 | 「🔗 接力：本轮完成 ✅」 |

### 3.2 数据流

```
OC (LLM agent, one-shot cron)
  │
  │  每次 tick：
  │  1. LLM 决策：该干什么
  │  2. 执行决策（创建任务/等待/停止）
  │  3. 更新 .oc_session.json 的 phase + phase_detail + completed_children
  │
  ▼
.oc_session.json  ←── 接力状态写在这里
  │
  ▼
Layer 1: Collector (no_agent, 30s)
  │  读 kanban.db（四维统计）
  │  读 .oc_session.json（接力状态 + 会话状态）
  │  输出：统一格式纯文本
  │
  ▼
Layer 2: Reporter (LLM cron, 1min)
  │  转发 collector 输出到 Feishu
  │
  ▼
Frank 看到一条统一消息：
  📋 安排5个 | ✅ 跑完3个 | 🔄 在跑2个 | ⏳ 未跑3个
  🔗 接力：派发中 — P0-15 D2 修复 (3/5)
  🕐 OC 会话：oc_20260710 | 已运行 12min | 下一轮：15:00 启动
```

### 3.3 为什么这是最优解

| 维度 | 方案 A（全局心跳） | 方案 B（降级 no_agent） | 方案 C（状态透传） |
|------|:---:|:---:|:---:|
| 满足 Frank 需求 #4（完事即静默） | ❌ 违反 | ✅ | ✅ |
| 不推翻 v3.0 已有设计 | ❌ 推翻 | ⚠️ 部分 | ✅ 扩展 |
| 保留 OC 的 LLM 决策能力 | ✅ | ❌ 废掉 | ✅ |
| 消除重复 kanban 扫描 | ❌ | ✅ | ✅ |
| Frank 看到接力过程 | ⚠️ 间接 | ✅ | ✅ 直接 |
| 改动量 | 大（推翻 v3.0） | 大（重写接力 cron） | **小（session file 加字段 + collector 加一行输出 + OC SOUL.md 加规则）** |

---

## 四、信息密度与频率设计

### 4.1 心跳频率：维持 1 分钟

理由：
- 1 分钟已经在 v3.0 PRD 中确定，Frank 确认过。改为更频繁（如 30s）会产生「刷屏感」，改为更稀疏（如 2min）则信息滞后。
- OC 的接力 tick 间隔通常也在 1-2 分钟级别，1 分钟心跳刚好覆盖 OC 的状态变化。

### 4.2 信息密度：三行制

Frank 要的是「一屏看清」，不是翻页滚动。统一消息格式：

```
📋 安排5个 | ✅ 跑完3个 | 🔄 在跑2个 | ⏳ 未跑3个
🔗 接力：派发中 — P0-15 D2 修复 (3/5)
🕐 OC 会话：oc_20260710 | 已运行 12min | 下一轮：15:00 启动
```

- **第一行**：kanban 四维统计（v3.0 已有，不变）
- **第二行**：接力状态（新增，仅 OC 活跃时显示）
- **第三行**：OC 会话摘要（v3.0 已有，不变）

设计原则：**每条信息都有「下一步是什么」的暗示**。
- 「安排5个 | 未跑3个」→ 暗示还有工作要做
- 「接力：等待中 — 3 个子任务在跑」→ 暗示 OC 没卡住，在等结果
- 「下一轮：15:00 启动」→ 暗示 OC 没死，下一轮已排期

### 4.3 不需要播报的内容

以下内容**不加**到心跳中（噪声 > 信号）：
- ❌ 每个子任务的具体 title 和 assignee → 信息过载，Frank 可以打开 kanban board 看
- ❌ OC 的内部 prompt 或推理过程 → 工程细节，对 Frank 无意义
- ❌ 「一切正常」类废话 → 如果数值没变，心跳本身就已经传达了「一切正常」

---

## 五、Frank 使用场景验证

### 场景 1：Frank 发起一个 OC 任务派发

```
Frank 在飞书发消息：「@OC 把 P0-15 的三个 MAJOR 修了」

OC 启动 → 写 session file (phase=polling)
  → Frank 收到：「📋 安排3个 | 🔗 接力：轮询中 — 扫描任务队列」

OC 扫到 3 个 ready 任务 → phase=dispatching → 创建 3 个子任务
  → Frank 收到：「📋 安排0个 | ✅ 跑完0个 | 🔄 在跑3个 | 🔗 接力：派发中 — P0-15 D2 修复 (3/3)」

子任务在跑 → phase=waiting
  → Frank 收到：「🔄 在跑3个 | 🔗 接力：等待中 — 3 个子任务在跑」

子任务陆续完成 → phase=completed
  → Frank 收到：「✅ 跑完3个 | 🔗 接力：本轮完成 ✅」
  → 然后：「👋 无任务在跑，即将静默」
```

**Frank 从头到尾知道 OC 在干什么，没有黑盒。**

### 场景 2：OC 扫了一圈没发现可做的事

```
OC tick → phase=polling → 没有 ready 任务
  → Frank 收到：「📋 安排0个 | 🔗 接力：轮询中 — 无待处理任务」

OC 判定无事可做 → phase=completed
  → Frank 收到：「🔗 接力：本轮完成 ✅」
  → watchdog 发告别消息后静默
```

**Frank 不会疑惑「OC 是不是卡住了」。**

---

## 六、改动清单

| # | 改动 | 位置 | 工作量 |
|---|------|------|:---:|
| 1 | `.oc_session.json` 增加 `phase` + `phase_detail` 字段 | 架构文档 §5.2 + PRD §2 | 文档更新 |
| 2 | OC SOUL.md 增加规则：「每次 tick 结束后更新 session file 的 phase」 | orchestrator profile | 1 条规则 |
| 3 | `kanban_collector.py` 的 `build_output()` 增加接力状态行 | Layer 1 | ~5 行代码 |
| 4 | collector 测试更新（TC-01 格式验证） | 测试套件 | ~3 个测试 |
| 5 | `read_session_state()` 读取 `phase` 字段 | collector | ~2 行 |

**总工作量估算：0.3 人天**（远低于方案 A 或 B 的重写成本）

---

## 七、产品裁定总结

| 决策点 | 裁定 |
|--------|------|
| 推荐方案 | **方案 C：接力状态透传 + watchdog 统一播报** |
| 方案 A（全局心跳） | ❌ 不推荐 — 违反 Frank 需求 #4 + 推翻 v3.0 设计 |
| 方案 B（降级 no_agent） | ⚠️ 方向对、执行错 — 不应废掉 LLM 决策能力 |
| 心跳频率 | 维持 1 分钟（v3.0 已定） |
| 信息密度 | 三行制：四维统计 + 接力状态 + 会话摘要 |
| 改动范围 | 仅扩展 session file 协议 + collector 加一行输出 |

**一句话：不推翻已有架构，只给 session file 加一个「接力 phase」字段，让 watchdog 替接力 cron 把过程播出来。**

> **移交**：此裁定供架构师（高见远）评估技术可行性、研发（寇豆码）评估实现成本。建议 Frank 一轮确认后直接进入实现。
