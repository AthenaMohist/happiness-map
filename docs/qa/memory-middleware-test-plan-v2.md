# Memory Middleware（记忆中间层）— QA 测试方案 v2

> 版本：v2.0 | 日期：2026-08-10 | 作者：game-qa（Frank 游戏开发团队 QA）
>
> 被测范围：`/workspace/mem-core`（独立 git repo，commit 27673b9）— 确定性引擎 `memcore/`（parse/indexer/lint/query/blast/drift/context/schema）+ `bin/memctl` CLI（+ `bin/mem` 软链）+ `wiki/` 记忆正文（6 页）+ 集成挂点（close.sh S3a/S3b / boot_context.py 第五源 / manifest.yaml 备份 / git 原子提交）
>
> 输入文档（**全部为定稿后版本，v1 方案作废**）：
> - PRD v1.1：`docs/prd/memory-middleware-prd.md`（355 行，commit 87731a4 + e1cc11c 修订）— **验收断言唯一权威（§5）**
> - 架构定稿 v1.0：`docs/arch-memory-middleware.md`（889 行，commit 78fc583）— CLI 命令面以 §4.1 为最终契约
> - D1 裁定三卷：`docs/roundtables/d1-memory-middleware/`（product 裁定 + architect 评审 + engineer 确认）
> - 实测基线：mem-core commit 27673b9（51 pytest pass / wiki 6 页 / lint 0）、devPPL fe482f8（boot_context v2 第五源）、9ae67d0（GAI 副本已删）、close.sh 双份 md5 fd22da95
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0（§1.2 判定公式 / §5 示例 / §8 SLA / §9 QA SLA / §10 发布门禁 / §11 产品红线）

---

## 0. v1 → v2 差异说明（为什么重出）

第一版方案（`docs/qa/memory-middleware-test-plan.md`，992 行 49 用例）是**架构定稿前并行产出**，D1 评审暴露 5 项契约错位（D1-F1~F5）。经 D1 三方裁定全部修复，本 v2 基于**定稿后的真实接口**重出：

| D1 契约项 | v1 错位 | v2 处理（本方案） |
|-----------|---------|------------------|
| F1 验收编号 | 任务卡编号 ≠ PRD §5.1 | 一律锁 PRD §5.1 A1-A9 / §5.2 B1-B5 / §5.3 C1-C4；每用例标注编号 |
| F2 CLI 命令面 | PRD §4 5 命令 / §10 10 命令矛盾 | 12 命令定稿面（MVP 7 + V2 4 + V3 占位 1），正式名 `memctl` + `mem` 软链，退出码 0/1/2/3；**全部用例引用 `bin/memctl`**，另加软链断言 |
| F3 mem done 写 GAI | 方案假设 done 可能写 GAI | `memctl done` 只写 wiki（结果节 + status=done + bump updated + 维护 + 提交），对 kanban/GAI 只读（铁律 2）；GAI ✅ done 归 close.sh S3b sed（行尾追加 + 幂等守卫） |
| F4 close.sh 挂点 | 指向 backup-repo 路径 | 活体 = `/root/.hermes/profiles/orchestrator/scripts/close.sh`（S3a=memctl done --check / S3b=sed），backup-repo 镜像同 md5；**双份同改同验 + md5 断言** |
| F5 首批 3 页 | 对象未定 | 3 页 = `wiki/concepts/decisions/r3-{product,architect,engineer}.md`（实测存在），type=decision 四段式，profile=game-director/game-architect/game-engine |

另吸收 Architect D1 卷 3 个非阻塞缺口（本方案已补齐专用用例）：
1. `memctl demote`（V2）→ B 组新增 BC-05
2. `memctl status` 无专用断言 → A2 组新增 TC-06
3. `memctl done` fail-open 分支（L0 读失败仍写 wiki）→ BE 组新增 BE-17

以及 Engineer D1 卷 3 个对齐注记（全部采纳）：
1. CLI 名统一 `bin/memctl` + 软链存在断言（TC-21）
2. BE-02 断言对象改为 gai-links 适配器输出（非全表解析）
3. TS-06 备份恢复 = clone + `index --rebuild` + lint（mem_meta.db 是 gitignore 派生数据不备份）

---

## 1. 真实接口基线（架构定稿后实测，方案断言以此为准）

> 以下全部为 2026-08-10 在 /workspace/mem-core（commit 27673b9）与 /workspace/devPPL（fe482f8）实测确认，不是文档假设。

### 1.1 CLI 命令面（架构 §4.1，D1-F2 定稿）

| 命令 | 阶段 | 实测行为 | 实测退出码 |
|------|------|---------|:---:|
| `memctl add task <id> [--title] [--priority]` | MVP | 建 actions/<id>.md 骨架（frontmatter + 四段占位）；从 kanban.db 只读 title | 0；非法 ID/priority → 1；页已存在 → 1 |
| `memctl add raw <path> [--tag]` | MVP | 复制不可变源材料进 wiki/raw/<tag>/ | 0；源不存在 → 1；非法 tag → 1 |
| `memctl done <ID> [--result] [--no-commit] [--check]` | MVP | `--check` dry-run：页存在且 done → 0；页不存在 → 1；页存在但未 done → 3。真实执行：结果节 + status=done + bump updated + log + 维护 + 提交；L0 只读 fail-open | 0/1/3 |
| `memctl query <terms…> [--limit] [--type] [--json]` | MVP | FTS5 trigram（≥3 字）→ bigram 回退（2 字 CJK）→ LIKE；无 db → 1；无 terms → 2；无命中 → 0 输出（无命中） | 0/1/2 |
| `memctl lint [--strict] [--json]` | MVP | 四不变式全过 → 0；有问题 → 3 | 0/3 |
| `memctl index [--rebuild]` | MVP | 构建/幂等重建 mem_meta.db；rebuild 后 lint 仍 0（实测 before=0/rebuild=0/after=0）；**注意：rebuild 会向 log.md append 一条 index_rebuild 事件** | 0 |
| `memctl status` | MVP | 页数按 type 分 / 最近 5 事件 / lint 摘要 / git 状态 | 0 |
| `memctl context --scope project\|task [--id] [--max-chars]` | MVP | project 三子段（≤800 字）；task 需 --id；无 db → 1 | 0/1/2 |
| `memctl update / drift / gai-links / demote` | V2 | 当前 stub，输出占位提示 | 2（占位） |
| `memctl mcp-serve` | V3 占位 | 占位提示 | 2 |

**软链**：`bin/mem` 是 `bin/memctl` 的 symlink（实测 `lrwxrwxrwx mem -> memctl`），两名字同一入口。

### 1.2 SCHEMA 定稿（架构 §3 / wiki/SCHEMA.md）

- 5 节点类型：raw / entity / concept / decision / action（目录映射见 schema.py TYPE_DIRS）
- frontmatter 必填 5 字段：id / type / status / created / updated；action 额外必填 priority + est_hours；decision 额外必填 priority
- wikilink 解析四级：ID 模式 `[A-Z]+-\d{2,3}` → actions/ → 相对路径 → 名称映射（index title→id）→ 别名；全部失败 = 断链（I1）
- location taxonomy：`<wing>/<room>/<shelf>` 三段小写 slug；合法例 `devppl/memory/architecture`；**非法负样本 `Wing-A` / `Room-1` / `Shelf-1`**（lint I4 报 location 未注册）
- 四不变式（lint）：I1 断链零容忍 / I2 孤儿页零容忍（≥2 出链且 ≥1 入链，SCHEMA/index/log 三首页除外）/ I3 status 镜像（L0 单向，L0 不可达跳过）/ I4 index 与文件一致 + frontmatter 结构校验

### 1.3 mem_meta.db（架构 §5，派生数据）

- pages / links / events / term_pages 四表 + FTS5 trigram（pages_fts）+ bigram_index 回退表
- 唯一真源 = wiki 文件；`memctl index --rebuild` 幂等（实测 0/0/0）；db 不提交 git（.gitignore）

### 1.4 集成挂点（实测）

| 挂点 | 实测位置 | 行为 |
|------|---------|------|
| close.sh S3a | `/root/.hermes/profiles/orchestrator/scripts/close.sh:96-100` | `memctl done '$TASK_ID' --check` 验证 wiki 页已写；失败则 `memctl done '$TASK_ID' --result 'close.sh 闭环补写'` 语义写入 |
| close.sh S3b | 同文件 :102-106 | `sed -i "/$TASK_ID/{/✅ done/!s/$/ ✅ done/}"` 行尾追加展示镜像，幂等守卫；GAI 文件路径经 MEM_GAI_FILE |
| close.sh 双份 | 活体 + `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh` | **md5 相同（fd22da95aef4f009da169b4437c9a1e2 实测）**，同改同验 |
| boot_context 第五源 | `/workspace/devPPL/pipeline/boot_context.py:143-196` | `_wiki_digest()` try-except 静默降级；MEM_WIKI_PATH 缺失跳过；wiki 段插在活跃任务段之后、≤800 字、防御性截断 |
| 备份 manifest | `/workspace/manifest.yaml` | 含 `- path: /workspace/mem-core/`（2 处引用，实测） |
| GAI 副本删除 | devPPL git | `git ls-files | grep GLOBAL_ACTION_ITEMS` 为空（实测）；删除提交 9ae67d0 可追溯 |

### 1.5 首批 3 页实测基线（A8 断言对象）

| 页 | type | profile | location | 四段 | 参考/出链 |
|----|------|---------|----------|------|----------|
| r3-product.md | decision | game-director | devppl/memory/architecture | 背景/问题/验收/参考 非空 | ≥1 参考 + ≥2 出链（lint I1/I2 PASS 佐证） |
| r3-architect.md | decision | game-architect | devppl/memory/architecture | 同上 | 同上 |
| r3-engineer.md | decision | game-engine | devppl/memory/architecture | 同上 | 同上 |

