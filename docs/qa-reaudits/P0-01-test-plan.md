# P0-01 测试方案：审计 importer $HOME → /root 重审

> 版本：v1.0 | 状态：Draft — QA 重审
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 原始任务：t_3769db02 — 修复审计 importer：`$HOME` → `/root`（审计机制，0.1h）

---

## 1. 背景

### 1.1 原始问题

审计 log 导入脚本中存在路径硬编码问题：脚本使用 `${HOME}` 变量引用审计目录路径，但在 cron 环境中 `$HOME` 可能不展开为 `/root`，导致审计数据写入错误路径或无法写入。

### 1.2 原始修复（已执行）

将 `audit-import.sh` 中的 `${HOME}` 替换为硬编码 `/root`：

**修复前**（推测）：
```bash
AUDIT_DIR="${HOME}/.hermes/profiles/orchestrator/audit"
```

**修复后**（已在 backup-repo 中确认）：
```bash
AUDIT_DIR="/root/.hermes/profiles/orchestrator/audit"
```

- 修复文件：`audit-import.sh`（两处：`config/scripts/` 和 `config/profiles/orchestrator/scripts/`）
- 修复确认：`/workspace/backup-repo/config/` 下两个 `audit-import.sh` 均使用 `/root`

### 1.3 先前列重审摘要

在 `test-plan-p0-01-13.md`（L107-115）中，P0-01 已有 1 个发现：

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: ${HOME} 解析错误 | — | **MINOR** | — | 用户可感知(数据完整性) + C级数据 + 不影响核心任务 |

---

## 2. §1.2 判定公式对照 — 修复完整性重审

### 2.1 发现 F1：`audit-import.sh` ${HOME} 硬编码（原始发现）

**判定路径**（按标准 §1.2 五步判定）：

```
前置检查：
  └─ 安全漏洞？ → 否 → 进入正式判定

正式判定：
  步骤 E — 用户可感知（含扩展定义）？ 
     → 是。cron 环境中 HOME≠/root 时，审计数据写入错误路径，造成数据完整性受损。
  步骤 F — 功能阻断？
     → 否。审计数据仍会写入（只是路径不对），不影响核心业务功能运行。
  步骤 D — 数据敏感度？
     → C 级（内部运维数据）。按 §4 不加权。
  步骤 P — 性能退化？
     → 不适用。

结论：用户可感知 + 非功能阻断 + C级数据不加权 → **MINOR** ✓
（与先前重审一致）
```

**修复状态**：✅ `audit-import.sh` 已修复为硬编码 `/root`。

### 2.2 发现 F2：修复范围不完整 — 5 个脚本仍使用 `${HOME}`（新发现）

**逐文件检查结果**：

| # | 脚本路径 | 位置 | `${HOME}` 行号 | 风险场景 |
|---|---------|------|:---:|---------|
| 1 | `/root/.hermes/profiles/orchestrator/scripts/audit-cron.sh` | 活跃运行时 | L6, L9 | **cron 调用** — HOME 不可控 |
| 2 | `/root/.hermes/profiles/orchestrator/scripts/terminal-audit.sh` | 活跃运行时 | L6 | 被 source，HOME 通常正确（低风险） |
| 3 | `/root/.hermes/profiles/orchestrator/scripts/terminal-audit-env.sh` | 活跃运行时 | L6 | BASH_ENV 模式，HOME 通常正确（低风险） |
| 4 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/audit-cron.sh` | backup-repo | L6, L9 | **cron 调用** |
| 5 | `/workspace/backup-repo/config/scripts/audit-cron.sh` | backup-repo | L6 | **cron 调用** |

**判定路径**（对 `audit-cron.sh`，风险最高的 cron 脚本）：

```
前置检查：
  └─ 安全漏洞？ → 否 → 进入正式判定

正式判定：
  步骤 E — 用户可感知（扩展定义）？
     → 是。数据完整性受损：cron 环境中 HOME≠/root 时，
       audit-cron.sh 将命令记录写入 ${HOME}/.hermes/... 而非 /root/.hermes/...，
       导致 session DB 扫描的审计数据与 importer 期望的路径不一致。
  步骤 F — 功能阻断？
     → 是。当 HOME 未正确展开时，审计 DB 写入错误路径，
       用户（运维人员）无法查到终端命令审计记录。
  步骤 W — 有 workaround？
     → 是。可在 cron entry 中显式设置 `HOME=/root` 绕过。
  步骤 D — 数据敏感度？
     → C 级（内部运维数据）。按 §4 不加权。

