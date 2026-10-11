# Slice 3 PRD — 收尾层：DPL-011 + dashboard + 备份策略 + S6 闭环 + 修复

> 作者：许清楚（产品负责人） | 日期：2026-07-30 | 版本：v1.0
> 来源：DPL-012 R5 最终统一工作流 → Slice 3（收尾层，~10h）
> 前提：Slice 1 + Slice 2 已交付：7 步管线（dev→qa-d1→qa-exec→qa-d2→va→merge→close）+ 21 分支 + rollback + gate_roundtable

---

## 0. Slice 3 在整体架构中的定位

DPL-012 最终按三 Slice 分批交付：

```
Slice 1 (3.5h): checkpoint + 5 步合约 + 简化 autopilot     ✅ 已交付
Slice 2 (3.5h): 完整 7 步 + 21 分支 + 回退 + gate_roundtable ✅ 已交付
Slice 3 (~10h):  DPL-011 + dashboard + 备份 + S6 闭环 + 修复 ← 本 PRD
```

**Slice 3 的产品目标**：将管线从"能跑"升级为"可运维"。解决三个关键问题：

1. **跨会话记忆断裂**（DPL-011）：agent 每次启动只知道静态规范，不知道"昨天做到哪了、上次犯了什么错"
2. **状态不可见**（dashboard）：Frank 和 OC 无法一眼看到管线全貌——哪些任务卡住了、哪些步骤红了
3. **数据安全未闭环**（备份 + S6）：merge/close 的备份命令仍是 stub，close.sh 的 GAI/manifest/备份/通知未实际落地

另修复两个已发现的线上缺陷（autopilot 任务发现盲区 + cron 上下文失效）。

**与 Slice 2 的关系**：Slice 3 不修改管线流转逻辑（7 步 + 21 分支保持不变）。Sl 3 的六个子系统是独立模块——通过 pipeline_state.db 和 kanban.db 与管线解耦连接，各自可独立开发、测试、部署。

---

## 1. DPL-011：跨会话记忆（boot_context.py + .hermes.md 双段式）

### 1.1 问题

当前 `.hermes.md` 是纯静态的规范文件（30 行）。agent 每次启动时加载它，知道项目的 QA 标准、申诉流程——但不知道：

- 当前有哪些活跃的管线任务
- 上一次被纠正了什么（Product 反例）
- 最近的 roundtable 裁定是什么
- 管线整体健康状况

**用户影响**：agent 在跨会话时反复犯同样的错误，Product 需要重复纠正。

### 1.2 方案：双段式 .hermes.md

```
┌─────────────────────────────────────────────┐
│ .hermes.md                                  │
│                                             │
│ ┌── 静态段（人工维护）───────────────────┐   │
│ │ · 项目规范（QA 标准、申诉流程、SLA）   │   │
│ │ · 发布门禁                              │   │
│ │ · 关键规则                              │   │
│ │                                         │   │
│ │ 维护者：Product（许清楚）                │   │
│ │ 更新频率：按需（PRD 变更时）             │   │
│ └─────────────────────────────────────────┘   │
│                                             │
│ ┌── 动态段（boot_context cron 生成）──────┐   │
│ │ · 活跃任务摘要（task_id + step + status)│   │
│ │ · 最近决策（3 条最近的 roundtable 结论） │   │
│ │ · 最近纠正（3 条最近的 Product 反例）   │   │
│ │ · 管线健康（红/黄/绿 灯总数）            │   │
│ │                                         │   │
│ │ 维护者：boot_context.py（cron 每 5min）  │   │
│ │ 硬限制：≤ 2000 字符（约 500 tokens）     │   │
│ └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 1.3 静态段——归档规范

**新增文件**：`/workspace/devPPL/config/hermes_static.md`

将当前 `.hermes.md` 中的人工维护内容移到独立的静态模板文件。理由：

- `.hermes.md` 是生成文件（含动态段），不应被 git 跟踪为人工编辑目标
- 静态模板独立存于 `config/hermes_static.md`，Product 编辑它，git 追踪变更
- boot_context cron 每次运行时拼接：静态模板 + 动态段 → 写入 `.hermes.md`

**切换操作**（Slice 3 部署时执行一次）：

```bash
# 人工操作（Product 执行）
cp .hermes.md config/hermes_static.md   # 复制当前内容到模板
echo "" > .hermes.md                     # 清空原文件（将由 cron 重写）
git add config/hermes_static.md
```

### 1.4 动态段格式（boot_context 产出）

boot_context cron 每 5 分钟运行，产出以下动态段（追加在静态段之后，以 `---` 分隔）：

```markdown
---

## 活跃管线任务（boot_context · 2026-07-30T22:15:00Z）

