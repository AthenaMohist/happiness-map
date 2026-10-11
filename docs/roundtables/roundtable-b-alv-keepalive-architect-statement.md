# RT-B Roundtable 架构评审 — 保活 5 项重评估 (ALV-001~005)

> 角色：高见远（架构师） | 日期：2026-07-12
> 评审对象：Product 裁定 `roundtable-b-alv-keepalive-product-ruling.md`
> 代码审查范围：
> - `/workspace/hermes_keepalive_v2.sh`（469 行，线上运行版本）
> - `/workspace/hermes_keepalive.sh`（267 行，v1）
> - `/workspace/hermes_hcd_watchdog.sh`（30 行，外部 watchdog）
> - `/workspace/SandboxHermesBackup/scripts/usr/local/share/supervisor/hermes-keepalive.conf`

---

## 核心结论

**Product 裁定大方向正确（3 归档 + 1 降级 + 1 保留），但存在 1 个事实性错误和 1 个风险误判。纠偏后结论不变，补充 3 项架构缺口。**

---

## 逐项架构评审

### ALV-001：Layer E 唯一判定 → 归档

| 维度 | Product 裁定 | 架构评审 |
|------|-------------|---------|
| **裁决** | 归档 | **同意归档** |
| **理由** | "keepalive v2 已无 Layer E" | **理由修正**：Layer E 确实存在于 v2 |

**关键发现：Product 的事实依据有误。**

keepalive v2 第 56 行明确定义：
```bash
readonly PLATFORM_INTERVAL=120    # Layer E: platform registration
```

第 171–198 行实现 `do_platform_register()` 函数，通过 CloudStudio healthz registry API 注册反休眠。第 337 行在 daemon_loop 中每 120s 调用。**Layer E 是存在的，且是 v2 最关键的层级**（CloudStudio 休眠不看 OS 活动，只看平台心跳）。

那为什么归档仍然正确？因为 ALV-001 的原始任务是"重构编排逻辑中的 Layer E 唯一判定"——确保 Layer E 不会重复执行。在 v2 的 timer-based 架构中，`do_platform_register` 作为 daemon_loop 的一部分被单进程按周期触发，**天然不具备重复执行的条件**。无需额外的"唯一判定"编排。

> **修正后的归档理由**：v2 的单进程 timer-based 调度天然保证 Layer E 单次执行，不需要额外的编排去重逻辑。任务目标已由架构本身满足。

---

### ALV-002：rotate_log 竞态 → 降级 P3

| 维度 | Product 裁定 | 架构评审 |
|------|-------------|---------|
| **裁决** | 降级 P2→P3 | **同意 P3** |
| **理由** | 真实 bug，409h 零触发 | 补充架构分析 |

**代码分析（v2 L94–103）**：

```bash
rotate_log() {
    lc=$(wc -l < "${LOG_FILE}")        # ← 读取行数
    if [[ "${lc}" -gt "${MAX_LOG_LINES}" ]]; then
        tail -n "${KEEP_LOG_LINES}" "${LOG_FILE}" > "${LOG_FILE}.tmp"  # ← tail
        mv "${LOG_FILE}.tmp" "${LOG_FILE}"                              # ← mv
    fi
}
```

这是一个经典的 TOCTOU 竞态窗口：`wc -l` 和 `tail | mv` 之间没有原子性保证。如果两个 shell 进程同时执行 rotate（例如 daemon_loop 中的 rotate 和 log_msg 触发的并发写入），可能导致日志损坏或丢失。

**竞态窗口极窄的原因**：
1. rotate_log 只在 daemon_loop 的单进程中调用（L353），同一进程不会并发
2. 只有外部 `log_msg` 写入和 rotate 存在理论上的交叉，但两者通常不同时触发
3. MAX_LOG_LINES=2000，按 300s 间隔产生日志，达标需要大量时间

**架构建议**：将来修的时候，用 `flock` 包围整个 rotate 块即可（0.1h），比引入 logrotate 更轻量。

---

### ALV-003：restart lock rm -f → 保留 P2

| 维度 | Product 裁定 | 架构评审 |
|------|-------------|---------|
| **裁决** | 保留 P2 | **同意保留 P2** |
| **理由** | "lock 残留→启动失败→服务离线" | **风险描述需修正** |

**代码分析（v2 L209–232）**：

```bash
local RESTART_LOCK="${WORKSPACE}/.hermes_dashboard_restart_lock"
local RESTART_COOLDOWN=600
```

Product 说"supervisor 重启 keepalive → 发现残留 lock 文件 → 启动失败"。**这是不准确的。** 实际流程：

1. keepalive v2 异常 crash
2. supervisor `autorestart=true` → keepalive v2 **正常启动**
3. keepalive v2 执行 do_health_check，发现 Dashboard 不可达
4. 检查 lock 文件 → 发现残留（来自 crash 前的 restart）→ lock_age < 600s
5. **跳过本次 Dashboard 重启** → 等待下一个 HEALTH_INTERVAL (300s) 再试
6. 最坏情况：Dashboard 在 crash 后最多 **10 分钟** 才能被 auto-restart

**修正后的风险模型**：

