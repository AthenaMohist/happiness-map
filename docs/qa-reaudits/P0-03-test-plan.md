# P0-03 备份 DR 演练 — 测试方案

> 版本：v1.0 | 状态：Draft — 待评审
> 编制日期：2026-07-08
> 编制人：game-qa（QA）
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0（436 行）
> 原始任务：P0-03 / t_692d189e — 备份 DR 演练

---

## 1. 范围

### 1.1 被测系统

Hermes Agent 备份系统由以下组件构成：

| 组件 | 路径/标识 | 功能 |
|------|----------|------|
| 每日备份 wrapper | `/workspace/hermes_daily_backup.sh` | 加载 `.env`，调用 push 脚本 |
| 备份推送脚本 | `/workspace/hermes_backup_push.sh` | rsync + split + git commit + push |
| 备份目标仓库 | `github.com/AthenaMohist/SandboxHermesBackup` | GitHub 私有仓库 |
| 备份 manifest | `/workspace/manifest.yaml` (v6) | 定义 backup_roots + sandbox_files |
| 恢复技能 | `hermes-backup-restore` skill | 标准恢复流程（7 步） |
| Curator 备份 | `config.yaml: curator.backup.enabled=true, keep=5` | 技能 curator 快照备份 |
| Cron 调度 | supervisor `hermes-cron.conf` | 每日 11:00 UTC 触发 |

### 1.2 被测数据资产

| 数据 | 路径 | 大小 | 备份状态 |
|------|------|------|:---:|
| kanban.db | `/root/.hermes/kanban.db` | ~556K | ✅ rsync 同步到 backup-repo/config/kanban.db |
| state.db | `/root/.hermes/state.db` | ~8.4M | ✅ split 为 49MB chunks 存入 backup-repo |
| profiles | `/root/.hermes/profiles/` | ~3.8G | ✅ rsync 同步（含 SOUL.md, SKILL.md, sessions, cron） |
| skills | `/root/.hermes/skills/` | ~6.5M | ✅ rsync 同步 |
| config.yaml | `/root/.hermes/config.yaml` | ~17K | ✅ rsync 同步 |
| sessions | `/root/.hermes/sessions/` | ~540K | ✅ rsync 同步 |
| memories | `/root/.hermes/memories/` | ~4K | ✅ rsync 同步 |
| sandbox scripts | `/workspace/*.sh, /workspace/*.py` | — | ✅ 按 manifest 逐个复制 |
| supervisor configs | `/usr/local/share/supervisor/*.conf` | — | ✅ 按 manifest 逐个复制 |
| **auth.json** | `/root/.hermes/auth.json` | ~1.2K | ❌ **有意排除**（凭据必须手动保留） |
| **.env** | `/root/.hermes/.env` | ~23K | ❌ **有意排除**（API keys 必须手动保留） |
| state.db-shm/wal | `/root/.hermes/state.db-*` | — | ❌ **排除**（运行时文件，恢复时重建） |

### 1.3 当前状态（执行前基线）

- **上次备份时间**：2026-07-08 10:30 UTC（今日，97 files changed，commit dd14e54）
- **备份 cron**：每日 11:00 UTC，由 supervisor `hermes-cron.conf` 管理
- **备份历史**：GitHub repo 上有持续提交历史
- **恢复记录**：**无**——从未执行过完整恢复验证
- **RPO**：~24h（每日备份间隔）
- **RTO**：未知（未测量恢复时长）

---

## 2. 风险摘要（预执行评估）

| 风险 | 级别 | 依据 |
|------|:---:|------|
| 备份存在但从未验证恢复 → 备份等于不存在 | **BLOCKER** | §1.2: 用户可感知 + 功能阻断 + 无 workaround |
| credential 文件（auth.json/.env）无备份 → 恢复后无法认证 | **BLOCKER** | 等效于功能阻断 |
| state.db split 重组的完整性未验证 | **MAJOR** | 数据一致性风险（C 级按正常公式） |
| 3.8G profiles 备份完整性未知（文件数巨大） | **MAJOR** | 大规模数据一致性风险 |
| sandbox scripts 权限未在恢复时自动设置 | **MAJOR** | 功能阻断但有 workaround（手动 chmod） |
| DR 演练从未执行（无流程文档、无复盘模板） | **MINOR** | 用户间接受影响 |
| 备份 cron 依赖 supervisor → supervisor 挂掉则备份停止 | **MAJOR** | 系统健康度退化 |
| 备份失败无告警通知 | **MAJOR** | 用户可感知（延迟发现数据丢失） |
| GitHub token 过期 → 备份静默失败 | **MAJOR** | 等效于功能阻断（有 workaround：手动更新 token） |

