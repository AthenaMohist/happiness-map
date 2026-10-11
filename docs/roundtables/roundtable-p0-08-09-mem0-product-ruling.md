# Roundtable 产品裁定：mem0 机制测试报告评审

> 角色：许清楚（产品负责人）
> 日期：2026-07-08
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 评审判定范围：P0-08 / P0-09

---

## 议程1：分级合理性审查

### P0-08（mem0 修通）

| 发现 | QA级别 | 产品裁定 | 理由 |
|------|:---:|:---:|------|
| P1: config.yaml api_key 死代码 | **MAJOR** | ✅ **维持** | §1.2 公式完全匹配：用户可感知（改 config.yaml api_key 无效果）+ 功能阻断（若只设 config.yaml 不设 .env，mem0 不工作）+ 有 workaround（手动设 .env 或 mem0.json）→ MAJOR |
| P2: is_available() SDK 预检缺失 | **MAJOR** | ✅ **维持** | §1.2 公式完全匹配。SDK 卸载但 api_key 仍设置时 is_available() 返回 True → agent 初始化 mem0 → from mem0 import MemoryClient 崩溃 |
| P3: lazy install 错误分化缺失 | **MAJOR** | ✅ **维持** | §1.2 公式完全匹配。5 种失败模式（网络不通、PEP 668、pip 不在 PATH、磁盘满、权限拒绝）全部被 except Exception: pass 吞噬，用户看到同一个 ModuleNotFoundError，无法自行诊断根因 |
| P4: 事实提取可观测性缺失 | **MINOR** | ✅ **维持** | §1.2 公式：间接可感知（用户可能发现记忆遗漏）+ 不阻断核心功能（记忆系统仍工作）→ MINOR。sync_turn() 丢弃 add() 返回值，agent 无法知道事实提取了什么 |
| P5: mem0.json 缺失无警告 | **MINOR** | ✅ **维持** | §1.2 公式：用户可感知（若用户期望通过 mem0.json 覆盖配置）+ 不阻断核心功能（通过 .env 可用）→ MINOR |

**P0-08 分级结论**：✅ 全部维持原判，3 MAJOR + 2 MINOR，无争议。

### P0-09（mem0 结果校验）

| 发现 | QA级别 | 产品裁定 | 理由 |
|------|:---:|:---:|------|
| **F5: Qdrant 维度不匹配** | BLOCKER→**SUGGESTION** | ✅ **同意降级** | 卡面标注：测试方法问题，非真实缺陷。默认 1536d 配置与 bge-small-en 384d 不兼容的"崩溃"仅在错误配置的测试环境中出现，生产环境通过显式设置 embedding_model_dims=384 不存在此问题。降为 SUGGESTION 合理 |
| F1: 默认阈值 0.25→100% FP | **MAJOR** | ✅ **维持** | §1.2 公式完全匹配：用户可感知（搜索返回 100% 不相关结果）+ 体验严重退化（搜索质量=随机）+ 有 workaround（阈值改为 0.60 完美分离，0% FP）→ MAJOR。数据量化充分 |
| F2: bge-small-en 中文噪声 | **MAJOR** | ✅ **维持** | §1.2 公式：用户可感知（中文/跨语言用户搜索质量差）+ 体验严重退化（38% 英文查询被中文噪声污染）+ 非功能阻断（纯英文场景正常）→ MAJOR。bge-small-en 模型固有限制，非代码缺陷 |
| F3: FTS5 无 CJK 分词器 | **MAJOR** | ✅ **维持** | §1.2 公式完全匹配：用户可感知（中文关键词 FTS5 搜索 0% 召回）+ 功能阻断（FTS5 关键词路径对中文不可用）+ 有 workaround（语义搜索对中文可用）→ MAJOR。SQLite 已知限制 |
| F4: 完整 LLM pipeline 未测试 | **SUGGESTION** | ✅ **维持** | §1.3：用户不可感知（测试覆盖 gap，不影响用户可见行为）→ SUGGESTION |

**P0-09 分级结论**：✅ 同意 F5 降级为 SUGGESTION，其余全部维持原判。最终分布：3 MAJOR + 2 SUGGESTION。

---

## 议程1总结：分级裁定

| 报告 | 总发现 | 产品调整 | 最终分布 |
|------|:---:|:---:|------|
| P0-08 | 3 MAJOR + 2 MINOR | 无调整 | 维持原判 |
| P0-09 | 原 1 BLOCKER + 3 MAJOR + 1 SUGGESTION | F5 降为 SUGGESTION（已执行） | 3 MAJOR + 2 SUGGESTION |

**无 BLOCKER，无安全漏洞，无分级争议需要升级到申诉流程。** ✅

---

## 议程2：处置决策

### 按级别分派

