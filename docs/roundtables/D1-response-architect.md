# D1 审定 — Architect 发言：Slice 1 测试方案架构评审

> 发言人：高见远（架构师） | 日期：2026-07-30
> 评审对象：QA 测试方案 `docs/qa/slice1-pipeline-test-plan.md` (411 行, 19 用例)
> 参考：架构设计 `docs/arch-slice1-pipeline-data-layer.md` v1.0、PRD `docs/prd/slice1-pipeline-prd.md` v1.0
> 前置裁定：4 项冲突已由 Product 裁定 + Architect 接受（`t_a221d3b1`）

---

## 一、4 项冲突的架构判断（D1-F1 ~ D1-F4）

前置结论：Product 的 4 项裁定已在 `t_a221d3b1` 中由架构师全部接受。以下从「裁定是否落地到代码和文档」角度重新审查。

### D1-F1：5 步步名冲突 — 已裁定但未落地

| 维度 | 内容 |
|------|------|
| **裁定结果** | 使用 PRD 版本：`dev → qa-exec → va → merge → close`（va 替代 qa-d1）|
| **架构设计文档** | ✅ §0.1 已使用正确步骤链 |
| **contracts.jsonl** | ✅ 正确：5 步为 dev/qa-exec/va/merge/close |
| **pipeline/constants.py** | ❌ 仍为 `["dev", "qa-d1", "qa-exec", "merge", "close"]` — 含 qa-d1，缺 va |
| **scripts/autopilot.sh** | ❌ 第 107-113 行仍有 `qa-d1)` case，无 `va)` case |
| **pipeline/state.py** | ❌ `_agent_for_step()` 第 278 行仍有 `"qa-d1": "game-qa"` 映射 |

**架构判定**：Product 裁定已接受但代码未同步。constants.py 是全局常量，autopilot.sh 依赖它做步骤分发，state.py 用它做步骤完整性检查。这三个文件不一致会导致：管线推进到 va 时 autopilot.sh 落入 `*）` 未知步骤分支，状态机判定「全部完成」的条件永远不满足。

**修复范围**：约 6 处修改（constants.py 1 行 + autopilot.sh qa-d1→va case + state.py _agent_for_step 1 行），10 分钟工作量。

### D1-F2：project_config 表归属 — 已正确落地

| 维度 | 内容 |
|------|------|
| **裁定结果** | Slice 1 就建 project_config（架构方案被采纳）|
| **架构设计文档** | ✅ §0.2 裁决详尽，§1.1 DDL 含 project_config，§1.4 含预定义 key |
| **checkpoint.py** | ✅ 含 project_config 表（第 35-38 行）|
| **config.py** | ✅ 只读接口已实现（get_project_config + get_config_item）|
| **init_project.py** | ✅ 初始化脚本已实现（argparse CLI）|
| **autopilot.sh** | ✅ 第 38-48 行读取 project_config 写入日志头 |

**架构判定**：无问题。这是 4 项冲突中唯一已完全正确落地的。project_config 的三件套（constants + config + init_project）与架构设计 §6.2-6.4 完全一致。

### D1-F3：user_version / verdict 列预置 — 已裁定但代码未回滚

| 维度 | 内容 |
|------|------|
| **裁定结果** | user_version = 1，不预置 verdict/verdict_detail/contract_check_passed 三列 |
| **架构设计文档** | ✅ §1.3 明确 user_version=1，无 verdict 列（「SQLite ALTER ADD COLUMN 零风险」）|
| **checkpoint.py SCHEMA_SQL** | ❌ `PRAGMA user_version = 2`（第 15 行），含 verdict/verdict_detail/contract_check_passed 列（第 29-31 行）|
| **checkpoint.py 文档字符串** | ❌ 第 4 行：「user_version = 2：v1 初始建表即含 verdict 三列」— 注释已过时 |

**架构判定**：checkpoint.py 的 v2 schema 是 R5 时期的方案（用户版本号冲突判断：当时认为「预置三列为 NULL 省一次 ALTER」更优）。Product 裁定后，架构师接受了「schema 清晰度 > 省 ALTER 语句」的判断，user_version 回退到 1。但 checkpoint.py 未同步修改。这导致：任何读 DDL 的人会困惑 verdict 列的用途（PRD §1.2 明确 Slice 1 不含 verdict），Sl 2 迁移时 user_version=2 已被占用（实际 Sl 2 需要从 1 → 2 迁移）。

