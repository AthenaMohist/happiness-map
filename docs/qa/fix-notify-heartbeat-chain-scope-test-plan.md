# FIX notify heartbeat 统计范围限定到当前开发链 — QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_d3f1e173 [DEV-QA-D1] FIX notify heartbeat 统计范围限定到当前开发链（不统计全局历史）
> 被测提交：ddc64e2（dev t_e72e6cc1，merge 6a05fbd）+ 1e12112 + 5afb7e6（split('-',2) 修复）
> 部署基线：main @ 7889bc6（含 F-9 自动关闭 + T19，本 worktree 落后 1 commit）
> 上游文档：
> - PRD：`docs/prd/fix-notify-heartbeat-chain-scope-prd.md`（v1.0，commit 6f7abcb，t_f86c3398）
> - 架构：`docs/arch-fix-notify-heartbeat-chain-scope.md`（v1.0，commit 2c57d81，t_0c41ef06）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> - 基线测试：`scripts/test_notify_check.py`（T1-T19，56 断言）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 基线复跑 `scripts/test_notify_check.py`（main @ 7889bc6） | ✅ 56/56 PASS（T1-T19，QA 独立复跑 2026-08-11） |
| 基线复跑（本 worktree @ 5afb7e6） | ✅ 50/50 PASS（无 T19/F-9，见 §4.4） |
| 真实 board dry-run（生产库副本） | ✅ `[AP 17:54] 活跃2 跑2 堵0 今完13` — 与 board 实况完全一致（2 张 qa-d1 running + 13 张 done 今日） |
| 边界探测（QA 独立 5 探针） | ✅ 11/11 PASS（blocked 链卡/连字符步骤/legacy 逃生阀/annex 冷却） |
| 模拟场景（真实库副本 3 变体） | ⚠️ sim1 暴露 **MAJOR × 1**（QA-D1-01：混合信号源盲区） |
| **D1 发现** | **MAJOR × 1**（QA-D1-01）+ **MINOR × 2**（QA-D1-02/03） |

**结论**：被测 FIX 的核心路径正确——真实 board dry-run 数字与板面一致（活跃2 跑2 堵0 今完13），连字符步骤（qa-d1/va-claim）解析正确，legacy 自动回退/逃生阀/归档退出统计全部生效，存量 T1-T18 无回归。但 D1 测试设计阶段发现 **1 个 MAJOR 混合信号源盲区**（链卡 done-今日 + pipeline 活跃时，heartbeat 报 活跃0 跑0 堵0 而 pipeline 实际在处理任务——与 arch ADR-2 自身声明的「避免活跃0 但 ACTIVE=true」矛盾，实时板 t_620b6ccf 当前即处于该状态）。修复（FIX 卡）未落地，需在测试执行前/执行中关闭，新增用例 T20/T21 作为回归门禁。

---

## 1. 测试范围概览

```
被测模块                           PRD AC 覆盖       arch ADR        新增/扩展
──────────────────────────────────────────────────────────────────────────────
scripts/notify_check.py (887行)    AC-1~AC-8          ADR-1~7         +read_dev_chain_cards/
                                                                    compute_chain_counts/
                                                                    chain_relevant/_to_epoch
config/notify.json                 F-5               §4.5            +heartbeat.stats_scope
scripts/test_notify_check.py       F-6               §5.2            fixture 升级 + T11-T19
pipeline/cmd_chain.py              —                —               零改动（对照确认）
scripts/cmd_channel.sh             —                —               零改动（对照确认）
pipeline/discover.py               —                —               零改动（R2 四道闸不回退）
```

**零改动确认（回归范围）**：autopilot.sh / cmd_channel.sh / discover.py / cmd_chain.py / constants.py / workspace_check.sh / stuck_check.sh —— 本 FIX 不触碰，需回归验证不破坏。

### 1.1 验收标准映射（PRD §5.2）

