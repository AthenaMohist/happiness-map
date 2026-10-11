# D1 评审 — Product 裁定记录：记忆中间层契约冲突

> 作者：许清楚（产品负责人，game-director） | 日期：2026-08-10 | 裁定任务：t_2cc3475d
> 输入：QA 测试方案（docs/qa/memory-middleware-test-plan.md，49 用例）+ PRD v1.0（docs/prd/memory-middleware-prd.md）+ 架构设计 v1.0（docs/arch-memory-middleware.md）
> 性质：D1 评审第一棒（product 裁定），供第二棒 architect（t_5b657c5f）与第三棒 engineer（t_aeb1b7b8）评审，最终供 Step 3 dev 执行

## 总原则

1. **PRD §5 是验收唯一权威**：Step 5 VA 按 PRD §5.1/§5.2 编号逐条断言；任务卡编号作废（见 D1-F1 映射）。
2. **架构 §4 是 CLI 唯一契约**：PRD §10 把 CLI 接口契约交给 Step 2 定稿，架构 §4 即定稿产物（见 D1-F2）。
3. **铁律 2 约束对象是中间层引擎**：展示层 sed 镜像不属于中间层写入路径（见 D1-F3）。
4. **不做与不追**：本裁定只定契约口径，不改任何代码；dev 按裁定执行，QA 按裁定校准断言。

---

## D1-F1 验收编号错位 | BLOCKER → 裁定：以 PRD §5.1 为唯一权威

**冲突**：任务卡（t_0d8a1f63 body）列出的 A1-A9 与 PRD §5.1 A1-A9 内容完全不对应（任务卡 A1=SCHEMA lint / A2=CLI 齐全 / A3=db 确定性生成…；PRD A1=GAI 副本删除 / A2=lint 零问题 / A3=query trigram…）。

**裁定**：**PRD §5.1 编号为唯一权威验收清单**，任务卡 A1-A9 编号作废。QA 已正确选择以 PRD 为权威，维持不动。

**理由**：
- PRD 是 6 步闭环 Step 1 的正式交付物（commit 87731a4），§5.1 自声明"MVP 验收 = §5.1 全绿"；任务卡编号是任务创建时的简写口径，内容已被 PRD 取代。
- 任务卡所有旧项在 PRD 中均有覆盖，**无内容丢失**，只是编号不同。VA 若按任务卡编号执行会错位（如"SCHEMA lint"并非 PRD 验收项）。

**旧编号 → PRD 映射（防下游误读，引用"A1"一律指 PRD 语义）**：

| 任务卡编号 | 任务卡内容 | PRD 对等项 |
|-----------|-----------|-----------|
| 任务卡 A1 | SCHEMA.md 存在且 lint 通过 | PRD A2（lint 零问题）+ A8（首批页 frontmatter 完整） |
| 任务卡 A2 | CLI 命令齐全 | D1-F2 命令面裁定；验证落在 PRD A2/A4/A5/A6 |
| 任务卡 A3 | mem_meta.db 确定性生成（index --rebuild 幂等） | PRD A4 |
| 任务卡 A4 | 双链校验：断链检测通过 | PRD A2（lint I1/I2）+ A8（≥2 出链） |
| 任务卡 A5 | trigram FTS5 CJK 检索可用 | PRD A3 |
| 任务卡 A6 | boot_context v2 第五源静默降级 | PRD A6 |
| 任务卡 A7 | close.sh S3 替换生效（sed → memctl done） | PRD A5 |
| 任务卡 A8 | 备份接入 manifest.yaml | PRD A7 |
| 任务卡 A9 | 首批 wiki 页存在（≥3 页） | PRD A8 |

---

## D1-F2 memctl CLI 命令面不一致 | BLOCKER → 裁定：以架构 §4.1 为最终契约

**冲突**：PRD §4 P0-4 = 5 命令（add/query/lint/index/status）；PRD §10 = 10 命令；R3 Engineer = 7 命令（add/update/query/lint/drift/context/status，无 index/done）；架构 §4.1 = 12 命令（MVP 7 + V2 4 + V3 占位 1）。

**裁定**：**命令面以架构 §4.1 为最终契约**，命令名 memctl（正式），`mem` 为官方软链别名（同一入口）。

