# 评估报告 — [DEV-EST] MEM-007 kanban 事件源 → memctl 自动写 wiki/GAI（mem-core 自动记录维护）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_2ba7e58f
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡链：t_33c634a1（PRD v1）→ t_6ed31c9a（PRD v2）→ t_e5918369（arch，main c819afc）→ **本评估 → dev**
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +3.22 → K=3.00（clamp 0.5-3.0）；最近 5 条偏差含 t_8458422f（12-15→60，+3.44）、t_e33936c6（12-18→60，+3.00）

## 1. 结论（TL;DR）

**拆 5 张串行子卡（校准后每张 ≤30 轮，落在单会话 42 有效轮预算内）。**

任务本质是**记忆积累自动化蓝图第一环**的落地：在 mem-core 上新增第二个 SourceAdapter
（`sources/kanban.py`，白名单 kind 归一化 created/completed/blocked/unblocked → create/done/demote/update，
mode=ro 只读），在 devPPL 上新增独立同步引擎（`scripts/mem_sync.py` + `mem_sync.sh`），
并补 `memctl gai-links --set-status`（GAI 状态列单一写入者）与 close.sh S3b 漂移修复。

架构 §12 建议拆 2 张 dev 卡（D1=mem-core S1+S2，D2=devPPL S3+S4+S5）。**按 DPL-018 校准 K=3.00 复算：
该 2 卡分组每张校准后 42-75 轮，双双超出单会话 42 有效轮预算——正是 t_8458422f/t_e33936c6
（预估 12-15/12-18 → 实际 60 超时）的同款量级，照搬必重蹈超时。** 必须拆得更细：
按架构自然边界（S1 机制 / S1 测试 / S2 / S3 / S4+S5）拆 5 张，每张基准 3-10 轮、校准后 9-30 轮。

**评估期间实测基线**：mem-core 现有 pytest 套件 ~90+ 用例（test_v2 36 + test_seq 4 + 其余 13 个测试文件）；
memcore/sources/base.py 41 行三方法（无 initial_cursor/command_for）；cli.py 1736 行已含
_kanban_read_full/_kanban_epoch_to_iso/_kanban_extract_task_code（L122/178/210，需提取为 kanban_db.py 共享模块）；
gailinks.py 117 行（无 set_gai_status）；close.sh L19 GAI_FILE 旧路径失效 + L104-106 S3b 行尾 ✅ 需改状态列替换。

## 2. 工作量评估（读码结论，非假设）