| 任务 | 步骤 | 状态 | Agent | 时长 |
|------|------|:----:|-------|------|
| t_3831c640 | dev | 🟡 running | game-engine | 12m |
| t_721e24b0 | va | 🔴 blocked | verifier | — |
| t_5a3f9c12 | close | 🟢 done | autopilot | — |

**管线健康**：🟢 1 · 🟡 1 · 🔴 1 · ⬜ 0

### 最近决策
- 2026-07-30 · D 类 roundtable (t_6d3046d0)：QA 发现 BLOCKER → Frank 裁定降级为 MAJOR，继续推进
- 2026-07-30 · D1 评审 (t_3831c640)：覆盖率 100%，pass
- 2026-07-29 · A 类 roundtable (t_2b1c8e00)：方案选择 → 采用方案 B（增量 checkpoint）

### 最近纠正
- va agent 未按标准 §1.2 判定 FALSIFIED，Product 要求重审。标准：FALSIFIED 必须能复现
- qa-exec agent 漏报安全漏洞，已补充到 test_report.md
```

**字符预算**：动态段硬限 2000 字符。如果超出，优先裁剪"最近决策"和"最近纠正"中的旧条目（保留最近 3 条），保持"活跃任务"表的完整。

### 1.5 boot_context.py 数据源

```
数据来源：
  pipeline_state.db  → 活跃任务（status IN ('pending','running','failed','blocked')）
  kanban.db          → 任务标题、优先级、assignee
  session DB         → 最近 Product 反例（搜索关键词："纠正"、"驳回"、Product ruling）
  memory             → 最近 roundtable 结论（含 task_id + 结论摘要）
```

**产物**：`.hermes.md`（完整文件，覆盖写，原子 rename）

### 1.6 原子写入（架构约束）

```python
# boot_context.py 写入逻辑（Architect §1 D-006）
import os

TMP = f"{workspace_root}/.hermes.md.tmp"
TARGET = f"{workspace_root}/.hermes.md"

with open(TMP, "w") as f:
    f.write(static_content + "\n\n---\n\n" + dynamic_content)
os.rename(TMP, TARGET)  # POSIX 原子 rename
```

`os.rename` 在 Linux 上是原子的——agent 启动时读取 `.hermes.md`，要么读到旧版本（完整），要么读到新版本（完整），不存在半截文件。

### 1.7 Cron 配置

```
cronjob:
  name: "pipeline-boot-context"
  schedule: "every 5m"
  workdir: /workspace/devPPL
  script: /workspace/devPPL/scripts/boot_context.py
```

每个项目各配一个 boot_context cron，通过 `workdir` 区分。`boot_context.py` 从工作目录推导 project root。

### 1.8 boot_context.py 文件清单

| 文件 | 作用 | 预估行数 |
|------|------|:------:|
| `pipeline/boot_context.py` | 核心逻辑：读数据源 → 拼接动态段 → 原子写入 .hermes.md | ~100 |
| `config/hermes_static.md` | 静态模板（从原 .hermes.md 复制） | ~30 |
| Cron job | Hermes cron 配置（见 §1.7） | — |

---

## 2. Dashboard：红绿灯可视化（dashboard.py）

### 2.1 问题

当前管线状态只能通过 SQLite CLI 直接查 `pipeline_state.db` 来了解：

```bash
sqlite3 pipeline_state.db "SELECT task_id, step_name, status FROM pipeline_steps WHERE status != 'done'"
```

Frank 和 OC 需要一个直观的"一眼看到"的命令。

### 2.2 方案：CLI 红绿灯面板

```bash
$ python3 pipeline/dashboard.py
```

输出：

```
┌────────────────────────────────────────────────────────────────────┐
│  devPPL 管线面板 · 2026-07-30T22:15:00Z · system_mechanism       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  任务              进度                                        状态 │
│  ───────────────────────────────────────────────────────────────── │
│  t_3831c640  dev     ██ qa-d1 ██ qa-exec qa-d2  va  merge close  🟡 │
│  t_721e24b0  dev ██ qa-d1 ██ qa-exec ██ qa-d2  va  merge  close  🔴 │
│  t_5a3f9c12  dev ██ qa-d1 ██ qa-exec ██ qa-d2 ██ va ██ merge ██ close 🟢 │
│                                                                    │
│  状态: 🟢 1 · 🟡 1 · 🔴 1 · ⬜ 0                                  │
│  🔴 详情: t_721e24b0 → va blocked [VA 无法判定：信息不足]          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 2.3 绘制规则

