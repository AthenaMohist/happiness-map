# 建卡铁律 v4 落地架构设计 — next-seq 分配 + 编号注入 + chain_check + drift/lint 扩展

> 发言人：高见远（架构师） | 日期：2026-08-12 | 版本：v1.0
> **v4.1 修订（2026-08-21，DPL-092 / Frank 创建者权威原则）**：本文档 §6 原定的 lint I5 ⑥「id==task_code 同值强推」已废止。现行规则以 mem-core `wiki/SCHEMA.md` §7 I5 ⑤⑥（建卡铁律 v5）为准：task_code = 创建者声明的隶属任务链编号（缺省回落自身 id），≠ 自身 id 时须指向真实存在的任务页（索引一致性对账），不再要求与 id 同值。本文档相应表述已按 v5 订正，历史设计动机保留在 §6 供追溯。
> 输入：PRD v1.0（docs/prd/refine-card-numbering-chain-prd.md，commit ba431a6）+ PIPELINE.md 核心纪律 6（OC 已接线，A5 达成）+ 现状代码核查（cmd_chain.py / discover.py / workspace_check.sh / mem-core drift.py / lint.py / schema.py / gailinks.py）
> 定位：6 步闭环 Step 2 架构落地 —— 把 PRD §8 交接项 1-5 细化为文件/函数/数据流级实现方案，工程师可直接照写代码
> 核心原则：**v4 是叠加在现有建卡流程之上的身份层**，不推翻 v1-v3 任何裁定；三条铁律（单一写入者 / 状态不回写 / 机械层零 LLM）在每条接线点逐点论证；MVP 过渡期只告警不阻断

---

## 0. 范围与裁决总表

### 0.1 本设计做什么（PRD §8 交接项 1-5 全覆盖；第 6 项 PIPELINE.md 已由 OC 完成）

| # | PRD 交接项 | 本设计章节 | 实现仓 |
|---|-----------|-----------|--------|
| 1 | memctl next-seq `<CODE>`（零 LLM 确定性分配 + GAI→wiki 双兜底 + 防并发重号） | §2 | mem-core |
| 2 | 建卡编号注入（cmd_chain `_dev_card_body()` 编号首行 + [CMD] create dev 描述解析 + 全链继承） | §3 | devPPL |
| 3 | chain_check 扫描（复用 workspace_check 模式 + [chain-gap] 告警 + 历史豁免） | §4 | devPPL |
| 4 | drift 扩展（编号存在性 / 唯一性 / 链一致性三个新维度） | §5 | mem-core |
| 5 | lint I5 扩展（task 页 task_code 非空 + 格式 + 索引一致性对账〔v4.1 订正：原 id/task_code 同值已废止，DPL-092〕） | §6 | mem-core |
| 6 | PIPELINE.md 核心纪律 6 更新 | ✅ 已由 OC 完成（/root/.hermes/profiles/orchestrator/PIPELINE.md L41） | — |

### 0.2 架构裁决总表（本设计的核心决策）

| 决策点 | 裁决 | 说明 |
|--------|------|------|
| **D0-1 现状修正** | ⚠️ PRD §2「[CMD] create dev 每棒 parents 门控」与实际代码**不符**：`advance_sequential_chains()` 建后棒卡未传 `parents`（cmd_chain.py L933-943）→ 开发链 task_links 实际为空 | 本设计必须修正：advance 建卡补 parents（§3.4）。否则 chain_check 上线后所有开发链全部误报平铺 |
| D0-2 next-seq 位置 | mem-core 新增 `memcore/seq.py`（与 gailinks.py 同域不同职责），CLI 挂 `memctl next-seq` | gailinks 是校验/修复引擎，seq 是分配器；共享 GaiAdapter + 同一 GAI 文件，合并目录但不合并函数 |
| D0-3 编号来源优先级 | topic → reason → 已有链卡 body → next-seq（预留） | 继承优先、分配兜底；MVP 期 next-seq 不可用则返回空（流程约定 + 扫描告警兜底） |
| D0-4 chain_check 挂载 | autopilot.sh 主循环末尾（与 workspace_check 同挂点），独立脚本 `scripts/chain_check.sh` | 复用 workspace_check 的「bash 壳 + python inline 扫描 + comment 告警 + 幂等守卫」模式 |
| D0-5 同编号成链判定 | 组内 task_links 图连通分量 == 1；多分量 → 非最大分量全部告警 | 线性链 / 拆卡树 / 扇入合并都覆盖；精确到卡 |
| D0-6 drift 编号缺失 | kanban 活跃项目卡无 [CODE]-NNN → 也报 drift 差异 | 缺陷 1 教训：编号缺失必须暴露，不能只对账已有编号 |
| D0-7 lint I5 追加 | I5 ⑤ task_code 非空 + 格式；I5 ⑥ 索引一致性（≠ 自身 id 时指向真实任务页）〔v4.1 订正：原 id==task_code 废止，DPL-092〕 | 沿用 I5 编号（SCHEMA §7），不新增 I6——PRD §5.2 明确定义为「I5 扩展」 |
| D0-8 task_code 必填豁免 | status=draft / mechanism=memctl add/done 的机械骨架页豁免 task_code 必填 | 同 est_hours 豁免逻辑（OBS-01 模式）；active 页强制 |
| D0-9 拆卡 | **建议拆 2 张研发子卡**（管线侧 / memctl 侧），由 OC 建卡 | §7；本卡不建卡（SOUL.md 建卡铁律） |

