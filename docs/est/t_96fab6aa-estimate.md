# 评估报告 — [DEV-EST] MEM-009 策展死锁修复补投 — resolve_wikilink 冒号/裸id 修复沙箱迁移丢失（DPL-092 复发）

> 评估人：寇豆码（game-engine） | 日期：2026-08-30 | 评估卡：t_96fab6aa | 源链：MEM-009（CMD t_534908cd → PRD t_c987e3ef → arch t_d1445c72）
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 上游交付：PRD v1.0（af49973）+ 架构 v1.0（6d4bd87，D1-D10 定稿，DEV 交接清单 8 项见 arch §8）
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 全撞 60 上限）

## 1. 结论（TL;DR）

**拆 4 张串行子卡（校准后每张 13-18 / 22-32 / 12-20 / 10-16 轮，全部落在 42 有效轮预算内）。**

任务本质：DPL-092 修复三件套（resolve_wikilink 五级 / lint I5⑥ v5 / 9 页 task_code 原值）在 08-26
沙箱销毁中随未 push 本地历史丢失后的**原样补投**（补投 ≠ 重设计）。架构已把全部精确改点定稿
（arch §2.2 parse 改点 / §3.2 lint 改点 / §4 裁定表 / §5 DPL-092 占位页规格 / §8 交接 8 项），
dev 侧无需再做设计裁决，主要是**按图施工 + 验证**。

**评估期间实测关键事实（决定拆卡与风险走向，非假设）：**
- **A8 push 门禁当前沙箱不可满足**：`git ls-remote origin HEAD` → `Permission denied (publickey)`，
  origin = git@github.com:AthenaMohist/mem-core.git。架构卡已呈 OC 一次，本卡再次确认——**push 阻塞
  必须独立成卡**（SUB-4），否则拖累 R3 数据恢复；SUB-4 若 push 失败须如实报告 OC 等待，不伪造成功。
- **mem-core 无 worktree 基建**（`git worktree list` 仅主树 main，先例 dev 卡直接 main 提交）→
  **R1/R2 不能并行**（并行 = 双 worker 抢 main 工作树，违反 2026-08-13 工作区隔离规范）→ 全串行。
- **R2→R3 顺序硬约束**（Frank 裁定：提前恢复 task_code 会触发旧规则 I4 阻断）→ R3 独立成卡天然满足
  「R2 done 后才 claim」的前置门。
- **改动面全部落点已核实**（实读 mem-core main @ 6d4bd87）：parse.py L180 四级无兜底；lint.py L366
  白名单缺 note/demote；L405-417 同值 ERROR 在位；run() L349 挂 I4；render() L49 无 I5；test_lint.py
  L565 test_t12_id_mismatch 断言同值 ERROR（须三态反转）；test_parse.py 现有 4 个 resolve 用例；
  probe 脚本 .pipeline/tmp/probe_resolvewikilink.py 可复跑。

## 2. 工作量评估（读码结论，非假设）

改动面（按架构定稿，dev 侧零设计决策）：
- **R1**：`memcore/parse.py` resolve_wikilink（L180-217）加 L0 id 兜底（含冒号，置最前）+ L4 casefold
  basename 改造 + docstring；`tests/test_parse.py` +4 用例（冒号 id 命中/裸 id 命中/路径回归/未命中 None）。
- **R2**：`memcore/lint.py` 拆 `_task_code_errors`（新函数，索引一致性 D3 三态）+ 删 L416-417 同值 ERROR
  + I5 bucket（run() L349 调用处挂 I5、render() L49 加 "I5"）+ `_mechanical_skeleton` 白名单恢复
  note/demote（D4，一行 + 测试扩）；`tests/test_lint.py` test_t12_id_mismatch 三态改写 + 骨架豁免用例扩；
  `wiki/SCHEMA.md` 5 语义点（L57/L85/L173-174/L176）+ `wiki/concepts/patterns/WIKI-001.md` 3 处（D9）。
- **R3**：9 页 task_code 按 Frank 裁定表恢复（memctl 单一写入者 + 简注可 blame）+ DPL-092 占位页
  memctl add（task_code=MEM-009，≥2 出链）。
- **A7/A8**：e2e 降级冒烟（夹具产物含冒号 id/裸 id 双链 → learn/lint 全绿 + 降级留痕）+ 修复报告 +
  claim + 飞书 + push origin（阻塞风险）。

