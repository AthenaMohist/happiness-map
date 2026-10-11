# 评估报告 — [FIX] heartbeat 卡链 3 链上限截断（blocked 链 + 全 done 当天链被砍）

> 评估人：寇豆码（game-engine） | 日期：2026-08-13 | 评估卡：t_est_f6047701
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）
> 源卡：t_f6047701（[FIX] heartbeat 卡链 3 链上限截断 — blocked 链被 running 挤掉 + 全 done 当天链不显示）
> 来源：Frank 2026-08-13 现场反馈（① MEM-008 blocked 不见；② 今天 0 点后完成的全 done 链不显示）

## 1. 结论（TL;DR）

**不拆，单卡可完成（预计 9-13 轮 ≤ 20 轮阈值）。**

改动集中在 `scripts/notify_check.py` 单个函数 `format_chain_visual`（L1521-1592，约 70 行），
根因已在源卡实锤（L1574 总 5 行上限 + L1577 `chain_count >= 3` 硬上限 + 优先级排序把 blocked(3)/全 done(4) 挤掉）。
修复 = 分组渲染（active[:3] + blocked 全显 + done[:3]）+ 溢出提示 + 2-3 例新测试 + 存量 68 例回归。
无跨模块改动、无新文件依赖、无共享常量冲突 → 单卡 60 轮预算内余量充足。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **1 个代码文件 + 1 个测试文件**：scripts/notify_check.py（format_chain_visual 分组渲染）+ scripts/test_notify_check.py（新增 2-3 例） | 源卡修复方案；grep 确认无其他调用方依赖链数上限 |
| 现状基线 | 存量 68 个 test 函数（test_notify_check.py，t1-t68），当前全绿；最近 heartbeat 相关修复刚落地（0be0d45 任务编号 + 5a63105 blocked 优先归并） | grep 计数 `^def t\d+_` = 68；git log |
| ① 分组渲染 | 把 items（链 + 独立卡）按状态分组：active（running/ready 链 + 活跃独立卡 📍，最多 3 条）→ blocked（blocked 链 + blocked 独立卡，全部显示）→ done（全 done 当天链 ✅✅，最多 3 条）。组内复用现有 `_render_chain_line`/`_status_emoji`/`_tag_of_title`，`line[:80]` 截断保留。约 20-30 行重构 | 源卡修复方案 + L1552-1592 现状 |
| ② 总行数上限协同 | 现 L1574 `len(lines) >= 5` 与分组后的上限（3+N+3）冲突，需调整：倾向总上限提到 9（active3 + blocked≤3 + done3）+ 消息级 `line[:500]` 截断兜底；blocked 组在总预算内优先占用名额 | L1574 + L1614 `return line[:500]` |
| ③ 溢出提示 | done_lines 超出 3 条 → 追加"…等N条"（N = 被截断的全 done 链数） | 源卡修复方案明确要求 |
| ④ 新测试 | T69：3 running + 1 blocked + 1 全 done 链场景 — blocked 链必现、全 done 链必现（Frank 反馈①②直接验收）；T70：done 溢出显示"…等N条"；T71：blocked 多链全显 + 排序不变式（活跃在上、done 在下，T58/T59 回归锚点） | 源卡验证要求；复用 Fixture().install() 模式 |
| ⑤ 回归 | 存量 68 例全绿。经 grep 确认**无测试断言 3 链上限**（无"最多 3"“等N条”等字样），T47/T58/T59/T60 断言行序/精简行/blocked 优先，分组后语义均保持 → 预计 0-2 例断言微调（若有） | grep 全测试文件 0 命中上限断言；读 T47/T58/T59/T60 |
| ⑥ 收尾 | commit + [PRODUCES] claim + 飞书推送 | 常规 |

