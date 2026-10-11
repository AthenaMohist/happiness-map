# Slice 3 收尾层 — QA D1 测试方案

> 版本：v1.0 | 日期：2026-07-30 | 作者：game-qa
>
> 被测范围：`pipeline/boot_context.py`（新增）+ `pipeline/backup.py`（新增）+ `pipeline/dashboard.py`（新增）+ `pipeline/state.py`（close stubs 展开）+ `pipeline/discover.py`（PIPELINE_ASSIGNEES 扩展）+ `scripts/autopilot.sh`（backup 集成 + cron 环境变量）+ `.hermes.md`（静态模板迁移）
>
> 输入文档：
> - PRD：`docs/prd/slice3-finishing-prd.md`（v1.0，820 行）
> - 架构：`docs/arch-slice3-closing-layer.md`（v1.0，638 行）
> - Slice 2 测试方案：`docs/qa/slice2-pipeline-test-plan.md`（v1.0，810 行）
> - Slice 1 测试方案：`docs/qa/slice1-pipeline-test-plan.md`（v1.0，411 行）
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 测试范围概览

```
被测模块                            PRD AC 覆盖        类型              新增/扩展       预估用例
────────────────────────────────────────────────────────────────────────────────────────────────
pipeline/boot_context.py (新增)     AC-1~5, AC-21      新增                ~120 行         TC-01~07
pipeline/dashboard.py (新增)        AC-6~8, AC-20      新增                ~100 行         TC-08~12
pipeline/backup.py (新增)           AC-9~11, AC-22     新增                ~80 行          TC-13~18
pipeline/state.py (close stub 展开)  AC-12~15           扩展（+155 行）     已有 stub→实现   TC-19~26
pipeline/discover.py (修复)         AC-16               扩展（+5 行）      已有             TC-27~28
scripts/autopilot.sh (修复+集成)     AC-17, AC-9~12     扩展（+40 行）      已有             TC-29~31
.hermes.md / config/hermes_static.md AC-1, AC-5         修改+新增           已有             TC-01, TC-07
三 cron 共存                         AC-18              配置验证            新增 cron        TC-32~34
```

### 0.1 与 Slice 2 的关系

Slice 3 **不修改管线流转逻辑**（7 步 + 21 分支保持不变）。以下 Slice 2 的 TC 需在 Slice 3 环境中回归：

| Slice 2 TC | 说明 | Slice 3 回归点 |
|:---:|------|------|
| TC-01~04 | checkpoint + 状态流转 | 验证 close 步骤写入不破坏已有 schema |
| TC-05~07 | gate_roundtable | 验证 close 步骤中的 roundtable 相关逻辑不变 |
| TC-11 | S6 检测 | close-0 已是 Slice 2 已有，Slice 3 验证其仍正确 |
| TC-12 | close.sh 调用 | Slice 3 展开 close 子步骤后，仍需验证 close.sh 调用正确 |
| TC-13 | 向后兼容 | user_version=2 不变，验证 Slice 3 新增模块不影响已有数据 |
| TC-15 | 日志可追溯 | 新增备份/GAI/manifest 失败需有日志 |

---

## 1. 测试环境准备

### 1.1 硬件/OS

| 维度 | 要求 |
|------|------|
| OS | Linux（与生产一致，`/workspace/devPPL`） |
| Python | 3.11+（标准库：sqlite3, json, subprocess, pathlib, argparse, os） |
| Bash | ≥ 4.0（支持 `set -euo pipefail`） |
| SQLite | ≥ 3.35（WAL 模式） |
| 测试框架 | pytest ≥ 7.0 |
| Hermes CLI | `hermes kanban` 可用（用于 autopilot 修复验证） |
| session DB | `~/.hermes/sessions.db` 可读（boot_context 数据源） |

### 1.2 测试前清理脚本

```bash
#!/bin/bash
cd /workspace/devPPL

# 1. 清理测试数据库
rm -f test_pipeline_state.db test_backup_state.db

# 2. 预留干净的 .hermes.md 模板用于 boot_context 测试
# （不破坏生产 .hermes.md）

# 3. 确认依赖文件存在
python3 -c "
from pipeline.checkpoint import CheckpointDB
from pipeline.constants import STEP_NAMES, STEP_ORDER
print('pipeline modules OK')
"
```

### 1.3 测试数据种子

```python
# tests/seed_slice3.py — 用于 TC-01~34 的测试数据
import sqlite3, tempfile, os

def seed_boot_context_db(db_path: str):
    """种子 pipeline_state.db，含多种状态的活跃任务。"""
    from pipeline.checkpoint import CheckpointDB
    db = CheckpointDB(db_path)
    db.ensure_schema()
    # 活跃任务 1: dev running
    db.upsert_step('t_seed1', 'dev', status='running', verdict='pass')
    # 活跃任务 2: qa-exec done + blocked
    db.upsert_step('t_seed2', 'dev', status='done', verdict='pass')
    db.upsert_step('t_seed2', 'qa-d1', status='done', verdict='pass')
    db.upsert_step('t_seed2', 'qa-exec', status='blocked', verdict='blocked',
                   error_msg='BLOCKER found')
    # 活跃任务 3: 接近 close（merge done）
    for step in ['dev','qa-d1','qa-exec','qa-d2','va','merge']:
        db.upsert_step('t_seed3', step, status='done', verdict='pass')
    return db
```

---

## 2. DPL-011 boot_context 测试用例（AC-1~5, 21）

### 2.1 模块级接口测试

