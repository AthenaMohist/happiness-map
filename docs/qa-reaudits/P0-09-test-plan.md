# P0-09 mem0 结果校验 — 重审测试方案

> 版本：v1.0 | 状态：Draft — 待评审
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 
> 关联重审报告：`docs/qa-reviews/P0-09-mem0-re-review.md`（302 行，已完成分析）
> 旧报告 task：t_f6800f62 (infomanager board)
> 旧报告测试文件：`/root/.hermes/kanban/boards/infomanager/workspaces/t_5e0fa943/test_mem0.py`

---

## 1. 背景与范围

### 1.1 原始任务

mem0 结果校验（score 阈值 + FTS5 交叉验证）——验证 mem0 在 Qdrant + fastembed + SQLite FTS5 环境下的搜索质量。

### 1.2 原始测试范围

| 测试套 | 测试数 | 覆盖内容 |
|--------|:---:|---------|
| Score 阈值 | 8 | 阈值过滤正确性，top-1 识别 InfoManager |
| FTS5 关键词 | 3 | 英文关键词命中，非匹配词返回空 |
| 语义-FTS5 交叉验证 | 1 | 两种方式 top results 有交集 |
| 边界 case | 2 | 零向量返回 ≈0，相关/无关查询 score gap > 0.1 |
| **小计（基线）** | **14** | 初始 14 测试，全部 PASS |
| 大规模验证 | 67 | 15 记忆 + 12 已知查询 + 6 FP，top-1 0.68–0.91，FP max 0.58，gap 0.33 |

### 1.3 重审目标

- 对旧报告的 5 个发现（F1–F5）按新标准 v1.0 重新分级
- 设计验证测试用例，确认每个重新分级判定正确
- 明确发布门禁影响和 SLA 要求

---

## 2. 新旧标准差异

### 2.1 旧分级体系 vs 新标准

P0-09 原始报告使用临时性标签（critical/high/medium/limitation），没有正式判定公式。新标准 v1.0 引入：

| 维度 | 旧标准 | 新标准 v1.0 | 对 P0-09 的影响 |
|------|:---:|------|------|
| 分级框架 | 临时 4 标签 | BLOCKER/MAJOR/MINOR/SUGGESTION + 判定公式（§1.2） | 旧 "critical" 需重新判定 |
| 安全漏洞 | 无独立路径 | OWASP Top 10 独立判定，最低 MAJOR（§2） | P0-09 不涉及 → 无影响 |
| 数据敏感度 | 未区分 | S/A/B/C 四级加权（§4） | P0-09 不涉及 → 无影响 |
| 性能量化 | 无 | 3x/10x 相对阈值或 1s/5s 绝对阈值（§3） | mem0 延迟未测量 → 无影响 |
| Workaround 判定 | 无 | BLOCKER → MAJOR 降级条件（§1.2） | F1/F5 的关键判定差异 |
| 用户可感知过滤 | 无 | SUGGESTION 门禁（§1.3） | F4 被过滤到 SUGGESTION |

### 2.2 判定公式速查（§1.2）

```
前置检查：
  └─ 安全漏洞？ → 是 → 最低 MAJOR，正式判定

正式判定：
  BLOCKER = (用户可感知 AND 功能阻断 AND 无 workaround)
            OR 安全漏洞（OWASP Top 10 重大级）
            OR S 级数据一致性
            OR 性能退化 P95 ≥ 10x
            OR OOM/崩溃

  MAJOR   = (用户可感知 AND (功能阻断但有 workaround OR 体验严重退化))
            OR 安全漏洞（非 BLOCKER 级）
            OR A 级数据一致性
            OR 性能退化 P95 ≥ 3x
            OR PII 泄露

  MINOR   = 用户可感知 AND 不影响核心任务完成
  SUGGESTION = 用户不可感知（非安全/非数据/非健康）OR 纯主观偏好
```

---

## 3. 发现重新分级映射

### 3.1 分级变更汇总

