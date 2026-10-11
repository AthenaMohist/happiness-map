---
created: 2026-10-03T00:40:00+08:00
id: dpl199-patrol-daily-judgment-template-prd
type: entity
page_type: project
project: "[[entities/devppl.md|devPPL]]"
status: active
updated: 2026-10-03T00:40:00+08:00
---

# PRD — 巡察使日报按「旧坑复发/新坑/处置状态」模板重写——报告要给出判断不是行数（DPL-199）

> 编号: DPL-199
> 作者: 许清楚（产品负责人）| 日期: 2026-10-03 | 版本: v1.0
> 来源: [CMD] 指令卡通道（Frank 2026-08-11 裁定 2 类型化建链）— 源卡 [[actions/DPL-199.md]] → 本卡 t_f832725f
> 议题: 巡察使日报按「旧坑复发/新坑/处置状态」模板重写——报告要给出判断不是行数
> 定位: **只改日报文本层（timeout_ledger.py format_daily_report + 一个坑指纹比对模块），不动扫描器 timeout_patrol.py 采集逻辑、不动 chain_review.py**。Frank 要的是"打开日报 10 秒内知道：老的坑有没有复发、冒了什么新坑、处置到哪一步了"，每段开头必须是一句判断，行数只是判断的证据，不是判断本身。
> 北极星对齐: 日报从"数据搬运工"升级为"值班分析员"——零坑日一句话放行，有坑日给出结论+建议动作，判断错了有据可查。

---

## 0. 数据实证（2026-10-03 实测，本 PRD 立论基础）

| # | 实测 | 出处 |
|---|---|---|
| P1 | 现行日报五段模板（①台账计数 ②存档铁律执行率 ③派修 ④ESCALATE ⑤其余动作）①段是纯行数罗列："昨日异常 N（timed x/gave_up y/僵尸 z/retry d），分类 F2 1，Top3: …"——**没有一句话回答"这正常吗、要不要管"** | timeout_ledger.py:408-478（format_daily_report） |
| P2 | 今日实测扫描：timed_out 1 张（t_5f115816，F2，rounds=60，cp_round=0 → 存档铁律 0%），repeat 4 张全部 task_status=done（t_3fa2c263 ×3 / t_428e72c4 ×2 / t_6fdb4bd0 ×2…）。**repeat 卡全部已 done 意味着"修过的坑又超时"，但日报只给 ×N 计数，不判"复发"，读者无从知道这是旧账还是新伤** | timeout_patrol.py --dry-run 实跑 2026-10-03 |
| P3 | 台账与派修管道互相矛盾且日报沉默: lessons-daily.md 有 **909 行含「待修复」**（vs 仅 20 行已修复），而 patrol_fix_agenda.log 连续多日输出「无未修坑待派」——根因是 agenda v2 过滤器只认含 `[[oc-pitfall-log-*]]` 双链的行，绝大多数坑行没有双链 → **派修管道实际失灵，但日报③段永远显示"无"，报告层没有能力发现这个矛盾** | wiki(devPPL)/actions/lessons-daily.md 统计 + logs/patrol_fix_agenda.log |
| P4 | error 字段零区分度依旧: 今日超时 run error 全部为 "Iteration budget exhausted (60/60)"，分类器把 rounds=60 无重复信号的默认归 F2——F2 成了"什么都不知道"的代名词，日报给读者的是分类行数而非根因判断 | scan 实测 `_error` 字段 |
| P5 | 存档铁律执行率仅覆盖超时坑一类；lessons 台账 909 待修复坑没有任何复发判定入口——「预防方案生效情况」列在 timeout 台账有机制（7 天复发回填），lessons 坑台账完全没有对应物 | timeout_ledger.py:68 vs lessons-daily.md |

**结论**: 采集层和台账层都已存在（scan 四类采集 + lessons 909 行 + timeout 台账复发回填），断点在**报告层没有做判断的义务**——它把行数原样搬给 Frank，却不回答"旧坑是否复发/新坑是什么/处置是否闭环"。本卡不改采集，只重写报告层，并要求每段开头给出可被反驳的判断句。

## 1. 用户故事

- **作为 Frank**，我每天 30 秒扫完日报：第一行告诉我"昨天的坑有没有复发"（判断），第二行告诉我"有没有新坑、什么性质"（判断），第三行告诉我"已在处置的坑走到哪了、有没有卡死"（判断）。行数和卡号是折叠在判断下面的证据，不是我自己的功课。
- **作为 OC**，我想要日报替我做第一轮复核——"这个 repeat ×3 的卡已经 done 了"应被判为「旧坑复发嫌疑」并给出建议动作（复核修复 commit），而不是一行 `t_3fa2c263 ×3` 让我自己去查。
- **作为产品**，我需要日报能暴露系统级矛盾（如 P3 的"909 待修复 vs 派修 0"）——这种矛盾就是下一张 PRD 的选题来源，现在的报告结构性地看不见它。

