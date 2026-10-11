# DPL-167 DEV-EST 复评报告（第二次重试）

> 卡: t_f8a0f076 | 日期: 2026-09-26 | 评估人: DEV-EST（复评）
> 对象: 巡察使v2 机制级归因引擎（DPL-162 迭代）——扫描口径重写 + LLM 归因 + 机制双链

## 1. 前置产物路径

| 产物 | 路径 |
|---|---|
| PRD v1.0 | /workspace/devPPL/docs/ref/dpl167-patrol-v2-mechanism-attribution-prd.md（t_f1c7cf96） |
| ARCH v1.0 | /workspace/devPPL/docs/ref/arch-dpl167-patrol-v2-mechanism-attribution.md（t_068d5893，M11-M15 规格 + S1-S4 拆卡建议） |
| 源码 | /workspace/devPPL/scripts/chain_review.py（1335 行） |
| 测试 | /workspace/devPPL/tests/test_chain_review.py（1059 行，域内套件） |

## 2. 源码实锚（已逐一核对）

| 锚点 | 行号 | 核对结论 |
|---|---|---|
| PIT_CAUSE 静态映射 | chain_review.py:59-74 | 11 条 pit_type→F1-F5，即 PRD P3 指出的"来源映射非语义" |
| _norm_desc | chain_review.py:101-103 | 归一化基线，M11 mechanism_fingerprint 依赖 |
| signal_hash | chain_review.py:106-113 | 卡级去重键，v2 **零改动**（G1 硬约束） |
| _TABLE_HEADER / WIKI_TEMPLATE | chain_review.py:379-390 | M13 加「机制」列需同步两处 |
| classify_pit | chain_review.py:393-395 | M12 触发条件挂接点（F5 系判定） |
| route_fix | chain_review.py:447 | 非目标区，一行不改 |
| render_lessons_rows | chain_review.py:475-491 | M13 加列渲染点 |
| update_lessons_page | chain_review.py:494-528 | M14 汇总段插入点（表头之下） |
| aggregate_pits | chain_review.py:841-875 | 一级组结构 confirmed，M11 二级聚合在其上叠加 |
| auto_writeback / writeback_fix_status | chain_review.py:1114-1194 | M15 append_mechanism_fix 挂接点 |
| main | chain_review.py:1235-1331 | M12 接线点：process_pits 之后、write_lessons_page 之前插 process_mechanisms |

## 3. M11-M15 逐模块轮次（按架构 §2 实际规格，不推断）

| 模块 | 内容（架构规格） | 交付物 | 实现轮次 | 依据 |
|---|---|---|---|---|
| M11 | mechanism_fingerprint（5 级占位符替换，顺序敏感）+ mechanism_key + MECHANISM_SEED + aggregate_by_mechanism 二级聚合 + AC1 表驱动单测 | 代码+单测 | 6 | 纯函数为主，但占位符正则表驱动用例（task_id/sha/时间戳/N/N/裸数字）边界多 |
| M12 | LLMClient（urlopen 直连 env 三项缺席→None）+ LLMBudget + load_taxonomy + attribute_mechanism（词表外拒收/超时/解析失败三级 fail-open）+ process_mechanisms 接线 + AC2 四例 fake-client 单测 | 代码+单测 | 8 | 规格最厚：prompt 契约、预算短路、main 接线、四例异常路径 |
| M13 | upsert_mechanism_page（建页/名下坑行覆盖写/判例追加幂等/定义不动）+ render_lessons_rows 加列 + 表头/模板同步 + 旧行列数容错（D4）+ AC3 单测 | 代码+单测 | 5 | 页面 upsert 三段语义 + 加列幂等兼容 |
| M14 | render_mechanism_summary 纯函数（全表重扫 + 历史行未归类 + Top-40 守卫）+ 插入 update_lessons_page + AC4 数字核对单测 | 代码+单测 | 4 | 纯函数，插入点单一 |
| M15 | append_mechanism_fix（行文本反解 key + 页不存在建页 + try/except 不改 v1 返回值）+ AC4 回写联动单测 | 代码+单测 | 3 | 挂接点明确，fail-open 包裹 |
| 小计 | | 5 交付物 | **26** | |

