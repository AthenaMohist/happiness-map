# 评估报告 — [FIX] 非管线任务 GAI 状态列不自动更新 — done 后 GAI 仍 active（DPL-059）

> 评估人：寇豆码（game-engine） | 日期：2026-08-15 | 评估卡：t_est_127ed037
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：t_127ed037（[FIX] 非管线任务 GAI 状态列不自动更新 — done 后 GAI 仍 active，DPL-059）
> 来源：ALV-006 端到端流程测试（t_e8a312a0，2026-08-15）暴露的衔接盲区
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 3 张串行子卡（校准后预计 69-100 轮 > 20 轮阈值）。**

缺陷真实：非管线任务（CMD 直执 / 纯 OS 操作 / 无 close.sh 兜底）done 后，
wiki 页与 mem_meta 由 mem_sync 自动更新，但 **GAI 状态列保持 active** → 与真实状态漂移。
Frank 2026-08-15 裁定「都做」→ **方案 A（done 事件自动同步 GAI）+ 方案 B（漂移收尾扫描）双落地**，
验收标准 2/3 明确要「任一非管线任务 done → GAI 自动 done」+「管线任务（close.sh）回归不变」。

本卡表面是「done 分支加一行」，实际是**双仓改动 + D10 架构裁决修订 + 双仓回归 + live 观察**：
- 方案 A 需要修订 MEM-007 架构 D10「不在 command_for 叠加」裁决（写入 arch 文档 repo 正本）；
- 方案 B 是**新增漂移扫描组件**（非一行改动：kanban 只读扫描 + GAI 状态比对 + 幂等 set-status + work-gated/fail-open + 日志）；
- 验收含 **live 观察**（真实非管线任务 done → GAI done，或构造场景 + 阴性观察）与**双仓全量 pytest**。

## 2. 工作量评估（读码结论 + 实测，非假设）

### 2.1 缺陷链路（实测定位）

```
非管线任务（如 ALV-006, [CMD] t_e8a312a0）done
  → kanban.db task_events kind='completed'
  → mem_sync.py run_tick (cron */2min)  →  adapter.command_for(ev, page_id)
      done → ["memctl","done",page_id,"--result",detail,"--collect-notes"]   # kanban.py L204-209
  → memctl done → wiki/actions/<page_id>.md status=done ✅（已验证自动）
  → mem_meta.db events done ✅（memctl _log_append 内部）
  → GAI 状态列 ❌ 不动 —— D10 规定 GAI 由 close.sh S3b / memctl gai-links --set-status 处理，
      但非管线任务不走 close.sh 链 → 无人写 GAI → 需人工 `memctl gai-links --set-status <ID> done` 补
```

- 实测证据：ALV-006 卡（t_e8a312a0）done 后 OC 人工补 set-status；GAI 文件 P3-02 ALV-006 现为 done。
- close.sh S3b（repo 正本 L105-107）已正确调 `memctl gai-links --set-status "$TASK_ID" done`，幂等；
  **close.sh 无需改**（本次不动，部署面零新增）。缺陷纯粹是「非管线任务无 close.sh 兜底」。
- 架构裁决原文：arch-mem007-auto-record-maintenance.md D10/D11 + §2.2 注「done 时 GAI 状态列由
  close.sh S3b / memctl --set-status 处理，不在 command_for 内叠加（避免 mem_sync 双写面）」。
- 基础设施现状：mem_sync.sh cron 已注册（`*/2 * * * *`，repo 路径直调，零部署耦合，D12）；close.sh
  repo 与 live md5 一致（2a7f11a3…，must-sync 清单）。

### 2.2 方案评估（Frank「都做」→ A + B 双落地）

