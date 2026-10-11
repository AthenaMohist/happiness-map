# 评估报告 — [FIX] 备份连续失败修复 — git fetch errexit 假失败 + rsync code24 容错 + fetch 重试

> 评估人：寇豆码（game-engine） | 日期：2026-08-30 | 评估卡：t_est_52c4a9c1 | 源卡：t_52c4a9c1
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：Frank 报备备份连续失败 → 手工排查 /workspace/backup-push.log → 三故障根因已定位并修复落地 → 本 FIX 卡做回归验证
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.40 → K=2.40（clamp 0.5-3.0）；沿用最近 est 卡同源校准

## 1. 结论（TL;DR）

**不拆（[SUB-SPLIT] 1）——源卡 t_52c4a9c1 直接执行。校准后 17-24 轮（基准 7-10 × K=2.40），
落在 42 有效轮预算内（40-57%），且任务原子、无第二可分离阶段。**

任务本质：**回归验证**而非实现。三个故障修复**已在评估期间实测确认全部落地**在
`/workspace/hermes_backup_push.sh`（该脚本在 /workspace 系统区，不在 devPPL 仓内，
源卡 workspace_kind=scratch 与事实一致）。剩余工作 = 手动跑一次全量备份三件套 +
远端 commit 确认 + 查日志无新增失败 +（可选）补 BKP-005b 教训文档。

**评估期间实测确认（非假设）：**
- 故障 1（git fetch 假失败）修复已落地：L360-362 BKP-005b 注释 + L363-400 temp file
  捕获 stderr + `set +e` 显式 `$?` 重试循环（3 次，间隔 10s/20s）——命令替换 + errexit
  陷阱已绕开。
- 故障 2（rsync code 24）修复已落地：L460 `--ignore-missing-args` + L462-468 显式
  判断（24 容忍，其余 die）——file has vanished 不再当硬错误。
- 故障 3（网络超时）修复已落地：BKP-005 L358-359 注释 + L365-397 三次重试，
  仍失败才 die。
- **修复已验证有效**：SandboxHermesBackup 仓 git log 显示修复后连续 2 次全量备份
  成功——a7f21fc（21:51:26）、593267b（21:54:56）；实测 `git ls-remote origin
  refs/heads/main` = 593267b = 本地 HEAD（SSH key 绝对路径 GIT_SSH_COMMAND），
  远端 push 已确认。
- backup-push.log 最后失败条目为 20:26:17（修复前，git fetch 3 次重试仍失败——
  正是 BKP-005b 要修的假失败），21:55 后无新增失败（实测 tail/stat）。
- 运行环境：hermes_daily_backup.sh（54 行 wrapper，载 .env + 调 push 脚本）+
  hermes_backup_push.sh（1019 行主体）；GITHUB_BACKUP_TOKEN 在 /root/.hermes/.env；
  SSH key /root/.hermes/profiles/orchestrator/home/.ssh/id_ed25519_github 存在。
- 修复本身**不需要写代码**——已落地；源卡任务 1/2 是验证、任务 3 是可选文档。

## 2. 工作量评估（实测结论，非假设）

改动面：**0 个代码文件改动**（修复已落地）。核心产出 = 一次成功的手动备份运行 +
远端确认证据 + 日志无新增失败证据；可选产出 = 1 处文档/技能补充。

| # | 工作项 | 基准轮数（未校准） | 依据 |
|---|------|:---:|------|
| ① | 领卡 orient + 读源卡 body + 核对脚本三修复已落地（读 L358-400/L460-468 注释与实现） | 1-2 | 本评估已实测修复落地；执行时复核关键行即可 |
| ② | 手动跑全流程 `bash /workspace/hermes_daily_backup.sh`（sha256 计算 ~40 文件 + rsync ~/.hermes + manifest 注解 + git fetch/push） | 2-4 | 从日志实测单次运行含失败重试约 40-90s；成功路径 rsync 全量 ~/.hermes 属大目录，等待 2-5 min 属正常；**主要耗时是真实等待，不是调试** |
| ③ | 远端确认：git ls-remote origin main == 本地 HEAD（GIT_SSH_COMMAND 绝对 key） | 0.5-1 | 评估已实测 593267b==593267b；执行时重跑一次即可 |
| ④ | 查 backup-push.log：确认 21:55 后无新增失败（grep ERROR + tail） | 0.5-1 | 评估已实测最后失败 20:26（修复前）；执行时顺带看本次运行产生的成功/失败条目 |
| ⑤ | 可选：BKP-005b 教训补入备份文档/技能（命令替换 + errexit 陷阱） | 0.5-1 | 修复注释已含教训（L360-362），补文档是搬运不是新写；明确可选，跳过不阻塞验收 |
| ⑥ | claim（changed_files/JSON claims）+ 飞书推送 + complete | 1.5-2 | 标准闭环；claims 以「手动运行成功 + 远端一致 + 日志无新失败」为主，代码文件 0 改动 |

