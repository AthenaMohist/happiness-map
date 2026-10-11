# 评估报告 — FIX watchdog 统一：oc_wake_check 吸收 stuck-15min/幽灵卡/main-dirty + 归档死脚本（DPL-061）

> 评估人：寇豆码（game-engine） | 日期：2026-08-16 | 评估卡：t_12539484
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：DPL-061（[CMD] 指令卡通道 t_b89e47b2，Frank 2026-08-11 裁定 2 类型化建链）
> 前置：PRD v1.0（t_34d696d5，done）+ ARCH v1.0（t_54b89425，done，17 项裁决 D1-D17 + 落地拆 2 serial 建议）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 3 张串行子卡（校准后总 70-106 轮 > 20 轮阈值 → 必须拆；交付物 5 个 → 按规则拆 ~3 卡）。**

DPL-061 是 devPPL 监控体系的收口：把「1 活宿主 + 1 违规挂载 + 2 死脚本」的 4 文件散装
统一为唯一宿主 oc_wake_check.sh 的 3 个新检测源（源 I 幽灵卡 / 源 J main-dirty / 源 K
stuck-long），死脚本里从未上线的能力救活上线，违规挂载的 infomanager cron 6b695ac1e290
迁移删除，4 个死脚本本体 git mv 归档。ARCH v1.0（562 行）已给出三源**完整代码块**
（§2.2/3.2/4.2 verbatim）+ seen 写回**精确改点**（§5.3 改点 1-4）+ 测试矩阵（T1-T9）
——实现主要是「落代码 + 接线 + 测试」，不是从零设计，这一点压低基准轮数。

**决策：3 serial（比 arch/PRD 的 2 serial 多拆 1 张）**——理由：arch 的 S1（机制 +
T1-T8 新测试套件 + 回归 + 首 tick）基准 19-29 轮 → 校准 49-75 轮，超出 42 有效轮预算；
按 DPL-018 近 10 条偏差记录（5/5 张子卡全部 60 轮 timed_out）实证，超预算卡大概率再超时。
机制代码（arch 已 verbatim，落代码即可）与 T1-T8 新测试套件（~300 行新文件，最大单项）
有清晰接缝，拆 3 后每卡校准 21-39 轮，均落在 42 有效轮预算内。

## 2. 工作量评估（读码结论 + 实测，非假设）

### 2.1 现状链路（读码核实）

```
宿主: scripts/oc_wake_check.sh（467 行，源 A-H，orchestrator cron f2aa32251adc 15m）
  底部 seen 写回（L425-446）:
    ① out 行自动解析 tag:tid 一次性键（A/B/C/D）
    ② 跳过名单 L438 ("code-not-in-main","merge-not-in-main","deploy-drift","va-skip")
    ③ *_new_keys 独立追加（E/G/H 状态型键 landing/drift/va_skip）
  源 I/J/K 落点: 源 H 块后、conn.close() 前（L422/423 之间，D9）
待归档: scripts/watch_board.sh（158 行）/ watch_dpl_chains.sh（82 行）/
        oc_stuck_watchdog.py（155 行）/ test_oc_stuck_watchdog.py（257 行）
待删 cron: infomanager 6b695ac1e290（5m，script=oc_stuck_watchdog.sh wrapper）
         → exec python3 /workspace/devPPL/scripts/oc_stuck_watchdog.py（D17 顺带清）
备份就绪: /workspace/SandboxHermesBackup/devppl-scripts-backup-20260816/
        （8 脚本 + README-BACKUP.md，tag backup-pre-watchdog-unify-20260816）
回归锚点: test_wip_progress_check.sh T14e/f（508 行）+ test_deploy_drift.sh T5a-h
        （175 行）+ test_va_backfill.sh T10c（571 行）+ test_cmd_channel.sh
        PRD-GATE-T6（2479 行，398 断言）+ devPPL pytest（基线 281/8/1）
```

- arch 给出源 I（~24 行）/J（~20 行）/K（~32 行）完整代码 + 写回改点 1-4（L438 元组加
  `"main-dirty"` + `main_dirty_new_keys` 声明/底部追加循环 + 头注释 A-H→A-K）——代码级
  落地工作量低，**关键是写回机制的精确性与测试覆盖**。
