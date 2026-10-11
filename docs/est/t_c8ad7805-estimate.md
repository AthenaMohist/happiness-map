# 评估报告 — [DEV-EST] worker 上下文连续性 — 检查点提交+发现笔记+预算收紧+审批白名单（DPL-030）

> 评估人：寇豆码（game-engine） | 日期：2026-08-14 | 评估卡：t_c8ad7805
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_c8ad7805（[DEV-EST] DPL-030 worker 上下文连续性 — 检查点提交+发现笔记+预算收紧+审批白名单）
> 上游：PRD t_84c53424（docs/prd/worker-context-continuity-prd.md，255 行）+ arch t_d24d1ad5（docs/arch/arch-worker-context-continuity.md，329 行，commit 22de657）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 4 张串行子卡（校准后预计 45-60 轮 > 20 轮阈值）。**

任务本身是**机械型实现**（常量 + 注入脚本 + 7 处文本注入 + 测试断言），无环境发现/无算法风险，
但改动面横跨 **7 个文件 + 373 断言回归**，且存在已实锤的回归雷（T59e/T60a 断言 body 末行=
存档要求行，追加 WIP_BODY_LINE 后必破）。按 DPL-018 校准系数 K=3.00 折算后总量远超 20 轮阈值，
必须拆卡。自然边界按 arch §7.1 的 S1/S2/S3 拆成 4 张（S2 的 est 口径注入与 S1 共用 cmd_chain.py/
discover.py 注入点，并入同一卡避免同文件双改；测试单列）。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **7 个文件**：pipeline/constants.py（+11 常量）、scripts/inject_wip_rule.sh（新，~63 行）、pipeline/cmd_chain.py（3 处注入）、pipeline/discover.py（1 处注入）、scripts/autopilot.sh（5 处 comment）、scripts/devppl_query.sh（+comments 子命令）、scripts/test_cmd_channel.sh（+断言 + 修正 2 处既有断言） | arch §5 模块划分；全部注入点已逐行核实（见下） |
| ① constants.py | 追加 `WIP_SOUL_TITLE/WIP_SOUL_PROFILES/WIP_CHECKPOINT_MIN_ROUNDS/WIP_CHECKPOINT_MAX_ROUNDS/WIP_COMMIT_PREFIX/WIP_NOTE_DIR/WIP_BODY_LINE/WIP_SOUL_PARAGRAPH/EST_EFFECTIVE_RATIO/EST_SPLIT_ROUNDS/EST_EFFECTIVE_LINE`，插在 CHECKPOINT_* 段（L200-245）之后。纯追加无侵入 | 实测 L210-241 CHECKPOINT_* 段；arch §1.2 给出全部常量定义 |
| ② inject_wip_rule.sh | 复刻 inject_checkpoint_rule.sh（63 行同构：--dry-run/--verify/--profiles + 幂等 SKIP + constants 单一源 import）。**只能本地 --dry-run 验证**（真实 9 profile 写入需 OC 授权，PRD §7 约束 4），交付 = 脚本就绪 + OC 执行后 --verify | 实测 scripts/inject_checkpoint_rule.sh 63 行；arch §1.3 |
| ③ cmd_chain.py 注入 | `_dev_card_body` 末行追加 WIP_BODY_LINE（L646 后）；`_sub_card_body` 末尾追加 CHECKPOINT_BODY_LINE + WIP_BODY_LINE（L849 前，修正 2 补洞，dev/qa 共用）；dev-est 块追加 EST_EFFECTIVE_LINE（L621-638 块内）。3 处 + import 行（L44 现有 CHECKPOINT_* import 旁） | 实测 L646 `lines.append(CHECKPOINT_BODY_LINE)`；L811-849 `_sub_card_body` 当前**无存档行**（S2 病根）；L621-638 dev-est 块 |
| ④ discover.py 注入 | `_create_est_card` est_body 追加 EST_EFFECTIVE_LINE（L244-246 之间）+ WIP_BODY_LINE（L249 CHECKPOINT_BODY_LINE 后） | 实测 L236-250 est_body 构造 |
| ⑤ autopilot.sh comment | 5 处 comment 串追加 `[WIP 节奏] ...（DPL-030）`：L159（手动卡）/L343（dev）/L383（qa-exec）/L520（qa-post）/L665（qa-d1 retry）。PRD 写 6 处，实测 L362/L400 无 comment 参数 → **按 5 处执行** | 实测 L159/L343/L383/L520/L665 五处 `kanban_ensure_card ... comment 串` 均含 [claim 要求]/[超轮次] 前缀 |
| ⑥ devppl_query.sh | 新增 `comments <task_id>` 子命令（白名单 `^t_[a-z0-9]+$` + mode=ro + ORDER BY created_at ASC）+ usage 行注册。~10 行，模式与 task/runs 完全一致 | 实测 q() 已有 datetime 按列名转换，comments 自动获得时间可读性 |
| ⑦ 测试断言 | 新增 AC-4（dev body 含 WIP_BODY_LINE）/AC-5（est body 含 EST_EFFECTIVE_LINE 双入口）/AC-6（devppl_query comments + BAD_ID 拒绝）/AC-9（subsplit 子卡 body 含 WIP+CHECKPOINT 双行）/AC-10（EST_SPLIT_THRESHOLD_ROUNDS=20 不变回归）约 10-15 断言 + **修正 T59e/T60a**（见风险 R1）+ 全量 373+ 回归 | 实测 T59e L1939 断言 `DEV_LAST=存档要求:`；T60a L1967 断言 est body 末行=存档要求行；T68b L2342 已断言阈值 20 |
| ⑧ 收尾 | commit（dev 卡强制 worktree）+ 结构化 claim + 飞书推送 + kanban_complete | 团队惯例 |

