# B1 通知 cron — QA 独立复测报告

> 版本：v1.0 | 日期：2026-08-11 | 作者：game-qa
>
> 任务卡：t_96cf339b [B1-QA] QA 复测 — 通知 cron 独立验证
> 被测提交：40f6aaf（研发卡 t_b3e1c93e，run 551）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 0. 执行摘要

| 项目 | 数值 |
|------|:---:|
| 研发测试套件独立重跑（test_notify_check.py） | **27 PASS / 0 FAIL**（exit 0） |
| QA 独立边界断言（qa_notify_retest.py，12 组） | **32 PASS / 0 FAIL**（exit 0） |
| 代码审查核对项 | 7/7 通过 |
| 实机核对项 | 6/6 通过 |
| 缺陷 | **1 MAJOR**（B1-F1，triage_needed）+ 1 SUGGESTION（B1-DOC-1） |
| 结论 | **FAIL（有条件通过）** — 核心功能与验收标准全部通过；B1-F1 为失败/重试路径下的消息内容缺陷，建议修复后合入或按 known issue 处理 |

发布门禁对照（§10）：BLOCKER=0，MAJOR=1（≤3 放行阈值内），安全漏洞=0，无未裁定申诉 → **门禁通过**；但 B1-F1 建议在当前窗口内修复（修复成本极低）。

---

## 1. 代码审查核对（notify_check.py，665 行）

| # | 核对项 | 结论 | 依据 |
|---|--------|:---:|------|
| 1.1 | heartbeat work-gated 判定：ACTIVE = pipeline 有 pending/running/blocked **或** kanban 有未归档 [CMD] 卡；IDLE = 静默 | ✅ | `is_active()` L277-281：`cmd_cards > 0 → True`，否则 `any(status in (pending,running,blocked))`；L614-635：仅 `active and enabled and not in_silent_window` 推 heartbeat；IDLE 分支 L635 打日志不推 |
| 1.2 | 边界消息：IDLE→ACTIVE「开工」/ ACTIVE→IDLE「空闲」（里程碑） | ✅ | L559-585：prev_state 变化才触发；合成 hash 入 notify_events 走冷却体系（L567/L572） |
| 1.3 | event_hash = md5(task_id\|step\|status\|event_type)，不含 detail | ✅ | L220-223：签名即四字段，无 detail；E4 独立验证 5 断言 |
| 1.4 | 冷却判定 last_sent_at > now-30min | ✅ | L398-407 `cooldown_active()`：`last_sent_at > datetime('now','-30 minutes')`；E6 边界验证 3 断言 |
| 1.5 | token 缓存（kv_store 过期才重换） | ✅ | L339-364：TTL 内直接返回缓存，过期才调 token API；E5 独立验证过期重换 3 断言 |
| 1.6 | 7 天清理 | ✅ | L476-491 `cleanup()`：notify_events 按 created_at 删 7 天外 + pipeline_snapshot 仅保留活跃 task |
| 1.7 | fail-open（缺源/无凭据/API 挂不崩） | ✅ | L501-504 无凭据早退；L167-168/L184-185 缺源返回空；L389-391 网络异常捕获返回 False；main L659-661 全局兜底返回 0；T5/E8/E9 独立验证 |

**附加审查发现**：
- 只读安全：`read_pipeline_steps` 用 `mode=ro` URI（L169）、`read_cmd_cards` 同（L186）；E7 对 pipeline_state.db 副本跑完整 tick 前后 hash 一致 ✅
- 发送失败不写 last_sent_at（L556/L610/L631 的 `and not dry_run` + 失败分支不 mark）→ 下 tick 重试，符合 engineer #848 设计 ✅
- 首跑判定用 kv `initialized` 而非 snapshot 空表（L514）——空 pipeline 仅 [CMD] ACTIVE 时 snapshot 恒空，此设计正确 ✅

---

## 2. 独立测试执行

### 2.1 研发套件独立重跑（非信任研发记录，亲自执行）

```
cd /workspace/devPPL && python3 scripts/test_notify_check.py
RESULTS: 27 PASS / 0 FAIL   （EXIT_CODE=0）
```
覆盖 T1 token 缓存 / T2 work-gated / T3 diff+去重 / T4 exception 无视 silent_window / T5 fail-open / T6 7 天清理 / T7 [CMD] ACTIVE / T8 dry-run 防污染。与研发 smoke 文档记录一致。

### 2.2 QA 独立边界断言（自建 fixture，不复用研发断言）

运行：`python3 /tmp/qa_notify_retest.py`（12 组 32 断言全 PASS，EXIT 0）

