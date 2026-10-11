# Memory Middleware（记忆中间层）— QA 测试方案 v3（V2 命令验收）

> 版本：v3.0 | 日期：2026-08-11 | 作者：game-qa（Frank 游戏开发团队 QA）
>
> 被测范围：`/workspace/mem-core`（独立 git repo，HEAD 7e206bf）— V2 四命令 CLI 接线 + 引擎层 blast.py / drift.py / sources/gai.py / demote（待实现）
>
> 本方案聚焦 V2 命令验收（PRD §5.2 B1-B5 + demote）。MVP 验收（A1-A9）已由 v2 方案覆盖并 PASS（VA 9/9 全绿）；V2 引擎函数已实现可先行测试，等 CLI 接线后补 CLI 层断言。
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0（§1.2 判定公式 / §5 示例 / §8 SLA / §9 QA SLA / §10 发布门禁 / §11 产品红线）

---

## 0. v2 → v3 差异说明（为什么出 v3）

v2 方案（`docs/qa/memory-middleware-test-plan-v2.md`，56 用例）已覆盖 MVP 全量 + V2 引擎层先行验证的 10 例（TC-22~26 / BC-05 / BE-07~08 / TS-04/07）。v2 方案的 V2 部分是**引擎函数级先行**，CLI 层断言标 `[V2-pending]`。

v3 方案在 v2 基础上**深化为 V2 命令的完整验收测试方案**：

1. 编号体系从 v2 的 TC/BE/TS 体系切换到任务卡要求的 **V2-CMD-NN** 格式（V2-UPD-NN / V2-DRF-NN / V2-GAI-NN / V2-DEM-NN / V2-REG-NN / V2-IDM-NN / V2-NEG-NN）
2. 新增幂等性专项测试（V2-IDM 组）— update 多次跑一致
3. 新增负面注入测试（V2-NEG 组）— 注入断链/差异/冲突 → V2 命令检出
4. 新增回归保护测试（V2-REG 组）— V2 命令不影响 MVP 7 命令行为
5. 覆盖 B1-B5 全量门禁 + demote 补充 + 边界 + 异常

### 0.1 契约差异标记（D2-F1~F3，待研发对齐）

> 以下为编写方案时发现的**任务卡命令面 vs 架构 §4.4 定稿面**的差异。按标准 §6 论证流程提交：发现 → 研发评估 → 通过/驳回/暂缓。本方案**以架构 §4.4 为权威契约**（架构是接口权威），任务卡标记记为差异（D2 系列），不改变测试断言。

| # | 差异项 | 任务卡标记 | 架构 §4.4 定稿 | 本方案采用 | 理由 |
|---|--------|-----------|---------------|-----------|------|
| **D2-F1** | `update` 子命令名 | `update [--dry-run]` | `update <source> --plan` / `--apply <pages…>` | **架构面**（`--plan` / `--apply`） | 架构 §4.4 定稿是接口权威；`--dry-run` 约等于 `--plan`（只列不动手），但参数签名不同（plan 需要 source 参数） |
| **D2-F2** | `gai-links` 子命令选项 | `gai-links [--fix]` | `gai-links`（无 `--fix` 选项） | **架构面**（无 `--fix`，缺页只报告） | 架构 §4.4 明确「缺页 → 报告（不自动建页，交 update --plan 流程）」；`--fix` 若存在需研发额外定义行为 |
| **D2-F3** | `demote` 子命令选项 | `demote <ID> --status blocked\|archived` | `demote <ID> --reason "…"` | **架构面**（`--reason`，status 由 reason 推断或内置映射） | 架构 §4.4 定义 demote 写 wiki status 变更 + 变更说明节；`--status` 直接指定 vs `--reason` 推断是语义差异，需研发确认 |

**处置建议**：研发实现 V2 CLI 时以架构 §4.4 为准；若任务卡标记为最新意图，则需 PRD/arch 修订后重跑用例。本方案全部用例引用架构 §4.4 定稿面。

### 0.2 引擎层先行就绪性（2026-08-11 smoke 实测）

| 引擎 | 模块 | 函数 | smoke 实测 | CLI 接线状态 |
|------|------|------|-----------|:---:|
| blast | `memcore/blast.py` | `compute_candidates(db, source)` `extract_source_terms(text)` | ✅ 真实 db 6 候选页，terms 正确提取 | ❌ stub exit 2 |
| drift | `memcore/drift.py` | `three_way_check(wiki, db, gai_file, kanban_db)` | ✅ 真实 wiki 114 diffs（kanban 活跃任务大量缺页）；一致状态返回 [] | ❌ stub exit 2 |
| gai-adapter | `memcore/sources/gai.py` | `GaiAdapter.fetch_events()` `.map_id()` `.mirror_status()` | ✅ golden 4 events 正确解析，map_id 大小写无关 | ❌ stub exit 2 |
| **demote** | **无独立引擎模块** | cli.py `cmd_demote` = stub | ❌ **无引擎实现，仅 CLI stub** | ❌ stub exit 2 |

> ⚠️ **demote 是 V2 四命令中唯一没有引擎实现的命令**。blast/drift/gai 已有引擎函数 + pytest 覆盖（test_drift.py 9 例 / test_gai.py 13 例），demote 需要研发从零实现引擎 + CLI。测试方案对 demote 组标注 `[DEV-DEPENDENT]`：引擎/CLI 未交付前无法执行引擎层断言，仅保留接口契约用例骨架。

---

## 1. 真实接口基线（V2 引擎实测，方案断言以此为准）

### 1.1 V2 命令面（架构 §4.4 定稿 + cli.py 现状）

| 命令 | 架构契约 | cli.py 当前实现 | 实测退出码 | 引擎就绪 |
|------|---------|----------------|:---:|:---:|
| `memctl update <source> --plan` | 读 source → extract_terms → 查 term_pages → 候选清单 + 命中理由 + 新增页建议；不读全 wiki（<20 文件）；--json 供 OC 裁定 | `cmd_update` = `_stub_v2("update")` | 2（占位） | ✅ blast.py |
| `memctl update <source> --apply <pages…>` | LLM 只在候选集内读页改写 + bump updated + 矛盾检测 + 机械维护 + 原子提交 | 同上 | 2 | ⚠️ 需 LLM |
| `memctl drift [--json]` | 只读三方对账：kanban 活跃 vs wiki actions / GAI 行 vs wiki actions / index vs 文件；空=无漂移 exit 0；有差异 exit 3 | `cmd_drift` = `_stub_v2("drift")` | 2（占位） | ✅ drift.py |
| `memctl gai-links` | GAI 待办行 [[ID]] 双链补/校验；缺页报告不自动建页 | `cmd_gai_links` = `_stub_v2("gai-links")` | 2（占位） | ✅ sources/gai.py |
| `memctl demote <ID> --reason "…"` | 写 wiki：status 变更 + 变更说明节 + bump updated + log + 镜像 L0 状态列 | `cmd_demote` = `_stub_v2("demote")` | 2（占位） | ❌ 无引擎 |

### 1.2 引擎函数签名（实测）

