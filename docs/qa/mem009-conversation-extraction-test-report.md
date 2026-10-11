# MEM-009 对话提取 — QA 执行测试报告（test_report.md）

> 版本：v1.0 | 日期：2026-08-19 | 作者：game-qa（QA-EXEC 独立执行，非研发自测）
>
> 任务卡：t_f91a64c5 [DEV-QA-EXEC] MEM-009 对话提取（DPL-074）
> 测试方案：t_2fc5fd0a 交付 docs/qa/mem009-conversation-extraction-test-plan.md v1.0
> 被测代码：devPPL main @ da145d7（被测 commit 8fec922 为祖先，MEM-009 文件 8fec922..HEAD 零改动）+ mem-core main @ 61457ae（被测 commit 4f67a75 为祖先，4f67a75..HEAD 仅 wiki 文档改动）
> 分级标准：docs/standards/qa-finding-classification.md v1.0

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 前置检查 | ✅ 4/4：双仓被测 commit 为祖先 + bash -n 3/3 + py_compile 2/2 |
| 基线四套 | ✅ mem-core pytest **246/0**（188.68s）+ test_conv_sync **55/0** + test_mem_sync **80/0** + devPPL pytest **281 passed / 8 failed / 1 error（134.78s）零新增**（失败集 = 存量 memory_middleware×3 + slice2_d1×5 + P2-02 ERROR×1，三个失败文件 git diff 证零改动） |
| 静态核查 | ✅ S1-S12 全过（含 S3/S5 命中人工判定：均为注释/pages 表查询，非 L0 SQL） |
| 独立探针 | ✅ P1-P8 全过（P3-P8 脚本 17/17 + P1 真实数据 e2e + P2 OBS-A 复验） |
| 发现分级 | **0 BLOCKER / 0 MAJOR / 1 MINOR（F1 继承确认）/ 1 观察项（OBS-A 复验确认）** |
| 发布门禁 | ✅ BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉 → **可发版** |

**结论**：MEM-009 双层管线（机械层骨架+correction / 语义层策展）经 QA-EXEC 独立执行全部验收成立。QA-D1 的 F1-MINOR 与 OBS-A 在本卡复验确认，无新增发现。

---

## 1. 前置检查（§2 执行前置）

| # | 检查项 | 结果 | 证据 |
|---|--------|:---:|------|
| 1 | devPPL 被测 commit | ✅ | `git merge-base --is-ancestor 8fec922 HEAD` → 是（HEAD=da145d7）；`git log 8fec922..HEAD -- scripts/conv_sync.sh scripts/conv_curate.py scripts/mem_sync.py scripts/test_conv_sync.sh` 空（MEM-009 文件零改动） |
| 2 | mem-core 被测 commit | ✅ | `git merge-base --is-ancestor 4f67a75 HEAD` → 是（HEAD=61457ae）；`git diff 4f67a75..HEAD --stat` 仅 wiki/actions/MEM-009.md + wiki/log.md 文档改动 |
| 3 | bash -n | ✅ | conv_sync.sh / test_conv_sync.sh / test_mem_sync.sh 3/3 OK |
| 4 | py_compile | ✅ | conv_curate.py + mem_sync.py 2/2 OK |

---

## 2. 基线回归（§3 四套全量复跑）

| 测试 | 期望 | 本卡实测 | 判定 |
|------|:---:|:---:|:---:|
| mem-core pytest（`.venv/bin/python -m pytest -o addopts='' -q`） | 246 全绿 | **246 passed**（188.68s，EXIT=0） | ✅ |
| test_conv_sync.sh（A1-A8/A10/A11/A12/R5） | 55/0 | **PASS=55 FAIL=0 / ALL TESTS PASSED** | ✅ |
| test_mem_sync.sh（MEM-007 回归） | 80/0 | **PASS=80 FAIL=0 / ALL TESTS PASSED** | ✅ |
| devPPL pytest（`python3 -m pytest tests/ -q`） | 281 基线 + 存量失败集零新增 | **281 passed / 8 failed / 1 error**（134.78s）；失败集 = test_memory_middleware_qa×3 + test_slice2_d1_qa×5 + ERROR test_P2-02_full×1，与 VA/dev claim 记录同款 | ✅ |

**零新增失败证据**：`git diff 8fec922^ 8fec922 --stat -- tests/test_memory_middleware_qa.py tests/test_slice2_d1_qa.py tests/test_P2-02_full.py` 与 `git diff 8fec922 HEAD --stat -- <同三文件>` 均为空 → 三个失败文件在 MEM-009 merge 及后续零改动，8 失败 + 1 ERROR 全部为存量（VA 记录的 14+1 含 test_p0_18_qa×6 为 OC live 脚本环境漂移项，本卡不出现）。

---

## 3. 静态核查（§4 S1-S12）