---

## 3. 发现分级（逐条对照标准）

### F1a: 备份存在但从未验证恢复 — BLOCKER

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（备份失败时用户发现无法恢复数据）
  功能阻断？→ 是（无法恢复 = 备份系统的核心功能失效）
  workaround？→ 否（没有其他恢复手段）
→ BLOCKER
```

**证据**：
- 备份 repo 有持续提交历史（最新 commit dd14e54, 2026-07-08）
- 但从未执行过 restore 步骤（hermes-backup-restore skill 的 Step 1-7）
- 无法确认 `config/` 目录下的文件是否可实际还原成可工作的 Hermes 环境

**SLA 要求**：响应 4h / 定位 8h / 方案 24h（§8.1）

**建议修复方案**：
1. 在 staging 环境执行一次完整 restore
2. 验证 hermes status / hermes profile list / hermes skills list 正常
3. 验证 kanban.db 可读（sqlite3 ".tables"）
4. 验证 skills 可加载（skill_view 随机抽查 3 个）
5. 记录完整 RTO 基线

---

### F1b: credential 无法自动恢复 — BLOCKER

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（恢复后所有 API 调用失败，Dashboard 500）
  功能阻断？→ 是（无认证 = 整个系统不可用）
  workaround？→ 是（手动复制 .env + auth.json 到恢复目标）
→ MAJOR（有 workaround）

特殊考虑：如果恢复流程中包含 auth.json/.env 的备份/恢复但实际被错误排除，
  则升级为：
  安全漏洞？→ 按 §A5 安全配置错误 → 最低 MAJOR
  数据敏感度：A 级（.env 含 API keys）

暂定：MAJOR。研发评估时确认。
```

**证据**：
- `hermes_backup_push.sh` 的 rsync 命令未显式排除 auth.json/.env（但路径 ``--exclude`` 列表无这两个文件）
- `hermes-backup-restore` skill 的 Step 3 明确要求"Preserve current credentials"——这是 restore 流程中的 manual step
- **restore skill 假设 credential 文件已被手动保存**，但如果用户未保存则不可恢复

**建议**：
- 在恢复流程文档中增加醒目的 credential 前置检查步骤
- 考虑加密备份 credential（需 Frank 批准安全策略）

---

### F2: state.db split/reassemble 完整性未验证 — MAJOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（扩展定义：数据完整性受影响）
  功能阻断？→ 有 workaround（state.db 可以重建，但丢失历史 session 数据）
  数据敏感度：C 级（内部状态数据）→ 按正常公式
→ MAJOR（数据一致性问题，C 级不加权）
```

**证据**：
- `hermes_backup_push.sh` Step 4.5：将 state.db 按 49MB split
- split 产生 `part_00` ~ `part_05` + README.md
- reassemble 命令 `cat part_* > ../state.db` 写入 README 中
- **但从未验证过 reassemble 后的 state.db 可被 SQLite 正常读取**

**建议**：
- DR 演练中增加 `sqlite3 state.db "SELECT COUNT(*) FROM sessions"` 完整性检查
- 计算原始 state.db 和 reassembled state.db 的 sha256 对比

---

### F3: 3.8G profiles 备份完整性未知 — MAJOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（某 profile 的 SKILL.md 或 cron 配置丢失）
  功能阻断？→ 有 workaround（可从其他 profile 复制技能）
  数据敏感度：C 级（内部配置）→ 按正常公式
→ MAJOR
```

**证据**：
- `~/.hermes/profiles/` 包含 6+ 个 profile（game-qa, game-engine, infomanager, orchestrator, verifier, gateway-demo 等）
- 每个 profile 含 skills/, sessions/, cron/, memories/ 子目录
- rsync 无文件计数校验——只依赖 rsync 自身的错误检测
- 3.8G 数据量，rsync 传输错误概率不可忽略

**建议**：
- 备份后执行文件计数对比（`find $HERMES_DIR/profiles -type f | wc -l` vs repo）
- 抽样校验（随机 50 个文件的 sha256）

---

