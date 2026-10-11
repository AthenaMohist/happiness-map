# D1 R1: Architect Review — Watchdog v3.0 测试方案

> 评审人：高见远（架构师） | 日期：2026-07-10
> 被评审文档：`docs/qa-test-plan-p0-18b-watchdog-v3.md`（QA: 45 用例，5 套件）
> 架构基线：`docs/arch-p0-18b-watchdog-v3.md` v1.1
> PRD 基线：`docs/prd-p0-18b-watchdog-v3.md` v3.0
> 评审标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 1. 总体评价

QA 测试方案**结构良好**，45 个用例沿测试金字塔分层（TS1 单元 → TS5 边缘），与架构文档 §3-§10 形成清晰映射。测试数据准备脚本（附录 A/B）可直接执行，不是纸上谈兵。

**R-D1（「安排」定义冲突）是本次评审的核心发现——且 QA 正确将其列为 BLOCKER。**

三个关键问题需要解决，详见下文。

---

## 2. 覆盖率评估

### 2.1 覆盖矩阵（架构章节 ↔ 测试套件）

| 架构章节 | 对应测试 | 覆盖状态 |
|---------|---------|:---:|
| §3.1-3.5 Collector 伪代码 | TS1-01 ~ TS1-27 (27 用例) | ✅ 全面 |
| §5.1-5.5 Session file 协议 | TS2-01 ~ TS2-08 (8 用例) | ✅ 全面 |
| §8.4 旧文件清理 | TS3-01 ~ TS3-05 (5 用例) | ✅ 全面 |
| §4 + §9 Layer1+2 集成 | TS4-01 ~ TS4-05 (5 用例) | ✅ 核心路径覆盖 |
| §10 边缘场景矩阵 (E1-E12) | TS5-01 ~ TS5-12 | ✅ 一一对应 |
| §11 风险缓解 | §8 风险清单 (R-C1~R-I3) | ✅ 标注 |

### 2.2 已覆盖的关键路径

- ✅ 四维统计计算（安排/跑完/在跑/未跑）
- ✅ Session file 完整生命周期（创建→active→draining→删除）
- ✅ 崩溃恢复（残留文件 + TTL 过期）
- ✅ 原子写（.tmp → mv）
- ✅ 三层数据源读取（kanban.db / .oc_session.json / cron.db）
- ✅ 12 个边缘场景（E1-E12）全部有对应测试
- ✅ 旧文件清理（v2 残留）
- ✅ Reporter 集成链路（collector→reporter→Feishu）

### 2.3 覆盖缺口

以下为**测试方案层面**的覆盖缺口（非架构问题——架构问题见 §5）：

| ID | 缺口 | 影响范围 | 严重度 |
|----|------|---------|:---:|
| **G-T1** | 未测试 `session_started_at` 缺失/为 0 时「跑完」的 fallback 行为 | TS1-14 测了有值场景，未测无值 → 当前伪代码 fallback 到 `stats["done"]`（全部 done 任务） | MINOR |
| **G-T2** | 未测试 board 目录存在但无 kanban.db 的场景 | TS1-11 测了空目录，TS1-12 测了损坏 DB，但未测"目录存在/kanban.db 不存在"（伪代码 `if not db_path.exists(): continue` 覆盖但需验证） | MINOR |
| **G-T3** | 未区分 Reporter「首次 tick 空输出」vs「曾有输出后变空」 | TS4-02 测了正常告别路径，但未测 reporter 第一次运行就收到空输出的情况（理论上行为应一致，但值得验证 LLM 不会在首次就发告别） | MINOR |
| **G-T4** | 未测试 `next_one_shot_at` 优先级逻辑的单元层面 | 架构 §7.3 定义优先级：session 字段优先，cron.db fallback。TS1-18/19/20 只测了 cron.db 路径，`build_output` 接受 `next_cron` 参数但不体现优先级选择逻辑 | MINOR |

**结论**：4 个 MINOR 级覆盖缺口，不影响核心路径。建议在实现阶段补上，不阻塞当前。

---

## 3. 成功标准评估

### 3.1 逐套件检查