**修复范围**：checkpoint.py SCHEMA_SQL 中删除 verdict 三列 + 改 user_version=2 → 1 + 修改文档字符串。约 5 行修改。

### D1-F4：超时检测实现 — 已裁定但逻辑未实现

| 维度 | 内容 |
|------|------|
| **裁定结果** | Slice 1 做超时检测（简化版：检测→failed→停止，不重试）|
| **架构设计文档** | ✅ §3.4：「Slice 1 做简化版：检测→failed→停止。实现为只读检查 `finished_at - started_at > timeout_min`」|
| **pipeline/state.py** | ❌ `determine_next_action()` 中无超时检测逻辑。running 步骤只检查 kanban 状态（done/failed），不检查 `started_at + timeout_min < now` |
| **contracts.jsonl** | ✅ timeout_min 字段存在（60/45/20/20/15），可被超时检测使用 |

**架构判定**：这是 4 项中最实质性的缺失。架构 §3.4 的设计是：在 `determine_next_action()` 中，对于 status='running' 的步骤，先检查是否超时 → 超时则 `upsert_step(status='failed', error_msg='timeout: N min')` → 返回 error → autopilot.sh 发 kanban_comment 告警。当前 state.py 直接从 kanban 状态做判断，完全跳过了超时检查。QA 的 TC-04 和 TS-05 依赖此逻辑存在。

**修复范围**：state.py `determine_next_action()` 中 running/pending 分支前插入约 10 行超时检查。影响函数：`determine_next_action()`（第 154 行附近）。

---

## 二、QA 测试方案覆盖率评审

### 2.1 覆盖矩阵

| 架构元素 | 对应测试用例 | 覆盖判定 |
|----------|------------|:------:|
| **§1 pipeline_state.db schema** | TC-01, TC-08, TC-09 | ✅ 充分 |
| **§1.1 DDL 表结构** | TC-01（检查所有字段 + UNIQUE 约束）| ✅ |
| **§1.3 user_version=1** | ⚠️ 未覆盖 — TC-01 不检查 user_version | ⚪ 缺口 |
| **§1.4 project_config 初始化** | ❌ 无对应测试用例 | 🔴 缺口 |
| **§2 合约 JSONL** | TC-07 | ✅ 充分 |
| **§3 state.py 核心逻辑** | TC-02, TC-03, TC-04, TC-05, TS-01~TS-05 | ✅ |
| **§3.1 数据流** | TS-01（全绿线集成测试）| ✅ |
| **§3.3 状态机** | TC-02（断点续跑）, TS-04（步骤失败停止）| ✅ |
| **§3.4 超时检测** | TC-04, TS-05 | ⚠️ 但被测功能尚未实现 |
| **§4 autopilot.sh** | TC-06（flock）, TC-10（日志）, TS-02（空任务）| ✅ |
| **§5 组件间接口** | TS-01（端到端集成）| ✅ |
| **§6 pipeline/ 目录结构** | TC-01（checkpoint import）, TC-07（JSONL 解析）| ✅ |
| **config.py 只读接口** | ❌ 无对应测试用例 | 🟡 缺口 |
| **init_project.py 初始化流程** | ❌ 无对应测试用例 | 🟡 缺口 |
| **_agent_for_step() agent 映射** | ⚠️ 隐式覆盖（TC-03 的 kanban_create 调用了映射）| 🟡 弱覆盖 |
| **get_active_tasks() 查询** | ⚠️ 隐式覆盖（TS-03）| 🟡 弱覆盖 |
| **upsert_step() UPSERT 语义** | TC-02（断点续跑不重复插入）| ✅ |
| **has_task()** | ❌ 无直接测试 | 🟡 弱覆盖 |

### 2.2 覆盖率评估

| 维度 | 值 |
|------|:--:|
| 核心功能（step 推进/状态判定/合约解析） | 100% |
| 数据层（schema CRUD / WAL / 幂等） | 90% |
| 配置层（project_config / init_project） | **0%** — 完全未覆盖 |
| 边界条件 | 4 用例覆盖 4 个已知风险点 |
| 集成测试 | TS-01/TS-03 覆盖端到端 |

### 2.3 缺口分析

**🔴 关键缺口：project_config 初始化与读取**

