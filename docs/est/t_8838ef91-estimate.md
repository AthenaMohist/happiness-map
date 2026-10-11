# 评估报告 — 评估算法校准机制（子卡超时→预估偏差反馈→自适应，DPL-018）

> 评估人：寇豆码（game-engine） | 日期：2026-08-13 | 评估卡：t_8838ef91
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）
> 源卡：t_8838ef91（[DEV-EST] DPL-018 评估算法校准机制）
> 来源：PRD t_8db323af（commit 33bef7a，docs/prd/estimate-calibration-prd.md，245 行）+ 架构 t_0c52f9e3（commit 17c5076，docs/arch/arch-estimate-calibration.md，581 行）

## 1. 结论（TL;DR）

**P0 拆 2 张串行子卡（S1 数据平面 → S2 注入平面；每张预计 10-13 轮 ≤ 20 轮阈值）。P1 另卡，待 P0 上线后按超时率趋势排期。**

单卡 P0 预计 **18-24 轮**（中位 21）> 20 轮阈值，必须拆。拆点选在「数据平面 / 注入平面」天然接缝：
- **S1 数据平面**：est_deviation 表 + 偏差采集（collect_est_deviations + 游标 + upsert）+ 校准系数纯函数 + [SUB-SPLIT] 解析扩展（采集前置依赖）+ cmd_channel 段 7 挂载 + 测试 T59-T63
- **S2 注入平面**：prompt 三入口注入（cmd_chain/discover/backfill）+ 子卡 body 校准注入（dev+qa）+ 测试 T64-T69 + 全量回归

串行而非并行：cmd_chain.py 是 S1（parse）与 S2（body 注入）的共改文件，且 test_cmd_channel.sh 由两张卡分别追加 T59-T63 / T64-T69——并行双 worktree 必然 merge 冲突（t_40ec4bde 同款教训：共享文件串行规避）。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **6 个文件**：pipeline/calibration.py（新，8 函数）+ pipeline/cmd_chain.py（parse/body/子卡 4 处）+ pipeline/discover.py（_create_est_card + trigger 文案）+ pipeline/checkpoint.py（schema v4）+ scripts/cmd_channel.sh（段 7）+ scripts/test_cmd_channel.sh（T59-T69） | 架构 §2-§9；实测行号：cmd_chain.py L551/596/630/665/709/972、discover.py L199/335、checkpoint.py L13-51 |
| 现状基线 | 存量测试 T1-T58 全绿（test_cmd_channel.sh 1836 行）；cmd_channel.sh 六段结构（L465-730）；est_deviation 无表（pipeline_state.db 现 3 表） | 实测 schema + 测试文件尾部 T58；checkpoint.py SCHEMA_SQL |
| ① E-1 parse 扩展 | `_parse_sub_split` 增 estimates 键 + `_extract_estimate`（2 正则）+ 3 处 prompt 格式说明（cmd_chain L483-487 / discover L229 / trigger SQL L353-354）。新增正则 + 兼容旧格式 fail-open | 架构 §3.1/§3.2；cmd_chain.py L551-593 现只取 count/mode/titles |
| ② E-2 schema | est_deviation 表 DDL + migrate_v3_to_v4 + collect 侧 CREATE IF NOT EXISTS 兜底（cmd_channel 在 ensure_schema 之前跑） | 架构 §4.1；checkpoint.py L13-51 + autopilot.sh L55/L116 |
| ③ E-3 采集 | calibration.py collect_est_deviations（游标 est_calib_last_run_id + _collect_one 8 步匹配 + INSERT OR IGNORE/UPDATE retry_count）+ cmd_channel.sh 段 7 heredoc | 架构 §5.1-5.4；T57 已有 task_runs fixture 先例（test L1749-1755） |
| ④ E-4 系数 | calc_calibration_factor 纯函数（中位数/样本<3 均值/clamp 0.5-3.0/连续超时 flag） | 架构 §6，全文给出实现 |
| ⑤ E-5 注入 | build_calibration_context + render_banner/render_section + 三入口（cmd_chain advance L1151-1159 / discover _create_est_card / trigger 路径由 backfill_est_bodies 兜底） | 架构 §7；A4 关键发现：trigger 纯 SQL 无法跨库读 pipeline_state → backfill 补写 |
| ⑥ E-6 子卡注入 | calibrated_rounds + _sub_card_body 增参数 + _create_dev_sub_cards/_create_qa_sub_cards 注入（A5 局部门控 spec_hash/est_card_id） | 架构 §8；cmd_chain.py L630-662/L687-706/L726-744 |
| ⑦ E-7 测试 | T59-T69 共 11 组 ≥28 断言 + T31 扩展 + 全量 T1-T58 回归。fixture 构造：task_runs timed_out 行 + 子卡 body + [SUB-SPLIT] comment | 架构 §9 测试表；T57 fixture 模式可复用（test L1749-1755） |
| ⑧ 收尾 | commit + [PRODUCES] + 飞书推送 | 常规 |

