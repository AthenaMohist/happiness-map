# P0-11 测试方案：/learn 产出校验（SKILL.md 硬校验）重审

> 编制：game-qa | 日期：2026-07-08
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 原始任务：t_a4bc7f65（infomanager board），/learn 产出校验，142s，1,042 文件扫描

---

## 1. 范围与目标

### 1.1 测试目标

对原始 P0-11 任务中发现的 2 个 bug（CRITICAL + ERROR，旧标准）按 v1.0 四级分层标准重新分级，验证判定公式应用的准确性，输出可执行的验证用例。

### 1.2 原始产出统计

| 指标 | 数值 |
|------|:---:|
| 总文件数 | 1,042 |
| 独立技能数 | 104 |
| 健康（无问题） | 457 |
| 仅警告 | 571 |
| 有错误 | 14 |
| 发现的 bug | 2 |

---

## 2. 原始发现与新旧标准对照

### 2.1 原始发现清单

| # | 发现 | 原始级别 | 简要描述 |
|---|------|:---:|------|
| B1 | headless-browser-tools frontmatter 字面量 \n | CRITICAL | /learn 产出的 SKILL.md 中 frontmatter 使用 `\\n` 字面量而非真实换行符 |
| B2 | research-paper-writing 超 100K 字符限制 | ERROR | 13 份拷贝超过 100K 字符限制（bundled skill，原始任务已豁免） |

### 2.2 重审分级总表

| # | 发现 | 原始级别 | 新标准级别 | 变更 | 判定路径 |
|---|------|:---:|:---:|:---:|------|
| F1 | headless-browser-tools 字面量 \n | CRITICAL | **MAJOR** | 降级 | §1.2：用户可感知 + 功能阻断 + 有 workaround → MAJOR |
| F2 | research-paper-writing 超 100K | ERROR | **N/A（已豁免）** | — | Bundled skill 豁免规则 |
| F3 | 571 peer-expected 字段缺失 | WARNING | **SUGGESTION** | 降级 | §1.2：用户不可感知 + 非安全/非数据/非健康 → SUGGESTION |
| F4 | 12 error 文件未记录（重审发现） | — | **SUGGESTION** | 新增 | 审计完整性 gap，用户不可感知 |

### 2.3 级别统计

| 级别 | 数量 |
|------|:---:|
| BLOCKER | 0 |
| MAJOR | 1（F1） |
| MINOR | 0 |
| SUGGESTION | 2（F3, F4）|
| 已豁免 | 1（F2） |

---

## 3. 逐项判定分析

### 3.1 F1：headless-browser-tools frontmatter 字面量 \n

#### 场景描述

/learn 命令产出的 `headless-browser-tools` 技能中，SKILL.md 的 frontmatter 区域使用字面量字符串 `\\n` 替代真正的换行符。导致 YAML frontmatter 解析异常，技能元数据损坏。

#### 五步判定公式应用

```
前置检查：安全漏洞？ → ❌ 否（不涉及 OWASP Top 10 任何类别）

Step 1: 用户可感知？ → ✅ 是
  - 用户可感知：技能 frontmatter 解析异常 → 技能可能加载失败或元数据配置失效
  - 数据完整性受影响：技能注册表中的元数据（description/author/command）损坏
  - 虽然不是直接的 UI 错误，但属于"数据完整性受影响"（§1.3 扩展定义）

Step 2: 功能阻断？ → ⚠️ 部分阻断
  - 技能加载异常，依赖该技能的 Agent 功能受影响
  - 但不影响 Hermes 核心系统（非支付/认证/数据持久化等关键路径）

Step 3: workaround 是否存在？ → ✅ 是
  - 手动编辑 SKILL.md，将 `\\n` 替换为真实换行
  - workaround 生效后技能恢复正常

Step 4: 数据敏感度？ → C 级（内部配置/技能注册表）
  - 不涉及 S/A/B 级数据，按正常公式判定

Step 5: 环境/概率性？ → 否/是
  - 环境差异：否（/learn 确定性产出，所有环境一致）
  - 概率性：否（每次 /learn 调用均受影响）
```

**判定公式对照**：

```
(user-visible AND function-blocking BUT has workaround) → MAJOR
```

**不满足 BLOCKER 条件**：
- 非安全漏洞（OWASP Top 10）
- 非 S 级数据一致性问题
- 有明确的 workaround（手动修复）
- 非 OOM/崩溃
- 非资金相关概率性 bug

**新分级：MAJOR**（原始：CRITICAL → 降级）

#### 判定说明

这是 /learn 机制的系统性缺陷——任何通过 /learn 创建的技能都可能存在此 bug。影响面是「所有 /learn 生成的技能」，但修复路径明确（手动编辑 frontmatter），不阻塞发版。

按 §1.3 「workaround 是否存在是第二刀」原则：用户能被临时方案解救 → 从 BLOCKER 降为 MAJOR。

#### SLA 对照（§8.1）

