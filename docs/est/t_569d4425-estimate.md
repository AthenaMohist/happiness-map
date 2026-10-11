# 评估报告 — [FIX] VA 补扫 claim 锚定匹配假阳性 — `## [PRODUCES]` markdown 前缀 claim 全漏检（DPL-087）

> 评估人：寇豆码（game-engine） | 日期：2026-08-20 | 评估卡：t_est_569d4425 | 源卡：t_569d4425
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：OC 实测误报（t_4db0eb2d skip_count 已 11+）→ 评估卡（本卡）→ FIX 卡执行
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 全撞 60 上限）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后每张 15-22 / 12-17 轮，全部落在 42 有效轮预算内）。**

任务本质：discover.py claim 检测的**前缀容差匹配改造**。4 处锚定 SQL
（`body LIKE '[CLAIM]%' OR body LIKE '[PRODUCES]%'`）+ 1 处短路边 + 真库两个 va-skip
注册文件收敛 + 全量回归。核心改动集中在一个 SQL 谓词族的统一重写。

**评估期间实测关键发现（决定方案走向，非假设）：**
- **卡面所列 5 处之外还有第 6 处同病点**：`pipeline/cmd_chain.py:1214 _extract_produces`
  也是锚定 `LIKE '[PRODUCES]%'`——链推进（advance）取前棒产物路径的入口。`## ` 前缀下
  该查询恒 miss → 静默回退到附件兜底（attachments 表无行 → 返回空串）。影响：11 棒链里
  任何一棒用 `## [PRODUCES]` 格式，advance 注入「前置产物: （见前棒卡 comment）」的路径
  提取退化为空，下游棒产物路径注入降级。**修 discover.py 4 处而不修 cmd_chain.py，链机制
  仍是盲的——必须纳入修复面**（复用同一个 helper，边际成本 ~0）。
- **机器自写标记不受影响**：`[VA-SKIP]` / `[SUB-SPLIT-DONE]` / `[SUB-SPLIT-HOLD]` /
  `[VERIFIED]` 均为 discover/autopilot/VA 机器自写，格式恒锚定（无 markdown 前缀变体），
  不需要容差。**人写 claim 才需要容差**（`## [PRODUCES]` / `**[CLAIM]**` / 全角空格等变体）。
- **真库活体证据**（.pipeline/va-skip/，2026-08-20 实读）：
  t_4db0eb2d skip_count=**13**（卡面写 11，持续递增中）reason=no-claim snippet=空串；
  t_1db58772 skip_count=**18** 同病。两者都是「claim 存在但锚定 miss → 判 no-claim」的
  假阳性活体，修复后应收敛为正常 VA 建卡路径（skip_count 停止递增，最新扫描按新判定走）。
- **生产调用链已核实**：cron jobs.json 直调 devppl_autopilot.sh → repo 路径 autopilot.sh
  L190 `process_va_backfill`（每 tick）→ 4 处锚定 SQL。**discover.py / cmd_chain.py 不在
  部署验证 must-sync 清单**（DPL-048 清单只含 cron 直调/绝对路径引用的 .sh 脚本；
  autopilot 内部 `from pipeline.discover import` 走 repo 路径，repo 合并即生效）→ 本卡
  **不适用部署验证规则**，无 OC 部署依赖。
- **测试基建现成**：test_va_backfill.sh 已有完整 harness（build_fake_kanban + seed_task/
  seed_claim + run_scan/rj + FAKE_REPO 注册文件隔离），T10 系列断言模式直接可仿。
  新用例组 T11 复用同一 harness，增量成本低。

## 2. 工作量评估（读码结论，非假设）

改动面：**3 文件**——
- `pipeline/discover.py`：新增 1 个匹配 helper（模块级 `_CLAIM_PREFIX_TOLERANT_SQL`
  常量 + 可选 `_match_claim_body`），4 处 SQL 谓词统一替换，L1176 短路修正为
  OR 语义（miss 不再直接 return False，继续走条件 3/4），docstring 同步；
- `pipeline/cmd_chain.py`：L1214 `_extract_produces` SQL + L1215 正则提取同步容差
  （含 markdown 前缀剥除后取路径）；
- `scripts/test_va_backfill.sh`：T11 用例组（4-6 用例 × 3-5 断言）+ 全量回归。