```
blast.py:
  extract_source_terms(text: str) -> list[str]
    # 确定性：标题词(CJK 2-4 + ASCII 2+) / ID 模式 / t_ ID / 全文 3-gram
    # 实测：source 含「记忆中间层架构决策」→ ['architecture','decision','memory','middleware']

  compute_candidates(db_path, source_text, *, top_n=10) -> list[dict]
    # 只读 db（term_pages 表），不读 wiki 文件
    # 返回 [{page_id, file_path, type, title, hit_count, terms[:8]}]
    # 实测：真实 db + 中间层 source → 6 候选页（SCHEMA hit=4 居首）

drift.py:
  three_way_check(wiki_root, db_path, *, gai_file=None, kanban_db=None) -> list[str]
    # 只读：kanban 活跃任务缺页 / GAI 缺页 / index vs 文件
    # 返回差异描述列表（空=无漂移）
    # 实测：真实 wiki → 114 diffs（kanban 活跃任务大量缺 wiki 页）

sources/gai.py:
  GaiAdapter(gai_file) / GaiAdapter()
    fetch_events(since=None) -> list[Event]
      # 表头驱动列位感知（MEM-QA-02 修复后）
      # 实测：golden gai-dirty.md → 4 events (DPL-009/010, INF-011/012)
    map_id(external_id) -> str | None
      # 实测：'DPL-009' → 'DPL-009'；'BOGUS' → None
    mirror_status(wiki_id, external_id) -> dict
      # 实测：{'status': 'active', 'detail': 'Webhook 替代 cron 轮询'}
```

### 1.3 已有 pytest 覆盖（V2 引擎层先行）

| 文件 | 用例数 | 覆盖范围 | 状态 |
|------|:---:|---------|:---:|
| test_drift.py | 9 | 一致空 / 缺页检出 / 只读 / done 排除 / index 不一致 / kanban 缺失静默 / kanban 损坏静默 / GAI 缺页 / index 未收录 | ✅ |
| test_gai.py | 13 | 4 表头变体 / 无表头 / 缺文件 / 旧格式 / 表头词误判回归 / done 状态 / map_id / drift 消费侧回归 / 真实优先级列 | ✅ |
| test_cli.py V2 stub | 1 | 4 命令 stub exit 2 + "V2 未实现" 提示 | ✅（stub 阶段） |

> **引擎层先行已验证的核心断言**：drift 只读不修复、drift 静默降级、gai-adapter 列位感知、blast 候选集正确。v3 方案的引擎层用例与已有 pytest 不重复，聚焦**引擎函数 → CLI 接线后的端到端断言** + **幂等/负面/回归**专项。

---

## 2. 测试环境

继承 v2 方案 §2 环境（mem-core 7e206bf / pytest 89 全绿 / sqlite 3.45.1 trigram / devPPL 集成）。V2 额外依赖：

| 维度 | 状态 | V2 特殊要求 |
|------|------|------------|
| V2 CLI 接线 | ❌ 4 命令 stub exit 2 | 研发实现 CLI 接线后执行 CLI 层断言；引擎层先行 |
| LLM 策展（update --apply） | ⚠️ 需 LLM agent | `--apply` 涉及 LLM 读候选页改写，测试需 mock LLM 或手动验证；幂等性可确定性验证（候选集一致） |
| kanban.db 夹具 | ✅ test_drift.py 已有 `_mock_kanban` | V2 用例复用 mock kanban 夹具 |
| GAI 夹具 | ✅ golden/gai-dirty.md + 真实 GAI | V2 用例双路径：golden 夹具 + 真实 GAI（MEM_GAI_FILE 注入） |
| 临时 wiki | ✅ conftest.py wiki_root fixture | 全部 V2 写入测试用临时 wiki，**不污染真实 repo** |
| 环境变量隔离 | ✅ v2 §2 OBS-03 | `MEM_WIKI_PATH / MEM_DB_PATH / MEM_GAI_FILE / MEM_KANBAN_DB` 每用例显式注入 |

### 2.1 测试执行状态分级

| 标签 | 含义 | 执行时机 |
|------|------|---------|
| `[ENGINE-READY]` | 引擎函数已实现，可立即执行引擎层断言 | 现在 |
| `[CLI-PENDING]` | 等 CLI 接线后补 CLI 层断言 | dev 交付 V2 CLI 后 |
| `[DEV-DEPENDENT]` | 等引擎/CLI 实现后才能执行 | demote 组（无引擎） |
| `[LLM-REQUIRED]` | 涉及 LLM 改写，需 mock 或手动验证 | update --apply |

---

## 3. update 命令测试组（V2-UPD-01 ~ V2-UPD-08）

> 被测命令：`memctl update <source> --plan` / `--apply <pages…>`
> 验收门禁：B1（update 后 index 与 rebuild 一致）+ B4（矛盾检测 contradictions 标记）
> 引擎：`blast.py` compute_candidates / extract_source_terms

### V2-UPD-01：update --plan 候选页清单（正常路径）`[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-01 |
| **PRD 断言** | B1（§5.2）；架构 §6.1/6.2 |
| **路径** | 路径 A（30+ 页 wiki + term_pages db） |
| **前置条件** | 临时 wiki 构建 6+ 页（含 r3-architect/SCHEMA 等），index --rebuild 生成 term_pages |
| **步骤** | 1. 构建临时 wiki（≥6 页，覆盖 concepts/actions/SCHEMA）<br>2. `memctl index --rebuild`<br>3. 准备 source 文本（含已存在主题词如「记忆中间层架构决策」+ 新主题如「未来扩展」）<br>4. 引擎层：`blast.compute_candidates(db, source)`<br>5. CLI 层（CLI 接线后）：`memctl update <source-file> --plan` |
| **预期结果** | 1. 候选页清单含命中理由（term→pages），按 hit_count 降序<br>2. 新增页建议出现（source 中未命中现有页的主题如「未来扩展」）<br>3. 全程零 LLM（确定性）<br>4. 引擎实测：source 含 4 terms → 6 候选页，SCHEMA hit=4 居首 |
| **风险等级** | **MAJOR**（blast radius 是 200 文件墙对策；候选集错位可人工裁定） |
| **分级依据** | 标准 §1.2：--plan 候选错位有 workaround（人工查 wiki）→ MAJOR |
| **环境依赖** | 路径 A + blast 引擎 |

### V2-UPD-02：update --plan 不读全 wiki（B1 硬约束 <20 文件）`[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-02 |
| **PRD 断言** | B1（§5.2 核心硬约束）；架构 §6.1 |
| **路径** | 路径 A（30+ 页 wiki + 文件读取计数器） |
| **前置条件** | 临时 wiki 30+ 页 |
| **步骤** | 1. 构建 30+ 页临时 wiki + index<br>2. 注入文件读取计数器（monkey-patch `open()` 或 strace）<br>3. `compute_candidates(db, source)` 或 `memctl update --plan`<br>4. 统计 wiki 文件读取次数 |
| **预期结果** | 1. 候选页清单正确<br>2. **wiki 文件读取数 = 0**（只查 db，不读 wiki 文件；compute_candidates 实现确认只 SELECT term_pages + pages 表）<br>3. 读取的 SQLite 查询 <20 条 |
| **风险等级** | **MAJOR**（B1 硬约束；范围失控有 workaround） |
| **分级依据** | 标准 §1.2：全 wiki 读取有 workaround（手动限定范围）→ MAJOR |
| **环境依赖** | 路径 A + 文件读取计数器 |

### V2-UPD-03：update --plan 空候选（source 无命中词）`[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-03 |
| **PRD 断言** | B1（边界）；架构 §6.2 |
| **路径** | 路径 A |
| **前置条件** | 临时 wiki + db 已建 |
| **步骤** | 1. source 文本 = 完全不相关内容（如「量子物理超导体」）<br>2. `compute_candidates(db, source)` |
| **预期结果** | 1. 候选页清单为空（0 命中）<br>2. 新增页建议 = 全部 source terms（均未命中现有页）<br>3. 不崩溃、不报错 |
| **风险等级** | **MINOR**（边界容错） |
| **分级依据** | 标准 §1.2：空候选不阻断功能（可手动查 wiki）→ MINOR |
| **环境依赖** | 路径 A |

