# Memory Middleware（记忆中间层）— QA 测试报告 v3（V2 命令验收）

> 版本：v3.0 | 日期：2026-08-11 | 作者：game-qa（Frank 游戏开发团队 QA）
>
> 被测对象：`/workspace/mem-core` @ HEAD `d29bac9`（含 `f9d7f46` V2 P1 实现）
> 测试方案：`docs/qa/memory-middleware-test-plan-v3.md`（41 用例）
> 执行脚本：`docs/qa/qa_v2_harness.py`（独立实测，未 import 被测方测试文件）
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0（§1.2 判定公式 / §5 示例 / §8 SLA / §10 发布门禁）

---

## 0. 执行摘要

| 维度 | 结果 |
|------|------|
| 用例总数 | 41 |
| **PASS** | **33** |
| **FAIL** | **2**（V2-UPD-05 / V2-UPD-07） |
| **OBS** | **3**（V2-STB-01 / V2-UPD-08 / V2-DEM-04） |
| **NOT_RUN** | **3**（V2-UPD-06 / V2-IDM-02 / V2-NEG-04，全部依赖 `update --apply`） |
| 缺陷发现 | **4 MAJOR**（MEM-V2-01 ~ 04）+ 2 OBS 记录，**无 BLOCKER** |
| B1-B5 门禁 | **B1 ✅ / B2 ✅ / B3 ✅ / B4 ✅ / B5 ✅**（引擎能力全过；CLI 层退出码偏差见 MEM-V2-04） |
| 回归保护 | 111 pytest 全绿（89 MVP + 22 V2）；MVP lint/query/status/context/done --check 冒烟全过 |
| 发布门禁（§10） | **不通过**：MAJOR=4 > 3（BLOCKER=0 但 MAJOR 超限）→ V2 需 FIX 后复测或产品裁定 known issue |

**一句话结论**：V2 四命令的**核心引擎能力全部可用且正确**（drift 检出 / gai-links 补链 / demote 状态变更 / update 增量幂等），
但 CLI 面存在 **2 项 FAIL + 2 项契约偏差**：`update --apply` 静默 no-op、`update --plan --json` 未接线、
`update --plan` 无 source 时静默写入、`drift` 有差异退出码 1≠3。这些是 CLI 接线层缺陷，不是引擎能力缺陷。

---

## 1. 被测对象与环境

- repo：`/workspace/mem-core`，HEAD `d29bac9`（f9d7f46 V2 实现 + revert 后 log 更新）
- 实现面：`update`/`drift`/`gai-links`/`demote` 四命令已从 stub（exit 2）落地为完整实现
- 引擎：`memcore/blast.py`（159 行）/ `drift.py`（81 行）/ `gailinks.py`（117 行）/ `sources/gai.py`（111 行）
- pytest：111 全绿（`python3 -m pytest`，49.8s）；MVP 89 全绿（排除 test_v2 后 35.6s）
- 隔离：每用例独立临时 wiki + 进程级 MEM_* 环境变量（不触真实 kanban.db / GAI 文件）
- 独立实测：harness 自行构造夹具与断言，不引用 mem-core tests/ 下任何代码

### 1.1 契约差异落地情况（D2-F1~F3）

| 差异项 | 方案采用面 | 实现落地面 | 判定 |
|--------|-----------|-----------|:---:|
| D2-F1 `update` 命令面 | 架构 `--plan/--apply` | **两面合并**：`--plan`（候选集）+ 默认增量模式 + `--dry-run` | 部分落地：`--plan` ✅；`--apply` ❌ 静默 no-op（MEM-V2-01） |
| D2-F2 `gai-links --fix` | 架构无 `--fix` | 实现 **有 `--fix`**（任务卡面） | ✅ 超集落地（B3 满足） |
| D2-F3 `demote --status/--reason` | 架构 `--reason` | 实现 `--status`（默认 blocked）+ `--reason` 可选 | OBS：任务卡面落地，`--reason` 降为可选（V2-DEM-04） |

> D2-F1 的 `--apply` 未实现是本次执行的核心阻断项：3 个 NOT_RUN 用例全部由此产生。
> `--apply` 参数被 parser 接受（`nargs="*"`）但 `cmd_update` 从未读取 `args.apply` —— 静默 no-op，比报错更危险。

---

## 2. 逐用例结果（41/41）

