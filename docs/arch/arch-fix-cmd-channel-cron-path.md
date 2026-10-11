# FIX cmd_channel cron PATH 缺陷 — 架构设计（失败可观测 + 分层防御 + 指令不静默丢失）

> 发言人：高见远（架构师） | 日期：2026-08-13 | 版本：v1.0
> 输入：PRD v1.0（docs/prd/fix-cmd-channel-cron-path-prd.md，commit 0ade9cc）+ **OC 补充发现（t_e4a9dbe4 卡 comment 2026-08-13 17:02，PRD 交付后）** + 现状代码核查（cmd_chain.py / discover.py / state.py / autopilot.sh / cmd_channel.sh / lib_kanban_dedup.sh / dedup|stuck|workspace|chain_check.sh / test_cmd_channel.sh）
> 定位：6 步闭环 Step 2 架构落地 —— 把 PRD F-1..F-9 细化为文件/函数/数据流级实现方案，工程师可直接照写代码
> 核心原则：**本设计对 PRD 做一处关键修正（根因重判）+ 一处增强（失败可观测升级为主修复）**。PRD 的 P0 措施（PATH 自举 + Python 绝对路径）全部保留，但从「根因修复」降级为「纵深防御」；真正的主修复是「失败必须可观测、原因必须可分类、指令必须不静默丢失」。

---

## 0. 范围与裁决总表

### 0.1 本设计做什么（PRD F-1..F-9 全覆盖 + OC 补充发现并入）

| # | PRD 需求 | 本设计章节 | 状态 |
|---|---------|-----------|------|
| 1 | F-1 共享 PATH 引导片段 scripts/lib_hermes_path.sh | §3 | ✅ 保留（降级为纵深防御，A1） |
| 2 | F-2 autopilot.sh 挂载 | §3.3 | ✅ 保留 |
| 3 | F-3 cmd_channel.sh 独立自举 | §3.4 | ✅ 保留 |
| 4 | F-4 pipeline/hermes_cli.py::hermes_bin() | §4 | ✅ 保留 + 扩展（hermes_invoke） |
| 5 | F-5 五处调用点统一替换 | §4.4 | ✅ 保留 |
| 6 | F-6 失败原因区分 | §5 | ⬆️ **升级为主修复**（A2/A4/A5） |
| 7 | F-7 测试（PRD 编号 T13-T16） | §6 | 🔄 **重排为 T36-T39**（存量 T13-T35 冲突，A6） |
| 8 | F-8 建卡失败回滚重试（P1） | §7.1 | ✅ 保留，D1 gated |
| 9 | F-9 回执直连 sqlite（P1） | §7.2 | ✅ 保留，D1 gated |
| 10 | OC 补充：失败回执必须带 stderr | §5.3 / §6 | ✅ **新增强制项**（A5） |
| 11 | OC 补充：同 tick 消费 2 张必须都成功 | §6 AC-10 | ✅ **新增强制验收**（A7） |

### 0.2 架构裁决总表（本设计的核心决策）

| 决策点 | 裁决 | 说明 |
|--------|------|------|
| **A1 根因修正** | ⚠️ **PRD 根因「cron 最小 PATH 下 hermes 不可达」与实际环境不符**。实测：`/usr/local/bin/hermes` 存在（110B wrapper → exec venv 绝对路径），cron daemon 环境 PATH 含 `/usr/local/bin`，`/usr/bin/env bash` 在最小 PATH 也可用；OC 手动复现（精确 cron PATH + 长标题 + 同 tick 两张）**全部成功** | PRD 复现用的 `env -i PATH=/usr/bin:/bin` 是人工构造环境，**不等于真实 cron**。真实缺陷是**间歇性**的（16:48 失败 / 16:54 成功 / 16:56 失败 / 17:00 失败，规律=同 tick 两张必挂、单张成功）。PATH 自举保留但只是防御，不解决主诉 |
| **A2 主修复重定位** | **失败可观测 + 失败分类 = 主修复**；PATH 自举 = 纵深防御 | OC 明确：「失败回执必须带 stderr（cmd_channel.sh `2>/dev/null` 吞错误，是排查最大障碍）」。当前所有 hermes 调用失败时 stderr 被吞（Python `capture_output` 不落日志、shell `2>/dev/null`/`>/dev/null 2>&1`），间歇根因无法定位。先让失败可观测，才能修根因 |
| **A3 hermes_bin() 解析** | `HERMES_BIN` env（存在且可执行）→ `shutil.which` → 回退目录列表 → 裸 `"hermes"`；`functools.lru_cache` 缓存 + 测试 reset 钩子 | 与 PRD §2.3 定义一致；缓存避免每调用开销（PRD F-5），reset 钩子供单测（T38）切换场景 |
| **A4 失败分类三态** | `not_found`（hermes 不可达，env 类，P1 可重试）/ `timeout`（超时，env 类，P1 可重试）/ `nonzero_or_parse`（业务类，重试必败，归档+回执） | PRD F-6 只分「hermes 不可用」vs「业务失败」；本设计细分 timeout 为 env 类——间歇失败中超时是首要嫌疑（同 tick 两张时 hermes CLI 串行两次、gateway/token 冷启动） |
| **A5 可观测红线** | 任何 hermes 调用失败必须：stderr 前 500 字写入 autopilot.log + 回执 comment 带 stderr 摘要。cmd_channel.sh 全部 `2>/dev/null` 改为捕获式 | OC 硬性要求。这是间歇根因能定位的前提 |
| **A6 测试编号重排** | 新增用例编 **T36-T39（P0）/ T40-T41（P1）**，不沿用 PRD 草案 T13-T16 | 存量 test_cmd_channel.sh 已有 T1-T35（T13/T14 已被 cmd_chain 补全占用），PRD 编号冲突 |
| **A7 OC 强制验收 AC-10** | 同 tick 消费 2 张 `[CMD] create dev` 必须都建链成功 | OC 补充发现的直接验收（16:48/16:56/17:00 三次都死在这） |
| **A8 回执直连 sqlite** | 复用 cmd_channel.sh 既有直连模式（CAS/STALE 查询），`INSERT INTO task_comments` | PRD F-9；不引入新依赖 |
| **A9 双驱动 cron 异常** | ⚠️ **运维发现（不在本 FIX 代码范围）**：autopilot.sh 被至少两个调度驱动——crontab `*/2`（:01 tick）与另一 `*/3` 调度（:25 tick，每 3 分钟，来源未见于当前 crontab）。两驱动可并发跑 cmd_channel.sh（flock 前后时序）→ 增加 hermes CLI 并发/SQLite 锁竞争概率 | 建议 OC/Frank 排查 :25 驱动来源并收敛为单一调度（§9） |
| **A10 P1 回滚状态机** | env 类失败 → 卡从 archived 回滚 ready（+ [cmd-retry] 计数 comment）→ 下 tick 重试；≥2 次 → blocked + 告警 comment。业务类 → 保持归档 + 明确回执 | PRD F-8 建议 A（混合），D1 裁定后实现 |

