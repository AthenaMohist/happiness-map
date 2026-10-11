# D1 Architect 发言 — Memory Middleware QA 5 项契约问题评审

> 发言人：高见远（架构师） | 日期：2026-08-10
> 评审对象：`docs/qa/memory-middleware-test-plan.md` v1.0（992 行，49 用例）发现的 D1-F1~F5
> 对照基准：`docs/arch-memory-middleware.md` v1.0（891 行，commit 78fc583）+ PRD v1.0（commit 87731a4）+ 实测环境
> 裁定角色：D1 审定架构侧口径，供 QA Round 0 + Product 统一裁定（t_84be63c0）吸收

---

## 0. 总体评价

QA 方案的 D1 前置发现质量高：5 项均为**契约级**问题（非代码缺陷），在 dev 动手前提出完全正确。三处 BLOCKER（F1 编号错位 / F2 命令面 / F3 铁律冲突）全部属实，实测复核均成立。架构设计本身无缺陷被新发现；本发言给出 5 项裁定的架构侧口径，并确认 49 用例与架构设计的覆盖关系。

实测复核结果：
- **F4 双路径成立**：`/root/.hermes/profiles/orchestrator/scripts/close.sh`（live，104 行）与 `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh`（git 镜像）**diff 完全一致**；backup-repo 是 git 仓（最近提交 f10af46c Backup 2026-07-31）。
- **F1 编号错位属实**：任务卡（t_0d8a1f63）A1-A9 与 PRD §5.1 A1-A9 内容确不对应（详见 §1 映射表）。
- **F2 三处命令面确不一致**：PRD §4=5 / PRD §10=10 / Engineer R3=7；架构设计 §4.1=12（含 MVP 7）。
- 环境：sqlite 3.45.1（QA 实测正确；架构设计 §5/§15 与 Engineer R3 引用的 "3.53.1" 有误——**文档勘误**，两者均 ≥3.34 不影响 trigram 结论）。

---

## 1. D1-F1 裁定：验收编号错位 — **维持 QA 立场：PRD §5.1 为唯一权威，附编号映射表**

**裁定：以 PRD §5.1 A1-A9 为唯一权威验收编号；任务卡编号作废但保留映射供 VA 对账。**

任务卡的 A1-A9 是 PRD 成形前的 R3 汇总速写（写卡时 PRD 尚未产出），被 PRD §5.1 正式取代。PRD 是产品权威文档，验收必须以它为基准——QA 方案"一律以 PRD §5 编号为权威"的处理正确。

**编号映射表（任务卡 → PRD，供 VA/后续 dev 对账，防"内容对但编号对不上"）**：

| 任务卡编号 | 任务卡内容 | 落点 |
|---|---|---|
| A1 | SCHEMA.md 存在且 lint 通过 | PRD A2（lint 四不变式）+ 架构 §3 |
| A2 | memctl CLI 命令齐全 | PRD A2/A4/A5 + 架构 §4（见 D1-F2） |
| A3 | mem_meta.db 确定性生成（幂等） | PRD A4 |
| A4 | 双链校验：断链检测通过 | PRD A2（不变式 I1） |
| A5 | trigram FTS5 CJK 检索 | PRD A3 |
| A6 | boot_context v2 第五源静默降级 | PRD A6 |
| A7 | close.sh S3 替换生效 | PRD A5 |
| A8 | 备份接入 manifest.yaml | PRD A7 |
| A9 | 首批 wiki 页 ≥3 页 | PRD A8 |
| —（任务卡无对应） | GAI 副本删除 / pytest ≥15 全绿 | PRD A1 / A9（PRD 新增硬断言） |

一句话理由：验收必须以交付物（PRD）为准，任务卡只是输入摘要；不修 = VA 断言无法机械对齐（QA 判 BLOCKER 正确）。

---

## 2. D1-F2 裁定：memctl CLI 命令面 — **给出权威定义（修正 PRD §4 骨架，吸收 §10，对齐 Engineer 7 命令）**

**裁定：命令面 = 12 命令三阶段；MVP 7 命令；命令名 `memctl`（正式）+ `mem`（官方软链别名，同一入口）；退出码 0/1/2/3。**

PRD §4 P0-4 的 5 命令（add/query/lint/index/status）是"CLI 骨架"清单，但 PRD 自己的验收断言要求 done（A5/P0-7）与 context（A6/P0-6）在 MVP 落地——**命令面由验收断言反推收敛，这是唯一不自相矛盾的口径**。架构设计 §4.1 的 12 命令表即最终命令面，予以确认。