| # | 核查点 | 判定 | 证据 |
|---|--------|:---:|------|
| S1 | SOURCES 注册含 conversation（A12） | ✅ | memcore/sources/__init__.py L10+L15：`from .conversation import ConversationAdapter` + `"conversation": ConversationAdapter()` |
| S2 | 引擎零对话语义（A12） | ✅ | mem_sync.py grep conversation/correction 仅命中 L65 注释 + L68 `"conversation", "correction"`（_COUNTER_KEYS） |
| S3 | SQL 只存在于 adapter | ✅ | mem_sync.py 零命中；conv_curate.py 3 命中均为 pages 表查询（`raw/sessions/%` 为 wiki 路径非 L0 表）；cli.py 10 命中均为路径/注释/pages 表查询，无 L0 state.db 表 SQL |
| S4 | adapter 只读三铁律 mode=ro | ✅ | conversation.py L346-350：`_connect` 用 `file:{path}?mode=ro` URI |
| S5 | adapter 无写语句 | ✅ | conversation.py grep INSERT/UPDATE/DELETE 唯一命中 L3 注释（"pytest 断言 INSERT 抛错"） |
| S6 | _COUNTER_KEYS 三键 | ✅ | mem_sync.py L67-69 tuple 含 conversation/correction/curated |
| S7 | conv_sync.sh 两阶段 fail-open | ✅ | L16 `set -uo pipefail`（无 -e）；L28/L31 两阶段；L34-35 各取 rc 打印；L36 恒 `exit 0` |
| S8 | conv_curate.py 打分/原子写/Top-N/retries | ✅ | L10 os.replace；L11 打分表（纠正+3/feishu+2/消息>40+1/决策词+2）；L54 DEFAULT_TOP_N=3；L64 retries ≥3 abandoned |
| S9 | memctl 命令面 | ✅ | cli.py L407 `_add_conversation` + L913 `_correction_exists` + L1052 `_query_corrections` + L1218 `_conv_queue_backlog`；status 三计数 L1246 |
| S10 | fingerprint 规则 | ✅ | conversation.py L114-122：`correction:<category>:<sha256(norm_lede)[:12]>`（D4 双因子） |
| S11 | A11 双链回 conversation + lint | ✅ | conv_curate.py L306 HTML 注释 curate-source 携带 page_id + L340-345 supersedes 接口（MVP 保留） |
| S12 | cron 注册行 + must-sync 外 | ✅ | conv_sync.sh L4-5 注册行注释（OC 执行）；deploy-drift-audit-2026-08-15.md §1.2 must-sync 定稿 4 脚本（oc_wake_check/sentinel_alert/devppl_autopilot/close）conv_sync 零命中 → repo 路径直调天然最新 |

---

## 4. 独立探针（§5 P1-P8）

### P1 真实 profile 数据端到端（qa-exec 新增高风险项）✅

- **环境**：MEM_CONV_PROFILE_ROOT=/root/.hermes/profiles（真实 8 profile 只读扫描）；MEM_WIKI_PATH/MEM_DB_PATH/MEM_SYNC_STATE/MEM_CONV_QUEUE/MEM_KANBAN_DB/MEM_GAI_FILE 全指 /tmp/qa-exec-p1（temp）
- **结果**：
  - anchor tick（first_run=1）：exit 0，events 0（D5 语义：初始 cursor=已合格 max started_at，不处理历史）✅
  - discover tick：exit 0，conversation=1 correction=0（无纠正信号），生成骨架页 `raw/sessions/orchestrator:20260817_182924_65cff3c8.md`（1 页）✅
  - cursor 推进：state.json sources.conversation.last_event_id 记录到 `1786962564.6399913|orchestrator:...|1` ✅
  - **真实 state.db md5**：聚合快照前后差异被定位为**并发 game-engine agent 会话自身写入**（该 profile WAL 活跃 6.3MB、agent.log 更新、state.db mtime 23:46:54 晚于两次 tick 23:46:46/23:46:51）；**对照实验 tick 前后同秒 md5 一致（54d41f44...）→ 被测代码零写** ✅
- **判定**：adapter 对真实 6+ profile state.db 可发现合格会话、生成骨架页到 temp wiki、L0 只读铁律成立（P4 mode=ro 静态+实测双重证据）。

### P2 OBS-A 复验 ✅（不复判，确认 dev 登记）

- 代码路径：cli.py L1225-1228 `_conv_queue_backlog` 无 MEM_CONV_QUEUE env → `Path(_wiki).parent / ".pipeline" / "conv_queue.json"`（默认）
- 实测：默认路径放 pending=2 队列 + MEM_CONV_QUEUE 指向 pending=1/abandoned=1 队列 → 无 env 读默认（2 积压）、带 env 读生产路径（2 积压）→ **读路径差异复现，但生产链路 conv_sync.sh L24 已导出 MEM_CONV_QUEUE 统一** → 非验收缺陷，观察项确认。