> ⚠️ 任务书口径确认：engineer 页 profile=**game-engine**（非 game-qa，实测一致）；D1-F5 裁定文中的 profile 列表与实测有出入，以实测 + 任务书为准。

---

## 2. 测试环境（已实测就绪）

| 维度 | 状态 |
|------|------|
| mem-core repo | /workspace/mem-core，commit 27673b9，51 pytest 全绿，wiki 6 页，lint 0 |
| sqlite | 3.45.1（≥3.34），FTS5 trigram 实测可用（`query "中间层"` 命中） |
| Python/pytest | 系统 python3 3.11.15 + pytest 9.1.1（venv pip SSL 挂，用系统 python） |
| devPPL 集成 | boot_context v2 第五源已集成（fe482f8）；GAI 副本已删（9ae67d0） |
| close.sh | 活体 + 备份镜像双份 md5 一致（fd22da95） |
| manifest | /workspace/manifest.yaml 已含 mem-core |
| 路径隔离 | 测试用临时 MEM_WIKI_PATH / MEM_DB_PATH / MEM_GAI_FILE / MEM_KANBAN_DB 指向夹具，**不得污染真实 repo**（实测：环境变量必须显式 unset，否则残留污染真实路径——见 §7 坑位） |

### 2.1 双路径（任务书要求 3）

| 路径 | 载体 | 适用用例 | 依赖 |
|------|------|---------|------|
| **路径 A：mock wiki 夹具** | `tests/golden/`（已有 6 样本）+ 临时目录；indexer 在临时目录生成**真实 SQLite mem_meta.db**（真实 FTS5 trigram） | 单元层全量：parse / indexer / lint / query / blast / drift / context / CLI 命令面；全部 BE；TC-02~11 | 无外部依赖，mem-core 已交付即可全跑 |
| **路径 B：真实 mem-core repo** | /workspace/mem-core 真实 wiki + mem_meta.db + git；devPPL 集成挂点实测 | A1 / A5 / A6 / A7 / A8 / A9 集成断言；TS-01~07；红线用例 | devPPL + mem-core + close.sh 活体 + manifest |

> 路径 A 的"真实 mem_meta.db"不是 mock——索引由真实 indexer 代码构建，验证"wiki 文件 → db"派生链路正确性（A4/C7）。

---

## 3. MVP 验收测试用例（PRD §5.1 A1-A9）

### TC-01：A1 — workspace GAI 副本已从 git 删除，删除提交可追溯

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-01 |
| **PRD 断言** | A1（§5.1）；架构 §0.3 / §2.3 |
| **路径** | 路径 B |
| **步骤** | 1. `git -C /workspace/devPPL ls-files \| grep GLOBAL_ACTION_ITEMS`<br>2. `git -C /workspace/devPPL log --oneline --diff-filter=D -- GLOBAL_ACTION_ITEMS.md` |
| **预期结果** | 1. 无输出（副本已删除）<br>2. 存在删除提交 9ae67d0 |
| **风险等级** | **BLOCKER**（A1 是 MVP 门禁断言；双份拷贝是 wiki 第三漂移面的源头） |
| **分级依据** | 标准 §1.2：A1 断言失败 = 双份拷贝未消灭，漂移风险直接回归 → 无 workaround → BLOCKER |
| **环境依赖** | devPPL repo |

### TC-02：A2 — `memctl lint` 零问题（真实 repo 四不变式全过）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-02 |
| **PRD 断言** | A2（§5.1）；架构 §3.7 / §4.3 |
| **路径** | 路径 B（真实 repo 为发布门禁基准）+ 路径 A（干净夹具） |
| **步骤** | 1. `cd /workspace/mem-core && unset MEM_WIKI_PATH`<br>2. `./bin/memctl lint` |
| **预期结果** | 1. 退出码 0<br>2. 输出含四不变式 I1-I4 全部 PASS + "零问题" |
| **风险等级** | **BLOCKER**（A2 是 lint 门禁；零问题为一切提交前置，PRD P0-4） |
| **分级依据** | 标准 §1.2：lint 失败 = 编译质量不可验证（互链/镜像/索引全无保障）→ BLOCKER |
| **环境依赖** | mem-core repo（lint 前需 index 保证 db 存在） |

### TC-03：A2 — lint I1 断链检出（正/负样本）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-03 |
| **PRD 断言** | A2；架构 §3.3 / §3.7 I1 |
| **路径** | 路径 A（golden/broken-links.md） |
| **步骤** | 1. 临时 wiki 复制 golden/broken-links.md（含 `[[NONEXIST-999]]` 断链）<br>2. `memctl lint` |
| **预期结果** | 1. 退出码 3<br>2. 报告含 `[I1:ERROR] ... 断链: [[NONEXIST-999]]` |
| **风险等级** | **BLOCKER**（I1 零容忍是四不变式之首） |
| **分级依据** | 标准 §1.2：断链 = 知识导航断裂（P2 决策可追溯的机制载体失效）→ BLOCKER |
| **环境依赖** | 路径 A |

### TC-04：A2 — lint I2 孤儿页检出（正/负样本）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-04 |
| **PRD 断言** | A2；架构 §3.7 I2 |
| **路径** | 路径 A（golden/orphan-page.md） |
| **步骤** | 1. 临时 wiki 复制 golden/orphan-page.md（无入链 + 出链 <2）<br>2. `memctl lint` |
| **预期结果** | 1. 退出码 3<br>2. 报告含 `[I2:ERROR] ... 出链不足` 或 `孤儿页` |
| **风险等级** | **BLOCKER** |
| **分级依据** | 孤儿页 = 知识孤岛（与"互链完整"编译质量度量直接冲突）→ BLOCKER |
| **环境依赖** | 路径 A |

### TC-05：A2 — lint I3 status 镜像检出（L0 单向只读）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-05 |
| **PRD 断言** | A2；架构 §3.6 / §3.7 I3；铁律 2 |
| **路径** | 路径 A（mock kanban.db 夹具，MEM_KANBAN_DB 指向） |
| **步骤** | 1. 构造 actions/t_12345678.md（status=active）+ mock kanban.db 中该任务 status=done<br>2. `memctl lint`<br>3. 反向：wiki=done / kanban=running |
| **预期结果** | 1. 报告含 `[I3:ERROR] status 镜像不一致: wiki=active kanban=done`<br>2. 反向同样检出<br>3. **全程只读**：mock kanban.db 内容不变（铁律 2 断言） |
| **风险等级** | **BLOCKER**（状态镜像失真是"wiki 不存状态"边界的机械保障） |
| **分级依据** | 标准 §1.2：镜像不一致 = 追溯失真（决策页说 done 但 L0 未 done）→ BLOCKER |
| **环境依赖** | 路径 A + mock kanban |

### TC-06：A2 — `memctl status` 输出完整性（Architect 缺口 2）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-06 |
| **PRD 断言** | A2（间接）；架构 §4.3 status 契约 |
| **路径** | 路径 B |
| **步骤** | 1. 真实 repo 运行 `./bin/memctl status`<br>2. 逐项核对输出 |
| **预期结果** | 1. 退出码 0<br>2. 输出含：wiki 路径 / db 存在标志 / 页数按 5 type 分 / 最近 5 事件 / lint 摘要（断链数、孤儿数）/ git 状态 |
| **风险等级** | **MINOR**（status 是诊断辅助命令；输出缺项可人工补查） |
| **分级依据** | 标准 §1.2：诊断信息不完整有 workaround（直接跑 lint/index 看输出）→ MINOR |
| **环境依赖** | 路径 B |

### TC-07：A2 — lint I4 index 与文件一致检出 + frontmatter 结构校验

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-07 |
| **PRD 断言** | A2 / A4；架构 §3.7 I4 |
| **路径** | 路径 A |
| **步骤** | 1. 临时 wiki：文件清单 ≠ index.md 收录清单（加一个未收录文件 + index 收录一个不存在文件）<br>2. `memctl lint` |
| **预期结果** | 1. 退出码 3<br>2. 报告含 `[I4:ERROR] 文件存在但 index.md 未收录` 与 `index.md 收录但文件不存在` |
| **风险等级** | **MAJOR**（index 失真是目录失效，可手动修复） |
| **分级依据** | 标准 §1.2：index 不一致可被 `memctl index` 重建修复（有 workaround）→ MAJOR |
| **环境依赖** | 路径 A |

### TC-08：A3 — trigram CJK 检索（≥3 字词命中对应页）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-08 |
| **PRD 断言** | A3（trigram 分支）；架构 §4.3 / §5 FTS5 |
| **路径** | 路径 A（golden 3 页）+ 路径 B（真实 3 页） |
| **步骤** | 1. `memctl query "中间层"`<br>2. `memctl query "记忆中间层"`（首批 3 页正文高频词）<br>3. 核对命中页含 r3-{product,architect,engineer} 至少其一 |
| **预期结果** | 1. 退出码 0，命中列表含对应页<br>2. 输出含 id/type/file_path/location/snippet |
| **风险等级** | **BLOCKER**（A3 是 CJK 检索主路径；PRD 北极星辅助指标依赖检索可用） |
| **分级依据** | 标准 §1.2：检索失效 = 决策追溯 ≤30s 的机制载体失效，无 workaround（手动翻 wiki 不满足 30s）→ BLOCKER |
| **环境依赖** | 路径 A/B（先 index） |

### TC-09：A3 — bigram 回退表（2 字词命中）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-09 |
| **PRD 断言** | A3（bigram 分支）；架构 §4.3 / §5 bigram_index |
| **路径** | 路径 A + 路径 B |
| **步骤** | 1. `memctl query "中间"`（2 字）<br>2. 确认 trigram 对 2 字返回 0 后走 bigram_index 命中 |
| **预期结果** | 1. 退出码 0，命中（实测 2 字"中间"命中 4 页）<br>2. 输出不报错、不空 |
| **风险等级** | **BLOCKER**（2 字中文词是 GAI/决策标题常见粒度；回退失效 = 2 字检索全断） |
| **分级依据** | 标准 §1.2：2 字检索是 CJK 语言的普遍需求，失效无 workaround → BLOCKER |
| **环境依赖** | 路径 A/B |