### 0.3 三铁律合规确认

| 铁律 | 本设计合规点 |
|------|-------------|
| 单一写入者 | next-seq **只分配不写**；写编号走 add/gai-links 通道；chain_check 只读不自动改卡；编号注入全部在 cmd_chain.py 建卡时一次完成 |
| 状态不回写环 | chain_check/drift 只读 kanban.db + GAI + wiki；绝不写 L0；编号一致性校验只报差异不补写 |
| 机械层零 LLM | next-seq（regex 扫 GAI + wiki 目录）、编号解析（regex）、chain_check（SQL + 图算法）、drift/lint 扩展全部确定性脚本；LLM（OC/autopilot）只调用不手填编号 |

---

## 1. 现状核查与数据流全景

### 1.1 现状核查（读码结论，非假设）

| # | 核查点 | 结论 | 证据 |
|---|--------|------|------|
| 1 | [CMD] create dev 链的 task_links | **空**。sequential 首棒无 parents；advance 建后棒无 parents（只注入 body 前棒 id） | cmd_chain.py L691-695 / L933-943 |
| 2 | 评估卡（dev-est/qa-est）parent 边 | **有**。est_intercept_after_insert 触发器 + discover._hold_oc_card 挂 est→源卡边 | discover.py L289-343 / L231-258 |
| 3 | 拆卡（dev-sub/qa-exec-sub）parent 边 | **有**。serial 模式 sub-N parents=[sub-(N-1)]；parallel parents=[est] | cmd_chain.py L514-527 / L552-564 |
| 4 | GAI 双链版 ID 列 | 任务 ID 列 = `[CODE]-NNN`（MEM-001 / DPL-009），行动列带 `[[ID]]` 双链 | /workspace/mem-core/gai/GLOBAL_ACTION_ITEMS.md |
| 5 | wiki actions/ 页 | `id: <外部ID>`（MEM-002 页 id=MEM-002），frontmatter 已有 task_code 字段（SCHEMA v1.1）但**无强制校验** | wiki/actions/MEM-002.md；SCHEMA.md §4 |
| 6 | 项目代码表 | /root/.hermes/profiles/orchestrator/PROJECT_CODES.md（11 码，2-3 字母） | PROJECT_CODES.md |
| 7 | 编号正则 | schema.ID_PATTERN `^[A-Z]+\d*-\d{2,3}$` 兼容 MEM-001/P1-07；**但会误匹配优先级列 P1-07** | schema.py L32 |
| 8 | workspace_check 扫描模式 | bash 壳 + python inline + 幂等 comment 守卫 + fail-open | scripts/workspace_check.sh |

### 1.2 核查点 #1 的严重性

PRD §2 规则 2「已覆盖路径」声明 `[CMD] create dev` 每棒 parents 门控 ✅ —— **代码实测不成立**。开发链卡（PRD/arch/dev/qa/va/…）之间 task_links=0，仅靠 advance 的幂等键轮询推进。后果：
- chain_check 若按 PRD 字面上线 → **所有开发链被误报 [chain-gap] 平铺**（噪声淹死真实告警）；
- 缺陷 2「卡链断裂」在开发链场景**仍存在**（PRD 以为已修）。

**裁决（D0-1）**：交接项 2 必须同时修正 advance 建链补 parents。这是本设计对 PRD 的**唯一实质性修正**，其余按 PRD 原样落地。

### 1.3 数据流全景（编号从出生到三处落位）

```
┌─────────────────────────────────────────────────────────────────────────┐
│ 路径 A — 从 GAI 发起（Frank 愿景主路径）                                 │
│   GAI 新增待办行（任务ID 列 = [CODE]-NNN，memctl next-seq 分配）          │
│     → OC 投 [CMD] create dev DPL-016: <描述>（编号带在描述里）            │
│     → cmd_chain 解析编号 → _dev_card_body 注入「编号: DPL-016」首行        │
│     → advance 后棒卡从链卡 body 继承编号 + 补 parents 成链                │
│     → memctl add task --from-kanban 采集 → frontmatter task_code=编号     │
│ 路径 B — 直接建卡（无 GAI 行）                                            │
│   建卡前调 memctl next-seq <CODE> 取编号（或 body 已有编号继承）          │
│     → 建卡（title/body 带编号）→ discover 注册 → est 拦截挂边            │
│     → chain_check 扫描：同编号多卡无链 → [chain-gap] 告警（OC 补 parents） │
│                                                                          │
│ 校验层（只读兜底）                                                       │
│   chain_check（devPPL cron）: 链一致性                                    │
│   memctl drift（mem-core）: 编号存在性 / 唯一性 / 链一致性 三方对账        │
│   memctl lint（mem-core）: I5 扩展 task_code 格式 + 索引一致性（v4.1 订正，DPL-092）│
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 交接项 1：memctl next-seq `<CODE>`（mem-core 仓，P1-2 GAI 适配器范围）

### 2.1 文件位置与接口

新建 `memcore/seq.py`（~80 行），CLI 挂 `memctl next-seq`（cli.py 增加子命令）。

```python
"""memcore.seq — GAI 编号分配器（零 LLM，确定性，只分配不写）。

PRD §3.3 memctl next-seq 的引擎。与 gailinks.py 同域（都操作 GAI 文件），
但职责不同：gailinks 校验/修复双链，seq 分配编号。共享 GaiAdapter 解析。
"""

