# MEM-009 对话提取 — QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-19 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_2fc5fd0a [DEV-QA-D1] MEM-009 对话提取 — 对话/纠正自动提取记忆与经验（蓝图方向A，依赖 MEM-007 SourceAdapter）（DPL-073）
> 被测代码：**devPPL main @ 8fec922**（merge t_1ab2ab46）+ **mem-core main @ 4f67a75**（conversation adapter + cli 命令面，均已合入 main）
> 上游文档：
> - PRD：`/workspace/mem-core/wiki/projects/devppl/prd/mem009-conversation-extraction-prd.md`（v1.0，276 行，t_3f5c8462）
> - 架构：`/workspace/mem-core/wiki/projects/devppl/arch/arch-mem009-conversation-extraction.md`（v1.0，714 行，t_71a9b5f9，§8 测试方案）
> - VA：t_6d6474ee（done，25/25 PASS，0 FALSIFIED；4 dev 子卡 t_11d3cf65 11/11 + t_9a3c1371 3/3 + t_c37ced5a 4/4 + t_1ab2ab46 7/7）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> - 基线测试：mem-core pytest（246 断言）+ `scripts/test_conv_sync.sh`（55 断言）+ `scripts/test_mem_sync.sh`（80 断言）+ devPPL pytest（281 passed / 存量失败集零新增）

---

## 0. 执行摘要（测试设计阶段结论）

| 项 | 结果 |
|---|---|
| 被测代码状态 | **双仓均已合入 main**：devPPL @ 8fec922（mem_sync.py 计数键 + conv_sync.sh + conv_curate.py + test_conv_sync.sh）+ mem-core @ 4f67a75（conversation.py + cli.py 命令面 + 2 个新测试文件） |
| 研发验证状态 | 4 dev 子卡 25/25 claims；VA t_6d6474ee 独立复核 **25/25 PASS，0 FALSIFIED** |
| QA 独立核查（本卡已实测） | mem-core pytest **246 PASS**（194.68s）+ test_conv_sync.sh **55/0** + test_mem_sync.sh **80/0** + devPPL pytest **281 passed / 8 failed / 1 error 零新增**（724.80s）+ 探针 **17/17 PASS** + 静态 S1-S12 全过（§3/§4/§5） |
| D1 前置发现 | **F1-MINOR**（策展 LLM exit 0 垃圾输出无内容校验 → 垃圾记忆页落库，探针 P6c 实测；详见 §5 P6 + 风险 §8）；0 BLOCKER/MAJOR；观察项继承 dev 登记 **OBS-A**（standalone `memctl status` 无 MEM_CONV_QUEUE env 时策展队列读错路径，生产链路已由 conv_sync.sh 导出 env 统一，非验收范围） |
| 工作量评估 | 预计 **14-22 轮（中位 18）≤ 20 轮阈值（中位口径）→ 不拆卡**（单张 QA 执行子卡），详见 §7 |

**结论**：dev 交付与 VA 复核一致，MEM-009 双层管线（机械层骨架+correction / 语义层策展）经 QA 独立核查全部成立。qa-exec 单卡执行：前置确认双仓被测 commit → 基线四套全量复跑 → 静态 S1-S12 → 独立探针 P1-P8 → A1-A12/R5 验收逐项核对 → 报告。**本卡 D1 已独立实测：mem-core pytest 246/0 + conv_sync 55/0 + mem_sync 80/0 + devPPL pytest 281/8/1 零新增 + 探针 17/17 + 静态 S1-S12。**

---

## 1. 测试范围概览

