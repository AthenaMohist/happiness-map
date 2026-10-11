# QA 复测报告: P0-15 A2 STATE_PREFIXES [FIX]

**任务**: t_7344369f — QA RETEST: P0-15 A2 STATE_PREFIXES [FIX] 专项复测
**复测日期**: 2026-07-09
**QA 执行**: game-qa
**原始发现**: A2-D2-05 FAIL (MAJOR) — 架构发现 A2: STATE_PREFIXES 与 YAML 不同步
**修复任务**: t_9ceb5979 — 添加 WITHDRAWN/DUPLICATE 到 STATE_PREFIXES
**标准依据**: `docs/standards/qa-finding-classification.md` v1.0, YAML `config/qa-classification.yaml` v1.0.0

---

## 1. 复测结论

**PASS** — 修复已验证，原始失败用例现已通过，无回归。

| 指标 | 值 |
|------|-----|
| A2-D2-05（原 FAIL） | **PASS** ✓ |
| A2 全部 11 项测试 | **11 PASS / 0 FAIL** |
| 全量回归 (52 项) | **52 PASS / 0 FAIL / 0 SKIP** |
| 集成测试 (8 项) | **ALL 8 PASS** |
| BLOCKER=0 | ✓ |
| 发布门禁评估 | **PASS** |

---

## 2. 原始发现回顾

**A2-D2-05: STATE_PREFIXES 与 YAML to-states 交叉验证** (原 FAIL → MAJOR)

YAML state_machine.transitions 定义了 11 个唯一目标状态（excl NEW/OPEN）：

```
CONFIRMED, REJECTED, APPEAL, DEFERRED, RESOLVED, CLOSED,
REOPENED, DUPLICATE, WITHDRAWN, DOWNGRADE(legacy), RULING(legacy)
```

原 STATE_PREFIXES（9 个）缺少：
- **WITHDRAWN** — YAML 定义: `{from: OPEN, to: WITHDRAWN, actor: qa, note: "QA 自行撤回"}`
- **DUPLICATE** — YAML 定义: `{from: OPEN, to: DUPLICATE, actor: dev, note: "链接主 bug"}`

判定: MAJOR（§5.3 架构发现 — YAML 数据源与代码硬编码不一致）

---

## 3. 修复验证

### 3.1 STATE_PREFIXES 现状 (11 条目)

```
 0: REJECTED   → ^\\[REJECTED\\]
 1: APPEAL     → ^\\[APPEAL\\]
 2: DOWNGRADE  → ^\\[DOWNGRADE\\]
 3: RULING     → ^\\[RULING\\]
 4: DEFERRED   → ^\\[DEFERRED\\]
 5: CONFIRMED  → ^\\[CONFIRMED\\]
 6: RESOLVED   → ^\\[RESOLVED\\]
 7: CLOSED     → ^\\[CLOSED\\]
 8: REOPENED   → ^\\[REOPENED\\]
 9: DUPLICATE  → ^\\[DUPLICATE\\]    ★ 新增
10: WITHDRAWN  → ^\\[WITHDRAWN\\]    ★ 新增
```

### 3.2 YAML 到 STATE_PREFIXES 同步验证

| YAML to-state | STATE_PREFIXES | 状态 |
|--------------|-----------------|------|
| CONFIRMED    | ✓               | OK  |
| REJECTED     | ✓               | OK  |
| APPEAL       | ✓               | OK  |
| DEFERRED     | ✓               | OK  |
| RESOLVED     | ✓               | OK  |
| CLOSED       | ✓               | OK  |
| REOPENED     | ✓               | OK  |
| DUPLICATE    | ✓               | **FIXED** |
| WITHDRAWN    | ✓               | **FIXED** |

缺失: **NONE** — 所有 YAML to-states (excl NEW/OPEN) 均在 STATE_PREFIXES 中。

额外条目: `DOWNGRADE`, `RULING` — 这两个是代码层面的旧条目，YAML 中不存在。A2-D2-05 测试将其标记为 `[INFO]`（non-fatal），符合设计意图（允许 legacy/future 额外条目）。

### 3.3 测试结果详情

#### A2-D2-05 重跑结果

```
  [INFO] STATE_PREFIXES has extra entries not in YAML: {'RULING', 'DOWNGRADE'}
  ✓ A2-D2-05: STATE_PREFIXES 与 YAML to-states 交叉验证
```

**PASS** — `missing` 集合为空（原 FAIL 原因是 `missing = {DUPLICATE, WITHDRAWN}`）

#### A2 全部 11 项测试

```
  ✓ A2-D2-01: YAML transitions 数量验证 (14 transitions)
  ✓ A2-D2-02: YAML transitions 无重复 from→to 对
  ✓ A2-D2-03: WITHDRAWN 状态在 YAML transitions 中存在
  ✓ A2-D2-04: DUPLICATE 状态在 YAML transitions 中存在
  ✓ A2-D2-05: STATE_PREFIXES 与 YAML to-states 交叉验证
  ✓ A2-D2-06: STATE_PREFIXES 排序确定性 (sorted order)
  ✓ A2-D2-07: 11 个 STATE_PREFIXES 正则均有效
  ✓ A2-D2-08: 11 个 STATE_PREFIXES 正则均匹配对应前缀
  ✓ A2-D2-09: YAML 缺失时的防御行为 (config_loader 错误处理)
  ✓ A2-D2-10: YAML semver 格式校验不崩溃
  ✓ A2-D2-11: 申诉 4 条核心路径在 YAML 中均定义
```

#### 集成测试

```
  ✓ kanban_helpers — VALID_LEVELS from config, 11 state prefixes
ALL 8 TESTS PASSED
```

---

## 4. 判定公式对照

| 步骤 | 判定 | 依据 |
|------|------|------|
| 用户可感知 | ❌（架构内部一致性） | — |
| 安全漏洞 | ❌ | — |
| 数据完整性 | ❌ | — |
| 系统健康度 | ❌ | — |
| → 原始级别 | MAJOR | YAML 与代码不同步，影响正确的状态转换 |

修复后：**不再存在**，STATE_PREFIXES 与 YAML 已同步。

---

## 5. 额外 Notes

- **DOWNGRADE/RULING 是旧条目**: 测试 A2-D2-05 允许 STATE_PREFIXES 有额外条目（标记 `[INFO]`），这两个是 §6 论证流程中的合法状态迁移标签，但当前 YAML state_machine 未包含它们。建议后续评估是否将此差异归档为技术债务（P2）。
- **无回归**: 全量 52 项测试保持 PASS，核心路径（申诉、驳回、分级）未受影响。

---

## 6. 发布门禁

| 条件 | 实际 | 通过 |
|------|------|------|
| BLOCKER=0 | 0 FAIL | ✓ |
| MAJOR≤3 | 0 FAIL | ✓ |
| 安全漏洞=0 | 无 | ✓ |
| 无未裁定的申诉 | N/A | ✓ |

**判定**: 发布门禁通过，可关闭原始 A2 MAJOR 发现。
