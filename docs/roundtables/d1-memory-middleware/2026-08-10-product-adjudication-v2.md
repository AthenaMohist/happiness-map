# D1 评审 v2 产品裁定卷 — QA 测试方案 v2 + OBS-01

> 发言人：许清楚（产品负责人） | 日期：2026-08-10 | 版本：v1.0
> 类型：D1 评审 v2 第一棒（product 裁定）—— 对 QA 测试方案 v2（docs/qa/memory-middleware-test-plan-v2.md，986 行 56 用例）的验收覆盖、优先级、红线严格度、新增用例必要性逐项裁定 + OBS-01 处置裁定
> 输入：QA 方案 v2（t_e2c58e2f）+ PRD v1.1（验收权威）+ 架构定稿 v1.0（commit 78fc583 + 79eac5f）+ 标准 docs/standards/qa-finding-classification.md v1.0 + OBS-01 研发评估卷（t_a4c55e68 comment #415）+ OBS-01 修复（t_802009a1 → mem-core d440793）
> 实测复核（本裁定独立执行，非转述）：mem-core HEAD d440793 上复现 add task 骨架 → lint 0；手写 active 页缺 est_hours → 仍 I4 报错（豁免未泄漏）；done 自动建页 → lint 0；pytest 54 全绿；L0 kanban.db tasks 表实测无 est_hours 列（方案 a 数据不可得的实证）

---

## 0. 裁定总览

| # | 问题 | 级别 | 产品立场 | 一句话落地 |
|---|------|:---:|------|-----------|
| OBS-01 | add task 骨架缺 est_hours → lint I4/I2 恒红死区 | **MAJOR 确认** | 采纳方案 c（机械中间态豁免 + 契约修正），否决方案 a | 已由 mem-core d440793 修复并实测验证：骨架 status=draft + mechanism 标记 + lint 豁免 I4-est_hours/I2-出链数；active/手工页保持强制；QA 方案需刷新基线并翻转 BE-18 |
| 覆盖 | 56 用例是否覆盖产品验收关注点（北极星） | ✅ 覆盖 | 维持方案 | 北极星机械使能面全覆盖（纠正→wiki→带出），C1-C4 按观测协议就绪；反指标正确排除 |
| 优先级 | MVP 21 用例先行 | ✅ 合理 | 维持方案 | MVP 门禁 = A1-A9 全绿 + BLOCKER=0 AND MAJOR≤3，执行顺序依赖正确 |
| 红线 | BE-10 是否足够严格 | ✅ 足够 + 1 项加强 | 维持方案 + 增强 | 哈希 + 写路径扫描 + 签字状态机三重复核已达红线强度；建议源码扫描扩到「任何逃逸 MEM_WIKI_PATH 的写模式」+ 全 profile 本体哈希 |
| 新增 | v2 相比 v1 新增 7 用例 | ✅ 全部必要 | 维持方案 | 逐项核对均有真实缺口，零 scope creep |

---

## 1. OBS-01 裁定 — MAJOR 确认，处置采纳方案 c（机械中间态豁免 + 契约修正）

### 1.1 分级裁定：MAJOR 确认（与 QA 候选、研发评估一致）

对照标准 §1.2 五步公式（本裁定独立复跑，非跟票）：

| 步骤 | 判定 | 证据 |
|------|------|------|
| 用户可感知 | **是** | 每次 `add task` / `done` 自动建页后，仓库 lint 门禁恒红，HEAD 质量信号失真——这是编译质量度量（PRD §1.2）的机制载体失效 |
| 功能阻断 | **是** | 违反 PRD P0-4「lint 零问题为一切提交前置」；A2（lint 门禁）与 A5（done 写页）出现不可同时满足的死区 |
| 无 workaround | **否** | LLM 策展手动补 est_hours/出链是设计内流程（R6 只求非空）→ 有 workaround |
| 结论 | **MAJOR** | 有 workaround 从 BLOCKER 降 MAJOR；非 MINOR（确定性路径、每次 add/done 必触发、门禁系统完整性受损） |

另按标准 §2 独立核查：本缺陷不涉及安全漏洞/权限边界（中间层仍在 mem-core 仓库内自洽），无独立升级理由。

### 1.2 处置裁定：方案 c，否决方案 a

**否决 (a) add task 预填 est_hours + 出链** —— 数据上不可行，逻辑上违背知识编译层边界：
- L0 kanban.db tasks 表实测**无 est_hours 列**，MVP 无 update/策展命令 → est_hours 在机械层结构性不可得；
- 预填默认值 = 伪造事实（估算 0 小时是谎言，不是数据），违反 wiki 保真 / 「编译器不造假」边界；
- 预填伪出链 = 语义图噪声，污染 I1/I2 的判定基座。

