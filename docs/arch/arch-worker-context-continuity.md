# 架构设计 — worker 上下文连续性（检查点提交 + 发现笔记 + 预算收紧 + 审批绕路治理）

> 编号: DPL-030 | 阶段: DEV-ARCH
> 作者：高见远（架构师） | 日期：2026-08-14 | 版本: v1.0
> 上游: docs/prd/worker-context-continuity-prd.md（v1.0，255 行，PRD 审核门 PASS 带 3 条修正）
> 前置: t_84c53424（prd，done）｜本卡: t_d24d1ad5（arch）
> 状态: 待 OC/FRANK 审核；OC 审核结论与 3 条修正全部吸收（见 §0）

---

## 0. 设计输入与审查修正吸收

### 0.1 审查链

| 节点 | 结论 | 对本设计的影响 |
|------|------|---------------|
| PRD 审核门（OC 审，t_84c53424 comment） | PASS + 3 条修正 | 全部吸收：修正 1→R1 执行范围（§1.4）；修正 2→R1.3 路径全覆盖（§1.6，MAJOR）；修正 3→AC 清单（§6 AC-9） |
| Frank 待裁决 2 项 | R4-B 建议 A / [WIP] 建议 A | 本设计按产品建议默认实施 A 方案；裁决落定可随时翻案（不阻塞落地，§8） |

### 0.2 修正 1（事实纠偏）吸收方式

PRD §0 图写「DPL-019 已上线 — SOUL 注入」，实测 **9/9 profile SOUL grep checkpoint/存档 = 0 命中**：
`scripts/inject_checkpoint_rule.sh` 已交付（13b5b36）但从未执行。本 arch 阶段已执行
（2026-08-14，run 889 会话内），实测结果：
- 首跑：INJECT 9/9（新增=9 跳过=0）→ `--verify` 9/9 VERIFY-OK
- 重跑幂等：SKIP 9/9（新增=0）→ `--verify` 9/9 VERIFY-OK

**结论**：DPL-019 SOUL 注入已真实上线（`轮次存档铁律（2026-08-13 Frank 裁定）` 段落在 9 profile
SOUL.md 均存在）。R1 的 `inject_wip_rule.sh` 必须**一并执行**，不允许只建脚本不跑
（修正 1 的直接要求），执行记录见 §7.2。

### 0.3 修正 2（注入路径盲区 — MAJOR）吸收方式

PRD R1 落点清单为 autopilot 6 处 comment + `_dev_card_body` + est_body，**未覆盖 subsplit 子卡 body 路径**。
实测确认（S2 复发病例）：

- `pipeline/cmd_chain.py:811-849` `_sub_card_body()`：dev/qa 拆卡子卡 body 构造函数。
  **结尾无任何 CHECKPOINT_BODY_LINE / 存档行** —— S2（t_22848225，[DEV-SUB-2] 拆卡子卡）
  的 body 实测无存档行，正是此洞。
- `_sub_card_body` 仅被 `_create_dev_sub_cards`（L883）与 `_create_qa_sub_cards`（L928）调用；
  这两条路径 = 链卡拆卡（[SUB-SPLIT]/[QA-SUB-SPLIT] 解析后 autopilot 建卡）与独立卡拆卡（discover 拆卡）。

本设计 R1.3 给出**全部 4 条建卡路径的注入点枚举**（链卡 dev / 拆卡子卡 dev+qa / discover est /
OC 手动建卡），逐一落点，堵死盲区。对应回归断言见 §6 AC-9。

### 0.4 修正 3（验收口径补强）吸收方式

AC 清单新增「subsplit 子卡 body 含 WIP_BODY_LINE」回归断言（§6 AC-9），
与修正 2 的洞一一对应，构成验收闭环。

---

## 1. R1+P2 核心设计 — WIP 检查点节奏 + 发现笔记（同一 SOUL 段，一次注入）

### 1.1 设计原则

1. **复用 DPL-019 注入管线，不新建机制**：constants 单一源 → 注入脚本幂等（--dry-run/--verify/--profiles）
   → 9 profile SOUL → 建卡路径 body/comment 注入 → 测试断言。与 checkpoint 完全同构，
   维护面不扩大。
2. **段落合并**：R1（WIP 节奏）与 R2（发现笔记）合并为**一段**「WIP 检查点节奏与发现笔记」，
   一次注入 9 profile，降低漂移面（PRD R2-5 已声明）。