#### TC-01：generate_boot_context 基本输出格式（AC-1）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-01 |
| **对应 AC** | AC-1：boot_context 每 5min 更新 |
| **被测函数** | `generate_boot_context()` |
| **触发条件** | 调用函数，传入含种子数据的 pipeline_state.db |
| **前置步骤** | 种子 pipeline_state.db（3 个活跃任务：1 running + 1 blocked + 1 done） |
| **步骤** | 1. `content = generate_boot_context(pipeline_db_path=seed_db)`<br>2. 检查 content 类型和结构<br>3. 验证 `len(content) <= 2000` |
| **预期结果** | 1. content 是 str<br>2. 含 `## 活跃管线任务` 段落<br>3. 含 `t_seed1`、`t_seed2`、`t_seed3`（按状态排序：先 blocked 再 running 再 done）<br>4. 字符数 ≤ 2000 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（agent 启动时依赖 boot_context 了解管线状态）+ 功能阻断（动态段为空 = DPL-011 失效）+ 无 workaround。 |

#### TC-02：generate_boot_context 空数据库处理（AC-1 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-02 |
| **对应 AC** | AC-1 边界：无活跃任务时的行为 |
| **被测函数** | `generate_boot_context()` |
| **触发条件** | pipeline_state.db 存在但无活跃任务 |
| **前置步骤** | 空的 pipeline_state.db（无 running/failed/blocked 任务） |
| **步骤** | `content = generate_boot_context(pipeline_db_path=empty_db)` |
| **预期结果** | 1. 不抛异常<br>2. 输出含 `无活跃管线任务` 或等效提示<br>3. 仍含 `最近决策` 段落（从 session DB/memory 提取）<br>4. 字符数 ≤ 2000 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（空管线时 agent 仍需知道上下文）+ 功能不阻断但有退化（无任务信息可展示）。 |

#### TC-03：generate_boot_context 数据源容错（AC-21 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-03 |
| **对应 AC** | AC-21 边界：一个数据源不可用不影响整体 |
| **被测函数** | `generate_boot_context()` |
| **触发条件** | 各数据源（pipeline/kanban/session/memory）逐一模拟不可用 |
| **前置步骤** | 准备种子 pipeline_state.db |
| **步骤** | 分别模拟以下场景：<br>1. pipeline_state.db 路径不存在 → `generate_boot_context(pipeline_db_path='/nonexistent/db')`<br>2. kanban.db 路径不存在 → 传入不存在的 kanban_db_path<br>3. session DB 不可读 → 传入错误路径<br>4. memory 工具不可用 → 模拟异常 |
| **预期结果** | 1. 任何单一数据源失败不抛异常<br>2. 输出中注明对应数据源不可用（如 `[pipeline 状态不可用]`）<br>3. 其他数据源的内容正常产出<br>4. 字符数 ≤ 2000 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（部分上下文缺失）+ 有 workaround（cron 下一轮可能恢复）。 |

#### TC-04：generate_boot_context 字符预算截断（AC-21 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-04 |
| **对应 AC** | AC-21：动态段 ≤ 2000 字符 |
| **被测函数** | `generate_boot_context()` |
| **触发条件** | 大量活跃任务导致内容超出 2000 字符 |
| **前置步骤** | 种子 50+ 个活跃任务的 pipeline_state.db |
| **步骤** | 1. `content = generate_boot_context(pipeline_db_path=large_db)`<br>2. 验证 `len(content) <= 2000` |
| **预期结果** | 1. 不抛异常<br>2. 字符数严格 ≤ 2000<br>3. 活跃任务表被截断但保留最紧急的（优先保留 blocked 和 failed 任务）<br>4. 如需要，`最近决策`/`最近纠正` 中旧条目被裁剪 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（截断导致部分任务不可见）+ 但不影响核心功能（最紧急任务仍展示）。 |

#### TC-05：write_boot_context 原子写入（AC-5）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-05 |
| **对应 AC** | AC-5：原子写入——读到的始终是完整文件 |
| **被测函数** | `write_boot_context()` |
| **触发条件** | 正常写入流程 |
| **前置步骤** | 1. 创建临时 .hermes.md（含 `<!-- BOOT_CONTEXT_START -->` 和 `<!-- BOOT_CONTEXT_END -->` 锚点）<br>2. 种子正确内容的 boot_context |
| **步骤** | 1. `write_boot_context(content, tmp_hermes_md)`<br>2. 读取文件验证静态段未被修改<br>3. 验证动态段被替换为新 content<br>4. 验证锚点标记仍存在<br>5. 验证文件末尾无重复锚点 |
| **预期结果** | 1. 返回 True<br>2. 静态段内容原样保留<br>3. `<!-- BOOT_CONTEXT_START -->` 和 `<!-- BOOT_CONTEXT_END -->` 之间的内容被替换<br>4. 文件总大小 ≤ 20000 字符<br>5. 无 .tmp 残留（原子 rename 清理） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（半截文件导致 agent 加载出错）+ 功能阻断（.hermes.md 是 agent 启动上下文源）+ 无 workaround。 |

#### TC-06：write_boot_context 锚点缺失处理

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-06 |
| **对应 AC** | AC-5 边界：.hermes.md 中无锚点标记 |
| **被测函数** | `write_boot_context()` |
| **触发条件** | .hermes.md 未包含 `<!-- BOOT_CONTEXT_START -->` |
| **前置步骤** | 创建不含锚点的 .hermes.md 文件 |
| **步骤** | `result = write_boot_context(content, no_anchor_hermes_md)` |
| **预期结果** | 1. 返回 False（写入失败）<br>2. 不修改 .hermes.md 文件<br>3. 不抛未捕获异常 |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知（首次部署时需手动加锚点）+ 不影响核心功能（首次部署是已知操作）。 |

