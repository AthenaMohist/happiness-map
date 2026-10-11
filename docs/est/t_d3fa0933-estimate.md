# 评估报告 — [DEV] MEM-007 S1+S2 — kanban adapter + gai-links --set-status（mem-core，蓝图第一环）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_d3fa0933
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_d3fa0933（[DEV] MEM-007 S1+S2 — kanban adapter + gai-links --set-status（mem-core，蓝图第一环））
> 来源：arch c819afc §2/§4/§9/§11 + PRD v2.0 2136345；源卡链 t_33c634a1 → t_6ed31c9a → t_e5918369 → D1(本卡) → D2(devPPL 侧)
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 4 张串行子卡（校准后预计 81-111 轮 ≫ 20 轮阈值）。**

任务按自然边界拆 4 张：S1 机制（base.py + kanban_db.py + sources/kanban.py 落地，验收 1/2/3
机制侧）→ S1 测试（test_sources_kanban.py 12 用例 + 既有回归，验收 2/3 测试侧）→ S2
（gailinks.set_gai_status + cli --set-status + 4 用例，验收 4）→ 回归 + 落地（全量 pytest +
merge mem-core main + claim，验收 5/6）。S1/S2 均改 cli.py（S1 改 import、S2 加 --set-status
参数）→ 同文件双改，串行防冲突。每张子卡 12-39 校准轮，均在单会话可控区间（42 有效轮）。

## 2. 工作量评估（读码结论，非假设）

### 2.1 现状基线（实测）

- **mem-core repo**：main 分支，188 个 pytest 用例收集（test_cli 22 / test_gai 13 / test_v2 36 /
  test_parse 14 / test_query 9 / test_seq 4 等）。改动后新增 ~16 用例 → 全量 ~204。
- **base.py**（41 行）：SourceAdapter 抽象已有 fetch_events/map_id/mirror_status 三方法；
  缺 initial_cursor/command_for（arch §2.5 代码块直接可抄，~15 行）。
- **cli.py**（1736 行）：已有 `_kanban_read`(L89)/`_kanban_read_full`(L122)/`_kanban_epoch_to_iso`(L178)/
  `_kanban_extract_task_code`(L210) 四个 L0 只读助手；cmd_gai_links(L1284) 已实现 check/fix 分支；
  argparse gai-links parser(L1671) 已注册 `--fix`/`--no-commit`。退出码常量 EXIT_OK=0/ERR=1/USAGE=2。
- **gailinks.py**（117 行）：check_gai_links/fix_gai_links 已有，复用 GaiAdapter（表头驱动列位感知）。
- **sources/gai.py**（111 行）：表头驱动解析已实现（_TASK_ID_HEADERS=("任务ID","ID")）；
  无「状态」列感知 —— S2 需扩展（arch §4.2 新增 _STATUS_HEADERS=("状态",)）。
- **schema.py**：ENV_KANBAN_DB/DEFAULT_KANBAN_DB/CARD_CODE_RE 已存在。
- **GAI 文件**（/workspace/mem-core/gai/GLOBAL_ACTION_ITEMS.md）：实测表头
  `| 优先级 | 任务ID | 行动 | 状态 | 机制 | 工时 |`，行含 `[[ID]]` 双链 + active/done 状态列 ——
  S2 状态列替换的目标格式已确认存在。
- **mem_meta.db pages**：indexer.py L168 `source_task TEXT` 列已建，S2 t_xxx 反查有落点。
- **kanban.db task_events schema/kind 分布**：arch t_e5918369 实测（20+ kind，MAX(id)=10915）
  —— adapter SQL 白名单四类（created/completed/blocked/unblocked）与 tasks LEFT JOIN 可行。
- **tests/conftest.py**：有 wiki_root/db_path/wiki_env 夹具，**无 kanban.db 临时库夹具、无 git
  repo 夹具** —— S1/S2 测试需新增（临时 kanban.db 建 tasks+task_events 表 + 插行；S2 需 tmp git
  repo 供「无 git diff」断言）。