### 2.1 update 组（V2-UPD-01~08）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-UPD-01 `--plan` 候选页清单 | **PASS** | `candidates=[('middleware',7),('architecture',2)]` 降序正确，零 LLM |
| V2-UPD-02 不读全 wiki（B1 硬约束） | **PASS** | monkeypatch 统计：**wiki 文件读取数 = 0**（只查 db） |
| V2-UPD-03 空候选 | **PASS** | `candidates=0`，11 terms 提取正常，不崩溃 |
| V2-UPD-04 无 db 降级 | **PASS** | `compute_candidates("/nonexistent.db")` → `[]`，不抛异常 |
| V2-UPD-05 `--apply` 候选页改写 + bump | **FAIL** | `update <src> --apply <page>` → `无变更（1 页未变）` exit 1；`--apply` 被 parser 接受但 **cmd_update 从不读取 args.apply**，静默走增量路径 → **MEM-V2-01** |
| V2-UPD-06 矛盾检测 contradictions | **NOT_RUN** | 依赖 `update --apply` 矛盾检测（未实现，同 MEM-V2-01） |
| V2-UPD-07 `--plan --json`（OC 消费契约） | **FAIL** | `--json` 未定义在 update parser → argparse `unrecognized arguments: --json` exit 2 → **MEM-V2-02** |
| V2-UPD-08 无 source 用法错误 | **OBS** | 裸 `update` = 增量模式（任务卡面 `update [--dry-run]` 落地），非 exit 2；**危险探针：`update --plan` 无 source 在脏 wiki 上写入 db = True + exit 3 → MEM-V2-03** |

### 2.2 drift 组（V2-DRF-01~08）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-DRF-01 干净为空（B5） | **PASS** | 引擎 `[]`，CLI exit 0 `无漂移（三方一致）` |
| V2-DRF-02 kanban 活跃缺页 | **PASS** | 检出 `t_10000001`；CLI exit=1（**契约 exit 3，实现 exit 1 → MEM-V2-04**） |
| V2-DRF-03 GAI 缺页 + MEM-QA-02 回归 | **PASS** | DPL-101/DPL-102 检出，优先级列 P1-01 **不**产生假断链 |
| V2-DRF-04 index 幽灵页 | **PASS** | `index.md 幽灵页: concepts/ghost.md` 检出 |
| V2-DRF-05 只读不修复（铁律 2） | **PASS** | 检出 1 项；文件哈希不变；缺页未自动重建 |
| V2-DRF-06 kanban 缺失/损坏静默降级 | **PASS** | 缺失→[]、损坏→[]，均不抛异常 |
| V2-DRF-07 done/closed/cancelled 排除 | **PASS** | 三类任务均不进入活跃过滤 |
| V2-DRF-08 `--json` 输出 | **PASS** | 干净 count=0 exit 0；脏 count=1 exit 1（**契约 exit 3 → MEM-V2-04**） |

### 2.3 gai-links 组（V2-GAI-01~06）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-GAI-01 零断链 | **PASS** | `missing=[]` exit 0 |
| V2-GAI-02 检出缺失双链 + B3 `--fix` | **PASS** | DPL-102 检出不建页；`--fix` 补 `GAI 关联` 段 exit 0，DPL-104 无页不建 |
| V2-GAI-03 表头变体解析（MEM-QA-02 回归） | **PASS** | golden 4 events：DPL-009/010/INF-011/012 全正确 |
| V2-GAI-04 map_id + mirror_status | **PASS** | 大小写无关直配；BOGUS→None；mirror 只读 |
| V2-GAI-05 缺 GAI 文件降级 | **PASS** | `[]` 不抛异常 |
| V2-GAI-06 done 行状态识别 | **PASS** | ✅ 行→done，无 ✅→active |

### 2.4 demote 组（V2-DEM-01~05）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-DEM-01 正常路径 | **PASS** | status→blocked + 变更记录节 + reason + log.md 全有 |
| V2-DEM-02 双链不断裂（B4 间接） | **PASS** | demote 后 lint **I1-I4 全 PASS 零问题**，`[[P0-19]]` 入链保留 |
| V2-DEM-03 不存在页 exit 1 | **PASS** | `页不存在: NONEXIST-999` exit 1 |
| V2-DEM-04 无 `--reason` 用法错误 | **OBS** | 实现 `--status` 默认 blocked + `--reason` 可选 → exit 0（任务卡面；架构 `--reason` 必填面未落地，D2-F3 差异记录） |
| V2-DEM-05 镜像 L0 状态列（铁律 2） | **PASS** | demote 后 **GAI 文件哈希不变**（memctl 不写 L0） |

