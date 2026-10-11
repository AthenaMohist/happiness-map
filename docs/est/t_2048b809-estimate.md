# 评估报告 — [DEV-EST] GLM 额度耗尽自动停机 + 备用模型强制收尾存档（DPL-099）

> 评估人：寇豆码（game-engine） | 日期：2026-08-30 | 评估卡：t_2048b809 | 源链：DPL-099（CMD → PRD t_5cdb27d5 → arch t_5d84df3a → 本卡）
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 上游交付：PRD v1.0（af1a79d，OC 审通过）+ 架构 v1.0（0c869ae @ mem-core main，628 行，D1-D8 继承 + D9-D17 新增裁决）
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.40 → K=2.40（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 全撞 60 上限）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 29-38 / 26-34 轮，全部落在 42 有效轮预算内）。**

任务本质：把架构 v1.0 的 R1-R6 落成**单文件四段函数脚本 + 测试 + 接线**——
`glm_quota_probe.sh`（probe 四态分类 / shutdown 熔断序列 / finalize-mech 机械收尾 /
recover 分级复位）+ `test_glm_quota_probe.sh`（T1-T16 断言矩阵）+ oc_wake_check 源 L
+ deploy_drift 清单 +1。架构已把全部设计点定稿（19 条实测事实 + 9 条新裁决 +
测试矩阵逐条给出 + §6.2 源 L 代码块原文），dev 侧是「按图施工 + 验证」，无设计决策。

**评估期间实测确认（非假设）：**
- 架构引用的行号/事实抽查全部对上：oc_wake_check.sh 741 行（源 F L433-455、
  conn.close L690、跳过名单 L705-710、输出段 L717-741）；deploy_drift_check.sh
  L40 DEFAULT_SYNC_LIST 恰 4 脚本；idle_check.sh L125-147 双调度源 pause 先例存在。
- 本链是 [CMD] 类型化链（PRD→ARCH→EST），[SUB-SPLIT] comment 写本卡即可：
  cmd_chain.py L1539-1540 在本卡 done 后建 dev 棒时读取（`_read_sub_split(conn,
  prev["id"], "SUB-SPLIT")`），N>1 建 [DEV-SUB-*] 子卡替代单 dev 卡。
- SUB_ITEM_RE 只认行首 `数字.` / `数字、` / `- ` / `* ` 格式（cmd_chain.py L779），
  轮数从行尾「预计 X-Y 轮」提取（L781-782）——[SUB-SPLIT] 行格式已按此写。
- 测试范式有成熟同型先例：test_watchdog_unify.sh（261 行，env 桥 + seed_card +
  assert_contains + seen 键断言）——test_glm_quota_probe 的结构模板。
- DPL-048 部署验证规则**适用于 S2 接线产物**（oc_wake_check.sh 在 must-sync 清单，
  repo↔profile 一致才 PASS）；glm_quota_probe.sh 新入清单后同样适用。
- 架构 §10.1 建议 S1（game-engine 脚本+源L+测试）/ S2（OC 部署+线上验证）——本评估
  认同 S1/S2 边界（S2 是 OC 执行），但 **S1 内部需再拆 2 卡**（见 §4）。

## 2. 工作量评估（读码结论，非假设）

改动面（架构 §12 文件清单）：devPPL 仓新增 2 + 修改 3；OC 侧 2 项（不在本拆卡范围）。