### V2-UPD-04：update --plan 无 db（降级容错）`[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-04 |
| **PRD 断言** | B1（异常路径）；架构 §6.2 |
| **路径** | 路径 A |
| **步骤** | 1. db_path 指向不存在文件<br>2. `compute_candidates("/nonexistent.db", source)` |
| **预期结果** | 1. 返回空候选列表（`db_path.exists()` 检查后 return []）<br>2. 不抛异常、不崩溃 |
| **风险等级** | **MAJOR**（无 db 崩溃 = 诊断无从下手） |
| **分级依据** | 标准 §1.2：崩溃无 workaround（无诊断）；空返回有 workaround（先 index）→ MAJOR |
| **环境依赖** | 路径 A |

### V2-UPD-05：update --apply 候选页改写 + bump updated `[CLI-PENDING]` `[LLM-REQUIRED]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-05 |
| **PRD 断言** | B1（apply 阶段）；架构 §6.2 |
| **路径** | 路径 A + mock LLM |
| **前置条件** | V2 CLI 接线 + update --apply 实现 |
| **步骤** | 1. `memctl update <source> --plan` → 获取候选页清单<br>2. 人工/mock 裁定接受全部候选<br>3. `memctl update <source> --apply <pages...>`<br>4. 检查候选页 git diff + updated 时间戳 bump<br>5. `memctl lint` |
| **预期结果** | 1. 只改候选页（git diff 只含候选集）<br>2. updated 时间戳 bump<br>3. lint 0（四不变式全过）<br>4. log.md 追加事件<br>5. 非候选页无变化 |
| **风险等级** | **MAJOR**（apply 范围失控可 git 回滚） |
| **分级依据** | 标准 §1.2：范围失控有 workaround（git 回滚）→ MAJOR |
| **环境依赖** | V2 CLI + mock LLM |

### V2-UPD-06：update --apply 矛盾检测（contradictions 标记 + review 队列）`[CLI-PENDING]` `[LLM-REQUIRED]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-06 |
| **PRD 断言** | B4（§5.2）；架构 §6.3 |
| **路径** | 路径 A（golden/conflict-a.md + conflict-b.md） |
| **前置条件** | V2 CLI + 矛盾检测实现 |
| **步骤** | 1. 注入 conflict-a.md（主张 trigram 足够）<br>2. source 含冲突主张（向量检索更好）→ `update --plan`<br>3. `update --apply` → LLM 发现冲突<br>4. 检查 contradiction 标记 |
| **预期结果** | 1. 冲突页打 `contradictions: [对方页]` 标记<br>2. 双版本并存（不覆盖）<br>3. `memctl drift` 输出带 contradictions 的页清单（review 队列）<br>4. 后续 lint 不因标记断链 |
| **风险等级** | **MAJOR**（矛盾检测缺失有 workaround：人工 review） |
| **分级依据** | 标准 §1.2：漏标可人工发现 → MAJOR |
| **环境依赖** | V2 CLI + conflict 夹具 |

### V2-UPD-07：update --plan --json 输出（OC 消费契约）`[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-07 |
| **PRD 断言** | B1（--json 供 OC 裁定）；架构 §6.2 |
| **路径** | 路径 A |
| **前置条件** | V2 CLI 接线 |
| **步骤** | 1. `memctl update <source> --plan --json`<br>2. 解析 JSON 输出 |
| **预期结果** | 1. 输出合法 JSON（`json.loads()` 不抛异常）<br>2. 含字段：candidates [{page_id, hit_count, terms}], new_page_suggestions []<br>3. 可被 OC 脚本消费（确定性结构） |
| **风险等级** | **MAJOR**（JSON 结构错位 = OC 消费断裂） |
| **分级依据** | 标准 §1.2：JSON 格式异常有 workaround（人工解析）→ MAJOR |
| **环境依赖** | V2 CLI |

### V2-UPD-08：update 无 source 参数（用法错误 exit 2）`[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-UPD-08 |
| **PRD 断言** | 架构 §4.2 退出码 |
| **路径** | 路径 A |
| **步骤** | 1. `memctl update`（无 source + 无 --plan/--apply）<br>2. `memctl update --plan`（无 source） |
| **预期结果** | 1. exit 2（用法错误）<br>2. stderr 有明确错误提示 |
| **风险等级** | **MINOR**（用法错误提示） |
| **分级依据** | 标准 §1.2：用法错误有 workaround（看 --help）→ MINOR |
| **环境依赖** | V2 CLI |

---

## 4. drift 命令测试组（V2-DRF-01 ~ V2-DRF-08）

> 被测命令：`memctl drift [--json]`
> 验收门禁：B2（drift 检出人工注入的三方差异）+ B5（干净状态下 drift 报告为空）
> 引擎：`drift.py` three_way_check（已有 9 例 pytest）

### V2-DRF-01：drift 干净状态为空（B5）`[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-01 |
| **PRD 断言** | B5（§5.2 核心）；架构 §4.4 drift |
| **路径** | 路径 A（一致状态夹具） |
| **前置条件** | 临时 wiki + mock kanban（活跃任务 ⊆ wiki actions）+ mock GAI（ID ⊆ actions）+ index 与文件一致 |
| **步骤** | 1. 构造一致状态（已有 test_drift.py `test_drift_consistent_empty` 复用）<br>2. 引擎层：`three_way_check(wiki, db, gai_file, kanban_db)`<br>3. CLI 层：`memctl drift` |
| **预期结果** | 1. 引擎返回空列表 []（无漂移）<br>2. CLI exit 0（无漂移），输出为空或 "无漂移" |
| **风险等级** | **MAJOR**（B5 门禁；兜底层失效有 workaround 人工对账） |
| **分级依据** | 标准 §1.2：drift 假报空（漏报漂移）可人工对账 → MAJOR |
| **环境依赖** | 路径 A + drift 引擎（已有 pytest 覆盖） |

### V2-DRF-02：drift kanban 活跃任务缺页检出 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-02 |
| **PRD 断言** | B2（间接）；架构 §4.4 drift |
| **路径** | 路径 A |
| **步骤** | 1. mock kanban 含活跃任务 t_10000001<br>2. wiki 无 t_10000001 页<br>3. `three_way_check(wiki, db, gai_file, kanban_db)` |
| **预期结果** | 1. 输出含 `"kanban 活跃任务缺 wiki 页: t_10000001"`<br>2. CLI exit 3（有差异）<br>3. 全程只读（wiki 文件不变） |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-DRF-01 |
| **环境依赖** | 路径 A（已有 test_drift_missing_page_detected_and_healed 覆盖） |

### V2-DRF-03：drift GAI 缺页检出 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-03 |
| **PRD 断言** | B2；架构 §4.4 drift |
| **路径** | 路径 A |
| **步骤** | 1. mock GAI 含 DPL-101/DPL-102<br>2. wiki 无对应页<br>3. `three_way_check(...)` |
| **预期结果** | 1. 输出含 `"GAI 待办缺 wiki 页: DPL-101"` 和 `"DPL-102"`<br>2. 优先级列值（如 P1-01）**不**产生假断链（MEM-QA-02 回归）<br>3. CLI exit 3 |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-DRF-01 |
| **环境依赖** | 路径 A（已有 test_drift_gai_missing_page_detected 覆盖） |

