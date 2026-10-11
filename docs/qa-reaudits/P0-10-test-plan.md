# P0-10 Consolidation 审计 — 测试方案（数据完整性专项）

> 版本：v1.0 | 状态：Draft — 待评审
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 专项目标：按标准 §4 数据敏感度加权框架，覆盖 consolidation 全路径数据完整性

---

## 1. 背景

P0-10（t_275f3135）是对 Hermes Curator 的 consolidation 机制的审计任务，涵盖 diff 对比、snapshot 快照存储、rollback 回滚恢复三个维度。已完成的初始审计（session 20260707_222616_ddb1e8）结论为 PASS，发现 3 个低优先级问题（P2/P3 级别）。

本方案在此基础上，按新 QA 标准 §4 数据完整性的要求，设计专项测试用例，确保 consolidation 机制在快照存储、恢复、合并全路径上不发生数据丢失、损坏或不一致。

### 1.1 关键发现（原始审计）

| 发现 | 描述 | 原始级别 | 新标准级别 |
|------|------|:---:|:---:|
| F1 | diff/snapshot/rollback 全部通过 | — | **PASS** |
| P2 | `skill_files` 字段命名歧义（统计 SKILL.md 数非 tar 文件数） | P2 | **SUGGESTION** |
| P3 | `run.json` vs `manifest.json` 计数口径不统一 | P3 | **SUGGESTION** |
| P3 | 快照保留策略不匹配（keep:5 vs archive_after_days:90） | P3 | **MINOR** |

### 1.2 当前功能状态

- **Diff/快照/回滚**：✅ 已验证通过（两次快照，零文件丢失）
- **LLM Consolidation（合并）**：❌ 功能关闭（`consolidate: false`），无法验证
- **最近 curator 运行**：2026-07-04，持续时间 0.26s（LLM pass skipped）

---

## 2. 测试范围

### 2.1 数据完整性维度映射

按标准 §4 数据敏感度分类，consolidation 涉及的数据资产如下：

| 数据类型 | 敏感度 | 加权规则 | 涉及路径 |
|---------|:---:|---------|---------|
| SKILL.md（agent 技能文件） | A级* | 一致性 bug → 最低 MAJOR | diff/snapshot/rollback/consolidate |
| cron-jobs.json（定时任务配置） | B级 | 不加权 | snapshot |
| manifest.json（快照元数据） | C级 | 按正常公式 | diff/snapshot |
| run.json（运行记录） | C级 | 按正常公式 | 审计日志 |
| skills.tar.gz（归档文件） | A级* | 一致性 bug → 最低 MAJOR | snapshot/rollback |
| .curator_state（curator 内部状态） | C级 | 按正常公式 | 状态一致性 |

> \* **A级映射说明**：SKILL.md 是 AI Agent 的核心能力资产——丢失技能文件等于丢失 agent 功能。在 agent 系统的语境中，技能文件的完整性与传统应用中「用户资产数据」的严重程度相当。本方案将 SKILL.md 按 A 级处理，一致性 bug 自动 +1 级，最低 MAJOR。

### 2.2 测试路径覆盖

```
curator run
  ├── 1. 扫描 skills/ 目录 → 产出 run.json 运行记录
  ├── 2. 创建 skills.tar.gz 快照 → 校验完整性
  ├── 3. 写入 manifest.json → 校验字段一致性
  ├── 4. 写入 cron-jobs.json → 校验无丢失
  ├── 5. 回滚路径（从旧快照恢复） → 校验可恢复性
  └── 6. LLM consolidate（当前关闭） → staging 开启验证
```

### 2.3 不覆盖的范围

| 范围外 | 理由 |
|--------|------|
| curator 调度可靠性（cron 触发机制） | 属于 P0-13 context_from 链的测试范围 |
| curator 性能（运行时长/token 消耗） | 本方案聚焦 §4 数据完整性，性能见 §3 |
| 非 curator 创建的 skill 变更 | 手动编辑/外部导入不通过 consolidation |
| archive 实际删除行为 | archive_after_days:90 尚未触发过（技能均 <30 天） |

---

## 3. 测试方法

### 3.1 判定公式（所有发现统一使用）

