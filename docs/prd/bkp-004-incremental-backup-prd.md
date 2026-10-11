# BKP-004 PRD — 增量切片备份方案：替代全量切片

> 作者：许清楚（产品负责人） | 日期：2026-08-14 | 版本：v1.0
> 来源：[CMD] 指令卡通道（Frank 2026-08-11 裁定 2 类型化建链）
> 议题：增量切片备份方案 — 替代全量切片（BKP-004）
> 存档要求: 对话接近 50 轮时按「轮次存档铁律」执行 [CHECKPOINT] 存档（见 SOUL）

---

## 0. 本 PRD 在整体规划中的定位

```
BKP-001（已定未落地）  — Git LFS 管理大文件（state.db parts）
BKP-002（已定）        — 备份脚本权限/完整性校验（F2/F3/F4）
BKP-003（已落地）      — wiki/mem-core 等项目接入 manifest.yaml 备份链路
BKP-004（本 PRD）      — 增量切片替代全量切片：解决 .git 无限膨胀
```

**一句话定位**：当前 `hermes_backup_push.sh` 每次运行都把所有 state.db 重新 split 成 49MB 分块并 commit 到 git。state.db 是 SQLite 单体文件，任何行变更都导致整个文件变化 → 每次备份都产生全套新 blob。151 次提交已积累 **16GB .git（其中 13.1GB 是 state.db parts）**，repo 总量 18GB。不解决，2 周内 repo 将超过 25GB，clone/push 耗时从分钟级恶化到不可用。

---

## 1. 背景与痛点

### 1.1 现状：全量切片备份机制

`hermes_backup_push.sh` 的备份流程（Step 4 + Step 4.5）：

```
Step 4:   rsync ~/.hermes/ → repo/config/    （全量镜像，--delete）
Step 4.5: 对 repo/config/ 中每个 state.db:
            IF size > 49MB:
              VACUUM → split -b 49M → part_00..part_NN
              为每个 part 生成 sha256
              删除单体 state.db（.gitignore）
            ELSE:
              直接提交单体 state.db
Step 4.7: rsync backup_roots → repo/workspace/（devPPL/dream/verification 等）
Step 8:   git add -A → diff → commit → push
```

**核心问题**：state.db 是 SQLite 单体二进制文件。即使用 WAL 模式，一次 `INSERT` 或 `UPDATE` 只改了几行，整个文件的字节布局也会变化 → sha256 完全不同 → git 无法做 delta 压缩（二进制文件不可 diff）→ **每次备份都是全量重传**。

### 1.2 数据证据：膨胀规模

实测（2026-08-14）：

| 指标 | 数值 |
|------|------|
| 备份 repo 总大小 | **18 GB** |
| 其中 .git 目录 | **16 GB** |
| 其中工作树（config/ + workspace/） | ~2.5 GB |
| state.db parts 占 .git 的比例 | **13.1 GB / 16 GB = 82%** |
| state.db parts 对象数 | 1,223 个版本，分布在 36 个唯一路径 |
| 提交总数 | 151 次 |
| 最近 7 天提交数 | 128 次（日均 ~18 次） |
| 最近 7 天日均新增 .git 体积 | ~1.5-2 GB/天 |

**增长趋势**：

| 日期 | 提交数 | 说明 |
|------|:------:|------|
| 2026-08-11 | 46 | 管线密集期（多任务并行） |
| 2026-08-12 | 21 | |
| 2026-08-13 | 29 | |
| 2026-08-14 | 16 | 截至中午 |

**触发频率**：
- cron 定时：北京时间 4:00 / 13:00 / 18:30（每日 3 次）
- 管线触发：merge-1（合并前）、merge-4（合并后）、close-4（闭环）— 每个任务 3 次
- 实际：密集开发期每日 20-40 次 commit

### 1.3 痛点总结

| # | 痛点 | 影响 | 严重度 |
|---|------|------|:------:|
| P1 | **.git 无限膨胀** | clone 从秒级→分钟级→超时；push 耗时线性增长；磁盘空间耗尽 | 🔴 BLOCKER |
| P2 | **无 delta 压缩** | state.db 是二进制，git 无法 diff → 每次全量 blob | 🔴 根因 |
| P3 | **BKP-001 LFS 未落地** | .gitattributes 为空，LFS 从未配置 | 🟡 已知债 |
| P4 | **备份频率过高** | cron 3次/日 + 管线触发 = 20-40次/日，每次都全量 | 🟡 加速器 |
| P5 | **恢复成本递增** | clone 18GB → 需要 10+ 分钟，灾难恢复时不可接受 | 🔴 BLOCKER |