**基准轮数（未校准）：15-21 轮**（① 1 + ② 3 + ③ 3 + ④ 1 + ⑤ 2 + ⑥ 1 + ⑦ 4-6 + ⑧ 1-2）。
**DPL-018 校准：基准 × K=3.00 → 校准后 45-63 轮**（取中位 54）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **T59e/T60a 末行断言必破（最高置信回归）** | **高** | T59e 断言 `_dev_card_body` 末行 = 存档要求行；T60a 断言 est 卡 body 末行 = 存档要求行。追加 WIP_BODY_LINE/EST_EFFECTIVE_LINE 后末行变化 → 断言必破。**不是"可能回归"，是确定要修的既有断言**。修正 = 断言改为"末行=WIP 行"或"含双行"，同时保留 CHECKPOINT 行存在性断言。测试卡 S3 轮数已含此修正 |
| R2 高频共改文件 merge 冲突 | 中 | cmd_chain.py / autopilot.sh / test_cmd_channel.sh 是仓库高频共改文件（t_73aed882 刚改过 cmd_chain L564-647 区）。4 张子卡串行 + 独立 worktree 分支，merge 阶段预留手动解决时间（每次 merge 都发生测试冲突解决先例） |
| R3 inject_wip_rule.sh 无法本地全量验证 | 中 | 真实注入写 /root/.hermes/profiles 跨 profile → 需 OC 授权。dev 交付 = 脚本 + --dry-run 预览输出；--verify 9/9 只能 OC 执行后补验。验收口径 AC-2 以"脚本输出（--dry-run 预览 + 真实注入记录）"为准，dev 侧可交付 dry-run 证据 |
| R4 文案漂移（7 处注入点 × 长串） | 中 | 全部文案唯一源 constants（WIP_BODY_LINE / EST_EFFECTIVE_LINE / [WIP 节奏] 串），注入点只引用不复制；测试断言锚定关键子串。arch §9 已列缓解，实现时严格遵循"不复制文案" |
| R5 全量回归时长 | 低 | 373+ 断言单次 2-5 min；新增子卡 body 断言需构造 _sub_card_body 输入（复用 T27/T28 模式） |
| R6 S4 OC 执行依赖 | 低（阻塞收尾） | SOUL 注入是 OC 授权动作，dev 卡完成后需 OC 执行 inject_wip_rule.sh + 贴 --verify 输出回卡。**不阻塞 dev 卡 complete**，但 AC-2 的"真实注入记录"闭环依赖 OC 动作 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 15-21 轮（中位 18） |
| DPL-018 校准后 | 45-63 轮（×K=3.00，中位 54）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | 常量（S1）→ 注入落点（S2）→ 测试（S3）单向依赖；est 口径（R3）与 body 注入共用 cmd_chain/discover 注入点，**不可拆到独立卡**（同文件双改冲突）；autopilot 与 devppl_query 文件互斥可并入 S2 |
| 并行收益 | 低——4 卡共享 constants.py / cmd_chain.py / test_cmd_channel.sh 依赖链，并行双 worktree 必然 merge 冲突（DPL-026/027 教训）；串行依赖清晰 |
| 兜底 | 每张子卡有独立可提交验收闭环：S1 常量+脚本（AC-1/2 可验）；S2 注入（AC-3/4/5/6/9 可验）；S3 测试回归（AC-7/10 可验）。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 4 张串行子卡（[SUB-SPLIT] 4 serial）。** 量级参照：t_40ec4bde（24-30 轮 → 拆 2 卡，6 文件 + 3 测试文件）；本卡 7 文件 + 确定性回归修正，拆 4 卡后每卡 9-21 校准轮，均在单会话可控区间（60 轮预算 × 0.7 = 42 有效轮）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 4 serial
1. [DEV-SUB-1] DPL-030 S1a — constants.py WIP_*/EST_* 常量 + scripts/inject_wip_rule.sh 幂等注入脚本
   （11 个常量单一源：WIP_SOUL_TITLE/PROFILES/MIN/MAX/COMMIT_PREFIX/NOTE_DIR/BODY_LINE/SOUL_PARAGRAPH
    + EST_EFFECTIVE_RATIO/EST_SPLIT_ROUNDS/EST_EFFECTIVE_LINE，插在 CHECKPOINT_* 段后；
    inject_wip_rule.sh 复刻 inject_checkpoint_rule.sh 63 行同构，--dry-run/--verify/--profiles，
    本地 --dry-run 验证 + 幂等重跑 SKIP；真实 9 profile 注入留 OC 执行） 预计 9-12 轮