### P3-P8 探针脚本（17/17 PASS）✅

| # | 探针 | 断言 | 结果 |
|---|------|:---:|:---:|
| P7a | 锚定 tick exit 0 | 0 | ✅ |
| P7b | 锚定 tick 零 memctl（A8） | 0 | ✅ |
| P3a | 发现 tick exit 0 | 0 | ✅ |
| P3b | 骨架页=6（alpha 3 + beta 3） | 6 | ✅ |
| P3c | correction 事件=3（同指纹 2 + 异指纹 1） | 3 | ✅ |
| P3d | cron 噪声无页 | 0 | ✅ |
| P3e | A4 SQL 直查聚合 2+1 | OK | ✅ |
| P3f | 单弱词「应该」不检出 | 0 | ✅ |
| P4 | state.db md5 前后一致（L0 只读） | 一致 | ✅ |
| P7c | 无新会话 tick 零 memctl（A8） | 0 | ✅ |
| P8a | 重放 2 次骨架页数不变（A5） | 6=6 | ✅ |
| P8b | 重放 2 次 correction 事件数不变（A5） | 3=3 | ✅ |
| P6a | 垃圾 LLM exit 0 → tick rc=0（fail-open） | 0 | ✅ |
| P6b | 骨架页不受策展影响 | 6=6 | ✅ |
| P6c | **观察：垃圾输出 exit 0 → concepts 页 0→4（F1-MINOR 复现）** | — | ⚠ 登记 |
| P6d | exit-1 三次失败不产记忆页 | 0 增量 | ✅ |
| P6e | exit-1 ≥3 次 → abandoned 非空（重试语义） | 队列轨迹 pending=2→2→0 abandoned=0→0→2 | ✅ |
| P5 | 队列损坏（非法 JSON）→ conv_curate exit 0 | 0 | ✅ |

---

## 5. A1-A12/R5 验收映射核对

| # | 验收要点 | 证据链 | 判定 |
|---|---------|--------|:---:|
| A1 | feishu 会话 → ≤1 tick 骨架页 | test_conv_sync + P3b（6 页含 feishu×4）+ P1（真实 orchestrator 会话 1 tick 产页） | ✅ |
| A2 | cli 全 profile 覆盖（静置主路径） | test_conv_discovery_idle_fallback + P3b（cli 页 alpha/beta 各 1） | ✅ |
| A3 | 噪声/未结束/低消息/archived 不生成 | P3d（cron 0 页）+ test_conv_sync 白名单段 | ✅ |
| A4 | 纠正复发计数可查询（2 同指纹+1 异指纹 → 3） | P3c（events=3）+ P3e（SQL GROUP BY 2+1） | ✅ |
| A5 | 幂等重放 3 次页数/事件数不变 | P8a/P8b（重放 2 次 6/3 不变）+ test_conv_sync 幂等段 | ✅ |
| A6 | state.db md5 全程一致 | P4（temp 夹具）+ P1 对照实验（真实库 tick 前后 md5 一致） | ✅ |
| A7 | fail-open（库损坏/LLM 失败） | P5（队列损坏 exit 0）+ P6a（LLM exit 0）+ test_conv_sync A7 段 | ✅ |
| A8 | work-gated 零 memctl | P7b/P7c（锚定 + 无新会话均零调用） | ✅ |
| A9 | pytest 全绿 + 集成 ≥10 断言 | 246/0 + 55 断言（≥12） | ✅ |
| A10 | 成本护栏全 env 可调 | test_conv_sync A10 段 + P6d/P6e（TOP_N/retries/abandoned 实测） | ✅ |
| A11 | 记忆页双链回 conversation + lint | S11（curate-source 携带 page_id）+ test_conv_sync A11 段（假 LLM 成功态） | ✅ |
| A12 | adapter 继承 + 一行注册 + 引擎零语义 | S1/S2/S3 + test_sources_conversation | ✅ |
| R5 | memctl status 三计数 | cli.py L1246 + P2（策展队列积压读路径）+ test_status_three_counts | ✅ |
| 部署 | conv_sync.sh cron 注册 → OC | S12（注册行交付 + must-sync 外） | ✅（部署动作归 OC） |

**MVP 门禁（A1-A9）：9/9 全过。**

---

## 6. 分级标准对照（qa-finding-classification.md v1.0）

