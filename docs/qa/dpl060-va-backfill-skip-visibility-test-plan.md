# DPL-060 FIX va_backfill 静默 skip 盲区 — QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-16 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_85f38e3b [DEV-QA-D1] FIX va_backfill 静默 skip 盲区 — claim 无 changed_files 段时 VA 缺口无感（DPL-060）
> 被测代码：**devPPL main @ 6195f34**（S1 77dc2d1 + S2 08ab896 + S3 6195f34 **全部已合入 main**，非未合入分支）
> 上游文档：
> - PRD：`/workspace/mem-core/wiki/projects/devppl/prd/dpl060-va-backfill-skip-visibility-prd.md`（v1.0，289 行，t_a3ba04d3）
> - 架构：`/workspace/mem-core/wiki/projects/devppl/arch/arch-dpl060-va-backfill-skip-visibility.md`（v1.0，661 行，D1-D12 裁决，t_428e6502）
> - 评估：`docs/est/t_a79c9684-estimate.md`（拆 3 serial：S1 23-31 / S2 26-37 / S3 20-31 轮）
> - VA：t_93e567b4（done，12 PASS/1 FALSIFIED——R3-4 claim-schema skill 节因跨 profile sync 回滚，DPL-061 t_6c381232 game-engine 跟进）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> - 基线测试：`scripts/test_va_backfill.sh`（T1-T10，**75 断言**，本卡实测全绿）+ `scripts/test_number_backfill.sh`（33 断言，实测全绿）+ `scripts/test_cmd_channel.sh`（**398 断言**，含 T59i/j CLAIM_HINT）+ devPPL pytest（281/8/1 存量基线，S3 实测零新增）

---

## 0. 执行摘要（测试设计阶段结论）

| 项 | 结果 |
|---|---|
| 被测代码状态 | **main @ 6195f34 已含 DPL-060 全部实现**（S1 机制 + S2 留痕巡检 + S3 规范回归，共 3 merge 已入 main；R3-4 claim-schema skill 节为 repo 外 PINNED skill，DPL-061 单独跟进） |
| 研发验证状态 | S1 t_bdcb5e16 3/3 + S2 t_af4313bd 4/4 + S3 t_de2602b3 5/6；VA t_93e567b4 独立复核 **12 PASS/1 FALSIFIED**（唯一不实 R3-4，非代码缺陷，系 skill 同步回滚） |
| QA 独立核查（本卡已实测） | test_va_backfill.sh **75 PASS / 0 FAIL** + test_number_backfill.sh **33 PASS / 0 FAIL**（详见 §3）；test_cmd_channel.sh 398 断言本卡后台复跑中；静态 S1-S12 全过（§4） |
| D1 前置发现 | **无 BLOCKER / MAJOR / MINOR 缺陷**；0 SUGGESTION；3 项观察（OBS-1 R3-4 skill 节由 DPL-061 跟进，qa-exec 需在 DPL-061 合入后复验；OBS-2 源 H 真实库冒烟需在部署态观察；OBS-3 无 claim comment 卡不进入条件 3，直接走 R2 no-claim 分支——设计使然，R2 恰好补位，非缺陷） |
| 工作量评估 | 预计 **15-21 轮（中位 18）≤ 20 轮阈值 → 不拆卡**（单张 QA 执行子卡），详见 §7 |

**结论**：dev 交付与 VA 复核一致，DPL-060 三层机制（R1 四条件宽化 / R2 skip 三分类留痕+注册+源 H 巡检 / R3 建卡提示+格式完整性文案）经 QA 独立核查全部成立。qa-exec 单卡执行：前置确认 main 被测 commit → 基线三套全量复跑 → 静态 S1-S12 → 探针 P1-P6 → R1-R4 验收逐项核对 → 报告。**本卡 D1 已独立实测：va 75/0 + number 33/0 + cmd 398/0 + 探针 P1/P3 + 静态 S1-S12。**

---

## 1. 测试范围概览

