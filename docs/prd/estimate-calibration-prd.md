# PRD — 评估算法校准机制（子卡超时→预估偏差反馈→自适应）

> 作者：许清楚（产品负责人） | 日期：2026-08-13 | 版本：v1.0
> 来源：[CMD] 指令卡通道（Frank 2026-08-13 裁定：拆过的子卡还超时 = 评估不准确，要调整评估算法）
> 议题：DPL-018 评估算法校准机制（子卡超时→预估偏差反馈→自适应）
> 定位：评估拆卡机制（estimate-split-cards，t_a23ff810 已交付）的**反馈闭环补全**。拆卡机制解决了「执行前拆分」，本 PRD 解决「拆了还超时怎么办」——把超时变成评估算法的训练信号。
> 北极星对齐：Frank 不需要反复说"这个任务怎么又超时了"。拆卡机制上线后，超时从「执行问题」变成「规划问题」；本 PRD 让规划本身会学习——每次子卡超时都自动反哺评估口径，评估一次比一次准，超时一次比一次少。

---

## 0. 本 PRD 在整体规划中的定位

```
评估拆卡机制（已交付 t_a23ff810） — [DEV-EST] 评估卡 → [SUB-SPLIT] N serial|parallel → 自动建子卡
智能跳步（已交付 t_7b2781ec）    — 产物驱动裁剪（--skip dev-est 等）
独立 dev 卡拆卡保障（已交付 DPL-020）— discover 层拦截 + [SUB-SPLIT] 触发器按住源卡
本 PRD（DPL-018）                — 给拆卡机制装「仪表盘」：预估→实际→偏差→校准
```

**一句话定位**：现在评估卡给"拆 N 张 + 每张预计轮数（口头）"，子卡超时了系统**无感知**（DPL-016-A1 拆后仍 60/60 超时就是实证）。本 PRD 要求：① [SUB-SPLIT] 每子卡**结构化带预估轮数**；② 子卡超时自动采集**实际轮数**生成**偏差记录**；③ 下次评估卡生成时**注入历史偏差**让评估模型主动校准；④ 连续超时**强制触发校准提示**。

---

## 1. 背景与痛点

### 1.1 现状：评估只给方向，不给标尺

评估拆卡机制（estimate-split-cards）的完整链路：

```
[DEV-EST] 评估卡（不写代码，只评估）
  ├─ 产出 docs/est/<task>-estimate.md（评估报告）
  ├─ 写 [SUB-SPLIT] N serial|parallel comment（结构化建议）
  └─ autopilot 解析 → 建 N 张 [DEV-SUB-*] 子卡（或 1 张 [DEV-DEV]）
```

现状缺口（Frank 2026-08-13 裁定原文归纳）：
1. **预估无结构化记录**：评估卡虽然口头写了"预计 10-12 轮"（如 MEM-003 评估），但 [SUB-SPLIT] comment 解析（`_parse_sub_split`）**只取 count/mode/titles，丢弃轮数** → 预估数字不进系统、不可比对。
2. **无实际轮数反馈**：子卡执行完成后，实际消耗轮数没有采集。`task_runs` 有 outcome（timed_out/gave_up/completed）+ 时长，但没有与预估比对的机制 → 预估准不准，系统永远不知道。
3. **超时后无校准**：实测 DPL-016-A1（t_15a3982c）是拆出来的子卡，仍 60/60 超时两次（评估"预计 10-12 轮" vs 实际 60 轮，偏差率 ~+500%）——但系统无感知、无记录、下次评估照旧。拆卡治标，评估失准治不了本。

### 1.2 与 Frank 需求映射

