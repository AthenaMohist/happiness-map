# PRD — 建卡铁律 v4：GAI 编号强制分配 + 连续步骤卡链

> 作者：许清楚（产品负责人） | 日期：2026-08-12 | 版本：v1.0
> 来源：Frank 2026-08-12 报告（记忆中间层任务暴露的流程缺陷）+ Frank 原话「以后从 gai 来建任务，必须要有唯一编号」
> 议题：固化建卡流程两条规则 —— ① GAI 编号强制分配 ② 连续步骤卡链
> 定位：跨项目流程规则（devPPL 管线层），不是记忆中间层专属；规则落文档后由 OC 接线到 PIPELINE.md / autopilot / memctl
> 北极星对齐：Frank 不重复解释任务背景、不重复纠错。编号是任务的永久身份，卡链是任务的推进轨迹——两者齐了，Frank 从 GAI 一行就能追溯一个任务的完整生命周期（背景 → 各步骤卡 → 产物 → 验收）。

---

## 0. 本 PRD 在整体规划中的定位

建卡铁律演进（每版都是前版失效后 Frank 裁定的强化）：

| 版本 | 日期 | 裁定 | 落地 |
|------|------|------|------|
| v1 | 2026-08-10 | 卡片创建权唯一属于 OC，worker 禁建卡 | 各角色 SOUL.md 建卡铁律 |
| v2 | 2026-08-10 | worker 可建**职责内**子卡，禁建上下游卡 | PIPELINE.md 核心纪律 4 |
| v3 | 2026-08-12 | 所有建卡走 autopilot，discover 层拦截 dev/qa 卡自动插评估卡 | f56cd1f（est_intercept_after_insert 触发器） |
| **v4（本 PRD）** | 2026-08-12 | **编号强制分配 + 连续步骤卡链** | 本 PRD → OC 接线 PIPELINE.md / autopilot / memctl |

**一句话定位**：v3 解决了「卡会不会被评估」，v4 解决「卡是谁的、卡与卡什么关系」。v4 不推翻 v1-v3 任何裁定——编号与卡链是叠加在现有建卡流程之上的**身份层**。

---

## 1. 背景与痛点

### 1.1 三个暴露的缺陷（Frank 2026-08-12 报告）

| # | 缺陷 | 实例 | 后果 |
|---|------|------|------|
| 1 | **编号缺失**：任务属于某项目但无 `[CODE]-NNN` | 记忆中间层「任务页愿景」最初以 `[PRD-REFINE]` / `[Step1] 架构设计` 两张自由命名卡存在，无 MEM-0xx | GAI/kanban/wiki 三方无法按编号归组；任务身份丢失；Frank 无从按编号追溯 |
| 2 | **卡链断裂**：同一任务连续步骤拆成独立卡，task_links=0 | PRD 细化卡（t_b476baba）→ 架构设计卡（t_b353d348）初始无 parent→child 边 | 管线无法自动推进；下游步骤拿不到前置产物路径；heartbeat/notify 看不到链 |
| 3 | **真源漂移**：编号无强制一致性校验 | 补编号（MEM-002）靠事后 commit（1686c67），非建卡即强制 | 每次补登都是手工救火，重复发生 |

### 1.2 Frank 需求映射

| Frank 原话/要求 | 现状 | 本 PRD |
|-----------------|------|--------|
| 「以后从 gai 来建任务，必须要有唯一编号」 | 无强制机制，自由命名 | 规则 1：建卡必须带 `[CODE]-NNN` |
| 「编号在 GAI 登记（一行）+ wiki 页 + kanban 卡三者一致」 | drift 只对账缺页/断链，不校验编号 | §5 一致性校验手段 |
| 连续步骤不得拆成独立平铺卡 | [CMD] create dev 已建链，OC 直建自由卡不建链 | 规则 2：同编号连续步骤必须 task_links |

### 1.3 现状盘点（已具备的基础，v4 直接继承）