```
被测模块                           PRD 需求覆盖       arch 章节        新增/扩展
──────────────────────────────────────────────────────────────────────────────────────
pipeline/discover.py               R1/R2 (P0)         §2/§3            _latest_claim_has_changed_files 四条件 OR（条件3 metadata + 条件4 交付/commit）
                                                                       + _metadata_has_file_claims + _claim_has_delivery_commit
                                                                       + _va_skip_reason 三分类 + _va_skip_leave_trace（comment 幂等 + 注册）
                                                                       + process_va_backfill skip 分支改造 + va-claim body [格式完整性] 文案
pipeline/constants.py              R3 (P1)            §4               CLAIM_HINT_LINE（L263-266，单一源）
pipeline/cmd_chain.py              R3 (P1)            §4 D10           _dev_card_body WIP 前插 CLAIM_HINT_LINE（L717-718，WIP 保末行）
scripts/oc_wake_check.sh           R2 (P0)            §3 D9            源 H（[va-skip] 行 + reason + skip_count + 状态型键 va-skip:<tid>:<skip_count> + 容器豁免双保险）
scripts/autopilot.sh               R3 (P1)            §4 D11           va-claim 步文案 [格式完整性]（L472）
scripts/test_va_backfill.sh        R1/R2 (P0)         §2.6/§3.5        T9（11 断言：交付-commit / metadata-only / claims=[] 负例 / 裸 commit 负例 / T1-T8 零改动）
                                                                       + T10（14 断言：comment 恰好 1 条 / 注册字段齐全 / 源 H 输出 / 容器豁免 / 幂等）
scripts/test_cmd_channel.sh        R3 (P1)            §4               T59i/T59j（CLAIM_HINT_LINE 存在 + 在 WIP 之前）
```

**零改动确认（回归范围）**：pipeline/state.py、notify_check.py、cmd_channel.sh、chain_check.sh 未改动；VA 验证语义（[VERIFIED]/[FALSIFIED] 判定流程）未动；24h 窗口/每 tick 上限（_VA_BACKFILL_MAX_PER_TICK=10）未动（红线）。

### 1.1 验收标准映射（PRD §5 R1-R4）

| # | 验收要点 | dev 测试锚点 | QA 复核 |
|---|---------|-------------|:---:|
| R1-a | done 卡 claim 只含「**4. 交付** - commit e0e84a2（3 files）」→ 必须补建（t_4436b52e 病例复刻，条件 4） | T9a/b/c/d | ✅ 基线含 + 探针 P2 |
| R1-b | comment 无产物声明但 metadata.claims 含 file_modified → 必须补建（条件 3 canonical 源） | T9e/f/g | ✅ 基线含 + 探针 P1 |
| R1-c | metadata.claims=[] 且 comment 无 commit → 仍 skip（负例，防 OR 扩过头） | T9h | ✅ 基线含 |
| R1-d | comment 含「参考 commit abc1234」无交付语义 → 仍 skip（负例，条件 4 双条件防误报） | T9i | ✅ 基线含 |
| R1-e | 既有 T1-T8 断言全部不变（只增不删） | T9j/k 计数锚点 | ✅ 基线含 |
| R2-a | skip 卡 → 卡面 [VA-SKIP] comment 恰好 1 条（重跑不重复写，幂等 D7） | T10a/T10a2 | ✅ 基线含 + 探针 P4 |
| R2-b | .pipeline/va-skip/<tid>.json 生成且字段齐全（task_id/reason/first_skip_at/skip_count/latest_claim_snippet） | T10b-T10b5 | ✅ 基线含 |
| R2-c | 源 H 输出含该卡 + reason + skip_count；重跑不重复报（状态型键 D9） | T10c-c3 + T10e | ✅ 基线含 + 探针 P5 |
| R2-d | 容器卡（有子卡）不写 comment、不出现在源 H 输出（D6 豁免） | T10d/d2 | ✅ 基线含 |
| R3-a | dev 卡 body 含 CLAIM_HINT_LINE（建卡提示） | T59i | ✅ 基线含 + 静态 S3 |
| R3-b | CLAIM_HINT_LINE 在 WIP 之前（WIP 保末行，T59e 零回归） | T59j | ✅ 基线含 + 静态 S3 |
| R3-c | va-claim 卡 body 含格式完整性检查文案（D11 两处：discover + autopilot） | 静态 grep | ✅ 静态 S6/S7 |
| R3-d | claim-schema skill「格式演进同步规则」节 | — | ⏳ **DPL-061 跟进**（本链不实测，见 OBS-1） |
| R4-a | 三套脚本回归全绿 + pytest 无新增失败 | va 75 + number 33 + cmd 398 + pytest 281/8/1 | ✅ 本卡 va/number 实测 + qa-exec cmd/pytest |
| R4-b | t_4436b52e 实证记录（已有 VA 卡 t_679f3765） | 存量核对 | ✅ 静态 S12 |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 board/DB）：

