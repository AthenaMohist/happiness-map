# 评估报告 — [DEV-EST] MEM-008 记忆突触自强化：访问加权 + 定期归档瘦身（解禁重启）

> 评估人：寇豆码（game-engine） | 日期：2026-08-30 | 评估卡：t_e0635404 | 源链：MEM-008（t_cba78311 arch → 本卡）
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.45 → K=2.45（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 18-33 全撞 60 上限）
> ⚠️ 本卡连续超时告警触发：预估必须按校准后口径（基准 × 2.45）重新评估

## 1. 结论（TL;DR）

**拆 5 张串行子卡（校准后每张 10-29 轮，全部落在 30 有效轮红线内 / 42 预算内）。**

任务本质：S1（decay/context/query 埋点 + 加权排序）冻结前已交付且有测试护栏；
本卡 scope = R1 修信号源（生命周期埋点 + 冷启动回填 + status 段 + 调度行交付 OC）
+ R2-R4 建归档子系统（候选判定五重护栏 → dry-run → stub 可回滚 apply → 报告）
+ R5 cron 行交付。**核心工作量集中在 memcore 新模块 archive.py + indexer/lint/parse 三处配套改造。**

**评估期间实测关键发现（决定拆卡方案，非假设）：**
- **arch D16 的 3 卡建议（R1 / R2+R3 / R4+R5）在 K=2.45 校准下不成立**：R2+R3 合并
  基准 22-33 → 校准 54-81 轮，必超时。必须把 R2+R3 再拆（配套基建 / 执行）两层。
- **R3 apply 有硬前置依赖**：apply 流程内 `_maintenance` 增量 build 在缺 D7（幽灵行清理）
  时必留 ghost 行 → lint I4 报错 → A9 失败；stub 出链 ≤1 → 缺 D15（I2 豁免）必报 I2；
  stub 归档链接 → 缺 D2（parse extra_paths）必报 I1。**配套基建卡必须在执行卡之前**。
- **S1 接线已完备**（context.py L133/L170 已 record_accesses；cli.py 写链统一
  `_log_append → _maintenance → _git_commit`）→ R1.1 devPPL 侧零代码，R1.2 是
  4 处一行插入 + 1 个 helper。**R1 实际工作量比 PRD 想象的小**，但仍需 A1 集成验证
  （构造 worker run → sqlite 直查）+ 回归，无法再拆。
- **env 注册 6 个新变量**（schema.py + SCHEMA.md §4.2 同步）随 R2 落地，独立小项。

## 2. 工作量评估（读码结论，非假设）

改动面：**mem-core 为主（5 文件 + 2 新模块），devPPL 零代码（仅调度行交付 OC）**——

| 模块 | 改动 | 依据 |
|------|------|------|
| memcore/archive.py（新） | 候选判定五重护栏 + 豁免统计 + dry-run + apply + rollback + report | 全新 ~350-450 行，arch §3 定稿 |
| memcore/lock.py（新） | flock 独占锁（30s 超时 fail-open） | arch D8，~40 行 |
| memcore/cli.py | `archive` 子命令壳 + 生命周期埋点 4 处（add/done/note/demote）+ status 访问统计段 | cli.py L231/693/1038/~L1750 写链实读 |
| memcore/indexer.py | D7 幽灵行清理 + D6 events 备份/恢复 + D11 冷启动回填 | indexer.py L246/L273/L291/L310 实读 |
| memcore/lint.py | D15 三条（I2 stub 豁免 / I3 archived 兼容 / archive_path 必填） | lint.py L289-297/L366/L429-430 实读 |
| memcore/parse.py | resolve_wikilink 增 extra_paths（向后兼容默认 None） | parse.py 实读（iter_wiki_files L340 已排除 _archive/） |
| memcore/schema.py | 6 个 MEM_ARCHIVE_* env 注册 | schema.py L55-128 env 表实读 |
| SCHEMA.md / cron 行 | §4.2 env 同步；§6.3 4 条 cron 行交付 OC（不注册） | arch §6.3 |

### 逐卡基准评估

