# R2 发言：寇豆码（研发工程师）— 回应分歧点

> 发言时间：2026-07-08
> 发言轮次：R2（交叉辩论，回应 QA 分歧点）
> 回应对象：QA（测试工程师）R1 发言中的 4 个分歧点

---

## 总体回应

QA 的 R1 发言是我读过的最完整的 QA 视角文档。状态机、复现证据矩阵、QA 侧 SLA——这些是之前缺失的实操骨架。我在 R1 中补了 5 个工程维度，QA 补了 6 个实操维度，两套拼起来正好是「标准→落地」的完整链路。以下 4 个分歧点逐一回应，我的姿态是：**能接受的直接接受，需要加条件的说清楚条件，不能接受的给出替代方案。**

---

## 分歧 1：可复现性门禁 — 「自动降级」vs「区分无证据/难复现」

### ① 立场

**我接受 QA 的修正方案。** 我 R1 的「自动降一级」确实太粗糙了——它把「QA 没提供任何证据说 crash 了」和「QA 提供日志/录屏/trace ID 但竞态条件就是 1/200」混为一谈。前者是流程问题（该降），后者是技术现实（不该降）。QA 的二分法更准确。

### ② 让步条件

我接受以下替代方案，替换我 R1 §4.1 的原始提案：

```
情况 A：「无证据可复现」
  QA 说 "it crashed" 但无日志、无截屏、无环境信息、无复现率
  → SLA 时钟暂停，等待 QA 补充（BLOCKER 2h / MAJOR 1 工作日）
  → 超时仍未补 → 可降一级

情况 B：「有证据但难复现」
  QA 提供了日志片段、录屏、trace ID、复现率（如 1/50）
  但研发仍无法稳定复现
  → 不降级，标记 hard_to_repro
  → SLA 时钟暂停，研发与 QA 协作定位
  → 研发「cannot repro」驳回必须附带：
      - 尝试复现的环境信息（OS/浏览器/版本/部署环境）
      - 尝试次数（BLOCKER ≥ 20, MAJOR ≥ 10）
      - 环境差异说明（如 "QA 在 staging-asia，我在 dev-us，DB 副本不同"）
  → 未满足以上条件 → 驳回不成立，issue 回退
```

### ③ 一句话理由

竞态条件和 Heisenbug 是代码的真实属性——不是因为 QA 没写清楚复现步骤。我的代码如果有 race condition 导致 1/200 的崩溃，它就是 BLOCKER，不应该因为「QA 不能总结为 step 1-2-3」而自动降级。但「没证据就说 crash」和「有证据但难复现」确实是两回事，QA 的分法更精确。

---

## 分歧 2：性能阈值 — 1s/5s 绝对值的合理性

### ① 立场

**1s/5s 对交互式 endpoint 合理，但对重操作 endpoint 不适用。** 需要按 endpoint 类型分层，而不是一刀切。

### ② 让步条件

我 R1 的 fallback 表缺少一个维度：不是所有 endpoint 都是交互式的。修正如下：

| Endpoint 类型 | 例子 | 退化判定（APM 就绪前） | 说明 |
|:---:|---|---|---|
| **Interactive** | 页面加载、按钮点击、API 查询 | < 1s → MINOR, 1s–5s → MAJOR, > 5s / OOM → BLOCKER | 用户实时等待。原阈值适用。 |
| **Heavy Op** | 报表生成、批量导出、数据同步 | 记录每次操作的基线耗时（首次作为 baseline），后续 > 2x 基线 → MAJOR, > 3x → BLOCKER | 这类操作本身耗时长，不能和非交互式用同一把尺子。需要 per-operation 记录。 |
| **Background/Async** | 消息推送、定时任务、离线计算 | 不参与实时性能阈值。由任务执行成功率 + 延迟率单独监控。 | 用户不等待。用成功/失败判断，不用响应时间判断。 |

**对 QA 问题的直接回答**：如果一个报表生成 endpoint 正常是 30s，退化到 35s——它不是 BLOCKER，甚至不是 MAJOR。但如果退化到 60s+（2x），那是 MAJOR。如果退化到 90s+ 或超时/OOM，那是 BLOCKER。