---

## 2. 方案：增量切片备份

### 2.1 核心思路

**不再每次全量提交 state.db 的 split parts，改为只提交「自上次备份以来变化的部分」。**

具体策略（三选一，见 §2.3 决策）：

```
策略 A: SQLite 增量导出（dump diff）
  ─ 上次备份时记录 state.db 的 schema_version + row_count
  ─ 本次备份时导出新增/变更的行 → incremental.sql
  ─ 定期（每周）做一次全量 baseline

策略 B: state.db 内容级去重（保留 split，但 git 层去重）
  ─ 每次 split 后，对每个 part 计算 sha256
  ─ 如果 part 的 sha256 与上次相同 → 跳过（git add 不变）
  ─ 只有变化的 part 才产生新 blob
  ─ 但二进制 part 内部字节仍全变 → 去重率低

策略 C: 压缩 + LFS + 频率治理（推荐）
  ─ state.db split 后 gzip 压缩 → part_XX.gz
  ─ .gitattributes 配置 LFS 跟踪 *.gz / state.db.parts/*
  ─ cron 频率从 3次/日 降到 1次/日（凌晨全量）
  ─ 管线触发的备份改为「标记 dirty + 延迟到下一次 cron」
```

### 2.2 方案对比

| 维度 | 策略 A (dump diff) | 策略 B (part 去重) | 策略 C (压缩+LFS+频率) |
|------|:---:|:---:|:---:|
| 压缩率 | ⭐⭐⭐⭐ 最高（只存 SQL diff） | ⭐ 最低（二进制不变） | ⭐⭐⭐ 中等（gzip ~40-60%） |
| 实现复杂度 | 🔴 高（需 SQLite diff 逻辑） | 🟢 低（sha256 比对） | 🟡 中（LFS 配置 + 频率改） |
| 恢复复杂度 | 🔴 高（baseline + N 个增量） | 🟢 低（cat parts） | 🟡 中（LFS smudge + gunzip） |
| 可靠性 | 🟡 中（增量链断裂=全丢） | 🟢 高（每份完整） | 🟢 高（每份完整） |
| 解决根因 | ✅ 是 | ❌ 否（part 仍全变） | ✅ 部分（LFS 移出 .git） |
| 落地速度 | 3-5 天 | 0.5 天 | 1 天 |

### 2.3 产品决策：策略 C（压缩 + LFS + 频率治理）

**理由**：

1. **用户影响优先**：Frank 需要的是「备份不爆 + 恢复可靠」，不是技术优雅。策略 C 在 1 天内可落地，立即止血。
2. **可靠性不可妥协**：策略 A 的增量链一旦中间丢失一个 commit，后续全部不可恢复。备份系统的核心价值是「任何时候都能恢复」，不能为了省空间牺牲可靠性。
3. **LFS 是 BKP-001 已定方向**：只是没落地。本 PRD 顺便完成 BKP-001 的落地。
4. **频率治理是免费收益**：当前 cron 3次/日 + 管线触发 = 20-40次/日，而 state.db 的有效变更窗口远小于此。降到 1次/日 全量 + 管线触发标记 dirty，立即减少 80% 的提交。

**策略 C 的三重减量效果**：

```
当前:    20-40 次/日 × 全量 split（~600MB state.db parts/次）= 12-24 GB/日 增长
策略 C:  1 次/日 × gzip 压缩（~250MB）+ LFS（不占 .git） = ~0.25 GB/日 .git 增长
减量比:  ~50-100x
```

### 2.4 频率治理方案

当前备份触发源：

| 触发源 | 频率 | 处理 |
|--------|------|------|
| cron 4:00 (UTC 20:00) | 1次/日 | ✅ 保留 — 改为全量备份主窗口 |
| cron 13:00 (UTC 5:00) | 1次/日 | ❌ 移除 — 降为 dirty 标记 |
| cron 18:30 (UTC 10:30) | 1次/日 | ❌ 移除 — 降为 dirty 标记 |
| merge-1（管线触发） | 每任务 1次 | ⚠️ 保留但改为异步标记 |
| merge-4（管线触发） | 每任务 1次 | ⚠️ 保留但改为异步标记 |
| close-4（管线触发） | 每任务 1次 | ⚠️ 保留但改为异步标记 |

