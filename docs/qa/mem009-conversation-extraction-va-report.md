# VA-QA 验证报告 — MEM-009 对话提取（对话/纠错自动提取记忆与经验）

> 版本：v1.0 | 日期：2026-08-20 | 执行人：Verification Agent（verifier profile，t_48a3dd47）
> 上游：QA-D2 结果严重度评审（t_ac88ed89 @ a8e25eb，review_pass）→ 放行 va-qa → qa-post
> 被测提交：**devPPL main @ 4e49c98**（复核时 main 已前进至 e13f6e6，DPL-077 正交）+ **mem-core main @ ce3c369**（复核时 a66ae5b，仅 wiki 文档）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 验证性质：VA 独立执行（非转述 QA-EXEC/QA-D2），基线全量 + 静态 + 探针 + AC 交叉核对 + 分级复核

---

## 0. 验证结论（TL;DR）

| 验证项 | 结果 | 证据 |
|---|---|---|
| 双仓前置确认（被测 commit 为祖先 + MEM-009 文件零改动） | ✅ 4/4 | §1.1（devPPL 8fec922→main / mem-core 4f67a75→main 均零改动） |
| mem-core pytest 全量独立复跑 | ✅ **246 passed in 198.93s，EXIT=0** | §2.1（本卡独立执行） |
| test_conv_sync.sh 独立复跑 | ✅ **PASS=55 FAIL=0** EXIT=0 | §2.2 |
| test_mem_sync.sh 独立复跑（MEM-007 回归） | ✅ **PASS=80 FAIL=0** EXIT=0 | §2.3 |
| devPPL pytest 独立复跑 | ✅ **281 passed / 8 failed / 1 error（HOME=/root）零新增** | §2.4 |
| 静态核对 S1-S12 | ✅ **12/12 PASS**（独立读码/grep） | §3 |
| 探针复验 P3-P8 | ✅ **17/17 PASS**（F1-MINOR 复现） | §4.1 |
| D2 漏报探针 A-G | ✅ **10/10 PASS** | §4.2 |
| AC A1-A12/R5 交叉核对 | ✅ **13/13 有证据锚点**（MVP A1-A9 9/9） | §5 |
| 分级判定复核（F1-MINOR / OBS-A） | ✅ 与 QA-D2 一致，无错判无漏判 | §6 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §7 |

**结论：QA-D2 报告（t_ac88ed89）全部核心声明经 VA 独立复验一致。0 FALSIFIED。MEM-009 可放行 qa-post（cron 注册后真实 tick 观测归 qa-post/OC）。**

---

## 1. 验证对象与方法

### 1.1 被测对象确认（P-1..P-4 复验，在复核时最新 main 上）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | devPPL main HEAD | 复核起点 `git log main -1` = 4e49c98（merge est t_f3108dfd）；8fec922（MEM-009 被测 commit）为祖先 = YES | ✅ |
| P-2 | mem-core main HEAD | 复核起点 `git log main -1` = ce3c369；4f67a75 + 61457ae 均为祖先 = YES | ✅ |
| P-3 | MEM-009 文件零改动 | `git diff 8fec922..main -- scripts/conv_sync.sh scripts/conv_curate.py scripts/mem_sync.py scripts/test_conv_sync.sh` = 空；`git diff 4f67a75..main -- memcore/sources/conversation.py memcore/cli.py memcore/sources/__init__.py` = 空 | ✅ |
| P-4 | 失败文件零改动 | `git diff 8fec922^ 8fec922` 与 `8fec922..main` 对三失败文件（test_memory_middleware_qa / test_slice2_d1_qa / test_P2-02_full）均为空 → 8 failed + 1 error 全为存量 | ✅ |

> 复核期间 main 前进：devPPL 4e49c98 → e13f6e6（DPL-077 容器豁免，pipeline/discover.py + oc_wake_check.sh，与 MEM-009 正交）；mem-core ce3c369 → a66ae5b（DPL-077 wiki 文档）。两次前进均未触碰 MEM-009 文件，本卡结论对最新 main 成立。

### 1.2 验证方法（独立执行，不转述）

- M1：基线四套独立复跑（mem-core pytest / test_conv_sync.sh / test_mem_sync.sh / devPPL pytest，本卡 worktree @ 4e49c98 + mem-core main）
- M2：静态独立核对 S1-S12（独立读码/grep/diff，12 项）
- M3：探针独立复验（qa_mem009_probes.sh 17 断言 + qa_mem009_d2_probes.sh 10 断言，脚本取自 t_ac88ed89 交付件 a8e25eb）
- M4：AC A1-A12/R5 交叉核对（与 QA-EXEC 报告、QA-D2 报告交叉印证）
- M5：分级判定复核（标准 §1.2 公式 + §10 门禁逐项对照）

---

## 2. 基线全量独立复跑