# 编号格式: [CODE]-NNN（PRD 规则 1）。CODE 2-3 字母（PROJECT_CODES.md），NNN 3 位。
# 注意不能用 schema.ID_PATTERN（^[A-Z]+\d*-\d{2,3}$）——它会把优先级列 P1-07
# 误匹配为 CODE=P1。分配器必须按 PROJECT_CODES.md 注册码精确前缀过滤。
NUMBER_RE = re.compile(r"([A-Z]{2,3})-(\d{3})")

def load_project_codes(path: str | None = None) -> set[str]:
    """读 PROJECT_CODES.md 注册码集合（'**DPL** | devPPL | ...' 行的首列）。
    默认 /root/.hermes/profiles/orchestrator/PROJECT_CODES.md（schema.py 新增
    PROJECT_CODES_PATH 常量，MEM_PROJECT_CODES env 可覆盖）。文件缺失 → 空集
    （fail-open：next-seq 无注册码可用时拒绝分配，宁缺毋滥）。
    """

def next_seq(code: str, *, gai_file: str | None = None,
             wiki_root: str | None = None) -> str | None:
    """分配 <CODE>-NNN（只读不写）。

    1. 校验 code ∈ load_project_codes()；非法 → None + stderr 说明
    2. 主源：读 GAI 文件（GaiAdapter.fetch_events 任务 ID 列），过滤
       f"{code}-\\d{{3}}" 前缀，取 max NNN → max+1
    3. 兜底 1：GAI 文件缺失/无该码编号 → 扫 wiki/actions/ 目录文件名
       f"{code}-\\d{{3}}"，取 max+1
    4. 兜底 2：两源都无 → "001"
    5. 分配过程对 GAI 文件加 fcntl.flock 共享锁（防与写通道读-改-写竞态）
    6. 返回 <CODE>-NNN（大写规范化）
    """
```

### 2.2 并发重号对策（验收项「next-seq 并发重号有明确对策」，PRD R3）

| 层 | 对策 | 机制 |
|----|------|------|
| L1 分配查询 | GAI 文件 flock 共享锁 | 同一时刻只一个分配进程读 max；写通道持独占锁写 → 读写互斥 |
| L2 写通道 CAS | gai-links/add 写 GAI 前**再次调用 next-seq 校验**：分配值仍是当前 max+1 → 是则写；否则重取重写（至多 3 次） | 「分配-登记」分离下的防超卖；写 GAI 行本身走 git 原子提交（memctl 单一写者天然串行） |
| L3 最终兜底 | drift 唯一性查重（§5.3）：三源各自查重，发现同号 → 报警 → **后建者改号**（OC 处置） | PRD R3 原样；机械分配 + 确定性校验让重号几乎不可能，L3 是最后一道 |

> **MVP 过渡期**（next-seq 未上线）：编号从 GAI 行手抄（流程约定），无并发写通道 → 重号风险仅来自手填错误，由 drift/lint 查重兜底。与 PRD §8「MVP 期间过渡」一致。

### 2.3 cli.py 接线

```python
# cli.py 增加（与 gai-links 同 V2 命令区）
def cmd_next_seq(args) -> int:
    """memctl next-seq <CODE> → 打印 <CODE>-NNN。
    退出码: 0 成功 / 1 一般错误（CODE 未注册 / 无法分配）。"""
```

### 2.4 三铁律合规

- 单一写入者 ✅：next-seq 零写（只读 GAI + wiki 目录 + 文件锁）；登记由 add/gai-links 通道负责（PRD §3.3「只分配不写」）
- 机械层零 LLM ✅：regex + max 统计，无任何 LLM 调用
- 状态不回写 ✅：不写 kanban/GAI/wiki

---

## 3. 交接项 2：建卡编号注入（devPPL 仓 cmd_chain.py）

### 3.1 编号解析与继承（新增辅助函数）

```python
# pipeline/cmd_chain.py 新增（~40 行）

# 编号 regex：2-3 字母 + 连字符 + 3 位数字。必须带边界（(?<![A-Z0-9])），
# 防匹配 [DEV-PRD]（PRD 非数字，天然安全）与 INF-011 等子串。
CARD_CODE_RE = re.compile(r"(?<![A-Z0-9])([A-Z]{2,3})-\d{3}(?![A-Z0-9])")

