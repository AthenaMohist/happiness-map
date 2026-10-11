# P0-12：Context Files 测试报告

> 版本：v1.0 | 状态：Completed | 测试日期：2026-07-08
> 测试执行人：game-qa（QA） | 原始任务：t_f1bf0a98
> 测试方案来源：`docs/qa-reaudits/P0-12-test-plan.md`
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 详细测试结果：`docs/qa-reaudits/P0-12-test-results.json`
> 测试脚本：`docs/qa-reaudits/p0-12-test-exec.py`

---

## 执行摘要

| 指标 | 数值 |
|------|:---:|
| 总测试用例 | 32 |
| **PASS** | 29 |
| **FAIL** | 3 |
| 通过率 | **90.6%** |
| BLOCKER 发现 | 0 |
| MAJOR 发现 | 1（已知 F2，未修复） |
| MINOR 发现 | 2（已知 F1/F3，未修复） |
| 新发现 | 1（F5：SOUL.md 含相同行数错误） |

**结论**：Hermes v0.18 Context Files 核心功能（文件发现、优先级、截断、安全防护、子目录发现）全部通过测试。3 个 FAIL 均为 devPPL `.hermes.md` 已知回归问题，非 Hermes 框架缺陷。建议修复 .hermes.md 后发版。

---

## 1. 测试环境

| 项目 | 详情 |
|------|------|
| Hermes 版本 | v0.18 (源码: /usr/local/lib/hermes-agent) |
| Context Files 实现 | `agent/prompt_builder.py` (1971 行) + `agent/subdirectory_hints.py` (270 行) |
| 安全扫描 | `tools/threat_patterns.py` (284 行, 43 个模式) |
| 测试仓库 | /workspace/devPPL（git 仓库） |
| SOUL.md | ~/.hermes/profiles/game-qa/SOUL.md (HERMES_HOME) |
| 默认截断 | CONTEXT_FILE_MAX_CHARS=20,000, Head=70%, Tail=20% |

---

## 2. 测试结果明细

### 2.1 功能测试：文件发现与优先级（TC-FUNC）

| ID | 场景 | 结果 | 详情 |
|----|------|:---:|------|
| TC-FUNC-01 | `.hermes.md` 最高优先级 | **PASS** | hermes.md 加载, AGENTS.md 被跳过 |
| TC-FUNC-02 | `AGENTS.md` 作为 fallback | **PASS** | AGENTS.md 正确作为 fallback 加载 |
| TC-FUNC-03 | `CLAUDE.md` 第三优先级 | **PASS** | CLAUDE.md 正确作为第三优先级加载 |
| TC-FUNC-04 | `.cursorrules` 兼容性 | **PASS** | .cursorrules 正确加载 |
| TC-FUNC-05 | 无任何 context file | **PASS** | 返回空字符串，无 Project Context block |
| TC-FUNC-06 | `HERMES.md` 大写变体 | **PASS** | HERMES.md 大写形式正确识别 |
| TC-FUNC-07 | 向 git root 搜索 | **PASS** | 子目录启动时正确找到 git root 的 .hermes.md |

**函数确认**：优先级链 = `_load_hermes_md()` → `_load_agents_md()` → `_load_claude_md()` → `_load_cursorrules()`，首匹配即停止（prompt_builder.py:1954-1959）。

**会话验证**：当前 game-qa session 的 Project Context block 已正确加载 `.hermes.md`。

### 2.2 边界测试：文件大小与截断（TC-EDGE）

