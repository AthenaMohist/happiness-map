# 拆卡保障 P0+P1 + notify 归并修复 — QA-POST 合并后验证报告

> 版本：v1.0 | 日期：2026-08-13 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_983002f6 [QA-POST] 合并后验证 — 拆卡保障+notify 归并修复（main @ fd85e12）
> 被测状态：**合并后** devPPL main @ `fd85e12`（merge commit，由 merge 卡 t_143376eb 完成）
> 被测内容：3 条链合并后的 main — P0 拆卡保障（34b41e1）+ P1 F-8/F-9 可观测收尾（79875f2）+ notify 归并修复（5a63105）+ P1-2 编号接线（5a48dd2，已在 main）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §6）
> 纪律：**只测不改**，QA 无任何代码改动

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并完整性** | ✅ 3 commit 全为 main 祖先（34b41e1/79875f2/5a63105 → YES/YES/YES），HEAD=fd85e12 |
| 全量测试 `scripts/test_cmd_channel.sh`（合并后） | ✅ **232 PASS / 0 FAIL**（49 个 T-section，含 P0 T42-T50 + P1-2 T40-T41/T52-T53） |
| 全量测试 `scripts/test_notify_check.py`（合并后） | ✅ **226 PASS / 0 FAIL**（含 T59-T63 blocked 优先归并回归） |
| 基线回归 `scripts/test_workspace_check.sh`（存量） | ✅ **40 PASS / 0 FAIL** |
| 关键行为抽查（合并后代码一致性） | ✅ 全部符号存在（详见 §3） |
| 撞号残留 | ✅ 无重复 T42/T43 定义（详见 §4） |
| 语法检查（回归风险） | ✅ autopilot.sh/test_cmd_channel.sh bash -n OK；notify_check/discover/cmd_chain py_compile OK |
| 新增缺陷（POST 阶段） | **0 新增** — 合并未引入回归 |
| 发布门禁（§10） | BLOCKER=0、MAJOR=0、安全=0、未裁定申诉=0 → **通过** |

**结论：PASS。** 合并后的 main 与三条链合并前各自 VA VERIFIED 的状态一致，两套全量测试 + 基线回归全部通过，无撞号残留，无语法回归，无新增缺陷。

---

## 1. 合并完整性检查

| 检查项 | 命令 | 结果 |
|---|---|---|
| 主分支 tip | `git log --oneline -6 main` | ✅ `fd85e12 Merge branch 'wt/t_95ec1a49'` 为 HEAD |
| P0 拆卡保障在 main | `git merge-base --is-ancestor 34b41e1 main` | ✅ YES |
| P1 F-8/F-9 在 main | `git merge-base --is-ancestor 79875f2 main` | ✅ YES |
| notify 修复在 main | `git merge-base --is-ancestor 5a63105 main` | ✅ YES |
| 工作树状态 | `git status --short` | ✅ 干净（仅 5 个既有 untracked：.pipeline/gai/t_b6f75d46.json、docs/qa/ 3 报告、scripts/lib_hermes_path.sh） |

`git log --oneline -6 main` 实测：
```
fd85e12 Merge branch 'wt/t_95ec1a49'
79875f2 feat(discover): F-8/F-9 可观测收尾 — [SUB-SPLIT-HOLD] 回执幂等 + 状态机说明 + 全链路日志
d053734 merge main 5a48dd2: cmd_chain P1-2 编号接线 + T40-T41/T52-T53 测试
5a48dd2 fix(cmd_chain): P1-2 编号接线 — _call_next_seq 调 memctl next-seq + T40-T43 测试
5a63105 fix(notify): 子卡归并 blocked 优先
34b41e1 feat(discover): subsplit hold trigger + process_standalone_subsplit + A9/A10 + T42-T50
```

## 2. 合并后全量测试

测试在 /workspace/devPPL（main @ fd85e12）独立执行，隔离 TMPT/锁，无并行干扰。

### 2.1 `bash scripts/test_cmd_channel.sh`

| 项 | 实测 |
|---|---|
| 结果 | **PASS=232 FAIL=0** — ALL TESTS PASSED |
| 覆盖 | T42-T50 拆卡保障（触发器按住/自动建子卡/parents 串并行/幂等/竞态/链卡回归/A9/F-8/F-9）+ T40-T41/T52-T53 编号接线（next-seq 自动分配/无代码不注入/fail-open/单元测试） |
| 尾部抽样 | T40a-g 建卡+编号注入+归档 ✅；T41a-c 无编号不阻断 ✅；T52a-b fail-open ✅；T53a-k 单元测试 11 项 ✅ |

### 2.2 `python3 scripts/test_notify_check.py`

| 项 | 实测 |
|---|---|
| 结果 | **226 PASS / 0 FAIL** — RESULTS: 226 PASS / 0 FAIL |
| 覆盖 | T59-T63 blocked 优先归并（dev-sub 混合含 blocked → 研发🚫；qa-exec-sub → 执行🚫；全 done → ✅ 不误报；全 running/混合非 blocked → 🔄） |
| 尾部抽样 | T60-2 卡链显示 研发🚫（blocked 不再被归并掩盖）✅；T61-2 执行🚫 ✅；T62-1/T63-1 回归不误报 ✅ |