#### TC-07：静态模板迁移验证（AC-1 部署验证）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-07 |
| **对应 AC** | AC-1：静态段迁移到 `config/hermes_static.md` |
| **触发条件** | Slice 3 部署后的 .hermes.md 结构 |
| **前置步骤** | Slice 3 代码已部署 |
| **步骤** | 1. 检查 `config/hermes_static.md` 存在且内容与原 `.hermes.md` 静态段一致<br>2. 检查 `.hermes.md` 含 `<!-- BOOT_CONTEXT_START -->` 锚点<br>3. `boot_context` cron 运行一次后，`.hermes.md` 含静态段 + 动态段 |
| **预期结果** | 1. `config/hermes_static.md` 存在<br>2. `.hermes.md` 含锚点<br>3. 拼接后文件格式正确（静态段 + `---` + 动态段） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（agent 启动时读取 .hermes.md）+ 有 workaround（手动运行 boot_context）。 |

---

## 3. Dashboard 测试用例（AC-6~8, 20）

### 3.1 模块级接口测试

#### TC-08：dashboard 基本输出（AC-6）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-08 |
| **对应 AC** | AC-6：dashboard 红绿灯面板 |
| **被测模块** | `pipeline/dashboard.py`（或 `scripts/dashboard.py`） |
| **触发条件** | 种子 pipeline_state.db（3 个任务：green + yellow + red） |
| **前置步骤** | 种子数据：t_green(7 步全 done)，t_yellow(dev running)，t_red(qa-exec blocked) |
| **步骤** | 1. `python3 pipeline/dashboard.py --db test_db`<br>2. 检查 stdout 输出 |
| **预期结果** | 1. 退出码 0<br>2. 含项目名称（如 `devPPL Pipeline Dashboard`）<br>3. t_green 状态显示为 🟢 或 ✅<br>4. t_yellow 状态显示为 🟡 或 🔄<br>5. t_red 状态显示为 🔴 或 ❌<br>6. 汇总行：`🟢 1 · 🟡 1 · 🔴 1` |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（Frank 的唯一管线视图入口）+ 功能阻断（看不到状态）+ 无 workaround（SQLite CLI 不是替代方案——用户不会接受）。 |

#### TC-09：dashboard --json 输出（AC-7）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-09 |
| **对应 AC** | AC-7：dashboard --json 输出合法 JSON |
| **被测模块** | `pipeline/dashboard.py --json` |
| **触发条件** | `--json` 标志 |
| **前置步骤** | 种子 pipeline_state.db（至少 1 个任务） |
| **步骤** | 1. `python3 pipeline/dashboard.py --json --db test_db`<br>2. `python3 -c "import sys,json; json.load(sys.stdin)"` 管道验证 |
| **预期结果** | 1. 退出码 0<br>2. stdout 是合法 JSON<br>3. JSON 含 `project`、`timestamp`、`summary`（green/yellow/red/gray 计数）、`tasks` 数组<br>4. `tasks` 中每个 task 有 `task_id`、`current_step`、`status`、`steps` |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（watchdog/自动化工具依赖 JSON 输出）+ 有 workaround（手动查 SQLite）。 |

#### TC-10：dashboard --task 筛选（AC-8）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-10 |
| **对应 AC** | AC-8：dashboard --task 只显示指定任务 |
| **被测模块** | `pipeline/dashboard.py --task t_xxx` |
| **触发条件** | `--task` 标志 |
| **前置步骤** | 种子 pipeline_state.db（3 个任务） |
| **步骤** | 1. `python3 pipeline/dashboard.py --task t_seed1 --db test_db`<br>2. 检查输出是否只含 t_seed1<br>3. `python3 pipeline/dashboard.py --task nonexistent --db test_db` |
| **预期结果** | 1. 输出只含 t_seed1 的信息<br>2. 不包含 t_seed2/t_seed3<br>3. 不存在的 task_id 输出 `任务不存在` 或等效提示（退出码 1 可接受） |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知 + 不影响核心任务完成（全量面板已可用）。 |

#### TC-11：dashboard --failed-only（AC-6 扩展）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-11 |
| **对应 AC** | AC-6 扩展：只看异常任务 |
| **被测模块** | `pipeline/dashboard.py --failed-only` |
| **触发条件** | `--failed-only` 标志 |
| **前置步骤** | 种子数据：1 green + 1 yellow + 1 red + 1 gray |
| **步骤** | `python3 pipeline/dashboard.py --failed-only --db test_db` |
| **预期结果** | 1. 只显示 red (blocked/failed/timeout) 的任务<br>2. 不显示 green/yellow/gray<br>3. 汇总行只统计 red 类 |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知（便利功能）+ 不影响核心任务完成。 |

#### TC-12：dashboard 性能（AC-20）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-12 |
| **对应 AC** | AC-20：100 个任务的 panel 渲染 < 1 秒 |
| **被测模块** | `pipeline/dashboard.py` 渲染性能 |
| **触发条件** | 大规模数据 |
| **前置步骤** | 种子 100 个活跃任务的 pipeline_state.db |
| **步骤** | `time python3 pipeline/dashboard.py --db large_db --full` |
| **预期结果** | 1. 渲染时间 < 1 秒<br>2. 无内存溢出<br>3. 所有 100 个任务显示正确 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——系统健康度退化（性能不达标）。性能退化 P95 未达 3x 阈值但破坏了 AC 承诺。 |