| ID | 场景 | 结果 | 实测数据 |
|----|------|:---:|---------|
| TC-EDGE-01 | 文件未超限 (<20,000) | **PASS** | 15,000 chars → 完整加载，0 截断 |
| TC-EDGE-02 | 文件等于限制 (=20,000) | **PASS** | 使用 `<=` 判断，20,000 chars 未触发截断 |
| TC-EDGE-03 | 文件超限 (>20,000) | **PASS** | 30,000 chars → Head 14,000 + Tail 4,000 + marker = 18,178 chars |
| TC-EDGE-04 | 空文件 (0 bytes) | **PASS** | `_truncate_content("")` → 返回空字符串 |
| TC-EDGE-05 | 仅含空白字符 | **PASS** | 空白正常处理，不崩溃 |
| TC-EDGE-06 | 二进制/非 UTF-8 | **PASS** | 非 UTF-8 字节 → `read_text(encoding="utf-8")` 抛异常被 catch，返回空 |
| TC-EDGE-07 | 超大文件 (>1MB) | **PASS** | 1,100,000 chars → 截断为 18,180 chars，无 OOM |
| TC-EDGE-08 | 自定义 max_chars=5,000 | **PASS** | 8,000 chars → 按 5,000 截断，结果 4,676 chars |

**截断公式验证**：`head = max_chars * 0.7` + `tail = max_chars * 0.2` + marker。实测与公式一致。

### 2.3 安全测试：Prompt Injection 防护（TC-SEC）

| ID | 场景 | 结果 | 拦截模式 |
|----|------|:---:|---------|
| TC-SEC-01 | HTML 隐藏注入 (`display:none`) | **PASS** | `prompt_injection` + `hidden_div` |
| TC-SEC-02 | 指令覆盖 (`<!-- ignore previous instructions -->`) | **PASS** | `prompt_injection` + `html_comment_injection` |
| TC-SEC-03 | 凭证窃取 (`curl ... $API_KEY`) | **PASS** | `exfil_curl` |
| TC-SEC-04 | 凭证文件读取 (`cat .env`) | **PASS** | `read_secrets` |
| TC-SEC-05 | 合法内容不误拦截 | **PASS** | "Follow these instructions" + "Run tests" 正常通过 |
| TC-SEC-06 | SOUL.md 同样受扫描 | **PASS** | load_soul_md() 调用 _scan_context_content(soul_content, "SOUL.md") |
| TC-SEC-07 | Unicode 编码绕过 (NFKC) | **PASS** | 全角 `ｃａｔ .env` → NFKC 归一到 `cat .env` → 被 `read_secrets` 拦截 |
| TC-SEC-07-INVIS | 不可见 Unicode 字符 | **PASS** | U+200B (zero-width space) + U+200C (zero-width non-joiner) 被检测 |

**安全扫描范围**：context scope (35 模式) — 覆盖经典注入、C2/promptware、身份劫持、凭证窃取。strict scope (额外 7 模式) 仅用于 memory/skills。

**NFKC 归一化**：已实现 Unicode 全角→半角归一化，有效防御同形字符绕过（threat_patterns.py:245）。注意：不包括跨脚本混淆（Cyrillic а vs. Latin a）。

### 2.4 渐进式子目录发现（TC-SUBDIR）

| ID | 场景 | 结果 | 详情 |
|----|------|:---:|------|
| TC-SUBDIR-01 | 访问子目录触发发现 | **PASS** | `read_file("frontend/main.ts")` → 发现 `frontend/AGENTS.md` |
| TC-SUBDIR-02 | 向上搜索父目录 | **PASS** | `read_file("backend/src/main.py")` → 向上发现 `backend/AGENTS.md` |
| TC-SUBDIR-03 | 每个子目录仅检查一次 | **PASS** | 第二次访问 frontend/ → 返回 None（`_loaded_dirs` 去重） |
| TC-SUBDIR-04 | 子目录无 context file | **PASS** | 空目录访问 → 返回 None |
| TC-SUBDIR-05 | 子目录文件也过安全扫描 | **PASS** | `lib/AGENTS.md` 含注入 → 显示 `[BLOCKED: ...]` |

**实现确认**：`SubdirectoryHintTracker` 监控 path/workdir/file_path 参数 + terminal 命令中的路径 token。向上最多搜索 5 层祖先目录。每目录 8,000 chars 上限（不同于启动时的 20,000）。

### 2.5 回归测试：已知 devPPL `.hermes.md` 问题（TC-REGRESS）

