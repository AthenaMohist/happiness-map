---
created: 2026-09-26T00:30:00+08:00
id: dpl167-patrol-v2-mechanism-attribution-prd
type: entity
page_type: project
project: "[[entities/devppl.md|devPPL]]"
status: active
updated: 2026-09-26T00:30:00+08:00
---

# PRD — 巡察使v2 机制级归因引擎：扫描口径重写 + LLM 归因 + 机制双链（DPL-162 迭代）

> 编号: DPL-167
> 作者: 许清楚（产品负责人）| 日期: 2026-09-26 | 版本: v1.0
> 来源: [CMD] 指令卡通道 — 本卡 t_f1c7cf96（Frank 指令：扫描口径重写+LLM归因+机制双链，DPL-162 迭代）
> 前链: DPL-162（巡察使闭环，chain_review.py M1-M10 已落 main @ devPPL）/ t_80367047（R5 FIX 三证据裁决管道，run 2078）
> 定位: DPL-162 解决了"坑被发现→定性→路由→回写"的流程闭环；DPL-167 解决"坑被看懂"——从事件级归因（这条 comment/这个 timeout）升级为机制级归因（这批信号同属哪个机制缺陷），让 lessons 台账从流水账变成可消费的机制缺陷清单。

---

## 0. 数据实证（2026-09-26 实测，本 PRD 立论基础）

| # | 实测 | 出处 |
|---|---|---|
| P1 | lessons-daily.md 现有 865 个坑行（904 处「待修复」标记），其中根因分类 **F5:未分类 492 行（57%）**——超过一半的坑归因引擎给不出机制结论 | wiki/actions/lessons-daily.md 统计（grep F[1-5] 计数） |
| P2 | 同一机制坑重复散落：「Iteration budget exhausted (60/60)」31 行、「OC 审 PRD blocked」71 行、「watchdog: 僵尸 running」18 行、「cc-glm doctor 四检」模板噪声 8 行——signal_hash 含 task_id+全文归一化，同机制不同卡永远无法聚合 | 同上（grep 计数）；scripts/chain_review.py `_norm_desc`/`signal_hash` :101-116 |
| P3 | 现归因是 pit_type→F1-F5 的**静态映射表**（PIT_CAUSE，11 条），只看信号来源不看内容语义：如 "Iteration budget exhausted" 因来源是 run_give_up 被归 F2（交付被打回），实际机制是轮次预算耗尽——分类与语义脱节 | scripts/chain_review.py :59-74 PIT_CAUSE |
| P4 | 台账无机制维度的入口：想回答「轮次预算机制今年修过几次、还复发吗」必须人肉 grep 全文；坑行与机制页之间没有双向链接，修了机制 A 不会回写它名下散落的坑行 | lessons-daily.md 表结构（坑描述|根因分类|涉及链与卡|修复状态|处置路由，无机制列） |
| P5 | F5 的两个子类（F5:循环型 / F5:未分类）合计 492 行正是 LLM 归因的目标带——机械规则能定 F1-F4 的（来源明确），定不了的堆在 F5 | scripts/chain_review.py PIT_CAUSE + lessons 统计 |

**结论**: 流程闭环已通（DPL-162），断点在归因质量——① 分类是来源映射不是语义理解（P3），② 同机制坑无法聚合（P2），③ 机制无台账无双链（P4）。三段补齐，巡察使从"记录员"升级为"归因分析员"。

## 1. 用户故事

- **作为 Frank**，我看 lessons 台账想知道「哪 3 个机制缺陷吃掉了最多的轮次预算」——台账应有机制聚合视图：机制A 名下 31 个坑、横跨 12 张卡、修复 2 次仍复发，而不是 31 行一模一样的流水。
- **作为 OC**，我处置告警想知道「这是不是已知机制的又一次复发」——归因应自动给出「机制: iteration-budget-exhausted，判例: DPL-145/167 两次修复记录」，而不是让我每条重新读。
- **作为产品**，我复盘要知道「修了 DPL-145 硬停后，iteration budget 类坑是否下降」——机制页应有坑行双向链，修复落地后名下坑行可批量回写。

## 2. 目标 / 非目标

