# Memory Middleware（记忆中间层）— QA D1 测试方案

> 版本：v1.0 | 日期：2026-08-10 | 作者：game-qa
>
> 被测范围：`/workspace/mem-core`（独立 git repo）— 确定性引擎 `memcore/`（parse/indexer/lint/blast/drift/context）+ `bin/mem` CLI + `wiki/` 记忆正文 + 集成挂点（close.sh S3 替换 / boot_context v2 第五源 / manifest.yaml 备份 / git 原子提交）
>
> 输入文档：
> - PRD：`docs/prd/memory-middleware-prd.md`（v1.0，355 行）— **验收断言权威（§5）**
> - R3 圆桌：`docs/roundtables/r3-memory-middleware/`（product / architect / engineer / oc-summary 四卷）
> - 架构设计：`docs/arch-memory-middleware.md`（并行产出中，t_4d5938a4；本方案以 PRD 为权威，架构定稿后需对账，见 D1-F2）
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0（§1.2 判定公式 / §5 示例 / §8 SLA / §9 QA SLA / §10 发布门禁 / §11 产品红线）

---

## 0. 范围与策略总览

```
被测模块                        PRD 断言覆盖      边界/场景          环境路径
──────────────────────────────────────────────────────────────────────────────
memcore/parse.py  (确定性解析)   A3(间接)          BE-01~03          mock wiki
memcore/indexer.py (mem_meta.db) A3, A4            BE-07, BE-09      mock + 真实 db
memcore/lint.py   (四不变式)      A2, A4, A8        BE-05~06, BE-10   mock wiki
memcore/blast.py  (增量候选集)    B1                BE-07, BE-12      mock wiki
memcore/drift.py  (三方对账)      B5, B2            TS-07             mock + 真实
memcore/context.py(boot_context) A6                BE-11, BE-12      mock + 真实
bin/mem           (CLI 入口)      A2~A5, B1~B5      BE-13~14          mock + 真实
wiki/ 正文样本（首批 3 页）       A8                BE-04, BE-15      golden fixtures
close.sh S3 替换                  A5                TS-03             mock kanban
boot_context.py 第五源            A6                TS-02, TS-05      mock mem
manifest.yaml 备份接入            A7                TS-06             mock manifest
git 原子提交 / 单一写者           A1, A5            BE-10             mock repo
```

### 0.1 两条测试路径（任务书要求：mock wiki + 真实 mem_meta.db）

| 路径 | 载体 | 适用用例 | 依赖 |
|------|------|---------|------|
| **路径 A：mock wiki（临时目录夹具）** | `tests/fixtures/` 构造样本 + indexer 在临时目录生成**真实 SQLite mem_meta.db**（真实 FTS5 trigram 索引） | 单元层全量：parse / indexer / lint / blast / drift / context；全部 BE；大部分 TC | 无外部依赖，dev 未交付即可先行 |
| **路径 B：真实 mem-core repo** | `/workspace/mem-core` 真实 wiki + 真实 mem_meta.db（git 管理） | A1 / A5 / A6 / A7 / A8 集成断言；TS-01~07 端到端 | dev Step 3 交付（repo + 首批 3 页 + close.sh 替换 + boot_context v2） |

> **执行策略**：dev 未交付前，路径 B 用例标 `[skip: dev-pending]`，路径 A 先行跑通确定性引擎全量。dev 交付后两路径并联回归。真实 db 在路径 A 中**不是 mock**——索引由真实 indexer 代码构建，验证的是"wiki 文件 → db"派生链路的正确性。

### 0.2 测试目标

1. PRD §5.1 A1-A9（MVP 门禁）全绿 → **MVP 发布门禁通过**（§10：BLOCKER=0 AND MAJOR≤3 且无未裁定申诉）
2. PRD §5.2 B1-B5（V2 门禁）全绿
3. PRD §5.3 C1-C4 观测协议就绪（MVP 后 1 周首观测）
4. R3 三卷提炼的 7 项测试重点全覆盖（确定性容错 / 单副本多 profile / blast radius / trigram+bigram 边界 / 记忆宫殿标签 / 跨会话恢复 / 本体文件红线）

---

## ⚠️ D1 前置发现：契约对齐项（QA 对照 PRD §4/§5/§10 与 R3 三卷、实测环境发现）

> 系统尚未开发（mem-core repo 不存在），D1 发现是**契约级**问题——必须在 Step 3 dev 动手前由架构/产品裁定，否则测试断言与实现口径会错位。分级按标准 §1.2 判定。

| # | 冲突项 | 证据 | 影响 | 风险级别 |
|---|--------|------|------|:---:|
| **D1-F1** | **验收断言编号错位**：任务卡列出的 A1-A9 与 PRD §5.1 A1-A9 **内容完全不对应**（任务卡 A1=SCHEMA lint / A2=CLI 齐全 / A3=db 确定性生成…；PRD A1=GAI 副本删除 / A2=lint 零问题 / A3=query trigram…） | 任务卡 body vs PRD §5.1 | Step 5 VA 若按任务卡编号验收会错位（如"SCHEMA lint"并非 PRD 验收项）。**本方案一律以 PRD §5 编号为权威**。 | **BLOCKER**（验收口径错位 = VA 断言无法机械对齐） |
| **D1-F2** | **memctl CLI 命令面不一致**：PRD §4 P0-4 只列 `add/query/lint/index/status`（5 命令 MVP 骨架）；PRD §10 交接列 10 命令（含 done/gai-links/drift/context/update）；Engineer R3 §2 列 7 命令（add/update/query/lint/drift/context/status，**无 index/done**） | PRD §4 P0-4、§10 交接项 2；engineer.md §2 | A2「CLI 命令齐全」以哪个清单为准？`done`（A5 依赖）、`index --rebuild`（A4 依赖）、`gai-links`（B2 依赖）的 MVP 归属不清。**架构定稿必须给出最终命令面 + 退出码约定**。 | **BLOCKER**（A2/A4/A5/B2 可测试性直接依赖） |
| **D1-F3** | **`mem done` 是否写 GAI 冲突**：Engineer R3 §5.2 说 `mem done` = 写 wiki 详情页 + 更新 GAI 状态列（"sed 级替换"）；但 PRD §7.1 铁律 2「状态不回写环」= 中间层对 GAI 表只读不写 | engineer.md §5.2 vs PRD §7.1 铁律 2 | 若 `mem done` 直接写 GAI 文件 = 违反铁律 2；若不写，close.sh 里 GAI 的 `✅ done` 标记由谁负责？B5 三方对账（kanban vs wiki vs GAI）的前提是 wiki 有 GAI 状态镜像。 | **BLOCKER**（铁律冲突，A5/B5 断言依赖） |
| **D1-F4** | **close.sh 挂点路径未定**：实测 close.sh 位于 `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh:73`（S3 步骤 `sed -i 's/\($TASK_ID.*\)待办/\1✅ done/'`），不在 devPPL 也不在 mem-core；PRD P0-7 说"sed → mem done（替换已有强制步骤）" | 实测 close.sh:73；PRD P0-7 | 替换动作落在哪个 repo 的哪个文件？QA 集成夹具需指向准确路径。 | **MAJOR**（可测性；挂点对象需确认） |
| **D1-F5** | **首批 3 页内容对象未定**：PRD A8 要求"首批 3 页（R3 三方发言编译）"，P0-10 LLM 策展回填 | PRD A8、P0-10 | A8 断链检查 + 人工抽查的抽样对象需确认（product/architect/engineer 三卷各一页？）。 | **MAJOR**（A8 断言对象需确认） |
| **D1-F6** | **环境前置（非缺陷）**：实测 `/workspace/mem-core` 不存在；GAI 副本 `GLOBAL_ACTION_ITEMS.md` 仍在 git（A1 验收目标状态）；sqlite 3.45.1 且 FTS5 trigram 实测可用（3 字查询命中） | 实测 2026-08-10 | 路径 A 先行不受阻；路径 B 依赖 dev 交付。trigram 环境已就绪（PRD R4 风险解除，BE-13 仍需覆盖降级逻辑）。 | 依赖声明 |

**裁定要求**：D1-F1~F3 三项 BLOCKER 契约项须由产品（许清楚）+ 架构师（高见远）在 Step 3 dev 动手前给出统一口径（可并入 Step 2 架构定稿的 D1 审定）。若未裁定，路径 A 单元层仍可测，但 A2/A4/A5/B2 的断言以 PRD §4/§10 原文为准并标注 `triage_needed`。

---

## 1. 测试环境准备

### 1.1 硬件/OS

| 维度 | 要求 |
|------|------|
| OS | Linux（与生产一致，`/workspace`） |
| Python | 3.11+（标准库：sqlite3, json, subprocess, pathlib, argparse, hashlib） |
| SQLite | ≥ 3.34（trigram tokenizer；本机实测 3.45.1 可用） |
| 测试框架 | pytest ≥ 7.0 |
| git | 2.x（mem-core repo + 测试用临时 repo） |

### 1.2 路径 A：mock wiki 夹具目录结构（golden file，吸收 MEM-003）

