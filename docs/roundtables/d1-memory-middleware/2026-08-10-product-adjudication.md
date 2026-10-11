# D1 产品裁定卷 — Memory Middleware QA 5 项契约问题

> 发言人：许清楚（产品负责人） | 日期：2026-08-10 | 版本：v1.0
> 类型：D1 前置契约裁定（QA 方案 docs/qa/memory-middleware-test-plan.md 的 D1 发现，产品视角逐项裁定）
> 输入：QA 方案（49 用例，commit a99682c）+ PRD v1.0（权威）+ 架构设计 v1.0（commit 78fc583）+ R3 三卷 + Engineer D1 确认卷（2026-08-10-engineer-confirm.md）
> 实测复核：close.sh 活体路径与 backup-repo 镜像 md5 相同（64eb0c69eef4a3ecbaa5248ffd05307b），两处同源

---

## 0. 裁定总览

| # | 问题 | 级别 | 产品立场 | 一句话落地 |
|---|------|:---:|------|-----------|
| D1-F1 | 验收编号不对应 | BLOCKER | 维持 QA 裁定 | VA/QA 一律以 PRD §5.1 A1-A9 为唯一权威，任务卡编号作废；原任务卡 A1-A9 内容无一条丢失，全部映射到 PRD 断言 |
| D1-F2 | memctl CLI 命令面不一致 | BLOCKER | 维持架构 §4 定稿面 | 12 命令定稿（MVP 7 + V2 4 + V3 占位 1），`memctl` 正式名 + `mem` 软链，退出码 0/1/2/3；**同步修订 PRD §4/§10 消除源头矛盾** |
| D1-F3 | `mem done` 与铁律 2 冲突 | BLOCKER | 修正（铁律 2 完整保留） | memctl 绝不写 GAI；GAI `✅ done` 由 close.sh S3b sed（行尾追加）负责，属 L0 侧脚本自写自文件，不构成回写环 |
| D1-F4 | close.sh 挂点位置 | MAJOR | 维持替换方案，修正挂点定位 | 活体 = `/root/.hermes/profiles/orchestrator/scripts/close.sh:70-73`；backup-repo 是同 md5 备份镜像；改活体 + 备份推送，两处同改同验 |
| D1-F5 | 首批 3 页内容对象 | MAJOR | 维持 QA 建议 | 3 页 = R3 三卷各一页（product/architect/engineer），与架构 §9.1 golden 夹具重合，type=decision 四段式 |

---

## 1. 逐项裁定

### D1-F1 验收编号不对应 — 立场：维持 QA 裁定（PRD §5 权威）

落地：验收编号**锁死 PRD §5.1 A1-A9 / §5.2 B1-B5 / §5.3 C1-C4**，任务卡（t_0d8a1f63 body）里的 A1-A9 编号作废；QA 方案已按 PRD 编号组织用例（TC-01~18 ↔ A1-A9），不需要改编号。核对任务卡原始 A1-A9 内容（SCHEMA lint / CLI 齐全 / db 确定性 / 双链校验 / trigram / boot_context 降级 / close.sh 替换 / 备份 manifest / 首批 3 页）——**逐条都被 PRD §5.1 断言覆盖**（分别对应 A2 / A2 / A4 / A2 / A3 / A6 / A5 / A7 / A8），无一条需求因编号切换而丢失。一句话理由：PRD 是 Frank 裁定的载体、Step 1 权威文档，任务卡编号是编排层早期草稿，冲突时以 PRD 为准——纯口径问题，零代码影响。

### D1-F2 memctl CLI 命令面不一致 — 立场：维持架构 §4 定稿面

落地：最终命令面 = **12 命令**——MVP 7：`add / done / query / lint / index / status / context`；V2 4：`update / drift / gai-links / demote`；V3 占位 1：`mcp-serve`。正式二进制 `bin/memctl`，`bin/mem` 为软链（历史文档引用 mem，两名字同一入口）。退出码 0=成功 / 1=一般错误 / 2=用法错误 / 3=校验失败（lint 有问题、drift 有差异、query 语法错）。QA 方案统一 `bin/memctl` 并加一条软链存在断言。**同步修订 PRD §4 P0-4 与 §10 交接项 2**（见 §3），消除「§4=5 命令 / §10=10 命令」的源头矛盾。一句话理由：架构 §4 是唯一把三份清单合并裁决的文档，命令归属与验收断言阶段完全一致（index→A4、done→A5、context→A6 在 MVP；gai-links/drift/update→B2/B5/B1 在 V2），dev 按此实现零歧义。

