# 评估报告 — [FIX] MERGE 卡死循环（链卡失败 blocked 缺 block_kind + task_runs 僵尸 + 无限重试）

> 评估人：寇豆码（game-engine） | 日期：2026-08-13 | 评估卡：t_est_22a98abb
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）
> 源卡：t_22a98abb（[FIX] MERGE 卡死循环 — 链卡失败 blocked 缺 block_kind + task_runs 僵尸 + 无限重试）

## 1. 结论（TL;DR）

**不拆，单卡可完成（预计 14-18 轮 ≤ 20 轮阈值）。**

根因已在源卡实锤，且本仓库已有两套可直接复用的成熟模式：
- **blocked 语义**：`pipeline/discover.py` L435-444 / L708-714 已验证的"blocked + block_kind + sticky task_events(kind='blocked')"三件套
  （arch-fix-standalone-dev-subsplit 实测：内核 recompute_ready 对 sticky-blocked 永不 promote，L3345）
- **重试状态机**：`cmd_channel.sh` L105-156 `rollback_retry()`（[CMD] env 类失败回滚 ready + [cmd-retry] 计数 comment + 上限后 blocked），T54 已全覆盖

修复 = 把这两套模式应用到链卡消费段（cmd_channel.sh §5 L550-578）+ 关闭 task_runs 僵尸 + 按失败性质分类（conflict 类直接终态 blocked、env 类回滚重试）。改动集中在 2 个文件（cmd_channel.sh §5 + cmd_chain.py exec_chain_merge 返回分类）+ 1 个测试文件（新增 2-3 组用例 + T16b 断言扩展）。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **2 个代码文件 + 1 个测试文件**：scripts/cmd_channel.sh §5.3（L550-578 失败终态分支）+ pipeline/cmd_chain.py（exec_chain_merge 失败分类）+ scripts/test_cmd_channel.sh（T16b 扩展 + 新用例） | 源卡参考段；grep 确认无其他链卡失败处理入口 |
| 现状基线 | 存量 269 断言全绿；T16b 已测 close 失败→blocked+[cmd-chain] comment（**但未断言 block_kind/sticky**，需扩展）；T15/T15b 已测 merge 成功路径；T54-T55 已测 [CMD] 回滚重试状态机 | 读 test_cmd_channel.sh L530-567 + L1620-1707 |
| ① block_kind + sticky（修复 1） | §5.3 失败分支的 UPDATE 从 `status='blocked'` 扩为 `status='blocked', block_kind=<分类>` + INSERT task_events(kind='blocked')。直接复制 discover.py L435-444 模式（本仓库已验证）。block_kind 分类决策（D1）见 §3 | discover.py L435-444；schema 已确认 tasks.block_kind + task_events 表存在 |
| ② task_runs 关闭（修复 2） | 失败分支追加 `UPDATE task_runs SET ended_at=?, outcome='failed', status='failed' WHERE task_id=? AND status='running'`。schema 已确认列齐全（status/ended_at/outcome）。测试需先插 fake running 行 | sqlite3 .schema task_runs（真实库）；测试复制真实库含此表 |
| ③ 重试状态机（修复 3） | 链卡版 rollback_retry：失败分类（env/conflict/business）→ 可重试类回滚 running→ready（CAS rowcount==1）+ [cmd-retry] N/M comment → 超限 blocked + block_kind + 告警。复用 L105-156 的 comment 计数模式，但 CAS 目标从 archived→ready 改为 running→ready（链卡终态是 done/blocked 而非 archived）。cmd_chain.py exec_chain_merge 返回增加 class 字段（env/conflict/business）供 shell 分类 | L105-156 rollback_retry 全函数 + L550-578 链卡失败分支 |
| ④ 可选：merge 前清理 untracked（修复 4） | exec_chain_merge 合并前 `git status --porcelain` 检测将覆盖的 untracked 文件 → 移到 .pipeline/untracked-backup/（只移动不删除）。**风险：动用户工作区文件，且非验收必需 → 推荐本次不做，另卡评估**（D2 见 §3） | exec_chain_merge L1300-1317；源卡标注"可选" |
| ⑤ 测试 | T16b 扩展（close/merge 失败断言 block_kind + sticky event，防回归）+ 新 T56（merge 冲突场景：setup_gitrepo 后在 main 工作区放同名 untracked 文件 → merge 失败 → blocked+block_kind+sticky；下 tick 仍 blocked 不循环）+ T57（task_runs 僵尸关闭：插 fake running 行 → 失败后 ended_at/outcome 非空）+ T58（重试状态机：env 类失败回滚 ready + [cmd-retry] 计数 → 超限 blocked；成功路径重试后 done）。约 15-25 新断言。冲突场景构造成本低：setup_gitrepo 已建 main + wt/<dev> + wt/t_unrelated | setup_gitrepo L229-249 + insert_dev_chain；T16b L559-567 |
| ⑥ 回归+收尾 | 全量 269+ 断言回归（测试文件 1707 行，单次跑 2-5 min）；commit + [PRODUCES] + 飞书推送。**merge 冲突风险**：cmd_channel.sh/test_cmd_channel.sh 是高频共改文件，S1/S2/S3 每次 merge 都有测试冲突解决先例 | git log bd9c07a/6a811de/af278a8 |

