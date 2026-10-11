# 智能跳步机制设计

> Frank 2026-08-11 裁定：流程是参考不是铁律，autopilot 必须能根据上下文智能裁剪步骤。

## 核心原则

**一个步骤可跳过 ⟺ 它的产物已存在且可信 OR 它的操作对象不存在**

## 三个例子 → 提炼的规则

| 场景 | 产物/对象状态 | 可跳步骤 | 原因 |
|------|-------------|---------|------|
| brainstorming 已产出 PRD + 架构 + 开发计划 | PRD、架构图已存在 | prd, arch | 产物已存在 |
| QA 发现缺陷，研发修复 | 缺陷在现有设计范围内 | prd, arch | 修复不改变设计 |
| 研发直接改了 main | 代码已在 main，无 worktree 分支 | merge, qa-post, va-post | 合并对象不存在 |

## 不可跳步骤（硬约束）

这些步骤的价值在**独立验证**本身，不在产出物，因此永远不能跳：

| 步骤 | 为什么不可跳 |
|------|-------------|
| dev | 研发交付声明（claim 的载体） |
| va-claim | VA 独立验证研发 claim |
| qa-d1 | 测试方案 |
| qa-exec | 测试执行 |
| qa-d2 | 测试评审 |
| va-qa | VA 验收 QA 结果 |

## 数据结构

```sql
CREATE TABLE IF NOT EXISTS chain_config (
  spec_hash TEXT PRIMARY KEY,
  skip_steps TEXT NOT NULL DEFAULT '[]',  -- JSON array
  reason TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);
```

## 三种触发方式

### 1. 显式指定（建卡指令）
```
[CMD] create dev <topic> --skip prd,arch
```
→ cmd_chain.py 解析 body 中的 `--skip` 参数

### 2. 迭代修复自动检测
- advance_sequential_chains 发现同 spec_hash 有 done 的 dev 卡
- 且当前是 QA/VA 发现的缺陷修复
- → 自动设置 skip_steps=["prd","arch"]

### 3. 合并跳步自动检测
- exec_chain_merge 检测到无 worktree 分支（`git rev-parse wt/<dev_id>` 失败）
- → skip merge/qa-post/va-post，只走 close

## 卡链可视化中的跳步标记
- 跳过的步骤显示 ⏭️（不是 ⏰）
- 在 format_chain_visual 里查询 chain_config 获取 skip_steps