## 2. 目标 / 非目标

**目标**
- G1 三段判断模板: 日报正文重写为固定三段，**每段第一行必须是判断句**（结论+依据摘要），证据行折叠其后。零事件日整报一行放行（保留信号存在）:
  - 段一「旧坑复发」: 扫描命中项与坑台账（lessons-daily + timeout 台账）已记录坑做指纹比对——命中已修复/已处置坑 = 复发（判断: 预防失效，点名校验修复 commit）；命中未修复坑 = 存量延续；无命中 = 「旧坑 0 复发，预防生效」。
  - 段二「新坑」: 扫描命中项在两台账均无指纹匹配 = 新坑（判断: 定性结论或 [待定性]+缺什么证据），新坑必须给"建议动作"（上报/OC 直修/建卡，沿用 DPL-162 R5 路由口径）。
  - 段三「处置状态」: 对已路由坑（修复卡/OC 直修/ESCALATE/修复中）报闭环进度——判断句形式（如"7 个修复中坑里 2 个超 7 天无进展，建议升级"），并**强制核对派修管道活性**: lessons「待修复」行数 >0 而 agenda 报「无未修坑待派」时必须输出矛盾告警（P3 实锤的失灵检测）。
- G2 坑指纹（复用而非新造）: 以 signal_hash（timeout_ledger/chain_review 现有 pit_type+归一化描述）为主键、normalize_signal(error) 为辅键，建坑指纹索引（scan 时内存构建，读两台账 + lessons_seen.json，只读不写台账）。比对纯函数独立可测。
- G3 复发判定规则（纯函数）: 已修复坑 + 指纹再命中 = 复发；判定须附证据引用（task_id + run_id + 命中信号），禁止只给结论不给出处。证据 <2 源（DPL-162 R4 口径）标 [待定性] 不写死"复发"。
- G4 零破坏兼容: 五段模板中的硬信号不得丢失——存档铁律执行率、FRANK-ESCALATE、环比快照全部保留，折叠进三段内（执行率并入段一证据、ESCALATE 保留独立强推通道不动，只改正文文本）。
- G5 判断句可测试: 每段判断句由纯函数从结构化输入生成（judge_recurrence/judge_new_pits/judge_disposition 三函数），单测覆盖"复发/未复发/待定性/矛盾告警/零事件"各分支的输出文案形态。

**非目标**
- 不改 timeout_patrol.py scan() 采集口径、不改 F1-F5 分类器（分类器升级另行立卡——P4 的 error 零区分度是真问题但属采集层）。
- 不改 lessons-daily 写回逻辑、不补 909 行的双链（那是台账层欠账，本卡只在日报里报矛盾，修管道归后续卡）。
- 不改飞书通道/去重/重试机制（seen/mark、retry marker 原样）。
- 不做 LLM 生成判断句——判断规则全部机械可测，宁可保守标 [待定性] 不猜。

## 3. 方案（R1-R5）

### R1 坑指纹索引（G2）
`scripts/patrol_pit_index.py`（新模块，供 timeout_ledger import）:
- `build_pit_index(lessons_path, forensics_path, seen_path) -> dict[signal_hash, pit_record]`：只读解析 lessons-daily 表行（坑描述+根因分类+修复状态列）与 timeout-forensics 台账行 + logs/lessons_seen.json 的 signal_hash。lessons 行无 signal_hash 时按坑描述归一化（去数字/截 40 字，复用 normalize_signal 规则）降级生成。单源缺失 fail-open 空索引。
- 匹配 `match_pits(entries, index) -> {recurrence: [...], new: [...], ongoing: [...]}`：命中已修复/已处置 → recurrence；命中待修复 → ongoing；未命中 → new。

### R2 三段判断函数（G3/G5）
timeout_ledger.py 新增三个纯函数，输入 scan result + pit index，输出 {judgment: str, evidence: [...]}:
- `judge_recurrence`：recurrence 逐条给"坑描述 + 原修复 commit/处置 + 本次命中 task_id/run_id"；全空输出「旧坑 0 复发，预防方案生效（含 X 个存量延续监控中）」。存档铁律执行率作为段一固定尾注（证据位）。
- `judge_new_pits`：new 逐条给"定性（三证据计数，不足标 [待定性]）+ 建议动作"；全空输出「新坑 0」。repeat 且 task_status=done 的条目按 P2 口径计入复发嫌疑而非新坑。
- `judge_disposition`：ongoing/修复中坑的进展聚合 + 派修活性矛盾检测（lessons 待修复数 vs agenda 输出/建卡记录，读 logs/patrol_fix_cards.json 与 agenda 日志尾行）→ 矛盾时判断句「派修管道疑似失灵: 台账 N 待修复 vs 派修 0」。

