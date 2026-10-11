# 评估报告 — [FIX] mem_sync create 幂等缺陷 — 目标页已存在报错 rc=1 而非降级 update/跳过（DPL-058）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_cd3c6d57
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_cd3c6d57（[FIX] mem_sync create 幂等缺陷 — 目标页已存在报错 rc=1 而非降级 update/跳过，DPL-058）
> 来源：MEM-007 端到端实测暴露（ALV-006 卡 t_e8a312a0 活体样本，2026-08-15）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 3 张串行子卡（校准后预计 43-63 轮 > 20 轮阈值）。**

缺陷真实、场景属正常业务路径（页先行创建/并发建页/手工补齐），必须修。但本卡表面是
"一个小改动"，实际是**双仓改动 + 契约约束 + 双仓回归 + live 观察**：
- 改动面跨 **mem-core**（adapter 探测能力 + D9 共享 helper）与 **devPPL**（引擎降级 + 集成测试）两个仓库；
- 源卡写「memctl page-get 或等价」，但 **`memctl page-get` 实测不存在**（--help 无此命令，
  调用报 `invalid choice: 'page-get'`）→ 必须用"等价"探测，这是一个需要实现时拍板的设计点；
- 验收含 **live 3 tick 日志观察**（cron 2 分钟/次 → ≥6 分钟等待）与**双仓全量 pytest**（devPPL
  基线 281/8/1、~10 分钟；mem-core 独立套件），单会话吃紧。

## 2. 工作量评估（读码结论 + 实测，非假设）

### 2.1 缺陷链路（实测定位）

```
mem_sync.py run_tick (L226-239)
  → adapter.command_for(ev, page_id)        # memcore/sources/kanban.py L192-193
      create → ["memctl","add","task",page_id,"--from-kanban",external_id]
  → run_memctl()                            # mem_sync.py L118-145
      memctl add 页已存在 → rc=1 → stderr "memctl add task: 页已存在: actions/ALV-006.md"
  → rc!=0 → counters["errors"] += 1, last_error="create ALV-006 rc=1"   # L238-239
```

- memctl 侧已存在幂等检查：`memcore/cli.py _add_task` L190-193 `target.exists()` → rc=1。
- 复现日志实锤：`/workspace/devPPL/logs/mem_sync.log` tick 14 @ 12:18:01Z `errors 1`，
  且 ALV-006.md 现仍存在（1846 B，actions/ 共 32 页）。
- 游标已越过该事件（cursor 11584 → 11591+），live 不再自然复现 → 回归只能靠测试复现 + 日志阴性观察。

### 2.2 关键发现：`memctl page-get` 不存在（源卡假设需修正）

实测 `memctl --help`：可用命令 add/done/note/query/lint/index/status/context/update/drift/
gai-links/demote/next-seq/mcp-serve/learn/journey —— **无 page-get**；直接调用报
`invalid choice: 'page-get'`。因此「探测目标页存在性」必须走**等价**实现，推荐两选一：

| 方案 | 内容 | 影响面 | 建议 |
|------|------|--------|:---:|
| P1 文件系统探测（推荐） | adapter 用 `indexer.default_paths()`（MEM_WIKI_PATH）解析 wiki 根 → `wiki/actions/<page_id>.md` exists；探测逻辑收进 D9 共享模块 `memcore/kanban_db.py`（新 `kanban_page_exists()`），cli.py `_add_task` 与 adapter 复用同一实现（契约对齐 D9 单一实现） | mem-core 3 文件 + 单测 | ✅ |
| P2 新增 memctl page-get 子命令 | cli.py 加 subcommand + argparse + help + 测试 | mem-core 更大改动面（CLI 契约变更） | ❌ 过重 |

引擎零感知约束：probe 由 adapter 暴露可选方法（如 `page_exists(page_id) -> bool | None`，
None=未知 → 保持现状），引擎在 create 命令执行前调用；已存在 → 记 skipped/update、log info、
不执行 memctl add、游标照常推进。

