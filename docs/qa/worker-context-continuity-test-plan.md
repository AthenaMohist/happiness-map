# worker 上下文连续性（DPL-030）— QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-15 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_07b1c297 [DEV-QA-D1] worker 上下文连续性 — 检查点提交+发现笔记+预算收紧+审批白名单（DPL-030）
> 被测提交：**wt/t_7c9d1952 @ ea489fb**（main e714aa1 + 5 commits FF-ready；**尚未合入 main**，qa-exec 前置须确认 merge-base）
> 上游文档：
> - PRD：`docs/prd/worker-context-continuity-prd.md`（v1.0，255 行，t_84c53424）
> - 架构：`docs/arch/arch-worker-context-continuity.md`（v1.0，329 行，t_d24d1ad5）
> - 评估：`docs/est/t_c8ad7805-estimate.md`（commit 0d2fee9，拆 4 张串行 dev 子卡）
> - VA：t_74724cf6（done，15/15 claims PASS，0 FALSIFIED，AC-1..AC-10 全绿）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> - 基线测试：`scripts/test_cmd_channel.sh`（T1-T74+T59e/T60a 修正+T63，**386 断言**，本卡实测全绿）+ `scripts/test_chain_check.sh`（41 断言）

---

## 0. 执行摘要（测试设计阶段结论）

| 项 | 结果 |
|---|---|
| 被测代码状态 | **wt/t_7c9d1952 @ ea489fb 已含 DPL-030 全部实现**（11 文件 +381/-9）：constants WIP_*/EST_* 11 常量 + inject_wip_rule.sh（64 行幂等注入）+ cmd_chain/discover 建卡路径注入（含 _sub_card_body 补洞）+ autopilot 5 处 [WIP 节奏] comment + devppl_query comments 子命令 + test_cmd_channel.sh 新断言（T59h/T60b-d/T63a-i）+ 4 个 .pipeline/wip 发现笔记。**尚未合入 main**（FF-ready，等待 merge） |
| 研发验证状态 | game-engine 4 张子卡 claims + merge claim → VA t_74724cf6 独立复核 **15/15 VERIFIED，0 FALSIFIED**（AC-1..AC-10 全绿） |
| QA 独立核查（本卡已实测） | 基线全量 @ wt/t_7c9d1952 → **PASS=386 FAIL=0**；静态 S1-S11 **11/11 通过**；探针 P1-P5 **5/5 通过**（详见 §3） |
| D1 前置发现 | **无 BLOCKER / MAJOR / MINOR 缺陷**；0 SUGGESTION；1 项流程观察（OBS-1：被测代码未合入 main，qa-exec 前置确认 merge-base） |
| 工作量评估 | 预计 **13-20 轮（中位 17）≤ 20 轮阈值 → 不拆卡**（单张 QA 执行子卡），详见 §7 |

**结论**：dev 交付与 VA 复核一致，机制本体（WIP 节奏/发现笔记/预算收紧/审批绕路）经 QA 独立核查全部成立。qa-exec 单卡执行：前置确认被测 commit → 基线 386 全量 → 静态 S1-S11 → 探针 P1-P6 → AC-1..AC-10 逐项核对 → 报告。

---

## 1. 测试范围概览

