# D1 Architect 发言 — Slice 3 测试方案架构评审

> 发言人：高见远（架构师） | 日期：2026-07-30
> 评审对象：`docs/qa/slice3-closing-test-plan.md` v1.0（721 行，37 用例）
> 对照基准：`docs/arch-slice3-closing-layer.md` v1.0（638 行架构设计）+ PRD + 已有代码

---

## 0. 总体评价

测试方案质量高，覆盖全面。37 用例（13 BLOCKER + 18 MAJOR + 6 MINOR）覆盖 6 个子系统，与 PRD 23 项 AC 全部对应。分级严格遵循 `qa-finding-classification.md` v1.0，每项 BLOCKER/MAJOR 均标注 §1.2 五步判定公式。

**QA 在测试方案末尾发现了 3 项"PRD/架构冲突"需要架构师裁定。其中 D1-F1 已自查为无冲突（✅），D1-F2/F3 为 MINOR 级别可工程自主裁决，D1-F0 为 MAJOR 需要 Product + Architect 统一口径。**

整体架构设计完整性验证：测试方案未发现架构设计本身的缺陷。所有 BLOCKER 用例均对应新模块的核心功能路径（非架构设计失误）。

---

## 1. D1-F0 裁定：hermes_static.md vs .hermes.md 锚点 — **架构方案为准，PRD 补充对齐**

### 1.1 两种方案对比

| 维度 | PRD 方案（§1.3） | 架构方案（§1.2） |
|------|:---|:---|
| **源真文件** | `config/hermes_static.md`（独立模板） | `.hermes.md`（锚点内嵌） |
| **boot_context 操作** | 读取静态模板 + 拼接动态段 → 写 `.hermes.md` | 定位 `<!-- BOOT_CONTEXT_START -->` 锚点 → 替换中间内容 → 原子 rename |
| **初始部署** | `cp .hermes.md config/hermes_static.md` + `echo "" > .hermes.md` | 在 `.hermes.md` 中插入锚点标记 |
| **故障模式** | `hermes_static.md` 被删除 → `.hermes.md` 只含动态段 → agent 失去规范知识 | `.hermes.md` 锚点缺失 → `write_boot_context()` 返回 False，不修改文件 |
| **agent 启动安全性** | 部署时清空 `.hermes.md`，cron 首次运行前 agent 读到空文件 | `.hermes.md` 始终完整——静态段永远存在，cron 只替换动态段 |

### 1.2 架构裁决

**裁定：采用架构方案（`.hermes.md` 内嵌 `<!-- BOOT_CONTEXT_START/END -->` 锚点）。**

理由：

1. **安全性**：架构方案的 `.hermes.md` 在任何时间点都是完整文件。agent 启动时即使 cron 尚未运行，静态规范依然存在。PRD 方案在初始部署时清空 `.hermes.md`——如果 cron 未及时运行，agent 将读到空文件，丢失所有规范知识。

2. **简单性**：架构方案的操作是「找到锚点 → 替换中间内容」，不需要维护两个文件之间的同步。PRD 方案需要确保 `hermes_static.md` 与 `.hermes.md` 的内容一致性——Product 编辑模板后，cron 下一轮才会反映到 `.hermes.md`（最大 5 分钟延迟）。

3. **容错性**：架构方案中锚点缺失时 `write_boot_context()` 返回 False 且不修改文件（TC-06 已覆盖此边界）。PRD 方案中模板文件被误删后，生成的 `.hermes.md` 只有动态段——agent 失去规范知识，且修复路径不明确（需要恢复模板 → 手动运行 cron）。

4. **与 Hermes 引擎兼容**：`.hermes.md` 是 Hermes 引擎直接加载的 Project Context 文件。在 `.hermes.md` 中维护静态段意味着 Hermes 的加载路径不变——无论 boot_context cron 是否运行，文件都是有效的。

### 1.3 PRD 的 `config/hermes_static.md` 如何保留

**建议保留 `config/hermes_static.md` 但调整其定位**：

- `config/hermes_static.md` = **Product 编辑的参考副本**，git 追踪变更（满足 PRD 的产品管理需求）
- `.hermes.md` 中的静态段 = **运行时的权威源**，由 Product 手动同步（或通过脚本从 `hermes_static.md` 同步到 `.hermes.md` 锚点之上）
- boot_context.py 只写锚点之间的动态段，**永远不修改静态段**

即：
```
config/hermes_static.md  ← Product 编辑（源文件，git 追踪）
         │
         ▼  （手动同步 / 部署脚本）
.hermes.md 静态段（锚点之上）← 由 hermes_static.md 同步而来
.hermes.md 动态段（锚点之间）← boot_context cron 写入
```