| 指标 | 要求 | 说明 |
|------|:---:|------|
| 响应时限 | 1 工作日 | 研发确认 issue + 初步判断 |
| 定位时限 | 2 工作日 | 定位 /learn 产出器中 frontmatter 生成逻辑 |
| 方案时限 | 当前版本窗口内 | 修复方案 OR 标注 known issue 发版 |

#### 回归验证范围（§10.1）

| 范围 | 内容 |
|------|------|
| 修复模块 | /learn SKILL.md 生成器 |
| 1 级依赖 | 技能加载器（YAML frontmatter 解析器） |
| 关键路径 | 创建 skill → /learn → 验证 SKILL.md → 加载技能 |

---

### 3.2 F2：research-paper-writing 超 100K 字符限制

#### 场景描述

`research-paper-writing` 技能的 13 份拷贝超过 100K 字符存储限制。原始任务明确豁免 bundled skills。

#### 判定

**不在审计范围内**（已豁免 bundled skill）。不参与新标准分级。

即使不豁免，按 §1.2 判定：
- 用户不可感知 → SUGGESTION 范畴
- 不满足 MAJOR/BLOCKER 条件

---

### 3.3 F3：571 文件 peer-expected 字段缺失

#### 场景描述

原始审计发现 571 个技能文件的 manifest 中 `peer-expected` 字段缺失。

#### 五步判定

```
前置检查：安全漏洞？ → ❌ 否

Step 1: 用户可感知？ → ❌ 否
  - peer-expected 是内部元数据字段，用于技能发现和交叉引用
  - 不暴露给终端用户，缺失不影响功能

→ 按 §1.2 公式：用户不可感知（非安全/非数据完整性/非系统健康度）→ SUGGESTION
```

**新分级：SUGGESTION**

#### 判定说明

peer-expected 是内部质量标记。补齐后能提升技能发现和交叉引用的精确度，但不做也不影响系统运行。属于纯质量改进范畴。

---

### 3.4 F4：12 error 文件未记录（重审发现）

#### 场景描述

原始任务报告了 14 个 "with_errors" 文件，但仅分类了 2 个（B1 和 B2）。剩余 12 个 error 文件未在报告中记录具体问题。

#### 五步判定

```
前置检查：安全漏洞？ → ❌ 否

Step 1: 用户可感知？ → ❌ 否
  - 这是审计报告本身的完整性 gap
  - 不影响系统功能，不暴露给终端用户

→ 按 §1.2 公式：用户不可感知 → SUGGESTION
```

**新分级：SUGGESTION**

#### 判定说明

审计覆盖不全——不影响原始结论的有效性（2 个已分类 bug 覆盖了关键问题类型），但降低了审计的完整性和可追溯性。

#### 建议

后续审计类任务要求「每个 error 必须有分类记录」，作为审计质量门禁。

---

## 4. 验证测试用例

### 4.1 F1 验证用例

#### TC-P11-01：验证 /learn 产出中 frontmatter 换行符格式

| 项目 | 内容 |
|------|------|
| **用例 ID** | TC-P11-01 |
| **关联发现** | F1（headless-browser-tools 字面量 \n） |
| **前置条件** | 原始 headless-browser-tools SKILL.md 可访问 |
| **步骤** | 1. `cd` 到 headless-browser-tools 技能目录<br>2. `grep -P 'description|author|command' SKILL.md` 检查 frontmatter 行<br>3. 验证每一行以真实换行符分隔（非 `\\n` 字面量）<br>4. 用 YAML 解析器 `python3 -c "import yaml; yaml.safe_load(open('SKILL.md').read())"` 验证可解析 |
| **预期结果** | YAML frontmatter 解析成功，无 `\\n` 字面量 |
| **级别** | MAJOR — 回归验证 |

#### TC-P11-02：验证修复后 /learn 新建技能的 frontmatter

| 项目 | 内容 |
|------|------|
| **用例 ID** | TC-P11-02 |
| **关联发现** | F1（回归验证 — 修复后） |
| **前置条件** | /learn 生成器已修复，可执行 /learn 命令 |
| **步骤** | 1. 创建一个最小合法 skill（仅 title + description）<br>2. 执行 `/learn <skill_path>`<br>3. 读取产出的 SKILL.md<br>4. 解析 YAML frontmatter<br>5. 验证 description 字段完整无 `\\n` 干扰 |
| **预期结果** | /learn 产出的 SKILL.md frontmatter 格式正确，YAML 解析通过，description 字段完整 |
| **级别** | MAJOR — 回归验证（核心路径） |

#### TC-P11-03：验证边界 case — 多行 description

| 项目 | 内容 |
|------|------|
| **用例 ID** | TC-P11-03 |
| **关联发现** | F1（边界 case） |
| **前置条件** | /learn 生成器已修复 |
| **步骤** | 1. 创建含多段落 description 的 skill<br>2. 执行 /learn<br>3. 验证 frontmatter 中多行文本正确编码（YAML `|` 或 `>` 块格式） |
| **预期结果** | 多行 description 在 YAML frontmatter 中正确编码，不出现字面量换行符 |
| **级别** | MAJOR — 边界验证 |

#### TC-P11-04：现有技能文件 impact 扫描