| 维度 | 评估 | 依据 |
|------|------|------|
| 改动面 | **跨 2 仓 ~12 文件**：mem-core 8（base.py 改 / kanban_db.py 新 / sources/kanban.py 新 / sources/__init__.py 改 / cli.py 改 / gailinks.py 改 / tests/test_sources_kanban.py 新 / tests/test_gai_set_status.py 新）+ devPPL 4（scripts/mem_sync.py 新 / mem_sync.sh 新 / scripts/test_mem_sync.sh 新 / scripts/close.sh 改） | 架构 §11.1 文件清单 |
| ① S1 机制（kanban adapter） | base.py +2 可选方法（initial_cursor/command_for，向后兼容 gai.py 零改动）1 轮；kanban_db.py 提取 3 函数（_kanban_read_full L122/_kanban_epoch_to_iso L178/_kanban_extract_task_code L210，cli.py 改 import）2-3 轮（1736 行 cli.py 重构需谨慎回归）；sources/kanban.py 主体（fetch_events 白名单 SQL + mode=ro + map_id + mirror_status + command_for，~200 行）4 轮；SOURCES 注册 0.5 轮；冒烟 2-3 断言 1 轮 → **基准 8-10 轮** | 架构 §2 契约定稿已给 SQL/映射表/签名，实现是照搬；schema.py 已有 CARD_CODE_RE/ENV_KANBAN_DB/DEFAULT_KANBAN_DB |
| ② S1 测试（12 用例） | conftest.py 需**新建 kanban.db fixture**（临时库 + 4 类 task_events + tasks 行，现有 conftest 只有 wiki_root/db_path）2 轮；test_sources_kanban.py 12 用例（归一化/白名单/增量/上限/只读/map_id/mirror/command）4 轮；mem-core pytest 全量回归 1 轮 → **基准 6-8 轮** | 架构 §9.1 用例表 12 条已列明断言 |
| ③ S2（gai-links --set-status） | gailinks.py set_gai_status 引擎（表头定位状态列 _STATUS_HEADERS 扩展 + 行定位 + t_xxx 反查 + 幂等不写 + 原子改写）2-3 轮；cli.py --set-status 接线（参数/退出码 0/1/2/3 + _maintenance + _git_commit `mem(gai): set-status <ID> done`）1-2 轮；test_gai_set_status.py 4 用例 2 轮；回归 1 轮 → **基准 6-8 轮** | 架构 §4 契约完整（幂等/退出码/commit 消息定稿）；GaiAdapter 表头驱动列位感知已存在 |
| ④ S3（mem_sync 引擎） | scripts/mem_sync.py（--source 分发 SOURCES 注册表 / 游标分桶 .pipeline/mem_sync_state.json 原子写 os.replace / MEM_SYNC_MAX_EVENTS=50 / fail-open 恒 exit 0 / work-gated / subprocess memctl 30s 超时，~200 行）4 轮；mem_sync.sh 薄包装 0.5 轮；scripts/test_mem_sync.sh（临时 kanban.db fixture + ≥10 断言：建页/游标推进/幂等 3 次/md5 一致/fail-open/work-gated/GAI 状态列）3-4 轮；挂入测试集合 1 轮 → **基准 8-10 轮** | 架构 §3 + §9.2；引擎零 import kanban 表结构（检查清单） |
| ⑤ S4+S5（close.sh + 冒烟） | close.sh repo 正本改（L19 GAI_FILE 新路径 + L104-106 S3b 状态列替换调 --set-status）1.5 轮；bash -n + 既有 close.sh 相关回归 1 轮；真实链路冒烟（建卡→wiki 页 / done→GAI 状态列，A9 证据）1.5 轮 → **基准 3-5 轮** | 架构 §5.2/§9.3；close.sh 是部署耦合 must-sync 脚本，改 repo 正本即可，部署留 OC（DPL-048） |

