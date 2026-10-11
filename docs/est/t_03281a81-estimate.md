# 评估报告 — [FIX] MERGE 型卡收尾脚本化 finalize_merge.sh — 验证+标记+推送一条命令（DPL-136 链微改）

> 评估人：寇豆码（game-engine） | 日期：2026-09-06 | 评估卡：t_est_03281a81
> 源卡：t_03281a81（执行模式: cc-glm，Frank 2026-09-06 批准七号卡）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径）

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1），单卡可完成，预计 14-24 轮（中位 19）≤ 20 轮阈值附近，取"不拆 + 明确降险路径"。**

理由：
1. **单文件交付为主**：finalize_merge.sh 是一个独立 bash 脚本（预计 300-450 行），与既有 finalize.sh 同型可大量参照（finalize.sh 289 行成熟先例 + send_claim_feishu.py + hermes 打桩模式）。
2. **依赖面已全部落位**：回归三套件（scripts/test_notify_check.py / test_cc_glm.sh / test_cmd_channel.sh）已存在；推送路由所需 hermes_backup_push.sh（/workspace/）与 manifest 写入逻辑（pipeline/cmd_chain.py:2231 .pipeline/manifest.jsonl）均已在线；判重探测 _branch_tip_in_main（merge-base --is-ancestor）DPL-136 补卡 t_00b8b257 已实现，可直接复用同款探测式。
3. **测试为隔离 fixture 板 3 用例**（正常收尾 / 分支未合 / 推送失败如实报），全部走 PATH 前置打桩 + 临时 git 仓，无外部网络依赖，参照 test_cc_glm.sh B 系列同款成熟模式，编写成本低。
4. **dry-run 回放验收**（t_b7da41b0 已 done，全分支已 IN-MAIN）是只读验证，1-2 轮。

## 2. 工作量评估（读码结论）

### 2.1 现状基线（评估期间实测）

| 检查项 | 实测结果 |
|--------|---------|
| finalize.sh 先例 | scripts/finalize.sh 289 行，五步 fail-fast + 幂等闸门 + 打桩注入口模式可直接套用 |
| 回归三套件 | scripts/test_notify_check.py、test_cc_glm.sh、test_cmd_channel.sh 均已存在（constants.py:344 亦引用为回归口径）|
| 推送脚本 | /workspace/hermes_backup_push.sh 在线（close.sh:20、test_backup_push_incr.sh 引用同一路径）|
| manifest 三件套 | pipeline/cmd_chain.py:2231 .pipeline/manifest.jsonl 追加逻辑既有 |
| 祖先探测 | merge-base --is-ancestor 判重式已在 t_00b8b257（_branch_tip_in_main，ref 悬空 fail-open）落 main |
| MERGE 卡 body 分支清单格式 | t_d817a069/t_2a3542d8 等标题「wt/<id>(<sha>) 并入 main」格式实证，body「来源链编号」可解析 |

### 2.2 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 脚本骨架 | finalize_merge.sh：参数解析 + 卡 body 解析（待合并分支清单 + 来源链编号）+ 幂等闸门（已 IN-MAIN / 已清理跳过）| 3-5 |
| ② | 验证+回归 | 逐分支 --is-ancestor 探测 + 三套件回归跑 + 结果摘要 | 2-3 |
| ③ | 清理+标记 | 通过分支 worktree/分支删除（不过则保留入 comment）+ 结构化收尾 comment + kanban complete | 2-3 |
| ④ | 推送路由 | 项目类型路由（系统机制类 → manifest 三件套 + hermes_backup_push.sh；纯产品类 → repo remote；混合双路；配置驱动不硬编码）；推送失败如实 FAIL | 3-4 |
| ⑤ | 测试 | fixture 板 3 用例（打桩 git 仓 + PATH 前置），含幂等重跑断言 | 3-4 |
| ⑥ | 验收+收尾 | dry-run 回放 t_b7da41b0 + DEV-MERGE 落 main + finalize.sh 收尾链 | 2-3 |

**预计总轮数（基准）：14-24 轮（中位 19）。**

### 2.3 风险点

| 风险 | 缓解 |
|------|------|
| 推送路由"项目类型"解析口径（来源链编号 → 类型映射）无现成配置表 | 从卡 body「来源链: DPL-xxx」判定系统机制类；映射表放脚本顶部配置区或 constants.py，不硬编码散落；产物中显式声明口径留 Frank 裁定入口 |
| kanban complete 步骤在测试环境需打桩 | 沿用 test_cc_glm.sh 的 hermes PATH 前置打桩成熟模式 |
| 三套件回归耗时（test_notify_check 46-73s/遍，cc_glm 全量 10-15min）| 脚本内回归支持 --skip-regression 开关 + 后台执行轮询（DPL-136 超时纪律）|
| 幂等重入（complete 已发生后再跑）| complete 步骤前置检测卡状态，已 done = 全链 SKIP |

## 3. 拆分决策

**[SUB-SPLIT] 1（不拆）。** 预估中位 19 轮 ≤ 20 轮阈值；交付物单脚本 + 单测试文件，串行依赖强（骨架→路由→测试），拆卡只会增加收尾链固定预算（+8 轮）反而超支。DEV-MERGE 落 main 卡由 autopilot 自动生成，不计入本卡。

> 若实际推进中 ①-④ 超出 15 轮（如路由口径需多轮讨论），降险路径：先交付「验证+回归+标记+清理+幂等」核心链落 main，推送路由留 [SUB-SPLIT] 2 子卡补齐——按建卡铁律由执行 run 自行裁决，本评估预授权该拆分。
