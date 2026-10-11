# QA-D2 结果严重度评审报告 — MEM-009 对话提取

> 版本：v1.0 | 日期：2026-08-20 | 执行人：game-qa（QA-D2 结果严重度评审卡 t_ac88ed89）
> 上游执行报告：`docs/qa/mem009-conversation-extraction-test-report.md`（QA-EXEC t_f91a64c5 @ 996054a，分支 wt/t_f91a64c5）
> 测试方案：`docs/qa/mem009-conversation-extraction-test-plan.md`（QA-D1 t_2fc5fd0a）
> 被测提交：**devPPL main @ da145d7**（8fec922 为祖先，MEM-009 文件 8fec922..HEAD 零改动）+ **mem-core main @ b200a6d**（4f67a75/61457ae 均为祖先，4f67a75..HEAD 仅 wiki 文档改动）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 评审性质：QA-D2 独立复验（非转述 QA-EXEC），复核分级判定 + 漏报检查 + 处置建议

---

## 0. 评审结论（TL;DR）

| 评审项 | 结果 | 证据 |
|---|---|---|
| 分级判定复核（QA-EXEC 结论 0 BLOCKER/0 MAJOR/1 MINOR F1/1 观察 OBS-A） | ✅ **复核一致** | §2 |
| 基线全量独立复跑（合并后 main 上） | ✅ **mem-core pytest 246 PASS / test_conv_sync 55/0 / test_mem_sync 80/0 / devPPL pytest 281/8/1 零新增** | §3 |
| 静态核对 S1-S12 复验 | ✅ **12/12 PASS**（独立读码/diff） | §4 |
| 探针复验 + 漏报探针 | ✅ **27/27 PASS**（P3-P8 复验 17/17 + D2 漏报探针 A-G 10/10） | §5 |
| AC A1-A12/R5 交叉核对 | ✅ **13/13 有证据锚点**（MVP A1-A9 9/9） | §6 |
| 漏报检查（QA-EXEC 是否漏判） | ✅ **无漏报**（A-G 补充探针全部通过） | §5/§7 |
| F1-MINOR（策展 LLM exit 0 垃圾输出） | ✅ 复验确认（P6c：concepts 0→4），分级公式核对 MINOR 成立 | §7 |
| OBS-A（standalone status 队列路径） | ✅ 复验确认（cli.py L1218-1228 读默认路径），非验收缺陷 | §7 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §8 |

**评审结论：QA-EXEC 测试报告分级判定准确、证据链完整、无漏报、无错判。MEM-009 结果评审通过（review_pass），可放行 va-qa → qa-post（main 态回归本卡已覆盖，qa-post 只需补 conv_sync.sh cron 注册后的真实 tick 观测）。**

---

## 1. 评审对象与方法

### 1.1 评审对象

- QA-EXEC 报告：`docs/qa/mem009-conversation-extraction-test-report.md`（v1.0，203 行，t_f91a64c5 @ 996054a）
- 报告核心声明：mem-core pytest 246 PASS、test_conv_sync 55/0、test_mem_sync 80/0、devPPL pytest 281/8/1 零新增、静态 S1-S12 12/12、探针 P1-P8 全过、A1-A12/R5 逐项成立、0 BLOCKER/0 MAJOR/1 MINOR（F1）/1 观察（OBS-A）

### 1.2 评审方法（独立复验，不转述）

| # | 方法 | 说明 |
|---|------|------|
| M1 | 基线全量独立复跑 | 本卡在**合并后双仓 main**（devPPL da145d7 + mem-core b200a6d）重新执行四集：mem-core pytest / test_conv_sync.sh / test_mem_sync.sh / devPPL pytest |
| M2 | 静态独立核对 | 独立读码/grep/diff 复验 S1-S12（12 项） |
| M3 | 探针独立复验 + 漏报探针 | P3-P8 重新执行（17 断言）+ 漏报探针 A-G 新增（exit2 区分/fail-open 边界/mute 名单/语法/gitignore/防回写/dry-run） |
| M4 | AC 交叉核对 | A1-A12/R5 逐项对照验收要点（test-plan §1.1 + EXEC 报告 §5） |
| M5 | 分级复核 | 对照标准 §1.2 判定公式，逐项复核 QA-EXEC 的 F1-MINOR + OBS-A 判定，并评估是否漏判 |

