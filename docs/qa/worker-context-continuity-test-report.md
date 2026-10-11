# QA 执行报告 — worker 上下文连续性（DPL-030）检查点提交+发现笔记+预算收紧+审批白名单

> 版本：v1.0 | 日期：2026-08-15 | 作者：game-qa（QA-EXEC 执行卡，独立实测）
>
> 任务卡：t_863366a3 [DEV-QA-EXEC] worker 上下文连续性（DPL-030）
> 测试方案：docs/qa/worker-context-continuity-test-plan.md（v1.0，t_07b1c297）
> 被测提交：**wt/t_7c9d1952 @ ea489fb**（DPL-030 全量 11 文件 +381/-9，**未合入 main**；main @ e714aa1）
> 分级标准：docs/standards/qa-finding-classification.md v1.0

---

## 1. 结论（TL;DR）

| 验证项 | 结果 | 证据 |
|---|---|---|
| **基线全量**（test_cmd_channel.sh） | ✅ **PASS=386 FAIL=0** | EXIT=0 / ALL TESTS PASSED（独立复跑，2026-08-15） |
| **chain_check 回归**（test_chain_check.sh） | ✅ **PASS=38 FAIL=0** | EXIT=0 / ALL TESTS PASSED |
| **静态核对 S1-S11** | ✅ **11/11 PASS** | 代码 grep 逐项，详见 §4 |
| **独立探针 P1-P6** | ✅ **6/6 PASS** | P1-P5 复验 + P6 补验（D1 待办项），详见 §5 |
| **AC-1..AC-10 逐项核对** | ✅ **10/10 PASS** | 与 VA（t_74724cf6）15/15 VERIFIED 交叉印证，详见 §6 |
| **被测对象确认** | ✅ merge-base 成立 | main @ e714aa1 未含 DPL-030；FF 链 5992dab→ea489fb 确认 |

**结论：DPL-030 实现通过 QA 执行验收。0 BLOCKER / 0 MAJOR / 0 MINOR；2 项观察（OBS-1 继承、OBS-2 新增）。发布门禁满足，可放行 merge 回 main。**

---

## 2. 执行前置（§2 要求）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | 被测分支确认 | `git log main -1` = e714aa1（BKP-004，无 DPL-030 commit）；`git merge-base --is-ancestor e714aa1 main` = YES；被测 commit = **ea489fb @ wt/t_7c9d1952** | ✅ |
| P-2 | FF 关系 | `git merge-base --is-ancestor 5992dab ea489fb` = YES（S2→S3 FF 链）；`git diff --stat e714aa1 ea489fb` = **11 文件 +381/-9**（与方案 §0 一致） | ✅ |
| P-3 | py_compile | `python3 -m py_compile pipeline/constants.py pipeline/cmd_chain.py pipeline/discover.py` → OK | ✅ |
| P-4 | 工作树干净 | 被测 worktree `git status --short` 为空（测试自隔离 $TMPT，未污染仓库） | ✅ |
| P-5 | 零改动确认 | pipeline/state.py、pipeline/notify_check.py、scripts/cmd_channel.sh、scripts/chain_check.sh 均 UNCHANGED（git diff e714aa1..ea489fb） | ✅ |

> OBS-1 落地确认：DPL-030 未合入 main（main @ e714aa1 无 WIP/EST 常量），按 DPL-028 先例直接在被测 worktree（/workspace/devPPL/.worktrees/t_7c9d1952）执行，测试脚本自隔离 $TMPT，零写仓库。

---

## 3. 基线全量回归（AC-7）

### 3.1 test_cmd_channel.sh（386 断言）

```bash
cd /workspace/devPPL/.worktrees/t_7c9d1952 && bash scripts/test_cmd_channel.sh
```

```
════════ 结果汇总 ════════
PASS=386 FAIL=0
ALL TESTS PASSED
```

- 独立复跑（非转述研发/VA 结果），耗时约 1-2 min
- 含 DPL-030 新增断言 13 条：T59h / T60b / T60c / T60d / T63a-i（grep 实证在册，§4 S8）
- 含 DPL-018 校准回归 T64-T69 全绿（基线未破坏）

### 3.2 test_chain_check.sh（38 断言）

```
════════ 结果汇总 ════════
PASS=38 FAIL=0
ALL TESTS PASSED
```

> ⚠️ **OBS-2（新增，文档口径差）**：测试方案 header 及 §1 表写「test_chain_check.sh（41 断言）」，实测输出为 **38 断言**（PASS=38 FAIL=0，全绿无功能影响）。系方案文档断言数统计口径与实际不符（可能含 3 条合并/重复计数），**非功能缺陷**，建议 qa-post 或 OC 顺手修正方案文档口径（SUGGESTION 级，不阻塞）。

---

## 4. 静态核对 S1-S11（全部 PASS）