回归面：test_va_backfill.sh 全量（91）+ test_watchdog_unify.sh（28）+ test_wip_progress_check.sh（94）
+ test_cmd_channel.sh（受 _extract_produces 改动影响的链测试）+ python 语法/导入冒烟。

|| 维度 | 评估 | 依据 |
|---|------|------|------|
| ① SUB-1 机制（discover.py + cmd_chain.py 匹配改造） | 方案细化（前缀集合选择：`[CLAIM]`/`[PRODUCES]` 裸锚定 + `## `/`# `/`**`/`__` markdown 变体 + 边界控制——卡面建议 3-4 个候选形态的裁决）**1-1.5 轮**；实现：helper + 4 SQL 替换 + L1176 短路修正 + cmd_chain `_extract_produces` 容差（SQL + 正则双改造）+ docstring **2-2.5 轮**；真库预演（修复前先复现：t_4db0eb2d 锚定 miss 实测 → 修复后验证收敛）**0.5 轮**；bash/python 冒烟 **0.5 轮** → **基准 4-5.5** | L1120-1359 全实读；L1176-1177 短路逻辑实读（在条件 3 `_metadata_has_file_claims` 之前 return False）；cmd_chain L1210-1222 实读；4 处 SQL 同构（同一 helper 一次修复） |
| ② SUB-2 测试 + 回归（test_va_backfill.sh T11 + 全量） | T11 用例组：正例 3 变体（`## [PRODUCES]` / `## [CLAIM]` / `**[CLAIM]**` 各建 done 卡 → 不判 no-claim，含 file 产物触发 VA 建卡）**1-1.5 轮**；反例 2（裸 `%[CLAIM]%` 全模糊被拒：引用不命中如「见子卡 claim」/ 前后缀乱序不命中）**0.5-1 轮**；短路面回归（L1176 修正：metadata 有 claims + comment 锚定 miss → 仍 True）**0.5-1 轮**；真库收敛断言（fixture 模拟 t_4db0eb2d 形态 → reason 重分类/收敛）**0.5 轮**；全量回归 4 套（va_backfill 91 + watchdog 28 + wip 94 + cmd_channel）+ 修破 **2-3 轮** → **基准 5-7.5** | test_va_backfill.sh T10 fixture 模式实读（build_fake_kanban/seed_claim/run_scan 现成）；test_cmd_channel.sh 621/636 行有 [PRODUCES] 锚定断言，受 _extract_produces 改动影响需回归；用例膨胀按 +40% 备（MEM-007 实证） |

**基准轮数（未校准，合计）：9-13 轮（中位 ~11）。**
**DPL-018 校准：9-13 × K=2.45 → 校准后 22-32 轮**（单卡 52-76% 预算，理论上勉强可单卡，
但考虑最近 5 卡 timed_out 前科 + 前缀匹配语义裁决风险，拆 2 卡留缓冲更稳）。

## 3. 复杂度与风险

|| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | 前缀匹配策略过宽 → 引用性误匹配（卡面明示红线） | 高 | 卡面禁止裸 `%[CLAIM]%` 全模糊。缓解：白名单前缀集（`'[CLAIM]%'`/`'[PRODUCES]%'` 裸锚定 + `'%\n[CLAIM]%'` 行首变体 + `'## [CLAIM]%'`/`'**[CLAIM]**%'` markdown 变体），SQLite LIKE 单 escape `#`/`*` 无需转义；「见子卡 claim」「参考 claim」引用语不进白名单形态 → 不命中（T11 反例显式测） |
| R2 | L1176 短路修正改变 OR 语义 → 既有 nonstd 判定回归 | 中 | 修正后「claim miss（含锚定 miss）→ 继续走条件 3（metadata）/4（交付 commit）」与 docstring「判定顺序 1/2 → 3 → 4」对齐。缓解：T10 既有用例（t_src_nonstd 四条件全不命中仍 skip）必须不破；真 no-claim 卡（无任何 claim comment）行为不变（ miss 后条件 3/4 也不命中 → 仍 skip，只是 reason 分类可能从 no-claim 变 nonstd——这正是验收要求的方向） |
| R3 | va-skip 注册文件收敛语义 | 中 | 修复后 t_4db0eb2d/t_1db58772 不再 skip → skip_count 自然停止递增（不再写）。reason 字段处置两案：a) 不动旧文件（历史痕迹保留）；b) 手工重分类。卡面允许两案，方案进 claim。缓解：fixture 断言「修复后扫描 → 文件不再更新/skip_count 不增」 |
| R4 | cmd_chain `_extract_produces` 正则提取在 markdown 前缀下退化 | 中 | SQL 容差后 body 以 `## [PRODUCES] x.md` 开头，L1215 `re.match(r"\[PRODUCES\]\s*(\S+)")` 仍 miss（`## ` 在前）→ 必须 SQL + 正则双改造（剥除 markdown 前缀后提取）。缓解：正则改 `r"(?:^|\n)\s{0,3}(?:#+\s*)?\*{0,2}\[PRODUCES\]\s*(\S+)"` 类形态，T11 加 cmd_chain 侧断言 |
| R5 | test_cmd_channel.sh 既有断言受波及 | 中低 | L621/636 断言 `LIKE '[PRODUCES]%'` 是**测试探针**（验证机器自写 comment 落库），机器自写恒锚定 → 不受影响；但 advance 全链测试若造 `## ` 前缀数据需同步。缓解：SUB-2 全量回归覆盖 |
| R6 | 前缀变体集合不穷尽（全角空格/缩进/引用块） | 低 | 白名单可增量扩展（helper 单点改）。缓解：helper 设计成常量驱动（_CLAIM_PREFIX_FORMS），后续新变体一行加入 |

## 4. 拆卡决策

|| 判定 | 结果 |
|------|------|
| 基准轮数 | 9-13 轮（中位 ~11） |
| DPL-018 校准后 | 22-32 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 2 个（机制改造 / 测试+回归）≥ 2 → 拆 2 卡合理 |
| 单卡方案复算 | base 9-13 → 校准 22-32 = 单卡 52-76% 预算，边际可单卡但风险集中（R1 语义裁决 + R2 语义修正 + 4 套回归全在一张卡）；且最近 5 卡 timed_out 前科 → 不选 |
| 本评估 2 卡方案 | SUB-1 基准 4-5.5 → 校准 10-13（13/42 = 31%）；SUB-2 基准 5-7.5 → 校准 12-18（18/42 = 43%）✅ |
| 依赖方向 | SUB-2 断言 SUB-1 的行为（前缀容差正/反例/短路面）→ 串行：SUB-1 合并进 main 后 SUB-2 才可测 |
| 并行收益 | 低——SUB-2 的 T11 断言依赖 SUB-1 的匹配语义定案；串行最稳 |
| 兜底 | SUB-1 若超预算：cmd_chain.py 改造可切独立 contingency（不影响 discover.py 主体）；SUB-2 若超预算：反例组（R1 红线）优先级最高，真库收敛断言可精简 |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_2717e1ae（DPL-063，1 行修复不拆）粒度太细；t_1db58772（DPL-069，40-70 行
跨仓改造 + 双仓 fixture）拆 2 卡同款。本任务 5+1 处 SQL 谓词族统一改造 + 语义修正 +
用例组，2 卡粒度与「机制/测试」分段对齐。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] claim 前缀容差匹配机制 — pipeline/discover.py 4 处 + cmd_chain.py 1 处：
   新增匹配 helper（白名单前缀集 _CLAIM_PREFIX_FORMS：裸 [CLAIM]/[PRODUCES] 锚定 +
   '## [CLAIM]'/'## [PRODUCES]' markdown H2/H3 变体 + '**[CLAIM]**' 加粗变体；
   禁止裸 %[CLAIM]% 全模糊——引用语「见子卡 claim」不得命中）；
   L1132 _claim_has_delivery_commit / L1172 _latest_claim_has_changed_files /
   L1284 _va_skip_reason / L1325 _va_skip_leave_trace 四处 SQL 谓词统一替换；
   L1176-1177 短路修正：锚定 miss 不再直接 return False，继续走条件 3（metadata
   claims/changed_files）与条件 4（交付 commit 兜底），与 docstring「1/2→3→4」OR 语义对齐；
   cmd_chain.py L1214 _extract_produces：SQL 同步容差 + L1215 正则剥 markdown 前缀后
   提取路径（SQL+正则双改造，缺一仍退化）；
   真库预演：修复前后对 t_4db0eb2d（skip_count=13）/t_1db58772（skip_count=18）
   锚定命中对比 → 修复后不再产 no-claim skip；
   docstring/头注释同步（判定顺序、前缀形态集）。
   预计 10-13 轮