```
前置检查：安全漏洞？→ 否（curator 内部工具，不暴露外部接口）

正式判定（五步）：
  步骤 E — 用户可感知？  → 数据不可恢复/丢失 → 是
  步骤 F — 功能阻断？    → 丢失技能 → 是（agent 失去对应能力）
  步骤 W — 有 workaround？→ 有旧快照可恢复 → 有 → MAJOR
                            → 所有快照都损坏 → 无 → BLOCKER
  步骤 D — 数据敏感度？  → SKILL.md = A级 → 涉及一致性 +1 级 → 最低 MAJOR
                            → cron-jobs = B级 → 不加权
  步骤 P — 性能退化？    → 不适用（数据完整性，非性能）
```

### 3.2 测试环境要求

| 条件 | 用途 | 状态 |
|------|------|:---:|
| 生产 curator 备份目录（`~/.hermes/profiles/orchestrator/skills/.curator_backups/`） | 快照/回滚测试 | ✅ 可用（2 个快照） |
| 生产 curator 配置文件（`config.yaml`） | 配置一致性检查 | ✅ 可用 |
| Staging 环境（开启 `consolidate: true`） | LLM 合并逻辑验证 | ❌ 待就绪 |
| 回滚隔离环境（`/tmp/rollback_test_*`） | 回滚不影响生产 | ✅ 可用 |

### 3.3 测试工具

```bash
# 快照完整性校验
tar -tzf skills.tar.gz | wc -l          # 条目数
tar -xzf skills.tar.gz -C /tmp/verify/   # 解压测试
diff -rq old_dir/ new_dir/               # 文件级对比

# manifest 校验
jq '.skill_files' manifest.json          # 字段提取
jq 'keys' manifest.json                  # 字段完整性

# 计数一致性
jq '.counts' run.json                    # agent-created 计数
jq '.skill_files' manifest.json           # 全部 SKILL.md 计数
```

---

## 4. 测试用例

### 4.1 数据完整性测试矩阵

| TC-ID | 测试项 | 数据敏感度 | 预期最坏级别 | 当前快照数要求 |
|-------|--------|:---:|:---:|:---:|
| TC-DATA-01 | 快照文件零丢失 | A级 | BLOCKER | ≥ 2 |
| TC-DATA-02 | manifest.json 字段一致性 | C级 | MAJOR | ≥ 2 |
| TC-DATA-03 | run.json vs manifest 计数对齐 | C级 | MINOR | ≥ 1 |
| TC-DATA-04 | tar.gz 解压完整性 | A级 | BLOCKER | ≥ 2 |
| TC-DATA-05 | 回滚可恢复性 | A级 | BLOCKER | ≥ 2 |
| TC-DATA-06 | cron-jobs.json 快照完整性 | B级 | MAJOR | ≥ 2 |
| TC-DATA-07 | 备份保留策略覆盖 | A级 | MAJOR | ≥ keep 值 |
| TC-DATA-08 | LLM 合并不破坏技能 | A级 | BLOCKER | ≥ 2（staging） |

### 4.2 详细测试用例

---

#### TC-DATA-01：快照文件零丢失（A级 → 最坏 BLOCKER）

**目标**：验证 curator 快照不丢失任何已有技能文件。

**前置条件**：至少 2 个 curator 快照。

**步骤**：
1. 列出所有快照：`ls -lt .curator_backups/`
2. 选取最近两次快照，解压到独立目录
3. 对比旧→新快照的文件级 diff：`diff -rq old_extract/ new_extract/ | grep "^Only in.*old"`
4. 记录所有 `Only in old/` 条目（= 丢失的文件）
5. 核对 `Only in new/` 条目（= 新增的文件）

**预期结果**：
- `Only in old/` 条目数 = 0（零文件丢失）
- 所有 `Only in new/` 条目可追溯（新增技能/参考文档）

**数据完整性判定**：
```
步骤 E: 用户可感知？ → 丢失技能文件 → 是
步骤 F: 功能阻断？   → 丢失的技能无法使用 → 是
步骤 W: 有 workaround？ → 取决于丢失范围：
  - 单个非核心技能丢失 → 有（手动重建）→ MAJOR
  - 多个技能或核心技能丢失 → 无 → BLOCKER
步骤 D: 数据敏感度？ → SKILL.md = A级 → 最低 MAJOR
最终: 最坏 → BLOCKER（多技能丢失）/ 最好 → MAJOR（单技能丢失）
```