| 基础设施 | 位置 | 状态 |
|----------|------|------|
| 项目代码表 | `/root/.hermes/profiles/orchestrator/PROJECT_CODES.md`（MEM=记忆、DPL=devPPL、INF=InfoManager 等 11 码） | ✅ 已有 |
| GAI 双链版 | `/workspace/mem-core/gai/GLOBAL_ACTION_ITEMS.md`（`[[MEM-002]]` 格式，commit bbac281） | ✅ 已有 |
| 任务页 frontmatter 字段 | SCHEMA v1.1：`page_type` / `project` / `project_folder` / `task_code`（commit 79af2e9） | ✅ 已有 |
| 类型化建链 | `[CMD] create dev` → DEVELOPMENT_CHAIN 13 棒 sequential，parents 门控 + 幂等键（cmd_chain.py） | ✅ 已覆盖开发链 |
| 创建瞬间拦截 | est_intercept_after_insert 触发器（f56cd1f） | ✅ 已覆盖 dev/qa 评估卡 |

**结论**：基础设施齐了，缺的是「建卡时强制编号 + 强制卡链」的规则与校验。

---

## 2. 规则定稿（建卡铁律 v4）

### 规则 1：GAI 编号强制分配

**适用对象**：任何从 GAI 发起、或属于某项目（PROJECT_CODES.md 定义）的任务卡。

**编号格式**：`[CODE]-NNN`
- CODE = PROJECT_CODES.md 3 字母项目代码（记忆中间层=MEM，devPPL=DPL，InfoManager=INF，…）
- NNN = 3 位序号（001 起），**每项目代码内唯一，永久不变，只增不回收**

**编号出现位置（三处一致，缺一即违规）**：
1. **GAI 登记**：GLOBAL_ACTION_ITEMS.md 任务行「任务ID」列（一行），行动列带 `[[编号]]` 双链
2. **wiki 页**：`wiki/actions/<编号>.md` frontmatter `id: <编号>`（SCHEMA v1.1 `task_code` 字段同值）
3. **kanban 卡**：标题或 body 首部含 `[CODE]-NNN`（标题建议格式：`[MEM-002] <步骤说明>`；body 首行 `编号: MEM-002`）

**编号是任务身份，不是卡片身份**：同一任务跨步骤的所有卡（PRD 卡、架构卡、dev 卡、QA 卡…）共享同一编号。编号 + 步骤 = 卡的完整身份。

### 规则 2：连续步骤卡链

**适用对象**：同一任务（同编号）的连续步骤卡（PRD→架构→dev→QA→VA→merge→close 及任何变体）。

**强制要求**：连续步骤必须构成 task_links parent→child 链——后一步卡创建时 `parents=[前一步卡]`。禁止同编号多张卡 task_links=0 平铺。

**已覆盖路径**（继承，不需新机制）：
- `[CMD] create dev <描述>` → cmd_chain.py DEVELOPMENT_CHAIN 13 棒 sequential，每棒 parents 门控 + 幂等键 `dev-<spec_hash>-<step>` ✅

**需要补齐路径**：
- OC 直建的自由命名卡（如本卡 `[PRD-REFINE]`）：若同编号已存在前序步骤卡，建卡必须 `parents` 引用前序卡；autopilot discover 注册时若发现同编号多卡无链 → 告警（§4.2）

---

## 3. 编号分配机制方案

### 3.1 决策：谁分配 / 何时分配 / 如何登记

| 决策点 | 结论 | 理由 |
|--------|------|------|
| **分配时机** | 编号在**任务出生时**分配：从 GAI 发起 → GAI 登记时；直接建卡（无 GAI 行）→ 首次建卡时 | 编号=任务身份，出生即定，事后补登是救火（缺陷 3 的教训） |
| **谁分配** | **机械层自动分配优先**：memctl `next-seq <CODE>` 读 GAI 现有编号取 max+1（零 LLM）；LLM（OC/autopilot）只调用、不手填 | 手填编号靠记忆 → 重号/跳号不可防；机械分配确定性可 lint |
| **如何登记** | 建卡流程调 memctl 拿到编号后，三处同步写：GAI 行 + wiki 页 + kanban 卡 | 一次分配三处落位，drift 只做对账不做补写 |

### 3.2 两条分配路径

**路径 A — 从 GAI 发起（推荐，Frank 愿景主路径）**：
```
GAI 新增待办行（含 [CODE]-NNN，编号由 memctl next-seq 分配）
  → OC 据 GAI 行投 [CMD] create dev <描述>（编号带在描述里）
  → autopilot 建链时把编号注入每张链卡标题/body
  → memctl add task --from-kanban 采集时 frontmatter task_code = 编号
```