```
tests/fixtures/
├── clean/                      # 干净 wiki 样本（lint 0 问题基准）
│   ├── SCHEMA.md               # 含 frontmatter 字段全集 + location 枚举 + 三铁律
│   ├── index.md                # 类型×空间双视角，与文件一致
│   ├── log.md                  # append-only 操作日志
│   ├── entities/
│   │   └── mem-core.md         # profile: game-qa, domain: devPPL, location: Wing-A/Room-1/Shelf-1
│   ├── concepts/
│   │   ├── decisions/
│   │   │   └── MEM-004.md      # 四段式（背景/问题/验收/参考）+ ≥2 出链
│   │   └── patterns/
│   │       └── single-writer.md
│   └── raw/
│       └── sessions/
│           └── 2026-08-10-r3.md
├── dirty/                      # 脏数据样本（容错测试）
│   ├── gai-dirty.md            # GAI L47 工时列="P3" 脏单元格 + 4 种表头变体
│   ├── bad-frontmatter.md      # 缺 id / 非法 location / 未知字段
│   ├── broken-link.md          # [[NONEXIST-999]] 断链
│   ├── orphan-page.md          # 孤儿页（无入链、不在 index）
│   └── index-mismatch/         # index.md 与文件列表不一致
├── expected/                   # golden 预期输出
│   ├── parse-gai-dirty.json    # 容错解析后的规范化输出
│   ├── lint-broken-link.json   # 预期 lint 报告（断链行号/目标）
│   ├── index-clean.json        # 预期 pages/links 表行数
│   └── blast-plan.json         # 预期候选页清单（term→pages 映射）
└── real-content/               # 首批 3 页样本（dev 交付后替换为真实 R3 三卷编译页）
```

**golden file 断言原则**：确定性引擎输出必须与 `expected/` 逐字节/逐结构一致；引擎改动必须同步提交 fixture 变更（SCHEMA 与解析器同仓同步的测试镜像）。

### 1.3 路径 B：真实环境前置清理脚本

```bash
#!/bin/bash
# 每次测试前执行，恢复干净状态（路径 B）
set -euo pipefail

# 1. 确认 mem-core repo 存在（dev 交付后）
[ -d /workspace/mem-core ] || { echo "mem-core repo 未交付 — 路径 B 跳过"; exit 2; }

# 2. 重建 mem_meta.db（派生数据，验证幂等）
cd /workspace/mem-core
bin/mem index --rebuild 2>/dev/null || python3 -m memcore.indexer --rebuild

# 3. lint 基准必须为 0（A2 前置）
bin/mem lint || { echo "lint 基准非 0 — 阻断路径 B"; exit 3; }

# 4. git 状态确认（A1：GAI 副本不在 devPPL；mem-core 干净）
git -C /workspace/devPPL ls-files | grep -q GLOBAL_ACTION_ITEMS && echo "WARN: devPPL 仍含 GAI 副本（A1 未满足）" || true
git -C /workspace/mem-core status --porcelain | head -5
```

### 1.4 Mock 策略

| 依赖 | 真实调用 | Mock 方式 | 影响用例 |
|------|---------|----------|:---:|
| `hermes kanban show` | 读取 kanban 状态 | mock 脚本返回 `status: done` / `running` JSON | A5、TS-03 |
| `mem`（boot_context 第五源） | `mem context --scope project` | ① 存在但输出超长（BE-11）② 返回非 0 退出码（TC-15）③ mem-core 路径缺失（TC-15） | A6、BE-11、TS-02 |
| GAI 文件 | close.sh 读/写 `GLOBAL_ACTION_ITEMS.md` | 临时 GAI 夹具（表头 4 变体 + L47 脏单元格） | A5、B2、B5、BE-02 |
| manifest.yaml | 备份链路读 manifest | 临时 manifest 夹具（备份根不含 mem-core → 预期 FAIL） | A7、TS-06 |
| 备份推送 | `hermes_backup_push.sh` | mock echo + exit 0 | A7、TS-06 |
| git 提交 | memctl 原子提交 | 路径 A 用临时 git repo（`git init` 空仓）；路径 B 用真实 mem-core | A1、A5、TS-01 |

**Mock 纪律**：mock 只替换**外部依赖**（kanban/GAI/manifest/备份），绝不 mock 引擎自身（parse/indexer/lint/blast/drift/context 全部真实执行）。"真实 mem_meta.db"指真实索引产物，不是预置 SQLite 文件。

### 1.5 环境预检脚本（每个测试轮次前）

```bash
python3 - <<'EOF'
import sqlite3
# 预检 trigram 可用性（PRD R4 风险；BE-13 依赖此探测）
conn = sqlite3.connect(":memory:")
try:
    conn.execute("CREATE VIRTUAL TABLE t USING fts5(x, tokenize='trigram')")
    conn.execute("INSERT INTO t VALUES ('记忆宫殿中间层宏观规划')")
    n = conn.execute("SELECT count(*) FROM t WHERE t MATCH '中间层'").fetchone()[0]
    print(f"trigram OK: {n}")
except sqlite3.OperationalError as e:
    print(f"trigram UNAVAILABLE: {e} — 触发 BE-13 降级路径")
EOF
```

---

## 2. MVP 验收测试用例（PRD §5.1 A1-A9）

### TC-01：A1 — workspace GAI 副本已从 git 删除，删除提交可追溯

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-01 |
| **对应 AC** | A1 |
| **触发条件** | dev 完成 P0-0（git rm GLOBAL_ACTION_ITEMS.md）后 |
| **前置步骤** | 1. 确认 devPPL repo 干净<br>2. 记录 `git log --oneline -3` |
| **步骤** | 1. `git -C /workspace/devPPL ls-files \| grep -i GLOBAL_ACTION_ITEMS`<br>2. 输出应为空<br>3. `git -C /workspace/devPPL log --oneline --all -- GLOBAL_ACTION_ITEMS.md \| head -3`<br>4. 最近一条应为删除提交（含 `git rm` / `remove` 语义） |
| **预期结果** | 1. grep 无输出（退出码非 0）<br>2. git log 可追溯删除提交（有明确删除 commit）<br>3. 工作区/索引均无该文件 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：GAI 副本是 wiki 第三个漂移面的隐患（数据一致性，C 级内部数据按正常公式）；用户可感知（记忆漂移 → 检索结果不可信）+ 有 workaround（手动 rm + 重新提交）→ 不达 BLOCKER。 |
| **验证命令** | `git -C /workspace/devPPL ls-files \| grep -i GLOBAL_ACTION_ITEMS; echo $?` |
| **环境依赖** | devPPL repo（路径 B） |

### TC-02：A2 — `mem lint` 零问题（干净 wiki 四不变式全过）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-02 |
| **对应 AC** | A2 |
| **触发条件** | clean/ 夹具或真实 wiki 处于一致状态 |
| **前置步骤** | 1. 准备 clean/ 夹具<br>2. 执行 `mem index` 构建 db |
| **步骤** | 1. `bin/mem lint`<br>2. 检查退出码<br>3. 检查输出格式（四不变式逐项报告）<br>4. 附带检查：`bin/mem --help` 命令面覆盖（D1-F2 裁定后对齐） |
| **预期结果** | 1. 退出码 0<br>2. 输出含四不变式逐项结果（断链 / 孤儿页 / status 镜像 / index 与文件一致），全 PASS<br>3. 无 ERROR 级输出 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：lint 是"零问题为一切提交前置"的门禁（PRD P0-4），漏检/误检 = 提交校验机制失效 = 系统健康度退化（"关键路径静默失败 → MAJOR 以上"，此处为门禁核心，无 workaround）→ BLOCKER。 |
| **验证命令** | `bin/mem lint; echo "exit=$?"` |
| **环境依赖** | clean/ 夹具（路径 A） |

### TC-03：A2 — lint 断链检测（双链校验）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-03 |
| **对应 AC** | A2、A4（双链校验通过） |
| **触发条件** | wiki 存在指向不存在页面的 wikilink |
| **前置步骤** | 将 broken-link.md（含 `[[NONEXIST-999]]`）放入夹具 |
| **步骤** | 1. `bin/mem lint`<br>2. 确认断链被报告（文件 + 行号 + 目标页）<br>3. 确认退出码非 0 |
| **预期结果** | 1. 断链项出现在报告并标记 FAIL<br>2. 退出码非 0（符合"零问题为提交前置"）<br>3. 修复后（删掉坏链）lint 归零 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 断链是双链核心不变式（PRD A4/A8 依赖）；漏检 = 编译质量不可信 + 决策追溯断链（P2 痛点直接失效），无 workaround → BLOCKER。 |
| **验证命令** | `bin/mem lint 2>&1 \| grep -A2 NONEXIST-999` |
| **环境依赖** | dirty/ 夹具（路径 A） |

### TC-04：A2 — lint 孤儿页检测

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-04 |
| **对应 AC** | A2 |
| **触发条件** | wiki 存在无入链、不在 index 的页面 |
| **前置步骤** | 将 orphan-page.md 放入夹具（无任何 `[[orphan-page]]` 入链，且 index.md 未收录） |
| **步骤** | 1. `bin/mem lint`<br>2. 确认孤儿页被报告 |
| **预期结果** | 孤儿页标记 FAIL，退出码非 0；将其加入 index 后归零 |
| **风险等级** | **MAJOR** |
| **分级依据** | 孤儿页 = 不可达知识（编译复利断裂），但页面仍可读、可经 query 命中 → 有 workaround → MAJOR。 |
| **环境依赖** | dirty/ 夹具（路径 A） |