**回归触发**：每次 curator 运行后。

---

#### TC-DATA-02：manifest.json 字段一致性（C级 → 最坏 MAJOR）

**目标**：验证 manifest.json 的所有字段在 curator 每次运行时正确更新，无遗漏、无漂移。

**前置条件**：至少 2 个 manifest.json。

**步骤**：
1. 提取两次 manifest 的顶层 keys：`jq 'keys' manifest_old.json` 和 `jq 'keys' manifest_new.json`
2. 对比 keys 列表，确认无新增/丢失字段（除 `id`/`created_at` 外）
3. 逐字段值校验：
   - `skill_files` ≥ 0 且与 tar.gz 内 SKILL.md 数一致
   - `archive_bytes` = 实际 tar.gz 文件大小（±1KB）
   - `jobs_count` = cron-jobs.json 内 job 数量
   - `run_number` = 上次运行次数 + 1

**预期结果**：
- 字段 key 集合不变（仅 `id`/`created_at` 值变化）
- `skill_files` = `find -name SKILL.md | wc -l`
- `archive_bytes` ≈ `stat -c%s skills.tar.gz`
- `jobs_count` = `jq 'length' cron-jobs.json`

**数据完整性判定**：
```
步骤 E: 用户可感知？ → manifest 字段不准确 → 内部元数据 → 否（用户不直接读 manifest）
  但：manifest 字段错误导致回滚选错快照 → 间接用户影响 → 是
步骤 F: 功能阻断？ → 回滚功能受影响 → 是
步骤 W: 有 workaround？ → 手动检查所有快照 → 有（但极耗时）→ MAJOR
步骤 D: C级 → 不加权
最终: → MAJOR
```

**回归触发**：每次 curator 运行后。

---

#### TC-DATA-03：run.json vs manifest 计数对齐（C级 → 最坏 MINOR）

**目标**：验证 run.json 的 `counts` 与 manifest.json 的 `skill_files` 之间的差异可解释（agent-created vs 全部）。

**前置条件**：一个 curator 运行周期。

**步骤**：
1. 读取 `run.json` → `counts.before` / `counts.after`
2. 读取 `manifest.json` → `skill_files`（旧快照）/ `skill_files`（新快照）
3. 计算差额 = manifest.skill_files - run.counts
4. 验证差额 = 内置技能数（built-in skills，非 agent 创建）

**预期结果**：
- 差额 ≥ 0，且恒定（内置技能数不变）
- 差额不为负数（agent-created 不应该多于全部技能）

**数据完整性判定**：
```
步骤 E: 用户可感知？ → 否（内部计数，用户不直接看到）
  但：差额为负数 = 计数混乱 → 系统健康度退化 → 是
步骤 F: 功能阻断？ → 不影响核心功能 → 否 → MINOR
步骤 D: C级 → 不加权
最终: 差额 ≥ 0 → SUGGESTION（当前状态）/ 差额 < 0 → MINOR
```

**回归触发**：每次 curator 运行后 + 每次新增内置技能后。

---

#### TC-DATA-04：tar.gz 解压完整性（A级 → 最坏 BLOCKER）

**目标**：验证 skills.tar.gz 归档文件可完整解压，无损坏。

**前置条件**：至少 2 个 skills.tar.gz。

**步骤**：
1. 对每个快照的 tar.gz 执行完整性校验：
   ```bash
   tar -tzf skills.tar.gz > /dev/null 2>&1  # 基本校验
   tar -xzf skills.tar.gz -C /tmp/verify_N/  # 完整解压
   ```
2. 验证解压后的文件数与 `tar -tzf` 条目数一致
3. 验证每个 SKILL.md 文件非空、有 YAML frontmatter
4. 验证目录结构与 curator 分类一致

**预期结果**：
- `tar -tzf` 返回码 0（无损坏）
- 解压文件数 = tar 条目数（无截断）
- 所有 SKILL.md 文件非空且有 `---` frontmatter 分隔符

