---
created: 2026-10-03T01:05:00+08:00
id: arch-dpl199-patrol-daily-judgment-template
page_type: project
project: "[[entities/devppl.md|devppl]]"
status: active
type: entity
updated: 2026-10-03T01:05:00+08:00
---

# ARCH v1.0 — 巡察使日报三段判断模板：报告层判断化，不动采集（DPL-199）

> 编号: DPL-199 | 作者: game-architect（架构）| 日期: 2026-10-03 | 版本: v1.0
> 上游: [[projects/devppl/prd/dpl199-patrol-daily-judgment-template-prd|PRD v1.0]]（t_f832725f，OC 审已过）· 本卡: t_97d10328
> 执行模式: CC-MAX | 交付物: DEV 实现卡（game-engine，由 OC 建卡派发，§7 拆卡规格）

---

## 0. 源码实锚（2026-10-03 实勘 devPPL main 工作区现行代码）

| # | 锚点 | 位置 | 实测结论 |
|---|---|---|---|
| A1 | 五段日报模板 | `timeout_ledger.py:408-483 format_daily_report`（纯函数，无 IO） | ①段纯行数罗列（P1）；②执行率算式 `cp_round >= rounds-ARCHIVE_SLACK`（:452-462）、③派修读 `logs/patrol_fix_cards.json`（:688-698 `_load_fix_cards`）、④ESCALATE 独立行、⑤其余动作——这四类硬信号 G4 要求全部保留 |
| A2 | 信号归一化 | `timeout_patrol.py:256-262 normalize_signal`（去数字+strip+截40字） | PRD G2 指定的辅键；ledger 侧 `_signal_hash`（:147-151）= sha1(normalize)[:12]，与 chain_review 的 `signal_hash()`（chain_review.py:108-115，键= pit_type\|task_id\|_norm_desc）**是两个不同 hash 空间，不可互比** |
| A3 | lessons 台账 | `wiki/actions/lessons-daily.md`（实测 1741 行，含 ~909「待修复」行） | 表行 `| 描述 | F分类 | 涉及卡双链 | 修复状态 |`，但描述 cell 常含多行散文（CC-PLAN 全文黏进 cell），**无 signal_hash 列** → 指纹必须走降级路径（描述归一化），且解析器必须容多行 cell（按 `\|` 分割后取 [1] 与 [4]） |
| A4 | timeout 台账 | `wiki/actions/timeout-forensics.md`（18 列宽表：原因\|生效情况\|说明\|发生/修复×5组）+ `logs/timeout_ledger.csv`（行级真源，含 signal_hash 列） | 复发比对**以 CSV 为行级真源**（DPL-183 A12 已裁定），wiki 表仅取「超时原因」粒度；「预防方案生效情况」列 = 复发判定的已修复/失效状态来源 |
| A5 | 派修管道 | `patrol_fix_agenda.py:18-41 pending_pits`（v2 只认 `[[oc-pitfall-log-*]]` 双链行，DAILY_CAP=3）+ `logs/patrol_fix_agenda.log` + `logs/patrol_fix_cards.json` | P3 失灵根因实锚：过滤器过窄 → 绝大多数待修复行不派修；矛盾检测的两侧输入 = lessons 待修复计数 vs agenda 日志尾行/fix_cards.json |
| A6 | lessons_seen | `chain_review.py:50 DEFAULT_SEEN_PATH=logs/lessons_seen.json`（实测**文件不存在**） | seen 索引缺失是常态而非异常 → build_pit_index 对其 fail-open 空处理（PRD R1 已写），不得当致命 |
| A7 | repeat 口径 | `timeout_patrol.py` scan 产 `repeat` 条目含 `task_status` | PRD AC4：repeat+done → 复发嫌疑归段一。scan 层已带该字段，报告层零采集改动可实现 |

**架构总判定**: 断点确在报告层（PRD §0 结论成立）。A2 揭示一个 PRD 未覆盖的坑：ledger 的 signal_hash 与 chain_review 的 signal_hash 是**不同键空间**（前者 hash(error 归一化)，后者 hash(pit_type|task_id|desc)），指纹索引不能假设两台账 hash 可直接 join——必须统一走「描述归一化降级指纹」为主比对路径（§2.1）。

---

## 1. 架构判定语义（唯一权威表述）

### 1.1 三段模板定稿（PRD G1，文本形态冻结）

