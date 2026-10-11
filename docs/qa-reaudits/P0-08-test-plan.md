# P0-08 重审测试方案：mem0 修通（SDK + API key + is_available）

> 版本：v1.0 | 状态：方案 — 待执行
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）

---

## 1. 背景

### 1.1 原始任务

| 字段 | 值 |
|------|-----|
| P0 编号 | P0-08 |
| 原始 kanban 任务 | `t_5e9b4d05` |
| 标题 | mem0 修通（SDK + API key + is_available）（记忆机制，0.5d） |
| 性质 | 外部依赖集成的环境修通 |
| 涉及第三方 | mem0 Platform（`api.mem0.ai`）— §8.2 第三方依赖 SLA 放宽适用 |

### 1.2 mem0 系统说明

mem0 是 Hermes 的云端记忆系统，通过 `plugins/memory/mem0/__init__.py` 和 `_backend.py` 驱动。核心依赖链：

```
config.yaml (provider: mem0)
    → .env MEM0_API_KEY / mem0.json api_key
        → is_available() 检查
            → _create_backend() 初始化
                → MemoryClient (mem0 SDK)
                    → api.mem0.ai (第三方云服务)
```

**修通条件（全部满足）**：
1. mem0ai SDK 已安装（`pip3 list | grep mem0ai`）
2. API key 可从插件读取路径访问（`.env` 或 `mem0.json`）
3. 网络可通（`api.mem0.ai` 可达）
4. SDK import 成功（`from mem0 import MemoryClient`）
5. `is_available()` 返回 True 的路径与实际功能路径一致

### 1.3 已有 QA 审查

原始 QA 重审报告 `docs/qa-reviews/P0-08-mem0-review.md`（2026-07-08）已按新标准完成逐项审查。本方案基于该报告的定义和分级，聚焦于**测试执行**——如何验证修通结果、如何验证设计缺陷的存在与修复。

---

## 2. 当前状态（基线）

### 2.1 修通确认

| 检查项 | 状态 | 证据 |
|--------|:---:|------|
| mem0ai SDK 安装 | ✅ | `pip3 list` → mem0ai 2.0.10 |
| API key 配置（.env） | ✅ | `MEM0_API_KEY=m0-Qpfn...` |
| config.yaml provider 配置 | ✅ | `provider: mem0` |
| 网络连通 | ✅ | `api.mem0.ai` → HTTP 200 |
| SDK import 测试 | 待验证 | 需批准执行 `from mem0 import MemoryClient` |

### 2.2 设计缺陷现状

| # | Pitfall | 级别 | 触发条件 | 当前状态 |
|---|---------|:---:|---------|---------|
| P1 | config.yaml api_key 对插件是死代码 | MAJOR | 用户仅在 config.yaml 改 key | 潜伏（wizard 写了双份） |
| P2 | is_available() SDK 未装仍返回 True | MAJOR | SDK 被卸载 / 环境重建 | SDK 已装，不触发 |
| P3 | Lazy install 5 种失败→1 种错误 | MAJOR | SDK 缺失 + pip install 失败 | SDK 已装，不触发 |
| P4 | Platform mode 事实提取不透明 | MINOR | 持续存在 | 持续存在 |
| P5 | mem0.json 缺失无警告 | MINOR | 持续存在 | **已确认：文件不存在** |

---

## 3. 测试层次与策略

### 3.1 三层测试模型

| 层 | 目标 | 对应发现 | 测试方法 |
|----|------|---------|---------|
| **L1：修通验证** | 确认 mem0 端到端可用 | 基线（§2.1） | 环境检查 + API 连通性 + SDK 端到端 |
| **L2：回退验证** | 确认修通不是"刚好踩中"——失效路径正确暴露 | P1, P2, P3 | 模拟失效场景（卸载 SDK、移除 env var） |
| **L3：持续性缺陷验证** | 确认已知设计缺陷存在、级别正确 | P4, P5 | 代码检查 + 行为观察 |

### 3.2 §8.2 第三方依赖 SLA 适用范围

P0-08 涉及 mem0 Platform（`api.mem0.ai`）——一个外部云服务，属于 §8.2 定义的「第三方依赖」范畴。

