# R3 独立卷 — Product 视角：新管线目标系统工作流全貌

> 角色：许清楚（产品负责人） | 日期：2026-07-30 | 类型：R3 独立卷
> 规则：不参考其他角色答卷，独立输出，暴露差异供 OC 最终对比。

---

## 0. 一句话定位

Frank 说"做 X"之后，他应该只需要关心三件事：**X 有没有开始做、做到哪了、做完没有**。其他一切——谁做什么、什么顺序、产什么物、验证没验证——系统应该自己搞定。这份报告描述的就是"系统自己搞定"的完整工作流。

---

## 1. 一个完整的管线周期：从 Frank 说"做 X"到交付验证

### 1.1 Frank 触发

```
Frank 在飞书对 OC 说："做 P0-21，修复 InfoManager 的 URL 消失问题"
```

这是整个管线的起点。Frank 不需要填表单、不需要写 issue、不需要记编号。他只需要说出来。

### 1.2 阶段 0：OC 理解 + 规范生成（~5 分钟）

| 步骤 | 谁做 | 做什么 | 产出 |
|------|------|--------|------|
| 0a | **OC** | 理解 Frank 意图，查 session_search 确认无历史矛盾 | 上下文确认消息回给 Frank |
| 0b | **OC** | 调用 `openspec propose "修复 InfoManager URL 消失"` | `openspec/changes/p0-21-url-fix/spec.md` |
| 0c | **OC** | `openspec validate --strict --json` 验证 spec 通过 | JSON 验证结果 |
| 0d | **OC** | 查 SOUL.md + `.hermes.md` 确认 spec 不与铁律/项目规范冲突 | 冲突报告（如有）或通过 |
| 0e | **OC** | 创建 kanban 卡片，assignee=game-engine，body 含 spec 引用 + 优先级 | kanban task `t_xxx` |

**Frank 看到什么**：OC 回复"理解了。已生成规范 `p0-21-url-fix`，验证通过。准备启动研发。" — 一句话，不展开细节。

### 1.3 阶段 1：研发执行（dev） — game-engine agent

| 步骤 | 谁做 | 做什么 | 数据流 |
|------|------|--------|--------|
| 1a | **autopilot.sh** (cron 2min) | 检测到 kanban `t_xxx` 状态 = ready → 分配给 engine | 读 kanban 状态 |
| 1b | **engine** | 读 kanban body → 读 `openspec/changes/p0-21-url-fix/spec.md` → 理解需求 | kanban → OpenSpec spec |
| 1c | **engine** | 写代码 + 单元测试 → PR 提交 | `feat/p0-21-url-fix` 分支 |
| 1d | **engine** | `pipeline/close.sh t_xxx` (S6 简易版) → 更新 kanban 为 done | kanban status = done |
| 1e | **checkpoint** (state.py) | 检测 engine done → 写 `pipeline_state.db`：step=dev, status=done, artifacts=[分支名, 改动的文件列表] | SQLite INSERT |
| 1f | **state.py 合约校验** | 入口校验：dev produces 是否满足合约要求（分支存在？文件改动非空？） | 合约通过/失败 → kanban comment |

**Frank 看到什么**：autopilot 在 kanban comment 写 `[AUTOPILOT] dev 阶段完成，产物：feat/p0-21-url-fix, 3 文件改动`。Frank 不需要介入。

### 1.4 阶段 2：QA 测试 — game-qa agent

| 步骤 | 谁做 | 做什么 | 数据流 |
|------|------|--------|--------|
| 2a | **autopilot.sh** | dev done + 合约通过 → 自动创建 QA 卡片，assignee=game-qa | kanban 新建子卡片 |
| 2b | **state.py** | 入口校验：dev 的 artifacts 是否满足 QA 合约的 requires（`["branch", "code_changes"]`） | 读 pipeline_state.db |
| 2c | **game-qa** | 写测试方案 → 执行测试 → 产生 QA report | `docs/qa-reports/p0-21-qa-report.md` |
| 2d | **QA report 分级判定** | 按 `.hermes.md`（项目规范）§1.2 五步判定公式，检查 BLOCKER/MAJOR | QA report 内含分级 |
| 2e | **闸门：D 类 roundtable** | QA 发现 BLOCKER → autopilot 停止，写 kanban comment `[GATE: roundtable]` | 人工介入 |

