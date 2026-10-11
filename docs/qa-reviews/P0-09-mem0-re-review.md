# P0-09 mem0 结果校验 — QA 重审报告

> 依据：`docs/standards/qa-finding-classification.md` v1.0
> 旧报告来源：session `20260708_010626_adc379` / `20260707_223417_7c8cc7`（infomanager 板）
> 旧报告文件：`/root/.hermes/kanban/boards/infomanager/workspaces/t_5e0fa943/test_mem0.py`
> 重审时间：2026-07-08

---

## 1. 旧报告摘要

P0-09 原始测试在 8 条英文记忆 + Qdrant (local) + fastembed/bge-small-en-v1.5 (384-dim) + SQLite FTS5 环境下进行。测试分 4 套：

| 测试套 | 结果 | 关键数据 |
|--------|:---:|---------|
| Score 阈值 | 8/8 PASS | top-1 正确识别 InfoManager；threshold 0.6 过滤正确 |
| FTS5 关键词 | 3/3 PASS | 英文关键词命中 + 非匹配词正确返回空 |
| 语义-FTS5 交叉验证 | 1/1 PASS | 两种方式 top results 有交集 |
| 边界 case | 2/2 PASS | 零向量返回 ≈0；无关查询与相关查询 score gap > 0.1 |

**旧报告未使用正式分级框架** — 发现以 critical/high/medium/low 标记，以及 "known limitation" 标注。

更大规模的测试（67 测试，15 记忆，12 已知查询，6 FP）发现：
- top-1 范围 0.68–0.91，FP max 0.58，gap 0.33
- 推荐阈值 top-1 ≥ 0.60（不是默认的 0.25）
- bge-small-en-v1.5 中文噪声：4/8 FPs 匹配同一条中文记忆

---

## 2. 新旧标准差异分析

### 2.1 旧报告的"分级"方式

旧报告使用临时性的严重度标签：

| 旧标签 | 对应旧语义 |
|--------|-----------|
| critical | 默认阈值错误会导致搜索质量崩溃 |
| high | 中文噪声影响跨语言搜索 |
| medium | FTS5 中文 0% 召回 |
| low / known limitation | 单字符/特殊字符噪声 |

**旧标准没有**：正式的判定公式、安全漏洞独立判定路径、数据敏感度加权、性能量化阈值。

### 2.2 新标准的差异

| 维度 | 旧标准（隐含） | 新标准 v1.0 | 对 P0-09 的影响 |
|------|:---:|---|------|
| 分级框架 | 临时 4 标签 | BLOCKER/MAJOR/MINOR/SUGGESTION + 判定公式 | 旧 "critical" 重新判定为 MAJOR |
| 安全漏洞 | 无独立路径 | OWASP Top 10 独立判定，最低 MAJOR | P0-09 不涉及安全 → 无影响 |
| 数据敏感度 | 未区分 | S/A/B/C 四级加权 | P0-09 不涉及敏感数据 → 无影响 |
| 性能量化 | 无 | 3x/10x 相对阈值 + fallback 1s/5s | mem0 搜索延迟未测量 → 无影响 |
| Workaround 判定 | 无 | BLOCKER → MAJOR 降级条件 | F1/F5 因 workaround 存在而降级 |
| 用户可感知过滤 | 无 | SUGGESTION 门禁 | F4 被过滤到 SUGGESTION |

---

## 3. 旧发现重新分级

### F1: 默认 score 阈值 0.25 导致 100% 假阳性通过

**旧级别**: critical（未用标准分级）
**新级别**: **MAJOR**

**判定公式对照** (§1.2):

```
前置检查:
  └─ 安全漏洞？ → 否 → 进入正式判定

正式判定:
  BLOCKER? → 用户可感知 ✓ + 功能阻断? ✗（搜索仍返回结果，只是不对）
  MAJOR?  → 用户可感知 ✓ + 体验严重退化 ✓（返回完全不相关的结果，置信度崩溃）
  → MAJOR
```

**关键论证**:
- 用户可感知：是 — 用户搜 "cooking recipes" 得到 "SiliconFlow proxy configuration"
- 体验严重退化：是 — 搜索质量相当于随机，用户对系统的信任感崩溃
- Workaround 存在：是 — 阈值改为 top-1 ≥ 0.60 完美分离
- 不涉及 S 级/A 级数据 → 不触发加权
- 非安全漏洞

**与 §5 分级示例对照**:
- 最接近 §5 #9 "列表页加载从 100ms 恶化到 1s" (MAJOR) — 功能可用但体验量化退化
- 不同于 §5 #1 (BLOCKER) — 支付按钮无响应 = 功能阻断；此处搜索仍返回结果

**变更说明**: 旧 report 标为 "critical" — 在新标准下，由于存在 workaround（改阈值），不符合 BLOCKER 条件，降为 MAJOR。

---