### 2.3 `bash scripts/test_workspace_check.sh`（存量基线，若存在）

| 项 | 实测 |
|---|---|
| 结果 | **PASS=40 FAIL=0** — ALL TESTS PASSED |
| 覆盖 | 基线存量回归（T10 注入幂等、T13 评估步注册等），合并未破坏 |

## 3. 关键行为抽查（合并后代码一致性）

| 检查项 | 位置 | 结果 |
|---|---|---|
| discover.py 含 `subsplit_hold_after_update` | L121 常量 + L392/399/454 触发器 SQL/安装 | ✅ |
| discover.py 含 `process_standalone_subsplit` | L827 def | ✅ |
| discover.py 含 `_has_subsplit_receipt` | L750 def | ✅ |
| cmd_chain.py 含 `_call_next_seq`（编号接线） | L177 def | ✅ |
| cmd_chain.py 含 `idem_prefix`（拆卡复用） | L663/669/689 | ✅ |
| notify_check.py 含 `_merge_sub_status` | L1259 def + L1322/1325 调用 | ✅ |

## 4. 撞号残留检查

- `test_cmd_channel.sh` 中 T42/T43 定义各仅 1 处（`grep -nE '^T4[0-9]...'` 无重复行）。
- 编号布局实测：T42-T50（拆卡保障，P0）+ T40-T41/T52-T53（编号接线，P1-2 重编号防撞号）→ 与任务描述一致，**无撞号残留**。

## 5. 回归风险（语法检查）

| 脚本 | 检查 | 结果 |
|---|---|---|
| scripts/autopilot.sh | `bash -n` | ✅ OK |
| scripts/test_cmd_channel.sh | `bash -n` | ✅ OK |
| scripts/notify_check.py | `python3 -m py_compile` | ✅ OK |
| pipeline/discover.py | `python3 -m py_compile` | ✅ OK |
| pipeline/cmd_chain.py | `python3 -m py_compile` | ✅ OK |

## 6. 标准对照（qa-finding-classification.md v1.0）

**6.1 判定公式对照（§1.2）**

POST 阶段验证未发现任何缺陷（0 finding），无分级对象。为审计完整，逐条说明：

| 公式前提 | 是否触发 |
|---|---|
| 安全漏洞（§2） | 否 — 无涉及 OWASP/认证/数据泄露的改动面 |
| 用户可感知 | 否 — 无功能行为缺陷，测试全绿 |
| 功能阻断 | 否 |
| 数据一致性 | 否 — 测试断言覆盖建卡/幂等/状态归并，全部符合预期 |
| 性能退化 | 否 — 无性能类改动，语法与运行正常 |

**6.2 SLA 对照（§8/§9）**

无 BLOCKER/MAJOR 发现，不触发 SLA 流程（4h 响应/8h 定位/24h 方案不适用）。QA 侧 SLA：验证任务当场完成，报告随卡提交。

**6.3 分级示例对照（§5）**

不适用 — 0 finding，无示例可对照。

**6.4 发布门禁（§10）**

| 门禁项 | 要求 | 实测 |
|---|---|---|
| BLOCKER | =0 | ✅ 0 |
| MAJOR | ≤3 | ✅ 0 |
| 安全漏洞 | =0 | ✅ 0 |
| 未裁定申诉 | =0 | ✅ 0 |

**结论：门禁通过。**

---

## 7. 结构化 Claim（供 VA 验证）

```
[CLAIM] QA-POST 合并后验证 PASS（t_983002f6, main @ fd85e12）
- 合并完整性: 34b41e1/79875f2/5a63105 全为 main ancestor（YES×3），HEAD=fd85e12，工作树干净（仅 5 既有 untracked）
- 全量测试: test_cmd_channel.sh 232/0 PASS；test_notify_check.py 226/0 PASS；test_workspace_check.sh 40/0 PASS
- 关键符号: discover.py subsplit_hold_after_update(L121/392/399/454)+process_standalone_subsplit(L827)+_has_subsplit_receipt(L750)；
  cmd_chain.py _call_next_seq(L177)+idem_prefix(L663/669/689)；notify_check.py _merge_sub_status(L1259+1322/1325)
- 撞号: T42/T43 无重复定义，T42-T50 + T40-T41/T52-T53 布局正确
- 语法: autopilot.sh/test_cmd_channel.sh bash -n OK；notify_check/discover/cmd_chain py_compile OK
- 缺陷: 0 新增（BLOCKER=0 MAJOR=0 安全=0 申诉=0）→ 发布门禁通过
- 结论: PASS（只测不改，QA 无代码改动）
```

---

*报告由 game-qa 生成，验证基于合并后 main @ fd85e12 的实机执行（日志 /tmp/qa_post_t983002f6_{cmd,notify,ws}.log）。*
