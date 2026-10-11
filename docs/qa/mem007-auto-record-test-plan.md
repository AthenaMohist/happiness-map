# MEM-007 自动记录维护（kanban 事件 → memctl 自动写 wiki/GAI）— QA D1 测试方案（test_plan.md）

> 版本：v1.0 | 日期：2026-08-15 | 作者：game-qa（独立测试方案，非研发自测）
>
> 任务卡：t_a06c8a09 [DEV-QA-D1] mem-core 自动记录维护 — kanban 事件 → memctl 自动写 wiki/GAI（MEM-007）
> 被测提交（双仓）：
> - **mem-core main @ cfec21d**（SUB-1+SUB-2+SUB-3 已合入：kanban adapter + pytest 12+14 用例 + gai-links --set-status）
> - **devPPL wt/t_cfe5908e @ a63582d**（SUB-4：mem_sync 引擎 316 行 + mem_sync.sh + test_mem_sync.sh 47 断言；**未合入 main**）
> - **devPPL wt/t_136e5048 @ e5bfbb0**（SUB-5：close.sh S3b 修复 + A9 冒烟证据；**未合入 main**）
> 上游文档：
> - PRD v2.0：`/workspace/mem-core/wiki/projects/devppl/prd/mem007-auto-record-maintenance-prd-v2.md`（472 行）
> - 架构 v1.0：`/workspace/mem-core/wiki/projects/devppl/arch/arch-mem007-auto-record-maintenance.md`（736 行）
> - VA：t_1a5f43f8（done，21/21 claims PASS，0 FALSIFIED；5 张源卡 [VERIFIED]）
> - 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> - 基线测试：mem-core `pytest`（214 断言）+ devPPL `scripts/test_mem_sync.sh`（47 断言）+ `scripts/test_deploy_drift.sh`（29 断言）

---

## 0. 执行摘要（测试设计阶段结论）

| 项 | 结果 |
|---|---|
| 被测代码状态 | **mem-core main 已合入 SUB-1+SUB-2+SUB-3**（kanban adapter + 26 条 pytest 用例 + gai-links --set-status，214 passed 实测）；**devPPL main 未合入 SUB-4/SUB-5**（mem_sync 引擎/close.sh 修复在工作树分支 wt/t_cfe5908e + wt/t_136e5048，FF-ready 待 merge） |
| 研发验证状态 | 5 张 dev 子卡 + VA 独立复核 **21/21 VERIFIED，0 FALSIFIED**（A1-A11 全绿） |
| QA 独立核查（本卡已实测） | mem-core pytest **214 PASS** / test_mem_sync.sh **47 PASS** / test_deploy_drift.sh **29 PASS** / 语法 6 项全 OK（详见 §3） |
| D1 前置发现 | **无 BLOCKER / MAJOR / MINOR 缺陷**；0 SUGGESTION；2 项观察（OBS-1 被测代码未合入 devPPL main；OBS-2 A9 mem_meta.db events 侧依赖引擎部署，属部署后观测） |
| 工作量评估 | 预计 **14-20 轮（中位 17）≤ 20 轮阈值 → 不拆卡**（单张 QA 执行子卡），详见 §7 |

**结论**：dev 交付与 VA 复核一致，机制本体（kanban adapter / 引擎零感知 / set-status 幂等 / close.sh S3b）经 QA 独立核查全部成立。qa-exec 单卡执行：前置确认双仓被测 commit → mem-core pytest 214 → test_mem_sync.sh 47 → test_deploy_drift.sh 29 → 静态 S1-S12 → 探针 P1-P8 → A1-A11 逐项核对 → 报告。

---

## 1. 测试范围概览

