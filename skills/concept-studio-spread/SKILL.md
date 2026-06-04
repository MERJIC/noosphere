---
name: "concept-studio-spread"
description: >
  概念库工作台·传播版——从 concept-studio 派生，去掉知识卡片模块，去除所有硬编码路径依赖。
  覆盖：寓言故事（被动学习，含圆桌）、摄入（从 URL/文本建概念页）、跳跃（从已有概念向外探索新概念）、关联分析（更新图谱）。
  触发词：「寓言故事」「讲个故事」「摄入」「ingest」「沉淀这个」「跳一跳」「漫游」「关联分析」「更新图谱」
config:
  concept_lib_root: "{ROOT}"
---

# Concept Studio Spread · 概念库工作台（传播版）

concept-studio 的开源传播版。去掉知识卡片（cards）模块和所有硬编码路径，改用配置驱动。

## 配置

使用前只需改一行：把下面 `config.concept_lib_root` 的 `{ROOT}` 替换为你的概念库根目录绝对路径。

**示例：**
```yaml
config:
  concept_lib_root: "/Users/yourname/Documents/my-concept-lib"
```

替换后，本 skill 所有模块自动使用该路径下的标准目录结构。

---

## 期望目录结构

你的概念库根目录下应有以下结构（没有的会自动创建）：

```
{ROOT}/
├── 概念页/              # 概念 .md 文件存放目录
├── memory/
│   ├── MEMORY.md        # 项目记忆文件
│   ├── concept_lite.json      # 轻量索引（概念名列表、孤立节点、别名）
│   ├── concept_graph.json     # 图结构索引（链接关系）
│   ├── concept_meta.json      # 管理索引（元数据）
│   └── concept_relations.md   # 关联图谱（集群、孤立节点记录）
├── scripts/
│   ├── build_index.py         # 索引构建脚本
│   ├── lint_concepts.py       # 概念页质检脚本（可选）
│   └── check_duplicate.py     # 查重脚本（可选）
└── roundtable/          # 圆桌讨论记录存放目录
```

> **首次使用？** 不需要预先创建任何文件。第一次执行「摄入」或「跳跃」时，skill 会引导你初始化索引。

---

## 意图识别 → 路由

收到请求后，先判断意图，读取对应 module，再执行。

| 用户说 | 路由到 |
|--------|--------|
| 「讲个寓言」「寓言故事」「讲个故事」「想听个故事」「寓言」 | 读 `modules/parable.md` |
| 「圆桌」「圆桌讨论」「roundtable」「辩论」「多角度」+ 具体议题 | 读 `modules/parable.md`，跳过故事直接执行 Step 6（直接圆桌模式） |
| 「摄入」「ingest」「沉淀这个」「存进概念库」「这个值得记」「从这个 URL」「粘贴内容」 | 读 `modules/ingest.md` |
| 「跳一跳」「漫游」「给我新的」「举一反三」「从孤立节点」「随便」 | 读 `modules/hop.md` |
| 「关联分析」「更新图谱」「concept-analyze」「跑一下」「增量」「全量重跑」 | 读 `modules/analyze.md` |

**有歧义时直接问：**
```
你想做哪个？
A. 寓言故事（被动学习，含圆桌）
B. 圆桌讨论（直接发起，不需要故事）
C. 摄入新概念（从 URL 或文字）
D. 向外探索新概念（概念跳跃）
E. 更新关联图谱
```

每次执行只激活一个 module，不混用。

---

## 路径解析规则

所有模块中的 `{ROOT}` 占位符在运行时替换为 `config.concept_lib_root` 的值。

常见路径映射：

| 占位符 | 实际路径 |
|--------|---------|
| `{ROOT}/概念页/` | 概念页 .md 文件目录 |
| `{ROOT}/memory/concept_lite.json` | 轻量索引 |
| `{ROOT}/memory/concept_graph.json` | 图结构索引 |
| `{ROOT}/memory/concept_meta.json` | 管理索引 |
| `{ROOT}/memory/concept_relations.md` | 关联图谱 |
| `{ROOT}/scripts/build_index.py` | 索引构建脚本 |
| `{ROOT}/scripts/lint_concepts.py` | 质检脚本（可选） |
| `{ROOT}/scripts/check_duplicate.py` | 查重脚本（可选） |
| `{ROOT}/roundtable/` | 圆桌记录目录 |
