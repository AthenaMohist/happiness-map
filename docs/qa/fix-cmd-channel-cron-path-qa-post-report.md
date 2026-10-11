# FIX cmd_channel cron PATH 缺陷 — QA-POST 合并后验证报告

> 版本：v1.0 | 日期：2026-08-13 | 作者：game-qa（QA-POST 合并后独立验证）
>
> 任务卡：t_f74e1c22 [DEV-QA-POST] FIX cmd_channel cron PATH 缺陷 — hermes 找不到导致建卡失败
> 被测状态：**合并后** devPPL main @ `bd9c07a`（merge commit，由 merge 卡 t_811b7330 手动接管完成）
> 被测内容：PATH 修复链三条 merge 后的 main — S1 lib_hermes_path.sh 自举（af278a8/t_d2db3d1f）+ S2 拆卡保障同步（6a811de/t_a0d89a1c）+ S3 回滚重试+直连回执（bd9c07a/t_5e77837d）+ claim-feishu LIKE 修复（2c018ea）
> 分级标准：`docs/standards/qa-finding-classification.md` v1.0（判定公式/SLA/分级示例对照见 §6）
> 纪律：**只测不改**，QA 无任何代码改动

---

## 0. 执行摘要

| 项 | 结果 |
|---|---|
| **合并完整性** | ✅ S1/S2/S3/claim-feishu 全为 main 祖先（9c3d4c6/494561b/d85ed3d/2c018ea → YES×4），HEAD=bd9c07a，工作树干净 |
| 全量测试 `scripts/test_cmd_channel.sh`（合并后） | ✅ **269 PASS / 0 FAIL**（含 T36-T39/AC-10/T54-T55 本 FIX 新增 + T42-T50 拆卡保障 + T40-T41/T52-T53 编号接线） |
| 基线回归 `scripts/test_workspace_check.sh`（存量） | ✅ **40 PASS / 0 FAIL** |
| 基线回归 `scripts/test_notify_check.py` | ✅ **259 PASS / 0 FAIL**（含合并前 2021609/0be0d45 新增 heartbeat 卡链测试，较 D1 时 226 增 33 断言，全绿） |
| 基线回归 `tests/slice2_smoke.py` | ✅ **ALL SMOKE TESTS PASSED**（需 PYTHONPATH=repo-root，脚本自身仅插 tests/ 目录） |
| QA 独立探针 P1（hermes_cli.py） | ✅ **14/14 PASS**（main 上重跑） |
| QA 独立探针 P2（lib_hermes_path.sh） | ✅ **8/8 PASS**（main 上重跑） |
| 语法检查 | ✅ bash -n × 4（cmd_channel/autopilot/lib_hermes_path/test_cmd_channel）+ py_compile × 5（hermes_cli/cmd_chain/discover/state/send_claim_feishu）全过 |
| 静态核对（S1-S7 复查） | ✅ 0 裸 hermes 残留；stderr 吞点仅剩 mktemp 兜底；双挂载就位；五调用点替换就位；LIKE 修复就位 |
| 撞号残留 | ✅ T36-T39/T42-T50/T54-T55 section 唯一，无重复定义 |
| 真实 board 核对 | ✅ 无活跃 [CMD] 卡；8 张历史失败卡全 archived（与 arch §9.3/D1 QA-D1-03 一致） |
| 新增缺陷（POST 阶段） | **0 新增** — 合并未引入回归 |
| 发布门禁（§10） | BLOCKER=0、MAJOR=0、安全=0、未裁定申诉=0 → **通过** |

**结论：PASS。** 合并后的 main 与 D1/EXEC/VA 验证的 fix 分支状态一致——全量 269 + 基线 40/259 + smoke + 22 条 QA 独立探针全部通过；merge 冲突解决（discover.py 保留 subprocess/sys、test 保留 T42-T50/T36-T39/T54-T55、state.py 合入 produces 校验）无丢失、无回归；0 新增缺陷，发布门禁通过。

---

## 1. 合并完整性检查

| 检查项 | 命令 | 结果 |
|---|---|---|
| 主分支 tip | `git log --oneline -3 main` | ✅ `bd9c07a merge: PATH 修复 S3 …` 为 HEAD |
| S1 lib_hermes_path 自举在 main | `git merge-base --is-ancestor 9c3d4c6 main` | ✅ YES |
| S2 拆卡保障同步在 main | `git merge-base --is-ancestor 494561b main` | ✅ YES |
| S3 回滚重试+直连回执在 main | `git merge-base --is-ancestor d85ed3d main` | ✅ YES |
| claim-feishu LIKE 修复在 main | `git merge-base --is-ancestor 2c018ea main` | ✅ YES |
| 工作树状态 | `git status --short` | ✅ 干净 |

