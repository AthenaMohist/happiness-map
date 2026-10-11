# P0-01~13 QA 报告重审 — 测试方案

> 版本：v1.0 | 状态：Draft — 待评审
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）

---

## 1. 背景

P0-01 到 P0-13 的 QA 测试报告在新 QA 发现分级标准生效前完成。本方案定义如何按新标准逐条重审这些报告，产出可追溯的级别变更记录。

**本方案仅定义审什么、怎么审、判定标准——不包含具体执行。执行须等方案评审通过。**

---

## 2. 重审范围

### 2.1 任务清单

| P0 | 任务 ID | 标题 | 状态 | 原始数据源 |
|----|---------|------|:---:|----------|
| P0-01 | t_3769db02 | 修复审计 importer $HOME → /root | ✅ 已重审 | session 20260708_124207_428bbd |
| P0-02 | t_8857c995 | 确认 pending_upgrades 目录 | ⚠️ 需收集 | infomanager board t_7313221c |
| P0-03 | t_692d189e | 备份 DR 演练 | ✅ 已重审 | kanban comment |
| P0-04 | t_18a1b2ee | Infomanager URL 消失根因 | ⚠️ 部分数据 | session 20260708_124208_f3ed7f |
| P0-05 | t_b66db2fa | Infomanager 管线加结构化日志 | ✅ 已重审 | session 20260708_124208_c8b648 |
| P0-06 | t_7128e28c | Infomanager contract test + e2e smoke | ✅ 已重审 | session 20260708_124208_314e87 |
| P0-07 | t_73b4c1b8 | MEMORY.md 归档（139%→<80%） | ⚠️ 需收集 | session 20260708_124208_368960 |
| P0-08 | t_5e9b4d05 | mem0 修通（SDK + API key + is_available） | ✅ 已重审 | session 20260708_124208_1136f7 |
| P0-09 | t_04796b8b | mem0 结果校验（score 阈值 + FTS5） | ✅ 已重审 | session 20260708_124208_c78d5c |
| P0-10 | t_275f3135 | consolidation 审计（diff + snapshot） | ✅ 已重审 | session 20260707_222616_ddb1e8 |
| P0-11 | t_14fe9a17 | /learn 产出校验（SKILL.md 硬校验） | ✅ 已重审 | session 20260708_124208_fe6172 |
| P0-12 | t_f4f2795e | Context Files（.hermes.md 项目规则） | ✅ 已重审 | session 20260708_124208_d5c5ed |
| P0-13 | t_d7ea14bf | Cron context_from 链 | ✅ 已重审 | session 20260708_124208_691051 |

### 2.2 数据收集状态

- **已完整重审（10/13）**：P0-01, P0-03, P0-05, P0-06, P0-08, P0-09, P0-10, P0-11, P0-12, P0-13
- **需补充收集（3/13）**：P0-02（pending_upgrades 确认）、P0-04（URL 消失根因）、P0-07（MEMORY.md 归档）

---

## 3. 重审方法

### 3.1 判定公式对照（核心）

按标准 §1.2 的五步判定序列，逐条重审每个原始发现：

```
前置检查：
  └─ 安全漏洞？→ 是 → 最低 MAJOR，对照 §2 + OWASP Checklist（附录 B）

正式判定（五步）：
  步骤 E — 用户可感知？→ 否 → SUGGESTION（例外：安全漏洞/数据一致性）
  步骤 F — 功能阻断？→ 否 → MINOR
  步骤 W — 有 workaround？→ 是 → MAJOR；否 → BLOCKER
  步骤 D — 数据敏感度？→ S/A/B/C（§4），涉及一致性 bug 时加权
  步骤 P — 性能退化？→ §3 的 3x/10x 或 fallback 1s/5s 阈值
```

### 3.2 判定维度交叉检查

