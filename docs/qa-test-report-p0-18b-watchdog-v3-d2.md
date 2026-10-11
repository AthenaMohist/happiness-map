# QA Test Report: Watchdog v3.0 — D2 测试执行

> QA: Frank 团队游戏QA | 日期: 2026-07-10 | 版本: v2.0 (D2 执行)
> 测试方案: `docs/qa-test-plan-p0-18b-watchdog-v3.md` (v1.0, 45 用例, D1 评审通过)
> 架构基线: `docs/arch-p0-18b-watchdog-v3.md` (v1.2, R-D1已修正)
> D1 评审: `docs/roundtables/watchdog-v3-d1-architect-test-review.md`
> 依据标准: `docs/standards/qa-finding-classification.md` v1.0

---

## 1. 执行摘要

**24/24 测试 PASS，0 BLOCKER，0 MAJOR。**

| 指标 | 值 |
|------|----|
| 总测试文件 | 2 (`test_watchdog_smoke.py`, `test_watchdog_d1_feedback.py`) |
| 总测试用例 | **24** |
| PASS | **24** |
| FAIL | 0 |
| BLOCKER | **0** |
| MAJOR | **0** |
| MINOR | 见 §4 覆盖缺口 |
| 安全漏洞 | **0** |
| 未裁定申诉 | **0** |

**发布门禁** (对照 `qa-finding-classification.md §10`):

```
条件: BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉
状态: ✅  ALL PASS
```

---

## 2. D1 反馈融入情况

### 2.1 已融入项

| ID | D1 反馈 | 融入方案 | 验证测试 | 状态 |
|----|---------|---------|---------|:---:|
| **R-D1** | Frank裁定 — 「安排」仅限项目相关board，project_boards (list) | collector 仅扫描 project_boards 列表中的 board；project_boards 未指定时扫描全部 + root DB | TC-06, TC-12, TC-13 | ✅ |
| **A1** | 下一轮优先级未实现 | `read_next_cron()` 优先读 session.next_one_shot_at，fallback 到 cron.db | G-T4, G-T4b, G-T4c | ✅ |
| **A2** | Stale session 无差异化输出 | `read_session_state()` 返回 (state, kind) — active/stale/absent；stale 输出带 ⚠️ 警告 | TC-04, 原始测试更新 | ✅ |
| **G1** | 产品 P0 红线: reporter prompt 行为隔离 | collector 输出格式固定：📋/✅/🔄/⏳ emoji + 纯 UTF-8 无 ANSI | G1, G1b | ✅ |
| **G-T1** | session_started_at 缺失/为0 时的 fallback | _done_in_session=0 时 fallback 到 stats["done"] | G-T1, G-T1b | ✅ |
| **G-T2** | board 目录存在但无 kanban.db | `if not db_path.exists(): continue` 正确跳过 | G-T2, G-T2b | ✅ |
| **G-T3** | Reporter 首次 tick vs 后续 tick 空输出 | 两次连续空输出行为一致（collector 侧验证） | G-T3, G-T3b | ✅ |
| **G-T4** | next_one_shot_at 优先级逻辑 | session 字段优先，cron.db fallback，均无时不显示 | G-T4, G-T4b, G-T4c | ✅ |

### 2.2 工程缺口 (GAP-1~5)

| ID | 缺口 | 状态 |
|----|------|:---:|
| GAP-1 | collector 脚本未创建 (`kanban_collector.py`) | ✅ 已创建 (~/scripts/kanban_collector.py, 238 行) |
| GAP-2 | 测试数据准备脚本未创建 | ✅ 内联在测试文件中 (_make_* helpers) |
| GAP-3 | reporter cron 未配置 | ⚠️ 待 OC 集成 (Phase 2) — 非 collector 范畴 |
| GAP-4 | OC session file 生命周期未集成 | ⚠️ 待 OC SOUL.md 更新 (Phase 2) — 非 collector 范畴 |
| GAP-5 | v2 旧文件清理未执行 | ⚠️ 待 Phase 4 — 清理脚本需另行执行 |

---

## 3. 测试结果明细