```
被测模块                           PRD 验收       arch 章节       dev 交付（已合入）
──────────────────────────────────────────────────────────────────────────────────────────
memcore/sources/conversation.py    A1-A6/A12      §2/§3          第三源 adapter（白名单发现/机械摘要/强弱词纠正检测/复合游标/双 kind Event）
memcore/sources/__init__.py        A12            §2.1           SOURCES["conversation"] 一行注册
memcore/cli.py                     A4/A5/R5       §4             add conversation / note --correction / query --corrections / status 三计数
mem-core tests/                    A9             §8.1           test_sources_conversation.py(14) + test_cmd_conversation.py(6)
scripts/mem_sync.py                A12            §5.1           _COUNTER_KEYS +conversation/correction/curated（引擎唯一改动）
scripts/conv_sync.sh               A1-A8/A10/A11  §5.2/§8.2     两阶段 fail-open cron 包装（36 行）
scripts/conv_curate.py             A10/A11/R5     §6            打分入队/原子写/Top-N/learn --llm/retries/abandoned（483 行）
scripts/test_conv_sync.sh          A1-A8/A10/A11/A12/R5  §8.2    55 断言集成测试（432 行）
```

**零改动确认（回归范围）**：kanban 源（MEM-007 第一环）、gai 源、mem_sync 引擎主循环/状态机/游标分桶逻辑零改动（仅 _COUNTER_KEYS 扩三键，git diff 8fec922^..8fec922 证实）；memctl 既有命令面（add note/learn/query）零改动（仅新增 conversation 子命令与 --correction/--corrections flags）。

### 1.1 验收标准映射（PRD A1-A12 + R5）

| # | 验收要点 | dev 测试锚点 | QA 复核 |
|---|---------|-------------|:---:|
| A1 | feishu 会话 → ≤1 tick 骨架页（raw/sessions/<profile>:<sid>.md + page_type: conversation） | test_conv_sync.sh + test_cmd_conversation.py | ✅ 基线含 + 探针 P1/P3 |
| A2 | cli 全 profile 覆盖（静置主路径：无 ended_at + 超 6h → 合格） | test_conv_discovery_idle_fallback | ✅ 基线含 |
| A3 | 噪声（cron 源）/ 未结束 / 低消息 / archived → 不生成 + skipped 可见 | test_conv_discovery_whitelist/user_min/noise_injection | ✅ 基线含 |
| A4 | 纠正复发计数可查询（`SELECT COUNT(*) FROM events WHERE kind='correction' AND page_id=?`）2 同指纹 + 1 异指纹 → total=3 聚合 2+1 | test_note_correction_dedup / test_query_corrections | ✅ 基线含 + 探针 P3 独立 SQL 直查 |
| A5 | 幂等重放 3 次页数/事件数不变（页去重 + message_id 去重） | test_note_correction_dedup / test_conv_cursor_crash_window | ✅ 基线含 + 探针 P8 |
| A6 | state.db md5 全程一致（engine+adapter 只读 L0，mode=ro） | test_conv_readonly + test_conv_sync.sh A6 段 | ✅ 基线含 + 探针 P4 |
| A7 | fail-open（库损坏/LLM 失败） | test_conv_sync.sh A7 段（删 profile db → exit 0 其余照常） | ✅ 基线含 + 探针 P5 |
| A8 | work-gated：无新会话 → 零 memctl 调用 | test_conv_sync.sh A8 段（memctl-wrapper marker） | ✅ 基线含 + 探针 P7 |
| A9 | pytest 全绿 + 集成 ≥10 断言 | mem-core 246 + test_conv_sync 55（≥12） | ✅ 本卡实测 |
| A10 | 成本护栏全 env 可调（MEM_CONV_CURATE_LLM/TOP_N/QUEUE_MAX/DONE_MAX） | test_conv_sync.sh A10 段（LLM exit 1 + Top-N 生效） | ✅ 基线含 + 探针 P6 |
| A11 | 记忆页双链回 conversation + lint 零新增 | test_conv_sync.sh A11 段（假 LLM 成功态） | ✅ 基线含 + 探针 P6 |
| A12 | adapter 继承 + 一行注册 + 引擎零语义 | grep 清单（§8.4）+ test_sources_conversation | ✅ 静态 S1/S2/S3 |
| R5 | memctl status 三计数（conversation 页 / correction 事件 / 策展队列积压） | test_status_three_counts + test_conv_sync.sh R5 段 | ✅ 基线含 + OBS-A 验证（P2） |
| 部署 | conv_sync.sh cron 注册（§7 行）→ OC 执行；repo 路径直调不进 must-sync | conv_sync.sh 头部注释 + DPL-048 审计 | 静态 S12 + 观察项（真实 tick 归 qa-post/OC） |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 wiki/DB/queue）：

