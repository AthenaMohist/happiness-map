# MEM-007 自动记录维护（kanban 事件 → memctl 自动写 wiki/GAI）— QA 执行测试报告（test_report.md）

> 版本：v1.0 | 日期：2026-08-15 | 作者：game-qa（独立执行，非研发自测）
>
> 任务卡：t_c8e6ef4e [DEV-QA-EXEC] mem-core 自动记录维护 — kanban 事件 → memctl 自动写 wiki/GAI（MEM-007）
> 上游：t_a06c8a09（QA-D1 测试方案，docs/qa/mem007-auto-record-test-plan.md @ wt/t_a06c8a09，commit 963e73a）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| 被测对象确认 | **mem-core main @ cb4c3d9**（cfec21d 为祖先 → SUB-1+SUB-2+SUB-3 在 main，且后续含 MEM-007 GAI done 提交）；**devPPL wt/t_cfe5908e @ a63582d**（SUB-4 引擎，**未合 main**）；**wt/t_136e5048 @ e5bfbb0**（SUB-5 close.sh 修复，**未合 main**） |
| 基线三集（独立复跑） | mem-core pytest **214 PASS**（EXIT=0，dot 计数=214）/ test_mem_sync.sh **47/47 PASS** / test_deploy_drift.sh **29/29 PASS** |
| 语法 | **6/6 OK**（mem_sync.py py_compile + 3×bash -n + kanban.py py_compile） |
| 静态核对 S1-S12 | **12/12 PASS**（含双仓 diff 核对） |
| 独立探针 P1-P8 | **8/8 PASS** |
| 验收 A1-A11 | **11/11 有证据锚点**（详见 §4.3） |
| **QA 发现** | **0 BLOCKER / 0 MAJOR / 0 MINOR / 0 SUGGESTION**；2 项观察（OBS-1/OBS-2 与 D1 一致，无新增） |

**结论：MEM-007 机制本体（kanban adapter / 引擎零感知 / set-status 幂等 / close.sh S3b 修复）经 QA 独立执行全部成立，发布门禁满足。**

---

## 1. 前置确认（执行前）

| # | 检查项 | 命令/依据 | 结果 |
|---|---|---|---|
| 1 | mem-core 被测 commit 在 main | `git merge-base --is-ancestor cfec21d cb4c3d9` | ✅ cfec21d 是 cb4c3d9 祖先（SUB-1+2+3 在 main） |
| 2 | devPPL SUB-4 是否合入 main | `git merge-base --is-ancestor a63582d f82ca87` | ❌ 未合入 → **OBS-1 确认**（qa-exec 在 wt/t_cfe5908e 测，DPL-028 先例） |
| 3 | devPPL SUB-5 是否合入 main | `git merge-base --is-ancestor e5bfbb0 f82ca87` | ❌ 未合入 → **OBS-1 确认**（qa-exec 在 wt/t_136e5048 测） |
| 4 | 语法 6 项 | py_compile mem_sync.py/kanban.py + bash -n mem_sync.sh/test_mem_sync.sh/close.sh×2 | ✅ 6/6 OK |
| 5 | 部署漂移（R4） | md5 repo main close.sh vs live | ✅ 一致（fd22da95…，旧 S3b 双在；修复部署留 OC per DPL-048） |

---

## 2. 基线三集（独立复跑，非转述）

| # | 测试集 | 命令 | 结果 |
|---|---|---|---|
| G1/P1 | mem-core pytest 全量 | `cd /workspace/mem-core && python3 -m pytest --tb=no -q` | **214 PASS**（EXIT=0；`.` 计数=214；含新增 26 用例） |
| G2/P2 | test_mem_sync.sh（引擎集成 47 断言） | `cd /workspace/devPPL/.worktrees/t_cfe5908e && bash scripts/test_mem_sync.sh` | **PASS=47 FAIL=0**（EXIT=0） |
| G3/P3 | test_deploy_drift.sh（29 断言） | `cd /workspace/devPPL && bash scripts/test_deploy_drift.sh` | **PASS=29 FAIL=0**（EXIT=0） |

> 说明：pytest 输出末尾汇总行被终端包装截断，以 EXIT=0 + 进度点计数 214 双重确认。

---

## 3. 静态核对 S1-S12（QA 独立读码/diff，非转述）

