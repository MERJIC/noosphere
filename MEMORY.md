# MEMORY.md — 概念库

## 索引
- **SQLite 索引层**（`memory/concepts.db`）— 结构化查询主入口，每新增/修改概念页后必须同步
- [概念库总索引](概念页/INDEX.md) — Dataview 自动维护，新增概念无需更新此文件
- [设计原则与背景](memory/workflow_obsidian_concepts.md) — 概念库的架构哲学、知识来源闭环、虚链接策略
- [概念关联图谱](memory/concept_relations.md) — 集群分析、孤立概念、待处理问题，由 concept-analyze 自动维护

---

## 规范权威

**概念页格式规范（字段、正文结构、自检规则、写作规范）以 `个人总部/skills/concept-studio/` 为唯一权威。** 本文件不再重复记录规范细节，避免版本冲突。

每次写概念页前，参照 concept-studio 对应模块的规范执行。词汇表也以 skill 文件中的为准。

---

## 行为规则

**概念库查阅**
- **禁止手动读取 INDEX.md**。INDEX.md 是 Noosphere 插件的自动产物，不是给 AI 翻的目录
- 结构化查询（跨字段筛选、关联分析、断链检测）：`python3 scripts/sync_db.py --query "SQL"` 或 `--preset 预设名`
- 统计摘要：`python3 scripts/sync_db.py --stats`
- 查库存（快速 grep）：用 Grep 搜概念页目录
- 查集群和关联关系：读 concept_relations.md 或 `--preset clusters-detail`

**索引维护（两步，缺一不可）**
1. 新增/修改概念页后，**必须**运行 `python3 scripts/sync_db.py --incremental` 同步到 SQLite
2. 同时运行 `python3 scripts/build_index.py --incremental` 刷新 JSON 索引（供查重等脚本使用）
- 单个概念可简化为：`python3 scripts/sync_db.py --file 概念名`

**项目级变更**
- 对工作流、规范、skill 做全局性变更时，在 concept-studio 的模块文件中修改，不在这份 MEMORY.md 中维护副本