### 2.1 mem-core pytest 全量（246 断言）

```bash
cd /workspace/mem-core && .venv/bin/python -m pytest -o addopts='' -q
```

- **246 passed in 198.93s (0:03:18)，EXIT=0**（与 QA-EXEC 246、QA-D2 246、VA-CLAIM 246 四方一致）
- 含 MEM-009 新增 test_sources_conversation.py（14）+ test_cmd_conversation.py（6）

### 2.2 test_conv_sync.sh（55 断言）

```bash
cd /workspace/devPPL/.worktrees/t_48a3dd47 && bash scripts/test_conv_sync.sh
```

- **PASS=55 FAIL=0 / ALL TESTS PASSED（EXIT=0）**
- 含 A1-A8/A10/A11/A12/R5 验收锚点（A0a-f 首跑语义、A1a-c 骨架页、A2a cli 静置、A3a-e 噪声免疫、A4a-b 聚合、A5a-b 幂等、A6a-b md5、A7a-b fail-open、A8a-c work-gated、R5a-c 三计数、A10a-k 成本护栏、A11 双链）

### 2.3 test_mem_sync.sh（80 断言，MEM-007 回归）

- **PASS=80 FAIL=0 / ALL TESTS PASSED（EXIT=0）**
- MEM-007 链路（kanban/gai 源）零回归

### 2.4 devPPL pytest（281 基线 + 存量失败集零新增）

```bash
cd /workspace/devPPL/.worktrees/t_48a3dd47 && HOME=/root python3 -m pytest tests/ -q
```

- **281 passed / 8 failed / 1 error in 95.25s（EXIT=1）**
- 失败集：test_memory_middleware_qa ×3（tc19/tc20/tc23）+ test_slice2_d1_qa ×5（TC14/TC09×3/BE01）+ ERROR test_P2-02_full ×1 —— 与 QA-D2（281/8/1）**逐项一致**
- 零新增证据：P-4（三个失败文件在 8fec922 merge 前后均零改动）

> **环境注意（复验方法论）**：本卡首跑未设 HOME 时得到 275/14/1，多出的 6 个失败为 test_p0_18_qa L1-L6（FileNotFoundError: `~/.hermes/profiles/orchestrator/scripts/kanban_watchdog.py`）——VA 会话 HOME 指向 `/root/.hermes/profiles/verifier/home`，`~` 展开错误。`HOME=/root` 复刻后 8 failed 精确恢复。与 QA-EXEC 报告 §2 注释一致（「VA 记录的 14+1 含 test_p0_18_qa×6 为 OC live 脚本环境漂移项」）。**非代码回归，属环境伪影。**

---

## 3. 静态核对 S1-S12（12/12 PASS，独立读码/grep/diff）

| # | 核对项 | 实测（main 上） | 结果 |
|---|--------|------|:---:|
| S1 | SOURCES 注册含 conversation（A12） | `memcore/sources/__init__.py` L10 `from .conversation import ConversationAdapter` + L15 `"conversation": ConversationAdapter()` | ✅ |
| S2 | 引擎零对话语义（A12） | `scripts/mem_sync.py` grep conversation/correction 仅命中 L65 注释 + L68 `"conversation", "correction"`（_COUNTER_KEYS L67-69） | ✅ |
| S3 | SQL 只存在于 adapter | mem_sync.py 3 命中（import sqlite3 + L207 mode=ro connect + L210 tasks 表 SELECT，均 kanban 路径）；conv_curate.py 2 命中均为 pages 表（L198/L268 `raw/sessions/%` wiki 路径非 L0 表） | ✅ |
| S4 | adapter 只读三铁律 mode=ro | `memcore/sources/conversation.py` L347-350 `_connect` 用 `file:{path}?mode=ro` URI | ✅ |
| S5 | adapter 无写语句 | conversation.py grep INSERT/UPDATE/DELETE 唯一命中 L3 注释（"pytest 断言 INSERT 抛错"） | ✅ |
| S6 | _COUNTER_KEYS 三键 | mem_sync.py L67-69 tuple 含 conversation/correction（+curated） | ✅ |
| S7 | conv_sync.sh 两阶段 fail-open | L16 `set -uo pipefail`（无 -e）；L28/L31 两阶段各取 rc 打印；L36 恒 `exit 0` | ✅ |
| S8 | conv_curate.py 打分/原子写/Top-N/retries | L10 os.replace；L11 打分表（纠正+3/feishu+2/消息>40+1/决策词+2）；L54 DEFAULT_TOP_N=3；L64 retries ≥3 abandoned | ✅ |
| S9 | memctl 命令面 | `memcore/cli.py` L407 `_add_conversation` + L913 `_correction_exists` + L1052 `_query_corrections` + L1218 `_conv_queue_backlog`；status 三计数 L1246/1289 | ✅ |
| S10 | fingerprint 规则 | conversation.py L114-122：`correction:<category>:<sha256(norm_lede)[:12]>`（D4 双因子） | ✅ |
| S11 | A11 双链回 conversation + lint | conv_curate.py L306 HTML 注释 curate-source 携带 page_id + L340-345 supersedes 接口（MVP 保留） | ✅ |
| S12 | cron 注册行 + must-sync 外 | conv_sync.sh L4-5 注册行注释（OC 执行）；deploy-drift-audit-2026-08-15.md §1.2 must-sync 定稿 4 脚本（oc_wake_check/sentinel_alert/devppl_autopilot/close）conv_sync 零命中；.gitignore L16-20 覆盖 mem_sync_state/conv_queue 运行时产物；git ls-files 零跟踪 | ✅ |

