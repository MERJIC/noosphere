---

## name: "write-page"
description: "共享概念页写入模块。负责组装 frontmatter、写入文件、自检、lint、同步。不被用户直接触发，由 parable/ingest/parable-Step7 委托调用。"

# Write Page — 概念页写入（共享模块）

纯机械层。不生成任何 section 内容。调用模块在读取本文件前必须准备好全部内容和元数据。

---

## 模式 A：新建概念页

由 `parable.md` Step 5、`ingest.md` Step 5 调用。

### 调用前提

读取本文件前，调用模块必须已确定以下全部内容：

- `concept_cn`：概念中文名（将成为文件名）
- `concept_en`：概念英文名
- `domain`：顶层学科（从 page-spec.md 11 个固定值选，支持数组）
- `source`：来源（page-spec.md 5 个固定值之一）
- `tags`：完整标签数组（顺序：discipline/ → apply/ → person/）
- `核心机制`：正文
- `入口场景`：正文
- `现实锚点`：正文
- `适用边界`：正文

入口场景的内容差异由调用模块负责：


| source             | 要求                   | 写作流程                      |
| ------------------ | -------------------- | ------------------------- |
| 寓言故事               | 300-500 字完整寓言，概念名隐藏  | parable.md Step 2         |
| 概念跳跃               | 300-500 字完整故事体，概念名可见 | parable.md Step 2（不隐藏概念名） |
| 对话整理 / 阅读沉淀 / 圆桌讨论 | 2-5 句场景片段            | 调用模块自定                    |


### 执行步骤

#### W1 — 获取日期

```bash
date +%Y-%m-%d
```

#### W2 — 组装 frontmatter

按 `modules/page-spec.md` 的 frontmatter 模板组装。字段顺序固定：name → domain → date → source → tags。

```yaml
---
name: {concept_cn}（{concept_en}）
domain: {domain}
date: {date}
source: {source}
tags: [{tags}]
---
```

**禁用字段检查**：不得出现 title、slug、created、related、updated、aliases、name_en、status、discipline。

#### W3 — 查关联图谱

**用 SQL 查询替代读文件**（concept_relations.md 随概念库增长会膨胀，查询成本固定）：

```bash
# 查集群归属（一次查出该概念所属的所有集群）
python3 scripts/sync_db.py --query "SELECT c.name FROM cluster_members cm JOIN clusters c ON cm.cluster_id = c.id JOIN concepts co ON cm.concept_id = co.id WHERE co.name = '{concept_cn}'"

# 查孤立状态
python3 scripts/sync_db.py --preset orphans
```

- 查到集群归属 → 确认调用模块提供的正文中集群内相关概念已有 `[[]]` 链接。如缺失，在写入前补上
- 查到孤立状态 → 记录：写入后它将从孤立列表移出（下次关联分析时更新）
- 两者都查不到 → 正常继续，不做特殊处理

#### W4 — 写入文件

用 Write 工具创建 `{ROOT}/概念页/{concept_cn}.md`。

文件结构：

```markdown
{frontmatter}

## 核心机制

{调用模块提供的核心机制正文}

## 入口场景

{调用模块提供的入口场景正文}

## 现实锚点

{调用模块提供的现实锚点正文}

## 适用边界

{调用模块提供的适用边界正文}
```

正文从 `## h2` 开始，无 h1 标题。**不预设圆桌 section**。

#### W5 — 自检（仅 lint 覆盖不到的 4 条）

**不重复 lint 已检查的规则**（frontmatter 格式、tags 词汇表、章节顺序、中文引号等由 W6 lint 负责）。

只检查 lint 无法覆盖的内容质量问题：

1. **否定排比**：正文是否出现「不是A而是B」「不仅A更B」→ 直接说B
2. **学者名标注准确性**：首次出现是否对照 `modules/scholar-dict.json` 标注了中文全名（英文名），后续是否只用简称
3. **`[[]]` 链接自然性**：链接是否自然嵌入正文语境，而非为了加链接而加
4. **章节内容非空洞**：每个 section 是否有实质性内容，而非只有一两句泛泛描述

发现问题立即修复。

#### W6 — lint 质检（强制）

```bash
python3 {ROOT}/scripts/lint_concepts.py --file {concept_cn}
```

- 发现 F07/F10/F11 问题需当场修复后重新 lint
- 发现其他可自动修复的问题，运行 `lint_concepts.py --fix --file {concept_cn}`
- F09（学者标注）不自动修复，当场手动处理

不可跳过。

#### W7 — 同步数据库

```bash
python3 {ROOT}/scripts/sync_db.py --file {concept_cn}
```

不可跳过。

---

## 模式 B：圆桌归位

由 `parable.md` Step 7、`ingest.md` Step 7 调用。圆桌流程结束后，将讨论内容追加到已有概念页。

### 调用前提

- `concept_cn`：目标概念名（已有概念页）
- `roundtable_content`：完整圆桌讨论内容（含嘉宾表、各轮对话、主持人综述、留存洞见）
- `trigger_question`：发起圆桌时的问题原文

### 执行步骤

#### B1 — 获取日期

```bash
date +%Y-%m-%d
```

#### B2 — 读取现有概念页

用 Read 工具读取 `{ROOT}/概念页/{concept_cn}.md` 全文。

#### B3 — 追加圆桌沉淀 section

在概念页末尾追加：

```markdown
## 圆桌沉淀

**日期：** {date}
**触发问题：** {trigger_question}

{roundtable_content}
```

写入规则：

- 完整原文保留：各嘉宾的完整论述不删减、不摘要、不转述
- 触发问题必须原文保留
- 出现的所有重要概念名用 `[[]]` 标注（包括尚未建页的虚链接）
- 有值得独立成页的衍生概念，写入后主动提出

#### B4 — 自检（仅 lint 覆盖不到的规则）

- 否定排比
- `[[]]` 链接自然性
- 圆桌内容完整性（嘉宾表四列、轮次结构完整）

发现问题立即修复。

#### B5 — lint 质检

```bash
python3 {ROOT}/scripts/lint_concepts.py --file {concept_cn}
```

F09 不自动修复，当场手动处理。

#### B6 — 同步数据库

```bash
python3 {ROOT}/scripts/sync_db.py --file {concept_cn}
```

圆桌内容写入后必须同步（捕获圆桌中的新 `[[]]` 链接和嘉宾信息）。

---

## 本模块不做的事

- 不生成任何 section 的内容（全部由调用模块完成）
- 不发起圆桌讨论
- 不做查重（查重在调用模块的更早阶段完成）
- 不补链接到已有概念页（hop 的职责）

&nbsp;
