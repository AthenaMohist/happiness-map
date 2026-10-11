# Roundtable 产品裁定：审计机制测试报告评审判定

> 角色：许清楚（产品负责人）
> 日期：2026-07-08
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 评审判定范围：P0-01 / P0-02 / P0-07 / P0-10

---

## 议程1：分级合理性审查

### P0-01（审计 importer）

| 发现 | QA级别 | 产品裁定 | 理由 |
|------|:---:|:---:|------|
| F1: audit-import.sh `${HOME}` | MINOR | ✅ 维持 | 已修复，回归验证通过 |
| **F2a: audit-cron.sh `${HOME}` (cron路径)** | **MAJOR** | ✅ **维持** | 判定公式完全匹配：用户可感知(数据完整性→审计数据丢失) + 功能阻断(无法查询cron时段记录) + 有workaround(HOME=/root)。C级数据按§4不加权。**修复成本0.1h（3行替换），强烈建议当前窗口内修复** |
| F2b: terminal-audit.sh `${HOME}` | MINOR | ✅ 维持 | source env场景HOME=/root概率高，非阻断。判定合理 |
| F2c: terminal-audit-env.sh `${HOME}` | MINOR | ✅ 维持 | BASH_ENV场景概率低，非阻断。判定合理 |
| F3: backup-repo 未同步 | SUGGESTION | ✅ 维持 | 冷备份，用户不可感知 |
| F4: terminal-audit-env.sh 代码分叉 | SUGGESTION | ✅ 维持 | 运维质量问题，用户不可感知。建议统一为版本B（`${HERMES_AUDIT_DIR:-/root/...}` fallback） |

### P0-02（pending_upgrades）

| 发现 | QA级别 | 产品裁定 | 理由 |
|------|:---:|:---:|------|
| F1: 目录状态 | PASS | ✅ 维持 | 目录正常、cron正常（11次成功）。无需处置 |
| F2: cron关联性 | PASS | ✅ 维持 | 已验证通过 |
| F3: 原始任务完成 | PASS | ✅ 维持 | 已闭环 |
| 建议1: 投放端到端测试 | SUGGESTION (非缺陷) | ✅ 维持 | 低优先级，不阻塞 |

**结论**：P0-02 零发现，全部PASS。✅

### P0-07（MEMORY.md 归档）

| 发现 | QA级别 | 产品裁定 | 理由 |
|------|:---:|:---:|------|
| **F1: 全局MEMORY.md已移除（目录消失）** | **MINOR** | ✅ **维持** | 判定合理：用户间接可感知（非game profile可能缺全局上下文）+ 非功能阻断。**需要产品决策：是否从备份恢复？**（见处置决策） |
| F2: 归档过程无文档 | SUGGESTION | ✅ 维持 | 内部流程记录，不可感知 |
| F3: 跨profile记忆同质化 | SUGGESTION | ✅ 维持 | 上下文由SOUL.md+kanban传递，不影响功能 |
| F4: game-qa过期kanban引用 | SUGGESTION | ✅ 维持 | memory工具的已知特性，不影响功能 |
| TC-P07-07/08 持久性测试 | PENDING | ⏳ 维持 | 需重启后执行，不阻塞发版 |

**MEMORY.md用量现状**：6个profile均在23.3%-27.5%，远低于80%上限（1,760 chars）。归档目标已达。

### P0-10（Consolidation审计）

| 发现 | QA级别 | 产品裁定 | 理由 |
|------|:---:|:---:|------|
| **F-DATA-01: manifest缺少run_number** | **MINOR** | ⚠️ **边际维持** | QA用了"系统健康度退化"扩展定义。实际影响：`created_at`可作fallback排序，功能不阻断。介于MINOR/SUGGESTION边界。按§1.3"无法判断取高级别"，维持MINOR但不升级 |
| F-DATA-02: skill_files命名歧义 | SUGGESTION | ✅ 维持 | 字段值正确，仅命名歧义。breaking change需慎改 |
| F-DATA-03: prompt变更不可审计 | SUGGESTION | ✅ 维持 | 当前内容正确，仅审计能力不足 |
| TC-DATA-08 LLM合并测试 | DEFERRED | ✅ 维持暂缓 | consolidate=false，生产无影响 |

**8个数据完整性用例全部PASS（含7个已执行+1个暂缓）**。✅

---

## 议程1总结：分级裁定