| # | 发现 | 旧级别 | 新级别 | 变更方向 | 判定依据 |
|---|------|:---:|:---:|:---:|---------|
| F5 | Qdrant 维度不匹配 (1536d vs 384d) | 未分级 | **BLOCKER** | 严重升级 | 功能阻断 + 无 workaround |
| F1 | 默认阈值 0.25 → 100% FP | critical | **MAJOR** | 降级 | 有 workaround（改阈值） |
| F2 | bge-small-en 中文噪声 | high | **MAJOR** | 定性一致 | 体验严重退化 |
| F3 | FTS5 无 CJK 分词器 | medium | **MAJOR** | 升级 | 功能阻断但有 workaround |
| F4 | 完整 LLM pipeline 未测试 | limitation | **SUGGESTION** | 降级 | 用户不可感知 |

### 3.2 统计

| 级别 | 数量 | 发现 |
|------|:---:|------|
| BLOCKER | 1 | F5 |
| MAJOR | 3 | F1, F2, F3 |
| MINOR | 0 | — |
| SUGGESTION | 1 | F4 |

---

## 4. 测试用例

### 4.1 测试环境要求

```
依赖: fastembed (BAAI/bge-small-en-v1.5), qdrant-client, sqlite3
环境: Python 3.11+, local Qdrant (path mode)
向量维度: 384 (bge-small-en-v1.5)
距离函数: Cosine
```

### 4.2 测试数据

当前基线测试使用 8 条记忆 + 2 组查询。大规模验证使用 15 条记忆 + 12 已知查询 + 6 FP 查询。

| 数据 | 数量 | 用途 |
|------|:---:|------|
| 记忆条目 | 8 | 基线测试 |
| 记忆条目 | 15 | 大规模阈值校准 |
| 相关查询（已知期望） | 2 / 12 | 验证 top-1 准确性 |
| FP 查询（无关查询） | 0 / 6 | 验证阈值下限 |

---

### TC-F5: Qdrant 维度不匹配 → BLOCKER

**发现**: 默认 QdrantConfig.embedding_model_dims=1536 与 bge-small-en 384d 不兼容，导致 mem0 完全不可用。

**判定路径**:
```
前置：非安全漏洞 → 正式判定
用户可感知 ✓（mem0 全部功能不可用）
功能阻断  ✓（Memory.add() 和 Memory.search() 均抛异常）
无 workaround ✓（默认配置即失败，用户无法自救）
→ BLOCKER
```

#### TC-F5-01: 默认配置复现（基线验证）

| 字段 | 内容 |
|------|------|
| 目的 | 确认默认 1536d 配置导致维度不匹配异常 |
| 前置 | QdrantClient 使用默认 QdrantConfig（不设置 embedding_model_dims） |
| 步骤 | 1. 初始化 TextEmbedding("BAAI/bge-small-en-v1.5") → dims=384<br>2. 创建 QdrantClient 不带显式 vectors_config<br>3. 尝试 upsert 384d 向量 |
| 预期 | 操作失败，异常信息包含维度不匹配 |
| 判定 | 异常 = 确认 BLOCKER 条件的"功能阻断 + 无 workaround" |

#### TC-F5-02: 修复后验证（回归）

| 字段 | 内容 |
|------|------|
| 目的 | 确认显式设置 embedding_model_dims=384 后正常 |
| 前置 | vectors_config=models.VectorParams(size=384, distance=models.Distance.COSINE) |
| 步骤 | 1. 运行完整基线测试套件（14 测试）<br>2. 确认 Memory.add() 正常写入<br>3. 确认 Memory.search() 正常返回 |
| 预期 | 全部 PASS |
| 判定 | PASS = BLOCKER 已修复 |

#### TC-F5-03: 其他 embedder 维度兼容性

