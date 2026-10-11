# MEM-009 对话提取（对话/纠正自动提取记忆与经验）— QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-20 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_de9e75df [DEV-QA-POST] MEM-009 对话提取 — 对话/纠正自动提取记忆与经验（蓝图方向A，依赖 MEM-007 SourceAdapter）（DPL-080）
> 被测状态：**合并后** devPPL main @ `d6682b5`（autopilot merge t_70c4ccc4，4 张 dev 子卡全部在 main，零漂移）+ mem-core main @ `f644dd0`（MEM-009 adapter/命令面在 main）
> 前置阶段：PRD t_3f5c8462 → DEV t_11d3cf65/t_9a3c1371/t_c37ced5a/t_1ab2ab46 → QA-D1 t_2fc5fd0a → QA-EXEC t_f91a64c5 → QA-D2 t_ac88ed89 → VA t_48a3dd47（VERIFIED）→ MERGE t_70c4ccc4（全链 done）→ 本卡 QA-POST
> 上游文档：QA-D1 方案（docs/qa/mem009-conversation-extraction-test-plan.md）、QA-EXEC 报告（docs/qa/mem009-conversation-extraction-test-report.md）、QA-D2 评审（docs/qa/mem009-conversation-extraction-d2-review.md）、VA 报告（docs/qa/mem009-conversation-extraction-va-report.md）——均存于各 QA 分支，本卡用 git show 取用
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §5）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ devPPL main @ `d6682b5`；4 张 dev 子卡分支 tip（10583092/12ce1d38/5f35ff6d/ddb5776）**全部为 main 祖先**（merge-base == tip，无独有 commit，合并无冲突残留）；mem-core main @ `f644dd0`（4f67a75 祖先 + conversation 文件零改动） |
| **合并零漂移** | ✅ `git diff 8fec922 main -- scripts/conv_curate.py scripts/conv_sync.sh scripts/test_conv_sync.sh scripts/mem_sync.py` = **0 行**（MEM-009 代码自 QA 被测 commit 8fec922 合入后无任何改动）；mem-core 侧 conversation.py/cli.py/__init__.py/两个测试文件 diff 空 |
| **合并后无代码变更** | ✅ 8fec922..main 对 MEM-009 文件零改动；pipeline/discover.py 有 DPL-077 改动（VA 容器豁免，正交非 MEM-009 范围，git diff 确认） |
| 基线四套复跑（合并后 main，独立执行） | ✅ mem-core pytest **246 PASS**（195.08s）+ test_conv_sync.sh **55/0** + test_mem_sync.sh **80/0** + devPPL pytest **281 passed / 8 failed / 1 error**（135.83s）**零新增**（失败文件双段 git diff = 0 行） |
| 静态 S1-S12 | ✅ **12/12 PASS**（独立读码/grep/diff；S3 人工判定：pages 表查询/wiki 路径非 L0 SQL） |
| 探针复验 | ✅ P3-P8 **17/17**（F1 P6c 复现 concepts 0→4）+ D2 A-G **10/10**（漏报检查零漏报） |
| 语法复验 | ✅ bash -n 3/3 + py_compile 2/2 |
| AC 核对 | ✅ A1-A12/R5 **13/13**（MVP A1-A9 9/9） |
| **部署依赖（cron 未注册）** | ⚠️ **OBS-B（新增观察项）**：root crontab / orchestrator jobs.json / live scripts 均无 conv_sync 条目 → conv_sync.sh cron 注册（`*/5 * * * *`）**归 OC 执行**（同 MEM-007 OBS-2 先例；merge 刚完成，注册属部署动作，QA 只记录不代做） |
| **新增缺陷（POST 阶段新发现）** | **0 功能缺陷** — 合并未引入回归 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） |

**结论**：合并过程正确——MEM-009 全部改动（devPPL conv_curate.py/conv_sync.sh/test_conv_sync.sh/mem_sync.py 计数键 + mem-core conversation adapter/命令面/20 测试用例）完整在 main、零漂移、无冲突残留、无合并引入回归；合并后基线四套（246/55/80/281）在发布态 main 上独立复跑全绿，与 QA-EXEC / QA-D2 / VA 三方结论一致。遗留发现与前置阶段一致（F1-MINOR 策展垃圾输出无校验 + OBS-A standalone 队列路径），均不阻塞发版；**唯一新增部署依赖 OBS-B（conv_sync.sh cron 注册）留 OC 处置**。发布门禁满足，MEM-009 收尾闭环。

---

## 1. 合并状态核对（POST 前置检查）