### 2.2 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 上下文 | 读 arch §2/§4/§9/§11 + memcore base.py/gai.py/__init__.py/schema.py + cli.py kanban 助手 + conftest | 2-3 |
| ② | base.py 扩展 | + initial_cursor()/command_for() 两可选方法（arch §2.5 代码块，默认 None，gai.py 零改动） | 1 |
| ③ | kanban_db.py 提取 | 从 cli.py 迁 _kanban_extract_task_code/_kanban_read_full/_kanban_epoch_to_iso（+kanban_read_task 适配）→ cli.py 6 处调用改 import 复用（L257/300/313/318 等），test_cli 22 用例回归 | 2-3 |
| ④ | sources/kanban.py | ~180 行：fetch_events 白名单 SQL（mode=ro URI + LIMIT MEM_SYNC_MAX_EVENTS）+ Event 构造 + map_id + mirror_status + command_for + initial_cursor（arch §2.1/2.2 代码块为主 + 助手函数 _json_loads/_event_title/_event_status/_event_detail） | 3-4 |
| ⑤ | sources/__init__.py | SOURCES["kanban"] = KanbanAdapter() 注册 | 0.5 |
| ⑥ | test_sources_kanban.py | 12 用例（§9.1 表：归一化4kind/白名单忽略/增量/上限50/只读/map_id编号+回退/mirror映射/command_for）+ 新增临时 kanban.db 夹具（tasks+task_events 建表插行，md5 前后比对） | 5-7 |
| ⑦ | 局部回归 | S1 改完跑 mem-core 既有 188 用例确认无回归 | 1-2 |
| ⑧ | S2 上下文 | 读 arch §4 + gailinks.py + cli.py cmd_gai_links/argparse + GAI 文件实样 | 1-2 |
| ⑨ | gailinks.set_gai_status | ~80-120 行：状态列表头感知（_STATUS_HEADERS 扩展，不破坏 GaiAdapter 既有解析）、t_xxx 反查（mem_meta.db pages.source_task）、状态列替换保留其余单元格与 [[ID]]、原子写 + _maintenance + _git_commit("mem(gai): set-status <ID> done")、坏行 exit 3、幂等 | 3-4 |
| ⑩ | cli.py --set-status | gai-links parser 加 --set-status <ID> <done\|active> [--no-commit]、cmd_gai_links 分发、退出码 0/1/2/3 | 1-2 |
| ⑪ | test_gai_set_status.py | 4 用例（幂等/列感知保留双链/t_xxx 反查/坏行 exit 3）+ 夹具（tmp GAI 状态列文件 + tmp git repo + mem_meta pages.source_task） | 3-4 |
| ⑫ | 全量回归 + 落地 | 全量 pytest ~204 全绿 + merge mem-core main（commit 引用卡 ID）+ worktree 无残留 + claim + 飞书 + complete | 4-6 |

**预计总轮数（基准，未校准）：25-37 轮（中位 31）。**

### 2.3 分卡后每卡轮数

| 子卡 | 内容 | 基准轮数 | DPL-018 校准（×K=3.00） |
|------|------|:---:|:---:|
| SUB-1 | S1 机制：base.py + kanban_db.py 提取 + sources/kanban.py + SOURCES 注册 + cli.py import 复用 | 8-10 | 24-30 |
| SUB-2 | S1 测试：test_sources_kanban.py 12 用例 + 夹具 + 既有 188 回归 | 6-8 | 18-24 |
| SUB-3 | S2：gailinks.set_gai_status + cli --set-status + test_gai_set_status 4 用例 | 9-13 | 27-39 |
| SUB-4 | 回归 + 落地：全量 pytest ~204 + merge mem-core main + claim + 飞书 | 4-6 | 12-18 |

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **cli.py kanban 助手迁移回归**（SUB-1 最大风险） | 中 | _kanban_read_full/_kanban_epoch_to_iso/_kanban_extract_task_code 被 G2 建卡采集链（cmd_add --from-kanban）多调用点使用；迁到 kanban_db.py 后必须全量跑 test_cli 22 用例 + 手动冒烟 add --from-kanban，否则 G2 链静默降级。缓解：迁移只搬函数体不改语义 + import 别名兼容 + SUB-1 局部回归 |
| R2 kanban.db schema 漂移 | 低-中 | adapter SQL 依赖 task_events(id/kind/payload/created_at/task_id) + tasks(title/status) 列名；arch 已实测 schema 但实现时用 mode=ro + SELECT 白名单列，缺失列 fail-open 返回 []，不崩 |
| R3 S2 状态列表头变体 | 中 | GAI 有 4 类表头（待办/P5/OBS/归档），只有「待办」变体有状态列；无状态列文件必须 exit 3 不误改（验收 4）。同时扩展表头解析不能破坏 GaiAdapter 既有 fetch_events（test_gai 13 用例回归） |
| R4 t_xxx 反查依赖 mem_meta.db | 低-中 | pages.source_task 列已建，但反查需确认 indexer 确实写入该列（L97 实测写入）。无反查结果 → exit 0 幂等跳过（契约已定） |
| R5 测试夹具新基建 | 中 | conftest 无 kanban.db 临时库夹具（需建 tasks+task_events+task_links+task_comments 表并插行）与 git repo 夹具（S2「无 git diff」断言需 tmp git init）。夹具本身 ~1-2 轮，复用性高（D2 引擎测试可复用） |
| R6 GAI 文件真实提交 | 低 | --set-status 会在 /workspace/mem-core repo 产生 commit（wiki.parent 即 repo）；测试用 tmp 隔离，真实链路验证放 SUB-4 冒烟即可 |
| R7 mode=ro 并发 | 低 | SQLite mode=ro URI 只读并发安全（notify_check 先例，arch 风险 6）；测试断言 INSERT 抛 OperationalError（§2.6 A5） |
| R8 归档/坏行容错 | 低-中 | fetch_events 白名单外 20+ kind 忽略（arch §2.2）；S2 坏行 exit 3 指明行——实现时注意「行定位」与「行损坏」区分（契约 1/3 退出码） |

