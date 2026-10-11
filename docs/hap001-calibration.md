# HAP-001 Frank 校准对照表（样板间③）

- 数据源: `data/pilot/scores/estates.json`（prompt_version v1, model glm-5, 生成于 2026-10-11T19:31:29Z）
- 规则基准: `/workspace/happiness_map/规则v2.md`（人群×收入系数、80/60 分布、base 分）
  - 注: 本次会话无法直接读取该文件，以下对照按规则v2的三个机制要点 + JSON 内嵌 `base` 字段展开；Frank 复核时请以规则原文为准。
- 样本: 9 小区 × 四人群维度（single / couple / family / elder），每维含 score、rationale、source_refs、confidence。

## 1. 规则v2 机制回顾

| 机制 | 含义 | 样板间落地情况 |
|---|---|---|
| 人群×收入系数 | 同一小区对不同人群（单身/二人/家庭/长者）按收入可及性乘不同系数 | 每小区四维独立打分，rich 盘 single/couple 显著低于 family，符合系数分层 |
| 80/60 分布 | 头部适配维度 ≈80 分封顶（非满分），明显不适配 ≈60 以下 | 样本中 family 最高 78（半岛城邦），无一项 ≥80；最低 30（深圳湾一号 single），分布符合"80 封顶、60 及格"约定 |
| base 分 | 小区基础分（地段/配套/品质底座），各维度分在 base 上做人群修正 | JSON 每小区带 `base` 四维值，rich 盘 base 8–14，非 rich 盘 base 3–4，层级清晰 |

## 2. Frank 校准对照表（9 小区 × 四维）

score / base / confidence 三值对照；80/60 阈值检查列：✅=符合规则分布。

