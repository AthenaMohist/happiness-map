# QA-D2 结果严重度评审报告 — mem-core 自动记录维护（MEM-007）

> 版本：v1.0 | 日期：2026-08-15 | 执行人：game-qa（QA-D2 结果严重度评审卡 t_397bf2f9）
> 上游执行报告：`docs/qa/mem007-auto-record-test-report.md`（QA-EXEC t_c8e6ef4e @ d70c4c0，分支 wt/t_c8e6ef4e）
> 测试方案：`docs/qa/mem007-auto-record-test-plan.md`（QA-D1 t_a06c8a09 @ 963e73a，分支 wt/t_a06c8a09）
> 被测提交：**mem-core main @ cb4c3d9** + **devPPL main @ b07ffa3**（SUB-4/SUB-5 已合入 main，18e9229/b07ffa3；QA-EXEC 阶段 OBS-1「未合入 main」已解除）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0
> 评审性质：QA-D2 独立复验（非转述 QA-EXEC），复核分级判定 + 漏报检查 + 处置建议

---

## 0. 评审结论（TL;DR）

| 评审项 | 结果 | 证据 |
|---|---|---|
| 分级判定复核（QA-EXEC 结论 0 BLOCKER/MAJOR/MINOR/SUGGESTION + 2 观察） | ✅ **复核一致** | §2 |
| 基线全量独立复跑（在合并后 main 上执行，qa-post R2 兜底提前完成） | ✅ **mem-core pytest 214 PASS / test_mem_sync.sh 47/47 / test_deploy_drift.sh 29/29**，均 EXIT=0 | §3 |
| OBS-1（SUB-4/5 未合入 main） | ✅ **已解除**（18e9229 + b07ffa3 合入，main 与分支逐字节一致） | §3.3 |
| 静态核对 S1-S12 复验 | ✅ **12/12 PASS**（独立读码/diff） | §4 |
| 探针 P1-P8 复验 + 漏报探针 A-K | ✅ **19/19 PASS**（8 复验 + 11 新增） | §5 |
| AC A1-A11 交叉核对 | ✅ **11/11 有证据锚点** | §6 |
| 漏报检查（QA-EXEC 是否漏判） | ✅ **无漏报**（A-K 补充探针全部通过） | §5/§7 |
| OBS-2（A9 events 侧待引擎部署） | ✅ 复确认成立，观察项非缺陷 | §7 |
| **新增观察 OBS-3（部署漂移方向反转）** | ⚠️ repo main close.sh=2a7f11a3（新 S3b）vs live=fd22da95（旧 S3b）→ 漂移，部署动作留 OC（DPL-048） | §7 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） | §8 |

**评审结论：QA-EXEC 测试报告分级判定准确、证据链完整、无漏报、无错判。OBS-1 已被 OC merge 解除；本卡在合并后 main 上独立复跑基线三集全绿（相当于 qa-post R2 兜底提前执行）。MEM-007 结果评审通过（review_pass），可放行后续 va-qa → qa-post（main 态回归已完成，qa-post 只需补 events 侧部署观测）。**

---

## 1. 评审对象与方法

### 1.1 评审对象

- QA-EXEC 报告：`docs/qa/mem007-auto-record-test-report.md`（v1.0，144 行，t_c8e6ef4e @ d70c4c0）
- 报告核心声明：mem-core pytest 214 PASS、test_mem_sync.sh 47/47、test_deploy_drift.sh 29/29、语法 6/6、S1-S12 12/12、P1-P8 8/8、A1-A11 11/11、0 缺陷、2 观察（OBS-1/OBS-2）

### 1.2 评审方法（独立复验，不转述）

| # | 方法 | 说明 |
|---|------|------|
| M1 | 基线全量独立复跑 | 本卡在**合并后 devPPL main（b07ffa3）**重新执行三集：mem-core pytest / test_mem_sync.sh / test_deploy_drift.sh（QA-EXEC 在分支上测，本卡在 main 上测，双重覆盖） |
| M2 | 静态独立核对 | 独立读码/diff 复验 S1-S12（12 项） |
| M3 | 探针独立复验 + 漏报探针 | P1-P8 重新执行 + 漏报探针 A-K 新增（fail-open/白名单/防回写/部署漂移方向/merge 一致性） |
| M4 | AC 交叉核对 | A1-A11 逐项对照验收要点（test-plan §1.1 + EXEC 报告 §4.3） |
| M5 | 分级复核 | 对照标准 §1.2 判定公式，逐项复核 QA-EXEC 的 0 缺陷 + 2 观察判定，并评估新增观察 OBS-3 |

