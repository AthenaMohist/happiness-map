# Slice 1 管线数据层 — QA D1 测试方案

> 版本：v1.0 | 日期：2026-07-30 | 作者：game-qa
>
> 被测范围：`pipeline/checkpoint.py` + `pipeline/state.py` + `config/contracts.jsonl` + `scripts/autopilot.sh`
>
> 输入文档：
> - PRD：`docs/prd/slice1-pipeline-prd.md`（v1.0，575 行）
> - 架构设计：`docs/arch-slice1-pipeline-data-layer.md`（v1.0，665 行）
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0

---

## ⚠️ D1 前置发现：PRD 与架构设计冲突（3 项）

在编写测试方案前，QA 对比 PRD 和架构设计，发现以下关键冲突。这些冲突必须在测试执行前由产品（许清楚）和架构师（高见远）裁定，否则测试无法进行。

| # | 冲突项 | PRD 规定 | 架构设计 | 影响 | 风险级别 |
|---|--------|---------|---------|------|:---:|
| **D1-F1** | **5 步步骤名** | dev → qa-exec → va → merge → close（PRD §2.1, §8 Sl1-01） | dev → qa-d1 → qa-exec → merge → close（Arch §0.1, §6.2） | PRD 有 va 无 qa-d1；架构有 qa-d1 无 va。**两套步骤名完全不同**，contracts.jsonl 的 `step` 字段必须二选一。 | **BLOCKER** |
| **D1-F2** | **project_config 表** | v1 schema 不含 project_config（PRD §8 Sl1-02：「只含 pipeline_steps 表，不含 verdict/project_config」） | Slice 1 就建 project_config（Arch §0.2：「裁决：放 Slice 1」；Arch §1.1 DDL 含此表） | 影响 init_project.py 是否实现、autopilot.sh 是否读取 project_config。 | **MAJOR** |
| **D1-F3** | **user_version / verdict 预置列** | user_version = 1，无 verdict 列（PRD §1.2） | user_version = 2，预置 verdict/verdict_detail/contract_check_passed 三列（Arch §1.1, §1.3） | 影响 checkpoint.py 的 schema DDL。如表结构错误，Sl 2 需 ALTER TABLE。 | **MAJOR** |

**裁定要求**：上述 3 项冲突必须由产品+架构师在 24h 内给出统一口径。QA 将按裁定后的标准执行测试。若未裁定，测试只能验证「文档一致性」而无法验证「功能正确性」。

---

## 1. 测试环境准备

### 1.1 硬件/OS

| 维度 | 要求 |
|------|------|
| OS | Linux（与生产环境一致，`/workspace/devPPL`） |
| Python | 3.11+（标准库：sqlite3, json, subprocess, pathlib, argparse） |
| Bash | ≥ 4.0（支持 `set -euo pipefail`） |
| 系统工具 | `flock`（来自 util-linux，生产环境已安装） |
| Cron | crontab 可用（非 root 也可写入） |

### 1.2 测试前清理脚本

```bash
# 每次测试前执行，恢复干净状态
cd /workspace/devPPL

# 1. 删除旧 pipeline_state.db
rm -f pipeline_state.db

# 2. 确认 contracts.jsonl 存在且可解析
python3 -c "
import json
with open('config/contracts.jsonl') as f:
    for line in f:
        json.loads(line.strip())
print('contracts.jsonl OK')
"

# 3. 确认 pipeline/ 模块可导入
python3 -c "from pipeline.checkpoint import CheckpointDB; print('import OK')"

# 4. 清理残留锁文件
rm -f /tmp/autopilot.lock
```

### 1.3 Mock 依赖

由于 autopilot 依赖 kanban 系统（`hermes kanban` CLI），测试需要 mock 以下接口：

| 依赖 | 真实调用 | Mock 方式 | 影响 TC |
|------|---------|----------|:---:|
| `kanban show --json` | `hermes kanban show t_xxx` | 替换为本地 JSON 文件 / echo | TC-02, TC-03 |
| `kanban create` | `hermes kanban create --title ... --assignee ...` | `echo "created: t_mock"` + exit 0 | TC-03, TC-05 |
| `kanban comment` | `hermes kanban comment t_xxx "..."` | `echo "commented"` + exit 0 | TC-04, TC-06 |
| `kanban complete` | `hermes kanban complete t_xxx` | `echo "completed"` + exit 0 | TC-03 |