---

## 4. 备份策略测试用例（AC-9~11, 22）

### 4.1 backup.py 模块测试

#### TC-13：determine_backup_script 三类项目类型判定

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-13 |
| **对应 AC** | AC-9~11：三类项目类型自动选备份命令 |
| **被测函数** | `determine_backup_script(project_type, backup_step, db)` |
| **触发条件** | 传入不同 project_type |
| **前置步骤** | 准备 CheckpointDB 实例 |
| **步骤** | 分别测试：<br>1. `project_type='system_mechanism'` → 预期返回 `/workspace/hermes_backup_push.sh`<br>2. `project_type='pure_product'` → 预期 git 推送命令<br>3. `project_type='hybrid'` → 预期双重备份<br>4. `project_type=None` → 默认 fallback 到 system_mechanism |
| **预期结果** | 1. system_mechanism → 返回 `hermes_backup_push.sh` 路径<br>2. pure_product → 返回 git push 命令或相应脚本<br>3. hybrid → 返回两个备份命令（git push + hermes_backup_push.sh）<br>4. None/未知 → 返回 system_mechanism 默认策略 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（数据安全）+ 功能阻断（备份选错=数据丢失不可恢复）+ 无 workaround。 |

#### TC-14：run_backup 正常执行（AC-9,10,11）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-14 |
| **对应 AC** | AC-9：合并前备份；AC-10：合并后备份；AC-11：close-4 备份 |
| **被测函数** | `run_backup(script_path, task_id, backup_step)` |
| **触发条件** | 传入可执行 mock 备份脚本 |
| **前置步骤** | 创建临时 mock 备份脚本：`#!/bin/bash\necho "backup ok"; exit 0` |
| **步骤** | 1. `run_backup(mock_script, 't_test', 'pre')`<br>2. `run_backup(mock_script, 't_test', 'post')`<br>3. `run_backup(mock_script, 't_test', 'close')` |
| **预期结果** | 1. 三个 backup_step 均返回 `(True, "backup ok")`<br>2. stdout 被捕获为 success 消息<br>3. backup_step 字段在日志/输出中正确出现 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（数据安全——备份执行失败=数据丢失风险）+ 功能阻断（备份是数据安全的最后防线）+ 无 workaround。 |

#### TC-15：run_backup 脚本失败处理

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-15 |
| **对应 AC** | AC-9 边界：备份脚本 exit ≠ 0 |
| **被测函数** | `run_backup()` + 重试逻辑 |
| **触发条件** | mock 备份脚本 exit 1 |
| **前置步骤** | 创建 mock 脚本：`#!/bin/bash\necho "backup failed" >&2; exit 1` |
| **步骤** | 1. `run_backup(mock_fail_script, 't_test', 'pre')`<br>2. 验证返回值<br>3. 验证重试计数（如适用） |
| **预期结果** | 1. 返回 `(False, ...)`，error 含 stderr<br>2. autopilot 日志中出现备份失败记录<br>3. pre-merge 备份失败 → merge 步骤被阻塞（不执行 merge）<br>4. post-merge/close 备份失败 → 管线不阻塞但发出告警 |
| **风险等级** | **BLOCKER**（pre-merge 失败部分）<br>**MAJOR**（post-merge/close 失败部分） |
| **分级依据** | pre-merge：用户可感知（数据安全）+ 功能阻断（必须先备份才 merge）+ 无 workaround。<br>post-merge/close：用户可感知 + 有 workaround（手动备份）。 |

#### TC-16：run_backup 脚本不存在/不可执行

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-16 |
| **对应 AC** | AC-22 边界：备份脚本路径不可执行 |
| **被测函数** | `run_backup()` |
| **触发条件** | 传入不存在的脚本路径 |
| **前置步骤** | 无 |
| **步骤** | `run_backup('/nonexistent/backup.sh', 't_test', 'pre')` |
| **预期结果** | 1. 返回 `(False, ...)`，error_msg 明确说明文件不存在或不可执行<br>2. 不抛未捕获异常 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（备份失败）+ 有 workaround（修复脚本路径）。 |

#### TC-17：run_backup 超时处理

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-17 |
| **对应 AC** | AC-22 边界：备份脚本运行超过 timeout_seconds |
| **被测函数** | `run_backup()` |
| **触发条件** | mock 备份脚本 sleep 超过 timeout |
| **前置步骤** | 创建 mock 脚本：`#!/bin/bash\nsleep 200` |
| **步骤** | `run_backup(mock_slow_script, 't_test', 'pre', timeout_seconds=1)` |
| **预期结果** | 1. 在 timeout_seconds 内返回<br>2. 返回 `(False, ...)`，error_msg 含 `timeout` 关键字<br>3. 子进程被正确 kill |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（备份超时可能意味着大仓库推送卡住）+ 有 workaround（手动备份 + 增加 timeout）。 |