**合计 12/12 PASS（与 QA-D2 S1-S12 一致，全部在 main 上核实）。**

---

## 4. 探针复验 + 漏报探针（27/27 PASS）

### 4.1 QA 探针 P3-P8 复验（scripts/qa_mem009_probes.sh，17/17 PASS）

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

### 4.2 D2 漏报探针 A-G（scripts/qa_mem009_d2_probes.sh，10/10 PASS）

| # | 探针 | 目标 | 实测 | 结果 |
|---|------|------|------|:---:|
| A | 未知 source exit 2 | fail-open 与用法错误区分（防吞错） | `mem_sync.py --source bogus` → EXIT=2 | ✅ |
| B1 | 缺 profile dir fail-open | adapter 对缺失数据源不崩 | `MEM_CONV_PROFILE_ROOT=/nonexistent` → exit 0 | ✅ |
| B2 | 损坏 state.db fail-open | adapter 对损坏 SQLite 不崩 | 非 sqlite 文本 → exit 0 | ✅ |
| C | MEM_CONV_CORR_MUTE 静默名单生效 | fingerprint 级静默防误报 | unmuted=1 muted=0 | ✅ |
| D1 | bash -n 3/3 | 合并后脚本语法完好 | conv_sync/test_conv_sync/test_mem_sync 全 OK | ✅ |
| D2 | py_compile 2/2 | 合并后 Python 语法完好 | conv_curate/mem_sync 全 OK | ✅ |
| E | 状态文件不入库 | 游标/队列不污染 git | `git ls-files | grep mem_sync_state/conv_queue` 空 | ✅ |
| F | 防回写环扩展（kanban.db） | conversation tick 不触碰其它 L0 库 | 已知内容 kanban.db tick 前后 md5 一致 | ✅ |
| G1 | 真实 profile --dry-run exit 0 | 真实 8 profile 只读探测不崩 | `/root/.hermes/profiles` + --dry-run → EXIT=0 | ✅ |
| G2 | --dry-run 不落游标 | smoke 模式无副作用 | state.json 未生成 | ✅ |

**合计 27/27 PASS。漏报检查结论：QA-EXEC 与 QA-D2 均未漏判；未发现报告之外的功能缺陷。**

---

## 5. A1-A12/R5 交叉核对（与 QA-EXEC / QA-D2 交叉印证）

| AC | 验收要点 | 本卡证据 | 结果 |
|----|---------|---------|:---:|
| A1 | feishu 会话 → ≤1 tick 骨架页 | test_conv_sync 55/0（A1a-c）+ P3b（6 页含 feishu×4） | ✅ |
| A2 | cli 全 profile 覆盖（静置主路径） | test_conv_sync A2a（cli 静置达标产页）+ P3b（cli 页 alpha/beta 各 1） | ✅ |
| A3 | 噪声/未结束/低消息/archived 不生成 | P3d（cron 0 页）+ test_conv_sync A3a-c | ✅ |
| A4 | 纠正复发计数可查询（2 同指纹+1 异指纹 → 3） | P3c（events=3）+ P3e（SQL GROUP BY 2+1）+ test_conv_sync A4a-b（total=3 聚合 2+1） | ✅ |
| A5 | 幂等重放 3 次页数/事件数不变 | P8a/P8b（重放 2 次 6/3 不变）+ test_conv_sync A5a-b（重放 3 次 4/4） | ✅ |
| A6 | state.db md5 全程一致 | P4（temp 夹具）+ test_conv_sync A6a-b | ✅ |
| A7 | fail-open（库损坏/LLM 失败） | P5（队列损坏 exit 0）+ P6a（LLM exit 0）+ D2 B1/B2 + test_conv_sync A7a-b | ✅ |
| A8 | work-gated 零 memctl | P7b/P7c + test_conv_sync A8b（全链路零 memctl） | ✅ |
| A9 | pytest 全绿 + 集成 ≥10 断言 | 246/0（198.93s）+ 55 断言（≥12） | ✅ |
| A10 | 成本护栏全 env 可调 | test_conv_sync A10a-k（Top-N=1/retries/abandoned）+ P6d/P6e | ✅ |
| A11 | 记忆页双链回 conversation + lint | S11（curate-source 携带 page_id）+ test_conv_sync A11 段（假 LLM 成功态） | ✅ |
| A12 | adapter 继承 + 一行注册 + 引擎零语义 | S1/S2/S3 + test_sources_conversation（246/0 含） | ✅ |
| R5 | memctl status 三计数 | cli.py L1246/1289 + test_conv_sync R5a-c（conversation 页 5/correction 4/队列 0）+ OBS-A 复验 | ✅ |

