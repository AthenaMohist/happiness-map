# P0-03 备份/DR 机制 Roundtable — 架构裁定

> 角色：高见远（架构师）
> 日期：2026-07-08
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0
> 测试报告：`docs/qa-reaudits/P0-03-test-report.md`（391 行）
> 代码审查：`hermes_backup_push.sh`（379 行）+ `hermes_daily_backup.sh`（54 行）+ `manifest.yaml`（84 行）
> 产品裁定：许清楚已同意 F1a BLOCKER→MAJOR（DR演练证明 workaround 存在），要求保持 OPEN 直到季度 DR 演练 + RPO/RTO 监控建立

---

## 裁定总览

| # | 审查项 | 裁定 | 置信度 |
|---|--------|:---:|:---:|
| 1 | F1a 降级：DR 恢复链路有效性 | ✅ 确认降级，附 3 项架构前置条件 | 高 |
| 2 | F2 state.db split/reassemble 可靠性 | ✅ 机制可靠，但缺 chunk 完整性校验 | 高 |
| 3 | DR 恢复链路架构完整性 | ⚠️ 链路完整，2 处残余风险 + 1 处缺失确认 | 中高 |
| 4 | F6 备份失败告警优先级 | 🔴 **P0 基础设施依赖**，优先级高于其他 MAJOR | 高 |

---

## 裁定 1：F1a BLOCKER→MAJOR 降级确认

### 1.1 判定对照

```
§1.2 判定公式：
  用户可感知？→ 是（无法恢复 = 备份系统核心功能失效）
  功能阻断？→ 是
  workaround？→ 是（DR演练已证明恢复链路可行）
→ MAJOR（满足「用户可感知 + 功能阻断 + 有 workaround」）
```

### 1.2 代码审查确认

备份链路经代码审查，确认以下数据流完整：

```
hermes_daily_backup.sh (cron 入口)
  └─→ hermes_backup_push.sh
        ├── Step 1: 解析 manifest.yaml → SANDBOX_PATHS[]
        ├── Step 2: sha256sum 计算（每个 sandbox_file）
        ├── Step 3: git clone/pull 备份 repo
        ├── Step 4: rsync ~/.hermes/ → repo/config/（--delete，排除 .git/state.db-wal/state.db-shm/cache/logs/venv/）
        ├── Step 4.5: state.db > 49MB → split -b 49M + VACUUM + .gitignore
        ├── Step 5: cp sandbox_files → repo/scripts/（--dereference symlinks）
        ├── Step 6: cp manifest.yaml → repo/
        ├── Step 7: 更新 manifest（last_scan + sha256 annotations）
        └── Step 8: git diff → commit → push（或 skip if no changes）
```

**架构判定**：备份链路设计合理，代码实现与设计一致。

1. **rsync 排除列表**（L167-176）覆盖了所有运行时临时文件、缓存、虚拟环境、二进制依赖——不会将不可恢复的垃圾数据污染备份。
2. **state.db split**（L182-258）在 rsync 之后对备份 repo 中的副本执行，不修改源文件——写入隔离正确。
3. **sandbox file 复制**（L264-298）使用 `cp --dereference` 处理 symlink——避免备份指向失效目标的链接。
4. **manifest 解析**（L91-105）使用 awk 提取 `sandbox_files:` section——解析可靠，无 YAML 库依赖。
5. **git push 失败处理**（L368-371）：die() 退出，本地 commit 保留——数据不丢失。

### 1.3 架构前置条件（降级生效必须满足）

F1a 降级为 MAJOR **不是无条件的**。以下 3 项必须在下一版本窗口内建立，否则 F1a 恢复为 BLOCKER：