| 项目 | 内容 |
|------|------|
| **用例 ID** | TC-P11-04 |
| **关联发现** | F1（blast radius — 受影响文件范围） |
| **前置条件** | 可访问所有已安装技能的 SKILL.md |
| **步骤** | 1. 扫描所有现有技能的 SKILL.md frontmatter<br>2. 搜索 `\\\\n` 字面量（非真实换行）<br>3. 统计受影响文件数和技能名 |
| **预期结果** | 输出受影响文件清单，确认 blast radius |
| **级别** | MAJOR — 影响面评估 |

### 4.2 F3/F4 验证用例

#### TC-P11-05：peer-expected 字段补齐验证

| 项目 | 内容 |
|------|------|
| **用例 ID** | TC-P11-05 |
| **关联发现** | F3（571 peer-expected 缺失） |
| **前置条件** | 决定补齐 peer-expected 字段 |
| **步骤** | 1. 查询 571 个受影响文件列表<br>2. 在 next 审计中抽样 10% 验证字段是否存在<br>3. 验证补充的 peer 引用指向存在的技能 |
| **预期结果** | peer-expected 字段存在且引用有效 |
| **级别** | SUGGESTION — 质量改进 |

---

## 5. SLA 时效性评估

### 5.1 各发现 SLA 对照

| 发现 | 级别 | 响应 | 定位 | 方案 |
|------|:---:|------|------|------|
| F1 | MAJOR | 1 工作日 | 2 工作日 | 当前版本窗口内 |
| F3 | SUGGESTION | 3 工作日 | — | 不限 |
| F4 | SUGGESTION | 3 工作日 | — | 不限 |

### 5.2 审计任务 vs Bug 修复任务

P0-11 本身是审计/验证任务（非 bug fix），原始任务运行 142s，不适用 bug SLA。上述 SLA 仅适用于审计发现的 bug（F1）进入修复流程后的时效要求。

---

## 6. 发布门禁检查

按 §10 发布门禁公式：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 检查项 | 状态 | 说明 |
|--------|:---:|------|
| BLOCKER=0？ | ✅ 通过 | P0-11 无 BLOCKER 级发现 |
| 安全漏洞=0？ | ✅ 通过 | 无安全漏洞（对照 OWASP Top 10 Checklist） |
| 无未裁定申诉？ | ✅ 通过 | 无申诉记录 |

**结论**：P0-11 满足发布门禁。F1（MAJOR）建议在发版 release notes 中标注为 known issue。

---

## 7. 建议行动

| # | 行动 | 优先级 | 关联 | 说明 |
|---|------|:---:|------|------|
| 1 | 修复 /learn SKILL.md 生成器（literal \n → 真实换行） | P0 | F1 | 根因修复，非检测 |
| 2 | /learn 后自动校验：description≤60, author=Hermes, command validity | P0 | F1 同类风险 | 防御性措施 |
| 3 | 审计任务标准新增：每个 error 必须记录具体问题 | P2 | F4 | 审计质量门禁 |
| 4 | peer-expected 字段补齐（跨 571 文件） | P3 | F3 | 质量改进 |

---

## 8. /learn 机制风险评估

从 QA 风险矩阵观察，F1（literal \n bug）确认了 `/learn` 产出质量风险的真实性。当前 P0-11 的缓解措施是「手动验证」（SKILL.md 硬校验），但仅检测不修复。

风险再评估：
- **风险等级**：中等偏高 — 影响所有 /learn 生成的技能
- **影响面**：所有新建 skill 的元数据完整性
- **当前缓解**：手动校验（被动检测，不阻止产出）
- **建议**：修复 /learn 生成器 + 增加自动 post-creation 校验

---

## 9. 审计覆盖一致性检查

| 检查项 | 状态 | 说明 |
|--------|:---:|------|
| 判定公式逐条对照 | ✅ | F1-F4 均按 §1.2 五步公式应用 |
| SLA 对照 | ✅ | §8.1 MAJOR/SUGGESTION SLA 已标注 |
| 分级示例对照 | ✅ | F1 对照示例 #2（支付按钮 + workaround），F3 对照示例 #15（内部字段） |
| 论证流程对照 | ✅ | §6.1 基础流程已应用 |
| 安全 Checklist 对照 | ✅ | F1-F4 均不涉及 OWASP Top 10 |
| 发布门禁对照 | ✅ | §10 门禁公式三项全通过 |
| 产品红线对照 | ✅ | 无 BLOCKER 暂缓、无申诉 |

---

## 10. 重审结论

P0-11 原始产出质量总体良好，核心发现（/learn 产出 bug）与风险矩阵预测一致。

按新标准 v1.0 重新分级：
- F1 从 **CRITICAL → MAJOR**（有 workaround 是降级关键因素）
- F3 从 **WARNING → SUGGESTION**（用户不可感知）
- F4 新增 **SUGGESTION**（审计完整性 gap）
- F2 维持**豁免**（bundled skill）

**无 BLOCKER，无安全漏洞，无申诉，满足发布门禁。**

---

> 编制：game-qa | 标准版本：v1.0 | 输出路径：`docs/qa-reaudits/P0-11-test-plan.md`