```
被测模块                           PRD 需求覆盖       arch 章节        新增/扩展
──────────────────────────────────────────────────────────────────────────────────────
memcore/sources/base.py            R1/R6 (A11)       §1.3/§2.1        + initial_cursor/command_for（可选方法）
memcore/sources/kanban.py          R1 (A1-A6/A11)    §2               新 adapter（白名单 4 kind / mode=ro / map_id / mirror_status）
memcore/kanban_db.py               R1 (D9)           §2.3             新共享模块（cli 与 adapter 单一实现）
memcore/sources/__init__.py        R1/R6 (A11)       §1.3             SOURCES + "kanban"
memcore/gailinks.py                R2 (A2/A7)        §4               + set_gai_status（表头驱动 / 幂等 / 反查）
memcore/cli.py                     R2 (A2)           §4.2             gai-links --set-status（exit 0/1/2/3）
scripts/mem_sync.py (devPPL)       R1/R3/R4/R6       §3               新引擎（--source 分发 / 游标分桶 / fail-open / 噪声防护）
scripts/mem_sync.sh (devPPL)       R1               §3.7             新薄包装（notify_cron 模式，env 可覆盖）
scripts/close.sh (devPPL)          R2 (A7)           §5               S3b 修复（GAI_FILE 新路径 + --set-status）
tests/test_sources_kanban.py       R5 (A8)           §9.1             12 用例
tests/test_gai_set_status.py       R5 (A8)           §9.1             14 用例
scripts/test_mem_sync.sh (devPPL)  R5 (A8)           §9.2             47 断言（A1-A6 + R7 + R6 + 附加）
```

**零改动确认（回归范围）**：memcore/sources/gai.py 未改动（SUB-1 冒烟断言）；memcore/schema.py 常量新增但无破坏性变更；mem-core 其余测试文件（test_cli/test_gai/test_indexer/...）未改。

### 1.1 验收标准映射（PRD §9 A1-A11）

| # | 验收要点 | dev 测试锚点 | QA 复核 |
|---|---------|-------------|:---:|
| A1 | 建卡 → ≤1 tick wiki 页自动生成（page_type=task/source_task/task_code） | test_mem_sync.sh A1a-A1d | ✅ 基线含 + 静态 S2 |
| A2 | completed → wiki status=done + 结果节 + GAI 状态列 done | test_mem_sync.sh A2a-A2e + test_gai_set_status 幂等 | ✅ 基线含 + 探针 P5/P6 |
| A3 | blocked → wiki status=blocked + 执行记录含 reason | test_mem_sync.sh A3a-A3e | ✅ 基线含 |
| A4 | 幂等：同事件 3 次无新增 | test_mem_sync.sh A4a-A4g | ✅ 基线含 + 静态 S8 |
| A5 | 防回写环：kanban.db md5 一致 | test_mem_sync.sh A5a | ✅ 基线含 + 静态 S3 |
| A6 | fail-open：memctl 缺失 exit 0 / 单事件失败其余照常 | test_mem_sync.sh A6a-A6o | ✅ 基线含 + 静态 S10 |
| A7 | close.sh S3b 修复：新路径 + 状态列更新 | t_136e5048 diff + S3b 冒烟 | ✅ 静态 S11/S12 + 探针 P8 |
| A8 | 回归：pytest 全绿 + test_mem_sync.sh ≥10 断言 | 214 + 47 | ✅ 本卡实测双绿 |
| A9 | 真实链路：MEM-007 done → events done + GAI done | log.md L84 + GAI 行 done | ✅ 证据在位（OBS-2 部分待部署） |
| A10 | 蓝图定位：PRD §0-§2 完整 | 读 PRD | ✅ 静态 S1 |
| A11 | 组件前瞻：kanban.py 继承 SourceAdapter / --source 分发 / 游标分桶 | 代码评审 + pytest | ✅ 静态 S4-S7 |

### 1.2 架构裁决项跟踪（§0.3 D1-D12）