| 项 | 配置 |
|---|---|
| 被测分支 | devPPL **main @ 8fec922** + mem-core **main @ 4f67a75**（qa-exec 若已前进，先 `git merge-base --is-ancestor` 确认被测 commit 为祖先） |
| 隔离 wiki | test_conv_sync.sh 自建 $TMPT/wikiroot/wiki（git init）+ $TMPT/mem_meta.db |
| 隔离 profile | $TMPT/profiles/{alpha,beta} 临时 state.db（含 feishu/cli/cron 会话夹具） |
| env 桩 | MEM_CONV_PROFILE_ROOT / MEM_WIKI_PATH / MEM_DB_PATH / MEM_SYNC_STATE / MEM_CONV_QUEUE / MEM_KANBAN_DB / MEM_GAI_FILE / MEM_CONV_CURATE_LLM 全部指向 temp |
| 真实库只读核对 | `devppl_query.sh`（禁止裸 python3 -c 内联读 DB，tirith MEDIUM 审批门限） |
| 执行命令 | `cd /workspace/mem-core && .venv/bin/python -m pytest -o addopts='' -q`（246）+ `bash scripts/test_conv_sync.sh`（55）+ `bash scripts/test_mem_sync.sh`（80）+ `cd /workspace/devPPL && python3 -m pytest tests/ -q`（281，后台 ~10min，对照 VA 存量失败集 14+1 零新增）+ 静态核对 + 探针 `scripts/qa_mem009_probes.sh` |
| mem-core pytest 注意 | 必须用 `.venv/bin/python` + `-o addopts=''`（SUB-3 同款命令；裸 python3 可能缺依赖） |

**执行前置（qa-exec 阶段）**：
1. 双仓被测 commit 确认：devPPL `git log --oneline -1` 应含 8fec922 为祖先；mem-core 应含 4f67a75（conversation.py + cli.py 在 main）
2. `bash -n scripts/conv_sync.sh scripts/test_conv_sync.sh scripts/test_mem_sync.sh` + `python3 -m py_compile scripts/conv_curate.py scripts/mem_sync.py`
3. 基线四套全量复跑全绿后，再执行独立探针

---

## 3. 基线回归（本卡 D1 已独立实测）

| 测试 | 断言数 | 本卡实测 | qa-exec 要求 |
|------|:---:|:---:|:---:|
| mem-core pytest（含新 20 用例） | 246 | **246 passed，EXIT=0（194.68s，2026-08-19 独立复跑）** | 复跑确认全绿 |
| test_conv_sync.sh（A1-A8/A10/A11/A12/R5） | 55 | **PASS=55 FAIL=0**（2026-08-19 独立复跑） | 复跑确认全绿 |
| test_mem_sync.sh（MEM-007 回归） | 80 | **PASS=80 FAIL=0**（2026-08-19 独立复跑） | 复跑确认全绿 |
| devPPL pytest | 281 基线 | **281 passed / 8 failed / 1 error（724.80s，2026-08-19 独立复跑）** — 失败集 = test_memory_middleware_qa ×3 + test_slice2_d1_qa ×5 + ERROR test_P2-02_full ×1，与 dev claim 同款；git diff a221b19..8fec922 对三个失败文件**零改动** → **零新增失败**（VA 的 14+1 含 test_p0_18_qa ×6，为 OC live 脚本环境漂移） | 复跑对照存量失败集，**零新增失败** |

### 3.1 本卡 D1 实测摘要（2026-08-19）