**预计轮数：14-18 轮**（① 1-2 + ② 1 + ③ 4-6 + ④ 0（不做）+ ⑤ 4-6 + ⑥ 2-3）≤ 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| D1 block_kind 分类 | **中（关键决策）** | 链卡失败置 capability 还是 needs_input？推荐 **capability**（git 冲突/untracked 是工作区/环境状态问题，非用户决策问题）；无法定位 dev 卡/分支不存在属业务类→ needs_input 或同样 capability 均可（两者都阻断 recompute promote，验收只要求"blocked 且不再自动恢复"）。discover.py 用 dependency 是子卡场景，链卡失败不适用。不改变轮数上限 |
| D2 冲突类是否重试 | **中（关键决策）** | untracked 覆盖冲突**重试不会自愈**（untracked 文件仍在，除非做修复 4 先清理）。推荐：**env 类**（hermes 不可达/超时）走回滚重试状态机；**conflict 类**一次性 blocked + block_kind + sticky（参照 T54l 业务类"重试必败"语义，避免无意义循环）——与验收"blocked 且不再自动恢复"一致，且不用做修复 4。若产品坚持冲突类也要重试，则必须连带做修复 4（merge 前清理 untracked），轮数 +3-4 |
| R1 recompute_ready 是内核代码 | 中 | Hermes dispatcher 的 recompute_ready 不在本仓库，无法直接改/测。仓库内修复走已验证模式（blocked + block_kind + sticky event，arch 文档实测 L3345 永不 promote）。测试只能断言三件套存在 + 下 tick 不被脚本自身消费，**无法端到端验证 dispatcher 行为**——依赖已文档化的内核语义，风险可控 |
| R2 并发消费竞争 | 中 | cmd_channel cron 与 dispatcher autopilot 可能同时消费同一链卡；回滚 CAS（running→ready rowcount==1）必须与消费 CAS（L502-519 ready→running）同等防护，否则双写计数/状态错乱 |
| R3 测试文件合并冲突 | 中 | S1/S2/S3 每次 merge 都发生测试冲突解决；本任务改 cmd_channel.sh + test_cmd_channel.sh + cmd_chain.py，与在途分支重叠概率高 → merge 阶段预留手动解决时间 |
| R4 测试库 task_runs 残留 | 低 | 测试复制真实 kanban.db 只 DELETE tasks/task_comments/task_links，task_runs 残留真实行（id 不同不干扰）；新 task_runs 测试必须用独立 task id + 测试后置 archived 隔离（参照 T54 隔离模式 L1642-1651） |
| R5 全量回归时长 | 低 | 269+ 断言单次 2-5 min；重试状态机用例需多 tick（类似 T54 3 tick），会加长测试 |