### TC-10：A3 — 查询边界（1 字 / 英文 / 数字 / 不存在词 / --type / --json）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-10 |
| **PRD 断言** | A3（间接，LIKE 分支）；架构 §4.3 query 契约 |
| **路径** | 路径 A |
| **步骤** | 1. `memctl query "记"`（1 字 → LIKE）<br>2. `memctl query "SCHEMA"`（英文）<br>3. `memctl query "P0-19"`（ID）<br>4. `memctl query "不存在的词xyz"`（无命中）<br>5. `memctl query 中间层 --type decision --json` |
| **预期结果** | 1. 有内容词命中对应页；无命中输出（无命中）退出码 0<br>2. --type 过滤生效；--json 输出合法 JSON |
| **风险等级** | **MAJOR**（边界查询是检索健壮性；单点失效可绕开） |
| **分级依据** | 标准 §1.2：边界失败不阻断主路径（有 workaround：换 3 字词）→ MAJOR |
| **环境依赖** | 路径 A |

### TC-11：A4 — `memctl index --rebuild` 幂等（真实 repo 前后 lint 0）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-11 |
| **PRD 断言** | A4（§5.1）；架构 §5 构建流程 7 / C7 |
| **路径** | 路径 B（发布门禁基准） |
| **步骤** | 1. `./bin/memctl lint`（before）<br>2. `./bin/memctl index --rebuild`<br>3. `./bin/memctl lint`（after）<br>4. 重复 rebuild 两次，比较 pages/links/term_pages 表行数与 checksum |
| **预期结果** | 1. before/rebuild/after 全部退出码 0（实测 0/0/0）<br>2. 两次 rebuild 后 pages/links 行数一致、lint 均 0 |
| **风险等级** | **BLOCKER**（A4 是 db 派生性 / 防漂移 C7 的核心断言） |
| **分级依据** | 标准 §1.2：重建不幂等 = db 与文件漂移不可恢复，双份拷贝教训重演 → BLOCKER |
| **环境依赖** | 路径 B；**坑位**：rebuild 会 append log.md 事件，幂等比较须排除 log.md / events 表 |
| **注意** | ⚠️ `index --rebuild` 会修改 wiki/log.md（append index_rebuild 事件）→ 测试后 `git checkout wiki/log.md` 恢复，避免污染真实 repo 状态 |

### TC-12：A4 — db 派生性（删 db 重建恢复 + 篡改检出）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-12 |
| **PRD 断言** | A4 / C7；架构 §5 |
| **路径** | 路径 A（临时 db） |
| **步骤** | 1. 构建 db → 记录 checksum<br>2. 删除 mem_meta.db → `memctl index --rebuild` → lint 0（从 wiki 完全恢复）<br>3. 篡改 db（如手工 UPDATE pages SET status='bogus'）→ `memctl lint` |
| **预期结果** | 1. 删库重建后 lint 0（唯一真源 = wiki 文件）<br>2. 篡改检出：lint I4 报 db 与文件不一致（checksum 不匹配） |
| **风险等级** | **BLOCKER**（C7 派生数据防双写漂移） |
| **分级依据** | 标准 §1.2：db 篡改不可检出 = 检索结果不可信（记忆失真），无 workaround → BLOCKER |
| **环境依赖** | 路径 A |

### TC-13：A5 — `memctl done <ID>` 自动写 wiki 页（语义写入主路径）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-13 |
| **PRD 断言** | A5（§5.1）；架构 §4.3 done 六步 / §8.3 镜像格式 |
| **路径** | 路径 A（mock kanban.db 提供 title/result，MEM_KANBAN_DB 指向） |
| **步骤** | 1. mock kanban.db 建任务 t_12345678（title=X, result=Y）<br>2. `memctl done t_12345678 --no-commit`<br>3. 检查 wiki/actions/t_12345678.md |
| **预期结果** | 1. 退出码 0<br>2. 页含：结果节（`## 结果（memctl done 追加）` + 状态 done + 完成时间 + 结果摘要）/ frontmatter status=done / updated 时间戳 bump<br>3. log.md 追加 done 事件；index 刷新（实测确认） |
| **风险等级** | **BLOCKER**（A5 是写入主路径 close.sh S3a 的引擎；PRD P0-7） |
| **分级依据** | 标准 §1.2：done 不写 wiki = 任务完成记忆不落库（P2 决策可追溯断裂），无 workaround → BLOCKER |
| **环境依赖** | 路径 A + mock kanban |
| **注意** | ⚠️ 实测发现：`add task` 骨架缺 `est_hours`（action 必填）→ 新页 lint I4 报错（见 §9 OBS-01）。本用例执行时若 lint 报 I4，记录观测而非判失败，与研发对齐骨架字段策略 |

### TC-14：A5 — `memctl done --check` dry-run 语义（exit 0/1/3）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-14 |
| **PRD 断言** | A5；架构 §8.2 S3a；D1-F3 |
| **路径** | 路径 A |
| **步骤** | 1. 页不存在：`memctl done t_nonexist --check`<br>2. 页存在 status=active：`memctl done t_12345678 --check`<br>3. 页存在 status=done：`memctl done t_12345678 --check`<br>4. **dry-run 断言**：--check 前后 wiki 无任何文件变化（不写） |
| **预期结果** | 1. exit 1（页不存在）<br>2. exit 3（页存在未 done）<br>3. exit 0（已 done）（**实测 1/3/0 全部吻合**）<br>4. git status 无变化 |
| **风险等级** | **BLOCKER**（close.sh S3a 验证步骤依赖 --check 语义；误写 = 铁律 2 破坏） |
| **分级依据** | 标准 §1.2：--check 若实际写文件 = 违反"验证不写"契约（数据完整性）→ BLOCKER |
| **环境依赖** | 路径 A |

### TC-15：A5 — close.sh S3a/S3b 替换生效（活体 + 镜像同验）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-15 |
| **PRD 断言** | A5；架构 §8.1/8.2；D1-F3/F4 |
| **路径** | 路径 B（mock PATH + 真实 close.sh 活体） |
| **步骤** | 1. 前置：mock kanban.db 任务 t_12345678 status=done；GAI 夹具含该任务行；临时 MEM_WIKI_PATH<br>2. 运行真实 close.sh（活体路径，mock 环境变量）<br>3. 检查 wiki 页（结果节 + status=done + updated）<br>4. 检查 GAI 文件：该行行尾追加 `✅ done`（S3b sed，幂等守卫）<br>5. **md5 断言**：`md5sum` 活体与 `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh` 一致（fd22da95） |
| **预期结果** | 1. close.sh 全流程退出 0，S3a/S3b check 均过<br>2. wiki 页已写 + GAI 行尾镜像已追加<br>3. 双份 md5 一致（同改同验，防镜像漂移）<br>4. 断言 `memctl done` 不直接写 GAI（铁律 2：GAI 变化只来自 S3b sed） |
| **风险等级** | **BLOCKER**（写入主路径端到端；PRD R2 三层保险的主路径） |
| **分级依据** | 标准 §1.2：S3 替换失效 = 任务完成记忆不落库 + 状态不一致，无 workaround → BLOCKER |
| **环境依赖** | 真实 close.sh 活体 + mock kanban/GAI + 临时 wiki（**不动真实 repo**） |

### TC-16：A6 — `memctl context --scope project` 输出格式（第五源引擎）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-16 |
| **PRD 断言** | A6（§5.1）；架构 §7.2 |
| **路径** | 路径 B |
| **步骤** | 1. `./bin/memctl context --scope project --max-chars 800`<br>2. 检查输出结构 + 长度 |
| **预期结果** | 1. 退出码 0<br>2. 首行 `### wiki 段（第五源）`<br>3. 三子段：最近更新页（24h 内 ≤5 条）/ 活跃任务关联页（≤3 条）/ 未决决策/待办（status=active ≤3 条）<br>4. 总长度 ≤800 字符（实测输出 3 子段齐全） |
| **风险等级** | **MAJOR**（context 是 boot_context 第五源的引擎；输出格式错位可被 boot_context 兜底截断） |
| **分级依据** | 标准 §1.2：context 格式异常有 workaround（boot_context 防御性截断 + 静默降级）→ MAJOR |
| **环境依赖** | 路径 B |

### TC-17：A6 — boot_context v2 第五源集成（真实脚本输出含 wiki 段）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-17 |
| **PRD 断言** | A6；架构 §7.2 接线表 |
| **路径** | 路径 B（真实 boot_context.py） |
| **步骤** | 1. 运行 `/workspace/devPPL/pipeline/boot_context.py`（或对应入口）<br>2. 检查输出 |
| **预期结果** | 1. 输出包含 `### wiki 段（第五源）`（插在活跃任务段之后）<br>2. 段内 ≤800 字<br>3. 无异常、无 traceback |
| **风险等级** | **BLOCKER**（A6 是第五源注入；任务书明确 boot_context v2 集成是 P0-6） |
| **分级依据** | 标准 §1.2：第五源缺失 = 会话启动读路径断（P4 上下文断点未解），无 workaround → BLOCKER |
| **环境依赖** | devPPL repo + mem-core |

