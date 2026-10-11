# MEM-010 工作量评估——agent 产出自动链接（产出声明→任务页+项目页双链，蓝图方向B）

- 编号：MEM-010
- 来源卡：t_0253366d（本卡）
- 前棒 arch 卡：t_eb53e51a
- PRD 卡：t_5a39e6a8

## 实勘结论

**实现已由前棒 t_eb53e51a 落 mem-core 仓 main**（commit 69bc7f9 / 0a0a0da / defbc55 / 823ee76，另有 PRD commit ce8bd7d）。

符号实测（2026-09-30）：

- `parse_claim_paths` @ mem-core `memcore/sources/output.py:180`
- `cmd_output_links` @ mem-core `memcore/cli.py:2035`（挂 p_olinks 子命令）
- 测试 `tests/test_sources_output.py`：15/15 PASS
- mem-core 全量 pytest：77/77 PASS（无预存失败）

⚠️ 勘误：cc 首跑只在 devPPL 仓 grep → 误判"实现未落 main"；已进 /workspace/mem-core 核实翻案。父卡交接"32/32 PASS"口径与实跑（本文件 15 用例）数字不同，以实跑全量绿为准。

## 工作量（DPL-136 三段口径）

| 段 | 估轮 |
|---|---|
| 实现轮次（已由前棒落 main，本卡 0） | 0 |
| 收尾链固定预算（claim/finalize/飞书推送等） | +8 |
| 回归轮次（全量已实跑绿，残留核对） | 1 |

**合计 ≈ 9-11 轮，≤20 轮 → 不拆卡。**

## 风险点

- 实现位于 **mem-core 仓**（/workspace/mem-core）而非 devPPL 仓：下游 merge/验证卡若按 devPPL 仓路径核验会误判缺失（oc_wake_seen 中 t_eb53e51a 曾标 code-pending-merge 即同类误报）；下游卡需显式指向 mem-core。
- est 报告按卡面要求落 devPPL worktree docs/est/，合并时随 wt/t_0253366d 入 devPPL main。
