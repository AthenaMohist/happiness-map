# worker 上下文连续性（DPL-030）— QA-POST 合并后测试报告

> 版本：v1.0 | 日期：2026-08-15 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_9e925eff [DEV-QA-POST] worker 上下文连续性 — 检查点提交+发现笔记+预算收紧+审批白名单（DPL-030）
> 被测状态：**合并后** devPPL main @ `86c4ec6`（dev 4 子卡经 merge 卡 t_d0462d23 逐张合入：a15af93 → d39f6fa → 9ecc4e5 → 86c4ec6）
> 前置阶段：PRD t_84c53424 → ARCH t_d24d1ad5 → DEV t_ab9a26b3/t_8458422f/t_5213b5dd/t_7c9d1952 → QA-D1 t_07b1c297 → QA-EXEC t_863366a3 → QA-D2 t_cfd940c3 → VA-QA t_74724cf6 → MERGE t_d0462d23（全链 done，见 §1.4）
> 上游文档（分支上）：`docs/prd/worker-context-continuity-prd.md`（v1.0，255 行）、`docs/arch/arch-worker-context-continuity.md`（v1.0，329 行）、QA-D1 方案（89b0ca2）、QA-EXEC 报告（ef63d3c）、QA-D2 评审（66a6c87）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §5）

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并状态核对** | ✅ main @ `86c4ec6`，DPL-030 改动面 **11 文件 +381/-9** 全部在 main；dev tip ea489fb 为 main 祖先（FF 语义）；merged 内容 == dev 分支内容（零漂移，git diff 为空） |
| 基线复跑 `test_cmd_channel.sh`（合并后，独立执行） | ✅ **386 PASS / 0 FAIL** EXIT=0（含 DPL-030 新增 13 断言 T59h/T60b-d/T63a-i） |
| chain_check 复跑 `test_chain_check.sh` | ✅ **38 PASS / 0 FAIL** EXIT=0（OBS-2 复确认：文档口径 41 vs 实测 38） |
| 静态核对 S1-S11（独立探针脚本） | ✅ **20/20 PASS**（§3.3） |
| 探针 P1-P6 + 漏报探针 A-F（独立执行） | ✅ **14/14 PASS**（§3.4） |
| AC-1..AC-10 交叉核对 | ✅ **10/10 PASS**（与 VA 15/15 VERIFIED 报告 20260814T201000.json 一致） |
| 相邻模块回归 | ✅ workspace_check **40/40** + idle_check **19/19**（合并未波及） |
| 真实环境只读核对 | ✅ 9 profile SOUL 注入现场 9/9 + inject --dry-run SKIP 9/9 + --verify 9/9 + devppl_query comments 合法/非法 id |
| **新增缺陷（POST 阶段新发现）** | **0 功能缺陷** — 合并未引入回归 |
| 文档观察（POST 新发现） | **POST-01（MINOR）**：DPL-030 文档链（PRD/arch/QA 报告/est 共 7 文件）**未合入 main**，constants.py L234 规范源引用悬空（详见 §4.1） |
| 既有观察维持 | OBS-1（未合入 main）→ 已由 merge 关闭；OBS-2（chain_check 41 vs 38 文档口径差）→ 维持 |

**结论**：合并过程正确——DPL-030 改动面完整在 main（11 文件 +381/-9 与 PRD/arch 范围一致）、无冲突残留、无合并引入的新回归；合并后基线 386/0、chain_check 38/0、静态 20/20、探针 14/14、AC 10/10、相邻模块 40+19 全绿，与 QA-EXEC / QA-D2 / VA 三方结论一致。**唯一新增项 POST-01（MINOR，文档链未上 main）不阻塞发版**。**发布门禁：BLOCKER=0、MAJOR=0（≤3）、安全漏洞=0、无未裁定申诉 → 满足。** 建议后续 merge 时补合 DPL-030 文档链（PRD/arch/QA 报告/est），关闭 POST-01。

---

## 1. 合并状态核对（POST 前置检查）

### 1.1 主分支与合并记录