| 方案 | 内容 | 实现点 | 风险 |
|------|------|--------|------|
| **A**（推荐实现） | done 事件自动同步 GAI：`memctl done` 增 `--sync-gai` flag（cmd_done 内部调 gailinks.set_gai_status，fail-open），kanban.py command_for done 分支追加 flag | mem-core: cli.py cmd_done + gailinks 复用（set_gai_status 已存在）+ sources/kanban.py command_for + pytest | 双写面：close.sh S3b 与 memctl done --sync-gai 都写 GAI → **幂等**（已 done 不写）→ 无害；D10 修订需产品/架构确认 |
| **B** | 非管线任务收尾检查：新增漂移扫描（mem_sync --reconcile-gai 模式或独立 sweep 脚本）——扫描 kanban.db status=done 任务 → GAI 状态列 active → 自动 set-status done | devPPL: 新 sweep（复用 memcore.kanban_db 只读 helper + memctl gai-links --set-status）+ work-gated + fail-open + 日志 + test_mem_sync.sh 场景 | 覆盖历史漂移 + 未来漏网；新组件需测试；cron 注册走 repo 路径直调（D12 先例，零部署） |
| C | 其他 | — | — |

**推荐 A 实现 = memctl done --sync-gai（单命令单写入者）**：
- mem_sync 仍只调 memctl 一次（1 event → 1 command），引擎零改动，遵守「mem_sync 只调 memctl」；
- GAI 写入仍收编在 memctl 内（cmd_done 内部调 gailinks.set_gai_status），单一写入者铁律不变；
- close.sh S3b 的 `gai-links --set-status` 与 `done --sync-gai` 双覆盖 → 幂等（已 done 不写文件不 commit）→ 无害；
- D10 修订 = arch 文档 §2.2 注改写 + D10 行更新（「--sync-gai 显式 flag 叠加，非无条件双命令」），研发职责内 repo 正本文档改动。

**方案 B = 漂移扫描**（Frank「都做」的收尾兜底）：
- 兜住历史漂移（ALV-006 类已 done 但 GAI active 的存量）+ close.sh 漏跑/失败场景；
- 实现：kanban_db.py 已有 kanban_read_task / kanban_extract_task_code 只读 helper；新增 list-done
  查询（或复用 adapter fetch + 过滤）+ gailinks.set_gai_status 幂等写入；work-gated（无 done 任务零 memctl）
  + fail-open（读失败/无 GAI 行跳过）+ 日志行。

### 2.3 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | 设计决策 | D10 修订确认（A 的 flag 语义 + fail-open 范围）+ B 扫描机制定稿（mem_sync 模式 vs 独立脚本）+ Frank「都做」范围落地 | 3-4 |
| ② | mem-core 方案 A | cli.py cmd_done 增 `--sync-gai`（内部调 gailinks.set_gai_status，catch ValueError 表头无状态列 → log 不阻断 done）+ sources/kanban.py command_for done 追加 flag | 4-6 |
| ③ | mem-core pytest | cmd_done --sync-gai 幂等（已 done 不写）/ 无 GAI 行 skip / 表头变体 fail-open / t_xxx 反查 + command_for argv 含 --sync-gai | 3-4 |
| ④ | devPPL 方案 B | sweep：kanban_db list-done 只读 + GAI 状态列比对 + memctl set-status 幂等 + work-gated + fail-open + 日志（或 mem_sync --reconcile-gai 模式）；cron 注记（注册留 OC） | 5-7 |
| ⑤ | 集成测试 | test_mem_sync.sh 新增：done 事件 → GAI 状态列 done 断言（方案 A）；预置 done-but-active 任务 → sweep 补齐（方案 B）；close.sh S3b 回归不变 | 4-5 |
| ⑥ | 回归 + live + 落地 | devPPL 全量 pytest（~10min 后台，基线 281/8/1 无新增）+ mem-core pytest 全量 + test_mem_sync.sh 全绿 + live 观察（构造非管线任务 done → GAI done，或 ALV-006 类已修复样本阴性观察 + cron 2min×N 等待）+ 双仓 merge 进 main + claim/飞书/complete | 6-9 |