- 测试桥模式现成：test_deploy_drift.sh T5（L99-144）已实现「cp 真实 schema → DROP 触发器
  → DELETE 四表 → env 桩 + REPO_ROOT 作 $1」隔离模式，test_watchdog_unify.sh 直接照抄。
- 新测试套件是最大单项：T1-T8 覆盖 3 源 8 断言组（幽灵卡含 qa 前缀/archived/seen 幂等；
  main-dirty 含干净/集合变化/非 git fail-open；stuck-long 含未超阈值/B 重叠排除/seen 幂等）
  + fixture repo + seed_card，预估 ~250-350 行新文件。
- 源 K 首 tick 观察与 OC 删 cron（D8 ①②）依赖 15m 宿主 tick 与 OC 操作，dev 侧只能
  准备 + 记录，不能自证——S3 里这部分是「协调 + 留痕」而非「执行」。

### 2.2 交付物清点（5 交付物 → 拆 ~3 卡规则触发）

| # | 交付物 | 内容 | 文件 |
|---|--------|------|------|
| 1 | 引擎（R1/R2/R3） | 源 I/J/K 三块 + seen 写回改点 + 头注释 | oc_wake_check.sh |
| 2 | 测试（R5） | test_watchdog_unify.sh T1-T8 | 新文件 |
| 3 | 归档（R4） | git mv 4 文件 → scripts/archive/ + T9 | archive/ + test |
| 4 | 迁移集成（R4） | D8 顺序：源 K 验证 → OC 删 cron + 清 wrapper → 首 tick | profile + 记录 |
| 5 | 回归（R5） | 三套 oc_wake 测试 + cmd + pytest 全量 | 测试三件套 |

### 2.3 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | S1 机制代码 | oc_wake_check.sh 源 I（幽灵卡 §2.2）/J（main-dirty §3.2）/K（stuck-long §4.2）三块插源 H 后 conn.close 前（arch verbatim，D9）；§5.3 改点 1-4：L438 跳过名单加 "main-dirty" + main_dirty_new_keys 声明/底部追加循环 + 头注释 A-H→A-K + 幂等注释 | 4-6 |
| ② | S1 自验证 | 最小手工 fixture（temp kanban.db + fixture repo）验证三源输出含/不含；bash -n + python 语法自检；test_va_backfill T10c + test_deploy_drift T5 spot-check（seen 写回零回归） | 2-3 |
| ③ | S2 测试套件 | 新增 scripts/test_watchdog_unify.sh（env 桥 + fixture repo + seed_card，仿 test_deploy_drift T5）；T1-T3 幽灵卡 / T4-T5 main-dirty / T6-T8 stuck-long（§8.2 断言矩阵）；本地跑通全绿 | 7-10 |
| ④ | S2 回归 | test_wip_progress_check T14 + test_deploy_drift T5 + test_va_backfill T10 + test_cmd_channel PRD-GATE-T6 + devPPL pytest（§8.3 清单，只增不删锁） | 3-5 |
| ⑤ | S3 归档+迁移 | git mv watch_board.sh / watch_dpl_chains.sh / oc_stuck_watchdog.py / test_oc_stuck_watchdog.py → scripts/archive/（D5）；test_watchdog_unify.sh 追加 T9（archive 4 文件存在且非空）；全量回归（test_watchdog_unify T1-T9 + 三套 + cmd + pytest，D8 ④） | 4-6 |
| ⑥ | S3 落地 | D8 顺序留痕（① 验证源 K 线上输出 → ② OC 删 cron 6b695ac1e290 + 清 wrapper D17 → ③ git mv → ④ 回归）；首 tick 观察幽灵卡/main-dirty/stuck-long；[PRODUCES] claim（changed_files + JSON 双格式）+ 飞书推送 + complete | 3-5 |

**基准轮数（未校准）：27-41 轮（中位 34）。**
**DPL-018 校准：基准 × K=2.60 → 校准后 70-106 轮（中位 88）> 20 轮阈值 → 必须拆卡。**

### 2.4 校准后每卡轮数（拆 3 serial 后）