| # | 核对项 | 实测证据 | 结果 |
|---|--------|---------|:---:|
| S1 | constants.py 11 个 WIP_*/EST_* 常量 | WIP_SOUL_TITLE L238 / WIP_SOUL_PROFILES L239 / WIP_CHECKPOINT_MIN_ROUNDS L243 / MAX L244 / WIP_COMMIT_PREFIX L245 / WIP_NOTE_DIR L246 / WIP_BODY_LINE L247 / WIP_SOUL_PARAGRAPH L248 + EST_EFFECTIVE_RATIO L273 / EST_SPLIT_ROUNDS L274 / EST_EFFECTIVE_LINE L275 | ✅ |
| S2 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变（AC-10 红线） | constants.py L92 = 20（未动） | ✅ |
| S3 | inject_wip_rule.sh：--dry-run/--verify/--profiles + 幂等 + 段落单一源 | 脚本 L16-18 参数、L25/26/30 `cd $REPO_ROOT && PYTHONPATH=$REPO_ROOT python3 -c "from pipeline.constants import ..."`（防影子导入）、L39 SKIP 幂等、L61 VERIFY | ✅ |
| S4 | autopilot.sh [WIP 节奏] 恰好 5 处 | `grep -c "WIP 节奏"` = **5**（L159/343/383/520/665）；L362/L400 为 3 参 kanban_ensure_card 无 comment 参数（arch A-1 成立） | ✅ |
| S5 | cmd_chain.py 注入点 | `_dev_card_body` 末行 CHECKPOINT L651 + WIP L652；`_sub_card_body` 补洞 CHECKPOINT L858 + WIP L859；dev-est 块 EST_EFFECTIVE_LINE L638 | ✅ |
| S6 | discover.py est_body 注入顺序 | EST_EFFECTIVE_LINE L249 → CHECKPOINT L253 → WIP L254（顺序正确，末行=WIP） | ✅ |
| S7 | devppl_query.sh comments 子命令 | 白名单 `^t_[a-z0-9]+$` L80、只读 mode=ro L28、`ORDER BY created_at ASC` L81、usage 注册 L12/L84 | ✅ |
| S8 | test_cmd_channel.sh 新断言 13 条在册 | T59h L1944 / T60b L1971 / T60c L1972 / T60d L1973 / T63a L2016 / T63b L2017 / T63c L2018 / T63d L2019 / T63e L2020 / T63f L2021 / T63g L2043 / T63h L2045 / T63i L2046；T59e L1941 / T60a L1970 修正（末行=WIP 节奏行） | ✅ |
| S9 | .pipeline/wip/ 4 个发现笔记 + 六节模板 | t_ab9a26b3 / t_8458422f / t_5213b5dd / t_7c9d1952 共 4 个 .md；每个 grep "^## " = 6 节（上游契约/关键事实/已踩坑/当前进度/下一步/更新记录） | ✅ |
| S10 | .pipeline/ 不在 .gitignore | .gitignore 仅 ignore __pycache__/logs/notify_state.db*/pipeline_state.db*/.worktrees/ 等，无 .pipeline/ | ✅ |
| S11 | bash -n 语法 | test_cmd_channel / inject_wip_rule / autopilot / devppl_query / test_chain_check 全 OK | ✅ |

---

## 5. 独立探针 P1-P6（全部 PASS）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | WIP_SOUL_PARAGRAPH 六节模板与 PRD R2-2 一致 | constants.py L248-272：含六节标题（上游契约/关键事实/已踩坑/当前进度/下一步/更新记录）+ [WIP] 例外 + 重启首读契约 | ✅ |
| P2 | 真实 9 profile SOUL 注入现场（AC-2） | 9/9 profile SOUL.md `grep -c "WIP 检查点节奏与发现笔记"` = 1（只读；game-engine..tag-system 各 1 命中） | ✅ |
| P3 | inject_wip_rule.sh 幂等（--dry-run） | 输出：SKIP 9/9（新增=0 已存在跳过=9 缺失=0），RC=0 | ✅ |
| P4 | devppl_query.sh comments 合法 id | `comments t_74724cf6` → RC=0，输出 author/时间/body 全文，含 [VERIFIED] 2 处 | ✅ |
| P5 | devppl_query.sh comments 白名单 | `comments bad_id` → `BAD_ID: bad_id` + RC=1 | ✅ |
| P6 | autopilot 注入点完整性（A-1 补验，D1 待办） | [WIP 节奏] 恰 5 处（L159/343/383/520/665）；L362（qa-d1）/L400（qa-d2）`kanban_ensure_card` 仅 3 参（title/assignee/idempotency-key），无 comment 参数 → 非注入点，arch A-1 结论复验成立 | ✅ |

---

## 6. AC-1..AC-10 逐项核对（与 VA 交叉印证）