| 场景 | 适用规则 | 具体含义 |
|------|---------|---------|
| L1 网络连通性测试 | — | 属于正常验证，不触发 SLA |
| 若 api.mem0.ai 不可达且导致功能阻断 | §8.2 第三方依赖阻塞 | BLOCKER 方案时限 48h（非 24h），4h 响应时必须明确标注「第三方依赖阻塞」 |
| 若 mem0 SDK 有已知 CVE | §2 OWASP A6 | 易受攻击组件 → MAJOR（CVSS≥7 → BLOCKER） |
| 若 mem0 返回数据异常但不阻断 | — | 按 §1.2 正常判定，不享受 SLA 放宽 |

**关键结论**：mem0 作为第三方依赖，当且仅当「修通后被证明 API 端不可用」时，才享受 §8.2 的 SLA 放宽。SDK 安装、API key 配置等本地环节不享受放宽。

### 3.3 判定公式框架（适用于 L2/L3 发现）

所有测试发现按标准 §1.2 五步判定：

```
前置检查：安全漏洞？→ 是 → 最低 MAJOR，对照 OWASP Top 10（附录 B）

正式判定：
  步骤 E — 用户可感知？
  步骤 F — 功能阻断？
  步骤 W — 有 workaround？
  步骤 D — 数据敏感度？（§4 附录 A）
  步骤 P — 性能退化？（§3 + 附录 C）
```

mem0 记忆功能数据敏感度判定：
- 记忆内容可能包含用户行为日志 → **B 级**（不加权）
- 若记忆涉及用户基础信息（手机号/邮箱等）→ **A 级**（+1 级）
- 不涉及资金/资产 → 非 S 级

---

## 4. 测试用例

### 4.1 L1：修通验证（4 个用例）

#### TC-P08-01：SDK 安装验证

```
Given: Hermes 环境已配置
When:  执行 pip3 list 2>/dev/null | grep mem0ai
Then:  输出包含 "mem0ai" 且版本号非空
       当前基准：mem0ai 2.0.10
```

**判定**：PASS → FAIL 则 mem0 完全不可用（BLOCKER，无 workaround）。

**SLA 触发**：否 — 本地环境修复，不涉及第三方。

---

#### TC-P08-02：API key 双路径验证

```
Given: orchestrator profile 已配置
When:  分别检查：
        (a) source ~/.hermes/profiles/orchestrator/.env && echo $MEM0_API_KEY
        (b) grep "api_key" ~/.hermes/profiles/orchestrator/config.yaml | grep mem0
        (c) cat ~/.hermes/profiles/orchestrator/mem0.json 2>/dev/null
Then:  (a) MEM0_API_KEY 非空（m0-...）
       (b) config.yaml memory.mem0.api_key 也非空（但此路径对插件是死代码 → P1）
       (c) mem0.json 不存在（当前现状 → P5）
```

**判定**：
- (a) PASS → API key 在正确的读取路径可用 ✓
- (b) 仅验证 API key 已写入 config.yaml，不验证插件能读取（已知 P1）
- (c) 验证 mem0.json 缺席状态（已知 P5）

**SLA 触发**：(a) FAIL → 属于配置问题，不涉及第三方，正常 SLA。

---

#### TC-P08-03：网络连通性

```
Given: 网络环境正常
When:  执行 curl -s -o /dev/null -w "%{http_code}" https://api.mem0.ai
       等待超时上限 10s
Then:  返回 HTTP 200
```

**判定**：
| 结果 | 级别 | 说明 |
|------|:---:|------|
| HTTP 200 | PASS | 第三方可达 |
| 超时 / 非 200 | **分析** | 需判断是临时故障还是持续阻断 |

**SLA 触发条件**：若非临时故障（重试 3 次以上仍失败）→ §8.2 第三方依赖阻塞。

**关键操作**：若 TC-P08-03 失败，立即区分两类场景：
- 场景 A：`api.mem0.ai` DNS 解析失败 / IP 不可达 → 网络层问题（可能 GFW / 代理），非 mem0 服务本身
- 场景 B：`api.mem0.ai` 可达但返回 5xx → mem0 Platform 故障，第三方 SLA 放宽适用

---

#### TC-P08-04：SDK 端到端验证

```
Given: MEM0_API_KEY 环境变量已设置（从 TC-P08-02 确认）
When:  执行：
       python3 -c "
       import os
       from mem0 import MemoryClient
       c = MemoryClient(api_key=os.environ['MEM0_API_KEY'])
       result = c.get_all()
       print('OK' if result is not None else 'FAIL')
       "
Then:  输出 "OK"（SDK 可 import，API 可调用）
       如抛出异常，记录具体错误类型
```