| 子卡 | 工作内容 | 基准轮数（未校准） | 依据 |
|------|---------|------------------|------|
| SUB-1 R1 信号接通 | 生命周期埋点 helper + 4 命令插入（--check 排除）；indexer 冷启动回填 SQL（幂等）；status 访问统计段（3 查询）；调度行交付 OC（boot_context/mem_sync/conv_sync 3 条）；A1-A3 pytest 用例 + 全量回归 | 8-12 | 埋点=机械插入（cli.py 4 处已定位）；回填=1 条 UPDATE；A1 集成验证需构造 boot_context worker run（跨仓库 env 注入）2-3 轮；回归 pytest 246 + lint 1-2 轮 |
| SUB-2 R2 候选判定 + dry-run | archive.py 候选函数（五重护栏 + 豁免统计）+ dry-run 输出（候选表/类型小计/豁免统计）+ 6 env 注册 + cli 壳（--dry-run）；A4-A6 测试 | 6-9 | 纯机械判定（arch D12 公式已定稿）；dry-run 只读无副作用；豁免统计逐条件计数（A5）是主要逻辑量 |
| SUB-3 R3 配套基建 | indexer D7 幽灵行清理 + D6 events 备份/恢复（--rebuild）；lint D15 三条适配；parse extra_paths + archive_path_map；相关测试 | 7-10 | 涉及 3 个既有模块语义改造（indexer build 增量 DELETE / rebuild restore / lint 判定 / resolve 签名），回归风险集中；D6 顺带修 MEM-009 correction rebuild 丢失 bug |
| SUB-4 R3 归档执行 | lock.py + archive.py apply（rename+stub+events+git commit+幂等）+ rollback（stub 定位+rename 回+events+幂等）+ cli --apply/--rollback；A7-A8 测试 | 8-12 | apply/rollback 是文件系统 + sqlite + git 三态操作，幂等 + fail-open + 单页 commit 语义；测试需构造归档/回滚全链夹具 |
| SUB-5 R4+R5 报告 + cron | archive --report（终端四指标 + 报告页 + 状态文件 .pipeline/archive_report.json）+ cron 行交付；A10-A11 测试 | 4-6 | report 是只读聚合 + 2 个落盘文件；cron 行已由 arch §6.3 定稿，仅交付不注册 |

**基准合计：33-49 轮（中位 ~41）。**
**DPL-018 校准：33-49 × K=2.45 → 校准 81-120 轮** → 单卡必然超时（预算仅 42 有效轮），
必须拆卡。按 5 卡方案每卡校准后 10-29 轮（详见 §4），全部落在安全区内。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | apply 后 lint 四不变式必破（ghost 行 / stub 出链 / 断链） | 高 | 根因是 D7/D15/D2 未先落地。缓解：拆卡顺序强制 SUB-3 配套基建先于 SUB-4 执行（serial 依赖），A9 门禁在 SUB-4 全量 lint |
| R2 | indexer 三处改造（D7/D6/D11）互相干扰 | 高 | 同文件多语义改动，回归面大（build 增量 + rebuild 全量两条路径）。缓解：SUB-3 单独一卡聚焦 indexer + 测试先行；pytest 全量回归每步跑 |
| R3 | D6 events 备份/恢复改动 rebuild 路径 → MEM-009 correction 事件回归 | 中 | 顺带修复实证 #9 已知 bug。缓解：SUB-3 测试显式造 correction/archive 事件 → rebuild → 断言保留 |
| R4 | resolve_wikilink extra_paths 改签名 → 4 调用方（lint/indexer/gailinks/drift）回归 | 中 | 默认 None 向后兼容，gailinks/drift 不传。缓解：SUB-3 测试覆盖 stub 链接两种形态（裸 id / 路径），全量 lint 门禁 |
| R5 | R1.1 依赖 cron 注册（OC 权限）才能真实验证 A1 调度恢复 | 中 | 本卡只交付 cron 行 + 构造 worker run 集成测试（非真实 tick）；真实 tick 验收由 OC 注册后 devPPL 集成脚本（§8.2）覆盖。缓解：A1 用例用临时 wiki + 临时 db + env 注入，不依赖生产调度 |
| R6 | 冷启动回填后 count=0 页 weight=1.0 基线语义 → 候选公式空转 | 低 | 架构已裁决（D11 只回填时间戳不伪造 count）；R2 的 MIN_ACCESS env 兜底；A4 用测试夹具造冷页验证不依赖真实时间 |
| R7 | 5 卡 serial 链总工期长（校准 81-120） | 中 | 每卡独立 commit/merge，任一张 done 即释放后续；链上卡可并行 claim 吗？——serial 依赖保证前卡 done 才派发下一张，无并行配额问题 |
| R8 | 报告页落 archive/ 不进 pages → A10「收录且 lint 过」口径需解释 | 低 | arch §4.3 已裁决（报告=归档域元数据，收录=稳定命名+状态文件）；SUB-5 测试按此口径 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 33-49 轮（中位 ~41） |
| DPL-018 校准后 | 81-120 轮（×K=2.45）**≫ 30 有效轮红线 → 必须拆卡** |
| 交付物数 | 5 个（信号埋点 / 候选+dry-run / 配套基建 / 归档执行 / 报告+cron）≥ 4 → 拆 ~3 卡起，本方案 5 卡 |
| arch D16 3 卡方案复算 | R1: 8-12→20-29 ✓ / R2+R3: 22-33→54-81 ❌ / R4+R5: 4-6→10-15 ✓ — **R2+R3 合并卡必超时，否决** |
| 本评估 5 卡方案 | SUB-1: 8-12→**20-29**（29/42=69%）✓ / SUB-2: 6-9→**15-22**（52%）✓ / SUB-3: 7-10→**17-25**（60%）✓ / SUB-4: 8-12→**20-29**（69%）✓ / SUB-5: 4-6→**10-15**（36%）✓ |
| 依赖方向 | R1 → R2（回填是候选判定的数据前提）→ SUB-3 配套 → SUB-4 执行（apply 硬依赖 D7/D15/D2，§1）→ SUB-5（报告依赖归档事件 + D6） |
| 并行收益 | 低——链上每步都是下一步的数据/语义前置；R4+R5 与 R2/R3 无耦合但量小不值得并行；串行最稳 |
| 兜底 | SUB-4 若超预算：rollback 幂等/夹具可精简，apply 主体优先；SUB-3 若超预算：D6 events 备份可切独立 contingency（不影响 D7/D15/D2 主路径） |

