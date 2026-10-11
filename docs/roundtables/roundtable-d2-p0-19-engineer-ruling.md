# D2 Roundtable 工程评审 — P0-19 接力 cron/Watchdog 合并测试报告

> 角色：寇豆码（工程师） | 日期：2026-07-10
> 议题：D2 工程评审判定 — QA 最终报告分级与处置
> 依据：产品裁定 (roundtable-d2-p0-19-product-ruling.md) + 架构裁定 (roundtable-d2-p0-19-architect-ruling.md) + QA D2 陈述 (docs/qa-d2-statement-p0-19.md) + QA 测试报告 (docs/qa-test-report-p0-19-relay-watchdog-merge.md)
> 代码：relay_update.py (119行) / kanban_collector.py (327行) / game-engine SOUL.md §6 / orchestrator SOUL.md

---

## 执行摘要

**产品 + 架构裁定在代码层面完全成立。三项议题逐一确认，无需调整。**

- 分级合理：R-R3/R-R7 合并指向同一代码路径（`read_relay_state()` → `(None, None)` → relay 行缺失），不可分治
- 处置正确：MAJOR 观察期是 LLM 驱动的系统下唯一诚实策略；5 MINOR 每项已有代码级缓释
- 修复最优：D1 prompt fix（~6 行 SOUL.md，零代码改动）是当前架构约束下的最高 ROI 路径

**工程确认：产品裁定 3/3 议题全部成立。放行。**

---

## 议题 1: 分级合理性 — 工程视角

### 裁定：合理。1 MAJOR + 5 MINOR 分级准确。无异议。

### 1.1 R-R3/R-R7 合并为 1 个 MAJOR — 代码级确认

**合并理由在代码层面成立**。两个风险最终指向同一条故障路径：

```python
# kanban_collector.py L217-251 — read_relay_state()
# 情况 1: .oc_relay.json 存在但 updated_at 过期 (R-R3: LLM 忘记调用 relay_update.py)
# 情况 2: .oc_relay.json 根本不存在 (R-R7: LLM 行为与 SOUL.md 规则不一致)
# 
# 两种情况最终都走到:

if time.time() - updated_at > RELAY_STALENESS_SECONDS:  # L246
    return None, None                                    # L247

# → build_output() L291: if relay_phase: ...  # 跳过 relay 行
```

**为什么不可分治**：

- 修 R-R3（让 LLM 记住调用）= 修 R-R7（让 LLM 行为匹配 SOUL.md），反之亦然
- D1 stage -1/0 强制前置同时覆盖两者——不存在"只修一个不修另一个"的代码改动
- 产品 + 架构的合并裁定在代码层面零争议

**MAJOR vs BLOCKER — 代码级确认**：

```python
# build_output() 的输出结构：
# L271-273: 四维统计行         ← 核心功能，relay 无关
# L275-281: session 行          ← 核心功能，relay 无关  
# L283-288: stale warning 行    ← 核心功能，relay 无关
# L291-293: 🔄 接力: ...        ← relay 附加行，由 `if relay_phase:` 门控

# relay_phase 为 None 时，前三行照常输出。核心播报不受影响。
```

核心 kanban 播报不依赖 relay 状态。MAJOR 是正确的——这是体验退化（接力过程黑盒），不是功能阻断（看板仍播报）。不满足 BLOCKER 的任何触发条件（无安全漏洞、无数据一致性问题、无 crash、无 S 级数据）。

### 1.2 R-R5 降为 MINOR — 代码级确认

```python
# relay_update.py L33-38
RELAY_FILE = Path(
    os.environ.get(
        "WATCHDOG_RELAY_FILE",
        "/root/.hermes/profiles/orchestrator/scripts/.oc_relay.json",
    )
)
```

`RELAY_HELPER` 在 SOUL.md 中定义为 `/root/.hermes/profiles/orchestrator/scripts/relay_update.py`——绝对路径，不依赖 PATH。6/6 测试套件均通过绝对路径调用成功。

**这是运维配置问题，不是代码缺陷。** 当前部署环境 PATH 可达，未来部署环境变更时需同步更新 RELAY_HELPER 变量——这和修改 nginx.conf 中的 upstream 地址是同一类问题。MINOR 正确。

### 1.3 5 个 MINOR — 代码级逐项确认

