# VA 独立验证报告 — 记忆中间层（mem-core）MVP

- **任务**: t_56ea4e12 [Step4] VA 验证 — 记忆中间层（mem-core）MVP
- **验证者**: Verification Agent（verifier profile）
- **时间**: 2026-08-10T13:05Z
- **验收权威**: docs/prd/memory-middleware-prd.md §5.1（唯一权威）
- **实测对象**: /workspace/mem-core（独立 repo，HEAD 7e206bf）
- **方法**: 独立实测 memctl 命令 + pytest + 断链/trigram 负面测试 + devPPL 集成点交叉验证；不转述 QA/研发 summary

---

## 一、逐项验证结果（PRD §5.1 A1-A9）

| # | 断言（PRD §5.1） | 验证方式 | VA 独立实测 | 结果 |
|---|------------------|----------|------------|------|
| A1 | workspace GAI 副本已从 git 删除，`git log` 可追溯删除提交 | `git ls-files \| grep GLOBAL_ACTION_ITEMS` 为空 | `git ls-files` 命中 = 0（EMPTY）；删除提交 9ae67d0 存在且可追溯（197 行删除） | **PASS** |
| A2 | `mem lint` 输出零问题（四不变式全过），退出码 0 | 执行 `memctl lint` | 真实 repo 实测：I1/I2/I3/I4 全 PASS，`lint_exit=0` | **PASS** |
| A3 | `mem query <≥3字中文词>` 命中对应页（trigram）；2 字词 bigram/LIKE 命中 | 对首批 3 页内容执行查询 | 3 字「编译器」命中 r3-architect（1 页）；4 字「记忆中间层」命中 4 页（SCHEMA/r3-architect/r3-product/index）；2 字「中间」通过 bigram/LIKE 命中 5 页 | **PASS** |
| A4 | `mem index --rebuild` 幂等：重复构建后 mem_meta.db 与 wiki 文件一致 | rebuild 前后 lint 均为 0 问题 | 实测 rebuild → lint=0 → rebuild → lint=0，两次 rebuild 输出一致（pages:6, links:15, broken:0） | **PASS** |
| A5 | close.sh 关闭任务自动写 wiki 页（`mem done` 生效），页面含结果节 + status=done + updated | 关闭测试任务，检查 wiki 页 | 独立沙盒实测 `memctl done`：追加「## 结果（memctl done 追加）」节 + status: done + updated bump 2026-08-10T13:02:08Z | **PASS** |
| A6 | boot_context 输出包含 wiki 段（第五源）；mem-core 缺失/失败时 5min 注入不阻塞（静默降级） | 移除 mem-core 路径跑一次 | `MEM_WIKI_PATH=/workspace/mem-core` 时输出含「### wiki 段（第五源）」3 R3 页；`/nonexistent/mem-core` 与 `/tmp`（无 memctl）均静默降级为空段，注入照常，exit 0 | **PASS** |
| A7 | 备份 manifest 包含 mem-core repo | 检查 manifest.yaml | /workspace/manifest.yaml 与 backup-repo/manifest.yaml backup_roots 均含 `/workspace/mem-core/`（P0-8 BKP-003 模式，排除 .git/pyc） | **PASS** |
| A8 | 首批 3 页（R3 三方发言编译）四段非空 + ≥1 参考来源 + ≥2 出链 | lint 断链检查 + 抽查 | 3 页均含 背景/要解决的问题/验收标准/参考 四段；参考节含源卷路径 + PRD；正文 [[wikilink]] 出链 3 条/页 + frontmatter links 3 条 | **PASS** |
| A9 | pytest 套件全绿（≥15 用例，含 golden file 测试） | pytest 退出码 0 | 独立运行 `pytest tests/`：**89 tests collected, 全绿**, exit 0 | **PASS** |

**结论：A1-A9 全部 PASS（9/9）。**

---

## 二、任务书补充验收点

| # | 断言 | VA 独立实测 | 结果 |
|---|------|------------|------|
| CLI 12 命令面 | memctl 12 命令（MVP 7 + V2 4 stub + V3 mcp-serve） | `memctl --help` 列出 12 子命令：add/done/query/lint/index/status/context + update/drift/gai-links/demote + mcp-serve | **PASS** |
| mem 软链 | `mem` 软链别名 | bin/mem -> memctl（lrwxrwxrwx，相对链接） | **PASS** |
| 退出码 0/1/2/3 | 命令全集退出码语义 | 实测：lint 零问题=0；add 非法 ID=1；无命令用法错误=2；断链 lint 失败=3；done --check 三态（不存在=1/未 done=3/done=0） | **PASS** |
| mem_meta.db 生成 | wiki 文件确定性生成（index --rebuild 幂等） | 见 A4；pages/links/events + FTS5 trigram + bigram 由 indexer 重建 | **PASS** |
| 双链校验（断链检测） | 断链检测通过 | 负面测试：注入断链 `[[nonexistent-page.md]]` → lint I1:ERROR 捕获（「断链」），exit 3；正常 repo lint 零问题 | **PASS** |
| GAI 展示镜像 S3b | close.sh S3b GAI 状态列镜像 | close.sh 双份（live + backup）md5 一致 fd22da95aef4f009da169b4437c9a1e2；S3a/S3b 逻辑存在；GAI L0 源文件存在（orchestrator/GLOBAL_ACTION_ITEMS.md） | **PASS** |
| boot_context 第五源接入 | wiki 段 ≤800 字、优先级低于活跃任务段 | 输出段序：header→task→wiki→session→memory；_wiki_digest max_chars=800 强制截断 | **PASS** |
| A1 前置（任务书） | SCHEMA.md 存在且 lint 通过 | wiki/SCHEMA.md 存在（v1.0, 2026-08-10）；lint I1-I4 全过 | **PASS** |

