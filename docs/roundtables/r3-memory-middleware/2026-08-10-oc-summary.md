# Roundtable R3 独立卷收卷 — 记忆中间层（memory middleware）宏观规划

> 日期：2026-08-10 ｜ 类型：B 类 Brainstorming — R3 独立卷（product / architect / engineer 并行出卷，不传递）
> OC 收卷：三卷已全部完成并提交，本文档做交叉对比 + 提炼分歧供 Frank 裁决。

---

## 一、Frank 裁定背景（本卷的坐标系）

上一轮 R1/R2（LLM-Wiki 记忆系统 + GAI 自动更新）方向抓错了重点，已全部暂停。Frank 重定向：

> **用新技术完整开发一个记忆中间层（memory middleware），弥补现有 Hermes 记忆的不足。**

三点指示：
1. **wiki-llm 是绝对核心**：先获取 wiki-llm 文档，宏观规划如何建立记忆中间层；要完整开发，不是小功能
2. **GAI 待办条目没细节只是附属品/MVP**：中间层搭成功后，GAI、跨记忆会话、项目共享文件存储都会自然产生解决办法
3. **中间层核心是 wiki-llm，可引入其他机制加强**（如记忆宫殿 memory palace）；把 GAI 里 mem 相关所有条目捞出来统一评估

## 二、三卷核心立场

| 维度 | Product（许清楚） | Architect（高见远） | Engineer（寇豆码） |
|------|------------------|-------------------|------------------|
| 问题定性 | 纠正遗忘（月浪费 7-17h）+ 决策不可追溯 + 记忆碎片化 + 会话上下文断点 | **「编译器不是搜索引擎」**（Karpathy 核心隐喻）：中间层本质是知识编译器 | 确定性引擎扛检索/索引/漂移，LLM 只做策展 |
| 定位 | 补充层 L3 知识编译层，不替代、不抽象层 | L3 wiki-llm + L4 检索导航层，**叠加渐进吸收**（否决推倒重建） | /workspace/mem-core 独立 repo「库+CLI+skill」，无守护进程 |
| 北极星 | **Frank 重复教的次数归零**（页数是手段，不重复教才是目的） | 三条铁律：单一写入者（memctl CLI）/ 状态不回写环 / 机械层零 LLM | 一个 repo + 一条命令 + 两个挂点（boot_context v2 读、close.sh S3 写） |
| 优先级 | wiki 核心 P0-1 > 写入通道 P0-2 > 读取协议 P1-1 > 记忆宫殿 P1-2 > GAI MVP P2 | P1 GAI MVP 11.5h → P2 中间层核心 2.5 人天 → P3 记忆宫殿 1.5 人天 → P4 可选 2 人天 | MVP 9.5h（引擎本体）→ V2 10h → V3 13h 可选（总 19.5h） |
| 工时口径 | —（未给总量） | 11.5h + ~4 人天 | 19.5h（MVP 9.5h + V2 10h） |

## 三、高度一致项（共识基础坚实）

1. **wiki-llm 是绝对核心**：三方一致，无异议（对应 Frank 指示 1）
2. **GAI 降级为应用/MVP，不是系统本体**：三方一致（对应 Frank 指示 2）——Engineer 直接取消 R1 的 gai.py 表感知解析器 3h 预算，GAI 只需 `mem gai-links` 断链校验 1.5h
3. **记忆宫殿引入，但作为标签/增强非目录**：Architect「Wing/Room/Shelf 是 frontmatter 标签 + index 双视角，不是目录——两套目录=双倍维护」；Product 语义迁移（标签对象从 session 流改为 wiki 知识页）；Engineer「SCHEMA location 枚举」
4. **MEM-006 翻案**：三方实测确认 **SQLite FTS5 trigram 对 CJK 可用**（sqlite 3.53.1 实测 3 字查询全命中，2 字用 bigram/LIKE 补）——「无 CJK 分词器不修」裁定过时，**升 P2 并入中间层**（Architect 升 P2；Engineer 并入 M1）
5. **MEM-005 维持不修**：三方一致（中间层主路径不依赖 embedding，上向量须换 bge-m3 级中文模型）
6. **单一写入者 + 事件驱动 + 状态不回写环**：三方一致
7. **跨会话恢复 = 启动协议 + boot_context 增强**：Architect「会话启动协议（SCHEMA→index→log→定向读页 10-20 文件）+ _wiki_digest()」；Engineer「boot_context v2 加第五源 mem context」
8. **写入路径三层**：close.sh S3 主路径（强制）+ skill 协议 + 周 cron 兜底（R2 已收敛，本卷延续）

## 四、需修正项 / 关键分歧（供 Frank 裁决）

