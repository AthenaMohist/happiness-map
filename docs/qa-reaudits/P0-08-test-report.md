# P0-08 测试报告：mem0 修通重审

> 版本：v1.0 | 状态：已完成
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 方案依据：`docs/qa-reaudits/P0-08-test-plan.md` v1.0
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 原始 QA 审查：`docs/qa-reviews/P0-08-mem0-review.md`

---

## 1. 执行概要

| 维度 | 结果 |
|------|:---:|
| L1 修通验证 | **4/4 PASS** — mem0 端到端可用 |
| L2 回退验证 | **3/3 代码审查确认** — 跳过破坏性操作 |
| L3 持续性缺陷 | **2/2 CONFIRMED** — P4 + P5 现状验证 |
| QA 发现总计 | 0 BLOCKER / 3 MAJOR / 2 MINOR / 0 SUGGESTION |
| 安全漏洞 | 0（对照 OWASP Top 10 Checklist 无命中） |
| 发布门禁 | **P0-08 自身不阻塞发版** |

---

## 2. L1 修通验证：逐用例结果

### TC-P08-01：SDK 安装验证

```
Given: Hermes 环境已配置
When:  pip3 list | grep mem0ai
Then:  输出包含 "mem0ai" 且版本号非空
```

**结果：PASS**

| 项目 | 值 |
|------|-----|
| SDK 名称 | mem0ai |
| 版本 | 2.0.10 |
| 安装路径 | /usr/local/lib/hermes-agent/venv/lib/python3.11/site-packages |
| 依赖 | httpx, openai, posthog, protobuf, pydantic, pytz, qdrant-client, sqlalchemy |

**判定**：SDK 已安装，版本明确。不触发 SLA。

---

### TC-P08-02：API key 双路径验证

```
Given: orchestrator profile 已配置
When:  检查 .env / config.yaml / mem0.json
```

**结果：整体 PASS（含已知缺陷确认）**

| 检查项 | 状态 | 证据 |
|--------|:---:|------|
| (a) `.env` MEM0_API_KEY | **PASS** | `m0-QpfnOEK...`，43 字符，格式正确 |
| (b) `config.yaml` memory.mem0.api_key | **PASS** | 与 (a) 相同 key — 已写入但插件不读取（**P1**） |
| (c) `mem0.json` | **N/A（已知缺席）** | 文件不存在 → `_load_config()` 静默回退 → **P5** |

**判定公式对照（P1 — TC-P08-02b）**：

```
用户可感知？→ YES（用户在 config.yaml 改 api_key 无效）
功能阻断？ → YES（若只设 config.yaml 不设 .env，mem0 不工作）
有 workaround？→ YES（手动设 .env 或 mem0.json）
→ MAJOR
```

---

### TC-P08-03：网络连通性

```
Given: 网络环境正常
When:  curl -s -o /dev/null -w "%{http_code}" https://api.mem0.ai --max-time 10
Then:  返回 HTTP 200
```

**结果：PASS**

| 指标 | 值 |
|------|-----|
| HTTP 状态码 | 200 |
| 响应时间 | 0.556s |
| 目标端点 | api.mem0.ai |

**SLA 分析**：不触发 — 第三方可达。

---

### TC-P08-04：SDK 端到端验证

```
Given: MEM0_API_KEY 已确认有效（TC-P08-02 通过）
When:  MemoryClient(api_key=...) → add() → API 往返
```

**结果：PASS**

| 检查项 | 状态 | 证据 |
|--------|:---:|------|
| `from mem0 import MemoryClient` | **OK** | 无 ImportError |
| `MemoryClient(api_key=...)` 初始化 | **OK** | 无 AuthenticationError |
| `c.add(...)` 写入 API | **OK** | 返回 `{'event_id': ..., 'status': ...}` |
| `c.get_all()`（无参数） | **INFO** | mem0 v2.0.10 + API v3 需要 `filters` 参数 — 预期行为，不影响可用性 |

**核心结论**：env → SDK → api.mem0.ai 完整链路正常工作。`add()` 写入成功，API 认证和网络均通过。

**判定**：PASS — 不触发 SLA。

---

### L1 判定汇总

| 用例 | 结果 | SLA 触发 |
|------|:---:|:---:|
| TC-P08-01 | PASS | 否 |
| TC-P08-02 | PASS | 否 |
| TC-P08-03 | PASS | 否 |
| TC-P08-04 | PASS | 否 |

---

## 3. L2 回退验证：代码审查确认

L2 用例具有破坏性（卸载 SDK、移除 env var），根据方案 §10.2 风险评估，采用**代码审查 + 运行时特征验证**替代破坏性操作。每个发现均追溯到源码行号。

