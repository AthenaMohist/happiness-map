# 工作量评估 — t_97a2b3eb（DPL-109 白名单 cc-glm wrapper 合入 main + live 验证）

- 评估卡: t_est_97a2b3eb | 源任务: t_97a2b3eb
- 日期: 2026-09-03 | 评估人: game-engine

## 1. 源需求摘要

ARCH t_4d03d75a（arch-ccmax-execution-mode.md §6）落地前置：白名单版 cc-glm wrapper 必须在 main 生效。当前实况（本卡实测确认）：

1. main 的 scripts/cc-glm（0b03d1a 线）不含 `--permission-mode acceptEdits` / `--allowedTools` 注入。
2. 白名单注入完整存在于分支 `wt/t_dceecf1d`（d752e69 注入 + 42ea615 空串回退语义修复 + 38181cf B7/B8 测试 + 196edb0 顺带修复）。**实测：main HEAD 8ab8d02 就是 wt/t_dceecf1d 的 merge-base（ancestor），分支无分叉 → 可直接 merge/ff，冲突面极小。**
3. main 工作区有一份未提交改动（`git status`：M scripts/cc-glm + D .glm_shutdown）。

## 2. 未提交改动处置评估（任务 1）

diff 内容实测：把主路径从「运行→捕获→解析 session_id→回放 + session_log_file 指针」（DPL-106 第六字段，commit 0b03d1a）**回退为直接 exec**，并新增 `ANTHROPIC_MODEL=glm-5` env 注入；同时删除 .glm_shutdown。

判断：
- 该改动**摧毁 DPL-106 第六字段契约**（d8b_claim_check 的 cc_session_log isfile 校验依赖 session_log_file 注入），且丢弃白名单版分支上的全部成果。
- 时间线（reflog）显示它生成于 glm-shutdown checkpoint 时期（8ab8d02），来路疑似某次 GLM 停机窗口的临时回退实验，无对应卡。
- `ANTHROPIC_MODEL=glm-5` 的意图（防 CLI fallback）有价值但未经验证、未过测试；白名单版已有 `--model glm-5` argv 锁定。

**处置建议：丢弃（git checkout -- scripts/cc-glm && git checkout -- .glm_shutdown）**，在源卡 comment 留痕即可，不拆卡、不保留。若 ANTHROPIC_MODEL 锁模型确有需求，应另立小卡走验证流程，不夹带。

## 3. 改动面与步骤盘点（任务 2-5）

| 步骤 | 内容 | 预计轮次 |
|---|---|---|
| S1 | 源卡 comment 处置未提交改动 + 丢弃 | 1 |
| S2 | 新 worktree 分支 merge wt/t_dceecf1d → main（含 B7/B8 测试与 oc_wake_check 修复，同分支交付） | 2-3 |
| S3 | STATIC 全量回归（test_cc_glm.sh + smoke_cc_glm.sh，分支上已全绿，main 视角复核） | 1-2 |
| S4 | `cc-glm doctor` 四检（symlink 指向 main 工作区文件，合并后自动生效） | 1 |
| S5 | **Live 验证**：真实 `cc-glm -p` 让 cc 执行 pytest/git 动作，确认白名单放行 + GLM 端点连通（DPL-101 v1.2 A5 口径），留 session jsonl/输出 JSON 证据 | 2-5 |
| S6 | commit + claim/VA 流程 | 2 |

合计 **9-14 轮**。

## 4. 风险点

- R1 live 验证受 GLM 端点窗口影响（429/SHUTDOWN 时 DPL-099 需 block 等窗口）——代码交付不阻塞，验收门禁后两条需端点健康。
- R2 merge 本身低风险：分支是 main 的直接后代（已实测 merge-base = main HEAD），唯一注意点是合并前必须先清掉 main 工作区未提交改动（S1 前置）。
- R3 部署验证：/usr/local/bin/cc-glm 是 symlink → main 工作区文件，合并即生效，无 live 副本 drift（不同于 DPL-048 orchestrator scripts 场景）；仍需 doctor 实测确认。
- R4 沙箱镜像备份为系统机制类事项（源任务第 5 条），不占本卡轮次，随 claim 留痕。

## 5. 拆分决策

**≤20 轮 → 不拆卡（[SUB-SPLIT] 1 serial）**。改动=一次快进式 merge + 验证链，串行一次交付即可；唯一变量是 live 验证的端点窗口，属等待而非工作量。
