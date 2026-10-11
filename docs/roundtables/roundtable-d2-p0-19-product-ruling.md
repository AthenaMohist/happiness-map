# D2 Roundtable 产品裁定 — P0-19 接力 cron/Watchdog 合并测试报告

> 角色：许清楚（产品负责人） | 日期：2026-07-10
> 议题：D2 产品评审判定 — QA 最终报告分级与处置
> 依据：QA D2 陈述 (docs/qa-d2-statement-p0-19.md) + QA 测试报告 (docs/qa-test-report-p0-19-relay-watchdog-merge.md)
> 标准：config/qa-classification.yaml v1.0.0 + §1.2 判定公式
> 背景：方案 C 裁定 (docs/roundtables/roundtable-b-cron-watchdog-merge-product-ruling.md)

---

## 执行摘要

**发布门禁通过。分级合理，处置正确。放行。**

- BLOCKER=0 ✅ | MAJOR=1 ✅ | MINOR=5 ✅ | 安全=0 ✅ | 申诉=0 ✅
- MAJOR (R-R3/R-R7): D1 修复已就位 → 验收期观察 ≥3 OC 周期，不阻塞发版
- MINOR (5 项): 全部已有结构性缓释 → P5 不修
- 修复策略：D1 prompt-level fix 已足够 → 不升级为全功能改造

---

## 议题 1: 分级合理性 — 1 MAJOR + 5 MINOR 是否合理？

### 裁定：合理。维持 QA 分级。

### 1.1 R-R3/R-R7 合并为 1 个 MAJOR — 合理

| 判定要素 | 分析 |
|---------|------|
| **根因** | 同一风险——LLM 概率性遗忘 relay_update.py 调用 |
| **用户可感知** | 是 — Frank 看不到接力状态播报行 |
| **功能阻断** | 否 — 核心 kanban 播报功能不受影响，仅 relay 信息缺失 |
| **有 workaround** | 是 — 可手动运行 relay_update.py |
| **体验退化程度** | 严重 — OC 接力过程对 Frank 变为黑盒，违反方案 C 核心设计目标 |

**判定对照** (yaml §1.2):
```
用户可感知=是 AND (功能阻断但有 workaround OR 体验严重退化) → MAJOR ✅
```

**合并理由成立**：
- R-R3（LLM 忘记 relay）和 R-R7（SOUL.md ≠ LLM 行为）描述同一风险：LLM 未按 SOUL.md 规则调用 relay_update.py
- 缓释相同（阶段 -1/0 强制前置 + 铁律规则 + 失败重试）
- 不可分治——修了 R-R3 就是修了 R-R7，反过来也一样
- D1 product/architect/engineer 三方一致同意合并

**为什么不是 BLOCKER？**
- 不满足 BLOCKER 判定：`用户可感知 AND 功能阻断 AND 无 workaround`
- 核心功能（kanban 播报）正常运作，relay 信息缺失是体验退化而非功能阻断
- 不涉及安全、数据一致性、OOM/crash、S 级数据
- LLM 概率性行为无法彻底消除——这是系统固有特性，非可修复 bug

### 1.2 R-R5 降为 MINOR — 合理

**实测评据充分**：TS-R1~R6 全部 6 套件通过绝对路径调用 relay_update.py 成功，无任何 PATH 相关失败。

**判定对照**:
- 原判定: `用户可感知=是 AND 功能阻断=否(有 workaround: 绝对路径) → MAJOR`
- 产品建议: 绝对路径已解决实际风险 → `用户可感知=否`（在绝对路径下用户不会遇到）
- 实测: 6/6 套件绝对路径可达

**降级确认**：R-R5 降为 MINOR。实测证据充分。✅

### 1.3 5 个 MINOR — 分级合理

全部 5 项 MINOR 均为 best-effort 型风险，判定正确：

| ID | 风险 | 判定 | 结构性缓释 |
|----|------|:---:|----------|
| R-R1 | 并发写冲突 | MINOR | 独立文件 + 原子写 → 无半写文件 |
| R-R2 | 读取时瞬态 rename | MINOR | 原子 rename + 下个 tick 自动恢复 |
| R-R4 | OC 结束 relay 残留 | MINOR | OC SOUL.md 含清理规则 |
| R-R5 | PATH（降级后） | MINOR | 绝对路径 6/6 可达 |
| R-R6 | phase 枚举扩展 | MINOR | collector 透传，不验证 |

所有 MINOR 满足 `用户可感知=是 AND 不影响核心任务完成 → MINOR`。

---

## 议题 2: 处置决策

### 2.1 R-R3/R-R7 (MAJOR): 验收期观察，不阻塞发版

**D1 修复已就位且通过 QA 复测**：
- 两个 SOUL.md 阶段 -1/0 强制前置：12 项 grep 检查全部命中
- relay_update.py 7 项静态检查通过
- G-T1 staleness guard 11/11 断言 + 31/31 回归 = 42/42 全绿
- D1 FIX 的两个 MAJOR 均已修复闭合

**为什么仍维持 MAJOR 而非闭环？**
- LLM 行为本质上是概率性的——静态测试证明 prompt 正确，但不能证明 LLM 100% 遵循
- 这是系统固有特性（LLM 不可控性），不是可彻底修复的 bug
- 维持 MAJOR = 诚实标注已知风险，验收期观察 = 数据驱动的风险验证