**工程落地**：Heavy Op 的基线记录很简单——首次运行时把耗时写入 issue 系统的一个字段（`baseline_duration`），后续提交同 endpoint 的性能 bug 时自动对比。不需要 APM，这是一个 issue 模板的字段设计问题。

### ③ 一句话理由

「超过 5s 就是 BLOCKER」对 99% 的 endpoint 正确，但对那 1% 本身就是重操作的 endpoint 会产生噪音——把每次正常耗时波动都标成 BLOCKER，反而稀释了 BLOCKER 的信号价值。

---

## 分歧 3：环境差异处理

### ① 立场

**接受 QA 的整合方案，完全同意。** 级别不降（QA）+ SLA 可暂停（研发）+ 环境差异不能作为驳回理由（QA）——这是最干净的三方平衡。

### ② 让步条件

我的 R1 §4.3 原始表述是「研发在 dev/local 无法复现时 SLA 暂停」，QA 补充了两个关键点我全部接受：

1. **级别判定维度 vs SLA 计时维度是两个独立轴。** Bug 在 production 上是 BLOCKER → 级别就是 BLOCKER，跟我能不能在 dev 复现无关。SLA 暂停是给我调试的工具，不是给 bug 降级的借口。
2. **环境差异不能作为驳回理由。** 「Cannot repro in dev」≠「bug 不存在」。这是一个很重要的防护——防止「我在本地跑了一遍没出来所以关掉」的廉价驳回。

补充一点举证责任的约定（QA 没明确说，但工程实践需要）：

| 谁主张环境差异 | 需要提供什么 |
|---|---|
| **QA**：「这个 bug 只在 staging 出现」 | staging 环境的日志/截屏/trace ID + staging 和 dev 的已知差异（DB 数据量、配置、网络拓扑） |
| **研发**：「我在 dev/local 无法复现」 | dev 环境信息 + 尝试复现次数 + dev 和 staging 的已知差异 |

**双方都不能只主张不举证。** 「我试了没出来」不是有效信息——「我试了 15 次，用的 dev-us 环境，DB 是从上周的 snapshot 恢复的，和 staging 的差异是 X」才是。

### ③ 一句话理由

环境差异是 tooling/process 问题，不是 bug severity 问题——它应该影响「我们怎么处理这个 bug」而不是「这个 bug 有多严重」。把这两个维度解耦是正确的。

---

## 分歧 4：技术债追踪工具化 — Required Fields + Dashboard MVP

### ① 立场

**Dashboard 的主要使用者是 QA + 架构师（高见远），研发是实现者。** QA 用 Dashboard 做质量监控，架构师用 Dashboard 做架构腐化检测；研发消费它的输出（被告知「你的模块技术债超标了」），但不一定是日常使用者。QA 说 Dashboard 的主要用户是 QA，我同意——但是这不妨碍研发负责构建它。

### ② 让步条件

#### Required Fields（必须在 issue 系统中强制）

| 字段 | 适用级别 | 类型 | 为什么是 required |
|---|---|---|---|
| `module` | **全部** | dropdown（从模块清单选） | 没有模块归属，Dashboard 的 per-module 统计全部失效。这是整个技术债追踪系统的基础数据。 |
| `issue_type` | **全部** | enum: `bug` / `tech_debt` / `security` / `performance` / `observability` | 需要区分「这是功能 bug 还是系统性问题」。observability 类型对应 QA 的 `observability_gap` 标签。 |
| `root_cause_category` | **MAJOR+** | enum: `logic_error` / `data_issue` / `concurrency` / `config_misuse` / `third_party` / `infra` / `unknown` | MAJOR+ bug 积累到一定量后，root cause 分布能告诉架构师「我们团队的系统性弱点在哪」（比如 concurrency 占比 40% → 团队需要 Go/并发培训）。初始可填 `unknown`，研发评估后修正。 |
| `data_sensitivity` | **MAJOR+** | enum: `S` / `A` / `B` / `C` / `none`（按 R1 分类表） | 落实高见远的数据敏感度加权。`S` 级（资金/资产/PII）自动 visual highlight。 |
| `associated_version` | **全部** | string（如 `v2.4.1`） | 没有版本号就无法做「连续 3 版本」的统计。 |