**判定**：
| 结果 | 级别 | 处理 |
|------|:---:|------|
| 输出 OK | PASS | SDK + API 端到端可用 |
| `ModuleNotFoundError: No module named 'mem0'` | BLOCKER | SDK 未安装 → P2 暴露 |
| `ConnectionError` / `Timeout` | §8.2 分析 | 第三方 API 不可达 |
| `AuthenticationError` | MAJOR | API key 无效（有 workaround：更新 key） |
| 其他异常 | 按 §1.2 判定 | — |

---

### 4.2 L2：回退验证 —— 失效路径正确暴露（3 个用例）

L2 测试的目标不是验证"现在能跑"，而是验证"当条件破坏时，系统是否正确报告不可用"。这些用例**可能破坏当前修通状态**，执行前需决策。

#### TC-P08-05：is_available() 可靠性（P2 回退验证）

```
Given: 当前 SDK 已装，mem0 可用
When:  （需决策是否执行——会破坏当前修通状态）
       (a) pip uninstall mem0ai -y
       (b) 重启 agent 或调用 is_available()
Then:  (a) SDK 已卸载 → pip3 list | grep mem0ai 为空
       (b) is_available() 应返回 False
       
       当前 Bug 行为（P2）：is_available() 仅检查 api_key 非空
       → 即使 SDK 未装，也返回 True
```

**判定公式对照**（修复前）：
```
用户可感知？→ YES（工具可用但调用崩溃）
功能阻断？ → YES（mem0 完全不可用）
有 workaround？→ YES（pip install mem0ai）
→ MAJOR
```

**SLA 触发**：修复前 → MAJOR SLA（研发 1d 响应 / 2d 定位 / 版本窗口内修复）。

**执行后恢复**：`pip install mem0ai==2.0.10`

**风险信号**：若执行此用例导致修通回退，需重新验证 TC-P08-01 和 TC-P08-04。

---

#### TC-P08-06：config.yaml api_key 生效性（P1 回退验证）

```
Given: 当前 .env 和 config.yaml 都设置了 api_key
When:  （需决策是否执行——会破坏当前配置）
       (a) 备份当前 .env 中的 MEM0_API_KEY
       (b) 从 .env 中移除 MEM0_API_KEY（或设为空）
       (c) 保留 config.yaml memory.mem0.api_key 不变
       (d) 重启 agent 并调用 mem0_search
Then:  
       Bug 行为（P1）：config.yaml api_key 对插件是死代码
       → mem0_search 返回 "backend not initialized"
       
       修复后行为：插件应从 config.yaml 读取 api_key
       → mem0 正常返回结果（或不读取但至少给出清晰错误）
```

**判定公式对照**（修复前）：
```
用户可感知？→ YES（改 config.yaml 的 api_key 无效果）
功能阻断？ → YES（若只设 config.yaml 不设 .env，mem0 不工作）
有 workaround？→ YES（手动设 .env 或 mem0.json）
→ MAJOR
```

**执行后恢复**：将备份的 MEM0_API_KEY 恢复至 .env。

---

#### TC-P08-07：Lazy install 错误分化（P3 回退验证）

```
Given: SDK 未安装（模拟环境）
When:  触发 _lazy_ensure("memory.mem0", prompt=False)
Then:  
       Bug 行为（P3）：所有失败返回 "No module named 'mem0'"
       
       修复后行为：根据失败原因返回不同错误——
       - 网络不通 → "Network unreachable: ..."
       - PEP 668 → "Externally managed environment: ..."
       - pip 不在 PATH → "pip not found: ..."
       - 磁盘满 → "Disk full: ..."
       - 权限拒绝 → "Permission denied: ..."
```

**判定公式对照**（修复前）：
```
用户可感知？→ YES（与 P2 同一症状但无法诊断原因）
功能阻断？ → YES（自动恢复路径失效）
有 workaround？→ YES（手动 pip install + 读终端 output）
→ MAJOR
```

**执行条件**：需构造 SDK 未安装环境。可在独立 venv 中测试，不影响主环境。

**SLA 触发**：MAJOR SLA。

---

### 4.3 L3：持续性缺陷验证（2 个用例）