3. **[WIP] commit 是唯一可信跨 run 状态**：worktree 工作区状态不可信（S2 实证），
   只有 git commit 历史可信。发现笔记随 [WIP] commit 入分支持久化。
4. **DPL-019 是兜底层，本设计是日常节奏层**：50 轮完整存档（comment 五字段）不变；
   本设计让每一 run 在 10-15 轮就产生可继承现场。

### 1.2 新增常量（pipeline/constants.py，DPL-019 段之后追加）

```python
# ── DPL-030: WIP 检查点节奏 + 发现笔记（Frank 2026-08-11 指令，PRD PASS）──
# 文档: docs/prd/worker-context-continuity-prd.md（规范源）
# 与 DPL-019 CHECKPOINT_* 的分层:
#   CHECKPOINT_* = 50 轮兜底完整存档（comment 五字段，超时继承唯一可信源）
#   WIP_*        = 10-15 轮节奏化轻量 checkpoint（[WIP] commit + 发现笔记，日常接续层）
WIP_SOUL_TITLE = "WIP 检查点节奏与发现笔记（2026-08-14 DPL-030）"
WIP_SOUL_PROFILES = [
    "game-engine", "game-qa", "game-architect", "game-director",
    "game-artist", "game-client", "gateway-eng", "infomanager", "tag-system",
]  # Frank 名单 9 profile，与 CHECKPOINT_SOUL_PROFILES 同源维护；D1 纳入 orchestrator → 追加
WIP_CHECKPOINT_MIN_ROUNDS = 10   # 节奏下界（实现/调试密集期取下限）
WIP_CHECKPOINT_MAX_ROUNDS = 15   # 节奏上界
WIP_COMMIT_PREFIX = "[WIP]"
WIP_NOTE_DIR = ".pipeline/wip"
WIP_BODY_LINE = "WIP 节奏: 每 10-15 轮 [WIP] checkpoint commit 到 worktree 分支，并更新 .pipeline/wip/<task_id>.md 发现笔记；重启 run 先读笔记 + git log 最近 [WIP]，禁止从零重来（DPL-030）"
WIP_SOUL_PARAGRAPH = """## WIP 检查点节奏与发现笔记（2026-08-14 DPL-030）

**每 10-15 轮做一次轻量 checkpoint（实现/调试密集期取下限），保证 run 重启后从上一轮直接接续。**

- **节奏**：每 10-15 轮（自估近似，宁可早不可晚）执行：
  1. `git add -A && git commit -m "[WIP] checkpoint <task_id> #N"`（worktree 分支内，含 .pipeline/wip/ 笔记）
  2. 更新 `.pipeline/wip/<task_id>.md` 发现笔记（发现即记，前 5 轮内必须创建）
- **[WIP] 前缀 = 显式例外于「有意义的 commit」原则**：merge 时由 merge worker 决定 squash 或保留。
- **发现笔记模板**（六节）：
  ```
  # WIP 发现笔记 — <task_id>（<标题>）
  ## 上游契约（前棒产物要点，含路径）
  ## 关键事实（schema/路径/环境，实测得来的）
  ## 已踩坑（现象→原因→绕法）
  ## 当前进度（对照验收标准的完成度）
  ## 下一步（重启 run 从这里继续）
  ## 更新记录（#N @ 轮次 M）
  ```
- **重启 run 领卡首个动作**：`git log --oneline` 找最近 `[WIP]` commit + 读发现笔记
  （存在则必读）→ 从其「下一步」继续，禁止重写已提交内容。
  笔记不存在且卡有前 run → 前 run 违规，在 comment 标注后从 git log 尽力恢复。
- **与轮次存档铁律的关系**：50 轮完整存档（comment 五字段）不变；本条是它的日常节奏层。
"""

EST_EFFECTIVE_RATIO = 0.7    # R3: 有效轮数折算系数（S2 实证：60 轮预算有效 ~40 轮）
EST_SPLIT_ROUNDS = 30        # R3: 折算后拆卡阈值参考值（预算 42+ → 预计 >30 有效轮 → 必拆）
EST_EFFECTIVE_LINE = "⚠️ 预估口径：按有效轮数估 = 迭代预算 × 0.7（审批绕路/发现/调试损耗，DPL-030 S2 实证）；预计 >30 有效轮（即预算 42+）→ 必须拆卡；4 交付物以上任务（如 引擎+测试+演练+集成）一律拆 ~3 卡"
```