#### TC-18：backup_step 重试逻辑验证（合约联动）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-18 |
| **对应 AC** | AC-9：pre-merge backup fail → retry(1)；AC-10：post-merge backup fail → retry(2)；AC-11：close backup fail → retry(3) |
| **被测模块** | `backup.py` + `state.py` BranchesEvaluator + `autopilot.sh` |
| **触发条件** | 备份失败 → 触发合约分支 |
| **前置步骤** | mock 备份脚本持续失败（exit 1） |
| **步骤** | 1. pre-merge backup 失败 → 验证 retry_count 递增<br>2. 达到 max_retries(1) 后 → action=block<br>3. post-merge backup 失败 → 验证 max_retries=2<br>4. close backup 失败 → 验证 max_retries=3 |
| **预期结果** | 1. 重试次数与合约一致：pre=1, post=2, close=3<br>2. 耗尽后正确触发 block 或告警<br>3. pipeline_state.db 中 backup_step 字段记录 'pre'/'post'/'close' |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（备份重试不足 = 数据安全漏洞）+ 功能阻断（合约约定了重试次数）+ 无 workaround。 |

---

## 5. S6 闭环 — close 7 子步骤测试用例（AC-12~15）

### 5.1 close-2: GAI 更新

#### TC-19：_close_gai_update 正常更新（AC-12）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-19 |
| **对应 AC** | AC-12：close-2 GAI 更新 |
| **被测函数** | `_close_gai_update(task_id)` |
| **触发条件** | GAI 文件存在，task 标题含 P0-XX 编号 |
| **前置步骤** | 1. 创建临时 `GLOBAL_ACTION_ITEMS.md` 含 `| P0-19 | ... | 待办 | ...`<br>2. mock kanban task 标题为 `P0-19: 管线脚本化` |
| **步骤** | 1. `_close_gai_update('t_test')`<br>2. 读取 GAI 文件验证 P0-19 行状态 |
| **预期结果** | 1. 函数不抛异常<br>2. GAI 文件中 P0-19 对应行从 `待办` → `✅ done`<br>3. 其他行不受影响<br>4. 返回 True |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（GAI 是 SDD 铁律的跟踪工具）+ 功能阻断（GAI 未更新 = S6 不闭环）+ 无 workaround（手动更新违背自动化原则）。 |

#### TC-20：_close_gai_update GAI 文件不存在（AC-12 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-20 |
| **对应 AC** | AC-12 边界：GAI 文件不存在 |
| **被测函数** | `_close_gai_update(task_id)` |
| **触发条件** | `GLOBAL_ACTION_ITEMS.md` 不存在 |
| **前置步骤** | 确保 GAI 文件不存在 |
| **步骤** | `_close_gai_update('t_test')` |
| **预期结果** | 1. 返回 False（或抛异常被上层捕获）<br>2. autopilot 日志含 GAI 文件缺失告警<br>3. 根据合约：`step_fail_gai` → retry(1) → 失败后继续（记录 warning） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（GAI 未更新）+ 有 workaround（手动创建 GAI 文件后 retry）。 |

#### TC-21：_close_gai_update 无法匹配 P0 编号（AC-12 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-21 |
| **对应 AC** | AC-12 边界：非 GAI 任务（标题不含 P0-XX） |
| **被测函数** | `_close_gai_update(task_id)` |
| **触发条件** | kanban task 标题不匹配 P0-XX 模式 |
| **前置步骤** | mock kanban task 标题为 `[Slice3-Step1] 架构设计`（无 P0 编号） |
| **步骤** | `_close_gai_update('t_test')` |
| **预期结果** | 1. 返回 True（跳过，不阻塞）<br>2. 不修改 GAI 文件<br>3. 不抛异常 |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知（并不是所有任务都需要 GAI 更新）+ 不影响核心任务完成。 |

### 5.2 close-3: manifest 更新

#### TC-22：_close_manifest_update 正常更新（AC-13）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-22 |
| **对应 AC** | AC-13：close-3 manifest 更新 |
| **被测函数** | `_close_manifest_update(task_id)` |
| **触发条件** | manifest.yaml 存在，git diff 有新增文件 |
| **前置步骤** | 1. 创建 `config/manifest.yaml`（含已有文件列表）<br>2. mock git diff --name-only HEAD~1 HEAD 返回新增文件列表 |
| **步骤** | 1. `_close_manifest_update('t_test')`<br>2. 读取 manifest.yaml 验证新增文件已注册 |
| **预期结果** | 1. manifest.yaml 中新增文件出现在 files 列表中<br>2. 已有文件不丢失<br>3. 返回 True |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（manifest 是项目文件清单）+ 有 workaround（手动更新 manifest）。 |

#### TC-23：_close_manifest_update 首次创建（AC-13 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-23 |
| **对应 AC** | AC-13 边界：manifest.yaml 不存在 → 首次创建 |
| **被测函数** | `_close_manifest_update(task_id)` |
| **触发条件** | `config/manifest.yaml` 文件不存在 |
| **前置步骤** | 确保 `config/manifest.yaml` 不存在 |
| **步骤** | 1. `_close_manifest_update('t_test')`<br>2. 验证 manifest.yaml 被创建<br>3. 检查内容覆盖 git 追踪的所有文件 |
| **预期结果** | 1. `config/manifest.yaml` 被创建<br>2. 至少含 `files` 列表<br>3. 返回 True |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知 + 不影响核心功能（首次创建是正常流程）。 |

### 5.3 close-4: 备份推送

TC-14~18 覆盖此子步骤。此处补充端到端验证：

#### TC-24：_close_backup 端到端（AC-11 端到端）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-24 |
| **对应 AC** | AC-11：close-4 备份实际执行 |
| **被测函数** | `_close_backup(task_id)` |
| **触发条件** | close 流程推进到 close-4 |
| **前置步骤** | 1. 种子数据：前 6 步 done<br>2. project_type='system_mechanism'<br>3. mock `hermes_backup_push.sh` 可执行 |
| **步骤** | 1. 触发 `close_pipeline_step('t_test')` → 执行到 close-4<br>2. 验证备份脚本被调用<br>3. 验证 close-4 输出日志 |
| **预期结果** | 1. close-4 日志含 `备份推送完成 ✅`<br>2. 备份脚本 exit 0 → close-4 success<br>3. pipeline_state.db close step 的 artifact_paths 含备份记录 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 同 TC-14。 |