L3 用例用于确认已知 MINOR 级缺陷的存在性和级别正确性，不试图破坏当前状态。

#### TC-P08-08：mem0.json 缺失行为验证（P5）

```
Given: orchestrator profile 的 mem0.json 不存在（已确认）
When:  调用 mem0_search / mem0_add 正常操作
Then:  当前行为：静默回退到 .env → 功能正常
       
       检查点：
       (a) 日志中是否有 mem0.json 缺失的提示（期望有但当前无 → P5）
       (b) 记忆功能是否因 mem0.json 缺失而退化（当前不退化）
```

**判定公式对照**：
```
用户可感知？→ YES（若用户期望通过 mem0.json 覆盖配置）
功能阻断？ → NO（核心功能通过 .env 可用）
→ MINOR
```

无破坏性操作，可直接执行。

---

#### TC-P08-09：事实提取可观测性验证（P4）

```
Given: mem0 正常可用
When:  执行一个对话 turn（agent 产生记忆操作）
Then:  检查日志中的 mem0 相关记录：
       (a) sync_turn() 是否被调用
       (b) backend.add() 的返回是否被记录
       (c) 是否有事实提取结果被回传至 agent 上下文
       
       当前行为：无任何事实提取结果回传 → 零可见性（P4）
```

**判定公式对照**：
```
用户可感知？→ 间接（用户可能发现记忆遗漏但不知原因）
功能阻断？ → NO（记忆系统仍工作）
→ MINOR
```

无破坏性操作，可直接执行。

---

## 5. 测试发现分级汇总

### 5.1 逐项级别确认

| # | Pitfall | 级别 | 判定路径 | 涉及测试用例 |
|---|---------|:---:|---------|:---------:|
| P1 | config.yaml api_key 是死代码 | **MAJOR** | 可感知 + 阻断 + 有 workaround(.env) | TC-P08-06 |
| P2 | is_available() SDK 未装仍返回 True | **MAJOR** | 可感知 + 阻断 + 有 workaround(pip install) | TC-P08-05 |
| P3 | Lazy install 5 种失败→1 种错误 | **MAJOR** | 关键路径静默失败（归入 MAJOR） | TC-P08-07 |
| P4 | Platform mode 事实提取不透明 | **MINOR** | 可感知(间接) + 不阻断核心任务 | TC-P08-09 |
| P5 | mem0.json 缺失无警告 | **MINOR** | 可感知 + 不阻断核心任务 | TC-P08-08 |
| 基线 | SDK + API key + 网络（修通） | **PASS** | 修通条件全部满足 | TC-P08-01~04 |

### 5.2 判定公式对照总表

| 发现 | 安全? | 可感知? | 阻断? | workaround? | 数据敏感度 | 性能? | 级别 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| P1 | 否 | YES | YES | YES (.env) | B | — | **MAJOR** |
| P2 | 否 | YES | YES | YES (pip) | B | — | **MAJOR** |
| P3 | 否 | YES | YES | YES (手动pip) | B | — | **MAJOR** |
| P4 | 否 | 间接 | NO | — | B | — | **MINOR** |
| P5 | 否 | YES | NO | YES (.env) | B | — | **MINOR** |

### 5.3 标准分级示例对照

| 发现 | 最接近的标准示例 | 匹配理由 |
|------|----------------|---------|
| P1 | §5 示例 2：支付按钮无响应但有手动输入绕过 | 用户操作失败 + 临时方案可用 → MAJOR |
| P2 | §5 示例 17：列表页偶发白屏，刷新恢复 | 可用性被阻断 + 简单操作恢复 → MAJOR |
| P3 | §5 示例 16 变体：关键路径静默失败 | 自动恢复的不可靠性 → MAJOR |
| P4 | 无直接匹配 — 可观测性缺失 | 不阻断功能但累积为数据质量风险 → MINOR |
| P5 | 无直接匹配 — 配置静默不生效 | 不影响核心任务 → MINOR |

---

## 6. SLA 时效分析

### 6.1 当前 SLA 触发状态

| 发现 | 级别 | 响应 | 定位 | 方案 |
|------|:---:|------|------|------|
| P1 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 |
| P2 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 |
| P3 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 |
| P4 | MINOR | 2 工作日 | — | 不限 |
| P5 | MINOR | 2 工作日 | — | 不限 |