| 字段 | 内容 |
|------|------|
| 目的 | 确认切换 embedder 时配置正确同步 |
| 前置 | — |
| 步骤 | 1. 用 bge-small-en (384d) 创建 collection<br>2. 用 bge-large-en (1024d) 向量做 search |
| 预期 | 操作失败，异常信息明确 |
| 判定 | 异常信息有意义 = 用户能诊断问题 → 非静默失败 |

**级别**: BLOCKER
**发布门禁** (§10): ✅ 第二人 review + staging smoke test
**SLA** (§8.1): 响应 4h / 定位 8h 初步判定+进度同步 / 方案 24h（已修复 → 不适用）

---

### TC-F1: 默认阈值 0.25 太低 → MAJOR

**发现**: mem0 默认 score_threshold=0.25，在 bge-small-en 下 100% 假阳性通过。阈值应为 top-1 ≥ 0.60。

**判定路径**:
```
前置：非安全漏洞 → 正式判定
用户可感知 ✓（搜索返回不相关结果）
功能阻断 ✗（搜索仍返回结果，非完全阻断）
体验严重退化 ✓（搜索质量 = 随机）
有 workaround ✓（阈值改为 0.60 完美分离）
→ MAJOR
```

**与 §5 分级示例对照**: #9 "列表页加载 100ms→1s" (MAJOR) — 功能可用但体验退化

#### TC-F1-01: 默认阈值 0.25 假阳性验证

| 字段 | 内容 |
|------|------|
| 目的 | 量化和确认默认阈值的不合理性 |
| 前置 | Qdrant collection 已加载 15 条记忆 |
| 步骤 | 1. 用 6 个 FP 查询（无关查询）进行 semantic search<br>2. score_threshold=0.25<br>3. 统计返回的假阳性数量 |
| 预期 | score_threshold=0.25 下，100% FP 查询返回结果（全部误判为相关） |
| 指标 | FP rate @ threshold=0.25 = 6/6 = 100% |

#### TC-F1-02: 推荐阈值 0.60 真阳性验证

| 字段 | 内容 |
|------|------|
| 目的 | 验证 top-1 ≥ 0.60 的正确性 |
| 前置 | Qdrant collection 已加载 15 条记忆 |
| 步骤 | 1. 用 12 个已知查询（期望匹配特定记忆）进行搜索<br>2. score_threshold=0.60<br>3. 验证 top-1 命中预期记忆 |
| 预期 | top-1 全部命中，top-1 score 范围 [0.68, 0.91] |
| 指标 | precision@1 @ threshold=0.60 = 12/12 = 100% |

#### TC-F1-03: 阈值 0.60 假阳性过滤验证

| 字段 | 内容 |
|------|------|
| 目的 | 验证 0.60 阈值正确过滤 FP |
| 前置 | 同上 |
| 步骤 | 1. 用 6 个 FP 查询搜索<br>2. score_threshold=0.60<br>3. 验证无假阳性通过 |
| 预期 | FP max score < 0.60，全部被过滤 |
| 指标 | FP max = 0.58 < 0.60，gap = 0.33 |

#### TC-F1-04: 阈值回归（快速检查）

| 字段 | 内容 |
|------|------|
| 目的 | 确保阈值调整不引入回归 |
| 前置 | — |
| 步骤 | 1. 运行基线 14 测试（含 score 阈值测试）<br>2. 验证 top-1 仍为 InfoManager |
| 预期 | 全部 PASS |
| 判定 | PASS = MAJOR 已通过阈值调整修复 |

**级别**: MAJOR
**发布门禁** (§10): ✅ 推荐 review + staging 回归（核心搜索路径）
**SLA** (§8.1): 响应 1 工作日 / 定位 2 工作日 / 版本窗口内（阈值参数调整 → 即时完成）

---

### TC-F2: 中文 embedding 噪声 → MAJOR

**发现**: bge-small-en-v1.5 对中文文本产生高 cos similarity 噪声向量，4/8 FP 匹配同一条中文记忆。

**判定路径**:
```
前置：非安全漏洞 → 正式判定
用户可感知 ✓（中文/跨语言用户搜索质量差）
体验严重退化 ✓（中文记忆成为"万能匹配"噪声源）
非功能阻断（单语场景不受影响）
→ MAJOR
```

