# 评估报告 — [FIX] oc_wake_check 源 E 跨仓库误报 — mem-core 产物卡 code-not-in-main 假阳性（DPL-069）

> 评估人：寇豆码（game-engine） | 日期：2026-08-19 | 评估卡：t_est_1db58772 | 源卡：t_1db58772
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：t_9a3c1371 实测误报（OC 核对结论 comment 1711）→ **本评估** → FIX 卡 t_1db58772 执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（26-33→60、18-29→60、20-31→60、24-30→60、18-24→60）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 17-27 / 15-20 轮，全部落在 42 有效轮预算内）。**

任务本质：oc_wake_check.sh 源 E（落地质检）的**跨仓库支持改造**。现状固定
repo_root=/workspace/devPPL 核对所有 done 卡产物（`git -C repo_root cat-file -e main:<path>`），
mem-core 产物卡（MEM-009 SUB-1/2 走 worker 直推 mem-core main、无 devPPL MERGE 卡）必然误报。

**评估期间实测关键发现（决定方案走向，非假设）：**
- **t_9a3c1371 的 workspace_path = `/workspace/devPPL/.worktrees/t_9a3c1371`（devPPL worktree），
  但产物真实落在 mem-core main**（merge 879b94c）。→ 源卡建议①「按任务 workspace_path 推断仓库」
  **对本次实证直接失效**，不能作为主方案。
- 可靠仓库信号是 **claim 结构化数据**：`metadata.claims[].target` 为绝对路径
  （`/workspace/mem-core/tests/test_sources_conversation.py`、`/workspace/mem-core/tests/conftest.py`），
  claim 文本含「mem-core main @ 879b94c / merge --no-ff 进 mem-core main」。
  而 `changed_files` 是**相对路径**（tests/conftest.py）——恰是误报的直接来源
  （相对路径按 devPPL main 核对 → 不存在 → 报）。
- 源 E 目前**只读 changed_files，不读 metadata.claims[].target** → 结构化 claim 时代的仓库信号被浪费，
  修复必须补上这条解析路径（源卡建议②的落地形态）。
- 跨仓掩盖风险实证：mem-core 与 devPPL main **都有 tests/conftest.py**（同路径存在）
  → 「任意兄弟仓存在即 pass」的朴素扫描会**掩盖 devPPL 真漏**（验收 2 红线），
  必须按卡解析目标仓库、而非全局放水。
- 现有测试覆盖：`test_wip_progress_check.sh` T9-T14 已覆盖源 E 单仓全场景
  （正/反例、路径变体、DEV-MERGE、窗口、幂等 seen），`test_watchdog_unify.sh` T1-T9 只覆盖 I/J/K 不含 E。
  → 新测试加在 test_wip_progress_check.sh（复用 load_done/run_oc_wake/commit_file fixture），
  test_watchdog_unify.sh 作为回归。
- oc_wake_check.sh 是 **cron 前置脚本 + must-sync 清单（D-A: jobs.json 直调）** → 部署验证规则适用
  （DPL-048：repo↔live md5 一致才 PASS；部署动作留 OC，研发只交 repo 正本）。

## 2. 工作量评估（读码结论，非假设）

