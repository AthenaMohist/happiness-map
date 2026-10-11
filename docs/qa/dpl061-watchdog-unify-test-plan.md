# DPL-061 FIX watchdog 统一 — QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-16 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_480d0aae [DEV-QA-D1] FIX watchdog 统一 — oc_wake_check 吸收 stuck-15min/幽灵卡/main-dirty + 归档死脚本（DPL-061）
> 被测代码：**devPPL main @ c96c9ae**（S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 **全部已合入 main**，非未合入分支）
> 上游文档：
> - PRD：`/workspace/mem-core/wiki/projects/devppl/prd/dpl061-watchdog-unify-oc-wake-check-prd.md`（v1.0，303 行，t_34d696d5）
> - 评估：`docs/est/t_12539484-estimate.md`（拆 3 serial：S1 16-23 / S2 26-39 / S3 18-29 轮）
> - VA：t_a1d8c2a9（done，16/16 PASS，0 FALSIFIED；唯一发现 F1 MEDIUM 部署漂移已由 t_5ab4b04c 闭环）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0 + `docs/standards/devppl-test-spec.md` v1.0
> - 基线测试：`scripts/test_watchdog_unify.sh`（T1-T9，**28 断言**，本卡实测全绿）+ `scripts/test_wip_progress_check.sh`（62 断言）+ `scripts/test_deploy_drift.sh`（29 断言）+ `scripts/test_va_backfill.sh`（75 断言）+ `scripts/test_cmd_channel.sh`（398 断言）+ devPPL pytest（281/8/1 存量基线）

---

## 0. 执行摘要（测试设计阶段结论）

| 项 | 结果 |
|---|---|
| 被测代码状态 | **main @ c96c9ae 已含 DPL-061 全部实现**（S1 机制三源 + S2 测试套件+rstrip 修复 + S3 归档+迁移，共 3 merge 已入 main） |
| 研发验证状态 | S1 t_7f86d7eb 5/5 + S2 t_9bb95b42 4/4 + S3 t_cc4bde55 7/7；VA t_a1d8c2a9 独立复核 **16/16 PASS，0 FALSIFIED** |
| QA 独立核查（本卡已实测） | test_watchdog_unify.sh **28 PASS / 0 FAIL** + test_deploy_drift **29/0** + test_va_backfill **75/0** + test_wip_progress_check **62/0** + test_cmd_channel **398/0** + 探针 P1/P2/P3/P3b/P4 **8/8 PASS** + pytest **281/8/1 零新增失败**（详见 §3/§5）；静态 S1-S12 全过（§4） |
| 部署漂移 F1 | **已闭环**：live oc_wake_check.sh md5 23936e2a == repo（t_5ab4b04c done，DPL-048 md5 一致 PASS）；本卡复核两侧 md5 一致 ✅ |
| D1 前置发现 | **无 BLOCKER / MAJOR / MINOR 缺陷**；0 SUGGESTION；1 项观察（OBS-1：源 K 首个线上 tick 输出观察记录依赖后续 cron tick，qa-exec 记录现状即可，最终线上确认由 qa-post/OC 补观测） |
| 工作量评估 | 预计 **13-19 轮（中位 16）≤ 20 轮阈值 → 不拆卡**（单张 QA 执行子卡），详见 §7 |

**结论**：dev 交付与 VA 复核一致，DPL-061 四层机制（源 I 幽灵卡 / 源 J main-dirty / 源 K stuck-long / R4 归档+迁移）经 QA 独立核查全部成立，唯一漂移 F1 已由 OC 闭环。qa-exec 单卡执行：前置确认 main 被测 commit → 基线五套全量复跑 → 静态 S1-S12 → 独立探针 P1-P5 → R1-R5 验收逐项核对 → 报告。**本卡 D1 已独立实测：watchdog_unify 28/0 + deploy 29/0 + va 75/0 + wip 62/0 + cmd 398/0 + pytest 281/8/1（零新增）+ 探针 8/8 + 静态 S1-S12 + 部署 md5 复核。**