**与 §5 分级示例对照**: #17 "列表页偶发白屏，刷新后恢复" (MAJOR)

#### TC-F2-01: 中文噪声量化

| 字段 | 内容 |
|------|------|
| 目的 | 量化中文记忆在英文查询中的噪声水平 |
| 前置 | collection 包含中英混合记忆（至少 1 条中文 + 7 条英文） |
| 步骤 | 1. 插入 1 条中文记忆（如"硅基流动是一个 API 代理服务"）<br>2. 用 8 个英文查询搜索<br>3. 统计中文记忆出现在 top-3 中的次数/位置 |
| 预期 | 中文记忆频繁出现在英文查询的 top results 中 |
| 指标 | 统计 FP count：旧数据 4/8 = 50% |

#### TC-F2-02: 纯英文场景回归（workaround 验证）

| 字段 | 内容 |
|------|------|
| 目的 | 确认纯英文 / 纯中文单语场景不受影响 |
| 前置 | collection 仅含英文记忆，查询为英文 |
| 步骤 | 1. 运行基线 14 测试（全英文数据） |
| 预期 | 全部 PASS |
| 判定 | PASS = 确认"单语场景不受影响" |

#### TC-F2-03: 多语言 embedder 对比（改进方向）

| 字段 | 内容 |
|------|------|
| 目的 | 如果用 paraphrase-multilingual 替换 bge-small-en，噪声是否消除 |
| 前置 | 切换到 multilingual embedder（如 paraphrase-multilingual-MiniLM-L6-v2） |
| 步骤 | 1. 重建 collection 用 multilingual embedder (384d)<br>2. 重复 TC-F2-01 的中英混合测试 |
| 预期 | 中文噪声显著降低（或中文/英文形成独立 cluster） |
| 判定 | 此测试验证 MAJOR 是否可通过换模型缓解 → 指导修复决策 |

**级别**: MAJOR
**发布门禁** (§10): ✅ 推荐 review + staging 回归（中英混合搜索路径）
**SLA** (§8.1): 响应 1 工作日 / 定位 2 工作日 / 版本窗口内
**注意**: 这是模型能力限制，非代码 bug。修复成本高（切换 embedder / 重训练），建议记录为 known issue 而非阻塞发布。

---

### TC-F3: FTS5 无 CJK 分词器 → MAJOR

**发现**: SQLite FTS5 默认 tokenizer 不支持 CJK 分词，中文关键词搜索 0% 召回。

**判定路径**:
```
前置：非安全漏洞 → 正式判定
用户可感知 ✓（中文关键词搜索完全无效）
功能阻断 ✓（关键词搜索路径对中文不可用）
有 workaround ✓（语义搜索对中文仍可用）
→ MAJOR
```

**与 §5 分级示例对照**: #2 "支付按钮无响应，但手动输入金额可绕过" (MAJOR)

#### TC-F3-01: 中文关键词 0% 召回验证

| 字段 | 内容 |
|------|------|
| 目的 | 确认中文关键词在 FTS5 下完全失效 |
| 前置 | FTS5 DB 含中英混合文本（如"信息管理器"、"深度学习"） |
| 步骤 | 1. 执行 `SELECT * FROM memories WHERE memories MATCH '信息管理'`<br>2. 执行 `SELECT * FROM memories WHERE memories MATCH '深度学习'` |
| 预期 | 返回 0 行（中文关键词无命中） |

#### TC-F3-02: 英文关键词正确（workaround 验证）

| 字段 | 内容 |
|------|------|
| 目的 | 确认英文关键词搜索正常（对比基准） |
| 前置 | 同上 FTS5 DB |
| 步骤 | 1. 运行基线 FTS5 测试（t2 测试套，3 个测试）<br>2. 验证英文关键词命中正确 |
| 预期 | 基线测试全部 PASS |
| 判定 | PASS = 确认"英文关键词正常" |

