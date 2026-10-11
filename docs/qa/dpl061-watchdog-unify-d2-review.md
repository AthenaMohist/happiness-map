# QA-D2 结果严重度评审报告 — FIX watchdog 统一 — oc_wake_check 吸收 stuck-15min/幽灵卡/main-dirty + 归档死脚本（DPL-061）

> 版本：v1.0 | 日期：2026-08-16 | 执行人：game-qa（QA-D2 结果严重度评审卡 t_7d8d9436）
> 上游执行报告：`docs/qa/dpl061-watchdog-unify-qa-exec-report.md`（QA-EXEC t_e682d627 @ 56e8b1c，分支 wt/t_e682d627，**未合 main**）
> 测试方案：`docs/qa/dpl061-watchdog-unify-test-plan.md`（QA-D1 t_480d0aae @ faea467，已合 main）
> 被测提交：**devPPL main @ faea467**（c96c9ae 为祖先；DPL-061 开发文件 S1 5b591f0 + S2 3b2aca9 + S3 0cf2138 全部已合入 main）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 评审性质：QA-D2 独立复验（非转述 QA-EXEC），复核分级判定 + 漏报检查 + 处置建议

---

## 0. 评审结论（TL;DR）

| 评审项 | 结果 | 证据 |
|---|---|---|
| 分级判定复核（QA-EXEC 结论 0 BLOCKER/MAJOR/MINOR + 1 SUGGESTION + OBS-1） | ✅ **复核一致** | §2 |
| 被测对象确认（main @ faea467 祖先 c96c9ae） | ✅ c96c9ae 为 main 祖先且 DPL-061 开发文件零触碰 | §1.3 |
| 语法前置（bash -n 7/7） | ✅ **7/7 OK** | §1.3 |
| 部署漂移复核（DPL-048） | ✅ live md5 == repo md5 == 23936e2a | §1.3 |
| 基线五套独立复跑（同一 main 对象） | ✅ **592/0**（28+29+75+62+398），均 EXIT=0 | §3 |
| pytest 全量独立复跑（对照存量基线） | ✅ **281 passed / 8 failed / 1 error**（646.73s）——失败集 9 项与存量清单逐条一致，**零新增** | §3.1 |
| 静态核对 S1-S12 复验 | ✅ **12/12 PASS**（独立读码） | §4 |
| 探针 P1-P5 复验（QA-EXEC 探针重跑） | ✅ **9/9 PASS**（P1-P4 8/8 + P5 真实库只读冒烟） | §5.1 |
| 漏报探针 A-J（QA-D2 新增） | ✅ **30/30 PASS**（无漏判） | §5.2 |
| AC R1-R5 交叉核对 | ✅ **R1 4/4 + R2 3/3 + R3 3/3 + R4 3/3 + R5 2/2 = 15/15** | §6 |
| 漏报检查（QA-EXEC 是否漏判） | ✅ **无漏报**（A-J 补充探针全部通过） | §5.2/§7 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §8 |

**评审结论：QA-EXEC 测试报告分级判定准确、证据链完整、无漏报、无错判。DPL-061 四层机制（源 I 幽灵卡 / 源 J main-dirty / 源 K stuck-long / R4 归档+cron 迁移）经 QA-D2 独立复验全部成立。结果评审通过（review_pass），可放行后续 qa-post。** 注：QA-EXEC 报告（wt/t_e682d627 @ 56e8b1c）尚未合入 main，落地由 OC 执行；本卡在同一 main 对象（faea467）独立复验全部证据链。

---

## 1. 评审对象与方法

### 1.1 评审对象

- QA-EXEC 报告：`docs/qa/dpl061-watchdog-unify-qa-exec-report.md`（v1.0，164 行，t_e682d627 @ 56e8b1c，wt/t_e682d627 分支）
- 报告核心声明：基线五套 592/0、pytest 281/8/1 与存量一致零新增、静态 S1-S12 12/12、探针 P1-P5 9/9、R1-R5 15/15 全部成立、0 BLOCKER/MAJOR/MINOR + 1 SUGGESTION（SUG-1 过期 .jobs_*.tmp）+ OBS-1（源 K 首个线上 tick → qa-post/OC）

### 1.2 评审方法（独立复验，不转述）