**管线触发的处理**：

```
当前:  merge-1 → 直接调 hermes_backup_push.sh → 全量 commit + push
改后:  merge-1 → 写 dirty 标记到 /workspace/.backup_dirty
       cron 4:00 → 检查 dirty 标记 → 如果有 → 执行全量备份
       (确保 RPO ≤ 24h，merge 后最迟次日 4:00 备份)
```

**RPO 分析**：

| 场景 | 当前 RPO | 策略 C RPO | 可接受？ |
|------|:------:|:------:|:------:|
| 常规 | ~8h（3次/日） | ~24h（1次/日） | ✅（原定 RPO=24h） |
| merge 后崩溃 | ~0h（立即备份） | ≤24h（次日 cron） | ⚠️ 需确认 |
| close 后崩溃 | ~0h（立即备份） | ≤24h | ⚠️ 需确认 |

**对 merge/close 后崩溃的补充保护**：保留 merge-4 / close-4 的同步备份，但使用压缩 + LFS（不再全量裸 commit）。merge-1 改为异步标记（merge 前的数据已在 git 分支里，不需要备份保护）。

---

## 3. 详细设计

### 3.1 修改清单

| # | 文件 | 改动 | 改动量 |
|---|------|------|:------:|
| 1 | `/workspace/hermes_backup_push.sh` Step 4.5 | split 后增加 gzip 压缩 | +15 行 |
| 2 | `/workspace/hermes_backup_push.sh` Step 4.5 | sha256 改为对 .gz 文件计算 | +5 行 |
| 3 | `/workspace/hermes_backup_push.sh` Step 4.5 | README 重组指令加 gunzip | +5 行 |
| 4 | `/workspace/SandboxHermesBackup/.gitattributes` | 新建，配置 LFS 跟踪规则 | +10 行 |
| 5 | crontab | 13:00 / 18:30 条目移除或改为 dirty 标记 | 2 行删除 |
| 6 | `/workspace/hermes_backup_push.sh` 新增 dirty 标记逻辑 | 管线触发时写标记而非直接 push | +20 行 |
| 7 | `/workspace/hermes_backup_push.sh` cron 入口 | 检查 dirty 标记决定是否执行 | +10 行 |
| 8 | `hermes_backup_restore.sh`（如存在） | 恢复时 gunzip + LFS smudge | +10 行 |

### 3.2 gzip 压缩设计

```bash
# Step 4.5 修改后:
# state.db > 49MB 时:
#   1. VACUUM
#   2. split -b 49M → part_00..part_NN
#   3. gzip 每个 part → part_00.gz..part_NN.gz    ← NEW
#   4. 删除未压缩的 part_00..part_NN               ← NEW
#   5. sha256 对 .gz 文件计算
#   6. README 更新重组指令: gunzip + cat

# 效果:
#   state.db 600MB → split 13 parts × 49MB → gzip 13 parts × ~20MB = ~260MB
#   压缩率 ~43%（SQLite 内部有大量重复结构和空闲页）
```

### 3.3 LFS 配置

```bash
# /workspace/SandboxHermesBackup/.gitattributes (新建)
config/profiles/*/state.db.parts/*.gz filter=lfs diff=lfs merge=lfs -text
config/profiles/*/state.db filter=lfs diff=lfs merge=lfs -text
config/state.db filter=lfs diff=lfs merge=lfs -text
config/state-snapshots/**/state.db filter=lfs diff=lfs merge=lfs -text

# LFS 初始化（一次性）:
cd /workspace/SandboxHermesBackup
git lfs install
git lfs track "config/profiles/*/state.db.parts/*.gz"
git lfs track "config/profiles/*/state.db"
git lfs track "config/state.db"
git add .gitattributes
git commit -m "feat(BKP-001/004): enable Git LFS for state.db files"
```

**LFS 效果**：
- state.db 文件不再存入 .git pack，而是存入 LFS 对象存储（GitHub LFS server）
- .git 只存 sha256 指针（~130 字节/文件）
- clone 时默认不下载 LFS 对象（`GIT_LFS_SKIP_SMUDGE=1`），需要时按需拉取
- 恢复时 `git lfs pull` 拉取所需文件

### 3.4 dirty 标记机制