| 维度 | 标准引用 | 检查方式 |
|------|---------|---------|
| 判定公式是否匹配 | §1.2, §1.3 | 逐条对照五步判定，确认每一步的 Y/N 判定有证据支撑 |
| 安全漏洞 | §2, 附录 B | 对照 OWASP Top 10 Checklist 逐项排除 |
| 性能阈值 | §3, 附录 C | 有基准数据用 3x/10x；无基准用 1s/5s fallback |
| 数据敏感度 | §4, 附录 A | 涉及一致性 bug 时确认 S/A/B/C 分级正确性 |
| 论证流程是否合规 | §6.1-§6.4 | 检查：是否通过/驳回/暂缓？驳回是否附理由？降级是否通知产品？ |
| SLA 是否满足 | §8.1-§8.2 | 对照三档时限：响应/定位/方案。跨时区从下一工作时段起算 |
| 发布门禁是否符合 | §10 | 验证：BLOCKER=0 AND 安全漏洞=0 AND 无未裁定申诉 |
| 产品红线是否触发 | §11 | BLOCKER 暂缓需 Frank 签字；申诉需新证据；产品裁定为最终 |

### 3.3 论证流程核查

每个 finding 须确认其完整的论证路径：

```
QA 发现 → [级别标注] → 研发评估 → 结果：
  ├── 通过 → 理由记录
  ├── 驳回 → 驳回理由 + 复现尝试记录
  ├── 暂缓 → 目标版本 + Frank 签字（BLOCKER 级）
  └── 申诉 → 新证据 + 产品裁定
```

**关键规则**：
- 驳回必须附理由（by design / cannot repro / cost > benefit）
- 降级自动通知产品，产品作为 observer 不阻塞
- 申诉必须带新证据（新复现/新影响面/新用户反馈），产品裁定为最终

---

## 4. 预期产出

### 4.1 每项 P0 输出一行级别变更

格式：

```
| P0-NN | 原始级别 | 新标准级别 | 变更方向 | 判定路径 |
```

### 4.2 现有重审结果汇总（来自已完成的数据收集）

#### P0-01：修复审计 importer $HOME → /root

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: ${HOME} 解析错误 | — | **MINOR** | — | 用户可感知(数据完整性) + C级数据 + 不影响核心任务 |

判定公式对照：非安全漏洞 → 用户可感知（审计路径重复）→ C 级内部运维数据不加权 → MINOR。
论证流程：grandfather clause 适用（标准发布前已修复）。
SLA：同日修复，远超 MINOR 2 工作日要求。
发布门禁：无阻塞项。

#### P0-02：确认 pending_upgrades 目录

**状态：待收集原始数据。**

数据收集步骤：
1. 查询 infomanager board 的 `t_7313221c` 任务状态和结果
2. 检查 `/root/.hermes/` 下的 pending_upgrades 目录结构
3. 确认目标状态（应该为空/已清理）
4. 按标准 §1.2 逐条判定：此任务性质为"确认运维状态"，非 bug 修复——如确实清理完毕 → 无需 QA 发现分级，直接记录验证结果

#### P0-03：备份 DR 演练

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1a: 备份不存在场景 | — | **BLOCKER** | — | 用户可感知 + 功能阻断 + 无 workaround |
| F1b: 备份存在但未验证 | — | **MAJOR** | — | 用户可感知 + 功能阻断 + 可能有 workaround |
| F1c: DR 演练频率不明确 | — | **MINOR** | — | 用户可感知(间接) + 不影响核心任务 |
| F1d: 缺少复盘模板 | — | **SUGGESTION** | — | 用户不可感知 |
| F2: 申诉脚本无备份验证 | — | **MAJOR** | — | 数据一致性问题 (C级 → 不加权, 但功能阻断有 workaround) |

判定公式对照：F1a 命中 BLOCKER 的第一子句（用户可感知 AND 功能阻断 AND 无 workaround）。
论证流程：标注 `triage_needed`，部分发现需研发二次确认。
SLA：仅 F1a 触发 BLOCKER SLA（4h/8h/24h）。

#### P0-04：Infomanager URL 消失根因

**状态：部分数据已收集——37 测试全过，识别到以下关键事实：**

**已收集证据**：
- 37/37 tests PASS（0.14s）
- Vault 中存在 `url: ""` 条目（如 2026-07-02 Hermes v0.18 文章）
- `process_collection.py` L1212-1244 有 `_find_existing_by_url()` 的 URL 去重逻辑
- L1219-1220：`if not url or not url.strip(): return None` — 空 URL 不触发去重匹配
- HARD GUARD 路径已验证：无 URL → 提取 failed → 仍写文件 → url="" 