QA 测试方案完全未覆盖 `init_project.py` 和 `config.py`。按架构设计 §1.4 + §5.2，project_config 是管线启动的前提条件——autopilot.sh 第 38-48 行读取 `project_type` 和 `project_name` 写入日志头。如果 project_config 未初始化，autopilot 仍能运行（fallback 到 'unknown'/'devPPL'），但日志标识丢失。

**建议新增 2 个测试用例**：

| 用例 | 内容 |
|------|------|
| **TC-11** | init_project.py 初始化：执行 `python3 pipeline/init_project.py --project-type system_mechanism` → 验证 pipeline_state.db 中 project_config 表的 4 个 key-value 均已写入 |
| **TC-12** | config.py 只读：调用 `get_project_config()` → 验证返回的 dict 包含 project_type/project_name/backup_script/notify_script；调用 `get_config_item('project_type')` → 验证返回 `system_mechanism` |

**🟡 弱覆盖：user_version 检查**

TC-01 验证了 schema DDL 包含正确字段，但未检查 `PRAGMA user_version` 的值。当前 checkpoint.py 仍输出 user_version=2（应为 1）。建议在 TC-01 的验证命令中追加 `sqlite3 pipeline_state.db "PRAGMA user_version"`。

**🟡 弱覆盖：_agent_for_step() 映射**

TC-03 的全绿线测试隐式验证了 agent 分配（通过检查 kanban_create 的 --assignee 参数），但没有独立的映射表测试。风险：如果 _agent_for_step() 中仍有 qa-d1 的旧映射（实际存在），而 contracts.jsonl 中没有 qa-d1 步骤，该映射是死代码。

### 2.4 整体评价

QA 的 19 个用例对架构核心路径（数据层 + 状态机 + 合约 + 调度）覆盖率良好。两个缺口集中在配置层（project_config），但该层的复杂度极低（一张 key-value 表，4 个预定义键），缺失不影响核心管线验证。建议 D1 测试执行时追加 TC-11/TC-12，或将其推至 D2（project_config 在 Slice 2 的备份策略查询中才真正发挥作用）。

---

## 三、代码与架构设计一致性评审

### 3.1 文件级一致性

| 文件 | 架构设计 | 实际代码 | 一致性 |
|------|---------|---------|:------:|
| `pipeline/__init__.py` | ~2 行空文件 | 2 行 | ✅ |
| `pipeline/constants.py` | ~25 行，STEP_NAMES=[dev,qa-exec,va,merge,close] | 14 行，STEP_NAMES=[dev,qa-d1,qa-exec,merge,close] | ❌ F1 未落地 |
| `pipeline/checkpoint.py` | ~120 行，user_version=1，10 字段 | 246 行，user_version=2，13 字段 | ❌ F3 未落地 |
| `pipeline/config.py` | ~30 行，get_project_config() | 40 行，get_project_config() + get_config_item() | ✅ 有小增强 |
| `pipeline/state.py` | ~120 行，含超时检测 | 346 行，无超时检测 | ❌ F4 未实现 |
| `pipeline/init_project.py` | ~25 行，argparse CLI | 53 行 | ✅ |
| `config/contracts.jsonl` | 5 行，5 步 | 5 行 | ✅ |
| `scripts/autopilot.sh` | ~60 行，5 步分发 | 174 行，含 qa-d1 case | ❌ F1 未落地 |

### 3.2 关键不一致汇总

| # | 文件:行 | 不一致描述 | 严重度 | 关联冲突 |
|---|---------|----------|:------:|:------:|
| **I1** | `constants.py:13` | STEP_NAMES 含 `qa-d1` 缺 `va` | BLOCKER | D1-F1 |
| **I2** | `autopilot.sh:107-113` | `qa-d1)` case 存在（不应属于 Slice 1）| BLOCKER | D1-F1 |
| **I3** | `autopilot.sh` | 无 `va)` case（va 步骤无法自动处理）| BLOCKER | D1-F1 |
| **I4** | `checkpoint.py:15,29-31` | user_version=2 + verdict 三列 | MAJOR | D1-F3 |
| **I5** | `state.py` | 无超时检测逻辑（架构 §3.4 要求）| MAJOR | D1-F4 |
| **I6** | `state.py:278` | `_agent_for_step()` 含 `"qa-d1": "game-qa"` | MINOR | D1-F1（死代码）|
| **I7** | `checkpoint.py:4` | 文档字符串「user_version = 2」已过时 | TRIVIAL | D1-F3 |