| | 子卡 | 工作项 | 基准轮数（未校准） | 依据 |
|---|------|--------|:---:|------|
| ① | SUB-1 R1 parse 五级 + 4 单测 | 读现状 + 对照 arch §2.2 精确改点 1；实现 L0+L4+docstring 1-1.5；写 4 用例 1.5-2；pytest 定向 + 修破 1-1.5；probe A 节复跑 + memctl lint 冒烟 1-1.5 | **5.5-7.5** | parse.py L180-217 实读；test_parse.py 现有 4 用例实读；probe 脚本在 .pipeline/tmp 可复跑；arch §2.2 已给出逐行形态 → 无设计成本 |
| ② | SUB-2 R2 lint I5 v5 + 文档同步 | 读 lint.py 结构 1-1.5；_task_code_errors 拆分 + 三态分支 + I5 bucket 2-3；render L49 + LintResult 注释 0.5；test_t12 三态改写 + note/demote 豁免扩 2-3；SCHEMA 5 点 + WIKI-001 3 处 1.5-2.5；全量 pytest + memctl lint + A6 三方对账 2-3 | **9-13** | lint.py L40-48/L347-350/L366-375/L405-417 实读；test_lint.py L501-600 实读；SCHEMA/WIKI-001 残留行号 arch §3.4 已定位；四不变式回归面全量 pytest + lint（PRD A3） |
| ③ | SUB-3 R3 数据恢复 + 占位页 | 前置断言 R2 在 main 0.5；9 页 frontmatter 编辑（memctl）+ index 2-3.5；DPL-092 页 memctl add 1-1.5；lint 全仓 + 逐行 diff + git 时序 1.5-2.5 | **5-8** | 裁定表 arch §4.1 逐行给出；9 页现存实读（PRD §1.2 #5）；memctl 单一写入者流程；R2 之后时序证明 = git log 检查 |
| ④ | SUB-4 A7/A8 闭环 | 夹具产物页 + learn/lint 冒烟 + 降级留痕 2-3；修复报告 + claim + changed_files 1.5-2.5；飞书 + complete 0.5-1；push origin（阻塞风险）0-∞ | **4-6.5** | arch §6.3 降级形态已定（D6）；报告格式 PRD R4-4；push 实测 publickey 拒绝 → 若 OC 未处理 key 则卡在 A8 |

**基准轮数（未校准，合计）：23.5-35 轮（中位 ~29）。**
**DPL-018 校准：23.5-35 × K=2.45 → 校准后 58-86 轮** —— 远超单会话 42 有效轮 → **必须拆卡**
（且按「>30 有效轮必须拆」红线，23.5-35 基准本身已超 20 轮阈值 → 拆 4 张）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | **A8 push origin 不可满足**（实测 publickey 拒绝） | **高** | 验收门禁 A8 =「origin/main 可见修复 commit」当前沙箱无法达成。缓解：SUB-4 独立成卡；push 失败 → 如实呈 OC（卡已呈过一次，机制面 arch §6.2 选项 A/B/C 待 OC 裁定）；不伪造成功。若 OC 提供可用 SSH key，SUB-4 补推即可 |
| R2 | R3 先于 R2（旧规则 I4 阻断） | 高 | 顺序硬约束（Frank 裁定原文）。缓解：串行链 + R3 卡前置断言「先跑 lint 确认 I5⑥ v5 在位」+ A5 git 时序证明 |
| R3 | lint.py 改动引发四不变式回归 | 中 | 改动面限定 task_code 块（拆独立函数），结构校验路径零改动；A3 全量 pytest + memctl lint RC=0 门禁 |
| R4 | test_t12 语义反转漏改 → 旧断言红 | 中 | v5 与 v4 语义完全相反（同值 ERROR → 同值 PASS）。缓解：三态夹具显式覆盖 ≠id 指向真实页 PASS / 指向不存在 ERROR / 同值 PASS；全量 test_lint.py 回归 |
| R5 | 五级顺序与 5288069 原实现有偏差 | 中低 | 架构已锁验收行为（A1/A2）不锁层级序；单测锚定行为；devPPL v4.1 幸存件对账（A6） |
| R6 | 9 页恢复遗漏/笔误 | 低 | 严格按裁定表 9 行逐行 diff；样例断言 DPL-070==MEM-009；v5 上线后索引一致性对账自然暴露遗漏 → 报告 OC |
| R7 | mem-core 无 worktree 基建 → 并行抢 main | 中 | 已裁决全串行（隔离规范 2026-08-13）；每卡独占 main 写权 |
| R8 | e2e 冒烟依赖未接线环境 | 低 | 架构 D6 已裁定降级形态（夹具 + 单测 + lint），降级留痕 conv_curate 未接线 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 23.5-35 轮（中位 ~29） |
| DPL-018 校准后 | 58-86 轮（×K=2.45）**> 20 轮阈值 → 必须拆卡**；且基准本身 >20 → 必须拆 |
| 交付物数 | 6 类（引擎代码 / 测试 / 数据恢复 / 文档同步 / e2e 冒烟 / 闭环报告）≥ 4 → 拆 ~3 卡（此处 4 卡更贴合） |
| 单卡方案复算 | 单卡 58-86 校准轮 = 138-205% 预算 → 不可能 |
| 3 卡方案复算 | SUB-3 合并 R3+A7/A8 后校准 22-36 = 52-86% 预算，且 push 阻塞会拖累 R3 → 不选 |
| **本评估 4 卡方案** | SUB-1 校准 13-18（31-43%）；SUB-2 22-32（52-76%）；SUB-3 12-20（29-48%）；SUB-4 10-16（24-38%）✅ |
| 依赖方向 | R2→R3 顺序硬约束（Frank 裁定）；A7/A8 依赖 R1+R2+R3 全部合入 → **全串行** |
| 并行收益 | 理论 R1∥R2 可省 ~0.4 会话，但 mem-core 无 worktree 基建 + 隔离规范禁双 worker 持 main 写权 → 并行不可行 |
| 兜底 | SUB-2 若超预算：SCHEMA/WIKI-001 文档同步可切独立 contingency（不阻塞 lint 规则合入）；SUB-4 若 push 阻塞：卡 block 等 OC，R1-R3 不受影响 |

