# MEM-017 QA-D1 测试方案（t_ffcd77dc）

> 依据: PRD wiki/projects/devppl/prd/mem017-signal-account-pointer-prd.md v1.0 §3 A1-A5
> 参考优先级: PRD 第一 → 架构第二（arch-mem017-signal-account-pointer.md v1.0）
> 性质: 指针型收口卡（零代码）→ 本卡验证对象 = 收口文档的闭环证据可复现性 + 底层 R2 功能行为抽样
> QA 只测不改: 本卡不产生任何代码/文档修改（发现问题时仅报告）

## 用例矩阵（每条含通过标准）

| # | 用例 | 行为级验证方式 | 通过标准 |
|---|------|----------------|----------|
| T1 | A1 功能符号落 main | mem-core main 工作树 git grep record_signal/resolve_actor/MEM_ACCESS_ACTOR/page_signal | 4 符号均命中 memcore/*.py（预期 decay/cli/schema） |
| T2 | A2 合入记录 | grep wiki/actions/MEM-017.md 收口行 + frontmatter status | status=done 且收口行含 575bd43/0ba037e |
| T3 | A3 测试门禁可复现 | QA 独立复跑 tests/test_mem008_r2_signal.py（14 用例） | 14 passed, 0 failed |
| T4 | A4 四信号齐备（行为级） | 读 schema.py page_signal 表定义 + signal 枚举；R2 测试用例覆盖 view/like/dislike/comment | 四信号在 schema/枚举中出现且 append-only（无 UPDATE/DELETE 路径，对应 test_no_update_delete_on_page_signal） |
| T5 | A5 归档护栏（指针复核） | mem-core main 上跑归档护栏相关测试子集（-k archive 或等价） | 相关子集全绿，无新增红 |
| T6 | actor 三态（行为抽测） | MEM_ACCESS_ACTOR 环境变量显式/缺省两条路径由 T3 内 test_actor_* 覆盖，QA 复跑即独立证据 | 对应用例 passed |
| T7 | 收口文档一致性 | PRD §3 证据表与架构 §1 V1-V3 口径交叉比对（引用路径实存、commit 可达） | 引用文件/commit 均实存，无矛盾陈述 |

## 工作量评估（拆卡判定）
预计 8-12 轮 ≤ 20 → **不拆卡**（N=1）。若 T3/T5 出现预存失败需溯源则升级评估。

## 门禁口径
- 只跑本卡子集（test_mem008_r2_signal.py + 归档护栏 -k 过滤），不跑全量（DPL-137）。
- 预存失败不作为门禁。
- 执行模式 CC-MAX: 测试执行在 cc 内闭环，worker 只做编排与判定。

## 分级标准
按 docs/standards/qa-finding-classification.md §1.2 五步判定；安全类独立判定。