### TC-05：A2 — lint status 镜像检测（kanban → wiki 状态镜像）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-05 |
| **对应 AC** | A2 |
| **触发条件** | kanban 任务已 done，但 wiki 页 status 字段未镜像 |
| **前置步骤** | 1. 创建页面 `entities/t_dummy.md`，frontmatter `status: active`<br>2. mock kanban 返回该任务 `status: done` |
| **步骤** | 1. `bin/mem lint`（status 镜像不变式）<br>2. 执行 `bin/mem done t_dummy`（或等效命令）<br>3. 再次 `bin/mem lint` |
| **预期结果** | 1. 首轮 lint 报告 status 不一致（FAIL）<br>2. done 后页面 `status: done`，lint 归零<br>3. 反向断言：wiki 从不写 kanban（铁律 2，见 BE-10 红线） |
| **风险等级** | **MAJOR** |
| **分级依据** | 状态镜像失效 = B5 三方对账前提破裂 + 决策追溯给出过时状态；用户可感知（状态误导）+ 有 workaround（手动改 frontmatter）→ MAJOR。 |
| **环境依赖** | mock kanban + 路径 A 夹具 |

### TC-06：A2 — lint index 与文件一致检测

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-06 |
| **对应 AC** | A2 |
| **触发条件** | index.md 列出的文件与实际文件列表不一致 |
| **前置步骤** | 构造 index-mismatch/ 夹具：① index 收录了不存在的文件 ② 存在文件未被 index 收录 |
| **步骤** | 1. `bin/mem lint`<br>2. 分别确认两类不一致都被报告 |
| **预期结果** | 两类不一致均标记 FAIL，退出码非 0；修正 index 后归零 |
| **风险等级** | **MAJOR** |
| **分级依据** | index 是导航第一入口（P2-2 会话启动协议依赖）；不一致 = 导航失效（找不到知识），但文件仍可直接读 → 有 workaround → MAJOR。 |
| **环境依赖** | dirty/ 夹具（路径 A） |

### TC-07：A3 — trigram FTS5 CJK 检索（3 字查询命中）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-07 |
| **对应 AC** | A3 |
| **触发条件** | 首批 3 页内容已入库（clean/ 或真实页） |
| **前置步骤** | 1. 构造含中文内容页面（如 raw/sessions/2026-08-10-r3.md 含"记忆中间层"）<br>2. `mem index` |
| **步骤** | 1. 对首批 3 页内容各取一个 ≥3 字中文词（如"记忆中间层" / "宏观规划" / "记忆宫殿"）<br>2. `bin/mem query <词>`<br>3. 检查命中页面 |
| **预期结果** | 1. 每个 3 字词都命中对应页（trigram）<br>2. 命中页面路径/标题正确<br>3. 零 LLM、零 API（本地 SQLite 查询，可断言无网络调用） |
| **风险等级** | **MAJOR** |
| **分级依据** | 读路径核心功能（L4 检索导航）；3 字检索失败有 workaround（LIKE 前缀 / 手工翻 index）→ MAJOR。 |
| **验证命令** | `bin/mem query 记忆中间层` |
| **环境依赖** | 路径 A（真实 indexer + 真实 FTS5） |

### TC-08：A3 — bigram 回退表（2 字查询命中）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-08 |
| **对应 AC** | A3 |
| **触发条件** | 页面含 2 字中文词（如"中间"） |
| **前置步骤** | 同 TC-07 前置 |
| **步骤** | 1. `bin/mem query 中间`<br>2. 检查是否经 bigram 回退表/LIKE 命中 |
| **预期结果** | 1. 2 字词命中对应页（trigram MATCH 0 → 回退路径生效）<br>2. 退出码 0，输出含命中页 |
| **风险等级** | **MAJOR** |
| **分级依据** | 2 字是中文查询高频形态（R3 实测 trigram 对 2 字 MATCH=0 但 LIKE 命中）；失败 = 大量查询落空，有 workaround（改为 3 字查询）→ MAJOR。 |
| **验证命令** | `bin/mem query 中间` |
| **环境依赖** | 路径 A |

### TC-09：A3 — 查询边界（1 字 / 英文 / 数字 / 不存在词）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-09 |
| **对应 AC** | A3（边界） |
| **触发条件** | 各种边界查询词 |
| **步骤** | 1. 1 字中文查询（如"记"）<br>2. 英文词（如"SCHEMA"）<br>3. 数字/ID（如"MEM-004"）<br>4. 不存在词（如"xyzzyq"）<br>5. 空参数 / 无参数调用 |
| **预期结果** | 1. 1 字查询不崩溃，返回空或最少命中（明确语义）<br>2. 英文/数字按子串命中<br>3. 不存在词返回空结果 + 退出码 0（或约定非 0 但输出明确）<br>4. 参数缺失时给出 usage 错误，退出码非 0，不抛 traceback |
| **风险等级** | **MINOR** |
| **分级依据** | 用户可感知（查询异常）但核心任务不受阻（正常 2/3 字查询可用）→ MINOR。 |
| **环境依赖** | 路径 A |

### TC-10：A4 — `mem index --rebuild` 幂等

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-10 |
| **对应 AC** | A4 |
| **触发条件** | mem_meta.db 已存在 |
| **前置步骤** | 1. 构建一次 db<br>2. 记录 db 文件哈希 + pages/links/events 表行数 |
| **步骤** | 1. `mem index --rebuild`（第一次）<br>2. 记录哈希 + 行数<br>3. `mem index --rebuild`（第二次）<br>4. 对比两次产物 |
| **预期结果** | 1. 两次 rebuild 后 db 内容一致（pages/links/events 行数相同，页内容哈希相同）<br>2. rebuild 前后 `mem lint` 均为 0<br>3. 不产生重复页 / 重复链接 |
| **风险等级** | **BLOCKER** |
| **分级依据** | db 是派生数据、唯一真源是 wiki 文件（PRD C7）；重建不一致 = 双写漂移（GAI 双份拷贝 33 天教训复发）= 数据一致性问题，无 workaround → BLOCKER。 |
| **验证命令** | `bin/mem index --rebuild && bin/mem lint` |
| **环境依赖** | 路径 A（真实 SQLite） |

### TC-11：A4 — db 派生性（删 db 重建恢复 + 篡改检出）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-11 |
| **对应 AC** | A4 |
| **触发条件** | mem_meta.db 被删除或篡改 |
| **前置步骤** | 1. 构建 db<br>2. 场景 A：删除 db 文件<br>3. 场景 B：`sqlite3 mem_meta.db "UPDATE pages SET title='hacked'"` 篡改 |
| **步骤** | 场景 A：1. `mem index --rebuild` 2. `mem lint` 3. 与原始行数对比<br>场景 B：1. 篡改后直接 `mem lint` 2. rebuild 后再次 `mem lint` |
| **预期结果** | 场景 A：rebuild 完全恢复，lint 0，行数与原始一致（派生数据可确定性重建）<br>场景 B：篡改后 lint 检出 db/文件不一致（FAIL）；rebuild 后归零 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 派生数据可恢复性 + 篡改检出 = C7 不变式的机械验证；任一失效 = db 可信度崩塌（检索/漂移建立在不可信 db 上），无 workaround → BLOCKER。 |
| **验证命令** | `sqlite3 mem_meta.db "UPDATE pages SET title='hacked'" && bin/mem lint` |
| **环境依赖** | 路径 A |

### TC-12：A5 — `mem done <ID>` 自动写 wiki 页

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-12 |
| **对应 AC** | A5 |
| **触发条件** | 关闭一个测试任务 |
| **前置步骤** | 1. mock kanban 任务 t_test_close（status: running）<br>2. 初始页面存在（骨架页）或不存在 |
| **步骤** | 1. `bin/mem done t_test_close`<br>2. 检查生成的 wiki 页<br>3. 检查 frontmatter + 内容 |
| **预期结果** | 1. 页面生成/更新：含结果节（如 `## 结果` / summary 字段）<br>2. frontmatter `status: done`<br>3. `updated` 时间戳更新为当前时间<br>4. 若骨架页不存在 → 新建页（含基础 frontmatter）<br>5. 若已存在 → 增量更新不重建（幂等） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 这是写入主路径（close.sh S3 强制挂点）；失败 = 记忆不再自动流入 wiki（P3 痛点回归）+ 任务闭环无知识沉淀，无 workaround（OBS-01 已证"记得手动调用"失败模式）→ BLOCKER。 |
| **验证命令** | `bin/mem done t_test_close && git diff --stat` |
| **环境依赖** | mock kanban + 路径 A 临时 repo |