### 0.3 约束合规确认

| 约束 | 本设计合规点 |
|------|-------------|
| C1 fail-open | lib_hermes_path.sh 找不到 hermes 只打 stderr 告警不 exit；hermes_bin() 兜底裸名；所有异常路径返回结构化失败而非抛出到主循环 |
| C2 单次消费/CAS 不回退 | 本 FIX 不动 CAS 先归档后执行（P1 F-8 仅在 D1 裁定后加回滚语义，回滚本身也是 CAS：archived→ready 仅 rowcount==1） |
| C3 discover 排除集不回退 | 本 FIX 不改 discover 排除逻辑 |
| C4 建卡走 hermes CLI + idempotency-key | hermes_bin() 只解析路径不绕过 CLI；幂等键保持 |
| C5 候选路径非唯一硬编码 | HERMES_BIN env 优先 + 回退列表可被 env 覆盖（`HERMES_BIN_FALLBACKS`，测试用） |
| C6 测试隔离 | 新测试沿用 temp kanban.db + 隔离 flock（AUTOPILOT_LOCKFILE）+ 不触碰真实 board |

---

## 1. 现状核查与数据流全景

### 1.1 现状核查（读码 + 实测结论，非假设）

| # | 核查点 | 结论 | 证据 |
|---|--------|------|------|
| 1 | hermes CLI 实际位置 | `/usr/local/lib/hermes-agent/venv/bin/hermes`（venv bin，绝对 shebang）+ `/usr/local/bin/hermes`（110B wrapper） | `ls -la` 实测 |
| 2 | cron daemon 环境 PATH | **含 `/usr/local/bin`**（cron 启动时继承：`/usr/local/go/bin:...:/usr/local/bin:/usr/bin:...`） | `/proc/<crond>/environ` 实测 |
| 3 | cron 实际调用 hermes 可达性 | **可达**（16:54:25 单张 [CMD] create dev 建链成功 = t_e4a9dbe4） | autopilot.log 2026-08-12T16:54:25Z |
| 4 | PRD「cron 最小 PATH 不可达」复现 | 复现手段是 `env -i PATH=/usr/bin:/bin`（人工构造），**≠ 真实 cron**；真实 cron PATH 含 /usr/local/bin | PRD §1.1 vs OC 补充发现 |
| 5 | 间歇失败规律 | 16:48 两张全挂 / 16:54 单张成功 / 16:56 两张全挂 / 17:00 两张全挂 → **同 tick 两张 = 双挂，单张 = 成功** | autopilot.log 2026-08-12 16:48-17:00 |
| 6 | 失败信息现状 | 一律「失败: 建卡失败: [DEV-PRD] <标题>」——无法区分 not_found/timeout/nonzero/parse | cmd_chain.py L294 返回 `""` → L798 `errors.append` |
| 7 | stderr 吞没点（Python） | cmd_chain._hermes_create L288-295 `capture_output=True` 失败即弃；_comment L301-306 吞；_reclaim L312-318 吞；discover._create_est_card L220-228 吞；state.get_kanban_task_state L97 吞 | 读码 |
| 8 | stderr 吞没点（shell） | cmd_channel.sh L66/97/108/133/164/178/199/221/343/448 `>/dev/null 2>&1`；L119/148/159/189/210/232 `2>/dev/null`；autopilot.sh 多处 `2>/dev/null || true` | 读码 |
| 9 | Python 裸 "hermes" 字面量 | **恰好 5 处**（与 PRD 一致）：cmd_chain L276/L302/L313、discover L213、state L79 | grep |
| 10 | _hermes_create 调用点 | **5 处**（L606 子卡/L644 va-claim/L728 roundtable/L789 sequential 首棒/L1044 advance）——PRD 说 5 处替换是对函数定义替换，实际一个函数统一替换即可 | grep |
| 11 | 存量测试编号 | **T1-T35 已存在**（T13/T14 被 cmd_chain 补全占用） | test_cmd_channel.sh |
| 12 | 双驱动 cron | :01 tick（*/2）+ :25 tick（每 3 分钟，来源未见于 crontab -l）都在跑 cmd_channel | autopilot.log 时间轴 |

### 1.2 根因重判（本设计对 PRD 的关键修正）