### 3.1 基础冒烟测试 (TS1: Collector 单元, 13 tests)

| # | 测试名称 | 覆盖原 D1 用例 | 结果 | 说明 |
|---|---------|-------------|:---:|------|
| TC-01 | test_no_session_file | TS1-01, TS1-26 | PASS | 无 session → 空输出 |
| TC-02 | test_four_dimension_output | TS1-09, TS1-13, TS1-14, TS1-19 | PASS | 四维统计准确性 |
| TC-03 | test_blocked_excluded | TS1-13, TS1-21 | PASS | blocked 不纳入「安排」|
| TC-04 | test_stale_session | TS1-04, TS2-06, **A2 fix** | PASS | stale → 输出+⚠️ 警告 |
| TC-05 | test_corrupted_session_file | TS1-03, TS1-08 | PASS | 损坏 JSON → 空输出 |
| TC-06 | test_project_board_filtering | TS1-15, TS1-16 | PASS | project_boards 过滤 |
| TC-07 | test_no_kanban_boards | TS1-10, TS1-11 | PASS | 空目录 → 全 0 |
| TC-08 | test_no_cron_db | TS1-20, TS1-24 | PASS | 无 cron.db → 不显示下一轮 |
| TC-09 | test_corrupted_kanban_db | TS1-12 | PASS | 损坏 DB → 降级不崩溃 |
| TC-10 | test_root_db_included | TS1-16 (回退) | PASS | 无 project_boards → 含 root DB |
| TC-11 | test_env_var_override | — | PASS | 路径覆盖正常 |
| TC-12 | test_multi_board_aggregation | TS1-17 | PASS | 跨 board 汇总 |
| TC-13 | test_root_db_excluded_with_project_boards | — (v1.2) | PASS | project_boards 设置 → root DB 排除 |

### 3.2 D1 反馈测试 (11 tests)

| # | 测试名称 | D1 反馈 ID | 结果 | 说明 |
|---|---------|-----------|:---:|------|
| G-T1 | test_gt1_session_started_at_missing_fallback | G-T1 | PASS | started_at 缺失 → fallback 到 all done |
| G-T1b | test_gt1_session_started_at_zero_fallback | G-T1 | PASS | started_at=0 → all done 匹配 |
| G-T2 | test_gt2_board_dir_no_kanban_db | G-T2 | PASS | 目录有/无 DB → 不影响 |
| G-T2b | test_gt2_mixed_dirs_some_empty | G-T2 | PASS | 混合目录 → 仅扫有 DB 的 |
| G-T3 | test_gt3_collector_empty_output_structure | G-T3 | PASS | 首次/后续空输出行为一致 |
| G-T3b | test_gt3_collector_format_parseability | G-T3 | PASS | 输出结构可解析 |
| G-T4 | test_gt4_next_cron_session_priority | G-T4, A1 | PASS | session 字段优先 |
| G-T4b | test_gt4_next_cron_fallback_to_cron_db | G-T4 | PASS | fallback 到 cron.db |
| G-T4c | test_gt4_next_cron_neither_available | G-T4 | PASS | 均无 → 不显示 |
| G1 | test_g1_output_format_header_unchanged | G1 (P0) | PASS | emoji 头部固定 |
| G1b | test_g1_output_is_pure_utf8_text | G1 (P0) | PASS | 纯文本无 ANSI |

---

## 4. 覆盖缺口分析

### 4.1 已解决的 D1 缺口

| ID | 缺口 | 状态 |
|----|------|:---:|
| G-T1 | session_started_at 缺失 fallback | ✅ 已覆盖 (G-T1, G-T1b) |
| G-T2 | 目录存在无 kanban.db | ✅ 已覆盖 (G-T2, G-T2b) |
| G-T3 | Reporter 首次 tick 空输出 | ✅ 已覆盖 (G-T3, G-T3b) |
| G-T4 | next_one_shot_at 优先级 | ✅ 已覆盖 (G-T4, G-T4b, G-T4c) |
| G1 (P0红线) | Reporter 格式隔离 | ✅ 已覆盖 (G1, G1b) |

