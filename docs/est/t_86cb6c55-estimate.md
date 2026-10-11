# 工作量评估 — t_86cb6c55（[MERGE] DPL-106 wt/t_407d67a6 → main）

评估卡: t_est_86cb6c55 · 2026-09-02 · 评估人: game-engine (dev-est)

## 1. 源任务需求
按合并纪律六步执行：
1. incremental_backup.py 备份先行
2. merge wt/t_407d67a6 → main（--no-ff）+ cat-file 逐文件完整性
3. main 上 QA：test_cc_glm.sh STATIC 49/49 + BEHAVIOR 12/12；a5_verify 六件套对 t_9b1b3301（历史五字段卡 ②⑤ 预期红，注明即可）
4. S2 双份同步：cp scripts/cc-glm → orchestrator live 副本 + md5 一致
5. /usr/local/bin/cc-glm 软链核验
6. 结构化 claim

## 2. 实测合并拓扑
- 源 commit 50f1645 @ wt/t_407d67a6，merge-base = 8803308 = main 链内祖先（main tip cd3028e 已含）
- diff 范围 5 文件 +141/-10：scripts/{cc-glm, d8b_claim_check.py, test_cc_glm.sh, a5_verify.sh} + .pipeline/wip/t_407d67a6.md
- 上游 wt/t_407d67a6 已全绿（BEHAVIOR 12/12 + STATIC 49/49 + d8b exit 0），合并应为零冲突 fast-forwardable --no-ff

## 3. 工作量评估
- 预计轮次：12-19 轮（merge 2-3 + QA 回归 5-8 + S2 同步/软链 2-3 + claim/complete 3-5）
- 复杂度：低——零冲突合并，脚本已在上游验证，main 上只做回归
- 风险点：
  - a5_verify 六件套对历史五字段卡（t_9b1b3301）②⑤ 预期红 → 属向后兼容预期，报告注明，不算失败
  - S2 live 副本同步属系统目录写入，需 md5 复核确认生效
  - 轮次存档：50 轮阈值远未触及，无拆分必要

## 4. 决策
预计 ≤20 轮 → **不拆卡，[SUB-SPLIT] 1 serial**（整卡由单个 game-engine run 完成）。