**Frank 看到什么**：如果 QA 通过 → autopilot 写 `[AUTOPILOT] QA 通过，0 BLOCKER，进入 VA`。如果 QA 发现 BLOCKER → autopilot 停，OC 通知 Frank"P0-21 QA 发现 BLOCKER，需要 roundtable 裁定"。

### 1.5 阶段 3：VA 验证 — verifier agent

| 步骤 | 谁做 | 做什么 | 数据流 |
|------|------|--------|--------|
| 3a | **autopilot.sh** | QA done + 0 BLOCKER → 创建 VA 卡片 | kanban 新建 |
| 3b | **verifier** | 读取 engine 的 claims → 逐条证伪/证实 | VA report |
| 3c | **state.py** | va done → 写入 pipeline_state.db | step=va, status=done |

### 1.6 阶段 4：合并 + 闭环 — OC

| 步骤 | 谁做 | 做什么 | 数据流 |
|------|------|--------|--------|
| 4a | **autopilot.sh** | va done → 通知 OC"可以 merge" | kanban comment |
| 4b | **OC** | merge PR, 执行 `close.sh t_xxx` 完整 S6 | 强制闭环 |
| 4c | **close.sh S6** | kanban done → GAI 更新 → manifest 更新 → 备份推送 → 飞书通知 | 6 步不可裁剪 |
| 4d | **pipeline 归档** | `openspec archive p0-21-url-fix` | spec 移至 archive/ 防止腐化 |

**Frank 看到什么**：飞书收到"P0-21 闭环完成。测试通过，VA 验证通过，已合并 main，GAI 已更新。"

### 1.7 总结：数据流全景

```
Frank 说"做 X"
    │
    ▼
[OC] 理解 → OpenSpec propose → validate → 创建 kanban
    │                                    ┌─────────────┐
    ▼                                    │  .hermes.md │ ← 项目规范（QA标准等）
[autopilot.sh] cron 检测 → 分发任务       │  SOUL.md    │ ← 铁律（不冲突检查）
    │                                    └─────────────┘
    ├─→ [engine] 研发 → close.sh(S6轻量)
    │       │
    │       ▼
    │   [pipeline_state.db] ← checkpoint 写入
    │       │
    │       ▼
    │   [state.py] 合约校验（入口检查 produces）
    │       │
    ├─→ [game-qa] QA → D类闸门(如需)
    │       │
    ├─→ [verifier] VA 验证
    │       │
    └─→ [OC] merge + close.sh(S6完整) + openspec archive
            │
            ▼
        Frank 收到飞书通知 "完成"
```

---

## 2. 新组件嵌入位置与角色

### 2.1 OpenSpec

| 维度 | 说明 |
|------|------|
| **嵌入位置** | 阶段 0：OC 理解 Frank 意图之后、创建 kanban 卡片之前 |
| **做什么** | 将 Frank 的自然语言需求转为结构化 spec（markdown） |
| **谁调用** | OC（不是 autopilot、不是 engine） |
| **产出** | `openspec/changes/{id}/spec.md` — 可被 engine/QA/VA 读取 |
| **与 SOUL.md 关系** | spec 不能违反 SOUL.md 铁律。OC 在 propose 后须检查冲突。如有冲突 → 修改 spec 或标记铁律例外（需 Frank 确认） |
| **关闭时机** | 任务闭环后 `openspec archive`，防止 spec 腐化 |

**对 Frank 的价值**：他不信任管线的原因之一是"管线正确性依赖 OC 记忆"。OpenSpec 把"要做什么"固化为可审查、可 diff、可验证的 markdown 文件。Frank 可以在任何时候打开 `spec.md` 看"这个任务到底要做什么"——不依赖 OC 是否记得。

### 2.2 checkpoint（pipeline_state.db）

