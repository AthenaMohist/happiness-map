# [DEV-EST] 通知群迁移实现 — 工作量评估

> 源任务: t_204e8733（[DEV] 通知群迁移实现 — heartbeat/摘要→群，sentinel→仅 VA DM）
> 评估人: game-engine
> 评估时间: 2026-09-05

---

## 一、需求拆解

### 变更 1: notify_check.py — heartbeat/摘要目标改为群

**现状**：
- `heartbeat` 路径（L2592）：`feishu_send(cfg, creds, conn, hb, dry_run)` — 不传 chat_id，走 FEISHU_USER_OPEN_ID（VA DM）
- `summary` 路径（L2646）：`feishu_send(cfg, creds, conn, msg, dry_run)` — 同上
- `claim` 路径（L2534）：`feishu_send(..., chat_id=claim_chat_id)` — 已发群（claim_report_chat_id）

**改动**：
- 读取新配置 `cfg.get("feishu", {}).get("heartbeat_chat_id")` 或 `.env` 的 `FEISHU_HEARTBEAT_CHAT_ID`
- heartbeat 路径：传 `chat_id=heartbeat_chat_id` → 发群
- 摘要路径：同 heartbeat，传 `chat_id=heartbeat_chat_id`
- fallback：若 heartbeat_chat_id 为空/无效 → 回退当前行为（VA DM，不传 chat_id）
- claim 路径：不变，仍发 claim_report_chat_id

**改动量**：
- 新增：`load_credentials()` 中增加 HEARTBEAT_CHAT_ID 读取（约 5 行）
- 修改：heartbeat 发送调用点（L2592）+ 摘要发送调用点（L2646）各加一个 chat_id 参数（2 处）
- 修改：配置常量/默认值说明（docstring）
- 预计：+20 行代码，2 处调用修改

### 变更 2: glm_quota_probe.sh — alert() 改为仅 VA DM

**现状**：
- `alert()` 函数（L93-97）：调用 `sentinel_alert.sh`（双通道：VA DM + OC DM）
- sentinel_alert.sh L84-90：VA DM（主）+ OC DM（唤醒，SENTINEL_ALERT_OC=1 时）

**改动**：
- 在 glm_quota_probe.sh 内新增 `alert_va_only()` 函数，或
- 修改现有 `alert()` 函数，增加环境变量 `GLM_ALERT_ONLY_VA=1` 控制只发 VA DM
- 或者：直接改调用方式，绕过 sentinel_alert.sh 的 OC DM 通道

**最简方案**：修改 alert() 函数，增加 `GLM_ALERT_VA_ONLY` 标志，跳过 OC DM 调用。
改动量：~5 行（alert() 函数体内加条件判断）

**改动量**：+5 行，0 处调用修改（alert() 签名不变）

### 变更 3: 配置文件

- `config/notify.json`：新增 `feishu.heartbeat_chat_id` 字段（初始空字符串或占位符）
- `.env`：新增 `FEISHU_HEARTBEAT_CHAT_ID`（但 .env 不在 repo，只读文件）

**改动量**：+1 行 JSON，0 行 Python（配置读取复用已有模式）

### 变更 4: 测试

**test_notify_check.py**：
- 新增 T110：heartbeat 发群（配置 heartbeat_chat_id 非空时，feishu_send 被调用带 chat_id）
- 新增 T111：heartbeat fallback（heartbeat_chat_id 为空时，feishu_send 不传 chat_id）
- 新增 T112：摘要发群（同 T110，验证 summary 路径也带 chat_id）
- 修改 T35/T36：原有回归测试需要适配（原断言"不传 chat_id" → 改为"传 heartbeat_chat_id"）
- 预计：+60 行测试代码

**test_glm_quota_probe.sh**：
- 新增 T17：alert 仅 VA DM（GLM_ALERT_VA_ONLY=1 时，sentinel 只收到 1 次调用而非 2 次）
- 预计：+20 行测试代码

---

## 二、工作量评估

| 模块 | 改动行数 | 复杂度 | 风险点 |
|------|---------|--------|--------|
| notify_check.py | +20 / -2 | 低 | fallback 逻辑需确保不影响 claim 路径 |
| glm_quota_probe.sh | +5 | 极低 | 不影响 probe/recover 主流程 |
| config/notify.json | +1 | 极低 | 字段默认空，不破坏现有逻辑 |
| test_notify_check.py | +60 | 中 | T35/T36 需适配，回退逻辑测试充分 |
| test_glm_quota_probe.sh | +20 | 低 | 环境变量覆盖已有模式 |
| **合计** | **~106 行** | **低** | **无高风险点** |

### 预期轮次：8-12 轮

**轮次分解**：
1. 读源码理解（已做）→ 0.5 轮
2. 改 notify_check.py（2 处调用 + 配置读取）→ 2 轮
3. 改 glm_quota_probe.sh（alert 函数）→ 0.5 轮
4. 改配置文件 → 0.5 轮
5. 写测试（notify + probe）→ 3 轮
6. 跑全量测试 + 修复 → 2 轮
7. claim + 飞书推送 → 1 轮

---

## 三、风险点

1. **fallback 逻辑**：heartbeat_chat_id 为空时必须回退 VA DM，不能静默失败
2. **测试适配**：T35/T36 原断言"摘要不传 chat_id"需要改为"摘要传 heartbeat_chat_id"
3. **部署验证**：glm_quota_probe.sh 是 must-sync 清单中的脚本（test_deploy_drift.sh T8），改动后需验证 deploy-drift 测试通过
4. **sentinel_alert.sh 不受影响**：OC DM 通道保留，只是 glm_quota_probe.sh 不再使用

---

## 四、拆卡建议

**[SUB-SPLIT] 1** — 不拆，单卡可完成。

理由：
- 改动面小（3 个文件 + 2 个测试文件）
- 预期 8-12 轮，< 20 轮阈值
- 无跨模块依赖，可顺序完成
- 测试可并行写，但整体工作量不足以拆分

---

## 五、验收标准核对

| 验收项 | 对应测试 | 状态 |
|--------|---------|------|
| heartbeat 发新群 | T110 | 待实现 |
| 摘要发新群 | T112 | 待实现 |
| GLM sentinel 仅 VA DM | T17（新） | 待实现 |
| 回退 OC DM 正常 | T111 + 现有 claim 测试 | 已有覆盖 |
| 测试全绿 | 全量 pytest + test_glm_quota_probe.sh | 待验证 |

---

## 六、产出物

- docs/est/t_204e8733-estimate.md（本文档）