### TC-13：A5 — close.sh S3 替换生效（sed → mem done）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-13 |
| **对应 AC** | A5 |
| **触发条件** | dev 完成 P0-7 替换 |
| **前置步骤** | 1. 定位 close.sh（D1-F4 裁定后确认路径）<br>2. mock kanban + mock mem 记录调用 |
| **步骤** | 1. `grep -n 'sed.*待办\|sed.*done' close.sh`<br>2. 运行 `close.sh t_test_close`（mock 环境）<br>3. 检查是否调用 `mem done t_test_close` |
| **预期结果** | 1. close.sh S3 不再含 GAI sed 替换（或替换为 memctl 调用）<br>2. close.sh 执行时调用 `mem done`（mock 记录到调用 + 参数正确）<br>3. close.sh 整体退出码 0（闭环完整） |
| **风险等级** | **BLOCKER** |
| **分级依据** | S3 是现有强制步骤（PRD P0-7 替换已有强制路径，非新增约定）；替换未生效 = 写入主路径名存实亡（sed 对 2026-08-10 新格式已是 no-op，等于写入路径断裂），无 workaround → BLOCKER。 |
| **验证命令** | `bash close.sh t_test_close`（mock PATH） |
| **环境依赖** | mock kanban + mock mem + close.sh 路径（D1-F4） |

### TC-14：A6 — boot_context 第五源（wiki 段输出）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-14 |
| **对应 AC** | A6 |
| **触发条件** | boot_context v2 已实现第五源 |
| **前置步骤** | 1. 构造 wiki 含最近 24h 更新的页面<br>2. 运行 `python3 pipeline/boot_context.py --print` |
| **步骤** | 1. 检查输出是否含 wiki 段（第五源）<br>2. 测量 wiki 段字符数<br>3. 检查段序（wiki 段在活跃任务段之后） |
| **预期结果** | 1. 输出含 wiki 段（标记如 `## Wiki 记忆摘要` 或约定 header）<br>2. wiki 段 ≤800 字符<br>3. wiki 段优先级低于 pipeline 活跃任务段（顺序靠后） |
| **风险等级** | **MAJOR** |
| **分级依据** | 第五源缺失 = 跨会话恢复（P4 痛点）无注入载体；用户可感知（新会话不带出上下文）+ 有 workaround（手动 mem query）→ MAJOR。 |
| **验证命令** | `python3 pipeline/boot_context.py --print \| grep -A5 'Wiki'` |
| **环境依赖** | 路径 B（boot_context.py 真实执行） |

### TC-15：A6 — 静默降级（mem-core 缺失/失败不阻塞 5min 注入）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-15 |
| **对应 AC** | A6 |
| **触发条件** | mem-core 缺失或 mem context 失败 |
| **前置步骤** | 场景 A：临时将 mem-core 路径改名（模拟缺失）<br>场景 B：mock mem 返回非 0 退出码 + stderr 报错 |
| **步骤** | 1. 运行 boot_context 注入（`--write` 或等效）<br>2. 检查是否阻塞 / 是否抛异常<br>3. 检查输出是否仍含原四源 |
| **预期结果** | 1. 注入照常完成（退出码 0）<br>2. 无 traceback / 无 wiki 段（静默跳过）<br>3. 原四源（pipeline_state / kanban / sessions / memory）不受影响 |
| **风险等级** | **BLOCKER** |
| **分级依据** | C9 硬约束（boot_context 降级优先）：mem-core 缺失不得阻塞 5min 注入；阻塞 = 全局会话上下文注入失败 = 系统健康度退化（每 5min 全量故障），无 workaround → BLOCKER。 |
| **验证命令** | 场景 A：`mv /workspace/mem-core /tmp/mem-core.bak && python3 pipeline/boot_context.py --write; echo $?` |
| **环境依赖** | 路径 B + mock mem（场景 B） |

### TC-16：A7 — 备份 manifest 包含 mem-core repo

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-16 |
| **对应 AC** | A7 |
| **触发条件** | dev 完成 P0-8 备份接入 |
| **前置步骤** | 1. 确认 manifest.yaml 位置<br>2. mock 备份推送脚本 |
| **步骤** | 1. 执行备份（mock 推送）<br>2. 检查 manifest.yaml<br>3. 检查 mem-core repo 是否被注册 |
| **预期结果** | 1. manifest.yaml 含 mem-core repo 条目（路径 + 类型）<br>2. 备份产物可确认 mem-core 内容被包含 |
| **风险等级** | **MAJOR** |
| **分级依据** | mem-core 丢失 = 全部编译知识丢失（记忆不可再生，PRD R4 单一写者红线）；有 workaround（git 远程 clone 若存在）→ MAJOR（若备份完全缺失则升级 BLOCKER，按生产影响定级）。 |
| **验证命令** | `grep -A3 'mem-core' manifest.yaml` |
| **环境依赖** | mock manifest + mock 备份 |

### TC-17：A8 — 首批 3 页四段非空 + ≥1 参考 + ≥2 出链

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-17 |
| **对应 AC** | A8 |
| **触发条件** | dev 完成 P0-10 首批真实内容 |
| **前置步骤** | 1. 确认首批 3 页对象（D1-F5 裁定）<br>2. `mem index` |
| **步骤** | 1. 对每页检查四段（背景/问题/验收/参考）非空<br>2. 检查每页 ≥1 参考来源<br>3. 检查每页 ≥2 出链<br>4. `mem lint`（断链检查）<br>5. 人工抽查内容相关性 |
| **预期结果** | 1. 3 页均四段非空<br>2. 每页 ≥1 参考<br>3. 每页 ≥2 出链（链接目标存在，无断链）<br>4. lint 0 |
| **风险等级** | **MINOR** |
| **分级依据** | 内容质量是北极星辅助手段（PRD §5.4 反指标：页数是手段不是目的）；不达标不影响功能正确性 → MINOR（若 3 页缺页则 A9 之外另行升级评估）。 |
| **环境依赖** | 路径 B（真实 3 页） |

### TC-18：A9 — pytest 套件全绿（≥15 用例，含 golden file）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-18 |
| **对应 AC** | A9 |
| **触发条件** | dev 完成 P0-5 测试体系 |
| **前置步骤** | 1. cd /workspace/mem-core<br>2. 确认测试目录存在 |
| **步骤** | 1. `pytest -q`<br>2. `pytest --collect-only -q \| tail -1` 统计用例数<br>3. 检查 golden file 测试存在（fixtures/expected 被断言） |
| **预期结果** | 1. 退出码 0，全绿<br>2. 用例数 ≥15<br>3. 至少 1 个用例断言 golden fixture（吸收 MEM-003）<br>4. 覆盖：解析器容错 / 索引幂等重建 / lint 四不变式 / trigram CJK 检索 |
| **风险等级** | **BLOCKER** |
| **分级依据** | PRD 铁律"没有测试的发布就是赌博"（QA 责任闭环）+ 发布门禁 §10；A9 不绿 = MVP 门禁不通过，无 workaround → BLOCKER。 |
| **验证命令** | `pytest -q && pytest --collect-only -q \| tail -1` |
| **环境依赖** | mem-core repo（路径 B） |

---

## 3. V2 验收测试用例（PRD §5.2 B1-B5）

### TC-19：B1 — `mem update --plan` 候选页清单 + 不读全 wiki

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-19 |
| **对应 AC** | B1 |
| **触发条件** | 新事件源（source 文件）到达 |
| **前置步骤** | 1. 构造 30+ 页 wiki（mock）<br>2. 构造 source 文件（含与 3 页相关的 term + 无关 term）<br>3. 注入文件读取计数器（pyinstrument / monkeypatch open） |
| **步骤** | 1. `bin/mem update <source> --plan`<br>2. 检查输出候选页清单<br>3. 检查命中理由（term→pages 映射）<br>4. 统计读取文件数 |
| **预期结果** | 1. 输出含候选页清单 + 每个候选页的命中理由（哪些 term 命中）<br>2. **读取文件数 < 20**（PRD B1 断言；反向索引查表，零 LLM）<br>3. `--plan` 为只读操作：不修改任何页面、不 bump updated |
| **风险等级** | **MAJOR** |
| **分级依据** | blast radius 是 200 文件墙的第一层对策（编译期问题）；读全 wiki = 墙提前到来（性能退化 P95 ≥ 3x），有 workaround（人工裁定）→ MAJOR。 |
| **验证命令** | `bin/mem update tests/fixtures/raw/source.md --plan` |
| **环境依赖** | 路径 A（30+ 页夹具） |

### TC-20：B2 — `mem gai-links` 对 5 项已回填待办零断链

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-20 |
| **对应 AC** | B2 |
| **触发条件** | 5 项最重要待办已回填四段页 |
| **前置步骤** | 1. 构造 GAI 夹具（5 行待办，含 `[[ID]]` 双链）<br>2. 构造对应详情页 |
| **步骤** | 1. `bin/mem gai-links`<br>2. 检查输出 |
| **预期结果** | 1. 输出为空（5 项全部有对应页 + 双链有效）<br>2. 人为断一条链后，输出报告该行断链（负向验证） |
| **风险等级** | **MAJOR** |
| **分级依据** | GAI→详情页双链是 P5 痛点（待办无细节）的载体；断链 = 从表点不进页、30s 追溯失效；有 workaround（手工查文件）→ MAJOR。 |
| **验证命令** | `bin/mem gai-links; echo "exit=$?"` |
| **环境依赖** | GAI 夹具 + 路径 A |