#### TC-F3-03: 语义搜索替代验证（workaround 确认）

| 字段 | 内容 |
|------|------|
| 目的 | 确认语义搜索可替代关键词搜索处理中文 |
| 前置 | Qdrant + bge-small-en collection |
| 步骤 | 1. 用中文查询做 semantic search<br>2. 验证返回合理结果（即使 embedder 非多语言） |
| 预期 | 返回结果（允许质量不如专用模型） |
| 判定 | 有返回结果 = workaround 存在（语义搜索可用） |

#### TC-F3-04: CJK tokenizer 方案评估

| 字段 | 内容 |
|------|------|
| 目的 | 评估是否可启用 FTS5 的 unicode61 tokenizer（含 tokenchars） |
| 前置 | — |
| 步骤 | 1. 尝试 `CREATE VIRTUAL TABLE ... USING fts5(..., tokenize='unicode61')`<br>2. 测试中文关键词搜索 |
| 预期 | unicode61 对 CJK 改善有限（仍按空格分词） |
| 判定 | 确认 SQLite FTS5 的固有局限 → 需要外部方案（Jieba 分词 + 自定义 tokenizer） |

**级别**: MAJOR
**发布门禁** (§10): ✅ 推荐 review + staging 回归（中文关键词搜索路径）
**SLA** (§8.1): 响应 1 工作日 / 定位 2 工作日 / 版本窗口内
**注意**: SQLite FTS5 固有限制。短期 workaround：语义搜索替代；长期方案：迁移到支持 CJK 的搜索引擎（MeiliSearch / PostgreSQL pg_bigm）。

---

### TC-F4: 完整 LLM pipeline 未测试 → SUGGESTION

**发现**: 仅测试了 Qdrant + FTS5 层（mem0 OSS core），未测试完整 LLM pipeline（记忆提取/分类）。

**判定路径**:
```
前置：非安全漏洞 → 正式判定
用户可感知 ✗（这是测试覆盖 gap，不影响用户可见行为）
数据完整性 ✗
系统健康度 ✗
→ SUGGESTION
```

**与 §5 分级示例对照**: #15 "变量命名 x 应改为 userCount" (SUGGESTION)

#### TC-F4-01: 测试覆盖 gap 确认

| 字段 | 内容 |
|------|------|
| 目的 | 文档化当前测试覆盖边界 |
| 前置 | 基线 14 测试全部 PASS |
| 步骤 | 1. 审查当前测试覆盖范围：Qdrant search + FTS5 检索<br>2. 确认未覆盖的组件：LLM memory extraction, memory update/consolidation, multi-user isolation |
| 预期 | 测试覆盖矩阵明确标记未覆盖区域 |
| 输出 | 测试覆盖矩阵 + 未覆盖风险清单 |

**级别**: SUGGESTION
**发布门禁** (§10): 不强制 review，常规 CI
**SLA** (§8.1): 响应 3 工作日（非强制）

---

## 5. 测试执行清单

### 5.1 基线回归测试（14 测试，全部应 PASS）

**来源**: `test_mem0.py` — 必须在每次变更后运行。

| # | 测试名 | 套件 | 关键断言 |
|---|--------|------|---------|
| 1 | Top result score > 0.5 | Score | hits[0].score > 0.5 |
| 2 | Threshold 0.6 filters correctly, top result is InfoManager | Score | top result = InfoManager |
| 3 | FTS5 keyword returns results | FTS5 | len(rows) > 0 |
| 4 | FTS5 top result is InfoManager or Obsidian | FTS5 | rank sort 正确 |
| 5 | FTS5 non-matching keyword returns empty | FTS5 | len(rows) == 0 |
| 6 | Semantic and FTS5 top results have overlap | Cross | len(overlap) >= 1 |
| 7 | Zero vector query returns ~0 scores | Edge | abs(score) < 0.01 |
| 8 | Relevant query scores higher than irrelevant (gap > 0.1) | Edge | gap > 0.1 |

