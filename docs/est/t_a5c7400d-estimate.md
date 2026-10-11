# 评估报告 — [DEV-EST] Claude Code 代工研发与测试 — GLM Anthropic 端点直连（DPL-101）

> 评估人：寇豆码（game-engine） | 日期：2026-09-01 | 评估卡：t_a5c7400d | 源卡：t_a5c7400d（est 卡即评估对象，承接 DPL-101 开发）
> 机制：docs/design/estimate-split-cards.md（Frank 2026-08-12）+ DPL-018 校准注入
> 源卡链：CMD（Frank 2026-08-30 登记）→ PRD（t_8e0109eb done，v1.0 206 行）→ ARCH（t_c661f808 done，v1.0 543 行）→ 本评估卡
> 有效轮折算: 预算 60 × 0.7 = 42 有效轮（R3 口径，DPL-030 S2 实证）
> 校准注入: 累计偏差 +1.35 → K=2.35（clamp 0.5-3.0）；最近 5 条子卡偏差全部 timed_out（估 20-41 全撞 60 上限）

## 1. 结论（TL;DR）

**拆 2 张串行子卡（校准后 SUB-1 13-19 / SUB-2 14-19 轮，合计 27-38 轮，全部落在 42 有效轮预算内）。**

任务本质：实现 DPL-101 的执行外挂通道（game-engine 侧 S1 交付物）——
一个 bash wrapper（`cc-glm`）+ 一套打桩测试（T1-T6 断言矩阵）+ 漂移清单 +1 + skill 增补 + 软链部署步骤。
ARCH v1.0（t_c661f808，543 行）已把 wrapper 的 key 解析/三检/doctor 四检/参数契约、
测试断言矩阵（T1a-T6b）、must-sync 清单改动全部给到可执行粒度——**实现是"按图施工"而非设计**，
主要工作量在 bash 实现细节与打桩测试调试（bash 无类型、env 注入断言、版本锁校验路径）。

**评估期间实测关键事实（非假设）：**
- claude CLI v2.0.0 双路径存在（/usr/bin/claude + /usr/local/bin/claude→nvm 软链）——版本锁基线可复现（arch 事实 1 复核 ✅）
- `/usr/local/bin/cc-glm` **不存在**（wrapper 从零建，无既有实现可改）
- `scripts/test_cc_glm.sh` **不存在**（测试从零建）
- `deploy_drift_check.sh` L42 DEFAULT_SYNC_LIST 现为 5 项（oc_wake_check.sh sentinel_alert.sh devppl_autopilot.sh close.sh glm_quota_probe.sh）→ S1 需 +1 为 6 项
- `test_deploy_drift.sh` T8 现断言 "5 脚本" 含 glm_quota_probe.sh → 期望需同步更新（唯一既有测试改动，arch §6.3 确认）
- **GLM 额度当前 429/1308 耗尽，RESET_AT=2026-09-01 18:21:02**（arch 事实 4 复核 ✅）——A1 真实 E2E 双绿必须等额度窗口；SUB-1/SUB-2 的验收全部用打桩模式（ENDPOINT_TEST/CLAUDE_CMD=echo），**不阻塞 dev 卡**
- `.glm_shutdown` 当前缺失（停机标记与端点状态窗口差现况，arch 事实 5 复核 ✅）
- claude-code skill 在 game-engine + game-qa 两 profile 均有副本（35324B，含 DeepSeek 段）→ 增补 GLM 直连段
- `deploy_drift_check.sh` 由 autopilot.sh L226 以 repo 路径调用（bash "$REPO_ROOT/scripts/deploy_drift_check.sh"）→ **改它不触发 DPL-048 部署验证**（非 cron 直调、非绝对路径引用；"仅从 repo 路径执行的脚本不适用本规则"）
- ⚠️ **设计张力（评估新增发现）**：arch §2.2 部署目标是 `/usr/local/bin/cc-glm` 软链，但 drift 检测比较 repo `scripts/cc-glm` vs profile `scripts/cc-glm`（orchestrator profile 目录）——cc-glm 需同时进 profile scripts 目录（供 drift 比较）或 drift 脚本需特殊处理软链路径。SUB-2 实现时必须落一个决策（推荐：ln -sf 后同时 cp 到 profile scripts，或按 arch §2.6 "系统软链双份校验" 扩展 drift 判定）。

