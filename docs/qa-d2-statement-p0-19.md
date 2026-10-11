# D2 Roundtable: QA 陈述 — P0-19 接力 cron/Watchdog 合并

> 日期: 2026-07-10 | QA: game-qa | 依据: docs/standards/qa-finding-classification.md v1.0 + config/qa-classification.yaml v1.0.0
>
> 母报告: docs/qa-test-report-p0-19-relay-watchdog-merge.md (t_75adc4a3, 全量测试)

---

## 0. 执行摘要

**全量测试: 162/162 PASS，零失败。发布门禁通过，安全余量充足。**

D1 提出的三项修正建议经实测评定后，**QA 全部确认**：
- R-R3/R-R7 合并（同一根因）→ 1 个 MAJOR
- R-R5 降为 MINOR（绝对路径 6/6 套件可达）

最终门禁: BLOCKER=0, **MAJOR=1** (边界充裕), MINOR=5, 安全=0, 申诉=0 → ✅

---

## 1. 分级确认 — 逐条对照 §1.2 判定公式

### 1.1 MAJOR → 确认维持 1 项（合并后）

| ID | 合并前 | 合并后 | 判定公式 | 实测评据 |
|----|--------|--------|----------|---------|
| **R-R3** | LLM 忘记 relay_update.py | **R-R3/R-R7 合并** | `用户可感知=是 AND 体验严重退化 → MAJOR` | SOUL.md 合规 7/7 PASS + D1 FIX 阶段 -1/0 强制前置 |
| **R-R7** | SOUL.md 行为不一致 | ↑ 合并入 R-R3 | `同上—同根因: LLM 概率性遗忘` | — |

**合并理由**: R-R3 与 R-R7 描述同一风险——LLM 未按 SOUL.md 规则调用 relay_update.py。根因相同（LLM 不可控性），缓释相同（7 阶段模板 + 铁律规则 + 阶段 -1/0），不可分治。D1 product/architect/engineer 三方一致同意合并。

**实测评据**: D1 FIX 后两个 SOUL.md 均在第一个 tick 强制调用 relay_update.py（orchestrator 阶段 -1, game-engine 阶段 0），含 ⚠️ 强制校验 + 铁律 enforcement + 失败重试。TS-R4 SOUL.md 合规 7/7 PASS 证明 prompt 结构正确。但 LLM 行为本质上是概率性的，无法通过静态测试完全证明。

### 1.2 MAJOR → MINOR 降级: R-R5

| ID | 内容 | D1 产品建议 | 实测评据 | 降级确认 |
|----|------|------------|---------|---------|
| **R-R5** | relay_update.py 不在 cron PATH | 降为 MINOR | 所有 6 套件 relay_update.py 绝对路径可达 | ✅ 确认 |

**判定对照**:
- 原始公式: `用户可感知=是 AND 功能阻断=否(有 workaround: 改绝对路径) → MAJOR`
- D1 产品建议: 绝对路径已解决 → MINOR
- 实测: TS-R1~R6 全部 6 套件均通过绝对路径调用 relay_update.py 成功，无任何 PATH 相关失败。

**QA 确认**: R-R5 降为 MINOR。实测证据充分，绝对路径 `RELAY_HELPER` 在所有环境中可达。

### 1.3 MINOR — 维持原级（4 项 + R-R5）

| ID | 风险 | 判定 | 处置 | 依据 |
|----|------|:---:|:---:|------|
| R-R1 | relay/session 并发写冲突 | MINOR | 不修 | 独立文件 + 原子写 → 无半写文件 |
| R-R2 | 读取时正在 rename（瞬态） | MINOR | 不修 | 原子 rename + best-effort = 最多漏 1 tick |
| R-R4 | relay 文件 OC 结束后残留 | MINOR | 不修 | OC SOUL.md 含清理规则 (L302) |
| R-R6 | relay phase 枚举扩展 | MINOR | 不修 | collector 透传，不验证 phase 值 |
| R-R5 | PATH（降级后） | MINOR | 不修 | 绝对路径 6/6 可达 |

**QA 确认**: 所有 MINOR 均为 best-effort 型风险，已有结构性缓释，不阻塞发版。

---

## 2. 分级汇总（D2 修正后）

| 级别 | D1/原始 | D2 QA 确认 | 变化 | 项目 |
|:---:|:---:|:---:|------|------|
| BLOCKER | 0 | **0** | — | — |
| MAJOR | 3 | **1** | -2 | R-R3/R-R7 合并为 1 项 |
| MINOR | 4 | **5** | +1 | +R-R5 降级 |
| SUGGESTION | 0 | 0 | — | — |
| 安全漏洞 | 0 | 0 | — | — |