| # | 方法 | 说明 |
|---|------|------|
| M1 | 基线五套独立复跑 | 本卡在 main @ faea467 重新执行 watchdog_unify/deploy/va/wip/cmd 五套（与 QA-EXEC 同一被测对象，双重覆盖） |
| M2 | pytest 全量独立复跑 | 后台全量 + 失败集逐条对照存量清单（8+1），确认零新增 |
| M3 | 静态独立核对 | 独立读码复验 S1-S12（12 项） |
| M4 | 探针独立复验 + 漏报探针 | P1-P4 重新执行（QA-D1 探针脚本）+ P5 真实库只读冒烟 + 漏报探针 A-J 新增（30 断言） |
| M5 | AC 交叉核对 | R1-R5 逐项对照验收要点（PRD §5 + test-plan §1.1 + EXEC 报告 §5） |
| M6 | 分级复核 | 对照标准 §1.2 判定公式，逐项复核 QA-EXEC 的 0 缺陷 + SUG-1 + OBS-1 判定 |

### 1.3 被测对象确认（P-1..P-5 复验）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | devPPL main HEAD | `git log main -1` = faea467（merge t_480d0aae QA-D1） | ✅ |
| P-2 | c96c9ae 为祖先 | `git merge-base --is-ancestor c96c9ae main` = YES（S1/S2/S3 全部在 main） | ✅ |
| P-3 | DPL-061 开发文件零触碰 | `git log --oneline c96c9ae..main -- scripts/oc_wake_check.sh scripts/test_watchdog_unify.sh scripts/archive/` = 空（仅 fbb8c27 触碰 qa_dpl061_probes.sh = D1 新增产物，非开发代码） | ✅ |
| P-4 | 语法前置 | `bash -n oc_wake_check.sh/test_watchdog_unify.sh/qa_dpl061_probes.sh/test_deploy_drift.sh/test_va_backfill.sh/test_wip_progress_check.sh/test_cmd_channel.sh/qa_dpl061_d2_probes.sh` = **8/8 OK** | ✅ |
| P-5 | 部署漂移复核 | `md5sum scripts/oc_wake_check.sh /root/.hermes/profiles/orchestrator/scripts/oc_wake_check.sh` 两侧一致 **23936e2a8cd66aee2fb27f5603bcca8f** | ✅ |
| P-6 | 工作树隔离 | 本卡在 wt/t_7d8d9436 执行，探针全部 $TMPT 隔离；未触碰 main 工作树写操作 | ✅ |

---

## 2. 分级判定复核（标准 §1.2 公式逐项对照）

### 2.1 QA-EXEC 结论 vs 本卡复核

| QA-EXEC 判定 | 本卡复核 | 复核依据 |
|------|:---:|------|
| 0 BLOCKER | ✅ 一致 | 无用户可感知+功能阻断+无 workaround 组合（§2.2）；无安全漏洞；无数据一致性；无性能退化；无 OOM/崩溃 |
| 0 MAJOR | ✅ 一致 | 无用户可感知+功能阻断但有 workaround/体验严重退化；无 XSS/CSRF/SSRF；无数据一致性；无性能退化 |
| 0 MINOR | ✅ 一致 | 无用户可感知且影响核心任务完成的问题（基线五套 + pytest + 探针 + 静态全绿） |
| 1 SUGGESTION（SUG-1 过期 .jobs_*.tmp） | ✅ 一致 | 用户不可感知（cron 读 jobs.json，tmp 不参与调度；仅 grep 审计假阳性），不阻断不劣化 → SUGGESTION（标准 §5 表 SUGGESTION 行） |
| OBS-1（源 K 首个线上 tick 输出） | ✅ 一致 | 依赖 cron 节奏（15m），qa-exec 已记录现状（cron 删 + wrapper 清 + 备份在 + P5 实测无 stuck 命中）；最终线上确认归 qa-post/OC |

### 2.2 判定公式逐项（标准 §1.2）

| 条件 | 是否触发 | 证据 |
|------|:---:|------|
| 安全漏洞（认证绕过/数据泄露/远程注入） | 否 | oc_wake_check 只读 sqlite mode=ro（L93）+ git status 只读 + 无网络面；D2 探针全在 temp 库/隔离 repo 执行 |
| 用户可感知 + 功能阻断 + 无 workaround | 否 | 三源机制（I/J/K）经基线 28/0 + 探针 A-J 30/30 全过，无异常输出/漏报/误报 |
| 用户可感知 + 功能阻断但有 workaround | 否 | 同上一行 |
| 数据一致性 | 否 | seen 写回三类键（一次性 I/K + 状态型 J）互不干扰（探针 I1-I9） |
| 性能退化 | 否 | 源 K 降序 O(n log n)；pytest 646.73s 与存量基线同量级（D1 711s / EXEC 589s 波动） |