### TC-18：A6 — 静默降级（mem-core 缺失/失败不阻塞 5min 注入）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-18 |
| **PRD 断言** | A6 / C9；架构 §7.2（try-except 静默降级） |
| **路径** | 路径 B（改环境变量模拟缺失）+ 路径 A（memctl 失败模拟） |
| **步骤** | 1. `MEM_WIKI_PATH=/nonexistent` 运行 boot_context.py → 输出无 wiki 段但其他段正常<br>2. 制造 memctl 失败（如 MEM_DB_PATH 指向坏 db）→ boot_context.py 照常完成 |
| **预期结果** | 1. 无 wiki 段、无阻塞、无 traceback、退出码 0（缺失/失败均静默降级）<br>2. 其余四源（pipeline/kanban/sessions/memory）完整输出 |
| **风险等级** | **BLOCKER**（C9 降级优先：mem-core 缺失不得阻塞 5min 注入 = 不破坏现有管线） |
| **分级依据** | 标准 §1.2：boot_context 被 mem-core 拖死 = 现有注入机制整体故障，无 workaround → BLOCKER |
| **环境依赖** | devPPL boot_context.py + 环境变量 mock |

### TC-19：A7 — 备份 manifest 包含 mem-core repo

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-19 |
| **PRD 断言** | A7（§5.1）；架构 §12.2 |
| **路径** | 路径 B |
| **步骤** | 1. 读 /workspace/manifest.yaml<br>2. 检查 backup_roots 含 `/workspace/mem-core/`<br>3. 执行一次备份脚本（如 hermes_backup_push.sh dry-run 或实跑）确认 mem-core 入备份 |
| **预期结果** | 1. manifest 含 mem-core 条目（实测存在）<br>2. 备份产物含 mem-core repo 文件（wiki + 引擎；mem_meta.db 派生数据不备份） |
| **风险等级** | **MINOR**（备份是 BKP-003 既有链路扩展；mem-core 本身有 git 双重保险） |
| **分级依据** | 标准 §1.2：备份缺失有 workaround（git 远程/手动拷贝）→ MINOR |
| **环境依赖** | /workspace/manifest.yaml + 备份链路 |

### TC-20：A8 — 首批 3 页四段非空 + ≥1 参考 + ≥2 出链

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-20 |
| **PRD 断言** | A8（§5.1）；架构 §9.1；D1-F5 |
| **路径** | 路径 B（真实 3 页）+ 人工抽查 |
| **步骤** | 1. 逐页读取 wiki/concepts/decisions/r3-{product,architect,engineer}.md<br>2. 断言：type=decision；四段（背景/要解决的问题/验收标准/参考）非空<br>3. 断言：参考节 ≥1 来源；出链 ≥2（`[[...]]` 计数）<br>4. `memctl lint` 断链检查（I1/I2 已隐式覆盖） |
| **预期结果** | 1. 三页全过四段非空 + ≥1 参考 + ≥2 出链（实测 lint I1/I2 PASS 佐证）<br>2. frontmatter profile 分别为 game-director / game-architect / game-engine |
| **风险等级** | **MAJOR**（A8 是首批内容质量；措辞不达标可 lint 迭代修复） |
| **分级依据** | 标准 §1.2：内容质量不达标有 workaround（LLM 重策展）→ MAJOR（R6 缓解只求非空） |
| **环境依赖** | 路径 B |

### TC-21：A9 — pytest 套件全绿（≥15 用例，含 golden file）+ 软链断言

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-21 |
| **PRD 断言** | A9（§5.1）；架构 §9；D1-F2 软链 |
| **路径** | 路径 B |
| **步骤** | 1. `cd /workspace/mem-core && python3 -m pytest tests/ -q`<br>2. `ls -la bin/mem` 检查 symlink |
| **预期结果** | 1. 退出码 0，≥15 用例全绿（实测 51 pass）<br>2. `bin/mem -> memctl` symlink 存在（两名字同一入口）<br>3. 测试集含 golden file 用例（tests/golden/ 样本被引用） |
| **风险等级** | **BLOCKER**（A9 是引擎正确性的机械证明；MEM-003 测试义务） |
| **分级依据** | 标准 §1.2：pytest 红 = 引擎正确性无证明，不能发布 → BLOCKER |
| **环境依赖** | mem-core repo |

---

## 4. V2 验收测试用例（PRD §5.2 B1-B5）

> ⚠️ V2 四命令当前为 stub（exit 2）。B 组用例在 **V2 交付前标 `[V2-pending]`**，以引擎函数（blast/drift/gai adapter）+ 夹具先行验证逻辑正确性；V2 CLI 接线后补 CLI 层断言。BC-05（demote）同理。

### TC-22：B1 — `memctl update <source> --plan` 候选页清单 + 不读全 wiki

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-22 `[V2-pending]` |
| **PRD 断言** | B1（§5.2）；架构 §6.1/6.2 |
| **路径** | 路径 A（30+ 页夹具 + 读计数器） |
| **步骤** | 1. 构造 30+ 页 wiki + term_pages<br>2. 提供 source 文本（含已存在主题词 + 新主题）<br>3. `memctl update <source> --plan`（V2 CLI 或 blast.compute_candidates 引擎函数）<br>4. 注入文件读取计数器 |
| **预期结果** | 1. 候选页清单含命中理由（term→pages），按命中数降序<br>2. **读取文件数 < 20**（B1 硬约束，只查 db 不读 wiki 文件）<br>3. 新增页建议出现（source 中未命中现有页的主题）<br>4. 全程零 LLM（确定性） |
| **风险等级** | **MAJOR**（blast radius 是 200 文件墙编译侧对策；范围失控有 workaround） |
| **分级依据** | 标准 §1.2：--plan 不读全 wiki 失败 = 增量更新成本失控（性能退化），可人工裁定 → MAJOR |
| **环境依赖** | 路径 A + blast 引擎（已实现：blast.py compute_candidates 实测可调） |

### TC-23：B2 — `memctl gai-links` 对已回填待办零断链

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-23 `[V2-pending]` |
| **PRD 断言** | B2（§5.2）；架构 §4.4 gai-links |
| **路径** | 路径 A（golden GAI 夹具 + 已回填 actions/ 页） |
| **步骤** | 1. 构造 GAI 夹具（含 5 项已回填待办 ID）+ 对应 actions/ 页<br>2. 运行 gai-links（或 GaiAdapter.fetch_events + map_id 引擎函数） |
| **预期结果** | 1. 输出为空（零断链）<br>2. 缺页仅报告不自动建页（交 update --plan 流程）<br>3. **断言对象 = gai-links 适配器输出**（Engineer 注记 2：非全表解析产物） |
| **风险等级** | **MAJOR**（B2 是 GAI 双链完整性；V2 交付后可测） |
| **分级依据** | 标准 §1.2：双链断可人工补链（有 workaround）→ MAJOR |
| **环境依赖** | 路径 A + GaiAdapter |

### TC-24：B3 — 5 项最重要待办回填质量

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-24 `[V2-pending]` |
| **PRD 断言** | B3（§5.2）；架构 §11.2 决策页形态 |
| **路径** | 路径 B（V2 回填后）+ 人工抽查 |
| **步骤** | 1. 检查 5 项已回填待办详情页<br>2. 断言每页四段非空 + ≥1 参考 + ≥2 出链 |
| **预期结果** | 1. 5 页全过质量断言<br>2. `memctl lint` 零断链 |
| **风险等级** | **MAJOR**（回填质量；措辞可 lint 迭代，R6） |
| **分级依据** | 标准 §1.2：质量不达标可 LLM 重策展（有 workaround）→ MAJOR |
| **环境依赖** | V2 P1-3 回填完成 |

### TC-25：B4 — 矛盾检测（contradictions 标记 + review 队列）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-25 `[V2-pending]` |
| **PRD 断言** | B4（§5.2）；架构 §6.3 |
| **路径** | 路径 A（golden/conflict-a.md + conflict-b.md） |
| **步骤** | 1. 注入两条同 topic 冲突源<br>2. 触发 update --apply 或手动模拟矛盾检测<br>3. 检查标记 |
| **预期结果** | 1. 冲突页被打 `contradictions:` 标记（指向对方页）<br>2. 双版本并存（不覆盖）<br>3. drift/review 队列可见带 contradictions 的页 |
| **风险等级** | **MAJOR**（矛盾标记是"矛盾显式标记"编译质量度量；漏标可人工发现） |
| **分级依据** | 标准 §1.2：矛盾检测缺失有 workaround（人工 review）→ MAJOR |
| **环境依赖** | 路径 A + conflict 夹具 |

### TC-26：B5 — 周 drift 三方对账为空（kanban vs wiki vs GAI）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-26 `[V2-pending]` |
| **PRD 断言** | B5（§5.2）；架构 §4.4 drift |
| **路径** | 路径 A（一致状态夹具）+ 路径 B（真实 repo，kanban 活跃任务 vs wiki） |
| **步骤** | 1. 构造一致状态：kanban 活跃任务 ⊆ wiki actions/ 页；GAI ID ⊆ actions/；index == 文件<br>2. 运行 drift（或 drift.three_way_check 引擎函数）<br>3. 制造漂移（单方改 wiki status）→ 再次 drift |
| **预期结果** | 1. 一致状态输出为空（无漂移）<br>2. 制造漂移后输出差异描述（哪方 + 期望/实际）<br>3. **全程只读**（不自动修复，仅报告） |
| **风险等级** | **MAJOR**（兜底层；滞后探测可人工对账） |
| **分级依据** | 标准 §1.2：drift 失效有 workaround（人工对账）→ MAJOR |
| **环境依赖** | 路径 A + drift 引擎（已实现：three_way_check 实测可调） |

### BC-05：V2 — `memctl demote <ID> --reason`（Architect 缺口 1）