| ID | 风险 | 代码级缓释 | 工程评估 |
|----|------|----------|---------|
| **R-R1** | 并发写冲突 | `atomic_write()` (L68-86): write .tmp → flush → fsync → os.rename。POSIX 保证 rename 在同一个文件系统上是原子的。两个 cron 同 tick 写时，最后 rename 者胜出，不产生半写文件。 | MINOR 正确。无锁设计在此场景下是正确的——加锁反而引入死锁风险和锁管理复杂度。 |
| **R-R2** | 读取时瞬态 rename | `read_relay_state()` (L224-234): 文件不存在 → `return None, None`；JSON 损坏 → `return None, None`。不崩溃。下个 tick（30s 后）自动恢复。 | MINOR 正确。best-effort 是正确模式。引入重试或等锁会增加 collector 复杂度，收益接近零。 |
| **R-R4** | OC 结束 relay 残留 | 双层防护：(1) SOUL.md 清理规则 —— OC 结束时删 .oc_relay.json；(2) staleness guard (L246) —— 过期 >10min 的 relay 不展示。 | MINOR 正确。双层防护已足够，再加 cron 清理脚本是过度设计。 |
| **R-R5** | PATH（降级后） | 绝对路径 6/6 套件可达。 | MINOR 正确。运维问题。 |
| **R-R6** | phase 枚举扩展 | collector 透传 phase (L249-251): `phase = state.get("phase", "unknown")` — 不校验、不崩溃。relay_update.py 写入端做白名单校验 (L39, L48-54)。 | MINOR 正确。**这是刻意设计的松耦合**——读端不验证、写端白名单。未来新增 phase 时 collector 零改动。 |

**工程层面无遗漏。** 所有缓释都在正确的代码层实现：文件层（原子 rename）、读取层（best-effort + staleness）、写入层（白名单校验）。

---

## 议题 2: 处置决策 — 工程视角

### 裁定：合理。MAJOR 观察期 + 5 MINOR P5，从实现角度完全成立。

### 2.1 MAJOR (R-R3/R-R7): 验收期观察 — 为什么这是唯一诚实策略

当前系统的核心事实：

```
OC orchestrator 是 LLM agent。
LLM 行为本质上是概率性的——没有 100% 保证。

relay_update.py 的调用依赖于 LLM 遵循 SOUL.md 提示。
这个依赖链无法通过代码消除——除非把 LLM 从 loop 中移除。
```

D1 fix 的工程策略是正确的——**概率压缩，不是概率消除**：

```
阶段 -1/0 强制前置  →  降低遗忘概率（"可能" → "极不可能"）
⚠️ 强制校验语言     →  提升 LLM 注意力权重
铁律 enforcement     →  增加违反成本（"跳过此步骤的 tick 将被视为违规"）
失败重试            →  覆盖瞬时调用失败
G-T1 staleness guard →  检测层：确实缺失时不展示过期数据
```

**无法通过静态测试完全验证 LLM 行为**——这是 LLM 系统的固有特性，不是测试覆盖不足。SOUL.md 合规 7/7 PASS 证明 prompt 结构正确，但不能证明 LLM 100% 遵循。观察期是数据驱动的风险验证——正确的做法。

**升级条件的工程合理性**：

```
升级条件: 连续 >3 周期无 relay 更新 → MAJOR→BLOCKER
```

- "连续 >3 周期"（非"任意 1 周期"）：避免单次 LLM 随机波动误报。3 周期 (~90s × 3 = ~270s) 足以区分偶发遗忘和系统性失效
- 代码级含义：3 个周期 × 每 tick 调 relay_update.py → 至少 3 次独立 LLM 决策都失败了 → 概率压缩不够 → 需要架构升级

### 2.2 P15（disk full 静默）→ MINOR — 代码级分析

relay_update.py 在磁盘满时：

```python
# relay_update.py L68-86
def atomic_write(path: Path, data: dict) -> None:
    tmp_path = path.with_suffix(".tmp")
    try:
        with open(tmp_path, "w") as f:       # ← 磁盘满 → OSError
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.rename(tmp_path, path)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)   # cleanup
        print(f"ERROR: atomic write failed: {e}", file=sys.stderr)  # ← stderr
        sys.exit(1)                            # ← exit 1
```

**不是"静默"失败**——exit code 1 + stderr 输出。如果 cron 的 terminal 工具忽略了 exit code，那是 cron 配置问题，不是 relay_update.py 的代码缺陷。

从工程角度：
1. 磁盘满是系统级故障，会影响所有文件写入——不仅 relay_update.py
2. relay_update.py 已经有正确的错误处理（exit 1 + stderr + cleanup）
3. 不需要在 relay_update.py 中加磁盘空间监控——这是运维监控的职责
4. **MINOR 判定正确**——代码本身没有缺陷，风险是运维层面的

### 2.3 架构建议：验收期加 relay 更新频率监控

架构师的自动化监控建议在工程上完全可行：