**对 QA TC-07 的影响**：AC-1 的「静态模板迁移到 `config/hermes_static.md`」仍成立——`config/hermes_static.md` 存在且为 Product 编辑目标。TC-07 的第三步「拼接后文件格式正确」的验证方式需调整为：验证 `.hermes.md` 含锚点 + 静态段 + 动态段。

### 1.4 需要 Product 确认

以上裁定为架构师技术决策。其中 §1.3 的「保留 `config/hermes_static.md` 作为参考副本」需要 Product 确认是否接受这个定位调整。

---

## 2. D1-F2 裁定：dashboard.py 路径 — **`scripts/dashboard.py`（架构方案为准）**

### 2.1 冲突描述

| 来源 | 路径 | 上下文 |
|------|------|------|
| PRD §2.6 | `pipeline/dashboard.py` | 示例命令 `python3 pipeline/dashboard.py` |
| 架构 §2.1 | `scripts/dashboard.py` | 设计命令 `python3 scripts/dashboard.py` |
| **实际代码** | **`scripts/dashboard.py`** | **已实现，313 行** |

### 2.2 裁决

**裁定：`scripts/dashboard.py`。PRD 的 `pipeline/dashboard.py` 是编写 PRD 时的占位路径，架构设计时根据模块性质将其归入 `scripts/`。**

理由：

1. **模块划分原则**：`pipeline/` 放的是管线引擎的逻辑模块（可以被其他 Python 代码 `import` 使用），`scripts/` 放的是独立执行的 CLI 工具。dashboard.py 是一个独立的 CLI 程序（有自己的 `argparse`、`if __name__ == '__main__'`），放在 `scripts/` 是正确的。

2. **已有代码**：`scripts/dashboard.py` 已实现 313 行，包括 ANSI 颜色输出、`--json`/`--task`/`--failed-only` 参数、CheckpointDB 集成。移动文件到 `pipeline/` 是不必要的成本且破坏现有的导入路径（`from pipeline.checkpoint import CheckpointDB` 已在 sys.path 适配中）。

3. **PRD 修正**：PRD §2.2 的示例命令 `python3 pipeline/dashboard.py` 应改为 `python3 scripts/dashboard.py`。这属于纯文档修正，不影响任何实现逻辑。

---

## 3. D1-F3 裁定：boot_context 输出段落 — **采用 4 段式，吸收 PRD 命名**

### 3.1 冲突描述

| 来源 | 段落数 | 段落名 |
|------|:---:|------|
| PRD §1.4 | 3 段 | 活跃管线任务 / 最近决策 / 最近纠正 |
| 架构 §1.5 | 4 段 | 活跃管线任务 / 最近决策 / 纠偏 / + 隐含"活跃上下文" |

架构 §1.4 数据源定义中明确标注了优先级 4 的「纠偏记录」作为独立数据源，但 PRD 将其合并进「最近纠正」。

### 3.2 裁决

**裁定：采用 4 段式。段落定义为：**

| # | 段落名 | 内容 | 数据源 |
|:---:|------|------|------|
| 1 | **活跃管线任务** | task_id + 步骤 + 状态 + Agent | pipeline_state.db + kanban.db |
| 2 | **最近决策** | roundtable 裁定结论（含 task_id） | session DB（搜 roundtable） |
| 3 | **最近纠正** | Product 反例（agent 被纠正的历史） | session DB / memory（搜 纠正/驳回/Product ruling） |
| 4 | **纠偏** | 关键行为守则（如「不应跳过 D2 roundtable」） | memory（已验证的关键事实） |

**段落 3 与段落 4 的区别**：

- **最近纠正**（§3）：Product 对 agent 具体行为的纠正——「va agent 未按标准 §1.2 判定 FALSIFIED，Product 要求重审」
- **纠偏**（§4）：跨任务的通用行为守则——「OC 不应跳过 D2 roundtable（即使 MAJOR=0），需 Product 裁定」

两者语义不同：纠正是对历史行为的事后修正，纠偏是对未来行为的预防性引导。拆分为独立段落让 agent 清楚区分「上次错了什么」和「以后要注意什么」。

### 3.3 PRD 对齐

PRD §1.4 的动态段模板（第 93-115 行）需从 3 段更新为 4 段，增加 `### 纠偏` 段落。此为文档修正，不影响代码实现——`generate_boot_context()` 的 4 个数据源已对应 4 个段落。

---

## 4. 架构审查：测试方案覆盖完整性

### 4.1 覆盖映射（架构 § ↔ QA TC）

