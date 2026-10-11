# D1 第三棒 — Engineer 可执行性确认（产品裁定 v1.1 实现侧确认）

> 发言人：寇豆码（工程师，game-engine） | 日期：2026-08-10 | 版本：v1.0
> 类型：D1 评审第三棒（engineer 可执行性确认），评审对象 = 产品裁定卷（docs/roundtables/d1-memory-middleware/2026-08-10-product-adjudication.md，v1.1，commit e1cc11c + b748667）
> 输入：QA 测试方案（docs/qa/memory-middleware-test-plan.md，49 用例）+ PRD v1.1 + 架构 v1.0（§4 CLI / §8 close.sh / §9.1 golden）+ 产品裁定 v1.1 + 我第一棒确认卷（2026-08-10-engineer-confirm.md）
> 实测复核：close.sh 双路径 md5/inode、GAI 新格式、check() --fix 语义、devPPL GAI 跟踪、sqlite 版本（见 §5）

---

## 0. 结论速览

| 项 | 结论 |
|----|------|
| 5 项 D1 裁定（F1-F5） | **全部可落地**，MVP 9.5h **零增量**；产品已吸收我第一棒全部修正（S3b 行尾追加 / BE-02 断言对象 / memctl 命名统一 / close.sh md5 断言） |
| 49 用例可执行性 | **45 可执行 + 4 观测项，全部能跑**；路径 A（mock wiki + 真实 mem_meta.db）**可先行**（33 用例），路径 B 12 用例等 dev 集成交付 |
| 新增实现层定案 | 产品裁定未覆盖的 **5 项**（S3b 匹配键 / S3b 幂等 / done --check / close.sh --fix 测试口径 / golden 单副本），均不改变裁定，只补实现口径，见 §3 |
| 一处勘误 | 产品裁定卷 F5 的 engineer 页 `profile:` 写 game-qa，应为 **game-engine**（R3 engineer 卷作者），见 §1-F5 |

---

## 1. 逐项实现确认

### D1-F1 验收编号错位 | 确认：PRD §5.1 唯一权威，零代码影响

- dev 自检对照表 = 架构 §14 里程碑映射（P0-0→A1，P0-3→A3/A4，P0-6→A6，P0-7→A5，P0-8→A7，P0-10→A8）；VA 阶段按 PRD §5 编号逐条断言。
- PRD v1.1 已提交（e1cc11c），§4 P0-4 / §10 已改 7 命令 + 引用架构 §4，源头矛盾消除（实测 grep 确认）。
- 实现影响：无。

### D1-F2 命令面 = 架构 §4.1（12 命令三阶段）| 确认：可落地

- MVP 7（add/done/query/lint/index/status/context）由 A2/A4/A5/A6 断言反推成立，argparse 分发零技术障碍；`bin/memctl` 正式 + `bin/mem` 软链（ln -s，同一入口）。
- 退出码 0/1/2/3 语义清晰；补一个既有细节：query 空结果 = 0（不是错误），lint 有 FAIL = 3（架构 §4.2 + 架构师 D1 卷 §2 已补充）。
- V2/V3 命令 MVP 阶段：`--help` 列出 + stub（未知命令 exit 2）即可，不计 MVP 门禁（产品 QA 对齐口径）。
- 实现影响：P0-4 1h 内；PRD 修订已由产品完成，dev 无需回退。

### D1-F3 memctl done 只写 wiki、GAI 归 S3b | 确认：可落地，铁律 2 边界成立

- `memctl done` 六步（读 L0 只读 → 写 wiki 结果节 + status=done + bump updated → 机械维护 → 原子提交）不碰 GAI，铁律 2 完整保留；close.sh 是 orchestrator 自写自文件，非中间层写路径。
- 产品已采纳我第一棒的 sed 修正（行尾追加而非旧"待办"替换）。实测复核：新 GAI 全文仅 2 行含"待办"（8366B），旧 sed 确认 no-op——行尾追加是**必须**改的，不是可选优化。
- 两个产品未覆盖的实现细节（S3b 匹配键 + 幂等守卫）见 §3-①②。

### D1-F4 close.sh 双副本同步替换 | 确认：可落地，实测双副本成立

- 实测复核（本次）：两路径 md5 相同（64eb0c69eef4a3ecbaa5248ffd05307b）、各 3314B、inode 不同（7456593 / 10248239）→ 字节相同的两份拷贝，非软链。
- 发布路径 = 改活体 `/root/.hermes/profiles/orchestrator/scripts/close.sh` → 备份推送进 backup-repo（git 提交可追溯）；QA 断言 diff 空 + md5 相同 + backup-repo log 可追溯。
- 实现影响：P0-7 0.5h 内；devPPL / mem-core 均不持有 close.sh，不迁移归仓（产品已确认）。

