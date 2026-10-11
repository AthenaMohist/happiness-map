# 工作量评估 — t_062b13a4（DPL-154 终态守卫 R1+R2+R3）

- 评估卡: t_062b13a4 | 上游: PRD t_f23a89e2（7beee60）+ ARCH t_c636d34e
- 评估日期: 2026-09-10 | 执行模式: CC-MAX

## 1. 变更面（ARCH §4 实测）

| 文件 | 变更 | 规模 |
|---|---|---|
| pipeline/state.py | 终态分支 ~8 行 + `_handle_terminal_skip` + `_insert_terminal_skip_event` ~45 行 + 常量 | 小 |
| tests/test_dpl154_terminal_guard.py | 新增 T1-T10 矩阵 | 新文件 |
| 其余 | 无 schema/合约/调用方变更 | — |

## 2. 轮次估算（三口径，DPL-136）

| 项 | 基准 | 校准 ×K=2.53 |
|---|---|---|
| 实现轮（ARCH 伪代码级设计就绪，§2/§3 可直译） | 6-9 | 15-23 |
| 回归测试轮（T1-T10 + 4 条反向红线，T9/T10 已含） | 4-5 | —（测试量直接计入） |
| 收尾链固定预算（merge 后验证/WIP/claim/finalize/飞书） | +8 | +8 |
| **总计** | 18-22 | **27-36** |

注: 子评估 cc 返回 43-51 系对已含回归的口径重复乘 K 的双重放大，本报告按逐项校准口径取 27-36。

## 3. 裁决: 不拆（[SUB-SPLIT] 1 serial）

- ARCH §7 红线: R1+R2+R3 同文件 state.py + 同测试文件，「拆卡反而撞车」。
- 校准后 27-36 < 30 有效轮红线（≤42 预算），单卡 60 轮预算内可完成。
- 子评估建议拆 2 卡被否决: 拆出的测试卡与实现卡共享 state.py 上下文与 fixture，串行等待成本 > 并行收益。

## 4. 复杂度与风险点

- 复杂度: 中（变更面小，但插入点在 `determine_next_action` 热路径，回归红线 4 条需反向用例钉死）
- R1: 伪代码 → state.py 实际结构映射偏差（插入点 L768 附近、事件写入顺序）→ 以 ARCH §1 源码行号实勘兜底
- R2: `_insert_terminal_skip_event` 与既有事件写入路径兼容性 → 照抄 cmd_chain.py L822-840 真实形态
- R3: 幂等/防刷屏依赖 `_comment_dedup_sql` 同型实现，遗漏会刷屏 → T7/T8 二次评估断言覆盖
- R4: 事件行写入 kanban.db 为跨库直连 SQL，须严守只 INSERT task_events、绝不 UPDATE tasks（AC4）

## 5. 交付验收（对实现卡的钉子）

- 只跑 `pytest tests/test_dpl154_terminal_guard.py`（或 -k "terminal or retry"），禁止全量（DPL-137）
- 携带 ARCH §0 两条锁定条款 + §2 action=wait 契约 + §5 测试矩阵；§6 R4 存量清理 SQL 由 OC 执行，实现卡不碰存量数据