def _extract_code(text: str) -> str | None:
    """从文本提取首个 [CODE]-NNN（大写规范化）。无 → None。"""

def _read_chain_code(conn: sqlite3.Connection, spec_hash: str) -> str | None:
    """从同 spec_hash 链卡 body 的「编号:」首行 / 标题继承编号。
    查询 idempotency_key LIKE 'dev-<hash>-%' 的卡，取任一卡的
    body 首行 '编号: <CODE>-NNN' 或标题 [CODE]-NNN。无 → None。
    后棒卡用：编号在首棒分配，后棒从链卡 body 继承（不重复分配）。
    """

def _resolve_chain_code(topic: str, reason: str,
                        conn: sqlite3.Connection, spec_hash: str) -> str:
    """解析开发链编号（优先级：topic → reason → 已有链卡 body → next-seq）。
    返回 '' 表示无编号（MVP 过渡期：流程约定执行 + chain_check/扫描告警兜底）。
    next-seq 接线点（P1-2 上线后自动启用）：
      _call_next_seq(topic) → subprocess ['memctl','next-seq', code]
      code 从 topic 中 [A-Z]{2,3}- 前缀或显式 'DPL:' 标记提取；
      无明确项目代码 → 返回 ''（不猜测，宁缺毋滥）。
    """
```

**MVP 期行为**：`_resolve_chain_code` 只做前三步（继承），`_call_next_seq` 返回空串（next-seq 未上线）。这与 PRD §8「MVP 期间过渡：编号从 GAI 行手抄」一致——编号必须出现在 [CMD] create dev 描述里才能注入，缺编号的链不阻断建卡，由 chain_check/drift 告警。

### 3.2 `_dev_card_body()` 编号首行注入

```python
def _dev_card_body(topic, reason, prev_step=None, ctx=None, step="", code=""):
    lines = []
    if code:
        lines.append(f"编号: {code}")          # v4 新增：首行
    lines.append(f"议题: {topic}")
    ...
```

调用点（3 处）全部透传 code：
1. `build_roundtable_chain` sequential 首棒（L691-695）：`code = _resolve_chain_code(topic, reason, ...)`
2. `advance_sequential_chains` 建后棒（L933-943）：`code = _read_chain_code(conn, spec_hash)`
3. `_create_dev_sub_cards` / `_create_qa_sub_cards` 子卡（L513/L551）：`code = ctx.get("code")`

### 3.3 子卡继承

`_sub_card_body()` 增加 `编号: <code>` 行（ctx.code 传入）。`_chain_context()` 增加 `code` 字段：

```python
def _chain_context(conn, cards, spec_hash, topic) -> dict:
    ctx = {"spec_hash": spec_hash, "topic": topic, "code": _read_chain_code(conn, spec_hash)}
    ...
```

### 3.4 【D0-1 修正】advance 建后棒卡补 parents（本设计核心修正）

```python
# advance_sequential_chains 建棒处（现 L933-943），新增 parents 参数：
parents = None
if prev.get("id"):
    parents = [prev["id"]]                    # 真实前棒卡 → 直接挂边
elif prev.get("_subs"):
    parents = prev["_subs"]                   # 拆卡场景 → 全部子卡扇入
card_id = _hermes_create(
    title, step_def["assignee"],
    _dev_card_body(topic, "", {...}, ctx, step=step, code=code),
    idem_key=f"dev-{spec_hash}-{step}",
    parents=parents,                          # ← 新增
    workspace=workspace,
)
```

**语义论证（无回归风险）**：
- advance 本来就是「前棒 done → 建后棒」，child 卡创建时 parent 已 done → kernel 家长门控不会 demote，行为不变；
- merge/close 自消费卡同样受益：close 卡 parents=[merge 卡] 后，merge 未 done 时 close 不会提前 ready（原实现靠 advance 顺序保证，现在是双重保证）；
- 拆卡场景 fan-in：qa-d1 parents=[全部 dev-sub 卡] —— 与 advance「子卡全 done 视为满足」条件一致（子卡未全 done 时 qa-d1 即使建了也被 demote，语义正确）；
- 幂等键不变，重复调用返回已有卡，parents 边只加一次（INSERT OR IGNORE 由 kernel 处理）。

**影响面**：chain_check 上线前必须先合入本修正，否则全量误报（§1.2）。测试 T3（§11）专门覆盖。

### 3.5 豁免清单（编号不注入）

- `_roundtable_card_body`（roundtable 发言链）：不加编号行（PRD §4.2 纯内部卡豁免）
- [CMD] 指令卡本身：不加（消费后归档，非任务身份）

---

## 4. 交接项 3：chain_check 扫描（devPPL 仓 scripts/chain_check.sh）

### 4.1 脚本结构与挂载

**完全复用 workspace_check.sh 模式**：bash 壳 + python inline + 幂等 comment 守卫 + fail-open + 独立脚本。

```
scripts/chain_check.sh [REPO_ROOT]     # autopilot.sh 末尾调用（workspace_check 同挂点）
环境变量: HERMES_KANBAN_DB（测试可覆盖）
```

挂载点：autopilot.sh 末尾（L759 workspace_check 之后）：

```bash
bash "$REPO_ROOT/scripts/chain_check.sh" "$REPO_ROOT" || true
```

### 4.2 扫描与判定逻辑（python inline 段）

```python
# 1. 扫描活跃卡（ready/running/blocked/todo），提取编号
rows = conn.execute(
    "SELECT id, title, body, status FROM tasks "
    "WHERE status IN ('ready','running','blocked','todo')"
).fetchall()