| # | 核对项 | 证据（文件:行） | 结果 |
|---|---|---|---|
| S1 | PRD v2.0 §0 系统蓝图 + §1 多事件源 + §2 路线图 ≥3 方向（A10） | `wiki/projects/devppl/prd/mem007-...-v2.md` L22/L57/L104（472 行） | ✅ |
| S2 | kanban.py 白名单 4 kind 映射，其余忽略 | `memcore/sources/kanban.py` L19-24（created→create/completed→done/blocked→demote/unblocked→update），L116-118 白名单外 continue | ✅ |
| S3 | mode=ro URI 只读连接 | kanban.py L96（fetch_events）、L177（initial_cursor）`file:...?mode=ro` | ✅ |
| S4 | base.py 可选方法 initial_cursor/command_for（默认 None），gai.py 不受影响 | `memcore/sources/base.py` L44-52 | ✅ |
| S5 | map_id 复用 kanban_db.kanban_extract_task_code（D9 单一实现） | kanban.py L17 import + L146-153 | ✅ |
| S6 | SOURCES 注册表含 "kanban" | `memcore/sources/__init__.py` L11-14 `{"gai","kanban"}` | ✅ |
| S7 | 游标分桶 + temp/os.replace 原子写 | `scripts/mem_sync.py` L76-107（load_state/save_state，`{version, sources:{<source>:{last_event_id}}}`，`os.replace(tmp,path)`） | ✅ |
| S8 | 命令级幂等（memctl add exit1/done --check/demote 跳过/note 跳过 + set-status 幂等） | kanban.py L186-207 command_for + gailinks.py L132-133 `if old_value == status: 不写` | ✅ |
| S9 | 每 tick 上限 MEM_SYNC_MAX_EVENTS（默认 50）+ 噪声饿死防护 noise_skip | mem_sync.py L95（limit=50）、L198-208（noise_skip 推进游标） | ✅ |
| S10 | fail-open：异常 exit 0，仅用法错误 exit 2；memctl 缺失跳过本轮 | mem_sync.py L267-309（main fail-open try/except exit 0）、L220-223（memctl_missing） | ✅ |
| S11 | close.sh GAI_FILE 新路径 + S3b 调 memctl gai-links --set-status | `git diff 34cb6f3..HEAD -- scripts/close.sh`（t_136e5048）：GAI_FILE 改 `/workspace/mem-core/gai/GLOBAL_ACTION_ITEMS.md` + warn_check 3b 双命令 --set-status | ✅ |
| S12 | close.sh S3b warn_check 语义（ID 无行 fail-open exit 0；表头无状态列 exit 3 非阻断） | t_136e5048 close.sh L104-107 注释 + warn_check() 函数（L60-78：失败只 WARN 不 FAIL） | ✅ |

---

## 4. 独立探针 P1-P8 与验收核对

### 4.1 探针结果

| # | 探针 | 结果 |
|---|---|---|
| P1 | mem-core pytest 独立复跑 | ✅ 214 PASS |
| P2 | 引擎集成独立复跑 | ✅ 47/47 PASS |
| P3 | 部署漂移回归 | ✅ 29/29 PASS |
| P4 | 引擎零感知：mem_sync.py 无 sqlite3/task_events 直连 | ✅ import 清单仅 argparse/json/os/subprocess/sys/datetime/typing；`grep -c task_events` = **0** |
| P5 | set-status 真实 GAI 幂等（只读） | ✅ `memctl gai-links --set-status MEM-007 done --no-commit` → `idempotent: MEM-007 状态列已 = done（不写不提交）` EXIT=0 |
| P6 | map_id 编号/回退双路径测试在位 | ✅ tests/test_sources_kanban.py L133 `test_kanban_map_id_code` + L142 `test_kanban_map_id_fallback`（含于 214 PASS） |
| P7 | close.sh S3b 修复静态核对 | ✅ git diff 证实（§3 S11/S12） |
| P8 | A9 真实链路观测 | ✅ wiki/actions/MEM-007.md `status: done`；GAI L29 `| P0-01 | MEM-007 | ... | done | 记忆 | 4h |`；wiki/log.md L84 `done | MEM-007 | ... SUB-4（S3）完成`；mem_meta.db events 侧 **54 条（53 index_update + 1 index_rebuild），无生命周期记录** → OBS-2（引擎未部署，注册留 OC） |

### 4.2 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|---|---|---|---|---|---|
| （无）代码缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR/SUGGESTION** |
| OBS-1（SUB-4/5 未合入 devPPL main） | ✅（qa-exec 需在分支测） | ❌（FF-ready，merge 即可） | ✅（直接测 wt/t_cfe5908e + wt/t_136e5048） | 否 | 否 | **观察项**（非功能缺陷，不设 SLA） |
| OBS-2（A9 mem_meta.db events 侧待引擎部署） | ✅（Frank 问"生效了吗"） | ❌（wiki/GAI/log.md 侧已生效） | ✅（部署后观测，OC 注册 cron） | 否 | 否 | **观察项**（部署依赖，非代码缺陷） |