| Frank 裁定/要求 | 现状 | 本 PRD |
|----------------|------|--------|
| "拆过的子卡还超时，说明评估不准确，要调整评估算法" | 子卡超时后系统无感知，无偏差数据 | 超时自动采集 → 偏差记录落库（预估 vs 实际） |
| "每子卡必须带预估轮数" | [SUB-SPLIT] 只解析 count/mode/titles，预估轮数被丢弃 | `_parse_sub_split` 扩展：每子卡解析 `预计 X-Y 轮` 结构化字段 |
| "评估卡生成预估时，读历史偏差 → 预估 = 基准 × (1+累计偏差率)" | 评估 prompt 无历史偏差上下文 | 评估卡 body 注入最近偏差记录 + 累计偏差率 + 校准系数 |
| "偏差记录在下次评估卡生成时自动注入 prompt" | 无反馈闭环 | discover `_create_est_card` + cmd_chain dev-est body 双入口注入 |
| "子卡连续超时（如 2 次）→ 强制触发评估校准提示" | 无阈值联动 | 连续超时检测 → prompt 顶部 ⚠️ 强制校准横幅 |
| "拆卡阈值 20 轮保持不变" | EST_SPLIT_THRESHOLD_ROUNDS=20 | **阈值不动**，只加偏差反馈与校准提示（产品红线：阈值是 Frank 确认的参数，不随本 PRD 改动） |

### 1.3 现状盘点（已具备的基础，直接继承）

| 基础设施 | 位置 | 状态 |
|----------|------|------|
| [SUB-SPLIT] 解析 | cmd_chain.py `_parse_sub_split` L551 / `_read_sub_split` L596 | ✅ 已有，待扩展 |
| 子卡创建 | cmd_chain.py `_create_dev_sub_cards` L665 / `_create_qa_sub_cards` | ✅ 已有 |
| 拆卡阈值 | constants.py `EST_SPLIT_THRESHOLD_ROUNDS = 20` L92 | ✅ 已有，不动 |
| 评估卡生成（链卡） | cmd_chain.py `_dev_card_body` L476-494（dev-est 步骤 prompt） | ✅ 已有，待注入 |
| 评估卡生成（独立卡） | discover.py `_create_est_card` L199-233 | ✅ 已有，待注入 |
| 超时事实数据 | kanban.db `task_runs`（status/outcome/error/started_at/ended_at） | ✅ 已有（error 含 "Iteration budget exhausted (60/60)"） |
| 超时标记消费先例 | notify_check.py L1147-1157 读 task_runs timed_out/gave_up → ever_timed_out | ✅ 已有（证明读 task_runs 是成熟模式） |
| 管线状态库 | pipeline_state.db（pipeline_steps/chain_config/task_control） | ✅ 已有，偏差表可落这里 |

---

## 2. 目标与范围

### 2.1 核心目标

1. **[SUB-SPLIT] 结构化预估**：每子卡必须带预估轮数（`预计 X-Y 轮`），可解析、可落库、可比对
2. **超时反馈采集**：子卡 timed_out/gave_up 时自动生成偏差记录（预估 vs 实际，偏差率），幂等落库
3. **评估算法自适应**：下次评估卡生成时注入历史偏差（最近记录 + 累计偏差率 + 校准系数），评估模型看到历史预测偏差主动校准
4. **阈值联动**：EST_SPLIT_THRESHOLD_ROUNDS=20 不变；连续超时 ≥2 次 → 强制校准提示
5. **全链路可测**：解析/采集/系数/注入均有测试用例，test_cmd_channel.sh 全绿回归

### 2.2 覆盖范围

| # | 范围 | 现状 | 改动 |
|---|------|------|------|
| 1 | [SUB-SPLIT] 解析 | count/mode/titles | + 每子卡 estimates[{min,max}] |
| 2 | 偏差数据 | 无 | 新表 est_deviation（pipeline_state.db） |
| 3 | 偏差采集 | 无 | cmd_channel tick 段扫描 task_runs → 匹配子卡 → 生成偏差记录 |
| 4 | 评估 prompt | 无历史上下文 | dev-est 卡 body 注入「历史偏差校准」段（链卡 + 独立卡双入口） |
| 5 | 校准系数 | 无 | 纯函数 calc_calibration_factor（滚动窗口 + 截断保护） |
| 6 | 连续超时联动 | 无 | 检测 → prompt ⚠️ 强制校准横幅 |
| 7 | 测试 | test_cmd_channel.sh 现有 T26-T31/T39/T42-T46 | 新增偏差采集 + 自适应计算用例 |

### 2.3 定义：什么是"偏差记录"与"累计偏差率"