## 4. 总轮次（DPL-136 口径）

- 实现轮次：26
- 收尾（文档/自检/MERGE 准备）：+8 = 34
- 回归折算（实现 × 30% ≈ 7.8）：+8 = **42 轮（基准）**
- K 校准（历史偏差 K=2.53）：**42 × 2.53 ≈ 106 轮（校准后口径）**

## 5. 拆卡决策

- 有效轮 = 106 × 0.7 ≈ 74 > 30 → **必须拆卡**（预算口径远超 42 上限）。
- 交付物 5 个（M11-M15 + 域内测试）≥ 4 → 一律拆 ~3 卡。
- 架构 §5 已给 S1-S4 拆卡法则（S1: M11 / S2: M12+M15 / S3: M13+M14 / S4: 回归+MERGE），**优先采纳**，按"合并到 3 卡"指令压为 3 卡：S4 的回归与 MERGE 职责并入卡三（AC5 域内回归 + dry-run 实证随最后交付卡收尾）。

## 6. [SUB-SPLIT] 三卡建议（轮次为校准后口径）

| 卡 | serial/parallel | 内容 | 依赖 | 预计轮次（校准后） |
|---|---|---|---|---|
| 卡一（S1） | 第 1 位，可先行 | M11 mechanism_fingerprint / mechanism_key / MECHANISM_SEED / 二级聚合 + AC1 表驱动单测 | 无 | 16 基准 × 2.53 ≈ **40** |
| 卡二（S2） | 第 2 位，与卡三 **parallel**（同依赖卡一，互不触碰对方文件区） | M12 LLM 归因全套（LLMClient/LLMBudget/load_taxonomy/attribute_mechanism/process_mechanisms 接线）+ M15 回写联动 + AC2/AC4 单测 | 卡一 | 20 基准 × 2.53 ≈ **51** |
| 卡三（S3+S4） | 第 2 位，与卡二 parallel；收尾串行（MERGE 等卡二） | M13 机制页+坑行加列 + M14 汇总视图 + AC3 单测 + AC5 域内全量回归 + 真实数据 dry-run 实证 + MERGE 落 main/备份推送 | 卡一（编码）；卡二（MERGE 串行收尾） | 20 基准 × 2.53 ≈ **51** |

三卡合计 ≈ **142 轮（校准后）**；因每卡独立承担收尾 8 轮，合计高于单卡基准校准值 106——区间口径：**总轮次 106（不拆）/ 142（三卡）**，推荐按 142 排期。

## 7. 复杂度与风险点

| # | 风险 | 评估 |
|---|---|---|
| 1 | M12 是全卡复杂度重心：LLM 端点契约 + 三级 fail-open + 预算短路 + main 接线，四条异常路径均需 fake-client 单测 | 高（已给 8 轮，最大单模块） |
| 2 | 表结构变更（D4）：lessons 加列影响下游，旧行幂等与 dry-run 旧区段 diff=0 必须在卡三实证 | 中高 |
| 3 | 端点缺席降级形态（D1）：无端点时 G2 形同虚设，但机械路径（M11/M13/M14）独立可交付——不阻塞交付，属质量降级 | 中 |
| 4 | mechanism_fingerprint 占位符顺序敏感（TID→SHA→TS→N/N→N），顺序错则同模板不同参数无法聚合——AC1 表驱动覆盖必须全 | 中 |
| 5 | 幂等三类语义（页覆盖写/判例追加判重/坑行锚去重）交叉，二跑 diff=空 是唯一硬验收 | 中 |
| 6 | 非目标红线清晰（route_fix:447 / route_action / 三证据 :398 一行不改），回归面可控（单测试文件域内） | 低 |

## 8. stdout 摘要

- 拆卡决策：必须拆卡（有效轮 74 > 30；5 交付物 ≥ 4）→ 按架构 S1-S4 合并为 3 卡（S4 并入卡三）
- 三卡轮次（校准后）：卡一 40 / 卡二 51 / 卡三 51，合计 ≈ 142
- 总轮次区间：基准 42，K 校准后 106（单卡）~ 142（三卡）
- 报告已写入：/workspace/devPPL/docs/est/t_f8a0f076-estimate.md