**数据完整性判定**：
```
步骤 E: 用户可感知？ → tar.gz 损坏 → 回滚失败 → 是
步骤 F: 功能阻断？   → 回滚不可用 → 是
步骤 W: 有 workaround？ → 有其他完好快照 → 有 → MAJOR
                          → 所有快照都损坏 → 无 → BLOCKER
步骤 D: A级 → 最低 MAJOR
最终: 最坏 → BLOCKER（全部损坏）
```

**回归触发**：每次 curator 运行后。

---

#### TC-DATA-05：回滚可恢复性（A级 → 最坏 BLOCKER）

**目标**：验证从指定快照完整恢复 skills/ 目录的能力。

**前置条件**：至少 2 个快照，回滚测试环境（`/tmp/`）。

**步骤**：
1. 选取最旧快照，解压到 `/tmp/rollback_test/`
2. 逐文件对比恢复后的 skills/ 与快照内文件：
   - 文件数一致
   - 每个 SKILL.md 内容一致（非空、无截断）
   - 目录结构一致
3. 恢复后的 skills/ 下执行 `hermes skill list`（如果 CLI 可用），验证技能可被 agent 识别
4. 选取最新快照，重复上述步骤

**预期结果**：
- 恢复文件数 = 快照 tar 条目数
- 所有技能文件完整、可被 agent 识别
- 回滚仅影响 skills/ 目录，不影响 config.yaml/其他配置

**数据完整性判定**：
```
步骤 E: 用户可感知？ → 快照无法恢复 → agent 能力降级 → 是
步骤 F: 功能阻断？   → 是（agent 失去技能）
步骤 W: 有 workaround？ → 有其他完好快照 → 有 → MAJOR
                          → 所有快照不可恢复 → 无 → BLOCKER
步骤 D: A级 → 最低 MAJOR
最终: 最坏 → BLOCKER
```

**回归触发**：每次 curator 运行后 + 每次配置变更后。

---

#### TC-DATA-06：cron-jobs.json 快照完整性（B级 → 最坏 MAJOR）

**目标**：验证 curator 快照不丢失 cron job 数据。

**前置条件**：至少 2 个 cron-jobs.json。

**步骤**：
1. 对比两次快照的 cron-jobs.json，提取 job id 列表
2. 确认旧快照中的所有 job id 在新快照中仍存在（除非曾被删除/过期）
3. 对每个 job，校验关键字段一致：
   - `name`、`schedule`、`origin` 不变
   - `prompt` 可能更新但不应该被清空或大幅截断
   - `enabled_toolsets` 只增不减（除非手动修改）

**预期结果**：
- 旧快照 job id 集合 ⊆ 新快照 job id 集合（+ 新增 jobs）
- 所有 job 的 name/schedule/origin 跨快照一致
- 无 job 的 prompt 被意外清空

**数据完整性判定**：
```
步骤 E: 用户可感知？ → cron job 丢失 → 定时任务不再运行 → 是
步骤 F: 功能阻断？   → 丢失的 job 对应的自动化功能失效 → 是
步骤 W: 有 workaround？ → 手动重建 job → 有 → MAJOR
步骤 D: B级 → 不加权
最终: → MAJOR
```

**回归触发**：每次 curator 运行后 + 每次新增 cron job 后。

---

#### TC-DATA-07：备份保留策略覆盖（A级 → 最坏 MAJOR）

**目标**：验证快照保留策略（`backup.keep`）与实际归档策略（`archive_after_days`）的时间窗口匹配，确保归档前的快照不会过早被清理。

**前置条件**：`config.yaml` 中 curator 配置可读取。

**步骤**：
1. 读取配置：
   ```yaml
   curator:
     interval_hours: 168      # 快照间隔
     archive_after_days: 90   # 归档期限
   backup:
     keep: 5                  # 保留快照数
   ```
2. 计算覆盖窗口：`keep × interval_hours / 24 = 5 × 7 = 35 天`
3. 对比：35 天（快照覆盖）< 90 天（归档期限）
4. 验证：当快照数量达到 keep 上限后，最旧快照被删除时，被删除快照中的技能是否已超过 archive_after_days

**预期结果**：
- 快照覆盖窗口 ≥ 归档期限 ÷ 2（至少覆盖一半归档期）
- 或在 curator 代码中确认：删除旧快照前检查该快照中最早创建的技能是否已归档