**路径 B — 直接建卡（无 GAI 行）**：
```
建卡前调 memctl next-seq <CODE> 取编号（或从 body 已有 [CODE]-NNN 继承）
  → 建卡（标题/body 带编号）
  → autopilot discover 注册时补登 GAI 行（一行）+ wiki 页骨架（若缺失）
```

### 3.3 memctl next-seq 功能需求（P1 实现项，交架构细化）

```
memctl next-seq <CODE>
  行为: 读 GAI 现有 [CODE]-\d{3} 取 max+1 → 输出 <CODE>-NNN（零 LLM，确定性）
  兜底: GAI 缺失 → 读 wiki actions/ 页编号 → 再兜底 001
  约束: 只分配不写（写由 add/gai-links 通道负责）；并发安全（单写者 memctl 串行）
```

> **产品裁定**：next-seq 是 v4 的机械基座，属于记忆中间层 P1-2「GAI 适配器」范围（与 gai-links 合并实现），不在 MVP 9.5h 内。MVP 期间规则 1 由流程约定执行（OC/autopilot 建卡时从 GAI 抄编号），lint/校验脚本负责兜底报警。

---

## 4. 卡链强制机制方案

### 4.1 [CMD] create dev 链（已覆盖，需补编号注入）

现状：cmd_chain.py 建链时 body 含 spec 上下文（前棒卡/产物路径），但**没有编号字段**。

补齐（架构落地项）：
- `_dev_card_body()` 增加 `编号: <CODE>-NNN` 首行（从 [CMD] 描述或 GAI 行解析；无编号 → 调 memctl next-seq 分配）
- 链上所有卡（含 dev-est/qa-est 评估卡、[DEV-SUB-*] 子卡）继承同一编号，标题/body 可见

### 4.2 OC 直建自由命名卡（新规则）

| 场景 | 规则 | 校验 |
|------|------|------|
| 同编号已有前序卡 | 建卡必须 `parents=[前序卡]`；标题带编号 | chain-check 扫描 |
| 无前序卡（任务首卡） | 标题/body 必须带编号；无编号 → memctl 分配 | number-check 扫描 |
| 纯内部卡（无项目归属，如 roundtable 发言卡） | 豁免编号（不适用规则 1） | 按 title 前缀豁免 |

### 4.3 强制校验（复用 dedup_check / workspace_check 扫描模式）

新增 `chain_check` 扫描（autopilot 每 tick，或独立 cron）：
1. 扫描活跃卡（ready/running/blocked）提取 `[CODE]-NNN`
2. 同编号多卡且 task_links=0 → `[chain-gap]` 告警 comment（不阻塞，OC 处置）
3. 同编号卡链必须 parent→child 串联 → 断裂即告警
4. 与 workspace_check 同风格：只读扫描 + comment 告警，不自动改卡

---

## 5. 编号一致性校验手段（GAI / wiki / kanban 三方）

### 5.1 drift 三方对账扩展（memctl drift，P1 实现项）

现状（drift.py）：kanban 活跃任务 vs wiki 缺页/status 不一致 + GAI 待办行 vs wiki 缺页/断链。

扩展（编号维度，缺一即 drift 差异）：
| 校验 | 判定 |
|------|------|
| kanban 卡编号 → GAI 行 | 卡 body/标题 [CODE]-NNN 必须在 GAI 行存在（任务ID 列） |
| kanban 卡编号 → wiki 页 | 编号必须在 wiki actions/ 存在（frontmatter id） |
| GAI 行编号 → wiki 页 | 已有（缺页/断链），保持 |
| 编号唯一性 | 同一 [CODE]-NNN 不得出现两次（GAI 行 / wiki / kanban 三源各自内查重） |
| 链一致性 | 同编号多卡必须构成完整 parent→child 链（§4.3） |

### 5.2 lint 扩展（memctl lint）

- I5 扩展：task 页 `task_code` 非空且格式匹配 `[CODE]-\d{3}`；`id` 与 `task_code` 同值（SCHEMA v1.1 字段语义落地）
- 编号在 GAI 行存在 → wiki 页存在 → 卡的引用一致，三者任一缺失 = lint 失败

