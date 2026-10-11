# 备份流程速查（backup-flow-quickref）

> [FIX DPL-136-A] 备份流程机制化 · repo 内 wiki 副本
> 自动注入入口: `pipeline/backup_guide.py`（finalize.sh 命中 备份/backup/push/镜像/MERGE 关键词时自动附到 claim）

按项目类型分三类，合并/收尾后对照执行：

## 1. 系统类（devPPL 等，无独立远端）→ SandboxHermesBackup 镜像

- 镜像 repo（绝对路径）: `/workspace/SandboxHermesBackup`
- remote: `git@github.com:AthenaMohist/SandboxHermesBackup.git`

**步骤：**

1. `cd /workspace/SandboxHermesBackup`
2. `bash scripts/workspace/hermes_backup_push.sh`
   - 自动: rsync `~/.hermes` → `config/`、复制 sandbox 文件、原地注解 `manifest.yaml`、有变更则 commit + push
3. 手动场景（脚本不可用 / 只补部分变更）:

   ```bash
   HERMES_BACKUP_PUSH=1 git add -A && git commit -m "backup: <说明>" && git push
   ```

   - pre-commit hook 依赖 `HERMES_BACKUP_PUSH=1` 放行，**缺省必被拦**

**完成判定: push 成功才算完成。** 失败排查 `/workspace/backup-push.log`。

## 2. 纯产品类（有独立远端）

正常 `git push` 到项目自身远端即完成，无需 SandboxHermesBackup 镜像。

## 3. 混合类（产品远端 + 系统产物）

双重备份，缺一不可：

1. 项目自身远端 `git push`
2. SandboxHermesBackup 镜像（同系统类步骤 ①-③）

## 陷阱清单

| # | 陷阱 | 说明 |
|---|------|------|
| 1 | `HERMES_BACKUP_PUSH` 放行 | 手动 commit 必须带 `HERMES_BACKUP_PUSH=1` 前缀，否则 pre-commit hook 拦截 |
| 2 | manifest 三件套唯一实例在备份 repo 根 | `manifest.yaml` 及配套文件的唯一权威实例在 `/workspace/SandboxHermesBackup` 根，勿在其他位置另建副本 |
| 3 | DR-04 脏区清理丢弃未提交改动 | 脏区清理会丢弃备份 repo 内未提交改动 → 先 push 再清理 |
| 4 | 备份脚本绝对路径 | 用 `bash scripts/workspace/hermes_backup_push.sh`（在 `/workspace/SandboxHermesBackup` 下执行），不要依赖相对 cwd |
| 5 | push 成功才算完成 | 本地 commit ≠ 备份完成；push 失败看 `/workspace/backup-push.log` |