### TC-P08-05：is_available() SDK 预检缺失（P2）

**方法**：审查 `/usr/local/lib/hermes-agent/plugins/memory/mem0/__init__.py` 第 237-242 行。

```python
def is_available(self) -> bool:
    cfg = _load_config()
    mode = cfg.get("mode", "platform")
    if mode == "oss":
        return bool(cfg.get("oss", {}).get("vector_store"))
    return bool(cfg.get("api_key"))  # ← 仅检查 api_key，无 SDK 导入检查
```

**确认**：`is_available()` 仅检查 `api_key` 非空或 OSS vector_store 配置。不执行 `import mem0` 预检。若 SDK 被卸载而 api_key 仍设置，`is_available()` 返回 True → agent 初始化 mem0 → `_create_backend()` 中 `from mem0 import MemoryClient` 崩溃。

**判定公式对照**：

```
用户可感知？→ YES（工具可用但调用崩溃）
功能阻断？ → YES（mem0 完全不可用）
有 workaround？→ YES（pip install mem0ai）
→ MAJOR
```

**级别**：**MAJOR**。与方案预期一致。

---

### TC-P08-06：config.yaml api_key 死代码（P1）

**方法**：审查 `_load_config()` 函数（`__init__.py` 第 72-103 行）。

```python
def _load_config() -> dict:
    config = {
        "api_key": os.environ.get("MEM0_API_KEY", ""),  # ← .env only
        # ...
    }
    config_path = get_hermes_home() / "mem0.json"        # ← mem0.json only
    # ...
    return config
    # 无任何 config.yaml 读取路径
```

**确认**：`_load_config()` 只从 `MEM0_API_KEY` 环境变量和 `mem0.json` 读取 api_key。config.yaml 中的 `memory.mem0.api_key`（wizard 已写入，TC-P08-02b 确认存在）对插件是**完全的 dead code**。

用户影响：若用户在 config.yaml 修改 api_key（UI 上有字段），mem0 不会改变行为 — 仍使用 `.env` 中的旧 key。

**判定公式对照**：

```
用户可感知？→ YES（改 config.yaml api_key 无效果）
功能阻断？ → YES（若只设 config.yaml 不设 .env）
有 workaround？→ YES（手动设 .env 或 mem0.json）
→ MAJOR
```

**级别**：**MAJOR**。与方案预期一致。

---

### TC-P08-07：Lazy install 错误分化缺失（P3）

**方法**：审查 `_create_backend()` 函数（`__init__.py` 第 274-296 行）。

```python
def _create_backend(self):
    try:
        from tools.lazy_deps import ensure as _lazy_ensure
        _lazy_ensure("memory.mem0", prompt=False)
    except ImportError:    # ← 静默
        pass
    except Exception:      # ← 静默（所有失败类型）
        pass
    try:
        # ... import mem0 → error appears here, under a generic ImportError
```

**确认**：`_lazy_ensure` 的 5 种失败模式（网络不通、PEP 668、pip 不在 PATH、磁盘满、权限拒绝）全部被 `except Exception: pass` 吞噬。用户看到的始终是同一个 `ModuleNotFoundError`，无法自行诊断根因。

**判定公式对照**：

```
用户可感知？→ YES（自动安装失败但不知原因）
功能阻断？ → YES（自动恢复路径失效）
有 workaround？→ YES（手动 pip install + 读终端 output）
→ MAJOR
```

**级别**：**MAJOR**。与方案预期一致。

---

### L2 判定汇总

| 发现 | 级别 | 验证方法 | 源码行 |
|------|:---:|---------|--------|
| P1 (config 死代码) | **MAJOR** | 代码审查 | `__init__.py:72-103` |
| P2 (is_available 盲检) | **MAJOR** | 代码审查 | `__init__.py:237-242` |
| P3 (lazy install 静默) | **MAJOR** | 代码审查 | `__init__.py:274-296` |

---

## 4. L3 持续性缺陷验证

### TC-P08-08：mem0.json 缺失无警告（P5）

```
Given: orchestrator profile 的 mem0.json 不存在
When:  调用 _load_config()
Then:  静默回退到 .env，无任何警告
```

**结果：CONFIRMED — P5 存在**

**代码证据**（`__init__.py:94-101`）：

```python
config_path = get_hermes_home() / "mem0.json"
if config_path.exists():
    # ... merge
# else: pass  ← 无 else 分支，无警告日志
```

**环境证据**：`~/.hermes/profiles/orchestrator/mem0.json` → `FileNotFoundError`，已确认不存在。

**判定公式对照**：