| # | 前置条件 | 理由 | 验收标准 |
|---|---------|------|---------|
| P1 | **季度 DR 演练制度化** | 一次演练只证明「这次能恢复」。DR 恢复链路的持续有效性需要定期验证。 | `docs/dr-drills/` 目录下有至少一次演练报告；cron 触发或手动执行记录可追溯 |
| P2 | **RPO/RTO 监控上线** | 当前 RPO=24h 目标、RTO=~30s 基线仅记录在测试报告中，无人持续监控。RPO 漂移（如备份两天未执行）无人感知。 | 每 24h 检查 `manifest.yaml` 中的 `last_scan` 时间戳，偏差 > 36h 触发告警 |
| P3 | **恢复文档可发现性** | `hermes-backup-restore` skill 在备份 repo 中存在（P0-03 测试报告 §2.2 确认），但无法通过 `skill_view` 在本环境加载——文档可发现性是灾难时能否快速恢复的关键。 | `skill_view("hermes-backup-restore")` 可正常返回 SKILL.md；或提供等效的备选获取路径 |

---

## 裁定 2：F2 state.db split/reassemble 可靠性

### 2.1 代码审查

split 逻辑（`hermes_backup_push.sh` L182-258）：

```
流程：
  1. find $REPO_DIR/config -name "state.db" -type f
  2. 对每个 state.db：du -m 检查大小
  3. ≤ 49MB → 跳过（不做 split）
  4. > 49MB → sqlite3 "$db_file" "VACUUM;"（回收空间）
  5. split -b 49M -d "$db_file" "${parts_dir}/part_"
  6. 写入 README.md（含重组命令 cat part_* > ../state.db）
  7. rm -f "$db_file"（删除单体文件）
  8. echo 'state.db' >> 对应目录的 .gitignore
```

### 2.2 可靠性分析

| 检查项 | 结论 | 证据 |
|--------|:---:|------|
| split 工具可靠性 | ✅ | `split -b` 是 GNU coreutils 标准工具，按字节边界精确切割 |
| 重组命令正确性 | ✅ | `cat part_* > ../state.db` — 标准 Shell glob 按字典序拼接，与 split 默认命名 `part_00, part_01, ...` 一致 |
| VACUUM 预处理 | ✅ | 在 split 前 VACUUM，减少碎片空间浪费 |
| .gitignore 正确性 | ✅ | 单体 state.db 被 gitignore 防止误提交 |
| DR 演练实证 | ✅ | orchestrator state.db（260MB, 6 parts → 337 sessions）重组成功 |
| 多 state.db 隔离 | ✅ | find 独立循环处理，无交叉污染 |

### 2.3 架构缺口：chunk 完整性校验

**当前状态**：split 产生的 chunks 没有任何完整性校验。单个 chunk 在 Git 存储/传输/恢复过程中若发生 bit rot 或截断，`cat part_*` 会静默产出损坏的 SQLite 文件，首次异常会在 SQLite 操作时以 `database disk image is malformed` 暴露。

**影响面**：重组后的 state.db 损坏 → session 历史丢失 → C 级数据（按 §4 不加权）。后果符合 MAJOR 定义（数据一致性问题 + 有 workaround：session 历史可重建）。

**建议**（不阻塞 F2 当前 MAJOR 维持）：

```
Split 时增加 SHA256 checksum per chunk：
  split -b 49M -d "$db_file" "${parts_dir}/part_"
  for chunk in "$parts_dir"/part_*; do
      sha256sum "$chunk" | tee -a "$parts_dir/checksums.sha256"
  done

重组时验证：
  cd "$parts_dir" && sha256sum -c checksums.sha256
  cat part_* > ../state.db
```

**裁定**：F2 维持 MAJOR，split/reassemble 机制本身可靠。chunk 完整性校验作为增强项，在下一版本中实现。不影响发版。

---

## 裁定 3：DR 恢复链路架构完整性

### 3.1 完整数据流图