```
PRD 判断:  cron 最小 PATH(/usr/bin:/bin) → hermes 不可达 → FileNotFoundError → 建卡失败（100% 复现）
实测证据:  /usr/local/bin/hermes 存在；cron daemon PATH 含 /usr/local/bin；
           16:54:25 真实 cron tick 下单张 [CMD] create dev 建链成功；
           OC 手动复现（精确 cron PATH + 长标题 + 同 tick 两张）全部成功；
           16:48/16:56/17:00 真实 cron tick 下两张同 tick 全挂。
结论:      PATH 不是（唯一）根因。真实缺陷 = 间歇性失败，触发条件与「同 tick 消费 2 张」强相关，
           根因未明（OC 候选：cmd_channel 完整脚本环境 / hermes CLI cron 长进程 gateway-token /
           autopilot 主流程与 cmd_channel 环境交互 / 并发锁竞争）。
```

**架构含义**：主修复不能押注「PATH 自举后必然成功」——因为 PATH 本来就通。真正能推动问题收敛的是：

1. **失败可观测**（stderr 落日志 + 回执带 stderr）——下一次失败发生时能直接看到 `TimeoutExpired` 还是 `database is locked` 还是 `gateway token expired`；
2. **失败分类 + P1 回滚重试**——env 类（timeout/not_found）自动重试，天然消化间歇性；
3. **PATH 自举 + hermes_bin() 绝对路径**——消灭「环境 PATH 恰好不含 /usr/local/bin」这台机器上的隐患（纵深防御，成本低）。

### 1.3 数据流全景（修复后）

```
┌─ cron tick ─────────────────────────────────────────────────────────────┐
│ 调度（*/2 autopilot + 待排查的 :25 驱动）                                 │
│   → bash autopilot.sh                                                    │
│       ├─ [F-2] source scripts/lib_hermes_path.sh   ← PATH 自举（纵深防御）│
│       │      command -v hermes 已可达? → 不动（幂等）                       │
│       │      否则 HERMES_BIN_DIR → venv bin → ~/.local/bin → /usr/local/bin│
│       ├─ bash cmd_channel.sh（继承已自举 PATH）                            │
│       │      └─ [F-3] 自身再 source lib_hermes_path.sh（standalone 安全）  │
│       │      └─ python3 -c build_roundtable_chain                          │
│       │            └─ [F-4] hermes_bin() → [F-5] hermes kanban create     │
│       │                  └─ [F-6] 失败 → 结构化 {kind, stderr_excerpt}     │
│       │                        → 日志 stderr 500 字 + 回执带摘要           │
│       │                        → (P1, D1 后) env 类 → 回滚 ready 重试       │
│       └─ dedup/stuck/workspace/chain_check（继承 PATH）                    │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 2. 分层防御架构总览

| 层 | 组件 | 职责 | 失败语义 |
|----|------|------|---------|
| L1 Shell PATH 自举 | scripts/lib_hermes_path.sh | cron 最小 PATH 下让 hermes 可达（幂等、fail-open） | 找不到 → stderr 告警，不 exit |
| L2 Python 路径解析 | pipeline/hermes_cli.py::hermes_bin() | 任意 Python 调用点拿到 hermes 绝对路径（env→which→回退→裸名） | 裸名兜底，行为与现状一致 |
| L3 统一调用 | pipeline/hermes_cli.py::hermes_invoke() | 包装 subprocess：捕获 stdout/stderr/rc/timeout，抛结构化异常 | HermesCLIError(kind, stderr_excerpt) |
| L4 调用点替换 | cmd_chain/discover/state | 5 处裸 "hermes" → hermes_bin()/hermes_invoke() | 失败沿调用链传播结构化原因 |
| L5 失败分类与回执 | cmd_channel.sh receipt() + 日志 | 区分 not_found/timeout/nonzero/parse；回执带 stderr 摘要；stderr 落 autopilot.log | 可观测（A5 红线） |
| L6 回滚重试（P1） | cmd_channel.sh + cmd_chain.py | env 类失败 → 卡回滚 ready → 下 tick 重试（上限 2）→ blocked + 告警 | 指令不静默丢失 |
| L7 直连 sqlite 回执（P1） | cmd_channel.sh | hermes 不可达时回执直写 kanban.db task_comments | 失败有回执不破 |

---

## 3. F-1/F-2/F-3 — Shell 层 PATH 自举（纵深防御）

### 3.1 新增 scripts/lib_hermes_path.sh（完整实现）

```bash
#!/bin/bash
# scripts/lib_hermes_path.sh — hermes CLI PATH 自举（F-1，纵深防御）
#
# 背景: cron 环境 PATH 可能不含 /usr/local/lib/hermes-agent/venv/bin（hermes 实际位置）。
#       虽然本机 cron daemon PATH 含 /usr/local/bin（wrapper 可达），但:
#         - 其它 host / 容器重建后 cron PATH 可能变化
#         - 人工构造的最小 PATH（env -i PATH=/usr/bin:/bin）下 hermes 不可达
#       本 lib 让脚本在任意环境下自举 PATH，幂等 + fail-open。
#
# 用法（source 库，勿直接执行）:
#   source "$SCRIPT_DIR/lib_hermes_path.sh"
# 环境变量:
#   HERMES_BIN_DIR  — 显式覆盖目录（找到即 export PATH="$dir:$PATH"）
#   HERMES_PATH_FALLBACKS — 冒号分隔的回退目录列表（测试可覆盖，默认内置列表）
#
# 设计约束（C1/C5）:
#   - 幂等: command -v hermes 已可达 → 立即返回，不重复改 PATH
#   - fail-open: 全部找不到 → 打 stderr 告警，不 exit（主循环继续，hermes 调用失败由 L3-L5 可观测）
#   - set -u 安全: 全部变量 ${VAR:-} 默认
#   - 本 lib 顶层不执行命令（无副作用），source 上下文 return 0 合法

# 直接执行保护（source 库被 bash xxx.sh 误跑时报错退出）
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    echo "lib_hermes_path.sh 是 source 库，请勿直接执行" >&2
    exit 1
