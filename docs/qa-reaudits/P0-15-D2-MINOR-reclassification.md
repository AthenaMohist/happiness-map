# P0-15 D2: MINOR 发现 QA 分级陈述（A3/A4/A5）

> 版本：v1.0 | 状态：Final
> 编制日期：2026-07-10
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 架构依据：`docs/arch-p0-15-appeal-mechanism.md` v1.0
> 来源任务：D2 roundtable (t_34dadb21) — P0-15 架构发现 MINOR 项分级审查
> 上游依赖：架构审查 (t_34c5a7a0)

---

## 执行摘要

对 P0-15 架构审查中标记为 MINOR 的 3 项发现（A3/A4/A5），逐项按标准 §1.2 判定公式重新分级。**结论**：3 项分级确认正确，均为 MINOR，不阻塞发布。

| 发现 ID | 发现 | 原级别 | 重分级 | 判定路径 |
|---------|------|:---:|:---:|------|
| **A3** | reinstated 后原始卡片未自动关闭 | MINOR | **MINOR** ✓ | user_visible=YES, no_block, workaround=YES → MINOR |
| **A4** | assignee 硬编码（脚本中写死角色名） | MINOR | **MINOR** ✓ | user_visible=NO → boundary case, system_health_risk → MINOR |
| **A5** | 申诉日志无结构化格式 | MINOR | **MINOR** ✓ | user_visible=NO → boundary case, maintainability → MINOR |

**发布门禁影响**：零。3 项均为 MINOR，不触发 BLOCKER 或 MAJOR 门禁。已在架构文档中记录，计划 P0-16 排期。

---

## 1. A3: reinstated 后原始卡片未自动关闭

### 1.1 发现描述

**位置**：`scripts/product_rule.py` L68-L97（reinstated 分支）

**现象**：产品裁定 `--verdict reinstated` 后，脚本在原始卡片上发布 `[RULING] reinstated` comment，并创建新 kanban 卡片（assignee=game-engine），但**原始卡片未被标记为 done/closed**，停留在看板上显示为未完成状态。

**代码证据**（`product_rule.py` L91-L97）：
```python
new_card_id = create_task(
    new_card_title, new_card_body,
    assignee="game-engine",        # ← 也是 A4 的硬编码
    priority="1",
)
print(f"✓ 裁定: 恢复为 {new_level} → {args.task_id}")
print(f"  新 kanban 卡片: {new_card_id}")
# ← 此处缺少原始卡片的关闭操作
```

**当前行为**：
- 原始卡片 kanban status 不变（保持 running/ready）
- `get_current_qa_state()` 扫描到 `[RULING] reinstated` → 返回 "RULING"
- appeal_tracker 的 `classify_task()` 依赖 `task["status"] == "done"`，原始卡片不会进入 "rejected_accepted" 分类
- 用户在看板上看到两个"未完成"卡片（原始 + 新建），产生混淆

### 1.2 判定公式对照（按标准 §1.2）

```
前置检查：
  └─ 安全漏洞？ → 否（不属 OWASP 任何类别，无认证绕过/数据泄露/注入风险）

正式判定：
  Step 1: user_visible？ → YES
           理由：看板用户可感知 — 原始卡片显示为未完成状态，与「已裁定恢复」的语义矛盾。
           满足「数据完整性受影响」的扩展定义 — 看板状态与实际流程状态不一致。

  Step 2: 功能阻断？ → NO
           理由：申诉流程核心路径（REJECTED → APPEAL → RULING reinstated → 新卡片）不受影响。
           新卡片正常创建并可以被研发认领处理。原始卡片的不关闭不影响后续操作。

  Step 3: 是否有 workaround？ → YES
           理由：看板维护者可以手动将原始卡片标记为 done（一条 CLI 命令）。
           成本极低，无需代码变更。

  Step 4: 数据一致性风险？
           S 级数据（资金/资产/订单）：不涉及。
           A 级数据（用户基础信息/权限）：不涉及。原始卡片与 kanban 状态不完全一致，
           但不会导致数据丢失、错误或权限问题。
           → 不加权。

  Step 5: 性能退化？ → 不涉及。

最终判定路径：
  user_visible=YES → 不是 SUGGESTION
  → 功能阻断=NO → 不是 BLOCKER
  → 不是 MAJOR 条件（非功能阻断、无安全风险、无 PII）
  → MINOR ✓
```