### 6.1 本卡发现分级

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 判定公式匹配 | 定级 |
|------|:---:|:---:|:---:|:---:|------|:---:|
| **F1**（继承确认）：策展 LLM C 命令 exit 0 垃圾输出 → learn 仍落垃圾记忆页（P6c：concepts 0→4，页体="this is not markdown, just garbage output"） | ✅（垃圾页可见，记忆污染） | ❌（机械层骨架/correction 不受影响） | ✅（OC 部署正确 LLM 命令；人工清理） | 否 | §1.2 标准判定：可感知 ∧ 非阻断 ∧ 有 workaround → MINOR | **MINOR** |
| **OBS-A**（复验确认）：standalone memctl status 无 MEM_CONV_QUEUE env 时策展队列积压读默认路径 | ✅（观察期读数可能错） | ❌（生产链路 conv_sync.sh 导出 env 统一） | ✅（跑 status 时同 env） | 否 | 非验收缺陷（dev 已登记） | **观察项** |

### 6.2 判定公式对照

- **BLOCKER 判例未触发**：无「合格 feishu/cli 会话不产骨架页」类发现（P1/P3b 均正常产页）；无安全漏洞（adapter mode=ro 零写实测）。
- **MAJOR 判例未触发**：无「correction 误报率异常」类发现（P3f 单弱词不检出验证门控有效）。
- **MINOR 判例触发 1 例**：F1（详见 6.1）。
- **SUGGESTION 判例未触发**：无文档/实现不一致且功能正确项。

### 6.3 SLA 对照

| SLA 条款 | 对照 |
|---------|------|
| BLOCKER 4h 响应 + 8h 定位 + 24h 方案 | 本卡 0 BLOCKER，不适用 |
| 论证流程（发现→研发评估→通过/驳回/暂缓） | F1 已在 QA-D1 登记并经 VA/dev 评估（dev claim 接受），本卡仅复验确认，无需重新启动论证 |
| 有成本申诉 | 未触发（无驳回） |
| 产品红线（BLOCKER 暂缓须 Frank 签字） | 未触发 |

### 6.4 发布门禁对照

| 门禁项 | 要求 | 本卡 |
|--------|------|:---:|
| BLOCKER | =0 | 0 ✅ |
| MAJOR | ≤3 | 0 ✅ |
| 安全漏洞 | =0 | 0 ✅ |
| 未裁定申诉 | =0 | 0 ✅ |
| **结论** | | **通过，可发版** |

---

## 7. 风险登记回顾（方案 §8）

| # | 风险 | 处置 |
|---|------|------|
| R1 | main 已前进（da145d7 > 8fec922） | 前置确认 8fec922 为祖先 + MEM-009 文件零改动 → 已闭环 |
| R2 | pytest 超长 | devPPL pytest 后台 134.78s 完成，与探针并行 → 已闭环 |
| R3 | P1 触碰真实 state.db | mode=ro 保证；聚合 md5 差异定位为并发 agent 写入，对照实验证被测代码零写 → 已闭环 |
| R4 | OBS-A 误判 | P2 复验确认 dev 登记成立，未复判 → 已闭环 |
| R5 | cron 注册依赖 OC | S12 确认注册行交付，真实 tick 心跳证据归 qa-post/OC → 标注部署依赖 |
| R6 | test_conv_sync 依赖 mem-core 检出 | 脚本自带 mem_core_ok 预检 + 前置确认 mem-core main 含 MEM-009 产物 → 已闭环 |
| R7 | F1-MINOR | 复验确认（P6c），MINOR 不阻塞；建议 conv_curate 后续加输出 sanity check 或 OC 部署时验证 C 命令 |

---

## 8. 结论与建议

**结论**：MEM-009 对话提取（机械层骨架+correction / 语义层策展）QA-EXEC 独立执行**全部验收通过**——基线四套全绿（246/55/80/281 零新增）+ 静态 S1-S12 + 探针 P1-P8 全过 + A1-A12/R5 逐项成立。**发布门禁通过（BLOCKER=0, MAJOR=0）**。

**发现清单**：
- F1-MINOR（继承）：策展 LLM exit 0 垃圾输出无内容校验 → 垃圾记忆页落库。建议：conv_curate 侧加输出 sanity check（如必须含 frontmatter/指定结构），或 OC 部署时验证 C 命令。
- OBS-A（观察项）：standalone memctl status 无 MEM_CONV_QUEUE env 时队列积压读默认路径。建议：后续独立小改对齐（默认路径指向 devPPL .pipeline/）。

**部署依赖**：conv_sync.sh cron 注册（*/5 * * * *）归 OC 执行（S12）；真实 tick 心跳证据归 qa-post/OC（同 MEM-007 D12 先例）。

---

## 附：执行产物

- 测试方案：docs/qa/mem009-conversation-extraction-test-plan.md（v1.0，前棒交付，本卡复用于执行）
- 探针脚本：scripts/qa_mem009_probes.sh（17 断言）
- 本报告：docs/qa/mem009-conversation-extraction-test-report.md
- WIP 笔记：.pipeline/wip/t_f91a64c5.md