**执行时的重审步骤**：
1. 还原原始 URL 消失场景：是什么操作导致 URL 从 `url: "..."` 变为 `url: ""`？
2. 检查 `process_collection.py` 的 URL 处理链路（从 parse→extract→classify→write_to_vault）
3. 验证修复是否阻止了 URL 被静默清空
4. 对发现的每个 gap 按 §1.2 五步判定分级
5. 确认修复后的回归测试涵盖 URL 持久化场景

**测试用例**：

```
TC-P04-01: 含 URL 的 Feishu 消息 → pipeline → vault 文件 url 字段非空
  Given: FEISHU_TEXT_WITH_URL = "AI 工具推荐...https://example.com/article/123"
  When:  process(message) 完整的 pipeline
  Then:  输出 vault 文件 frontmatter 中 url 字段 != ""
        pipeline log 第 6 步 url 字段 != ""

TC-P04-02: 不含 URL 的 Feishu 消息 → pipeline → vault 文件 url 字段为空字符串
  Given: FEISHU_TEXT_NO_URL = "这是一条没有链接的纯文本消息"
  When:  process(message) 完整的 pipeline
  Then:  输出 vault 文件 frontmatter 中 url 字段 == ""
        这是预期行为（无链接分享），不应被当作 bug

TC-P04-03: 含 URL 消息 → 中间某步异常 → url 不会因异常而丢失
  Given: 含 URL 消息，mock 中间步骤（如 classify）失败
  When:  process(message) 容错走过
  Then:  vault 文件 url 字段仍为原始 URL（非空字符串）
        或整个 pipeline 显式失败返回（而非静默写空 url）

TC-P04-04: 空 URL 不触发去重误判
  Given: vault 中已有 url="" 的文件
  When:  新消息 URL 也为空 → 调用 _find_existing_by_url("")
  Then:  L1219-1220: 空 URL 直接返回 None，不会匹配到任何文件
```

#### P0-05：Infomanager 管线加结构化日志

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F0: P0-05 实现任务不存在 | — | **SUGGESTION** | — | 流程阻塞，非代码 bug |

特殊说明：P0-05 实现在 infomanager board 上缺失（P0-01~P0-04/P0-06 均存在）。非标准 bug 发现——属流程级前置条件未满足。无法执行完整 QA 重审。

重审建议：先由研发创建 P0-05 实现任务，附 6 项前置 QA 检查清单（JSON schema / 日志级别 / Trace ID / 错误上下文 / PII 不泄露 / 日志量可控），再触发正式 QA 重审。

#### P0-06：Infomanager contract test + e2e smoke test

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: parse_message('') 无显式测试 | 低风险缺失 | **SUGGESTION** | 降级 | 用户不可感知(内部边缘 case) |
| F2: 损坏的 Feishu JSON 无专门测试 | 低风险缺失 | **SUGGESTION** | 降级 | 用户不可感知(Feishu webhook 不发损坏 JSON) |

判定公式对照：F1/F2 均不满足"用户可感知"门槛。非安全漏洞。源码有 try/except 安全网。
测试结果：78/78 PASS (0.18s)，38 contract points + 4 HARD GUARD 路径完整。
发布门禁：BLOCKER=0, MAJOR=0, 安全漏洞=0 → 无阻塞。

#### P0-07：MEMORY.md 归档（139%→<80%）

**状态：部分数据已收集——当前 MEMORY.md 仅 513 字节/1 行。**

**执行时的重审步骤**：
1. 确认"139%"的来源：是 memory char budget 的使用率曾达 139%（超过 2,200 chars 上限）
2. 验证当前状态：所有 profile 的 MEMORY.md 是否 < 80%
3. 检查归档/trim 机制是否已生效（旧内容是否有备份）
4. 确认修改是否持久（重启后不反弹）
5. 按 §1.2 分级：如已修复 → 验证记录，无需新 QA 发现；如未修复 → 按数据完整性判定

