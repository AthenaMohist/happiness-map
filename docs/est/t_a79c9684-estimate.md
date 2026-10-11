# 评估报告 — FIX va_backfill 静默 skip 盲区：claim 无 changed_files 段时 VA 缺口无感（DPL-060）

> 评估人：寇豆码（game-engine） | 日期：2026-08-16 | 评估卡：t_a79c9684
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12 提出）+ DPL-018 校准注入
> 源卡：DPL-060（[CMD] 指令卡通道 t_c57b201a，Frank 2026-08-11 裁定 2 类型化建链）
> 前置：PRD v1.0（t_a3ba04d3，done）+ ARCH v1.0（t_428e6502，done，12 项裁决 D1-D12）
> 有效轮数折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）

## 1. 结论（TL;DR）

**拆 3 张串行子卡（校准后总 78-114 轮 > 20 轮阈值 → 必须拆）。**

缺陷真实且已数据实证：va_backfill 补扫（DPL-040）对「claim 无标准 `**changed_files**` 段」的卡
**静默 skip**——22 张卡 4089 次 skip，真漏检占比 ≈ 41%（nonstd 6 + md-claims-only 3）/45%（含
超时无 claim 的 t_22848225）。t_4436b52e（DPL-058 S2）是 Frank 追问才暴露的活病例：claim 用
「**4. 交付** - commit …」格式，产物声明真实存在，只因段名不标准被当容器卡。

修复 = R1 判定宽化（四源 OR，恢复 9/22 自动补建）+ R2 留痕（残余 skip 可见可追溯可巡检）+
R3 格式规范（上游防再犯）+ R4 回归落地。本卡不写代码，只评估工作量。

**决策：3 serial（比 arch D12 的 2 serial 多拆 1 张）**——理由：arch 的 S2 捆绑
R2+R3+R4（校准 46-66 轮）超出 42 有效轮预算，按 DPL-018 近 10 条连续超时（5/5 全部 60 轮
timed_out）的实证，超预算卡大概率再超时；R2（留痕机制）与 R3/R4（规范+回归+落地）有清晰
接缝，拆 3 后每张卡校准 23-40 轮，均落在 42 有效轮预算内。

## 2. 工作量评估（读码结论 + 实测，非假设）

### 2.1 现状链路（读码核实）

```
每 tick（autopilot.sh L179-193 块）
  → process_va_backfill（discover.py L1113-1200）
  → _va_backfill_candidates（done + [DEV-%/[FIX]% + 24h 窗口 + NOT EXISTS verifier 子卡 + LIMIT 10）
  → _latest_claim_has_changed_files（discover.py L1079-1110，OR 双条件）
      ├─ 条件1: comment 含 **changed_files** 子串（L1106）
      ├─ 条件2: comment 含 JSON file_* markers（L1108，_CLAIM_JSON_FILE_MARKERS 四变体）
      └─ 都不中 → skip: 只 print stderr（L1156-1161），无 comment、无注册、无分类
```

- 判定函数现状：`_latest_claim_has_changed_files`（L1079-1110）只查 `task_comments`，**从未查
  `task_runs.metadata`**——claim-schema 1.0 canonical 源（kanban_complete metadata 落点）被晾着。
- 写 comment 通道：cmd_chain `_comment`（L547-552，`hermes kanban comment`，env HERMES_KANBAN_DB
  指向）；建卡通道 `_hermes_create`（L507-544，idem_key + parents + json）。**两个现成通道，R2 直接复用。**
- 注册文件模式：`_write_gai_json_minimal`（discover.py L1336-1359，tmp + os.replace 原子写）——
  R2 的 `.pipeline/va-skip/<tid>.json` 同构。
- OC 巡检：oc_wake_check.sh（407 行，源 A-G）已有状态型 seen 键先例（`landing:<tid>:<sha>`、
  `deploy-drift:<script>:<md5>`）——源 H 的 `va-skip:<tid>:<skip_count>` 同模式，照抄写回逻辑（L369-386）。