### TC-21：B3 — 5 项最重要待办回填质量

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-21 |
| **对应 AC** | B3 |
| **触发条件** | dev 完成 P1-3 回填 |
| **前置步骤** | 1. 确认 5 项待办清单（Frank 裁定优先级）<br>2. 定位对应页面 |
| **步骤** | 1. 对每页检查四段非空<br>2. 检查 ≥1 参考<br>3. 检查 ≥2 出链<br>4. `mem lint` |
| **预期结果** | 5 页均四段非空 + ≥1 参考 + ≥2 出链，lint 0 |
| **风险等级** | **MINOR** |
| **分级依据** | 内容质量（同 TC-17 反指标逻辑）；B3 是 V2 门禁项但内容缺陷不阻断功能 → MINOR（缺页则另行升级）。 |
| **环境依赖** | 路径 B |

### TC-22：B4 — 矛盾检测（contradictions 标记 + review 队列）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-22 |
| **对应 AC** | B4 |
| **触发条件** | 同 topic 两页内容冲突 |
| **前置步骤** | 1. 构造 topics/a.md（"方案 X 使用 A"）<br>2. 构造 topics/a2.md（"方案 X 使用 B"） |
| **步骤** | 1. 运行矛盾检测（`mem update` 触发或 `mem conflict` 命令，以架构定稿为准）<br>2. 检查标记<br>3. 检查 review 队列 |
| **预期结果** | 1. 冲突页被打 `contradictions:` 标记（含对方页引用）<br>2. 进入 review 队列（可列出待裁决冲突）<br>3. 解决后标记清除 |
| **风险等级** | **MAJOR** |
| **分级依据** | 矛盾不标记 = 编译质量的核心卖点（矛盾显式标记）失效 → 决策追溯给出自相矛盾结论；有 workaround（人工比对）→ MAJOR。 |
| **环境依赖** | 路径 A |

### TC-23：B5 — 周 drift 三方对账为空

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-23 |
| **对应 AC** | B5 |
| **触发条件** | kanban / wiki / GAI 三方一致 |
| **前置步骤** | 1. 构造一致状态（mock kanban done ↔ wiki status done ↔ GAI ✅ done） |
| **步骤** | 1. `bin/mem drift`<br>2. 检查输出<br>3. 负向验证：单方改状态（如 wiki 改回 active）→ 再次 drift |
| **预期结果** | 1. 一致时输出为空<br>2. 不一致时报告差异（哪方漂移 + 期望/实际）<br>3. 退出码区分（一致 0 / 不一致非 0） |
| **风险等级** | **MAJOR** |
| **分级依据** | drift 是写路径三层保险的兜底层（滞后 ≤1 周可探测）；失效 = 漂移静默累积（数据一致性），有 workaround（人工对账）→ MAJOR。 |
| **验证命令** | `bin/mem drift; echo "exit=$?"` |
| **环境依赖** | mock kanban + GAI 夹具 |

---

## 4. 北极星长期观测（PRD §5.3 C1-C4）

> 北极星为**长期观测项**，不做自动化断言（PRD：MVP 验收 = §5.1 全绿；北极星为长期观测）。观测协议就绪性在 QA 阶段验收：观测点 + 记录载体 + 首观测时间。

### TC-24：C1 — Frank 重复教的次数归零（首观测点：MVP 后 1 周）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-24 |
| **对应 AC** | C1 |
| **观测方式** | Frank 主观记录 / OC 会话日志；QA 提供观测模板（记录纠正事件 → 是否复发 → 复现日期） |
| **首观测点** | MVP 交付后 1 周（2026-08-17 前后） |
| **观测协议** | 1. QA 在 MVP 交付时建立纠正事件基线（已纠正事件清单）<br>2. 每周检查新会话是否重复出现已纠正事件<br>3. 计数 Frank 重复教的次数 |
| **预期结果** | 基线期记录 ≥1 个已知纠正场景；1 周观测窗口内重复教次数 = 0（长期目标） |
| **风险等级** | 观测项（无缺陷级别） |
| **环境依赖** | 生产会话（Frank 真实使用） |

### TC-25：C2 — 决策追溯时长 ≤30s

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-25 |
| **对应 AC** | C2 |
| **观测方式** | 计时实测：Frank 问"X 为什么这么做" → 给出四段页的耗时 |
| **观测协议** | 1. 预置 3 个可追溯决策（如 MEM-004 / DPL-011 / close.sh S3）<br>2. 模拟提问：`mem query <ID>` 或导航 → 读页 → 回答<br>3. 计时 |
| **预期结果** | 单次追溯 ≤30s（含 query + 读页 + 合成回答） |
| **风险等级** | 观测项 |
| **环境依赖** | 路径 B 真实内容 |

### TC-26：C3 — 新会话首轮主动带出正确上下文

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-26 |
| **对应 AC** | C3 |
| **观测方式** | 新会话首轮观察：最近纠正 + 活跃决策 + 当前任务是否被主动带出 |
| **观测协议** | 1. 制造已知纠正事件（如"梦境报告投递方式"）<br>2. 开新会话<br>3. 观察首轮 boot_context / 主动输出 |
| **预期结果** | 首轮输出含最近纠正 + 活跃决策 + 当前任务（三项至少两项命中） |
| **风险等级** | 观测项 |
| **环境依赖** | 生产会话 |

### TC-27：C4 — 同一纠正跨会话复发次数 = 0

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-27 |
| **对应 AC** | C4 |
| **观测方式** | 跟踪已知纠正事件（如 Roundtable-B 梦境报告事件），统计跨会话复发次数 |
| **观测协议** | 1. 选定 2 个已知纠正事件<br>2. 每周检查会话日志是否复发<br>3. 复发时通过 wiki 页追溯根因（为何没带出） |
| **预期结果** | 观测窗口内复发次数 = 0；若复发，输出根因分析（wiki 页缺失 / 检索未命中 / 注入未触发） |
| **风险等级** | 观测项 |
| **环境依赖** | 生产会话 |

---

## 5. 边界条件测试用例（BE-01 ~ BE-15）

### BE-01：frontmatter 脏数据容错（GAI L47 工时列="P3"）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-01 |
| **对应 AC** | A3（间接，确定性引擎） |
| **触发条件** | frontmatter 含脏值（枚举外取值、错误类型） |
| **步骤** | 1. 构造 `工时: P3`（期望枚举 `0.2h/1.5h/3h` 等）、`status: DONE`（大小写错误）、`updated: 昨天`（非 ISO 时间）<br>2. 运行 parse<br>3. 运行 lint |
| **预期结果** | 1. 解析不崩溃（容错），脏值进入告警/规范化通道<br>2. lint 对脏 frontmatter 报可读错误（字段名 + 位置），退出码非 0 但**不抛 traceback**<br>3. 不影响同目录其他页面解析 |
| **风险等级** | **MAJOR** |
| **分级依据** | 确定性引擎的容错是"脏数据不炸"的第一道防线（R3 实测 GAI 表 L47 真实存在脏单元格）；解析器崩溃 = 编译管线整体失败（数据一致性），修复后重跑可恢复 → 有 workaround → MAJOR。 |
| **环境依赖** | dirty/ 夹具 |

### BE-02：4 种表头 9 张表解析容错

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-02 |
| **对应 AC** | A3（间接） |
| **触发条件** | GAI 源表格存在 4 种表头变体、9 张表 |
| **步骤** | 1. 构造 4 种表头变体（`# | ID | 待办 |`、`| 编号 | 任务 | 状态 |`、无表头分隔线、合并单元格）<br>2. 构造 9 张表样本<br>3. 运行 parse → 检查规范化输出 |
| **预期结果** | 1. 每张表可解析出 ID 列 + 内容列（容错不丢行）<br>2. 脏单元格（如 L47 工时列="P3"）不阻断整表解析<br>3. golden 输出与 expected/parse-gai-dirty.json 一致 |
| **风险等级** | **MAJOR** |
| **分级依据** | GAI 是第一个 source adapter（R3 反共识 1：不需要 gai.py 表感知解析器，但 `mem gai-links` 仍需读表）；表解析崩溃 = 双链校验/GAI 适配不可用，有 workaround → MAJOR。 |
| **环境依赖** | dirty/ 夹具 |

### BE-03：wikilink 解析规则（`[A-Z]+-\d{3}` → actions/；非法格式）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-03 |
| **对应 AC** | A4（双链校验） |
| **触发条件** | wikilink 各种合法/非法形态 |
| **步骤** | 1. 合法：`[[MEM-004]]`、`[[entities/mem-core]]`（路径式）、`[[ID|显示文本]]`（带别名）<br>2. 非法：`[[no-dash]]`、`[[   ]]`（空白）、`[[]]`（空）、嵌套 `[[[MEM-004]]]`<br>3. 运行 parse + lint |
| **预期结果** | 1. 合法链接解析为目标页（含 actions/ 目录映射规则）<br>2. 非法格式不崩溃，lint 报格式错误<br>3. 别名链接解析出正确目标 |
| **风险等级** | **MAJOR** |
| **分级依据** | wikilink 是双链地基（MEM-004 升格 P0）；解析错误 = 断链误报/漏报（数据一致性），有 workaround → MAJOR。 |
| **环境依赖** | dirty/ 夹具 |