**目标**
- G1 扫描口径重写: signal_hash 去重键与聚合键分离——signal_hash 保留（卡级精确去重，回写锚点不变），新增 mechanism_key（pit_type + 归一化机制指纹，见 R1）。聚合单位从"同卡同描述"升级为"同机制跨卡"。
- G2 LLM 机制归因: 对 F5 带（及高价值 F1-F4 复核）调用 LLM（cc-glm 端点，GLM Anthropic 代理，与 devPPL 既有 cc 通道同源）输出机制标签——受控词表（mechanism taxonomy，约 15-25 个机制：iteration-budget-exhausted / watchdog-zombie-running / prd-review-gate-loop / exec-mode-missing / card-audit-false-positive / registry-gap / cc-channel-failure / merge-conflict-loss 等，词表本身落在 wiki 可演进页）。LLM 失败/超时/输出不在词表 → fail-open 落 `F5:未归因`，绝不阻塞主流程（DPL-162 AC8 纪律延续）。
- G3 机制双链: lessons 坑行新增「机制」列（mechanism_label）；新建机制页目录 wiki/actions/mechanisms/<mechanism-key>.md——机制页正向链：定义+判例+历次修复 commit；坑行反向链：`[[mechanisms/<key>]]`。机制页由脚本机械生成/追加，不手写。
- G4 机制聚合视图: lessons-daily 头部追加「机制汇总表」（机制 | 坑数 | 涉卡数 | 最新修复状态），每 run 幂等重算（按 mechanism_key 重扫全表，不依赖增量）。
- G5 回写联动: writeback_fix_status 修复回写时，若坑行带机制标签 → 同机制页追加修复记录行（commit+日期）；修复状态批量视图随之更新。

**非目标**
- 不改 DPL-162 的三证据裁决/分级路由/执行器逻辑（route_fix、route_action 原样）——v2 只改"归因与呈现"层，不动"路由与执行"层。
- 不用 LLM 做定性（confirmed/refuted 仍走机械三证据）——LLM 只产出机制标签，不定性不定路由，避免把裁决权交给概率组件。
- 不回填重写历史坑行的分类列（历史 F1-F4 保留）；历史 F5 行由 G4 聚合视图自然吸收，不逐行改写。
- 不新增 cron/watchdog——挂进 dpl162_daily.sh 既有 06:30 流程。

## 3. 需求明细（R1-R5 对应 G1-G5）

### R1 扫描口径重写（改 chain_review.py：mechanism_key + 聚合拆分）
- `mechanism_key(pit)` = `f"{pit_type}:{mechanism_label}"`；mechanism_label 初值 = 现有静态映射（机械层），LLM 归因后覆盖（语义层）。
- aggregate_pits 增加二级聚合：现有组（signal_hash 级，供去重与回写）之上新增 mechanism 组（mechanism_key 级，供 G4 汇总表）。lessons 行级去重逻辑不变。
- 机制指纹归一化：描述中抽 task_id/时间戳/数字（60/60、commit sha、N 分钟）替换为占位符后再比对，同模板不同参数归同机制。

### R2 LLM 归因（新增 attribute_mechanism()，独立模块或同文件函数均可）
- 触发范围：verdict=confirmed 或 count>=2 的组代表，且机制标签为 F5 系（未分类/循环型）——控制调用量（P1 实测该带占 57%，但去重后组数远小于行数）。
- Prompt 契约：输入 = 坑描述（去敏后）+ 现有机械分类 + 机制词表；输出 = 单一 mechanism_key + 置信度（high/low）。词表外输出 = 拒收落 `F5:未归因`。解析失败/端点失败 = fail-open 跳过打日志。
- 预算守卫：单 run LLM 调用上限（env CHAIN_REVIEW_LLM_BUDGET，缺省 20 次），超限组直接落未归因，防端点费用失控。
- 端点：复用 cc-glm 通道配置（ANTHROPIC 代理 /workspace/anthropic_proxy.py 口径），env 可覆盖；离线环境 = 全部 fail-open 落未归因，机制聚合仍工作（退化为机械标签粒度）。

### R3 机制双链（新增机制页目录 + 坑行列）
- 目录 wiki/actions/mechanisms/；页 frontmatter：mechanism_key、definition、status(active/fixed)；正文节：定义 / 判例与历次修复（追加式） / 名下坑行（signal_hash 短链表）。
- lessons 坑行表新增「机制」列：渲染 `[[mechanisms/<key>|<key>]]`；未归因渲染 `F5:未归因` 纯文本。表结构变更需同步 update_lessons_page 的行渲染与 seen 去重（幂等：旧行无机制列不重写）。

### R4 机制汇总视图（update_lessons_page 内新增 render_mechanism_summary()）
- 全表重扫（读 lessons-daily.md 现有行 + 本轮组）→ 机制汇总表（机制 | 坑行数 | 涉卡数 | 待修复数 | 最新修复 commit）插在表头之下；每 run 重算覆盖写，天然幂等。
- 汇总表行数守卫：>40 机制时只列坑数 Top-40 + 「其余 N 机制」行（防机制词表膨胀打爆页首）。