fi

# 幂等: 已可达直接返回
if command -v hermes >/dev/null 2>&1; then
    return 0
fi

_HERMES_PATH_FALLBACKS="${HERMES_PATH_FALLBACKS:-/usr/local/lib/hermes-agent/venv/bin:${HOME:-/root}/.local/bin:/usr/local/bin}"

# HERMES_BIN_DIR 显式覆盖优先（插到最前）
if [ -n "${HERMES_BIN_DIR:-}" ]; then
    _HERMES_PATH_FALLBACKS="$HERMES_BIN_DIR:$_HERMES_PATH_FALLBACKS"
fi

_HERMES_FOUND=""
IFS=':' read -r -a _HERMES_DIRS <<< "$_HERMES_PATH_FALLBACKS"
for _dir in "${_HERMES_DIRS[@]}"; do
    [ -z "$_dir" ] && continue
    if [ -x "$_dir/hermes" ]; then
        export PATH="$_dir:$PATH"
        _HERMES_FOUND="$_dir"
        break
    fi
done
unset _HERMES_DIRS _HERMES_PATH_FALLBACKS

if [ -z "$_HERMES_FOUND" ]; then
    echo "$(date -u '+%Y-%m-%dT%H:%M:%SZ') [hermes-path] 警告: 未找到 hermes CLI（PATH=$PATH）。" \
         "可设置 HERMES_BIN_DIR 指定目录；hermes kanban 调用将失败并在日志中可见" >&2
fi
unset _HERMES_FOUND
```

### 3.2 设计要点

- **幂等**：`command -v hermes` 命中即 `return 0`——交互 shell / 测试环境 / worker 会话（venv bin 已在 PATH）零改动。
- **fail-open**：找不到不 exit（C1），后续 hermes 调用失败由 L5 可观测——不是静默。
- **`set -u` 兼容**：autopilot.sh 是 `set -euo pipefail`（L30），cmd_channel.sh 是 `set -uo pipefail`（L38）；lib 内所有变量带 `${VAR:-}` 默认。
- **source 保护**：`${BASH_SOURCE[0]} = "$0"` 判断防误直接执行（BASH_SOURCE 在 bash 3+ 可用，脚本均 bash）。

### 3.3 F-2 autopilot.sh 挂载点（最小侵入）

现状（autopilot.sh）：
```bash
L40  source "$SCRIPT_DIR/lib_kanban_dedup.sh"
L43  export HERMES_KANBAN_DB="${HERMES_KANBAN_DB:-/root/.hermes/kanban.db}"
L54  bash "$REPO_ROOT/scripts/cmd_channel.sh" "$REPO_ROOT" || true
```

改后（仅插 1 行，主循环零改动）：
```bash
L40  source "$SCRIPT_DIR/lib_kanban_dedup.sh"
L41  source "$SCRIPT_DIR/lib_hermes_path.sh"      # [F-2] PATH 自举（幂等/fail-open）
L43  export HERMES_KANBAN_DB="${HERMES_KANBAN_DB:-/root/.hermes/kanban.db}"
L54  bash "$REPO_ROOT/scripts/cmd_channel.sh" "$REPO_ROOT" || true
```

- 挂载点选在 L40 之后（lib 依赖仅 shell 内建，无前置要求）、cmd_channel.sh（L54）之前 → cmd_channel 及后续所有子脚本（dedup/stuck/workspace/chain_check，L740-770）继承已自举 PATH。
- **注意**：cmd_channel.sh 是 `bash` 子进程，继承父进程环境变量（含改后的 PATH）——一次自举覆盖整棵调用树。

### 3.4 F-3 cmd_channel.sh 独立自举

现状（cmd_channel.sh）：
```bash
L40  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L41  REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
L43  LOCKFILE="${AUTOPILOT_LOCKFILE:-/tmp/autopilot.lock}"
```

改后（SCRIPT_DIR/REPO_ROOT 解析后立即 source，覆盖 standalone 调用/测试直跑）：
```bash
L40  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
L41  REPO_ROOT="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
L42  source "$SCRIPT_DIR/lib_hermes_path.sh"      # [F-3] standalone 自举（幂等，重复 source 无害）
L43  LOCKFILE="${AUTOPILOT_LOCKFILE:-/tmp/autopilot.lock}"
```

- 幂等：即使 autopilot.sh 已 source 过（PATH 已含 hermes），`command -v hermes` 命中 → return，零开销。
- standalone 直跑 `bash scripts/cmd_channel.sh`（测试 T36/T37/AC-1/AC-2 场景）同样可达。

---

## 4. F-4/F-5 — Python 层 hermes_bin() + 统一调用（纵深防御 + 可观测地基）

### 4.1 新增 pipeline/hermes_cli.py（完整实现）

```python
"""pipeline/hermes_cli.py — hermes CLI 路径解析 + 统一调用（F-4/F-5/F-6 地基）

背景: cron 环境 PATH 可能不含 hermes；且历史调用点裸 "hermes" 失败时
      stderr 被吞（capture_output 不落日志）→ 间歇失败不可定位（OC 补充发现）。
本模块提供:
  - hermes_bin(): 解析 hermes 绝对路径（env → which → 回退列表 → 裸名兜底），lru_cache
  - hermes_invoke(): 统一 subprocess 包装，捕获 stdout/stderr/rc，抛 HermesCLIError(kind)
  - reset_hermes_bin_cache(): 测试钩子（T38 切换场景）
失败分类（A4）:
  - kind='not_found': hermes 不可达（env 类，P1 可重试）
  - kind='timeout':   subprocess.TimeoutExpired（env 类，P1 可重试）
  - kind='nonzero':   returncode != 0（业务类，重试必败；stderr 摘要保留）
  - kind='parse':     stdout 非 JSON / 缺 id（业务类；兼容旧 CLI 无 --json）
"""