---

## 3. 基线五套独立复跑（main @ faea467，非转述）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1 | test_watchdog_unify.sh（T1-T9，28 断言） | `bash scripts/test_watchdog_unify.sh` | **PASS=28 FAIL=0**（EXIT=0） |
| G2 | test_deploy_drift.sh（29 断言） | `bash scripts/test_deploy_drift.sh` | **PASS=29 FAIL=0**（EXIT=0） |
| G3 | test_va_backfill.sh（75 断言） | `bash scripts/test_va_backfill.sh` | **PASS=75 FAIL=0**（EXIT=0） |
| G4 | test_wip_progress_check.sh（62 断言） | `bash scripts/test_wip_progress_check.sh` | **PASS=62 FAIL=0**（EXIT=0） |
| G5 | test_cmd_channel.sh（398 断言） | `bash scripts/test_cmd_channel.sh` | **PASS=398 FAIL=0 / ALL TESTS PASSED**（EXIT=0） |
| **合计** | | | **592 PASS / 0 FAIL** |

### 3.1 pytest 全量结果（对照存量基线 281/8/1）

- 命令：`cd /workspace/devPPL/.worktrees/t_7d8d9436 && python3 -m pytest tests/ -q --tb=no -p no:cacheprovider`（后台，**646.73s**）
- 结果：**281 passed / 8 failed / 1 error** — 与存量基线 **完全一致**（QA-EXEC 实测 281/8/1，588.73s；D1 实测 281/8/1，711.46s；DPL-060 实测 281/8/1）
- 失败集逐条对照存量清单（同一 9 项）：
  - `test_memory_middleware_qa.py::test_tc19_blast_radius_engine` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc20_gai_links_adapter` — 存量 ✅
  - `test_memory_middleware_qa.py::test_tc23_drift_engine` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved` — 存量 ✅
  - `test_slice2_d1_qa.py::TestRound4_Boundary::test_BE01_empty_branches_default_advance` — 存量 ✅
  - `test_P2-02_full.py::test`（ERROR，模块顶层 `def test(...)` 误收集 fixture error）— 存量 ✅
- **结论：零新增失败（R5-b 成立）**

---

## 4. 静态核对 S1-S12 复验（独立读码/实测，12/12 PASS）

| # | 核对项 | 证据（文件:行，main @ faea467） | 结果 |
|---|---|---|---|
| S1 | 头注释源清单 A-H → A-K（三源均标注 [DPL-061]） | oc_wake_check.sh L31/L36/L42 + 代码块 L443/467/492 | ✅ |
| S2 | 源 I：查询 ikey LIKE discover-est-% OR discover-qa-est-% AND status != 'archived'；src 为空跳过；源卡 EXISTS 跳过；一次性键 ghost-card:<tid> | oc_wake_check.sh L448-463（L451 查询 / L454 src 替换 / L455-456 空跳过 / L457-459 EXISTS 跳过 / L460 key） | ✅ |
| S3 | 源 J：git status --porcelain -- pipeline/ scripts/；**rstrip 修复**（L478 注释说明 strip 截断 tracked 首行路径）；D10 完整列表进 sha1 前8；展示截前 5；fail-open（D15） | oc_wake_check.sh L475-490（L476 白名单 / L478 rstrip / L484 哈希 / L488 展示前5 / L489-490 fail-open） | ✅ |
| S4 | 源 K：status='running' AND started_at NOT NULL AND age > thr；D16 无 started_at 跳过；D3 B 重叠排除；D13 按时长降序 | oc_wake_check.sh L499-529（L502 running / L505-506 NULL 跳过 / L508 >thr / L514-515 B 重叠 / L528 降序） | ✅ |
| S5 | seen 写回：一次性键 ghost-card:/stuck-running-long: **不进**跳过名单（走 out 行自动解析）；E/G/H/J 状态型键走 *_new_keys | oc_wake_check.sh L545-561（L551 排除名单不含 ghost/stuck；L554-561 *_new_keys） | ✅ |
| S6 | 状态型键 main-dirty **进**跳过名单 + main_dirty_new_keys 声明/追加/底部写回 | oc_wake_check.sh L473/L487/L551/L560 | ✅ |
| S7 | D3 互补：K 排除 B 已覆盖（hb_stale AND claim_dead → continue） | oc_wake_check.sh L512-515 | ✅ |
| S8 | D12 源 K 不标「疑似卡死」，只展示心跳年龄（<1 分钟前 / N 分钟前 / 无心跳） | oc_wake_check.sh L519-523 | ✅ |
| S9 | 归档：scripts/archive/ 4 文件在 main + 旧路径 0 残留 | `git ls-tree main --name-only scripts/archive/`（4 文件）+ `ls scripts/watch_board.sh ...`（No such file ×4）；字节 7397/12883/5925/2568 与备份一致 | ✅ |
| S10 | cron：infomanager jobs.json 无 6b695ac1e290（0 匹配）；orchestrator f2aa32251adc 保留 | `grep -c 6b695ac1e290 /root/.hermes/profiles/infomanager/cron/jobs.json` → 0；`grep -o f2aa32251adc orchestrator/cron/jobs.json` → 1；live infomanager/scripts 无 oc_stuck/watch_board/watch_dpl 残留（0） | ✅ |
| S11 | 备份：SandboxHermesBackup/devppl-scripts-backup-20260816/ 8 脚本 + README + wrapper.bak + tag | `ls`（autopilot/deploy_drift_check/oc_stuck_watchdog/oc_wake_check/stuck_check/watch_board/watch_dpl_chains + wrapper.bak + README-BACKUP.md）+ `git tag`（backup-pre-watchdog-unify-20260816） | ✅ |
| S12 | 部署漂移 F1 闭环：live md5 == repo（23936e2a） | `md5sum` 两侧一致（唯一 md5 计数 = 1） | ✅ |