| AC | 验收要点 | 测试用例 | 状态 |
|----|---------|---------|:---:|
| AC-1 | 在途链卡 → ACTIVE + 数字正确 | T11 | ✅ 已有 |
| AC-2 | 多棒在途（prd done 今日 + arch running + dev ready） | T12 | ✅ 已有 |
| AC-3 | 全局历史不统计（非 dev-* 卡不计入今完N） | T12/T14 | ✅ 已有 |
| AC-4 | 归档退出统计；全归档 → IDLE | T13 | ✅ 已有 |
| AC-5 | 完成自动停（链全 done 非今日 → IDLE 静默 + 空闲边界） | T17 | ✅ 已有 |
| AC-6 | 纯 legacy 不回归（自动回退 + stats_scope=legacy） | T14/T15 | ✅ 已有 |
| AC-7 | fail-open（缺库/缺列不崩） | T5-2/T18 | ✅ 已有 |
| AC-8 | 格式不变（≤80 字，[AP HH:MM] 前缀） | T7-2/T7-3 | ✅ 已有 |
| （补） | 连字符步骤（va-claim/qa-d1）不被跳过 | **T22（新增）** | ⚠️ 缺测 |
| （补） | blocked 链卡 → 堵N + ACTIVE | **T23（新增）** | ⚠️ 缺测 |
| （补） | 链卡 done-今日 + pipeline 活跃 → 信号不失真 | **T20/T21（新增）** | 🔴 QA-D1-01 |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 board）：

| 项 | 配置 |
|---|---|
| 隔离 kanban.db | 复制真实 schema → 受控行（fixture `Fixture.seed_kanban_dev_chain`） |
| 隔离 pipeline_state.db | `Fixture.seed_pipeline`（tempfile） |
| 隔离 notify_state.db | `Fixture` 自动建（tempfile） |
| 真实库副本验证 | `/tmp/qa-d1-heartbeat/`：cp 生产三库 → dry-run 不写生产 |
| 执行命令 | `python3 scripts/test_notify_check.py`（56 断言基线）+ 本方案新增用例 |

**执行前置**：
1. `python3 -m py_compile scripts/notify_check.py scripts/test_notify_check.py`
2. 基线复跑 56 断言全绿后，再执行新增用例
3. 真实库副本 dry-run 核对 board 数字（§4.3）

---

## 3. ⚠️ D1 前置发现（测试设计阶段）

### QA-D1-01（MAJOR）：混合信号源盲区 — 链卡 done-今日 + pipeline 活跃 → heartbeat 报 活跃0 跑0 堵0，实际 pipeline 正在处理任务

**位置**：`scripts/notify_check.py` — `chain_relevant()`（L411-424）+ `compute_counts()`（L454-465）+ `is_active()`（L369-382）

**缺陷描述**：
`chain_relevant()` 的「今日完成卡」分支（ADR-2 第二项）只检查链卡，不看 pipeline：
```
chain_relevant = 在途链卡(ready/running/blocked) ∨ done 且 completed_at ≥ 本地今日零点
```
当链卡**全部 done-今日**（无在途）且 pipeline **有活跃步骤**时：
- `chain_relevant=True` → 数字来自链卡 → `活跃0 跑0 堵0 今完N`
- `is_active()` 仍看 pipeline → 有 pending/running/blocked → **ACTIVE=True** → heartbeat 照推
- 结果：heartbeat 推送 `活跃0 跑0 堵0` 而 pipeline 实际在处理任务——**数字与真实工作完全脱节**

这与 arch ADR-2 rationale #1 自身声明直接矛盾：「若不回退，纯 legacy 活跃时 heartbeat 会报 活跃0 但 ACTIVE=true——**比现在更误导**」。ADR-2 只处理了 chain_relevant=False（无链卡/链 done 非今日）的回退，遗漏了 done-今日 + pipeline 活跃的组合。

**实机复现（不可辩驳的证据）**：