---

## 1. 测试范围概览

```
被测模块                           PRD 需求覆盖       arch 章节        新增/扩展
──────────────────────────────────────────────────────────────────────────────────────
scripts/oc_wake_check.sh           R1/R2/R3 (P0)      §2/§3/§4         源 I（幽灵卡 L443-465）+ 源 J（main-dirty L467-490）
                                                                       + 源 K（stuck-long L492-529）+ 头注释 A-H → A-K
                                                                       + 底部 seen 写回改点（跳过名单 + main_dirty_new_keys）
scripts/test_watchdog_unify.sh     R5 (P0)            §8.2             新增 T1-T9（28 断言：三源 fixture + 归档存在性）
scripts/archive/                   R4 (P0)            §5 D5            watch_board.sh / watch_dpl_chains.sh / oc_stuck_watchdog.py / test_oc_stuck_watchdog.py（git mv 归档 4 文件）
infomanager cron 6b695ac1e290      R4 (P0)            §5 D8            删除（OC 执行，D8 顺序 ②）
```

**零改动确认（回归范围）**：源 A-H 逻辑零改动（git diff 6195f34..main 仅 4 行删除 = 跳过名单元组加 "main-dirty" + 头注释 + 注释行）；`stuck_check.sh` / `deploy_drift_check.sh` / `autopilot.sh` 未动；seen 键 `ghost-card:<tid>` / `stuck-running-long:<tid>` 未进跳过名单（一次性键，走 out 行自动解析）。

### 1.1 验收标准映射（PRD §5 R1-R5）

| # | 验收要点 | dev 测试锚点 | QA 复核 |
|---|---------|-------------|:---:|
| R1-a | ikey=discover-est-* 且源卡不存在 → 输出 `[ghost-card] <tid> 源卡 <src> 不存在` | T1a/b | ✅ 基线含 + 静态 S2 |
| R1-b | 源卡存在 → 不输出；status=archived → 不输出（负例） | T2a/T2c | ✅ 基线含 |
| R1-c | qa 前缀 discover-qa-est-* → 命中 | T2b | ✅ 基线含 |
| R1-d | 重跑不重复报告（一次性键 ghost-card:<tid> 落盘） | T3a/b | ✅ 基线含 + 静态 S5 |
| R2-a | 脏 repo（pipeline/ scripts/ 未提交）→ 输出 `[main-dirty]` + 前 5 文件 | T4a/b | ✅ 基线含 + 静态 S3 |
| R2-b | seen 含 main-dirty:<文件列表 sha1 前8>（状态型键，D10 完整列表哈希） | T4c | ✅ 基线含 + 静态 S6 |
| R2-c | 干净 repo → 不输出；集合变化 → 重报；非 git → fail-open exit 0 | T5a/T5b/T5c | ✅ 基线含（T5b 同时锁 rstrip 修复） |
| R3-a | running + started_at 16min 前 + 心跳新鲜 → 输出 `[stuck-running-long] 已跑 16 分钟（心跳 N 分钟前）` | T6a/b/c | ✅ 基线含 + 静态 S4 |
| R3-b | 14min 未超阈值 → 不输出；B 重叠（hb_stale AND claim_dead）→ K 不输出 | T7a/T7b | ✅ 基线含 + 静态 S7 |
| R3-c | 重跑不重复报告（一次性键 stuck-running-long:<tid> 落盘） | T8a/b | ✅ 基线含 |
| R4-a | scripts/archive/ 4 文件存在且非空；旧路径消失 | T9 | ✅ 基线含 + 静态 S9 |
| R4-b | infomanager cron 6b695ac1e290 已删；orchestrator f2aa32251adc 保留；wrapper 清理 | OC 操作记录 | ✅ 静态 S10 + 本卡实测 |
| R4-c | 迁移前备份存在（SandboxHermesBackup + tag） | README-BACKUP.md | ✅ 静态 S11 |
| R5-a | 三套既有 oc_wake 测试全绿（源 A-D/E + G + H 零改动） | wip 62 + deploy 29 + va 75 | ✅ 本卡实测全绿 |
| R5-b | cmd 398 + pytest 无新增失败 | cmd + pytest | ✅ 本卡 cmd 398/0 + pytest 后台 |
| 部署 | live oc_wake_check.sh md5 == repo（DPL-048） | diff/md5 比对 | ✅ 本卡复核 23936e2a 两侧一致 |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 board/DB）：

