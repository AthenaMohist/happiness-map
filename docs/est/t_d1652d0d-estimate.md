# 评估报告 — [FIX] va_backfill R3 漏检 — claim JSON file_modified 产物不触发 VA 补扫（DPL-033）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_d1652d0d
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_d1652d0d（[FIX] va_backfill R3 漏检 — claim JSON file_modified 产物不触发 VA 补扫）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后预计 27-48 轮 > 20 轮阈值）。**

任务本质是**一个判定函数的 OR 扩展**：`_latest_claim_has_changed_files`
（discover.py L1066-1086）现只认 body 含 `**changed_files**` 字面段，需扩展为
「`**changed_files**` **或** claim JSON 段含 `"type": "file_modified"` /
`"type": "file_created"`（claim schema 1.0）」。改动面极小（1 函数 ~10-15 行），
但配套工作不可省：防回归 fixture（验收 3）、全量回归（验收 4：va 37 + number 33）、
t_ddc6940c 漏检卡补建（验收 3）、进 main 落地（验收 5）。
自然边界：S1 = 机制 + fixture 测试（含自身 merge），S2 = 全量回归 + 漏检卡补建 + 收尾。

**评估期间实测**（2026-08-15 上午，本 worktree wt/t_est_d1652d0d @ 1109615）：
- **根因实证**：t_ddc6940c 的 [PRODUCES] claim（2026-08-15 03:14）body 无
  `**changed_files**` 字面段，但 JSON 段含 3 个 `"type": "file_modified"` 产物
  （c1 notify_check.py / c2 test_notify_check.py / c3 wip 笔记）+ 3 个 test_passed——
  现判定 False → 跳过补建，漏检链路与源卡描述完全一致。
- **引用面实证**：`grep -rn _latest_claim_has_changed_files` 全仓仅 2 处——
  定义（discover.py L1066）+ 唯一调用点（L1130，process_va_backfill 循环内）。
  零外部引用 → 改动波及面封闭在 va_backfill 路径内。
- **基线实测**：test_va_backfill.sh PASS=37 FAIL=0（T1-T7）；test_number_backfill.sh
  PASS=33 FAIL=0（同为 R3 检测类机制，D2 窗口/排除/幂等同构，必须一起回归）。
- **补建窗口**：t_ddc6940c completed_at=03:14（1786734876），评估时刻 ≈6.1h 后
  → 在 24h 窗口内；但 autopilot 休眠中（02:16 起），va_backfill 不 tick →
  窗口内不会自动补建，S2 需手工补建或届时实证已建。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **2 个文件**：pipeline/discover.py（`_latest_claim_has_changed_files` L1066-1086 改 ~10-15 行）、scripts/test_va_backfill.sh（+T8 fixture 块 ~40-70 行）。无新文件、无新表、无新 harness | 实测函数体 L1074-1086 现为单条件 `return "**changed_files**" in (row["body"] or "")`；测试 harness（隔离 temp DB + seed_task/seed_claim + run_scan/q1/rj）L20-149 全量现成，第二批 fixture（L207-242）即「后置 seed 不扰先批计数」的活模板 |
