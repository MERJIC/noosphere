# 入口场景扩写报告 · 2026-06-06

## 背景

麦橘反馈：概念跳跃沉淀的「入口场景」过于简略。已统一规则：`hop.md` / `ingest.md` / `page-spec.md` 均引用 **`modules/parable.md` → Step 2 — 构建故事**。

## 审计标准

- `source` 为 **寓言故事** 或 **概念跳跃**
- `## 入口场景` 正文 **< 280 字** → 标为待扩写

脚本：`概念库/scripts/audit_entry_scenes.py`

```bash
python3 概念库/scripts/audit_entry_scenes.py
python3 概念库/scripts/audit_entry_scenes.py --jsonl 概念库/output/entry-scene-audit-2026-06-06.jsonl
```

## 规模

| 指标 | 数量 |
|------|------|
| 初筛待扩写 | **303** |
| 本日已处理批次 | batch-1 … batch-19（见 `output/entry-scene-batch-*.txt`） |
| 麦橘指定三页（跳跃） | 新闻回避、门控机制、带宽瓶颈 — 已按 Step 2 精修 |
| 会话末仍 <280 字 | **29**（见 `entry-scene-remaining.jsonl`，已派 agent 收尾） |

## 批次文件

- 全量清单：`output/entry-scene-audit-2026-06-06.jsonl`
- 优先最短：`output/entry-scene-batch-priority.txt`
- 分批执行：`output/entry-scene-batch-{1..19}.txt`
- 收尾清单：`output/entry-scene-remaining.jsonl`

## 后续

跑 `audit_entry_scenes.py`，若 **FLAGGED: 0** 则全库达标。若有残留，对 `entry-scene-remaining.jsonl` 再跑一轮即可。