| 子卡 | 基准 | 校准（×2.60） | 42 有效轮预算内？ |
|------|:---:|:---:|:---:|
| S1 机制核心（①+②） | 6-9 | 16-23 | ✅ |
| S2 测试+回归（③+④） | 10-15 | 26-39 | ✅ |
| S3 归档+迁移+落地（⑤+⑥） | 7-11 | 18-29 | ✅ |

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **arch/PRD 建议 2 serial，本 EST 改 3 serial** | 低 | 差异仅拆法：arch 的 S1（机制+T1-T8+回归+首tick）基准 19-29 → 校准 49-75 轮 > 42 预算，按连续超时实证（5/5 张 60 轮 timed_out）大概率超时；机制代码（verbatim 落代码）与 T1-T8（~300 行新测试文件，最大单项）接缝清晰，拆 3 后每卡 ≤39 轮。拆卡粒度是 EST 职责，不改变功能范围（DPL-060 同款修正先例） |
| R2 seen 写回改点（D11） | 中 | 核心风险：`main-dirty` 必须进 L438 跳过名单 + 走 main_dirty_new_keys 独立写回——漏改则自动解析把文件名当 tid 写成一次性键 → 持续异常每 tick 刷屏（arch §5.2 反例警示）；回归红线：`ghost-card`/`stuck-running-long` **绝不能**进跳过名单。T4b/T5b/T8 seen 落盘断言锁死 |
| R3 源 J git 子进程 | 低 | fail-open（D15）：非 git 目录/超时/缺 git → 视为干净。test_deploy_drift T5 的 REPO_ROOT 是非 git 目录，此路必走；`except Exception` 覆盖 run 非零返回 + 抛异常两条路径 |
| R4 源 K 与源 B 重叠 | 低 | D3 排除 `hb_stale AND claim_dead`（B 优先）；B 在前天然满足；T7b 负例 fixture 锁死 |
| R5 源 I 一次性键吞持续异常 | 低 | PRD D1 裁定（防刷屏优先）；S1 首 tick 观察幽灵卡数留痕；若「报了没人管」后续可改状态型键（不在本卡范围） |
| R6 新测试套件 fixture 复杂度 | 中 | seed_card 直接 INSERT 需对齐 tasks 表全列（idempotency_key/started_at/last_heartbeat_at/claim_expires/workspace_kind 等）；fixture repo 需 git init + commit；断言「只增不删」——参考 test_deploy_drift T5 现成桥，照抄为主 |
| R7 全量回归破坏 | 中 | test_cmd_channel 398 断言 + devPPL pytest（~10min 后台）——只增不删 + 影响面分析（arch 0.3 事实 9-11）：源 I 零影响 / 源 J fail-open + contains 断言 / 源 K 无 running fixture；源 G 自引用悖论预期（oc_wake_check.sh 自身漂移 → merge 后 OC 部署平息） |
| R8 归档与 cron 竞态 | 低 | D8 顺序锁死：先删 cron 后归档（防 wrapper exec 报文件不存在直投飞书）；S2→S3 串行双轨窗口（源 K 随宿主输出 + cron 6b695 仍跑双保险）；wrapper 清理（D17）由 OC 顺手执行 |
| R9 备份丢失 | 低 | 已做双份（commit 6195f34 + 目录快照 + README tag）；回滚预案 arch §6.2 |

**关键决策点（S1/S2 实现时拍板，不改变轮数量级）**：
- D9 新源落点：源 H 后、conn.close() 前（arch 已定）
- D11 main-dirty 进跳过名单 + main_dirty_new_keys 独立写回（arch 已定，S1 改点 1-2）
- D10 状态键 sha1 用完整文件列表（展示截前 5）（arch 已定）
- D12/D13 源 K 心跳展示语义 + 按时长降序（arch 已定）

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 27-41 轮（中位 34） |
| DPL-018 校准后 | 70-106 轮（×K=2.60，中位 88）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 5（引擎/测试/归档/迁移集成/回归）→ 按规则拆 ~3 卡 |
| 模块依赖 | S1（机制代码）→ S2（T1-T8 测试 + 回归，依赖 S1 已 merge 才能测新源）→ S3（归档 + 全量回归 + OC 迁移，依赖 S1/S2 在 main + T9 追加到 S2 的测试文件）单向依赖，串行 |
| 并行收益 | 低——S2 测试依赖 S1 代码在 main；S3 归档与 T9 依赖 S2 测试文件存在；并行引入接口未就绪风险 |
| 兜底 | 若 S2 超预算，T1-T8 断言组可分 commit 交付（每源一组）；S1 独立可验收（手工 fixture + 锚点 spot-check）；S3 若 OC cron 删除受阻，git mv + T9 可先行（D8 ① 验证前置） |

