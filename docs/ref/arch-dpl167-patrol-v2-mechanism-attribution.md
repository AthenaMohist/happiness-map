---
created: 2026-09-26T22:30:00+08:00
id: arch-dpl167-patrol-v2-mechanism-attribution
type: entity
page_type: project
project: "[[entities/devppl.md|devPPL]]"
status: active
updated: 2026-09-26T22:30:00+08:00
---

# ARCH — 巡察使v2 机制级归因引擎：扫描口径重写 + LLM 归因 + 机制双链（DPL-167）

> 编号: DPL-167 / 卡 t_068d5893
> 作者: 高见远（架构师）| 日期: 2026-09-26 | 版本: v1.0
> 上游: PRD v1.0（t_f1c7cf96，commit 7264c1c @ mem-core main）+ OC 审 PRD 通过（2026-09-26 comment）
> 前链: DPL-162（巡察使闭环，chain_review.py M1-M10 已落 main @ devPPL）
> 实现仓: /workspace/devPPL（scripts/chain_review.py 现状 1335 行 / tests/test_chain_review.py 1059 行，本设计在其上做增量）

---

## 0. 对齐校验表（PRD 逐条 → 设计落点）

| PRD 条目 | 设计落点 | 源码实锚 |
|---|---|---|
| G1/R1 mechanism_key + 二级聚合 + 指纹归一化 | §2 M11 `mechanism_key()` / `mechanism_fingerprint()` / aggregate_pits 二级聚合 | `PIT_CAUSE` chain_review.py:59-74；`signal_hash`:106-113（不动）；`_norm_desc`:101；`aggregate_pits`:841 |
| G2/R2 LLM 机制归因 + 词表 + fail-open + 预算守卫 | §2 M12 `attribute_mechanism()` + `load_taxonomy()` + `LLMBudget` | `classify_pit`:393；cc 通道 `/workspace/anthropic_proxy.py`（OpenAI chat completions 透传，BRAIN_PROXY_API_KEY）|
| G3/R3 机制页目录 + 坑行「机制」列 | §2 M13 `render_mechanism_page()` / `upsert_mechanism_page()` + render_lessons_rows 加列 | `render_lessons_rows`:475-491（锚点注入形态复用）；`WIKI_TEMPLATE`:379；`_TABLE_HEADER`:390 |
| G4/R4 机制汇总视图 | §2 M14 `render_mechanism_summary()` 插入 update_lessons_page | `update_lessons_page`:494-528（表尾插入逻辑，汇总插 header 之下为新增段） |
| G5/R5 回写联动机制页 | §2 M15 writeback 机制页追加 | `writeback_fix_status`:1147-1194；`auto_writeback`:1114-1138 |
| AC1-AC5 | §4 验收映射 | pytest tests/test_chain_review.py 域内子集 |
| D1 端点可用性 / D2 词表漂移 / D3 历史不回填 / D4 表结构变更 | §3 | fail-open 全线继承 + 词表 wiki 页 + 幂等旧行兼容 |

非目标硬约束（PRD §2）：route_fix/route_action/三证据裁决**一行不改**；LLM 只出标签不定性不定路由；不回填历史 F5；不新增 cron。

## 1. 总体架构（v2 = 在 v1 四层之间插入「归因层」，采集/路由/执行层不动）

```
每日 cron 06:30（dpl162_daily.sh 既有流程内追加，不新增 watchdog）
        ▼
采集层（v1 原样: 五源扫描 + signal_hash 卡级去重）
        ▼
定性/路由层（v1 原样: 豁免→wiki复核→三证据→route_fix→route_action）
        ▼
┌─ 归因层（v2 新增，位于 lessons 渲染之前）──────────────┐
│ M11 mechanism_key: 机械初值(pit_type→映射) + 指纹归一化 │
│ M12 attribute_mechanism: F5 带组代表 → LLM 词表标签     │
│     fail-open / 词表外拒收 / CHAIN_REVIEW_LLM_BUDGET    │
└──────────┬────────────────────────────────────────────┘
           ▼ pit 携带 mechanism_label
┌─ 呈现层（v2 扩展）────────────────────────────────────┐
│ M13 lessons 坑行新增「机制」列 + 机制页 upsert（双链）  │
│ M14 机制汇总表（每 run 全表重算覆盖，插表头之下）       │
└──────────┬────────────────────────────────────────────┘
           ▼
回写层（v1 writeback_fix_status 原样 + v2 追加: 命中行带
mechanism_key → 机制页「判例与历次修复」追加一行）
```

