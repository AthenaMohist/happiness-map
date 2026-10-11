# P0-10 Consolidation 审计 — 测试报告（数据完整性专项）

> 版本：v1.0 | 状态：Final
> 执行日期：2026-07-08
> 执行人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 测试方案：`docs/qa-reaudits/P0-10-test-plan.md` v1.0

---

## 1. 执行摘要

| 指标 | 值 |
|------|:---:|
| 总测试用例 | 8 |
| 已执行 | 7 |
| 暂缓 | 1（TC-DATA-08：LLM 合并 staging 不可用） |
| PASS | 7 |
| FAIL | 0 |
| 发现总数 | 3 |
| BLOCKER | 0 |
| MAJOR | 0 |
| MINOR | 1 |
| SUGGESTION | 2 |

**结论**：P0-10 Consolidation 机制数据完整性路径全部通过。满足发布门禁（BLOCKER=0，安全漏洞=0，无未裁定申诉）。无需阻塞发版。

## 2. 测试环境

| 项目 | 值 |
|------|-----|
| 快照源 | `/root/.hermes/profiles/orchestrator/skills/.curator_backups/` |
| 快照 1（旧） | `2026-06-27T15-19-23Z`（83 SKILL.md, 1 cron job） |
| 快照 2（新） | `2026-07-04T16-04-08Z`（89 SKILL.md, 3 cron jobs） |
| 配置文件 | `/root/.hermes/profiles/orchestrator/config.yaml` |
| curator 版本 | interval_hours=168, backup.keep=13, consolidate=false |
| 回滚测试目录 | `/tmp/verify_s1/`, `/tmp/verify_s2/` |

## 3. 逐用例结果

### TC-DATA-01：快照文件零丢失（A级 → 最坏 BLOCKER）

| 项目 | 结果 |
|------|:---:|
| 状态 | ✅ **PASS** |
| Only in old (丢失文件) | 0 |
| Only in new (新增文件) | 17 |
| Files differ (内容变更) | 13 |

**分析**：旧快照→新快照之间无任何文件丢失。新增 17 个条目（含 `hermes-admin` 技能、`agent-memory-architecture`、`claim-schema`、`deterministic-schema-output`、`progressive-feedback-pipeline`、`script-driven-agent` 等新增技能及参考文件），13 个 SKILL.md 内容更新——均属正常演进。

**判定公式对照**：
```
步骤 E: 用户可感知？ → 零文件丢失 → 不适用
最终: PASS（无问题触发判定）
```

---

### TC-DATA-02：manifest.json 字段一致性（C级 → 最坏 MAJOR）

| 项目 | S1 值 | S2 值 | 验证 |
|------|-------|-------|:---:|
| 状态 | — | — | ✅ **PASS** |
| `skill_files` | 83 | 89 | ✅ 与 `find -name SKILL.md` 一致 |
| `archive_bytes` | 2,014,230 | 2,070,764 | ✅ 与 `stat -c%s` 一致（精确匹配） |
| `jobs_count` | 1 | 3 | ✅ 与 cron-jobs.json 实际 job 数一致 |
| 字段 key 集合 | 7 keys | 7 keys | ✅ 仅 `id`/`created_at` 值变化 |

**分析**：两个 manifest 的结构完全一致，所有字段值与实际数据精确匹配。

**发现**：
- **F-DATA-01（MINOR）**：manifest 缺少 `run_number` 字段。测试方案预期每次 curator 运行后 `run_number + 1`，但当前 manifest 不包含此字段。这对版本追踪和回滚选快照有影响——`created_at` 是弱排序依据（依赖时钟精度），`run_number` 是强顺序依据。

**判定公式对照（F-DATA-01）**：
```
步骤 E: 用户可感知？ → 是（扩展定义：系统健康度退化——缺少强排序字段降低回滚可审计性）
步骤 F: 功能阻断？   → 否（created_at 可作为 fallback 排序）
→ MINOR
```

---

### TC-DATA-03：run.json vs manifest 计数对齐（C级 → 最坏 MINOR）

| 项目 | S1 | S2 |
|------|:--:|:--:|
| 状态 | ✅ **PASS** | ✅ **PASS** |
| run.json `counts.before` | 73 | 75 |
| run.json `counts.after` | 73 | 75 |
| manifest `skill_files` | 83 | 89 |
| 差额（manifest − run） | 10 | 14 |
| 差额说明 | 内置技能数 | 内置技能数 |

**分析**：差额为正且恒定/递增，`counts` 追踪 agent-created 技能，`skill_files` 统计全部 SKILL.md。差额 = 内置技能数——可解释且合理。

**发现**：
- **F-DATA-02（SUGGESTION）**：`skill_files` 字段命名歧义（原始审计 P2 重审）。该字段统计 SKILL.md 文件数（83/89），而非 tar.gz 内的文件数（489/509）或 tar 条目数（662/693）。命名可能使新用户误认为统计 tar 包内文件数。建议未来更名为 `skill_count`（须 breaking change 管理）。