| ① 机制改动（S1 核心） | 判定改 OR 双条件：body 含 `**changed_files**`（兼容现有格式，37 断言里的正例格式）**或** 含 `"type": "file_modified"` / `"type": "file_created"` 子串（claim schema 1.0 JSON 段）。**子串匹配而非 json 解析**——claim body 是 markdown 内嵌 json 块，json.loads 需先抠代码块，解析失败会误判 False（fail-closed 违反需求 4）；字面子串匹配稳定且 schema 1.0 的 `"type": "file_xxx"` 键值排版标准化。docstring 同步更新（含双条件说明） | 实测 t_ddc6940c claim JSON：`{"id": "c1", "type": "file_modified", "target": ...}`——键值间冒号+空格标准化（claim-schema skill 模板产出），子串 `"type": "file_modified"` 命中；file_created/file_modified 是 schema 8 类中仅有的两个文件系统产物类型，test_passed/git_pushed 等不是代码产物（源卡需求 1 已拍板只扩这两类） |
| ② fixture 测试（S1） | test_va_backfill.sh 追加 T8（第三批 fixture，T6 后 T7 前 seed，避免扰动 T1a 计数 4 / T5b 总数 5 / T6 各窗口断言）：(a) done 卡 claim 只含 JSON file_modified 无 changed_files 段 → **必须补建**（断言 created 含新卡 + idem_key=va-backfill-<tid> + parents=源卡 + assignee=verifier——防回归核心）；(b) claim 只含 JSON file_created → 同样补建；(c) claim 只含 test_passed 类型 JSON（无 file_*）→ 仍跳过（范围控制，防 OR 扩过头）；(d) 既有负例 t_src_skip（无 changed_files 无 JSON）→ 行为不变（已在 T1b/T4 覆盖，确认不破） | 实测 T1a 断言 N_CREATED=4、T1b skipped=1、T5b VA 卡总数=5——第三批后置 seed 则这三处不需改；若实现者选并入 batch 1 则须同步改 T1a 4→6、T5b 5→7（D3 决策点，推荐后置） |
| ③ S1 自身验证 + merge | bash -n（改的是 .py 无需）→ py_compile discover.py → 本地跑 test_va_backfill.sh 全绿（37+新增 ~6-10 断言）→ grep 验收 1（`grep -n 'file_modified\|changed_files' pipeline/discover.py` 双条件可见）→ wt 分支 commit → merge --no-ff 进 main（引用本卡/源卡 ID） | 落地铁律：禁卡 done 代码留 worktree；单函数改动 merge 冲突风险≈0（number_backfill 链 1109615 已进 main，discover.py 改动区域 L1066-1086 与其 L1180+ 不重叠） |
| ④ 全量回归（S2） | main 上复跑 test_va_backfill.sh（37+新增）+ test_number_backfill.sh（33）双绿；test_cmd_channel.sh 387 与本改动无交集（源卡验收 4 只要求前两者，387 可选跑作加强） | 本评估实测两套基线 37/0、33/0；改动只增不删 → 既有断言理论不受影响，必须复跑确认 |
| ⑤ 漏检卡补建（S2） | 查 t_ddc6940c verifier 子卡（kanban_show/devppl_query）：已存在（autopilot 醒后自动补建过）→ 记录实证即完；不存在 → 手工补建 `va-claim: t_ddc6940c`（kanban_create，assignee=verifier，parents=[t_ddc6940c]，idem_key=va-backfill-t_ddc6940c，body 对齐 discover.py L1141-1152 补扫文案） | 实测 t_ddc6940c children=[] 无 verifier 子卡；completed 6.1h 前（<24h 窗口内）但 autopilot 休眠 → 自动路径不可达，手工补建是确定性路径（源卡需求 2 明示授权） |
| ⑥ 收尾（S2） | S2 自身 merge（若 S2 有 wip 笔记等产物）+ [PRODUCES] claim（JSON，**必须含 changed_files 段**——本漏检的教训闭环）+ 飞书推送 + kanban_complete | SOUL 5.1 硬性要求；验收 5 |