### 1.1 主分支与合并记录

| 检查项 | 命令 | 结果 |
|---|---|---|
| devPPL main tip | `git rev-parse main` | ✅ `d6682b5`（autopilot merge: t_70c4ccc4 wt/t_c37ced5a） |
| 本卡工作树 == main | `git rev-parse HEAD` | ✅ 相同（d6682b5，worktree wt/t_de9e75df 与 main 同 tip） |
| t_11d3cf65 tip 在 main | `git merge-base --is-ancestor 10583092 main` | ✅ YES |
| t_9a3c1371 tip 在 main | `git merge-base --is-ancestor 12ce1d38 main` | ✅ YES |
| t_c37ced5a tip 在 main | `git merge-base --is-ancestor 5f35ff6d main` | ✅ YES |
| t_1ab2ab46 tip 在 main | `git merge-base --is-ancestor ddb5776 main` | ✅ YES |
| 合并无独有 commit | `git log --not <parent> <tip>`（三支） | ✅ 均为空（no-op merge：分支在 8fec922 之前分叉，代码早已在 main） |
| **合并零漂移（MEM-009 文件）** | `git diff 8fec922 main -- scripts/conv_curate.py scripts/conv_sync.sh scripts/test_conv_sync.sh scripts/mem_sync.py` | ✅ **0 行**（main 上 MEM-009 代码 == QA 被测 commit 8fec922 内容） |
| mem-core main tip | `git log -1` | ✅ `f644dd0`（mem(MEM-009): done，链上含 d44f5e5） |
| mem-core MEM-009 零漂移 | `git diff 4f67a75 HEAD -- memcore/sources/conversation.py memcore/cli.py memcore/sources/__init__.py tests/test_sources_conversation.py tests/test_cmd_conversation.py` | ✅ 空 |
| 合并后无代码变更 | `git log 8fec922..main -- <MEM-009 文件>` | ✅ 零命中（唯一非空为 discover.py 的 DPL-077 正交改动） |

### 1.2 上游链完整性（全链 done）

| 卡 | 状态 | 卡 | 状态 |
|---|---|---|---|
| PRD t_3f5c8462 | done | VA-QA t_48a3dd47 | done（VERIFIED 25/25，0 FALSIFIED） |
| DEV t_11d3cf65 (SUB) | done | MERGE t_70c4ccc4 | done（merge_commit 9a5a7f5/a922d3a/d6682b5） |
| DEV t_9a3c1371 (SUB) | done | **本卡 t_de9e75df** | running |
| DEV t_c37ced5a (SUB) | done | | |
| DEV t_1ab2ab46 (SUB) | done（8fec922，代码主体） | | |
| QA-D1 t_2fc5fd0a | done | QA-D2 t_ac88ed89 | done（review_pass） |
| QA-EXEC t_f91a64c5 | done | | |

---

## 2. 基线四套复跑结果（合并后 main，独立执行非转述）

| 测试 | 断言 | 本卡实测 | 与前置阶段对比 |
|---|---|:---:|---|
| mem-core pytest | 246 | **246 passed in 195.08s**，EXIT=0 | = QA-EXEC 246 / QA-D2 246 / VA 246 四方一致 |
| test_conv_sync.sh | 55 | **PASS=55 FAIL=0 / ALL TESTS PASSED** | = 55/0 一致（含 A1-A8/A10/A11/A12/R5 锚点） |
| test_mem_sync.sh | 80 | **PASS=80 FAIL=0 / ALL TESTS PASSED** | = 80/0 一致（MEM-007 回归无回退） |
| devPPL pytest | 281 基线 | **281 passed / 8 failed / 1 error（135.83s）** | 失败集 = test_memory_middleware_qa ×3 + test_slice2_d1_qa ×5 + ERROR test_P2-02_full ×1，与 QA-EXEC/D2/VA 同款 |

### 2.1 devPPL pytest 失败集零新增证明

```
FAILED tests/test_memory_middleware_qa.py::test_tc19_blast_radius_engine
FAILED tests/test_memory_middleware_qa.py::test_tc20_gai_links_adapter
FAILED tests/test_memory_middleware_qa.py::test_tc23_drift_engine
FAILED tests/test_slice2_d1_qa.py::TestRound0_Static::test_TC14_double_rollback_idempotent
FAILED tests/test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_retry_count_preserved
FAILED tests/test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_upsert_retry_count_bug_demo
FAILED tests/test_slice2_d1_qa.py::TestRound1_BranchEngine::test_TC09_rollback_verdict_preserved
FAILED tests/test_slice2_d1_qa.py::TestRound1_BranchEngine::test_BE01_empty_branches_default_advance
ERROR tests/test_P2-02_full.py::test
```