### 5.4 close-5: 通知

#### TC-25：_close_notify 正常通知（AC-14）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-25 |
| **对应 AC** | AC-14：close-5 飞书通知 |
| **被测函数** | `_close_notify(task_id, db)` |
| **触发条件** | close-5 执行 |
| **前置步骤** | 1. project_config 含 notify_script<br>2. 种子完成的前 6 步 |
| **步骤** | 1. `_close_notify('t_test', db)`<br>2. 验证 notify_script 被调用并传入 task_id |
| **预期结果** | 1. 通知脚本被调用（可通过 mock 验证参数）<br>2. 返回 True<br>3. 失败不阻塞 close 流程（静默忽略） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（通知缺失 = 相关人员不知道闭环完成）+ 有 workaround（手动通知）。 |

### 5.5 close-6: 归档

#### TC-26：_close_archive 归档 + close.sh 验证（AC-15）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-26 |
| **对应 AC** | AC-15：close-6 归档 |
| **被测函数** | `_close_archive(task_id, db)` |
| **触发条件** | close-6 执行 |
| **前置步骤** | 1. 种子完成的前 6 步<br>2. 各步骤有 artifact_paths |
| **步骤** | 1. `_close_archive('t_test', db)`<br>2. 验证 `.pipeline/archive/t_test/manifest.json` 被创建<br>3. 验证 `close.sh` 被调用（如果存在） |
| **预期结果** | 1. 归档目录被创建<br>2. 归档清单含所有步骤的 artifacts<br>3. close.sh 验证通过 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（归档是可追溯性的基础）+ 有 workaround（手动归档）。 |

---

## 6. Autopilot 修复测试用例（AC-16~17）

### 6.1 任务发现盲区修复

#### TC-27：PIPELINE_ASSIGNEES 扩展验证（AC-16）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-27 |
| **对应 AC** | AC-16：discover 发现 game-director/architect/autopilot 任务 |
| **被测模块** | `pipeline/discover.py` `PIPELINE_ASSIGNEES` |
| **触发条件** | 静态检查 + 功能测试 |
| **前置步骤** | 无 |
| **步骤** | 1. 静态检查：`from pipeline.discover import PIPELINE_ASSIGNEES` → 验证含 `game-director`, `game-architect`, `autopilot`<br>2. 功能测试：创建 assignee=game-director 的 kanban task → 运行 discover <br>3. 功能测试：创建 assignee=autopilot 的 kanban task → 运行 discover |
| **预期结果** | 1. PIPELINE_ASSIGNEES 含 6 个值：game-engine, game-qa, verifier, game-director, game-architect, autopilot<br>2. game-director task 被 discover 发现<br>3. autopilot task（非子任务标题）被 discover 发现 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（任务不被发现 = 管线漏掉整个 task）+ 功能阻断（任务发现是管线入口）+ 无 workaround。 |

#### TC-28：子任务标题前缀补全（AC-16 边界）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-28 |
| **对应 AC** | AC-16 边界：autopilot 创建的子任务不被误发现 |
| **被测模块** | `pipeline/discover.py` `_is_sub_task()` |
| **触发条件** | autopilot 创建的 merge/close 子任务标题 |
| **前置步骤** | 无 |
| **步骤** | 1. 模拟标题 `merge: t_xxx` → 应识别为子任务<br>2. 模拟标题 `close: t_xxx` → 应识别为子任务<br>3. 模拟标题 `[Slice3] DPL-011 实现` → 不应识别为子任务 |
| **预期结果** | 1. 管线子任务标题被 `_is_sub_task()` 过滤<br>2. 正常任务不被误过滤<br>3. 新加的 close/merge 前缀正确匹配 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（子任务被误发现可能导致重复创建管线步骤）+ 有 workaround（手动清理）。 |

### 6.2 cron 上下文修复

#### TC-29：cron 环境变量显式导出（AC-17）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-29 |
| **对应 AC** | AC-17：cron 环境中 `hermes kanban show` 不返回空 |
| **被测模块** | `scripts/autopilot.sh` 开头环境变量导出 |
| **触发条件** | 模拟 cron 环境（清空 Hermes 环境变量） |
| **前置步骤** | 无 |
| **步骤** | 1. 在无 `HERMES_KANBAN_DB` 的环境下执行 autopilot.sh 的环境变量检查段落<br>2. 验证 `HERMES_KANBAN_DB` 被设为默认值<br>3. 验证 `HERMES_PROFILE` 被设为默认值<br>4. 验证 kanban.db 存在性检查通过 |
| **预期结果** | 1. `HERMES_KANBAN_DB` 指向有效路径<br>2. `HERMES_PROFILE` 正确设置<br>3. kanban.db 不存在时 exit 1 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（cron 下 `hermes kanban show` 返回空 = 状态引擎无法获取任务状态）+ 功能阻断（autopilot 无法推进管线）+ 无 workaround。 |

