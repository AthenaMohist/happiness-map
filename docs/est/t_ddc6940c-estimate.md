# 评估报告 — [FIX] heartbeat work-gate 吞掉当天完成全 done 链 — active=False 也推 ✅✅ 直到 0 点

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_ddc6940c
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_ddc6940c（[FIX] heartbeat work-gate 吞掉当天完成全 done 链 — active=False 也推 ✅✅ 直到 0 点）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后预计 36-54 轮 > 20 轮阈值）。**

任务本质是**改 notify_check.py heartbeat 的一个分支门**：数据层（`read_active_cards_with_chain`）
**已经实现了规则 c 和 DPL-025 standalone _done_today**（L1381-1399 / L1400-1428），缺的只是
heartbeat 推送路径的 work-gate（L2307 `if active and ...`）在 IDLE 时不调用它。修复 = 把
gate 扩成「active **或** 存在当天完成的全 done 链/独立 done 卡 → 推一次 heartbeat」+ 冷却去重，
**不新增数据层逻辑**。但验收 3 要求 4 组 fixture 场景（a/b/c/d）覆盖 + 全量回归（test_notify_check
341 + test_cmd_channel 387），按 DPL-018 校准系数 K=3.00 折算后总量 > 20 轮阈值，必须拆卡。
自然边界：S1 = 机制（gate 改造 + 冷却去重），S2 = 测试（4 fixture 场景 + 回归 + 落地）。

**评估期间实测基线**（2026-08-15 03:0x）：`test_notify_check.py` PASS=341 FAIL=0（T1-T95，
本改动直接回归套件）；`test_cmd_channel.sh` 387（t_ccee095c 02:20 claim 实证，源卡写的 386
为 T15-T18 前快照）；`test_wip_progress_check.sh` 62。数据层与测试 harness 均已就绪，无新表/新 harness。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **~2 个文件**：scripts/notify_check.py（heartbeat gate 改造 ~30-50 行）、scripts/test_notify_check.py（+4 fixture 场景 ~80-140 行断言）。**无新增文件、无新增表、无新增 harness** | 实测根因在 notify_check.py L2307 `if active and heartbeat_cfg.get("enabled", True) and not in_silent_window(cfg):`；L2331-2332 `elif not active: log("IDLE: 无活跃任务，不推 heartbeat")`。测试 harness（Fixture 类 + run_tick + check + seed_kanban_dev_chain/seed_kanban_task/done_today_epoch）已在 test_notify_check.py L80-330 全量就绪，T90-T95 已是同款 fixture 模式 | 
| ① 数据层复用（零新增） | read_active_cards_with_chain（L1133-1433）已实现：规则 c `_chain_completed_today`（L1121-1130）过滤全 done 当天链；DPL-025 standalone `_done_today`（L1400-1428，条件 `last_wake_at is not None` + `completed_at >= today_start`）。**无需改数据层** | 实测 L1390-1399 链过滤三规则（a 未完成 / b 本次唤醒新建 / c 全 done 当天）；L1409-1428 standalone 独立卡并入逻辑完整 |
| ② gate 改造（核心改动） | 把 L2305-2332 从「if active → 推」改为「if (active or _has_done_today_visual(...)) and enabled and not silent → 推」：IDLE 时也调 read_active_cards_with_chain（传入 dev_cards + last_wake_epoch + cfg），判 `any(_chain_completed_today(ch, today_start) for ch in chains) or any(s.get("_done_today") for s in standalone)`；满足 → format_heartbeat + feishu_send + **冷却去重**；不满足 → 原 IDLE 日志。**冷却键 = 日期作用域**（推荐 `hb\|done_today\|<YYYY-MM-DD>` 走 notify_events cooldown_active/mark_sent_hash 或 kv 水位 `done_today_hb_date`）：同一天只推一次，第二天 0 点后规则 c 自然失效 → 自动消失（验收 2 零额外工作） | 实测 L2322-2330 活跃路径已调用 read_active_cards_with_chain + format_heartbeat + mark_sent_hash；cooldown_active/mark_sent_hash（L1898-1950）现成机制。last_wake_at 在 L2111-2112 首跑初始化，此后永不为 None → standalone _done_today 条件恒满足 |
| ③ 测试（4 fixture 场景） | test_notify_check.py 追加 T96-T99（或 T96+）：(a) 全 done 链完成当天 + 无活跃 → IDLE 仍推含 `✅✅ <链名>` 的 heartbeat；(b) 同一天第二次 tick → 不重复推（冷却键命中，断言 sent 数不变）；(c) 链完成于昨天 / completed_at < today_start → 不推（0 点后消失语义）；(d) 有活跃任务 → 行为不变（原 heartbeat 照推，且不被冷却键误伤）。+ 幂等断言（冷却键写入 notify_events/kv 后重跑不推）。另需回归确认 T2-3/T2-4（IDLE 停推）、T17（昨日 done IDLE 静默）、T47/T51/T55、T90-T95 不被破坏 | 实测 T90（done_today_epoch + seed_kanban_task + run_tick 后断言 `✅✅ [编号]`）就是 (a) 的活模板；T2（L364-407）用 pipeline 活跃/空闲断言 heartbeat 门；T17（L853-874）昨日完成断言静默。harness 三件套（today_start_epoch/done_today_epoch/run_tick）L310-330 现成 |
| ④ 全量回归 | test_notify_check.py 341 + test_cmd_channel.sh 387 + test_wip_progress_check.sh 62 + bash -n ×1（notify_check.py 非 shell）+ py_compile | t_ccee095c claim 实证三套数字；本评估实测 test_notify_check 341/0 |
| ⑤ 收尾 | 自身分支 merge 进 main + 结构化 claim + [PRODUCES] comment + 飞书推送 + kanban_complete | 落地铁律：禁卡 done 代码留 worktree；SOUL 5.1 飞书硬性要求 |