```
                           ┌──────────────────────────┐
                           │   Backup Cron (daily)     │
                           │   supervisor hermes-cron  │
                           └───────────┬──────────────┘
                                       │
                    ┌──────────────────┼──────────────────┐
                    ▼                  ▼                  ▼
           ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
           │ ~/.hermes/   │  │ sandbox_files│  │ state.db (>49M)  │
           │ (rsync)      │  │ (cp)         │  │ (split)          │
           └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘
                  │                 │                    │
                  ▼                 ▼                    ▼
           ┌──────────────────────────────────────────────────┐
           │        SandboxHermesBackup (GitHub)              │
           │  config/ (rsync) + scripts/ (cp) + state.db parts│
           └──────────────────────┬───────────────────────────┘
                                  │
                     DR演练 / 灾难恢复
                                  │
                                  ▼
           ┌──────────────────────────────────────────────────┐
           │  Restore Process (hermes-backup-restore skill)   │
           │  Step 1: git clone backup repo                   │
           │  Step 2: rsync config/ → ~/.hermes/              │
           │  Step 3: 手动保留 credential (auth.json + .env)  │ ◄── F1b
           │  Step 4: cat state.db parts → state.db           │
           │  Step 5: cp scripts/ → /workspace/               │
           │  Step 6: chmod +x scripts（手动）                │ ◄── F4
           │  Step 7: 验证 hermes status / profile list       │
           └──────────────────────────────────────────────────┘
```

### 3.2 完整性逐项审计

| # | 数据资产 | 备份路径 | 恢复路径 | 完整性验证 | 风险评估 |
|---|---------|---------|---------|:---:|------|
| 1 | config.yaml | rsync → config/config.yaml | rsync 还原 | ✅ 存在性检查 | 低 |
| 2 | profiles/ (12) | rsync → config/profiles/ | rsync 还原 | ✅ 计数检查 | 低（rsync --delete 保证一致） |
| 3 | skills/ (20 类别) | rsync → config/skills/ | rsync 还原 | ✅ 存在性检查 | 低 |
| 4 | kanban.db | rsync → config/kanban.db | rsync 还原 | ✅ sqlite3 .tables | 低 |
| 5 | state.db (≤49MB) | rsync → config/state.db | rsync 还原 | ✅ sqlite3 .tables | 低 |
| 6 | state.db (>49MB) | split → config/state.db.parts/ | cat part_* | ✅ sqlite3 SELECT COUNT | **中**（缺 chunk 校验，见裁定 2） |
| 7 | sessions/ | rsync → config/sessions/ | rsync 还原 | ✅ 目录存在 | 低 |
| 8 | memories/ | rsync → config/memories/ | rsync 还原 | ⚠️ 仅存在性检查 | 低（MEMORY.md < 2KB） |
| 9 | sandbox_files (27) | cp → scripts/ | cp 还原 | ✅ SHA256 抽样 10 文件 | 低 |
| 10 | manifest.yaml | cp → manifest.yaml | N/A（参考用） | ✅ | 低 |
| 11| supervisor configs | cp → scripts/usr/local/share/supervisor/ | cp 还原 | ⚠️ 未显式验证 | **中**（见 3.3 风险点 #1） |
| 12 | auth.json / .env | ❌ 有意排除 | 手动保留/恢复 | N/A（by design） | **中**（见 3.3 风险点 #2） |

### 3.3 残余风险

#### 风险点 #1：supervisor 配置恢复未验证

**现状**：6 个 supervisor `.conf` 文件通过 `sandbox_files` 机制备份到 `scripts/usr/local/share/supervisor/`，恢复时复制回原路径。但 DR 演练中未显式测试 `supervisorctl status`（因为沙箱环境 supervisorctl 不可用，见报告 §2.4）。

**影响**：supervisor 是 Dashboard/Keepalive/KeepAwake/Proxy/Cron/WebTerm 6 个关键守护进程的宿主。配置错误 → 所有守护进程无法启动。

**裁定**：NOT a blocking gap — supervisor 配置是静态文本文件，`cp` 复制不会损坏。但在非沙箱恢复环境（如真实 DR 场景）中，必须增加 supervisor 配置语法验证步骤（`supervisorctl reread && supervisorctl update`）。

#### 风险点 #2：credential 恢复的人因风险

**现状**：Restore skill Step 3 要求「Preserve current credentials」。这是有意设计（安全考虑），但依赖操作者：
- 记得保存 auth.json + .env
- 保存到了可恢复的位置
- 灾难发生时找回这些文件

