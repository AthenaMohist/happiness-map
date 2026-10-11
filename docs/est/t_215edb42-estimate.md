# 工作量评估 — t_215edb42（INF-014 OCR 图片检测缺陷——依赖配齐 + hard_guard 测试修正）

- 评估人: game-engine（est）| 日期: 2026-10-06
- 输入: PRD `mem-core/wiki/projects/devppl/prd/inf014-ocr-image-detection-prd.md`（v1.0）+ ARCH `mem-core/wiki/projects/devppl/arch/arch-inf014-ocr-deps-and-guard.md`（v1.0，前棒 t_dab0b897，D1-D6 已全部实锚 InfoManager main 36ba1ac）

## 范围盘点

| 项 | 内容 | 预估（基准） |
|----|------|------|
| R1-环境 | 安装 tesseract-ocr + tesseract-ocr-chi-sim + google-chrome/chromium + pip pytesseract/pillow；**sudo 权限不确定，装包失败需上报 OC 派运维**（PRD §5 预案） | 3-8 轮（含重试/兜底沟通） |
| R1-代码 | D1 `_ocr_deps_probe()`（~15 行）+ D2 chrome 别名链（~5 行）+ D3 启动自检 ERROR+飞书一次告警（~10 行）+ D4 deploy-guide/requirements.txt | 3-5 轮 |
| R1-测试 | 新增 test_ocr_deps_probe（mock shutil.which/sys.modules，不依赖真实环境） | 2-3 轮 |
| R2 | D5 两个腐化用例改 R3 新语义（url_missing 短序列 + 有 URL 全链 9-step），纯测试改动 | 2-4 轮 |
| 门禁回归 | `pytest tests -k "toutiao or message_id or url"` 0 failed + AC-A2 日志断言 | 1-2 轮 |
| 收尾链固定预算 | merge 后验证 / WIP 笔记 / claim 六字段 / finalize / 飞书推送 | +8 轮 |

## 结论

- 基准实现轮 ~14-24 + 收尾 +8 → 按校准口径（K=2.32）总轮次 **预估 25-35 轮**（主要不确定性 = 环境装包 sudo/网络，属不可控外部变量）。
- **>20 轮 → 拆卡（SPLIT: 2 parallel）**，与 PRD §3 一致：
  1. **R1 卡**：环境配齐 + D1-D4 代码/文档 + test_ocr_deps_probe + AC-A2 预估 20-28 轮（若 sudo 缺失升级 OC，轮次含沟通损耗）
  2. **R2 卡**：hard_guard 两用例修正 + 门禁子集回归 预估 8-14 轮
- 两卡改动不相交（R1 在 process_collection.py/docs/requirements，R2 仅 tests/test_pipeline_log.py），可并行；AC-A3 全绿依赖 R1 环境配齐后复验（R2 卡内先按本机现状验「腐化用例转绿」，环境依赖项由 R1 卡收口时复跑）。
- 复杂度: 中。风险点：① 沙箱无 sudo → R1 兜底降级为「告警显性化 + 部署清单」，AC-A1 须运维节点真实跑；② chromium WSL 依赖杂 → D2 别名链已备，claim 显式声明命中二进制。