**合计 12/12 PASS（与 QA-EXEC 一致，全部在 main @ faea467 核实）。**

---

## 5. 探针复验 + 漏报探针（39/39 PASS）

### 5.1 QA-EXEC 探针 P1-P5 复验（本卡独立执行）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | 源 I 无源卡段边界（ikey 恰为前缀本身）→ 不误报 | 复验：无 [ghost-card] 输出 | ✅ |
| P2 | 源 J rstrip 修复回归（tracked 修改路径完整） | 复验：路径完整 scripts/dirty.sh，无截断 ×3 断言 | ✅ |
| P3 | 源 K 无心跳分支（claim 仍有效）→ 输出含「无心跳」 | 复验：行含「无心跳」 | ✅ |
| P3b | 源 K D3 B 重叠边界（hb=NULL AND claim=NULL → B 优先） | 复验：无 stuck-running-long 输出 | ✅ |
| P4 | 源 K 降序（D13） | 复验：30min 在前、16min 在后 | ✅ |
| P5 | 真实库只读冒烟 | 复验：**exit 0**；输出 live 状态（wip-check / code-not-in-main / autopilot-cron，无 ghost-card/main-dirty/stuck-running-long 命中）；SEEN_FILE=temp 仅写 temp；真实库未触碰 | ✅ |

**P1-P5 复验：PASS=9 FAIL=0（与 QA-EXEC 一致）。**

### 5.2 漏报探针（QA-D2 新增，检查 QA-EXEC 是否漏判）——30/30 PASS

> 独立编写 `scripts/qa_dpl061_d2_probes.sh`（A-J，30 断言），针对 test-plan §5 / QA-EXEC P1-P5 之外的边界。

