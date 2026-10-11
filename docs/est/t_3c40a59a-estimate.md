# EST — t_3c40a59a: REGISTRY 建卡自动登记 hook（DPL-177）

> 评估人: game-engine（寇豆码）| 日期: 2026-09-29 | 依据: PRD v1.0（t_47cf1aab）+ ARCH v1.0（t_9860c800, mem-core 00d975b）

## 1. 锚点实勘（2026-09-29，mem-core main 027d0e1）

| 架构锚点 | 实测 | 结论 |
|---|---|---|
| seq.py `_max_seq_from_registry` | :82 存在，区间正则**内联在函数体**（:96），非模块常量 | M1 需按 ARCH §M1 提为 `seq._REGISTRY_RANGE_RE` 导出（二选一中的确定项）；注意还有第二条单行「已用: CODE-NNN」正则（:101），回写只处理连续段行即可 |
| gailinks.append_gai_row | :41，五步流程，detail 契约 `written:`(:116)/`idempotent:`(:72,:98)，步骤2 幂等预检在锁外、步骤4+5 LOCK_EX 窗口 | M2 接线点明确：`written:` return 前插步骤6；幂等路径 :98 处 return 不触发回写 |
| cli.py cmd_gai_row | :1902 存在，commit 归 cli 层 | M3 零改动成立（REGISTRY.md 与 GAI 同 wiki.parent 仓库） |
| REGISTRY.md 水位 | `- **已用: DPL-2 ~ DPL-176**` @ :15 | 夹具格式与正则匹配验证通过 |
| 测试资产 | tests/test_gai_row.py / test_gai.py / test_seq.py 均已存在 | T2.2 门禁子集可直接扩展 |

架构引用零漂移，无预警项。

## 2. 工作量评估

| 项 | 内容 | 预估轮次 |
|---|---|---|
| M1 | seq 正则提为模块常量导出 + gailinks.sync_registry_watermark 纯函数（路径三段式/右移/幂等 noop/void 复查/全 fail-open 分支） | 4-6 |
| M2 | append_gai_row 两处接线（幂等路径不触发 + written 路径插步骤6 + stderr 锚词） | 1 |
| M4 | REGISTRY.md 维护段一行措辞 | 0.5 |
| 测试 | T1.1-T1.6 + T2.1-T2.2 共 ~8 用例（MEM_REGISTRY_FILE 夹具隔离红线；T2.1 需先写探针验证隔离语义） | 4-6 |
| 回归 | T2.2 子集（test_seq/test_gai/test_gai_row，DPL-137 口径） | 1-2 |
| 收尾链 | merge 后验证/WIP 笔记/claim 文件/finalize 四步/飞书推送（DPL-136 固定 +8） | 8 |

**总预估: 18.5-23.5 轮**（取整 19-24 轮；含 K=2.53 校准后落在 ≤30 有效轮红线内）
- 复杂度: 低-中。单文件为主的纯函数 + 接线，无新依赖、无跨仓改动、无锁逻辑新增（DA2 锁外+单调收敛设计合理）。
- 风险点: ① T2.1 隔离语义（next_seq 传 gai_file 即沙箱不读全局 REGISTRY，需探针先行——架构已标注）；② 现有测试若意外触发真 REGISTRY 写，需在夹具上先封堵。

## 3. 决策

**≤20-24 轮，N=1，不拆卡**（单 dev 子卡承担 M1+M2+M4+T 全部，serial）。
理由: 改动面集中在一个模块的一组函数，拆卡产生的合并/交接成本 > 收益；PRD §5 与 ARCH §6 拆卡建议一致为单卡 S1。

[SUB-SPLIT] 1 serial
1. [DEV] mem-core gai-row REGISTRY 回写 hook：M1 sync_registry_watermark（seq 正则提导出）+ M2 append_gai_row 接线 + T1.1-T1.6/T2.1-T2.2 测试 + M4 REGISTRY.md 维护段措辞，门禁 test_seq/test_gai/test_gai_row 子集（DPL-177）预计 19-24 轮