**P0 单卡预计轮数：18-24 轮**（① 1-2 + ② 1 + ③ 4-5 + ④ 1-2 + ⑤ 3-4 + ⑥ 2 + ⑦ 5-7 + ⑧ 1-2）> 20 轮阈值。

**P1 单独核算（不进本次拆卡）**：E-8 完成卡采集 2h（约 3-4 轮）、E-9 机械自适应 1h（2 轮）、E-10 偏差看板 1.5h（2-3 轮）——按架构 D1 定稿「P0 只做超时反馈，P1 待 P0 上线后按超时率趋势排期」。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 跨库读写（只读 kanban / 只写 pipeline） | **中** | sqlite URI `file:...?mode=ro` 只读连接 + 写入侧 try/except fail-open；C2/C3 红线。架构 §5.2 已给伪代码，实现风险可控 |
| R2 _collect_one 8 步匹配 | **中** | 幂等键/body 正则多（idem `dev-<hash>-*-sub-N` + `discover-sub-<id>-<N>` + body「评估卡 <id>」「子卡 i/N」+ error 轮数）。T61-T63 fixture 构造成本高，是测试大头 |
| R3 backfill_est_bodies 竞态窗口 | 中 | trigger→claim <60s vs backfill 2min tick 的残留窗口（架构 A4 已接受：校准是 prompt 增强非正确性门）。实现需幂等 MARKER 防重写 |
| R4 测试文件共改冲突 | 中 | cmd_chain.py + test_cmd_channel.sh 是高频共改文件；串行拆卡规避（S2 parents=[S1]，S2 在 S1 合 main 后开跑） |
| R5 回归 fallout | 中 | 存量 T1-T58 269+ 断言；T27/T28 子卡 body 断言必须不回归（E-6 无数据不加行）；T31 需扩展（parse estimates）。全量单次 2-5 min，预计 3-5 次迭代跑测 |
| R6 本卡自证预言 | 低（警示） | **本卡就是 DPL-018 的活体样本**：DPL-018 立项证据 = 评估偏差 +500%（t_15a3982c 估 10-12 实际 60）。按本机制口径，6 文件 + 11 测试组 + 新模块的任务，单卡估 14-20 属历史低估区间 → 拆卡是机制的自我执行 |

**关键决策点（实现时需拍板，均不改变轮数上限）**：
1. **D1（沿用架构 A4）**：backfill 幂等用「body 含 MARKER 即跳过」，已 claim 的卡不补写。
2. **D2（沿用架构 A6）**：横幅=body 首行、校准段=dev-est 块末尾、无数据全省略。
3. **D3（新增，实现时确认）**：`_collect_one` 中 task_runs `id > 游标` 但 task 已 archived 的子卡——按 C5 只依赖 task_runs 语义，正常采集（任务卡 archived 不影响偏差落库）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 预计轮数 | P0 单卡 18-24 轮 > 20 轮阈值 → **拆** |
| 模块依赖 | S1 产出 est_deviation 表 + collect + calc + parse；S2 消费（注入/校准）→ 强依赖 |
| 串行收益 | S1 先落 cmd_chain.py parse 扩展 + schema，S2 直接消费；同文件/同测试文件零冲突 |
| 并行收益 | 无——cmd_chain.py 与 test_cmd_channel.sh 双卡共改，并行必 merge 冲突 |
| 兜底 | 即使 S2 超预算，S1（采集+落库）是独立可交付的数据平面，验收 AC-3/AC-4/AC-5 已覆盖；S2 注入是 prompt 增强（fail-open），任一完成均可部分交付 |

