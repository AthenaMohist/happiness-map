# P0-04 测试方案：Infomanager URL 消失根因重审

> **原始任务**：Infomanager — 排查 URL 消失根因 + URL 为空时拒绝 success（1h）
> **QA 标准版本**：v1.0 (`docs/standards/qa-finding-classification.md`)
> **代码基准**：`/workspace/InfoManager/scripts/process_collection.py`（1892 行）
> **数据敏感度**：B 级（用户提交的外部链接内容）— 不加权，按正常公式判定
> **编制日期**：2026-07-08

---

## 1. 代码路径分析

### 1.1 URL 流经的完整路径

```
Feishu 消息
  │
  ▼
parse_message() [L359]
  │ urls = re.findall(r'https?://[^\s]+', text) [L386]
  │ primary_url = urls[0] if urls else "" [L395]
  │
  ▼
process() [L1643]
  │ parsed["primary_url"] → _pipeline_log(url=...) [L1664~]
  │ parsed["primary_url"] → extract_content(parsed) [L1690]
  │ parsed["primary_url"] → _reflect_on_quality() [L775]
  │ parsed["primary_url"] → write_to_vault(title, url, ...) [L1799]
  │
  ▼
write_to_vault() [L1503]
  │ if url and url.strip(): → _find_existing_by_url(url) [L1509]
  │   ├── found → merge_to_existing() → 覆写 url: "{new_url}" [L1418]
  │   └── not found → 新建文件 → url: "{url}" [L1559]
  │ if url is empty: → 新建文件 → url: "" [L1559]
  │
  ▼
merge_to_existing() [L1353]
  │ 前端元数据 url: "{new_url}" 直接覆写旧值 [L1420]
  │ 无 new_url 为空的防御检查
```

### 1.2 已确认的安全机制

| 机制 | 位置 | 行为 |
|------|------|------|
| 空 URL 不触发 merge | `write_to_vault` L1508-1510 | `if url and url.strip()` → 空 URL 走新建路径 |
| `_find_existing_by_url("")` 返回 None | L1219-1220 | 显式 guard：空 URL 不匹配任何文件 |
| HARD GUARD: 无 URL 时提取步骤标记 failed | `test_pipeline_log.py` L425 | 已验证通过 |
| HARD GUARD: 提取失败仍执行写入 | `test_pipeline_log.py` L440 | 已验证通过 |

### 1.3 已识别的风险点

| # | 风险 | 位置 | 影响 |
|---|------|------|------|
| R1 | **merge_to_existing 无条件覆写 URL**：新 URL 直接覆盖旧前端元数据中的 url 字段 | L1420 (`url: "{new_url}"`) | 如果后续处理的同一文章 URL 格式变化（短链 vs 长链），旧 URL 被静默替换 |
| R2 | **管线返回成功但 URL 为空**：`process()` 总是返回 `status: "processing"`，从未因 url="" 而返回失败状态 | L1643-1820 | 违反原始修复要求"URL 为空时拒绝 success" |
| R3 | **URL 提取 regex 边界**：`r'https?://[^\s]+'` 不处理 URL 中的换行/零宽字符/编码实体 | L386 | 特定格式 URL 可能无法提取 |
| R4 | **parse_message JSON 解析容错**：多层 JSON decode 失败时静默 fallback 到 raw_text | L370-383 | 嵌套 JSON 异常时 primary_url 可能被错误设空 |

---

## 2. QA 发现判定（按标准 §1.2）

### 2.1 发现分级表

| 发现 ID | 描述 | 判定 | 判定路径 |
|---------|------|:---:|---------|
| **F1** | URL 为空时管线仍返回 success 状态，不拒绝（违反原始修复要求） | **MAJOR** | 用户可感知（数据完整性：url="" 写入 vault）+ 功能阻断（错误被静默）+ 有 workaround（手动检查 vault 文件确认 URL） |
| **F2** | merge_to_existing 无条件覆写旧 URL，无 new_url 空值防御 | **MAJOR** | 用户可感知（数据完整性：有效 URL 被清空）+ 触发概率低但后果严重 |
| **F3** | URL regex 不覆盖换行/零宽字符，特定格式 URL 提取失败 | **MINOR** | 用户可感知（URL 丢失）+ 不影响核心任务（概率极低，需特殊消息格式） |
| **F4** | parse_message 多层 JSON 解析异常时静默 fallback，可能丢失 URL | **MINOR** | 同上 |
| **F5** | pipeline_log 中 url 字段跟踪仅依赖 parsed["primary_url"]，不验证最终 vault 文件 url 一致性 | **SUGGESTION** | 用户不可感知（纯内部日志增强） |
| **F6** | 缺少端到端回归：verify vault 文件 url 字段 == 原始消息中的 URL | **MAJOR** | 数据完整性验证缺口 → 无法防御 URL 在管线任意步骤静默丢失。这本身是测试覆盖缺失。 |