**决策：拆 5 张串行子卡（[SUB-SPLIT] 5 serial）。**
粒度参照：t_569d4425（DPL-087）拆 2 卡、t_1db58772（DPL-069）拆 2 卡同款机制；
本任务交付物 5 个 + 2 个新模块 + 3 个既有模块语义改造，5 卡粒度与「交付物边界」对齐，
比 arch D16 的 3 卡更符合 K=2.45 校准后的安全口径。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 5 serial
1. [DEV-SUB-1] MEM-008 R1 信号接通：cli.py 生命周期埋点（_record_lifecycle_access
   helper + add/done/note/demote 4 处 _log_append 后插入，--check 只读不埋）+
   indexer 冷启动回填（build 幂等 UPDATE last_access_at=COALESCE(created, 首建时间)
   WHERE NULL，access_count 不动）+ cmd_status 访问统计段（有流量页/总访问/近 7 天
   三计数）+ 调度行交付 OC（boot_context/mem_sync/conv_sync 3 条 cron 行，不注册）+
   A1-A3 pytest 用例（含 boot_context worker run 集成验证：临时 wiki+db+env 注入 →
   sqlite 直查 count>0）+ 全量回归（pytest 246 + lint）。预计 20-29 轮
2. [DEV-SUB-2] MEM-008 R2 归档候选判定 + dry-run：memcore/archive.py 候选函数
   （五重护栏：HOME_PAGES 排除 / status 镜像 / type 白名单 / weight 阈值 / idle 超时
   / min_access / min_age / allowlist，全 env 化 MEM_ARCHIVE_* 6 个注册 schema.py+
   SCHEMA.md）+ 豁免统计逐条件计数（A5）+ dry-run 输出（候选表+类型小计+豁免统计）+
   cli.py archive 子命令壳（--dry-run [--json]，只读零副作用）+ A4-A6 测试。
   预计 15-22 轮