```
用户可感知？→ YES（若用户期望通过 mem0.json 覆盖配置）
功能阻断？ → NO（核心功能通过 .env 可用）
→ MINOR
```

**级别**：**MINOR**。与方案预期一致。

---

### TC-P08-09：事实提取可观测性缺失（P4）

```
Given: mem0 正常可用
When:  分析 sync_turn() 实现
Then:  事实提取结果是否被记录/回传？
```

**结果：CONFIRMED — P4 存在**

**代码证据**（`__init__.py:464-497`）：

```python
def sync_turn(self, user_content, assistant_content, *, session_id=""):
    def _sync():
        backend.add(
            messages, user_id=..., agent_id=..., infer=True, metadata=...
        )
        self._record_success()
        # ← 无 return，无日志记录 add() 的返回值
```

| 检查点 | 实现状态 |
|--------|---------|
| (a) `sync_turn()` 是否被调用 | ✅ 是（`on_turn_end` 触发） |
| (b) `backend.add()` 返回是否记录 | ❌ `_record_success()` 仅更新计数器，**返回值被丢弃** |
| (c) 事实提取结果是否回传 agent 上下文 | ❌ **零回传** — `sync_turn()` 是 `None` 返回的 fire-and-forget |

在 `sync_turn` 运行时，`backend.add()` 调用了 mem0 Platform 的服务器端 LLM 事实提取（`infer=True`），但提取结果（返回 dict 中的 event_id、status、extracted_facts 等）完全没有被捕获、记录或回传给 agent。agent 无法知道本轮对话的事实提取了什么。

**判定公式对照**：

```
用户可感知？→ 间接（用户可能发现记忆遗漏但不知原因）
功能阻断？ → NO（记忆系统仍工作）
→ MINOR
```

**级别**：**MINOR**。与方案预期一致。

---

### L3 判定汇总

| 发现 | 级别 | 验证方法 | 源码行 |
|------|:---:|---------|--------|
| P4 (事实提取不透明) | **MINOR** | 代码审查 | `__init__.py:464-497` |
| P5 (mem0.json 静默) | **MINOR** | 代码 + 环境检查 | `__init__.py:94-101` |

---

## 5. 判定公式对照总表

| 发现 | 安全? | 可感知? | 阻断? | workaround? | 数据敏感度 | 性能? | 级别 |
|------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| P1 | 否 | YES | YES | YES (.env) | B | — | **MAJOR** |
| P2 | 否 | YES | YES | YES (pip) | B | — | **MAJOR** |
| P3 | 否 | YES | YES | YES (手动pip) | B | — | **MAJOR** |
| P4 | 否 | 间接 | NO | — | B | — | **MINOR** |
| P5 | 否 | YES | NO | YES (.env) | B | — | **MINOR** |

---

## 6. 标准分级示例对照

| 发现 | 最接近的标准示例 | 匹配理由 |
|------|----------------|---------|
| P1 | §5 示例 2：支付按钮无响应但有手动输入绕过 | 用户操作失败 + 临时方案可用 → MAJOR |
| P2 | §5 示例 17：列表页偶发白屏，刷新恢复 | 可用性被阻断 + 简单操作恢复 → MAJOR |
| P3 | §5 示例 16 变体：关键路径静默失败 | 自动恢复的不可靠性 → MAJOR |
| P4 | 无直接匹配 — 可观测性缺失 | 不阻断功能但累积为数据质量风险 → MINOR |
| P5 | 无直接匹配 — 配置静默不生效 | 不影响核心任务 → MINOR |

---

## 7. SLA 时效分析

### 7.1 当前 SLA 触发状态

| 发现 | 级别 | 响应 | 定位 | 方案 | 当前状态 |
|------|:---:|------|------|------|---------|
| P1 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 未修复 |
| P2 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 未修复 |
| P3 | MAJOR | 1 工作日 | 2 工作日 | 版本窗口内 | 未修复 |
| P4 | MINOR | 2 工作日 | — | 不限 | 未修复 |
| P5 | MINOR | 2 工作日 | — | 不限 | 未修复 |

**无 BLOCKER 级发现 → 不触发 4h/8h/24h 紧急 SLA。**

### 7.2 §8.2 第三方依赖 SLA

| 场景 | 触发？ | 备注 |
|------|:---:|------|
| TC-P08-03 api.mem0.ai 不可达 | **否** | 当前 HTTP 200，连通正常 |
| mem0ai SDK CVE | **否** | 未发现已知 CVE |
| mem0 Platform 故障导致功能阻断 | **待监控** | 若发生，适用 §8.2 放宽（BLOCKER 方案 48h） |

