# Memory Middleware 架构设计 v1.2 — 任务页愿景落地（G1-G4 接线）

> 发言人：高见远（架构师） | 日期：2026-08-12 | 版本：v1.2
> 输入：PRD v1.2（docs/prd/memory-middleware-prd.md，commit 77ad2fe）+ SCHEMA v1.1（/workspace/mem-core/wiki/SCHEMA.md，commit 79af2e9）+ 示范三页（mem-core commit f65b1ac：WIKI-001 任务页 / devppl 项目页 / bug-lesson-template 经验页）+ 架构 v1.0（docs/arch-memory-middleware.md，893 行）
> 定位：6 步闭环 Step 2 增量 —— 在 v1.0 架构之上把 Frank 任务页愿景 4 缺口（G1-G4）落地为可执行接线设计，工程师可直接照写代码
> 核心原则：**G1-G4 不推翻 v1.0 任何定案**，只补 4 缺口；三条铁律（单一写入者 / 状态不回写 / 机械层零 LLM）在每条接线点逐点论证

---

## 0. 范围与裁决总表

### 0.1 本设计做什么（PRD §10 交接九项全覆盖，重点 1/2/7/8/9）

| # | PRD 交接项 | 本设计章节 |
|---|-----------|-----------|
| 1 | SCHEMA v1.1 定稿（page_type/project/project_folder/task_code + I5） | §2 |
| 2 | memctl CLI 接口契约（v1.2 扩展：`add task --from-kanban` / `note` / `done --collect-notes`） | §3 |
| 3 | F2 落地（mem-core 同仓目录布局与提交约定） | §4 |
| 4 | mem_meta.db schema（三表 + trigram FTS5 + bigram 回退表） | §5 |
| 5 | golden file 测试夹具（R3 三页 + 示范三页） | §6 |
| 6 | boot_context v2 集成契约（`mem context` 输出格式 + 字符预算） | §7 |
| 7 | close.sh S3 替换方案（`mem done --collect-notes` 调用点与状态镜像格式） | §8 |
| 8 | **建卡→wiki 采集链接线（G2，重点）** | §9 |
| 9 | **执行中更新接线（G3，重点）** | §10 |

另覆盖：G4 bug→经验页关联（§11）、冲突点标注（§12）、工作量分解（§13）、风险（§14）、测试方案（§15）。

### 0.2 架构裁决总表（G1-G4 接线裁决 + 三铁律合规确认）

| 决策点 | 裁决 | 说明 |
|--------|------|------|
| G1 page_type | ✅ 采纳 PRD §12.1：page_type 与 type 正交双字段 | SCHEMA v1.1 已定稿，本设计只确认 + 细化 I5 判定规则（§2.3） |
| G2 采集链触发点 | ✅ 挂 autopilot discover 注册后（register_discovered_task 之后），**否决 SQLite 触发器** | f56cd1f 证明 est_intercept 触发器只能建评估卡、不能调外部 CLI；采集链必须读卡 body + 写 wiki 文件 → 必须走 memctl CLI（§9.4） |
| G2 字段映射 | kanban.db tasks 表 36 列 → frontmatter/背景节（§9.3） | priority（INTEGER 调度值）与 wiki priority（P0-P5 业务枚举）语义不同 → 机械映射 + 背景节保留原值（ADR-1） |
| G2 幂等 | 页已存在 → exit 1，调用方忽略 | discover 只发现未注册任务，重复触发场景由 autopilot `|| true` 兜底（§9.5） |
| G3 note 锚定 | **统一锚定源卡 ID**（管线 task_id），不锚定执行子卡 | 任务页以源卡为锚（close.sh S3 同样传源卡）；拆卡场景子卡执行记录经 worker 协议回源卡页（§10.2 ADR-2） |
| G3 状态机驱动 | 源卡驱动 status（advance start_step→active / close→done）；子卡只贡献执行记录，不驱动状态 | 避免多写者并发改 status（§10.1） |
| G4 经验页 ID | `bug-<task_id>-<seq>`（确定性、不冲突） | 机械骨架先给确定性 ID；LLM 策展时可在候选集内改名并更新 links（§11.2） |
| G4 双链原子性 | `note --bug` 单次 CLI 调用内完成 任务页回链 + 经验页来源任务链，**互指原子** | 保证 lint I5 ④（经验页 ≥1 入链来自 task 页）对机械骨架同样生效（§11.3） |
| 单写入者 | ✅ 所有新接线点只调 memctl CLI，任何脚本不直接 touch wiki 文件 | autopilot.sh / discover.py / cmd_chain.py / close.sh 全部 subprocess 调 `bin/memctl`（§9.1/§10.1） |
| 状态不回写 | ✅ 采集只读 kanban.db；note/done 只写 wiki 页 status 镜像 | drift 只读兜底（§10.3） |
| 机械层零 LLM | ✅ add --from-kanban / note / done --collect-notes / 查重 / 骨架生成全部确定性 | LLM 只在 update 通道补语义（§3 各命令契约） |

### 0.3 与 v1.0 架构的关系（增量，不推翻）

- v1.0 已交付：mem-core repo（引擎 + wiki + skill 单副本）、memctl MVP 7 命令 + V2 4 命令 + V3 占位、mem_meta.db 三表 + FTS5 trigram + bigram、boot_context 第五源、close.sh S3a/S3b 替换方案、golden file 测试体系。
- v1.2 增量（本设计）：SCHEMA v1.1 确认（已有字段）+ memctl 3 个命令扩展（`add task --from-kanban` / `note` / `done --collect-notes`）+ 3 个接线点（discover 注册后 / advance start_step / close.sh S3）+ G4 查重建链流程。
- **未落地缺口标注**：mem-worker skill（PRD P0-9 声称随 repo 走，但 mem-core repo 当前无 SKILL.md）——本设计 §10.2 定义其协议内容，供 dev 阶段创建。

---

## 1. 接线全景（事件源 → memctl → wiki）

### 1.1 G1-G4 数据流图

