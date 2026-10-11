# VA-QA 验证报告 — worker 上下文连续性（DPL-030）检查点提交+发现笔记+预算收紧+审批白名单

> 版本：v1.0 | 日期：2026-08-15 | 执行人：Verification Agent（verifier profile，t_4aa731e1）
> 上游：QA-D2 结果严重度评审（t_cfd940c3 @ 66a6c87，review_pass）→ 放行 va-qa → merge → qa-post
> 被测提交：**wt/t_7c9d1952 @ ea489fb**（main @ e714aa1 未合入，OBS-1 复确认）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 验证性质：VA 独立执行（非转述 QA-EXEC/QA-D2/研发），基线全量 + 静态 + 探针 + AC 交叉核对

---

## 0. 验证结论（TL;DR）

| 验证项 | 结果 | 证据 |
|---|---|---|
| 基线全量独立复跑（test_cmd_channel.sh） | ✅ **PASS=386 FAIL=0** EXIT=0 | §3.1（本卡独立执行） |
| chain_check 独立复跑 | ✅ **PASS=38 FAIL=0** EXIT=0 | §3.2（OBS-2 复确认） |
| 静态核对 S1-S11 | ✅ **20/20 PASS**（独立探针脚本） | §4 |
| 探针 P1-P6 + 漏报探针 A-F | ✅ **12/12 PASS**（9 profile 白名单口径修正后） | §5 |
| AC-1..AC-10 交叉核对 | ✅ **10/10 PASS**（与 VA-CLAIM 15/15、QA-D2 10/10 三方一致） | §6 |
| 分级判定复核 | ✅ 0 BLOCKER/MAJOR/MINOR，2 观察项（OBS-1/OBS-2） | §7 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §8 |

**结论：DPL-030 实现通过 VA 独立复核。0 FALSIFIED。分级判定与 QA-D2 一致（0 缺陷 + 2 观察项），发布门禁满足，可放行 merge 回 main → qa-post。**

---

## 1. 验证对象与方法

### 1.1 被测对象确认

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | main HEAD | `git log main -1` = e714aa1（BKP-004，无 DPL-030 commit） | ✅ |
| P-2 | FF 关系 | `git merge-base --is-ancestor e714aa1 ea489fb` = YES（FF-ready）；diff e714aa1..ea489fb = **11 文件 +381/-9** | ✅ |
| P-3 | 被测 worktree | /workspace/devPPL/.worktrees/t_7c9d1952，HEAD=ea489fb | ✅ |
| P-4 | 测试隔离 | 测试后 `git status --short` 为空（$TMPT 自隔离零写仓库） | ✅ |
| P-5 | 4 parent cards 状态 | t_ab9a26b3 done / t_8458422f done（run 892 timed_out 后 run 893 收尾）/ t_5213b5dd done / t_7c9d1952 done | ✅ |

### 1.2 验证方法（独立执行，不转述）

- M1：基线全量独立复跑（test_cmd_channel.sh / test_chain_check.sh，被测 worktree）
- M2：静态独立核对（独立探针脚本 20 断言，S1-S11）
- M3：探针独立复验（P1-P6 + 漏报探针 A-F，12 断言）
- M4：AC-1..AC-10 交叉核对（与 VA-CLAIM t_74724cf6 [VERIFIED] 15/15、QA-D2 10/10 交叉印证）
- M5：分级判定复核（标准 §1.2 公式 + §10 门禁逐项对照）

---

## 2. 基线全量独立复跑

### 2.1 test_cmd_channel.sh（386 断言）

```bash
cd /workspace/devPPL/.worktrees/t_7c9d1952 && bash scripts/test_cmd_channel.sh
```

```
════════ 结果汇总 ════════
PASS=386 FAIL=0
ALL TESTS PASSED        （EXIT=0，日志 /tmp/va4_cmdchannel.log）
```

- VA 独立执行（非转述），含 DPL-030 新增断言 13 条 + DPL-018 校准回归 T64-T69
- 与 QA-EXEC 386/0、QA-D2 386/0、VA-CLAIM 386/0 四方一致

### 2.2 test_chain_check.sh（38 断言实测）

```
PASS=38 FAIL=0
ALL TESTS PASSED        （EXIT=0，日志 /tmp/va4_chaincheck.log）
```

- **OBS-2 复确认**：测试方案文档（wt/t_07b1c297 header L13/L87/L236 共 4 处）写 41 断言，实测 38。内部文档口径差，非功能缺陷（0 FAIL 全绿）。

---

## 3. 静态核对 S1-S11（20/20 PASS，独立探针脚本 /tmp/va4_static_check.py）