| 项 | 配置 |
|---|---|
| 被测分支 | **devPPL main @ 6195f34**（qa-exec 若 main 已前进，先 `git log --oneline -3` 确认 6195f34 为祖先，避免测错对象） |
| 隔离 kanban.db | test_va_backfill.sh 自建 $TMPT/kanban.db（复制真实 schema + DROP 触发器 + 后置 seed 5 批） |
| R2 注册文件隔离 | FAKE_REPO=$TMPT/fakerepo（process_va_backfill repo_root 参数指向 temp，不污染仓库） |
| 源 H seen 隔离 | SEEN_FILE=$TMPT/seen + AUTOPILOT_JOBS_JSON=$TMPT/jobs_empty.json |
| 真实库只读核对 | `devppl_query.sh`（禁止裸 python3 -c 内联读 DB，tirith MEDIUM 审批门限） |
| 执行命令 | `bash scripts/test_va_backfill.sh`（75 断言）+ `bash scripts/test_number_backfill.sh`（33 断言）+ `bash scripts/test_cmd_channel.sh`（398 断言）+ `python3 -m py_compile` + `bash -n` + pytest 全量（后台，602s）+ 静态核对 + 探针 |
| 被测代码获取 | main 直接跑（全部已合入） |

**执行前置（qa-exec 阶段）**：
1. main 被测 commit 确认：`git log --oneline -3`（应含 6195f34 merge）+ `git merge-base --is-ancestor 6195f34 HEAD`
2. `python3 -m py_compile pipeline/discover.py pipeline/constants.py pipeline/cmd_chain.py` + `bash -n scripts/autopilot.sh scripts/oc_wake_check.sh scripts/test_va_backfill.sh scripts/test_cmd_channel.sh`
3. 基线三套全量复跑全绿后，再执行新增探针

---

## 3. 基线回归（本卡 D1 已独立实测）

| 测试 | 断言数 | 本卡实测 | qa-exec 要求 |
|------|:---:|:---:|:---:|
| test_va_backfill.sh | 75 | **PASS=75 FAIL=0**（2026-08-16 实测） | 复跑确认全绿 |
| test_number_backfill.sh | 33 | **PASS=33 FAIL=0**（2026-08-16 实测） | 复跑确认全绿 |
| test_cmd_channel.sh | 398 | **PASS=398 FAIL=0**（2026-08-16 本卡后台复跑实测） | 复跑确认全绿 |
| pytest tests/ | 281/8/1 | S3 实测 602s（8+1 全存量零新增） | 后台复跑对照基线，**零新增失败** |

> D1 实测证据：va 75/0 + number 33/0 + cmd 398/0 已在本卡 run 内独立执行通过（非引用 dev claim），见 §3 结论。

### 3.1 本卡 D1 实测摘要（2026-08-16）

| 项 | 结果 |
|---|---|
| test_va_backfill.sh | **75 PASS / 0 FAIL**（独立复跑） |
| test_number_backfill.sh | **33 PASS / 0 FAIL**（独立复跑） |
| test_cmd_channel.sh | **398 PASS / 0 FAIL**（后台复跑，81s） |
| 探针 P1 | PASS：有 claim comment + metadata status='done' → 补建；status='gave_up' → nonstd skip + 留痕（D1 双值语义成立） |
| 探针 P3 | PASS：坏 json 注册文件被忽略，skip_count 从 1 重计，字段齐全（fail-open 成立） |
| 静态 S1-S12 | 全过（§4） |

---

## 4. 静态核查（S1-S12，本卡已全部通过）