### 2.3 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 定位 + 设计决策 | 确认缺陷链路、page-get 缺失、P1/P2 取舍、探测方法签名 | 2-3 |
| ② | mem-core 探测能力 | `kanban_db.py` 新增 `kanban_page_exists()`（D9 单一实现）+ `sources/base.py` 可选 `page_exists()` + `sources/kanban.py` 实现 + `cli.py _add_task` 复用 helper + `tests/test_sources_kanban.py` 增用例 | 5-7 |
| ③ | devPPL 引擎降级 | `mem_sync.py run_tick` create 前探测 → 已存在 → `skipped/update++` + info 日志 + 不调 memctl + 游标推进；`scripts/test_mem_sync.sh` 增「预建页 + create 事件」场景（断言 errors=0、update/skipped=1） | 6-8 |
| ④ | 回归 + 落地 + live | devPPL 全量 pytest（~10min 后台）+ mem-core pytest + test_mem_sync.sh 全绿 + mem_sync 日志 3 tick 无「页已存在」（cron 2min×3，等待 ~6min）+ 双仓 merge 进 main + claim/飞书/complete | 4-6 |

**基准轮数（未校准）：15-22 轮（中位 18.5）。**
**DPL-018 校准：基准 × K=2.86 → 校准后 43-63 轮（中位 53）> 20 轮阈值 → 必须拆卡。**

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **`page-get` 不存在（设计决策）** | **中** | 源卡假设的命令不存在；P1（fs 探测 + D9 helper）是低成本等价，但需实现时确认 `default_paths()` 路径解析与测试 fixture（test_mem_sync.sh 用 `MEM_WIKI_PATH=$TMPT/wikiroot`，wiki 根为 `$MEM_WIKI_PATH/wiki` 或自身——与 `indexer.default_paths()` L505-515 的 `candidate = repo/"wiki"` 判定一致，可复用） |
| R2 双仓协调 | 中 | adapter 在 mem-core、引擎在 devPPL；S1 必须先进 mem-core main（S2 依赖 adapter 新方法），S2 引擎改动进 devPPL main，S3 做双仓回归+合并。两个仓库的 merge 窗口都要防 main 工作树冲突（DPL-026/027 教训） |
| R3 语义保持（不覆盖已存在内容） | 中 | 需求 2 明确"页已存在不重复建页、不覆盖已存在内容"。降级走"跳过记账"（skipped）最安全；若走 `memctl update` 需确认 update 不重写既有内容——`memctl update` 是索引/双链维护（cli.py L1060-1199），非内容重写，可安全用于"记账 update"，但**推荐 skipped**（语义最清晰、零风险） |
| R4 计数语义 | 低-中 | 需求 3 断言 `update/skipped=1`：实现时定死走 `skipped`（或 `update`）其一，计数器在 `_COUNTER_KEYS` 已存在（L54），无 schema 变更 |
| R5 日志级别 | 低 | 现有 `log()` 即 info 级别输出（L57-59）；探测命中走 info 日志即可，天然满足"日志级别 info 非 error"；关键是**探测前置**避免 run_memctl 打出 "非零退出" error 行 |
| R6 live 3 tick 观察 | 低-中 | 修复后真实日志不再自然复现该缺陷（游标已过）；live 验证是**阴性观察**（3 tick 无新「页已存在」error）+ 测试复现的阳性断言。等待 ~6min 不占轮数（后台/间歇轮询），但 tick 数必须对齐 cron 2min 周期 |
| R7 全量 pytest 存量失败 | 低 | devPPL 基线 281 passed / 8 failed / 1 error（DPL-057 实测，621s），8 failed 为存量（test_notify_exec_qa 等），只做"无新增"对照；mem-core 套件需单独跑（测试路径与 devPPL 不同，必须 MEM_CORE_PATH 指向修复后的 mem-core） |

**关键决策点（S1 实现时拍板，不改变轮数量级）**：
D1 探测等价方案：P1 fs 探测（推荐）vs P2 新增 page-get 子命令；
D2 降级记账：skipped（推荐，语义最清晰）vs update；
D3 `page_exists()` 返回 None 时保持现状（fail-open，兼容 gai adapter 不实现该可选方法）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 15-22 轮（中位 18.5） |
| DPL-018 校准后 | 43-63 轮（×K=2.86，中位 53）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（mem-core 探测）→ S2（devPPL 引擎降级，依赖 adapter 新方法）→ S3（双仓回归 + live + merge）单向依赖，串行 |
| 并行收益 | 无——S2 直接依赖 S1 的 adapter 接口；双仓并行反而引入接口未就绪风险 |
| 跨仓边界 | S1 纯 mem-core（探测能力 + 单测，可独立交付）；S2 纯 devPPL（引擎 + 集成测试，接口就绪后可独立交付）；S3 双仓收尾 |
| 兜底 | 若 S2 超预算，③ 的引擎改动与 test_mem_sync.sh 场景可分 commit 交付；S1 探测能力本身独立可验收（单测覆盖） |

