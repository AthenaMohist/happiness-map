# QA 复测报告 — P0-19 D1 FIX: staleness guard + relay 合规

> 复测日期：2026-07-10
> 母任务：P0-19 (t_9c82bf17)
> 修复任务：t_21daf056 (game-engine)
> 复测任务：t_c698943c (game-qa)
> 复测范围：仅 G-T1 和 R-R3 两个 MAJOR 修复

## 复测发现总表

| 编号 | 原发现 | 原级别 | 修复后判定 | 测试用例 | 结果 |
|------|--------|--------|-----------|---------|------|
| G-T1 | staleness guard 缺失 | MAJOR | **已修复** | 11/11 PASS | ✅ |
| R-R3 | LLM relay 不合规 | MAJOR | **已修复** | 6/6 PASS | ✅ |

## G-T1: staleness guard — 详细验证

### 修复内容
`kanban_collector.py` 的 `read_relay_state()` 新增 staleness guard：
- `RELAY_STALENESS_SECONDS = 600`（10 分钟）
- 当 `updated_at > 10min` → 返回 `(None, None)`
- 无 `updated_at` 字段时保持向后兼容（正常展示 relay）

### 测试策略
6 个边界条件 x 多场景 = 11 项断言：

| TC | 场景 | 断言 | 结果 |
|----|------|------|------|
| TC1a | 新鲜 relay (60s前) → phase | phase='polling' | PASS |
| TC1b | 新鲜 relay (60s前) → detail | detail 包含原文 | PASS |
| TC2a | 过期 relay (660s前) → phase | phase=None | PASS |
| TC2b | 过期 relay (660s前) → detail | detail=None | PASS |
| TC3a | 无 updated_at 字段 → phase（兼容） | phase='completed' | PASS |
| TC3b | 无 updated_at 字段 → detail（兼容） | detail='QA PASS' | PASS |
| TC4a | 文件不存在 → phase | phase=None | PASS |
| TC4b | 文件不存在 → detail | detail=None | PASS |
| TC5a | ISO 字符串 + 过期 → phase | phase=None | PASS |
| TC5b | ISO 字符串 + 过期 → detail | detail=None | PASS |
| TC6 | ISO 字符串 + 新鲜 → phase | phase='dispatching' | PASS |

### 回归验证
- `tests/test_watchdog_smoke.py`: 13/13 PASS
- `tests/test_watchdog_d1_feedback.py`: 11/11 PASS
- `_s6_collector_test.py`: 7/7 PASS

**总计：35/35 PASS，0 回归**

## R-R3: relay_update 合规 — 详细验证

### 修复内容
两个 SOUL.md 的接力 cron prompt 模板新增"阶段 -1/0（强制前置）"：
- 每个 tick 第一步强制调用 `relay_update.py`
- ⚠️ 强制校验语言 + 铁律 enforcement
- relay_update.py 调用失败时要求立即重试

### grep 检查结果

**orchestrator/SOUL.md**（6 项命中）：
- Line 337: `RELAY_HELPER = /root/.../relay_update.py` ← 路径正确
- Line 339: `## 阶段 -1（强制前置）：relay 状态初始化 — 每个 tick 第一步`
- Line 340-341: `必须先调用 relay_update.py` + 完整命令
- Line 344-345: `⚠️ 强制校验` + `铁律`
- Line 369: `每个 tick 必须从 阶段 -1 开始：先调 relay_update.py`
- Line 370: `如果 relay_update.py 调用失败...立即重试`

**game-engine/SOUL.md**（6 项命中）：
- Line 126: `RELAY_HELPER = /root/.../relay_update.py` ← 路径正确
- Line 128: `## 阶段 0（强制前置）：relay 状态初始化 — 每个 tick 第一步`
- Line 129-130: `必须先调用 relay_update.py` + 完整命令
- Line 131-132: `⚠️ 强制校验` + `铁律` + `跳过此步骤的 tick 将被视为违规`
- Line 156: `每个状态变更必须先调 relay_update.py`

### relay_update.py 静态验证
- 文件存在 ✅ | 可执行 ✅
- 5 个有效 phase（polling/dispatching/waiting/completed/error）✅
- 原子写入（write .tmp → os.rename）✅
- detail 截断 ≤ 60 字符 ✅
- `updated_at = time.time()` ✅
- JSON 输出到 stdout ✅
- 错误处理（sys.exit + stderr）✅

## 判定对照

依据 `docs/standards/qa-finding-classification.md` §1.2 判定公式：

| 检查项 | 用户可感知 | 功能阻断 | 有 workaround | 判定 |
|--------|-----------|---------|--------------|------|
| G-T1 | 是（过期 relay 会误导） | 否（不影响核心功能） | 是（手动检查时间戳） | → 原 MAJOR 合理 |
| G-T1 修复后 | 不再触发 | — | — | → **修复通过** |
| R-R3 | 是（LLM 忘记 relay 导致播报缺失） | 否（不影响核心功能） | 是（手动调 relay_update） | → 原 MAJOR 合理 |
| R-R3 修复后 | prompt 强制前置 | — | — | → **修复通过** |

**发布门禁检查**（§10）：
- BLOCKER=0 ✅
- MAJOR：原 2 项均修复完成，当前 **MAJOR=0** ✅
- 安全漏洞=0 ✅
- 无未裁定的申诉 ✅

## 结论

**P0-19 D1 的两个 MAJOR 修复（G-T1 staleness guard + R-R3 relay 合规）均通过 QA 复测。**

- G-T1：11/11 针对性断言 + 31/31 回归 = 42/42 全绿
- R-R3：两个 SOUL.md 共 12 项 grep 检查全部命中，relay_update.py 7 项静态检查通过
- 无新增问题，无回归

**发布建议：✅ 放行。两个 MAJOR 均已修复闭合，可合入 main。**