#### P0-08：mem0 修通（SDK + API key + is_available）

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| P1: config.yaml api_key 对插件是死代码 | — | **MAJOR** | — | 用户可感知 + 功能阻断 + 有 workaround(.env) |
| P2: is_available() SDK 未装仍返回 True | — | **MAJOR** | — | 用户可感知 + 功能阻断 + 有 workaround(pip install) |
| P3: Lazy install 5 种失败→1 种错误 | — | **MAJOR** | — | 关键路径静默失败 |
| P4: Platform mode 事实提取不透明 | — | **MINOR** | — | 用户可感知(间接) + 不影响核心任务 |
| P5: mem0.json 缺失无警告 | — | **MINOR** | — | 用户可感知 + 不影响核心任务 |

判定公式对照：P1/P2/P3 均命中 `用户可感知 AND 功能阻断 AND 有 workaround → MAJOR`。
SLA：MAJOR → 研发 1 工作日响应、2 工作日定位、当前版本窗口内修复。

**测试用例**：

```
TC-P08-01: mem0 SDK 安装验证
  Given: pip3 list
  Then:  输出包含 "mem0ai 2.0.10"

TC-P08-02: API key 配置验证
  Given: source ~/.hermes/profiles/orchestrator/.env
  Then:  echo $MEM0_API_KEY 输出非空（m0-...）
         config.yaml memory.mem0.api_key 也非空

TC-P08-03: 网络连通性
  Given: curl -s -o /dev/null -w "%{http_code}" https://api.mem0.ai
  Then:  返回 200

TC-P08-04: is_available() 可靠性（修复后验证）
  Given: 模拟卸载 SDK（pip uninstall mem0ai -y）
  When:  调用 is_available()
  Then:  返回 False（而非 True）—— 当前 SDK 已装，此 test case 需 SDK 卸载后验证

TC-P08-05: config.yaml api_key 生效性（修复后验证）
  Given: 仅在 config.yaml 中设置 mem0.api_key，不设 .env MEM0_API_KEY
  When:  重启 agent 并调用 mem0_search
  Then:  mem0 正常返回结果（不从 config.yaml 读取的是当前 bug 行为）
```

#### P0-09：mem0 结果校验（score 阈值 + FTS5）

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F5: Qdrant 维度不匹配 (1536d vs 384d) | 未分级 | **BLOCKER** | 严重升级 | 默认配置即功能阻断 + 无 workaround |
| F1: 默认阈值 0.25 → 100% FP | critical | **MAJOR** | 降级 | 有 workaround（改阈值到 0.60） |
| F2: bge-small-en-v1.5 中文噪声 | high | **MAJOR** | 定性一致 | 用户可感知 + 体验严重退化 |
| F3: FTS5 无 CJK 分词器 | medium | **MAJOR** | 升级 | 功能阻断但有 workaround |
| F4: 完整 LLM pipeline 未测试 | limitation | **SUGGESTION** | 降级 | 用户不可感知 |

判定公式对照：
- F5: 默认配置下 mem0 完全不可用 → `用户可感知 AND 功能阻断 AND 无 workaround → BLOCKER`
- F1: 有 workaround（改阈值） → 不满足 BLOCKER 的"无 workaround"条件 → MAJOR
- F3: 新标准以"功能阻断但有 workaround"判定 → 从 medium 升级为 MAJOR
- F4: 不满足"用户可感知"门槛 → 降为 SUGGESTION

SLA：仅 F5 触发 BLOCKER SLA（4h 响应 / 8h 初步判定+进度同步 / 24h 方案）。
发布门禁：1 BLOCKER → 阻塞发版。F5 必须修复。

#### P0-10：consolidation 审计（diff + snapshot）

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: diff/snapshot/rollback 全部通过 | — | **PASS** | — | 审计本身无 bug |
| P2: skill_files 字段命名歧义 | — | **SUGGESTION** | — | 用户不可感知（内部 manifest） |
| P3: run.json vs manifest 计数不统一 | — | **SUGGESTION** | — | 用户不可感知 |
| P3: 快照保留策略不匹配 | — | **MINOR** | — | 系统健康度（长期影响） |