#### TC-30：get_kanban_task_state SQLite fallback（AC-17 容错）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-30 |
| **对应 AC** | AC-17 容错：CLI 失败 → SQLite 直读 |
| **被测函数** | `get_kanban_task_state(task_id)` |
| **触发条件** | `hermes kanban show` CLI 失败 |
| **前置步骤** | mock `hermes` CLI 不可用 |
| **步骤** | 1. `get_kanban_task_state('t_exists_in_db')`<br>2. 验证返回的 task 状态与 kanban.db 一致 |
| **预期结果** | 1. CLI 失败后 fallback 到 SQLite 直读<br>2. 返回正确的 task 状态（title, assignee, status）<br>3. task 不存在时返回 None |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（fallback 失败 = 状态引擎拿不到任务信息）+ 有 workaround（修复 CLI 后 retry）。 |

---

## 7. Autopilot merge 备份集成测试用例（AC-9~10 端到端）

#### TC-31：autopilot merge case 备份调用（AC-9/10 端到端）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-31 |
| **对应 AC** | AC-9：合并前备份；AC-10：合并后备份 |
| **被测模块** | `scripts/autopilot.sh` merge case |
| **触发条件** | autopilot 推进到 merge 步骤 |
| **前置步骤** | 1. 种子数据：merge 步骤 ready<br>2. mock `execute_backup` 函数（或实际调用 backup.py） |
| **步骤** | 1. autopilot 执行 merge case<br>2. 验证 merge-1（合并前备份）先于 git merge 执行<br>3. 验证 merge-4（合并后备份）在 git merge 后执行<br>4. 验证 project_type 被正确传入 backup |
| **预期结果** | 1. 日志含 `合并前备份` 或 `pre_merge`<br>2. 日志含 `合并后备份` 或 `post_merge`<br>3. backup 调用顺序正确（pre → merge → post）<br>4. backup 失败时 merge 被阻塞（pre）或告警（post） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：同 TC-14/TC-18。 |

---

## 8. 三 cron 共存测试用例（AC-18）

#### TC-32：三 cron 并发无 SQLITE_BUSY（AC-18）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-32 |
| **对应 AC** | AC-18：三 cron 不冲突，pipeline_state.db 无 SQLITE_BUSY |
| **被测模块** | autopilot + watchdog + boot_context 并发执行 |
| **触发条件** | 三个 cron 同时 tick |
| **前置步骤** | 1. 种子 pipeline_state.db（含活跃任务）<br>2. 准备三个独立进程 |
| **步骤** | 1. 并行启动 autopilot（写 pipeline_state.db）+ boot_context（读 pipeline_state.db）<br>2. watchdog 同时读 kanban.db + 心跳文件<br>3. 重复 10 次 |
| **预期结果** | 1. 无 SQLITE_BUSY 错误<br>2. 无锁等待超时<br>3. pipeline_state.db 数据一致性正确（写入无丢失）<br>4. .hermes.md 无截断读 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——系统健康度退化（SQLITE_BUSY 会导致 cron 主动跳过本轮）+ 有 workaround（错峰调度）。 |

#### TC-33：autopilot flock 防重入验证

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-33 |
| **对应 AC** | AC-18 边界：autopilot 自身不并发 |
| **被测模块** | `scripts/autopilot.sh` flock 锁 |
| **触发条件** | 第二个 autopilot 实例尝试启动 |
| **前置步骤** | 第一个 autopilot 持有 /tmp/autopilot.lock |
| **步骤** | 1. 启动 autopilot #1（hold lock）<br>2. 在 #1 运行期间启动 autopilot #2<br>3. 检查 #2 的行为 |
| **预期结果** | 1. autopilot #2 日志含 `另一实例运行中，跳过本轮`<br>2. #2 退出码 0（不报错）<br>3. pipeline_state.db 不被 #2 修改 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（并发 autopilot 会导致 pipeline_state.db 数据竞争）+ 功能阻断（并行写入破坏状态一致性）+ 无 workaround。 |

#### TC-34：boot_context 原子写入并发读

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-34 |
| **对应 AC** | AC-18 边界：.hermes.md 写入时并发读不读脏 |
| **被测模块** | `write_boot_context()` 原子 rename |
| **触发条件** | boot_context 写入 + agent 启动读取并发 |
| **前置步骤** | 准备含锚点的 .hermes.md |
| **步骤** | 1. 启动 boot_context 写入（模拟慢写，在 rename 前 sleep）<br>2. 并发读取 .hermes.md<br>3. 验证读到的内容完整性 |
| **预期结果** | 1. 读操作要么读到旧版本（完整），要么读到新版本（完整）<br>2. 不存在半截文件（os.rename 是 POSIX 原子操作） |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知（半截 .hermes.md 导致 agent 启动加载错误）+ 但 POSIX 原子 rename 是已知保证，风险极低。 |

---

## 9. 非功能验收测试用例（AC-19~23）

#### TC-35：Slice 1/2 向后兼容（AC-19）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-35 |
| **对应 AC** | AC-19：pipeline_state.db schema 不变，已有数据不受影响 |
| **被测模块** | `CheckpointDB` + `pipeline/state.py` |
| **触发条件** | Slice 3 新代码操作 Slice 1/2 生产的 pipeline_state.db |
| **前置步骤** | 使用 Slice 1/2 种子数据 |
| **步骤** | 1. `ensure_schema()` → user_version 保持 2<br>2. `get_all_steps()` → 返回已有步骤数据<br>3. `upsert_step()` → 写入 close 步骤不破坏已有步骤<br>4. `advance_pipeline()` → 推进到 close 不失败 |
| **预期结果** | 1. schema 无变更（用户版本号不加）<br>2. 已有 14 列均可读写<br>3. close 步骤正常写入 7 步中 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（向后不兼容 = 已有管线数据报废）+ 数据一致性问题 + 无 workaround。 |

