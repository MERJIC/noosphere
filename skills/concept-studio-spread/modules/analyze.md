---
name: "concept-analyze"
description: "概念库关联分析——扫描概念页之间的 [[]] 链接，识别孤立概念和集群，增量更新 concept_relations.md。用户说「跑一下关联分析」「更新图谱」「concept-analyze」时触发。"
---

# Concept Analyze · 概念关联分析

概念库路径：`{ROOT}/概念页/`
关联图谱：`{ROOT}/memory/concept_relations.db`（SQLite）
脚本：`{ROOT}/scripts/sync_db.py`

---

## 索引优先原则

所有数据查询通过 SQLite 执行，**禁止读取** concept_lite.json、concept_graph.json、concept_meta.json、INDEX.md 或任何 JSON 索引文件。

```bash
# 基础统计
python3 scripts/sync_db.py --stats

# 孤立概念
python3 scripts/sync_db.py --preset orphans

# 断链列表
python3 scripts/sync_db.py --preset broken

# 集群详情
python3 scripts/sync_db.py --preset clusters-detail

# 高连接度概念
python3 scripts/sync_db.py --preset highly-connected

# 自定义查询
python3 scripts/sync_db.py --query "SELECT ..."
```

新增/修改概念页后，运行 `python3 {ROOT}/scripts/sync_db.py --incremental` 即可同时刷新索引和 DB。

---

## 两种模式

**增量模式**（默认，用户说「更新」「跑一下」）
- 只处理上次分析后新增的概念
- 更新孤立概念列表、集群归属、断链记录

**全量模式**（用户说「全量重跑」「重建基准」）
- 从 DB 读取全部数据，重建集群结构和孤立节点列表

---

## 执行步骤

### Step 1 — 确定扫描范围

用 `--stats` 获取当前概念总数。

**增量判断**：从 DB 查询上次分析日期：
```bash
python3 scripts/sync_db.py --query "SELECT value FROM db_meta WHERE key = 'last_analysis'"
```

- 查不到（首次运行）：自动切换为全量模式
- 增量：如果 DB 已包含最新数据（`sync_db.py --incremental` 已跑过），直接用预设查询；否则先运行 `sync_db.py --incremental`

### Step 2 — 提取链接关系

从 DB 查询：
```sql
-- 出链 + 入链
SELECT s.name AS source, l.target_name, l.resolved, l.context
FROM links l JOIN concepts s ON s.id = l.source_id
ORDER BY s.name, l.target_name;

-- 断链
SELECT s.name AS source, l.target_name FROM links l
JOIN concepts s ON s.id = l.source_id WHERE l.resolved = 0;
```

无需逐文件读取。

### Step 3 — 识别孤立概念

直接用 `--preset orphans` 或：
```sql
SELECT name, name_en, domains, source FROM concepts c
WHERE NOT EXISTS (SELECT 1 FROM links WHERE source_id = c.id)
AND NOT EXISTS (SELECT 1 FROM links WHERE target_id = c.id);
```

### Step 4 — 集群分析

用 `--preset clusters-detail` 获取现有集群。

对新增概念（可通过 date 字段筛选最近新增的）：
- 判断它是否属于某个已有集群。判断维度（满足2条即可建议加入）：
  ① 核心机制与集群内概念属于同一理论传统
  ② 已有集群内概念通过 `[[]]` 链接到它
  ③ 它的 domain + discipline 与集群内概念高度重叠
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

从 DB 查询 apply 分布情况，报告孤立概念在 apply 域的聚集情况：
```sql
SELECT value, COUNT(*) FROM concepts, json_each(concepts.applies)
GROUP BY value ORDER BY COUNT(*) DESC;
```

标记接入机会。不硬写，只输出建议。

### Step 6 — 更新 concept_relations.md

更新 `{ROOT}/memory/concept_relations.md` 中的以下内容：
- `concept_count` 总数
- `orphan_count` 孤立概念数
- 孤立概念列表（如有变化）
- 集群建议（新增「待确认」条目，不直接修改已有集群）
- Apply 分析结果

**不删除已有的「已解决」记录，只追加新内容。**

同步更新 DB 中的 last_analysis：
```bash
python3 scripts/sync_db.py --set-meta last_analysis {date}
```

### Step 7 — 刷新索引

运行 `python3 {ROOT}/scripts/sync_db.py --incremental`（同时完成 SQLite 同步 + JSON 索引刷新）。

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
- 断链只记录，不自动修复（修复由 `concept-ingest` 或用户手动处理）
- Apply 分析只报告，不硬写链接
- **禁止读取任何 JSON 索引文件**，所有数据从 SQLite 查询获取