2. [DEV-SUB-2] claim 前缀容差测试 + 全量回归 — scripts/test_va_backfill.sh 新增 T11
   （复用 build_fake_kanban/seed_task/seed_claim/run_scan harness）：
   T11 正例 3 变体（## [PRODUCES]/## [CLAIM]/**[CLAIM]** 前缀 claim 的 done 叶子卡
   → 不判 no-claim；含 file 产物 → 正常触发 VA 补扫建卡）；
   T11 反例（引用语「见子卡 claim」「参考 claim」不命中；裸 %CLAIM% 乱序不命中）；
   T11 短路面（metadata 有 claims + comment 锚定 miss → 条件 3 命中仍 True）；
   T11 真库收敛（t_4db0eb2d 形态 fixture：修复后 skip_count 不再递增/reason 收敛）；
   + cmd_chain 侧 advance 提取断言（## 前缀产物路径提取不退化）；
   + 全量回归（test_va_backfill 91→+T11 / test_watchdog_unify 28 / test_wip_progress_check 94 /
   test_cmd_channel [PRODUCES] 断言组 + python 导入冒烟）。
   预计 12-18 轮
```

- SPLIT: yes（count=2，校准后 22-32 轮超 20 阈值）
- MODE: serial（SUB-2 断言 SUB-1 语义，需 SUB-1 合并进 main）
- ROUNDS_EST（校准后）: 22-32（基准 9-13 × K=2.45；分卡后每张 10-13 / 12-18）
- FILES: pipeline/discover.py（改 4 处 + helper）+ pipeline/cmd_chain.py（改 1 处）+
  scripts/test_va_backfill.sh（增 T11）——3 文件
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 2 张子卡挂源卡 t_569d4425）
- TESTS: SUB-1 真库预演 + 冒烟；SUB-2 T11 约 15-20 断言 + 4 套全量回归
- RISK: R1 前缀过宽误匹配（白名单 + 反例测试）；R2 短路语义修正回归（T10 不破）；
  R3 va-skip 文件收敛（两案进 claim）；R4 cmd_chain 正则双改造；R5 cmd_channel 探针回归；
  R6 变体不穷尽（常量驱动可扩展）
- ACTION: build_two_dev_cards（assignee=game-engine，parents=[t_569d4425]，serial）

## 6. 备注

1. **部署验证不适用**：discover.py/cmd_chain.py 不在 DPL-048 must-sync 清单——生产链
   jobs.json → devppl_autopilot.sh → repo 路径 autopilot.sh L190 import，repo 合并即生效，
   无 live 副本同步依赖。（test_va_backfill.sh 同为 repo 路径执行，不适用。）
2. **验收 2 va-skip 收敛方案**（推荐案 a）：修复后 t_4db0eb2d/t_1db58772 的 claim 被
   容差命中 → 走 _latest_claim_has_changed_files 四条件（run metadata 含 claims+changed_files
   → 条件 3 命中）→ 不再 skip → skip_count 停止递增。旧注册文件保留为历史痕迹
   （first_skip_at/skip_count 反映修复前状态），不改写 reason 字段。案 b（手工重分类）
   留给 OC 裁定，不在本 [SUB-SPLIT] 内。
3. **68 张历史卡影响面**（验收 3）：修复后下一个 wake-check 窗口（默认近 7 天 done 卡）
   内的卡按新判定走——真有 file 产物的 markdown 前缀 claim 卡会补建 VA（预期行为，
   即 DPL-060 机制本意）；窗口外的旧卡天然不扫（时间窗控制），无需无差别全量补扫。
   评估结论：影响面 = wake-check 窗口内卡，非 68 张全量。
4. **同病第 6 处（cmd_chain.py:1214）超出卡面所列 5 处**，已纳入 SUB-1 修复面——
   不修则链 advance 的产物路径提取对 markdown 前缀 claim 仍盲。这是评估读码新增发现，
   与卡面「同链路第三层缺口」定位一致。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 2 张
   [DEV-SUB] 卡执行。