| 检查项 | 命令 | 结果 |
|---|---|---|
| 主分支 tip | `git log --oneline -1 main` | ✅ `86c4ec6 autopilot merge: t_d0462d23 (wt/t_7c9d1952)` |
| 本卡工作树 == main | `git rev-parse HEAD main` | ✅ 相同（86c4ec6f…219） |
| 合并链 | `git log --oneline e714aa1..main` | ✅ 4 次 autopilot merge（a15af93 S1a / d39f6fa S1b / 9ecc4e5 S2 / 86c4ec6 S3） |
| dev tip 在 main | `git merge-base --is-ancestor wt/t_7c9d1952 main` | ✅ YES（ea489fb 已合入） |
| 合并零漂移 | `git diff wt/t_7c9d1952 main --stat` | ✅ 空（merged 内容 == dev 分支内容） |

### 1.2 DPL-030 改动面核对（e714aa1..main）

```
 .pipeline/wip/t_5213b5dd.md |  49 ++
 .pipeline/wip/t_7c9d1952.md |  47 ++
 .pipeline/wip/t_8458422f.md |  45 ++
 .pipeline/wip/t_ab9a26b3.md |  34 ++
 pipeline/cmd_chain.py       |  11 ++
 pipeline/constants.py       |  45 ++
 pipeline/discover.py        |   7 ++
 scripts/autopilot.sh        |  10 +-
 scripts/devppl_query.sh     |  11 ++
 scripts/inject_wip_rule.sh  |  64 ++
 scripts/test_cmd_channel.sh |  67 ++
 11 files changed, 381 insertions(+), 9 deletions(-)
```

✅ 与 PRD/arch 声明的改动面（constants + inject_wip_rule + cmd_chain/discover 注入 + autopilot 5 处 + devppl_query comments + test_cmd_channel 新断言 + 4 个发现笔记）完全一致，**无合并冲突残留、无无关文件混入**。

### 1.3 零改动确认（回归范围）

`git diff e714aa1 main --stat` 无 `pipeline/state.py` / `notify_check.py` / `cmd_channel.sh` / `chain_check.sh` / `inject_checkpoint_rule.sh` → 相邻模块未被 DPL-030 触碰（与 D1 方案 §1 一致）。

### 1.4 上游链完整性

| 卡 | 状态 | 卡 | 状态 |
|---|---|---|---|
| PRD t_84c53424 | done | QA-D1 t_07b1c297 | done |
| ARCH t_d24d1ad5 | done | QA-EXEC t_863366a3 | done |
| DEV t_ab9a26b3 (S1a) | done | QA-D2 t_cfd940c3 | done |
| DEV t_8458422f (S1b) | done | VA-QA t_74724cf6 | done |
| DEV t_5213b5dd (S2) | done | MERGE t_d0462d23 | done |
| DEV t_7c9d1952 (S3) | done | **本卡 t_9e925eff** | running |

---

## 2. 基线复跑结果（合并后，HEAD @ 86c4ec6）

### 2.1 静态语法

```
$ python3 -m py_compile pipeline/constants.py pipeline/cmd_chain.py pipeline/discover.py
✅ 通过
$ bash -n scripts/test_cmd_channel.sh scripts/test_chain_check.sh scripts/inject_wip_rule.sh scripts/autopilot.sh scripts/devppl_query.sh
✅ 全部 OK
$ git status --short → 空（测试自隔离 $TMPT，零写仓库）
```

### 2.2 基线 386 PASS / 0 FAIL（AC-7，独立复跑）

```bash
cd /workspace/devPPL/.worktrees/t_9e925eff && bash scripts/test_cmd_channel.sh
```

```
════════ 结果汇总 ════════
PASS=386 FAIL=0
ALL TESTS PASSED        （EXIT=0，日志 /tmp/post_cmdchannel.log）
```

- **合并后独立执行**（非转述），耗时 ~76s
- 含 DPL-030 新增断言 13 条（T59h/T60b-d/T63a-i）+ T59e/T60a 末行修正 + DPL-018 校准回归 T64-T69
- 与 QA-EXEC（386/0 @ ef63d3c）、QA-D2（386/0 @ 66a6c87）、VA（386/0 @ 20260814T201000.json）**四方一致** → **合并后无回归**

### 2.3 chain_check 38 PASS / 0 FAIL

```
PASS=38 FAIL=0
ALL TESTS PASSED        （EXIT=0）
```

- 独立复跑确认 **38 断言**（OBS-2 复确认：方案文档 4 处写 41，实测 38，非功能缺陷，文档口径差）
- 与 QA-D2 记录（38/0）一致

### 2.4 相邻模块回归（合并未波及确认）