| 场景 | 构造 | 输出 |
|------|------|------|
| 真实 board 当前状态 | 2 张 qa-d1 running + pipeline t_620b6ccf dev running | `[AP 17:54] 活跃2 跑2 堵0 今完13`（堵0 掩盖 t_620b6ccf kanban blocked） |
| **sim1（即将到来的状态）** | 2 张 qa-d1 置 done-今日 + pipeline t_620b6ccf dev running | `[AP 18:01] 活跃0 跑0 堵0 今完15` ⚠️ |
| 对照 sim2（正确回退） | 全部链卡 archived + pipeline t_620b6ccf running | `[AP 18:03] 活跃1 跑1 堵0 今完2` ✅ legacy 回退正常 |

sim1 是**必然发生**的状态：本任务 t_d3f1e173 与 t_5f9f1633（MEM-001 qa-d1）一旦 done，board 即进入「链卡全 done-今日 + t_620b6ccf 在 pipeline 处理中」→ heartbeat 从此报 活跃0 直到 t_620b6ccf 结束或午夜，Frank 无法区分「没活干」和「系统死了/堵了」。

**分级判定（对照标准 §1.2 五步公式）**：
- ① 存在缺陷 ✅（sim1 真实库副本复现：活跃0 而 pipeline running）
- ② 用户可感知 ✅（Frank 依赖 heartbeat 判断 autopilot 状态，数字与真实工作脱节 = 信号失真）
- ③ 非安全漏洞 ✅
- ④ 影响核心功能 ✅（heartbeat 是本 FIX 的核心交付物；信号失真正是 PRD §1.2 要修的缺陷类别）
- ⑤ 分级：用户可感知 AND 功能阻断（数字失真，pipeline 活跃被完全掩盖）AND 有 workaround（查 board / autopilot.log 可发现）→ **MAJOR**（非 BLOCKER，有 workaround）

**SLA 对照（标准 §8）**：MAJOR 1 工作日响应 + 2 工作日定位 + 当前版本窗口内方案。QA 已实机复现（sim1）+ 证据链完整，建议研发优先评估。

**建议修复方向（供研发评估，QA 不代修）**：
- 方案 A（推荐）：`chain_relevant()` 的 done-今日分支增加 pipeline 活跃检查——「链 done-今日 且 pipeline 无 pending/running/blocked」才保持链卡口径；pipeline 有活跃步骤时回退 legacy（活跃N/跑N/堵N 用 pipeline，今完N 保留链卡或合并）。
- 方案 B：`compute_counts()` 在 chain_relevant=True 但链卡无在途时，将 pipeline 活跃步骤数并入 活跃N/跑N/堵N（今完N 仍只算链卡）。
- 无论哪种：**新增回归测试 T20/T21（见 §4.3）锁死该场景**。

**影响面评估**：当前真实板 t_620b6ccf（[FIX] 卡，kanban blocked + pipeline dev running）即处于盲区边缘——2 张 qa-d1 完成后 heartbeat 立即失真。修复不改变 FIX 主路径（链卡在途时数字正确），仅补齐混合源边界。

---

### QA-D1-02（MINOR）：连字符步骤（va-claim/qa-d1）解析修复（5afb7e6）无测试覆盖

**位置**：`scripts/test_notify_check.py` T11-T19 全部使用 `prd/arch/dev` 单段步骤名；**没有任何用例 seed `qa-d1`/`va-claim` 等连字符步骤**。

5afb7e6 修复的正是「split('-') 导致 va-claim/qa-d1 被静默跳过」的缺陷（真实板 qa-d1 从漏统计 → 活跃1 跑1），但该修复**没有对应的回归测试**。QA 独立探针 P2 验证当前代码正确（qa-d1/va-claim 解析为完整步骤名），但修复未锁死，后续重构可能回退。

**分级判定**：用户可感知？修复本身已在真实板生效（当前 heartbeat 活跃2 含 qa-d1 卡），缺陷是**测试缺口**而非产品缺陷 → MINOR（不阻塞发版，但应在本次 FIX 中补测）。新增用例 **T22**（§4.3）。

---

### QA-D1-03（MINOR）：PRD/架构文档未合入 main，下游引用路径断裂