**基准轮数（未校准）：25-35 轮（中位 30）。**
**DPL-018 校准：基准 × K=2.86（同型 DPL-058 双仓修复先例，t_cd3c6d57 实证）→ 校准后 72-100 轮（中位 86）> 20 轮阈值 → 必须拆卡。**

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **D10 架构裁决修订** | **中** | 方案 A 需修订 arch-mem007 §2.2 注 + D10 行（「--sync-gai 显式 flag 叠加」替代「不在 command_for 叠加」）。研发职责内改 repo 正本文档即可，但语义变化需在评估/实现时显式声明；close.sh 不动 → 部署面零新增（md5 已一致） |
| R2 双写面（memctl done --sync-gai vs close.sh S3b） | 低 | 两写者都是 memctl 内部 gailinks.set_gai_status，幂等（状态列已 done → 不写文件不 commit）；close.sh S3b 对管线任务仍正常通过（check 幂等 exit 0）。需测试覆盖「管线任务 done → close.sh S3b 仍 PASS」 |
| R3 表头无「状态」列变体（P5/OBS/归档） | 中 | set_gai_status 对无状态列表 → ValueError → cli exit 3。cmd_done --sync-gai **必须 catch 并 fail-open**（log 后继续 done 成功），否则 done 事件被 GAI 格式问题拖垮 —— 实现关键点，测试必覆盖 |
| R4 t_xxx 反查失败（无 mem_meta 页） | 低 | set_gai_status 已处理（skip fail-open exit 0），非所有 kanban 任务有 GAI 行 |
| R5 GAI 文件缺失 | 低 | 已有 fail-open（skip exit 0） |
| R6 全量 pytest 存量失败 | 低 | devPPL 基线 281 passed / 8 failed / 1 error（DPL-057 实测，621s），8+1 全存量；只做「无新增」对照；mem-core 基线 220 passed，需 MEM_CORE_PATH 指向修复后 mem-core |
| R7 live 观察为构造/阴性 | 低-中 | 修复后真实日志不再自然复现（游标已越过，ALV-006 已人工补 done）；验证 = 测试阳性断言（构造非管线 done 卡 → GAI done）+ live 阴性观察（cron 2min×3 无「GAI active 残留」）。等待 ~6min 不占轮数（后台/间歇轮询） |
| R8 sweep 与 mem_sync 并发写 GAI | 低 | memctl 是唯一写入者 + set_gai_status 幂等；sweep 可复用 mem_sync 游标/日志模式，或独立脚本错峰（cron 同频 2min 无冲突） |

**关键决策点（S1/S2 实现时拍板，不改变轮数量级）**：
D1 方案 A 实现位：memctl done --sync-gai（推荐，引擎零改动）vs mem_sync run_tick 二次调用（改引擎，双命令）——推荐前者；
D2 方案 B 载体：mem_sync --reconcile-gai 模式（复用引擎游标/日志，推荐）vs 独立 sweep 脚本（更隔离）；
D3 D10 修订文案：arch 文档 §2.2 注 + D10 行显式声明「--sync-gai flag 叠加（幂等，双覆盖无害）」；
D4 sweep 触发：cron 同频（D12 先例，注册留 OC）vs mem_sync tick 尾部内联。

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 25-35 轮（中位 30） |
| DPL-018 校准后 | 72-100 轮（×K=2.86，中位 86）**> 20 轮阈值 → 必须拆卡** |
| 模块依赖 | S1（mem-core 方案 A）→ S2（devPPL 方案 B + 集成测试，依赖 S1 的 --sync-gai 进 mem-core main）→ S3（双仓回归 + live + 落地）单向依赖，串行 |
| 并行收益 | 低——S2 的 A 路径测试依赖 S1 落地；B 扫描可先行但集成测试要 S1；双仓并行引入接口未就绪风险 |
| 跨仓边界 | S1 纯 mem-core（A 能力 + 单测）；S2 纯 devPPL（B 扫描 + 集成测试，含 A/B 双场景 + close.sh 回归）；S3 双仓收尾 |
| 兜底 | 若 S2 超预算，⑤ 的 A/B 场景可分 commit 交付；S1 独立可验收（cmd_done --sync-gai 单测覆盖） |

**决策：拆 3 张串行子卡。** 单卡 72-100 轮远超 60 轮预算（有效 42 轮），且 R1 架构修订 +
双仓 + 双方案 + live 观察客观是多会话工作量，拆后每张 17-40 轮（校准口径），留足余量。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 3 serial
1. [S1] mem-core 方案 A 能力（mem-core 仓）：cli.py cmd_done 增 --sync-gai（内部调
   gailinks.set_gai_status，catch ValueError 表头无状态列 → log fail-open 不阻断 done）+
   sources/kanban.py command_for done 分支追加 --sync-gai + arch-mem007 §2.2 注/D10 修订
   （repo 正本文档）+ pytest（幂等/无 GAI 行/表头变体/t_xxx 反查/argv 断言）。
   预计校准后 20-29 轮。
