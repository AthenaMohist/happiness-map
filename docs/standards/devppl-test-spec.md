# devPPL 测试规范（Test Spec）

> 版本：v1.0 | 状态：生效 | 生效日期：2026-08-15
>
> 本文档由 DPL-057（t_f8d25717）登记根因后落地。触发事件：DPL-056 SUB-3（t_49ce4679）全量验证反复失败超时，OC 排查定位为测试环境 sys.path 硬编码污染 + pytest 收集被模块级 exit() 杀死（2026-08-15）。
>
> **核心原则**：测试代码必须 worktree-portable（在任何 checkout 路径都能跑），且绝不允许破坏 pytest 收集/运行流程。验收门禁=全量 pytest 可完整跑完（无 INTERNALERROR）。

---

## 目录

1. [事故复盘（为什么有这份规范）](#1-事故复盘为什么有这份规范)
2. [规则 R1：禁止硬编码绝对路径](#2-规则-r1禁止硬编码绝对路径)
3. [规则 R2：脚本式测试禁止 test_ 前缀 / 必须加收集守卫](#3-规则-r2脚本式测试禁止-test_-前缀--必须加收集守卫)
4. [验收扫描命令](#4-验收扫描命令)
5. [存量债务清单（非阻断，逐步清理）](#5-存量债务清单非阻断逐步清理)
6. [版本历史](#版本历史)

---

## 1. 事故复盘（为什么有这份规范）

### 1.1 事件经过

DPL-056 SUB-3（R2 建链门禁）worker 在 60 迭代预算内反复"实现完成 → 全量 pytest 验证失败 → 重试"直至超时。OC 排查根因分两层：

**根因 A — sys.path 硬编码污染 import 缓存：**

```
tests/test_dpl026_est_card_isolation.py L21（旧版）
    sys.path.insert(0, '/workspace/devPPL')        # ← 硬编码主仓库绝对路径

运行顺序（字母序）：test_dpl026_* 先于 test_dpl056_*
→ dpl026 把 /workspace/devPPL（主仓库）插到 sys.path[0]
→ 后续 dpl056 测试 import pipeline.cmd_chain 时命中主仓库旧版模块（import 缓存被污染）
→ validate_card_gate_fields AttributeError → 8 用例连锁失败
→ worker 误以为自己的实现有 bug，反复重试
```

**根因 B — 脚本式测试模块级 exit() 杀死 pytest 收集：**

```
tests/scripts/test_staleness_guard.py（旧版，模块级）
    ...直接执行断言...
    exit(0)        # ← 模块顶层 exit → pytest 收集阶段 INTERNALERROR → 整个套件跑不起来
```

### 1.2 教训

1. **修一类模式必须全量扫描**：昨天 0d95694 只修了 `test_slice3_d1_qa.py` 一个文件，同类 5 文件漏网（slice2_integration / test_slice2_d1_qa / slice3_smoke_test / test_produces_check / test_dpl026_est_card_isolation），导致污染未根治。根治教训：修复时用本文档 §4 的扫描命令全量确认 0 残留。
2. **测试代码与生产代码同标准**：测试也是代码，同样禁止硬编码环境绝对路径。
3. **pytest 收集是脆弱阶段**：任何模块顶层副作用（exit、无限循环、sys.exit）都会杀死整个套件，危害远大于单个用例失败。

---

## 2. 规则 R1：禁止硬编码绝对路径

### 2.1 强制条款

新增/修改测试**禁止**硬编码任何机器/仓库绝对路径（如 `/workspace/devPPL/...`、`/root/...`）。

需要引用仓库路径时，必须基于 `__file__` 计算（worktree-portable）：

```python
# ✅ 正确：基于 __file__ 相对计算（worktree-portable，DPL-056 根治硬编码）
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent   # tests/ → 仓库根
sys.path.insert(0, str(REPO_ROOT))

# ✅ 正确：os.path 写法（同类文件可见）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ❌ 禁止：硬编码绝对路径（无论是否带尾注释）
sys.path.insert(0, '/workspace/devPPL')
```

### 2.2 覆盖范围

- `sys.path.insert / sys.path.append` 的路径参数
- 资源文件读取路径（contract_path、report_path、db_path、脚本路径等）
- 任何会被 `open()` / `Path()` / `subprocess` 引用的绝对路径

### 2.3 例外（必须显式注释说明原因）

- 测试**就是**要验证固定路径行为的用例（如验证门禁拒绝 `/workspace/devPPL` 硬编码），此时应在代码旁注释 `# DPL-057 例外: 本用例故意验证固定路径行为`。
- 读环境变量回退主仓库（如 `os.environ.get("HERMES_KANBAN_WORKSPACE", "/workspace/devPPL")`）属存量模式，新代码应优先 `__file__` 相对，环境变量仅在确实需要指向部署副本时使用。

---

## 3. 规则 R2：脚本式测试禁止 test_ 前缀 / 必须加收集守卫

### 3.1 定义

**脚本式测试** = 在模块顶层直接执行断言/流程、并以 `exit()` / `sys.exit()` 结束的 Python 文件（通常靠 `python3 xxx.py` 独立运行）。

### 3.2 强制条款

1. **禁止**在 `tests/` 下创建模块级执行 + `exit()` 且命名为 `test_*.py` / `*_test.py` 的文件 —— pytest 默认收集规则会 import 它，模块级 `exit()` 在收集阶段触发 INTERNALERROR，杀死整个测试套件。
2. 脚本式测试必须：
   - **改名**为非 pytest 收集名（如 `test_staleness_guard.py` → `staleness_guard_check.py`），或
   - **加收集守卫**：把顶层执行包进 `if __name__ == "__main__":`，并保留 `test_*` 命名时提供至少一个纯 pytest 用例入口（不调用 exit）。
3. `exit()` / `sys.exit()` 只允许出现在 `__name__ == "__main__"` 块或 `if __name__ == "__main__":` 保护下的函数内。

### 3.3 反例与正例

```python
# ❌ 禁止（收集阶段 INTERNALERROR）—— tests/test_foo_script.py
import sys
print("run check...")
sys.exit(0)

# ✅ 正例 A：改名，pytest 不收集，独立运行不受影响
# tests/foo_script_check.py（原 test_foo_script.py）
import sys
print("run check...")
sys.exit(0)

# ✅ 正例 B：保持 test_ 前缀 + __main__ 守卫（pytest 收集安全）
# tests/test_foo_script.py
def test_placeholder():
    """pytest 收集入口；脚本式逻辑走 __main__。"""
    assert True

if __name__ == "__main__":
    import sys
    print("run check...")
    sys.exit(0)
```

---

## 4. 验收扫描命令

以下命令用于确认/预防"硬编码污染"与"收集杀死"复发，**新卡提交前必须跑通，残留数必须为 0**：

```bash
# 扫描 1：sys.path 硬编码污染（必须 0 残留）
grep -rn 'sys.path.insert(0, "/workspace/devPPL")' tests/

# 扫描 2：模块级 exit() 的 test_ 文件（必须 0 残留）
grep -rn '^exit(' tests/ --include='test_*.py'

# 补充扫描（研发自查用，非门禁）：
#   - sys.path.insert 所有出现点应基于 __file__ 相对
grep -rn 'sys.path.insert' tests/
#   - 任何 exit( 出现点应位于 __main__ 块或函数内
grep -rn 'exit(' tests/ --include='test_*.py'
```

**验收门禁**：全量 pytest 必须能完整跑完（无 INTERNALERROR）。若遇 INTERNALERROR，先按本文档 §3 检查是否有模块级 exit/无限循环的 test_ 文件。

---

## 5. 存量债务清单（非阻断，逐步清理）

DPL-057 扫描确认：两条门禁扫描（§4 扫描 1/2）均已 0 残留。以下为**非 import 类**硬编码绝对路径存量，不影响 import 缓存与 pytest 收集，不阻断验收，但应在后续 FIX 卡中逐步改为 `__file__` 相对（DPL-057 登记，2026-08-15）：

| 文件 | 行号 | 内容 | 类别 |
|------|------|------|------|
| tests/slice2_integration.py | 17 | `contract_path = '/workspace/devPPL/config/contracts.jsonl'` | 资源路径 |
| tests/test_slice2_d1_qa.py | 33 | `CONTRACT_PATH = '/workspace/devPPL/config/contracts.jsonl'` | 资源路径 |
| tests/test_P2-02_full.py | 353 | `report_path = "/workspace/devPPL/tests/results_P2-02.json"` | 输出路径 |
| tests/test_dpl056_chain_gate.py | 236 | `workspace_path="/workspace/devPPL"` | 用例参数（验证固定路径行为，可保留） |
| tests/test_slice3_d1_qa.py | 836 | `_os.environ.get("HERMES_KANBAN_WORKSPACE", "/workspace/devPPL")` | 环境回退（例外模式） |
| tests/test_slice3_d1_qa.py | 1068/1092/1189 | `autopilot_path = Path("/workspace/devPPL/scripts/autopilot.sh")` | 资源路径 |
| tests/test_slice3_d1_qa.py | 1253/1287 | `db_path = "/workspace/devPPL/pipeline_state.db"` | 资源路径 |

> 说明：上表仅登记存量，不构成本卡改动范围。清理时注意区分"验证固定路径行为的用例"（保留并注释）与"资源访问路径"（改 `__file__` 相对）。

---

## 版本历史

| 版本 | 日期 | 变更 | 作者 |
|------|------|------|------|
| v1.0 | 2026-08-15 | 初版：登记 DPL-057 事故复盘、R1/R2 规则、验收扫描命令、存量债务清单 | 研发（寇豆码） |

<!-- 参考：OC 排查 comment t_49ce4679 #1569；修复 commit 12eb90a + cee5d6b + 9daa839；DPL-057 t_f8d25717 -->