| 维度 | 说明 |
|------|------|
| **嵌入位置** | 每个步骤完成后，由 state.py 自动写入 |
| **做什么** | 记录 task_id → step_name → status → artifacts → 时间戳 |
| **谁写** | autopilot.sh 通过 state.py 写入 |
| **谁读** | autopilot（判断下一步）、resume.sh（跨会话续接）、dashboard.py（可视化） |
| **存储位置** | `/workspace/devPPL/pipeline_state.db`（项目级，不跨 workspace 共享） |
| **数据格式** | SQLite WAL，单表 pipeline_steps，append-only |

**对 Frank 的价值**：出问题时不用"从零排查"。checkpoint 精确记录每一步的状态和产物，故障定位从"翻聊天记录"变成"查 pipeline_state.db"——一行 SQL。

### 2.3 autopilot.sh

| 维度 | 说明 |
|------|------|
| **嵌入位置** | 贯穿整个管线生命周期，cron 每 2 分钟轮询 |
| **做什么** | 检测 kanban 状态变化 → 触发下一步骤 → 调用 state.py 写 checkpoint → 调用 state.py 做合约校验 |
| **谁运行** | cron job，不需要 Frank 或 OC 手动触发 |
| **决策权限** | 只能做"确定性转移"：上一步 done + 合约通过 → 创建下一步卡片。遇到闸门（D 类 roundtable、merge 确认）→ 停止 |
| **什么时候不自动** | D 类 roundtable 需要人工裁定、merge 前需要 OC 确认、发现合约违规 → 停止并通知 |

**对 Frank 的价值**：管线不再需要 OC 手动 sleep-poll。autopilot 替代了 OC 的"等 30 秒 → 查状态 → 推下一步"这种 token 浪费行为。

### 2.4 条件路由

| 维度 | 说明 |
|------|------|
| **嵌入位置** | autopilot.sh 检测到步骤完成、决定下一步时 |
| **做什么** | 根据上一步的输出决定下一步走向（如 QA 通过 → VA；QA 发现 MAJOR → 研发返修） |
| **配置格式** | YAML（复用 config_loader.py 模式） |
| **适用场景** | 标准路径之外的分支：QA 返修、超时告警、并行 fan-out 条件 |

**对 Frank 的价值**：管线不是一条僵硬的直线。实际开发中 QA 发现问题要返修、超时要升级——条件路由让管线能处理这些"合理意外"，而不是卡死。

### 2.5 可视化面板

| 维度 | 说明 |
|------|------|
| **嵌入位置** | 独立于管线执行之外，是"观察窗口" |
| **做什么** | 从 pipeline_state.db + kanban 读取数据，展示：当前所有任务在哪一步、耗时、阻塞原因 |
| **实现优先级** | 先 CLI（`pipeline/dashboard.py`），后飞书消息格式，最后 web 面板 |
| **数据依赖** | P0-1(state.py) + P0-2(checkpoint) 就绪后才能展示有意义的数据 |

**对 Frank 的价值**：Frank 说"做到哪了"——以前要问 OC，OC 查 kanban + 翻聊天记录。以后 Frank 可以自己看面板：一行显示所有活跃任务的状态。**管线从"黑盒"变成"透明盒"。**

---

## 3. DPL-011 跨会话记忆 — .hermes.md 怎么解决

### 3.1 正确理解（Frank 纠偏后）

DPL-011 要解决的问题不是"让 Frank 读"。Frank 在飞书里是连续对话——他自己不会失忆。

**问题是 Hermes 的架构问题**：Frank 和 OC 在飞书聊天，但 Hermes 内部可能被分割成多个 session。Session 之间上下文不互通——OC 切会话后"失忆"。Hermes 有一个 Project Context 系统（`.hermes.md`）可以从工作目录自动加载、跨会话保留——但我们一直没用起来。

### 3.2 .hermes.md 的双重角色

| 角色 | 当前使用 | 目标使用 |
|------|---------|---------|
| **项目规范** | ✅ 已用：QA 分级标准、申诉机制 | 维持，不动 |
| **跨会话上下文** | ❌ 未用 | **新增**：管线状态摘要、活跃任务列表、最近关键决策 |

### 3.3 .hermes.md 应该写什么（跨会话上下文部分）

新 OC 会话启动时，.hermes.md 自动加载。它应该包含：

