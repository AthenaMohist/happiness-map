# D1 产品裁定 — Slice 1 管线数据层 4 项冲突

> 发言人：许清楚（产品负责人） | 日期：2026-07-30
> 依据：PRD v1.0 + 架构设计 v1.0 + QA D1 测试方案 v1.0

---

## 裁定总览

| # | 冲突 | QA 定级 | 产品裁定 | 结果 |
|---|------|:---:|------|:---:|
| D1-F1 | 5 步步名 | BLOCKER | QA 引用的架构版本已过时——当前架构 §6.2 与 PRD 一致 | **以 PRD 为准，架构已修正** |
| D1-F2 | project_config 表 | MAJOR | 接受架构建议：Slice 1 建表。PRD §5.2 §8 需修订 | **采纳架构，修订 PRD** |
| D1-F3 | user_version/verdict 列 | MAJOR | QA 引用的架构版本已过时——当前架构 §1.1 user_version=1 与 PRD 一致 | **以 PRD 为准，架构已修正** |
| D1-F4 | 超时检测实现 | MAJOR | QA 引用的架构版本已过时——当前架构 §3.4 明确做超时检测 | **以 PRD 为准，架构已修正** |

---

## 逐项裁定

### D1-F1：5 步步名（BLOCKER → 裁定为无冲突）

**QA 所述冲突**：PRD 使用 `dev→qa-exec→va→merge→close`，架构使用 `dev→qa-d1→qa-exec→merge→close`

**产品核实**：当前架构文档（v1.0）§0.1 组件范围表、§6.2 `STEP_NAMES` 常量均采用与 PRD 完全一致的 5 步顺序：
```
STEP_NAMES = ["dev", "qa-exec", "va", "merge", "close"]
```

qa-d1 被明确归入 Slice 2（Arch §2.3、§7），va 明确在 Slice 1 实现（Arch §0.1、§7）。

**裁定**：D1-F1 不存在冲突。QA 测试方案引用的可能为架构早期草稿。当前 PRD 与架构在步骤名上完全一致。PRD 无需修订。

---

### D1-F2：project_config 表（MAJOR → 采纳架构，修订 PRD）

**冲突本质**：

| 维度 | PRD §5.2 / §8 Sl1-02 | 架构 §0.2 |
|------|-----|------|
| project_config 表 | Slice 3 再建 | Slice 1 就建 |

**产品分析**：

架构的论证有理：

1. **成本对**：建表 55 行（constants 20 + config 30 + init 15），未来零改造成本；defer 到 Slice 2 则需 migration + 全组件回归 ≈ 20 行改造 + 风险
2. **架构整洁**：集中式 config.py 优于散落硬编码
3. **YAGNI 边界的合理越界**：project_config 在 Slice 1 确实没有业务逻辑用途（备份操作在 Slice 2），但它的存在不会给 Slice 1 增加任何复杂度——只是两张表而非一张表，初始化时多写 4 行 key-value

PRD 的原始反对理由：「project_type 字段在 Slice 1 无用」——这是正确的，但「无用」和「有害」不同。建一个不参与业务逻辑的表，代价接近于零。

**产品附加约束**：接受架构建议的同时，加一条产品红线：

> init_project.py 是可选的。如果未运行 init_project.py（project_config 表为空或不存在），系统应以硬编码默认值降级运行（project_type='system_mechanism', project_name='devPPL'），不得因缺少 project_config 导致管线启动失败。这是为 Slice 1 的开发/测试环境降低摩擦。

**需要执行的修订**：PRD §5.2 将 project_config 从「Slice 3 才做」移至「已在 Slice 1 实现」；PRD §8 Sl1-02 更新描述。

---

### D1-F3：user_version / verdict 预置列（MAJOR → 裁定为无冲突）

**QA 所述冲突**：PRD 用 user_version=1 无 verdict 列，架构用 user_version=2 预置三列

**产品核实**：当前架构文档 §1.1 明确：
```sql
PRAGMA user_version = 1;
```
§1.3 小节标题即为「为什么 user_version = 1」，正文明确说明：「verdict/verdict_detail/contract_check_passed 在 Slice 1 中不参与任何逻辑，不应存在于 v1 表中」。

**裁定**：D1-F3 不存在冲突。当前架构与 PRD 在 user_version 和 verdict 列问题上完全一致。PRD 无需修订。

---

### D1-F4：超时检测实现（MAJOR → 裁定为无冲突）

**QA 所述冲突**：PRD AC-4 要求超时检测，架构 §3.4 写「Slice 1 不做超时检测」

**产品核实**：当前架构文档 §3.4 明确：
> 超时检测 | Slice 1 做简化版：检测→failed→停止 | 不涉及 retry/block/rollback——那是 Slice 2 branches engine 的职责

架构 §2.1 合约 JSONL 每行含 `timeout_min` 字段，§3.4 给出了具体实现方式（`finished_at - started_at > timeout_min`）。

**裁定**：D1-F4 不存在冲突。当前架构与 PRD AC-4 在超时检测上完全一致。PRD 无需修订。

---

## PRD 修订清单

需修订 `docs/prd/slice1-pipeline-prd.md`：

1. **§5.2「Slice 3 才做」表**：将 project_config 行移至 §0 Slice 分拆描述，标注「已在 Slice 1 实现」
2. **§8 Sl1-02**：更新为 `pipeline_state.db v1 含 pipeline_steps + project_config 两张表，不含 verdict 三列`

修订后 PRD 版本标记为 v1.1。

---

## 对其他角色的影响

| 角色 | 影响 |
|------|------|
| **Architect（高见远）** | D1-F1/F3/F4 已自行修正，无需动作。D1-F2 架构方案被产品接受，按 §1 实现即可，注意产品附加约束（init_project.py 可选） |
| **Engineer（寇豆码）** | 步骤名 = PRD 5 步；schema = user_version=1 + pipeline_steps + project_config（两张表）；超时检测 = 做 |
| **QA** | 测试方案 D1-F1/F3/F4 的冲突声明可撤回。D1-F2 按「两张表」schema 验证。测试方案建议修订后进入 Round 1 执行 |

---

## QA 测试方案需修订的位置

`docs/qa/slice1-pipeline-test-plan.md` 中：
- D1 前置发现表：D1-F1/F3/F4 标记为「已裁定，冲突消除」
- TC-01 预期结果：验证 project_config 表存在（若 init_project.py 已运行）或确认降级运行（若未运行）
- §8 D1 审定 Checklist：划掉已裁定项

---

> 产品发言完毕。PRD v1.1 修订随附。下一步：QA 更新测试方案 → 进入 Round 1 测试执行。
