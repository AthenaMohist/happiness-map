# 评估报告 — [FIX] VA 补扫容器豁免失效 — t_1db58772 no-claim skip 持续（DPL-072）

> 评估人：寇豆码（game-engine） | 日期：2026-08-19 | 评估卡：t_est_f3108dfd | 源卡：t_f3108dfd
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：t_1db58772（DPL-069 容器卡，autopilot 关闭无 claim）→ **本评估** → FIX 卡 t_f3108dfd 执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0，沿用 t_1db58772 同族最新口径）；最近 5 条子卡偏差全部 timed_out

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 15-25 / 17-25 轮，全部落在 42 有效轮预算内）。**

任务本质：va_backfill（discover.py `_va_skip_reason`）的 legit-container 豁免判据过窄——
只认 `task_links` **直接子卡 EXISTS**（DPL-060 t_af4313bd 实现）。t_1db58772 的 work 子卡
（t_4778efd8/t_dbbec269）挂在**评估卡 t_est_1db58772 下**（serial 链），源卡自身 children=[] →
豁免永不满足 → 每 tick 归类 no-claim → [VA-SKIP] comment + `.pipeline/va-skip/*.json`
skip_count 持续递增（实测 18）→ oc_wake_check 源 H 持续向 OC 报 [va-skip] 告警。

**评估期间实测确认（非假设）：**
- t_1db58772 已有 **3 条 [SUB-SPLIT-DONE] comment**（autopilot 关闭源卡的容器语义标记，
  1719 已建 2 张子卡 / 1727 子卡全部完成）。→ 判据补「[SUB-SPLIT-DONE] 标记存在」即可直接命中豁免。
- t_1db58772 chain：parent=t_est_1db58772（评估卡）；评估卡 children 含 t_4778efd8（DPL-070，done，
  VA 13/13 [VERIFIED]）、t_dbbec269（DPL-071，done，VA 5/5 [VERIFIED]，挂 t_4778efd8 下 serial）。
  → 判据补「沿 task_links 双向查找到 done 子卡且均 VA VERIFIED」亦命中。
- oc_wake_check.sh 源 H（L492-541）当前防御只认 comment 内 `reason == "legit-container"`
  （L525）——但 discover.py 对 legit-container **不写 comment**（D6 豁免），历史 no-claim comment
  残留后源 H 无法识别容器 → **源 H 也必须补同一容器判据**（防历史 comment 继续触发告警）。
- oc_wake_check.sh 是 **cron 前置脚本 + must-sync 清单（D-A jobs.json 直调 + D-B stuck_check.sh:58 引用）**
  → 部署验证规则适用（DPL-048：repo↔live md5 一致才 PASS；部署动作留 OC，研发只交 repo 正本 + 审计）。

## 2. 工作量评估（读码结论，非假设）

改动面：**2 文件**（pipeline/discover.py `_va_skip_reason` L1205-1228 改 ~25-40 行 + 新 helper；
scripts/oc_wake_check.sh 源 H L492-541 改 ~15-25 行 python heredoc）+ 1 测试文件
（scripts/test_va_backfill.sh 增 ~80-120 行新用例组 T11）。
回归面：test_va_backfill.sh 全组（46 断言）+ test_watchdog_unify.sh（T1-T9）+ test_wip_progress_check.sh
（T1-T23）+ bash -n ×2 + 部署验证 md5。

| 维度 | 评估 | 依据 |
|------|------|------|
| ① SUB-1 机制（discover.py `_va_skip_reason` + oc_wake 源 H） | 读码复盘（现判据 + t_1db58772 数据形态 + 源 H 防御缺口）**1-2 轮**；方案裁决（判据二选一 OR：SUB-SPLIT-DONE 标记 / 双向 done 子卡 VERIFIED；seen 键与 fail-open 语义）**1-2 轮**；实现：`_container_exempt(conn, tid)` helper（查 task_comments [SUB-SPLIT-DONE]% → 真；查 task_links 双向：tid 的 parent → parent 的 children（排除自身）→ 全部 done 且均有 [VERIFIED] comment → 真；异常内吞 fail-open）**2-3 轮**；源 H 同判据防御（历史 no-claim comment 残留卡仍豁免）**1-2 轮**；bash -n + py_compile + 手工冒烟（临时 fixture 复刻 t_1db58772 链）**1-2 轮** → **基准 6-10** | `_va_skip_reason` L1205-1228 全代码实读；源 H L492-541 实读；t_1db58772 3 条 SUB-SPLIT-DONE comment 实测；t_4778efd8/t_dbbec269 done+VERIFIED 实测；DPL-060 arch D6 豁免语义实读 | 
| ② SUB-2 测试+回归（test_va_backfill.sh） | 新 fixture 批次（复刻 t_1db58772 链：est 卡 + 源卡无 children + 子卡挂 est 下 done+VERIFIED；SUB-SPLIT-DONE 标记卡；真 no-claim 反例）**1-2 轮**；T11 断言组 6-8 条：(a) SUB-SPLIT-DONE 标记 → 豁免不写 comment/不注册 (b) 双向 done 子卡+VERIFIED → 豁免 (c) 真 no-claim 仍留痕+源 H 仍报（验收 2 反例不丢）(d) 源 H 历史 comment 残留卡 → 豁免不报 (e) seen 幂等（重跑不重复报）(f) 计数锚点（T1-T10 零回归）**2-3 轮**；全量回归（test_va_backfill 46+新 + test_watchdog_unify T1-T9 + test_wip_progress_check T1-T23 + bash -n ×2）**2-3 轮**；部署验证（md5 repo vs live，审计报告，部署留 OC）**1 轮**；claim+飞书+complete **1 轮** → **基准 7-10** | T10 fixture 模式现成（batch5 后置 seed + run_scan/rj helper 直接复用）；源 H 测试已在 test_va_backfill T10c/T10e 覆盖（非 test_watchdog_unify——T1-T9 只测 I/J/K，源 H 不在此）；用例膨胀按 +40% 备（MEM-007 12→17 实证同款） |