**基准轮数（未校准）：9-16 轮**（① 1-2 + ② 1-2 + ③ 2-3 + ④ 1-2 + ⑤ 1-2 + ⑥ 2-3）。
**DPL-018 校准：基准 × K=3.00 → 校准后 27-48 轮**（取中位 38）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 OR 扩展破坏既有断言 | 低 | 只增不删：含 `**changed_files**` 的 claim 行为不变（T1 正例仍建）；无 changed_files 且无 file JSON 的仍 False（T1b skipped=1、T4 t_src_skip 不破）。全量复跑确认即可 |
| R2 **fixture 放置扰动计数** | 低-中 | 新 fixture 若并入 batch 1（L116-149），T1a 的 N_CREATED=4、T5b 的 VA 总数=5 都要同步 +N，且 T6 的 H=1/H=3 扫描会连带拾取新 fixture（completed_at=now 必在 H=3 窗口内）→ 断言耦合面大。**推荐第三批后置 seed**（T6 后 T7 前，仿第二批 L207 模式）：T1-T7 既有断言零改动，T8 独立 scan 独立断言。D3 决策点，S1 内定稿 |
| R3 匹配精度（误报/漏报） | 低 | 子串 `"type": "file_modified"` 在 claim body 中只可能来自 claims[].type（schema 1.0 语义唯一）；file_created 同理。风险侧反而是**过窄**：worker 手写 claim 若用单引号/无空格排版（`"type":"file_modified"`）会漏——但 schema 1.0 模板产出标准化，且这是 fail-open 语义（漏检顶多不建卡，不误建）。D1 决策：是否同时兼容无空格变体 `"type":"file_modified"`（推荐兼容，成本一行） |
| R4 test_passed 不触发 | 低 | 源卡需求 1 已拍板只扩 file_modified/file_created。test_passed/git_pushed 等非文件系统产物（如 t_ddc6940c c4-c6）不触发建卡——语义正确，fixture (c) 锁死该边界防未来 OR 扩过头 |
| R5 **t_ddc6940c 补建时序** | 低-中 | autopilot 休眠中 va_backfill 不 tick；24h 窗口（03:14+24h = 次日 03:14）内若 autopilot 唤醒会自动补建（修复进 main 后）。S2 执行时先查：已建 → 实证记录；未建 → 手工 kanban_create（idem_key 对齐机制，幂等：若机制后续也建，kernel idem 防重）。两路径都确定性可验 |
| R6 merge 冲突 | 低 | discover.py 与 number_backfill 链（1109615 已进 main）同文件不同区域（L1066-1086 vs L1180+）；S1 从最新 main 拉分支即可。test_va_backfill.sh 无并发改动方 |
| R7 自身落地自引用 | 低 | S1 改的 discover.py + test_va_backfill.sh 都要进 main（验收 5）；S1 的 [PRODUCES] claim 本身要含 changed_files 段 + JSON 双保险（正好同时命中新旧两种检测——机制的活正例） |

**关键决策点（S1 实现时拍板，不改轮数量级）**：D1 匹配串形态（推荐双变体兼容：
`"type": "file_modified"` 与 `"type":"file_modified"`）；D2 检测范围沿用「最新一条
[CLAIM]/[PRODUCES]」（现 ORDER BY 语义不变）；D3 fixture 放置（推荐第三批后置 seed）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 9-16 轮（中位 13） |
| DPL-018 校准后 | 27-48 轮（×K=3.00，中位 38）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（机制 + fixture + 自身 merge）→ S2（main 复跑回归 + 补建 + 收尾）单向依赖：S2 的回归与「机制在 main 上」强绑定，S2 的补建验证依赖 S1 已进 main |
| 并行收益 | 低——S2 回归断言 S1 在 main 上的行为，天然串行 |
| 兜底 | 每张子卡独立验收闭环：S1 交付双条件判定 + T8 fixture + 自身 merge（验收 1/2 可验）；S2 交付全量回归绿 + t_ddc6940c 补建/实证（验收 3/4 可验）+ 收尾。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。** 量级参照：t_ddc6940c（heartbeat
gate 同为「1 函数 OR 扩展 + fixture + 回归」形态，基准 12-18 → 拆 2 serial）。本卡改动面
更小（1 函数 vs 1 gate + 冷却水位），但多了「漏检卡补建」半（R5）→ 同构拆 2。拆后每卡
校准 12-27 轮，均在单会话可控区间（42 有效轮）。警示先例：t_ddc6940c 单 run 实际
60/60 轮耗尽（虽交付完成）——校准 36-54 的卡压单会话已是极限，本卡 27-48 不赌。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] 机制 — _latest_claim_has_changed_files OR 双条件 + T8 fixture
   （discover.py L1066-1086：判定从单一 `**changed_files** in body` 扩展为 OR——
    body 含 **changed_files**（兼容现有 37 断言正例）或含 "type": "file_modified" /
    "type": "file_created" 子串（claim schema 1.0 JSON 段，D1 兼容无空格变体；
    子串匹配不 json 解析——解析失败会 fail-closed 违反需求 4）；docstring 同步；
    test_va_backfill.sh 追加 T8 第三批 fixture（T6 后 T7 前 seed，不扰 T1a=4/
    T5b=5 计数）：(a) claim 只含 JSON file_modified 无 changed_files → 必须补建
    （idem_key/parents/verifier 断言，防回归核心）；(b) 只含 file_created → 补建；
    (c) 只含 test_passed JSON → 仍跳过（范围控制）；(d) 负例 t_src_skip 行为不变；
    py_compile + 本地 test_va_backfill 全绿（37+新增）+ grep 验收 1 双条件可见；
    S1 自身 merge --no-ff 进 main） 预计 5-9 轮
