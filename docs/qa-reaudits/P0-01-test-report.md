# P0-01 测试报告：审计 importer $HOME → /root 重审

> 版本：v1.0 | 状态：Complete
> 测试执行日期：2026-07-08
> 测试执行人：game-qa（QA）
> 测试方案依据：`docs/qa-reaudits/P0-01-test-plan.md` v1.0
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 1. 测试执行摘要

| 指标 | 值 |
|------|:---:|
| 总测试用例 | 6（TC-P01-01 ~ TC-P01-06） |
| 执行 | 4 |
| 跳过（需前置修复） | 2（TC-P01-02, TC-P01-06） |
| 通过 | 2（TC-P01-01, TC-P01-04） |
| 失败 | 2（TC-P01-03, TC-P01-05） |
| 阻塞 (BLOCKER) | 0 |
| MAJOR | 1（F2a — 已确认未修复） |
| MINOR | 2（F2b, F2c — 已确认未修复） |
| SUGGESTION | 2（F3, F4 — backup-repo + 代码分叉） |

---

## 2. 逐用例测试结果

### 2.1 TC-P01-01：audit-import.sh 路径硬编码验证（F1 回归）

| 项目 | 内容 |
|------|------|
| **状态** | ✅ **PASS** |
| **覆盖发现** | F1（audit-import.sh `${HOME}` → `/root`） |
| **执行命令** | `HOME=/tmp bash /root/.hermes/profiles/orchestrator/scripts/audit-import.sh` |
| **预期** | HOME 不干扰审计路径；`/tmp/.hermes/...` 不被创建 |
| **实际** | exit_code=0；无 `/tmp/.hermes/` 路径创建；`/root/.hermes/.../terminal_commands.db` 正常访问 |
| **证据** | L7 使用 `AUDIT_DIR="/root/.hermes/profiles/orchestrator/audit"`（硬编码），HOME 变量不会改变路径 |

**判定公式对照**（重审确认）：
```
用户可感知（数据完整性） + 非功能阻断 + C级数据 → MINOR
→ 原始级别不变。修复有效，无回归。
```

---

### 2.2 TC-P01-02：audit-cron.sh 路径硬编码验证（修复后）

| 项目 | 内容 |
|------|------|
| **状态** | ⏭️ **SKIP** |
| **原因** | 此用例验证**修复后**行为。TC-P01-03 已确认当前代码存在缺陷，TC-P01-02 需在研发修复 audit-cron.sh 后重新执行。 |

---

### 2.3 TC-P01-03：audit-cron.sh 修复前缺陷复现（F2a）

| 项目 | 内容 |
|------|------|
| **状态** | ❌ **FAIL — 缺陷已确认** |
| **覆盖发现** | F2a（audit-cron.sh `${HOME}` 未修复） |
| **执行命令** | `HOME=/tmp bash /root/.hermes/profiles/orchestrator/scripts/audit-cron.sh` |
| **预期（缺陷行为）** | `/tmp/.hermes/profiles/orchestrator/audit/terminal_commands.db` 被创建 | `/root/.hermes/.../audit/.last_scan_id` 未被更新 |
| **实际** | ✅ 缺陷行为完全符合预期 |
| **证据** | `/tmp/.hermes/profiles/orchestrator/audit/terminal_commands.db` 已创建（20KB） | `/tmp/.hermes/.../audit/.last_scan_id` 已创建（空文件） | `/root/.hermes/.../audit/.last_scan_id` **不存在** |

**数据分裂路径确认**：
```
audit-cron.sh (HOME=/tmp) → 写入 /tmp/.hermes/.../terminal_commands.db
audit-import.sh            → 读取 /root/.hermes/.../terminal_commands.db
结果：import 读取的 DB 为空 → 审计数据不可见
```

**判定公式对照**（按标准 §1.2）：
```
前置检查: 安全漏洞？→ 否
步骤 E: 用户可感知（数据完整性）
     → 是。cron 环境中数据写入错误路径，审计数据丢失
步骤 F: 功能阻断？
     → 是。用户无法查询到 cron 时段的终端审计记录
步骤 W: workaround？
     → 是。cron entry 中显式 HOME=/root 可绕过
步骤 D: 数据敏感度？
     → C 级（内部运维数据），按 §4 不加权

结论: 用户可感知 + 功能阻断 + 有 workaround → MAJOR ✓
```

---

### 2.4 TC-P01-04：terminal-audit.sh source 环境验证（F2b）