**判定公式对照（F-DATA-02）**：
```
步骤 E: 用户可感知？ → 否（字段值正确，仅命名歧义）
→ SUGGESTION
```

---

### TC-DATA-04：tar.gz 解压完整性（A级 → 最坏 BLOCKER）

| 项目 | S1 | S2 |
|------|:--:|:--:|
| 状态 | ✅ **PASS** | ✅ **PASS** |
| `tar -tzf` 返回码 | 0 | 0 |
| tar 条目数 | 662 | 693 |
| 解压返回码 | 0 | 0 |
| 解压文件数 | 489 | 509 |
| 解压目录数 | 174 | 185 |
| SKILL.md 数 | 83 | 89 |
| 空 SKILL.md | 0 | 0 |
| 无 frontmatter 的 SKILL.md | 0 | 0 |

**分析**：两个快照的 tar.gz 均完整、无损。所有 SKILL.md 非空且有 YAML frontmatter。目录结构完整——18 个技能分类目录（apple, autonomous-ai-agents, balance-check, ..., yuanbao）全部存在。

**判定公式对照**：无问题触发判定 — PASS。

---

### TC-DATA-05：回滚可恢复性（A级 → 最坏 BLOCKER）

| 项目 | S1 | S2 |
|------|:--:|:--:|
| 状态 | ✅ **PASS** | ✅ **PASS** |
| 可完整解压 | ✅ | ✅ |
| 文件数匹配 tar 条目 | ✅ | ✅ |
| SKILL.md 全部非空 | ✅（83/83） | ✅（89/89） |
| 目录结构完整 | ✅（18 分类） | ✅（19 分类） |
| 技能可被识别 | ✅（frontmatter 完整） | ✅（frontmatter 完整） |

**分析**：从任意快照恢复 skills/ 目录不存在技术障碍。所有 SKILL.md 文件完整、目录结构正确。回滚过程为纯 tar 解压操作，不依赖外部服务。

**判定公式对照**：无问题触发判定 — PASS。

---

### TC-DATA-06：cron-jobs.json 快照完整性（B级 → 最坏 MAJOR）

| 项目 | S1 | S2 |
|------|:--:|:--:|
| 状态 | ✅ **PASS** | ✅ **PASS** |
| Job 数 | 1 | 3 |
| 丢失的 job | 0 | — |
| 新增的 job | — | 2（d9961f9611e5, c4a0aee0e954） |
| 共同 job name 一致 | — | ✅（39227b58ebcf） |
| 共同 job schedule 一致 | — | ✅（0 3 * * *） |
| 共同 job origin 一致 | — | ✅ |
| prompt 无清空/截断 | — | ✅（有更新但非截断） |

**分析**：旧快照中的 job（39227b58ebcf）在新快照中完整保留，字段一致。新增的 2 个 job 均在 S1 快照日期之后创建（d9961f9611e5 创建于 2026-06-29，c4a0aee0e954 创建于 2026-06-29）。无 job 丢失，无 prompt 被意外清空。

**判定公式对照**：无问题触发判定 — PASS。

---

### TC-DATA-07：备份保留策略覆盖（A级 → 最坏 MAJOR）

| 参数 | 值 |
|------|-----|
| 状态 | ✅ **PASS** |
| `interval_hours` | 168（7 天） |
| `backup.keep` | 13 |
| `archive_after_days` | 90 |
| 覆盖窗口 | 13 × 7 = 91 天 |
| 覆盖率 | 91 / 90 = **101%** ✅ |

**分析**：原始审计中发现覆盖率不足的 P3 发现（keep:5 → 35天 < 90天）已变为 PASS。配置已更新为 `keep: 13`，注释明确说明："Keep 13 snapshots to cover the 90-day archive window." 13 个周快照 = 91 天覆盖，足以保障归档窗口内的所有技能可恢复。

**判定公式对照**：无问题触发判定 — PASS。

---

### TC-DATA-08：LLM 合并不破坏技能内容（A级 → 最坏 BLOCKER）

| 状态 | **DEFERRED** |
|------|-------------|
| 原因 | `consolidate: false`（当前生产关闭）；staging 环境不可用 |
| 影响 | 无生产影响——LLM 合并逻辑未启用 |
| 前置条件 | staging 环境 + `consolidate: true` |

**待办**：当 staging 环境就绪且 consolidation feature flag 开启后执行此测试。

---

## 4. QA 发现汇总

### 4.1 发现清单

| ID | 测试用例 | 级别 | 描述 |
|----|---------|:---:|------|
| F-DATA-01 | TC-DATA-02 | **MINOR** | manifest.json 缺少 `run_number` 字段。无法按运行序号强排序快照，依赖 `created_at`（弱排序） |
| F-DATA-02 | TC-DATA-03 | **SUGGESTION** | `skill_files` 字段命名歧义（统计 SKILL.md 数，非 tar 文件数）。见原始审计 P2 |
| F-DATA-03 | TC-DATA-06 | **SUGGESTION** | 共同 job (39227b58ebcf) 的 prompt 在快照间发生了变化（新增"基础健康检查"部分）。这属正常更新但无法从 manifest 区分故意的 prompt 更新 vs 数据损坏 |

