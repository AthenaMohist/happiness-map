# P0-15 D2 架构发现测试方案：修复验证（修订版）

> 版本：v2.0 | 状态：Executed
> 编制日期：2026-07-10
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 架构依据：`docs/arch-p0-15-appeal-mechanism.md` v1.0 §5
> D1 方案：`docs/qa-reaudits/P0-15-D1-test-plan.md` v1.0（47 cases）
> D1 评审批次：全员通过，反馈已融入本修订版

---

## 目录

1. [D1 → D2 变更摘要](#1-d1--d2-变更摘要)
2. [测试矩阵总览](#2-测试矩阵总览)
3. [S1: A1 whoami 前置验证](#3-s1-a1-whoami-前置验证)
4. [S2: A2 STATE_PREFIXES 同步验证](#4-s2-a2-state_prefixes-同步验证)
5. [S3: A3 CLOSED 防护验证](#5-s3-a3-closed-防护验证)
6. [S4: E2E 全流程集成](#6-s4-e2e-全流程集成)
7. [S5: Dev Supplements](#7-s5-dev-supplements)
8. [S6: M1/M2 模块覆盖](#8-s6-m1m2-模块覆盖)
9. [S7: 回归验证](#9-s7-回归验证)
10. [S8: Schema & Security](#10-s8-schema--security)
11. [发布门禁评估](#11-发布门禁评估)

---

## 1. D1 → D2 变更摘要

### 1.1 移除项（产品裁定）

| 移除内容 | 原因 | 决策者 |
|---------|------|--------|
| A1-01 ~ A1-10（10 项角色鉴权测试） | 角色鉴权不归脚本管理，是 Hermes 基础设施层问题 | 产品（许清楚） |

### 1.2 新增项（架构补充）

| 来源 | 新增内容 | 测试项数 |
|------|---------|:---:|
| 架构审查 | A1 whoami 前置验证 | 3 |
| 架构审查 | A2 transition 数量错误检测、WITHDRAWN 缺失、sorted 排序风险 | 8 |
| 架构审查 | A3 重复 CLOSED 防护 | 2 |
| 架构审查 | 全流程 E2E | 6 |
| **小计** | | **19** |

### 1.3 新增项（研发补充）

| 来源 | 新增内容 | 测试项数 |
|------|---------|:---:|
| 研发审查 | A1 downgrade_notify 鉴权测试 | 1 |
| 研发审查 | A2 YAML 缺失防御行为 | 1 |
| 研发审查 | A5 has_ruling 字段兼容性 | 2 |
| **小计** | | **4** |

### 1.4 新增项（M1/M2 覆盖遗漏）

| 模块 | 覆盖内容 | 测试项数 |
|------|---------|:---:|
| M1 (kanban_helpers) | 公开 API 完整性、类型正确性、timestamp 格式 | 5 |
| M2 (config_loader) | 访问器完整性、force_reload、YAML key 覆盖 | 5 |
| **小计** | | **10** |

### 1.5 净变化

| 维度 | D1 | D2 | 变化 |
|------|:---:|:---:|:---:|
| 架构发现测试 | 41 | 23 | -18 |
| E2E 集成 | 0 | 6 | +6 |
| 模块覆盖 | 0 | 10 | +10 |
| 回归验证 | 6 | 6 | 0 |
| Schema/Security | 0 | 4 | +4 |
| Dev Supplements | 0 | 4 | +4 |
| A1 whoami | 10 | 3 | -7 |
| **合计** | **47** | **52** | **+5** |

---

## 2. 测试矩阵总览

| Section | 内容 | 测试数 | 级别 | 预计耗时 |
|---------|------|:---:|:---:|:---:|
| S1 | A1 whoami 前置验证 | 3 | L0 | <0.1s |
| S2 | A2 STATE_PREFIXES 同步 | 11 | L0/L1 | <0.5s |
| S3 | A3 CLOSED 防护 | 5 | L0/L1 | <0.1s |
| S4 | E2E 全流程集成 | 6 | L0/L1 | <0.5s |
| S5 | Dev Supplements | 7 | L1 | <0.3s |
| S6 | M1/M2 模块覆盖 | 10 | L1 | <0.3s |
| S7 | 回归验证 | 6 | L1/L3 | <3s |
| S8 | Schema & Security | 4 | L1 | <0.1s |
| **合计** | | **52** | | **<5s** |

---

## 3. S1: A1 whoami 前置验证

### 背景

D1 方案中的 A1（10 项角色级鉴权测试）被产品裁定全部拒绝。但架构审查指出仍需验证 `hermes kanban whoami` 的基本可用性和模块一致性。

### 测试用例

| TC-ID | 场景 | 验证方法 | 优先级 |
|-------|------|---------|:---:|
| A1-D2-01 | hermes kanban whoami 语法验证 | subprocess 命令结构检查 | P1 |
| A1-D2-02 | _run_hermes 接受 whoami 参数 | 源码分析 | P1 |
| A1-D2-03 | 6 脚本统一导入 lib.kanban_helpers | 源码 grep | P0 |

---

## 4. S2: A2 STATE_PREFIXES 同步验证

### 核心风险

STATE_PREFIXES 是硬编码的 9 个前缀列表，与 YAML state_machine 的 14 条 transitions 不同步。YAML 中定义的 DUPLICATE 和 WITHDRAWN 状态无对应前缀，新增状态需同时修改两处。

### 测试用例

| TC-ID | 场景 | 验证方法 | 优先级 |
|-------|------|---------|:---:|
| A2-D2-01 | YAML transitions 数量 = 14 | 计数验证 | P0 |
| A2-D2-02 | 无重复 from→to 对 | Counter 去重 | P1 |
| A2-D2-03 | WITHDRAWN 在 YAML to-states 中 | 集合成员检查 | P1 |
| A2-D2-04 | DUPLICATE 在 YAML to-states 中 | 集合成员检查 | P1 |
| A2-D2-05 | STATE_PREFIXES 覆盖所有 YAML to-states | **差异检测** | **P0** |
| A2-D2-06 | STATE_PREFIXES 无重复状态名 | 去重检查 | P1 |
| A2-D2-07 | 9 个正则均可编译 | re.compile | P1 |
| A2-D2-08 | 每个正则匹配对应前缀 | 模式匹配验证 | P1 |
| A2-D2-09 | YAML 缺失时防御行为 | 源码验证 | P2 |
| A2-D2-10 | YAML 版本 semver 校验 | 正则匹配 | P1 |
| A2-D2-11 | 4 条申诉核心路径在 YAML 中 | 路径匹配 | P0 |

### 关键发现

**A2-D2-05 FAIL**: STATE_PREFIXES 缺少 `WITHDRAWN` 和 `DUPLICATE`。这**验证了架构发现 A2** — STATE_PREFIXES 与 YAML 不同步的 MAJOR 级问题确实存在。

按标准 §1.2 判定公式：
- 是否 user_visible？ → 否（内部实现细节）
- 是否影响状态解析正确性？ → 是（DUPLICATE/WITHDRAWN 状态不可解析）
- 是否有 workaround？ → 是（手动同步）
- **判定：MAJOR** — 与架构审查一致

---

## 5. S3: A3 CLOSED 防护验证

### 测试用例

| TC-ID | 场景 | 优先级 |
|-------|------|:---:|
| A3-D2-01 | has_ruling 使用 startswith 防重复裁定 | P0 |
| A3-D2-02 | appeal.py 含 has_ruling 二次申诉防护 | P0 |
| A3-D2-03 | product_rule reinstated 分支含 create_task | P0 |
| A3-D2-04 | product_rule upheld 分支不调用 create_task | P1 |
| A3-D2-05 | CLOSED 状态存在于 STATE_PREFIXES | P1 |

---

## 6. S4: E2E 全流程集成

### 测试用例

| TC-ID | 场景 | 优先级 |
|-------|------|:---:|
| E2E-D2-01 | 6 脚本可独立导入 | P0 |
| E2E-D2-02 | 6 脚本含 main() | P0 |
| E2E-D2-03 | 6 脚本 --help 参数声明 | P0 |
| E2E-D2-04 | 跨脚本 config 引用一致性 | P0 |
| E2E-D2-05 | 状态机 11 个状态完整性 | P0 |
| E2E-D2-06 | 3 条产品红线完整性 | P0 |

---

## 7. S5: Dev Supplements

| TC-ID | 场景 | 优先级 |
|-------|------|:---:|
| DEV-D2-01 | downgrade_notify 级别降级校验 | P0 |
| DEV-D2-02 | LEVEL_RANK 4 层完整 | P1 |
| DEV-D2-03 | has_ruling 前缀匹配兼容性 | P1 |
| DEV-D2-04 | has_ruling 不匹配文中引用 | P1 |
| DEV-D2-05 | get_current_qa_state 逆序扫描 | P1 |
| DEV-D2-06 | classify_task 5 种分类 | P1 |
| DEV-D2-07 | defer.py BLOCKER 暂缓需 Frank 签字 | P0 |

---

## 8. S6: M1/M2 模块覆盖

| TC-ID | 场景 | 模块 | 优先级 |
|-------|------|------|:---:|
| M1-D2-01 | 公开符号完整性 (13 exports) | kanban_helpers | P0 |
| M1-D2-02 | 公开访问器完整性 (20 accessors) | config_loader | P0 |
| M1-D2-03 | STATE_PREFIXES 元素类型 (str, str) | kanban_helpers | P1 |
| M1-D2-04 | timestamp() ISO 8601 格式 | kanban_helpers | P1 |
| M1-D2-05 | VALID_LEVELS 跨模块一致性 | both | P0 |
| M2-D2-01 | force_reload 功能 | config_loader | P1 |
| M2-D2-02 | YAML 顶级 key 全量覆盖 | config_loader | P0 |
| M2-D2-03 | 3 种驳回理由 | config_loader | P1 |
| M2-D2-04 | 4 种证据类型 | config_loader | P1 |
| M2-D2-05 | SLA dev/qa 双维度 | config_loader | P1 |

---

## 9. S7: 回归验证

| TC-ID | 场景 | 预期 | 优先级 |
|-------|------|------|:---:|
| REG-D2-01 | test_integration.py 8/8 PASS | PASS | P0 |
| REG-D2-02 | test_config_loader.py ALL OK | PASS | P0 |
| REG-D2-03 | 6 脚本 --help | 无 ImportError/AttributeError | P0 |
| REG-D2-04 | VALID_LEVELS 跨脚本一致 | 一致 | P1 |
| REG-D2-05 | A4 assignee 硬编码检查 | 发现 location | P1 |
| REG-D2-06 | 脚本 docstring 引用标准文档 | 含引用 | P1 |

---

## 10. S8: Schema & Security

| TC-ID | 场景 | 优先级 |
|-------|------|:---:|
| S8-D2-01 | YAML 使用 safe_load（非 yaml.load） | P0 |
| S8-D2-02 | subprocess 参数列表（非 shell=True） | P0 |
| S8-D2-03 | appeal.py 证据门槛 ≥20 字符 | P0 |
| S8-D2-04 | defer.py 理由门槛 ≥10 字符 | P1 |

---

## 11. 发布门禁评估

按标准 §10 发布门禁公式：

```
BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
```

| 门禁项 | 要求 | D2 实测 | 状态 |
|--------|:---:|:---:|:---:|
| BLOCKER = 0 | 0 | **0** | ✅ |
| MAJOR ≤ 3 | ≤ 3 | **1（A2 同步问题）** | ✅ |
| 安全漏洞 = 0 | 0 | **0** | ✅ |
| 无未裁定的申诉 | 0 | **0** | ✅ |

**结论**：门禁通过。1 项 MAJOR（A2 STATE_PREFIXES 与 YAML 不同步）已验证架构发现，计划 P0-16 修复。

---

## 附录 A: 与 D1 方案对比

| 维度 | D1 v1.0 | D2 v2.0 |
|------|:---:|:---:|
| 总测试数 | 47 | 52 |
| P0 用例 | 16 | 28 |
| P1 用例 | 20 | 20 |
| P2 用例 | 11 | 4 |
| 移除（产品裁定） | — | A1-01~A1-10 |
| 新增（架构补充） | — | 19 tests |
| 新增（研发补充） | — | 4 tests |
| 新增（模块覆盖） | — | 10 tests |
| 新增（安全审查） | — | 4 tests |
| 执行结果 | 未执行 | 51 PASS / 1 FAIL |

---

## 附录 B: 修复建议

| 发现 | 级别 | 修复方案 | 文件 | 预计成本 |
|------|:---:|------|------|:---:|
| A2: STATE_PREFIXES 不同步 | MAJOR | `_build_state_prefixes()` 从 YAML 自动生成 | kanban_helpers.py | ~15 lines |
| A4: assignee 硬编码 | MINOR | 从 YAML `roles.dev[0]` 或新字段读取 | product_rule.py L93 | ~3 lines |
| A5: has_ruling 纯文本前缀 | MINOR | 结构化 metadata 块 + backward compat | kanban_helpers.py | ~20 lines |