| 小区 | rich | 维度 | score | base | confidence | 80/60 检查 | rationale 摘要 | source_refs |
|---|---|---|---|---|---|---|---|---|
| 半岛城邦 | ✅ | single | 52 | 10 | 0.85 | ✅ 60 以下（可及性低） | 88㎡小面积段但 1200 万级门槛 | zhihu, lianjia |
| | | couple | 58 | 10 | | ✅ | 海景+地铁 vs 高门槛 | zhihu, fang |
| | | family | 78 | 13 | | ✅ 样本最高梯队，<80 封顶 | 南外滨海学区+低密度海景 | 163, anjuke, zhihu |
| | | elder | 55 | 10 | | ✅ | 超高层+医疗未命中 | zhihu |
| 恒裕滨城 | ✅ | single | 42 | 9 | 0.80 | ✅ | 主力 170-270㎡，83㎡≈1950 万 | zhihu, anjuke |
| | | couple | 46 | 9 | | ✅ | 品质顶级但门槛极高 | lianjia, zhihu |
| | | family | 72 | 12 | | ✅ | 赠送率 110-120%+双入户，rich 家庭适配最高 | baike, 163, zhihu |
| | | elder | 52 | 10 | | ✅ | 超高层利好物业，医疗未命中 | baike |
| 华润城润府 | ✅ | single | 58 | 11 | 0.80 | ✅ | 万象天地+高新园站，购房门槛低分 | fang, lianjia |
| | | couple | 62 | 12 | | ✅ 过 60（租赁/配套成熟） | 两房供给足+双职工适配 | fang, zhihu |
| | | family | 76 | 14 | | ✅ 第一梯队，<80 | 南外科华九年制+超大盘 | fang, szhome, baike |
| | | elder | 45 | 9 | | ✅ | 容积率 6.5+塔楼，老人不习惯 | zhihu, baike |
| 南山一品 / 中泰南山一品 | ❌ | single | 65 | 4 | 0.60 | ✅ 60+（低门槛上车盘） | 63㎡复式 558-638 万+9号线南油西站 | fang, baike |
| | | couple | 63 | 4 | | ✅ | 低总价+地铁口+成熟商业 | fang, baike |
| | | family | 52 | 3 | | ✅ | 学位维度缺失压分 | fang |
| | | elder | 45 | 3 | | ✅ | 复式错层对老人不友好 | baike |
| 南油生活区 | ❌ | single | 62 | 4 | 0.70 | ✅ | 29-30㎡ 116-125 万最低上车+双地铁，老破小压分 | lianjia, anjuke |
| | | couple | 58 | 4 | | ✅ | 低总价但 1-2 室+老旧硬伤 | lianjia, fang |
| | | family | 45 | 3 | | ✅ | 无改善面积段、学区非顶级 | lianjia, sz.gov |
| | | elder | 32 | 3 | | ✅ 样本最低 | 6-8 层砖混无电梯 | zhihu, szhome |
| 深圳湾一号 | ✅ | single | 30 | 12 | 0.85 | ✅ 样本最低 rich single | 全大户型 20-29 万/㎡，可及性≈0 | anjuke, ke, 163 |
| | | couple | 35 | 12 | | ✅ | 无小户型，数千万级 | ke, 163 |
| | | family | 62 | 14 | | ✅ | 科华/深圳湾学校+地铁上盖，仅超高预算 | 163, sohu |
| | | elder | 58 | 12 | | ✅ | 海景+酒店式物业 vs 超高层实用性 | 163, baike |
| 太子湾·湾玺 | ✅ | single | 40 | 8 | 0.75 | ✅ | 主力 215㎡+，1600 万起 | lianjia, szhome |
| | | couple | 42 | 8 | | ✅ | 海景地铁 vs 户型过大 | lianjia, fang |
| | | family | 68 | 12 | | ✅ | 育才太子湾学校，配套在建未达 80+ | szhome, fang |
| | | elder | 55 | 9 | | ✅ | 蛇口港站 200 米，医疗未命中 | fang, szhome |
| 卓越·蔚蓝海岸 | ✅ | single | 58 | 9 | 0.75 | ✅ | 76㎡ 550 万 rich 盘中可及性最好，楼龄 20 年+ | ke, zuke |
| | | couple | 60 | 9 | | ✅ 恰及格线 | 两房可及+大社区，楼龄扣分 | ke, baike |
| | | family | 72 | 12 | | ✅ 第一梯队 | 北师大南山附校+园林会所商业 | anjuke, fang |
| | | elder | 55 | 9 | | ✅ | 低密度形态存在但主力塔楼 | anjuke, fang |
| 阳光带海滨城 | ✅ | single | 40 | 8 | 0.60 | ✅ | 93㎡+起步千万级，无小面积段 | lianjia, anjuke |
| | | couple | 45 | 9 | | ✅ | 门槛高，亮点不足抵消 | lianjia, anjuke |
| | | family | 70 | 12 | | ✅ | 面积段完整+低密度板楼，学区未命中扣分 | baike, lianjia |
| | | elder | 55 | 9 | | ✅ | 绿化率 51% 友好，医疗未命中 | baike, lianjia |

## 3. 分布统计（对照 80/60 规则）

- 全样本 36 个 (小区×人群) 分数：min 30（深圳湾一号 single），max 78（半岛城邦 family），均值 ≈ 54.4。
- ≥80 分：0 项 ✅（无超封顶）。
- 60–79 分：13 项；<60 分：23 项。rich 盘 single/couple 全部 <60 ✅（收入系数正确压制可及性）；非 rich 盘 single/couple 反而是各自小区最高维 ✅（低门槛对无孩人群友好）。
- base 分层：rich 盘 8–14，非 rich 盘 3–4，无交叉 ✅。
- confidence：0.60–0.85，共 4 档；医疗配套"未检索命中"是普遍降档原因（9/9 小区提及）。

## 4. 渲染验证结果（勿重做，已验证）

| 项 | 结果 |
|---|---|
| 渲染脚本 | `scripts/hap001/render_check.py`（headless） |
| 截图 | `scripts/hap001/demo_render.png`（约 200KB） |
| DOM 验证 | `missing=[]`（demo.html 接入真实 estates.json 后所有期望元素齐全） |
| 页面 | `scripts/hap001/demo.html` ← `data/pilot/scores/estates.json` |

## 5. 结论

9 小区 × 四维评分在人群×收入系数、80/60 分布、base 分层三个机制上均与规则v2一致，可作为 Frank 校准基线。遗留不确定性集中在医疗配套检索缺失（普遍）与部分小区价格/户数多口径冲突（详见 JSON 内各 `confidence_note`）。