### 3.3 值得注意的设计偏离（非 Bug）

**state.py 行数膨胀**：架构估算 ~120 行，实际 346 行。主要差异来源：
- `determine_next_action()` 内联了架构设计中分散在多个小函数的逻辑（含 kanban 状态轮询 / produces 校验 / 下一步推进），比设计更集中
- `_check_produces()` 额外做了磁盘文件存在性检查（第 307 行），架构设计只要求检查 artifact_paths 字段
- 错误处理比设计更细粒度（每个异常路径都有独立 return）

**评估**：行数膨胀本身不是问题——集中的状态机比分散的小函数更易理解和维护。但需要确认 `_check_produces()` 的磁盘检查不会在真实环境中引入文件系统性能问题（每 2 分钟 cron tick 对每个活跃任务做 Path.exists()）。

**config.py 增强**：新增 `get_config_item()` 单键查询函数。架构设计只定义了 `get_project_config()` 全量读取。这个增强合理——autopilot.sh 只需要 project_type 和 project_name 两个键，全量读取浪费 2 个多余的 DB 查询。

### 3.4 代码质量观察

**正面**：
- CheckpointDB 的 UPSERT 实现利用了 UNIQUE(task_id, step_name) 约束，保留了 started_at 的读取逻辑（第 92-96 行），比简单的 INSERT OR REPLACE 更安全
- autopilot.sh 的 flock 实现正确（exec 200> + flock -n + exit 时自动释放）
- state.py 的异常处理覆盖了 hermes CLI 不可用 / JSON 解析失败 / 超时三种场景
- contracts.jsonl 的格式与架构设计逐字一致

**需要改进**：
- checkpoint.py 的 `_connect()` 每次创建新连接（无连接池），在高频 cron 下可能产生 SQLite 文件锁竞争。但在 flock 保护下（单一进程写入），这不是实际问题
- state.py 的 `get_kanban_task_state()` 对每个活跃任务每次都 subprocess.run，没有缓存。在活跃任务数量 <5 时无影响

---

## 四、修复优先级与工作量

### 必须修复（D1 测试执行前）

| 优先级 | 修复项 | 文件 | 行数 | 时间 |
|:------:|--------|------|:---:|:---:|
| **P0** | I1: STEP_NAMES 修正 | `constants.py:13` | 1 | 1min |
| **P0** | I2: 删除 autopilot.sh qa-d1 case | `autopilot.sh:107-113` | 7（删）| 2min |
| **P0** | I3: 新增 autopilot.sh va case | `autopilot.sh` | +8 | 3min |
| **P0** | I4: user_version=1 + 删除 verdict 列 | `checkpoint.py:4,15,29-31` | 4 | 2min |
| **P0** | I5: 超时检测逻辑 | `state.py` | +10 | 10min |
| **P1** | I6: 删除 _agent_for_step qa-d1 | `state.py:278` | 1（删）| 1min |
| **P2** | I7: 修正 checkpoint.py 文档字符串 | `checkpoint.py:4` | 1 | 1min |

**总计**：约 32 行修改 / 20 分钟工作量。全部在 3 个文件（constants.py, autopilot.sh, checkpoint.py, state.py）中，无跨模块影响。

### 必须在 D1 测试方案中补充

| 优先级 | 补充项 | 位置 | 时间 |
|:------:|--------|------|:---:|
| **P1** | TC-11: init_project.py 初始化验证 | §2 或 §5 | 10min |
| **P1** | TC-12: config.py 读取验证 | §2 或 §5 | 10min |
| **P2** | TC-01 追加 user_version 检查 | TC-01 验证命令 | 1min |

---

## 五、一句话总结

> Product 的 4 项裁定（F1 步骤名 / F2 project_config / F3 user_version / F4 超时）架构上全部正确，但 F1/F3/F4 的代码未同步落地。contracts.jsonl 和架构设计文档已正确，constants.py + checkpoint.py + autopilot.sh + state.py 存在 5 处不一致（3 BLOCKER + 2 MAJOR）。QA 测试方案覆盖率良好但缺 project_config 测试。全部 P0 修复约 20 分钟，修复后代码与架构设计完全对齐。

---

> 架构师发言完毕。下一站：engineer（寇豆码），请按上述 P0 清单修复代码，然后 QA 进入 Round 1 测试执行。