### D1-F3 `mem done` 与铁律 2 冲突 — 立场：修正（铁律 2 完整保留，明确写回边界）

落地：状态流单向 **L0 → wiki → 读取**，铁律 2 一条不改：**memctl（中间层）对 kanban/pipeline_state/GAI 只读不写**，`memctl done` 只写 wiki（结果节 + status=done + bump updated + 机械维护 + 原子 git 提交，架构 §4.3 六步）。GAI 的 `✅ done` 标记由 close.sh **S3b 的 sed** 负责——close.sh 是 orchestrator profile 自己的脚本写自己的展示文件，**不属于中间层写路径**；因新 GAI 行内无「待办」字样，sed 模式改为行尾追加 `sed -i "/$TASK_ID/s/$/ ✅ done/"`（采纳 Engineer 确认卷 §1）。B5 drift 三方对账保持只读。一句话理由：铁律 2 的边界是「中间层对 L0 只读不写」，L0 侧脚本自写自文件是展示镜像而非回写环，A5（wiki 页生成）与 B5（三方一致）断言各自可测且不碰铁律。

### D1-F4 close.sh 挂点位置 — 立场：维持替换方案，修正挂点定位

落地：活体脚本 = **`/root/.hermes/profiles/orchestrator/scripts/close.sh`**（104 行，S3 在 70-73 行，Hermes 实际执行路径）；`/workspace/backup-repo/config/profiles/orchestrator/scripts/close.sh` 是 hermes_backup_push.sh 同步的备份镜像（实测两文件 md5 相同 64eb0c69…）。发布路径 = 改活体 → 备份推送进 backup-repo（git 提交可追溯）；devPPL 与 mem-core **都不持有** close.sh，不迁移归仓。QA 夹具指向活体路径，并加一条「活体与镜像 md5 相同」断言。一句话理由：挂点物理位置在 orchestrator profile 脚本是既成事实，中间层只通过 memctl CLI 交互、不依赖脚本归属，产品不要求迁移；双副本必须同改同验，否则就是 GAI 双份拷贝漂移教训的变体。

### D1-F5 首批 3 页内容对象 — 立场：维持 QA 建议（R3 三卷各一页）

落地：首批 3 页 = **R3 三卷各编译一页**，即架构 §9.1 已定的 golden 夹具 `golden/r3-product.md` / `golden/r3-architect.md` / `golden/r3-engineer.md`，**type=decision**（四段式是 SCHEMA §3.1 decision 的定义形态，页落 `wiki/concepts/decisions/`；Architect D1 卷写 type: concept 与之有出入，以 SCHEMA §3.1 为准，dev 落地时按 decision 实现），四段式（背景/问题/验收/参考）+ ≥1 参考 + ≥2 出链，frontmatter `profile:` 分别标 game-director / game-architect / game-qa（顺带喂 BE-04 单副本多 profile 用例）。同一批回填同时服务 A8 抽查与 golden 测试，P0-10 的 1.5h 预算不变。一句话理由：三卷天然是四段式 + 双链 + 单副本多 profile 三个验收面的真实样本，与架构 golden 夹具设计重合，不需要另定对象。

---

## 2. PRD §5 验收断言覆盖确认（任务要求 2）

逐条核对 QA 方案 49 用例与 PRD §5 断言映射，**无遗漏**：

| PRD §5 断言 | QA 覆盖用例 | 覆盖状态 |
|------------|------------|:---:|
| A1 GAI 副本已删 + 可追溯 | TC-01 | ✅ |
| A2 lint 零问题（四不变式） | TC-02~06 + BE-05/06/14 间接 | ✅ |
| A3 trigram 3 字 / bigram 2 字 | TC-07~09 + BE-13 降级 | ✅ |
| A4 index --rebuild 幂等 | TC-10~11 + BE-09 篡改检出 | ✅ |
| A5 close.sh → wiki 页 | TC-12~13 + TS-03 | ✅ |
| A6 boot_context 第五源 + 静默降级 | TC-14~15 + BE-11 + TS-02 | ✅ |
| A7 备份 manifest 含 mem-core | TC-16 + TS-06 | ✅ |
| A8 首批 3 页四段非空 + 参考 + 出链 | TC-17 + BE-04 | ✅ |
| A9 pytest ≥15 用例全绿 | TC-18 | ✅ |
| B1 update --plan 候选集 + <20 文件 | TC-19 + BE-07 + TS-04 | ✅ |
| B2 gai-links 零断链 | TC-20 | ✅ |
| B3 5 项待办回填质量 | TC-21 | ✅ |
| B4 矛盾检测 + review 队列 | TC-22 + BE-08 | ✅ |
| B5 drift 三方对账为空 | TC-23 + TS-07 | ✅ |
| C1-C4 北极星观测协议就绪 | TC-24~27（观测项，MVP 后 1 周首观测） | ✅ |
| §5.4 反指标（不看页数/同步率/覆盖率） | QA §0.2 声明 + §9 统计不含反指标断言 | ✅ |