**偏差记录**（est_deviation 一行）= 一次子卡超时事件的可审计反馈：
- `sub_task_id`：超时的子卡 id（[DEV-SUB-*]/[DEV-QA-SUB-*]）
- `est_card_id`：来源评估卡 id（从子卡 body「评估卡 <id>」解析）
- `spec_hash`：链标识（子卡幂等键 dev-<hash>-dev-sub-N 解析）
- `sub_idx`：子卡序号（1..N）
- `estimate_min / estimate_max`：该子卡预估轮数区间（来自 [SUB-SPLIT] 每子卡字段）
- `actual_rounds`：实际轮数（timed_out/gave_up → 解析 error "Iteration budget exhausted (X/Y)" 取 X；解析失败取 max_turns=60）
- `deviation_rate`：偏差率 = (actual − estimate_mid) / estimate_mid，estimate_mid=(min+max)/2；下偏（actual<min）为负
- `outcome`：timed_out / gave_up
- `retry_count`：同一子卡重复超时次数（首次超时建记录，后续同卡超时只 +1，不重复建行）
- `created_at`

**累计偏差率** = 最近 10 条（按 created_at 倒序）偏差记录 deviation_rate 的**中位数**（鲁棒，防单次极端超时污染；样本 <3 时退化为均值；无样本 → 0）。
**校准系数 K** = 1 + 累计偏差率，截断保护 clamp 到 [0.5, 3.0]（产品红线：防止极端数据把预估系数推到荒谬值；下偏最低打到 0.5 防止拆卡阈值被无限放宽）。
**调整后预估** = round(基准 × K)，基准 = 评估卡原始预估（est_mid）。

**连续超时** = 最近 10 条偏差记录（按 created_at 倒序，含 retry_count 合并后的独立子卡）中，不同子卡超时次数 ≥2（不同 spec_hash 也算，反映评估算法整体失准）。

---

## 3. 非目标（明确不做）

| # | 不做 | 理由 |
|---|------|------|
| N1 | 不改 EST_SPLIT_THRESHOLD_ROUNDS=20 | Frank 确认的参数，产品红线；本 PRD 只加反馈不调阈值 |
| N2 | 不机械强制改预估数字 | 校准走「prompt 注入 + 系数建议」，最终预估由评估模型决策（评估卡是研发自评，裁定"自评自己工作量，合理"）；机械覆写是 P1 增强（E-9） |
| N3 | 不采集已完成卡的精确轮数（P0） | task_runs 对 completed 无轮数列，唯一可靠信号是超时 error；完成卡轮数采集需 [CLAIM] 结构化字段联动（P1 E-8） |
| N4 | 不改 dispatcher / 内核超时逻辑 | 60 轮预算、timed_out 归档、gave_up 重试都是内核语义，仓库外不可改；本 PRD 只消费 task_runs 数据 |
| N5 | 不做评估质量看板（P0） | 偏差数据先落库；可视化/汇总通知属 P1（E-10） |
| N6 | 不追溯历史超时 | 只采集本 PRD 上线后的超时事件；历史超时（t_15a3982c 等）作为 fixture 种子，不补采 |

---

## 4. 需求清单（按优先级）

### P0 — 反馈闭环 MVP（核心）