Mock 策略：在测试目录下创建 `mock_hermes.sh` 脚本，替换 PATH 使 `hermes` 指向 mock。

### 1.4 Cron 模拟

由于 cron 触发需要真实时间等待，测试中使用以下策略：
- 手动调用 `bash scripts/autopilot.sh` 模拟单次 cron tick
- 使用 `sleep` + 手动 `touch` 修改心跳文件来模拟时间流逝
- 超时测试使用极短 timeout（1min），配合 `sleep 65 && touch` 验证

---

## 2. 功能验收测试用例（AC 1-7）

### TC-01：checkpoint 初始化（AC-1）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-01 |
| **对应 AC** | AC-1：checkpoint 初始化 |
| **触发条件** | 首次运行 checkpoint.py（pipeline_state.db 不存在） |
| **前置步骤** | `rm -f /workspace/devPPL/pipeline_state.db` |
| **步骤** | 1. 确认 pipeline_state.db 不存在<br>2. 执行 `python3 -c "from pipeline.checkpoint import CheckpointDB; db = CheckpointDB('pipeline_state.db'); db.ensure_schema()"`<br>3. 检查文件是否存在<br>4. 检查表结构 |
| **预期结果** | 1. pipeline_state.db 文件创建<br>2. `pipeline_steps` 表存在<br>3. 表含所有必要字段：task_id, step_name, status, artifact_paths, started_at, finished_at, error_msg, retry_count, assigned_agent<br>4. UNIQUE(task_id, step_name) 约束生效<br>5. PRAGMA journal_mode = WAL（非功能 AC-8 同时验证） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（checkpoint 是整个管线的状态基础，初始化失败 = 管线无法跟踪任何任务）+ 功能阻断 + 无 workaround。涉及系统健康度的「用户可感知」扩展定义。 |
| **验证命令** | `sqlite3 pipeline_state.db ".schema pipeline_steps"` + `sqlite3 pipeline_state.db "PRAGMA journal_mode"` |
| **环境依赖** | 无外部依赖 |

### TC-02：断点续跑（AC-2）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-02 |
| **对应 AC** | AC-2：断点续跑 |
| **触发条件** | 模拟中途 kill autopilot，重新启动后从上次中断的步骤继续 |
| **前置步骤** | 1. 初始化 pipeline_state.db<br>2. 插入一条假数据：`task_id='t_mock_02', step_name='dev', status='done'`<br>3. 插入下一条：`task_id='t_mock_02', step_name='qa-exec', status='running'` |
| **步骤** | 1. 运行 `bash scripts/autopilot.sh`（mock kanban 返回 t_mock_02 为 running）<br>2. 观察日志和 pipeline_state.db 变化<br>3. 确认没有创建重复的 kanban card |
| **预期结果** | 1. autopilot 识别到 qa-exec 正在 running，不创建新的 dev card<br>2. pipeline_state.db 中 dev 行保持 status='done'<br>3. 没有重复的 kanban_create 调用 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（断点续跑失败会导致重复执行步骤——创建重复 kanban card 给 agent，造成混乱）+ 功能阻断（管线状态一致性基础）+ 无 workaround。涉及数据完整性的「用户可感知」扩展定义。 |
| **注意事项** | 需要在 mock hermes 中记录 kanban_create 调用次数，验证 dev step 只被创建一次。 |
| **环境依赖** | mock kanban 需实现 `kanban show` 返回 running 状态 |

### TC-03：5 步线形推进（AC-3）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-03 |
| **对应 AC** | AC-3：5 步线形推进（dev→qa-exec→va→merge→close 全部完成） |
| **触发条件** | 从零开始，每个步骤依次完成 |
| **前置步骤** | 1. 清理 pipeline_state.db<br>2. mock kanban 返回新任务 t_mock_03<br>3. 准备 mock agent 脚本：模拟 agent 执行后标记 kanban task 为 done |
| **步骤** | 1. Tick 1：autopilot 发现新任务 → 插入 step=dev, status=pending → 创建 kanban card<br>2. 模拟 dev agent 完成（kanban task done）<br>3. Tick 2：autopilot 检测 dev done → 验证 produces → 推进到 qa-exec<br>4. 模拟 qa-exec agent 完成<br>5. Tick 3：推进到 va<br>6. 模拟 va agent 完成<br>7. Tick 4：推进到 merge（autopilot 自己执行）<br>8. Tick 5：推进到 close（autopilot 自己执行）<br>9. 检查 pipeline_state.db 共 5 行 |
| **预期结果** | 1. pipeline_state.db 含 5 行：dev/qa-exec/va/merge/close，全部 status='done'<br>2. 每行有 started_at 和 finished_at（非空）<br>3. 步骤顺序严格线性，无跳步<br>4. close 步骤完成后 pipeline 报告「全部完成」 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（5 步管线是最小可行骨架，线形推进失败 = 整个 Slice 1 无法交付）+ 功能阻断（全流程核心路径）+ 无 workaround。 |
| **注意事项** | 这是 Slice 1 的核心验收用例。如果此用例失败，Slice 1 不可交付。 |
| **环境依赖** | mock kanban（创建/状态查询/完成）+ mock agent 行为模拟 |

