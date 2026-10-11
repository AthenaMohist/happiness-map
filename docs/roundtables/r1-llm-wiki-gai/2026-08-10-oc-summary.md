# Roundtable R1 汇总 — LLM-Wiki 记忆系统 + GAI 自动更新机制（B 类）

> 日期：2026-08-10 ｜ 类型：B 类头脑风暴 ｜ R1 初始表态轮（product → architect → engineer 串行）
> OC 收卷：三方发言已全部完成，本报告提交 Frank 裁决方向与执行时机。

---

## 一、三棒发言速览

| 角色 | 发言位置 | 核心观点 |
|------|---------|---------|
| Product（许清楚） | 评论 #378 | 问题定性 = 「决策可追溯」而非「知识管理」；自动更新 > wiki 本体（状态不同步是误导）；触发场景按用户可见事件排序；两条红线（不并入 vault、wiki 必须 git+备份+单一写入者） |
| Architect（高见远） | 评论 #379 + 完整文档 | 定位为 **L3 决策档案层**（零重叠现有三层）；命名双链 + gai_index.py 校验；双层事件驱动（gai.py CLI 唯一写入口 + gai-writer skill）；**实测发现 GAI 双份拷贝已分叉 33 天** |
| Engineer（寇豆码） | 评论 #380 + 完整文档 | 实测 GAI 待办区 32 行、4 种表头 9 张表、L47 脏单元格 → gai.py 必须表感知解析；**「worker 约定」是 OBS-01 同款失败模式** → 主路径接 close.sh S3；WIKI_PATH 不设全局 |

完整文档：
- `docs/roundtables/r1-llm-wiki-gai/2026-08-10-gjy-architect-statement.md`（9 节，~250 行）
- `docs/roundtables/r1-llm-wiki-gai/2026-08-10-kdm-engineer-statement.md`（8 节）

## 二、共识项（三方一致，无需裁决）

1. **问题定性**：决策上下文丢失，不是缺知识库 → 方案 = 行动条目决策档案（每 ID 一页，四段：背景/要解决的问题/验收标准/参考材料）
2. **GAI 承担 index 角色**：GAI 文件保持 orchestrator 路径不动，通过命名双链（`[A-Z]+-\d{3}` → actions/）指向详情页；wiki 不存状态、不替代检索、不存事实偏好，数据流单向（kanban 事件 → GAI 表 → 详情页）
3. **不复用 InfoManager vault-writer**：数据域不同、写入者冲突（vault 四写入者 vs wiki 单一写入者）、repo 边界；只借鉴 frontmatter/git/Obsidian 兼容三条惯例
4. **WIKI_PATH = /workspace/devPPL-wiki 独立 git repo**，必须接入现有备份链路（BKP-003 LFS 模式），记忆不可再生
5. **只回填 P1 七行试点**，不全量回填（回填是最贵的一步）
6. **验收可断言化**：30s 追溯（四段非空 + ≥1 参考来源 + ≥2 出链）、1h 同步（事件时间戳 vs 详情页 updated ≤1h）、周漂移报告为空、Frank 只读（git 写权限仅 agent）
7. **改造第一步 = 消灭 GAI 双份拷贝**（已实测确认分叉 33 天）

## 三、关键分歧（供 Frank 裁决）

