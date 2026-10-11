# DPL-158 巡检使 — QA-EXEC 验收报告

- 任务: t_5a5f36fb（[DEV-QA-EXEC]，DPL-158）
- 执行模式: QA-EXEC（DPL-137 分层 TL1）— 只跑本卡测试子集 + 行为级抽验
- 被测产物: scripts/timeout_patrol.py（565 行）、scripts/timeout_ledger.py（526 行）
- 测试代码: tests/test_dpl158_patrol.py（28 用例）、tests/test_dpl158_ledger.py（9 用例）
- worktree: wt/t_5a5f36fb @ 03bc349
- 日期: 2026-09-11

## 1. 验收门禁子集重跑（本卡相关，非全量）

| 套件 | 结果 |
|------|------|
| tests/test_dpl158_patrol.py + test_dpl158_ledger.py | 35/35 passed (0.55s) |
| 行为级抽验（patrol 关键 11 项：扫描采集/僵尸/F1-F5 分类器/级联覆盖/block 门禁写一次/fail-open/dry-run 不写） | 11/11 passed |
| 行为级抽验（ledger 全 9 项：日报结构/飞书推送+去重/wiki 写回追加列/CSV/复发标记） | 9/9 passed |

## 2. 行为级独立抽验（自写探针，非套件内断言）

探针: /tmp/qa_exec_probe_dpl158.py（直接 import timeout_ledger 喂真实 wiki 表文本）

- P1 正常 F2 命中追加「发生2/修复2/修复2问题和解决方案」三列组、时间戳落发生列、修复列留空待人填 → PASS（与 PRD 一致）
- P2 未知 cause 键（F9:漂移键）：表头不追加组、无数据落笔、无行损坏 → PASS（未知键 fail-open 合理）

## 3. 发现

### F-E1 MAJOR — update_wiki_table 表行重消费错位导致数据行重复

- 复现: probe1 — wiki 表 1 条数据行（F2），cause="F5:循环型"（有命中但表内无对应行）时，输出表中 F2 数据行出现两次。
- 根因: timeout_ledger.py 表行重组循环 `consumed >= 1 + len(parsed["rows"])`（约 :243-254）。line_indices=[header, 数据行]，消费目标 = 2，只吞掉 header+第 1 行物理行，未覆盖分隔行与其后数据行；table_stop 截断错位，残留原表尾部行拼进新表 → 重复行。
- 影响: wiki 台账页被写坏（行重复/错列），cron 每日运行会持续累积脏数据；QA-D1 F-D1-3（cause 键集漂移产生碎行+写错行）同类缺陷在 cause 命中但行缺失路径上仍复现 → 确认为 F-D1-3 同根因的一个独立触发面，cron 上线前必须修（与 QA-D1 建议一致，需 OC 建研发 FIX 卡）。
- 定级: MAJOR（功能可感知、台账数据被污染、无 workaround——除非人工每次校对 wiki）。0 BLOCKER。
- 判定公式对照（标准 §1.2）: 用户可感知（台账页错乱）AND 功能受损 AND 无 workaround → 达 MAJOR；不阻断巡检主流程（扫描/推送正常）故非 BLOCKER。SLA: MAJOR 不适用 BLOCKER SLA，建议随 F-D1-3 合并处理。

### F-E2 MINOR — probe1 中表头空组仍追加

- 同 probe1 场景：cause 行缺失时表头仍被追加一组 3 列（发生1/修复1/...）但无任何数据落笔，产生纯空列。与 F-E1 同触发面，修复 F-E1 时应一并处理（无行命中则不追加组）。

## 4. 结论 / verdict

- 0 BLOCKER / 1 MAJOR open（F-E1，与 QA-D1 F-D1-3 同根因族）/ 1 MINOR
- DEV 交付的扫描/分类/门禁/日报/CSV 行为与 PRD 一致，35/35 绿；唯一实质风险集中在 ledger wiki 写回的行重组逻辑。
- 处置建议: F-E1 + F-E2 与 QA-D1 F-D1-3/F-D1-4 合并为一张研发 FIX 卡（ledger wiki 写回模块），cron 上线前修复后由 QA 复测回归。

## 5. 标准对照

- 判定公式: 已逐条对照 §1.2（见 F-E1）；无安全漏洞面（脚本只读 kanban.db ro 模式，测试验证 mode=ro URI）。
- SLA: MAJOR 按常规排期；无 BLOCKER，不触发 4h/8h/24h SLA。
- 发布门禁（§10）: BLOCKER=0 满足；MAJOR=1 open 需研发 FIX 卡跟踪，cron 启用前必须闭环。