### 1.3 被测对象确认（P-1..P-4 复验）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | devPPL main HEAD | `git log main -1` = da145d7（merge t_dbbec269 DPL-071）；8fec922（MEM-009 被测 commit）为祖先 | ✅ |
| P-2 | mem-core main HEAD | `git log main -1` = b200a6d（mem(MEM-009): done）；4f67a75 + 61457ae 均为祖先 | ✅ |
| P-3 | MEM-009 文件零改动 | `git log 8fec922..HEAD -- scripts/conv_sync.sh scripts/conv_curate.py scripts/mem_sync.py scripts/test_conv_sync.sh` = 空；`git diff 4f67a75..HEAD --stat` 仅 wiki 文档（DPL-069/MEM-009/index/log） | ✅ |
| P-4 | 失败文件零改动 | `git diff 8fec922^ 8fec922` 与 `8fec922..HEAD` 对三个失败文件（test_memory_middleware_qa/test_slice2_d1_qa/test_P2-02_full）均空 → 8 failed + 1 error 全为存量 | ✅ |

---

## 2. 分级判定复核（标准 §1.2 公式逐项对照）

### 2.1 QA-EXEC 结论 vs 本卡复核

| QA-EXEC 判定 | 本卡复核 | 复核依据 |
|------|:---:|------|
| 0 BLOCKER | ✅ 一致 | 无用户可感知+功能阻断+无 workaround 组合（§2.2）；无安全漏洞；无数据一致性；无性能退化 ≥10x；无 OOM/崩溃 |
| 0 MAJOR | ✅ 一致 | 无用户可感知+功能阻断但有 workaround/体验严重退化；无 XSS/CSRF/SSRF；无 A 级数据一致性；无性能退化 ≥3x |
| 1 MINOR（F1：策展 LLM exit 0 垃圾输出 → 垃圾记忆页落库） | ✅ **一致** | 用户可感知（垃圾页可见、记忆污染）∧ 非功能阻断（机械层骨架/correction 不受影响，P6b 6=6）∧ 有 workaround（OC 部署正确 C 命令 + 人工清理）∧ 非安全漏洞 → 标准 §1.2 判定 MINOR（详见 §7.1） |
| 1 观察项（OBS-A：standalone memctl status 无 MEM_CONV_QUEUE env 读默认路径） | ✅ **一致** | cli.py L1218-1228 复读确认：无 env → `Path(_wiki).parent / ".pipeline" / "conv_queue.json"`；生产链路 conv_sync.sh L24 已导出 MEM_CONV_QUEUE 统一 → 观察项非缺陷 |

### 2.2 判定公式逐项（标准 §1.2）

| 条件 | 是否触发 | 证据 |
|------|:---:|------|
| 安全漏洞（认证绕过/数据泄露/远程注入） | 否 | conversation.py L347-350 全 mode=ro URI（S4）；S5 零写语句；D2 探针 F（tick 不写 kanban.db md5 一致）；P4（state.db md5 一致）；无网络/认证面 |
| 数据一致性（S/A 级数据） | 否 | 无资金/用户基础信息数据面；读写 wiki/events 属 C 级内部配置数据 |
| 性能退化（P95 ≥10x / ≥3x） | 否 | 批处理脚本 + 每 tick 上限事件；无用户请求路径 |
| OOM/崩溃 | 否 | Python 脚本 + bash 包装；fail-open 异常 exit 0（D2 探针 B1/B2 实测缺 profile dir/损坏 state.db 均 exit 0） |
| 概率性 bug（资金/核心功能） | 否 | 幂等重放（P8）+ message_id 去重键（conversation.py L485 D5）；单写入者 |

**结论：QA-EXEC 的「0 BLOCKER/0 MAJOR/1 MINOR + 1 观察」分级判定与标准公式完全一致，无错判、无漏判。**