**说明**：
- `EST_EFFECTIVE_RATIO=0.7` 为 S2 单样本初始系数，与 DPL-018 校准机制衔接（018 偏差反馈积累后由校准系数吸收，不新增机制）。
- `EST_SPLIT_ROUNDS=30` 是**折算后**的拆卡参考值，**不动** `EST_SPLIT_THRESHOLD_ROUNDS=20`（原始口径，Frank 已确认参数，红线）。

### 1.3 注入脚本 — scripts/inject_wip_rule.sh（新）

与 `inject_checkpoint_rule.sh` 完全同构（63 行 → ~63 行，同一模式）：

- 参数：`--dry-run` / `--verify` / `--profiles a,b`（默认 9 profile）
- 幂等：`WIP_SOUL_TITLE` 已存在 → SKIP（重跑安全）
- 段落唯一源：`cd $REPO_ROOT && PYTHONPATH=$REPO_ROOT python3 -c "from pipeline.constants import WIP_SOUL_PARAGRAPH, ..."`（杜绝影子导入，复刻 checkpoint 脚本 L22-24 注释的坑）
- 注入位置：SOUL.md 尾部追加（`---` 分隔），与 checkpoint 段并列

**执行记录**（修正 1 要求「执行既有脚本」，本 arch 已一并跑过 checkpoint 注入；WIP 注入
在 dev 实现后由 OC 授权执行，见 §7.2 执行清单）。

### 1.4 建卡路径注入点枚举（修正 2：全部 4 条路径）

| # | 建卡路径 | 文件:行 | 注入方式 | 注入内容 |
|---|---------|--------|---------|---------|
| P1 | 链卡 dev（cmd_chain 主链） | pipeline/cmd_chain.py `_dev_card_body` L646 之后 | body 末行追加 `WIP_BODY_LINE`（CHECKPOINT_BODY_LINE 已存在） | WIP_BODY_LINE |
| P2 | 拆卡 dev 子卡（[SUB-SPLIT]） | pipeline/cmd_chain.py `_sub_card_body` L849 之前 | body 末尾追加 **`CHECKPOINT_BODY_LINE` + `WIP_BODY_LINE`**（**修正 2 补洞**：DPL-019 存档行 + DPL-030 WIP 行一起补） | CHECKPOINT_BODY_LINE + WIP_BODY_LINE |
| P3 | 拆卡 qa 执行子卡（[QA-SUB-SPLIT]） | pipeline/cmd_chain.py `_sub_card_body`（同 P2，kind='qa' 共用） | 同上 | CHECKPOINT_BODY_LINE + WIP_BODY_LINE |
| P4 | est 卡（链卡 dev-est 块 / discover `_create_est_card`） | pipeline/cmd_chain.py dev-est 任务说明块（L621-638）+ pipeline/discover.py est_body（L236-250） | est 块决策行后追加 `EST_EFFECTIVE_LINE`；est body 末行（L249 CHECKPOINT_BODY_LINE 后）追加 `WIP_BODY_LINE` | EST_EFFECTIVE_LINE + WIP_BODY_LINE |
| P5 | autopilot 建卡 comment（实测 5 处） | scripts/autopilot.sh L159（手动卡注入）/ L343（dev）/ L383（qa-exec）/ L520（qa-post）/ L665（qa-d1 retry） | comment 串追加 `[WIP 节奏] 每 10-15 轮 [WIP] checkpoint commit 到 worktree 分支；重启 run 先读 .pipeline/wip/<task_id>.md + git log 最近 [WIP]，禁止从零重来（DPL-030）` | [WIP 节奏] 提示 |
| P6 | OC 手动建卡 | 同 P5 L159（手动卡注册后自动补 comment 路径，实测 L150-163 存在） | 同 P5 | [WIP 节奏] 提示 |

**注意**：
- P2/P3 共用 `_sub_card_body`，一处改动覆盖 dev/qa 两类拆卡子卡；实测 S2（t_22848225）
  正是 P2 路径漏注的病例（[DEV-SUB-2] body 无存档行）——故 P2/P3 必须同时补
  CHECKPOINT_BODY_LINE（DPL-019 欠账）与 WIP_BODY_LINE（DPL-030 新规）。
