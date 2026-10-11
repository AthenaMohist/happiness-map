# DPL-153/157 QA-D1 测试方案 — InfoManager 头条卡片链接丢失反查兜底

- 卡: t_69960b58（[DEV-QA-D1]）｜作者: game-qa｜日期: 2026-09-10
- PRD: mem-core wiki/projects/devppl/prd/dpl153-toutiao-card-msgid-fallback-prd.md（v1.0）
- ARCH: mem-core wiki/projects/devppl/arch/arch-dpl153-toutiao-card-msgid-fallback.md（v1.1，§1.1 D1-D3 + AC8）
- 被测代码: /workspace/InfoManager main @ 2c21d6f（只读运行；QA 不改代码）
- 方案独立性: 本方案与测试脚本由 QA 依据 PRD §4 + ARCH §2-§5 独立产出，非研发脚本事后追认

## 1. 用例矩阵（每条含通过标准）

| TC | 需求 | 场景 | 行为级断言 | 通过标准 |
|---|---|---|---|---|
| TC-Q1 | R1/AC1 | message_id 经 pipeline_state 真实 SQLite 持久化（临时库，非 mock）后读回 | record→get 往返值一致；空记录返回 ""；DB 异常 fail-open 不抛 | 往返一致且无异常 |
| TC-Q2 | R1/ARCH D1 | CLI_MESSAGE_ID 与 pipeline_state 值并存 | 反查链取 CLI 值（msg_source=cli_arg），fetch 收到 CLI 的 om_id | fetch 参数 == CLI 值 |
| TC-Q3 | R1/AC2 | gateway.log 窗口内 2 条 om_id / 唯 1 条 / 仅窗外的旧时间戳 | 多条→空集不猜；唯一→返回该 id；窗外→空集 | 三分支均符合宁缺毋错 |
| TC-Q4 | R2/AC3+AC4 | 闸门单测：高相似 og:title / 无关 og:title / 网络失败 / 无 og:title | 高相似 True；无关 False 且 dice 可观测；失败与缺 og 均 fail-closed False | False 路径不放行 |
| TC-Q5 | R3/AC5 | 反查全失败触发 url_missing 分支（自建 mock 驱动 process()） | vault meta 含 ocr_skipped_reason=url_missing + url_source=none；ERROR 行 message 以 ocr_skipped: 开头；extraction_status=failed | 字段/日志/状态三齐 |
| TC-Q6 | R4/AC7 | chrome 与网络全不可用调用 _headless_toutiao_ocr_fallback | ok=False、ocr_status=failed、不抛异常 | fail-open 无 silent success |
| TC-Q7 | R4/AC6 逻辑面 | API 提图 3 张 + OCR 全成功 / 部分 OCR 失败 | ocr_status=ok / partial；text 含 OCR 内容；image_count 正确 | 状态机 ok>partial>failed 正确 |

### AC8（ARCH §1.1 D2 锁定）处置
om_x100b6510e9b7a8a0c44e45fac661153 真网回放依赖外部飞书 API/头条 CDN 实时可用性，QA-D1 层以 mock 等价覆盖三段式与触发点（TC-Q6/Q7）；真网样例回放留给 QA-EXEC/复测节点在环境可用时执行，本卡不冒充真网结果。

## 2. 覆盖与门禁

- 只跑本卡子集：QA 自有脚本 + `pytest tests/ -k "toutiao or message_id or url"`（禁全量，DPL-137）。
- 已知预存问题：`scripts/test_f3_url_boundary.py` 顶层 exit() 致裸 pytest -k INTERNALERROR（VA 报告留痕，非本链引入）——scope 锁定 `tests/`。
- 分级依据：docs/standards/qa-finding-classification.md §1.2。