```markdown
## 当前上下文（自动生成，cron 每 30 分钟刷新）

### 活跃任务
- t_abc123: P0-21 URL 修复 → [dev:done → qa:running] 开始于 14:30
- t_def456: P1-07 schema 审计 → [dev:running] 开始于 13:00

### 最近关键决策（近 7 天）
- 2026-07-30: OpenSpec P0 引入 — R2 roundtable 三方共识
- 2026-07-29: checkpoint 先于 autopilot — Engineer/Architect 共识

### 最近纠正（近 7 天）
- Frank 纠正：DPL-011 不是"人类可读记忆"，是 Hermes session 架构问题
- Frank 纠正：先看目标系统全貌，再看 MVP 方案
```

**关键设计**：
- 这部分由 cron job 自动生成，**OC 不能手动编辑**（防止 OC 写错导致后续会话被误导）
- 生成频率：每 30 分钟，与 autopilot cron 复用 context_from 链
- 写入位置：`.hermes.md` 的 `## 当前上下文` section —— 与已有的"项目规范" section 隔离
- 字符预算：项目规范 ~1400 字符，剩余 ~18600 字符给上下文（20,000 上限完全够用）

### 3.4 新 session OC 启动时自动获得什么

```
1. .hermes.md 自动加载（Hermes 框架行为，不需要 OC 主动调用）
   → 包含：项目规范 + 活跃任务 + 最近决策 + 最近纠正

2. SOUL.md 自动加载（铁律 + 身份契约）
   → 包含：铁律 6（新会话前三轮必须查历史）

3. OC 主动执行铁律 6：
   → session_search() 回顾最近 3 天关键决策
   → 检查 memory 中的活跃事实
   → 向 Frank 确认上下文
```

**三层防护**：`.hermes.md`（自动加载，零延迟） → SOUL.md 铁律 6（OC 行为规则） → OC 主动 session_search（深度上下文）。即使前两层失效，第三层也能兜底。

### 3.5 什么不应该写进 .hermes.md

- 临时调试信息（token 浪费）
- 中间推理过程（单次会话价值，跨会话无意义）
- 已被 Frank 否定的方案详细描述（只保留"某方案被否决"的结论）
- 超过 7 天未更新的"活跃任务"（自动过期清除）

---

## 4. 组织 / 执行 / 验证三层模型

### 4.1 组织层：谁编排流程

| 角色 | 职责 | 工具 |
|------|------|------|
| **OC** | 接收 Frank 指令 → 理解 → OpenSpec → 创建 kanban | OpenSpec CLI, hermes kanban |
| **autopilot.sh** | 检测状态变更 → 创建下一步卡片 → 调用合约校验 → 写 checkpoint | cron, kanban CLI, state.py |
| **cron 调度** | 定时触发 autopilot + context 刷新 + watchdog | hermes cron |

**边界**：OC 负责"启动"（把 Frank 的话变成 kanban 任务），autopilot 负责"推进"（任务之间的状态转移）。两者不重叠：OC 不需要手动 sleep-poll，autopilot 不负责理解 Frank 意图。

### 4.2 执行层：谁干活

| 角色 | 职责 | 触发方式 |
|------|------|---------|
| **game-engine** | 写代码、修复 bug、提交 PR | kanban dispatcher 自动分配 |
| **game-qa** | 写测试方案、执行测试、产出 QA report | kanban dispatcher 自动分配 |
| **game-architect** | 架构评审、技术方案设计 | kanban dispatcher 自动分配 |

**边界**：执行 agent 不关心"谁派的任务"和"做完后谁来接"。它们只读 kanban body 中的 spec 引用，完成任务后标 done。剩下的由 autopilot 接管。

### 4.3 验证层：谁检查结果

| 验证类型 | 谁做 | 检查什么 | 工具 |
|---------|------|---------|------|
| **合约校验** | state.py（确定性脚本） | 检查 produces 是否满足 requires（文件存在、产物非空） | Python 脚本，零 LLM |
| **QA 分级** | game-qa | 按 `.hermes.md` 标准检查 BLOCKER/MAJOR | QA report |
| **VA 证伪** | verifier | 读取 engine 的 claims，逐条证伪/证实 | VA report |
| **闭环完整性** | close.sh（脚本） | kanban done → GAI → manifest → 备份 → 通知不缺步 | shell 脚本 |
| **Spec 合规** | openspec validate | 检查 spec.md 格式完整性 | openspec CLI |