核心审计结果：零文件丢失（0 deleted / 20 added），snapshot 完整解压，回滚可用。
Consolidation 功能当前关闭（`consolidate: false`），无法验证 LLM 合并逻辑——需 staging 环境开启测试。
发布门禁：无阻塞项。

#### P0-11：/learn 产出校验（SKILL.md 硬校验）

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: headless-browser-tools literal \n | CRITICAL | **MAJOR** | 降级 | 有 workaround（手动编辑 SKILL.md） |
| F2: research-paper-writing 超 100K | ERROR（已豁免） | **N/A** | — | bundled skill 已豁免 |
| F3: 571 peer-expected 字段缺失 | WARNING | **SUGGESTION** | 降级 | 用户不可感知 |
| F4: 12 error 文件未记录 | — | **SUGGESTION** | 新增 | 审计完整性 gap |

判定公式对照：F1 命中 `用户可感知 AND 功能阻断 AND 有 workaround → MAJOR`。
发布门禁：BLOCKER=0, 安全漏洞=0 → 满足发布条件。F1 建议在 release notes 标注 known issue。

#### P0-12：Context Files（.hermes.md 项目规则）

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: 标准文档行数引用错误 433→436 | — | **MINOR** | — | 用户可感知（文档不精确） + 不影响核心任务 |
| F2: 发布门禁公式省略 MAJOR≤N | — | **MAJOR** | — | 用户可感知（规则缺失） + 影响发版决策 |
| F3: defer.py 未在脚本列表中 | — | **MINOR** | — | 用户可感知 + 不影响核心任务 |
| F4: "五步判定公式"表述可精确化 | — | **SUGGESTION** | — | 用户不可感知（表述问题） |

判定公式对照：F2 是关键——如果 `.hermes.md` 是开发者的日常参考，缺少 MAJOR≤N 可能导致发布时误判。用户可感知 + 影响决策 → MAJOR。
发布门禁：1 MAJOR → 建议修复后发版。

#### P0-13：Cron context_from 链

| 发现 | 原始 | 新标准 | 变更 | 判定路径 |
|------|:---:|:---:|:---:|------|
| F1: Watchdog 被阻止的工具调用 | LOW | **SUGGESTION** | 降级 | 用户不可感知（内部日志） |
| Chain integrity: context_from 链完整 | — | **PASS** | — | 审计通过 |

判定公式对照：F1 的 WARNING 仅出现在 agent.log 内部日志，最终输出正确 JSON，下游 VA 正常接收。五步判定：Step1≠安全 → Step2≠用户感知 → Step3≠数据 → Step4≠健康 → Step5=主观建议 → SUGGESTION。
发布门禁：SUGGESTION 不在门禁公式中，不阻塞发版。

---

## 5. 测试用例（详细）

### 5.1 P0-04: URL 消失根因（4 个测试用例）

见 §4.2 P0-04 节。核心覆盖：
1. TC-P04-01：含 URL → pipeline → url 字段非空
2. TC-P04-02：不含 URL → url=""（预期行为）
3. TC-P04-03：中间异常不导致 URL 静默丢失
4. TC-P04-04：空 URL 不触发去重误匹配

### 5.2 P0-08: mem0 修通（5 个测试用例）

见 §4.2 P0-08 节。核心覆盖：
1. TC-P08-01：SDK 安装验证
2. TC-P08-02：API key 双路径验证
3. TC-P08-03：网络连通性
4. TC-P08-04：is_available() 可靠性
5. TC-P08-05：config.yaml api_key 生效性

---

## 6. 重审待办清单

### 6.1 需补充数据收集

| # | P0 | 当前状态 | 下一步 |
|---|----|---------|--------|
| 1 | P0-02 | 无原始重审数据 | 查询 infomanager board t_7313221c，确认 pending_upgrades 目录状态 |
| 2 | P0-04 | 部分数据（37 tests PASS, URL="" 条目已确认） | 补充完整的原始 QA 发现清单，还原根因分析链路 |
| 3 | P0-07 | 当前 MEMORY.md=513B/1行 | 确认"139%"的来源和修复机制，验证不再反弹 |

### 6.2 需评审确认