---

## 3. 处置建议

### 3.1 R-R3/R-R7（MAJOR，合并后）: 验收期观察

**不阻塞发版**，但需验收期监控：

- 观察窗口: 发布后 ≥3 个完整 OC 接力周期
- 监控指标: 每个 tick 有 relay phase 变化，无连续 >2 tick relay 状态冻结
- 升级条件: 连续 >3 周期无 relay 更新 → MAJOR→BLOCKER 升级
- 已有基线: D1 FIX 的 SOUL.md 阶段 -1/0 强制前置 + 铁律 + 失败重试 = 风险已显著降低
- 静态测试 7/7 PASS 证明 prompt 结构正确，唯一剩余风险是 LLM 行为不可控（概率性、无法静态验证）

### 3.2 MINOR (5 项): 不修，已有缓释

全部 5 项 MINOR 均有结构性缓释：
- R-R1: 原子写 + 独立文件
- R-R2: 原子 rename + 下个 tick 自动恢复
- R-R4: OC 结束清理规则
- R-R5: 绝对路径 6/6 套件确认可达
- R-R6: collector 透传，不验证 phase 值

**无需修复，不阻塞发版。**

---

## 4. 发布门禁检查（§10）

```
条件: BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉

D2 QA 确认:
  BLOCKER:      0  ✅
  MAJOR:        1  ✅ (远低于 3 上限)
  安全漏洞:      0  ✅
  未裁定申诉:    0  ✅
```

**门禁: 通过。安全余量充足（MAJOR=1, 上限=3）。**

### 发布建议

**放行。** 建议流程:
1. 发布
2. 验收期观察 R-R3/R-R7 ≥3 个 OC 接力周期
3. 若连续 >3 周期无 relay 更新 → 触发 MAJOR→BLOCKER 升级
4. 3 周期内 relay 更新正常 → MAJOR 闭环

---

## 5. D1 修正建议的实测评据

| D1 修正 | 类型 | 评据 | QA 确认 |
|---------|------|------|:---:|
| R-R3/R-R7 合并 | product 确认 | 同根因(LLM 概率)，缓释相同(阶段 -1/0)，不可分治 | ✅ |
| R-R5 降为 MINOR | product 建议 | TS-R1~R6 全部 6 套件绝对路径 relay_update.py 可达 | ✅ |
| G-T1 staleness guard | D1 发现→已修复 | 11/11 针对性断言 + 31/31 回归 PASS, QA 复测通过 | ✅ 已闭合 |
| R-R3 relay 合规 | D1 发现→已修复 | 两个 SOUL.md 共 12 项 grep 命中 + 7 项 relay_update.py 静态检查 PASS | ✅ 已闭合 |

**D1 两项 FIX 修复均已通过 QA 复测闭合。三项修正建议实测评据充分，QA 全部确认。**

---

## 6. 裁定记录

| 事项 | 裁定方 | 结果 |
|------|--------|------|
| R-R3/R-R7 合并 | D1 product/architect/engineer | 同意合并 |
| R-R5 降 MINOR | D1 product | 同意降级 |
| BLOCKER 暂缓 | 不适用 (无 BLOCKER) | — |

---

## 7. 补充观察（非发现）

- **TC-R4-05**: SOUL.md 使用 RELAY_HELPER 变量而非字面路径 → 功能等效，不影响合规
- **TC-R5-02**: relay 行位于 session 行之后 → 符合 build_output() 实际代码顺序，不影响信息可读性
- **TC-R3-02/03**: collector 对 relay 文件缺失/为空→优雅降级（无 relay 行不崩溃），行为正确

以上三项均为测试方案与实现的细节差异，不影响质量判断，不纳入缺陷统计。

---

## 8. QA 签署

| 字段 | 值 |
|------|-----|
| QA 角色 | game-qa |
| 圆桌阶段 | D2（最终 QA 陈述） |
| 基于测试报告 | docs/qa-test-report-p0-19-relay-watchdog-merge.md |
| 基于 D1 FIX 复测 | docs/qa-reaudits/P0-19-D1-fix-retest-report.md |
| 分级标准 | config/qa-classification.yaml v1.0.0 |
| 判定流程 | 所有发现逐条对照 §1.2 判定公式 |

> **QA 最终陈述**: 发布门禁通过。MAJOR=1（R-R3/R-R7 合并），MINOR=5（含 R-R5 降级），BLOCKER=0，安全=0，申诉=0。D1 三项修正建议全部经实测确认成立。建议放行，验收期观察 R-R3/R-R7 ≥3 个 OC 接力周期。