- R3 注入点：cmd_chain `_dev_card_body` L713-715（CHECKPOINT_BODY_LINE + WIP_BODY_LINE，
  **WIP 是末行**，新增 CLAIM_HINT_LINE 必须插在 WIP 前——test_cmd_channel T59e 断言末行=WIP 零回归）。
- 测试基线：test_va_backfill.sh（372 行，T1-T8 PASS 37+，temp kanban.db 隔离 + DROP 触发器 +
  后置 seed 模式）；test_cmd_channel.sh 387 断言；claim-schema skill 已有 `[PARTIAL - no structured
  claims]` 语义（R3-2 直接复用，不新造标记）。
- arch 已给出全部核心函数完整代码（§2.3/2.4/3.2/3.3/3.4），实现主要是**落代码 + 接线 + 测试**，
  不是从零设计——这点压低基准轮数。

### 2.2 交付物清点（4 交付物 → 拆 ~3 卡规则触发）

| # | 交付物 | 内容 | 文件 |
|---|--------|------|------|
| 1 | 机制（R1） | 判定四条件 OR + 2 新 helper | discover.py + T9 |
| 2 | 留痕+巡检（R2） | skip 三分类 + comment + 注册 + 源 H | discover.py + oc_wake_check.sh + T10 |
| 3 | 规范（R3） | CLAIM_HINT_LINE + va-claim 文案 + skill | constants/cmd_chain/autopilot + test_cmd_channel |
| 4 | 回归+落地（R4） | 全量回归 + 存量实证 + claim | test 三件套 + pytest + 飞书 |

### 2.3 改动清单（逐项轮数）

| # | 项 | 内容 | 预估轮数 |
|---|----|------|:---:|
| ① | S1 判定宽化 | discover.py `_latest_claim_has_changed_files` 扩四条件（条件 1/2 保留 + 新增 `_metadata_has_file_claims`（D1 run 选取 + D5 changed_files 纳入）+ `_claim_has_delivery_commit`（D4 双条件正则）+ 主函数接线（条件 3 不命中不短路条件 4）+ docstring 同步（注释即契约） | 3-4 |
| ② | S1 T9 fixture | test_va_backfill.sh 追加 T9（5 断言：(a) 交付-commit 复刻 t_4436b52e 建卡 (b) metadata-only 建卡 (c) metadata=[] 仍 skip (d) 裸 commit 提及仍 skip (e) T1-T8 零改动确认）；后置 seed 批次（DPL-033 D3 教训）；py_compile + 本地全绿 + grep 验收双条件可见；S1 自身 merge --no-ff 进 main | 5-7 |
| ③ | S2 留痕机制 | discover.py skip 分支三分类（`_va_skip_reason`：legit-container 豁免 D6 / no-claim / nonstd，fail-open）+ `_va_skip_leave_trace`（comment 幂等 D7 `(task_id,reason)` 写前查 + snippet 捕获 + `.pipeline/va-skip/<tid>.json` 读改写原子注册 D8 + skip_count 递增） | 4-6 |
| ④ | S2 源 H + T10 | oc_wake_check.sh 源 H（窗口 done 无 VA + [VA-SKIP] comment → `[va-skip] <tid> reason=… skip_count=N`；状态型 seen 键 `va-skip:<tid>:<skip_count>` D9 + 底部统一写回 L369-386 + 容器豁免双保险）；T10 4 断言（comment 恰好 1 条 / 注册文件字段齐全 / 源 H 输出 / 容器卡豁免） | 5-7 |
| ⑤ | S3 R3 规范 | constants CLAIM_HINT_LINE + cmd_chain `_dev_card_body` WIP 前插行（D10，T59e 末行零回归）+ discover.py L1166-1177 补扫文案 + autopilot.sh L470-472 va-claim 文案（D11 两处）+ claim-schema skill「格式演进同步规则」节（R3-4）+ test_cmd_channel CLAIM_HINT 断言 | 3-5 |
| ⑥ | S3 回归+落地 | 全量回归（test_va_backfill 37+T9 5+T10 4 + test_number_backfill 33 + test_cmd_channel 387 + devPPL pytest 基线对照无新增）；存量实证（t_4436b52e 已有 t_679f3765 记录）；[PRODUCES] claim（标准 changed_files + JSON claims 双格式——本卡自身就是 R1 活正例）+ 飞书推送 + complete | 4-6 |

