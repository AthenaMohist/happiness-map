# 工作量评估 — t_1713c90c（DPL-150 heartbeat 双显示 bug）

> 评估卡 t_est_1713c90c · 方案 C · 实察基线 main 228f261

## 1. 源需求实察

### Bug 复现路径（代码层确认）
notify_check.py 双显示根因是**两个渲染区数据口径不一致**：

- **✅✅ 完结区**（`done_today_chain_entries` L1155 / `chains_done_today_groups` L1134 / `group_dev_chains` L1114）：分组数据源是 `read_dev_chain_cards`（L384）返回的 dev_cards —— **只收标题 [DEV-*] 的链卡**。模拟卡 t_92f586f5 标题 `[TEST]` 不入 dev_cards，DPL-149 编号分组内全部 done → 误判「今日完结链」→ 出 `✅✅ DPL-149 ...` 行。
- **活跃区**（`_render_gai_chain_lines` L1492）：数据源是链对象 `ch["cards"]`（含链内所有卡，含 running 模拟卡）→ `_chain_is_all_done`（L1960）因存在 running 卡返回 False → 树形活跃渲染，且正确把 running 卡画为 `(未登记)` 节点。

即：**链分组/完结判定层（group_dev_chains 族）看不见非 DEV 前缀的子卡，渲染层看得见** → 同一链两区各渲染一次。

### 源卡修向对照
1. 「链活跃判定纳入 descendants」——对应实察：完结判定必须覆盖链下全部后代卡（不限 [DEV-*] 前缀），任一 running/ready/blocked → 整链按活跃渲染。改点在 `chains_done_today_groups` / `done_today_chain_entries`（或其卡集合入参），不动 `_chain_is_all_done` 本体（它已被活跃区正确使用）。
2. 「活跃树中 done 父链段保留 ✅ 状态」——`_render_gai_chain_lines` 主链节点已按 GAI 权威口径渲染 done 节点 ✅，只需确认 done 父链段不再额外吐单行 ✅✅ 摘要（即去重逻辑），渲染函数本体小改或不改。
3. 「行为级 fixture」——tests/test_notify_gai_b2.py 已有 39 用例框架，新增「done 父链 + running 子卡」fixture，断言 ✅✅ 区 0 行 + 活跃树 1 次出现。

## 2. 工作量估算

| 项 | 轮数 |
|---|---|
| 复现 fixture 编写 + 确认 bug（红） | 1-2 |
| 分组/完结判定层修（descendants 纳入 + ✅✅ 去重） | 1-2 |
| 行为级用例 + 回归（b1 36 / b2 39+新增 / dpl145_f3_f5 8） | 1-2 |
| dry-run 实版验证 + finalize/claim | 1 |
| **合计** | **4-7 轮** |

## 3. 复杂度与风险

- **复杂度：中低**。单文件（notify_check.py）单层（链分组/判定），渲染函数本体不动（符合硬约束）。
- **风险点**：
  - `read_dev_chain_cards` 只收 [DEV-*] 卡是 arch-fix-notify-heartbeat-chain-scope 的职责收窄设计（ADR），修复不得推翻该收窄——应在分组/判定层补后代卡可见性（如复用链对象 cards / kanban children），而非放宽 dev_cards 采集口径。
  - 既有对账 AC「✅✅ 行数 == chains_done_today」必须保持同口径（`group_dev_chains` 是共享函数，两处消费，改一处即两处同步）。
  - `_chain_is_all_done` 语义被 b1/b2 多用例依赖，禁止改其签名/语义。
  - [TEST]/非 DEV 前缀卡挂链属新形态（本次 OC 亲手造），回归时确认正常 DEV 链不受影响。

## 4. 决策

总估算 **4-7 轮 ≤ 20** → **[SUB-SPLIT] 1 不拆**，单卡串行完成。