| 组 | 验证点 | 断言 |
|----|--------|:---:|
| E1 | **IDLE 状态不推 heartbeat 实际验证**：ACTIVE 推 1 条 → 全 done → 连续 3 个 IDLE tick 零 heartbeat + work_state 持久化 idle | 3 ✅ |
| E2 | **[CMD] 卡存在但 pipeline 无活跃任务的 ACTIVE 判定**：2 张未归档 [CMD] 卡 + 空 pipeline → 推 heartbeat（计数活跃0）；归档后停止 | 3 ✅ |
| E3 | **silent_window=null 行为**：in_silent_window False、heartbeat 照推 | 2 ✅ |
| E4 | event_hash 不含 detail：同字段恒同、不同字段必不同、hash=md5(四字段) | 5 ✅ |
| E5 | token 过期重换：缓存期 1 次 → 强制过期 → 重换 + 新 token 落库 | 3 ✅ |
| E6 | 冷却边界：now→冷却中；31min 前→释放；未知 hash→不冷却 | 3 ✅ |
| E7 | 只读验证：pipeline_state.db 副本跑 tick 前后 md5 一致 | 1 ✅ |
| E8 | 飞书 API 抛网络异常（URLError）→ tick 不崩 | 2 ✅ |
| E9 | 无凭据（config 空 + .env 不存在）→ 跳过不崩、不换 token | 2 ✅ |
| E10 | 非法 silent_window 字符串（非格式/越界时间）→ False 不崩 | 2 ✅ |
| E11 | heartbeat 格式 `[AP HH:MM] 活跃N 跑N 堵N 今完N` + ≤80 字 + 计数正确 | 4 ✅ |
| E12 | IDLE→ACTIVE 开工边界 30min 去重（状态抖动不刷屏） | 2 ✅ |

---

## 3. 实机核对

| # | 核对项 | 结果 | 证据 |
|---|--------|:---:|------|
| 3.1 | crontab 已接入 | ✅ | `crontab -l` L13：`*/2 * * * * bash /workspace/devPPL/scripts/notify_cron.sh >> /workspace/devPPL/logs/notify_cron.log 2>&1` |
| 3.2 | cron 实跑存活 | ✅ | kv_store `initialized`/`work_state` updated_at=04:06:01（检查时刻 04:07:19）→ 每 2 分钟 tick 正常；`/usr/sbin/cron` 进程存活 |
| 3.3 | notify_cron.log 内容 | ✅ | 首跑行 `2026-08-11 03:54:01 首跑建基线（不 emit），工作状态=ACTIVE，步骤数=3`。此后无日志行 = ACTIVE tick 全部发送成功（成功路径不写 stdout，符合设计）；无 IDLE/失败/异常行 |
| 3.4 | notify_state.db 结构 | ✅ | 3 表：`notify_events`（含 UNIQUE(event_hash)+2 索引）、`pipeline_snapshot`（PK task_id,step_name）、`kv_store`；与 NOTIFY_SCHEMA 完全一致 |
| 3.5 | notify_state.db 在 .gitignore | ✅ | `.gitignore` L6-8（注释「含飞书 token 缓存，禁止入库」）；`git check-ignore` 确认；`git ls-files` 无该文件 |
| 3.6 | 真实 token 缓存 | ✅ | kv_store 存有真实 tenant_access_token + expires_at（03:54:09 写入，~2h TTL）；至 04:06 未重换（缓存生效） |
| 3.7 | 生产 dry-run | ✅ | `python3 scripts/notify_check.py --dry-run` → `[AP 12:04] 活跃1 跑1 堵1 今完0`（1 running + 1 blocked → ACTIVE，计数与 pipeline_steps 实况一致） |
| 3.8 | 凭据链路 | ✅ | config/notify.json app_id/secret 空 → fallback `/root/.hermes/profiles/verifier/.env`（存在，0600） |

---

## 4. 缺陷清单

### B1-F1（MAJOR，triage_needed）— 边界消息重试/dry-run 后推送垃圾文案 `__boundary__ work_state done`

**现象**：当「开工/空闲」边界消息发送失败，或对生产库执行 dry-run 触发边界后，下一个 tick 会向飞书推送包含内部合成标识的垃圾文案：

```
✅ t_a dev done, __boundary__ work_state done
```

其中 `__boundary__ work_state done` 是合成行被误当普通 milestone 格式化的结果（真实任务/步骤名缺失，且状态后缀硬编码为 `done`，与实际 idle/active 不符）。

**根因**：边界消息合成行（task_id=`__boundary__`，step_name=`work_state`，event_type=`milestone`）在发送失败（S1）或 dry-run（S2）时不写 `last_sent_at`（符合 FIX-1 设计意图），因此进入 pending 队列（L538-543：`event_type IN ('exception','milestone') AND last_sent_at IS NULL`）；下 tick milestone 聚合路径（L595-606）对该行无过滤，直接格式化为 `{task_id} {step_name} done`。

**复现步骤（S1 — 发送失败重试）**：
1. 建 fixture：pipeline 1 个 running 步骤，跑 1 tick 建基线（ACTIVE）
2. 步骤置 done，令飞书 send API 返回失败（模拟 code=99999），跑 1 tick → 空闲边界行入 notify_events，`last_sent_at=NULL`
3. 恢复 send 成功，再跑 1 tick → 观察推送内容包含 `__boundary__ work_state done`