### 4.3 验收 A1-A11 证据链

| # | 验收要点 | 证据 | 结果 |
|---|---|---|---|
| A1 | 建卡 → ≤1 tick wiki 页自动生成 | test_mem_sync.sh A1a-A1d（P2 47/47 含） | ✅ |
| A2 | completed → wiki status=done + 结果节 + GAI 状态列 done | test_mem_sync.sh A2a-A2e + test_gai_set_status 幂等（P1 含）+ P5 真实幂等 | ✅ |
| A3 | blocked → wiki status=blocked + 执行记录含 reason | test_mem_sync.sh A3a-A3e | ✅ |
| A4 | 幂等：同事件 3 次无新增 | test_mem_sync.sh A4a-A4g | ✅ |
| A5 | 防回写环：kanban.db md5 一致 | test_mem_sync.sh A5a | ✅ |
| A6 | fail-open：memctl 缺失 exit 0 / 单事件失败其余照常 | test_mem_sync.sh A6a-A6o | ✅ |
| A7 | close.sh S3b 修复：新路径 + 状态列更新 | S11/S12 + P7 | ✅ |
| A8 | 回归：pytest 全绿 + test_mem_sync.sh ≥10 断言 | P1 214 + P2 47 | ✅ |
| A9 | 真实链路：MEM-007 done → events done + GAI done | P8：wiki+GAI+log.md 三处 done 在位；mem_meta.db events 侧 **待部署**（OBS-2） | ✅（拆分验证） |
| A10 | 蓝图定位：PRD §0-§2 完整 | S1 | ✅ |
| A11 | 组件前瞻：kanban.py 继承 SourceAdapter / --source 分发 / 游标分桶 | S2-S7 + P4 | ✅ |

### 4.4 SLA 对照（标准 §8）

qa-exec 阶段 **0 BLOCKER / 0 MAJOR** → **无 SLA 触发**。与 D1 一致的 2 项观察项不设 SLA。

### 4.5 分级示例对照（标准 §5 表）

- 未发现「某 kind 漏归一化 → 建卡事件被忽略」类 BLOCKER（S2 白名单全覆盖 + A1 用例绿）。
- 未发现「noise_skip 日志格式与文档不一致」类 MINOR（S9 读码一致 + A6 用例绿）。

---

## 5. 观察项（非缺陷，登记备查，与 D1 一致）

| # | 观察 | 现状（qa-exec 实测） | 处置建议 |
|---|---|---|---|
| OBS-1 | SUB-4/SUB-5 未合入 devPPL main | mem_sync.py/mem_sync.sh/test_mem_sync.sh 仅在 wt/t_cfe5908e（a63582d）；close.sh 修复仅在 wt/t_136e5048（e5bfbb0）；main close.sh 仍旧 S3b（fd22da95） | qa-post 阶段在 main 上再回归一遍兜底（R2）；merge 动作由 OC 执行 |
| OBS-2 | A9 的 mem_meta.db events 侧依赖引擎部署 | mem_meta.db events 54 条全 index_update/index_rebuild，无生命周期事件；真实 cron 未注册（留 OC） | OC 注册 cron + 引擎部署后由 qa-post/OC 补观测 events 侧 |

---

## 6. 发布门禁对照（标准 §10）

- **BLOCKER=0** AND **MAJOR=0**（≤3）AND **安全漏洞=0** AND **无未裁定的申诉** → **门禁满足 ✅**
- 风险登记（test-plan §8）：R1 双仓被测对象确认已执行；R2 分支测试偏差由 qa-post 兜底；R3 A9 拆分验证已执行；R4 部署漂移 repo==live 一致、修复部署留 OC；R5 探针 P5 以 --no-commit 只读执行；R6 基线三集单遍全绿。

---

## 7. 交付物

| 交付物 | 路径 |
|---|---|
| 本测试报告 | `docs/qa/mem007-auto-record-test-report.md`（本文件） |
| 上游测试方案 | `docs/qa/mem007-auto-record-test-plan.md`（t_a06c8a09，commit 963e73a @ wt/t_a06c8a09） |
| 发现笔记 | `.pipeline/wip/t_c8e6ef4e.md` |

**执行轮数：约 12 轮（≤ 20 阈值，不拆卡正确）。**