**基准轮数（未校准）：24-35 轮（中位 30）。**
**DPL-018 校准：基准 × K=2.86 → 校准后 69-100 轮（中位 85）> 20 轮阈值 → 必须拆卡。**

### 2.4 校准后每卡轮数（拆 3 serial 后）

| 子卡 | 基准 | 校准（×2.86） | 42 有效轮预算内？ |
|------|:---:|:---:|:---:|
| S1 机制（①+②） | 8-11 | 23-31 | ✅ |
| S2 留痕+巡检（③+④） | 9-13 | 26-37 | ✅ |
| S3 规范+回归+落地（⑤+⑥） | 7-11 | 20-31 | ✅ |

## 3. 复杂度与风险

| 项 | 评级 | 说明 |
|----|:---:|------|
| R1 **arch D12 建议 2 serial，本 EST 改 3 serial** | 低 | 差异仅拆法：arch 的 S2（R2+R3+R4）校准 46-66 轮 > 42 预算，按连续超时实证（5/5 张 60 轮 timed_out）大概率超时；R2（discover 留痕 + oc_wake 源 H）与 R3/R4（提示行 + skill + 全量回归）接缝清晰，拆 3 后每卡 ≤37 轮。拆卡粒度是 EST 职责，不改变功能范围 |
| R2 源 H seen 键机制 | 中 | bash + SQL + JSON 混合，407 行脚本；但完全仿源 E/G 状态型键先例（L369-386 写回逻辑现成），照抄 + T10(c) 断言锁死 |
| R3 T9/T10 fixture 后置 seed | 中 | DPL-033 D3 教训：新批次必须后置、独立 seed，否则污染 T1-T8 计数；断言"只增不删"（T9(e)） |
| R4 条件 4 正则误报 | 低 | 双条件 AND（commit ref + 交付语义）+ T9(d) 负例 fixture 锁死；补扫建卡门槛放低由 verifier 判伪（arch §2.4 架构边界） |
| R5 metadata 读取新依赖 | 低 | 同库同连接（mode=ro）；查不到/解析失败 → False（fail-open 现状语义）；D1 双值 IN ('done','completed') + S1 checklist `SELECT DISTINCT status` 实测（OC 注意 2 吸收） |
| R6 _comment 写真实 board 风险 | 低 | test harness 已 export HERMES_KANBAN_DB=temp 库（test_va_backfill.sh L29 同款隔离）；_comment 走 env 指向 |
| R7 全量回归破坏 | 中 | test_cmd_channel 387 断言 + devPPL pytest（~10min 后台）——只增不删 + CLAIM_HINT_LINE 插 WIP 前（T59e 末行断言锁死）+ pytest 基线对照（281/8/1 无新增，参考 DPL-059 S3 实证） |
| R8 存量 22 卡历史 skip | 低 | 注册文件只记上线后；历史 4089 行日志留基线不迁移 |

**关键决策点（S1/S2 实现时拍板，不改变轮数量级）**：
- D1 run 选取：最近 status IN ('done','completed') ORDER BY id DESC LIMIT 1（arch 已定）
- D2 metadata 解析失败 → False 不短路条件 4（arch 已定）
- D5 条件 3 纳入 metadata.changed_files 数组（arch 已定，比 PRD 略宽同源零误报）
- D9 源 H seen 键 = 状态型 `va-skip:<tid>:<skip_count>`（arch 已定）

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 24-35 轮（中位 30） |
| DPL-018 校准后 | 69-100 轮（×K=2.86，中位 85）**> 20 轮阈值 → 必须拆卡** |
| 交付物数 | 4（机制/留痕巡检/规范/回归落地）→ 按规则拆 ~3 卡 |
| 模块依赖 | S1（R1 判定）→ S2（R2 留痕，依赖 S1 机制在 main 才能验证 skip 分支）→ S3（R3 提示行 + R4 全量回归，依赖 S1/S2 都在 main）单向依赖，串行 |
| 并行收益 | 低——S2 测试依赖 S1 已 merge；S3 回归依赖 S1/S2；并行引入接口未就绪风险 |
| 兜底 | 若 S2 超预算，T10(d) 容器豁免断言可分 commit 交付；S1 独立可验收（T9 5 断言全覆盖 R1） |