| ID | Finding | 结果 | 级别 | 详情 |
|----|:---:|:---:|:---:|------|
| TC-REGRESS-01 | F1: 行数引用错误 | **FAIL** | MINOR | `.hermes.md` 标注 433 行，实际 436 行。偏差 3 行 |
| TC-REGRESS-02 | F2: 发布门禁缺 MAJOR≤N | **FAIL** | MAJOR | 门禁行只有 `BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉` |
| TC-REGRESS-03 | F3: defer.py 未列入 | **FAIL** | MINOR | 列出 5 脚本，实际 scripts/ 有 6 个 .py（含 defer.py） |
| TC-REGRESS-04 | F4: "五步判定公式"表述 | **PASS** | SUGGESTION | `.hermes.md` 提及 "五步判定公式"。实际 §1.2 为 "前置检查 → 正式判定(BLOCKER/MAJOR/MINOR/SUGGESTION)" 两阶段而非五步。表述可更精确但功能正确 |

---

## 3. 新发现

### Finding F5：SOUL.md 也含行数引用错误

| 维度 | 内容 |
|------|------|
| **问题描述** | `~/.hermes/profiles/game-qa/SOUL.md` 第 28 行标注 `qa-finding-classification.md` 为 "435 行"，实际 436 行 |
| **判定路径** | Step1: 非安全漏洞 → Step2: 用户不可感知（SOUL.md 为 agent 内部 identity，不影响用户）→ SUGGESTION |
| **新标准级别** | **SUGGESTION** |
| **判定公式对照** | 用户不可感知 → SUGGESTION |
| **SLA 对照** | SUGGESTION: 研发 3 工作日响应 |
| **修复建议** | 将 SOUL.md 中 "435 行" 更新为 "436 行" 或移除具体数字 |
| **影响范围** | SOUL.md 仅影响 game-qa profile 的 system prompt，不影响其他 profile |

### 观察：scripts/ 目录存在未文档化的脚本

scripts/ 目录实际包含 9 个文件：`appeal.py`, `appeal_tracker.py`, `defer.py`, `dev_reject.py`, `downgrade_notify.py`, `product_rule.py`, `p11-hex-check.py`, `p11-scan-v2.py`, `p11-scan.py` + `README.md`。其中 `p11-*.py` 三个文件不属于申诉机制脚本，建议单独文档说明或纳入项目规范。

---

## 4. 综合级别统计

| 级别 | 数量 | 涉及 Finding |
|------|:---:|-------------|
| **BLOCKER** | 0 | — |
| **MAJOR** | 1 | F2（发布门禁公式缺 MAJOR≤N） |
| **MINOR** | 2 | F1（行数引用 433→436）、F3（defer.py 未列入） |
| **SUGGESTION** | 2 | F4（表述精确化）、F5（SOUL.md 行数） |

### 4.1 发布门禁影响

| 条件 | 状态 |
|------|:---:|
| BLOCKER = 0 | ✅ 通过 |
| 安全漏洞 = 0 | ✅ 通过 |
| MAJOR = 1 (F2) | ⚠️ 建议修复后发版，或发版时标注 known issue |
| 无未裁定的申诉 | ✅ 通过 |

---

## 5. 风险矩阵验证

| # | 原始风险 | 测试覆盖 | 验证结果 |
|---|---------|---------|:---:|
| R1 | Context file 过大导致启动变慢 | TC-EDGE-03/07 | ✅ 截断机制正常，1MB+ 文件不导致 OOM |
| R2 | Prompt injection 扫描漏网 | TC-SEC-01~07 | ✅ 8/8 安全测试通过，NFKC 归一化有效 |
| R3 | 优先级行为与预期不符 | TC-FUNC-01~04 | ✅ 优先级链正确：hermes.md > AGENTS.md > CLAUDE.md > .cursorrules |
| R4 | 子目录发现过于频繁 | TC-SUBDIR-03 | ✅ 去重逻辑正常，每目录仅加载一次 |
| R5 | .hermes.md 内容错误 | TC-REGRESS-01~04 | ⚠️ 3/4 已知问题未修复 |
| R6 | 非 git 仓库场景 | 代码审查 | ⚠️ `_find_git_root()` 返回 None 时仅搜索 CWD，fallback 已实现 |

