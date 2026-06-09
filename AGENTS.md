# 概念库

遵循全局 AGENTS.md 的通用规则（称呼、语言、交互风格），以下为本项目补充。

## 每次对话必读

对话开始时，读取根目录 `MEMORY.md`——词汇表、行为规则、概念库设计原则全部在里面，不读不开工。

**概念页格式规范、自检规则、写作规范以 `skills/concept-studio/` 为唯一权威。** 本项目不再重复记录规范细节。

---

## 目录结构

- `概念页/` — 全部概念 .md 文件 + INDEX.md（Dataview 自动索引），可单独作为 Obsidian vault 打开
- `memory/` — MEMORY.md（规则索引 + 设计原则）+ concept_relations.md（关联图谱）+ **concepts.db**（SQLite 索引层）
- `scripts/` — sync_db.py（SQLite 同步）+ build_index.py（JSON 索引）+ lint_concepts.py（质检）+ check_duplicate.py（查重）
- `skills/concept-studio/` — 概念库工作台 skill（与数据目录同项目，路径自洽）
- `AGENTS.md` — 本项目入口指令

这是麦橘的个人知识资产库，用 Obsidian 管理。存放跨领域的概念沉淀，供长期积累和检索使用。

## RTK — 本项目常用命令

所有 Bash 命令加 `rtk` 前缀。本项目高频命令：

```bash
# SQLite 同步（每新增/修改概念后必须执行）
rtk python3 scripts/sync_db.py --incremental               # 增量同步（日常首选，~10ms）
rtk python3 scripts/sync_db.py --file 概念名               # 单个概念同步
rtk python3 scripts/sync_db.py --stats                     # 统计摘要
rtk python3 scripts/sync_db.py --check                     # 一致性校验
rtk python3 scripts/sync_db.py --query "SELECT ..."        # 自定义 SQL 查询
rtk python3 scripts/sync_db.py --preset orphans            # 预设查询（orphans/broken/recent/...）

# JSON 索引刷新（供查重脚本使用，与 sync_db 互补）
rtk python3 scripts/build_index.py --incremental

# lint 质检
rtk python3 scripts/lint_concepts.py --file 概念名
rtk python3 scripts/lint_concepts.py                      # 全量质检

# 文件操作
rtk ls 概念页/
rtk grep "关键词" 概念页/
```

## 关联 Skill（本项目，skills/concept-studio/）

概念库的完整工作流统一由 concept-studio 管理，包含以下模块：
- parable — 寓言故事写概念
- roundtable — 多视角圆桌讨论
- ingest — 概念摄入
- hop — 概念跳跃
- analyze — 关联分析
- cards — 知识卡片传播
- parable-rewrite — 寓言重写