**决策：拆 2 张串行子卡。** 与同系列 t_40ec4bde（24-30 轮 → 拆 2，每张 10-14）量级一致；S1/S2 各 10-13 轮，均在 ≤20 轮阈值内且留足余量。P1（E-8/E-9/E-10）按架构 D1 定稿另卡排期，不并入本次。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [S1] DPL-018 数据平面：est_deviation 采集与系数计算（game-engine）
   a. pipeline/checkpoint.py：SCHEMA_SQL 追加 est_deviation 表 + migrate_v3_to_v4（PRAGMA user_version=4）
   b. pipeline/calibration.py（新）：collect_est_deviations（只读 kanban task_runs timed_out/gave_up
      → 游标 est_calib_last_run_id → _collect_one 8 步匹配 → INSERT OR IGNORE/UPDATE retry_count）
      + load_recent_records + calc_calibration_factor（中位数/clamp 0.5-3.0/连续超时 flag）
   c. pipeline/cmd_chain.py：_parse_sub_split 扩展 estimates 键（预计 X-Y 轮/预计 X 轮/旧格式兼容）
      + 3 处评估 prompt 格式说明（cmd_chain _dev_card_body L483-487 / discover _create_est_card L229
      / trigger SQL L353-354）
   d. scripts/cmd_channel.sh：段 7 偏差采集挂载（collect_est_deviations，fail-open，只写 pipeline_state.db）
   e. 测试：T59（parse 扩展）/T60（calc 纯函数）/T61（采集落库）/T62（幂等 retry_count）/T63（非子卡忽略）
   明确不做：prompt 注入、backfill、子卡 body 校准（归 S2）
   预计 10-13 轮。依赖：无（独立于现有在途分支）
2. [S2] DPL-018 注入平面：prompt 校准注入 + 子卡 body 校准（game-engine）
   a. pipeline/calibration.py：build_calibration_context + render_banner/render_calibration_section
      + backfill_est_bodies（trigger 路径兜底，幂等 MARKER）+ calibrated_rounds
   b. pipeline/cmd_chain.py：_dev_card_body 增 calibration 参数（横幅首行 + 校准段末尾）+ _sub_card_body
      增 calibrated_rounds + _create_dev_sub_cards/_create_qa_sub_cards 注入（spec_hash/est_card_id 门控）
   c. pipeline/discover.py：_create_est_card 注入校准段
   d. 测试：T64（链卡 prompt 注入）/T65（独立卡 + backfill 幂等）/T66（⚠️ 横幅）/T67（子卡 body 校准）
      /T68（无数据不注入 + 阈值不变 + fail-open）/T69（全量回归 T1-T58 + T31 扩展）
   明确不做：P1 E-8/E-9/E-10（完成卡采集/机械自适应/偏差看板，另卡）
   预计 10-13 轮。依赖：S1（est_deviation 表 + collect + parse 已合 main）→ parents=[S1]
```

- SPLIT: yes（count=2）
- MODE: serial（S1 → S2，共享 cmd_chain.py / test_cmd_channel.sh）
- ROUNDS_EST: 21（P0 单卡口径；S1 11 / S2 11）
- FILES: pipeline/calibration.py(新), pipeline/cmd_chain.py, pipeline/discover.py, pipeline/checkpoint.py, scripts/cmd_channel.sh, scripts/test_cmd_channel.sh
- STATUS: not_started（评估卡 t_8838ef91 待 autopilot 建子卡）
- TESTS: 存量 T1-T58 269+ 断言 PASS 基线；新增 T59-T69 共 11 组 ≥28 断言
- RISK: R1 跨库读写（fail-open）；R2 _collect_one 8 步匹配 fixture 成本；R3 backfill 竞态窗口（已接受）；R5 回归 fallout
- ACTION: build_two_dev_cards（S1/S2 均 assignee=game-engine；S2 parents=[S1]）

## 6. 备注

- 架构文档已给出函数级伪代码（collect/calc/context/render/backfill/calibrated/parse 全部有实现锚点），实现基本是「照写 + 接线」；风险集中在测试 fixture 构造与回归，不在算法本身。
- 本卡不写代码；autopilot 读取 [SUB-SPLIT] comment 后建 2 张 [DEV-SUB-*] 卡执行（S1 先派发，S2 等 S1 done 后自动 promote）。
- 与在途分支冲突面：cmd_channel.sh 段 7 追加在段 6 之后（L728 之前），与 DPL-019（SOUL 注入，改 cmd_chain.py 同区）可能重叠——merge 阶段预留手动解决时间。
- P1 排期建议：P0 上线后观测 2-3 个拆卡周期，若超时率未降再排 E-8/E-9/E-10；E-8 无 schema 变更（actual_rounds 字段已预留），随时可接。