**关键决策点（实现时需拍板，不改变轮数上限）**：
1. **D1**：block_kind = capability（推荐，覆盖 git 冲突/环境/无法定位等所有链卡失败）
2. **D2**：conflict 类不重试（推荐，一次性 blocked 终态）；env 类走回滚重试上限 2-3 次
3. **D3**：修复 4（merge 前清理 untracked）**本次不做**，作为独立评估项（动工作区文件需单独评审）

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | 14-18 轮 ≤ 20 轮阈值 → **不拆** |
| 模块依赖 | 改动集中在同一消费段（cmd_channel.sh §5）+ 1 个 python 函数返回分类 + 1 个测试文件，三处强耦合（改 §5.3 必然连带 cmd_chain.py 分类 + 测试） |
| 并行收益 | 无——拆卡会把"失败终态语义"拆成多卡，每张都改同一段代码，冲突面反而更大 |
| 兜底 | 即使超预算，验收只要求 1-3（block_kind + task_runs 关闭 + 重试上限），修复 4 已排除 → 核心交付物原子可提交，无半成品风险 |

**决策：不拆（[SUB-SPLIT] 1），单卡直接完成。** 与同系列 t_f6047701（9-13 轮，单函数 + 3 组测试）量级相当；本卡略大因涉及 3 个修复点 + 状态机。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
1. [DEV-DEV] MERGE 卡死循环修复（game-engine，单卡）：
   a. cmd_channel.sh §5.3 链卡失败终态：blocked + block_kind=capability + sticky task_events(kind='blocked')
      （复制 discover.py L435-444 模式，阻断 recompute_ready 自动 promote 循环）
   b. 失败时关闭 task_runs 僵尸：UPDATE task_runs SET ended_at/outcome='failed' WHERE task_id=? AND status='running'
   c. 链卡重试状态机：env 类失败（hermes 不可达/超时）→ 回滚 running→ready（CAS）+ [cmd-retry] N/2 comment；
      超限或 conflict/business 类 → 一次性 blocked + block_kind + 告警 comment（参照 rollback_retry L105-156 + T54 模式）
   d. cmd_chain.py exec_chain_merge 失败返回增加 class 字段（env/conflict/business）供 shell 分类
   e. 测试：T16b 断言扩展（block_kind + sticky）+ 新 T56（merge 冲突→blocked+不循环）/T57（task_runs 关闭）
      /T58（重试状态机成功+超限路径）+ 全量 269 断言回归
   明确不做：修复 4（merge 前清理 untracked，另卡评估）
   预计 14-18 轮。依赖：无（独立修复卡，源卡 t_22a98abb 已含完整方案）
```

- SPLIT: no（count=1，单卡可完成）
- MODE: single
- ROUNDS_EST: 16
- FILES: scripts/cmd_channel.sh, pipeline/cmd_chain.py, scripts/test_cmd_channel.sh
- STATUS: not_started（源卡 t_22a98abb 待 dev 实现）
- TESTS: 存量 269 断言 PASS 基线；新增 T56-T58 共 3 组 + T16b 断言扩展
- RISK: D1 block_kind 分类（capability）；D2 冲突类不重试（否则需连带修复 4 +3-4 轮）；R3 测试文件 merge 冲突；R4 task_runs 测试隔离
- ACTION: build_one_dev_card（assignee=game-engine）

## 6. 备注

- 根因已实锤（源卡提供完整因果链 1-5），实现无需再定位；唯一需实现时确认的是 recompute_ready 对 sticky-blocked 的语义（arch-fix-standalone-dev-subsplit 已实测文档化，L3345 永不 promote）。
- 与最近 PATH 修复 S3（bd9c07a）同文件不同段（S3 改 §2 [CMD] 段 + rollback_retry；本卡改 §5 链卡段），rollback_retry 可整体复用其模式，无冲突。
- T16b 现有断言（close 失败 → blocked + [cmd-chain] comment）在本修复后仍成立，但需补 block_kind/sticky 断言防回归——这是现有测试漏掉的验收点。
- 本评估卡不写代码；autopilot 读取 [SUB-SPLIT] comment 后建 1 张 [DEV-DEV] 卡执行。