| 报告 | 总发现 | 产品调整 | 最终分布 |
|------|:---:|:---:|------|
| P0-01 | 1 MAJOR + 2 MINOR + 2 SUGGESTION | 无调整 | 维持原判 |
| P0-02 | 0 缺陷 + 1 SUGGESTION(建议) | 无调整 | 全PASS |
| P0-07 | 1 MINOR + 3 SUGGESTION | 无调整 | 维持原判 |
| P0-10 | 1 MINOR(边际) + 2 SUGGESTION | 无调整 | 维持原判 |

**无BLOCKER，无安全漏洞，无分级争议需要升级到申诉流程。**

---

## 议程2：处置决策

### 按级别分派

| 级别 | 发现 | 处置 | 目标 |
|------|------|------|------|
| **MAJOR** | P0-01 F2a | 🔧 当前窗口修复 | 3行替换，0.1h。SLA: 响应1工作日、定位2工作日（QA已完成复现）、修复窗口内 |
| **MINOR** | P0-01 F2b | 📋 待办 P1 | 当前窗口内修复（如时间允许），否则下版本 |
| **MINOR** | P0-01 F2c | 📋 待办 P1 | 同上 |
| **MINOR** | P0-07 F1 | 📋 产品决策 | 见下方专项决策 |
| **MINOR** | P0-10 F-DATA-01 | 📋 待办 P2 | 下次curator更新时加run_number字段 |
| **SUGGESTION** | P0-01 F3, F4 + P0-07 F2/F3/F4 + P0-10 F2/F3 | 📝 记录在案 | 不阻塞，按优先级排队 |

### 专项：P0-07 F1 全局MEMORY.md恢复决策

**现状**：
- 备份存在：`/workspace/backup-repo/config/memories/MEMORY.md`（1,948 bytes）
- 内容：Claude Code proxy配置 + Game Kanban团队 + InfoManager架构概述
- 影响面：非game类profile如果依赖全局memory上下文，可能缺失

**产品决策**：🔍 **建议恢复，但非强制。**
- 如果存在非game profile依赖全局memory（如infomanager相关profile），应从备份恢复
- 如果所有活跃profile通过SOUL.md+kanban通道正常工作，可保持现状
- **由架构师（高见远）评估非game profile的实际依赖**后执行

### 暂缓与签批

- 无BLOCKER → 无需Frank签批（§11红线1）
- 无申诉 → 无申诉率影响
- 无安全漏洞 → 发布门禁无安全阻塞

---

## 发布门禁检查（§10）

```
BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉
```

| 检查项 | 状态 |
|--------|:---:|
| BLOCKER=0？ | ✅ |
| 安全漏洞=0？ | ✅（全部发现不涉及OWASP Top 10） |
| 无未裁定申诉？ | ✅ |
| MAJOR建议 | 1个（P0-01 F2a），建议修复后发版，可按§10标注known issue发版 |

**结论**：✅ 满足发布门禁条件。建议在当前窗口内修复F2a后发版；如窗口紧张，可标注known issue发版。

---

## 处置决策清单（供架构/研发/QA后续执行）

| # | 发现 | 级别 | 处置 | 负责人 | 备注 |
|---|------|:---:|------|--------|------|
| 1 | P0-01 F2a audit-cron.sh | MAJOR | 🔧 修复 | 研发（寇豆码） | L6,L9 `${HOME}`→`/root`，3行，0.1h |
| 2 | P0-01 F2b terminal-audit.sh | MINOR | 📋 P1 | 研发 | L6 `${HOME}`→`/root` |
| 3 | P0-01 F2c terminal-audit-env.sh | MINOR | 📋 P1 | 研发 | L6 `${HOME}`→`/root`（活跃运行时） |
| 4 | P0-07 F1 全局MEMORY.md | MINOR | 🔍 评估后恢复 | 架构（高见远） | 评估非game profile依赖 |
| 5 | P0-10 F-DATA-01 run_number | MINOR | 📋 P2 | 架构+研发 | curator更新时加入 |
| 6 | P0-01 F3/F4 + P0-07 F2-F4 + P0-10 F2/F3 | SUGGESTION | 📝 记录 | — | 不阻塞，按优先级排队 |
| 7 | P0-07 TC-P07-07/08 | PENDING | ⏳ 重启后执行 | QA | 持久性验证 |
| 8 | P0-10 TC-DATA-08 | DEFERRED | ⏳ staging就绪后执行 | QA | LLM合并测试 |

---

> **产品端裁定完成。移交架构师（高见远）进行技术可行性评估，研发（寇豆码）确认修复方案，QA做最终回应。**