**基准轮数（未校准，合计）：31-41 轮。**
**DPL-018 校准：基准 × K=3.00 → 校准后 93-123 轮**（远超 42 有效轮单卡预算 → 必须多卡拆分）。

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **架构已把契约定到实现级，主体是照搬** | 低 | §2 SQL/映射表/签名/退出码全部定稿，含 12 项 D1-D12 裁决；研发主要风险是细节遗漏而非设计决策 |
| R2 cli.py 1736 行提取 kanban 辅助函数 | 中 | _kanban_read_full/_kanban_epoch_to_iso/_kanban_extract_task_code/_kanban_priority_mapping 被 cmd_add_task 等引用；提取为 kanban_db.py 后 cli.py 改 import，**必须全量 pytest 回归确认无行为漂移**（SUB-1 收尾 + SUB-2 全量回归双保险） |
| R3 新 fixture 建设（kanban.db 临时库） | 中 | mem-core conftest 目前只有 wiki/mem_meta fixture，无 kanban.db 模拟；SUB-2/SUB-4 都要建（SUB-4 在 devPPL 侧建 shell fixture）。两处独立建设，不共享代码但模式同源（golden 样本模式） |
| R4 幂等语义依赖 memctl 既有命令 | 中 | add exit1 / done --check / demote 已 blocked 跳过 / note 已 active 跳过——需逐一实测确认语义（架构 D8 已按既有语义设计，但 S1 落地时要以真实 memctl 行为为准，可能发现语义缺口需小修） |
| R5 close.sh 部署耦合 | 低 | repo 正本改完 md5 必与 live 不一致 → deploy-drift hook 报 drift 属**预期**；部署动作留 OC（DPL-048）。验收 A7 在 OC 部署后做，本卡只交 repo 正本 |
| R6 50 事件/tick → 50 commits 洪泛 | 低 | 命令级幂等多数 skip；近 2 天 2740 条 ≈ 2/tick；若实测过多 SUB-4 加 --no-commit 批提交模式（架构风险 2 已列，不阻塞） |
| R7 两仓并行 worker 冲突 | 低 | 拆 5 张串行（同 repo 不同卡不并行），避免 DPL-026/027 同仓写冲突教训；SUB-2/SUB-3 理论上文件不重叠（tests/ vs gailinks+cli）可并行，但默认串行更稳 |
| R8 幻影父卡 t_est_d3fa0933 | 高（流程） | **OC 已建 D1 卡 t_d3fa0933（S1+S2 范围），但其 parents 含 t_est_d3fa0933 = BAD_ID（不存在）→ 该卡永远无法 ready。** 本评估建议更细拆分（5 卡）后，t_d3fa0933 范围被 SUB-1/SUB-2/SUB-3 吸收，**建议 OC 将 t_d3fa0933 标记 SUPERSEDED 关闭**，避免与 autopilot 按 [SUB-SPLIT] 新建的 5 张子卡重复/冲突 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 31-41 轮（中位 36） |
| DPL-018 校准后 | 93-123 轮（×K=3.00）**远 > 20 轮阈值 → 必须拆卡** |
| 交付物数 | 5 个（adapter / pytest / set-status / 引擎+集成测试 / close.sh+冒烟）≥ 4 → 按规则拆 ~3-5 卡 |
| 架构 2 卡方案复算 | D1=mem-core(S1+S2) 基准 18-25 → 校准 54-75 ❌；D2=devPPL(S3+S4+S5) 基准 14-18 → 校准 42-54 ❌ —— **双双超 42 有效轮，照搬会重蹈 t_8458422f/t_e33936c6 超时** |
| 本评估 5 卡方案 | 每张基准 3-10 轮 → 校准 9-30 轮，全部落在单会话 42 有效轮预算内 ✅ |
| 依赖方向 | SUB-2 断言 SUB-1 的 adapter 行为；SUB-3 改 cli.py（SUB-1 也改 cli.py import）→ 等 SUB-1；SUB-4 引擎依赖 SOURCES 注册（SUB-1）+ adapter 在真实 memctl 下行为；SUB-5 依赖 --set-status（SUB-3）+ 引擎（SUB-4） |
| 并行收益 | 低-中——SUB-2/SUB-3 文件不重叠可并行（同仓风险 R7），其余天然串行；默认全串行最稳 |
| 兜底 | 每张子卡独立验收闭环：SUB-1 交 adapter 机制 + 冒烟；SUB-2 交 12 用例全绿；SUB-3 交 --set-status 幂等绿；SUB-4 交引擎 + ≥10 断言；SUB-5 交 close.sh 正本 + A9 证据。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 5 张串行子卡（[SUB-SPLIT] 5 serial）。**
量级参照：t_2dfec09c/t_04cc55a5（S1 机制 / S2 测试 双卡模式，DPL-050/051 实证成功）；
t_ddc6940c（2 文件 + 4 fixture → 拆 2 serial）。本任务跨 2 仓 12 文件 5 交付物，粒度必须更细。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 5 serial
1. [DEV-SUB-1] mem-core S1 机制 — kanban adapter（base.py 加 initial_cursor/command_for 可选方法；
   kanban_db.py 新建共享模块（从 cli.py 提取 _kanban_read_full/_kanban_epoch_to_iso/_kanban_extract_task_code，
   cli.py 改 import 复用，单一实现 D9）；sources/kanban.py 新建 adapter（fetch_events 白名单 SQL
   created/completed/blocked/unblocked→create/done/demote/update + mode=ro 只读 + map_id + mirror_status +
   command_for 返回 memctl argv + initial_cursor→MAX(id)）；sources/__init__.py 注册 SOURCES["kanban"]；
   冒烟 2-3 断言（归一化/白名单/mode=ro 写拒绝）；mem-core pytest 回归确认 cli.py 重构无漂移）
   预计 24-30 轮（基准 8-10 × K=3.00）
2. [DEV-SUB-2] mem-core S1 测试 — test_sources_kanban.py 12 用例全量（conftest 新建 kanban.db 临时库 fixture：
   4 类 task_events + tasks 行；断言 归一化/白名单忽略 claimed+spawned+heartbeat/增量 since/上限 50/
   只读 OperationalError/map_id 编号+回退/mirror 映射/command_for 4 类 argv）+ mem-core pytest 全量回归
   预计 18-24 轮（基准 6-8 × K=3.00）