**决策：拆 4 张串行子卡（[SUB-SPLIT] 4 serial）。**
量级参照：t_569d4425（DPL-087，2 卡同款结构）；本任务比它多数据恢复 + 占位页 + push 门禁三块，
4 卡粒度与「R1 引擎 / R2 规则+文档 / R3 数据 / A7A8 闭环」四段对齐，每段一个可独立验收的单元。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 4 serial
1. [DEV-SUB-1] R1 resolve_wikilink 五级恢复 + 回归单测 — memcore/parse.py L180-217：
   按 arch §2.2 精确改点（L0 id 兜底含冒号置最前 + L4 casefold basename 兜底置最后，L1-L3 现行
   语义零改动）+ docstring 同步「四级→五级」；tests/test_parse.py 新增 4 用例（冒号 id 命中
   pages_by_id→file_path / 裸 id 命中→file_path / 路径形态回归 / 未命中→None，原 4 用例保留）；
   复跑 .pipeline/tmp/probe_resolvewikilink.py A 节两个 None case→返回 file_path；
   pytest tests/test_parse.py 全绿 + memctl lint 四不变式 RC=0（A1/A2/A3）。
   预计 13-18 轮
2. [DEV-SUB-2] R2 lint I5⑥ v5 收窄 + SCHEMA 同步 — memcore/lint.py：
   拆独立函数 _task_code_errors(page, pages_by_id)（索引一致性三态：≠id 命中 pages_by_id→PASS /
   未命中→ERROR「指向的任务页不存在」/ 同值→PASS；缺省非骨架→ERROR 保留）+ 删除 L416-417 同值
   ERROR + 调用处 run() L349 改挂 Issue("I5",...)（非 task_code 结构错误仍挂 I4）+ render() L49
   循环增 "I5" + LintResult 注释；_mechanical_skeleton 白名单恢复 note/demote（D4）；
   tests/test_lint.py test_t12_lint_i5_id_mismatch 改写三态 + 骨架豁免用例扩 note/demote；
   wiki/SCHEMA.md 5 语义点（L57/L85/L173-174/L176）+ wiki/concepts/patterns/WIKI-001.md 3 处
   v4→v5（D9）；A6 三方对账（SCHEMA↔lint.py↔devPPL v4.1 grep 关键句一致）；
   全量 pytest + memctl lint RC=0（A3/A4/A6）。
   预计 22-32 轮