**决策：拆 3 张串行子卡。** 单卡 43-63 轮逼近 60 轮预算上限（有效 42 轮），且 R1 设计决策 +
双仓 + 双仓回归 + live 观察客观上是多会话工作量，拆后每张 11-23 轮（校准口径），留足余量。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 3 serial
1. [S1] mem-core 探测能力（mem-core 仓）：kanban_db.py 新增 kanban_page_exists()（D9 单一实现，
   复用 indexer.default_paths() 解析 wiki 根）+ sources/base.py 可选 page_exists() + sources/kanban.py
   实现（wiki/actions/<page_id>.md exists）+ cli.py _add_task 复用同一 helper + tests/test_sources_kanban.py
   增用例（存在/不存在/未知）。预计校准后 14-20 轮。
2. [S2] devPPL 引擎降级 + 集成测试（devPPL 仓）：mem_sync.py run_tick create 前调 adapter.page_exists()
   → 已存在 → skipped++ + info 日志 + 不执行 memctl + 游标照常推进；scripts/test_mem_sync.sh 增
   「预建页 + create 事件」场景（断言 errors=0、update/skipped=1，参照 §2.1 复现链路构造 fixture）。
   依赖：S1 的 adapter.page_exists 进 mem-core main。预计校准后 17-23 轮。
3. [S3] 双仓回归 + live 观察 + 落地（devPPL + mem-core）：devPPL 全量 pytest（基线 281/8/1 无新增）
   + mem-core pytest + test_mem_sync.sh 全绿 + mem_sync 日志 3 tick 无「页已存在」阴性观察
   + 双仓 merge 进 main + claim/飞书/complete。依赖：S2 引擎改动进 devPPL main。预计校准后 11-17 轮。
```

- SPLIT: yes（count=3）
- MODE: serial（S1 → S2 → S3，接口依赖链）
- ROUNDS_EST（校准后）: 53（基准 18.5 × K=2.86）
- FILES: memcore/kanban_db.py, memcore/sources/base.py, memcore/sources/kanban.py, memcore/cli.py,
  memcore/tests/test_sources_kanban.py, scripts/mem_sync.py, scripts/test_mem_sync.sh
- STATUS: not_started（源卡 t_cd3c6d57 待 autopilot 建子卡）
- TESTS: mem-core test_sources_kanban.py 新增探测用例；test_mem_sync.sh 新增「页已存在 + create」场景；
  devPPL 全量 pytest 281/8/1 基线对照（无新增）；mem-core pytest 全量；live 3 tick 阴性观察
- RISK: R1 page-get 不存在 → P1 fs 探测等价（D9 helper）；R3 语义保持 → 走 skipped 记账不覆盖；
  R2 双仓 merge 窗口；R6 live 观察为阴性（~6min 等待）
- ACTION: build_three_dev_cards（S1/S2/S3 均 assignee=game-engine；S2 parents=[S1]，S3 parents=[S2]）

## 6. 备注

- **源卡假设修正**：源卡参考节写「memctl page-get（见 /usr/local/bin/memctl --help）」，
  实测该命令不存在。实现必须走等价探测（P1 推荐），评估已在 §2.2 记录证据。
- **D9 单一实现**：源卡契约对齐 D9（memcore/kanban_db.py 共享模块），探测逻辑必须收进
  kanban_db.py 单一实现，cli.py `_add_task` 与 adapter 复用，杜绝双实现漂移
  （与 arch-mem007 §2.3/D9 同构，参照 kanban_extract_task_code 先例）。
- **部署验证**：mem_sync.sh 是 cron repo 路径直调（"天然最新、零部署耦合，不进 must-sync"，
  脚本头注释自证）→ 修复进 main 即生效，**不适用** deploy-drift 部署验证规则
  （.hermes.md DPL-048），S3 只做 repo merge + live 日志观察即可。
- 本评估卡自身产物（本文件）需随源卡 merge 进 main，不能悬空（est 文档 NOT in main 正是
  DPL-056 类问题，见 t_est_0f418cf6 第三实例教训）。
- 本卡是真实代码修复（非文档收尾型），K=1.0 不适用——DPL-018 校准系数 K=2.86 全额生效。