**位置**：任务 body 引用 `docs/prd/fix-notify-heartbeat-chain-scope-prd.md`，但该文件仅存在于 t_f86c3398 链分支（commit 6f7abcb），**main 上不存在**（`git ls-tree main docs/prd/` 确认）。arch 文档同理（2c57d81 仅存于 t_0c41ef06 分支）。merge 6a05fbd 只合入了代码三件套，文档未合入。

**影响**：下游 QA-EXEC / VA 读取任务卡引用 spec.md 路径时文件不存在；与上一链（cmd_chain 补全）同模式——两链的 PRD/arch 文档均未上 main。属文档交付缺口，不阻塞功能验证（QA 已从 commit 内容核对）。

**分级判定**：用户可感知（下游引用断裂）但无功能影响 → **MINOR**（建议 merge 时文档一并合入 main，或任务卡引用改为 commit 链接）。

---

## 4. 测试用例设计

### 4.1 基线 56 断言（研发已有，QA 独立复跑确认）——按需求域归类

| 需求域 | 用例 | 断言数 | 说明 |
|--------|------|:---:|------|
| token 缓存 | T1（3 断言） | 3 | 验收 1：token 只换 1 次 |
| work-gated heartbeat | T2（5 断言）+ T19（6 断言） | 11 | 验收 2 + F-9 自动关闭/唤醒 |
| 事件推断/去重 | T3（5 断言） | 5 | 验收 3：30min 冷却 |
| 三路经独立 | T4（3 断言） | 3 | 验收 4：exception 无视 silent_window |
| fail-open | T5（4 断言） | 4 | 验收 5：缺库/无凭据/API 挂 |
| 7 天清理 | T6（2 断言） | 2 | 验收 6 |
| [CMD] ACTIVE + 格式 | T7（3 断言） | 3 | ≤80 字 |
| dry-run 不污染 | T8（2 断言） | 2 | |
| B1-F1 回归 | T9/T10（各 3 断言） | 6 | __boundary__ 垃圾文案过滤 |
| **FIX 链卡口径** | T11-T18（8 用例） | 17 | F-1~F-8 + ADR-1~7 |

### 4.2 静态核对清单（QA 独立代码核对）