| 项 | 结果 |
|---|---|
| mem-core pytest | **246 passed / 0 failed**（独立复跑，194.68s） |
| test_conv_sync.sh | **PASS=55 FAIL=0 / ALL TESTS PASSED**（独立复跑） |
| test_mem_sync.sh | **PASS=80 FAIL=0 / ALL TESTS PASSED**（独立复跑） |
| devPPL pytest | **281 passed / 8 failed / 1 error（724.80s）** — 失败集与 dev claim 同款（memory_middleware ×3 + slice2_d1 ×5 + P2-02 ERROR），git diff 证三个失败文件零改动 → **零新增失败** |
| 探针 P3-P8 | **17/17 PASS**（scripts/qa_mem009_probes.sh，2026-08-19 独立实测） |
| 静态 S1-S12 | 全过（D1 已实测，见 §4） |
| D1 发现 | **F1-MINOR**（策展 LLM exit 0 垃圾输出无内容校验 → 垃圾记忆页落库）；**OBS-A**（standalone memctl status 队列路径，dev 已登记） |

---

## 4. 静态核查（S1-S12，qa-exec 逐项复验）

| # | 核查点 | 方法/证据 |
|---|--------|---------|
| S1 | SOURCES 注册含 "conversation"（A12） | `grep -n conversation memcore/sources/__init__.py` |
| S2 | 引擎零对话语义（A12）：mem_sync.py grep conversation/correction 仅命中 _COUNTER_KEYS 与注释 | `grep -n "conversation\|correction" scripts/mem_sync.py` |
| S3 | SQL 只存在于 adapter：mem_sync.py / conv_curate.py / memcore/cli.py grep state.db/sessions/messages 零命中 | `grep -rn "state.db\|sessions\|messages" scripts/mem_sync.py scripts/conv_curate.py memcore/cli.py` |
| S4 | adapter 只读三铁律：conversation.py 所有 connect 用 `mode=ro` URI（A6 前置） | `grep -n "mode=ro\|connect" memcore/sources/conversation.py` |
| S5 | adapter 无写语句：conversation.py 无 INSERT/UPDATE/DELETE | `grep -n "INSERT\|UPDATE\|DELETE" memcore/sources/conversation.py`（应零命中） |
| S6 | _COUNTER_KEYS 含 conversation/correction/curated 三键（D7） | `grep -n "_COUNTER_KEYS" scripts/mem_sync.py` → L67 tuple |
| S7 | conv_sync.sh 两阶段 fail-open 包装：set -uo pipefail 无 -e、两阶段各取 rc、恒 exit 0 | 读 conv_sync.sh L16-36 |
| S8 | conv_curate.py：队列原子写（temp+os.replace）、打分规则（纠正+3/feishu+2/消息>40+1/决策词+2，score≥3 入队）、Top-N=3 env 可调、retries<3/≥3 abandoned | `grep -n "os.replace\|score\|TOP_N\|retries\|abandoned" scripts/conv_curate.py` |
| S9 | memctl 命令面：add conversation 页模板+幂等 exit 1；note --correction 三元去重键 (page_id,fingerprint,message_id)+只写 events；query --corrections 对话级+links 记忆级聚合；status 三计数 | `grep -n "_add_conversation\|_correction_exists\|_query_corrections\|_conv_queue_backlog" memcore/cli.py` |
| S10 | fingerprint 规则：`correction:<category>:<sha256(norm_lede)[:12]>`，关键词不进指纹 | `grep -n "fingerprint\|sha256" memcore/sources/conversation.py` |
| S11 | A11 双链回 conversation：conv_curate 组装输入含来源对话双链、learn --llm 产物 lint 门禁 | `grep -n "来源对话\|supersedes\|lint" scripts/conv_curate.py` |
| S12 | cron 注册行交付（§7 注释，注册权归 OC）+ 脚本 repo 路径直调不进 must-sync | 读 conv_sync.sh L4-5 + `.pipeline/reports/deploy-drift-audit-2026-08-15.md` must-sync 清单 |

---

## 5. 独立探针（P1-P8，qa-exec 阶段执行；D1 已具备实测基础）