## 2. 工作量评估（读码结论，非假设）

### 2.1 交付物清单（game-engine S1 范围，≥4 → 触发"一律拆 ~3 卡"口径）

| # | 交付物 | 落点 | 内容 |
|---|--------|------|------|
| 1 | wrapper 引擎 | `scripts/cc-glm`（新增，bash） | key 解析（env → profile .env → 报错指路）/ 启动三检（key 存在/版本==2.0.0/.glm_shutdown 不存在）/ doctor 四检（key/端点 curl/版本/停机标记 + 429 无标记预警）/ 参数契约（默认 -p --model glm-5 --max-turns 30 --output-format json + API_TIMEOUT_MS=600000 + 透传）/ exec env 注入 |
| 2 | 测试套 | `scripts/test_cc_glm.sh`（新增） | T1a-T6b 断言矩阵（12 断言，打桩模式：GLM_KEY_FILE_TEST/SHUTDOWN_MARKER_TEST/CLAUDE_CMD=echo/ENDPOINT_TEST） |
| 3 | 漂移清单 +1 | `scripts/deploy_drift_check.sh`（改）+ `scripts/test_deploy_drift.sh`（改） | DEFAULT_SYNC_LIST 5→6（cc-glm）+ T8 期望同步 |
| 4 | skill 增补 | game-engine + game-qa 两份 claude-code SKILL.md（改） | 「GLM 直连（devPPL cc-glm 通道）」段（arch §5.4 模板） |
| 5 | 部署步骤 | `/usr/local/bin/cc-glm` 软链（部署动作归 OC，S1 只产出步骤/文档） | ln -sf 命令 + 部署说明（arch §2.6） |

### 2.2 两卡工作量分解