**MVP 门禁（A1-A9）：9/9 全过。13/13 有证据锚点。**

---

## 6. 分级判定复核（标准 §1.2 公式逐项）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 判定公式匹配 | VA 复核 |
|------|:---:|:---:|:---:|:---:|------|:---:|
| **F1-MINOR**（复验确认）：策展 LLM C 命令 exit 0 垃圾输出 → learn 仍落垃圾记忆页（P6c：concepts 0→4，页体="this is not markdown, just garbage output"） | ✅（垃圾页可见，记忆污染） | ❌（机械层骨架/correction 不受影响，P6b 6=6） | ✅（OC 部署正确 LLM 命令；人工清理） | 否 | 可感知 ∧ 非阻断 ∧ 有 workaround → **MINOR** | ✅ **一致** |
| **OBS-A**（复验确认）：standalone memctl status 无 MEM_CONV_QUEUE env 时策展队列积压读默认路径 | ✅（观察期读数可能错） | ❌（生产链路 conv_sync.sh L24 导出 env 统一） | ✅（跑 status 时同 env） | 否 | 非验收缺陷（dev 已登记） | ✅ **一致**（cli.py L1218-1228 复读确认） |

- **安全漏洞**：无（conversation.py L347-350 mode=ro；S5 零写语句；D2 探针 F kanban.db md5 一致；无网络/认证面）
- **数据一致性（S/A 级）**：无（读写 wiki/events 属 C 级内部配置数据）
- **性能退化/OOM/崩溃**：无（批处理脚本 + fail-open 恒 exit 0）
- **概率性 bug（资金/核心功能）**：无（幂等重放 P8 + message_id 去重键 + 单写入者）
- **SLA 对照（标准 §8）**：0 BLOCKER/0 MAJOR → 无 SLA 触发；F1 已在 QA-D1 登记并经 VA/dev 评估，无需重新启动论证流程；无有成本申诉；产品红线未触发

**结论：QA-D2 的「0 BLOCKER/0 MAJOR/1 MINOR + 1 观察项」分级判定与标准公式完全一致，VA 独立复核无错判、无漏判。**

---

## 7. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。MEM-009 结果评审通过（review_pass），VA-QA 复核通过，可放行 qa-post。**

---

## 8. 验证结论与建议

1. **复核通过**：QA-D2 报告（t_ac88ed89）核心声明全部成立——基线四套（246/55/80/281 零新增）、静态 S1-S12 12/12、探针 27/27、AC 13/13、分级判定一致、发布门禁满足。0 FALSIFIED。
2. **环境伪影澄清**：test_p0_18_qa L1-L6 在 VA 会话（HOME=profile home）下必失败，属 OC live 脚本环境漂移项（QA-EXEC §2 已注明），`HOME=/root` 复刻后恢复 281/8/1 精确基线。后续 VA 复跑 devPPL pytest 须 `HOME=/root`。
3. **F1-MINOR 处置（同 QA-D2）**：建议后续 conv_curate 加输出 sanity check（如必须含 `---` frontmatter 或指定结构），或 OC 部署时验证 C 命令。MINOR 不阻塞发版。
4. **OBS-A 处置（同 QA-D2）**：建议后续独立小改对齐（默认路径指向 devPPL .pipeline/）。观察项非验收缺陷，不设 SLA。
5. **部署依赖（归 OC）**：conv_sync.sh cron 注册（`*/5 * * * * bash /workspace/devPPL/scripts/conv_sync.sh`）+ 真实 tick 心跳证据归 qa-post/OC（同 MEM-007 D12 先例）。

---

## 附：执行产物

- 本报告：docs/qa/mem009-conversation-extraction-va-report.md
- 复验日志：/tmp/va_memcore_pytest.log（246/0）/ /tmp/va_conv_sync.log（55/0）/ /tmp/va_mem_sync.log（80/0）/ /tmp/va_devppl_pytest2.log（281/8/1）
- 探针脚本（QA-D2 交付件，取自 a8e25eb，本卡复用于执行）：scripts/qa_mem009_probes.sh / scripts/qa_mem009_d2_probes.sh
- WIP 笔记：.pipeline/wip/t_48a3dd47.md