### BE-04：单副本多 profile（frontmatter `profile:` 标签隔离）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-04 |
| **对应 AC** | A8（间接，N8 单副本硬约束） |
| **触发条件** | 一个 repo 含多个 profile 的知识 |
| **步骤** | 1. 构造 3 页，`profile:` 分别 = game-qa / game-architect / game-dev<br>2. `mem index`<br>3. `mem query <词>`（跨 profile 命中）<br>4. 若有按 profile 过滤参数，验证过滤正确 |
| **预期结果** | 1. 一个 repo 容纳多 profile 页，不要求复制 wiki（N8）<br>2. 检索可跨 profile 命中（默认不隔离）<br>3. 若实现 profile 过滤，过滤结果精确（只含目标 profile 页） |
| **风险等级** | **MAJOR** |
| **分级依据** | 单副本是 Frank 裁定硬约束（不要 12 个 profile 副本）；实现为多副本/无法区分来源 = 记忆碎片化回归（P3），有 workaround（人工维护）→ MAJOR。 |
| **环境依赖** | 路径 A |

### BE-05：location 枚举校验（Wing/Room/Shelf）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-05 |
| **对应 AC** | A2（frontmatter 校验入 lint） |
| **触发条件** | location 字段合法/非法值 |
| **步骤** | 1. 合法：`location: devPPL/Wing-A/Room-1/Shelf-1`（按 SCHEMA 枚举格式）<br>2. 非法：`location: 随便写`、缺字段、路径层级错误<br>3. `mem lint` |
| **预期结果** | 1. 合法值通过<br>2. 非法值 lint 报错（字段名 + 位置）<br>3. SCHEMA 中 location 枚举完整可校验 |
| **风险等级** | **MINOR** |
| **分级依据** | 空间标签是导航增强（记忆宫殿，P2-1），非法标签不阻断核心读写；用户可感知（导航错乱）但不影响任务完成 → MINOR。 |
| **环境依赖** | dirty/ 夹具 |

### BE-06：页面 >200 行 lint 告警

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-06 |
| **对应 AC** | C4 约束（每页 ≤200 行） |
| **触发条件** | 页面超 200 行 |
| **步骤** | 1. 构造 250 行页面<br>2. `mem lint` |
| **预期结果** | lint 报页面超长（告警级或 FAIL 以架构定稿为准），提示拆子页 + 交叉链 |
| **风险等级** | **MINOR** |
| **分级依据** | 超长页面是 200 文件墙的诱因之一（长期退化），单页超限不阻断当前功能 → MINOR。 |
| **环境依赖** | 路径 A |

### BE-07：增量更新幂等（同一事件重复触发同一结果）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-07 |
| **对应 AC** | B1（V2，增量更新约定 C5） |
| **触发条件** | 同一 source 事件被重复处理 |
| **步骤** | 1. `mem update <source> --apply <pages>`<br>2. 记录页面内容哈希<br>3. 再次 `mem update <source> --apply <pages>`<br>4. 对比 |
| **预期结果** | 1. 两次 apply 结果一致（骨架页已存在则更新不重建，杜绝重复页）<br>2. updated 时间戳：第二次 apply 不 bump（无变化）或按约定 bump（以 SCHEMA 为准）<br>3. lint 0 |
| **风险等级** | **MAJOR** |
| **分级依据** | 幂等是增量更新约定（C5）的核心；非幂等 = 重复页/重复链接累积（数据一致性），有 workaround（手动清理）→ MAJOR。 |
| **环境依赖** | 路径 A |

### BE-08：冲突内容双版本并存（contested 标记）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-08 |
| **对应 AC** | B4（间接） |
| **触发条件** | 同一事实两页表述不同且暂不裁决 |
| **步骤** | 1. 构造同 topic 两页冲突内容<br>2. 运行矛盾检测 → 确认 contested/双版本标记<br>3. 两页均保留（不删一方） |
| **预期结果** | 1. 两页共存且互标 contested<br>2. 索引正常收录两页<br>3. 检索时两页都命中（不静默选一） |
| **风险等级** | **MINOR** |
| **分级依据** | 双版本并存是 B4 的既有行为（矛盾显式标记），影响面是内容呈现，不阻断核心任务 → MINOR。 |
| **环境依赖** | 路径 A |

### BE-09：mem_meta.db 被篡改 → lint 检出（双写漂移防护）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-09 |
| **对应 AC** | A4（间接，C7 派生数据） |
| **触发条件** | 外部进程（非 memctl）篡改 db |
| **步骤** | 1. 构建 db<br>2. `sqlite3 mem_meta.db "UPDATE links SET target='hacked'"`<br>3. `mem lint`<br>4. `mem index --rebuild` → 再次 lint |
| **预期结果** | 1. 篡改后 lint 检出（db 与文件不一致）<br>2. rebuild 后归零 |
| **风险等级** | **MAJOR** |
| **分级依据** | 派生数据防护（复用 GAI 双份拷贝教训）；外部写 db 不被检出 = 漂移静默积累，rebuild 可恢复 → 有 workaround → MAJOR。 |
| **验证命令** | 同 TC-11 场景 B |
| **环境依赖** | 路径 A |

### BE-10：🔴 红线 — memctl 不修改 Hermes 本体文件（编译产物先存在、本体保持现状）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-10 |
| **对应 AC** | PRD §7.2 红线（替代 soul.md / memory.md / hermes.md / SKILL.md 必须 Frank 逐项签字） |
| **触发条件** | memctl 任一命令执行（add/done/update/index） |
| **步骤** | 1. 记录本体文件哈希：`~/.hermes/` SOUL.md、profile memory、`.hermes.md`、任一 SKILL.md<br>2. 依次执行 `mem add` / `mem done` / `mem index --rebuild` / `mem update --apply`<br>3. 再次哈希对比<br>4. 检查 memctl 源码：是否含对上述路径的写操作 |
| **预期结果** | 1. 全部本体文件哈希不变（memctl 只写 mem-core repo 内）<br>2. 源码无任何本体文件写路径（grep 验证）<br>3. 若出现替换提案 → 必须有四段式决策页 + 迁移脚本 + 回退方案 + Frank 签字记录 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 红线 §7.2 是 Frank 硬约束（未签字 = 不替换）；违反 = 越权修改 Hermes 本体（数据完整性 + 权限边界），无 workaround → BLOCKER。 |
| **验证命令** | `sha256sum <本体文件>` 前后对比；`grep -rn 'soul.md\|hermes.md\|SKILL.md' memcore/ bin/` |
| **环境依赖** | 路径 A 或 B |

### BE-11：boot_context wiki 段超 800 字截断

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-11 |
| **对应 AC** | A6（字符预算） |
| **触发条件** | 最近 24h 更新页过多，摘要超 800 字 |
| **步骤** | 1. 构造 20+ 更新页<br>2. `mem context --scope project`<br>3. 测量输出长度 |
| **预期结果** | 1. 输出 ≤800 字符（截断或精选，不超预算）<br>2. 截断不破坏 markdown 结构（不出现半个表格/代码块） |
| **风险等级** | **MINOR** |
| **分级依据** | 字符预算溢出是体验退化（注入超限可能挤占其他源），有 workaround（减少更新量）→ MINOR。 |
| **环境依赖** | 路径 A |

### BE-12：会话启动协议文件读取 10-20 个

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-12 |
| **对应 AC** | P2-2（会话启动协议；V2/P2 功能） |
| **触发条件** | 新会话启动执行协议 |
| **步骤** | 1. 构造 50+ 页 wiki<br>2. 运行启动协议（SCHEMA → index → log 最近 30 条 → 定向读相关页）<br>3. 注入文件读取计数器<br>4. 统计读取文件数 |
| **预期结果** | 1. 读取文件数 10-20 个（PRD P2-2 约定）<br>2. 全确定性路径（零 LLM 检索调用）<br>3. 输出摘要含最近活动 + 活跃任务关联页 |
| **风险等级** | **MAJOR** |
| **分级依据** | 启动协议是全 wiki 加载的替代方案（200 文件墙的读侧对策）；读取数失控 = context 膨胀（性能退化），有 workaround（人工定向读）→ MAJOR。 |
| **环境依赖** | 路径 A（50+ 页夹具） |

### BE-13：sqlite < 3.34 降级路径（关键词评分 + LIKE 前缀）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-13 |
| **对应 AC** | A3（降级），PRD R4 风险 |
| **触发条件** | 目标环境 sqlite 无 trigram tokenizer |
| **步骤** | 1. 预检脚本探测（§1.5）<br>2. 模拟：在无 trigram 环境（或 mock tokenizer 不可用）运行 `mem query`<br>3. 检查降级路径 |
| **预期结果** | 1. 探测到无 trigram 时不崩溃<br>2. 降级到关键词评分 + LIKE 前缀（仍可命中，精度下降）<br>3. 输出标注降级模式（可观测） |
| **风险等级** | **MAJOR** |
| **分级依据** | 降级路径缺失 = 低版本 sqlite 环境完全不可检索（功能阻断）；本机 3.45.1 正常但有 workaround（升级 sqlite）→ MAJOR。 |
| **环境依赖** | 路径 A（模拟环境） |

### BE-14：空 wiki / 缺 SCHEMA 容错

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-14 |
| **对应 AC** | A2（间接） |
| **触发条件** | wiki 目录为空 / SCHEMA.md 缺失 / wiki 路径不存在 |
| **步骤** | 1. 场景 A：空 wiki（无任何页）→ `mem index` / `mem lint`<br>2. 场景 B：删 SCHEMA.md → `mem lint`<br>3. 场景 C：`mem query` 指向不存在路径 |
| **预期结果** | 1. 空 wiki：index 建空表，lint 报"缺 SCHEMA"等可读错误，不崩溃<br>2. 缺 SCHEMA：lint 明确报错（SCHEMA 是三铁律载体）<br>3. 不存在路径：报错 + 退出码非 0，无 traceback |
| **风险等级** | **MAJOR** |
| **分级依据** | 缺 SCHEMA 是配置错误（C 级内部配置）；引擎崩溃 = 无从诊断（可读性失效），报错可读则问题可控 → MAJOR。 |
| **环境依赖** | 路径 A |

