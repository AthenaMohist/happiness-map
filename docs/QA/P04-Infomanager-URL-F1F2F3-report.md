# QA 测试报告：P04 Infomanager URL 修复 (F1/F2/F3)

> 日期：2026-07-09 | QA：game-qa | 父任务：t_3e2718fc
> 依从标准：`docs/standards/qa-finding-classification.md` v1.0

---

## 1. 测试方法

### 1.1 独立验证步骤

1. **代码审查**：逐行审查 process_collection.py 中 F1/F2/F3 改动
2. **已有测试重跑**：独立运行 test_merge.py (14 项) + test_f3_url_boundary.py (15 项)
3. **新增边界测试**：编写 test_qa_boundary.py (31 项)，覆盖已有测试未触及的边界
4. **交叉分析**：验证 F1+F3 交互路径

### 1.2 测试环境

```
Python: 3.11.15
pytest: 9.1.1
目标文件: /workspace/InfoManager/scripts/process_collection.py
已有测试: test_merge.py, test_f3_url_boundary.py
新增测试: test_qa_boundary.py
```

---

## 2. 测试结果概览

| 编号 | 修复 | 改动规模 | 已有测试 | 边界测试 | 结论 |
|:--:|------|:--:|:--:|:--:|:--:|
| F1 | 空URL管道拒绝 | +12行 | — | 5/6 PASS | ⚠️ 1项发现 |
| F2 | merge_to_existing URL guard | +3行 | 14/14 PASS | 4/4 PASS | ✅ 通过 |
| F3 | URL regex边界 | +51行 | 15/15 PASS | 17/17 PASS | ✅ 通过 |

**已有测试总计**：29/29 PASS
**新增边界测试**：30/31 PASS（1项真实发现）

---

## 3. 逐项详细验证

### 3.1 F1 — 空URL管道拒绝（+12行，line 1854-1864）

**改动**：在 `process()` 中添加空消息前置检查：
```python
if (not parsed.get("primary_url")
        and not parsed.get("has_user_text")
        and not parsed.get("has_images")):
    result["status"] = "rejected_empty"
    ...
    return result
```

**验证结果**：

| 测试 | 输入 | 预期 | 实际 | 结果 |
|------|------|------|------|:--:|
| F1.1 | `""` 空字符串 | rejected_empty | rejected_empty | ✅ |
| F1.2 | `"  \n  \t  "` 纯空白 | rejected_empty | rejected_empty | ✅ |
| F1.3 | `"https://example.com/article"` URL | 不拒绝 | 不拒绝 | ✅ |
| F1.4 | `"这是一篇好文章"` 纯文本(7字) | 不拒绝 | **rejected_empty** | ❌ |
| F1.5 | `"👍🎉"` 纯emoji | rejected_empty | rejected_empty | ✅ |
| F1.6 | `{"event":{"message":{"content":"{\"image_key\":\"img_test123\"}"}}}` 图片消息 | 不拒绝 | 不拒绝 | ✅ |

**发现 #QA-F1-01**：F1 使用 `has_user_text`（阈值 20 字符）作为非空判断，导致短文本消息（<20 字符，无 URL，无图片）被错误拒绝。

**详细分析**：
- `parse_message()` 中 `has_user_text = len(non_url_text) >= 20`（line 636）
- 但对于 <20 字符的纯文本消息，`extract_content()` 有 `direct_text` fallback（line 677-682）
- F1 的前置检查在 extract_content 之前执行，阻止了 fallback 路径
- 影响范围：所有纯文本消息（无URL/图片）且文本长度 1-19 字符
- 受影响消息示例：`"好"`、`"你好"`、`"这是一篇好文章"`、`"这篇文章写得非常好，推荐大家阅读收藏"` (18字)

**判定**（依从标准 §1.2）：
```
用户可感知：✅（用户消息被静默丢弃，无任何反馈）
功能阻断：✅（合法消息无法被处理）
workaround：⚠️ 用户需添加URL或将文本扩展到20+字符（用户不知道阈值）
→ MAJOR（用户可感知 AND 功能阻断，但存在用户端 workaround）

非安全漏洞，非数据一致性问题，非性能问题
```

**修复建议**：
```python
# 方案A：在 F1 guard 中也检查 title 是否非空
if (not parsed.get("primary_url")
        and not parsed.get("has_user_text")
        and not parsed.get("has_images")
        and not (parsed.get("user_text") or "").strip()):  # 加上 user_text
```
```python
# 方案B：改用 non_url_text 长度 >= 2 而非 20
# 在 parse_message() 中将 has_user_text 阈值从 20 降为 2
```
预计修复工时：0.15h（2行改动 + 测试更新）

### 3.2 F2 — merge_to_existing URL guard（+3行，line 1608-1610）

**改动**：在 `merge_to_existing()` 中保护已有 URL 不被空值覆盖：
```python
# F2: guard — don't overwrite existing URL with empty/whitespace on merge
new_url_clean = (new_url or "").strip()
preserved_url = new_url_clean if new_url_clean else old_fm.get("url", "")
```

**验证结果**：

| 测试 | 场景 | 预期 | 实际 | 结果 |
|------|------|------|------|:--:|
| F2.1 | `write_to_vault(url="")` → 跳过 find_existing | 不触发 merge | is_merge=False | ✅ |
| F2.2 | `merge_to_existing(new_url="")` + 已有URL | 保留已有 URL | url=已有URL | ✅ |
| F2.3 | `merge_to_existing(new_url="   ")` + 已有URL | 保留已有 URL | url=已有URL | ✅ |
| F2.4 | `merge_to_existing(new_url="https://new")` | 使用新 URL | url=新URL | ✅ |

