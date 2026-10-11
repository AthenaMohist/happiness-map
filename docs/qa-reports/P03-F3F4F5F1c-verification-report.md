# QA 验证报告：P03 剩余4项修复 (F3/F4/F5/F1c)

> 报告日期：2026-07-08 | QA：game-qa | 任务：t_e3e4302b
> 父任务：t_15882802（game-engine 修复完成）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 测试方法

| 维度 | 方法 |
|------|------|
| 语法 | `bash -n` |
| 逻辑 | 代码路径审查 + 模拟条件测试 |
| 集成 | 3 副本 sha256 一致性校验 |
| 分级 | 对照 Roundtable 判定公式 §1.2 |

---

## F3: profiles.sha256 校验清单

### 修复位置

`hermes_backup_push.sh:279-291`（+12 行逻辑，不含注释）

### 修复内容

在 rsync profiles 后，生成 `profiles.sha256` 清单文件，对 `$REPO_DIR/config/profiles/` 下所有文件计算 sha256 校验和，排除自身和 SQLite WAL/SHM 文件。

### 测试结果

| 测试项 | 结果 | 证据 |
|--------|:---:|------|
| bash -n 语法 | ✅ PASS | `bash -n hermes_backup_push.sh` 无错误 |
| 3 副本一致性 | ✅ PASS | 6 个副本 sha256 完全一致 |
| sha256 生成 | ✅ PASS | 正确生成绝对路径 + sha256 格式清单 |
| 校验通过（完好文件） | ✅ PASS | `sha256sum -c` 全部 OK |
| 校验失败（损坏文件） | ✅ PASS | 损坏文件正确检测为 FAILED |
| 逻辑审查 | ✅ PASS | `> "$REPO_DIR/config/profiles.sha256"` 每次截断，无累积问题 |
| 排除自引用 | ✅ PASS | `-not -path '*/profiles.sha256'` 排除自身 |
| 排序 | ✅ PASS | `sort -k2` 保证可复现输出 |

### 分级判定（对照 §1.2）

```
安全漏洞？ 否 → 进入正式判定
用户可感知？ 否（仅在 DR 恢复场景由 operator 使用）
数据完整性？ 是（备份内容级校验增强）
→ 判定：MINOR（基础设施增强，非功能阻断）

公式对照：
  MINOR = 用户可感知 AND 不影响核心任务完成
  本项：用户不可感知（DR operator tool），不符合 MINOR 严格定义
  → SUGGESTION 更符合「用户不可感知的非安全/非数据完整性问题」
  但 parent task 已定 MINOR（数据完整性增强），维持不变

结论：MINOR ✅（维持 parent task 级别）
```

**已有 file count 检查（line 269-277）做基础完整性保障**，profiles.sha256 提供内容级增强，但两者覆盖不同维度：count 是数量校验，sha256 是内容校验。F3 补齐了内容校验缺口。

---

## F4: 权限自动捕获（stat→permissions.yaml→恢复脚本 chmod/chown）

### 修复位置

| 文件 | 行号 | 内容 |
|------|------|------|
| `hermes_backup_push.sh` | 422-435 | stat 权限捕获 |
| `hermes_backup_push.sh` | 484-505 | manifest 注释（`# perms:`） |
| `hermes_backup_push.sh` | 507-528 | `permissions.yaml` 生成 |
| `hermes_backup_restore.sh` | 全文件 (163 行) | 恢复脚本 |

### 修复内容

备份时通过 `stat` 捕获每个 sandbox 文件的 mode/owner/group，写入 `permissions.yaml` 和 manifest 注释。恢复脚本 `hermes_backup_restore.sh` 解析 `permissions.yaml` 并回放 chmod/chown（chown 需要 root，非 root 自动 skip）。

### 测试结果

| 测试项 | 结果 | 证据 |
|--------|:---:|------|
| bash -n 语法 | ✅ PASS | push + restore 双脚本均通过 |
| 3 副本一致性 | ✅ PASS | 6 个副本 sha256 一致 |
| stat 捕获 mode/owner/group | ✅ PASS | 正确获取 755/root/root 等属性 |
| permissions.yaml 生成格式 | ✅ PASS | YAML keyed by path，含 mode/owner/group |
| restore --dry-run | ✅ PASS | 正确显示将要执行的 chmod/chown |
| restore 实际 chmod | ✅ PASS | 权限从 700→755，600→644 正确恢复 |
| restore chown skip（非 root） | ✅ PASS | 自动检测非 root + 正确 skip 并提示 |
| restore chown skip（--skip-chown） | ✅ PASS | 显式 skip 生效，记录 skip 计数 |
| restore 缺失文件处理 | ✅ PASS | 文件不存在时 skip + warning + 计数 |

