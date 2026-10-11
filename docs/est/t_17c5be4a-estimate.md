# DPL-218 EST 评估 — 建卡统一入口收口（库口前移 + 谓词同源化 + est 派生防御）

- 评估卡: t_17c5be4a（[DEV-EST]，wt/t_17c5be4a）
- 依据: ARCH v1.0 `arch-dpl218-unified-entry-library-gate.md`（2026-10-07，game-architect）
- 实勘时间: 2026-10-07，只读源码实测（本 worktree 当前 HEAD 64cde8e）
- 模式: 只读实勘 + 本文档，不改任何实现代码

## 1. 实勘锚点核对（对照 ARCH §1.1 表格逐条）

### 1.1 核对结果

| # | ARCH 声称锚点 | 实测 | 结论 |
|---|---|---|---|
| 1 | card_bumps.py:141-146 报错文案（INSERT 触发器 error_msg，无指路） | `error_msg` 实际在 **133-140**；141 是 `escaped = error_msg.replace(...)` | **偏差 -8 行**（行号漂移，现状描述一致：确实无指路） |
| 2 | card_bumps.py:167 `WHEN NEW.status = 'ready'` 只拦 ready | WHEN 实际在 **154**（`_bumps_trigger_sql` 内 f-string 起点 152）；167 是凸点 c 注释行 | **偏差 -13 行**（现状一致：只拦 ready，G1 属实） |
| 3 | card_bumps.py:249-251 谓词碎片（升舱 est 查） | 升舱触发器 est 谓词（`RAISE ... WHERE instr(...)`) 实际在 **231-233**，WHEN 在 **222-228**；249-251 实际落在 `install_card_bumps_update_trigger` 函数体内（conn.execute/commit） | **偏差 -19 行**（碎片化现状属实，行号错位） |
| 4 | card_bumps.py:240-257 升舱触发器（语义正确，拒旧不拒新） | `_bumps_update_trigger_sql` 实际 **199-234**，其 install 函数 **237-256** | **偏差**：ARCH 区段实际横跨触发器尾部+install 函数；语义判断一致（BEFORE UPDATE，OLD.status<>'ready' 守卫自愈通道在位） |
| 5 | card_bumps.py:262 附近 install 函数（CREATE IF NOT EXISTS） | install 函数实际在 **174-193**（INSERT）与 **237-256**（UPDATE）；262 实际是 `CARD_BUMPS_SKIPPED_PREFIX` 常量区 | **偏差**：两个 install 均 `CREATE TRIGGER IF NOT EXISTS`（A7 坑属实，见 :152/:222），但行号需按实测定位 |
| 6 | card_bumps.py:275-293 预检扫描 SQL | `_bumps_precheck_scan_sql` 实际 **275-293** | **精确一致** ✓（扫 `('todo','blocked')`、只查凸点 c、豁免表同源、parents 终态过滤均在位） |
| 7 | card_bumps.py:99-125 白名单守卫/豁免表/SYSTEM_IDEM_PREFIXES | 实际 **74-112**（SYSTEM_IDEM_PREFIXES 76-85 / MECHANIC_TITLE_PREFIXES 89-95 / off 标记 98 / whitelist_guard 147-151） | **偏差 -25 行**（内容完整属实，零放宽前提成立） |
| 8 | discover.py:434-540 est_intercept 触发器 | `_est_trigger_sql` 实际 **437-539** | **基本一致**（±3 行）✓ |
| 9 | discover.py:455-470 WHEN 守卫区域 | sub_prefixes **457-463**、text_expr 466、_est_whitelist_guard **470-476** | **基本一致**（守卫段略后移至 470-476）✓ |
| 10 | discover.py:505 `'t_est_' \|\| substr(NEW.id, 3)` 无形态防御 | 实测 **505 精确命中** | **精确一致** ✓（无 GLOB/length 校验，R4.1 缺口属实） |
| 11 | autopilot.sh:179-186 install 调用链 | if 守卫 179，三个 install 调用 **180-187**，precheck 插桩 192-197，fi 198 | **一致** ✓（card_bumps.off 守卫在调用外侧，D7 零改动结论成立） |