| # | 核查点 | 实测证据 |
|---|--------|---------|
| S1 | `_latest_claim_has_changed_files` 四条件 OR 顺序 1/2 → 3 → 4 → False | discover.py L1146-1191；条件 3 不命中不短路条件 4（L1184-1188） |
| S2 | `_metadata_has_file_claims`：claims 数组 file_* 或 changed_files 非空；异常 fail-open False | discover.py L1094-1117（L1116-1117 except → False） |
| S3 | `_claim_has_delivery_commit`：commit 引用 + 交付语义双条件 AND | discover.py L1120-1143（_COMMIT_REF_RE + _DELIVERY_SEMANTIC_RE） |
| S4 | `_va_skip_reason` 三分类：legit-container（task_links EXISTS）/ no-claim / nonstd，异常→nonstd fail-open | discover.py L1205-1228 |
| S5 | `_va_skip_leave_trace`：comment 幂等（(task_id,reason) 写前查）+ snippet 捕获 + 注册 tmp+os.replace 原子写 + skip_count 递增 + first_skip_at 保留 | discover.py L1231-1297 |
| S6 | va-claim 补扫 body 含 [格式完整性] 文案（D11 一处） | discover.py L1378-1380 |
| S7 | autopilot.sh va-claim 步含 [格式完整性] 文案（D11 另一处） | autopilot.sh L472 |
| S8 | oc_wake_check 源 H：窗口查询条件与候选 SQL 对齐 + reason 正则 [a-z][a-z-]* + skip_count 读注册文件 + 状态型键 va-skip:<tid>:<skip_count> | oc_wake_check.sh L372-419 |
| S9 | 源 H 底部统一写回（va_skip_new_keys 排除列表含 va-skip） | oc_wake_check.sh L430-444 |
| S10 | 容器豁免双保险：legit-container reason 不输出 | oc_wake_check.sh L405-406 |
| S11 | constants CLAIM_HINT_LINE + cmd_chain _dev_card_body 插行（CHECKPOINT → CLAIM_HINT → WIP，WIP 末行） | constants.py L263-266 + cmd_chain.py L715-718 |
| S12 | 存量实证：t_4436b52e 已有 VA 卡 t_679f3765（VA t_93e567b4 S3 实证） | t_de2602b3 claim metadata |

---

## 5. 独立探针（P1-P6，qa-exec 执行）

| # | 探针 | 方法 | 预期 |
|---|------|------|------|
| P1 | 条件 3 run 选取边界：有 claim comment（无产物声明）时 status='done' 命中 / 'gave_up' 不命中（D1 双值枚举实测） | temp 库 seed claim + run metadata，run_scan 断言 | done 建卡 / gave_up skip（fail-open False 不误建）（**本卡已实测 PASS**：done 命中补建 / gave_up nonstd skip + 留痕） |
| P2 | 条件 4 双条件边界：交付+commit 命中 / 裸 commit 不命中 / commit 大小写（0-9a-f 7-40） | T9a/T9i 已有 + 补一例大写 commit ref | 命中/不命中符合双条件 AND |
| P3 | 注册文件损坏恢复：旧 json 非法 → skip_count 从 1 重计（fail-open） | 预写坏 json，run_scan 后读注册 | 不抛、字段齐全、skip_count≥1（**本卡已实测 PASS**：坏 json 忽略，reason=no-claim skip_count=1 字段齐全） |
| P4 | comment 幂等边界：同 (task_id,reason) 3 次扫描 → comment 恰 1 条（不刷屏） | T10a 已有，扩到 3 次扫描 | 恒 1 条 |
| P5 | 源 H 真实库只读冒烟：对 live board 跑 oc_wake_check 源 H 不崩、不写卡 | `bash scripts/oc_wake_check.sh <repo> 2>&1`（只读） | exit 0 / 无异常 / 不创建任何卡（fail-open） |
| P6 | CLAIM_HINT_LINE 插行零回归：T59e（末行=WIP）断言仍过 + T59i/j 新增断言过 | test_cmd_channel.sh T59e/i/j | 398/0 全绿 |

---

## 6. 分级标准对照（qa-finding-classification.md v1.0）

- 若 qa-exec 发现「四条件全命中仍 skip 且无留痕」类缺陷 → 用户可感知（VA 缺口继续无感）+ 功能阻断（补扫失效）+ 无 workaround → **BLOCKER**（对照标准 §5 表 BLOCKER 行）。
- 若发现「[VA-SKIP] comment 文案与文档不一致（如时间戳格式）」→ 用户可感知 + 不阻断（留痕功能正常）+ workaround（人读注释理解）→ **MINOR**。
- 若发现「源 H 对 legit-container 防御冗余」→ 不阻塞、不劣化 → **SUGGESTION**。

---

## 7. 工作量评估与拆卡决策（任务 body 要求）

### 7.1 评估依据