| 维度 | 内容 |
|------|------|
| **用例编号** | BC-05 `[V2-pending]` |
| **PRD 断言** | B 组补充（V2 命令面）；架构 §4.4 demote |
| **路径** | 路径 A |
| **步骤** | 1. 构造 actions/P0-19.md（status=active）<br>2. `memctl demote P0-19 --reason "阻塞"`<br>3. 检查 wiki 页 |
| **预期结果** | 1. 页 status 变更 + 变更说明节 + bump updated + log<br>2. 展示层镜像（GAI 状态列 sed 级更新）只由脚本执行，memctl 不写 L0 |
| **风险等级** | **MAJOR**（V2 命令；写 wiki 语义错误有 workaround） |
| **分级依据** | 标准 §1.2：V2 功能缺陷不阻塞 MVP；降级操作可手动改 → MAJOR |
| **环境依赖** | 路径 A |

---

## 5. 北极星长期观测（PRD §5.3 C1-C4）

> 观测协议就绪性在 MVP 交付时验收；首观测点 MVP 后 1 周（2026-08-17）。非自动化断言。

| 用例 | 断言 | 观测方式 | 就绪性验收 |
|------|------|---------|-----------|
| TC-27：C1 | Frank 重复教的次数归零 | Frank 主观记录 / OC 会话日志；基线 ≥1 已知纠正事件 | 纠正事件基线已登记；周检查机制就绪 |
| TC-28：C2 | 决策追溯时长 ≤30s | 计时实测：Frank 问"X 为什么这么做"→ 30s 内给出四段页 | 3 个决策页已预置（r3-三卷）；计时模板就绪 |
| TC-29：C3 | 新会话首轮主动带出正确上下文 | 新会话首轮观察（最近纠正 + 活跃决策 + 当前任务） | boot_context 第五源已集成（实测）；观测模板就绪 |
| TC-30：C4 | 同一纠正跨会话复发次数 = 0 | 跟踪已知纠正事件 | 跟踪表就绪；周检查机制就绪 |

---

## 6. 边界条件测试用例（BE-01 ~ BE-18）

### BE-01：frontmatter 脏数据容错（缺字段/非法枚举/未知字段）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-01 |
| **PRD 断言** | A2（间接）；架构 §3.2 lint 校验规则 |
| **路径** | 路径 A（golden/bad-frontmatter.md） |
| **步骤** | 1. 临时 wiki 复制 bad-frontmatter.md（缺 id / 非法 location / 未知字段）<br>2. `memctl lint` |
| **预期结果** | 1. 不抛异常（解析容错）<br>2. lint 报告逐条列出必填缺失/枚举非法（I4 结构校验）<br>3. 退出码 3（有问题） |
| **风险等级** | **MAJOR**（解析崩溃 = 无法诊断；报错可读则问题可控） |
| **分级依据** | 标准 §1.2：容错缺失崩溃无 workaround；报错可读则降 MAJOR |
| **环境依赖** | 路径 A |

### BE-02：GAI 行级轻量解析（gai-links 适配器输出，非全表解析）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-02 |
| **PRD 断言** | B2（间接）；架构 §4.5 / sources/gai.py；Engineer 注记 2 |
| **路径** | 路径 A（golden/gai-dirty.md） |
| **步骤** | 1. 用 GaiAdapter.fetch_events() 解析 gai-dirty.md<br>2. 断言输出 |
| **预期结果** | 1. 每行输出 Event{external_id, kind, title, status}（ID 单元格识别 + 行动列 + ✅/done 状态）<br>2. 脏行（无 ID / 表头 / 分隔线）跳过<br>3. **断言对象是适配器输出**，不是全表规范化解析产物 |
| **风险等级** | **MAJOR**（适配器输出错位 = B2/B5 断言基座错） |
| **分级依据** | 标准 §1.2：adapter 解析失败有 workaround（人工看 GAI 行）→ MAJOR |
| **环境依赖** | 路径 A + GaiAdapter（已实现） |

### BE-03：wikilink 解析四级规则（ID / 相对路径 / 名称映射 / 别名 + 负样本）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-03 |
| **PRD 断言** | A2/A8（间接）；架构 §3.3 |
| **路径** | 路径 A |
| **步骤** | 1. 构造含 4 种 wikilink 的页：`[[P0-19]]`（ID）、`[[concepts/decisions/r3-product.md]]`（路径）、`[[中间层]]`（名称映射）、`[[目标|显示]]`（别名）<br>2. `memctl lint` + 解析结果检查 |
| **预期结果** | 1. ID 模式 `[A-Z]+-\d{2,3}` → actions/<ID>.md（实测：P0-19 大写规范化）<br>2. 相对路径按 wiki/ 根解析<br>3. 名称映射查 index title→id；多义报歧义<br>4. 别名显示文本正确<br>5. 全部失败 = 断链 I1 |
| **风险等级** | **MAJOR**（解析规则错位 = 断链误判/漏判） |
| **分级依据** | 标准 §1.2：wikilink 解析错位导致 lint 误报，可人工核对 → MAJOR |
| **环境依赖** | 路径 A |

### BE-04：单副本多 profile（frontmatter profile 标签隔离）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-04 |
| **PRD 断言** | C1（§7.3 约束）；架构 §2.1；D1-F5 |
| **路径** | 路径 B（真实 3 页即多 profile 样本） |
| **步骤** | 1. 检查 3 页 profile 值（game-director / game-architect / game-engine）<br>2. 断言同一 repo 内不同 profile 页共存，无 12 profile 副本 |
| **预期结果** | 1. 3 页 profile 各异且共处一个 repo<br>2. 无重复拷贝（LLM-WIKI 单副本） |
| **风险等级** | **MINOR**（单副本是架构约束；违反可合并） |
| **分级依据** | 标准 §1.2：多副本是维护债非功能阻断（有 workaround 合并）→ MINOR |
| **环境依赖** | 路径 B |

### BE-05：location 枚举校验（合法/非法值）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-05 |
| **PRD 断言** | A2（间接）；架构 §3.4 taxonomy |
| **路径** | 路径 A |
| **步骤** | 1. 合法：`location: devppl/memory/architecture` → lint 过<br>2. 非法负样本：`location: Wing-A/Room-1/Shelf-1` → lint I4 报 location 未注册<br>3. `location: devppl`（缺段）→ 格式非法 |
| **预期结果** | 1. 合法值零问题<br>2. 非法值逐段报未注册（wing/room/shelf）<br>3. 缺段报格式非法 |
| **风险等级** | **MAJOR**（标签体系失控 = 记忆宫殿导航失效） |
| **分级依据** | 标准 §1.2：location 校验失效有 workaround（人工查 SCHEMA 枚举）→ MAJOR |
| **环境依赖** | 路径 A |

### BE-06：页面 >200 行 lint 告警（C4）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-06 |
| **PRD 断言** | C4（§7.3）；架构 §3.2 / §10 层 3 |
| **路径** | 路径 A |
| **步骤** | 1. 构造 201 行页<br>2. `memctl lint` |
| **预期结果** | 1. 报告 WARN（超限，非 ERROR）<br>2. 提示拆子页 + 交叉链 |
| **风险等级** | **MINOR**（超限是规模对策；不拆不阻断功能） |
| **分级依据** | 标准 §1.2：页超行数有 workaround（拆页）→ MINOR |
| **环境依赖** | 路径 A |

### BE-07：增量更新幂等（同一事件重复触发同一结果）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-07 `[V2-pending]` |
| **PRD 断言** | B1 / C5（§7.3）；架构 §6.1 |
| **路径** | 路径 A |
| **步骤** | 1. 同一 source 对同一 wiki 触发 update --plan/--apply 两次<br>2. 比较结果 |
| **预期结果** | 1. 两次候选集一致<br>2. 第二次 apply 不产生重复页（骨架已存在则更新不重建）<br>3. lint 两次均 0 |
| **风险等级** | **MAJOR**（幂等失败 = 重复页漂移，可人工删） |
| **分级依据** | 标准 §1.2：重复页有 workaround（手动合并）→ MAJOR |
| **环境依赖** | 路径 A |

### BE-08：冲突内容双版本并存（contradictions 标记）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-08 `[V2-pending]` |
| **PRD 断言** | B4（间接）；架构 §6.3 |
| **路径** | 路径 A（golden/conflict-a/b） |
| **步骤** | 1. 注入冲突双页<br>2. 检查 contradictions 标记 + 双版本 |
| **预期结果** | 1. 双版本并存不覆盖<br>2. 标记指向对方页<br>3. 后续 lint 不因标记断链 |
| **风险等级** | **MAJOR** |
| **分级依据** | 同 TC-25 |
| **环境依赖** | 路径 A |

### BE-09：mem_meta.db 被篡改 → lint 检出（双写漂移防护）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-09 |
| **PRD 断言** | A4 / C7；架构 §5 |
| **路径** | 路径 A |
| **步骤** | 1. 构建 db → 手工 UPDATE pages SET status='bogus'<br>2. `memctl lint` |
| **预期结果** | 1. 检出 db 与文件不一致（checksum 不匹配）<br>2. 退出码 3 |
| **风险等级** | **BLOCKER**（C7 派生数据防漂移核心） |
| **分级依据** | 同 TC-12 |
| **环境依赖** | 路径 A |

