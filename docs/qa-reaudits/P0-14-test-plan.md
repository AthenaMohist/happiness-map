# P0-14 测试方案：QA 发现分级标准编码化

> 版本：v1.0 | 状态：Draft
> 编制日期：2026-07-09
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 架构依据：`docs/architecture/p0-14-classification-encoding.md` v1.0
> 被测对象：`config/qa-classification.yaml`（287 行，v1.0.0）

---

## 目录

1. [背景与范围](#1-背景与范围)
2. [被测对象概览](#2-被测对象概览)
3. [测试矩阵总览](#3-测试矩阵总览)
4. [L1: YAML Schema 验证](#4-l1-yaml-schema-验证)
5. [L2: YAML ↔ Markdown 双向一致性](#5-l2-yaml--markdown-双向一致性)
6. [L3: 脚本集成回归测试](#6-l3-脚本集成回归测试)
7. [L4: VA 集成就绪验证](#7-l4-va-集成就绪验证)
8. [L5: 边缘 Case 覆盖分析](#8-l5-边缘-case-覆盖分析)
9. [L6: YAML 编码正确性专项](#9-l6-yaml-编码正确性专项)
10. [CI 门禁设计](#10-ci-门禁设计)
11. [Findings 分级](#11-findings-分级)
12. [发布门禁评估](#12-发布门禁评估)

---

## 1. 背景与范围

### 1.1 原始任务

| 字段 | 值 |
|------|-----|
| P0 编号 | P0-14 |
| 标题 | QA 发现分级标准的编码化 |
| 架构裁定 | YAML 作为单一事实来源，Markdown 降级为生成产物 |
| Phase 1 产出 | `config/qa-classification.yaml`（已完成）+ 本测试方案 |

### 1.2 测试目标

P0-14 将 QA 发现分级标准从手写 Markdown 迁移为机器可读的 YAML 权威编码。测试需验证：

| 层级 | 目标 | 覆盖内容 |
|------|------|---------|
| **L1: Schema 验证** | YAML 结构完整性 | 所有 required 字段存在、类型正确、枚举值合法 |
| **L2: 双向一致性** | YAML ↔ Markdown 同步 | YAML 编码了标准文档的全部 13 个章节，生成 Markdown 与当前手工版一致 |
| **L3: 脚本集成回归** | 现有脚本正确迁移 | `kanban_helpers.py` + 6 个申诉脚本从 YAML 读取后行为不变 |
| **L4: VA 集成就绪** | VA 可结构化读取 | VA 能从 YAML 提取判定公式/安全规则/SLA/门禁做结构化比对 |
| **L5: 边缘 Case** | 异常输入不崩溃 | 版本冲突、字段缺失、类型错误、YAML 格式破坏 |
| **L6: 编码正确性** | 中文/特殊字符/锚点 | YAML 正确编码中文、特殊字符、多行字符串、列表结构 |

### 1.3 测试范围说明

- **覆盖**：YAML schema、YAML↔Markdown 一致性、6 个脚本集成、VA 接口、边缘 case
- **不覆盖**：Markdown 自动生成脚本 `generate_standard_doc.py` 的实现细节（Phase 3，本方案只覆盖 Phase 1 的 YAML schema + Phase 2 的脚本迁移）
- **测试执行**：所有 L1-L4 测试应在 < 5s 内完成（纯数据验证，无网络/LLM 调用）

---

## 2. 被测对象概览

### 2.1 文件清单

| 文件 | 行数 | 性质 |
|------|:---:|------|
| `config/qa-classification.yaml` | 287 | 单一事实来源（Phase 1 产出） |
| `docs/standards/qa-finding-classification.md` | 436 | 人类可读导出（当前手工维护，Phase 3 后改为生成） |
| `scripts/lib/kanban_helpers.py` | 122 | 共享工具库（Phase 2 迁移目标） |
| `scripts/appeal.py` | — | 申诉脚本（Phase 2 迁移目标） |
| `scripts/dev_reject.py` | — | 研发驳回脚本（Phase 2 迁移目标） |
| `scripts/product_rule.py` | — | 产品裁定脚本（Phase 2 迁移目标） |
| `scripts/downgrade_notify.py` | — | 降级通知脚本（Phase 2 迁移目标） |
| `scripts/defer.py` | — | 暂缓脚本（Phase 2 迁移目标） |
| `scripts/appeal_tracker.py` | — | 申诉率追踪脚本（Phase 2 迁移目标） |

### 2.2 YAML 结构概览

```
version: "1.0.0"              # semver
levels: {BLOCKER, MAJOR, MINOR, SUGGESTION}  # §1
principles: {5 条判定原则}                    # §1.3
security: {rules + owasp_checklist}           # §2
performance: {relative + fallback thresholds}  # §3
data_sensitivity: {S/A/B/C}                  # §4
examples: [8 个场景示例]                       # §5
workflow: {resolution + appeal + downgrade}   # §6
state_machine: {11 states + 14 transitions}   # §7
sla: {dev + qa + special_scenarios}           # §8-9
release_gate: {condition + review + regression} # §10
product_redlines: [3 条红线]                   # §11
supplementary: {p0_immediate + p1_future}      # §12
appeal_tracking: {threshold + description}     # 申诉率
```

### 2.3 现有脚本硬编码清单（Phase 2 迁移对照）

| 脚本 | 当前硬编码项 | YAML 对应字段 | 迁移方式 |
|------|------------|-------------|---------|
| `kanban_helpers.py` | `VALID_LEVELS = {"BLOCKER", "MAJOR", "MINOR", "SUGGESTION"}` | `levels` keys | 动态读取 |
| `kanban_helpers.py` | `STATE_PREFIXES` 元组列表 | `state_machine.transitions` | 自动生成 |
| `dev_reject.py` | 驳回理由枚举 | `workflow.resolution.reject.valid_reasons` | 动态读取 |
| `appeal.py` | 证据类型枚举 | `workflow.appeal.evidence_types` | 动态读取 |
| `appeal_tracker.py` | 阈值 `0.20` 硬编码 | `appeal_tracking.threshold` | 动态读取 |

---

## 3. 测试矩阵总览

| 层级 | 测试分类 | 测试数（预估） | 优先级 | 预计耗时 |
|------|---------|:---:|:---:|:---:|
| L1 | YAML Schema 验证 | 18 | P0 | < 1s |
| L2 | YAML↔Markdown 一致性 | 13（每章 1 条） | P0 | < 1s |
| L3 | 脚本集成回归 | 10 | P1 | < 2s |
| L4 | VA 集成就绪 | 6 | P1 | < 1s |
| L5 | 边缘 Case | 12 | P1 | < 1s |
| L6 | YAML 编码正确性 | 8 | P0 | < 1s |
| **合计** | | **67** | | **< 5s** |

---

## 4. L1: YAML Schema 验证

### 4.1 测试设计

验证 YAML 文件的结构完整性——所有 required 字段存在、类型正确、枚举值在合法范围内。

### 4.2 测试用例矩阵

| # | 测试 ID | 验证点 | 预期 | 优先级 |
|:---:|---------|--------|------|:---:|
| TC-S01 | `test_yaml_parses` | YAML 文件可被 `yaml.safe_load()` 正常解析 | 无异常 | P0 |
| TC-S02 | `test_version_field` | `version` 字段存在且为 semver 格式 | `"1.0.0"` 匹配 `\d+\.\d+\.\d+` | P0 |
| TC-S03 | `test_levels_all_four_present` | `levels` 下 BLOCKER/MAJOR/MINOR/SUGGESTION 四个 key 都存在 | 4 keys | P0 |
| TC-S04 | `test_levels_each_has_definition_and_impact` | 每个 level 有 `definition` 和 `release_impact` | 均为 non-empty string | P0 |
| TC-S05 | `test_levels_each_has_criteria_list` | 每个 level 有 `criteria`，且为 list（≥1 项） | `isinstance(list)` | P0 |
| TC-S06 | `test_principles_all_five` | `principles` 下 5 个 key 都存在 | user_visible_filter, workaround_filter, probabilistic_bug, tie_break, env_not_downgrade | P0 |
| TC-S07 | `test_security_rules_have_valid_levels` | `security.rules[].level` ∈ {BLOCKER, MAJOR, cvss_mapped} | 全部合法 | P0 |
| TC-S08 | `test_owasp_checklist_all_ten` | `security.owasp_checklist` 下 A1-A10 全部存在 | 10 entries | P0 |
| TC-S09 | `test_owasp_checklist_min_level_valid` | 每个 OWASP 的 `min_level` ∈ valid levels | 全部合法 | P0 |
| TC-S10 | `test_data_sensitivity_all_four` | `data_sensitivity` 下 S/A/B/C 四个 key 都存在 | 4 keys | P0 |
| TC-S11 | `test_examples_all_have_scenario_level_rationale` | `examples[]` 每项含 scenario, level, rationale | 全部必填字段存在 | P0 |
| TC-S12 | `test_workflow_reject_reasons` | `workflow.resolution.reject.valid_reasons` 含 by_design, cannot_repro, cost_gt_benefit | 3 项 | P0 |
| TC-S13 | `test_workflow_appeal_evidence_types` | `workflow.appeal.evidence_types` 含 repro, impact, feedback, contradiction | 4 项 | P0 |
| TC-S14 | `test_state_machine_all_states_declared` | `state_machine.states` 含全部 11 个状态 | NEW, OPEN, CONFIRMED, REJECTED, APPEAL, DEFERRED, RESOLVED, CLOSED, REOPENED, DUPLICATE, WITHDRAWN | P0 |
| TC-S15 | `test_state_machine_all_transitions_valid` | 每条 transition 的 from/to ∈ states，actor ∈ {qa, dev, product, dev+product} | 全部合法 | P0 |
| TC-S16 | `test_sla_dev_all_levels` | `sla.dev` 下 BLOCKER/MAJOR/MINOR/SUGGESTION 四个 key 都存在 | 4 keys | P0 |
| TC-S17 | `test_release_gate_condition_format` | `release_gate.condition` 含 `BLOCKER=0` `MAJOR<=3` `安全漏洞=0` | 公式完整 | P0 |
| TC-S18 | `test_product_redlines_three` | `product_redlines` 为 list，长度 = 3 | 3 items | P0 |

### 4.3 实现方式

```
tests/test_classification_schema.py
  ├── class TestYamlSchema
  │   ├── setUp: yaml.safe_load("config/qa-classification.yaml")
  │   └── TC-S01 ~ TC-S18
  └── runner: python -m pytest tests/test_classification_schema.py -v
```

---

## 5. L2: YAML ↔ Markdown 双向一致性

### 5.1 测试设计

验证 YAML 编码了标准 Markdown 文档的全部 13 个章节内容，无遗漏、无矛盾。

### 5.2 测试用例矩阵

| # | 测试 ID | 标准章 | YAML 字段 | 验证方式 | 优先级 |
|:---:|---------|--------|----------|---------|:---:|
| TC-C01 | `test_consistency_levels` | §1 四级分层 | `levels` | 4 个级别定义一致 | P0 |
| TC-C02 | `test_consistency_principles` | §1.3 判定原则 | `principles` | 5 条原则都在 | P0 |
| TC-C03 | `test_consistency_security` | §2 安全独立判定 | `security` | bypass_user_visible_filter=true, OWASP 10 类全 | P0 |
| TC-C04 | `test_consistency_performance` | §3 性能退化阈值 | `performance` | relative + fallback 双阈值都有 | P0 |
| TC-C05 | `test_consistency_data_sensitivity` | §4 数据敏感度加权 | `data_sensitivity` | S/A/B/C 权重公式一致 | P0 |
| TC-C06 | `test_consistency_examples` | §5 分级示例表 | `examples` | 8 个示例级别一致 | P0 |
| TC-C07 | `test_consistency_workflow` | §6 论证流程 | `workflow` | agree/reject/defer + appeal 机制 | P0 |
| TC-C08 | `test_consistency_state_machine` | §7 状态机 | `state_machine` | 11 states + 14 transitions 完整 | P0 |
| TC-C09 | `test_consistency_sla` | §8-9 SLA | `sla` | dev 三档 + qa 四阶段 + 特殊场景 | P0 |
| TC-C10 | `test_consistency_release_gate` | §10 发布门禁 | `release_gate` | 公式 + review + regression 范围 | P0 |
| TC-C11 | `test_consistency_redlines` | §11 产品红线 | `product_redlines` | 3 条红线 | P0 |
| TC-C12 | `test_consistency_supplementary` | §12 补充维度 | `supplementary` | P0 5 项 + P1 4 项 | P0 |
| TC-C13 | `test_consistency_appeal_tracking` | §6.3 申诉率追踪 | `appeal_tracking` | threshold=0.20 | P0 |

### 5.3 实现方式

```python
# TC-C01 示例：验证 YAML levels 涵盖标准 §1 的全部级别
def test_consistency_levels(self):
    yaml_levels = set(self.data["levels"].keys())
    assert yaml_levels == {"BLOCKER", "MAJOR", "MINOR", "SUGGESTION"}
    
    # BLOCKER criteria 含 user_visible AND function_blocked AND no_workaround
    blocker_conditions = [c["condition"] for c in self.data["levels"]["BLOCKER"]["criteria"]]
    assert any("user_visible" in c and "function_blocked" in c and "no_workaround" in c 
               for c in blocker_conditions)
```

---

## 6. L3: 脚本集成回归测试

### 6.1 测试设计

验证现有脚本在引入 YAML 读取后行为不变。使用 mock YAML 数据隔离测试。

### 6.2 测试用例矩阵

| # | 测试 ID | 验证点 | 测试方式 | 优先级 |
|:---:|---------|--------|---------|:---:|
| TC-R01 | `test_valid_levels_from_yaml` | `kanban_helpers.VALID_LEVELS` 从 YAML 动态生成 = {"BLOCKER", "MAJOR", "MINOR", "SUGGESTION"} | 导入后断言集合 | P1 |
| TC-R02 | `test_state_prefixes_from_yaml` | `kanban_helpers.STATE_PREFIXES` 从 YAML `state_machine.transitions` 自动生成，顺序与原来一致 | 断言列表长度 + 每个 prefix | P1 |
| TC-R03 | `test_reject_reasons_from_yaml` | `dev_reject.py` 的驳回理由从 `workflow.resolution.reject.valid_reasons` 读取 | mock yaml → 断言理由枚举 | P1 |
| TC-R04 | `test_evidence_types_from_yaml` | `appeal.py` 的证据类型从 `workflow.appeal.evidence_types` 读取 | mock yaml → 断言 4 项 | P1 |
| TC-R05 | `test_appeal_threshold_from_yaml` | `appeal_tracker.py` 阈值 `0.20` 从 `appeal_tracking.threshold` 读取 | mock yaml → assert threshold == 0.20 | P1 |
| TC-R06 | `test_downgrade_notify_triggers` | `downgrade_notify.py` 触发条件从 `workflow.downgrade_transparency.triggers` 读取 | assert ["BLOCKER→MAJOR", "MAJOR→MINOR"] | P1 |
| TC-R07 | `test_state_transition_actors` | 状态转换 actor 从 YAML 验证（qa/dev/product 权限） | 每个 transition 的 actor ∈ valid | P1 |
| TC-R08 | `test_missing_yaml_graceful_fallback` | YAML 文件不存在/损坏时脚本有 fallback（内置默认值 + 日志警告） | mock FileNotFoundError → 脚本不崩溃 | P1 |
| TC-R09 | `test_yaml_version_mismatch_warning` | 脚本检测 version 与预期不兼容时输出 warning（不中止） | mock version="9.0.0" → 警告不崩溃 | P1 |
| TC-R10 | `test_all_scripts_load_yaml` | 6 个申诉脚本全部能正确加载 YAML | 遍历导入 → 无 ImportError | P1 |

### 6.3 实现方式

```
tests/test_classification_integration.py
  ├── class TestScriptMigration
  │   ├── setUp: mock YAML data → patch yaml.safe_load
  │   └── TC-R01 ~ TC-R10
  └── runner: python -m pytest tests/test_classification_integration.py -v
```

### 6.4 当前硬编码清单（回归基准）

| 位置 | 当前值 | 预期从 YAML 读取 |
|------|--------|----------------|
| `kanban_helpers.py:34` | `VALID_LEVELS = {"BLOCKER", "MAJOR", "MINOR", "SUGGESTION"}` | `levels` keys |
| `kanban_helpers.py:22-32` | `STATE_PREFIXES = [...9 个前缀...]` | `state_machine.transitions` |
| `dev_reject.py` | 驳回理由枚举 | `workflow.resolution.reject.valid_reasons` |
| `appeal.py` | 证据类型枚举 | `workflow.appeal.evidence_types` |
| `appeal_tracker.py` | `threshold = 0.20` | `appeal_tracking.threshold` |
| `downgrade_notify.py` | 触发级别 | `workflow.downgrade_transparency.triggers` |

---

## 7. L4: VA 集成就绪验证

### 7.1 测试设计

验证 VA（Verification Agent）能从 YAML 结构化读取判定所需的所有数据，不需要解析 Markdown 或依赖硬编码。

### 7.2 VA 读取路径对照

| VA 需求 | YAML 读取路径 | 数据类型 |
|---------|-------------|---------|
| 级别定义白名单 | `levels.<LEVEL>.definition` | `str` |
| 判定公式（BLOCKER 条件） | `levels.BLOCKER.criteria[0].condition` | `str` |
| 安全独立判定标志 | `security.bypass_user_visible_filter` | `bool` |
| 安全漏洞类别→级别映射 | `security.rules[].category -> .level` | `dict` |
| 数据敏感度加权 | `data_sensitivity.<S/A/B/C>.weight` | `str` |
| 发布门禁公式 | `release_gate.condition` | `str` |
| 申诉证据类型白名单 | `workflow.appeal.evidence_types[].id` | `list` |
| SLA 时限 | `sla.dev.BLOCKER.response` | `str` |

### 7.3 测试用例矩阵

| # | 测试 ID | 验证点 | 预期 | 优先级 |
|:---:|---------|--------|------|:---:|
| TC-V01 | `test_va_can_read_levels` | VA 读取 `levels` 可获取 4 个级别定义 | 返回 dict with 4 keys | P1 |
| TC-V02 | `test_va_can_read_security_rules` | VA 读取 `security.rules` 获取 category→level 映射 | list of 9 items | P1 |
| TC-V03 | `test_va_can_read_data_sensitivity` | VA 读取 `data_sensitivity` 获取 S/A/B/C 权重 | 4 keys with weight | P1 |
| TC-V04 | `test_va_can_read_release_gate` | VA 读取 `release_gate.condition` 获取门禁公式 | non-empty string | P1 |
| TC-V05 | `test_va_can_read_sla` | VA 读取 `sla.dev.BLOCKER` 获取 response/locate/plan | 3 fields all strings | P1 |
| TC-V06 | `test_va_can_read_owasp_checklist` | VA 读取 `security.owasp_checklist.A1.min_level` | "BLOCKER" | P1 |

### 7.4 实现方式

```python
# TC-V01 示例
def test_va_can_read_levels(self):
    loader = ClassificationLoader()  # from lib/classification.py
    levels = loader.get_levels()
    assert set(levels.keys()) == {"BLOCKER", "MAJOR", "MINOR", "SUGGESTION"}
    assert levels["BLOCKER"]["release_impact"] == "阻塞发版"
```

---

## 8. L5: 边缘 Case 覆盖分析

### 8.1 测试用例矩阵

| # | 测试 ID | 边缘场景 | 预期行为 | 风险 | 优先级 |
|:---:|---------|---------|---------|:---:|:---:|
| TC-E01 | `test_yaml_file_not_found` | YAML 文件不存在 | `ClassificationLoader` 抛 `FileNotFoundError` + 友好错误消息 | 低 | P1 |
| TC-E02 | `test_yaml_file_empty` | YAML 文件为空 | 抛异常或返回空 dict + 日志警告 | 低 | P1 |
| TC-E03 | `test_yaml_missing_required_key` | `levels` 被删除 | schema validation 失败 + 明确指出缺失哪个 key | 低 | P1 |
| TC-E04 | `test_yaml_invalid_level_in_example` | `examples[0].level` 为 "INVALID" | 加载时校验 → 抛出/记录警告 | 低 | P1 |
| TC-E05 | `test_yaml_state_transition_invalid_actor` | transition actor = "unknown" | 校验失败 | 低 | P1 |
| TC-E06 | `test_yaml_extra_unknown_top_level_key` | 顶层出现未知 key（forward-compat） | 警告但不崩溃（forward-compat） | 低 | P1 |
| TC-E07 | `test_yaml_version_not_semver` | `version: "abc"` | 警告 + 继续加载 | 低 | P1 |
| TC-E08 | `test_yaml_circular_reference` | YAML anchor/alias 循环引用 | `yaml.safe_load` 应拒绝或检测 | 低 | P1 |
| TC-E09 | `test_yaml_duplicate_level_key` | `levels` 下出现两个 BLOCKER | YAML 解析后取后者（YAML 特性），校验时警告 | 中 | P1 |
| TC-E10 | `test_yaml_list_as_string` | criteria 为字符串而非 list | 类型校验失败 | 低 | P1 |
| TC-E11 | `test_yaml_numeric_value_not_number` | `appeal_tracking.threshold` 为 "abc" | 类型校验失败 | 低 | P1 |
| TC-E12 | `test_concurrent_yaml_read` | 多进程同时读取 YAML | 无竞态（纯读取操作） | 低 | P1 |

---

## 9. L6: YAML 编码正确性专项

### 9.1 测试设计

YAML 作为机器可读的权威编码，必须正确处理中文、特殊字符、多行字符串、列表嵌套等场景。本节验证 YAML 本身编码的正确性。

### 9.2 测试用例矩阵

| # | 测试 ID | 验证点 | 预期 | 优先级 |
|:---:|---------|--------|------|:---:|
| TC-Y01 | `test_chinese_encoding` | 中文字段正确加载 | `levels.BLOCKER.definition` = "不修不能发版" | P0 |
| TC-Y02 | `test_chinese_in_examples` | 示例场景中文正确 | `examples[0].scenario` 含中文文本 | P0 |
| TC-Y03 | `test_special_characters_in_description` | 特殊字符（→, ≥, ≤, /）正确 | `workflow.downgrade_transparency.triggers[0]` = "BLOCKER→MAJOR" | P0 |
| TC-Y04 | `test_multiline_string_no_escape_issues` | 多行 description 无转义问题 | `principles.user_visible_filter.description` 无多余引号/转义 | P0 |
| TC-Y05 | `test_nested_list_depth` | 深层嵌套 list 正确 | `levels.BLOCKER.criteria` 为 list of dicts | P0 |
| TC-Y06 | `test_boolean_values` | Boolean 值正确解析为 Python bool | `security.bypass_user_visible_filter` is `True` (not string "true") | P0 |
| TC-Y07 | `test_numeric_values` | 数值正确解析为 Python float | `appeal_tracking.threshold` is `0.2` (not string "0.20") | P0 |
| TC-Y08 | `test_null_values` | null 值正确解析为 Python None | `sla.dev.MINOR.locate` is `None` | P0 |

### 9.3 实现方式

```python
# TC-Y01 示例
def test_chinese_encoding(self):
    assert self.data["levels"]["BLOCKER"]["definition"] == "不修不能发版"
    assert self.data["levels"]["MAJOR"]["definition"] == "严重影响体验，发版需标注 known issue"

# TC-Y03 示例
def test_special_characters(self):
    triggers = self.data["workflow"]["downgrade_transparency"]["triggers"]
    assert "BLOCKER→MAJOR" in triggers  # → is U+2192
```

---

## 10. CI 门禁设计

### 10.1 门禁步骤

```
CI Pipeline:
  1. YAML Schema Validation  → tests/test_classification_schema.py
  2. 一致性检查               → tests/test_classification_consistency.py
  3. 脚本集成测试             → tests/test_classification_integration.py
  4. YAML 编码正确性          → tests/test_classification_encoding.py
  5. (Phase 3) diff check    → 确保生成的 .md 与 YAML 同步
```

### 10.2 门禁失败处理

| 失败类型 | 级别 | 处理 |
|---------|:---:|------|
| YAML 解析失败 | **BLOCKER** | 阻断合入 |
| Schema 校验失败 | **BLOCKER** | 阻断合入 |
| 一致性检查失败 | **MAJOR** | 阻断合入（说明 YAML 与标准文档不同步） |
| 脚本集成回归失败 | **BLOCKER** | 阻断合入（破坏现有功能） |
| 编码正确性失败 | **BLOCKER** | 阻断合入 |

### 10.3 快速运行命令

```bash
# 全量运行
cd /workspace/devPPL && python -m pytest tests/ -v

# 仅 schema
cd /workspace/devPPL && python -m pytest tests/test_classification_schema.py -v

# 仅一致性
cd /workspace/devPPL && python -m pytest tests/test_classification_consistency.py -v

# 仅集成
cd /workspace/devPPL && python -m pytest tests/test_classification_integration.py -v

# 仅编码
cd /workspace/devPPL && python -m pytest tests/test_classification_encoding.py -v
```

---

## 11. Findings 分级

### 11.1 已知缺口（实施前识别）

以下缺口在测试方案设计过程中识别，需在实施前确认是否阻塞 Phase 2：

| # | 发现 | 标准判定 | 级别 | 处置 |
|:---:|------|---------|:---:|------|
| F01 | YAML `version` 字段为 string，TypeScript/Go 消费可能需要 semver 对象 | 非用户可感知 + 非安全 | SUGGESTION | 记录，Phase 2 暂不处理 |
| F02 | `examples` 目前只编码了 8 条，标准 Markdown 有 17 条 | 用户不可感知（YAML 是内部数据源） | SUGGESTION | Phase 1 补齐全部 17 条 |
| F03 | YAML 无 `data_sensitivity` 完整分类表（附录 A），只编码了加权规则 | 无用户影响 | SUGGESTION | Phase 2 补充 |
| F04 | YAML 无 OWASP Checklist 的 `典型表现` 列（附录 B） | 无用户影响 | SUGGESTION | Phase 2 补充 |

### 11.2 实施后 Findigns 分级标准

任何在实施过程中发现的 bug，按标准 §1.2 五步判定公式逐条定级：

```
前置检查：安全漏洞？→ 否
正式判定：
  步骤 E — 用户可感知？→ ...
  步骤 F — 功能阻断？→ ...
  步骤 W — 有 workaround？→ ...
  步骤 D — 数据敏感度？
  步骤 P — 性能退化？
→ 级别
```

---

## 12. 发布门禁评估

按标准 §10 发布门禁公式：`BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉`

### 12.1 Phase 1 门禁

| 门禁项 | 要求 | 状态 |
|--------|:---:|:---:|
| YAML schema 18 项测试全部 PASS | BLOCKER=0 | ⏳ 待执行 |
| YAML↔Markdown 一致性 13 项 PASS | BLOCKER=0 | ⏳ 待执行 |
| YAML 编码正确性 8 项 PASS | BLOCKER=0 | ⏳ 待执行 |

### 12.2 Phase 2 门禁（脚本迁移完成后）

| 门禁项 | 要求 | 状态 |
|--------|:---:|:---:|
| 脚本集成回归 10 项 PASS | BLOCKER=0 | ⏳ 待执行 |
| 现有 6 个脚本功能回归（上阶段测试） | MAJOR≤3 | ⏳ 待执行 |

---

## 附录 A：测试执行环境

| 依赖项 | 版本 | 说明 |
|--------|------|------|
| Python | ≥ 3.10 | 项目最低要求 |
| pytest | ≥ 7.0（当前 9.1.1） | 测试框架 |
| PyYAML | ≥ 6.0 | YAML 解析 |

## 附录 B：测试文件清单（实施产出）

| 文件 | 测试数 | 说明 |
|------|:---:|------|
| `tests/test_classification_schema.py` | 18 | L1: YAML schema 验证 |
| `tests/test_classification_consistency.py` | 13 | L2: YAML↔Markdown 一致性 |
| `tests/test_classification_integration.py` | 10 | L3: 脚本集成回归 |
| `tests/test_classification_va.py` | 6 | L4: VA 集成就绪 |
| `tests/test_classification_edge.py` | 12 | L5: 边缘 Case |
| `tests/test_classification_encoding.py` | 8 | L6: YAML 编码正确性 |
| **合计** | **67** | |

## 附录 C：与架构文档的对照

| 架构文档要求 | 本方案覆盖 | 对应测试层级 |
|------------|:---:|:---:|
| YAML schema validation | ✅ | L1（18 tests） |
| 确保 generated markdown 与 YAML 同步 (diff check) | ✅ | L2（13 tests） |
| 确保所有脚本仍可正确加载 YAML | ✅ | L3（10 tests） |
| VA 集成（结构化比对） | ✅ | L4（6 tests） |
| 版本号语义（semver） | ✅ | TC-S02, TC-E07 |

---

> **方案状态**：Draft — 待 Roundtable 评审后进入实施（Phase 1 测试编写约 1h）