**边界**：验证分层做——脚本做确定性验证（不需要 LLM），agent 做需要判断的验证（QA 分级、VA 证伪）。脚本验证失败 = 硬阻塞（不进入下一步）。agent 验证 = 产生报告 → 条件路由决定下一步。

### 4.4 三层之间的数据契约

```
组织层产出 → kanban task (id + body + spec ref)
执行层消费 → 读 kanban body → 理解 spec → 执行
执行层产出 → pipeline_state.db (step status + artifacts)
验证层消费 → 读 pipeline_state.db → 读 spec → 验证
验证层产出 → kanban comment (pass/fail + 证据)
组织层消费 → autopilot 读 comment → 决定下一步
```

**这个闭环不需要 Frank 在中间传话。** 数据通过 kanban + pipeline_state.db + .hermes.md 传递，不依赖 OC 的短期记忆。

---

## 5. 功能间冲突分析

### 5.1 OpenSpec specs  vs  SOUL.md 铁律冲突

| 场景 | 示例 | 如何处理 |
|------|------|---------|
| OpenSpec 要求 LLM 自动决定需求范围 | spec 写"agent 自行判断优先级" | ❌ 违规。SOUL.md 铁律"不代替 Frank 做决定"。**产品裁定：spec 必须显式标注"需 Frank 确认"的决策点** |
| OpenSpec spec 和 SOUL.md 格式冲突 | spec 用 JSON，SOUL.md 用 markdown | 不冲突。spec 是任务级，SOUL.md 是身份级。两者格式独立 |
| 冲突不可调和 | spec 必须做的事恰好是 SOUL.md 禁止的 | **升级为 Frank 裁定**。OC 标记冲突 → kanban comment → 等待 Frank 回复。不自行裁决 |

**产品立场**：SOUL.md 铁律优先级 > OpenSpec spec。铁律是经过验证的协作边界，spec 是单次任务的执行细节。如果 spec 需要突破铁律 → 必须 Frank 签字。

### 5.2 checkpoint（pipeline_state.db） vs  kanban.db 数据不一致

| 场景 | 原因 | 如何处理 |
|------|------|---------|
| kanban 标 done 但 pipeline_state.db 无记录 | autopilot 漏写或写失败 | **kanban 是权威源。** pipeline_state.db 是镜像。不一致时以 kanban 为准，autopilot 补写 checkpoint |
| pipeline_state.db 显示 running 但 kanban 标 done | 手动改 kanban 状态，autopilot 未感知 | autopilot 检测到不一致 → 写 kanban comment `[AUTOPILOT] 状态不一致，以 kanban done 为准，已补 checkpoint` |
| 两者都显示不同状态 | 并发写入 | SQLite WAL + busy_timeout 串行化写操作，不会出现幻读 |

**产品立场**：kanban 是单一事实来源（single source of truth），pipeline_state.db 是加速查询的镜像。不一致时的恢复方向：以 kanban 为准 → 重建 pipeline_state.db。这个原则写入 `.hermes.md` 项目规范。

### 5.3 autopilot 自动决策  vs  roundtable 人工裁定

| 场景 | 谁优先 | 规则 |
|------|--------|------|
| autopilot 想推进到下一步 | 正常流转 | autopilot 自动推进 |
| autopilot 遇到 D 类闸门 | roundtable | autopilot 停止，写 kanban comment + 通知 |
| roundtable 裁定后 autopilot 如何继续 | roundtable 裁定写入 kanban → autopilot 读取后继续 | autopilot 检测到闸门解除（kanban unblock）→ 恢复推进 |
| roundtable 裁定和 autopilot 预期矛盾 | roundtable 优先 | autopilot 以 kanban 上最新的 roundtable 裁定为准，覆盖自己的默认路由 |

**产品立场**：autopilot 只能做"无争议的确定性转移"（dev done + 合约通过 → qa）。任何需要人类判断的节点（D 类 roundtable、merge 确认、产品方向变更）→ autopilot 停止。**autopilot 的决策权是被明确授予的，不是默认拥有的。**