### V2-DRF-04：drift index 与文件不一致检出 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-04 |
| **PRD 断言** | B5；架构 §4.4 drift |
| **路径** | 路径 A |
| **步骤** | 1. index.md 列出不存在的文件（幽灵页）<br>2. `three_way_check(...)` |
| **预期结果** | 1. 输出含 `"index.md 幽灵页: ..."`<br>2. CLI exit 3 |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-DRF-01 |
| **环境依赖** | 路径 A（已有 test_drift_index_inconsistency_detected 覆盖） |

### V2-DRF-05：drift 只读不修复（铁律 2）`[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-05 |
| **PRD 断言** | B5（全程只读）；架构铁律 2；PRD §7.1 |
| **路径** | 路径 A |
| **步骤** | 1. 制造漂移（删 wiki 页）<br>2. `three_way_check(...)`<br>3. 检查 wiki 文件是否被重建 |
| **预期结果** | 1. drift 检出缺页<br>2. **缺页文件不被自动重建**（只读）<br>3. 全程零写入 |
| **风险等级** | **BLOCKER**（铁律 2 违反 = 状态回写环破坏，无 workaround） |
| **分级依据** | 标准 §1.2：drift 自动修复 = 违反「状态不回写环」铁律（数据完整性）→ BLOCKER |
| **环境依赖** | 路径 A（已有 test_drift_readonly_no_autofix 覆盖） |

### V2-DRF-06：drift kanban.db 缺失/损坏静默降级 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-06 |
| **PRD 断言** | B5（容错）；架构 §4.4 drift + C9 降级优先 |
| **路径** | 路径 A |
| **步骤** | 1. kanban_db 指向不存在文件 → `three_way_check(...)`<br>2. kanban_db 指向损坏文件（非 SQLite）→ `three_way_check(...)` |
| **预期结果** | 1. 缺失：返回 [] 或仅含其他维度差异，不抛异常<br>2. 损坏：sqlite3.Error 静默降级，返回 []<br>3. CLI exit 0 或 3（视其他维度），不崩溃 |
| **风险等级** | **MAJOR**（kanban 缺失崩溃 = 周 cron 挂死） |
| **分级依据** | 标准 §1.2：崩溃无诊断 → MAJOR；静默降级有 workaround → MAJOR |
| **环境依赖** | 路径 A（已有 test_drift_missing_kanban_db_silent + test_drift_corrupt_kanban_db_silent 覆盖） |

### V2-DRF-07：drift 忽略 done/closed/cancelled 任务 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-07 |
| **PRD 断言** | B5（MEM-QA-03 回归）；架构 §4.4 drift |
| **路径** | 路径 A |
| **步骤** | 1. mock kanban 含 done 状态任务 + wiki 页 status=active<br>2. `three_way_check(...)` |
| **预期结果** | 1. drift **不报**状态漂移（status 镜像由 lint I3 负责非 drift）<br>2. done/closed/cancelled 任务不进 `_kanban_active` 过滤 |
| **风险等级** | **MAJOR**（误报状态漂移 = 噪声淹没真漂移） |
| **分级依据** | 标准 §1.2：误报有 workaround（人工过滤）→ MAJOR |
| **环境依赖** | 路径 A（已有 test_drift_ignores_done_closed_cancelled 覆盖） |

### V2-DRF-08：drift --json 输出 `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DRF-08 |
| **PRD 断言** | 架构 §4.4 drift（--json）；架构 §4.2 退出码 |
| **路径** | 路径 A |
| **步骤** | 1. 制造漂移状态<br>2. `memctl drift --json` |
| **预期结果** | 1. 输出合法 JSON（`json.loads()` 成功）<br>2. 含 diffs 数组<br>3. exit 3（有差异）；干净状态 exit 0 + 空 diffs |
| **风险等级** | **MAJOR**（JSON 消费契约） |
| **分级依据** | 标准 §1.2：JSON 格式错位有 workaround → MAJOR |
| **环境依赖** | V2 CLI |

---

## 5. gai-links 命令测试组（V2-GAI-01 ~ V2-GAI-06）

> 被测命令：`memctl gai-links`
> 验收门禁：B2（gai-links 能检出缺失双链）
> 引擎：`sources/gai.py` GaiAdapter（已有 13 例 pytest）
> 注意：架构 §4.4 定义 gai-links 为「双链补/校验，缺页报告不自动建页」；任务卡标记 `--fix`（D2-F2 差异），本方案以架构为准（无 --fix）

### V2-GAI-01：gai-links 零断链（已回填待办）`[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-GAI-01 |
| **PRD 断言** | B2（§5.2）；架构 §4.4 gai-links |
| **路径** | 路径 A（GAI 夹具含 5 项已回填 ID + 对应 actions/ 页） |
| **步骤** | 1. 构造 GAI 夹具（含 5 项已回填待办 ID）+ 对应 actions/ 页<br>2. 引擎层：`GaiAdapter.fetch_events()` 获取 GAI ID 集<br>3. 校验每个 ID 有对应 wiki 页 |
| **预期结果** | 1. 输出为空（零断链）<br>2. 缺页仅报告不自动建页（交 update --plan） |
| **风险等级** | **MAJOR**（B2 门禁） |
| **分级依据** | 标准 §1.2：双链断可人工补链 → MAJOR |
| **环境依赖** | 路径 A + GaiAdapter |

### V2-GAI-02：gai-links 检出缺失双链 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-GAI-02 |
| **PRD 断言** | B2（任务书要求：注入断链 → gai-links 检出） |
| **路径** | 路径 A |
| **步骤** | 1. GAI 夹具含 DPL-101/DPL-102<br>2. wiki 只有 DPL-101 页（DPL-102 缺）<br>3. 引擎层：fetch_events + 逐 ID 查 wiki 页存在性<br>4. CLI 层：`memctl gai-links` |
| **预期结果** | 1. 报告 DPL-102 缺 wiki 页（断链）<br>2. DPL-101 不报（已有页）<br>3. 不自动建页<br>4. 优先级列 P1-01 不产生假断链（MEM-QA-02 回归） |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-GAI-01 |
| **环境依赖** | 路径 A |

### V2-GAI-03：gai-links 表头变体解析（4 种）`[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-GAI-03 |
| **PRD 断言** | B2（间接）；架构 §4.5 / MEM-QA-02 回归 |
| **路径** | 路径 A（golden/gai-dirty.md） |
| **步骤** | 1. 使用 golden/gai-dirty.md（4 种表头变体 + 脏单元格）<br>2. `GaiAdapter.fetch_events()` |
| **预期结果** | 1. 4 events 正确解析：DPL-009 / DPL-010 / INF-011 / INF-012<br>2. external_id 全部为任务 ID 列值（非优先级列）<br>3. 脏行/表头行跳过 |
| **风险等级** | **MAJOR**（适配器输出错位 = B2/B5 断言基座错） |
| **分级依据** | 标准 §1.2：adapter 解析失败有 workaround（人工看 GAI）→ MAJOR |
| **环境依赖** | 路径 A（已有 test_gai.py 13 例覆盖） |

### V2-GAI-04：gai-links map_id + mirror_status `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-GAI-04 |
| **PRD 断言** | 架构 §4.5 source adapter |
| **路径** | 路径 A |
| **步骤** | 1. `GaiAdapter.map_id("DPL-009")` → "DPL-009"<br>2. `GaiAdapter.map_id("dpl-009")` → "DPL-009"（大小写无关）<br>3. `GaiAdapter.map_id("BOGUS")` → None<br>4. `GaiAdapter.mirror_status("wiki", "DPL-009")` → {status, detail} |
| **预期结果** | 1. 合法 ID 直配（大写规范化）<br>2. 非法 ID 返回 None<br>3. mirror_status 返回 {status: active/done, detail: title}（只读不写 GAI） |
| **风险等级** | **MAJOR**（map_id 错位 = gai-links/drift 双链基座错） |
| **分级依据** | 同 V2-GAI-03 |
| **环境依赖** | 路径 A（已有 test_map_id_case_insensitive 覆盖） |