**采纳 (b) 扩展为方案 c（机械中间态豁免 + 契约修正）** —— 产品视角核心原则：**lint 门禁管「编译完成态」，不管「机械中间态」**：
- 骨架（status=draft，mechanism=memctl add）与机械 done 页（mechanism=memctl done）是待策展中间态 → 豁免 I4-est_hours 必填 + I2 出链数；
- **豁免范围必须收窄**（这是产品对方案 b 的关键补强，防止门禁失守）：豁免仅当 `status==draft` OR `mechanism ∈ {memctl add, memctl done}`；active/手工页 est_hours 必填 + I2≥2 出链**保持强制**；priority 必填、孤儿检查、I1/I3/I4 其余结构校验全部保留。

### 1.3 修复验收（本裁定独立实测，mem-core d440793）

| 断言 | 实测结果 | 判定 |
|------|---------|:---:|
| `memctl add task t_x --priority P1` → 骨架 status=draft + mechanism=memctl add | exit 0，frontmatter 含 draft/mechanism | ✅ |
| add 后 `memctl lint` | exit 0，I1-I4 全 PASS（零问题） | ✅ |
| 手写 active 页缺 est_hours（负样本） | exit 3，I4 报 est_hours（豁免未泄漏） | ✅ |
| `memctl done` 自动建页（A5/close.sh S3 主路径） | exit 0，lint 0（mechanism=memctl done 豁免生效） | ✅ |
| pytest 全量 | 54 pass | ✅ |

### 1.4 SLA 对照

OBS-01 走标准 §6 论证流程：QA 预执行发现（t_e2c58e2f）→ 研发评估 17 分钟确认 MAJOR + 方案（t_a4c55e68 #415）→ 修复落地 13 分钟（t_802009a1 → d440793）。全程远优于 §8 SLA（响应 4h / 定位 8h / 方案 24h）。**修复后 OBS-01 为「已确认 MAJOR + 已修复」状态，不计入发布门禁 MAJOR≤3 的开放计数（当前开放 MAJOR = 0）。**

### 1.5 对 QA 方案 v2 的要求（QA 需刷新，非阻断项）

方案 v2 基线写的是 27673b9（修复前），D1 评审时修复已落地，QA 应在正式执行前刷新：
1. §0/§1 实测基线 commit 27673b9 → **d440793**（51 pytest → 54）；
2. **BE-18 从「观测确认」翻转为「回归断言」**：预期 add task → lint exit 0，可加 done 自动建页 → lint 0（负样本 active 无 est_hours 仍报 I4）；
3. TC-13 注意行（§3）引用的「实测发现缺 est_hours」改为已修复说明，执行时不再记录观测；
4. §9 OBS-01 处置状态 = 已修复（d440793），从开放发现移入回归覆盖；
5. §11 SLA 表补 OBS-01 关闭记录。

---

## 2. 评审点 1：56 用例覆盖产品验收关注点（北极星：Frank 重复教归零）— ✅ 覆盖

产品视角：北极星是**长期结果指标**，不可能在 11.5h 内机械断言（「Frank 不再重复教」无法自动化）；方案的处理方式正确——**机械使能面全部机器断言 + 北极星本身按观测协议**：

| 北极星分解 | 机械使能面 | 覆盖用例 | 判定 |
|-----------|-----------|---------|:---:|
| 纠正不再遗忘（P1） | 纠正事件落 wiki + 跨会话可检索 | TS-02（纠正闭环）、TC-08/09（trigram/bigram 检索）、TC-17/18（boot_context 带出） | ✅ |
| 决策 30s 追溯（P2/C2） | 四段决策页 + 检索 | TC-08、TC-20（3 页质量）、C2 计时模板就绪 | ✅ |
| 会话上下文断点（P4/C3） | boot_context 第五源 | TC-16/17/18、BE-11 截断 | ✅ |
| 待办无细节（P5） | GAI 双链 → 详情页 | B2/B3（TC-23/24）、BE-02 | ✅ |
| 单副本（C1） | profile 标签隔离 | BE-04 | ✅ |
| 红线（§7.2） | 本体不被改 | BE-10 | ✅ |
| 反指标（§5.4 不看页数/同步率/覆盖率） | 方案 §8.3 统计不含反指标断言 | 合规 | ✅ |

**产品结论：PRD §5 全量断言被 56 用例覆盖，无遗漏，MVP 门禁条件成立。**

---

## 3. 评审点 2：优先级（MVP 21 用例先行）— ✅ 合理

- **MVP 门禁 = A1-A9（21 例）当前全部可执行**；V2 10 例标 `[V2-pending]` 且引擎层（blast/drift/gai adapter）可先行验证逻辑——这正好匹配 Frank 裁定「引擎本体优先」；
- 执行顺序依赖正确：Round 0 环境预检 → Round 1 引擎单元 → Round 2 检索/CLI → Round 3 集成（含红线 BE-10 + A1）→ Round 4 端到端 → Round 5 内容验收 → Round 6 北极星观测初始化；
- 工时合理：MVP 11.5h / 46 用例 ≈ 15 分钟/例（golden-file 驱动可行），V2 3h / 10 例；
- 一条产品建议（不改变结论）：OBS-01 修复后，BE-18 已排在 Round 1，自动升级为回归断言，无额外时间成本。