### 1.3 分级示例对照（按标准 §5）

| 示例 | 场景 | 对比 |
|------|------|------|
| §5 #12 | 按钮颜色与设计稿差 2px（用户能注意到）→ **MINOR** | 类比：看板状态不一致 ≈ UI 显示微妙偏差，用户注意到但不影响操作 |
| §5 #15 | 变量命名应改为 userCount → **SUGGESTION** | 不类比：A3 用户可感知，而 SUGGESTION 要求用户不可感知 |
| §5 #17 | 列表页偶发白屏，刷新后恢复 → **MAJOR** | 不类比：A3 无功能阻断，workaround（手动关闭）成本极低 |

### 1.4 SLA 对照（按标准 §8）

| SLA 项 | MINOR 要求 | 实际 |
|--------|:---:|------|
| 研发响应 | 2 工作日 | ✅ 架构审查中已确认 |
| 研发定位 | 不限 | ✅ 已明确定位（product_rule.py L68-L97，缺少 3 行关闭逻辑） |
| 修复方案 | 不限 | ✅ 建议方案已归档（见架构文档 §5.5） |
| QA 回归范围 | 修复模块单元测试 + 1 个关键场景 | 预估 5 项测试（见 D1 test plan A3 section） |

### 1.5 建议修复方案（P0-16 排期）

在 `product_rule.py` 的 reinstated 分支中，创建新卡片后追加一行：

```python
# 关闭原始卡片（标记为 done）
comment(args.task_id,
    f"[CLOSED] 产品裁定 reinstated {new_level} → 新卡片 {new_card_id}\n"
    f"原始 issue 已通过产品裁定恢复，后续跟踪在新卡片上进行。")
```

**迁移成本**：3 行代码。回归风险：LOW。

---

## 2. A4: assignee 硬编码（脚本中写死角色名）

### 2.1 发现描述

**位置**：`scripts/product_rule.py` L93

**现象**：`product_rule.py --verdict reinstated` 创建新卡片时，`assignee="game-engine"` 是硬编码常量。如果团队结构变更（如 "game-engine" 重命名为 "game-dev"），所有通过产品裁定恢复的卡片将分配给不存在的 profile，看板无法正常分发任务。

**代码证据**（`product_rule.py` L91-L95）：
```python
new_card_id = create_task(
    new_card_title, new_card_body,
    assignee="game-engine",    # ← 硬编码，应从 YAML 配置读取
    priority="1",
)
```

**YAML 现状**：`config/qa-classification.yaml` 的 `roles` section 已定义角色映射，但 `assignee_mapping` section 尚未建立（架构文档 §4.4 建议新增）。

**对比**：同一项目中，`VALID_LEVELS` 已从 YAML 读取（`kanban_helpers.py` L26-L38），`EVIDENCE_TYPES` 已从 YAML 读取（`appeal.py` L37），`appeal_threshold` 已从 YAML 读取（`appeal_tracker.py` L24）。assignee 是少数遗留硬编码之一。

### 2.2 判定公式对照（按标准 §1.2）

