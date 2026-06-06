---
name: 概念知识库索引
description: Dataview 动态索引，自动同步，无需手动维护
---

# 概念目录

> 由 Dataview 自动生成。新增/修改概念页后自动刷新，无需重建。

---

```dataviewjs
const pages = dv.pages("")
  .where(p => p.file.name !== "INDEX" && p.file.name !== "INDEX-DV" && p.domain);

// ── 按学科 ──
const grouped = {};
for (const p of pages) {
  for (const d of (p.domain ?? [])) {
    if (!grouped[d]) grouped[d] = [];
    grouped[d].push(p);
  }
}

const domains = ["哲学", "心理学", "经济学", "社会学", "传播学", "管理学", "生物学", "物理学", "人类学", "政治学", "艺术"];

dv.header(2, "按学科");

for (const d of domains) {
  const items = grouped[d];
  if (!items || items.length === 0) continue;
  dv.header(3, `${d}（${items.length} 个）`);
  dv.list(items.sort((a, b) => a.file.name.localeCompare(b.file.name, "zh-Hans-CN")).map(p => p.file.link));
}

// 未分类
const otherKeys = Object.keys(grouped).filter(d => !domains.includes(d));
if (otherKeys.length > 0) {
  const otherItems = otherKeys.flatMap(d => grouped[d]);
  dv.header(3, `其他（${otherItems.length} 个）`);
  dv.list(otherItems.sort((a, b) => a.file.name.localeCompare(b.file.name, "zh-Hans-CN")).map(p => p.file.link));
}

// ── 按应用场景 ──
const applyGrouped = {};
for (const p of pages) {
  const tags = p.tags ?? [];
  for (const t of tags) {
    if (t.startsWith("apply/")) {
      const val = t.slice("apply/".length);
      if (!applyGrouped[val]) applyGrouped[val] = [];
      applyGrouped[val].push(p);
    }
  }
}

dv.header(2, "按应用场景");

const applies = Object.keys(applyGrouped).sort();
for (const a of applies) {
  const items = applyGrouped[a];
  dv.header(3, `${a}（${items.length} 个）`);
  dv.list(items.sort((x, y) => x.file.name.localeCompare(y.file.name, "zh-Hans-CN")).map(p => p.file.link));
}
```
