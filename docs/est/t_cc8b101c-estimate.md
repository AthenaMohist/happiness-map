# EST — GAI 行手写绕过 CAS 修复（DPL-179）· t_cc8b101c

> 评估人: game-engine | 日期: 2026-09-29 | 依据: PRD v1.0 + ARCH v1.0 + main 实锚

## 1. 锚点实勘（mem-core main，2026-09-29）

- `memcore/seq.py:173-174`：`isolated = ("PYTEST_CURRENT_TEST" in os.environ or os.environ.get("MEM_SEQ_NO_REGISTRY") == "1")` —— PRD A1 / ARCH D1 已由 f60b606 落 main，与 ARCH §1 判定流零漂移。
- `_max_seq_from_registry`（seq.py:82/90）：`MEM_REGISTRY_FILE` env 通道在位，T-D1..T-D3 fixture 路径可行。
- `tests/test_seq.py`：现有 T8/T9/T10/T13 四用例，全部隐式 isolated 分支，A6 三条新增用例零覆盖 —— ARCH A6 缺口确认。
- 结论：**零生产代码改动**（A1-A5 已达标），DEV 主体 = 纯测试补齐 T-D1..T-D4，改 1 文件（tests/test_seq.py，可能 + conftest fixture）。

## 2. 工作量评估

| 工作项 | 内容 | 预估 |
|---|---|---|
| T-D1 | 用例① delenv PYTEST + MEM_REGISTRY_FILE fixture + 显式传参 → 断言 DPL-180（核心，读 REGISTRY 证据） | 4-6 轮 |
| T-D2 | 用例② MEM_SEQ_NO_REGISTRY=1 → 断言回落 GAI | 2-3 轮 |
| T-D3 | 用例③ 单行「- CODE-NNN:」「- **已用**:」形态计入 max + 连续段不回归 | 2-3 轮 |
| T-D4 | 子集回归 test_seq + test_gai_row 全绿 + py_compile | 2-3 轮 |

**实现小计: 10-15 轮**

## 3. 总轮次（DPL-136 三项合计口径 × 校准 K）

- 实现轮次: 10-15
- 收尾链固定预算: +8（merge 后验证 / WIP 笔记 / claim 文件 / finalize 四步 / 飞书推送）
- 回归测试: +2-3（子集 11+ 用例，实测 46-73s/遍 × 1 遍折算）
- **原始合计: 20-26 轮**
- 历史偏差校准（K=2.53 上限钳制过保守，本卡为纯测试、锚点已实勘零漂移、无生产代码风险面，取部分校准 ×1.3）: **校准后 26-34 轮**

## 4. 复杂度与风险

- 复杂度: 低。纯测试改动，无生产代码，红线（§3 四条）均为"不动"类约束。
- 风险点:
  1. delenv 后 CI 环境泄漏（ARCH §4 已备合规变体：subprocess 独立进程探针）→ +3-5 轮
  2. REGISTRY fixture 单行形态正则边界（全角冒号/粗体）→ 已由现行 m2 正则覆盖，低
  3. T8 教训回归（pytest 下误读真实 REGISTRY）→ T-D2 断言回落即覆盖

## 5. 拆卡决策

> 30 有效轮阈值（原始 42+）：本卡原始 26-34 轮，有效 ≈ 26×0.7 ≈ 18-24 < 30。且 4 交付物门槛不触发（单一交付物：测试补齐）。

**决策: N=1，不拆卡**，单张 dev 卡串行完成。