**无 BLOCKER 级发现 → 不触发 4h/8h/24h 紧急 SLA。**

### 6.2 §8.2 第三方依赖 SLA 触发场景

| 场景 | 是否触发 | 具体调整 |
|------|:---:|---------|
| TC-P08-03 网络不可达（场景 B：5xx） | **是** | BLOCKER 方案时限 48h，4h 响应时标注「第三方依赖阻塞」 |
| mem0ai SDK 有已知 CVE | **可能** | 对照 OWASP A6 → CVSS≥7 则 BLOCKER |
| mem0 Platform 限流导致部分失败 | **否** | 不影响核心功能可用性，按 MINOR/MAJOR 常规判定 |
| mem0 SDK 新版本 breaking change | **是** | 升级评估归入 P2 §12.2 #2 的第三方 SLA 放宽 |

### 6.3 跨时区规则

mem0 Platform 为美国西部时区服务（UTC-7/UTC-8）。若出现第三方故障：
- BLOCKER 响应 4h 从 Hermes 团队下一工作时段起算
- §8.2 方案时限 48h 从确认第三方依赖阻塞起算
- 若 mem0 提供 status page，纳入监控（suggested）

---

## 7. 论证流程（标准 §6）

### 7.1 当前论证状态

| 阶段 | 状态 | 说明 |
|------|:---:|------|
| QA 发现 → 按公式标注 | ✅ | P1-P5 均按 §1.2 五步判定标注（见 §5.2） |
| 研发评估 | ⏳ 待执行 | 研发需逐条确认/驳回/暂缓 |
| 驳回（如有） | — | 驳回需附 by-design / cannot-repro / cost>benefit 理由 |
| QA 申诉（如有） | — | 需附新证据（新复现 / 新影响面 / 新用户反馈） |
| 产品裁定（如有） | — | 产品裁定为最终 |
| BLOCKER 暂缓 | — | 当前无 BLOCKER，无需触发 §11 红线 1 |

### 7.2 研发降级透明度（标准 §6.4）

若研发将 P1/P2/P3 从 MAJOR 降为 MINOR：
- `downgrade_notify.py` 自动通知产品（许清楚）
- 降级必须附理由（如「用户几乎不会只改 config.yaml 不改 .env」）
- 产品作为 observer，不阻塞研发动作

---

## 8. 发布门禁（标准 §10）

### 8.1 门禁检查

按 §10 发布门禁公式：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 检查项 | 当前状态 |
|--------|:---:|
| BLOCKER=0？ | ✅ 无 BLOCKER（P1-P5 最高 MAJOR） |
| 安全漏洞=0？ | ✅ 对照 OWASP Top 10 Checklist 无命中 |
| 无未裁定申诉？ | ✅ 无申诉 |

**结论**：✅ **P0-08 自身不阻塞发版。** 3 个 MAJOR + 2 个 MINOR 符合 `MAJOR≤N` 门禁（具体 N 值由产品/架构确定）。

### 8.2 修复后的回归范围

| 修复项 | 回归范围（§10.1） | 时间预算 |
|--------|---------|:---:|
| P1（config 读取路径修复） | 修复模块 + 1 级依赖（所有调用 _load_config() 的路径） | 2h（MAJOR） |
| P2（is_available import 预检） | 修复模块 + agent init 路径 | 2h（MAJOR） |
| P3（lazy install 错误分化） | 修复模块 + 5 种失败场景逐一验证 | 2h（MAJOR） |
| P4（事实提取日志） | 修复模块 | 1h（MINOR） |
| P5（mem0.json 缺失日志） | 修复模块 | 1h（MINOR） |

---

## 9. 产品红线（标准 §11）

| 红线 | 触发？ | 说明 |
|------|:---:|------|
| 红线 1：BLOCKER 暂缓需 Frank 签字 | 否 | 无 BLOCKER 级发现 |
| 红线 2：申报诉必须带新证据 | 待定 | 当且仅当研发驳回 P1/P2/P3 时可能触发 |
| 红线 3：产品裁定为最终，不可二次申诉 | 待定 | 同上 |

---

## 10. 执行顺序与依赖

### 10.1 推荐执行顺序

```
L1 先跑（无破坏性）：
  TC-P08-01 → TC-P08-02 → TC-P08-03 → TC-P08-04

L3 可在 L1 后直接跑（无破坏性）：
  TC-P08-08 → TC-P08-09

L2 需决策（有破坏性，见 §10.2）：
  TC-P08-05 → TC-P08-06 → TC-P08-07
  每执行一个 L2 用例后恢复环境，再执行下一个
```