| 符号 | 含义 | 判定条件 |
|:----:|------|---------|
| ██ | 已完成 | step.status = 'done' AND verdict IN ('pass','VERIFIED','conditional_pass') |
| 🟢 | 步骤通过 | 等同于 ██ 完成 |
| 🟡 | 进行中 | step.status = 'running' 或 'pending'（但未超时） |
| 🔴 | 阻塞/失败 | step.status IN ('failed','blocked') 或 verdict IN ('FALSIFIED','fail') 或 超时 |
| ⬜ | 未开始 | step.status = 'pending' 且非当前步骤 |

### 2.4 数据源

dashboard.py 只读两个数据源：

```
pipeline_state.db  → pipeline_steps 表（step_name, status, verdict, started_at, error_msg）
kanban.db          → tasks 表（title, priority, assignee）
```

不需要额外 API。两个 SQLite DB 即可生成完整面板。

### 2.5 查询逻辑

```python
# pipeline/dashboard.py 核心查询
def get_pipeline_view(db_path: str, kanban_db: str):
    conn = sqlite3.connect(db_path)
    rows = conn.execute("""
        SELECT task_id, step_name, status, verdict,
               error_msg, started_at, finished_at, assigned_agent
        FROM pipeline_steps
        WHERE status != 'done' OR verdict = 'FALSIFIED'
        ORDER BY task_id, step_name
    """).fetchall()

    kanban = sqlite3.connect(kanban_db)
    tasks = kanban.execute("""
        SELECT id, title, priority, assignee
        FROM tasks WHERE status NOT IN ('done','failed','cancelled')
    """).fetchall()

    return assemble_dashboard(rows, tasks)
```

### 2.6 命令行参数

```
python3 pipeline/dashboard.py [options]

选项：
  --task TASK_ID    只显示指定任务
  --json            机器可读 JSON 输出（供 watchdog 或其他工具消费）
  --full            显示所有任务（包括已完成的）
  --db PATH         pipeline_state.db 路径（默认 ./pipeline_state.db）
```

`--json` 模式输出示例：

```json
{
  "project": "devPPL",
  "project_type": "system_mechanism",
  "timestamp": "2026-07-30T22:15:00Z",
  "summary": {"green": 1, "yellow": 1, "red": 1, "gray": 0},
  "tasks": [
    {
      "task_id": "t_3831c640",
      "current_step": "dev",
      "status": "running",
      "verdict": null,
      "steps": {"dev": "running", "qa-d1": "pending", "qa-exec": "pending",
                "qa-d2": "pending", "va": "pending", "merge": "pending", "close": "pending"}
    }
  ]
}
```

### 2.7 文件清单

| 文件 | 作用 | 预估行数 |
|------|------|:------:|
| `pipeline/dashboard.py` | 红绿灯面板 CLI | ~80 |

---

## 3. 备份策略：三类项目自动判定 + 三重备份执行

### 3.1 背景

R5 D-011/D-012/D-013 已裁定备份策略。当前实现：

- `project_config` 表已建（含 `project_type`, `backup_script`, `notify_script`）
- `init_project.py` 已提供项目类型初始化
- autopilot.sh 的 merge 步骤：只做 `git merge`，**未执行备份**
- state.py 的 `_close_backup()` 是 **空 stub**

**用户影响**：merge 和 close 步骤缺少数据安全保障。如果 merge 出问题或 close 时数据丢失，无法恢复。

### 3.2 三类项目备份策略

| 类型 | 示例 | 备份方式 | 实现 |
|------|------|---------|------|
| **system_mechanism** | devPPL | SandboxHermesBackup（`hermes_backup_push.sh`） | `bash /workspace/hermes_backup_push.sh` |
| **pure_product** | Threes | git commit + push | `git add . && git commit -m 'backup: ...' && git push` |
| **hybrid** | InfoManager | 双重（git push + SandboxHermesBackup） | 先 git push，再 hermes_backup_push.sh |

### 3.3 三重备份点

```
管线流转:
               merge 前              merge 后            close 中
                  │                    │                   │
    [merge-1]     ▼     [merge-4]      ▼     [close-4]    ▼
    合并前备份         合并后备份            闭环备份
    (pre_merge)       (post_merge)          (close_backup)
```

| 备份点 | 触发时机 | 失败处理 | 重试次数 |
|--------|---------|---------|:------:|
| merge-1（合并前） | merge 步骤启动时 | retry → block | 1 |
| merge-4（合并后） | VA 合并验证通过后 | retry → block | 2 |
| close-4（闭环） | close 流程中 | retry → block | 3 |

### 3.4 备份脚本的实现

在 autopilot.sh 中新增统一的备份执行函数：

