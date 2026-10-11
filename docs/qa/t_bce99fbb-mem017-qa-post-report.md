# MEM-017 QA-POST 合并后抽测报告（t_bce99fbb）

> 日期: 2026-10-06 | 执行模式: CC-MAX（cc-glm，doctor 四检全绿）| QA 只测不改: 零代码变更
> 性质: QA-POST 合并后 main 抽测（DPL-137 TL2：随机抽断言复核 + 报告逻辑检查，不跑全量）
> 依据: docs/qa/t_ffcd77dc-mem017-qa-plan.md（T1-T7）+ docs/qa/t_8aa8f2f5-mem017-qa-exec-report.md
> 对象: main HEAD 60d4281（MEM-017 merge t_fa589e9b，merge card t_2ff07077）

## 结论: PASS — 0 BLOCKER / 0 MAJOR / 1 MINOR（维持 MINOR-1）。MEM-017 合并后 main 状态与前棒 EXEC/D2 结论一致。

## 抽测断言（随机抽 4 条，独立复跑于 merge 后 main）

| 抽测 | 断言 | 结果 | 实测证据（本次 main 复跑输出） |
|------|------|------|----------|
| S1（T3/T6） | signal 门禁套件 + actor 三态行为 | PASS | /workspace/mem-core tests/test_mem008_r2_signal.py：14 passed in 0.37s；-k actor：4 passed（explicit_env/profile_fallback/anonymous_default/three_states_land_in_page_signal） |
| S2（T5） | 归档护栏零回归 | PASS | -k archive：20 passed, 469 deselected in 2.45s |
| S3（T1/T4） | 四符号实锚 + 四信号常量 | PASS | record_signal→decay.py:120 + cli.py:103/2443/2497；resolve_actor→decay.py:85；ENV_ACCESS_ACTOR="MEM_ACCESS_ACTOR"→schema.py:134；page_signal→archive/cli/decay/indexer 四文件实锚（schema.py 命中的是 ENV_ACCESS_ACTOR——即 MINOR-1 所述 PRD 措辞瑕疵）；schema.py:138 SIGNALS=("view","like","dislike","comment") |
| S4（T7/T2） | 收口三 commit 可达 + 收口行在位 | PASS | git merge-base --is-ancestor：575bd436 / 0ba037ed / 26569124 均 reachable；wiki/actions/MEM-017.md 执行记录含 2026-09-29 收口行（含 575bd43/0ba037e） |

## 报告逻辑检查
前棒 EXEC 报告（docs/qa/t_8aa8f2f5-mem017-qa-exec-report.md）判定公式/SLA/分级三段对照齐全，结论与本次抽测一致。

## MINOR-1（维持，不改判）
PRD §3 A1 "page_signal 命中 schema.py" 措辞不精确（schema.py 实际命中的是 ENV_ACCESS_ACTOR），本次 main 复跑确认仍在。不阻塞，建议 PRD 下次改版修正。分级依据: §1.2 → MINOR。

## 判定公式对照
收口抽测：全部证据可复现；无安全类发现；0 BLOCKER / 0 MAJOR → 发布门禁（§10）满足。

## SLA 对照
无 BLOCKER/MAJOR 发现 → 无 SLA 时钟启动。

## 分级示例对照
MINOR-1 对应标准 §3 MINOR 档。

## 交付物
- 本报告: docs/qa/t_bce99fbb-mem017-qa-post-report.md（落盘 wt/t_bce99fbb）
- changed_files: docs/qa/t_bce99fbb-mem017-qa-post-report.md
