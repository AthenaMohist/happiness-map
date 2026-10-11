# MEM-007 自动记录维护（kanban 事件 → memctl 自动写 wiki/GAI）— QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-15 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_f8320427 [DEV-QA-POST] mem-core 自动记录维护 — kanban 事件 → memctl 自动写 wiki/GAI（MEM-007）
> 被测状态：**合并后** devPPL main @ `630c2c5` + mem-core main @ `cb4c3d9`（5 张 dev 子卡内容全部在 main，零漂移）
> 前置阶段：PRD t_33c634a1 → DEV t_d4917dec/t_227981f2/t_0d7a4a1a/t_cfe5908e/t_136e5048 → QA-D1 t_a06c8a09 → QA-EXEC t_c8e6ef4e → QA-D2 t_397bf2f9 → VA-QA t_06937309（VERIFIED）→ MERGE t_03121c26（全链 done）
> 上游文档：QA-D1 方案（docs/qa/mem007-auto-record-test-plan.md）、QA-EXEC 报告（docs/qa/mem007-auto-record-test-report.md）、QA-D2 评审（docs/qa/mem007-auto-record-d2-review.md）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §5）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ devPPL main @ `630c2c5`；5 张 dev 子卡全部在 main（a63582d SUB-4 + e5bfbb0 SUB-5 均为祖先，双 diff 为空 = **零漂移合并**）；mem-core main @ `cb4c3d9`（cfec21d 祖先 → SUB-1+2+3 在 main） |
| **合并后无代码变更** | ✅ `b07ffa3..main` 仅 3 次 QA 报告合并（943308b/9df2deb/630c2c5），自 QA-D2 无代码提交 → 无新增回归面 |
| 基线复跑（合并后 main，独立执行） | ✅ mem-core pytest **214 PASS** / test_mem_sync.sh **47/47 PASS** / test_deploy_drift.sh **29/29 PASS**，均 EXIT=0 |
| 语法复验 | ✅ **5/5 OK**（mem_sync.py + kanban.py py_compile、mem_sync.sh/test_mem_sync.sh/close.sh bash -n） |
| A9 真实链路复核 | ✅ wiki/actions/MEM-007.md L8 `status: done` + GAI L29 `\| MEM-007 \| ... \| done \|` + wiki/log.md L84 done 记录 三处全在位 |
| **OBS-2（cron 未注册 / events 侧待部署）** | ⚠️ **维持成立**：root crontab 与 orchestrator jobs.json 均无 mem_sync 条目；mem_meta.db events 侧仍 54 条（53 index_update + 1 index_rebuild）无生命周期事件 |
| **OBS-3（close.sh 部署漂移方向反转）** | ✅ **已解除**：live close.sh md5 **2a7f11a3** == repo close.sh md5（OC 已同步部署新 S3b，部署验证规则一致才 PASS） |
| **新增缺陷（POST 阶段新发现）** | **0 功能缺陷** — 合并未引入回归 |
| 发布门禁（标准 §10） | ✅ **满足**（BLOCKER=0 AND MAJOR=0 AND 安全漏洞=0 AND 无未裁定申诉） |

**结论**：合并过程正确——MEM-007 全部改动（mem-core SUB-1+2+3 + devPPL SUB-4/5）完整在 main、零漂移、无冲突残留、无合并引入回归；合并后基线三集（214/47/29）在发布态 main 上独立复跑全绿，与 QA-EXEC / QA-D2 / VA 三方结论一致。OBS-3（close.sh 部署漂移）已由 OC 同步部署解除；**唯一遗留 OBS-2（cron 注册 + events 侧部署观测）留 OC 处置**。发布门禁满足，MEM-007 收尾闭环。

---

## 1. 合并状态核对（POST 前置检查）

### 1.1 主分支与合并记录

| 检查项 | 命令 | 结果 |
|---|---|---|
| devPPL main tip | `git rev-parse main` | ✅ `630c2c5`（merge: t_397bf2f9 QA-D2 报告进 main） |
| 本卡工作树 == main | `git rev-parse HEAD` | ✅ 相同（630c2c5，worktree wt/t_f8320427 与 main 同 tip） |
| SUB-4 tip 在 main | `git merge-base --is-ancestor a63582d main` | ✅ YES |
| SUB-5 tip 在 main | `git merge-base --is-ancestor e5bfbb0 main` | ✅ YES |
| 合并零漂移（SUB-4） | `git diff a63582d main -- scripts/mem_sync.py scripts/mem_sync.sh scripts/test_mem_sync.sh` | ✅ 空（merged 内容 == dev 分支内容） |
| 合并零漂移（SUB-5） | `git diff e5bfbb0 main -- scripts/close.sh` | ✅ 空 |
| mem-core main tip | `git log -1` | ✅ `cb4c3d9`（mem(gai): set-status MEM-007 done） |
| mem-core SUB 基线 | `git merge-base --is-ancestor cfec21d HEAD` | ✅ YES（SUB-1+2+3 在 main） |
| 自 QA-D2 后的提交 | `git log --oneline b07ffa3..main` | ✅ 仅 943308b/9df2deb/630c2c5（3 次 QA 报告合并，无代码提交） |