### 2.5 幂等组（V2-IDM-01~04）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-IDM-01 update 候选 3 次一致 | **PASS** | `r1==r2==r3`（确定性） |
| V2-IDM-02 update --apply 幂等 | **NOT_RUN** | 依赖 `--apply`（未实现，同 MEM-V2-01） |
| V2-IDM-03 drift 3 次一致 | **PASS** | `d1==d2==d3` |
| V2-IDM-04 drift 只读无副作用 | **PASS** | 5 文件哈希全不变 |

### 2.6 负面注入组（V2-NEG-01~05）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-NEG-01 注入 GAI 断链 | **PASS** | gai-links 检出 DPL-101 缺页 + drift 双路径检出 |
| V2-NEG-02 注入 kanban 差异 | **PASS** | 检出 t_99999999；建页+维护后 drift 空 `[]` |
| V2-NEG-03 注入 index 不一致 | **PASS** | 双向检出：未收录 b.md + 幽灵页 ghost.md |
| V2-NEG-04 注入冲突源 → contradictions | **NOT_RUN** | 依赖 `update --apply` 矛盾检测（未实现，同 MEM-V2-01） |
| V2-NEG-05 注入 db 篡改 → lint I4 | **PASS** | `db 与文件不一致（status）` exit 3，仅此 1 项 |

### 2.7 回归保护组（V2-REG-01~04）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-REG-01 真实 repo lint 零问题 | **PASS** | 6 页 I1-I4 全 PASS exit 0 |
| V2-REG-02 done --check 三态不变 | **PASS** | nonexist=1 / active=3 / done=0（与 MVP VA 基线一致） |
| V2-REG-03 query 仍命中 | **PASS** | trigram「中间层」+ bigram「中间」均命中 |
| V2-REG-04 index --rebuild 幂等 | **PASS** | pages=5/5，lint=0/0（含首页已存在场景） |

### 2.8 stub 组（V2-STB-01）

| 用例 | 结果 | 证据摘要 |
|------|:---:|------|
| V2-STB-01 4 命令 stub exit 2 | **OBS** | stub 契约已被实现取代：`update` exit=1（≠2）→ 契约升级为已实现面（正常演进） |

---

## 3. 验收门禁判定（任务卡 B1-B5）

| 门禁 | 断言 | 结果 | 证据 |
|------|------|:---:|------|
| **B1** | update 后 index 与全量 rebuild 结果一致 | ✅ | V2-UPD-02 读文件=0；V2-REG-04 pages 5/5 lint 0/0；dev test_update_idempotent_b1 一致 |
| **B2** | drift 能检出人工注入的三方差异 | ✅ | V2-NEG-01/02/03 三路注入全检出 |
| **B3** | gai-links 检出缺失双链 + --fix 能补 | ✅ | V2-GAI-02：检出 DPL-102 + `--fix` 补段 exit 0 + 不建无页 ID |
| **B4** | demote 变更后双链不断裂 | ✅ | V2-DEM-02：demote 后 lint 零问题，入链保留 |
| **B5** | 周 drift 报告为空（干净状态） | ✅ | V2-DRF-01 引擎 [] + CLI exit 0 |

> B1-B5 引擎能力**全过**。MEM-V2-04（drift 退出码）影响的是自动化消费方对退出码的依赖，
> 不改变 drift 报告本身正确性，因此不推翻 B2/B5 的能力判定，但需在 FIX 时对齐契约。

---

## 4. 缺陷清单（MEM-V2-01 ~ 06）

### MEM-V2-01 — MAJOR：`update --apply` 静默 no-op（LLM 策展路径未实现）

- **现象**：`memctl update <source> --apply <pages>` 被 parser 接受（`nargs="*"`），但 `cmd_update` 从头到尾**未读取 `args.apply`**，静默落入增量更新路径（detect_changes），输出 `无变更` exit 1。用户以为 LLM 已在候选集内改写页，实际什么都没发生。
- **影响**：V2-UPD-05/06、V2-IDM-02、V2-NEG-04（3 个 NOT_RUN 全部由此产生）。架构 §4.4 `update <source> --apply <pages…>` 契约面未落地。
- **判定公式对照（§1.2）**：用户可感知（apply 后无任何效果）+ 功能阻断（LLM 策展不存在）+ **有 workaround（手动编辑 wiki / 走 update 增量路径）→ MAJOR**。
- **分级依据**：标准 §5 示例 2「功能阻断 + 有 workaround → MAJOR」；方案 V2-UPD-05 原评级 MAJOR 一致。
- **建议处置**：① 实现 `--apply`（LLM 读候选页改写 + bump + log）；② 或至少将 `--apply` 改为「明确报错 exit 2（未实现）」——静默 no-op 是当前最危险形态。