| # | 核对项 | 实测 | 结果 |
|---|--------|------|:---:|
| S1 | constants.py 11 个 WIP_*/EST_* 常量 | grep -c=11（WIP_SOUL_TITLE L238 / PROFILES L239 / MIN L243 / MAX L244 / COMMIT_PREFIX L245 / NOTE_DIR L246 / BODY_LINE L247 / SOUL_PARAGRAPH L248 + EST_EFFECTIVE_RATIO L273 / SPLIT_ROUNDS L274 / EFFECTIVE_LINE L275） | ✅ |
| S2 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变 | L92 `= 20`（AC-10 红线未动） | ✅ |
| S3 | inject_wip_rule.sh 参数/幂等/单一源 | 6 处参数匹配 + SKIP 逻辑 3 处 + `from pipeline.constants import` 3 处（cd REPO_ROOT 防影子导入） | ✅ |
| S4 | autopilot.sh [WIP 节奏] 恰 5 处 | L159/343/383/520/665 | ✅ |
| S5 | cmd_chain.py 注入点 | WIP_BODY_LINE 3 处（L54 import/L652/L859）+ EST_EFFECTIVE_LINE 2 处（L46/L638） | ✅ |
| S6 | discover.py est_body 注入顺序 | EST L249 → CHECKPOINT L253 → WIP L254（顺序正确） | ✅ |
| S7 | devppl_query.sh comments 白名单 + 只读 | mode=ro 3 处 + `=~ ^t_[a-z0-9]+$` 白名单 3 处 + BAD_ID 拒绝 | ✅ |
| S8 | test_cmd_channel.sh 新断言在册 | 16 处匹配（13 新断言 + 修正回归） | ✅ |
| S9 | .pipeline/wip 4 个发现笔记六节模板 | t_ab9a26b3/t_8458422f/t_5213b5dd/t_7c9d1952 全含六节标题 | ✅ |
| S10 | .pipeline 不在 .gitignore | grep 精确匹配 NONE；`git check-ignore .pipeline/wip/foo.md` = NOT IGNORED；`git ls-files .pipeline/wip/` = 4 文件已入库 | ✅ |
| S11 | bash -n 语法 5 脚本 | test_cmd_channel/inject_wip_rule/autopilot/devppl_query/test_chain_check 全 OK | ✅ |

> S10 说明：VA 首轮探针误命中 .gitignore L12 注释（pipeline_state.db 运行时库），修正为精确路径模式检查后确认 `.pipeline/` 无 ignore 规则，4 笔记已 commit 入库（git ls-tree HEAD = 4 文件）。

---

## 4. 探针 P1-P6 + 漏报探针 A-F（12/12 PASS，独立脚本 /tmp/va4_probes.py）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | WIP_SOUL_PARAGRAPH 六节模板 | 上游契约/关键事实/已踩坑/当前进度/下一步/更新记录 全在 | ✅ |
| P2 | 真实 9 profile SOUL 注入现场 | **修正口径**：按 constants.WIP_SOUL_PROFILES 白名单（game-engine/game-qa/game-architect/game-director/game-artist/game-client/gateway-eng/infomanager/tag-system）逐 profile grep = 1/1 × 9（orchestrator/vault-writer/verifier 不在名单，PRD §4.2 明确不覆盖） | ✅ |
| P3 | inject_wip_rule.sh --dry-run 幂等 | SKIP 9/9，RC=0 | ✅ |
| P4 | devppl_query comments 合法 id | comments t_74724cf6 → RC=0，输出含 [VERIFIED]（comment 1371） | ✅ |
| P5 | devppl_query comments BAD_ID | bad_id → `BAD_ID: bad_id` + RC=1 | ✅ |
| P6 | autopilot 注入点完整性 | [WIP 节奏] 恰 5 处；L362（qa-d1）/L400（qa-d2）为 3 参 kanban_ensure_card 无 comment 参数 → 非注入点（与 arch A-1 一致） | ✅ |
| A | inject_wip_rule.sh --verify | VERIFY-OK 9/9，RC=0 | ✅ |
| B | WIP_BODY_LINE 内容双要素 | 含「每 10-15 轮 [WIP] checkpoint commit」+「.pipeline/wip/<task_id>.md」 | ✅ |
| C | 4 个发现笔记已 commit 入库 | `git ls-tree HEAD .pipeline/wip/` = 4 文件 | ✅ |
| D | EST_EFFECTIVE_LINE 含 ×0.7 折算 | 含「迭代预算 × 0.7」「>30 有效轮必须拆卡」「4 交付物以上一律拆 ~3 卡」 | ✅ |
| E | _sub_card_body 补洞 CHECKPOINT+WIP | L858-859 区域同时含 CHECKPOINT_BODY_LINE + WIP_BODY_LINE | ✅ |
| F | 单一源漂移检查 | 9/9 profile SOUL 注入段含模板关键子串（每 10-15 轮/[WIP] checkpoint/.pipeline/wip/），零漂移 | ✅ |

> P2/F 说明：VA 首轮探针误扫全部 12 个 profile 目录（含 orchestrator/vault-writer/verifier 3 个不在白名单的 profile），修正为按 constants.WIP_SOUL_PROFILES 精确名单后 9/9 全 PASS。这与 PRD §4.2「不覆盖 OC/orchestrator profile」红线一致。

---

## 5. AC-1..AC-10 交叉核对（10/10 PASS）