| 项目 | 内容 |
|------|------|
| **状态** | ⚠️ **CONDITIONAL PASS** |
| **覆盖发现** | F2b（terminal-audit.sh `${HOME}`） |
| **测试方法** | 静态分析（source 执行被交互 shell 限制阻止） |
| **正常环境** | HOME=/root 时，`AUDIT_DIR` 展开为 `/root/.hermes/.../audit` → 正确 |
| **风险环境** | HOME≠/root 时（如 cron、特殊容器环境），路径错误 |
| **评估** | source 脚本在正常交互 shell 中 HOME=/root 概率高 → PASS in normal env。但 `${HOME}` 模式在非标准环境中与其他脚本存在相同风险。F2b 级别维持 **MINOR**。 |

**注意**：由于 `source` 执行涉及交互 shell 的 DEBUG trap 安装，在非交互式测试环境中无法直接 source。此项为静态验证。

---

### 2.5 TC-P01-05：backup-repo 同步检查（F3）

| 项目 | 内容 |
|------|------|
| **状态** | ❌ **FAIL — 未同步** |
| **覆盖发现** | F3（backup-repo audit-cron.sh 未同步修复） |

**逐文件检查结果**：

| # | 脚本路径 | `${HOME}` 行 | 状态 |
|---|---------|:---:|:---:|
| 1 | `/workspace/backup-repo/config/scripts/audit-cron.sh` | L6, L9 | ❌ 未修复 |
| 2 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/audit-cron.sh` | L6, L9 | ❌ 未修复 |
| 3 | `/workspace/backup-repo/config/scripts/audit-import.sh` | L7 使用 `/root` | ✅ 已修复 |
| 4 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/audit-import.sh` | L7 使用 `/root` | ✅ 已修复 |
| 5 | `/workspace/backup-repo/config/scripts/terminal-audit-env.sh` | L17: `${HERMES_AUDIT_DIR:-/root/...}` | ✅ 已安全（不同实现） |
| 6 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/terminal-audit-env.sh` | L6 `${HOME}` | ❌ 未修复 |
| 7 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/terminal-audit.sh` | L6 `${HOME}` | ❌ 未修复 |

**判定公式对照**：
```
用户不可感知（backup-repo 为冷备份）+ 非功能阻断 → SUGGESTION
〉 如 backup-repo 曾作为恢复源，建议升级为 MINOR
```

---

### 2.6 TC-P01-06：审计数据完整性端到端验证

| 项目 | 内容 |
|------|------|
| **状态** | ⏭️ **SKIP** |
| **原因** | E2E 验证需要在所有审计脚本修复后执行。当前 audit-cron.sh 仍存在 `${HOME}` 缺陷（F2a），全链路数据一致性无法验证。 |
| **预期修复后重测** | 1. audit-cron.sh 写入 `/root/.hermes/.../` → 2. audit-import.sh 从 `/root/.hermes/.../` 读取 → 3. 查询 DB 应返回 > 0 条命令 |

---

## 3. 发现汇总（按标准 §1.2 判定）

| 发现 | 级别 | 状态 | 涉及文件数 | 判定依据 |
|------|:---:|:---:|:---:|---------|
| F1: audit-import.sh `${HOME}` | **MINOR** | ✅ 已修复 | 2（L7 硬编码） | 用户可感知 + 非阻断 + C级 |
| F2a: audit-cron.sh `${HOME}`（cron 路径） | **MAJOR** | ❌ 未修复 | 1 活跃 + 2 backup | 用户可感知 + 阻断 + 有 workaround |
| F2b: terminal-audit.sh `${HOME}` | **MINOR** | ❌ 未修复 | 1 活跃 + 1 backup | 用户可感知 + 非阻断（source env）+ C级 |
| F2c: terminal-audit-env.sh `${HOME}` | **MINOR** | ❌ 未修复（2/4 副本） | 2 | 用户可感知 + 非阻断（BASH_ENV）+ C级 |
| F3: backup-repo audit-cron.sh 未同步 | **SUGGESTION** | ❌ 未修复 | 2 | 用户不可感知（冷备份） |
| **F4: terminal-audit-env.sh 代码分叉** | **SUGGESTION** | 新发现 | 4 个副本 | 用户不可感知（运维质量） |

---

## 4. 新发现 F4：terminal-audit-env.sh 代码分叉

### 4.1 问题描述

`terminal-audit-env.sh` 在同一代码库中存在 **4 个副本**，使用 **2 种不同实现**：

