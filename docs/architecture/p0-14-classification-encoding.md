# P0-14 架构设计：QA 发现分级标准的编码化

> 作者：高见远（架构） | 日期：2026-07-09 | 版本：v1.0

## 决策：YAML 作为机器可读的权威编码，Markdown 降级为生成产物

### 1. 编码/存储方案

**选择 YAML**，排除 JSON 和 Python 配置：

| 方案 | 人类可读 | 注释 | 安全 | 工具链 | 结论 |
|------|:---:|:---:|:---:|:---:|:---:|
| **YAML** | ⭐⭐⭐ | ✅ | ✅（无 eval） | PyYAML 标准库 | ✅ 采用 |
| JSON | ⭐⭐ | ❌ | ✅ | json 标准库 | ❌ 无注释，格式死板 |
| Python .py | ⭐⭐⭐ | ✅ | ❌（eval 风险） | import | ❌ 安全风险，语言耦合 |
| Markdown only | ⭐⭐⭐ | ✅ | ✅ | 需 NLP 解析 | ❌ 不可靠的机器读取 |

**文件位置**：`config/qa-classification.yaml`

权威性：YAML 是单一事实来源。`docs/standards/qa-finding-classification.md` 由 `scripts/generate_standard_doc.py` 从 YAML 生成，不再手工维护。

### 2. 与 kanban/VA 管线的集成点

```
┌─────────────────────────────────────────────────┐
│         config/qa-classification.yaml           │  ← 单一事实来源
│  levels | security | SLA | state_machine | gate │
└──────────────┬──────────────────────────────────┘
               │ 读取
    ┌──────────┼──────────────────────┐
    ▼          ▼                      ▼
┌───────┐ ┌─────────┐ ┌──────────────────────┐
│  VA   │ │ Scripts │ │ .hermes.md context    │
│ 验证  │ │ 申诉流程 │ │ injection (精简版)    │
└───────┘ └─────────┘ └──────────────────────┘
```

**集成点 1 — kanban_helpers.py（现有脚本迁移）**：

当前 `lib/kanban_helpers.py` 硬编码了 `VALID_LEVELS = {"BLOCKER", "MAJOR", "MINOR", "SUGGESTION"}` 和状态前缀列表。迁移路径：

- `get_current_qa_level()` → 读取 YAML `levels` 作为白名单校验
- `STATE_PREFIXES` → 从 YAML `state_machine.transitions` 自动生成
- `dev_reject.py` 的 `REJECTION_REASONS` → 读取 YAML `workflow.resolution.reject.valid_reasons`
- `appeal.py` 的 `EVIDENCE_TYPES` → 读取 YAML `workflow.appeal.evidence_types`

**迁移成本**：`kanban_helpers.py` 新增一个 `ClassificationLoader` 类 → 6 个脚本各改 3-5 行 import，总改动约 80 行。

**集成点 2 — VA（Verification Agent）**：

VA 验证 QA 报告的判定公式时，对照 YAML 做结构化比对：

```
VA 输入: QA 报告声称 level=MAJOR
VA 动作: 从 YAML levels.MAJOR.criteria 逐条比对
         检查 security.owasp_checklist 是否触发安全漏洞独立判定
         检查 data_sensitivity 是否需要加权
         检查 release_gate.condition 是否满足
VA 输出: verified / falsified / partial
```

**集成点 3 — .hermes.md context injection**：

当前 `.hermes.md` 手写了 7 条关键规则。改为从 YAML 自动生成精简版（30 行以内），避免手写规则与权威源不同步。

**集成点 4 — appeal_tracker.py**：

申诉率阈值 `20%` 从 YAML `appeal_tracking.threshold` 读取，修改阈值不再需要改代码。

### 3. 版本控制/更新机制

```
┌──────────────────────┐
│ 修改 YAML            │  ← 唯一入口，git commit
│ bump version 字段     │     semver 语义
└──────┬───────────────┘
       │
       ├─→ 运行 scripts/generate_standard_doc.py
       │   生成 docs/standards/qa-finding-classification.md
       │
       ├─→ 运行 tests/test_classification_schema.py
       │   验证 YAML schema 完整性（所有 required 字段存在、类型正确）
       │
       └─→ CI 门禁：
            - YAML schema validation (pykwalify / manual)
            - 确保 generated markdown 与 YAML 同步 (diff check)
            - 确保所有脚本仍可正确加载 YAML
```

**版本号语义**：
- **MAJOR**（X.0.0）：新增/删除/重命名 `levels` 键 → 兼容性影响脚本
- **MINOR**（0.X.0）：新增规则项（如 OWASP 新类别）、新增示例
- **PATCH**（0.0.X）：文案修正、threshold 数字微调

git tag 与版本号绑定：`git tag v1.0.0` 对应 `version: "1.0.0"`。

### 4. 迁移计划

| 阶段 | 内容 | 工期 |
|------|------|:---:|
| Phase 1 | 创建 YAML + schema 验证脚本 | 本任务 |
| Phase 2 | `lib/classification.py` 加载器 + 现有脚本迁移 | 1d |
| Phase 3 | `generate_standard_doc.py` 生成 markdown | 0.5d |
| Phase 4 | VA 集成 | 1d |
| Phase 5 | CI 门禁（schema check + diff check） | 0.5d |

---

## 架构裁定

YAML as single source of truth。Markdown 降级为 human-readable export。所有脚本从 YAML 读取规则，消灭硬编码。版本号与 git tag 同步。

无架构 BLOCKER，可以执行 Phase 2。