| ID | 需求 | 内容 | 验收要点 |
|----|------|------|---------|
| E-1 | [SUB-SPLIT] 每子卡预估轮数 | `_parse_sub_split` 扩展：每个子任务行支持 `预计 X-Y 轮` / `预计 X 轮`（X≤Y，均可选下限/上限）→ split["estimates"] = [{min,max}, ...]；无轮数 → estimates 为 None（该子卡不采集偏差，不报错）。评估 prompt（cmd_chain L476-494 + discover L220-233）同步写明格式要求 | 解析单元测试覆盖：有区间/单值/缺省/混杂行；estimate 与 titles 按序号对齐 |
| E-2 | est_deviation 表 | pipeline_state.db 新增表 est_deviation（字段见 §2.3）；`UNIQUE(sub_task_id)` 幂等（每子卡首次超时一条记录，后续 retry_count+1）；表缺失 → fail-open（采集跳过，不阻塞主流程） | schema 建表 + 幂等验证（同一子卡重复超时只一行，retry_count 递增） |
| E-3 | 偏差采集 | cmd_channel tick 新增采集段（或独立函数 collect_est_deviations）：扫 task_runs 新 timed_out/gave_up → 找子卡（idempotency_key 含 `-sub-` 或标题 [DEV-SUB-*]/[DEV-QA-SUB-*]）→ 解析子卡 body 取 est_card_id → 读评估卡最新 [SUB-SPLIT] comment 取该子卡预估 → 算偏差率 → upsert est_deviation。采集只读 kanban.db、只写 pipeline_state.db | 构造 task_runs 超时行 → 偏差记录落库（预估/实际/偏差率正确）；重复 tick 不重复建行；非子卡超时（[CMD] 等）忽略 |
| E-4 | 校准系数纯函数 | 新增 calc_calibration_factor(records, window=10) → (factor, cum_rate, timeout_count)：中位数（样本<3 退化均值）+ clamp [0.5, 3.0]；连续超时检测（最近 10 条不同子卡超时 ≥2 → timeout_flag=True）。纯函数，无 IO，可单测 | 单元测试：空记录 → factor=1.0；全超时 → factor=3.0（截断）；全下偏 → factor=0.5（截断）；混合窗口统计正确；timeout_flag 触发条件正确 |
| E-5 | 评估 prompt 注入历史偏差 | dev-est 卡 body（cmd_chain `_dev_card_body`）+ 独立评估卡 body（discover `_create_est_card`）均新增「历史偏差校准」段：最近 5 条偏差记录摘要（子卡/预估/实际/偏差率）+ 累计偏差率 + 校准系数 K + 校准建议（`预估轮数 = 基准 × (1+累计偏差率)`，示例计算）+ timeout_flag 时顶部加 `⚠️ 连续超时，必须校准` 横幅。无记录 → 段省略（不干扰首次评估） | 有偏差记录 → body 含校准段与系数；无记录 → body 不含校准段；⚠️ 横幅仅在 timeout_flag 时出现 |
| E-6 | 自适应系数生效（子卡 body 注入） | `_create_dev_sub_cards` 建子卡时：若该 spec_hash 已有 est_deviation → 子卡 body 新增「预估轮数（含校准）: N 轮」（N = round(基准 × K)，基准取该子卡 [SUB-SPLIT] 预估 mid）；无历史偏差 → 不加该行（子卡 body 与现有一致）。**拆卡决策仍以原始预估为准，不机械改拆法**（Frank：阈值不变） | 有偏差 → 子卡 body 含校准后预估 = round(基准×K)；无偏差 → body 无该行（T27/T28 不回归） |

| E-7 | 测试 | test_cmd_channel.sh 新增：① 解析扩展（T31 扩展 + 新用例）② 采集落库 + 幂等 ③ calc_calibration_factor 单测 ④ prompt 注入断言（建评估卡 body 含校准段 / 无记录不含）⑤ 子卡 body 校准注入断言 ⑥ 回归 T1-T55 全绿 | 新增断言 ≥15；存量全绿；跑测时间不显著增加（<6 min） |

### P1 — 增强（MVP 之后）

| ID | 需求 | 内容 | 验收要点 |
|----|------|------|---------|
| E-8 | 完成卡轮数采集 | [CLAIM]/[PRODUCES] comment 支持 `轮数: N` 结构化字段 → completed 子卡也生成偏差记录（actual=N）；无该字段 → 不采集（fail-open） | 完成卡带轮数字段 → 偏差记录落库；不带 → 无记录不报错 |
| E-9 | 机械自适应（可选） | 校准后预估自动参与拆卡判定：评估卡声明预估 P，校准后 P' = P × factor；P' > 20 且原 P ≤ 20 → prompt 额外提示"校准后超阈值，建议拆更细" | 提示出现条件正确；仍不机械改拆卡结果 |
| E-10 | 偏差看板 | notify_check.py heartbeat 附注/阶段摘要增加一行：近 7 天评估偏差（条数 + 累计偏差率 + 连续超时 flag） | Frank 可见评估质量趋势；≤80 字格式约束内 |

---

## 5. 验收标准