```
被测模块                           PRD AC 覆盖       arch 章节        新增/扩展
──────────────────────────────────────────────────────────────────────────────
pipeline/constants.py             R1/R2/R3 (AC-1)   §1.2             WIP_SOUL_TITLE/PROFILES/MIN/MAX/COMMIT_PREFIX/
                                                                    NOTE_DIR/BODY_LINE/SOUL_PARAGRAPH + EST_EFFECTIVE_RATIO/
                                                                    SPLIT_ROUNDS/EFFECTIVE_LINE（11 常量）
scripts/inject_wip_rule.sh        R1/R2 (AC-2)      §1.3            新脚本（--dry-run/--verify/--profiles/幂等 SKIP）
pipeline/cmd_chain.py             R1/R2/R3 (AC-4/5/9) §1.4 P1/P2/P3/P4  _dev_card_body 末行 WIP（L651-652）+ _sub_card_body 补洞
                                                                    CHECKPOINT+WIP 双行（L858-859）+ dev-est 块 EST_EFFECTIVE_LINE（L638）
pipeline/discover.py              R1/R2/R3 (AC-4/5) §1.4 P4          est_body EST_EFFECTIVE_LINE（L249）+ WIP_BODY_LINE（L254）
scripts/autopilot.sh              R1 (AC-3)        §1.4 P5          5 处 comment 串追加 [WIP 节奏]（L159/343/383/520/665）
scripts/devppl_query.sh           R4-A (AC-6)      §3.1/§3.2        comments 子命令（白名单 + 只读 + ORDER BY created_at ASC）
scripts/test_cmd_channel.sh       R1-R4 (AC-7/8)   §6               T59h/T60b-d/T63a-i（13 新断言）+ T59e/T60a 修正
.pipeline/wip/*.md                R2               §1.5             4 张 dev 子卡发现笔记（六节模板实证）
```

**零改动确认（回归范围）**：pipeline/state.py、notify_check.py、cmd_channel.sh、chain_check.sh 未改动；`EST_SPLIT_THRESHOLD_ROUNDS=20` 未动（AC-10 红线）；inject_checkpoint_rule.sh 未动（DPL-019 既有）。

### 1.1 验收标准映射（PRD §6.1 AC-1..AC-10）

| AC | 验收要点 | dev 用例 | QA 复核 |
|----|---------|---------|:---:|
| AC-1 | constants.py 新增 WIP_SOUL_* / WIP_BODY_LINE / EST_* 常量（单一源） | grep 证据 | ✅ 静态 S1 |
| AC-2 | inject_wip_rule.sh 幂等注入 9 profile，--verify 全 HIT/SKIP | 脚本输出 | ✅ 探针 P2/P3（**真实注入已存在**：9/9 FOUND + SKIP 9/9 + VERIFY-OK 9/9） |
| AC-3 | autopilot.sh 建卡 comment 含 [WIP 节奏]（5 处实测） | grep | ✅ 静态 S4 |
| AC-4 | dev 卡 / est 卡 body 末含 WIP_BODY_LINE | T59h/T60c | ✅ 基线含 |
| AC-5 | dev-est 口径含「有效轮数 × 0.7」折算指引（双入口） | T60d/T63a | ✅ 基线含 |
| AC-6 | devppl_query.sh 新增 comments 子命令（白名单 + 只读） | T63g-i + 手测 | ✅ 基线含 + 探针 P4/P5 |
| AC-7 | test_cmd_channel.sh 全量回归 PASS（基线 373 + 新增） | 测试输出 | ✅ **386 PASS/0 FAIL**（本卡复跑） |
| AC-8 | 结构化 claim（changed_files/tests_run/verification） | kanban_complete metadata | ✅ VA 已核（S3-c） |
| AC-9 | subsplit 子卡 body 含 WIP_BODY_LINE 且含 CHECKPOINT_BODY_LINE（修正 3 补强） | T63c/d/e | ✅ 基线含 |
| AC-10 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变（红线回归） | T63f/T68b | ✅ 基线含 + 静态 S2 |

### 1.2 架构裁决项跟踪（§0.2/§0.3 修正吸收）

| 项 | 裁决 | 测试关注 | 状态 |
|----|------|---------|:---:|
| 修正 1 | DPL-019 checkpoint SOUL 注入必须已执行（9/9） | 探针 P2 扩展（WIP 段与 checkpoint 段并存） | ✅ 实测 9/9 已注入 |
| 修正 2 | _sub_card_body 补洞（CHECKPOINT+WIP 双行） | T63c/d/e + 静态 S5 | ✅ 实测 L858-859 |
| 修正 3 | AC-9 回归断言锚定 subsplit 子卡 | T63c/d/e | ✅ 基线含 |
| A-1 | P5 注入点为 5 处（非 PRD 6 处），L362/L400 无 comment 参数 | 静态 S4 + 探针 P6 | ✅ 实测 5 处 |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 board）：