**基准轮数（未校准，合计）：7-10 轮（中位 ~8.5）。**
**DPL-018 校准：7-10 × K=2.40 → 校准后 17-24 轮**（中位 ~20，42 有效轮预算的
40-57%）——**单卡可行，不拆**。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | **手动备份运行中网络再抖**（git fetch/push 超时） | 中 | 正是本卡要回归验证的场景。缓解：脚本已有 3 次重试（10s/20s），仍失败才 die；若 die → 如实报告 + 看 DEBUG-BKP-005 输出（BACKUP_DEBUG=1），不伪造成功；单次重试等待 30s 在 ② 预算内 |
| R2 | rsync 并发文件消失再次触发 code 24 | 低 | 修复后 24 已容忍（L462-468），不再 die；若出现会打 (rsync exit 24...) 日志条目，属预期 |
| R3 | 手动运行与 cron 11:00 UTC 撞车 | 低 | 当前 21:56 CST = 13:56 UTC，距下次 cron 11:00 UTC 尚远；若真撞车，脚本已有脏标记/幂等设计，双跑最多冗余 push 无数据损坏 |
| R4 | push 远端失败导致本地领先（BKP-DR-04 欠账路径） | 低 | 脚本会自动补推（L410-417）；若远端领先则 die 报警——评估已实测远端 == 本地，此路径不应触发 |
| R5 | 修复「已落地」但执行时被回滚/覆盖 | 低 | 脚本 mtime 21:52（今天）；执行时先 grep BKP-005b/--ignore-missing-args 复核，缺失则按源卡语义补回（但那会让本卡从回归变实现，需即时反馈） |
| R6 | 可选文档任务 scope 蔓延 | 低 | 明确「可选」：只补 BKP-005b 教训（命令替换+errexit），不重构备份文档体系；预算不足可跳过并在 claim 注明 |
| R7 | 本卡产物 docs/est/t_52c4a9c1-estimate.md 自身 code-not-in-main | 中 | 评估产物在 wt/t_est_52c4a9c1 分支，落 main 需后续 MERGE 卡（先例 t_d683fdef/t_est_15e790bc 均踩过）。缓解：[PRODUCES] 给 OC 明示，由 OC 派 MERGE 卡追回 |
| R8 | claim 格式（DPL-060） | 低 | 源卡 claim 必带 changed_files 段；本卡代码 0 改动，claims 以验证证据为主，四源至少命中（运行日志/远端对比/JSON claims） |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 7-10 轮（中位 ~8.5） |
| DPL-018 校准后 | 17-24 轮（×K=2.40），42 有效轮预算的 40-57% ✅ 单卡可行 |
| 20 轮阈值 | 校准中位 ~20 贴线——但超阈值本义是「防单会话超预算」；24/42 = 57% 预算，余量充足；且本卡核心是**等待型验证**（跑备份等结果），不是多模块实现 |
| 任务原子性 | 跑一次备份 + 远端确认 + 查日志一气呵成，**无第二可分离阶段**（无多模块、无接线、无测试矩阵）——拆卡无可拆内容 |
| 拆卡开销 | 2 卡 ×（orient + claim + 飞书 + complete）≈ 额外 4-6 轮 > 拆分收益（几乎为零） |
| 代码改动量 | **0 文件**（修复已落地）——拆卡没有实现分片可拆 |
| 与先例差异 | t_2048b809/t_94b55776 拆 2 serial 是**实现卡**（多文件代码+测试矩阵）；本卡是**回归验证卡**，量级同 t_est_77055941（机械 MERGE，不拆） |
| 历史偏差源 | 最近 timed_out 的 5 条全是**实现卡**（MEM-013/DPL-092 类）；本卡是验证+等待，偏差驱动因素弱 |