### 2.2 判定公式对照

**F1（MAJOR）**：
```
前置检查：非安全漏洞 → 跳过
正式判定：
  Step 1: 用户可感知？→ 是（数据完整性：url="" 被写入 vault，用户分享的链接丢失）
  Step 2: 功能阻断？→ 是（错误被静默，管线报告 success 但 URL 实际为空）
  Step 3: 有 workaround？→ 是（手动检查 vault 文件 frontmatter 确认 URL）
  → MAJOR = 用户可感知 AND 功能阻断 AND 有 workaround
```
对照：§5 分级示例 #2（支付按钮无响应但有 workaround → MAJOR）

**F2（MAJOR）**：
```
前置检查：非安全漏洞 → 跳过
正式判定：
  Step 1: 用户可感知？→ 是（数据完整性：有效 URL 被 merge 覆写）
  Step 2: 功能阻断？→ 是（原有 URL 丢失，页面链接断裂）
  Step 3: 有 workaround？→ 是（git history 可恢复，但用户侧不可见）
  → MAJOR
```

**F6（MAJOR）**：
```
前置检查：非安全漏洞 → 跳过
正式判定：
  此发现属"测试覆盖缺失"类，映射到标准 §1.3「数据完整性受影响」扩展定义：
  → 用户可感知（间接受影响：无测试 → 可能漏检 → 数据完整性无保障）
  → 按"无法判断级别时默认取高级别"原则 → MAJOR
```

### 2.3 数据敏感度加权分析

| 发现 | 涉及数据 | 敏感度等级 | 加权结果 |
|------|---------|:---:|---------|
| F1-F6 | URL（用户提交的外部链接内容） | **B 级**（用户行为日志/偏好设置类） | **不加权**，按正常公式 |

URL 不属于：
- S 级（资金流水、用户资产、订单金额）
- A 级（用户基础信息、权限数据）

因此不触发自动升级。

---

## 3. 测试用例

### 3.1 测试矩阵总览

| 类别 | 用例数 | 覆盖风险点 |
|------|:---:|-----------|
| 核心功能回归 | 4 | 已通过 |
| **新增：URL 消失根因** | 6 | F1-F4, F6 |
| **新增：Merge URL 安全** | 3 | F2 |
| **新增：URL 格式边界** | 3 | F3 |
| **新增：管线拒绝空 URL** | 2 | F1 |
| **合计** | **18** | |

### 3.2 核心功能回归（已有，需确认仍通过）

```
TC-R01: 含 URL 的 Feishu 消息 → pipeline → vault 文件 url 字段非空
  Given: FEISHU_TEXT_WITH_URL = '{"event":{"message":{"content":{"text":"AI 工具推荐 https://example.com/article/123"}}}}'
  When:  process(message)
  Then:  输出 vault 文件 frontmatter 中 url 字段 != ""
         pipeline log 全部 9 步 url 字段 != ""

TC-R02: 不含 URL 的 Feishu 消息 → vault 文件 url 字段为空字符串
  Given: FEISHU_TEXT_NO_URL = '{"event":{"message":{"content":{"text":"纯文本消息无链接"}}}}'
  When:  process(message)
  Then:  vault 文件 frontmatter 中 url 字段 == ""
         pipeline log 全部 9 步 url 字段 == ""
         注：这是预期行为（无链接分享），不应被当作 bug

TC-R03: 含 URL 消息 → 中间某步异常 → url 不会因异常而丢失
  Given: 含 URL 消息，mock classify 步骤失败
  When:  process(message)
  Then:  vault 文件 url 字段仍为原始 URL（非空）
         或整个 pipeline 显式失败（而非静默写空 url）

TC-R04: 空 URL 不触发去重误匹配
  Given: vault 中已有 url="" 的旧文件
  When:  调用 _find_existing_by_url("")
  Then:  返回 None（L1219-1220 守卫生效）
```

### 3.3 新增：URL 消失根因（6 个用例）

