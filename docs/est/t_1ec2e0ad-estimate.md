# EST — t_1ec2e0ad DPL-145 PRD 返工（R3）工作量评估

> 评估人: game-engine（寇豆码）· 2026-09-16
> 输入: PRD v2.1（wiki/projects/devppl/prd/dpl145-round50-hardstop-autosystem-prd.md，mem-core）+ ARCH v1.0（arch-dpl145-round50-hardstop-autosystem.md）+ main 源码实测

## 1. 关键事实：三机制件主体已落 main，本卡是收尾增量

main 逐文件实锚（2026-09-16 git grep 实测）：

| 机制件 | ARCH 落点 | main 状态 | 证据 |
|---|---|---|---|
| M1 55 硬停 | wip_progress_check.sh | ✅ 已落 | 3bbd6ce [DEV-SUB-1]；25/50/55 三节点（L232-233, L382+）、`hard-stop:<tid>:<run_id>` 幂等、头注释修订（L8-11 已含 55 硬停例外）、hard-stop comment 文案（L418） |
| M2 TIMEOUT-HANDOFF | notify_check.py | ✅ 已落 | e375e5b；`emit_timeout_handoff()` 第 6 条 emit、run_id 幂等、phantom run 过滤、per-profile state.db 兼容（test_notify_dpl145_m2.py 17 PASS） |
| M3 派发注入+锁A | autopilot + lib | ✅ 已落 | f9d6e23；lib_handoff_inject.sh + handoff_gate_check.sh + autopilot L42/L496 接线 |
| 增补② 提取源优先级 | notify_check | ✅ 已落 | e375e5b commit 描述含 state.db 优先 |
| 增补③ CHECKPOINT_PROMPT_LINE 双保险 | constants.py L224 | ✅ 已落 | 双保险文案 + 55 硬停 + 60 边界，已在文案内 |
| AC6 合并门禁 grep | main 脚本 | ✅ 已满足 | `hard-stop` 7 文件 / `TIMEOUT-HANDOFF` 4 文件 hit @ main |

## 2. 剩余增量（本卡 dev 子卡的真实工作量）

1. **WINDOWN_SOUL_PARAGRAPH 修订（ARCH M-增补2 遗留，唯一实质改动）**：
   constants.py L345-367 现文仍是 FIX-B 旧版——触发写 `api_calls>=50`、无 55 硬停例外，且含已废除条款「**明确不做：脚本层不 block/reclaim 50 轮卡**」（PRD §1 打回理由 2 明令不得再引用，该段必须删除）。
   改法：触发带对齐 25/50/55（50 收尾 + 55 硬停兜底双轨）、删废除条款、加硬停例外标注。
   ⚠ 坑：inject_windown_rule.sh 按 TITLE 幂等跳过——TITLE 未变则三 profile 旧段永不更新，需 TITLE 加版本后缀（如 v2）或改幂等键。
2. **wip_progress_check.sh 50 节点文案补「双保险」两条件**（ARCH M-增补2：L449 现无"双保险"字样，仅 hard-stop L418 有）：1 行文案改。
3. **inject_windown_rule.sh --verify 回归**（scripts/test_inject_windown_rule.sh 104 行，快）+ wip_progress_check 子集 + notify 子集（46-73s/遍）。
4. **PRD §7 风险4 OC 上浮**：claim EXTEND 窗口行为确认 comment 1 条（PRD 明文要求实现前上浮）。

## 3. 估算（DPL-136 三项合计口径）

| 项 | 轮次 |
|---|---|
| 实现（constants 修订 + TITLE 幂等改造 + 50 节点文案 + 注入验证） | 6-9 |
| 回归子集（windown/wip/notify 各 1-2 遍） | 2-3 |
| 收尾链（WIP 笔记/claim/finalize/飞书） | +8 |
| **合计（校准前基准）** | **16-20** |
| DPL-018 校准 K=2.45 上界参考 | 偏高（本卡实现面已大部落 main，前 5 张超时卡是全新实现非收尾） |

**判定：≤20 轮 → 不拆**。依据：三机制主体已在 main，本卡仅文案/常量收尾，无新机制实现；上界 20 轮留足审批与测试折算余量。

## 4. 风险点

- TITLE 幂等键改造若遗漏 → 三 profile SOUL 永远停留旧版（含废除条款）——列为 dev 卡首个验收项。
- 部署面：SOUL 注入是跨 profile 写，执行方为 OC 授权（inject 脚本既有约束），dev 只改 repo 正本 + verify 模式测试。
- PRD 风险4 的 OC 上浮若未回 → 不阻塞实现（pid 二分已按 ARCH §1 M1 落地），claim 注明待确认即可。

## 5. 结论

[SUB-SPLIT] 1 serial（见 comment）。