**关键决策点（实现时拍板，不改轮数量级）**：D1 kanban_db.py 导出命名（kanban_read_task vs
kanban_read_full，arch §2.3 引用 kanban_read_task —— 建议 kanban_db.py 提供
kanban_read_task = 现 _kanban_read_full 的窄化版，cli.py 保留别名兼容）；D2 状态列空值语义
（空单元格 = active？不写？—— 契约只定 done/active 白名单，空值按 active 处理即可）；
D3 --set-status 参数形态（`--set-status <ID> <status>` 双位置参数 vs 子命令 —— 按 arch §4.1
双位置参数 + --no-commit flag）。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 25-37 轮（中位 31） |
| DPL-018 校准后 | 75-111 轮（×K=3.00，中位 93）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（adapter 机制）→ S2（--set-status 独立功能）弱依赖（无代码依赖，但 cli.py 同文件）；SUB-2 依赖 SUB-1 机制在 main 上；SUB-4 依赖前 3 卡 merge 完成 |
| 并行收益 | 低——S1/S2 均改 cli.py（import vs argparse 不同区但同文件），并行有冲突风险；测试卡必须等机制卡 merge |
| 兜底 | 每张子卡独立验收闭环：SUB-1 交付机制（验收 1/2/3 机制侧可验）；SUB-2 交付 12 用例（验收 2/3 测试侧）；SUB-3 交付 --set-status（验收 4 可验）；SUB-4 交付全量回归 + merge（验收 5/6）。任一卡超预算，已完成卡可先 merge 不阻塞 |

**决策：拆 4 张串行子卡（[SUB-SPLIT] 4 serial）。** 量级参照：t_74963b5d（17-26 轮 →
拆 3 serial）；本卡 25-37 轮 + 双功能 + 双夹具新基建 → 拆 4。S1 机制与 S1 测试分离
（DPL-048 链先例：t_04cc55a5 机制 / t_c29ae232 测试+回归+落地 分卡），S2 与回归落地分离
（回归含全量 204 用例 + merge，独立成卡可单独验收 5/6）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 4 serial
1. [DEV-SUB-1] S1 机制 — base.py 扩展 + kanban_db.py 提取 + sources/kanban.py + SOURCES 注册
   （base.py + initial_cursor()/command_for()（arch §2.5 默认 None，gai.py 零改动）；
    kanban_db.py 迁 _kanban_extract_task_code/_kanban_read_full/_kanban_epoch_to_iso（+kanban_read_task
    窄化版）→ cli.py 6 处调用改 import 复用（L257/300/313/318 等，别名兼容防 G2 链回归）；
    sources/kanban.py ~180 行（fetch_events 白名单 SQL mode=ro URI + LIMIT MEM_SYNC_MAX_EVENTS、
    map_id 复用 kanban_extract_task_code、mirror_status 只读、command_for 返回 memctl argv、
    initial_cursor → str(MAX(id))）；sources/__init__.py 注册 SOURCES["kanban"]；
    回归 mem-core 既有 188 用例全绿） 预计 8-10 轮（校准 24-30）
2. [DEV-SUB-2] S1 测试 — test_sources_kanban.py 12 用例 + 临时 kanban.db 夹具
   （新增 conftest kanban_db fixture：tasks+task_events+task_links+task_comments 建表插行；
    §9.1 12 用例：归一化4kind（created/completed/blocked/unblocked → create/done/demote/update +
    meta.event_id）/ 白名单忽略（claimed/spawned/heartbeat 不产出）/ 增量（since=N → id>N，空 since → []）/
    上限（60 条 → 50）/ 只读（mode=ro INSERT → OperationalError + db md5 前后一致）/ map_id 编号+
    回退（MEM-007 → "MEM-007"；无编号 → t_xxx）/ mirror 映射（done→done/blocked→blocked/ready→active/
    读失败→None）/ command_for（4 kind → argv 含 --from-kanban/--collect-notes/--status）；
    既有 188 用例回归） 预计 6-8 轮（校准 18-24）