# 2. 提取 [CODE]-NNN（body 首行「编号:」优先 → body 全文 → 标题）
#    排除内部卡（title 前缀 [CMD] / [ROUNDTABLE-] —— 豁免清单，PRD §4.2/§7 R2）
#    → groups: dict[code, list[card]]

# 3. 读 task_links（全表一次）
links = conn.execute("SELECT parent_id, child_id FROM task_links").fetchall()

# 4. 组内成链判定（连通分量算法）
def chain_violations(cards, links):
    """cards: [card_id]; links: [(parent, child)]  → 违规卡 id 列表。
    组内卡构无向图（parent/child 均视为边），BFS 求连通分量。
    分量数 == 1 → 成链（线性链 / 拆卡树 / 扇入合并都覆盖）。
    分量数 > 1 → 除最大分量外的所有卡违规（平铺/断链）。"""
    ...

# 5. 输出: code \t card_id \t title \t status
```

### 4.3 告警（幂等 + 只读）

```bash
# 每张违规卡（同编号组内取最大分量外的卡）：
hermes kanban comment "$CID" \
  "[chain-gap] 同编号 $CODE 的 ${N} 张活跃卡（${IDS}）未构成完整 task_links 链，违反建卡铁律 v4 规则 2（Frank 2026-08-12 裁定）。本扫描只读不自动改卡；请 OC 处置：为后建卡补 parents 前序卡，或确认豁免。"