### V2-GAI-05：gai-links 缺 GAI 文件降级 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-GAI-05 |
| **PRD 断言** | B2（容错）；架构 §4.4 / C9 降级 |
| **路径** | 路径 A |
| **步骤** | 1. MEM_GAI_FILE 指向不存在文件<br>2. `GaiAdapter(gai_file="/nonexistent").fetch_events()` |
| **预期结果** | 1. 返回空列表 []（不抛异常）<br>2. gai-links 命令输出空（无待办）或提示 GAI 文件缺失 |
| **风险等级** | **MAJOR**（GAI 缺失崩溃 = 周 cron 挂死） |
| **分级依据** | 标准 §1.2：崩溃无 workaround → MAJOR；空返回有 workaround → MAJOR |
| **环境依赖** | 路径 A（已有 test_missing_file_returns_empty 覆盖） |

### V2-GAI-06：gai-links done 行状态识别 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-GAI-06 |
| **PRD 断言** | B2（间接）；架构 §4.5 |
| **路径** | 路径 A |
| **步骤** | 1. GAI 行含 `✅ done`<br>2. `GaiAdapter.fetch_events()` |
| **预期结果** | 1. Event.kind = "done" / status = "done"<br>2. 无 ✅ 行 → kind = "active" / status = "active" |
| **风险等级** | **MINOR**（状态识别错位可人工核对） |
| **分级依据** | 标准 §1.2：状态识别错位有 workaround → MINOR |
| **环境依赖** | 路径 A（已有 test_done_row_kind_and_status 覆盖） |

---

## 6. demote 命令测试组（V2-DEM-01 ~ V2-DEM-05）

> 被测命令：`memctl demote <ID> --reason "…"`（架构 §4.4 定稿面）
> 验收门禁：B 组补充（V2 命令面）；demote 变更后双链不断裂（B4 间接）
> 引擎：**无独立引擎模块**（D2 标记 `[DEV-DEPENDENT]`）
> 注意：任务卡标记 `demote <ID> --status blocked|archived`（D2-F3 差异），本方案以架构为准（`--reason`）

### V2-DEM-01：demote 正常路径（status 变更 + 说明节 + bump + log）`[DEV-DEPENDENT]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DEM-01 |
| **PRD 断言** | B 组补充（V2 命令面）；架构 §4.4 demote |
| **路径** | 路径 A |
| **前置条件** | **demote 引擎实现 + CLI 接线**（当前无引擎） |
| **步骤** | 1. 构造 actions/P0-19.md（status=active）<br>2. `memctl demote P0-19 --reason "被上游阻塞"`<br>3. 检查 wiki 页 |
| **预期结果** | 1. 页 status 变更（active → blocked 或架构定义的目标状态）<br>2. 变更说明节（含 reason）追加<br>3. updated 时间戳 bump<br>4. log.md 追加 demote 事件<br>5. 原子 git 提交 |
| **风险等级** | **MAJOR**（V2 命令；写 wiki 语义错误有 workaround 手动改） |
| **分级依据** | 标准 §1.2：V2 功能缺陷不阻塞 MVP；降级可手动改 → MAJOR |
| **环境依赖** | 路径 A + **demote 引擎（待实现）** |

### V2-DEM-02：demote 后双链不断裂（B4 间接）`[DEV-DEPENDENT]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DEM-02 |
| **PRD 断言** | B4 间接（任务书要求：demote 变更后双链不断裂） |
| **路径** | 路径 A |
| **步骤** | 1. P0-19 页有入链（其他页 `[[P0-19]]`）<br>2. `memctl demote P0-19 --reason "X"`<br>3. `memctl lint` |
| **预期结果** | 1. demote 后 lint I1（断链）**不触发**（页仍在，只是 status 变）<br>2. 双链 `[[P0-19]]` 仍可解析到该页<br>3. 入链页不报断链 |
| **风险等级** | **MAJOR**（双链断裂 = 知识导航断裂） |
| **分级依据** | 标准 §1.2：双链断裂可人工补（有 workaround）→ MAJOR |
| **环境依赖** | 路径 A + demote 引擎 |

### V2-DEM-03：demote 不存在页（exit 1）`[DEV-DEPENDENT]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DEM-03 |
| **PRD 断言** | 架构 §4.2 退出码 |
| **路径** | 路径 A |
| **步骤** | 1. `memctl demote NONEXIST-999 --reason "X"` |
| **预期结果** | 1. exit 1（一般错误：页不存在）<br>2. stderr 明确报错 |
| **风险等级** | **MINOR**（错误处理） |
| **分级依据** | 标准 §1.2：错误提示有 workaround → MINOR |
| **环境依赖** | V2 CLI |

### V2-DEM-04：demote 无 --reason（用法错误 exit 2）`[DEV-DEPENDENT]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DEM-04 |
| **PRD 断言** | 架构 §4.2 退出码 |
| **路径** | 路径 A |
| **步骤** | 1. `memctl demote P0-19`（无 --reason） |
| **预期结果** | 1. exit 2（用法错误）或 exit 1（参数校验失败，视实现）<br>2. stderr 提示 --reason 必填 |
| **风险等级** | **MINOR** |
| **分级依据** | 标准 §1.2：用法错误有 workaround → MINOR |
| **环境依赖** | V2 CLI |

### V2-DEM-05：demote 镜像 L0 状态列（sed 级展示更新）`[DEV-DEPENDENT]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-DEM-05 |
| **PRD 断言** | 架构 §4.4 demote（镜像 L0 状态列） |
| **路径** | 路径 A |
| **步骤** | 1. mock GAI 含 P0-19 行<br>2. `memctl demote P0-19 --reason "X"`<br>3. 检查 GAI 文件状态列 |
| **预期结果** | 1. wiki 页 status 变更<br>2. GAI 展示层镜像状态列 sed 级更新（非语义写入；展示镜像由脚本执行，memctl 不写 L0）<br>3. **铁律 2 断言**：memctl 不直接写 kanban/GAI L0（镜像由外部脚本 sed） |
| **风险等级** | **MAJOR**（铁律 2 违反 = 状态回写环） |
| **分级依据** | 标准 §1.2：memctl 直接写 L0 = 违反铁律 2（数据完整性），但 demote 镜像由脚本执行非 memctl → MAJOR |
| **环境依赖** | V2 CLI + mock GAI |

---

## 7. 幂等性测试组（V2-IDM-01 ~ V2-IDM-04）

> 任务书要求：update 多次跑一致（幂等性测试）
> 架构 §6.1：幂等 = 同一事件重复触发同一结果；骨架页已存在则更新不重建

### V2-IDM-01：update --plan 多次跑候选集一致 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-IDM-01 |
| **PRD 断言** | B1（幂等性）；架构 §6.1；C5 |
| **路径** | 路径 A |
| **步骤** | 1. 同一 source + 同一 db<br>2. `compute_candidates(db, source)` 跑 3 次<br>3. 比较候选集 |
| **预期结果** | 1. 3 次候选页清单完全一致（page_id / hit_count / terms）<br>2. 排序一致<br>3. 零随机性（确定性） |
| **风险等级** | **MAJOR**（幂等失败 = 候选集不稳定，OC 裁定不可重复） |
| **分级依据** | 标准 §1.2：候选集抖动有 workaround（多次跑取交集）→ MAJOR |
| **环境依赖** | 路径 A |

