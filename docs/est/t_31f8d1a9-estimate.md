# 评估报告 — [DEV-EST] MEM-013 memctl 安全公证人 — 写入前凭据扫描+脱敏+注入检测（MEM-013）

> 评估人：寇豆码（game-engine） | 日期：2026-08-30 | 评估卡：t_31f8d1a9 | 源卡：t_31f8d1a9
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：PRD（t_ac5b20b3 done）→ 架构（t_5d64a722 done，commit bb0d673）→ 评估卡（本卡）→ 子卡执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 全撞 60 上限）

## 1. 结论（TL;DR）

**拆 3 张串行子卡（校准后每张 25-34 / 29-39 / 29-39 轮，全部落在 42 有效轮预算内）。**

任务本质：新增 memcore/notary.py 确定性安全闸门（纯 stdlib 规则引擎），并在
**10+4+2 处写点**接入 gate——cli.py 7 处页文本写收敛 `_write_page_text` + add raw
读-改-写 + 模块外写者（learn×4 / blast×1 / gailinks×1 / indexer×1）+ 派生出口
（_log_append / _git_commit 内部 gate）+ events 留档（幂等键双路径）+ 命令面
（notary --scan/--rules + status 扩展）+ strict/allowlist + AST 护栏测试 + 文档同步
（SCHEMA §2.1 / schema.py ENV）。

**评估期间实测关键发现（决定方案走向，非假设）：**
- **架构 D1-D9 已完全定稿**，实现是"按图施工"而非设计——arch 文档（bb0d673，
  569 行）对规则表（§2 逐条正则）、算法（§3.3 单遍顺序）、挂点矩阵（§4.2
  12 入口逐条）、异常矩阵（§5.4）、events schema（§6）、命令面（§7）、测试布局
  （§9.1）全部给到可执行粒度。这大幅压低发现/裁决轮数——主要工作量在机械接入
  与测试。
- **规则正则可直接复用零误报验证集**：/tmp/mem013_fp_check.py 存在（父卡 run 产物，
  10 族 credential + ZW + HTML 正则，93 页 0 命中已实测）——不重新发明，原样搬运
  进 notary.py 表驱动。⚠️ 但 /tmp 在沙箱重启后可能丢失（08-26 教训），实现时若
  丢失按 arch §2 表逐条重建（正则都在文档里，成本 ~0.5 轮）。
- **cli.py 写点实测确认**（grep）：write_text/copy2/copytree 共 10 处（L230/342/377/
  480/502/505/692/873/1036/1749），与 arch 事实 1 一致；`EXIT_VALIDATION=3` 已存在
  （L31）；_log_append L76 / _git_commit L47 实读确认 detail/message 切片形态
  （`title[:40]` / `title[:50]`）。
- **模块外写点实测确认**：learn.py L287/302/428/476（4 处）、blast.py L242、gailinks.py
  L136+L262（**grep 发现 L136 是另一处整文件写 `gai_path.write_text`，arch 事实 2
  只列了 L262——AST 护栏测试必须覆盖 L136，评估时列入 SUB-3 修复面**）、indexer.py L480。
- **conftest 基建现成**：wiki_root/db_path 临时夹具 + write_page 工具 + create_kanban_db/
  insert_task/insert_event（tests/conftest.py L19-199 实读）——E2E 测试直接复用，
  无需新建 fixture 框架。
- **schema.py ENV 区现 8 常量**（L55-118），无 MEM_NOTARY_*——新增 2 常量对齐既有风格。
- **测试基线**：pytest 174 passed（PRD 证据 9）+ lint 四不变式绿——A8 回归门禁有据。

## 2. 工作量评估（读码结论，非假设）

### 2.1 交付物清单（≥4，触发"一律拆 ~3 卡"）

| # | 交付物 | 落点 | 内容 |
|---|--------|------|------|
| 1 | 引擎模块 | memcore/notary.py（新增） | 规则表 + Finding/GateResult + scan/sanitize/gate_text + 掩码/脱敏/allowlist/strict/异常矩阵 |
| 2 | 写点集成 | cli.py + learn/blast/gailinks/indexer（改） | _write_page_text 收敛 7 处 + 模块外 4 写者一行 + 派生出口内部 gate + _notary_event |
| 3 | 测试套 | tests/test_notary*.py（新增 4 文件） | 单测 ≥15 断言 + E2E ≥6 入口 + AST 护栏 + perf |
| 4 | 命令面+文档 | cli.py build_parser + SCHEMA.md §2.1 + schema.py ENV | notary --scan/--rules + status 扩展 + 规范条款 + env 登记 |