### F4: sandbox scripts 恢复后权限未自动设置 — MAJOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（恢复后脚本无法执行，dashboard/keepalive 启动失败）
  功能阻断？→ 有 workaround（手动 chmod +x）
→ MAJOR
```

**证据**：
- `hermes-backup-restore` skill Step 6 末尾：`chmod +x /workspace/*.sh /workspace/*.py`
- manifest 中还有 `/usr/local/share/supervisor/*.conf` 等非脚本文件
- 如果恢复流程中遗漏 chmod，supervisor 无法启动守护进程

**建议**：
- 在 restore skill 的验证步骤（Step 7）中增加权限检查
- 自动化权限恢复：遍历 manifest 中的 executable 文件类型

---

### F5: 备份 cron 单点依赖 supervisor — MAJOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（扩展定义：系统健康度退化）
  功能阻断？→ 有 workaround（手动执行备份脚本）
→ MAJOR
```

**证据**：
- 每日备份由 supervisor `hermes-cron.conf` 中的 cron daemon 触发
- 如果 supervisor 挂掉，备份 cron 也随之停止
- cron daemon 本身在 supervisor 管理之外没有独立的健康检查
- `backup-push.log` 只记录成功/失败，不包含 supervisor 状态的监控

**建议**：
- 增加独立的 cron watchdog（如 systemd timer 作为 supervisor 的 fallback）
- 备份失败时发送通知（Telegram/Discord 告警）

---

### F6: 备份失败无告警通知 — MAJOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（备份静默失败 → 某天需要恢复时发现最近一次成功备份是 N 天前）
  功能阻断？→ 有 workaround（手动检查 backup-push.log）
→ MAJOR
```

**证据**：
- `hermes_backup_push.sh` 失败时只记录到 `backup-push.log`（本地文件）
- 无 Telegram/Discord/邮件通知
- `hermes_daily_backup.sh` log 写到了 `backup-push.log`，但无人监控

**建议**：
- 备份成功/失败各发送一条通知到指定 channel
- 连续 3 天失败 → 升级告警

---

### F7: GitHub token 过期无检测 — MAJOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 是（备份静默失败）
  功能阻断？→ 有 workaround（手动更新 token 后重新推送）
→ MAJOR
```

**证据**：
- backup 脚本依赖 `GITHUB_BACKUP_TOKEN` 环境变量（从 `.env` 加载）
- 脚本第 42 行检查 token 是否设置，但无法检测 token 是否仍有效
- token 过期后 `git push` 会失败，但错误信息被 `_filter_token` 过滤
- **当前 token 过期时间未知**（需确认 GitHub Personal Access Token 的有效期设置）

**建议**：
- 在 backup 脚本中增加 token 有效性预检（如 `curl -s -o /dev/null -w "%{http_code}" https://api.github.com/user`）
- 设置 token 过期前 7 天的 reminder cron job

---

### F1c: DR 演练频率不明确 — MINOR

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户可感知？→ 间接（只有灾难发生时才会被发现）
  功能阻断？→ 否
→ MINOR
```

**证据**：
- 无文档定义 DR 演练的执行频率
- 上次演练：从未执行
- 业界建议：至少每季度一次

**建议**：
- 定义 DR 演练频率：首次立即执行，后续每季度一次
- 将演练结果记录到 `docs/dr-drill/YYYY-MM-DD-report.md`

---

### F1d: 缺少 DR 复盘模板 — SUGGESTION

**判定路径**：
```
前置检查：安全漏洞？→ 否
正式判定：
  用户不可感知？→ 是（纯流程/文档层面）
→ SUGGESTION
```

**建议**：
- 创建标准化 DR 复盘模板，含 RPO 达成率、RTO 实际值、发现的问题、改进项

---

## 4. 测试用例

### 4.1 DR 演练主流程（端到端）

---

#### TC-P03-01: 完整备份 → 恢复 → 功能验证（DR 演练核心）

```
Given: Hermes 环境正常运行
       备份 repo 已配置且有最近一次成功备份（commit dd14e54）
       一个独立的恢复目录 /tmp/hermes-dr-restore/

When:  执行 DR 演练流程：
        1. 确认最新备份 commit 存在且数据完整（见 TC-P03-02）
        2. git clone SandboxHermesBackup 到恢复环境
        3. 手工保存当前 auth.json + .env 到安全位置
        4. 按 hermes-backup-restore skill Step 1-7 执行恢复
        5. 验证恢复后的 Hermes 环境功能完整性（见 TC-P03-03）

Then:  所有恢复步骤成功执行
       恢复后的 Hermes 环境满足 TC-P03-03 的全部验证条件
       RTO 实际值已记录（从 clone 到验证完成的总耗时）
```

---

#### TC-P03-02: 备份完整性校验

```
Given: 备份 repo SandboxHermesBackup 已 clone 到本地

When:  执行完整性校验：
        1. 检查 manifest.yaml 中的 last_scan 时间戳（应 ≤ 24h 前）
        2. 逐条验证 sandbox_files 中的所有 path 在 scripts/ 下有对应文件
        3. 抽样对比 SHA256：随机 10 个 sandbox_file，计算 scripts/ 下副本的 sha256
        4. 验证 config/ 目录结构完整性：
           - config/config.yaml 存在
           - config/profiles/ 下至少有一个 profile 子目录
           - config/skills/ 下至少有一个 skill
           - config/sessions/ 目录存在
           - config/kanban.db 存在且可被 sqlite3 打开
        5. 验证 state.db parts：cat part_* > state.db.reassembled
           然后用 sqlite3 state.db.reassembled "SELECT COUNT(*) FROM sessions"

Then:  manifest last_scan ≤ 24h
      所有 sandbox_files 在 scripts/ 下存在
      抽样 sha256 全部匹配
      config/ 目录结构完整
      state.db.reassembled 可被 sqlite3 正常读取
      sessions 表行数 > 0
```

---

#### TC-P03-03: 恢复后功能验证

```
Given: 已按 hermes-backup-restore skill 完成恢复
       auth.json 和 .env 已手动恢复到 ~/.hermes/

When:  执行功能验证：
        1. hermes status → 无报错，显示正确的 model/provider/profile 数量
        2. hermes profile list → 列出所有 profile（≥ 6 个）
        3. hermes skills list → 列出所有 skill（≥ 15 个）
        4. skill_view("hermes-backup-restore") → 返回完整 SKILL.md 内容
        5. sqlite3 ~/.hermes/kanban.db "SELECT COUNT(*) FROM tasks" → 行数 > 0
        6. 随机启动一个 skill（如 skill_view("kanban-worker")）→ 正常加载
        7. supervisorctl status → 所有关键服务 running（dashboard, keepalive, keepawake, claude-proxy, cron, webterm）
        8. curl http://localhost:9119/login → HTTP 200

Then:  所有 8 项检查通过
       无 ERROR 级别日志出现在恢复过程中
```

---

#### TC-P03-04: kanban.db 恢复后数据完整性

```
Given: 恢复前的 kanban.db 已备份其 task/task_event/comment 表的计数
       恢复已完成

When:  对比恢复后 kanban.db：
        1. SELECT COUNT(*) FROM tasks
        2. SELECT COUNT(*) FROM task_events
        3. SELECT COUNT(*) FROM comments
        4. 随机抽查 5 个 task id 的 title 与恢复前一致

Then:  tasks 计数 ≥ 恢复前计数（容许恢复期间新增 task）
       task_events / comments 计数 ≥ 恢复前
       抽查的 5 个 task title 全部一致
```

---

### 4.2 失败场景

---

#### TC-P03-05: 备份 cron 停止时的表现

```
Given: Hermes 环境正常运行
       备份 cron 已正常运行至少 1 天

When:  模拟 cron 停止：
        1. supervisorctl stop hermes-cron（或等效操作停止 cron daemon）
        2. 等待超过 1 个备份周期（> 24h）
        3. 检查 backup-push.log 的最后一次成功时间

Then:  backup-push.log 显示最后一次成功 ≤ cron 停止前的最近一次
       超过 24h 无新备份 → 触发告警（如告警机制已实施）
       手动执行 /workspace/hermes_daily_backup.sh 仍可成功备份
```

---

#### TC-P03-06: GitHub token 失效时的表现

```
Given: Hermes 备份系统配置完成
       用于测试的临时 token（或使用无效 token 模拟）

When:  将 GITHUB_BACKUP_TOKEN 设置为无效值
       执行 /workspace/hermes_backup_push.sh

Then:  脚本以非零退出码退出
       backup-push.log 中有明确的 git push 失败记录
       （期望）告警通知已发送
       原有的备份 repo 未受影响（无损坏的 push）
```

---

#### TC-P03-07: ~/.hermes/ 目录不存在时的备份表现

```
Given: Hermes 配置目录 /root/.hermes 被模拟为不存在
       备份脚本指向不存在的目录

When:  临时重命名 /root/.hermes → /root/.hermes.bak
       执行 /workspace/hermes_backup_push.sh

Then:  脚本在 Step 1 检测到 hermes 目录缺失，立即报错退出
       退出码 ≠ 0
       错误信息明确指向目录缺失
       backup repo 无损坏（无空目录覆盖）
```

---

#### TC-P03-08: rsync 过程中网络中断

```
Given: 备份 repo 的 GitHub 仓库可达
       rsync 中 ~/.hermes/ 的数据已准备就绪

When:  在 git push 阶段模拟网络中断（设置极短的 curl 超时或断网）
       执行 /workspace/hermes_backup_push.sh

Then:  git push 失败，脚本以非零退出码退出
       本地 repo 的 commit 已生成但未 push
       下次 cron 运行时重新 push（或创建新的 cumulative commit）
       数据未丢失——rsync 阶段已完成，只是 push 失败
```

---

### 4.3 边界条件

---

#### TC-P03-09: 空 ~/.hermes 目录备份

```
Given: Hermes 刚初始化，~/.hermes/ 仅有最小文件集
       （config.yaml, auth.json, .env 等）

When:  执行备份脚本

Then:  备份成功执行
       backup repo 中 config/ 包含最小文件集
       无 rsync 报错（如 "vanished files"）
       manifest 更新了 last_scan 时间戳
```

---

#### TC-P03-10: state.db 超过 49MB 阈值

```
Given: state.db 大小 > 49MB（模拟：cp 大文件到 state.db）
       备份脚本配置为 49MB split 阈值

When:  执行备份脚本

Then:  state.db 被正确 split 为 state.db.parts/part_* 
       part_00 ~ part_N 每个 ≤ 49MB
       state.db.parts/README.md 包含 reassemble 指令
       monolithic state.db 被移除，.gitignore 已添加 state.db
       执行 cat part_* > state.db; sqlite3 state.db ".tables" 返回正常
```

---

#### TC-P03-11: 同时有多个 state.db 需要 split

```
Given: ~/.hermes/config/ 和 ~/.hermes/config/profiles/orchestrator/ 都有 state.db

When:  执行备份脚本

Then:  两个 state.db 都被独立 split
       各自的 .gitignore 中都有 state.db
       各自的 .parts/ 目录结构完整
       无交叉污染
```

---

## 5. 执行检查清单

### 5.1 演练前准备

- [ ] 确认最新备份 commit 存在且完整（TC-P03-02）
- [ ] 准备独立恢复环境（/tmp/hermes-dr-restore/ 或新容器）
- [ ] 确认 auth.json + .env 已安全备份到恢复环境之外
- [ ] 记录当前 kanban.db 基线（task/event/comment 计数）
- [ ] 记录当前 profile 列表
- [ ] 确认恢复环境有 rsync、git、sqlite3、python3 可用

### 5.2 演练执行

- [ ] TC-P03-01: 完整备份 → 恢复 → 功能验证
- [ ] TC-P03-02: 备份完整性校验
- [ ] TC-P03-03: 恢复后功能验证
- [ ] TC-P03-04: kanban.db 恢复后数据完整性
- [ ] TC-P03-09: 空目录边界测试
- [ ] TC-P03-10: state.db split 完整性

### 5.3 演练后

- [ ] 记录 RPO 实际值（最后备份时间到当前时间的差距）
- [ ] 记录 RTO 实际值（从 clone 到所有验证通过的总耗时）
- [ ] 填充 DR 复盘模板（见 §7）
- [ ] 更新恢复文档（如发现流程与实际不符）
- [ ] 关闭或更新本方案中的 findings

---

## 6. SLA 与时间预算

### 6.1 执行 SLA（本次 DR 演练）

| 阶段 | 预计耗时 | 备注 |
|------|:---:|------|
| 准备（基线记录 + 环境搭建） | 30min | |
| TC-P03-02 备份完整性校验 | 15min | 取决于 repo clone 速度 |
| TC-P03-01/03 恢复 + 验证 | 30min | |
| TC-P03-04 数据完整性 | 10min | |
| TC-P03-05~08 失败场景 | 30min | |
| TC-P03-09~11 边界条件 | 20min | |
| 复盘 + 文档更新 | 30min | |
| **总计** | **~2.5h** | |

### 6.2 修复 SLA（如发现 BLOCKER）

| 级别 | 响应 | 定位 | 方案 |
|------|:---:|:---:|:---:|
| F1a (BLOCKER) | 4h | 8h（如备份不可恢复 → 立即定位问题所在环节） | 24h |
| F1b (MAJOR→BLOCKER?) | 4h | 8h | 24h |

---

## 7. DR 复盘模板

```markdown
# DR 演练复盘报告 — YYYY-MM-DD

## 基线
- 备份时间：
- 备份 commit：
- 数据量（~/.hermes 总大小）：
- sandbox_files 数量：

## 恢复结果
| 检查项 | 结果 | 备注 |
|--------|:---:|------|
| backup integrity (TC-P03-02) | PASS/FAIL | |
| restore + func verify (TC-P03-03) | PASS/FAIL | |
| kanban data integrity (TC-P03-04) | PASS/FAIL | |

## 指标
- RPO（实际）：距离最后备份的时长
- RTO（实际）：从 clone 到验证通过的总耗时
- RPO 目标：24h（☐ 达成 / ☐ 未达成）
- RTO 目标：待定义（本次建立基线）

## 发现的问题
1. 
2. 

## 改进项
1. 
2. 

## 下次演练
- 建议日期：
- 演练人：
```

---

## 8. 发布门禁影响

按标准 §10：

```
当前状态：BLOCKED — F1a BLOCKER 未修复
门禁条件：BLOCKER=0 AND 安全漏洞=0 AND 无未裁定的申诉
```

**解封路径**：
1. 执行一次完整 DR 演练并通过所有核心测试用例
2. F1a 降级或关闭（证明备份可恢复）
3. F1b 确认级别（MAJOR 或有 workaround 保持 MAJOR）
4. 其他 MAJOR findings 至少标注 known issue

**如果 DR 演练失败（恢复不成功）**：F1a 确认 BLOCKER，需研发立即修复备份链路。

---

## 9. 附录

### 9.1 证据目录

| 证据 | 路径 | 内容 |
|------|------|------|
| 备份脚本 | `/workspace/hermes_backup_push.sh` | 379 行 bash 脚本 |
| 备份 wrapper | `/workspace/hermes_daily_backup.sh` | 54 行 bash 脚本 |
| 备份 manifest | `/workspace/manifest.yaml` | v6，含 20+ 个 sandbox_files |
| 备份日志 | `/workspace/backup-push.log` | 最近一次：2026-07-08 10:30 UTC — 成功 |
| 恢复 skill | `~/.hermes/skills/devops/hermes-backup-restore/SKILL.md` | 7 步恢复流程 |
| 上次备份 commit | `dd14e54` | 2026-07-08, 97 files changed |
| 备份 repo | `github.com/AthenaMohist/SandboxHermesBackup` | 私有仓库 |

### 9.2 判定公式对照总表

| 发现 | §1.2 子句 | 级别 | 置信度 |
|------|----------|:---:|:---:|
| F1a | 用户可感知 + 功能阻断 + 无 workaround | BLOCKER | 高 |
| F1b | 用户可感知 + 功能阻断 + 有 workaround | MAJOR | 中（研发需确认排除意图） |
| F2 | 数据一致性问题 + C 级 + 按正常公式 | MAJOR | 高 |
| F3 | 数据一致性问题 + C 级 + 按正常公式 | MAJOR | 中（需抽样验证） |
| F4 | 用户可感知 + 功能阻断 + 有 workaround | MAJOR | 高 |
| F5 | 系统健康度退化 + 有 workaround | MAJOR | 高 |
| F6 | 用户可感知 + 有 workaround | MAJOR | 高 |
| F7 | 用户可感知 + 有 workaround | MAJOR | 高 |
| F1c | 用户可感知 + 不影响核心任务 | MINOR | 高 |
| F1d | 用户不可感知 | SUGGESTION | 高 |

---

## 10. 审批

| 角色 | 审批意见 | 日期 |
|------|---------|------|
| QA（game-qa） | 方案编制完成，待评审 | 2026-07-08 |
| 研发（寇豆码） | 待审批 | |
| 架构（高见远） | 待审批 | |
| 产品（许清楚） | 待审批 | |