### V2-IDM-02：update --apply 幂等（同一事件不产生重复页）`[CLI-PENDING]` `[LLM-REQUIRED]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-IDM-02 |
| **PRD 断言** | B1 / C5（§7.3）；架构 §6.1 |
| **路径** | 路径 A |
| **前置条件** | V2 CLI + update --apply 实现 |
| **步骤** | 1. 同一 source 对同一 wiki 触发 `update --apply` 两次<br>2. 比较结果 |
| **预期结果** | 1. 第一次 apply 改写候选页<br>2. 第二次 apply 不产生重复页（骨架已存在则更新不重建）<br>3. lint 两次均 0<br>4. git diff 第二次为空或仅 updated 时间戳 |
| **风险等级** | **MAJOR**（幂等失败 = 重复页漂移） |
| **分级依据** | 标准 §1.2：重复页有 workaround（手动合并）→ MAJOR |
| **环境依赖** | V2 CLI + mock LLM |

### V2-IDM-03：drift 多次跑一致 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-IDM-03 |
| **PRD 断言** | B5（幂等性） |
| **路径** | 路径 A |
| **步骤** | 1. 同一 wiki + kanban + GAI 状态<br>2. `three_way_check(...)` 跑 3 次<br>3. 比较 diffs |
| **预期结果** | 1. 3 次 diffs 完全一致<br>2. 只读（无副作用） |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-IDM-01 |
| **环境依赖** | 路径 A |

### V2-IDM-04：drift 幂等只读无副作用 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-IDM-04 |
| **PRD 断言** | B5；铁律 2 |
| **路径** | 路径 A |
| **步骤** | 1. 记录 wiki/kanban/GAI 文件哈希<br>2. `three_way_check(...)`<br>3. 再次哈希对比 |
| **预期结果** | 1. 所有文件哈希不变<br>2. drift 全程零写入 |
| **风险等级** | **BLOCKER**（铁律 2 违反 = 状态回写环） |
| **分级依据** | 标准 §1.2：drift 写文件 = 铁律 2 违反（数据完整性）→ BLOCKER |
| **环境依赖** | 路径 A |

---

## 8. 负面注入测试组（V2-NEG-01 ~ V2-NEG-05）

> 任务书要求：注入断链 → gai-links 检出；注入差异 → drift 检出
> 负面测试 = 主动注入故障 → 验证检出能力

### V2-NEG-01：注入 GAI 断链 → gai-links/drift 检出 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-NEG-01 |
| **PRD 断言** | B2（任务书核心要求） |
| **路径** | 路径 A |
| **步骤** | 1. 一致状态（GAI ID ⊆ wiki actions）<br>2. **注入断链**：删 wiki/actions/DPL-101.md<br>3. `GaiAdapter.fetch_events()` 获取 GAI ID → 逐 ID 查 wiki<br>4. `three_way_check(...)` |
| **预期结果** | 1. gai-links 检出 DPL-101 缺页<br>2. drift 检出 `"GAI 待办缺 wiki 页: DPL-101"`<br>3. 其他 ID 不受影响 |
| **风险等级** | **MAJOR**（断链漏检 = 双链完整性失效） |
| **分级依据** | 标准 §1.2：断链漏检可人工补 → MAJOR |
| **环境依赖** | 路径 A |

### V2-NEG-02：注入 kanban 差异 → drift 检出 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-NEG-02 |
| **PRD 断言** | B2（任务书核心要求：注入差异 → drift 检出） |
| **路径** | 路径 A |
| **步骤** | 1. 一致状态<br>2. **注入差异**：mock kanban 新增活跃任务 t_99999999（wiki 无页）<br>3. `three_way_check(...)` |
| **预期结果** | 1. drift 检出 `"kanban 活跃任务缺 wiki 页: t_99999999"`<br>2. 修复（加 wiki 页）→ drift 空 |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-NEG-01 |
| **环境依赖** | 路径 A |

### V2-NEG-03：注入 index 不一致 → drift 检出 `[ENGINE-READY]` `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-NEG-03 |
| **PRD 断言** | B5 |
| **路径** | 路径 A |
| **步骤** | 1. 一致状态<br>2. **注入差异**：index.md 删除已存在文件的条目<br>3. `three_way_check(...)` |
| **预期结果** | 1. drift 检出 `"index.md 未收录: ..."`<br>2. 反向注入幽灵页 → 检出 `"index.md 幽灵页: ..."` |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 V2-NEG-01 |
| **环境依赖** | 路径 A |

### V2-NEG-04：注入冲突源 → contradictions 标记 `[CLI-PENDING]` `[LLM-REQUIRED]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-NEG-04 |
| **PRD 断言** | B4（任务书间接） |
| **路径** | 路径 A（golden/conflict-a.md + conflict-b.md） |
| **步骤** | 1. 注入 conflict-a.md（trigram 足够）<br>2. source 含冲突主张 → `update --apply`<br>3. 检查 contradictions 标记 |
| **预期结果** | 1. 冲突页打 `contradictions:` 标记<br>2. 双版本并存 |
| **风险等级** | **MAJOR** |
| **分级依据** | 标准 §1.2：矛盾漏标可人工发现 → MAJOR |
| **环境依赖** | V2 CLI + LLM |

### V2-NEG-05：注入 db 篡改 → lint 检出（非 V2 命令但回归保护）`[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-NEG-05 |
| **PRD 断言** | C7；架构 §5 |
| **路径** | 路径 A |
| **步骤** | 1. 构建 db<br>2. 手工 `UPDATE pages SET status='bogus'`<br>3. `memctl lint` |
| **预期结果** | 1. lint I4 检出 db 与文件不一致（checksum 不匹配）<br>2. exit 3 |
| **风险等级** | **BLOCKER**（C7 派生数据防漂移核心） |
| **分级依据** | 标准 §1.2：db 篡改不可检出 = 检索结果不可信 → BLOCKER |
| **环境依赖** | 路径 A（已有 test_cli_lint_detects_db_tamper 覆盖） |

---

## 9. 回归保护测试组（V2-REG-01 ~ V2-REG-04）

> 任务书要求：V2 命令不影响 MVP 7 命令行为
> V2 命令 CLI 接线后，必须验证 MVP 7 命令行为不变

### V2-REG-01：V2 stub → V2 接线后 MVP lint 仍零问题 `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-REG-01 |
| **PRD 断言** | A2 回归（MVP 门禁不受 V2 影响） |
| **路径** | 路径 B（真实 repo） |
| **步骤** | 1. V2 CLI 接线后<br>2. `./bin/memctl lint`（真实 repo）<br>3. 与 MVP VA 基线对比 |
| **预期结果** | 1. lint 退出码 0（零问题）<br>2. 四不变式 I1-I4 全 PASS<br>3. 与 VA 基线一致（V2 接线不破坏 lint） |
| **风险等级** | **BLOCKER**（V2 接线破坏 MVP 门禁 = 回归） |
| **分级依据** | 标准 §1.2：MVP 门禁回归无 workaround → BLOCKER |
| **环境依赖** | V2 CLI 接线 + 真实 repo |

### V2-REG-02：V2 stub → V2 接线后 MVP done --check 三态不变 `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-REG-02 |
| **PRD 断言** | A5 回归 |
| **路径** | 路径 A |
| **步骤** | 1. V2 接线后<br>2. `memctl done t_nonexist --check` → exit 1<br>3. `memctl done t_active --check` → exit 3<br>4. `memctl done t_done --check` → exit 0 |
| **预期结果** | 1. 三态退出码 1/3/0 不变（与 MVP VA 基线一致） |
| **风险等级** | **BLOCKER**（close.sh S3a 依赖 --check 语义） |
| **分级依据** | 标准 §1.2：done --check 语义破坏 = close.sh 闭环断裂 → BLOCKER |
| **环境依赖** | V2 CLI + mock kanban |