| 套件 | 成功标准 | 是否明确 | 评价 |
|------|---------|:---:|------|
| TS1 | 27 用例 PASS, 0 BLOCKER | ✅ | 明确，基于伪代码逐函数 |
| TS2 | 全部 PASS + 无僵尸 session file + 2 tick 内静默 | ✅ | 明确，有可量化指标 |
| TS3 | 旧文件确认不存在 + v2 cron 不引用旧脚本 | ✅ | 明确 |
| TS4 | 3 个完整周期 + 无僵尸 cron + reporter 不修改格式 | ✅ | "3 个周期"可量化 |
| TS5 | 边缘场景与架构 §10 对照表一致 | ✅ | 架构照搬，明确 |

### 3.2 发布门禁

对照 `qa-finding-classification.md §10`：

```
门禁条件: BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定申诉
当前状态: ❌ (1 BLOCKER + 6 MAJOR)
```

QA 正确执行了门禁检查。**但我对 MAJOR 计数有部分异议——见 §4**。

---

## 4. 风险等级评审

按 `qa-finding-classification.md §1.2` 五步判定公式逐条复核：

### 4.1 文档风险

| ID | QA 定级 | 架构复核 | 理由 |
|----|:---:|:---:|------|
| **R-D1** | BLOCKER | **BLOCKER ✅ 确认** | 用户可感知（Frank 看到数字）+ 功能阻断（定义不一致 → collector 输出错误）+ 无 workaround（只能等裁定）。**这是最紧急的阻塞项** |

> **架构立场声明**：架构设计「安排 = ready + running」（排除 blocked）是基于实战教训——blocked 任务往往是僵尸卡片，纳入「安排」会虚增工作量计数。产品说「安排是 OC 派发的任务池总量」，两者根本矛盾在于对 blocked 任务的管理语义理解不同。**需要 Frank 裁定。**

### 4.2 代码风险

| ID | QA 定级 | 架构复核 | 理由 |
|----|:---:|:---:|------|
| **R-C1** | MAJOR | **→ MINOR** | "OC LLM agent 行为不可靠"是架构**已知且已接受的 tradeoff**，已通过 TTL + SOUL.md 规则缓解。不是测试发现的缺陷，而是设计约束 |
| **R-C2** | MAJOR | **→ MINOR** | Stale session file 已有 TTL 600s 自愈机制 + collector 检测 + reporter 告别。三层防御，残留影响 → 最多额外一两条过期心跳，不造成持续性错误 |
| **R-C3** | MAJOR | **→ MINOR** | 僵尸 cron 已有**双重缓解**：idempotency_key + OC 启动清理 + Reporter 自删。OC 启动时主动删除旧 reporter cron 是架构 §6.1 的明确步骤 |
| **R-C4** | MINOR | **MINOR ✅ 确认** | SQLite 锁竞争，try/except + WAL 已缓解 |

### 4.3 集成风险

| ID | QA 定级 | 架构复核 | 理由 |
|----|:---:|:---:|------|
| **R-I1** | MAJOR | **MAJOR ✅ 确认** | Reporter 转发时可能修改格式——LLM 不可控，确有风险。Prompt 中明确指令"原文字符串不要修改格式"是正确的缓解但不是完全保证 |
| **R-I2** | MAJOR | **MAJOR ✅ 确认** | Reporter 自删失败风险确实存在（API 权限/网络瞬时故障）。OC 启动清理是防御措施但非 100% 可靠 |
| **R-I3** | MINOR | **MINOR ✅ 确认** | 多 OC 会话预留扩展，当前不处理 |

### 4.4 调整后的风险清单

| 级别 | 数量 | 项目 |
|:---:|:---:|------|
| BLOCKER | 1 | R-D1（「安排」定义冲突） |
| MAJOR | 3 | R-D2（cron.db 空）、R-I1（格式修改风险）、R-I2（自删失败） |
| MINOR | 4 | R-C1、R-C2、R-C3、R-I3（原 MAJOR 降级） + G-T1~G-T4（覆盖缺口） |

**调整后门禁检查**：BLOCKER=1 ❌ | MAJOR=3 ✅（≤3） | 安全=0 ✅ | 无未裁定申诉 ✅

**唯一阻塞项仍是 R-D1。**

---

## 5. 发现的架构自身缺陷

以下问题来自**测试方案审查过程中对照架构文档发现的不一致**，属于架构设计需修正的项，非 QA 测试方案问题：