| 项 | 配置 |
|---|---|
| 被测分支 | **devPPL main @ c96c9ae**（qa-exec 若 main 已前进，先 `git log --oneline -3` 确认 c96c9ae 为祖先，避免测错对象） |
| 隔离 kanban.db | test_watchdog_unify.sh 自建 $TMPT/kanban.db（复制真实 schema + DROP est/subsplit 触发器 + 清空四表）+ seed_card 注入 |
| fixture git repo | $TMPT/repo（git init -b main + pipeline/x.sh scripts/y.sh 提交）+ $TMPT/nongit（非 git 目录 fail-open 用例） |
| env 桩 | HERMES_KANBAN_DB=$KDB + SEEN_FILE=$TMPT/seen + AUTOPILOT_JOBS_JSON=$TMPT/no-jobs.json（空 jobs，源 F 不输出 paused 行） |
| 真实库只读核对 | `devppl_query.sh`（禁止裸 python3 -c 内联读 DB，tirith MEDIUM 审批门限） |
| 执行命令 | `bash scripts/test_watchdog_unify.sh`（28 断言）+ `bash scripts/test_deploy_drift.sh`（29）+ `bash scripts/test_va_backfill.sh`（75）+ `bash scripts/test_wip_progress_check.sh`（62）+ `bash scripts/test_cmd_channel.sh`（398）+ pytest 全量（后台，~10min）+ 静态核对 + 探针 + 部署 md5 比对 |
| 被测代码获取 | main 直接跑（全部已合入） |

**执行前置（qa-exec 阶段）**：
1. main 被测 commit 确认：`git log --oneline -3`（应含 c96c9ae merge）+ `git merge-base --is-ancestor c96c9ae HEAD`
2. `bash -n scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh` + 语法自检
3. 基线五套全量复跑全绿后，再执行新增探针
4. 部署漂移复核：`md5sum /workspace/devPPL/scripts/oc_wake_check.sh /root/.hermes/profiles/orchestrator/scripts/oc_wake_check.sh` → 两侧应一致 23936e2a8cd66aee2fb27f5603bcca8f

---

## 3. 基线回归（本卡 D1 已独立实测）

| 测试 | 断言数 | 本卡实测 | qa-exec 要求 |
|------|:---:|:---:|:---:|
| test_watchdog_unify.sh | 28 | **PASS=28 FAIL=0**（2026-08-16 实测，T1-T9 全绿） | 复跑确认全绿 |
| test_deploy_drift.sh | 29 | **PASS=29 FAIL=0**（2026-08-16 实测） | 复跑确认全绿 |
| test_va_backfill.sh | 75 | **PASS=75 FAIL=0**（2026-08-16 实测） | 复跑确认全绿 |
| test_wip_progress_check.sh | 62 | **PASS=62 FAIL=0**（2026-08-16 实测） | 复跑确认全绿 |
| test_cmd_channel.sh | 398 | **PASS=398 FAIL=0**（2026-08-16 实测） | 复跑确认全绿 |
| pytest tests/ | 281/8/1 | **281 passed / 8 failed / 1 error（711.46s，失败集逐条对照存量清单全部一致，零新增失败）** | 后台复跑对照基线，**零新增失败** |

### 3.1 本卡 D1 实测摘要（2026-08-16）