```bash
# 管线触发备份（merge-1 / merge-4 / close-4）时:
# 不再直接执行全量 push，而是:
mark_backup_dirty() {
    local source="$1"  # merge-1 / merge-4 / close-4
    local task_id="$2"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ${source} ${task_id}" >> /workspace/.backup_dirty
    log "Backup marked dirty by ${source} (${task_id}) — will be picked up by next cron run"
}

# cron 4:00 入口:
if [[ -f /workspace/.backup_dirty ]]; then
    log "Dirty marker found — executing full backup"
    # 执行全量备份
    # 成功后删除 dirty 标记
    rm -f /workspace/.backup_dirty
fi
```

**例外**：merge-4 和 close-4 保留同步备份（使用压缩+LFS），因为 merge/close 是不可逆操作，崩溃后数据无法从 git 分支恢复。merge-1 改为异步（merge 前的数据在分支里已有）。

### 3.5 历史清理（一次性 gc）

当前 16GB .git 中有大量历史 state.db parts blob。LFS 配置后，新的 blob 不再进入 .git，但历史 blob 仍在。

```bash
# 一次性清理（在 LFS 迁移完成后执行）:
cd /workspace/SandboxHermesBackup

# 1. 将现有 state.db parts 迁移到 LFS
git lfs migrate import --include="config/profiles/*/state.db.parts/*" --everything

# 2. 过期并清理旧 ref
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# 3. force push（重写历史需要 force push）
git push --force origin main

# 预期效果: .git 从 16GB → ~2-3GB（只保留非 state.db 的历史）
```

**风险**：`git lfs migrate import --everything` 重写全部历史，需要 force push。执行前需：
1. 确认无其他活跃 clone（或通知重新 clone）
2. 备份当前 repo（`cp -a` 一份）
3. 在低峰期执行

---

## 4. 验收标准

| AC# | 验收项 | 验证方法 | 通过条件 |
|-----|--------|---------|---------|
| AC-1 | gzip 压缩生效 | 备份后检查 repo 中 part 文件为 .gz | `ls config/profiles/*/state.db.parts/*.gz` 有输出 |
| AC-2 | 压缩率 ≥ 40% | 对比压缩前后大小 | `gz_size / raw_size ≤ 0.6` |
| AC-3 | LFS 跟踪生效 | `.gitattributes` 存在且 LFS 配置正确 | `git lfs ls-files` 列出 state.db 文件 |
| AC-4 | .git 停止膨胀 | 连续 3 天备份后 .git 大小变化 | 日增长 ≤ 500MB（当前 ~1.5-2GB/日） |
| AC-5 | 恢复链路完整 | 从 LFS repo 恢复 state.db 并验证 | `gunzip + cat` 重组后 sha256 与源文件一致 |
| AC-6 | cron 频率降低 | crontab 只保留 1 条备份 cron | `crontab -l \| grep backup \| wc -l` == 1 |
| AC-7 | dirty 标记工作 | merge-4 触发后检查 dirty 文件 | `/workspace/.backup_dirty` 存在且内容正确 |
| AC-8 | merge-4/close-4 同步备份保留 | 管线 merge 后 backup 立即执行 | backup.py 日志显示 merge-4 触发了同步备份 |
| AC-9 | 历史清理后 repo 缩小 | gc 后 .git 大小 | ≤ 4GB（从 16GB 降低） |
| AC-10 | 飞书通知正常 | 备份成功/失败通知仍发送 | 收到飞书通知 |

---

## 5. 用户故事

### US-1：Frank（系统 Owner）

> 作为系统 Owner，我希望备份 repo 不要无限膨胀，这样 clone 和恢复不会越来越慢。

**当前痛点**：repo 18GB 且每天增长 1.5-2GB。如果 sandbox 崩溃需要迁移到新机器，clone 18GB 需要 10+ 分钟，且持续恶化。

**方案收益**：策略 C 落地后，.git 日增长从 ~1.5GB 降到 ~250MB，历史清理后 .git 从 16GB 降到 ~3GB。clone + LFS pull 总时间可控。

### US-2：OC（Orchestrator）

> 作为 OC，我希望管线触发的备份不要拖慢 merge/close 步骤。

**当前痛点**：每次 merge-1/merge-4/close-4 都同步执行 hermes_backup_push.sh，耗时 30-120 秒（含 rsync + git push），阻塞管线流转。

