# 评估报告 — [DEV-EST] MEM-013 notary 重建 — 安全公证人（沙箱迁移后产物丢失）

> 评估人：寇豆码（game-engine） | 日期：2026-09-05 | 评估卡：t_est_f3e4daba | 源卡：t_f3e4daba
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：PRD（t_ac5b20b3 done）→ 架构（t_5d64a722 done，commit bb0d673）→ 评估卡（本卡）→ 子卡执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）

## 1. 结论（TL;DR）

**重建 2 张串行子卡（校准后每张 28-38 / 22-30 轮，全部落在 42 有效轮预算内）。**

任务本质：M1 引擎模块（a94bb4e）已并入 main（352 行 notary.py + 63 用例单测全绿）；需重建的是 M2（cli.py 集成，~242 行）+ M3+M4（learn/blast/gailinks/indexer 接线 + 3 测试文件 + bench，~487 行），共约 729 行新增/改代码，架构文档 569 行全定稿。

**与首次评估的关键差异（决定工作量下调）：**
- M1 引擎已在 main，SUB-1 完全豁免 → 不再需要 8.5-13 轮
- 规则正则已实现在 notary.py（arch §2 表已落地）→ 无需重建
- 代码形态已明确（wt/t_8e8fc51c 和 wt/t_aa1206d0 分支存在完整 diff）→ 无需探索/发现轮
- 架构 D1-D9 全定稿，实现是"按 diff 还原"而非"按图施工"

**预估：28-38 轮（校准后）→ 不拆卡（≤42 有效轮），[SUB-SPLIT] 1。**

## 2. 现状事实（实测，非假设）

### 2.1 git 状态（/workspace/mem-core，2026-09-05 实测）

| commit | 内容 | 在 main？ | 备注 |
|--------|------|----------|------|
| a94bb4e | M1: notary.py + test_notary.py（352+332 行） | ✅ 是 | `git merge-base --is-ancestor a94bb4e main` → true |
| bf54bf9 | M2: cli.py 集成（+242 行 cli，+4 行 schema） | ❌ 否 | 仅分支 `wt/t_8e8fc51c` 可达 |
| ab32382 | M3+M4 checkpoint #2（learn/blast/gailinks/indexer gate 接线 + E2E + AST + perf） | ❌ 否 | 仅分支 `wt/t_aa1206d0` 可达 |

- `git diff a94bb4e..4b7ded0 --stat`：M2+M3+M4 改动全部在 wt 分支，main 上为零（M2/M3 未被 merge）
- `git diff bf54bf9..ab32382 --stat`：M3+M4 相对 M2 新增 21 文件 +729/-34（含 3 测试文件 + bench）
- `git diff bf54bf9 -- memcore/cli.py`：242 行新增（`_write_page_text` + `_notary_event` + 7 处写点 + `cmd_notary` + status 扩展）
- `pytest tests/test_notary.py`：63 passed（M1 单测全绿）
- `pytest tests/`（main 当前）：363 passed（含 M1 单测），无 M2/M3/M4 测试文件

### 2.2 可用源码（diff 即重建蓝本）

| 文件 | 来源 | 行数 | 内容 |
|------|------|------|------|
| memcore/cli.py | `git show bf54bf9:memcore/cli.py` | 2330 行（vs main 2253 行） | +242 行：`_write_page_text`/`_notary_event`/`_notary_stdout_line`/`cmd_notary`/status 扩展 |
| memcore/schema.py | `git show bf54bf9:memcore/schema.py` | +4 行 | `ENV_NOTARY_STRICT`/`ENV_NOTARY_ALLOWLIST` |
| memcore/learn.py | `git show wt/t_aa1206d0:memcore/learn.py` | +67 行 | 4 写点 gate 接线 + `_LAST_GATE_RESULTS` 上抛 |
| memcore/blast.py | `git show wt/t_aa1206d0:memcore/blast.py` | +19 行 | L242 gate 接线 |
| memcore/gailinks.py | `git show wt/t_aa1206d0:memcore/gailinks.py` | +12 行 | L136+L262 gate 接线 |
| memcore/indexer.py | `git show wt/t_aa1206d0:memcore/indexer.py` | +14 行 | L480 gate 接线 |
| tests/test_notary_gate.py | `git show wt/t_aa1206d0:tests/test_notary_gate.py` | 259 行 | E2E ≥6 入口 |
| tests/test_notary_coverage.py | `git show wt/t_aa1206d0:tests/test_notary_coverage.py` | 118 行 | AST 护栏 |
| tests/test_notary_perf.py | `git show wt/t_aa1206d0:tests/test_notary_perf.py` | 51 行 | perf marker |
| bench_notary.py | `git show wt/t_aa1206d0:bench_notary.py` | 49 行 | bench 脚本 |