| 项 | 结果 |
|---|---|
| test_watchdog_unify.sh | **28 PASS / 0 FAIL**（独立复跑，T1-T9 全绿） |
| test_deploy_drift.sh | **29 PASS / 0 FAIL**（独立复跑） |
| test_va_backfill.sh | **75 PASS / 0 FAIL**（独立复跑） |
| test_wip_progress_check.sh | **62 PASS / 0 FAIL**（独立复跑） |
| test_cmd_channel.sh | **398 PASS / 0 FAIL**（独立复跑） |
| pytest tests/ | **281 passed / 8 failed / 1 error（711.46s）** — 失败集 9 项与存量基线（t_4436b52e/t_56ab5309/t_e7d69f20 WIP 记录）逐条一致，**零新增失败** |
| 探针 P1/P2/P3/P3b/P4 | **8/8 PASS**（scripts/qa_dpl061_probes.sh，§5） |
| 静态 S1-S12 | 全过（§4） |
| 部署漂移复核 | live md5 == repo md5 == 23936e2a ✅ |

---

## 4. 静态核查（S1-S12，本卡已全部通过）

| # | 核查点 | 实测证据 |
|---|--------|---------|
| S1 | 头注释源清单 A-H → A-K（三源均标注 [DPL-061]） | oc_wake_check.sh L31/L36/L42（I/J/K 注释）+ 代码块 L443/467/492 |
| S2 | 源 I：查询条件 ikey LIKE discover-est-% OR discover-qa-est-% AND status != 'archived'；src 为空（前缀本身）跳过；源卡 EXISTS 跳过；一次性键 ghost-card:<tid> | L449-463 |
| S3 | 源 J：git status --porcelain -- pipeline/ scripts/；**rstrip 修复**（L478 注释说明 strip 会截断 tracked 首行路径）；D10 完整文件列表 | 分隔进 sha1 前8；展示截前 5；fail-open（D15）非 git/异常视为干净 | L475-490 |
| S4 | 源 K：status='running' AND started_at NOT NULL AND age > thr；D16 无 started_at 跳过；D3 B 重叠排除（hb_stale AND claim_dead）；D13 按时长降序排序 | L499-529 |
| S5 | seen 写回：一次性键 ghost-card:/stuck-running-long: **不进**跳过名单（走 out 行自动解析）；头注释明确警示 | L543-544 + L551 跳过名单不含两者 |
| S6 | 状态型键 main-dirty **进**跳过名单 + main_dirty_new_keys 声明/追加/底部写回 | L473/L487/L551/L560 |
| S7 | D3 互补：K 排除 B 已覆盖（hb_stale AND claim_dead → continue） | L514-515 |
| S8 | D12 源 K 不标「疑似卡死」，只展示心跳年龄（<1 分钟前 / N 分钟前 / 无心跳） | L519-523 |
| S9 | 归档：scripts/archive/ 4 文件在 main（git ls-tree 确认）+ 旧路径 scripts/ 下 0 残留 | git ls-tree main + 实测目录 |
| S10 | cron：infomanager jobs.json 无 6b695ac1e290（0 匹配）；orchestrator f2aa32251adc 保留 | 本卡实测 grep |
| S11 | 备份：SandboxHermesBackup/devppl-scripts-backup-20260816/ 8 脚本 + README + tag backup-pre-watchdog-unify-20260816 | 本卡实测 ls + git tag |
| S12 | 部署漂移 F1 闭环：live oc_wake_check.sh md5 == repo（23936e2a） | 本卡实测 md5sum 两侧一致 |

---

## 5. 独立探针（P1-P5，P1/P2/P3/P3b/P4 本卡已实测 8/8 PASS）

