# QA-D2 结果严重度评审报告 — worker 上下文连续性（DPL-030）

> 版本：v1.0 | 日期：2026-08-15 | 执行人：game-qa（QA-D2 结果严重度评审卡 t_cfd940c3）
> 上游执行报告：`docs/qa/worker-context-continuity-test-report.md`（QA-EXEC t_863366a3 @ ef63d3c）
> 测试方案：`docs/qa/worker-context-continuity-test-plan.md`（QA-D1 t_07b1c297 @ 89b0ca2）
> 被测提交：**wt/t_7c9d1952 @ ea489fb**（main @ e714aa1 未合入，OBS-1 复确认）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 评审性质：QA-D2 独立复验（非转述 QA-EXEC），复核分级判定 + 漏报检查 + 处置建议

---

## 0. 评审结论（TL;DR）

| 评审项 | 结果 | 证据 |
|---|---|---|
| 分级判定复核（QA-EXEC 结论 0 BLOCKER/MAJOR/MINOR） | ✅ **复核一致** | §2 |
| 基线全量独立复跑（AC-7） | ✅ **PASS=386 FAIL=0** EXIT=0（本卡独立执行） | §3.1 |
| chain_check 独立复跑 | ✅ **PASS=38 FAIL=0** EXIT=0（OBS-2 复确认） | §3.2 |
| 静态核对 S1-S11 复验 | ✅ **21/21 PASS**（独立探针脚本） | §4 |
| 探针 P1-P6 复验 + 漏报探针 A-F | ✅ **16/16 PASS** | §5 |
| AC-1..AC-10 交叉核对 | ✅ **10/10 PASS**（与 VA 15/15 VERIFIED 一致） | §6 |
| 漏报检查（QA-EXEC 是否漏判） | ✅ **无漏报**（A-F 补充探针全部通过） | §5/§7 |
| OBS-1（未合入 main）/ OBS-2（chain_check 41→38） | ✅ 复确认成立，均为观察项非缺陷 | §7 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §8 |

**评审结论：QA-EXEC 测试报告分级判定准确、证据链完整、无漏报、无错判。DPL-030 结果评审通过（review_pass），可放行后续 va-qa → merge → qa-post 流程。**

---

## 1. 评审对象与方法

### 1.1 评审对象

- QA-EXEC 报告：`docs/qa/worker-context-continuity-test-report.md`（v1.0，160 行，t_863366a3 @ ef63d3c）
- 报告核心声明：386 PASS/0 FAIL、chain_check 38/0、S1-S11 11/11、P1-P6 6/6、AC-1..AC-10 10/10、0 缺陷、2 观察（OBS-1/OBS-2）

### 1.2 评审方法（独立复验，不转述）

| # | 方法 | 说明 |
|---|------|------|
| M1 | 基线全量独立复跑 | 本卡重新执行 `test_cmd_channel.sh` / `test_chain_check.sh`（被测 worktree，自隔离 $TMPT） |
| M2 | 静态独立核对 | 独立探针脚本重新 grep 被测分支代码（21 项断言） |
| M3 | 探针独立复验 | P1-P6 重新执行 + 漏报探针 A-F 新增（verify 模式/单一源漂移/笔记入库） |
| M4 | AC 交叉核对 | AC-1..AC-10 逐项对照 VA verdict comment（t_74724cf6 [VERIFIED] 15/15） |
| M5 | 分级复核 | 对照标准 §1.2 判定公式，逐项复核 QA-EXEC 的 0 缺陷 + 2 观察判定 |

### 1.3 被测对象确认（P-1..P-5 复验）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | main HEAD | `git log main -1` = e714aa1（BKP-004，无 DPL-030） | ✅ |
| P-2 | FF 关系 | `git merge-base --is-ancestor e714aa1 ea489fb` = YES（FF-ready）；diff 11 文件 +381/-9 | ✅ |
| P-3 | py_compile | constants/cmd_chain/discover → OK（QA-EXEC 已验，本卡 bash -n + import 复验通过） | ✅ |
| P-4 | 工作树干净 | 被测 worktree `git status --short` 为空（测试隔离 $TMPT 未污染） | ✅ |
| P-5 | 零改动确认 | state.py / notify_check.py / cmd_channel.sh / chain_check.sh UNCHANGED（diff e714aa1..ea489fb 无这些文件） | ✅ |

---

## 2. 分级判定复核（标准 §1.2 公式逐项对照）

### 2.1 QA-EXEC 结论 vs 本卡复核

