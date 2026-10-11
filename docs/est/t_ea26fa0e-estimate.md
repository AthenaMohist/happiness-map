# 工作量评估 — t_ea26fa0e（[FIX] keepalive v2 加 crond 守护层）

## 1. 源需求
crond 死亡后 gateway watchdog 全部失效（05 机制独木桥）。修法：`hermes_keepalive_v2.sh`（supervisor autorestart 托管）里加一层"crond 不在就拉起"，让保活守护反向守护 crond。

## 2. 实测校准（2026-09-06 现场侦查）
- 实现文件：/workspace/hermes_keepalive_v2.sh（非 repo 内脚本，live 副本即正本）
- **OC 09-06 已完成实现**（L309–334 Layer G：crond guardian）：
  - `pgrep -x cron` 检测 → 不在则 `( cron -f >/dev/null 2>&1 & )` 拉起
  - 二次校验失败计 `crond_fail_streak`（state file），≥3 → `hermes_backup_notify.sh alert` 飞书告警
  - 主循环每轮 `do_crond_guard &` 后台调用（L390–394），带 Frank 裁定背景注释
- 运行证据：/workspace/.hermes_keepalive_v2.log 各层（DISK/CPU/PLATFORM/SESSION/EXT）持续正常心跳；备份 cron（10:31 / 20:00）真实触发
- 回归 13 项全 PASS（OC 复核）

## 3. 工作量
- 预计轮数：**0–2 轮**（buffer 至 4）
  - 实现已完成 + 验收标准三项全部 [x] → 本卡无需新代码
  - 剩余工作仅：评估文档产出 + claim 收尾 → 1–2 轮
- 复杂度：极低（纯收尾，无实现工作）
- 风险点：
  1. keepalive_v2.sh 不在 devPPL repo（live-only 脚本）→ 本卡不涉及 repo 合并；若后续要把该脚本入库需单独建卡
  2. crond 拉起依赖 supervisor 侧 keepalive_v2 自身存活 — 已由 supervisor autorestart 托管，风险闭环

## 4. 决策
预计 ≤20 轮 → **不拆卡**，[SUB-SPLIT] 1 serial。