### 1.2 上游链完整性（全链 done）

| 卡 | 状态 | 卡 | 状态 |
|---|---|---|---|
| PRD t_33c634a1 | done | QA-D2 t_397bf2f9 | done |
| DEV t_d4917dec (SUB-1) | done | VA-QA t_06937309 | done（VERIFIED 5/5） |
| DEV t_227981f2 (SUB-2) | done | MERGE t_03121c26 | done |
| DEV t_0d7a4a1a (SUB-3) | done | **本卡 t_f8320427** | running |
| DEV t_cfe5908e (SUB-4) | done | | |
| DEV t_136e5048 (SUB-5) | done | | |

---

## 2. 基线复跑结果（合并后 main，独立执行非转述）

### 2.1 mem-core pytest 全量（214 断言）

```bash
cd /workspace/mem-core && python3 -m pytest --tb=no -q
```

- 进度点计数 = **214**，EXIT=0（与 QA-EXEC 214、QA-D2 214、VA 214 四方一致）
- 含新增 26 用例（test_sources_kanban.py 12 + test_gai_set_status.py 14）

### 2.2 test_mem_sync.sh（47 断言，main 上执行）

```bash
cd /workspace/devPPL/.worktrees/t_f8320427 && bash scripts/test_mem_sync.sh
```

```
════════ 结果汇总 ════════
PASS=47 FAIL=0
ALL TESTS PASSED        （EXIT=0）
```

- main 上跑通 → 合并后引擎（scripts/mem_sync.py）与测试脚本在发布态可用
- 含 A1-A6 验收锚点、R6 日志字段、A5 防回写环、A6 fail-open

### 2.3 test_deploy_drift.sh（29 断言）

```bash
cd /workspace/devPPL/.worktrees/t_f8320427 && bash scripts/test_deploy_drift.sh
```

```
== 部署漂移 fixture 测试结果: PASS=29 FAIL=0 ==   （EXIT=0）
```

- DPL-048 回归全绿（漂移检测机制本身正常）

### 2.4 语法复验（5/5 OK）

- `python3 -m py_compile scripts/mem_sync.py` ✅ / `python3 -m py_compile memcore/sources/kanban.py` ✅
- `bash -n scripts/mem_sync.sh` ✅ / `bash -n scripts/test_mem_sync.sh` ✅ / `bash -n scripts/close.sh` ✅

---

## 3. 观察项状态更新（OBS-2 / OBS-3）

| # | 观察 | QA-D2 记录 | QA-POST 实测（本卡） | 状态 |
|---|---|---|---|---|
| OBS-1 | SUB-4/5 未合入 main | 已解除（18e9229/b07ffa3） | 零漂移复确认（§1.1） | ✅ 关闭 |
| OBS-2 | A9 mem_meta.db events 侧依赖引擎部署 | cron 未注册，events 54 条无生命周期 | **root crontab 无 mem_sync；orchestrator jobs.json 8 条 script 无 mem_sync；orchestrator cron 目录无 mem_sync 作业**；events 侧仍 54 条（53 index_update + 1 index_rebuild），无 create/done/demote/update 生命周期事件 | ⚠️ **维持（留 OC）** |
| OBS-3 | close.sh 部署漂移方向反转（repo 新 S3b 先行，live 旧 S3b） | repo=2a7f11a3 vs live=fd22da95 | **live close.sh md5 = 2a7f11a3 == repo close.sh md5**（`md5sum /root/.hermes/profiles/orchestrator/scripts/close.sh /workspace/devPPL/scripts/close.sh` 双侧一致）→ OC 已同步部署新 S3b | ✅ **已解除** |

> OBS-2 处置建议（同 QA-D2/VA）：OC 注册 cron（`*/2 * * * * bash /workspace/devPPL/scripts/mem_sync.sh`，见 mem_sync.sh L10-13 注释）+ 引擎部署后补观测 mem_meta.db events 侧（期望出现 create/done/demote/update 生命周期事件）。本卡只负责记录，部署动作留 OC（DPL-048）。

---

## 4. A9 真实链路复核（本卡独立只读核对）