### MEM-V2-02 — MAJOR：`update --plan --json` 未接线（OC 消费契约断裂）

- **现象**：`memctl update <source> --plan --json` → argparse `unrecognized arguments: --json` exit 2。update parser 未定义 `--json`（仅 drift 有），`cmd_update` 内 `hasattr(args,"json")` 保护永远为 False。
- **影响**：架构 §6.2「--json 供 OC 裁定 blast radius」契约断裂；OC 脚本无法结构化消费候选集。
- **判定公式对照（§1.2）**：用户可感知（OC 脚本报错）+ 功能阻断（JSON 消费）+ 有 workaround（人工解析文本输出）→ **MAJOR**。
- **分级依据**：方案 V2-UPD-07 原评级 MAJOR（JSON 结构错位 = OC 消费断裂）一致。
- **建议处置**：update parser 补 `--json` 参数并输出 `{candidates:[{page_id,hit_count,terms}], new_page_suggestions:[]}` 结构。

### MEM-V2-03 — MAJOR：`update --plan` 无 source 时静默执行写入（只读语义被破坏）

- **现象**：脏 wiki（有未入库新页）+ `memctl update --plan`（无 source）→ 条件 `args.plan and args.source` 为 False → 落入增量更新分支 → **实际写 db**（实测 db 字节变化 = True）→ lint exit 3。`--plan` 文档语义是「只读候选清单」，结果静默写库。
- **影响**：用户意图是「看 plan」，系统却执行了写入（机械维护 + 可能 git commit）。误操作成本：db 被改写、可能产生 commit。
- **判定公式对照（§1.2）**：用户可感知（只读请求触发写入）+ 功能阻断（--plan 语义失效）+ 有 workaround（git revert / 检查 status）→ **MAJOR**。
- **分级依据**：比「用法错误 exit 2」（方案原评级 MINOR）更严重：**静默副作用 > 报错**。按 §1.2 取高。
- **建议处置**：`--plan` 无 source 时明确报错 exit 2（`update --plan 需要 <source>`），不允许落入写入分支。

### MEM-V2-04 — MAJOR：`drift` 有差异退出码 = 1，契约 = 3

- **现象**：任务卡「空=无漂移 exit 0；有差异 exit 3」+ 架构 §4.2「3 = 校验失败（drift 发现差异）」+ §4.4「有差异退出码 3」；实现 `cmd_drift` 返回 `EXIT_ERR`=1。dev 自身 test_drift_* 也断言 1（与契约冲突未发现）。
- **影响**：自动化消费方（周 drift cron、CI 门禁）若按 exit 3 判定「有差异」会漏判；按 exit 1 判定则与「一般错误」混淆。
- **判定公式对照（§1.2）**：用户可感知（退出码契约不符）+ 功能阻断（自动化判定失效）+ 有 workaround（解析 stdout/--json）→ **MAJOR**。
- **分级依据**：方案 V2-DRF-02/08 预期「CLI exit 3」；实测 1。契约面冲突需研发裁定（§6 论证流程）。
- **建议处置**：`cmd_drift` 有差异时返回 `EXIT_VALIDATION`=3，或产品裁定更新架构 §4.2/§4.4 为 exit 1。

### MEM-V2-05 — OBS：`demote --reason` 降为可选（D2-F3 差异）

- **现象**：`demote <ID>`（无 `--reason`）→ exit 0，`--status` 默认 blocked + 自动 reason。架构 §4.4 `demote <ID> --reason "…"`（必填）面未落地。
- **影响**：低。任务卡面（`--status blocked|archived`）已落地，`--reason` 可选是超集；语义差异已在 D2-F3 记录。
- **建议处置**：产品/研发裁定 D2-F3 最终面；如需 reason 必填，补参数校验。

### MEM-V2-06 — OBS：V2-STB-01 stub 契约被实现取代

- **现象**：4 命令已实现，不再 exit 2。stub 阶段契约自然作废。
- **建议处置**：无（正常演进，方案 §10 已预期）。

---

## 5. 回归保护结果

| 项 | 结果 |
|----|:---:|
| 全量 pytest（111 = 89 MVP + 22 V2） | ✅ 111 passed（49.8s） |
| MVP 子集 pytest（89） | ✅ 89 passed（35.6s） |
| 真实 repo `memctl lint` | ✅ exit 0，I1-I4 全 PASS（6 页） |
| `memctl query 中间层`（trigram） | ✅ 命中 SCHEMA/r3-architect/r3-engineer |
| `memctl status` | ✅ 页面统计 / db / lint / git 正常 |
| `memctl context` | ✅ 第五源摘要输出 |
| `memctl done t_ffffffff --check` | ✅ exit 1（只读，页不存在） |