**当前状态**：覆盖窗口（35天）远小于归档期限（90天），快照可能在技能归档前被清理 → **MINOR**（当前系统健康度退化，但尚未触发数据丢失）。

**数据完整性判定**：
```
步骤 E: 用户可感知？ → 快照被过早清理 → 回滚窗口缩小 → 用户可能感知（长期观察）
步骤 F: 功能阻断？ → 否（快照仍存在，只是覆盖窗口不够）
步骤 D: A级 → 涉及数据保护策略 → 最低 MAJOR（系统健康度退化路径）
当前: 尚未触发数据丢失 → MINOR（降一级）
  但：如已触发「归档前快照被清理」→ MAJOR（A级加权）
```

**回归触发**：每次 `backup.keep` 或 `archive_after_days` 变更后。

---

#### TC-DATA-08：LLM 合并不破坏技能内容（A级 → 最坏 BLOCKER）（staging 专属）

**目标**：验证 consolidation 的 LLM 合并逻辑在合并重复技能时不引入内容损坏、不丢失关键信息。

**前置条件**：
- Staging 环境已部署 curator
- `consolidate: true` 已设置
- 至少有两个语义相近的技能（模拟合并场景）

**步骤**：
1. 在 staging skills/ 下创建 2 个相似技能（如 `file-reader-v1` 和 `file-reader-v2`，有重叠内容）
2. 手动触发 curator run（`hermes curator run` 或等价操作）
3. 检查合并后的 SKILL.md：
   - 内容非空、有完整 YAML frontmatter
   - 保留了 v1 和 v2 的独有信息（无关键步骤丢失）
   - `absorbed_into` 引用正确
4. 检查引用该技能的 cron jobs：
   - cron job 中的 skill 引用是否被 rewrite 到合并后的技能名
   - 无悬空引用（orphaned skill reference）
5. 检查合并后的 snapshot：
   - tar.gz 中只有合并后的技能（被吸收的旧技能不在新快照中）
   - manifest.skill_files 反映了合并后的数量
6. 从合并前快照回滚，验证可恢复到合并前状态

**预期结果**：
- 合并后技能内容完整（无截断、无乱码）
- `absorbed_into` 引用指向正确的合并目标
- Cron job 引用正确 rewrite
- 旧快照仍可完整恢复（合并不影响历史快照）

**数据完整性判定**：
```
步骤 E: 用户可感知？ → 合并破坏技能内容 → agent 能力受损 → 是
步骤 F: 功能阻断？   → 被破坏的技能无法正常工作 → 是
步骤 W: 有 workaround？ → 从旧快照回滚 → 有 → MAJOR
                           → 旧快照也被破坏 → 无 → BLOCKER
步骤 D: A级 → 最低 MAJOR
最终: 最坏 → BLOCKER（内容丢失 + 所有快照受影响）
      正常 → MAJOR（内容受损但有旧快照可回滚）
```

**回归触发**：每次开启 consolidation 后 + 每次 curator 配置变更后。

---

## 5. 测试执行顺序与依赖

```
Phase 1 — 生产线（立即可执行，无需 staging）
  ├── TC-DATA-04: tar.gz 解压完整性      ← 先验证数据物理层无损坏
  ├── TC-DATA-01: 快照文件零丢失          ← 依赖 TC-DATA-04 的旧快照数据
  ├── TC-DATA-06: cron-jobs.json 完整性   ← 依赖 TC-DATA-04 的解压数据
  ├── TC-DATA-02: manifest 字段一致性     ← 依赖 TC-DATA-01 的 diff 数据
  ├── TC-DATA-03: run vs manifest 对齐    ← 独立
  ├── TC-DATA-05: 回滚可恢复性           ← 依赖 TC-DATA-04 的解压数据
  └── TC-DATA-07: 备份保留策略覆盖        ← 独立（仅读配置）

Phase 2 — Staging（需 staging 环境就绪）
  └── TC-DATA-08: LLM 合并不破坏技能     ← 需要 consolidate:true + staging
```

---

## 6. 退出标准

### 6.1 发布门禁（按标准 §10）

```
BLOCKER = 0 AND 安全漏洞 = 0 AND 无未裁定的申诉
```