```
                      ┌────────────────────────────────────────────────────────┐
                      │                    L0 真源（只读）                      │
                      │  kanban.db (tasks 36 列 + task_links + task_comments)  │
                      └───────────────┬────────────────────────────────────────┘
                                      │ 只读
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
    G2 建卡采集链              G3 执行中更新              G4 bug→经验页
    autopilot discover        autopilot advance          worker note --bug
    ↓ register_discovered     ↓ start_step 分支          （mem-worker 协议）
    ↓ 之后调用                 ↓ 之后调用                  ↓
    memctl add task           memctl note                memctl note --bug
      --from-kanban <id>        <id> --status active       <id> --bug ...
              │                       │                       │
              └───────────┬───────────┴───────────┬───────────┘
                          ▼                       ▼
              ┌────────────────────────┐  ┌──────────────────────────┐
              │   memctl CLI（单一写者）  │  │  memctl done --collect- │
              │  add/note/done/demote   │  │  notes（close.sh S3，    │
              │  机械骨架 + 状态镜像      │  │  完成回填兜底 OBS-01）    │
              └───────────┬────────────┘  └──────────┬───────────────┘
                          ▼                           ▼
              ┌────────────────────────────────────────────────────────┐
              │   wiki/（L3 编译知识层）                                  │
              │   actions/<task_id>.md（page_type=task）                │
              │   entities/devppl.md（page_type=project）               │
              │   concepts/patterns/bug-<task>-<n>.md（page_type=exp）  │
              │   index.md / log.md / mem_meta.db（机械维护，零 LLM）     │
              └────────────────────────────────────────────────────────┘
                          │
                          ▼
              L4 读路径：boot_context v2 第五源（mem context ≤800 字）
                        / memctl query（FTS5 trigram）+ memctl journey
```

### 1.2 写入矩阵（谁在何时写什么，全部经 memctl）

| 角色 | 何时 | 命令 | wiki 写什么 | 强制程度 |
|------|------|------|------------|---------|
| autopilot/OC | 建卡瞬间（discover 注册后） | `memctl add task <id> --from-kanban <卡ID>` | 任务页骨架（frontmatter + 背景节 + 参考节占位） | 强制（挂 discover，fail-open） |
| autopilot | advance start_step（dev 卡就绪） | `memctl note <id> --status active` | status=draft→active + 执行记录节 | 强制（挂 advance，fail-open） |
| worker | 领卡后、执行前（可选） | `memctl update --apply` | 四段式语义补全（背景/问题/验收） | 协议约定 |
| worker | 执行中 | `memctl note <id> --text "..."/--bug ...` | 执行记录节 + status 可选 | 协议约定 + done 回填兜底 |
| worker | kanban_block 时 | `memctl demote <id> --status blocked --reason "..."` | status=blocked + 执行记录节 | 协议约定 + drift 兜底 |
| close.sh S3 | 任务完成 | `memctl done <id> --result "..." --collect-notes` | 结果节 + status=done + 执行记录回填 | 强制（close.sh 已接线） |
| memctl（脚本） | 每次写入后 | index/log/双链校验/原子提交 | 机械维护 | 零 LLM |

---

## 2. SCHEMA v1.1 定稿确认（G1）

> SCHEMA v1.1 已由 commit 79af2e9 落盘（/workspace/mem-core/wiki/SCHEMA.md，168 行）。本节**确认定稿**并细化架构层判定规则；未发现需要 SCHEMA 修订的缺口（结论见 §2.4）。

### 2.1 frontmatter 字段全集确认（含 v1.2 新增）

| 字段 | 必填 | 枚举/格式 | v1.2 新增 |
|------|------|-----------|:---------:|
| id | ✅ | 唯一；ID 模式 §5；actions/ 用外部 ID | |
| type | ✅ | raw\|entity\|concept\|decision\|action | |
| page_type | 新页必填，老页推断 | task\|project\|experience\|conversation | ✅ |
| project | 可选 | 项目实体双链 `[[entities/<name>.md|显示]]` | ✅ |
| project_folder | task 含 project 时必填 | 项目文件夹绝对路径 | ✅ |
| task_code | 可选 | 项目内编号（DPL-010），与 GAI ID 对齐 | ✅ |
| status | ✅ | draft\|active\|done\|blocked\|superseded\|archived | |
| priority | action/decision 必填 | P0\|P1\|P2\|P3\|P4\|P5 | |
| mechanism | 可选 | close.sh\|cron\|skill 协议\|memctl add\|memctl done\|manual | |
| est_hours | action 必填（骨架豁免） | 数字小时 | |
| created / updated | ✅ | ISO8601 UTC | |
| source_task | 可选 | 来源 kanban 任务 ID（t_ 前缀） | |
| external_id | 可选 | 外部系统 ID（GAI 编号） | |
| links / location / profile / domain / tags / contradictions / superseded_by / archived_at | 可选 | 见 SCHEMA §4 | |

### 2.2 page_type ↔ type 映射表（I5 ② 强制映射）

| page_type | 对应 type | 目录 | 示范页 | 用途 |
|-----------|----------|------|--------|------|
| task | action | wiki/actions/ | WIKI-001 | 任务详情页（GAI 待办/kanban 卡详情） |
| project | entity | wiki/entities/ | devppl | 项目实体页（任务归属 + 项目级知识） |
| experience | concept | wiki/concepts/patterns/ | bug-lesson-template | 经验/教训页（bug+方案、复盘五段式） |
| conversation | raw | wiki/raw/sessions/ | （预留，P2） | 对话历史页（日常发现、趣事） |

**推断规则**（老页无 page_type 时）：action→task、entity→project、concept→experience（仅当位于 patterns/）、raw→conversation。推断不落盘，lint 时按此校验映射一致。

### 2.3 五不变式 I1-I5（I5 判定细则，供 dev 实现）

| # | 不变式 | 判定细则（架构层细化） |
|---|--------|----------------------|
| I1 | 断链零容忍 | 出链 wikilink 目标存在（SCHEMA §5 四级解析）；actions/ 页 ID 与外部源一致 |
| I2 | 孤儿页零容忍 | 每页 ≥2 出链且 ≥1 入链（三首页除外；index 收录视同入链；机械骨架豁免出链数、孤儿检查保留） |
| I3 | status 镜像 | action/decision 页 status 与 L0 真源一致（单向 L0→wiki）；**draft 豁免**（建卡采集时 L0 是 ready/todo，wiki 是 draft——镜像不一致合法，机制是采集先行） |
| I4 | index 与文件一致 | index.md 清单 == 文件清单；mem_meta.db 与文件一致（checksum）；骨架豁免 est_hours |
| I5 | page_type 校验（v1.1 新增，随 P1-5 落地） | ① page_type 枚举合法；② page_type↔type 映射一致（§2.2）；③ task 页含 project 时：project 双链目标存在 + project_folder 非空；④ experience 页必须有 ≥1 入链来自 task 页（任务页↔经验页双链互指校验） |

**I5 实现要点**（dev 阶段）：
- ③ 的"project 双链目标存在"复用以 I1 断链判定（`[[entities/devppl.md]]` 解析命中即通过）；project_folder 非空为字符串非空校验。
- ④ 的"入链来自 task 页"：反向遍历 links 表（mem_meta.db），找 `links.dst = 经验页路径 AND links.src_type = action`；或从经验页正文「来源任务」节解析出链再校验目标存在。两种实现二选一，推荐 links 表反向索引（机械、稳定）。
- **骨架豁免**：I5 ③ 对 status=draft 的 task 骨架同样强制（add task --from-kanban 只在项目页存在时填 project，不存在则不填 → 天然不触发 ③）；I5 ④ 对 status=draft 的经验页骨架**不豁免**（note --bug 原子保证互指，见 §11.3）。