### F1：实施顺序 — GAI MVP 先做还是引擎本体先做？
- **Architect**：P1 本周 GAI 决策档案 MVP ~11.5h（验证编译管线，R1 已定案）
- **Engineer**：MVP 9.5h 是**引擎本体**（repo+SCHEMA+索引+CLI+pytest），GAI 只是 V2 的适配器 1.5h
- **Product**：记忆宫殿排在 GAI 前（「GAI 只是应用的表单细节，记忆宫殿是系统自身规模问题」）
- OC 观察：三方其实都同意「引擎优先」，分歧是 **GAI 作为引擎的验证场景应该排在第几**。Product 明确说记忆宫殿 > GAI，Architect 说 GAI 是 P1 验证场景。

### F2：repo 形态 — 引擎与 wiki 正文同仓还是分仓？
- **Engineer**：`/workspace/mem-core` 独立 repo，wiki 正文与引擎**同仓**（反共识 R1 两仓方案：「SCHEMA 与解析器必须同步提交、lint 可验证」）
- **Architect**：wiki repo 本身就是共享存储，与 devPPL repo 物理隔离；未明确引擎与正文是否同仓
- OC 观察：Engineer 的理由（SCHEMA/引擎/正文同步演进防漂移）与 Architect 的「wiki repo 即共享存储」不冲突，但需 Frank 裁定同仓 vs 分仓。

### F3：MEM 条目处置差异
| 条目 | Product | Architect | Engineer |
|------|---------|-----------|----------|
| MEM-001 /learn+/journey | 并入（L2 写入源，learn 内容必须映射 wiki 页） | 吸收 | 降为依赖项（中间层建成后启用） |
| MEM-002 Wing/Room/Shelf | 并入但语义迁移（标签对象从 session 流改为 wiki 知识页） | 吸收（frontmatter 标签） | 并入 M0（SCHEMA location 枚举） |
| MEM-003 LLM pipeline 测试 | **独立**（mem0 平台侧债） | 吸收 | 废弃吸收为 mem-core 测试体系 |
| MEM-004 wikilinks | 并入，P3 升 P0 | 吸收 | 并入核心 |
| MEM-005 bge 中文噪声 | 废弃（主路径不依赖 embedding） | 维持 P5 | 维持 P5 |
| MEM-006 FTS5 CJK | 维持不修（历史债） | **升 P2**（trigram 修正） | **翻案并入 M1**（trigram+bigram） |
| DPL-011 跨会话记忆 | 并入，升格读/写/摘要三协议 | 归档保持，实现升级为索引式恢复 | 被上下文引擎吸收 |

- **MEM-003 分歧**：Product 认为独立（mem0 平台侧债），Architect/Engineer 认为吸收进中间层测试体系。若中间层自己有 golden file 测试，MEM-003 可以吸收——但 mem0 平台侧的管道测试债仍是独立的，需 Frank 定。
- **MEM-006 是本次最大翻案**：之前「不修」裁定基于「需要分词器」的错误前提，实测 trigram 零依赖可用。

### F4：Product 与 Architect 的 L 层命名差异
- Product：L3 知识编译层（补充层，不替代不抽象）
- Architect：L3 wiki-llm + L4 检索导航层（叠加渐进吸收，L2 mem0 保留 fast-path 逐步被吸收）
- OC 观察：实质一致（都是新增编译层 + 检索增强），仅命名/边界表述不同，不构成真分歧。

## 五、实测发现（本卷新增）

1. **MEM-006 翻案实锤**：sqlite3 3.53.1 `FTS5 tokenize='trigram'` 对 CJK 可用（`中间层`/`宏观规划`/`记忆宫殿` 3 字查询全命中；2 字 MATCH 为 0 但 LIKE 命中，bigram 回退表补 2 字）——零依赖解决 CJK 检索
2. **workspace GAI 副本仍在 git**（197 行旧格式），R1 M0（git rm）从未执行——MVP 第一步仍要 git rm
3. **llm-wiki skill 实际 13 份副本**（12 profile + 默认池），非任务书写的 10

## 六、OC 建议

1. **方向已对齐 Frank 裁定**：三方全部回到「wiki-llm 为核心建记忆中间层」，无一人再跑偏到 GAI 单点——R3 独立卷达成了 R1/R2 没达到的共识
2. **F1-F3 三处分歧需要你裁决**，其中 MEM-006 翻案建议直接采纳（零依赖、有实测）
3. **B 类规则：本报告不建执行卡**。你裁定方向后，OC 再按 6 步闭环拆卡派发
4. 三份完整卷已提交：`docs/roundtables/r3-memory-middleware/`（product / architect / engineer 三份 md，commit 0f4933a / 2676ce7 / 3648814）