```
🕰 巡查使日报 MM-DD
【旧坑复发】<判断句>                ← 段一首行；判断句禁止以计数开头（AC1）
    · <坑描述> — 原处置: <commit/生效情况> — 本次命中: <task_id>(run <run_id>)
    · 铁律执行率: <pct>（<环比>）   ← G4: 执行率并入段一固定尾注（证据位）
【新坑】<判断句>
    · <定性或[待定性]> — <task_id> — 建议动作: <上报/OC直修/建卡>
【处置状态】<判断句>
    · <闭环进度行>…
    · ⚠ 派修管道疑似失灵: 台账 N 待修复 vs 派修 0（需人工确认）   ← AC5 矛盾告警（措辞含「疑似」，PRD §6）
⚠️ FRANK-ESCALATE: <escalate 或 无>（归因: wiki/actions/timeout-forensics.md）  ← 位置不动（段三后独立行）
```

规则：
1. 三段顺序、段名括号形式冻结；每段 0 项时判断句走固定放行文案（「旧坑 0 复发，预防方案生效」「新坑 0」「处置无变化」）。
2. 证据行缩进 4 空格 + `·`，属折叠层；判断句行禁止出现 `t_` 卡号以外的原始错误文本（错误文本只进证据行）。
3. 零事件日（PRD R4）：timed/gave_up/zombie/repeat 全空且无 escalate → 整报单行 `🕰 巡查使日报 MM-DD: 昨日 0 异常，旧坑 0 复发，处置无变化`；快照/环比照写。
4. `--legacy-format` 开关：调旧 `format_daily_report`（保留原函数改名为 `_format_daily_report_legacy` 或以 flag 分支，DEV 择一，但**旧五段输出必须逐字符不变**，AC8 快照锁）。

### 1.2 指纹统一口径（PRD G2 修正案，本节为定稿）

两台账 hash 空间不同（A2）→ 索引主键统一为**降级指纹** `pit_fp = sha1(_norm_desc_like(描述)[:40])[:12]`，其中 `_norm_desc_like` 复用 `normalize_signal` 的规则（去数字、strip、截 40）。辅键 `sig_fp = normalize_signal(error)` 直接字符串比对（不 hash），保留差异可见性。

映射规则：
- lessons 行：`pit_fp = fp(描述 cell 首个语义段)`；多行 cell 取首个非空行。修复状态 cell 含「待修复/待做/待清理/待建」→ ongoing 池；含「已修复/已清理」→ fixed 池。
- timeout 台账 CSV 行：`pit_fp = fp(cause 对应原因行文本)` 不可行（CSV 无描述）→ **CSV 只贡献辅键** `sig_fp`（现成 signal_hash 列反查不出原文 → 改存 `normalize_signal(_error)` 原文？否——CSV 已写 hash。定稿：CSV 辅键比对用 `_signal_hash(e._error)==csv.signal_hash` 同函数同空间（A2 ledger 侧自洽），可行）；wiki 表「超时原因」行贡献 `pit_fp = fp(超时原因文本)` 与「生效情况」状态。
- 匹配优先级：辅键命中 > 主键命中 > 未命中。命中 fixed/生效=失效 → recurrence；命中 ongoing → ongoing；未命中 → new。

### 1.3 复发判定（PRD G3，纯函数）

`judge_recurrence` 判「复发」须同时满足：① 命中 fixed/失效池 ② 证据 ≥2 源（task_id + run_id/CSV 行 + 台账行引用，DPL-162 R4 口径）。只满足① → 输出 `[待定性]` 行进段一证据区，判断句保持「疑似复发 N 处待定性」。

---

## 2. 模块划分与接口定义

### 2.1 `scripts/patrol_pit_index.py`（新模块，纯函数 + 薄 IO）

```python
@dataclass
class PitRecord:
    fp: str            # 降级指纹（§1.2 口径）
    desc: str          # 原文摘要（≤80字，证据引用用）
    status: str        # "fixed" | "ongoing" | "unknown"
    source: str        # "lessons" | "forensics_wiki" | "forensics_csv" | "seen"
    ref: str           # 台账行引用（文件+行号或 CSV date+task_id）

def build_pit_index(lessons_path, forensics_wiki_path, forensics_csv_path,
                    seen_path) -> dict[str, list[PitRecord]]   # fp -> records
    # 只读；任一单源缺失/解析失败 → 该源跳过（fail-open 空贡献），全缺 → {}
    # lessons_seen.json 不存在（A6）→ 静默跳过

def match_pits(entries: list[dict], index: dict) -> dict[str, list[dict]]:
    # entries = scan result 的 timed+zombie+repeat 合并
    # 返回 {"recurrence": [...], "new": [...], "ongoing": [...], "pending": [...]}
    # 每项附 {"entry": 原条目, "matches": [PitRecord...], "evidence_sources": int}
```

### 2.2 `timeout_ledger.py` 新增三判断函数（纯函数，PRD G5）

```python
def judge_recurrence(matches: dict, arch_rate: str, trend: str | None) -> str
def judge_new_pits(matches: dict) -> str
def judge_disposition(matches: dict, fix_cards: list | None,
                      pending_lessons: int, agenda_alive: bool) -> str
```