### 2.4 SCHEMA 修订结论

**无需修订**。SCHEMA v1.1 已完整覆盖 G1-G4 需要的字段/枚举/不变式。架构层新增的约定（经验页 ID 规则、执行记录节格式、priority 机械映射）属于命令契约与正文模板范畴，不属 SCHEMA 域规则，落位 §3/§11。

---

## 3. memctl CLI 接口契约（v1.2 扩展）

### 3.1 命令总表

| 命令 | 用途 | 阶段 |
|------|------|------|
| `memctl add task <id> --from-kanban <卡ID>` | **v1.2 新增**：G2 建卡采集链——从 kanban.db 机械采集生成任务页骨架（零 LLM） | MVP + v1.2 扩展 |
| `memctl add task <id>` / `add raw <path>` | 原 MVP 命令（保留） | MVP |
| `memctl note <id> [--status ...] [--text ...] [--bug ... --solution ...]` | **v1.2 新增**：G3 执行中更新（机械追加执行记录 + 状态镜像 + G4 bug 查重建链） | v1.2（归 V2 P1-5） |
| `memctl done <id> [--result ...] [--collect-notes]` | 完成：结果节 + status=done；**v1.2 扩展 `--collect-notes`**：完成时从 kanban 卡 comment/claim 回填执行记录 | MVP + v1.2 扩展 |
| `memctl query / lint / index / status / context` | MVP 原命令（不变） | MVP |
| `memctl update / drift / gai-links / demote` | V2 原命令（不变；`demote` 是 G3 blocked 接线点） | V2 |
| `memctl mcp-serve` | V3 占位（不变） | V3 占位 |

### 3.2 退出码约定（不变）

| 码 | 含义 |
|----|------|
| 0 | 成功 / lint 零问题 / 无漂移 |
| 1 | 一般错误（参数校验失败、写入失败、**页已存在**） |
| 2 | 用法错误（未知命令/缺参，argparse 默认） |
| 3 | 校验失败（lint 有问题 / drift 发现差异 / query 语法错误） |

### 3.3 `add task --from-kanban` 详细契约（G2，零 LLM）

```bash
memctl add task <task_id> --from-kanban <卡ID> [--title "..."] [--priority P0-P5] [--no-commit]
# <task_id>：wiki 页 ID（管线源卡 ID，通常 == <卡ID>；拆卡/子任务场景可指定）
# <卡ID>：kanban.db 中要采集的卡（t_x）
```

**执行流程**（全部确定性）：
1. 校验：task_id 合法（`t_[0-9a-f]{8}` 或 ID 模式）；--priority 若给则校验枚举。
2. 只读 kanban.db（fail-open：db 不存在/卡不存在/读取异常 → 降级为无 `--from-kanban` 的旧 `add task` 行为，只填 title）。
3. 读卡字段（tasks 表 36 列 + task_links 父链 + task_comments 最近 1 条）→ 字段映射见 §9.3。
4. 生成 frontmatter（id/type=action/page_type=task/status=draft/priority/mechanism=memctl add/source_task=<卡ID>/project(推断)/project_folder(推断)/task_code(提取)/created/updated）。
5. 生成正文：`# <title>` + 「背景」节（建卡上下文：body 摘要 + 建卡信息块） + 「要解决的问题/验收标准/参考」占位 + 参考节占位（父任务双链 + 项目页双链）。
6. 页已存在 → 打印提示，exit 1（幂等语义，调用方忽略）。
7. 写入 → `_log_append` → `_maintenance`（index/log/db）→ `_git_commit`（`mem(<id>): add task <title>`）→ exit 0。

**骨架为机械中间态**：lint 豁免 I4 est_hours 必填 + I2 出链数（SCHEMA §5 既有规则）；priority 必填与孤儿检查保留；I5 ③ 只在 project 已填时校验。

### 3.4 `note` 详细契约（G3 + G4，零 LLM）

```bash
memctl note <id> [--status active|blocked|done] [--text "进展/bug/关键改动点"]
              [--bug "现象" --solution "方案"] [--no-commit]
```

**执行流程**（全部确定性）：
1. 定位页（`_find_page`：actions/<id>.md 优先，全库按 id 兜底）；页不存在 → exit 1（执行中更新要求页已存在；建卡采集链已保证骨架先行）。
2. 追加「执行记录」节条目：`- <ISO8601 UTC> — <text>`（多行 --text 按行缩进）。
3. `--status` 给定 → 更新 frontmatter status 字段 + bump updated。
4. `--bug` 给定 → 进入 G4 查重建链子流程（§11）：
   a. 追加执行记录条目（bug 现象 + 方案）。
   b. FTS5 查 concepts/patterns/ 既有经验页（按 bug 关键词查重，trigram ≥3 字词；2 字词 bigram 回退）。
   c. 命中同类 → 任务页 links 追加既有经验页双链（不重复建）。
   d. 未命中 → 建经验页骨架（page_type=experience，五段式模板，id=`bug-<task_id>-<seq>`，status=draft，mechanism=memctl add）**并**任务页 links 追加回链（互指原子）。
5. 任何变更 → bump updated → `_maintenance` → `_git_commit`（`mem(<id>): note <summary 前 50 字>`）→ exit 0。

**零 LLM 边界**：note 只追加/镜像/查重/建骨架，不改写既有正文语义；根因/教训语义补全走 `memctl update --apply`（LLM 通道，独立命令）。

### 3.5 `done --collect-notes` 详细契约（G3 完成回填）

```bash
memctl done <id> [--result "..."] [--collect-notes] [--no-commit]
```

**在 v1.0 done 基础上扩展 `--collect-notes`**（v1.0 流程：① 读 L0 ② 建/定位页 ③ 补结果节 ④ status=done ⑤ 维护 ⑥ 提交）：

1. `--collect-notes` 给定 → 完成时回填：从 kanban.db 只读 `task_comments`（最近 N=10 条）+ `tasks.result`，机械提取关键记录：
   - `[PRODUCES] <路径>` → 执行记录条目「产出: <路径>」
   - `[CLAIM]` / `[PRODUCES]` comment 的正文摘要（前 200 字）
   - 结构化 claim report（changed_files/tests_run/verification，claim-schema 格式）→ 逐项提取为执行记录条目
   - `tasks.result` 非空 → 追加「结果摘要」
2. 与既有「结果」节合并：结果节（v1.0 格式）保持，执行记录回填追加到「执行记录」节（若该节已存在 note 条目，回填条目追加其后，不覆盖）。
3. 幂等：执行记录节已有来自本 comment 的条目（按 comment id 时间戳前缀判重）→ 跳过。
4. fail-open：L0 读失败 → 仅完成 wiki 写（以 ID 为锚），退出码记 warning（沿用 v1.0 done 语义）。