- **P5 实测为 5 处 comment 串**（PRD 写「6 处」）：L159（手动卡）+ L343（dev）+
  L383（qa-exec）+ L520（qa-post）+ L665（qa-d1 retry）。实测 L362（qa-d1 正常路径）与
  L400（qa-d2）的 `kanban_ensure_card` 调用**无 comment 参数**（仅 3 参数），故不构成
  注入点——按 5 处执行，PRD 与实测差异已在卡上记录，供 dev 参照。

### 1.5 发现笔记路径设计（R2）

```
仓库根/.pipeline/wip/<task_id>.md
```

- `.pipeline/` 已存在（archive/ gai/ 运行时目录，pipeline/state.py 使用），
  **不在 .gitignore**（实查：仅 pipeline_state.db 被 ignore）→ 随 [WIP] commit 入分支，
  跨 run 持久（worktree 分支跨 run 复用已实测，S2）。
- 文件名 `<task_id>.md` 全局唯一（t_ 前缀），子卡/链卡/独立卡互不冲突。
- 写入节奏：前 5 轮内创建（发现即记）；每 10-15 轮随 checkpoint 更新；50 轮完整存档时必须已更新。
- 内容模板：SOUL 段内固化（六节，见 WIP_SOUL_PARAGRAPH）。

### 1.6 R1 验收口径（PRD §5 继承 + 修正 3 补强）

| 项 | 口径 |
|----|------|
| 注入覆盖 | `bash scripts/inject_wip_rule.sh --verify` → 9 profile SOUL 均含 `WIP_SOUL_TITLE`（幂等重跑 SKIP） |
| dev 卡 body | 含 `WIP_BODY_LINE`（test_cmd_channel.sh 断言） |
| **subsplit 子卡 body（修正 3）** | **含 `WIP_BODY_LINE`（test_cmd_channel.sh 断言，回归锚点）** |
| est 卡 body | 含 `EST_EFFECTIVE_LINE`（折算行） |
| autopilot comment | 含 `[WIP 节奏]`（test_cmd_channel.sh 断言） |
| 真实场景 | 下一个跨度 >20 轮任务：`git log --grep='\[WIP\]'` ≥2 条 |

---

## 2. R3 设计 — est 卡预算收紧（P1）

### 2.1 设计要点

1. **口径注入（双入口）**：
   - 链卡：`_dev_card_body(step="dev-est")` 任务说明块末尾（L634 之后）追加 `EST_EFFECTIVE_LINE`；
   - 独立卡：`discover.py _create_est_card` est_body L244-246 之间追加 `EST_EFFECTIVE_LINE`。
2. **estimate.md 模板**：评估报告必须含一行 `有效轮数折算: 预算 60 × 0.7 = 42 有效轮`（可测断言）。
   模板文字注入 dev-est 任务说明块（与 EST_EFFECTIVE_LINE 相邻）。
3. **拆卡阈值不变**：`EST_SPLIT_THRESHOLD_ROUNDS=20`（原始轮数口径）不动；
   新增折算参考 `EST_SPLIT_ROUNDS=30`（有效轮口径）。两条口径并存，dev-est 依折算后判断。
4. **与 DPL-018 互补**：018 事后反馈（偏差 → 校准系数），030 事前收紧（折算 → 拆卡决策）。

### 2.2 验收口径

- dev-est 卡 body 含折算行（双入口断言）
- 下一个 [SUB-SPLIT] 评估报告含「有效轮数折算」行
- 拆卡阈值 20 不变（回归断言，T68b 扩展）

---

## 3. R4-A 设计 — 审批绕路治理（P1，行为规范路线）

### 3.1 设计要点

1. **SOUL 段固化**（并入 R1 同一段落或紧邻，PRD R4-A-1）：
   - 禁：`python3 -c "..."` / `python3 <<EOF` / `cat x | python3`（tirith 判 pipe_to_interpreter/heredoc → MEDIUM → 审批 → 60s deny）
   - 许：`write_file /tmp/<name>.py` → `python3 /tmp/<name>.py`（实测 Allow）；查状态用 `devppl_query.sh`（已固化）；`pytest`/`py_compile` 本就不拦
   - 原则：审批门限是防线不是障碍（Frank 2026-08-13 裁定，不因流畅放松）——本条只治「无谓撞门」，不主张放门