# 幂等守卫：已有 [chain-gap] 标记 comment 的卡不重复告警（同 workspace_check L105-118）
# 幂等键位：同一编号组的告警挂在「非最大分量」的卡上（每卡一次）；组修复后下次扫描不再命中
```

### 4.4 历史豁免（验收项「chain_check 只读告警 + 历史豁免明确」，PRD R4）

- **只扫活跃卡**（ready/running/blocked/todo）→ done/closed/cancelled/archived 天然豁免；
- **v4 生效前创建的卡不追溯**：按 `created_at` 判断（v4 生效时刻 = PIPELINE.md 纪律 6 commit ba431a6 的 2026-08-12，实现时以 chain_check 首版上线时间戳为 cutoff，硬编码常量 `V4_EPOCH = <上线时间戳>`，测试可覆盖）；
  - 判定：同编号组内**全部**卡 created_at < V4_EPOCH → 整组豁免；组内**部分**卡在 V4 后 → 只对 V4 后创建的卡告警；
- **内部卡豁免**：title 前缀 `[CMD] ` / `[ROUNDTABLE-`（复用 discover.SUB_TASK_TITLE_PREFIXES 的豁免语义，与 workspace_check L91 同风格）。

### 4.5 与 workspace_check 的差异对照

| 维度 | workspace_check | chain_check |
|------|----------------|-------------|
| 扫描对象 | workspace_kind 违规 | 同编号卡链一致性 |
| 判定 | 白名单 + assignee | 编号分组 + 连通分量 |
| 标记 | [workspace-check] | [chain-gap] |
| 写操作 | 无（只 comment） | 无（只 comment） |
| 幂等 | comment 标记守卫 | comment 标记守卫 |

---

## 5. 交接项 4：drift 扩展（mem-core 仓 drift.py）

### 5.1 现状（drift.py 已有）

`three_way_check()`：kanban 活跃任务 vs wiki 缺页 + GAI 待办 vs wiki 缺页/断链 + index 对账。`_kanban_active()` 只取 id/title/status。

### 5.2 扩展设计（编号维度，缺一即 drift 差异）

```python
def _kanban_active(db_path) -> list[dict]:
    """扩展: SELECT id, title, status, body + task_links 读取。"""

def _extract_codes(text: str) -> set[str]:
    """复用 CARD_CODE_RE（cmd_chain 同源 regex，mem-core 侧复制常量，
    两仓各有一份——同步约定标注在 schema.py）。"""

def _numbering_diffs(kanban_tasks, gai_ids: set[str], page_ids: set[str],
                     kanban_links) -> list[str]:
    """编号三维度校验，返回差异描述列表：
    1. 存在性（kanban→GAI / kanban→wiki）
       - 活跃项目卡（assignee ∈ PIPELINE_ASSIGNEES 且非豁免前缀）无编号
         → "[编号缺失] {tid} ({title}): 活跃项目卡无 [CODE]-NNN"
       - 卡有编号 N → N ∉ gai_ids → "[编号→GAI] {tid} ({title}): {N} 不在 GAI 行"
       - 卡有编号 N → N ∉ page_ids → "[编号→wiki] {tid} ({title}): {N} 无 wiki actions/ 页"
    2. 唯一性（三源各自内查重）
       - GAI 行: 同编号出现 2+ 次 → "[GAI 重号] {N}: 出现 {k} 次"
       - wiki: page_ids 同编号 2+ 页 → "[wiki 重号] {N}: {pages}"
       - kanban: 活跃卡同编号 2+ 张 → "[kanban 重号] {N}: {tids}"
    3. 链一致性（同编号多卡必须 task_links 串联，复用 chain_check 判定）
       - 同编号活跃卡 2+ 张且连通分量 > 1 → "[链断裂] {N}: {ids} 未构成完整链"
    """
```

### 5.3 输出与验收口径

`memctl drift` 输出为空 = 三方一致（含编号维度）。现有 three_way_check 的差异列表追加编号维度（追加在现有缺页/断链之后，不改变既有输出语义）。退出码不变（drift 无 FAIL 退出码，输出为空即通过——PRD §5.3「drift 输出空 = 三方一致」）。

### 5.4 只读论证

drift 只新增读操作（kanban body/task_links + regex），不新增任何写路径。三铁律 ✅。

---

## 6. 交接项 5：lint I5 扩展（mem-core 仓 lint.py + schema.py + SCHEMA.md）

### 6.1 lint.py 扩展

```python
# lint.py _frontmatter_errors() 增加（SCHEMA §7 I5 ⑤⑥）：

if page.page_type == "task" or page.type == "action":
    tc = page.frontmatter.get("task_code")
    if tc in (None, ""):
        if not _mechanical_skeleton(page):
            errors.append("task 页缺 task_code（建卡铁律 v4：task 页必须带编号）")
    elif not CARD_CODE_RE.fullmatch(str(tc).upper()):
        errors.append(f"task_code 非法: {tc}（应为 [CODE]-\\d{{3}}）")
    elif str(tc).upper() != page.id.upper():
        # v4.1 订正（DPL-092）：废除 id==task_code 同值强推 → 索引一致性对账
        # task_code ≠ 自身 id 时，须指向真实存在的任务页（actions/<task_code>.md）
        target_page = f"actions/{str(tc).upper()}.md"
        if not _mechanical_skeleton(page) and target_page not in known_action_paths:
            errors.append(f"task_code({tc}) 索引不一致: {target_page} 不存在")
```

### 6.2 豁免（D0-8）

- `_mechanical_skeleton(page)`（status=draft 或 mechanism=memctl add/done）→ 豁免 task_code 必填（同 est_hours 豁免模式，OBS-01 落地）；
- 非 task 页（entity/concept/decision/raw）不适用；
- **注意**：actions/ 页 id 本就是外部 ID（MEM-002），id==task_code 旧规则（v4 原设计）对 actions/ 页天然成立，但 v4.1（DPL-092）已废除该强推——task_code 语义改为「创建者声明的隶属任务链编号」（如 DPL-070 页 task_code=MEM-009 表示该卡隶属 MEM-009 链），校验收窄为索引一致性对账；page_type=task 的页面若在 actions/ 外（不应存在）由 page_type↔type 映射校验兜底。

### 6.3 schema.py + SCHEMA.md 同步（SCHEMA §10 同步约定）

| 文件 | 改动 |
|------|------|
| schema.py | ① 新增 `PROJECT_CODES_PATH` 常量 + `MEM_PROJECT_CODES` env；② 新增 `CARD_CODE_RE = re.compile(r"([A-Z]{2,3})-\d{3}")`（seq/lint/drift 共用，两仓同步约定标注）；③ I5 规则常量不新增（lint 内联） |
| wiki/SCHEMA.md | §4 frontmatter 字段表 task_code 行更新「task 页必填（骨架豁免）+ 格式 [CODE]-NNN + 索引一致性（v4.1 订正 DPL-092：≠ 自身 id 时须指向真实任务页，废除 id 同值）」；§7 I5 追加 ⑤⑥ 两条 |

### 6.4 MVP 门禁

I5 ⑤⑥ 随 P1-5（V2）落地；MVP 期 `memctl lint` 仍查 I1-I4（SCHEMA §7 实现进度注已声明）。本设计不改门禁节奏。

---

## 7. 拆卡建议（验收项「拆卡建议（如需）明确写出」）

### 7.1 范围评估

| 维度 | 结论 |
|------|------|
| 实现点 | 5 项交接 + 1 项修正（D0-1），跨 **2 个仓库**（devPPL + mem-core） |
| 里程碑 | 管线侧（编号注入 + advance 补 parents + chain_check）= **MVP 过渡期即需**（扫描兜底）；memctl 侧（next-seq + drift/lint）= **P1-2**（PRD §3.3 产品裁定不在 MVP 9.5h） |
| 依赖 | chain_check 依赖 advance 补 parents（D0-1）先合入；drift/lint 不依赖 next-seq（独立可先行） |
| 轮次预估 | 管线侧 ~2.5h / memctl 侧 ~3.5h（§9）——单卡超 60 轮风险中等偏高，建议拆 |

### 7.2 建议拆分（**由 OC 建卡**——本卡遵守 SOUL.md 建卡铁律，不越权建卡）

| 子卡 | 内容 | 仓 | 里程碑 | assignee 建议 |
|------|------|-----|--------|--------------|
| **子卡 A（管线侧）** | §3 编号注入 + §3.4 advance 补 parents + §4 chain_check + 测试 T1-T7 | devPPL | MVP 过渡期（立即） | game-engine |
| **子卡 B（memctl 侧）** | §2 next-seq + §5 drift 扩展 + §6 lint I5 扩展 + schema/SCHEMA 同步 + 测试 T8-T13 | mem-core | P1-2 | game-engine |

依赖关系：A、B 可并行（无代码级依赖；B 的 drift/lint 不读 A 的产物）。建议 `parents=[t_84884feb]`。

---

## 8. 冲突点与 ADR

### 8.1 需 Product 确认的分歧（本设计对 PRD 的实质修正）

| # | 分歧点 | PRD 表述 | 架构裁决 | 理由 |
|---|--------|---------|---------|------|
| D1-1 | [CMD] create dev 链 task_links | §2 规则 2「已覆盖路径：每棒 parents 门控 ✅」 | **未覆盖，需修正**：advance 建后棒补 parents（§3.4） | 实测 cmd_chain.py L933-943 未传 parents；不修则 chain_check 全量误报 |

### 8.2 架构自行裁决（无 PRD 冲突，仅细化）

| # | 裁决 | 说明 |
|---|------|------|
| A1 | 编号解析优先级 topic → reason → 链卡 body → next-seq | 继承优先、分配兜底；LLM 零负担（PRD R1） |
| A2 | next-seq 校验 CODE ∈ PROJECT_CODES.md | 防任意前缀垃圾编号；P1-07 优先级列误匹配防线 |
| A3 | 同编号成链判定 = 无向连通分量 == 1 | 覆盖线性链/拆卡树/扇入；精确到卡 |
| A4 | V4_EPOCH 硬编码常量 + 测试可覆盖 | 历史豁免判定可测（PRD R4） |
| A5 | chain_check 只告警非最大分量卡 | 主链不刷屏，断裂支链精确告警 |
| A6 | drift 编号缺失也报（活跃项目卡无编号） | 缺陷 1 教训：编号缺失必须暴露 |
| A7 | 子卡继承编号走 ctx.code（不重新解析） | 一次解析全链一致，防多源漂移 |

### 8.3 与 PIPELINE.md 核心纪律 6 的一致性确认

纪律 6（L41）要求：编号三处一致 + 同编号连续步骤成链 + next-seq 机械分配优先 + 内部卡 title 前缀豁免。本设计五项落地点逐一对应：编号注入（纪律 6 第 1 句）、advance 补 parents（第 2 句）、chain_check/drift（校验）、next-seq（分配优先）、豁免清单（内部卡）。**无冲突**。

---

## 9. 工作量估算与里程碑映射

| 子任务 | 内容 | 子卡 | 工时 |
|--------|------|:---:|:---:|
| C1 | cmd_chain 编号解析/继承/注入（§3.1-3.3） | A | 0.6h |
| C2 | advance 补 parents（§3.4，D0-1 修正） | A | 0.3h |
| C3 | chain_check.sh 脚本 + autopilot 挂载 + 豁免/历史判断（§4） | A | 1.0h |
| C4 | 管线侧测试 T1-T7（§11） | A | 0.6h |
| | **子卡 A 合计** | | **~2.5h** |
| C5 | memcore/seq.py next-seq + cli 接线 + 项目代码表读取（§2） | B | 0.8h |
| C6 | drift 编号三维度扩展（§5） | B | 0.8h |
| C7 | lint I5 ⑤⑥ + schema.py + SCHEMA.md 同步（§6） | B | 0.6h |
| C8 | memctl 侧测试 T8-T13（§11） | B | 1.0h |
| | **子卡 B 合计** | | **~3.2h** |

里程碑：子卡 A 归 MVP 过渡期（立即排期）；子卡 B 归 P1-2（与 gai-links 合并实现，PRD §3.3 产品裁定）。

---

## 10. 风险点

| # | 风险 | 缓解 |
|---|------|------|
| R1 | advance 补 parents 改变 kernel 门控行为 → 回归 | 家长门控与 advance 顺序语义一致（§3.4 论证）；T3/T4 覆盖建链 + 推进全流程；test_cmd_channel.sh 回归 |
| R2 | chain_check 全量误报刷屏（历史卡/内部卡） | 只扫活跃卡 + V4_EPOCH 豁免 + title 前缀豁免（§4.4）；告警挂非最大分量卡不刷主链 |
| R3 | 同编号组内多条独立开发链（同一编号被错误复用到不同任务） | 连通分量>1 即告警（§4.2）；drift 唯一性维度对 kanban 活跃卡查重（§5.2） |
| R4 | next-seq 与 GAI 手工编辑并发重号 | L1 flock + L2 写通道 CAS + L3 drift 查重（§2.2） |
| R5 | 编号 regex 误匹配（[DEV-PRD] / P1-07） | CARD_CODE_RE 带边界 + 精确 `[A-Z]{2,3}-\d{3}`（数字后缀天然排除 [DEV-PRD]）；next-seq 过滤 PROJECT_CODES 注册码（排除 P1） |
| R6 | 两仓 regex 常量漂移（cmd_chain vs mem-core） | schema.py 标注「与 devPPL pipeline/cmd_chain.py CARD_CODE_RE 同源同步」；T13 双仓交叉测试 |
| R7 | 规则落文档不落代码（OBS-01 教训） | 本设计全部落代码接线点：cmd_chain / chain_check.sh 挂 autopilot / memctl CLI；验收以「扫描/命令可执行」为准 |

---

## 11. 测试方案（dev 阶段验收映射）

### 11.1 管线侧（子卡 A，devPPL）

| # | 测试 | 验证方式 | 覆盖 |
|---|------|---------|------|
| T1 | [CMD] create dev "DPL-016: 实现登录" → prd 卡 body 首行 `编号: DPL-016` | fixture kanban.db + cmd_channel.sh 集成 | §3.2 |
| T2 | 描述无编号 → prd 卡无编号行，不阻断建卡 | 同上 | MVP 过渡 |
| T3 | advance 推进：dev 卡 parents=[arch 卡]（真实卡） | fixture 链 + advance 调用 | §3.4 |
| T4 | 拆卡场景：qa-d1 parents=[全部 dev-sub 卡] | 同 T3 + 子卡 fixture | §3.4 |
| T5 | chain_check：同编号 2 卡无链 → [chain-gap] comment；幂等不重复 | 复用 test_workspace_check.sh 模式（fixture kanban.db） | §4 |
| T6 | chain_check：正常开发链（1 连通分量）→ 无告警 | 同 T5 | §4.2 |
| T7 | chain_check 历史豁免：V4_EPOCH 前卡组 / [CMD] 前缀卡 → 不告警 | 同 T5 | §4.4 |

### 11.2 memctl 侧（子卡 B，mem-core pytest）

| # | 测试 | 验证方式 | 覆盖 |
|---|------|---------|------|
| T8 | next-seq DPL：GAI 有 DPL-009 → 返回 DPL-010 | pytest（GaiAdapter fixture） | §2 |
| T9 | next-seq 兜底：GAI 缺失 → wiki actions/ 目录 → 001 | pytest + tmp wiki | §2.1 |
| T10 | next-seq 非法 CODE（P1 / 未注册码）→ None + stderr | pytest | §2.2 |
| T11 | drift 编号三维度：存在性/唯一性/链断裂各出差异；一致 → 空 | test_drift.py 扩展（fixture kanban + wiki + GAI） | §5 |
| T12 | lint I5 ⑤⑥：task_code 缺失/格式错/索引不一致（指向不存在任务页）→ ERROR；骨架页豁免〔v4.1 订正：原 id 不同值用例废止，DPL-092〕 | test_lint.py 扩展 | §6 |
| T13 | CARD_CODE_RE 双仓一致性（cmd_chain vs mem-core regex 同串） | 双仓交叉断言 | R6 |

### 11.3 dev 完成定义

- 子卡 A：T1-T7 全绿 + autopilot.sh 实测（建测试链卡观察 chain_check 告警）+ test_cmd_channel.sh/test_workspace_check.sh 回归无破坏
- 子卡 B：T8-T13 全绿 + `memctl lint` 零问题（I5 生效后）+ `memctl drift` 输出空（编号维度）+ SCHEMA.md 与 schema.py 同步

---

## 附：与 PRD 的对应关系

- 本设计是 PRD §8 交接项 1-5 的实现方案（第 6 项已由 OC 完成）；
- 唯一实质修正：D1-1（advance 补 parents）——PRD §2 声称已覆盖但实测未覆盖；
- 三铁律、MVP 过渡、验收断言 A1-A6 口径不变；A5 由 PIPELINE.md 纪律 6 + chain_check 上线共同达成。

---

## 附：编号挂靠继承（R4 扩充，2026-09-05）

本设计上线后，DPL-125 R4（t_089db8c6 合入）在管线侧追加了「编号挂靠继承」：`number_backfill` 对 `[FIX]` 卡做 topic 匹配（去前缀/后缀、括号空白归一，相等或前缀 ≥10 字符）→ 匹配则**继承原链编号**（打 `[number-inherited]` 注释，不消耗 next-seq），无匹配才分配新号。

⚠️ 该判定只在管线建卡路径生效——**手动 `kanban_create` 绕过机制，必须自行判定**：微改/bug 修复打 `[FIX]` + parents 挂原链继承编号，禁打 `[PRD]`，禁子缀（污染 `DPL-\d+` 正则）。完整规则与 DPL-133 抢号教训见 **mem-core wiki `wiki/concepts/patterns/kanban-card-format.md` §8.5**。