| 项 | 裁决 | 测试关注 | 状态 |
|----|------|---------|:---:|
| D3 | base.py 最小扩展（command_for/initial_cursor 可选方法） | 静态 S4 | ✅ 实测（base.py 44-51 行） |
| D4 | since 不透明游标字符串 | 静态 S2 + pytest incremental | ✅ |
| D5 | 首跑 initial_cursor→MAX(id) 不处理历史 | test_mem_sync A0a-A0e | ✅ |
| D7 | 游标分桶 + temp/os.replace 原子写 | 静态 S7 + 探针 P3 | ✅ |
| D9 | map_id 复用 kanban_db 单一实现 | 静态 S5 + pytest map_id | ✅ |
| D12 | cron 注册留 OC（repo 路径直调） | OBS-2（部署后观测） | ⏳ OC 部署 |

---

## 2. 测试环境与方法

与既有基线一致（隔离，不触碰真实 board/DB）：

| 项 | 配置 |
|---|---|
| 被测分支（双仓） | **mem-core main @ cfec21d** + **devPPL wt/t_cfe5908e @ a63582d**（引擎）+ **wt/t_136e5048 @ e5bfbb0**（close.sh）。qa-exec 若 devPPL 已合入则以 main 为准，**先核对 merge-base 避免测错对象** |
| 隔离 kanban.db | test_mem_sync.sh 自建 $TMPT/kanban.db（真实 schema 镜像 + 受控行） |
| 隔离 wiki/GAI | $TMPT/wikiroot/wiki + $TMPT/gai（MEM_WIKI_PATH/MEM_DB_PATH/MEM_GAI_FILE env 注入） |
| 隔离状态文件 | MEM_SYNC_STATE=$TMPT/state.json |
| 真实库只读核对 | `devppl_query.sh` / sqlite3 只读脚本（禁止裸 python3 -c 内联读 DB） |
| 执行命令 | `python3 -m pytest`（mem-core，214 断言）+ `bash scripts/test_mem_sync.sh`（47 断言）+ `bash scripts/test_deploy_drift.sh`（29 断言）+ 静态核对 + 探针脚本 |
| 被测代码获取 | mem-core main 直接跑；devPPL 引擎在 `cd /workspace/devPPL/.worktrees/t_cfe5908e` 跑（SUB-4 未合 main 期间） |

**执行前置（qa-exec 阶段）**：
1. 双仓被测 commit 确认：`git log mem-core -1`（应 cfec21d）+ `git log wt/t_cfe5908e -1`（应 a63582d）+ `git merge-base --is-ancestor` 判断 devPPL 是否已合入
2. `python3 -m py_compile scripts/mem_sync.py` + `bash -n scripts/mem_sync.sh scripts/test_mem_sync.sh scripts/close.sh`
3. 基线全量复跑全绿后，再执行新增探针

---

## 3. ⚠️ D1 前置发现（测试设计阶段）

### 3.1 缺陷发现汇总

**无 BLOCKER / MAJOR / MINOR 缺陷。** QA 独立核查项全部通过（§3.2）。

### 3.2 QA 独立核查结果（本卡已实测，非转述）

| # | 核查项 | 结果 |
|---|--------|:---:|
| G1 | mem-core pytest 全量（214 断言，23.66s） | **214 PASS**（EXIT=0） |
| G2 | test_mem_sync.sh（47 断言） | **PASS=47 FAIL=0**（EXIT=0） |
| G3 | test_deploy_drift.sh（29 断言） | **PASS=29 FAIL=0**（EXIT=0） |
| G4 | 语法：mem_sync.py py_compile / mem_sync.sh / test_mem_sync.sh / main close.sh / t_136e5048 close.sh | **6/6 OK** |
| G5 | 引擎零感知：mem_sync.py 不 import kanban 表结构（仅 memcore.sources.SOURCES） | ✅ grep 证实 |
| G6 | 游标分桶：state {version, sources:{<source>:{last_event_id}}} + temp/os.replace | ✅ 读码证实 |
| G7 | SOURCES 注册表：{"gai", "kanban"} | ✅ 读码证实 |
| G8 | close.sh S3b diff：GAI_FILE 新路径 + --set-status（非行尾 ✅ done） | ✅ git diff 证实（2a7f11a3 vs fd22da95） |
| G9 | A9 证据：wiki/actions/MEM-007.md status=done + GAI MEM-007 done + log.md done 记录 | ✅ 三处全在位 |
| G10 | mem_meta.db events：54 条全 index_update/index_rebuild，无生命周期记录 | ⚠️ OBS-2（引擎未部署，非缺陷） |