3. [DEV-SUB-3] R3 9 页 task_code 数据恢复 + DPL-092 占位页补建（严格在 R2 合入后）：
   前置断言：先跑 lint 确认 I5⑥ v5 规则在位（旧规则下禁止动数据，Frank 裁定）；
   9 页按 arch §4.1 裁定表逐行恢复（DPL-070→MEM-009 / DPL-056→MEM-007 / DPL-058→MEM-007 /
   DPL-060→DPL-058 / DPL-061→DPL-019 / DPL-071→MEM-009 / DPL-059→ALV-006 / DPL-069→DPL-070 /
   DPL-077→DPL-075），走 memctl 单一写入者（页面编辑→index→commit）+ 简注可 git blame 追溯；
   wiki/actions/DPL-092.md 占位页 memctl add（task_code=MEM-009，status=done，source_task=t_f79ee9ef，
   mechanism=memctl add，≥2 出链）；lint RC=0 + 逐行 diff == 裁定表 + 样例断言 DPL-070==MEM-009 +
   git 时序证明恢复在 R2 合入之后（A5）。
   预计 12-20 轮
4. [DEV-SUB-4] A7/A8 端到端闭环 — e2e 降级冒烟 + 报告 + push：
   夹具产物页含「来源对话: [[<冒号id>]]」+ 裸 id 双链 → memctl learn/lint 全绿 rc=0（降级形态
   留痕：conv_curate 未接线，arch D6）；修复报告（改了什么/为什么/测试证据）+ claim（含
   changed_files）+ 飞书推送；合入 main 后 push origin（A8 门禁；⚠️ 实测 publickey 拒绝 → 先
   尝试 push，失败则如实报告 OC 等待，不伪造成功）。
   预计 10-16 轮
```

- SPLIT: yes（count=4，校准后 58-86 轮超 20 阈值；基准本身 23.5-35 也超）
- MODE: serial（R2→R3 顺序硬约束 Frank 裁定；mem-core 无 worktree 基建禁并行；A7/A8 依赖全部合入）
- ROUNDS_EST（校准后）: 58-86（基准 23.5-35 × K=2.45；分卡后每张 13-18 / 22-32 / 12-20 / 10-16）
- FILES: memcore/parse.py + tests/test_parse.py + memcore/lint.py + tests/test_lint.py +
  wiki/SCHEMA.md + wiki/concepts/patterns/WIKI-001.md + wiki/actions/DPL-092.md（新建）+
  9 页 actions/*.md（task_code 恢复）——mem-core 仓
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 4 张子卡挂源链）
- TESTS: SUB-1 pytest test_parse（+4 用例）+ probe A 节；SUB-2 test_lint 全量（test_t12 三态改写）；
  SUB-3 逐行 diff + lint RC=0 + git 时序；SUB-4 夹具 learn/lint 冒烟
- RISK: R1 push 阻塞（A8 无法闭环 → 呈 OC）；R2 R3 顺序违规（硬约束 + 前置断言）；R3 四不变式回归
  （A3 全量）；R4 test_t12 语义反转漏改；R5 五级顺序偏差（锁验收行为）；R7 无 worktree 基建（串行）
- ACTION: build_four_dev_cards（assignee=game-engine，parents=[t_d1445c72]，serial，mem-core 仓）

## 6. 备注

1. **push 阻塞是本链最大风险**（R1 高）：arch 卡已实测并呈 OC（「push origin 实测 publickey 拒绝」），
   本评估卡复测确认（git ls-remote origin HEAD → Permission denied）。SUB-4 的 A8 验收在 OC 提供可用
   push 通道前无法闭环；若 OC 选择先降级验收（本地 main commit + 报告），SUB-4 留痕即可，机制面
   （arch §6.2 选项 A/B/C）仍归 OC 裁定——**dev 不擅自建 cron、不伪造 push 成功**。
2. **部署验证规则不适用**：本链改动在 mem-core 仓（python 库 + wiki 页 + memctl），不在 DPL-048
   must-sync 清单（/root/.hermes/profiles/orchestrator/scripts/ 下 cron 直调 .sh）；memcore 包走
   repo 路径执行，repo 合并即生效，无 live 副本同步依赖。
3. **dev 开发方式**：mem-core 无 worktree 基建，先例（5288069/6254f62）为直接 main 提交；串行链下
   每卡独占 main 写权，不违反隔离规范。若 OC 要求分支开发，需先建 mem-core worktree 基建（本链不建）。
4. **本评估卡不写功能代码**；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 4 张 [DEV-SUB]
   卡执行。子卡挂 parents=[t_d1445c72]（arch 已完成 → 可立即 ready）。
5. **历史偏差反思**：最近 5 卡估 18-33 全撞 60 上限（+1.03~+1.61），本卡按 K=2.45 校准后分卡，
   单卡最大 22-32（52-76% 预算）——仍留 24-48% 缓冲应对 60/60 前科。