改动面：**2 文件**（scripts/oc_wake_check.sh 改 ~40-70 行 python heredoc + 头注释源 E 语义；
scripts/test_wip_progress_check.sh 增 ~100-140 行新用例组）。
回归面：test_wip_progress_check.sh 全组（T1-T18）+ test_watchdog_unify.sh（T1-T9）+ bash -n ×2。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① SUB-1 机制（oc_wake_check.sh 源 E） | 读码复盘（t_9a3c1371 数据形态 + E 逻辑 + claims schema）**2-3 轮**；方案裁决（workspace_path 失效 → claims-target/known-repos 主方案 + 掩盖风险对策）**1-2 轮**；实现：repo 候选发现（env OC_WAKE_EXTRA_REPOS / 自动发现 /workspace/*/.git，fail-open）+ `_git_ok` 参数化 repo + 按卡 repo 解析（claims[].target 前缀匹配 → 该仓 main 核对）+ `_norm_landing_path` 支持任意已知仓前缀剥除 + E2 merge 卡同仓化 + seen 键含 repo 标识（或验证逻辑本身）**3-4 轮**；bash -n + 手工冒烟（临时双仓 fixture 复刻 t_9a3c1371）**1-1.5 轮** → **基准 7-11** | 源 E 全代码实读（L184-327）；t_9a3c1371 claim 双格式实读（changed_files 相对 + claims[].target 绝对）；claims schema 见 t_9a3c1371 run metadata（claims[].target 字段） | 
| ② SUB-2 测试+回归（test_wip_progress_check.sh） | 双 repo fixture 基建（复用 load_done/run_oc_wake/commit_file + 新增兄弟仓 make_repo_main）**0.5-1 轮**；T19 跨仓正例（复刻 t_9a3c1371：changed_files 相对路径 + claims target 指 mem-core → 不报）**1-1.5 轮**；T20 跨仓反例（产物 A/B 仓 main 均无 → 仍报 code-not-in-main）**1 轮**；T21 devPPL 真漏回归（验收 2：devPPL 产物缺失且兄弟仓有同路径 → 必须仍报，防掩盖）**1 轮**；T22 claims-target 绝对路径变体 + fail-open（兄弟仓缺失/非 git → 回退 repo_root 不崩）**1 轮**；T23 seen 幂等（旧键兼容 + 换 key 重报语义）**0.5-1 轮**；全量回归（test_wip_progress_check 全组 + test_watchdog_unify T1-T9 + bash -n）**2-3 轮** → **基准 6-8** | T9-T14 fixture 模式现成（load_done/run_oc_wake 直接复用）；test_watchdog_unify 双仓无关（只回归）；用例膨胀按 +40% 备（MEM-007 12→17 实证同款） |

**基准轮数（未校准，合计）：13-19 轮（中位 ~16）。**
**DPL-018 校准：13-19 × K=2.45 → 校准后 32-47 轮**（单卡 76-112% 预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | **workspace_path 推断仓库失效（实证）** | 高 | t_9a3c1371 workspace 是 devPPL worktree 但产物在 mem-core → 按卡 workspace_path 会重新引入误报。缓解：主方案走 claims[].target 绝对路径 + claim 文本仓库名 + known-repos 清单；workspace_path 只作兜底且测试必须复刻 t_9a3c1371 数据形态证明兜底不主用 |
| R2 | 跨仓扫描掩盖真漏（验收 2 红线） | 高 | mem-core/devPPL 均有 tests/conftest.py → 「任意仓存在即 pass」会掩盖 devPPL 真漏。缓解：按卡解析**目标仓库**（claims/known-repos），缺失在目标仓才报；T21 显式测「兄弟仓有同路径但本仓无 → 仍报」 |
| R3 | seen 键兼容（验收 1 的幂等语义） | 中 | 旧键 `landing:t_9a3c1371:<mk>` 已落盘 /tmp/oc_wake_seen。修复后验证逻辑本身通过（产物在 mem-core main 存在 → 不再产生异常行），旧键无害；若换 key 需含 repo 标识并测重报语义（T23）。验收允许「换 key 或验证逻辑本身」二选一 |
| R4 | 生产 watchdog 脚本改动（cron 直调 + must-sync） | 中 | 改动直接影响每 tick 唤醒输出。缓解：全量回归（两套 shell 套件 + bash -n）+ 部署验证规则（repo↔live md5，部署留 OC；merge 后 deploy-drift 源 G 报自身漂移为预期 R2 自引用悖论，OC 部署平息） |
| R5 | 兄弟仓发现机制 fail-open | 中低 | env 覆盖 + 自动发现 /workspace/*/.git；任一仓不可达 → 跳过该仓不崩（T22）；发现清单变化不改写 seen 键语义 |
| R6 | 用例膨胀 | 已计入 | 新用例组按 +40% 备（MEM-007 12→17 实证）；T19-T23 合计 18-22 断言 |
| R7 | E2 merge 卡跨仓 | 低 | [DEV-MERGE] 卡 sha 核对同 repo 化（E2 用同 repo 解析 helper）；当前 mem-core 无 MERGE 卡（直推模式），只做参数化不新增语义 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 13-19 轮（中位 ~16） |
| DPL-018 校准后 | 32-47 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个（机制改造 / 测试+回归）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 13-19 → 校准 32-47 = 单卡 76-112% 预算 ❌ 且最近 5 卡 timed_out 前科（估 18-33 全部撞 60 上限）→ 单卡不可行 |
| 本评估 2 卡方案 | SUB-1 基准 7-11 → 校准 17-27（27/42 = 64%）；SUB-2 基准 6-8 → 校准 15-20（20/42 = 48%）✅ |
| 依赖方向 | SUB-2 断言 SUB-1 的行为（跨仓正/反例/fail-open）→ 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——同文件（oc_wake_check.sh / test_wip_progress_check.sh）强耦合，串行最稳；SUB-2 若并行需等 SUB-1 merge，无净收益 |
| 兜底 | SUB-1 若超预算：seen 键策略/claims 解析为独立可切块（contingency SUB-1b），不改变 SUB-2 结构；SUB-2 若超预算：T21（真漏回归）优先级最高，其余断言可精简 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_12539484（DPL-061，拆 3 serial 同脚本族）、t_2717e1ae（DPL-063，1 行修复不拆，
但本任务 30-70 行 python + 新用例组 + 部署验证，粒度不同）。对比 MEM-009（350 行 adapter + 4 卡）
本任务小一个量级，2 卡粒度与「机制/测试」天然分段对齐。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] oc_wake_check 源 E 跨仓库 repo 解析机制 — scripts/oc_wake_check.sh 源 E（L184-327）：
   repo 候选发现（repo_root + env OC_WAKE_EXTRA_REPOS + 自动发现 /workspace/*/.git，fail-open）；
   按卡目标仓库解析（metadata.claims[].target 绝对路径前缀匹配已知仓 → 该仓 main 核对；
   claim 文本「<repo> main @ sha」兜底；workspace_path 仅作最后兜底——实证 t_9a3c1371 是
   devPPL worktree 产物在 mem-core，workspace_path 不可主用）；
   _git_ok 参数化 repo；_norm_landing_path 支持任意已知仓前缀剥除；
   E2 [DEV-MERGE] sha 祖先核对同 repo 化；seen 键含 repo 标识（或验证逻辑本身，验收 1 二选一）；
   头注释源 E 语义更新；bash -n + 手工冒烟（临时双仓 fixture 复刻 t_9a3c1371 数据形态：
   changed_files 相对路径 + claims target 指兄弟仓 → 不误报）。
   预计 17-27 轮
2. [DEV-SUB-2] oc_wake 源 E 跨仓测试 + 全量回归 — scripts/test_wip_progress_check.sh 新增 T19-T23
   （复用 load_done/run_oc_wake/commit_file + 兄弟仓 fixture）：
   T19 跨仓正例（复刻 t_9a3c1371 → 不报 code-not-in-main）；
   T20 跨仓反例（A/B 仓 main 均无 → 仍报）；
   T21 devPPL 真漏回归（验收 2：本仓缺失且兄弟仓有同路径 → 必须仍报，防掩盖）；
   T22 claims-target 绝对路径变体 + fail-open（兄弟仓缺失/非 git → 回退不崩）；
   T23 seen 幂等（旧键兼容/换 key 重报语义）；
   + 全量回归（test_wip_progress_check 全组 T1-T18 不破 + test_watchdog_unify T1-T9 + bash -n ×2）。
   预计 15-20 轮
```

- SPLIT: yes（count=2，校准后 32-47 轮远超 20 阈值；单卡 76-112% 预算不可行）
- MODE: serial（SUB-2 断言 SUB-1 行为，需 SUB-1 合并进 main）
- ROUNDS_EST（校准后）: 32-47（基准 13-19 × K=2.45；分卡后每张 17-27 / 15-20）
- FILES: scripts/oc_wake_check.sh（改）+ scripts/test_wip_progress_check.sh（增）——2 文件
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_1db58772）
- TESTS: SUB-1 冒烟 3-4 断言；SUB-2 T19-T23 约 18-22 断言 + 两套全量回归
- RISK: R1 workspace_path 失效（claims-target 主方案）；R2 跨仓掩盖真漏（T21 显式测）；
  R3 seen 键兼容；R4 部署验证（must-sync，部署留 OC）；R5 兄弟仓 fail-open
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_1db58772]，serial）

## 6. 备注

1. **部署验证规则**（DPL-048）：oc_wake_check.sh 是 cron 前置脚本（jobs.json 直调）→ 验收标准必须含
   「diff/md5 比对 repo 版 vs /root/.hermes/profiles/orchestrator/scripts/ 同名文件 → 一致才 PASS」。
   研发只交 repo 正本；merge 后 deploy-drift 源 G 报自身漂移为预期（R2 自引用悖论），OC 部署平息。
2. 验收 1 的 seen 键处置：推荐「验证逻辑本身」——修复后 t_9a3c1371 产物在 mem-core main 存在，
   不再产生异常行，旧键 `landing:t_9a3c1371:<mk>` 无害残留；如需显式换 key 则含 repo 标识并在 T23 测重报。
3. 修复方案优先级（供 SUB-1 裁决）：claims[].target 绝对路径 > claim 文本仓库名 > known-repos 清单
   > workspace_path 兜底；禁止「任意兄弟仓存在即 pass」的全局放水（R2 掩盖）。
4. QA 卡（跨仓全量验证）由 OC 按 QA 流程另建，不在本 [SUB-SPLIT] 内。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张 [DEV-SUB] 卡执行。
