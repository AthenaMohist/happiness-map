# GATE_Q5_WHITELIST — Q5 发验一致性门禁白名单规范（DPL-195）

> 真源: [[arch-dpl195-registry-single-source-numbering]] §1.3/§6-D6
> 消费方: `devPPL/scripts/gate_code_4q.sh`（Q5 段，仅 `--pre` 建链预检启用）

## 定义

- **env 名**: `GATE_Q5_WHITELIST`
- **值格式**: 逗号分隔的 `CODE-NNN` 列表（大小写不敏感，忽略空白），如：
  `GATE_Q5_WHITELIST="DPL-196,DPL-197"`
- **空 / 未设置** = 无任何豁免（Q5 全量生效）。

## 语义

Q5 = 发号器 `next_hint` 与验号收到的 CODE 一致性比对。命中白名单的编号
**豁免 Q5 漂移判定**（仍照常过 Q1/Q2/Q3/Q4），适用且仅适用两类场景：

1. **修补链继承号**：修一条历史链时继承其原编号（≠ next_hint），属合法回写。
2. **OC 显式换号**：OC 裁定跳号/换号后，REGISTRY `next` 行尚未推进的过渡窗口。

白名单**不是**绕过撞号/作废的后门——Q2/Q3 在 Q5 之前独立判定，永不豁免。

## 生命周期约定

- 白名单是**过渡态豁免**：REGISTRY `next` 行对齐（或修补链落链）后应从列表移除。
- 仅卡 `--pre` 建链入口；非 `--pre` 模式 Q5 不启用，白名单自然无效。

## 使用示例

```bash
# 修补 DPL-186 历史链（继承号 ≠ 当前应发号）
GATE_Q5_WHITELIST="DPL-186" bash scripts/gate_code_4q.sh --pre DPL-186

# 无豁免（默认）：发号器应发 DPL-195，收到别的号即 exit 7
bash scripts/gate_code_4q.sh --pre DPL-196
# → [Q5-fail] 发号器当前应发 DPL-195，验号收到的却是 DPL-196——…
```
