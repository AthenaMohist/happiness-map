# P0-06 测试方案：Infomanager Contract Test + E2E Smoke Test

> 版本：v1.0 | 状态：重审完成
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）

---

## 目录

1. [背景与范围](#1-背景与范围)
2. [代码库概览](#2-代码库概览)
3. [Contract Test 矩阵](#3-contract-test-矩阵)
4. [E2E Smoke Test 矩阵](#4-e2e-smoke-test-矩阵)
5. [Pipeline Log 验证矩阵](#5-pipeline-log-验证矩阵)
6. [Progressive Feedback 验证](#6-progressive-feedback-验证)
7. [边界 Case 覆盖分析](#7-边界-case-覆盖分析)
8. [降级路径 (HARD GUARD) 验证](#8-降级路径-hard-guard-验证)
9. [新标准维度交叉检查](#9-新标准维度交叉检查)
10. [Findings 分级](#10-findings-分级)
11. [发布门禁评估](#11-发布门禁评估)
12. [测试执行与维护](#12-测试执行与维护)
13. [可扩展性建议](#13-可扩展性建议)

---

## 1. 背景与范围

### 1.1 原始任务

| 字段 | 值 |
|------|-----|
| P0 编号 | P0-06 |
| devPPL kanban 任务 | `t_7128e28c` |
| 标题 | Infomanager contract test + e2e smoke test（2h） |
| 性质 | 测试覆盖建设 |
| 源码仓库 | `/workspace/InfoManager` |
| 当前 HEAD | `3e32e2b`（原始审查时为 `c54da7f`，+2 个提交为文档/缓存变更，不影响测试代码） |

### 1.2 测试目标

Infomanager 管线此前缺乏结构化自动化测试。P0-06 建设了两层测试体系：

| 层级 | 目标 | 覆盖内容 |
|------|------|---------|
| **L1: Contract Test** | 验证每个管线阶段的输入/输出合约 | 7 个阶段函数的接口契约、边界 case、降级行为 |
| **L2: E2E Smoke Test** | 验证端到端管线完整性 | 管线不抛异常、输出文件正确、pipeline.jsonl 记录完整、降级路径 |

### 1.3 测试范围说明

- **覆盖**：7 个管线阶段（parse_message / OCR / extract_content / classify_content / summarize_content / _reflect_on_quality / _enrich_sources）
- **不覆盖**：真实的 LLM 调用（所有测试使用 mock LLM 响应）、真实的网络请求（所有平台 extractor 被 mock）、真实的 Feishu webhook 端到端（使用模拟的 Feishu 消息格式）
- **受限于**：Infomanager 为离线批处理管线——无 HTTP 端点、无数据库连接——测试范围自然限定在数据处理流程

---

## 2. 代码库概览

### 2.1 测试文件清单

| 文件 | 行数 | 测试数 | 性质 |
|------|:---:|:---:|------|
| `tests/test_pipeline_contract.py` | 716 | 41 | L1: Contract tests（7 阶段 × 合约点） |
| `tests/test_e2e_smoke.py` | 400 | 19 | L2: E2E smoke tests（含 HARD GUARD） |
| `tests/test_pipeline_log.py` | 515 | 12 | 管线日志格式 + 序列化验证 |
| `tests/verify_progressive_feedback.py` | 466 | 6 | Progressive feedback 机制验证 |
| **合计** | **2097** | **78** | |

### 2.2 被测源码

| 文件 | 行数 | 说明 |
|------|:---:|------|
| `scripts/process_collection.py` | 1892 | 核心管线实现——包含所有 7 个阶段的函数 |

### 2.3 Mock 策略

由于 Infomanager 管线依赖外部服务（LLM API、平台 extractor），所有测试使用统一的 mock 策略：

```python
# 平台 extractor 统一 mock
sys.modules["extractors"] = _mock_extractors
sys.modules["extractors.platform_extractors"] = _mock_pe_module

# LLM 调用通过 patch 逐测试替换
@patch("scripts.process_collection.call_llm", return_value=mock_response)
```

优点：快速（0.18s）、确定性的、CI 友好。
局限：不验证真实 LLM 响应质量 → 需 staging 环境补充 LLM 质量回归。

---

## 3. Contract Test 矩阵

### 3.1 测试结构

所有 contract test 定义在 `test_pipeline_contract.py`。每个阶段函数被作为黑盒测试——只验证输入/输出合约，不校验内部实现细节。

### 3.2 阶段 1: parse_message() — 消息解析

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C01 | test_returns_required_fields | 返回 dict 含全部必填字段（raw_text, urls, primary_url, platform, platform_display, user_text, has_user_text, image_keys, has_images） | ✅ |
| TC-C02 | test_extracts_url_correctly | 包含 URL 消息 → primary_url 非空且正确 | ✅ |
| TC-C03 | test_no_url_message_has_empty_primary_url | 无 URL 消息 → primary_url = "" | ✅ |
| TC-C04 | test_platform_is_detected | platform / platform_display 是字符串 | ✅ |
| TC-C05 | test_has_images_is_bool | has_images / has_user_text 是 bool | ✅ |
| TC-C06 | test_image_keys_extracted_from_image_message | 图片消息提取 image_keys | ✅ |
| TC-C07 | test_returns_dict_not_none | 非 JSON 输入不崩溃（返回 dict 而非 None） | ✅ |

**合约总结**：7/7 合约点全部覆盖。源码安全网为 try/except (L382-383, L229-230)。

**边界 case 分析**：

| 场景 | 是否覆盖 | 说明 |
|------|:---:|------|
| 正常 Feishu 文本消息（含 URL） | ✅ | TC-C02 |
| 纯文本无 URL | ✅ | TC-C03 |
| 图片消息 | ✅ | TC-C06 |
| 非 JSON 输入 ("just some random text") | ✅ | TC-C07 |
| 空字符串 `""` | ⚠️ F1 | 源码 try/except 兜底，无显式断言 |
| 损坏 JSON（partial structure） | ⚠️ F2 | 源码 try/except + regex fallback 双重兜底 |

### 3.3 阶段 2: OCR — 图片处理

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C08 | test_extract_image_keys_returns_list | _extract_image_keys 返回 list | ✅ |
| TC-C09 | test_extract_image_keys_empty_for_no_image | 非图片消息返回空列表 | ✅ |
| TC-C10 | test_extract_image_keys_extracts_key | 正确提取 image_key | ✅ |
| TC-C11 | test_no_image_ocr_status | no_image 状态 | ✅ |
| TC-C12 | test_ocr_success_status | success 状态 | ✅ |
| TC-C13 | test_ocr_partial_status | partial 状态 | ✅ |
| TC-C14 | test_ocr_failed_all_status | failed_all 状态 | ✅ |

**合约总结**：7/7 合约点全部覆盖。4 种 OCR 状态机的全部路径均已验证。

### 3.4 阶段 3: extract_content() — 内容提取

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C15 | test_contract_schema | 返回 dict，schema 含 title, content, extraction_status, method | ✅ |
| TC-C16 | test_extraction_status_is_valid_value | extraction_status ∈ {success, partial, failed} | ✅ |
| TC-C17 | test_method_is_non_empty_string | method 是 non-empty string | ✅ |
| TC-C18 | test_title_is_string | title 是 string | ✅ |
| TC-C19 | test_content_can_be_empty | 提取失败场景 content 可为空字符串 | ✅ |

**合约总结**：5/5 合约点全部覆盖。

### 3.5 阶段 4: classify_content() — 内容分类

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C20 | test_returns_tags_list | 返回 tags（非空 list） | ✅ |
| TC-C21 | test_returns_new_tags_list | 返回 new_tags（list，可空） | ✅ |
| TC-C22 | test_returns_type_field | 返回 type（non-empty string） | ✅ |
| TC-C23 | test_returns_external_sources_list | 返回 external_sources（list） | ✅ |
| TC-C24 | test_handles_empty_content | 空 content → 降级（使用 title 作为 content） | ✅ |
| TC-C25 | test_fallback_when_llm_returns_garbage | LLM 返回垃圾 JSON → fallback 值 {"待分类", [], "文章", []} | ✅ |

**合约总结**：6/6 合约点全部覆盖，含 2 种降级路径（空 content + LLM 垃圾）。

### 3.6 阶段 5: summarize_content() — 内容摘要

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C26 | test_returns_summary_and_keywords | 返回 summary + keywords | ✅ |
| TC-C27 | test_summary_is_non_empty_string | summary 是 non-empty string | ✅ |
| TC-C28 | test_summary_does_not_contain_placeholder | summary 无占位符（无裸 JSON） | ✅ |
| TC-C29 | test_keywords_is_list_of_strings | keywords 是 list of strings | ✅ |
| TC-C30 | test_short_content_returns_title_as_summary | 短内容 (<100 chars) → 降级返回 title | ✅ |
| TC-C31 | test_handles_llm_failure_gracefully | LLM 返回垃圾 → fallback {title[:100], []} | ✅ |

**合约总结**：6/6 合约点全部覆盖，含 2 种降级路径（短内容 + LLM 失败）。

### 3.7 阶段 6: _reflect_on_quality() — 质量评估

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C32 | test_returns_quality_score_field | 返回 quality_score | ✅ |
| TC-C33 | test_quality_score_is_valid_value | score ∈ {high, medium, low} | ✅ |
| TC-C34 | test_failed_extraction_is_low_quality | 提取失败 → low | ✅ |
| TC-C35 | test_sufficient_content_is_high | 足够内容 → high | ✅ |
| TC-C36 | test_returns_actions_taken_list | actions_taken 是 list | ✅ |
| TC-C37 | test_quality_score_bounded | 9 种组合 (3 status × 3 content) 全遍历 | ✅ |

**合约总结**：6/6 合约点全部覆盖，含 9 种边界组合全遍历。

### 3.8 阶段 7: _enrich_sources() — 来源丰富

| # | 测试名 | 合约点 | 判定 |
|:---:|--------|--------|:---:|
| TC-C38 | test_returns_sources_found_list | sources_found 是 list | ✅ |
| TC-C39 | test_returns_actions_taken_list | actions_taken 是 list | ✅ |
| TC-C40 | test_sources_found_has_correct_schema | 每个 source 含 title, url, type | ✅ |
| TC-C41 | test_not_resource_returns_empty | 非资源文章返回空 | ✅ |

**合约总结**：4/4 合约点全部覆盖。

---

## 4. E2E Smoke Test 矩阵

所有 E2E test 定义在 `test_e2e_smoke.py`。每条 test 执行完整的管线流程（使用模拟的 Feishu 消息），验证端到端正确性。

### 4.1 核心流程验证

| # | 测试名 | 验证点 | 判定 |
|:---:|--------|--------|:---:|
| TC-E01 | test_pipeline_completes_without_exception | pipeline 执行不抛异常 | ✅ |
| TC-E02 | test_pipeline_returns_success_status | 返回 status = "done" | ✅ |
| TC-E03 | test_result_contains_all_required_fields | result 含全部必填字段 | ✅ |
| TC-E04 | test_result_title_correct | title 内容验证 | ✅ |
| TC-E05 | test_result_summary_correct | summary 内容验证 | ✅ |
| TC-E06 | test_result_tags_correct | tags 内容验证 | ✅ |
| TC-E07 | test_result_type_correct | type 内容验证 | ✅ |

### 4.2 输出文件验证

| # | 测试名 | 验证点 | 判定 |
|:---:|--------|--------|:---:|
| TC-E08 | test_result_file_exists | 输出文件存在 | ✅ |
| TC-E09 | test_vault_file_has_content | vault 文件有内容 + YAML frontmatter | ✅ |
| TC-E10 | test_vault_file_contains_title | vault 文件含标题 | ✅ |
| TC-E11 | test_result_quality_score_is_valid | quality_score ∈ {high, medium, low} | ✅ |
| TC-E12 | test_result_extraction_status_matches | extraction_status 一致性 | ✅ |

### 4.3 Pipeline Log (pipeline.jsonl) 验证

| # | 测试名 | 验证点 | 判定 |
|:---:|--------|--------|:---:|
| TC-E13 | test_pipeline_jsonl_has_nine_entries | pipeline.jsonl 含 9 条记录 | ✅ |
| TC-E14 | test_pipeline_jsonl_steps_in_order | step 顺序正确 | ✅ |
| TC-E15 | test_pipeline_jsonl_all_entries_valid | 每条含 6 个必填字段 | ✅ |
| TC-E16 | test_pipeline_jsonl_is_valid_jsonl | JSONL valid JSON | ✅ |
| TC-E17 | test_all_log_entries_have_url_field | url 字段有值 | ✅ |
| TC-E18 | test_metrics_are_dicts | metrics 是 dict | ✅ |
| TC-E19 | test_duration_ms_are_positive | duration_ms ≥ 0 | ✅ |

---

## 5. Pipeline Log 验证矩阵

定义在 `test_pipeline_log.py`（12 tests）。验证管线日志的格式、序列化和持久化行为。

| # | 测试名 | 验证点 | 判定 |
|:---:|--------|--------|:---:|
| TC-L01 | 日志文件格式 | JSONL 标准格式，每行一个 JSON object | ✅ |
| TC-L02 | 必填字段完整性 | timestamp, step, status, metrics, url 必填 | ✅ |
| TC-L03 | status 值合法性 | status ∈ {start, done, error} | ✅ |
| TC-L04 | duration_ms 计算 | start→done 间隔 ≥ 0 | ✅ |
| TC-L05 | error 场景 logging | error status + error_message 字段 | ✅ |
| TC-L06 | 日志写入失败不崩溃 | ProcessLog.write() 写失败 → silent fail | ✅ |
| TC-L07 | pipeline 抛异常仍写日志 | 管线异常 → 已有日志不丢失 | ✅ |
| TC-L08 | 并发写入安全性 | 多 step 不互相覆盖 | ✅ |
| TC-L09 | metrics 类型一致性 | 所有 metrics 值类型一致 | ✅ |
| TC-L10 | JSON 序列化正确性 | json.loads 可恢复正常解析 | ✅ |
| TC-L11 | 大字段截断行为 | 超长字段不破坏 JSONL | ✅ |
| TC-L12 | 增量写入 | step 写入不覆盖已有记录 | ✅ |

---

## 6. Progressive Feedback 验证

定义在 `verify_progressive_feedback.py`（6 tests）。验证管线运行时将中间结果（如分类、摘要）写入 vault 文件以支持渐进式用户回看。

| # | 测试名 | 验证点 | 判定 |
|:---:|--------|--------|:---:|
| TC-PF01 | 分类结果写入 | classify 阶段完成后 vault 文件已含分类数据 | ✅ |
| TC-PF02 | 摘要结果写入 | summarize 阶段完成后 vault 文件已含摘要 | ✅ |
| TC-PF03 | enrichment 写入 | _enrich_sources 阶段完成后 sources 已附加 | ✅ |
| TC-PF04 | feedback 写入顺序 | 写入顺序 = 管线执行顺序 | ✅ |
| TC-PF05 | feedback 不覆盖已有字段 | 后续写入 append 而非覆盖 | ✅ |
| TC-PF06 | 异常不阻断 feedback | 某阶段失败 → 之前阶段 feedback 仍保留 | ✅ |

---

## 7. 边界 Case 覆盖分析

| # | 边界场景 | 测试 | 覆盖 | 风险评级 |
|:---:|-----------|--------|:---:|:---:|
| 1 | 空 URL 消息 | TC-C03 | ✅ | — |
| 2 | 空 content（提取失败） | TC-C19, TC-C34 | ✅ | — |
| 3 | 短内容降级 (<100 chars) | TC-C30 | ✅ | — |
| 4 | LLM 返回垃圾 JSON | TC-C25, TC-C31 | ✅ | — |
| 5 | 非 JSON 原始输入 | TC-C07 | ✅ | — |
| 6 | 日志写入磁盘失败 | TC-L06 | ✅ | — |
| 7 | 管线异常仍写日志 | TC-L07 | ✅ | — |
| 8 | quality_score 9 组合全遍历 | TC-C37 | ✅ | — |
| 9 | 空字符串 `parse_message("")` | ⚠️ F1 | ⚠️ | 低风险 |
| 10 | 损坏的 Feishu JSON | ⚠️ F2 | ⚠️ | 低风险 |
| 11 | 超大输入 (> 100K chars) | 未覆盖 | ❌ | 低风险 |
| 12 | Unicode 异常字符 | 未覆盖 | ❌ | 低 - LLM 可能行为怪异 |
| 13 | 并发管线调用 | TC-L08 | ✅ | — |
| 14 | 所有平台 extractor 同时失败 | 部分覆盖 | ⚠️ | 中 - LLM fallback 覆盖，全平台 extractor 未 mock 全 fail |

---

## 8. 降级路径 (HARD GUARD) 验证

当 URL 提取失败时（如消息不含链接），管线不应崩溃——应走降级路径继续处理。4 条 HARD GUARD 测试验证此能力：

| # | 测试名 | 验证点 | 判定 |
|:---:|--------|--------|:---:|
| TC-HG01 | test_pipeline_handles_extraction_failure | 提取失败 → 管线仍正常完成 | ✅ |
| TC-HG02 | test_hard_guard_missing_url_extraction_failed | 无 URL → extraction_status = "failed" | ✅ |
| TC-HG03 | test_hard_guard_write_still_executes_on_failed_extraction | 无 URL → 仍写文件到 vault | ✅ |
| TC-HG04 | test_hard_guard_complete_step_sequence_present | 无 URL → 全步骤保留（不跳过） | ✅ |
| TC-HG05 | test_hard_guard_url_field_empty_on_missing_url | 无 URL → url = ""（非 None） | ✅ |

**源码对应**：
- `_find_existing_by_url()` (L1212-1244) 有空 URL 检查：`if not url or not url.strip(): return None` (L1219-1220)
- 降级路径确保空 URL 不触发去重匹配，不导致管线崩溃

---

## 9. 新标准维度交叉检查

按 QA 发现分级标准 v1.0 的判定维度，逐项检查 P0-06 测试覆盖：

### 9.1 安全漏洞（标准 §2 + 附录 B OWASP Top 10）

| OWASP 类别 | 风险 | 测试覆盖？ |
|-----------|:---:|:---:|
| A1 访问控制失效 | 无 — 无用户认证/授权 | N/A |
| A2 加密失效 | 无 — 无敏感数据传输 | N/A |
| A3 注入 | 无 — 无 SQL/命令执行 | N/A |
| A4 不安全设计 | 无 — 离线批处理 | N/A |
| A5 安全配置错误 | 无 — 无服务端口 | N/A |
| A6 易受攻击组件 | 依赖库检查未覆盖 → 建议补充 `pip-audit` | ⚠️ |
| A7 身份认证失效 | 无 — 无认证流程 | N/A |
| A8 完整性失效 | 低 — 输入经过 JSON 解析 | ✅ try/except |
| A9 日志监控失效 | 中 — pipeline.jsonl 在磁盘可被篡改 → 非安全风险（运维问题） | N/A |
| A10 SSRF | 无 — 测试全部 mock 网络 | N/A |

### 9.2 性能退化（标准 §3）

| 指标 | 当前值 | 基线 | 判定 |
|------|:---:|:---:|:---:|
| 全量测试运行时间 | 0.18s | N/A | N/A — 无 APM baseline |
| 单管线执行时间 | < 1s（mock 环境） | N/A | Fallback < 1s → MINOR |
| 内存使用 | 未测量 | — | 建议补充内存 profiling |

**注意**：78 个测试运行 0.18s 是因为所有 LLM/网络调用被 mock。真实管线性能需 staging 环境测量。

### 9.3 数据敏感度（标准 §4 + 附录 A）

| 数据类别 | 敏感度 | 测试覆盖 | 加权适用？ |
|---------|:---:|------|:---:|
| 文章标题/内容 | B 级 | ✅ | 不加权 |
| Tags / keywords | B 级 | ✅ | 不加权 |
| pipeline.jsonl（管线日志） | C 级 | ✅ | 按正常公式 |
| Vault 文件 | B 级 | ✅ | 不加权 |
| Feishu message_id / user_id | A 级（用户 ID） | 未专门测试 PII 不泄露 | ⚠️ 低风险 |

**关键**：Infomanager 处理的是已分享的文章链接内容（B 级），不涉及资金（S 级）或用户核心信息（A 级）。唯一需关注的是 Feishu message_id / user_id 不应明文写入 vault。

### 9.4 论证流程合规（标准 §6）

由于 P0-06 是测试建设任务而非 bug 修复任务：

| 流程步骤 | 状态 | 说明 |
|---------|:---:|------|
| QA 发现 | N/A | 非 bug 发现——是测试覆盖建设 |
| 研发评估 | N/A | N/A |
| 通过/驳回/暂缓 | N/A | 无争议点 |
| 申诉路径 | N/A | N/A |

### 9.5 SLA 符合性（标准 §8）

| 检查项 | 状态 | 说明 |
|--------|:---:|------|
| 测试执行时间 | < 1s | 远超任何 SLA 要求 |
| 78 测试通过率 | 100% | 无 flaky test |
| CI 集成 | 待确认 | 当前为本地执行，需集成到 CI pipeline |

---

## 10. Findings 分级

按标准 §1.2 五步判定公式，逐条分析 2 个边界缺失：

### F1: `parse_message("")` 无显式测试

```
前置检查：
  └─ 安全漏洞？→ 否（不涉及 OWASP Top 10 范畴）

正式判定：
  步骤 E — 用户可感知？→ 否
    - 空字符串输入是内部边缘 case
    - Feishu webhook 不会发送空消息
    - 即使发生也不会暴露给终端用户
  步骤 F — 功能阻断？→ 否（源码 try/except 兜底）
  步骤 W — 有 workaround？→ N/A
  步骤 D — 数据敏感度？→ B 级（不加权）
  步骤 P — 性能退化？→ 不相关

→ SUGGESTION
```

标准对照：§1.3「用户不可感知（非安全漏洞/非数据完整性/非系统健康度）→ SUGGESTION」。

### F2: 损坏的 Feishu JSON 无专门测试

```
前置检查：
  └─ 安全漏洞？→ 否

正式判定：
  步骤 E — 用户可感知？→ 否
    - Feishu webhook 不会发送损坏 JSON
    - 即使损坏，try/except + regex fallback 双重兜底
    - 终端用户不可感知
  步骤 F — 功能阻断？→ 否（有安全网）
  步骤 W — 有 workaround？→ N/A
  步骤 D — 数据敏感度？→ B 级
  步骤 P — 性能退化？→ 不相关

→ SUGGESTION
```

### 综合结论

| 发现 | 级别 | 标准引用 | 影响发版？ |
|------|:---:|---------|:---:|
| F1: parse_message("") 无显式测试 | SUGGESTION | §1.3 | 否 |
| F2: 损坏 JSON 无专门测试 | SUGGESTION | §1.3 | 否 |

---

## 11. 发布门禁评估

按标准 §10 发布门禁公式：`BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉`

| 门禁项 | 当前状态 | 说明 |
|--------|:---:|------|
| BLOCKER=0？ | ✅ | 0 BLOCKER 发现 |
| MAJOR≤N？ | ✅ | 0 MAJOR 发现 |
| 安全漏洞=0？ | ✅ | 无已知安全漏洞 |
| 无未裁定申诉？ | ✅ | 无申诉 |
| 78/78 测试通过？ | ✅ | 100% pass rate |
| 回归范围声明？ | ✅ | 7 阶段 contract 全覆盖 + 4 HARD GUARD |

**门禁结论：通过 ✅ ——无阻塞项，满足发版条件。**

按 §10 回归测试范围：

| 修复级别 | 触发场景 | 回归范围 | 时间预算 |
|---------|---------|---------|:---:|
| BLOCKER | 管线核心逻辑变更 | 修复模块 + 1 级依赖 + E2E 冒烟 | 4h |
| MAJOR | 非核心逻辑变更 | 修复模块 + contract 回归 | 2h |
| MINOR | 日志/feedback 变更 | 对应模块 contract + 1 关键场景 | 1h |
| SUGGESTION | 文档/注释/命名 | 无需回归 | — |

---

## 12. 测试执行与维护

### 12.1 执行命令

```bash
# 全量运行（推荐）
cd /workspace/InfoManager && python -m pytest tests/ -v

# 仅 contract tests
cd /workspace/InfoManager && python -m pytest tests/test_pipeline_contract.py -v

# 仅 E2E smoke tests
cd /workspace/InfoManager && python -m pytest tests/test_e2e_smoke.py -v

# 仅 pipeline log tests
cd /workspace/InfoManager && python -m pytest tests/test_pipeline_log.py -v

# 显示覆盖率（需 pytest-cov）
cd /workspace/InfoManager && python -m pytest tests/ -v --cov=scripts.process_collection --cov-report=term
```

### 12.2 执行环境要求

| 依赖项 | 版本 | 说明 |
|--------|------|------|
| Python | ≥ 3.10 | 项目最低要求 |
| pytest | ≥ 7.0 | 测试框架 |
| 操作系统的临时目录 | 可写 | Tempmdir 用于隔离测试 |

### 12.3 已知局限

| 局限 | 影响 | 缓解措施 |
|------|------|---------|
| 所有 LLM 调用被 mock | 不验证 LLM 响应质量 | staging 环境补充 LLM 质量回归 |
| 无真实网络调用 | 不验证平台 extractor | 需 staging 环境用真实 URL 测试 |
| 未测量内存使用 | 不知真实内存 profile | 补充 memory profiling CI step |
| 依赖库安全未检查 | 可能有已知 CVE | 补充 `pip-audit` 到 CI |
| 无 chaos testing | 不验证极端异常 | 暂非优先级 |

### 12.4 维护建议

1. **源码变更 → 同步更新 contract**：process_collection.py 的函数签名或返回结构变更时，必须同步更新对应的 contract test
2. **新增管线阶段 → 补 contract**：如新增第 8 个阶段，按本方案的 contract test 模板补齐
3. **Flaky test 处理**：当前 0 flaky。如出现 → 先标记 `pytest.mark.xfail` + 创建 MAJOR bug
4. **CI 集成**：建议在 GitHub Actions / GitLab CI 中添加 `python -m pytest tests/ -v` 作为必过门禁

---

## 13. 可扩展性建议

### 13.1 短期（当前版本）

| # | 建议 | 优先级 | 工作量 |
|---|------|:---:|:---:|
| 1 | 补充 `pip-audit` 依赖库安全检查 | MINOR | 0.1h |
| 2 | 补充 F1/F2 的显式测试（2 tests） | SUGGESTION | 0.2h |
| 3 | 为超大输入 (>100K chars) 添加边界 test | SUGGESTION | 0.2h |

### 13.2 中期（下版本）

| # | 建议 | 优先级 | 工作量 |
|---|------|:---:|:---:|
| 4 | staging 环境 LLM 质量回归测试（用真实 LLM） | MAJOR | 2h |
| 5 | 补充所有平台 extractor 全 fail 场景的端到端测试 | MAJOR | 1h |
| 6 | 内存 profiling CI step（监控泄漏） | MINOR | 1h |
| 7 | PII 泄露检查——确保 Feishu user_id/message_id 不写入 vault | MAJOR | 0.5h |

### 13.3 长期（下下版本）

| # | 建议 | 优先级 | 工作量 |
|---|------|:---:|:---:|
| 8 | chaos testing：模拟磁盘满、网络超时、LLM 超时等极端场景 | MINOR | 3h |
| 9 | 基于 APM 的性能回归基线（真实管线执行时间的 3x/10x 告警） | MAJOR | 4h |

---

## 附录 A: 测试文件交叉引用

| 标准条款 | 涉及测试 | 文件 |
|---------|---------|------|
| §1.2 判定公式 | N/A（本文件为测试方案） | — |
| §2 安全漏洞 | TC-C07（非 JSON 输入安全网） | test_pipeline_contract.py |
| §3 性能退化 | TC-E19（duration_ms ≥ 0） | test_e2e_smoke.py |
| §4 数据敏感度 | N/A（B 级不加权） | — |
| §6 论证流程 | N/A | — |
| §8 SLA | N/A（测试执行时间 0.18s） | — |
| §10 发布门禁 | 全量测试作为门禁 | 所有测试文件 |
| §11 产品红线 | N/A（无 BLOCKER） | — |

---

## 附录 B: 测试统计总结

```
测试文件:          4
测试总数:         78
通过数:           78
失败数:            0
跳过数:            0
运行时间:          0.18s
Contract 阶段:      7
Contract 合约点:   38
E2E 测试数:        19
HARD GUARD 路径:    4
降级路径:           4（空 content, 短 content, LLM 垃圾, 空 URL）
安全漏洞发现:       0
BLOCKER 发现:       0
MAJOR 发现:         0
MINOR 发现:         0
SUGGESTION 发现:    2
```

---

> **方案状态**：已完成重审 — 78/78 测试通过，发布无阻塞项。
>
> 本方案适用于当前版本（commit `3e32e2b`）的 Infomanager 管线。源码变更时需同步更新本方案。