| # | 探针 | 目标 | 实测 | 结果 |
|---|------|------|------|:---:|
| A | 源 I 长标题（>50 字符）→ 输出截断到 50 不崩 | L463 title[:50] 边界 | [ghost-card] t_ghost_long 命中 + 不含完整长标题 | ✅ |
| B | 源 I src 源卡 archived → exists 仍命中 → 不误报 | 源卡存在即跳过（不看 status） | 无 ghost-card | ✅ |
| C | 源 J tracked 删除（" D path" 前导空格）→ rstrip 保留 → 路径完整 | 删除状态路径提取 | [main-dirty] 行路径 = pipeline/x.sh（无截断） | ✅ |
| D | 源 J 白名单外目录脏（docs/）→ 不误报 | D2 只查 pipeline/ scripts/ | 无 [main-dirty] | ✅ |
| E | 源 J 6 个 dirty 文件 → 展示截前 5 + 哈希基于完整列表 | D10 哈希 vs 展示截断 | 展示含 dirty1/5 不含 dirty6；seen 哈希含 dirty6 | ✅ |
| F | 源 K 心跳 55s 前 → "<1 分钟前" | D12 边界 | 行含「心跳 <1 分钟前」 | ✅ |
| G | 源 K 心跳 65min 前 → "65 分钟前" | D12 分钟格式 | 行含「心跳 65 分钟前」 | ✅ |
| H | 源 K 三卡降序（45/30/16min）→ 行序正确 | D13 多卡 | 45 < 30 < 16 行序 + 45 分钟展示 | ✅ |
| I | 混合 seen：ghost + stuck（一次性）+ main-dirty（状态键）同跑 → 三类键互不干扰；同 seen 重跑全去重 | 写回隔离（I/K 走 out 解析、J 走 *_new_keys） | I4-I6 三类键全落盘；I7-I9 重跑全去重 | ✅ |
| J | 源 I 双前缀同跑（discover-est + discover-qa-est）→ 同时命中 | 双前缀互不干扰 | 两卡均命中 + seen 双键落盘 | ✅ |

**漏报检查结论：QA-EXEC 未漏判任何缺陷；QA-D2 补充探针 A-J 全部通过（30/30）。**

---

## 6. R1-R5 交叉核对（与 QA-EXEC 报告交叉印证）

| # | 验收要点 | 本卡证据 | 结果 |
|----|---------|---------|:---:|
| R1-a | ikey=discover-est-* 且源卡不存在 → 输出 `[ghost-card] <tid> 源卡 <src> 不存在` | 基线 T1a/T1b（G1 28/0）+ 静态 S2 + 探针 A/J | ✅ |
| R1-b | 源卡存在 → 不输出；status=archived → 不输出（负例） | 基线 T2a/T2c + 探针 B | ✅ |
| R1-c | qa 前缀 discover-qa-est-* → 命中 | 基线 T2b + 探针 J | ✅ |
| R1-d | 重跑不重复报告（一次性键 ghost-card:<tid> 落盘） | 基线 T3a/T3b + 静态 S5 + 探针 I4 | ✅ |
| R2-a | 脏 repo（pipeline/ scripts/ 未提交）→ 输出 `[main-dirty]` + 前 5 文件 | 基线 T4a/T4b + 静态 S3 + 探针 C/E | ✅ |
| R2-b | seen 含 main-dirty:<完整列表 sha1 前8>（状态型键 D10） | 基线 T4c + 静态 S6 + 探针 E5 | ✅ |
| R2-c | 干净 repo → 不输出；集合变化 → 重报；非 git → fail-open exit 0 | 基线 T5a/T5b/T5c + 探针 D（白名单外不报） | ✅ |
| R3-a | running + started_at 16min 前 + 心跳新鲜 → `[stuck-running-long] 已跑 16 分钟（心跳 N 分钟前）` | 基线 T6a/T6b/T6c + 静态 S4 + 探针 F/G | ✅ |
| R3-b | 14min 未超阈值 → 不输出；B 重叠（hb_stale AND claim_dead）→ K 不输出 | 基线 T7a/T7b + 静态 S7 | ✅ |
| R3-c | 重跑不重复报告（一次性键 stuck-running-long:<tid> 落盘） | 基线 T8a/T8b + 探针 I5 | ✅ |
| R4-a | scripts/archive/ 4 文件存在且非空；旧路径消失 | 基线 T9 + 静态 S9 | ✅ |
| R4-b | infomanager cron 6b695ac1e290 已删；orchestrator f2aa32251adc 保留；wrapper 清理 | 静态 S10（jobs.json 0 匹配 + orchestrator 保留 + live 无残留） | ✅ |
| R4-c | 迁移前备份存在（SandboxHermesBackup + tag） | 静态 S11 | ✅ |
| R5-a | 三套既有 oc_wake 测试全绿（源 A-D/E + G + H 零改动） | wip 62/0 + deploy 29/0 + va 75/0 | ✅ |
| R5-b | cmd 398 + pytest 无新增失败 | cmd 398/0 + pytest 281/8/1 零新增 | ✅ |
| 部署 | live oc_wake_check.sh md5 == repo（DPL-048） | md5 23936e2a 两侧一致 | ✅ |