### 5.1 判定公式对照（QA 标准 §1.2）

- **缺陷性质**：能力缺失（产品增强，非缺陷修复）。拆卡机制上线后子卡仍超时且系统无感知——按五步判定公式：问题存在（实测 t_15a3982c 60/60 两次）、用户可见（Frank 凌晨反馈拆卡后仍超时）、影响评估算法有效性（MAJOR 级能力缺口）。
- **分级判定**：不涉及安全漏洞；属功能能力增强，MAJOR 级（评估失准导致反复超时，直接消耗 Frank 的等待时间与系统配额）。
- **本 PRD 定位**：作为 MAJOR 级能力缺口的**方案文档**（SLA 8h 定位 + 24h 方案，已满足）。

### 5.2 验收用例

| # | 场景 | 前置 | 期望结果 |
|---|------|------|---------|
| AC-1 | [SUB-SPLIT] 带预估轮数 | 评估卡 comment：`[SUB-SPLIT] 2 serial\n1. [S1] 编号注入 预计 8-10 轮\n2. [S2] drift 扩展 预计 12-14 轮` | `_parse_sub_split` 返回 estimates=[{8,10},{12,14}]，与 titles 序号对齐 |
| AC-2 | [SUB-SPLIT] 无轮数（兼容旧格式） | comment 只有 `[SUB-SPLIT] 2 serial\n1. 甲\n2. 乙` | 解析成功，estimates=None；建子卡行为与现有一致（T27/T28 不回归） |
| AC-3 | 子卡超时 → 偏差记录 | task_runs 有子卡 t_x timed_out，error "Iteration budget exhausted (60/60)"；评估卡 [SUB-SPLIT] 预估 8-10 | est_deviation 新增一行：est=8-10, actual=60, deviation_rate=(60-9)/9≈5.67, outcome=timed_out |
| AC-4 | 采集幂等 | 同一子卡再次超时（gave_up 重试） | 不新增行，retry_count 1→2 |
| AC-5 | 非子卡超时忽略 | [CMD] 卡 timed_out | 不产生偏差记录 |
| AC-6 | 校准系数 | 最近 10 条偏差率均为 +5（超时） | factor=3.0（clamp 上限）；timeout_flag=True |
| AC-7 | 校准系数（无数据） | est_deviation 空 | factor=1.0，timeout_flag=False |
| AC-8 | prompt 注入 | est_deviation 有 3 条记录 | 新建 dev-est 卡 body 含「历史偏差校准」段：最近记录摘要 + 累计偏差率 + 校准系数 K + 建议公式 |
| AC-9 | prompt 注入（无数据） | est_deviation 空 | body 不含校准段（首次评估不被噪音干扰） |
| AC-10 | 连续超时横幅 | timeout_flag=True | body 顶部出现 ⚠️ 强制校准横幅 |
| AC-11 | 子卡 body 校准注入 | est_deviation 有记录（偏差率中位数 +50% → K=1.5）；[SUB-SPLIT] 预估 8-10（mid=9） | 新建子卡 body 含「预估轮数（含校准）: 14 轮」（round(9×1.5)=14） |
| AC-12 | 子卡 body 校准注入（无数据） | est_deviation 空 | 子卡 body 无校准行，与现有一致（T27/T28 不回归） |
| AC-13 | 阈值不变 | 任意场景 | EST_SPLIT_THRESHOLD_ROUNDS 仍 = 20（常量未改） |
| AC-14 | fail-open | pipeline_state.db 缺失/表不存在 | 采集跳过、不抛异常、不阻塞 cmd_channel 其余 tick 逻辑 |
| AC-15 | 回归 | 全量 test_cmd_channel.sh | 存量断言全绿（T1-T55 + 新增） |

### 5.3 SLA 对照（QA 标准 §8）

- MAJOR 级能力缺口：8h 定位 + 24h 方案（本 PRD 即方案，完成于 2026-08-13）

---

## 6. 约束

