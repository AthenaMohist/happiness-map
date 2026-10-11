# QA-POST 报告 — INF-021 chain_review 扫描窗参数化（DPL-170，合并后 main 验证）

任务: t_0ceff964 | 日期: 2026-09-27 | 验证人: game-qa

## 验证范围（仅本卡子集，DPL-137 分层）

前置: dev 子卡 t_592760fa(S1) + t_6f1492c5(S2) 经 t_f3e8443f 合并，main HEAD=4292059。

| 检查 | 结果 |
|---|---|
| 扫描窗子集 pytest -k "ScanWindow or Cutoff" | 11 passed |
| 域回归 tests/test_chain_review.py 全文件 | 134 passed（无预存失败） |
| QA-D1 行为级探针 qa_inf021_probe.py（独立复跑） | 18/19 PASS |
| M17 dpl162_daily.sh:6 注释行「扫描窗缺省 23:00-23:00 BJT」 | 存在，cron 06:30 未动 |
| 扫描窗审计行 chain_review.py:1888-1899（day / cutoff 两分支） | 存在 |

探针唯一未过项 T8a：探针脚本硬编码日期过期，非产品缺陷（与 QA-D2 t_8cd1dedd 结论一致）。

## QA 分级对照（qa-finding-classification §1.2）

- 发现: BLOCKER=0, MAJOR=0, MINOR=0（T8a 系工具性硬编码，非用户可感知，不构成发现）
- SLA: 无发现，不适用
- 发布门禁 §10: 满足

## 结论

合并后 main 与 dev 交付声明一致，AC1-AC5 行为级复验通过。建议本链收口。