```python
# kanban_collector.py — 约 5 行新增
# 在 read_relay_state() 返回 (None, None) 时累加计数器
# 当计数器 > N 时在输出中加告警行

consecutive_stale = 0  # 新增

def read_relay_state():
    global consecutive_stale
    ...
    if time.time() - updated_at > RELAY_STALENESS_SECONDS:
        consecutive_stale += 1   # ← 新增
        if consecutive_stale >= 3:
            # 可选：在 build_output 中追加告警
            ...
        return None, None
    consecutive_stale = 0         # ← 新增：恢复归零
    ...
```

**改动量极小（~5 行），无破坏性风险，验收期内可实施。** 不阻塞当前发版。

### 2.4 5 MINOR → P5 — 工程确认

全部 5 项 MINOR 的"修复"会破坏现有代码的简洁性：

| ID | "修"的代价 | 为什么不应该修 |
|----|-----------|--------------|
| R-R1 | 加文件锁 | 引入锁管理、死锁风险、跨进程锁的复杂性。原子 rename 已经是 POSIX 标准解决方案。 |
| R-R2 | 加重试/等锁 | 增加 collector 复杂度。漏 1 tick 在下个 tick 自动恢复，收益为零。 |
| R-R4 | 加 cron 清理脚本 | 双层防护（SOUL.md 清理 + staleness guard）已足够。再加一层是过度设计。 |
| R-R5 | 改代码 | 运维问题不应在代码中解决。 |
| R-R6 | collector 加枚举校验 | 破坏刻意设计的松耦合。读端不验证是特性，不是缺陷。 |

**这些不是应该修的 bug——它们是正确的工程 tradeoff 的另一面。** P5 won't fix 正确。

---

## 议题 3: 修复路径 — 工程视角

### 裁定：强烈同意。D1 prompt fix 是最优路径。不升级为全功能改造。

### 3.1 三条路径的代码级比较

| 路径 | 机制 | 代码改动 | 能否消除风险 | 工程评估 |
|------|------|:---:|:---:|------|
| **A: D1 prompt fix**（当前） | SOUL.md 阶段 -1/0 强制前置 | 0 行代码（仅 SOUL.md ~6 行） | 不能（概率压缩至极低） | ✅ 最优。已完成，7/7 SOUL.md 合规 PASS。 |
| **B: 代码级钩子（LLM 触发）** | LLM agent 调用 pre/post hook 函数 | ~100-200 行 Python | 不能（与 A 同底限——仍需 LLM 调用） | ❌ 超额投资。ROI 趋近于零。 |
| **C: 独立钩子（shell wrapper）** | cron wrapper 层强制 relay | ~50 行 shell + 架构重构 | **能**（绕过 LLM） | ❌ 推翻方案 C。代价过高。 |

### 3.2 为什么 B 不行——代码级论证

路径 B 的"代码级钩子"本质上还是：

```python
# 伪代码 — 路径 B
def oc_orchestrator_tick():
    relay_pre_hook()        # ← 钩子
    llm_decision = call_llm(prompt)   # ← LLM
    relay_post_hook()       # ← 钩子
    execute(llm_decision)
```

这里有一个致命假设：**LLM agent 的代码框架会调用 `relay_pre_hook()`**。但在当前的 Hermes agent 架构中，LLM agent 没有"代码框架"——它的行为完全由 SOUL.md prompt 驱动。要让钩子生效，需要：

1. 修改 Hermes agent 核心循环（非项目代码，是框架代码）
2. 或者在 SOUL.md prompt 中加入"调用 relay_pre_hook()"——这又回到了路径 A

**路径 B 和路径 A 共享同一个不可突破的底限——LLM 是否遵循调用指令。** 100-200 行 Python 代码换不来任何额外的可靠性提升。

### 3.3 为什么 C 不行——架构代价

路径 C（shell wrapper pre-hook）：

```bash
# cron wrapper — 在每个 cron tick 前强制调用 relay
python3 relay_update.py polling "tick started"  # ← 强制前置
exec cron_agent "${prompt}"                       # ← LLM agent
```

这是唯一能彻底绕过 LLM 概率性的路径。但代价是：

- **推翻方案 C 的核心设计**——OC 不再是灵活的 LLM agent
- 每个 OC cron tick 无论是否需要 relay 都要调用 relay_update.py
- 失去 LLM 决策灵活性——OC 不能根据上下文跳过 relay（虽然目前不需要跳过）

**工程判断：C 的代价远超收益。** 方案 C 的核心价值（统一播报 + 消除重复扫描）不依赖 relay 行。为消除一个已压缩至极低的概率性风险而推翻整个架构设计，ROI 为负。

### 3.4 验收期观察 = 数据驱动决策

```
现在: D1 fix 已将风险压到极低 → 发布
3 周期后:
  ├── relay 正常 → MAJOR 闭环，投入 0
  └── relay 异常 → 带着真实失败数据评估是否需要路径 C
```