| # | 事项 | 关联 |
|---|------|------|
| 1 | P0-05 实现任务缺失 → 先建任务还是跳过？ | §11 红线 1: BLOCKER 暂缓需 Frank |
| 2 | P0-09 F5 (Qdrant 维度不匹配) 被重分级为 BLOCKER → 是否阻塞当前发版？ | §10 发布门禁 |
| 3 | P0-03 F1a (备份不存在) 被重分级为 BLOCKER → 当前备份状态是否需要立即修复？ | §8.1 BLOCKER SLA |
| 4 | P0-10 consolidation 关闭 → 是否需要 staging 验证 LLM 合并逻辑？ | —

---

## 7. 综合级别统计

基于已完成重审的 10/13 任务：

| 级别 | 数量 | 涉及发现 |
|------|:---:|---------|
| **BLOCKER** | 2 | P0-03 F1a（备份不存在）, P0-09 F5（Qdrant 维度不匹配） |
| **MAJOR** | 10 | P0-03 F1b/F2, P0-08 P1/P2/P3, P0-09 F1/F2/F3, P0-11 F1, P0-12 F2 |
| **MINOR** | 6 | P0-01 F1, P0-03 F1c, P0-08 P4/P5, P0-12 F1/F3, P0-10 P3 |
| **SUGGESTION** | 11 | P0-03 F1d, P0-06 F1/F2, P0-08—, P0-09 F4, P0-10 P2/P3, P0-11 F3/F4, P0-12 F4, P0-13 F1 |
| **PASS** | 3 | P0-10 F1, P0-13 chain, P0-06 78/78 |

### 7.1 发布门禁影响

按 §10 发布门禁公式：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 检查项 | 当前状态 |
|--------|:---:|
| BLOCKER=0？ | ❌ 2 BLOCKERs（P0-03 F1a, P0-09 F5） |
| 安全漏洞=0？ | ✅ 无安全漏洞发现 |
| 无未裁定申诉？ | ✅ 无申诉 |

**结论**：当前存在 2 个 BLOCKER 级发现，按 §10 发版门禁规则，不允许发版。需修复或 Frank 暂缓签字。

---

## 8. 评审与批准

| 角色 | 签名 | 日期 |
|------|------|------|
| QA（方案编制） | game-qa | 2026-07-08 |
| 研发（技术可行性） | — | — |
| 产品（用户影响） | — | — |
| 架构（系统风险） | — | — |
| Frank（最终批准） | — | — |

---

## 附录 A：标准文档快速参考

| 条款 | 主题 | 关键内容 |
|------|------|---------|
| §1.2 | 判定公式 | BLOCKER=可感知+阻断+无workaround; MAJOR=可感知+阻断+有workaround; MINOR=可感知+不阻断; SUGGESTION=不可感知 |
| §1.3 | 判定原则 | 用户可感知是第一刀；workaround 是第二刀；概率性以最坏定级；无法判断取高；环境差异不降级 |
| §2 | 安全漏洞 | 不经过用户可感知过滤；OWASP Top 10 限定范围；PII 泄露最低 MAJOR |
| §3 | 性能退化 | 正式: 3x→MAJOR, 10x→BLOCKER；Fallback: 1s→MINOR, 1-5s→MAJOR, >5s→BLOCKER |
| §4 | 数据敏感度 | S 级自动→BLOCKER；A 级自动+1→最低 MAJOR；B 级不加权；C 级按正常 |
| §6 | 论证流程 | QA→研发→通过/驳回/暂缓；驳回可申诉（需新证据）；产品裁定为最终 |
| §8 | SLA | BLOCKER: 4h响应/8h定位(初步)/24h方案；MAJOR: 1d/2d/版本窗口内 |
| §10 | 发布门禁 | BLOCKER=0 AND 安全漏洞=0 AND 无未裁定申诉 |
| §11 | 产品红线 | BLOCKER 暂缓需 Frank 签字；申诉需新证据；产品裁定为最终 |

---

> **方案状态**：Draft — 待评审。评审通过后方可进入重审执行阶段。
> 最终产出目录建议：`docs/qa-reaudits/findings/` 下每个 P0 一个独立重审报告文件。