### V2-REG-03：V2 stub → V2 接线后 MVP query 仍命中 `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-REG-03 |
| **PRD 断言** | A3 回归 |
| **路径** | 路径 B |
| **步骤** | 1. V2 接线后<br>2. `memctl query "中间层"`（3 字 trigram）<br>3. `memctl query "中间"`（2 字 bigram） |
| **预期结果** | 1. 3 字命中对应页<br>2. 2 字通过 bigram 回退命中<br>3. 与 MVP VA 基线一致 |
| **风险等级** | **BLOCKER**（检索回归 = 北极星辅助指标失效） |
| **分级依据** | 标准 §1.2：检索失效无 workaround → BLOCKER |
| **环境依赖** | V2 CLI + 真实 repo |

### V2-REG-04：V2 stub → V2 接线后 index --rebuild 仍幂等 `[CLI-PENDING]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-REG-04 |
| **PRD 断言** | A4 回归 |
| **路径** | 路径 B |
| **步骤** | 1. V2 接线后<br>2. `memctl index --rebuild` × 2<br>3. `memctl lint` 前后均 0 |
| **预期结果** | 1. 两次 rebuild 后 pages/links 行数一致<br>2. lint 均 0 |
| **风险等级** | **BLOCKER**（C7 派生性回归） |
| **分级依据** | 标准 §1.2：重建不幂等 = db 漂移不可恢复 → BLOCKER |
| **环境依赖** | V2 CLI + 真实 repo |

---

## 10. V2 stub 阶段断言（当前可执行）

> V2 CLI 接线前，验证 4 命令 stub 行为正确（已有 test_cli.py `test_cli_v2_stubs_exit_2` 覆盖）

### V2-STB-01：V2 4 命令 stub exit 2 + 明确提示 `[ENGINE-READY]`

| 维度 | 内容 |
|------|------|
| **用例编号** | V2-STB-01 |
| **PRD 断言** | 架构 §4.1 / §4.2（V2 占位阶段契约） |
| **路径** | 路径 A |
| **步骤** | 1. `memctl update` / `memctl drift` / `memctl gai-links` / `memctl demote`<br>2. 检查退出码 + stderr |
| **预期结果** | 1. 4 命令均 exit 2（用法错误/占位）<br>2. stderr 含 "V2 未实现" 提示<br>3. 不崩溃、不静默 |
| **风险等级** | **MINOR**（stub 阶段契约） |
| **分级依据** | 标准 §1.2：stub 提示清晰有 workaround → MINOR |
| **环境依赖** | 路径 A（已有 pytest 覆盖） |

---

## 11. 覆盖矩阵

### 11.1 PRD §5.2 断言 × 用例覆盖

| PRD §5.2 断言 | 直接用例 | 引擎层先行 | CLI 层（pending） | 覆盖状态 |
|------------|---------|:---:|:---:|:---:|
| B1 update --plan + <20 文件 | V2-UPD-01/02/03/04/07/08 + V2-IDM-01/02 | ✅ 5 例可执行 | ⏳ 3 例 pending | ✅ |
| B2 drift 检出三方差异 + gai-links 零断链 | V2-DRF-01~08 + V2-GAI-01~06 + V2-NEG-01/02 | ✅ 12 例可执行 | ⏳ 6 例 pending | ✅ |
| B3 gai-links 缺失双链 + --fix 补（D2-F2：架构无 --fix） | V2-GAI-02 + V2-NEG-01 | ✅ 可执行 | ⏳ pending | ✅（以架构为准：报告不自动补） |
| B4 矛盾检测 contradictions 标记 | V2-UPD-06 + V2-NEG-04 | ⏳ 引擎待验证 | ⏳ pending | ✅（需 LLM） |
| B5 周 drift 干净为空 | V2-DRF-01 + V2-IDM-03/04 + V2-NEG-03 | ✅ 4 例可执行 | ⏳ pending | ✅ |
| demote 双链不断裂 | V2-DEM-01~05 | ❌ 待引擎 | ⏳ pending | ⏳ `[DEV-DEPENDENT]` |

### 11.2 任务书 5 项要求覆盖

| 要求 | 覆盖用例 |
|------|---------|
| 1. 每个命令的正常路径 + 边界 + 异常 | V2-UPD-01/03/04/08 / V2-DRF-01/06/08 / V2-GAI-03/05/06 / V2-DEM-03/04 |
| 2. 幂等性测试（update 多次跑一致） | V2-IDM-01/02/03/04 |
| 3. 负面测试（注入断链 → gai-links 检出；注入差异 → drift 检出） | V2-NEG-01/02/03/04/05 |
| 4. 回归保护（V2 不影响 MVP 7 命令） | V2-REG-01/02/03/04 |
| 5. 编号格式 V2-CMD-NN | 全部用例（V2-UPD/DRF/GAI/DEM/REG/IDM/NEG/STB） |

### 11.3 用例统计

| 分组 | 数量 | BLOCKER | MAJOR | MINOR | ENGINE-READY | CLI-PENDING | DEV-DEPENDENT | LLM-REQUIRED |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| update（V2-UPD-01~08） | 8 | 0 | 7 | 1 | 4 | 4 | 0 | 2 |
| drift（V2-DRF-01~08） | 8 | 1 | 7 | 0 | 7 | 1 | 0 | 0 |
| gai-links（V2-GAI-01~06） | 6 | 0 | 5 | 1 | 6 | 0 | 0 | 0 |
| demote（V2-DEM-01~05） | 5 | 0 | 4 | 1 | 0 | 0 | 5 | 0 |
| 幂等（V2-IDM-01~04） | 4 | 1 | 3 | 0 | 3 | 1 | 0 | 1 |
| 负面（V2-NEG-01~05） | 5 | 1 | 3 | 0 | 4 | 1 | 0 | 1 |
| 回归（V2-REG-01~04） | 4 | 4 | 0 | 0 | 0 | 4 | 0 | 0 |
| stub（V2-STB-01） | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 |
| **合计** | **41** | **7** | **29** | **4** | **25** | **11** | **5** | **4** |

> **当前可执行**：25 例 `[ENGINE-READY]`（blast/drift/gai 引擎层断言可立即跑，其中多数已有 pytest 覆盖）
> **CLI 接线后**：+11 例 `[CLI-PENDING]`
> **demote 引擎实现后**：+5 例 `[DEV-DEPENDENT]`
> **需 LLM**：4 例 `[LLM-REQUIRED]`（update --apply / 矛盾检测）

### 11.4 与 v2 方案的关系

v3 的 41 例**不替代** v2 的 56 例（v2 含 MVP A1-A9 全量 + 北极星 C1-C4 + 边界 BE-01~18 + 端到端 TS-01~07）。v3 是 V2 验收的**专项深化**：

- v2 的 TC-22~26（B 组 6 例）→ v3 扩展为 V2-UPD/DRF/GAI 组 22 例（+16 例深化）
- v2 的 BC-05（demote 1 例）→ v3 扩展为 V2-DEM 组 5 例（+4 例深化）
- v2 的 BE-07/08（幂等/冲突 2 例）→ v3 扩展为 V2-IDM/NEG 组 9 例（+7 例深化）
- v2 的 TS-04/07（V2 端到端 2 例）→ v3 引擎层断言已覆盖核心逻辑
- v3 新增 V2-REG 回归组 4 例（v2 未覆盖 V2 接线后 MVP 回归）