### TC-04：超时检测（AC-4）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-04 |
| **对应 AC** | AC-4：超时检测 |
| **触发条件** | 某步骤运行时间 > timeout_min |
| **前置步骤** | 1. 修改 contracts.jsonl 中 dev 的 timeout_min=1<br>2. 插入 checkpoint：task_id='t_mock_04', step='dev', status='running', started_at=<2min ago> |
| **步骤** | 1. 运行 autopilot.sh<br>2. 检查 pipeline_state.db 中 dev 的状态变化<br>3. 检查是否发送 kanban_comment 告警 |
| **预期结果** | 1. status 变为 'failed'<br>2. error_msg 包含 "timeout: 1 min"（或类似描述）<br>3. kanban_comment 被调用一次，含告警信息<br>4. 管线停止推进（不创建下一步 kanban card） |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（超时检测失效 = 管线在 agent 卡死时无限等待，整个管线被阻塞）+ 功能阻断（超时是 Slice 1 唯一的自动异常处理机制）+ 无 workaround。 |
| **环境依赖** | mock kanban comment 需记录调用参数 |

### TC-05：produces 验证（AC-5）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-05 |
| **对应 AC** | AC-5：produces 验证 |
| **触发条件** | 步骤完成后 produces 文件缺失 |
| **前置步骤** | 1. contracts.jsonl 中 dev 的 produces=["branch","code_changes"]<br>2. 插入 checkpoint：task_id='t_mock_05', step='dev', status='running'<br>3. mock kanban 返回 dev task 为 done<br>4. 确保磁盘上不存在 branch 文件 |
| **步骤** | 1. 运行 autopilot.sh<br>2. 检查状态更新 |
| **预期结果** | 1. dev 状态变为 'failed'<br>2. error_msg 包含 "missing produces: branch"（或类似描述）<br>3. 不推进到 qa-exec |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（produces 验证是合约约束的唯一落地检查，缺失导致下游步骤拿不到输入）+ 功能阻断（合约校验失效则管线形同虚设）+ 无 workaround。 |
| **注意事项** | 此项验证需区分：produces 文件缺失 → failed；produces 文件存在 → done。两个方向都要测。 |
| **环境依赖** | 需在临时目录创建/删除文件以模拟文件存在性 |

### TC-06：flock 防重入（AC-6）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-06 |
| **对应 AC** | AC-6：flock 锁 |
| **触发条件** | 同时启动两个 autopilot.sh 实例 |
| **前置步骤** | 1. 创建一个长时间运行的 autopilot 变体（sleep 30s 在获取锁后）<br>2. 在后台启动第一个实例 |
| **步骤** | 1. 第一个实例启动并持有锁<br>2. 立即启动第二个实例<br>3. 观察第二个实例的输出和 exit code |
| **预期结果** | 1. 第二个实例输出含 "另一 autopilot 实例正在运行"（或 "上一轮未完成，跳过"）<br>2. 第二个实例 exit code = 0（优雅退出，不报错）<br>3. 第一个实例完成后释放锁<br>4. pipeline_state.db 状态一致（无重复写入） |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知（双实例并发可能导致状态竞写，卡坏 pipeline_state.db）+ 功能阻断但有 workaround（kill 多余进程）。与数据完整性相关，但不涉及 S/A 级数据，按正常公式评定。 |
| **环境依赖** | 需真实 flock 支持（Linux util-linux） |

