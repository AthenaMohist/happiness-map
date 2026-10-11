# 工作量评估 — t_51a7af45（[MERGE] 标签整理 Round 2 → main）

## 1. 源需求
将 wt/t_2b4c6441（标签体系整理 Round 2，方案A v1.1）并入 InfoManager main，标准合并闭环：备份三件套 push → merge → 实锤验证 → push main → 删已合并分支。

## 2. 实测校准（2026-09-06 现场侦查）
- 真实仓库：/workspace/InfoManager（origin=git@github.com:AthenaMohist/InfoManager.git）；注意 devPPL worktree 不是该 repo
- 分支：wt/t_2b4c6441 @ d12a6ea 已在本地 + 远端（fetch 实锤）；主 commit 3d12502 + 收尾 d12a6ea
- 领先 origin/main 的 commit：d3d7325, 67b2a56, 3d12502, d12a6ea（4 个，含 2 个 WIP）
- 物料在位：config/tags.yaml、backups/t_2b4c6441_tags_diff.patch、scripts/_t2b4/（accept.py/check_diff.py/common.py/finish.py）
- 本地 main=88be221（[ahead 1]，est 文档 commit，尚未 push）
- 前置实锤（OC 已复核）：diff 113 文件，96+3 篇 md 仅动 tags 行；accept.py 独立复跑 PASS（377 篇、白名单外=0）

## 3. 工作量
- 预计轮数：**8–14 轮**（buffer 至 18）
  - 备份三件套 push（repo 远端 push 必须 rc=0）：2–3 轮
  - merge wt/t_2b4c6441 → main（非 fast-forward，真 merge commit）：1–2 轮
  - 合并后实锤验证（git show main:config/tags.yaml + accept.py 复跑 PASS + 祖先检查）：2–3 轮
  - push main + 删分支（本地+远端，删前验祖先）：2–3 轮
  - 收尾（finalize + claim + 飞书）：1–2 轮
- 复杂度：低-中。机械操作为主，但 push 链路（SSH key 绝对路径）与"Already up to date 不算数"验证点是风险位
- 风险点：
  1. SSH push 需 GIT_SSH_COMMAND 绝对 key 路径（已知坑，memory 有记录）
  2. 本地 main ahead 1（88be221 est 文档）——merge 前先一并 push/备份，避免丢失
  3. accept.py 复跑需在 main checkout 下跑（InfoManager 主工作树当前在 wt/t_2b4c6441，需临时切 main 或用独立 worktree）

## 4. 决策
预计 ≤20 轮 → **不拆卡**，[SUB-SPLIT] 1 serial。
