# P0-15 D1 架构发现测试方案：修复验证

> 版本：v1.0 | 状态：Draft
> 编制日期：2026-07-10
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 架构依据：`docs/arch-p0-15-appeal-mechanism.md` v1.0 §5
> 来源任务：架构审查 (t_34c5a7a0) — P0-15 驳回申诉机制

---

## 目录

1. [背景与范围](#1-背景与范围)
2. [架构发现概览](#2-架构发现概览)
3. [A1: 角色级访问控制缺失 (MAJOR)](#3-a1-角色级访问控制缺失)
4. [A2: STATE_PREFIXES 与 YAML 不同步 (MAJOR)](#4-a2-state_prefixes-与-yaml-不同步)
5. [A3: reinstated 后原始卡片未自动关闭 (MINOR)](#5-a3-reinstated-后原始卡片未自动关闭)
6. [A4: assignee 硬编码 (MINOR)](#6-a4-assignee-硬编码)
7. [A5: 申诉日志无结构化格式 (MINOR)](#7-a5-申诉日志无结构化格式)
8. [集成回归验证](#8-集成回归验证)
9. [测试矩阵总览](#9-测试矩阵总览)
10. [发布门禁评估](#10-发布门禁评估)
11. [风险矩阵](#11-风险矩阵)

---

## 1. 背景与范围

### 1.1 D1 阶段说明

P0-15 初始交付（de717ad）的 QA 测试已通过发布门禁（51 PASS / 6 FAIL / 6 SKIP，BLOCKER=0），已于 2026-07-09 发布。架构审查（t_34c5a7a0）在此基础上发现了 5 项改进建议（2 MAJOR + 3 MINOR），不阻塞当前版本，建议在 P0-16 排期修复。

本测试方案用于 **P0-16 修复后的验证**，覆盖 5 项架构发现的修复验收。

### 1.2 被测对象

| 模块 | 涉及发现 | 变更类型 |
|------|---------|---------|
| `scripts/lib/kanban_helpers.py` | A2 | STATE_PREFIXES 从 YAML 自动生成 |
| `scripts/lib/config_loader.py` | A2, A4 | 新增 `get_state_prefixes()` / `get_default_assignee()` |
| `scripts/product_rule.py` | A1, A3, A4 | 角色验证 + reinstated 关闭原始卡片 + assignee 从 YAML 读取 |
| `scripts/appeal.py` | A1, A5 | 角色验证 + 结构化日志 |
| `scripts/dev_reject.py` | A1 | 角色验证 |
| `scripts/defer.py` | A1 | 角色验证 |
| `scripts/downgrade_notify.py` | A5 | 结构化日志 |
| `scripts/appeal_tracker.py` | A5 | 结构化日志解析 |
| `config/qa-classification.yaml` | A2, A4 | 新增 roles / assignee_mapping section |

### 1.3 非覆盖范围

- `hermes kanban` CLI 身份验证能力本身（属于 hermes 项目范围，本方案仅验证脚本对 CLI 返回结果的正确使用）
- 原始 P0-15 测试方案覆盖的功能回归（已有 L1-L6 63 项测试，本方案聚焦新增变更）

---

## 2. 架构发现概览

| ID | 发现 | 级别 | 修复模块 | 核心风险 | 测试重点 |
|----|------|:---:|------|------|------|
| **A1** | 角色级访问控制缺失 | **MAJOR** | 4 脚本 (product_rule, appeal, dev_reject, defer) | 任何人可越权操作；修复后正常角色被误拦 | 角色→脚本映射校验 + 门控拒绝/通过 |
| **A2** | STATE_PREFIXES 与 YAML 不同步 | **MAJOR** | kanban_helpers + config_loader | 修复后状态解析回归；YAML 变更传播正确性 | 前缀自动生成逻辑 + 端到端状态机一致性 |
| **A3** | reinstated 后原始卡片未关闭 | **MINOR** | product_rule | 关闭失败不影响新卡片创建；appeal_tracker 计数改善 | 原始卡片关闭正确性 + tracker 分类准确 |
| **A4** | assignee 硬编码 | **MINOR** | product_rule + YAML | YAML 配置错误时回退行为 | 配置读取 + 回退机制 |
| **A5** | 申诉日志无结构化格式 | **MINOR** | 3 脚本 + appeal_tracker | 格式兼容性；旧日志解析退化 | 新格式正确 + 向后兼容旧格式解析 |

---

## 3. A1: 角色级访问控制缺失

### 3.1 修复要求

架构文档 §4.4 建议方案：

1. `hermes kanban whoami` 返回当前用户身份（profile name）
2. YAML 中定义角色映射：`roles: {product: ["game-product"], qa: ["game-qa"], dev: ["game-engine"]}`
3. 脚本在执行关键操作前验证当前用户角色与操作匹配

### 3.2 测试用例

| TC-ID | 测试场景 | 前置条件 | 操作 | 预期结果 | 优先级 |
|-------|---------|---------|------|---------|:---:|
| **A1-01** | YAML 角色映射完整加载 | YAML 含 `roles` section | `config_loader.get_roles()` | 返回 dict: `{product: [profiles], qa: [...], dev: [...]}`，每个 key 对应非空 list | P1 |
| **A1-02** | product_rule.py 允许产品角色执行 | `hermes kanban whoami → {profile: "game-product"}` | `product_rule.py TASK --verdict upheld` | 正常执行，无鉴权错误 | P0 |
| **A1-03** | product_rule.py 拒绝非产品角色 | `hermes kanban whoami → {profile: "game-engine"}` | `product_rule.py TASK --verdict upheld` | exit(1)，stderr 含 "鉴权拒绝" / "仅产品角色" / 当前角色名 | P0 |
| **A1-04** | appeal.py 允许 QA 角色执行 | `hermes kanban whoami → {profile: "game-qa"}` | `appeal.py TASK --evidence "新复现步骤：..."` | 正常执行（先通过鉴权，后续状态机校验独立） | P1 |
| **A1-05** | appeal.py 拒绝非 QA 角色 | `hermes kanban whoami → {profile: "game-product"}` | `appeal.py TASK --evidence "..."` | exit(1)，stderr 含 "仅 QA 角色" | P1 |
| **A1-06** | dev_reject.py 允许研发角色执行 | `hermes kanban whoami → {profile: "game-engine"}` | `dev_reject.py TASK --reason by_design --detail "xxx"` | 正常执行 | P1 |
| **A1-07** | defer.py 允许研发角色执行 | `hermes kanban whoami → {profile: "game-engine"}` | `defer.py TASK --target-version v2.4.0 --reason "xxx" --frank-confirmed` | 正常执行 | P1 |
| **A1-08** | whoami 不可用时降级行为 | `hermes kanban whoami` 返回非零或 JSON 解析失败 | `product_rule.py TASK --verdict upheld` | 友好报错（非 JSONDecodeError traceback），含 "无法获取用户身份" 说明 | P1 |
| **A1-09** | YAML roles 中一个 key 对应多个 profile | YAML: `qa: ["game-qa", "game-qa-senior"]` | `hermes kanban whoami → {profile: "game-qa-senior"}` → `appeal.py` | 正常通过鉴权 | P2 |
| **A1-10** | YAML roles 缺失时安全默认 | YAML 不含 `roles` key | 任意脚本鉴权 | 应根据默认策略：要么全部放行（backward-compat）并 WARNING，要么全部拒绝并提示配置缺失 | P2 |

### 3.3 成功标准

| 维度 | 标准 | 测量方法 |
|------|------|---------|
| **功能正确** | 4 脚本（product_rule, appeal, dev_reject, defer）均在操作前执行角色鉴权 | 代码审查：`main()` 中 hermes CLI 调用前存在 `verify_role()` |
| **拒绝准确** | 非匹配角色 100% 被拒绝（A1-03, A1-05） | 负面路径测试 |
| **通过不误拦** | 匹配角色 100% 通过（A1-02, A1-04, A1-06, A1-07） | 正向路径测试 |
| **错误友好** | whoami 不可用时给出中文错误消息，不抛 Python traceback | 异常路径测试（A1-08） |
| **零回归** | 原始 P0-15 测试套件（test_integration.py 等）中不因鉴权新增而失败 | 全量 regression 运行 |
| **判定公式** | A1 修复不引入新 BLOCKER：修复本身不阻断现有申诉流程 | §1.2 五步判定 |

### 3.4 风险等级：MEDIUM

- **修复风险**：如果 `hermes kanban whoami` 不可靠（CLI 版本差异），可能误拦所有合法操作 → **建议在鉴权层提供 `--skip-auth` debug flag**
- **回归风险**：低。鉴权是纯加法（在执行路径前端插入），不影响已有业务逻辑
- **测试依赖**：需要能 mock `subprocess.run` 的返回值来模拟 different roles（A1-02~A1-07 可通过设计可测试接口解决）

---

## 4. A2: STATE_PREFIXES 与 YAML 不同步

### 4.1 修复要求

架构文档 §5.2 建议方案：

1. STATE_PREFIXES 不再硬编码，改为从 YAML `state_machine.transitions` 自动生成
2. 收集所有 transition 的 "to" 目标状态，排除隐式状态（NEW/OPEN），生成正则前缀列表
3. YAML 中补充 DUPLICATE/WITHDRAWN 的 transition 定义

### 4.2 测试用例

| TC-ID | 测试场景 | 前置条件 | 操作 | 预期结果 | 优先级 |
|-------|---------|---------|------|---------|:---:|
| **A2-01** | 自动生成的 STATE_PREFIXES 与实际 YAML transitions 一致 | YAML 含 14 transitions（当前状态） | 调用 `_build_state_prefixes()` | 返回列表与 YAML transitions 的 `to` 字段完全一致（排除 NEW/OPEN） | P0 |
| **A2-02** | YAML transitions 新增状态后前缀自动包含 | 在 YAML 中添加 `{from: "RESOLVED", to: "ARCHIVED"}` | 调用 `_build_state_prefixes()` | 结果包含 `("ARCHIVED", r'^\[ARCHIVED\]')` | P1 |
| **A2-03** | YAML transitions 删除状态后前缀自动排除 | 从 YAML 中删除 DUPLICATE 和 WITHDRAWN transition | 调用 `_build_state_prefixes()` | 结果不再包含 DUPLICATE/WITHDRAWN 前缀 | P1 |
| **A2-04** | get_current_qa_state() 使用生成的前缀仍正确工作 | 自动生成的 STATE_PREFIXES 已就位 | Mock comments: `[{body: "[REJECTED] by design"}]` → `get_current_qa_state()` | 返回 "REJECTED" | P0 |
| **A2-05** | get_current_qa_state() 对新增的 DUPLICATE 前缀正确识别 | STATE_PREFIXES 含 DUPLICATE | Mock comment: `[{body: "[DUPLICATE] see #1234"}]` | 返回 "DUPLICATE" | P1 |
| **A2-06** | 全部 4 条申诉核心路径状态转换端到端 | 自动生成前缀 | 模拟 comment 序列：REJECTED → APPEAL → RULING | `get_current_qa_state()` 返回 "RULING"（last-write-wins） | P0 |
| **A2-07** | 降级路径状态转换 | 自动生成前缀 | 模拟 comment 序列：CONFIRMED → DOWNGRADE | `get_current_qa_state()` 返回 "DOWNGRADE" | P1 |
| **A2-08** | 暂缓路径状态转换 | 自动生成前缀 | 模拟 comment 序列：OPEN → DEFERRED | `get_current_qa_state()` 返回 "DEFERRED" | P1 |
| **A2-09** | 无状态 comment 时返回 None | 自动生成前缀 | 无任何前缀匹配的 comments | `get_current_qa_state()` 返回 None | P1 |
| **A2-10** | YAML 与 STATE_PREFIXES 差异检测 | 修复完成后 | 扫描 YAML transitions 的 `to` 字段 vs STATE_PREFIXES 的动态生成结果 | 差异 = 0（100% 一致） | P0 |

### 4.3 成功标准

| 维度 | 标准 | 测量方法 |
|------|------|---------|
| **一致性** | STATE_PREFIXES 与 YAML transitions 自动保持同步（A2-01, A2-10） | 差异检测脚本：扫描 YAML `to` states vs 生成的前缀 |
| **可扩展** | 新增/删除 YAML transition 时前缀自动跟随（A2-02, A2-03） | 修改 YAML 后重新加载验证 |
| **功能不退化** | get_current_qa_state() 对 4 条申诉路径全部返回正确状态（A2-04~A2-09） | Mock comment 序列测试 |
| **判定公式** | A2 修复不引入新 BLOCKER：状态解析不应因重构而回归 | P0-15 原始 L2 测试全量通过 |

### 4.4 风险等级：HIGH

- **修复风险**：状态解析是申诉流程的核心基础。如果自动生成逻辑有 bug（如遗漏某些 state、生成错误的正则），可能导致状态判断全面失效
- **回归风险**：MEDIUM。`get_current_qa_state()` 是 5 个生产脚本的依赖项
- **缓解措施**：
  1. 保留手动 STATE_PREFIXES 作为 smoke check 参考
  2. 在 `_build_state_prefixes()` 中添加一致性断言：若生成结果与旧的手动列表有差异，打印 WARNING
  3. A2-10 差异检测应作为 CI gate

---

## 5. A3: reinstated 后原始卡片未自动关闭

### 5.1 修复要求

架构文档 §5.5 建议方案：

1. `product_rule.py --verdict reinstated` 创建新卡片后，追加 `[CLOSED]` comment + 新卡片链接到原始卡片
2. 或直接调用 hermes kanban status 变更（如果 CLI 支持）

### 5.2 测试用例

| TC-ID | 测试场景 | 前置条件 | 操作 | 预期结果 | 优先级 |
|-------|---------|---------|------|---------|:---:|
| **A3-01** | reinstated 后原始卡片获得 [CLOSED] comment | 卡片在 APPEAL 状态 | `product_rule.py TASK --verdict reinstated --level MAJOR` | 原始卡片出现 `[CLOSED]` comment，含新卡片 ID 引用 | P0 |
| **A3-02** | [CLOSED] comment 不影响 RULING comment | 同 A3-01 | 查看 comment 历史 | 顺序：`[RULING] reinstated MAJOR` comment 在前，`[CLOSED]` comment 在后 | P1 |
| **A3-03** | upheld 裁定**不**产生 [CLOSED] comment | 卡片在 APPEAL 状态 | `product_rule.py TASK --verdict upheld` | 仅产生 `[RULING] upheld` comment，无 [CLOSED] | P1 |
| **A3-04** | appeal_tracker classify_task() 正确分类已关闭的 reinstated 卡片 | 原始卡片有 [CLOSED] comment + status="done" | `classify_task(task)` | 不应误判为 "rejected_accepted"（应正确流入"appealed"→"other"或按关闭状态正常分类） | P1 |
| **A3-05** | appeal_tracker 统计中 reinstated 卡片不被计为"驳回已接受" | reinstated 原始卡片已关闭 | 运行 appeal_tracker | rejected_accepted 计数不因 reinstated 而虚增 | P1 |
| **A3-06** | 新创建的 reinstated 卡片与原始卡片关联清晰 | reinstated 成功 | 新卡片 body | 含原始卡片 ID + 裁定级别 + 时间戳 | P2 |
| **A3-07** | 原始卡片关闭失败不阻塞新卡片创建 | hermes kanban comment 断开（模拟失败） | `product_rule.py --verdict reinstated` | 新卡片仍正常创建，原始卡片关闭失败打印 WARNING（非 exit(1)） | P2 |

### 5.3 成功标准

| 维度 | 标准 | 测量方法 |
|------|------|---------|
| **功能正确** | reinstated 后原始卡片被标记为 CLOSED（A3-01），upheld 不受影响（A3-03） | 检查 comment 历史 |
| **追踪准确** | appeal_tracker 统计因原始卡片关闭而改善（A3-04, A3-05） | appeal_tracker --json 输出 |
| **隔离性好** | 原始卡片关闭失败不阻塞新卡片创建（A3-07） | 故障注入 |
| **判定公式** | user_visible（卡片状态） + 功能改善（非阻断） → MINOR | §1.2 |

### 5.4 风险等级：LOW

- **修复风险**：低。仅在 product_rule.py 的 reinstated 分支末尾增加 1 次 `comment()` 调用
- **回归风险**：极低。不改变现有业务流程逻辑
- **注意**：若 hermes kanban 本身不支持对已 closed 的卡片 comment，需验证此边界（但目前 comment 不依赖卡片状态）

---

## 6. A4: assignee 硬编码

### 6.1 修复要求

架构文档 §4.3 建议方案：

1. `product_rule.py` L93 的 `assignee="game-engine"` 从 YAML 读取
2. YAML 中新增 `assignee_mapping` section，如：`reinstated_default_assignee: "game-engine"`
3. 或从 A1 的 `roles.dev` 列表中取第一位

### 6.2 测试用例

| TC-ID | 测试场景 | 前置条件 | 操作 | 预期结果 | 优先级 |
|-------|---------|---------|------|---------|:---:|
| **A4-01** | assignee 从 YAML 读取 | YAML: `reinstated_default_assignee: "game-engine"` | `product_rule.py --verdict reinstated --level MAJOR` | 新卡片的 assignee = "game-engine"（与修复前一致） | P0 |
| **A4-02** | YAML 中修改 assignee 后生效 | 修改 YAML: `reinstated_default_assignee: "game-engine-v2"` | 同上 | 新卡片 assignee = "game-engine-v2" | P1 |
| **A4-03** | YAML 缺少 assignee 配置时的回退 | YAML 不含 `reinstated_default_assignee` | 同上 | 回退到默认值 + 打印 WARNING（如回退到 "game-engine" 或从 roles.dev[0] 取） | P1 |
| **A4-04** | YAML assignee 为空字符串时的处理 | `reinstated_default_assignee: ""` | 同上 | 打印 WARNING 并使用回退默认值 | P2 |
| **A4-05** | 确认代码中无硬编码 "game-engine" 字符串 | 修复后 | `grep -n "game-engine" scripts/product_rule.py` | 仅出现在 YAML 读取结果的使用处，无硬编码常量赋值 | P1 |

### 6.3 成功标准

| 维度 | 标准 | 测量方法 |
|------|------|---------|
| **功能一致** | 默认行为不变（A4-01：新卡片 assignee 仍为 "game-engine"） | 端到端测试 |
| **可配置** | 修改 YAML 后行为跟随（A4-02） | 配置变更测试 |
| **健壮性** | 配置缺失/异常有合理回退（A4-03, A4-04） | 异常配置测试 |
| **无残留硬编码** | 代码中无 `assignee="game-engine"` 字面量（A4-05） | grep 验证 |
| **判定公式** | 非 user_visible（内部配置）→ MINOR | §1.2 |

### 6.4 风险等级：LOW

- **修复风险**：极低。单一值读取路径
- **回归风险**：极低。仅影响新卡片创建时的 assignee 字段

---

## 7. A5: 申诉日志无结构化格式

### 7.1 修复要求

架构文档 §4.3 建议方案：

1. appeal_tracker 的 `has_ruling()` / `classify_task()` 依赖 `body.startswith("[RULING]")` 的纯文本匹配
2. 可选改进：comment body 中包含 JSON metadata block（如 `<!--qa-meta: {"state":"RULING","verdict":"upheld"}-->`）
3. 或至少：comment body 具有一致的键值对格式（如 `**状态**: RULING | **裁定**: upheld`）

### 7.2 测试用例

| TC-ID | 测试场景 | 前置条件 | 操作 | 预期结果 | 优先级 |
|-------|---------|---------|------|---------|:---:|
| **A5-01** | 新格式 [RULING] 含结构化元数据 | 修复后的 product_rule.py | product_rule.py 发起 upheld 裁定 | comment body 含 `[RULING]` 前缀 + 结构化字段（如 YAML front matter 块或 JSON metadata 块） | P1 |
| **A5-02** | appeal_tracker 解析新格式 | 新格式 comment 存在 | `classify_task()` | 能正确提取 state/verdict/level 等字段（不依赖纯文本 `startswith`） | P1 |
| **A5-03** | 新格式与旧格式 comment 共存时向后兼容 | 混合 comment: 旧格式 `[RULING] upheld — 维持驳回` + 新格式带 metadata | `has_ruling()` / `classify_task()` | 两种格式均正确识别 | P0 |
| **A5-04** | dev_reject.py 新格式 | 修复后 | `dev_reject.py --reason by_design --detail "xxx"` | [REJECTED] comment 含结构化字段 | P1 |
| **A5-05** | appeal.py 新格式 | 修复后 | `appeal.py --evidence "..." --evidence-type repro` | [APPEAL] comment 含结构化字段 | P1 |
| **A5-06** | downgrade_notify.py 新格式 | 修复后 | `downgrade_notify.py --from BLOCKER --to MAJOR --reason "xxx"` | [DOWNGRADE] comment 含结构化字段 | P1 |
| **A5-07** | appeal_tracker 解析新格式的 downgrade | 新格式 [DOWNGRADE] comment | `classify_task()` | 正确识别为 "downgraded" | P2 |
| **A5-08** | 结构化 metadata 非法 JSON/格式时不崩溃 | 手工写入非法的 metadata 块 | `classify_task()` | 优雅退化到旧前缀匹配，打印 WARNING（非 crash） | P2 |
| **A5-09** | 只含 [RULING] 文本引用但非真实裁定的 comment 不被误判 | comment body: "可以参考 [RULING] 的案例" | `has_ruling()` | 返回 False（结构化解析区分 metadata 和普通文本引用） | P1 |

### 7.3 成功标准

| 维度 | 标准 | 测量方法 |
|------|------|---------|
| **结构化** | 所有 4 类状态 comment（REJECTED/APPEAL/RULING/DOWNGRADE）均含统一的结构化元数据格式 | 审查 comment 输出 |
| **向后兼容** | 旧格式 comment 仍可正确解析（A5-03） | 混合数据回归测试 |
| **误判免疫** | 普通文本中的 `[RULING]` 引用不触发误判（A5-09） | 注入干扰文本测试 |
| **健壮性** | metadata 解析失败时优雅退化，不崩溃（A5-08） | 故障注入 |
| **判定公式** | 非 user_visible（内部日志格式）→ MINOR | §1.2 |

### 7.4 风险等级：MEDIUM

- **修复风险**：结构化格式设计需谨慎。如果格式与旧版不兼容，可能导致 appeal_tracker 解析大面积失败
- **回归风险**：MEDIUM。appeal_tracker 的 classify_task() 是解析入口，需同时支持新旧格式
- **建议**：采用渐进迁移策略——新 comment 同时保留 `[PREFIX]` 前缀文本（向后兼容）+ 附加结构化 metadata

---

## 8. 集成回归验证

### 8.1 回归范围

P0-15 原始 63 项测试（L1-L6）必须全量通过，且不能因 A1-A5 修复而产生新的 FAIL。

### 8.2 回归测试用例

| TC-ID | 测试内容 | 验证方法 | 预期结果 |
|-------|---------|---------|---------|
| **REG-01** | P0-15 原始 test_integration.py 全量通过 | `cd /workspace/devPPL && python scripts/test_integration.py` | 8/8 PASS（或 ≥8，若新增测试） |
| **REG-02** | P0-15 原始 test_config_loader.py 全量通过 | `cd /workspace/devPPL/scripts && python test_config_loader.py` | ALL OK |
| **REG-03** | 6 脚本 --help 正常输出 | 遍历 dev_reject, appeal, product_rule, downgrade_notify, defer, appeal_tracker | 全部正常输出 usage，无 ImportError |
| **REG-04** | config_loader 新增访问器可正常调用 | `get_state_prefixes()` / `get_roles()` / `get_default_assignee()` | 无 ImportError / KeyError / AttributeError |
| **REG-05** | LEVEL_RANK 修复（若本次一并实施 P15-F2） | `downgrade_notify.py` 的 LEVEL_RANK 从 YAML 派生 | 降级校验行为不变 |
| **REG-06** | P15-F4/F5 修复（参数校验前置，若本次实施） | `appeal.py` / `defer.py` 的校验在 hermes CLI 调用之前 | 无 hermes CLI 时也能给出 "证据过短" / "理由过短" 而非 JSONDecodeError |

### 8.3 成功标准

| 维度 | 标准 |
|------|------|
| **零回归** | REG-01 ~ REG-03 全部 PASS |
| **可扩展** | REG-04 新增访问器正常 |
| **判定公式** | 回归失败 = 功能阻断 → BLOCKER（按 §1.2） |

---

## 9. 测试矩阵总览

| 层级 | 发现 | 测试数 | 优先级分布 | 预计耗时 |
|------|------|:---:|------|:---:|
| A1 | 角色级访问控制 | 10 | 2 P0 / 6 P1 / 2 P2 | < 2s |
| A2 | STATE_PREFIXES 同步 | 10 | 4 P0 / 4 P1 / 2 P2 | < 1s |
| A3 | reinstated 卡片关闭 | 7 | 2 P0 / 3 P1 / 2 P2 | < 1s |
| A4 | assignee 配置化 | 5 | 1 P0 / 3 P1 / 1 P2 | < 0.5s |
| A5 | 结构化日志 | 9 | 1 P0 / 4 P1 / 4 P2 | < 1s |
| REG | 集成回归 | 6 | 6 P0 | < 2s |
| **合计** | | **47** | **16 P0 / 20 P1 / 11 P2** | **< 8s** |

---

## 10. 发布门禁评估

按标准 §10 发布门禁公式：`BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉`

| 门禁项 | 要求 | 目标 | 测量 |
|--------|:---:|:---:|------|
| P0 用例 PASS 率 | — | 100%（16/16） | 自动化测试 |
| P1 用例 PASS 率 | — | ≥ 90%（18/20） | 自动化测试 |
| 回归测试 | 全量通过 | 6/6 PASS | REG-01~REG-06 |
| A1（MAJOR 修复）中引入新问题 | BLOCKER=0 | 无新增 BLOCKER | 每条新发现按 §1.2 判定 |
| A2（MAJOR 修复）中引入新问题 | BLOCKER=0 | 无新增 BLOCKER | 同上 |
| 安全漏洞 | = 0 | 0 | A1 修复涉及鉴权，需特别审查是否有权限提升路径 |

---

## 11. 风险矩阵

| 发现 | 修复风险 | 回归风险 | 测试依赖 | 建议 |
|------|:---:|:---:|------|------|
| A1 | HIGH | LOW | hermes kanban whoami 可用性 | 提供 `--skip-auth` debug flag + mockable 接口 |
| A2 | HIGH | MEDIUM | YAML 一致性 | CI 中增加 A2-10 差异检测 gate |
| A3 | LOW | LOW | hermes kanban comment 对 closed 卡片支持 | 验证边界 |
| A4 | LOW | LOW | YAML 格式正确 | — |
| A5 | MEDIUM | MEDIUM | 旧格式数据存在 | 渐进迁移 + 双格式兼容 |

---

## 附录 A: 修复顺序建议

```
Phase 1: A2 + A5（基础设施层，无用户影响）
  ├── A2: STATE_PREFIXES 从 YAML 自动生成
  └── A5: 结构化日志格式（先定义格式，后更新脚本）

Phase 2: A4 + A3（产品裁定脚本改善）
  ├── A4: assignee 配置化（1 行改动）
  └── A3: reinstated 关闭原始卡片（3 行改动）

Phase 3: A1（权限控制，影响面最大）
  └── 角色鉴权（4 脚本，需要 whoami CLI 配合）
```

## 附录 B: A1 鉴权接口设计建议

```python
# 建议在 kanban_helpers.py 中新增
def verify_role(allowed_roles: list[str]):
    """验证当前用户是否属于允许的角色。失败则 exit(1)。"""
    try:
        result = _run_hermes(["whoami", "--json"], check=False)
        if result.returncode != 0:
            print("[ERROR] 无法获取当前用户身份。hermes kanban whoami 不可用。", file=sys.stderr)
            # 决策：在此处 exit(1) 还是降级放行？
            # 建议：exit(1) + 提示联系管理员，避免鉴权被绕过
            sys.exit(1)
        user = json.loads(result.stdout)
        profile = user.get("profile", "")
    except Exception:
        print("[ERROR] 用户身份解析失败。", file=sys.stderr)
        sys.exit(1)

    roles = get_roles()  # from YAML
    for role in allowed_roles:
        if profile in roles.get(role, []):
            return  # 鉴权通过

    print(f"[ERROR] 鉴权拒绝：当前角色 '{profile}' 不属于 {allowed_roles}", file=sys.stderr)
    sys.exit(1)
```

## 附录 C: A2 STATE_PREFIXES 自动生成建议

```python
def _build_state_prefixes():
    """从 YAML state_machine.transitions 自动生成 STATE_PREFIXES。"""
    sm = get_state_machine()
    to_states = {t["to"] for t in sm["transitions"]}
    # 排除隐式状态（NEW/OPEN — 这些不产生 comment）
    to_states.discard("NEW")
    to_states.discard("OPEN")
    prefixes = []
    for state in sorted(to_states):
        prefixes.append((state, rf'^\[{state}\]'))
    return prefixes
```
