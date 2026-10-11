# Roundtable 架构裁定：P0-01/07/10

> 角色：高见远（架构师）
> 日期：2026-07-08
> 前置：产品裁定（许清楚，同日）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 1. P0-01 F2a：audit-cron.sh `${HOME}` 数据分裂 — 修复方案技术可行性

### 1.1 缺陷确认

**数据分裂路径已验证**（TC-P01-03）：

```
audit-cron.sh (HOME=/tmp) → 写入 /tmp/.hermes/.../terminal_commands.db
audit-import.sh            → 读取 /root/.hermes/.../terminal_commands.db
结果：import 读取的 DB 为空 → cron 时段审计数据不可见
```

**受影响文件**（`${HOME}` 出现位置）：

| 文件 | 行号 | 变量 | 级别 | 用途 |
|------|------|------|:---:|------|
| `orchestrator/scripts/audit-cron.sh` | L6 | `AUDIT_DIR` | **MAJOR** | enricher 模式，cron 执行 |
| `orchestrator/scripts/audit-cron.sh` | L9 | `SESSION_DB` | **MAJOR** | 同上 |
| `/root/.hermes/scripts/audit-cron.sh` | L6 | `AUDIT_DIR` | **MAJOR** | scanner 模式，不同脚本！ |
| `/root/.hermes/scripts/audit-cron.sh` | L9 | `SESSION_DB` | **MAJOR** | 同上 |
| `orchestrator/scripts/terminal-audit.sh` | L6 | `AUDIT_DIR` | MINOR | source 执行，HOME=/root 概率高 |
| `orchestrator/scripts/terminal-audit-env.sh` | L6 | `AUDIT_DIR` | MINOR | BASH_ENV 模式，HOME=/root 概率高 |

**重要发现**：两个 `audit-cron.sh` 是**不同脚本**：
- orchestrator 版（66行）：enricher 模式——retroactively 填充 exit_code
- 全局版（45行）：scanner 模式——从 session DB 扫描新命令
- 同名但功能不同，需分别修复

### 1.2 修复方案技术评估

**方案**：`${HOME}` → `/root`，直接硬编码。

**对照**：audit-import.sh L7 已使用 `AUDIT_DIR="/root/.hermes/profiles/orchestrator/audit"`，验证通过（TC-P01-01 PASS）。

**技术可行性**：✅ 零风险
- 路径硬编码不依赖环境变量，消除整个 `${HOME}` 攻击面
- 与 audit-import.sh 修复模式完全一致
- 无级联影响——AUDIT_DIR 和 SESSION_DB 仅在本脚本内使用
- 不影响 `terminal-audit.sh` 和 `terminal-audit-env.sh`（它们通过 source/BASH_ENV 执行，HOME 展开发生在调用 shell 中）

**修复范围建议**：修复全部 6 处 `${HOME}`（2 个 audit-cron.sh 副本 × 2 行 + 2 个辅助脚本 × 1 行），一次性消除整个审计子系统的环境变量依赖风险。

**工作量**：
- F2a（MAJOR）：audit-cron.sh × 2 副本，每副本 2 行 → 共 4 行，约 0.1h
- F2b/F2c（MINOR）：terminal-audit.sh + terminal-audit-env.sh，各 1 行 → 建议一并修复，总工作量仍 < 0.2h

### 1.3 架构教训

**设计原则**：cron 执行的脚本不得依赖环境变量来确定关键路径。系统 cron 的 HOME 通常为 `/` 或 `/var/spool/cron`，不可假设为 `/root`。

**架构建议**（非必需，下版本考虑）：审计子系统引入配置文件驱动的路径管理（如 `HERMES_AUDIT_DIR` 环境变量 + fallback 到 `/root/.hermes/...`），统一所有审计脚本的路径解析逻辑。

### 1.4 裁定

| 项 | 结论 |
|----|------|
| 修复技术可行性 | ✅ **可行**，零风险 |
| 修复范围 | F2a 必须修复；建议 F2b/F2c 一并修复 |
| 数据分裂根因 | `${HOME}` 在 cron 环境中展开为非 `/root` 值 |
| 长期建议 | 审计脚本统一使用绝对路径或配置驱动的路径管理 |

**研发待确认**：修复 4 个文件共 6 行（或至少修复 2 个 audit-cron.sh 共 4 行）。

---

## 2. P0-07 F1：全局 MEMORY.md 恢复决策

### 2.1 依赖分析

**结论：无 profile 依赖全局 MEMORY.md。**

逐 profile 检查：

| Profile | 类型 | MEMORY.md | SOUL.md | 依赖全局 memory？ |
|---------|------|:---:|:---:|:---:|
| gateway-eng | 非 game | ❌ 无 | 默认 | ❌ |
| infomanager | 非 game | ❌ 无 | 详细（InfoManager 概述） | ❌ |
| orchestrator | 非 game | ❌ 无 | 详细（架构概述） | ❌ |
| tag-system | 非 game | ❌ 无 | 默认 | ❌ |
| vault-writer | 非 game | ❌ 无 | 默认 | ❌ |
| verifier | 非 game | ❌ 无 | 详细（VA 身份） | ❌ |
| game-architect | game | ✅ 513B | 详细 | ❌ |
| game-artist | game | ✅ 513B | 详细 | ❌ |
| game-client | game | ✅ 513B | 详细 | ❌ |
| game-director | game | ✅ 513B | 详细 | ❌ |
| game-engine | game | ✅ 513B | 详细 | ❌ |
| game-qa | game | ✅ 604B | 详细 | ❌ |