### 3.3 观察项（非缺陷，登记备查）

| # | 观察 | 说明 | 处置建议 |
|---|------|------|---------|
| OBS-1 | SUB-4/SUB-5 未合入 devPPL main | mem_sync.py/close.sh 修复仅在 wt/t_cfe5908e + wt/t_136e5048；main 的 close.sh 仍是旧 S3b（fd22da95） | qa-exec 前置确认 merge-base；若仍未合入则在工作树分支测（DPL-028 先例）；部署验证（repo vs live）留 OC（DPL-048） |
| OBS-2 | A9 的 mem_meta.db events 侧依赖引擎部署 | 真实 cron 未注册（注册留 OC），mem_meta.db 无生命周期事件；wiki/GAI/log.md 侧已 done 在位 | A9 拆两半验证：wiki+GAI+log.md 侧现可过；mem_meta.db events 侧在引擎部署后（qa-post/OC 验证）补观测 |

---

## 4. 测试用例设计

### 4.1 基线断言（研发已有，QA 独立复跑确认）——按需求域归类

| 需求域 | 测试集 | 断言数 | 说明 |
|--------|--------|:---:|------|
| adapter 契约（归一化/白名单/增量/上限/只读/map_id/mirror/command_for/initial_cursor） | mem-core pytest test_sources_kanban.py | 12 | §9.1 用例表前 9 条 + 3 条附加 |
| set-status 契约（幂等/列位/反查/坏行/exit 码/commit 消息） | mem-core pytest test_gai_set_status.py | 14 | §9.1 用例表后 5 条 + 9 条边界 |
| mem-core 全量回归 | mem-core pytest | 214 | 含新增 26 用例 |
| 引擎集成（首跑/生命周期/幂等/只读/fail-open/噪声/dry-run/state 损坏） | test_mem_sync.sh | 47 | A1-A6 + R7 + R6 + 附加 |
| 部署漂移（close.sh must-sync 语义） | test_deploy_drift.sh | 29 | DPL-048 回归 |

### 4.2 静态核对清单（QA 独立代码核对，S1-S12）

| # | 核对项 | 依据 | 结果 |
|---|--------|------|:---:|
| S1 | PRD v2.0 §0 系统蓝图 + §1 多事件源管线 + §2 路线图 ≥3 方向（A10） | PRD 读 | ✅ 本卡已读（§0-§2 完整） |
| S2 | kanban.py 白名单 4 kind 映射（created→create/completed→done/blocked→demote/unblocked→update），其余忽略 | arch §2.2 | ✅ 读码证实（L19-24） |
| S3 | mode=ro URI 只读连接（fetch_events + initial_cursor） | arch §2.6/R4 | ✅ 读码证实（L96/L177） |
| S4 | base.py 新增 initial_cursor/command_for 可选方法（默认 None），gai.py 不受影响 | arch D3 | ✅ 读码证实（base.py L44-51） |
| S5 | map_id 复用 kanban_db.kanban_extract_task_code（D9 单一实现，非 cli 双实现） | arch D9 | ✅ 读码证实（kanban.py L17/L146-153） |
| S6 | SOURCES 注册表含 "kanban" | arch D2 | ✅ 读码证实（__init__.py L11-14） |
| S7 | mem_sync.py 游标分桶 {version, sources:{<source>:{last_event_id}}} + temp+os.replace 原子写 | arch §3.3/D7 | ✅ 读码证实（L76-107） |
| S8 | 命令级幂等依赖 memctl 既有语义（add exit1/done --check/demote 跳过/note 跳过）+ set-status 幂等 | arch D8 | ✅ 读码证实（kanban.py L186-207 + gailinks L132-133） |
| S9 | 每 tick 上限 MEM_SYNC_MAX_EVENTS（默认 50）+ 噪声饿死防护（noise_skip） | arch §3.5 | ✅ 读码证实（L95/L198-208） |
| S10 | fail-open：异常 exit 0，仅用法错误 exit 2；memctl 缺失跳过本轮 | arch §3.5 | ✅ 读码证实（L267-309） |
| S11 | close.sh GAI_FILE 新路径（/workspace/mem-core/gai/...）+ S3b 调 memctl gai-links --set-status | arch §5.2 | ✅ git diff 证实（wt/t_136e5048） |
| S12 | close.sh S3b warn_check 语义（ID 无行 fail-open exit 0；表头无状态列 exit 3 非阻断） | arch §4.2 | ✅ 读码证实（t_136e5048 close.sh L105-107） |