import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

# 已知安装路径回退列表（C5: 非唯一硬编码，env 可覆盖，测试用）
DEFAULT_FALLBACK_DIRS: List[str] = [
    "/usr/local/lib/hermes-agent/venv/bin",
    "/opt/hermes/bin",
    str(Path.home() / ".local/bin"),
    "/usr/local/bin",
]


class HermesCLIError(Exception):
    """hermes CLI 调用失败（结构化，供调用方分类处置）。"""

    def __init__(self, kind: str, message: str, stderr_excerpt: str = ""):
        super().__init__(message)
        self.kind = kind          # not_found | timeout | nonzero | parse
        self.message = message
        self.stderr_excerpt = stderr_excerpt[:500]  # A5 红线: stderr 摘要上限 500 字

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"HermesCLIError(kind={self.kind}, msg={self.message!r}, stderr={self.stderr_excerpt!r})"


def _fallback_dirs() -> List[str]:
    """回退目录列表（env HERMES_BIN_FALLBACKS 可覆盖，冒号分隔）。"""
    raw = os.environ.get("HERMES_BIN_FALLBACKS")
    if raw:
        return [d for d in raw.split(":") if d]
    return list(DEFAULT_FALLBACK_DIRS)


def _resolve_hermes_bin() -> str:
    """解析 hermes 路径。优先级（PRD §2.3）:
    HERMES_BIN env（存在且可执行）→ shutil.which('hermes') → 回退目录列表 → 裸 'hermes'。
    """
    env_bin = os.environ.get("HERMES_BIN")
    if env_bin:
        p = Path(env_bin)
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    which = shutil.which("hermes")
    if which:
        return which
    for d in _fallback_dirs():
        p = Path(d) / "hermes"
        if p.is_file() and os.access(p, os.X_OK):
            return str(p)
    return "hermes"  # 最后兜底: 行为与现状一致（子进程会抛 FileNotFoundError → 归 not_found）


@lru_cache(maxsize=1)
def hermes_bin() -> str:
    """返回 hermes 绝对路径（缓存一次；reset_hermes_bin_cache() 清空供测试）。"""
    return _resolve_hermes_bin()


def reset_hermes_bin_cache() -> None:
    """清空 hermes_bin 缓存（测试钩子）。"""
    hermes_bin.cache_clear()


def hermes_unavailable_reason() -> str:
    """hermes 不可达的可读原因（F-6/回执文案）。"""
    return (
        "hermes CLI 不可用（PATH 缺 hermes-agent venv/bin；"
        "可设置 HERMES_BIN 指定可执行文件或 HERMES_BIN_DIR/HERMES_BIN_FALLBACKS 指定目录）"
    )


def _is_hermes_available() -> bool:
    """hermes_bin() 解析结果是否真实可用（非裸名兜底）。"""
    return hermes_bin() != "hermes" or shutil.which("hermes") is not None


def hermes_invoke(
    args: List[str],
    timeout: int = 30,
    *,
    expect_json: bool = False,
) -> dict:
    """统一调用 hermes CLI（F-4/F-6 地基）。

    Args:
        args: hermes 之后的参数（如 ["kanban", "create", title, "--assignee", ...]）
        timeout: 子进程超时秒（默认 30，与现状一致）
        expect_json: True 时 stdout 必须可解析为 JSON（建卡场景）

    Returns:
        {"returncode": int, "stdout": str, "stderr": str}

    Raises:
        HermesCLIError:
          kind='not_found' — hermes 不可达（FileNotFoundError 或解析兜底裸名）
          kind='timeout'   — 超时
          kind='nonzero'   — returncode != 0（stderr_excerpt 保留）
          kind='parse'     — expect_json 但 stdout 非 JSON
    """
    cmd = [hermes_bin()] + args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
    except FileNotFoundError:
        raise HermesCLIError(
            "not_found", hermes_unavailable_reason(),
            stderr_excerpt=f"FileNotFoundError: {cmd[0]}",
        )
    except subprocess.TimeoutExpired as e:
        raise HermesCLIError(
            "timeout",
            f"hermes 调用超时（>{timeout}s）: {' '.join(cmd[:3])}",
            stderr_excerpt=(e.stderr or "")[:500] if isinstance(e.stderr, str) else "",
        )
    if proc.returncode != 0:
        raise HermesCLIError(
            "nonzero",
            f"hermes 调用失败 rc={proc.returncode}: {' '.join(cmd[:3])}",
            stderr_excerpt=(proc.stderr or "")[:500],
        )
    if expect_json:
        import json
        try:
            json.loads(proc.stdout or "")
        except json.JSONDecodeError as e:
            raise HermesCLIError(
                "parse",
                f"hermes 输出非 JSON（可能为旧 CLI 无 --json）: {e}",
                stderr_excerpt=(proc.stderr or "")[:500],
            )
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
```

### 4.2 设计要点

- **A3 缓存**：`lru_cache(maxsize=1)` 模块级缓存——每 tick 多次调用（建卡/comment/show）只解析一次 PATH；`reset_hermes_bin_cache()` 供单测（T38）切换 env/PATH 场景。
- **C5 可覆盖**：`HERMES_BIN_FALLBACKS` env 覆盖回退列表（测试可注入空列表模拟彻底不可达）。
- **A5 stderr 摘要**：所有失败路径保留 stderr 前 500 字——回执/日志都能带上真实错误（间歇根因定位的钥匙）。
- **行为兼容**：交互 PATH 下 `hermes_bin()` 返回 which 结果（= venv bin），`hermes_invoke` 行为与现状一致（AC-6 零差异）。

### 4.3 F-5 五处调用点替换（diff 级）

| 文件 | 现状 | 改为 |
|------|------|------|
| pipeline/cmd_chain.py L262-295 `_hermes_create` | `cmd = ["hermes", "kanban", "create", ...]` + `subprocess.run` + 失败 `return ""` | 改用 `hermes_invoke(["kanban","create",...], expect_json=True)`；`HermesCLIError` → `return ""` 前把 `kind/stderr_excerpt` 记入模块级 `LAST_HERMES_ERROR`（供 build_roundtable_chain 组装结构化 errors） |
| pipeline/cmd_chain.py L298-306 `_comment` | `subprocess.run(["hermes","kanban","comment",...])` 吞异常 | `hermes_invoke(["kanban","comment",task_id,body])`；HermesCLIError → `log_hermes_error(e)` 落日志（不抛） |
| pipeline/cmd_chain.py L309-318 `_reclaim` | `subprocess.run(["hermes","kanban","reclaim",...])` 返回 bool | `hermes_invoke(["kanban","reclaim",task_id,"--reason",reason])`；except → False |
| pipeline/discover.py L212-228 `_create_est_card` | `cmd = ["hermes", "kanban", "create", est_title, ...]` | `hermes_invoke([...], expect_json=True)`；HermesCLIError → `log_hermes_error` + `return ""`（fail-open 回退 dev-only 注册不变） |
| pipeline/state.py L78-98 `get_kanban_task_state` | `subprocess.run(["hermes","kanban","show","--json",task_id])` 吞 FileNotFoundError 返回 None | `hermes_invoke(["kanban","show","--json",task_id], expect_json=True)`；HermesCLIError → `log_hermes_error` + `return None`（fail-open 不变） |

**关键点**：cmd_chain._hermes_create 保留 `return str` 签名（调用点 L606/644/728/789/1044 零改动），失败时通过模块级 `LAST_HERMES_ERROR: Optional[HermesCLIError]` 传递结构化原因；build_roundtable_chain / advance_sequential_chains 组装 `errors` 时读取它：

```python
# cmd_chain.py 模块级（新增）
LAST_HERMES_ERROR: Optional[HermesCLIError] = None