### 5.3 校验手段验收口径

`memctl drift` 输出空 = 三方一致；`memctl lint` exit 0 = wiki 内部编号合法。两条命令是 Frank/OC 的「一致性体检」入口。

---

## 6. 验收断言（A1-A6）

| # | 断言 | 验证方式 |
|---|------|---------|
| A1 | 建卡铁律 v4 规则文档落盘（本 PRD），含编号格式/三处登记/卡链要求 | 本文件存在；OC 已接线 PIPELINE.md 核心纪律 |
| A2 | 编号分配机制明确：memctl next-seq 分配时机/责任方/登记链路成文 | 本 PRD §3；架构卡落地 next-seq 功能需求 |
| A3 | 连续步骤卡链规则明确，[CMD] create dev 链编号注入有方案 | 本 PRD §4；架构卡落地编号注入 |
| A4 | GAI/wiki/kanban 编号一致性有校验手段（drift 扩展 + lint I5 扩展） | 本 PRD §5；P1 实现后 `memctl drift` / `lint` 可验 |
| A5 | 规则被 autopilot/OC 建卡流程引用 | PIPELINE.md 更新 + chain_check 扫描上线（OC 接线项） |
| A6 | 本任务自身合规：t_4e8e0d71 属 devPPL 项目 → 编号 DPL-0xx；若为记忆中间层任务 → MEM-0xx（建卡时未编号为历史缺陷，补登） | 卡 body/comment 补登编号，chain 归位 |

> A6 说明：本卡创建时尚未有 v4 规则（v4 正是本卡产物），按「历史缺陷补登」处理——不追溯改卡标题，但需在卡 comment 声明归属编号，示例价值大于处罚价值。

---

## 7. 风险与对策

| # | 风险 | 缓解 |
|---|------|------|
| R1 | 强制编号拖慢建卡（OC 多一步） | 机械分配（next-seq 一条命令）+ 默认继承（GAI 行已有编号直接抄），LLM 零负担 |
| R2 | 内部卡误判需编号（roundtable 等） | title 前缀豁免清单（复用 SUB_TASK_TITLE_PREFIXES + [ROUNDTABLE-]/[CMD] 前缀） |
| R3 | next-seq 与 GAI 手工编辑并发重号 | 单写者 memctl 串行分配 + drift 唯一性校验兜底（发现重号 → 报警 → 后建者改号） |
| R4 | 历史卡无编号，扫描刷屏告警 | chain_check 只扫活跃卡；历史 done 卡豁免（v4 生效前创建的卡不追溯） |
| R5 | 规则只落文档不落代码（OBS-01 教训） | A5 明确 OC 接线项（PIPELINE.md + chain_check），验收以「规则被引用」为准而非「文档存在」 |

---

## 8. 与下一阶段交接（架构落地项）

Step 2 架构设计必须落地的关键项（产出本 PRD 后由 OC 建架构卡）：

1. **memctl next-seq <CODE>**：P1-2 GAI 适配器范围；零 LLM 确定性分配；GAI→wiki 双兜底
2. **建卡编号注入**：cmd_chain.py `_dev_card_body()` 加 `编号:` 首行；[CMD] create dev 描述解析编号
3. **chain_check 扫描**：复用 workspace_check 模式；[chain-gap] 告警；历史卡豁免
4. **drift 扩展**：编号存在性/唯一性/链一致性三个新维度
5. **lint I5 扩展**：task 页 task_code 格式 + id/task_code 同值
6. **PIPELINE.md 更新**：核心纪律 6「建卡必须带编号 + 同编号连续步骤必须成链」（OC 接线）

**MVP 期间过渡**（next-seq 未上线）：规则 1/2 由流程约定执行 + 扫描告警兜底；编号从 GAI 行手抄，不阻断建卡。

---

## 9. 一句话结论

建卡铁律 v4 = 编号强制分配 + 连续步骤卡链：任何属于项目的任务出生即带 `[CODE]-NNN`（GAI 行 / wiki 页 / kanban 卡三处一致，机械分配优先），同一任务的连续步骤必须构成 task_links 链；一致性由 `memctl drift` / `lint` 扩展 + `chain_check` 扫描兜底，规则被 PIPELINE.md / autopilot 引用后 v4 才算落地（A5）。
