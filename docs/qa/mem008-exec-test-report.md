# QA-EXEC 测试报告 — MEM-008 记忆突触自强化（访问加权 + 定期归档瘦身）

- 任务卡: t_75028424（[DEV-QA-EXEC]）
- 被测对象: mem-core MEM-008 五张 dev 子卡合并产物（分支 wt/t_e7b9ac69，顶 1d92b65）
- 测试环境: 独立 detach worktree /tmp/qa_exec_mem008 + 隔离 tmp wiki（/tmp/qa_mem008_exec_wiki）
- 测试人: game-qa | 日期: 2026-09-04 | 方式: EXEC 独立复测（不信任前棒结果，独立实跑）

## 1. 测试结果

| # | 项目 | 结果 |
|---|------|------|
| 1 | targeted 6 文件（r1/r2/r3/r3_apply/r4/r5） | ✅ 52 用例全绿（exit 0） |
| 2 | 全量回归 tests/ | ✅ **363 passed / 0 failed / 0 error / 0 skipped**（exit 0，与 QA-D1/SUB-5 一致） |
| 3 | 源码落盘 | ✅ archive.py L606+ 五报告函数齐全；lock.py fcntl.flock 独占锁 + 30s 超时；cli.py _record_lifecycle_access 8 个埋点调用点 |
| 4 | smoke-1 dry-run | ✅ rc=0；候选仅 TST-001（done, WT 0.010, idle 200d）；TST-002 active 豁免（status）、TST-003 热页豁免（idle）；豁免统计逐条件计数 |
| 5 | smoke-2 apply --all-candidates | ✅ rc=0；归档 1 跳过 0 失败 0；原件移 archive/2026-09/actions/、原位 stub status=archived |
| 6 | smoke-3 rollback TST-001 | ✅ rc=0；文件还原 status=done、archive 正本移除、**page_access 保留**（终端明示 + db 实查确认） |
| 7 | smoke-4 report --month | ✅ rc=0；四指标齐全（归档 1/释放体积/回滚 1/误归档率 100.0% ⚠ 标红）+ 状态文件 false_archive_red: true + 报告页落 wiki/archive/ |
| 8 | R1 埋点行为级 | ✅ `memctl add task TST-900` 后 page_access 实插 (TST-900, 1, now)——信号接通实证 |
| 9 | 冷启动护栏 | ✅ last_access_at=NULL 永不候选（v1 smoke 复现：0 访问历史时候选 0 页，保守豁免符合架构 D12⑤） |

## 2. 判定公式对照（qa-finding-classification §1.2）

- 发现: 0 BLOCKER / 0 MAJOR / 0 MINOR。
- 备注（SUGGESTION 不立案，与前棒一致）: 误归档率=回滚数/归档数，单页全回滚月报必 100% 标红——spec 预期行为，仅小样本月份解读提示。

## 3. SLA / 流程对照

- 无 BLOCKER/MAJOR，SLA 时钟不启动。
- 分级示例对照 §3: BLOCKER 定义（功能阻断无 workaround）不适用——全部验收口径行为级实证通过。

## 4. 结论

**PASS。** MEM-008 合并产物满足 PRD（R1-R5）与架构（A1-A12 相关项）验收口径，0 BLOCKER / 0 MAJOR，可发布。R5 cron 行注册权归 OC。

## 附: 复测证据

- targeted + 全量: pytest 独立实跑（日志 /tmp/qa_exec_mem008_run.log，363 行 PASSED）
- smoke 脚本: /tmp/qa_mem008_exec_smoke.sh、/tmp/qa_mem008_smoke2.sh、/tmp/qa_mem008_r1_smoke.sh（隔离 tmp 环境，真仓库零污染）