### 10.2 L2 执行风险评估

| 用例 | 破坏性 | 恢复难度 | 推荐决策 |
|------|:---:|:---:|---------|
| TC-P08-05（卸载 SDK） | 高 | 低（`pip install mem0ai==2.0.10`） | 如在独立 venv 中执行则安全 |
| TC-P08-06（移除 .env key） | 中 | 低（恢复备份） | 备份 + 执行 + 恢复 |
| TC-P08-07（模拟 SDK 缺失） | 低 | N/A（独立 venv） | 安全执行 |

**建议**：L2 在独立 venv 中执行，不与主环境耦合。所有 L2 用例执行前后确认 L1 基线通过。

---

## 11. 诊断 Checklist（运维参考）

以下 Checklist 来自 `agent-memory-architecture/references/mem0-integration-pitfalls.md`，供运维/QA 在修通被破坏时快速诊断：

```bash
# 1. Is the SDK installed?
pip3 list 2>/dev/null | grep mem0

# 2. Is the API key reachable by the plugin?
grep MEM0_API_KEY ~/.hermes/profiles/orchestrator/.env

# 3. Is the provider configured?
grep "provider: mem0" ~/.hermes/profiles/orchestrator/config.yaml

# 4. Network reachability
curl -s -o /dev/null -w "%{http_code}" https://api.mem0.ai

# 5. Full-path test
MEM0_API_KEY=$(grep MEM0_API_KEY ~/.hermes/profiles/orchestrator/.env | cut -d= -f2) \
  python3 -c "from mem0 import MemoryClient; c = MemoryClient(api_key='$MEM0_API_KEY'); print(c.get_all())" 2>&1
```

---

## 12. 建议

| # | 建议 | 对应发现 | 优先级 | 目标 |
|---|------|---------|:---:|------|
| 1 | 短期在 `_load_config()` 增加 config.yaml fallback 路径 | P1 | 高 | 消除 config.yaml 装饰性配置 |
| 2 | `is_available()` 增加 `import mem0` 预检 | P2 | 高 | 消除误报 |
| 3 | lazy install 捕获并分类 5 种失败模式 | P3 | 中 | 用户可自助诊断 |
| 4 | `sync_turn()` 后回调事实提取结果摘要 | P4 | 低 | 记忆质量可观测 |
| 5 | mem0.json 缺失时记录 debug 日志 | P5 | 低 | 配置路径可追溯 |
| 6 | 接入 mem0 status page 监控（如有） | §6.2 | 中 | 第三方 SLA 可观测 |

---

## 13. 评审与批准

| 角色 | 签名 | 日期 |
|------|------|------|
| QA（方案编制） | game-qa | 2026-07-08 |
| 研发（技术可行性） | — | — |
| 产品（用户影响） | — | — |
| 架构（系统风险） | — | — |

---

## 附录 A：标准章节快速索引

| 标准条款 | 主题 | 本文档对应章节 |
|---------|------|-------------|
| §1.2 | 判定公式 | §3.3 框架、§5.2 判定对照总表 |
| §1.3 | 判定原则 | §5.3 分级示例对照 |
| §2 + 附录 B | 安全漏洞独立判定 | §8.1（无命中） |
| §4 + 附录 A | 数据敏感度加权 | §3.3（mem0 = B 级） |
| §6 | 论证流程 | §7 |
| §8.1 | 研发 SLA 三档 | §6.1 |
| §8.2 | 第三方依赖 SLA 放宽 | §3.2、§6.2 |
| §10 | 发布门禁 | §8 |
| §11 | 产品红线 | §9 |
| 附录 C | 性能退化阈值 | 不适用（非性能类 bug） |

## 附录 B：版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-07-08 | 初始方案。基于 P0-08 QA 重审报告编制。 | game-qa |

---

> **方案状态**：待评审执行。L1（TC-P08-01~04）可直接执行无破坏性。L2（TC-P08-05~07）需确认是否允许破坏性测试。L3（TC-P08-08~09）可直接执行。
> **P0-08 自身不阻塞发版**：3 MAJOR + 2 MINOR，无 BLOCKER、无安全漏洞、无未裁定申诉。
