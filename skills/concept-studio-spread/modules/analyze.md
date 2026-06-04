---
name: "concept-analyze"
description: "概念库关联分析——扫描概念页之间的 [[]] 链接，识别孤立概念和集群，增量更新 concept_relations.md。用户说「跑一下关联分析」「更新图谱」「concept-analyze」时触发。"
---

# Concept Analyze · 概念关联分析

概念页目录：`{ROOT}/概念页/`
关联图谱：`{ROOT}/memory/concept_relations.md`
轻量索引：`{ROOT}/memory/concept_lite.json`
图结构索引：`{ROOT}/memory/concept_graph.json`
管理索引：`{ROOT}/memory/concept_meta.json`（可选）

---

## 索引优先原则

关联分析需要读取轻量索引 + 图结构索引两个文件（按需可选管理索引）。

新增/修改概念页后，运行 `python3 {ROOT}/scripts/build_index.py --root {ROOT} --incremental` 刷新索引。
如果脚本不存在，提示用户需要手动维护索引或配置脚本。

> **首次使用？** 如果索引文件不存在，自动切换为全量模式并从概念页目录扫描生成初始数据。

## 两种模式

**增量模式**（默认，用户说「更新」「跑一下」）
- 对比 `concept_meta.json` 的 `meta.last_built` 和 `concept_relations.md` 的 `last_analysis`
- 只处理上次分析后新增的概念页
- 更新孤立概念列表、集群归属、断链记录

**全量模式**（用户说「全量重跑」「重建基准」）
- 先运行 `python3 {ROOT}/scripts/build_index.py --root {ROOT}` 重建索引（如脚本存在）
- 从索引读取全部数据，重建集群结构和孤立节点列表

---

## 执行步骤

### Step 1 — 确定扫描范围

读取 `{ROOT}/memory/concept_lite.json` 和 `{ROOT}/memory/concept_graph.json`。
需要文件路径/来源/日期时可选读取 `{ROOT}/memory/concept_meta.json`。

合并两个分片的 nodes 数据为完整视图：
```
nodes[name] = {**lite['nodes_lite'][name], **graph['nodes_graph'].get(name, {}), **meta['nodes_meta'].get(name, {})}
```

**任一分片找不到时**：检查路径是否正确，索引文件固定在 `{ROOT}/memory/` 下。

**首次运行（无 `last_analysis` 字段）**：自动切换为全量模式。

增量：对比 `meta.last_built`（从 concept_meta.json 读取）和上次分析日期（`concept_relations.md` 的 `last_analysis` 字段）。如果索引已包含最新数据，直接从分片读取；否则先运行 `build_index.py --incremental`。
全量：确保索引是最新（运行 `build_index.py`），然后从分片读取所有数据。

### Step 2 — 提取链接关系

直接从分片读取：
- 合并后 `nodes[name].out_links` = 出链列表（来自 graph 分片）
- 合并后 `nodes[name].in_links` = 入链列表（来自 graph 分片）
- `graph['edges']` = 全量边列表
- `graph['broken_links']` = 断链列表（已在索引中预计算）

无需逐文件读取。

### Step 3 — 识别孤立概念

直接从轻量索引读取 `orphan_nodes`：
- `fully_isolated` = 完全孤立（0 入 0 出）
- `semi_isolated` = 半孤立（有入链无出链）

### Step 4 — 集群分析

读取图结构索引中的 `clusters`（从 concept_relations.md 加载）。
对新增概念：
- 判断它是否属于某个已有集群。判断维度（满足2条即可建议加入）：①核心机制与集群内概念属于同一理论传统（如都是社会心理学中的认知偏差）②已有集群内概念通过 [[]] 链接到它③它的 domain + discipline 与集群内概念高度重叠
- 如果属于，建议加入该集群，并说明理由
- 如果不属于任何集群，标记为「待归类」

不自动修改集群定义，输出建议后等用户确认：

```
集群归属建议（N 个，需确认）：

1. 「{概念名}」→ 建议加入集群 {集群名}
   理由：{一句话}
   确认加入？（是/否）

2. 「{概念名}」→ 待归类（暂无匹配集群）
```

用户逐条回应后，只把「是」的条目写入 Step 5。

### Step 5 — Apply 分析

从轻量索引读取 `apply_index`，报告孤立概念在 apply 域的聚集情况，标记接入机会。不硬写，只输出建议。

### Step 6 — 更新 concept_relations.md

更新 `{ROOT}/memory/concept_relations.md` 中的以下内容：
- `last_analysis` 日期（用 `date` 命令获取当前日期）
- `concept_count` 总数
- `orphan_count` 孤立概念数
- 孤立概念列表（如有变化）
- 集群建议（新增「待确认」条目，不直接修改已有集群）
- Apply 分析结果

**不删除已有的「已解决」记录，只追加新内容。**

### Step 7 — 刷新索引

运行 `python3 {ROOT}/scripts/build_index.py --root {ROOT} --incremental`，确保索引与最新 concept_relations.md 同步。
如果脚本不存在，跳过此步并提示用户。

### Step 8 — 输出摘要

```
本轮分析完成（增量/全量）

扫描概念数：N
新增断链：X 条
新增孤立概念：Y 个
集群归属建议：Z 个（需确认）
Apply 接入机会：W 个

concept_relations.md 已更新。
索引已刷新。
```

---

## 原则

- 只分析 `[[]]` 链接，不分析语义相似度
- 集群归属建议需用户确认，不自动写入集群定义
- 断链只记录，不自动修复（修复由摄入模块或用户手动处理）
- Apply 分析只报告，不硬写链接