2. [DEV-SUB-2] 回归 + 补建 + 落地 — 全量双套回归 + t_ddc6940c VA 补建
   （main 复跑 test_va_backfill.sh（37+新增）+ test_number_backfill.sh（33）双绿
    （验收 4）；查 t_ddc6940c verifier 子卡：无且 autopilot 仍休眠 → 手工
    kanban_create va-claim: t_ddc6940c（assignee=verifier，parents=[t_ddc6940c]，
    idem_key=va-backfill-t_ddc6940c，body 对齐 discover.py L1141-1152）；已有 →
    实证记录（验收 3）；[PRODUCES] claim 必须含 **changed_files** 段 + JSON
    双格式（本漏检教训闭环）+ 飞书推送 + complete；worktree 无残留（验收 5））
    预计 4-7 轮
```

- SPLIT: yes（count=2，校准后 27-48 轮超 20 阈值）
- MODE: serial（S2 回归/补建依赖 S1 机制已在 main）
- ROUNDS_EST（校准后）: 38（基准 13 × K=3.00）
- FILES: S1 改 pipeline/discover.py（~10-15 行）+ scripts/test_va_backfill.sh（+T8 ~40-70 行）；
  S2 无代码改动（回归 + kanban 建卡 + 收尾，可含 .pipeline/wip/ 发现笔记）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂 t_d1652d0d）
- TESTS: S1 py_compile + test_va_backfill 37+新增全绿 + grep 验收 1；S2 main 复跑
  test_va_backfill（37+新增）+ test_number_backfill（33）+ t_ddc6940c 补建实证
- RISK: R2 fixture 放置计数耦合（推荐第三批后置，D3）；R3 匹配变体（D1 双形态兼容）；
  R5 补建时序（autopilot 休眠 → 手工路径已授权）；R7 S1 claim 自身双格式正例
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_d1652d0d]，serial）

## 6. 备注

- **单函数改动为何仍拆**：改代码本身 1-2 轮，但验收链（fixture 防回归 + 双套全量回归 +
  漏检卡补建 + merge 落地 + claim 闭环）占大头；校准 27-48 轮压单会话有 60/60 超时先例
  （t_ddc6940c run 937 实际耗尽预算）。拆 2 后每卡 12-27 校准轮，安全边际充分。
- **与 number_backfill 机制的关系**：两者共享「窗口 + 排除 + 幂等 + fail-open」骨架但函数
  独立（process_va_backfill L1089 / process_number_backfill L1180+），本改动只碰前者；
  test_number_backfill.sh 回归是防 discover.py 级联破坏（同文件 import 面）。
- **fail-open 语义双向保持**：DB 异常 → False（现状，需求 4）；子串不命中 → False
  （fail-open 漏检不误建）。唯一的 fail-closed 风险来自 json 解析方案，已排除（D1 子串）。
- **S2 的 claim 是机制的活验证**：S1/S2 的 [PRODUCES] 若只写 JSON 不写 changed_files 段，
  本卡修好的机制应照样拾取——建议 S2 收尾时用自身 claim 做一次正例自证（R7）。
- **本评估卡不写代码**；autopilot 读取 [SUB-SPLIT] comment 后建 2 张 [DEV-SUB-*] 卡
  （parents=[t_d1652d0d] 串行挂接）。
- 评估期间实测基线：test_va_backfill.sh PASS=37 FAIL=0；test_number_backfill.sh
  PASS=33 FAIL=0（本 worktree @ 1109615，2026-08-15 上午）。
- 每张子卡完成后推飞书（send_claim_feishu.py，SOUL 5.1 硬性要求）。