### F2: bge-small-en-v1.5 中文 embedding 产生噪声向量（4/8 FPs 匹配同一条中文记忆）

**旧级别**: high（未用标准分级）
**新级别**: **MAJOR**

**判定公式对照** (§1.2):

```
前置检查:
  └─ 安全漏洞？ → 否

正式判定:
  MAJOR? → 用户可感知 ✓（中文/跨语言用户搜索质量差）
           + 体验严重退化 ✓（中英混合语料下中文记忆成为"万能匹配"噪声源）
  → MAJOR
```

**关键论证**:
- 用户可感知：是 — 中文用户使用英文查询时，top match 是中文无关记忆
- 体验严重退化：是 — 中文记忆在英文查询空间中 cos similarity 偏高，形成系统性噪声
- 非功能阻断 — 单语场景（纯英文/纯中文）不受影响
- 非安全隐患
- 这是模型选择/能力问题，不是代码 bug

**环境差异考量** (§1.3): 不因 "仅中文场景受影响" 而降级（"环境差异不降级"）。

**与 §5 分级示例对照**:
- 最接近 §5 #17 "列表页偶发白屏，刷新后恢复" (MAJOR) — 偶尔出现 + 有替代方案（用更好的 embedder）

**变更说明**: 旧 report 标为 "high" — 新标准下确认为 MAJOR，定性一致。但需注意这不是代码 bug 而是模型能力限制。

---

### F3: FTS5 无 CJK 分词器 — 中文关键词搜索 0% 召回

**旧级别**: medium（未用标准分级）
**新级别**: **MAJOR**

**判定公式对照** (§1.2):

```
前置检查:
  └─ 安全漏洞？ → 否

正式判定:
  MAJOR? → 用户可感知 ✓（中文关键词搜索完全无效）
           + 功能阻断但有 workaround ✓（可以用语义搜索代替）
  → MAJOR
```

**关键论证**:
- 用户可感知：是 — 中文关键词搜索返回空结果
- 部分功能阻断：是 — 关键词搜索路径对中文完全不可用
- Workaround 存在：是 — 语义搜索对中文仍可用
- 这是 SQLite FTS5 固有限制，不是产品 bug

**与 §5 分级示例对照**:
- 最接近 §5 #2 "支付按钮无响应，但手动输入金额可绕过" (MAJOR) — 功能阻断 + 有 workaround

**变更说明**: 旧 report 标为 "medium" — 新标准下确认为 MAJOR（功能路径阻断 + 有替代路径）。

---

### F4: mem0 完整 LLM pipeline 未测试

**旧级别**: limitation（未用标准分级）
**新级别**: **SUGGESTION**

**判定公式对照** (§1.2):

```
前置检查:
  └─ 安全漏洞？ → 否

正式判定:
  用户可感知? ✗ — 这是测试覆盖问题，不影响用户可见行为
  数据完整性? ✗
  系统健康度? ✗
  → SUGGESTION
```

**关键论证** (§1.3):
- "用户可感知"是第一刀 → 用户完全不可感知这是一个测试 gap
- 这是内部质量改进事项，不属于产品缺陷
- 不做不阻塞发版，做了提升测试覆盖置信度

**与 §5 分级示例对照**:
- 对应 §5 #15 "变量命名 x 应改为 userCount" (SUGGESTION) — 用户不可感知 + 纯内部层面

**变更说明**: 旧 report 标为 "limitation" — 新标准下此发现不满足 MAJOR/MINOR 的"用户可感知"门槛，归为 SUGGESTION。

---

### F5: Qdrant 维度不匹配 — 默认配置 1536d 与 fastembed 384d 冲突

**旧级别**: 未单独分级（在测试日志中以 config fix 形式记录）
**新级别**: **BLOCKER**

**判定公式对照** (§1.2):

```
前置检查:
  └─ 安全漏洞？ → 否

正式判定:
  BLOCKER? → 用户可感知 ✓（mem0 完全无法存储/搜索）
            + 功能阻断 ✓（add/search 全部失败，无返回）
            + 无 workaround ✓（默认配置下用户无法自救，必须改代码/配置）
  → BLOCKER
```

**关键论证**:
- 用户可感知：是 — 任何依赖 mem0 的功能全部不可用
- 功能阻断：是 — `Memory.add()` 和 `Memory.search()` 均抛异常
- 无 workaround：是 — 普通用户无法修改 Qdrant 配置
- 即使用户是开发者，也需要理解 embedding model dims 才能修复 — 这不是合理的 workaround
- 非安全漏洞，不涉及敏感数据

**为何不是 MAJOR**:
- MAJOR 需要 "有 workaround" — 这里默认配置就 broken，用户无路可退
- 影响范围是 mem0 全部功能 = 系统性阻断

**与 §5 分级示例对照**:
- 最接近 §5 #1 "支付按钮点击无响应，无替代支付路径" (BLOCKER) — 核心功能路径完全阻断，无 workaround