- `git diff 8fec922 main -- <3 个失败文件>` = **0 行**（合并后未触碰）
- `git diff 8fec922^ 8fec922 -- <3 个失败文件>` = **0 行**（MEM-009 合入 commit 未触碰）
- → **零新增失败**，与前置四阶段（D1/EXEC/D2/VA）同款失败集。

### 2.2 语法复验（5/5 OK）

- `bash -n scripts/conv_sync.sh scripts/test_conv_sync.sh scripts/test_mem_sync.sh` ✅ 3/3
- `python3 -m py_compile scripts/conv_curate.py scripts/mem_sync.py` ✅ 2/2

---

## 3. 静态核查（S1-S12，合并后 main 逐项复验）

| # | 核查点 | 本卡实测 | 结果 |
|---|---|:---:|:---:|
| S1 | SOURCES 注册含 "conversation"（A12） | `__init__.py` L10 import + L15 `"conversation": ConversationAdapter()` | ✅ |
| S2 | 引擎零对话语义：mem_sync.py grep conversation/correction 仅 _COUNTER_KEYS + 注释 | L65 注释 + L68 两键，无逻辑引用 | ✅ |
| S3 | SQL 只存在于 adapter：mem_sync/conv_curate/cli grep state.db/sessions/messages | cli.py 命中均为 mem_meta.db(L1)/wiki 路径（L99/526/572/794/952/1064/1250 为 cli 自身 L1 管理）；无 L0 state.db SQL；conv_curate L195/265 mode=ro 读 mem_meta.db | ✅（人工判定同前置） |
| S4 | adapter mode=ro 三铁律 | conversation.py L350 `file:{path}?mode=ro` | ✅ |
| S5 | adapter 无写语句 | grep INSERT/UPDATE/DELETE 仅注释 L3 | ✅ |
| S6 | _COUNTER_KEYS 含 conversation/correction/curated 三键 | L67-69 tuple 9 键齐全 | ✅ |
| S7 | conv_sync.sh 两阶段 fail-open | L31-36：set -uo pipefail（无 -e）、两阶段取 rc、恒 exit 0 | ✅ |
| S8 | conv_curate.py：原子写/打分/Top-N/retries | L97-133 os.replace 原子写 + L229 score_candidate + TOP_N=3 + retries<3/≥3 abandoned | ✅ |
| S9 | memctl 命令面：add conversation/note --correction/query --corrections/status 三计数 | cli.py L179/407/900/1052/1218 全在位 | ✅ |
| S10 | fingerprint 规则 | conversation.py L114-122 `correction:<category>:<sha256(norm_lede)[:12]>` | ✅ |
| S11 | A11 双链回 conversation + lint 门禁 | conv_curate.py L306 curate-source 注释携带 page_id + L340-345 supersedes 接口 | ✅ |
| S12 | cron 注册行交付 + 不进 must-sync | conv_sync.sh L4-5 注册行（`*/5 * * * *`）+ deploy-drift-audit must-sync 清单 4 脚本无 conv_sync（repo 路径直调，与 notify_cron 同款） | ✅ |

---

## 4. 探针复验（合并后 main，独立执行）

### 4.1 QA 独立探针 P3-P8（scripts/qa_mem009_probes.sh，17 断言）

```
PASS=17 FAIL=0 / ALL TESTS PASSED
```

- P3 跨会话 fingerprint 聚合：P3b 骨架页=6 + P3c correction=3 + P3e SQL 直查聚合 2+1（A4）+ P3f 单弱词不检出 ✅
- P4 A6 md5 独立复核：tick 前后 state.db md5 一致（L0 只读 mode=ro）✅
- P7 work-gated（A8）：P7b 锚定 tick 零 memctl + P7c 无新会话 replay 零 memctl ✅
- P8 幂等重放（A5）：P8a 页数不变 + P8b 事件数不变 ✅
- P6 策展健壮性（A10/A11）：P6a exit-0 垃圾 rc=0（fail-open）+ P6b 骨架页不受影响 + **P6c 垃圾文本落记忆页（concepts 0→4，F1-MINOR 复现）** + P6d exit-1 三次不产页 + P6e ≥3 → abandoned ✅
- P5 队列损坏 fail-open：非法 JSON → conv_curate exit 0 不崩 ✅

### 4.2 D2 漏报探针 A-G（scripts/qa_mem009_d2_probes.sh，10 断言）