**作用**：解决 OBS-01「LLM 忘记手动步骤」——执行中 worker 漏了 note，完成时 close.sh 强制路径一次性回填关键记录。

### 3.6 参数/错误码速查（dev 实现对照）

| 场景 | 命令 | 退出码 | 说明 |
|------|------|:------:|------|
| 骨架创建成功 | add task --from-kanban | 0 | |
| 页已存在 | add task | 1 | 幂等；autopilot `|| true` |
| kanban.db 不可读 | add task --from-kanban | 0（降级） | fail-open，降级旧行为 |
| 非法 ID / priority | add task | 1 | |
| 页不存在 | note | 1 | 执行中更新要求骨架先行 |
| bug 命中既有经验页 | note --bug | 0 | 只加回链不重建 |
| bug 未命中建骨架 | note --bug | 0 | 互指原子 |
| 完成回填成功 | done --collect-notes | 0 | |
| 用法错误 | 任意 | 2 | argparse |
| lint 有问题 | lint | 3 | |

---

## 4. F2 落地确认（mem-core 同仓）

### 4.1 目录布局（确认 v1.0 §2.1，无变化）

```
/workspace/mem-core/            ← 独立 git repo
├── memcore/                    # Python 确定性引擎
│   ├── schema.py / parse.py / indexer.py / lint.py / query.py
│   ├── blast.py / drift.py / context.py / gailinks.py / journey.py / learn.py
│   ├── cli.py                  # v1.2 新增: cmd_note + add --from-kanban + done --collect-notes
│   └── sources/                # source adapter（kanban 是第一个 source）
├── bin/memctl                  # CLI 入口（mem 为软链别名）
├── wiki/                       # 记忆正文
│   ├── SCHEMA.md / index.md / log.md
│   ├── actions/                # page_type=task（WIKI-001 等）
│   ├── entities/               # page_type=project（devppl 等）
│   ├── concepts/patterns/      # page_type=experience（bug-<task>-<n> 等）
│   ├── concepts/decisions/     # 决策档案
│   ├── raw/                    # 不可变源材料
│   └── _archive/
├── tests/                      # pytest + golden file
└── SKILL.md                    # mem-worker skill（v1.2 需创建，见 §10.2）
```

### 4.2 提交约定（确认 v1.0 §2.2）

- 提交粒度：按事件（add/note/done/demote/update 每次独立 commit）；正文高频提交可接受（单一写者）。
- commit message：`mem(<id>): <动作> <摘要>`（既有模式）。
- **v1.2 新增约定**：`note` 提交 `mem(<id>): note <摘要>`；经验页骨架随 note 提交同 commit（互指原子，不允许半链提交）。
- 禁止：任何人绕过 memctl 直接 touch wiki 文件（单一写入者，lint 不校验 git 来源，靠流程纪律 + repo 写权限）。

---

## 5. mem_meta.db schema 确认

确认 v1.0 §5（memcore/indexer.py 已实现），G1-G4 无 schema 变更，仅说明 G4 查重依赖：

| 表 | 用途 | G1-G4 相关 |
|----|------|-----------|
| pages | 页元数据（id/file_path/type/status/checksum…） | I4 一致性 |
| links | 双链边（src→dst） | I5 ④ 经验页入链反查 |
| events | append-only 事件日志 | 追溯 |
| term_pages | term→pages 反向索引 | blast radius |
| pages_fts（FTS5 trigram） | ≥3 字中文检索 | **G4 查重主路径** |
| bigram_index | 2 字 CJK 回退 | G4 查重 2 字词回退 |

**G4 查重查询形态**（dev 实现参考）：
```sql
-- 从 --bug "现象" 提取关键词（标题词/现象短句分词 ≥3 字）
SELECT p.file_path, p.id FROM pages_fts f JOIN pages p ON p.rowid = f.rowid
WHERE pages_fts MATCH '"<keyword1>" OR "<keyword2>"' AND p.file_path LIKE 'concepts/patterns/%'
ORDER BY bm25(pages_fts) LIMIT 3;
```
- 命中判定：BM25 命中且文件位于 concepts/patterns/ → 视为同类经验页候选；机械判定"同类" = 关键词交集 ≥1 且同一任务页曾链接 → 复用；否则建新。**保守策略**：宁建新页不误链（误链污染经验页语义，新建可被 LLM 策展合并）。

---

## 6. golden file 测试夹具（G1-G4 新增）

### 6.1 夹具清单

| 夹具 | 来源 | 用途 |
|------|------|------|
| wiki/actions/WIKI-001.md | 示范三页（commit f65b1ac） | G1 任务页 frontmatter 全字段 / I5 ③ 正向 |
| wiki/entities/devppl.md | 示范三页 | G1 项目页 / project 双链目标 |
| wiki/concepts/patterns/bug-lesson-template.md | 示范三页 | G1 经验页 / G4 五段式模板 |
| tests/golden/from-kanban-card.json | 新造（fixture） | G2 字段映射：模拟 kanban.db 卡（36 列子集） |
| tests/golden/from-kanban-db.sqlite | 新造（fixture，可脚本生成） | G2 集成：真实 sqlite 读卡 |
| tests/golden/bug-note-input.json | 新造 | G4 查重：--bug 输入样例 |

> R3 三页（concepts/decisions/r3-product/architect/engineer.md）继续作为 v1.0 既有 golden fixture（不动）。

### 6.2 测试用例清单（v1.2 新增，映射 B6-B9）

| # | 用例 | 断言（B 映射） |
|---|------|---------------|
| T1 | parse WIKI-001.md frontmatter | page_type/project/project_folder/task_code 正确解析（B6） |
| T2 | lint I5 映射校验：非法 page_type / 映射不一致 | exit 3 + 指明页（B6） |
| T3 | lint I5 ③：task 含 project 且 project_folder 空 | exit 3（B6） |
| T4 | lint I5 ④：experience 页无 task 入链 | exit 3（B9） |
| T5 | add task --from-kanban 字段映射（fixture 卡） | frontmatter 含 page_type=task/project/project_folder/task_code/source_task/created/updated；背景节含建卡上下文（B7） |
| T6 | add task --from-kanban 幂等 | 二次调用 exit 1（B7） |
| T7 | add task --from-kanban fail-open | kanban.db 缺失 → 降级旧行为 exit 0（B7） |
| T8 | note --status active | status 镜像 + 执行记录节 + updated bump（B8） |
| T9 | note --text 追加 | 执行记录节多条目、时间戳递增（B8） |
| T10 | note --bug 未命中 → 建经验页 | 经验页存在（五段式骨架）+ 任务页↔经验页双链互指 + lint 0（B9） |
| T11 | note --bug 命中 → 复用经验页 | 不重复建、任务页 links 追加既有页（B9） |
| T12 | done --collect-notes 回填 | 从 comment/claim 提取条目入执行记录节 + status=done（B8） |
| T13 | lint 对新建经验页骨架 I5 ④ 通过 | note --bug 后 lint 0（B9，回归 T4） |