| 阶段 | 命令 | 依据（验收断言） |
|---|---|---|
| **MVP（7）** | `add` / `query` / `lint` / `index` / `status` / **`done`** / **`context`** | done←A5（close.sh S3）；context←A6（boot_context 第五源）；index --rebuild←A4 |
| **V2（4）** | `update` / `drift` / `gai-links` / `demote` | drift←B5；gai-links←B2；update←B1 |
| **V3 占位（1）** | `mcp-serve` | PRD N4 预留 |

**归属澄清（QA D1-F2 表直接引用）**：`done`=MVP（A5 依赖）；`index --rebuild`=MVP（A4 依赖）；`gai-links`=V2（B2 依赖）；`drift`=V2（B5 依赖）；`context`=MVP（A6 依赖）。

**退出码约定（架构 §4.2 确认）**：0=成功/lint 零问题/无漂移；1=一般错误；2=用法错误（argparse 默认，缺参/未知命令）；3=校验失败（lint 有问题 / drift 有差异 / query 语法错误）。**补充语义：query 空结果 = 退出 0**（不是错误，TC-09 以 0 为准）；lint 有 FAIL = 3。

**QA 断言影响**：TC-02/03/04/05/06 断言 lint 退出码（0 vs 3）；TC-09 断言 query 空结果退出 0、缺参退出 2；TS-03 断言 close.sh 调 `mem done`——统一用 `bin/mem` 或 `memctl` 均可（软链同一入口，QA 现用 `bin/mem` 正确）。

一句话理由：MVP 命令面由 PRD 验收断言反推（done/context 是 A5/A6 的硬依赖，不能留到 V2），12 命令三阶段是 PRD §10 全景 + demote + mcp-serve 的完整收敛。

---

## 3. D1-F3 裁定：`mem done` 与铁律 2 — **维持铁律 2 字面：memctl 不写 GAI；GAI 状态列由 close.sh S3b 展示层镜像负责**

**裁定：memctl（编译管线）对 GAI 表只读不写——读（drift/gai-links/done 的 L0 只读提取），写仅限 wiki 页。GAI 状态列 `✅ done` 的写者是 close.sh 的 S3b（保留现有 sed，展示层镜像），不是 memctl。**

铁律 2「状态不回写环」管的是**中间层（memctl）不得回写 L0**；close.sh 是 orchestrator 既有脚本，其 sed 是把 wiki 状态展示到 GAI 表格的**展示层更新**（非语义写入），不属于中间层写路径——因此不冲突。wiki 页 `status` 字段是镜像（不变式 I3），方向恒为 L0→wiki。

落地（架构 §8.2 确认，S3 拆两步）：
- **S3a（主路径·强制）**：close.sh 调用 `memctl done <ID>` → 写 wiki 详情页（结果节 + status=done + bump updated）+ 机械维护 + 原子提交。
- **S3b（展示层镜像）**：close.sh 保留 `sed 's/($TASK_ID.*)待办/\1✅ done/'` 更新 GAI 状态列。
- **fail-open**（R10）：memctl done 读 L0 失败 → 仍完成 wiki 写（以 ID 为锚），close 流程继续不挂死；S3a 失败仅记 FAIL 提示手动补。

**QA 断言影响**：TS-03 步骤 4「GAI 状态列 ✅ done」= 验证 **close.sh S3b 的 sed**（不是 memctl 写 GAI）；TC-12/TC-05 断言 wiki 页 status=done（镜像）；B5 drift 三方对账以 wiki 页 status 镜像为基准，GAI 侧只做缺页/断链检查（架构 §4.4 已定义）。

一句话理由：让 memctl 写 GAI = 中间层自己破坏自己的铁律；把展示层 sed 留在 close.sh（它本就在做这件事），铁律 2 字面与闭环功能两全。

---

## 4. D1-F4 裁定：close.sh 挂点 — **实测双路径：live 为主 + backup-repo git 镜像同步提交**

**裁定：替换对象 = live 路径 `/root/.hermes/profiles/orchestrator/scripts/close.sh`（orchestrator 实际执行），同步更新 git 镜像 `/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh`；发布 = 两处一致 + backup-repo 内提交。**

实测复核：两文件 **diff 完全一致**（3314 字节），backup-repo 是 git 仓。QA 找到的是 git 镜像（backup-repo），架构设计 §8.1 记录的是 live 路径——**两个都是真的，缺一不可**。

**替换/发布路径（dev Step 3）**：
1. 改 live：`/root/.hermes/profiles/orchestrator/scripts/close.sh` S3 → S3a + S3b
2. 同步 git 镜像：`/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh`（同一改动）
3. backup-repo 内 git commit（message 注明 memctl S3a/S3b 替换），提交可追溯

**QA 夹具**：TS-13/TS-03 用 mock PATH 指向 **live 脚本**运行；断言三处——live 无旧 sed（或已替换为 memctl 调用）、backup-repo 镜像一致（diff 为空）、backup-repo git log 可追溯替换提交。