```
TC-N01: URL 提取 → 写入 → 读取全链路一致性
  Given: 含 5 个不同格式 URL 的消息（标准 https/带参数/带锚点/短链/中文域名）
    - https://example.com/article/123
    - https://github.com/user/repo?tab=readme#section
    - https://t.co/abc123
    - https://m.toutiao.com/is/abc123/
    - https://公众号测试.中国/article
  When:  process(message)
  Then:  vault 文件 url 字段 == primary_url（第一个 URL）
         parse_message["urls"] 包含全部 5 个 URL

TC-N02: 多层 JSON 嵌套容错（Feishu 异常消息格式）
  Given: 畸形 JSON：content 字段为嵌套 3 层的 JSON 字符串
  When:  parse_message(message)
  Then:  primary_url 不为空（URL 仍被提取）
         不因 JSON 解析异常而丢失 URL

TC-N03: URL 包含换行符/零宽字符
  Given: 消息文本中包含 "https://example.com/arti\ncle"（URL 中意外换行）
        或 "https://example.com/\u200barticle"（零宽空格 U+200B）
  When:  parse_message(message)
  Then:  尽可能提取 URL（至少提取到换行/零宽字符前的部分）
         或 pipeline 返回 extraction_status=failed 而非 success

TC-N04: pipeline_log url 字段与 vault 文件 url 一致性
  Given: 执行完整 pipeline
  When:  对比 pipeline_log 最后一步的 url 字段 vs vault 文件的 url 前端元数据
  Then:  两者一致（pipeline_log["push"].url == vault_frontmatter.url）

TC-N05: URL 正常但 extraction 全部失败 → url 仍写入
  Given: 含 URL 的消息，但平台抓取全部超时（mock）
  When:  process(message)
  Then:  vault 文件 url 字段 == 原始消息中的 URL（非空）
         extraction_status == "failed" 但 URL 不丢失

TC-N06: OCR 步骤失败 → URL 不受影响
  Given: 含 URL + 图片的消息，mock OCR 全部失败
  When:  process(message)
  Then:  vault 文件 url 字段 == 原始消息中的 URL（非空）
         ocr_status == "failed" 但 URL 不丢失
```

### 3.4 新增：Merge URL 安全（3 个用例）

```
TC-M01: merge_to_existing 覆写 URL 为空
  Given: vault 中存在 url="https://example.com/old" 的文件
  When:  write_to_vault(title="New Title", url="") → 走新建路径（L1509 guard）
  Then:  新建文件，url=""
         旧文件 url 不变（不触发 merge）
         注：当前 guard 已生效，此用例确认不会回退

TC-M02: merge_to_existing 覆写 URL 为不同值
  Given: vault 中存在 url="https://example.com/old" 的文件
  When:  write_to_vault(title="New Title", url="https://example.com/new")
  Then:  因 URL 不匹配 → 不触发 merge → 新建文件
         旧文件 url="https://example.com/old" 保持不变
         注：确认不同 URL 不会错误匹配

TC-M03: merge 后旧 URL 是否被保留在 body 或 metadata 中
  Given: vault 中存在 url="https://example.com/original" 的文件
  When:  同 URL 再次处理（触发 merge），new_url 同上
  Then:  frontmatter url 正确（同值覆写无损失）
         body 中的标题链接正确更新
         tags/keywords 正确并集
```

### 3.5 新增：URL 格式边界（3 个用例）

```
TC-B01: URL 位于消息中间而非末尾
  Given: "这篇文章 https://example.com/article 总结得很好，推荐阅读"
  When:  parse_message(message)
  Then:  primary_url 正确提取（非空）
         非 URL 部分的文本正确进入 user_text

TC-B02: 消息包含多个 URL → 只有第一个作为 primary_url
  Given: "推荐阅读 https://example.com/a 和 https://example.com/b"
  When:  process(message)
  Then:  vault 文件 url 字段 == "https://example.com/a"
         urls 列表包含两个 URL

TC-B03: URL 超长（>2000 字符）→ 不截断
  Given: 含极长 URL 的消息（如带大量 query 参数）
  When:  parse_message(message)
  Then:  primary_url 完整保留，不截断
```

### 3.6 新增：管线拒绝空 URL（2 个用例）

```
TC-E01: 无 URL 消息 → pipeline 返回 extraction_status != "success"
  Given: 纯文本消息（无 URL）
  When:  process(message)
  Then:  result["extraction_status"] in ("failed", "no_url")
         不返回 "success"
         注：此为原始修复要求的核心——"URL 为空时拒绝 success"

TC-E02: URL 提取失败（regex 未匹配但消息格式正常）→ 不静默通过
  Given: 格式正确但无 URL 的消息
  When:  process(message)
  Then:  pipeline 显式标记 extraction_status != "success"
         不创建 url="" 的 vault 条目并报告 success
         或：如果仍创建文件，至少 pipeline 返回 status 包含 "no_url" 信息
```

---

## 4. 测试执行策略

### 4.1 测试框架

| 维度 | 选择 |
|------|------|
| 测试框架 | pytest（与现有 `test_pipeline_log.py` / `test_pipeline_contract.py` 一致） |
| Mock 策略 | 复用现有 mock 模式：`_block_network` + `_call_llm_side_effect` + monkeypatch |
| 运行环境 | `/workspace/InfoManager`，虚拟环境需安装 pytest + pyyaml |
| CI 集成 | 合入 `.github/workflows/test.yml`（如存在）或新增 pre-push hook |