| QA-EXEC 判定 | 本卡复核 | 复核依据 |
|------|:---:|------|
| 0 BLOCKER | ✅ 一致 | 无用户可感知 + 功能阻断 + 无 workaround 组合（§2.2）；无安全漏洞；无数据一致性；无性能退化 ≥10x；无 OOM/崩溃 |
| 0 MAJOR | ✅ 一致 | 无用户可感知 + 功能阻断但有 workaround / 体验严重退化；无 XSS/CSRF/SSRF；无 A 级数据一致性；无性能退化 ≥3x |
| 0 MINOR | ✅ 一致 | 无用户可感知且影响核心任务完成的问题（基线 386+38 全绿，行为无异常） |
| OBS-1（未合入 main） | ✅ 观察项成立 | 用户（qa-post/merge worker）可感知但非功能阻断（FF-ready，可 merge）；有 workaround（直测分支，DPL-028 先例）；非安全/非数据一致性 → 按标准 §1.2 不构成 BLOCKER/MAJOR/MINOR |
| OBS-2（chain_check 文档 41 vs 实测 38） | ✅ 观察项成立 | 内部文档口径差：用户不可感知（0 FAIL 功能全绿）；非安全/非数据一致性 → SUGGESTION 级，不阻塞 |

### 2.2 判定公式逐项（标准 §1.2）

| 条件 | 是否触发 | 证据 |
|------|:---:|------|
| 安全漏洞（认证绕过/数据泄露/远程注入） | 否 | devppl_query 新增 comments 为只读 + 白名单（^t_[a-z0-9]+$）；inject_wip_rule 只写 SOUL.md 文本；无网络/认证面 |
| 数据一致性（S/A 级数据） | 否 | 无资金/用户基础信息数据面；改的是提示文本与查询工具 |
| 性能退化（P95 ≥10x / ≥3x） | 否 | 文本注入型改动；测试耗时未纳入生产路径 |
| OOM/崩溃 | 否 | bash 脚本 + 常量文本 |
| 概率性 bug（资金/核心功能） | 否 | 无状态机/无并发面 |

**结论：QA-EXEC 的「0 缺陷 + 2 观察项」分级判定与标准公式完全一致，无错判、无漏判。**

---

## 3. 基线全量独立复跑（AC-7）

### 3.1 test_cmd_channel.sh（386 断言）

```bash
cd /workspace/devPPL/.worktrees/t_7c9d1952 && bash scripts/test_cmd_channel.sh
```

```
════════ 结果汇总 ════════
PASS=386 FAIL=0
ALL TESTS PASSED        （EXIT=0，日志 /tmp/d2_cmdchannel.log）
```

- **独立执行**（非转述 QA-EXEC/VA），耗时 ~75s
- 含 DPL-030 新增断言 13 条（T59h/T60b-d/T63a-i）+ DPL-018 校准回归 T64-T69 全绿
- 与 QA-EXEC 386/0、VA 386/0（/tmp/dpl030_va_regression.log）三方一致

### 3.2 test_chain_check.sh（38 断言实测）

```
PASS=38 FAIL=0
ALL TESTS PASSED        （EXIT=0，日志 /tmp/d2_chaincheck.log）
```

- 独立复跑确认 **38 断言**（方案文档 header/§1/§6.1 共 4 处写 41 → OBS-2 复确认，非功能缺陷，文档口径差）
- 结论：QA-EXEC 报告 §3.2 所述 38/0 准确，OBS-2 成立

---

## 4. 静态核对 S1-S11 复验（QA 独立探针脚本，21/21 PASS）