**决策：不拆（[SUB-SPLIT] 1）——源卡 t_52c4a9c1 按卡面直接执行。**
量级参照：t_est_77055941（机械 MERGE 不拆，校准 19-26）——本卡代码改动更少（0 文件），
但多一次真实备份运行等待（② 2-4 轮），总量级相当；t_94b55776（2 文件机械落地不拆）。
本卡卡面已把验证命令/证据要求全部给定（ls-remote 一致、日志无新增失败、代码注释可追
溯），无设计决策、无发现轮。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 1
```

- SPLIT: no（count=1；校准 17-24 轮在 42 有效轮预算内，任务原子无第二可分离阶段，
  代码 0 改动，拆卡开销 > 收益；历史偏差源为实现卡，本卡为回归验证卡）
- MODE: N/A（单卡直接执行，源卡已存在 t_52c4a9c1，workspace_kind=scratch——脚本在
  /workspace 系统区，不在 devPPL 仓，无需 worktree）
- ROUNDS_EST（校准后）: 17-24（基准 7-10 × K=2.40）
- FILES: 代码 0 改动（三修复已在 /workspace/hermes_backup_push.sh 落地）；
  可选 +1 文档（BKP-005b 教训补入备份相关技能/文档）
- STATUS: not_started（本评估卡待 complete，源卡 t_52c4a9c1 的 parents=[t_est_52c4a9c1]
  done 后自动 promote ready → 直派）
- TESTS: 验收三门禁 = ① `bash /workspace/hermes_daily_backup.sh` 手动全流程 exit 0 +
  backup-push.log 出现成功条目；② `git ls-remote origin refs/heads/main` ==
  本地 `git rev-parse HEAD`（GIT_SSH_COMMAND 绝对 key）；③ backup-push.log 21:55 后
  无 ERROR/Daily backup failed 新增
- RISK: R1 网络再抖（中，重试 3 次兜底，die 则如实报告）；R5 修复被回滚（低，先复核
  再跑）；R7 est 产物自身 code-not-in-main（中，OC 另派 MERGE 追回）
- ACTION: none（不建子卡；源卡 t_52c4a9c1 直接执行）

## 6. 备注

1. **本卡不写功能代码**；产出即本报告 + [SUB-SPLIT] 1 comment + [PRODUCES] claim，
   autopilot 按 count=1 不建子卡，源卡直接执行。
2. **三个修复已在评估期间逐行实测确认**（BKP-005b L360-362/L363-400、rsync 24
   L460-468、BKP-005 L358-359/L365-397），且修复后 2 次全量备份成功 + 远端一致——
   源卡执行时以「复核 + 回归」为主，若复核发现修复缺失再按源卡语义补回。
3. **远端 ls-remote 实测**：`GIT_SSH_COMMAND="ssh -i /root/.hermes/profiles/orchestrator/
   home/.ssh/id_ed25519_github -o StrictHostKeyChecking=no"` 下
   `git ls-remote origin refs/heads/main` = 593267b2082620916ba0263c6659b776676d8767
   == 本地 HEAD——push 链路健康。
4. **backup-push.log 时间线**：10:30（rsync 24 硬错误，修复前）→ 20:00（rsync 24 再犯，
   触发本次修复）→ 20:25-20:26（git fetch 假失败 3 重试仍 die，BKP-005b 根因）→
   21:51/21:54（修复后 2 次全量成功，commit a7f21fc/593267b）→ 21:55 后无新失败。
5. **BKP-005b 教训**（命令替换 + errexit 陷阱）已写入脚本注释 L360-362；可选文档补充
   仅搬运该教训到备份相关文档/技能，不新造内容。该陷阱与 memory 中记录的
   `VAR=$(failing_cmd)` + set -e 交互同源，执行时可直接复用。
6. **建议执行顺序**：复核修复落地 → 跑全量备份（等待）→ 远端确认 → 查日志 → 可选文档
   → claim。若跑备份即失败且重试耗尽 → 按 R1 处理：BACKUP_DEBUG=1 复现取证，如实
   claim 失败原因，不伪造成功。