| | Product 描述 | 实际 |
|---|---|---|
| **keepalive 启动** | 启动失败 ❌ | **正常启动** ✅ |
| **影响范围** | 全服务离线 | Dashboard 恢复延迟 ≤10min |
| **HCD 覆盖** | HCD 告警后人工介入 | HCD 在 180s 心跳停滞 + 5min 检查周期内告警 |

**真正的 blast radius**：Dashboard 最多 10 分钟不可用（而非 keepalive 完全起不来）。HCD watchdog 会在心跳超时后发飞书告警，但不会自动修复。

**结论不变但理由修正**：0.2h 投资仍然值得。正确做法是在 daemon_loop 启动时检查 lock 文件是否来自"本进程启动之前"——若是，则 `rm -f`。判断方式简单：在 `daemon_loop()` 入口处 `touch /tmp/.keepalive_start_ts`，若 lock mtime 早于启动时间戳，清理之。

**补充发现**：daemon_loop 的 trap handler（L311）只清理 PID_FILE，不清理 RESTART_LOCK。正常 shutdown 后残留的 lock 也会在下一次启动时造成不必要的 cooldown。此项也应一并修复。

---

### ALV-004：端口配置化 → 归档

| 维度 | Product 裁定 | 架构评审 |
|------|-------------|---------|
| **裁决** | 归档 | **同意归档** |

**架构判断**：Dashboard=9119, KeepAwake=8001 在当前部署模型下合理。如果未来需要多实例，**环境变量是最轻量的配置化方案**（`DASHBOARD_PORT=9119`），不是引入配置系统。但那是未来的事。当前不需要动。

---

### ALV-005：cron 监控 log 写入 → 归档

| 维度 | Product 裁定 | 架构评审 |
|------|-------------|---------|
| **裁决** | 归档 | **同意归档** |

**信号质量对比**：

```
log mtime 代理信号: log 有写入 ⟹ 间接推断进程活着
    vs
heartbeat mtime 直接信号: keepalive 显式写入心跳 ⟹ 直接证明进程活着
    vs
PID 存活: kill -0 ⟹ 最直接信号
```

HCD watchdog 使用 heartbeat mtime（每 5min 检查），这本身就是比 log mtime 更可靠的信号。再加一层 log mtime 监控是**冗余告警源**——降低信噪比，不增加覆盖。归档正确。

---

## Product 提案中缺失的架构风险

审查代码后，以下 3 项在 Product 的 5 项评估中没有被覆盖，属于架构盲区：

### 缺失 1：Layer E 声明冲突（MINOR，文档级）

Product 裁定声称 "keepalive v2 已无 Layer E"，但代码明确包含 `do_platform_register()`。这不影响裁定的实质正确性（因为任务目标确实已由架构满足），但**文档与代码的不一致会在未来造成混淆**。建议在裁定文档中补充更正注释。

### 缺失 2：graceful shutdown 不清理 restart lock（MINOR）

daemon_loop 的 trap 只清理 PID_FILE：
```bash
trap 'log_msg "STOP" "Keepalive v2 shutting down (signal)"; rm -f "${PID_FILE}"; exit 0' SIGTERM SIGINT
```

不清理 `RESTART_LOCK`。这意味着即使用 `keepalive_v2.sh stop` 正常停止，下次启动后的 10 分钟内 Dashboard 也无法被 auto-restart。这是 ALV-003 修复的自然延伸——修复 ALV-003 时应一并处理此问题。

### 缺失 3：HCD watchdog 监控间隔与心跳阈值不匹配（OBSERVATION）

- HCD watchdog crontab: `*/5 * * * *`（每 5 分钟）
- 心跳过期阈值: `STALE_SECONDS=180`（3 分钟）
- 最坏检测延迟: 心跳在 cron 检查刚过后停滞 → 5 分钟后才被检测 → 此时心跳已停滞 8 分钟

这不是 bug，而是正常的轮询延迟。但如果希望告警更快，可以将 crontab 改为 `*/2 * * * *` 或让 watchdog 本身 daemon 化（当前 Product 方案 C 已有此讨论）。**当前不属于 action item，仅记录**。

---

## 总结

| ID | Product | Architect | 一致？ | 备注 |
|:---:|:---:|:---:|:---:|------|
| ALV-001 | 归档 | ✅ 归档 | ⚠️ | 同意结论，但理由需修正：Layer E 存在，只是不需要额外编排 |
| ALV-002 | 降级 P3 | ✅ P3 | ✅ | 真实竞态，极窄窗口。修时建议用 flock |
| ALV-003 | 保留 P2 | ✅ P2 | ⚠️ | 同意结论，但 blast radius 被高估：不是"起不来"而是"Dashboard 恢复延迟 ≤10min" |
| ALV-004 | 归档 | ✅ 归档 | ✅ | 完全一致 |
| ALV-005 | 归档 | ✅ 归档 | ✅ | 完全一致 |

**架构裁决**：Product 裁定大方向正确，无需推翻。需修正 ALV-001 的归档理由和 ALV-003 的风险描述。补充 3 项缺失：Layer E 文档声明修正、graceful shutdown lock 清理、watchdog 间隔观察。

> **架构师一句话**：5 裁 5 确认，2 处理由纠偏，3 项盲区补充。保活 P2 从 5→1 的瘦身方向正确，不推倒重来。