设计原则（继承 v1 三原则 + v2 新增两条）：
4. **归因是标签不是裁决**：mechanism_label 只影响聚合与呈现，绝不改变 verdict/route（PRD 非目标②）。LLM 是"分类器"不是"裁判"——概率组件永不获得决策权。
5. **mechanism_key 是派生产物**：机制页/汇总表全部可由 lessons-daily.md + 本轮组重算重建（幂等覆盖写），因此 close 校验不加新项（PRD R5）——派生物丢失不产生 REGISTRY-GAP。
6. **聚合预算闸门前置**：LLM 只对**组代表**调用（aggregate_pits 已把 865 行压成组），预算守卫 CHAIN_REVIEW_LLM_BUDGET 兜底费用上限。

## 2. 模块规格（M11-M15，全部落 scripts/chain_review.py 或新文件 scripts/mechanism_attribution.py —— 建议同文件追加，与既有风格一致、避免 import 环）

### M11 mechanism_key + 二级聚合（R1）

```python
MECHANISM_SEED: dict[str, str] = {
    # 机械初值映射: 描述关键词（归一化后）→ 机制词表 key。只收 PRD §2 G2
    # 列出的高频机制，LLM 归因后由语义层覆盖。空 dict 合法（全走 LLM/未归因）。
}

def mechanism_fingerprint(desc: str) -> str:
    """机制指纹归一化（纯函数）:
    1. _norm_desc 基线;
    2. 占位符替换（顺序敏感）:
       task_id  → <TID>     (re: \bt_[0-9a-f]{6,}\b / \bt_\w+\b)
       commit   → <SHA>     (re: \b[0-9a-f]{7,40}\b)
       时间戳   → <TS>      (re: \d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(:\d{2})?)
       数字对   → <N/N>     (re: \b(\d+)\s*/\s*(\d+)\b  — 60/60、31/71 形态)
       裸数字   → <N>       (其余 \d+)
    3. 返回替换后字符串（不 hash，可读便于 debug 与单测断言）。
    """

def mechanism_key(pit: dict) -> str:
    """f"{pit_type}:{mechanism_label}"。
    label 优先级: pit["mechanism_label"]（LLM/已算） > MECHANISM_SEED 关键词
    匹配 > "unattributed"。
    """
```

`aggregate_pits()` 增加二级聚合 `aggregate_by_mechanism(groups) -> dict[mechanism_key, group]`：
- 输入是 v1 一级组列表（每组已有 representative/count/task_ids/signal_hashes）；
- 键 = `mechanism_key(representative)`；
- 组结构 `{"mechanism_key", "pit_rows": n, "task_ids": 并集, "signal_hashes": 并集, "fix_commits": 从 lessons 行反查（M15 用）}`；
- **signal_hash 一级去重逻辑零改动**（PRD G1 硬约束：回写锚点不变）。

### M12 LLM 机制归因（R2）

```python
MECHANISM_TAXONOMY_PATH = REPO_ROOT / "wiki" / "actions" / "mechanisms" / "_taxonomy.md"

def load_taxonomy() -> list[str]:
    """读词表 wiki 页 `- key` 行集。缺文件/解析失败 → []（fail-open，
    全部落 F5:未归因，机制聚合退化为机械标签粒度 — PRD D1 降级形态）。"""

def attribute_mechanism(group_rep: dict, taxonomy: list[str],
                        client: "LLMClient|None") -> tuple[str, str]:
    """返回 (mechanism_label|None, confidence)。
    触发条件（调用方 process_mechanisms 把关，本函数只管单次归因）:
      verdict=confirmed 或 count>=2 的组，且机械分类 ∈ {F5:未分类, F5:循环型}。
    Prompt 契约（system+user 两条）:
      输入 = description（去敏: description[:300]）+ 机械分类 + 词表清单;
      要求输出 JSON: {"mechanism": "<key>", "confidence": "high|low"};
    校验: mechanism ∉ taxonomy → 返回 (None, "rejected")（词表外拒收,
      机械保证 LLM 不得自造词 — PRD D2）;
    client None / 调用异常 / JSON 解析失败 / 超时(15s) → (None, "fail-open")。
    """

class LLMBudget:
    """单 run 调用计数器。上限 env CHAIN_REVIEW_LLM_BUDGET（缺省 20）。
    exhausted 后 attribute_mechanism 不再被调用（调用方短路，省 prompt 拼装）。"""

class LLMClient:
    """OpenAI chat completions 口径（与 anthropic_proxy.py 同协议族，
    直接 HTTP urlopen，不启动代理进程 — 链复盘是无人值守 cron，不依赖
    长驻服务）。env: CHAIN_REVIEW_LLM_URL（缺省 deepseek 官方端点，同
    proxy DEEPSEEK_URL）、CHAIN_REVIEW_LLM_MODEL（缺省 deepseek-chat）、
    CHAIN_REVIEW_LLM_KEY（缺省读 BRAIN_PROXY_API_KEY）。任一缺席 →
    client=None（全 fail-open）。timeout=15s。"""
```