### TC-07：JSONL 合约可解析（AC-7）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-07 |
| **对应 AC** | AC-7：JSONL 合约可解析 |
| **触发条件** | 读取 contracts.jsonl |
| **前置步骤** | contracts.jsonl 已部署到 config/ 目录 |
| **步骤** | 1. `python3 -c "import json; lines=[json.loads(l) for l in open('config/contracts.jsonl')]; print(f'{len(lines)} steps loaded')"`<br>2. 验证每行的 required 字段<br>3. 验证 step 字段互不重复<br>4. 验证 step 顺序与 STEP_ORDER 一致 |
| **预期结果** | 1. 5 行全部可解析，无 JSON 解析异常<br>2. 每行含 step/requires/produces/timeout_min 字段<br>3. timeout_min 为正整数<br>4. step 字段值不重复<br>5. requires/produces 为合法 JSON array |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（JSONL 不可解析 = 整个合约引擎无法启动，管线停止工作）+ 功能阻断（合约是管线推进的元数据基础）+ 无 workaround。 |
| **环境依赖** | 无 |

---

## 3. 非功能验收测试用例（AC 8-10）

### TC-08：SQLite WAL 模式（AC-8）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-08 |
| **对应 AC** | AC-8：SQLite WAL 模式 |
| **触发条件** | checkpoint.py ensure_schema() 执行后 |
| **前置步骤** | 删除旧 pipeline_state.db |
| **步骤** | 1. 执行 `python3 -c "from pipeline.checkpoint import CheckpointDB; db = CheckpointDB('pipeline_state.db'); db.ensure_schema()"`<br>2. 执行 `sqlite3 pipeline_state.db "PRAGMA journal_mode"` |
| **预期结果** | PRAGMA journal_mode 返回 "wal" |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——系统健康度（WAL 缺失在高并发读写下可能导致锁冲突）。删除模式下回退到 journal 仍有 workaround（加 flock 防并发写），但有性能退化风险。 |
| **环境依赖** | 无 |

### TC-09：幂等建表（AC-9）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-09 |
| **对应 AC** | AC-9：幂等建表 |
| **触发条件** | ensure_schema() 在已存在 pipeline_state.db 时重复调用 |
| **前置步骤** | 1. 执行 ensure_schema() 第一次（创建 db）<br>2. 插入一条测试数据 |
| **步骤** | 1. 执行 ensure_schema() 第二次<br>2. 检查之前插入的数据是否仍然存在<br>3. 检查是否有异常抛出 |
| **预期结果** | 1. 第二次调用不抛异常<br>2. 已有数据不受影响（不会 DROP TABLE 再 CREATE）<br>3. 表结构不变 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——数据完整性（幂等建表失败可能删掉已有数据）。有 workaround（先备份再重建）但应在一开始就做对。 |
| **环境依赖** | 无 |

### TC-10：日志可读（AC-10）

| 维度 | 内容 |
|------|------|
| **用例编号** | TC-10 |
| **对应 AC** | AC-10：日志可读 |
| **触发条件** | autopilot.sh 运行时 |
| **前置步骤** | 正常启动 autopilot.sh |
| **步骤** | 1. 检查 stdout/stderr 每行是否以 `[autopilot]` 标记开头<br>2. 检查关键操作是否有对应日志（任务发现、步骤推进、完成/失败）<br>3. 验证无日志行以 `[autopilot]` 标记失配 |
| **预期结果** | 1. 所有日志行带 `[autopilot]` 前缀<br>2. 开始/结束用 `===` 分隔线<br>3. 每个任务的处理有明确日志（处理中/完成/失败）<br>4. 错误日志写入 stderr |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户可感知（OC/Frank 通过日志确认管线状态）+ 不影响核心任务完成（管线仍可运行）+ 有变通方案（直接查 pipeline_state.db）。 |
| **环境依赖** | 无 |

---

## 4. 测试场景用例（5 场景）

### TS-01：正常流转（全绿线）

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-01 |
| **场景描述** | 创建 kanban task → 各 agent 依次完成 → 5 步全部 done → close 执行 kanban_complete |
| **操作** | 与 TC-03 一致（全流程正向测试） |
| **预期结果** | 所有 5 步 status='done'，每条有 time 戳，close 步骤触发 kanban_complete |
| **与 TC 关系** | TC-03 的上层场景描述 |