| # | 探针 | 目标 | 命令/断言 | 状态 |
|---|------|------|----------|:---:|
| P1 | **真实 profile 数据端到端**（temp wiki/state，L0 只读） | 验证 adapter 对真实 6 profile state.db 可发现合格会话、生成骨架页到 temp wiki、写 correction 事件 | env 指 temp；`python3 scripts/mem_sync.py --source conversation`；断言：exit 0 + 骨架页出现 + state.json cursor 推进 + 真实 state.db md5 不变 | qa-exec 执行（D1 设计） |
| P2 | OBS-A 验证：standalone `memctl status` 无 MEM_CONV_QUEUE env 时策展队列读路径 | 复现 dev 登记观察项：默认路径 <wiki.parent>/.pipeline/conv_queue.json vs 实际 devPPL .pipeline/；确认生产链路由 conv_sync.sh 导出 env 统一、非验收缺陷 | 读 cli.py _conv_queue_backlog L1218-1228 + 无 env 跑 status 观察输出 | qa-exec 复验 |
| P3 | 跨会话 fingerprint 聚合（A4 独立 SQL 直查） | 2 个会话同纠正文案 → 同 fingerprint → 计数聚合 2+1；异文案 → 异指纹；单弱词不检出 | `bash scripts/qa_mem009_probes.sh`（P3a-P3f） | ✅ D1 已实测 17/17 |
| P4 | A6 md5 独立复核 | 完整 tick（阶段①+②）前后所有真实 profile state.db md5 一致 | md5sum 前后对比（独立复跑） | ✅ D1 已实测 |
| P5 | 队列损坏 fail-open | conv_queue.json 写坏（非法 JSON）→ conv_curate exit 0 不崩、骨架/correction 不受影响 | 手动损坏 queue + 跑 conv_curate + 断言 rc=0 | ✅ D1 已实测 |
| P6 | LLM 输出垃圾（非 md 草稿，exit 0） | 探针实测：rc=0 fail-open；**垃圾文本仍落记忆页（concepts 0→4，登记 F1-MINOR）**；exit-1 三次失败 → 不产页、abandoned 非空（重试语义） | `bash scripts/qa_mem009_probes.sh` | ✅ D1 已实测 |
| P7 | work-gated 零调用独立复核 | 锚定 tick 零 memctl（D5 首跑）；无新会话 tick 零 memctl（A8） | 复用 test_conv_sync.sh A8 段（独立复跑） | ✅ D1 已实测 |
| P8 | 幂等重放 3 次独立复核 | 页数/事件数不变（A5） | 完整管线重放 2 次 + 计数对比 | ✅ D1 已实测 |

> P1 注意：**MEM_WIKI_PATH/MEM_DB_PATH/MEM_SYNC_STATE 必须指向 temp**（防真实 wiki/状态被写）；MEM_CONV_PROFILE_ROOT 指向真实 /root/.hermes/profiles（只读扫描）；适配器 mode=ro 保证 L0 不被写。与 DPL-061 P5 教训一致（SEEN_FILE 指向 temp 防污染 live 状态）。

---

## 6. 分级标准对照（qa-finding-classification.md v1.0）

### 6.1 D1 实测发现分级（F1-MINOR）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|
| F1：策展 LLM C 命令 exit 0 垃圾输出（非 md）→ learn 仍落垃圾记忆页（探针 P6c：concepts 页 0→4，页体 = "this is not markdown, just garbage output"） | ✅（垃圾页可见于 wiki，记忆污染） | ❌（机械层骨架/correction 不受影响；策展机制仍运行） | ✅（OC 部署正确 LLM 命令；人工清理垃圾页） | 否 | **MINOR**（用户能忍，不阻塞发版；对照标准 §5 MINOR 行） |
| OBS-A：standalone `memctl status` 无 MEM_CONV_QUEUE env 时策展队列积压读错路径（默认 <wiki.parent>/.pipeline/ vs 实际 devPPL） | ✅（观察期读错值） | ❌（生产链路由 conv_sync.sh 导出 env 统一） | ✅（跑 status 时同 env） | 否 | **观察项**（dev 已登记，非验收缺陷；建议独立小改对齐） |