> **结论：V2 接线未破坏 MVP 7 命令行为。** V2-REG-01~04 全 PASS。

---

## 6. 分级对照（标准 §1.2 / §8 / §10 落实说明）

| 标准条款 | 本报告落实 |
|---------|-----------|
| §1.2 判定公式 | 4 个 MAJOR 均逐条附「判定公式对照」：用户可感知 + 功能阻断 + 有 workaround → MAJOR；无 BLOCKER（无数据完整性破坏、无崩溃、无铁律违反——drift 只读与 demote 不写 L0 均实测通过） |
| §2 安全漏洞独立判定 | 本地记忆库（C 级内部数据），无 OWASP 暴露面；无安全漏洞 |
| §3 性能退化 | V2-UPD-02 编译期断言（读取文件数=0）满足 B1 硬约束，无性能退化 |
| §5 分级示例 | MEM-V2-01/02/03 对应示例 2「功能阻断 + 有 workaround → MAJOR」；无示例 1 场景 |
| §6 论证流程 | **本报告为 QA 发现层输出**：4 MAJOR + 2 OBS 已编号（MEM-V2-XX），建议处置附后；研发评估 → 通过/驳回/暂缓流程待 OC 建 FIX 卡后走标准 §6 |
| §8 SLA | 本报告交付时间：发现即报告（未跨 SLA 窗口）；MEM-V2-01~04 若转 FIX 卡，SLA 从 FIX 卡创建起算 |
| §9 QA SLA | 41 用例一次性执行完成（Phase 1 引擎 25 例 + Phase 2 CLI 11 例大部分可执行；Phase 3 demote 5 例因 dev 已实现 demote 引擎而全部可执行） |
| §10 发布门禁 | **BLOCKER=0 ✅；MAJOR=4 > 3 ❌；安全漏洞=0 ✅；无未裁定申诉 ✅ → V2 发布门禁不通过**（需 FIX 或产品裁定 known issue） |
| §11 产品红线 | 未涉及本体文件替换；V2-DEM-05 实测 memctl 不写 L0（GAI 哈希不变）——铁律 2 未违反 |

---

## 7. 建议处置（供 OC 建 FIX 卡参考）

| # | 缺陷 | 建议 FIX 卡标题 | assignee | 优先级 |
|---|------|----------------|----------|:---:|
| 1 | MEM-V2-01 | FIX MEM-V2-01 (MAJOR): update --apply 静默 no-op — cmd_update 未读取 args.apply，LLM 策展路径未实现 | dev | P1 |
| 2 | MEM-V2-02 | FIX MEM-V2-02 (MAJOR): update --plan --json 未接线 — parser 缺 --json，OC 消费契约断裂 | dev | P1 |
| 3 | MEM-V2-03 | FIX MEM-V2-03 (MAJOR): update --plan 无 source 静默执行写入 — 只读语义被破坏，应 exit 2 | dev | P1 |
| 4 | MEM-V2-04 | FIX MEM-V2-04 (MAJOR): drift 有差异退出码 1≠3 — 契约对齐（改 cmd_drift 或修订架构 §4.2） | dev | P2 |
| 5 | MEM-V2-05 | （OBS）D2-F3 最终裁定：demote --reason 是否必填 | 产品/架构 | P3 |
| 6 | MEM-V2-06 | （OBS）V2-STB-01 stub 契约作废 — 方案 §10 更新 | 文档 | P3 |

> 依据团队建卡协议（SOUL.md §6），QA 不直接建研发 FIX 卡；以上建议处置供 OC 创建 FIX 卡时引用 MEM-V2-XX 编号。
> FIX 完成后需 QA 复测回归（V2-UPD-05/07 重跑 + MEM-V2-03 探针 + drift 退出码断言）。

---

## 8. 一句话结论

V2 四命令**引擎能力全绿**（B1-B5 全过、铁律 2 未违反、111 pytest 全绿），但 **CLI 接线层有 4 个 MAJOR**：
`update --apply` 静默 no-op、`update --plan --json` 未接线、`update --plan` 无 source 静默写入、`drift` 有差异退出码 1≠3；
**V2 发布门禁不通过（MAJOR=4 > 3）**，需 FIX 后复测或产品裁定 known issue；当前状态**不进入 VA 验证**，建议 OC 按 §7 建 4 张 FIX 卡。