---

## 6. 代码审查发现

通过直接审查 Hermes 源码 (`/usr/local/lib/hermes-agent/agent/prompt_builder.py` + `subdirectory_hints.py` + `tools/threat_patterns.py`)，确认以下实现细节：

1. **优先级链**：`build_context_files_prompt()` 使用 `or` 短路，首匹配即停止。与文档一致。
2. **Git root 搜索**：`_find_hermes_md()` 从 CWD 向 git root 逐级搜索。无 git 仓库时仅检查 CWD。
3. **安全扫描**：context scope 下匹配 35 个模式（含 8 个 "all" 范围模式）。SOUL.md 同受保护。
4. **截断逻辑**：使用 `<=`（而非 `<`），20,000 恰好在边界时不触发截断。
5. **子目录发现**：`SubdirectoryHintTracker._MAX_HINT_CHARS` = 8,000（独立于启动时的 20,000）。向上最多搜索 5 层祖先。仅限 working_dir 子树内。
6. **动态截断**：`_dynamic_context_file_max_chars()` 对大规模上下文窗口自动扩大上限（最大 500,000 chars），但 config.yaml 显式设置优先。
7. **Unicode 安全**：NFKC 归一化在正则扫描前执行（threat_patterns.py:245），可拦截全角混淆但无法拦截跨脚本同形字（Cyrillic/Latin）。

---

## 7. 修复建议

### 高优先级（MAJOR — 建议修复后发版）

| Finding | 文件 | 当前内容 | 修复为 |
|---------|------|---------|--------|
| F2 | `.hermes.md` L20 | `BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉（§10）` | `BLOCKER=0 AND MAJOR≤N AND 安全漏洞=0 AND 无未裁定的申诉（§10）` |

### 中优先级（MINOR — 不阻塞发版）

| Finding | 文件 | 修复 |
|---------|------|------|
| F1 | `.hermes.md` L8 | `（v1.0，433 行）` → `（v1.0，436 行）` |
| F3 | `.hermes.md` §申诉机制 | 添加 `- defer.py：研发降级通知脚本` |

### 低优先级（SUGGESTION）

| Finding | 文件 | 修复 |
|---------|------|------|
| F4 | `.hermes.md` L14 | "五步判定公式" → "二阶段判定公式（前置检查 → 正式判定）" |
| F5 | `~/.hermes/profiles/game-qa/SOUL.md` L28 | "435 行" → "436 行" 或移除具体数字 |

---

## 8. 附录

### A. 测试脚本

完整测试脚本位于 `docs/qa-reaudits/p0-12-test-exec.py`（476 行），可通过以下命令复现：

```bash
cd /workspace/devPPL && PYTHONPATH=/usr/local/lib/hermes-agent python3 docs/qa-reaudits/p0-12-test-exec.py
```

### B. 结果数据

结构化测试结果位于 `docs/qa-reaudits/P0-12-test-results.json`（32 条记录）。

### C. 相关实现文件

| 文件 | 路径 | 行数 |
|------|------|:---:|
| Prompt Builder | `/usr/local/lib/hermes-agent/agent/prompt_builder.py` | 1,971 |
| Subdirectory Hints | `/usr/local/lib/hermes-agent/agent/subdirectory_hints.py` | 270 |
| Threat Patterns | `/usr/local/lib/hermes-agent/tools/threat_patterns.py` | 284 |

---

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1.0 | 2026-07-08 | 初始测试报告。32 用例执行完毕，29 PASS / 3 FAIL。核心功能全部通过，3 FAIL 为已知 .hermes.md 回归问题。新发现 F5（SOUL.md 行数错误）。 |