> 工程实现：这些字段就是 issue 模板里的 dropdown。Godot/GDScript 项目的话，如果有自建 issue 系统就是加几个 column；如果用 Jira/Linear 就是配置 custom fields。无论哪种，一天内的工程工作。

#### Dashboard MVP（v0，最小可行功能）

**不需要花哨的可视化，3 个 panel 就够：**

**Panel 1 — 模块健康度总览**

| 指标 | 数据来源 | 阈值 |
|---|---|---|
| 当前版本 MAJOR+ 数量（per module） | `module` + `issue_type` + `level` | — |
| 最近 3 版本 MAJOR+ 累计（per module） | `module` + `issue_type` + `level` + `associated_version` | ≥ 3 → 自动通知架构师（高见远） |
| `cannot_repro` 驳回率（per module） | issue 状态流转记录 | > 30% → 该模块可能有可调试性问题 |
| `observability_gap` 密度（per module） | `issue_type=observability` 计数 | — |

**Panel 2 — Root Cause 分布（饼图或简单 table）**

- `root_cause_category` 的分布（当前版本 + 历史累计）
- 用于架构师判断团队的系统性弱点

**Panel 3 — 技术债积压**

- 所有 `issue_type=tech_debt` 且状态 ≠ closed 的 issue 列表
- 按 module + 创建时间排序
- 最小功能：一眼看到「我们欠了多少债、欠在哪个模块」

**最简实现**：一个 SQLite DB + 一个 Godot Control 节点渲染 table / 或一个简单的 web Dashboard（如果系统是 web-based）。我估 1-2 天开发 + 半天接入 issue 系统 API。

### ③ 一句话理由

技术债追踪的核心不是 Dashboard UI——是 required fields 强迫数据质量。没有 `module` 字段的 issue 系统里，Dashboard 是 garbage-in-garbage-out。先保证每一行数据都是完整的，再谈展示层。

---

## 补充：R2 中发现的额外对齐点

QA 的 R1 中还有一些我完全同意、不需要辩论的点，我在此记录为「已对齐」：

| # | 事项 | QA 立场 | 我的立场 |
|---|------|---------|---------|
| 1 | PII 隐私数据按安全漏洞处理，最低 MAJOR+ | 新增提案 | ✅ 同意。PII 泄露的合规风险等同于安全漏洞。建议在 `data_sensitivity` 分类表里将 S 级扩展为「资金/资产/PII」。 |
| 2 | 性能退化 transition 期间同时记录绝对值和相对值 | 补充建议 | ✅ 同意。issue 模板里加两个字段：`perf_absolute_ms`（当前实测）和 `perf_relative_ratio`（APM 就绪后回溯填充）。 |
| 3 | 跨团队 bug 的 QA 回归时限从「全部修复部署到 staging 后」起算 | 补充建议 | ✅ 同意。这防止「研发修好了但 staging 没部署，QA 的回归时钟已经在跑了」的计时错位。 |
| 4 | BLOCKER 修复的 staging smoke test 由 QA 执行（非研发自测） | 补充建议 | ✅ 同意。研发 review 代码 + QA 验证修复 = 双重检查。这是 BLOCKER 修复门禁的合理分工。 |

---

## 总结

R2 四个分歧点，我的最终姿态：

| 分歧 | 结论 |
|---|---|
| 可复现性降级 | **收回原方案**，接受 QA 的「区分无证据/难复现」二分法 + 研发反驳必须带尝试次数 |
| 性能阈值 | **修正原方案**，1s/5s 只对 Interactive endpoint 适用，Heavy Op 用 per-endpoint 基线对比 |
| 环境差异 | **完全接受 QA 整合方案**：级别不降 + SLA 可暂停 + 环境差异≠驳回理由 + 谁主张谁举证 |
| 技术债追踪 | **细化原方案**：5 个 required fields + 3-panel Dashboard MVP，研发负责实现 |

**核心一致点**：我和 QA 在 R1/R2 立场高度一致——都支持高见远的「有成本申诉」和架构修正，都接受许清楚的 4 级框架骨架，都认为标准需要工程落地条件。这届三方的共识比分歧多得多。

**核心分歧已解决**：可复现性门禁从「自动降级」修正为「区分无证据/难复现」——这是 R2 最实质性的立场调整，也是我认为 QA 提案更好的地方。