### BE-15：归档移出活跃索引（_archive/）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-15 |
| **对应 AC** | P3-1（200 文件墙对策第 4 层） |
| **触发条件** | done/superseded 页面移入 `_archive/` |
| **步骤** | 1. 构造 1 页 done 状态 → 移入 `_archive/`<br>2. `mem index --rebuild`<br>3. `mem lint`<br>4. `mem query <归档页词>` |
| **预期结果** | 1. 归档页不进活跃索引（index 不含）<br>2. lint 0（归档区不触发活跃区不变式，或以 SCHEMA 约定为准）<br>3. 归档页仍可被显式路径访问（不删除） |
| **风险等级** | **MINOR** |
| **分级依据** | 归档是规模对策（>50 页才触发），不归档不阻断当前功能 → MINOR。 |
| **环境依赖** | 路径 A |

---

## 6. 端到端场景测试用例（TS-01 ~ TS-07）

### TS-01：写→存→读全链路（纠正闭环价值链）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-01 |
| **对应 AC** | A2/A3/A4/A5/A8（MVP 全链路） |
| **前置步骤** | 干净临时 repo + mock 环境 |
| **步骤** | 1. `mem add`（新决策/纠正事件，含四段内容）<br>2. `mem index --rebuild`<br>3. `mem query <3字词>`（命中新页）<br>4. `mem lint`（0 问题）<br>5. 检查 git 提交（原子提交、提交信息含事件 ID）<br>6. `mem done` 关闭关联任务 → 再次 lint |
| **预期结果** | 1. 全链路各命令退出码 0<br>2. 新页可检索（trigram 命中）<br>3. lint 前后均为 0<br>4. git log 有原子提交记录 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 这是 MVP 的价值闭环（产品 §5.1：写→存→读）；任一环节断裂 = 纠正闭环不通（P1/P4 痛点未解决），无 workaround → BLOCKER。 |
| **环境依赖** | 路径 A 临时 repo |

### TS-02：纠正闭环（纠正事件 → 落 wiki → boot_context 带出）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-02 |
| **对应 AC** | A6 + 北极星 C1（价值链场景） |
| **前置步骤** | 1. mock mem context 返回已知纠正摘要<br>2. boot_context.py 真实执行 |
| **步骤** | 1. 模拟 Frank 纠正事件（如"梦境报告投递方式改为 X"）→ `mem add`<br>2. 运行 boot_context --write<br>3. 检查输出含该纠正摘要<br>4. 开新会话模拟：检查首轮上下文 |
| **预期结果** | 1. 纠正内容落 wiki 页（四段非空）<br>2. boot_context wiki 段含该纠正<br>3. 模拟新会话首轮可带出（观测协议就绪） |
| **风险等级** | **MAJOR** |
| **分级依据** | 这是北极星价值链的机械部分；boot_context 带出失败有 workaround（手动 mem query）→ MAJOR。 |
| **环境依赖** | 路径 B + mock |

### TS-03：close.sh 全闭环（kanban done → mem done → wiki + 镜像 + drift）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-03 |
| **对应 AC** | A5 + B5 |
| **前置步骤** | 1. mock kanban 任务 running<br>2. GAI 夹具含该任务行（待办状态）<br>3. 临时 repo |
| **步骤** | 1. mock kanban 置 done<br>2. 运行 close.sh（真实脚本 + mock PATH）<br>3. 检查 wiki 页（结果节 + status=done + updated）<br>4. 检查 GAI 状态列（✅ done，D1-F3 裁定后按口径）<br>5. `mem drift` |
| **预期结果** | 1. close.sh 退出码 0<br>2. wiki 页生成且状态镜像<br>3. drift 三方对账一致（空输出） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 这是写入主路径的端到端验证（R2 三层保险的主路径）；闭环断裂 = 记忆不流入 + 状态不一致（数据一致性），无 workaround → BLOCKER。 |
| **环境依赖** | mock kanban + GAI 夹具 + close.sh 路径（D1-F4） |

### TS-04：增量更新场景（新源 → --plan → 裁定 → --apply → lint 0）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-04 |
| **对应 AC** | B1 |
| **前置步骤** | 30+ 页 wiki + 新 source 文件 |
| **步骤** | 1. `mem update <source> --plan` → 人工裁定候选集（mock 裁定：接受全部）<br>2. `mem update <source> --apply <pages...>`<br>3. `mem lint`<br>4. 检查 updated bump + log 追加 |
| **预期结果** | 1. plan 只读、候选集合理（命中理由可解释）<br>2. apply 只改候选页（git diff 只含候选集）<br>3. lint 0<br>4. log.md 追加本次更新事件 |
| **风险等级** | **MAJOR** |
| **分级依据** | 增量更新是 200 文件墙编译侧对策；apply 范围失控（改非候选页）= 漂移风险，有 workaround → MAJOR。 |
| **环境依赖** | 路径 A |

### TS-05：跨会话恢复场景（协议 5 步 → 上下文摘要）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-05 |
| **对应 AC** | P2-2（会话启动协议） |
| **前置步骤** | 50+ 页 wiki，含最近更新 + 活跃任务关联页 |
| **步骤** | 1. 模拟新会话启动<br>2. 执行启动协议（SCHEMA → index → log → 定向读页）<br>3. 合成上下文摘要<br>4. 检查摘要质量（上次做到 X / 决策 Y / 任务 Z） |
| **预期结果** | 1. 摘要含最近活动 + 活跃决策 + 当前任务<br>2. 读取文件数 10-20（计数器验证）<br>3. 无 LLM 检索调用（零 API 断言） |
| **风险等级** | **MAJOR** |
| **分级依据** | 跨会话恢复是 P4 痛点（上下文断点）的解决方案；恢复质量差有 workaround（Frank 重复解释——但这是北极星要消灭的）→ MAJOR。 |
| **环境依赖** | 路径 A（50+ 页） |

### TS-06：备份恢复场景（备份 → clone → lint 0）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-06 |
| **对应 AC** | A7 |
| **前置步骤** | 1. mem-core repo 含内容<br>2. mock 备份推送 |
| **步骤** | 1. 执行备份<br>2. 确认 manifest 含 mem-core<br>3. 模拟恢复：`git clone` 备份副本到临时目录<br>4. 临时目录内 `mem index --rebuild` + `mem lint` |
| **预期结果** | 1. manifest 含 mem-core<br>2. clone 后可重建 db，lint 0（备份完整可恢复） |
| **风险等级** | **MINOR** |
| **分级依据** | 备份是 BKP-003 既有链路扩展；mem-core 本身有 git 版本（双重保险）→ MINOR。 |
| **环境依赖** | mock manifest + 临时 repo |

### TS-07：周 drift 兜底（制造漂移 → mem drift 检出）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-07 |
| **对应 AC** | B5 |
| **前置步骤** | 一致状态三方（kanban ↔ wiki ↔ GAI） |
| **步骤** | 1. 人为制造漂移：单方修改 wiki status（不回写 kanban）<br>2. `mem drift`<br>3. 检查检出<br>4. 修复漂移 → 再次 drift |
| **预期结果** | 1. drift 检出漂移源（哪方 + 期望/实际）<br>2. 修复后 drift 空输出<br>3. 全程只读（不自动修复，输出对账报告） |
| **风险等级** | **MAJOR** |
| **分级依据** | 兜底层失效 = 漂移滞后探测失败（数据一致性）；有 workaround（人工对账）→ MAJOR。 |
| **环境依赖** | mock kanban + GAI 夹具 |

---

## 7. 风险矩阵

| 风险 | 级别 | 可能性 | 影响 | 缓解 |
|------|:---:|:---:|------|------|
| D1-F1 验收编号错位 | **BLOCKER** | 确认存在 | VA 断言与 PRD 对不齐 | 本方案以 PRD §5 为准；D1 审定确认 |
| D1-F2 memctl 命令面不一致 | **BLOCKER** | 确认存在 | A2/A4/A5/B2 断言依赖命令存在 | 架构定稿给出最终命令面 + 退出码 |
| D1-F3 mem done 写 GAI 冲突 | **BLOCKER** | 确认存在 | A5/B5 断言依赖写 GAI 口径 | 架构/产品澄清铁律 2 边界 |
| D1-F4 close.sh 挂点路径 | **MAJOR** | 确认存在 | TS-03 夹具指向错误 | 架构确认替换对象 |
| D1-F5 首批 3 页对象 | **MAJOR** | 确认存在 | A8 抽查对象不清 | 产品确认 3 页对象 |
| BE-10 本体文件红线被越 | **BLOCKER** | 低 | 越权改 Hermes 本体 | 哈希对比 + 源码 grep 硬断言 |
| 路径 B 依赖 dev 交付延迟 | **MAJOR** | 中 | 集成用例延迟执行 | 路径 A 先行，路径 B 标 skip |
| mock 不准确导致假阳性 | **MAJOR** | 中 | 集成用例可信度 | mock 仅限外部依赖（§1.4 纪律）+ code review |
| trigram 环境差异 | **MAJOR** | 低 | A3 断言失败 | 预检脚本（§1.5）+ BE-13 降级验证 |
| 首批真实内容质量参差（R6） | MINOR | 高 | A8 措辞不达标 | 只求四段非空 + ≥1 参考 + ≥2 出链 |