---

## 3. 基线全量独立复跑（在合并后双仓 main 上执行）

> QA-EXEC 已在分支上复跑（devPPL main @ da145d7 / mem-core @ b200a6d 均为其被测 commit 的父辈）；本卡在**当前 main HEAD**上再次全量复跑四集——等价于 qa-post R2 的 main 态回归兜底提前完成。

### 3.1 mem-core pytest 全量（246 断言）

```bash
cd /workspace/mem-core && .venv/bin/python -m pytest -o addopts='' -q
```

- **246 passed in 192.08s，EXIT=0**（与 QA-EXEC 246、VA 246 三方一致）
- 含 MEM-009 新增 test_sources_conversation.py（14）+ test_cmd_conversation.py（6）

### 3.2 test_conv_sync.sh（55 断言）

```bash
cd /workspace/devPPL && bash scripts/test_conv_sync.sh
```

```
PASS=55 FAIL=0
ALL TESTS PASSED        （EXIT=0）
```

- 含 A1-A8/A10/A11/A12/R5 验收锚点（§6 交叉核对证据）

### 3.3 test_mem_sync.sh（80 断言，MEM-007 回归）

```bash
cd /workspace/devPPL && bash scripts/test_mem_sync.sh
```

```
PASS=80 FAIL=0
ALL TESTS PASSED        （EXIT=0）
```

- MEM-007 链路（kanban/gai 源）零回归

### 3.4 devPPL pytest（281 基线 + 存量失败集零新增）

```bash
cd /workspace/devPPL && python3 -m pytest tests/ -q
```

- **281 passed / 8 failed / 1 error in 134.63s**（EXIT=1）
- 失败集：test_memory_middleware_qa ×3 + test_slice2_d1_qa ×5 + ERROR test_P2-02_full ×1 —— 与 QA-EXEC（281/8/1, 134.78s）**逐项一致**
- 零新增证据：P-4（三个失败文件在 8fec922 merge 前后均零改动）

### 3.5 双仓合并状态确认

| 检查 | 结果 |
|------|:---:|
| `git merge-base --is-ancestor 8fec922 da145d7` | YES（devPPL main 含 MEM-009 被测 commit） |
| `git merge-base --is-ancestor 4f67a75 b200a6d` | YES（mem-core main 含被测 adapter） |
| `git log 8fec922..da145d7 -- scripts/conv_sync.sh scripts/conv_curate.py scripts/mem_sync.py scripts/test_conv_sync.sh` | 空（MEM-009 文件零改动） |
| `git diff 4f67a75..b200a6d --stat` | 仅 wiki 文档（DPL-069/MEM-009/index/log） |

---

## 4. 静态核对 S1-S12 复验（独立读码/grep/diff，12/12 PASS）