| 套件 | 结果 | 说明 |
|------|:----:|------|
| `bash scripts/test_workspace_check.sh` | ✅ 40/40 | 工作区合规无回归 |
| `bash scripts/test_idle_check.sh` | ✅ 19/19 | 空闲检查无回归 |

---

## 3. 独立核对结果（POST 阶段，合并后 main）

### 3.1 探针 P1-P6 + 漏报探针 A-F（独立脚本 /tmp/post_probes.py，14/14 PASS）

| # | 探针 | 实测 | 结果 |
|---|------|------|:---:|
| P1 | WIP_SOUL_PARAGRAPH 六节模板 | 六节标题全部在册（上游契约/关键事实/已踩坑/当前进度/下一步/更新记录） | ✅ |
| P2 | 真实 9 profile SOUL 注入现场 | 9/9 profile SOUL.md 含「WIP 检查点节奏与发现笔记」（game-architect..tag-system 各 1 命中，含本次会话自身） | ✅ |
| P3 | inject_wip_rule.sh --dry-run 幂等 | SKIP 9/9，RC=0 | ✅ |
| P4 | devppl_query comments 合法 id | comments t_74724cf6 → RC=0，输出 1698 字符（含 [VERIFIED]） | ✅ |
| P5 | devppl_query comments BAD_ID | bad_id → `BAD_ID: bad_id` + RC=1（白名单生效） | ✅ |
| P6 | autopilot 注入点完整性 | [WIP 节奏] 恰 5 处（L159/343/383/520/665）；L362/L400 qa-d1/qa-d2 ensure 无 comment 参数（arch A-1 成立） | ✅ |
| A | inject_wip_rule.sh --verify | VERIFY-OK/HIT 9/9，RC=0（AC-2 校验模式可用） | ✅ |
| B | WIP_BODY_LINE 内容双要素 | 含「每 10-15 轮 [WIP] checkpoint commit」+「.pipeline/wip/<task_id>.md」 | ✅ |
| C | 4 个发现笔记已 commit 入库 | git ls-tree HEAD .pipeline/wip/ = 4 文件（t_ab9a26b3/t_8458422f/t_5213b5dd/t_7c9d1952） | ✅ |
| D | EST_EFFECTIVE_LINE 含 ×0.7 折算 | 含「迭代预算 × 0.7」+「>30 有效轮必须拆卡」 | ✅ |
| E | _sub_card_body 补洞 CHECKPOINT+WIP | cmd_chain.py L858=CHECKPOINT_BODY_LINE + L859=WIP_BODY_LINE 双行 | ✅ |
| F | 单一源零漂移（9 名单 profile） | 9/9 注入段含模板关键子串（每 10-15 轮/[WIP] checkpoint/.pipeline/wip/发现笔记/更新记录），零漂移 | ✅ |

### 3.2 静态核对 S1-S11（独立脚本 /tmp/post_static_check.py，20/20 PASS）

S1 11 常量 ✅ / S2 EST_SPLIT_THRESHOLD_ROUNDS=20 ✅ / S3 inject 参数+幂等+单一源 ✅ / S4 [WIP 节奏] 恰 5 处 ✅ / S5 cmd_chain 注入点（CHECKPOINT 3 + WIP 3 + EST 2 + 补洞双行）✅ / S6 discover 注入顺序 EST(L249)→CHECKPOINT(L253)→WIP(L254) ✅ / S7 devppl_query comments 白名单+只读 ✅ / S8 13 新断言在册（T59h/T60b-d/T63a-i 全 13 命中）✅ / S9 4 发现笔记六节完整 ✅ / S10 .pipeline 不在 .gitignore ✅ / S11 bash -n 5 脚本 ✅

### 3.3 AC-1..AC-10 交叉核对（与 VA verdict 交叉印证）