#### TC-36：boot_context mtime 时效性（AC-21）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-36 |
| **对应 AC** | AC-21：.hermes.md 的 mtime 与当前时间的差值 < 6min |
| **被测模块** | boot_context cron |
| **触发条件** | cron 正常运行 |
| **前置步骤** | 确保 boot_context cron 每 5min 运行 |
| **步骤** | 1. 记录 .hermes.md 初始 mtime<br>2. 等待 7 分钟<br>3. 检查新 mtime |
| **预期结果** | 1. mtime 在 5-7 分钟内更新<br>2. 更新后的动态段内容反映最新管线状态 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（时效性不达标 = agent 拿到的上下文是旧的）+ 有 workaround（手动运行 boot_context）。 |

#### TC-37：无静默失败（AC-23）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-37 |
| **对应 AC** | AC-23：备份失败/GAI 更新失败/通知失败 → autopilot 日志 + kanban comment 记录 |
| **被测模块** | `autopilot.sh` + `state.py` |
| **触发条件** | 各 close 子步骤失败 |
| **前置步骤** | mock 各子步骤失败 |
| **步骤** | 1. 触发 GAI 更新失败 → 验证日志含 `close-2 GAI 更新失败`<br>2. 触发备份失败 → 验证日志含失败原因<br>3. 触发通知失败 → 验证日志含 `close-5 通知`（不阻塞） |
| **预期结果** | 1. 所有失败在 autopilot 日志中有记录<br>2. 关键失败（GAI/backup）在 kanban comment 中有记录<br>3. 无静默跳过（stub pass → 未实际执行） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（静默失败 = 假闭环）+ 有 workaround（主动查日志）。 |

---

## 10. 发布门禁

```
发布条件：BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉
              AND Slice 1/2 回归全部通过
```

| 门禁项 | 阈值 | Slice 3 要求 |
|--------|:---:|------|
| BLOCKER TC | 0 失败 | TC-01,05,08,13,14,18,19,24,27,29,31,33,35 |
| MAJOR TC | ≤ 3 失败 | TC-02,03,04,07,09,12,15(post),16,17,20,22,25,26,28,30,32,36,37 |
| MINOR TC | 无限制 | 其余 |
| Slice 1/2 回归 | 全部通过 | 6 个回归 TC |

---

## 11. 文件清单

| 产出 | 路径 | 预估 |
|------|------|:---:|
| **测试方案（本文档）** | `docs/qa/slice3-closing-test-plan.md` | ~600 行 |
| **测试代码** | `tests/test_slice3_d1_qa.py` | ~500 行（待 Step3 产出） |
| **回归验证** | 现有 slice2_smoke + slice2_integration | 全部通过 |

---

## 12. QA 分析：PRD vs 架构发现的冲突

在编写测试方案过程中，QA 对比 PRD、架构设计、已有代码，发现以下需注意的点：

| # | 项目 | 观察 | 级别 |
|---|------|------|:---:|
| **D1-F0** | **PRD §1.3 说静态模板是 `config/hermes_static.md`，但架构 §1.2 设计的是 .hermes.md 内嵌 `<!-- BOOT_CONTEXT_START -->` 锚点** | PRD 提到"将当前 .hermes.md 中的人工维护内容移到独立的静态模板文件"，架构设计的是 `hermes_static.md → boot_context 拼接 → .hermes.md` vs 直接在 `.hermes.md` 中用锚点替换动态段。两者都是可行的，但实现路径不同——需 Product + Architect 统一口径。 | **MAJOR** |
| **D1-F1** | **contracts.jsonl close branches 中的 `step_fail_backup` 重试 max_retries=3 与 PRD §3.3 的 close-4 重试次数 3 一致，但 PRD §4.8 close-2 GAI 和 close-3 manifest 的重试次数是 1，与合约中的 `step_fail_gai`/`step_fail_manifest` max_retries=1 一致** | 经对比，PRD 与 contracts.jsonl 在重试次数上是一致的。✅ 无冲突。 | — |
| **D1-F2** | **dashboard.py 在 PRD 中放在 `pipeline/dashboard.py`，架构中放在 `scripts/dashboard.py`** | PRD §2.6 示例命令是 `python3 pipeline/dashboard.py`，架构 §2.1 是 `python3 scripts/dashboard.py`。路径不一致——需统一。 | **MINOR** |
| **D1-F3** | **PRD §1.5 boot_context.py 和 PRD §1.4 动态段格式中不含 `纠偏` 段落，但架构 §1.5 输出示例含 `### 纠偏`** | PRD 动态段模板只有 3 段（活跃任务/最近决策/最近纠正），架构模板含 4 段（活跃任务/最近决策/纠偏）+ 缺少 "最近纠正"。需统一。 | **MINOR** |

**裁定要求**：D1-F0 需要 Product + Architect 在编码前统一。D1-F2/D1-F3 为 MINOR 级别，可在编码时由 Engineer 就近决策。

---

## 13. 一句话总结

> Slice 3 收尾层测试方案覆盖 6 个子系统（boot_context/dashboard/backup/close 展开/autopilot 修复/三 cron 共存），共 37 个测试用例（13 BLOCKER + 18 MAJOR + 6 MINOR），对应 PRD 23 项验收标准全部覆盖。新增约 625 行 Python + Shell 代码的测试范围。不修改 Slice 1/2 的 7 步管线逻辑，已有回归测试全部保留。