---

## 三、红线检查（PRD §7.2 BE-10 语义）

**断言：本体文件（soul/memory/.hermes.md/SKILL.md）未被 mem-core 替换或修改。**

| 检查项 | 证据 | 结果 |
|--------|------|------|
| mem-core repo 是否含本体文件 | `git ls-files \| grep -i "soul\|memory\.md\|hermes\.md\|SKILL"` → NONE | **PASS** |
| devPPL .hermes.md 本体 | .hermes.md 仍为 devPPL 项目规范原文（42 行），git 跟踪中；git diff HEAD 为空（无新改动）；仅 BOOT_CONTEXT_START/END 动态段由既有 boot_context cron 维护（DPL-011 既有机制，非 mem-core 新增替换） | **PASS** |
| SCHEMA.md 边界声明 | wiki/SCHEMA.md 三边界：wiki 不存状态 / 不替代检索 / 不存事实偏好；无任何「替换 Hermes 本体」内容 | **PASS** |
| 替换提案审批 | 无未签字替换提案进入代码 | **PASS** |

**红线检查结论：PASS（无本体文件被替换/修改）。**

---

## 四、职责分离确认（QA 测改不分残留）

| 检查项 | 证据 | 结果 |
|--------|------|------|
| mem-core 提交者 | git log 全部 9 条提交 author = `memctl compiler <memctl@mem-core.local>`（单一写入者机械提交身份） | **PASS** |
| 无 QA 直接提交 mem-core | QA 测试脚本 run_memory_middleware_tests.py 位于 devPPL docs/qa/（不在 mem-core repo 内）；mem-core 内无 QA 身份提交 | **PASS** |
| QA 结果 vs 独立实测 | QA 报告 R0-4 曾 FAIL（lint rc=3 db 不一致）→ 已由 MEM-QA-01/04 FIX 提交修复（6b39166/f87cc46）；VA 独立实测当前 lint rc=0 | **PASS** |

**职责分离结论：PASS（mem-core 全部提交为编译入口机械提交，无 QA 直接写码）。**

---

## 五、观察项（非阻断）

1. **OBS（低风险）**：`_wiki_digest()` 从 `os.environ` 继承残留 `MEM_DB_PATH` 时可能读到错误 DB（测试中残留 env 曾导致 wiki 段显示外部测试页）。QA 脚本 OBS-03 明确要求「每个 memctl 调用显式构造 env，绝不继承残留 MEM_* 变量」——boot_context.py 已显式设置 MEM_WIKI_PATH，但未显式清空其他 MEM_* 残留。生产 cron 环境干净时无影响（A6 验收场景 PASS），建议 V2 顺手补 `env.pop("MEM_DB_PATH", None)` 对齐 OBS-03。
2. **说明**：mem-core git status 有未提交变更（wiki/log.md 修改 + 若干 _check/scratch 文件）—— 属 QA 执行期间生成物，不影响验收断言；log.md 修改为 memctl index 追加行为（机械层预期）。
3. **说明**：wiki/mem_meta.db（0 字节占位）+ 根 mem_meta.db（548KB）并存 —— status 显示 DB 在根路径，占位文件无功能影响。

---

## 六、结论

**VERIFIED — 9/9 全绿（A1-A9）。**

mem-core MVP 通过 VA 独立复核：引擎（schema/parse/indexer/blast/drift/context/lint/cli）实测可用，CLI 12 命令面 + 退出码语义正确，FTS5 trigram CJK 检索实测命中，rebuild 幂等，断链检测负面测试捕获正确，boot_context 第五源静默降级实测通过，close.sh S3a/S3b 双份 md5 一致，manifest.yaml 备份接入确认，首批 3 页内容结构完整，pytest 89 用例全绿。红线（本体文件未替换）与职责分离（提交者全为 memctl compiler 机械身份）均确认无残留。

**未发现 FALSIFIED 项，无需创建 FIX 卡。**