2. [DEV-SUB-2] DPL-030 S1b — 建卡路径注入全量：cmd_chain.py 3 处（_dev_card_body 末行 WIP_BODY_LINE
   + _sub_card_body 末尾 CHECKPOINT_BODY_LINE+WIP_BODY_LINE 补洞 + dev-est 块 EST_EFFECTIVE_LINE）
   + discover.py est_body（EST_EFFECTIVE_LINE + WIP_BODY_LINE）+ autopilot.sh 5 处 comment [WIP 节奏]串
   + devppl_query.sh comments 子命令（白名单+只读） 预计 12-15 轮
3. [DEV-SUB-3] DPL-030 S2 — test_cmd_channel.sh 新断言：AC-4（dev body 含 WIP_BODY_LINE）
   + AC-5（est body 含 EST_EFFECTIVE_LINE 双入口）+ AC-6（devppl_query comments + BAD_ID 拒绝）
   + AC-9（subsplit 子卡 body 含 WIP+CHECKPOINT 双行）+ AC-10（EST_SPLIT_THRESHOLD_ROUNDS=20 不变）
   + 修正 T59e/T60a 末行断言（必破回归）+ 全量 373+ 回归 预计 15-21 轮
4. [DEV-SUB-4] DPL-030 S3 — 收尾：全量回归确认 + 结构化 claim（changed_files/tests_run/verification）
   + 飞书推送 + kanban_complete；提醒 OC 执行 inject_wip_rule.sh 并贴 --verify 输出回卡（AC-2 闭环）
   预计 9-12 轮
```

- SPLIT: yes（count=4，校准后 45-63 轮远超 20）
- MODE: serial（S1a→S1b→S2→S3 单向依赖；并行必撞 constants/cmd_chain/test 共改文件）
- ROUNDS_EST（校准后）: 54（基准 18 × K=3.00）
- FILES: pipeline/constants.py, scripts/inject_wip_rule.sh（新）, pipeline/cmd_chain.py, pipeline/discover.py, scripts/autopilot.sh, scripts/devppl_query.sh, scripts/test_cmd_channel.sh
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 4 张子卡）
- TESTS: 新增 ~10-15 断言（bash test_cmd_channel.sh）；修正 T59e/T60a；全量回归 373+ PASS
- RISK: R1 T59e/T60a 必破（已计入 S2 轮数）；R2 merge 冲突高频文件；R3 SOUL 注入需 OC 授权；R4 文案漂移靠 constants 单一源
- ACTION: build_four_dev_cards（assignee=game-engine，serial parents 链）

## 6. 备注

- **校准口径说明**：DPL-018 注入的 K=3.00 来自 t_e33936c6（BKP-004 S2 预估 12-18 / 实际 60 轮，偏差 +3.00，timed_out）。本卡基准 15-21 轮已含"机械型任务"折扣（无环境发现/无算法风险，arch 给出精确注入点行号）；但 S2 病例证明 60 轮预算下任何实现深水区都可能耗尽，且本卡有确定性回归修正（R1）+ 7 文件横切，按校准后口径拆 4 卡是稳妥决策。
- **与 arch §7.1 的关系**：arch 建议"1 张 dev 卡（有效轮 ~20 < 20 拆卡阈值）"是**未应用 DPL-018 K 校准**的乐观口径；本评估卡按任务 body 明确要求"请按校准后口径重新评估"执行，拆 4 卡。若 Frank/OC 认为 K=3.00 对机械型任务过严，可合并为 2 卡（S1a+S1b / S2+S3），每卡 21-33 校准轮，属可接受区间。
- **PRD 写 6 处 comment 注入、arch 实测 5 处**：L362（qa-d1 正常路径）/L400（qa-d2）的 kanban_ensure_card 调用无 comment 参数（仅 3 参数），不构成注入点。dev 实现按 arch 实测 5 处执行，PRD 差异已在 arch 卡记录。
- **本评估卡不写代码**；autopilot 读取 [SUB-SPLIT] comment 后建 4 张 [DEV-SUB-*] 卡（parents 链按 serial 挂接）。