**基准轮数（未校准）：12-18 轮**（① 2-3 + ② 3-4 + ③ 4-6 + ④ 1-2 + ⑤ 2-3）。
**DPL-018 校准：基准 × K=3.00 → 校准后 36-54 轮**（取中位 45）> 20 轮阈值。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **冷却去重键设计（最大决策点）** | 中 | 「同一天只推一次」需要日期作用域键。**键 = `hb\|done_today\|<本地日期>`**（notify_events event_hash 或 kv_store 水位）→ 同一链当天完成只推一次，验收 b 满足。**若用链作用域键**（每链一个 hash）→ 同一天第二条链完成会再推一次，虽然语义也说得通（新增完成信息），但与「0 点后消失」的日语义不一致，且可能一天推 N 次。**推荐日期键**；若产品希望「每条新完成的链都推送」，改用链+日期复合键（`hb\|done_today\|<date>\|<root_id>`），两条路线在 S1 内定稿（D1） |
| R2 既有断言回归（T2/T17/T47/T51/T55/T90-T95） | 中 | T2-3/T2-4 断言「IDLE 后不再推 heartbeat」——本改动语义上**必须保持**：T2 fixture 只 seed pipeline_steps 不 seed kanban 链卡 → IDLE 时无 done-today 链 → 不推，天然不破。T17（昨日 done）→ 规则 c False → 不推，不破。**风险点**：T47/T51/T55 是「全 done 链显示」类用例，若其 fixture 用了 done_today_epoch 且走 ACTIVE 路径，改动不触碰 active 分支 → 不破。仍需全量跑 341 确认（S2 必做） |
| R3 last_wake_at 语义交互 | 低-中 | IDLE 路径读 last_wake_epoch 来自 kv `last_wake_at`（上次唤醒时刻，可能陈旧）。规则 c 只看 today_start 不看 last_wake_at（L1121-1130 独立）；standalone _done_today 要求 last_wake_at 非 None（首跑已初始化，L2111-2112）→ **恒满足**。陈旧 last_wake 只会影响规则 b（本次唤醒新建），不阻塞 done-today 显示。S1 冒烟验证即可 |
| R4 silent_window / enabled 门复用 | 低 | 需求 1 说「也必须要推一次 heartbeat（含 ✅✅）」，未提 silent_window。推荐**沿用同一组门**（enabled + not in_silent_window）保持一致；若 silent_window 配置了夜间静默，0 点后本就不推 → 与验收 2 天然一致。D2 决策点，S1 定稿 |
| R5 IDLE 日志语义 | 低 | 原 `elif not active: log("IDLE: 无活跃任务，不推 heartbeat")` 只在「无 done-today」时打；有 done-today 时打新日志「IDLE 但存在当天完成链 → 推 done-today heartbeat」。notify_cron.log 观测语义变化，无脚本依赖该字符串（实测无 grep 引用） |
| R6 全量回归 | 低 | notify_check.py 改动只增分支不删逻辑；test_notify_check.py 只增 T96+ 不动既有断言 → 341 基线不回退。test_cmd_channel.sh / test_wip_progress_check.sh 不涉及 notify_check → 387/62 理论不动，必须复跑确认 |
| R7 自身落地自引用 | 低 | S2 改的测试文件与 notify_check.py 都要进 main → 与源卡约束 5 一致；fixture 用隔离 temp DB（Fixture 类 tempfile.mkdtemp）不触碰真实 board |