> F1 说明：该行为继承自 MEM-007 learn 管线（`_run_llm` 信任编译器 stdout，rc 协议 0=成功），非 MEM-009 新增写路径；架构 §3.4 明确「语义准确率归 QA 阶段评估」，MVP A11（双链+lint）仍满足 → MINOR 不阻塞发版。建议后续在 conv_curate 侧加输出 sanity check（如必须含 `---` frontmatter 或指定结构）或依赖 OC 部署正确 C 命令。

### 6.2 判定公式 / 分级示例

- 若 qa-exec 发现「合格 feishu/cli 会话不产骨架页（如白名单 SQL 误排除、摘要生成抛异常导致事件丢失）」→ 用户可感知（Frank 的对话不被记录）+ 功能阻断（对话流核心失效）+ 无 workaround → **BLOCKER**（对照标准 §5 表 BLOCKER 行）。
- 若发现「correction 检测误报率异常（弱词门控失效致大量无意义 events）」→ 用户可感知（计数虚高）+ 功能阻断（A4 计数语义失真）+ workaround（人工忽略/MUTE）→ **MAJOR**（MVP 只断言计数机制，语义准确率按架构 §3.4 归 QA 评估）。
- 若发现「日志/输出格式与架构文档略有出入（如 conv_sync.log 行格式）」→ 用户可感知 + 不阻断（功能正常）+ workaround（人读日志理解）→ **MINOR**。
- 若发现「注释/文档与实现细节不一致但功能正确」→ 不阻塞、不劣化 → **SUGGESTION**。

---

## 7. 工作量评估与拆卡决策（任务 body 要求）

### 7.1 评估依据

| 阶段 | 内容 | 预计轮数 |
|------|------|:---:|
| ① 前置检查 | 双仓被测 commit 确认（8fec922/4f67a75 为祖先）+ bash -n + py_compile（4 项） | 1-2 |
| ② mem-core pytest | 246 断言（实测 194.68s/遍，可能 2 次迭代） | 2-3 |
| ③ test_conv_sync.sh | 55 断言（实测 <1min/遍） | 1-2 |
| ④ test_mem_sync.sh | 80 断言 | 1 |
| ⑤ devPPL pytest | 281 存量基线（~10min 后台 + 失败集对照 VA 记录 14+1） | 2-3 |
| ⑥ 静态核对 | S1-S12 逐项（双仓 grep/读码） | 2-3 |
| ⑦ 独立探针 | P1-P8（P1 真实数据 e2e 为新增高风险项；P3-P8 复用/改造 test_conv_sync 夹具） | 3-5 |
| ⑧ AC 核对 + 报告 | A1-A12/R5 逐项核对 + 写 test_report.md + [PRODUCES]/[CLAIM] + 飞书推送 | 2-3 |
| **合计** | | **14-22（中位 18）** |

> 校准说明：本任务为**跨双仓集成型改动**（mem-core adapter+命令面 + devPPL 引擎+脚本），但研发已交付完整测试体系（mem-core pytest 20 新用例 + test_conv_sync.sh 55 断言 + test_mem_sync.sh 80 回归），VA 已独立复核 25/25，**双仓均已合入 main（无 MEM-007 的 OBS-1 未合入风险）**。QA 主要是**独立复跑 + 静态核对 + 少量边界探针**。对比 MEM-007 QA-D1（14-20 中位 17 不拆）与 DPL-061 QA-D1（13-19 中位 16 不拆），本卡测试体系更完整（55+80 断言 vs 47+29），但多一套 devPPL pytest 281 对照与真实数据探针 P1，诚实区间 **14-22 轮（中位 18）**。