---

## 7. boot_context v2 集成契约（确认 + G1 可见性）

确认 v1.0 §7（pipeline/boot_context.py 已实现 `_wiki_digest`，第五源，≤800 字，try-except 静默降级）。v1.2 无契约变更，仅新增说明：

- `mem context --scope project` 输出可包含任务页摘要（page_type=task 的 active 页）→ Frank 新会话首轮能感知当前活跃任务（北极星 C3）。
- 字符预算分配不变：wiki 段 ≤800 字、插在活跃任务段之后、低于活跃任务段优先级（PRD N10）。
- **不新增**：任务页全量不注入（C9 降级优先 + N10 页太大不能注入）。

---

## 8. close.sh S3 替换方案（v1.2 扩展 --collect-notes）

### 8.1 v1.0 方案回顾（S3a + S3b，已定案）

close.sh 实际位置：`/root/.hermes/profiles/orchestrator/scripts/close.sh`。v1.0 设计（arch-memory-middleware.md §8.2）：
- S3a（主路径，强制）：`memctl done '<TASK_ID>'` 写 wiki 详情页 + 状态镜像；fail-open（memctl 异常不挂死 close）。
- S3b（展示镜像）：GAI sed 兜底（展示层，非语义写入）。

### 8.2 v1.2 扩展：`--collect-notes` 调用点

```bash
# S3a 修改（加 --collect-notes）：
check 3a "wiki 页已编译完成（memctl done --collect-notes）" \
    "memctl done '$TASK_ID' --check 2>/dev/null || memctl lint 2>/dev/null | grep -q '零问题'" \
    "memctl done '$TASK_ID' --result '${RESULT:-}' --collect-notes 2>/dev/null || memctl done '$TASK_ID' 2>/dev/null"
```

- **调用点**：close.sh S3a 的 fix 分支（原 `memctl done '$TASK_ID'` 处）。
- **fail-open 双层**：`--collect-notes` 失败（L0 读失败等）→ 降级裸 `memctl done`；再失败 → close 继续（S3a 记 FAIL 提示手动补）。
- **状态镜像格式**：沿用 v1.0 §8.3（结果节 + status=done + updated 时间戳），`--collect-notes` 额外在「执行记录」节追加回填条目（§3.5）。
- 幂等：close.sh 每次 close 只跑一次；done 已 done → `--check` 短路（exit 0 跳过 fix）。

### 8.3 状态镜像格式（确认 v1.0 §8.3）

```markdown
## 结果（memctl done 追加）
- 状态: done
- 完成时间: <ISO8601 UTC>
- 结果摘要: <--result 或 L0 提取>

## 执行记录
- <ts> — <执行中 note 条目...>
- <ts> — [collect-notes 回填] 产出: docs/xxx.md（来自 [PRODUCES] comment）
- <ts> — [collect-notes 回填] changed_files: [...]; tests_run: N; verification: ...
```

---

## 9. 建卡→wiki 采集链接线（G2，重点）

> 对应 PRD §12.2。目标：新建待办（kanban 卡）→ 任务页骨架自动生成，零 LLM，fail-open，不违反单一写入者。

### 9.1 接线点：autopilot discover 注册后

**调用点（唯一强制路径）**：`scripts/autopilot.sh` discover 循环内，`register_discovered_task` 之后（现 L118-124 的 python3 注册块后）：

```bash
# ── G2 建卡→wiki 采集链（v1.2，fail-open）──────────────────────────
# 注册成功后机械采集任务页骨架。mem-core 缺失/失败 → 不阻塞建卡/注册。
MEMCTL_BIN="${MEM_WIKI_PATH:-/workspace/mem-core}/bin/memctl"
if [ -x "$MEMCTL_BIN" ]; then
    "$MEMCTL_BIN" add task "$NEW_TASK" --from-kanban "$NEW_TASK" \
        >/dev/null 2>&1 \
    || echo "$LOG_TAG 采集 wiki 任务页骨架 $NEW_TASK 失败（fail-open，不阻塞）"
else
    echo "$LOG_TAG memctl 不可用（$MEMCTL_BIN），跳过 G2 采集（fail-open）"
fi
```

**为什么是这里**：
- discover 循环是**现成强制路径**——每 tick 扫描 kanban.db，注册未注册的新任务；新卡注册 pipeline 的瞬间必然经过这里。
- 与 f56cd1f 的 est_intercept 触发器互补：触发器在 SQL 层拦截（只能建评估卡）；采集链在 Python/CLI 层拦截（读卡 body + 写 wiki 文件）。两者不冲突、不重复（触发器不调 memctl）。
- **接线点不违反单一写入者**：autopilot.sh 只**调用** memctl CLI，不直接 touch wiki 文件；wiki 写全部发生在 memctl 进程内（add task 的内部写入 + 机械维护 + git 提交）。接线点是"调用点"而非"写入点"。

### 9.2 fail-open 守卫设计

| 失败场景 | 行为 | 依据 |
|---------|------|------|
| memctl 不存在 / 不可执行 | 跳过采集，注册照常 | `[ -x ]` 守卫；C9 降级优先精神 |
| kanban.db 不可读 | memctl 内部降级为旧 add task（只填 title） | §3.3 step 2 |
| 页已存在（重复触发） | exit 1 → `\|\|` 忽略 | 幂等语义 |
| memctl 超时/异常 | `\|\|` 忽略，注册照常 | 不阻塞 2min 轮询主循环 |
| lint 因骨架中间态报 I2 出链不足 | 骨架豁免（SCHEMA §5） | 不产生误报 |

**不接线点**（显式不做）：
- ❌ SQLite 触发器调 memctl：SQL 层无法执行外部 CLI（f56cd1f 已证：触发器只能 INSERT 卡）；且把外部进程副作用塞进 DB 事务 = 挂死风险。
- ❌ OC kanban_create TOOL 钩子：Hermes 内核无 post-create hook；且 OC 是入口之一，discover 覆盖**所有**入口（TOOL/CLI/直连 SQL 建的卡最终都注册进 pipeline）。

### 9.3 kanban.db 字段映射表（tasks 表 36 列 → frontmatter/背景节）

实测 `PRAGMA table_info(tasks)` 36 列。映射如下（**只读**，绝不写 kanban.db）：