```
PASS=10 FAIL=0 / ALL TESTS PASSED
```

- A 未知 source exit 2（用法错误不吞）✅
- B1/B2 缺 profile dir / 损坏 state.db → exit 0 fail-open ✅
- C MEM_CONV_CORR_MUTE 静默名单生效（1→0）✅
- D1/D2 bash -n 3/3 + py_compile 2/2 ✅
- E 状态文件不入库（mem_sync_state/conv_queue 零 git 跟踪）✅
- F conversation tick 不写 kanban.db（md5 一致）✅
- G1/G2 真实 profile --dry-run exit 0 + 不落游标状态文件 ✅

---

## 5. 分级复核（标准 §1.2 五步判定公式 + SLA 对照）

### 5.1 发现清单（沿自 QA-D1/EXEC/D2，本卡复验一致；新增 OBS-B 部署观察项）

| # | 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 判定 | 本卡复验 |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|
| F1 | 策展 LLM exit 0 垃圾输出无内容校验 → 垃圾记忆页落库（P6c：concepts 0→4，页体 = "this is not markdown, just garbage output"） | ✅（垃圾页可见） | ❌（机械层骨架/correction 不受影响） | ✅（OC 部署正确 LLM 命令；人工清理） | 否 | **MINOR**（对照标准 §5 MINOR 行） | ✅ 复现一致（P6c） |
| OBS-A | standalone `memctl status` 无 MEM_CONV_QUEUE env 时策展队列读默认路径（<wiki.parent>/.pipeline/ vs 实际 devPPL .pipeline/） | ✅（观察期读错值） | ❌（生产链路由 conv_sync.sh L24 导出 env 统一） | ✅（跑 status 时同 env） | 否 | **观察项**（非验收缺陷） | ✅ 复验一致（status RC=0，队列计数需同 env） |
| **OBS-B（新增）** | conv_sync.sh cron 未注册（root crontab / orchestrator jobs.json / live scripts 三处均无 conv_sync 条目） | ✅（Frank 问"生效了吗"） | ❌（repo 脚本可手动执行；合入即交付） | ✅（OC 注册 cron 后生效） | 否 | **观察项**（部署依赖，非代码缺陷，不设 SLA） | ✅ 本卡实测三处零命中 |

> OBS-B 说明：merge（t_70c4ccc4）于本卡启动前 1 分钟完成，cron 注册属 OC 部署动作（架构 §8「注册动作留给 OC」+ DPL-048 部署验证规则「部署动作留给 OC」）。QA 只记录状态，不代建/代做。conv_sync.sh 为 repo 路径直调（`bash /workspace/devPPL/scripts/conv_sync.sh`），天然最新、不进 must-sync 清单，**注册后无 repo→live 同步需求**。

### 5.2 判定公式 / 分级示例对照（标准 §5 表）

- 未发现「合格 feishu/cli 会话不产骨架页（白名单 SQL 误排除、摘要抛异常丢事件）」类 **BLOCKER**（A1 用例绿 + P3 探针绿 + 基线 246/55/80 含）。
- 未发现「correction 检测误报率异常（弱词门控失效致大量无意义 events）」类 **MAJOR**（P3f 单弱词不检出 + A4 聚合精确）。
- 未发现「日志/输出格式与架构文档出入」类 **MINOR**（S7/S8 读码一致 + 55 断言含）。
- 未发现「注释/文档与实现不一致」类 **SUGGESTION**（S1-S12 全过）。

### 5.3 SLA 对照（标准 §8）

- 本卡 **0 BLOCKER / 0 MAJOR** → **无 SLA 触发**（QA-D1/EXEC/D2/VA/QA-POST 五阶段均无发现）。
- OBS-A/OBS-B 为观察项（非缺陷），不设 SLA；OBS-B 由 OC 注册 cron 时处置。

---

## 6. 验收映射（A1-A12/R5，13/13）