**基准轮数（未校准，合计）：13-20 轮（中位 ~16）。**
**DPL-018 校准：13-20 × K=2.45 → 校准后 32-49 轮**（单卡 76-117% 预算 → 必须拆卡）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 双向查找语义歧义（验收 1 核心） | 中 | 「存在 done 子卡且均 VA VERIFIED」的查找半径需明确：建议「tid 的 parent（评估卡）→ 该 parent 的 children（排除自身）→ 全部 done 且均有 [VERIFIED] comment」即可；更深层（t_dbbec269 挂 t_4778efd8 下）不必递归——已有 3 条 [SUB-SPLIT-DONE] 标记直接命中，双向判据是兜底。测试须同时覆盖两层挂法（est→src+sub1 / sub1→sub2） |
| R2 | 历史 [VA-SKIP] no-claim comment 残留 | 中 | t_1db58772 已有 1 条 no-claim comment + skip_count=18 的 json。即使 discover.py 停止新增，源 H 读最新 comment 仍报 no-claim → 源 H 必须补容器判据（L525 防御从「只认 reason 字面」扩为「卡级容器判定」）。测试 T11d 显式覆盖 |
| R3 | seen 键幂等语义（验收 1 的「不再产出 [va-skip] 行」） | 中低 | 状态型键 `va-skip:<tid>:<skip_count>` 不变不重报；修复后 skip_count 冻结 → 键自然不再更新 → 不再产出新行。若源 H 判据修复彻底，历史卡直接豁免（L525 continue）→ 双保险。T11e 覆盖重跑幂等 |
| R4 | fail-open 反例不丢（验收 2） | 中 | 真 no-claim（无 [SUB-SPLIT-DONE]、无 done 子卡 VERIFIED 证据）必须仍报。判据实现用 AND/OR 语义要精确：标记 OR 双向证据任一命中才豁免；SQL 异常 → 不豁免（走 no-claim/nonstd 原路径）。T11c 显式反例 |
| R5 | 部署验证（cron 前置脚本 + must-sync） | 中 | oc_wake_check.sh 改动直接影响每 tick 唤醒输出。缓解：全量回归（三套 shell 套件 + bash -n）+ 部署验证（repo↔live md5，部署留 OC；merge 后 deploy-drift 源 G 报自身漂移为预期 R2 自引用悖论，OC 部署平息）。discover.py 非 cron 直调（autopilot 内部 repo 路径执行）→ 不适用 must-sync |
| R6 | 用例膨胀 | 已计入 | 新用例组按 +40% 备（MEM-007 12→17 实证）；T11 合计 6-8 断言，后置 seed 批次不扰动前置计数（DPL-033 D3 教训） |
| R7 | 评估卡自身（本卡）超时 | 低 | 只读码+估轮，不写功能代码，60 轮预算充裕 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 13-20 轮（中位 ~16） |
| DPL-018 校准后 | 32-49 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个（机制改造 / 测试+回归）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 13-20 → 校准 32-49 = 单卡 76-117% 预算 ❌ 且最近 5 卡 timed_out 前科（估 18-33 全部撞 60 上限）→ 单卡不可行 |
| 本评估 2 卡方案 | SUB-1 基准 6-10 → 校准 15-25（25/42 = 60%）；SUB-2 基准 7-10 → 校准 17-25（25/42 = 60%）✅ |
| 依赖方向 | SUB-2 断言 SUB-1 的行为（豁免判据 + 源 H 防御）→ 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——同文件族（discover.py / oc_wake_check.sh / test_va_backfill.sh）强耦合，串行最稳；SUB-2 若并行需等 SUB-1 merge，无净收益 |
| 兜底 | SUB-1 若超预算：判据实现按「SUB-SPLIT-DONE 标记先行 + 双向兜底」可切块（contingency SUB-1b：只做标记判据 + 源 H 防御，跳过双向）；SUB-2 若超预算：T11c（真 no-claim 反例）优先级最高，其余断言可精简 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_1db58772（DPL-069，同脚本族同型改造，拆 2 serial 17-27/15-20 已完成）、
t_12539484（DPL-061，拆 3 serial 同脚本族）。本任务比 DPL-069 小一个量级（~30-60 行 python +
一个测试用例组），2 卡粒度与「机制/测试」天然分段对齐。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] VA 补扫容器豁免判据补兜底 — pipeline/discover.py `_va_skip_reason`（L1205-1228）：
   新增 `_container_exempt(conn, tid)` helper，判据 OR（任一命中即 legit-container）：
   (a) task_comments 存在 body LIKE '[SUB-SPLIT-DONE]%'（autopilot 关闭源卡标记）；
   (b) 双向 task_links：tid 的 parent → 该 parent 的 children（排除 tid 自身）→
       全部 status='done' 且均有 [VERIFIED] comment（VA VERIFIED 兜底）；
   异常内吞 → 不豁免（走原 no-claim/nonstd fail-open 路径）；
   + scripts/oc_wake_check.sh 源 H（L492-541）：防御从「comment 内 reason=='legit-container'」
   扩为「卡级容器判定」（历史 no-claim comment 残留卡仍豁免，防源 H 继续报）；
   头注释 DPL-060 R2 语义更新；bash -n + py_compile + 手工冒烟
   （临时 fixture 复刻 t_1db58772 链：est 卡 + 源卡无 children + 子卡挂 est 下 done+VERIFIED）。
   预计 15-25 轮