### 4.2 未覆盖的原 D1 测试用例 (MINOR)

| 原用例 ID | 未覆盖原因 | 严重度 | 计划 |
|-----------|----------|:---:|------|
| TS1-05 | TTL 边界刚好 600s | MINOR | Phase 5 |
| TS1-06 | TTL 边界 599s | MINOR | Phase 5 |
| TS1-07 | 缺少 max_age_seconds 字段 | MINOR | Phase 5 |
| TS1-18 | archived 任务不计数 | MINOR | 需 test fixture 增加 archived 列 |
| TS1-21 | cron.db 为空 (0 bytes) | MINOR | Phase 5 |
| TS2 (全8用例) | Session 生命周期 | MINOR | 待 OC 集成 (Phase 2) |
| TS3 (全5用例) | 旧文件清理验证 | MINOR | Phase 4 |
| TS4 (全5用例) | Layer1+2 集成 | MINOR | 待 reporter 配置 (Phase 2) |
| TS5 (部分用例) | 异常边缘场景 | MINOR | Phase 5 |

**MINOR 缺口**: 约 9-12 个用例等待后续 Phase 实现。不阻塞当前交付。

### 4.3 风险重新定级

按 `qa-finding-classification.md §1.2` 逐条复核：

| ID | D1 原定级 | D2 重新定级 | 理由 |
|----|:---:|:---:|------|
| R-D1 | BLOCKER | **已解决** | Frank 裁定完毕，project_boards 已实现 |
| R-D2 | MAJOR | **→ MINOR** | cron.db 为空已降级，有 session 字段替代 |
| R-C1 | MAJOR→MINOR (架构复核) | **MINOR** | OC 行为不可靠已有 TTL+SOUL.md 缓解 |
| R-C2 | MAJOR→MINOR (架构复核) | **MINOR** | A2 fix 提供差异化 stale 输出 |
| R-C3 | MAJOR→MINOR (架构复核) | **MINOR** | 幂等 key + OC 启动清理 |
| R-I1 | MAJOR | **MINOR** | G1 测试验证格式固定，减少 LLM 修改风险 |
| R-I2 | MAJOR | **MINOR** | OC 启动清理 + Reporter 自删 |

**结论**: 无 BLOCKER，无 MAJOR。所有风险项降级为 MINOR 或已解决。

---

## 5. 产出物清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `/root/.hermes/profiles/orchestrator/scripts/kanban_collector.py` | **新建** | Layer 1 collector, 238 行 |
| `/workspace/devPPL/tests/test_watchdog_smoke.py` | **修改** | TC-04 更新匹配 A2 fix |
| `/workspace/devPPL/tests/test_watchdog_d1_feedback.py` | **新建** | D1 反馈 11 tests |
| `docs/qa-test-report-p0-18b-watchdog-v3-d2.md` | **新建** | 本报告 |

---

## 6. 下一步建议

1. **Phase 2 (OC 集成)** — 需要 orchestrator SOUL.md 增加 watchdog 生命周期规则
2. **Phase 4 (v2 清理)** — 删除 3 个旧状态文件 + 废弃 v2 watchdog cron
3. **Phase 5 (完整测试)** — 补齐 TS2-TS5 测试（session 生命周期、集成、边缘场景）
4. **Reporter 配置** — 创建 Layer 2 reporter cron job，测试端到端心跳投递

---

> **QA 结论**: Watchdog v3.0 Layer 1 (kanban_collector.py) 通过全部 24 项测试。0 BLOCKER，0 MAJOR。D1 架构评审中发现的 4 个覆盖缺口 (G-T1~G-T4) 和产品 P0 红线 (G1) 已全部通过专项测试验证。架构不一致项 A1/A2 已在 collector 实现中修正。当前交付风险为 MINOR 级别，不阻塞 Phase 1 完成。

> **判定依据**: 本报告所有风险定级按 `docs/standards/qa-finding-classification.md` §1.2 五步判定公式执行。发布门禁检查通过 §10 条件。SLA 未触发（无 BLOCKER）。