**决策：拆 3 张串行子卡。** arch/PRD 的 2 serial 会让 S1 超预算（校准 49-75 轮），
按近 10 条偏差记录（5 张全 60 轮 timed_out）必再超时；拆 3 后每卡校准 16-39 轮，
全部落在 42 有效轮预算内，符合「4 交付物以上 → ~3 卡」规则。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 3 serial
1. [DEV-SUB-1] 机制核心 — R1/R2/R3 源 I/J/K 代码落地：oc_wake_check.sh 源 I（幽灵卡
   §2.2）/J（main-dirty §3.2）/K（stuck-long §4.2）三块插源 H 后 conn.close 前（arch
   verbatim，D9）；§5.3 改点 1-4（L438 跳过名单加 "main-dirty" + main_dirty_new_keys
   声明/底部追加循环 + 头注释 A-H→A-K + 幂等注释）；最小手工 fixture（temp kanban.db +
   fixture repo）验证三源输出含/不含 + bash -n/py 语法自检 + test_va_backfill T10c +
   test_deploy_drift T5 spot-check（seen 写回零回归）；merge --no-ff 进 main；
   [PRODUCES] claim（changed_files 段 + JSON 双格式） 预计 16-23 轮
2. [DEV-SUB-2] 测试+回归 — R5：新增 scripts/test_watchdog_unify.sh（env 桥 + fixture
   repo + seed_card，仿 test_deploy_drift T5 桥模式）；T1-T3 幽灵卡（含 qa 前缀/
   archived 负例/seen 幂等）/ T4-T5 main-dirty（含干净/集合变化/非 git fail-open）/
   T6-T8 stuck-long（含未超阈值/B 重叠排除/seen 幂等）；本地跑通全绿；回归
   test_wip_progress_check T14 + test_deploy_drift T5 + test_va_backfill T10 +
   test_cmd_channel PRD-GATE-T6 + devPPL pytest（§8.3 只增不删清单）；merge --no-ff
   进 main；[PRODUCES] claim（changed_files + JSON 双格式） 预计 26-39 轮
3. [DEV-SUB-3] 归档+迁移+落地 — R4/R5：git mv watch_board.sh / watch_dpl_chains.sh /
   oc_stuck_watchdog.py / test_oc_stuck_watchdog.py → scripts/archive/（D5，git mv 自动
   建目录）；test_watchdog_unify.sh 追加 T9（archive 4 文件存在且非空）；全量回归
   （test_watchdog_unify T1-T9 + 三套 oc_wake 测试 + cmd + pytest，D8 ④）；D8 顺序留痕
   （① 验证源 K 线上输出 → ② OC 删 cron 6b695ac1e290 + 清 wrapper D17 → ③ git mv →
   ④ 回归）；首 tick 观察幽灵卡/main-dirty/stuck-long 输出留痕；[PRODUCES] claim
   （changed_files + JSON 双格式）+ 飞书推送 + complete 预计 18-29 轮
```

- SPLIT: yes（count=3，交付物 5 → ~3 卡；arch/PRD 2 serial 的 S1 超预算，EST 修正）
- MODE: serial（S2 依赖 S1 机制在 main 才能测新源；S3 依赖 S1/S2 在 main + T9 追加到 S2 的测试文件；cron 删除依赖源 K 验证）
- FILES: S1 改 oc_wake_check.sh；S2 新增 test_watchdog_unify.sh；S3 git mv 4 文件 + 改 test_watchdog_unify.sh（追加 T9）
- 部署: S1 merge 后由 OC 部署 repo→profile（DPL-048 must-sync 清单覆盖 oc_wake_check.sh，R2 自引用悖论预期：源 G 会先报 oc_wake_check.sh 自身漂移，merge 后部署平息）