2. [DEV-SUB-2] VA 容器豁免测试 + 全量回归 — scripts/test_va_backfill.sh 新增 T11
   （复用 run_scan/rj/后置 seed fixture）：
   T11a SUB-SPLIT-DONE 标记卡 → 豁免（无 [VA-SKIP] comment、无 .json 注册、源 H 不报）；
   T11b 双向 done 子卡+VERIFIED（复刻 t_1db58772 链挂法）→ 豁免；
   T11c 真 no-claim 反例（无任何容器证据）→ 仍留痕 + 源 H 仍报（验收 2 反例不丢）；
   T11d 源 H 历史 [VA-SKIP] no-claim comment 残留 + 卡已容器化 → 豁免不报（验收 1 核心）；
   T11e seen 幂等重跑不重复报 + T1-T10 计数锚点零回归；
   + 全量回归（test_va_backfill 46+新 + test_watchdog_unify T1-T9 + test_wip_progress_check T1-T23
   + bash -n ×2）+ 部署验证（oc_wake_check.sh repo↔live md5 审计，部署留 OC）。
   预计 17-25 轮
```

- SPLIT: yes（count=2，校准后 32-49 轮远超 20 阈值；单卡 76-117% 预算不可行）
- MODE: serial（SUB-2 断言 SUB-1 行为，需 SUB-1 合并进 main）
- ROUNDS_EST（校准后）: 32-49（基准 13-20 × K=2.45；分卡后每张 15-25 / 17-25）
- FILES: pipeline/discover.py（改）+ scripts/oc_wake_check.sh（改）+ scripts/test_va_backfill.sh（增）——3 文件
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_f3108dfd）
- TESTS: SUB-1 冒烟 3-4 断言；SUB-2 T11 约 6-8 断言 + 三套全量回归（46+28+94）
- RISK: R1 双向查找半径；R2 历史 comment 残留（源 H 卡级判据）；R3 seen 幂等；R4 fail-open 反例；
  R5 部署验证（must-sync，部署留 OC）
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_f3108dfd]，serial）

## 6. 备注

1. **部署验证规则**（DPL-048）：oc_wake_check.sh 是 cron 前置脚本（jobs.json 直调 + stuck_check.sh:58
   引用）→ 验收标准必须含「diff/md5 比对 repo 版 vs /root/.hermes/profiles/orchestrator/scripts/
   同名文件 → 一致才 PASS」。研发只交 repo 正本；merge 后 deploy-drift 源 G 报自身漂移为预期
   （R2 自引用悖论），OC 部署平息。discover.py 非 cron 直调 → 不适用 must-sync。
2. 验收 1 的 seen 键处置：推荐「验证逻辑本身」——源 H 卡级判据修复后 t_1db58772 直接豁免
   （L525 continue），skip_count 冻结、键不更新、不再产出新行；旧键 `va-skip:t_1db58772:18`
   无害残留（与 DPL-069 处置同款）。
3. 修复方案优先级（供 SUB-1 裁决）：[SUB-SPLIT-DONE] 标记判据（最简单，t_1db58772 实测 3 条）>
   双向 done 子卡+VERIFIED 兜底（防手工关闭/无标记场景）；禁止「任意兄弟卡存在即豁免」的全局
   放水（R4 掩盖真 no-claim）。
4. QA 卡（容器豁免全量验证）由 OC 按 QA 流程另建，不在本 [SUB-SPLIT] 内。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张 [DEV-SUB] 卡执行。