### 7.2 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | **14-22 轮（中位 18）≤ 20 轮阈值（中位口径，与 MEM-007/DPL-061 先例一致）→ 不拆**（上限 22 由 P1 真实数据 e2e 与 pytest 对照调试驱动，qa-exec 可吸收：pytest 后台跑与静态/探针并行） |
| 模块依赖 | 全部验收共享同一批基线（mem-core 246 + conv 55 + mem 80 + devPPL pytest）与同一被测对象（双仓 main）；静态/探针/AC 核对均为独立只读操作，无串行数据依赖 |
| 并行收益 | 无——单被测对象 + 共享基线环境，拆卡只引入 merge/交接成本 |
| 兜底 | 若 qa-exec 实际执行中发现 P1 真实数据探针或 pytest 对照调试成本超预期（>20 轮），按建卡铁律在职责内拆子卡（assignee=game-qa，parents 挂当前卡） |

**决策：不拆卡（[QA-SUB-SPLIT] 1，单张 QA 执行子卡由 autopilot 按链自动建）。**

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | qa-exec 时 main 已前进（其它链 merge） | 被测对象变化 | 执行前置确认 8fec922/4f67a75 为祖先；MEM-009 相关文件用 git log 确认未被动过 |
| R2 | devPPL pytest ~10min 超长 + mem-core pytest ~3min | 单轮迭代耗时 | 后台跑 + 与静态/探针并行；只对照 VA 记录的存量失败集（14+1）零新增 |
| R3 | P1 真实数据 e2e 触碰真实 profile state.db | 只读风险 / 发现真实数据形态问题 | mode=ro URI 保证；MEM_WIKI/DB/STATE 全指 temp；若真实数据触发异常按分级标准登记 |
| R4 | OBS-A（standalone status 队列路径）可能被误判为缺陷 | 分级偏差 | 明确其为 dev 已登记观察项（生产链路 env 统一），非验收范围；探针 P2 只验证不复判 |
| R5 | cron 注册（S5）依赖 OC | 真实链路验收不完整 | conv_sync.sh 已交付 §7 注册行；真实 tick 心跳证据归 qa-post/OC（同 MEM-007 D12 先例）；QA 报告明确标注部署依赖 |
| R6 | test_conv_sync.sh 依赖 mem-core 检出（MEM_CORE_PATH 默认 /workspace/mem-core） | 环境漂移 | 脚本自带 mem_core_ok 预检（exit 2 提示）；qa-exec 前置确认 mem-core main 含 MEM-009 产物 |
| R7 | **F1-MINOR**（D1 实测）：策展 LLM exit 0 垃圾输出 → 垃圾记忆页落库 | 若 OC 部署的 C 命令输出异常（如 LLM 报错却 exit 0），wiki 会积累垃圾页 | D1 已登记分级（MINOR 不阻塞）；建议 conv_curate 后续加输出 sanity check（frontmatter/结构校验）或 OC 部署时验证 C 命令；qa-exec 在报告中复核 |

---

## 附：与本方案相关的既有文档

- MEM-009 PRD：`/workspace/mem-core/wiki/projects/devppl/prd/mem009-conversation-extraction-prd.md`（v1.0，t_3f5c8462）
- MEM-009 架构：`/workspace/mem-core/wiki/projects/devppl/arch/arch-mem009-conversation-extraction.md`（v1.0，t_71a9b5f9，§8 测试方案/§9 A1-A12 映射）
- VA 复核：t_6d6474ee（25/25 PASS，0 FALSIFIED）+ `/workspace/.va_reports/20260819T232156.json`
- 基线测试：`/workspace/mem-core/tests/test_sources_conversation.py`（14 用例）+ `test_cmd_conversation.py`（6 用例）+ `scripts/test_conv_sync.sh`（55 断言）+ `scripts/test_mem_sync.sh`（80 断言）
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0
- 类似 D1 方案参考：`docs/qa/mem007-auto-record-test-plan.md`（MEM-007，14-20 轮不拆先例）、`docs/qa/dpl061-watchdog-unify-test-plan.md`（DPL-061，13-19 轮不拆先例）