| # | 核对项 | 实测（main 上） | 结果 |
|---|--------|------|:---:|
| S1 | SOURCES 注册含 conversation（A12） | `memcore/sources/__init__.py` L10 `from .conversation import ConversationAdapter` + L15 `"conversation": ConversationAdapter()` | ✅ |
| S2 | 引擎零对话语义（A12） | `scripts/mem_sync.py` grep conversation/correction 仅命中 L65 注释 + L68 `"conversation", "correction"`（_COUNTER_KEYS） | ✅ |
| S3 | SQL 只存在于 adapter | mem_sync.py 零命中；conv_curate.py 3 命中均为 pages 表 `raw/sessions/%`（wiki 路径非 L0 表）；cli.py 命中均为路径/注释/pages 表查询，无 L0 state.db 表 SQL | ✅ |
| S4 | adapter 只读三铁律 mode=ro | `memcore/sources/conversation.py` L347-350 `_connect` 用 `file:{path}?mode=ro` URI | ✅ |
| S5 | adapter 无写语句 | conversation.py grep INSERT/UPDATE/DELETE 唯一命中 L3 注释（"pytest 断言 INSERT 抛错"） | ✅ |
| S6 | _COUNTER_KEYS 三键 | `scripts/mem_sync.py` L67-69 tuple 含 conversation/correction（+curated 由 conv_curate 落库） | ✅ |
| S7 | conv_sync.sh 两阶段 fail-open | L16 `set -uo pipefail`（无 -e）；L29-36 两阶段各取 rc 打印、恒 `exit 0` | ✅ |
| S8 | conv_curate.py 打分/原子写/Top-N/retries | L10 os.replace；L11 打分表（纠正+3/feishu+2/消息>40+1/决策词+2）；L54 DEFAULT_TOP_N=3；L64 retries ≥3 abandoned；L126-133 temp+os.replace 原子写 | ✅ |
| S9 | memctl 命令面 | `memcore/cli.py` L407 `_add_conversation` + L913 `_correction_exists` + L1052 `_query_corrections` + L1218 `_conv_queue_backlog`；status 三计数 L1246 | ✅ |
| S10 | fingerprint 规则 | `conversation.py` L114-122：`correction:<category>:<sha256(norm_lede)[:12]>`（D4 双因子）；L161-187 detect_corrections 弱词门控 | ✅ |
| S11 | A11 双链回 conversation + lint | `conv_curate.py` L306 HTML 注释 curate-source 携带 page_id + L340-345 supersedes 接口（MVP 保留） | ✅ |
| S12 | cron 注册行 + must-sync 外 | conv_sync.sh L4-5 注册行注释（OC 执行）；deploy-drift-audit-2026-08-15.md §1.2 must-sync 定稿 4 脚本（oc_wake_check/sentinel_alert/devppl_autopilot/close）conv_sync 零命中 → repo 路径直调天然最新；.gitignore L16-20 覆盖 mem_sync_state/conv_queue 运行时产物 | ✅ |

**合计 12/12 PASS（与 QA-EXEC S1-S12 一致，且全部在 main 上核实）。**

---

## 5. 探针复验 + 漏报探针（27/27 PASS）

### 5.1 QA-EXEC 探针 P3-P8 复验（本卡独立执行 `scripts/qa_mem009_probes.sh`，17/17 PASS）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P7a | 锚定 tick exit 0 | 0 | ✅ |
| P7b | 锚定 tick 零 memctl（A8） | 0 | ✅ |
| P3a | 发现 tick exit 0 | 0 | ✅ |
| P3b | 骨架页 = 6（alpha 3 + beta 3） | 6 | ✅ |
| P3c | correction 事件 = 3（同指纹 2 + 异指纹 1） | 3 | ✅ |
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
| P6e | exit-1 ≥3 次 → abandoned 非空（重试语义） | pending=2→2→0 abandoned=0→0→2 | ✅ |
| P5 | 队列损坏（非法 JSON）→ conv_curate exit 0 | 0 | ✅ |

### 5.2 漏报探针（QA-D2 新增 `scripts/qa_mem009_d2_probes.sh`，10/10 PASS）

| # | 探针 | 目标 | 实测 | 结果 |
|---|------|------|------|:---:|
| A | 未知 source exit 2 | fail-open 与用法错误区分（防吞错） | `mem_sync.py --source bogus` → EXIT=2 | ✅ |
| B1 | 缺 profile dir fail-open | adapter 对缺失数据源不崩 | `MEM_CONV_PROFILE_ROOT=/nonexistent` → exit 0 | ✅ |
| B2 | 损坏 state.db fail-open | adapter 对损坏 SQLite 不崩 | 写入非 sqlite 文本 → exit 0 | ✅ |
| C | MEM_CONV_CORR_MUTE 静默名单生效 | fingerprint 级静默（§3.4）防误报 | 无 mute 1 条 correction → 设 mute 后 0 条 | ✅ |
| D1 | bash -n 3/3 | 合并后脚本语法完好 | conv_sync/test_conv_sync/test_mem_sync 全 OK | ✅ |
| D2 | py_compile 2/2 | 合并后 Python 语法完好 | conv_curate/mem_sync 全 OK | ✅ |
| E | 状态文件不入库 | 游标/队列不污染 git | `git ls-files | grep mem_sync_state/conv_queue` 空；.gitignore L16-20 覆盖 | ✅ |
| F | 防回写环扩展（kanban.db） | conversation tick 不触碰其它 L0 库 | 已知内容 kanban.db tick 前后 md5 一致 | ✅ |
| G1 | 真实 profile --dry-run exit 0 | 真实 8 profile 只读探测不崩 | `/root/.hermes/profiles` + --dry-run → EXIT=0 | ✅ |
| G2 | --dry-run 不落游标 | smoke 模式无副作用 | state.json 未生成 | ✅ |