---

## 6. 从 Frank 视角看

### 6.1 Frank 需要关注的

| 时机 | 关注什么 | 信息来源 |
|------|---------|---------|
| 说"做 X"之后 | OC 是否理解了（spec.md 是否正确反映了意图） | OC 的确认消息 + spec.md（如果 Frank 想看） |
| 执行中 | 进度（做到哪了、谁在做） | 可视化面板 / autopilot kanban comment |
| QA 发现 BLOCKER | 什么被阻塞了、需要什么裁定 | OC 通知 + roundtable 记录 |
| 完成后 | 是否真的完成了（不是"标了 done 但漏了 GAI"） | 飞书通知（close.sh 6 步全部通过才触发） |
| 出问题时 | 断在哪里、谁的责任、怎么恢复 | pipeline_state.db + kanban 历史 |

### 6.2 Frank 不需要关注的

| 原来的痛点 | 新管线如何消除 |
|-----------|--------------|
| "OC 还在不在跑？" | autopilot.sh 替代 OC 的 sleep-poll，不需要 Frank 担心 OC 是否在线 |
| "做到哪一步了？问 OC" | 可视化面板一行显示，不需要通过 OC 中转 |
| "上次说好的别用方案 A，OC 又忘了" | `.hermes.md` 持久化"最近纠正"，新 session OC 自动加载 |
| "GAI 更新了吗？manifest 更新了吗？" | close.sh 强制 S6 闭环，少一步都不发"完成"通知 |
| "spec 规范写了一堆，没人验证对不对" | openspec validate --strict + state.py 合约校验，双重确定性验证 |

### 6.3 Frank 什么时机介入

| 介入时机 | 触发条件 | Frank 做什么 |
|---------|---------|------------|
| **方向确认** | OC 理解 Frank 意图后有歧义 | 确认或纠正 spec.md 中的理解 |
| **闸门裁定** | D 类 roundtable（BLOCKER、产品方向变更、铁律例外） | 做决策，写 kanban comment |
| **异常升级** | autopilot 3 次重试失败 / 超时 > 30 分钟 / 合约违规无法自动修复 | 判断是修管线 bug 还是手动推进 |
| **版本发布前** | close.sh 全绿 → Frank 最终确认（可选） | "确认发布"或"暂缓" |

### 6.4 Frank 什么时候不介入

管线正常运行时不介入。Frank 说"做 X"之后，如果一切按合约走（dev → qa pass → va pass → merge → close），Frank 唯一收到的就是飞书通知"P0-XX 闭环完成"。

**产品设计原则**：管线的默认行为是"不打扰 Frank"。只有三种情况会打扰：需要裁定、出错了、做完了。其他一切——进度更新、状态转移、合约校验——都在 Frank 视线之外自动运行。

---

## 7. 总结：管线承诺

从 Product 视角，新管线系统交付后，我们向 Frank 做出以下承诺：

1. **启动零摩擦**：Frank 说"做 X" → OC 自动生成 spec + 创建 kanban。Frank 不需要填表。
2. **推进不依赖记忆**：autopilot 替代 OC 的 sleep-poll。状态通过 pipeline_state.db 传递，不依赖任何 agent 的短期记忆。
3. **跨会话不遗忘**：`.hermes.md`（项目上下文）+ SOUL.md 铁律 6（行为规则）+ session_search（深度查询）三层防护，OC 切换会话后自动恢复上下文。
4. **验证不靠信任**：state.py 合约校验（确定性脚本）+ QA 分级（`.hermes.md` 标准）+ VA 证伪 + close.sh S6 闭环——四层验证，每层独立、可审计。
5. **完成是真的完成**：close.sh 通过 6 步验证才发送"完成"通知。不存在"标了 done 但 GAI 没更新"的半成品状态。
6. **Frank 只在三种情况下被打扰**：需要裁定、出错了、做完了。

---

> **产品发言完毕。这是独立卷，基于 Product（许清楚）的视角对目标系统工作流的完整理解。交由 OC 与 Engineer、Architect 的独立卷对比。**