| kanban 列 | 值示例 | → wiki 落点 | 规则 |
|-----------|--------|------------|------|
| `id` | t_b353d348 | `id` / `source_task` | 直接映射；source_task 恒等于卡 ID |
| `title` | [Step1] 架构设计 | 正文 `# 标题` | 去掉 `[FIX]/[DEV]/[QA-` 等前缀（与 discover._card_type 同源清理） |
| `body` | 需求全文 | 「背景」节「建卡上下文」 | 截断前 2000 字（与 est card 一致）；空则占位 |
| `priority`（INTEGER 调度值） | 85 | frontmatter `priority`（机械映射）+ 背景节「建卡信息: 优先级 85」 | **ADR-1**：INTEGER（0-100+，dispatcher tiebreaker）≠ wiki P0-P5（业务枚举）。映射表：≥80→P0，≥60→P1，≥40→P2，≥20→P3，<20→P4；原值保留背景节可追溯；LLM 策展可校正。 |
| `assignee` | game-architect | 背景节「建卡信息: assignee」 | 不映射 frontmatter（无该字段） |
| `status` | ready/running/todo | **不映射**（wiki 固定 status=draft） | I3 豁免：采集先行，镜像滞后；active/done 由 note/close 驱动 |
| `created_by` | worker | 背景节「建卡信息: created_by」 | |
| `created_at`（epoch） | 1786543953 | frontmatter `created`/`updated` | epoch → ISO8601 UTC |
| `started_at` / `completed_at` | | 背景节「建卡信息」原样 | 可能为 NULL |
| `workspace_kind` | dir/worktree | → project 推断依据 | worktree 取 workspace_path 的 repo 名 |
| `workspace_path` | /workspace/devPPL | frontmatter `project_folder`（若可解析） | 目录存在才写；worktree 的 wt/<id> 不写 |
| `tenant` / `idempotency_key` | | 背景节「建卡信息」 | 链路追溯 |
| `result` | | 暂不采集（done 时处理） | |
| `task_links.parent_id`（关联查询） | t_b476baba | 「参考」节「父任务: [[actions/t_b476baba.md]]」 | 有父链才写；父页不存在 → 占位豁免（骨架） |
| `task_comments.body`（最近 1 条） | [claim 要求]... | 背景节「建卡上下文」补充 | 仅取首条非空 comment 前 300 字；无则跳过 |
| 其余列（claim_lock/worker_pid/goal_mode 等） | | 不采集 | 运行时状态，无知识价值 |

**project 推断规则**（零 LLM）：
1. workspace_path 非空且目录存在 → 取 basename（devPPL）→ 查 `wiki/entities/<basename>.md` 存在 → 填 `project: "[[entities/devppl.md|devPPL]]"` + `project_folder: <path>`。
2. 项目页不存在 → project/project_folder 不填（不建项目页——项目页创建是 LLM 策展通道 update --apply 的职责）。
3. 无法解析 → 不填；lint I5 ③ 不触发（§2.3）。

**task_code 提取规则**（零 LLM）：从 title+body 扫描 `[A-Z]+-\d{2,3}` 模式（DPL-010 / MEM-003）：
- 命中且不是本卡自身 id → 填 task_code（取第一个匹配）。
- 未命中 → 不填（LLM 策展补）。

### 9.4 为什么不是 SQLite 触发器（已否决，接线点如何不违反单一写入者）

- **否决理由（继承 PRD §12.2 + f56cd1f 实测）**：est_intercept_after_insert 触发器是 SQL 层，只能 INSERT 评估卡；无法执行外部 CLI（SQLite 不提供 subprocess）。采集链需要读 body（DB 内已有，SQL 可读）**并写 wiki 文件 + git 提交**（DB 事务内无法完成文件系统副作用 + 跨仓提交）。所以采集链挂 autopilot discover（进程层），不挂触发器（SQL 层）。
- **单一写入者论证**：触发器方案（若可行）会引入"DB 事务内写 wiki"的第二写者，反而违反单一写入者；discover 接线点保证**所有 wiki 写仍只发生在 memctl 进程内**。autopilot/OC/worker 都只是 memctl 的调用方（client），不是写者（writer）。写入矩阵见 §1.2。
- **状态不回写论证**：采集链对 kanban.db 只有 SELECT（§9.3 全表映射均为只读）；status=draft 是 wiki 自身状态，与 L0 无关。

### 9.5 幂等与边界

- **幂等**：`add task` 页已存在 → exit 1 → autopilot `|| true`。discover 只返回未注册任务（pipeline_state.db 无记录），已注册任务不会重复触发；即使重复，exit 1 静默忽略。
- **边界 A**：评估卡（[DEV-EST]/[QA-EST]）也被 discover 注册 → 同样走采集链（页面 id=t_est_xxx）。这是**特性不是 bug**：评估卡也是任务，其 wiki 页记录评估结论；但 est 卡 title 带 [DEV-EST] 前缀，前缀清理规则 §9.3 已处理。
- **边界 B**：非管线任务（assignee ∉ PIPELINE_ASSIGNEES）不进 discover → 不采集。符合 PRD 范围（管线任务第一公民）。
- **边界 C**：fail-open 后不重试（本 tick 跳过，下 tick discover 不再返回该卡——已注册）→ 骨架缺失由 drift 兜底检测（§10.3）或 done 时补建（§3.5 step 2 建/定位页）。

---

## 10. 执行中更新接线（G3，重点）

> 对应 PRD §12.3。目标：任务开始执行 → 状态镜像 active；执行中进展/bug/改动点 → 执行记录；阻塞 → blocked；完成 → done + 回填。

### 10.1 接线点：advance start_step → note --status active

**调用点（唯一强制路径）**：`scripts/autopilot.sh` start_step 分支内，dev 卡创建成功 + state 同步之后（现 L321-329 的 dev 卡就绪块后）：

```bash
# ── G3 执行中更新：任务开始执行 → wiki 状态镜像 active（v1.2，fail-open）──
MEMCTL_BIN="${MEM_WIKI_PATH:-/workspace/mem-core}/bin/memctl"
if [ -x "$MEMCTL_BIN" ]; then
    "$MEMCTL_BIN" note "$TASK_ID" --status active \
        >/dev/null 2>&1 \
    || echo "$LOG_TAG wiki 状态镜像 active $TASK_ID 失败（fail-open）"
fi
```

**为什么是这里**：
- autopilot 主循环的 start_step 分支是管线推进的**唯一入口**——每个任务从 pending → 执行必经 `advance_pipeline` 返回 start_step → 建 dev 卡 → 标记 running。此处 hook 覆盖所有管线任务。
- **状态机驱动规则（ADR-2）**：status 镜像由**源卡**驱动——`advance start_step`（源卡 dev 步 running）→ `note <源卡ID> --status active`；close.sh S3 → `done <源卡ID>`。执行子卡（dev: t_x / dev-sub-*）**不驱动**源卡 status（避免多写者竞态）；子卡执行记录经 worker 协议落源卡页（§10.2）。
- **接线点不违反单一写入者**：autopilot.sh 只调 memctl CLI；status 写发生在 memctl note 进程内。
- **状态不回写**：note --status 只写 wiki 页 frontmatter `status` 字段；kanban.db 状态由 pipeline 自身管理，memctl 不触碰。