### D1-F5 首批 3 页 = R3 三卷各一页 | 确认：可落地，附 1 处勘误 + 1 个实现定案

- type=decision、落 `wiki/concepts/decisions/`、四段非空 + ≥1 参考 + ≥2 出链、三页互链 + 链 SCHEMA/index；QA 断言内容不断言文件名。
- **勘误**：产品裁定卷写 frontmatter `profile:` 分别标 game-director / game-architect / **game-qa**——第三页（engineer 卷）应为 **game-engine**（R3 engineer 卷作者是寇豆码/game-engine，不是 game-qa）。BE-04 单副本多 profile 用例靠这个标签区分来源，标错源会喂错数据。dev 落地 P0-10 时按 game-director / game-architect / game-engine。
- **实现定案**（golden 单副本，防新双份拷贝漂移）见 §3-⑤。

---

## 2. 49 用例可执行性确认

**结论：45 可执行 + 4 观测项（TC-24~27），全部能跑；路径 A 先行成立。**

| 组 | 数量 | 路径 A（先行） | 路径 B（等 dev 集成交付） |
|----|:---:|:---:|:---:|
| MVP TC-01~18 | 18 | TC-02~12（11） | TC-01 / 13 / 14 / 15 / 16 / 17 / 18（7） |
| V2 TC-19~23 | 5 | TC-19 / 20 / 22 / 23（4） | TC-21（1，需 P1-3 真实回填） |
| 边界 BE-01~15 | 15 | BE-01~09 / 11 / 13 / 14 / 15（14） | BE-10（1，活体本体哈希基线） |
| 端到端 TS-01~07 | 7 | TS-01 / 04 / 05 / 07（4） | TS-02 / 03 / 06（3） |
| **合计** | **49** | **33 先行** | **12 等交付 + 4 观测项** |

**路径 A 可行性依据（实测）**：
- sqlite 3.45.1（2024-01-30）≥3.34，FTS5 trigram 可用（QA 预检脚本 §1.5 已实测定型）；`mem_meta.db` 由真实 indexer 代码构建，非预置 SQLite——"wiki 文件 → db"派生链路（A4/C7 断言对象）成立。
- 依赖仅标准库（sqlite3/json/subprocess/pathlib/argparse/hashlib），无第三方运行时依赖（架构 §12.1）；pytest 需在 mem-core venv 内提供（本机 PEP 668 外部管理，dev P0-5 交付时带 venv 或 uv，QA 路径 A 用它跑）。
- 零外部依赖：kanban/GAI/manifest/备份全部 mock（§1.4 纪律：只 mock 外部依赖，绝不 mock 引擎）。

**路径 B 前置现状（实测）**：/workspace/mem-core 不存在（等 Step 3 dev 交付）；devPPL git 仍跟踪 GLOBAL_ACTION_ITEMS.md（A1 前置成立，TC-01 等 P0-0 执行）。

---

## 3. 新增实现层定案（产品裁定未覆盖，dev P0-7/P0-10 动手前需要）

> 均不改变 5 项裁定，只补实现口径；其中 ①②③④ 必须在 P0-7（close.sh 替换）落地前定，⑤ 在 P0-10 前定，⑥ 随 P0-3 实现留口。

**① S3b 匹配键（t_x vs GAI ID）— 必须在 P0-7 前定**
实测：待办态 GAI 行**不含** t_x kanban ID（全文仅 5 行含 t_，全部在已完成行的备注列，如 `✅ 2026-07-23 — t_697acac7→...`）。`sed -i "/$TASK_ID/s/$/ ✅ done/"` 在 close.sh 以 t_x 调用时匹配不到 P0-xx 行 → GAI 镜像静默失败。
定案：S3b 接受两种 ID 形态——TASK_ID 形如 `P\d+-xx`/`DPL-\d+` 直接匹配行；形如 `t_` 时先 grep 行内是否含该 ID，无则记 FAIL 不阻塞（fail-open，展示镜像非语义写入）；kanban→GAI 真映射留 V2 source adapter `map_id()`（架构 §4.5）。QA TS-03 夹具在 GAI 行内放测试任务 ID 保证确定性。

**② S3b 幂等守卫 — 必须在 P0-7 前定**
行尾追加 `s/$/ ✅ done/` 每次执行都加，重复 close 会叠多个标记。
定案：改条件追加 `sed -i "/$TASK_ID/{/✅ done/!s/$/ ✅ done/}"`；verify grep 收紧为行尾标记 `grep -q "$TASK_ID.*✅ done$"`（避免命中正文含 "done" 的行）。