| 项 | 配置 |
|---|---|
| 被测分支 | **wt/t_7c9d1952 @ ea489fb**（若 qa-exec 时已合入 main，则以 main 为准；**先核对 merge-base，避免测错对象**） |
| 隔离 kanban.db | test_cmd_channel.sh 自建 $TMPT/kanban.db（复制真实 schema + 受控行） |
| 隔离 pipeline_state.db | $TMPT/pipe*.db（CheckpointDB.ensure_schema） |
| 真实库只读核对 | `scripts/devppl_query.sh` 查状态 + 9 profile SOUL.md 只读 grep（禁止裸 python3 -c 读 DB） |
| 执行命令 | `bash scripts/test_cmd_channel.sh`（386 断言）+ `bash scripts/test_chain_check.sh`（41 断言）+ 探针脚本 |
| 被测代码获取 | 若 main 未合入：`cd /workspace/devPPL/.worktrees/t_7c9d1952` 直接执行；或在工作树分支 `git merge wt/t_7c9d1952` 后执行 |

**执行前置（qa-exec 阶段）**：
1. 被测分支确认：`git merge-base --is-ancestor e714aa1 main`（main 是否已含 DPL-030 基础）+ `git log wt/t_7c9d1952 -1` 记录被测 commit
2. `python3 -m py_compile pipeline/constants.py pipeline/cmd_chain.py pipeline/discover.py`
3. 基线全量复跑全绿后，再执行新增探针

---

## 3. ⚠️ D1 前置发现（测试设计阶段）

### 3.1 缺陷发现汇总

**无 BLOCKER / MAJOR / MINOR 缺陷。** QA 独立核查项全部通过（§3.2）。

### 3.2 QA 独立核查结果（本卡已实测，非转述）

| # | 核查项 | 结果 |
|---|--------|:---:|
| G1 | 基线全量 test_cmd_channel.sh @ wt/t_7c9d1952 | **PASS=386 FAIL=0**（EXIT=0） |
| G2 | 静态 S1-S11（11 项，见 §4.2） | **11/11 通过** |
| G3 | 探针 P1-P5（SOUL 注入现场 / 幂等 / comments 合法 / BAD_ID / 签名） | **5/5 通过** |
| G4 | 9 profile SOUL.md 含 WIP 段（AC-2 真实注入） | **9/9 FOUND**（game-engine..tag-system 各 1 命中） |
| G5 | inject_wip_rule.sh --dry-run | **SKIP 9/9**（幂等成立），RC=0 |
| G6 | devppl_query.sh comments：合法 id（t_74724cf6） | **RC=0**，输出 author/时间/body 全文 |
| G7 | devppl_query.sh comments：bad_id | **BAD_ID + RC=1**（白名单生效） |
| G8 | autopilot [WIP 节奏] 注入点 | **恰 5 处**（L159/343/383/520/665），L362/L400 无 comment 参数（arch A-1 成立） |
| G9 | bash -n 语法 | test_cmd_channel / inject_wip_rule / autopilot / devppl_query 全 OK |
| G10 | .pipeline/ 不在 .gitignore | 仅 pipeline_state.db* 被 ignore（发现笔记可入库） |

### 3.3 观察项（非缺陷，登记备查）

| # | 观察 | 说明 | 处置建议 |
|---|------|------|---------|
| OBS-1 | 被测代码未合入 main | DPL-030 全量在 wt/t_7c9d1952，main @ e714aa1 无 WIP/EST 常量。qa-exec 若在 merge 前执行，须直接在被测 worktree 分支跑（DPL-028 先例：同样在 wt/t_ee71cabb 测） | qa-exec 前置确认被测 commit；不阻塞本卡 |

---

## 4. 测试用例设计

### 4.1 基线 386 断言（研发已有，QA 独立复跑确认）——按需求域归类

