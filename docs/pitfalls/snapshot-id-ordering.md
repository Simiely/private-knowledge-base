---
id: "docs.pitfalls.snapshot-id-ordering"
title: "id 带随机后缀后，字典序不再等于时间序"
summary: "-9c93 与 -4515 的字典序和创建顺序相反，sorted 取到错的「最新」。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/backup/engine.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "high"
symptom: "快照列表顺序错乱；按 id 倒序取到旧快照。"
cause: "修复重复 id 时加了随机后缀，破坏了原本「id 即时间」的假设。"
detect: "造两个同一秒的快照，比较 sorted(ids) 与 createdAt 顺序。"
avoid: "排序统一在 list_snapshots() 内按 createdAt 降序；外部禁止依赖 id 序。"
recover: "改调用点即可，不改数据。"
---

# id 带随机后缀后，字典序不再等于时间序

## 影响

与「id 加随机后缀」是同一次修复的两面。