| 副本位置 | 路径变量实现 | HOME 安全？ |
|----------|-------------|:---:|
| 活跃运行时 | L6: `AUDIT_DIR="${HOME}/.hermes/..."` | ❌ |
| backup-repo config/scripts/ | L17: `LOG="${HERMES_AUDIT_DIR:-/root/.hermes/...}"` | ✅ |
| backup-repo config/profiles/orchestrator/scripts/ | L6: `AUDIT_DIR="${HOME}/.hermes/..."` | ❌ |
| backup-repo skills/hermes-admin/command-audit/scripts/ | L17: `LOG="${HERMES_AUDIT_DIR:-/root/.hermes/...}"` | ✅ |

**关键差异**：
- 版本 A（2 个副本，不安全）：写入 SQLite，使用 `${HOME}`
- 版本 B（2 个副本，安全）：写入 flat log，使用 `${HERMES_AUDIT_DIR:-/root/...}` fallback

两个版本的核心架构不同（SQLite vs flat log），说明代码在扩散过程中出现了分叉，且修复未全局应用。

### 4.2 判定

```
用户不可感知 + 非安全/非数据完整性 → SUGGESTION
```

> 但代码分叉是技术债务信号：无法确定哪个版本是"最新/正确"的。

---

## 5. §8 SLA 对照

### 5.1 原始修复 F1 SLA

| 指标 | 标准 | 实际 | 状态 |
|------|------|------|:---:|
| 响应时限 | MINOR: 2 工作日 | 同日修复 | ✅ 远超 |
| 定位时限 | MINOR: 不要求 | — | — |
| 方案时限 | MINOR: 不限 | — | — |

### 5.2 新发现 F2a SLA（MAJOR）

| 指标 | 标准 | 当前状态 |
|------|------|-----|
| 响应时限 | 1 工作日 | ⏳ 待研发确认 |
| 定位时限 | 2 工作日 | ✅ QA 已完成复现 |
| 方案时限 | 当前版本窗口内 | 预估 0.1h（3 行替换） |

---

## 6. §6 论证流程合规检查

### 6.1 原始 F1 流程

| 环节 | 标准 | 实际 | 合规？ |
|------|------|------|:---:|
| QA 发现 → 级别标注 | 按判定公式 | MINOR | ✅ |
| 研发评估 | 通过/驳回/暂缓 | 已修复（视为通过） | ✅ |
| Grandfather clause | 新标准前完成 | 适用 | ✅ |

### 6.2 新发现 F2a 流程

F2a 为新发现，触发新论证流程：

```
QA 发现 F2a (MAJOR) → 研发需评估：
  ├── 通过 → 扩展修复 audit-cron.sh + terminal-audit.sh + terminal-audit-env.sh
  ├── 驳回 → 需附理由（如："cron 已设置 HOME=/root，不会出现路径错误"）
  └── 暂缓 → 目标版本 + 标注 known issue
```

---

## 7. 发布门禁影响（按标准 §10）

```
BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉
```

| 检查项 | 状态 |
|--------|:---:|
| BLOCKER=0？ | ✅ 无 BLOCKER |
| 安全漏洞=0？ | ✅ 非安全漏洞 |
| 无未裁定申诉？ | ✅ 无申诉 |
| MAJOR 建议 | 1 个 MAJOR (F2a)，建议修复后发版 |

**结论**：满足发布门禁。F2a 为 MAJOR 级，可按 §10 发版但需标注 known issue："cron 环境中 HOME≠/root 时，audit-cron.sh 的审计数据写入路径与 importer 不一致"。

---

## 8. 修复建议更新

原测试方案 §6 的修复建议基于测试结果更新如下：

### 8.1 最小修复集（必须，覆盖 MAJOR F2a）

```bash
# 文件：/root/.hermes/profiles/orchestrator/scripts/audit-cron.sh
# L6: AUDIT_DIR="${HOME}/.hermes/profiles/orchestrator/audit"
#  →   AUDIT_DIR="/root/.hermes/profiles/orchestrator/audit"
# L9: SESSION_DB="${HOME}/.hermes/profiles/orchestrator/state.db"
#  →   SESSION_DB="/root/.hermes/profiles/orchestrator/state.db"
```

### 8.2 完整修复集（覆盖所有发现）

