# MEM-009 QA 产品落地 main — 合并后全量回归 + 验收报告（DPL-083 SUB-2 / DPL-084）

> 版本：v1.0 | 日期：2026-08-20 | 作者：game-engine（DPL-084 SUB-2 独立回归验收）
>
> 任务卡：t_4db0eb2d [DEV-SUB-2] t_66e31a89 — 源分支 wt/t_2fc5fd0a / wt/t_f91a64c5 / wt/t_ac88ed89 / wt/t_48a3dd47 / wt/t_de9e75df
> 上游：评估卡 t_est_66e31a89（拆 2 serial）→ SUB-1（t_2e8cfc8b，12 文件逐文件 checkout 合并 main，merge 72156df）→ 本卡全量回归
> 被测状态：devPPL main @ `72156df`（merge(mem009) 12 文件逐文件 checkout，DPL-083 SUB-1）
> 验收依据：评估卡 t_est_66e31a89 body「验收」五条 + [SUB-SPLIT] SUB-2 子任务描述

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **验收 1：mem009 文件全命中** | ✅ `git ls-tree -r main --name-only | grep -E "mem009"` = **7 命中**（docs/qa 5 报告 + scripts 2 探针） |
| **验收 2：wip 笔记在 main** | ✅ 5 份 .pipeline/wip/t_{2fc5fd0a,f91a64c5,ac88ed89,48a3dd47,de9e75df}.md 全部在 main |
| **验收 3：无回退（保护文件零改动）** | ✅ 合并提交 72156df diff vs first parent d6682b5：**仅 12 文件新增**（1851 insertions），无 D/M；pipeline/discover.py / scripts/oc_wake_check.sh / scripts/test_va_backfill.sh **零改动**（无假删除回退） |
| **附加：无夹带混入** | ✅ 合并 diff 不含 .pipeline/gai/*、manifest.jsonl、.pipeline/archive/*（wt/t_2fc5fd0a 夹带风险零带入） |
| **附加：blob 一致性** | ✅ 12 文件 blob hash 与源分支（wt/t_2fc5fd0a / t_f91a64c5 / t_ac88ed89 / t_48a3dd47 / t_de9e75df）**12/12 一致** |
| **验收 4：三套回归（main 上，独立执行）** | ✅ test_va_backfill.sh **91/91** + test_watchdog_unify.sh **28/28** + test_wip_progress_check.sh **94/94** 全绿，退出码全 0 |
| **验收 5：claim 带 changed_files 段** | ✅ 见本卡 [CLAIM] comment（DPL-060） |
| **部署验证（DPL-048）** | 不适用：目标 12 文件均为新增 QA 产品（报告/探针/wip 笔记），非 cron 前置脚本、非 must-sync 清单；oc_wake_check.sh 未改动 |

**结论**：SUB-1 合并正确——12 个 MEM-009 QA/VA 产品文件完整落地 main、零回退、零夹带、blob 与源分支一致；合并后 main 三套回归套件（91/28/94）全绿，**合并未引入任何回归**。评估卡验收五条全部通过，MEM-009 落地链路闭环。

---

## 1. 静态验收核对（合并质量复核）

| # | 检查项 | 命令 | 结果 |
|---|---|---|---|
| 1 | mem009 全命中（docs/qa 5 + scripts 2） | `git ls-tree -r main --name-only \| grep mem009` | ✅ 7 命中 |
| 2 | wip 5 在 main | `git ls-tree -r main --name-only \| grep wip/t_` | ✅ 5 命中（2fc5fd0a/f91a64c5/ac88ed89/48a3dd47/de9e75df） |
| 3 | 合并 diff 仅新增 | `git diff d6682b5 72156df --name-status` | ✅ 12 行全为 A（add），无 M/D |
| 4 | 保护文件零改动 | `git diff d6682b5 72156df --name-only \| grep -E "discover.py\|oc_wake_check.sh\|test_va_backfill.sh"` | ✅ NONE（PASS） |
| 5 | gai/manifest/archive 零混入 | `git diff d6682b5 72156df --name-only \| grep -E "\.pipeline/(gai\|manifest\|archive)"` | ✅ NONE（PASS） |
| 6 | blob 与源分支一致 | `git rev-parse main:<path>` vs `git rev-parse wt/<branch>:<path>` | ✅ 12/12 OK |

> 基线说明：72156df 为 merge commit，parents = d6682b5（合并前 main）+ e1c7e5f（SUB-1 分支提交）。静态核对一律以 **first parent d6682b5** 为 diff 基线（对第二 parent 比对 name-status 为空，属预期，非缺陷）。

## 2. 全量回归（main 合并后状态，独立执行）

执行环境：worktree wt/t_4db0eb2d（HEAD == main @ 72156df，内容等价 main 合并后状态），脚本均从 scripts/ 目录直接运行。

| 套件 | 命令 | 结果 | 退出码 |
|---|---|---|---|
| VA 补扫机制 | `bash scripts/test_va_backfill.sh` | **PASS=91 FAIL=0** | 0 |
| watchdog 统一（源 I/J/K） | `bash scripts/test_watchdog_unify.sh` | **PASS=28 FAIL=0** | 0 |
| wip_progress_check / oc_wake 巡检 | `bash scripts/test_wip_progress_check.sh` | **PASS=94 FAIL=0** | 0 |

关键覆盖点（抽查）：
- va_backfill：T1 补建/T2 链式补建/T3 去重/T4 跳过/T5 幂等/T6 窗口/T8 R3 双条件/T9 DPL-060 R1 宽化/T10 skip 留痕/T11 DPL-077 容器豁免三判据 + 反例不丢 + 源 H 残留豁免/T7 fail-open
- watchdog_unify：T1-T3 源 I 幽灵卡、T4-T5 源 J main-dirty、T6-T8 源 K stuck-long、T9 归档存在性
- wip_progress：T1-T6 阈值边界与幂等窗口、T7 源 D 输出、T9-T13 源 E code-not-in-main 正反例/路径变体/窗口边界、T14-T18 源 A-D/F 只增不删、T19-T23 跨仓正反例 + seen 幂等

## 3. 结论与门禁

- 评估卡验收 **5/5 通过**；静态核对 + 三套回归全绿。
- 合并未引入回归；无新增缺陷；无保护文件回退；无夹带。
- MEM-009 QA 产品落地链路（QA-D1/EXEC/D2/VA-QA/QA-POST 报告 + 2 探针 + 5 WIP 笔记）已在 main，code-not-in-main 缺口消除。