---

## 8. 测试执行顺序与依赖

```
Round 0: 契约裁定 + 环境预检（路径 A 先行，无外部依赖）
  ├── D1 审定：F1~F5 裁定（产品 + 架构）
  ├── 环境预检（§1.5 trigram 探测 + §1.3 清理）
  ├── TC-18 前置检查：pytest 骨架存在（dev 交付后）
  └── 路径 A 夹具构造（golden fixtures 评审）

Round 1: 确定性引擎单元层（mock wiki，真实 db 产物）
  ├── TC-02/03/04/05/06: lint 四不变式
  ├── TC-10/11: index 幂等 + db 派生性
  ├── BE-01/02/03: 脏数据容错（GAI L47 / 4 表头 / wikilink）
  └── BE-05/06/09/13/14/15: 枚举/超长/篡改/降级/空wiki/归档

Round 2: 检索与 CLI（mock wiki）
  ├── TC-07/08/09: trigram / bigram / 边界查询
  ├── BE-04: 单副本多 profile
  └── TC-19: blast radius（30+ 页夹具 + 读计数器）

Round 3: 集成层（mock 外部依赖 + 真实脚本）
  ├── TC-13: close.sh S3 替换（需 D1-F4 路径）
  ├── TC-14/15: boot_context 第五源 + 静默降级
  ├── TC-16: manifest 备份
  ├── BE-10: 本体文件红线（哈希 + grep）
  └── BE-11: 800 字预算

Round 4: 端到端场景（路径 B 真实 repo，需 dev 交付）
  ├── TS-01: 写→存→读全链路
  ├── TS-02: 纠正闭环
  ├── TS-03: close.sh 全闭环
  ├── TS-04: 增量更新
  ├── TS-05: 跨会话恢复
  ├── TS-06: 备份恢复
  └── TS-07: 周 drift 兜底

Round 5: 内容验收 + 回归
  ├── TC-01: A1 GAI 副本删除（git 追溯）
  ├── TC-12: mem done 写页
  ├── TC-17/21: 首批 3 页 + 5 项回填质量
  ├── TC-20/22/23: gai-links / 矛盾检测 / drift
  ├── TC-18: pytest 全绿（≥15 用例）
  └── 全量回归：Round 1-4 快照对比

Round 6: 北极星观测协议初始化（MVP 交付后立即）
  ├── TC-24: 纠正事件基线（≥1 已知场景）
  ├── TC-25: 3 个决策页预置 + 计时
  ├── TC-26/27: 观测模板 + 周检查机制
  └── 首观测：MVP 后 1 周（2026-08-17）
```

---

## 9. 测试用例统计

| 分类 | 数量 | BLOCKER | MAJOR | MINOR | 观测项 |
|------|:---:|:---:|:---:|:---:|:---:|
| MVP 验收（A1-A9，TC-01~18） | 18 | 8 | 8 | 2 | 0 |
| V2 验收（B1-B5，TC-19~23） | 5 | 0 | 4 | 1 | 0 |
| 北极星观测（C1-C4，TC-24~27） | 4 | 0 | 0 | 0 | 4 |
| 边界条件（BE-01~15） | 15 | 1 | 8 | 6 | 0 |
| 端到端场景（TS-01~07） | 7 | 2 | 4 | 1 | 0 |
| **合计** | **49** | **11** | **24** | **10** | **4** |

---

## 10. QA 初步判定

| 判定维度 | 结论 |
|---------|------|
| **可测试性** | ⚠️ 部分可测——路径 A（mock wiki + 真实 mem_meta.db）在 dev 未交付即可覆盖确定性引擎全量（约 30 用例）；路径 B 集成用例（A1/A5/A6/A7/A8 + TS）依赖 dev 交付 repo + close.sh 替换 + boot_context v2。 |
| **覆盖目标** | PRD §5 全部断言：A1-A9（18 用例）、B1-B5（5 用例）、C1-C4（4 观测项）；R3 七项测试重点全部映射到 BE/TS 用例（见 §0.2）。 |
| **pytest 目标** | mem-core 自带 pytest ≥15 用例（TC-18 断言），QA 执行层在其上叠加路径 A 夹具用例（不并入 mem-core 库，避免测试义务混淆——MEM-003 已吸收为中间层测试义务，QA 夹具是独立的验收层）。 |
| **阻塞项** | D1-F1/F2/F3 三项 BLOCKER 契约项必须在 Step 3 dev 动手前裁定；D1-F4/F5 两项 MAJOR 在 Round 3/5 前裁定即可。 |
| **测试时间估算** | Round 0：1h；Round 1：2.5h；Round 2：1.5h；Round 3：2h；Round 4：2.5h；Round 5：2h；Round 6：1h。总计约 **12.5h**（不含 dev 交付等待）。 |
| **发布门禁建议（§10）** | MVP：11 项 BLOCKER 用例全 PASS + A1-A9 全绿 → 门禁通过。若测试执行中发现真实缺陷，按 §1.2 公式定级，BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉方可发布。 |
| **红线确认** | BE-10 是红线守护用例（§7.2）：任何 memctl 命令不得修改 soul.md / memory.md / hermes.md / SKILL.md，违反即 BLOCKER。 |

---

## 11. D1 审定 Checklist

审定会需确认以下问题（产品 + 架构，建议并入 Step 2 架构定稿审定）：

- [ ] **D1-F1 验收编号**：确认以 PRD §5 编号为唯一权威（A1-A9 / B1-B5 / C1-C4），任务卡编号作废。VA 阶段按本方案对齐。
- [ ] **D1-F2 memctl 命令面**：MVP 命令全集是 5 个（add/query/lint/index/status）还是含 done/drift/context？`done`（A5）、`index --rebuild`（A4）、`gai-links`（B2）、`drift`（B5）、`context`（A6）各自落在 MVP 还是 V2？每个命令的退出码约定（0=成功/非0=失败的具体语义）。
- [ ] **D1-F3 mem done 写 GAI 口径**：`mem done` 是否更新 GAI 文件状态列？若更新，与铁律 2（状态不回写环）的边界如何界定（wiki 状态镜像 ≠ GAI 真源写）？若由 close.sh 保留 sed，替换后 GAI 标记谁负责？
- [ ] **D1-F4 close.sh 挂点**：替换对象是 `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh` 还是另有副本？替换的发布路径（哪个 repo 提交）？
- [ ] **D1-F5 首批 3 页对象**：R3 三卷各编一页，还是按其他口径？（建议：product / architect / engineer 三卷各一页，天然覆盖四段式 + 双链）
- [ ] **BE-10 红线验证口径**：本体文件清单（soul.md / memory.md / .hermes.md / SKILL.md）与哈希基线由谁维护？QA 每次回归前重取？
- [ ] **pytest 用例分布**：≥15 用例中 golden file 用例占比（建议 ≥5）；QA 验收层夹具与 mem-core 自带 pytest 的边界。
- [ ] **测试优先级**：若时间有限，D1 必须通过的用例（建议：TC-02/03/10/11/12/13/15/18 + 全部 BLOCKER 级 BE/TS）。

---

## 12. 分级依据对照（标准 §1.2 / §8 / §10 落实说明）

| 标准条款 | 本方案落实 |
|---------|-----------|
| §1.2 判定公式 | 每个 TC 的"风险等级"= 该行为若失败/回归时真实缺陷的级别，按公式判定并附"分级依据"；无法判断时取高级别 + `triage_needed`（§1.3） |
| §2 安全漏洞独立判定 | 本系统为本地记忆库（C 级内部数据），无 OWASP 暴露面；BE-10 红线按数据完整性/权限边界定级 BLOCKER |
| §3 性能退化 | TC-19（读文件数<20）、BE-12（10-20 文件）为编译期/读路径性能断言；不满足按 MAJOR |
| §8 SLA | D1 发现按 BLOCKER 4h 响应 + 8h 定位 + 24h 方案起算（裁定项非代码缺陷，以"方案"形式产出即满足）；测试执行中发现缺陷后按 §9 QA SLA 提交 |
| §9 QA SLA | 发现缺陷后 1h 内提交（复现步骤 + 环境 + 预期 vs 实际 + 复现率）；BLOCKER 回归 4h 内 / MAJOR 1 工作日 |
| §10 发布门禁 | MVP 门禁 = A1-A9 全绿 + BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉；§10.1 回归范围（BLOCKER 修模块 + 1 级依赖 + 核心冒烟） |
| §11 产品红线 | BE-10（替代本体文件）必须 Frank 逐项签字，未签字 = 不替换；本方案将红线落为可执行断言 |

---

> QA 测试方案完毕。下一步：D1 审定（产品 + 架构）裁定 F1-F5 → Round 0 环境预检 → 路径 A 先行执行确定性引擎全量；dev 交付后并联路径 B 集成与端到端。