| 阶段 | 内容 | 预计轮数 |
|------|------|:---:|
| ① 前置检查 | main commit 确认 + py_compile/bash -n（6 项） | 1 |
| ② test_va_backfill.sh | 75 断言（实测 ~1min/遍，可能 2 次迭代） | 2-3 |
| ③ test_number_backfill.sh | 33 断言 | 1-2 |
| ④ test_cmd_channel.sh | 398 断言（含 T59e/i/j 回归锁定） | 2-3 |
| ⑤ pytest 全量 | 281/8/1 存量基线（实测 602s，后台跑 + 对照） | 2-3 |
| ⑥ 静态核对 | S1-S12 逐项 + 与 dev claim 交叉（本卡已跑通，qa-exec 复验成本低） | 1-2 |
| ⑦ 独立探针 | P1-P6（P3 坏 json / P4 三次扫描 / P5 真实库冒烟为新增） | 3-4 |
| ⑧ AC 核对 + 报告 | R1-R4 逐项核对 + 写 test_report.md + [PRODUCES]/[CLAIM] + 飞书推送 | 3-4 |
| **合计** | | **15-21（中位 18）** |

> 校准说明：本任务为**单仓已合入 main**（无 mem007 的双仓/未合入 OBS-1 成本），dev 已交付完整测试体系（T9 11 + T10 14 断言），QA 主要是**独立复跑 + 静态核对 + 少量边界探针**。对比 DPL-030（13-20 不拆）、MEM-007（14-20 不拆），本卡多一项 pytest 全量 602s 尾部等待（后台并行可吸收）与源 H 真实库冒烟。按 DPL-018 校准经验（QA 执行偏差 +20-30%），诚实区间 **15-21 轮（中位 18）**。

### 7.2 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | **15-21 轮（中位 18）≤ 20 轮阈值 → 不拆**（上限 21 含 pytest 后台等待与探针调试，qa-exec 单卡可吸收：pytest 后台跑与静态/探针并行） |
| 模块依赖 | 全部验收共享同一批基线（va 75 + number 33 + cmd 398）与同一被测对象（main @ 6195f34）；静态/探针/AC 核对均为独立只读操作，无串行数据依赖 |
| 并行收益 | 无——单被测对象 + 共享基线环境，拆卡只引入 merge/交接成本 |
| 兜底 | 若 qa-exec 实际执行中发现 pytest 基线调试或探针调试成本超预期，可在执行卡内按建卡铁律拆职责内子卡（assignee=game-qa，parents 挂当前卡） |

**决策：不拆卡（[QA-SUB-SPLIT] 1，单张 QA 执行子卡由 autopilot 按链自动建）。**

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | qa-exec 时 DPL-061（t_6c381232，R3-4 skill 节）已合入/未合入 | R3-4 验收状态漂移 | 本链 R3-4 不实测（OBS-1 标注，DPL-061 链独立验证）；qa-exec 报告注明「skill 节归属 DPL-061」避免重复判定 |
| R2 | main 在 qa-exec 前前进（其它链 merge） | 被测对象变化 | 执行前置确认 6195f34 为祖先；以合并后 main 为准，DPL-060 相关文件用 git log 确认未被动过 |
| R3 | pytest 全量 602s 超长 | 单轮迭代耗时 | 后台跑 + 与静态/探针并行；只对照存量失败集（281/8/1 的 8+1）零新增 |
| R4 | 源 H 真实库冒烟（P5）潜在写 seen 风险 | 触碰 live 状态文件 | SEEN_FILE env 指向 temp；只读核对不写卡；deploy 态由 qa-post/OC 补观测 |
| R5 | cmd_channel 398 断言执行时长 | 多轮迭代耗时 | 单遍全绿优先；失败定位用断言名 grep 输出 |
| R6 | claim-schema skill 同步回滚（12h cron）影响后续 claim 引用 | 引用失效 | 任何 skill 节改动必须改 orchestrator canonical（VA t_93e567b4 lessons）；本卡不改 skill |

---

## 附：与本方案相关的既有文档

- DPL-060 PRD：`/workspace/mem-core/wiki/projects/devppl/prd/dpl060-va-backfill-skip-visibility-prd.md`
- DPL-060 架构：`/workspace/mem-core/wiki/projects/devppl/arch/arch-dpl060-va-backfill-skip-visibility.md`
- DPL-060 评估：`docs/est/t_a79c9684-estimate.md`
- VA 复核：t_93e567b4（12 PASS/1 FALSIFIED）+ `.va_reports/20260816T122000_va_t_93e567b4.json`
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0