| 子卡 | 维度 | 评估 | 依据 |
|------|------|------|------|
| SUB-1（M1） | cc-glm wrapper 本体 + 冒烟 | key 解析（env → HERMES_PROFILE .env → 扫描 profiles/*/.env → 人话报错指路）**1-1.5 轮**；启动三检（key/`claude --version`==2.0.0/.glm_shutdown）+ 版本锁拒绝路径 **1-1.5 轮**；doctor 四检（key/端点 curl 200 或 429 RESET_AT 解析/版本/停机标记 + 汇总行 + 429-无标记预警行）**1.5-2 轮**；参数契约（默认值注入 + 透传 + API_TIMEOUT_MS + 不配三件套）**0.5-1 轮**；exec env 注入 + fail-open/fail-safe 边界（curl 缺失/config 读不到/exit code 语义）**1-1.5 轮**；打桩冒烟（GLM_KEY_FILE_TEST/CLAUDE_CMD=echo 手动验 env 注入与参数）**0.5-1 轮** → **基准 5.5-8.5** | arch §2.3-2.5 伪代码逐段实读；test_glm_quota_probe.sh（30228B）T5 打桩模式先例实读；env 前缀不写 ps 的断言需 shell 细节调试 |
| SUB-2（M2+M3） | test_cc_glm.sh 全矩阵 + drift +1 + skill + 软链步骤 + 门禁 | 测试框架（TMPT/run_cc_glm/四打桩 env）**1-1.5 轮**；T1a-T1b（端点 200/429 RESET_AT）**0.5-1 轮**；T2a-T2b（key 缺指路/注入断言 stdout 无明文）**0.5-1 轮**；T3a-T3d（参数默认/覆盖/版本拒/停机拒）**1-1.5 轮**；T4a-T4b（Brief 5 硬字段/worktree 契约）**0.5-1 轮**；T5a-T5b（门控命令序列/claim 结构校验）**0.5-1 轮**；T6a-T6b（退役条件/回滚窗口文档检查）**0.5 轮**；deploy_drift_check.sh +1 + test_deploy_drift.sh T8 同步 + 回归 **1-1.5 轮**；skill 增补（两份 SKILL.md，§5.4 模板搬运）**1-1.5 轮**；软链部署步骤文档 **0.5 轮**；门禁（test_cc_glm.sh 全绿 + deploy_drift 回归 + pytest 相关 + claim + 飞书）**2-3 轮** → **基准 8.5-13.5** | arch §6.2 断言矩阵逐条实读；deploy_drift_check.sh L42 + test_deploy_drift.sh T8 实读（5→6 期望明确）；skill 双副本路径实确认；⚠️ 设计张力（软链 vs profile 目录漂移比较）需落决策 |

**基准轮数（未校准，合计）：14-22 轮（中位 ~18）。**
**DPL-018 校准：14-22 × K=2.35 → 校准后 33-52 轮**——**超出单卡 42 有效轮预算（上限 52 > 42），
且 >20 轮阈值 → 必须拆卡**；按"4 交付物以上一律拆 ~3 卡"口径拆 2 张（wrapper 引擎 / 测试+集成收尾），
每张落在预算内：
- SUB-1: 5.5-8.5 × 2.35 → **13-20 轮**（13/42 = 31% 起）
- SUB-2: 8.5-13.5 × 2.35 → **20-32 轮**（20/42 = 48% 起）

⚠️ SUB-2 校准后起点 48% 预算——考虑最近 5 卡 timed_out 前科（估 20-41 全撞 60），
这是诚实口径；若 SUB-2 再拆会碎成 3 张微型卡（每张 8-12 轮），串行链延迟反而更糟；
SUB-2 内部可按里程碑排优先级（先 test_cc_glm.sh 核心断言，skill/软链可后置）。

## 3. 复杂度与风险

| # | 风险 | 评级 | 说明与缓解 |
|---|------|:---:|------|
| R1 | **bash 细节调试成本被低估**（env 注入断言、版本锁比较、doctor curl 解析、exit code 语义） | 高 | 历史 timed_out 主因（5 卡全撞 60）。缓解：SUB-1 打桩冒烟先行（CLAUDE_CMD=echo 断言参数/env），不碰真实 claude；每个检查点单独小测再组装 |
| R2 | **GLM 额度窗口阻塞真实 E2E**（RESET_AT=18:21:02） | 中 | dev 卡验收全部打桩（ENDPOINT_TEST=1 不发网络请求）；真实 A1 双绿放 S2/OC（额度窗口后重放 arch §6.4）——**dev 卡不阻塞**，但 claim 必须注明"真实端点验证待 S2" |
| R3 | **cc-glm 软链 vs drift 比较目录的路径张力**（评估新增发现） | 中 | arch §2.2 部署目标 /usr/local/bin，drift 比较 repo scripts/ vs profile scripts/。缓解：SUB-2 落决策——推荐 `ln -sf` + 同时 cp 到 profile scripts（双份一致），或按 arch §2.6 扩展 drift 脚本支持软链校验（后者改动面更大，倾向前者） |
| R4 | **版本锁的 npm/nvm 环境漂移**（claude update 静默换版本） | 中 | wrapper 启动校验精确 ==2.0.0 已设计；SUB-1 测试覆盖 T3c（CLAUDE_VERSION=2.1.0 打桩 → 拒绝） |
| R5 | **must-sync +1 触发部署验证规则**（DPL-048 误判） | 低 | 实测 deploy_drift_check.sh 由 autopilot 以 repo 路径调用（非 cron 直调/非绝对路径引用）→ 不适用部署验证规则；但 .hermes.md 规则读者可能误判，SUB-2 claim 注明依据 |
| R6 | **A1-A6 验收依赖 OC 侧 S2**（部署+E2E+首单验证） | 中 | dev 卡只交付"可验证的构建物"（wrapper 可跑、测试全绿、skill 段在）；A5 首单 CC 代工闭环天然在 S2——SUB-2 claim 明确交接面，防 VA 误判 dev 卡未完成 |
| R7 | 本卡 est 产物自身 code-not-in-main | 中 | 评估产物在 wt/t_a5c7400d 分支，落 main 需后续 MERGE 卡（先例 t_est_52c4a9c1 → t_ab21ecc4）。缓解：[PRODUCES] 给 OC 明示，由 OC 派 MERGE 卡追回 |
| R8 | claim 格式（DPL-060） | 低 | 两张子卡 claim 必带 changed_files 段；SUB-2 含 skill 增补（profile 路径，非 repo 内）→ claim 同时列 repo 内改动与 profile 侧改动路径 |

## 4. 拆卡决策

| 判定 | 结果 |
|------|------|
| 基准轮数 | 14-22 轮（中位 ~18） |
| DPL-018 校准后 | 33-52 轮（×K=2.35）**> 20 轮阈值 且 上限 > 42 预算 → 必须拆卡** |
| 交付物数 | 5（wrapper / 测试套 / drift+1 / skill 增补 / 部署步骤）≥ 4 → 拆卡（机制口径） |
| 单卡方案复算 | 2 张串行：SUB-1 13-20 / SUB-2 20-32，全部 < 42 有效轮 ✅（SUB-2 上限贴线，按里程碑排优先级兜底） |
| 依赖方向 | SUB-1（wrapper 引擎）→ SUB-2（测试需 wrapper 存在才能跑 + 集成收尾）→ **串行** |
| 并行收益 | 低——SUB-2 的 test_cc_glm.sh 直接依赖 SUB-1 的 scripts/cc-glm；同仓同文件（scripts/ 目录）并行会互相覆盖 |
| 与 arch 建议对齐 | arch §7.1 建议 S1(game-engine)+S2(OC) 两卡；本评估将 S1 细拆为 SUB-1/SUB-2（同 profile 两段），S2 保持 OC 部署+E2E+首单验证——**不改变 arch 总体串行链**，只把 game-engine 工作量控制在预算内 |
| 兜底 | SUB-1 超预算：key 解析+三检先行交付，doctor 四检可切 SUB-2；SUB-2 超预算：skill 增补/软链步骤可切 S2（OC 部署时顺带），测试矩阵可精简到 T1-T4 核心断言（T5/T6 是流程文档检查，成本低但可后置） |

**决策：拆 2 张串行子卡（[SUB-SPLIT] 2 serial）。**
量级参照：t_569d4425（DPL-087，3 文件改造拆 2 卡）；t_1db58772（跨仓改造拆 2 卡）；
本任务 1 新脚本 + 1 新测试 + 2 改 + 2 skill，是 MEM-013（10+4+2 写点 + 引擎 + 4 测试文件）的
1/3 量级，2 卡粒度与"引擎 / 测试+集成"自然分段对齐，也与 arch §7.1 S1 的 5 项交付物映射
（M1→SUB-1，M2+M3→SUB-2）。

## 5. 对 autopilot 的建议（[SUB-SPLIT] 结构化）

```
[SUB-SPLIT] 2 serial
1. [DEV-SUB-1] DPL-101 M1 — scripts/cc-glm wrapper 本体（key 解析/三检/doctor 四检/参数契约）：
   新增 scripts/cc-glm（bash，零外部依赖：bash+curl+claude，chmod +x）；
   key 解析顺序（env GLM_API_KEY → $HOME/.hermes/profiles/<HERMES_PROFILE>/.env →
   扫描 profiles/*/.env 首个含 GLM_API_KEY → 缺则 exit 1 人话指路"哪个文件哪个变量"）；
   启动三检（① key 存在 ② claude --version 精确==2.0.0 否则拒绝并给出 npmmirror 锁版本命令
   ③ /workspace/devPPL/.glm_shutdown 存在则拒绝并输出 RESET_AT）；
   doctor 四检（key/端点 curl /api/anthropic/v1/messages 200 或 429 RESET_AT 解析/版本/停机标记，
   汇总行 KEY=... ENDPOINT=... VERSION=... SHUTDOWN=...，429-无标记时追加 DPL-099 交叉引用提示）；
   参数契约（默认 -p --model glm-5 --max-turns 30 --output-format json + API_TIMEOUT_MS=600000 +
   用户参数覆盖透传；不配 ANTHROPIC_DEFAULT_*_MODEL 三件套）；
   exec env 注入（env ANTHROPIC_BASE_URL=... ANTHROPIC_API_KEY=... claude ...，key 不出现在
   ps/claim/日志）；fail-open 与 fail-safe 分离（doctor 自身故障人话报错 exit 非零；
   停机检测拒绝派发 fail-safe）；
   打桩冒烟（GLM_KEY_FILE_TEST/SHUTDOWN_MARKER_TEST/CLAUDE_CMD=echo 手动验证 env 注入与参数契约）。
   预计 13-20 轮