| | 子卡 | 工作项 | 基准轮数（未校准） | 依据 |
|---|------|--------|:---:|------|
| ① | SUB-1 探针主体 | 领卡 orient + 读 PRD/架构全文（628 行）+ 交接 | 2-3 | 上游文档实读量；架构 §0-§7 是实现唯一依据 |
| | | glm_quota_probe.sh 四段函数：probe 四态分类器（§2.2 含 RESET_AT 正则）+ 状态机含抖动防（§2.3）+ --inject 注入接口（§2.4）+ shutdown 五步序列（§3.1 含双调度源 pause 照抄 idle_check L125-147 + CLI 降级直写 jobs.json D9）+ D15 活跃卡口径三 SQL 并集（§3.2）+ KEY_INVALID/TRANSIENT 边界（§3b 限频）+ finalize-mech N+2 git 工作区遍历（§4.2）+ recover 时间闸门/分级/归属对账（§5）+ R5 派发（§7.1 D17 命令） | 7-9 | 全部设计已定稿（伪代码/SQL/裁决逐条给出），纯 bash 翻译；但状态机分支多（四态×计数×熔断×恢复 4 个正交轴）+ 全链路幂等/fail-open 硬要求，细节密度高 |
| | | 冒烟自测（--inject 四态各一轮 + bash -n + 真实 probe 一次走 OK 路径） | 1.5-2 | SUB-1 不带全量测试但必须冒烟过手（不交未测代码，SOUL 责任闭环） |
| | | claim（changed_files + JSON claims）+ 飞书 + complete | 1.5-2 | 标准闭环 |
| | | **小计** | **12-16** | |
| ② | SUB-2 测试+接线 | 领卡 orient + 读架构 §8 + 测试桥搭建（§8.1 env 打桩 6 点 + fixture DB/REPO/JOBS） | 2-3 | 桥设计架构已给出；fixture DB 复制真实 schema 模式有 test_watchdog_unify 先例 |
| | | T1a-T1e 探针四态断言 | 1-1.5 | 断言矩阵 §8.2 逐条定稿 |
| | | T2a-T2c 熔断（连续 2 次/抖动防/KEY_INVALID 负例）+ 修破缓冲 | 3-4.5 | fixture 最复杂段（jobs.json state + crontab 打桩 + task_control 三表并集 + 标记文件 + SENTINEL 记录五维断言）；历史偏差主源，缓冲从宽 |
| | | T3a-T3c + T4a-T4d 收尾/恢复断言 | 2-3 | fixture git repo + 归属对账负例 |
| | | T6a-T6c 源 L 断言（标记存在/负例/seen 跳过名单） | 1.5-2 | 源 L 代码块架构 §6.2 已给出；oc_wake_check 回归（test_watchdog_unify 不动 K） |
| | | deploy_drift DEFAULT_SYNC_LIST +1 + test_deploy_drift 期望同步 | 0.5-1 | 一行 + 测试期望 |
| | | 既有回归：test_idle_check + test_deploy_drift + test_watchdog_unify + test_cmd_channel | 1.5-2 | 四套件跑通核对（探针/源 L 均只增不删，预期零回归但必须实证） |
| | | claim + 飞书 + complete | 1.5-2 | 标准闭环 |
| | | **小计** | **13.5-19** | |