**处置决策**：
```
✅ 不阻塞发版
✅ 验收期观察 ≥3 个 OC 接力周期
✅ 监控指标: 每个 tick 有 relay phase 变化，无连续 >2 tick relay 状态冻结
⚠️ 升级条件: 连续 >3 周期无 relay 更新 → MAJOR→BLOCKER
```

**优先级：P2 监控（非 P0 修复）**。D1 修复已是最优成本路径。

### 2.2 5 个 MINOR: P5 不修，纳入技术债追踪

**全部 5 项 → P5 won't fix（当前版本）**

理由：
- 每项均有结构性缓释，无用户可感知的实际问题
- 修复单项成本（测试 + 代码 + review）远超收益（消除一个已缓释的理论风险）
- 如任何一项在验收期观察中升级（出现实际影响），再根据实际数据评估修复

**不纳入待办（backlog）**——理由同上。如果未来某个 MINOR 的实际影响出现，届时创建新 issue。在当前阶段，5 项 MINOR 的处置 = 文档记录 + 归档。

---

## 议题 3: 修复难易程度 — R-R3 是 bug fix 还是功能升级？

### 环境确认

当前 D1 修复 = **prompt-level fix（简化管线）**：
- orchestrator SOUL.md: 阶段 -1 强制前置 → relay_update.py
- game-engine SOUL.md: 阶段 0 强制前置 → relay_update.py
- ⚠️ 强制校验 + 铁律 + 失败重试
- 修改量：每个 SOUL.md ~3-5 行 prompt 规则
- 零代码改动

### 裁定：维持 D1 prompt-level fix，不升级为全功能改造

**对比分析**：

| 维度 | D1 fix（prompt-level） | Full feature（code-level enforcement） |
|------|------------------------|---------------------------------------|
| 修改范围 | ~6 行 prompt 规则 | 预/后置钩子机制 + OC 循环重构 + 幂等保证 |
| 改动量 | 0 代码，仅 SOUL.md | ~100-200 行 Python + SOUL.md 重写 |
| 测试成本 | 静态检查（已完成 7/7 PASS） | 全套单元 + 集成 + 回归测试 |
| 工期 | 已完成 | 0.5-1 人天 |
| 能否彻底消除风险 | **不能**——LLM 概率性行为无法通过代码消除 | **不能**——代码级钩子仍依赖 LLM 调用 |
| ROI | 高（低成本 + 实质性降低风险） | 极低（高成本 + 无法消除同一根本风险） |

**核心理由**：

1. **两种方案都无法消除同一根本风险——LLM 概率性行为。**
   - prompt-level fix: LLM 可能"忘记"执行阶段 -1 规则
   - code-level fix: 如果钩子机制也依赖 LLM 调用（OC 本身是 LLM agent），LLM 仍然可能"忘记"调用钩子
   - 完全消除此风险需要将 OC 从 LLM agent 改为确定性状态机——这直接推翻方案 C 的核心设计（保留 LLM 决策能力）

2. **超额投资陷阱。** 当收益不随投入线性增长时（r=-0.01% → -0.005%），0.5 人天的投入换不来 0.5 人天的用户价值。更好的做法是把这 0.5 人天花在下一个确有用户价值的功能上。

3. **验收期观察是正确的一步。** 如果 3 周期后 relay 更新正常 → MAJOR 闭环，投入 0。如果异常触发升级 → 带着真实数据重新评估，此时额外投入有据可依。

**结论**：
```
R-R3 = bug fix（简化管线）✅ — 不升级为功能改造
D1 prompt-level fix 已足够 — 风险已从"LLM 可能忘记"降为"LLM 极不可能忘记"
验收期观察 3 周期 → 闭环 or 重新评估（带数据）
```

---

## 发布门禁确认

对照 yaml §10:
```
BLOCKER=0      ✅
MAJOR≤3        ✅ (MAJOR=1, 远低于 3 上限)
安全漏洞=0      ✅
无未裁定申诉    ✅
```

**门禁：通过。发布建议：放行。**

### 发布后行动

| 步骤 | 动作 | 时限 |
|------|------|------|
| 1 | 发布 | 即日 |
| 2 | 验收期监控 R-R3/R-R7 | ≥3 个 OC 接力周期 |
| 3a | 若 3 周期内 relay 更新正常 → MAJOR 闭环 | 3 周期后 |
| 3b | 若连续 >3 周期无 relay 更新 → 升级 BLOCKER | 触发时 |
| 4 | 5 个 MINOR → P5 归档，不纳入 backlog | — |

---

## 裁定记录

| 事项 | 裁定方 | 结果 |
|------|--------|------|
| R-R3/R-R7 分级合理性 | 产品 | ✅ 合理 — 1 MAJOR |
| R-R5 降级确认 | 产品 | ✅ 确认 — MINOR |
| 5 MINOR 分级 | 产品 | ✅ 合理 — MINOR |
| R-R3/R-R7 处置 | 产品 | 验收期观察（不阻塞发版），P2 |
| 5 MINOR 处置 | 产品 | P5 won't fix |
| 修复策略 | 产品 | Bug fix（prompt-level），不升级功能改造 |
| 发布门禁 | 产品 | ✅ 放行 |

---

> **一句话裁定**：分级合理、处置正确、门禁通过、放行。D1 的 prompt-level fix 已是最优成本路径——验收期观察 3 个周期，数据说话。如果 LLM 做到了，MAJOR 闭环；如果做不到，带着真实失败数据回来，届时全功能投入有据可依。
>
> **移交**：此裁定交 game-engine 执行发布、game-qa 执行验收期监控。