一句话理由：只改一处必然制造两副本分叉（GAI 双份拷贝 33 天是同一个病）；live 改 + 镜像提交才能让强制步骤真实生效且版本可溯。

---

## 5. D1-F5 裁定：首批 3 页内容对象 — **确认架构 §9.1 方案（R3 三卷各一页），补充内容契约**

**裁定：首批 3 页 = R3 product / architect / engineer 三卷各编译一页（QA 建议即架构设计 §9.1 golden 夹具方案，予以确认）。**

内容契约（写进 P0-10 执行口径 + golden 夹具）：
- 文件：`wiki/concepts/r3-2026-08-10-product.md` / `r3-2026-08-10-architect.md` / `r3-2026-08-10-engineer.md`（tests/golden/ 同名夹具）
- frontmatter：`type: concept`；`profile:` = 发言人 profile（game-product / game-architect / game-dev）；`location: devppl/roundtable/memory`（wing=devppl, room=roundtable, shelf=memory，均已在 SCHEMA 枚举内）
- 四段式（背景/要解决的问题/验收标准/参考）非空；≥1 参考来源（指向 `raw/` 原始发言或 `docs/roundtables/r3-memory-middleware/` 路径）；≥2 出链（如 `[[concepts/compiler-not-search-engine.md]]`、`[[concepts/single-writer.md]]`）
- 与 A8 的关系：TC-17 直接以这 3 页为抽样对象（不再另选）；同时作为 golden fixture 进 tests/golden/（A9/TC-18 断言 golden 用例存在）

一句话理由：三卷各一页天然满足四段式+双链要求，LLM 策展输入现成（1.5h P0-10 预算足够），且同时服务 A8 验收与 golden 测试两件事。

---

## 6. 覆盖关系确认：QA 49 用例 ↔ 架构设计（任务 3）

**结论：QA 49 用例对架构设计 §4-§12 全部工程契约有对应覆盖，PRD §5 全断言（A1-A9×18 / B1-B5×5 / C1-C4×4 观测项）均有归宿。**

| 架构设计章节 | 对应 QA 用例 |
|---|---|
| §3 SCHEMA（frontmatter/wikilink/taxonomy/铁律/四不变式） | TC-02/03/04/05/06；BE-01/03/05/06；BE-04（单副本） |
| §4 CLI 契约（MVP 7 命令 + 退出码） | TC-02~16（lint/index/done/context/query）；TS-01 |
| §5 mem_meta.db schema（派生数据） | TC-10/11（幂等/派生性）；BE-09（篡改检出）；BE-13（trigram 降级） |
| §6 blast radius 增量更新 | TC-19；BE-07；TS-04 |
| §7 boot_context v2 | TC-14/15；BE-11；TS-02/05 |
| §8 close.sh S3 替换 | TC-12/13；TS-03 |
| §9 golden file 测试体系 | TC-18（pytest≥15 含 golden）；TC-17（A8 首批 3 页）；BE-01/02/03 |
| §10 200 文件墙/归档 | BE-12（启动协议 10-20 文件）；BE-15（归档）；BE-06（200 行） |
| §11 替代本体红线 | BE-10 |
| §12 备份 | TC-16；TS-06 |
| §4.5 source adapter | TC-20（gai-links）；TC-23（drift）；BE-02（GAI 表解析容错） |

**3 个小缺口（建议 Round 3/5 补，非阻塞，不改变 49 用例结论）**：
1. `memctl demote`（V2）无专用用例——B5 覆盖一致性但 demote 行为（写 wiki + 展示层镜像）无断言，建议 V2 阶段补 1 例。
2. `memctl status` 无专用断言——TS-01 隐含，建议 Round 5 顺带断言（低优先）。
3. `memctl done` fail-open 分支（L0 读失败仍写 wiki，close 不挂死）无用例——这是 R10/close.sh 闭环的关键路径，建议 TC-13 增加一个 mock L0 失败的变体。

**环境勘误**：sqlite 实机 3.45.1（QA 实测正确）；架构设计 §5/§15 与 Engineer R3 引用 "3.53.1" 有误，建议顺手修正文档版本号（均 ≥3.34，trigram 可用，不改变任何结论）。

---

## 7. 一句话总结

QA 的 5 项 D1 全部成立且已给架构侧口径：**F1 PRD §5.1 为唯一验收权威（附映射表）；F2 命令面 12 命令三阶段、MVP 7 命令、退出码 0/1/2/3；F3 memctl 不写 GAI、GAI 状态列由 close.sh S3b 展示层镜像负责、铁律 2 字面完整；F4 close.sh 双路径（live + backup-repo 镜像）同步替换；F5 首批 3 页 = R3 三卷各一页（golden 夹具同源）**——49 用例覆盖架构设计全部工程契约，3 个小缺口建议 Round 3/5 补齐。