### BE-10：🔴 红线 — memctl 不修改 Hermes 本体文件（未确认前本体不被改）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-10（红线用例，任务书要求 4 必须覆盖） |
| **PRD 断言** | §7.2 红线（替代 soul.md / memory.md / hermes.md / SKILL.md 必须 Frank 逐项签字）；架构 §11 |
| **路径** | 路径 B（真实本体文件哈希基线）+ 源码 grep |
| **步骤** | 1. 记录本体文件哈希：`~/.hermes/` SOUL.md（如存在）、profile memory 文件、`/workspace/devPPL/.hermes.md`、任一 SKILL.md（`~/.hermes/profiles/game-qa/skills/` 或 mem-core/SKILL.md）<br>2. 依次执行 `memctl add` / `memctl done` / `memctl index --rebuild` / `memctl query` / `memctl lint`<br>3. 再次哈希对比<br>4. 源码扫描：`grep -rn 'soul.md\|hermes.md\|SKILL.md' memcore/ bin/` |
| **预期结果** | 1. **全部本体文件哈希不变**（memctl 只写 mem-core repo 内）<br>2. 源码无任何对本体文件路径的写操作（只读引用可存在，写操作必须无）<br>3. 若存在替换提案 → 必须有四段式决策页 + 迁移脚本 + 回退方案 + Frank 签字记录（decision 页 status=approved）；**未签字 = 不替换**（架构 §11.2 状态机） |
| **风险等级** | **BLOCKER**（红线 §7.2 是 Frank 硬约束；违反 = 越权修改 Hermes 本体，数据完整性 + 权限边界） |
| **分级依据** | 标准 §1.2：红线违反无 workaround（Frank 未签字 = 不替换，违反即不可接受）→ BLOCKER；另按标准 §2 权限边界独立判定 ≥MAJOR，此处取最高级 |
| **验证命令** | `sha256sum <本体文件>` 前后对比；`grep -rn 'soul.md\|hermes.md\|SKILL.md' /workspace/mem-core/memcore/ /workspace/mem-core/bin/` |
| **环境依赖** | 路径 B（真实本体文件）+ 路径 A（源码静态扫描） |

### BE-11：boot_context wiki 段超 800 字截断

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-11 |
| **PRD 断言** | A6（字符预算）；架构 §7.2 |
| **路径** | 路径 A |
| **步骤** | 1. 构造 20+ 更新页（大量未决决策）<br>2. `memctl context --scope project --max-chars 800`<br>3. 测量长度 |
| **预期结果** | 1. 输出 ≤800 字符<br>2. 截断不破坏 markdown 结构（无半个代码块/表格）<br>3. boot_context 层防御性截断兜底 |
| **风险等级** | **MINOR**（字符预算溢出是体验退化，有 workaround） |
| **分级依据** | 标准 §1.2：超预算可减少更新量（有 workaround）→ MINOR |
| **环境依赖** | 路径 A |

### BE-12：会话启动协议文件读取 10-20 个

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-12 |
| **PRD 断言** | P2-2（§4）；架构 §7.1 |
| **路径** | 路径 A（30+ 页夹具 + 读计数器） |
| **步骤** | 1. 模拟新会话启动协议（SCHEMA → index → log 最近 20-30 条 → 定向读相关页）<br>2. 注入文件读取计数器<br>3. 统计 |
| **预期结果** | 1. 读取文件数 10-20 个<br>2. 全确定性路径（零 LLM 检索调用）<br>3. 输出摘要含最近活动 + 活跃任务关联页 |
| **风险等级** | **MAJOR**（读路径性能；上下文膨胀可人工定向读） |
| **分级依据** | 标准 §1.2：读取数失控 = 上下文膨胀（性能退化），有 workaround → MAJOR |
| **环境依赖** | 路径 A |

### BE-13：sqlite 降级路径（MEM_FORCE_QUERY_FALLBACK）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-13 |
| **PRD 断言** | A3（降级）；架构 §4.3 / query.py 降级钩子 |
| **路径** | 路径 A |
| **步骤** | 1. 环境预检：sqlite 版本 ≥3.34 且有 trigram（实测 3.45.1 可用）<br>2. `MEM_FORCE_QUERY_FALLBACK=1 memctl query "中间层"`（强制 LIKE 路径）<br>3. 比较命中 |
| **预期结果** | 1. 强制降级不崩溃、可命中（精度下降可接受）<br>2. 正常路径 trigram 命中优先 |
| **风险等级** | **MAJOR**（低版本 sqlite 环境完全不可检索 = 功能阻断；本机正常但有 workaround 升级） |
| **分级依据** | 标准 §1.2：降级缺失仅影响低版本环境（有 workaround 升级 sqlite）→ MAJOR |
| **环境依赖** | 路径 A |

### BE-14：空 wiki / 缺 SCHEMA / 不存在路径容错

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-14 |
| **PRD 断言** | A2/A6（间接）；架构 §12.1 |
| **路径** | 路径 A |
| **步骤** | 1. 场景 A：空 wiki → `memctl index` / `memctl lint`<br>2. 场景 B：删 SCHEMA.md → `memctl lint`<br>3. 场景 C：`memctl query` 指向不存在路径（MEM_WIKI_PATH=/nonexistent） |
| **预期结果** | 1. 空 wiki：index 建空表；lint 报缺首页等可读错误，不崩溃<br>2. 缺 SCHEMA：lint 明确报错<br>3. 不存在路径：报错 + 非 0 退出码，无 traceback |
| **风险等级** | **MAJOR**（配置错误可读性；崩溃 = 无从诊断） |
| **分级依据** | 标准 §1.2：缺 SCHEMA 是配置错误；崩溃无诊断（有 workaround 恢复文件）→ MAJOR |
| **环境依赖** | 路径 A |

### BE-15：归档移出活跃索引（_archive/）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-15 |
| **PRD 断言** | P3-1（§4）；架构 §10 层 4 |
| **路径** | 路径 A |
| **步骤** | 1. 构造 done 页 → 移入 `_archive/`<br>2. `memctl index --rebuild` → `memctl lint`<br>3. `memctl query <归档页词>` |
| **预期结果** | 1. 归档页不进活跃索引（index 不再列出）<br>2. lint 0（归档区不触发活跃区不变式）<br>3. 归档页仍可被显式路径访问 |
| **风险等级** | **MINOR**（归档是规模对策 >50 页才触发） |
| **分级依据** | 标准 §1.2：不归档不阻断当前功能 → MINOR |
| **环境依赖** | 路径 A |

### BE-16：退出码约定全表验证（0/1/2/3）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-16 |
| **PRD 断言** | A2-A9（间接）；架构 §4.2；D1-F2 |
| **路径** | 路径 A |
| **步骤** | 1. 成功命令（query 有命中 / lint 0 / status / context）→ exit 0<br>2. 一般错误（query 无 db / add 非法 ID / done 页不存在 --check）→ exit 1<br>3. 用法错误（未知命令 / query 无 terms / context task 无 --id / V2 stub）→ exit 2<br>4. 校验失败（lint 有问题 / done --check 未 done）→ exit 3 |
| **预期结果** | 全部与架构 §4.2 表吻合（实测：lint 0→0 / lint 问题→3 / done --check 未 done→3 / 页不存在→1 / V2 stub→2） |
| **风险等级** | **MAJOR**（退出码是脚本消费契约；close.sh/boot_context 依赖非 0 判定） |
| **分级依据** | 标准 §1.2：退出码错位导致上层脚本误判（有 workaround 人工看输出）→ MAJOR |
| **环境依赖** | 路径 A |

### BE-17：`memctl done` fail-open（L0 只读失败仍写 wiki，close 不挂死）（Architect 缺口 3）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-17 |
| **PRD 断言** | A5 / R10；架构 §4.3 fail-open / §8.2 |
| **路径** | 路径 A（mock kanban 失败模拟） |
| **步骤** | 1. 构造 actions/P0-19.md（source_task=t_2345b07e）<br>2. 令 MEM_KANBAN_DB 指向不存在/损坏的 db<br>3. `memctl done P0-19 --result "R" --no-commit`<br>4. 检查 |
| **预期结果** | 1. 退出码 0（wiki 写入完成）<br>2. 页含结果节 + status=done + updated bump（以 ID 为锚）<br>3. stderr 有 warning：L0 只读失败（fail-open 提示）<br>4. close.sh 不因 L0 失败挂死（R10） |
| **风险等级** | **BLOCKER**（fail-open 是 close 流程不挂死的工程承诺；挂死 = 任务无法关闭） |
| **分级依据** | 标准 §1.2：done 因 L0 失败挂死 = 关闭流程阻塞，无 workaround → BLOCKER |
| **环境依赖** | 路径 A + mock kanban 失败 |

### BE-18：`memctl add task` 骨架 lint 状态（OBS-01 观测用例）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-18（观测确认用例，见 §9 OBS-01） |
| **PRD 断言** | A2 / A5（骨架与 lint 门禁的关系）；架构 §4.3 add task 契约 |
| **路径** | 路径 A |
| **步骤** | 1. `memctl add task t_12345678 --title X --priority P1`<br>2. `memctl lint` |
| **预期结果** | 观测记录：当前实测 add task 骨架缺 est_hours（action 必填）→ lint I4 报错；出链 0 → I2 报错。**本用例的目的不是判失败，而是确认骨架与 lint 门禁的关系**——若研发确认骨架为中间态（留待 LLM 策展补全），需明确 lint 对骨架页的豁免/暂缓策略；否则补 est_hours 预填 |
| **风险等级** | **MAJOR**（候选；待研发评估后定级，见 §9 OBS-01） |
| **分级依据** | 标准 §1.2：骨架页 lint 必失败 = 新增任务后仓库 lint 门禁恒红（A2 与 A5 冲突面）；当前有 workaround（LLM 策展补全）→ 候选 MAJOR，论证流程见 §9 |
| **环境依赖** | 路径 A |

---

## 7. 端到端场景测试用例（TS-01 ~ TS-07）

### TS-01：写→存→读全链路（纠正闭环价值链）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-01 |
| **PRD 断言** | A2/A3/A4/A5/A8（MVP 全链路）；架构 §1.2 数据流 |
| **路径** | 路径 A（临时 repo）+ 路径 B 冒烟 |
| **步骤** | 1. `memctl add task t_12345678`（或 raw）<br>2. `memctl index --rebuild`<br>3. `memctl query <3字词>`（命中新页）<br>4. `memctl lint`（0 问题）<br>5. 检查 git 提交（原子提交、信息含 ID）<br>6. `memctl done t_12345678` → 再次 lint |
| **预期结果** | 1. 各命令退出码符合 §4.2<br>2. 新页可检索（trigram 命中）<br>3. git log 有原子提交记录（commit message `mem(<ID>): ...`）<br>4. done 后页含结果节 + status=done |
| **风险等级** | **BLOCKER**（MVP 价值闭环：写→存→读；任一环节断裂 = P1/P4 痛点未解决） |
| **分级依据** | 标准 §1.2：价值闭环断裂无 workaround → BLOCKER |
| **环境依赖** | 路径 A/B |