### TS-02：无任务时静默退出

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-02 |
| **场景描述** | cron 触发 autopilot，但 kanban 无 running 任务 |
| **操作** | 1. 确保 pipeline_state.db 中无 active 任务<br>2. 运行 autopilot.sh |
| **预期结果** | 输出 "无 running 任务" 或等效消息，exit code = 0，不产生副作用 |
| **风险等级** | **MINOR** |
| **分级依据** | 按标准 §1.2：用户不可感知（cron 后台运行），但系统健康度相关——空跑不应浪费资源或报错。 |
| **环境依赖** | mock kanban 返回空列表 |

### TS-03：新任务首次检测

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-03 |
| **场景描述** | autopilot 发现 task_id 不在 pipeline_state.db 中 |
| **操作** | 1. 确保 pipeline_state.db 干净（无记录）<br>2. mock kanban 返回一个 running 任务<br>3. 运行 autopilot.sh |
| **预期结果** | 1. 插入 step='dev', status='pending'<br>2. 创建 dev kanban card（kanban_create 被调用）<br>3. 日志输出 "新任务" 及 task_id |
| **环境依赖** | mock kanban create 需记录调用 |

### TS-04：步骤失败 — 停止推进

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-04 |
| **场景描述** | agent 返回失败 → pipeline_state.db status='failed' → kanban_comment 告警 → 不继续推进 |
| **操作** | 1. 插入 checkpoint：dev status='failed'<br>2. 运行 autopilot.sh |
| **预期结果** | 1. 日志输出 "步骤 dev 失败，停止推进"（或等效）<br>2. kanban_comment 被调用一次<br>3. 不创建下一步（qa-exec）的 kanban card<br>4. pipeline_state.db 不新增 qa-exec 行 |
| **风险等级** | **BLOCKER** |
| **分级依据** | 按标准 §1.2：用户可感知（失败后继续推进可能导致错误传播到下游步骤）+ 功能阻断（失败停止是 Slice 1 的唯一安全边界）+ 无 workaround。 |
| **环境依赖** | mock kanban comment |

### TS-05：超时（与 TC-04 对应）

| 维度 | 内容 |
|------|------|
| **场景编号** | TS-05 |
| **场景描述** | 某步运行时间 > timeout_min → status='failed', error_msg="timeout: N min" |
| **操作** | 与 TC-04 一致 |
| **预期结果** | status='failed', error_msg 含 timeout 信息，kanban_comment 告警 |
| **与 TC 关系** | TC-04 的精确验证 |

---

## 5. 边界条件 & 异常路径

### BE-01：pipeline_state.db 文件不可写

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-01 |
| **触发条件** | pipeline_state.db 所在目录只读，或文件被 chmod 000 |
| **操作** | `chmod 000 pipeline_state.db && bash scripts/autopilot.sh` |
| **预期结果** | 不崩溃（无 uncaught exception / segfault），输出错误日志，exit code ≠ 0 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——系统健康度（crash 意味着 cron 任务静默失败，管理员收不到告警）。有 workaround（手动修复权限后重启 cron）。 |

### BE-02：contracts.jsonl 文件缺失

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-02 |
| **触发条件** | `config/contracts.jsonl` 不存在 |
| **操作** | `mv config/contracts.jsonl config/contracts.jsonl.bak && bash scripts/autopilot.sh` |
| **预期结果** | 不崩溃，输出明确错误信息（如 "contracts.jsonl not found"），exit code ≠ 0 |
| **风险等级** | **MAJOR** |
| **分级依据** | 按标准 §1.2：用户可感知的扩展定义——系统健康度。合约缺失 = 管线无法判定步骤顺序。有 workaround（恢复文件）。 |

### BE-03：step_name 不在合约中

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-03 |
| **触发条件** | pipeline_state.db 中某行 step_name 不在 contracts.jsonl 的步骤列表中 |
| **操作** | 手动插入一条 step_name='unknown_step' 的记录，运行 autopilot.sh |
| **预期结果** | 不崩溃，日志输出警告，pipeline 标记该任务为 error 或跳过 |
| **风险等级** | **MAJOR** |
| **分级依据** | 数据完整性问题（B 级数据：内部状态），按正常公式。有 workaround（手动修复 DB）。 |

### BE-04：并发写入 pipeline_state.db（无 flock 保护场景）

