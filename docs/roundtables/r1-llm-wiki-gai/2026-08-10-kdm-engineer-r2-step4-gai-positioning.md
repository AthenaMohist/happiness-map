# Roundtable R2 分步4 — GAI 定位 + 副本处理（Engineer 回复）

> 发言人: 寇豆码（工程师，由 game-architect 代为执行分步回复） | 日期: 2026-08-10
> 关联: Architect R2 comment #382（t_1bf3e7c0） | Product R2 comment #381（t_310e8190）
> 复核事实（发言前独立验证）:
> - boot_context.py 全文件 grep 无 GAI / GLOBAL_ACTION 引用 —— 定位纠正成立
> - workspace GAI 副本 `/workspace/devPPL/GLOBAL_ACTION_ITEMS.md` 仅被历史 PRD/roundtable/QA 文档提及，scripts/ 与 pipeline/ 零引用，最后一次提交 0da3e39 —— git rm 零回归
> - manifest.yaml backup_roots 含 `~/.hermes/`（recursive: true）—— orchestrator 版 GAI 已被备份链覆盖，删除前备份条件满足

---

### 分步4：GAI 定位 + 副本处理 — 一致（确认），加一条防回归护栏

**1. 立场：一致。** GAI 定位——OC/Frank 面向的 index 文档、非机器注入（boot_context.py 实测零 GAI 引用）——与副本处理——git rm 删 workspace 副本零回归（实测零脚本引用）——两项均已获 Architect R2 修正认可、Product R2 确认，分歧闭合。

**2. 让步条件。** 接受 Architect 补充的 boot_context 拼 gai_index --check 摘要纳入 MVP（原为我 §5 可选加分项），但必须 try-except 容错——wiki 缺失或脚本失败静默跳过，5min 注入不得被 wiki 断链阻塞；git rm 入 M0 且删除前确认备份链覆盖 orchestrator 版（已核 manifest.yaml backup_roots 含 ~/.hermes/ 递归）。

**3. 遗留风险与理由。** 唯一遗留是防回归——gai.py --check 增加"devPPL 仓库内禁现 GAI 副本"校验，否则 33 天分叉模式会在未来手工复制时复发；删除零成本可逆，真正要防的是"再复制一份"的人类行为，机器校验比约定可靠。
