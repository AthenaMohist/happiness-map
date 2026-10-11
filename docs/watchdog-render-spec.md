# watchdog 渲染规范（图例 / 链行语法 / 卡片关系语义）

> 双写互链: 本文与 mem-core wiki 副本同步维护 —— mem-core 路径
> `/workspace/mem-core/wiki/concepts/patterns/watchdog-render-spec.md`
> （wiki 副本可精简，以本文件为准）。
> 出处: `scripts/notify_check.py` 常量 STATUS_EMOJI / NODE_NOTE / NODE_EMOJI /
> EVENT_MARK / CHAIN_ORDER / STEP_LABELS。

## 1. 图例全表

### 1.1 STATUS_EMOJI（卡片/链节点通用状态，notify_check.py 常量 `STATUS_EMOJI`）

| 状态 | emoji |
|---|---|
| done | ✅ |
| running | 🔄 |
| ready | 🔵 |
| blocked | 🚫 |
| pending | ⏰ |
| archived | ⛔ |

### 1.2 NODE_NOTE / NODE_EMOJI（同 step 多节点时间线注解，常量 `NODE_NOTE` / `NODE_EMOJI`）

时间线上同一 step 有多个节点时，按状态给文案注解，如
`研发⌛ → 研发🔄 → 研发✅`。archived 用 ⌛ 表示「超时归档」，与
STATUS_EMOJI 的 ⛔（通用归档）区分；其余沿用 STATUS_EMOJI。

| 状态 | NODE_NOTE 文案 | NODE_EMOJI |
|---|---|---|
| archived | 超时 | ⌛ |
| running | 重启 | 🔄 |
| done | 完成 | ✅ |
| ready | 就绪 | 🔵 |
| blocked | 堵塞 | 🚫 |
| pending | 等待 | ⏰ |

### 1.3 EVENT_MARK（事件窗口标记，常量 `EVENT_MARK`）

| 事件 | 标记 |
|---|---|
| done | ✅ |
| failed | 🚨 |
| blocked | 🚫 |
| running | 🔄 |
| ready | 🔵 |
| pending | 🔵 |

### 1.4 其他标记

| 标记 | 含义 |
|---|---|
| ⏭️ | 智能跳步（skip_steps） |
| 📍 | 独立卡（standalone，分行展示） |
| ⚠️cc | cc 执行模式违规 |
| ⚠️ | 堵塞告警 |
| 🚨 | 失败 |
| ✅✅ | 当日完结链/独立卡折叠行 |
| ⚠️无编号 | 无编号尾标（链/卡提取不到 CARD_CODE_RE 编号时追加） |

## 2. 链行语法

```
[编号]链名: 步骤名emoji→步骤名emoji→…
```

- 例: `[DPL-136]收尾链: 产品✅→架构✅→研发🔄→…`
- 同 step 多节点时间线: `研发⌛→研发🔄→研发✅`（NODE_EMOJI 注解）。
- 折叠行: 当日完结链/独立卡超量时折叠为 `✅✅ ×N: [编号]列表`。

### 2.1 截断与折叠（DPL-185 v1.0，活跃优先单规则）

链行超显示预算（主链行 120 / GAI 树形行 120，`bl[:80]` 硬切已退役）时，
统一按 `_clip_node_chain_line` 活跃优先截断:

1. **活跃优先截断**: 任一 running(🔄)/blocked(🚫)/pending(⏰)/死卡(⛔)/
   打回(🔁)/超时归档(⌛) 节点强制保留在可见区内（完整节点、严禁半词）；
   done(✅) 节点按链头顺序优先牺牲。
2. **done 计数尾注**: 被牺牲的 done 节点以 `…(N✅)` 计数尾注呈现（N=数量），
   绝不吞噬活跃节点预算。
3. **历史分支折叠**: 历史分支（全部 [CARD] done/archived）>4 条时折叠为
   最新 3 条 + `│ …（折叠 N 条）` + 最旧 1 条；≤4 条全显。

预算分配优先级: `[CODE-NNN] 编号`（OC 对账锚点，任何情况不牺牲）>
活跃节点 > done 节点 > 链名（超预算时链名侧截短，编号段完整保留）。

### CHAIN_ORDER（链步骤顺序，常量 `CHAIN_ORDER`，13 步）

prd → arch → dev-est → dev → va-claim → qa-d1 → qa-exec → qa-d2 →
va-qa → merge → qa-post → va-post → close

（中文简称见常量 `STEP_LABELS`: 产品/架构/评估/研发/VA/测试方案/执行/评审/VA/合并/回归/VA/关闭）

## 3. 卡片关系语义

| 关系 | 语义 | 渲染 |
|---|---|---|
| 上下游 | 同链内步骤先后 | 同一链行内 `→` 连接（按 CHAIN_ORDER） |
| 并行 | 相互独立的卡 | 独立卡分行展示，前缀 📍 |
| 依赖 | task_links 链归属 | 同编号卡归入同一链行（CARD_CODE_RE 提取编号） |
| 阻塞 | 卡片 blocked | 节点 🚫 + 链级 priority 上浮 |
| 无编号 | 提取不到编号 | 行尾追加「⚠️无编号」 |