```
前置检查：
  └─ 安全漏洞？ → 否（非 OWASP 类别，不涉及访问控制/加密/注入）

正式判定：
  Step 1: user_visible？ → NO
           理由：终端看板用户看不到 `assignee="game-engine"` 这个字符串。
           用户只看到「新卡片已创建，分配给 game-engine」。
           如果 game-engine 被重命名导致分配失败，用户会感知到，但这是硬编码的后果，
           而非硬编码本身。按标准 §1.3 原则：「用户可感知」指当前时刻用户能否注意到，
           不包括「未来可能发生」的场景。

           ⚠ 边界情况：如果 assignee 被重命名，将导致新卡片无法正常分发，
           属于系统健康度退化（kanban 流程中断）。
           按标准 §1.3 扩展定义：「系统健康度退化（错误率上升、MTTR 恶化）」→ 
           虽然当前未发生，但风险明确且修复成本极低，保守取 MINOR。

  Step 2: 功能阻断？ → NO（当前正常运行）
  Step 3: 是否有 workaround？ → N/A（当前无问题需绕过）
  Step 4: 数据一致性风险？ → 不涉及资金/用户数据
  Step 5: 性能退化？ → 不涉及

最终判定路径：
  user_visible=NO →
  不是 SUGGESTION（因为有系统健康度风险 — 重命名后流程中断）
  → 不满足 MAJOR（非安全、非功能阻断、非性能退化）
  → MINOR ✓
```

### 2.3 分级示例对照（按标准 §5）

| 示例 | 场景 | 对比 |
|------|------|------|
| §5 #15 | 变量命名应改为 userCount → **SUGGESTION** | 部分类比：纯代码层面改进。区别：A4 有运维风险（重命名后中断），SUGGESTION 无风险 |
| §5 #16 | 日志持续报 ERROR 但功能正常 → 非关键路径 **MINOR** | 类类比：当前功能正常但有潜在风险信号 |
| §5 #12 | 按钮颜色偏差 2px → **MINOR** | 类比：问题小、影响小、易修复 |

### 2.4 SLA 对照（按标准 §8）

| SLA 项 | MINOR 要求 | 实际 |
|--------|:---:|------|
| 研发响应 | 2 工作日 | ✅ 架构审查中已确认 |
| 研发定位 | 不限 | ✅ 已明确定位（product_rule.py L93，1 行改动） |
| 修复方案 | 不限 | ✅ 建议方案已归档 |
| QA 回归范围 | 单元测试 + 1 关键场景 | 预估 5 项测试（见 D1 test plan A4 section） |

### 2.5 建议修复方案（P0-16 排期）

**第一步**：在 `config/qa-classification.yaml` 中新增 `assignee` section：

```yaml
roles:
  product: ["game-product"]
  qa: ["game-qa"]
  dev: ["game-engine"]

# 新增：默认 assignee 映射
assignee_mapping:
  dev_default: "game-engine"    # 产品裁定恢复后的默认研发 assignee
```

**第二步**：在 `config_loader.py` 中新增访问器：

```python
def get_default_dev_assignee() -> str:
    """返回产品裁定恢复后的默认研发 assignee。"""
    return _get_config().get("assignee_mapping", {}).get("dev_default", "game-engine")
```

**第三步**：修改 `product_rule.py` L93：

```python
# Before:
assignee="game-engine",

# After:
from lib.config_loader import get_default_dev_assignee
assignee=get_default_dev_assignee(),
```

**迁移成本**：约 10 行（YAML 3 行 + config_loader 5 行 + product_rule 2 行）。回归风险：LOW。

---

## 3. A5: 申诉日志无结构化格式

### 3.1 发现描述

**位置**：
- `scripts/appeal.py` L78-L93（申诉 comment body）
- `scripts/product_rule.py` L56-L65 / L70-L79（裁定 comment body）
- `scripts/downgrade_notify.py`（降级通知 comment body）
- `scripts/appeal_tracker.py` L27-L69（`classify_task()` 解析器）

**现象**：所有 comment 采用自由格式 Markdown，关键字段（issue、level、timestamp、evidence_type）分散在粗体标记中：

```markdown
[APPEAL] QA 发起申诉 — 产品（许清楚）请裁定

**Issue**: some-task-title
**当前级别**: MAJOR
**证据类型**: 复现证据
**时间**: 2026-07-10T12:00:00Z

**新证据**:
具体内容...
```