**R1-R5 15/15 全部成立（与 QA-EXEC 一致），0 项不通过。**

---

## 7. 发现汇总与分级（标准 §6 输出格式要求）

### 7.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR** |
| SUG-1（infomanager cron 目录残留 2 个过期 .jobs_*.tmp） | ❌（cron 读 jobs.json，tmp 不参与调度；仅 grep 审计假阳性） | ❌ | ✅（OC 例行清理） | 否 | 否 | **SUGGESTION**（不阻塞发版） |
| OBS-1（源 K 首个线上 tick 输出观察） | ✅（线上确认依赖 cron 节奏） | ❌（qa-exec 已记录现状：cron 删 + wrapper 清 + 备份在 + P5 无 stuck 命中） | ✅（qa-post/OC 补观测） | 否 | 否 | **观察项**（非缺陷） |

### 7.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**（QA-EXEC 与 QA-D2 均无发现）。
- SUG-1 为 SUGGESTION，不进入 SLA 通道，建议随 OC 例行清理。
- OBS-1 为观察项，由部署态 qa-post/OC 补观测。

### 7.3 分级示例对照（标准 §5 表）

- 未发现「源 I 幽灵卡误报/漏报且无 seen 键落盘」类 BLOCKER（基线 T1-T3 正负例 + 探针 A/B/J 全过）。
- 未发现「源 J rstrip 未修导致哈希错误 → 集合变化不重报 → 抢 main 漏检」类 BLOCKER（基线 T5b + 探针 C/E 全过）。
- 未发现「源 K 输出格式与 PRD 出入（心跳展示）」类 MINOR（基线 T6b/c + 探针 F/G 输出符合 D12）。
- 未发现「归档文件保留只读位/权限异常」类 SUGGESTION（S9 字节数与备份一致）。

---

## 8. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。DPL-061 结果评审通过，可进入 qa-post。** 注：被测对象 main @ faea467 与 QA-EXEC（main @ 44bbcfd 的后续 QA-D1 merge faea467，DPL-061 开发文件零触碰）等价；本卡在同一开发对象上独立复跑全部证据链，qa-post 阶段只需确认后续 merge 未引入回归。

---

## 9. 评审建议

1. **放行**：QA-EXEC 报告分级判定准确、证据链完整、无漏报无错判。DPL-061 可继续 qa-post 流程。
2. **SUG-1 处置（同 QA-EXEC）**：infomanager cron 目录 2 个过期 .jobs_*.tmp（含已删 cron id 6b695ac1e290）随 OC 例行清理（非阻塞，不建 FIX 卡）。
3. **OBS-1 处置（同 QA-EXEC）**：源 K 首个线上 tick 输出由部署态 qa-post/OC 补观测（cron 15m 节奏）。
4. **落地跟进**：QA-EXEC 报告（wt/t_e682d627 @ 56e8b1c）与 QA-D2 评审报告（wt/t_7d8d9436）由 OC 逐张 merge 进 main。
5. **无新增缺陷/观察**：QA-D2 漏报探针 A-J（30/30）全部通过，未发现 QA-EXEC 遗漏的功能缺陷或边界问题。

---

## 附：执行记录

- 独立复跑（main @ faea467）：`bash scripts/test_watchdog_unify.sh`（28/0）+ `bash scripts/test_deploy_drift.sh`（29/0）+ `bash scripts/test_va_backfill.sh`（75/0）+ `bash scripts/test_wip_progress_check.sh`（62/0）+ `bash scripts/test_cmd_channel.sh`（398/0）+ `python3 -m pytest tests/ -q --tb=no -p no:cacheprovider`（281/8/1，646.73s，零新增）
- 探针复验：P1-P4（QA-D1 脚本重跑）8/8 + P5 真实库只读冒烟 PASS；漏报探针 A-J（本卡独立编写 `scripts/qa_dpl061_d2_probes.sh`）30/30
- 静态 S1-S12 独立读码（§4）
- 只读 DB 核对：`devppl_query.sh task t_e682d627` → done（受控脚本，无内联裸读）
- 被测提交：devPPL main @ faea467（QA-D1 merge；c96c9ae 为祖先，DPL-061 开发文件零触碰）
- 本卡发现笔记：`.pipeline/wip/t_7d8d9436.md`（六节模板）
- commit：`31ffac5 [WIP] checkpoint t_7d8d9436 #1` + 最终 claim commit @ wt/t_7d8d9436