| # | 议题 | Architect 观点 | Engineer 观点 | OC 倾向 |
|---|------|---------------|--------------|--------|
| F1 | **工时估算** | 004a wiki 核心 ~2h + 004b 自动更新 ~4h + 回填 ~1h = **~7h** | 004b 实际 **7h**（gai.py 表感知解析器 3h 是最大难点，4 种 schema + 脏数据容错）；回填 P1 七行 1.5-2h（Architect 1h 偏乐观）；总账 **MVP 6.5h + V2 5h ≈ 11.5h** | 采纳 Engineer 实测口径（他先核对了 GAI 真实结构再发言）；建议执行按 11.5h 预算，分 MVP/V2 两阶段 |
| F2 | **触发机制** | worker 生命周期约定（同步调用 gai.py，零轮询，天然带 task_id）；周漂移为唯一 cron | 「worker 约定」是 OBS-01 同款失败模式（LLM 忘记调用 relay_update.py 正在观察期）；**主路径必须接 close.sh S3**（sed→gai.py done，替换现有强制步骤而非新增约定）；新指令走 kanban-worker skill 协议；周 cron 只作兜底 | 采纳 Engineer：把同步动作挂进**已有强制步骤**（close.sh S3），不依赖新增约定；语义层挂事件钩子（DPL-013 思路）作为 V2 |
| F3 | **WIKI_PATH 配置** | WIKI_PATH=/workspace/devPPL-wiki 独立 repo | **不能全局设置**：llm-wiki 通用 skill 的激活条件就是「configured path 存在 wiki」，全局指向会污染研究型会话；WIKI_PATH 由 gai.py/gai-writer 脚本内显式传参，profile .env 保持未设 | 采纳 Engineer：脚本内显式传参，零迁移成本（实测 orchestrator .env 本就无 WIKI_PATH） |
| F4 | **触发场景排序** | 新指令/完成归档/状态变更 = worker 约定；周漂移 = cron | 同左，但强调主路径替换而非新增 | 三方一致：新指令（上下文最新鲜，错过就回不来）> 完成归档（修滞后主战场）> 状态变更记理由 > 周漂移报告 |

## 四、实测发现（已核实）

1. **GAI 双份拷贝分叉 33 天**：orchestrator 版 144 行（2026-08-10 更新）vs workspace 版 197 行（2026-07-08 旧 P0 格式）——workspace 副本零脚本引用，可安全 `git rm`（Engineer 建议，比 symlink 干净）
2. **GAI 待办区实际 32 行**（P1×7 + P2×9 + P3×7 + P5×8 + OBS×1），4 种表头 9 张表；L47 有脏单元格（P3-06 工时列="P3"）→ gai.py 必须表感知解析 + 容错，不能行级 sed
3. **close.sh S3 的 sed 自动修复对新格式已是 no-op**（新表行无「待办」字样）→ 直接证据：GAI 必须 CLI 化，S3 换 gai.py done
4. boot_context.py 不读 GAI（读 kanban/pipeline_state/sessions/memory）→ 纠正：GAI 是 OC/Frank 面向文档，非 5 分钟机器注入

## 五、MVP 实施路径（Engineer 提案，待 Frank 批准）

**MVP（6.5h）**：
- M0：git rm workspace GAI 副本（0.5h）
- M1：wiki 初始化 + 定制 SCHEMA（2h）
- M2：gai.py 最小集 + 20 pytest + close.sh S3 接线（3h）
- M3：回填 P1 七行（1.5h）

**V2（5h）**：gai_drift.py kanban 语义对账（等详情页回填后有对齐基础）、事件钩子（DPL-013 吸收项）、全量回填 32 行。

**试点节奏（本周）**：处理双份拷贝 → 初始化 wiki + SCHEMA → gai.py + gai_index.py → gai-writer skill → 回填 P1 七行 → 接通「新指令」「归档」两触发点 → 周漂移 cron；**下周对账验证，成功再铺 P2**。

## 六、管线标准要素自查（Pitfall 69）

- ✅ 备份流程：devPPL-wiki 独立 repo 接入 BKP-003 LFS 备份链路；系统机制类项目（devPPL）走 SandboxHermesBackup
- ✅ S6 闭环集成点：close.sh S3 替换为 gai.py done 即归档触发主路径（Engineer F2）
- ✅ 失败分支：gai.py --check 四段非空校验、gai_index.py --check 断链 lint、周漂移报告兜底
- ✅ OC ≠ Product：本报告仅为收卷，执行决策权在 Frank

## 七、OC 建议

1. **批准 Engineer 口径**（F1-F3）：按 11.5h 总预算、close.sh S3 主路径、脚本内传参 WIKI_PATH
2. **B 类规则：本报告不建执行卡**。Frank 裁决方向后，OC 再按 6 步闭环建卡派发（MEM-004 拆分 004a/004b 两卡可并行）
3. **GAI 双份拷贝是当下唯一「应立即修」项**——即使方案暂缓，也建议尽快 git rm 旧副本避免进一步分叉（零风险，已实测零引用）
