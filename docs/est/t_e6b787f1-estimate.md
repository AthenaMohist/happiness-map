# 评估报告 — [FIX] autopilot 休眠期手工拆卡缺 VA 环节 — done 卡 VA 补扫机制 + 拆卡必带 VA 约束

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_e6b787f1
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_e6b787f1（[FIX] autopilot 休眠期手工拆卡缺 VA 环节 — done 卡 VA 补扫机制 + 拆卡必带 VA 约束）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后预计 45-63 轮 > 20 轮阈值）。**

任务本质是**补一个 autopilot 的巡检扫描机制**：扫描"done 但无 VA 验证卡"的 [DEV-*]/[FIX] 卡，
自动补建 [Step4] VA 卡（parents=源卡，assignee=verifier）。与既有 `process_standalone_subsplit`
（discover.py L869-961，每 tick 扫描 + 建卡 + fail-open）**完全同构**，实现模式成熟；
但存在几个已实锤的边界坑（R1 历史卡洪泛 / R2 VA 存在性判定口径 / R3 changed_files 过滤），
测试 fixture 需覆盖三种场景（验收 3）。按 DPL-018 校准系数 K=3.00 折算后总量远超 20 轮阈值，必须拆卡。
自然边界：S1 = 机制（扫描 + 建卡 + 挂载 + 约束注释），S2 = 测试（fixtures a/b/c + 幂等 + 回归 + 落地）。