| AC | 验收要点 | POST 证据 | 结果 |
|----|---------|---------|:---:|
| AC-1 | constants.py 新增 WIP_SOUL_* / EST_* 常量（单一源） | 静态 S1（11 常量，L238-275） | ✅ |
| AC-2 | inject_wip_rule.sh 幂等注入 9 profile | P2（9/9 FOUND）+ P3（SKIP 9/9）+ A（VERIFY-OK 9/9） | ✅ |
| AC-3 | autopilot.sh 建卡 comment 含 [WIP 节奏] | S4（恰 5 处）+ P6（L362/L400 非注入点） | ✅ |
| AC-4 | dev 卡 / est 卡 body 末含 WIP_BODY_LINE | 基线 T59h + T60c（386 全绿内含） | ✅ |
| AC-5 | dev-est 口径含 ×0.7 折算（双入口） | 基线 T60d + T63a + 探针 D | ✅ |
| AC-6 | devppl_query comments 子命令（白名单+只读） | 基线 T63g-i + P4/P5（合法/非法 id） | ✅ |
| AC-7 | 全量回归 PASS | **386 PASS / 0 FAIL**（本卡合并后独立复跑） | ✅ |
| AC-8 | 结构化 claim（changed_files/tests_run/verification） | VA 报告 claims_pass=15 / claims_fail=0，canonical-claims-array，kanban_comment_written=true | ✅ |
| AC-9 | subsplit 子卡 body 含 WIP+CHECKPOINT 双行 | 基线 T63c/d/e + 探针 E（L858-859） | ✅ |
| AC-10 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变（红线） | S2（L92=20）+ 基线 T63f/T68b | ✅ |

**10/10 PASS，与 VA 报告（15/15 VERIFIED，ac_coverage 全 PASS）一致。**

---

## 4. 新增发现与分级（POST 阶段）

### 4.1 POST-01（MINOR）— DPL-030 文档链未合入 main，constants.py 规范源引用悬空

| 项 | 内容 |
|---|---|
| 现象 | main 上 **7 个 DPL-030 文档全部缺失**：`docs/prd/worker-context-continuity-prd.md`、`docs/arch/arch-worker-context-continuity.md`、`docs/qa/worker-context-continuity-test-plan.md`、`...-test-report.md`、`...-d2-review.md`、`...-va-report.md`、`docs/est/t_c8ad7805-estimate.md`。而 `pipeline/constants.py` L234 注释声明 `# 文档: docs/prd/worker-context-continuity-prd.md（规范源）` → 该引用在 main 上悬空 |
| 证据 | `git ls-tree main docs/prd/`（无该文件）；`git cat-file -e main:docs/prd/worker-context-continuity-prd.md` → not found；各文档仅在分支 wt/t_84c53424 / wt/t_d24d1ad5 / wt/t_07b1c297 / wt/t_863366a3 / wt/t_cfd940c3 上 |
| 对比 | 早前链 `fix-notify-heartbeat-chain-scope` 的 PRD（`docs/prd/fix-notify-heartbeat-chain-scope-prd.md`）已在 main → 存在不一致惯例 |
| 影响 | 下游维护者读 main 代码时点开规范源引用会断裂；文档链只存在于一次性 worktree 分支（有被 GC 风险） |
| 判定公式（标准 §1.2） | 用户可感知 ✅（引用断裂，且各分支回收后文档将丢失）/ 功能阻断 ❌（代码功能全绿）/ workaround ✅（git show 各分支 commit 可读，08 系列 commit 仍在）/ 安全 ❌ / 数据一致性 ❌ → **MINOR** |
| 分级示例对照 | 与标准 §5 MINOR 行（文档/提示类，可感知但不阻断）一致；与 fix-notify QA-POST 先例 QA-D1-03（MINOR，文档未上 main）同构 |
| SLA | MINOR 不触发 SLA 计时（标准 §8 仅 BLOCKER/MAJOR 设 SLA） |
| 处置建议 | 后续 merge 时把 DPL-030 文档链一并合入 main（或至少 PRD+arch）；本卡将 QA-POST 报告合入 main 时顺带补合 |

### 4.2 既有观察维持

| # | 观察 | 状态 |
|---|---|---|
| OBS-1 | D1/D2 时被测代码未合入 main | ✅ **已关闭**（merge t_d0462d23 完成，main 已含全部改动） |
| OBS-2 | chain_check 文档口径 41 vs 实测 38 | 维持（非功能缺陷；建议后续修正方案文档 header/§1/§6.1 的 41 → 38） |

---

## 5. 判定公式 / SLA / 分级示例对照（标准 §6 输出格式要求）

### 5.1 判定公式对照（标准 §1.2）

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| POST-01（文档链未上 main） | ✅ | ❌ | ✅（git show 分支 commit） | 否 | 否 | **MINOR** |
| （无）功能缺陷 | — | — | — | — | — | 0 BLOCKER/MAJOR |

### 5.2 SLA 对照（标准 §8）