`git log --oneline -3 main` 实测：
```
bd9c07a merge: PATH 修复 S3 — 回滚重试+直连回执 (t_5e77837d)，测试冲突解决（保留 T36-T39 最终版 + T54-T55 新测试）
6a811de merge: PATH 修复 S2 — 测试冲突解决（保留 T42-T50 拆卡保障 + T36-T39/AC-10 PATH 测试） (t_a0d89a1c)
af278a8 merge: PATH 修复 S1 — lib_hermes_path.sh 自举 + discover.py 冲突解决(保留 subprocess/sys import) (t_d2db3d1f)
```

merge commit 拓扑确认：`af278a8` parents=(2021609, 9c3d4c6)；`6a811de` parents=(af278a8, 494561b)；`bd9c07a` parents=(6a811de, 2c018ea) — 逐张顺序合并，无跳过。

## 2. 合并后全量测试

测试在 main @ bd9c07a（本 worktree HEAD == main）独立执行，隔离 TMPT/锁（`/tmp/cmdchan-test-t_f74e1c22`），无并行干扰。

### 2.1 `bash scripts/test_cmd_channel.sh`

| 项 | 实测 |
|---|---|
| 结果 | **PASS=269 FAIL=0** — ALL TESTS PASSED（EXIT=0） |
| 覆盖 | 存量 T1-T35（roundtable/链补全/智能跳步/评估拆卡/discover 拦截）+ T36-T39/AC-10（最小 PATH 建卡/roundtable/hermes_bin 优先级/不可达回执/同 tick 双卡）+ T42-T50（拆卡保障）+ T40-T41/T52-T53（编号接线）+ T54-T55（回滚重试状态机 3 连败 blocked/重试成功/业务类不回滚 + 直连回执幂等） |
| 尾部抽样 | T54a-f 回滚状态机 ✅（env 失败×2 → ready → 第 3 次 blocked+告警）；T54g-i 重试成功路径 ✅；T54j-l 业务类不回滚 ✅；T55a-d 直连回执+幂等守卫 ✅ |

### 2.2 `bash scripts/test_workspace_check.sh`（存量基线）

| 项 | 实测 |
|---|---|
| 结果 | **PASS=40 FAIL=0** — ALL TESTS PASSED |

### 2.3 `python3 scripts/test_notify_check.py`

| 项 | 实测 |
|---|---|
| 结果 | **259 PASS / 0 FAIL** — EXIT=0 |
| 说明 | D1 时为 226；合并前 main 新增 2021609/0be0d45（heartbeat 卡链 3 链上限取消 + 任务编号前置）在 notify_check 增 33 断言 → 259。全部通过，无回归 |
| 尾部抽样 | T71-x blocked 优先归并 + 全 done 链 ✅ |

### 2.4 `PYTHONPATH=. python3 tests/slice2_smoke.py`

| 项 | 实测 |
|---|---|
| 结果 | **ALL SMOKE TESTS PASSED** |
| 说明 | 脚本自身 `sys.path.insert(0, tests/)`，从仓库根跑需要 PYTHONPATH 含 repo-root（D1/EXEC 同法）。首次裸跑 ModuleNotFoundError 为调用方式问题，非代码缺陷 |

## 3. 关键行为抽查（合并后代码一致性）

| 检查项 | 位置 | 结果 |
|---|---|---|
| lib_hermes_path.sh 存在且为最终版（63 行） | scripts/lib_hermes_path.sh | ✅ |
| autopilot.sh source 挂载 | L41 `source "$SCRIPT_DIR/lib_hermes_path.sh"  # [F-2]` | ✅ |
| cmd_channel.sh 独立自举 | L42 source + L57/58 TMP_ERR/TMP_OUT 捕获式 stderr | ✅ |
| hermes_cli.py hermes_bin/hermes_invoke/HermesCLIError/log_hermes_error | L33/87/110 | ✅ |
| cmd_chain.py 3 处调用点替换 | L381/393/401 hermes_invoke | ✅ |
| discover.py 1 处调用点替换 | L244 hermes_invoke | ✅ |
| discover.py 保留 subprocess/sys import（merge 冲突解决） | L24/25 | ✅ |
| state.py 1 处调用点替换 | L79 hermes_invoke | ✅ |
| state.py produces 内容级校验合入（1a74268） | L167-245 _is_file_like/_file_has_content | ✅ |
| send_claim_feishu.py LIKE 修复 | L131 `LIKE '%[PRODUCES]%'` | ✅ |
| F-8 rollback_retry 状态机 | cmd_channel.sh L105+（[cmd-retry] 计数 <2 回滚 ready / ≥2 blocked+告警） | ✅ |
| F-9 send_comment 直连 sqlite + 幂等守卫 | L74+（同 task_id+body 不重复写） | ✅ |
| 拆卡保障符号（S2 同步） | discover.py _create_dev_sub_cards/_read_sub_split/_topic_from_title/_extract_code（L60-63/836） | ✅ |