**影响**：credential 丢失 → 所有 API 调用失败（包括飞书通知、模型调用）。

**裁定**：F1b 维持 MAJOR。这不是架构缺陷——credential 排除是安全设计决策，不是 bug。但恢复文档应增加更醒目的前置检查（如 checklist 首项：「确认 auth.json 和 .env 已安全存放在灾难范围之外」）。

#### 缺失确认项：hermes-backup-restore skill 可发现性

P0-03 测试报告 §2.2 确认 skill 存在（167 行），但本环境无法通过 `skill_view` 加载。需确认：
- skill 是否在备份 repo 中正确存储
- skill 在恢复后是否可被 Hermes skill 系统正确索引

**裁定**：架构前置条件 P3（见裁定 1.3）已涵盖此项。

### 3.4 判定

**DR 恢复链路架构完整。** 所有关键数据流已覆盖，恢复流程经端点验证通过。3 处残余风险均为已知、有 workaround、不阻塞发版。2 处（F1b/F4）已作为 MAJOR 记录，1 处（supervisor 验证）作为 DR 演练 checklist 增强项。

---

## 裁定 4：F6 备份失败告警 —— P0 基础设施依赖

### 4.1 当前状态

```
hermes_daily_backup.sh
  └── log() → backup-push.log（本地文件，无人监控）
      ├── 成功：log "Daily backup completed successfully"
      └── 失败：log "ERROR: Daily backup failed (exit code: $?)"
          exit 1 → cron 感知，但无通知
```

### 4.2 为什么 F6 是 P0 基础设施依赖

F6 的特殊性在于它是**元问题**——它不是备份系统本身的问题，而是「我们不知道自己不知道备份已经坏了」。

| 对比维度 | F6 | 其他 MAJOR（F2/F3/F4/F5/F7） |
|---------|:---:|------|
| 失效模式 | **静默失败** | 用户主动操作时发现 |
| 发现延迟 | 可能数天/数周（直到需要恢复时） | 首次恢复时或手动检查时发现 |
| 连锁影响 | 备份链路全部断裂却无人知晓 | 单个问题的局部影响 |
| 恢复难度 | 发现越晚，数据丢失窗口越大 | 有 workaround |

**架构判定**：F6 是备份系统可观测性的基线。没有 F6，所有其他 findings 的修复都无法验证其持续有效性。F6 应作为**基础设施依赖**独立评估，优先级高于其他 MAJOR。

### 4.3 实施路径

F6 的修复可以与 Watchdog 系统（`tasks_watchdog/docs/architecture.md`）共用告警基础设施：

```
方案 A（轻量，推荐）：
  修改 hermes_daily_backup.sh：
    - 成功 → 无通知（安静的备份才是好备份）
    - 失败 → hermes send --profile orchestrator -t feishu:ou_... "🔴 备份失败: {error}"
    - 连续 3 天失败 → 升级告警 "🔴🔴 备份已连续 3 天失败！"

方案 B（监控驱动）：
  新增 watchdog 检查项：
    - 每 6h 检查 manifest.yaml last_scan 时间戳
    - 偏差 > 36h → 告警
    - 偏差 > 72h → 升级告警
```

**推荐**：方案 A + 方案 B 组合。方案 A 覆盖「执行失败」场景，方案 B 覆盖「cron 停止导致未执行」场景（F5 相关）。

### 4.4 裁定

**F6 维持 MAJOR，但标注 `infra_dependency: P0`。** 在发版 checklist 中作为已知限制标注。建议在当前版本窗口内实现方案 A（轻量通知），下一版本实现方案 B（监控驱动）。

---

## 附录 A：发现状态总表（架构裁定后）