`appeal_tracker.py` 的 `classify_task()` 仅通过 `body.startswith("[PREFIX]")` 进行粗粒度状态分类，无法提取结构化字段（如 level、timestamp、evidence_type）。这意味着：
- 统计申诉按证据类型分布 → 不可行（需 NLP）
- 按级别统计申诉率 → 不可行（`get_current_qa_level()` 可用，但不来自同一 comment）
- 追踪平均申诉响应时间 → 不可行（时间戳在 Markdown 散文中）

### 3.2 判定公式对照（按标准 §1.2）

```
前置检查：
  └─ 安全漏洞？ → 否

正式判定：
  Step 1: user_visible？ → NO
           理由：终端看板用户看到的是 comment 的人类可读文本，
           不关心底层是 Markdown 还是 JSON。appeal_tracker 用户（QA/架构）
           看到的是汇总统计，而非原始日志格式。

           ⚠ 边界情况：非结构化日志导致数据质量下降 —
           统计准确性依赖文本解析规则（startswith），未来扩展易出错。
           属于可观测性范畴的维护性问题。保守取 MINOR。

  Step 2: 功能阻断？ → NO
           appeal_tracker 当前功能正常（分类正确），仅缺乏扩展深度。

  Step 3: 是否有 workaround？ → YES
           可通过人工解析 comment（当前已有 appeal_tracker 文本分类）。

  Step 4: 数据一致性风险？ → 不涉及
  Step 5: 性能退化？ → 不涉及

最终判定路径：
  user_visible=NO →
  不是 SUGGESTION（维护性风险明确，未来扩展成本递增）
  → 不满足 MAJOR（非安全、非功能阻断、非性能退化）
  → MINOR ✓
```

### 3.3 分级示例对照（按标准 §5）

| 示例 | 场景 | 对比 |
|------|------|------|
| §5 #16 | 日志持续报 ERROR 但功能正常 → 非关键路径 **MINOR** | 类类比：当前功能正常，但日志/数据质量有改善空间 |
| §5 #15 | 变量命名应改为 userCount → **SUGGESTION** | 区别：A5 影响可观测性/自动化能力，非纯粹命名偏好 |
| §5 #13 | 后端 500 + 前端友好 fallback → 视数据影响 | 不类比：A5 不涉及用户数据 |

### 3.4 SLA 对照（按标准 §8）

| SLA 项 | MINOR 要求 | 实际 |
|--------|:---:|------|
| 研发响应 | 2 工作日 | ✅ 架构审查中已确认 |
| 研发定位 | 不限 | ✅ 已明确定位（appeal.py L78 / product_rule.py L56-L79 / appeal_tracker.py L27-L69） |
| 修复方案 | 不限 | ✅ 见下节，渐进迁移策略 |
| QA 回归范围 | 单元测试 + 1 关键场景 | D1 test plan 已规划 9 项测试 |

### 3.5 建议修复方案（P0-16 排期）

采用**渐进迁移策略**——既保持向后兼容，又新增结构化数据：

```markdown
[APPEAL] QA 发起申诉 — 产品（许清楚）请裁定
<!-- metadata: {"type":"appeal","level":"MAJOR","evidence_type":"repro","timestamp":"2026-07-10T12:00:00Z"} -->

**Issue**: some-task-title
**当前级别**: MAJOR
...
```

新方案和旧方案并存：
1. `body.startswith("[PREFIX]")` 向后兼容（现有 appeal_tracker 不破坏）
2. `<!-- metadata: {...} -->` HTML 注释对 Markdown 渲染无影响
3. appeal_tracker 新增 `extract_metadata(body)` 尝试解析 JSON，fallback 到 prefix 匹配

**迁移成本**：
- `appeal.py` L78：追加 1 行 metadata comment
- `product_rule.py` L56/L70：追加 1 行 metadata comment
- `downgrade_notify.py`：追加 1 行 metadata comment
- `appeal_tracker.py`：新增 `extract_metadata()` 函数（约 15 行）
- 回归风险：MEDIUM — `classify_task()` 需同时支持新旧两种格式