## 4. 撞号残留检查

- section 头 grep 确认：T36-T39/AC-10（L1105）、T42-T50（L1202）、T40-T41/T52-T53（L1507）、T54-T55（L1620）各仅 1 处。
- T39b 断言已更新为 F-8 语义（`ready` 回滚而非 `archived`），与 S3 d85ed3d 一致。
- **无重复定义、无撞号残留。**

## 5. 回归风险（语法检查）

| 脚本 | 检查 | 结果 |
|---|---|---|
| scripts/cmd_channel.sh | `bash -n` | ✅ OK |
| scripts/autopilot.sh | `bash -n` | ✅ OK |
| scripts/lib_hermes_path.sh | `bash -n` | ✅ OK |
| scripts/test_cmd_channel.sh | `bash -n` | ✅ OK |
| pipeline/hermes_cli.py | `python3 -m py_compile` | ✅ OK |
| pipeline/cmd_chain.py | `python3 -m py_compile` | ✅ OK |
| pipeline/discover.py | `python3 -m py_compile` | ✅ OK |
| pipeline/state.py | `python3 -m py_compile` | ✅ OK |
| scripts/send_claim_feishu.py | `python3 -m py_compile` | ✅ OK |

## 6. 标准对照（qa-finding-classification.md v1.0）

### 6.1 判定公式对照（§1.2）

POST 阶段发现 0 功能缺陷（合并未引入回归）。D1 既有发现复查：

| 发现 | 用户可感知 | 功能阻断 | workaround | 安全漏洞 | 数据一致性 | 判定 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| QA-D1-01（FIX 未合 main） | —（流程状态） | — | — | 否 | 否 | ✅ **已闭环**（S1/S2/S3 已入 main，本 POST 即验证） |
| QA-D1-02（PRD 文档未上 main） | ✅（下游引用断裂） | ❌ | ✅（查分支 commit） | 否 | 否 | ⚠️ **MINOR 延续** — merge 卡未把 docs/prd/fix-cmd-channel-cron-path-prd.md（0ade9cc）合入 main，任务卡 body 引用路径仍断裂（建议后续文档补齐卡处理） |
| QA-D1-03（历史失败卡处置） | ❌ | ❌ | — | 否 | 否 | ✅ **SUGGESTION 维持** — 真实库核对 8 张全 archived，无活跃 [CMD] 卡 |

### 6.2 SLA 对照（§8/§9）

- 本 POST 无新增 BLOCKER/MAJOR，不触发 SLA 流程。
- QA-D1-02 MINOR 延续：按标准 §8，MINOR 响应时限 2 工作日；建议由 OC/研发在后续文档补齐时处置。
- QA 侧 SLA：验证任务当场完成，报告随卡提交。

### 6.3 分级示例对照（§5）

不适用新增 — 0 新增 finding，无示例可对照。既有 QA-D1-02 MINOR 判定与 D1/EXEC/VA 评审一致（VA t_9cf2a214 VERIFIED 维持）。

### 6.4 发布门禁（§10）

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
[CLAIM] QA-POST 合并后验证 PASS（t_f74e1c22, main @ bd9c07a）
- 合并完整性: 9c3d4c6/494561b/d85ed3d/2c018ea 全为 main ancestor（YES×4），HEAD=bd9c07a，工作树干净；
  merge 拓扑 af278a8(2021609,9c3d4c6) → 6a811de(af278a8,494561b) → bd9c07a(6a811de,2c018ea) 逐张顺序
- 全量测试: test_cmd_channel.sh 269/0 PASS；test_workspace_check.sh 40/0；test_notify_check.py 259/0（较 D1 226 增 33 为合并前 2021609/0be0d45 新增，全绿）；slice2_smoke ALL PASS（PYTHONPATH=repo-root）
- QA 独立探针（main 重跑）: P1 hermes_cli 14/14 + P2 lib_hermes_path 8/8
- 语法: bash -n 4/4 + py_compile 5/5 OK
- 关键符号: hermes_cli L33/87/110；cmd_chain L381/393/401；discover L244 + subprocess/sys import 保留（merge 冲突解决）；
  state L79 + produces 内容级校验合入；send_claim_feishu L131 LIKE；cmd_channel F-8 rollback_retry/F-9 send_comment 幂等守卫
- 撞号: T36-T39/AC-10、T42-T50、T40-T41/T52-T53、T54-T55 section 唯一，无重复
- 真实 board: 无活跃 [CMD] 卡；8 张历史失败卡全 archived（与 arch §9.3 一致）
- 缺陷: 0 新增（BLOCKER=0 MAJOR=0 安全=0 申诉=0）→ 发布门禁通过
- 延续: QA-D1-02 MINOR（PRD 文档 0ade9cc 未入 main，引用路径断裂）→ 建议后续文档补齐卡合入
- 结论: PASS（只测不改，QA 无代码改动）
```