```bash
# scripts/autopilot.sh 新增函数
execute_backup() {
    local BACKUP_POINT="$1"    # pre_merge | post_merge | close_backup
    local PROJECT_TYPE="$2"

    case "$PROJECT_TYPE" in
        system_mechanism)
            bash /workspace/hermes_backup_push.sh
            ;;
        pure_product)
            git add . && git commit -m "backup: $BACKUP_POINT $(date -u '+%Y-%m-%dT%H:%M:%SZ')" && git push
            ;;
        hybrid)
            git add . && git commit -m "backup: $BACKUP_POINT $(date -u '+%Y-%m-%dT%H:%M:%SZ')" && git push
            bash /workspace/hermes_backup_push.sh
            ;;
        *)
            echo "[backup] 未知项目类型: $PROJECT_TYPE，跳过备份" >&2
            return 1
            ;;
    esac
}
```

### 3.5 嵌入 autopilot.sh 的位置

在 autopilot.sh 的 merge case 中：

```bash
merge)
    cd "$REPO_ROOT"
    PROJECT_TYPE=$(python3 -c "
import sys; sys.path.insert(0, '$REPO_ROOT')
from pipeline.config import get_config_item
print(get_config_item('project_type', '$REPO_ROOT/pipeline_state.db') or 'system_mechanism')
" 2>/dev/null)

    # merge-1: 合并前备份
    if ! execute_backup "pre_merge" "$PROJECT_TYPE"; then
        echo "合并前备份失败 → retry 或 block"
        # state.py branches 的 pre_merge_backup_fail 分支处理
    fi

    # merge-2: git merge
    # ... 现有代码 ...

    # merge-3: VA 合并验证
    # ...

    # merge-4: 合并后备份
    if ! execute_backup "post_merge" "$PROJECT_TYPE"; then
        echo "合并后备份失败 → retry 或 block"
    fi
```

### 3.6 state.py 的 `_close_backup` 补完

将当前空 stub 替换为实际实现：

```python
def _close_backup(task_id: str, db_path: str = "pipeline_state.db") -> bool:
    """close-4: 备份推送。按项目类型选择备份命令。"""
    project_type = get_config_item("project_type", db_path) or "system_mechanism"

    strategies = {
        "system_mechanism": ["bash", "/workspace/hermes_backup_push.sh"],
        "pure_product": ["git", "add", ".", "&&", "git", "commit", "-m",
                         f"backup: close {task_id}", "&&", "git", "push"],
        "hybrid": [
            ["git", "add", ".", "&&", "git", "commit", "-m", f"backup: close {task_id}", "&&", "git", "push"],
            ["bash", "/workspace/hermes_backup_push.sh"],
        ],
    }

    commands = strategies.get(project_type, strategies["system_mechanism"])
    # ... 执行命令并返回 success/failure
```

### 3.7 文件清单

| 修改 | 作用 | 改动量 |
|------|------|:------:|
| `scripts/autopilot.sh` | merge case 中新增 backup 调用 | +30 行 |
| `pipeline/state.py` | `_close_backup()` 补完（从 stub → 实际实现） | +40 行 |

---

## 4. S6 闭环：close.sh 7 子步骤完整展开

### 4.1 背景

当前 autopilot.sh 的 close case 调用了 `close_pipeline_step()`，其中 close-2（GAI 更新）、close-3（manifest 更新）、close-4（备份推送）的 state.py stub 全是 `pass`。close-5（飞书通知）未实现。close-6（归档）未实现。

**用户影响**：close 步骤虽然 `status='done'` 写入了，但 GAI 未更新、manifest 未更新、备份未执行——铁律 2 的 S6 闭环实际上没闭环。

### 4.2 close 7 子步骤完整规范

```
[close-0] S6 检测                      ✅ 已实现（autopilot.sh L106-127）
[close-1] 关闭 kanban 任务              ✅ 已实现（autopilot.sh L130-134）
[close-2] 更新 GAI                      ❌ stub — 本 PRD 补完
[close-3] 更新 manifest                 ❌ stub — 本 PRD 补完
[close-4] 备份推送                      ❌ stub — 见 §3.6
[close-5] 飞书通知                      ❌ 未实现 — 本 PRD 补完
[close-6] 归档 + 清理                   ❌ 未实现 — 本 PRD 补完
```

### 4.3 close-2：更新 GAI

```
谁执行: autopilot（通过 state.py _close_gai_update）
内容: 将 GLOBAL_ACTION_ITEMS.md 中对应 P0-XX 条目从"待办"→"✅ done"
判定: 从 kanban task 标题中提取 P0-XX 编号 → 在 GAI 中 grep 定位 → sed 替换状态
IF GAI 文件不存在 → block，通知 OC
IF 无法匹配 P0-XX 编号 → 记录 warning，不阻塞（非所有任务都对应 GAI）
```

实现：

