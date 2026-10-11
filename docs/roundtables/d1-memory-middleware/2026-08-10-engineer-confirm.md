# D1 确认卷 — Memory Middleware QA 5 项契约问题（Engineer 可行性确认）

> 发言人：寇豆码（工程师） | 日期：2026-08-10 | 版本：v1.0
> 类型：D1 前置契约问题 Engineer 确认（QA 方案 docs/qa/memory-middleware-test-plan.md 的 D1 发现，逐项从实现可行性角度确认）
> 输入：QA 方案（49 用例）+ PRD v1.0（权威）+ 架构设计 v1.0（docs/arch-memory-middleware.md）+ 我 R3 独立卷（docs/roundtables/r3-memory-middleware/2026-08-10-engineer.md）
> 实测复核：close.sh 两路径 md5、GAI 新格式、sqlite 版本、mem-core 存在性（见 §3）

---

## 0. 结论速览

| # | 问题 | 级别 | 立场 | 一句话落地 |
|---|------|:---:|------|-----------|
| D1-F1 | 验收编号不对应 | BLOCKER | 维持 QA 裁定 | VA 一律以 PRD §5 编号为权威，任务卡编号作废，代码零影响 |
| D1-F2 | memctl CLI 命令面不一致 | BLOCKER | 维持架构 §4 定稿 | 12 命令定稿面（MVP 7），`mem` 为 `memctl` 软链，退出码 0/1/2/3 |
| D1-F3 | `mem done` 与铁律 2 冲突 | BLOCKER | **修正我 R3 §5.2** | `memctl done` 只写 wiki；GAI 标记归 close.sh S3b 展示镜像（sed 模式需改） |
| D1-F4 | close.sh 挂点位置 | MAJOR | 维持替换方案，修正挂点定位 | 活体 = orchestrator profile 脚本，backup-repo 是同 md5 镜像，两处同改同验 |
| D1-F5 | 首批 3 页内容对象 | MAJOR | 维持 QA 建议 | 3 页 = R3 三卷各一页（= arch §9.1 golden 夹具），type=decision 四段式 |

---

## 1. 逐项确认

### D1-F1 验收编号不对应 — 立场：维持 QA 裁定（PRD §5 权威）

落地：VA 阶段验收清单一律按 PRD §5.1 A1-A9 / §5.2 B1-B5 / §5.3 C1-C4 执行，任务卡 body 里的 A1-A9 编号作废；架构 §14 里程碑映射（P0-* → A1-A9）即验收对照表，dev 交付时按该表自检。一句话理由：任务卡编号是 Step-2 早期产物，与 PRD 冲突时以 PRD（Frank 裁定载体）为准，且编号错位零代码影响、纯 VA 口径对齐。

### D1-F2 memctl CLI 命令面不一致 — 立场：维持架构 §4 定稿面

落地：最终命令面 = **12 命令**——MVP 7 条：`add / done / query / lint / index / status / context`；V2 4 条：`update / drift / gai-links / demote`；V3 占位 1 条：`mcp-serve`。正式二进制 `bin/memctl`，`bin/mem` 为软链（PRD/R3/QA 文档历史引用 mem，两名字同一入口）。退出码 0=成功 / 1=一般错误 / 2=用法错误 / 3=校验失败（lint 有问题、drift 有差异、query 语法错）。QA 计划中 `bin/mem` 引用统一为 `bin/memctl`（或加一条软链存在断言）。一句话理由：架构已把 PRD §4（5 命令 MVP 骨架）/ §10（10 命令交接）/ R3（7 命令）三份清单合并裁决，`index`（A4 幂等重建）、`done`（A5）、`context`（A6）都在 MVP，`gai-links`/`drift`（B2/B5）在 V2，与 PRD 阶段划分完全一致，实现上 argparse 分发无任何技术障碍。

### D1-F3 `mem done` 与铁律 2 冲突 — 立场：修正我 R3 §5.2 的表述