| 需求域 | 用例 | 断言数 | 说明 |
|--------|------|:---:|------|
| 指令通道基础 | T1-T12 | ~30 | 消费/归档/幂等/roundtable/fail-open/告警 |
| 开发链补全 | T13-T25 | ~60 | 连字符步骤/全链/merge/close/跳步 |
| 拆卡 | T26-T31 | ~40 | [SUB-SPLIT]/[QA-SUB-SPLIT]/子卡扇入 |
| 评估步 | T32-T50 | ~90 | dev-est 拦截/评估卡/触发器/子卡 |
| 编号/工具 | T40-T58 | ~80 | next-seq/memctl/回滚重试/僵尸清理 |
| DPL-018 校准 | T59-T74 | ~60 | est_deviation/系数/注入/横幅/backfill |
| **DPL-030 新增** | T59h/T60b-d/T63a-i | **13** | WIP/EST/CHECKPOINT 注入断言（AC-4/5/6/9/10） |

> 注：T59e/T60a 为 DPL-030 适配修正（末行=WIP 节奏行，CHECKPOINT 行保留存在性断言），S2 卡已实现（5992dab）。

### 4.2 静态核对清单（QA 独立代码核对，S1-S11；本卡已执行 ✅）

| # | 核对项 | 依据 | 结果 |
|---|--------|------|:---:|
| S1 | constants.py 11 个 WIP_*/EST_* 常量（WIP_SOUL_TITLE/PROFILES/MIN/MAX/COMMIT_PREFIX/NOTE_DIR/BODY_LINE/SOUL_PARAGRAPH + EST_EFFECTIVE_RATIO/SPLIT_ROUNDS/EFFECTIVE_LINE），L238-275 | arch §1.2 | ✅ |
| S2 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变（AC-10 红线） | L92 | ✅ |
| S3 | inject_wip_rule.sh：--dry-run/--verify/--profiles + 幂等（WIP_SOUL_TITLE 已存在→SKIP）+ 段落单一源 import（cd REPO_ROOT + PYTHONPATH 防影子导入） | arch §1.3 | ✅ |
| S4 | autopilot.sh [WIP 节奏] 恰好 5 处（L159/343/383/520/665）；L362/L400 无 comment 参数（arch A-1 实测结论） | arch §1.4 | ✅ |
| S5 | cmd_chain.py：_dev_card_body 末行 CHECKPOINT+WIP（L651-652）；_sub_card_body 末尾 CHECKPOINT+WIP 补洞（L858-859）；dev-est 块 EST_EFFECTIVE_LINE（L638） | arch §1.4 P1/P2/P3/P4 | ✅ |
| S6 | discover.py：est_body EST_EFFECTIVE_LINE（L249）+ CHECKPOINT（L253）+ WIP（L254）顺序正确 | arch §1.4 P4 | ✅ |
| S7 | devppl_query.sh comments：白名单 ^t_[a-z0-9]+$ + mode=ro + ORDER BY created_at ASC + usage 注册 | arch §3.2 | ✅ |
| S8 | test_cmd_channel.sh 新断言 13 条（T59h/T60b/T60c/T60d/T63a-i）编号与内容对齐 | S2 claim | ✅ |
| S9 | .pipeline/wip/ 4 个发现笔记存在且六节模板完整（上游契约/关键事实/已踩坑/当前进度/下一步/更新记录） | arch §1.5 | ✅ |
| S10 | .pipeline/ 不在 .gitignore（仅 pipeline_state.db* 被 ignore） | PRD §3 | ✅ |
| S11 | bash -n 语法 4 脚本全 OK | — | ✅ |

### 4.3 独立探针（P1-P6，qa-exec 阶段执行；P1-P5 本卡已跑通 ✅）