| 退出条件 | 含义 |
|---------|------|
| TC-DATA-01~07 全部 PASS | 快照/回滚/完整性路径无阻塞问题 |
| 无 BLOCKER 级发现 | 满足发布门禁 BLOCKER=0 |
| TC-DATA-07 有明确结论 | 保留策略虽然不匹配但尚未触发数据丢失 → MINOR，可发版标注 known issue |
| TC-DATA-08 完成或明确暂缓 | LLM 合并仅在 staging 验证，非阻塞条件 |

### 6.2 允许发版的情况

- TC-DATA-01~07 PASS + TC-DATA-08 未执行（consolidation 关闭，当前生产无影响）
- 所有发现的级别 ≤ MAJOR
- MAJOR 项已标注 known issue

### 6.3 阻塞发版的情况

- TC-DATA-01/04/05 中出现 BLOCKER（零文件丢失/解压失败/回滚失败）
- 涉及 A 级数据（SKILL.md）的一致性 bug

---

## 7. 风险与假设

### 7.1 假设

| # | 假设 | 若假设不成立 |
|---|------|-------------|
| A1 | 生产 curator 备份目录至少有 2 个有效快照 | TC-DATA-01/02/04/05/06 无法执行（需至少 1 个快照，2 个做 diff） |
| A2 | 可读生产环境的 `skills/.curator_backups/` | 所有测试无法执行 → 需要在可访问的副本环境中执行 |
| A3 | curator 在测试期间不会新增/删除快照 | 测试结果可能过时，需标注快照日期 |
| A4 | Staging 环境可在合理时间内就绪 | TC-DATA-08 执行窗口不明确 |

### 7.2 已知风险

| # | 风险 | 缓解措施 |
|---|------|---------|
| R1 | curator 在测试期间运行，改变快照状态 | 在测试开始前锁定 `latest` 快照 ID，所有测试基于固定快照执行 |
| R2 | 回滚测试误操作影响生产 skills/ | 回滚测试完全在 `/tmp/` 隔离环境执行，不解压到生产 skills/ |
| R3 | 测试中操作大量文件触发磁盘 IO 瓶颈 | 每次测试后清理 `/tmp/rollback_test_*` |

---

## 8. 发现级别汇总（预判）

基于原始审计数据 + 本测试方案的覆盖矩阵，预判发现级别分布：

| 级别 | 预估数量 | 来源 |
|:---:|:---:|------|
| BLOCKER | 0 | 原始审计零文件丢失，但取决于 TC-DATA-04/05 执行结果 |
| MAJOR | 0-2 | TC-DATA-06 cron job 丢失 / TC-DATA-07 快照过早清理 |
| MINOR | 1-2 | TC-DATA-03 计数不对齐 / TC-DATA-07 保留策略（当前未触发） |
| SUGGESTION | 1-2 | TC-DATA-02 manifest 命名歧义 / TC-DATA-03 字段说明不足 |
| PASS | 4+ | TC-DATA-01/04/05 预期通过 |

---

## 9. SLA 与时间估算

| 阶段 | 内容 | 预估时间 | 依赖 |
|------|------|:---:|------|
| Phase 1 执行 | TC-DATA-01~07 | 30 min | 生产环境可读 |
| Phase 1 报告 | 测试结果 + 级别判定 | 15 min | Phase 1 执行完成 |
| Phase 2 执行 | TC-DATA-08（staging） | 20 min | Staging 就绪 + consolidate:true |
| Phase 2 报告 | LLM 合并结果 | 10 min | Phase 2 执行完成 |
| **总计** | | **1h 15min** | |

---

## 10. 附录：与 P0-01~13 重审的对接

P0-10 已纳入 P0-01~13 综合重审测试方案（`docs/qa-reaudits/test-plan-p0-01-13.md`）：

- **原始重审状态**：✅ 已重审，PASS（session 20260707_222616_ddb1e8）
- **待办事项**：#4 — consolidation 关闭，是否需要 staging 验证 LLM 合并逻辑？
- **级别统计**：PASS × 1, SUGGESTION × 2, MINOR × 1

本方案不重复 P0-01~13 方案的已有分析，而是补充 §4 数据完整性维度的专项测试。

---

## 版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-07-08 | 初始版本。按标准 §4 数据敏感度框架编写数据完整性专项测试方案。 | game-qa |
