# oc_wake [SILENT] 判据规范（DPL-103）

> 状态: 定稿（裁定通过）
> 适用: OC live cron `oc_wake` job prompt（`/root/.hermes/profiles/orchestrator/cron/jobs.json`）
> 关联: DPL-099（GLM 停机窗口静默语义，保留不误伤）

## 1. 问题实录（2026-09-29）

唤醒器（oc_wake cron）某轮检测到 `[blocked-new]` 并做了**实质处置**（建 ARCH 裁定卡），
却因 prompt 的 `[SILENT]` 条款自判「无需决策」而静默结束——OC 与 Frank 均不知道处置
发生过。当日连续五轮 `[SILENT]` 吞掉处置记录；期间 `t_a54ae503` 与 `t_49f54dd5`
发生撞卡（处置不可见 → 无法及时协调）。

根因: 旧 `[SILENT]` 条款只看「是否需要 Frank 决策」，不看「本轮是否做了动作」。
处置了但不投递 = 处置黑洞。

## 2. 新条款全文（建议 prompt 替换文案）

> [SILENT] 仅允许用于零发现且零动作的纯空轮（检测输出 = NO_ANOMALY 且未做任何操作）。
> 凡本轮做过任何实质处置（kanban 建卡/block/unblock/resume/reclaim/comment 协调），
> 必须正常输出本轮总结，内容包含处置清单（做了什么、建/动了哪些卡）。
> 「无需 Frank 决策」不等于「无需告知」。
> 例外：[glm-shutdown] 停机窗口内仍按 DPL-099 静默。

配套机制: `scripts/oc_wake_check.sh` 在 out 非空（有异常条目）时随 out 追加
`[action-required]` 注记行，提醒唤醒器禁静默（源 S）。

## 3. OC 落地指引

1. 编辑 live `/root/.hermes/profiles/orchestrator/cron/jobs.json`，定位 `oc_wake` job
   的 prompt，将其中 `[SILENT]` 相关条款段替换为上文第 2 节全文。
2. 替换由 OC 执行；repo 侧仅本 spec 留档（prompt 属 live profile，不进 repo）。
3. 验证: 下一轮含异常条目的检测输出应出现 `[action-required]` 行（DPL-103 源 S），
   唤醒器该轮应正常投递总结（含处置清单）。
4. 例外确认: `[glm-shutdown]` 停机窗口内静默语义（DPL-099）不变，替换文案中已含
   例外条款，不得单独删除。

## 4. [DPL-103 追问 2026-09-29 Frank 采納三点]（合并时补实现）

Frank 追问「第二点扩围不加条件门确实有永动风险」，修正设计如下三点：

### 4.1 autopilot 不扩（保持 G5 双条件）
autopilot 机械 resume 保持 G5 双条件（paused + 窗口内新增 ready/todo 卡）不变。
idle_check 3-tick 空闲休眠是合法态；无条件 resume 会造成「休眠↔空转↔再休眠」
烧 token 循环。

### 4.2 watchdog/巡察使 resume 扩围
`oc_wake_check.sh` 新增哨兵扩围段（独立于 autopilot paused 分支，每 tick 执行）：
- watchdog（cron 72852093c5e6）/ 巡察使（cron 530a359ebff3）paused = 异常态：
  常驻监控、空转成本≈0（不调 LLM）、无休眠设计；resume 后仍是 2min/每日轻任务，
  不会自我触发，天然无循环。
- 机械判定：`state=paused` 且 `paused_reason` 有机械方标注 → 立即
  `hermes cron resume`，输出 `[auto-resume] <哨兵>(<id>) ...`。
- 人工豁免：`paused_reason` 含 manual/frank/Frank/人工 → 只告警不 resume，
  输出 `[sentinel-paused-manual]`（Frank 手动停的不能被机械 undo）。
- 未知来源：paused 且无 paused_reason → 保守不机械 resume，输出
  `[sentinel-paused-unknown]` 交 OC 判定。
- GLM 停机窗口内整段跳过（DPL-099 静默，探针负责复位）。

### 4.3 人工暂停豁免（manual/frank 只告警不 resume）
autopilot 本体 G5 分支同样先查 `paused_reason`：含 manual/frank/人工 → 只告警不
resume（即使 pending_new > 0）。配套：机械 pause 方 pause 时同步写 paused_reason
（idle_check.sh 已补标注写入；glm_quota_probe.sh 已有 reason 传递机制）。


## 6. 三件套联动契约（DPL-103，Frank 2026-09-29 拍板）

三件套 = autopilot（cron 4e52405060a3）/ watchdog（72852093c5e6）/ oc_wake
（f2aa32251adc）。巡察使（530a359ebff3）随 watchdog 同款处置。

### 6.1 活跃卡定义（唯一口径）
活跃卡 = status NOT IN ('blocked','paused','done','archived')，
即 todo/ready/running/triage，现势全量、不限窗口。
- 存在活跃卡 → 三件套应处于 active。
- 不存在活跃卡超 3 tick → idle_check 3-tick 休眠 → 立即跑一次 oc_wake
  → 跑完无卡状态变化 → 三件套集体休眠（不打扰=休眠）。

### 6.2 建卡入口三灯齐拉（scripts/trio_wake.sh）
`oc_create_card.sh` 与 `cmd_channel.sh`（cmd_wake_autopilot）建卡/拒绝路径
统一调 `scripts/trio_wake.sh`：三件套齐查齐拉，替换原「只 resume autopilot
单个」。
- 机械 pause（paused_reason 有机械方标注）→ resume。
- 人工豁免：paused_reason 含 manual/frank/人工 → 只告警不 resume（三处口径
  与 4.2/4.3 哨兵扩围一致）。
- 无 paused_reason → 保守只告警。
- fail-open：trio_wake.sh 缺失时 cmd_channel 兜底保留原单 autopilot 行为。

### 6.3 三灯显式状态收敛（trio_state.json）
`oc_wake_check.sh` 每 tick 终局写 `$REPO_ROOT/.pipeline/trio_state.json`
（TRIO_STATE_FILE 可覆盖）：
- `trio=sleeping`: 无活跃卡 && 本轮无异常（out 空）&& 非停机窗口。
- `trio=active`: 存在活跃卡或本轮有异常输出。
- `trio=shutdown`: GLM 停机窗口内（glm-shutdown 行存在）——停机不是休眠，
  不写休眠标注（DPL-099 保留，探针负责复位）。
写失败 fail-open 不阻断主检测。状态文件供建卡入口与人工互查，不作为
调度依据（调度仍以 cron state 为准）。

### 6.4 G5 resume 条件扩围
autopilot paused 且非人工暂停时，resume 条件从「窗口内新增 todo/ready」
扩为「窗口内新增 OR 全量活跃卡」——一张 running 老卡也算真有活干。

### 6.5 边界
- 不动 hermes 本体；GLM 探针（201fb5e2241b）与巡察使不在本契约三件套内
  （巡察使随 watchdog 同款哨兵处置，见 4.2）。
- 休眠动作尊重 GLM 停机窗口：停机窗口内不写休眠标注、不机械 resume。
