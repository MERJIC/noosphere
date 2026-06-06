---
name: 概念知识库索引
description: Dataview 动态索引，自动同步，无需手动维护
---

# 概念目录

> 由 Dataview 自动生成。新增/修改概念页后自动刷新，无需重建。

---

## 按学科

```dataviewjs
const pages = dv.pages('"."')
  .where(p => p.file.name !== "INDEX" && p.file.name !== "INDEX-DV" && p.domain);

const grouped = {};
for (const p of pages) {
  for (const d of (p.domain ?? [])) {
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(p);
  }
}

const domains = ["哲学", "心理学", "经济学", "社会学", "传播学", "管理学", "生物学", "物理学", "人类学", "政治学", "艺术"];

let md = "";
for (const d of domains) {
  const items = grouped[d];
  if (!items || items.length === 0) continue;
  md += `### ${d}（${items.length} 个）\n\n`;
  for (const p of items.sort((a, b) => a.file.name.localeCompare(b.file.name, "zh-Hans-CN"))) {
    md += `- ${p.file.link}\n`;
  }
  md += "\n";
}

// 未分类的
const otherKeys = Object.keys(grouped).filter(d => !domains.includes(d));
if (otherKeys.length > 0) {
  const otherItems = otherKeys.flatMap(d => grouped[d]);
  md += `### 其他（${otherItems.length} 个）\n\n`;
  for (const p of otherItems.sort((a, b) => a.file.name.localeCompare(b.file.name, "zh-Hans-CN"))) {
    md += `- ${p.file.link}\n`;
  }
  md += "\n";
}

dv.paragraph(md);
```

---

## 按应用场景

```dataviewjs
const pages = dv.pages('"."')
  .where(p => p.file.name !== "INDEX" && p.file.name !== "INDEX-DV");

const grouped = {};
for (const p of pages) {
  const tags = p.tags ?? [];
  for (const t of tags) {
    if (t.startsWith("apply/")) {
      const val = t.slice("apply/".length);
      if (!grouped[val]) grouped[val] = [];
      grouped[val].push(p);
    }
  }
}

const applies = Object.keys(grouped).sort();

let md = "";
for (const a of applies) {
  const items = grouped[a];
  md += `### ${a}（${items.length} 个）\n\n`;
  for (const p of items.sort((x, y) => x.file.name.localeCompare(y.file.name, "zh-Hans-CN"))) {
    md += `- ${p.file.link}\n`;
  }
  md += "\n";
}

dv.paragraph(md);
```
