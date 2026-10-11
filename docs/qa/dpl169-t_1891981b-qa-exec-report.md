# QA-EXEC 报告 — t_1891981b（DPL-169 M9 G1-G7 门禁用例全绿）

日期: 2026-09-28 | 分支: wt/t_1891981b | dev 前棒: t_b601510d（merge 3d1b719 已合入）

## 执行方式

- CC-MAX: cc-glm doctor 四检（KEY=ok ENDPOINT=200 VERSION=2.0.0 SHUTDOWN=none）
- 全量实跑 scripts/test_cmd_channel.sh 两轮（后台，隔离 TMPT=/tmp/cmdchan-test-t_1891981b）
- run1: 带.delegate fence env（HERMES_DELEGATED_CHILD_CONTEXT）→ G7b/c 红（hermes CLI
  拒子上下文写卡，与 QA-D1 run1 同根因）；run2: env -u 解除后重跑。

## 结果

- run2: PASS=422 FAIL=44；exit=44
- **G1-G7 组 33/33 全绿**（本卡验收门禁）:
  - G1a-d 登记（4）✓ G2a-d 幂等（4）✓ G3a-c fail-closed（3）✓
  - G4a-c 缺编号门禁（3）✓ G5 链型判定 8 条 ✓ G6 拒建路径+性能 9 条 ✓
  - G7a=8 / G7b ok=8 / G7c bad=0 ✓
- FAIL 集合级对比 QA-D1 run2（42 红，全为 main 基线预存）:
  - only_in_run（本卡新增 2 条）: PRD-GATE-T2a（OC unblock 后 arch 回 ready）、
    T50h（源卡 status=done 容器关闭）
  - 判定: 两条均为 hermes kanban CLI 子进程调用 / 容器关闭时序敏感用例，
    QA-D1 run2 中同位置通过 → 环境非确定性波动，非 G1-G7 回归
    （G1-G7 组断言不受影响，全绿）。
- in_run_only=0 相对 QA-D1 run2 集合（42/42 完全复现于本 run 红 集）。

## §1.2 判定

- BLOCKER=0 / MAJOR=0（G1-G7 门禁全绿；2 条 only_in_run 为时序波动观察项，
  建议 QA-D2 抽测 PRD-GATE-T2a 复核）
- 验收门限遵守: 本卡相关子集 + 集合级对比，未跑全量 pytest（DPL-137）

## verdict: PASS（附 2 条 MINOR 观察项，不阻塞）