### TS-02：纠正闭环（纠正事件 → 落 wiki → boot_context 带出）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-02 |
| **PRD 断言** | A6 + C1（价值链场景）；架构 §7.2 |
| **路径** | 路径 A（mock mem context）+ 真实 boot_context.py |
| **步骤** | 1. 模拟纠正事件（如"梦境报告投递方式改为 X"）→ `memctl add`<br>2. 运行 boot_context.py<br>3. 检查输出含该纠正摘要<br>4. 模拟新会话首轮 |
| **预期结果** | 1. 纠正内容落 wiki 页<br>2. boot_context wiki 段含该纠正<br>3. 新会话首轮可带出（观测协议就绪） |
| **风险等级** | **MAJOR**（价值链机械部分；boot_context 带出失败有 workaround 手动 query） |
| **分级依据** | 标准 §1.2：带出失败有 workaround → MAJOR |
| **环境依赖** | 路径 B + mock |

### TS-03：close.sh 全闭环（kanban done → mem done → wiki + 镜像 + drift）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-03 |
| **PRD 断言** | A5 + B5；架构 §8 |
| **路径** | 路径 B（mock kanban/GAI + 真实 close.sh 活体 + 临时 wiki） |
| **步骤** | 1. mock kanban 任务 done；GAI 夹具含该任务行<br>2. 运行真实 close.sh<br>3. 检查 wiki 页（结果节 + status=done + updated）<br>4. 检查 GAI 行尾 ✅ done（S3b sed 幂等）<br>5. `memctl drift`（三方一致） |
| **预期结果** | 1. close.sh 退出 0<br>2. wiki 页生成 + GAI 镜像追加<br>3. drift 三方对账一致（空输出）<br>4. 双份 close.sh md5 一致 |
| **风险等级** | **BLOCKER**（写入主路径端到端；数据一致性） |
| **分级依据** | 同 TC-15 |
| **环境依赖** | mock kanban + GAI 夹具 + close.sh 活体 |

### TS-04：增量更新场景（新源 → --plan → 裁定 → --apply → lint 0）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-04 `[V2-pending]` |
| **PRD 断言** | B1；架构 §6 |
| **路径** | 路径 A（30+ 页） |
| **步骤** | 1. `memctl update <source> --plan` → 人工裁定候选集（mock 接受全部）<br>2. `memctl update <source> --apply <pages...>`<br>3. `memctl lint`<br>4. 检查 updated bump + log 追加 |
| **预期结果** | 1. plan 只读、候选集合理（命中理由可解释）<br>2. apply 只改候选页（git diff 只含候选集）<br>3. lint 0<br>4. log.md 追加事件 |
| **风险等级** | **MAJOR**（增量更新是 200 文件墙编译侧对策；apply 范围失控可人工回滚） |
| **分级依据** | 标准 §1.2：范围失控有 workaround（git 回滚）→ MAJOR |
| **环境依赖** | 路径 A |

### TS-05：跨会话恢复场景（协议 5 步 → 上下文摘要）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-05 |
| **PRD 断言** | P2-2（§4）；架构 §7.1 |
| **路径** | 路径 A（30+ 页，含最近更新 + 活跃任务关联页） |
| **步骤** | 1. 模拟新会话启动<br>2. 执行启动协议（SCHEMA → index → log → 定向读页）<br>3. 合成上下文摘要<br>4. 检查摘要质量 |
| **预期结果** | 1. 摘要含最近活动 + 活跃决策 + 当前任务<br>2. 读取文件数 10-20<br>3. 零 LLM 检索调用 |
| **风险等级** | **MAJOR**（跨会话恢复是 P4 解决方案；恢复质量差有 workaround） |
| **分级依据** | 标准 §1.2：恢复质量差有 workaround（Frank 重复解释）→ MAJOR |
| **环境依赖** | 路径 A |

### TS-06：备份恢复场景（备份 → clone → index --rebuild → lint 0）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-06 |
| **PRD 断言** | A7；架构 §12.2 |
| **路径** | 路径 B（真实 repo clone 到临时目录）+ mock manifest |
| **步骤** | 1. 执行备份<br>2. 确认 manifest 含 mem-core<br>3. 模拟恢复：`git clone` 备份副本到临时目录<br>4. 临时目录内 `memctl index --rebuild` + `memctl lint` |
| **预期结果** | 1. manifest 含 mem-core<br>2. clone 后可重建 db，lint 0（备份完整可恢复；mem_meta.db 派生不备份） |
| **风险等级** | **MINOR**（备份是 BKP-003 既有链路；mem-core 有 git 双重保险） |
| **分级依据** | 标准 §1.2：备份缺失有 workaround → MINOR |
| **环境依赖** | mock manifest + 临时 repo |

### TS-07：周 drift 兜底（制造漂移 → mem drift 检出 → 修复 → 空）

| 维度 | 内容 |
|------|------|
| **用例编号** | TS-07 `[V2-pending]` |
| **PRD 断言** | B5；架构 §4.4 |
| **路径** | 路径 A（mock kanban + GAI 夹具） |
| **步骤** | 1. 一致状态三方<br>2. 人为制造漂移（单方改 wiki status 不回写 kanban）<br>3. `memctl drift`<br>4. 检查检出 → 修复 → 再次 drift |
| **预期结果** | 1. drift 检出漂移源（哪方 + 期望/实际）<br>2. 修复后空输出<br>3. 全程只读（不自动修复） |
| **风险等级** | **MAJOR**（兜底层失效 = 漂移滞后探测失败，可人工对账） |
| **分级依据** | 标准 §1.2：漂移滞后有 workaround（人工对账）→ MAJOR |
| **环境依赖** | 路径 A + drift 引擎 |

---

## 8. 覆盖矩阵（任务书要求 5：用例数 + 覆盖矩阵 + 估算执行时间）

### 8.1 PRD §5 断言 × 用例覆盖

| PRD §5 断言 | 直接用例 | 间接覆盖 | 覆盖状态 |
|------------|---------|---------|:---:|
| A1 GAI 副本已删 + 可追溯 | TC-01 | — | ✅ |
| A2 lint 零问题（四不变式） | TC-02~07 | BE-01/03/05/06/09/14/16/18 | ✅ |
| A3 trigram / bigram / 边界 | TC-08~10 | BE-13 降级 | ✅ |
| A4 index --rebuild 幂等 + db 派生 | TC-11~12 | BE-09 篡改 | ✅ |
| A5 close.sh → wiki 页 | TC-13~15 | BE-17 fail-open、BE-18 骨架 | ✅ |
| A6 boot_context 第五源 + 静默降级 | TC-16~18 | BE-11 截断 | ✅ |
| A7 备份 manifest 含 mem-core | TC-19 | TS-06 | ✅ |
| A8 首批 3 页质量 | TC-20 | BE-03/04 | ✅ |
| A9 pytest ≥15 用例全绿 | TC-21 | — | ✅ |
| B1 update --plan + <20 文件 | TC-22 `[V2]` | BE-07 幂等、TS-04 | ✅（引擎层可先行） |
| B2 gai-links 零断链 | TC-23 `[V2]` | BE-02 adapter | ✅（引擎层可先行） |
| B3 5 项待办回填质量 | TC-24 `[V2]` | — | ✅（V2 交付后） |
| B4 矛盾检测 + review 队列 | TC-25 `[V2]` | BE-08 | ✅（引擎层可先行） |
| B5 drift 三方对账为空 | TC-26 `[V2]` | TS-03/07 | ✅（引擎层可先行） |
| C1-C4 北极星观测 | TC-27~30 | TS-02 | ✅ 观测协议就绪 |

### 8.2 任务书 5 项契约基线覆盖

| 契约项 | 覆盖用例 |
|--------|---------|
| 验收编号锁 PRD §5.1（D1-F1） | 全部用例标注；§0 差异表 |
| CLI 12 命令面 + 软链 + 退出码（D1-F2） | TC-21（软链）、BE-16（退出码）、§1.1 全命令实测 |
| memctl done 只写 wiki + --check（D1-F3） | TC-13/14、BE-17 |
| close.sh S3a/S3b + 双份 md5（D1-F4） | TC-15、TS-03 |
| 首批 3 页 = R3 三卷（D1-F5） | TC-20、BE-04 |
| 🔴 红线：本体未确认不被改（PRD §7.2 / 架构 §11） | **BE-10**（哈希 + 源码扫描 + 签字状态机） |
| 双路径（mock wiki + 真实 repo） | 全部用例标注路径；§2.1 |
| mem_meta.db 派生 + 幂等（C7） | TC-11/12、BE-09 |
| 单副本多 profile（C1） | BE-04 |

### 8.3 用例统计

| 分类 | 数量 | BLOCKER | MAJOR | MINOR | 观测项 | V2-pending |
|------|:---:|:---:|:---:|:---:|:---:|:---:|
| MVP 验收（A1-A9，TC-01~21） | 21 | 14 | 6 | 1 | 0 | 0 |
| V2 验收（B1-B5 + demote，TC-22~26 + BC-05） | 6 | 0 | 6 | 0 | 0 | 6 |
| 北极星观测（C1-C4，TC-27~30） | 4 | 0 | 0 | 0 | 4 | 0 |
| 边界条件（BE-01~18） | 18 | 4 | 10 | 4 | 0 | 2 |
| 端到端场景（TS-01~07） | 7 | 2 | 3 | 2 | 0 | 2 |
| **合计** | **56** | **20** | **25** | **7** | **4** | **10** |