**复现步骤（S2 — 生产 dry-run）**：
1. 同上建基线（ACTIVE）
2. 步骤置 done，跑 `--dry-run` tick → 空闲边界行写入但 `last_sent_at=NULL`（dry-run 不 mark，FIX-1 行为）
3. 跑 1 个真实 tick → 推送 `✅ t_a dev done, __boundary__ work_state done`

**影响面**：
- 用户可感知：飞书（运维主通道）出现误导性垃圾文案（形似「__boundary__ 任务 work_state 步骤完成」）
- 附带损失：设计的边界信号（Frank 裁定「空闲」消息 = 区分静默-没事 vs 静默-死了）在该路径被垃圾文案消费掉，真实「空闲」消息不再补推
- 发生时机恰在 API 故障恢复窗口（最需要准确信息的时刻）；且 dry-run 是 smoke 文档记录的常规操作，生产库跑 dry-run 即可触发
- 自愈：单 tick 后恢复，不破坏后续事件；无数据损坏

**判定公式对照（§1.2）**：
- 安全漏洞？否
- 功能阻断？否（通知管道整体可用，其余消息正常；仅 1 条消息内容错误）
- workaround？无（运维无法拦截该条）
- → 按公式下限为 MINOR（用户可感知 AND 不影响核心任务完成）；但叠加「边界信号丢失」+「故障恢复窗口发生」+「dry-run 常规操作即可触发」，按 §1.3「无法判断级别时默认取高级别」裁定为 **MAJOR（triage_needed）**，交研发评估（§6 论证流程，可附理由降级）

**最小修复建议（供研发参考，QA 只测不改）**：milestone 聚合路径（L595）过滤合成行：
```python
milestone_rows = [r for r in pending
                  if r["event_type"] == "milestone" and r["task_id"] != "__boundary__"]
```
合成行继续留在 notify_events 承担冷却/审计职责，但不再进入正文格式化。回归用例：S1/S2 各 1 条（断言推送不含 `__boundary__`，且真实「空闲」边界在失败恢复后以正确文案补推）。

**SLA 对照（§8）**：MAJOR → 研发 1 工作日内响应，2 工作日内定位，当前版本窗口内出方案。

### B1-DOC-1（SUGGESTION）— smoke 文档边界 hash 描述与代码不符

`docs/qa/notify-cron-smoke-verification.md` §5.3 写合成 hash `__boundary__|active|idle|milestone`，代码实际为两个独立 hash（L567 `__boundary__|active|milestone`、L572 `__boundary__|idle|milestone`）。行为正确（各方向独立冷却），纯文档失准，建议下次文档维护顺带修正。

---

## 5. 验收标准对照（6 条全过）

| # | 验收标准 | 证据 | 结果 |
|---|---------|------|:---:|
| 1 | 飞书 token 缓存（1 tick=1 发送，token 只过期重换） | T1 + E5 + 实机 3.6 | ✅ |
| 2 | heartbeat work-gated（活跃推/清空停/边界消息） | T2 + T7 + E1 + E2 + E12 | ✅ |
| 3 | 事件推断 + event_hash 去重（30min 冷却） | T3 + E4 + E6 | ✅ |
| 4 | 三路经独立（exception 无视 silent_window） | T4 + E3 + E10 | ✅ |
| 5 | 不影响 autopilot（独立运行、fail-open） | T5 + E7 + E8 + E9 | ✅ |
| 6 | 7 天滑动窗口清理 | T6 + 代码审查 1.6 | ✅ |

---

## 6. 结论

- **核心功能与 6 条验收标准全部通过**：27 研发断言 + 32 QA 独立断言全绿；crontab 实跑存活、token 缓存生效、fail-open 各路径验证、只读安全确认。
- **发现 1 个 MAJOR（B1-F1）**：边界消息失败重试 / dry-run 路径推送 `__boundary__ work_state done` 垃圾文案。非阻塞（BLOCKER=0，MAJOR=1 ≤ 3，门禁可过），但修复成本极低（1 行过滤），建议当前窗口内修复。
- **发布建议**：修复 B1-F1 后合入，或按 known issue 标注发版（触发条件为 API 故障恢复 / 生产 dry-run，概率低但会污染主通知通道）。

## 7. 备注

- 本复测未修改任何 B1 文件（QA 只测不改）；独立断言脚本存于 `/tmp/qa_notify_retest.py`、`/tmp/qa_boundary_repro.py`，报告存于 `docs/qa/retest-notify-cron-b1.md`。
- 工作树中 `scripts/autopilot.sh` 的未提交改动为并行 B2 任务（Gap2+5 手动建卡注入）的进行中工作，与本任务无关，未触碰。
- 缺陷处置建议：由 OC 依据本报告创建 FIX 卡（assignee 研发），QA 在修复后执行回归（复跑 S1/S2 场景 + 27/32 断言套件）。