### 4.2 覆盖率目标

| 目标 | 当前 | 目标 |
|------|:---:|:---:|
| URL 处理路径 | 4 个用例 | ≥ 14 个用例（本次新增 10+） |
| merge_to_existing | 5 个用例 | ≥ 8 个用例（本次新增 3）|
| 空 URL 拒绝 success | 0 个用例 | ≥ 2 个用例（本次新增 2）|
| URL 格式边界 | 0 个用例 | ≥ 3 个用例（本次新增 3）|

### 4.3 执行命令

```bash
cd /workspace/InfoManager
python -m pytest tests/test_pipeline_log.py scripts/test_merge.py -v
# 新增用例集成后：
python -m pytest tests/ -v --tb=short
```

---

## 5. SLA 对照

| 发现 | 级别 | 响应 | 定位 | 方案 |
|------|:---:|------|------|------|
| F1（空 URL 仍 success）| MAJOR | 1 工作日 | 2 工作日 | 当前版本窗口内 |
| F2（merge 覆写 URL）| MAJOR | 1 工作日 | 2 工作日 | 当前版本窗口内 |
| F3（URL regex 边界）| MINOR | 2 工作日 | — | 不限 |
| F4（JSON 解析容错）| MINOR | 2 工作日 | — | 不限 |
| F5（pipeline_log 增强）| SUGGESTION | 3 工作日 | — | 不限 |
| F6（e2e 回归缺失）| MAJOR | 1 工作日 | 2 工作日 | 当前版本窗口内 |

**无 BLOCKER 级发现 → 不触发 4h/8h/24h SLA。**

---

## 6. 发布门禁

根据标准 §10 发布门禁公式：

```
BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉
```

| 条件 | 本次重审状态 |
|------|:---:|
| BLOCKER | ✅ 0 个 |
| 安全漏洞 | ✅ 0 个 |
| 未裁定申诉 | ✅ 无 |

→ **门禁通过，不阻塞发版。** 但 F1 和 F2（均为 MAJOR）建议在当前版本修复，发版时需标注 known issue。

---

## 7. 与原始 P0-01-13 汇总方案的衔接

本方案是对 `test-plan-p0-01-13.md` §4.2 P0-04 节的深化。原始汇总中记录的 4 个用例（TC-P04-01~04）均保留并重编号为 TC-R01~R04（回归用例）。新增用例 TC-N01~N06、TC-M01~M03、TC-B01~B03、TC-E01~E02 覆盖了原始汇总方案中标注的待办：

> "补充完整的原始 QA 发现清单，还原根因分析链路"

本次重审成功还原了完整的 URL 流经路径（9 步管线 × 6 个函数），识别了 6 个发现，并设计了 18 个测试用例覆盖所有风险点。

---

## 8. 论证流程状态

| 发现 | QA 判定 | 研发评估 | 论证结果 |
|------|:---:|:---:|:---:|
| F1 | MAJOR | 待评估 | — |
| F2 | MAJOR | 待评估 | — |
| F3 | MINOR | 待评估 | — |
| F4 | MINOR | 待评估 | — |
| F5 | SUGGESTION | 待评估 | — |
| F6 | MAJOR | 待评估 | — |

如研发驳回任何发现，QA 保留启动 §6.3 有成本申诉的权利（需附带新复现证据）。

---

## 附录：测试数据清单

```python
# 用于测试的消息 fixture
MESSAGES = {
    "standard_url": '{"event":{"message":{"content":{"text":"推荐 https://example.com/article"}}}}',
    "no_url": '{"event":{"message":{"content":{"text":"纯文本无链接"}}}}',
    "multiple_urls": '{"event":{"message":{"content":{"text":"A https://a.com B https://b.com"}}}}',
    "url_with_params": '{"event":{"message":{"content":{"text":"链接 https://github.com/x/y?tab=readme#L10"}}}}',
    "chinese_domain": '{"event":{"message":{"content":{"text":"测试 https://中文域名.中国/path"}}}}',
    "url_mid_text": '{"event":{"message":{"content":{"text":"文章 https://example.com 值得读"}}}}',
    "long_url": '{"event":{"message":{"content":{"text":"链接 https://example.com/?" + "x=1&"*500 + "end"}}}}',
    "nested_json": '{"event":{"message":{"content":"{\\"text\\":\\"{\\\\\\"text\\\\\\":\\\\\\"推荐 https://example.com\\\\\\"}\\"}"}}}',
}
```