**合计 27/27 PASS。漏报检查结论：QA-EXEC 未漏判任何缺陷；D2 新增探针 A-G 全部通过，未发现 QA-EXEC 报告之外的功能缺陷。**

---

## 6. A1-A12/R5 交叉核对（与 QA-EXEC 报告交叉印证）

| AC | 验收要点 | 本卡证据 | 结果 |
|----|---------|---------|:---:|
| A1 | feishu 会话 → ≤1 tick 骨架页 | test_conv_sync 55/0（含）+ P3b（6 页含 feishu×4）+ P1 真实 orchestrator 会话（EXEC 报告） | ✅ |
| A2 | cli 全 profile 覆盖（静置主路径） | P3b（cli 页 alpha/beta 各 1）+ test_conv_discovery_idle_fallback（55/0 含） | ✅ |
| A3 | 噪声/未结束/低消息/archived 不生成 | P3d（cron 0 页）+ test_conv_sync 白名单段（55/0 含） | ✅ |
| A4 | 纠正复发计数可查询（2 同指纹+1 异指纹 → 3） | P3c（events=3）+ P3e（SQL GROUP BY 2+1） | ✅ |
| A5 | 幂等重放 3 次页数/事件数不变 | P8a/P8b（重放 2 次 6/3 不变）+ test_conv_sync 幂等段 | ✅ |
| A6 | state.db md5 全程一致 | P4（temp 夹具）+ D2 探针 F（kanban.db md5）+ P1 对照实验（EXEC 报告） | ✅ |
| A7 | fail-open（库损坏/LLM 失败） | P5（队列损坏 exit 0）+ P6a（LLM exit 0）+ D2 B1/B2（缺库/损坏库 exit 0）+ test_conv_sync A7 段 | ✅ |
| A8 | work-gated 零 memctl | P7b/P7c（锚定 + 无新会话均零调用） | ✅ |
| A9 | pytest 全绿 + 集成 ≥10 断言 | 246/0（192.08s）+ 55 断言（≥12） | ✅ |
| A10 | 成本护栏全 env 可调 | test_conv_sync A10 段（55/0 含）+ P6d/P6e（TOP_N/retries/abandoned 实测） | ✅ |
| A11 | 记忆页双链回 conversation + lint | S11（curate-source 携带 page_id）+ test_conv_sync A11 段（假 LLM 成功态，55/0 含） | ✅ |
| A12 | adapter 继承 + 一行注册 + 引擎零语义 | S1/S2/S3 + test_sources_conversation（246/0 含） | ✅ |
| R5 | memctl status 三计数 | cli.py L1246 + test_conv_sync R5 段（55/0 含：conversation 页 5/correction 4/队列 0）+ OBS-A（P2 复验） | ✅ |
| 部署 | conv_sync.sh cron 注册 → OC | S12（注册行交付 + must-sync 外） | ✅（部署动作归 OC） |

**MVP 门禁（A1-A9）：9/9 全过。13/13 有证据锚点。**

---

## 7. 发现汇总与分级（标准 §6 输出格式要求）