**最终命令面**：
- **MVP 7 命令**：`add` / `done` / `query` / `lint` / `index` / `status` / `context`
- **V2 4 命令**：`update` / `drift` / `gai-links` / `demote`
- **V3 占位 1**：`mcp-serve`（仅占位，PRD N4 维持不做 MCP server）
- **退出码**：架构 §4.2（0=成功 / 1=一般错误 / 2=用法错误 / 3=校验失败）

**理由**：
1. PRD §10 交接项 2 明确把"memctl CLI 接口契约：参数与退出码"交给 Step 2 架构设计定稿——架构 §4 正是这项交接的落地产物，是唯一"参数+退出码"齐全的清单。
2. PRD §4 P0-4 是"骨架"表述（原文即"骨架"），5 命令与 §5.1 自相矛盾：A4 依赖 `index --rebuild`、A5 依赖 `done`、A6 依赖 `context`。架构补为 7 命令 MVP 才与验收全对上。
3. Engineer R3 的 7 命令缺 `index`/`done`，无法满足 A4/A5，不可作为 MVP 基准。
4. `demote`（V2）是架构对"状态变更/降级"需求的承接，产品确认新增合理；`gai-links`/`drift`/`update` 归 V2 与 PRD P1 一致。

**附注（PRD 同步修订，不阻塞 dev）**：PRD §4 P0-4 与 §10 交接项 2 需补一行注记"命令面以架构 §4.1 为准"。由文档维护在 Step 3 顺手修订即可，无需专门回退 PRD。

**QA 对齐**：TC-02 附带检查的 `--help` 命令面断言改为按架构 §4.1 清单校验：MVP 7 命令必须实现且可执行；V2/V3 命令允许 `--help` 列出或占位（不计 MVP 门禁）。

---

## D1-F3 `mem done` 写 GAI vs 铁律 2 | BLOCKER → 裁定：确认架构 §8 S3a/S3b 双写职责划分

**冲突**：Engineer R3 说 `mem done` = 写 wiki + 更新 GAI 状态列（sed 级替换）；PRD §7.1 铁律 2"状态不回写环"= 中间层对 L0 只读不写。

**裁定**：**采纳架构 §8 方案**——`mem done` 语义写入 wiki，GAI 状态列展示镜像由 close.sh S3b 负责。职责划分如下：

| 写入方 | 写什么 | 方向 | 性质 |
|--------|--------|------|------|
| L0 真源（kanban.db / GAI 表） | 状态真值 | 机器写 | 事实真源，零 LLM，**不动** |
| memctl done（中间层引擎） | wiki 页：结果节 + status=done + bump updated | 只读 L0 → 写 wiki | 语义写入（主路径） |
| close.sh S3b（既有脚本） | GAI 状态列 `✅ done` | sed 字符串替换 | 展示层镜像，非语义写入 |

**铁律 2 的精确解释**：
- 铁律约束对象是**中间层（memctl 引擎/编译管线）**：对 L0 只读不写。`memctl done` 流程（架构 §4.3）只读 L0 判状态 → 写 wiki → 机械维护 → git 提交，**引擎绝不写 GAI 文件/表**。
- close.sh S3b 的 sed 是 devPPL 既有关闭脚本的展示维护，执行者不是 memctl/中间层，**不属于中间层写入路径**，故不违反铁律 2。
- wiki 页 status 是镜像（供追溯），方向 L0 → wiki 单向；镜像由 memctl 从 L0 同步，**不回写**。

**B5 三方对账前提成立**：wiki 有 status 镜像（memctl 写）+ GAI 有展示列（close.sh sed 写）+ kanban 真源——`drift` 只读对账三方。

**V2 `demote` 同纪律**：语义写 = wiki（status 变更 + 变更说明节）；L0 展示列同步 = sed 级展示镜像，且必须走 source adapter `mirror_status`（架构 §4.5），禁止结构性写 L0。此项在 V2 实现时确认，不进 MVP。

**QA 对齐**：
- A5/TS-03：断言 `memctl done` 写 wiki（结果节 + status=done + updated bump）；并断言 memctl done 执行后 GAI 文件**不变**（GAI 更新只发生在 close.sh S3b 执行后）。
- B5/TS-07：drift 三方对账按上表职责理解（缺页/断链/镜像不一致判定不变）。

---

## D1-F4 close.sh 挂点位置 | MAJOR → 裁定：双份同步替换（源 + 运行实例）

**冲突**：QA 实测 close.sh 在 `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh:73`；架构 §8.1 写 `/root/.hermes/profiles/orchestrator/scripts/close.sh`（104 行）。替换动作落点不清。