```python
def _close_gai_update(task_id: str, db_path: str = "pipeline_state.db") -> bool:
    """close-2: 更新 GLOBAL_ACTION_ITEMS.md。"""
    gai_path = "GLOBAL_ACTION_ITEMS.md"
    if not Path(gai_path).exists():
        return False

    # 从 kanban task 标题提取 P0-XX 编号
    # 例：t_3831c640 的标题可能是 "P0-19: 管线脚本化"
    p0_match = _extract_p0_from_task(task_id)
    if not p0_match:
        return True  # 非 GAI 任务，跳过（成功）

    # sed 替换状态
    # 匹配行：| P0-XX | ... | 待办 | ...
    # 替换为：| P0-XX | ... | ✅ done | ...
    subprocess.run(
        ["sed", "-i",
         f"s/\\(| {p0_match} .*\\)| 待办 |/\\1| ✅ done |/",
         gai_path],
        check=True,
    )
    return True
```

### 4.4 close-3：更新 manifest

```
谁执行: autopilot（通过 state.py _close_manifest_update）
内容: 检查本次改动的新增文件是否在 config/manifest.yaml 中注册
如果不存在 config/manifest.yaml → 创建并扫描新增文件
如果存在 → diff HEAD~1 获取新增文件列表 → 检查是否已在 manifest → 未注册的自动追加
```

实现：

```python
def _close_manifest_update(task_id: str) -> bool:
    """close-3: 更新 manifest。"""
    manifest_path = Path("config/manifest.yaml")
    if not manifest_path.exists():
        # 首次：扫描 git 追踪的文件生成初始 manifest
        _generate_initial_manifest(manifest_path)
        return True

    # 获取 merge 引入的新增文件
    result = subprocess.run(
        ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
        capture_output=True, text=True,
    )
    new_files = result.stdout.strip().split("\n") if result.stdout.strip() else []

    if not new_files:
        return True  # 无新增文件

    # 读取现有 manifest
    import yaml
    with open(manifest_path) as f:
        manifest = yaml.safe_load(f) or {"files": []}

    registered = set(manifest.get("files", []))
    for f in new_files:
        if f not in registered:
            manifest.setdefault("files", []).append(f)

    # 追加 GAI 关联
    p0_match = _extract_p0_from_task(task_id)
    if p0_match:
        manifest[f"p0_{p0_match.replace('-','_')}"] = {
            "task_id": task_id,
            "files": new_files,
            "closed_at": datetime.now(timezone.utc).isoformat(),
        }

    with open(manifest_path, "w") as f:
        yaml.dump(manifest, f, default_flow_style=False, allow_unicode=True)
    return True
```

### 4.5 close-5：飞书通知

```
谁执行: autopilot
内容: 发送飞书通知 "✅ P0-XX 闭环完成。7 步全部 pass。备份已推送。"
格式: markdown 消息，含 7 步摘要表 + 耗时
IF 通知失败 → 记录 warning（不阻塞 close 完成）
```

实现：通过 `hermes_backup_notify.sh` 或 webhook 发送。具体 webhook URL 从 `project_config` 表读取（如果配置了 `notify_script`）。

### 4.6 close-6：归档 + 清理

```
谁执行: autopilot
内容:
  a. 如果 openspec CLI 可用 → openspec archive {task_id}
  b. git worktree remove（如果任务使用了 worktree）
  c. pipeline_state.db: step=close, verdict='pass', status='done'
IF 归档失败 → 记录 warning（不阻塞）
```

### 4.7 close.sh 的角色裁定（DPL-012 R5）

**Product/Architect/Engineer 三方共识**：

- `close.sh`（位于 `/root/.hermes/profiles/orchestrator/scripts/close.sh`）的角色是 **验证脚本**，不是执行脚本
- autopilot 在 close-6 之后调用 `close.sh` 做最终验证（B 方案）
- 如果 close.sh 检测到遗漏（如 GAI 未更新）→ 报错 → autopilot 按分支合约 retry

### 4.8 文件清单

| 修改 | 作用 | 改动量 |
|------|------|:------:|
| `pipeline/state.py` | `_close_gai_update()` 从 stub → 实际实现 | +30 行 |
| `pipeline/state.py` | `_close_manifest_update()` 从 stub → 实际实现 | +40 行 |
| `pipeline/state.py` | `_close_backup()` 从 stub → 实际实现（见 §3.6） | +40 行 |
| `pipeline/state.py` | `_close_notify()` 从 stub → 飞书通知实际实现 | +25 行 |
| `pipeline/state.py` | `_close_archive()` 从 stub → openspec + worktree 清理 | +20 行 |
| `scripts/autopilot.sh` | close case 中的 backup 调用（见 §3） | 复用 |

---

## 5. Autopilot 修复

### 5.1 修复 1：任务发现盲区（t_6d3046d0）