2. **devppl_query.sh 扩展**：新增 `comments <task_id>` 子命令（读卡 comment 线，
   worker 重启接续刚需，替代裸内联读 DB 的高频场景）。
   - 白名单：`^t_[a-z0-9]+$`（与 task/runs/chain 相同）
   - 只读：SQLite `mode=ro`（q() 已有）；`ORDER BY created_at ASC` 全文输出
   - 幂等/安全：不新增任何写路径

### 3.2 devppl_query.sh comments 子命令实现

```bash
  comments)
    [ $# -eq 2 ] || { echo "usage: devppl_query.sh comments <task_id>"; exit 1; }
    id="$2"; [[ "$id" =~ ^t_[a-z0-9]+$ ]] || { echo "BAD_ID: $id"; exit 1; }
    q "$KANBAN_DB" "SELECT id, author, created_at, body FROM task_comments WHERE task_id=? ORDER BY created_at ASC" "$id"
    ;;
```

- 注册到 usage 行（L75）与头部注释（L6-11）。
- 注意：q() 的 datetime 转换按列名匹配 `created_at`，comments 子命令自动获得时间可读性。

### 3.3 验收口径

- `devppl_query.sh comments <id>` 输出卡 comment 线（含 author/时间/body）
- `devppl_query.sh comments bad_id` → `BAD_ID` 拒绝（白名单）
- 机制上线后 30 天 tirith 日志 `pipe_to_interpreter`/heredoc Block 事件环比下降 ≥50%（观察指标，不设门禁）

---

## 4. R4-B 设计（P2，待裁决，本设计不默认实施）

若 Frank 裁定接受安全面扩大：tirith policy 层为 worker profile 放行 `/tmp` 下脚本执行模式。
**本 arch 不实施**——触碰「不改 Hermes 本体」红线边缘（Frank 2026-08-10 裁定），
且 R4-A 已覆盖 90% 痛点（S2 + PRD 会话双验证）。裁决问题见 §8 待办。

---

## 5. 模块划分与依赖

```
pipeline/constants.py          ← 新增 WIP_* / EST_* 常量（单一源）
pipeline/cmd_chain.py          ← _dev_card_body / _sub_card_body / dev-est 块 注入
pipeline/discover.py           ← _create_est_card 注入
scripts/inject_wip_rule.sh     ← 新脚本（复刻 inject_checkpoint_rule.sh）
scripts/autopilot.sh           ← 5 处 comment 串追加 [WIP 节奏]
scripts/devppl_query.sh        ← 新增 comments 子命令
scripts/test_cmd_channel.sh    ← 新增断言（AC-1..AC-9）
```

依赖方向：constants → 注入脚本/body 构造/测试（单向，无环）。
不改 Hermes 本体（引擎/dispatcher/审批内核零改动）。

---

## 6. 验收标准（AC 清单，VA 可核）

| # | 验收项 | 证据 | 来源 |
|---|--------|------|------|
| AC-1 | constants.py 新增 WIP_SOUL_* / WIP_BODY_LINE / EST_* 常量 | grep pipeline/constants.py | PRD 6.1 |
| AC-2 | inject_wip_rule.sh 幂等注入 9 profile，--verify 全 HIT/SKIP | 脚本输出（--dry-run 预览 + 真实注入记录） | PRD 6.1 |
| AC-3 | autopilot.sh 5 处建卡 comment 含 `[WIP 节奏]` | grep scripts/autopilot.sh | PRD 6.1（6 处语义，5 处实测） |
| AC-4 | dev 卡 body 末含 WIP_BODY_LINE | test_cmd_channel.sh 断言 | PRD 6.1 |
| AC-5 | est 卡 body 含 EST_EFFECTIVE_LINE（双入口） | test_cmd_channel.sh 断言 | PRD 6.1 |
| AC-6 | devppl_query.sh 新增 comments 子命令（白名单 + 只读） | 手测 + 断言 | PRD 6.1 |
| AC-7 | test_cmd_channel.sh 全量回归 PASS（基线 373 + 新增） | 测试输出 | PRD 6.1 |
| AC-8 | 结构化 claim（changed_files/tests_run/verification） | kanban_complete metadata | PRD 6.1 |
| **AC-9** | **subsplit 子卡 body 含 WIP_BODY_LINE 且含 CHECKPOINT_BODY_LINE（修正 3 补强，修正 2 回归锚）** | **test_cmd_channel.sh 断言（新增 T7x）** | OC 修正 3 |
| AC-10 | EST_SPLIT_THRESHOLD_ROUNDS=20 不变（红线回归） | 断言 | PRD §7 约束 2 |

