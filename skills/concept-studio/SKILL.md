---
name: "concept-studio"
description: >
  概念库统一工作台——麦橘概念库的全流程入口。
  覆盖：寓言故事（被动学习，含圆桌）、摄入（从 URL/文本建概念页）、跳跃（从已有概念向外探索新概念）、关联分析（更新图谱）、知识卡片（转小红书）。
  触发词：「寓言故事」「讲个故事」「摄入」「ingest」「沉淀这个」「跳一跳」「漫游」「关联分析」「更新图谱」「知识卡片」「做成卡片」「传播版」「发到小红书」
---

# Concept Studio · 概念库工作台

## 固定路径

所有文件都在固定位置，找不到就是路径写错了，检查后重试。不要乱翻、不要猜路径。

| 资源 | 路径 |
|------|------|
| 概念页目录 | `/Users/myke/Documents/MERJIC/概念库/概念页/` |
| 概念页规范（唯一权威） | `modules/page-spec.md`（写概念页时参照，写完后用「自检清单」质检。Noosphere 插件也从这里读取词汇表，不维护硬编码副本） |
| 学者名对照表 | `modules/scholar-dict.json`（Noosphere 插件读取，用于自动检查学者名首现中英文标注） |
| **SQLite 索引层**（主入口，查询/查重/统计全走这里） | `/Users/myke/Documents/MERJIC/概念库/memory/concepts.db` |
| 同步脚本（SQLite + JSON 索引一体化） | `/Users/myke/Documents/MERJIC/概念库/scripts/sync_db.py` |
| JSON 索引分片（供 check_duplicate.py 等旧脚本使用，逐步淘汰中） | `memory/concept_lite.json` / `concept_graph.json` / `concept_meta.json` |
| 关联图谱 | `/Users/myke/Documents/MERJIC/概念库/memory/concept_relations.md` |
| Noosphere 插件源码 | `/Users/myke/Documents/MERJIC/概念库/概念页/.obsidian/plugins/noosphere/` |

---

## 意图识别 → 路由

收到请求后，先判断意图，读取对应 module，再执行。

| 用户说 | 路由到 |
|--------|--------|
| 「讲个寓言」「寓言故事」「讲个故事」「想听个故事」「寓言」 | 读 `modules/parable.md`，正常流程 |
| 「圆桌」「圆桌讨论」「roundtable」「辩论」「多角度」+ 具体议题 | 读 `modules/parable.md`，跳过故事直接执行 Step 6（直接圆桌模式） |
| 「摄入」「ingest」「沉淀这个」「存进概念库」「这个值得记」「从这个 URL」「粘贴内容」 | 读 `modules/ingest.md` |
| 「跳一跳」「漫游」「给我新的」「举一反三」「从孤立节点」「随便」 | 读 `modules/hop.md` |
| 「关联分析」「更新图谱」「concept-analyze」「跑一下」「增量」「全量重跑」 | 读 `modules/analyze.md` |
| 「知识卡片」「做成卡片」「传播版」「可传播格式」「小红书卡片」「发到小红书」「知识图文」 | 读 `modules/cards.md` |

**有歧义时直接问：**
```
你想做哪个？
A. 寓言故事（被动学习，含圆桌）
B. 圆桌讨论（直接发起，不需要故事）
C. 摄入新概念（从 URL 或文字）
D. 向外探索新概念（概念跳跃）
E. 更新关联图谱
F. 输出知识卡片
```

每次执行只激活一个 module，不混用。