> 对比 v1：49 → 56 用例（+7）。净增：TC-06（status 断言）、BC-05（demote）、BE-17（done fail-open）、BE-18（骨架 lint 观测）、BE-16（退出码全表）、TC-14 拆出（done --check 语义）、红线 BE-10 强化（哈希 + 源码扫描 + 签字状态机）。V2-pending 10 例在 V2 交付后转为可执行；MVP 门禁（A1-A9）21 例全部当前可执行。

### 8.4 预估执行时间

| Round | 内容 | 用例 | 时间 |
|-------|------|------|:---:|
| Round 0 | 环境预检 + 契约基线复核（sqlite trigram / 双份 md5 / A1-A9 前置状态） | — | 1.0h |
| Round 1 | 确定性引擎单元层（路径 A：parse/indexer/lint 全量） | TC-02~07, BE-01/03/05/06/09/14/16/18 | 2.5h |
| Round 2 | 检索与 CLI（路径 A：query/退出码/context/降级） | TC-08~10, BE-11/13/16, TS-01 | 1.5h |
| Round 3 | 集成层（close.sh / boot_context / manifest / 红线） | TC-01/15/17/18/19, BE-10, TS-02/03 | 2.0h |
| Round 4 | 端到端 + 真实 repo 回归 | TC-11/13/14/16/20/21, BE-04/17, TS-05/06 | 2.0h |
| Round 5 | 内容验收 + 全量回归（快照对比 v1 断言口径） | TC-20, A1-A9 全量 | 1.5h |
| Round 6 | 北极星观测协议初始化（MVP 交付后立即） | TC-27~30 | 1.0h |
| V2 轮 | V2 命令接线后补跑 B 组 + V2-pending | TC-22~26, BC-05, BE-07/08, TS-04/07 | 3.0h（V2 阶段） |
| **MVP 小计** | | **46 用例（A1-A9 + BE + TS 非 V2）** | **≈ 11.5h** |
| **V2 增量** | | **10 用例** | **≈ 3.0h** |

> BE-15（归档 _archive/）属 P3-1 对策（wiki >50 页触发），不依赖 V2 命令面，wiki 规模达标后单独执行。

---

## 9. QA 预执行观测（smoke 实测发现，待研发评估）

> 以下为编写本方案时对真实 mem-core（commit 27673b9）冒烟实测发现的问题。按标准 §6 论证流程提交：发现 → 研发评估 → 通过/驳回/暂缓。本方案已为之设计观测用例（BE-18），执行时正式记录。

### OBS-01：`memctl add task` 骨架缺 est_hours（action 必填）→ lint I4 恒失败（候选 MAJOR）

- **复现**：`memctl add task t_12345678 --title X --priority P1` 后 `memctl lint` → `[I4:ERROR] actions/t_12345678.md: action 缺必填 frontmatter 字段: est_hours`（实测）；同时出链 0 → `[I2:ERROR] 出链不足: 0 < 2`
- **预期 vs 实际**：架构 §4.3 add task 契约"frontmatter 机械预填：id/source_task/status=active/created"，未列 est_hours；但 SCHEMA §3.2 规定 action 必填 est_hours → 骨架页生成即 lint 红，与 PRD P0-4"mem lint 零问题为一切提交前置"冲突
- **影响面**：A2（lint 门禁）与 A5（done 写页）之间出现"新建任务 → lint 恒红"的死区；close.sh S3a 用 `done --check`（只查 status=done）不受影响，但全库 lint 门禁会因任一未策展任务而失败
- **候选定级**：**MAJOR**（用户可感知：新增任务后 lint 门禁恒红；功能阻断：A2 断言无法全绿；workaround：LLM 策展补 est_hours + 出链 → 非 BLOCKER）
- **处置建议**：二选一——(a) add task 预填 `est_hours: 0`（或默认值）+ 骨架页预填出链（如 source_task 关联页）；(b) lint 对 status=active 的骨架页豁免 I4-est_hours / I2-出链不足（标注中间态），直到 LLM 策展。需研发评估 + 产品裁定

### OBS-02：`memctl index --rebuild` 会 append log.md 事件（副作用可观测）

- **复现**：真实 repo `index --rebuild` 后 `git status` 显示 `M wiki/log.md`（append index_rebuild 事件）
- **影响面**：A4 幂等断言必须排除 log.md/events 表（TC-11 已标注坑位）；测试后需恢复 log.md
- **定级**：非缺陷（log append 是机械维护设计的一部分），仅测试坑位提醒

### OBS-03：环境变量残留污染（MEM_WIKI_PATH 跨命令残留）

- **复现**：smoke 测试 export MEM_WIKI_PATH 后，后续 lint/index 打到错误路径（实测误报 3）
- **影响面**：路径 B 用例必须显式 `unset MEM_WIKI_PATH` 或以 `MEM_WIKI_PATH=/workspace/mem-core` 显式指定，否则断言打到夹具（§2 环境表已列入）
- **定级**：测试基建提醒，非产品缺陷

---

## 10. 测试执行顺序与依赖

```
Round 0: 环境预检 + 契约基线（无外部依赖）
  ├── sqlite trigram 探测（3.45.1 已实测）
  ├── close.sh 双份 md5（fd22da95 已实测）
  ├── A1-A9 前置状态快照（git ls-files / manifest / boot_context 已实测）
  └── 路径 A 夹具评审（golden/ 6 样本已存在）

Round 1: 确定性引擎单元层（路径 A，mock wiki + 真实 db 产物）
  ├── TC-02~07: lint 四不变式 + status
  ├── TC-11/12: index 幂等 + db 派生性
  ├── BE-01/03/05/06/09/14/16/18: 脏数据/链接/location/超长/篡改/容错/退出码/骨架
  └── OBS-01 正式记录（BE-18）

Round 2: 检索与 CLI（路径 A）
  ├── TC-08~10: trigram / bigram / 边界
  ├── BE-11/13: 800 字截断 / 降级路径
  └── TS-01: 写→存→读全链路（临时 repo）

Round 3: 集成层（路径 B + mock 外部依赖）
  ├── TC-01: A1 GAI 副本删除
  ├── TC-15/17/18/19: close.sh / boot_context / 降级 / manifest
  ├── BE-10: 🔴 红线（哈希 + 源码扫描 + 签字状态机）
  └── TS-02/03: 纠正闭环 / close.sh 全闭环

Round 4: 端到端 + 真实 repo 回归（路径 B）
  ├── TC-11/13/14/16/20/21: 幂等 / done / --check / context / 3 页 / pytest
  ├── BE-04/17: 单副本 / fail-open
  ├── TS-05: 跨会话恢复协议
  └── TS-06: 备份恢复

Round 5: 内容验收 + 全量回归
  ├── TC-20: A8 3 页质量
  └── A1-A9 全量快照对比（对照 §8.1 矩阵）

Round 6: 北极星观测协议初始化（MVP 交付后立即）
  ├── TC-27: 纠正事件基线登记
  ├── TC-28: 3 决策页计时模板
  ├── TC-29/30: 观测模板 + 周检查机制
  └── 首观测：MVP 后 1 周（2026-08-17）

V2 轮（V2 命令接线后）：TC-22~26 + BC-05 + BE-07/08/15 + TS-04/07
```

---

## 11. 分级依据对照（标准 §1.2 / §8 / §10 落实说明）

| 标准条款 | 本方案落实 |
|---------|-----------|
| §1.2 判定公式 | 每个用例"风险等级" = 该断言失败时的真实缺陷级别，按公式（用户可感知 AND 功能阻断 AND 无 workaround → BLOCKER）逐条附"分级依据"；无法判断取高级别 + triage_needed |
| §2 安全漏洞独立判定 | 本系统为本地记忆库（C 级内部数据），无 OWASP 暴露面；BE-10 红线按权限边界/数据完整性独立判定（≥MAJOR，取 BLOCKER） |
| §3 性能退化 | TC-22（读文件数<20）、BE-12（10-20 文件）为编译期/读路径性能断言；不满足按 MAJOR |
| §5 分级示例 | OBS-01 候选 MAJOR 的判定过程显式写出（可感知/阻断/workaround 三要素），供研发对表 |
| §8 SLA | OBS-01~03 已按发现流程提交：响应 4h / 定位 8h / 方案 24h 从 kanban_comment 时间起算；BLOCKER 暂缓必须 Frank 签字（§11） |
| §9 QA SLA | 执行中发现缺陷后 1h 内提交（复现步骤 + 环境 + 预期 vs 实际 + 复现率）；BLOCKER 回归 4h 内 / MAJOR 1 工作日 |
| §10 发布门禁 | MVP 门禁 = A1-A9 全绿 + BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉；OBS-01 若维持 MAJOR 计入 MAJOR≤3 预算 |
| §11 产品红线 | BE-10 是红线守护用例：本体文件未 Frank 签字 = 不替换；哈希对比 + 源码扫描 + 签字状态机三重复核 |

---

## 12. 一句话结论

v2 测试方案基于**架构定稿后的真实接口**（mem-core commit 27673b9 实测：12 命令面 + 退出码 0/1/2/3 + done --check 1/3/0 + close.sh S3a/S3b 双份 md5 + boot_context 第五源 + 首批 3 页）重出 **56 用例**（MVP 门禁 A1-A9 21 例当前全可执行；V2 10 例标 `[V2-pending]` 引擎层可先行；北极星 4 观测项协议就绪），双路径（mock wiki 夹具 + 真实 mem-core repo），**红线 BE-10 覆盖"本体文件未确认前不被改"**；预执行发现 OBS-01（add task 骨架缺 est_hours → lint I4 恒红，候选 MAJOR）待研发评估；MVP 执行约 **11.5h**，V2 增量约 3h。MVP 门禁 = A1-A9 全绿 + BLOCKER=0 AND MAJOR≤3。