结论：用户可感知 + 功能阻断 + 有 workaround + C级不加权 → **MAJOR**
```

**对 `terminal-audit.sh` 和 `terminal-audit-env.sh`**（source 模式，HOME 通常正常）：

```
结论：用户可感知（数据完整性）+ 非功能阻断 + C级不加权 → MINOR
（source 环境中 HOME 展开为 /root 概率高，风险较低但仍存在）
```

### 2.3 发现 F3：backup-repo 同步缺失（新发现）

`/workspace/backup-repo/config/` 下的两个 `audit-cron.sh` 未同步修复。

```
判定：用户不可感知（backup-repo 为冷备份）+ 非功能阻断 → SUGGESTION
```

> 但如 backup-repo 曾作为恢复源，则升级为 MINOR。

### 2.4 级别汇总

| 发现 | 级别 | 状态 | 判定依据 |
|------|:---:|:---:|---------|
| F1: audit-import.sh ${HOME} | **MINOR** | ✅ 已修复 | 用户可感知 + 非阻断 + C级 |
| F2a: audit-cron.sh ${HOME}（cron 路径） | **MAJOR** | ❌ 未修复 | 用户可感知 + 阻断 + 有 workaround |
| F2b: terminal-audit.sh ${HOME} | **MINOR** | ❌ 未修复 | 用户可感知 + 非阻断 + C级 |
| F2c: terminal-audit-env.sh ${HOME} | **MINOR** | ❌ 未修复 | 用户可感知 + 非阻断 + C级 |
| F3: backup-repo audit-cron.sh 未同步 | **SUGGESTION** | ❌ 未修复 | 用户不可感知 + 冷备份 |

---

## 3. §6 论证流程合规检查

### 3.1 原 QA 流程追溯

| 环节 | 标准要求 | 实际状态 | 合规？ |
|------|---------|---------|:---:|
| QA 发现 → 级别标注 | 按判定公式标注级别 | F1 标注为 MINOR | ✅ |
| 研发评估 | 通过/驳回/暂缓 | 修复执行（视为通过） | ✅ |
| 驳回理由 | 需附 by design / cannot repro / cost>benefit | 未驳回，不适用 | — |
| 降级通知 | 降级自动通知产品 | 无降级，不适用 | — |
| 申诉 | 需新证据 + 产品裁定 | 无申诉 | — |

**合规性评估**：grandfather clause 适用。P0-01 在新标准生效前已完成修复，无违反 §6 流程。

### 3.2 新发现 F2 的流程影响

F2 为新增发现（修复范围不完整），触发新论证流程：

```
QA 发现 F2 (MAJOR) → 研发评估：
  ├── 通过 → 扩展修复到 audit-cron.sh + terminal-audit.sh + terminal-audit-env.sh
  ├── 驳回 → 需附理由（如："cron 已设置 HOME=/root，不会出现路径错误"）
  └── 暂缓 → 目标版本 + 标注 known issue
```

### 3.3 关键风险

修复仅覆盖了 `audit-import.sh`（数据导入端），但未覆盖 `audit-cron.sh`（数据采集端）。当 cron 环境中 `$HOME` 指向非 `/root` 路径时：

- `audit-cron.sh` → 扫描 session DB 写入 `${HOME}/.hermes/profiles/orchestrator/audit/terminal_commands.db`
- `audit-import.sh` → 从 `/root/.hermes/profiles/orchestrator/audit/terminal_commands.db` 读取
- **结果**：importer 读取的 DB 是空/旧的，cron scanner 写入的 DB 在另一个路径 → **审计数据分裂**

---

## 4. §8 SLA 时效性评估

### 4.1 原始修复 SLA

| 指标 | 标准要求 | 实际 | 状态 |
|------|---------|------|:---:|
| 响应时限 | MINOR: 2 工作日 | 同日修复 | ✅ 远超 |
| 定位时限 | MINOR: 不要求 | — | — |
| 方案时限 | MINOR: 不限 | — | — |

**评估**：原始修复(0.1h 工时)远超 MINOR 时效要求。PASS。

### 4.2 新发现 F2a SLA（如确认 MAJOR）

| 指标 | 标准要求 | 说明 |
|------|---------|------|
| 响应时限 | 1 工作日 | 研发确认收到 issue 并给出初步判断 |
| 定位时限 | 2 工作日 | — |
| 方案时限 | 当前版本窗口内 | 修复即为 3 行路径替换 |

F2a (MAJOR) 修复工作量极小（`s/${HOME}/\/root/g`），预期 ≤ 0.1h。不阻塞当前发布窗口。

---

## 5. 测试用例

### 5.1 TC-P01-01：audit-import.sh 路径硬编码验证

```
Given: 审计目录 /root/.hermes/profiles/orchestrator/audit/ 存在
       审计 log terminal_audit.log 有内容
       audit-import.sh 中 AUDIT_DIR 使用硬编码 /root