### 分级判定（对照 §1.2）

```
安全漏洞？ 否 → 进入正式判定
用户可感知？ 是（DR 恢复场景：权限错误 → 脚本无法执行 → 服务中断）
功能阻断？ 是（恢复后脚本无执行权限 = 功能不可用）
有 workaround？ 是（手动 chmod 可以修复）
→ 判定：MAJOR（用户可感知 + 功能阻断 + 有 workaround）

公式对照：
  MAJOR = (用户可感知 AND (功能阻断但有 workaround OR 体验严重退化))
  本项满足：用户可感知 ✅ + 功能阻断 ✅ + workaround ✅

结论：MAJOR ✅（维持 parent task 级别）
```

**边界用例**：
- `stat` 不可用时 fallback 为 `"???"`，permissions.yaml 跳过该文件 → ✅
- chown best-effort 设计合理：恢复脚本自动检测 root 权限 → ✅
- `--dry-run` 和 `--skip-chown` 参数提供操作安全性 → ✅

---

## F5: 死人手环死锁检测（心跳+完成时间戳+超25h告警）

### 修复位置

| 文件 | 行号 | 内容 |
|------|------|------|
| `hermes_backup_push.sh` | 39-45 | 配置（DEADMAN_DIR, DEADMAN_STALE_HOURS） |
| `hermes_backup_push.sh` | 132-174 | 心跳写入 + 过期检测逻辑 |
| `hermes_backup_push.sh` | 564-566 | 完成时间戳写入 |

### 修复内容

脚本启动时写入心跳时间戳，成功完成后写入完成时间戳。下次运行时检测上次心跳是否过期（>25h）且无匹配的完成记录，触发告警。

### 测试结果

| 测试项 | 结果 | 证据 |
|--------|:---:|------|
| bash -n 语法 | ✅ PASS | 无错误 |
| 正常周期（心跳 < 25h） | ✅ PASS | 不触发告警 |
| 过期心跳 + 完成时间戳 > 2h 差距 | ✅ PASS | 正确触发 dead man's switch |
| 过期心跳 + 无完成记录 | ✅ PASS | 正确触发 dead man's switch |
| 告警发送 | ✅ PASS | 通过 `_send_alert()` → VA Bot DM（Feishu） |
| 日志输出 | ✅ PASS | WARNING 级别日志清晰标注触发原因 |
| 目录不存在 | ✅ PASS | `mkdir -p "$DEADMAN_DIR"` 自动创建 |

### 分级判定（对照 §1.2）

```
安全漏洞？ 否 → 进入正式判定
用户可感知？ 是（operator 监控系统健康度）
系统健康度退化？ 是（备份静默失败无法检测）
→ 判定：MAJOR（系统健康度监控缺失可导致备份静默失败）

公式对照：
  MAJOR = 系统健康度退化（per §1.3 "用户可感知"扩展定义）
  "用户可感知"扩展定义 = ... OR 系统健康度退化（内存泄漏、错误率上升、MTTR 恶化）
  本项：备份静默失败 = MTTR 恶化风险

结论：MAJOR ✅（维持 parent task 级别）
```

**已知限制**（parent task 已记录）：
- 无法检测「cron 从未运行」场景 → 需要 GitHub Actions 作为第二层监控
- 检测仅在下次 cron 运行时生效 → 最多 24h 检测延迟（与 cron 频率相同）

---

## F1c: DR Runbook 模板

### 修复位置

`/workspace/dr_drill_reports/DR-RUNBOOK.md`（新文件，120 行）

### 修复内容

DR 恢复操作手册模板，包含 6 个恢复阶段 + 3 个应急场景 + 演习计划。

### 测试结果

| 测试项 | 结果 | 证据 |
|--------|:---:|------|
| 7 个必须 section | ✅ 全有 | Overview/Pre-Flight/Recovery/Drill/Incident/RTO/ChangeLog |
| 恢复阶段数 | 6 | Clone→Restore Config→Restore Scripts→Permissions→Verify→Services |
| 应急场景数 | 3 | Backup Failed / Dead Man's / Token Expired |
| 引用 F3 功能 | ✅ | Phase 5: `sha256sum -c profiles.sha256` |
| 引用 F4 功能 | ✅ | Phase 4: `bash hermes_backup_restore.sh` |
| 引用 F5 功能 | ✅ | Dead Man's Switch 应急场景 |
| 演习计划 | ✅ | Quarterly/Monthly/Weekly 三级 |
| 占位符 | 1 处 | `[e.g., 30 minutes]` — 模板预期行为 |
| MD 格式 | ✅ | 正确 Markdown，表格渲染正常 |