### 5.2 大规模阈值验证（67 测试，基准数据）

| 指标 | 值 | 含义 |
|------|:---:|------|
| 记忆数 | 15 | 测试数据集规模 |
| 已知查询数 | 12 | 已知正确结果的查询 |
| FP 查询数 | 6 | 已知无关的查询 |
| top-1 范围 | [0.68, 0.91] | 相关查询的 cos similarity 分布 |
| FP max | 0.58 | 无关查询的最大 cos similarity |
| gap | 0.33 | 相关下限与无关上限的间距 |
| 推荐阈值 | ≥ 0.60 | 落于 gap 中间 |

### 5.3 新标准验证测试（新增）

| TC | 发现 | 类型 | 优先级 |
|----|------|------|:---:|
| TC-F5-01 | 默认配置复现 | 基线验证 | P0 |
| TC-F5-02 | 修复后回归 | 回归 | P0 |
| TC-F5-03 | 其他 embedder 兼容性 | 边界 | P2 |
| TC-F1-01 | 默认阈值 FP 验证 | 量化 | P0 |
| TC-F1-02 | 推荐阈值 TP 验证 | 验证 | P0 |
| TC-F1-03 | 阈值 FP 过滤 | 验证 | P0 |
| TC-F1-04 | 阈值回归 | 回归 | P1 |
| TC-F2-01 | 中文噪声量化 | 量化 | P1 |
| TC-F2-02 | 纯英文回归 | 回归 | P1 |
| TC-F2-03 | 多语言 embedder 对比 | 探索 | P2 |
| TC-F3-01 | 中文关键词 0% 召回 | 量化 | P1 |
| TC-F3-02 | 英文关键词正常 | 回归 | P1 |
| TC-F3-03 | 语义搜索替代 | workaround 验证 | P1 |
| TC-F3-04 | CJK tokenizer 评估 | 探索 | P2 |
| TC-F4-01 | 测试覆盖 gap 确认 | 文档化 | P2 |

**总计**: 基线 14 + 新增 15 = 29 测试用例

---

## 6. 发布门禁影响

### 6.1 门禁结论

基于已完成的 P0-09 重审分析（`docs/qa-reviews/P0-09-mem0-re-review.md`）：

| 门禁条件 | 当前状态 | 说明 |
|----------|:---:|------|
| BLOCKER = 0? | ❌ | F5 (Qdrant 维度不匹配) = BLOCKER |
| 安全漏洞 = 0? | ✅ | P0-09 不涉及安全 |
| 无未裁定申诉? | ✅ | 无申诉 |

**结论**：F5 必须在发版前修复。但 F5 在测试阶段已修复（显式设置 `embedding_model_dims=384`），实际不阻塞。

### 6.2 F5 发布策略（§10）

| 检查项 | 要求 | 当前状态 |
|--------|------|:---:|
| 代码审查 | ✅ 第二人 review | 待执行 |
| Staging smoke test | QA 执行 | TC-F5-02 复盖 |
| 灰度发布 | 灰度 30min 无明显退化后全量 | 推荐（非强制） |

### 6.3 MAJOR 发布策略

F1、F2、F3 均为 MAJOR，建议标准处理：

| 发现 | 修复策略 | 发布处理 |
|------|---------|---------|
| F1（默认阈值） | 阈值改为 0.60 → 即时修复 | 常规发布 |
| F2（中文噪声） | 切换 multilingual embedder（成本高） | 标注 known issue，下版本修 |
| F3（FTS5 CJK） | 短期：语义搜索代替；长期：搜索引擎迁移 | 标注 known issue，下版本修 |

---

## 7. SLA 对照

> 注意：旧报告发现的是测试环境配置问题/模型限制，非生产环境已部署 bug。以下分析基于"如果在生产环境发现"的前提。