- 本卡 **0 BLOCKER / 0 MAJOR** → **无 SLA 触发**。POST-01 为 MINOR，按标准不设 SLA。
- 若后续发现 BLOCKER：4h 响应 + 8h 定位 + 24h 方案（§8 表）。

### 5.3 分级示例对照（标准 §5 表）

- 未发现「注入点漏注某路径」类缺陷（S4/P6 实证 5 处 + L362/L400 非注入点）→ 无 BLOCKER 触发条件。
- 未发现「dev-est 折算口径缺失」类缺陷（T60d/T63a + 探针 D 含 0.7）→ 无 MAJOR 触发条件。
- POST-01 对照示例 15（文档/提示类，低影响）→ **MINOR** 成立；对比 BLOCKER 门槛（无资金/核心数据一致性、无 OOM、无安全漏洞）→ 不满足。

---

## 6. 发布门禁对照（标准 §10）

| 门禁条件 | 数值 | 满足 |
|---------|:---:|:---:|
| BLOCKER = 0 | 0 | ✅ |
| MAJOR ≤ 3 | 0 | ✅ |
| 安全漏洞 = 0 | 0 | ✅ |
| 无未裁定的申诉 | 0 | ✅ |

**发布门禁满足。** POST-01（MINOR）不阻塞发版，但建议在文档层面尽快补合（见 §7）。

---

## 7. 处置建议（QA 只测不改，不代建 FIX 卡）

1. **POST-01（MINOR）处置**：由后续 merge worker / OC 把 DPL-030 文档链合入 main——`docs/prd/worker-context-continuity-prd.md` + `docs/arch/arch-worker-context-continuity.md` + `docs/qa/worker-context-continuity-{test-plan,test-report,d2-review,va-report}.md` + `docs/est/t_c8ad7805-estimate.md`（从分支 wt/t_84c53424 / wt/t_d24d1ad5 / wt/t_07b1c297 / wt/t_863366a3 / wt/t_cfd940c3 / commit 0d2fee9 提取）。本卡完成时若 QA-POST 报告合入 main，可一并处理。
2. **OBS-2（MINOR 级文档口径）**：后续任一文档维护机会把 chain_check 断言数 41 → 38（方案文档 4 处）。
3. **回归门禁**：DPL-030 全量回归基线已固化（386 断言），后续任何改动的合并后回归直接复用 `bash scripts/test_cmd_channel.sh`（386/0）+ `bash scripts/test_chain_check.sh`（38/0）。

---

## 8. 风险登记

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | DPL-030 文档只在一次性 worktree 分支（wt/t_84c53424 等），若分支被 GC 则文档丢失 | 规范源/验收证据链断裂（POST-01 加重） | 尽快补合 main；git reflog 兜底（commit 仍在 object DB） |
| R2 | 后续合入 main 的改动若触碰 constants/cmd_chain/discover 注入逻辑，可能破坏 386 断言 | 回归 | 每次合并后跑 test_cmd_channel.sh（386/0）作为门禁 |
| R3 | 9 profile SOUL 注入是真实环境状态，若新 profile 加入（注释已预留 orchestrator → 追加）需重新注入 | 新 profile 无 WIP 段 | 用 inject_wip_rule.sh --profiles 增量注入 + --verify 校验 |

---

## 附：与本任务相关的既有文档

- PRD：`docs/prd/worker-context-continuity-prd.md`（commit 080c15c，分支 wt/t_84c53424，未上 main）
- 架构：`docs/arch/arch-worker-context-continuity.md`（commit 22de657，分支 wt/t_d24d1ad5，未上 main）
- QA-D1 方案：`docs/qa/worker-context-continuity-test-plan.md`（commit 89b0ca2，分支 wt/t_07b1c297）
- QA-EXEC 报告：`docs/qa/worker-context-continuity-test-report.md`（commit ef63d3c，分支 wt/t_863366a3）
- QA-D2 评审：`docs/qa/worker-context-continuity-d2-review.md`（commit 66a6c87，分支 wt/t_cfd940c3）
- VA 报告：`/root/.hermes/profiles/verifier/.va_reports/20260814T201000.json`（15/15 VERIFIED）
- 分级标准：`docs/standards/qa-finding-classification.md` v1.0
- 本卡独立探针脚本：/tmp/post_static_check.py（S1-S11 20 断言）、/tmp/post_probes.py（P1-P6+A-F 14 断言）、日志 /tmp/post_cmdchannel.log（386/0）