**决策：拆 3 张串行子卡。** arch D12 的 2 serial 会让 S2 超预算（校准 46-66 轮），
按近 10 条偏差记录（5 张全 60 轮 timed_out）必再超时；拆 3 后每卡校准 20-37 轮，
全部落在 42 有效轮预算内，符合「4 交付物 → ~3 卡」规则。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 3 serial
1. [DEV-SUB-1] 机制 — R1 检测宽化（四条件 OR）：discover.py _latest_claim_has_changed_files
   扩四条件（保留 comment 双条件 + 新增 _metadata_has_file_claims（task_runs 最近
   done/completed run metadata.claims file_* 或 changed_files 非空，D1 双值 + S1 checklist
   SELECT DISTINCT status 实测）+ _claim_has_delivery_commit（commit 引用 + 交付语义双条件
   正则 D4）+ 条件 3 不命中不短路条件 4 + docstring 同步）；test_va_backfill.sh 追加 T9
   （5 断言 (a)交付-commit 复刻 t_4436b52e 建卡 (b)metadata-only 建卡 (c)metadata=[] 仍
   skip (d)裸 commit 提及仍 skip (e)T1-T8 零改动）；py_compile + 本地 test_va_backfill
   全绿 + grep 验收双条件可见；S1 merge --no-ff 进 main 预计 23-31 轮
2. [DEV-SUB-2] 留痕+巡检 — R2：discover.py skip 分支三分类（_va_skip_reason：
   legit-container 容器豁免（task_links 子卡 EXISTS D6）/no-claim/nonstd，fail-open）+
   _va_skip_leave_trace（[VA-SKIP] comment 幂等 (task_id,reason) 写前查 D7 + snippet
   捕获 + .pipeline/va-skip/<tid>.json 读改写原子注册 D8 + skip_count 递增）；
   oc_wake_check.sh 源 H（窗口 done 无 VA + [VA-SKIP] comment → [va-skip] 行，
   状态型 seen 键 va-skip:<tid>:<skip_count> D9 + 底部统一写回 + 容器豁免双保险）；
   T10 4 断言（comment 恰好 1 条 / 注册文件字段齐全 / 源 H 输出含 reason+skip_count /
   容器卡豁免）；本地 test_va_backfill 全绿；S2 merge --no-ff 进 main 预计 26-37 轮
3. [DEV-SUB-3] 规范+回归+落地 — R3/R4：constants CLAIM_HINT_LINE + cmd_chain
   _dev_card_body WIP 前插行（D10，T59e 末行零回归）+ discover.py 补扫文案 +
   autopilot.sh va-claim 文案（D11 两处）+ claim-schema skill「格式演进同步规则」节 +
   test_cmd_channel CLAIM_HINT 断言；全量回归（test_va_backfill 37+T9 5+T10 4 +
   test_number_backfill 33 + test_cmd_channel 387 + devPPL pytest 无新增）；存量实证
   （t_4436b52e 已有 t_679f3765 记录）；[PRODUCES] claim（标准 changed_files + JSON
   claims 双格式）+ 飞书推送 + complete 预计 20-31 轮
```

- SPLIT: yes（count=3，交付物 4 → ~3 卡；arch D12 2 serial 的 S2 超预算，EST 修正）
- MODE: serial（S2 依赖 S1 机制在 main；S3 回归依赖 S1/S2 都在 main）
- FILES: S1 改 discover.py + test_va_backfill.sh；S2 改 discover.py + oc_wake_check.sh +
  test_va_backfill.sh；S3 改 constants.py + cmd_chain.py + autopilot.sh + test_cmd_channel.sh +
  claim-schema skill（+ 全量回归）
- 部署: 全部经 OC 部署（DPL-048 must-sync 清单 + autopilot.sh 若入清单），repo 正本先行