### 1.2 偏差汇总

- **行号系统性前移**（card_bumps.py 内 -8~-25 行）：ARCH 行号基于略早的源码版本，实现时**必须以本表实测行号重新定位**，不得盲抄 ARCH §1.1。
- **内容/现状判断零偏差**：全部 7 个结构性事实（G1 只拦 ready、A7 IF NOT EXISTS no-op 坑、三处谓词碎片化、预检只查凸点 c、est 派生无防御、豁免体系完整、autopilot 调用链）与 ARCH 描述完全一致。**设计有效性不受行号漂移影响**。

### 1.3 测试基建核对（偏差，实现者必读）

- **ARCH §4 称「复用 DPL-145 测试基建（tmp_path 建库 + install 函数 + 裸 INSERT）」——实测不成立**：
  - DPL-145 的 F1 触发器测试不在 tests/ pytest，而在 **scripts/test_card_bumps.sh**（shell + assert_contains 断言 `card-bumps-missing`）。
  - DPL-198 测试同为 shell：scripts/test_dpl198_bumps_upgrade.sh、scripts/test_dpl198_bumps_precheck.sh。
  - tests/test_dpl145_f3_f5.py、test_dpl145_f6_branch_merge.py 为纯函数/mock 测试，无建库+install+裸 INSERT 模式。
- **可复用的 pytest 先例是 tests/test_dpl209_s2_wiring.py**（tmp_path 建库 + `install_oc_write_guard_triggers(str(path))` + sqlite_master 断言），新测试文件应以此为骨架模板，触发器断言语义参考 scripts/test_card_bumps.sh。
- **tests/test_dpl218_bumps_library_gate.py 确认不存在**（Glob 全 tests/ 无命中）——需新建，ARCH 交付清单无误。
- 影响评估：基建移植成本小（一个 conftest 风格的 `_mk_db(tmp_path)` helper），但 ARCH「直接复用」表述需修正为「从 DPL-209 移植模式」。

## 2. 工作量评估（轮次）

### 2.1 实现轮次拆解

| 阶段 | 内容 | 基准轮次 |
|---|---|---|
| card_bumps D1/D2/D3/D7 | `_ACTIVE_STATUS_SQL`/`_EST_LINE_SQL` 常量 + 三处引用 + 文案追加 + DROP+CREATE ×2（~40 行净变更） | 3-4 |
| discover D4/D5 | est GLOB+length 守卫（RAISE(IGNORE)）+ 告警指路句（~8 行） | 1 |
| 新测试文件 | tests/test_dpl218_bumps_library_gate.py 全表 9 用例组（§4：毒卡×4 / 良卡 / 豁免全绿 / est 卡不误伤 / 谓词同源 / 预检三查 / est 防御 / DROP+CREATE 部署 / 含建库 helper 移植） | 3-4 |
| qa_probes 回放 | qa_probes/qa_exec_dpl218.md（t_24ca2fd3 形态红→绿基线 + oc_create_card dry-run） | 1-2 |
| autopilot 实测确认 | 安装链打印新 status 面（零改动，仅验证） | 0.5（并入上项） |
| **实现小计** | | **8-11（取 9）** |

### 2.2 回归测试轮次（实测折算）

- 实测 `pytest tests/test_dpl145_f6_branch_merge.py tests/test_dpl145_f3_f5.py -q`：**14 passed, 0.61s**。
- 新增 test_dpl218 文件预估 1-3s（tmp_path 建库 ×9 组，参考 DPL-209 耗时量级）。
- 墙钟成本可忽略，回归主要消耗对话轮（跑批+解读）：**折算 1-2 轮**（含一次失败重跑缓冲）。