落地：**`memctl done` 绝不写 GAI**——只写 wiki（结果节 + status=done + bump updated + index/log/db 增量 + 原子 git 提交，架构 §4.3 六步）；GAI 的 `✅ done` 标记由 close.sh **S3b 的 sed** 负责（close.sh 是 orchestrator profile 自己的脚本写自己的文件，不属于中间层写路径）。注意：S3b 沿用旧 sed 模式 `s/\($TASK_ID.*\)待办/.../` 对 2026-08-10 新格式是 no-op（实测行内无"待办"、行尾无状态列），必须改为行尾追加标记：`sed -i "/$TASK_ID/s/$/ ✅ done/"`。一句话理由：铁律 2 的边界是"中间层对 L0 只读不写"，close.sh 的展示镜像不是中间层写路径——S3a（memctl done 写 wiki）/S3b（sed 写 GAI 展示）分离后，A5 断言 wiki 页、B5 断言三方对账各自可测且不碰铁律。

### D1-F4 close.sh 挂点位置 — 立场：维持替换方案，修正挂点定位

落地：活体脚本 = **/root/.hermes/profiles/orchestrator/scripts/close.sh**（104 行，S3 在 70-73 行，Hermes 实际执行路径）；/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh 是 hermes_backup_push.sh 同步的 git 镜像（实测两文件 md5 相同 64eb0c69…，backup-repo 是 git repo）。修改发布路径 = 改活体文件 → 备份推送进 backup-repo（提交在 backup-repo 可追溯）；devPPL 与 mem-core **都不含** close.sh，无需也不应在两仓提交。QA 夹具指向活体路径，并加一条备份镜像 md5 断言。一句话理由：挂点不在任何中间层 repo，而是 orchestrator profile 脚本 + backup-repo 镜像两个物理副本，必须同改同验，否则活体改了镜像没改（或反之）就是新的双份拷贝漂移。

### D1-F5 首批 3 页内容对象 — 立场：维持 QA 建议（R3 三卷各一页）

落地：3 页 = R3 三卷各编译一页，即架构 §9.1 已定的 golden 夹具 `golden/r3-architect.md` / `golden/r3-engineer.md` / `golden/r3-product.md`，type=decision，四段式（背景/问题/验收/参考）+ ≥1 参考 + ≥2 出链，frontmatter `profile:` 分别标 game-architect / game-dev / game-qa（顺带喂 BE-04 单副本多 profile 用例）。同一批回填同时服务 A8 抽查与 golden 测试，P0-10 的 1.5h 预算不变。一句话理由：三卷天然覆盖四段式 + 双链 + 单副本多 profile 三个验收面，且与架构 golden 夹具设计重合，不需要另定对象。

---

## 2. QA 方案 49 用例在 mem-core 上的可执行性确认

### 2.1 结论：45 个可执行用例 + 4 个观测项，全部可在 mem-core 上落地

| 组 | 数量 | 路径 | 可执行性 |
|----|:---:|------|---------|
| MVP 验收 A1-A9（TC-01~18） | 18 | TC-02~11 路径 A；TC-01/12/13/14/15/16/17/18 路径 B | ✅ 路径 A 先行（TC-02~11 无外部依赖，临时目录 + 真实 SQLite）；路径 B 需 dev 交付 + close.sh 活体 + boot_context v2 |
| V2 验收 B1-B5（TC-19~23） | 5 | 路径 A（mock GAI/manifest/kanban） | ✅ TC-19/20/22/23 在 mem-core 上以夹具可跑；TC-21 需 P1-3 回填 |
| 北极星 C1-C4（TC-24~27） | 4 | 观测项 | ✅ 观测协议就绪性可在 MVP 交付时验收，非自动化断言 |
| 边界 BE-01~15 | 15 | 路径 A 为主 | ✅ 全部可在 mem-core 引擎层执行（BE-10 需活体本体文件哈希基线） |
| 端到端 TS-01~07 | 7 | TS-01/04/05/06 路径 A；TS-02/03/07 路径 B | ✅ TS-03 依赖 D1-F4 活体路径 + mock PATH；TS-06 恢复=clone + `index --rebuild` |

