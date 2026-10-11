# D1 评审 — Architect 第二棒评审：产品裁定 5 项契约冲突

> 评审人：高见远（架构师） | 日期：2026-08-10 | 任务：t_5b657c5f
> 评审对象：产品裁定（t_2cc3475d，commit aa13606，docs/roundtables/r3-memory-middleware/2026-08-10-d1-ruling-product.md）
> 对照基准：架构设计 v1.0（docs/arch-memory-middleware.md，commit 78fc583）+ PRD v1.0（commit 87731a4）+ QA 测试方案（docs/qa/memory-middleware-test-plan.md）+ 实测环境

---

## 0. 总体评价

产品裁定 5 项（F1-F5）**全部成立**，与架构设计 §3/§4/§8/§9 口径一致，dev 可依此执行。第二棒评审确认 F2/F3 架构方案成立，无方向性推翻。

**但评审发现 3 个产品裁定未覆盖的缝隙**（不改裁定，但 dev/QA 必须吸收，否则 Step 5 VA 会红）：

1. **[缝隙 A — 必改] S3b 的 sed 模式对新格式 GAI 仍是 no-op**：裁定 F3 保留 `sed 's/\($TASK_ID.*\)待办/\1✅ done/'` 作为 S3b 展示镜像。实测当前 GAI（GLOBAL_ACTION_ITEMS.md，8366B）任务行**不含"待办"字样**（"待办"仅出现在标题行与分区头，`grep -c '待办'` = 2，均为非任务行）。该 sed 对 2026-08-10 新格式任务行匹配不到 → S3b 依然写不进 `✅ done`。若不做修正，B5 三方对账的 GAI 侧镜像永远不成立、TS-03 步骤 4 断言必挂。
   - **修正方向**（架构 §8.2 S3b 需升级）：以 TASK_ID 行定位 + 行尾追加/替换，例如 `sed -i "/$TASK_ID/ s/| *$/$TASK_ID | ✅ done |/"` 类模式（按实际表头 4 变体校准，QA BE-02 夹具可复用），不再依赖"待办"字样。
   - **QA 对齐**：TS-03/TC-13 断言改为"close.sh 执行后 GAI 含 `$TASK_ID.*✅ done` 行"，并加负向断言"未执行 close.sh 时 GAI 不变"。

2. **[缝隙 B — 必改] S3a 引用 `memctl done --check`，但架构 §4.3 done 契约未定义该 flag**：close.sh S3a 的 check 命令是 `memctl done '$TASK_ID' --check`（§8.2），但 §4.3 只定义了 `--result` / `--no-commit`。`--check` 语义（只检查不写、退出码 0=已完成）必须补进 §4.3 契约，否则 dev 实现时 S3a 的 check 分支无据可依。
   - **修正**：dev 实现 done 时同步实现 `--check`（dry-run：页面存在且 status=done → 退出 0；否则退出 1，**不写任何东西**）；QA TC-12 可加 `done --check` 变体断言。

3. **[缝隙 C — 建议] QA 夹具 location 与架构 §3.4 taxonomy 冲突**：QA clean/ 夹具 `entities/mem-core.md` 与 BE-05 步骤用 `location: Wing-A/Room-1/Shelf-1`，但架构 §3.4 的 wing 枚举是小写 slug（devppl/infomanager/hermes/claude/general），room 枚举为 memory/pipeline/qa/roundtable/backup/tooling/integration/general——`Wing-A/Room-1/Shelf-1` **不是合法 location**，`mem lint` 会 FAIL，导致 clean 夹具跑 TC-02（lint 零问题）直接红。
   - **修正**：夹具改用已注册值，如 `location: devppl/memory/architecture`；BE-05 的"非法值"用例恰好可以用 `Wing-A/Room-1/Shelf-1` 当负样本。

另有 2 个小勘误（不阻塞）：
- 架构 §4.3 标题"MVP 六条 + done 特殊"是旧计数，§4.1 已定 MVP 7 命令（add/done/query/lint/index/status/context）；dev 以 §4.1 命令总表为准，QA 以裁定 F2 清单为准。
- QA BE-03 的 wikilink 正则写作 `[A-Z]+-\d{3}`，架构 §3.3 是 `[A-Z]+-\d{2,3}`（两位三位兼容）；BE-03 步骤应补 `[[P0-19]]`（两位）用例。

---

## 1. D1-F1 验收编号错位 | BLOCKER — 确认裁定

裁定"PRD §5.1 为唯一权威 + 任务卡编号作废 + 附映射表"，**确认成立**。

- 架构 §14 自声明"MVP 交付门禁 = PRD §5.1 A1-A9 全绿"，与裁定同口径。
- 映射表核对：任务卡 A1→PRD A2+A8、A2→CLI 裁定、A3→A4、A4→A2+A8、A5→A3、A6→A6、A7→A5、A8→A7、A9→A8，无内容丢失。✓
- 唯一补充：VA 阶段必须按 PRD 编号执行，架构 §3.7 四不变式表已标注对应 A 断言（I1→A2/A8、I2→A2、I3→A2/A5、I4→A2/A4），作为 VA 逐条断言时的映射参考。

## 2. D1-F2 memctl CLI 命令面 | BLOCKER — 确认裁定

裁定"架构 §4.1 为最终契约：MVP 7 + V2 4 + V3 占位 1，memctl 正式 + mem 软链，退出码 0/1/2/3"，**确认成立**。