**问题**：`discover.py` 的 `discover_new_tasks()` 过滤条件中包含 `assignee IN PIPELINE_ASSIGNEES`（只有 game-engine/game-qa/verifier）。但有些 kanban task 的 assignee 是 **game-director 或 autopilot 自身**——这些任务会被扫描遗漏。

**修复**：扩展 `PIPELINE_ASSIGNEES` 集合，增加管线相关的 profile：

```python
# pipeline/discover.py — 修复
PIPELINE_ASSIGNEES = frozenset({
    "game-engine",
    "game-qa",
    "verifier",
    # Slice 3 新增：这些 profile 的任务也可能需要管线追踪
    "game-director",   # Product D1/D2 评审任务
    "game-architect",  # Architect 评审任务
    "autopilot",       # autopilot 自己创建的 merge/close 任务
})
```

同时，当前 `_is_sub_task()` 的标题前缀列表需要补全（已有 `dev: `, `qa-d1: `, `dev [ROLLBACK]: ` 等，需要增加 close 相关的标题模式）。

### 5.2 修复 2：cron 上下文 `hermes kanban show` 失效

**问题**：autopilot cron job 运行在 cron 环境中，没有 Hermes CLI 的完整上下文（`$HERMES_KANBAN_DB` 等环境变量可能缺失），`hermes kanban show` 返回空结果。

**修复**：在 autopilot.sh 开头显式导出所需环境变量：

```bash
# autopilot.sh 开头新增
export HERMES_KANBAN_DB="${HERMES_KANBAN_DB:-$HOME/.hermes/kanban.db}"
export HERMES_PROFILE="${HERMES_PROFILE:-game-director}"

# 验证 kanban.db 存在
if [ ! -f "$HERMES_KANBAN_DB" ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [autopilot] 错误: kanban.db 不存在 ($HERMES_KANBAN_DB)" >&2
    exit 1
fi
```

同时，`state.py` 的 `get_kanban_task_state()` 函数需要增加直接读 SQLite 的 fallback（当 `hermes kanban show` 失败时）：

```python
def get_kanban_task_state(task_id: str) -> Optional[dict]:
    """通过 hermes CLI 读取 kanban 任务状态。fallback 到直接读 SQLite。"""
    # 优先用 CLI（能拿到完整的结构化数据）
    result = _read_via_cli(task_id)
    if result:
        return result

    # CLI 失败 → fallback 到直接读 SQLite
    return _read_via_sqlite(task_id)
```

### 5.3 文件清单

| 修改 | 作用 | 改动量 |
|------|------|:------:|
| `pipeline/discover.py` | 扩展 `PIPELINE_ASSIGNEES` + 标题前缀 | ~5 行 |
| `scripts/autopilot.sh` | 显式 export 环境变量 + kanban.db 存在性检查 | +10 行 |
| `pipeline/state.py` | `get_kanban_task_state()` 增加 SQLite fallback | +20 行 |

---

## 6. Watchdog 共存：三 cron 零冲突

### 6.1 问题

Slice 3 部署后会有三个 cron job 同时运行：

```
autopilot:     每 2min  → 写 pipeline_state.db + 心跳文件，读 kanban.db
watchdog:      每 30min → 读心跳文件 + kanban.db + session DB（只读）
boot_context:  每 5min  → 读 session DB + pipeline_state.db + memory → 写 .hermes.md
```

需要确保三者之间不会互相踩踏。

### 6.2 冲突分析（已有代码基础）

当前 autopilot.sh 已使用 `flock` 文件锁防止自身并发：

```bash
LOCKFILE="/tmp/autopilot.lock"
exec 200>"$LOCKFILE"
flock -n 200 || exit 0
```

**写冲突矩阵**（Architect §5.3 已证明无冲突）：

| 数据源 | autopilot | watchdog | boot_context | 冲突？ |
|--------|:---------:|:--------:|:------------:|:------:|
| pipeline_state.db | **W** | — | R | ❌ SQLite WAL 单写+多读 |
| kanban.db | R | R | R | ❌ 全读 |
| .hermes.md | R | — | **W**（原子） | ❌ 唯一写者 |
| session DB | — | R | R | ❌ 全读 |
| 心跳文件 | **W** | R | — | ❌ 唯一写者 |
| memory | — | — | R | ❌ 唯一读者 |

### 6.3 心跳文件机制

autopilot 每个 cron tick 写心跳文件：

```bash
# autopilot.sh 主循环结束时
echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" > /tmp/pipeline-autopilot.heartbeat
```

watchdog cron 检查心跳文件 mtime：

