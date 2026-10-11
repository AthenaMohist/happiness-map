# 工作量评估 — t_bba78333（DPL-162 巡察使完整闭环 DEV）

> 评估卡: t_bba78333 | 评估人: game-engine | 日期: 2026-09-16
> 输入: PRD v1.0（wiki/projects/devppl/prd/dpl162-patrol-closed-loop-prd.md, commit e6115f6）
>      ARCH v1.0（wiki/projects/devppl/arch/arch-dpl162-patrol-closed-loop.md, commit 6e9d431）
> 源码实锚（本 worktree 实测）: scripts/chain_review.py 661 行 / tests/test_chain_review.py 307 行（10 case）

## 1. 工作量盘点（按 ARCH M1-M6）

| 模块 | 内容 | 实现轮次估 | 复杂度 | 风险点 |
|---|---|---|---|---|
| M1 扩源 | `_scan_wake`（/tmp/oc_wake_seen + autopilot.log 尾 5000 行 `[oc-wake-check]`）+ `_scan_diag`（[OC-DIAG] comment），env 可覆盖（OC_WAKE_SEEN_FILE/AUTOPILOT_LOG），scan_chains 汇聚点接线，fail-open | 6-8 | 中 | autopilot.log 14 万行大文件只读尾部；SEEN 文件键格式 `tag:task_id[:node]` 解析（实测 /tmp/oc_wake_seen 存在） |
| M4 三证据 | `verify_with_evidence()` 聚合 comment/event/run + OC-DIAG 引用计数，≥3 且 ≥2 源同向 → confirmed | 3-4 | 低 | 纯函数，三源同构可聚合（_scan_events:198/_scan_runs:220 同签名） |
| M2 wiki 复核 | `review_against_wiki()` memctl query Top-3，复用 `_resolve_memctl_bin:548`，缺席 fail-open route=new | 3-4 | 低-中 | 环境无 memctl → 全走 new 路径，测试需打桩 MEMCTL_BIN |
| M3 误报判定 | `is_false_positive()` import CARD_AUDIT_EXEMPT（chain_review.py:85 已在 main 工作树，不复制） | 2 | 低 | D1 收编依赖：清单随 S4 落 main |
| M5 分级路由 | `route_fix()` 纯函数 escalate/oc_direct/new_card，est_lines 机械规则 | 3-4 | 低 | AC3 单测直接断言 |
| M6 wiki 回写 | `writeback_fix_status()` 行级替换 + `--mark-fixed` CLI + cmd_chain.py close 接 [WIKI-GAP] 校验（_comment_gap_sql:2525 层） | 5-6 | 中-高 | cmd_chain.py 是核心管线文件，改动需谨慎；行格式漂移 miss 只告警（R-2） |
| 测试 | 每模块夹具单测 + AC2 误报夹具 + AC3 路由单测，tmp 隔离 | 6-8 | 中 | 五个 IO 入口全部 env/参数化 |
| 收尾链 | merge 后验证/WIP 笔记/claim/finalize 四步/飞书推送 | +8 | 固定预算 | DPL-136 口径 |
| 回归 | pytest tests/test_chain_review.py 子集（现 10 case 约 5-10s/轮）+ 两次真实数据 dry-run 实证 | 4-6 | — | 禁全量（DPL-137） |

## 2. 总量与决策

- **单卡总量**：实现 32-42 轮 + 收尾 8 + 回归 4-6 ≈ **44-56 轮**（校准前）；× 有效轮口径（÷0.7）预算需 63-80，远超单卡 60 上限。
- **历史校准 K=2.45**：近期同体量子卡 5/5 timed_out @60 轮。单卡不拆 = 大概率第 6 次 timeout。
- **ARCH §5 拆卡建议**：S1-S4 串行，每张 est_rounds≈15（实现口径）。
- **决策：拆 4 张串行子卡（>20 轮 → 拆）**，与 ARCH §5 完全一致。

每张子卡校准后口径：实现 15 × K(1.5~2 保守取中) + 收尾 8 + 回归 3 ≈ **预算 35-40 轮**（有效轮 25-28），单卡安全区内。

## 3. 拆卡方案（[SUB-SPLIT] 依据）

| 子卡 | 内容 | 依赖 |
|---|---|---|
| S1 | M1 扩源（_scan_wake/_scan_diag）+ M4 三证据 + 单测 | 无（D1 57 行 diff 验证归 OC/S4） |
| S2 | M2 wiki 复核 + M3 误报判定 + 单测 | S1 |
| S3 | M5 路由 + M6 回写 + cmd_chain close [WIKI-GAP] 接线 + 单测 | S2 |
| S4 | AC1 真实数据 dry-run 实证 + D1 半成品落 main + 子集回归 + 备份推送（MERGE） | S3 |

关键跨卡决策（写入各卡 body）：IO 入口 env 名固定 OC_WAKE_SEEN_FILE / AUTOPILOT_LOG / MEMCTL_BIN（与 oc_wake_check.sh:101、chain_review 既有口径一致）；pit_type 取值 watchdog_alert / oc_diag；路由优先级 escalate > oc_direct > new_card。

## 4. 风险与减损

1. **R-1** autopilot.log 格式漂移 → 源 B 只做包含匹配（ARCH 已定）。
2. **R-2** 经验页行格式不一致 → M6 匹配 miss 只告警不误写，幂等可补。
3. **R-3** close 校验存量链批量 [WIKI-GAP] → 告警不阻断。
4. cmd_chain.py 改动是唯一高险点 → 独立放 S3，测试子集覆盖 close 路径。