2. [DEV-SUB-2] DPL-101 M2+M3 — test_cc_glm.sh T1-T6 全矩阵 + drift +1 + skill 增补 + 软链步骤 + 门禁：
   新增 scripts/test_cc_glm.sh（打桩模式：GLM_KEY_FILE_TEST/SHUTDOWN_MARKER_TEST/CLAUDE_CMD=echo/
   ENDPOINT_TEST，TMPT 隔离，仿 test_glm_quota_probe.sh T5）；
   T1a-T1b（doctor 端点 200/429 RESET_AT）T2a-T2b（key 缺人话指路/env 注入断言 stdout 无明文）
   T3a-T3d（默认参数/用户覆盖/版本≠2.0.0 拒绝/停机标记拒绝）T4a-T4b（Brief 5 硬字段模板/worktree 契约）
   T5a-T5b（门控命令序列出现/claim 含 changed_files+executed_via+cc_num_turns+cc_cost_usd）
   T6a-T6b（§5 退役条件+动作清单存在/14 天回滚段存在）；
   deploy_drift_check.sh DEFAULT_SYNC_LIST 5→6（cc-glm）+ test_deploy_drift.sh T8 期望同步 + 回归；
   /usr/local/bin/cc-glm 软链部署步骤文档（ln -sf + 同时 cp 到 orchestrator profile scripts 供 drift
   比较，或按 arch §2.6 双份校验——实现时落决策，评估倾向前者）；
   game-engine + game-qa 两份 claude-code SKILL.md 增补「GLM 直连（devPPL cc-glm 通道）」段
   （arch §5.4 模板）；
   门禁：test_cc_glm.sh 全绿 + test_deploy_drift.sh 回归 + 相关 pytest + claim（changed_files 段 +
   注明"真实端点 A1 双绿待 S2/OC 额度窗口后重放"）。
   预计 20-32 轮