| # | 核对项 | 实测 | 结果 |
|---|--------|------|:---:|
| S1 | constants.py 11 个 WIP_*/EST_* 常量 | grep -c = 11（WIP_SOUL_TITLE/PROFILES/MIN/MAX/COMMIT_PREFIX/NOTE_DIR/BODY_LINE/SOUL_PARAGRAPH + EST_EFFECTIVE_RATIO/SPLIT_ROUNDS/EFFECTIVE_LINE） | ✅ |
| S2 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变 | L92 `= 20`（AC-10 红线未动） | ✅ |
| S3 | inject_wip_rule.sh --dry-run/--verify/--profiles + 幂等 + 单一源 | 6 处参数匹配 + SKIP 逻辑 3 处 + `from pipeline.constants import` 3 处（cd REPO_ROOT 防影子导入） | ✅ |
| S4 | autopilot.sh [WIP 节奏] 恰 5 处 | grep -c = 5（L159/343/383/520/665） | ✅ |
| S5 | cmd_chain.py 注入点 | CHECKPOINT_BODY_LINE 3 处 + WIP_BODY_LINE 3 处 + EST_EFFECTIVE_LINE 2 处（_dev_card_body / _sub_card_body / dev-est 块） | ✅ |
| S6 | discover.py est_body 注入顺序 | EST_EFFECTIVE_LINE L249 → CHECKPOINT L253 → WIP L254（顺序正确，末行=WIP） | ✅ |
| S7 | devppl_query.sh comments 白名单 + 只读 | comments 5 处 + mode=ro 3 处 + `=~ ^t_` 白名单 6 处 | ✅ |
| S8 | test_cmd_channel.sh 新断言 13 条在册 | 14 处匹配（13 新断言 + T59e 修正） | ✅ |
| S9 | .pipeline/wip 4 个发现笔记六节模板 | 4 个 .md（t_ab9a26b3/t_8458422f/t_5213b5dd/t_7c9d1952）全含六节标题 | ✅ |
| S10 | .pipeline 不在 .gitignore | .gitignore 无 .pipeline | ✅ |
| S11 | bash -n 语法 5 脚本 | test_cmd_channel/inject_wip_rule/autopilot/devppl_query/test_chain_check 全 OK | ✅ |

**合计 21/21 PASS（11 项 × 细化断言）。**

---

## 5. 探针复验 + 漏报探针（16/16 PASS）

### 5.1 QA-EXEC 探针 P1-P6 复验（本卡独立执行）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | WIP_SOUL_PARAGRAPH 六节模板 | 六节标题全部在册（上游契约/关键事实/已踩坑/当前进度/下一步/更新记录） | ✅ |
| P2 | 真实 9 profile SOUL 注入现场 | 9/9 profile SOUL.md 含「WIP 检查点节奏与发现笔记」（game-architect..tag-system 各 1 命中） | ✅ |
| P3 | inject_wip_rule.sh --dry-run 幂等 | SKIP 9/9，RC=0 | ✅ |
| P4 | devppl_query comments 合法 id | comments t_74724cf6 → RC=0，输出 1698 字符（含 [VERIFIED]） | ✅ |
| P5 | devppl_query comments BAD_ID | bad_id → `BAD_ID: bad_id` + RC=1 | ✅ |
| P6 | autopilot 注入点完整性 | [WIP 节奏] 恰 5 处；L362（qa-d1）/L400（qa-d2）`kanban_ensure_card` 无 comment 参数 → 非注入点 | ✅ |

### 5.2 漏报探针（QA-D2 新增，检查 QA-EXEC 是否漏判）