3. [DEV-SUB-3] MEM-008 R3 配套基建：indexer D7 幽灵行清理（build 增量 DELETE
   file_path 不在清单的 pages/links/term_pages/bigram_index/pages_fts 行）+
   D6 events 备份/恢复（--rebuild 保留 kind=archive/unarchive/correction 事件，
   顺带修 MEM-009 correction rebuild 丢失 bug）+ lint D15 三条（I2 stub 豁免
   status=archived+mechanism=memctl archive / I3 archived⊇done 兼容 / archive_path
   必填 ERROR）+ parse resolve_wikilink extra_paths + archive_path_map 小助手 +
   相关测试（含 stub 链接两种形态 + rebuild 事件保留）。预计 17-25 轮
4. [DEV-SUB-4] MEM-008 R3 归档执行：memcore/lock.py（flock 独占锁 .memctl.lock
   30s fail-open）+ archive.py apply（os.rename→archive/YYYY-MM/ + 原位写 stub
   （D4 schema 全集）+ _log_append(kind=archive) + events 落库 + 独立 git commit +
   幂等 exit 1 + fail-open 批量 --limit）+ rollback（stub 定位 + 读 archive_path +
   rename 回 + 删 stub + events kind=unarchive + 独立 commit + page_access 保留 +
   幂等）+ cli --apply/--all-candidates/--rollback + A7-A8 测试 + A9 全量 lint 门禁。
   预计 20-29 轮
5. [DEV-SUB-5] MEM-008 R4+R5 归档报告 + cron：archive --report（终端四指标：
   归档数/释放体积(line+word)/回滚数/误归档率>10% 标红 + 下期候选余量）+ 落
   wiki/archive/report-YYYY-MM.md + 状态文件 .pipeline/archive_report.json
   （watchdog 可消费）+ cron 行交付 OC（月度 dry-run+report，apply 无自动化路径）+
   A10-A11 测试。预计 10-15 轮
```

- SPLIT: yes（count=5，校准后 81-120 轮 ≫ 30 红线）
- MODE: serial（SUB-3 配套基建 → SUB-4 执行硬依赖；R1→R2 数据依赖；SUB-5 依赖归档事件）
- ROUNDS_EST（校准后）: 20-29 / 15-22 / 17-25 / 20-29 / 10-15（基准 33-49 × K=2.45）
- FILES: memcore/archive.py（新）+ memcore/lock.py（新）+ memcore/cli.py + memcore/indexer.py
  + memcore/lint.py + memcore/parse.py + memcore/schema.py + SCHEMA.md —— 5 改 2 新 1 文档
- STATUS: not_started（本评估卡待 complete，autopilot 解析建 5 张子卡挂源链）
- TESTS: 新增 pytest ≥18（arch §8.1 表 18 用例映射 A1-A11）+ 每卡全量回归（pytest 246 + lint）
- RISK: R1 apply 后 lint 必破（依赖序强制）；R2 indexer 三改造互扰；R3 D6 rebuild 回归；
  R4 resolve 签名 4 调用方；R5 A1 真实验证依赖 OC 注册（本卡用构造 run 集成测试兜底）
- ACTION: build_five_dev_cards（assignee=game-engine，parents=[源链 dev 卡]，serial）

## 6. 备注

1. **devPPL 侧零代码改动**：R1.1 已由 S1 接线（context.py L133 record_accesses）；
   调度恢复是 cron 注册（OC 权限），本链只交付 cron 行。DPL-048 部署验证规则不适用
   （无 cron 直调脚本改动）。
2. **与 arch D16 的分歧及理由**：arch 建议 3 卡（R2+R3 合并），本评估改为 5 卡——
   合并卡校准后 54-81 轮必超时（最近 5 张子卡 timed_out 前科同款）。拆卡边界沿用
   arch 交付物边界，仅把 R2+R3 在「配套基建/执行」处再切一刀，符合 est 卡
   「必须按校准后口径重新评估」的硬性要求。
3. **SUB-3 前置性不可省**：apply 的 A9 门禁（lint 四不变式零问题）依赖 D7（幽灵清理）、
   D15（I2 stub 豁免）、D2（parse extra_paths）先落地；顺序错则 SUB-4 必返工。
4. **D6 归属**：arch D16 将 D6 列 R4+R5，但注释明示「随 R2+R3 一并实现更省一次
   rebuild 改动」——本评估归 SUB-3（indexer 改造集中卡），SUB-5 仅消费 events 计数。
5. 本评估卡不写功能代码；产出即本报告 + [SUB-SPLIT] comment，autopilot 读取后建 5 张
   [DEV-SUB] 卡执行。