**关键决策点（S1 实现时拍板，不改轮数量级）**：D1 冷却键作用域（推荐日期键 `hb\|done_today\|<date>`；备选链+日期复合键）；
D2 silent_window 门是否沿用（推荐沿用）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 12-18 轮（中位 15） |
| DPL-018 校准后 | 36-54 轮（×K=3.00，中位 45）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（gate 机制）→ S2（4 fixture 断言 + 回归）单向依赖：S2 的 fixture 断言 S1 改后的 heartbeat 行为 |
| 并行收益 | 低——S2 测试断言 S1 的函数行为，天然串行 |
| 兜底 | 每张子卡独立验收闭环：S1 交付 gate 改造 + 冷却去重（验收 1/2 可验）；S2 交付 4 fixture 场景 + 全量回归（验收 3/4 可验）。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。** 量级参照：t_14fb6a11（5 文件 + 386 回归 → 拆 2 serial）、
t_e6b787f1（2-3 文件 + 3 fixture → 拆 2 serial）；本卡改动面更小（2 文件、数据层零新增），但 4 fixture
场景 + 341 断言回归需要 S2 独立成卡。拆 2 卡后每卡 18-27 校准轮，均在单会话可控区间（42 有效轮）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] heartbeat done-today 推送 S1 — notify_check.py gate 改造 + 冷却去重（机制）
   （L2305-2332：把「if active → 推 heartbeat」扩为「if (active or 存在当天完成的全 done
    链/独立 done 卡) and enabled and not silent → 推」；IDLE 时也调 read_active_cards_with_chain
    （dev_cards + last_wake_epoch + cfg），判 any(_chain_completed_today) or any(_done_today)；
    满足 → format_heartbeat + feishu_send + 冷却去重（推荐日期键 hb|done_today|<YYYY-MM-DD>
    走 cooldown_active/mark_sent_hash 或 kv 水位）；不满足 → 原 IDLE 日志；S1 内先定 D1 冷却键
    作用域 / D2 silent_window 门；冒烟 = test_notify_check.py 341 全绿 + 手写 1 个隔离 fixture
    验证 IDLE 推 ✅✅） 预计 7-9 轮
2. [DEV-SUB-2] heartbeat done-today 推送 S2 — 4 fixture 场景 + 全量回归 + 落地
   （test_notify_check.py 追加 T96-T99（复用 Fixture harness + done_today_epoch）：
    (a) 全 done 链当天 + 无活跃 → IDLE 仍推含 ✅✅ 的 heartbeat（断言消息含 ✅✅ <链名>）；
    (b) 同一天第二 tick → 不重复推（冷却键命中，sent 数不变）；
    (c) completed_at 昨天 / < today_start → 不推（0 点后消失）；
    (d) 有活跃任务 → 行为不变（原 heartbeat 照推，冷却键不误伤）；
    + 幂等重跑断言；回归确认 T2-3/T2-4、T17、T47/T51/T55、T90-T95 不破；
    全量 test_notify_check 341 + test_cmd_channel 387 + test_wip_progress_check 62；
    S2 自身分支 merge 进 main + claim + 飞书 + complete） 预计 9-12 轮
```

- SPLIT: yes（count=2，校准后 36-54 轮远超 20）
- MODE: serial（S2 测试断言依赖 S1 的 gate 行为在 main 上存在）
- ROUNDS_EST（校准后）: 45（基准 15 × K=3.00）
- FILES: S1 改 scripts/notify_check.py（gate + 冷却 ~30-50 行）；S2 改 scripts/test_notify_check.py（+4 fixture 场景 ~80-140 行）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂 t_ddc6940c）
- TESTS: S1 test_notify_check.py 341 全绿 + 冒烟 1 fixture；S2 4 fixture 场景（~12-20 断言）+ 全量 341 + 387 + 62
- RISK: R1 冷却键作用域（D1 日期键 vs 链+日期复合键）；R2 既有断言回归（T2/T17/T47/T51/T55/T90-T95 全量确认）；R3 last_wake 陈旧只影响规则 b 不影响 done-today；D1/D2 S1 内定稿
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_ddc6940c]，serial）

## 6. 备注

- **根因与数据层已分离**：规则 c（L1381-1389）和 standalone _done_today（L1400-1428）是**已实现且带测试**的
  数据层能力（T90-T95 实证）；本 FIX 只缺推送路径的 gate。因此 S1 不含任何数据层改动，风险集中在
  「gate 分支语义」与「冷却键」两处，都可在 S1 冒烟内闭环。
- **0 点后自动消失零额外工作**：`_chain_completed_today` 用 `local_today_start_epoch(cfg)`（本地时区
  今天零点）比较 completed_at；跨天后 today_start 前进 → 规则 c 变 False → 不再推 → 消息自然消失。
  验收 2 是规则语义的既有性质，不需新增「过期清理」代码。
- **冷却键与「同一天多条链」**：验收 b 只要求「已推过的不重复推」；日期键（D1 推荐）会把当天所有
  done-today 链合并成一条 heartbeat（首推时已含全部），后续新完成的链当天不再单独推——若产品希望
  「每条新完成链都推」，改链+日期复合键即可，S1 内定稿。
- **测试命名沿用 T 序号**：当前 test_notify_check.py 最后一个用例 T95（L3526），新增从 T96 起，
  避免重号；`main()` 的调用列表同步追加。
- **实现复用现有机制**：format_heartbeat / feishu_send / cooldown_active / mark_sent_hash /
  local_today_start_epoch / _chain_completed_today 全部现成，S1 是「组合」不是「新写」。
- **本评估卡不写代码**；autopilot 读取 [SUB-SPLIT] comment 后建 2 张 [DEV-SUB-*] 卡（parents 链按 serial 挂接）。
- 每张子卡完成后推飞书（send_claim_feishu.py，SOUL 5.1 硬性要求）。