| # | 探针 | 目标 | 实测 | 结果 |
|---|------|------|------|:---:|
| A | inject_wip_rule.sh --verify | AC-2 注入后校验模式可用 | VERIFY-OK/HIT 9/9，RC=0 | ✅ |
| B | WIP_BODY_LINE 内容双要素 | body 提示同时含 WIP 节奏 + 笔记路径 | 含「每 10-15 轮 [WIP] checkpoint commit」「.pipeline/wip/<task_id>.md」 | ✅ |
| C | 4 个发现笔记已 commit 入库 | .pipeline/wip/*.md 随分支持久（R2 关键） | `git ls-tree HEAD .pipeline/wip/` = 4 文件 | ✅ |
| D | EST_EFFECTIVE_LINE 含 ×0.7 折算 | R3 口径注入完整 | 含「迭代预算 × 0.7」「>30 有效轮必须拆卡」 | ✅ |
| E | _sub_card_body 补洞 CHECKPOINT+WIP | AC-9 修正 2 双行 | L858-859 区域同时含 CHECKPOINT_BODY_LINE + WIP_BODY_LINE | ✅ |
| F | 单一源漂移检查 | 9 profile SOUL 注入段与 constants 是否漂移 | 9/9 注入段含模板关键子串（每 10-15 轮/[WIP] checkpoint/.pipeline/wip/发现笔记/更新记录），零漂移 | ✅ |

**合计 16/16 PASS。漏报检查结论：QA-EXEC 未漏判任何缺陷。**

---

## 6. AC-1..AC-10 交叉核对（与 VA verdict 交叉印证）

| AC | 验收要点 | 本卡证据 | 结果 |
|----|---------|---------|:---:|
| AC-1 | constants.py 新增 WIP_SOUL_* / EST_* 常量 | 静态 S1（11 常量） | ✅ |
| AC-2 | inject_wip_rule.sh 幂等注入 9 profile | P2（9/9 FOUND）+ P3（SKIP 9/9）+ 探针 A（VERIFY-OK 9/9） | ✅ |
| AC-3 | autopilot.sh 建卡 comment 含 [WIP 节奏] | S4（恰 5 处）+ P6（L362/L400 非注入点） | ✅ |
| AC-4 | dev 卡 / est 卡 body 末含 WIP_BODY_LINE | 基线 T59h + T60c（386 全绿内含） | ✅ |
| AC-5 | dev-est 口径含 ×0.7 折算（双入口） | 基线 T60d + T63a + 探针 D（EST_EFFECTIVE_LINE 含 0.7） | ✅ |
| AC-6 | devppl_query comments 子命令 | 基线 T63g-i + P4/P5（合法/非法 id） | ✅ |
| AC-7 | 全量回归 PASS | 本卡独立复跑 **386 PASS/0 FAIL** | ✅ |
| AC-8 | 结构化 claim | VA verdict 引用 comment 1370（schema_version 1.0 claims 数组）；本卡读 comment 1370 实证 | ✅ |
| AC-9 | subsplit 子卡 body 含 WIP+CHECKPOINT 双行 | 基线 T63c/d/e + 探针 E（L858-859） | ✅ |
| AC-10 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变 | S2（L92）+ 基线 T63f/T68b | ✅ |

**10/10 PASS，与 VA 15/15 VERIFIED（t_74724cf6 [VERIFIED] comment，4 parent cards 独立复核）交叉一致。**

---

## 7. 发现汇总与分级（标准 §6 输出格式要求）

### 7.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR** |
| OBS-1（未合入 main） | ✅（merge/qa-post 需在分支测） | ❌（FF-ready） | ✅（直测分支，DPL-028 先例） | 否 | 否 | **观察项**（非功能缺陷，不设 SLA） |
| OBS-2（方案文档 chain_check 41 vs 实测 38） | ❌（仅内部文档口径） | ❌（0 FAIL） | ✅（以实测输出为准） | 否 | 否 | **观察项**（SUGGESTION 级，不阻塞） |

### 7.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**（QA-EXEC 与 QA-D2 均无发现）。
- 后续 merge 后 qa-post 阶段若发现 BLOCKER：4h 响应 + 8h 定位 + 24h 方案（按 §8 表执行）。

### 7.3 分级示例对照（标准 §5 表）

- 未发现「注入点漏注某路径」类缺陷（S4/P6 实证 5 处 + L362/L400 非注入点）→ 无 BLOCKER 触发条件。
- 未发现「WIP_BODY_LINE 文案错误」类缺陷（T59h/T60c/T63b 全绿 + 探针 B 文案完整）→ 无 MINOR 触发条件。
- 未发现「dev-est 折算口径缺失」类缺陷（T60d/T63a + 探针 D 含 0.7）→ 无 MAJOR 触发条件。

---

## 8. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。DPL-030 结果评审通过，可进入 va-qa → merge → qa-post。**

---

## 9. 评审建议

1. **放行**：QA-EXEC 报告分级判定准确、证据链完整、无漏报无错判。DPL-030 可继续 va-qa → merge → qa-post 流程。
2. **OBS-1 处置（同 QA-EXEC 建议）**：merge 后 qa-post 阶段须在 main 上再回归一遍（DPL-028 惯例），核对 merge 后 386 断言仍全绿。
3. **OBS-2 处置（同 QA-EXEC 建议）**：修正测试方案文档 chain_check 断言数（41→38，方案 header L13/L87/L205/L236 共 4 处）；不影响本次验收。
4. **无新增缺陷/观察**：QA-D2 漏报探针 A-F 全部通过，未发现 QA-EXEC 遗漏项。

---

## 附：执行记录

- 独立复跑：`bash scripts/test_cmd_channel.sh`（386/0，日志 /tmp/d2_cmdchannel.log）+ `bash scripts/test_chain_check.sh`（38/0，日志 /tmp/d2_chaincheck.log）
- 独立探针脚本：/tmp/d2_static_check.py（S1-S11 21 断言）、/tmp/d2_probes.py（P1-P6 + A-E 13 断言）、/tmp/d2_drift_probe.py（F 3 断言）
- 被测 worktree：`/workspace/devPPL/.worktrees/t_7c9d1952`（HEAD=ea489fb，工作树干净，测试自隔离 $TMPT 零写仓库）
- VA verdict：t_74724cf6 [VERIFIED] comment（15/15 claims，AC-1..AC-10 全绿，JSON /root/.hermes/profiles/verifier/.va_reports/20260814T201000.json）
- 本卡发现笔记：`.pipeline/wip/t_cfd940c3.md`（六节模板）