### R5 回写联动（改 writeback_fix_status / auto_writeback）
- 修复回写命中坑行后：若行带 mechanism_key → 机制页「判例与历次修复」节追加一行（日期 + commit + signal_hash[:12]）；机制页不存在则按 R3 模板创建。
- close 校验不加新项（机制页是派生产物非登记物，避免 REGISTRY-GAP 误拦）。

## 4. 验收标准

| AC | 内容 | 验证口径 |
|---|---|---|
| AC1 | mechanism_key 聚合正确：同机制跨卡信号归入同 mechanism 组 | 单测：构造 3 卡同模板坑（Iteration budget exhausted 变体）→ mechanism 组 count=3、signal_hash 各异；pytest tests/test_chain_review.py -k mechanism |
| AC2 | LLM 归因受控词表 + fail-open：词表内标签采信，词表外/端点失败/超预算 → F5:未归因 且主流程 0 异常 | 单测（mock 端点）：正常返回/词表外返回/连接失败/超预算四例；断言 attribute_mechanism 输出与 lessons 行不中断 |
| AC3 | 机制双链落地：坑行含 [[mechanisms/<key>]]，机制页含定义+修复节+坑行短链；二次运行幂等（无重复追加） | 单测 + 真实数据 dry-run：chain_review.py --dry-run 后机制页/坑行可 grep；连续跑两遍 diff 为空（除新增坑） |
| AC4 | 汇总视图与回写联动：汇总表数字与全表行一致；writeback_fix_status 后机制页追加修复行 | 单测：构造 5 行 2 机制 → 汇总表 2 行数字正确；mark-fixed 一行 → 机制页 +1 修复行，再跑不重复 |
| AC5 | 回归不破坏 DPL-162 既有行为：route_fix/route_action/三证据/lessons 去重回写测试全绿 | pytest tests/test_chain_review.py -q（本卡子集=全文件，该文件即本功能域套件）；git grep 实锤 main + 备份推送（MERGE 卡职责） |

测试纪律：只跑 tests/test_chain_review.py 域内子集；mock LLM 端点不真网；不跑全量 pytest（DPL-137）。

## 5. 依赖与风险（产品上报段）

- **D1（LLM 端点可用性）**: cc-glm 通道历史上出现额度耗尽/通道故障（lessons 中 cc-channel 类坑多次）。设计已按"端点缺席=全 fail-open 退化"兜底（R2），但若长期无可用端点，G2 语义归因形同虚设、v2 退化为 G1/G3/G4 的机械改进——需 Frank 知悉此降级形态仍可交付。
- **D2（机制词表漂移）**: 词表放 wiki 可演进页（G2），但词表膨胀会稀释标签质量。约束：新增机制须在机制页有判例支撑（≥1 真实坑行），由 PRD/OC 审核进词表，LLM 不得自造词（R2 词表外拒收已机械保证）。
- **D3（历史 F5 不回填）**: 492 行历史 F5 只有新采集信号才走 LLM 归因（R2 触发范围限本轮组）。产品拍板：不批量回填——回填无用户故事支撑且消耗预算；汇总视图（G4）已能给机制级全景。
- **D4（lessons 表结构变更）**: 加「机制」列影响所有消费 lessons 的下游（GAI/人工阅读）。旧行无列不重写（幂等），渲染层兼容空列——MERGE 卡需验证 dry-run 输出旧区段 diff 为零。

## 6. 拆卡建议（供 OC 建卡，本卡不越权建卡）

| 子卡 | 内容 | 建议指派 | 依赖 |
|---|---|---|---|
| S1 | R1 mechanism_key + 二级聚合 + 机制指纹归一化 + AC1 单测 | game-engine | 无 |
| S2 | R2 LLM 归因（mock 可测）+ R5 回写联动 + AC2/AC4 单测 | game-engine | S1 |
| S3 | R3 机制双链 + R4 汇总视图 + AC3 单测 | game-engine | S1 |
| S4 | AC5 回归 + 真实数据 dry-run 实证 + MERGE 落 main + 备份推送 | autopilot | S2, S3 |

## 7. 关联

- [[dpl162-patrol-closed-loop-prd]]（巡察使闭环 v1，本卡直接上游——流程层已闭环，本卡补归因层）
- [[dpl158-timeout-patrol-prd]]（超时观察层，链路更上游）
- [[actions/MEM-016]]（[OC-DIAG] 格式——机制页判例节复用其证据链风格）
- [[concepts/patterns/kanban-card-format]]（建卡铁律 / 编号继承）
- 本卡: t_f1c7cf96