### 分级判定（对照 §1.2）

```
安全漏洞？ 否 → 进入正式判定
用户可感知？ 否（文档模板，非运行时代码）
→ 判定：SUGGESTION 或 MINOR

但 parent task 已定 MINOR（DR 程序必要文档），维持不变。
1 处占位符 `[e.g., 30 minutes]` 是模板预期行为，非缺陷。

结论：MINOR ✅（维持 parent task 级别）
```

---

## 综合门禁检查（对照 §10）

| 门禁条件 | 状态 |
|----------|:---:|
| BLOCKER = 0 | ✅ 0 |
| MAJOR ≤ 3 | ✅ 2（F4 + F5） |
| 安全漏洞 = 0 | ✅ 0 |
| 无未裁定的申诉 | ✅ 0 |
| bash -n 全脚本通过 | ✅ 6/6 副本 |
| 3 位置同步 | ✅ 6 个脚本 sha256 完全一致 |

**发布门禁：通过 ✅**

---

## 结构化 Claims

```yaml
claims:
  - id: "F3-VERIFIED"
    fix: "profiles.sha256 checksum manifest"
    location: "hermes_backup_push.sh:279-291"
    level: MINOR
    status: verified
    tests:
      - bash_syntax: pass
      - sha256_generation: pass
      - sha256_validation: pass
      - corruption_detection: pass
      - exclude_self: pass
      - three_copy_sync: pass
    notes: "Truncates fresh each run via '>' redirect. Correctly excludes self-reference and sqlite WAL/SHM."

  - id: "F4-VERIFIED"
    fix: "Permission auto-capture (stat→permissions.yaml→restore chmod/chown)"
    location:
      push: "hermes_backup_push.sh:422-528"
      restore: "hermes_backup_restore.sh (full file, 163 lines)"
    level: MAJOR
    status: verified
    tests:
      - bash_syntax: pass
      - stat_capture: pass
      - permissions_yaml_format: pass
      - restore_dry_run: pass
      - restore_chmod: pass
      - restore_chown_skip_non_root: pass
      - restore_missing_file_handling: pass
      - three_copy_sync: pass
    notes: "chown is best-effort (requires root). --dry-run and --skip-chown provide operational safety."

  - id: "F5-VERIFIED"
    fix: "Dead man's switch (heartbeat+completion+>25h alert)"
    location:
      config: "hermes_backup_push.sh:39-45"
      check: "hermes_backup_push.sh:132-174"
      completion: "hermes_backup_push.sh:564-566"
    level: MAJOR
    status: verified
    tests:
      - bash_syntax: pass
      - fresh_heartbeat_no_alert: pass
      - stale_heartbeat_with_completion_gap: pass
      - stale_heartbeat_no_completion_ever: pass
      - alert_via_va_bot: pass
      - log_output: pass
      - auto_mkdir: pass
    notes: "Cannot detect 'cron never ran'. Requires GitHub Actions as second monitoring layer. Max 24h detection delay."

  - id: "F1c-VERIFIED"
    fix: "DR Runbook template"
    location: "dr_drill_reports/DR-RUNBOOK.md (new file, 120 lines)"
    level: MINOR
    status: verified
    tests:
      - all_7_sections_present: pass
      - recovery_phases: 6
      - incident_scenarios: 3
      - references_f3_f4_f5: pass
      - drill_schedule_3_tiers: pass
      - markdown_valid: pass
    notes: "1 unfilled placeholder [e.g., 30 minutes] — expected for template. References all 3 other fixes correctly."

gate_check:
  BLOCKER: 0
  MAJOR: 2  # F4 + F5
  security_vulns: 0
  pending_appeals: 0
  bash_n: "6/6 copies passed"
  sync: "all 3 locations identical"
  release_ready: true
```

---

## 未覆盖的边缘场景（known limitations）

| # | 场景 | 影响 | 建议 |
|---|------|------|------|
| 1 | F5 无法检测「cron 从未运行」 | 备份完全停止时无告警 | 需 GitHub Actions 第二层（parent task 已记录） |
| 2 | F4 chown 在非 root 环境无效 | 恢复后文件 owner 可能不正确 | 大部分 sandbox 文件 owner=root，非 root 运行场景极少 |
| 3 | F3 profiles.sha256 使用绝对路径 | 恢复后路径可能变化 | 恢复时需 cd 到 repo config 目录后验证（DR runbook 已记录） |
| 4 | F1c RTO Target 为占位符 | 模板未填充实际值 | 首次 DR drill 后填入实际值 |