| # | 探针 | 目标 | 命令/断言 | 结果 |
|---|------|------|----------|:---:|
| P1 | WIP_SOUL_PARAGRAPH 六节模板 | 模板与 PRD R2-2 一致 | sed constants L248-272；含 六节标题 | ✅ |
| P2 | 真实 9 profile SOUL 注入现场（AC-2） | 9 profile SOUL.md 含 WIP 段标题 | grep -c =1 ×9（只读） | ✅ |
| P3 | inject_wip_rule.sh 幂等重跑 | --dry-run → SKIP 9/9 | bash scripts/inject_wip_rule.sh --dry-run | ✅ |
| P4 | devppl_query.sh comments 合法 id | 输出 comment 线（author/时间/body） | 对 t_74724cf6 → RC=0 且含 [VERIFIED] | ✅ |
| P5 | devppl_query.sh comments 白名单 | bad_id → BAD_ID + RC=1 | bash scripts/devppl_query.sh comments bad_id | ✅ |
| P6 | autopilot 注入点完整性（A-1 补验） | [WIP 节奏] 恰 5 处 + L362/L400 无 comment 参数 | grep -n + sed 上下文（qa-exec 复验） | 待 qa-exec |

### 4.4 验收口径逐项核对（qa-exec 阶段）

AC-1..AC-10 的验收证据链：静态 S1-S11（代码 grep）+ 基线 386 断言（T59h/T60b-d/T63a-i 已含）+ 探针 P1-P6 + VA 已核 claims。qa-exec 逐项打勾，与 VA 结论交叉印证，任何不一致按分级标准处理。

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）代码缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR**（设计阶段） |
| OBS-1（未合入 main） | ✅（qa-exec 需在分支测） | ❌（FF-ready，merge 即可） | ✅（直接测 wt/t_7c9d1952 分支，DPL-028 先例） | 否 | 否 | **观察项**（非功能缺陷，不设 SLA） |

### 5.2 SLA 对照（标准 §8）

设计阶段无 BLOCKER/MAJOR 发现 → 无 SLA 触发。qa-exec 阶段若出现 BLOCKER：4h 响应 + 8h 定位 + 24h 方案；MAJOR：24h 响应 + 72h 方案（按标准 §8 表格执行）。

### 5.3 分级示例对照（标准 §5 表）

- 若 qa-exec 发现「注入点漏注某路径」类缺陷 → 用户可感知（worker 看不到提示）+ 功能阻断（接续契约失效）+ 无 workaround → **BLOCKER**（对照标准 §5 表 BLOCKER 行）。
- 若发现「WIP_BODY_LINE 文案拼写错误」→ 用户可感知 + 不阻断（语义仍可读）+ workaround（人读理解）→ **MINOR**。

---

## 6. 测试执行与交付

### 6.1 执行步骤（qa-exec 阶段，先满足 §2 前置）

```bash
cd /workspace/devPPL/.worktrees/t_7c9d1952   # 或已合入后的 main
# 1. 静态检查
python3 -m py_compile pipeline/constants.py pipeline/cmd_chain.py pipeline/discover.py
# 2. 基线全量（期望 386 PASS / 0 FAIL）
bash scripts/test_cmd_channel.sh
# 3. chain_check 回归（期望 41 PASS / 0 FAIL）
bash scripts/test_chain_check.sh
# 4. 静态核对 S1-S11（逐项，见 §4.2）
# 5. 独立探针 P1-P6（见 §4.3；P1-P5 本卡已跑通，qa-exec 复验 + P6）
# 6. AC-1..AC-10 逐项核对（§1.1 表）
# 7. 报告
#    docs/qa/worker-context-continuity-test-report.md
```

### 6.2 交付物

| 交付物 | 路径 |
|--------|------|
| 本测试方案 | `docs/qa/worker-context-continuity-test-plan.md`（本文件） |
| （qa-exec 产出）测试报告 | `docs/qa/worker-context-continuity-test-report.md` |

### 6.3 发布门禁对照（标准 §10）

- BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
- 当前（设计阶段）：BLOCKER=0，MAJOR=0，安全漏洞=0 → 门禁满足（qa-exec 阶段以实测为准更新）。

---

## 7. 工作量评估与拆卡决策（任务 body 要求）

### 7.1 评估依据