| # | 探针 | 方法 | 预期 | D1 实测 |
|---|------|------|------|:---:|
| P1 | 源 I 无源卡段边界：ikey 恰为前缀本身（discover-est- 无尾段）→ 不误报 | temp 库 seed_card ikey=discover-est-（无源卡 id），run_wake fresh seen | 无 [ghost-card] 输出（L454-456 src 为空 continue） | ✅ PASS |
| P2 | 源 J rstrip 修复回归：tracked 修改路径首字符不丢（T5b 捕获的 strip→rstrip bug 不复发） | T5b 既有 dirty2.sh 断言 + 补一例 tracked 修改（git add 后未 commit）路径含首字符完整 | [main-dirty] 行含完整路径（如 scripts/dirty.sh 而非 cripts/dirty.sh） | ✅ PASS |
| P3 | 源 K 无心跳分支：running + started_at 16min 前 + last_heartbeat_at=NULL + claim 仍有效（非 B 重叠）→ 输出含「无心跳」 | seed_card claim_expires=3600 不传 last_heartbeat_at，run_wake | [stuck-running-long] 行含「无心跳」 | ✅ PASS |
| P3b | 源 K D3 B 重叠边界：last_heartbeat_at=NULL AND claim_expires=NULL → B 优先排除 | seed_card 两字段均缺，run_wake | 无 [stuck-running-long] 输出（D3 正确排除） | ✅ PASS |
| P4 | 源 K 降序：多卡不同时长 → 输出按已跑时长降序（D13） | seed 2 卡（30min / 16min），run_wake 断言行序 | 30min 卡在前、16min 卡在后 | ✅ PASS |
| P5 | 真实库只读冒烟：live board 跑 oc_wake_check 不崩、不写卡 | `SEEN_FILE=$TMPT/seen bash scripts/oc_wake_check.sh /workspace/devPPL 2>&1`（只读；HERMES_KANBAN_DB 不覆盖 → 真实库） | exit 0 / 无异常 / 不创建任何卡；输出含或不含 [ghost-card]/[main-dirty]/[stuck-running-long] 均可（按 live 实际状态） | qa-exec 执行 |

> P5 注意：**SEEN_FILE 必须指向 temp**（防真实 seen 文件被写入影响线上幂等）；HERMES_KANBAN_DB 保持真实库（只读连接 mode=ro，脚本不写卡）。与 qa_dpl060_probes.sh P5 教训一致（unset HERMES_KANBAN_DB 防 temp 库泄漏伪影）。

---

## 6. 分级标准对照（qa-finding-classification.md v1.0）

- 若 qa-exec 发现「源 I 幽灵卡误报（源卡存在仍输出）/漏报（源卡缺失不输出）且无 seen 键落盘」类缺陷 → 用户可感知（OC 巡检信号错误/丢失）+ 功能阻断（幽灵卡污染统计不可见）+ 无 workaround → **BLOCKER**（对照标准 §5 表 BLOCKER 行）。
- 若发现「源 J 状态型键哈希与展示不一致（如 rstrip 未修复导致路径截断）」→ 用户可感知 + 功能阻断（哈希错误 → 集合变化不重报 → 抢 main 风险漏检）+ 无 workaround → **BLOCKER**（T5b 已捕获该 bug 且 S2 已修；qa-exec 确认不复发）。
- 若发现「源 K 输出格式与 PRD 略有出入（如心跳展示格式）」→ 用户可感知 + 不阻断（告警仍有效）+ workaround（人读输出理解）→ **MINOR**。
- 若发现「归档文件保留只读位/权限与预期不符」→ 不阻塞、不劣化 → **SUGGESTION**。

---

## 7. 工作量评估与拆卡决策（任务 body 要求）

### 7.1 评估依据

| 阶段 | 内容 | 预计轮数 |
|------|------|:---:|
| ① 前置检查 | main commit 确认 + bash -n + 部署 md5 复核（3 项） | 1 |
| ② test_watchdog_unify.sh | 28 断言（实测 <1min/遍，可能 2 次迭代） | 1-2 |
| ③ test_deploy_drift.sh | 29 断言 | 1 |
| ④ test_va_backfill.sh | 75 断言 | 1-2 |
| ⑤ test_wip_progress_check.sh | 62 断言 | 1 |
| ⑥ test_cmd_channel.sh | 398 断言（~80s） | 1-2 |
| ⑦ pytest 全量 | 281/8/1 存量基线（实测 ~10min，后台跑 + 对照） | 2-3 |
| ⑧ 静态核对 | S1-S12 逐项（本卡已跑通，qa-exec 复验成本低） | 1-2 |
| ⑨ 独立探针 | P1-P5（P2 rstrip 回归 / P3 无心跳 / P4 降序 / P5 真实库冒烟为新增） | 2-3 |
| ⑩ AC 核对 + 报告 | R1-R5 逐项核对 + 写 test_report.md + [PRODUCES]/[CLAIM] + 飞书推送 | 2-3 |
| **合计** | | **13-19（中位 16）** |