| # | 核对项 | 依据 | 结果 |
|---|--------|------|:---:|
| S1 | read_dev_chain_cards SQL 双过滤（dev-% + [DEV-% + 非 archived） | notify_check.py L245-289 | ✅ |
| S2 | split('-', 2) 支持连字符步骤，与 cmd_chain._parse_dev_key 对齐 | notify_check.py L275 | ✅（P2 实测） |
| S3 | fail-open（缺库/缺表/缺列 → []） | notify_check.py L258-287 | ✅ |
| S4 | compute_chain_counts 四维度口径与 PRD F-2 一致 | L385-408 | ✅ |
| S5 | chain_relevant 自动回退逻辑与 ADR-2 一致 | L411-424 | ⚠️ **done-今日 + pipeline 活跃盲区（QA-D1-01）** |
| S6 | is_active 三来源（pipeline/[CMD]/链卡）scope 分支 | L369-382 | ✅ |
| S7 | _to_epoch 归一化（int/ISO Z/SQLite 格式） | L105-127 | ✅ |
| S8 | 链卡事件只进 heartbeat_annex 不进 milestone | run_tick L690-694 | ✅（T16 断言） |
| S9 | cleanup 保留集 = pipeline ∪ 非 archived 链卡 | L634-656 | ✅ |
| S10 | stats_scope 缺省 chain、显式 legacy 生效 | config/notify.json + run_tick L699 | ✅ |
| S11 | read_cmd_cards 收窄为 [CMD] 专用 | L223-242 | ✅ |
| S12 | 主 repo 与 worktree 差异仅 F-9/t19（7889bc6） | diff | ⚠️ 见 §4.4 |

### 4.3 新增用例（本方案扩展，测试执行时并入 test_notify_check.py）

| # | 场景 | 前置 | 断言 | 对应缺陷/ADR |
|---|------|------|------|-------------|
| **T20** | **混合源盲区回归（关键）**：链卡全 done-今日 + pipeline 有 running 步骤 → heartbeat 数字必须反映 pipeline（修复后） | seed 链卡 1 张 done(completed_at=今日) + pipeline 1 条 running | T20a: ACTIVE 仍成立（推 heartbeat）；T20b: 修复后 活跃N ≥ 1（不再 活跃0 跑0 堵0） | **QA-D1-01** |
| **T21** | 混合源：链卡无在途 + pipeline blocked → 堵N 合并（修复后） | seed 链卡全 done-今日 + pipeline 1 条 blocked | T21a: ACTIVE=true；T21b: 修复后 堵N ≥ 1 | **QA-D1-01** |
| T22 | 连字符步骤回归：qa-d1 + va-claim 两张链卡 → 活跃N 正确统计 | seed_kanban_dev_chain step='qa-d1'/'va-claim' | T22a: read_dev_chain_cards 返回完整步骤名；T22b: heartbeat 活跃2 跑1 堵0 今完0 | **QA-D1-02**（5afb7e6 锁死） |
| T23 | blocked 链卡 → 堵N + ACTIVE | seed 链卡 1 张 blocked | T23a: ACTIVE=true（推 heartbeat）；T23b: 数字=活跃0 跑0 堵1 今完0 | 补 AC-1 缺测 |
| T24 | 归档链卡 snapshot 立即清理（ADR-7 实测） | seed 链卡 running → 跑 1 tick → 置 archived → 再 tick | T24a: pipeline_snapshot 无该 task_id 残留 | ADR-7 |
| T25 | 真实 board 数字核对（只读） | 生产库副本 dry-run | T25a: 活跃N/跑N/堵N/今完N 与 kanban tasks 实况逐项一致 | 环境核对 |

**门禁判定**：T20/T21 在修复前必然 FAIL（盲区存在）——作为回归用例必须在 FIX 卡交付后通过；T22-T25 当前基线可直接执行验证（QA 独立探针 P1/P2 已先行验证通过）。

### 4.4 ⚠️ 部署基线差异（本 worktree vs main）

| 项 | 本 worktree（wt/t_d3f1e173） | main（部署，crontab 实跑） |
|---|---|---|
| HEAD | 5afb7e6 | 7889bc6 |
| 测试结果 | 50 PASS / 0 FAIL | 56 PASS / 0 FAIL |
| 差异 | 无 F-9/t19 | +F-9 活跃0持续3tick自动关闭 + T19 六断言（7889bc6） |

**处置**：QA 独立复跑以 **main@7889bc6（部署版本）为准**（56/56）。worktree 落后不影响本 FIX 判定（F-9 是 7889bc6 新增的独立增强，非本 FIX 范围）；测试执行阶段应从 main 拉取最新代码。本 worktree 交付的测试方案文档在 merge 时合入 main。

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| QA-D1-01（混合信号源盲区） | ✅（heartbeat 报 活跃0 而 pipeline 在跑） | ✅（信号失真，pipeline 活跃被掩盖） | ✅（查 board/log 可发现） | 否 | 否 | **MAJOR** |
| QA-D1-02（连字符步骤缺测） | ❌（修复已生效，仅缺回归测试） | ❌ | — | 否 | 否 | **MINOR** |
| QA-D1-03（文档未上 main） | ✅（下游引用断裂） | ❌ | ✅（查 commit） | 否 | 否 | **MINOR** |

### 5.2 SLA 对照（标准 §8）

| 发现 | 级别 | 响应 | 定位（初步判定） | 方案 | 当前状态 |
|------|:---:|:---:|:---:|:---:|:---:|
| QA-D1-01 | MAJOR | 1 工作日 | 2 工作日（QA 已实机复现 + 证据链完整） | 当前版本窗口（本方案 §3 给出修复方向） | 待研发评估 |
| QA-D1-02 | MINOR | 2 工作日 | — | 不限（本次 FIX 内补测 T22） | 待研发评估 |
| QA-D1-03 | MINOR | 2 工作日 | — | 不限（merge 时合入文档） | 待 OC/研发处置 |

### 5.3 分级示例对照（标准 §5 表）

- QA-D1-01 对照示例 8（「缓存不一致导致部分用户看到过期数据」= MAJOR：数据一致性问题非关键）与示例 16（「关键路径静默失败」）→ 同构，**MAJOR** 成立；对比 BLOCKER 门槛：无资金/核心数据一致性、无 OOM、无安全漏洞 → 不满足 BLOCKER。
- QA-D1-02/03 对照示例 15（代码层面）→ 用户不可感知/低影响 → **MINOR** 成立。

---

## 6. 测试执行与交付

### 6.1 执行步骤（qa-exec 阶段）

```bash
cd /workspace/devPPL   # 注意：先 git pull 到 main@7889bc6+

# 1. 静态检查
python3 -m py_compile scripts/notify_check.py scripts/test_notify_check.py

# 2. 基线复跑（56 断言）
python3 scripts/test_notify_check.py          # 期望 PASS=56 FAIL=0

# 3. 新增用例（T20/T21 需 FIX 落地后；T22-T25 可直接执行）
#    —— 并入 test_notify_check.py 或独立扩展脚本

# 4. 真实库副本 dry-run 核对（只读，不写生产）
cp /root/.hermes/kanban.db /tmp/qa/ && cp pipeline_state.db notify_state.db /tmp/qa/
python3 scripts/notify_check.py --dry-run --state-db /tmp/qa/pipeline_state.db \
  --notify-db /tmp/qa/notify_out.db --kanban-db /tmp/qa/kanban.db
# 期望: [AP HH:MM] 活跃N 跑N 堵N 今完N 与 board 实况一致

# 5. 回归范围
bash scripts/test_workspace_check.sh          # 期望 PASS=27 FAIL=0（B2 回归）
bash scripts/test_cmd_channel.sh              # 期望 78/78（B3 回归，若未跑过）
```

### 6.2 交付物

| 交付物 | 路径 |
|--------|------|
| 本测试方案 | `docs/qa/fix-notify-heartbeat-chain-scope-test-plan.md` |
| （qa-exec 产出）测试报告 | `docs/qa/fix-notify-heartbeat-chain-scope-test-report.md` |

### 6.3 发布门禁对照（标准 §10）

- BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
- 当前：BLOCKER=0，**MAJOR=1**（QA-D1-01）→ 未越过门禁，MAJOR 需在发布前修复或标注 known issue（标准 §1.1）

---

## 7. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | QA-D1-01 盲区未修：qa-d1 done 后 heartbeat 立即失真（sim1 已证明必然发生） | Frank 对系统状态错误认知（本 FIX 核心目标失效） | 测试执行前由 OC 建 FIX 卡给研发；T20/T21 作为回归门禁 |
| R2 | 部署基线差异（worktree 落后 main 1 commit） | 误在旧代码上验证 | 明确以 main@7889bc6 为准；执行前 git pull |
| R3 | PRD/arch 文档不在 main | 下游引用断裂 | QA 已从 commit 核对内容；建议 merge 合入文档 |
| R4 | 新增用例 T20/T21 在修复前 FAIL | 误读为回归 | 标注「FIX 前置」，门禁判定按 §4.3 |
| R5 | 真实库核对（T25）依赖只读查询 | 无写入风险 | 仅 dry-run + SELECT；不触碰生产库写入 |

---

## 附：与本方案相关的既有文档

- B1 通知 cron 验收：`docs/qa/notify-cron-smoke-verification.md`
- B1-F1 回归验证：`docs/qa/retest-notify-cron-b1.md`、`docs/qa/b1-f1-fix-verification.md`
- B3 指令卡通道验证：`docs/qa/retest-b3-cmd-channel.md`
- FIX cmd_chain 补全 QA D1：`docs/qa/fix-cmd-chain-complete-test-plan.md`
- R2 裁定落地设计：`docs/roundtables/b-autopilot-oc-relationship/2026-08-11-r2-rulings-design.md`
- discover 排除集（SUB_TASK_TITLE_PREFIXES）：`pipeline/discover.py`