| 发现 | 级别 | 响应 | 定位 | 方案 | 当前状态 |
|------|:---:|:---:|:---:|:---:|------|
| F5: 维度不匹配 | BLOCKER | 4h | 8h 初步判定+进度同步 | 24h 方案 | 已 fix（测试阶段修复 → SLA 不适用） |
| F1: 默认阈值 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 阈值 0.60 已识别，修复成本极低 |
| F2: 中文噪声 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 推荐升级 multilingual embedder（未执行） |
| F3: FTS5 CJK | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 短期用语义搜索代替 |

---

## 8. 申诉风险评估

| 发现 | 级别 | 驳回风险 | 分析 | 预准备证据 |
|------|:---:|:---:|------|------|
| F5 | BLOCKER | 低 | 技术事实明确：默认配置与 embedder 不兼容 | 异常日志 + 复现脚本 (TC-F5-01) |
| F1 | MAJOR | 低 | 数据清晰：0.25 vs 0.60 gap 0.33 | 大规模验证数据 (TC-F1-01/02/03) |
| F2 | MAJOR | 中 | 可能被驳回为 "by design — 英文模型不支持中文" | 噪声量化 (TC-F2-01) + 多语言对比 (TC-F2-03) |
| F3 | MAJOR | 低 | SQLite 已知限制，无可争议 | 0% 召回证据 (TC-F3-01) |
| F4 | SUGGESTION | N/A | 低于申诉门槛 | — |

**F2 申诉预案**：如研发驳回为 "by design"，QA 可引用 §1.3 "环境差异不降级" 原则——中文用户使用场景是 production 环境的一部分。加上 TC-F2-01 量化数据作为"新证据"。

---

## 9. 测试执行顺序（推荐）

```
Phase 1 — 基线验证（确保环境正常）
  ├── TC-F5-02: 修复后回归（确认 mem0 可用）
  ├── 基线 14 测试套件（全部必须 PASS）
  └── 大规模 67 测试（阈值数据基准）

Phase 2 — BLOCKER 验证
  ├── TC-F5-01: 默认配置复现（确认 BLOCKER 条件）
  └── TC-F5-03: 其他 embedder 兼容性

Phase 3 — MAJOR 量化 + Workaround 验证
  ├── TC-F1-01/02/03: 阈值量化
  ├── TC-F1-04: 阈值回归
  ├── TC-F2-01/02: 中文噪声 + 回归
  ├── TC-F3-01/02: FTS5 CJK 量化 + 回归
  └── TC-F3-03: 语义搜索替代

Phase 4 — 探索性（改进方向，非阻塞）
  ├── TC-F2-03: 多语言 embedder 对比
  ├── TC-F3-04: CJK tokenizer 评估
  └── TC-F4-01: 测试覆盖 gap 确认
```

---

## 10. 元数据

| 字段 | 值 |
|------|-----|
| 测试方案文件 | `docs/qa-reaudits/P0-09-test-plan.md` |
| 关联重审报告 | `docs/qa-reviews/P0-09-mem0-re-review.md` |
| 关联综合方案 | `docs/qa-reaudits/test-plan-p0-01-13.md` |
| 标准版本 | qa-finding-classification.md v1.0 |
| 旧报告 task | t_f6800f62 (infomanager board) |
| 旧报告测试文件 | `test_mem0.py` (268 行) |
| 编制人 | game-qa |
| 编制时间 | 2026-07-08 |

---

## 附录A：重审报告关键结论（引用自 re-review.md）

1. 旧报告发现基本有效，在新标准下得到更精确的分级。核心变更：F5 从未分级升级为 BLOCKER。
2. F5 是唯一 BLOCKER，但在测试阶段已修复，不影响生产。
3. F2/F3 是基础设施层面的 MAJOR，应在技术债务追踪中记录（§12.2 P1 #4），不阻塞当前版本。
4. 旧报告缺失正式分级框架——新标准 v1.0 提供了完整的判定公式。
5. 本次重审未发现安全漏洞，无需进入 OWASP Top 10 判定路径。