| 阶段 | 内容 | 预计轮数 |
|------|------|:---:|
| ① 前置检查 | 确认被测 commit（wt/t_7c9d1952 或合并后 main）+ py_compile | 1 |
| ② 基线全量 | test_cmd_channel.sh 386 断言（实测 2-5 min/遍，可能 2 次迭代） | 2-3 |
| ③ chain_check | 41 断言 | 1 |
| ④ 静态核对 | S1-S11 逐项 + diff 核对（7 文件） | 2-3 |
| ⑤ 独立探针 | P1-P6（P1-P5 本卡已跑通，qa-exec 复验成本低；P6 autopilot 上下文核对） | 2-3 |
| ⑥ AC 逐项核对 | AC-1..AC-10（对照 §1.1 表 + VA 结论交叉） | 2-3 |
| ⑦ 报告 | 写 test_report.md + [PRODUCES]/[CLAIM] + 飞书推送 | 2-3 |
| **合计** | | **12-17（中位 14-15）** |

> 校准说明：本任务为**文本注入型改动**（常量 + 脚本 + 7 处注入串 + 断言），无算法/无状态机/无 DB schema 变更，风险面远小于 DPL-028（advance 重写，估 18-24）。QA 探针 P1-P5 本卡已实际跑通（非推测），qa-exec 主要是复验 + 报告。按 DPL-018 校准经验（QA 执行偏差通常 +20-30%），诚实区间 **13-20 轮（中位 17）**。

### 7.2 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | **13-20 轮（中位 17）≤ 20 轮阈值 → 不拆** |
| 模块依赖 | 全部验收共享同一条基线（386 断言）与同一被测分支；静态/探针/AC 核对均为独立只读操作，无串行数据依赖 |
| 并行收益 | 无——单被测对象 + 共享基线环境，拆卡只会引入 merge/交接成本 |
| 兜底 | 若 qa-exec 实际执行中发现集成用例调试成本超预期，可在执行卡内按建卡铁律拆职责内子卡（assignee=game-qa） |

**决策：不拆卡（[QA-SUB-SPLIT] 1，单张 QA 执行子卡由 autopilot 按链自动建）。**

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | qa-exec 时 main 已合入 DPL-030（autopilot 活跃 merge 可能已发生） | 被测对象变化 | 执行前置确认 merge-base；以合并后 main 为准；与 wt/t_7c9d1952 内容一致性用 git diff 核对 |
| R2 | 被测代码尚未合入 main（OBS-1） | qa-exec 在分支上测，与发布态有偏差 | DPL-028 先例（wt/t_ee71cabb 直接测）；qa-post 阶段在 main 上再回归一遍兜底 |
| R3 | 探针涉及真实 profile SOUL（/root/.hermes/profiles 跨 profile） | 只读 grep 无写风险 | 严格执行只读（grep/--dry-run）；真实注入已由 OC 完成，qa 只核对 |
| R4 | devppl_query comments 输出大卡 comment 全文（body 长） | 输出截断影响断言 | 断言关键词子串；T63g 用受控 fixture 卡（t_cmd63）已验证 |
| R5 | 基线 386 断言时长（2-5 min/遍） | 多轮迭代耗时 | 单遍全绿优先；失败定位用断言名 grep 输出 |

---

## 附：与本方案相关的既有文档

- DPL-030 PRD（规范源）：`docs/prd/worker-context-continuity-prd.md`
- DPL-030 架构落地：`docs/arch/arch-worker-context-continuity.md`
- DPL-030 评估拆卡：`docs/est/t_c8ad7805-estimate.md`
- DPL-019 存档铁律：`docs/prd/archive-inheritance-50rounds-prd.md`
- DPL-018 校准机制：`docs/prd/estimate-calibration-prd.md`
- QA 发现分级标准：`docs/standards/qa-finding-classification.md`
- 类似 D1 方案参考：`docs/qa/pipeline-parallel-dual-review-test-plan.md`（DPL-028，18-24 轮拆 2 serial 先例）、`docs/qa/fix-standalone-dev-subsplit-test-plan.md`（DPL-020，16-22 轮拆 2 serial 先例）