def log_hermes_error(e: HermesCLIError) -> None:
    """A5 红线: hermes 调用失败必须落日志（含 stderr 摘要）。"""
    import logging
    logging.getLogger("hermes_cli").error(
        "hermes CLI 调用失败 kind=%s msg=%s stderr=%s",
        e.kind, e.message, e.stderr_excerpt,
    )
```

### 4.4 失败原因传播（F-6 升级，对应 PRD 验收 AC-5）

`build_roundtable_chain` 的 errors 从「泛化建卡失败」升级为结构化：

```python
# 现状（L798）:
#   errors.append(f"建卡失败: {title}")
# 改为:
def _fmt_create_error(title: str) -> str:
    e = LAST_HERMES_ERROR
    if e is None:
        return f"建卡失败: {title}"
    if e.kind in ("not_found", "timeout"):
        return f"建卡失败（环境类:{e.kind}）: {title}；{e.message}；stderr={e.stderr_excerpt}"
    return f"建卡失败（业务类:{e.kind}）: {title}；{e.message}；stderr={e.stderr_excerpt}"
```

cmd_channel.sh `receipt()` 解析 RESULT JSON 时（L72-95）增加分支：

```bash
# RESULT JSON 解析后（python 内联段）:
if '环境类' in err_text or 'not_found' in err_text or 'timeout' in err_text:
    print('失败(环境): ' + err_text)   # P1 启用时此处驱动回滚（§7.1）
elif r.get('errors'):
    print('失败: ' + '; '.join(r['errors']))
```

---

## 5. F-6 升级 — 失败可观测（主修复）

### 5.1 现状问题（OC 补充发现的核心）

所有 hermes 调用失败时 stderr 被吞：

| 位置 | 吞法 | 后果 |
|------|------|------|
| cmd_chain._hermes_create L288-295 | `capture_output=True`，失败 `return ""` 丢弃 stderr | 「建卡失败」看不出是 timeout 还是 rc!=0 |
| cmd_chain._comment / _reclaim | `except ...: pass` | 回执丢失无痕 |
| state.get_kanban_task_state L97 | `except FileNotFoundError: return None` | 静默 fail-open |
| cmd_channel.sh L66/97/.../448 | `>/dev/null 2>&1 \|\| true` | 回执失败无痕 |
| cmd_channel.sh L119/148/... | `2>/dev/null) \|\| RESULT=""` | python stderr 全丢 |
| autopilot.sh L147/188/549/... | `2>/dev/null \|\| true` | 告警 comment 失败无痕 |

### 5.2 修复设计（A5 红线）

1. **Python 侧**：`hermes_invoke()` 统一捕获（§4.1），`log_hermes_error()` 把 kind/message/stderr_excerpt 写入 `logging`（autopilot.sh 的 python3 -c 子进程 stderr 默认汇入 autopilot.log——因为 cron 重定向 `>> logs/autopilot.log 2>&1`）。
2. **Shell 侧**：cmd_channel.sh 的 `2>/dev/null` 全部改为捕获式：

```bash
# 现状: RESULT=$(python3 -c "..." 2>/dev/null) || RESULT=""
# 改为: 失败时 stderr 落日志（不吞）:
RESULT=$(python3 -c "..." 2>"$TMP_ERR") || RESULT=""
if [ -z "$RESULT" ] && [ -s "$TMP_ERR" ]; then
    log "$CMD_ID: python 执行失败 stderr: $(head -c 500 "$TMP_ERR")"