| # | 文件 | 变更 | 优先级 | 级别 |
|---|------|------|:---:|:---:|
| 1 | `/root/.hermes/profiles/orchestrator/scripts/audit-cron.sh` | `${HOME}` → `/root` (L6, L9) | P0 | MAJOR |
| 2 | `/root/.hermes/profiles/orchestrator/scripts/terminal-audit.sh` | `${HOME}` → `/root` (L6) | P1 | MINOR |
| 3 | `/root/.hermes/profiles/orchestrator/scripts/terminal-audit-env.sh` | `${HOME}` → `/root` (L6) | P1 | MINOR |
| 4 | `/workspace/backup-repo/config/scripts/audit-cron.sh` | 同步修复 | P2 | SUGGESTION |
| 5 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/audit-cron.sh` | 同步修复 | P2 | SUGGESTION |
| 6 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/terminal-audit.sh` | 同步修复 | P2 | SUGGESTION |
| 7 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/terminal-audit-env.sh` | 同步修复 | P2 | SUGGESTION |

### 8.3 建议（非阻塞）

- 解决 terminal-audit-env.sh 代码分叉：统一为一种实现（建议版本 B，使用 `${HERMES_AUDIT_DIR:-/root/...}` fallback 更灵活）
- 在 cron entry 中显式设置 `HOME=/root` 作为防御层
- 在 audit-cron.sh 开头添加 `HOME=/root` 作为 defense-in-depth

---

## 9. 测试方案覆盖度评估

| 维度 | 覆盖率 |
|------|:---:|
| 发现的覆盖（F1/F2a/F2b/F2c/F3） | 5/5（100%） |
| 脚本文件覆盖（去重后 5 个独立脚本） | 5/5（100%） |
| 路径覆盖（活跃运行时 + backup-repo） | 8/8（100%） |
| E2E 测试 | 0/1（需前置修复） |
| 新发现（F4 代码分叉） | 超出方案范围 |

---

## 10. 附录

### 10.1 审计脚本完整状态矩阵

| # | 脚本 | 路径 | HOME 引用 | 状态 | 发现 | 数据分裂风险 |
|---|------|------|:---:|:---:|------|:---:|
| 1 | audit-import.sh | 活跃运行时 | L7 `/root` | ✅ FIXED | F1 | — |
| 2 | audit-import.sh | backup-repo config/scripts/ | L7 `/root` | ✅ FIXED | F1 | — |
| 3 | audit-import.sh | backup-repo profiles/.../scripts/ | L7 `/root` | ✅ FIXED | F1 | — |
| 4 | audit-import.sh | backup-repo skills/hermes-admin/.../ | L7 `/root` | ✅ FIXED | F1 | — |
| 5 | **audit-cron.sh** | **活跃运行时** | **L6,L9 `${HOME}`** | ❌ BROKEN | F2a | **是（主要风险）** |
| 6 | audit-cron.sh | backup-repo config/scripts/ | L6,L9 `${HOME}` | ❌ BROKEN | F3 | 冷备份 |
| 7 | audit-cron.sh | backup-repo profiles/.../scripts/ | L6,L9 `${HOME}` | ❌ BROKEN | F3 | 冷备份 |
| 8 | terminal-audit.sh | 活跃运行时 | L6 `${HOME}` | ❌ BROKEN | F2b | 低（source env） |
| 9 | terminal-audit.sh | backup-repo profiles/.../scripts/ | L6 `${HOME}` | ❌ BROKEN | F2b | 冷备份 |
| 10 | terminal-audit-env.sh | 活跃运行时 | L6 `${HOME}` | ❌ BROKEN | F2c | 低（BASH_ENV） |
| 11 | terminal-audit-env.sh | backup-repo config/scripts/ | L17 `/root` fallback | ✅ SAFE | — | — |
| 12 | terminal-audit-env.sh | backup-repo profiles/.../scripts/ | L6 `${HOME}` | ❌ BROKEN | F2c | 冷备份 |
| 13 | terminal-audit-env.sh | backup-repo skills/hermes-admin/.../ | L17 `/root` fallback | ✅ SAFE | — | — |

> 总计 13 个文件副本，5 个独立脚本。已修复 4 个（仅 audit-import.sh），未修复 9 个。

### 10.2 标准引用速查

| 条款 | 主题 | 本报告使用 |
|------|------|---------|
| §1.2 | 判定公式 | F1/F2a/F2b/F2c/F3/F4 判定 |
| §1.3 | 判定原则 | "用户可感知"扩展定义（数据完整性） |
| §4 | 数据敏感度 | C 级不加权 |
| §6 | 论证流程 | grandfather clause + 新发现流程 |
| §8 | SLA | MINOR 2 工作日 / MAJOR 1+2 工作日 |
| §10 | 发布门禁 | BLOCKER=0 → 可发版 |

---

> **测试结论**：P0-01 原始修复（audit-import.sh）回归验证通过。但修复范围不完整——`audit-cron.sh` 等 3 个活跃运行时脚本仍使用 `${HOME}`，其中 audit-cron.sh 的数据分裂风险已通过缺陷复现（TC-P01-03）确认。新增 1 个 MAJOR 发现(F2a)和 1 个代码分叉发现(F4)。MAJOR 修复工作量极小（3 行替换，约 0.1h），建议当前窗口内修复。