| 发现 | 级别 | 架构裁定 | 下一动作 |
|------|:---:|------|------|
| F1a | **MAJOR**（确认降级） | ✅ 降级成立，附 3 项前置条件 | 研发：确认接受降级。架构：监督 P1-P3 实施 |
| F1b | MAJOR | ✅ 确认 by design，非 bug | 文档增强：恢复 skill checklist 首项增加 credential 检查 |
| F2 | MAJOR | ✅ 机制可靠，缺 chunk 校验 | 增强：split 时写入 checksums.sha256 + 重组时验证 |
| F3 | MAJOR | ✅ 维持（SHA256 抽样通过，但无自动文件计数） | 增强：备份后自动文件计数对比 |
| F4 | MAJOR | ✅ 维持（手动 chmod，已文档化） | 增强：restore skill Step 7 增加权限检查 |
| F5 | MAJOR | ✅ 维持（supervisor 单点依赖） | 增强：方案 B（监控 last_scan 时间戳）可覆盖 F5 的失效检测 |
| F6 | **MAJOR（标注 infra_dependency: P0）** | 🔴 基础设施优先级最高 | 当前窗口：方案 A（轻量通知）。下版本：方案 B（监控） |
| F7 | MAJOR | ✅ 维持（token 过期无预检） | 增强：token 有效性预检（curl GitHub API） |
| F1c | MINOR | ✅ 维持 | 季度 DR 演练制度化（裁定 1.3 P1） |
| F1d | SUGGESTION | ✅ 维持 | 复用 P0-03 测试报告 §6 的复盘模板 |
| F-NEW-1 | MINOR | ✅ 确认（HERMES_DIR env var 无效） | 修复：L66 优先级改为 `HERMES_DIR > /root/.hermes > HERMES_HOME` |

---

## 附录 B：发版门禁影响

按标准 §10：

```
BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉
```

| 检查项 | 状态 |
|--------|:---:|
| BLOCKER=0？ | ✅（F1a 架构确认降级） |
| MAJOR≤3？ | ❌ **7 个 MAJOR，超过 N=3 阈值** |
| 安全漏洞=0？ | ✅ |
| 无未裁定申诉？ | ✅ |

**⚠️ MAJOR 数量 7 > 3 阈值。不能按标准 §10 直接发版。** 需要产品决策：接受 MAJOR 标注 known issue 发版，或暂缓发版等待 MAJOR 修复。

如果走「标 known issue 发版」路径，建议 known issue 列表按优先级排列：

1. F6（备份失败无告警）— `infra_dependency: P0`
2. F1a 前置条件 P1-P3（季度 DR 演练 + RPO/RTO 监控 + 恢复文档可发现性）
3. F2 缺 chunk 校验
4. F3 缺自动文件计数
5. F4 权限手动设置
6. F5 supervisor 单点依赖
7. F7 token 过期无预检

---

## 附录 C：代码审查发现汇总

### C1 确认的设计优点

| # | 发现 | 位置 |
|---|------|------|
| 1 | 备份链路的 `set -euo pipefail` 确保任何步骤失败不会静默继续 | `hermes_backup_push.sh:21` |
| 2 | `rsync --delete` 保证备份 repo 与源目录完全一致（避免累积僵尸文件） | L167 |
| 3 | state.db split 前 `VACUUM` 回收空间 | L200-204 |
| 4 | `cp --dereference` 正确处理 symlink | L283 |
| 5 | git push 使用 `PIPESTATUS` 检查上游管道真实退出码 | L368 |
| 6 | token 通过 `_filter_token` 从所有输出中过滤 | L48-50 |

### C2 改进建议（不阻塞发版）

| # | 建议 | 位置 | 人天 |
|---|------|------|:---:|
| 1 | state.db split 后生成 `checksums.sha256` 文件 | L212-214 之后 | 0.2 |
| 2 | 备份后增加文件计数对比（`find | wc -l`） | L177 之后 | 0.1 |
| 3 | 修复 HERMES_DIR env var 优先级 | L66-72 | 0.1 |
| 4 | 增加 `curl` 预检 GitHub token 有效性 | L56-58 之后 | 0.1 |
| 5 | 备份失败时调用 `hermes send` 发送飞书通知 | L368-371 附近 | 0.3 |

> 总计：0.8 人天。

---

> 架构裁定完成。移交下一位 Roundtable 参与者确认。