### 4.3 独立探针（P1-P8，qa-exec 阶段执行；P1-P7 本卡已具备实测基础）

| # | 探针 | 目标 | 命令/断言 | 状态 |
|---|------|------|----------|:---:|
| P1 | mem-core pytest 独立复跑 | 214 断言全绿（隔离 mem_meta.db） | `cd /workspace/mem-core && python3 -m pytest` | ✅ 本卡已跑（214 PASS） |
| P2 | 引擎集成独立复跑 | test_mem_sync.sh 47 断言全绿 | `cd /workspace/devPPL/.worktrees/t_cfe5908e && bash scripts/test_mem_sync.sh` | ✅ 本卡已跑（47 PASS） |
| P3 | 部署漂移回归 | test_deploy_drift.sh 29 断言全绿 | `cd /workspace/devPPL && bash scripts/test_deploy_drift.sh` | ✅ 本卡已跑（29 PASS） |
| P4 | 引擎零感知静态复验 | mem_sync.py 无 sqlite3/task_events 直连 | `grep -n "import\|task_events" scripts/mem_sync.py`（应无 sqlite3 import） | ✅ 本卡已 grep |
| P5 | set-status 真实 GAI 行幂等 | GAI MEM-007 已 done → 再跑 exit 0 不写（对真实 GAI 只读核对，不写） | `memctl gai-links --set-status MEM-007 done`（dry 核对 stdout idempotent） | qa-exec 复验 |
| P6 | map_id 编号/回退双路径 | title 含 MEM-007 → MEM-007；无编号 → t_xxx | pytest test_kanban_map_id_code/fallback | ✅ 基线含 |
| P7 | close.sh S3b 修复静态核对 | 新路径 + --set-status 调用（不执行真实 close，只读 diff） | `git diff 34cb6f3..wt/t_136e5048 -- scripts/close.sh` | ✅ 本卡已 diff |
| P8 | A9 真实链路观测 | wiki MEM-007 done + GAI done + log.md done；mem_meta.db events 侧标记待部署 | 只读核对 wiki/GAI/log.md + events 表 | ✅ 本卡已核（OBS-2 拆分） |

### 4.4 验收口径逐项核对（qa-exec 阶段）

A1-A11 的验收证据链：静态 S1-S12（代码 grep/读码）+ 基线三集（pytest 214 + test_mem_sync 47 + deploy_drift 29）+ 探针 P1-P8 + VA 已核 claims（21/21）。qa-exec 逐项打勾，与 VA 结论交叉印证，任何不一致按分级标准处理。

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）代码缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR**（设计阶段） |
| OBS-1（SUB-4/5 未合入 main） | ✅（qa-exec 需在分支测） | ❌（FF-ready，merge 即可） | ✅（直接测 wt/t_cfe5908e + wt/t_136e5048，DPL-028 先例） | 否 | 否 | **观察项**（非功能缺陷，不设 SLA） |
| OBS-2（A9 events 侧待部署） | ✅（Frank 问"生效了吗"） | ❌（wiki/GAI/log.md 已生效） | ✅（部署后观测，OC 注册 cron） | 否 | 否 | **观察项**（部署依赖，非代码缺陷） |