另：R3 七项测试重点（确定性容错 / 单副本多 profile / blast radius / trigram+bigram 边界 / 记忆宫殿标签 / 跨会话恢复 / 本体文件红线）全部映射到 BE/TS 用例（QA §0.2 项 4），Engineer D1 卷 §2 已从实现侧逐项确认可执行（45 可执行 + 4 观测项）。

**结论：PRD §5 全量断言被 QA 方案覆盖，无遗漏。MVP 门禁 = A1-A9 全绿 + BLOCKER=0 AND MAJOR≤3 的发布条件成立。**

**Architect D1 卷补充的 3 个非阻塞缺口（建议 QA Round 3/5 顺带补齐，不改变 49 用例结论）**：
1. `memctl demote`（V2）无专用用例——建议 V2 阶段补 1 例（写 wiki + 展示层镜像行为断言）
2. `memctl status` 无专用断言——建议 Round 5 顺带断言（TS-01 隐含）
3. `memctl done` fail-open 分支（L0 读失败仍写 wiki，close 不挂死）无用例——建议 TC-13 增加 mock L0 失败变体

另采纳 Architect 环境勘误：sqlite 实机 3.45.1，架构设计 §5/§15 与 Engineer R3 的 "3.53.1" 为文档笔误（均 ≥3.34，trigram 结论不变），建议顺手修正。

---

## 3. PRD 修订清单（D1-F2 源头矛盾消除）

PRD v1.0 内部存在「§4 P0-4 = 5 命令 / §10 交接 = 10 命令」的矛盾，QA D1-F2 正源于此。作为权威文档，PRD 必须自洽。修订两处（版本 bump v1.1）：

1. **§4 P0-4 行**：MVP 命令面从 `add / query / lint / index / status` 改为 **7 命令**：`add / done / query / lint / index / status / context`，注明「正式名 memctl，mem 为软链；V2 增 update/drift/gai-links/demote，V3 占位 mcp-serve；命令全集与退出码见架构 §4」
2. **§10 交接项 2**：从 10 命令清单改为引用架构 §4 定稿面（12 命令 + 退出码 0/1/2/3）

D1-F1/F3/F4/F5 无需改 PRD（F1 纯口径、F3/F4 已在架构 §8 落地、F5 已在架构 §9.1 落地）。

---

## 4. 对其他角色影响

| 角色 | 影响 |
|------|------|
| **Architect（高见远）** | §4 命令表被确认为权威契约；§8.2 S3a/S3b 分离被确认为铁律 2 的边界裁定；§9.1 golden 夹具确认为 A8 对象。无需改动 |
| **Engineer（寇豆码）** | 按架构 §4 实现 12 命令（MVP 7）；S3b sed 改行尾追加模式；改活体 close.sh + 备份推送。与 Engineer D1 确认卷一致，无新增负担 |
| **QA** | 验收编号按 PRD §5；CLI 引用统一 `bin/memctl` + 软链断言；BE-02 断言对象改为 gai-links 适配器输出；TS-03 夹具指向活体路径 + md5 断言。三项对齐注记（Engineer 卷 §2.2）全部接受 |

---

## 5. 一句话结论

五项 D1 契约问题产品裁定完毕：**验收口径锁 PRD §5（F1）、命令面锁架构 §4 的 12 命令定稿并回修 PRD 源头矛盾（F2）、铁律 2 一条不改——memctl 绝不写 GAI、GAI 标记归 close.sh 展示镜像（F3）、挂点按 orchestrator 活体脚本 + backup-repo 镜像同改同验（F4）、首批 3 页 = R3 三卷 golden 夹具（F5）**；PRD §5 全量断言 QA 覆盖无遗漏，MVP 门禁条件成立，Step 3 dev 可据此动手。

> 产品发言完毕。PRD v1.1 修订随附（§4 P0-4 + §10 交接项 2）。下一步：QA 更新测试方案对齐注记 → Round 0 契约裁定关闭 → Step 3 dev 启动。
