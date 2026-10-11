# 工作量评估 — t_c923c170（DPL-153 统一入口门禁）

评估卡: t_est_c923c170 @ 2026-09-09，branch=dpl153-unified-entry，CC-MAX。

## 源需求拆解（3 个交付物）

1. **oc_create_card.sh 前置路由检查**（scripts/oc_create_card.sh, 206 行）
   - 新增 `routing_gate`：校验卡类型是否命中豁免清单（①调试 autopilot ②[CMD] 指令卡 ③[OC-TAKEOVER] 接棒收尾 ④纯登记/归档类 ⑤autopilot 明确不可用+body 声明理由）
   - 非豁免 → 拒绝并输出 `[CMD] create dev <主题>` 指引
   - 豁免卡 body 必须含 `[OC-DIRECT] <豁免理由>` 行，缺 = 拒绝
   - 结构完全平移现有 `card_verify_gate`（L74-124）：`_inner` 判定 + fail-open 包装 + `OC_CREATE_DRYRUN` 测试口已就绪
2. **oc_wake_check.sh 哨兵**（scripts/oc_wake_check.sh, 1381 行）
   - 近 24h body 含 `[OC-DIRECT]` 卡计数（SQLite 单查询），≥3 时 heartbeat 输出提示行，fail-open
   - 挂入现有 heartbeat 输出块（L187 附近模式），风险低
3. **wiki 收敛**：pipeline-concepts.md 混合模式 + kanban-card-format.md §1 补 `[OC-DIRECT]` 义务与哨兵条款，纯文档

## 复杂度 / 风险点

- 低-中。路由门禁有现成模板（card_verify_gate），核心工作是豁免判定的正则设计（5 类豁免识别，主要靠 title 前缀 + body 标记）
- 风险①：豁免判定误伤/漏放 —— 需功能级实测覆盖每类豁免（验收硬性要求，mock 全绿不收货）
- 风险②：wake_check 查询需索引友好（tasks.body LIKE，近 24h 按 created_at 过滤），卡量小无性能问题
- 回归面：test_oc_takeover_stale.sh 及现有 oc_create_card 门禁测试须不回退

## 轮数估算

| 阶段 | 基准 | 校准（CC-MAX） |
|------|------|----------------|
| doctor + CC-PLAN | 1-2 | 2 |
| 路由门禁实现 + 单测 | 4-6 | 7-10 |
| wake_check 哨兵 + 测试 | 2-3 | 4-6 |
| wiki 两文档 | 1-2 | 2-3 |
| 功能级验收（scratch 副本三类实测）+ 回归 | 3-4 | 5-8 |
| finalize | 1 | 1-2 |
| **合计** | **12-18** | **21-31** |

## 决策

校准估算 21-31 轮略超 20 阈值，但三个交付物强耦合于同一个门禁语义（路由检查的豁免判定同时决定 wake_check 哨兵的计数口径），拆开会产生跨卡语义同步成本，且单卡上限 60 轮余量充足。

**结论: [SUB-SPLIT] 1（不拆，单卡串行完成）**