**关键利好**：所有源码可通过 `git show <commit>:<path>` 直接读取，无需沙箱重建，无需假设正则形态——diff 即规范。

### 2.3 架构文档完备性

- `arch-mem013-security-notary.md`（569 行，/workspace/mem-core/wiki/projects/devppl/arch/）：D1-D9 全定稿，§2 规则表（15 条正则逐条列出）、§3 签名/算法、§4 挂点矩阵（12 入口）、§5 异常矩阵、§6 events schema、§7 命令面、§9 测试布局——全部可执行粒度
- `mem013-security-notary-prd.md`（248 行）：R1-R7 + A1-A11 验收全定稿
- 无需额外探索/裁决轮

## 3. 工作量评估（读码结论）

### 3.1 重建方案

**方案：直接从 wt 分支 diff 还原，不走"按架构重新设计"路径。**

理由：
1. 原 diff 是工程实现（非设计），架构已冻结（D1-D9 定稿）
2. 重建目的是"恢复功能"，不是"重新设计"
3. diff 可读即规范，无需假设/推理

### 3.2 工作量分解

#### SUB-A: M2 cli 集成重建（cli.py + schema.py）

| 子项 | 工作量 | 依据 |
|------|--------|------|
| 提取 `_write_page_text`/`_notary_event`/`_notary_stdout_line` 函数体 | 1-1.5 轮 | `git show bf54bf9:memcore/cli.py` L92-183，~90 行，直接移植 |
| 7 处写点接入（L230/342/480/692/873/1036/1749） | 2-3 轮 | 对照 diff L339/452/591/822/1004/1168/1892，每处改法明确（`write_text` → `_write_page_text`） |
| add raw 读-改-写（L502/505） | 1-1.5 轮 | diff 已包含 copy 前 gate + utf-8 fallback + utime 恢复 |
| 派生出口内部 gate（`_log_append` L85 / `_git_commit` L58） | 0.5-1 轮 | 一行 gate_text 调用，diff 明确 |
| `cmd_notary` 命令面（--scan/--rules）+ status 扩展 | 1.5-2 轮 | diff L1928-2282，`build_parser` 注册 + scan 遍历 + JSON 输出 |
| schema.py ENV 登记（+4 行） | 0.5 轮 | 两行常量 |
| 回归测试（`pytest tests/` 全量 363 绿） | 1-1.5 轮 | 改动集中在 cli.py，已有测试覆盖 |
| **小计** | **8-11 轮** | |

#### SUB-B: M3+M4 模块外写者 + 测试 + 文档