**双层防护确认**：
1. `write_to_vault()` L1691：`if url and url.strip():` — 空URL不进 merge 分支
2. `merge_to_existing()` L1608-1610：即使 merge 被触发，也保护已有 URL
3. `_find_existing_by_url()` L1399：`if not url or not url.strip(): return None` — 空URL永不匹配

**结论**：F2 实现正确，三重空URL防护无遗漏。全部 4/4 边界测试通过。

### 3.3 F3 — URL regex 边界（+51行，line 488-537）

**改动**：新增 `_strip_url_trailing()` 和 `_extract_urls()`，三段式清理：
1. 在首个中文全角标点处截断
2. 剥离尾部 ASCII 标点
3. 仅剥离不平衡的尾部 `)`

**验证结果**：

| 测试 | 输入 | 预期输出 | 结果 |
|------|------|------|:--:|
| F3.1 | `url/path]` | `url/path` | ✅ |
| F3.2 | `url/path]]` | `url/path` | ✅ |
| F3.3 | `url/clean-path` | `url/clean-path` | ✅ |
| F3.4 | `C_(language)。` | `C_(language)` | ✅ |
| F3.5 | `url/page\nnext` | `url/page` | ✅ |
| F3.6 | `url?q=test,` | `url?q=test` | ✅ |
| F3.7 | `url#section1;` | `url#section1` | ✅ |
| F3.8 | Multi-URL + 中英标点 | 两个干净URL | ✅ |
| F3.9 | `url:8080/admin.` | `url:8080/admin` | ✅ |
| F3.10 | `(url/path(v2))` | `url/path(v2)` | ✅ |
| F3.11 | `(url/path(v2)))` | `url/path(v2)` | ✅ |
| F3.12 | `url/page！` | `url/page` | ✅ |
| F3.13 | `url/article】` | `url/article` | ✅ |
| F3.14 | `""` 空文本 | `[]` | ✅ |
| F3.15 | 无URL文本 | `[]` | ✅ |
| F3.16 | `url/path%5Dvalue` | 保留 `%5D` | ✅ |
| F3.17 | `url/page，` | `url/page` | ✅ |

**已有 test_f3_url_boundary.py 重跑**：15/15 PASS

**结论**：F3 实现正确，中英文标点、嵌套括号、多URL、空文本等边界全部正确处理。全部 17/17 边界测试通过，叠加已有 15 项测试 = 32/32。

### 3.4 交叉验证：F1 + F3 交互

| 测试 | 场景 | F3处理 | F1判断 | 结果 |
|------|------|--------|--------|:--:|
| X.1 | `"url/path, 中文文本"` | F3 剥离逗号 → clean URL | F1 检测到 primary_url → 不拒绝 | ✅ |

F1 和 F3 不冲突。

---

## 4. 结构化 Claims

### Claim 1: F2 修复完成且无遗漏
- **内容**：merge_to_existing URL guard 正确实现，三重防护（write_to_vault + merge_to_existing + _find_existing_by_url）覆盖所有空URL路径
- **状态**：✅ VERIFIED — 4/4 边界测试通过

### Claim 2: F3 修复完成且无遗漏
- **内容**：URL regex 三段式边界清理正确处理中英标点、嵌套括号、多URL场景
- **状态**：✅ VERIFIED — 15/15 已有测试 + 17/17 新增测试 = 32/32

### Claim 3: F1 修复基本正确但存在边界遗漏
- **内容**：空消息管道拒绝功能正确，但 `has_user_text` 20字符阈值导致短文本消息被错误拒绝
- **状态**：⚠️ PARTIAL — 核心功能正确，发现 MAJOR 级边界遗漏 (#QA-F1-01)
- **修复**：需在 F1 guard 中添加对短文本的考虑（预计 2 行改动）

### Claim 4: 发布门禁状态
- **内容**：当前 BLOCKER=0, MAJOR=1(#QA-F1-01), 安全漏洞=0, 无未裁定申诉
- **状态**：⚠️ 可通过（MAJOR≤3 临界），但建议修复 #QA-F1-01 后再发布

---

## 5. 发现清单

| 编号 | 级别 | 描述 | 位置 | 建议修复 |
|------|:--:|------|------|------|
| #QA-F1-01 | **MAJOR** | F1 guard 使用 `has_user_text`(阈值20) 判断非空，导致短文本消息被错误拒绝 | L1854-1857 | guard 中增加 `parsed["user_text"]` 检查或降阈值至 2 |

### 5.1 #QA-F1-01 分级论证

依从标准 §1.2 判定：
```
安全漏洞？→ 否
用户可感知？→ 是（用户消息被静默丢弃，无反馈）
功能阻断？→ 是（合法消息无法被处理）
workaround？→ 是（用户添加URL或将文本扩展至20+字符可绕过）
→ MAJOR：用户可感知 AND 功能阻断但有 workaround
```

---

## 6. 门禁判定

```
发布门禁公式：BLOCKER=0 AND MAJOR≤3 AND 安全漏洞=0 AND 无未裁定的申诉

当前状态：
  BLOCKER   = 0 ✅
  MAJOR     = 1 ⚠️ (≤3，通过)
  安全漏洞   = 0 ✅
  未裁定申诉 = 0 ✅

结论：门禁通过，可发布。建议在发布前修复 #QA-F1-01（2行改动）。
```

---

## 7. 测试产物

| 文件 | 行数 | 用途 |
|------|:--:|------|
| `/workspace/InfoManager/scripts/test_qa_boundary.py` | ~250 | 新增 QA 边界测试（31项） |
| 已有 `test_merge.py` | 637 | Merge 测试（14项，全部通过） |
| 已有 `test_f3_url_boundary.py` | 45 | F3 URL 测试（15项，全部通过） |