---

## 12. 测试执行顺序与依赖

```
Phase 0: V2 stub 阶段（当前可执行）
  ├── V2-STB-01: 4 命令 stub exit 2（已有 pytest 覆盖）
  └── 引擎层先行：blast/drift/gai 函数级断言（已有 pytest 22 例覆盖）

Phase 1: 引擎层深化（当前可执行，25 例 [ENGINE-READY]）
  ├── V2-UPD-01/02/03/04: blast compute_candidates（候选集/不读全 wiki/空候选/无 db）
  ├── V2-DRF-01~07: drift three_way_check（空/缺页/GAI/index/只读/降级/done 排除）
  ├── V2-GAI-01~06: GaiAdapter（零断链/检出/表头变体/map_id/降级/done 状态）
  ├── V2-IDM-01/03/04: 幂等（update 候选一致/drift 一致/drift 只读）
  └── V2-NEG-01/02/03/05: 负面注入（断链/kanban 差异/index 不一致/db 篡改）

Phase 2: CLI 接线后（+11 例 [CLI-PENDING]，dev 交付 V2 CLI 后）
  ├── V2-UPD-05/06/07/08: update --apply/矛盾/--json/无参
  ├── V2-DRF-08: drift --json
  ├── V2-IDM-02: update --apply 幂等
  ├── V2-NEG-04: 注入冲突源
  └── V2-REG-01~04: MVP 回归（lint/done --check/query/index --rebuild）

Phase 3: demote 引擎实现后（+5 例 [DEV-DEPENDENT]）
  ├── V2-DEM-01: 正常路径（status + 说明节 + bump + log）
  ├── V2-DEM-02: 双链不断裂
  ├── V2-DEM-03: 不存在页 exit 1
  ├── V2-DEM-04: 无 --reason exit 2
  └── V2-DEM-05: 镜像 L0 状态列（铁律 2）
```

### 12.1 预估执行时间

| Phase | 内容 | 用例 | 时间 |
|-------|------|:---:|:---:|
| Phase 0 | V2 stub 验证 + pytest 全量回归 | V2-STB-01 | 0.5h |
| Phase 1 | 引擎层深化（路径 A 全量） | 25 例 [ENGINE-READY] | 3.0h |
| Phase 2 | CLI 接线后补跑 | 11 例 [CLI-PENDING] | 2.0h |
| Phase 3 | demote 引擎实现后 | 5 例 [DEV-DEPENDENT] | 1.5h |
| **合计** | | **41** | **≈ 7.0h** |

> Phase 1 的 25 例中，~18 例已有 pytest 覆盖（test_drift 9 + test_gai 13），v3 执行时确认 pytest 全绿后补跑引擎层 CLI 断言即可，实际增量约 1.5h。

---

## 13. 契约差异处置（D2-F1~F3）

> 标准第 6 节论证流程：发现 → 研发评估 → 通过/驳回/暂缓

### D2-F1：`update [--dry-run]` vs `update <source> --plan/--apply`

- **发现**：任务卡标记 `update [--dry-run]`，架构 §4.4 定稿为 `update <source> --plan` / `--apply <pages…>`
- **影响**：参数签名不同（--dry-run 无 source 参数 vs --plan 需要 source）；语义近似（只列不动手）
- **QA 立场**：以架构 §4.4 为权威（架构是接口权威）；`--dry-run` 约等于 `--plan` 但需研发确认
- **处置**：本方案全部用例引用 `--plan / --apply` 面；若研发采用 `--dry-run`，V2-UPD 组用例参数需同步修订

### D2-F2：`gai-links [--fix]` vs `gai-links`（无 --fix）

- **发现**：任务卡标记 `gai-links [--fix]`，架构 §4.4 为 `gai-links`（无 --fix）
- **影响**：架构明确「缺页 → 报告（不自动建页，交 update --plan 流程）」；`--fix` 若存在需研发定义自动补链行为
- **QA 立场**：以架构为准（gai-links 只校验/报告，不自动建页）
- **处置**：本方案 V2-GAI 组无 --fix 断言；若研发实现 --fix，新增 V2-GAI-07（--fix 自动补链 + 幂等）

### D2-F3：`demote <ID> --status blocked|archived` vs `demote <ID> --reason "…"`

- **发现**：任务卡标记 `demote --status blocked|archived`，架构 §4.4 为 `demote --reason "…"`
- **影响**：status 直接指定 vs reason 推断是语义差异；架构说「status 变更 + 变更说明节」暗示 reason 驱动
- **QA 立场**：以架构为准（--reason）；但任务卡的 --status 枚举（blocked|archived）可作为 status 映射参考
- **处置**：本方案 V2-DEM 组用例引用 `--reason`；若研发采用 `--status`，V2-DEM-01 预期结果需改为「status 变更为 --status 指定值」

### D2 处置 SLA（标准 §8）

- 响应：4h 内研发确认采用哪一面
- 定位：8h 内给出初步判定 + 进度同步
- 方案：24h 内给出最终接口面
- 若研发驳回 QA 的架构面立场 → 启动有成本申诉（标准 §6.3）

---

## 14. 分级依据对照（标准 §1.2 / §8 / §10 落实说明）

| 标准条款 | 本方案落实 |
|---------|-----------|
| §1.2 判定公式 | 每个用例"风险等级" = 该断言失败时的真实缺陷级别，按公式逐条附"分级依据"；7 个 BLOCKER 均为铁律违反或 MVP 门禁回归 |
| §2 安全漏洞独立判定 | 本系统为本地记忆库（C 级内部数据），无 OWASP 暴露面；V2-DEM-05 铁律 2 按数据完整性独立判定 |
| §3 性能退化 | V2-UPD-02（<20 文件）为编译期性能断言；不满足按 MAJOR |
| §5 分级示例 | V2-DEM 组的 `[DEV-DEPENDENT]` 标注体现"无法判断时取高级别 + triage_needed"原则 |
| §8 SLA | D2-F1~F3 契约差异已按发现流程提交：响应 4h / 定位 8h / 方案 24h |
| §9 QA SLA | 引擎层先行用例（Phase 1）当前可执行；CLI 接线后补跑 |
| §10 发布门禁 | V2 门禁 = B1-B5 全绿 + BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉；D2 差异需裁定后方可执行 CLI 层断言 |
| §11 产品红线 | V2 命令不涉及本体文件替换；demote 镜像 L0 状态列（V2-DEM-05）验证铁律 2 |

---

## 15. 一句话结论

v3 测试方案聚焦 V2 四命令（update/drift/gai-links/demote）的完整验收：**41 用例**（7 BLOCKER / 29 MAJOR / 4 MINOR + 1 stub），25 例引擎层 `[ENGINE-READY]` 当前可执行（blast/drift/gai 函数级断言，多数已有 pytest 22 例覆盖），11 例 `[CLI-PENDING]` 等 dev CLI 接线，5 例 `[DEV-DEPENDENT]` 等 demote 引擎实现；覆盖 B1-B5 全量门禁 + 幂等 + 负面注入 + MVP 回归保护；发现 3 项契约差异（D2-F1~F3：任务卡命令标记 vs 架构 §4.4 定稿面）已按标准 §6 论证流程提交待研发裁定；**demote 是 V2 四命令中唯一无引擎实现的命令**（需研发从零实现）；V2 执行约 **7.0h**（Phase 1 引擎层 3h + Phase 2 CLI 2h + Phase 3 demote 1.5h + Phase 0 stub 0.5h）。
