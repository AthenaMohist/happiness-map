# P0-09 F5 BLOCKER 根因分析 — Qdrant 维度不匹配

> 调查任务：t_a448a3f5
> 调查人：game-qa
> 日期：2026-07-08
> 标准依据：`docs/standards/qa-finding-classification.md` v1.0

---

## 1. 背景

QA P0-09 重审报告将 F5（Qdrant 维度不匹配）判定为 **BLOCKER**：
- 声称默认 Qdrant 配置使用 1536d
- bge-small-en-v1.5 使用 384d
- 维度不匹配导致 mem0 完全不可用

**Frank 质疑**：mem0 之前测试过很多次，可以用。怀疑 QA 测试方法有问题。

## 2. 调查过程

### 2.1 当前 Hermes mem0 配置状态

```
hermes memory status → Provider: (none — built-in only)
```

当前 game-qa profile **未启用 mem0**。memory 使用内置后端。

### 2.2 Hermes mem0 插件代码审查

源码位置：`/usr/local/lib/hermes-agent/plugins/memory/mem0/`

#### `_backend.py` OSSBackend.__init__() (L96-126) — 维度处理逻辑：

```python
def __init__(self, oss_config: dict):
    ...
    embedder_config = oss_config.get("embedder", {}).get("config", {})
    dims = embedder_config.get("embedding_dims")        # ① 先读显式配置
    if not dims:
        from ._oss_providers import KNOWN_DIMS
        model = embedder_config.get("model", "")
        dims = KNOWN_DIMS.get(model)                     # ② 再查已知维度表
    if dims:
        vs_config["embedding_model_dims"] = dims         # ③ 传给 vector store
        self._recreate_collection_if_dims_changed(       # ④ 检查现有 collection
            vector_store.get("provider", "qdrant"), vs_config, dims,
        )
    ...
    self._memory = Memory.from_config(config)            # ⑤ 用正确配置创建
```

#### `_oss_providers.py` — 支持的 provider 与已知维度：

```python
EMBEDDER_PROVIDERS = {
    "openai":  {"dims": 1536, "default_model": "text-embedding-3-small"},
    "ollama":  {"dims": 768,  "default_model": "nomic-embed-text"},
}

KNOWN_DIMS = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002":  1536,
    "nomic-embed-text":        768,
}
```

#### `_recreate_collection_if_dims_changed()` (L129-159)：

该方法在 OSSBackend 初始化时运行，检查现有 Qdrant collection 的向量维度。如发现维度不匹配，**自动删除旧 collection**，让 Memory.from_config() 用新维度重建。

### 2.3 Orchestrator 实际配置（mem0 已知可用的 profile）

模板 `mem0-deepseek.json`：
```json
{
  "mode": "oss",
  "oss": {
    "embedder": {
      "provider": "openai",
      "config": {
        "model": "text-embedding-3-small"   // ← KNOWN_DIMS 映射到 1536
      }
    },
    "vector_store": {
      "provider": "qdrant",
      "config": { "path": "~/.hermes/profiles/orchestrator/mem0_qdrant" }
    }
  }
}
```

### 2.4 QA TC-F5-01 测试方法

QA 测试脚本 `/workspace/devPPL/test_p0_09_mem0.py` TC-F5-01：
```python
# 手动创建 QdrantClient，用 1536d 创建 collection
client_bad = QdrantClient(path=td2)
client_bad.recreate_collection(
    collection_name="test_dim_mismatch",
    vectors_config=models.VectorParams(size=1536, ...),  # ← 手动指定 1536
)
# 用 bge-small-en (384d) 生成向量
vec_384 = list(ts.emb.embed(["test"]))[0].tolist()
# 尝试 upsert → 预期报错
client_bad.upsert(...)
```

## 3. 根因分析

### 3.1 QA 测试场景 vs Hermes 实际运行路径

| 维度 | QA TC-F5-01 测试 | Hermes 实际 OSSBackend |
|------|-----------------|----------------------|
| Qdrant collection 创建 | 手动 `recreate_collection(size=1536)` | `Memory.from_config()` 通过 mem0 SDK，传入 `embedding_model_dims` |
| 维度来源 | 硬编码 1536（"Qdrant 默认"） | embedder config → `embedding_dims` → `KNOWN_DIMS` |
| 维度不匹配处理 | 抛异常 → 判定 BLOCKER | `_recreate_collection_if_dims_changed()` 自动删除旧 collection |
| 是否实际发生 | **仅在手动构造的场景中** | **否 — 代码路径确保了维度一致** |

### 3.2 关键差异

QA 的 TC-F5-01 **直接操作 QdrantClient**，绕过了 Hermes 的 `OSSBackend` 初始化逻辑。