**基准轮数（未校准，合计）：25.5-35 轮（中位 ~30）。**
**DPL-018 校准：25.5-35 × K=2.40 → 校准后 61-84 轮** —— 超单会话 42 有效轮 → **必须拆卡**
（基准本身 >20 轮阈值 → 同样触发拆卡红线）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | **探针状态机分支组合漏测**（四态×计数×熔断×恢复正交） | 高 | T1-T16 覆盖主路径，但 inject 驱动下边界组合（如熔断瞬间 OK / 恢复闸门边界）易漏。缓解：SUB-2 断言矩阵逐条对照 §8.2 实现清单核对；测试不通过的边界回填用例 |
| R2 | **直写 jobs.json 降级路径（D9）与内核写竞争** | 中 | 架构已裁定降级仅在 CLI 不可用时走 + 前后记日志。缓解：SUB-2 用 AUTOPILOT_JOBS_JSON 指向 fixture 隔离测试；真实环境降级路径由 S2（OC）线上验证 |
| R3 | oc_wake_check 输出段改造破坏既有源 F 行为 | 中 | 输出段 L717-741 是 NO_ANOMALY/autopilot_tail 敏感区（DPL-030 静默教训原址）。缓解：glm_tail 严格仿 autopilot_tail 模式（架构 §6.2 已给代码）；test_watchdog_unify 全量回归 + 新增 T6 断言 |
| R4 | must-sync 清单 +1 后部署漂移误报 | 低 | deploy_drift_check 检测 repo↔profile 一致性，S1 只改 repo → 漂移检测会报「glm_quota_probe.sh 缺 profile 副本」——这是**预期行为**（提示 OC 部署），非缺陷。SUB-2 报告注明 |
| R5 | 测试 fixture 复杂度超预期（三 DB + git repo + crontab 打桩） | 中 | test_watchdog_unify 先例只有单 DB；本测试桥多 AUTOPILOT_JOBS_JSON + CRONTAB_CMD 两个桩。缓解：§8.1 桥设计已给出；T2 段缓冲已从宽（3-4.5） |
| R6 | bash 长脚本可维护性（四段全单文件） | 低 | 架构 D10/D13 已裁定单文件 + 日志留档；函数分段 + set -uo pipefail + 幂等注释 |
| R7 | claim 格式（DPL-060） | 低 | 两卡均带 changed_files 段 + JSON claims |
| R8 | worktree 规范 | 低 | 两卡均 workspace_kind=worktree，改动落 wt/<task-id> 分支 |
| R9 | **est 产物自身不在 main → code-not-in-main 续报** | 中 | 先例 t_d683fdef/t_est_15e790bc 均踩过。缓解：子卡 claim 的 changed_files 必须含 docs/est/t_2048b809-estimate.md 的落地（本报告随 SUB-1 或 SUB-2 的 merge 一并落 main） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 25.5-35 轮（中位 ~30） |
| DPL-018 校准后 | 61-84 轮（×K=2.40）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 引擎脚本 / 测试矩阵 / 接线（源 L + drift）三类 ≥ 2 → 拆合理；架构 §10.1 S1/S2 边界认同（S2 OC 执行），S1 内部按「实现/验证」二分 |
| 单卡方案复算 | 单卡 61-84 校准轮 = 145-200% 预算 → 不可能（最近 5 卡同量级全 timed_out） |
| 3 卡方案复算 | 探针按 probe+shutdown / finalize+recover 拆 → 每段 15-19 校准轮，但两段共享状态机与状态文件，拆开 = 双倍上下文重建 + 接口对齐成本 > 收益 → 不选 |
| **本评估 2 卡方案** | SUB-1 基准 12-16 → 校准 29-38（69-91% 预算，偏高但实现是纯翻译可控）；SUB-2 基准 13.5-19 → 校准 32-46（76-109%……重新平衡：测试矩阵 T3/T4 段移入 SUB-1 不可行（依赖测试桥），SUB-2 内部再压缩：T3a-T3c 与 T4a-T4d 共享 fixture 串联跑，缓冲收窄 → 12.5-17 基准 → 校准 30-41（71-98%）✅ 两卡均贴上限但无超 100% |
| 依赖方向 | SUB-2 测试对象是 SUB-1 产物 → **serial**（SUB-1 done + merge 后 SUB-2 才能跑全量） |
| 并行收益 | 无——测试依赖实现产物 |
| 兜底 | SUB-1 若超预算：四段函数按 probe→shutdown→finalize→recover 顺序交付，WIP checkpoint 每 10-15 轮（DPL-030），未完成段在 [CHECKPOINT] 注明；SUB-2 若超预算：T 矩阵按 T2（熔断核心）→T4（恢复）→T1（四态）→T6（源 L）优先级裁剪，T3 可降级为冒烟 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_96fab6aa（MEM-009，4 serial 13-18/22-32/12-20/10-16）、t_d683fdef
（DPL-098，2 serial 22-34/22-34）——本任务改动面（2 新增 + 3 修改，设计全定稿）
介于两者之间，2 卡粒度与「实现/验证+接线」天然分段对齐。架构 §10.1 的 S2
（OC 执行：cron 注册 + 部署 + 线上验证 + R7 提交 Frank）不在本 [SUB-SPLIT] 内，
由 OC 在 SUB-2 完成后自行建卡。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] DPL-099 探针脚本主体 glm_quota_probe.sh（四段函数 + 状态机 + --inject）:
   按架构 v1.0 §2-§7 逐段实现（arch: wiki/projects/devppl/arch/arch-dpl099-glm-quota-shutdown-fallback.md）:
   probe 四态分类器（OK/QUOTA_EXHAUSTED 含 1308+RESET_AT 正则/KEY_INVALID/TRANSIENT，fail-open）
   + 状态机抖动防（连续 2 次熔断 / TRANSIENT 6 次告警 / KEY_INVALID 24h 限频不计数）
   + shutdown 序列（pause autopilot 双调度源照抄 idle_check L125-147 + CLI 降级直写 jobs.json D9
   + .glm_shutdown 原子写 D10 + D15 活跃卡口径三 SQL 并集写 task_control + sentinel 双通道）
   + finalize-mech（N+2 git 工作区 [WIP] glm-shutdown commit/push + 备份触发 + 清单回写 D16）
   + recover（时间闸门防提前复活 + 窗口型自动复位三件套/无窗口型只通知 + D7 归属对账只清自己的）
   + R5 agnes 一次性会话派发（D17 命令，失败重试上限 3）
   + 探针日志 logs/glm_probe.log 追加式（D13）+ 探针自身绝不 pause 自己（设计原则 7）;
   自测：bash -n + --inject 四态各一轮（OK/QUOTA_EXHAUSTED 带 reset-at/KEY_INVALID/TRANSIENT）
   + 真实 probe 一次走 200 OK 路径（不打真 429）;
   claim 带 changed_files（scripts/glm_quota_probe.sh 新增 + .pipeline/wip 笔记）。
   预计 29-38 轮