### 2.2 三卡工作量分解

| 子卡 | 维度 | 评估 | 依据 |
|------|------|------|------|
| SUB-1（M1） | notary.py 引擎 + test_notary.py 单测 | 规则表搬运（10+3+2 正则，arch §2 表 + fp_check 脚本直搬）**1-1.5 轮**；dataclasses + 三函数 + 单遍算法（§3.3 占位符掩码→code 语境掩码→匹配→去重叠→allowlist→修复→field 反查）**2-3 轮**；占位符幂等 + code 剔除哨兵（NUL 等长映射）**1.5-2 轮**；strict/allowlist/异常矩阵（§5.4 四行）**1-1.5 轮**；test_notary.py ≥15 断言（规则边界×每族 + code-span 豁免 + 幂等 + 确定性 byte-equal + allowlist 损坏弃用 + strict rejected）**2.5-3.5 轮**；模块级 A6 静态断言（import 仅 stdlib）**0.5 轮** → **基准 8.5-13** | arch §2/§3/§5 全实读；fp_check.py 45 行实读；A6 断言可复用 conftest AST 模式（test_v2 先例） |
| SUB-2（M2） | cli 集成：_write_page_text + 7 页写点 + add raw 读改写 + 派生出口 + events + 命令面 | _write_page_text helper + strict 拒写（exit 3 语义）**1.5-2 轮**；7 处 write_text 收敛（L230/342/377/480/692/873/1036/1749，每处组装点前插 gate，控制流各异——done 有 --sync-gai 后置、note 有 bug 链分支）**3-4 轮**；add raw 读-改-写（L502/505：copy 前读源 gate + utf-8 失败 copy2 + 目录递归 + utime 恢复 mtime）**1.5-2 轮**；_notary_event + INSERT events + 幂等键（JSON1 json_extract 主路径 + LIKE 回退，对齐 _correction_exists L913-930）**2-2.5 轮**；_log_append/_git_commit 内部 gate（L47-80）**1-1.5 轮**；notary --scan/--rules 子命令 + build_parser + status 扩展行 + stdout 行（§7）**2-3 轮** → **基准 11-15** | cli.py L47-80/L166-380/L480-505/L615-700/L973-1040/L1696-1760/L1945-2040 实读；arch §4.1/§4.2/§6/§7 定稿；EXIT_VALIDATION=3 已存在 |
| SUB-3（M3+M4） | 模块外写者 + strict/allowlist 接线 + AST 护栏 + E2E + 文档 + 交付门禁 | learn.py 4 写点接入 + _write_page 返回 GateResult 上抛（L287/302/428/476）**1.5-2 轮**；blast L242 + gailinks L262 + **gailinks L136（评估新增发现）** + indexer L480 + 豁免注释决策 **1.5-2 轮**；allowlist 模块级缓存加载 + strict env 接线 **1 轮**；test_notary_gate.py E2E ≥6 入口（参数化真命令，断言页/log.md/commit message 三处无原值 + events 行）**2.5-3.5 轮**；test_notary_coverage.py AST 护栏（遍历 memcore/*.py 断言 gate_text 或豁免注释）**1.5-2 轮**；test_notary_perf.py + bench 脚本（marker=perf 双阈值）**1-1.5 轮**；SCHEMA.md §2.1 + schema.py ENV 登记 **0.5-1 轮**；A1-A11 交付门禁（pytest 全量 174+ 新增 + lint + 真库 --scan 0 命中 + bench 数字）**2-3 轮** → **基准 11.5-16** | learn/blast/gailinks/indexer 写点 grep 实读；conftest 夹具实读；arch §9 测试布局/验收映射表定稿；gailinks L136 是评估新增（arch 未列） |

**基准轮数（未校准，合计）：31-44 轮（中位 ~37）。**
**DPL-018 校准：31-44 × K=2.45 → 校准后 76-108 轮**——远超单卡 42 有效轮预算，
**必须拆卡**；按"4 交付物以上一律拆 ~3 卡"口径拆 3 张，每张落在预算内：
- SUB-1: 8.5-13 × 2.45 → **21-32 轮**（21/42 = 50% 起）
- SUB-2: 11-15 × 2.45 → **27-37 轮**（27/42 = 64% 起）
- SUB-3: 11.5-16 × 2.45 → **28-39 轮**（28/42 = 67% 起）

⚠️ 校准后每张卡起点都在 50% 预算以上——考虑最近 5 卡 timed_out 前科（估 18-33
全撞 60），这是诚实口径。若 SUB-2/SUB-3 再拆会碎成 5-6 张微型卡（每张 8-12 轮），
串行链延迟反而更糟；3 卡是 4+ 交付物任务的最优粒度（机制文档口径）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 规则正则搬运漂移（实现时私自放宽/收紧 → 零误报基线被破坏） | 高 | arch 明文硬约束（§2 头注：禁止嵌套量词；正则与 §2 表逐条一致）。缓解：SUB-1 claim 必须附"正则与 arch §2 表 diff 一致"证据；A3 全库 93 页 0 命中是交付门禁 |
| R2 | /tmp/mem013_fp_check.py 沙箱重启丢失 → 规则源只剩 arch 文档 | 中 | 正则全在 arch §2 表，重建成本 ~0.5 轮；SUB-1 开头先检查 /tmp，丢了就从文档搬运 |
| R3 | 7 处 cli 写点控制流各异（done 后置 --sync-gai / note bug 链 / add raw copy）→ helper 收敛回归风险 | 高 | arch D1 已裁决不重构成全统一 _write_page（控制流差异大），用私有 _write_page_text 收敛 7 处 + 逐处插 gate。缓解：SUB-2 每处接入后跑对应既有测试（test_cli.py / test_cmd_conversation.py 全量回归） |
| R4 | gailinks L136 整文件写未被 arch 挂点矩阵收录（评估新增发现） | 中 | AST 护栏测试若只按 arch 矩阵写会漏 L136。缓解：SUB-3 的 AST 护栏按"所有 write_text 调用点"收集（不按 arch 矩阵硬编码），L136 纳入 gate 或豁免注释 |
| R5 | events 幂等键 JSON1 依赖 sqlite 编译选项 → LIKE 回退路径 | 中 | 对齐 _correction_exists 双路径先例（cli.py L913-930）。缓解：SUB-2 幂等测试同时覆盖 JSON1 与强制 LIKE 回退（monkeypatch 抛 OperationalError） |
| R6 | E2E 测试对 git 的依赖（断言 `git show HEAD` commit message 无原值）→ CI 环境 git 隔离 | 中 | arch §9.2 已定 --no-commit 路径覆盖 + 临时 repo。缓解：conftest 现成 create_kanban_db/insert_event 可复用；E2E 用 tmp wiki 做独立 git init 或 no_commit 断言 |
| R7 | 异常矩阵 fail-open 语义难测（顶层异常 → 原文写 + stderr） | 中低 | 单测用 monkeypatch 让 gate_text 抛异常断言放行 + 警告行。缓解：SUB-1 单测覆盖，SUB-3 E2E 不重复 |
| R8 | 计时测试 flaky（CI 头号杀手） | 中 | arch D9 双阈值设计（CI <10s 宽松 / bench 5s 人工）。缓解：perf 独立 marker，主套件不含计时断言 |
| R9 | 校准后单卡起点 50%+ 预算 → 仍有超时风险 | 中 | 3 卡粒度是 4+ 交付物的机制最优解；每卡内部按里程碑再排优先级（SUB-2 先 helper+写点，命令面可后置；SUB-3 先写者接入+AST，E2E 可精简入口数） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 31-44 轮（中位 ~37） |
| DPL-018 校准后 | 76-108 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 4（引擎 / 写点集成 / 测试套 / 命令面+文档）≥ 4 → **拆 ~3 卡**（机制口径） |
| 单卡方案复算 | 3 张串行：SUB-1 21-32 / SUB-2 27-37 / SUB-3 28-39，全部 < 42 有效轮 ✅ |
| 依赖方向 | SUB-1（引擎）→ SUB-2（cli 集成，需 notary.gate_text）→ SUB-3（模块外写者需 gate_text + E2E 需 cli 写点 + 交付门禁需全部合并）→ **串行** |
| 并行收益 | 低——SUB-2/SUB-3 都依赖 SUB-1；SUB-3 的 E2E 断言 SUB-2 的写点行为；同仓同文件（cli.py/learn.py）并行会互相覆盖 |
| 兜底 | SUB-1 超预算：规则表可先行交付（其余下张卡）；SUB-2 超预算：命令面（notary --scan/--rules）可切到 SUB-3；SUB-3 超预算：E2E 入口从 6 精简到 4（A2 只要求 ≥6 但 QA 可补），perf 改人工 bench |

**决策：拆 3 张串行子卡（[SUB-SPLIT] 3 serial）。**
量级参照：t_569d4425（DPL-087，3 文件改造拆 2 卡）；t_1db58772（跨仓改造拆 2 卡）；
本任务 10+4+2 处写点 + 新增引擎 + 4 测试文件 + 文档同步，是 MEM-009（5 文件 +
4 测试文件）量级的 1.5 倍，3 卡粒度与"引擎/集成/收尾"分段对齐，也与 arch M1-M4
里程碑自然映射（M1→SUB-1，M2→SUB-2，M3+M4→SUB-3）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 3 serial
1. [DEV-SUB-1] MEM-013 M1 — memcore/notary.py 引擎模块 + test_notary.py 单测：
   新增 memcore/notary.py（纯 stdlib：re/hashlib/json/dataclasses，A6 静态断言
   import 仅 stdlib）：NOTARY_RULES_VERSION=1 + RULE_DEFS 表驱动（凭据 10 族 +
   不可见 Unicode 3 族 + HTML 2 族，正则与 arch-mem013-security-notary.md §2 表
   逐条一致——若 /tmp/mem013_fp_check.py 仍在则直接搬运，否则按 arch 表重建）；
   Finding/GateResult frozen dataclass；scan/sanitize/gate_text 三函数；
   单遍算法（§3.3：占位符掩码→HTML code 语境 NUL 哨兵掩码→三族匹配→重叠去重→
   allowlist 过滤→修复应用→field 反查）；占位符幂等（_PLACEHOLDER_RE）；
   strict 判定 + allowlist 加载（解析失败弃用 fail-secure）+ 异常矩阵（单规则跳过
   /顶层 fail-open/strict 拒写）；零 IO 纯函数（env/print 只在 gate_text 层）；
   新增 tests/test_notary.py ≥15 断言（规则族边界每族 ≥3、code-span/fence 内
   <script> 不命中、幂等重放零变化零计数、确定性 byte-equal、allowlist 命中豁免 +
   损坏弃用、strict rejected、占位符自识别）；
   交付自证：正则与 arch §2 表 diff 一致 + pytest tests/test_notary.py 全绿 +
   /tmp 或重建脚本跑全库 93 页 0 命中（A3 预演）。
   预计 21-32 轮
2. [DEV-SUB-2] MEM-013 M2 — cli 集成：_write_page_text + 7 页写点 + add raw 读改写
   + 派生出口 gate + events 留档 + 命令面：
   cli.py 新增私有 _write_page_text(path, text, *, field)（gate_text → strict 拒写
   exit 3 无落盘 → write_text）；收敛 7 处页文本写（L230 add task plain / L342
   from-kanban / L377 降级 / L480 conversation / L692 done / L873 note --bug /
   L1036 note / L1749 demote——按 arch §4.2 矩阵逐处组装前插 gate）；
   add raw 读-改-写（L502/505：copy 前逐文件读源 gate、utf-8 不可解码原样 copy2、
   目录递归、写后 os.utime 恢复源 mtime）；
   派生出口内部 gate（_log_append detail / _git_commit message 过 gate_text）；
   _notary_event(db, source, page_id, g) 唯一 events 写入口 + 幂等键
   （idempotency_key = "notary:" + sha256(sorted(rule:hash8:action))[:16]；
   JSON1 json_extract 主路径 + LIKE 回退，对齐 _correction_exists）；
   命令面：memctl notary --scan [--json]（0 命中 exit 0 / 有命中 exit 1，报告
   不含原值）+ notary --rules + status 扩展 notary 计数行 + 每次打码 stdout 行；
   build_parser 注册 notary 子命令；
   交付自证：7 写点 + 派生出口逐处 E2E 冒烟（构造含模拟凭据输入 → 落盘/log.md/
   commit message 无原值）+ 既有测试全量回归（test_cli/test_cmd_conversation/
   test_v2 等）不破。
   预计 27-37 轮
3. [DEV-SUB-3] MEM-013 M3+M4 — 模块外写者 + strict/allowlist 接线 + AST 护栏 +
   E2E 测试 + SCHEMA/schema.py 同步 + 交付门禁：
   learn.py 4 写点接入 gate（L287/302/428/476，_write_page 返回 GateResult 上抛）；
   blast.py L242（apply_curation_marker 返回 (changed, GateResult) 上抛）；
   gailinks.py L262 + **L136（arch 矩阵未收录，评估新增发现，必须覆盖）**；
   indexer.py L480 统一 gate（机械文本实际 no-op 或显式豁免注释）；
   事件统一走 cli._notary_event（模块外只 gate 不上抛 db 职责）；
   MEM_NOTARY_STRICT=1 拒写 exit 3 + MEM_NOTARY_ALLOWLIST 加载（模块级缓存）；
   新增 tests/test_notary_gate.py E2E ≥6 入口（add task from-kanban 标题 /
   add conversation --summary-file / add raw / done --result / note / learn --apply，
   断言落盘页 + log.md + git show HEAD commit message 三处无原值 + events 行
   detail 含 rule+hash8 不含原值 + strict 场景 exit 3）；
   tests/test_notary_coverage.py AST 护栏（遍历 memcore/*.py 所有 write_text/
   copy2/copytree 调用点 → 所在函数有 gate_text 或文件头 # notary-exempt 豁免注释）；
   tests/test_notary_perf.py（marker=perf，CI <10s 宽松阈值）+ bench 脚本；
   SCHEMA.md §2 铁律后新增 §2.1 写入安全闸门 + schema.py ENV 区登记
   ENV_NOTARY_STRICT/ENV_NOTARY_ALLOWLIST；
   交付门禁 A1-A11：pytest 全量绿（174+ 新增）+ memctl lint 零问题 + 真库
   notary --scan 0 命中 exit 0 + bench 计时数字写 claim。
   预计 28-39 轮
```

## 6. 备注

1. **部署验证不适用**：本任务全部改动在 mem-core 仓（memcore/*.py + tests/ +
   wiki/SCHEMA.md），非 devPPL cron 前置脚本（DPL-048 must-sync 清单只含
   orchestrator scripts/*.sh）→ 不适用部署验证规则，无 OC 部署依赖。
2. **串行依赖是硬约束**：SUB-2/SUB-3 都需要 notary.gate_text（SUB-1 产物）才可
   编译运行；SUB-3 的 E2E 断言 SUB-2 的写点行为。不可并行（同 profile 并行上限
   3 张虽有，但同仓同文件 cli.py/learn.py 改动会互相覆盖——DPL-026/DPL-027
   worktree 冲突教训）。
3. **gailinks L136 是评估新增发现**：arch 事实 2 只列了 gailinks.py L262，grep 实测
   L136 还有一处 `gai_path.write_text("\n".join(lines))` 整文件写。AST 护栏按
   "所有 write_text 调用点"收集（非 arch 矩阵硬编码）即天然覆盖；SUB-3 必须处理
   （gate 或豁免注释）。
4. **/tmp 脚本非持久**：fp_check.py 是父卡 run 的临时产物，沙箱重启即丢。SUB-1
   若发现丢失，按 arch §2 表重建正则（成本 ~0.5 轮），并在 claim 中注明来源
   （arch 表 vs /tmp 脚本）。
5. **A2 的 ≥6 入口与 SUB-3 E2E 的 ≥6 入口一致**：参数化真命令直调 cmd_* 或
   subprocess bin/memctl（conftest 现成夹具）；若 SUB-3 超预算，E2E 可精简到 4 个
   代表性入口（A2 原文"覆盖 ≥6 个代表性入口"——精简需在 claim 注明由 QA 补测）。
6. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建
   3 张 [DEV-SUB] 卡执行。