- 段一尾注 = 铁律执行率（G4）；`judge_new_pits` 内实现 AC4（repeat+task_status=done → 复发嫌疑，路由进段一 pending）。
- `judge_disposition` 矛盾检测输入：`pending_lessons`（index 构建时顺带计数，lessons 源 ongoing 池大小）与 `agenda_alive`（读 `logs/patrol_fix_agenda.log` 尾行含「无未修坑待派」为 False；`logs/patrol_fix_cards.json` 近 24h 有写为 True）。两输入由调用方（main）IO 取得，判断函数保持纯。
- 判定「复发」与告警文案逐字模板见 §1.1/§1.3，DEV 不得改写措辞。

### 2.3 `format_daily_report` 重写（PRD R3）

签名不变（`result, now, trend, fix_cards, escalate, other_actions`）+ 新增 keyword-only `pit_index: dict | None = None, agenda_alive: bool | None = None`。`pit_index=None` 时内部现建（fail-open 空索引）——保证既有调用点（main、测试、`--legacy-format`）零改动兼容。ESCALATE 推送路径、去重/重试（`dedup_seen/mark`、retry marker）完全不动（A1/PRD 非目标）。

---

## 3. 数据流

```
timeout_patrol.scan() ──result──┐
lessons-daily.md ──┐            ├─> match_pits ─> judge_recurrence ─┐
timeout-forensics ─┼─> build_pit_index                            ├─> format_daily_report ─> 飞书推送（通道不动）
timeout_ledger.csv─┘        │      └─────────────> judge_new_pits ─┤        │
logs/lessons_seen.json ─────┘      agenda日志/fix_cards.json > judge_disposition ┘
```

全流程只读台账/wiki/日志（AC9）；唯一写路径仍是现有 CSV/snapshot/seen 通道，本卡不新增任何写。

---

## 4. 测试与验收（映射 PRD AC1-AC9）

| AC | 测试落点（tests/ 新文件 `test_dpl199_report.py`） |
|---|---|
| AC1 | 输出结构断言：恰三段、段名匹配、首行无「共 N 条」 |
| AC2 | 构造 fixed 池 + 辅键命中样例 → 判复发含 task_id+run_id；单源证据 → [待定性] |
| AC3 | 空命中 → 两条放行文案逐字断言 |
| AC4 | repeat+done 条目出现在段一、不在段二 |
| AC5 | pending>0 + agenda_alive=False → 告警行存在；一致时无告警 |
| AC6 | 全空输入 → 单行文案 + save_daily_snapshot 仍被调（mock 断言） |
| AC7 | 现有 test_dpl158_ledger / test_dpl158_patrol 全绿 + ESCALATE 行位置断言 |
| AC8 | legacy 分支输出与改造前快照逐字符一致（fixture 快照比对） |
| AC9 | 缺失文件样例不崩；主流程异常 exit 1 无 traceback（沿用现有纪律测试模式） |

验收门禁：`pytest tests/test_dpl199_report.py tests/test_dpl158_ledger.py tests/test_dpl158_patrol.py`（本卡子集，不跑全量）。

---

## 5. 风险与边界（架构侧补充）

- **多行 cell 解析**（A3）：lessons 描述 cell 含整段 CC-PLAN 散文 → 指纹取首语义段仍可能把不同坑归同指纹。兜底：match 结果必须附原文摘要与行引用，误判代价=一行证据可查的文案（PRD §6 已接受）；<2 源强制 [待定性] 再拦一道。
- **agenda_alive 判定窗口**：DAILY_CAP=3 造成「合法无派」与失灵同貌 → 告警文案固定「疑似失灵，需人工确认」（PRD §6），不升级为 FAIL。
- **归一化截 40 字**：中文截断可能落在词中——两台账同源文本（lessons 描述 vs 命中 error）本就不同文，主键匹配本就是模糊启发，辅键优先级（§1.2）缓解；不引入分词依赖（保持零新依赖）。

## 6. 明确不做（PRD 非目标重申 + 实锚）

不改 `timeout_patrol.py` scan/classify（P4 分类器升级另卡）；不改 chain_review.py 写回（lessons 909 路由修复另卡，OC 优先排）；不合并双口径台账（长期卡）；不动飞书去重/重试。

## 7. DEV 拆卡规格（移交 OC 建卡，assignee=game-engine）

- 卡 1【DEV·DPL-199】报告层实现：§2 三个模块/函数 + §1.1 文本形态 + §4 测试全部；前置产物 = 本 ARCH + PRD；验收 = §4 门禁子集绿 + AC8 快照一致。
- 冻结项（DEV 不得擅改）：§1.1 段名/放行文案/告警措辞、§1.2 指纹口径、§2.2 函数签名。