> 校准说明：本任务为**单仓已合入 main**（无 mem007 的双仓/未合入成本），dev 已交付完整测试体系（T1-T9 28 断言），VA 已独立复核 16/16 PASS，QA 主要是**独立复跑 + 静态核对 + 少量边界探针 + 部署漂移复核**。对比 DPL-060 QA-D1（15-21 中位 18 不拆），本卡测试体系更完整（28 断言覆盖三源正负例 + T9 归档），预计轮数略低。按 DPL-018 校准经验（QA 执行偏差 +20-30%），诚实区间 **13-19 轮（中位 16）**。

### 7.2 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | **13-19 轮（中位 16）≤ 20 轮阈值 → 不拆**（上限 19 含 pytest 后台等待与探针调试，qa-exec 单卡可吸收：pytest 后台跑与静态/探针并行） |
| 模块依赖 | 全部验收共享同一批基线（watchdog_unify 28 + deploy 29 + va 75 + wip 62 + cmd 398）与同一被测对象（main @ c96c9ae）；静态/探针/AC 核对均为独立只读操作，无串行数据依赖 |
| 并行收益 | 无——单被测对象 + 共享基线环境，拆卡只引入 merge/交接成本 |
| 兜底 | 若 qa-exec 实际执行中发现 pytest 基线调试或探针调试成本超预期，可在执行卡内按建卡铁律拆职责内子卡（assignee=game-qa，parents 挂当前卡） |

**决策：不拆卡（[QA-SUB-SPLIT] 1，单张 QA 执行子卡由 autopilot 按链自动建）。**

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | qa-exec 时 main 已前进（其它链 merge） | 被测对象变化 | 执行前置确认 c96c9ae 为祖先；DPL-061 相关文件用 git log 确认未被动过 |
| R2 | pytest 全量 ~10min 超长 | 单轮迭代耗时 | 后台跑 + 与静态/探针并行；只对照存量失败集（281/8/1 的 8+1）零新增 |
| R3 | P5 真实库冒烟潜在写 seen 风险 | 触碰 live 状态文件 | SEEN_FILE env 指向 temp；只读核对不写卡；部署态由 qa-post/OC 补观测 |
| R4 | 源 K 首个线上 tick 观察依赖 cron 节奏 | 验收 4 无法即时自证 | qa-exec 记录当前状态（cron 删除 + wrapper 清理 + 备份存在）；首 tick 输出观察归 qa-post/OC |
| R5 | T9 归档存在性断言只看文件存在非空，不验内容 | 归档内容被篡改不感知 | 静态 S9 git ls-tree 确认 blob 在 main；与备份目录交叉核对字节数（7397/12883/5925/2568） |
| R6 | cmd_channel 398 断言执行时长 | 多轮迭代耗时 | 单遍全绿优先；失败定位用断言名 grep 输出 |

---

## 附：与本方案相关的既有文档

- DPL-061 PRD：`/workspace/mem-core/wiki/projects/devppl/prd/dpl061-watchdog-unify-oc-wake-check-prd.md`
- DPL-061 评估：`docs/est/t_12539484-estimate.md`
- VA 复核：t_a1d8c2a9（16/16 PASS，0 FALSIFIED）+ F1 闭环 t_5ab4b04c（live md5 23936e2a == repo）
- 归档备份：`/workspace/SandboxHermesBackup/devppl-scripts-backup-20260816/`（tag backup-pre-watchdog-unify-20260816）
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0 + `docs/standards/devppl-test-spec.md` v1.0