### 7.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 判定公式匹配 | 定级 |
|------|:---:|:---:|:---:|:---:|------|:---:|
| **F1-MINOR**（复验确认）：策展 LLM C 命令 exit 0 垃圾输出 → learn 仍落垃圾记忆页（P6c：concepts 0→4，页体="this is not markdown, just garbage output"） | ✅（垃圾页可见，记忆污染） | ❌（机械层骨架/correction 不受影响，P6b 6=6） | ✅（OC 部署正确 LLM 命令；人工清理） | 否 | 可感知 ∧ 非阻断 ∧ 有 workaround → **MINOR** | **MINOR**（与 QA-EXEC 一致） |
| **OBS-A**（复验确认）：standalone memctl status 无 MEM_CONV_QUEUE env 时策展队列积压读默认路径 | ✅（观察期读数可能错） | ❌（生产链路 conv_sync.sh L24 导出 env 统一） | ✅（跑 status 时同 env） | 否 | 非验收缺陷（dev 已登记） | **观察项**（与 QA-EXEC 一致） |

> F1 分级复核依据：标准 §5 MINOR 行「用户能忍，不阻塞发版」——该行为继承自 MEM-007 learn 管线（`_run_llm` 信任编译器 stdout，rc 协议 0=成功），非 MEM-009 新增写路径；MVP A11（双链+lint）仍满足 → MINOR 成立且不阻塞发版。

### 7.2 漏报检查结论

- D2 新增漏报探针 A-G（10 项）全部通过：未知 source 正确 exit 2（无吞错）、缺库/损坏库 fail-open、mute 名单生效、语法完好、状态文件不入库、防回写环（kanban.db md5 不变）、真实 profile dry-run 只读。
- **未发现 QA-EXEC 漏判的功能缺陷**。QA-EXEC 的 F1-MINOR 与 OBS-A 均复验确认，无错判、无遗漏。

### 7.3 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**（QA-EXEC 与 QA-D2 均无新增缺陷）。
- F1-MINOR 已在 QA-D1 登记并经 VA/dev 评估（dev claim 接受），本卡仅复验确认，无需重新启动论证流程。
- 有成本申诉未触发（无驳回）；产品红线（BLOCKER 暂缓须 Frank 签字）未触发。

### 7.4 分级示例对照（标准 §5 表）

- 未发现「合格 feishu/cli 会话不产骨架页」类 BLOCKER（P1/P3b 均正常产页）。
- 未发现「correction 误报率异常」类 MAJOR（P3f 单弱词不检出 + D2 C mute 名单生效）。
- 未发现「日志/输出格式与文档略有出入」类 MINOR（S7/S8 读码一致 + 基线全绿）。
- 未发现「注释/文档与实现细节不一致」类 SUGGESTION。

---

## 8. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。MEM-009 结果评审通过（review_pass），可进入 va-qa → qa-post。**

---

## 9. 评审建议

1. **放行**：QA-EXEC 报告分级判定准确、证据链完整、无漏报无错判。MEM-009 可继续 va-qa → qa-post 流程。
2. **main 态回归已提前覆盖**：本卡在合并后双仓 main（devPPL da145d7 / mem-core b200a6d）独立复跑基线四集全绿（246/55/80/281 零新增）+ 静态 S1-S12 + 探针 27/27。qa-post 无需重复 main 态回归，只需确认 merge 后无后续提交引入回归。
3. **F1-MINOR 处置（同 QA-EXEC 建议）**：建议后续在 conv_curate 侧加输出 sanity check（如必须含 `---` frontmatter 或指定结构），或 OC 部署时验证 C 命令。MINOR 不阻塞发版。
4. **OBS-A 处置（同 QA-EXEC 建议）**：建议后续独立小改对齐（默认路径指向 devPPL .pipeline/）。观察项非验收缺陷，不设 SLA。
5. **部署依赖（归 OC）**：conv_sync.sh cron 注册（`*/5 * * * * bash /workspace/devPPL/scripts/conv_sync.sh`，见 L4-5 注释）+ 真实 tick 心跳证据归 qa-post/OC（同 MEM-007 D12 先例）。

---

## 附：执行产物

- 本报告：docs/qa/mem009-conversation-extraction-d2-review.md
- D2 漏报探针脚本：scripts/qa_mem009_d2_probes.sh（10 断言）
- 复验探针脚本（来自 QA-EXEC）：scripts/qa_mem009_probes.sh（17 断言）
- WIP 笔记：.pipeline/wip/t_ac88ed89.md