**零引用**：`grep -r` 在所有非 game profile 中搜索 `global.memory` 及 `/root/.hermes/config/memories` 路径，结果为空。

### 2.2 备份内容覆盖分析

备份（`/workspace/backup-repo/config/memories/MEMORY.md`，1,948 bytes）含 3 部分：

| 内容 | 当前覆盖情况 | 是否缺失？ |
|------|-------------|:---:|
| Claude Code proxy 配置 | 已复制到 6 个 game profile MEMORY.md（各 513B） | ❌ 不缺失 |
| Game dev Kanban 团队概述 | 已在各 game profile SOUL.md 中编码 | ❌ 不缺失 |
| InfoManager 架构概述 | 已在 infomanager SOUL.md + skills/SKILL.md 中编码 | ❌ 不缺失 |

### 2.3 架构评估

全局 MEMORY.md（`/root/.hermes/config/memories/`）是 Hermes 的**全局记忆机制**——memories 写入该路径会注入所有 profile 的 system prompt。该机制的设计意图是跨 profile 共享上下文。

但在当前架构中，此机制已被**三层替代方案**覆盖：
1. **SOUL.md**：role-specific 身份和职责（per-profile）
2. **MEMORY.md**：per-profile durable facts（per-profile）
3. **Kanban 注入**：task-specific 上下文（per-task）

恢复全局 MEMORY.md 会引入**架构歧义**：
- 新的 agent session 应该信任 SOUL.md 还是全局 memory？
- 如果全局 memory 中的 proxy 配置与 per-profile MEMORY.md 冲突，哪个优先？
- 全局 memory 的更新需要跨所有 profile 保持一致性，增加运维负担

### 2.4 裁定

| 项 | 结论 |
|----|------|
| 是否有 profile 依赖全局 MEMORY.md？ | ❌ **无** |
| 备份内容是否有未被覆盖的关键信息？ | ❌ **全部已覆盖** |
| 恢复是否改善系统行为？ | ❌ **不会**——三层替代方案已满足需求 |
| 恢复是否引入架构风险？ | ⚠️ **是**——引入歧义源 + 运维负担 |

**最终决策：不恢复全局 MEMORY.md。**

备份保留于 `/workspace/backup-repo/config/memories/MEMORY.md` 作为架构文档参考，但不再注入 system prompt。

---

## 3. P0-10 TC-DATA-07：保留策略架构影响

### 3.1 当前状态

```yaml
curator:
  interval_hours: 168      # 每周运行
  archive_after_days: 90   # 归档窗口
  backup:
    keep: 13               # 13 × 7 = 91 天覆盖
```

- 覆盖率：91/90 = **101%** ✅
- TC-DATA-07：**PASS**（已验证）

### 3.2 架构评估

**原问题**（keep:5 → 35天 < 90天）：已通过 `keep:13` 修复。修复方案正确：
- 每周 curator 运行产生 1 个快照
- 13 周快照 = 91 天覆盖 > 90 天归档窗口
- 归档窗口内的技能可从快照恢复

**边际风险**：松驰余量仅 1 天。
- 如果一次 curator 运行因系统停机延迟超过 24h，最旧快照可能超出归档窗口
- 实际风险：curator 每周运行一次，系统停机 > 24h 的概率低
- 影响：即使触发，也只是快照覆盖暂时 < 90 天，不导致数据丢失

**优化建议**（P2，不阻塞）：
- `keep: 14` 可提供 14 × 7 = 98 天覆盖，一周松驰余量
- 边际成本：多保留一个 50-70MB tar.gz 快照（磁盘开销可忽略）

### 3.3 裁定

| 项 | 结论 |
|----|------|
| 保留策略是否匹配归档窗口？ | ✅ **已匹配**（91 > 90） |
| 是否有数据丢失风险？ | ❌ **无**——配置已修复，TC-DATA-07 PASS |
| 架构建议 | keep:14（P2，非阻塞，增加一周余量） |
| 是否需要架构变更？ | ❌ **不需要**——curator 机制本身无缺陷 |

---

## 4. 架构裁定总结

| # | 发现 | 级别 | 架构裁决 | 研发行动 |
|----|------|:---:|------|------|
| 1 | P0-01 F2a audit-cron.sh | MAJOR | ✅ 修复可行，零风险 | 4 文件 6 行 `${HOME}`→`/root` |
| 2 | P0-07 F1 全局 MEMORY.md | MINOR | ❌ 不恢复 | 无（备份保留为文档） |
| 3 | P0-10 TC-DATA-07 保留策略 | PASS | ✅ 已修复，架构无问题 | keep:14（P2 优化，可选） |

**发布门禁**：无 BLOCKER，无安全漏洞。架构端同意产品裁定：
- P0-01 F2a 建议当前窗口修复后发版
- P0-07 F1 无需恢复
- P0-10 TC-DATA-07 架构无影响

### 研发待确认项

1. **P0-01 F2a**：确认修复范围——至少修复 2 个 `audit-cron.sh` 副本（4 行），建议一并修复 `terminal-audit.sh` + `terminal-audit-env.sh`（2 行）
2. **P0-07 F1**：确认不执行恢复操作
3. **P0-10**：keep:14 优化建议（非阻塞，P2 排队）

---

> **架构裁定完成。移交研发（寇豆码）确认修复方案，QA 做最终回应。**