| AC | 验收要点 | VA 证据 | 结果 |
|----|---------|---------|:---:|
| AC-1 | constants.py 新增 WIP_SOUL_* / EST_* 常量 | 静态 S1（11 常量） | ✅ |
| AC-2 | inject_wip_rule.sh 幂等注入 9 profile | P2（9/9 = 1）+ P3（SKIP 9/9）+ 探针 A（VERIFY-OK 9/9） | ✅ |
| AC-3 | autopilot.sh 建卡 comment 含 [WIP 节奏] | S4（恰 5 处）+ P6（L362/L400 非注入点） | ✅ |
| AC-4 | dev 卡 / est 卡 body 末含 WIP_BODY_LINE | 基线 T59h + T60c（386 全绿内含） | ✅ |
| AC-5 | dev-est 口径含 ×0.7 折算（双入口） | 基线 T60d + T63a + 探针 D | ✅ |
| AC-6 | devppl_query comments 子命令 | 基线 T63g-i + P4/P5（合法/非法 id） | ✅ |
| AC-7 | 全量回归 PASS | 本卡独立复跑 **386 PASS/0 FAIL** | ✅ |
| AC-8 | 结构化 claim | t_7c9d1952 kanban_complete metadata 含 canonical claims 数组（schema_version 1.0，c1-c4）；VA-CLAIM 15/15 交叉一致 | ✅ |
| AC-9 | subsplit 子卡 body 含 WIP+CHECKPOINT 双行 | 基线 T63c/d/e + 探针 E（L858-859） | ✅ |
| AC-10 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变 | S2（L92）+ 基线 T63f/T68b | ✅ |

---

## 6. 发现汇总与分级（标准 §6 输出格式要求）

### 6.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR** |
| OBS-1（未合入 main） | ✅（merge/qa-post 需在分支测） | ❌（FF-ready） | ✅（直测分支，DPL-028 先例） | 否 | 否 | **观察项**（非功能缺陷，不设 SLA） |
| OBS-2（方案文档 chain_check 41 vs 实测 38） | ❌（仅内部文档口径） | ❌（0 FAIL） | ✅（以实测输出为准） | 否 | 否 | **观察项**（SUGGESTION 级，不阻塞） |

### 6.2 安全面检查（标准 §2 独立判定）

| 检查项 | 结论 | 证据 |
|--------|:---:|------|
| devppl_query comments 只读 | ✅ 无风险 | SQLite mode=ro + 白名单 `^t_[a-z0-9]+$` + BAD_ID 拒绝（无注入面） |
| inject_wip_rule.sh | ✅ 无风险 | 只写 SOUL.md 文本（注入段来自单一源 constants），无网络/认证面 |
| 认证绕过/数据泄露/远程注入 | ✅ 无 | 无新增网络面；改动为提示文本 + 查询工具 |

### 6.3 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**。
- 后续 merge 后 qa-post 阶段若发现 BLOCKER：4h 响应 + 8h 定位 + 24h 方案。

### 6.4 分级示例对照（标准 §5 表）

- 未发现「注入点漏注某路径」类缺陷（S4/P6 实证 5 处 + L362/L400 非注入点）→ 无 BLOCKER 触发条件。
- 未发现「WIP_BODY_LINE 文案错误」类缺陷（T59h/T60c/T63b 全绿 + 探针 B 文案完整）→ 无 MINOR 触发条件。
- 未发现「dev-est 折算口径缺失」类缺陷（T60d/T63a + 探针 D 含 0.7）→ 无 MAJOR 触发条件。

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。DPL-030 验证通过，可进入 merge → qa-post。**

---

## 8. 处置建议

1. **放行 merge**：VA 独立复核与 QA-D2（review_pass）、QA-EXEC、VA-CLAIM 四方结论一致，0 FALSIFIED。DPL-030 可 merge 回 main。
2. **OBS-1（同 QA-D2）**：merge 后 qa-post 阶段须在 main 上再回归一遍（DPL-028 惯例），核对 merge 后 386 断言仍全绿。
3. **OBS-2（同 QA-D2）**：修正测试方案文档 chain_check 断言数（41→38，wt/t_07b1c297 L13/L87/L236）；不影响本次验收。

---

## 附：执行记录

- 独立复跑：`bash scripts/test_cmd_channel.sh`（386/0，日志 /tmp/va4_cmdchannel.log）+ `bash scripts/test_chain_check.sh`（38/0，日志 /tmp/va4_chaincheck.log）
- 独立探针脚本：/tmp/va4_static_check.py（S1-S11 20 断言）、/tmp/va4_probes.py（P1-P6 + A-F 12 断言）
- 被测 worktree：/workspace/devPPL/.worktrees/t_7c9d1952（HEAD=ea489fb，测试后工作树干净）
- 交叉印证：VA-CLAIM t_74724cf6 [VERIFIED] 15/15（comment 1371，JSON /root/.hermes/profiles/verifier/.va_reports/20260814T201000.json）；QA-D2 t_cfd940c3 review_pass（66a6c87）
- VA 执行中修正 2 处探针口径（S10 .gitignore 精确匹配；P2/F 按 constants.WIP_SOUL_PROFILES 白名单），均为探针脚本自身缺陷非实现缺陷