### 5.1 A1:「下一轮启动时间」优先级未实现（架构 §7.3 vs 伪代码 §3.5）

架构 §7.3 定义了优先级：
> 1. `.oc_session.json` 的 `next_one_shot_at` 字段（OC 主动声明）
> 2. `cron.db` 的 one-shot jobs 的 `next_run_at`（collector 自行查询）

但伪代码 `read_next_cron()` **只实现了路径 2**（读 cron.db），完全没有读 session 的 `next_one_shot_at` 字段。`build_output()` 函数接受 `next_cron` 参数但不关心其来源。

**修正方案**：在 `read_session_state()` 返回的 session dict 中包含 `next_one_shot_at`，`main()` 中优先使用 session 字段，fallback 到 `read_next_cron()`。

```python
# main() 修改
session = read_session_state()
if not session:
    return

stats = scan_all_boards(session)
next_cron = session.get("next_one_shot_at") or read_next_cron()  # session 优先
```

**影响**：MINOR — 当前 cron.db 为空（R-D2），此优先级逻辑暂不可测试，但设计必须一致。

### 5.2 A2: Stale session 无差异化输出（架构 §7.2 vs 伪代码 §3.5）

架构 §7.2 示例输出中有：
```
⚠️ OC 最后活动: 12 分钟前 — 可能已静默
```

但伪代码 `read_session_state()` 在 TTL 过期时直接返回 `None`——与"session file 不存在"返回相同值。Reporter 无法区分"OC 从未启动"和"OC 崩溃/卡死"。

**修正方案**：`read_session_state()` 返回三种状态：

```python
def read_session_state():
    """Returns: (state_dict, 'active') | (stale_info_dict, 'stale') | (None, 'absent')"""
    if not SESSION_FILE.exists():
        return None, "absent"
    # ... parse ...
    if time.time() - updated_at > ttl:
        return {"status": "stale", "last_updated_at": updated_at, ...}, "stale"
    return state, "active"
```

然后 `main()` 在 stale 时输出警告格式的统计。这需要对应测试用例（TS5-03 需验证差异化输出）。

**影响**：MAJOR — 用户（Frank）无法区分"一切正常，OC 不在"和"OC 可能崩溃了"。

---

## 6. 架构评估结论

### 6.1 对 QA 测试方案的评价

| 维度 | 评分 | 说明 |
|------|:---:|------|
| 覆盖率 | ⭐⭐⭐⭐ | 核心路径全覆盖，4 个 MINOR 缺口 |
| 成功标准 | ⭐⭐⭐⭐⭐ | 每套件都有可量化标准 |
| 风险定级 | ⭐⭐⭐⭐ | 主要分歧在 R-C1/C2/C3 的 MAJOR→MINOR（见 §4） |
| 可执行性 | ⭐⭐⭐⭐⭐ | 附录脚本可直接跑，非纸上方案 |

### 6.2 核心决策点

```
❌ 不能进入实现的原因
└── R-D1: 「安排」定义冲突（架构 vs 产品）
    架构说: ready + running
    产品说: running + ready + blocked
    → 必须有 Frank 裁定
    
⚠️ 需要架构修正（先于或并行于实现）
├── A1: 下一轮优先级未实现
└── A2: Stale session 无差异化输出
```

### 6.3 建议路径

1. **立即**：Frank 裁定 R-D1（「安排」是否包含 blocked）
2. **R-D1 裁定后**：架构文档 v1.2 修正 A1 + A2
3. **架构修正后**：实现 Phase 1（kanban_collector.py + reporter cron）
4. **实现时**：补上 G-T1 ~ G-T4 覆盖缺口
5. **Phase 1 通过后**：Phase 2-5 逐步推进

---

> **架构结论**：测试方案质量良好，覆盖合理。一个 BLOCKER（R-D1，需产品裁定）+ 两个架构不一致（A1/A2，我负责修正）。MAJOR 数从名义 6 调整为实际 3，当前唯一真阻塞是「安排」定义冲突。

> **判定依据**：所有定级复核按 `docs/standards/qa-finding-classification.md` §1.2 五步判定公式执行。架构修正项按架构文档自身的设计一致性标准判定。