```python
# watchdog 检查逻辑
import os, time

HEARTBEAT = "/tmp/pipeline-autopilot.heartbeat"
MAX_AGE = 4 * 60  # 4 分钟（2× cron interval）

if os.path.exists(HEARTBEAT):
    age = time.time() - os.path.getmtime(HEARTBEAT)
    if age > MAX_AGE:
        send_alert("⚠️ autopilot 心跳超时！可能已停止工作")
```

### 6.4 boot_context 读 pipeline_state.db 的时效性

```
时间线:
  T=0   autopilot 写 pipeline_state.db (新的 dev done)
  T=1   autopilot 完成（释放 SQLite 写锁）
  T=2   boot_context 读 pipeline_state.db (WAL 读事务)
        → 可能看到 T=0 写之前的快照（SQLite WAL snapshot isolation）
  T=7   boot_context 再次运行（5min 后）
        → 一定看到 T=0 的更新
```

**产品判断**：5 分钟内的轻微延迟可接受。agent 的派发间隔 > 5min，boot_context 第二次运行时一定能拿到最新状态。不做额外同步。

### 6.5 验证：三 cron 不互相阻塞

```
最坏情况并发（每 30min 一次，LCM = 30min）:
  T=30 → autopilot（flock 锁自己）
  T=30 → boot_context（只读 pipeline_state.db → WAL 不阻塞 autopilot 的写）
  T=30 → watchdog（只读心跳文件 + other DBs → 零锁竞争）

结论: 三者互不阻塞。SQLite WAL 确保 reader 不阻塞 writer，writer 不阻塞 reader。
```

### 6.6 文件清单

| 文件 | 作用 | 状态 |
|------|------|:----:|
| `scripts/autopilot.sh` | flock 防重入 + 写心跳文件 | ✅ 已有 |
| watchdog cron | 读心跳文件 → 超时告警 | ✅ 已有（需验证配置） |
| boot_context cron | 读 pipeline_state.db → 写 .hermes.md | 新增（§1.7） |

---

## 7. 验收标准

### 7.1 功能验收

| # | 验收项 | 验证方式 | 通过标准 |
|---|--------|---------|---------|
| AC-1 | **boot_context 每 5min 更新** | 等待 5min → 查看 `.hermes.md` mtime | mtime 在 5min 内更新，动态段 ≤ 2000 字符 |
| AC-2 | **动态段含活跃任务** | `.hermes.md` 中检查动态段内容 | 包含 `## 活跃管线任务` 表格，数据与 pipeline_state.db 一致 |
| AC-3 | **动态段含最近决策** | 同上 | 包含 `## 最近决策`，至少 1 条（如果存在） |
| AC-4 | **动态段含最近纠正** | 同上 | 包含 `## 最近纠正` |
| AC-5 | **原子写入** | 在 boot_context 运行时 `cat .hermes.md` | 读到的始终是完整文件（无截断） |
| AC-6 | **dashboard 红绿灯面板** | `python3 pipeline/dashboard.py` | 显示 🟢🟡🔴⬜ 符号 + 任务进度条 |
| AC-7 | **dashboard --json** | `python3 pipeline/dashboard.py --json` | 输出合法 JSON，含 summary + tasks 数组 |
| AC-8 | **dashboard --task** | `python3 pipeline/dashboard.py --task t_xxx` | 只显示指定任务 |
| AC-9 | **合并前备份** | 观察 autopilot 日志 merge case | "合并前备份" 日志出现 + `hermes_backup_push.sh` 被调用 |
| AC-10 | **合并后备份** | 同上 | "合并后备份" 日志出现 |
| AC-11 | **close-4 备份** | 观察 close 流程日志 | `_close_backup()` 实际执行（非 stub） |
| AC-12 | **close-2 GAI 更新** | 检查 GLOBAL_ACTION_ITEMS.md | P0-XX 状态从"待办"→"✅ done" |
| AC-13 | **close-3 manifest 更新** | 检查 config/manifest.yaml | 新增文件出现在 manifest 中 |
| AC-14 | **close-5 通知** | 检查飞书 | 收到 "✅ P0-XX 闭环完成" 通知 |
| AC-15 | **close-6 归档** | 检查 openspec archive | task 被归档（如 openspec CLI 可用） |
| AC-16 | **任务发现盲区修复** | 创建 assignee=game-director 的 kanban task | autopilot 发现并注册到 pipeline_state.db |
| AC-17 | **cron 上下文修复** | cron 环境中执行 autopilot | `hermes kanban show` 不返回空 |
| AC-18 | **三 cron 不冲突** | 同时运行 autopilot+watchdog+boot_context | pipeline_state.db 无 SQLITE_BUSY 错误，.hermes.md 无截断 |

### 7.2 非功能验收

