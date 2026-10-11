# 工作量评估 — t_3cb55dfc（close 门禁 fail-closed 改造）

评估卡: t_est_3cb55dfc | 评估人: game-engine | 日期: 2026-09-29

## 1. 需求摘要

exec_chain_close（pipeline/cmd_chain.py:3164）当前准入锚为 _parse_dev_key（链棒格式 idempotency_key），OC 手建卡（oc-* key）解析不出链 → 门禁不可见 → complete 即 done 无合并校验。回滚三例：t_ebce9fab / t_75c05b96 / t_6a051c8e。

改造：准入改锚到 title 前缀（[DEV]/[FIX]/[PRD]/[DEV-MERGE]/[DEV-CLOSE]，含组合前缀），豁免=body 行首「门禁豁免: <理由>」；证据校验 git grep 符号 @ main（符号取「功能核验: <符号> @ main」行，DPL-145 同构）；缺符号行查 git diff main --name-only / 同名 worktree，非空即 blocked 要先 MERGE（fail-open 不死锁）；oc_wake_check.sh 增固定扫项 [close-gate-violation] + SQL 踢回 ready；oc_create_card.sh 强制生成核验占位行缺行拒绝；wiki §8.5 增 fail-closed 条款。

## 2. 实勘结论（已核，勿重复勘）

- exec_chain_close 现有 5 道门禁（S6' / REGISTRY-GAP / CARD-GAP / BKP-GAP / WIKI-GAP），本改造在入口处新增「准入判定 + 符号核验」两段，形态与既有 gap 模式（幂等 comment + blocked）完全一致，可复用 _comment_gap_sql。
- oc_create_card.sh 已有 DPL-145 BLOCK-1 功能核验门禁（129-175 行）成熟模板（豁免行 grep + 拒绝 + fail-open），新建卡侧门禁可照抄结构，改前缀集合即可。
- oc_wake_check.sh（1670 行纯 bash）已有同类扫项结构，新增一项检查 + SQL 踢回（sqlite3 UPDATE）。
- 测试基础：tests/test_chain_registry.sh 已有直调 exec_chain_close 的 harness（temp DB 路径注入），test_dpl173_oc_wake_blocked_still.py 是 wake 扫项测试先例。
- 注意：oc_wake_check.sh 是 cron 前置脚本 → 验收须含部署验证（repo vs /root/.hermes/profiles/orchestrator/scripts/ diff 一致才 PASS，研发只交 repo 正本）。

## 3. 工作量分解

| 项 | 内容 | 预估轮次 |
|---|---|---|
| A | cmd_chain.py 准入改锚（前缀集合判定 + 豁免行解析 + 符号核验 + fail-open blocked） | 5-7 |
| B | oc_wake_check.sh 扫项（done 卡无豁免无符号在 main → [close-gate-violation] + 踢回 ready） | 4-5 |
| C | oc_create_card.sh 强制核验占位行（仿 DPL-145） | 2-3 |
| D | wiki kanban-card-format.md §8.5 fail-closed 条款 | 1 |
| E | T1-T6 测试（回归三例形态 / 合规 / 豁免 / 组合前缀 / 建卡拒绝 / 既有测试不回绿退） | 5-6 |

合计：17-22 轮

## 4. 决策

**临界判定：≤20 → 不拆，[SUB-SPLIT] 1，源卡直跑。**

依据：四点改动高度关联（同一门禁语义的四个消费侧），拆卡会造成上下文重复加载与语义漂移，反增总轮次；A 项若超预期，B-E 可在剩余预算内收敛（B/C 有成熟模板）。

## 5. 风险点

- exec_chain_close 是 close 唯一汇聚点，回归面大 → T6 必须跑 test_chain_registry.sh + test_dpl056_chain_gate.py + drill_autopilot_chain.sh 相关子集（只跑本卡子集，不跑全量）。
- 前缀判定需覆盖组合前缀（[FIX][DEV]）与 [DEV-MERGE]/[DEV-CLOSE] 的歧义边界，T4 专测。
- 落 main 顺序：先 t_ae0975fc 后本卡，rebase 即可（卡面边界已声明）。
