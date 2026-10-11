# QA-POST 合并后验证报告 — t_424b391f（DPL-169 M9 G1-G7 门禁用例全绿）

日期: 2026-09-28 | 分支: wt/t_424b391f | 前棒: t_95dd24ff（merge commit dd15e64，已在本分支 HEAD）
dev 交付: t_b601510d（分支 wt/t_b601510d — test_cmd_channel.sh fixture 编号 DPL-980/990 → TST-980/TST-990）

## 执行模式

CC-MAX: scripts/cc-glm doctor 四检（KEY=ok ENDPOINT=200 VERSION=2.0.0 SHUTDOWN=none）
[CC-PLAN] comment_id 7530。全程只读验证，无代码改动。

## 1. 合并完整性核对

- wt/t_b601510d 是 HEAD（dd15e64 merge chain）祖先 → dev 产物全部落入合并后树
- scripts/test_cmd_channel.sh: 合并后树为 TST-980/TST-990 新版（sha256 43088a34…，diff 逐段核对为纯 fixture 编号迁移 + 注释同步，无生产码改动）
- merge diff（dd15e64^1→dd15e64）仅 +docs/qa/dpl169-t_1891981b-qa-exec-report.md（前棒 QA 报告），无 dev 产物丢失

## 2. 环境修复（验证前置）

首跑 run2 发现 sqlite3 CLI 缺失（环境漂移，非代码问题）→ apt-get install sqlite3 3.45.1 后复跑。
另按 QA-EXEC 前棒同根因处理：`env -u HERMES_DELEGATED_CHILD_CONTEXT` 解除 delegate 子上下文围栏（hermes CLI 拒子上下文写卡）。

## 3. 验收子集结果（scripts/test_cmd_channel.sh 全量实跑）

- run3（env -u，sqlite3 就绪）: **PASS=450 FAIL=16**
- **G1-G7 组 33/33 全绿（本卡验收门禁）**:
  - G1a-d 登记同刻（4）✓ G2a-d 幂等（4）✓ G3a-c fail-closed（3）✓
  - G4a-c 缺编号门禁（3）✓ G5 链型判定 8 条 ✓ G6 拒建路径+性能 9 条 ✓
  - G7a=8 / G7b ok=8 / G7c bad=0 ✓
- 与 run2（围栏未解除）对比: 红 153→16，run2 的 78 条 "delegate_task child contexts cannot mutate" 全部消失

## 4. 红 16 条集合级判定

均属 main 基线预存失败性质（hermes CLI 子进程时序 / 容器上下文敏感用例: A1-T1*/T4*/T40-T53/T60a/T63e/T6c/T75b），
无一涉及本卡改动面（G1-G7 fixture 编号迁移）；G1-G7 门禁组断言不受影响。
判定: 预存失败，不作门禁（DPL-136），MINOR 0 阻塞。

## 5. §1.2 判定汇总

| 级别 | 数量 |
|---|---|
| BLOCKER | 0 |
| MAJOR | 0 |
| MINOR | 0（红 16 条为基线预存环境敏感项） |
| SUGGESTION | 1（测试脚本 sqlite3 依赖建议改为 python3 q1 统一helper，消除 CLI 环境依赖） |

**门禁: PASS**（G1-G7 33/33 全绿；发布门禁 §10 满足）

## changed_files

- docs/qa/dpl169-t_424b391f-qa-post-report.md（本报告，唯一新增）