| AC | 验收要点 | QA-EXEC 证据 | 结果 |
|----|---------|-------------|:---:|
| AC-1 | constants.py 新增 WIP_SOUL_* / WIP_BODY_LINE / EST_* 常量 | 静态 S1（11 常量在册 L238-275） | ✅ |
| AC-2 | inject_wip_rule.sh 幂等注入 9 profile，--verify 全 HIT/SKIP | 探针 P2（9/9 FOUND）+ P3（--dry-run SKIP 9/9） | ✅ |
| AC-3 | autopilot.sh 建卡 comment 含 [WIP 节奏] | 静态 S4（恰 5 处）+ 探针 P6（L362/L400 无 comment 参数） | ✅ |
| AC-4 | dev 卡 / est 卡 body 末含 WIP_BODY_LINE | 基线 T59h（DEV_HAS_WIP=True）+ T60c（est 含 WIP 节奏:）+ T63b/T63e（末行=WIP 节奏行） | ✅ |
| AC-5 | dev-est 口径含「有效轮数 × 0.7」折算指引（双入口） | 基线 T60d（discover 入口）+ T63a（cmd_chain 入口，EST_CHAIN_HAS_EFFECTIVE=True） | ✅ |
| AC-6 | devppl_query.sh 新增 comments 子命令（白名单+只读） | 基线 T63g/T63h/T63i（输出/BAD_ID/RC=1）+ 探针 P4/P5 | ✅ |
| AC-7 | test_cmd_channel.sh 全量回归 PASS | 基线 PASS=386 FAIL=0（§3.1，独立复跑） | ✅ |
| AC-8 | 结构化 claim（changed_files/tests_run/verification） | VA t_74724cf6 15/15 VERIFIED（含 4 父卡 commit@branch + 4/4 claims）；dev 卡 t_7c9d1952 done（run 895 completed） | ✅ |
| AC-9 | subsplit 子卡 body 含 WIP_BODY_LINE + CHECKPOINT_BODY_LINE | 基线 T63c/T63d/T63e（SUB_HAS_CKPT=True / SUB_HAS_WIP=True / SUB_LAST=WIP 节奏:）+ 静态 S5（L858-859） | ✅ |
| AC-10 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变（红线回归） | 基线 T63f（TH=20）+ T68b + 静态 S2（L92） | ✅ |

---

## 7. 发现汇总与分级（标准 §6 输出格式）

### 7.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR** |
| OBS-1（未合入 main） | ✅（exec 需在分支测） | ❌（FF-ready） | ✅（DPL-028 先例直测分支） | 否 | 否 | 观察项 |
| OBS-2（方案文档断言数 41 vs 实测 38） | ❌（仅内部文档口径） | ❌（0 FAIL） | ✅（以实测输出为准） | 否 | 否 | 观察项（SUGGESTION 级，不阻塞） |

### 7.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**。
- 若后续 merge 后 qa-post 发现 BLOCKER：4h 响应 + 8h 定位 + 24h 方案；MAJOR：24h 响应 + 72h 方案（按 §8 表执行）。

### 7.3 分级示例对照（标准 §5 表）

- 未发现「注入点漏注某路径」类缺陷（S4/P6 实证 5 处 + L362/L400 非注入点）→ 无 BLOCKER 触发条件。
- 未发现「WIP_BODY_LINE 文案错误」类缺陷（T59h/T60c/T63b 全绿，文案单一源 constants）→ 无 MINOR 触发条件。

### 7.4 发布门禁对照（标准 §10）

- **BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉 → 门禁满足 ✅**
- 本卡 0 BLOCKER / 0 MAJOR / 0 MINOR / 0 SUGGESTION（OBS-2 文档口径差建议顺手修，非正式发现）。

---

## 8. 结论与建议

1. **放行**：DPL-030 全量实现（constants 11 常量 / inject_wip_rule.sh / 4 路径 body 注入 / autopilot 5 处 comment / devppl_query comments 子命令 / 13 新断言）经 QA 独立实测全部成立，**可 merge 回 main**。
2. **OBS-1 处置**：qa-post 阶段须在 main 上再回归一遍（DPL-028 惯例），并核对 merge 后 386 断言仍全绿。
3. **OBS-2 处置**（建议）：修正测试方案文档中 chain_check 断言数（41→38）；不影响本次验收。
4. **机制效果确认**：真实 9 profile SOUL 已含 WIP 段（P2 9/9）、发现笔记 4 份六节模板完整（S9）、幂等注入成立（P3）——R1/R2 执行层落地闭环。

---

## 附：执行记录

- 测试命令：`bash scripts/test_cmd_channel.sh` / `bash scripts/test_chain_check.sh` / py_compile / 静态 grep / 探针 bash
- 被测 worktree：`/workspace/devPPL/.worktrees/t_7c9d1952`（HEAD=ea489fb，工作树干净）
- 独立证据：基线输出、静态 grep 行号、探针 RC 值（§3-§5）
- 发现笔记：`.pipeline/wip/t_863366a3.md`（本卡六节模板）
