# Concept Studio Spread

> 概念库工作台的开源传播版。用 AI + Markdown 管理个人知识资产中的**学术概念沉淀**。

从 [concept-studio](https://github.com/...) 派生，去掉知识卡片模块和所有硬编码路径依赖。改一行配置就能接入你自己的概念库。

## 它是什么

一套 **Claude Code / 牛马AI Skill**，帮你：

| 能做什么 | 一句话说明 |
|---------|-----------|
| **寓言故事** | AI 选一个冷门学术原理，写成寓言讲给你听，听完可存入概念库 |
| **摄入** | 丢一个 URL 或一段文字，AI 从中提取值得沉淀的概念，自动建页 |
| **跳跃** | 以已有概念为跳板，每次推荐 3 个库里没有的新概念，链式探索 |
| **圆桌讨论** | 就任意议题发起多视角结构化辩论（学者/influencer/实践者） |
| **关联分析** | 扫描所有概念页的链接关系，识别孤立节点、集群、断链 |

产出物是 **标准化的 Markdown 概念页**，兼容 Obsidian（支持 `[[]]` 双向链接）。

## 谁适合用

- 用 Obsidian / VS Code 等 Markdown 编辑器管理笔记的人
- 有跨学科阅读习惯，想系统沉淀学术概念的人
- 用 Claude Code 或牛马AI 作为 AI 助手的人
- 不想从零设计知识库结构，想要一套「拿来就能写」的工作流的人

## 不适合

- 需要小红书/社交媒体卡片输出的人（原版 concept-studio 的 cards 模块已移除）
- 需要协同编辑或云端同步方案的人（这是本地 Markdown 工作流）
- 想要全自动知识图谱可视化的人（关联分析是文本报告，不是图形界面）

---

## 快速开始（3 步）

### 第 1 步：安装 Skill

**方式 A — 克隆到项目 skills 目录（推荐）**

```bash
# 在你的概念库项目根目录下
git clone https://github.com/your-repo/concept-studio-spread.git skills/concept-studio-spread
```

**方式 B — 克隆到全局 skills 目录**

```bash
# 所有项目都能用
git clone https://github.com/your-repo/concept-studio-spread.git ~/.newmax/skills/concept-studio-spread
```

### 第 2 步：配置路径

打开 `SKILL.md`，找到第 8 行附近的 `config` 部分：

```yaml
config:
  concept_lib_root: "{ROOT}"
```

把 `{ROOT}` 替换为你的概念库根目录的**绝对路径**。例如：

```yaml
config:
  concept_lib_root: "/Users/yourname/Documents/my-concept-lib"
```

就改这一行。其他不用动。

### 第 3 步：初始化目录结构

你的概念库根目录下需要有这些文件夹（没有的话手动创建）：

```
my-concept-lib/
├── 概念页/          # 概念 .md 文件放这里
├── memory/          # 索引文件自动生成在这里
├── scripts/         # 脚本放这里（可选）
└── roundtable/      # 圆桌记录放这里
```

```bash
mkdir -p 概念页 memory scripts roundtable
```

完成。现在可以开始用了。

---

## 使用方法

### 寓言故事

对 AI 说：

```
讲个寓言
```

或指定领域：

```
讲个寓言 经济学
```

AI 会选一个冷门原理，写成故事，讲完揭示原理名。听完觉得有价值，说「建页」就自动存入概念库。

### 摄入概念

丢 URL 或文字：

```
摄入 https://example.com/article-about-cognitive-bias
```

或直接粘贴：

```
摄入 [粘贴一段文字]
```

AI 会从中提取 1-5 个候选概念，去重后让你选。确认后自动建页、刷新索引。

### 概念跳跃

```
跳一跳
```

AI 从你的概念库里随机选一个起点，推荐 3 个新方向（延伸跳 / 跨域跳 / 意外跳）。选一个继续跳，或者「沉淀这个」存入库。

也可以指定起点：

```
跳一跳 从「证实偏差」出发
```

### 圆桌讨论

```
圆桌讨论 AI 是否具有创造力？
```

AI 自动选人、主持辩论、生成结构图。讨论记录自动保存到 `roundtable/` 目录。

### 关联分析

```
更新图谱
```

扫描全库链接关系，报告孤立节点、集群归属建议、断链记录。

---

## 概念页长什么样

每个概念是一个 `.md` 文件，放在 `概念页/` 目录下：

```markdown
---
name: 证实偏差（Confirmation Bias）
domain: [心理学]
date: 2025-05-20
source: 寓言故事
tags: [discipline/认知心理学, pattern/盲区, apply/自我, apply/决策]
---

## 核心机制

人倾向于寻找、解释、记忆那些支持自己既有信念的信息...

## 入口场景

1973 年冬天，普林斯顿大学的会议室里...

## 现实锚点

- **信息茧房**：算法推荐强化既有观点...
- **投资决策**：只看利空/利好中符合预期的那部分...

## 适用边界

不等于「所有信念都是错的」...
```

完整格式规范见 `modules/page-spec.md`。

---

## 可选：配置脚本

skill 自带两个 Python 脚本（纯标准库，无需 pip install）：

| 脚本 | 作用 | 用法 |
|------|------|------|
| `scripts/build_index.py` | 扫描概念页目录，生成索引文件 | `python3 scripts/build_index.py --root /path/to/lib` |
| `scripts/check_duplicate.py` | 检查候选概念是否已存在 | `python3 scripts/check_duplicate.py --root /path/to/lib "概念名"` |

两个脚本都支持 `--root` 参数指定概念库路径。不传 `--root` 时默认使用脚本所在目录的上级。

**脚本不是必须的。** 没有脚本也能正常使用全部 skill 功能——只是索引需要手动维护，查重需要人工比对。

---

## 目录结构

```
concept-studio-spread/
├── SKILL.md                 # ← 改这里的一行配置就行
├── README.md                # 本文件
├── modules/
│   ├── page-spec.md         # 概念页格式规范（唯一权威）
│   ├── parable.md           # 寓言故事模块
│   ├── ingest.md            # 概念摄入模块
│   ├── hop.md               # 概念跳跃模块
│   ├── roundtable.md        # 圆桌讨论模块
│   └── analyze.md           # 关联分析模块
└── scripts/
    ├── build_index.py       # 索引构建（--root 支持）
    └── check_duplicate.py   # 查重工具（--root 支持）
```

注意：**没有** `cards.md`（知识卡片模块已移除），**没有** `reference/`（CSS 样式文件不需要了）。

---

## 与原版 concept-studio 的区别

| | 原版 concept-studio | 本版 spread |
|--|---------------------|-------------|
| 知识卡片（小红书） | ✅ 有 | ❌ 移除 |
| 路径硬编码 | ✅ 写死绝对路径 | ❌ `{ROOT}` 占位符 + config |
| Noosphere 插件依赖 | ✅ 有 | ❌ 移除 |
| scholar-dict.json | ✅ 必需 | ⚪ 可选（自行维护）|
| lint_concepts.py | ✅ 建页后强制跑 | ⚪ 建议 but 不强制 |
| 适用范围 | 麦橘的个人概念库 | 任何人 |

逻辑零改动。去掉的是耦合，不是功能。

---

## 工作流示意

```
阅读/对话 → 发现有趣概念
    │
    ├─→ 「摄入」→ 自动建概念页 → 入库
    │
    ├─→ 「讲个寓言」→ AI 编故事 → 揭示原理 → 「建页」→ 入库
    │
    └─→ 「跳一跳」→ 已有概念 → 推荐 3 个新方向 → 「沉淀」→ 入库
                                                          │
                                            「更新图谱」→ 分析链接关系
                                                          │
                                            「圆桌讨论」→ 多视角深挖 → 归位到概念页
```

---

## 许可证

MIT License

---

## 贡献

Issue 和 PR 都欢迎。核心原则：
- 不加回 cards 模块（那是另一个仓库的事）
- 保持 `{ROOT}` 路径机制不动
- 新模块应在 `modules/` 下独立文件