---

## 4. 评审点 3：BE-10 红线严格度 — ✅ 足够严格 + 1 项加强建议

**BE-10 已达到红线强度**：三重复核 = (1) 行为层：本体文件哈希前后对比（memctl 全命令序列执行后不变）；(2) 静态层：源码 grep 写路径扫描（memcore/ bin/ 无本体写操作）；(3) 治理层：Frank 签字状态机（替换提案必须四段式决策页 + 迁移脚本 + 回退方案 + decision 页 status=approved；**未签字 = 不替换**）。分级 BLOCKER + §2 权限边界独立判定 ≥MAJOR 取最高级——正确。

**加强建议（QA 执行时采纳，非阻断）**：
1. 源码扫描从「字面量 grep」扩为「**任何写模式逃逸 MEM_WIKI_PATH**」：`open(...,'w'/'a')`、`os.replace`、`shutil.copy`、`Path.write_text` 等对非 wiki 路径的写操作——堵住「变量拼路径间接写」的洞（OBS-03 已证明本环境路径变量混乱真实存在）；
2. 哈希对象从「~/.hermes/ SOUL.md（如存在）+ 任一 SKILL.md」扩为**全部 profile 的本体文件**（`/root/.hermes/profiles/*/SOUL.md`、memory 文件、devPPL `.hermes.md`、mem-core SKILL.md）——本体文件全集一次性哈希成本极低，覆盖更稳。

---

## 5. 评审点 4：v2 相比 v1 新增 7 用例 — ✅ 全部必要，零 scope creep

| 新增用例 | 对应缺口 | 必要性判定 |
|---------|---------|:---:|
| TC-06（status 输出断言） | MVP 7 命令中 status 无任何专用断言（Architect 缺口 2） | ✅ 命令面完整性 |
| TC-14 拆出（done --check dry-run 1/3/0） | S3a 验证步骤语义独立，与真实执行混测有歧义 | ✅ 消除断言歧义 |
| BC-05（demote V2） | V2 命令无覆盖（Architect 缺口 1） | ✅ 整命令需覆盖 |
| BE-16（退出码全表 0/1/2/3） | close.sh/boot_context 脚本消费契约；D1-F2 定稿后需全表验证 | ✅ 契约可消费性 |
| BE-17（done fail-open） | 工程承诺 R10（close 不挂死），Architect 缺口 3 | ✅ 主路径韧性 |
| BE-18（骨架 lint 观测） | OBS-01 发现的正式记录载体 | ✅ 论证流程要求（现已翻转为回归） |
| BE-10 强化（哈希+扫描+签字状态机） | Frank 硬红线 §7.2 的执行保障 | ✅ 红线必守 |

**结论：7 项新增全部对应真实缺口（命令面/V2 覆盖/退出码契约/fail-open 承诺/OBS-01 发现/dry-run 语义/红线执行），无一为「锦上添花」。**

---

## 6. 对其他角色影响

| 角色 | 影响 |
|------|------|
| **QA** | 按 §1.5 刷新方案 v2 基线（d440793）+ BE-18 翻转 + §9 OBS-01 关闭；BE-10 执行时采纳 §4 两条加强；其余用例定义、分级、路径划分维持不变 |
| **Architect** | 架构 §4.3 已同步 79eac5f（draft + mechanism + 豁免），无需再改；若认同 §4 加强建议，可在 SCHEMA 红线章节补一句「lint 写路径扫描按写模式逃逸判定」 |
| **Engineer** | OBS-01 修复已落地 d440793 且验收通过，无需再动；BE-10 若发现扫描缺口按缺陷流程提交 |
| **Orchestrator** | 本裁定完成后，D1 评审 v2 第二棒（Architect t_be227e33）与第三棒（Engineer t_433546b7）可启动；两棒依赖本卷 OBS-01 结论 |

---

## 7. 一句话结论

**QA 测试方案 v2 产品裁定通过**：56 用例完整覆盖 PRD §5（北极星机械使能面全机器断言 + C1-C4 观测协议就绪）、优先级 MVP 先行合理、BE-10 红线已达强度（另加写模式逃逸扫描 + 全 profile 本体哈希两条增强）、新增 7 用例全部必要；**OBS-01 裁定 MAJOR 确认 + 处置采纳方案 c（机械中间态豁免 + 契约修正）**，修复已在 mem-core d440793 落地并经本裁定独立实测验收（add/done 建页 lint 0、手写 active 页仍强制、pytest 54 绿），开放 MAJOR 计数 = 0，MVP 发布门禁（A1-A9 全绿 + BLOCKER=0 AND MAJOR≤3）成立；QA 正式执行前按 §1.5 刷新基线即可。

> 产品发言完毕。下一步：Architect 第二棒 → Engineer 第三棒 → QA 按本卷 §1.5 刷新方案 → Round 0 执行。