接线点：`main()` 在 `process_pits(pits)` 之后、`write_lessons_page(reps)` 之前插入 `process_mechanisms(groups, budget, client)`——逐组判触发条件 → attribute_mechanism → 把 label 写回 `rep["mechanism_label"]`（组内全部 signal_hash 共享同 label，G4 聚合口径）。

### M13 机制双链（R3）

机制页目录 `wiki/actions/mechanisms/<mechanism-key>.md`（key 中的 `:`→`-`，路径安全）：

```markdown
---
mechanism_key: run_give_up:iteration-budget-exhausted
status: active        # active / fixed（全名下坑行已修复时由脚本翻转）
---
# 机制: iteration-budget-exhausted

## 定义
（首条判例的 description 摘要 160 字，脚本生成，人工可改写——改写不被覆盖，
仅 status 与追加节由脚本维护）

## 判例与历次修复（追加式）
- 2026-09-26 fix <commit[:12]> 锚 <!--signal_hash[:12]-->

## 名下坑行（signal_hash 短链，重算覆盖写）
- <!--h12--> [[t_xxx]] 描述[:60]
```

`upsert_mechanism_page(key, ...)`：页不存在按模板建；存在则「名下坑行」节整体重算覆盖（派生产物语义）、「判例与历次修复」只追加（按 `锚<!--h12-->+sha` 幂等判重）、「定义」节不动。

lessons 坑行加列：`render_lessons_rows` 行尾（处置路由列后、锚点注释前）追加 `| [[mechanisms/<key-slug>|<label>]] |`；label 为 None 渲染 `F5:未归因` 纯文本。`_TABLE_HEADER` 与 `WIKI_TEMPLATE` 同步加「机制」列。**旧行兼容（D4）**：update_lessons_page 去重按 signal_hash 锚（行内 `<!--h12-->`），旧行无机制列不会被重写——渲染层读列时按「列数不足 → 视为未归因」容错。

### M14 机制汇总视图（R4）

`render_mechanism_summary(all_rows, groups) -> str`（纯函数）：
- 输入 = lessons-daily.md 现有全表行（含历史 F5 无机制列行）+ 本轮二级聚合组；
- 历史行归类：行内有 `[[mechanisms/...]]` 链 → 归该机制；否则归 `未归类`（对应 PRD P1 的 F5 带，不回填但全景可见）；
- 输出表：`| 机制 | 坑行数 | 涉卡数 | 待修复数 | 最新修复 commit |`；
- 插入位置：lessons 页 `# 教训日账` 标题行之后、`## sentinel 待裁定` 之前的独立段 `## 机制汇总（每 run 重算）`，每 run 整段覆盖写（天然幂等）；
- 行数守卫：>40 机制 → Top-40（按坑行数降序）+ 末行「其余 N 机制 M 行」。

### M15 回写联动（R5）

`writeback_fix_status()` 命中坑行成功回写后，追加调用 `append_mechanism_fix(h12, commit_sha)`：
- 由行文本提取 `[[mechanisms/<slug>]]` → 反解 mechanism_key → 机制页「判例与历次修复」追加 `- <BJT日期> fix <sha> 锚 <!--h12-->`；
- 页不存在 → 按 M13 模板创建（只含该判例行，「名下坑行」留空待下轮重算）；
- 全程 try/except fail-open，**不影响既有坑行回写返回值**（v1 行为零改动）；机制页不进 close 校验清单（派生产物非登记物，PRD R5）。