**评估期间实锤现状**（2026-08-15 09:51）：VA 补验卡 t_ad5656e4（[Step4] VA 事后核验 — autopilot 休眠期
4 张手工链卡 claim）已 done，4/4 VERIFIED —— 根因 6 张卡中 4 张 sub 卡（t_6c4a9cae/t_a2466834/
t_6d807f49/t_288e56a6）已由 **verifier 手工补验**；2 张 [FIX] 容器卡（t_14fb6a11/t_0f418cf6）因
无 changed_files claim（容器语义）本就无需 VA。因此本 FIX 的**存量缺口已人工堵住**，剩余工作 = 把
补验能力**机制化**（autopilot 自动补扫），防止未来再发生。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **~2-3 个文件**：pipeline/discover.py（+`process_va_backfill` ~80-120 行，或独立 pipeline/va_backfill.py）、scripts/autopilot.sh（+1 挂载块 ~10 行）、scripts/test_cmd_channel.sh 或新 test_va_backfill.sh（+3 fixture 场景 ~150-250 行断言） | 实测 `process_standalone_subsplit`（discover.py L869-961）即模板：连接 kanban.db → 扫描候选 → 查重 → `_hermes_create` 建卡（idempotency-key + parents）→ 日志 → fail-open 全内吞 |
| ① 补扫扫描函数 | 仿 process_standalone_subsplit 结构：SELECT status='done' AND (title LIKE '[DEV-%' OR title LIKE '[FIX]%') AND 无 VA 子卡 AND claim 含 changed_files → `_hermes_create` "[Step4] VA 验证 — <源卡标题> claim（<tid>）" parents=[源卡] assignee=verifier idem_key=va-backfill-<tid>。**VA 存在性判定**：task_links 子卡 assignee='verifier'（最稳，覆盖 autopilot 建的 va-claim: <tid> 与 worker 建的 [Step4] VA 两种标题）或 title LIKE 'va-claim: <tid>'。**claim 判定**：task_comments 最新 [CLAIM]/[PRODUCES] comment body 含 `**changed_files**` 段 | 实测 VA 卡两命名并存：autopilot va-claim 步建 "va-claim: <tid>"（autopilot.sh L419）；worker/verifier 建 "[Step4] VA 验证 — …"（t_d8441c47 标题实证）/[Step4] VA 事后核验（t_ad5656e4 标题实证）。claim 格式：comment 1385（t_6c4a9cae）`**changed_files**:` + 反引号路径 bullet（claim-schema 标准） |
| ② autopilot.sh 挂载 | 仿 L171-176 subsplit 挂载点：python3 -c 调 `process_va_backfill`（或新脚本 bash va_backfill.sh），`|| true` fail-open；注释写明"每 tick 扫描 done 无 VA 卡补建 [Step4] VA" | 实测 L171-176 `process_standalone_subsplit` 挂载模式（每 tick 一次，独立于 ACTIVE_TASKS 循环） |
| ③ SUB-SPLIT 拆卡约束 | **选「autopilot 检测拆卡链缺 VA 立即补」实现**（需求 2 两选项之一）：同一补扫扫描天然覆盖 [DEV-SUB-*] 子卡（title LIKE '[DEV-%' 命中）——拆卡链上任意 done 无 VA 卡都会被补扫抓到，无需 worker 侧同步建卡逻辑。在 process_va_backfill 头注释 + autopilot.sh 挂载注释中写明"本机制同时满足需求 2（SUB-SPLIT 拆卡约束）" | 实测拆卡链 t_14fb6a11→t_6c4a9cae→t_a2466834 中 sub 卡标题为 "[DEV-SUB-N] …" 均命中 [DEV-% 前缀；根因正是手动拆卡链 done 时无 VA |
| ④ 测试 | 3 fixture 场景（验收 3）：(a) done 卡无 VA 卡 + claim 含 changed_files → 补建 VA 卡（断言：卡存在、assignee=verifier、parents=源卡、idem_key 正确）；(b) 已有 VA 卡（verifier 子卡存在）→ 不重复建（卡数不变）；(c) 暂停期拆卡链（3 张 done [DEV-SUB-*] 无 VA）→ 恢复后跑一次扫描 → 3 张全补建。外加幂等重跑 / claim 无 changed_files 跳过 / [DEV-EST] 排除 / DB 缺失 fail-open | 实测 test_cmd_channel.sh harness（L22-116）：隔离 temp kanban.db（复制真实 schema + DROP 触发器）+ 受控注入行 + q1 helper；fixture 注入模式现成，无需新 harness。当前断言基线 387 PASS（386 基线 + T15-T18 的 +1，t_ad5656e4 claim 实证） |
| ⑤ 全量回归 | test_cmd_channel.sh 387 + test_wip_progress_check.sh 62 + bash -n ×2（discover.py 改动跑 pytest 相关单测若存在）；main 上复跑 | t_ad5656e4 claim 实证两套数字；本评估实测 test_cmd_channel.sh PASS=387 FAIL=0 |
| ⑥ 收尾 | 自身分支 merge 进 main + 结构化 claim + [PRODUCES] comment + 飞书推送 + kanban_complete | 落地铁律：禁卡 done 代码留 worktree；SOUL 5.1 飞书硬性要求 |

**基准轮数（未校准）：15-21 轮**（① 5-7 + ② 1 + ③ 1 + ④ 5-7 + ⑤ 1-2 + ⑥ 2-3）。
**DPL-018 校准：基准 × K=3.00 → 校准后 45-63 轮**（取中位 54）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **历史卡洪泛（最大风险）** | **中-高** | 当前 board 有 **238 张 done [DEV-*]/[FIX] 卡**（实测 SQL COUNT）。若无时间窗口，补扫一次会为所有历史无 VA 卡批量建 VA 卡 → verifier 队列爆炸 + 每张 VA 卡都是一次完整验证 run。存量 6 张缺口已由 t_ad5656e4 人工补验 → **建议默认只扫近 N 小时 done 的卡**（env `VA_BACKFILL_WINDOW_H`，默认 24h，可调宽），超出窗口的缺口记日志留给 OC 处置（fail-open 语义，与源 E LANDING_CHECK_WINDOW_H 同款模式）。需在 S1 内定窗口 + 上限（如每 tick ≤10 张，防洪泛） |
| R2 VA 存在性判定口径 | 中 | 判"已有 VA"必须同时覆盖：task_links 子卡（autopilot va-claim 步建的 "va-claim: <tid>" 与 worker 建的 "[Step4] VA 验证 —" 都是源卡的 task_links 子卡）+ 标题直查兜底。**用「子卡 assignee='verifier'」为主判定最稳**——它天然覆盖两种命名，也覆盖批量补验卡（t_ad5656e4 同时是 4 张源卡的子卡）。单查 title LIKE 'va-claim: <tid>' 会漏掉 worker 建卡场景 → 重复建卡（幂等键虽防同 key 重复，但 worker 卡无 va-backfill- 前缀 key，会真重复） |
| R3 claim changed_files 过滤 | 中 | "claim 无 changed_files 则跳过"需解析 task_comments：一卡可能多条 comment，最新 [CLAIM]/[PRODUCES] 才权威；body 含 `**changed_files**` 即判定有产物。容器卡（[FIX] 拆卡源卡，如 t_14fb6a11/t_0f418cf6）无 changed_files claim → 正确跳过（本就不需 VA）；[DEV-EST] 评估卡（title 也命中 [DEV-%）必须显式排除（评估卡无代码产物）；[DEV-MERGE]/[DEV-QA-SUB-*] 需按 assignee/title 排除避免误建 |
| R4 与 discover 注册的交互 | 低-中 | 补建的 "[Step4] VA 验证 —" 卡 title 不以 va-claim:/va: 前缀开头 → 不命中 SUB_TASK_TITLE_PREFIXES（discover.py L106-121）→ 若该卡 status='ready' 且 assignee=verifier 在 PIPELINE_ASSIGNEES（L81-87），**会被 discover_new_tasks 误注册为管线任务**（_card_type 返回 None → 走 dev-only 注册）。缓解：补建时用 idempotency-key va-backfill-<tid> + **title 复用 "va-claim: <tid>" 前缀**（命中 SUB_TASK_TITLE_PREFIXES，天然排除），或补建后立即 demote todo。**S1 内必须先定 title 方案**（推荐复用 va-claim: 前缀，与 autopilot va-claim 步命名一致，零 discover 交互） |
| R5 幂等 | 低 | idem_key `va-backfill-<tid>`（kernel 幂等）+ 每 tick 重扫天然幂等（已建则 VA 存在性判定命中 → 跳过）。重复 tick 不重复建卡 |
| R6 全量回归 | 低 | discover.py/autopilot.sh 改动只增不删 → 既有 387 断言不受影响（源 A-D + T15-T18 断言不涉及补扫）；但必须全量复跑确认。新增 fixture 用独立 temp DB，不触碰真实 board |
| R7 自身落地自引用 | 低 | S2 改的 test 文件与 discover.py 也要进 main → S2 收尾含自身 merge，与源卡约束 5 一致；fixture 测试保证能力不依赖 live 状态 |

**关键决策点（S1 实现时拍板，不改轮数量级）**：D1 时间窗口（`VA_BACKFILL_WINDOW_H`，默认 24h + 每 tick 上限）；
D2 VA 存在性判定（推荐 task_links 子卡 assignee='verifier' 为主）；D3 补建卡 title（推荐复用 `va-claim: <tid>`
前缀防 discover 误注册，或 `[Step4] VA 验证 — <tid>` + 同步加入 SUB_TASK_TITLE_PREFIXES 排除——二选一，注释写明）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 15-21 轮（中位 18） |
| DPL-018 校准后 | 45-63 轮（×K=3.00，中位 54）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（机制）→ S2（测试 + 回归 + 落地）单向依赖：S2 的 fixture 断言必须等 S1 的函数在 main 上存在才能跑 |
| 并行收益 | 低——S2 测试断言 S1 的函数行为，天然串行 |
| 兜底 | 每张子卡独立验收闭环：S1 交付补扫机制 + 挂载（需求 1/2 可验）；S2 交付 3 fixture 测试 + 全量回归（需求 3/4 可验）。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。** 量级参照：t_14fb6a11（5 文件 + 386 回归 → 拆 2 serial，
S1/S2 均单会话完成）；本卡改动面更小（2-3 文件），但 fixture 场景 3 组 + discover 注册交互（R4）需要
S1 先定 D1-D3 决策。拆 2 卡后每卡 21-32 校准轮，均在单会话可控区间（42 有效轮）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] VA 补扫机制 S1 — pipeline/discover.py process_va_backfill + autopilot.sh 挂载
   （仿 process_standalone_subsplit：每 tick 扫 status='done' AND (title LIKE '[DEV-%' OR
    title LIKE '[FIX]%') AND 无 VA 子卡 AND claim 含 changed_files 的卡 → _hermes_create
    "[Step4] VA 验证 — <源卡标题> claim（<tid>）" parents=[源卡] assignee=verifier
    idem_key=va-backfill-<tid>；VA 存在性判定 = task_links 子卡 assignee='verifier'；
    claim 判定 = 最新 [CLAIM]/[PRODUCES] comment 含 **changed_files**；排除 [DEV-EST]/
    [DEV-MERGE]/[DEV-QA-SUB-*]/容器卡（无 changed_files 天然跳过）；env VA_BACKFILL_WINDOW_H
    默认 24h + 每 tick 上限防历史洪泛；头注释写明「本机制同时满足需求 2 SUB-SPLIT 拆卡约束」；
    S1 内先定 D1 窗口 / D2 VA 判定 / D3 补建卡 title（推荐 va-claim: 前缀防 discover 误注册）；
    autopilot.sh L171 后追加挂载块 || true fail-open） 预计 8-11 轮
2. [DEV-SUB-2] VA 补扫机制 S2 — 3 fixture 测试 + 全量回归 + 落地
   （test_cmd_channel.sh 追加或新 test_va_backfill.sh，复用隔离 temp DB harness：
    (a) done 无 VA + claim 有 changed_files → 补建 VA 卡（断言 assignee/parents/idem_key）；
    (b) 已有 VA 子卡 → 不重复建（卡数不变）；(c) 暂停期拆卡链 3 张 done [DEV-SUB-*] 无 VA →
    扫描一次 → 3 张全补建；+ 幂等重跑 / claim 无 changed_files 跳过 / [DEV-EST] 排除 /
    DB 缺失 fail-open / VA_BACKFILL_WINDOW_H 窗口边界；全量回归 test_cmd_channel.sh 387 +
    test_wip_progress_check.sh 62 + bash -n；S2 自身分支 merge 进 main + claim + 飞书 + complete）
    预计 10-14 轮
```

- SPLIT: yes（count=2，校准后 45-63 轮远超 20）
- MODE: serial（S2 测试断言依赖 S1 函数在 main 上存在）
- ROUNDS_EST（校准后）: 54（基准 18 × K=3.00）
- FILES: S1 改 pipeline/discover.py（+process_va_backfill ~80-120 行）+ scripts/autopilot.sh（+挂载 ~10 行）；S2 改 scripts/test_cmd_channel.sh 或新 scripts/test_va_backfill.sh（+3 fixture 场景 ~150-250 行）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂 t_e6b787f1）
- TESTS: S1 bash -n + 冒烟（隔离 DB 跑一次扫描建 1 张卡）；S2 3 fixture 场景（~10-15 断言）+ 全量回归 387 + 62
- RISK: R1 历史卡洪泛（窗口 + 上限）；R2 VA 存在性判定口径（task_links verifier 子卡为主）；R3 claim changed_files 过滤（容器/[DEV-EST] 排除）；R4 discover 误注册（D3 title 方案）；D1-D3 实现时拍板
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_e6b787f1]，serial）

## 6. 备注

- **存量缺口已人工堵住**：t_ad5656e4（VA 事后核验，09:51 done）4/4 VERIFIED 覆盖 4 张手工链卡；
  2 张 [FIX] 容器卡无 changed_files claim 本就无需 VA。本 FIX 价值 = 把补验从"人工"变成"机制"，
  防止下次 autopilot 休眠/暂停期再出现缺口（Frank：任何情况不走 VA 都不合规）。
- **R1 窗口是必做项**：238 张 done [DEV-*]/[FIX] 卡若无窗口会一次性洪泛 verifier 队列。
  窗口 + 每 tick 上限双保险；超出窗口的历史缺口记日志留给 OC（fail-open，不阻断主流程）。
- **R4 title 方案优先复用 `va-claim: <tid>` 前缀**：与 autopilot va-claim 步（autopilot.sh L419）
  命名一致，天然命中 SUB_TASK_TITLE_PREFIXES 不被 discover 注册；body 里写清验证要点（对齐
  autopilot.sh L420-422 的 va-claim 约束文案）。若坚持 "[Step4] VA 验证 —" 标题（对齐 t_d8441c47
  样本），必须同步把该前缀加入 discover.py SUB_TASK_TITLE_PREFIXES，二选一，注释互链。
- **实现复用 `process_standalone_subsplit` 模式**（discover.py L869-961）：连接 → 扫描 → 查重 →
  建卡 → 日志 → finally close → except sqlite3.Error 返回 dict。建卡走 cmd_chain._hermes_create
  （idempotency-key + parents + workspace 参数），不裸写 hermes CLI。
- **本评估卡不写代码**；autopilot 读取 [SUB-SPLIT] comment 后建 2 张 [DEV-SUB-*] 卡（parents 链按 serial 挂接）。
- 评估期间实测基线：test_cmd_channel.sh PASS=387 FAIL=0（含 T15-T18；源卡验收 4 写 386 为 T15-T18 前快照）。
- 每张子卡完成后推飞书（send_claim_feishu.py，SOUL 5.1 硬性要求）。