| 级别 | 发现 | 处置 | 目标 |
|------|------|------|------|
| **MAJOR** | P0-08 P1 (config 死代码) | 🔧 当前窗口修复 | `_load_config()` 增加 config.yaml fallback 路径。修复成本低（1-2 个函数修改），SLA: 响应 1 工作日、定位 2 工作日（QA 已完成代码定位）、方案窗口内 |
| **MAJOR** | P0-08 P2 (is_available 盲检) | 🔧 当前窗口修复 | `is_available()` 增加 `import mem0` 预检。修复成本低（3-5 行 try/except） |
| **MAJOR** | P0-08 P3 (lazy install 静默) | 🔧 当前窗口修复 | lazy install 捕获并分类 5 种失败模式。修复成本中等（需设计错误分类逻辑） |
| **MAJOR** | P0-09 F1 (默认阈值) | ✅ **已修复** | 阈值改为 0.60，参数调整即时生效。TC-F1-01/02/03 全确认。**CLOSED** |
| **MAJOR** | P0-09 F2 (中文噪声) | 📋 标注 known issue | bge-small-en 模型固有限制。解决方案：切换 multilingual embedder（成本高，需模型选型+迁移测试）。下版本修复 |
| **MAJOR** | P0-09 F3 (FTS5 CJK) | 📋 标注 known issue | SQLite 已知限制。短期 workaround：语义搜索替代；长期方案：搜索引擎迁移（MeiliSearch/PostgreSQL pg_bigm）。下版本修复 |
| **MINOR** | P0-08 P4 (事实提取不透明) | 📋 待办 P1 | `sync_turn()` 后回调事实提取结果摘要。修复后 agent 可感知本轮提取了哪些事实 |
| **MINOR** | P0-08 P5 (mem0.json 静默) | 📋 待办 P2 | mem0.json 缺失时记录 debug 日志。低优先级，修复成本极低 |
| **SUGGESTION** | P0-09 F4 (LLM pipeline 未测试) | 📝 记录在案 | LLM API 可用时补充端到端测试 |
| **SUGGESTION** | P0-09 F5 (维度不匹配) | ✅ **已关闭** | 测试方法问题 + 已修复（显式设置 embedding_model_dims=384）。**CLOSED** |

### 处置优先级说明

P0-08 三个 MAJOR 修复成本均为低到中等：
- P1（config fallback）：增加 config.yaml 读取路径，约 0.5h
- P2（SDK 预检）：增加 try/except ImportError，约 0.3h
- P3（错误分化）：分类 5 种失败模式，约 1h

**三个 MAJOR 合计约 2h，强烈建议当前版本窗口内全部修复。**

P0-09 F2/F3 为基础设施层限制（模型选型 + 搜索引擎迁移），不适合 rush fix。建议：
- 记录 MAJOR known issue 后正常发版
- 纳入 §12.2 P1 #4 技术债务追踪

### 暂缓与签批

- 无 BLOCKER → 无需 Frank 签批（§11 红线 1）
- 无申诉 → 无申诉率影响
- 无安全漏洞 → 发布门禁无安全阻塞

---

## 发布门禁检查（§10）

```
BLOCKER=0 AND MAJOR≤N AND 安全漏洞=0 AND 无未裁定的申诉
```

| 检查项 | 状态 |
|--------|:---:|
| BLOCKER=0？ | ✅（F5 已降级为 SUGGESTION） |
| 安全漏洞=0？ | ✅（全部发现不涉及 OWASP Top 10） |
| 无未裁定申诉？ | ✅ |
| MAJOR 统计 | **6 个**（P0-08 P1/P2/P3 + P0-09 F1/F2/F3）。其中 F1 已修复(CLOSED)，F2/F3 为 known issue，P1/P2/P3 建议窗口内修复 |

**结论**：✅ 满足发布门禁条件。建议在当前窗口内修复 P1/P2/P3 后发版。F2/F3 标注 known issue 可正常发版。

---

## 处置决策清单（供架构/研发/QA后续执行）

| # | 发现 | 级别 | 处置 | 负责人 | 备注 |
|---|------|:---:|------|--------|------|
| 1 | P0-08 P1 config 死代码 | MAJOR | 🔧 修复 | 研发（寇豆码） | `_load_config()` 增加 config.yaml fallback，约 0.5h |
| 2 | P0-08 P2 is_available 盲检 | MAJOR | 🔧 修复 | 研发 | `is_available()` 增加 SDK import 预检，约 0.3h |
| 3 | P0-08 P3 lazy install 静默 | MAJOR | 🔧 修复 | 研发 | 分类 5 种失败模式并给出不同错误信息，约 1h |
| 4 | P0-09 F1 默认阈值 | MAJOR | ✅ 已修复 | — | 阈值→0.60，CLOSED |
| 5 | P0-09 F2 中文噪声 | MAJOR | 📋 known issue | 架构+研发 | 切换 multilingual embedder，下版本修复 |
| 6 | P0-09 F3 FTS5 CJK | MAJOR | 📋 known issue | 架构+研发 | 搜索引擎迁移，下版本修复 |
| 7 | P0-08 P4 事实提取不透明 | MINOR | 📋 P1 | 研发 | sync_turn() 回调结果摘要 |
| 8 | P0-08 P5 mem0.json 静默 | MINOR | 📋 P2 | 研发 | 缺失时记录 debug 日志 |
| 9 | P0-09 F4 LLM pipeline 未测试 | SUGGESTION | 📝 记录 | QA | LLM API 可用时补充 |
| 10 | P0-09 F5 维度不匹配 | SUGGESTION | ✅ 已关闭 | — | 测试方法问题，CLOSED |

---

> **产品端裁定完成。移交架构师（高见远）进行技术可行性评估，研发（寇豆码）确认修复方案，QA 做最终回应。**