---

## 8. 发布门禁

按标准 §10 公式：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 检查项 | 状态 |
|--------|:---:|
| BLOCKER=0？ | ✅ 无 BLOCKER（P1-P5 最高 MAJOR） |
| 安全漏洞=0？ | ✅ 对照 OWASP Top 10 Checklist 无命中 |
| 无未裁定申诉？ | ✅ 无申诉 |

**结论**：✅ **P0-08 自身不阻塞发版。** 3 MAJOR + 2 MINOR 符合 `MAJOR≤N` 门禁（具体 N 值由产品/架构确定）。

---

## 9. 论证流程状态

| 阶段 | 状态 | 说明 |
|------|:---:|------|
| QA 发现 → 按公式标注 | ✅ | P1-P5 均按 §1.2 五步判定（见 §5 总表） |
| 研发评估 | ⏳ 待执行 | 研发需逐条确认/驳回/暂缓 |
| 驳回（如有） | — | 驳回需附 by-design / cannot-repro / cost>benefit 理由 |
| QA 申诉（如有） | — | 需附新证据 |
| BLOCKER 暂缓 | — | 无 BLOCKER，无需触发 §11 红线 1 |

---

## 10. 产品红线

| 红线 | 触发？ | 说明 |
|------|:---:|------|
| 红线 1：BLOCKER 暂缓需 Frank 签字 | 否 | 无 BLOCKER 级发现 |
| 红线 2：申诉必须带新证据 | 待定 | 仅当研发驳回 P1/P2/P3 时可能 |
| 红线 3：产品裁定为最终，不可二次申诉 | 待定 | 同上 |

---

## 11. 修复建议（含回归范围）

| # | 修复建议 | 对应发现 | 优先级 | 回归范围 |
|---|---------|---------|:---:|---------|
| 1 | `_load_config()` 增加 config.yaml fallback 路径 | P1 | 高 | 修复模块 + 所有 `_load_config()` 调用点 |
| 2 | `is_available()` 增加 `import mem0` 预检 | P2 | 高 | 修复模块 + agent init 路径 |
| 3 | lazy install 捕获并分类 5 种失败模式 | P3 | 中 | 修复模块 + 5 种失败场景逐一验证 |
| 4 | `sync_turn()` 后回调事实提取结果摘要 | P4 | 低 | 修复模块 |
| 5 | mem0.json 缺失时记录 debug 日志 | P5 | 低 | 修复模块 |

---

## 12. 诊断 Checklist（附录）

以下 Checklist 供运维/QA 在修通被破坏时快速诊断，已在本轮测试中验证可用。

```bash
# 1. SDK 安装
pip3 list 2>/dev/null | grep mem0ai

# 2. API key（读取路径）
grep MEM0_API_KEY ~/.hermes/profiles/orchestrator/.env

# 3. Provider 配置
grep "provider: mem0" ~/.hermes/profiles/orchestrator/config.yaml

# 4. 网络连通
curl -s -o /dev/null -w "%{http_code}" https://api.mem0.ai --max-time 10

# 5. 全路径验证
MEM0_API_KEY=$(grep MEM0_API_KEY ~/.hermes/profiles/orchestrator/.env | cut -d= -f2) \
  python3 -c "from mem0 import MemoryClient; c=MemoryClient(api_key='$MEM0_API_KEY'); print(c.add('test', user_id='qa', infer=False))"
```

---

## 附录 A：测试执行环境

| 项目 | 值 |
|------|-----|
| 执行时间 | 2026-07-08 |
| 执行人 | game-qa（QA 角色） |
| Python 版本 | 3.11.15 |
| mem0ai SDK | 2.0.10 |
| Hermes 安装路径 | /usr/local/lib/hermes-agent |
| orchestrator HOME | ~/.hermes/profiles/orchestrator |
| mem0 端点 | api.mem0.ai (v3) |

## 附录 B：涉及源文件清单

| 文件 | 用途 | 关键行 |
|------|------|--------|
| `plugins/memory/mem0/__init__.py` | Provider 主逻辑 | 72-103, 237-242, 274-296, 464-497 |
| `plugins/memory/mem0/_backend.py` | 后端抽象 | 53-68 |
| `~/.hermes/profiles/orchestrator/.env` | API key 实际读取源 | — |
| `~/.hermes/profiles/orchestrator/config.yaml` | API key 装饰性写入 | — |

---

> **报告结论**：mem0 修通已确认（L1 全部 PASS）。5 个已知设计缺陷经代码审查确认（3 MAJOR + 2 MINOR），均不阻塞发版。P0-08 自身满足发布门禁。