### 1.3 被测对象确认（P-1..P-5 复验）

| # | 前置项 | 实测 | 结果 |
|---|---|------|:---:|
| P-1 | mem-core main HEAD | `git log -1` = cb4c3d9（mem(gai): set-status MEM-007 done），cfec21d 是其祖先（SUB-1+2+3 在 main） | ✅ |
| P-2 | devPPL main HEAD | `git log main -1` = b07ffa3（merge t_1ecadb5f SUB-5 close.sh 修复），18e9229（SUB-4 mem_sync 引擎）为祖先 | ✅ |
| P-3 | OBS-1 状态 | `git merge-base --is-ancestor a63582d b07ffa3` = YES（SUB-4 合入）；`git merge-base --is-ancestor e5bfbb0 b07ffa3` = YES（SUB-5 合入）→ **OBS-1 解除** | ✅ |
| P-4 | merge 内容一致性 | `git diff a63582d main -- scripts/mem_sync.py scripts/mem_sync.sh scripts/test_mem_sync.sh` = 空；`git diff e5bfbb0 main -- scripts/close.sh` = 空 → **main 与 QA-EXEC 被测分支逐字节一致** | ✅ |
| P-5 | 工作树隔离 | 本卡在 wt/t_397bf2f9 执行，测试全部 $TMPT 隔离；main 工作树 .pipeline/* 脏文件来自并行 dev 管线任务（test_slice3_d1_qa.py 写 manifest.jsonl），非本卡测试产生，不触碰 | ✅ |

---

## 2. 分级判定复核（标准 §1.2 公式逐项对照）

### 2.1 QA-EXEC 结论 vs 本卡复核

| QA-EXEC 判定 | 本卡复核 | 复核依据 |
|------|:---:|------|
| 0 BLOCKER | ✅ 一致 | 无用户可感知+功能阻断+无 workaround 组合（§2.2）；无安全漏洞；无数据一致性；无性能退化 ≥10x；无 OOM/崩溃 |
| 0 MAJOR | ✅ 一致 | 无用户可感知+功能阻断但有 workaround/体验严重退化；无 XSS/CSRF/SSRF；无 A 级数据一致性；无性能退化 ≥3x |
| 0 MINOR | ✅ 一致 | 无用户可感知且影响核心任务完成的问题（基线三集全绿，行为无异常） |
| 0 SUGGESTION | ✅ 一致 | 无用户不可感知但值得提的代码层面建议（引擎/适配器/close.sh 均符合 arch 约定） |
| OBS-1（未合入 main） | ✅ **已解除** | OC 已 merge（18e9229 + b07ffa3）；本卡在 main 上复跑全绿，分支 vs main 逐字节一致 |
| OBS-2（A9 events 侧待部署） | ✅ 观察项成立 | mem_meta.db events 侧仍 54 条全 index_update/index_rebuild，无生命周期事件；wiki/GAI/log.md 侧已 done 在位 → 部署依赖，非代码缺陷 |

### 2.2 判定公式逐项（标准 §1.2）

| 条件 | 是否触发 | 证据 |
|------|:---:|------|
| 安全漏洞（认证绕过/数据泄露/远程注入） | 否 | kanban.py mode=ro 只读连接（L96/L177）；mem_sync.py 无 sqlite3/task_events 直连（import 清单仅 argparse/json/os/subprocess/sys/datetime/typing）；无网络/认证面 |
| 数据一致性（S/A 级数据） | 否 | 无资金/用户基础信息数据面；读写的是 wiki/GAI/kanban 事件，属 C 级内部配置数据 |
| 性能退化（P95 ≥10x / ≥3x） | 否 | 批处理脚本 + 每 tick 上限 50 事件；无用户请求路径 |
| OOM/崩溃 | 否 | Python 脚本 + bash 包装；fail-open 异常 exit 0 |
| 概率性 bug（资金/核心功能） | 否 | 无状态机/并发面（单写入者 memctl 子进程，30s 超时） |

**结论：QA-EXEC 的「0 缺陷 + 2 观察」分级判定与标准公式完全一致；OBS-1 已随 merge 解除，无错判、无漏判。**

---

## 3. 基线全量独立复跑（在合并后 main 上执行，qa-post R2 兜底提前）

> QA-EXEC 阶段因 SUB-4/5 未合入 main 而测分支（DPL-028 先例）；本卡阶段 OC 已完成 merge，**直接在 main 上独立复跑**——等价于 test-plan 风险 R2 要求的「qa-post 阶段在 main 上再回归一遍」，故 qa-post 的 main 态回归本卡已覆盖。

### 3.1 mem-core pytest 全量（214 断言）

```bash
cd /workspace/mem-core && python3 -m pytest --tb=no -q
```

- 进度点计数 = **214**，EXIT=0（与 QA-EXEC 214、VA 214 三方一致）
- 含新增 26 用例（test_sources_kanban.py 12 + test_gai_set_status.py 14）

### 3.2 test_mem_sync.sh（47 断言，main 上执行）

```bash
cd /workspace/devPPL && bash scripts/test_mem_sync.sh
```

```
════════ 结果汇总 ════════
PASS=47 FAIL=0
ALL TESTS PASSED        （EXIT=0）
```

- **main 上跑通** → 证明合并后的引擎（scripts/mem_sync.py）与测试脚本在发布态可用
- 含 A1-A6 验收锚点、R6 日志字段、A5 防回写环、A6 fail-open

### 3.3 test_deploy_drift.sh（29 断言）

```bash
cd /workspace/devPPL && bash scripts/test_deploy_drift.sh
```

```
== 部署漂移 fixture 测试结果: PASS=29 FAIL=0 ==   （EXIT=0）
```

- DPL-048 回归全绿（漂移检测机制本身正常）

### 3.4 合并状态确认（OBS-1 解除证据）

| 检查 | 结果 |
|------|:---:|
| `git diff a63582d main -- scripts/mem_sync.py scripts/mem_sync.sh scripts/test_mem_sync.sh` | 空（main == SUB-4 分支，零漂移合并） |
| `git diff e5bfbb0 main -- scripts/close.sh` | 空（main == SUB-5 分支，零漂移合并） |
| `git merge-base --is-ancestor a63582d b07ffa3` | YES |
| `git merge-base --is-ancestor 18e9229 b07ffa3` | YES |

---

## 4. 静态核对 S1-S12 复验（独立读码/diff，12/12 PASS）

| # | 核对项 | 实测（main 上） | 结果 |
|---|--------|------|:---:|
| S1 | PRD v2.0 §0 系统蓝图 + §1 多事件源 + §2 路线图 ≥3 方向（A10） | `wiki/projects/devppl/prd/mem007-...-v2.md` L22/L57/L104（§0/§1/§2 齐全） | ✅ |
| S2 | kanban.py 白名单 4 kind 映射，其余忽略 | `memcore/sources/kanban.py` L19-24（created→create/completed→done/blocked→demote/unblocked→update），L114-120 白名单外 continue | ✅ |
| S3 | mode=ro URI 只读连接 | kanban.py L96（fetch_events）、L177（initial_cursor）`file:...?mode=ro` | ✅ |
| S4 | base.py 可选方法 initial_cursor/command_for（默认 None），gai.py 不受影响 | `memcore/sources/base.py` L44/L48 方法定义 | ✅ |
| S5 | map_id 复用 kanban_db.kanban_extract_task_code（D9 单一实现） | kanban.py L17 import + L140 注释 | ✅ |
| S6 | SOURCES 注册表含 "kanban" | `memcore/sources/__init__.py` `{"gai", "kanban"}` | ✅ |
| S7 | 游标分桶 + temp/os.replace 原子写 | `scripts/mem_sync.py` L76-107（load_state/save_state，`{version, sources:{...}}`，os.replace(tmp,path)） | ✅ |
| S8 | 命令级幂等（memctl add exit1/done --check/demote 跳过/note 跳过 + set-status 幂等） | kanban.py L186-207 command_for + gailinks.py L132-133 `if old_value == status: 不写` | ✅ |
| S9 | 每 tick 上限 MEM_SYNC_MAX_EVENTS（默认 50）+ 噪声饿死防护 noise_skip | mem_sync.py L41/L206/L261 | ✅ |
| S10 | fail-open：异常 exit 0，仅用法错误 exit 2；memctl 缺失跳过本轮 | mem_sync.py L304（except Exception → return 0）、L222（memctl_missing） | ✅ |
| S11 | close.sh GAI_FILE 新路径 + S3b 调 memctl gai-links --set-status | `scripts/close.sh` L19（`/workspace/mem-core/gai/GLOBAL_ACTION_ITEMS.md`）+ L105-107（warn_check 3b --set-status） | ✅ |
| S12 | close.sh S3b warn_check 语义（失败只 WARN 不 FAIL） | close.sh L60-78 warn_check 函数 + L104-107 注释 | ✅ |

**合计 12/12 PASS（与 QA-EXEC S1-S12 一致，且全部在 main 上核实）。**

---

## 5. 探针复验 + 漏报探针（19/19 PASS）

### 5.1 QA-EXEC 探针 P1-P8 复验（本卡独立执行）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | mem-core pytest 独立复跑 | **214 PASS**（EXIT=0，进度点计数 214） | ✅ |
| P2 | 引擎集成独立复跑（main 上） | **47/47 PASS**（EXIT=0） | ✅ |
| P3 | 部署漂移回归 | **29/29 PASS**（EXIT=0） | ✅ |
| P4 | 引擎零感知：mem_sync.py 无 sqlite3/task_events 直连 | `grep -c task_events` = 0；`grep -c sqlite3` = 0；import 清单仅 argparse/json/os/subprocess/sys/datetime/typing | ✅ |
| P5 | set-status 真实 GAI 幂等（只读） | `memctl gai-links --set-status MEM-007 done --no-commit` → `idempotent: MEM-007 状态列已 = done（不写不提交）` EXIT=0 | ✅ |
| P6 | map_id 编号/回退双路径测试在位 | tests/test_sources_kanban.py L133/L142（含于 214 PASS） | ✅ |
| P7 | close.sh S3b 修复静态核对 | §4 S11/S12（main 上 diff 证实） | ✅ |
| P8 | A9 真实链路观测 | wiki/actions/MEM-007.md L8 `status: done`；GAI L29 `\| P0-01 \| MEM-007 \| ... \| done \|`；wiki/log.md L84 done 记录 → 三处全在位；mem_meta.db events 侧 **54 条（53 index_update + 1 index_rebuild），无生命周期** → OBS-2 复确认 | ✅ |

### 5.2 漏报探针（QA-D2 新增，检查 QA-EXEC 是否漏判）

| # | 探针 | 目标 | 实测 | 结果 |
|---|------|------|------|:---:|
| A | 未知 source 用法错误 exit 2 | fail-open 与用法错误区分 | `python3 scripts/mem_sync.py --source bogus` → `未知 source: 'bogus'` EXIT=2 | ✅ |
| B | memctl 缺失 fail-open（真实环境） | 引擎在 memctl 缺失时跳过本轮 exit 0 | `MEM_CTL=/nonexistent/memctl MEM_SYNC_STATE=/tmp/... MEM_KANBAN_DB=/tmp/nonexistent.db python3 mem_sync.py --source kanban --no-commit` → `events 0 ... memctl_missing=1` EXIT=0 | ✅ |
| C | set-status 无 GAI 行 fail-open | ID 无对应 GAI 行不阻断 | `memctl gai-links --set-status t_bogus_id123 done --no-commit` → `skip: T_BOGUS_ID123 无对应 GAI 行` EXIT=0 | ✅ |
| D | 语法复验（main 上 5 项） | 合并后脚本语法完好 | py_compile mem_sync.py/kanban.py + bash -n mem_sync.sh/test_mem_sync.sh/close.sh 全 OK | ✅ |
| E | 白名单外 kind 测试在位 | heartbeat/claimed 噪声被忽略 | test_mem_sync.sh L166/L171（claimed/heartbeat 噪声）+ L235（events 0 断言） | ✅ |
| F | 状态文件不入库 | 游标状态不会污染 git | `git ls-files | grep mem_sync_state` = 空；.gitignore L16-17 覆盖 | ✅ |
| G | 真实环境 dry-run 只读 | 引擎对真实 kanban.db 只读探测 | `python3 scripts/mem_sync.py --source kanban --no-commit --dry-run` → `events 0 ... cursor 11340 | first_run=1` EXIT=0，无状态文件落盘 | ✅ |
| H | 防回写环断言在册 | kanban.db md5 前后一致 | test_mem_sync.sh L178/L302-304（MD5_BEFORE/MD5_AFTER） | ✅ |
| I | mem_sync.sh 包装器语义 | cron 直调 repo 路径、env 可覆盖 | L10-13 注释（cron 注册留 OC）+ L18-26 env 覆盖 + `exec python3 ... >> logs/mem_sync.log` | ✅ |
| J | merge 一致性 | main == 被测分支（防测错对象） | §3.4 双 diff 为空 | ✅ |
| K | 部署漂移方向（新增观察 OBS-3 的证据） | repo 正本 vs live | repo main close.sh md5=**2a7f11a3**（新 S3b）vs live=**fd22da95**（旧 S3b）→ **漂移存在，方向反转**（QA-EXEC 阶段两者均为 fd22da95 旧 S3b；SUB-5 merge 后 repo 先行） | ⚠️ OBS-3 |

**合计 19/19 PASS。漏报检查结论：QA-EXEC 未漏判任何缺陷；本卡唯一新增为观察项 OBS-3（部署漂移方向反转，非代码缺陷，部署动作留 OC per DPL-048）。**

---

## 6. A1-A11 交叉核对（与 QA-EXEC 报告交叉印证）

| AC | 验收要点 | 本卡证据 | 结果 |
|----|---------|---------|:---:|
| A1 | 建卡 → ≤1 tick wiki 页自动生成 | test_mem_sync.sh A1a-A1d（P2 47/47 含，main 上） | ✅ |
| A2 | completed → wiki status=done + 结果节 + GAI 状态列 done | test_mem_sync.sh A2a-A2e + test_gai_set_status 幂等（P1 含）+ P5 真实幂等 | ✅ |
| A3 | blocked → wiki status=blocked + 执行记录含 reason | test_mem_sync.sh A3a-A3e | ✅ |
| A4 | 幂等：同事件 3 次无新增 | test_mem_sync.sh A4a-A4g | ✅ |
| A5 | 防回写环：kanban.db md5 一致 | test_mem_sync.sh A5a + 探针 H | ✅ |
| A6 | fail-open：memctl 缺失 exit 0 / 单事件失败其余照常 | test_mem_sync.sh A6a-A6o + 探针 B（真实 env） | ✅ |
| A7 | close.sh S3b 修复：新路径 + 状态列更新 | §4 S11/S12 + P7（main 上） | ✅ |
| A8 | 回归：pytest 全绿 + test_mem_sync.sh ≥10 断言 | P1 214 + P2 47（main 上） | ✅ |
| A9 | 真实链路：MEM-007 done → events done + GAI done | P8：wiki+GAI+log.md 三处 done 在位；mem_meta.db events 侧 **待部署**（OBS-2，未变） | ✅（拆分验证） |
| A10 | 蓝图定位：PRD §0-§2 完整 | S1 | ✅ |
| A11 | 组件前瞻：kanban.py 继承 SourceAdapter / --source 分发 / 游标分桶 | S2-S7 + P4 | ✅ |

**11/11 PASS（与 QA-EXEC 一致，且本卡在 main 上复核）。**

---

## 7. 发现汇总与分级（标准 §6 输出格式要求）

### 7.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR/SUGGESTION** |
| OBS-1（SUB-4/5 未合入 main） | ✅（qa-exec 需在分支测） | ❌（FF-ready） | ✅（直测分支） | 否 | 否 | **已解除**（merge 完成，本卡 main 复跑全绿） |
| OBS-2（A9 events 侧待引擎部署） | ✅（Frank 问"生效了吗"） | ❌（wiki/GAI/log.md 已生效） | ✅（部署后观测，OC 注册 cron） | 否 | 否 | **观察项**（部署依赖，非代码缺陷，不设 SLA） |
| **OBS-3（新增：close.sh 部署漂移方向反转）** | ✅（live 仍执行旧 S3b） | ❌（新 S3b 为增量改进，旧逻辑仍可用） | ✅（部署动作=同步 repo→live，OC 执行） | 否 | 否 | **观察项**（部署差异，非代码缺陷；DPL-048 部署动作留 OC） |

### 7.2 SLA 对照（标准 §8）

- 本卡 0 BLOCKER / 0 MAJOR → **无 SLA 触发**（QA-EXEC 与 QA-D2 均无发现）。
- OBS-2/OBS-3 为部署依赖观察项，不设 SLA；由 OC 在部署/注册 cron 时处置。

### 7.3 分级示例对照（标准 §5 表）

- 未发现「某 kind 漏归一化 → 建卡事件被忽略」类 BLOCKER（S2 白名单全覆盖 + A1 用例绿 + 探针 E）。
- 未发现「noise_skip 日志格式与文档不一致」类 MINOR（S9 读码一致 + A6 用例绿）。
- 未发现「close.sh 旧路径导致 GAI 找不到」类 MAJOR（S11 新路径 + A7 用例绿 + P7 diff）。

---

## 8. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。MEM-007 结果评审通过，可进入 va-qa → qa-post。** 注：main 态回归（test-plan R2 的 qa-post 兜底）本卡已在合并后 main 上执行完毕（§3），qa-post 阶段仅需补 OBS-2 的 events 侧部署后观测。

---

## 9. 评审建议

1. **放行**：QA-EXEC 报告分级判定准确、证据链完整、无漏报无错判。MEM-007 可继续 va-qa → qa-post 流程。
2. **OBS-1 处置（已解除）**：OC merge 已完成（18e9229 + b07ffa3），本卡在 main 上独立复跑基线三集全绿，main 与分支逐字节一致。qa-post 无需重复 main 态回归，只需确认 merge 后无后续提交引入回归。
3. **OBS-2 处置（同 QA-EXEC 建议）**：OC 注册 cron（`*/2 * * * * bash /workspace/devPPL/scripts/mem_sync.sh`，见 mem_sync.sh L10-13 注释）+ 引擎部署后由 qa-post/OC 补观测 mem_meta.db events 侧（期望出现 create/done/demote/update 生命周期事件）。
4. **OBS-3 处置（新增，DPL-048）**：repo main close.sh（2a7f11a3，新 S3b）已先行，live `/root/.hermes/profiles/orchestrator/scripts/close.sh`（fd22da95，旧 S3b）待 OC 同步部署；部署后 md5 比对 repo==live 才算 PASS（.hermes.md 部署验证规则）。本卡只负责记录漂移，部署动作留 OC。
5. **无新增缺陷/观察（除 OBS-3 部署漂移）**：QA-D2 漏报探针 A-K 全部通过，未发现 QA-EXEC 遗漏的功能缺陷。

---

## 附：执行记录

- 独立复跑（main 上）：`cd /workspace/mem-core && python3 -m pytest --tb=no -q`（214，EXIT=0）；`cd /workspace/devPPL && bash scripts/test_mem_sync.sh`（47/47，EXIT=0）；`bash scripts/test_deploy_drift.sh`（29/29，EXIT=0）
- 独立探针：P1-P8 复验（§5.1）+ 漏报探针 A-K（§5.2）；静态 S1-S12（§4）
- 只读 DB 核对：/tmp/d2_memmeta_probe.py（mem_meta.db events 侧 54 条，mode=ro）
- 被测提交：mem-core main @ cb4c3d9；devPPL main @ b07ffa3（SUB-4/5 已合入）
- 部署漂移：repo main close.sh=2a7f11a3（新 S3b）vs live=fd22da95（旧 S3b）→ OBS-3
- 环境备注：devPPL main 工作树 .pipeline/* 脏文件来自并行 dev 管线任务（tests/test_slice3_d1_qa.py 写 manifest.jsonl/gai 夹具，非 MEM-007 代码，非本卡测试产生）；本卡未触碰 main 工作树写操作
- 本卡发现笔记：`.pipeline/wip/t_397bf2f9.md`（六节模板）