| # | 约束 | 来源 |
|---|------|------|
| C1 | EST_SPLIT_THRESHOLD_ROUNDS=20 不改 | Frank 2026-08-12 确认参数，产品红线 |
| C2 | 采集只读 kanban.db、只写 pipeline_state.db | 与 B1/notify 数据流隔离原则一致 |
| C3 | fail-open：任何采集/注入失败不阻塞主流程、退出码 0 | B1 设计约束 |
| C4 | 校准走 prompt 注入，不机械改预估（P0） | 评估卡=研发自评裁定（不设复核） |
| C5 | 子卡超时判定只依赖 task_runs（status timed_out/gave_up + error） | 内核语义，仓库外不可改，消费不修改 |
| C6 | 兼容旧 [SUB-SPLIT] 格式（无轮数不得解析失败） | 存量评估卡/测试不回归 |
| C7 | dev-est 可被 --skip dev-est 跳过（智能跳步） | t_7b2781ec 已交付语义不回退 |
| C8 | 时间基准：created_at 用 UTC（与 task_runs 一致）；展示口径由 notify 层处理 | 口径一致性 |

---

## 7. 待 Frank 裁决（2 项）

| # | 点 | 建议 |
|---|-----|------|
| D1 | **完成卡是否也要采集偏差（P1 E-8）？** 超时反馈是 P0（可靠信号）；完成卡的精确轮数需要 [CLAIM] 加 `轮数: N` 字段（跨角色约定，涉及 SOUL.md/worker 行为），成本更高 | 建议 P0 只做超时反馈；E-8 排 P1，等 P0 上线后看超时率是否改善再定 |
| D2 | **校准系数是否允许 <1（下偏校准）？** 若评估总是高估（实际 << 预估），系数 <1 会让拆卡更不积极（更多卡走单卡硬跑） | 建议 clamp 下限 0.5（允许温和下偏，但不无限放宽）；激进下偏（实际 < 预估一半）仍保留拆卡决策权给评估模型 |

---

## 8. 工时估算

| 模块 | 工时 |
|------|:---:|
| E-1 [SUB-SPLIT] 解析扩展 + 评估 prompt 格式说明 | 1.5h |
| E-2 est_deviation 表 + schema | 0.5h |
| E-3 偏差采集段（cmd_channel tick 钩子 + 匹配 + upsert） | 2h |
| E-4 calc_calibration_factor 纯函数 | 1h |
| E-5 双入口 prompt 注入（cmd_chain + discover） | 1.5h |
| E-6 子卡 body 校准注入 | 1h |
| E-7 测试（新增 ≥15 断言 + 回归） | 1.5h |
| **P0 合计** | **9h** |
| P1 E-8 完成卡轮数采集 | 2h |
| P1 E-9 机械自适应提示 | 1h |
| P1 E-10 偏差看板 | 1.5h |
| **P0+P1 合计** | **13.5h** |

---

## 9. 交付物

| 交付物 | 路径 |
|--------|------|
| 本 PRD | `docs/prd/estimate-calibration-prd.md` |
| （后续）实现 | pipeline/cmd_chain.py + pipeline/discover.py + pipeline/constants.py（只读引用）+ scripts/cmd_channel.sh + scripts/test_cmd_channel.sh |
| （后续）数据 | pipeline_state.db 新表 est_deviation |

---

## 附：与本 PRD 相关的既有文档

- 拆卡机制设计：`docs/design/estimate-split-cards.md`（Frank 2026-08-12 提出）
- 智能跳步设计：`docs/design/smart-skip-steps.md`（t_7b2781ec）
- 独立 dev 卡拆卡保障：`docs/arch/arch-fix-standalone-dev-subsplit.md`（DPL-020）
- 本议题早期 PRD（v4 草案，源于已删除卡 t_c767d4c2 的孤儿分支，供实现参考）：`docs/prd/est-calibration-loop-prd.md`（commit 68f29e7，未合 main，内容与本文档基本一致，本 PRD 为准）
- 超时实证案例：t_15a3982c（拆后仍 60/60 超时×2）、t_40ec4bde（未拆硬跑 60/60 超时×2）
- 评估报告样例（含 ROUNDS_EST 约定）：`docs/est/t_22a98abb-estimate.md` / `docs/est/t_40ec4bde-estimate.md`
- task_runs 超时标记消费先例：`scripts/notify_check.py` L1147-1157（ever_timed_out）