3. [DEV-SUB-3] S2 — gailinks.set_gai_status + cli --set-status + test_gai_set_status 4 用例
   （gailinks.py + set_gai_status：_STATUS_HEADERS=("状态",) 扩展表头解析（不破坏 GaiAdapter 既有
    fetch_events，test_gai 13 回归）、t_xxx 反查 mem_meta.db pages.source_task、状态列替换保留
    其余单元格与 [[ID]] 双链、原子写 + _maintenance + _git_commit("mem(gai): set-status <ID> done")、
    坏行 exit 3 指明行、幂等（已 done 不写无 diff exit 0）、GAI 缺失 exit 0 fail-open；
    cli.py gai-links parser + --set-status <ID> <done|active> [--no-commit] + 退出码 0/1/2/3；
    test_gai_set_status.py 4 用例（幂等/列感知保留双链/t_xxx 反查/坏行 exit 3）+ tmp git repo 夹具）
    预计 9-13 轮（校准 27-39）
4. [DEV-SUB-4] 回归 + 落地 — 全量 pytest ~204 + merge mem-core main + claim + 飞书
   （全量 pytest（既有 188 + 新增 16）全绿；merge commit 引用本卡 ID；worktree 无残留；
    claim 输出结构化 report（changed_files/tests_run/verification）供 VA；飞书推送；
    complete） 预计 4-6 轮（校准 12-18）
```

- SPLIT: yes（count=4，校准后 81-111 轮远超 20）
- MODE: serial（S1 测试依赖 S1 机制 merge；S2/S4 依次依赖前一卡；cli.py 同文件防并行冲突）
- ROUNDS_EST（校准后）: 93（基准 31 × K=3.00）
- FILES: SUB-1 改 memcore/sources/base.py + 新增 memcore/kanban_db.py + 新增 memcore/sources/kanban.py + 改 memcore/sources/__init__.py + 改 memcore/cli.py（import）；SUB-2 新增 tests/test_sources_kanban.py + 改 tests/conftest.py（kanban fixture）；SUB-3 改 memcore/gailinks.py + memcore/cli.py（--set-status）+ 新增 tests/test_gai_set_status.py；SUB-4 无新代码（回归 + merge）
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 4 张子卡挂 t_d3fa0933）
- TESTS: SUB-1 回归 188；SUB-2 新增 12 用例 + 回归 188；SUB-3 新增 4 用例 + test_gai 13 回归；SUB-4 全量 ~204
- RISK: R1 cli.py 助手迁移回归（别名兼容 + 局部回归）；R2 kanban schema 漂移（mode=ro fail-open）；R3 状态列表头变体（无状态列 exit 3 不误改）；R4 t_xxx 反查（pages.source_task 已写入实测）；R5 测试夹具新基建（kanban 临时库 + tmp git）；D1-D3 实现时拍板
- ACTION: build_four_dev_cards（assignee=game-engine，parents=[t_d3fa0933]，serial）

## 6. 备注

- **arch §2/§4 提供了大部分代码骨架**（base.py 扩展、kanban.py fetch_events SQL、command_for 映射表、
  --set-status 契约）——实现多为「照 arch 落码 + 补助手函数 + 写测试」，轮数已按此打折；
  若某卡实际更轻，SUB-4 可吸收余量（回归 + merge 兜底）。
- **D1 决策点**：kanban_db.py 导出命名（kanban_read_task 窄化版，cli.py 别名兼容）——
  影响 SUB-1 与 SUB-3（t_xxx 反查走 mem_meta.db 不依赖 kanban_db，无跨卡耦合）。
- **GAI 文件已带状态列**（实测 `| 优先级 | 任务ID | 行动 | 状态 | 机制 | 工时 |`）——
  S2 直接改这一列，不是加列，行尾 ✅ done 方案（close.sh 旧 S3b）已被 arch §5 弃用。
- **close.sh S3b / mem_sync.py 是 D2 范围**（devPPL 侧，t_04cc55a5 之后建），本卡不碰。
- 每张子卡完成后推飞书（send_claim_feishu.py，SOUL 5.1 硬性要求）。
- 本评估卡自身产物（本文件）留在 wt/t_est_d3fa0933 分支，由 OC/merge 链决定合入 devPPL main
  （评估卡不写代码，但产物不能悬空——不犯它评估的错）。
- 校准口径说明：K=3.00 沿用 DPL-018（t_e33936c6 病例，后续 08-15 全部估计同口径）。
