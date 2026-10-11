# DPL-185 DEV-EST 评估结果

- worktree: /workspace/devPPL/.worktrees/t_a9e7da89 (wt/t_a9e7da89, 基于 main 118c627，含 885a154 落地 commit)
- 日期: 2026-10-02 | 结论: **全部落地，剩余工作仅评估收尾**

## 1. 实锚证据（worktree HEAD，git grep/读源码）

| 项 | 证据 |
|---|---|
| A1/A2 _clip_node_chain_line 活跃优先 | scripts/notify_check.py:1763 定义；docstring 明示「保活不保完」语义（DPL-185 A1/A2 2026-10-02）；实现含 actives/dones 分离、…(N✅) 计数尾注、链名缩号保编号 R2（编号段 [CODE-NNN] 完整保留） |
| A3 bl[:80] 退役 | notify_check.py:3181-3189 注释 [DPL-185 A3] bl[:80] 硬切退役，改 _clip_node_chain_line(..., budget=120) 行级转发 |
| A4 规范成文 | docs/watchdog-render-spec.md:70 §2.1 截断与折叠（DPL-185 v1.0，活跃优先单规则），含三规则 + 预算分配优先级（编号>活跃>done>链名） |
| A6 fixture | tests/test_notify_dpl185.py 存在（17 用例，含 F2 先红后绿 + 全 done 反例 + 半词抽检） |
| 调用接线 | notify_check.py:1921/1931/3206 多处走 _clip_node_chain_line |

## 2. 测试实跑（targeted，worktree 内）

| 套件 | 结果 |
|---|---|
| tests/test_notify_dpl185.py | PASS=17 FAIL=0 |
| tests/test_notify_gai_b2.py | PASS=47 FAIL=0 |
| tests/test_notify_dpl150.py | PASS=12 FAIL=0 |
| tests/test_notify_dpl145_m2.py | 17 PASS / 0 FAIL |

（注：test_notify_dpl185.py 为自运行脚本风格，python3 直跑；pytest 收集会触发模块级 sys.exit，属测试基建形态，非失败。）

## 3. PRD 验收逐项判定

| 项 | 判定 |
|---|---|
| A1 当前卡强制可见（活跃优先、禁半词） | 已实现（源码+测试 17/17） |
| A2 done 计数尾注 + 预算分配（先缩链名保编号） | 已实现（…(N✅) + R2 编号不牺牲） |
| A3 GAI 行 bl[:80] 退役 → budget=120 行级转发 | 已实现（notify_check.py:3181-3189） |
| A4 双写规范 | 已实现：devPPL docs §2.1 存在；mem-core main 72e6fc7 含 arch-dpl185-heartbeat-active-first-clip.md + wiki/concepts/patterns/watchdog-render-spec.md（git ls-tree 实锚） |
| A5 短行零回归 | 三套件 47+12+17 全绿 |
| A6 先红后绿 fixture | 存在且绿（输出含「F2 复现」「半词形态抽检」ok） |
| R1/R2/R3 红线 | 实现内嵌（绝不全词截节点 / 编号段不牺牲 / 短行零回归） |

## 4. 剩余工作量评估（DPL-136 口径）

- 收尾链（本 est → 拆卡/结卡确认 → 汇报）: ~4 轮
- 回归测试轮次: 0（已在本评估内实跑全绿，无需另派）
- 实现工作: 0（全部已在 main 885a154 落地）
- 小计: ~4 轮 × K=2.53 校准 ≈ 10 轮

## 5. 拆卡建议

预计 ≤20 轮 → [SUB-SPLIT] 1 serial：无需拆分，单卡收尾即可（确认父卡 t_c01a23f0 状态 + est 归档 + 汇报）。
