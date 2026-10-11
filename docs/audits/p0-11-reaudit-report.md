# P0-11 重审报告：/learn 产出校验（SKILL.md 硬校验）

> 重审时间：2026-07-08
> 重审依据：`docs/standards/qa-finding-classification.md` v1.0
> 原始任务：`t_a4bc7f65`（infomanager board），运行 142s，产出 1,042 文件扫描

---

## 1. 原始产出摘要

| 指标 | 数值 |
|------|:---:|
| 总文件数 | 1,042 |
| 独立技能数 | 104 |
| 健康（无问题） | 457 |
| 仅警告 | 571 |
| 有错误 | 14 |
| 发现的 bug | 2 |

**原始 bug 列表**：
- B1（CRITICAL）：`headless-browser-tools` — frontmatter 使用字面量 `\n` 而非真实换行（根因：/learn 输出 bug）
- B2（ERROR）：`research-paper-writing` — 13 份拷贝超过 100K 字符限制（已豁免，bundled skill）

**边界 case 验证**：最小 skill 创建→校验全流程通过 ✅

---

## 2. 按新标准重新分级

### 2.1 F1：headless-browser-tools frontmatter 字面量 \n

| 判定维度 | 评估 |
|---------|------|
| 是否安全漏洞？ | ❌ 否（不涉及 OWASP Top 10） |
| 用户可感知？ | ✅ 是 — 技能 frontmatter 解析异常 → 技能可能加载失败或元数据错误 |
| 功能阻断？ | ⚠️ 部分阻断 — 技能加载异常，但不影响系统核心功能 |
| 有 workaround？ | ✅ 是 — 手动编辑 SKILL.md，将 `\\n` 替换为真实换行 |
| 数据敏感度 | C 级（内部配置/技能注册表） |
| 是否概率性？ | ❌ 否（/learn 确定性产出） |
| 环境相关？ | ❌ 否 |

**判定公式对照**：
```
(user-visible AND function-blocking BUT has workaround) → MAJOR
```
不满足 BLOCKER 条件：
- 非安全漏洞
- 非 S 级数据一致性问题
- 有明确的 workaround（手动修复）
- 非 OOM/崩溃
- 非资金相关概率性 bug

**新分级：MAJOR**（原始：CRITICAL）

**判定说明**：这是 /learn 机制产出的系统性问题——任何通过 /learn 创建的技能都可能存在此缺陷。影响面是「所有 /learn 生成的技能」，但修复路径明确（手动编辑），不阻塞发版。属于 MAJOR：用户可感知（技能元数据损坏）且影响功能（技能无法正常加载），但有 workaround。

**SLA 对照**：
- 响应：1 工作日
- 定位：2 工作日
- 方案：当前版本窗口内

**推荐处理**：修复 /learn 的 SKILL.md 生成器，确保 frontmatter 中使用真实换行符。修复后需定向回归测试 /learn 产出（创建 skill→验证 frontmatter 格式）。

---

### 2.2 F2：research-paper-writing 超 100K 字符限制

| 判定维度 | 评估 |
|---------|------|
| 豁免状态 | ✅ 原始任务明确豁免 bundled skills |
| 用户可感知？ | ❌ 否（技能功能正常，仅内部存储超限） |

**结论：不在审计范围内**（已豁免 bundled skill）

即使不豁免，按新标准判定：
- 用户不可感知 → 按 §1.2 归入 SUGGESTION 范畴
- 不满足 MAJOR/BLOCKER 条件

---

### 2.3 F3：571 文件 peer-expected 字段缺失（警告）

| 判定维度 | 评估 |
|---------|------|
| 用户可感知？ | ❌ 否（内部元数据字段，不暴露给用户） |
| 功能阻断？ | ❌ 否 |
| 安全相关？ | ❌ 否 |
| 数据完整性？ | ⚠️ 轻微 — 缺失的元数据可能导致技能发现/推荐不准 |

**判定公式对照**：
```
用户不可感知（非安全/非数据完整性/非系统健康度）OR 纯主观偏好 → SUGGESTION
```

**新分级：SUGGESTION**

