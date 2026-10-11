# cc-glm 软链部署步骤 — DPL-101 SUB-2（交付 OC/S2 执行）

> 依据: 架构 §2.2/§2.6（arch-dpl101-claude-code-glm-anthropic-direct.md v1.1）+ 评估 R3 决策
> 决策（本卡落地）: **ln -sf + cp 双份**（评估倾向项）——/usr/local/bin 软链满足"一次调用"部署语义，
> cp 到 orchestrator profile scripts/ 满足 deploy_drift_check.sh 的 repo↔profile 比较语义（第 7 项）。
> 部署动作永远留给 OC（.hermes.md 规则）；研发只负责 repo 正本 + 本文档。

## 前置条件

1. SUB-1 wrapper 已合入 main: `/workspace/devPPL/scripts/cc-glm`（bash，可执行）
2. must-sync 清单已 +1: `deploy_drift_check.sh` DEFAULT_SYNC_LIST 含 `cc-glm`（第 7 项）
3. claude CLI 2.0.0 可用（`claude --version` 首 token = 2.0.0；setup.py Phase 6 基线）

## 部署步骤（OC 执行）

```bash
# 1. 确认 repo 正本就绪（merge 后）
ls -l /workspace/devPPL/scripts/cc-glm          # 存在且可执行（-rwxr-xr-x）

# 2. 系统 PATH 软链（与 /usr/local/bin/claude 同模式）
ln -sf /workspace/devPPL/scripts/cc-glm /usr/local/bin/cc-glm

# 3. profile scripts 双份（供 deploy_drift_check.sh repo↔profile md5 比较；
#    与 glm_quota_probe.sh 的部署形态一致: cp + chmod，不做软链）
cp /workspace/devPPL/scripts/cc-glm /root/.hermes/profiles/orchestrator/scripts/cc-glm
chmod +x /root/.hermes/profiles/orchestrator/scripts/cc-glm

# 4. 部署自检（四检，doctor 不门禁只报告；额度窗口外期待 ENDPOINT=200）
/usr/local/bin/cc-glm doctor

# 5. drift 校验（清单第 7 项 cc-glm: 期待无 [deploy-drift] cc-glm 行 = repo↔profile 一致）
bash /workspace/devPPL/scripts/deploy_drift_check.sh | grep cc-glm || echo "cc-glm: 一致"
```

## 校验判据

| 步骤 | 期待 |
|------|------|
| `cc-glm doctor` | KEY=ok / ENDPOINT=200（额度窗口外）/ VERSION=2.0.0 ✓ / SHUTDOWN=none |
| deploy_drift_check.sh | 无 `[deploy-drift] cc-glm` 行（md5 一致） |
| E2E 双绿重放（S2，额度窗口外） | `cc-glm -p "Reply with exactly: DPL101-A1-OK" --max-turns 1` → JSON subtype=success, result=DPL101-A1-OK |

## 回滚

```bash
rm -f /usr/local/bin/cc-glm /root/.hermes/profiles/orchestrator/scripts/cc-glm
# repo 正本保留（must-sync 清单项保留——回滚部署不回滚监控清单）
```

## 备注

- **DPL-048 部署验证规则不适用本卡 repo 改动**（实测依据）: deploy_drift_check.sh 由
  autopilot.sh L226 以 repo 路径 `bash "$REPO_ROOT/scripts/deploy_drift_check.sh"` 调用，
  非 jobs.json script 直调、非绝对路径 /root/.hermes/profiles/orchestrator/scripts/ 引用；
  cc-glm 本身是 worker terminal 调用（非 cron 前置）——两者均不触发"repo vs live diff 一致才 PASS"门禁。
- 真实端点 A1 双绿（curl 200 + E2E subtype=success）按架构 §6.4 留 S2/OC 额度窗口后重放
  （本卡验收全部打桩，额度窗口不阻塞 dev 卡）。