**③ `done --check` 契约补齐 — 必须在 P0-7 前定**
架构 §8.2 S3a 的 check 引用了 `memctl done <ID> --check`，但 §4.3 done 契约只有 `[--result] [--no-commit]`，无此 flag。
定案：在架构 §4.3 done 契约补 `--check`（只读验证：wiki 页存在且 status=done → exit 0/3，不写任何东西）；S3a 的 check 用它、fix 用 `memctl done <ID>`。dev 不要按原样抄 S3a 的 `--check` 却不实现该 flag。

**④ close.sh `--fix` 是 opt-in — QA 测试口径需对齐（Round 3 前）**
实测 close.sh check() 第 44 行：`if $FIX_MODE && [[ -n "$fix_cmd" ]]` —— fix 动作只在带 `--fix` 参数时执行。QA TC-13/TS-03 写的 `bash close.sh t_test_close`（无 --fix）**不会执行 S3a/S3b 写入**，只会记录 FAIL。
定案：QA 用例改为 `close.sh <id> --fix` 验证写入路径；可加一条负向断言（无 --fix 时只报 FAIL、不写 wiki/GAI）。

**⑤ golden 单副本 — 必须在 P0-10 前定**
产品裁定说 golden/r3-*.md 与真实页"同源"。若 tests/golden/ 存永久副本 + wiki/concepts/decisions/ 存真页，就是第三份拷贝——GAI 双份拷贝 33 天教训的变体。
定案：P0-10 编译 3 页只落 wiki/；golden 测试按路径读真实页（fixtures 引用 wiki/ 路径），或测试内复制到临时目录断言。不维护第二份永久副本。

**⑥ BE-13 强制降级钩子（附带，随 P0-3 留口）**
"模拟无 trigram 环境"需要引擎能强制走降级路径。定案：探测函数可注入/monkeypatch，或提供 `MEM_FORCE_QUERY_FALLBACK=1` 环境变量；否则 BE-13 无法确定执行。

---

## 4. 工时影响

- 5 项裁定 + 5 项实现定案对 MVP 9.5h **零增量**：S3b 模式/幂等/匹配键都属 P0-7 替换步骤本身（0.5h 内）；`--check` 是 done 契约加一个 argparse flag（P0-4 1h 内）；golden 单副本是 P0-10 的组织方式（1.5h 预算不变）；BE-13 钩子随 P0-3 解析器一起实现（3h 内）。
- QA 12.5h 估算成立；Round 1 前 QA 需完成 BE-02 断言对象调整（改为 gai-links 适配器轻量输出，产品已列入对齐项）与 TC-13/TS-03 的 `--fix` 口径（本卷 §3-④）。

---

## 5. 实测复核记录（本卷，2026-08-10）

| 项 | 实测 | 影响 |
|----|------|------|
| close.sh 双路径 | 两文件 md5 相同 64eb0c69eef4a3ecbaa5248ffd05307b，3314B，inode 7456593 vs 10248239 → 字节相同的两份拷贝（非软链） | D1-F4 双副本成立；QA md5 断言可执行 |
| close.sh S3 | :70-73 旧 sed `s/\($TASK_ID.*\)待办/\1✅ done/`；check() 第 44 行 `$FIX_MODE && fix_cmd` → fix 仅 --fix 时执行 | §3-④ 成立；§3-①② 的 sed 必须改 |
| GAI 活体 | 8366B；全文仅 2 行含"待办"；仅 5 行含 t_（全在已完成备注） | 旧 sed no-op 确认；§3-① 匹配键问题成立 |
| devPPL GAI 副本 | git ls-files 仍含 GLOBAL_ACTION_ITEMS.md | A1 前置成立（TC-01 等 P0-0） |
| mem-core | /workspace/mem-core 不存在 | 路径 B 等 dev Step 3 交付；路径 A 不受阻 |
| sqlite | 3.45.1（2024-01-30）≥3.34 | trigram 可用；架构 §5/§15 的 3.53.1 为文档笔误（架构师已勘误） |
| PRD v1.1 | commit e1cc11c：§4 P0-4 = MVP 7 命令 + memctl/mem 软链，§10 引用架构 §4 | F2 源头矛盾已消除，dev 按 PRD v1.1 + 架构 §4 实现 |

---

## 6. 一句话结论

产品裁定 v1.1 从实现角度**全部可落地、MVP 9.5h 零增量**（且已吸收我第一棒全部修正）；49 用例 45 可执行 + 4 观测项全部能跑，路径 A（mock wiki + 真实 mem_meta.db）先行成立（33 用例）；另补 5 项实现层定案——S3b 匹配键（t_x vs GAI ID）、S3b 幂等守卫、`done --check` 契约补齐、close.sh `--fix` 测试口径、golden 单副本——供 Step 3 dev 在 P0-7/P0-10 落地时采用，QA Round 1/3 前同步对齐。