**判定说明**：peer-expected 字段是内部质量标记，不影响用户可见功能。补齐后能提升技能发现和交叉引用的精确度，但不做也不影响系统运行。属于纯质量改进范畴。

---

### 2.4 未分类的 12 个 error 文件

**新发现（重审中识别）**：原始任务报告了 14 个 "with_errors" 文件，但仅分类了 2 个。剩余 12 个 error 文件未在报告中记录具体问题。

**判定**：这是原始审计的**覆盖不全**问题。属 SUGGESTION 级别——不影响原始任务的结论有效性（2 个已分类的 bug 覆盖了关键问题），但降低了审计的完整性和可追溯性。

**追踪建议**：如果原始 workspace 已清理（scratch workspace），无法恢复数据。建议后续审计类任务要求「每个 error 必须有分类记录」，作为审计质量门禁。

---

## 3. 综合重审结论

| # | 发现 | 原始级别 | 新标准级别 | 变化 | 依据条款 |
|---|------|:---:|:---:|:---:|------|
| F1 | headless-browser-tools 字面量 \n | CRITICAL | **MAJOR** | 降级 | §1.2: 有 workaround，非安全漏洞 |
| F2 | research-paper-writing 超 100K | ERROR | **N/A（已豁免）** | — | Bundled skill 豁免规则 |
| F3 | 571 peer-expected 缺失 | WARNING | **SUGGESTION** | 降级 | §1.2: 用户不可感知 |
| F4 | 12 error 文件未记录 | — | **SUGGESTION** | 新增 | 审计完整性 gap |

### 级别统计

| 级别 | 数量 |
|------|:---:|
| BLOCKER | 0 |
| MAJOR | 1（F1） |
| MINOR | 0 |
| SUGGESTION | 2（F3, F4） |
| 已豁免 | 1（F2） |

### 发布门禁判定

按 §10 发布门禁标准：BLOCKER=0 AND 安全漏洞=0 → **满足发布条件**。F1（MAJOR）建议在发版 release notes 中标注为 known issue。

---

## 4. 附加评估

### 4.1 /learn 机制风险评估

P0-11 的核心价值不在于「发现有问题的 skill」，而在于**暴露了 /learn 机制的产出质量风险**。从 QA 风险矩阵（`memory-qa-risks.md`）来看：

| 风险 # | 描述 | RPN | 当前状态 |
|--------|------|:---:|------|
| #2 | /learn produces broken SKILL.md | 30 | ⚠️ F1 已确认，F4 暗示可能还有更多 |

F1（literal \n bug）确认了 risk #2 的真实性。P0-11 在此风险上的缓解措施是「手动验证」（SKILL.md 硬校验），但这只是检测手段，不是根因修复。

**建议**：将 /learn 机制修复（而非仅检测）提升为独立任务，纳入 P1（本周）。

### 4.2 原始审计质量评估

- ✅ 扫描覆盖面充分（1,042 文件，104 独立技能）
- ✅ 边界 case 验证通过
- ⚠️ 14 个 error 中仅 2 个有详细记录（F4）
- ⚠️ 使用了「CRITICAL」而非标准四级分级（当时标准尚未制定）

### 4.3 SLA 时效性对照

P0-11 不是 bug fix 任务，而是审计/验证任务。原始任务运行 142s，不适用 bug SLA。

---

## 5. 建议行动项

| # | 行动 | 优先级 | 关联 |
|---|------|:---:|------|
| 1 | 修复 /learn SKILL.md 生成器（literal \n → 真实换行） | P0 | F1 |
| 2 | 补全 /learn 后自动校验：description≤60, author=Hermes, command validity | P0 | F1 同类风险 |
| 3 | 审计任务标准新增：每个 error 必须记录具体问题 | P2 | F4 |
| 4 | peer-expected 字段补齐（跨 571 文件） | P3 | F3 |

---

> 重审结论：P0-11 原始产出质量总体良好，核心发现（/learn 产出 bug）与风险矩阵预测一致。按新标准，F1 从 CRITICAL 降为 MAJOR（有 workaround），F3 从 WARNING 降为 SUGGESTION（用户不可见）。新增 1 个 SUGGESTION（F4：审计覆盖不全）。无 BLOCKER/安全漏洞/申诉，满足发布门禁。