---

## 4. 综合评估

### 4.1 发布门禁

按标准 §10 公式：`BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉`

| 门禁项 | 阈值 | 实测 | 判定 |
|--------|:---:|:---:|:---:|
| BLOCKER | = 0 | **0** | ✅ |
| MAJOR | ≤ 3 | **0**（3 项均为 MINOR） | ✅ |
| 安全漏洞 | = 0 | **0** | ✅ |
| 未裁定申诉 | = 0 | **0** | ✅ |

**发布门禁：PASS ✅** — 3 项 MINOR 不阻塞任何发布阶段。

### 4.2 修复优先级建议

| 优先级 | 发现 | 理由 | 修复成本 |
|:---:|------|------|:---:|
| **1** | A3 reinstated 关闭 | 用户可感知的看板状态不一致 | ~3 lines |
| **2** | A4 assignee 配置化 | 运维风险明确（重命名后中断），修复成本极低 | ~10 lines |
| **3** | A5 结构化日志 | 维护性改善，成本中等（需改 4 个脚本） | ~25 lines |

建议在 P0-16 中一次性全部修复（总成本 < 40 行，回归范围可控）。

### 4.3 风险提示

| 风险 | 说明 |
|------|------|
| **A4 阻塞风险** | 如果 game-engine 在 P0-16 之前被重命名，A4 将从 MINOR 升级为 MAJOR（功能阻断，影响产品裁定流程） |
| **A3 统计偏差** | appeal_tracker 的 "rejected_accepted" 计数可能偏低（原始卡片因未关闭而不被计入），但不影响申诉率的分子（appealed 计数依赖 [APPEAL] comment，不依赖卡片 status） |

---

## 5. 判定公式完整对照（按标准 §1.2 逐项）

| 发现 | 安全漏洞? | user_visible? | 功能阻断? | workaround? | 数据风险? | 性能? | **最终** |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **A3** | NO | YES | NO | YES（手动关闭） | NO | — | **MINOR** |
| **A4** | NO | NO* | NO | N/A | NO | — | **MINOR** |
| **A5** | NO | NO* | NO | YES（文本解析） | NO | — | **MINOR** |

> `NO*` = 边界情况。严格按公式可评 SUGGESTION，但有系统健康度/可观测性风险，保守取 MINOR（符合 §1.3 原则：「无法判断级别时默认取高级别」）。

---

## 附录 A: 文件清单

| 文件 | 说明 |
|------|------|
| `docs/qa-reaudits/P0-15-D2-MINOR-reclassification.md` | 本文件 — QA 分级陈述 |
| `docs/arch-p0-15-appeal-mechanism.md` | 架构审查报告 |
| `docs/qa-reaudits/P0-15-D1-test-plan.md` | D1 测试方案（含 A3/A4/A5 测试用例） |
| `docs/qa-reaudits/P0-15-D2-qa-report.md` | D2 测试执行报告 |
| `scripts/product_rule.py` | A3 + A4 原始位置 |
| `scripts/appeal.py` | A5 原始位置 |
| `scripts/appeal_tracker.py` | A5 解析器位置 |

## 附录 B: 论证流程状态

按标准 §6 论证流程：

| 步骤 | A3 | A4 | A5 |
|------|:---:|:---:|:---:|
| 1. QA 发现并标注级别 | ✅ MINOR | ✅ MINOR | ✅ MINOR |
| 2. 研发评估 | 待执行（P0-16） | 待执行（P0-16） | 待执行（P0-16） |
| 3. 研发判定 | — | — | — |
| 4. 暂缓（defer）？ | ✅ 目标版本 P0-16 | ✅ 目标版本 P0-16 | ✅ 目标版本 P0-16 |

已暂缓至 P0-16，不阻塞当前版本发布。