这是正确的工程节奏——先低成本降风险，再数据驱动定是否需要架构升级。不提前做超额投资。

---

## 工程师独立发现

### 发现 1：relay_update.py 代码质量良好

```python
# 119 行，职责单一，错误处理完整
- 原子写: write .tmp → flush → fsync → os.rename  ← 标准 POSIX 模式
- 写入端白名单校验: VALID_PHASES = frozenset({...})  ← 不可变集合
- 输入规范化: phase.strip().lower()                  ← 大小写容错
- detail 截断: max 60 字符，超长截断 + "..."         ← 防御性
- 错误恢复: except 块 cleanup tmp + exit 1           ← fail-safe
- JSON 验证输出: print(json.dumps(state))             ← LLM 可 grep
```

无代码异味。原子写实现与 collector 的 best-effort 读取形成正确的松耦合。

### 发现 2：collector read_relay_state 实现稳健

```python
# 多层防御:
L224:  文件不存在 → return None, None     # 不崩溃
L230-231: 文件为空 → return None, None    # 不崩溃
L233-234: JSON 损坏 → return None, None   # 不崩溃
L238-247: 过期 >10min → return None, None # staleness guard
L242-243: timestamp 支持 float/int/isoformat  # 向后兼容
L249-251: 未知 phase → 透传               # 松耦合
```

无崩溃路径。`best-effort + 降级` 模式实现正确。

### 发现 3：G-T2/G-T3/G-T4 验收期建议

架构师的 G-T2（relay schema 版本）/ G-T3（结构化日志）/ G-T4（幂等性）建议均为 MINOR，不阻塞发版。从工程角度：

- **G-T2 (schema version)**：`.oc_relay.json` 只有 3 个字段（phase / detail / updated_at），结构极度简单。加 schema version 在字段少于此数量前属于 premature optimization。但如果未来扩展字段，应该加。接受为 MINOR，验收期可选实施。
- **G-T3 (结构化日志)**：当前 stderr 输出已包含错误信息。加结构化日志（如 JSON 到 stderr）提升可诊断性但不改变行为。验收期实施合理。
- **G-T4 (幂等性)**：当前 relay_update.py 覆盖写（非追加），天然幂等——同 phase+detail 重复调用结果一致。不需要额外幂等保证。

---

## 发布门禁确认（工程视角）

对照 yaml §10：

```
BLOCKER = 0      ✅
MAJOR = 1        ✅  (远低于 3 上限)
安全漏洞 = 0      ✅
未裁定申诉 = 0    ✅
```

**工程门禁：通过。** D1 两项 FIX（G-T1 staleness guard + R-R3 relay 合规）均通过 QA 复测闭合。relay_update.py（119 行）+ kanban_collector.py（327 行）代码质量良好，无已知缺陷。

---

## 裁定记录

| 事项 | 产品 | 架构 | 工程师 | 结果 |
|------|:---:|:---:|:---:|------|
| R-R3/R-R7 分级合理性 | ✅ | ✅ | ✅ | 合理 — 1 MAJOR |
| R-R5 降级确认 | ✅ | ✅ | ✅ | 合理 — MINOR |
| 5 MINOR 分级 | ✅ | ✅ | ✅ | 合理 — MINOR |
| R-R3/R-R7 处置 | ✅ 观察期 | ✅ 观察期+监控 | ✅ 观察期+监控 | 不阻塞发版 |
| 5 MINOR 处置 | ✅ P5 | ✅ P5 | ✅ P5 | P5 won't fix |
| 修复策略 | ✅ D1 fix | ✅ 强确认 | ✅ 强确认 | 最优路径 |
| P15 (disk full) | — | — | ✅ MINOR | 代码有 exit 1 + stderr |
| 自动化监控建议 | — | 验收期实施 | ✅ 约 5 行代码 | 验收期实施 |
| 发布门禁 | ✅ 放行 | ✅ 放行 | ✅ 放行 | 三方一致 |

---

> **一句话工程裁定**：产品 + 架构裁定在代码层面完全成立。D1 prompt fix 是当前架构约束下的最高 ROI 路径——6 行 SOUL.md + 零代码改动，不推翻方案 C 的设计。relay_update.py（119 行）+ collector relay 集成（~50 行新增）代码质量良好，原子写 + best-effort 读形成正确的松耦合。MAJOR 维持观察期是 LLM 驱动系统下唯一诚实的策略——静态测试证 prompt 正确，观察期证行为正确。放行。

> **移交**：此裁定交 game-engine 执行发布。验收期建议：collector 加 relay frequency counter（~5 行）+ 可选 G-T2/G-T3（均为 MINOR，不阻塞发版）。