### 4.2 级别分布

| 级别 | 数量 | 占已执行测试 |
|:---:|:---:|:---:|
| BLOCKER | 0 | 0% |
| MAJOR | 0 | 0% |
| MINOR | 1 | 14% |
| SUGGESTION | 2 | 29% |
| PASS（无发现） | 4 | 57% |

### 4.3 判定公式逐条对照

#### F-DATA-01（MINOR）：manifest 缺少 run_number

```
前置检查：安全漏洞？ → 否
正式判定：
  步骤 E — 用户可感知？ → 是（扩展：系统健康度退化——回滚排序依赖弱排序依据）
  步骤 F — 功能阻断？   → 否（created_at 可作为 fallback）
  最终: MINOR
```

#### F-DATA-02（SUGGESTION）：skill_files 命名歧义

```
步骤 E — 用户可感知？ → 否（字段值正确，仅有命名歧义）
不参与 BLOCKER/MAJOR/MINOR 讨论 → SUGGESTION
```

#### F-DATA-03（SUGGESTION）：prompt 变更不可验证意图

```
步骤 E — 用户可感知？ → 否（当前 prompt 内容正确，无法区分更新 vs 损坏）
不参与 BLOCKER/MAJOR/MINOR 讨论 → SUGGESTION
```

### 4.4 SLA 与处理状态

| 发现 | 级别 | SLA 要求 | 当前状态 |
|------|:---:|---------|---------|
| F-DATA-01 | MINOR | 无强制时延，可排期修复 | 待排期 |
| F-DATA-02 | SUGGESTION | 无时延要求 | 记录在案 |
| F-DATA-03 | SUGGESTION | 无时延要求 | 记录在案 |

### 4.5 原始审计发现的重新定级

| 原始发现 | 原始级别 | 新标准级别 | 状态 |
|---------|:---:|:---:|:---:|
| F1（diff/snapshot/rollback 全部通过） | PASS | PASS（维持） | ✅ |
| P2（skill_files 字段命名歧义） | P2 | **SUGGESTION** | → 即 F-DATA-02 |
| P3（计数口径不统一） | P3 | **SUGGESTION** | → 合并入 F-DATA-02 |
| P3（快照保留策略不匹配 keep:5） | P3 | **已修复** | → 配置已更新为 keep:13（91天覆盖） |

---

## 5. 发布门禁检查

按标准 §10 发布门禁：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 条件 | 状态 |
|------|:---:|
| BLOCKER = 0 | ✅ |
| 安全漏洞 = 0 | ✅（curator 内部工具，无外部攻击面） |
| 无未裁定的申诉 | ✅ |

**结论**：✅ **可发版**。TC-DATA-08（LLM 合并）暂缓不影响发布——consolidation 当前关闭，生产无影响。

---

## 6. 已知问题

| # | 内容 | 影响 | 发版标注 |
|---|------|------|:---:|
| KI-1 | manifest 缺少 `run_number` 字段（F-DATA-01） | 回滚选快照依赖 `created_at` 而非强排序 | 建议 |
| KI-2 | TC-DATA-08（LLM 合并）未执行 | 当前 consolidate=false，无生产影响 | 不适用 |

---

## 7. 与测试方案的偏差

| 偏差 | 说明 |
|------|------|
| TC-DATA-08 未执行 | Staging 环境不可用，consolidate=false。不影响发布门禁 |
| backup.keep 值 | 测试方案假设 keep:5（35天覆盖），实际为 keep:13（91天覆盖）。原始 P3 发现已自动修复 |
| 未检查 `.bundled_manifest`、`.curator_state`、`.usage.json` | 这些内部状态文件在快照中包含且通过 diff 覆盖，但未逐字段校验——超出测试方案范围 |

---

## 8. 建议

1. **（MINOR）** 在 manifest.json 中增加 `run_number` 字段，每次 curator 运行后自增。这是低成本改进，可消除回滚排序的不确定性。

2. **（SUGGESTION）** 考虑重命名 `manifest.skill_files` 为 `skill_count` 或 `total_skills`（需 breaking change 管理）。

3. **（SUGGESTION）** 在 manifest 中增加 `prompt_hashes` 或类似机制，使快照之间的 cron job prompt 变更可审计（区分故意的更新 vs 意外损坏）。

4. **（待办）** 当 staging 环境就绪时执行 TC-DATA-08（LLM 合并测试）。

---

## 版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-07-08 | 初始版本。Phase 1（TC-DATA-01~07）全部执行完毕，Phase 2（TC-DATA-08）暂缓。 | game-qa |