fi
```

   `receipt()` 的 `hermes kanban comment ... >/dev/null 2>&1` 改为失败时打日志：

```bash
receipt() {
    ...
    if ! hermes kanban comment "$CMD_ID" "..." >"$TMP_OUT" 2>"$TMP_ERR"; then
        log "$CMD_ID: 回执 comment 失败: $(head -c 500 "$TMP_ERR")"
    fi
}
```

3. **回执带 stderr**（OC 强制）：失败回执 comment 文案追加 `；stderr=<摘要>`（≤500 字）。

### 5.3 预期效果

下一次间歇失败（同 tick 两张）发生时，autopilot.log 会出现：

```
[cmd-channel] t_xxx: create dev xxx → 失败(环境:timeout): 建卡失败: [DEV-PRD] xxx；
              hermes 调用超时（>30s）: hermes kanban create；stderr=...
```

→ 根因（超时？锁？gateway token？）一眼可见，无需再盲猜。

---

## 6. 测试方案（T36-T39 P0 + T40-T41 P1，编号 A6 重排）

### 6.1 测试矩阵（对应 PRD F-7 / 验收 AC-1..AC-7 + OC 强制 AC-10）

| # | 场景 | 前置 | 断言 | 对应 |
|---|------|------|------|------|
| **T36** | cron 最小 PATH 建卡（纵深防御验证） | `PATH=/usr/bin:/bin`（env 注入）下消费 `[CMD] create dev <议题>` | 建链成功（[DEV-PRD] 卡产生）+ 回执 comment 落卡 | AC-1 / F-1+F-2+F-3 |
| **T37** | cron 最小 PATH roundtable | 同上 `[CMD] roundtable B <议题>` | all_at_once 一次建全链 + parents 门控保序 | AC-2 / F-1+F-2+F-3 |
| **T38** | hermes_bin() 解析优先级单测 | ① `HERMES_BIN` 指向真实 hermes；② 无 env + PATH 含 hermes；③ 无 env + PATH 空 + 回退列表命中；④ 全空 → 裸名 | ① env 优先 ② which ③ 回退 ④ 裸名；reset_hermes_bin_cache 后生效 | AC-3/AC-4 / F-4 |
| **T39** | 失败可观测（A5 红线） | 模拟 hermes 不可达（`HERMES_BIN=/nonexistent` + `HERMES_BIN_FALLBACKS=` + PATH 空）消费 `[CMD] create dev` | 失败回执 comment 含「hermes CLI 不可用」+ stderr 摘要；autopilot.log 含 kind=not_found | AC-5 / F-6 |
| **T40**（P1） | 回滚重试（F-8） | 环境类失败（mock not_found）→ 卡回滚 ready → 下 tick 重试成功；连续 2 次失败 → blocked + 告警 | AC-8 | D1 gated |
| **T41**（P1） | 回执直连 sqlite（F-9） | hermes 不可达时失败回执 | task_comments 表新增行（不回执丢） | AC-9 | D1 gated |
| **AC-10**（强制） | **同 tick 两张 create dev 都成功** | fixture 两张 `[CMD] create dev`（长标题+全角括号，复刻 16:48 现场） | 两张都建链成功 + 两张回执落卡 | OC 强制 |

### 6.2 实现要点

- **T36/T37 的 PATH 注入**：test_cmd_channel.sh 中 `run_channel()` 改为可传 env：`env PATH=/usr/bin:/bin HERMES_KANBAN_DB="$KDB" bash "$REPO_ROOT/scripts/cmd_channel.sh" "$REPO_ROOT"`。注意 cmd_channel.sh 内部 source lib_hermes_path.sh 自举 → 找到 /usr/local/lib/hermes-agent/venv/bin → hermes 可达 → 建链成功。**此用例同时验证 L1 自举 + L2 解析的纵深防御**。
- **T39 模拟不可达**：`HERMES_BIN=/nonexistent HERMES_BIN_FALLBACKS= PATH=/usr/bin:/bin` → lib 自举也找不到（回退列表被 env 清空）→ python 侧 `hermes_bin()` 兜底裸名 → `hermes_invoke` 抛 FileNotFoundError → kind=not_found → 回执带「hermes CLI 不可用」。
- **AC-10 复刻现场**：fixture 用 16:48 的真实标题（含全角括号/箭头）两张同 tick；断言两张 `[DEV-PRD]` 卡都存在 + 两张 `[cmd-channel]` 回执 comment 都在。
- **存量回归**：T1-T35 全绿（AC-6）；`hermes_bin()` 交互 PATH 下解析结果与现状一致 → 零行为差异。

---

## 7. P1 设计（D1 裁定后实现）

### 7.1 F-8 建卡失败回滚重试（状态机）

```
env 类失败（not_found / timeout）
   │
   ├─ [cmd-retry] 计数 < 2
   │     ├─ 回滚: UPDATE tasks SET status='ready' WHERE id=? AND status='archived'（CAS: rowcount==1）
   │     ├─ 写计数 comment: "[cmd-retry] N/2 环境失败（<kind>），已回滚 ready，下 tick 重试"
   │     └─ 下 tick 自动重试（幂等键防重: 同 idempotency-key 返回已有卡/或建新卡——首棒未建成则正常建）
   │
   └─ [cmd-retry] 计数 ≥ 2
         ├─ UPDATE tasks SET status='blocked' WHERE id=?
         └─ 告警 comment: "[cmd-channel] 失败(环境): hermes CLI 连续不可用 2 次，卡滞留 blocked，待人工处置"

业务类失败（nonzero / parse）
   └─ 保持 archived + 明确回执（现状行为，不重试——重试必败）
