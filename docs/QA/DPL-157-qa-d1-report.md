# DPL-153/157 QA-D1 测试报告 — t_69960b58（INF-018）

- 日期: 2026-09-10｜执行人: game-qa｜被测: /workspace/InfoManager main @ 2c21d6f（只读）
- 方案: docs/QA/DPL-157-qa-d1-test-plan.md｜脚本: docs/QA/qa_d1_scripts.py（QA 独立产出）

## 1. 执行结果

### QA 自有行为级脚本（mock 驱动，与研发测试独立）：7/7 PASS

| TC | 断言 | 结果 |
|---|---|---|
| TC-Q1 | R1 pipeline_state 真实 SQLite 往返 + 空记录 fail-open | PASS |
| TC-Q2 | ARCH D1 CLI 参数优先级最高（fetch 收到 CLI om_id） | PASS |
| TC-Q3 | AC2 gateway.log 多条不猜 / 唯一采信 / 窗外拒绝 | PASS |
| TC-Q4 | R2/AC4 相似度闸门 fail-closed（高相似 T；无关/拉取失败/无 og 均 F） | PASS |
| TC-Q5 | R3/AC5 url_missing 诚实降级（meta 双字段 + ocr_skipped: 前缀 + failed） | PASS |
| TC-Q6 | R4/AC7 全通道不可用 fail-open（ok=False，不抛异常） | PASS |
| TC-Q7 | R4/AC6 状态机 ok(3/3)+partial(1/3)+文本合并 | PASS |

### 子集回归（验收门禁，DPL-137 只跑本卡子集）
`pytest tests/ -k "toutiao or message_id or url"` → **31 passed, 133 deselected**（独立复跑两次一致）。

## 2. AC 覆盖对照

- AC1 ✓（TC-Q1+Q2，真实 SQLite 持久化非 mock 库）、AC2 ✓（TC-Q3）、AC3/AC4 ✓（TC-Q4+子集回归）、AC5 ✓（TC-Q5）、AC6 逻辑面 ✓（TC-Q7）、AC7 ✓（TC-Q6）。
- AC8（真网样例 om_x100b6510e9b7a8a0c44e45fac661153 回放）：**本卡未执行真网回放**，依赖外部飞书/头条端点实时可用，属 QA-EXEC/复测节点职责；本卡以 mock 等价覆盖三段式逻辑，不冒充真网证据。

## 3. 发现分级（标准 §1.2）

- BLOCKER 0 / MAJOR 0 / MINOR 0 / SUGGESTION 0。
- 复核预存问题（非本链引入，VA 报告 20260910T181226 已留痕）：`scripts/test_f3_url_boundary.py` 顶层 `exit()` 致裸 `pytest -k`（不限 scope）collect 阶段 INTERNALERROR。本卡以 `tests/` 为 scope 规避，不作为门禁。建议 OC 开 FIX 卡（SUGGESTION 级）。

## 4. 结论

DPL-157 R1-R4 实现与 PRD §4 / ARCH §2-§5 语义一致，行为级验证 7/7 + 子集回归 31/31 全绿。QA-D1 通过，0 发现。测试方案终审权在产品（Frank 2026-09-02 裁定）。