2. [DEV-SUB-2] DPL-099 测试矩阵 T1-T16 + 源 L 接线 + must-sync + 回归:
   测试桥按架构 §8.1（env 打桩 6 点: HERMES_CMD/CRONTAB_CMD/GLM_STATE_FILE/
   PIPELINE_STATE_DB/HERMES_KANBAN_DB/SENTINEL_CMD + fixture DB/REPO/JOBS，仿 test_watchdog_unify）
   + 断言矩阵 T1-T16 逐条对照 §8.2（四态/熔断三态/收尾/恢复四态/清理/源 L 三态）
   + oc_wake_check.sh 源 L 追加（§6.2 代码块: K 后 conn.close 前插入 + glm_tail 独立输出
   仿 autopilot_tail + 跳过名单 L705-710 加 glm-shutdown 项 D14）
   + deploy_drift_check.sh DEFAULT_SYNC_LIST +1（5 脚本）+ test_deploy_drift.sh 期望同步
   + 既有回归四套件（test_idle_check/test_deploy_drift/test_watchdog_unify/test_cmd_channel）
   + DPL-048 部署验证说明（oc_wake_check/glm_quota_probe 均在 must-sync，diff 一致才 PASS，
   部署动作留 OC）;
   claim 带 changed_files（scripts/test_glm_quota_probe.sh 新增 + oc_wake_check.sh 修改
   + deploy_drift_check.sh 修改 + test_deploy_drift.sh 修改 + docs/est/t_2048b809-estimate.md 落 main）。
   预计 30-41 轮
```

- SPLIT: yes（count=2，校准后 61-84 轮超 20 阈值；基准 25.5-35 也超）
- MODE: serial（SUB-2 测试对象是 SUB-1 产物，严格依赖）
- ROUNDS_EST（校准后）: 59-79 分卡（基准 25.5-35 × K=2.40；SUB-1 29-38 / SUB-2 30-41）
- FILES: scripts/glm_quota_probe.sh + scripts/test_glm_quota_probe.sh（新增）+
  scripts/oc_wake_check.sh + scripts/deploy_drift_check.sh + scripts/test_deploy_drift.sh（修改）
  —— devPPL 仓
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂本链）
- TESTS: SUB-1 --inject 四态冒烟 + bash -n + 真实 probe OK；SUB-2 T1-T16 全量 + 四套件回归
- RISK: R1 状态机边界漏测（矩阵对照）；R3 源 F 输出段敏感（回归护栏）；R5 fixture 复杂度
  （缓冲从宽）；R9 est 产物落 main（changed_files 必含）
- ACTION: build_two_dev_cards（assignee=game-engine，serial，devPPL 仓 worktree）

## 6. 备注

1. **S2（OC 执行）不在本 [SUB-SPLIT]**：架构 §10.1 S2 四项（merge 部署 + cron 注册 +
   首 tick 线上验证 + R7 提交 Frank 裁定）是 OC 职责，SUB-2 done 后由 OC 建卡执行。
   dev 不擅自注册 cron、不擅自部署 profile 副本（DPL-048：部署动作永远留 OC）。
2. **R7（fallback 补齐）是建议项**（P2 优先级）：架构 §9 已给出建议（5 个单级 profile
   补 agnes），交 Frank 裁定，不阻塞本链。OC PRD 审核评论已确认 deepseek key 有效，
   fallback 链当前不是断的。
3. **测试不打真实 429**：全 --inject 驱动（架构 A5 契约）；真实 probe 只走 200 OK 路径
   验证连通（架构实测事实 7 已做过一次）。
4. **本评估卡不写功能代码**；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建
   2 张 [DEV-SUB-*] 卡执行（cmd_chain L1539 读本卡 [SUB-SPLIT]，子卡替代单 dev 卡）。
5. **历史偏差反思**：最近 5 卡估 18-33 全撞 60 上限（+1.03~+1.61），本卡按 K=2.40
   校准后分卡，单卡最大 30-41（71-98% 预算）——偏贴上限，兜底方案（T 矩阵裁剪优先级）
   已备，超预算风险主要在 SUB-2 的 fixture 复杂度段。