**变更说明**: 此发现未被旧报告正式分级，标注在测试日志中。新标准下确认为 BLOCKER — 默认配置导致系统完全不可用。

---

## 4. 分级汇总

| # | 发现 | 旧级别 | 新级别 | 变更方向 | 关键差异 |
|---|------|:---:|:---:|:---:|---------|
| F1 | 默认阈值 0.25 太低 | critical | **MAJOR** | critical → MAJOR | 有 workaround（改阈值），不满足 BLOCKER 的无 workaround 条件 |
| F2 | 中文 embedding 噪声 | high | **MAJOR** | 定性一致 | 新标准确认为 MAJOR，框架更正式 |
| F3 | FTS5 无 CJK 分词 | medium | **MAJOR** | medium → MAJOR | 新标准以 "功能阻断但有 workaround" 升级 |
| F4 | 完整 pipeline 未测试 | limitation | **SUGGESTION** | limitation → SUGGESTION | 不满足"用户可感知"门槛，降为 SUGGESTION |
| F5 | Qdrant 维度不匹配 | (未分级) | **BLOCKER** | 未分级 → BLOCKER | 默认配置即失败 = 功能阻断 + 无 workaround |

### 统计

- BLOCKER: 1 (F5)
- MAJOR: 3 (F1, F2, F3)
- MINOR: 0
- SUGGESTION: 1 (F4)

---

## 5. SLA 对照

> 注意：旧报告发现的是测试环境中的配置问题/模型限制，非生产环境已部署 bug。以下 SLA 分析基于 "如果在生产环境中发现" 的前提。

| 发现 | 级别 | 响应时限 | 定位时限 | 方案时限 | 当前状态 |
|------|:---:|:---:|:---:|:---:|------|
| F5: 维度不匹配 | BLOCKER | 4h | 8h 初步判定 | 24h 方案 | 测试中已 fix（显式设置 embedding_model_dims=384） |
| F1: 默认阈值 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 测试中已识别正确阈值 0.60 |
| F2: 中文噪声 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 推荐升级 multilingual embedder（未执行） |
| F3: FTS5 CJK | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 已知 SQLite 限制，短期用语义搜索代替 |

**F5 SLA 状态**: 已在测试阶段修复 → SLA 不适用（非生产发现）。
**F1 SLA 状态**: 阈值参数调整 → 修复成本极低，可即时完成。

---

## 6. 发布门禁影响 (§10)

如 P0-09 相关代码需要发布：

| 发现 | 级别 | 审查要求 | 测试要求 |
|------|:---:|---------|---------|
| F5 | BLOCKER | ✅ 第二人 review | staging smoke test |
| F1 | MAJOR | ✅ 推荐 review | staging 回归（核心搜索路径） |
| F2 | MAJOR | ✅ 推荐 review | staging 回归（中英混合搜索路径） |
| F3 | MAJOR | ✅ 推荐 review | staging 回归（中文关键词搜索路径） |

**实际建议**: F5 已 fix，F1 阈值调整简单。F2/F3 涉及模型/基础设施变更，建议记录为 known issue 而非阻塞发布。

---

## 7. 申诉风险评估

| 发现 | 级别 | 被驳回风险 | 分析 |
|------|:---:|:---:|------|
| F5 | BLOCKER | 低 | 技术事实明确，默认配置与 embedder 不兼容 |
| F1 | MAJOR | 低 | 数据清晰，0.25 vs 0.60 gap 0.33 可验证 |
| F2 | MAJOR | 中 | 可能被驳回为 "by design — 英文模型不支持中文" |
| F3 | MAJOR | 低 | SQLite 已知限制，无可争议 |
| F4 | SUGGESTION | N/A | 低于申诉门槛 |

---

## 8. 重审结论

1. **旧报告发现基本有效**，在新标准下得到更精确的分级。核心变更是 F5 从 "未分级/config fix" 升级为 BLOCKER。
2. **F5 是唯一 BLOCKER**，但在测试阶段已修复，不影响生产。
3. **F2/F3 是基础设施层面的 MAJOR**，应在技术债务追踪中记录（§12.2 P1 #4），不阻塞当前版本。
4. **旧报告缺失正式分级框架** — 新标准 v1.0 提供了完整的判定公式，使分类可计算、可争议、可追溯。
5. **本次重审未发现安全漏洞**，无需进入 OWASP Top 10 判定路径。

---

## 9. 元数据

| 字段 | 值 |
|------|-----|
| 重审人 | game-qa |
| 标准版本 | qa-finding-classification.md v1.0 |
| 旧报告 task | t_f6800f62 (infomanager 板) |
| 旧报告工件 | `/root/.hermes/kanban/boards/infomanager/workspaces/t_5e0fa943/test_mem0.py` |
| 重审文件 | `docs/qa-reviews/P0-09-mem0-re-review.md` |
| 重审时间 | 2026-07-08T12:50:00+08:00 |