```

## 6. 备注

1. **本卡不写功能代码**；产出即本报告 + [SUB-SPLIT] 2 serial comment + [PRODUCES] claim，
   autopilot 按 count=2 建 2 张串行 [DEV-SUB] 子卡执行（parents=[t_a5c7400d]）。
2. **S2 归属明确**：arch §7.1 的 S2（OC：merge + 部署软链 + cc-glm doctor 四检 + A1 双绿重放 +
   真实 >25 轮卡首单 CC 代工验证 + 退役计时 + 开放问题交 Frank）不属于 game-engine dev 范围，
   本评估只拆 dev 卡；S2 由 OC 按 arch 派发（部署动作永远留给 OC，研发只负责 repo 正本）。
3. **额度窗口不阻塞 dev 卡**：GLM 双端点当前 429/1308（RESET_AT=18:21:02），但 SUB-1/SUB-2 验收
   全部打桩（ENDPOINT_TEST/CLAUDE_CMD=echo），真实 A1 双绿留 S2 重放 arch §6.4 两条命令。
4. **R3 设计张力是 SUB-2 的决策点**：arch §2.2 部署目标是 /usr/local/bin/cc-glm 软链，但
   deploy_drift_check.sh 比较 repo scripts/ vs profile scripts/ 目录——若只建软链不 copy profile，
   drift 检测会报 cc-glm repo≠profile（repo 有 profile 缺）。推荐 ln -sf + cp 双份（drift 语义
   与部署语义都满足）；若走 arch §2.6 "系统软链双份校验" 需改 drift 脚本比较逻辑，改动面 +0.5-1 轮。
5. **DPL-048 部署验证不适用**（实测依据）：deploy_drift_check.sh 由 autopilot.sh L226 以 repo 路径
   bash "$REPO_ROOT/scripts/deploy_drift_check.sh" 调用——非 jobs.json script 直调、非绝对路径
   /root/.hermes/profiles/orchestrator/scripts/ 引用；cc-glm 同理（worker terminal 调用，非 cron 前置）。
   SUB-2 claim 需注明该依据，防 .hermes.md 规则读者误判。
6. **skill 增补是 profile 侧改动**（不在 devPPL repo 内）：SUB-2 claim 的 changed_files 需同时列出
   repo 内（scripts/test_cc_glm.sh + deploy_drift_check.sh + test_deploy_drift.sh）与 profile 侧
   （game-engine/game-qa 两份 SKILL.md）路径；VA 验证逻辑零改动。
7. **A5 首单闭环在 S2**：SUB-2 的 T5a-T5b 只校验"门控命令序列 + claim 结构"（打桩断言），
   真实首单 CC 代工（Brief → cc-glm → 门控 → claim + executed_via → VA [VERIFIED]）是 S2 的线上验证，
   dev 卡不承担——防 VA 误判 dev 卡未完成 A5。