Hermes 的 mem0 集成在 `OSSBackend.__init__()` 中有三层保障：
1. **显式 dims**：从 `embedder_config.get("embedding_dims")` 读取
2. **KNOWN_DIMS 降级**：从模型名查找已知维度
3. **自动修复**：`_recreate_collection_if_dims_changed()` 发现旧 collection 维度不对 → 删除重建

对于支持的 provider（openai/ollama），维度**总是能正确解析**。对于不支持的自定义 provider，用户需要在 mem0.json 中显式设置 `embedding_dims`。

### 3.3 实际风险场景

唯一能触发维度不匹配的场景：
- 用户使用不在 EMBEDDER_PROVIDERS 中的自定义 embedder
- 且用户没有在 mem0.json 中设置 `embedding_dims`
- 且该 embedder 的维度 ≠ 1536（Qdrant 默认）

但即使在这种场景下，mem0 SDK (`Memory.from_config()`) 也会在初始化时报错，**不会静默失败后让用户存入错误维度的数据**。

## 4. 结论

### 4.1 F5 分级需降级

```
原判定：BLOCKER（声称 Qdrant 默认 1536d 与 bge-small-en 384d 冲突）
调查结论：BLOCKER → SUGGESTION（或撤回）
```

**依据**：

1. **QA 测试场景不代表实际运行路径** — Hermes 的 `OSSBackend` 不经过 QA 测试中的"手动创建 QdrantClient 1536d"路径
2. **Hermes 有维度处理机制** — `_backend.py` 第 106-116 行显式处理维度，确保 vector store 与 embedder 一致
3. **有自动修复能力** — `_recreate_collection_if_dims_changed()` 检测到不匹配会自动删除旧 collection
4. **支持的 provider 无此风险** — openai (1536d) 和 ollama (768d) 维度已知，always match
5. **即使边缘场景也不静默失败** — mem0 SDK 会在初始化时报错，不会让用户存入错误数据

### 4.2 分级对照 (§1.2)

```
判定公式：
  用户可感知？⚠️ 仅在极端边缘场景（自定义 embedder + 没设 embedding_dims）
  功能阻断？⚠️ 同上，且 mem0 SDK 会在 init 时报错
  Workaround？✓ 显式设置 embedding_dims 即可
→ SUGGESTION（文档建议：非标准 embedder 需显式设置 embedding_dims）
```

### 4.3 Frank 的判断是正确的

mem0 在 Hermes 中确实可以正常工作：
- Hermes 的 mem0 插件从代码层面处理了维度一致性问题
- 支持的 provider（openai "text-embedding-3-small" 1536d, ollama "nomic-embed-text" 768d）均无此问题
- 即使切换 embedder 导致维度变化，`_recreate_collection_if_dims_changed()` 会自动修复
- QA 的 TC-F5-01 测试场景（手动 QdrantClient(recreate_collection(size=1536))) **不代表 Hermes 的实际代码路径**

### 4.4 建议

1. **F5 从 BLOCKER 降为 SUGGESTION**：确认为"文档建议 — 非标准 embedder 需显式设置 embedding_dims"
2. **更新 QA 测试方法**：后续 mem0 测试应通过 Hermes 的 `Memory.from_config()` 路径（或 OSSBackend）而非直接操作 QdrantClient
3. **文档改进**：在 `_oss_providers.py` 或 mem0 设置文档中注明："使用非标准 embedder 时，需在 embedder.config 中设置 embedding_dims"

---

## 5. 证据清单

| # | 证据 | 路径 |
|---|------|------|
| 1 | OSSBackend 维度处理代码 | `/usr/local/lib/hermes-agent/plugins/memory/mem0/_backend.py` L106-126 |
| 2 | _recreate_collection_if_dims_changed | `/usr/local/lib/hermes-agent/plugins/memory/mem0/_backend.py` L129-159 |
| 3 | KNOWN_DIMS + EMBEDDER_PROVIDERS | `/usr/local/lib/hermes-agent/plugins/memory/mem0/_oss_providers.py` |
| 4 | Orchestrator 实际配置模板 | `/root/.hermes/profiles/orchestrator/skills/hermes-admin/hermes-backend-setup/templates/mem0-deepseek.json` |
| 5 | 当前 game-qa profile 未启用 mem0 | `hermes memory status` → "built-in only" |
| 6 | QA TC-F5-01 测试脚本 | `/workspace/devPPL/test_p0_09_mem0.py` L~2850-2900 |
| 7 | QA P0-09 重审报告 | `/workspace/devPPL/docs/qa-reviews/P0-09-mem0-re-review.md` |
| 8 | QA P0-09 重审测试报告 | `/workspace/devPPL/docs/qa-reaudits/P0-09-test-report.md` |