When:  在设置 HOME=/tmp 的 cron 模拟环境中执行 audit-import.sh
       HOME=/tmp bash /path/to/audit-import.sh
Then:  sqlite3 /root/.hermes/profiles/orchestrator/audit/terminal_commands.db \
         "SELECT COUNT(*) FROM commands;" 返回 > 0
       /tmp/.hermes/profiles/orchestrator/audit/terminal_commands.db 不存在
       （即：HOME 变量不干扰审计路径）
```

### 5.2 TC-P01-02：audit-cron.sh 路径硬编码验证（修复后）

```
Given: audit-cron.sh 中所有 AUDIT_DIR/SESSION_DB 使用硬编码 /root
       （修复：s/${HOME}/\/root/g on L6, L9）
When:  HOME=/tmp bash audit-cron.sh
Then:  /tmp/.hermes/profiles/orchestrator/audit/terminal_commands.db 不存在
       /root/.hermes/profiles/orchestrator/audit/terminal_commands.db 存在且更新
       /root/.hermes/profiles/orchestrator/audit/.last_scan_id 存在
```

### 5.3 TC-P01-03：audit-cron.sh 修复前缺陷复现

```
Given: audit-cron.sh 仍使用 ${HOME}（当前状态）
When:  HOME=/tmp bash /root/.hermes/profiles/orchestrator/scripts/audit-cron.sh
Then:  /tmp/.hermes/profiles/orchestrator/audit/terminal_commands.db 被创建
       而 /root/.hermes/profiles/orchestrator/audit/ 下的状态文件未更新
       （证明：数据写入错误路径，importer 无法读取）
```

### 5.4 TC-P01-04：terminal-audit.sh source 环境验证

```
Given: terminal-audit.sh 使用 ${HOME}（当前状态或修复后）
When:  source terminal-audit.sh（正常终端环境，HOME=/root）
Then:  audit 功能正常启用，输出 "[audit] Terminal command audit enabled"
       echo $AUDIT_DIR 返回 /root/.hermes/profiles/orchestrator/audit
       mkdir -p 的目录可正常创建
```

### 5.5 TC-P01-05：backup-repo 同步检查

```
Given: /workspace/backup-repo/config/ 下的 audit-cron.sh
When:  grep -n 'HOME' audit-cron.sh
Then:  修复后应无任何 HOME 引用（或仅注释中存在）
       所有路径变量使用硬编码 /root
```

### 5.6 TC-P01-06：审计数据完整性端到端验证（综合测试）

```
Given: 所有审计脚本已修复为硬编码 /root
       cron 环境 HOME=/tmp
When:  1. audit-cron.sh 扫描 session DB 并写入
       2. audit-import.sh 从 log 导入
       3. 查询 audit DB
Then:  sqlite3 /root/.hermes/profiles/orchestrator/audit/terminal_commands.db \
         "SELECT COUNT(*) FROM commands;"  > 0
       审计路径统一为 /root/.hermes/...，无数据分裂
       不存在 /tmp/.hermes/ 下的孤立审计数据