### R3 日报文本重写（G1）
`format_daily_report` 改为调三判断函数组装：每段 `【旧坑复发】<判断句>` + 缩进证据行；保留标题行与日期。FRANK-ESCALATE 独立行保留在段三后（推送逻辑不动）。`--legacy-format` 开关保留旧五段输出一周（对照期），期满移除。

### R4 零事件日（G1）
三段全为空且无 ESCALATE → 整报单行「巡查使日报 MM-DD: 昨日 0 异常，旧坑 0 复发，处置无变化」（快照/环比照写，防日报悄悄死掉）。

### R5 测试与验收脚本
tests/ 下新增目标子集：指纹索引构建（含 lessons 行降级指纹）、三判断函数分支、format_daily_report 三段形态、零事件单行、矛盾告警触发、`--legacy-format` 等价性。现有 timeout_ledger/timeout_patrol 测试全部保持绿（G4 回归门禁）。

## 4. 验收标准（AC，全部可测）

| # | 标准 | 验证方式 |
|---|---|---|
| AC1 | 日报正文恰为三段（旧坑复发/新坑/处置状态），每段首行含判断句且句式非纯计数（不含"共 N 条"作为段首） | 单测断言 format_daily_report 输出结构 |
| AC2 | 构造"已修复坑指纹再命中"样例 → 段一判「复发」并附 task_id+run_id+原处置引用；证据 <2 源 → 判「[待定性]」而非复发 | 单测（纯函数） |
| AC3 | 构造"无命中"样例 → 段一「旧坑 0 复发，预防方案生效」；段二「新坑 0」 | 单测 |
| AC4 | repeat 条目 task_status=done → 归入段一复发嫌疑，不进段二新坑 | 单测（P2 口径） |
| AC5 | lessons 待修复行数 >0 且 agenda 无派修记录 → 段三输出派修失灵矛盾告警；两者一致时不告警 | 单测（mock 日志/JSON 输入） |
| AC6 | 全空输入 → 单行放行文案，且快照/环比文件照常写入 | 单测 |
| AC7 | 存档铁律执行率、FRANK-ESCALATE 独立行、环比、去重/重试机制在输出与推送路径中行为不变 | 现有测试子集全绿 + 新增等价性断言 |
| AC8 | `--legacy-format` 输出与现行五段逐字符一致（对照期） | 单测快照比对 |
| AC9 | 全流程只读台账/wiki；单源缺失 fail-open 不崩，主流程异常 exit 1 无 traceback | 现有 AC8 纪律回归 |

## 5. 优先级与里程碑

- P0: R1 指纹索引 + R2 三判断函数 + R3 文本重写 + R5 测试——报告判断化一次到位。
- P1: AC8 对照期（--legacy-format 一周后移除，移除动作归收口卡）。
- 顺序: R1 → R2 → R3 → R5；R4 随 R3 顺带。
- 明确移交后续卡（本卡不做）: ①F 分类器 error 零区分度升级（采集层）②lessons 909 待修复行路由修复（派修管道，P3 实锤，建议 OC 优先排）③timeout 台账与 lessons 坑台账双口径合并（长期）。

## 6. 风险与边界

- **指纹误配**: 描述归一化指纹可能把相似不同的坑判为复发——代价是一行误判+证据可查，且 <2 源证据强制 [待定性] 兜底，可控。
- **矛盾告警误报**: agenda 可能因 DAILY_CAP=3 主动限流而非失灵——告警文案写「疑似失灵，需人工确认」，不定罪。
- **报告变长**: 判断句+证据行会比五段长——Frank 明确要判断不要行数，证据行用缩进折叠，接受。

## 7. 交付与登记

- [PRODUCES] wiki/projects/devppl/prd/dpl199-patrol-daily-judgment-template-prd.md（本文件）
- 任务详情页: [[actions/DPL-199.md]]（close 阶段按 DPL-151 门禁登记，GAI 行同步）
- 关联: [[dpl158-timeout-patrol-prd]]（日报宿主与五段模板来源）、[[dpl162-patrol-closed-loop-prd]]（signal_hash/三证据/路由口径复用）、[[dpl197-timeout-patrol-terminal-exempt-zombie-prd]]（扫描层豁免，本卡不动）