### 5.2 SLA 对照（标准 §8）

设计阶段无 BLOCKER/MAJOR 发现 → 无 SLA 触发。qa-exec 阶段若出现 BLOCKER：4h 响应 + 8h 定位 + 24h 方案；MAJOR：24h 响应 + 72h 方案（按标准 §8 表格执行）。

### 5.3 分级示例对照（标准 §5 表）

- 若 qa-exec 发现「某 kind 漏归一化 → 建卡事件被忽略」类缺陷 → 用户可感知（wiki 不自动建页）+ 功能阻断（自动记录失效）+ 无 workaround → **BLOCKER**（对照标准 §5 表 BLOCKER 行）。
- 若发现「noise_skip 日志格式与文档不一致」→ 用户可感知 + 不阻断（功能正常）+ workaround（人读日志理解）→ **MINOR**。

---

## 6. 测试执行与交付

### 6.1 执行步骤（qa-exec 阶段，先满足 §2 前置）

```bash
# 0. 前置：双仓被测 commit 确认（mem-core main @ cfec21d；devPPL wt/t_cfe5908e @ a63582d；wt/t_136e5048 @ e5bfbb0）
# 1. mem-core pytest 全量（期望 214 passed）
cd /workspace/mem-core && python3 -m pytest
# 2. 引擎集成（期望 47/47）——在 SUB-4 工作树分支执行
cd /workspace/devPPL/.worktrees/t_cfe5908e && bash scripts/test_mem_sync.sh
# 3. 部署漂移回归（期望 29/29）
cd /workspace/devPPL && bash scripts/test_deploy_drift.sh
# 4. 静态核对 S1-S12（逐项，见 §4.2）
# 5. 独立探针 P1-P8（见 §4.3；P1-P7 本卡已跑通，qa-exec 复验 + P8 部署态标注）
# 6. A1-A11 逐项核对（§1.1 表）
# 7. 报告
#    docs/qa/mem007-auto-record-test-report.md
```

### 6.2 交付物

| 交付物 | 路径 |
|--------|------|
| 本测试方案 | `docs/qa/mem007-auto-record-test-plan.md`（本文件） |
| （qa-exec 产出）测试报告 | `docs/qa/mem007-auto-record-test-report.md` |

### 6.3 发布门禁对照（标准 §10）

- BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
- 当前（设计阶段）：BLOCKER=0，MAJOR=0，安全漏洞=0 → 门禁满足（qa-exec 阶段以实测为准更新）。

---

## 7. 工作量评估与拆卡决策（任务 body 要求）

### 7.1 评估依据

| 阶段 | 内容 | 预计轮数 |
|------|------|:---:|
| ① 前置检查 | 双仓被测 commit 确认 + merge-base + py_compile/bash -n（6 项） | 1 |
| ② mem-core pytest | 214 断言（实测 23.66s/遍，可能 2 次迭代） | 2-3 |
| ③ test_mem_sync.sh | 47 断言（实测 ~1min/遍） | 2-3 |
| ④ test_deploy_drift.sh | 29 断言 | 1-2 |
| ⑤ 静态核对 | S1-S12 逐项 + 双仓 diff 核对（13 文件） | 2-3 |
| ⑥ 独立探针 | P1-P8（P1-P7 本卡已跑通，qa-exec 复验成本低；P8 部署态标注） | 2-3 |
| ⑦ AC 逐项核对 | A1-A11（对照 §1.1 表 + VA 结论交叉） | 2-3 |
| ⑧ 报告 | 写 test_report.md + [PRODUCES]/[CLAIM] + 飞书推送 | 2-3 |
| **合计** | | **14-20（中位 17）** |