3. [DEV-SUB-3] mem-core S2 — gai-links --set-status（gailinks.py 新增 set_gai_status：表头驱动定位
   「状态」列 _STATUS_HEADERS + 行定位 + t_xxx 经 mem_meta.db pages.source_task 反查 + 幂等已 done 不写 +
   整文件原子改写保留双链；cli.py 接线 --set-status <ID> <done|active> [--no-commit] 退出码 0/1/2/3 +
   _maintenance + _git_commit "mem(gai): set-status <ID> done"）+ test_gai_set_status.py 4 用例
   （幂等/列位感知/t_xxx 反查/坏行 exit 3）+ 回归
   预计 18-24 轮（基准 6-8 × K=3.00）
4. [DEV-SUB-4] devPPL S3 — mem_sync 引擎（scripts/mem_sync.py：--source 经 memcore.sources.SOURCES 分发 /
   游标分桶 .pipeline/mem_sync_state.json temp+os.replace 原子写 / 首跑 initial_cursor→MAX(id) 不处理历史 /
   MEM_SYNC_MAX_EVENTS=50 / fail-open 恒 exit 0 / work-gated 无新事件零 memctl / subprocess memctl 30s 超时 /
   日志含 source 字段；scripts/mem_sync.sh 薄包装 notify_cron 模式；scripts/test_mem_sync.sh ≥10 断言：
   建页/游标推进/幂等 3 次页数不变/kanban.db md5 前后一致/fail-open memctl 缺失 exit 0/work-gated/GAI 状态列）
   预计 24-30 轮（基准 8-10 × K=3.00）
5. [DEV-SUB-5] devPPL S4+S5 — close.sh S3b 修复 + 集成冒烟（scripts/close.sh repo 正本：L19 GAI_FILE
   换 /workspace/mem-core/gai/GLOBAL_ACTION_ITEMS.md + L104-106 S3b 从行尾 ✅ done 改为调
   memctl gai-links --set-status "$TASK_ID" done（check/fix 同一命令天然幂等）；bash -n + 既有回归；
   真实链路冒烟 A9：建卡→wiki 页生成 / done→mem_meta.db events done + GAI MEM-007 状态列 done；
   部署动作留 OC，本卡只交 repo 正本）
   预计 9-15 轮（基准 3-5 × K=3.00）
```

- SPLIT: yes（count=5，校准后 93-123 轮远超 20）
- MODE: serial（SUB-2 依赖 SUB-1 adapter 行为；SUB-3 与 SUB-1 同改 cli.py 需串行；SUB-4 依赖注册表；SUB-5 依赖 SUB-3+SUB-4）
- ROUNDS_EST（校准后）: 93-123（基准 31-41 × K=3.00；分卡后每张 9-30）
- FILES: mem-core 8 文件 + devPPL 4 文件（架构 §11.1 清单）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 5 张子卡挂本卡）
- TESTS: SUB-1 pytest 回归 + 冒烟 2-3；SUB-2 12 用例全绿；SUB-3 4 用例全绿；SUB-4 ≥10 断言；SUB-5 bash -n + A9 证据
- RISK: R2 cli.py 提取回归漂移（SUB-1/SUB-2 双保险）；R3 两处 kanban.db fixture 独立建设；
  R4 memctl 既有幂等语义需实测确认；R8 幻影父卡 t_est_d3fa0933 阻塞 t_d3fa0933 → 建议 OC SUPERSEDED 关闭
- ACTION: build_five_dev_cards（assignee=game-engine，parents=[t_2ba7e58f]，serial）

## 6. 备注

1. **幻影父卡告警**：OC 已建的 t_d3fa0933（D1=S1+S2）parents 含 t_est_d3fa0933（BAD_ID，实测确认不存在）
   → 该卡永远无法 ready。且本评估建议 5 卡拆分已覆盖其范围。**请 OC 将 t_d3fa0933 标记 SUPERSEDED 关闭**，
   避免 autopilot 按本 [SUB-SPLIT] 新建 5 张子卡后出现重复/冲突卡。
2. 架构 §12 的 2 卡建议基于人时估算（~10.5h），未过 DPL-018 轮数校准；本评估按轮数口径复算后必须 5 卡。
3. cron 注册（root crontab 行直调 repo 路径）不在任何 dev 卡内，属 OC 部署动作（D12，DPL-048 铁律）。
4. SUB-4 引擎依赖 memctl 真实语义（R4），若 S1 阶段发现 memctl 幂等语义缺口，SUB-4 的 test_mem_sync.sh
   断言需同步小修——不影响拆分结构。