**方案收益**：merge-1 改为异步 dirty 标记（即时返回），merge-4/close-4 保留同步但使用压缩（减少 push 数据量）。

### US-3：恢复操作员（灾难恢复）

> 作为恢复操作员，我希望从备份恢复时步骤简单、可靠。

**当前痛点**：恢复需要 `cat part_* > state.db`，但如果 part 损坏无法提前发现（需要手动 sha256 校验）。

**方案收益**：LFS 自带内容寻址（sha256），恢复时 `git lfs pull` 自动校验。gzip 解压失败也能立即发现。

---

## 6. 风险与缓解

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|:----:|:----:|------|
| R1 | LFS 存储配额用尽 | 中 | 中 | GitHub LFS 免费 1GB 存储 + 1GB/月带宽；当前 state.db 总量 ~2GB，需购买 $5/月 50GB pack |
| R2 | `git lfs migrate` 重写历史失败 | 低 | 高 | 执行前 `cp -a` 备份；低峰期执行；force push 后验证 |
| R3 | gzip 压缩率不达预期 | 低 | 低 | SQLite VACUUM 后冗余页已清除，实测 gzip 对 SQLite 压缩率 40-60% |
| R4 | cron 频率降低导致 RPO 超标 | 低 | 中 | 保留 merge-4/close-4 同步备份；RPO ≤ 24h 符合原定目标 |
| R5 | LFS 服务不可用导致备份失败 | 低 | 高 | LFS push 失败时 fallback 到普通 git commit（非 LFS）+ 告警 |
| R6 | 恢复时忘记 `git lfs pull` | 中 | 中 | restore 脚本自动执行 `git lfs pull`；README 明确标注 |

### 6.1 LFS 配额评估

```
当前 state.db 总量（所有 profile）:
  orchestrator:  ~600MB (13 parts × 49MB)
  game-engine:   ~450MB
  game-qa:       ~280MB
  其他 profiles:  ~300MB
  合计:          ~1.6GB

gzip 压缩后:      ~700MB

GitHub LFS 免费配额: 1GB 存储 + 1GB/月带宽
→ 略超免费配额，建议购买 $5/月 Data Pack（50GB 存储 + 50GB/月带宽）
→ 或自建 LFS server（git-lfs-transfer 协议），但运维成本高，不推荐 MVP 阶段
```

---

## 7. 实施计划

### Phase 1: 止血（Day 1，~4h）

1. crontab 移除 13:00 / 18:30 两条备份 cron（保留 4:00）
2. merge-1 改为 dirty 标记（merge-4/close-4 暂保留同步）
3. state.db parts 增加 gzip 压缩
4. 验证：备份正常执行，.gz 文件生成，飞书通知正常

**预期效果**：日提交从 20-40 次降到 5-10 次，每次数据量减半。

### Phase 2: LFS 落地（Day 2，~4h）

1. 配置 `.gitattributes` + `git lfs install`
2. `git lfs migrate import` 迁移历史 state.db parts
3. `git gc --prune=now` 清理
4. force push
5. 验证：clone 新 repo，`git lfs pull`，恢复 state.db

**预期效果**：.git 从 16GB 降到 ~3GB。

### Phase 3: 验收（Day 3，~2h）

1. 连续运行 3 天，监控 .git 大小变化
2. 执行一次完整恢复演练（DR drill）
3. AC-1 ~ AC-10 全部验证

---

## 8. 工作量评估

| 阶段 | 工作内容 | 预估工时 | 执行方 |
|------|---------|:------:|:------:|
| Phase 1 | crontab + dirty 标记 + gzip | 4h | game-engine |
| Phase 2 | LFS 配置 + 迁移 + gc | 4h | game-engine |
| Phase 3 | 验收 + DR 演练 | 2h | game-qa |
| **合计** | | **10h** | |

**与架构师/工程师的分工**：
- 产品（本 PRD）：定义需求、验收标准、优先级、RPO/RTO 目标
- 架构师：评审 LFS 可行性、gzip 压缩率预期、migrate 安全性
- 工程师：实现代码修改、执行 LFS 迁移、验证
- QA：验收测试、DR 演练

---

## 9. 不做什么（Out of Scope）

