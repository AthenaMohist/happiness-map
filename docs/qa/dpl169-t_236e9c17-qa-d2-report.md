# QA-D2 报告 — t_236e9c17（DPL-169 M9 复核 t_1891981b QA-EXEC）

日期: 2026-09-28 | 分支: wt/t_236e9c17 | 前棒: t_1891981b（QA-EXEC, commit a620541）| dev 卡: t_b601510d

## 评审结论（报告逻辑检查）

t_1891981b 报告逻辑合规：
- 执行方式如实（CC-MAX doctor 四检、后台两轮、隔离 TMPT、env -u 解除 delegate fence）
- G1-G7 门禁口径正确（本卡验收 = G 组 33 断言，非全量红零）
- FAIL 集合级对比方法符合 DPL-136（预存失败不作门禁，只比对新增）
- §1.2 判定过程完整（BLOCKER=0/MAJOR=0，2 条 MINOR 观察项）

## 独立抽测（3/3 VERIFIED，DPL-137 抽测口径）

- A1【G1-G7 全组复现】: 独立实跑 scripts/test_cmd_channel.sh（隔离 TEST_TMPT=/tmp/cmdchan-d2-t_236e9c17，
  env -u HERMES_DELEGATED_CHILD_CONTEXT）→ PASS=424 FAIL=42，G1-G7 组 33/33 全绿
  （G1a-d/G2a-d/G3a-c/G4a-c/G5a-d/G6a-e/G7a=8/G7b ok=8/G7c bad=0）。REPRODUCED。
- A2【only_in_run 时序判定复核】: 前棒报告的 2 条 only_in_run（PRD-GATE-T2a、T50h）
  本次复跑均 PASS → 证实"环境非确定性波动，非回归"判定成立。VERIFIED。
- A3【FAIL 集合对比复核】: 本次 42 红与 QA-D1 基线 42 完全一致（含 T21*/NO-REBUILD*/
  T53* 等），only_in_run=0，in_run_only=0。与前棒集合级结论一致。VERIFIED。

注: 本次 PASS=424 vs 前棒 422、FAIL=42 vs 44，差异恰为前棒的 2 条时序波动项，
两侧均无 G1-G7 组内差异。

## §1.2 判定

- BLOCKER=0 / MAJOR=0 / MINOR=0（前棒 2 条 MINOR 观察项经 A2 复核确认为环境波动，
  非产品缺陷，不构成 known issue）
- 安全漏洞: 无涉及
- 分歧/申诉: 无

## verdict: PASS（DPL-169 M9 门禁通过，建议合并）