> 校准说明：本任务为**跨双仓集成型改动**（mem-core adapter + devPPL 引擎 + close.sh 修复），但研发已交付完整测试体系（pytest 26 新用例 + test_mem_sync.sh 47 断言），QA 主要是**独立复跑 + 静态核对 + 少量探针**，无新测试编写。对比 DPL-030（单仓文本注入，估 13-20 不拆）与 DPL-028（单仓管线改造，估 18-24 拆 2），本任务双仓但测试体系最完整，风险主要在被测对象未合入 main（OBS-1）与部署依赖（OBS-2），均为观察项不阻塞。按 DPL-018 校准经验（QA 执行偏差通常 +20-30%），诚实区间 **14-20 轮（中位 17）**。

### 7.2 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | **14-20 轮（中位 17）≤ 20 轮阈值 → 不拆** |
| 模块依赖 | 全部验收共享同一批基线（pytest 214 + test_mem_sync 47 + deploy_drift 29）与同一被测对象；静态/探针/AC 核对均为独立只读操作，无串行数据依赖 |
| 并行收益 | 无——单被测对象 + 共享基线环境，拆卡只会引入 merge/交接成本；且双仓状态（devPPL 未合入）使拆卡后子卡仍需同一套前置确认 |
| 兜底 | 若 qa-exec 实际执行中发现集成用例调试成本超预期，可在执行卡内按建卡铁律拆职责内子卡（assignee=game-qa） |

**决策：不拆卡（[QA-SUB-SPLIT] 1，单张 QA 执行子卡由 autopilot 按链自动建）。**

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | qa-exec 时 devPPL main 已合入 SUB-4/SUB-5（OC merge 可能已发生） | 被测对象变化 | 执行前置确认 merge-base；以合并后 main 为准；与 wt/t_cfe5908e/wt/t_136e5048 内容一致性用 git diff 核对 |
| R2 | 被测代码尚未合入 devPPL main（OBS-1） | qa-exec 在分支上测，与发布态有偏差 | DPL-028 先例（wt/t_ee71cabb 直接测）；qa-post 阶段在 main 上再回归一遍兜底 |
| R3 | A9 mem_meta.db events 侧依赖 cron 部署（OBS-2） | 真实链路验收不完整 | 拆两半：wiki/GAI/log.md 侧现可过；events 侧在 OC 部署后由 qa-post/OC 补观测；QA 报告明确标注部署依赖 |
| R4 | close.sh 部署漂移（repo 2a7f11a3 vs live） | repo 改后 live 不同步 | DPL-048：repo 正本 + 审计报告 + 部署动作留 OC；QA 只核对 repo 正本 + 记录 drift |
| R5 | 探针 P5 涉及真实 GAI 文件 | 只读核对无写风险 | 严格只读（--no-commit + 幂等断言 stdout）；真实写入已在 pytest 隔离环境覆盖 |
| R6 | 基线三集执行时长（pytest 24s + mem_sync ~1min + drift ~10s） | 多轮迭代耗时 | 单遍全绿优先；失败定位用断言名 grep 输出 |

---

## 附：与本方案相关的既有文档

- MEM-007 PRD v2.0：`/workspace/mem-core/wiki/projects/devppl/prd/mem007-auto-record-maintenance-prd-v2.md`
- MEM-007 架构 v1.0：`/workspace/mem-core/wiki/projects/devppl/arch/arch-mem007-auto-record-maintenance.md`
- VA 复核：t_1a5f43f8（21/21 PASS）+ `.va_reports/20260815T152459.json`
- 部署验证规则：`.pipeline/reports/deploy-drift-audit-2026-08-15.md`（DPL-048，close.sh must-sync §1.1/§5）
- QA 发现分级标准：`docs/standards/qa-finding-classification.md` v1.0
- 类似 D1 方案参考：`docs/qa/worker-context-continuity-test-plan.md`（DPL-030，13-20 轮不拆先例）、`docs/qa/pipeline-parallel-dual-review-test-plan.md`（DPL-028，18-24 轮拆 2 serial 先例）