| # | 不做的事 | 理由 |
|---|---------|------|
| 1 | 不改 rsync 全量镜像策略（config/ 目录） | config/ 是文本文件，git 能 delta 压缩，不是膨胀主因 |
| 2 | 不引入 SQLite 增量导出（策略 A） | 可靠性风险高（增量链断裂=全丢），复杂度不值得 |
| 3 | 不改 backup_roots 的 workspace/ 镜像 | workspace/ 总量 ~420MB，不是膨胀主因 |
| 4 | 不自建 LFS server | GitHub LFS $5/月足够，自建运维成本远超收益 |
| 5 | 不改 state.db split 阈值（49MB） | GitHub 文件大小限制 100MB，49MB 有余量；改阈值无收益 |
| 6 | 不做「按需备份」（只备份变化的 profile） | 实现复杂度高（需跟踪每个 profile 的变更时间），收益小 |

---

## 10. 度量指标（上线后监控）

| 指标 | 当前值 | 目标值 | 监控方式 |
|------|--------|--------|---------|
| .git 大小 | 16 GB | ≤ 4 GB | `du -sh .git/` 每日记录 |
| .git 日增长 | ~1.5-2 GB/日 | ≤ 500 MB/日 | 连续 3 天对比 |
| 备份 commit 频率 | 20-40 次/日 | ≤ 5 次/日 | `git log --since=1day \| wc -l` |
| 单次备份耗时 | 30-120 秒 | ≤ 60 秒 | backup-push.log 时间戳 |
| clone 耗时（含 LFS） | 10+ 分钟 | ≤ 3 分钟 | 定时测量 |
| 恢复成功率 | 100%（未测） | 100% | DR 演练验证 |

---

## 11. 决策记录

| 决策 | 选择 | 理由 | 日期 |
|------|------|------|------|
| 备份策略 | 策略 C（压缩+LFS+频率） | 可靠性优先 + BKP-001 落地 + 1 天可交付 | 2026-08-14 |
| merge-1 备份 | 改为异步 dirty 标记 | merge 前数据在 git 分支中已有，不需要备份保护 | 2026-08-14 |
| merge-4/close-4 备份 | 保留同步（压缩+LFS） | 不可逆操作，崩溃后无法从分支恢复 | 2026-08-14 |
| cron 频率 | 3次/日 → 1次/日 | RPO=24h 符合原定目标；管线触发补充保护 | 2026-08-14 |
| LFS 存储方案 | GitHub LFS $5/月 | 自建成本远超收益 | 2026-08-14 |

---

## 附录 A: 数据采集明细

### A.1 state.db parts 占比分析

```
备份 repo .git 总大小:   16 GB
state.db parts 对象:     13.1 GB (82%)
其他 git 对象:            2.9 GB (18%)

state.db parts 明细:
  唯一路径数:    36 (7 profiles × ~5 parts/profile)
  总对象版本数:  1,223
  平均每路径版本数: ~34 次（即每个 part 被重新提交了 ~34 次）
```

### A.2 各 profile state.db 大小

| Profile | state.db 大小 | split parts 数 | gzip 后预估 |
|---------|:------:|:------:|:------:|
| orchestrator | ~600MB | 13 | ~250MB |
| game-engine | ~450MB | 9 | ~190MB |
| game-qa | ~280MB | 6 | ~120MB |
| game-architect | ~100MB | 2 | ~45MB |
| infomanager | ~100MB | 2 | ~45MB |
| verifier | ~100MB | 2 | ~45MB |
| game-director | ~50MB | 1 | ~25MB |
| gateway-eng | 26MB | 0（不 split） | ~12MB |
| tag-system | 13MB | 0 | ~6MB |
| **合计** | **~1.7GB** | **35** | **~740MB** |

### A.3 提交频率与备份触发源映射

```
备份触发源:
  ┌─ cron 4:00 (UTC 20:00)  ────────────────────── 每日 1 次
  ├─ cron 13:00 (UTC 5:00)  ────────────────────── 每日 1 次
  ├─ cron 18:30 (UTC 10:30) ────────────────────── 每日 1 次
  ├─ merge-1 (管线)  ─────────── 每任务 1 次 ──────┐
  ├─ merge-4 (管线)  ─────────── 每任务 1 次 ──────┤ 每日 ~5-10 次
  └─ close-4 (管线) ─────────── 每任务 1 次 ──────┘
                                                  合计: ~8-13 次/日

密集期（如 2026-08-11 的 46 次提交）:
  = 3 cron + ~14 任务 × 3 管线触发 = 3 + 42 = 45 ≈ 46 ✓
```