**其它 start_step 分支**（qa-d1/qa-exec/qa-d2/va 等）**不重复 note**——只有 dev 步（任务真正开始执行）触发 active 镜像；后续步骤不改变任务页 status（任务仍 active，直到 close done）。评估步（dev-est/qa-est）不触发（评估不是执行，骨架保持 draft；评估结论由 worker 协议 note 追加）。

### 10.2 worker 协议（mem-worker skill，v1.2 需创建）

> 现状：PRD P0-9 声称 mem-worker skill 随 repo 走，但 mem-core repo 无 SKILL.md（已实测 `find . -name SKILL.md` 为空）——**缺口**。本设计定义协议内容，dev 阶段创建 `SKILL.md`（单副本，随 repo 走，各 profile skills 配置指向）。

**mem-worker skill 核心内容（v1.2）**：

```markdown
# mem-worker — 记忆中间层策展协议（随 mem-core repo 走，单副本）

## 何时调用（协议约定，OBS-01 已证纯约定会忘 → done --collect-notes 兜底）
- 领到任务卡 → 若任务页骨架缺失：`memctl add task <源卡ID> --from-kanban <卡ID>`
- 执行前补全四段式（可选，LLM）：`memctl update --apply <页ID> --reason "..."` 
  （或 /learn 通道，P2-3）
- 执行中关键进展/改动点 → `memctl note <源卡ID> --text "..."`（机械零 LLM）
- 遇到 bug + 方案 → `memctl note <源卡ID> --bug "现象" --solution "方案"`
  （自动建/链经验页，G4）
- kanban_block 时 → `memctl demote <源卡ID> --status blocked --reason "..."`
- 完成 → close.sh S3 自动 `memctl done <源卡ID> --collect-notes`（无需手动）

## 锚定规则
- 一律用**源卡 ID**（管线 task_id，body 中 task_id= 字段），不用执行子卡 ID
- 拆卡场景：dev-sub-* 子卡 worker 从卡 body 的源卡引用提取源卡 ID 再 note

## 铁律
- 不直接 touch wiki 文件（单一写入者）
- 不写 kanban.db / pipeline_state.db（状态不回写）
- note 零 LLM；语义补全走 update --apply
```

### 10.3 drift 对 status 镜像的兜底规则

`memctl drift`（V2 已有，只读）扩展检测项：

| 检测项 | 现状 | v1.2 扩展 | 处置 |
|--------|------|----------|------|
| kanban 活跃任务缺 wiki 页 | ✅ 已有（drift.py `_kanban_active`） | 保持 | 报告（周 cron 兜底） |
| wiki status vs kanban status 不一致 | ❌ 未实现（I3 lint 负责单页） | 新增：`draft 但 kanban running >24h` / `active 但 kanban todo` | 报告（不自动修，状态不回写） |
| G4 经验页孤儿（无 task 入链） | ❌ | lint I5 ④ 覆盖 | lint exit 3 |

**兜底语义**：drift 是**只读对账**（周 cron），只报告不修复；状态镜像的正确性由强制接线点（§10.1）+ 完成回填（§3.5）保证，drift 是最后防线（滞后 ≤1 周可探测，PRD §6.2）。

### 10.4 demote blocked 处理

- **接线点**：worker kanban_block 时协议约定调 `memctl demote <id> --status blocked --reason "..."`（V2 命令已有，不新增）。
- **drift 兜底**：kanban blocked 卡 wiki 仍 active → drift 报告。
- **解除 blocked**：worker unblock 后执行 `memctl note <id> --status active`（协议约定）→ status 回 active。
- **边界**：demote 只写 wiki 页 status + 执行记录节；不回写 kanban（kanban block 状态由 worker 的 kanban_block TOOL 维护）。

---

## 11. G4 bug→经验页关联（note --bug 内部流程）

> 对应 PRD §12.4。目标：bug+方案 → 自动建/链经验页（page_type=experience，五段式），任务页与经验页双链互指，同类 bug 复用不重复建。

### 11.1 查重（FTS5 关键词，零 LLM）

```bash
memctl note <task_id> --bug "现象描述" --solution "解决方案"
```

内部流程（§3.4 step 4）：
1. 追加任务页「执行记录」节条目：`<ts> — [BUG] 现象: <现象>；方案: <方案>`。
2. 提取查询词：现象/方案文本中 ≥3 字 CJK 词（trigram 直接 MATCH）+ 2 字词（bigram 回退）；排除停用词（的了是在等）。
3. FTS5 查 `concepts/patterns/` 范围（§5 查询形态）。
4. 命中判定（保守策略，宁建新不误链）：
   - 候选页 BM25 命中 **且** 现象关键词交集 ≥1 **且** 候选页有 `tags: [bug, lesson]` 或位于 patterns/ → 同类。
   - 否则 → 未命中。

### 11.2 经验页骨架生成（ID 规则 + 五段式模板）

**ID 规则**：`bug-<task_id>-<seq>`，seq 为该任务第 N 个 bug（查 `concepts/patterns/bug-<task_id>-*.md` 计数 +1）。确定性、不冲突、可追溯回源任务。LLM 策展改名时保留 `source_task` 字段追溯。

**五段式模板**（对齐示范页 bug-lesson-template）：

```markdown
---
id: bug-t_b353d348-1
type: concept
page_type: experience
status: draft
mechanism: memctl add
project: "[[entities/devppl.md|devPPL]]"   # 继承任务页 project
source_task: t_b353d348
created: <ISO8601 UTC>
updated: <ISO8601 UTC>
tags:
  - bug
  - lesson
links:
  - actions/t_b353d348.md                  # 来源任务双链（互指原子）
---
# <现象前 40 字>

## 现象
（机械骨架：<--bug 现象原文>）

## 根因
（待 LLM 策展）

## 解决方案
（机械骨架：<--solution 方案原文>）

## 教训
（待 LLM 策展）

## 来源任务
[[actions/t_b353d348.md|t_b353d348]]
```

**互指原子性**：同一 memctl note --bug 调用内——任务页 links 追加经验页 **和** 经验页来源任务节指向任务页 **同时完成**（同一次 `_maintenance` + 同一次 git 提交）。不允许半链提交（lint I5 ④ 保证，§2.3）。

### 11.3 双链互指 + I5 校验