| # | 验收要点 | 证据（本卡实测） | 结果 |
|---|---------|------|:---:|
| A1 | feishu 会话 → ≤1 tick 骨架页（raw/sessions/<profile>:<sid>.md + page_type: conversation） | test_conv_sync 55/0（A1 段）+ P3b 骨架页=6 | ✅ |
| A2 | cli 全 profile 覆盖（静置主路径：无 ended_at + 超 6h → 合格） | test_conv_sync 55/0（A2 段） | ✅ |
| A3 | 噪声/未结束/低消息/archived → 不生成 + skipped 可见 | test_conv_sync 55/0（A3 段）+ P3d cron 噪声无页 | ✅ |
| A4 | 纠正复发计数可查询（2 同指纹 + 1 异指纹 → total=3 聚合 2+1） | test_conv_sync A4b + P3e SQL 直查 | ✅ |
| A5 | 幂等重放 3 次页数/事件数不变 | test_conv_sync A5a/A5b + P8a/P8b | ✅ |
| A6 | state.db md5 全程一致（mode=ro） | test_conv_sync A6 段 + P4 | ✅ |
| A7 | fail-open（库损坏/LLM 失败） | test_conv_sync A7 段 + P5 + B1/B2 | ✅ |
| A8 | work-gated：无新会话 → 零 memctl 调用 | test_conv_sync A8 段 + P7b/P7c | ✅ |
| A9 | pytest 全绿 + 集成 ≥10 断言 | mem-core 246/0 + test_conv_sync 55（≥12） | ✅ |
| A10 | 成本护栏全 env 可调（LLM/TOP_N/QUEUE_MAX/DONE_MAX） | test_conv_sync A10 段 + P6d/P6e（exit-1 retries/abandoned） | ✅ |
| A11 | 记忆页双链回 conversation + lint 零新增 | test_conv_sync A11 段（假 LLM 成功态）+ S11 + P6c（垃圾态 MVP 仍满足） | ✅ |
| A12 | adapter 继承 + 一行注册 + 引擎零语义 | 静态 S1/S2/S3 + test_sources_conversation | ✅ |
| R5 | memctl status 三计数（conversation 页 / correction 事件 / 策展队列积压） | test_conv_sync R5a/R5b + 本卡 status RC=0 | ✅ |

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---|---|---|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0（无申诉记录） | ✅ |

**发布门禁满足。** MEM-009 全链（PRD → DEV×4 → QA-D1/EXEC/D2 → VA → MERGE → QA-POST）闭环，可收尾。

---

## 8. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **OBS-B（唯一新增遗留，部署依赖）**：OC 注册 conv_sync.sh cron（`*/5 * * * * bash /workspace/devPPL/scripts/conv_sync.sh >> /workspace/devPPL/logs/conv_sync.log 2>&1`，见 conv_sync.sh L4-5 注释）+ 注册后观测真实 tick 心跳（期望 logs/conv_sync.log 出现「阶段① discover tick + 阶段② curate」行；同 MEM-007 D12 先例）。观测结果可挂本卡 comment 或由 OC 复核。
2. **F1-MINOR（沿前置，不阻塞发版）**：建议后续 conv_curate 加输出 sanity check（如必须含 `---` frontmatter 或指定结构）或 OC 部署时验证 C 命令。可独立小卡跟进。
3. **OBS-A（沿前置，非验收缺陷）**：建议后续独立小改对齐 standalone status 默认队列路径（如 cli.py 默认路径与 conv_sync.sh 导出的 MEM_CONV_QUEUE 一致化）。
4. **回归门禁固化**：MEM-009 全量回归基线已固化（mem-core pytest 246 + test_conv_sync 55 + test_mem_sync 80 + devPPL pytest 281/8/1 零新增），后续任何改动的合并后回归直接复用四集。

---

## 附：执行记录

- 合并状态：devPPL main @ d6682b5；mem-core main @ f644dd0；4 dev 分支 tip 全部祖先；MEM-009 文件双仓零漂移（git diff 空）
- 基线四集（合并后 main 独立复跑）：`cd /workspace/mem-core && .venv/bin/python -m pytest -o addopts='' -q --tb=no`（246，195.08s，EXIT=0）；`bash scripts/test_conv_sync.sh`（55/0）；`bash scripts/test_mem_sync.sh`（80/0）；`cd /workspace/devPPL && python3 -m pytest tests/ -q --tb=no`（281/8/1，135.83s，失败文件双段 diff 0 行）
- 语法：bash -n 3/3 + py_compile 2/2
- 静态：S1-S12 逐项独立读码/grep/diff（S3 人工判定同前置）
- 探针：P3-P8 17/17（F1 P6c 复现）+ D2 A-G 10/10
- OBS-B 复核：`crontab -l`（root 无 conv）+ `grep conv /root/.hermes/profiles/orchestrator/cron/jobs.json`（0 命中）+ `ls /root/.hermes/profiles/orchestrator/scripts/`（无 conv 脚本）
- 本卡发现笔记：`.pipeline/wip/t_de9e75df.md`（六节模板）
- 执行用探针脚本：`scripts/qa_mem009_probes.sh` + `scripts/qa_mem009_d2_probes.sh`（自 QA 分支 git show 取用，本卡复跑，不改动）