```

### 5.7 测试覆盖矩阵

| 测试用例 | 覆盖脚本 | 覆盖发现 | 类型 |
|---------|---------|---------|:---:|
| TC-P01-01 | audit-import.sh | F1 (已修复) | 回归验证 |
| TC-P01-02 | audit-cron.sh | F2a (修复后) | 正向验证 |
| TC-P01-03 | audit-cron.sh | F2a (修复前) | 缺陷复现 |
| TC-P01-04 | terminal-audit.sh | F2b | 环境验证 |
| TC-P01-05 | backup-repo audit-cron.sh | F3 | 同步检查 |
| TC-P01-06 | 全链路 | F1+F2a+F2b | 端到端 |

---

## 6. 修复建议

### 6.1 最小修复集（修复 MAJOR F2a）

```bash
# 修复文件：/root/.hermes/profiles/orchestrator/scripts/audit-cron.sh
# 替换 L6: AUDIT_DIR="${HOME}/.hermes/profiles/orchestrator/audit"
#    →   AUDIT_DIR="/root/.hermes/profiles/orchestrator/audit"
# 替换 L9: SESSION_DB="${HOME}/.hermes/profiles/orchestrator/state.db"
#    →   SESSION_DB="/root/.hermes/profiles/orchestrator/state.db"
```

### 6.2 完整修复集（覆盖所有发现）

| # | 文件 | 变更 | 优先级 |
|---|------|------|:---:|
| 1 | `/root/.hermes/profiles/orchestrator/scripts/audit-cron.sh` | `${HOME}` → `/root` (L6, L9) | **BLOCKER** (MAJOR) |
| 2 | `/root/.hermes/profiles/orchestrator/scripts/terminal-audit.sh` | `${HOME}` → `/root` (L6) | HIGH (MINOR) |
| 3 | `/root/.hermes/profiles/orchestrator/scripts/terminal-audit-env.sh` | `${HOME}` → `/root` (L6) | HIGH (MINOR) |
| 4 | `/workspace/backup-repo/config/profiles/orchestrator/scripts/audit-cron.sh` | 同步修复 | LOW (SUGGESTION) |
| 5 | `/workspace/backup-repo/config/scripts/audit-cron.sh` | 同步修复 | LOW (SUGGESTION) |

### 6.3 可选增强（建议但非必须）

- 在 `audit-cron.sh` 开头添加 `HOME=/root` 作为防御性 fallback（即使修复后也保留）
- 在 cron entry 中显式设置 `HOME=/root` 作为额外安全层

---

## 7. 发布门禁影响

按标准 §10：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 检查项 | 当前状态 |
|--------|:---:|
| BLOCKER=0？ | ✅ 无 BLOCKER 级发现 |
| 安全漏洞=0？ | ✅ 非安全漏洞 |
| 无未裁定申诉？ | ✅ 无申诉 |
| MAJOR 建议 | 1 个 MAJOR (F2a)，建议修复后发版 |

**结论**：满足发布门禁。F2a 为 MAJOR 级，按 §10 可发版但需标注 known issue。

---

## 8. 附录

### 8.1 审计脚本完整清单

| 脚本 | 路径 | 用途 | 调用方式 | HOME 风险 |
|------|------|------|---------|:---:|
| audit-import.sh | `/workspace/backup-repo/config/scripts/` | 从 log 导入到 SQLite | cron | 已修复 |
| audit-import.sh | `/workspace/backup-repo/config/profiles/orchestrator/scripts/` | 同上（profile 版） | cron | 已修复 |
| audit-cron.sh | `/root/.hermes/profiles/orchestrator/scripts/` | 扫描 session DB | cron | **未修复** |
| terminal-audit.sh | `/root/.hermes/profiles/orchestrator/scripts/` | 实时审计（source） | source 执行 | **未修复** |
| terminal-audit-env.sh | `/root/.hermes/profiles/orchestrator/scripts/` | 实时审计（BASH_ENV） | BASH_ENV | **未修复** |
| audit-cron.sh | `/workspace/backup-repo/config/profiles/orchestrator/scripts/` | backup 副本 | cron | **未修复** |
| audit-cron.sh | `/workspace/backup-repo/config/scripts/` | backup 副本 | cron | **未修复** |

### 8.2 标准引用速查

| 条款 | 主题 | 本方案使用 |
|------|------|---------|
| §1.2 | 判定公式 | F1/F2 五步判定 |
| §1.3 | 判定原则 | "用户可感知"扩展定义（数据完整性） |
| §4 | 数据敏感度 | C 级不加权 |
| §6 | 论证流程 | grandfather clause + 新发现流程 |
| §8 | SLA | MINOR 2 工作日 → 同日修复远超 |
| §10 | 发布门禁 | BLOCKER=0 → 可发版 |

---

> **重审结论**：P0-01 原始修复有效但不完整。`audit-import.sh` 已正确修复为 `/root`，但 `audit-cron.sh` 等 3 个活跃运行时脚本 + 2 个 backup 副本仍使用 `${HOME}`，新增 1 个 MAJOR 发现(F2a)。建议扩展修复范围到所有审计脚本。
>
> 预计修复工时：0.1h（3 行代码变更）。不阻塞发版。