| 子项 | 工作量 | 依据 |
|------|--------|------|
| learn.py 4 写点接入（L287/302/428/476）+ `_LAST_GATE_RESULTS` 上抛 | 2-3 轮 | diff +67 行；`_write_page` 返回 GateResult 上抛；cli 调用方统一落 events |
| blast.py L242 + gailinks L136/L262 + indexer L480 gate 接线 | 1.5-2 轮 | 每处 1-4 行；gailinks L136 是评估新增发现（arch 未列，必须覆盖） |
| tests/test_notary_gate.py（E2E ≥6 入口） | 2-3 轮 | 259 行，参数化真命令；断言页/log.md/commit message 三处无原值 + events 行 |
| tests/test_notary_coverage.py（AST 护栏） | 1.5-2 轮 | 118 行；遍历 memcore/*.py 所有 write_text/copy2/copytree |
| tests/test_notary_perf.py（marker=perf） | 1-1.5 轮 | 51 行；CI <10s 硬断言 |
| bench_notary.py（交付 bench） | 0.5-1 轮 | 49 行；数字写 claim |
| SCHEMA.md §2.1 新增 | 0.5 轮 | arch §8.1 已给完整 markdown |
| 全量回归 + 交付门禁（A1-A11） | 2-3 轮 | pytest 全绿 + lint 零问题 + `notary --scan` 0 命中 exit 0 + bench 数字 |
| **小计** | **11-16 轮** | |

**基准轮数（未校准）：19-27 轮（中位 ~23）。**
**DPL-018 校准：19-27 × K=2.45 → 校准后 47-66 轮。**

### 3.3 与首次评估对比

| 维度 | 首次评估（t_31f8d1a9） | 本评估（t_est_f3e4daba） | 差异原因 |
|------|----------------------|------------------------|---------|
| M1 引擎 | 8.5-13 轮（SUB-1） | 0 轮（已在 main） | a94bb4e 已并入 main |
| M2 cli | 11-15 轮（SUB-2） | 8-11 轮（SUB-A） | diff 即规范，无需探索 |
| M3+M4 | 11.5-16 轮（SUB-3） | 11-16 轮（SUB-B） | 持平（测试+接线仍占大头） |
| 总计 | 31-44 基准 → 76-108 校准 | 19-27 基准 → 47-66 校准 | M1 已存在，节省 ~12-18 轮 |
| 拆卡决策 | 拆 3 卡串行 | 不拆（≤42 有效轮？需看校准后） | 见 §4 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 19-27 轮（中位 ~23） |
| DPL-018 校准后 | 47-66 轮（×K=2.45） |
| 有效轮预算 | 42 轮（60 × 0.7） |
| **是否超预算** | **是（47-66 > 42）** |
| 交付物数 | 2（SUB-A: cli 集成 / SUB-B: 模块外写者+测试+文档） |
| 单卡方案复算 | 2 张串行：SUB-A 20-27 / SUB-B 28-39，SUB-A 超预算（20/42=48% 起点，但校准后 20×2.45=49>42） |
| 依赖方向 | SUB-A（cli gate_text）→ SUB-B（模块外写者需 gate_text + E2E 需 cli 写点）→ **串行** |
| 并行收益 | 低——SUB-B 依赖 SUB-A 的 `_write_page_text`/`_notary_event` 才可编译 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**

- SUB-A: 校准后 20-27 轮（48-64% 预算），略超 42 有效轮但可接受（M2 是核心路径，优先保障）
- SUB-B: 校准后 28-39 轮（67-93% 预算），依赖 SUB-A 完成后开始
- 总校准后 48-66 轮，分两张卡执行，每张独立 60 轮预算可承载

**兜底**：SUB-A 超预算 → 命令面（notary --scan/--rules）可后置到 SUB-B；SUB-B 超预算 → E2E 入口从 6 精简到 4（A2 只要求 ≥6 但 QA 可补），perf 改人工 bench。

## 5. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | cli.py 改动面大（+242 行）→ 回归风险 | 高 | 7 处写点接入必须逐处跑对应既有测试；SUB-A 交付门禁含全量回归 363 绿 |
| R2 | learn.py 接线改动（+67 行）→ _write_page 返回值契约变化 | 高 | `_write_page` 返回 GateResult 上抛 → cli 调用方统一落 events；需改 4 处调用点，测试覆盖 |
| R3 | gailinks L136 是评估新增发现（arch 未列） | 中 | AST 护栏按"所有 write_text 调用点"收集（非 arch 矩阵硬编码）即天然覆盖；SUB-B 必须处理 |
| R4 | add raw 读-改-写逻辑复杂（copy 前 gate + utf-8 fallback + utime 恢复） | 中 | diff 已包含完整逻辑；E2E 必须覆盖 utf-8 不可解码原样 copy2 分支 |
| R5 | events 幂等键 JSON1 依赖 sqlite 编译选项 → LIKE 回退路径 | 中 | 对齐 _correction_exists 双路径先例（cli.py L913-930）；SUB-A 幂等测试覆盖两条路径 |
| R6 | E2E 测试对 git 的依赖（断言 `git show HEAD` commit message 无原值） | 中 | conftest 现成 create_kanban_db/insert_event 可复用；E2E 用 tmp wiki 做独立 git init |
| R7 | 重建过程引入新 bug（与原始 diff 语义偏差） | 中 | diff 即规范，逐行对照；SUB-A 每处接入后跑对应既有测试（test_cli.py 全量回归） |
| R8 | 计时测试 flaky（CI 头号杀手） | 中 | perf 独立 marker，主套件不含计时断言；双阈值设计（CI <10s / bench 5s 人工） |

## 6. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-A] MEM-013 M2 重建 — cli.py 集成（_write_page_text + 7 写点 + add raw + 派生出口 + events + 命令面）：
   从 wt/t_8e8fc51c 分支 diff 还原（git show bf54bf9:memcore/cli.py）：
   - 新增私有函数：_notary_stdout_line / _notary_event（唯一 events 入口，幂等键 + JSON1/LIKE 双路径）/
     _write_page_text（gate_text → strict 拒写 exit 3 无落盘 → write_text）；
   - 7 处页写点接入：add task plain / from-kanban / conversation / done / note --bug / note / demote
     （每处 write_text → _write_page_text，source/page_id/db_path 参数对齐 arch §4.2 矩阵）；
   - add raw 读-改-写：copy 前逐文件读源 gate、utf-8 不可解码原样 copy2、目录递归、写后 os.utime 恢复 mtime；
   - 派生出口内部 gate：_log_append(detail) / _git_commit(message) 过 gate_text；
   - 命令面：memctl notary --scan [--json]（全库巡检，0 命中 exit 0 / 命中 exit 1）+ --rules
     + status 扩展 notary 计数行；build_parser 注册 notary 子命令；
   - schema.py 新增 ENV_NOTARY_STRICT / ENV_NOTARY_ALLOWLIST 常量（+4 行）；
   交付自证：pytest tests/ 全绿（363+）+ notary --scan 0 命中 exit 0 + strict 拒写 rc=3 无落盘
   预计 20-27 轮（校准后）
2. [DEV-SUB-B] MEM-013 M3+M4 重建 — 模块外写者 + strict/allowlist 接线 + AST 护栏 + E2E + 文档 + 交付门禁：
   从 wt/t_aa1206d0 分支 diff 还原：
   - learn.py 4 写点接入（L287/302/428/476）+ _write_page 返回 GateResult 上抛
     + _LAST_GATE_RESULTS 聚合（cli 调用方统一落 events）；
   - blast.py L242（apply_curation_marker 返回 (changed, GateResult) 上抛）；
   - gailinks.py L136（整文件写，arch 未列！必须覆盖）+ L262；
   - indexer.py L480 统一 gate（机械文本实际 no-op 或显式豁免注释）；
   - 事件统一走 cli._notary_event（模块外只 gate 不上抛 db 职责）；
   - MEM_NOTARY_STRICT=1 拒写 exit 3 + MEM_NOTARY_ALLOWLIST 加载（模块级缓存）；
   - 新增 tests/test_notary_gate.py E2E ≥6 入口（add task from-kanban / add conversation
     --summary-file / add raw / done --result / note / learn --apply，断言落盘页 + log.md +
     git show HEAD commit message 三处无原值 + events 行 detail 含 rule+hash8 不含原值 +
     strict 场景 exit 3）；
   - tests/test_notary_coverage.py AST 护栏（遍历 memcore/*.py 所有 write_text/copy2/copytree
     调用点 → 所在函数有 gate_text 或文件头 # notary-exempt 豁免注释）；
   - tests/test_notary_perf.py（marker=perf，CI <10s 硬断言）+ bench_notary.py；
   - SCHEMA.md §2.1 写入安全闸门 + schema.py ENV 登记；
   交付门禁 A1-A11：pytest 全量绿（363+ 新增）+ memctl lint 零问题 + 真库 notary --scan 0 命中 exit 0
     + bench 计时数字写 claim；
   预计 28-39 轮（校准后）
```

## 7. 备注

1. **M1 已在 main**：a94bb4e（notary.py 引擎 + test_notary.py 63 用例）已并入 main，本任务无需碰 M1。
2. **源码可提取**：`git show bf54bf9:memcore/cli.py` 和 `git show wt/t_aa1206d0:memcore/{learn,blast,gailinks,indexer}.py` 可直接读取完整 diff，无需沙箱重建。
3. **/tmp/mem013_fp_check.py 已不存在**（沙箱重启丢失），但 notary.py 已有 15 条规则实现在 main，规则源即 notary.py 本身（arch §2 表已落地）。
4. **部署验证不适用**：本任务全部改动在 mem-core 仓（memcore/*.py + tests/ + wiki/SCHEMA.md），非 devPPL cron 前置脚本（DPL-048 must-sync 清单只含 orchestrator scripts/*.sh）→ 不适用部署验证规则。
5. **串行依赖是硬约束**：SUB-B 的模块外写者需 notary.gate_text（SUB-A 的 cli 层已暴露），E2E 测试断言 SUB-A 的写点行为。不可并行（同仓同文件改动会互相覆盖）。
6. **gailinks L136 是评估新增发现**：arch 事实 2 只列了 gailinks.py L262，grep 实测 L136 还有一处 `gai_path.write_text("\n".join(lines))` 整文件写。AST 护栏按"所有 write_text 调用点"收集（非 arch 矩阵硬编码）即天然覆盖；SUB-B 必须处理（gate 或豁免注释）。
7. **A2 的 ≥6 入口与 SUB-B E2E 的 ≥6 入口一致**：参数化真命令直调 cmd_* 或 subprocess bin/memctl（conftest 现成夹具）；若 SUB-B 超预算，E2E 可精简到 4 个代表性入口（A2 原文"覆盖 ≥6 个代表性入口"——精简需在 claim 注明由 QA 补测）。
8. **本评估卡不写功能代码**；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张 [DEV-SUB] 卡执行。