- 架构 §4.1 12 命令清单与裁定一致（add/done/query/lint/index/status/context + update/drift/gai-links/demote + mcp-serve）。✓
- 退出码与 QA 断言兼容：TC-09 空结果→0、缺参→2；TC-02~06 lint→0/3。✓
- 裁定"PRD §4/§10 补注记不阻塞 dev"同意；**dev 交付时应顺手同步**（一行 footnote，避免 PRD 继续作为歧义源）。
- 补充：`--help` 命令面断言按裁定清单执行，V2/V3 命令允许占位（不计 MVP 门禁）——已与 QA TC-02 对齐。

## 3. D1-F3 `mem done` 写 GAI vs 铁律 2 | BLOCKER — 确认裁定 + 缝隙 A/B

裁定"采纳架构 §8 S3a/S3b：memctl done 只写 wiki，GAI 展示镜像归 close.sh S3b sed，铁律 2 约束中间层引擎"，**确认成立**。

**回答任务卡遗留的两个问题**：
- **GAI 表作为 L0 真源由谁更新？** → GAI 状态列由 close.sh S3b（orchestrator 既有脚本，机器写）维护；kanban.db 由 Hermes 引擎生命周期维护。memctl（中间层）对两者**只读不写**，铁律 2 完整。
- **wiki 写 status 不算回写环？** → 不算。wiki 页 status 是 L0→wiki 的单向镜像（架构 §3.6 边界 1 + 不变式 I3），memctl 从 L0 读真值、写镜像，镜像不回传 L0，方向不成立，不构成回写环。

**缝隙 A（S3b sed 对新格式 no-op）与缝隙 B（done --check 未定义）见 §0，必须吸收。**

职责表补充确认（比裁定表更精确）：
| 写入方 | 写什么 | 方向 | 铁律 2 适用 |
|--------|--------|------|:---:|
| Hermes 引擎 | kanban.db 状态真值 | 机器写 | 不适用（L0 自身） |
| close.sh S3b | GAI 展示列 ✅ done | 展示镜像 | 不适用（非中间层） |
| memctl done | wiki 页 status 镜像 + 结果节 | L0→wiki | 适用：只读 L0，绝不写 GAI/kanban |

## 4. D1-F4 close.sh 挂点位置 | MAJOR — 确认裁定

裁定"双份同步替换：backup-repo 源（git）+ /root/.hermes 运行实例，字节一致，不动 mem-core"，**确认成立**。

实测复核（本评审独立验证）：
- 两路径文件字节相同（3314B，`diff` 空），inode 不同（两拷贝，非软链）。✓
- backup-repo 是 git 仓（最近提交 3828d0b4 Backup 2026-08-10），**是唯一可追溯源**；`/root/.hermes/profiles/orchestrator` **不是 git repo**（`git rev-parse` 报 not a git repository），是纯运行副本。✓
- 补充：dev 同步复制时**保留可执行位**（现权限 -rwx--x--x，QA 可加权限断言）；替换内容按 §8.2 S3a/S3b 执行，并吸收缝隙 A/B 的修正。

## 5. D1-F5 首批 3 页对象 | MAJOR — 确认裁定

裁定"首批 3 页 = R3 三卷各一页，type=decision，四段非空 + ≥1 参考 + ≥2 出链，QA 断言内容不断言文件名"，**确认成立**。

- type=decision 与架构 §3.1 决策页形态（背景/问题/验收/参考）吻合，A8 的"四段非空"断言天然对齐。✓
- 与架构 §9.1 golden 夹具同源（tests/golden/r3-*.md 与真实页同内容，dev 交付时替换 real-content/）。✓
- 补充：若 location 用 `devppl/roundtable/memory`，`memory` shelf 不在 §3.4 示例枚举内，**需先在 SCHEMA.md 注册**（新增值流程 §3.4）；或改用已注册 shelf（如 `devppl/roundtable/decisions`）。

---

## 6. 评审结论

| # | 项 | 级别 | 产品裁定 | 架构评审 |
|---|----|:---:|---------|---------|
| D1-F1 | 验收编号错位 | BLOCKER | PRD §5.1 唯一权威 | ✅ 确认 |
| D1-F2 | CLI 命令面 | BLOCKER | 架构 §4.1 最终契约 | ✅ 确认（dev 顺手同步 PRD footnote） |
| D1-F3 | mem done vs 铁律 2 | BLOCKER | 采纳 §8 S3a/S3b | ✅ 确认 + **缝隙 A/B 必改** |
| D1-F4 | close.sh 挂点 | MAJOR | 双份同步替换 | ✅ 确认（保留可执行位） |
| D1-F5 | 首批 3 页 | MAJOR | R3 三卷各一页 | ✅ 确认（shelf 需注册） |

**Step 3 dev 必须吸收**：缝隙 A（S3b sed 模式适配新格式）、缝隙 B（done --check 契约）、QA 夹具 location 修正（缝隙 C）。
**Step 4 QA 必须吸收**：TS-03/TC-13 断言按新格式 GAI 校准；clean 夹具 location 用已注册值；BE-03 补两位 ID 用例。

一句话：**产品裁定方向全对，5 项全部确认；真正的工作量在"把 S3b 从'展示镜像'的语义落地成对新格式真实有效的模式"，这是裁定与架构 §8.2 交接时漏掉的一环，dev 实现时务必补上。**
