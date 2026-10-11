# 评估卡 → 子卡拆分机制设计

> Frank 2026-08-12 提出：超时问题从执行层移到规划层解决。
> 研发/测试在执行前先评估工作量、给出拆卡建议，autopilot 按建议建子卡。

## 问题背景

当前超时根因：`agent.max_turns=60`，复杂任务单卡 60 轮跑不完 → gave_up → blocked。
靠 agent 自己"更快"很难根治——任务复杂度是客观的，单会话预算有限。

## 核心思路

**与其等执行超时，不如执行前就拆分。** 评估卡只评估不写代码，产出子卡拆分建议，
autopilot 按建议建卡。每张子卡工作量控制在单会话预算内（≤20 轮），从源头消除超时。

## 流程设计

### 研发评估卡（[DEV-EST]）

```
PRD done → 架构 done → [DEV-EST] 研发评估卡（不写代码）
    ├─ 读 PRD + 架构 + 开发计划
    ├─ 评估工作量：预计轮数 / 复杂度 / 风险点
    ├─ 决策：≤20 轮 → 不拆，直接标注"单卡可完成"
    │        >20 轮 → 拆，给出子卡建议
    ├─ 产出: docs/est/<task>-estimate.md（评估报告）
    │       + [SUB-SPLIT] comment（结构化建议，autopilot 可解析）
    └─ 完成后 → autopilot 读取建议：
        ├─ 不拆 → 建 1 张 [DEV-DEV] 开发卡（原逻辑）
        └─ 拆   → 建 N 张 [DEV-SUB-1..N] 子卡
```

### 测试评估（并入 qa-d1 测试用例步骤）

```
[DEV-DEV] done → [QA-D1] 测试用例设计（已有步骤）
    ├─ 写测试用例（原职责不变）
    ├─ 顺便评估测试执行工作量：预计轮数 / 用例数 / 复杂度
    ├─ 决策：≤20 轮 → 不拆；>20 轮 → 拆
    ├─ 产出: [QA-SUB-SPLIT] comment（测试子卡建议）
    └─ 完成后 → autopilot 读建议：
        ├─ 不拆 → 建 1 张 [QA-EXEC]（原逻辑）
        └─ 拆   → 建 N 张 [QA-SUB-1..N] 执行子卡
```

### 子卡执行模式

| 模式 | 机制 | 适用 |
|------|------|------|
| **串行** | parents 依赖：父卡 done 才派发下一张 | 子卡间有依赖（模块 A → 模块 B）|
| **并行** | 多张 ready 子卡同时派发（dispatcher 支持） | 子卡间无依赖（独立模块）|

**dispatcher 并行能力已验证**：`kanban.max_in_progress_per_profile` 默认 null（不限），
同一 profile 可同时跑多张 ready 卡（gateway/kanban_watchers.py L903-930）。

## 参数（Frank 2026-08-12 确认）

1. **子卡粒度**：≤20 轮/张（max_turns=60 的 1/3，留安全余量）✅
2. **并行上限**：同 profile **最多 3 张**同时跑（Frank 明确；⚠️ 之前 GLM 配额被并行耗尽过，
   实现时并行逻辑带配额感知或至少留观测点）
3. **评估卡复核**：**不设复核**，研发自评（自评自己工作量，合理）✅

## 防超时兜底（评估卡本身也要防）

- 评估卡工作量一般远小于开发卡（读文档 + 估算，不做实现），60 轮足够
- 若评估卡也超时 → 说明任务连"评估"都复杂到爆，此时应提示 Frank 人工介入拆解
  （比开发卡超时更有价值的信息：任务本身过于庞大）

## 实现位置（预估）

- `pipeline/cmd_chain.py`: DEVELOPMENT_CHAIN 增加 dev-est 步骤（或作为 prd→dev 间的可选步骤）
- `scripts/cmd_channel.sh`: [CMD] create dev 消费时解析评估建议
- `pipeline/state.py`: advance_pipeline 增加"读评估建议 → 建子卡"的 fanout 逻辑
- `docs/est/`: 评估报告目录
- 测试: test_cmd_channel.sh 增加评估→拆卡链路用例

## 与现有机制的关系

- 智能跳步（t_7b2781ec 已完成）：--skip 机制可跳过评估卡（任务小、明确不拆时）
- 迭代修复：缺陷修复默认不拆（小改动），直接 dev 卡
- claim/VA/QA 硬约束不变：子卡也要走 claim + VA 验证

## 预测公式：总轮次 ≠ 实现轮次（DPL-136 链，t_35dffbf6）

**病根**：t_b4014d10 est 评估「8-12 轮 buffer 15」只估实现轮次，实际 run1 烧满 60 轮
timed_out（t_b185e090 同型，run1 同样 timed_out）——超预估 5 倍。评估遗漏的固定项：

**总轮次 = 实现轮次 + 收尾链固定预算（+8 轮） + 回归测试轮次（按套件实测耗时折算）**

| 分项 | 量级 | 依据 |
|------|------|------|
| 实现轮次 | 按任务本身估 | 原有评估口径，仍然成立 |
| 收尾链固定预算 | **+8 轮**（首轮保守值，靠 DPL-018 偏差闭环实测校准） | merge 后验证 / WIP 笔记 / claim 文件 / finalize 四步 / 飞书推送 ≈ 固定 6-10 轮，实证样本两卡均在此区间超时 |
| 回归测试轮次 | 按套件实测耗时折算（如 test_notify_check 46-73s/遍 × 预计遍数） | 套件慢是隐性轮次消耗源 |

- 注入方式：`pipeline/constants.py` `EST_TAILCHAIN_LINE` 常量，三处评估模板注入点
  （cmd_chain dev-est 块 / discover `_create_est_card` / discover 触发器 SQL）同步追加——
  模板是三副本，漏一处 = 该路径评估卡看不到新口径（先例：EST_EFFECTIVE_LINE 曾触发器缺失）。
- 部署注意：触发器是 `CREATE TRIGGER IF NOT EXISTS`，已装的 live 触发器不自动更新，
  需 DROP + CREATE 重建后验证新 est 卡 body 含收尾链行。
- 回测基线（首轮）：新公式对 t_b4014d10/t_b185e090 预估 ≈18-23 轮 vs 实际 60-75 轮，
  单靠固定项难命中 ±30%——持续校准依赖 DPL-018 偏差闭环数据，不指望本卡一刀达标。
