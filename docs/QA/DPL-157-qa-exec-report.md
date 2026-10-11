# DPL-153/157 QA-EXEC 报告 — t_8b793888（INF-018）

- 作者: game-qa（QA-EXEC）｜日期: 2026-09-10
- 上游: QA-D1 t_69960b58（方案 docs/QA/DPL-157-qa-d1-test-plan.md + qa_d1_scripts.py，commit 0813a52）
- 被测: /workspace/InfoManager main @ 0d38a72（R1-R3=dc7f8b6/66b7604，R4=2c21d6f，只读）
- 分级依据: docs/standards/qa-finding-classification.md §1.2

## 1. 执行结果（只跑本卡子集，DPL-136/137）

| 项 | 结果 |
|---|---|
| E1 QA-D1 自有脚本复跑 qa_d1_scripts.py | **7/7 PASS, 0 FAIL/ERROR**（TC-Q1~Q7） |
| E2 验收子集 `pytest tests -k "toutiao or message_id or url"` | **31 passed, 133 deselected**（42s，无新失败） |
| E3 AC8 真网回放 | **FAIL → 见发现 F-1**（证据链完整，非环境臆断） |

## 2. 发现

### F-1（MAJOR）R4 Stage1 提图解析器与真实 API 响应格式不匹配 → image-only 头条 OCR 兜底真网恒空转

- 判定公式对照（§1.2）: 用户可感知（头条图片型文章正文仍提取不到，OCR 兜底形同虚设）AND 功能阻断（本 feature 的核心场景 AC8 无 workaround）AND 非安全漏洞 → **MAJOR**（不满足 BLOCKER：有 fail-open 不阻塞入库，数据不丢）。
- 复现（行为级，2026-09-10 实测）:
  1. 真网调 `_headless_toutiao_ocr_fallback("https://m.toutiao.com/w/1875751979183364/")` → 返回 `ok=False, image_count=0, ocr_status=failed, source=none`。
  2. 直接请求同一 API `m.toutiao.com/api/pc/detail/?group_id=1875751979183364`（message=success）→ `data.content` 是**嵌套 JSON 字符串**（`rich_content.spans[].images[]` 含 3 个 `web_uri`，尺寸 1242×1660），**不存在任何 `<img src=...>` 标签**。
  3. 而 process_collection.py:1380 用 `re.findall(r'<img[^>]+src="([^"]+)"', content)` 提图 → 恒为 `[]` → Stage2 永不执行。
  4. Stage3 chrome `--dump-dom` 对 www/m 站均渲染不出图片（实测 DOM len 5059/0 imgs，www 站超时）→ 全链路失败。
- 佐证: AC6 样例"图片数=3"与 API 实际返回 3 张图一致——数据在，只是解析器读不到。
- SLA 对照（§8）: MAJOR 建议随下个迭代窗口修复；本报告即研发评估输入。
- 建议修复方向（供研发评估，QA 不改码）: Stage1 先 `json.loads(content)` 取 `rich_content` 遍历 `images[].web_uri` 拼 CDN URL（`https://p3-sign.toutiaoimg.com/{web_uri}~noop.image`），保留 `<img>` 正则做旧格式兼容。

### F-2（SUGGESTION）真网 CDN 下载对 sandbox 出口 403（带 Referer/UA 均 403，curl 等效复现）

- 即使 Stage1 修好，本 sandbox 环境下载 toutiaoimg CDN 会被 403（疑似风控按出口 IP 拦截）。fix 后的 AC8 真网回放需在可直连头条 CDN 的环境（或加代理配置）复核。
- 非缺陷，环境约束记录，不阻塞发版。

## 3. 结论

- mock/逻辑面（TC-Q1~Q7、AC1-AC5、AC7）：全绿，31/31 子集回归绿，**R1-R3 质量确认**。
- AC8 真网面：**未达成**（F-1 MAJOR）——R4 三段式在真网 image-only 场景下无法产出 OCR 内容。
- 发布门禁（§10）建议: MAJOR=1 ≤3 形式上可发，但本 feature（R4）的核心价值场景未兑现，建议 OC 开 FIX 卡修复 F-1 后由 QA 复测 AC8，再关 INF-018 链。

## 4. 证据文件

- 脚本复跑输出: 本报告 §1（QA 会话终端留痕 /tmp/qa_exec_t879/）
- 诊断链: ac8_replay3.py（fallback 真网调用）、ac8_diag3/5.py（API 嵌套 JSON + web_uri×3）、ac8_diag6.py + chrome 超时实测（Stage3 空 DOM）、ac8_equiv.py + ac8_cdn.py（web_uri 拼 CDN 403）