```

- **幂等键防重**：build_roundtable_chain 已带 `dev-<spec_hash>-<step>`（L792）/ `rt-<hash>-<i>`（L730）；环境失败时卡未建成 → 无幂等冲突；重试成功正常建卡。
- **计数存储**：复用 comment 幂等守卫模式（[cmd-retry] 标记），不新增 DB 表（最小侵入）。
- **回滚 CAS**：`archived→ready` 仅当 rowcount==1 执行（与消费 CAS 对称，防并发双写）。

### 7.2 F-9 回执直连 sqlite

```python
# cmd_channel.sh 内 python 内联段（新增直连回执函数，复用 CAS/STALE 直连模式）
def direct_receipt(db, task_id, body):
    import sqlite3, time
    conn = sqlite3.connect(db)
    # 幂等守卫: [cmd-channel] 标记已有 → 不重复写（与 CLI comment 幂等语义一致）
    dup = conn.execute(
        "SELECT 1 FROM task_comments WHERE task_id=? AND body LIKE '[cmd-channel]%' "
        "AND body=? LIMIT 1", (task_id, body)
    ).fetchone()
    if not dup:
        conn.execute(
            "INSERT INTO task_comments (task_id, author, body, created_at) VALUES (?,?,?,?)",
            (task_id, 'autopilot', body, int(time.time())),
        )
        conn.commit()
    conn.close()
```

- 触发时机：`hermes kanban comment` 失败（rc!=0 / not_found / timeout）时 fallback 直连；成功仍走 CLI（保留 kernel 审计）。
- **注意**：直连写绕过 kernel 的事件审计/通知——仅作为 hermes 不可达时的最后手段（PRD N2 约束允许，回执 comment 是唯一豁免）。

---

## 8. 约束合规确认（汇总）

| 约束 | 合规 | 说明 |
|------|------|------|
| C1 fail-open | ✅ | lib_hermes_path.sh 不 exit；hermes_bin() 裸名兜底；hermes_invoke 异常被调用方捕获转结构化结果；主循环退出码不受 PATH 问题影响 |
| C2 单次消费/CAS | ✅ | 本 FIX 不动消费 CAS；P1 回滚是独立 CAS（archived→ready） |
| C3 discover 排除集 | ✅ | 未改 discover 排除逻辑（T32-T35 回归覆盖） |
| C4 建卡走 CLI + idem key | ✅ | hermes_bin() 只解析路径；幂等键不变 |
| C5 非唯一硬编码 | ✅ | 四级 env 覆盖：shell 层 `HERMES_BIN_DIR`（目录覆盖）+ `HERMES_PATH_FALLBACKS`（回退列表）；Python 层 `HERMES_BIN`（可执行文件覆盖）+ `HERMES_BIN_FALLBACKS`（回退列表） |
| C6 测试隔离 | ✅ | temp kanban.db + AUTOPILOT_LOCKFILE 隔离 + 不触碰真实 board |

---

## 9. 运维发现（OC 处置，非本 FIX 代码范围）

1. **双驱动 cron（A9）**：autopilot.log 显示 :01（*/2）与 :25（每 3 分钟）两个 tick 序列都跑 cmd_channel。:25 驱动来源未见于 `crontab -l`（root 用户）与 /etc/cron.d——可能为历史残留/其它用户 crontab/容器外调度。**建议 OC 排查并收敛为单一调度**；两驱动并发跑 cmd_channel（flock 前后时序）会放大 hermes CLI 并发/SQLite 锁竞争，是间歇失败的候选诱因之一。
2. **crontab 显式 PATH（PRD §9 运维项，保留建议）**：在 autopilot 条目前加 `PATH=/usr/local/lib/hermes-agent/venv/bin:/usr/bin:/bin`——双保险（本设计已让 repo 脚本自举，此项非必需但更稳）。
3. **失败现场保留**：t_02ed5f30 / t_cb4161cd / t_e3db035f / t_a737d47e / t_9f3a1c01 / t_9f3a1c02 六张已归档无产出 [CMD] 卡是间歇失败的现场证据；本 FIX 上线后若再失败，日志应直接给出根因。OC 按 D1 裁定结果决定是否重发（PRD N6）。

---

## 10. 工时估算与拆卡建议

### 10.1 工时（按 PRD §8 口径，含升级项）

| 模块 | 工时 |
|------|:---:|
| F-1/F-2/F-3 lib_hermes_path.sh + 双挂载 | 0.5h |
| F-4 hermes_cli.py（hermes_bin + hermes_invoke + 异常） | 1h |
| F-5 五处调用替换 + LAST_HERMES_ERROR 传播 | 1.5h |
| F-6 可观测升级（receipt 带 stderr + 日志红线） | 1h |
| T36-T39 + AC-10 测试 | 2h |
| **P0 小计** | **6h** |
| F-8 回滚重试 + F-9 直连 sqlite（P1，D1 后） | 2.5h |
| **合计** | **8.5h（P0 6h + P1 2.5h）** |

### 10.2 拆卡建议（提交 OC 决策，本卡不建卡）

- **建议拆 2 张**：① P0（F-1..F-6 + T36-T39/AC-10，6h）——纵深防御 + 可观测落地；② P1（F-8/F-9 + T40-T41，2.5h）——D1 裁定后开工。
- 理由：P0 独立可交付（哪怕 D1 悬而未决，可观测性已让下一次失败可定位）；P1 依赖 D1 裁定，串行更稳。
- 工程实现后由 QA 走 FIX 验收（AC-1..AC-10 全量）。

---

## 附：与相关既有文档的衔接

- PRD：docs/prd/fix-cmd-channel-cron-path-prd.md（本设计输入；根因章节被 A1 修正）
- OC 补充发现：t_e4a9dbe4 卡 comment（2026-08-13 17:02，PRD 交付后）
- B3 指令卡通道验收：docs/qa/retest-b3-cmd-channel.md、docs/qa/cmd-channel-verification.md
- 建卡铁律 v4 架构（编号/chain_check 同源）：docs/arch/arch-card-numbering-chain-v4.md
- 测试 harness：scripts/test_cmd_channel.sh（T1-T35 存量 + T36-T41 新增）