双路径设计成立：路径 A 的"真实 mem_meta.db"不是 mock——索引由 memcore.indexer 真实构建，验证的是"wiki 文件 → db"派生链路的正确性（A4/C7 断言对象）；路径 B 只验证集成挂点（close.sh / boot_context / manifest / git 追溯）。

### 2.2 三个对齐注记（QA 执行前需要微调）

1. **CLI 名**：QA 方案全文用 `bin/mem`，架构定稿正式名为 `bin/memctl`（mem 软链）。建议 QA 统一为 `bin/memctl` 并加一条软链存在性断言，避免 Step 5 VA 时名字歧义。
2. **BE-02（4 表头 9 表 GAI 解析）**：架构按 R3 反共识取消了 gai.py 表感知解析器，GAI 表格只在 `memctl gai-links`（行 → [[ID]] 双链）和 drift 里做轻量 ID/状态提取。QA 夹具 `expected/parse-gai-dirty.json` 的断言对象应改为 **gai-links 适配器输出**（不是全表规范化解析产物），否则夹具与实现错位。
3. **TS-06（备份恢复）**：mem_meta.db 是 gitignore 派生数据不备份，恢复 = clone + `index --rebuild` + lint。QA 步骤已正确覆盖，此处仅为确认，不需要改动。

### 2.3 工时影响

- 五项 D1 裁定对 MVP 9.5h **无增量**：D1-F2 命令面 = 架构已定稿的 CLI 骨架（P0-4 1h 内）；D1-F3 的 S3a/S3b 分离在 P0-7 0.5h 内（sed 模式改为行尾追加 + 调 memctl done，均属于替换步骤本身）；D1-F4 是发布路径确认（改活体 + 备份推送，0 增量）；D1-F1/F5 纯口径对齐。
- QA 侧 12.5h 估算成立（Round 0 契约裁定 1h 依赖本确认卷与产品/架构卷）。

---

## 3. 实测复核记录（2026-08-10，本卷独有）

| 项 | 实测 | 影响 |
|----|------|------|
| close.sh 两路径 | /root/.hermes/profiles/orchestrator/scripts/close.sh 与 /workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh **md5 相同**（64eb0c69eef4a3ecbaa5248ffd05307b）；backup-repo 为 git repo | D1-F4：活体 + 镜像双副本，同改同验 |
| close.sh S3 | close.sh:70-73 `sed -i 's/\($TASK_ID.*\)待办/\1✅ done/'`；新 GAI 行格式（`\| P1-01 \| DPL-009 \| ... \| 1h \|`）行内无"待办"、行尾无状态列 | D1-F3：sed 对行标记 no-op，需改行尾追加模式 |
| GAI 活体 | /root/.hermes/profiles/orchestrator/GLOBAL_ACTION_ITEMS.md 存在（8366B，2026-08-10 更新，新格式） | D1-F3 口径：GAI 状态是"行标记/分区"而非独立状态列 |
| GAI 副本 | devPPL git 仍跟踪 GLOBAL_ACTION_ITEMS.md（A1 未满足，P0-0 待执行） | 与 QA D1-F6 一致；A1 用例前置成立 |
| mem-core | /workspace/mem-core 不存在 | 路径 B 依赖 dev Step 3 交付；路径 A 不受阻 |
| sqlite | 3.45.1（2024-01-30），≥3.34 trigram 可用 | A3/BE-13 环境就绪；降级路径仍需实现 |

---

## 4. 一句话结论

五项 D1 契约问题从实现角度全部可落地且 MVP 9.5h 零增量：验收口径锁 PRD §5（F1）、命令面锁架构 §4 的 12 命令定稿（F2）、`memctl done` 只写 wiki 而 GAI 标记归 close.sh 展示镜像（F3）、挂点按 orchestrator 活体脚本 + backup-repo 镜像同改同验（F4）、首批 3 页 = R3 三卷 golden 夹具（F5）；QA 49 用例中 45 个可执行项 + 4 个观测项全部可在 mem-core 双路径上执行，仅需三处夹具对齐（CLI 名 / BE-02 断言对象 / 无）。