## 3. 风险与决策落点

| # | 风险/决策 | 设计落点 |
|---|---|---|
| D1 | LLM 端点缺席/额度耗尽 | LLMClient env 缺席→client=None；调用失败/超时→(None,"fail-open")；词表文件缺席→taxonomy=[]。三级降级后 G1/G3/G4 机械路径完全独立可交付（与 PRD §5 D1 承诺一致） |
| D2 | 词表膨胀稀释质量 | 词表落 wiki/actions/mechanisms/_taxonomy.md 可演进页；LLM 词表外输出机械拒收（代码保证，不靠 prompt 约束）；新增机制需 ≥1 真实判例由 OC 审进词表 |
| D3 | 历史 492 行 F5 不回填 | attribute_mechanism 只对**本轮新增组**触发；历史行由 M14 汇总表「未归类」行给全景 |
| D4 | lessons 表结构变更冲击下游 | 旧行不重写（signal_hash 锚幂等）；读侧按列数容错；MERGE 卡需 dry-run 验证旧区段 diff 为零（AC4） |
| D5 | LLM 归因耗时可拖垮 06:30 cron | 组数实测远小于行数（865 行→去重后约数十组）；budget=20 × 单次 <15s ≈ 最坏 5 分钟，可接受；budget 耗尽即短路不拼 prompt |
| D6 | mechanism_key 含 pit_type 导致同机制跨 pit_type 不聚合 | 有意为之：pit_type 是证据源维度（来源可信度），机制是语义维度，二者正交。若实践发现需跨源合并，在 M11 MECHANISM_SEED 加映射即可，不动键结构 |

## 4. 验收映射（对应 PRD AC1-AC5）

| AC | 设计落点 | 测试口径 |
|---|---|---|
| AC1 mechanism 聚合 | M11 单测：`mechanism_fingerprint` 占位符替换表驱动（task_id/sha/时间戳/60÷60/裸数字）；3 卡同模板坑 → 二级组 count=3、signal_hashes 各异 | pytest tests/test_chain_review.py -k mechanism |
| AC2 LLM 归因 | M12 单测（fake client，不真网）：正常返回采信 / 词表外拒收 / client 抛错 fail-open / budget 耗尽短路 四例；断言主流程返回组列表完整、lessons 行不中断 | -k attribution |
| AC3 机制双链 | M13 单测 + 真实数据 `chain_review.py --dry-run`：机制页存在、坑行含 `[[mechanisms/`；连续跑两遍 diff 为空（除新增坑行） | -k mechanism_page |
| AC4 汇总+回写联动 | M14/M15 单测：5 行 2 机制 → 汇总表 2 行数字核对；mark-fixed 一行 → 机制页 +1 修复行，再跑不重复（幂等） | -k summary or writeback |
| AC5 回归 | v1 域内全文件回归：route_fix/route_action/verify_with_evidence/writeback 既有测试全绿（表头加列需同步修正既有 render 断言——允许，属本功能域） | pytest tests/test_chain_review.py -q |

测试纪律：只跑 tests/test_chain_review.py；mock/LLM 端点不真网；不跑全量 pytest（DPL-137）。

## 5. 拆卡建议（供 OC 建卡，本卡不越权建卡；与 PRD §6 S1-S4 对齐并细化）

| 子卡 | 内容 | 建议指派 | 依赖 |
|---|---|---|---|
| S1 | M11 mechanism_fingerprint/mechanism_key/二级聚合 + AC1 单测 | game-engine | 无 |
| S2 | M12 LLM 归因（fake client 可测）+ M15 回写联动 + AC2/AC4 单测 | game-engine | S1 |
| S3 | M13 机制页 + 坑行加列 + M14 汇总视图 + AC3 单测 | game-engine | S1 |
| S4 | AC5 域内回归 + 真实数据 dry-run 实证 + MERGE 落 main + 备份推送 | autopilot | S2, S3 |

## 6. 关联

- [[dpl167-patrol-v2-mechanism-attribution-prd]]（本卡 PRD v1.0）
- [[arch-dpl162-patrol-closed-loop]]（v1 闭环架构，本设计直接增量基座）
- [[arch-dpl145-round50-hardstop-autosystem]]（iteration-budget 机制首个判例来源）
- [[actions/MEM-016]]（机制页判例节证据链风格）
- 本卡: t_068d5893
