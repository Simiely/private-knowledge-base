---
id: "docs.pitfalls.fts5-count-null"
title: "FTS5 空表 count(*) 返回 NULL，不是 0"
summary: "build 清空表的瞬间查询 count 拿到 None，int(None) 直接 TypeError。"
type: "explanation"
kind: "pitfall"
status: "resolved"
owner: "@simiely"
topics: ["development"]
source_type: "code"
source: "app/core/indexer/fts5.py"
last_reviewed: "2026-07-31"
related: []
applies_to: ["docs.architecture"]
severity: "medium"
symptom: "status() 偶发 TypeError: NoneType not subscriptable，只在索引重建窗口出现。"
cause: "FTS5 虚拟表空索引的 count 优化返回 NULL；普通表才返回 0。"
detect: "对空 FTS5 表执行 select count(*) 看返回值；或在重建时轮询 status 复现。"
avoid: "一律写 int(row[\"n\"] or 0)；涉及 FTS5 计数的地方都按可空处理。"
recover: "已抛错的请求重试即可，索引状态本身正常。"
---

# FTS5 空表 count(*) 返回 NULL，不是 0

## 影响

查询 FTS5 虚拟表计数不能假设恒为 int。