**实测核对（本裁定补充证据）**：两个路径文件**字节完全相同**（3314 字节，diff 为空，mtime 一致，inode 不同 → 两份拷贝，非软链）。

**裁定**：
1. **源码/配置真源**：`/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh`（git 管理，可追溯，备份链路覆盖）
2. **运行实例**：`/root/.hermes/profiles/orchestrator/scripts/close.sh`（每次任务关闭实际执行）
3. **替换动作两处同步**：dev 改 backup-repo 源（S3 → S3a + S3b，见架构 §8.2）并 git 提交，再**同步复制**到 `/root/.hermes` 运行实例；两文件必须保持字节一致（与现网现状一致）。
4. **QA 断言**：两文件 diff 为空 + 运行实例 S3a/S3b 生效（A5 走运行实例路径验证，集成夹具指向 backup-repo 源路径）。
5. **不动 mem-core**：close.sh 属于 orchestrator profile 脚本，不属于中间层 repo；mem-core 只提供 `memctl` 二进制入口供 close.sh 调用。

**架构 §8.1 与 QA 的"冲突"是同一脚本的两份拷贝**，非真实分歧：架构写运行实例路径，QA 写源路径，两者都正确，本裁定统一为"双份同步替换"。

---

## D1-F5 首批 3 页对象未定 | MAJOR → 裁定：R3 三卷发言编译页，各一页

**冲突**：PRD A8 要求"首批 3 页（R3 三方发言编译）"，P0-10 LLM 策展回填；具体页面对象未定，QA 建议三卷各一页。

**裁定**：**确认首批 3 页 = R3 三卷发言各编译一页**：
- **对象**：`docs/roundtables/r3-memory-middleware/2026-08-10-product.md` / `-architect.md` / `-engineer.md` 三卷
- **页类型**：`type=decision`（决策档案四段式：背景/问题/验收/参考）——R3 发言本质是裁定/规划，天然匹配 decision 形态
- **命名建议**（与架构 §9.1 golden fixtures 对齐）：`wiki/concepts/decisions/r3-product.md`、`r3-architect.md`、`r3-engineer.md`；具体文件名 dev 可按 SCHEMA ID 模式微调，**QA 不断言文件名，断言内容**
- **A8 断言对象明确**：3 页各自满足 四段非空 + ≥1 参考（指向原始 R3 卷文件路径）+ ≥2 出链（三页互链 product↔architect↔engineer + 链 SCHEMA/index）
- **内容范围**：每卷核心主张（Product=宏观规划/优先级、Architect=架构裁决、Engineer=工时口径/反共识），LLM 策展，不追求全量；同时作为 golden file 测试的真实样本（架构 §9.1 的 golden/r3-*.md 与真实页同源，dev 交付时替换 real-content/）

---

## 裁定汇总

| # | 项 | 级别 | 裁定 | 下游影响 |
|---|----|:---:|------|---------|
| D1-F1 | 验收编号错位 | BLOCKER | PRD §5.1 为唯一权威，任务卡编号作废（附映射表） | VA 按 PRD 编号；QA 维持 |
| D1-F2 | CLI 命令面 | BLOCKER | 架构 §4.1 为最终契约：MVP 7（add/done/query/lint/index/status/context）+ V2 4 + V3 1 占位 | dev 按架构实现；QA 按架构 §4.1 断言 --help |
| D1-F3 | mem done vs 铁律 2 | BLOCKER | 采纳架构 §8：memctl 只写 wiki（L0 只读）；GAI 展示镜像归 close.sh S3b sed；铁律 2 约束对象=中间层引擎 | dev 实现 done 不写 GAI；QA 断言 done 后 GAI 不变 |
| D1-F4 | close.sh 挂点 | MAJOR | 双份同步替换：backup-repo 源（git）+ ~/.hermes 运行实例，字节一致；不动 mem-core | dev 改源并部署；QA 断言两文件一致 |
| D1-F5 | 首批 3 页 | MAJOR | R3 三卷发言各一页，type=decision，四段非空 + ≥1 参考 + ≥2 出链 | dev 编译 3 页；QA 以内容断言 |

**执行顺序**：本裁定（product）→ architect 评审（t_5b657c5f）→ engineer 可执行性确认（t_aeb1b7b8）→ Step 3 dev 按裁定执行 → QA 按裁定校准断言执行。