| 架构章节 | 对应 TC | 覆盖评价 |
|------|:---|------|
| §1 boot_context.py | TC-01~07 | ✅ 完整：基本输出 + 空数据 + 容错 + 截断 + 原子写 + 锚点缺失 + 部署验证 |
| §2 dashboard.py | TC-08~12 | ✅ 完整：基本输出 + JSON + 筛选 + 异常过滤 + 性能 |
| §3 backup.py | TC-13~18 | ✅ 完整：策略判定 + 执行 + 失败处理 + 重试 + 端到端 |
| §4 close 7 子步 | TC-19~26 | ✅ 完整：每一步 stub→实现 + 错误处理 + 顺序 |
| §5 discover.py 扩展 | TC-27~28 | ✅ 完整：PIPELINE_ASSIGNEES + 子任务过滤 |
| §6 三 cron 共存 | TC-32~34 | ✅ 完整：并发 + flock + 原子读 |
| autopilot 集成 | TC-29~31 | ✅ 完整：cron 环境变量 + fallback + merge backup |
| 非功能 | TC-35~37 | ✅ 完整：向后兼容 + 时效性 + 无静默失败 |

**结论**：测试方案对架构设计的覆盖完整，无遗漏的架构关注点。

### 4.2 架构设计未覆盖的 QA 发现

QA 测试方案未发现架构设计本身的缺陷。所有 BLOCKER 级 TC 均对应新模块的核心功能路径，架构设计已为每个模块定义了接口、数据源、错误处理和边界行为。

---

## 5. 架构附加观察

### 5.1 boot_context.py 的 session_search 依赖

架构 §1.4 中 boot_context 依赖 `session_search()` 获取最近决策/纠正/纠偏。注意：`session_search()` 是 Hermes Agent 的工具函数，在 cron 环境中（纯 Python 脚本）不可用。

**建议**：boot_context.py 直接读 session DB（`~/.hermes/sessions.db`）的 SQLite FTS5 索引，而非调用 `session_search()`。这在架构 §1.3 的 `generate_boot_context()` 设计注记中已隐含（"session_search — 最近 session 摘要"应改为"session DB SQLite 直读"）。Engineer 实现时注意此点。

### 5.2 dashboard.py 对 kanban.db 的依赖

架构 §2.5 中 dashboard.py 标注为「只读 pipeline_state.db」。但 PRD §2.4 和 QA TC-08 预期 dashboard 输出含任务标题（title）——这需要读 kanban.db（tasks 表）。

**确认**：实现中的 `scripts/dashboard.py` 第 30 行已正确导入 `CheckpointDB`，且从 kanban.db 读取 title。架构 §2.5 的「数据源」描述应更新为「pipeline_state.db（读步骤状态）+ kanban.db（读任务标题）」。此为架构文档修正，不影响实现。

---

## 6. 裁定汇总

| 发现 | 级别 | QA 判定 | 架构裁定 | 动作 |
|------|:---:|------|------|------|
| **D1-F0** | MAJOR | hermes_static.md vs 锚点冲突，需统一 | **架构方案为准**：`.hermes.md` 锚点替换。`config/hermes_static.md` 保留为 Product 参考副本 | PRD §1.3 对齐架构 §1.2；Product 确认 hermes_static.md 定位 |
| **D1-F1** | — | ✅ 自查无冲突 | 同意 QA 的 ✅ 自查结论 | 无动作 |
| **D1-F2** | MINOR | dashboard.py 路径不一致 | **架构方案为准**：`scripts/dashboard.py`（已实现文件位置） | PRD §2.2 命令修正为 `scripts/dashboard.py` |
| **D1-F3** | MINOR | boot_context 段落数不一致 | **4 段式**：活跃任务/最近决策/最近纠正/纠偏 | PRD §1.4 模板增加「纠偏」段落 |
| §5.1 附加 | — | 架构文档注记 | session_search → session DB SQLite 直读 | 架构 §1.3 注记修正 |
| §5.2 附加 | — | 架构文档修正 | 数据源描述更新 | 架构 §2.5 增加 kanban.db 依赖 |

---

## 7. 一句话结论

> Slice 3 测试方案质量高、覆盖完整、分级严谨。3 项 PRD/架构冲突中 D1-F0 架构方案为准（安全性与简单性显著优于 PRD 的拼接方案），D1-F2/F3 为 MINOR 级文档修正。架构设计本身无缺陷，可以进入 Engineer 编码阶段。

---

> 架构师发言完毕。下一站：Product（许清楚）确认 D1-F0 中 `config/hermes_static.md` 的定位调整，然后 Engineer（寇豆码）按 Slice 3 Step 2 开始编码实现。