| 证据点 | 实测 | 结果 |
|---|---|---|
| wiki/actions/MEM-007.md | L8 `status: done` | ✅ |
| GAI GLOBAL_ACTION_ITEMS.md | L29 `\| P0-01 \| MEM-007 \| ... \| done \| 记忆 \| 4h \|` | ✅ |
| wiki/log.md | L84 `done \| MEM-007 \| ... SUB-4（S3）完成`（另 L31/34/37 create + L74 note 记录在位） | ✅ |
| mem_meta.db events 侧 | 54 条全 index_update/index_rebuild，无生命周期事件（OBS-2，依赖 cron 部署） | ⚠️ 待部署观测 |

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|---|---|---|---|---|---|
| （无）功能缺陷 | — | — | — | — | — | **0 BLOCKER/MAJOR/MINOR/SUGGESTION** |
| OBS-2（cron 未注册/events 侧待部署） | ✅（Frank 问"生效了吗"） | ❌（wiki/GAI/log.md 已生效） | ✅（部署后观测，OC 注册 cron） | 否 | 否 | **观察项**（部署依赖，非代码缺陷，不设 SLA） |
| OBS-3（close.sh 部署漂移） | ✅（live 曾执行旧 S3b） | ❌（旧逻辑仍可用，新 S3b 为增量改进） | ✅（同步 repo→live，OC 已执行） | 否 | 否 | **已解除**（md5 双侧一致） |

### 5.2 SLA 对照（标准 §8）

- 本卡 **0 BLOCKER / 0 MAJOR** → **无 SLA 触发**（QA-EXEC / QA-D2 / VA / QA-POST 四阶段均无发现）。
- OBS-2 为部署依赖观察项，不设 SLA；由 OC 在注册 cron 时处置。

### 5.3 分级示例对照（标准 §5 表）

- 未发现「某 kind 漏归一化 → 建卡事件被忽略」类 BLOCKER（S2 白名单全覆盖 + A1 用例绿 + 基线 47/47 含）。
- 未发现「noise_skip 日志格式与文档不一致」类 MINOR（S9 读码一致 + A6 用例绿）。
- 未发现「close.sh 旧路径导致 GAI 找不到」类 MAJOR（S11 新路径 + A7 用例绿 + OBS-3 已部署解除）。

---

## 6. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---|---|---|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。** MEM-007 全链（PRD → DEV → QA-D1/EXEC/D2 → VA → MERGE → QA-POST）闭环，可收尾。

---

## 7. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **OBS-2（唯一遗留）**：OC 注册 cron（`*/2 * * * * bash /workspace/devPPL/scripts/mem_sync.sh`，见 mem_sync.sh L10-13 注释）+ 引擎部署后补观测 mem_meta.db events 侧（期望出现 create/done/demote/update 生命周期事件）。观测结果可挂本卡 comment 或由 OC 复核。
2. **OBS-3（已解除确认）**：live close.sh 已与新 S3b 同步（2a7f11a3 == 2a7f11a3），无需动作；后续 close.sh 改动继续走 repo → merge → OC 同步（DPL-048 部署验证规则）。
3. **回归门禁固化**：MEM-007 全量回归基线已固化（mem-core pytest 214 + test_mem_sync.sh 47 + test_deploy_drift.sh 29），后续任何改动的合并后回归直接复用三集。

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | OBS-2 cron 长期未注册 → 引擎永远不生效（wiki 自动记录不触发） | 功能价值不兑现 | OC 注册 cron + 部署后 events 观测（本卡已记录处置建议） |
| R2 | 后续合入 main 的改动触碰 mem_sync.py/close.sh | 回归 | 每次合并后跑三集基线（214/47/29）作为门禁 |
| R3 | main 工作树 .pipeline/* 脏文件来自并行 dev 管线（manifest.jsonl/gai 夹具，非 MEM-007） | 误判为回归 | 本卡全部测试在 worktree + $TMPT 隔离；已记录环境备注，不触碰 |

---

## 附：执行记录

- 合并状态：devPPL main @ 630c2c5；mem-core main @ cb4c3d9；双 diff 为空（零漂移）；b07ffa3..main 仅 QA 报告合并
- 基线三集（合并后 main 独立复跑）：`cd /workspace/mem-core && python3 -m pytest --tb=no -q`（214，EXIT=0）；`cd /workspace/devPPL/.worktrees/t_f8320427 && bash scripts/test_mem_sync.sh`（47/47，EXIT=0）；`bash scripts/test_deploy_drift.sh`（29/29，EXIT=0）
- 语法：py_compile mem_sync.py/kanban.py + bash -n mem_sync.sh/test_mem_sync.sh/close.sh = 5/5 OK
- A9 复核：wiki L8 done / GAI L29 done / log.md L84 done（只读核对）
- OBS-2 复核：`crontab -l`（root）+ `grep '"script"' /root/.hermes/profiles/orchestrator/cron/jobs.json`（8 条无 mem_sync）+ `/tmp/post_memmeta_probe.py`（events 54 条，mode=ro）
- OBS-3 解除证据：`md5sum /root/.hermes/profiles/orchestrator/scripts/close.sh /workspace/devPPL/scripts/close.sh` = 2a7f11a3 双侧一致
- 本卡发现笔记：`.pipeline/wip/t_f8320427.md`（六节模板）