---

## 7. 落地计划（S1-S4，估算与 PRD §9 一致，8-10h 单 dev 卡）

### 7.1 任务拆分建议（给 OC 派发参考）

| 阶段 | 内容 | 估时 | 依赖 |
|------|------|------|------|
| S1 | constants 常量 + inject_wip_rule.sh + 4 路径 body 注入（_dev_card_body/_sub_card_body/discover）+ 5 处 comment 注入 | 3-4h | 无（本 arch 批准） |
| S2 | est 口径双入口（R3）+ devppl_query.sh comments 子命令（R4-A） | 2h | S1 后 |
| S3 | test_cmd_channel.sh 新断言（AC-4/5/6/9/10）+ 全量回归 | 2-3h | S2 后 |
| S4 | OC 授权执行 9 profile SOUL 注入（inject_wip_rule.sh --verify）+ checkpoint 注入核对 | 0.5h | S1 后（脚本就绪） |

建议拆 1 张 dev 卡（有效轮 ~20 < 20 拆卡阈值，单卡可完成）；若 OC 倾向 2 卡（S1+S2 / S3），
按 [SUB-SPLIT] 走即可，不强制。

### 7.2 SOUL 注入执行记录（本 arch 已完成部分）

| 脚本 | 状态 | 实测 |
|------|------|------|
| inject_checkpoint_rule.sh（DPL-019，修正 1） | ✅ 已执行 | 首跑 INJECT 9/9；重跑 SKIP 9/9；--verify 9/9 VERIFY-OK |
| inject_wip_rule.sh（DPL-030，本设计） | ⏳ dev 实现后 OC 授权执行 | — |

> 注：本 arch 会话已把 DPL-019 的 SOUL 注入落地（修正 1 要求），WIP 注入脚本在 dev
> 实现后由 OC 执行（跨 profile 写，需 OC 授权，PRD §7 约束 4）。

---

## 8. 待办 / 待裁决（不阻塞落地）

| # | 事项 | 状态 |
|---|------|------|
| 1 | Frank 裁决 R4-B（tirith policy 白名单）是否实施 | 产品建议 A；本设计按 A 落地，B 留档 |
| 2 | Frank 裁决 [WIP] commit 与「有意义的 commit」原则 | 产品建议 A（显式例外）；本设计按 A 落地 |
| 3 | orchestrator 是否纳入 SOUL 注入名单 | D1 裁决；constants 预留追加位置 |

---

## 9. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 注入面扩大（5 处 comment + 4 路径 body）导致文案漂移 | 中 | 全部文案唯一源 constants；test_cmd_channel.sh 断言锚定；inject 脚本 --verify |
| [WIP] commit 污染主分支历史 | 低 | worktree 分支隔离（dev 卡强制 worktree）；merge worker 决定 squash/保留 |
| .pipeline/wip/ 与运行时目录混淆 | 低 | 目录已存在同类（archive/ gai/）；命名 wip/ 语义清晰；gitignore 不新增 |
| 0.7 系数失真（单样本） | 低 | 与 DPL-018 校准衔接，系数由校准机制吸收；S2 样本已是最佳实证 |
| 审批门限放松误读 | 低 | SOUL 段明确「审批门限是防线不是障碍」，只治无谓撞门 |

---

## 附：相关文档与证据

- PRD: docs/prd/worker-context-continuity-prd.md（v1.0）
- 既有注入管线: scripts/inject_checkpoint_rule.sh（63 行，DPL-019 模式）
- 注入点实测: pipeline/cmd_chain.py L564-647 / L811-849 / pipeline/discover.py L236-250 / scripts/autopilot.sh L159/L343/L383/L520/L665
- 测试基线: scripts/test_cmd_channel.sh（373 PASS，PRD-GATE 后）
- S2 病例: /root/.hermes/kanban/logs/t_22848225.log（2058 行）
- tirith 证据: /root/.local/share/tirith/log.jsonl（24016 verdicts / 453 Block）