| 校验 | 规则 | 机制 |
|------|------|------|
| 任务页 → 经验页 | 任务页 frontmatter `links` 含 `concepts/patterns/bug-*.md` | note --bug 追加（命中复用 / 未命中新建） |
| 经验页 → 任务页 | 经验页「来源任务」节 `[[actions/<task_id>.md]]` | 骨架模板固定（§11.2） |
| I5 ④ 反向校验 | links 表反查：`dst=经验页 AND src.type=action` ≥1 | lint（§2.3） |
| 复用判定 | 同类 bug 复发 → 任务页 links 追加既有经验页，不重复建 | §11.1 查重 |

**三铁律合规**：经验页创建/更新全部经 memctl CLI（单一写入者 ✅）；经验页是 wiki 编译产物，不回写 L0（✅）；查重（FTS5）与骨架生成是确定性脚本，LLM 仅在 update 通道补根因/教训（机械层零 LLM ✅）。

---

## 12. 冲突点标注（PRD vs 架构，按 D1 流程交 Product 裁定）

### 12.1 需 Product 确认的分歧（PRD 未明确，架构给出建议）

| # | 分歧点 | PRD 表述 | 架构建议 | 理由 |
|---|--------|---------|---------|------|
| D1-1 | kanban priority（INTEGER 调度值）→ wiki priority（P0-P5 业务枚举）映射 | PRD §12.2 只说"优先级"入 frontmatter | 阈值机械映射（≥80→P0 …）+ 背景节保留原值 + LLM 可校正（ADR-1，§9.3） | 两枚举语义不同，直接搬运会污染业务优先级 |
| D1-2 | 子任务/拆卡（dev-sub-*）是否驱动任务页 status | PRD §12.3 说"任务开始执行 → active" | 只源卡驱动，子卡不驱动（ADR-2，§10.1） | 避免多写者竞态；任务页锚定源卡 |
| D1-3 | 经验页 ID 命名 | PRD 未规定 | `bug-<task_id>-<seq>`（§11.2） | 确定性 + 可追溯；示范页 bug-lesson-template 是模板页非实例页 |
| D1-4 | 评估卡（[DEV-EST]）是否走采集链 | PRD 未提 | 走（页面 id=t_est_xxx） | 评估卡也是任务，评估结论值得留痕 |

> 按 D1 流程：以上 4 项本设计给出架构建议，若 Product/FRank 有不同意见，以 Product 裁定为准，dev 阶段实现按建议执行。

### 12.2 架构自行裁决（无 PRD 冲突，仅细化）

| # | 裁决 | 说明 |
|---|------|------|
| A1 | note 页不存在 → exit 1（不自动建页） | 骨架先行原则；建页是 add 的职责 |
| A2 | add task --from-kanban 不建项目页 | 项目页创建是 LLM 策展通道职责 |
| A3 | 采集链不采集 claim_lock/worker_pid 等运行时列 | 无知识价值 |
| A4 | note --bug 查重保守策略 | 宁建新不误链（§11.1） |

---

## 13. 工作量估算与里程碑映射（对齐 PRD §4 P1-5，3h）

| 子任务 | 内容 | 工时 |
|--------|------|:---:|
| C1 | cli.py：`add task --from-kanban`（字段映射 §9.3 + 背景节生成 + 幂等） | 0.8h |
| C2 | cli.py：`cmd_note`（执行记录节 + status 镜像 + bump updated） | 0.5h |
| C3 | cli.py：`done --collect-notes`（comment/claim 提取 + 判重） | 0.5h |
| C4 | G4 查重建链（FTS5 查重 + 经验页骨架 + 互指原子） | 0.6h |
| C5 | lint I5 实现（枚举/映射/project_folder/经验页入链）+ schema.py 同步 | 0.4h |
| C6 | 接线点：autopilot.sh G2（discover 后）+ G3（start_step 后）+ close.sh S3a（--collect-notes） | 0.4h |
| C7 | mem-worker SKILL.md 创建（§10.2 协议落盘） | 0.2h |
| C8 | 测试 T1-T13（§6.2）+ golden fixture | 0.6h（部分与 C1-C5 并行） |
| | **合计（P1-5）** | **~3h（含并行）** |

里程碑：全部归 V2 dev（P1-5）；MVP 门禁不受影响（I5 不生效，A2 lint 只查 I1-I4）。

---

## 14. 风险点

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 采集链在 autopilot 主循环引入外部进程调用 → 轮询延迟 | 单次调用 <1s（纯 sqlite 读 + 文件写）；fail-open + `\|\| true`；不改主循环节奏 |
| R2 | kanban.db 并发读写（dispatcher 同时写） | SQLite 读共享锁；`_kanban_read` 已有 try-except；只读连接短事务 |
| R3 | note --bug 查重误链污染经验页语义 | 保守策略宁建新不误链（§11.1）；LLM 策展合并 |
| R4 | --collect-notes 提取噪声（comment 无关内容） | 只提取结构化标记（[PRODUCES]/[CLAIM]/changed_files 等）；判重防重复 |
| R5 | 接线点被 OBS-01 遗忘 | 三个接线点全部挂**强制路径**（discover/advance/close.sh），非行为约定；mem-worker skill 只是补充 |
| R6 | I5 ④ 对机械骨架误报 | note --bug 互指原子保证（§11.3）；lint 对 status=draft 经验页不豁免但互指已满足 |

---

## 15. 测试方案（dev 阶段验收映射 B6-B9）

| 验收断言 | 测试 | 验证方式 |
|---------|------|---------|
| B6 SCHEMA page_type + 字段；示范三页 lint 零问题 | T1-T4 | `pytest tests/` + `memctl lint`（I5 生效后） |
| B7 建卡→采集链：frontmatter/背景节 | T5-T7 | fixture 卡 + 真实建卡抽查 |
| B8 执行中更新：note/状态镜像/完成回填 | T8-T9, T12 | fixture 任务页 + close.sh 集成 |
| B9 bug+方案→经验页：建/链/复用/互指/lint 0 | T10-T11, T13 | fixture 输入 + lint 回归 |

**dev 阶段完成定义**：T1-T13 全绿 + `memctl lint` 零问题（I5 生效）+ autopilot.sh/close.sh 接线点实测（建测试卡验证采集 + note + done 全链路）+ mem-worker SKILL.md 落盘。

---

## 附：与 v1.0 架构文档的关系

- v1.0（docs/arch-memory-middleware.md）是引擎本体的完整设计；本 v1.2 是其增量补丁，**不重述 v1.0 已定案内容**（SCHEMA 解析规则、indexer、query、blast、备份、替代本体红线等）。
- 实现冲突时：v1.2 优先（本设计更新）；未提及处 v1.0 继续有效。
- 本设计落盘后，SCHEMA v1.1 无需修订（§2.4 结论），两仓提交 = devPPL 本文件 + mem-core 无改动。

