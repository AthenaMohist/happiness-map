# PRD: QA 发现分级标准

> 作者：许清楚（产品） | 日期：2026-07-09 | 版本：v1.0
> 依据：Roundtable R1+R2 四方共识（产品/架构/研发/QA），Frank R3 最终平衡

## 1. BLOCKER — 不修不发版

触发条件：功能阻断且无 workaround；认证绕过/数据泄露/远程注入等安全漏洞；S 级数据（资金/资产/订单）一致性问题；P95 ≥ 10x 基准或 OOM/崩溃。

权限：QA 初标，研发可驳回（须附理由），QA 可申诉至产品，产品裁定终审。BLOCKER 暂缓须 Frank 签字。

门禁：BLOCKER = 0。

## 2. MAJOR — 发版标注 known issue

触发条件：功能阻断但有 workaround，或体验严重退化；非 BLOCKER 级安全漏洞（XSS/CSRF/SSRF）；A 级数据一致性问题；P95 ≥ 3x 基准；PII 泄露。

门禁：MAJOR ≤ 3。

## 3. MINOR — 用户可感知但不影响核心任务完成。不阻塞发版。

## 4. SUGGESTION — 用户不可感知（非安全/非数据完整性/非系统健康度）或纯主观偏好。

## 5. 安全漏洞独立判定

安全漏洞不经过「用户可感知」过滤，最低 MAJOR。范围限定 OWASP Top 10，QA 对照 Checklist 判定，不要求执行渗透测试。
