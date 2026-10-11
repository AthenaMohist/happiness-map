# B1-F1 修复验证记录（研发回归）

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-engine
>
> 来源卡：t_eb49e276 [B1-FIX] B1-F1 MAJOR — 边界消息失败重试推垃圾文案到飞书
> 修复 commit：`9263501` fix(notify): B1-F1 — milestone 聚合路径过滤 `__boundary__` 合成行

---

## 1. 修复内容

`scripts/notify_check.py` milestone 聚合路径（L595-600）格式化前过滤合成行：

```python
milestone_rows = [r for r in pending
                  if r["event_type"] == "milestone" and r["task_id"] != "__boundary__"]
```

- **过滤语义**：`task_id='__boundary__'` 的合成行（step_name=`work_state`）是纯内部冷却/审计用途，
  发送失败或 dry-run 时 `last_sent_at` 保持 NULL → 进入 pending 队列，原逻辑会被格式化为
  `{__boundary__} {work_state} done` 垃圾文案推送到飞书主通道。
- **边界消息优先路径不受影响**：状态迁移 tick 中 `boundary_msg` 非空时走优先分支，
  合成行被正确消费（`sent_rows=[{event_hash: boundary_hash}]`），真实「开工/空闲」消息正常推送。
- **冷却/审计职责保留**：合成行仍留在 notify_events，参与 event_hash 冷却去重与 7 天清理审计。

## 2. 回归测试记录（对 HEAD=9263501 执行）

| 套件 | 结果 | 证据 |
|------|:---:|------|
| 研发断言套件 `scripts/test_notify_check.py` | **33 PASS / 0 FAIL**（exit 0） | 27 原有 + T9(3)/T10(3) 新增回归断言 |
| T9: S1 边界消息发送失败 → 重试 tick 不推垃圾文案 | ✅ | T9-1/2/3：边界行入队未标记、无 `__boundary__` 文案、真实 milestone 仍推 |
| T10: S2 生产库 dry-run → 下 tick 不推垃圾文案 | ✅ | T10-1/2/3：dry-run 后 last_sent_at 仍 NULL、无垃圾文案、真实 milestone 仍推 |
| QA 独立断言 `python3 /tmp/qa_notify_retest.py` | **32 PASS / 0 FAIL**（exit 0） | E1-E12 全部通过 |
| QA 复现脚本 `python3 /tmp/qa_boundary_repro.py` | **S1 repro=False, S2 repro=False**（exit 0） | 两条触发路径均不再复现 |
| 补充边界消息正常推送验证 | ✅ | 空闲/开工边界各推 1 条正确文案、无 `__boundary__` 泄漏、30min 冷却仍抑制抖动 |

## 3. 验收标准对照（4 条全过）

| # | 验收标准 | 结果 |
|---|---------|:---:|
| 1 | S1/S2 两条触发路径修复后 repro=False | ✅ |
| 2 | 真实边界消息（开工/空闲）仍正常推送 | ✅ |
| 3 | 研发 27 断言套件 + QA 32 断言套件全绿 | ✅（研发 33 断言，含新增 6 条回归） |
| 4 | B1-DOC-1：smoke 文档 §5.3 边界 hash 描述修正 | ✅ 已修正为两个独立 hash |

## 4. 附带修复：B1-DOC-1（SUGGESTION）

`docs/qa/notify-cron-smoke-verification.md` §5.3 原描述误写为单 hash `__boundary__|active|idle|milestone`，
代码实际为两个独立 hash（L567 `__boundary__|active|milestone`、L572 `__boundary__|idle|milestone`），
各自独立冷却。已随本修复一并修正。