2. [S2] devPPL 方案 B 收尾扫描 + 集成测试（devPPL 仓）：新增漂移扫描（mem_sync
   --reconcile-gai 模式或独立 sweep 脚本：kanban_db list-done 只读 + GAI 状态列比对 +
   memctl gai-links --set-status 幂等 + work-gated + fail-open + 日志；cron 注册留 OC）；
   test_mem_sync.sh 新增 A/B 双场景（done → GAI done 断言；预置 done-but-active → sweep
   补齐）+ close.sh S3b 回归不变。依赖：S1 的 --sync-gai 进 mem-core main。
   预计校准后 26-37 轮。
3. [S3] 双仓回归 + live 落地（devPPL + mem-core）：devPPL 全量 pytest（基线 281/8/1 无新增）
   + mem-core pytest 全量 + test_mem_sync.sh 全绿 + live 观察（构造非管线 done 卡 → GAI done
   阳性 / cron 2min×3 阴性）+ 双仓 merge 进 main + claim/飞书/complete。
   依赖：S2 进 devPPL main + S1 进 mem-core main。预计校准后 17-26 轮。
```

- SPLIT: yes（count=3）
- MODE: serial（S1 → S2 → S3，接口依赖链）
- ROUNDS_EST（校准后）: 86（基准 30 × K=2.86）
- FILES: memcore/cli.py, memcore/sources/kanban.py, memcore/gailinks.py（复用，可能零改动）,
  memcore/tests/test_cli.py + test_gai_set_status.py, wiki/projects/devppl/arch/arch-mem007-auto-record-maintenance.md
  （D10/§2.2 修订）, scripts/mem_sync.py（或 scripts/gai_sweep.py）, scripts/test_mem_sync.sh
- STATUS: not_started（源卡 t_127ed037 待 autopilot 建子卡）
- TESTS: mem-core cmd_done --sync-gai 幂等/表头变体/fail-open 用例；test_mem_sync.sh 新增
  A/B 双场景（done→GAI done + sweep 补齐）+ close.sh S3b 回归；devPPL 全量 pytest 281/8/1
  基线对照（无新增）；mem-core pytest 全量；live 构造/阴性观察
- RISK: R1 D10 修订（语义显式声明）；R3 表头无状态列 fail-open（cmd_done 关键点）；R2 双写面
  幂等无害（测试覆盖）；R7 live 观察为构造/阴性；R8 sweep 并发写幂等
- ACTION: build_three_dev_cards（S1/S2/S3 均 assignee=game-engine；S2 parents=[S1]，
  S3 parents=[S2]）

## 6. 备注

- **Frank「都做」裁定**：源卡注明 Frank 2026-08-15 裁定「都做」→ 方案 A + 方案 B 均落地，
  本评估按 A+B 双方案计工作量；若仅做 A，S2 可缩减约 40%（但验收 2 的「经自动收尾流程」仍需
  B 类兜底，不推荐砍）。
- **D10 修订属研发职责**：arch 文档是 repo 正本（/workspace/mem-core/wiki/projects/devppl/arch/），
  不是部署耦合脚本；S1 改文档 + commit 即可，不触发 deploy-drift（.hermes.md DPL-048 只约束
  cron 直调/绝对路径引用的脚本）。
- **close.sh 零改动**：S3b 已正确（memctl gai-links --set-status 幂等），repo/live md5 已一致
  （2a7f11a3…），本次不碰部署面；回归只需确认管线任务 close.sh 仍 PASS。
- **mem_sync.sh cron 已注册**（D12，`*/2 * * * *` repo 路径直调）→ 方案 A 落地进 main 即生效，
  零部署耦合；方案 B 若新增 cron 行，注册动作留 OC（D12 铁律）。
- 本评估卡自身产物（本文件）需随源卡 merge 进 main，不能悬空（DPL-056，t_est_0f418cf6 教训）。
- 本卡是真实代码修复 + 架构裁决修订（非文档收尾型），K=1.0 不适用——DPL-018 校准系数 K=2.86
  全额生效（同型先例 t_est_cd3c6d57 / DPL-058）。