**预计轮数：9-13 轮**（① 3-4 + ② 1 + ③ 1 + ④ 2-3 + ⑤ 1-2 + ⑥ 1-2）≤ 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| 总行数上限与分组冲突 | **中（关键决策点 D1）** | 现 5 行上限 vs 分组后上限 3+N+3。源卡示例输出恰为 5 行（3 active + 1 blocked + 1 done），但 blocked 全显 + done 3 条同时多时会超。倾向：总上限提到 9（active3 + blocked≤3 + done3），blocked 组在总预算内优先；配合 `line[:500]` 截断兜底，不会刷爆飞书。需实现时确认，不改变轮数上限 |
| 独立卡（standalone）分组归位 | 中 | 活跃独立卡（📍 running/ready）归 active 组、blocked 独立卡归 blocked 组。T58 断言"活跃独立卡在全 done 链之前"仍满足；实现时注意 blocked 独立卡与 blocked 链的相对顺序（同组内按 _created_at 排序，与现逻辑一致） |
| 存量测试回归 | 低 | 无测试断言 3 链硬上限 → 重构不会被存量用例锁死；唯一微调风险是 T58/T59 若独立卡组顺序变化（预计 0-2 例断言） |
| 附带发现 scope 控制 | 低 | compute_chain_counts done_today 口径（ADR-2 已裁定，Frank 若仍嫌数字不对再单独评估）+ MEM-008 重复节点（tail_extra）——源卡标注"不强制"，**本次明确不做**，防止 scope 膨胀 |
| 消息长度 | 低 | 分组后最多 9 行 × 80 字符 ≈ 720 字符，但 `format_heartbeat` L1614 `line[:500]` 会截断；9 行内实际可控，blocked 全显场景需观察是否触发截断（若截断需确认截断发生在哪一行） |

**关键决策点（实现时需拍板，均不改变轮数上限）**：
1. **D1 总行数上限**：5 → 9（推荐：active3 + blocked≤3 + done3，blocked 优先占额）；或保持 5 但 blocked 组先占名额。倾向 9 + 500 字符兜底。
2. **D2 溢出文案**：`…等N条`（N=截断条数），与源卡方案一致。
3. **D3 blocked 独立卡**：与 blocked 链同组同序（_created_at），不另起一行。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | 9-13 轮 ≤ 20 轮阈值 → **不拆** |
| 模块依赖 | 单函数改动，无跨模块依赖、无共享常量、无多文件冲突面 |
| 并行收益 | 无必要——函数级改动拆卡只会引入上下文切换成本 |
| 兜底 | 即使超预算，分组渲染本身是原子改动，一次性 commit 即可交付，无半成品风险 |

**决策：不拆（[SUB-SPLIT] 1），单卡直接完成。** 与同系列 t_3e00306b（8-13 轮，单函数 + 5 组测试）量级一致。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
1. [DEV-DEV] heartbeat 卡链 3 链上限截断修复（game-engine，单卡）：
   format_chain_visual 分组渲染 active[:3] + blocked 全显 + done[:3]（…等N条）
   + 总行数上限 5→9 + 新测试 T69（blocked 必现 + 全 done 必现）/T70（溢出提示）
   /T71（blocked 多链 + 排序回归）+ 存量 68 例全绿。预计 9-13 轮。
   依赖：无（独立修复卡，源卡 t_f6047701 已含完整方案）
```

- SPLIT: no（count=1，单卡可完成）
- MODE: single
- ROUNDS_EST: 11
- FILES: scripts/notify_check.py, scripts/test_notify_check.py
- STATUS: not_started（源卡 t_f6047701 待 dev 实现）
- TESTS: 存量 68 例 PASS 基线；新增 T69-T71 共 3 例
- RISK: D1 总行数上限决策（5→9）；standalone 分组归位；0-2 例存量断言微调；附带发现明确不做
- ACTION: build_one_dev_card（assignee=game-engine）

## 6. 备注

- 根因已实锤（源卡提供 L1572-1582 复现），实现无需再定位，直接从分组渲染改起。
- 与最近两次 heartbeat 修复（0be0d45 任务编号、5a63105 blocked 优先归并）同文件不同区域，无冲突。
- 源卡"附带发现"两项（done_today 口径 / MEM-008 重复节点）按源卡标注不强制，本次不纳入；
  若渲染修复后 Frank 仍反馈数字不对，另开评估卡单独处理。
- 本评估卡不写代码；autopilot 读取 [SUB-SPLIT] comment 后建 1 张 [DEV-DEV] 卡执行。