| # | 验收项 | 标准 |
|---|--------|------|
| AC-19 | **向后兼容** | Slice 1/2 的 pipeline_state.db schema 不变，已有数据不受影响 |
| AC-20 | **dashboard 性能** | 100 个任务的 panel 渲染 < 1 秒 |
| AC-21 | **boot_context 时效** | .hermes.md 的 mtime 与当前时间的差值 < 6min（5min cron + 1min 执行容忍） |
| AC-22 | **备份脚本幂等** | 多次执行 `hermes_backup_push.sh` 不产生重复备份 |
| AC-23 | **无静默失败** | 备份失败/GAI 更新失败/通知失败 → autopilot 日志 + kanban comment 记录 |

### 7.3 测试场景

| 场景 | 操作 | 预期结果 |
|------|------|---------|
| 正常 boot_context 运行 | 等待 5min | .hermes.md 动态段更新 |
| boot_context 首次运行（无 session 数据） | 部署后首次 cron tick | 动态段显示"无最近决策"（不崩溃） |
| dashboard 显示混合状态 | 不同 task 处于 dev/va/close | 🟢🟡🔴⬜ 正确映射 |
| 备份失败 → retry | 备份脚本 exit ≠ 0 | autopilot retry → 达到上限 → block |
| GAI 文件丢失 | close-2 时 GAI 不存在 | block + kanban comment |
| 三 cron 同时 tick | LCM=30min 的并发点 | 无 SQLITE_BUSY，无数据不一致 |
| autopilot 心跳超时 | 手动停 autopilot cron 5min | watchdog 检测到 + 飞书告警 |
| discover 发现新 task | 手动创建 assignee=game-director 的 kanban task | autopilot 注册并启动管线 |

---

## 8. 不做的事（Slice 3 之后）

| 项目 | 为什么不在 Slice 3 做 | 影响 |
|------|----------------------|------|
| **dashboard web UI** | CLI 面板满足 Frank "一眼看到"的需求，web UI 是锦上添花 | 不影响 |
| **boot_context 从 memory 提取"最近纠正"的 NLP** | 需要 NLP 从句子里提取 Product 反例——Sl 3 用简单关键词匹配（"纠正"、"驳回"）即可 | 可能漏掉部分纠正，但不影响核心功能 |
| **备份压缩 + 去重** | 当前 `hermes_backup_push.sh` 已处理增量同步。压缩/去重是备份系统的优化 | 不影响 |
| **manifest 完整性审计** | 当前 manifest 检查新增文件，不检查已登记文件是否仍存在。完整性审计是 Slice 3+ 的特性 | 不影响 |
| **飞书通知富文本（嵌入 dashboard 截图）** | markdown 通知足够，富文本需要额外渲染 | 不影响 |
| **A/B/C 类 roundtable 完整自动化** | OC 在阶段 -1 手动判定类型，不需要 autopilot 在管线中创建 A/B/C 类 roundtable | Slice 2 的 gate_roundtable(D) 已覆盖管线内的 roundtable 需求 |

---

## 9. 总结

Slice 3 是收尾层——它不改变管线的流转逻辑，而是把管线从"能跑"升级为"可运维"：

1. **DPL-011**（跨会话记忆）：boot_context cron 每 5 分钟把管线状态、最近决策、最近纠正写入 `.hermes.md`，agent 每次启动时都能看到——不再反复犯同样的错
2. **Dashboard**：一行 `python3 pipeline/dashboard.py` 就让 Frank 看到红绿灯——哪些任务卡住了，哪步红了，不用查 SQLite
3. **备份策略**：三个备份点（merge 前、merge 后、close 中）按项目类型自动选备份命令——数据安全终于不是在 stub 里的承诺
4. **S6 闭环**：close-2 到 close-6 的 stub 全部补完——GAI 更新、manifest 注册、备份推送、飞书通知、归档清理——铁律 2 的 6 步闭环一个都不缺
5. **两个修复**：任务发现盲区 + cron 上下文失效——autopilot 不会再漏任务

**与 Slice 1/2 的增量**：

| 组件 | Slice 2 → Slice 3 |
|------|:---------------:|
| `pipeline/boot_context.py` | 0 → ~100 行（新增） |
| `pipeline/dashboard.py` | 0 → ~80 行（新增） |
| `config/hermes_static.md` | 0 → ~30 行（新增，从 .hermes.md 复制） |
| `pipeline/state.py` | stub 函数 → 实际实现（+155 行） |
| `scripts/autopilot.sh` | merge case 新增备份调用 + cron 环境变量（+40 行） |
| `pipeline/discover.py` | 扩展 PIPELINE_ASSIGNEES（+5 行） |
| `config/manifest.yaml` | 0 → 自动生成（close-3 时创建） |

**总增量**：约 410 行新代码 + 2 个新文件 + 1 个 cron job（boot_context）。