### 2.3 收尾链

- 固定 **+8 轮**（[PRODUCES] comment、merge/close 链、wiki 经验沉淀等既定收尾，与 DPL-217/DPL-198 先例同口径）。

### 2.4 基准汇总

基准 = 9（实现）+ 1.5（回归）+ 8（收尾）≈ **18.5 轮**

## 3. 历史偏差校准（K=2.32）

- 口径: 最终估算 = 基准 × K = 18.5 × 2.32 ≈ **43 轮**
- 区间（±10%）: **39-47 轮**
- 主要超支源（K 的由来项）: ① A7 DROP+CREATE 在真实库的部署验证（毒卡回放依赖临时库副本构造）；② 豁免回归面广（SYSTEM_IDEM_PREFIXES × MECHANIC_TITLE_PREFIXES × 白名单缺失 fail-open 三维组合）；③ 谓词同源断言对 f-string 展开文本的精确匹配易在实现细节上返工。

## 4. 复杂度 / 风险点

| # | 风险 | 评级 | 说明/缓解 |
|---|---|:---:|---|
| R1 | **A7 DROP+CREATE 坑本体**：`CREATE TRIGGER IF NOT EXISTS` 对已装旧版（ready 面）触发器是 no-op，不 DROP 则 R1 扩面永不生效 | 高（本卡核心） | 两个 install 均升级 DROP+CREATE（实测行号 174-193 / 237-256）；毫秒级窗口 + autopilot 每 tick 重装自愈；测试用例「先装旧版 SQL 再 install → sqlite_master 含 'todo'」必须覆盖 |
| R2 | **豁免回归面**：R1 扩到 todo/running/blocked 后，机制自建卡（est 评估卡/discover-*/cmd-*/dev-*/rt-* 幂等前缀、dev:%/qa-d1:% 等标题）若豁免口径错一格即自锁管线 | 中-高 | est 评估卡双豁免（[DEV-EST] 标题 + discover-est- 幂等前缀）实测在位（card_bumps.py:76-95）；测试表「豁免全绿」+「est 卡不误伤」两组全覆盖 |
| R3 | **谓词同源断言脆弱**：`_EST_LINE_SQL.format(e=...)` 展开文本在三处 SQL 中的字面匹配对空格/引号敏感 | 中 | 断言写「含常量 f-string 展开子串」而非整串相等；A4 断言失败即 CI 红，正是设计意图 |
| R4 | 预检增查凸点 a/b 后隔离面扩大（sticky blocked 更多卡） | 低 | 24h 幂等告警已有（card_bumps.py:264）；补行自愈通道在位 |
| R5 | 行号漂移（本次实勘 §1.2）导致实现挂错位置 | 低 | 以本文件 §1.1 实测行号为准 |
| R6 | 测试基建与 ARCH 表述不符（§1.3） | 低 | 按 test_dpl209_s2_wiring.py 模式移植 |

## 5. 拆卡结论

**[SUB-SPLIT] 1 — 维持 ARCH 的 [SINGLE] 单卡（est_rounds=4）**：

- 改动面高度耦合于两个文件的同一段谓词区（D1/D3/D7 触碰同一批函数），拆分必然产生跨卡冲突与重复建库 fixture，通信成本 > 收益。
- 工作量主体是新测试文件（基准 3-4 轮），可独立但不宜独立（断言对象是 D1/D3 的常量，同卡写最省）。
- 按 K 校准口径 43 轮超出典型拆卡阈值，但该口径含收尾链与历史超支噪声；实现本体（~48 行净变更 + 1 测试文件）符合单卡粒度，回归风险由 §4 测试表 + qa_probes 回放兜底。

## 6. 验收门禁提醒（实现卡照抄）

```
pytest tests/test_dpl218_bumps_library_gate.py tests/test_dpl145*.py -q
bash scripts/test_card_bumps.sh   # F1 旧断言不得回退
```