| 维度 | 内容 |
|------|------|
| **用例编号** | BE-04 |
| **触发条件** | 绕过 flock 直接并发写入 pipeline_state.db |
| **操作** | 两个进程同时 `INSERT INTO pipeline_steps` 同一 task_id+step_name |
| **预期结果** | UNIQUE 约束阻止重复插入，至少一个进程返回 constraint violation（不静默覆盖） |
| **风险等级** | **MINOR** |
| **分级依据** | 数据完整性（B 级），flock 是主保护机制，此边界是 defense-in-depth。 |

---

## 6. 测试执行顺序与依赖

```
Round 1: 环境 + 静态检查（无外部依赖，可立即执行）
  ├── TC-07: JSONL 可解析
  ├── TC-01: checkpoint 初始化（同时验证 TC-08 WAL + TC-09 幂等）
  └── TC-10: 日志可读

Round 2: 核心流程（需 mock kanban）
  ├── TS-02: 无任务静默退出
  ├── TS-03: 新任务首次检测
  ├── TC-06: flock 防重入
  ├── TC-02: 断点续跑
  ├── TC-04: 超时检测
  ├── TC-05: produces 验证
  ├── TS-04: 步骤失败停止
  └── TC-03 / TS-01: 全绿线 5 步推进 ← 最后执行，依赖前面所有 bug 被修复

Round 3: 边界条件
  ├── BE-01: DB 不可写
  ├── BE-02: contracts.jsonl 缺失
  ├── BE-03: 未知 step_name
  └── BE-04: 无 flock 并发写
```

---

## 7. 风险矩阵

| 风险 | 级别 | 可能性 | 影响 | 缓解 |
|------|:---:|:---:|------|------|
| PRD vs 架构步骤名冲突未裁定 | **BLOCKER** | 确认存在 | 测试无法执行——不知道该测哪 5 步 | D1 审定会上要求产品+架构师当场裁定 |
| kanban mock 不准确导致假阳性 | **MAJOR** | 中 | TC-02/03/04/05 全部受影响 | mock 脚本需 code review + 用真实 hermes CLI 输出格式验证 |
| autopilot.sh 的 mock 边界不完整 | **MAJOR** | 中 | 漏测真实环境行为 | D2 测试时必须有一次在真实 cron + 真实 kanban 环境下执行 |
| timeout_min=1 太短，可能误判 | MINOR | 低 | TC-04 假阳性 | 可用 timeout_min=0 做极端值测试，再设 1min 验证实际阈值 |

---

## 8. D1 审定 Checklist

审定会需确认以下问题：

- [ ] **D1-F1 步骤名冲突**：最终 5 步是 PRD 的 `dev→qa-exec→va→merge→close` 还是架构的 `dev→qa-d1→qa-exec→merge→close`？
- [ ] **D1-F2 project_config**：Slice 1 是否建 project_config 表？init_project.py 是否实现？
- [ ] **D1-F3 user_version/verdict 列**：user_version = 1 还是 2？是否预置 verdict 三列？
- [ ] **Mock 策略**：是否接受 mock kanban 的测试方式？还是要求全部真实环境？
- [ ] **AC-4 超时检测实现**：架构 §3.4 写「Slice 1 不做超时检测」，PRD AC-4 要求超时检测。谁为准？
- [ ] **AC 优先级**：如果时间有限，哪些 AC 是 D1 必须通过的（建议：AC-1/3/6/7）？

---

## 9. QA 初步判定

| 判定维度 | 结论 |
|---------|------|
| **可测试性** | ⚠️ 有条件可测——需先裁定 3 项 PRD/架构冲突 + 准备 mock kanban 环境 |
| **覆盖率** | 10 AC + 5 场景 + 4 边界条件 = 19 用例，预计覆盖 Slice 1 所有公开接口和异常路径 |
| **阻塞项** | D1-F1/D1-F2/D1-F3 未裁定前，Round 2 测试无法执行（不知道 step 名和 schema 字段） |
| **测试时间估算** | Round 1（环境+静态）：0.5h；Round 2（核心流程+场景）：2.5h；Round 3（边界）：1h。总计约 4h |
| **发布门禁建议** | TC-01/02/03/04/05/06/07 全部 BLOCKER → 必须 7/7 PASS。TC-08/09 为 MAJOR，允许 ≤1 项延后（带 known issue）。TC-10 为 MINOR 不阻塞。 |

---

> QA 测试方案完毕。下一步：发起 D1 审定（product + architect + engineer），裁定冲突后进入 Round 1 测试执行。
>
> 分级依据：`docs/standards/qa-finding-classification.md` v1.0
