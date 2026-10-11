# P0-06 架构裁定：高见远

> 裁定人：高见远（架构师）
> 裁定日期：2026-07-08
> 依据源码：`/workspace/InfoManager/scripts/process_collection.py` (2036 lines)
> 产品提问来源：许清楚（产品）Roundtable 发言 §「给架构/研发的递进问题」

---

## 裁定 1：A8 完整性防护 — JSON try/except + regex fallback

### 产品提问

> 一个依赖 try/except 的 JSON 解析是否足够作为完整性防护？regex fallback 可能产生静默数据损坏吗？

### 源码分析

`parse_message()` (L488-588) 使用两层独立解析策略，互不干扰：

```
Layer 1 (JSON 路径, L501-512):
  json.loads(raw_text) → data.event.message.content.text
  try/except (json.JSONDecodeError, TypeError) → 失败则 user_text_from_json = ""

Layer 2 (Regex 路径, L515):
  re.findall(r'https?://[^\s]+', text) → URL 列表
  直接作用在 raw text 上，不依赖 JSON 结构
```

**关键设计事实**：
- Layer 1 和 Layer 2 是独立的提取维度：JSON 路径取文本，Regex 路径取 URL
- JSON 解析失败只影响 `user_text_from_json`（辅助文本），不影响 URL 提取
- `non_url_text` 从 raw text 中去掉 URL 后得到，同样不依赖 JSON
- 函数始终返回 dict（TC-C07 已验证），不存在返回 None 的半成品问题

### 静默数据损坏风险分析

**不存在静默数据损坏路径。** 理由：

| 场景 | JSON 路径 | Regex 路径 | 结果 |
|------|-----------|-----------|------|
| 正常 Feishu JSON | ✅ 提取 content.text + URL | ✅ 提取 URL | 完整 |
| JSON 解析失败 | ❌ user_text_from_json="" | ✅ 提取 URL（raw text 上跑） | URL 正确，user_text 空 |
| 空输入 | ❌ user_text_from_json="" | ✅ 返回空列表 | 正常 fallback |
| 损坏 JSON | ❌ user_text_from_json="" | ✅ URL 在 raw text 中不受影响 | URL 正确 |

regex 不是被当作 JSON 的"备胎解析器"使用——它是在 raw text 上独立提取不同维度的数据。两个路径不存在数据互相覆盖或竞争关系。

### 裁定

**✅ 架构通过。** try/except JSON + 独立 regex 的设计满足完整性防护要求。

设计正确地将 URL 提取与 JSON 结构解析解耦，形成防御性架构：
- JSON 失败 → URL 仍能从 raw text 提取
- URL 失败 → 有 HARD GUARD 降级路径（TC-HG01~HG05 已验证）

**补充建议**（非阻塞，SUGGESTION 级别）：
- 补充一个单元测试验证 JSON 解析失败路径：输入非法 JSON → 断言 `primary_url` 仍正确提取 + `user_text_from_json` 为空
- 当前 TC-C07 覆盖"非 JSON 纯文本"，但未覆盖"形似 JSON 但损坏"的 case。差异在测试粒度层面，不是架构层面。

---

## 裁定 2：PII 泄露风险 — vault 文件访问控制与最小权限

### 产品提问

> user_id/message_id → vault 的 PII 泄漏风险——vault 文件的访问控制和最小权限原则是否到位？

### 源码分析

**核心发现：`user_id` 和 `message_id` 从未进入管线数据流。**

证据链：

1. `parse_message()` (L488-588) 是 raw Feishu 消息的**唯一入口**。代码中 `message_id` 和 `user_id` 的 grep 结果：**0 matches**。

2. `parse_message()` 从 Feishu webhook JSON 中仅 cherry-pick：
   - `data.event.message.content.text` — 用户发送的文本（L504-510）
   - URL 通过 regex 从 raw text 提取（L515）
   - image_keys 通过 `_extract_image_keys()` 提取

3. `write_to_vault()` (L1632-1728) 写入 vault 的字段清单：
   - title, url, platform_display
   - tags, keywords, summary, content_type
   - external_sources, created, extraction_status, ocr_status
   - **不含任何 PII 字段**

4. `_pipeline_log()` (L135-184) 写入 pipeline.jsonl 的字段：
   - step, status, duration_ms, url, message, trace_id, metrics
   - 所有字符串值经过 `_deep_sanitize()` → `_sanitize_for_pii()`，覆盖 API key、Bearer token、手机号、邮箱
   - **不含 user_id 或 message_id**

5. PII 清洗合约在代码中明确标注（L152: "PII sanitation (C5): API keys, tokens, phone numbers, and emails are redacted before write."），并通过 `_deep_sanitize` 递归清洗所有嵌套字符串。

### 风险级别

**当前状态：无 PII 泄露风险。** 管线设计上从未提取 `user_id`/`message_id`，属于「结构安全」而非「清洗安全」——代码的结构保证了敏感字段不会进入数据流，比依赖事后清洗更可靠。

### 但存在一个架构债务

**当前安全是"默认安全"（safe by omission），不是"强制安全"（safe by design）。**

风险场景：未来迭代中，有开发者想在 `parse_message()` 中增加 `message_id` 用于去重追踪，然后这个字段沿管线流到 `write_to_vault()` 或 `_pipeline_log()` → PII 泄露。

当前缺少的防护：
- `parse_message()` 没有显式声明"本函数不提取 PII"的合约
- `write_to_vault()` 和 `_pipeline_log()` 没有 PII 字段白名单校验
- `_PII_PATTERNS` 不覆盖 Feishu 用户 ID 格式（如 `ou_` 前缀的 open_id）

### 裁定

**✅ 架构通过 — 当前代码 PII-safe。** 但存在架构债务需在后续迭代修复。

**强制建议**（纳入下一迭代，非 P0 阻塞）：

| # | 措施 | 类型 | 工作量 |
|---|------|------|:---:|
| 1 | `parse_message()` docstring 显式声明不提取 PII | 合约化 | 1 行 |
| 2 | CI 增加 PII 回归测试：断言 vault 文件和 pipeline.jsonl 不含 `user_id`/`message_id` | 门禁 | 1 个测试 |
| 3 | `_PII_PATTERNS` 增加 Feishu ID 格式（`ou_` 前缀）作为 defense-in-depth | 防御 | 1 行 regex |
| 4 | `write_to_vault()` 增加 PII 字段白名单校验（断言只写入已知 schema 字段，拒绝未知字段） | 架构增强 | ~15 行 |

这些是防御性改进——当前代码在结构上已经是安全的，但缺少显式合约和回归门禁来保证未来变更不引入回归。

---

## 综合裁定

```
P0-06 架构评审结论：✅ 通过

┌─ A8 完整性防护 ── ✅ try/except + 独立 regex 设计正确，无静默损坏路径
├─ PII 泄露风险 ─── ✅ 当前代码 PII-safe（结构安全），message_id/user_id 未进入管线
├─ 架构债务 ────── ⚠️ 4 项防御性改进建议，非 P0 阻塞
└─ 风险评级 ────── LOW
   - 两项产品提问均无实质风险
   - PII 安全由代码结构保证，非依赖运行时清洗
   - 建议项为防御性加固，可纳入常规迭代
```

> 高见远（架构师）
> 2026-07-08
